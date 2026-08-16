# MATHEMATICAL_MODELING_ROUTER_V2.1 — 通用数学建模风险路由（设计文档）

> 状态：IMPLEMENTED（Phase B；additive，构建于已接受的 Phase-A PRO-MAX ROUTING V1.0 之上）
> 日期：2026-08-16
> Phase-A accepted commit：`7f670557f8b6e7787386f10908608eea0327d20e`
> 适用：全国大学生数学建模竞赛 A/B/C、研究生数学建模、MCM/ICM 及一般数学建模任务
> 证据根：`05_结果/governance/model_routing/`（v2/ 为本阶段产物）

## 0. 定位

Phase A（MODEL_ROUTING_PRO_MAX_V1.0）= **HOW TO INVOKE VERIFIED PRO-MAX**。
Phase B（本 Router）= **WHEN TO INVOKE PRO-MAX + HOW TO VERIFY DIFFERENT MODEL FAMILIES**。

本 Router 不判断任务"难不难"；它判断：**如果当前执行者把问题理解错，是否可能改变题意/建模假设/数学模型/数据定义/统计推断/算法含义/数值解/模型比较/排序/最优方案/预测结论/正式建议/论文主要结论。**

不对称错误代价：**FALSE GREEN 比 FALSE YELLOW 严重得多。** UNKNOWN/UNSURE/AMBIGUOUS → YELLOW。无法证明 GREEN → YELLOW（不是"没发现危险 → GREEN"）。

## 1. 四层架构

```
LAYER 1  UNIVERSAL RISK FACT EXTRACTION   执行者描述客观风险事实（Risk Card）
LAYER 2  DETERMINISTIC ROUTE ENGINE       机械计算 GREEN/YELLOW/RED
LAYER 3  ROUTE SENTINEL                   独立低成本 reviewer，只查分类遗漏
LAYER 4  METHOD-AWARE VERIFICATION       Method Family → 验证武器
```

**重要分离（spec 5）**：
- RISK ROUTING 决定"谁来判断"：GREEN→Flash；YELLOW→Flash + mandatory fresh Pro-Max（VERIFIED_PRO_MAX）；RED→Human Gate。
- METHOD FAMILY 决定"怎么验证"：例如优化→feasibility/brute-force small instance；物理→dimensions/conservation/convergence；ML→leakage/CV/baseline；DES→event invariant/toy world。
- Method family **不得决定风险颜色**。

## 2. Authority State（spec 6）

`EXPLORATORY | PROPOSED | FROZEN | HUMAN_ACCEPTED`。
修改模型**不是自动 RED**：EXPLORATORY 阶段选线性/非线性 → YELLOW；只有 FROZEN / HUMAN_ACCEPTED 之后改变正式定义 → RED。

## 3. Modeling Stage（spec 7）

`PROBLEM_UNDERSTANDING | DATA_UNDERSTANDING | EXPLORATORY_MODELING | ASSUMPTION_DESIGN | FORMULATION | IMPLEMENTATION | CALIBRATION | VALIDATION | FORMAL_EVALUATION | RECOMMENDATION | WRITING | GOVERNANCE`。
"在写代码"不自动低风险：一行代码修改也可能是 semantic YELLOW。

## 4. 通用风险维度 R1..R10（spec 9）

R1 PROBLEM_SEMANTICS（题意/目标/事件/指标/自然语言约束词义）
R2 MODELING_ASSUMPTION（独立性/线性/平稳性/分布/缺失机制/物理简化/可忽略因素）
R3 MATHEMATICAL_FORMULATION（目标函数/约束/决策变量/转移方程/概率模型/守恒/初边值）
R4 DATA_SEMANTICS（样本单位/聚合/缺失/异常/归一化/标签/对齐/分母口径）
R5 STATISTICAL_INFERENCE（estimator/sampling unit/CI/bootstrap/检验/多重比较/split/CV/holdout/口径）
R6 ALGORITHMIC_SEMANTICS（状态/事件顺序/random stream/seed/停止条件/tie-break/搜索空间/MC protocol/solver semantics）
R7 NUMERICAL_METHOD（步长/网格/容差/积分器/离散化/精度/收敛判据）
R8 VALIDATION_INTERPRETATION（test 是否真测到目标机制/checker 独立性/baseline 有效性/敏感性支持）
R9 FORMAL_RESULT_IMPACT（核心数值/排序/最优方案/参数推荐/预测/评价/正式结论）
R10 GOVERNANCE_AUTHORITY（FROZEN/HUMAN_ACCEPTED 下改变正式题意解释/核心假设/模型/阈值/split/random protocol/评估门/统计口径 → RED）

