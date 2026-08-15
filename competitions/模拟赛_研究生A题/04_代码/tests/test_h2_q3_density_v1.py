#!/usr/bin/env python3
"""Tests for Q3-H2-DENSITY: density analyzer, independent checker, runner
gate evaluation (Q3-H2-DENSITY package).

Covers:
  * Q3 two-shift K calendar boundaries (K=9 and K=12; off-shift; horizon);
  * latest_legal_start / BOUNDARY legal-wait semantics;
  * analyzer classification on deterministic synthetic logs (STRICT /
    BOUNDARY / NONSTRICT / PM_WITH_HEAD / PM_IDLE queue-empty /
    PM_IDLE forced-wait / exact_240 / mandatory / meaningful);
  * independent checker (h2_q3_density_checker_v1) full pass;
  * aggregate_k math (denominators, per-batch stats, zero-opportunity);
  * D-14 gate evaluation (PASS and FAIL branches A / B);
  * accepted-cell binding loads 200 hashes per Tier 1 K.

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

from checker import h2_q3_density_analyzer_v1 as dan  # noqa: E402
from checker import h2_q3_density_checker_v1 as dchk  # noqa: E402
from scripts import run_q3_h2_density_v1 as run  # noqa: E402


class TestQ3Calendar(unittest.TestCase):
    def test_shift_grid_k9(self):
        shifts = dan.q3_shift_grid(Fraction(9))
        self.assertEqual(shifts[0], (Fraction(0), Fraction(9)))
        self.assertEqual(shifts[1], (Fraction(9), Fraction(18)))
        self.assertEqual(shifts[2], (Fraction(24), Fraction(33)))
        # day d shift2 end = 24d + 2K
        self.assertEqual(shifts[1][1], Fraction(18))

    def test_shift_grid_k12(self):
        shifts = dan.q3_shift_grid(Fraction(12))
        self.assertEqual(shifts[0], (Fraction(0), Fraction(12)))
        self.assertEqual(shifts[1], (Fraction(12), Fraction(24)))
        self.assertEqual(shifts[2], (Fraction(24), Fraction(36)))
        # off-shift window [24d+2K, 24(d+1)) is between shift2 end and next
        # day shift1 start: for d=0, [24, 24) -> none; for d=1, [48,48) none.
        # K=9: off [18, 24) exists.
        shifts9 = dan.q3_shift_grid(Fraction(9))
        self.assertIsNone(dan.active_shift(shifts9, Fraction(20)))
        self.assertIsNotNone(dan.active_shift(shifts9, Fraction(17)))

    def test_active_shift_boundaries(self):
        shifts = dan.q3_shift_grid(Fraction(9))
        # t = 9 is shift2 start (half-open intervals: [9,18))
        self.assertEqual(dan.active_shift(shifts, Fraction(9)), (Fraction(9), Fraction(18)))
        # t = 18 is off-shift
        self.assertIsNone(dan.active_shift(shifts, Fraction(18)))
        # t = 24 is next day shift1
        self.assertEqual(dan.active_shift(shifts, Fraction(24)), (Fraction(24), Fraction(33)))
        # t = 0 is shift1 start
        self.assertEqual(dan.active_shift(shifts, Fraction(0)), (Fraction(0), Fraction(9)))

    def test_latest_legal_start(self):
        self.assertEqual(dan.latest_legal_start(Fraction(9), Fraction(2)), Fraction(7))
        self.assertEqual(dan.latest_legal_start(Fraction(12), Fraction(5, 2)), Fraction(19, 2))


class TestAnalyzerSynthetic(unittest.TestCase):
    """Analyzer output on the deterministic checker scenarios equals the
    independently derived expectations (re-asserted here for regression;
    full boundary coverage lives in the checker)."""

    def test_strict(self):
        log, K = dchk.case1_strict()
        s = dan.classify_batch_q3(log, K, "K12", "12", 0, batch_size=2)
        self.assertEqual(s.legal_dispatch_decision_points, 2)
        self.assertEqual(s.strategic_strict, 1)
        self.assertEqual(s.strategic_boundary, 0)
        self.assertEqual(s.strategic_nonstrict, 1)
        self.assertEqual(s.meaningful_h2_choice, 1)
        self.assertFalse(s.zero_opportunity)

    def test_boundary_is_legal_wait(self):
        log, K = dchk.case2_boundary()
        s = dan.classify_batch_q3(log, K, "K09", "9", 0, batch_size=2)
        self.assertEqual(s.strategic_boundary, 1)
        self.assertEqual(s.strategic_strict, 0)
        # BOUNDARY is a legal WAIT -> meaningful (frozen contract 早于或等于)
        self.assertEqual(s.meaningful_h2_choice, 1)

    def test_nonstrict_not_legal(self):
        log, K = dchk.case3_nonstrict_not_legal()
        s = dan.classify_batch_q3(log, K, "K09", "9", 0, batch_size=2)
        self.assertEqual(s.strategic_strict, 0)
        self.assertEqual(s.strategic_boundary, 0)
        self.assertEqual(s.strategic_nonstrict, 0)
        self.assertEqual(s.meaningful_h2_choice, 0)
        self.assertTrue(s.zero_opportunity)

    def test_exact_240_not_optional_pm(self):
        log, K = dchk.case7_exact_240()
        s = dan.classify_batch_q3(log, K, "KXX", "x", 0, batch_size=2)
        self.assertEqual(s.exact_240, 1)
        self.assertEqual(s.mandatory_replacement, 0)

    def test_mandatory_not_optional_pm(self):
        log, K = dchk.case8_mandatory()
        s = dan.classify_batch_q3(log, K, "KXX", "x", 0, batch_size=2)
        self.assertEqual(s.mandatory_replacement, 1)
        self.assertEqual(s.exact_240, 1)

    def test_pm_idle_forced_wait(self):
        log, K = dchk.case6_pm_idle_forced_wait()
        s = dan.classify_batch_q3(log, K, "KXX", "x", 0, batch_size=2)
        self.assertEqual(s.forced_wait, 1)
        self.assertEqual(s.pm_idle, 1)

    def test_pm_idle_queue_empty(self):
        log, K = dchk.case5_pm_idle_queue_empty()
        s = dan.classify_batch_q3(log, K, "KXX", "x", 0, batch_size=2)
        self.assertEqual(s.pm_idle, 1)


class TestIndependentChecker(unittest.TestCase):
    def test_checker_full_pass(self):
        failures = dchk.run_checks()
        self.assertEqual(failures, [],
                         f"independent checker must PASS; failures={failures}")

    def test_checker_resource_order(self):
        self.assertEqual(dan.RESOURCES, ("A", "B", "C", "E"))

    def test_checker_determinism(self):
        log, K = dchk.case1_strict()
        a = dan.classify_batch_q3(log, K, "K12", "12", 0, batch_size=2).to_dict()
        b = dan.classify_batch_q3(log, K, "K12", "12", 0, batch_size=2).to_dict()
        self.assertEqual(a, b)


class TestTemporalReconstruction(unittest.TestCase):
    """Q3-H2-DENSITY-E1: time-causal reconstruction regression (T1-T10)."""

    def test_t1_future_terminal_contamination(self):
        log, K = dchk.case_t1_future_terminal()
        view = dan.build_time_index(log)
        self.assertFalse(dan.terminal_at_or_before(view, 1, Fraction(10)))
        self.assertTrue(dan.terminal_at_or_before(view, 1, Fraction(20)))
        self.assertTrue(dan.future_potential_demand_at(
            view, "A", Fraction(10), batch_size=2))
        self.assertTrue(dchk.prefix_demand(log, "A", Fraction(10), 2))

    def test_t2_future_pass_contamination(self):
        log, K = dchk.case_t2_future_pass()
        view = dan.build_time_index(log)
        for p in ("A", "B", "C"):
            self.assertFalse(dan.process_passed_at_or_before(
                view, 1, p, Fraction(10)))
            self.assertTrue(dan.process_passed_at_or_before(
                view, 1, p, Fraction(25)))
        self.assertFalse(dan.head_is_legal_at(
            view, (1, "E", 1), Fraction(10), Fraction(3), Fraction(300)))
        self.assertTrue(dan.head_is_legal_at(
            view, (1, "E", 1), Fraction(25), Fraction(3), Fraction(300)))

    def test_t3_future_release_contamination(self):
        log, K = dchk.case_t3_future_release()
        view = dan.build_time_index(log)
        self.assertIsNone(dan.fcfs_head_at(view, "A", Fraction(5)))
        self.assertEqual(dan.waiting_tasks_at(view, "A", Fraction(5)), [])
        self.assertEqual(dan.fcfs_head_at(view, "A", Fraction(10)), (1, "A", 1))

    def test_t4_delayed_start_stale_waiting(self):
        log, K = dchk.case_t4_delayed_start()
        view = dan.build_time_index(log)
        self.assertEqual(dan.fcfs_head_at(view, "A", Fraction(1)), (1, "A", 1))
        self.assertIsNone(dan.fcfs_head_at(view, "A", Fraction(6)))
        self.assertTrue(dchk.prefix_head_waiting(log, "A", Fraction(1)))
        self.assertFalse(dchk.prefix_head_waiting(log, "A", Fraction(6)))

    def test_t5_completed_full_log_pm_idle(self):
        # OLD bug: final DEVICE_TERMINAL records suppressed pm_idle to 0;
        # time-causal: at t=120 future demand TRUE -> pm_idle = 1.
        log, K = dchk.case_t5_completed_full_log_pm_idle()
        s = dan.classify_batch_q3(log, K, "KXX", "x", 0, batch_size=2)
        self.assertEqual(s.pm_idle, 1)
        self.assertEqual(s.queue_empty_pm_idle, 1)
        self.assertEqual(s.meaningful_h2_choice, 0)
        self.assertTrue(s.zero_dispatch_opportunity)
        self.assertFalse(s.zero_full_action_space_opportunity)
        self.assertEqual(dchk.prefix_maintenance_count(log, K, 2), 1)

    def test_t6_forced_wait_eventual_terminal(self):
        log, K = dchk.case_t6_forced_wait_eventual_terminal()
        s = dan.classify_batch_q3(log, K, "KXX", "x", 0, batch_size=2)
        self.assertEqual(s.forced_wait, 1)
        self.assertEqual(s.pm_idle, 0)
        self.assertTrue(dchk.prefix_head_waiting(log, "B", Fraction(17, 2)))

    def test_t7_release_closure_on_idle_resource(self):
        log, K = dchk.case_t7_release_closure()
        view = dan.build_time_index(log)
        self.assertIn(Fraction(17, 2),
                      dan.closure_times(view, dan.q3_shift_grid(K)))
        s = dan.classify_batch_q3(log, K, "KXX", "x", 0, batch_size=2)
        self.assertEqual(s.forced_wait, 1)

    def test_t8_mandatory_pre_start_replacement(self):
        log, K = dchk.case_t8_mandatory_pre_start()
        s = dan.classify_batch_q3(log, K, "KXX", "x", 0, batch_size=2)
        self.assertEqual(s.mandatory_replacement, 1)
        self.assertEqual(s.mandatory_a_plus_d_gt_240, 1)
        self.assertEqual(s.pm_idle, 0)

    def test_t9_exact_240(self):
        log, K = dchk.case_t9_exact_240()
        s = dan.classify_batch_q3(log, K, "KXX", "x", 0, batch_size=2)
        self.assertEqual(s.exact_240, 1)
        self.assertEqual(s.mandatory_replacement, 0)

    def test_t10_same_closure_single_point(self):
        log, K = dchk.case_t10_same_closure_single_point()
        s = dan.classify_batch_q3(log, K, "KXX", "x", 0, batch_size=2)
        self.assertEqual(s.pm_idle, 1)
        self.assertEqual(s.queue_empty_pm_idle, 1)
        self.assertEqual(dchk.prefix_maintenance_count(log, K, 2), 1)


class TestAggregate(unittest.TestCase):
    def _mk(self, legal, meaningful, strict, zero=False):
        return dan.DensityBatchStats(
            k_label="K09", k_hours="9", batch_index=0,
            legal_dispatch_decision_points=legal,
            meaningful_h2_choice=meaningful,
            strategic_strict=strict,
            zero_opportunity=zero,
        )

    def test_aggregate_denominator(self):
        batches = [self._mk(100, 50, 4), self._mk(100, 30, 2)]
        agg = dan.aggregate_k("K09", "9", batches)
        d = agg.to_dict()
        self.assertEqual(d["total_counts"]["legal_dispatch_decision_point_count"], 200)
        self.assertEqual(d["total_counts"]["meaningful_h2_choice_point_count"], 80)
        self.assertAlmostEqual(d["meaningful_choice_fraction"], 0.4)
        self.assertEqual(d["total_counts"]["strategic_wait_strict_count"], 6)
        self.assertAlmostEqual(
            d["per_batch"]["strategic_wait_strict_count"]["mean"], 3.0)

    def test_aggregate_zero_opportunity(self):
        batches = [self._mk(50, 0, 0, zero=True), self._mk(50, 0, 0, zero=True)]
        agg = dan.aggregate_k("K09", "9", batches)
        d = agg.to_dict()
        self.assertEqual(d["total_counts"]["zero_opportunity_batches"], 2)
        self.assertAlmostEqual(d["zero_opportunity_batch_fraction"], 1.0)
        self.assertEqual(d["meaningful_choice_fraction"], 0.0)


class TestGateEvaluation(unittest.TestCase):
    def _mk_batch(self, legal, meaningful, strict):
        return dan.DensityBatchStats(
            k_label="K09", k_hours="9", batch_index=0,
            legal_dispatch_decision_points=legal,
            meaningful_h2_choice=meaningful,
            strategic_strict=strict,
            zero_opportunity=meaningful == 0,
        )

    def _per_k_all(self, legal, meaningful, strict):
        return {k: [self._mk_batch(legal, meaningful, strict) for _ in range(3)]
                for k, _ in run.K_VALUES}

    def test_gate_pass(self):
        per_k = self._per_k_all(100, 50, 5)  # fraction 0.5, strict 5/batch
        gate, _ = run.evaluate_gate(per_k)
        self.assertTrue(gate["condition_A"]["pass"])
        self.assertTrue(gate["condition_B"]["pass"])
        self.assertEqual(gate["overall"], "PASS")

    def test_gate_fail_condition_a(self):
        per_k = self._per_k_all(100, 50, 5)
        per_k["K09"] = [self._mk_batch(100, 10, 5) for _ in range(3)]  # frac 0.1
        gate, _ = run.evaluate_gate(per_k)
        self.assertFalse(gate["condition_A"]["pass"])
        self.assertEqual(gate["condition_A"]["pass_count"], 6)
        self.assertTrue(gate["condition_B"]["pass"])
        self.assertEqual(gate["overall"], "FAIL")

    def test_gate_fail_condition_b(self):
        per_k = self._per_k_all(100, 50, 1)  # strict 1/batch everywhere
        gate, _ = run.evaluate_gate(per_k)
        self.assertTrue(gate["condition_A"]["pass"])
        self.assertFalse(gate["condition_B"]["pass"])
        self.assertEqual(gate["condition_B"]["pass_count"], 0)
        self.assertEqual(gate["overall"], "FAIL")

    def test_gate_boundary_not_merged(self):
        # A K with strict=0 but boundary>0 must NOT pass condition B
        # (frozen: BOUNDARY legal WAIT is reported separately, never merged).
        per_k = self._per_k_all(100, 50, 0)
        for k in per_k:
            for b in per_k[k]:
                b.strategic_boundary = 9
        gate, _ = run.evaluate_gate(per_k)
        self.assertFalse(gate["condition_B"]["pass"])
        self.assertEqual(gate["overall"], "FAIL")


class TestAcceptedBinding(unittest.TestCase):
    def test_accepted_cells_200_per_k(self):
        accepted = run.load_accepted_cells()
        self.assertEqual(len(accepted), 7)
        for k, by_rep in accepted.items():
            self.assertEqual(len(by_rep), 200)
            self.assertEqual(set(by_rep), set(range(200)))
            for info in by_rep.values():
                sha = info["canonical_log_sha256"]
                self.assertEqual(len(sha), 64)
                int(sha, 16)  # hex


if __name__ == "__main__":
    unittest.main(verbosity=2)
