# MATHEMATICAL_MODELING_ROUTER_V2.1.2 — FINAL HARDENING（最终加固版权威）

> **Human Gate: ACCEPTED（2026-08-16）**——Reviewer Verdict: PASS；Phase A: ACCEPTED；Phase B: ACCEPTED；Ending commit `193d3722579a60307ad1969502d4e66d1a67e1c1`；Status: **READY_FOR_GENERAL_MATHEMATICAL_MODELING_AUTOPILOT**。

> 状态：IMPLEMENTED / HUMAN_ACCEPTED（narrow final repair；架构不改、不调用 Pro-Max、不运行 Q3/H2/formal modeling）
> 日期：2026-08-16
> Phase-A accepted：`7f670557f8b6e7787386f10908608eea0327d20e`（UNCHANGED）
> V2.1：`0e8f6612b0274a8e53717f36af23e40701bbc583`（历史）
> V2.1.1：`0db58db0e48331840e4f9288bca4229cc54e8609`（标记 **SUPERSEDED_FOR_FINAL_GATE by V2.1.2**）
> 证据根：`05_结果/governance/model_routing/v2_1_2/`

## 1. authority_conflict 必须 fail-closed（§1，P0）

`route_gate_v2_1_1` 现在消费 `authority_conflict`：
- YELLOW + authority_conflict=true → **HUMAN_GATE_REQUIRED**（任何本可通过的 verdict 均如此；未解决的 authority 冲突不得由 reviewer 自行裁决）。
- PASS + authority_conflict=true 矛盾 → 不能 PASS；PASS_WITH_CAVEAT + authority_conflict=true 也不能 PASS。
- 不变量：PASS/PASS_WITH_CAVEAT 与 authority_conflict 组合永远无法 formal-pass（检查器 F-01/F-02/F-03）。

## 2. Authority-Backed GREEN（§2）

authority 依赖的 GREEN 类（UNDER_FROZEN_EXACT_RULE / UNDER_FROZEN_EXACT_FORMULA / UNDER_FROZEN_CONFIG / PLOT_FROM_FROZEN_DATA_AND_SPEC / REPRODUCE_ACCEPTED_RESULT_WITHOUT_METHOD_CHANGE）现在要求：`authority_state ∈ {FROZEN, HUMAN_ACCEPTED}` **且** `authority_refs` 非空；EXPLORATORY/PROPOSED 卡不得声称 UNDER_FROZEN... 并路由 GREEN —— fail-closed（`RiskCardInvalid`，ROUTING_INVALID）。

## 3. 可解析 Authority Receipt（§3）

Risk Card 新增 `authority_receipts: [{ref, exists, sha256, authority_state}]`。`verify_authority_receipts(card, workspace_root)`：workspace-relative 文件必须存在；记录 sha256 时须与实文件一致；authority_state 须为 FROZEN/HUMAN_ACCEPTED。任意自由文本不算正式 authority 证据。路由计算保持纯函数；formal GREEN Gate/Sentinel receipt 层做存在性验证。合成/非正式单元测试用 fixture（`v2_1_2/fixtures/frozen_solver_fixture_spec.json`，authority_state=FROZEN）。

## 4. Sentinel 运行时身份 Receipt（§5）

`v2_1_2/sentinel_request_header.json`：从**实际已持久化的** Sentinel child session（`5562219f-…`）的 request/header + request/context 事件提取（provider=deepseek-official、model=deepseek-v4-flash、reasoningEffort=high、maxTokens=256000、contextWindow=1e6、fresh、只读工具 read/grep/glob、delta=0）。与 Pro-Max identity 证据同标准；不靠工具配置推断；**未发起任何新模型调用**。旧 SENTINEL-LIVE-001 的 "authority: frozen solver specification v1" 仅作为 runtime-channel 历史证据保留，不声称 authority 验证（§4）。

## 5. Formal GREEN Receipt 强制（§6）

formal GREEN @ R4 门现在消费并检查：`sentinel_required`、`sentinel_identity_verified`、`sentinel_verdict=AGREE_GREEN`、**`authority_receipt_verified=true`**——任一缺失 → ROUTING_BLOCKED。formal checker 层不允许"调用方布尔值单独"充当验证：必须存在 receipt 工件（sentinel_request_header.json + 可解析 authority receipt）才计为 verified（F-09/F-10）。

## 6. BLOCKED Dedup 语义（§7）

`SemanticIssueStore` 分离 `needs_review()` 与 `is_resolved()`：
- BLOCKED + 同 contract + 无新 re-review 条件 → `is_resolved=false` 但 **`needs_review=false`**（保持 BLOCKED、等待决策层，不自动重复 Pro-Max）。
- 仅当：contract 改变 / 新反例 / 新 authority 证据 / checker 矛盾 / required action 状态实质改变 / 新 formal implication / 先前 caveat 变实质时才 re-review。
- RESOLVED 仍要求终态 verdict + actions closed + identity verified；BLOCKED/HUMAN_PENDING 永不能记为 RESOLVED。

## 7. 检查器与测试

- 最终检查器 `check_mathematical_modeling_router_v2_1_2.py`：**F-01..F-15 = 15/15 PASS**（全部从 artifact/计算得出）。
- 测试套件：**103/103 PASS**（新增 authority_conflict 门、authority-backed GREEN、receipt 解析、BLOCKED dedup 细化）。
- V2.1.1 检查器（R-01..22）在新语义下可运行（其 R-04 已按 needs_review/is_resolved 更新）；V2.1 检查器（MMR-01..16）同样保持可运行——二者均标记为历史/superseded。
- 预算：新 Pro-Max 调用 = **0**；新 Flash 调用 = **0**（Sentinel 身份 receipt 从既有 session 提取）。

## 8. 版本与约束

- ROUTER_VERSION = `MMR_V2.1.2`；V2.1.1 标记 **SUPERSEDED_FOR_FINAL_GATE by V2.1.2**（文档/证据保留为历史）。
- Phase-A route/tool/config、Harness core、formal 建模代码/结果：**零修改**。
- 不 squash 历史 commit。
