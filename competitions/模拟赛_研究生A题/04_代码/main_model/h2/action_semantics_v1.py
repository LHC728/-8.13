#!/usr/bin/env python3
"""Q3-H2-P3-A action continuation semantics (SPEC sections 6-10, frozen).

Deterministic continuation-step semantics for the five H2 actions:

  * START_HEAD (dispatch points): starts the frozen FCFS legal head ONLY;
    no head skipping / no reordering; emits the ACTIVITY_START event with
    the H1-identical fields; next time = t + duration.  H1 parity: the
    emitted record equals the accepted H1 engine dispatch record field for
    field.
  * H1_NOOP / ADVANCE_EVENT (maintenance points): no proactive PM, the
    resource stays idle, advance to the next scheduled event / next legal
    wakeup, then re-run the closure.  It is NOT WAIT_EVENT, NOT strategic
    wait, NOT queue reordering; no fixed wait duration is manufactured.
  * WAIT_EVENT: anchored to a specific finite scheduled same-device
    completion event e (STRICT t<e<latest_start or BOUNDARY e==latest_start
    -- legal per the frozen contract); advance to e; re-decide at the
    closure where the anchor occurs / is cancelled / is invalidated /
    device terminal / head state changes.  No infinite wait, no arbitrary
    future time, never skip the event without re-decision.
  * PM_WITH_HEAD (dispatch points): preventive replacement + calibration
    first, then re-run the closure and re-judge the FCFS head (the original
    head is NOT guaranteed to start afterwards -- observable state may
    change during the PM).
  * PM_IDLE (maintenance points): preventive replacement on an idle
    resource; after completion re-run the closure and re-judge the legal
    head; never bypasses FCFS, never assigns a specific task.

Mandatory / exact_240 are NEVER policy choices: random equipment failure,
a+d > 240 mandatory replacement and a+d == 240 completion-first-then-
replacement are engine facts; H2 cannot block mandatory, cannot record
mandatory as a PM action, cannot record exact_240 as optional PM.

Each continuation step is a pure function producing the next time and the
new observable event records (C23-safe: no hidden fields, no live-DES
imports).

Python 3.12, standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Optional

from main_model.h2.frozen_params_v1 import (  # noqa: E402
    CALIBRATION_MINUTES, DURATIONS_H,
)
from main_model.h2.decision_point_v1 import (  # noqa: E402
    A_H1_NOOP, A_PM_IDLE, A_PM_WITH_HEAD, A_START_HEAD, A_WAIT_EVENT,
)


@dataclass(frozen=True)
class ContinuationStep:
    """Deterministic result of applying one action at a decision point."""
    action: str
    next_time: Fraction
    events: tuple[dict[str, Any], ...]

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "action": self.action, "next_time": str(self.next_time),
            "events": [
                {k: (str(v) if isinstance(v, Fraction) else v)
                 for k, v in e.items()} for e in self.events]}


def _start_record(device: int, process: str, attempt: int, resource: str,
                  t: Fraction) -> dict[str, Any]:
    d = DURATIONS_H[process]
    return {
        "event_type": "ACTIVITY_START", "event_time": str(t),
        "device_id": device, "process": process,
        "effective_attempt_no": attempt, "resource_id": resource,
        "attempt_start_time": str(t),
        "attempt_end_time": str(t + d), "outcome": "NONE",
    }


def apply_start_head(head: tuple[int, str, int], t: Fraction
                     ) -> ContinuationStep:
    dev, proc, att = head
    d = DURATIONS_H[proc]
    return ContinuationStep(
        action=A_START_HEAD, next_time=t + d,
        events=(_start_record(dev, proc, att, proc, t),))


def apply_h1_noop(t: Fraction, next_event_time: Fraction
                  ) -> ContinuationStep:
    """Advance to the next scheduled event / next legal wakeup; the
    resource stays idle; no proactive PM and no manufactured wait."""
    return ContinuationStep(action=A_H1_NOOP, next_time=next_event_time,
                            events=())


def apply_wait_event(anchor_time: Fraction, t: Fraction) -> ContinuationStep:
    """Advance to the anchored finite event time e; re-decision happens at
    the anchor closure (cancellation / invalidation / terminal / head
    change all re-trigger decision)."""
    if anchor_time <= t:
        raise ValueError("WAIT anchor must be in the future")
    return ContinuationStep(action=A_WAIT_EVENT, next_time=anchor_time,
                            events=())


def _replacement_records(resource: str, t: Fraction, kind: str,
                         trigger: str, generation: int) -> tuple[dict, ...]:
    cal = CALIBRATION_MINUTES[resource] / Fraction(60)
    start = {
        "event_type": "EQUIPMENT_REPLACEMENT_START", "event_time": str(t),
        "resource_id": resource, "kind": kind, "trigger": trigger,
        "old_generation": generation, "new_generation": generation + 1,
        "age_before": str(t), "calibration_duration_hours": str(cal),
        "calibration_start": str(t), "calibration_end": str(t + cal),
    }
    complete = {
        "event_type": "EQUIPMENT_CALIBRATION_COMPLETE",
        "event_time": str(t + cal), "resource_id": resource,
        "generation": generation + 1, "calibration_start": str(t),
        "calibration_end": str(t + cal),
    }
    return (start, complete)


def apply_pm(resource: str, t: Fraction, kind: str, generation: int
             ) -> ContinuationStep:
    """Preventive replacement (PM_WITH_HEAD at dispatch points or PM_IDLE
    at maintenance points): replacement + calibration, then re-run the
    closure and re-judge the FCFS head."""
    cal = CALIBRATION_MINUTES[resource] / Fraction(60)
    return ContinuationStep(
        action=kind, next_time=t + cal,
        events=_replacement_records(resource, t, "preventive", "preventive",
                                    generation))
