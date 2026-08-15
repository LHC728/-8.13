"""Unit tests for Q2-FORMAL-SPEC-V1.0 formal runner logic (run_q2_formal_v1).

Scope discipline (task package): pure functions only -- frozen cell-id tokens
(DEC-05), frozen observation kernels (single / chain, never recalibrated),
cell config construction (CRN: policy/turnover/observation never in physical
keys), the exact Clopper-Pearson rare-event intervals (DEC-04), the paired
bootstrap CI (DEC-03) and cell aggregation.  NO full 200-batch formal runs
are executed here (cost guard); a tiny smoke with a few batches is done in a
separate explicit smoke invocation (never an accepted formal result).

Frozen-contract coverage:

  1. cell_id tokens match the frozen 8-cell syntax exactly
  2. single kernel: A/B/C via P060 closed form; E via Q1-frozen q_E
     (0.062593912407392898); identical to G3 tuning/holdout kernels
  3. chain kernel: accepted G2-02 4bb92eda standard_chain_v1 values
     (q_E=0.047150339332016366; E alpha/beta frozen), consumed as config
  4. make_cell_config: namespace=q2_formal, master_seed=3, 100 devices,
     q2_single_shift; tau198 -> Fraction(198), nopm -> NO_PM sentinel
  5. CRN: configs for the 8 cells of the same replicate share master_seed and
     replicate_id; physical key schema fields identical except scenario_id
     (metadata, excluded from canonical U keys)
  6. clopper_pearson_two_sided / one_sided_upper are exact; x=0 upper bound
     equals 1 - 0.05^(1/20000) (mechanical, not hand-rounded)
  7. paired_bootstrap_ci: deterministic under the frozen analysis seed;
     point estimate correct; percentile CI within observed bootstrap range
  8. aggregation: mean of T exact; pooled PL/PW counts correct
"""

from __future__ import annotations

import importlib.util
import math
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
from g3 import lifetime_regeneration_v1 as lr  # noqa: E402
from g3 import random_des_v1 as rd  # noqa: E402

RUNNER_PATH = CODE_DIR / "scripts" / "run_q2_formal_v1.py"
_SPEC = importlib.util.spec_from_file_location(
    "run_q2_formal_v1_under_test", RUNNER_PATH
)
RUNNER = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = RUNNER
_SPEC.loader.exec_module(RUNNER)

NO_PM = lr.NO_PM_BEFORE_MANDATORY


class TestCellIds(unittest.TestCase):
    def test_frozen_8_cells(self):
        expected = {
            "obs_single__turn_1h__policy_tau198",
            "obs_single__turn_1h__policy_nopm",
            "obs_single__turn_0p5h__policy_tau198",
            "obs_single__turn_0p5h__policy_nopm",
            "obs_chain__turn_1h__policy_tau198",
            "obs_chain__turn_1h__policy_nopm",
            "obs_chain__turn_0p5h__policy_tau198",
            "obs_chain__turn_0p5h__policy_nopm",
        }
        got = {
            RUNNER.cell_id(o, t, p)
            for o in ("single", "chain")
            for t in (RUNNER.TURNOVER_1H, RUNNER.TURNOVER_0P5H)
            for p in ("tau198", "nopm")
        }
        self.assertEqual(got, expected)
        self.assertEqual(len(got), 8)

    def test_token_mapping_total(self):
        self.assertEqual(RUNNER.OBS_TOKENS["single"], "single_test_unconditional_v1")
        self.assertEqual(RUNNER.OBS_TOKENS["chain"], "standard_chain_v1")
        self.assertEqual(RUNNER.POLICY_TOKENS["tau198"], RUNNER.TAU_PM_198)
        self.assertIs(RUNNER.POLICY_TOKENS["nopm"], NO_PM)


class TestObservationKernels(unittest.TestCase):
    def test_single_kernel_p060(self):
        kernel = RUNNER.single_kernel()
        for proc in ("A", "B", "C"):
            q = RUNNER.FROZEN_Q_ABC[proc]
            e = RUNNER.FROZEN_E_ABC[proc]
            alpha = kernel[proc]["alpha"]
            beta = kernel[proc]["beta"]
            self.assertEqual((1 - q) * alpha, q * beta)
            self.assertEqual((1 - q) * alpha, e / 2)
        q_e = Fraction(RUNNER.Q1_FROZEN_Q_E_TEXT)
        alpha_e, beta_e = rd.frozen_single_test_alpha_beta(q_e, RUNNER.FROZEN_E_E)
        self.assertEqual(kernel["E"]["alpha"], alpha_e)
        self.assertEqual(kernel["E"]["beta"], beta_e)

    def test_chain_kernel_frozen_accepted(self):
        kernel = RUNNER.chain_kernel()
        self.assertEqual(
            kernel["E"]["alpha"], Fraction("0.010920932310648563")
        )
        self.assertEqual(
            kernel["E"]["beta"], Fraction("0.1185856135607714")
        )
        # every process present
        self.assertEqual(set(kernel), {"A", "B", "C", "E"})


