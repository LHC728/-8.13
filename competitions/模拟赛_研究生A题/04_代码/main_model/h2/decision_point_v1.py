#!/usr/bin/env python3
"""Q3-H2-P3-A decision-point reconstruction and canonical ordering
(SPEC sections 2/5/10/11/12, frozen).

Two decision-point classes per (resource, event closure):
  * DISPATCH_DECISION_POINT: a legal FCFS head exists for the resource.
    H1 default action A0 = START_HEAD; candidates (per actual legality):
    START_HEAD, WAIT_EVENT (STRICT t<e<latest_start or BOUNDARY
    e==latest_start, anchored to a specific scheduled same-device
    completion event), PM_WITH_HEAD (age>=120, non-mandatory, calibration
    fits the shift).
  * MAINTENANCE_DECISION_POINT: NO legal START_HEAD while the resource is
    idle/available, age>=120, non-mandatory, future potential demand
    exists, replacement+calibration fits the shift.  H1 default A0b =
    H1_NOOP / ADVANCE_EVENT; candidates: H1_NOOP, PM_IDLE.  Both queue
    empty and queue-nonempty-but-no-legal-head form a maintenance point.

Canonical ordering (frozen): within one closure the resources are
evaluated in fixed order A/B/C/E; at most ONE decision point per
(resource, closure) (legal head -> dispatch point; else maintenance
conditions -> maintenance point; else no point).  ``dp`` = 0-based index of
the H2 decision point within the batch, a pure function of (world,
observable history, configuration, code).

The reconstruction is derived from the ObservableState (safe projection)
plus the scheduled same-device completion events read from the observable
fields of the log prefix (in-flight ACTIVITY_START attempt_end_time); it
never reads hidden fields (C23).  The h2 package imports no live-DES
engine (isolation).

Python 3.12, standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Optional

from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2.frozen_params_v1 import (  # noqa: E402
    CALIBRATION_MINUTES, DURATIONS_H, MANDATORY_AGE_H, MIN_PREVENTIVE_AGE_H,
    RESOURCES,
)

# frozen action names
A_START_HEAD = "START_HEAD"
A_H1_NOOP = "H1_NOOP"
A_WAIT_EVENT = "WAIT_EVENT"
A_PM_WITH_HEAD = "PM_WITH_HEAD"
A_PM_IDLE = "PM_IDLE"

# Event types produced by the DISPATCH / post-action phases of a closure.
# The frozen closure order is: settle -> observe -> classify -> exits ->
# cancel -> materialize D -> shift -> release -> [H2 policy decision] ->
# equipment dispatch -> start turnovers.  The H2 decision boundary sits
# BEFORE equipment dispatch, so same-timestamp records from the dispatch /
# turnover phases must NOT enter the pre-action decision state.
DISPATCH_PHASE_EVENT_TYPES = frozenset({
    "ACTIVITY_START",
    "TURNOVER_OUT_START",
    "TURNOVER_IN_START",
    "EQUIPMENT_REPLACEMENT_START",
    "EQUIPMENT_REPLACEMENT_DEFERRED",
    "WAKE_UP",
})


def pre_action_log(event_log: list[dict[str, Any]], t: Fraction
                   ) -> list[dict[str, Any]]:
    """Deterministic PRE-ACTION / PRE-DISPATCH view of the log at closure t.

    Keeps every record with event_time < t, plus same-timestamp records that
    belong to the pre-dispatch phases (settle / observation materialization /
    classification / second-abnormal exit+cancel / D materialization / shift
    update / task release); EXCLUDES same-timestamp records produced by the
    equipment-dispatch and turnover phases (ACTIVITY_START, turnover starts,
    replacement starts/deferrals, WAKE_UP) — the candidate action must be
    compared on the state BEFORE any action at t.

    This is phase-semantics based (accepted closure ordering + event identity),
    not a 'delete the ACTIVITY_START' result-guessing patch.
    """
    out: list[dict[str, Any]] = []
    for r in event_log:
        et = r.get("event_time")
        if et is None:
            continue
        tt = Fraction(et)
        if tt < t:
            out.append(r)
        elif tt == t and r.get("event_type") not in DISPATCH_PHASE_EVENT_TYPES:
            out.append(r)
    return out


def project_pre_action_state(event_log: list[dict[str, Any]], t: Fraction,
                             batch_size: int = 100) -> obs.ObservableState:
    """Observable state at the PRE-ACTION decision boundary of closure t."""
    return obs.project_log_prefix(pre_action_log(event_log, t), t,
                                  batch_size=batch_size)


@dataclass(frozen=True)
class WaitAnchor:
    """A concrete in-flight same-device fragment (finite event identity)
    used to anchor WAIT_EVENT.

    F2 (P3-A-E1): the anchor stores the TRUE identity of the waited-upon
    fragment -- the in-flight ACTIVITY_START's process / effective_attempt_no
    / attempt_start_time / resource -- NOT the head's fields.  Example:
    A running, B the waiting head -> anchor.process == "A" (never "B").
    """
    completion_time: Fraction
    device_id: int
    process: str               # in-flight fragment's process (NOT head's)
    effective_attempt_no: int  # in-flight fragment's attempt
    attempt_start_time: Fraction  # in-flight fragment's start identity
    resource: str              # in-flight fragment's resource
    boundary: str              # "STRICT" | "BOUNDARY"

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "completion_time": str(self.completion_time),
            "device_id": self.device_id,
            "process": self.process,
            "effective_attempt_no": self.effective_attempt_no,
            "attempt_start_time": str(self.attempt_start_time),
            "resource": self.resource,
            "boundary": self.boundary,
        }


@dataclass(frozen=True)
class ActiveFragment:
    """A scheduled same-device in-flight fragment (F1 exact identity)."""
    completion_time: Fraction
    device_id: int
    process: str
    effective_attempt_no: int
    attempt_start_time: Fraction
    resource: str


@dataclass(frozen=True)
class DecisionPoint:
    dp: int
    time: Fraction
    resource: str
    kind: str  # "dispatch" | "maintenance"
    head: Optional[tuple[int, str, int]]  # (device, process, attempt)
    legal_actions: tuple[str, ...]
    wait_anchor: Optional[WaitAnchor]
    pm_eligible: bool

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "dp": self.dp, "time": str(self.time), "resource": self.resource,
            "kind": self.kind, "head": self.head,
            "legal_actions": list(self.legal_actions),
            "wait_anchor": (None if self.wait_anchor is None else
                            self.wait_anchor.to_canonical_dict()),
            "pm_eligible": self.pm_eligible,
        }


def _device_passed(st: obs.ObservableState, device_id: int,
                   process: str) -> bool:
    for dev in st.devices:
        if dev.device_id != device_id:
            continue
        return any(o.process == process and o.outcome == "PASS"
                   for o in dev.observations)
    return False


def _fragment_settled(pre: list[dict[str, Any]], device: int, process: str,
                      attempt: int, fstart: Fraction) -> bool:
    """F1: fragment-aware settle -- ONLY a COMPLETE/CANCEL with the SAME
    exact identity (device_id, process, effective_attempt_no,
    attempt_start_time) settles this fragment (Density E2 principle;
    implemented independently here, never calling the Density analyzer)."""
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


def _active_fragments(event_log: list[dict[str, Any]], t: Fraction
                      ) -> dict[int, list[ActiveFragment]]:
    """F1: exact-fragment scheduled-completion reconstruction.  A fragment
    is a scheduled completion candidate at t iff there EXISTS an
    ACTIVITY_START with identity (device_id, process, effective_attempt_no,
    attempt_start_time), start_time <= t < attempt_end_time, AND the <= t
    prefix contains NO matching COMPLETE/CANCEL for that exact fragment.
    An old fragment's CANCEL never settles a new fragment (different
    attempt_start_time); a new fragment's existence is never erased by an
    old CANCEL.  Returns per-device lists sorted deterministically."""
    pre = [r for r in event_log
           if r.get("event_time") is not None
           and Fraction(r["event_time"]) <= t]
    out: dict[int, list[ActiveFragment]] = {}
    for r in pre:
        if r.get("event_type") != "ACTIVITY_START":
            continue
        s = Fraction(r.get("attempt_start_time", r["event_time"]))
        end = Fraction(r["attempt_end_time"])
        if not (s <= t < end):
            continue
        if _fragment_settled(pre, r["device_id"], r["process"],
                             r["effective_attempt_no"], s):
            continue
        frag = ActiveFragment(
            completion_time=end, device_id=r["device_id"],
            process=r["process"], effective_attempt_no=r["effective_attempt_no"],
            attempt_start_time=s, resource=r.get("resource_id", r["process"]))
        out.setdefault(r["device_id"], []).append(frag)
    for dev in out:
        out[dev].sort(key=lambda f: (f.completion_time,
                                     _process_order(f.resource),
                                     f.effective_attempt_no,
                                     f.attempt_start_time))
    return out


def _head_is_legal(st: obs.ObservableState, head: tuple[int, str, int],
                   t: Fraction, shift_end: Fraction) -> bool:
    dev, proc, att = head
    if _device_passed(st, dev, "E") and proc == "E":
        pass  # head process E needs A/B/C passed (checked below)
    if proc == "E":
        if not all(_device_passed(st, dev, p) for p in ("A", "B", "C")):
            return False
    return t + DURATIONS_H[proc] <= shift_end


def _maintenance_eligible(st: obs.ObservableState, resource: str, t: Fraction,
                          shift_end: Fraction) -> bool:
    rsrc = next((r for r in st.resources if r.resource == resource), None)
    if rsrc is None or rsrc.status != "idle":
        return False
    if not (MIN_PREVENTIVE_AGE_H <= rsrc.age_h < MANDATORY_AGE_H):
        return False
    cal = CALIBRATION_MINUTES[resource] / Fraction(60)
    if t + cal > shift_end:
        return False
    if st.remaining_not_entered > 0:
        return True
    for dev in st.devices:
        if dev.terminal_state is not None:
            continue
        if not _device_passed(st, dev.device_id, resource):
            return True
    return False


def reconstruct_decision_points(event_log: list[dict[str, Any]], K: Fraction,
                                batch_size: int = 100,
                                t_end: Optional[Fraction] = None
                                ) -> list[DecisionPoint]:
    """Reconstruct the H2 decision points of a batch deterministically:
    closure enumeration (distinct canonical event times + Q3 shift starts),
    per closure resources in A/B/C/E order, at most one point per
    (resource, closure); dp = 0-based batch index (pure function).

    REQUALIFICATION (decision semantics): each closure is evaluated on the
    PRE-ACTION view (pre_action_log): same-timestamp dispatch-phase records
    (ACTIVITY_START / turnover starts / replacement starts) do NOT enter the
    decision state, and a DISPATCH decision point additionally requires the
    resource to be IDLE / AVAILABLE (status "idle" in the projection) — a
    resource already testing / calibration / replacement / failed yields NO
    dispatch point.  MAINTENANCE decision points keep the frozen maintenance
    conditions unchanged."""
    shifts = obs.q3_shift_grid(K)
    event_times = sorted({Fraction(r.get("event_time", 0)) for r in event_log})
    batch_end = t_end if t_end is not None else max(event_times)
    points: list[DecisionPoint] = []
    dp = 0
    for t in sorted(set(event_times) | {s for s, _e in shifts}):
        if t >= batch_end:
            continue
        sh = obs.active_shift(shifts, t)
        if sh is None:
            continue
        pre_log = pre_action_log(event_log, t)
        st = obs.project_log_prefix(pre_log, t, batch_size=batch_size)
        active = _active_fragments(pre_log, t)
        for resource in RESOURCES:
            rsrc = next((r for r in st.resources if r.resource == resource),
                        None)
            resource_idle = rsrc is not None and rsrc.status == "idle"
            head = None
            for q in st.queue:
                if q.process_order == _process_order(resource):
                    head = (q.device_id, _process_name(q.process_order), q.effective_attempt_no)
                    break
            if resource_idle and head is not None \
                    and _head_is_legal(st, head, t, sh[1]):
                actions = [A_START_HEAD]
                anchor = _wait_anchor(st, head, t, sh[1], active)
                if anchor is not None:
                    actions.append(A_WAIT_EVENT)
                rsrc = next(r for r in st.resources if r.resource == resource)
                pm_ok = (MIN_PREVENTIVE_AGE_H <= rsrc.age_h
                         < MANDATORY_AGE_H
                         and t + CALIBRATION_MINUTES[resource] / Fraction(60)
                         <= sh[1])
                if pm_ok:
                    actions.append(A_PM_WITH_HEAD)
                points.append(DecisionPoint(
                    dp=dp, time=t, resource=resource, kind="dispatch",
                    head=head, legal_actions=tuple(actions),
                    wait_anchor=anchor, pm_eligible=pm_ok))
                dp += 1
            elif _maintenance_eligible(st, resource, t, sh[1]):
                points.append(DecisionPoint(
                    dp=dp, time=t, resource=resource, kind="maintenance",
                    head=head, legal_actions=(A_H1_NOOP, A_PM_IDLE),
                    wait_anchor=None, pm_eligible=True))
                dp += 1
    return points


def _process_order(resource: str) -> int:
    return {"A": 0, "B": 1, "C": 2, "E": 3}[resource]


def _process_name(order: int) -> str:
    return {0: "A", 1: "B", 2: "C", 3: "E"}[order]


def _wait_anchor(st: obs.ObservableState, head: tuple[int, str, int],
                 t: Fraction, shift_end: Fraction,
                 active: dict[int, list[ActiveFragment]]
                 ) -> Optional[WaitAnchor]:
    """STRICT / BOUNDARY WAIT anchor: a scheduled same-device IN-FLIGHT
    fragment e with t < e < latest_start (STRICT) or e == latest_start
    (BOUNDARY, legal per the frozen contract).  F1: only active fragments
    (not settled by a matching COMPLETE/CANCEL) are candidates.  F2: the
    anchor stores the TRUE in-flight fragment identity.  Deterministic
    selection: earliest completion_time; tie-break by resource A/B/C/E
    (process_order), effective_attempt_no, attempt_start_time."""
    dev, proc, att = head
    latest_start = shift_end - DURATIONS_H[proc]
    candidates: list[WaitAnchor] = []
    for f in active.get(dev, []):
        if t < f.completion_time < latest_start:
            candidates.append(WaitAnchor(
                completion_time=f.completion_time, device_id=f.device_id,
                process=f.process, effective_attempt_no=f.effective_attempt_no,
                attempt_start_time=f.attempt_start_time, resource=f.resource,
                boundary="STRICT"))
        elif f.completion_time == latest_start:
            candidates.append(WaitAnchor(
                completion_time=f.completion_time, device_id=f.device_id,
                process=f.process, effective_attempt_no=f.effective_attempt_no,
                attempt_start_time=f.attempt_start_time, resource=f.resource,
                boundary="BOUNDARY"))
    if not candidates:
        return None
    candidates.sort(key=lambda a: (a.completion_time,
                                   _process_order(a.resource),
                                   a.effective_attempt_no,
                                   a.attempt_start_time))
    return candidates[0]
