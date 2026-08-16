#!/usr/bin/env python3
"""Q3-H2-P1 ObservableState: the H2 information-firewall safe projection.

Frozen authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED
section 7 (C23 observable-information boundary) and section 8/9 (posterior
/ conditional-lifetime interface references ONLY -- their mathematics is
P2/P3 and is NOT implemented here).

Design (Q3-H2-P1):
  * ObservableState is an IMMUTABLE DTO exposing ONLY the frozen whitelist
    (section 7):
      - time t and calendar / active shift / on-duty squad;
      - remaining not-yet-entered device count n;
      - bay occupancy / turnover state;
      - per-resource status (idle/testing/failed/replacement/calibration),
        equipment age a_j, in-flight remaining l_j, generation g_j;
      - queue entries with frozen FCFS keys
        (release_time, device_id, process_order, effective_attempt_no);
      - each device's materialized completed observation history and
        effective attempt numbers;
      - D materialized BOOLEAN only;
      - device terminal state;
      - completed replacement/calibration history.
  * FORBIDDEN information (section 7) is structurally excluded: the DTO has
    no fields for true_state / x_A..x_D / live U_L / live lifetime / future
    U / u_key material / is_right_censored / unmaterialized D truth / raw
    DES or engine references.  The DTO is a plain immutable data carrier and
    never retains the raw log, the engine, device/equipment objects, or any
    closure that could reach hidden state.
  * The PRIVILEGED boundary adapter (``project_log_prefix``) MAY read raw
    event-log records (which contain hidden annotations such as
    ``true_state`` / ``u`` / ``u_key``) ONLY to construct the safe DTO.  It
    reads ONLY whitelisted record fields, is TIME-CAUSAL (only records with
    event_time <= t influence the projection -- Density E1 lesson), and is
    FRAGMENT-AWARE (a fragment is settled only by a COMPLETE/CANCEL with
    the SAME attempt_start_time -- Density E2 lesson).  It never returns
    anything but the immutable DTO.
  * Deterministic canonical form: resources A/B/C/E, bays and devices by
    id, queue by frozen FCFS key, observations by (time, process, attempt).
    ``to_canonical_dict`` / ``fingerprint`` support checker comparison.
    No object ids / memory addresses / unordered iteration enter it.

This module imports NOTHING from the live DES engine (``g3`` / ``des``):
the adapter processes plain dict records, and the frozen canonical constants
are declared locally.  H2 consumers receive only ObservableState.

Python 3.12, standard library only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Frozen canonical constants (declared locally; the h2 package must not
# import the live DES engine per the C23 import/AST isolation clause).
# ---------------------------------------------------------------------------

RESOURCES: tuple[str, ...] = ("A", "B", "C", "E")
PROCESS_ORDER: dict[str, int] = {"A": 0, "B": 1, "C": 2, "E": 3}
DEFAULT_DURATIONS_H: dict[str, Fraction] = {
    "A": Fraction(5, 2),
    "B": Fraction(2),
    "C": Fraction(5, 2),
    "E": Fraction(3),
}
CALIBRATION_MINUTES: dict[str, Fraction] = {
    "A": Fraction(30),
    "B": Fraction(20),
    "C": Fraction(20),
    "E": Fraction(40),
}

# Frozen C23 forbidden-name vocabulary (used by the checker; the DTO has no
# such fields and the adapter never reads them).
FORBIDDEN_NAMES: tuple[str, ...] = (
    "true_state", "x_A", "x_B", "x_C", "x_D",
    "lifetime_h", "is_right_censored", "u_key", "u", "consumed_u",
    "d_state_value", "hidden",
)

EV_ACTIVITY_START = "ACTIVITY_START"
EV_ACTIVITY_COMPLETE = "ACTIVITY_COMPLETE"
EV_TASK_RELEASE = "TASK_RELEASE"
EV_TASK_CANCEL = "TASK_CANCEL"
EV_OBSERVATION = "OBSERVATION_MATERIALIZED"
EV_D_CREATED = "D_CREATED"
EV_DEVICE_TERMINAL = "DEVICE_TERMINAL"
EV_TRUE_STATE = "TRUE_STATE_GENERATED"
EV_REPLACEMENT_START = "EQUIPMENT_REPLACEMENT_START"
EV_REPLACEMENT_DEFERRED = "EQUIPMENT_REPLACEMENT_DEFERRED"
EV_CALIBRATION_COMPLETE = "EQUIPMENT_CALIBRATION_COMPLETE"
EV_SHIFT_CHANGE = "SHIFT_CHANGE"
EV_TURNOVER_OUT_START = "TURNOVER_OUT_START"
EV_TURNOVER_OUT_COMPLETE = "TURNOVER_OUT_COMPLETE"
EV_TURNOVER_IN_START = "TURNOVER_IN_START"
EV_TURNOVER_IN_COMPLETE = "TURNOVER_IN_COMPLETE"


# ---------------------------------------------------------------------------
# Immutable DTOs (frozen whitelist only; no hidden fields, no raw refs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservationObs:
    time: Fraction
    process: str
    attempt: int
    outcome: str  # materialized observation outcome only (never true_state)


@dataclass(frozen=True)
class DeviceObs:
    device_id: int
    terminal_state: Optional[str]  # "PASSED" / "EXITED" / None
    d_materialized: bool           # boolean ONLY (never x_D)
    observations: tuple[ObservationObs, ...]  # materialized history, sorted
    effective_attempts: tuple[tuple[str, int], ...]  # (process, attempt_no)


@dataclass(frozen=True)
class BayObs:
    bay_id: int
    current_device: Optional[int]
    status: str  # EMPTY / TESTING / TRANSPORT / TERMINAL


@dataclass(frozen=True)
class ResourceObs:
    resource: str
    status: str  # idle / testing / failed / replacement / calibration
    age_h: Fraction
    in_flight_remaining_h: Fraction
    generation: int


@dataclass(frozen=True)
class QueueObs:
    release_time: Fraction
    device_id: int
    process_order: int
    effective_attempt_no: int


@dataclass(frozen=True)
class ReplacementObs:
    resource: str
    kind: str
    trigger: str
    calibration_start: Fraction
    calibration_end: Fraction
    old_generation: int
    new_generation: int


@dataclass(frozen=True)
class ObservableState:
    """Immutable safe projection of the live DES hidden world at time t.

    Exposes ONLY the frozen section-7 whitelist.  No engine/device/
    equipment/log references are retained; every value is an immutable
    primitive, Fraction, or tuple of frozen DTOs with deterministic order.
    replacement_history contains ONLY already-completed replacement /
    calibration records (frozen semantics '已完成更换/校准历史'); ongoing
    replacements are expressed via ResourceObs.status / in_flight_remaining
    / generation and are NOT in replacement_history until their
    calibration completes (temporal causality, no future leakage).
    """
    time: Fraction
    active_shift: Optional[tuple[Fraction, Fraction]]
    shift_index: Optional[int]
    on_duty_squad: Optional[int]
    remaining_not_entered: int
    bays: tuple[BayObs, ...]
    resources: tuple[ResourceObs, ...]
    queue: tuple[QueueObs, ...]
    devices: tuple[DeviceObs, ...]
    replacement_history: tuple[ReplacementObs, ...]

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "time": str(self.time),
            "active_shift": (None if self.active_shift is None
                             else [str(self.active_shift[0]),
                                   str(self.active_shift[1])]),
            "shift_index": self.shift_index,
            "on_duty_squad": self.on_duty_squad,
            "remaining_not_entered": self.remaining_not_entered,
            "bays": [{"bay_id": b.bay_id, "current_device": b.current_device,
                      "status": b.status} for b in self.bays],
            "resources": [{"resource": r.resource, "status": r.status,
                           "age_h": str(r.age_h),
                           "in_flight_remaining_h": str(r.in_flight_remaining_h),
                           "generation": r.generation} for r in self.resources],
            "queue": [{"release_time": str(q.release_time),
                       "device_id": q.device_id,
                       "process_order": q.process_order,
                       "effective_attempt_no": q.effective_attempt_no}
                      for q in self.queue],
            "devices": [{"device_id": d.device_id,
                         "terminal_state": d.terminal_state,
                         "d_materialized": d.d_materialized,
                         "observations": [
                             {"time": str(o.time), "process": o.process,
                              "attempt": o.attempt, "outcome": o.outcome}
                             for o in d.observations],
                         "effective_attempts": [list(a) for a in d.effective_attempts]}
                        for d in self.devices],
            "replacement_history": [
                {"resource": rh.resource, "kind": rh.kind, "trigger": rh.trigger,
                 "calibration_start": str(rh.calibration_start),
                 "calibration_end": str(rh.calibration_end),
                 "old_generation": rh.old_generation,
                 "new_generation": rh.new_generation} for rh in self.replacement_history],
        }

    def fingerprint(self) -> str:
        """Deterministic SHA-256 fingerprint of the canonical form."""
        canonical = json.dumps(
            self.to_canonical_dict(), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Privileged boundary adapter (reads RAW records ONLY to build the safe DTO)
# ---------------------------------------------------------------------------

_FRAGMENT_SETTLE_TYPES = (EV_ACTIVITY_COMPLETE, EV_TASK_CANCEL)


def _frac(value: Any) -> Fraction:
    return Fraction(value)


def _fragment_settled(pre: list[dict[str, Any]], device: int, process: str,
                      attempt: int, fstart: Fraction) -> bool:
    """Fragment-aware settle: only a COMPLETE/CANCEL with the SAME
    attempt_start_time settles this fragment (Density E2 lesson)."""
    for r in pre:
        if r.get("event_type") not in _FRAGMENT_SETTLE_TYPES:
            continue
        if r.get("attempt_start_time") is None:
            continue
        if (r.get("device_id") == device and r.get("process") == process
                and r.get("effective_attempt_no") == attempt
                and _frac(r["attempt_start_time"]) == fstart):
            return True
    return False


def _fragment_running(pre: list[dict[str, Any]], device: int, process: str,
                      attempt: int, t: Fraction) -> bool:
    for r in pre:
        if r.get("event_type") != EV_ACTIVITY_START:
            continue
        if (r.get("device_id") != device or r.get("process") != process
                or r.get("effective_attempt_no") != attempt):
            continue
        s = _frac(r.get("attempt_start_time", r["event_time"]))
        end = _frac(r["attempt_end_time"])
        if s <= t < end and not _fragment_settled(
                pre, device, process, attempt, s):
            return True
    return False


def _task_completed(pre: list[dict[str, Any]], device: int, process: str,
                    attempt: int, t: Fraction) -> bool:
    return any(r.get("event_type") == EV_ACTIVITY_COMPLETE
               and r.get("device_id") == device and r.get("process") == process
               and r.get("effective_attempt_no") == attempt
               and _frac(r["event_time"]) <= t
               for r in pre)


def q3_shift_grid(K: Fraction) -> list[tuple[Fraction, Fraction]]:
    """Frozen Q3 two-shift calendar: day d: shift 1 = [24d, 24d+K),
    shift 2 = [24d+K, 24d+2K), off [24d+2K, 24(d+1)).  Horizon 400 days
    is far beyond any 100-device Q3 batch (frozen config, implementer
    copy; the checker keeps its own independent copy)."""
    out: list[tuple[Fraction, Fraction]] = []
    for d in range(0, 400):
        s1 = Fraction(24) * d
        out.append((s1, s1 + K))
        out.append((s1 + K, s1 + 2 * K))
    return out


def active_shift(shifts: list[tuple[Fraction, Fraction]], t: Fraction
                 ) -> Optional[tuple[Fraction, Fraction]]:
    for s, e in shifts:
        if s <= t < e:
            return (s, e)
    return None


def project_log_prefix(event_log: list[dict[str, Any]], t: Fraction,
                       batch_size: int = 100) -> ObservableState:
    """PRIVILEGED projection of the log PREFIX (event_time <= t) into the
    safe ObservableState.  Time-causal and fragment-aware; reads only
    whitelisted record fields; never retains the log."""
    pre = sorted(
        (r for r in event_log if r.get("event_time") is not None
         and _frac(r["event_time"]) <= t),
        key=lambda r: (_frac(r["event_time"]), 0))
    # stable secondary order: preserve input order within the same time
    pre.sort(key=lambda r: _frac(r["event_time"]))

    # -- calendar / shift / squad (last SHIFT_CHANGE <= t) --
    shift_index: Optional[int] = None
    on_duty_squad: Optional[int] = None
    active_shift: Optional[tuple[Fraction, Fraction]] = None
    for r in pre:
        if r.get("event_type") == EV_SHIFT_CHANGE:
            s = _frac(r["shift_start"])
            e = _frac(r["shift_end"])
            if s <= t < e:
                active_shift = (s, e)
                shift_index = r.get("shift_index")
                on_duty_squad = r.get("on_duty_squad")

    # -- entered devices / remaining not entered --
    entered: set[int] = set()
    for r in pre:
        if r.get("event_type") == EV_TRUE_STATE:
            entered.add(r["device_id"])
    remaining_not_entered = max(0, batch_size - len(entered))

    # -- replacement / deferral / calibration windows per resource --
    repl_records: dict[str, list[dict[str, Any]]] = {r: [] for r in RESOURCES}
    cal_windows: dict[str, list[tuple[Fraction, Fraction]]] = {r: [] for r in RESOURCES}
    deferrals: dict[str, list[Fraction]] = {r: [] for r in RESOURCES}
    for r in pre:
        et = r.get("event_type")
        rsrc = r.get("resource_id")
        if rsrc not in RESOURCES:
            continue
        if et == EV_REPLACEMENT_START:
            repl_records[rsrc].append(r)
            cs = _frac(r["calibration_start"])
            ce = _frac(r["calibration_end"])
            cal_windows[rsrc].append((cs, ce))
        elif et == EV_REPLACEMENT_DEFERRED:
            deferrals[rsrc].append(_frac(r["event_time"]))

    def _repl_window(rsrc: str, t: Fraction) -> Optional[tuple[Fraction, Fraction]]:
        """Replacement pending window [w0, w1) covering t (replacement start
        or deferral until the next replacement's calibration end)."""
        wins: list[tuple[Fraction, Fraction]] = []
        for r in repl_records[rsrc]:
            wins.append((_frac(r["event_time"]), _frac(r["calibration_end"])))
        for td in deferrals[rsrc]:
            nxt = None
            for r in repl_records[rsrc]:
                q0 = _frac(r["event_time"])
                qce = _frac(r["calibration_end"])
                if q0 >= td and (nxt is None or qce < nxt):
                    nxt = qce
            if nxt is not None:
                wins.append((td, nxt))
        for w0, w1 in wins:
            if w0 <= t < w1:
                return (w0, w1)
        return None

    def _gen_start(rsrc: str, t: Fraction) -> Fraction:
        gs = Fraction(0)
        for r in repl_records[rsrc]:
            t0 = _frac(r["event_time"])
            if t0 <= t:
                gs = max(gs, t0)
        return gs

    def _equipment_age(rsrc: str, t: Fraction) -> Fraction:
        gs = _gen_start(rsrc, t)
        age = Fraction(0)
        for r in pre:
            if r.get("event_type") not in _FRAGMENT_SETTLE_TYPES:
                continue
            if r.get("resource_id") != rsrc:
                continue
            if r.get("attempt_start_time") is None:
                continue
            s = _frac(r["attempt_start_time"])
            e = _frac(r["event_time"])
            if s < gs or e > t:
                continue
            age += e - s
        return age

    def _generation(rsrc: str, t: Fraction) -> int:
        gen = 1
        for r in repl_records[rsrc]:
            if _frac(r["event_time"]) <= t:
                gen = r.get("new_generation", gen)
        return int(gen)

    # -- resources --
    resources: list[ResourceObs] = []
    for rsrc in RESOURCES:
        status = "idle"
        in_flight = Fraction(0)
        # calibration busy
        cal_cover = None
        for cs, ce in cal_windows[rsrc]:
            if cs <= t < ce:
                cal_cover = (cs, ce)
                break
        if cal_cover is not None:
            status = "calibration"
            in_flight = cal_cover[1] - t
        else:
            # in-flight test fragment
            running = None
            for r in pre:
                if r.get("event_type") != EV_ACTIVITY_START:
                    continue
                if r.get("resource_id") != rsrc:
                    continue
                s = _frac(r.get("attempt_start_time", r["event_time"]))
                end = _frac(r["attempt_end_time"])
                if s <= t < end and not _fragment_settled(
                        pre, r["device_id"], r["process"],
                        r["effective_attempt_no"], s):
                    running = (s, end)
                    break
            if running is not None:
                status = "testing"
                in_flight = running[1] - t
            else:
                win = _repl_window(rsrc, t)
                if win is not None:
                    # failure-driven replacement (kind=failure) -> "failed",
                    # otherwise mandatory/preventive pending -> "replacement"
                    trigger = ""
                    for r in repl_records[rsrc]:
                        if _frac(r["event_time"]) <= t and _frac(r["event_time"]) >= win[0]:
                            trigger = r.get("trigger", "")
                    status = "failed" if "failure" in trigger else "replacement"
        resources.append(ResourceObs(
            resource=rsrc, status=status, age_h=_equipment_age(rsrc, t),
            in_flight_remaining_h=in_flight, generation=_generation(rsrc, t)))

    # -- queue (fragment-aware waiting tasks, frozen FCFS order) --
    terminal_t: dict[int, Fraction] = {}
    for r in pre:
        if r.get("event_type") == EV_DEVICE_TERMINAL:
            d = r["device_id"]
            tt = _frac(r["event_time"])
            if d not in terminal_t or tt < terminal_t[d]:
                terminal_t[d] = tt
    # per (dev, proc, att): earliest release
    releases: dict[tuple[int, str, int], Fraction] = {}
    for r in pre:
        if r.get("event_type") == EV_TASK_RELEASE:
            key = (r["device_id"], r["process"], r["effective_attempt_no"])
            rt = _frac(r["event_time"])
            if key not in releases or rt < releases[key]:
                releases[key] = rt
    queue: list[QueueObs] = []
    for (dev, proc, att), rel in releases.items():
        if rel > t:
            continue
        if dev in terminal_t and terminal_t[dev] <= t:
            continue
        if _task_completed(pre, dev, proc, att, t):
            continue
        if _fragment_running(pre, dev, proc, att, t):
            continue
        queue.append(QueueObs(release_time=rel, device_id=dev,
                              process_order=PROCESS_ORDER[proc],
                              effective_attempt_no=att))
    queue.sort(key=lambda q: (q.release_time, q.device_id, q.process_order,
                              q.effective_attempt_no))

    # -- devices (observations / effective attempts / terminal / D bool) --
    obs_by_dev: dict[int, list[ObservationObs]] = {}
    attempts_by_dev: dict[int, set[tuple[str, int]]] = {}
    d_materialized: set[int] = set()
    for r in pre:
        et = r.get("event_type")
        if et == EV_OBSERVATION:
            d = r["device_id"]
            obs_by_dev.setdefault(d, []).append(ObservationObs(
                time=_frac(r["event_time"]), process=r["process"],
                attempt=r["effective_attempt_no"], outcome=r["outcome"]))
        elif et == EV_TASK_RELEASE:
            d = r["device_id"]
            attempts_by_dev.setdefault(d, set()).add(
                (r["process"], r["effective_attempt_no"]))
        elif et == EV_D_CREATED:
            d_materialized.add(r["device_id"])
    devices: list[DeviceObs] = []
    for dev in sorted(entered):
        obs = sorted(obs_by_dev.get(dev, []),
                     key=lambda o: (o.time, PROCESS_ORDER[o.process], o.attempt))
        atts = sorted(attempts_by_dev.get(dev, set()))
        terminal_state = None
        if dev in terminal_t:
            for r in pre:
                if r.get("event_type") == EV_DEVICE_TERMINAL \
                        and r.get("device_id") == dev \
                        and _frac(r["event_time"]) == terminal_t[dev]:
                    terminal_state = r.get("terminal_state")
                    break
        devices.append(DeviceObs(
            device_id=dev, terminal_state=terminal_state,
            d_materialized=dev in d_materialized,
            observations=tuple(obs), effective_attempts=tuple(atts)))

    # -- bays (occupancy / turnover state, deterministic) --
    bay_dev: dict[int, int] = {}
    bay_state: dict[int, str] = {}
    for r in pre:
        et = r.get("event_type")
        bid = r.get("bay_id")
        if bid is None:
            continue
        if et in (EV_D_CREATED, EV_TURNOVER_IN_COMPLETE) \
                and r.get("device_id") is not None:
            bay_dev[int(bid)] = r["device_id"]
        if et in (EV_TURNOVER_OUT_START, EV_TURNOVER_OUT_COMPLETE,
                  EV_TURNOVER_IN_START):
            bay_state[int(bid)] = "TRANSPORT"
        elif et == EV_TURNOVER_IN_COMPLETE:
            bay_state[int(bid)] = "TESTING"
    for r in pre:
        if r.get("event_type") == EV_DEVICE_TERMINAL and r.get("bay_id") is not None:
            bay_state[int(r["bay_id"])] = "TERMINAL"
    bays: list[BayObs] = []
    for bid in sorted(bay_dev.keys() | bay_state.keys()):
        bays.append(BayObs(bay_id=bid, current_device=bay_dev.get(bid),
                           status=bay_state.get(bid, "TESTING")))

    # -- completed replacement/calibration history (no u / u_key) --
    # FROZEN semantics ('已完成更换/校准历史'): ONLY replacement/
    # calibration records whose calibration has COMPLETED at or before t
    # (a matching EQUIPMENT_CALIBRATION_COMPLETE with calibration_end <= t)
    # enter the history.  Ongoing replacements are expressed by
    # ResourceObs.status / in_flight_remaining_h / generation and NEVER
    # appear here before completion (no future leakage).
    calib_done: set[tuple[str, Fraction]] = set()
    for r in pre:
        if r.get("event_type") == EV_CALIBRATION_COMPLETE:
            calib_done.add((r["resource_id"], _frac(r["calibration_end"])))
    replacement_history: list[ReplacementObs] = []
    for rsrc in RESOURCES:
        for r in repl_records[rsrc]:
            ce = _frac(r["calibration_end"])
            if (rsrc, ce) not in calib_done:
                continue  # not yet completed at t -> NOT in completed history
            replacement_history.append(ReplacementObs(
                resource=rsrc, kind=r.get("kind", ""), trigger=r.get("trigger", ""),
                calibration_start=_frac(r["calibration_start"]),
                calibration_end=ce,
                old_generation=r.get("old_generation", 0),
                new_generation=r.get("new_generation", 0)))
    replacement_history.sort(key=lambda rh: (rh.resource, rh.calibration_start))

    return ObservableState(
        time=t, active_shift=active_shift, shift_index=shift_index,
        on_duty_squad=on_duty_squad, remaining_not_entered=remaining_not_entered,
        bays=tuple(bays), resources=tuple(resources), queue=tuple(queue),
        devices=tuple(devices), replacement_history=tuple(replacement_history))
