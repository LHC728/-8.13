#!/usr/bin/env python3
"""Q3-H2-DENSITY-E1 independent checker (temporal reconstruction).

The density analyzer must not self-certify.  This checker independently
recomputes the frozen classifications for hand-built deterministic small
cases and cross-checks the analyzer on those same logs.  It does NOT call
the analyzer's classification functions (fcfs_head_at /
future_potential_demand_at / process_passed_at_or_before / classify) as an
oracle: expected values are derived by the checker's OWN log-prefix logic
and hand derivation.  The analyzer is used only as the system under test.

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
  T10 same-timestamp single decision point per resource.

Python 3.12, standard library only.
"""
from __future__ import annotations

import sys
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
# ---------------------------------------------------------------------------

DUR = {"A": Fraction(5, 2), "B": Fraction(2), "C": Fraction(5, 2),
       "E": Fraction(3)}


def prefix(log: list[dict[str, Any]], t: Fraction) -> list[dict[str, Any]]:
    return [r for r in log if Fraction(r.get("event_time", 0)) <= t]


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


def prefix_head_waiting(log: list[dict[str, Any]], resource: str, t: Fraction
                        ) -> bool:
    """Checker's own waiting-head test at t from the log PREFIX: some
    released task of `resource` with release_time <= t that is not
    terminal, not completed, and not running at t."""
    pre = prefix(log, t)
    terminal_devs = {r["device_id"] for r in pre
                     if r.get("event_type") == "DEVICE_TERMINAL"}
    released = [(Fraction(r["event_time"]), r["resource_id"], r["device_id"],
                 r["process"], r["effective_attempt_no"])
                for r in pre if r.get("event_type") == "TASK_RELEASE"]
    for rel, rsrc, dev, proc, att in released:
        if rsrc != resource:
            continue
        if dev in terminal_devs:
            continue
        completed = any(r.get("event_type") == "ACTIVITY_COMPLETE"
                        and r["device_id"] == dev and r["process"] == proc
                        and r["effective_attempt_no"] == att
                        for r in pre)
        if completed:
            continue
        running = any(r.get("event_type") == "ACTIVITY_START"
                      and r["device_id"] == dev and r["process"] == proc
                      and r["effective_attempt_no"] == att
                      and Fraction(r["event_time"]) <= t
                      and t < Fraction(r["attempt_end_time"])
                      for r in pre)
        if running:
            continue
        return True
    return False


def prefix_legal_head(log: list[dict[str, Any]], resource: str, t: Fraction,
                      shift_end: Fraction) -> bool:
    """Checker's own time-causal legality of the FCFS head at t: device
    non-terminal, E prereq passed by observations <= t, duration fits."""
    pre = prefix(log, t)
    terminal_devs = {r["device_id"] for r in pre
                     if r.get("event_type") == "DEVICE_TERMINAL"}
    passed = {(r["device_id"], r["process"]) for r in pre
              if r.get("event_type") == "OBSERVATION_MATERIALIZED"
              and r.get("outcome") == "PASS"}
    released = [(Fraction(r["event_time"]), r["resource_id"], r["device_id"],
                 r["process"], r["effective_attempt_no"])
                for r in pre if r.get("event_type") == "TASK_RELEASE"]
    cand = None
    for rel, rsrc, dev, proc, att in released:
        if rsrc != resource:
            continue
        if dev in terminal_devs:
            continue
        completed = any(r.get("event_type") == "ACTIVITY_COMPLETE"
                        and r["device_id"] == dev and r["process"] == proc
                        and r["effective_attempt_no"] == att for r in pre)
        running = any(r.get("event_type") == "ACTIVITY_START"
                      and r["device_id"] == dev and r["process"] == proc
                      and r["effective_attempt_no"] == att
                      and Fraction(r["event_time"]) <= t
                      and t < Fraction(r["attempt_end_time"]) for r in pre)
        if completed or running:
            continue
        key = (rel, dev, an.PROCESS_ORDER.get(proc, 9), att)
        if cand is None or key < cand[0]:
            cand = (key, dev, proc, att)
    if cand is None:
        return False
    _key, dev, proc, att = cand
    if proc == "E" and not all((dev, p) in passed for p in ("A", "B", "C")):
        return False
    return t + DUR[proc] <= shift_end


