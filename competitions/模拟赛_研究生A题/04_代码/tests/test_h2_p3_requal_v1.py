#!/usr/bin/env python3
"""Q3-H2-P3 requalification tests (decision semantics repair):
DP-IDLE-01..04 (resource idle/availability guard for DISPATCH decision
points) and PRE-01..04 (pre-action / pre-dispatch closure boundary).

Frozen domain: K = 21/2, two-shift calendar; standard library only.
"""
from __future__ import annotations

import sys
import unittest
from fractions import Fraction
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from main_model.h2 import decision_point_v1 as dp  # noqa: E402
from main_model.h2 import observable_state_v1 as obs  # noqa: E402

K = Fraction(21, 2)
BATCH = 6


def _log(*records: dict) -> list[dict]:
    base = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
    ]
    return base + list(records)


def _release(device: int, process: str, att: int, at: str) -> dict:
    return {"event_type": "TASK_RELEASE", "event_time": at,
            "device_id": device, "process": process,
            "effective_attempt_no": att, "resource_id": process,
            "release_time": at}


def _start(device: int, process: str, att: int, s: str, e: str) -> dict:
    return {"event_type": "ACTIVITY_START", "event_time": s,
            "device_id": device, "process": process,
            "effective_attempt_no": att, "resource_id": process,
            "attempt_start_time": s, "attempt_end_time": e, "outcome": "NONE"}


def _complete(device: int, process: str, att: int, s: str, e: str) -> dict:
    return {"event_type": "ACTIVITY_COMPLETE", "event_time": e,
            "device_id": device, "process": process,
            "effective_attempt_no": att, "resource_id": process,
            "attempt_start_time": s, "attempt_end_time": e, "outcome": "PASS"}


def _replacement(resource: str, at: str, end: str, kind: str,
                 trigger: str) -> dict:
    return {"event_type": "EQUIPMENT_REPLACEMENT_START", "event_time": at,
            "resource_id": resource, "kind": kind, "trigger": trigger,
            "old_generation": 1, "new_generation": 2, "age_before": 100,
            "calibration_duration_hours": "4",
            "calibration_start": at, "calibration_end": end}


def _points_at(log, t: Fraction, resource: str):
    pts = dp.reconstruct_decision_points(log, K, batch_size=BATCH)
    return [p for p in pts if p.time == t and p.resource == resource]


class TestResourceIdleGuard(unittest.TestCase):
    """DP-IDLE-01..04: DISPATCH decision points require idle/available."""

    def test_dp_idle_01_resource_testing_no_dispatch_point(self):
        # resource A testing (in-flight fragment) with a queued B task
        log = _log(
            _start(1, "A", 1, "1", "5"),
            _release(1, "B", 1, "1"),
        )
        pts = _points_at(log, Fraction(2), "A")
        self.assertEqual(pts, [])  # no dispatch (nor maintenance) point

    def test_dp_idle_02_idle_legal_head_one_dispatch_point(self):
        log = _log(
            _release(1, "A", 1, "1"),
            _release(2, "B", 1, "4"),  # later event keeps t=1 < batch_end
        )
        pts = _points_at(log, Fraction(1), "A")
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0].kind, "dispatch")
        self.assertEqual(pts[0].head, (1, "A", 1))
        self.assertIn(dp.A_START_HEAD, pts[0].legal_actions)

    def test_dp_idle_03_same_timestamp_h1_start_only_one_point(self):
        # H1 already dispatched device1-A at t=2 (ACTIVITY_START at 2);
        # queue holds A (pre-action head) and a next B task.  The pre-action
        # boundary yields exactly ONE dispatch point (for A), never a second
        # point reinterpreting B as another decision at the same closure.
        log = _log(
            _release(1, "A", 1, "2"),
            _release(1, "B", 1, "2"),
            _start(1, "A", 1, "2", "9/2"),
            _release(2, "C", 1, "6"),  # later event keeps t=2 < batch_end
        )
        pts = _points_at(log, Fraction(2), "A")
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0].head, (1, "A", 1))

    def test_dp_idle_04_calibration_no_dispatch_point(self):
        log = _log(
            _replacement("A", "1", "5", "preventive", "preventive"),
            _release(1, "A", 1, "1"),
        )
        pts = _points_at(log, Fraction(2), "A")
        self.assertEqual(pts, [])

    def test_dp_idle_04b_replacement_no_dispatch_point(self):
        log = _log(
            _replacement("A", "1", "5", "mandatory_240", "a_plus_d_gt_240"),
            _release(1, "A", 1, "1"),
        )
        pts = _points_at(log, Fraction(2), "A")
        self.assertEqual(pts, [])

    def test_dp_idle_04c_failed_no_dispatch_point(self):
        log = _log(
            _replacement("A", "1", "5", "failure", "mid_fragment_failure"),
            _release(1, "A", 1, "1"),
        )
        pts = _points_at(log, Fraction(2), "A")
        self.assertEqual(pts, [])


