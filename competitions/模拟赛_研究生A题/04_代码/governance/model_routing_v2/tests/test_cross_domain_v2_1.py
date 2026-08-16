"""MATHEMATICAL_MODELING_ROUTER_V2.1.1 — synthetic cross-domain tests (spec 38
as repaired: T01..T26 preserved + §17 bilingual tests + §11 sentinel-gate
negatives + §12/13/14 fail-closed card tests).

Deterministic unit tests — no network, no Pro-Max calls.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]  # 04_代码
for _entry in (str(BASE), str(BASE / "governance")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from governance.model_routing_v2.risk_card import (  # noqa: E402
    RiskCard, EngineeringSignals, RiskCardInvalid)
from governance.model_routing_v2.route_engine import (  # noqa: E402
    compute_model_route_v2_1_1, route_gate_v2_1_1, GREEN, YELLOW, RED,
    ROUTING_BLOCKED, HUMAN_GATE_REQUIRED, GATE_PASS)
from governance.model_routing_v2.method_families import (  # noqa: E402
    classify_method_families, HYBRID_OTHER, DISCRETE_EVENT_SIMULATION)
from governance.model_routing_v2.sentinel import (  # noqa: E402
    parse_sentinel_verdict, sentinel_upgrade)
from governance.model_routing_v2.extensions import (  # noqa: E402
    validate_extension, ExtensionRejected)

FROZEN_REF = "authority: frozen solver specification v1"


def card(**kw) -> RiskCard:
    defaults = dict(task_id="T", stage="FORMULATION",
                    authority_state="EXPLORATORY", formal_scope=True)
    defaults.update(kw)
    return RiskCard(**defaults)


def green_card(cls="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
               refs=(FROZEN_REF,), **kw):
    return card(green_allowlist_class=cls, frozen_mechanical_execution=True,
                authority_state="FROZEN", authority_refs=list(refs), **kw)


class TestCrossDomainRouting(unittest.TestCase):
    # ---- optimization ---------------------------------------------------
    def test_t01_run_frozen_milp_green(self):
        self.assertEqual(compute_model_route_v2_1_1(green_card()).route, GREEN)

    def test_t02_choose_average_vs_max_wait_objective_yellow(self):
        c = card(risk={"mathematical_formulation": True},
                 risk_evidence=[{"dimension": "mathematical_formulation",
                                 "evidence": "objective choice not frozen"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    # ---- physics / numerics ---------------------------------------------
    def test_t03_run_frozen_rk4_green(self):
        self.assertEqual(compute_model_route_v2_1_1(green_card()).route, GREEN)

    def test_t04_air_resistance_negligible_decision_yellow(self):
        c = card(risk={"modeling_assumption": True},
                 risk_evidence=[{"dimension": "modeling_assumption",
                                 "evidence": "negligibility is a modeling choice"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    def test_t05_step_size_changes_conclusion_yellow(self):
        c = card(risk={"numerical_method": True},
                 risk_evidence=[{"dimension": "numerical_method",
                                 "evidence": "step size choice changes the conclusion"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    # ---- statistics -----------------------------------------------------
    def test_t06_run_frozen_bootstrap_green(self):
        self.assertEqual(compute_model_route_v2_1_1(green_card()).route, GREEN)

    def test_t07_bootstrap_row_vs_subject_yellow(self):
        c = card(risk={"statistical_inference": True},
                 risk_evidence=[{"dimension": "statistical_inference",
                                 "evidence": "sampling unit choice is not frozen"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    # ---- ML / prediction ------------------------------------------------
    def test_t08_train_frozen_ml_config_green(self):
        self.assertEqual(compute_model_route_v2_1_1(green_card()).route, GREEN)

    def test_t09_random_split_vs_temporal_split_yellow(self):
        c = card(risk={"statistical_inference": True},
                 risk_evidence=[{"dimension": "statistical_inference",
                                 "evidence": "split semantics undefined"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    def test_t10_choose_rolling_origin_cv_yellow(self):
        c = card(risk={"statistical_inference": True},
                 risk_evidence=[{"dimension": "statistical_inference",
                                 "evidence": "CV scheme is a statistical choice"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    # ---- multi-criteria -------------------------------------------------
    def test_t11_run_frozen_topsis_green(self):
        c = green_card(cls="MECHANICAL_FORMULA_IMPLEMENTATION_UNDER_FROZEN_EXACT_FORMULA")
        self.assertEqual(compute_model_route_v2_1_1(c).route, GREEN)

    def test_t12_minmax_vs_zscore_changes_ranking_yellow(self):
        c = card(risk={"data_semantics": True, "formal_result_impact": True},
                 risk_evidence=[{"dimension": "data_semantics",
                                 "evidence": "normalization choice not frozen"},
                                {"dimension": "formal_result_impact",
                                 "evidence": "ranking changes under the two schemes"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    # ---- graph / network ------------------------------------------------
    def test_t13_run_shortest_path_frozen_graph_green(self):
        self.assertEqual(compute_model_route_v2_1_1(green_card()).route, GREEN)

    def test_t14_edge_weight_distance_or_time_yellow(self):
        c = card(risk={"problem_semantics": True},
                 risk_evidence=[{"dimension": "problem_semantics",
                                 "evidence": "edge weight meaning is ambiguous"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    # ---- simulation -----------------------------------------------------
    def test_t15_run_frozen_simulation_green(self):
        self.assertEqual(compute_model_route_v2_1_1(green_card()).route, GREEN)

    def test_t16_simultaneous_event_ordering_unclear_yellow(self):
        c = card(risk={"algorithmic_semantics": True},
                 risk_evidence=[{"dimension": "algorithmic_semantics",
                                 "evidence": "same-time event order undefined"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    # ---- authority states (spec 6/16) -----------------------------------
    def test_t17_exploratory_linear_to_nonlinear_yellow_not_red(self):
        c = card(risk={"modeling_assumption": True},
                 authority_state="EXPLORATORY",
                 risk_evidence=[{"dimension": "modeling_assumption",
                                 "evidence": "model family choice in exploration"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    def test_t18_frozen_change_accepted_objective_red(self):
        c = card(risk={"mathematical_formulation": True,
                       "governance_authority": True},
                 authority_state="FROZEN",
                 risk_evidence=[{"dimension": "mathematical_formulation",
                                 "evidence": "objective mutation requested"},
                                {"dimension": "governance_authority",
                                 "evidence": "frozen authority mutation"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, RED)

    def test_t19_human_accepted_change_significance_threshold_red(self):
        c = card(risk={"statistical_inference": True,
                       "governance_authority": True},
                 authority_state="HUMAN_ACCEPTED",
                 risk_evidence=[{"dimension": "statistical_inference",
                                 "evidence": "threshold change after result"},
                                {"dimension": "governance_authority",
                                 "evidence": "accepted authority mutation"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, RED)

    # ---- dynamic reclassification (spec 15) ------------------------------
    def test_t20_path_typo_green_then_units_discovered_yellow(self):
        c0 = card(task_id="T20", checkpoint="R0",
                  green_allowlist_class="TYPO_FIX",
                  frozen_mechanical_execution=True)
        self.assertEqual(compute_model_route_v2_1_1(c0).route, GREEN)
        c1 = card(task_id="T20", checkpoint="R1",
                  risk={"data_semantics": True},
                  risk_evidence=[{"dimension": "data_semantics",
                                  "evidence": "fields carry different statistical units"}])
        self.assertEqual(compute_model_route_v2_1_1(c1).route, YELLOW)

    # ---- scale independence ----------------------------------------------
    def test_t21_500_line_mechanical_implementation_green(self):
        c = green_card(cls="MECHANICAL_FORMULA_IMPLEMENTATION_UNDER_FROZEN_EXACT_FORMULA")
        self.assertEqual(compute_model_route_v2_1_1(c).route, GREEN)

    def test_t22_one_line_state_transition_semantic_change_yellow(self):
        c = card(risk={"algorithmic_semantics": True},
                 risk_evidence=[{"dimension": "algorithmic_semantics",
                                 "evidence": "state-transition semantics change"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    # ---- unknown hybrid ---------------------------------------------------
    def test_t23_unknown_hybrid_two_models_yellow(self):
        fams = classify_method_families("hybrid custom approach with no known family")
        self.assertEqual(fams, [HYBRID_OTHER])
        c = card(risk={"modeling_assumption": True},
                 multiple_plausible_interpretations=True,
                 risk_evidence=[{"dimension": "modeling_assumption",
                                 "evidence": "two plausible models"}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    # ---- sentinel ---------------------------------------------------------
    def test_t24_sentinel_finds_missed_assumption_upgrade_yellow(self):
        c = green_card(cls="RUN_EXISTING_CHECKER")
        self.assertEqual(compute_model_route_v2_1_1(c).route, GREEN)
        result = parse_sentinel_verdict(
            "SENTINEL_VERDICT: RISK_OMISSION\n"
            "missing_risk_dimensions: [modeling_assumption]\n"
            "reason: assumption unstated")
        up = sentinel_upgrade(GREEN, result)
        self.assertTrue(up["upgraded"])
        self.assertEqual(up["route"], YELLOW)

    def test_t25_sentinel_agrees_mechanical_frozen_green(self):
        c = green_card()
        self.assertEqual(compute_model_route_v2_1_1(c).route, GREEN)
        result = parse_sentinel_verdict("SENTINEL_VERDICT: AGREE_GREEN")
        up = sentinel_upgrade(GREEN, result)
        self.assertFalse(up["upgraded"])
        self.assertEqual(up["route"], GREEN)

    # ---- extension non-deescalation ---------------------------------------
    def test_t26_extension_yellow_to_green_rejected(self):
        with self.assertRaises(ExtensionRejected):
            validate_extension({
                "extension_version": "1.0", "project_id": "p",
                "term_risks": {"some_term": {"risks": [], "route_cap": "GREEN"}}})
        with self.assertRaises(ExtensionRejected):
            validate_extension({
                "extension_version": "1.0", "project_id": "p",
                "term_risks": {"some_term": {"risks": ["not_a_dimension"]}}})


class TestChineseBilingualClassification(unittest.TestCase):
    """§17: Chinese / bilingual method-family recognition."""

    def test_monte_carlo_chinese(self):
        fams = classify_method_families("采用蒙特卡洛方法估计失效概率")
        self.assertIn("MONTE_CARLO_STOCHASTIC", fams)
        self.assertIn("PROBABILITY_STATISTICS", fams)

    def test_integer_programming_chinese(self):
        fams = classify_method_families("建立整数规划模型求最优调度方案")
        self.assertIn("OPTIMIZATION", fams)
        self.assertIn("OPERATIONS_RESEARCH", fams)

    def test_ode_physics_chinese(self):
        fams = classify_method_families("建立微分方程描述运动过程")
        self.assertIn("ODE_PDE_DYNAMICAL_SYSTEM", fams)
        self.assertIn("PHYSICS_MECHANISM", fams)

    def test_mcdm_chinese(self):
        fams = classify_method_families("使用TOPSIS和熵权法进行综合评价")
        self.assertIn("MULTI_CRITERIA_EVALUATION", fams)

    def test_des_chinese(self):
        fams = classify_method_families("建立离散事件仿真模拟排队系统")
        self.assertIn(DISCRETE_EVENT_SIMULATION, fams)
        self.assertIn("OPERATIONS_RESEARCH", fams)

    def test_ml_chinese(self):
        fams = classify_method_families("用随机森林和交叉验证做预测")
        self.assertIn("MACHINE_LEARNING", fams)
        self.assertIn("REGRESSION_PREDICTION", fams)

    def test_time_series_chinese(self):
        fams = classify_method_families("时间序列的趋势与季节性分析")
        self.assertIn("TIME_SERIES", fams)

    def test_graph_chinese(self):
        fams = classify_method_families("图论中的最短路与最小生成树")
        self.assertIn("GRAPH_NETWORK", fams)

    def test_spatial_chinese(self):
        fams = classify_method_families("基于GIS空间坐标的距离分析")
        self.assertIn("SPATIAL_GIS", fams)

    def test_numerical_chinese(self):
        fams = classify_method_families("有限差分法数值计算步长收敛性")
        self.assertIn("NUMERICAL_COMPUTATION", fams)

    def test_analytical_chinese(self):
        fams = classify_method_families("解析解与数学推导")
        self.assertIn("ANALYTICAL_MATH", fams)

    def test_statistics_chinese(self):
        fams = classify_method_families("概率统计中的假设检验与置信区间")
        self.assertIn("PROBABILITY_STATISTICS", fams)


class TestDesRefinement(unittest.TestCase):
    """§16: generic simulation alone must NOT imply DES."""

    def test_generic_simulation_not_des(self):
        fams = classify_method_families("simulation of the whole system")
        self.assertNotIn(DISCRETE_EVENT_SIMULATION, fams)

    def test_generic_simulation_chinese_not_des(self):
        fams = classify_method_families("对系统整体进行仿真")
        self.assertNotIn(DISCRETE_EVENT_SIMULATION, fams)

    def test_discrete_event_evidence_yields_des(self):
        fams = classify_method_families("discrete-event simulation with event queue")
        self.assertIn(DISCRETE_EVENT_SIMULATION, fams)

    def test_monte_carlo_simulation_not_des(self):
        fams = classify_method_families("monte carlo simulation of random sampling")
        self.assertNotIn(DISCRETE_EVENT_SIMULATION, fams)
        self.assertIn("MONTE_CARLO_STOCHASTIC", fams)


class TestSentinelGateNegatives(unittest.TestCase):
    """§11: deterministic Sentinel gate tests."""

    def test_formal_green_without_sentinel_blocked(self):
        g = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True)
        self.assertEqual(g["status"], ROUTING_BLOCKED)

    def test_formal_green_sentinel_not_identity_verified_blocked(self):
        g = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True,
                              sentinel_identity_verified=False,
                              sentinel_verdict="AGREE_GREEN")
        self.assertEqual(g["status"], ROUTING_BLOCKED)

    def test_formal_green_malformed_sentinel_blocked(self):
        g = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True,
                              sentinel_identity_verified=True,
                              sentinel_verdict=None)
        self.assertEqual(g["status"], ROUTING_BLOCKED)

    def test_green_sentinel_agree_yellow_upgrades_yellow(self):
        g = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True,
                              sentinel_identity_verified=True,
                              sentinel_verdict="AGREE_YELLOW")
        self.assertEqual(g["status"], ROUTING_BLOCKED)  # cannot pass as GREEN
        up = sentinel_upgrade(GREEN, {"verdict": "AGREE_YELLOW"})
        self.assertEqual(up["route"], YELLOW)

    def test_green_sentinel_agree_red_upgrades_red(self):
        up = sentinel_upgrade(GREEN, {"verdict": "AGREE_RED"})
        self.assertEqual(up["route"], RED)

    def test_yellow_sentinel_agree_green_remains_yellow(self):
        up = sentinel_upgrade(YELLOW, {"verdict": "AGREE_GREEN"})
        self.assertFalse(up["upgraded"])
        self.assertEqual(up["route"], YELLOW)

    def test_red_sentinel_agree_green_remains_red(self):
        up = sentinel_upgrade(RED, {"verdict": "AGREE_GREEN"})
        self.assertFalse(up["upgraded"])
        self.assertEqual(up["route"], RED)

    def test_green_agree_green_can_pass_at_r4(self):
        g = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True,
                              sentinel_identity_verified=True,
                              sentinel_verdict="AGREE_GREEN")
        self.assertEqual(g["status"], GATE_PASS)


class TestRiskCardFailClosed(unittest.TestCase):
    """§12/13/14: malformed cards are ROUTING_INVALID and never pass."""

    def test_risk_without_evidence_rejected(self):
        c = card(risk={"data_semantics": True})
        with self.assertRaises(RiskCardInvalid):
            compute_model_route_v2_1_1(c)

    def test_evidence_for_false_dimension_rejected(self):
        c = card(risk_evidence=[{"dimension": "data_semantics",
                                 "evidence": "no flag set"}])
        with self.assertRaises(RiskCardInvalid):
            compute_model_route_v2_1_1(c)

    def test_informational_evidence_allowed(self):
        c = card(risk_evidence=[{"dimension": "data_semantics",
                                 "evidence": "informational note",
                                 "informational": True}])
        self.assertEqual(compute_model_route_v2_1_1(c).route, YELLOW)

    def test_green_without_frozen_mechanical_rejected(self):
        c = card(green_allowlist_class="TYPO_FIX", frozen_mechanical_execution=False)
        with self.assertRaises(RiskCardInvalid):
            compute_model_route_v2_1_1(c)

    def test_authority_dependent_green_without_refs_rejected(self):
        c = card(green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                 frozen_mechanical_execution=True, authority_refs=[])
        with self.assertRaises(RiskCardInvalid):
            compute_model_route_v2_1_1(c)

    def test_frozen_mechanical_with_semantic_risk_rejected(self):
        # §13: frozen_mechanical_execution must NOT suppress flagged risk;
        # the combination is contradictory and rejected.
        c = card(risk={"statistical_inference": True},
                 frozen_mechanical_execution=True,
                 risk_evidence=[{"dimension": "statistical_inference",
                                 "evidence": "choice"}])
        with self.assertRaises(RiskCardInvalid):
            compute_model_route_v2_1_1(c)

    def test_unknown_dimension_rejected(self):
        c = card(risk={"not_a_dimension": True})
        with self.assertRaises(RiskCardInvalid):
            compute_model_route_v2_1_1(c)


class TestOutcomeAwareGate(unittest.TestCase):
    """P0-1/§3: VERIFIED_PRO_MAX is identity, never semantic approval."""

    def test_yellow_identity_unverified_blocked(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=False,
                              review_verdict="PASS", required_actions_closed=True)
        self.assertEqual(g["status"], ROUTING_BLOCKED)

    def test_yellow_verdict_blocked_blocked(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict="BLOCKED", required_actions_closed=False)
        self.assertEqual(g["status"], ROUTING_BLOCKED)

    def test_yellow_verdict_human_gate_required(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict="HUMAN_GATE_REQUIRED")
        self.assertEqual(g["status"], HUMAN_GATE_REQUIRED)

    def test_yellow_pass_actions_open_blocked(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict="PASS", required_actions_closed=False)
        self.assertEqual(g["status"], ROUTING_BLOCKED)

    def test_yellow_pass_actions_closed_passes(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict="PASS", required_actions_closed=True)
        self.assertEqual(g["status"], GATE_PASS)

    def test_yellow_caveat_actions_open_blocked(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict="PASS_WITH_CAVEAT",
                              required_actions_closed=False)
        self.assertEqual(g["status"], ROUTING_BLOCKED)

    def test_yellow_caveat_actions_closed_passes_with_caveat_recorded(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict="PASS_WITH_CAVEAT",
                              required_actions_closed=True)
        self.assertEqual(g["status"], GATE_PASS)
        self.assertTrue(g.get("caveat_recorded"))

    def test_yellow_unknown_verdict_blocked(self):
        g = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict=None)
        self.assertEqual(g["status"], ROUTING_BLOCKED)


class TestHumanGateVerdicts(unittest.TestCase):
    """§4: RED gate requires human_gate_verdict ACCEPTED."""

    def test_red_pending_requires_human_gate(self):
        g = route_gate_v2_1_1(RED, human_gate_verdict="PENDING")
        self.assertEqual(g["status"], HUMAN_GATE_REQUIRED)

    def test_red_rejected_blocked(self):
        g = route_gate_v2_1_1(RED, human_gate_verdict="REJECTED")
        self.assertEqual(g["status"], ROUTING_BLOCKED)

    def test_red_accepted_continues(self):
        g = route_gate_v2_1_1(RED, human_gate_verdict="ACCEPTED")
        self.assertEqual(g["status"], GATE_PASS)

    def test_red_unknown_verdict_blocked(self):
        g = route_gate_v2_1_1(RED, human_gate_verdict="OCCURRED")
        self.assertEqual(g["status"], ROUTING_BLOCKED)


if __name__ == "__main__":
    unittest.main()
