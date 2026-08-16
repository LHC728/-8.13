"""MATHEMATICAL_MODELING_ROUTER_V2.1 — synthetic cross-domain tests (spec 38).

T01..T26: deterministic route-engine behaviour across generic modeling
domains.  Pure unit tests — no network, no Pro-Max calls.
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
    RiskCard, EngineeringSignals)
from governance.model_routing_v2.route_engine import (  # noqa: E402
    compute_model_route_v2_1, route_gate_v2_1, GREEN, YELLOW, RED,
    ROUTING_BLOCKED, HUMAN_GATE_REQUIRED)
from governance.model_routing_v2.method_families import (  # noqa: E402
    classify_method_families, HYBRID_OTHER)
from governance.model_routing_v2.sentinel import (  # noqa: E402
    parse_sentinel_verdict, sentinel_upgrade)
from governance.model_routing_v2.extensions import (  # noqa: E402
    validate_extension, ExtensionRejected)


def card(**kw) -> RiskCard:
    defaults = dict(task_id="T", stage="FORMULATION",
                    authority_state="EXPLORATORY", formal_scope=True)
    defaults.update(kw)
    return RiskCard(**defaults)


class TestCrossDomainRouting(unittest.TestCase):
    # ---- optimization ---------------------------------------------------
    def test_t01_run_frozen_milp_green(self):
        c = card(green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                 frozen_mechanical_execution=True,
                 authority_state="FROZEN")
        self.assertEqual(compute_model_route_v2_1(c).route, GREEN)

    def test_t02_choose_average_vs_max_wait_objective_yellow(self):
        c = card(risk={"mathematical_formulation": True},
                 risk_evidence=[{"dimension": "mathematical_formulation",
                                 "evidence": "objective choice not frozen"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    # ---- physics / numerics ---------------------------------------------
    def test_t03_run_frozen_rk4_green(self):
        c = card(green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                 frozen_mechanical_execution=True,
                 authority_state="FROZEN")
        self.assertEqual(compute_model_route_v2_1(c).route, GREEN)

    def test_t04_air_resistance_negligible_decision_yellow(self):
        c = card(risk={"modeling_assumption": True},
                 risk_evidence=[{"dimension": "modeling_assumption",
                                 "evidence": "negligibility is a modeling choice"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    def test_t05_step_size_changes_conclusion_yellow(self):
        c = card(risk={"numerical_method": True},
                 risk_evidence=[{"dimension": "numerical_method",
                                 "evidence": "step size choice changes the conclusion"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    # ---- statistics -----------------------------------------------------
    def test_t06_run_frozen_bootstrap_green(self):
        c = card(green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                 frozen_mechanical_execution=True,
                 authority_state="FROZEN")
        self.assertEqual(compute_model_route_v2_1(c).route, GREEN)

    def test_t07_bootstrap_row_vs_subject_yellow(self):
        c = card(risk={"statistical_inference": True},
                 risk_evidence=[{"dimension": "statistical_inference",
                                 "evidence": "sampling unit choice is not frozen"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    # ---- ML / prediction ------------------------------------------------
    def test_t08_train_frozen_ml_config_green(self):
        c = card(green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                 frozen_mechanical_execution=True,
                 authority_state="FROZEN")
        self.assertEqual(compute_model_route_v2_1(c).route, GREEN)

    def test_t09_random_split_vs_temporal_split_yellow(self):
        c = card(risk={"statistical_inference": True},
                 risk_evidence=[{"dimension": "statistical_inference",
                                 "evidence": "split semantics undefined"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    def test_t10_choose_rolling_origin_cv_yellow(self):
        c = card(risk={"statistical_inference": True},
                 risk_evidence=[{"dimension": "statistical_inference",
                                 "evidence": "CV scheme is a statistical choice"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    # ---- multi-criteria -------------------------------------------------
    def test_t11_run_frozen_topsis_green(self):
        c = card(green_allowlist_class="MECHANICAL_FORMULA_IMPLEMENTATION_UNDER_FROZEN_EXACT_FORMULA",
                 frozen_mechanical_execution=True,
                 authority_state="FROZEN")
        self.assertEqual(compute_model_route_v2_1(c).route, GREEN)

    def test_t12_minmax_vs_zscore_changes_ranking_yellow(self):
        c = card(risk={"data_semantics": True, "formal_result_impact": True},
                 risk_evidence=[{"dimension": "data_semantics",
                                 "evidence": "normalization choice not frozen"},
                                {"dimension": "formal_result_impact",
                                 "evidence": "ranking changes under the two schemes"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    # ---- graph / network ------------------------------------------------
    def test_t13_run_shortest_path_frozen_graph_green(self):
        c = card(green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                 frozen_mechanical_execution=True,
                 authority_state="FROZEN")
        self.assertEqual(compute_model_route_v2_1(c).route, GREEN)

    def test_t14_edge_weight_distance_or_time_yellow(self):
        c = card(risk={"problem_semantics": True},
                 risk_evidence=[{"dimension": "problem_semantics",
                                 "evidence": "edge weight meaning is ambiguous"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    # ---- simulation -----------------------------------------------------
    def test_t15_run_frozen_simulation_green(self):
        c = card(green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                 frozen_mechanical_execution=True,
                 authority_state="FROZEN")
        self.assertEqual(compute_model_route_v2_1(c).route, GREEN)

    def test_t16_simultaneous_event_ordering_unclear_yellow(self):
        c = card(risk={"algorithmic_semantics": True},
                 risk_evidence=[{"dimension": "algorithmic_semantics",
                                 "evidence": "same-time event order undefined"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    # ---- authority states (spec 6/16) -----------------------------------
    def test_t17_exploratory_linear_to_nonlinear_yellow_not_red(self):
        c = card(risk={"modeling_assumption": True},
                 authority_state="EXPLORATORY",
                 risk_evidence=[{"dimension": "modeling_assumption",
                                 "evidence": "model family choice in exploration"}])
        r = compute_model_route_v2_1(c)
        self.assertEqual(r.route, YELLOW)  # NOT RED

    def test_t18_frozen_change_accepted_objective_red(self):
        c = card(risk={"mathematical_formulation": True,
                       "governance_authority": True},
                 authority_state="FROZEN",
                 risk_evidence=[{"dimension": "mathematical_formulation",
                                 "evidence": "objective mutation requested"},
                                {"dimension": "governance_authority",
                                 "evidence": "frozen authority mutation"}])
        self.assertEqual(compute_model_route_v2_1(c).route, RED)

    def test_t19_human_accepted_change_significance_threshold_red(self):
        c = card(risk={"statistical_inference": True,
                       "governance_authority": True},
                 authority_state="HUMAN_ACCEPTED",
                 risk_evidence=[{"dimension": "statistical_inference",
                                 "evidence": "threshold change after result"},
                                {"dimension": "governance_authority",
                                 "evidence": "accepted authority mutation"}])
        self.assertEqual(compute_model_route_v2_1(c).route, RED)

    # ---- dynamic reclassification (spec 15) ------------------------------
    def test_t20_path_typo_green_then_units_discovered_yellow(self):
        c0 = card(task_id="T20", checkpoint="R0",
                  green_allowlist_class="TYPO_FIX",
                  frozen_mechanical_execution=True)
        self.assertEqual(compute_model_route_v2_1(c0).route, GREEN)
        c1 = card(task_id="T20", checkpoint="R1",
                  risk={"data_semantics": True},
                  risk_evidence=[{"dimension": "data_semantics",
                                  "evidence": "fields carry different statistical units"}])
        self.assertEqual(compute_model_route_v2_1(c1).route, YELLOW)

    # ---- scale independence ----------------------------------------------
    def test_t21_500_line_mechanical_implementation_green(self):
        c = card(green_allowlist_class="MECHANICAL_FORMULA_IMPLEMENTATION_UNDER_FROZEN_EXACT_FORMULA",
                 frozen_mechanical_execution=True,
                 authority_state="FROZEN")
        self.assertEqual(compute_model_route_v2_1(c).route, GREEN)

    def test_t22_one_line_state_transition_semantic_change_yellow(self):
        c = card(risk={"algorithmic_semantics": True},
                 risk_evidence=[{"dimension": "algorithmic_semantics",
                                 "evidence": "state-transition semantics change"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    # ---- unknown hybrid ---------------------------------------------------
    def test_t23_unknown_hybrid_two_models_yellow(self):
        fams = classify_method_families("hybrid custom approach with no known family")
        self.assertEqual(fams, [HYBRID_OTHER])
        c = card(risk={"modeling_assumption": True},
                 multiple_plausible_interpretations=True,
                 risk_evidence=[{"dimension": "modeling_assumption",
                                 "evidence": "two plausible models"}])
        self.assertEqual(compute_model_route_v2_1(c).route, YELLOW)

    # ---- sentinel ---------------------------------------------------------
    def test_t24_sentinel_finds_missed_assumption_upgrade_yellow(self):
        c = card(green_allowlist_class="RUN_EXISTING_CHECKER",
                 frozen_mechanical_execution=True)
        self.assertEqual(compute_model_route_v2_1(c).route, GREEN)
        result = parse_sentinel_verdict(
            "SENTINEL_VERDICT: RISK_OMISSION\n"
            "missing_risk_dimensions: [modeling_assumption]\n"
            "reason: assumption unstated")
        up = sentinel_upgrade(GREEN, result)
        self.assertTrue(up["upgraded"])
        self.assertEqual(up["route"], YELLOW)

    def test_t25_sentinel_agrees_mechanical_frozen_green(self):
        c = card(green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                 frozen_mechanical_execution=True,
                 authority_state="FROZEN")
        self.assertEqual(compute_model_route_v2_1(c).route, GREEN)
        result = parse_sentinel_verdict("SENTINEL_VERDICT: AGREE_GREEN")
        up = sentinel_upgrade(GREEN, result)
        self.assertFalse(up["upgraded"])
        self.assertEqual(up["route"], GREEN)

    # ---- extension non-deescalation ---------------------------------------
    def test_t26_extension_yellow_to_green_rejected(self):
        bad = {
            "extension_version": "1.0", "project_id": "p",
            "term_risks": {"some_term": {"risks": [], "route_cap": "GREEN"}},
        }
        with self.assertRaises(ExtensionRejected):
            validate_extension(bad)
        bad2 = {
            "extension_version": "1.0", "project_id": "p",
            "term_risks": {"some_term": {"risks": ["not_a_dimension"]}},
        }
        with self.assertRaises(ExtensionRejected):
            validate_extension(bad2)


if __name__ == "__main__":
    unittest.main()
