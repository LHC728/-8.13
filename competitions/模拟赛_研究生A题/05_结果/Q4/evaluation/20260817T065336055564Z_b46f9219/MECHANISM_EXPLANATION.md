# Q4 MECHANISM EXPLANATION（formal evaluation，mechanism ledger 解释）

> run_id: `20260817T065336055564Z_b46f9219`（Q4_EVALUATION，seed 7，R=128，rep 100..227）
> 本文件为机制账本（mechanism ledger）的解释性说明。**账本不是 T 的加法分解**（并行活动重叠），
> 禁止写 `T = 各组件时间之和`。数字均来自 `Q4_EVALUATION_RESULTS.json / mechanism_ledgers`（128 reps 求和）。
> **HG-Q4-NUMERIC-01 修订**：interaction 解释已修正为方向非对称条件边际结论（§3）；F3/F5 措辞按 HG 批准窄表述（§5）；数值未作任何修改。

## 1. F2（turnover 1.0h → 0.5h complete overlap；dT ≈ −73.89 h，95% CI [−75.10, −72.69]）

- **直接通道 = 台位周转占位减半 + 班外停工大幅下降**：
  - turnover_occupancy：12544 h（baseline）→ 6272 h（F2）＝**恰好减半**（每台周转 1h→0.5h，同槽 0.5+0.5 的重叠运输直接缩短台位占位）。
  - off_shift（班外停工）：48768 h → 23124 h（**−53%**）：0.5h 周转使更多批次能在班内完成全部周转，减少跨班/班末等待。
- E retest / effective / calibration 几乎不变（2292 vs 2292）→ 故障语义、测手行为未受影响；**F2 的收益纯粹来自调度/台位时间**。

## 2. F4-E（duration_E −10% / +10%）

- **非对称（M10：dT ≈ −34.07 h；P10：dT ≈ +18.16 h）已正式验证**，与 screening 方向一致：
  - E effective：37881 → 34093（M10）/ 41669（P10）；E retest：2292 → 2063（M10）/ 2521（P10）。
  - **班界/task-fit 非线性解释（不假设线性）**：E 片段缩短 → 更容易嵌入剩余班窗（off_shift 46596 vs baseline 48768，下降），
    缩短的边际收益被「能完整落班」放大；E 片段延长 → 更频繁跨班界（off_shift 53364，上升），
    且延长幅度被队列耦合放大。**不是简单的 duration×数量线性关系**（M10 效应 ≈ 2×P10 效应，方向也不对称）。
- A/C 的 P10 同向非对称（+15.06 / +13.52 h）与 E 相似：主因是 A/C 片段延长把下游（E 队列）启动整体推迟 + 班界匹配变差；B 影响最小（+0.78 h）。

## 3. Top-2 interaction（F2 × F4-E）——方向非对称的强非加性（HG-Q4-NUMERIC-01 修正后）

- **INT_F2_05_E_M10**：dT ≈ −77.46 h（vs F2 单独 −73.89、E_M10 单独 −34.07）→ I_minus = **+30.50 h**（95% CI [29.45, 31.55]，排除 0）。
- **INT_F2_05_E_P10**：dT ≈ +17.44 h（vs F2 单独 −73.89、E_P10 单独 +18.16）→ I_plus = **+73.17 h**（95% CI [71.80, 74.54]，排除 0）。
- **条件边际（exact）**：
  - `cond_E_M10_given_F2 = ΔT(INT_M10) − ΔT(F2) ≈ **−3.57 h**`：当 turnover 已由 1.0h 改为 0.5h 时，E 缩短 10% 的附加收益从单独约 −34.07 h 降为约 −3.57 h ⇒ **STRONG DIMINISHING BENEFIT（显著边际收益递减）**。
  - `cond_E_P10_given_F2 = ΔT(INT_P10) − ΔT(F2) ≈ **+91.33 h**`：E 增长 10% 的惩罚在 fast-turnover 条件下被**强烈放大**（不是被中和/萎缩）⇒ **STRONG AMPLIFICATION OF PENALTY（显著惩罚放大）**。
