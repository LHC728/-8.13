# INVALIDATION_REPORT_V2.1.1 — Phase-B V2.1 路由语义失效声明

> 日期：2026-08-16
> 依据：Human Gate 对 Phase B V2.1 的独立评审（STATUS = BLOCKED；P0-1/P0-2/P1-1/P1-2/P1-3）
> 修复版权威：`08_项目管理/模型路由/MATHEMATICAL_MODELING_ROUTER_V2.1.1.md`

## 1. 失效范围（被本修复取代的 PASS 声明）

| 项 | V2.1 声明 | 失效原因 | 替代 |
|---|---|---|---|
| Phase-B V2.1 PASS claim | PASS | P0-1：VERIFIED_PRO_MAX 被当作语义批准；P0-2：Sentinel 未进入正式 GREEN 门 | V2.1.1 门语义（identity/outcome 分离 + runtime Sentinel Gate） |
| MMR checker PASS claim（MMR-01..16） | 16/16 PASS | 旧门语义（verified_pro_max bool、human_gate_done bool、无 sentinel 门、dedup 把身份验证当解决） | `check_mathematical_modeling_router_v2_1_1.py` R-01..22 |
| semantic issue dedup evidence | SAMPLING-LIVE-001 记 PASS_WITH_CAVEAT/verified；LIVE-002 声称"已解决" | 与已提交评审原文 VERDICT: BLOCKED 冲突；BLOCKED 永不能被身份验证解决 | `v2/semantic_issues.json`（BLOCKED/OPEN）+ 事件流修正 |
| V2.1 方法族分类 | English-only；generic simulation → DES | P1-1/P1-2（§15/§16） | 双语分类 + DES 细化（96/96 测试） |
| V2.1 Risk Card 校验 | 软校验（可忽略） | P1-2（§12）：可被绕过导致 under-route | fail-closed `validate_card_fail_closed` → ROUTING_INVALID |
| V2.1 frozen-mechanical 语义 | `any risk ∧ NOT frozen_mechanical → YELLOW`（单布尔全局旁路） | P1-2（§13） | risk 字段 = 未解决当前风险；任一 risk true → YELLOW；矛盾卡拒绝 |

## 2. 不失效（明确保留）

- **Phase-A**：deepseek-pro-max route、pro_max_review tool、spawn 语义、reasoningEffort=max、provider 配置、Phase-A evidence（`7f670557…`）——UNCHANGED。
- **Q3 formal modeling evidence、H1/H2 历史结果、无关仿真输出**——未触碰。
- **Harness core**——未修改。
- V2.1 文档/证据/检查器文件本身——保留为历史实现（标记 SUPERSEDED_FOR_ROUTING_GATE）。

## 3. 修复验证（替代证据）

- 修复检查器 R-01..R-22 = **22/22 PASS**（`v2_1_1/repair_checker_result.json`）。
- 测试套件 = **96/96 PASS**（跨域 26 + 双语/DES/门/校验新增）。
- 真实 Flash Sentinel：SENTINEL-LIVE-001（child `5562219f-…`）AGREE_GREEN + identity 实测（`v2_1_1/sentinel_live_result.json`）。
- LIVE-001 评审原文保留（VERDICT: BLOCKED），派生证据已修正（identity/outcome 分离）。
- A1 replay（committed evidence）与 Phase-A ROUTE-01..12 不受影响（Phase A UNCHANGED）。
