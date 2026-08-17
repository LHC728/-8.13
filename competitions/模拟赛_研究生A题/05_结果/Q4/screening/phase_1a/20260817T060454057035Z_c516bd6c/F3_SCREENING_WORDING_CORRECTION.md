# F3 SCREENING WORDING CORRECTION（Human Gate 红线落文）

> 依据：Human Gate 对 Phase 1A F3 结果措辞的重要解释纠正（2026-08-17，Q4 PHASE 1B + FORMAL EVALUATION 执行包）。
> 本 addendum 为**追加修正记录**，不修改任何已冻结 screening 数字；原 `Q4_SCREENING_FACTOR_RANKING.md` 数字保留不可变。

## 原措辞（须替换，禁止再使用）

`Q4_SCREENING_FACTOR_RANKING.md` 中：

> "F3 counterfactual preventive replacement (tau 150/180/210) shows no improvement over the frozen NO_PM_BEFORE_MANDATORY baseline (positive Delta T); NOT a recommendation to change the H1 policy (COUNTERFACTUAL_ONLY)."

「shows no improvement」属被禁止表述（等同「PM 干预无益」）。

## 修正后措辞（本包及后续报告统一使用）

> **F3（preventive replacement threshold，COUNTERFACTUAL_ONLY）**：Phase 1A screening **未观察到 preventive replacement 的明确改善**（tau150：mean ΔT = +11/8 h、95% screening CI [-0.18562, 2.93562] 跨 0；tau180：+29/40 h、CI [-0.447422, 1.897422] 跨 0；tau210：≈+0.480 h、CI [-0.387267, 1.347552] 跨 0）。**点估计为正但 CI 跨 0**——screening 不足以支持「改善」或「恶化」结论；**正式结论待独立 Q4_EVALUATION**。该因素不构成对正式 H1 / NO_PM_BEFORE_MANDATORY 政策的任何变更建议（FROZEN：Q3 正式策略 = H1、K\*=K12 UNCHANGED）。

## 措辞红线（禁止项）

- ❌「PM 干预无益」「已证明不能改善」「提前更换一定更差」
- ❌ 把 screening（CI 跨 0）写成正式负面结论
- ✅「未观察到明确改善；点估计为正但 CI 跨 0；正式结论待独立 Q4_EVALUATION」

## screening 数字（不变，供对照）

| scenario | mean ΔT (h) | 95% screening CI | standardized |
|---|---|---|---|
| F3_TAU150 | 11/8 | [-0.18562, 2.93562] | 0.412344 |
| F3_TAU180 | 29/40 | [-0.447422, 1.897422] | 0.289407 |
| F3_TAU210 | 33213993915376109987/69175290276410818560 | [-0.387267, 1.347552] | 0.259060 |