class TestPreActionBoundary(unittest.TestCase):
    """PRE-01..04: decision state is the PRE-ACTION state at closure t."""

    def test_pre_01_action_start_excluded_resource_stays_idle(self):
        log = _log(
            _release(1, "A", 1, "2"),
            _start(1, "A", 1, "2", "9/2"),  # dispatch-phase record at t
        )
        st = dp.project_pre_action_state(log, Fraction(2), batch_size=BATCH)
        rsrc = next(r for r in st.resources if r.resource == "A")
        self.assertEqual(rsrc.status, "idle")
        heads = [q for q in st.queue if q.process_order == 0]
        self.assertEqual(len(heads), 1)  # head still queued pre-action

    def test_pre_02_pre_dispatch_records_visible(self):
        # completion + release + D materialization at t are visible
        log = _log(
            _start(1, "A", 1, "0", "2"),
            _complete(1, "A", 1, "0", "2"),
            _release(1, "A", 2, "2"),
            {"event_type": "D_CREATED", "event_time": "2", "device_id": 1,
             "d_state": "NORMAL", "u": "1/2"},
        )
        st = dp.project_pre_action_state(log, Fraction(2), batch_size=BATCH)
        rsrc = next(r for r in st.resources if r.resource == "A")
        self.assertEqual(rsrc.status, "idle")
        self.assertEqual(rsrc.age_h, Fraction(2))  # completed fragment counted
        dev = next(d for d in st.devices if d.device_id == 1)
        self.assertTrue(dev.d_materialized)
        heads = [q for q in st.queue if q.process_order == 0]
        self.assertEqual(len(heads), 1)

    def test_pre_03_dispatch_start_not_in_decision_state(self):
        log = _log(
            _release(1, "A", 1, "2"),
            _start(1, "A", 1, "2", "9/2"),
        )
        st = dp.project_pre_action_state(log, Fraction(2), batch_size=BATCH)
        active = dp._active_fragments(dp.pre_action_log(log, Fraction(2)),
                                      Fraction(2))
        self.assertEqual(active, {})  # no in-flight fragment at the boundary

    def test_pre_04_same_timestamp_order_preserved(self):
        # multiple releases at the same timestamp: frozen FCFS order
        log = _log(
            _release(1, "B", 1, "2"),
            _release(1, "C", 1, "2"),
            _release(1, "A", 1, "2"),
            _release(2, "E", 1, "7"),  # later event keeps t=2 < batch_end
        )
        pts = dp.reconstruct_decision_points(log, K, batch_size=BATCH)
        # at t=2 resource A head = device1-A (process order A < B < C)
        a_pts = [p for p in pts if p.time == Fraction(2)
                 and p.resource == "A"]
        self.assertEqual(len(a_pts), 1)
        self.assertEqual(a_pts[0].head, (1, "A", 1))


if __name__ == "__main__":
    unittest.main()