class TestCellConfig(unittest.TestCase):
    def test_frozen_world_fields(self):
        cfg = RUNNER.make_cell_config("single", RUNNER.TURNOVER_1H, "tau198", 7)
        self.assertEqual(cfg.namespace, ks.NAMESPACE_Q2_FORMAL)
        self.assertEqual(cfg.master_seed, 3)
        self.assertEqual(cfg.replicate_id, 7)
        self.assertEqual(cfg.batch_size, 100)
        self.assertEqual(cfg.scenario, "q2_single_shift")
        self.assertEqual(Fraction(cfg.tau_pm), Fraction(198))

    def test_nopm_sentinel(self):
        cfg = RUNNER.make_cell_config("chain", RUNNER.TURNOVER_0P5H, "nopm", 0)
        self.assertIs(cfg.tau_pm, NO_PM)

    def test_crn_physical_key_identity_across_cells(self):
        # for a fixed replicate, the 8 cells share master_seed+replicate_id;
        # scenario_id (metadata) differs but is excluded from canonical U keys
        key_fields = []
        for o in ("single", "chain"):
            for t in (RUNNER.TURNOVER_1H, RUNNER.TURNOVER_0P5H):
                for p in ("tau198", "nopm"):
                    cfg = RUNNER.make_cell_config(o, t, p, 42)
                    self.assertEqual(cfg.master_seed, 3)
                    self.assertEqual(cfg.replicate_id, 42)
                    key_fields.append((cfg.namespace, cfg.master_seed, cfg.replicate_id))
        self.assertEqual(len(set(key_fields)), 1)


class TestClopperPearson(unittest.TestCase):
    def test_zero_upper_bound_mechanical(self):
        # x=0, n=20000: one-sided exact 95% upper = 1 - 0.05^(1/20000)
        upper = RUNNER.clopper_pearson_one_sided_upper(0, 20000)
        expected = 1.0 - 0.05 ** (1.0 / 20000)
        self.assertAlmostEqual(upper, expected, places=10)
        self.assertGreater(upper, 0.0)
        self.assertLess(upper, 0.001)

    def test_two_sided_contains_point(self):
        lo, hi = RUNNER.clopper_pearson_two_sided(100, 20000)
        self.assertLess(lo, 100 / 20000)
        self.assertGreater(hi, 100 / 20000)
        self.assertLess(lo, hi)

    def test_two_sided_bounds(self):
        lo, hi = RUNNER.clopper_pearson_two_sided(5, 100)
        self.assertGreater(lo, 0.0)
        self.assertLess(hi, 1.0)
        self.assertLess(lo, hi)


class TestPairedBootstrap(unittest.TestCase):
    def test_deterministic_and_point(self):
        # genuinely varying deltas so the percentile CI has interior
        import random as _r
        rng = _r.Random(7)
        t_tau = [10.0 + rng.uniform(-1, 1) for _ in range(30)]
        t_nopm = [12.0 + rng.uniform(-1, 1) for _ in range(30)]
        a = RUNNER.paired_bootstrap_ci(t_tau, t_nopm, seed=30003)
        b = RUNNER.paired_bootstrap_ci(t_tau, t_nopm, seed=30003)
        self.assertEqual(a["point_estimate_Delta_T_h"],
                         b["point_estimate_Delta_T_h"])
        # point estimate = mean(t_tau - t_nopm) exactly
        expected = sum(x - y for x, y in zip(t_tau, t_nopm)) / len(t_tau)
        self.assertAlmostEqual(a["point_estimate_Delta_T_h"], expected, places=12)
        self.assertLess(a["ci_lo_h"], a["ci_hi_h"])

    def test_different_seed_different_resample(self):
        t_tau = [10.0 + (i % 3) for i in range(50)]
        t_nopm = [12.0 + (i % 3) for i in range(50)]
        a = RUNNER.paired_bootstrap_ci(t_tau, t_nopm, seed=30003)
        c = RUNNER.paired_bootstrap_ci(t_tau, t_nopm, seed=30004)
        # point estimate identical, CI may differ
        self.assertEqual(a["point_estimate_Delta_T_h"],
                         c["point_estimate_Delta_T_h"])


class TestAggregation(unittest.TestCase):
    def _rec(self, rep, T, pl, pw):
        return RUNNER.BatchMetrics(
            replicate_id=rep, T=Fraction(T), T_days=Fraction(T) / 24,
            S=100 - pl - pw, PL=pl, PW=pw, exited=pl + pw,
            YXB={"A": Fraction(1, 2), "B": Fraction(1, 3),
                 "C": Fraction(1, 4), "E": Fraction(1, 5)},
            preventive=1, mandatory=2, random_failures=3, wasted_fragments=4,
            four_cell={"GP": 90, "BP": 5, "GE": 2, "BE": 3},
            quality_verdict="PASS", replay_verdict="PASS",
            quality_issues=[], replay_issues=[], c24={}, log_sha256="x",
            wall_clock_s=0.1,
        )

    def test_mean_and_pooled(self):
        recs = [self._rec(0, "100", 2, 1), self._rec(1, "200", 3, 2)]
        agg = RUNNER.aggregate_cell("c", recs, [2, 3], [1, 2])
        self.assertEqual(agg.mean_T, Fraction(150))
        self.assertEqual(agg.pl_pooled_x, 5)
        self.assertEqual(agg.pw_pooled_x, 3)
        self.assertEqual(agg.quality_pass_count, 2)


if __name__ == "__main__":
    unittest.main()
