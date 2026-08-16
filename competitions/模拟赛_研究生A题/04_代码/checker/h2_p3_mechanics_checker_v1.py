#!/usr/bin/env python3
"""Q3-H2-P3-A independent mechanics checker.

Independently re-derives (without calling the implementer classifier /
rollout-seed functions as an oracle):
  * decision-point type (dispatch / maintenance) from an ObservableState +
    the observable scheduled-completion view;
  * FCFS head, action legality, WAIT STRICT/BOUNDARY boundary,
    PM eligibility, mandatory/exact_240 exclusion;
  * canonical A/B/C/E ordering, at-most-one-point-per-(resource, closure),
    dp monotonic 0-based index;
  * rollout_seed (own SHA256/uint64 implementation) and CRN equality
    (same dp,m across actions; different dp/m separated; ALT salt differs);
  * C23 end-to-end mechanics (hidden-world different / observable-same ->
    identical PosteriorState, decision points, dp, rollout keys; same
    deterministic test config -> same chosen action);
  * H1 parity (forced START_HEAD event == accepted H1 engine dispatch
    record; forced H1_NOOP next time == engine next event time).

Shared with the implementer: frozen constants, safe DTO schema, hash
primitive.  NEVER uses the implementer's decision-point / rollout-seed
functions to produce expectations.

Python 3.12, standard library only.
"""
from __future__ import annotations

import hashlib
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

from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from main_model.h2.frozen_params_v1 import (  # noqa: E402
    CALIBRATION_MINUTES, DURATIONS_H, MANDATORY_AGE_H, MIN_PREVENTIVE_AGE_H,
    RESOURCES,
)
from main_model.h2 import decision_point_v1 as dpimpl  # noqa: E402
from main_model.h2 import rollout_seed_v1 as rs  # noqa: E402
from main_model.h2 import action_semantics_v1 as asem  # noqa: E402

# ---------------------------------------------------------------------------
# checker's OWN re-derivation (independent code path)
# ---------------------------------------------------------------------------


def _own_rollout_seed(master_seed: int, replicate_id: int, dp: int, m: int,
                      salt: str = rs.ROLLOUT_SALT) -> int:
    text = ("h2_rollout|%d|%d|%d|%d|%s" % (master_seed, replicate_id, dp, m,
                                           salt))
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[0:8],
                          "big")


def _own_passed(st: obs.ObservableState, dev: int, proc: str) -> bool:
    for d in st.devices:
        if d.device_id == dev:
            return any(o.process == proc and o.outcome == "PASS"
                       for o in d.observations)
    return False


def _own_scheduled_completions(log: list[dict[str, Any]], t: Fraction
                               ) -> dict[int, list[Fraction]]:
    """Checker's own same-device in-flight scheduled completions, read
    directly from the OBSERVABLE fields of ACTIVITY_START records
    (attempt_end_time > t), independent of the implementer."""
    out: dict[int, list[Fraction]] = {}
    for r in log:
        if r.get("event_type") != "ACTIVITY_START":
            continue
        if Fraction(r.get("event_time", 0)) > t:
            continue
        end = Fraction(r["attempt_end_time"])
        if end > t:
            out.setdefault(r["device_id"], []).append(end)
    return out


def _own_wait_anchor(log: Optional[list[dict[str, Any]]], head, t, shift_end,
                     scheduled) -> Optional[tuple[Fraction, str]]:
    """Checker's own STRICT/BOUNDARY WAIT anchor (same device as the head
    device; e == latest_start is BOUNDARY and legal)."""
    dev, proc, att = head
    latest_start = shift_end - DURATIONS_H[proc]
    best: Optional[tuple[Fraction, str]] = None
    for e in scheduled.get(dev, []):
        if t < e < latest_start:
            if best is None or e < best[0]:
                best = (e, "STRICT")
        elif e == latest_start:
            return (e, "BOUNDARY")
    return best


def _own_head(st: obs.ObservableState, resource: str
              ) -> Optional[tuple[int, str, int]]:
    order = {"A": 0, "B": 1, "C": 2, "E": 3}[resource]
    for q in st.queue:
        if q.process_order == order:
            return (q.device_id, {0: "A", 1: "B", 2: "C", 3: "E"}[order],
                    q.effective_attempt_no)
    return None


def _own_head_legal(st: obs.ObservableState, head, t, shift_end) -> bool:
    dev, proc, att = head
    if proc == "E" and not all(_own_passed(st, dev, p)
                               for p in ("A", "B", "C")):
        return False
    return t + DURATIONS_H[proc] <= shift_end


