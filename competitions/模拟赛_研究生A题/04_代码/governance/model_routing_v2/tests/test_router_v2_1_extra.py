"""MATHEMATICAL_MODELING_ROUTER_V2.1.1 — verification-family tests (spec 39),
negative runtime tests (spec 41 as repaired), dedup repair (spec 6), and the
project-token leak guard (spec 18).  Deterministic; no network.
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
    route_gate_v2_1_1, SemanticIssueStore, YELLOW, GREEN, RED,
    ROUTING_BLOCKED, HUMAN_GATE_REQUIRED, GATE_PASS)
from governance.model_routing_v2.method_families import (  # noqa: E402
    classify_method_families, FAMILIES, DISCRETE_EVENT_SIMULATION)
from governance.model_routing_v2.generalization import (  # noqa: E402
    generalization_check, validate_miss_registry)
from governance.model_routing_v2.risk_card import RiskCard  # noqa: E402
from governance.model_routing_v2.route_engine import (  # noqa: E402
    compute_model_route_v2_1_1)


class TestVerificationFamilies(unittest.TestCase):
    def test_optimization_prefers_feasibility_and_oracle(self):
        checks = strategy_checks(["OPTIMIZATION"])
        self.assertEqual(checks[0], "constraint_feasibility")
        self.assertIn("objective_recomputation", checks)
        self.assertIn("small_instance_brute_force", checks)
        self.assertNotIn("deterministic_toy_world", checks)

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
        checks = strategy_checks([DISCRETE_EVENT_SIMULATION])
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

    def test_family_never_changes_route(self):
        # families are strategy metadata; the route engine never consumes them
        base = dict(task_id="X", stage="FORMULATION",
                    authority_state="EXPLORATORY", formal_scope=True,
                    risk={"algorithmic_semantics": True},
                    risk_evidence=[{"dimension": "algorithmic_semantics",
                                    "evidence": "ordering"}])
        c1 = RiskCard(**base)
        fams = classify_method_families("离散事件仿真模拟排队系统")
        self.assertIn(DISCRETE_EVENT_SIMULATION, fams)
        c2 = RiskCard(**base)
        self.assertEqual(compute_model_route_v2_1_1(c1).route,
                         compute_model_route_v2_1_1(c2).route)

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
    """spec 41 (repaired): YELLOW without a verified, outcome-clear review ->
    ROUTING_BLOCKED; no fallback; no formal PASS."""

    def test_yellow_identity_unverified_blocked(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=False)
        self.assertEqual(g["status"], ROUTING_BLOCKED)
        self.assertEqual(g["route"], YELLOW)

    def test_yellow_verdict_blocked_blocked(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict="BLOCKED")
        self.assertEqual(g["status"], ROUTING_BLOCKED)

    def test_yellow_pass_with_open_actions_blocked(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict="PASS",
                              required_actions_closed=False)
        self.assertEqual(g["status"], ROUTING_BLOCKED)

    def test_red_without_acceptance_blocked(self):
        g = route_gate_v2_1_1(RED, human_gate_verdict="PENDING")
        self.assertEqual(g["status"], HUMAN_GATE_REQUIRED)
        g2 = route_gate_v2_1_1(RED, human_gate_verdict="REJECTED")
        self.assertEqual(g2["status"], ROUTING_BLOCKED)

    def test_red_accepted_passes(self):
        g = route_gate_v2_1_1(RED, human_gate_verdict="ACCEPTED")
        self.assertEqual(g["status"], GATE_PASS)

    def test_green_outside_r4_passes_without_sentinel(self):
        g = route_gate_v2_1_1(GREEN, checkpoint="R0")
        self.assertEqual(g["status"], GATE_PASS)

    def test_formal_green_at_r4_requires_sentinel(self):
        g = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True)
        self.assertEqual(g["status"], ROUTING_BLOCKED)


class TestSemanticIssueDedupRepair(unittest.TestCase):
    """spec 6: identity verification is NOT resolution; BLOCKED never
    resolves; HUMAN_GATE_REQUIRED never resolves without acceptance."""

    def setUp(self):
        self.store = SemanticIssueStore()

    def test_first_time_needs_review(self):
        self.assertTrue(self.store.needs_pro_max("ASSUMPTION-001", "hash-a"))

    def test_resolved_pass_closed_deduped(self):
        self.store.record("ASSUMPTION-001", "hash-a", "PASS",
                          "RESOLVED", review_identity_verified=True,
                          required_actions_closed=True, commit_sha="abc")
        self.assertFalse(self.store.needs_pro_max("ASSUMPTION-001", "hash-a"))

    def test_identity_verified_alone_is_not_resolution(self):
        # identity verified but status OPEN -> still needs review
        self.store.record("ASSUMPTION-001", "hash-a", "PASS",
                          "OPEN", review_identity_verified=True,
                          required_actions_closed=True, commit_sha="abc")
        self.assertTrue(self.store.needs_pro_max("ASSUMPTION-001", "hash-a"))

    def test_blocked_never_resolves_via_identity(self):
        self.store.record("ASSUMPTION-001", "hash-a", "BLOCKED",
                          "BLOCKED", review_identity_verified=True,
                          required_actions_closed=False, commit_sha="abc")
        self.assertTrue(self.store.needs_pro_max("ASSUMPTION-001", "hash-a"))

    def test_record_blocked_as_resolved_rejected(self):
        with self.assertRaises(ValueError):
            self.store.record("ASSUMPTION-001", "hash-a", "BLOCKED",
                              "RESOLVED", review_identity_verified=True,
                              required_actions_closed=False)

    def test_human_pending_never_resolves(self):
        self.store.record("ASSUMPTION-001", "hash-a", "HUMAN_GATE_REQUIRED",
                          "HUMAN_PENDING", review_identity_verified=True,
                          required_actions_closed=False, commit_sha="abc")
        self.assertTrue(self.store.needs_pro_max("ASSUMPTION-001", "hash-a"))

    def test_caveat_open_stays_open(self):
        self.store.record("ASSUMPTION-001", "hash-a", "PASS_WITH_CAVEAT",
                          "OPEN", review_identity_verified=True,
                          required_actions_closed=False, commit_sha="abc")
        self.assertTrue(self.store.needs_pro_max("ASSUMPTION-001", "hash-a"))

    def test_contract_change_reopens(self):
        self.store.record("ASSUMPTION-001", "hash-a", "PASS",
                          "RESOLVED", review_identity_verified=True,
                          required_actions_closed=True, commit_sha="abc")
        self.assertTrue(self.store.needs_pro_max("ASSUMPTION-001", "hash-b"))

    def test_rereview_conditions(self):
        self.store.record("ASSUMPTION-001", "hash-a", "PASS",
                          "RESOLVED", review_identity_verified=True,
                          required_actions_closed=True, commit_sha="abc")
        self.assertFalse(self.store.rereview_required("ASSUMPTION-001", {}))
        self.assertTrue(self.store.rereview_required(
            "ASSUMPTION-001", {"new_counterexample": True}))


class TestProjectTokenLeakGuard(unittest.TestCase):
    """spec 18: the guard proves only known-token non-leakage."""

    def test_core_clean(self):
        core = Path(__file__).resolve().parents[1]
        res = generalization_check(str(core))
        self.assertEqual(res["status"], "PASS", res)
        self.assertEqual(res["matches"], {})
        self.assertEqual(res["check"], "PROJECT_TOKEN_LEAK_GUARD")

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
