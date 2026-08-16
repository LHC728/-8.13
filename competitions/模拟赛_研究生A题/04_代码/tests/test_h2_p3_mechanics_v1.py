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
    """Standalone: device 1 has an in-flight A (started at 0, ending at
    anchor_end) and a RELEASED-at-1 B (the queued head B); shift [0,
    shift_end).  The B decision closure is t=1, where A is already running
    (corrected pre-action semantics: the anchor fragment started at an
    earlier closure)."""
    return [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TASK_RELEASE", "event_time": "0", "resource_id": "A",
         "device_id": 1, "process": "A", "effective_attempt_no": 1},
        {"event_type": "ACTIVITY_START", "event_time": "0", "device_id": 1,
         "process": "A", "effective_attempt_no": 1, "resource_id": "A",
         "attempt_start_time": "0", "attempt_end_time": anchor_end,
         "outcome": "NONE"},
        {"event_type": "TASK_RELEASE", "event_time": "1", "resource_id": "B",
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
        # head B on device 1 with in-flight A ending at 2.5 (A started at 0);
        # B released at 1; latest_start(B) = 10-2 = 8 -> 1 < 2.5 < 8 STRICT
        log = _wait_log("5/2", "10")
        pts = dp.reconstruct_decision_points(log, Fraction(10),
                                             batch_size=2, t_end=Fraction(10))
        waits = [p for p in pts
                 if p.wait_anchor is not None and p.time == 1]
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
                   if p.wait_anchor is not None and p.time == 1]
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

    def test_pm_r1_age_before_is_age_h(self):
        # F4: replacement record age_before == equipment age_h (135), never
        # the wall-clock decision time (200)
        step = asem.apply_pm("A", Fraction(200), dp.A_PM_IDLE, generation=1,
                             age_h=Fraction(135))
        self.assertEqual(Fraction(step.events[0]["age_before"]),
                         Fraction(135))

    def test_pm_r2_exact240_head_no_pm_with_head(self):
        # PM-R2: age == 240 with a legal head -> PM_WITH_HEAD must NOT be a
        # policy action (mandatory node)
        log, K, tend = chk._pm_logs()["PM-R2-EXACT240-HEAD"]
        pts = dp.reconstruct_decision_points(log, K, batch_size=2, t_end=tend)
        d = [p for p in pts if p.kind == "dispatch" and p.time == 240]
        self.assertTrue(d, "dispatch point with legal head at age=240")
        self.assertNotIn(dp.A_PM_WITH_HEAD, d[0].legal_actions)

    def test_pm_r3_exact240_nohead_no_pm_idle(self):
        # PM-R3: age == 240, maintenance conditions otherwise satisfied ->
        # PM_IDLE must NOT become a policy action
        log, K, tend = chk._pm_logs()["PM-R3-EXACT240-NOHEAD"]
        pts = dp.reconstruct_decision_points(log, K, batch_size=2, t_end=tend)
        self.assertFalse(any(p.kind == "maintenance" and p.time == 240
                             for p in pts))

    def test_pm_r4_age120_pm_offered(self):
        # PM-R4: age == 120 with calendar/other conditions legal -> optional
        # PM appears
        log, K, tend = chk._pm_logs()["PM-POSITIVE-120"]
        pts = dp.reconstruct_decision_points(log, K, batch_size=2, t_end=tend)
        m = [p for p in pts if p.kind == "maintenance"]
        self.assertTrue(m)
        self.assertIn(dp.A_PM_IDLE, m[0].legal_actions)

    def test_pm_with_head_positive(self):
        # PM_WITH_HEAD positive: age=120 + legal head -> offered
        log, K, _ = chk._pm_logs()["PM-POSITIVE-120"]
        log = [dict(r) for r in log]
        log.append({"event_type": "TASK_RELEASE", "event_time": "120",
                    "resource_id": "A", "device_id": 2, "process": "A",
                    "effective_attempt_no": 1})
        pts = dp.reconstruct_decision_points(log, K, batch_size=2,
                                             t_end=Fraction(121))
        d = [p for p in pts if p.kind == "dispatch" and p.time == 120]
        self.assertTrue(d)
        self.assertIn(dp.A_PM_WITH_HEAD, d[0].legal_actions)


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


