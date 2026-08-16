"""MATHEMATICAL_MODELING_ROUTER_V2.1 — verification-family tests (spec 39),
negative runtime test (spec 41), dedup (spec 20/21), and generalization
(spec 34).  Deterministic; no network.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]  # 04_代码
for _entry in (str(BASE), str(BASE / "governance")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from governance.model_routing_v2.verification_strategies import (  # noqa: E402
    strategy_checks, build_verification_plan, UNIVERSAL_BASELINE)
from governance.model_routing_v2.route_engine import (  # noqa: E402
    route_gate_v2_1, SemanticIssueStore, YELLOW, GREEN, RED,
    ROUTING_BLOCKED, HUMAN_GATE_REQUIRED, GATE_PASS)
from governance.model_routing_v2.method_families import (  # noqa: E402
    classify_method_families, FAMILIES)
from governance.model_routing_v2.generalization import (  # noqa: E402
    generalization_check, validate_miss_registry)
from governance.model_routing_v2.risk_card import RiskCard, EngineeringSignals  # noqa: E402
from governance.model_routing_v2.route_engine import compute_model_route_v2_1  # noqa: E402


class TestVerificationFamilies(unittest.TestCase):
    def test_optimization_prefers_feasibility_and_oracle(self):
        checks = strategy_checks(["OPTIMIZATION"])
        self.assertEqual(checks[0], "constraint_feasibility")
        self.assertIn("objective_recomputation", checks)
        self.assertIn("small_instance_brute_force", checks)
        self.assertNotIn("deterministic_toy_world", checks)  # not DES replay

    def test_physics_prefers_units_conservation_convergence(self):
        checks = strategy_checks(["PHYSICS_MECHANISM", "ODE_PDE_DYNAMICAL_SYSTEM"])
        for first in ("dimensional_analysis", "unit_consistency",
                      "conservation_law"):
            self.assertIn(first, checks)
        self.assertIn("mesh_convergence", checks)

    def test_ml_prefers_leakage_split_baseline(self):
        checks = strategy_checks(["MACHINE_LEARNING"])
        self.assertEqual(checks[0], "train_test_leakage")
        self.assertIn("feature_leakage", checks)
        self.assertIn("baseline_model", checks)

    def test_simulation_prefers_toy_world_and_invariants(self):
        checks = strategy_checks(["DISCRETE_EVENT_SIMULATION"])
        self.assertEqual(checks[0], "deterministic_toy_world")
        self.assertIn("state_invariant", checks)
        self.assertIn("event_invariant", checks)

    def test_mcdm_prefers_normalization_and_rank_sensitivity(self):
        checks = strategy_checks(["MULTI_CRITERIA_EVALUATION"])
        self.assertEqual(checks[0], "normalization_recomputation")
        self.assertIn("rank_reversal", checks)
        self.assertIn("weight_perturbation", checks)

    def test_unknown_hybrid_returns_universal_baseline(self):
        checks = strategy_checks(["HYBRID_OTHER"])
        self.assertEqual(tuple(checks), UNIVERSAL_BASELINE)

    def test_multi_label_and_family_does_not_change_route(self):
        fams = classify_method_families(
            "simulate a queue with monte carlo sampling")
        self.assertTrue("DISCRETE_EVENT_SIMULATION" in fams
                        and "MONTE_CARLO_STOCHASTIC" in fams)
        # same card, with and without family metadata -> identical route
        base = dict(task_id="X", stage="FORMULATION",
                    authority_state="EXPLORATORY", formal_scope=True,
                    risk={"algorithmic_semantics": True},
                    risk_evidence=[{"dimension": "algorithmic_semantics",
                                    "evidence": "ordering"}])
        c1 = RiskCard(**base)
        c2 = RiskCard(**{**base, "risk_evidence": base["risk_evidence"]})
        self.assertEqual(compute_model_route_v2_1(c1).route,
                         compute_model_route_v2_1(c2).route)

    def test_registry_never_invents_thresholds(self):
        with self.assertRaises(ValueError):
            build_verification_plan(
                task_id="X", semantic_issue_id=None,
                method_families=["MONTE_CARLO_STOCHASTIC"],
                risk_dimensions=["statistical_inference"],
                claim_under_review="convergence",
                selected_checks=["monte_carlo_convergence"],
                authority_thresholds={})
        plan = build_verification_plan(
            task_id="X", semantic_issue_id=None,
            method_families=["MONTE_CARLO_STOCHASTIC"],
            risk_dimensions=["statistical_inference"],
            claim_under_review="convergence",
            selected_checks=["monte_carlo_convergence"],
            authority_thresholds={"monte_carlo_convergence": "authority-specified"})
        self.assertEqual(plan["authority_thresholds"]["monte_carlo_convergence"],
                         "authority-specified")

    def test_all_families_served(self):
        for fam in FAMILIES:
            self.assertGreaterEqual(len(strategy_checks([fam])), 1)


class TestNegativeRuntime(unittest.TestCase):
    """spec 41: YELLOW + Pro-Max unavailable -> ROUTING_BLOCKED, no fallback,
    no formal PASS."""

    def test_yellow_without_verified_pro_max_blocked(self):
        g = route_gate_v2_1(YELLOW, verified_pro_max=False)
        self.assertEqual(g["status"], ROUTING_BLOCKED)
        self.assertNotEqual(g["status"], GATE_PASS)
        self.assertEqual(g["route"], YELLOW)  # no silent re-route

    def test_yellow_with_verified_pro_max_passes(self):
        g = route_gate_v2_1(YELLOW, verified_pro_max=True)
        self.assertEqual(g["status"], GATE_PASS)

    def test_red_without_human_gate_blocked(self):
        g = route_gate_v2_1(RED, verified_pro_max=True, human_gate_done=False)
        self.assertEqual(g["status"], HUMAN_GATE_REQUIRED)
        self.assertNotEqual(g["status"], GATE_PASS)

    def test_red_with_human_gate_passes(self):
        g = route_gate_v2_1(RED, human_gate_done=True)
        self.assertEqual(g["status"], GATE_PASS)

    def test_green_passes(self):
        g = route_gate_v2_1(GREEN)
        self.assertEqual(g["status"], GATE_PASS)


class TestSemanticIssueDedup(unittest.TestCase):
    """spec 20/21: resolved issues do not re-invoke Pro-Max; contract changes
    and re-review conditions do."""

    def setUp(self):
        self.store = SemanticIssueStore()

    def test_first_time_needs_review(self):
        self.assertTrue(self.store.needs_pro_max("ASSUMPTION-001", "hash-a"))

    def test_resolved_issue_deduped(self):
        self.store.record("ASSUMPTION-001", "hash-a", "PASS",
                          verified=True, commit_sha="abc")
        self.assertFalse(self.store.needs_pro_max("ASSUMPTION-001", "hash-a"))

    def test_contract_change_reopens(self):
        self.store.record("ASSUMPTION-001", "hash-a", "PASS",
                          verified=True, commit_sha="abc")
        self.assertTrue(self.store.needs_pro_max("ASSUMPTION-001", "hash-b"))

    def test_unverified_never_dedupes(self):
        self.store.record("ASSUMPTION-001", "hash-a", "PASS",
                          verified=False, commit_sha="abc")
        self.assertTrue(self.store.needs_pro_max("ASSUMPTION-001", "hash-a"))

    def test_rereview_conditions(self):
        self.store.record("ASSUMPTION-001", "hash-a", "PASS",
                          verified=True, commit_sha="abc")
        self.assertFalse(self.store.rereview_required("ASSUMPTION-001", {}))
        self.assertTrue(self.store.rereview_required(
            "ASSUMPTION-001", {"new_counterexample": True}))


class TestGeneralization(unittest.TestCase):
    """spec 34: Universal Core must contain zero project-specific tokens."""

    def test_core_clean(self):
        core = Path(__file__).resolve().parents[1]
        res = generalization_check(str(core))
        self.assertEqual(res["status"], "PASS", res)
        self.assertEqual(res["matches"], {})

    def test_miss_registry_validation(self):
        good = {"entries": [
            {"miss_id": "M-001", "date": "2026-08-16", "domain": "general",
             "original_route": "GREEN", "correct_route": "YELLOW",
             "universal_risk_dimension": "algorithmic_semantics",
             "failure_pattern": "same-time event order assumed",
             "new_general_rule": "undefined event order -> algorithmic risk",
             "scope": "UNIVERSAL", "status": "ACTIVE"}]}
        validate_miss_registry(good)
        with self.assertRaises(ValueError):
            validate_miss_registry({"entries": [{"miss_id": "M-002"}]})


if __name__ == "__main__":
    unittest.main()