## 5. 确定性路由引擎（spec 11，顺序固定）

```
IF governance_authority AND authority_state ∈ {FROZEN, HUMAN_ACCEPTED}   → RED
ELIF any semantic risk AND NOT frozen_mechanical_execution               → YELLOW
ELIF uncertainty_present                                                 → YELLOW
ELIF multiple_plausible_interpretations                                  → YELLOW
ELIF authority_ambiguity                                                 → YELLOW
ELIF engineering escalation (formal_scope)                               → YELLOW
ELIF green_allowlist_class ∈ ALLOWLIST                                   → GREEN
ELSE                                                                     → YELLOW
```

## 6. GREEN Allowlist（spec 12）

GREEN 只能来自白名单：RUN_EXISTING_TEST / RUN_EXISTING_CHECKER / REGRESSION_EXECUTION / FORMAT_ONLY / TYPO_FIX / IMPORT_PATH_FIX / JSON_SCHEMA_FIELD_FIX / REPORT_FIELD_SYNC / HASH_PROVENANCE / EVIDENCE_PACKAGING / MECHANICAL_DATA_TRANSFORM_UNDER_FROZEN_EXACT_RULE / MECHANICAL_FORMULA_IMPLEMENTATION_UNDER_FROZEN_EXACT_FORMULA / MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG / PLOT_FROM_FROZEN_DATA_AND_SPEC / SEMANTICS_PRESERVING_REFACTOR / REPRODUCE_ACCEPTED_RESULT_WITHOUT_METHOD_CHANGE。且无 RED、无 YELLOW 语义触发、uncertainty=false。代码量不影响颜色。

## 7. Engineering Escalation（spec 13）

S1 new_complex_seam；S2 repeat_failure_count≥2；S3 checker_disagreement；S4 checker_independence_concern；S5 claimed_coverage_not_exercised；S6 unexpected_behavior_after_pass；S7 formal_numeric_shift。
formal_scope=true 且 S3–S7 任一 → YELLOW；S1/S2 且无法证明纯机械（frozen_mechanical_execution）→ YELLOW。

## 8. Uncertainty Escalation（spec 14）

unclear/ambiguous/uncertain/not sure/seems/probably/could mean/two reasonable interpretations/spec does not define/authority may conflict 等，且对象涉及题意/模型/假设/数据/统计/算法/数值/正式结果 → uncertainty_present=true → ≥YELLOW。禁止"虽然拿不准，先按我的理解做"。

## 9. 动态重分类（spec 15，R0–R4）

R0 task start；R1 first failure/unexpected behavior；R2 before semantic-affecting patch；R3 after patch before formal verification；R4 before Gate decision。每个 checkpoint 存 Risk Card snapshot；记录 `TASK_RECLASSIFIED`（如 GREEN→YELLOW），立刻停止 semantic branch 进入 Pro-Max review。

## 10. Route Sentinel V1（spec 16-17，见 ROUTE_SENTINEL_V1.md）

低成本 Flash CLASSIFICATION_AUDITOR_ONLY reviewer；只查分类遗漏，不做数学裁决、不改 authority、不修代码、不能把 YELLOW 降 GREEN / RED 降 YELLOW。触发：A）formal_scope=true 且 proposed=GREEN 的 R4 Gate；B）GREEN 任务曾发生 R1/R2/R3 reclassification candidate；C）任务产生 formal result；D）新 cross-module semantic seam；E）正式 reviewer 即将 PASS。
输出 SENTINEL_VERDICT：AGREE_GREEN/AGREE_YELLOW/AGREE_RED/RISK_OMISSION/ROUTE_TOO_LOW。RISK_OMISSION/ROUTE_TOO_LOW → 自动 YELLOW → mandatory Pro-Max；Flash 不得否决 Sentinel 分歧。

## 11. YELLOW 执行（spec 18）

Flash 负责读文件/收集证据/跑 checker/构造 toy case/无语义争议的机械实现；semantic question 交给 pro_max_review（fresh spawn、VERIFIED_PRO_MAX required），Pro-Max 负责语义/数学/统计/模型假设判断/反例/验证设计建议；默认 READ_ONLY。

## 12. RED 执行（spec 19）

STOP semantic branch；生成 HUMAN_GATE_PACKET（existing frozen authority / requested mutation / why / expected effect / alternatives / Pro-Max opinion if available）；Human Gate 决定；Pro-Max 不得自行批准 frozen mutation。

## 13. Semantic Issue Dedup（spec 20-21）