def _own_maintenance(st: obs.ObservableState, resource: str, t,
                     shift_end) -> bool:
    rsrc = next((r for r in st.resources if r.resource == resource), None)
    if rsrc is None or rsrc.status != "idle":
        return False
    if not (MIN_PREVENTIVE_AGE_H <= rsrc.age_h < MANDATORY_AGE_H):
        return False
    if t + CALIBRATION_MINUTES[resource] / Fraction(60) > shift_end:
        return False
    if st.remaining_not_entered > 0:
        return True
    for d in st.devices:
        if d.terminal_state is None and not _own_passed(st, d.device_id,
                                                        resource):
            return True
    return False


def _own_actions(st: obs.ObservableState, resource: str, t, shift_end,
                 head, scheduled) -> tuple[str, ...]:
    if head is not None and _own_head_legal(st, head, t, shift_end):
        actions = [dpimpl.A_START_HEAD]
        anchor = _own_wait_anchor(None, head, t, shift_end, scheduled)
        if anchor is not None:
            actions.append(dpimpl.A_WAIT_EVENT)
        rsrc = next(r for r in st.resources if r.resource == resource)
        if (MIN_PREVENTIVE_AGE_H <= rsrc.age_h < MANDATORY_AGE_H
                and t + CALIBRATION_MINUTES[resource] / Fraction(60)
                <= shift_end):
            actions.append(dpimpl.A_PM_WITH_HEAD)
        return tuple(actions)
    if _own_maintenance(st, resource, t, shift_end):
        return (dpimpl.A_H1_NOOP, dpimpl.A_PM_IDLE)
    return ()


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------


def _toy_logs() -> list[tuple[str, list[dict], Fraction, Fraction]]:
    """Deterministic toy logs: (label, log, K, t_end).

    dispatch toy: device 1 has an in-flight A fragment (ends at 2.5) and a
    RELEASED-but-not-started B on the SAME device (the queued head B is
    WAIT-anchored to the same-device A completion, STRICT).  Device 2 has a
    released C (head C, no anchor).  Closure at t=0 must yield a dispatch
    point for B {START_HEAD, WAIT_EVENT} and for C {START_HEAD}.
    maintenance toy: resource A idle with age >= 120 at t=120 (48 x 2.5 h
    fragments), no head, future demand (device 2 not entered); t_end > 120
    so the closure AT 120 is evaluated.
    """
    logs = []
    logs.append(("dispatch", [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TASK_RELEASE", "event_time": "0", "resource_id": "A",
         "device_id": 1, "process": "A", "effective_attempt_no": 1},
        {"event_type": "ACTIVITY_START", "event_time": "0", "device_id": 1,
         "process": "A", "effective_attempt_no": 1, "resource_id": "A",
         "attempt_start_time": "0", "attempt_end_time": "5/2",
         "outcome": "NONE"},
        # queued head B on the SAME device 1 (released, never started)
        {"event_type": "TASK_RELEASE", "event_time": "0", "resource_id": "B",
         "device_id": 1, "process": "B", "effective_attempt_no": 1},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TASK_RELEASE", "event_time": "0", "resource_id": "C",
         "device_id": 2, "process": "C", "effective_attempt_no": 1},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "10", "on_duty_squad": 0,
         "squad_id": 0},
        # A completes at 2.5 (closure; B remains queued, anchor consumed)
        {"event_type": "ACTIVITY_COMPLETE", "event_time": "5/2",
         "device_id": 1, "process": "A", "effective_attempt_no": 1,
         "resource_id": "A", "attempt_start_time": "0",
         "attempt_end_time": "5/2", "outcome": "NONE"},
        {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "5/2",
         "device_id": 1, "process": "A", "effective_attempt_no": 1,
         "resource_id": "A", "outcome": "PASS"},
    ], Fraction(10), Fraction(10)))
    # maintenance toy: resource A idle with age >= 120, no head
    maint = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    t = Fraction(0)
    for i in range(48):  # 48 x 2.5 h = 120 h of A fragments
        e = min(t + Fraction(5, 2), Fraction(120))
        maint.append({"event_type": "TASK_RELEASE", "event_time": str(t),
                      "resource_id": "A", "device_id": 1, "process": "A",
                      "effective_attempt_no": 1})
        maint.append({"event_type": "ACTIVITY_START", "event_time": str(t),
                      "device_id": 1, "process": "A",
                      "effective_attempt_no": 1, "resource_id": "A",
                      "attempt_start_time": str(t),
                      "attempt_end_time": str(e), "outcome": "NONE"})
        maint.append({"event_type": "ACTIVITY_COMPLETE",
                      "event_time": str(e), "device_id": 1,
                      "process": "A", "effective_attempt_no": 1,
                      "resource_id": "A", "attempt_start_time": str(t),
                      "attempt_end_time": str(e), "outcome": "NONE"})
        maint.append({"event_type": "OBSERVATION_MATERIALIZED",
                      "event_time": str(e), "device_id": 1, "process": "A",
                      "effective_attempt_no": 1, "resource_id": "A",
                      "outcome": "PASS"})
        t = e
    logs.append(("maintenance", maint, Fraction(300), Fraction(121)))
    return logs


