#!/usr/bin/env python3
"""Q3-H2-P3-B continuation rollout event engine (fresh implementation).

Authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED sections
1/6/7/8/9/10/11/12/13 (frozen).  P3-B authorization (starting HEAD
fcf07f6): full continuation rollout execution kernel; first-action-then-H1
Q_hat_M; NO re-design of the frozen rules.

DESIGN (C23 / P1 hard constraints):
  * FRESH engine, entirely inside ``main_model/h2`` -- it imports NOTHING
    from the live DES engine (``g3`` / ``des``); all random consumption goes
    through the injected post-key provider (the external adapter in
    ``main_model/h2_rollout`` derives h2_rollout-domain post keys);
  * the hidden world is rebuilt ONLY from ObservableState + PosteriorState +
    ContinuationWorld + post keys; it NEVER deepcopies the live DES world,
    NEVER reads live true_state / live lifetime / future raw log / live
    u_key;
  * future observations consume U_Y_post ONLY on a valid completion
    (NO_OBSERVATION_CONSUMED_BY semantics: never-started / shift-deferred /
    interrupted / cancelled / failure-interrupted / terminal-cancelled
    fragments consume nothing);
  * D materialization: a not-yet-reached-E device draws U_D_post once at the
    legal junction (A/B/C all PASSED, E not yet released), prior q_D; never
    counterfactually before exit; never twice;
  * equipment lifetime: current generation uses the P2 conditional-residual
    lifetime from ContinuationWorld; the engine's INTERNAL coordinate for
    ``equipment.lifetime_h`` is the ABSOLUTE equipment age of natural
    failure (P3-B-E1 F1): a current-generation draw (tau, right_censored)
    with right_censored=False is converted to lifetime_h = current_age +
    tau; right_censored=True -> lifetime_h = 240 (survive to 240, no
    natural failure before the mandatory boundary).  Every new generation
    after a replacement binds a NEW U_L_post(resource, new_generation) and
    is sampled from the P2/G3 UNCONDITIONAL inverse sampler (age=0 ->
    absolute failure age from generation birth; never add age again); the
    P2 validation synthetic generation mapping is never used;
  * mandatory / exact_240 semantics are carried verbatim from the frozen
    engine contract (a+d>240 force-replace first; a+d==240 complete-first
    then replace; age==240 post-completion mandatory; random failure at
    lifetime).

FIRST-ACTION-THEN-H1 (frozen Q_hat_M semantics): one candidate first action
is applied at the decision point; after it completes / is invalidated the
engine falls back to the accepted H1 baseline policy
NO_PM_BEFORE_MANDATORY and simulates to batch absorption; T_end is the
absorption instant; absorption-tail value is 0 (no truncation, no finite
horizon, no second H2 call).

The engine mirrors the accepted H1 engine's same-timestamp closure order:
settle -> observe -> classify -> exits -> cancel unfinished -> materialize
D -> shift change -> release tasks -> equipment+dispatch -> turnovers, and
the frozen FCFS minimal-key dispatch.

Python 3.12, standard library only.
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Optional

from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from main_model.h2 import continuation_v1 as cont  # noqa: E402
from main_model.h2.frozen_params_v1 import (  # noqa: E402
    CALIBRATION_MINUTES, DURATIONS_H, MANDATORY_AGE_H, Q_ABC, Q_D,
    RESOURCES, observation_kernel,
)
from main_model.h2.lifetime_generator_v1 import inverse_cdf  # noqa: E402

NO_PM_BEFORE_MANDATORY: str = "NO_PM_BEFORE_MANDATORY"

# fail-closed runaway guard: legitimate 100-device batches settle in a few
# thousand closures; this is a huge headroom (see RolloutEngine.run).
MAX_CLOSURES: int = 1_000_000

# action names (frozen, imported for interface consistency)
A_START_HEAD = "START_HEAD"
A_H1_NOOP = "H1_NOOP"
A_WAIT_EVENT = "WAIT_EVENT"
A_PM_WITH_HEAD = "PM_WITH_HEAD"
A_PM_IDLE = "PM_IDLE"

_PROCESS_ORDER = {"A": 0, "B": 1, "C": 2, "E": 3}


# ---------------------------------------------------------------------------
# minimal frozen engine state models (local, no des import)
# ---------------------------------------------------------------------------


@dataclass
class _Task:
    task_id: str
    resource_id: str
    device_id: int
    process: str
    effective_attempt_no: int
    release_time: Fraction
    status: str = "READY"  # READY | RUNNING | COMPLETED | CANCELLED


@dataclass
class _QueueEntry:
    queue_id: str
    task_id: str
    fcfs_key: tuple  # (release_time, device_id, process_order, attempt)
    status: str = "WAITING"  # WAITING | DISPATCHED | REMOVED


@dataclass
class _Attempt:
    attempt_id: str
    task_id: str
    device_id: int
    process: str
    effective_attempt_no: int
    start_time: Fraction
    end_time: Optional[Fraction] = None
    status: str = "RUNNING"  # RUNNING | COMPLETED | CANCELLED
    outcome: Optional[str] = None
    result_squad_id: Optional[int] = None


@dataclass
class _ProcessState:
    process: str
    status: str = "PENDING"  # PENDING | IN_PROGRESS | AWAITING_RETEST | PASSED
    first_failure_time: Optional[Fraction] = None


@dataclass
class _Device:
    device_id: int
    entry_time: Fraction
    bay_id: int
    terminal_state: str = "PENDING"  # PENDING | PASSED | EXITED
    terminal_reason: Optional[str] = None
    d_state: str = "NOT_CREATED"  # NOT_CREATED | NORMAL | PROBLEM
    x_abc: tuple[int, int, int] = (0, 0, 0)   # sampled hidden truth
    x_d: Optional[int] = None                  # None until materialized
    process_state: dict[str, _ProcessState] = field(default_factory=dict)


@dataclass
class _Equipment:
    resource_id: str
    age: Fraction = Fraction(0)
    generation: int = 1
    available: bool = True
    lifetime_h: Optional[Fraction] = None
    is_right_censored: bool = False
    replacement_pending: bool = False
    pending_kind: Optional[str] = None
    pending_trigger: Optional[str] = None
    deferral_emitted: bool = False
    calibration_in_flight: bool = False
    calibration_start: Optional[Fraction] = None
    calibration_end: Optional[Fraction] = None
    replacement_count: int = 0
    preventive_count: int = 0


@dataclass
class _Resource:
    resource_id: str
    status: str = "IDLE"  # IDLE | BUSY
    current_activity: Optional[dict[str, Any]] = None


@dataclass
class _Bay:
    bay_id: int
    status: str = "EMPTY"  # EMPTY | OCCUPIED_TESTING | OCCUPIED_TRANSPORT_OUT
    current_device_id: Optional[int] = None
    turnover_pending: bool = False
    transport_phase: str = "none"


@dataclass
class PostKeyProvider:
    """Injected post-key provider (h2_rollout domain, external adapter).
    Every call returns the SAME value for the same canonical slot (CRN)."""
    u_x_by_device: dict[int, Fraction] = field(default_factory=dict)
    u_d_by_device: dict[int, Fraction] = field(default_factory=dict)
    u_l_by_resource: dict[str, Fraction] = field(default_factory=dict)
    u_y_lookup: Optional[Callable[[int, str, int], Fraction]] = None
    u_l_lookup: Optional[Callable[[str, int], Fraction]] = None  # (resource, gen)
    u_x_subsystem_lookup: Optional[Callable[[int, str], Fraction]] = None

    def u_y(self, device: int, process: str, attempt: int) -> Fraction:
        if self.u_y_lookup is None:
            raise ValueError("U_Y_post provider not bound")
        return self.u_y_lookup(device, process, attempt)

    def u_l(self, resource: str, generation: int) -> Fraction:
        if self.u_l_lookup is not None:
            return self.u_l_lookup(resource, generation)
        if generation == 1:
            try:
                return self.u_l_by_resource[resource]
            except KeyError:
                raise ValueError(f"missing U_L_post for {resource} gen 1") from None
        raise ValueError(
            f"U_L_post for generation {generation} of {resource} requires "
            f"u_l_lookup (new-generation provider)")

    def u_x(self, device: int) -> Fraction:
        try:
            return self.u_x_by_device[device]
        except KeyError:
            raise ValueError(
                f"missing per-device U_X_post for device {device} "
                f"(fail-close)") from None

    def u_x_subsystem(self, device: int, subsystem: str) -> Fraction:
        """Per-subsystem U_X_post for not-yet-entered-device prior draws
        (SPEC 8: 未进入装置按各先验采样; canonical slot = subsystem)."""
        if self.u_x_subsystem_lookup is not None:
            return self.u_x_subsystem_lookup(device, subsystem)
        # fall back to the single categorical draw (interface compatibility;
        # the production adapter always binds the subsystem lookup)
        return self.u_x(device)

    def u_d(self, device: int) -> Fraction:
        try:
            return self.u_d_by_device[device]
        except KeyError:
            raise ValueError(
                f"missing per-device U_D_post for device {device} "
                f"(fail-close)") from None


@dataclass
class RolloutConfig:
    """Frozen continuation config (subset of the engine config)."""
    batch_size: int
    shift_length_h: Fraction
    shifts_per_day: int = 2
    scenario: str = "q3_two_shift"
    tau_pm: Any = NO_PM_BEFORE_MANDATORY
    turnover_profile: str = "1h_literal"
    transport_out_h: Fraction = Fraction(1, 2)
    transport_in_h: Fraction = Fraction(1, 2)


@dataclass
class RolloutResult:
    """One world's continuation result (Q_hat input)."""
    t_end: Fraction
    events: tuple[dict[str, Any], ...]
    consumed_u_y: int
    consumed_u_d: int
    consumed_u_l: int
    replacements: int
    devices_passed: int
    devices_exited: int

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "t_end": str(self.t_end),
            "n_events": len(self.events),
            "consumed_u_y": self.consumed_u_y,
            "consumed_u_d": self.consumed_u_d,
            "consumed_u_l": self.consumed_u_l,
            "replacements": self.replacements,
            "devices_passed": self.devices_passed,
            "devices_exited": self.devices_exited,
        }


