# Q4 FINAL MANAGEMENT RECOMMENDATIONS（paper-facing DRAFT；MODEL-INTERNAL）

> 状态：**NUMERIC_ACCEPTED / SEMANTIC_REVIEW_PENDING / DRAFT_FOR_HUMAN_GATE**。
> 每条绑定 factor_id / scenario_id / ΔT / 95% CI / effect rank；均为**冻结模型世界内（H1 / NO_PM / K12）的模型内敏感性，不是现实因果定理**。
> 数学影响排序 ≠ 管理实施优先级。

## R1. F2 — turnover 0.5h overlap（rank 1 by |std| = 10.74；F2_TURNOVER_05）

- 模型内收益：ΔT ≈ **−73.89 h**，95% CI [−75.10, −72.69]。
- **实现表述（HG 修正）**：若现实中能够使运出与运入过程**充分重叠**，将等效周转占位由 1.0 h 降至 0.5 h，模型内完成时间显著下降。**具体工程实现方式及成本不在本模型内**；例如可能需要额外物流/缓冲资源，具体方案需工程评估。**不得把「两槽位物流」等某一工程方案写成题面事实。**

## R2. F4-E — E-duration −10%（rank 2 by |std| = 6.13；F4_E_M10）

- 单独收益：ΔT ≈ **−34.07 h**，95% CI [−35.04, −33.10]。
- **联合建议（HG 修正）**：如果已实现 turnover = 0.5h，E 再缩短 10% 的**条件边际收益仅约 −3.57 h**。
  ⇒ **E 提速在原 baseline 下具有明显独立价值，但在 fast-turnover 已实施后，其附加收益显著下降。**

## ⚠ NEW INTERACTION WARNING（HG §3；重要管理含义之一，MODEL-INTERNAL）

- 如果已经实施 fast-turnover（turnover = 0.5h），则 **E 工序时长增加 10% 会使完成时间相对于 fast-turnover 状态增加约 +91.33 h**。
- **条件边际 direct paired CI（RA-S1；R=128，rep 100..227，t_{0.975,127}=1.9793；独立于 interaction-contrast CI，不得混用）**：
  - `cond_E_M10_given_F2`：mean = **−3.5648 h**，SE = 0.2336，95% CI = **[−4.027, −3.103]**，half-width = 0.4623（paired：T(INT_M10) − T(F2) per rep）。
  - `cond_E_P10_given_F2`：mean = **+91.3330 h**，SE = 0.5599，95% CI = **[90.225, 92.441]**，half-width = 1.1083（paired：T(INT_P10) − T(F2) per rep）。
  - **注意**：I_minus / I_plus 的 CI 是 **interaction-contrast CI**（另一组 paired CI：`T(INT) − T(F2) − T(E级) + T(base)`）；**conditional-margin CI 与 interaction-contrast CI 不得混用**。
- ⇒ **快周转方案对 E 工序时长恶化更加敏感；实施快周转后必须避免 E 工序能力退化**（如设备降速、节拍劣化、工序时间上行）。
- 限定：MODEL-INTERNAL，不是现实因果定理。

## R3（反向警示）F4-A / F4-C duration +10%（rank 3/4）

- 模型内 ΔT ≈ +15.06 h（CI [14.12, 16.01]）/ +13.52 h（CI [12.44, 14.60]）→ 避免 A/C 检测时长上行 10%。
- A/C 缩短的边际收益小（M10：−0.38 / −0.29 h）→ 上行惩罚大、下行收益小（非对称）。

## R4. q/e 输入因素（风险提示，非管理杠杆）

- **Q-B（incoming defect pressure，rank 5）**：本实验为 **q_A/q_B/q_C/q_D joint proportional scale = 0.8 / 1.2（四个真实问题率同乘同一比例，不是单独一个 q）**：↑20% → +3.52 h（CI [2.69, 4.35]）；↓20% → −2.37 h（CI [−3.03, −1.70]）。用于描述上游来料质量变化风险；**不得称为单纯「调 q 就能降低 T」**。
- **e（operator-error environment，rank 6）**：本实验为 **e_A/e_B/e_C/e_E joint proportional scale = 0.8 / 1.2（四个测手差错率同乘同一比例，不是单独一个测手参数）**：↓20% → −2.66 h（CI [−3.56, −1.76]）；↑20% → +2.20 h。可作为质量/测试管理风险因素；**不把 alpha/beta 拆成独立控制变量**。
- **Q-A（calibration-input uncertainty，rank 8）**：在本次联合重标定链下，Q-A 的工期响应小于 Q-B（HIGH +1.58 / LOW −1.19 h）；这一结果与观测核随 q 重标定产生补偿作用的解释相一致，**但本实验未单独识别各传播通道的独立贡献**；**不是可直接控制的企业管理杠杆**。

## R5. F3 — preventive-replacement threshold（rank 9；COUNTERFACTUAL_ONLY）

- **不建议改变正式 H1 / NO_PM_BEFORE_MANDATORY 政策**。
- 三个预注册阈值均未观察到缩短总完成时间的证据（tau150 不明确；tau180/210 小幅延长 +0.59/+0.66 h）。
- 结论仅覆盖 {150, 180, 210} h；**不得推广为所有 preventive replacement 策略必然无效**。
- Q3 正式策略 = H1、K\*=K12 **UNCHANGED**。

## R6. F5 — failure-semantics alternative（rank 10；MODEL_SEMANTIC_ONLY）

- 在分段线性 CDF 与常风险率两种故障语义比较下，完成时间差异很小（−0.02 h，CI [−0.16, 0.12]），未观察到明确影响。
- **不宣称对所有可能寿命分布普遍鲁棒**（无 equivalence margin 预注册，不做等价声明）。

## 交互联合决策要点（MODEL-INTERNAL）

- F2 × F4-E 模型内强非加性 + **方向非对称**：
  - 已 fast-turnover 后：E 提速附加价值低（条件边际 ≈ −3.57 h，95% CI [−4.027, −3.103]），但 **E 时长恶化惩罚被放大**（条件边际 ≈ +91.33 h，95% CI [90.225, 92.441]）。
  - 联合实施时收益不可线性相加；**在本次已测试模型情景内，实施快周转时同步维持 E 工序节拍是更稳妥的组合**（快周转 + E 工序能力退化是高风险组合）。**禁止 universal robustness 表述**。
