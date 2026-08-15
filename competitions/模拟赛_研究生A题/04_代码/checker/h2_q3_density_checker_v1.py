#!/usr/bin/env python3
"""Q3-H2-DENSITY independent checker (Q3-H2-DENSITY package, section 18).

The density analyzer must not self-certify.  This checker independently
recomputes the frozen classifications for hand-built deterministic small
cases and cross-checks the analyzer's counts on those same logs.  It does
NOT call the analyzer's ``classify_batch_q3`` as an oracle: expected values
are derived from the frozen definitions (Bootstrap FINAL_FREEZE_ACCEPTED
sections 10/11/12/15 and D-14) by (a) hand-derived per-case expectations and
(b) an independent mini-logic implemented here (``independent_dispatch_
wait_expected``) for the dispatch-anchored wait cases; both are compared
against the analyzer's output.

Covered cases (package requirement):
  A. hand/ deterministic small cases (dispatch legal, forced wait, STRICT,
     BOUNDARY, NONSTRICT, pm_with_head, meaningful)
  B. Q3 K-specific calendar boundaries (K=9 and K=12 shift ends)
  C. e == latest_start (BOUNDARY legal WAIT)
  D. queue-empty PM_IDLE (maintenance point)
  E. queue-nonempty but no legal head PM_IDLE (forced-wait maintenance)
  F. a + d == 240 (exact_240, not optional PM)
  G. a + d > 240 (mandatory, not optional PM)
  H. same event closure / resource ordering (frozen canonical order
     A/B/C/E; determinism of classification)

Python 3.12, standard library only.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
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


def synthetic_log(records: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Merge scenario event groups in event-time order (stable sort keeps
    same-instant canonical order: TRUE_STATE -> RELEASE -> START)."""
    flat = [r for group in records
            for r in (group if isinstance(group, list) else [group])]
    flat.sort(key=lambda r: Fraction(r.get("event_time", 0)))
    return flat


def fragment_chain(device: int, end_target: Fraction) -> list[dict[str, Any]]:
    """Back-to-back A fragments covering [0, end_target]; the last fragment
    may be shorter.  Each fragment is START + COMPLETE with the TRUE start
    time (the analyzer's age reconstruction uses attempt_start_time)."""
    out: list[dict[str, Any]] = []
    t = Fraction(0)
    while t < end_target:
        e = min(t + Fraction(5, 2), end_target)
        out.append(start(device, "A", str(t), str(e)))
        out.append(complete(device, "A", str(e), str(t)))
        t = e
    return out


# ---------------------------------------------------------------------------
# Independent mini-logic for dispatch-anchored WAIT cases (this checker's own
# re-derivation of STRICT / BOUNDARY / NONSTRICT from the frozen text; it
# does not call the analyzer).
# ---------------------------------------------------------------------------


def independent_dispatch_wait_expected(
    log: list[dict[str, Any]], K: Fraction, durations: dict[str, Fraction],
) -> dict[str, int]:
    out = {"legal_dispatch": 0, "strict": 0, "boundary": 0, "nonstrict": 0}
    starts = [r for r in log if r.get("event_type") == "ACTIVITY_START"]
    for r in starts:
        t = Fraction(r["event_time"])
        dev = r["device_id"]
        proc = r["process"]
        d = durations[proc]
        day = t // Fraction(24)
        s1 = Fraction(24) * day
        if s1 + K <= t < s1 + 2 * K:
            shift_end = s1 + 2 * K
        else:
            shift_end = s1 + K
        latest_start = shift_end - d
        out["legal_dispatch"] += 1
        completions = []
        for other in starts:
            if other["device_id"] != dev:
                continue
            os_, oe_ = Fraction(other["event_time"]), Fraction(other["attempt_end_time"])
            if os_ < t < oe_:
                completions.append(oe_)
        if any(c < latest_start for c in completions):
            out["strict"] += 1
        if any(c == latest_start for c in completions):
            out["boundary"] += 1
        if any(c <= latest_start for c in completions):
            out["nonstrict"] += 1
    return out