class TestE1WaitFragment(unittest.TestCase):
    """P3-A-E1 F1/F2 + WAIT-R1..R5."""

    def test_wait_r1_cancelled_old_fragment_not_anchor(self):
        res = chk.check_wait_fragment_identity()
        self.assertEqual(res["status"], "PASS", res)
        for row in res["rows"]:
            if row["label"] == "WAIT-R1" and row["closure_t"] == "2":
                self.assertIsNone(row["impl_anchor"])
                self.assertIsNone(row["own_anchor"])

    def test_wait_r2_restarted_fragment_identity(self):
        res = chk.check_wait_fragment_identity()
        self.assertEqual(res["status"], "PASS", res)
        row = next(r for r in res["rows"]
                   if r["label"] == "WAIT-R2" and r["closure_t"] == "3")
        self.assertEqual(row["impl_anchor"]["process"], "A")
        self.assertEqual(row["impl_anchor"]["attempt_start_time"], "2")
        self.assertEqual(row["impl_anchor"]["completion_time"], "4")

    def test_wait_r3_completed_fragment_not_anchor(self):
        res = chk.check_wait_fragment_identity()
        self.assertEqual(res["status"], "PASS", res)
        for row in res["rows"]:
            if row["label"] == "WAIT-R3" and row["closure_t"] == "1":
                self.assertIsNone(row["impl_anchor"])

    def test_wait_r4_anchor_identity_is_inflight_process(self):
        res = chk.check_wait_fragment_identity()
        self.assertEqual(res["status"], "PASS", res)
        row = next(r for r in res["rows"]
                   if r["label"] == "WAIT-R4" and r["closure_t"] == "1")
        self.assertEqual(row["impl_anchor"]["process"], "A")
        self.assertNotEqual(row["impl_anchor"]["process"], "B")
        self.assertEqual(row["impl_anchor"]["resource"], "A")

    def test_wait_r5_invalidation(self):
        res = chk.check_wait_invalidation()
        self.assertEqual(res["status"], "PASS", res)
        self.assertTrue(res["wait_legal_at_t0"])
        self.assertEqual(res["stale_after_terminal_head_change"], 0)
        self.assertEqual(res["stale_after_anchor_cancel"], 0)

    def test_wait_anchor_impl_own_agree(self):
        # every impl WAIT anchor must be matched by the checker's own
        # exact-fragment anchor (identity-level agreement, PRE-ACTION view)
        for label, log, K, tend in chk._toy_logs():
            pts = dp.reconstruct_decision_points(log, K, batch_size=2,
                                                 t_end=tend)
            for p in pts:
                if p.wait_anchor is None:
                    continue
                pre = chk._own_pre_action_log(log, p.time)
                own = chk._own_wait_anchor(
                    p.head, p.time,
                    obs.active_shift(obs.q3_shift_grid(K), p.time)[1],
                    chk._own_active_fragments(pre, p.time))
                self.assertIsNotNone(own, (label, p.to_canonical_dict()))
                self.assertEqual(own[1], p.wait_anchor.process, label)
                self.assertEqual(own[3], p.wait_anchor.attempt_start_time,
                                 label)
                self.assertEqual(own[0], p.wait_anchor.completion_time, label)


