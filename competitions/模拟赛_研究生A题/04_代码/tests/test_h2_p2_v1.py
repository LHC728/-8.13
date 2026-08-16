#!/usr/bin/env python3
"""Q3-H2-P2 tests: posterior defect-state generator (POST-01..14) and
conditional residual-lifetime generator (LIFE-01..10).

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

from main_model.h2 import frozen_params_v1 as fp  # noqa: E402
from main_model.h2 import posterior_generator_v1 as pg  # noqa: E402
from main_model.h2 import lifetime_generator_v1 as lg  # noqa: E402
from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from checker import h2_posterior_checker_v1 as pchk  # noqa: E402
from checker import h2_residual_lifetime_checker_v1 as lchk  # noqa: E402

N, A = "N", "A"


def _p1(abc_key, joint=None):
    """P(x_A=1 | ABC posterior) marginal helper."""
    pass


class TestPosterior(unittest.TestCase):
    def test_post01_prior_only(self):
        # no observations, not yet at E -> 8-state posterior == prior
        post = pg.abc_posterior_8({}, ())
        for (xa, xb, xc), p in post.items():
            prior = (fp.Q_ABC["A"] if xa else 1 - fp.Q_ABC["A"])
            prior *= (fp.Q_ABC["B"] if xb else 1 - fp.Q_ABC["B"])
            prior *= (fp.Q_ABC["C"] if xc else 1 - fp.Q_ABC["C"])
            self.assertEqual(p, prior)

    def test_post02_one_normal_a(self):
        kern = fp.observation_kernel()
        alpha, beta = kern["A"]["alpha"], kern["A"]["beta"]
        w0 = (1 - fp.Q_ABC["A"]) * (1 - alpha)  # x=0, Y=N
        w1 = fp.Q_ABC["A"] * beta               # x=1, Y=N
        p1 = w1 / (w0 + w1)
        post = pg.abc_posterior_8({"A": (N,)}, ())
        marg = sum(p for (xa, _b, _c), p in post.items() if xa == 1)
        self.assertEqual(marg, p1)

    def test_post03_one_abnormal_a(self):
        kern = fp.observation_kernel()
        alpha, beta = kern["A"]["alpha"], kern["A"]["beta"]
        w0 = (1 - fp.Q_ABC["A"]) * alpha   # x=0, Y=A
        w1 = fp.Q_ABC["A"] * (1 - beta)    # x=1, Y=A
        p1 = w1 / (w0 + w1)
        post = pg.abc_posterior_8({"A": (A,)}, ())
        marg = sum(p for (xa, _b, _c), p in post.items() if xa == 1)
        self.assertEqual(marg, p1)

    def test_post04_abnormal_then_normal(self):
        kern = fp.observation_kernel()
        alpha, beta = kern["A"]["alpha"], kern["A"]["beta"]
        w0 = (1 - fp.Q_ABC["A"]) * alpha * (1 - alpha)  # A then N
        w1 = fp.Q_ABC["A"] * (1 - beta) * beta
        p1 = w1 / (w0 + w1)
        post = pg.abc_posterior_8({"A": (A, N)}, ())
        marg = sum(p for (xa, _b, _c), p in post.items() if xa == 1)
        self.assertEqual(marg, p1)

    def test_post05_abnormal_abnormal_terminal(self):
        kern = fp.observation_kernel()
        alpha, beta = kern["A"]["alpha"], kern["A"]["beta"]
        w0 = (1 - fp.Q_ABC["A"]) * alpha * alpha
        w1 = fp.Q_ABC["A"] * (1 - beta) * (1 - beta)
        p1 = w1 / (w0 + w1)
        post = pg.abc_posterior_8({"A": (A, A)}, ())
        marg = sum(p for (xa, _b, _c), p in post.items() if xa == 1)
        self.assertEqual(marg, p1)

    def test_post06_e_normal_updates_d_when_abc_clear(self):
        # ABC all-clear, obs_E=[N] -> E observation updates D
        abc = (0, 0, 0)
        p1 = pg.d_given_abc((N,), abc)
        kern = fp.observation_kernel()
        le1 = kern["E"]["beta"]      # H nonempty, Y=N
        le0 = 1 - kern["E"]["alpha"]  # H empty, Y=N
        expected = (fp.Q_D * le1) / (fp.Q_D * le1 + (1 - fp.Q_D) * le0)
        self.assertEqual(p1, expected)
        self.assertNotEqual(p1, fp.Q_D)  # E did update D

    def test_post07_e_abnormal_with_abc_pass(self):
        abc = (0, 0, 0)
        p1 = pg.d_given_abc((A,), abc)
        kern = fp.observation_kernel()
        le1 = 1 - kern["E"]["beta"]   # H nonempty, Y=A
        le0 = kern["E"]["alpha"]      # H empty, Y=A
        expected = (fp.Q_D * le1) / (fp.Q_D * le1 + (1 - fp.Q_D) * le0)
        self.assertEqual(p1, expected)

    def test_post08_h_abc_nonempty_d_equals_q_d(self):
        for abc in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)):
            for oe in ((), (N,), (A,)):
                self.assertEqual(pg.d_given_abc(oe, abc), fp.Q_D)

    def test_post09_abc_empty_e_updates_d(self):
        p_no_e = pg.d_given_abc((), (0, 0, 0))
        # no obs_E -> prior
        self.assertEqual(p_no_e, fp.Q_D)
        p_n = pg.d_given_abc((N,), (0, 0, 0))
        self.assertNotEqual(p_n, fp.Q_D)
        p_a = pg.d_given_abc((A,), (0, 0, 0))
        self.assertNotEqual(p_a, fp.Q_D)

    def test_post10_same_observable_same_posterior(self):
        post1 = pg.joint_posterior_16({"A": (N,), "B": (N,), "C": (N,)}, (N,))
        post2 = pg.joint_posterior_16({"A": (N,), "B": (N,), "C": (N,)}, (N,))
        self.assertEqual(post1, post2)

    def test_post11_terminal_device_absorbed(self):
        # PosteriorState marks terminal; P2 never resamples terminal devices
        log = [
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "2",
             "device_id": 1, "process": "A", "effective_attempt_no": 1,
             "resource_id": "A", "outcome": "PASS"},
            {"event_type": "DEVICE_TERMINAL", "event_time": "5",
             "device_id": 1, "terminal_state": "PASSED"},
        ]
        st = obs.project_log_prefix(log, Fraction(6), batch_size=2)
        post = ps.PosteriorState.from_observable(st)
        self.assertTrue(post.devices[0].terminal)

    def test_post12_not_yet_entered_prior(self):
        ua, ub, uc = Fraction(0), Fraction(0), Fraction(0)
        xa, xb, xc = pg.sample_prior_abc_components(ua, ub, uc)
        self.assertEqual((xa, xb, xc), (1, 1, 1))
        # D drawn only at the junction from the prior
        self.assertEqual(pg.prior_d(Fraction(0)), 1)
        self.assertEqual(pg.prior_d(Fraction(1)), 0)

    def test_post13_d_not_prematurely_materialized(self):
        # obs_E empty -> 8-state ABC only; joint_posterior is None
        joint = pg.joint_posterior_16({"A": (N,)}, ())
        abc = pg.abc_posterior_8({"A": (N,)}, ())
        self.assertEqual(len(joint), 16)
        self.assertEqual(len(abc), 8)
        st = obs.project_log_prefix(
            [{"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
              "device_id": 1,
              "true_state": {"A": False, "B": False, "C": False}},
             {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "2",
              "device_id": 1, "process": "A", "effective_attempt_no": 1,
              "resource_id": "A", "outcome": "PASS"}],
            Fraction(3), batch_size=2)
        post = ps.PosteriorState.from_observable(st)
        self.assertFalse(post.devices[0].reached_e)
        self.assertIsNone(post.devices[0].joint_posterior)

    def test_post14_inflight_no_result_ignored(self):
        # an in-flight (no-result) attempt must not enter the posterior
        log = [
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "2",
             "device_id": 1, "process": "A", "effective_attempt_no": 1,
             "resource_id": "A", "outcome": "PASS"},
            {"event_type": "ACTIVITY_START", "event_time": "2", "device_id": 1,
             "process": "A", "effective_attempt_no": 2, "resource_id": "A",
             "attempt_start_time": "2", "attempt_end_time": "9/2",
             "outcome": "NONE"},
            # attempt 2 is IN FLIGHT at t=3: no completed observation
        ]
        st = obs.project_log_prefix(log, Fraction(3), batch_size=2)
        self.assertEqual(len(st.devices[0].observations), 1)  # only attempt 1
        post = ps.PosteriorState.from_observable(st)
        marg = sum(Fraction(v) for (xa, _b, _c), v in post.devices[0].abc_posterior
                   if xa == 1)
        expected_posterior = pg.abc_posterior_8({"A": (N,)}, ())
        expected = sum(p for (xa, _b, _c), p in expected_posterior.items()
                       if xa == 1)
        self.assertEqual(marg, expected)


class TestLifetime(unittest.TestCase):
    def test_life01_age0_degenerate(self):
        res = lchk.check_age0_degenerate()
        self.assertEqual(res["status"], "PASS", res)

    def test_life02_pmax_exact(self):
        f120, f240 = fp.F120["A"], fp.F240["A"]
        pm30 = lg.p_max(Fraction(30), f120, f240)
        fa = Fraction(3, 100) * Fraction(30) / Fraction(120)  # F(30)=0.0075
        expected = (f240 - fa) / (Fraction(1) - fa)
        self.assertEqual(pm30, expected)

    def test_life03_v_below_pmax(self):
        f120, f240 = fp.F120["A"], fp.F240["A"]
        tau, cens = lg.conditional_residual(Fraction(1, 100),
                                            Fraction(0), f120, f240)
        self.assertFalse(cens)
        self.assertGreater(tau, Fraction(0))

    def test_life04_v_equals_pmax(self):
        f120, f240 = fp.F120["A"], fp.F240["A"]
        pm = lg.p_max(Fraction(0), f120, f240)
        tau, cens = lg.conditional_residual(pm, Fraction(0), f120, f240)
        self.assertFalse(cens)
        self.assertEqual(tau, Fraction(240))  # F^-1(F(240)) - 0

    def test_life05_v_above_pmax_right_censored(self):
        f120, f240 = fp.F120["A"], fp.F240["A"]
        pm = lg.p_max(Fraction(120), f120, f240)
        tau, cens = lg.conditional_residual(pm + lg.EPSILON,
                                            Fraction(120), f120, f240)
        self.assertTrue(cens)
        self.assertEqual(tau, Fraction(240) - Fraction(120))

    def test_life06_age210(self):
        f120, f240 = fp.F120["B"], fp.F240["B"]
        pm = lg.p_max(Fraction(210), f120, f240)
        # v = p_max/2 -> natural branch with a+tau <= 240
        tau, cens = lg.conditional_residual(pm / Fraction(2),
                                            Fraction(210), f120, f240)
        self.assertFalse(cens)
        self.assertLessEqual(Fraction(210) + tau, Fraction(240))
        # v = 0.5 > p_max(210) -> right-censored (conditional survival mass
        # above 210 is tiny for the frozen CDF)
        tau2, cens2 = lg.conditional_residual(Fraction(1, 2),
                                              Fraction(210), f120, f240)
        self.assertTrue(cens2)
        self.assertEqual(tau2, Fraction(30))

    def test_life07_exact_240(self):
        f120, f240 = fp.F120["C"], fp.F240["C"]
        for age in (Fraction(30), Fraction(120), Fraction(210)):
            pm = lg.p_max(age, f120, f240)
            tau, cens = lg.conditional_residual(pm, age, f120, f240)
            if not cens:
                self.assertLessEqual(age + tau, Fraction(240))

    def test_life08_a_plus_d_gt_240_mandatory(self):
        # a+d > 240 -> mandatory pre-start replacement (never optional PM);
        # the generator's clip keeps a+tau <= 240
        for resource in fp.RESOURCES:
            d = fp.DURATIONS_H[resource]
            age = Fraction(239)  # a + d > 240 for every resource
            pm = lg.p_max(age, fp.F120[resource], fp.F240[resource])
            tau, cens = lg.conditional_residual(pm + lg.EPSILON, age,
                                                fp.F120[resource],
                                                fp.F240[resource])
            self.assertTrue(cens)
            self.assertEqual(age + tau, Fraction(240))
            self.assertGreater(age + d, Fraction(240))  # mandatory domain
            # a + d == 240 -> completion-first then mandatory (boundary)
            age_eq = Fraction(240) - d
            tau_eq, cens_eq = lg.conditional_residual(
                lg.p_max(age_eq, fp.F120[resource], fp.F240[resource]),
                age_eq, fp.F120[resource], fp.F240[resource])
            self.assertFalse(cens_eq)
            self.assertLessEqual(age_eq + tau_eq, Fraction(240))

    def test_life09_resource_specific_cdf(self):
        for resource in fp.RESOURCES:
            pm0 = lg.p_max(Fraction(0), fp.F120[resource], fp.F240[resource])
            self.assertEqual(pm0, fp.F240[resource])

    def test_life10_old_generation_not_resampled(self):
        # the lifetime generator operates on (v, age, resource) only; past
        # generations are observable history and never resampled (P2
        # PosteriorState exposes only the CURRENT generation)
        st = obs.project_log_prefix(
            [{"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
              "device_id": 1,
              "true_state": {"A": False, "B": False, "C": False}},
             {"event_type": "EQUIPMENT_REPLACEMENT_START", "event_time": "1",
              "resource_id": "A", "kind": "preventive", "trigger": "preventive",
              "old_generation": 1, "new_generation": 2, "age_before": "1",
              "calibration_duration_hours": "1/2", "calibration_start": "1",
              "calibration_end": "3/2"},
             {"event_type": "EQUIPMENT_CALIBRATION_COMPLETE",
              "event_time": "3/2", "resource_id": "A", "generation": 2,
              "calibration_start": "1", "calibration_end": "3/2"}],
            Fraction(4), batch_size=2)
        post = ps.PosteriorState.from_observable(st)
        rsrc = next(r for r in post.resources if r.resource == "A")
        self.assertEqual(rsrc.generation, 2)  # current generation only

    def test_primary_deterministic(self):
        res = pchk.check_deterministic()
        self.assertEqual(res["status"], "PASS", res)
        res2 = lchk.check_deterministic()
        self.assertEqual(res2["status"], "PASS", res2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
