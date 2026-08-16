# MATHEMATICAL_MODELING_ROUTER_V2.1.1 — 通用数学建模风险路由（修复版权威）

> **SUPERSEDED_FOR_FINAL_GATE by MATHEMATICAL_MODELING_ROUTER_V2.1.2**（2026-08-16 FINAL HARDENING）。
> 本文档为 V2.1.1 修复历史记录，保留用于追溯；最终路由门语义以 `MATHEMATICAL_MODELING_ROUTER_V2.1.2.md` 为准（authority_conflict fail-closed、authority receipt、Sentinel runtime identity receipt、BLOCKED no-auto-rereview）。

> 状态：IMPLEMENTED（Phase B REPAIR；targeted repair of V2.1，架构保留）
> 日期：2026-08-16
> Phase-A accepted commit：`7f670557f8b6e7787386f10908608eea0327d20e`
> Phase-B V2.1 base：`0e8f6612b0274a8e53717f36af23e40701bbc583`
> V2.1 状态：**SUPERSEDED_FOR_ROUTING_GATE by V2.1.1**（历史实现保留）
> 失效声明：`05_结果/governance/model_routing/v2_1_1/INVALIDATION_REPORT_V2.1.1.md`
> 证据根：`05_结果/governance/model_routing/`（v2_1_1/ 为本修复阶段产物）

## 0. 修复范围（Human Gate 评审 STATUS=BLOCKED 的五个问题）

| 问题 | 修复 |
|---|---|
| P0-1 VERIFIED_PRO_MAX 被当作语义批准 | §2 身份/结果分离；§3 outcome-aware YELLOW 门 |
| P0-2 Sentinel 只被测试、未被正式 GREEN 门强制 | §7-9 runtime Sentinel Gate |
| P1-1 方法族分类器仅英文 | §15 中英双语分类 |
| P1-2 Risk Card 校验可被绕过 / frozen_mechanical_execution 全局旁路 | §12 fail-closed 校验；§13 移除旁路 |
| P1-3 旧 AUTOPILOT 措辞与通用 Router 冲突 | §19 显式治理优先级 |

**冻结基础设施（不修改）**：deepseek-pro-max、pro_max_review、Phase-A provider 配置、spawn 语义、reasoningEffort=max、Harness core、正式建模代码/结果。Phase A 保持 ACCEPTED。

## 1. Review Identity ≠ Review Outcome（P0-1）

两个独立维度：
- `review_identity_verified`（true/false）：仅证明 fresh_spawn + provider=deepseek-pro-max + model=deepseek-v4-pro + reasoningEffort=max + workspace_delta=0。
- `review_verdict`（PASS / PASS_WITH_CAVEAT / BLOCKED / HUMAN_GATE_REQUIRED）+ `required_actions_closed` + `authority_conflict`：评审结果。

**VERIFIED_PRO_MAX 绝不意味着语义 PASS。**

## 2. YELLOW outcome-aware 门（§3）

```
YELLOW + identity=false                          -> ROUTING_BLOCKED
YELLOW + identity=true + verdict 缺失/未知       -> ROUTING_BLOCKED
YELLOW + identity=true + BLOCKED                 -> ROUTING_BLOCKED
YELLOW + identity=true + HUMAN_GATE_REQUIRED     -> HUMAN_GATE_REQUIRED
YELLOW + identity=true + PASS + actions closed   -> PASS
YELLOW + identity=true + PASS + actions open     -> ROUTING_BLOCKED
YELLOW + identity=true + PASS_WITH_CAVEAT + closed -> PASS（caveat 状态保留记录）
YELLOW + identity=true + PASS_WITH_CAVEAT + open -> ROUTING_BLOCKED
```

## 3. RED Human Gate（§4）

`human_gate_verdict ∈ {PENDING, ACCEPTED, REJECTED}`；仅 ACCEPTED → 正式继续；PENDING → HUMAN_GATE_REQUIRED；REJECTED/未知 → ROUTING_BLOCKED。**Human Gate "发生过" 不等于接受。**

## 4. Formal GREEN Runtime Sentinel Gate（P0-2，§7-9）

