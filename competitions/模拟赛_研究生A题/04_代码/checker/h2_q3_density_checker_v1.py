#!/usr/bin/env python3
"""Q3-H2-DENSITY-E1/E2 independent checker (temporal reconstruction).

The density analyzer must not self-certify.  This checker independently
recomputes the frozen classifications for hand-built deterministic small
cases and cross-checks the analyzer on those same logs.  It does NOT call
the analyzer's classification functions (fcfs_head_at /
future_potential_demand_at / process_passed_at_or_before / classify /
resource_idle_at / build_time_index) as an oracle: expected values are
derived by the checker's OWN log-prefix logic and hand derivation.  The
analyzer is used only as the system under test.

Q3-H2-DENSITY-E2 (fragment-aware requalification): the checker's prefix
state reconstruction is FRAGMENT-AWARE -- the same (device, process,
effective_attempt_no) may own several physical fragments (equipment
failure / illegal-240 interruption -> TASK_CANCEL -> requeue with the
frozen FCFS key -> later ACTIVITY_START).  Fragment identity includes
attempt_start_time; a fragment is settled ONLY by a COMPLETE/CANCEL with
the SAME attempt_start_time (prefix_fragment_settled / prefix_running).

Boundary cases (frozen definitions, Bootstrap FINAL_FREEZE_ACCEPTED
sections 10/11/12/15 + D-14; Q3-H2-DENSITY-E1 sections 5/6/14):
  C1 STRICT, C2 BOUNDARY (e == latest_start legal WAIT),
  C3 NONSTRICT-not-legal, C4 PM_WITH_HEAD, C5 PM_IDLE queue-empty,
  C6 PM_IDLE forced-wait, C7 exact_240 (a+d==240), C8 mandatory
  (kind=mandatory_240 replacement, pre-start), C9 determinism/resource
  order;
  T1 future-terminal contamination, T2 future-PASS contamination,
  T3 future-release contamination, T4 delayed-start stale waiting,
  T5 completed-full-log PM_IDLE (old bug: pm_idle=0 -> new: 1),
  T6 forced wait with eventual terminal records, T7 TASK_RELEASE closure
  on idle resource, T8 mandatory pre-start replacement, T9 exact_240,
  T10 same-timestamp single decision point per resource;
  T11 cancel->requeue between fragments, T12 restarted fragment running,
  T13 second fragment complete, T14 PM_IDLE false during restarted
  fragment, T15 post-cancel legal/illegal FCFS head.

Python 3.12, standard library only.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from checker import h2_q3_density_analyzer_v1 as an  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic event-log builders (engine event schema)
# ---------------------------------------------------------------------------


def ev(event_type: str, **fields) -> dict[str, Any]:
    return {"event_type": event_type, **fields}


def true_state(devices: list[int]) -> list[dict[str, Any]]:
    out = []
    for d in devices:
        out.append(ev("TRUE_STATE_GENERATED", event_time="0", device_id=d,
                      true_state={"A": False, "B": False, "C": False}))
    return out


def release(device: int, process: str, t: str, attempt: int = 1) -> dict[str, Any]:
    return ev("TASK_RELEASE", event_time=t, resource_id=process, device_id=device,
              process=process, effective_attempt_no=attempt)


def start(device: int, process: str, t: str, end: str, attempt: int = 1,
          resource: Optional[str] = None) -> dict[str, Any]:
    return ev("ACTIVITY_START", event_time=t, device_id=device, process=process,
              effective_attempt_no=attempt, resource_id=resource or process,
              attempt_start_time=t, attempt_end_time=end, outcome="NONE")


def complete(device: int, process: str, t: str, s: str,
             attempt: int = 1) -> dict[str, Any]:
    return ev("ACTIVITY_COMPLETE", event_time=t, device_id=device, process=process,
              effective_attempt_no=attempt, resource_id=process,
              attempt_start_time=s, outcome="PASS", result_squad_id=0)


def cancel(device: int, process: str, t: str, s: str,
           reason: str = "EQUIPMENT_FAILURE", attempt: int = 1) -> dict[str, Any]:
    return ev("TASK_CANCEL", event_time=t, device_id=device, process=process,
              resource_id=process, effective_attempt_no=attempt,
              attempt_start_time=s, attempt_end_time=t, outcome="NONE",
              cancel_reason=reason,
              elapsed_hours=str(Fraction(t) - Fraction(s)))


def obs(device: int, process: str, t: str, attempt: int = 1) -> dict[str, Any]:
    return ev("OBSERVATION_MATERIALIZED", event_time=t, device_id=device,
              process=process, effective_attempt_no=attempt, outcome="PASS")


def terminal(device: int, t: str, state: str = "PASSED") -> dict[str, Any]:
    return ev("DEVICE_TERMINAL", event_time=t, device_id=device,
              terminal_state=state)


def replacement_start(resource: str, t: str, kind: str, trigger: str,
                      cal: str = "1/2") -> dict[str, Any]:
    return ev("EQUIPMENT_REPLACEMENT_START", event_time=t, resource_id=resource,
              kind=kind, trigger=trigger, calibration_start=t,
              calibration_end=str(Fraction(t) + Fraction(cal)),
              old_generation=1, new_generation=2)


def synthetic_log(records: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    flat = [r for group in records
            for r in (group if isinstance(group, list) else [group])]
    flat.sort(key=lambda r: Fraction(r.get("event_time", 0)))
    return flat


def age_chain(rsrc: str, end_target: Fraction, start_dev: int = 1
              ) -> tuple[list[dict[str, Any]], int]:
    """Engine-realistic equipment-age chain: consecutive 2.5 h fragments of
    DISTINCT devices (one task/attempt per fragment, back-to-back so the
    resource is never idle between fragments), each with entry, release,
    ACTIVITY_START, ACTIVITY_COMPLETE, PASS observation.  Returns
    (records, next_device_id).  Equipment age at time T == T for full
    fragments (sum of elapsed <= T since generation start)."""
    out: list[dict[str, Any]] = []
    t = Fraction(0)
    dev = start_dev
    while t < end_target:
        e = min(t + Fraction(5, 2), end_target)
        out.extend(true_state([dev]))
        out.append(release(dev, rsrc, str(t)))
        out.append(start(dev, rsrc, str(t), str(e)))
        out.append(complete(dev, rsrc, str(e), str(t)))
        out.append(obs(dev, rsrc, str(e)))
        t = e
        dev += 1
    return out, dev


# ---------------------------------------------------------------------------
# Checker's OWN log-prefix state logic (independent of the analyzer)
#
# Q3-H2-DENSITY-E2 (fragment-aware requalification): the same
# (device, process, effective_attempt_no) may own SEVERAL physical
# fragments (equipment-failure / illegal-240 interruption -> TASK_CANCEL ->
# task requeue with the frozen FCFS key -> later ACTIVITY_START).
# Fragment identity MUST include attempt_start_time; a fragment is settled
# only by a COMPLETE/CANCEL with the SAME attempt_start_time.  The analyzer
# helpers are NEVER used as oracle.
# ---------------------------------------------------------------------------

DUR = {"A": Fraction(5, 2), "B": Fraction(2), "C": Fraction(5, 2),
       "E": Fraction(3)}


def prefix(log: list[dict[str, Any]], t: Fraction) -> list[dict[str, Any]]:
    return [r for r in log if Fraction(r.get("event_time", 0)) <= t]


def prefix_fragment_settled(log: list[dict[str, Any]], device: int,
                            process: str, attempt: int,
                            fragment_start_time: Fraction, t: Fraction) -> bool:
    """Checker's own fragment-specific settle test: only a COMPLETE/CANCEL
    with the SAME (device, process, attempt, attempt_start_time) and
    event_time <= t settles this exact fragment."""
    pre = prefix(log, t)
    for r in pre:
        if r.get("event_type") not in ("ACTIVITY_COMPLETE", "TASK_CANCEL"):
            continue
        if r.get("attempt_start_time") is None:
            continue
        if (r.get("device_id") == device and r.get("process") == process
                and r.get("effective_attempt_no") == attempt
                and Fraction(r["attempt_start_time"]) == fragment_start_time):
            return True
    return False


def prefix_running(log: list[dict[str, Any]], device: int, process: str,
                   attempt: int, t: Fraction) -> bool:
    """Checker's own fragment-aware running test: exists a FRAGMENT of the
    exact task with start s <= t < scheduled end and NO fragment-specific
    settle <= t (a settle of an OLD fragment never settles a NEW one)."""
    pre = prefix(log, t)
    for r in pre:
        if r.get("event_type") != "ACTIVITY_START":
            continue
        if (r.get("device_id") != device or r.get("process") != process
                or r.get("effective_attempt_no") != attempt):
            continue
        s = Fraction(r.get("attempt_start_time", r["event_time"]))
        end = Fraction(r["attempt_end_time"])
        if s <= t < end and not prefix_fragment_settled(
                log, device, process, attempt, s, t):
            return True
    return False


# -- index core (built once per log; fragment-aware; own implementation) ---


@dataclass
class _TaskRec:
    dev: int
    proc: str
    att: int
    rel: Fraction
    terminal_t: Optional[Fraction] = None
    starts: list[tuple[Fraction, Fraction]] = None  # (start, end) sorted
    completes: list[tuple[Fraction, Fraction]] = None  # (t, start) sorted
    cancels: list[tuple[Fraction, Fraction]] = None  # (t, start) sorted

    def __post_init__(self) -> None:
        if self.starts is None:
            self.starts = []
        if self.completes is None:
            self.completes = []
        if self.cancels is None:
            self.cancels = []


@dataclass
class PrefixIndex:
    log: list[dict[str, Any]]
    entry_dev: dict[int, Fraction] = field(default_factory=dict)  # dev -> entry t
    terminal_t: dict[int, Fraction] = field(default_factory=dict)
    obs_passed: list[tuple[Fraction, int, str]] = field(default_factory=list)
    obs_passed_times: list[Fraction] = field(default_factory=list)
    tasks: dict[str, dict[tuple[int, str, int], _TaskRec]] = field(
        default_factory=dict)
    cal_windows: dict[str, list[tuple[Fraction, Fraction]]] = field(
        default_factory=dict)  # calibration busy [cs, ce)
    unavail_windows: dict[str, list[tuple[Fraction, Fraction]]] = field(
        default_factory=dict)  # replacement/deferral pending [w0, w1)
    replacements: dict[str, list[Fraction]] = field(default_factory=dict)
    dispatch_at: dict[Fraction, set[str]] = field(default_factory=dict)
    event_times: list[Fraction] = field(default_factory=list)
    batch_end: Fraction = Fraction(0)


def build_prefix_index(log: list[dict[str, Any]]) -> PrefixIndex:
    idx = PrefixIndex(log=log)
    terminal_candidates: dict[int, Fraction] = {}
    times: set[Fraction] = set()
    for r in log:
        et = r.get("event_type")
        t = Fraction(r.get("event_time", 0))
        times.add(t)
        if et == "TRUE_STATE_GENERATED":
            d = r["device_id"]
            if d not in idx.entry_dev or t < idx.entry_dev[d]:
                idx.entry_dev[d] = t
        elif et == "DEVICE_TERMINAL":
            d = r["device_id"]
            if d not in terminal_candidates or t < terminal_candidates[d]:
                terminal_candidates[d] = t
        elif et == "OBSERVATION_MATERIALIZED" and r.get("outcome") == "PASS":
            idx.obs_passed.append((t, r["device_id"], r["process"]))
        elif et == "TASK_RELEASE":
            rsrc = r["resource_id"]
            key = (r["device_id"], r["process"], r["effective_attempt_no"])
            rec = idx.tasks.setdefault(rsrc, {}).get(key)
            if rec is None:
                rec = _TaskRec(dev=r["device_id"], proc=r["process"],
                               att=r["effective_attempt_no"], rel=t)
                idx.tasks.setdefault(rsrc, {})[key] = rec
            else:
                rec.rel = min(rec.rel, t)
        elif et == "ACTIVITY_START":
            rsrc = r["resource_id"]
            s = Fraction(r.get("attempt_start_time", r["event_time"]))
            end = Fraction(r["attempt_end_time"])
            key = (r["device_id"], r["process"], r["effective_attempt_no"])
            rec = idx.tasks.setdefault(rsrc, {}).get(key)
            if rec is None:
                rec = _TaskRec(dev=r["device_id"], proc=r["process"],
                               att=r["effective_attempt_no"], rel=s)
                idx.tasks.setdefault(rsrc, {})[key] = rec
            rec.starts.append((s, end))
            idx.dispatch_at.setdefault(t, set()).add(rsrc)
        elif et == "ACTIVITY_COMPLETE":
            rsrc = r["resource_id"]
            if r.get("attempt_start_time") is None:
                continue
            s = Fraction(r["attempt_start_time"])
            key = (r["device_id"], r["process"], r["effective_attempt_no"])
            rec = idx.tasks.setdefault(rsrc, {}).get(key)
            if rec is None:
                rec = _TaskRec(dev=r["device_id"], proc=r["process"],
                               att=r["effective_attempt_no"], rel=s)
                idx.tasks.setdefault(rsrc, {})[key] = rec
            rec.completes.append((t, s))
        elif et == "TASK_CANCEL":
            rsrc = r["resource_id"]
            # A READY-task cancel (device exit, no runtime fragment) carries
            # NO attempt_start_time and contributes ZERO equipment elapsed;
            # only fragment cancels (attempt_start_time present) are stored
            # (E2 fragment identity; the analyzer skips start-less records).
            if r.get("attempt_start_time") is None:
                continue
            s = Fraction(r["attempt_start_time"])
            key = (r["device_id"], r["process"], r["effective_attempt_no"])
            rec = idx.tasks.setdefault(rsrc, {}).get(key)
            if rec is None:
                rec = _TaskRec(dev=r["device_id"], proc=r["process"],
                               att=r["effective_attempt_no"], rel=s)
                idx.tasks.setdefault(rsrc, {})[key] = rec
            rec.cancels.append((t, s))
        elif et == "EQUIPMENT_REPLACEMENT_START":
            rsrc = r["resource_id"]
            cs = Fraction(r["calibration_start"])
            ce = Fraction(r["calibration_end"])
            idx.cal_windows.setdefault(rsrc, []).append((cs, ce))
            idx.unavail_windows.setdefault(rsrc, []).append((t, ce))
            idx.replacements.setdefault(rsrc, []).append(t)
        elif et == "EQUIPMENT_REPLACEMENT_DEFERRED":
            rsrc = r["resource_id"]
            idx.unavail_windows.setdefault(rsrc, []).append(
                (t, t))  # merged with the next replacement's ce below
    # terminal times (earliest)
    idx.terminal_t = terminal_candidates
    # merge unavailability windows per resource (deferral -> next ce)
    for rsrc in list(idx.unavail_windows):
        wins = sorted(idx.unavail_windows[rsrc])
        merged: list[tuple[Fraction, Fraction]] = []
        for w0, w1 in wins:
            if w1 <= w0:
                # deferral-only marker; find next replacement's ce
                nxt = None
                for q0, q1 in wins:
                    if q0 >= w0 and q1 > q0:
                        if nxt is None or q1 < nxt:
                            nxt = q1
                if nxt is not None:
                    w1 = nxt
                else:
                    continue
            if merged and w0 < merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], w1))
            else:
                merged.append((w0, w1))
        idx.unavail_windows[rsrc] = merged
    for rsrc in list(idx.tasks):
        for key in idx.tasks[rsrc]:
            rec = idx.tasks[rsrc][key]
            rec.starts.sort()
            rec.completes.sort()
            rec.cancels.sort()
    idx.obs_passed.sort()
    idx.obs_passed_times = [t for t, _d, _p in idx.obs_passed]
    idx.event_times = sorted(times)
    idx.batch_end = (
        max(idx.terminal_t.values()) if idx.terminal_t
        else (max(idx.event_times) if idx.event_times else Fraction(0)))
    return idx


def _idx_fragment_settled(idx: PrefixIndex, dev: int, proc: str, att: int,
                          fstart: Fraction, t: Fraction) -> bool:
    rsrc = proc
    rec = idx.tasks.get(rsrc, {}).get((dev, proc, att))
    if rec is None:
        return False
    for ct, s in rec.completes:
        if s == fstart and ct <= t:
            return True
    for ct, s in rec.cancels:
        if s == fstart and ct <= t:
            return True
    return False


def _idx_task_running(idx: PrefixIndex, dev: int, proc: str, att: int,
                      t: Fraction) -> bool:
    rec = idx.tasks.get(proc, {}).get((dev, proc, att))
    if rec is None:
        return False
    for s, end in rec.starts:
        if s <= t < end and not _idx_fragment_settled(idx, dev, proc, att, s, t):
            return True
    return False


def _idx_task_completed(idx: PrefixIndex, dev: int, proc: str, att: int,
                        t: Fraction) -> bool:
    rec = idx.tasks.get(proc, {}).get((dev, proc, att))
    if rec is None:
        return False
    return any(ct <= t for ct, _s in rec.completes)


def _idx_task_waiting(idx: PrefixIndex, dev: int, proc: str, att: int,
                      t: Fraction) -> bool:
    rec = idx.tasks.get(proc, {}).get((dev, proc, att))
    if rec is None:
        return False
    if rec.rel > t:
        return False
    tt = idx.terminal_t.get(dev)
    if tt is not None and tt <= t:
        return False
    if _idx_task_completed(idx, dev, proc, att, t):
        return False
    if _idx_task_running(idx, dev, proc, att, t):
        return False
    return True


def _idx_head(idx: PrefixIndex, resource: str, t: Fraction
              ) -> Optional[tuple[int, str, int]]:
    best = None
    for (dev, proc, att), rec in idx.tasks.get(resource, {}).items():
        if not _idx_task_waiting(idx, dev, proc, att, t):
            continue
        key = (rec.rel, dev, an.PROCESS_ORDER.get(proc, 9), att)
        if best is None or key < best[0]:
            best = (key, dev, proc, att)
    if best is None:
        return None
    return (best[1], best[2], best[3])


def _idx_legal(idx: PrefixIndex, head: tuple[int, str, int], t: Fraction,
               d: Fraction, shift_end: Fraction) -> bool:
    dev, proc, att = head
    tt = idx.terminal_t.get(dev)
    if tt is not None and tt <= t:
        return False
    if proc == "E" and not all(_idx_passed(idx, dev, p, t)
                               for p in ("A", "B", "C")):
        return False
    return t + d <= shift_end


def _idx_idle(idx: PrefixIndex, resource: str, t: Fraction) -> bool:
    for (dev, proc, att), rec in idx.tasks.get(resource, {}).items():
        if _idx_task_running(idx, dev, proc, att, t):
            return False
    for cs, ce in idx.cal_windows.get(resource, []):
        if cs <= t < ce:
            return False
    return True


def _idx_available(idx: PrefixIndex, resource: str, t: Fraction) -> bool:
    for w0, w1 in idx.unavail_windows.get(resource, []):
        if w0 <= t < w1:
            return False
    return True


def _idx_age(idx: PrefixIndex, resource: str, t: Fraction) -> Fraction:
    gen_start = Fraction(0)
    for t0 in idx.replacements.get(resource, []):
        if t0 <= t:
            gen_start = max(gen_start, t0)
    age = Fraction(0)
    for (dev, proc, att), rec in idx.tasks.get(resource, {}).items():
        for ct, s in rec.completes:
            if s >= gen_start and ct <= t:
                age += ct - s
        for ct, s in rec.cancels:
            if s >= gen_start and ct <= t:
                age += ct - s
    return age


def prefix_demand(log: list[dict[str, Any]], resource: str, t: Fraction,
                  batch_size: int) -> bool:
    """Checker's own future-potential-demand at t from the log PREFIX
    (<= t) only: entered-at-t, non-terminal-at-t, not-passed-at-t, or
    batch not fully entered."""
    pre = prefix(log, t)
    entered = {r["device_id"] for r in pre
               if r.get("event_type") == "TRUE_STATE_GENERATED"}
    terminal_devs = {r["device_id"] for r in pre
                     if r.get("event_type") == "DEVICE_TERMINAL"}
    passed = {(r["device_id"], r["process"]) for r in pre
              if r.get("event_type") == "OBSERVATION_MATERIALIZED"
              and r.get("outcome") == "PASS"}
    for dev in entered - terminal_devs:
        if (dev, resource) not in passed:
            return True
    return len(entered) < batch_size


def _idx_passed(idx: PrefixIndex, dev: int, proc: str, t: Fraction) -> bool:
    import bisect
    lo = bisect.bisect_right(idx.obs_passed_times, t)
    for i in range(lo - 1, -1, -1):
        ot, d, p = idx.obs_passed[i]
        if d == dev and p == proc:
            return True
        if i == 0:
            break
    return False


def _idx_demand_idx(idx: PrefixIndex, resource: str, t: Fraction,
                    batch_size: int) -> bool:
    """Index-based demand (identical semantics to prefix_demand): entered
    at t, non-terminal at t, not passed at t, or batch not fully entered."""
    entered = {d for d, et in idx.entry_dev.items() if et <= t}
    for dev in entered:
        tt = idx.terminal_t.get(dev)
        if tt is not None and tt <= t:
            continue
        if not _idx_passed(idx, dev, resource, t):
            return True
    return len(entered) < batch_size


def prefix_head_waiting(log: list[dict[str, Any]], resource: str, t: Fraction
                        ) -> bool:
    """Checker's own waiting-head test at t from the log PREFIX:
    fragment-aware (a requeued task between cancel and restart is waiting;
    a running fragment is never waiting)."""
    idx = build_prefix_index(log)
    return _idx_head(idx, resource, t) is not None


def prefix_legal_head(log: list[dict[str, Any]], resource: str, t: Fraction,
                      shift_end: Fraction) -> bool:
    """Checker's own time-causal legality of the FCFS head at t (device
    non-terminal, E prereq by PASS observation <= t, duration fits;
    fragment-aware waiting)."""
    idx = build_prefix_index(log)
    head = _idx_head(idx, resource, t)
    if head is None:
        return False
    return _idx_legal(idx, head, t, DUR[head[1]], shift_end)


def prefix_idle(log: list[dict[str, Any]], resource: str, t: Fraction) -> bool:
    """Checker's own idle test at t (fragment-aware: only the exact
    in-flight fragment with no fragment-specific settle makes it busy)."""
    idx = build_prefix_index(log)
    return _idx_idle(idx, resource, t)


def prefix_available(log: list[dict[str, Any]], resource: str, t: Fraction
                     ) -> bool:
    """Checker's own equipment-availability test at t (replacement /
    deferral pending windows)."""
    idx = build_prefix_index(log)
    return _idx_available(idx, resource, t)


def prefix_age(log: list[dict[str, Any]], resource: str, t: Fraction) -> Fraction:
    """Checker's own equipment age at t from the log PREFIX (fragments
    ending <= t since the latest replacement start <= t)."""
    idx = build_prefix_index(log)
    return _idx_age(idx, resource, t)


def prefix_maintenance_counts(log: list[dict[str, Any]], K: Fraction,
                              batch_size: int) -> tuple[int, int, int]:
    """Checker's OWN independent PM_IDLE (maintenance point) enumeration
    over the reconstructed closure set (distinct canonical event times +
    Q3 shift starts), fragment-aware, with dispatch-closure skip and
    equipment availability.  Returns (pm_idle, queue_empty_pm_idle,
    queue_nonempty_no_legal_head_pm_idle).  Never calls the analyzer's
    maintenance helpers."""
    idx = build_prefix_index(log)
    shifts: list[tuple[Fraction, Fraction]] = []
    for d in range(400):
        s1 = Fraction(24) * d
        shifts.append((s1, s1 + K))
        shifts.append((s1 + K, s1 + 2 * K))
    pm_idle = 0
    q_empty = 0
    q_nonempty = 0
    for t in sorted(set(idx.event_times) | {s for s, _e in shifts}):
        if t >= idx.batch_end:
            continue
        sh = None
        for s, e in shifts:
            if s <= t < e:
                sh = (s, e)
                break
        if sh is None:
            continue
        for rsrc in ("A", "B", "C", "E"):
            if rsrc in idx.dispatch_at.get(t, ()):
                continue
            if not _idx_idle(idx, rsrc, t):
                continue
            if not _idx_available(idx, rsrc, t):
                continue
            head = _idx_head(idx, rsrc, t)
            if head is not None and _idx_legal(idx, head, t,
                                               DUR[head[1]], sh[1]):
                continue
            age = _idx_age(idx, rsrc, t)
            if not (an.MIN_PREVENTIVE_AGE_H <= age < an.MANDATORY_AGE_H):
                continue
            cal = an.CALIBRATION_MINUTES[rsrc] / Fraction(60)
            if t + cal > sh[1]:
                continue
            if not _idx_demand_idx(idx, rsrc, t, batch_size):
                continue
            pm_idle += 1
            if head is None:
                q_empty += 1
            else:
                q_nonempty += 1
    return pm_idle, q_empty, q_nonempty


def prefix_maintenance_count(log: list[dict[str, Any]], K: Fraction,
                             batch_size: int) -> int:
    """Total PM_IDLE count (back-compat wrapper)."""
    return prefix_maintenance_counts(log, K, batch_size)[0]


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------


def case1_strict() -> tuple[list[dict[str, Any]], Fraction]:
    """STRICT (K=12): device1 A in flight (0..2.5), B starts at 1, ends 3;
    latest_start(B) = 12-2 = 10; e(A) = 2.5 < 10 -> STRICT."""
    return synthetic_log([
        true_state([1]),
        release(1, "A", "0"), release(1, "B", "0"),
        start(1, "A", "0", "5/2"), complete(1, "A", "5/2", "0"),
        obs(1, "A", "5/2"),
        start(1, "B", "1", "3"), complete(1, "B", "3", "1"),
        obs(1, "B", "3"),
    ]), Fraction(12)


def case2_boundary() -> tuple[list[dict[str, Any]], Fraction]:
    """BOUNDARY (e == latest_start): K=9, A in flight ending 7; B starts at
    1: latest_start(B)=9-2=7; e(A)=7 == 7 -> BOUNDARY legal WAIT."""
    return synthetic_log([
        true_state([1]),
        release(1, "A", "0"), release(1, "B", "0"),
        start(1, "A", "0", "7"), complete(1, "A", "7", "0"),
        obs(1, "A", "7"),
        start(1, "B", "1", "3"), complete(1, "B", "3", "1"),
        obs(1, "B", "3"),
    ]), Fraction(9)


def case3_nonstrict_not_legal() -> tuple[list[dict[str, Any]], Fraction]:
    """NONSTRICT-only when e > latest_start (NOT a legal wait): K=9, A in
    flight ending 8; B at 1: latest_start(B)=7; e=8 > 7 -> no wait."""
    return synthetic_log([
        true_state([1]),
        release(1, "A", "0"), release(1, "B", "0"),
        start(1, "A", "0", "8"), complete(1, "A", "8", "0"),
        obs(1, "A", "8"),
        start(1, "B", "1", "3"), complete(1, "B", "3", "1"),
        obs(1, "B", "3"),
    ]), Fraction(9)


def case4_pm_with_head() -> tuple[list[dict[str, Any]], Fraction]:
    """PM_WITH_HEAD at a dispatch point: A fragments to age exactly 120,
    then an A dispatch at t=120 (a+d = 122.5 < 240) -> optional
    PM_WITH_HEAD (meaningful)."""
    records, next_dev = age_chain("A", Fraction(120), start_dev=1)
    d = next_dev  # 49
    return synthetic_log([
        true_state([d]),
        records,
        release(d, "A", "120"), start(d, "A", "120", "245/2"),
        complete(d, "A", "245/2", "120"), obs(d, "A", "245/2"),
    ]), Fraction(240)


def case5_pm_idle_queue_empty() -> tuple[list[dict[str, Any]], Fraction]:
    """queue-empty PM_IDLE (maintenance point): A fragments to age 120;
    resource idle at t=120 with NO waiting head; device `next_dev` keeps
    the batch alive past 120 (entered, not yet passed -> future demand)."""
    records, next_dev = age_chain("A", Fraction(120), start_dev=2)
    d = next_dev  # 50
    return synthetic_log([
        true_state([d]),
        records,
        release(d, "A", "121"), start(d, "A", "121", "247/2"),
        complete(d, "A", "247/2", "121"), obs(d, "A", "247/2"),
    ]), Fraction(240)


def case6_pm_idle_forced_wait() -> tuple[list[dict[str, Any]], Fraction]:
    """queue-nonempty but NO legal head (forced wait) -> maintenance
    PM_IDLE: A fragments to age 120, an A release at t=120 cannot legally
    start (120+2.5 = 122.5 > shift_end 121) -> forced wait; not mandatory;
    cal fits -> pm_idle = 1.  device `next_dev` keeps the batch alive."""
    records, next_dev = age_chain("A", Fraction(120), start_dev=10)
    alive = next_dev  # 58
    return synthetic_log([
        true_state([3, alive]),
        records,
        release(3, "A", "120"),
        release(alive, "A", "121"), start(alive, "A", "121", "247/2"),
        complete(alive, "A", "247/2", "121"), obs(alive, "A", "247/2"),
    ]), Fraction(121)


def case7_exact_240() -> tuple[list[dict[str, Any]], Fraction]:
    """a + d == 240 -> exact_240 (NOT optional PM): age exactly 237.5,
    d = 2.5 at the final dispatch anchor (device `next_dev`)."""
    records, next_dev = age_chain("A", Fraction(475, 2), start_dev=1)
    d = next_dev  # 96
    return synthetic_log([
        true_state([d]),
        records,
        release(d, "A", "475/2"), start(d, "A", "475/2", "240"),
        complete(d, "A", "240", "475/2"), obs(d, "A", "240"),
    ]), Fraction(300)


def case8_mandatory() -> tuple[list[dict[str, Any]], Fraction]:
    """mandatory pre-start replacement: chain to age 238 (partial last
    fragment), then EQUIPMENT_REPLACEMENT_START kind=mandatory_240
    trigger=a_plus_d_gt_240 at t=238 (the head could never start:
    a+d = 240.5 > 240), then a fresh post-replacement dispatch at 240."""
    records, next_dev = age_chain("A", Fraction(238), start_dev=1)
    d = next_dev  # 97
    return synthetic_log([
        true_state([d]),
        records,
        replacement_start("A", "238", "mandatory_240", "a_plus_d_gt_240"),
        release(d, "A", "240"), start(d, "A", "240", "481/2"),
        complete(d, "A", "481/2", "240"), obs(d, "A", "481/2"),
    ]), Fraction(300)


def case_t1_future_terminal() -> tuple[list[dict[str, Any]], Fraction]:
    """T1 future-terminal contamination: device1 terminal only at 20; at
    t=10 device1 is NON-terminal and demand is TRUE (device2 entered,
    non-terminal, not passed A)."""
    return synthetic_log([
        true_state([1, 2]),
        release(1, "A", "0"), start(1, "A", "0", "5/2"),
        complete(1, "A", "5/2", "0"), obs(1, "A", "5/2"),
        terminal(1, "20"), terminal(2, "30"),
    ]), Fraction(240)


def case_t2_future_pass() -> tuple[list[dict[str, Any]], Fraction]:
    """T2 future-PASS contamination: A/B/C PASS observations only at 20; at
    t=10 NONE is passed (E prereq must fail at t=10); at t=25 all three are
    passed -> E head legal."""
    return synthetic_log([
        true_state([1]),
        release(1, "A", "0"), start(1, "A", "0", "5/2"),
        complete(1, "A", "5/2", "0"),
        release(1, "B", "0"), start(1, "B", "0", "2"),
        complete(1, "B", "2", "0"),
        release(1, "C", "0"), start(1, "C", "0", "5/2"),
        complete(1, "C", "5/2", "0"),
        obs(1, "A", "20"), obs(1, "B", "20"), obs(1, "C", "20"),
        release(1, "E", "10"),
    ]), Fraction(300)


def case_t3_future_release() -> tuple[list[dict[str, Any]], Fraction]:
    """T3 future-release contamination: release at 10 must NOT enter the
    queue at t=5."""
    return synthetic_log([
        true_state([1]),
        release(1, "A", "10"),
    ]), Fraction(240)


def case_t4_delayed_start() -> tuple[list[dict[str, Any]], Fraction]:
    """T4 delayed-start stale waiting: release=0, start=5; at t=1 the task
    is WAITING, at t=6 it is RUNNING (not waiting)."""
    return synthetic_log([
        true_state([1]),
        release(1, "A", "0"), start(1, "A", "5", "8"),
    ]), Fraction(240)


def case_t5_completed_full_log_pm_idle() -> tuple[list[dict[str, Any]], Fraction]:
    """T5 completed full-log PM_IDLE: the log CONTAINS final DEVICE_TERMINAL
    records (all devices terminal at 121); at t=120 the resource is idle,
    age = 120, no head, and future demand is still TRUE (device `next_dev`
    entered but not yet passed, non-terminal at 120).  OLD bug: final
    terminals suppressed pm_idle to 0; correct: 1.  batch_end = 121 so the
    t=120 maintenance point is the only one."""
    records, next_dev = age_chain("A", Fraction(120), start_dev=1)
    devs = list(range(1, next_dev + 1))  # 1..49 (49 entered, not all passed)
    return synthetic_log([
        true_state(devs),
        records,
        [terminal(x, "121") for x in devs],
    ]), Fraction(240)


def case_t6_forced_wait_eventual_terminal() -> tuple[list[dict[str, Any]], Fraction]:
    """T6 forced wait with eventual terminal records: B released at 8.5 in
    K=9 (t+d = 10.5 > 9 -> not legal); device terminal only at 100; the
    final terminal set must not erase the forced wait."""
    return synthetic_log([
        true_state([1]),
        release(1, "B", "8.5"),
        terminal(1, "100"),
    ]), Fraction(9)


def case_t7_release_closure() -> tuple[list[dict[str, Any]], Fraction]:
    """T7 TASK_RELEASE closure on idle resource: the ONLY event at 8.5 is
    the release; the closure at 8.5 (neither a busy-end nor a shift-start)
    must classify forced-wait (head cannot start: 8.5+2 > 9).  device2's
    C fragments end at 9 -> batch_end = 9 keeps the 8.5 closure inside the
    batch and excludes the 9 closure."""
    return synthetic_log([
        true_state([1, 2]),
        release(1, "B", "8.5"),
        release(2, "C", "0"), start(2, "C", "0", "3"),
        complete(2, "C", "3", "0"), obs(2, "C", "3"),
        start(2, "C", "3", "6"), complete(2, "C", "6", "3"),
        obs(2, "C", "6"),
        start(2, "C", "6", "9"), complete(2, "C", "9", "6"),
        obs(2, "C", "9"),
    ]), Fraction(9)


def case_t8_mandatory_pre_start() -> tuple[list[dict[str, Any]], Fraction]:
    """T8 mandatory pre-start replacement: same as case8; asserted at the
    classification level (mandatory=1, optional PM=0 at that closure)."""
    return case8_mandatory()


def case_t9_exact_240() -> tuple[list[dict[str, Any]], Fraction]:
    """T9 exact_240: same as case7; asserted at classification level."""
    return case7_exact_240()


def case_t10_same_closure_single_point() -> tuple[list[dict[str, Any]], Fraction]:
    """T10 same timestamp / same event closure: at t=120 the dev-A chain
    end has MULTIPLE records (complete + observation) in ONE closure;
    resource A yields exactly ONE maintenance point (pm_idle=1); the B
    fragment (realistic 2 h) completes at t=2 with age 2 (< 120) -> no
    point; no double counting per (resource, closure).  All devices
    terminal at 121 -> batch_end = 121 so later closures are excluded."""
    records, next_dev = age_chain("A", Fraction(120), start_dev=1)
    db = next_dev  # 49: realistic B fragment (0,2)
    devs = list(range(1, next_dev + 1))
    return synthetic_log([
        true_state(devs),
        records,
        release(db, "B", "0"), start(db, "B", "0", "2"),
        complete(db, "B", "2", "0"), obs(db, "B", "2"),
        [terminal(x, "121") for x in devs],
    ]), Fraction(240)


def case_t11_requeue_between_fragments() -> tuple[list[dict[str, Any]], Fraction]:
    """T11 CANCEL -> REQUEUE BETWEEN FRAGMENTS: same task/attempt,
    release=0, fragment1 start=0 end=1, cancel=1 (equipment failure),
    fragment2 start=2 end=4.  At t=1.5 the task is WAITING and the
    resource is IDLE (fragment1 settled, fragment2 not started)."""
    return synthetic_log([
        true_state([1]),
        release(1, "A", "0"),
        start(1, "A", "0", "1"),
        cancel(1, "A", "1", "0"),
        start(1, "A", "2", "4"),
        complete(1, "A", "4", "2"),
    ]), Fraction(240)


def case_t12_restarted_fragment_running() -> tuple[list[dict[str, Any]], Fraction]:
    """T12 RESTARTED FRAGMENT RUNNING: same log; at t=3 fragment2
    (start=2, end=4) is RUNNING -> task NOT waiting, resource BUSY.  The
    OLD fragment1 CANCEL (attempt_start_time=0) must NOT settle fragment2
    (attempt_start_time=2).  This is the Human Gate defect core regression."""
    return case_t11_requeue_between_fragments()


def case_t13_second_fragment_complete() -> tuple[list[dict[str, Any]], Fraction]:
    """T13 SECOND FRAGMENT COMPLETE: fragment2 completes at t=4
    (attempt_start_time=2) -> task completed, NOT waiting, resource IDLE."""
    return case_t11_requeue_between_fragments()


def case_t14_pm_idle_false_during_restart() -> tuple[list[dict[str, Any]], Fraction]:
    """T14 PM_IDLE FALSE DURING RESTARTED FRAGMENT: equipment age >= 120
    (age chain), future demand TRUE (device 60 entered, non-terminal, not
    passed); same effective attempt has fragment1 cancelled and fragment2
    currently running.  During fragment2 the resource is BUSY -> PM_IDLE
    MUST be 0 (checker computes this from its own prefix idle logic)."""
    records, next_dev = age_chain("A", Fraction(120), start_dev=1)
    d60 = 60
    return synthetic_log([
        true_state([d60]),
        records,
        release(d60, "A", "120"),
        start(d60, "A", "120", "121"),
        cancel(d60, "A", "121", "120"),
        start(d60, "A", "122", "124"),
        complete(d60, "A", "124", "122"),
    ]), Fraction(240)


def case_t15_post_cancel_head() -> tuple[list[dict[str, Any]], Fraction]:
    """T15 POST-CANCEL LEGAL/ILLEGAL HEAD: after fragment1 cancel (t=1)
    and before fragment2 restart (t=2), the task must re-enter the FCFS
    waiting set.  (a) shift remaining enough -> legal head TRUE;
    (b) shift remaining insufficient -> legal head FALSE (forced-wait
    state)."""
    return case_t11_requeue_between_fragments()


# ---------------------------------------------------------------------------
# Checker harness
# ---------------------------------------------------------------------------


def analyzer_counts(log: list[dict[str, Any]], K: Fraction) -> dict[str, int]:
    s = an.classify_batch_q3(log, K, "KCK", "9", 0, batch_size=2)
    return {
        "legal_dispatch": s.legal_dispatch_decision_points,
        "strict": s.strategic_strict,
        "boundary": s.strategic_boundary,
        "nonstrict": s.strategic_nonstrict,
        "pm_head": s.pm_with_head,
        "pm_idle": s.pm_idle,
        "queue_empty_pm_idle": s.queue_empty_pm_idle,
        "queue_nonempty_pm_idle": s.queue_nonempty_no_legal_head_pm_idle,
        "maintenance_points": s.maintenance_decision_points,
        "forced_wait": s.forced_wait,
        "mandatory": s.mandatory_replacement,
        "mandatory_a_plus_d": s.mandatory_a_plus_d_gt_240,
        "exact_240": s.exact_240,
        "both": s.both_wait_and_pm,
        "meaningful": s.meaningful_h2_choice,
        "mandatory_dispatch_diag": s.mandatory_at_dispatch_diagnostic,
    }


def expect(failures: list[str], name: str, got: dict[str, int],
           expected: dict[str, int]) -> None:
    for key, exp in expected.items():
        if got[key] != exp:
            failures.append(f"{name}: {key} expected {exp} got {got[key]}")


def run_checks() -> list[str]:
    failures: list[str] = []

    # C1 STRICT
    log1, K1 = case1_strict()
    got1 = analyzer_counts(log1, K1)
    expect(failures, "STRICT", got1,
           {"legal_dispatch": 2, "strict": 1, "boundary": 0,
            "nonstrict": 1, "meaningful": 1})

    # C2 BOUNDARY
    log2, K2 = case2_boundary()
    expect(failures, "BOUNDARY", analyzer_counts(log2, K2),
           {"legal_dispatch": 2, "strict": 0, "boundary": 1, "nonstrict": 1,
            "meaningful": 1})

    # C3 NONSTRICT-not-legal
    log3, K3 = case3_nonstrict_not_legal()
    expect(failures, "NONSTRICT-not-legal", analyzer_counts(log3, K3),
           {"legal_dispatch": 2, "strict": 0, "boundary": 0, "nonstrict": 0,
            "meaningful": 0})

    # C4 PM_WITH_HEAD
    log4, K4 = case4_pm_with_head()
    expect(failures, "PM_WITH_HEAD", analyzer_counts(log4, K4),
           {"pm_head": 1, "meaningful": 1, "pm_idle": 0})

    # C5 PM_IDLE queue-empty (independent prefix confirmation)
    log5, K5 = case5_pm_idle_queue_empty()
    expect(failures, "PM_IDLE-queue-empty", analyzer_counts(log5, K5),
           {"pm_idle": 1, "queue_empty_pm_idle": 1})
    if not prefix_demand(log5, "A", Fraction(120), 2):
        failures.append("PM_IDLE-queue-empty: checker prefix demand at 120 must be True")

    # C6 PM_IDLE forced-wait
    log6, K6 = case6_pm_idle_forced_wait()
    expect(failures, "PM_IDLE-forced-wait", analyzer_counts(log6, K6),
           {"pm_idle": 1, "forced_wait": 1, "queue_nonempty_pm_idle": 1})

    # C7 exact_240 (chain anchors age>=120; final anchor a+d==240)
    log7, K7 = case7_exact_240()
    got7 = analyzer_counts(log7, K7)
    n7 = 95
    pm7 = sum(1 for k in range(n7)
              if Fraction(120) <= Fraction(5, 2) * k
              and Fraction(5, 2) * k + Fraction(5, 2) < Fraction(240))
    expect(failures, "exact-240", got7,
           {"exact_240": 1, "mandatory": 0, "pm_head": pm7, "pm_idle": 0})

    # C8 mandatory (kind=mandatory_240 replacement, pre-start)
    log8, K8 = case8_mandatory()
    got8 = analyzer_counts(log8, K8)
    n8 = 96
    pm8 = sum(1 for k in range(n8)
              if Fraction(120) <= Fraction(5, 2) * k
              and Fraction(5, 2) * k + Fraction(5, 2) < Fraction(240))
    expect(failures, "mandatory", got8,
           {"mandatory": 1, "mandatory_a_plus_d": 1, "exact_240": 1,
            "pm_head": pm8, "pm_idle": 0, "mandatory_dispatch_diag": 0})

    # T1 future-terminal contamination
    logt1, Kt1 = case_t1_future_terminal()
    view_t1 = an.build_time_index(logt1)
    if an.terminal_at_or_before(view_t1, 1, Fraction(10)):
        failures.append("T1: dev1 must be NON-terminal at t=10 (terminal only at 20)")
    if not an.terminal_at_or_before(view_t1, 1, Fraction(20)):
        failures.append("T1: dev1 must be terminal at t=20")
    if not an.future_potential_demand_at(view_t1, "A", Fraction(10), batch_size=2):
        failures.append("T1: future demand at t=10 must be True (dev1 non-terminal at 10)")
    if not prefix_demand(logt1, "A", Fraction(10), 2):
        failures.append("T1: checker prefix demand at 10 must be True")

    # T2 future-PASS contamination
    logt2, Kt2 = case_t2_future_pass()
    view_t2 = an.build_time_index(logt2)
    if an.process_passed_at_or_before(view_t2, 1, "A", Fraction(10)):
        failures.append("T2: A must NOT be passed at t=10 (PASS obs at 20)")
    if not an.process_passed_at_or_before(view_t2, 1, "A", Fraction(25)):
        failures.append("T2: A must be passed at t=25")
    # E prereq legality: at t=10 E head (released at 10) is ILLEGAL
    if an.head_is_legal_at(view_t2, (1, "E", 1), Fraction(10),
                           Fraction(3), Fraction(300)):
        failures.append("T2: E head must be ILLEGAL at t=10 (A not passed yet)")
    if not an.head_is_legal_at(view_t2, (1, "E", 1), Fraction(25),
                               Fraction(3), Fraction(300)):
        failures.append("T2: E head must be LEGAL at t=25 (A passed at 20)")

    # T3 future-release contamination
    logt3, Kt3 = case_t3_future_release()
    view_t3 = an.build_time_index(logt3)
    if an.fcfs_head_at(view_t3, "A", Fraction(5)) is not None:
        failures.append("T3: future release at t=10 must NOT appear at t=5")
    if an.waiting_tasks_at(view_t3, "A", Fraction(5)):
        failures.append("T3: no waiting tasks at t=5")
    head5 = an.fcfs_head_at(view_t3, "A", Fraction(10))
    if head5 != (1, "A", 1):
        failures.append(f"T3: at t=10 head must be (1,A,1), got {head5}")

    # T4 delayed-start stale waiting
    logt4, Kt4 = case_t4_delayed_start()
    view_t4 = an.build_time_index(logt4)
    if an.fcfs_head_at(view_t4, "A", Fraction(1)) != (1, "A", 1):
        failures.append("T4: at t=1 the released task must be WAITING (head present)")
    if an.fcfs_head_at(view_t4, "A", Fraction(6)) is not None:
        failures.append("T4: at t=6 the started task must be RUNNING, not waiting")
    if not prefix_head_waiting(logt4, "A", Fraction(1)):
        failures.append("T4: checker prefix: task waiting at t=1")
    if prefix_head_waiting(logt4, "A", Fraction(6)):
        failures.append("T4: checker prefix: task NOT waiting at t=6")

    # T5 completed full-log PM_IDLE (old bug reproduction at the new code:
    # must be 1; OLD analyzer gave 0)
    logt5, Kt5 = case_t5_completed_full_log_pm_idle()
    got_t5 = analyzer_counts(logt5, Kt5)
    expect(failures, "T5-completed-full-log-PM_IDLE", got_t5,
           {"pm_idle": 1, "queue_empty_pm_idle": 1, "meaningful": 0})
    if not prefix_demand(logt5, "A", Fraction(120), 2):
        failures.append("T5: checker prefix demand at 120 must be True "
                        "(device1 terminal only at 121)")
    if prefix_maintenance_count(logt5, Kt5, 2) != 1:
        failures.append("T5: checker independent maintenance count must be 1")

    # T6 forced wait with eventual terminal records
    logt6, Kt6 = case_t6_forced_wait_eventual_terminal()
    got_t6 = analyzer_counts(logt6, Kt6)
    expect(failures, "T6-forced-wait-eventual-terminal", got_t6,
           {"forced_wait": 1, "pm_idle": 0})
    if not prefix_head_waiting(logt6, "B", Fraction(8.5)):
        failures.append("T6: checker prefix: B task waiting at 8.5")

    # T7 TASK_RELEASE closure on idle resource
    logt7, Kt7 = case_t7_release_closure()
    view_t7 = an.build_time_index(logt7)
    if Fraction(17, 2) not in an.closure_times(view_t7, an.q3_shift_grid(Kt7)):
        failures.append("T7: release time 8.5 must be a closure time")
    got_t7 = analyzer_counts(logt7, Kt7)
    expect(failures, "T7-release-closure", got_t7, {"forced_wait": 1})

    # T8 mandatory pre-start replacement
    logt8, Kt8 = case_t8_mandatory_pre_start()
    got_t8 = analyzer_counts(logt8, Kt8)
    expect(failures, "T8-mandatory-pre-start", got_t8,
           {"mandatory": 1, "mandatory_a_plus_d": 1})

    # T9 exact_240
    logt9, Kt9 = case_t9_exact_240()
    got_t9 = analyzer_counts(logt9, Kt9)
    expect(failures, "T9-exact-240", got_t9, {"exact_240": 1, "mandatory": 0})

    # T10 same timestamp single decision point per resource
    logt10, Kt10 = case_t10_same_closure_single_point()
    got_t10 = analyzer_counts(logt10, Kt10)
    expect(failures, "T10-same-closure-single-point", got_t10,
           {"pm_idle": 1, "queue_empty_pm_idle": 1})
    if prefix_maintenance_count(logt10, Kt10, 2) != 1:
        failures.append("T10: checker independent maintenance count must be 1")

    # --- Q3-H2-DENSITY-E2 fragment/requeue regressions (T11-T15) ---
    logt11, Kt11 = case_t11_requeue_between_fragments()
    # T11: between cancel and restart -> WAITING, resource IDLE
    if not prefix_head_waiting(logt11, "A", Fraction(3, 2)):
        failures.append("T11: task must be WAITING at t=1.5 (between cancel "
                        "and restart)")
    if not prefix_idle(logt11, "A", Fraction(3, 2)):
        failures.append("T11: resource must be IDLE at t=1.5")
    if not prefix_fragment_settled(logt11, 1, "A", 1, Fraction(0), Fraction(3, 2)):
        failures.append("T11: fragment1 (start 0) must be settled at t=1.5")

    # T12: restarted fragment RUNNING (old fragment's CANCEL must not
    # settle the new fragment) -> NOT waiting, resource BUSY
    if prefix_head_waiting(logt11, "A", Fraction(3)):
        failures.append("T12: task must NOT be waiting at t=3 (fragment2 "
                        "running)")
    if prefix_idle(logt11, "A", Fraction(3)):
        failures.append("T12: resource must be BUSY at t=3 (fragment2 "
                        "running); old fragment1 CANCEL must not settle "
                        "fragment2")
    if prefix_fragment_settled(logt11, 1, "A", 1, Fraction(2), Fraction(3)):
        failures.append("T12: fragment2 (start 2) must NOT be settled at "
                        "t=3 by fragment1's CANCEL")
    if not prefix_running(logt11, 1, "A", 1, Fraction(3)):
        failures.append("T12: fragment2 must be RUNNING at t=3")
    # analyzer side (system under test): fragment-aware idle at t=3
    s12 = an.classify_batch_q3(logt11, Kt11, "KCK", "9", 0, batch_size=2)
    if s12.pm_idle != 0:
        failures.append("T12: analyzer pm_idle must be 0 (resource busy at "
                        "t=3)")

    # T13: second fragment COMPLETE -> completed, NOT waiting, IDLE
    if not prefix_fragment_settled(logt11, 1, "A", 1, Fraction(2), Fraction(4)):
        failures.append("T13: fragment2 (start 2) must be settled at t=4 by "
                        "its own COMPLETE")
    if prefix_head_waiting(logt11, "A", Fraction(4)):
        failures.append("T13: task must NOT be waiting at t=4 (completed)")
    if not prefix_idle(logt11, "A", Fraction(4)):
        failures.append("T13: resource must be IDLE at t=4")

    # T14: PM_IDLE MUST be 0 while the restarted fragment runs (resource
    # BUSY despite age >= 120 and demand TRUE); expected truth computed by
    # the checker's own prefix idle logic.
    logt14, Kt14 = case_t14_pm_idle_false_during_restart()
    if prefix_idle(logt14, "A", Fraction(123)):
        failures.append("T14: resource must be BUSY at t=123 (fragment2 "
                        "running) -> PM_IDLE impossible")
    if prefix_head_waiting(logt14, "A", Fraction(123)):
        failures.append("T14: task must NOT be waiting at t=123 (fragment2 "
                        "running)")
    if not prefix_demand(logt14, "A", Fraction(123), 2):
        failures.append("T14: checker prefix demand must be TRUE at t=123")
    m14 = prefix_maintenance_counts(logt14, Kt14, 2)
    if m14[0] != 0:
        failures.append(f"T14: checker PM_IDLE must be 0 during restarted "
                        f"fragment, got {m14}")
    s14 = an.classify_batch_q3(logt14, Kt14, "KCK", "9", 0, batch_size=2)
    if s14.pm_idle != 0:
        failures.append("T14: analyzer pm_idle must be 0 during restarted "
                        "fragment")

    # T15: post-cancel legal/illegal FCFS head
    logt15, Kt15 = case_t15_post_cancel_head()
    if not prefix_head_waiting(logt15, "A", Fraction(1)):
        failures.append("T15: task must be the waiting head at t=1 (after "
                        "cancel, before restart)")
    if not prefix_legal_head(logt15, "A", Fraction(1), Fraction(300)):
        failures.append("T15a: head must be LEGAL at t=1 when the shift has "
                        "enough room (1+2.5 <= 300)")
    if prefix_legal_head(logt15, "A", Fraction(1), Fraction(3)):
        failures.append("T15b: head must be ILLEGAL at t=1 when 1+2.5 > 3 "
                        "(forced-wait state)")
    s15 = an.classify_batch_q3(logt15, Fraction(3), "KCK", "9", 0, batch_size=2)
    if s15.forced_wait != 1:
        failures.append(f"T15b: analyzer forced_wait must be 1 at K=3 "
                        f"(head illegal), got {s15.forced_wait}")

    # C9 determinism + frozen canonical resource order A/B/C/E
    s_a = an.classify_batch_q3(log1, K1, "KCK", "9", 0, batch_size=2)
    s_b = an.classify_batch_q3(log1, K1, "KCK", "9", 0, batch_size=2)
    if s_a.to_dict() != s_b.to_dict():
        failures.append("determinism: same log -> different classification")
    if an.RESOURCES != ("A", "B", "C", "E"):
        failures.append("resource order must be frozen A/B/C/E")

    return failures


def main() -> int:
    failures = run_checks()
    if failures:
        print("CHECKER: FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("CHECKER: PASS (8 boundary cases + 15 temporal cases "
          "(T1-T10 + T11-T15 fragment/requeue) + determinism/order)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