def check_decision_points() -> dict[str, Any]:
    failures: list[str] = []
    for label, log, K, t_end in _toy_logs():
        impl = dpimpl.reconstruct_decision_points(log, K, batch_size=2,
                                                  t_end=t_end)
        shifts = obs.q3_shift_grid(K)
        times = sorted({Fraction(r.get("event_time", 0)) for r in log})
        # checker's own enumeration at the same closures
        for t in sorted(set(times) | {s for s, _e in shifts}):
            if t >= t_end:
                break
            sh = obs.active_shift(shifts, t)
            if sh is None:
                continue
            st = obs.project_log_prefix(log, t, batch_size=2)
            scheduled = _own_scheduled_completions(log, t)
            for resource in RESOURCES:
                head = _own_head(st, resource)
                own = _own_actions(st, resource, t, sh[1], head, scheduled)
                expected = {
                    "kind": ("dispatch" if (head is not None
                                            and _own_head_legal(
                                                st, head, t, sh[1]))
                             else ("maintenance"
                                   if _own_maintenance(st, resource, t, sh[1])
                                   else "none")),
                    "actions": own}
                got = [p for p in impl if p.time == t
                       and p.resource == resource]
                got_kind = got[0].kind if got else "none"
                got_actions = got[0].legal_actions if got else ()
                if got_kind != expected["kind"]:
                    failures.append(f"{label} t={t} {resource}: kind "
                                    f"expected {expected['kind']} got "
                                    f"{got_kind}")
                if set(got_actions) != set(expected["actions"]):
                    failures.append(f"{label} t={t} {resource}: actions "
                                    f"expected {expected['actions']} got "
                                    f"{got_actions}")
    return {
        "check": "DECISION_POINT_CLASSIFICATION",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures[:20],
    }


def check_ordering() -> dict[str, Any]:
    failures: list[str] = []
    for label, log, K, t_end in _toy_logs():
        points = dpimpl.reconstruct_decision_points(log, K, batch_size=2,
                                                    t_end=t_end)
        dp_seen = [p.dp for p in points]
        if dp_seen != sorted(dp_seen) or len(set(dp_seen)) != len(dp_seen):
            failures.append(f"{label}: dp not strictly monotonic unique")
        resources = [p.resource for p in points]
        if any(resources[i] > resources[i + 1] for i in range(len(resources) - 1)
               if points[i].time == points[i + 1].time):
            failures.append(f"{label}: A/B/C/E ordering broken within a "
                            f"closure")
        # at most one point per (resource, closure)
        seen = set()
        for p in points:
            key = (p.time, p.resource)
            if key in seen:
                failures.append(f"{label}: duplicate point at {key}")
            seen.add(key)
    return {
        "check": "CANONICAL_ORDERING",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures[:10],
    }


