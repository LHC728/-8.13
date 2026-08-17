# Q4 FINAL MECHANISM NARRATIVE（paper-facing）

> 状态：**NUMERIC_ACCEPTED / SEMANTIC_REVIEW_PENDING**。
> 机制账本（mechanism ledger，128 reps 求和）来自 accepted `Q4_EVALUATION_RESULTS.json / mechanism_ledgers`。
> **账本不是 T 的加法分解**（并行活动重叠）——禁止 `T = 组件时间之和` 表述。

## 1. F2（turnover 1.0h → 0.5h overlap；ΔT ≈ −73.89 h）

- **台位周转占位减半**：turnover_occupancy 12544 → 6272 h（sum over 128 reps，恰好减半）。
- **班外停工大幅下降**：off_shift 48768 → 23124 h（−53%）：0.5h 重叠运输使更多周转能在班内完成，减少跨班/班末等待。
- E retest / effective / calibration 基本不变 → 收益来自调度/台位时间通道，不是故障或测手行为变化。
- 注：ΔT −73.89 h 与 turnover_occupancy 直接减半的账本通道**方向一致**，但账本仍**不是** T 的线性分解。

## 2. F4-E（E-duration −10% / +10%）

- 非对称正式验证：M10 −34.07 h vs P10 +18.16 h。
- 机制通道：E effective 37881 → 34093（M10）/ 41669（P10）；E retest 2292 → 2063（M10）/ 2521（P10）；off_shift 48768 → 46596（M10）/ 53364（P10）。
- 解释（非线性，不假设线性）：E 片段缩短 → 更容易嵌入剩余班窗（task-fit），边际收益被「能完整落班」放大；E 片段延长 → 更频繁跨班界 + 队列耦合放大惩罚。A/C 的 P10 同向非对称同理（+15.06 / +13.52 h）；B 影响最小（+0.78 h）。

## 3. Top-2 interaction（F2 × F4-E）——方向非对称的强非加性（HG 修正后）

- 条件边际（exact）：
  - `cond_E_M10_given_F2 ≈ **−3.57 h**`（E 缩短 10% 在 fast-turnover 下的附加收益；单独 ≈ −34.07 h → 显著递减）
  - `cond_E_P10_given_F2 ≈ **+91.33 h**`（E 增长 10% 在 fast-turnover 下的惩罚；单独 ≈ +18.16 h → 显著放大）
- 机械验证：`I_minus = cond_M10 − standalone_M10 = +30.50 h`；`I_plus = cond_P10 − standalone_P10 = +73.17 h`（与 accepted 一致）。
- 冻结解释：**快周转显著削弱「进一步缩短 E 时长」的额外收益，但显著放大「E 时长增加」的工期惩罚**——联合措施不能用单因素效应简单相加（模型内，禁现实因果）。

## 4. q/e 二级语义因素

- **Q-B（incoming defect pressure，kernel 冻结 baseline；q_A/q_B/q_C/q_D joint proportional scale = 0.8 / 1.2，不是单独一个 q）**：q↑20% → E retest 2292→2685（+17%）→ ΔT ≈ +3.52 h；q↓20% → E retest 2292→1953 → ΔT ≈ −2.37 h。机制 = E 重测链 + 班外停工。用于描述上游来料质量变化风险。
- **Q-A（calibration-input uncertainty，kernel 重标定 + q 同变）**：在本次联合重标定链下，**Q-A 的工期响应小于 Q-B**（HIGH +1.58 / LOW −1.19 h vs Q-B HIGH +3.52 / LOW −2.37 h）；这一结果与观测核随 q 重标定产生补偿作用的解释相一致，**但本实验未单独识别各传播通道的独立贡献**（不得声称 mechanism independently identified）。仅标定输入不确定性，非管理杠杆。
- **e（operator-error environment，e_A/e_B/e_C/e_E joint proportional scale = 0.8 / 1.2，不是单独一个测手参数；kernel 重标定）**：e↓20% → E retest 2019（−12%）→ ΔT ≈ −2.66 h；e↑20% → E retest 2469 → ΔT ≈ +2.20 h。机制 = 观测误差率→重测频率→E 路径。e 阶梯 ±20% 全链可行（e ≤ 2min(q,1−q)），无 clip；不把 alpha/beta 拆成独立控制变量。

## 5. F3（COUNTERFACTUAL_ONLY）与 F5（MODEL_SEMANTIC_ONLY）

- F3：三个预注册阈值均未观察到缩短总完成时间的证据（tau150 不明确，CI 跨 0；tau180/210 小幅延长 +0.59/+0.66 h）；结论仅覆盖 {150,180,210} h，不得推广。
- F5：分段线性 vs 常风险率两种故障语义下完成时间差异很小（−0.02 h，CI [−0.16, 0.12]），未观察到明确影响；不宣称对所有寿命分布普遍鲁棒。

## 红线检查

- ✅ 无 `T = 组件时间和`；✅ 无「PM 无益/已证明不能改善」；✅ 无「E ±10% 边际都萎缩/被中和」；✅ 无现实因果断言。