每个 YELLOW concern 有 semantic_issue_id（如 ASSUMPTION-001 / SAMPLING-003）。已有 VERIFIED_PRO_MAX + 明确 verdict 且 contract（哈希）未变 → 只机械执行 verdict，不重复调用 Max。Re-review 仅当：semantic contract changed / new counterexample / new authority evidence / checker contradiction / previous required_action unresolved / new formal implication / previous caveat becomes material。

## 14. 验证注册表（spec 22-32）

- METHOD_FAMILY_REGISTRY_V1.0：16 族 multi-label（ANALYTICAL_MATH / PROBABILITY_STATISTICS / REGRESSION_PREDICTION / TIME_SERIES / MACHINE_LEARNING / OPTIMIZATION / OPERATIONS_RESEARCH / GRAPH_NETWORK / DISCRETE_EVENT_SIMULATION / MONTE_CARLO_STOCHASTIC / ODE_PDE_DYNAMICAL_SYSTEM / PHYSICS_MECHANISM / MULTI_CRITERIA_EVALUATION / SPATIAL_GIS / NUMERICAL_COMPUTATION / HYBRID_OTHER）。不确定时 multi-label；无法识别 → HYBRID_OTHER。**Family 不决定颜色。**
- UNIVERSAL VERIFICATION BASELINE（11 项候选）：independent recomputation / small toy instance / boundary/extreme case / scale-unit sanity / invariant-conservation / baseline comparison / sensitivity-perturbation / reproducibility / claim-to-evidence consistency / data lineage-leakage / verification independence。
- VERIFICATION_STRATEGY_REGISTRY_V1.0：每族优先武器（见独立文档）。Registry 只选武器，**不得创建** PASS/significance/accept-reject 阈值——阈值必须来自 authority（plan builder 对 threshold-bearing check 缺 authority_thresholds 即拒绝）。

## 15. Project Extension（spec 33）

`PROJECT_ROUTING_EXTENSION.yml/json`：项目术语→风险维度、项目方法→method family、项目历史错误→regression pattern。只能保持或升级风险；YELLOW→GREEN、RED→YELLOW 一律 REJECTED。禁止修改 Universal Core。

## 16. Generalization Guard（spec 34）

Universal Core source（risk_card/route_engine/method_families/verification_strategies/sentinel/extensions/miss_registry/events）不得出现项目专属 token（列表见 `04_代码/governance/model_routing_v2/data/project_specific_tokens.json`）。`GENERALIZATION_CHECK` FAIL → 本包 FAIL。项目经验只进 extension / regression corpus / miss registry。

## 17. Routing Miss Registry（spec 35）

`MODEL_ROUTING_MISS_REGISTRY.json`：miss_id/date/domain/original_route/correct_route/universal_risk_dimension/failure_pattern/new_general_rule/scope(UNIVERSAL|PROJECT_SPECIFIC)/status。只有跨题型有效 pattern 进 Universal；题目专属进 Extension。

## 18. A3 — 静态策略 ≠ 运行时强制（Phase-A carry-forward）

Phase-A 的 ROUTE-08/09/10 只证明：**policy contract + 专用 route 的 fail-closed 行为**（dedicated route 静态绑定、失败即 errored tool result）。它们**不构成** Universal Router 的运行时强制。本 Phase B 才实现：task classification（Risk Card）、risk card、deterministic route computation、YELLOW mandatory VERIFIED_PRO_MAX、RED Human Gate、runtime enforcement（route_gate_v2_1）、Gate-time checker（MMR-01..16）。只有 Phase B 完成后，`MODEL_ROUTING_ENFORCEMENT_GAP` 才在**任务层**闭合。

## 19. 检查与门

- 路由检查器：`04_代码/governance/model_routing_v2/check_mathematical_modeling_router_v2_1.py`（MMR-01..16，从真实 artifact/状态计算）。
- 跨域合成测试 T01–T26（spec 38）+ verification-family 测试 + 负例（spec 39/41）见 `.../tests/`。
- 阶段指标（spec 43）：从 `v2/routing_events.jsonl` 计算；**不设 GREEN 占比目标、不设 Pro-Max 调用数目标**。

## 20. 与本阶段相关的命令

- 事件/指标生成：`python tmp/generate_router_evidence_v2.py`（演示序列 + 事件流 + metrics）。
- 路由检查：`python 04_代码/governance/model_routing_v2/check_mathematical_modeling_router_v2_1.py 05_结果/governance/model_routing`。
- 通用性检查：`generalization_check()`（MMR-14 内含）。
