# METHOD_FAMILY_REGISTRY_V1.0 — 方法族注册表

> 通用、multi-label；方法族只决定验证武器，**绝不决定风险颜色**（路由引擎不消费方法族）。
> 实现：`04_代码/governance/model_routing_v2/method_families.py`

## 支持的方法族（16）

| ID | 关键词示例 |
|---|---|
| ANALYTICAL_MATH | closed form, analytic, derivation, exact solution, formula |
| PROBABILITY_STATISTICS | probability, distribution, hypothesis, bootstrap, confidence, estimator, likelihood |
| REGRESSION_PREDICTION | regression, predict, forecast, linear/logistic model |
| TIME_SERIES | time series, rolling, seasonal, autocorrelation, arima, trend |
| MACHINE_LEARNING | neural, gradient boosting, random forest, SVM, training set, cross-validation, deep learning |
| OPTIMIZATION | optimize, minimize/maximize, objective, constraint, LP/MILP, convex, gradient descent |
| OPERATIONS_RESEARCH | scheduling, routing, assignment, queueing, inventory, transportation, network flow |
| GRAPH_NETWORK | graph, network, shortest path, connectivity, centrality, max flow, topology |
| DISCRETE_EVENT_SIMULATION | discrete event, event-driven, simulation, agent-based, queue simulation |
| MONTE_CARLO_STOCHASTIC | monte carlo, stochastic, random draw/seed, sampling, replicate, bootstrap |
| ODE_PDE_DYNAMICAL_SYSTEM | ODE, PDE, differential equation, dynamical, equilibrium, phase plane |
| PHYSICS_MECHANISM | physics, mechanism, force, mass, energy, conservation, mechanics, friction |
| MULTI_CRITERIA_EVALUATION | topsis, ahp, entropy weight, multi-criteria, composite index, ranking, weighted scoring |
| SPATIAL_GIS | gis, spatial, coordinate, geospatial, raster, distance matrix |
| NUMERICAL_COMPUTATION | numerical, discretization, step size, finite difference/element, iteration, solver, convergence |
| HYBRID_OTHER | 无法识别的兜底（multi-label 命中任意族时也允许叠加） |

## 规则

1. multi-label：一个任务可命中多族（如 "simulate a queue with monte carlo sampling" → DISCRETE_EVENT_SIMULATION + MONTE_CARLO_STOCHASTIC）。
2. 完全无法识别 → HYBRID_OTHER。
3. 分类器为确定性关键词规则（`classify_method_families`）；不引入 LLM。
4. 风险颜色由 Risk Card + 路由引擎决定；方法族元数据不进入 `compute_model_route_v2_1`（结构性隔离，MMR-12 验证）。
