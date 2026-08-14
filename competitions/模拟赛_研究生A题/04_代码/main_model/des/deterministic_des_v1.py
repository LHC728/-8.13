"""G2-03 deterministic minimal parallel DES engine (Python standard library only).

Implements the frozen G2-03-SPEC-V1.0.2 semantics:

* frozen_event_engine_semantics SEM-01..SEM-24 (see module docstrings of each
  method and the completion report);
* same_timestamp_event_order A..I (V1.0.2 executable refinement):
  A settle_completed_activities -> B materialize_test_observations ->
  C classify_outcomes -> D apply_device_exit -> E cancel_unfinished ->
  E2 materialize_D_for_newly_E_eligible_devices -> SHIFT_CHANGE -> F
  release_tasks -> G recompute_legal_candidates -> H dispatch_by_fcfs ->
  I liveness_closure (completion always settles before the shift change;
  D_CREATED is emitted before the same-timestamp E TASK_RELEASE);
* explicit state objects from ``state_models_v1`` (never hidden in locals);
* FCFS key (release_time, device_id, process_order, effective_attempt_no) with
  squad_id/execution_no/restart_no excluded; release_time frozen at creation;
* exact Fraction arithmetic, half-open intervals [start, end), no float, no
  epsilon, no RNG;
* scripted outcomes: every completed effective test MUST have a scripted
  (device, process, effective_attempt_no) outcome, otherwise an explicit
  MissingScriptedOutcome failure is raised; there is no default PASS/NORMAL;
* D generation (V1.0.2): materialized exactly once, in the E2 substep, at the
  same timestamp where the device's A/B/C flow first becomes fully PASSED (=
  its E logical release timestamp), BEFORE the E TASK_RELEASE is emitted and
  never at/from the E ACTIVITY_START; E retests never regenerate D; early-exit
  devices keep d_state=not_created; devices marked device_exit in the same
  closure never get D;
* SEM-21 initial-state rule: batch_size==1 => preloaded_devices == [1];
  batch_size>=2 => preloaded_devices == [1,2]; anything else raises
  DesPreloadRuleError (explicit FAIL, no EMPTY-bay bypass for batch>=2);
* event_log: append-only, deterministic (seq strictly increasing), every time
  serialized as an exact fraction/integer string, sufficient for the future
  G2-04 checker to recompute bay/resource occupancy, release/start/end,
  effective attempt, outcomes, cancellation, shifts, turnover, terminal state,
  T and the YXB/age ledger seam without importing this state machine.

The engine only implements the deterministic fixed-FCFS "start every legal
head as soon as feasible" verification baseline (H in the frozen order). It is
NOT an H1 formal experiment and produces no formal results.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Optional

from . import state_models_v1 as sm

RESOURCES = sm.RESOURCES
PROCESS_ORDER = sm.PROCESS_ORDER
DEFAULT_DURATIONS_H = sm.DEFAULT_DURATIONS_H


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DesError(Exception):
    """Base class for deterministic DES failures."""


class DesConfigError(DesError):
    """Invalid input configuration."""


class DesPreloadRuleError(DesConfigError):
    """SEM-21 (G2-03-SPEC-V1.0.2) initial-state rule violation.

    batch_size==1 requires deterministic_initial_state.preloaded_devices == [1]
    and batch_size>=2 requires exactly [1,2]. Any other preload (including a
    prefix like [1] for batch>=2, which would leave a bay EMPTY and bypass the
    frozen "first two devices already in the hall" initial state) is an
    explicit FAIL.
    """


class DesFixtureError(DesError):
    """Invalid or incomplete scripted fixture."""


class MissingScriptedOutcome(DesFixtureError):
    """A completed effective test has no scripted outcome (explicit FAIL,
    never a default PASS/NORMAL)."""

    def __init__(self, device_id: int, process: str, attempt_no: int) -> None:
        self.device_id = device_id
        self.process = process
        self.attempt_no = attempt_no
        super().__init__(
            f"MISSING_SCRIPTED_OUTCOME: (device_id={device_id}, process={process}, "
            f"effective_attempt_no={attempt_no}) has no scripted outcome"
        )


class LivenessError(DesError):
    """Unfinished work exists but the calendar is empty and there is no future
    shift boundary (CR-V3.1/C18 violation)."""


class ZeroTimeLoopError(DesError):
    """An event would re-schedule itself at the same timestamp (no zero-time
    loops allowed)."""


# ---------------------------------------------------------------------------
# Configuration and scripted fixture
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DesConfig:
    scenario_id: str
    scenario: str
    batch_size: int
    shift_length_h: Fraction
    shifts_per_day: int
    durations: dict[str, Fraction]  # per process A/B/C/E
    transport_out_h: Fraction
    transport_in_h: Fraction
    turnover_profile: str
    preloaded_devices: tuple[int, ...]
    random_enabled: bool
    key_schema_version: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DesConfig":
        if not isinstance(raw, dict):
            raise DesConfigError("config must be a JSON object")
        if raw.get("schema_version") != "des_config_v1":
            raise DesConfigError("config.schema_version must be 'des_config_v1'")
        if raw.get("random_enabled") is not False:
            raise DesConfigError("G2-03 is deterministic: random_enabled must be false")
        if raw.get("key_schema_version") != sm.KEY_SCHEMA_VERSION:
            raise DesConfigError("config.key_schema_version must be 'key_schema_v1'")

        scenario = raw.get("scenario")
        if scenario not in sm.SCENARIOS:
            raise DesConfigError(f"config.scenario must be one of {sm.SCENARIOS}")
        scenario_id = raw.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise DesConfigError("config.scenario_id must be a non-empty string")

        batch_size = raw.get("batch_size")
        if not isinstance(batch_size, int) or batch_size < 1:
            raise DesConfigError("config.batch_size must be a positive integer")

        shift_length_h = _parse_positive(raw.get("shift_length_h"), "shift_length_h")
        shifts_per_day = raw.get("shifts_per_day")
        if not isinstance(shifts_per_day, int) or shifts_per_day < 1:
            raise DesConfigError("config.shifts_per_day must be a positive integer")

        durations_raw = raw.get("durations")
        if not isinstance(durations_raw, dict):
            raise DesConfigError("config.durations must be an object")
        durations: dict[str, Fraction] = {}
        for proc in RESOURCES:
            if proc not in durations_raw:
                raise DesConfigError(f"config.durations missing process {proc}")
            durations[proc] = _parse_positive(durations_raw[proc], f"durations.{proc}")

        transport_out = _parse_nonnegative(raw.get("transport_out_h"), "transport_out_h")
        transport_in = _parse_nonnegative(raw.get("transport_in_h"), "transport_in_h")
        turnover_profile = raw.get("turnover_profile")
        if turnover_profile not in sm.TURNOVER_PROFILES:
            raise DesConfigError(
                f"config.turnover_profile must be one of {sm.TURNOVER_PROFILES}"
            )

        initial = raw.get("deterministic_initial_state")
        if not isinstance(initial, dict):
            raise DesConfigError("config.deterministic_initial_state must be an object")
        if initial.get("all_calibrated") is not True:
            raise DesConfigError("deterministic_initial_state.all_calibrated must be true")
        if initial.get("queues_empty") is not True:
            raise DesConfigError("deterministic_initial_state.queues_empty must be true")
        preloaded = initial.get("preloaded_devices")
        if not isinstance(preloaded, list) or not preloaded:
            raise DesConfigError("deterministic_initial_state.preloaded_devices must be a non-empty list")
        if any(not isinstance(p, int) or p < 1 for p in preloaded):
            raise DesConfigError("preloaded_devices must contain positive integers")
        # SEM-21 (G2-03-SPEC-V1.0.2, Human Gate final ruling): the t=0 initial
        # state is frozen to exactly [1] for batch_size==1 (bay2=EMPTY legal)
        # and exactly [1,2] for batch_size>=2 (bay1=device1, bay2=device2).
        # Anything else — including the V1.0.1-era prefix [1] for batch>=2 —
        # is an explicit FAIL; batch>=2 must never bypass the first-two
        # preloaded devices through an EMPTY bay.
        expected_preload = [1] if batch_size == 1 else [1, 2]
        if preloaded != expected_preload:
            raise DesPreloadRuleError(
                f"SEM-21 initial-state rule: batch_size=={batch_size} requires "
                f"deterministic_initial_state.preloaded_devices == "
                f"{expected_preload!r}, got {preloaded!r}"
            )

        return cls(
            scenario_id=scenario_id,
            scenario=scenario,
            batch_size=batch_size,
            shift_length_h=shift_length_h,
            shifts_per_day=shifts_per_day,
            durations=durations,
            transport_out_h=transport_out,
            transport_in_h=transport_in,
            turnover_profile=turnover_profile,
            preloaded_devices=tuple(preloaded),
            random_enabled=False,
            key_schema_version=sm.KEY_SCHEMA_VERSION,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "des_config_v1",
            "scenario_id": self.scenario_id,
            "scenario": self.scenario,
            "batch_size": self.batch_size,
            "shift_length_h": sm.fraction_to_string(self.shift_length_h),
            "shifts_per_day": self.shifts_per_day,
            "durations": {p: sm.fraction_to_string(self.durations[p]) for p in RESOURCES},
            "transport_out_h": sm.fraction_to_string(self.transport_out_h),
            "transport_in_h": sm.fraction_to_string(self.transport_in_h),
            "turnover_profile": self.turnover_profile,
            "deterministic_initial_state": {
                "preloaded_devices": list(self.preloaded_devices),
                "all_calibrated": True,
                "queues_empty": True,
            },
            "random_enabled": False,
            "key_schema_version": sm.KEY_SCHEMA_VERSION,
        }


@dataclass(frozen=True)
class ScriptedFixture:
    """Scripted real states + scripted observations. No RNG anywhere.

    real_states: {device_id: {"A": "normal"|"problem", "B": ..., "C": ...,
                              "D": "normal"|"problem"|"not_created"}}
    outcomes: {(device_id, process, attempt_no): "PASS"|"ABNORMAL"}
    """

    fixture_id: str
    real_states: dict[int, dict[str, str]]
    outcomes: dict[tuple[int, str, int], str]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ScriptedFixture":
        if not isinstance(raw, dict):
            raise DesFixtureError("scripted fixture must be a JSON object")
        fixture_id = raw.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id:
            raise DesFixtureError("scripted fixture needs a non-empty fixture_id")

        real_raw = raw.get("scripted_real_states")
        if not isinstance(real_raw, dict):
            raise DesFixtureError("scripted_real_states must be an object keyed by device_id")
        real_states: dict[int, dict[str, str]] = {}
        for dev_key, state in real_raw.items():
            device_id = int(dev_key)
            if not isinstance(state, dict):
                raise DesFixtureError(f"real state of device {device_id} must be an object")
            real_states[device_id] = {}
            for proc in ("A", "B", "C"):
                if proc not in state:
                    raise DesFixtureError(f"real state of device {device_id} missing {proc}")
                if state[proc] not in ("normal", "problem"):
                    raise DesFixtureError(f"real state {proc} of device {device_id} must be normal|problem")
                real_states[device_id][proc] = state[proc]
            if "D" not in state:
                raise DesFixtureError(f"real state of device {device_id} missing D")
            if state["D"] not in ("normal", "problem", "not_created"):
                raise DesFixtureError(f"real state D of device {device_id} must be normal|problem|not_created")
            real_states[device_id]["D"] = state["D"]

        outcomes_raw = raw.get("scripted_outcomes")
        if not isinstance(outcomes_raw, list):
            raise DesFixtureError("scripted_outcomes must be a list")
        outcomes: dict[tuple[int, str, int], str] = {}
        for item in outcomes_raw:
            if not isinstance(item, dict):
                raise DesFixtureError("scripted_outcomes items must be objects")
            device_id = item.get("device_id")
            process = item.get("process")
            attempt = item.get("effective_attempt_no")
            outcome = item.get("outcome")
            if not isinstance(device_id, int) or process not in RESOURCES or attempt not in (1, 2):
                raise DesFixtureError(f"bad scripted outcome item: {item!r}")
            if outcome not in ("PASS", "ABNORMAL"):
                raise DesFixtureError(f"bad scripted outcome value: {outcome!r}")
            key = (device_id, process, attempt)
            if key in outcomes:
                raise DesFixtureError(f"duplicate scripted outcome {key!r}")
            outcomes[key] = outcome

        return cls(fixture_id=fixture_id, real_states=real_states, outcomes=outcomes)

    def outcome_for(self, device_id: int, process: str, attempt_no: int) -> str:
        key = (device_id, process, attempt_no)
        if key not in self.outcomes:
            raise MissingScriptedOutcome(device_id, process, attempt_no)
        return self.outcomes[key]

    def real_state(self, device_id: int, process: str) -> str:
        return self.real_states[device_id][process]

    def d_script(self, device_id: int) -> str:
        return self.real_states[device_id]["D"]


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class DesRunResult:
    config: DesConfig
    event_log: list[dict[str, Any]]  # append-only, deterministic
    metrics: dict[str, Any]  # run-level counts / ratios (NOT formal results)
    summary: dict[str, Any]  # terminal states and ledgers for tests


def make_fcfs_key(release_time: Fraction, device_id: int, process: str,
                  attempt_no: int) -> tuple:
    """Frozen canonical FCFS key: (release_time, device_id, process_order,
    effective_attempt_no) with dictionary order (G2-03-SPEC-V1.0.2 section 7).

    squad_id / execution_no / restart_no are deliberately not parameters and
    never enter the key (SEM-17, CR-V3.1/C11)."""
    if not isinstance(release_time, Fraction):
        release_time = sm.string_to_fraction(str(release_time))
    return (release_time, device_id, PROCESS_ORDER[process], attempt_no)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class DeterministicDesEngine:
    def __init__(self, config: DesConfig, scripted: ScriptedFixture) -> None:
        self.config = config
        self.scripted = scripted
        self.now: Fraction = Fraction(0)
        self._seq: int = 0
        self.log: list[sm.LogRecord] = []
        # calendar: heap of (time, order_seq, kind, token)
        self._calendar: list[tuple[Fraction, int, str, Any]] = []
        self._cal_seq: int = 0
        self._cancelled_attempts: set[str] = set()
        self.devices: dict[int, sm.DeviceState] = {}
        self.resources: dict[str, sm.ResourceState] = {}
        self.bays: dict[int, sm.BayState] = {}
        self.tasks: dict[str, sm.TaskState] = {}
        self.attempts: dict[str, sm.TestAttemptState] = {}
        self.queues: dict[str, list[sm.QueueEntry]] = {r: [] for r in RESOURCES}
        self.shift_state: sm.ShiftCalendarState = sm.ShiftCalendarState(
            scenario=config.scenario,
            shift_length_h=config.shift_length_h,
            shifts_per_day=config.shifts_per_day,
        )
        # elapsed test-runtime ledger per process group (YXB numerator and age
        # ledger seam share this source; cancelled fragments included).
        self.ledger_elapsed: dict[str, Fraction] = {r: Fraction(0) for r in RESOURCES}
        self._pending_retests: dict[tuple[int, str], Fraction] = {}
        self._pending_creations: list[int] = []  # devices entering via turnover-in
        self._created_count: int = 0
        self._init_state()

    # -- initialization ----------------------------------------------------

    def _init_state(self) -> None:
        for r in RESOURCES:
            self.resources[r] = sm.ResourceState(resource_id=r)
        for bay_id in (1, 2):
            self.bays[bay_id] = sm.BayState(
                bay_id=bay_id, status=sm.BayStatus.EMPTY,
                turnover_profile=self.config.turnover_profile,
            )
        for idx, device_id in enumerate(self.config.preloaded_devices):
            bay_id = idx + 1
            self._create_device(device_id, Fraction(0), bay_id)
            self._pending_creations.append(device_id)

    def _create_device(self, device_id: int, entry_time: Fraction, bay_id: int) -> None:
        device = sm.DeviceState(
            device_id=device_id,
            entry_time=entry_time,
            bay_id=bay_id,
            process_state={p: sm.ProcessState(process=p) for p in RESOURCES},
        )
        self.devices[device_id] = device
        self._created_count = max(self._created_count, device_id)
        bay = self.bays[bay_id]
        bay.current_device_id = device_id
        bay.status = sm.BayStatus.OCCUPIED_TESTING
        bay.transport_phase = "none"

    # -- FCFS / release -----------------------------------------------------

    def _task_id(self, device_id: int, process: str, attempt_no: int) -> str:
        return f"D{device_id:03d}_{process}_{attempt_no}"

    def _release_task(self, device_id: int, process: str, attempt_no: int,
                      release_time: Fraction) -> sm.TaskState:
        task_id = self._task_id(device_id, process, attempt_no)
        if task_id in self.tasks:
            raise DesError(f"task {task_id} already exists")
        task = sm.TaskState(
            task_id=task_id,
            resource_id=process,
            device_id=device_id,
            process=process,
            effective_attempt_no=attempt_no,
            release_time=release_time,  # frozen at creation, never rewritten
        )
        self.tasks[task_id] = task
        key = make_fcfs_key(release_time, device_id, process, attempt_no)
        entry = sm.QueueEntry(queue_id=process, task_id=task_id, fcfs_key=key)
        self.queues[process].append(entry)
        self._emit(
            sm.EventType.TASK_RELEASE,
            device_id=device_id,
            process=process,
            effective_attempt_no=attempt_no,
            resource_id=process,
            task_id=task_id,
            release_time=release_time,
        )
        return task

    # -- shift calendar -----------------------------------------------------

    def _shift_start(self, index: int) -> Optional[Fraction]:
        scenario = self.config.scenario
        if scenario == "q3_two_shift":
            day = index // self.config.shifts_per_day
            slot = index % self.config.shifts_per_day
            return day * Fraction(24) + slot * self.config.shift_length_h
        if scenario == "q2_single_shift":
            return index * Fraction(24)
        # isolated_small_case: one very long single shift
        if index == 0:
            return Fraction(0)
        return None

    def _shift_end(self, index: int) -> Optional[Fraction]:
        start = self._shift_start(index)
        if start is None:
            return None
        return start + self.config.shift_length_h

    def _squad(self, index: int) -> int:
        if self.config.scenario == "q3_two_shift":
            return 1 if index % 2 == 0 else 2
        return 1

    def _shift_at(self, t: Fraction) -> Optional[sm.ShiftInfo]:
        """Active shift containing t (half-open [start, end)), or None (gap)."""
        index = 0
        while True:
            start = self._shift_start(index)
            if start is None:
                return None
            end = self._shift_end(index)
            assert end is not None
            if start <= t < end:
                return sm.ShiftInfo(index, start, end, self._squad(index))
            if t < start:
                return None
            index += 1

    def _next_shift_boundary_after(self, t: Fraction) -> Optional[Fraction]:
        index = 0
        while True:
            start = self._shift_start(index)
            if start is None:
                return None
            end = self._shift_end(index)
            assert end is not None
            if t < start:
                return start
            if t < end:
                return end
            index += 1

    # -- calendar helpers ---------------------------------------------------

    def _schedule(self, kind: str, time: Fraction, token: Any) -> None:
        self._cal_seq += 1
        heapq.heappush(self._calendar, (time, self._cal_seq, kind, token))

    def _calendar_min(self) -> Optional[Fraction]:
        if not self._calendar:
            return None
        return self._calendar[0][0]

    # -- log ----------------------------------------------------------------

    def _emit(self, event_type: sm.EventType, **fields: Any) -> sm.LogRecord:
        self._seq += 1
        record = sm.LogRecord(seq=self._seq, event_time=self.now, event_type=event_type.value, **fields)
        self.log.append(record)
        return record

    # -- main loop ----------------------------------------------------------

    def run(self) -> DesRunResult:
        self._closure(Fraction(0))
        while True:
            if self._is_terminal():
                self._emit(sm.EventType.SIMULATION_END)
                break
            nxt = self._next_event_time()
            if nxt <= self.now:
                raise ZeroTimeLoopError(
                    f"no progress: next event time {nxt} not after current time {self.now}"
                )
            cal_min = self._calendar_min()
            boundary = self._next_shift_boundary_after(self.now)
            if cal_min is None and boundary is not None and nxt == boundary:
                # Pure liveness wake-up (CR-V3.1/C18): calendar empty but
                # unfinished work exists -> jump to the next shift boundary.
                self.now = nxt
                self._emit(sm.EventType.WAKE_UP)
            self._closure(nxt)
        return DesRunResult(
            config=self.config,
            event_log=[record.to_dict() for record in self.log],
            metrics=self._metrics(),
            summary=self._summary(),
        )

    def _next_event_time(self) -> Fraction:
        candidates: list[Fraction] = []
        cal_min = self._calendar_min()
        if cal_min is not None:
            candidates.append(cal_min)
        boundary = self._next_shift_boundary_after(self.now)
        if boundary is not None:
            candidates.append(boundary)
        if not candidates:
            raise LivenessError(
                "calendar empty and no future shift boundary while work is unfinished"
            )
        return min(candidates)

    def _is_terminal(self) -> bool:
        if any(d.terminal_state == sm.TerminalState.PENDING for d in self.devices.values()):
            return False
        if self._calendar:
            return False
        if any(t.status in (sm.TaskStatus.READY, sm.TaskStatus.RUNNING) for t in self.tasks.values()):
            return False
        if any(b.turnover_pending for b in self.bays.values()):
            return False
        return True

    # -- same-timestamp closure (frozen order A..I; V1.0.2 E2 refinement) -----

    def _closure(self, t: Fraction) -> None:
        self.now = t

        # --- A. settle_completed_activities ---------------------------------
        completed: list[sm.TestAttemptState] = []
        turnover_out_done: list[int] = []
        turnover_in_done: list[int] = []
        while self._calendar and self._calendar[0][0] == t:
            _time, _cseq, kind, token = heapq.heappop(self._calendar)
            if kind == "test_complete":
                if token in self._cancelled_attempts:
                    continue  # lazy deletion of cancelled fragments
                attempt = self.attempts[token]
                attempt.status = sm.AttemptStatus.COMPLETED
                attempt.end_time = t
                task = self.tasks[attempt.task_id]
                task.status = sm.TaskStatus.COMPLETED
                res = self.resources[task.resource_id]
                res.status = sm.ResourceStatus.IDLE
                res.current_activity = None
                elapsed = attempt.end_time - attempt.start_time
                assert elapsed is not None and elapsed > Fraction(0)
                self.ledger_elapsed[task.process] += elapsed
                completed.append(attempt)
            elif kind == "turnover_out_complete":
                turnover_out_done.append(token)
            elif kind == "turnover_in_complete":
                turnover_in_done.append(token)

        def _attempt_sort_key(attempt: sm.TestAttemptState):
            return (
                attempt.device_id,
                PROCESS_ORDER[attempt.process],
                attempt.effective_attempt_no,
            )

        completed.sort(key=_attempt_sort_key)
        for attempt in completed:
            task = self.tasks[attempt.task_id]
            self._emit(
                sm.EventType.ACTIVITY_COMPLETE,
                device_id=attempt.device_id,
                process=attempt.process,
                effective_attempt_no=attempt.effective_attempt_no,
                resource_id=task.resource_id,
                bay_id=self.devices[attempt.device_id].bay_id,
                squad_id=attempt.result_squad_id,
                task_id=task.task_id,
                attempt_start_time=attempt.start_time,
                attempt_end_time=attempt.end_time,
                outcome=sm.Outcome.NONE.value,
                elapsed_hours=attempt.end_time - attempt.start_time,
            )

        # Turnover out completion -> in phase (or, for the 0.5h overlap
        # profile, instantaneous handover: out and in coincide at t).
        for bay_id in sorted(turnover_out_done):
            bay = self.bays[bay_id]
            self._emit(
                sm.EventType.TURNOVER_OUT_COMPLETE,
                bay_id=bay_id,
                device_id=bay.current_device_id,
            )
            if self.config.turnover_profile == "0.5h_overlap":
                self._emit(
                    sm.EventType.TURNOVER_IN_START,
                    bay_id=bay_id,
                    device_id=bay.current_device_id,
                )
                self._emit(
                    sm.EventType.TURNOVER_IN_COMPLETE,
                    bay_id=bay_id,
                    device_id=bay.current_device_id,
                )
                self._finish_turnover_in(bay, t)
            else:
                bay.status = sm.BayStatus.OCCUPIED_TRANSPORT_IN
                bay.transport_phase = "in"
                self._emit(
                    sm.EventType.TURNOVER_IN_START,
                    bay_id=bay_id,
                    device_id=bay.current_device_id,
                )
                self._schedule(
                    "turnover_in_complete", t + self.config.transport_in_h, bay_id
                )
        for bay_id in sorted(turnover_in_done):
            bay = self.bays[bay_id]
            self._emit(
                sm.EventType.TURNOVER_IN_COMPLETE,
                bay_id=bay_id,
                device_id=bay.current_device_id,
            )
            self._finish_turnover_in(bay, t)

        # --- B. materialize_observations ------------------------------------
        for attempt in completed:
            outcome = self.scripted.outcome_for(
                attempt.device_id, attempt.process, attempt.effective_attempt_no
            )
            attempt.outcome = outcome
            self.tasks[attempt.task_id].outcome = outcome
            self._emit(
                sm.EventType.OBSERVATION_MATERIALIZED,
                device_id=attempt.device_id,
                process=attempt.process,
                effective_attempt_no=attempt.effective_attempt_no,
                resource_id=self.tasks[attempt.task_id].resource_id,
                outcome=outcome,
            )

        # --- C. classify_outcomes -------------------------------------------
        exit_devices: list[tuple[int, str]] = []
        passed_devices: list[int] = []  # E passed in this closure -> terminal PASSED
        for attempt in completed:
            device = self.devices[attempt.device_id]
            ps = device.process_state[attempt.process]
            ps.outcome_history.append(attempt.outcome)
            if attempt.outcome == sm.Outcome.PASS.value:
                ps.process_status = sm.ProcessStatus.PASSED
                if attempt.process == "E":
                    passed_devices.append(attempt.device_id)
            else:  # ABNORMAL
                if attempt.effective_attempt_no == 1:
                    ps.process_status = sm.ProcessStatus.AWAITING_RETEST
                    ps.first_failure_time = t
                    self._pending_retests[(attempt.device_id, attempt.process)] = t
                else:
                    exit_devices.append((attempt.device_id, attempt.process))

        # --- D. apply_device_exit / terminal ---------------------------------
        exit_device_ids = sorted({device_id for device_id, _proc in exit_devices})
        for device_id in exit_device_ids:
            device = self.devices[device_id]
            device.terminal_state = sm.TerminalState.EXITED
            device.exit_reason = sm.TERMINAL_REASON_SECOND_ABNORMAL
            self._emit(
                sm.EventType.DEVICE_EXIT,
                device_id=device_id,
                process=",".join(
                    sorted(
                        proc for dev_id, proc in exit_devices if dev_id == device_id
                    )
                ),
                effective_attempt_no=2,
            )
            self._emit(
                sm.EventType.DEVICE_TERMINAL,
                device_id=device_id,
                terminal_state=sm.TerminalState.EXITED.value,
                terminal_reason=sm.TERMINAL_REASON_SECOND_ABNORMAL,
            )
        for device_id in sorted(set(passed_devices) - set(exit_device_ids)):
            device = self.devices[device_id]
            device.terminal_state = sm.TerminalState.PASSED
            self._emit(
                sm.EventType.DEVICE_TERMINAL,
                device_id=device_id,
                terminal_state=sm.TerminalState.PASSED.value,
                terminal_reason=None,
            )

        # --- E. cancel_unfinished --------------------------------------------
        for device_id in exit_device_ids:
            for task in sorted(
                (task for task in self.tasks.values() if task.device_id == device_id),
                key=lambda task: (
                    PROCESS_ORDER[task.process],
                    task.effective_attempt_no,
                    task.task_id,
                ),
            ):
                if task.status == sm.TaskStatus.COMPLETED:
                    continue
                if task.status == sm.TaskStatus.RUNNING:
                    attempt = self._running_attempt_of(task)
                    if attempt is None:  # pragma: no cover - defensive
                        continue
                    attempt.status = sm.AttemptStatus.CANCELLED
                    attempt.end_time = t
                    self._cancelled_attempts.add(attempt.attempt_id)
                    res = self.resources[task.resource_id]
                    res.status = sm.ResourceStatus.IDLE
                    res.current_activity = None
                    elapsed = t - attempt.start_time
                    assert elapsed is not None and elapsed > Fraction(0)
                    self.ledger_elapsed[task.process] += elapsed
                    task.status = sm.TaskStatus.CANCELLED
                    self._emit(
                        sm.EventType.TASK_CANCEL,
                        device_id=device_id,
                        process=task.process,
                        effective_attempt_no=task.effective_attempt_no,
                        resource_id=task.resource_id,
                        bay_id=self.devices[device_id].bay_id,
                        squad_id=attempt.result_squad_id,
                        task_id=task.task_id,
                        attempt_start_time=attempt.start_time,
                        attempt_end_time=t,
                        outcome=sm.Outcome.NONE.value,
                        cancel_reason=sm.CancelReason.DEVICE_EXIT.value,
                        elapsed_hours=elapsed,
                    )
                else:  # READY (never started): no runtime fragment
                    self._remove_queue_entry(task)
                    task.status = sm.TaskStatus.CANCELLED
                    self._emit(
                        sm.EventType.TASK_CANCEL,
                        device_id=device_id,
                        process=task.process,
                        effective_attempt_no=task.effective_attempt_no,
                        resource_id=task.resource_id,
                        bay_id=self.devices[device_id].bay_id,
                        task_id=task.task_id,
                        outcome=sm.Outcome.NONE.value,
                        cancel_reason=sm.CancelReason.DEVICE_EXIT.value,
                        elapsed_hours=Fraction(0),
                    )

        # --- E2. materialize_D_for_newly_E_eligible_devices (V1.0.2) ---------
        # D is generated exactly once, at the timestamp where the A/B/C flow
        # first becomes fully PASSED (== the E logical release timestamp),
        # BEFORE the E TASK_RELEASE (step F) so that
        # D_CREATED.seq < TASK_RELEASE(E).seq at the same timestamp.
        # E ACTIVITY_START must never create/change D; E retests never
        # regenerate D; devices marked device_exit in this same closure
        # (terminal_state != PENDING) never get D; early-exit devices keep
        # d_state=not_created.
        for device_id in sorted(self.devices):
            device = self.devices[device_id]
            if device.terminal_state != sm.TerminalState.PENDING:
                continue  # includes same-timestamp second-abnormal exits
            if device.d_state != sm.DState.NOT_CREATED:
                continue  # already materialized (E retest / later closures)
            if not all(
                device.process_state[p].process_status == sm.ProcessStatus.PASSED
                for p in ("A", "B", "C")
            ):
                continue  # not yet E-eligible
            e_task_id = self._task_id(device_id, "E", 1)
            if e_task_id in self.tasks:
                continue  # E initial task already produced (defensive)
            d_script = self.scripted.d_script(device_id)
            if d_script == "not_created":
                raise DesFixtureError(
                    f"device {device_id} becomes E-eligible but scripted D is "
                    "'not_created' (fixture inconsistency)"
                )
            device.d_state = sm.DState(d_script)
            squad = None
            if self.shift_state.active_shift is not None:
                squad = self.shift_state.active_shift.on_duty_squad
            self._emit(
                sm.EventType.D_CREATED,
                device_id=device_id,
                d_state=device.d_state.value,
                bay_id=device.bay_id,
                squad_id=squad,
            )

        # --- SHIFT_CHANGE (settle first, then shift; K9 rule) ----------------
        new_shift = self._shift_at(t)
        if new_shift != self.shift_state.active_shift:
            self.shift_state.active_shift = new_shift
            if new_shift is not None:
                self.shift_state.next_shift_wake_up_time = (
                    self._next_shift_boundary_after(t)
                )
                self._emit(
                    sm.EventType.SHIFT_CHANGE,
                    shift_index=new_shift.shift_index,
                    shift_start=new_shift.shift_start,
                    shift_end=new_shift.shift_end,
                    on_duty_squad=new_shift.on_duty_squad,
                    squad_id=new_shift.on_duty_squad,
                )

        # --- F. release_tasks ------------------------------------------------
        for device_id in sorted(self._pending_creations):
            device = self.devices[device_id]
            for proc in ("A", "B", "C"):
                device.process_state[proc].process_status = sm.ProcessStatus.IN_PROGRESS
                self._release_task(device_id, proc, 1, device.entry_time)
        self._pending_creations.clear()

        for (device_id, process), release_time in sorted(
            self._pending_retests.items()
        ):
            device = self.devices[device_id]
            if device.terminal_state != sm.TerminalState.PENDING:
                continue  # device exited in this closure; retest is moot
            self._release_task(device_id, process, 2, release_time)
        self._pending_retests.clear()

        for device_id in sorted(self.devices):
            device = self.devices[device_id]
            if device.terminal_state != sm.TerminalState.PENDING:
                continue
            if device.process_state["E"].process_status == sm.ProcessStatus.PASSED:
                continue
            e_task_id = self._task_id(device_id, "E", 1)
            if e_task_id in self.tasks:
                continue  # E already released (READY/RUNNING)
            if all(
                device.process_state[p].process_status == sm.ProcessStatus.PASSED
                for p in ("A", "B", "C")
            ):
                device.process_state["E"].process_status = sm.ProcessStatus.IN_PROGRESS
                self._release_task(device_id, "E", 1, t)

        for bay_id in sorted(self.bays):
            bay = self.bays[bay_id]
            if bay.turnover_pending or bay.current_device_id is None:
                continue
            if bay.status != sm.BayStatus.OCCUPIED_TESTING:
                continue  # already in transport phase or terminal-until-stop
            device = self.devices[bay.current_device_id]
            if device.terminal_state == sm.TerminalState.PENDING:
                continue
            if self._next_device_to_create() > self.config.batch_size:
                bay.status = sm.BayStatus.TERMINAL_OCCUPIED_UNTIL_STOP
                continue
            bay.turnover_pending = True

        # --- G + H. recompute_legal_candidates + dispatch_by_fcfs -------------
        starts: list[tuple[tuple, dict[str, Any], sm.TestAttemptState]] = []
        for resource_id in RESOURCES:
            resource = self.resources[resource_id]
            queue = self.queues[resource_id]
            if resource.status != sm.ResourceStatus.IDLE:
                continue
            if not queue:
                continue
            head = queue[0]
            if head.status != sm.QueueEntryStatus.WAITING:
                continue
            if self._is_legal(head):
                attempt = self._start_task(head)
                starts.append((head.fcfs_key, self._start_payload(attempt), attempt))

        for bay_id in sorted(self.bays):
            bay = self.bays[bay_id]
            if not bay.turnover_pending:
                continue
            if bay.status != sm.BayStatus.OCCUPIED_TESTING:
                continue
            shift = self.shift_state.active_shift
            if shift is None:
                continue
            total = self._turnover_total_h()
            if t + total > shift.shift_end:
                continue  # non-preemptive within shift (SEM-18): wait for next shift
            bay.turnover_pending = False
            bay.status = sm.BayStatus.OCCUPIED_TRANSPORT_OUT
            bay.transport_phase = "out"
            self._emit(
                sm.EventType.TURNOVER_OUT_START,
                bay_id=bay_id,
                device_id=bay.current_device_id,
                squad_id=shift.on_duty_squad,
            )
            self._schedule(
                "turnover_out_complete", t + self.config.transport_out_h, bay_id
            )

        starts.sort(key=lambda item: item[0])
        for _key, payload, attempt in starts:
            # V1.0.2: the E ACTIVITY_START must never create or change D.
            # D is materialized earlier in this closure (E2 substep), at the
            # A/B/C all-PASS timestamp, before the E TASK_RELEASE.
            self._emit(sm.EventType.ACTIVITY_START, **payload)

    # -- dispatch helpers ---------------------------------------------------

    def _next_device_to_create(self) -> int:
        return self._created_count + 1

    def _running_attempt_of(self, task: sm.TaskState) -> Optional[sm.TestAttemptState]:
        for attempt in self.attempts.values():
            if attempt.task_id == task.task_id and attempt.status == sm.AttemptStatus.RUNNING:
                return attempt
        return None

    def _remove_queue_entry(self, task: sm.TaskState) -> None:
        queue = self.queues[task.resource_id]
        for idx, entry in enumerate(queue):
            if entry.task_id == task.task_id:
                entry.status = sm.QueueEntryStatus.REMOVED
                queue.pop(idx)
                return

    def _turnover_total_h(self) -> Fraction:
        if self.config.turnover_profile == "0.5h_overlap":
            return self.config.transport_out_h  # out/in fully overlap -> 0.5h total
        return self.config.transport_out_h + self.config.transport_in_h

    def _finish_turnover_in(self, bay: sm.BayState, t: Fraction) -> None:
        device_id = self._next_device_to_create()
        if device_id > self.config.batch_size:  # pragma: no cover - defensive
            raise DesError("turnover_in without a next device")
        bay.status = sm.BayStatus.OCCUPIED_TESTING
        bay.transport_phase = "none"
        self._create_device(device_id, t, bay.bay_id)
        self._pending_creations.append(device_id)

    def _is_legal(self, entry: sm.QueueEntry) -> bool:
        task = self.tasks[entry.task_id]
        device = self.devices[task.device_id]
        if device.terminal_state != sm.TerminalState.PENDING:
            return False
        bay = self.bays[device.bay_id]
        if bay.status != sm.BayStatus.OCCUPIED_TESTING:
            return False
        if task.process == "E":
            for proc in ("A", "B", "C"):
                if device.process_state[proc].process_status != sm.ProcessStatus.PASSED:
                    return False
        shift = self.shift_state.active_shift
        if shift is None:
            return False  # outside any shift (gap): nothing starts
        if self.now + self.config.durations[task.process] > shift.shift_end:
            return False  # SEM-20: would cross the shift boundary
        return True  # SEM-19: start+duration == shift_end is legal

    def _start_task(self, head: sm.QueueEntry) -> sm.TestAttemptState:
        task = self.tasks[head.task_id]
        device = self.devices[task.device_id]
        shift = self.shift_state.active_shift
        squad = shift.on_duty_squad if shift is not None else None
        attempt_id = (
            f"A{task.device_id:03d}_{task.process}_{task.effective_attempt_no}_1"
        )
        attempt = sm.TestAttemptState(
            attempt_id=attempt_id,
            task_id=task.task_id,
            device_id=task.device_id,
            process=task.process,
            effective_attempt_no=task.effective_attempt_no,
            execution_no=1,
            status=sm.AttemptStatus.RUNNING,
            start_time=self.now,
            result_squad_id=squad,
        )
        self.attempts[attempt_id] = attempt
        task.status = sm.TaskStatus.RUNNING
        self.devices[task.device_id].process_state[task.process].process_status = (
            sm.ProcessStatus.IN_PROGRESS
        )
        resource = self.resources[task.resource_id]
        resource.status = sm.ResourceStatus.BUSY
        resource.current_activity = {
            "task_id": task.task_id,
            "device_id": task.device_id,
            "process": task.process,
            "attempt_no": task.effective_attempt_no,
            "start_time": self.now,
            "end_time": self.now + self.config.durations[task.process],
        }
        head.status = sm.QueueEntryStatus.DISPATCHED
        self.queues[task.resource_id].pop(0)
        end = self.now + self.config.durations[task.process]
        self._schedule("test_complete", end, attempt_id)
        return attempt

    def _start_payload(self, attempt: sm.TestAttemptState) -> dict[str, Any]:
        task = self.tasks[attempt.task_id]
        device = self.devices[attempt.device_id]
        return {
            "device_id": attempt.device_id,
            "process": attempt.process,
            "effective_attempt_no": attempt.effective_attempt_no,
            "resource_id": task.resource_id,
            "bay_id": device.bay_id,
            "squad_id": attempt.result_squad_id,
            "task_id": task.task_id,
            "attempt_start_time": attempt.start_time,
            "attempt_end_time": attempt.start_time + self.config.durations[task.process],
            "outcome": sm.Outcome.NONE.value,
            "release_time": task.release_time,
        }

    # -- metrics / summary --------------------------------------------------

    def _generated_problems(self, device: sm.DeviceState) -> list[str]:
        """Generated real problems among A/B/C and D (D only if created)."""
        problems: list[str] = []
        for proc in ("A", "B", "C"):
            if self.scripted.real_state(device.device_id, proc) == "problem":
                problems.append(proc)
        if device.d_state == sm.DState.PROBLEM:
            problems.append("D")
        return problems

    def _metrics(self) -> dict[str, Any]:
        t = self.now
        passed = [d for d in self.devices.values() if d.terminal_state == sm.TerminalState.PASSED]
        exited = [d for d in self.devices.values() if d.terminal_state == sm.TerminalState.EXITED]
        s = len(passed)
        pl = sum(1 for d in passed if self._generated_problems(d))
        pw = sum(1 for d in exited if not self._generated_problems(d))
        shift_count = 0
        index = 0
        while True:
            start = self._shift_start(index)
            if start is None:
                break
            if start < t:
                shift_count += 1
                index += 1
                continue
            break
        denominator = Fraction(shift_count) * self.config.shift_length_h
        yxb = {
            proc: (self.ledger_elapsed[proc] / denominator)
            for proc in RESOURCES
        }
        return {
            "T": sm.fraction_to_string(t),
            "S": s,
            "PL": pl,
            "PW": pw,
            "YXB_A": sm.fraction_to_string(yxb["A"]),
            "YXB_B": sm.fraction_to_string(yxb["B"]),
            "YXB_C": sm.fraction_to_string(yxb["C"]),
            "YXB_E": sm.fraction_to_string(yxb["E"]),
            "shift_count": shift_count,
            "yxb_denominator_h": sm.fraction_to_string(denominator),
        }

    def _summary(self) -> dict[str, Any]:
        devices: dict[str, Any] = {}
        for device_id in sorted(self.devices):
            device = self.devices[device_id]
            first_failure_times: dict[str, Any] = {}
            for proc in RESOURCES:
                fft = device.process_state[proc].first_failure_time
                first_failure_times[proc] = (
                    sm.fraction_to_string(fft) if fft is not None else None
                )
            devices[str(device_id)] = {
                "entry_time": sm.fraction_to_string(device.entry_time),
                "bay_id": device.bay_id,
                "terminal_state": device.terminal_state.value,
                "exit_reason": device.exit_reason,
                "d_state": device.d_state.value,
                "process_status": {
                    proc: device.process_state[proc].process_status.value
                    for proc in RESOURCES
                },
                "first_failure_time": first_failure_times,
            }
        return {
            "devices": devices,
            "bays": {
                str(bay_id): {
                    "status": bay.status.value,
                    "current_device_id": bay.current_device_id,
                    "transport_phase": bay.transport_phase,
                    "turnover_pending": bay.turnover_pending,
                }
                for bay_id, bay in sorted(self.bays.items())
            },
            "ledger_elapsed_h": {
                proc: sm.fraction_to_string(self.ledger_elapsed[proc]) for proc in RESOURCES
            },
        }


def run_des(config_raw: dict[str, Any], scripted_raw: dict[str, Any]) -> DesRunResult:
    """Run the deterministic DES once. Deterministic: the same config+fixture
    always yields a byte-identical event_log (verified by tests)."""
    config = DesConfig.from_dict(config_raw)
    scripted = ScriptedFixture.from_dict(scripted_raw)
    engine = DeterministicDesEngine(config, scripted)
    return engine.run()


def _parse_positive(value: Any, name: str) -> Fraction:
    if not isinstance(value, str):
        raise DesConfigError(f"config.{name} must be a rational string")
    try:
        fraction = sm.string_to_fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise DesConfigError(f"config.{name} is not a valid rational: {value!r}") from exc
    if fraction <= 0:
        raise DesConfigError(f"config.{name} must be positive")
    return fraction


def _parse_nonnegative(value: Any, name: str) -> Fraction:
    if not isinstance(value, str):
        raise DesConfigError(f"config.{name} must be a rational string")
    try:
        fraction = sm.string_to_fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise DesConfigError(f"config.{name} is not a valid rational: {value!r}") from exc
    if fraction < 0:
        raise DesConfigError(f"config.{name} must be non-negative")
    return fraction