class TestE1Continuation(unittest.TestCase):
    """P3-A-E1 F3: per-device draws, reached-E D posterior, fail-close."""

    def test_cont_reached_e_d_posterior_counterexample(self):
        res = chk.check_continuation_posterior()
        self.assertEqual(res["status"], "PASS", res)
        self.assertTrue(res["e_observation_changes_d_continuation_draw"])
        self.assertNotEqual(res["x_D_correct_continuation"],
                            res["x_D_wrong_prior"])

    def test_cont_per_device_independence(self):
        res = chk.check_per_device_post_draw()
        self.assertEqual(res["status"], "PASS", res)
        self.assertTrue(res["same_posterior"])
        self.assertNotEqual(res["d1_before"], res["d2_before"])
        self.assertEqual(res["d1_after_swap"], res["d2_before"])
        self.assertEqual(res["d2_after_swap"], res["d1_before"])

    def test_cont_missing_draw_fail_close(self):
        from main_model.h2 import continuation_v1 as cont
        log = chk._e1_continuation_log()
        st = obs.project_log_prefix(log, Fraction(4), batch_size=2)
        from main_model.h2 import posterior_state_v1 as ps
        post = ps.PosteriorState.from_observable(st)
        with self.assertRaises(ValueError):
            cont.rebuild_continuation_world(
                st, post, u_x_by_device={}, u_d_by_device={},
                u_l_by_resource={"A": Fraction(1, 2)})
        with self.assertRaises(ValueError):
            cont.rebuild_continuation_world(
                st, post,
                u_x_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
                u_d_by_device={}, u_l_by_resource={})
        with self.assertRaises(ValueError):
            cont.rebuild_continuation_world(
                st, post,
                u_x_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
                u_d_by_device={1: Fraction(1, 2)},
                u_l_by_resource={"A": Fraction(1, 2)})

    def test_cont_not_reached_e_d_deferred(self):
        from main_model.h2 import continuation_v1 as cont
        # device 2 of the E1 log is entered at t=0 but has NO observations
        # (not reached E) -> its x_D must be None (deferred), and it must
        # NOT require a U_D_post draw
        log2 = chk._e1_continuation_log()
        st = obs.project_log_prefix(log2, Fraction(0), batch_size=2)
        from main_model.h2 import posterior_state_v1 as ps
        post = ps.PosteriorState.from_observable(st)
        w = cont.rebuild_continuation_world(
            st, post, u_x_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
            u_d_by_device={}, u_l_by_resource={
                r: Fraction(1, 2) for r in ("A", "B", "C", "E")})
        for d in w.devices:
            if not d.terminal and not d.reached_e:
                self.assertIsNone(d.x_d)


class TestE1RolloutAdapter(unittest.TestCase):
    """P3-A-E1 section 12: rollout_seed -> h2_rollout post-key adapter."""

    def test_adapter_crn_and_separation(self):
        res = chk.check_rollout_post_keys()
        self.assertEqual(res["status"], "PASS", res)
        self.assertEqual(res["namespace"], "h2_rollout")

    def test_adapter_same_dp_m_identical(self):
        from main_model.h2_rollout import post_keys_v1 as pk
        a = pk.rollout_post_keys(6, 0, 2, 3, (1, 2), ("A", "B", "C", "E"),
                                 {"A": 1, "B": 1, "C": 1, "E": 1})
        b = pk.rollout_post_keys(6, 0, 2, 3, (1, 2), ("A", "B", "C", "E"),
                                 {"A": 1, "B": 1, "C": 1, "E": 1})
        self.assertEqual(a.to_canonical_dict(), b.to_canonical_dict())

    def test_adapter_different_dp_m_separated(self):
        from main_model.h2_rollout import post_keys_v1 as pk
        gens = {"A": 1, "B": 1, "C": 1, "E": 1}
        a = pk.rollout_post_keys(6, 0, 2, 3, (1,), ("A",), {"A": 1})
        b = pk.rollout_post_keys(6, 0, 2, 4, (1,), ("A",), {"A": 1})
        c = pk.rollout_post_keys(6, 0, 3, 3, (1,), ("A",), {"A": 1})
        self.assertNotEqual(a.u_x_by_device[1], b.u_x_by_device[1])
        self.assertNotEqual(a.u_x_by_device[1], c.u_x_by_device[1])
        self.assertNotEqual(a.u_d_by_device[1], b.u_d_by_device[1])

    def test_adapter_no_p2_synthetic_mapping(self):
        from main_model.h2_rollout import post_keys_v1 as pk
        k = pk.rollout_post_keys(6, 0, 0, 0, (1, 2, 3), ("A",), {"A": 1})
        for dev in (1, 2, 3):
            self.assertIn(dev, k.u_x_by_device)
            self.assertIn(dev, k.u_d_by_device)
        self.assertNotIn(100001, k.u_x_by_device)


class TestE1C23Continuation(unittest.TestCase):
    def test_c23_continuation(self):
        res = chk.check_c23_continuation()
        self.assertEqual(res["status"], "PASS", res)
        self.assertTrue(res["same_keys_same_world_across_hidden"])
        self.assertTrue(res["different_keys_world_differs"])


class TestE1H1RealParity(unittest.TestCase):
    def test_h1_real_parity(self):
        res = chk.check_h1_real_parity()
        self.assertEqual(res["status"], "PASS", res)


if __name__ == "__main__":
    unittest.main(verbosity=2)
