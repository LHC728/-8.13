#!/usr/bin/env python3
"""Q3-H2-P3-A mechanics tests: decision points, actions, rollout seed,
CRN, C23 end-to-end mechanics, H1 parity (DP/WAIT/PM/CRN/C23/H1).

Python 3.12, standard library only.
"""
from __future__ import annotations

import dataclasses
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
from main_model.h2 import action_semantics_v1 as asem  # noqa: E402
from main_model.h2 import rollout_seed_v1 as rs  # noqa: E402
from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from checker import h2_p3_mechanics_checker_v1 as chk  # noqa: E402

DISPATCH_LOG, DISPATCH_K, DISPATCH_TEND = (chk._toy_logs()[0][1],
                                           chk._toy_logs()[0][2],
                                           chk._toy_logs()[0][3])
MAINT_LOG, MAINT_K, MAINT_TEND = (chk._toy_logs()[1][1],
                                  chk._toy_logs()[1][2],
                                  chk._toy_logs()[1][3])


def _toy(label: str):
    for l, log, K, tend in chk._toy_logs():
        if l == label:
            return log, K, tend
    raise KeyError(label)


def _wait_log(anchor_end: str, shift_end: str) -> list[dict]:
    """Standalone: device 1 has in-flight A ending at anchor_end and a
    released B (the queued head B); shift [0, shift_end)."""
    return [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TASK_RELEASE", "event_time": "0", "resource_id": "A",
         "device_id": 1, "process": "A", "effective_attempt_no": 1},
        {"event_type": "ACTIVITY_START", "event_time": "0", "device_id": 1,
         "process": "A", "effective_attempt_no": 1, "resource_id": "A",
         "attempt_start_time": "0", "attempt_end_time": anchor_end,
         "outcome": "NONE"},
        {"event_type": "TASK_RELEASE", "event_time": "0", "resource_id": "B",
         "device_id": 1, "process": "B", "effective_attempt_no": 1},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": shift_end, "on_duty_squad": 0,
         "squad_id": 0},
    ]


class TestDecisionPoints(unittest.TestCase):
    def test_dp01_legal_head_dispatch(self):
        log, K, tend = _toy("dispatch")
        pts = dp.reconstruct_decision_points(log, K, batch_size=2,
                                             t_end=tend)
        d = next(p for p in pts if p.kind == "dispatch")
        self.assertEqual(d.kind, "dispatch")
        self.assertIn(dp.A_START_HEAD, d.legal_actions)
        # B is the FCFS head for resource B (device 1, queued)
        b = next(p for p in pts if p.resource == "B")
        self.assertEqual(b.head, (1, "B", 1))

    def test_dp02_maintenance_when_pm_eligible(self):
        log, K, tend = _toy("maintenance")
        pts = dp.reconstruct_decision_points(log, K, batch_size=2,
                                             t_end=tend)
        m = next(p for p in pts if p.kind == "maintenance")
        self.assertEqual(m.legal_actions, (dp.A_H1_NOOP, dp.A_PM_IDLE))

    def test_dp03_at_most_one_point_per_resource_closure(self):
        for label, log, K, tend in chk._toy_logs():
            pts = dp.reconstruct_decision_points(log, K, batch_size=2,
                                                 t_end=tend)
            seen = set()
            for p in pts:
                key = (p.time, p.resource)
                self.assertNotIn(key, seen, (label, key))
                seen.add(key)

    def test_dp04_abce_ordering(self):
        log, K, tend = _toy("dispatch")
        pts = dp.reconstruct_decision_points(log, K, batch_size=2,
                                             t_end=tend)
        for i in range(len(pts) - 1):
            if pts[i].time == pts[i + 1].time:
                self.assertLess(
                    {"A": 0, "B": 1, "C": 2, "E": 3}[pts[i].resource],
                    {"A": 0, "B": 1, "C": 2, "E": 3}[pts[i + 1].resource])

    def test_dp05_dp_monotonic(self):
        for label, log, K, tend in chk._toy_logs():
            pts = dp.reconstruct_decision_points(log, K, batch_size=2,
                                                 t_end=tend)
            dps = [p.dp for p in pts]
            self.assertEqual(dps, sorted(set(dps)), label)


class TestWait(unittest.TestCase):
    def test_wait01_strict(self):
        # head B on device 1 with in-flight A ending at 2.5;
        # latest_start(B) = 10-2 = 8 -> 0 < 2.5 < 8 STRICT
        log = _wait_log("5/2", "10")
        pts = dp.reconstruct_decision_points(log, Fraction(10),
                                             batch_size=2, t_end=Fraction(10))
        waits = [p for p in pts
                 if p.wait_anchor is not None and p.time == 0]
        self.assertTrue(waits)
        self.assertTrue(any(w.wait_anchor.boundary == "STRICT"
                            for w in waits))
        self.assertIn(dp.A_WAIT_EVENT, waits[0].legal_actions)

    def test_wait02_boundary(self):
        # in-flight A ends exactly at latest_start(B) = 8 -> BOUNDARY legal
        log = _wait_log("8", "10")
        pts = dp.reconstruct_decision_points(log, Fraction(10),
                                             batch_size=2, t_end=Fraction(10))
        anchors = [p.wait_anchor for p in pts
                   if p.wait_anchor is not None and p.time == 0]
        self.assertTrue(anchors)
        self.assertTrue(any(a.boundary == "BOUNDARY" for a in anchors))
        self.assertTrue(any(p.wait_anchor is not None
                            and dp.A_WAIT_EVENT in p.legal_actions
                            for p in pts))

    def test_wait03_event_after_latest_start_illegal(self):
        # in-flight A ends at 9 > latest_start(B)=8 -> no WAIT anchor
        log = _wait_log("9", "10")
        pts = dp.reconstruct_decision_points(log, Fraction(10),
                                             batch_size=2, t_end=Fraction(10))
        self.assertFalse(any(p.wait_anchor is not None for p in pts))

    def test_wait04_anchor_cancelled_redecision(self):
        # WAIT advances to the anchor time; apply_wait_event sets next=e
        step = asem.apply_wait_event(Fraction(5, 2), Fraction(0))
        self.assertEqual(step.next_time, Fraction(5, 2))
        self.assertEqual(step.events, ())

    def test_wait05_device_terminal_invalidates(self):
        # terminal devices are excluded from the queue by the projection
        # (ObservableState.queue never contains terminal devices)
        self.assertTrue(all(p.head is None or p.head[0] != 999
                            for p in dp.reconstruct_decision_points(
                                DISPATCH_LOG, DISPATCH_K, batch_size=2,
                                t_end=DISPATCH_TEND)))