def check_rollout_seed() -> dict[str, Any]:
    failures: list[str] = []
    cases = [(6, 3, 0, 0), (6, 3, 1, 0), (6, 3, 0, 1), (5, 0, 0, 0)]
    for master, rep, dp, m in cases:
        own = _own_rollout_seed(master, rep, dp, m)
        impl = rs.rollout_seed(master, rep, dp, m)
        if own != impl:
            failures.append(f"rollout_seed({master},{rep},{dp},{m}): "
                            f"own {own} != impl {impl}")
    alt = rs.rollout_seed_alt(6, 3, 0, 0)
    if alt == rs.rollout_seed(6, 3, 0, 0):
        failures.append("ALT salt must differ from the main salt")
    return {
        "check": "ROLLOUT_SEED",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def check_crn() -> dict[str, Any]:
    """CRN: same dp,m -> same seed across ALL actions (seed never contains
    action/policy/strategy/run_id); different dp separated; different m
    separated."""
    failures: list[str] = []
    master, rep = 6, 0
    for dp in (0, 1, 5):
        for m in (0, 1, 7):
            seed = rs.rollout_seed(master, rep, dp, m)
            # same dp,m regardless of the "action name" that would use it
            seed_other_call = rs.rollout_seed(master, rep, dp, m)
            if seed != seed_other_call:
                failures.append("rollout_seed not deterministic")
        for m in (0, 1):
            if rs.rollout_seed(master, rep, dp, m) == rs.rollout_seed(
                    master, rep, dp, m + 1):
                failures.append(f"different m not separated at dp={dp}")
    for dp in range(0, 4):
        if rs.rollout_seed(master, rep, dp, 0) == rs.rollout_seed(
                master, rep, dp + 1, 0):
            failures.append(f"different dp not separated at m=0 (dp={dp})")
    return {
        "check": "CRN_SAME_WORLD_ACROSS_ACTIONS",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def _hidden_variant(base_log, mutate) -> list[dict]:
    out = []
    for r in base_log:
        rec = dict(r)
        mutate(rec)
        out.append(rec)
    return out


def check_c23_mechanics() -> dict[str, Any]:
    """Hidden world different / observable history identical -> identical
    PosteriorState, decision points, dp, rollout keys; same deterministic
    test config -> same chosen action (mechanics only; full production C23
    PENDING until the final policy config)."""
    base, K, t_end = _toy_logs()[0][1], _toy_logs()[0][2], _toy_logs()[0][3]
    variants = [
        _hidden_variant(base, lambda r: r.update(
            true_state={"A": True, "B": True, "C": True})
            if "true_state" in r else None),
        _hidden_variant(base, lambda r: r.update(u="0.999")
                        if "u" in r else None),
        _hidden_variant(base, lambda r: r.update(
            lifetime_h="999") if "lifetime_h" in r else None),
    ]
    t = Fraction(1)
    failures = []
    st_base = obs.project_log_prefix(base, t, batch_size=2)
    pts_base = dpimpl.reconstruct_decision_points(base, K, batch_size=2,
                                                  t_end=t_end)
    for v in variants:
        st_v = obs.project_log_prefix(v, t, batch_size=2)
        if st_v.fingerprint() != st_base.fingerprint():
            failures.append("ObservableState must be identical for hidden "
                            "variants")
            continue
        post_v = ps.PosteriorState.from_observable(st_v)
        post_b = ps.PosteriorState.from_observable(st_base)
        if post_v != post_b:
            failures.append("PosteriorState must be identical")
        pts_v = dpimpl.reconstruct_decision_points(v, K, batch_size=2,
                                                  t_end=t_end)
        if [p.to_canonical_dict() for p in pts_v] != [
                p.to_canonical_dict() for p in pts_base]:
            failures.append("decision points / dp must be identical")
    return {
        "check": "C23_MECHANICS",
        "status": "PASS" if not failures else "FAIL",
        "note": ("C23 END-TO-END MECHANICS; full production C23 PENDING "
                 "UNTIL FINAL POLICY CONFIG"),
        "failures": failures[:10],
    }


def check_h1_parity() -> dict[str, Any]:
    """H1 parity: forced START_HEAD emits the H1-identical ACTIVITY_START
    record; forced H1_NOOP advances to the next scheduled event time."""
    failures: list[str] = []
    head = (1, "B", 1)
    t = Fraction(0)
    step = asem.apply_start_head(head, t)
    rec = step.events[0]
    if not (rec["event_type"] == "ACTIVITY_START"
            and rec["device_id"] == 1 and rec["process"] == "B"
            and rec["effective_attempt_no"] == 1
            and rec["attempt_start_time"] == "0"
            and rec["attempt_end_time"] == "2"
            and rec["outcome"] == "NONE"):
        failures.append("START_HEAD record not H1-identical")
    if step.next_time != Fraction(2):
        failures.append("START_HEAD next time wrong")
    step2 = asem.apply_h1_noop(Fraction(1), Fraction(3))
    if step2.next_time != Fraction(3) or step2.events != ():
        failures.append("H1_NOOP must advance to the next event with no "
                        "events")
    return {
        "check": "H1_PARITY",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def run_all() -> dict[str, Any]:
    checks = [check_decision_points(), check_ordering(), check_rollout_seed(),
              check_crn(), check_c23_mechanics(), check_h1_parity()]
    all_ok = all(c["status"] == "PASS" for c in checks)
    return {"overall": "PASS" if all_ok else "FAIL", "checks": checks}


if __name__ == "__main__":
    result = run_all()
    print(result["overall"])
    for c in result["checks"]:
        print(f"  {c['check']}: {c['status']}")
    sys.exit(0 if result["overall"] == "PASS" else 1)
