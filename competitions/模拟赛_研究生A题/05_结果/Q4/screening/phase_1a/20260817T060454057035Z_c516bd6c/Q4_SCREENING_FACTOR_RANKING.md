# Q4 SCREENING MATHEMATICAL EFFECT RANK (screening-only)

| rank | factor | scenario | mean Delta T (h) | SE | 95% screening CI | standardized | sign |
|---|---|---|---|---|---|---|---|
| 1 | F2 | F2_TURNOVER_05 | -1507/20 | 1.758102 | [-79.029707, -71.670293] | -9.583503 | ALL_NEG |
| 2 | F4-E | F4_E_M10 | -7097/200 | 1.476915 | [-38.576183, -32.393817] | -5.372474 | ALL_NEG |
| 3 | F4-C | F4_C_P10 | 159/10 | 0.98832 | [13.831446, 17.968554] | 3.597366 | ALL_POS |
| 4 | F4-E | F4_E_P10 | 6215449104249006633007/345876451382054092800 | 1.558438 | [14.708331, 21.231954] | 2.57838 | ALL_POS |
| 5 | F4-A | F4_A_P10 | 273/20 | 1.357533 | [10.808684, 16.491316] | 2.248368 | ALL_POS |
| 6 | F3 | F3_TAU150 | 11/8 | 0.745638 | [-0.18562, 2.93562] | 0.412344 | MIXED |
| 7 | F4-A | F4_A_M10 | -19/40 | 0.350704 | [-1.209024, 0.259024] | -0.302857 | MIXED |
| 8 | F3 | F3_TAU180 | 29/40 | 0.560163 | [-0.447422, 1.897422] | 0.289407 | MIXED |
| 9 | F3 | F3_TAU210 | 33213993915376109987/69175290276410818560 | 0.414433 | [-0.387267, 1.347552] | 0.25906 | MIXED |
| 10 | F4-C | F4_C_M10 | -1/2 | 0.474342 | [-1.492797, 0.492797] | -0.235702 | MIXED |
| 11 | F4-B | F4_B_M10 | -1/50 | 0.02 | [-0.06186, 0.02186] | -0.223607 | MIXED |
| 12 | F4-B | F4_B_P10 | 1/50 | 0.02 | [-0.02186, 0.06186] | 0.223607 | MIXED |
| 13 | F5 | F5_CONSTANT_HAZARD | 3/5 | 0.6 | [-0.6558, 1.8558] | 0.223607 | MIXED |

> SCREENING_ONLY / NON_FINAL_INFERENCE. F3 rows are COUNTERFACTUAL_ONLY
> (HG-Q4-F3-01); F5 row is MODEL_SEMANTIC_ONLY.

## PRELIMINARY MANAGEMENT NOTES (separate from mathematical rank)
- F2 (turnover 1.0h -> 0.5h overlap) has the largest mathematical effect; management implementation (two-bay overlap logistics) carries its own cost/constraints.
- F4-E (E-duration -10%) second-largest; E 是整机检测（A/B/C 通过后），缩短 E 直接减末端路径。
- F3 counterfactual preventive replacement (tau 150/180/210) shows no improvement over the frozen NO_PM_BEFORE_MANDATORY baseline (positive Delta T); NOT a recommendation to change the H1 policy (COUNTERFACTUAL_ONLY).
- F5 constant-hazard semantic sensitivity is small; model-semantic only.
> 数学影响排序 ≠ 现实实施优先级（须另行考虑可控性/代价/约束）。
