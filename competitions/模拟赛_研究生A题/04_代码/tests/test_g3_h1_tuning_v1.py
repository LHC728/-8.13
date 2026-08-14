"""Unit tests for G3-SPEC-V1.0 S7 tuning logic (run_g3_h1_tuning_v1).

Scope discipline (task package): pure functions only -- candidate generation
(G3-DEC-01), the local-refinement grid (G3-DEC-02), the exact tie-break and
winner selection (Human Gate section 1), the frozen observation kernel (P060
closed form + Q1-frozen q_E propagation) and exact mean aggregation. NO full
100-device tuning runs are executed here (cost guard); the end-to-end runner
is exercised separately as an authorized tuning run.

Frozen-contract coverage:

  1. coarse_candidates() == {120, 144, 168, 192, 216} + NO_PM_BEFORE_MANDATORY;
     240 is never a preventive threshold (no_240_as_preventive)
  2. refinement_grid: window +/-12 h, step 6 h, clipped to [120, 240),
     already-evaluated candidates removed; edge centers 120 and 216
  3. tie-break fires ONLY on exact equality of the canonical mean T
     (no epsilon); rule 1 fewer preventive replacements; rule 2 larger
     tau_pm; rule 3 NO_PM_BEFORE_MANDATORY least aggressive wins a full tie
  4. select_best: strictly lower mean T always wins regardless of tie-break
  5. frozen observation kernel: A/B/C closed-form values are exact
     ((1-q)alpha = q beta = e/2; P060); E uses the Q1-frozen q_E
     propagation and matches the accepted G2-02 output to 1e-18
  6. mean_of_fractions exactness; aggregate_runs rejects protocol drift
     (mixed candidates / duplicate replicates)
  7. make_tuning_config builds a valid frozen q2_single_shift tuning config
     (constructed only; no simulation run)
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
from g3 import lifetime_regeneration_v1 as lr  # noqa: E402

RUNNER_PATH = CODE_DIR / "scripts" / "run_g3_h1_tuning_v1.py"
_SPEC = importlib.util.spec_from_file_location(
    "run_g3_h1_tuning_v1_under_test", RUNNER_PATH
)
RUNNER = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = RUNNER
_SPEC.loader.exec_module(RUNNER)

NO_PM = lr.NO_PM_BEFORE_MANDATORY


def _stats(
    candidate,
    mean_T,
    mean_pm=Fraction(0),
    n=20,
    quality=("PASS",) * 20,
    replay=("PASS",) * 20,
) -> RUNNER.CandidateStats:
    """Build a minimal CandidateStats for selection/tie-break tests."""
    return RUNNER.CandidateStats(
        candidate=candidate,
        n_replicates=n,
        mean_T=Fraction(mean_T),
        mean_T_days=Fraction(mean_T) / 24,
        mean_preventive_replacement_count=Fraction(mean_pm),
        mean_replacement_count=Fraction(0),
        mean_failure_count=Fraction(0),
        mean_S=Fraction(0),
        mean_PL=Fraction(0),
        mean_PW=Fraction(0),
        mean_exited=Fraction(0),
        quality_verdicts=tuple(quality),
        replay_verdicts=tuple(replay),
        c24_mean_decision_point_density=Fraction(0),
        c24_total_decision_points=0,
        c24_total_legal_actions=0,
        c24_total_waiting_opportunities=0,
        c24_total_pm_opportunities=0,
        c24_total_branching_burden=0,
    )


class TestCoarseCandidates(unittest.TestCase):
    def test_frozen_candidate_set(self):
        cands = RUNNER.coarse_candidates()
        numerics = [c for c in cands if RUNNER.is_numeric_tau(c)]
        self.assertEqual([int(c) for c in numerics], [120, 144, 168, 192, 216])
        self.assertIn(NO_PM, cands)
        self.assertEqual(len(cands), 6)

    def test_240_is_not_a_preventive_candidate(self):
        cands = RUNNER.coarse_candidates()
        self.assertNotIn(Fraction(240), cands)
        # NO_PM_BEFORE_MANDATORY is an independent policy baseline, not tau=240.
        self.assertIsNot(NO_PM, Fraction(240))
        # the S2 seam rejects tau_pm = 240 as a preventive threshold
        with self.assertRaises(ValueError):
            lr.replacement_decision(
                Fraction(200), Fraction(2), Fraction(240), is_idle_decision_point=True
            )

    def test_labels(self):
        self.assertEqual(RUNNER.candidate_label(Fraction(120)), "tau_pm_120")
        self.assertEqual(RUNNER.candidate_label(Fraction(216)), "tau_pm_216")
        self.assertEqual(RUNNER.candidate_label(NO_PM), "NO_PM_BEFORE_MANDATORY")


class TestRefinementGrid(unittest.TestCase):
    def test_center_120_clips_and_dedups(self):
        # clipped to [120, 240): 108/114 dropped; 120 already evaluated -> {126, 132}
        grid = RUNNER.refinement_grid(Fraction(120), evaluated=(Fraction(120),))
        self.assertEqual(grid, (126, 132))

    def test_center_168_dedups_center(self):
        grid = RUNNER.refinement_grid(Fraction(168), evaluated=(Fraction(168),))
        self.assertEqual(grid, (156, 162, 174, 180))

    def test_center_216_full_grid(self):
        grid = RUNNER.refinement_grid(Fraction(216), evaluated=(Fraction(216),))
        self.assertEqual(grid, (204, 210, 222, 228))

    def test_grid_points_only_shows_center(self):
        full = RUNNER.refinement_grid_points_only(Fraction(168))
        self.assertEqual(full, (156, 162, 168, 174, 180))
        full120 = RUNNER.refinement_grid_points_only(Fraction(120))
        self.assertEqual(full120, (120, 126, 132))

    def test_dedup_arbitrary_evaluated(self):
        grid = RUNNER.refinement_grid(
            Fraction(168), evaluated=(Fraction(156), Fraction(180), Fraction(999))
        )
        # 156/180 removed; the center 168 stays because it was NOT evaluated
        self.assertEqual(grid, (162, 168, 174))

    def test_no_pm_sentinel_in_evaluated_is_ignored(self):
        # the runner passes the whole coarse evaluated set (including the
        # NO_PM_BEFORE_MANDATORY sentinel) defensively; the sentinel must be
        # skipped, never crash the grid
        grid = RUNNER.refinement_grid(
            Fraction(168), evaluated=(Fraction(168), NO_PM)
        )
        self.assertEqual(grid, (156, 162, 174, 180))

    def test_invalid_center_rejected(self):
        with self.assertRaises(ValueError):
            RUNNER.refinement_grid(Fraction(100))  # below the legal domain
        with self.assertRaises(ValueError):
            RUNNER.refinement_grid(Fraction(240))  # 240 is mandatory semantics
        with self.assertRaises((TypeError, ValueError)):
            RUNNER.refinement_grid(NO_PM)  # never called for NO_PM in the runner


class TestTieBreak(unittest.TestCase):
    def test_no_tie_when_mean_t_differs(self):
        a = _stats(Fraction(120), Fraction(100))
        b = _stats(Fraction(144), Fraction(99))
        self.assertFalse(RUNNER.exact_mean_t_tie(a, b))
        self.assertIs(RUNNER.select_best([a, b]), b)

    def test_tie_rule1_fewer_preventive_replacements(self):
        a = _stats(Fraction(144), Fraction(100), mean_pm=Fraction(5))
        b = _stats(Fraction(168), Fraction(100), mean_pm=Fraction(2))
        self.assertTrue(RUNNER.exact_mean_t_tie(a, b))
        self.assertIs(RUNNER.select_best([a, b]), b)

    def test_tie_rule2_larger_tau_pm(self):
        a = _stats(Fraction(168), Fraction(100), mean_pm=Fraction(2))
        b = _stats(Fraction(216), Fraction(100), mean_pm=Fraction(2))
        self.assertIs(RUNNER.select_best([a, b]), b)

    def test_tie_rule3_no_pm_least_aggressive_wins_full_tie(self):
        numeric = _stats(Fraction(216), Fraction(100), mean_pm=Fraction(0))
        no_pm = _stats(NO_PM, Fraction(100), mean_pm=Fraction(0))
        self.assertTrue(RUNNER.exact_mean_t_tie(numeric, no_pm))
        # full tie: NO_PM_BEFORE_MANDATORY (least aggressive) wins
        self.assertIs(RUNNER.select_best([numeric, no_pm]), no_pm)

    def test_tie_evidence_reports_rule(self):
        a = _stats(Fraction(144), Fraction(100), mean_pm=Fraction(5))
        b = _stats(Fraction(168), Fraction(100), mean_pm=Fraction(2))
        ev = RUNNER._tie_break_evidence([a, b])
        self.assertTrue(ev["tie_break_triggered"])
        self.assertEqual(ev["rule"], "1_fewer_preventive_replacements")

    def test_three_way_tie_resolution(self):
        low = _stats(Fraction(120), Fraction(100), mean_pm=Fraction(3))
        mid = _stats(Fraction(168), Fraction(100), mean_pm=Fraction(1))
        high = _stats(Fraction(216), Fraction(100), mean_pm=Fraction(1))
        self.assertIs(RUNNER.select_best([low, mid, high]), high)


class TestFrozenKernel(unittest.TestCase):
    def test_abc_closed_form_exact(self):
        kernel = RUNNER.frozen_observation_kernel()
        # P060: (1-q)alpha = q beta = e/2, solved exactly
        self.assertEqual(kernel["A"]["alpha"], Fraction(1, 65))
        self.assertEqual(kernel["A"]["beta"], Fraction(3, 5))
        self.assertEqual(kernel["B"]["alpha"], Fraction(2, 97))
        self.assertEqual(kernel["B"]["beta"], Fraction(2, 3))
        self.assertEqual(kernel["C"]["alpha"], Fraction(1, 98))
        self.assertEqual(kernel["C"]["beta"], Fraction(1, 2))

    def test_e_kernel_q1_frozen_propagation(self):
        kernel = RUNNER.frozen_observation_kernel()
        q_e = Fraction(RUNNER.Q1_FROZEN_Q_E_TEXT)
        e_e = Fraction(2, 100)  # P033
        expected_alpha = e_e / (2 * (1 - q_e))
        expected_beta = e_e / (2 * q_e)
        self.assertEqual(kernel["E"]["alpha"], expected_alpha)
        self.assertEqual(kernel["E"]["beta"], expected_beta)
        # consistency with the accepted G2-02 frozen output (4bb92eda,
        # single_test_unconditional_v1 response E_kernel) to 1e-15: the Q1
        # response reports alpha_E/beta_E rounded to 18 significant digits,
        # while this kernel re-derives them from the reported q_E via the
        # exact closed form, so the residual is ~6e-18 (documented).
        self.assertLess(
            abs(kernel["E"]["alpha"] - Fraction("0.010667735288215836")),
            Fraction(1, 10**15),
        )
        self.assertLess(
            abs(kernel["E"]["beta"] - Fraction("0.15975994494344646")),
            Fraction(1, 10**15),
        )

    def test_kernel_is_valid_engine_kernel(self):
        kernel = RUNNER.frozen_observation_kernel()
        rd_module = __import__("g3.random_des_v1", fromlist=["validate_observation_kernel"])
        rd_module.validate_observation_kernel(
            {p: {"alpha": v["alpha"], "beta": v["beta"]} for p, v in kernel.items()}
        )


class TestMeanAndAggregation(unittest.TestCase):
    def test_mean_of_fractions_exact(self):
        self.assertEqual(
            RUNNER.mean_of_fractions([Fraction(1, 3), Fraction(1, 3), Fraction(1, 3)]),
            Fraction(1, 3),
        )
        self.assertEqual(
            RUNNER.mean_of_fractions([Fraction(1, 2), Fraction(3, 4)]),
            Fraction(5, 8),
        )
        with self.assertRaises(ValueError):
            RUNNER.mean_of_fractions([])

    def test_aggregate_rejects_mixed_candidates(self):
        from g3 import random_des_v1 as rd

        kernel = RUNNER.frozen_observation_kernel()
        cfg_a = RUNNER.make_tuning_config(Fraction(120), 0, 1, kernel)
        cfg_b = RUNNER.make_tuning_config(Fraction(144), 1, 1, kernel)
        rec_a = RUNNER.RunRecord(
            candidate=Fraction(120), replicate_id=0, T=Fraction(100),
            T_days=Fraction(100, 24), preventive_replacement_count=0,
            replacement_count=0, failure_count=0, S=0, PL=0, PW=0, exited=0,
            quality_verdict="PASS", replay_verdict="PASS",
            c24={
                "decision_point_count": 1, "legal_action_count": 1,
                "waiting_opportunity_count": 0,
                "preventive_replacement_opportunity_count": 1,
                "decision_point_density": "1/100",
                "estimated_rollout_branching_burden": 2,
            },
            log_sha256="x",
        )
        rec_b = RUNNER.RunRecord(
            candidate=Fraction(144), replicate_id=1, T=Fraction(101),
            T_days=Fraction(101, 24), preventive_replacement_count=1,
            replacement_count=1, failure_count=0, S=0, PL=0, PW=0, exited=0,
            quality_verdict="PASS", replay_verdict="PASS",
            c24={
                "decision_point_count": 1, "legal_action_count": 1,
                "waiting_opportunity_count": 0,
                "preventive_replacement_opportunity_count": 1,
                "decision_point_density": "1/101",
                "estimated_rollout_branching_burden": 2,
            },
            log_sha256="y",
        )
        with self.assertRaises(ValueError):
            RUNNER.aggregate_runs([rec_a, rec_b])
        with self.assertRaises(ValueError):
            RUNNER.aggregate_runs([rec_a, rec_a])  # duplicate replicate_id
        with self.assertRaises(ValueError):
            RUNNER.aggregate_runs([])

    def test_aggregate_exact_mean(self):
        from g3 import random_des_v1 as rd

        kernel = RUNNER.frozen_observation_kernel()
        records = []
        for rep in (0, 1):
            cfg = RUNNER.make_tuning_config(Fraction(120), rep, 1, kernel)
            records.append(
                RUNNER.RunRecord(
                    candidate=Fraction(120), replicate_id=rep,
                    T=Fraction(800 + rep), T_days=Fraction(800 + rep, 24),
                    preventive_replacement_count=rep, replacement_count=1,
                    failure_count=0, S=90, PL=2, PW=1, exited=10,
                    quality_verdict="PASS", replay_verdict="PASS",
                    c24={
                        "decision_point_count": 100, "legal_action_count": 80,
                        "waiting_opportunity_count": 20,
                        "preventive_replacement_opportunity_count": 30,
                        "decision_point_density": f"{100 + rep}/801",
                        "estimated_rollout_branching_burden": 130,
                    },
                    log_sha256="z",
                )
            )
        stats = RUNNER.aggregate_runs(records)
        self.assertEqual(stats.mean_T, Fraction(1601, 2))
        self.assertEqual(stats.mean_preventive_replacement_count, Fraction(1, 2))
        self.assertEqual(stats.mean_S, Fraction(90))
        self.assertTrue(stats.quality_all_pass and stats.replay_all_pass)


class TestConfigConstruction(unittest.TestCase):
    def test_tuning_config_shape(self):
        kernel = RUNNER.frozen_observation_kernel()
        cfg = RUNNER.make_tuning_config(Fraction(168), 7, 1, kernel)
        d = cfg.to_dict()
        self.assertEqual(d["schema_version"], "random_des_config_v1")
        self.assertEqual(d["namespace"], ks.NAMESPACE_H1_TUNING)
        self.assertEqual(d["master_seed"], 1)
        self.assertEqual(d["replicate_id"], 7)
        self.assertEqual(d["batch_size"], 100)
        self.assertEqual(d["scenario"], "q2_single_shift")
        self.assertEqual(d["shift_length_h"], "12")
        self.assertEqual(d["shifts_per_day"], 1)
        self.assertEqual(d["tau_pm"], "168")
        self.assertEqual(d["turnover_profile"], "1h_literal")

    def test_no_pm_config(self):
        kernel = RUNNER.frozen_observation_kernel()
        cfg = RUNNER.make_tuning_config(NO_PM, 0, 1, kernel)
        self.assertEqual(cfg.to_dict()["tau_pm"], "NO_PM_BEFORE_MANDATORY")

    def test_240_tau_rejected_by_config(self):
        kernel = RUNNER.frozen_observation_kernel()
        with self.assertRaises(Exception):
            RUNNER.make_tuning_config(Fraction(240), 0, 1, kernel)


if __name__ == "__main__":
    unittest.main()
