# Q4 FINAL FACTOR TABLE（paper-facing；rank by |standardized effect|）

> 状态：**NUMERIC_ACCEPTED / SEMANTIC_REVIEW_CLOSED / READY_FOR_PAPER**（HG-Q4-REVIEWER-01 caveats CLOSED；HG-Q4-FINAL-SEAL-01 = FINAL PASS / ACCEPTED）。
> 排序量（冻结规则）：`factor_score = max(|standardized_effect|)` per factor（main scenarios only；F1 = REUSED_ACCEPTED_FORMAL_EVIDENCE 不参与 Q4 排序）。
> **表头优先写「rank by |standardized effect|」，方向符号另列**（避免 `-10.74 > -6.13 > +2.79` 的歧义写法）。

| rank | factor (display) | machine/scenario id | \|std effect\| | direction (max-scenario) | max-scenario mean ΔT (h) | 95% CI (h) |
|---|---|---|---|---|---|---|
| 1 | F2 — turnover 0.5h overlap | F2_TURNOVER_05 | 10.74 | 缩短 | −73.893 | [−75.097, −72.690] |
| 2 | F4-E — E-duration | F4_E_M10 | 6.13 | 缩短 | −34.067 | [−35.039, −33.095] |
| 3 | F4-A — A-duration | F4_A_P10 | 2.79 | 延长 | +15.061 | [14.116, 16.006] |
| 4 | F4-C — C-duration | F4_C_P10 | 2.19 | 延长 | +13.520 | [12.440, 14.599] |
| 5 | Q-B — incoming defect pressure | QB_HIGH | 0.74 | 延长 | +3.518 | [2.686, 4.350] |
| 6 | e — operator-error environment（测手差错环境 e） | E_LOW | 0.52 | 缩短 | −2.661 | [−3.561, −1.762] |
| 7 | F4-B — B-duration | F4_B_P10 | 0.35 | 延长 | +0.782 | [0.390, 1.174] |
| 8 | Q-A — calibration-input uncertainty | QA_HIGH | 0.29 | 延长 | +1.583 | [0.632, 2.535] |
| 9 | F3 — preventive-replacement threshold (COUNTERFACTUAL_ONLY) | F3_TAU210 | 0.26 | 小幅延长 | +0.657 | [0.211, 1.103] |
| 10 | F5 — failure-semantics alternative (MODEL_SEMANTIC_ONLY) | F5_CONSTANT_HAZARD | 0.03 | 不明确 | −0.020 | [−0.158, 0.119] |

## 显示名约定

- **机器 ID「E」= 综合测试工序（process E）**；**因子「e」= operator-error environment（测手差错环境 e）**。论文 facing 表格中 e 因子一律写「operator-error environment (e)」/「测手差错环境 e」，避免与工序 E 混淆；机器/工序 ID 保持 E。
- Q-A 只解释为 **calibration-input uncertainty（标定输入不确定性）**，不是可直接控制的企业管理杠杆。
- Q-B 解释为 **incoming defect pressure（上游来料质量问题率）**：本实验为 **q_A/q_B/q_C/q_D joint proportional scale = 0.8 / 1.2**（四个真实问题率同乘同一比例），**不是单独一个 q**；可用于描述来料质量变化风险，不得写成「调 q 就能降低 T」。
- e 解释为 **measurement-error environment（测量误差环境）**：本实验为 **e_A/e_B/e_C/e_E joint proportional scale = 0.8 / 1.2**（四个测手差错率同乘同一比例），**不是单独一个测手参数**；可作为质量/测试管理风险因素；**不得把 alpha/beta 拆成独立控制变量**。

## 排序 scope（RA-S3D）

> **本排序仅在本次预注册 factor levels / perturbation range 内成立，不是因素全参数域的全局敏感度排序。**

## 数学影响排序 ≠ 管理实施优先级

本表为模型内数学影响排序；管理实施优先级见 `Q4_FINAL_MANAGEMENT_RECOMMENDATIONS.md`（另列可控性/代价/约束）。