- **机械验证**：`I_minus = cond_M10 − standalone_E_M10 = −3.5648 − (−34.0672) = +30.5024`；`I_plus = cond_P10 − standalone_E_P10 = +91.3330 − 18.1640 = +73.1689`（与 accepted 一致，数值容差按报告精度）。
- **冻结解释（HG 批准措辞）**：F2 与 F4-E 存在显著模型内非加性交互，且交互具有**明显方向非对称性**：快周转显著削弱进一步缩短 E 时长的额外收益，但显著放大 E 时长增加的工期惩罚。因此联合措施不能用单因素效应简单相加。
- **禁止表述（原 §3 错误措辞已删除）**：❌「E 时长 ±10% 的边际影响都被吸收/大幅萎缩」；❌「E_P10 的惩罚被几乎完全中和」；❌「快周转使 E 时长不再重要」。
- 账本佐证（非因果分解）：INT_M10 turnover_occ 6272（= F2）、E retest 2063（= E_M10）；INT_P10 off_shift 53268（≈ E_P10 单独 53364）——E 延长在快周转下仍主要由班界承担，且相对 fast-turnover 状态形成 **+91.33 h** 的放大惩罚。

## 4. q/e 语义因素（二级）

- **Q-B（INCOMING_DEFECT_PRESSURE，kernel 冻结 baseline）**：q↑20%（QB_HIGH）→ E retest 2292→2685（+17%）、off_shift 48768→49356 → dT ≈ +3.52 h（CI [2.69, 4.35]）；q↓20%（QB_LOW）→ E retest 2292→1953 → dT ≈ −2.37 h（CI [−3.03, −1.70]）。机制 = **E 重测链 + 班外停工**。
- **Q-A（CALIBRATION_INPUT，kernel 重标定 + q 同变）**：效应比 Q-B 更小（HIGH +1.58 h / LOW −1.19 h）——重标定核（alpha/beta 随 q 重新校准）部分抵消了真实问题率变化：更多真实问题被观测核「预先识别」→ 重测路径变化被压缩。符合「标定输入不确定性」语义。
- **E（E-ERROR_ENVIRONMENT，e 同 scale，kernel 重标定）**：e↓20%（E_LOW）→ E retest 2019（−12%）→ dT ≈ −2.66 h（CI [−3.56, −1.76]）；e↑20%（E_HIGH）→ E retest 2469（+8%）→ dT ≈ +2.20 h（CI [1.28, 3.12]）。机制 = **观测误差率→重测频率→E 路径**。e 阶梯 ±20% 全链可行（e≤2min(q,1−q) 满足），无 clip。

## 5. F3（COUNTERFACTUAL_ONLY）与 F5（MODEL_SEMANTIC_ONLY）

- **F3（HG 批准措辞）**：在三个预注册 counterfactual 预防更换阈值中（tau_PM = 150 / 180 / 210 h），**均未观察到缩短总完成时间的证据**。tau=150 h 的差异仍不明确（95% CI [−0.11, 0.71] 跨 0）；tau=180 h（+0.59 h，CI [0.10, 1.07]）与 tau=210 h（+0.66 h，CI [0.21, 1.10]）表现为小幅延长完成时间。**该结论仅覆盖 {150, 180, 210} h 三个测试阈值，不得推广为所有 preventive replacement 策略必然无效。** Q3 正式策略 = H1 / NO_PM_BEFORE_MANDATORY UNCHANGED。
- **F5（HG 批准窄表述）**：在本次预注册的分段线性 CDF 与常风险率两种故障语义比较下，完成时间差异很小（ΔT ≈ −0.02 h，95% CI [−0.16, 0.12]），**未观察到明确影响**。**这不等于对所有可能寿命分布都具有普遍鲁棒性**（未预注册 equivalence margin，不做等价声明）；仅模型语义敏感性，非现实因果。

## 红线检查

- ❌ 无 `T = 组件时间和` 表述；❌ 无「PM 无益/已证明不能改善/universal dominance」；❌ 无「E ±10% 边际都萎缩/被中和」；❌ 无把模型内敏感性写成现实因果定理；❌ 无「对所有寿命分布普遍鲁棒」等价声明。
- ✅ 全部结论绑定 scenario / dT / CI / 机制账本；✅ F3/F5 authority 标注明确。
