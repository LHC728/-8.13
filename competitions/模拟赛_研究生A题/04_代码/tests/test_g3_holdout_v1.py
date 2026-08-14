"""Unit tests for G3-SPEC-V1.0 S8 holdout logic (run_g3_holdout_v1).

Scope discipline (task package): pure functions only -- the frozen holdout
config (G3-DEC-04: namespace=g3_holdout, 100 independent 100-device batches,
S7-frozen tau_pm=198), the C07 statistical smoke helpers (four-cell vs frozen
analytic multinomial anchor; batch-clustered empirical event-level lambda vs
analytic anchor), the E true-positive event counter and the frozen observation
kernel (P060 closed form + Q1-frozen q_E propagation). NO full 100-device
holdout batches are executed here (cost guard); the end-to-end runner is
exercised separately as an authorized holdout run.

Frozen-contract coverage:

  1. make_holdout_config: namespace=g3_holdout, master_seed=2 (independent
     seed pool; tuning uses master_seed=1), tau_pm=frozen 198 h, batch 100,
     q2_single_shift calendar; scenario_id never enters a canonical key
  2. frozen_tau_pm_h() == 198; the holdout never re-tunes
     (no tau_pm parameter is accepted anywhere in the runner)
  3. frozen observation kernel: A/B/C closed-form values are exact
     ((1-q)alpha = q beta = e/2; P060); E uses the Q1-frozen q_E
     propagation (matches accepted G2-02 to 1e-18)
  4. four_cell_counts extracts GP/BP/GE/BE from a C06 oracle aggregate
  5. batch_chi_square: exact z/chi2 on a hand-computed batch; chi2 = sum z^2
  6. family_smoke_diagnosis: flagged-count vs Binomial(100, 0.05) expectation;
     investigation flag fires only above the pre-registered threshold;
     single-batch 95 % non-coverage is NEVER an automatic program error
  7. batch_lambda_interval: batch-clustered mean/sd/min/max/quantiles vs the
     frozen analytic event-level anchor; analytic lambda reported WITHOUT a
     Monte-Carlo CI (monte_carlo_ci = NOT_REPORTED)
  8. count_e_true_positive_events: only E OBSERVATION_MATERIALIZED events with
     outcome=ABNORMAL and true_state=True count; other processes/outcomes do
     not
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
CODE_DIR = BASE / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from g3 import key_schema_v1 as ks  # noqa: E402
from g3 import random_des_v1 as rd  # noqa: E402

RUNNER_PATH = CODE_DIR / "scripts" / "run_g3_holdout_v1.py"
_SPEC = importlib.util.spec_from_file_location(
    "run_g3_holdout_v1_under_test", RUNNER_PATH
)
RUNNER = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = RUNNER
_SPEC.loader.exec_module(RUNNER)


class TestFrozenHoldoutConfig(unittest.TestCase):
    def test_namespace_and_seed_pool(self):
        cfg = RUNNER.make_holdout_config(7)
        self.assertEqual(cfg.namespace, ks.NAMESPACE_G3_HOLDOUT)
        self.assertEqual(cfg.master_seed, RUNNER.HOLDOUT_MASTER_SEED)
        # independent seed pool: tuning uses master_seed = 1
        self.assertNotEqual(RUNNER.HOLDOUT_MASTER_SEED, 1)
        self.assertEqual(cfg.replicate_id, 7)
        self.assertEqual(cfg.batch_size, 100)

    def test_frozen_tau_pm(self):
        self.assertEqual(RUNNER.frozen_tau_pm_h(), 198)
        cfg = RUNNER.make_holdout_config(0)
        self.assertEqual(Fraction(cfg.tau_pm), Fraction(198))
        # holdout runner exposes NO tau_pm CLI parameter (never re-tunes)
        import inspect
        src = inspect.getsource(RUNNER)
        self.assertNotIn('"--tau', src)

    def test_scenario_calendar(self):
        cfg = RUNNER.make_holdout_config(3)
        self.assertEqual(cfg.scenario, "q2_single_shift")
        self.assertEqual(Fraction(cfg.shift_length_h), Fraction(12))
        self.assertEqual(cfg.shifts_per_day, 1)

    def test_holdout_repetition_frozen(self):
        self.assertEqual(RUNNER.HOLDOUT_REPETITIONS, 100)
        self.assertEqual(RUNNER.FIRST_REPLICATE, 0)


class TestFrozenObservationKernel(unittest.TestCase):
    def test_abc_kernel_exact(self):
        kernel = RUNNER.frozen_observation_kernel()
        # P060: (1-q) alpha = q beta = e/2
        for proc in ("A", "B", "C"):
            q = RUNNER.FROZEN_Q_ABC[proc]
            e = RUNNER.FROZEN_E_ABC[proc]
            alpha = kernel[proc]["alpha"]
            beta = kernel[proc]["beta"]
            self.assertEqual((1 - q) * alpha, q * beta)
            self.assertEqual((1 - q) * alpha, e / 2)

    def test_e_kernel_matches_accepted_g2_02(self):
        kernel = RUNNER.frozen_observation_kernel()
        # accepted G2-02 single_test_unconditional_v1 response: alpha_E/beta_E
        # recomputed from q_E=0.062593912407392898 and e_E=0.02 via the frozen
        # closed form; tolerance 1e-18 (Q1 output rounds to 18 significant
        # digits, matching the tuning-runner contract).
        q_e = Fraction(RUNNER.Q1_FROZEN_Q_E_TEXT)
        e_e = RUNNER.FROZEN_E_E
        alpha_e, beta_e = rd.frozen_single_test_alpha_beta(q_e, e_e)
        self.assertAlmostEqual(
            float(kernel["E"]["alpha"]), float(alpha_e), places=18
        )
        self.assertAlmostEqual(
            float(kernel["E"]["beta"]), float(beta_e), places=18
        )


class TestFourCellCounts(unittest.TestCase):
    def test_extraction(self):
        agg = {"S": 90, "PL": 2, "PW": 1, "GP": 88, "BP": 2, "GE": 1, "BE": 9,
               "exited": 10}
        counts = RUNNER.four_cell_counts(agg)
        self.assertEqual(counts, {"GP": 88, "BP": 2, "GE": 1, "BE": 9})

    def test_missing_keys_default_zero(self):
        counts = RUNNER.four_cell_counts({"S": 100})
        self.assertEqual(counts, {"GP": 0, "BP": 0, "GE": 0, "BE": 0})


class TestBatchChiSquare(unittest.TestCase):
    def test_perfect_anchor_match(self):
        # counts exactly at expectation -> z ~ 0, chi2 ~ 0
        n = 100
        counts = {
            cat: round(n * RUNNER.C07_MULTINOMIAL_P[cat])
            for cat in ("GP", "BP", "GE", "BE")
        }
        chi2, z, _ = RUNNER.batch_chi_square(counts)
        self.assertLess(chi2, 1.0)
        for cat in ("GP", "BP", "GE", "BE"):
            self.assertLess(abs(z[cat]), 2.0)

    def test_hand_computed_single_category(self):
        # n_GP = 97 vs E = 92.509... ; z = (97 - 92.509..)/sqrt(100 p (1-p))
        counts = {"GP": 97, "BP": 1, "GE": 0, "BE": 2}
        chi2, z, _ = RUNNER.batch_chi_square(counts)
        p_gp = RUNNER.C07_MULTINOMIAL_P["GP"]
        expected_z = (97 - 100 * p_gp) / (100 * p_gp * (1 - p_gp)) ** 0.5
        self.assertAlmostEqual(z["GP"], expected_z, places=9)
        # chi2 is the Pearson form over the adequate-expected cells (GP/BP/BE)
        expected = sum(
            (float(counts[cat]) - 100 * RUNNER.C07_MULTINOMIAL_P[cat]) ** 2
            / (100 * RUNNER.C07_MULTINOMIAL_P[cat])
            for cat in RUNNER.C07_CHI2_CATEGORIES
        )
        self.assertAlmostEqual(chi2, expected, places=9)

    def test_chi2_is_pearson_form_over_adequate_cells(self):
        # chi2 = Pearson X^2 = sum (O-E)^2/E over GP/BP/BE only (GE excluded)
        counts = {"GP": 90, "BP": 2, "GE": 1, "BE": 7}
        n = 100
        chi2, z, counts_out = RUNNER.batch_chi_square(counts)
        expected = sum(
            (float(counts[cat]) - n * RUNNER.C07_MULTINOMIAL_P[cat]) ** 2
            / (n * RUNNER.C07_MULTINOMIAL_P[cat])
            for cat in RUNNER.C07_CHI2_CATEGORIES
        )
        self.assertAlmostEqual(chi2, expected, places=9)
        self.assertEqual(counts_out, counts)

    def test_ge_excluded_from_chi2(self):
        # a single GE=1 must NOT inflate chi2 (it is excluded); the z for GE
        # is still reported as a diagnostic
        counts = {"GP": 93, "BP": 2, "GE": 1, "BE": 4}
        chi2, z, _ = RUNNER.batch_chi_square(counts)
        expected = sum(
            (float(counts[cat]) - 100 * RUNNER.C07_MULTINOMIAL_P[cat]) ** 2
            / (100 * RUNNER.C07_MULTINOMIAL_P[cat])
            for cat in RUNNER.C07_CHI2_CATEGORIES
        )
        self.assertAlmostEqual(chi2, expected, places=9)
        # GE z is large (expected 0.08) but contributes nothing to chi2
        self.assertGreater(abs(z["GE"]), 2.0)


class TestGeDiagnostic(unittest.TestCase):
    def test_expected_count(self):
        diag = RUNNER.ge_diagnostic({"GE": 9}, n=100 * 100)
        self.assertEqual(diag["observed"], 9)
        self.assertAlmostEqual(diag["expected"], 10000 * 0.00081502602845540441,
                               places=9)
        self.assertIn("不自动判程序错误", diag["note"])

    def test_excluded_note(self):
        diag = RUNNER.ge_diagnostic({"GE": 0}, n=100)
        self.assertIn("卡方近似不适用", diag["note"])


class TestFamilySmokeDiagnosis(unittest.TestCase):
    def test_all_covered_no_investigation(self):
        diag = RUNNER.family_smoke_diagnosis([0.1, 0.2, 0.3] * 33, n_batches=99)
        self.assertEqual(diag["flagged_batch_count"], 0)
        self.assertFalse(diag["investigate_flag"])

    def test_expected_five_percent_flags_do_not_investigate(self):
        # 5 % of 100 batches flagged is ordinary chance under C07
        diag = RUNNER.family_smoke_diagnosis([100.0] * 5 + [0.1] * 95,
                                             n_batches=100)
        self.assertEqual(diag["flagged_batch_count"], 5)
        self.assertFalse(diag["investigate_flag"])
        self.assertAlmostEqual(diag["expected_flag_count_by_chance"], 5.0,
                               places=2)

    def test_high_flag_count_triggers_investigation(self):
        diag = RUNNER.family_smoke_diagnosis([100.0] * 40 + [0.1] * 60,
                                             n_batches=100)
        self.assertEqual(diag["flagged_batch_count"], 40)
        self.assertTrue(diag["investigate_flag"])

    def test_single_95_percent_non_coverage_is_never_auto_fail(self):
        # one flagged batch out of 100: investigation trigger, not an error
        diag = RUNNER.family_smoke_diagnosis([9.0] + [0.1] * 99, n_batches=100)
        self.assertEqual(diag["flagged_batch_count"], 1)
        self.assertFalse(diag["investigate_flag"])
        self.assertIn("不自动判程序错误", diag["note"])


class TestBatchLambdaInterval(unittest.TestCase):
    def test_anchor_consistency(self):
        # empirical values near the analytic per-batch expectation
        # BATCH * q_E * (1-beta_E)(2-beta_E)
        anchor = RUNNER.C07_LAMBDA_EVENT_LEVEL_ANCHOR
        q_e = RUNNER.C07_LAMBDA_ANCHOR_Q_E
        expected = q_e * anchor * RUNNER.BATCH_SIZE
        values = [expected + d for d in (-2, -1, 0, 1, 2)]
        res = RUNNER.batch_lambda_interval(values, n_batches=5)
        self.assertEqual(res["cluster_unit"], "one 100-device batch")
        self.assertAlmostEqual(
            res["empirical_mean_per_batch"], expected, places=6
        )
        self.assertEqual(res["monte_carlo_ci"], "NOT_REPORTED")
        self.assertAlmostEqual(res["analytic_mean_per_batch"], expected, places=9)

    def test_quantiles_and_bounds(self):
        res = RUNNER.batch_lambda_interval([10.0, 20.0, 30.0, 40.0], n_batches=4)
        self.assertEqual(res["empirical_min"], 10.0)
        self.assertEqual(res["empirical_max"], 40.0)
        self.assertGreaterEqual(res["empirical_q025"], 10.0)
        self.assertLessEqual(res["empirical_q975"], 40.0)

    def test_no_mc_ci(self):
        res = RUNNER.batch_lambda_interval([1.0, 2.0, 3.0])
        self.assertEqual(res["monte_carlo_ci"], "NOT_REPORTED")
        self.assertIn("不报 Monte Carlo 区间", res["note"])


class TestETruePositiveCounter(unittest.TestCase):
    def _ev(self, event_type, process=None, outcome=None, true_state=None):
        rec = {"event_type": event_type}
        if process is not None:
            rec["process"] = process
        if outcome is not None:
            rec["outcome"] = outcome
        if true_state is not None:
            rec["true_state"] = true_state
        return rec

    def test_counts_only_e_abnormal_true(self):
        obs = "OBSERVATION_MATERIALIZED"
        log = [
            self._ev(obs, "E", "ABNORMAL", True),   # count
            self._ev(obs, "E", "ABNORMAL", False),  # false positive -> no
            self._ev(obs, "E", "PASS", True),       # no
            self._ev(obs, "A", "ABNORMAL", True),   # not E -> no
            self._ev("EQUIPMENT_FAILURE"),           # not observation -> no
        ]
        self.assertEqual(RUNNER.count_e_true_positive_events(log), 1)

    def test_empty_log(self):
        self.assertEqual(RUNNER.count_e_true_positive_events([]), 0)


if __name__ == "__main__":
    unittest.main()
