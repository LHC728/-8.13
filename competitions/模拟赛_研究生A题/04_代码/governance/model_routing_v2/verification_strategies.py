"""MATHEMATICAL_MODELING_ROUTER_V2.1 — verification strategy registry (spec
23-32, LAYER 4).

VERIFICATION_STRATEGY_REGISTRY_V1.0: per-method-family verification weapons
plus the universal baseline.  The registry ONLY selects checks — it never
creates PASS thresholds, significance levels, or accept/reject rules; every
threshold must come from authority (verification_plan builder refuses
threshold-bearing checks without supplied authority_thresholds).

This module is part of the UNIVERSAL CORE (generalization guard scans it).
Python 3.12, standard library only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

# universal verification baseline (spec 23)
UNIVERSAL_BASELINE = (
    "independent_recomputation",
    "small_toy_instance",
    "boundary_extreme_case",
    "scale_unit_sanity",
    "invariant_conservation",
    "baseline_comparison",
    "sensitivity_perturbation",
    "reproducibility",
    "claim_to_evidence_consistency",
    "data_lineage_leakage",
    "verification_independence",
)

# per-family candidate checks, most-valuable-first (spec 25-31)
STRATEGY_REGISTRY: dict[str, tuple[str, ...]] = {
    "ANALYTICAL_MATH": (
        "symbolic_derivation_check", "independent_numeric_recomputation",
        "normalization_check", "limiting_case", "exact_small_domain_enumeration"),
    "PROBABILITY_STATISTICS": (
        "probability_sum_check", "distribution_moments", "sampling_unit_audit",
        "denominator_audit", "bootstrap_vs_analytic_comparison",
        "monte_carlo_sanity", "exact_small_domain_enumeration"),
    "REGRESSION_PREDICTION": (
        "train_test_leakage", "baseline_model", "metric_recomputation",
        "residual_diagnostics", "overfitting_check", "seed_stability"),
    "TIME_SERIES": (
        "temporal_leakage", "rolling_origin_validation", "residual_diagnostics",
        "baseline_model", "metric_recomputation"),
    "MACHINE_LEARNING": (
        "train_test_leakage", "feature_leakage", "cross_validation_audit",
        "baseline_model", "metric_recomputation", "ablation",
        "class_imbalance", "seed_stability", "calibration_check"),
    "OPTIMIZATION": (
        "constraint_feasibility", "objective_recomputation",
        "small_instance_brute_force", "alternative_solver",
        "lower_upper_bound", "integrality_check", "parameter_sensitivity",
        "initialization_dependence", "local_vs_global_warning"),
    "OPERATIONS_RESEARCH": (
        "constraint_feasibility", "small_instance_brute_force",
        "objective_recomputation", "alternative_solver", "lower_upper_bound",
        "parameter_sensitivity"),
    "GRAPH_NETWORK": (
        "connectivity_check", "flow_conservation", "small_graph_oracle",
        "path_cut_recomputation", "topology_invariants", "geometry_edge_cases"),
    "DISCRETE_EVENT_SIMULATION": (
        "deterministic_toy_world", "state_invariant", "event_invariant",
        "independent_replay", "event_ordering", "random_stream_audit",
        "seed_reproducibility", "state_transition_counterexample",
        "extreme_load_scenario"),
    "MONTE_CARLO_STOCHASTIC": (
        "monte_carlo_convergence", "variance_audit", "seed_reproducibility",
        "random_stream_audit", "paired_comparison",
        "deterministic_toy_world", "bootstrap_vs_analytic_comparison"),
    "ODE_PDE_DYNAMICAL_SYSTEM": (
        "dimensional_analysis", "unit_consistency", "conservation_law",
        "initial_condition", "boundary_condition", "known_special_case",
        "limiting_behavior", "step_size_refinement", "mesh_convergence",
        "alternative_integrator", "residual_check", "numerical_stability"),
    "PHYSICS_MECHANISM": (
        "dimensional_analysis", "unit_consistency", "conservation_law",
        "physical_plausibility", "known_special_case", "limiting_behavior"),
    "MULTI_CRITERIA_EVALUATION": (
        "normalization_recomputation", "weight_consistency",
        "monotonicity", "rank_reversal", "weight_perturbation",
        "scale_invariance", "alternative_weighting",
        "raw_score_to_rank_trace"),
    "SPATIAL_GIS": (
        "coordinate_system_audit", "distance_metric_audit",
        "spatial_leakage", "geometry_edge_cases", "topology_invariants"),
    "NUMERICAL_COMPUTATION": (
        "step_size_refinement", "mesh_convergence", "alternative_integrator",
        "residual_check", "numerical_stability", "unit_consistency",
        "known_special_case", "limiting_behavior"),
    "HYBRID_OTHER": UNIVERSAL_BASELINE,
}

# checks whose acceptance requires a numeric threshold (authority-provided only)
THRESHOLD_BEARING_CHECKS = frozenset({
    "monte_carlo_convergence",      # convergence tolerance
    "numerical_stability",          # stability criterion
    "mesh_convergence",             # convergence tolerance
    "metric_recomputation",         # evaluation threshold
})


def strategy_checks(families: list[str]) -> list[str]:
    """Ordered candidate checks for the given families (deduplicated)."""
    seen: set[str] = set()
    out: list[str] = []
    for fam in families:
        for check in STRATEGY_REGISTRY.get(fam, UNIVERSAL_BASELINE):
            if check not in seen:
                seen.add(check)
                out.append(check)
    if not out:
        out = list(UNIVERSAL_BASELINE)
    return out


def build_verification_plan(*, task_id: str, semantic_issue_id: Optional[str],
                            method_families: list[str],
                            risk_dimensions: list[str],
                            claim_under_review: str,
                            selected_checks: list[str],
                            authority_thresholds: dict[str, Any],
                            independence_level: str = "independent",
                            estimated_cost: str = "low") -> dict[str, Any]:
    """Build a verification plan.  Threshold-bearing checks REQUIRE an
    authority-provided threshold; the registry never invents one (spec 24).
    """
    missing = [c for c in selected_checks
               if c in THRESHOLD_BEARING_CHECKS
               and c not in authority_thresholds]
    if missing:
        raise ValueError(
            "verification plan requires authority-provided thresholds for "
            + ", ".join(missing) + "; the registry never invents thresholds")
    return {
        "router_version": "MMR_V2.1",
        "task_id": task_id,
        "semantic_issue_id": semantic_issue_id,
        "method_families": method_families,
        "risk_dimensions": risk_dimensions,
        "claim_under_review": claim_under_review,
        "candidate_checks": strategy_checks(method_families),
        "selected_checks": selected_checks,
        "why_selected": "highest error-detection value at lowest cost, "
                        "matched to the flagged risk dimensions",
        "estimated_cost": estimated_cost,
        "independence_level": independence_level,
        "requires_code_execution": True,
        "requires_external_source": False,
        "requires_pro_max": False,
        "authority_thresholds": authority_thresholds,
        "expected_artifacts": [f"evidence/{task_id}/{c}.json" for c in selected_checks],
    }


def plan_to_json(plan: dict[str, Any], path: str) -> None:
    Path(path).write_text(
        json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")
