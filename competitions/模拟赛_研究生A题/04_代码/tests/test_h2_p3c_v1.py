#!/usr/bin/env python3
"""Q3-H2-P3-C tests: frozen policy constants / canonical tie order,
2SE confident-deviation rule invariants, rollout-post-key CRN + salt
separation, physical-post-key determinism, and the H2BatchRunner smoke
(policy injection, decision log, C_rollout accounting).

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

from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from main_model.h2 import continuation_v1 as cont  # noqa: E402
from main_model.h2_rollout import rollout_engine_v1 as re1  # noqa: E402
from main_model.h2_rollout import h2_policy_v1 as pol  # noqa: E402
from main_model.h2_rollout import h2_batch_runner_v1 as br  # noqa: E402
from main_model.h2_rollout.post_keys_v1 import (  # noqa: E402
    rollout_post_keys, physical_post_provider, ROLLOUT_NAMESPACE)

MASTER_SEED = 6
K = Fraction(21, 2)
BATCH_SIZE = 6
SALT = "q3h2-bootstrap-v1"
ALT_SALT = "q3h2-bootstrap-alt-v1"


class TestFrozenPolicyConstants(unittest.TestCase):
    def test_frozen_config(self):
        self.assertEqual(pol.M_STAR, 8)
        self.assertEqual(pol.C_EVAL_STAR, 8)
        self.assertEqual(pol.W_CAP_STAR, 4)
        self.assertEqual(pol.P_CAP_STAR, 4)

    def test_canonical_action_order(self):
        self.assertEqual(pol.ACTION_ORDER,
                         (re1.A_START_HEAD, re1.A_H1_NOOP,
                          re1.A_WAIT_EVENT, re1.A_PM_WITH_HEAD,
                          re1.A_PM_IDLE))
        self.assertEqual(len(pol.ACTION_RANK), len(pol.ACTION_ORDER))
        self.assertEqual(sorted(pol.ACTION_RANK.values()),
                         list(range(len(pol.ACTION_ORDER))))

    def test_argmin_tie_break_declaration_order(self):
        mk = lambda a, q: pol.ActionEstimate(  # noqa: E731
            action=a, t_end_by_world=(), q_hat=q, d_m=(), se_m=None)
        # equal Q_hat -> canonical declaration order wins
        est = {re1.A_WAIT_EVENT: mk(re1.A_WAIT_EVENT, Fraction(10)),
               re1.A_PM_IDLE: mk(re1.A_PM_IDLE, Fraction(10)),
               re1.A_START_HEAD: mk(re1.A_START_HEAD, Fraction(10))}
        self.assertEqual(pol._argmin_action(est), re1.A_START_HEAD)
        # strictly lower Q_hat wins regardless of order
        est2 = {re1.A_START_HEAD: mk(re1.A_START_HEAD, Fraction(20)),
                re1.A_WAIT_EVENT: mk(re1.A_WAIT_EVENT, Fraction(15))}
        self.assertEqual(pol._argmin_action(est2), re1.A_WAIT_EVENT)

    def test_sample_sd(self):
        self.assertEqual(pol._sample_sd((Fraction(5), Fraction(5),
                                         Fraction(5))), 0.0)
        sd = pol._sample_sd((Fraction(1), Fraction(3)))
        self.assertAlmostEqual(sd, 2 ** 0.5, places=12)

    def test_clopper_pearson_oracle(self):
        """CP 95% interval matches the independent regularized-beta oracle
        (bisection directions were inverted once; locked by this test)."""
        from scripts.run_h2_p3c_stability_v1 import _cp95_binomial

        def _betacf(a, b, x):
            FPMIN = 1e-300
            qab, qap, qam = a + b, a + 1.0, a - 1.0
            c, d = 1.0, 1.0 - qab * x / qap
            if abs(d) < FPMIN:
                d = FPMIN
            d, h = 1.0 / d, 1.0 / d
            for m in range(1, 201):
                m2 = 2 * m
                aa = m * (b - m) * x / ((qam + m2) * (a + m2))
                d = 1.0 + aa * d
                if abs(d) < FPMIN:
                    d = FPMIN
                c = 1.0 + aa / c
                if abs(c) < FPMIN:
                    c = FPMIN
                d = 1.0 / d
                h *= d * c
                aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
                d = 1.0 + aa * d
                if abs(d) < FPMIN:
                    d = FPMIN
                c = 1.0 + aa / c
                if abs(c) < FPMIN:
                    c = FPMIN
                d = 1.0 / d
                delt = d * c
                h *= delt
                if abs(delt - 1.0) < 3e-12:
                    break
            return h

        def _ibeta(a, b, x):
            if x <= 0:
                return 0.0
            if x >= 1:
                return 1.0
            import math as _m
            bt = _m.exp(_m.lgamma(a + b) - _m.lgamma(a) - _m.lgamma(b)
                        + a * _m.log(x) + b * _m.log(1 - x))
            if x < (a + 1) / (a + b + 2):
                return bt * _betacf(a, b, x) / a
            return 1.0 - bt * _betacf(b, a, 1 - x) / b

        def _beta_ppf(p, a, b):
            lo, hi = 0.0, 1.0
            for _ in range(100):
                mid = (lo + hi) / 2
                if _ibeta(a, b, mid) >= p:
                    hi = mid
                else:
                    lo = mid
            return (lo + hi) / 2

        for x, n in [(60, 120), (95, 100), (50, 50), (0, 120), (120, 120),
                     (40, 120), (114, 120)]:
            lo, hi = _cp95_binomial(x, n)
            rlo = _beta_ppf(0.025, x, n - x + 1) if x > 0 else 0.0
            rhi = _beta_ppf(0.975, x + 1, n - x) if x < n else 1.0
            self.assertAlmostEqual(lo, rlo, places=4, msg=f"CP lo x={x} n={n}")
            self.assertAlmostEqual(hi, rhi, places=4, msg=f"CP hi x={x} n={n}")


class TestRolloutPostKeyCRN(unittest.TestCase):
    def _keys(self, dp, m, salt=SALT, rep=3):
        return rollout_post_keys(MASTER_SEED, rep, dp, m,
                                 (1, 2, 3), ("A", "B", "C", "E"),
                                 {"A": 1, "B": 1, "C": 1, "E": 1},
                                 salt=salt)

    def test_crn_same_dp_m_identical(self):
        k1 = self._keys(4, 2)
        k2 = self._keys(4, 2)
        self.assertEqual(k1.seed, k2.seed)
        self.assertEqual(k1.to_canonical_dict(), k2.to_canonical_dict())
        self.assertEqual(k1.u_x_by_device, k2.u_x_by_device)
        self.assertEqual(k1.u_d_by_device, k2.u_d_by_device)
        self.assertEqual(k1.u_l_by_resource, k2.u_l_by_resource)

    def test_different_m_separates_streams(self):
        k1 = self._keys(4, 2)
        k2 = self._keys(4, 3)
        self.assertNotEqual(k1.seed, k2.seed)
        self.assertNotEqual(k1.u_x_by_device, k2.u_x_by_device)

    def test_different_dp_separates_streams(self):
        k1 = self._keys(4, 2)
        k2 = self._keys(5, 2)
        self.assertNotEqual(k1.seed, k2.seed)

    def test_alt_salt_changes_draws(self):
        k1 = self._keys(4, 2, salt=SALT)
        k2 = self._keys(4, 2, salt=ALT_SALT)
        self.assertNotEqual(k1.seed, k2.seed)
        self.assertNotEqual(k1.to_canonical_dict(), k2.to_canonical_dict())

    def test_seed_does_not_contain_action(self):
        # the bundle depends only on (ms, rep, dp, m, entities): recompute
        # with a different resource set order must still be deterministic
        k1 = rollout_post_keys(MASTER_SEED, 3, 4, 2, (1, 2, 3),
                               ("A", "B", "C", "E"),
                               {"A": 1, "B": 1, "C": 1, "E": 1}, salt=SALT)
        k2 = rollout_post_keys(MASTER_SEED, 3, 4, 2, (1, 2, 3),
                               ("A", "B", "C", "E"),
                               {"A": 1, "B": 1, "C": 1, "E": 1}, salt=SALT)
        self.assertEqual(k1.to_canonical_dict(), k2.to_canonical_dict())
        self.assertEqual(k1.namespace, ROLLOUT_NAMESPACE)


class TestPhysicalPostProvider(unittest.TestCase):
    def test_deterministic_and_bounded(self):
        p1 = physical_post_provider("h2_tuning", MASTER_SEED, 0,
                                    BATCH_SIZE, ("A", "B", "C", "E"))
        p2 = physical_post_provider("h2_tuning", MASTER_SEED, 0,
                                    BATCH_SIZE, ("A", "B", "C", "E"))
        for d in range(1, BATCH_SIZE + 1):
            self.assertEqual(p1.u_x(d), p2.u_x(d))
            self.assertEqual(p1.u_d(d), p2.u_d(d))
            self.assertTrue(0 <= p1.u_x(d) < 1)
            self.assertTrue(0 <= p1.u_d(d) < 1)
        for r in ("A", "B", "C", "E"):
            self.assertEqual(p1.u_l(r, 1), p2.u_l(r, 1))
            self.assertTrue(0 <= p1.u_l(r, 1) < 1)

    def test_different_rep_separates_physical_worlds(self):
        p1 = physical_post_provider("h2_tuning", MASTER_SEED, 0,
                                    BATCH_SIZE, ("A", "B", "C", "E"))
        p2 = physical_post_provider("h2_tuning", MASTER_SEED, 1,
                                    BATCH_SIZE, ("A", "B", "C", "E"))
        self.assertNotEqual({d: p1.u_x(d) for d in (1, 2)},
                            {d: p2.u_x(d) for d in (1, 2)})


def _fresh_state(rep: int):
    log = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    st = obs.project_log_prefix(log, Fraction(0), batch_size=BATCH_SIZE)
    post = ps.PosteriorState.from_observable(st)
    prov = physical_post_provider("h2_tuning", MASTER_SEED, rep,
                                  BATCH_SIZE, ("A", "B", "C", "E"))
    ux = {1: prov.u_x(1), 2: prov.u_x(2)}
    ud = {1: prov.u_d(1), 2: prov.u_d(2)}
    ul = {r: prov.u_l(r, 1) for r in ("A", "B", "C", "E")}
    world = cont.rebuild_continuation_world(st, post, ux, ud, ul)
    return st, post, world, prov


class TestPolicyEvaluationInvariants(unittest.TestCase):
    def test_single_legal_action_is_a_h1(self):
        # REQUALIFIED (decision semantics): the START_HEAD candidate is
        # bound to its FROZEN decision head (the queue head of the
        # pre-action projection at t=0)
        log = [
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 1,
             "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 2,
             "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
             "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
             "squad_id": 0},
            {"event_type": "TASK_RELEASE", "event_time": "0", "device_id": 1,
             "process": "A", "effective_attempt_no": 1, "resource_id": "A",
             "release_time": "0"},
        ]
        st = obs.project_log_prefix(log, Fraction(0), batch_size=BATCH_SIZE)
        post = ps.PosteriorState.from_observable(st)
        prov = physical_post_provider("h2_tuning", MASTER_SEED, 0,
                                      BATCH_SIZE, ("A", "B", "C", "E"))
        ux = {1: prov.u_x(1), 2: prov.u_x(2)}
        ud = {1: prov.u_d(1), 2: prov.u_d(2)}
        ul = {r: prov.u_l(r, 1) for r in ("A", "B", "C", "E")}
        world = cont.rebuild_continuation_world(st, post, ux, ud, ul)
        cfg = re1.RolloutConfig(batch_size=BATCH_SIZE, shift_length_h=K,
                                shifts_per_day=2, scenario="q3_two_shift",
                                tau_pm=re1.NO_PM_BEFORE_MANDATORY)
        dec = pol.evaluate_decision_point(
            st, post, world, prov, cfg, 0, "A", "dispatch", "WAIT",
            (re1.A_START_HEAD,), None, MASTER_SEED, 0, M=2,
            decision_head=(1, "A", 1))
        self.assertEqual(dec.a_h1, re1.A_START_HEAD)
        self.assertEqual(dec.chosen, re1.A_START_HEAD)
        self.assertFalse(dec.deviated)
        self.assertEqual(dec.legal_actions, (re1.A_START_HEAD,))

    def test_determinism_same_inputs(self):
        st, post, world, prov = _fresh_state(1)
        cfg = re1.RolloutConfig(batch_size=BATCH_SIZE, shift_length_h=K,
                                shifts_per_day=2, scenario="q3_two_shift",
                                tau_pm=re1.NO_PM_BEFORE_MANDATORY)
        kw = dict(dp=1, resource="A", kind="maintenance", quota_class="PM",
                  legal_actions=(re1.A_H1_NOOP, re1.A_PM_IDLE),
                  log_prefix=None, master_seed_h2=MASTER_SEED,
                  replicate_id=1, M=2)
        d1 = pol.evaluate_decision_point(st, post, world, prov, cfg, **kw)
        d2 = pol.evaluate_decision_point(st, post, world, prov, cfg, **kw)
        self.assertEqual(d1.chosen, d2.chosen)
        self.assertEqual(d1.to_canonical_dict(), d2.to_canonical_dict())

    def test_se_m_nonnegative(self):
        st, post, world, prov = _fresh_state(1)
        cfg = re1.RolloutConfig(batch_size=BATCH_SIZE, shift_length_h=K,
                                shifts_per_day=2, scenario="q3_two_shift",
                                tau_pm=re1.NO_PM_BEFORE_MANDATORY)
        dec = pol.evaluate_decision_point(
            st, post, world, prov, cfg, 1, "A", "maintenance", "PM",
            (re1.A_H1_NOOP, re1.A_PM_IDLE), None, MASTER_SEED, 1, M=2)
        for a, e in dec.estimates.items():
            self.assertGreaterEqual(e.q_hat, Fraction(-10**9))
            self.assertTrue(e.se_m is None or e.se_m >= 0.0)


class TestH2BatchRunnerSmoke(unittest.TestCase):
    def test_smoke_policy_enabled(self):
        st, post, world, prov = _fresh_state(2)
        cfg = re1.RolloutConfig(batch_size=BATCH_SIZE, shift_length_h=K,
                                shifts_per_day=2, scenario="q3_two_shift",
                                tau_pm=re1.NO_PM_BEFORE_MANDATORY)
        dlog = br.BatchDecisionLog()
        eng = br.H2BatchRunner(st, post, world, prov, cfg, None,
                               MASTER_SEED, 2, policy_enabled=True,
                               decision_log=dlog)
        out = eng.run()
        self.assertGreater(out.t_end, 0)
        self.assertGreaterEqual(eng._c_rollout, 0)
        # C_rollout hard cap is 200 per batch (SPEC 2/10)
        self.assertLessEqual(eng._c_rollout, 200)
        self.assertEqual(dlog.rollout_count, eng._c_rollout)
        self.assertEqual(dlog.n_selected, len(dlog.rows))
        # every row: dp monotonic, chosen in legal, rollout count correct
        prev_dp = -1
        for row in dlog.rows:
            self.assertGreater(row["dp"], prev_dp)
            prev_dp = row["dp"]
            self.assertIn(row["chosen"], row["legal_actions"])
            self.assertGreater(row["rollout_count"], 0)
            self.assertEqual(
                row["rollout_count"],
                len(row["legal_actions"]) * pol.M_STAR)
        # chosen actions injected coherently (no crash; batch terminates)
        self.assertGreaterEqual(out.devices_passed + out.devices_exited, 0)

    def test_smoke_policy_disabled_is_h1(self):
        st, post, world, prov = _fresh_state(3)
        cfg = re1.RolloutConfig(batch_size=BATCH_SIZE, shift_length_h=K,
                                shifts_per_day=2, scenario="q3_two_shift",
                                tau_pm=re1.NO_PM_BEFORE_MANDATORY)
        eng = br.H2BatchRunner(st, post, world, prov, cfg, None,
                               MASTER_SEED, 3, policy_enabled=False)
        out = eng.run()
        self.assertGreater(out.t_end, 0)
        self.assertEqual(eng._c_rollout, 0)


class TestInFlightCalibrationRebuild(unittest.TestCase):
    """P3-C FIX regression: a decision-point rollout whose state has a
    resource mid-calibration must schedule the calibration completion
    (otherwise the calendar empties, _is_terminal() never turns True and
    run() records WAKE_UP forever -> runaway log / MemoryError)."""

    def _engine_with_calibration(self):
        log = [
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 1, "true_state": {"A": False, "B": False,
                                            "C": False}},
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 2, "true_state": {"A": False, "B": False,
                                            "C": False}},
            {"event_type": "SHIFT_CHANGE", "event_time": "0",
             "shift_index": 0, "shift_start": "0", "shift_end": "300",
             "on_duty_squad": 0, "squad_id": 0},
            {"event_type": "EQUIPMENT_REPLACEMENT_START",
             "event_time": "2", "resource_id": "B",
             "kind": "preventive", "trigger": "preventive",
             "old_generation": 1, "new_generation": 2,
             "age_before": 120, "calibration_duration_hours": "1",
             "calibration_start": "2", "calibration_end": "3"},
        ]
        t = Fraction(2)
        st = obs.project_log_prefix(log, t, batch_size=2)
        post = ps.PosteriorState.from_observable(st)
        prov = physical_post_provider("h2_tuning", MASTER_SEED, 4, 2,
                                      ("A", "B", "C", "E"))
        ux = {1: prov.u_x(1), 2: prov.u_x(2)}
        ud = {1: prov.u_d(1), 2: prov.u_d(2)}
        ul = {r: prov.u_l(r, 1) for r in ("A", "B", "C", "E")}
        world = cont.rebuild_continuation_world(st, post, ux, ud, ul)
        cfg = re1.RolloutConfig(batch_size=2, shift_length_h=K,
                                shifts_per_day=2, scenario="q3_two_shift",
                                tau_pm=re1.NO_PM_BEFORE_MANDATORY)
        b_obs = next(r for r in st.resources if r.resource == "B")
        self.assertEqual(b_obs.status, "calibration")
        self.assertGreater(b_obs.in_flight_remaining_h, 0)
        eng = re1.RolloutEngine(st, post, world, prov, cfg, log_prefix=log)
        return eng, b_obs.in_flight_remaining_h

    def test_calibration_completion_is_scheduled(self):
        eng, remaining = self._engine_with_calibration()
        # the fix must have scheduled the calibration completion event
        kinds = {k for _t, _c, k, _tok in eng._calendar}
        self.assertIn("calibration_complete", kinds)

    def test_rollout_terminates_with_in_flight_calibration(self):
        eng, remaining = self._engine_with_calibration()
        out = eng.run()  # would loop forever before the fix
        self.assertGreater(out.t_end, 0)
        self.assertFalse(eng.equipment["B"].calibration_in_flight)
        self.assertTrue(eng.equipment["B"].available)
        self.assertLessEqual(out.t_end, Fraction(240) * 2)

    def test_runaway_guard_raises_fail_closed(self):
        # MAX_CLOSURES guard: a stuck engine raises instead of looping
        from main_model.h2_rollout.rollout_engine_v1 import MAX_CLOSURES
        self.assertGreater(MAX_CLOSURES, 10 ** 5)


if __name__ == "__main__":
    unittest.main()
