# Q4 FINAL NUMERIC RESULT（paper-facing；NUMERIC_ACCEPTED）

> 状态：**NUMERIC_ACCEPTED / SEMANTIC_REVIEW_PENDING**（**NOT READY_FOR_PAPER**；final Pro-Max semantic review + Human Gate 前不得进入论文）。
> 依据：Human Gate HG-Q4-NUMERIC-01（accepted HEAD `8096d80`）。
> accepted evaluation root：`05_结果/Q4/evaluation/20260817T065336055564Z_b46f9219/`。
> 设计：q4_evaluation / master_seed=7 / R=128 / rep 100..227；two-stage：stage-1（R=64）max half-width = 2.0930 h > 2.0 h → 全 scenarios 统一扩 R=128；final max half-width < 2.0 h。
> **筛选域数据（q4_screening rep 0..39）未混入任何 final CI；Q4_EVALUATION 是正式 CI 唯一证据源。**

## 主情景 paired ΔT vs Q4_BASELINE（95% CI；正式）

| scenario | factor | mean ΔT (h) | 95% CI (h) | half-width | |std| | direction |
|---|---|---|---|---|---|---|
| F2_TURNOVER_05 | F2 (turnover 0.5h overlap) | −73.893 | [−75.097, −72.690] | 1.204 | 10.74 | 缩短 |
| F4_E_M10 | F4-E (E duration −10%) | −34.067 | [−35.039, −33.095] | 0.972 | 6.13 | 缩短 |
| F4_E_P10 | F4-E (E duration +10%) | +18.164 | [17.105, 19.223] | 1.059 | 3.00 | 延长 |
| F4_A_P10 | F4-A (A duration +10%) | +15.061 | [14.116, 16.006] | 0.945 | 2.79 | 延长 |
| F4_C_P10 | F4-C (C duration +10%) | +13.520 | [12.440, 14.599] | 1.079 | 2.19 | 延长 |
| QB_HIGH | Q-B (incoming defect pressure ×1.2) | +3.518 | [2.686, 4.350] | 0.832 | 0.74 | 延长 |
| E_LOW | operator-error env (e) ×0.8 | −2.661 | [−3.561, −1.762] | 0.900 | 0.52 | 缩短 |
| QB_LOW | Q-B (incoming defect pressure ×0.8) | −2.366 | [−3.034, −1.697] | 0.668 | 0.62 | 缩短 |
| E_HIGH | operator-error env (e) ×1.2 | +2.197 | [1.278, 3.116] | 0.919 | 0.42 | 延长 |
| QA_HIGH | Q-A (calibration input ×1.2) | +1.583 | [0.632, 2.535] | 0.952 | 0.29 | 延长 |
| QA_LOW | Q-A (calibration input ×0.8) | −1.195 | [−2.159, −0.230] | 0.965 | 0.22 | 缩短 |
| F3_TAU150 | F3 (tau_PM=150, COUNTERFACTUAL_ONLY) | +0.300 | [−0.106, 0.707] | 0.406 | 0.13 | 不明确 |
| F3_TAU180 | F3 (tau_PM=180, COUNTERFACTUAL_ONLY) | +0.587 | [0.099, 1.075] | 0.488 | 0.21 | 小幅延长 |
| F3_TAU210 | F3 (tau_PM=210, COUNTERFACTUAL_ONLY) | +0.657 | [0.211, 1.103] | 0.446 | 0.26 | 小幅延长 |
| F4_B_P10 | F4-B (B duration +10%) | +0.782 | [0.390, 1.174] | 0.392 | 0.35 | 延长 |
| F4_A_M10 | F4-A (A duration −10%) | −0.380 | [−0.596, −0.164] | 0.216 | 0.31 | 缩短 |
| F4_C_M10 | F4-C (C duration −10%) | −0.289 | [−0.531, −0.047] | 0.242 | 0.21 | 缩短 |
| F4_B_M10 | F4-B (B duration −10%) | +0.030 | [−0.056, 0.117] | 0.086 | 0.06 | 不明确 |
| F5_CONSTANT_HAZARD | F5 (failure semantics, MODEL_SEMANTIC_ONLY) | −0.020 | [−0.158, 0.119] | 0.139 | 0.03 | 不明确 |

- 数值逐项与 accepted `Q4_EVALUATION_RESULTS.json / scenario_stats` 一致（机械核对见 `Q4_FINAL_PROVENANCE.json`）。
- **F1（K）＝ REUSED_ACCEPTED_FORMAL_EVIDENCE**（Q3 accepted 七 K；k\*=K12 为「七 K + 冻结 H1 政策集」内 strong winner；不重跑、不混入 Q4 CI）。
- **level 说明（RA-S3B/C）**：Q-B 的「×0.8 / ×1.2」指 **q_A/q_B/q_C/q_D joint proportional scale**（四个真实问题率同乘同一比例，不是单独一个 q）；e 因子的「×0.8 / ×1.2」指 **e_A/e_B/e_C/e_E joint proportional scale**（四个测手差错率同乘同一比例，不是单独一个测手参数）。

## F3 正式措辞（COUNTERFACTUAL_ONLY；HG 批准措辞）

> 在三个预注册 counterfactual 预防更换阈值（tau_PM = 150 / 180 / 210 h）中，**均未观察到缩短总完成时间的证据**。
> tau=150 h 的差异仍不明确（95% CI 跨 0）；tau=180 h 与 tau=210 h 表现为小幅延长完成时间（+0.59 / +0.66 h，CI 不含 0 但幅度 <1.1 h）。
> **该结论仅覆盖 {150, 180, 210} h 三个测试阈值，不得推广为所有 preventive replacement 策略必然无效。**
> Q3 正式策略 = H1 / NO_PM_BEFORE_MANDATORY（UNCHANGED）；K\*=K12（UNCHANGED）。

## F5 正式措辞（MODEL_SEMANTIC_ONLY；HG 批准窄表述）

> 在本次预注册的分段线性 CDF 与常风险率两种故障语义比较下，完成时间差异很小（ΔT ≈ −0.02 h，95% CI [−0.16, 0.12]），**未观察到明确影响**。
> **这不等同于对所有可能寿命分布都具有普遍鲁棒性**（未预注册 equivalence margin，不宣称等价）。
