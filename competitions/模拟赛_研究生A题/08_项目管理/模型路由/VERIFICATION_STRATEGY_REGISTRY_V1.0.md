# VERIFICATION_STRATEGY_REGISTRY_V1.0 — 验证策略注册表

> 只决定"验证武器"，不得创建 PASS/significance/accept-reject 阈值（阈值必须来自 authority）。
> 实现：`04_代码/governance/model_routing_v2/verification_strategies.py`

## Universal Baseline（任何正式数学建模任务至少从这些候选中考虑）

independent_recomputation / small_toy_instance / boundary_extreme_case / scale_unit_sanity / invariant_conservation / baseline_comparison / sensitivity_perturbation / reproducibility / claim_to_evidence_consistency / data_lineage_leakage / verification_independence。

不要求全部执行；选择"最可能发现当前错误且成本最低"的一组（`build_verification_plan`）。

## 分族优先武器（most-valuable-first）

| 族 | 优先候选 |
|---|---|
| ANALYTICAL_MATH | symbolic derivation check, independent numeric recomputation, normalization check, limiting case, exact small-domain enumeration |
| PROBABILITY_STATISTICS | probability-sum check, distribution moments, sampling-unit audit, denominator audit, bootstrap-vs-analytic comparison, Monte Carlo sanity |
| REGRESSION_PREDICTION | train/test leakage, baseline model, metric recomputation, residual diagnostics, overfitting, seed stability |
| TIME_SERIES | temporal leakage, rolling-origin validation, residual diagnostics, baseline model |
| MACHINE_LEARNING | train/test leakage, feature leakage, CV audit, baseline model, metric recomputation, ablation, class imbalance, calibration |
| OPTIMIZATION | constraint feasibility, objective recomputation, small-instance brute force, alternative solver, lower/upper bound, integrality, parameter sensitivity, local-vs-global warning |
| OPERATIONS_RESEARCH | constraint feasibility, small-instance brute force, objective recomputation, alternative solver, lower/upper bound |
| GRAPH_NETWORK | connectivity, flow conservation, small-graph oracle, path/cut recomputation, topology invariants |
| DISCRETE_EVENT_SIMULATION | deterministic toy world, state invariant, event invariant, independent replay, event ordering, random-stream audit, seed reproducibility, extreme-load scenario |
| MONTE_CARLO_STOCHASTIC | MC convergence, variance audit, seed reproducibility, random-stream audit, paired comparison |
| ODE_PDE_DYNAMICAL_SYSTEM | dimensional analysis, unit consistency, conservation law, initial/boundary condition, known special case, limiting behavior, step-size refinement, mesh convergence, alternative integrator, residual check, numerical stability |
| PHYSICS_MECHANISM | dimensional analysis, unit consistency, conservation law, physical plausibility, known special case, limiting behavior |
| MULTI_CRITERIA_EVALUATION | normalization recomputation, weight consistency, monotonicity, rank reversal, weight perturbation, scale invariance, alternative weighting, raw-score-to-rank trace |
| SPATIAL_GIS | coordinate-system audit, distance-metric audit, spatial leakage, geometry edge cases, topology invariants |
| NUMERICAL_COMPUTATION | step-size refinement, mesh convergence, alternative integrator, residual check, numerical stability, unit consistency |
| HYBRID_OTHER | Universal Baseline |

## 阈值纪律（spec 24）

- `THRESHOLD_BEARING_CHECKS`（monte_carlo_convergence / numerical_stability / mesh_convergence / metric_recomputation）的接受需要 authority 提供的阈值。
- `build_verification_plan` 对"选择了 threshold-bearing check 但未提供 authority_thresholds"直接拒绝（ValueError）；注册表从不发明阈值（MMR-13 验证）。