# ---------------------------------------------------------------------------
# continuation engine
# ---------------------------------------------------------------------------


def _fragment_settled_local(pre: list[dict[str, Any]], device: int,
                            process: str, attempt: int,
                            fstart: Fraction) -> bool:
    """Fragment-aware settle for the log-prefix reconstruction (F1
    principle): only a COMPLETE/CANCEL with the SAME exact identity
    settles this fragment."""
    for r in pre:
        if r.get("event_type") not in ("ACTIVITY_COMPLETE", "TASK_CANCEL"):
            continue
        if r.get("attempt_start_time") is None:
            continue
        if (r.get("device_id") == device and r.get("process") == process
                and r.get("effective_attempt_no") == attempt
                and Fraction(r["attempt_start_time"]) == fstart):
            return True
    return False


def _fragment_outcome(a_start, d, lifetime_h, is_right_censored
                      ) -> tuple[str, Fraction]:
    """Frozen fragment classification (mirrors the accepted engine's
    fragment_outcome): ILLEGAL_240 backstop first; then random failure
    strictly before the end; a failure exactly at the end settles as a
    completion; otherwise complete.  Returns (kind, fragment_duration)."""
    a = Fraction(a_start)
    d = Fraction(d)
    if a + d > MANDATORY_AGE_H:
        return ("illegal_240", MANDATORY_AGE_H - a)
    interrupted = False
    if not is_right_censored and lifetime_h is not None:
        L = Fraction(lifetime_h)
        if L <= a:
            raise ValueError(
                f"inconsistent lifetime L={L} <= start age a={a} "
                f"(device should already be replaced)")
        if a < L < a + d:
            interrupted = True
    if interrupted:
        return ("failed", Fraction(lifetime_h) - a)
    return ("complete", d)


def _replacement_decision(a, d, tau_pm, is_idle_decision_point) -> str:
    """Frozen C26 A-H decision: MANDATORY_REPLACE_FIRST / EXACT_240 /
    SERVE_HEAD / PREVENTIVE_REPLACE (NO_PM => preventive never triggers).

    P3-B-E1 (string semantics): the NO_PM sentinel is compared by VALUE
    (== on the frozen literal string), never by Python object identity
    (``is``), so a dynamically constructed equal string cannot fall into
    the Fraction(tau_pm) numeric path."""
    a = Fraction(a)
    d = Fraction(d)
    if a + d > MANDATORY_AGE_H:
        return "MANDATORY_REPLACE_FIRST"
    if a + d == MANDATORY_AGE_H:
        return "EXACT_240_COMPLETE_FIRST"
    no_pm = (str(tau_pm) == str(NO_PM_BEFORE_MANDATORY))
    if no_pm:
        return "SERVE_HEAD"
    if a >= Fraction(tau_pm) and is_idle_decision_point:
        return "PREVENTIVE_REPLACE"
    return "SERVE_HEAD"


def make_fcfs_key(release_time, device_id, process, attempt) -> tuple:
    return (Fraction(release_time), int(device_id),
            _PROCESS_ORDER[process], int(attempt))