# ---------------------------------------------------------------------------
# Checker harness
# ---------------------------------------------------------------------------

DUR = {"A": Fraction(5, 2), "B": Fraction(2), "C": Fraction(5, 2),
       "E": Fraction(3)}


def analyzer_counts(log: list[dict[str, Any]], K: Fraction) -> dict[str, int]:
    s = an.classify_batch_q3(log, K, "KCK", "9", 0, batch_size=2)
    return {
        "legal_dispatch": s.legal_dispatch_decision_points,
        "strict": s.strategic_strict,
        "boundary": s.strategic_boundary,
        "nonstrict": s.strategic_nonstrict,
        "pm_head": s.pm_with_head,
        "pm_idle": s.pm_idle,
        "forced_wait": s.forced_wait,
        "mandatory": s.mandatory_replacement,
        "exact_240": s.exact_240,
        "both": s.both_wait_and_pm,
        "meaningful": s.meaningful_h2_choice,
    }


def expect(failures: list[str], name: str, got: dict[str, int],
           expected: dict[str, int]) -> None:
    for key, exp in expected.items():
        if got[key] != exp:
            failures.append(f"{name}: {key} expected {exp} got {got[key]}")


# ---------------------------------------------------------------------------
# Deterministic scenarios (module-level; each is (event_log, K))
# ---------------------------------------------------------------------------


def case1_strict() -> tuple[list[dict[str, Any]], Fraction]:
    """STRICT (K=12): device1 A in flight (0..2.5), B starts at 1, ends 3;
    latest_start(B) = 12-2 = 10; e(A) = 2.5 < 10 -> STRICT.  A's own anchor
    has no same-device in-flight completion -> no wait."""
    return synthetic_log([
        true_state([1]),
        release(1, "A", "0"), release(1, "B", "0"),
        start(1, "A", "0", "5/2"), complete(1, "A", "5/2", "0"),
        obs(1, "A", "5/2"),
        start(1, "B", "1", "3"), complete(1, "B", "3", "1"),
        obs(1, "B", "3"),
    ]), Fraction(12)