def prefix_idle(log: list[dict[str, Any]], resource: str, t: Fraction) -> bool:
    """Checker's own idle test at t from the log PREFIX: no in-flight
    fragment (start s <= t < scheduled end without a settle <= t) and no
    calibration interval covering t."""
    pre = prefix(log, t)
    for r in pre:
        if r.get("event_type") == "ACTIVITY_START" and r.get("resource_id") == resource:
            s = Fraction(r["event_time"])
            end = Fraction(r["attempt_end_time"])
            if s <= t < end:
                dev, proc, att = r["device_id"], r["process"], r["effective_attempt_no"]
                settled = any(
                    (q.get("event_type") in ("ACTIVITY_COMPLETE", "TASK_CANCEL"))
                    and q["device_id"] == dev and q["process"] == proc
                    and q["effective_attempt_no"] == att
                    for q in pre)
                if not settled:
                    return False
        if r.get("event_type") == "EQUIPMENT_REPLACEMENT_START" \
                and r.get("resource_id") == resource:
            cs = Fraction(r["calibration_start"])
            ce = Fraction(r["calibration_end"])
            if cs <= t < ce:
                return False
    return True


def prefix_age(log: list[dict[str, Any]], resource: str, t: Fraction) -> Fraction:
    """Checker's own equipment age at t from the log PREFIX (fragments
    ending <= t since the latest replacement start <= t)."""
    pre = prefix(log, t)
    gen_start = Fraction(0)
    for r in pre:
        if r.get("event_type") == "EQUIPMENT_REPLACEMENT_START" \
                and r.get("resource_id") == resource:
            t0 = Fraction(r["event_time"])
            if t0 <= t:
                gen_start = max(gen_start, t0)
    age = Fraction(0)
    for r in pre:
        if r.get("event_type") not in ("ACTIVITY_COMPLETE", "TASK_CANCEL"):
            continue
        if r.get("resource_id") != resource:
            continue
        if r.get("attempt_start_time") is None:
            continue
        s = Fraction(r["attempt_start_time"])
        e = Fraction(r["event_time"])
        if s < gen_start:
            continue
        if e <= t:
            age += e - s
    return age


def prefix_maintenance_count(log: list[dict[str, Any]], K: Fraction,
                             batch_size: int) -> int:
    """Checker's OWN independent PM_IDLE (maintenance point) count over the
    reconstructed closure set (distinct event times + Q3 shift starts),
    using only the prefix state helpers above.  Never calls the analyzer."""
    event_times = sorted({Fraction(r["event_time"]) for r in log})
    terminals = [Fraction(r["event_time"]) for r in log
                 if r.get("event_type") == "DEVICE_TERMINAL"]
    batch_end = max(terminals) if terminals else (
        max(event_times) if event_times else Fraction(0))
    shifts: list[tuple[Fraction, Fraction]] = []
    for d in range(400):
        s1 = Fraction(24) * d
        shifts.append((s1, s1 + K))
        shifts.append((s1 + K, s1 + 2 * K))
    count = 0
    for t in sorted(set(event_times) | {s for s, _e in shifts}):
        if t >= batch_end:
            continue
        sh = None
        for s, e in shifts:
            if s <= t < e:
                sh = (s, e)
                break
        if sh is None:
            continue
        for rsrc in ("A", "B", "C", "E"):
            if not prefix_idle(log, rsrc, t):
                continue
            if prefix_legal_head(log, rsrc, t, sh[1]):
                continue
            age = prefix_age(log, rsrc, t)
            if not (an.MIN_PREVENTIVE_AGE_H <= age < an.MANDATORY_AGE_H):
                continue
            cal = an.CALIBRATION_MINUTES[rsrc] / Fraction(60)
            if t + cal > sh[1]:
                continue
            if not prefix_demand(log, rsrc, t, batch_size):
                continue
            count += 1
    return count


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
    print("CHECKER: PASS (8 boundary cases + 10 temporal cases + "
          "determinism/order)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