class RolloutEngine:
    """Fresh continuation event engine (no live-DES imports).

    Start state is rebuilt from the safe projections; the first candidate
    action is applied at the decision point; afterwards the engine follows
    the H1 baseline NO_PM_BEFORE_MANDATORY until batch absorption.
    """

    def __init__(self, state: obs.ObservableState,
                 posterior: ps.PosteriorState,
                 world: cont.ContinuationWorld,
                 provider: PostKeyProvider,
                 config: RolloutConfig,
                 first_action: str = A_H1_NOOP,
                 wait_anchor_time: Optional[Fraction] = None,
                 pm_resource: Optional[str] = None,
                 log_prefix: Optional[list[dict[str, Any]]] = None,
                 decision_resource: Optional[str] = None,
                 decision_head: Optional[tuple[int, str, int]] = None,
                 decision_kind: Optional[str] = None) -> None:
        self.config = config
        self.provider = provider
        self.now: Fraction = state.time
        self._seq: int = 0
        self.log: list[dict[str, Any]] = []
        self._calendar: list[tuple[Fraction, int, str, Any]] = []
        self._cal_seq: int = 0
        self._cancelled_attempts: set[str] = set()
        self.devices: dict[int, _Device] = {}
        self.tasks: dict[str, _Task] = {}
        self.attempts: dict[str, _Attempt] = {}
        self.queues: dict[str, list[_QueueEntry]] = {r: [] for r in RESOURCES}
        self.resources: dict[str, _Resource] = {
            r: _Resource(r) for r in RESOURCES}
        self.equipment: dict[str, _Equipment] = {
            r: _Equipment(r) for r in RESOURCES}
        self.bays: dict[int, _Bay] = {}
        self.kernel = observation_kernel()
        self._pending_retests: dict[tuple[int, str], Fraction] = {}
        self._pending_creations: list[int] = []
        self._created_count: int = 0
        self._fragment_counter: dict[str, int] = {}
        self.consumed_u_y = 0
        self.consumed_u_d = 0
        self.consumed_u_l = 0
        self.first_action = first_action
        self.wait_anchor_time = wait_anchor_time
        self.pm_resource = pm_resource
        self._first_action_done = False
        # decision point context (frozen decision boundary facts, REQUALIFIED)
        self.decision_resource: Optional[str] = decision_resource
        self.decision_head: Optional[tuple[int, str, int]] = decision_head
        self.decision_kind: Optional[str] = decision_kind
        # strategic-wait holds: resource -> anchor time (WAIT_EVENT first
        # action); the resource's head is not dispatched before the anchor.
        self.wait_holds: dict[str, Fraction] = {}
        self._log_prefix = list(log_prefix) if log_prefix is not None else None
        self._init_from_projections(state, posterior, world)

    # -- rebuild from the safe projections -------------------------------

    def _init_from_projections(self, state: obs.ObservableState,
                               posterior: ps.PosteriorState,
                               world: cont.ContinuationWorld) -> None:
        # bays: reconstruct from ObservableState; ALWAYS ensure the two
        # physical bays exist (the accepted engine's init creates bays 1,2;
        # the projection may not yet have D_CREATED/TURNOVER records at t=0)
        for b in state.bays:
            self.bays[b.bay_id] = _Bay(
                bay_id=b.bay_id,
                status=("OCCUPIED_TESTING" if b.current_device is not None
                        else b.status.upper() if b.status else "EMPTY"),
                current_device_id=b.current_device,
            )
        if not self.bays:
            self.bays[1] = _Bay(bay_id=1, status="OCCUPIED_TESTING",
                                current_device_id=None)
            self.bays[2] = _Bay(bay_id=2, status="OCCUPIED_TESTING",
                                current_device_id=None)
        # devices: sampled hidden truth from the continuation world
        post_devs = {d.device_id: d for d in posterior.devices}
        entered_ids = sorted(d.device_id for d in state.devices)
        bay_of = {}
        for b in state.bays:
            if b.current_device is not None:
                bay_of[b.current_device] = b.bay_id
        for idx, dev_id in enumerate(entered_ids):
            if dev_id not in bay_of:
                bay_of[dev_id] = (idx % 2) + 1  # preload: dev1->bay1, dev2->bay2
        for dev in state.devices:
            pv = post_devs.get(dev.device_id)
            cw = next((c for c in world.devices
                       if c.device_id == dev.device_id), None)
            d_state = "NOT_CREATED"
            if cw is not None and cw.x_d is not None:
                d_state = "PROBLEM" if cw.x_d == 1 else "NORMAL"
            terminal = "PENDING"
            if dev.terminal_state is not None:
                terminal = ("PASSED" if "PASS" in str(dev.terminal_state)
                            else "EXITED")
            device = _Device(
                device_id=dev.device_id,
                entry_time=dev.entry_time if hasattr(dev, "entry_time")
                else state.time,
                bay_id=bay_of.get(dev.device_id, 1),
                terminal_state=terminal,
                x_abc=(0, 0, 0) if cw is None else cw.x_abc,
                x_d=None if cw is None else cw.x_d,
                d_state=d_state,
                process_state={p: _ProcessState(p) for p in RESOURCES},
            )
            self.devices[dev.device_id] = device
            self._created_count = max(self._created_count, dev.device_id)
            if dev.terminal_state is None:
                self._pending_creations.append(dev.device_id)
        # bind preloaded devices to their bays (current_device_id)
        for dev in self.devices.values():
            bay = self.bays.get(dev.bay_id)
            if bay is not None and bay.current_device_id is None:
                bay.current_device_id = dev.device_id
                bay.status = "OCCUPIED_TESTING"
        # process status from the observable device history
        for dev in self.devices.values():
            obs_hist = next((d.observations for d in state.devices
                             if d.device_id == dev.device_id), ())
            for o in obs_hist:
                p = dev.process_state.get(o.process)
                if p is None:
                    continue
                if o.outcome == "PASS":
                    p.status = "PASSED"
                elif p.status != "PASSED":
                    p.status = ("AWAITING_RETEST"
                                if o.attempt == 1
                                else "IN_PROGRESS")
        # resources / equipment from ObservableState (age from age_h)
        for r in state.resources:
            equip = self.equipment[r.resource]
            equip.age = r.age_h
            equip.generation = r.generation
            if r.status == "calibration":
                equip.calibration_in_flight = True
                equip.available = False
                self.resources[r.resource].status = "BUSY"
                cal_end = state.time + r.in_flight_remaining_h
                self.resources[r.resource].current_activity = {
                    "kind": "calibration", "resource_id": r.resource,
                    "start_time": state.time,
                    "end_time": cal_end}
                # FIX (P3-C): a rebuild must also schedule the completion
                # of the in-flight calibration, exactly like
                # _begin_replacement does -- otherwise the resource is
                # stuck in calibration forever, its queue backs up, the
                # calendar empties, _is_terminal() never turns True and
                # run() advances over shift boundaries recording WAKE_UP
                # indefinitely (runaway now/log -> MemoryError).
                self._schedule("calibration_complete", cal_end,
                               r.resource)
            elif r.status == "testing":
                self.resources[r.resource].status = "BUSY"
                self.resources[r.resource].current_activity = {
                    "kind": "test", "resource_id": r.resource,
                    "start_time": state.time,
                    "end_time": state.time + r.in_flight_remaining_h}
            elif r.status == "replacement" or r.status == "failed":
                equip.replacement_pending = True
                equip.available = False
            # conditional-residual lifetime from the continuation world.
            # P2 returns (tau, right_censored) with tau = RESIDUAL lifetime
            # from the current age.  The engine's internal coordinate is the
            # ABSOLUTE equipment age of natural failure (F1, P3-B-E1):
            #   * natural branch (right_censored=False):
            #       lifetime_h = current_age + tau   (absolute failure age)
            #   * right-censored branch (survive to 240):
            #       lifetime_h = 240, is_right_censored = True
            #         (no natural failure inside [0, 240]; the mandatory-240
            #          rule handles the boundary).
            # P2 API stays accepted (never modified).
            rl = world.residual_lifetimes.get(r.resource)
            if rl is not None:
                tau, cens = rl
                if cens:
                    equip.lifetime_h = MANDATORY_AGE_H
                    equip.is_right_censored = True
                else:
                    if tau is None:
                        raise ValueError(
                            f"natural-branch conditional residual for "
                            f"{r.resource} must not be None")
                    equip.lifetime_h = r.age_h + tau
                    equip.is_right_censored = False
            elif not equip.is_right_censored:
                # no lifetime yet (calibration in flight): draw later at the
                # first dispatch via the generation provider
                pass
        # queue entries from ObservableState (frozen FCFS keys); use the
        # CANONICAL task id so _release_task's duplicate guard works
        for q in state.queue:
            tid = self._task_id(q.device_id,
                                _PROCESS_ORDER_REV[q.process_order],
                                q.effective_attempt_no)
            task = _Task(
                task_id=tid, resource_id=_PROCESS_ORDER_REV[q.process_order],
                device_id=q.device_id, process=_PROCESS_ORDER_REV[q.process_order],
                effective_attempt_no=q.effective_attempt_no,
                release_time=q.release_time)
            self.tasks[tid] = task
            self.queues[task.resource_id].append(_QueueEntry(
                queue_id=task.resource_id, task_id=tid,
                fcfs_key=make_fcfs_key(q.release_time, q.device_id,
                                       _PROCESS_ORDER_REV[q.process_order],
                                       q.effective_attempt_no)))
        # in-flight activities from the observable log prefix (fragment-
        # aware: an ACTIVITY_START with start <= t < end and no matching
        # settle in the prefix is the in-flight attempt identity)
        if self._log_prefix is not None:
            pre = [r for r in self._log_prefix
                   if r.get("event_time") is not None
                   and Fraction(r["event_time"]) <= state.time]
            for r in pre:
                if r.get("event_type") != "ACTIVITY_START":
                    continue
                s = Fraction(r.get("attempt_start_time", r["event_time"]))
                end = Fraction(r["attempt_end_time"])
                if not (s <= state.time < end):
                    continue
                if _fragment_settled_local(pre, r["device_id"],
                                           r["process"],
                                           r["effective_attempt_no"], s):
                    continue
                dev_id = r["device_id"]
                proc = r["process"]
                att = r["effective_attempt_no"]
                rsrc = r.get("resource_id", proc)
                tid = self._task_id(dev_id, proc, att)
                task = _Task(task_id=tid, resource_id=rsrc,
                             device_id=dev_id, process=proc,
                             effective_attempt_no=att, release_time=s,
                             status="RUNNING")
                self.tasks[tid] = task
                self._fragment_counter[tid] = 0
                execution_no = self._fragment_counter[tid] + 1
                self._fragment_counter[tid] = execution_no
                attempt_id = (f"A{dev_id:03d}_{proc}_{att}_{execution_no}")
                attempt = _Attempt(
                    attempt_id=attempt_id, task_id=tid, device_id=dev_id,
                    process=proc, effective_attempt_no=att,
                    start_time=s, result_squad_id=None)
                self.attempts[attempt_id] = attempt
                self.resources[rsrc].status = "BUSY"
                self.resources[rsrc].current_activity = {
                    "kind": "test", "task_id": tid, "attempt_id": attempt_id,
                    "device_id": dev_id, "process": proc,
                    "attempt_no": att, "start_time": s, "end_time": end}
                self._schedule("test_complete", end, attempt_id)
                # process status: the head is in-flight -> IN_PROGRESS
                dev = self.devices.get(dev_id)
                if dev is not None:
                    ps_ = dev.process_state.get(proc)
                    if ps_ is not None:
                        ps_.status = "IN_PROGRESS"
        # remaining_not_entered devices will be created by turnovers
        self._remaining_to_create = state.remaining_not_entered
        # seed the engine log with the observable prefix records (so the
        # H2 driver's per-closure decision reconstruction sees the full
        # observable history including entered devices / releases / etc.)
        if self._log_prefix is not None:
            for r in self._log_prefix:
                if (r.get("event_time") is not None
                        and Fraction(r["event_time"]) <= state.time):
                    rec = dict(r)
                    rec.setdefault("seq", 0)
                    self._seq = max(self._seq, rec["seq"])
                    self.log.append(rec)
        self._apply_first_action_if_dispatch()

    # -- event machinery --------------------------------------------------

    def _record(self, event_type: str, **fields: Any) -> dict[str, Any]:
        self._seq += 1
        rec: dict[str, Any] = {
            "seq": self._seq, "event_time": str(self.now),
            "event_type": event_type}
        for name, value in fields.items():
            if value is None:
                continue
            rec[name] = value if not isinstance(value, Fraction) else str(value)
        self.log.append(rec)
        return rec

    def _schedule(self, kind: str, time: Fraction, token: Any) -> None:
        self._cal_seq += 1
        heapq.heappush(self._calendar, (time, self._cal_seq, kind, token))

    def _calendar_min(self) -> Optional[Fraction]:
        return self._calendar[0][0] if self._calendar else None

    def _next_shift_boundary_after(self, t: Fraction) -> Optional[Fraction]:
        if self.config.scenario == "q3_two_shift":
            # day d: shift1 [24d, 24d+K), shift2 [24d+K, 24d+2K)
            K = self.config.shift_length_h
            day = t // Fraction(24)
            s1 = day * Fraction(24)
            for cand in (s1, s1 + K, s1 + 2 * K):
                if cand > t:
                    return cand
            return (day + 1) * Fraction(24)
        return None

    def _active_shift(self, t: Fraction
                      ) -> Optional[tuple[Fraction, Fraction]]:
        if self.config.scenario != "q3_two_shift":
            return (Fraction(0), Fraction(10 ** 9))
        K = self.config.shift_length_h
        day = t // Fraction(24)
        s1 = day * Fraction(24)
        shifts = ((s1, s1 + K), (s1 + K, s1 + 2 * K))
        for s, e in shifts:
            if s <= t < e:
                return (s, e)
        return None

    def _is_terminal(self) -> bool:
        if any(d.terminal_state == "PENDING" for d in self.devices.values()):
            return False
        if any(b.turnover_pending for b in self.bays.values()):
            return False
        if any(b.status in ("OCCUPIED_TRANSPORT_OUT",
                            "OCCUPIED_TRANSPORT_IN")
               for b in self.bays.values()):
            return False
        return True

    # -- first action (frozen Q_hat semantics, REQUALIFIED) ------------------

    def _apply_first_action_if_dispatch(self) -> None:
        """Apply the candidate first action at the decision boundary.  Only
        the FIRST step is influenced; afterwards the H1 baseline governs.

        REQUALIFICATION (decision semantics): the candidate action must
        really take effect on the FROZEN decision context:
          * START_HEAD  starts the frozen FCFS head identity at t (fail
                        closed when the frozen head is missing / no longer
                        the queue head / not legal);
          * WAIT_EVENT  holds the decision resource's head until the frozen
                        WaitAnchor (no H1 dispatch in [t, anchor));
          * PM_WITH_HEAD / PM_IDLE begin a preventive replacement of the
            decision resource; H1_NOOP does nothing.
        Any candidate action that needs decision context but does not have
        it FAILS CLOSED (never a silent no-op)."""
        if self._first_action_done:
            return
        a = self.first_action
        if a == A_H1_NOOP:
            self._first_action_done = True
            return
        if a == A_START_HEAD:
            if self.decision_resource is None or self.decision_head is None:
                raise ValueError(
                    "START_HEAD requires decision_resource and decision_head "
                    "(fail-closed; no silent default dispatch)")
            self._start_frozen_head()
            self._first_action_done = True
            return
        if a == A_WAIT_EVENT:
            if self.decision_resource is None:
                raise ValueError(
                    "WAIT_EVENT requires decision_resource (fail-closed)")
            if self.wait_anchor_time is None:
                raise ValueError(
                    "WAIT_EVENT requires a wait anchor (fail-closed)")
            # strategic wait hold: the decision resource's head must NOT be
            # dispatched by the H1 closure in [t, anchor).
            self.wait_holds[self.decision_resource] = self.wait_anchor_time
            if self.wait_anchor_time > self.now:
                self._schedule("h2_wait_wake", self.wait_anchor_time,
                               ("wait", self.decision_resource))
            self._first_action_done = True
            return
        if a in (A_PM_WITH_HEAD, A_PM_IDLE):
            r = self.pm_resource if self.pm_resource is not None \
                else self.decision_resource
            if r is None:
                raise ValueError(
                    f"{a} requires pm_resource/decision_resource "
                    "(fail-closed)")
            self._set_replacement_pending(r, "preventive", "h2_pm")
            self._begin_replacement(r)
            self._first_action_done = True
            return
        raise ValueError(f"unknown first action {a!r}")

    def _start_frozen_head(self) -> None:
        """START_HEAD: immediately start the FROZEN FCFS head identity of the
        decision resource at the decision boundary t (ACTIVITY_START at t);
        then H1 baseline continuation.  Fail closed if the frozen head cannot
        be found, is not the queue head, or is no longer legal."""
        r = self.decision_resource
        frozen = self.decision_head
        queue = self.queues[r]
        queue.sort(key=lambda e: e.fcfs_key)
        if not queue:
            raise ValueError(
                f"START_HEAD: decision queue of {r} is empty (fail-closed)")
        head_entry = queue[0]
        task = self.tasks[head_entry.task_id]
        actual = (task.device_id, task.process, task.effective_attempt_no)
        if actual != frozen:
            raise ValueError(
                f"START_HEAD: frozen head {frozen} != actual queue head "
                f"{actual} (fail-closed; never silently start another task)")
        if not self._is_legal(head_entry):
            raise ValueError(
                f"START_HEAD: frozen head {frozen} is no longer legal at "
                f"t={self.now} (fail-closed)")
        attempt = self._start_task(head_entry)
        self._record_activity_start(attempt)

    def _record_activity_start(self, attempt: _Attempt) -> None:
        act = self.resources[attempt.task_id and
                             self.tasks[attempt.task_id].resource_id] \
            .current_activity
        scheduled_end = (act.get("end_time") if act is not None else None)
        end_rec = (attempt.end_time if attempt.end_time is not None
                   else scheduled_end)
        self._record("ACTIVITY_START", device_id=attempt.device_id,
                     process=attempt.process,
                     effective_attempt_no=attempt.effective_attempt_no,
                     resource_id=self.tasks[attempt.task_id].resource_id,
                     attempt_start_time=attempt.start_time,
                     attempt_end_time=end_rec,
                     outcome="NONE")

    def _dispatch_decision_resource(self, force: bool = False) -> None:
        r = self.decision_resource
        if r is None:
            return
        equip = self.equipment[r]
        res = self.resources[r]
        if res.status != "IDLE" or not equip.available:
            return
        q = self.queues[r]
        if not q:
            return
        q.sort(key=lambda e: e.fcfs_key)
        head = q[0]
        if head.status != "WAITING":
            return
        shift = self._active_shift(self.now)
        if shift is None:
            return
        task = self.tasks[head.task_id]
        if not self._is_legal(head):
            return
        decision = _replacement_decision(
            equip.age, self.config.shift_length_h and DURATIONS_H[task.process],
            self.config.tau_pm, True)
        if decision == "MANDATORY_REPLACE_FIRST":
            self._set_replacement_pending(
                r, "mandatory_240", "a_plus_d_gt_240")
            self._begin_replacement(r)
            return
        if decision == "PREVENTIVE_REPLACE" and not force:
            self._set_replacement_pending(r, "preventive", "preventive")
            self._begin_replacement(r)
            return
        self._start_task(head)

    # -- closure (same-timestamp order mirroring the accepted engine) ------

    def _closure(self, t: Fraction) -> None:
        self.now = t
        completed, failed, illegal, calib_done, turnover_out, turnover_in = (
            self._settle(t))
        self._observe(completed)
        self._classify(completed)
        exit_devices = self._apply_exits(completed)
        self._cancel_unfinished(exit_devices)
        self._materialize_d()
        self._shift_change()
        self._release_tasks()
        self._equipment_and_dispatch()
        self._start_turnovers()

    def _settle(self, t: Fraction):
        completed: list[_Attempt] = []
        failed: list[tuple[_Attempt, _Task]] = []
        illegal_list: list[tuple[_Attempt, _Task]] = []
        calib_done: list[str] = []
        turnover_out_done: list[int] = []
        turnover_in_done: list[int] = []
        while self._calendar and self._calendar[0][0] == t:
            _time, _cseq, kind, token = heapq.heappop(self._calendar)
            if kind == "test_complete":
                if token in self._cancelled_attempts:
                    continue
                attempt = self.attempts[token]
                attempt.status = "COMPLETED"
                attempt.end_time = t
                task = self.tasks[attempt.task_id]
                task.status = "COMPLETED"
                res = self.resources[task.resource_id]
                res.status = "IDLE"
                res.current_activity = None
                self.equipment[task.resource_id].age += (
                    attempt.end_time - attempt.start_time)
                completed.append(attempt)
            elif kind == "test_failed":
                if token in self._cancelled_attempts:
                    continue
                attempt = self.attempts[token]
                attempt.status = "CANCELLED"
                attempt.end_time = t
                task = self.tasks[attempt.task_id]
                task.status = "READY"
                res = self.resources[task.resource_id]
                res.status = "IDLE"
                res.current_activity = None
                self.equipment[task.resource_id].age += t - attempt.start_time
                failed.append((attempt, task))
            elif kind == "test_240_interrupt":
                if token in self._cancelled_attempts:
                    continue
                attempt = self.attempts[token]
                attempt.status = "CANCELLED"
                attempt.end_time = t
                task = self.tasks[attempt.task_id]
                task.status = "READY"
                res = self.resources[task.resource_id]
                res.status = "IDLE"
                res.current_activity = None
                self.equipment[task.resource_id].age += t - attempt.start_time
                illegal_list.append((attempt, task))
            elif kind == "calibration_complete":
                resource = token
                equip = self.equipment[resource]
                equip.available = True
                equip.replacement_pending = False
                equip.pending_kind = None
                equip.pending_trigger = None
                equip.calibration_in_flight = False
                equip.calibration_start = None
                equip.calibration_end = None
                self.resources[resource].status = "IDLE"
                self.resources[resource].current_activity = None
                calib_done.append(resource)
            elif kind == "turnover_out_complete":
                turnover_out_done.append(token)
            elif kind == "turnover_in_complete":
                turnover_in_done.append(token)
            elif kind == "h2_wait_wake":
                # WAIT_EVENT hold release: at the anchor the strategic wait
                # ends and the H1 baseline re-decides (the same closure's
                # equipment_and_dispatch proceeds normally).
                token_list = list(token) if isinstance(token, tuple) else []
                if token_list and token_list[0] == "wait":
                    self.wait_holds.pop(token_list[1], None)
        def _key(a: _Attempt):
            return (a.device_id, _PROCESS_ORDER[a.process],
                    a.effective_attempt_no)
        completed.sort(key=_key)
        for attempt in completed:
            task = self.tasks[attempt.task_id]
            self._record("ACTIVITY_COMPLETE", device_id=attempt.device_id,
                         process=attempt.process,
                         effective_attempt_no=attempt.effective_attempt_no,
                         resource_id=task.resource_id,
                         attempt_start_time=attempt.start_time,
                         attempt_end_time=attempt.end_time,
                         outcome="NONE")
        failed.sort(key=lambda p: _key(p[0]))
        for attempt, task in failed:
            resource = task.resource_id
            self._record("TASK_CANCEL", device_id=attempt.device_id,
                         process=attempt.process,
                         effective_attempt_no=attempt.effective_attempt_no,
                         resource_id=resource,
                         attempt_start_time=attempt.start_time,
                         attempt_end_time=attempt.end_time,
                         outcome="NONE", cancel_reason="equipment_failure")
            self._record("EQUIPMENT_FAILURE", resource_id=resource,
                         device_id=attempt.device_id, process=attempt.process,
                         effective_attempt_no=attempt.effective_attempt_no,
                         fragment_start=attempt.start_time,
                         fragment_end=attempt.end_time)
            self._requeue_task(task)
            self._set_replacement_pending(resource, "failure",
                                          "mid_fragment_failure")
        illegal_list.sort(key=lambda p: _key(p[0]))
        for attempt, task in illegal_list:
            self._record("TASK_CANCEL", device_id=attempt.device_id,
                         process=attempt.process,
                         effective_attempt_no=attempt.effective_attempt_no,
                         resource_id=task.resource_id,
                         attempt_start_time=attempt.start_time,
                         attempt_end_time=attempt.end_time,
                         outcome="NONE", cancel_reason="illegal_240")
            self._requeue_task(task)
            self._set_replacement_pending(task.resource_id, "mandatory_240",
                                          "illegal_crossing_backstop")
        for resource in calib_done:
            self._record("EQUIPMENT_CALIBRATION_COMPLETE",
                         resource_id=resource, generation=
                         self.equipment[resource].generation,
                         calibration_start=self.now,
                         calibration_end=self.now)
        for bay_id in turnover_out_done:
            bay = self.bays[bay_id]
            self._record("TURNOVER_OUT_COMPLETE", bay_id=bay_id,
                         device_id=bay.current_device_id)
            if self.config.turnover_profile == "0.5h_overlap":
                self._record("TURNOVER_IN_START", bay_id=bay_id,
                             device_id=bay.current_device_id)
                self._record("TURNOVER_IN_COMPLETE", bay_id=bay_id,
                             device_id=bay.current_device_id)
                self._finish_turnover_in(bay, t)
            else:
                bay.status = "OCCUPIED_TRANSPORT_IN"
                bay.transport_phase = "in"
                self._record("TURNOVER_IN_START", bay_id=bay_id,
                             device_id=bay.current_device_id)
                self._schedule("turnover_in_complete",
                               t + self.config.transport_in_h, bay_id)
        for bay_id in turnover_in_done:
            bay = self.bays[bay_id]
            self._record("TURNOVER_IN_COMPLETE", bay_id=bay_id,
                         device_id=bay.current_device_id)
            self._finish_turnover_in(bay, t)
        # post-fragment-end equipment check on completions
        for attempt in completed:
            self._post_fragment_end(self.tasks[attempt.task_id].resource_id)
        return (completed, failed, illegal_list, calib_done,
                turnover_out_done, turnover_in_done)

    def _observe(self, completed: list[_Attempt]) -> None:
        for attempt in completed:
            task = self.tasks[attempt.task_id]
            device_id = attempt.device_id
            process = attempt.process
            true_problem = self._true_problem_for(device_id, process)
            # U_Y_post consumed ONLY on a valid completion
            u = self.provider.u_y(device_id, process,
                                  attempt.effective_attempt_no)
            self.consumed_u_y += 1
            kern = self.kernel[process]
            if true_problem:
                outcome = ("PASS" if u >= 1 - kern["beta"] else "ABNORMAL")
            else:
                outcome = ("ABNORMAL" if u < kern["alpha"] else "PASS")
            attempt.outcome = outcome
            task.outcome = outcome
            self._record("OBSERVATION_MATERIALIZED", device_id=device_id,
                         process=process,
                         effective_attempt_no=attempt.effective_attempt_no,
                         resource_id=task.resource_id, outcome=outcome)

    def _true_problem_for(self, device_id: int, process: str) -> bool:
        dev = self.devices[device_id]
        if process in ("A", "B", "C"):
            return dev.x_abc[{"A": 0, "B": 1, "C": 2}[process]] == 1
        # E
        if any(dev.x_abc[i] for i in range(3)):
            return True
        return dev.d_state == "PROBLEM"

    def _classify(self, completed: list[_Attempt]) -> None:
        for attempt in completed:
            dev = self.devices[attempt.device_id]
            p = dev.process_state[attempt.process]
            p.status = "PASSED" if attempt.outcome == "PASS" else \
                ("AWAITING_RETEST" if attempt.effective_attempt_no == 1
                 else "IN_PROGRESS")
            if attempt.outcome == "ABNORMAL" and attempt.effective_attempt_no == 1:
                p.first_failure_time = self.now
                self._pending_retests[(attempt.device_id, attempt.process)] = \
                    self.now

    def _apply_exits(self, completed: list[_Attempt]) -> list[int]:
        exit_devices: list[int] = []
        passed: list[int] = []
        for attempt in completed:
            if (attempt.outcome == "ABNORMAL"
                    and attempt.effective_attempt_no == 2):
                exit_devices.append(attempt.device_id)
            if (attempt.outcome == "PASS" and attempt.process == "E"):
                passed.append(attempt.device_id)
        exit_set = sorted(set(exit_devices))
        for device_id in exit_set:
            dev = self.devices[device_id]
            dev.terminal_state = "EXITED"
            dev.terminal_reason = "second_abnormal"
            self._record("DEVICE_TERMINAL", device_id=device_id,
                         terminal_state="EXITED",
                         terminal_reason="second_abnormal")
        for device_id in sorted(set(passed) - set(exit_set)):
            dev = self.devices[device_id]
            dev.terminal_state = "PASSED"
            self._record("DEVICE_TERMINAL", device_id=device_id,
                         terminal_state="PASSED")
        return exit_set

    def _cancel_unfinished(self, exit_device_ids: list[int]) -> None:
        for device_id in exit_device_ids:
            for task in sorted(
                    (task for task in self.tasks.values()
                     if task.device_id == device_id),
                    key=lambda task: (_PROCESS_ORDER[task.process],
                                      task.effective_attempt_no,
                                      task.task_id)):
                if task.status in ("COMPLETED", "CANCELLED"):
                    continue
                if task.status == "RUNNING":
                    attempt = self._running_attempt_of(task)
                    if attempt is None:
                        continue
                    attempt.status = "CANCELLED"
                    attempt.end_time = self.now
                    self._cancelled_attempts.add(attempt.attempt_id)
                    self.resources[task.resource_id].status = "IDLE"
                    self.resources[task.resource_id].current_activity = None
                    self.equipment[task.resource_id].age += (
                        self.now - attempt.start_time)
                    task.status = "CANCELLED"
                    self._record("TASK_CANCEL", device_id=device_id,
                                 process=task.process,
                                 effective_attempt_no=task.effective_attempt_no,
                                 resource_id=task.resource_id,
                                 attempt_start_time=attempt.start_time,
                                 attempt_end_time=self.now,
                                 outcome="NONE",
                                 cancel_reason="device_exit")
                    self._post_fragment_end(task.resource_id)
                else:  # READY
                    self._remove_queue_entry(task)
                    task.status = "CANCELLED"
                    self._record("TASK_CANCEL", device_id=device_id,
                                 process=task.process,
                                 effective_attempt_no=task.effective_attempt_no,
                                 resource_id=task.resource_id,
                                 outcome="NONE", cancel_reason="device_exit",
                                 elapsed_hours=Fraction(0))

    def _materialize_d(self) -> None:
        for device_id in sorted(self.devices):
            dev = self.devices[device_id]
            if dev.terminal_state != "PENDING":
                continue
            if dev.d_state != "NOT_CREATED":
                continue
            if not all(dev.process_state[p].status == "PASSED"
                       for p in ("A", "B", "C")):
                continue
            e_tid = self._task_id(device_id, "E", 1)
            if e_tid in self.tasks:
                continue
            # consume U_D_post exactly once at the legal materialization
            u = self.provider.u_d(device_id)
            self.consumed_u_d += 1
            dev.d_state = "PROBLEM" if u < Q_D else "NORMAL"
            if dev.x_d is None:
                dev.x_d = 1 if u < Q_D else 0
            self._record("D_CREATED", device_id=device_id,
                         d_state=dev.d_state, u=u)

    def _shift_change(self) -> None:
        pass  # active shift is computed on demand via _active_shift

    def _release_tasks(self) -> None:
        for device_id in sorted(self._pending_creations):
            dev = self.devices[device_id]
            for proc in ("A", "B", "C"):
                if dev.process_state[proc].status in ("PASSED", "IN_PROGRESS",
                                                      "AWAITING_RETEST"):
                    # already passed / already in flight / awaiting retest
                    # (FIX: in an OFFLINE REBUILD the completed attempt-1
                    # tasks are NOT in self.tasks, so the tid guard below
                    # cannot see them -- the process-state guard prevents
                    # re-releasing a tested attempt that would block the
                    # FCFS queue head forever)
                    continue
                dev.process_state[proc].status = "IN_PROGRESS"
                self._release_task(device_id, proc, 1, dev.entry_time)
        self._pending_creations.clear()
        for (device_id, process), release_time in sorted(
                self._pending_retests.items()):
            dev = self.devices[device_id]
            if dev.terminal_state != "PENDING":
                continue
            self._release_task(device_id, process, 2, release_time)
        self._pending_retests.clear()
        for device_id in sorted(self.devices):
            dev = self.devices[device_id]
            if dev.terminal_state != "PENDING":
                continue
            if dev.process_state["E"].status in ("PASSED", "IN_PROGRESS",
                                                 "AWAITING_RETEST"):
                # FIX: never re-release an E attempt that was already
                # tested (offline rebuild: the completed attempt is not in
                # self.tasks, so the tid guard alone cannot see it)
                continue
            e_tid = self._task_id(device_id, "E", 1)
            if e_tid in self.tasks:
                continue
            if all(dev.process_state[p].status == "PASSED"
                   for p in ("A", "B", "C")):
                dev.process_state["E"].status = "IN_PROGRESS"
                self._release_task(device_id, "E", 1, self.now)
        for bay_id in sorted(self.bays):
            bay = self.bays[bay_id]
            if bay.turnover_pending or bay.current_device_id is None:
                continue
            if bay.status != "OCCUPIED_TESTING":
                continue
            dev = self.devices[bay.current_device_id]
            if dev.terminal_state == "PENDING":
                continue
            if self._next_device_to_create() > self.config.batch_size:
                bay.status = "TERMINAL_OCCUPIED_UNTIL_STOP"
                continue
            inflight = sum(
                1 for b in self.bays.values()
                if b.turnover_pending
                or b.status in ("OCCUPIED_TRANSPORT_OUT",
                                "OCCUPIED_TRANSPORT_IN"))
            if self._next_device_to_create() + inflight > self.config.batch_size:
                bay.status = "TERMINAL_OCCUPIED_UNTIL_STOP"
                continue
            bay.turnover_pending = True

    def _release_task(self, device_id: int, process: str, attempt_no: int,
                      release_time: Fraction) -> None:
        tid = self._task_id(device_id, process, attempt_no)
        if tid in self.tasks:
            return
        task = _Task(task_id=tid, resource_id=process, device_id=device_id,
                     process=process, effective_attempt_no=attempt_no,
                     release_time=release_time)
        self.tasks[tid] = task
        key = make_fcfs_key(release_time, device_id, process, attempt_no)
        self.queues[process].append(_QueueEntry(
            queue_id=process, task_id=tid, fcfs_key=key))
        self._record("TASK_RELEASE", device_id=device_id, process=process,
                     effective_attempt_no=attempt_no, resource_id=process,
                     release_time=release_time)

    def _equipment_and_dispatch(self) -> None:
        starts: list[tuple] = []
        for resource_id in RESOURCES:
            resource = self.resources[resource_id]
            equip = self.equipment[resource_id]
            # WAIT_EVENT strategic hold: the decision resource's head must
            # not be dispatched before the anchor (first-action-only).
            hold_until = self.wait_holds.get(resource_id)
            if hold_until is not None and self.now < hold_until:
                continue
            if equip.replacement_pending and not equip.calibration_in_flight:
                self._begin_replacement(resource_id)
            if resource.status != "IDLE":
                continue
            if not equip.available:
                continue
            queue = self.queues[resource_id]
            if not queue:
                continue
            queue.sort(key=lambda e: e.fcfs_key)
            head = queue[0]
            if head.status != "WAITING":
                continue
            if self._active_shift(self.now) is None:
                continue
            if not self._is_legal(head):
                continue
            d = DURATIONS_H[resource_id]
            a = equip.age
            decision = _replacement_decision(a, d, self.config.tau_pm, True)
            if decision == "MANDATORY_REPLACE_FIRST":
                self._set_replacement_pending(
                    resource_id, "mandatory_240", "a_plus_d_gt_240")
                self._begin_replacement(resource_id)
            elif decision == "PREVENTIVE_REPLACE":
                self._set_replacement_pending(
                    resource_id, "preventive", "preventive")
                self._begin_replacement(resource_id)
            else:
                attempt = self._start_task(head)
                starts.append((head.fcfs_key, attempt))
        starts.sort(key=lambda item: item[0])
        for _key, attempt in starts:
            act = self.resources[attempt.task_id and
                                 self.tasks[attempt.task_id].resource_id] \
                .current_activity
            scheduled_end = (act.get("end_time") if act is not None
                             else None)
            end_rec = (attempt.end_time if attempt.end_time is not None
                       else scheduled_end)
            self._record("ACTIVITY_START", device_id=attempt.device_id,
                         process=attempt.process,
                         effective_attempt_no=attempt.effective_attempt_no,
                         resource_id=self.tasks[attempt.task_id].resource_id,
                         attempt_start_time=attempt.start_time,
                         attempt_end_time=end_rec,
                         outcome="NONE")

    def _begin_replacement(self, resource_id: str) -> None:
        equip = self.equipment[resource_id]
        kind = equip.pending_kind
        trigger = equip.pending_trigger
        cal = CALIBRATION_MINUTES[resource_id] / Fraction(60)
        shift = self._active_shift(self.now)
        if shift is None or self.now + cal > shift[1]:
            if not equip.deferral_emitted:
                next_wake = self._next_shift_boundary_after(self.now)
                self._record("EQUIPMENT_REPLACEMENT_DEFERRED",
                             resource_id=resource_id, kind=kind,
                             trigger=trigger, reason="no_cross_shift",
                             next_wake=next_wake)
                equip.deferral_emitted = True
            return
        equip.deferral_emitted = False
        old_gen = equip.generation
        new_gen = old_gen + 1
        age_before = equip.age
        equip.age = Fraction(0)
        equip.generation = new_gen
        # new generation binds a NEW U_L_post(resource, new_gen)
        u = self.provider.u_l(resource_id, new_gen)
        self.consumed_u_l += 1
        lifetime, censored = _sample_lifetime(resource_id, u)
        equip.lifetime_h = lifetime
        equip.is_right_censored = censored
        equip.calibration_in_flight = True
        equip.calibration_start = self.now
        equip.calibration_end = self.now + cal
        equip.replacement_count += 1
        if kind == "preventive":
            equip.preventive_count += 1
        self.resources[resource_id].status = "BUSY"
        self.resources[resource_id].current_activity = {
            "kind": "calibration", "resource_id": resource_id,
            "start_time": self.now, "end_time": self.now + cal}
        self._schedule("calibration_complete", self.now + cal, resource_id)
        self._record("EQUIPMENT_REPLACEMENT_START", resource_id=resource_id,
                     kind=kind, trigger=trigger, old_generation=old_gen,
                     new_generation=new_gen, age_before=age_before,
                     calibration_duration_hours=cal,
                     calibration_start=self.now, calibration_end=self.now + cal)

    def _is_legal(self, entry: _QueueEntry) -> bool:
        task = self.tasks[entry.task_id]
        device = self.devices[task.device_id]
        if device.terminal_state != "PENDING":
            return False
        bay = self.bays.get(device.bay_id)
        if bay is not None and bay.status not in ("OCCUPIED_TESTING",):
            return False
        if task.process == "E":
            for proc in ("A", "B", "C"):
                if device.process_state[proc].status != "PASSED":
                    return False
        shift = self._active_shift(self.now)
        if shift is None:
            return False
        if self.now + DURATIONS_H[task.process] > shift[1]:
            return False
        return True

    def _start_task(self, head: _QueueEntry) -> _Attempt:
        task = self.tasks[head.task_id]
        resource_id = task.resource_id
        device = self.devices[task.device_id]
        equip = self.equipment[resource_id]
        shift = self._active_shift(self.now)
        squad = shift[1] if shift is not None else None
        a = equip.age
        d = DURATIONS_H[resource_id]
        kind, frag_dur = _fragment_outcome(a, d, equip.lifetime_h,
                                           equip.is_right_censored)
        if kind == "complete":
            event_kind = "test_complete"
        elif kind == "failed":
            event_kind = "test_failed"
        else:
            event_kind = "test_240_interrupt"
        self._fragment_counter[task.task_id] = (
            self._fragment_counter.get(task.task_id, 0) + 1)
        execution_no = self._fragment_counter[task.task_id]
        attempt_id = (f"A{task.device_id:03d}_{task.process}_"
                      f"{task.effective_attempt_no}_{execution_no}")
        attempt = _Attempt(
            attempt_id=attempt_id, task_id=task.task_id,
            device_id=task.device_id, process=task.process,
            effective_attempt_no=task.effective_attempt_no,
            start_time=self.now, result_squad_id=squad)
        self.attempts[attempt_id] = attempt
        task.status = "RUNNING"
        self.devices[task.device_id].process_state[task.process].status = (
            "IN_PROGRESS")
        resource = self.resources[resource_id]
        resource.status = "BUSY"
        resource.current_activity = {
            "kind": "test", "task_id": task.task_id,
            "attempt_id": attempt_id, "device_id": task.device_id,
            "process": task.process, "attempt_no": task.effective_attempt_no,
            "start_time": self.now, "end_time": self.now + frag_dur}
        head.status = "DISPATCHED"
        self.queues[resource_id].pop(0)
        end = self.now + frag_dur
        self._schedule(event_kind, end, attempt_id)
        return attempt

    def _post_fragment_end(self, resource: str) -> None:
        equip = self.equipment[resource]
        if equip.replacement_pending:
            return
        if equip.age >= MANDATORY_AGE_H:
            self._set_replacement_pending(resource, "mandatory_240",
                                          "post_completion_240")
            return
        if not equip.is_right_censored and equip.lifetime_h is not None:
            if equip.age >= equip.lifetime_h:
                self._set_replacement_pending(resource, "failure",
                                              "failure_at_end")

    def _set_replacement_pending(self, resource: str, kind: str,
                                 trigger: str) -> None:
        equip = self.equipment[resource]
        equip.available = False
        equip.replacement_pending = True
        equip.pending_kind = kind
        equip.pending_trigger = trigger
        equip.deferral_emitted = False

    def _start_turnovers(self) -> None:
        for bay_id in sorted(self.bays):
            bay = self.bays[bay_id]
            if not bay.turnover_pending:
                continue
            if bay.status != "OCCUPIED_TESTING":
                continue
            shift = self._active_shift(self.now)
            if shift is None:
                continue
            total = (self.config.transport_out_h
                     + self.config.transport_in_h)
            if self.now + total > shift[1]:
                continue
            bay.turnover_pending = False
            bay.status = "OCCUPIED_TRANSPORT_OUT"
            bay.transport_phase = "out"
            self._record("TURNOVER_OUT_START", bay_id=bay_id,
                         device_id=bay.current_device_id)
            self._schedule("turnover_out_complete",
                           self.now + self.config.transport_out_h, bay_id)

    def _finish_turnover_in(self, bay: _Bay, t: Fraction) -> None:
        device_id = self._next_device_to_create()
        if device_id > self.config.batch_size:
            raise RuntimeError("turnover_in without a next device")
        bay.status = "OCCUPIED_TESTING"
        bay.transport_phase = "none"
        self._create_device(device_id, t, bay.bay_id)
        self._pending_creations.append(device_id)

    def _create_device(self, device_id: int, entry_time: Fraction,
                       bay_id: int) -> None:
        device = _Device(device_id=device_id, entry_time=entry_time,
                         bay_id=bay_id,
                         process_state={p: _ProcessState(p)
                                        for p in RESOURCES})
        # hidden truth for a not-yet-entered device: sample from the PRIOR
        # (SPEC 8: 未进入装置按各先验采样) using per-subsystem U_X_post
        # (canonical slot = subsystem, mirroring the accepted engine's three
        # U_X keys per device; SPEC 6.2 U_X_post slot semantics).
        x_abc = [0, 0, 0]
        for sub, idx in (("A", 0), ("B", 1), ("C", 2)):
            u = self.provider.u_x_subsystem(device_id, sub)
            x_abc[idx] = 1 if u < Q_ABC[sub] else 0
        device.x_abc = (x_abc[0], x_abc[1], x_abc[2])
        device.x_d = None
        self.devices[device_id] = device
        self._created_count = max(self._created_count, device_id)
        bay = self.bays[bay_id]
        bay.current_device_id = device_id
        bay.status = "OCCUPIED_TESTING"
        bay.transport_phase = "none"
        self._record("TRUE_STATE_GENERATED", device_id=device_id,
                     entry_time=entry_time, bay_id=bay_id)

    # -- helpers ----------------------------------------------------------

    def _task_id(self, device_id: int, process: str, attempt_no: int) -> str:
        return f"t_{device_id}_{process}_{attempt_no}"

    def _running_attempt_of(self, task: _Task) -> Optional[_Attempt]:
        for attempt in self.attempts.values():
            if (attempt.task_id == task.task_id
                    and attempt.status == "RUNNING"):
                return attempt
        return None

    def _remove_queue_entry(self, task: _Task) -> None:
        queue = self.queues[task.resource_id]
        for idx, entry in enumerate(queue):
            if entry.task_id == task.task_id:
                entry.status = "REMOVED"
                queue.pop(idx)
                return

    def _requeue_task(self, task: _Task) -> None:
        """Re-insert a failure-interrupted task at the FCFS head position:
        the frozen FCFS key is unchanged (release_time immutable, effective
        attempt unchanged), so its key is strictly smaller than every other
        queued task of the same resource."""
        key = make_fcfs_key(task.release_time, task.device_id, task.process,
                            task.effective_attempt_no)
        entry = _QueueEntry(queue_id=task.resource_id, task_id=task.task_id,
                            fcfs_key=key)
        self.queues[task.resource_id].insert(0, entry)

    def _next_device_to_create(self) -> int:
        return self._created_count + 1

    # -- run --------------------------------------------------------------

    def run(self) -> RolloutResult:
        # first action applied at the initial decision point
        self._apply_first_action_if_dispatch()
        # initial closure at the start time (releases + dispatch, mirroring
        # the accepted engine's run(): _closure(Fraction(0)) first)
        self._closure(self.now)
        # fail-closed runaway guard: a legitimate 100-device batch settles
        # in a few thousand closures; 1e6 is a huge headroom and turns any
        # future non-termination (e.g. a stuck resource whose completion
        # event was never scheduled) into a detectable RuntimeError instead
        # of an unbounded WAKE_UP loop that exhausts memory.
        closures = 0
        while True:
            if self._is_terminal():
                self._record("SIMULATION_END")
                break
            closures += 1
            if closures > MAX_CLOSURES:
                raise RuntimeError(
                    f"runaway: {closures} closures without termination at "
                    f"now={self.now} (fail-closed guard)")
            nxt = self._next_event_time()
            if nxt <= self.now:
                raise RuntimeError(f"no progress: next event {nxt} <= now "
                                   f"{self.now}")
            cal_min = self._calendar_min()
            boundary = self._next_shift_boundary_after(self.now)
            if (cal_min is None and boundary is not None
                    and nxt == boundary):
                self.now = nxt
                self._record("WAKE_UP")
            self._closure(nxt)
        return RolloutResult(
            t_end=self.now,
            events=tuple(self.log),
            consumed_u_y=self.consumed_u_y,
            consumed_u_d=self.consumed_u_d,
            consumed_u_l=self.consumed_u_l,
            replacements=sum(e.replacement_count
                             for e in self.equipment.values()),
            devices_passed=sum(1 for d in self.devices.values()
                               if d.terminal_state == "PASSED"),
            devices_exited=sum(1 for d in self.devices.values()
                               if d.terminal_state == "EXITED"),
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
            raise RuntimeError("calendar empty and no future shift boundary "
                               "while work is unfinished")
        return min(candidates)


_PROCESS_ORDER_REV = {0: "A", 1: "B", 2: "C", 3: "E"}


def _f120f240(resource: str):
    from main_model.h2.frozen_params_v1 import F120, F240
    return F120[resource], F240[resource]


def _sample_lifetime(resource: str, u: Fraction):
    f120, f240 = _f120f240(resource)
    return inverse_cdf(u, f120, f240)
