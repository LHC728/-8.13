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


@dataclass(frozen=True)
class WaitAnchor:
    """A concrete scheduled same-device completion event (finite event
    identity) used to anchor WAIT_EVENT."""
    completion_time: Fraction
    device_id: int
    process: str
    attempt: int
    boundary: str  # "STRICT" | "BOUNDARY"


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
            "wait_anchor": (None if self.wait_anchor is None else {
                "completion_time": str(self.wait_anchor.completion_time),
                "device_id": self.wait_anchor.device_id,
                "process": self.wait_anchor.process,
                "attempt": self.wait_anchor.attempt,
                "boundary": self.wait_anchor.boundary}),
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


def _scheduled_completions(event_log: list[dict[str, Any]], t: Fraction
                           ) -> dict[int, list[Fraction]]:
    """Same-device in-flight scheduled completion events from the OBSERVABLE
    fields of the log prefix (ACTIVITY_START attempt_end_time > t)."""
    out: dict[int, list[Fraction]] = {}
    for r in event_log:
        if r.get("event_type") != "ACTIVITY_START":
            continue
        if Fraction(r.get("event_time", 0)) > t:
            continue
        end = Fraction(r["attempt_end_time"])
        if end > t:
            out.setdefault(r["device_id"], []).append(end)
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
    (resource, closure); dp = 0-based batch index (pure function)."""
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
        st = obs.project_log_prefix(event_log, t, batch_size=batch_size)
        scheduled = _scheduled_completions(event_log, t)
        for resource in RESOURCES:
            head = None
            for q in st.queue:
                if q.process_order == _process_order(resource):
                    head = (q.device_id, _process_name(q.process_order), q.effective_attempt_no)
                    break
            if head is not None and _head_is_legal(st, head, t, sh[1]):
                actions = [A_START_HEAD]
                anchor = _wait_anchor(st, head, t, sh[1], scheduled)
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
                 scheduled: dict[int, list[Fraction]]) -> Optional[WaitAnchor]:
    """STRICT / BOUNDARY WAIT anchor: a scheduled same-device completion
    event e with t < e < latest_start (STRICT) or e == latest_start
    (BOUNDARY, legal per the frozen contract)."""
    dev, proc, att = head
    latest_start = shift_end - DURATIONS_H[proc]
    best: Optional[WaitAnchor] = None
    for e in scheduled.get(dev, []):
        if t < e < latest_start:
            anchor = WaitAnchor(completion_time=e, device_id=dev,
                                process=proc, attempt=att, boundary="STRICT")
            if best is None or e < best.completion_time:
                best = anchor
        elif e == latest_start:
            return WaitAnchor(completion_time=e, device_id=dev, process=proc,
                              attempt=att, boundary="BOUNDARY")
    return best
