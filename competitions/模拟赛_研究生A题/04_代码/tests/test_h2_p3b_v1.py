#!/usr/bin/env python3
"""Q3-H2-P3-B tests: rollout kernel, H1 fallback parity, future D timing,
U_Y consumption, lifetime generation, CRN, quota selector + causality,
C_rollout accounting, Q_hat/SE, C23 rollout.

Python 3.12, standard library only.
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

from main_model.h2_rollout import rollout_engine_v1 as re1  # noqa: E402
from main_model.h2 import quota_selector_v1 as qsel  # noqa: E402
from main_model.h2 import q_estimator_v1 as qest  # noqa: E402
from checker import h2_p3b_checker_v1 as chk  # noqa: E402


class TestP3BChecker(unittest.TestCase):
    def test_checker_overall(self):
        res = chk.run_all()
        self.assertEqual(res["overall"], "PASS", res)
        for c in res["checks"]:
            self.assertEqual(c["status"], "PASS", c["check"])

    def test_h1_fallback_parity_all_scenarios(self):
        res = chk.check_h1_fallback_parity()
        self.assertEqual(res["status"], "PASS", res)
        for row in res["rows"]:
            self.assertEqual(row["ref_t_end"], row["p3_t_end"], row)
            self.assertTrue(row["ref_core"] == row["p3_core"], row)


class TestRolloutKernel(unittest.TestCase):
    def test_kernel_absorbs_2_devices(self):
        res = chk.check_rollout_kernel()
        self.assertEqual(res["status"], "PASS", res)
        for row in res["rows"]:
            self.assertEqual(row["passed"] + row["exited"], 2)
            self.assertTrue(Fraction(row["t_end"]) > 0)

    def test_first_actions_all_supported(self):
        res = chk.check_rollout_kernel()
        actions = {row["action"] for row in res["rows"]}
        self.assertIn(re1.A_START_HEAD, actions)
        self.assertIn(re1.A_H1_NOOP, actions)
        self.assertIn(re1.A_WAIT_EVENT, actions)
        self.assertIn(re1.A_PM_IDLE, actions)


class TestFutureD(unittest.TestCase):
    def test_d_materialized_once_per_device(self):
        res = chk.check_future_d_materialization()
        self.assertEqual(res["status"], "PASS", res)
        self.assertEqual(res["n_d_created"], 2)
        self.assertEqual(res["consumed_u_d"], 2)

    def test_d_prior_drives_state(self):
        res = chk.check_future_d_materialization()
        self.assertEqual(res["status"], "PASS", res)


class TestUYConsumption(unittest.TestCase):
    def test_all_pass_consumes_8(self):
        res = chk.check_u_y_consumption()
        self.assertEqual(res["status"], "PASS", res)
        self.assertEqual(res["all_pass_u_y"], 8)

    def test_retest_consumes_per_observation(self):
        res = chk.check_u_y_consumption()
        self.assertEqual(res["status"], "PASS", res)


class TestLifetimeGeneration(unittest.TestCase):
    def test_new_generation_binds_new_u_l(self):
        res = chk.check_lifetime_generation()
        self.assertEqual(res["status"], "PASS", res)
        self.assertGreaterEqual(res["n_replacements"], 1)


class TestCRN(unittest.TestCase):
    def test_crn_world_manifest(self):
        res = chk.check_crn_world()
        self.assertEqual(res["status"], "PASS", res)


class TestQuota(unittest.TestCase):
    def test_c_eval_6(self):
        res = chk.check_quota_selector()
        self.assertEqual(res["status"], "PASS", res)
        self.assertEqual(res["rows"][6]["wait_selected"], 3)
        self.assertEqual(res["rows"][6]["pm_selected"], 3)

    def test_c_eval_8(self):
        res = chk.check_quota_selector()
        self.assertEqual(res["rows"][8]["wait_selected"], 4)
        self.assertEqual(res["rows"][8]["pm_selected"], 4)

    def test_causality(self):
        res = chk.check_quota_causality()
        self.assertEqual(res["status"], "PASS", res)
        self.assertTrue(res["state_at_t4_identical"])

    def test_invariants(self):
        # direct: build a batch that exhausts both caps and check invariants
        points = []
        for i in range(12):
            points.append(qsel.DecisionPointEvent(
                dp=i, time=Fraction(i), resource="A", kind="dispatch",
                wait_legal=True, pm_legal=False, age_h=Fraction(130)))
        ages = (Fraction(130), Fraction(170), Fraction(210))
        for i in range(12):
            points.append(qsel.DecisionPointEvent(
                dp=100 + i, time=Fraction(100 + i), resource="A",
                kind="maintenance", wait_legal=False, pm_legal=True,
                age_h=ages[i % 3]))
        for c_eval in (6, 8):
            r = qsel.run_online_selection(c_eval, points)
            self.assertEqual(r["wait_selected"], (c_eval + 1) // 2)
            self.assertEqual(r["pm_selected"], c_eval // 2)
            self.assertLessEqual(r["selected_total"], c_eval)
            self.assertEqual(qsel.check_invariants(r), [])


class TestRolloutCount(unittest.TestCase):
    def test_c_rollout_candidates(self):
        res = chk.check_rollout_count()
        self.assertEqual(res["status"], "PASS", res)
        self.assertEqual(res["worst_cases"]["(4,8)"], 96)
        self.assertEqual(res["worst_cases"]["(8,6)"], 144)
        self.assertEqual(res["worst_cases"]["(8,8)"], 192)


class TestQEstimator(unittest.TestCase):
    def test_q_hat_and_se(self):
        res = chk.check_q_estimator()
        self.assertEqual(res["status"], "PASS", res)

    def test_paired_d_m(self):
        t_s = Fraction(10)
        a = (Fraction(100), Fraction(120), Fraction(110), Fraction(90))
        b = (Fraction(105), Fraction(115), Fraction(105), Fraction(95))
        est = qest.q_hat_from_t_end(t_s, a, dp=0, action="START_HEAD",
                                    a_h1=qest.A_H1_DISPATCH,
                                    t_end_h1_by_world=b)
        self.assertEqual(len(est.d_m), 4)
        self.assertIsNotNone(est.se_m)


if __name__ == "__main__":
    unittest.main(verbosity=2)
