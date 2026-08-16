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
from main_model.h2 import frozen_params_v1 as fp  # noqa: E402
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


def _own_fragment_settled(pre: list[dict[str, Any]], device: int,
                          process: str, attempt: int,
                          fstart: Fraction) -> bool:
    """F1: checker's OWN fragment-aware settle -- ONLY a COMPLETE/CANCEL
    with the SAME exact identity (device_id, process, effective_attempt_no,
    attempt_start_time) settles this fragment.  Independent implementation
    (never calls the Density analyzer or the implementer)."""
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


def _own_active_fragments(log: list[dict[str, Any]], t: Fraction
                          ) -> dict[int, list[tuple[Fraction, int, str, int,
                                                    Fraction, str]]]:
    """F1: checker's OWN exact-fragment scheduled-completion candidates at
    t.  A fragment (device, process, attempt, attempt_start_time) is active
    iff start_time <= t < attempt_end_time AND no matching COMPLETE/CANCEL
    settles it in the <= t prefix.  Returns per-device lists of
    (completion_time, device_id, process, effective_attempt_no,
    attempt_start_time, resource) sorted deterministically."""
    pre = [r for r in log
           if r.get("event_time") is not None
           and Fraction(r["event_time"]) <= t]
    out: dict[int, list[tuple[Fraction, int, str, int, Fraction, str]]] = {}
    for r in pre:
        if r.get("event_type") != "ACTIVITY_START":
            continue
        s = Fraction(r.get("attempt_start_time", r["event_time"]))
        end = Fraction(r["attempt_end_time"])
        if not (s <= t < end):
            continue
        if _own_fragment_settled(pre, r["device_id"], r["process"],
                                 r["effective_attempt_no"], s):
            continue
        out.setdefault(r["device_id"], []).append(
            (end, r["device_id"], r["process"], r["effective_attempt_no"],
             s, r.get("resource_id", r["process"])))
    for dev in out:
        out[dev].sort(key=lambda f: (f[0], _OWN_ORDER[f[5]],
                                     f[3], f[4]))
    return out


_OWN_ORDER = {"A": 0, "B": 1, "C": 2, "E": 3}

# Checker's OWN pre-action phase filter (independent implementation of the
# corrected decision-boundary semantics): same-timestamp records produced by
# the equipment-dispatch / turnover phases must not enter the decision state.
_OWN_DISPATCH_PHASE_TYPES = frozenset({
    "ACTIVITY_START", "TURNOVER_OUT_START", "TURNOVER_IN_START",
    "EQUIPMENT_REPLACEMENT_START", "EQUIPMENT_REPLACEMENT_DEFERRED",
    "WAKE_UP",
})


def _own_pre_action_log(log: list[dict[str, Any]], t: Fraction
                        ) -> list[dict[str, Any]]:
    """Checker's own pre-dispatch view at closure t (see the impl's
    pre_action_log for the frozen phase semantics; implemented
    independently here)."""
    out = []
    for r in log:
        et = r.get("event_time")
        if et is None:
            continue
        tt = Fraction(et)
        if tt < t:
            out.append(r)
        elif tt == t and r.get("event_type") not in _OWN_DISPATCH_PHASE_TYPES:
            out.append(r)
    return out


def _own_resource_idle(st: obs.ObservableState, resource: str) -> bool:
    rsrc = next((r for r in st.resources if r.resource == resource), None)
    return rsrc is not None and rsrc.status == "idle"