def case2_boundary() -> tuple[list[dict[str, Any]], Fraction]:
    """BOUNDARY (e == latest_start): K=9 shift1=[0,9); A in flight ending 7;
    B (d=2) starts at 1: latest_start(B)=9-2=7; e(A)=7 == 7 -> BOUNDARY
    legal WAIT (frozen contract: 早于或等于)."""
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
    flight ending 8; B at 1: latest_start(B)=7; e=8 > 7 -> no strict /
    boundary / nonstrict."""
    return synthetic_log([
        true_state([1]),
        release(1, "A", "0"), release(1, "B", "0"),
        start(1, "A", "0", "8"), complete(1, "A", "8", "0"),
        obs(1, "A", "8"),
        start(1, "B", "1", "3"), complete(1, "B", "3", "1"),
        obs(1, "B", "3"),
    ]), Fraction(9)


def case4_pm_with_head() -> tuple[list[dict[str, Any]], Fraction]:
    """PM_WITH_HEAD at a dispatch point: A fragments to age exactly 120, then
    an A dispatch at t=120 (a+d = 122.5 < 240, age >= 120, calibration 0.5 h
    fits shift [0,240)) -> optional PM_WITH_HEAD, meaningful."""
    return synthetic_log([
        true_state([1]),
        release(1, "A", "0"),
        fragment_chain(1, Fraction(120)),
        release(1, "A", "120"), start(1, "A", "120", "245/2"),
        complete(1, "A", "245/2", "120"), obs(1, "A", "245/2"),
    ]), Fraction(240)


def case5_pm_idle_queue_empty() -> tuple[list[dict[str, Any]], Fraction]:
    """queue-empty PM_IDLE (maintenance point): device2 A fragments to age
    120; resource idle at t=120 with NO waiting head; a second device
    (device5) keeps the batch alive past 120.  age >= 120, cal fits, future
    demand -> pm_idle = 1."""
    return synthetic_log([
        true_state([2, 5]),
        release(2, "A", "0"),
        fragment_chain(2, Fraction(120)),
        release(5, "A", "121"), start(5, "A", "121", "247/2"),
        complete(5, "A", "247/2", "121"), obs(5, "A", "247/2"),
    ]), Fraction(240)


def case6_pm_idle_forced_wait() -> tuple[list[dict[str, Any]], Fraction]:
    """queue-nonempty but NO legal head (forced wait) -> maintenance PM_IDLE:
    device3 A fragments to age 120, an A release at t=120 cannot legally
    start (120+2.5 = 122.5 > shift_end 121) -> forced wait; a+d = 122.5 < 240
    -> not mandatory; cal fits -> pm_idle = 1.  device4 keeps the batch alive
    past the forced-wait instant."""
    return synthetic_log([
        true_state([3, 4]),
        release(3, "A", "0"),
        fragment_chain(3, Fraction(120)),
        release(3, "A", "120"),
        release(4, "A", "121"), start(4, "A", "121", "247/2"),
        complete(4, "A", "247/2", "121"), obs(4, "A", "247/2"),
    ]), Fraction(121)


def case7_exact_240() -> tuple[list[dict[str, Any]], Fraction]:
    """a + d == 240 -> exact_240 (NOT optional PM): age exactly 237.5,
    d = 2.5."""
    return synthetic_log([
        true_state([4]),
        release(4, "A", "0"),
        fragment_chain(4, Fraction(475, 2)),
        release(4, "A", "475/2"), start(4, "A", "475/2", "240"),
        complete(4, "A", "240", "475/2"), obs(4, "A", "240"),
    ]), Fraction(300)


def case8_mandatory() -> tuple[list[dict[str, Any]], Fraction]:
    """a + d > 240 -> mandatory (NOT optional PM): age exactly 238,
    d = 2.5 -> 240.5."""
    return synthetic_log([
        true_state([5]),
        release(5, "A", "0"),
        fragment_chain(5, Fraction(238)),
        release(5, "A", "238"), start(5, "A", "238", "481/2"),
        complete(5, "A", "481/2", "238"), obs(5, "A", "481/2"),
    ]), Fraction(300)


def run_checks() -> list[str]:
    failures: list[str] = []

    # C1 STRICT (K=12)
    log1, K1 = case1_strict()
    got1 = analyzer_counts(log1, K1)
    expect(failures, "STRICT", got1,
           {"legal_dispatch": 2, "strict": 1, "boundary": 0,
            "nonstrict": 1, "meaningful": 1})
    mini1 = independent_dispatch_wait_expected(log1, K1, DUR)
    expect(failures, "STRICT(mini)", mini1,
           {"legal_dispatch": 2, "strict": 1, "boundary": 0, "nonstrict": 1})

    # C2 BOUNDARY (e == latest_start): K=9 shift1=[0,9); A in flight ending
    #     7; B (d=2) starts at 1: latest_start(B)=9-2=7; e(A)=7 == 7 ->
    #     BOUNDARY legal WAIT (frozen contract: 早于或等于).
    log2, K2 = case2_boundary()
    got2 = analyzer_counts(log2, K2)
    expect(failures, "BOUNDARY", got2,
           {"legal_dispatch": 2, "strict": 0, "boundary": 1, "nonstrict": 1})
    mini2 = independent_dispatch_wait_expected(log2, K2, DUR)
    expect(failures, "BOUNDARY(mini)", mini2,
           {"legal_dispatch": 2, "strict": 0, "boundary": 1, "nonstrict": 1})

    # C3 NONSTRICT-only when e > latest_start (NOT a legal wait): K=9, A in
    #     flight ending 8; B at 1: latest_start(B)=7; e=8 > 7 -> no strict /
    #     boundary / nonstrict.
    log3, K3 = case3_nonstrict_not_legal()
    got3 = analyzer_counts(log3, K3)
    expect(failures, "NONSTRICT-not-legal", got3,
           {"legal_dispatch": 2, "strict": 0, "boundary": 0, "nonstrict": 0})
    mini3 = independent_dispatch_wait_expected(log3, K3, DUR)
    expect(failures, "NONSTRICT-not-legal(mini)", mini3,
           {"legal_dispatch": 2, "strict": 0, "boundary": 0, "nonstrict": 0})

    # C4 PM_WITH_HEAD at a dispatch point: A fragments to age exactly 120,
    #     then an A dispatch at t=120 (a+d = 122.5 < 240, age >= 120,
    #     calibration 0.5 h fits shift [0,240)) -> optional PM_WITH_HEAD,
    #     meaningful.
    log4, K4 = case4_pm_with_head()
    got4 = analyzer_counts(log4, K4)
    expect(failures, "PM_WITH_HEAD", got4, {"pm_head": 1, "meaningful": 1})

    # C5 queue-empty PM_IDLE (maintenance point): device2 A fragments to age
    #     120; resource idle at t=120 with NO waiting head; a second device
    #     (device5) keeps the batch alive past 120.  age >= 120, cal fits,
    #     future demand -> pm_idle = 1.
    log5, K5 = case5_pm_idle_queue_empty()
    got5 = analyzer_counts(log5, K5)
    expect(failures, "PM_IDLE-queue-empty", got5, {"pm_idle": 1})

    # C6 queue-nonempty but NO legal head (forced wait) -> maintenance
    #     PM_IDLE: device3 A fragments to age 120, an A release at t=120
    #     cannot legally start (120+2.5 = 122.5 > shift_end 121) -> forced
    #     wait; a+d = 122.5 < 240 -> not mandatory; cal fits -> pm_idle = 1.
    #     device4 keeps the batch alive past the forced-wait instant.
    log6, K6 = case6_pm_idle_forced_wait()
    got6 = analyzer_counts(log6, K6)
    expect(failures, "PM_IDLE-forced-wait", got6,
           {"pm_idle": 1, "forced_wait": 1})

    # C7 a + d == 240 -> exact_240 (NOT optional PM).  Fragment chain to age
    #     237.5: chain anchors at t_k = 2.5k (k=0..94) have age 2.5k; the
    #     final anchor at 237.5 has age 237.5 -> a+d = 240 -> exact_240.
    #     Independent pm-eligible chain anchors: 120 <= 2.5k and
    #     2.5k + 2.5 < 240.  The exact_240 anchor must NOT be counted as pm.
    log7, K7 = case7_exact_240()
    got7 = analyzer_counts(log7, K7)
    n7 = 95
    pm7 = sum(1 for k in range(n7)
              if Fraction(120) <= Fraction(5, 2) * k
              and Fraction(5, 2) * k + Fraction(5, 2) < Fraction(240))
    expect(failures, "exact-240", got7,
           {"exact_240": 1, "mandatory": 0, "pm_head": pm7})
    expect(failures, "exact-240-sum", got7,
           {"legal_dispatch": n7 + 1})

    # C8 a + d > 240 -> mandatory (NOT optional PM).  Chain to 238 (partial
    #     last fragment): chain anchor at 237.5 has age 237.5 -> exact_240
    #     (a+d == 240); final anchor at 238 has age 238 -> a+d = 240.5 ->
    #     mandatory.  Neither is optional pm_head.
    log8, K8 = case8_mandatory()
    got8 = analyzer_counts(log8, K8)
    n8 = 96
    pm8 = sum(1 for k in range(n8)
              if Fraction(120) <= Fraction(5, 2) * k
              and Fraction(5, 2) * k + Fraction(5, 2) < Fraction(240))
    expect(failures, "mandatory", got8,
           {"mandatory": 1, "exact_240": 1, "pm_head": pm8})
    expect(failures, "mandatory-sum", got8, {"legal_dispatch": n8 + 1})

    # C9 determinism + frozen canonical resource order A/B/C/E.
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
    print("CHECKER: PASS (8 deterministic boundary cases + determinism/order)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