- 门输入：`sentinel_required`、`sentinel_identity_verified`、`sentinel_verdict`。
- formal_scope=true ∧ route=GREEN ∧ checkpoint=R4 ⇒ 必须：sentinel_required=true、实际低成本独立 Sentinel 运行存在（identity verified）、sentinel_verdict=AGREE_GREEN；缺失/畸形 → ROUTING_BLOCKED。禁止静默 PASS GREEN。
- Sentinel 用 Flash/E2 基础设施（非 Pro-Max），CLASSIFICATION_AUDITOR_ONLY、只读、不产生子 agent；记录 run id / provider/model / fresh / packet hash / verdict / delta / identity。
- `sentinel_upgrade` **永不降级**（矩阵见 §9 原文）：GREEN+AGREE_YELLOW→YELLOW、GREEN+AGREE_RED→RED、GREEN+RISK_OMISSION/ROUTE_TOO_LOW→YELLOW minimum；YELLOW 不因 AGREE_GREEN 降级；RED 永不动摇；畸形输出 → formal GREEN ROUTING_BLOCKED。
- **不得用合成 parser 测试冒充 runtime 强制**：本修复执行了一个真实 Flash Sentinel（SENTINEL-LIVE-001，child `5562219f-...`，AGREE_GREEN，identity 实测）。

## 5. Risk Card Fail-Closed（P1-2，§12-14）

`validate_card_fail_closed` 在路由计算前强制运行；畸形卡 → `ROUTING_INVALID`（`RiskCardInvalid`），永不能 formal PASS。至少拒绝：risk true 无 evidence；evidence 引用 false 维度（除非 informational）；未知维度；非法 authority state / stage；GREEN 白名单类缺 mechanical evidence；FROZEN/ACCEPTED 依赖类缺 `authority_refs`；机械/语义矛盾字段。

**frozen_mechanical_execution 不再是语义风险全局开关（§13）**：risk 字段表示"未解决的当前风险"；任一语义风险 true → YELLOW（除非 RED 前置规则）。真正冻结的机械任务应：risk 全 false + frozen_mechanical_execution=true + 合法白名单类 + authority_refs。

## 6. Semantic Issue Dedup（§6）

`SemanticIssueStore` 区分 identity 与 resolved，新增 `semantic_status ∈ {OPEN, RESOLVED, BLOCKED, HUMAN_PENDING}`。仅当 identity verified ∧ verdict 为可接受终态 ∧ required_actions_closed=true ∧ contract_hash 未变才可 dedup。BLOCKED 永不被身份验证"解决"；HUMAN_GATE_REQUIRED 无接受证据永不 RESOLVED；PASS_WITH_CAVEAT 在 actions 未闭时保持 OPEN。存储层拒绝把 BLOCKED/HUMAN_GATE_REQUIRED 记为 RESOLVED。

## 7. LIVE-001 证据修复（§5）

已提交的 Pro-Max 评审原文 = **VERDICT: BLOCKED**（不重写）。据此修正：`review_verdict=BLOCKED`、`semantic_status=BLOCKED`（OPEN/DECISION_REQUIRED），旧 `PASS_WITH_CAVEAT/verified` 记录与"已解决"dedup 事件已替换为"BLOCKED 未解决"事件。无需新 Pro-Max 调用。

## 8. 双语方法族分类（P1-1，§15-16）

中英双语模式覆盖全部 16 族（解析解/概率统计/回归预测/时间序列/机器学习/优化/运筹/图网络/离散事件/蒙特卡洛/ODE-PDE/物理/多指标评价/空间GIS/数值计算）。DES 细化：generic "simulation/simulate/仿真" 不再自动归 DES；DES 需要离散事件证据（discrete-event/event-driven/event queue/排队仿真/事件驱动…）。

## 9. Generalization 表述（§18）

`PROJECT_TOKEN_LEAK_GUARD`（原 GENERALIZATION_CHECK）：零匹配只证明"已知当前项目 token 未泄漏进 Universal Core"，不单独证明跨域/跨语言泛化；泛化证据 = 跨域测试 + 中英测试 + 验证族测试。

## 10. 治理优先级（P1-3，§19）

- 实质数学建模任务 GREEN/YELLOW/RED 分类：**MATHEMATICAL_MODELING_ROUTER_V2.1.1 权威**。
- `MODEL_ROUTING_PRO_MAX_V1.0`：仅"HOW VERIFIED_PRO_MAX 被调用/验证"权威。
- `AUTOPILOT-PLAN-V1.1`：阶段推进/预算/停机边界/产物纪律/变更与恢复规则继续管辖；其旧模型风险措辞不覆盖 MMR 分类。
- Human Gate 始终为最终权威。历史不删除，旧路由措辞标记 superseded（AGENTS.md 已落文）。

## 11. 检查器与测试

- 修复检查器 `check_mathematical_modeling_router_v2_1_1.py`：**R-01..R-22 = 22/22 PASS**（全部从 artifact/计算得出）。
- 测试：原 26 跨域测试保留 + 中英分类 + DES 细化 + Sentinel 门负例 + Risk Card fail-closed + outcome-aware 门 + Human Gate 矩阵 + dedup 修复 = **96/96 PASS**。
- V2.1 检查器（MMR-01..16）标记 SUPERSEDED_FOR_ROUTING_GATE，并在新引擎语义下可运行（16/16）。