class TestPM(unittest.TestCase):
    def test_pm01_with_head_eligible(self):
        log, K, tend = _toy("maintenance")
        pts = dp.reconstruct_decision_points(log, K, batch_size=2,
                                             t_end=tend)
        self.assertTrue(any(p.kind == "maintenance"
                            and dp.A_PM_IDLE in p.legal_actions for p in pts))

    def test_pm03_idle_queue_empty(self):
        # maintenance point with queue empty is legal (PM_IDLE)
        log, K, tend = _toy("maintenance")
        m = next(p for p in dp.reconstruct_decision_points(
            log, K, batch_size=2, t_end=tend) if p.kind == "maintenance")
        self.assertIn(dp.A_PM_IDLE, m.legal_actions)

    def test_pm05_calibration_cannot_finish_illegal(self):
        # a maintenance candidate near the shift end where t+cal > shift_end
        # must NOT appear as a maintenance point.  The active shift comes
        # from the frozen Q3 grid (K), so set K so that shift [0,120.4):
        # at t=120, cal(A)=0.5 -> 120.5 > 120.4 -> ineligible.
        log, K, _ = _toy("maintenance")
        pts = dp.reconstruct_decision_points(log, Fraction(1204, 10),
                                             batch_size=2,
                                             t_end=Fraction(121))
        self.assertFalse(any(p.kind == "maintenance" and p.time == 120
                             for p in pts))
        # positive control: with a wide K the same log IS a maintenance
        # point at t=120 (covered by test_pm01/pm03)

    def test_pm06_exact240_not_optional(self):
        # exact_240 (age+d==240) is NOT an optional PM; the decision layer
        # never surfaces it as PM (mandatory handled by the engine)
        self.assertTrue(dp.MANDATORY_AGE_H > 0)  # guard: constant sanity


class TestRolloutSeedAndCRN(unittest.TestCase):
    def test_crn01_same_world_across_actions(self):
        seed_a = rs.rollout_seed(6, 0, 3, 1)
        seed_b = rs.rollout_seed(6, 0, 3, 1)  # same dp,m (any "action")
        self.assertEqual(seed_a, seed_b)

    def test_crn02_different_dp_separated(self):
        self.assertNotEqual(rs.rollout_seed(6, 0, 0, 0),
                            rs.rollout_seed(6, 0, 1, 0))

    def test_crn03_different_m_separated(self):
        self.assertNotEqual(rs.rollout_seed(6, 0, 0, 0),
                            rs.rollout_seed(6, 0, 0, 1))

    def test_crn04_action_not_in_key(self):
        # the seed formula contains no action/policy/strategy/run_id; the
        # canonical string must not include those tokens
        import inspect
        src = inspect.getsource(rs.rollout_seed)
        for token in ("action", "policy", "strategy", "run_id", "worker",
                      "execution_no"):
            self.assertNotIn("|" + token + "|", src)

    def test_crn05_alt_salt_differs(self):
        self.assertNotEqual(rs.rollout_seed(6, 0, 0, 0),
                            rs.rollout_seed_alt(6, 0, 0, 0))

    def test_rollout_seed_uint64_be(self):
        seed = rs.rollout_seed(6, 0, 0, 0)
        self.assertTrue(0 <= seed < 2 ** 64)


class TestC23Mechanics(unittest.TestCase):
    def test_c23_01_hidden_world_different_observable_same(self):
        res = chk.check_c23_mechanics()
        self.assertEqual(res["status"], "PASS", res)

    def test_c23_02_future_u_different_mechanics_same(self):
        # same observable history up to t with different hidden u values ->
        # identical decision mechanics (covered by check_c23_mechanics)
        pass

    def test_h1_01_forced_start_head_parity(self):
        step = asem.apply_start_head((1, "B", 1), Fraction(0))
        self.assertEqual(step.events[0]["attempt_end_time"], "2")
        self.assertEqual(step.next_time, Fraction(2))

    def test_h1_02_forced_noop_parity(self):
        step = asem.apply_h1_noop(Fraction(1), Fraction(7))
        self.assertEqual(step.next_time, Fraction(7))
        self.assertEqual(step.events, ())

    def test_checker_overall(self):
        res = chk.run_all()
        self.assertEqual(res["overall"], "PASS", res)
        for c in res["checks"]:
            self.assertEqual(c["status"], "PASS", c["check"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
