# FROZEN AUTHORITY ADDENDUM — HG-Q4-F3-01

> 性质：**追加**（additive Human Gate addendum）到 Q4 实验设计口径；**不重写历史问题契约**。
> 日期：2026-08-17；来源：Human Gate（Q4/G6 BOOTSTRAP 设计审查 BLOCKED 后的裁决）。
> 状态：**HUMAN GATE 裁决 = 冻结授权（权威）**。

## 1. 背景

Q4/G6 实验设计审查（Pro-Max 2026-08-17）发现：一级因素 F3（preventive replacement threshold）无法在冻结的
NO_PM_BEFORE_MANDATORY H1 policy family 内定义（任何 τ<240 都是 mandatory 前的 PM，即评估冻结候选政策集之外的策略）→
`authority_conflict=true` → HUMAN_GATE_REQUIRED（RA1）。

## 2. 裁决内容（RA1 = OPTION B / ACCEPTED）

**F3 = AUTHORIZED_AS_HYPOTHETICAL_COUNTERFACTUAL_SENSITIVITY**

### F3 may（允许）：

1. 作为**模型内 what-if 因素**改变预防更换阈值；
2. 计算相对于**正式 H1 baseline** 的 **paired Delta T**；
3. 参与 **Q4 数学因素影响排序**；
4. 支撑**有条件的管理建议**（明确模型内收益与实施约束）。

### F3 may NOT（禁止）：

1. **不得 reopen Q3 policy selection**；
2. **不得替换 H1**；
3. **不得改变 K\***；
4. **不得宣称「PM beats H1」**；
5. **不得宣称新最优政策**；
6. **不得成为 H2'**；
7. **不得追溯修改 Q3 结论**。

## 3. 冻结不变项

- Q3 formal strategy = **H1 / NO_PM_BEFORE_MANDATORY**（UNCHANGED）
- Q3 K\* = **K12**（UNCHANGED；范围 = 七个 K + 冻结 H1 policy set）
- H2 = FROZEN_HISTORICAL_CHALLENGER（UNCHANGED）

## 4. 引用与登记

- Pro-Max 设计审查：`05_结果/governance/model_routing/v2_1_2/p3_requal_pro_max/pro_max_review_q4_design.txt`（BLOCKED，RA1）。
- Risk Card：`05_结果/governance/model_routing/v2_1_2/q4_design_risk_card.json`（authority_conflict = RESOLVED_BY_HUMAN_GATE；required_actions_closed=true）。
- Q4 spec：`08_项目管理/任务包/Q4_G6_EXPERIMENT_SPEC_DRAFT.md`（F3 = AUTHORIZED，含 may / may NOT 边界）。
- 本裁决登记：`CHANGELOG.md`（2026-08-17 / HG-Q4-F3-01）。
