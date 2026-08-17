# Q4 FINAL INTERACTION TABLE（paper-facing；F2 × F4-E）

> 状态：**NUMERIC_ACCEPTED / SEMANTIC_REVIEW_PENDING**。
> 数值与 accepted `Q4_EVALUATION_RESULTS.json` 一致，**未修改**；本表只呈现修正后的条件边际解释（HG-Q4-NUMERIC-01 §2）。

## 2×3 设计（q4_evaluation，seed 7，R=128，rep 100..227；paired ΔT vs baseline）

| E-duration level | turnover 1.0h (baseline) | turnover 0.5h (F2) |
|---|---|---|
| E baseline | 0（参考） | **−73.893 h** [−75.097, −72.690] |
| E −10% | **−34.067 h** [−35.039, −33.095] | **−77.458 h** [−78.657, −76.259] |
| E +10% | **+18.164 h** [17.105, 19.223] | **+17.440 h** [16.389, 18.490] |

## 条件边际效应（exact Fraction 算术；≈ 值按报告精度）

- **E −10% 在 fast-turnover 下的条件边际**：`cond_M10 = ΔT(INT_M10) − ΔT(F2) = −77.458 − (−73.893) ≈ **−3.57 h**`
  - E 缩短 10% 的附加收益：单独 ≈ −34.07 h → fast-turnover 条件下 ≈ −3.57 h ⇒ **STRONG DIMINISHING BENEFIT（显著边际收益递减）**。
- **E +10% 在 fast-turnover 下的条件边际**：`cond_P10 = ΔT(INT_P10) − ΔT(F2) = +17.440 − (−73.893) ≈ **+91.33 h**`
  - E 增长 10% 的惩罚：在 fast-turnover 条件下被**强烈放大** ⇒ **STRONG AMPLIFICATION OF PENALTY（显著惩罚放大）**。

## 交互对照（replicate-level paired；95% CI）

| contrast | 公式（逐 rep） | mean (h) | 95% CI (h) | 结论 |
|---|---|---|---|---|
| I_minus | `T(INT_M10) − T(F2) − T(E_M10) + T(base)` | **+30.50** | [29.45, 31.55] | 排除 0 → 模型内非加性交互 |
| I_plus | `T(INT_P10) − T(F2) − T(E_P10) + T(base)` | **+73.17** | [71.80, 74.54] | 排除 0 → 模型内非加性交互 |

机械验证（exact）：`I_minus = cond_M10 − standalone_E_M10 = −3.5648 − (−34.0672) = +30.5024`；`I_plus = cond_P10 − standalone_E_P10 = +91.3330 − 18.1640 = +73.1689`（与 accepted 一致）。

## 条件边际 direct paired CI（RA-S1；独立于 interaction-contrast CI）

从 accepted `T_by_rep.json` 逐 replicate 计算（R=128，rep 100..227；t_{0.975,127}=1.9793，与正式 evaluation 相同）：

| 条件边际 | 逐 rep 定义 | mean (h) | SE | 95% CI (h) | half-width |
|---|---|---|---|---|---|
| cond_E_M10_given_F2 | `T(INT_F2_05_E_M10, r) − T(F2_TURNOVER_05, r)` | **−3.5648** | 0.2336 | **[−4.0271, −3.1025]** | 0.4623 |
| cond_E_P10_given_F2 | `T(INT_F2_05_E_P10, r) − T(F2_TURNOVER_05, r)` | **+91.3330** | 0.5599 | **[90.2247, 92.4412]** | 1.1083 |

- mean 与 accepted exact 值一致（cond_M10 = INT_M10 − F2 = −3.5648；cond_P10 = INT_P10 − F2 = +91.3330）。
- **重要（不得混用）**：I_minus / I_plus 的 CI 是 **interaction-contrast CI**（另一组 paired CI：`T(INT) − T(F2) − T(E 级) + T(base)`，用于检验非加性交互）；**conditional-margin CI** 是「已 fast-turnover 条件下 E 时长扰动的直接 paired 效应 CI」。两组 CI 语义不同，**不得混用**（例如不得用 I_plus CI [71.80, 74.54] 代替 cond_P10 CI [90.22, 92.44]，反之亦然）。

## 冻结解释（HG 批准措辞；替换一切旧「±10% 边际都萎缩/被中和」表述）

> **F2 与 F4-E 存在显著模型内非加性交互，且交互具有明显方向非对称性：**
> **快周转显著削弱进一步缩短 E 时长的额外收益，但显著放大 E 时长增加的工期惩罚。**
> **因此联合措施不能用单因素效应简单相加。**

禁止表述：❌「turnover 0.5h 后 E 时长 ±10% 的边际影响都大幅萎缩」；❌「E_P10 惩罚被中和」；❌「E 正负扰动都变得不重要」；❌「快周转使 E 时长不再重要」。

## 管理含义（MODEL-INTERNAL）

- 快周转方案对 E 工序时长恶化**更加敏感**：若已实施 fast-turnover，E 工序时长 +10% 会使完成时间相对 fast-turnover 状态增加约 **+91.33 h**。
- 实施快周转后必须避免 E 工序能力退化（如设备降速、节拍劣化、工序时间上行）。
- 以上均为模型内结论，不是现实因果定理。