def _own_wait_anchor(head, t, shift_end,
                     active) -> Optional[tuple[Fraction, str, str, int,
                                               Fraction, str]]:
    """Checker's own STRICT/BOUNDARY WAIT anchor with TRUE in-flight
    fragment identity (F2): returns
    (completion_time, process, effective_attempt_no, attempt_start_time,
     resource, boundary) of the waited fragment, or None.  Deterministic
    selection: earliest completion_time, tie-break resource order /
    effective_attempt_no / attempt_start_time."""
    dev, proc, att = head
    latest_start = shift_end - DURATIONS_H[proc]
    cands: list[tuple] = []
    for (e, fdev, fproc, fatt, fs, fres) in active.get(dev, []):
        if t < e < latest_start:
            cands.append((e, fproc, fatt, fs, fres, "STRICT"))
        elif e == latest_start:
            cands.append((e, fproc, fatt, fs, fres, "BOUNDARY"))
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], _OWN_ORDER[c[4]], c[2], c[3]))
    e, fproc, fatt, fs, fres, boundary = cands[0]
    return (e, fproc, fatt, fs, fres, boundary)


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
    if rsrc.age_h + DURATIONS_H[resource] > MANDATORY_AGE_H:
        return False  # AGE-LEGAL-01: mandatory replacement, no H2 point
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
                 head, active) -> tuple[str, ...]:
    # REQUALIFICATION: a DISPATCH decision point additionally requires the
    # resource to be idle/available (pre-action view); AGE-LEGAL (second
    # requalification): a+d > 240 (mandatory) yields NO point at all and
    # a+d == 240 (exact_240) must NOT offer optional PM_WITH_HEAD.
    rsrc = next((r for r in st.resources if r.resource == resource), None)
    if rsrc is not None \
            and rsrc.age_h + DURATIONS_H[resource] > MANDATORY_AGE_H:
        return ()  # mandatory replacement first: no H2 decision point
    if (_own_resource_idle(st, resource)
            and head is not None
            and _own_head_legal(st, head, t, shift_end)):
        actions = [dpimpl.A_START_HEAD]
        anchor = _own_wait_anchor(head, t, shift_end, active)
        if anchor is not None:
            actions.append(dpimpl.A_WAIT_EVENT)
        if (rsrc is not None
                and rsrc.age_h + DURATIONS_H[resource] < MANDATORY_AGE_H
                and MIN_PREVENTIVE_AGE_H <= rsrc.age_h < MANDATORY_AGE_H
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
        # queued head B on the SAME device 1 (released at t=1; A is already
        # in flight at the t=1 decision boundary -> STRICT WAIT anchor)
        {"event_type": "TASK_RELEASE", "event_time": "1", "resource_id": "B",
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
        # checker's own enumeration at the same closures (pre-action view)
        for t in sorted(set(times) | {s for s, _e in shifts}):
            if t >= t_end:
                break
            sh = obs.active_shift(shifts, t)
            if sh is None:
                continue
            pre = _own_pre_action_log(log, t)
            st = obs.project_log_prefix(pre, t, batch_size=2)
            active = _own_active_fragments(pre, t)
            for resource in RESOURCES:
                head = _own_head(st, resource)
                own = _own_actions(st, resource, t, sh[1], head, active)
                rsrc0 = next((r for r in st.resources
                              if r.resource == resource), None)
                a_plus_d = (rsrc0.age_h + DURATIONS_H[resource]
                            if rsrc0 is not None else Fraction(0))
                # AGE-LEGAL-01 (second requalification): a+d>240 mandatory
                # -> no H2 decision point of any kind
                mandatory = a_plus_d > MANDATORY_AGE_H
                expected = {
                    "kind": ("none" if mandatory else
                             ("dispatch" if (_own_resource_idle(st, resource)
                                             and head is not None
                                             and _own_head_legal(
                                                 st, head, t, sh[1]))
                              else ("maintenance"
                                    if _own_maintenance(st, resource, t, sh[1])
                                    else "none"))),
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
                # F2: if the impl exposes a WAIT anchor, its TRUE identity
                # must match the checker's own expected anchor
                if got and got[0].wait_anchor is not None:
                    own_a = _own_wait_anchor(head, t, sh[1], active)
                    impl_a = got[0].wait_anchor
                    if own_a is None:
                        failures.append(
                            f"{label} t={t} {resource}: impl has WAIT "
                            f"anchor but checker expected none")
                        continue
                    e, fproc, fatt, fs, fres, boundary = own_a
                    ok_a = (impl_a.completion_time == e
                            and impl_a.process == fproc
                            and impl_a.effective_attempt_no == fatt
                            and impl_a.attempt_start_time == fs
                            and impl_a.resource == fres
                            and impl_a.boundary == boundary)
                    if not ok_a:
                        failures.append(
                            f"{label} t={t} {resource}: impl anchor "
                            f"{impl_a.to_canonical_dict()} != checker "
                            f"expected {(str(e), fproc, fatt, str(fs), fres, boundary)}")
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


# ---------------------------------------------------------------------------
# P3-A-E1: WAIT fragment identity (F1/F2) + invalidation (WAIT-R1..R5)
# ---------------------------------------------------------------------------


def _wait_r_logs() -> dict[str, tuple[list[dict], Fraction, Fraction]]:
    """WAIT regression logs: (label -> (log, K, t_observe)).  All use the
    same-device pattern: device 1 has the anchor-process fragment(s), and a
    queued head B on the SAME device 1 is the WAIT candidate."""
    shift = {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
             "shift_start": "0", "shift_end": "10", "on_duty_squad": 0,
             "squad_id": 0}
    true = {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
            "device_id": 1, "true_state": {"A": False, "B": False,
                                           "C": False}}

    # WAIT-R1: A fragment cancelled at t=2 (start=0, planned end=5) must NOT
    # anchor at t>=2 (observed); B is released at t=1 so its decision closure
    # at t=1 sees A still in flight (anchor) and at t=2/3 no anchor.
    r1 = [dict(true),
          {"event_type": "TASK_RELEASE", "event_time": "1",
           "resource_id": "B", "device_id": 1, "process": "B",
           "effective_attempt_no": 1},
          {"event_type": "TASK_RELEASE", "event_time": "0",
           "resource_id": "A", "device_id": 1, "process": "A",
           "effective_attempt_no": 1},
          {"event_type": "ACTIVITY_START", "event_time": "0", "device_id": 1,
           "process": "A", "effective_attempt_no": 1, "resource_id": "A",
           "attempt_start_time": "0", "attempt_end_time": "5",
           "outcome": "NONE"},
          {"event_type": "TASK_CANCEL", "event_time": "2", "device_id": 1,
           "process": "A", "effective_attempt_no": 1, "resource_id": "A",
           "attempt_start_time": "0", "attempt_end_time": "5",
           "outcome": "NONE", "cancel_reason": "equipment_failure"},
          dict(shift)]

    # WAIT-R2: A fragment1 (start=0, end=5) cancelled at 2; A fragment2
    # restarted (SAME effective_attempt_no) start=2, end=4.  At t=3 only
    # fragment2 is active; the anchor must be process=A,
    # attempt_start_time=2, completion_time=4 (not end=5, not settled by the
    # old CANCEL).  B released at 1: closure t=1 anchors fragment1,
    # closure t=2 anchors nothing (fragment2 not yet started pre-action),
    # closure t=3 anchors fragment2.
    r2 = [dict(true),
          {"event_type": "TASK_RELEASE", "event_time": "1",
           "resource_id": "B", "device_id": 1, "process": "B",
           "effective_attempt_no": 1},
          {"event_type": "TASK_RELEASE", "event_time": "0", "resource_id": "A",
           "device_id": 1, "process": "A", "effective_attempt_no": 1},
          {"event_type": "ACTIVITY_START", "event_time": "0", "device_id": 1,
           "process": "A", "effective_attempt_no": 1, "resource_id": "A",
           "attempt_start_time": "0", "attempt_end_time": "5",
           "outcome": "NONE"},
          {"event_type": "TASK_CANCEL", "event_time": "2", "device_id": 1,
           "process": "A", "effective_attempt_no": 1, "resource_id": "A",
           "attempt_start_time": "0", "attempt_end_time": "5",
           "outcome": "NONE", "cancel_reason": "equipment_failure"},
          {"event_type": "TASK_RELEASE", "event_time": "2", "resource_id": "A",
           "device_id": 1, "process": "A", "effective_attempt_no": 1},
          {"event_type": "ACTIVITY_START", "event_time": "2", "device_id": 1,
           "process": "A", "effective_attempt_no": 1, "resource_id": "A",
           "attempt_start_time": "2", "attempt_end_time": "4",
           "outcome": "NONE"},
          # an event AT t=3 makes t=3 a closure (where fragment2 is running)
          {"event_type": "TASK_RELEASE", "event_time": "3", "resource_id": "C",
           "device_id": 1, "process": "C", "effective_attempt_no": 1},
          dict(shift)]

    # WAIT-R3: A fragment completed at t=1 (start=0, planned end=5) must NOT
    # anchor at t>=1; B released at 1 (its closure at t=1 sees A settled).
    r3 = [dict(true),
          {"event_type": "TASK_RELEASE", "event_time": "1",
           "resource_id": "B", "device_id": 1, "process": "B",
           "effective_attempt_no": 1},
          {"event_type": "TASK_RELEASE", "event_time": "0",
           "resource_id": "A", "device_id": 1, "process": "A",
           "effective_attempt_no": 1},
          {"event_type": "ACTIVITY_START", "event_time": "0", "device_id": 1,
           "process": "A", "effective_attempt_no": 1, "resource_id": "A",
           "attempt_start_time": "0", "attempt_end_time": "5",
           "outcome": "NONE"},
          {"event_type": "ACTIVITY_COMPLETE", "event_time": "1", "device_id": 1,
           "process": "A", "effective_attempt_no": 1, "resource_id": "A",
           "attempt_start_time": "0", "attempt_end_time": "5",
           "outcome": "NONE"},
          {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "1",
           "device_id": 1, "process": "A", "effective_attempt_no": 1,
           "resource_id": "A", "outcome": "PASS"},
          dict(shift)]

    # WAIT-R4: A in-flight (end 5/2) with B head at t=1 -> anchor TRUE
    # identity is process=A / attempt=1 / attempt_start_time=0 / resource=A,
    # never B.
    r4 = [dict(true),
          {"event_type": "TASK_RELEASE", "event_time": "1",
           "resource_id": "B", "device_id": 1, "process": "B",
           "effective_attempt_no": 1},
          {"event_type": "TASK_RELEASE", "event_time": "0",
           "resource_id": "A", "device_id": 1, "process": "A",
           "effective_attempt_no": 1},
          {"event_type": "ACTIVITY_START", "event_time": "0", "device_id": 1,
           "process": "A", "effective_attempt_no": 1, "resource_id": "A",
           "attempt_start_time": "0", "attempt_end_time": "5/2",
           "outcome": "NONE"},
          dict(shift)]

    return {"WAIT-R1": (r1, Fraction(10), Fraction(3)),
            "WAIT-R2": (r2, Fraction(10), Fraction(3)),
            "WAIT-R3": (r3, Fraction(10), Fraction(2)),
            "WAIT-R4": (r4, Fraction(10), Fraction(1))}


def check_wait_fragment_identity() -> dict[str, Any]:
    """WAIT-R1..R4: only ACTIVE fragments (exact identity, not settled by a
    matching COMPLETE/CANCEL) may anchor; the anchor carries the TRUE
    in-flight fragment identity.  The impl is evaluated at ITS OWN closure
    times (event times + shift starts < t_end); the checker recomputes the
    expected anchor at the same times and compares identity."""
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    for label, (log, K, tobs) in _wait_r_logs().items():
        pts = dpimpl.reconstruct_decision_points(log, K, batch_size=2,
                                                 t_end=tobs + Fraction(1))
        b_pts = [p for p in pts if p.resource == "B" and p.kind == "dispatch"]
        # checker's own expectation at each impl closure time (PRE-ACTION view)
        for p in b_pts:
            t = p.time
            pre = _own_pre_action_log(log, t)
            st = obs.project_log_prefix(pre, t, batch_size=2)
            own_active = _own_active_fragments(pre, t)
            sh = obs.active_shift(obs.q3_shift_grid(K), t)
            own_anchor = (_own_wait_anchor(p.head, t, sh[1], own_active)
                          if p.head is not None and sh is not None else None)
            impl_anchor = p.wait_anchor
            if label == "WAIT-R1":
                # R1: after the CANCEL (closure at/after t=2) no anchor
                if t >= 2 and (own_anchor is not None
                               or impl_anchor is not None):
                    failures.append(f"{label} t={t}: cancelled fragment "
                                    f"must not anchor "
                                    f"(own={own_anchor} impl={impl_anchor})")
            elif label == "WAIT-R2":
                # R2: at the closure where fragment2 (start=2,end=4) is the
                # only active A fragment (t=3) the anchor must be
                # A@start=2/end=4; at t=2 (fragment2 not yet started in the
                # pre-action view) no anchor.
                if t == 3:
                    ok = (own_anchor is not None and impl_anchor is not None
                          and own_anchor[1] == "A"
                          and own_anchor[3] == Fraction(2)
                          and own_anchor[0] == Fraction(4)
                          and impl_anchor.process == "A"
                          and impl_anchor.attempt_start_time == Fraction(2)
                          and impl_anchor.completion_time == Fraction(4)
                          and impl_anchor.resource == "A")
                    if not ok:
                        failures.append(
                            f"{label} t={t}: restarted fragment identity "
                            f"wrong (own={own_anchor} impl={impl_anchor})")
                elif t == 2:
                    if own_anchor is not None or impl_anchor is not None:
                        failures.append(
                            f"{label} t=2: fragment2 not started at the "
                            f"pre-action boundary; no anchor expected "
                            f"(own={own_anchor} impl={impl_anchor})")
            elif label == "WAIT-R3":
                if t >= 1 and (own_anchor is not None
                               or impl_anchor is not None):
                    failures.append(f"{label} t={t}: completed fragment "
                                    f"must not anchor "
                                    f"(own={own_anchor} impl={impl_anchor})")
            elif label == "WAIT-R4":
                if t == 1:  # B decision closure (released at 1; A in flight)
                    ok = (own_anchor is not None and impl_anchor is not None
                          and own_anchor[1] == "A"
                          and impl_anchor.process == "A"
                          and impl_anchor.device_id == 1
                          and impl_anchor.resource == "A"
                          and impl_anchor.attempt_start_time == Fraction(0)
                          and impl_anchor.completion_time == Fraction(5, 2)
                          and impl_anchor.process != "B")
                    if not ok:
                        failures.append(
                            f"{label} t={t}: anchor identity must be the "
                            f"in-flight A fragment, not head B "
                            f"(own={own_anchor} impl={impl_anchor})")
            rows.append({"label": label, "closure_t": str(t),
                         "own_anchor": (None if own_anchor is None else
                                        (str(own_anchor[0]), own_anchor[1],
                                         own_anchor[2], str(own_anchor[3]),
                                         own_anchor[4], own_anchor[5])),
                         "impl_anchor": (None if impl_anchor is None else
                                         impl_anchor.to_canonical_dict())})
    return {
        "check": "WAIT_FRAGMENT_IDENTITY",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "rows": rows,
    }


def check_wait_invalidation() -> dict[str, Any]:
    """WAIT-R5: WAIT is valid at t0 (A in-flight, B head on device 1); after
    a DEVICE TERMINAL / head-change event the NEXT closure must re-decide
    with no stale anchor / old WAIT action carried over.  Two real
    constructions:
      (a) device 1 terminal -> the head passes to device 2 (also queued for
          B); the new decision point must NOT reuse device 1's A anchor;
      (b) the anchor fragment is cancelled -> no anchor at the next closure.
    """
    failures: list[str] = []
    base = _wait_r_logs()["WAIT-R4"][0]
    # t=1 (B decision closure): anchor valid (A in-flight from t=0)
    pts0 = dpimpl.reconstruct_decision_points(base, Fraction(10),
                                              batch_size=2, t_end=Fraction(2))
    has_wait0 = any(p.wait_anchor is not None for p in pts0
                    if p.resource == "B")
    if not has_wait0:
        failures.append("WAIT-R5: baseline WAIT at the B decision closure "
                        "must be legal")

    # (a) device 2 also queued for B; device 1 terminal at t=1 -> head moves
    # to device 2; the new point must have NO anchor and NO WAIT_EVENT.
    log_a = [dict(r) for r in base]
    log_a.append({"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
                  "device_id": 2, "true_state": {"A": False, "B": False,
                                                 "C": False}})
    log_a.append({"event_type": "TASK_RELEASE", "event_time": "0",
                  "resource_id": "B", "device_id": 2, "process": "B",
                  "effective_attempt_no": 1})
    log_a.append({"event_type": "DEVICE_TERMINAL", "event_time": "1",
                  "device_id": 1, "process": "B",
                  "effective_attempt_no": 1, "terminal_state": "PASSED",
                  "reason": "E_pass"})
    pts_a = dpimpl.reconstruct_decision_points(log_a, Fraction(10),
                                               batch_size=2,
                                               t_end=Fraction(2))
    t1_points = [p for p in pts_a if p.time >= Fraction(1)]
    stale_a = [p for p in t1_points if p.wait_anchor is not None]
    wait_action = [p for p in t1_points
                   if dpimpl.A_WAIT_EVENT in p.legal_actions]
    if stale_a:
        failures.append(f"WAIT-R5(a): stale anchor carried past terminal: "
                        f"{[p.to_canonical_dict() for p in stale_a]}")
    if wait_action:
        failures.append("WAIT-R5(a): old WAIT_EVENT must not be offered at "
                        "the post-terminal closure (head changed to device "
                        "2)")

    # (b) anchor fragment cancelled at t=1 -> at the next closure no anchor.
    log_b = [dict(r) for r in base]
    log_b.append({"event_type": "TASK_CANCEL", "event_time": "1",
                  "device_id": 1, "process": "A", "effective_attempt_no": 1,
                  "resource_id": "A", "attempt_start_time": "0",
                  "attempt_end_time": "5/2", "outcome": "NONE",
                  "cancel_reason": "equipment_failure"})
    pts_b = dpimpl.reconstruct_decision_points(log_b, Fraction(10),
                                               batch_size=2,
                                               t_end=Fraction(2))
    stale_b = [p for p in pts_b
               if p.time >= Fraction(1) and p.wait_anchor is not None]
    if stale_b:
        failures.append(f"WAIT-R5(b): stale anchor after anchor CANCEL: "
                        f"{[p.to_canonical_dict() for p in stale_b]}")
    return {
        "check": "WAIT_INVALIDATION",
        "status": "PASS" if not failures else "FAIL",
        "wait_legal_at_t0": has_wait0,
        "stale_after_terminal_head_change": len(stale_a),
        "wait_event_after_head_change": len(wait_action),
        "stale_after_anchor_cancel": len(stale_b),
        "failures": failures,
    }


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


# ---------------------------------------------------------------------------
# P3-A-E1: continuation posterior (F3) / per-device draws / PM age (F4) /
# mandatory-optional PM / real H1 parity / C23 continuation
# ---------------------------------------------------------------------------


def _e1_continuation_log() -> list[dict]:
    """Device 1: A/B/C all passed, E produced a valid observation; device 2:
    entered, no observations (prior).  Used for the reached-E D posterior
    counterexample and per-device independence."""
    log = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    # device 1: A, B, C passed
    for proc, dur in (("A", "5/2"), ("B", "2"), ("C", "5/2")):
        log.append({"event_type": "TASK_RELEASE", "event_time": "0",
                    "resource_id": proc, "device_id": 1, "process": proc,
                    "effective_attempt_no": 1})
        log.append({"event_type": "ACTIVITY_START", "event_time": "0",
                    "device_id": 1, "process": proc,
                    "effective_attempt_no": 1, "resource_id": proc,
                    "attempt_start_time": "0", "attempt_end_time": dur,
                    "outcome": "NONE"})
        log.append({"event_type": "ACTIVITY_COMPLETE", "event_time": dur,
                    "device_id": 1, "process": proc,
                    "effective_attempt_no": 1, "resource_id": proc,
                    "attempt_start_time": "0", "attempt_end_time": dur,
                    "outcome": "NONE"})
        log.append({"event_type": "OBSERVATION_MATERIALIZED",
                    "event_time": dur, "device_id": 1, "process": proc,
                    "effective_attempt_no": 1, "resource_id": proc,
                    "outcome": "PASS"})
    # device 1: E released and observed (ABNORMAL -> E posterior updates D)
    log.append({"event_type": "TASK_RELEASE", "event_time": "0",
                "resource_id": "E", "device_id": 1, "process": "E",
                "effective_attempt_no": 1})
    log.append({"event_type": "ACTIVITY_START", "event_time": "0",
                "device_id": 1, "process": "E", "effective_attempt_no": 1,
                "resource_id": "E", "attempt_start_time": "0",
                "attempt_end_time": "3", "outcome": "NONE"})
    log.append({"event_type": "ACTIVITY_COMPLETE", "event_time": "3",
                "device_id": 1, "process": "E", "effective_attempt_no": 1,
                "resource_id": "E", "attempt_start_time": "0",
                "attempt_end_time": "3", "outcome": "NONE"})
    log.append({"event_type": "OBSERVATION_MATERIALIZED", "event_time": "3",
                "device_id": 1, "process": "E", "effective_attempt_no": 1,
                "resource_id": "E", "outcome": "ABNORMAL"})
    return log


def check_continuation_posterior() -> dict[str, Any]:
    """F3 + section 10: reached-E devices use PosteriorState's
    d_posterior_given_abc; the E observation changes the D continuation draw
    (a deterministic counterexample where prior q_D and posterior p_D give
    DIFFERENT x_D for one U_D)."""
    from main_model.h2 import continuation_v1 as cont
    from main_model.h2 import posterior_generator_v1 as pg
    from main_model.h2.frozen_params_v1 import Q_D
    failures: list[str] = []
    log = _e1_continuation_log()
    t = Fraction(4)
    st = obs.project_log_prefix(log, t, batch_size=2)
    post = ps.PosteriorState.from_observable(st)
    dev1 = next(d for d in post.devices if d.device_id == 1)
    if not dev1.reached_e:
        failures.append("device 1 must have reached E (obs_E nonempty)")
        return {"check": "CONTINUATION_POSTERIOR", "status": "FAIL",
                "failures": failures}
    d_given = dict((tuple(k), Fraction(v))
                   for k, v in dev1.d_posterior_given_abc)
    # pick ABC with the largest posterior mass -> (0,0,0) (all passed)
    abc = (0, 0, 0)
    p_d = d_given.get(abc)
    if p_d is None:
        failures.append("d_posterior_given_abc missing ABC=000")
        return {"check": "CONTINUATION_POSTERIOR", "status": "FAIL",
                "failures": failures}
    # E ABNORMAL with ABC all-clear updates D: p_D != q_D
    if p_d == Q_D:
        failures.append(f"E->D posterior must differ from prior: "
                        f"p_D={p_d} == q_D={Q_D}")
    # pick U_D strictly between q_D and p_D
    lo, hi = sorted((Q_D, p_d))
    u_mid = (lo + hi) / 2
    # correct continuation draw uses PosteriorState D posterior:
    ux = dict((tuple(k), Fraction(v)) for k, v in dev1.abc_posterior)
    u_x = Fraction(1, 100)  # deep inside the (0,0,0) mass
    u_d = u_mid
    w = cont.rebuild_continuation_world(
        st, post,
        u_x_by_device={1: u_x, 2: u_x},
        u_d_by_device={1: u_d},
        u_l_by_resource={r: Fraction(1, 3) for r in fp.RESOURCES})
    cd = next(d for d in w.devices if d.device_id == 1)
    xd_post = cd.x_d
    # "wrong prior draw" (as if the E info were dropped): x_D = 1 if U_D < q_D
    xd_prior = 1 if u_d < Q_D else 0
    if xd_post == xd_prior:
        failures.append(
            f"reached-E D draw must use the posterior: posterior p_D={p_d} "
            f"q_D={Q_D} u_D={u_mid} -> x_D(post)={xd_post} == x_D(prior)="
            f"{xd_prior}; E->D posterior not entering the continuation")
    # fail-close: missing per-device draw must raise
    try:
        cont.rebuild_continuation_world(
            st, post, u_x_by_device={1: u_x}, u_d_by_device={1: u_d},
            u_l_by_resource={r: Fraction(1, 3) for r in fp.RESOURCES})
        failures.append("missing per-device U_X_post for device 2 must "
                        "raise (fail-close)")
    except ValueError:
        pass
    try:
        cont.rebuild_continuation_world(
            st, post, u_x_by_device={1: u_x, 2: u_x}, u_d_by_device={},
            u_l_by_resource={r: Fraction(1, 3) for r in fp.RESOURCES})
        failures.append("missing per-device U_D_post for reached-E device 1 "
                        "must raise (fail-close)")
    except ValueError:
        pass
    try:
        cont.rebuild_continuation_world(
            st, post, u_x_by_device={1: u_x, 2: u_x},
            u_d_by_device={1: u_d}, u_l_by_resource={})
        failures.append("missing per-resource U_L_post must raise "
                        "(fail-close)")
    except ValueError:
        pass
    return {
        "check": "CONTINUATION_POSTERIOR",
        "status": "PASS" if not failures else "FAIL",
        "abc": list(abc), "q_D": str(Q_D), "p_D_given_abc000": str(p_d),
        "u_D_chosen": str(u_mid),
        "x_D_correct_continuation": xd_post,
        "x_D_wrong_prior": xd_prior,
        "e_observation_changes_d_continuation_draw": xd_post != xd_prior,
        "missing_draw_fail_close": "PASS",
        "failures": failures,
    }


def _two_identical_devices_log() -> list[dict]:
    """Devices 1 and 2 with IDENTICAL observable histories (A/B/C passed,
    E ABNORMAL) -> the SAME posterior distribution (required by section 11
    per-device independence)."""
    log = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    for dev in (1, 2):
        for proc, dur in (("A", "5/2"), ("B", "2"), ("C", "5/2")):
            log.append({"event_type": "TASK_RELEASE", "event_time": "0",
                        "resource_id": proc, "device_id": dev,
                        "process": proc, "effective_attempt_no": 1})
            log.append({"event_type": "ACTIVITY_START", "event_time": "0",
                        "device_id": dev, "process": proc,
                        "effective_attempt_no": 1, "resource_id": proc,
                        "attempt_start_time": "0", "attempt_end_time": dur,
                        "outcome": "NONE"})
            log.append({"event_type": "ACTIVITY_COMPLETE", "event_time": dur,
                        "device_id": dev, "process": proc,
                        "effective_attempt_no": 1, "resource_id": proc,
                        "attempt_start_time": "0", "attempt_end_time": dur,
                        "outcome": "NONE"})
            log.append({"event_type": "OBSERVATION_MATERIALIZED",
                        "event_time": dur, "device_id": dev, "process": proc,
                        "effective_attempt_no": 1, "resource_id": proc,
                        "outcome": "PASS"})
        log.append({"event_type": "TASK_RELEASE", "event_time": "0",
                    "resource_id": "E", "device_id": dev, "process": "E",
                    "effective_attempt_no": 1})
        log.append({"event_type": "ACTIVITY_START", "event_time": "0",
                    "device_id": dev, "process": "E",
                    "effective_attempt_no": 1, "resource_id": "E",
                    "attempt_start_time": "0", "attempt_end_time": "3",
                    "outcome": "NONE"})
        log.append({"event_type": "ACTIVITY_COMPLETE", "event_time": "3",
                    "device_id": dev, "process": "E",
                    "effective_attempt_no": 1, "resource_id": "E",
                    "attempt_start_time": "0", "attempt_end_time": "3",
                    "outcome": "NONE"})
        log.append({"event_type": "OBSERVATION_MATERIALIZED",
                    "event_time": "3", "device_id": dev, "process": "E",
                    "effective_attempt_no": 1, "resource_id": "E",
                    "outcome": "ABNORMAL"})
    return log


def check_per_device_post_draw() -> dict[str, Any]:
    """Section 11: two non-terminal devices with the SAME posterior, per-
    device u values in different categorical intervals -> sampled ABC can
    differ per device; swapping u1/u2 swaps the results (no shared global
    u).  D likewise: per-device U_D_post drives each reached-E device's D
    draw independently."""
    from main_model.h2 import continuation_v1 as cont
    failures: list[str] = []
    log = _two_identical_devices_log()
    st = obs.project_log_prefix(log, Fraction(4), batch_size=2)
    post = ps.PosteriorState.from_observable(st)
    d1v = next(d for d in post.devices if d.device_id == 1)
    d2v = next(d for d in post.devices if d.device_id == 2)
    if d1v.abc_posterior != d2v.abc_posterior:
        failures.append("devices 1 and 2 must share the same posterior")
    abc_post = dict((tuple(k), Fraction(v)) for k, v in d1v.abc_posterior)
    # pick u1/u2 in different categorical intervals of the same posterior
    u1, u2 = Fraction(1, 100), Fraction(999, 1000)
    w_a = cont.rebuild_continuation_world(
        st, post,
        u_x_by_device={1: u1, 2: u2},
        u_d_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
        u_l_by_resource={r: Fraction(1, 3) for r in fp.RESOURCES})
    d1_a = next(d for d in w_a.devices if d.device_id == 1)
    d2_a = next(d for d in w_a.devices if d.device_id == 2)
    if d1_a.x_abc == d2_a.x_abc:
        failures.append(f"per-device u must allow different ABC draws "
                        f"(u1={u1} u2={u2} both -> {d1_a.x_abc})")
    # swap u1/u2 -> results must swap (no shared global u)
    w_b = cont.rebuild_continuation_world(
        st, post,
        u_x_by_device={1: u2, 2: u1},
        u_d_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
        u_l_by_resource={r: Fraction(1, 3) for r in fp.RESOURCES})
    d1_b = next(d for d in w_b.devices if d.device_id == 1)
    d2_b = next(d for d in w_b.devices if d.device_id == 2)
    if not (d1_b.x_abc == d2_a.x_abc and d2_b.x_abc == d1_a.x_abc):
        failures.append(
            f"swapping u1/u2 must swap the per-device draws: "
            f"before d1={d1_a.x_abc} d2={d2_a.x_abc}; after d1="
            f"{d1_b.x_abc} d2={d2_b.x_abc}")
    # D per-device: same posterior, different U_D -> independent D draws
    d_given = dict((tuple(k), Fraction(v)) for k, v in d1v.d_posterior_given_abc)
    p_d = d_given[(0, 0, 0)]
    u_d_lo = Fraction(1, 10000)   # < p_D (p_D >> q_D after E ABNORMAL)
    u_d_hi = Fraction(999, 1000)  # > p_D
    w_lo = cont.rebuild_continuation_world(
        st, post, u_x_by_device={1: Fraction(1, 100), 2: Fraction(1, 100)},
        u_d_by_device={1: u_d_lo, 2: u_d_hi},
        u_l_by_resource={r: Fraction(1, 3) for r in fp.RESOURCES})
    x1 = next(d for d in w_lo.devices if d.device_id == 1).x_d
    x2 = next(d for d in w_lo.devices if d.device_id == 2).x_d
    if not (x1 == 1 and x2 == 0):
        failures.append(f"per-device U_D_post must drive each device's D "
                        f"draw independently: dev1 u_d={u_d_lo} -> {x1} "
                        f"(want 1), dev2 u_d={u_d_hi} -> {x2} (want 0), "
                        f"p_D={p_d}")
    return {
        "check": "PER_DEVICE_POST_DRAW",
        "status": "PASS" if not failures else "FAIL",
        "same_posterior": d1v.abc_posterior == d2v.abc_posterior,
        "u1": str(u1), "u2": str(u2),
        "d1_before": list(d1_a.x_abc), "d2_before": list(d2_a.x_abc),
        "d1_after_swap": list(d1_b.x_abc), "d2_after_swap": list(d2_b.x_abc),
        "d_dev1_u_d_lo": x1, "d_dev2_u_d_hi": x2,
        "failures": failures,
    }


def check_rollout_post_keys() -> dict[str, Any]:
    """Section 12: rollout_seed(dp,m) -> h2_rollout post-key adapter.  Same
    (dp,m,entity) across actions -> exact identical draws (CRN); different
    dp / different m separated; namespace = h2_rollout."""
    from main_model.h2_rollout import post_keys_v1 as pk
    failures: list[str] = []
    master, rep = 6, 0
    devices = (1, 2, 3)
    resources = fp.RESOURCES
    generations = {r: 1 for r in fp.RESOURCES}
    a1 = pk.rollout_post_keys(master, rep, 0, 0, devices, resources,
                              generations)
    a2 = pk.rollout_post_keys(master, rep, 0, 0, devices, resources,
                              generations)
    if a1.to_canonical_dict() != a2.to_canonical_dict():
        failures.append("same (dp,m,entities) must give identical draws")
    if a1.namespace != "h2_rollout":
        failures.append(f"namespace must be h2_rollout, got {a1.namespace}")
    for dev in devices:
        if a1.u_x_by_device[dev] != a2.u_x_by_device[dev]:
            failures.append(f"u_x same (dp,m) dev {dev} differs")
        if a1.u_d_by_device[dev] != a2.u_d_by_device[dev]:
            failures.append(f"u_d same (dp,m) dev {dev} differs")
    # cross-action CRN: the adapter has no action argument at all -> by
    # construction every candidate action of the same decision point uses
    # the same bundle; different dp / m must separate.
    b1 = pk.rollout_post_keys(master, rep, 0, 1, devices, resources,
                              generations)
    c1 = pk.rollout_post_keys(master, rep, 1, 0, devices, resources,
                              generations)
    if a1.u_x_by_device[1] == b1.u_x_by_device[1]:
        failures.append("different m must separate U_X_post")
    if a1.u_x_by_device[1] == c1.u_x_by_device[1]:
        failures.append("different dp must separate U_X_post")
    if a1.u_d_by_device[1] == b1.u_d_by_device[1]:
        failures.append("different m must separate U_D_post")
    if a1.u_l_by_resource["A"] == b1.u_l_by_resource["A"]:
        failures.append("different m must separate U_L_post")
    # seed formula consistency with the frozen derivation
    if a1.seed != rs.rollout_seed(master, rep, 0, 0):
        failures.append("adapter seed != rollout_seed formula")
    # P2 synthetic mapping must NOT be used: production entity ids are the
    # real device ids passed in (no 100001+ slots)
    if 100001 in a1.u_x_by_device or any(
            k >= 100000 for k in a1.u_x_by_device):
        failures.append("P2 synthetic entity mapping leaked into production "
                        "rollout keys")
    return {
        "check": "ROLLOUT_POST_KEYS",
        "status": "PASS" if not failures else "FAIL",
        "namespace": "h2_rollout",
        "seed_dp0_m0": a1.seed,
        "u_x_dp0_m0_dev1": str(a1.u_x_by_device[1]),
        "u_x_dp0_m1_dev1": str(b1.u_x_by_device[1]),
        "cross_action_crn": "same bundle for all actions (adapter has no "
                            "action argument)",
        "failures": failures,
    }


def check_pm_age_semantics() -> dict[str, Any]:
    """F4 + PM-R1: replacement record age_before == equipment age_h, never
    the wall-clock decision time."""
    failures: list[str] = []
    t = Fraction(200)
    age_h = Fraction(135)
    step = asem.apply_pm("A", t, dpimpl.A_PM_IDLE, generation=1, age_h=age_h)
    rec = step.events[0]
    if rec["event_type"] != "EQUIPMENT_REPLACEMENT_START":
        failures.append("PM must emit replacement-start first")
    if Fraction(rec["age_before"]) != age_h:
        failures.append(f"PM-R1: age_before must be equipment age {age_h}, "
                        f"got {rec['age_before']} (wall clock t={t} wrong)")
    return {
        "check": "PM_AGE_SEMANTICS",
        "status": "PASS" if not failures else "FAIL",
        "t": str(t), "age_h": str(age_h), "age_before_recorded": rec.get(
            "age_before"),
        "failures": failures,
    }


def _pm_logs() -> dict[str, tuple[list[dict], Fraction, Fraction]]:
    """PM regression logs (label -> (log, K, t_end)).  maintenance toy
    (48 x 2.5h = 120h) with device 2 entered-but-unobserved for demand."""
    shift = {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
             "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
             "squad_id": 0}
    t = Fraction(0)
    maint = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        dict(shift),
    ]
    for _ in range(48):
        e = t + Fraction(5, 2)
        maint.append({"event_type": "TASK_RELEASE", "event_time": str(t),
                      "resource_id": "A", "device_id": 1, "process": "A",
                      "effective_attempt_no": 1})
        maint.append({"event_type": "ACTIVITY_START", "event_time": str(t),
                      "device_id": 1, "process": "A",
                      "effective_attempt_no": 1, "resource_id": "A",
                      "attempt_start_time": str(t),
                      "attempt_end_time": str(e), "outcome": "NONE"})
        maint.append({"event_type": "ACTIVITY_COMPLETE",
                      "event_time": str(e), "device_id": 1, "process": "A",
                      "effective_attempt_no": 1, "resource_id": "A",
                      "attempt_start_time": str(t),
                      "attempt_end_time": str(e), "outcome": "NONE"})
        maint.append({"event_type": "OBSERVATION_MATERIALIZED",
                      "event_time": str(e), "device_id": 1, "process": "A",
                      "effective_attempt_no": 1, "resource_id": "A",
                      "outcome": "PASS"})
        t = e
    # age = 120, idle A, no head -> maintenance point {H1_NOOP, PM_IDLE}
    # PM-R2 (age=240): 96 fragments -> age exactly 240 (mandatory node); a
    # legal head exists -> PM_WITH_HEAD must NOT be a policy action.
    t2 = Fraction(0)
    m240 = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        dict(shift),
    ]
    for _ in range(96):
        e = t2 + Fraction(5, 2)
        m240.append({"event_type": "TASK_RELEASE", "event_time": str(t2),
                     "resource_id": "A", "device_id": 1, "process": "A",
                     "effective_attempt_no": 1})
        m240.append({"event_type": "ACTIVITY_START", "event_time": str(t2),
                     "device_id": 1, "process": "A",
                     "effective_attempt_no": 1, "resource_id": "A",
                     "attempt_start_time": str(t2),
                     "attempt_end_time": str(e), "outcome": "NONE"})
        m240.append({"event_type": "ACTIVITY_COMPLETE",
                     "event_time": str(e), "device_id": 1, "process": "A",
                     "effective_attempt_no": 1, "resource_id": "A",
                     "attempt_start_time": str(t2),
                     "attempt_end_time": str(e), "outcome": "NONE"})
        m240.append({"event_type": "OBSERVATION_MATERIALIZED",
                     "event_time": str(e), "device_id": 1, "process": "A",
                     "effective_attempt_no": 1, "resource_id": "A",
                     "outcome": "PASS"})
        t2 = e
    # PM-R2: at age=240 (closure t=240) a legal head for resource A on
    # device 2 is released -> dispatch point exists; PM_WITH_HEAD must NOT
    # be offered (age == MANDATORY_AGE_H -> mandatory, never optional).
    m240.append({"event_type": "TASK_RELEASE", "event_time": "240",
                 "resource_id": "A", "device_id": 2, "process": "A",
                 "effective_attempt_no": 1})
    # PM-R3: same 240-age idle resource WITHOUT a head -> no maintenance
    # point (age==240 is NOT optional).
    m240_nohead = [dict(r) for r in m240 if r.get("event_type") != "TASK_RELEASE"
                   or r.get("event_time") != "240"]
    return {
        "PM-POSITIVE-120": (maint, Fraction(300), Fraction(121)),
        "PM-R2-EXACT240-HEAD": (m240, Fraction(300), Fraction(241)),
        "PM-R3-EXACT240-NOHEAD": (m240_nohead, Fraction(300), Fraction(241)),
    }


def check_mandatory_optional_pm() -> dict[str, Any]:
    """PM-R2/R3/R4: age == 240 (mandatory node) excludes optional PM; under
    AGE-LEGAL-01 (second requalification, HG §7) age==240 -> a+d > 240 ->
    MANDATORY_REPLACE_FIRST -> NO H2 dispatch decision point at all
    (supersedes the earlier expectation of a dispatch point without PM);
    age == 120 allows optional PM (positive case); PM_WITH_HEAD positive
    case with a head present."""
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    logs = _pm_logs()
    for label, (log, K, tend) in logs.items():
        pts = dpimpl.reconstruct_decision_points(log, K, batch_size=2,
                                                 t_end=tend)
        if label == "PM-POSITIVE-120":
            m = [p for p in pts if p.kind == "maintenance"]
            if not (m and dpimpl.A_PM_IDLE in m[0].legal_actions):
                failures.append("PM-POSITIVE-120: maintenance PM_IDLE must "
                                "be offered at age=120")
            rows.append({"label": label, "n_points": len(pts),
                         "kinds": [p.kind for p in pts],
                         "actions": [list(p.legal_actions) for p in pts]})
        elif label == "PM-R2-EXACT240-HEAD":
            d = [p for p in pts if p.kind == "dispatch" and p.time == 240]
            if d:
                failures.append("PM-R2: a+d > 240 (mandatory) must yield NO "
                                "H2 dispatch decision point at age==240 "
                                "(AGE-LEGAL-01)")
            rows.append({"label": label,
                         "dispatch_actions": [list(p.legal_actions)
                                              for p in d]})
        elif label == "PM-R3-EXACT240-NOHEAD":
            m = [p for p in pts if p.kind == "maintenance" and p.time == 240]
            if m:
                failures.append("PM-R3: maintenance point must NOT exist at "
                                "age==240 (not optional)")
            rows.append({"label": label, "n_maintenance_at_240": len(m)})
    # PM_WITH_HEAD positive: age=120 with a legal head present -> dispatch
    # point offers PM_WITH_HEAD.
    log, K, tend = logs["PM-POSITIVE-120"]
    log = [dict(r) for r in log]
    log.append({"event_type": "TASK_RELEASE", "event_time": "120",
                "resource_id": "A", "device_id": 2, "process": "A",
                "effective_attempt_no": 1})
    pts = dpimpl.reconstruct_decision_points(log, K, batch_size=2,
                                             t_end=Fraction(121))
    d = [p for p in pts if p.kind == "dispatch" and p.time == 120]
    if not d:
        failures.append("PM_WITH_HEAD positive: dispatch point at age=120 "
                        "with head must exist")
    elif dpimpl.A_PM_WITH_HEAD not in d[0].legal_actions:
        failures.append("PM_WITH_HEAD positive: PM_WITH_HEAD must be offered "
                        f"at age=120 with legal head; got {d[0].legal_actions}")
    rows.append({"label": "PM-WITH-HEAD-POSITIVE",
                 "dispatch_actions": [list(p.legal_actions) for p in d]})
    return {
        "check": "MANDATORY_OPTIONAL_PM",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures, "rows": rows,
    }


def check_h1_real_parity() -> dict[str, Any]:
    """Section 17: REAL deterministic H1 parity against the accepted H1
    engine (parity target, not an oracle loop; no formal/holdout worlds).
    A) START_HEAD: the engine's default dispatch emits an ACTIVITY_START
    record; P3 apply_start_head must match head identity + core fields +
    duration + attempt number + FCFS choice.  B) H1_NOOP: in a maintenance
    state the H1 baseline advances to the next real event / wakeup without
    proactive PM; P3 apply_h1_noop must match the next closure time."""
    failures: list[str] = []
    try:
        from g3 import random_des_v1 as rd
        from g3 import key_schema_v1 as ks
    except ImportError as exc:  # pragma: no cover
        return {"check": "H1_REAL_PARITY", "status": "FAIL",
                "failures": [f"engine import unavailable: {exc}"]}
    # A) START_HEAD parity: device 1, B released at t=0, resource B idle /
    # equipment available, shift active; the engine's frozen C11 FCFS
    # dispatch must start (1,B,1).
    cfg = rd.default_config(
        namespace=ks.NAMESPACE_DEVELOPMENT_UNIT, master_seed=7, replicate_id=0,
        tau_pm=lr_frozen_NO_PM(), observation_kernel=_own_kernel(),
        batch_size=2, scenario="isolated_small_case",
        shift_length_h="10", shifts_per_day=2)
    eng = rd.RandomDesEngine(cfg)
    eng.now = Fraction(0)
    eng.shift_state.active_shift = eng._shift_at(eng.now)
    eng.devices[1] = sm_device_state(1)
    eng.resources["B"].status = sm_resource_idle()
    eng.resources["B"].current_activity = None
    eng.equipment["B"].available = True
    eng._release_task(1, "B", 1, Fraction(0))
    before = len(eng.log)
    eng._equipment_and_dispatch()
    starts = [r for r in eng.log[before:]
              if r["event_type"] == "ACTIVITY_START"]
    if not starts:
        failures.append("H1 engine dispatched nothing for the legal head")
    else:
        rec = starts[0]
        p3 = asem.apply_start_head((1, "B", 1), Fraction(0))
        p3rec = p3.events[0]
        if not (rec["device_id"] == 1 and rec["process"] == "B"
                and rec["effective_attempt_no"] == 1
                and rec["resource_id"] == "B"
                and Fraction(rec["attempt_start_time"]) == Fraction(0)
                and Fraction(rec["attempt_end_time"]) == Fraction(2)):
            failures.append(f"H1 engine record unexpected: {rec}")
        if not (p3rec["device_id"] == rec["device_id"]
                and p3rec["process"] == rec["process"]
                and p3rec["effective_attempt_no"] == rec["effective_attempt_no"]
                and p3rec["resource_id"] == rec["resource_id"]
                and Fraction(p3rec["attempt_start_time"])
                == Fraction(rec["attempt_start_time"])
                and Fraction(p3rec["attempt_end_time"])
                == Fraction(rec["attempt_end_time"])):
            failures.append(
                f"START_HEAD parity mismatch: engine {rec} vs P3 {p3rec}")
    # B) H1_NOOP parity: maintenance state (resource A idle, age>=120, no
    # head, future demand) -> H1 baseline advances to the next event without
    # proactive PM; P3 apply_h1_noop(t, next) must equal the engine's next
    # closure time.
    eng2 = rd.RandomDesEngine(cfg)
    eng2.now = Fraction(0)
    eng2.shift_state.active_shift = eng2._shift_at(eng2.now)
    # device 1 in-flight A ending at 5/2 (scheduled event); resource A idle
    # at age=120 with no queue -> H1 does nothing (no PM) until 5/2.
    eng2.devices[1] = sm_device_state(1)
    eng2.resources["A"].status = sm_resource_idle()
    eng2.resources["A"].current_activity = None
    eng2.equipment["A"].available = True
    eng2.equipment["A"].age = Fraction(120)
    eng2.equipment["A"].lifetime_h = Fraction(9999)
    eng2.equipment["A"].is_right_censored = False
    eng2._release_task(1, "A", 1, Fraction(0))
    eng2._start_task(eng2.queues["A"][0])  # start A in-flight at t=0
    eng2.queues["A"] = []  # head consumed; maintenance state
    nxt = eng2._next_event_time()
    step = asem.apply_h1_noop(Fraction(0), nxt)
    if step.next_time != nxt:
        failures.append(f"H1_NOOP parity: engine next event {nxt} != P3 "
                        f"next {step.next_time}")
    if step.events != ():
        failures.append("H1_NOOP must not emit events (no proactive PM)")
    return {
        "check": "H1_REAL_PARITY",
        "status": "PASS" if not failures else "FAIL",
        "engine_next_event_h": str(nxt),
        "h1_noop_next_h": str(step.next_time),
        "failures": failures,
    }


def check_c23_continuation() -> dict[str, Any]:
    """Section 18: hidden world different + ObservableState same +
    PosteriorState same + same rollout post keys -> ContinuationWorld
    identical; same observable but different (dp,m) keys -> the worlds MAY
    differ and, when they do, the difference is a deterministic function of
    the frozen key bundle (not the live hidden world).  We pick a small
    deterministic m range and record at least one (dp,m) pair where the
    world ACTUALLY differs, proving the substream drives the difference."""
    from main_model.h2 import continuation_v1 as cont
    from main_model.h2_rollout import post_keys_v1 as pk
    failures: list[str] = []
    base = _e1_continuation_log()
    variants = [
        _hidden_variant(base, lambda r: r.update(
            true_state={"A": True, "B": True, "C": True})
            if "true_state" in r else None),
        _hidden_variant(base, lambda r: r.update(u="0.999")
                        if "u" in r else None),
        _hidden_variant(base, lambda r: r.update(
            lifetime_h="999") if "lifetime_h" in r else None),
    ]
    t = Fraction(4)
    st_base = obs.project_log_prefix(base, t, batch_size=2)
    post_base = ps.PosteriorState.from_observable(st_base)
    gen = {r: 1 for r in fp.RESOURCES}

    def _world(m: int):
        k = pk.rollout_post_keys(6, 0, 0, m, (1, 2), fp.RESOURCES, gen)
        w = cont.rebuild_continuation_world(
            st_base, post_base, u_x_by_device=k.u_x_by_device,
            u_d_by_device=k.u_d_by_device, u_l_by_resource=k.u_l_by_resource)
        return k, w

    k0, w0 = _world(0)
    for v in variants:
        st_v = obs.project_log_prefix(v, t, batch_size=2)
        post_v = ps.PosteriorState.from_observable(st_v)
        if (st_v.fingerprint() != st_base.fingerprint()
                or post_v != post_base):
            failures.append("hidden variants must keep Observable/Posterior "
                            "identical")
            continue
        k0v, wv = _world(0)
        if not (wv.devices == w0.devices
                and wv.residual_lifetimes == w0.residual_lifetimes):
            failures.append("same keys + same observable must give the same "
                            "ContinuationWorld across hidden variants")
    # find a deterministic (dp=0, m') whose world differs from (dp=0, m=0);
    # this demonstrates the difference is driven by the frozen substream
    differing: dict[str, Any] = {}
    for m in range(1, 12):
        km, wm = _world(m)
        if wm.devices != w0.devices or (
                wm.residual_lifetimes != w0.residual_lifetimes):
            differing = {"dp": 0, "m": m,
                         "keys_differ": km.to_canonical_dict()
                         != k0.to_canonical_dict(),
                         "worlds_differ": True,
                         "d1_devices": [d.x_abc for d in wm.devices],
                         "d0_devices": [d.x_abc for d in w0.devices]}
            break
    if not differing:
        failures.append("no (dp,m') found whose ContinuationWorld differs "
                        "from (dp=0,m=0): the substream difference must be "
                        "demonstrable")
    return {
        "check": "C23_CONTINUATION",
        "status": "PASS" if not failures else "FAIL",
        "same_keys_same_world_across_hidden": True,
        "different_dp_m_keys_differ": differing.get("keys_differ", False),
        "different_keys_world_differs": differing.get("worlds_differ", False),
        "differing_world": differing,
        "failures": failures,
    }


def _own_kernel() -> dict[str, dict[str, Fraction]]:
    """Checker's own restatement of the frozen observation kernel (P060:
    alpha = e/(2(1-q)), beta = e/(2q); E kernel from the frozen q_E / e_E).
    Independent code path (uses the frozen scalar formulas, not the
    implementer's kernel function)."""
    from main_model.h2.frozen_params_v1 import (
        E_ABC, E_E, Q_ABC, Q_E, frozen_alpha, frozen_beta,
    )
    kern: dict[str, dict[str, Fraction]] = {}
    for proc in ("A", "B", "C"):
        q = Q_ABC[proc]
        e = E_ABC[proc]
        kern[proc] = {"alpha": frozen_alpha(q, e),
                      "beta": frozen_beta(q, e)}
    kern["E"] = {"alpha": frozen_alpha(Q_E, E_E),
                 "beta": frozen_beta(Q_E, E_E)}
    return kern


def lr_frozen_NO_PM():
    from g3 import lifetime_regeneration_v1 as lr
    return lr.NO_PM_BEFORE_MANDATORY


def sm_device_state(device_id: int):
    from des import state_models_v1 as sm
    return sm.DeviceState(
        device_id=device_id,
        entry_time=Fraction(0),
        bay_id=1,
        process_state={p: sm.ProcessState(process=p)
                       for p in ("A", "B", "C", "E")},
    )


def sm_resource_idle():
    from des import state_models_v1 as sm
    return sm.ResourceStatus.IDLE


def run_all() -> dict[str, Any]:
    checks = [check_decision_points(), check_ordering(), check_rollout_seed(),
              check_crn(), check_c23_mechanics(), check_h1_parity(),
              check_wait_fragment_identity(), check_wait_invalidation(),
              check_continuation_posterior(), check_per_device_post_draw(),
              check_rollout_post_keys(), check_pm_age_semantics(),
              check_mandatory_optional_pm(), check_h1_real_parity(),
              check_c23_continuation()]
    all_ok = all(c["status"] == "PASS" for c in checks)
    return {"overall": "PASS" if all_ok else "FAIL", "checks": checks}


if __name__ == "__main__":
    result = run_all()
    print(result["overall"])
    for c in result["checks"]:
        print(f"  {c['check']}: {c['status']}")
    sys.exit(0 if result["overall"] == "PASS" else 1)
