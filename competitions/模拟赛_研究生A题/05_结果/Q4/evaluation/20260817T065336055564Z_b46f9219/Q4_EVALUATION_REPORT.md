# Q4 FORMAL EVALUATION RESULT (Q4_EVALUATION, seed 7)

- run_id: `20260817T065336055564Z_b46f9219`
- R_final = 128 (replicate 100..227); two-stage expansion: TRIGGERED
- target 95% CI half-width = 2.0 h; max half-width at stage 1 = 2.0930 h
- F1 (K) = REUSED_ACCEPTED_FORMAL_EVIDENCE (Q3 accepted; separate).

## Main-scenario paired Delta T vs Q4_BASELINE (95% CI)

| scenario | factor | mean dT (h) | 95% CI | half-width | std | sign |
|---|---|---|---|---|---|---|
| F2_TURNOVER_05 | F2 | -16357056701513088058783/221360928884514619392 | [-75.0966, -72.6897] | 1.2035 | -10.7419 | ALL_NEG |
| F3_TAU150 | F3 | 44304141664390327241/147573952589676412928 | [-0.1062, 0.7066] | 0.4064 | 0.1292 | MIXED |
| F3_TAU180 | F3 | 259733790499924149083/442721857769029238784 | [0.0987, 1.0747] | 0.4880 | 0.2103 | MIXED |
| F3_TAU210 | F3 | 290862671124309017435/442721857769029238784 | [0.2107, 1.1032] | 0.4463 | 0.2576 | MIXED |
| F4_A_M10 | F4-A | -56134990120988054059/147573952589676412928 | [-0.5963, -0.1644] | 0.2160 | -0.3081 | MIXED |
| F4_A_P10 | F4-A | 2222614363734444994005/147573952589676412928 | [14.1160, 16.0061] | 0.9451 | 2.7881 | ALL_POS |
| F4_B_M10 | F4-B | 39/1280 | [-0.0556, 0.1166] | 0.0861 | 0.0619 | MIXED |
| F4_B_P10 | F4-B | 1001/1280 | [0.3902, 1.1739] | 0.3918 | 0.3492 | MIXED |
| F4_C_M10 | F4-C | -37/128 | [-0.5315, -0.0467] | 0.2424 | -0.2086 | MIXED |
| F4_C_P10 | F4-C | 3461/256 | [12.4404, 14.5987] | 1.0791 | 2.1917 | MIXED |
| F4_E_M10 | F4-E | -75411539817269246226233/2213609288845146193920 | [-35.0392, -33.0952] | 0.9720 | -6.1317 | ALL_NEG |
| F4_E_P10 | F4-E | 40208040350723795914951/2213609288845146193920 | [17.1053, 19.2227] | 1.0587 | 3.0015 | ALL_POS |
| F5_CONSTANT_HAZARD | F5 | -2935757529566958647/147573952589676412928 | [-0.1584, 0.1186] | 0.1385 | -0.0251 | MIXED |
| QA_LOW | Q-A | -528864518651159182501/442721857769029238784 | [-2.1594, -0.2297] | 0.9649 | -0.2166 | MIXED |
| QA_HIGH | Q-A | 350505282497034893921/221360928884514619392 | [0.6318, 2.5350] | 0.9516 | 0.2911 | MIXED |
| QB_LOW | Q-B | -523697448371106825631/221360928884514619392 | [-3.0341, -1.6975] | 0.6683 | -0.6193 | MIXED |
| QB_HIGH | Q-B | 389356343656323731063/110680464442257309696 | [2.6856, 4.3501] | 0.8323 | 0.7395 | MIXED |
| E_LOW | E | -392754955344523336305/147573952589676412928 | [-3.5609, -1.7619] | 0.8995 | -0.5176 | MIXED |
| E_HIGH | E | 121587877526973459203/55340232221128654848 | [1.2779, 3.1163] | 0.9192 | 0.4182 | MIXED |
| INT_F2_05_E_M10 | INT-F2xF4-E | -42865403668341537175469/553402322211286548480 | [-78.6571, -76.2588] | 1.1992 | -11.3003 | ALL_NEG |
| INT_F2_05_E_P10 | INT-F2xF4-E | 38604902998567975194823/2213609288845146193920 | [16.3892, 18.4904] | 1.0506 | 2.9041 | ALL_POS |

## Top-2 interaction (F2 x F4-E) contrasts (replicate-level paired)

| contrast | mean (h) | 95% CI | half-width | std |
|---|---|---|---|---|
| I_minus | 67520492159033978112187/2213609288845146193920 | [29.4504, 31.5545] | 1.0521 | 5.0722 |
| I_plus | 80983714831487529933851/1106804644422573096960 | [71.7971, 74.5407] | 1.3718 | 9.3313 |

CI contains 0 -> '未观察到明确 interaction'; excludes 0 -> '模型内非加性交互' (never real causality)

## Formal factor rank (factor_score = max |std|, main scenarios)

| rank | factor | factor_score | max scenario | mean dT (h) | CI |
|---|---|---|---|---|---|
| 1 | F2 | -10.7419 | F2_TURNOVER_05 | -16357056701513088058783/221360928884514619392 | [-75.0966, -72.6897] |
| 2 | F4-E | -6.1317 | F4_E_M10 | -75411539817269246226233/2213609288845146193920 | [-35.0392, -33.0952] |
| 3 | F4-A | 2.7881 | F4_A_P10 | 2222614363734444994005/147573952589676412928 | [14.1160, 16.0061] |
| 4 | F4-C | 2.1917 | F4_C_P10 | 3461/256 | [12.4404, 14.5987] |
| 5 | Q-B | 0.7395 | QB_HIGH | 389356343656323731063/110680464442257309696 | [2.6856, 4.3501] |
| 6 | E | -0.5176 | E_LOW | -392754955344523336305/147573952589676412928 | [-3.5609, -1.7619] |
| 7 | F4-B | 0.3492 | F4_B_P10 | 1001/1280 | [0.3902, 1.1739] |
| 8 | Q-A | 0.2911 | QA_HIGH | 350505282497034893921/221360928884514619392 | [0.6318, 2.5350] |
| 9 | F3 | 0.2576 | F3_TAU210 | 290862671124309017435/442721857769029238784 | [0.2107, 1.1032] |
| 10 | F5 | -0.0251 | F5_CONSTANT_HAZARD | -2935757529566958647/147573952589676412928 | [-0.1584, 0.1186] |

## Mechanism ledger (summed over all evaluation reps; NOT an additive T decomposition)

### F2_TURNOVER_05
- effective: {'A': '31995', 'B': '25600', 'C': '32000', 'E': '37881'}
- retest: {'A': '775', 'B': '880', 'C': '565', 'E': '2292'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '18086482947761441533/4611686018427387904', 'C': '44854568504353658585/4611686018427387904', 'E': '14731846455727075893/1152921504606846976'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '15', 'B': '126551130246018001/4611686018427387904', 'C': '6294382119671238485/2305843009213693952', 'E': '22766513499413918049/2305843009213693952'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '268/3'}
- turnover_occupancy: 6272 h (summed over 128 reps)
- off_shift: 23124 h

### INT_F2_05_E_P10
- effective: {'A': '63995/2', 'B': '25600', 'C': '32000', 'E': '416691/10'}
- retest: {'A': '775', 'B': '880', 'C': '565', 'E': '12606/5'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '9106517039003729767/2305843009213693952', 'C': '45914117697627665795/4611686018427387904', 'E': '143945316087386484903/5764607523034234880'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '15/2', 'B': '0', 'C': '0', 'E': '51222003868034698401/11529215046068469760'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '274/3'}
- turnover_occupancy: 6272 h (summed over 128 reps)
- off_shift: 53268 h

### E_HIGH
- effective: {'A': '31995', 'B': '25600', 'C': '63995/2', 'E': '38097'}
- retest: {'A': '780', 'B': '838', 'C': '585', 'E': '2469'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '18086482947761441533/4611686018427387904', 'C': '44958831624698767755/4611686018427387904', 'E': '6231788537168579323/576460752303423488'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '10', 'B': '126551130246018001/4611686018427387904', 'C': '3001714520633229695/576460752303423488', 'E': '27303052262193752543/2305843009213693952'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '268/3'}
- turnover_occupancy: 12544 h (summed over 128 reps)
- off_shift: 49092 h

### F4_E_P10
- effective: {'A': '63995/2', 'B': '25600', 'C': '32000', 'E': '416691/10'}
- retest: {'A': '775', 'B': '880', 'C': '565', 'E': '12606/5'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '9106517039003729767/2305843009213693952', 'C': '45914117697627665795/4611686018427387904', 'E': '143945316087386484903/5764607523034234880'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '15/2', 'B': '0', 'C': '0', 'E': '51222003868034698401/11529215046068469760'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '274/3'}
- turnover_occupancy: 12544 h (summed over 128 reps)
- off_shift: 53364 h

### QA_HIGH
- effective: {'A': '63945/2', 'B': '25600', 'C': '31985', 'E': '37464'}
- retest: {'A': '1905/2', 'B': '1056', 'C': '710', 'E': '2472'}
- failure_wasted: {'A': '5883701141526721015/576460752303423488', 'B': '8151970654914777053/2305843009213693952', 'C': '9088823797634873923/1152921504606846976', 'E': '6231788537168579323/576460752303423488'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '48641000341043548715/1152921504606846976', 'B': '477273192044476357/1152921504606846976', 'C': '104098385884849622135/4611686018427387904', 'E': '22766513499413918049/2305843009213693952'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '266/3'}
- turnover_occupancy: 12544 h (summed over 128 reps)
- off_shift: 49020 h

### QB_LOW
- effective: {'A': '63985/2', 'B': '25600', 'C': '31995', 'E': '37983'}
- retest: {'A': '715', 'B': '838', 'C': '515', 'E': '1953'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '8151970654914777053/2305843009213693952', 'C': '45809854577282556625/4611686018427387904', 'E': '26608138637322861187/2305843009213693952'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '15', 'B': '477273192044476357/1152921504606846976', 'C': '11581346606241024345/2305843009213693952', 'E': '10542764505382687077/1152921504606846976'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '266/3'}
- turnover_occupancy: 12544 h (summed over 128 reps)
- off_shift: 48672 h

### QB_HIGH
- effective: {'A': '63985/2', 'B': '25600', 'C': '31995', 'E': '37776'}
- retest: {'A': '1705/2', 'B': '934', 'C': '635', 'E': '2685'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '8151970654914777053/2305843009213693952', 'C': '17931191908693583951/2305843009213693952', 'E': '6231788537168579323/576460752303423488'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '35/2', 'B': '477273192044476357/1152921504606846976', 'C': '46945222027659601125/4611686018427387904', 'E': '22766513499413918049/2305843009213693952'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '266/3'}
- turnover_occupancy: 12544 h (summed over 128 reps)
- off_shift: 49356 h

### QA_LOW
- effective: {'A': '63995/2', 'B': '25600', 'C': '32000', 'E': '38223'}
- retest: {'A': '1265/2', 'B': '706', 'C': '465', 'E': '2094'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '9106517039003729767/2305843009213693952', 'C': '22542877927120971855/2305843009213693952', 'E': '6231788537168579323/576460752303423488'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '5/2', 'B': '0', 'C': '828361843385722085/4611686018427387904', 'E': '22766513499413918049/2305843009213693952'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '266/3'}
- turnover_occupancy: 12544 h (summed over 128 reps)
- off_shift: 48768 h

### E_LOW
- effective: {'A': '63955/2', 'B': '25600', 'C': '63965/2', 'E': '37572'}
- retest: {'A': '775', 'B': '886', 'C': '575', 'E': '2019'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '8151970654914777053/2305843009213693952', 'C': '23695799431727818831/2305843009213693952', 'E': '6231788537168579323/576460752303423488'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '65/2', 'B': '477273192044476357/1152921504606846976', 'C': '70003652119796540645/4611686018427387904', 'E': '24039062261891046981/2305843009213693952'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '266/3'}
- turnover_occupancy: 12544 h (summed over 128 reps)
- off_shift: 48648 h

### F4_E_M10
- effective: {'A': '31970', 'B': '25600', 'C': '31970', 'E': '340929/10'}
- retest: {'A': '775', 'B': '880', 'C': '565', 'E': '10314/5'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '15629558986657075753/4611686018427387904', 'C': '47160411513567352537/4611686018427387904', 'E': '3041486909867167421/1152921504606846976'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '35', 'B': '2583475091350383781/4611686018427387904', 'C': '75469672396082057045/2305843009213693952', 'E': '119742195700973444567/11529215046068469760'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '260/3'}
- turnover_occupancy: 12544 h (summed over 128 reps)
- off_shift: 46596 h

### Q4_BASELINE
- effective: {'A': '31990', 'B': '25600', 'C': '63985/2', 'E': '37881'}
- retest: {'A': '775', 'B': '880', 'C': '565', 'E': '2292'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '8151970654914777053/2305843009213693952', 'C': '35631196467498882777/4611686018427387904', 'E': '6231788537168579323/576460752303423488'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '20', 'B': '477273192044476357/1152921504606846976', 'C': '17823597165739708245/2305843009213693952', 'E': '27303052262193752543/2305843009213693952'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '268/3'}
- turnover_occupancy: 12544 h (summed over 128 reps)
- off_shift: 48768 h

### INT_F2_05_E_M10
- effective: {'A': '31995', 'B': '25600', 'C': '32000', 'E': '340929/10'}
- retest: {'A': '775', 'B': '880', 'C': '565', 'E': '10314/5'}
- failure_wasted: {'A': '14291542439823111705/1152921504606846976', 'B': '15629558986657075753/4611686018427387904', 'C': '44854568504353658585/4611686018427387904', 'E': '1731002074064490967/288230376151711744'}
- shift_wasted: {'A': '0', 'B': '0', 'C': '0', 'E': '0'}
- terminal_cancelled: {'A': '15', 'B': '2583475091350383781/4611686018427387904', 'C': '6294382119671238485/2305843009213693952', 'E': '80916981837065480097/11529215046068469760'}
- calibration: {'A': '129/2', 'B': '5/3', 'C': '43', 'E': '260/3'}
- turnover_occupancy: 6272 h (summed over 128 reps)
- off_shift: 41076 h

## Management recommendation (DRAFT for Human Gate)

- **F2** (rank 1, F2_TURNOVER_05): dT=-16357056701513088058783/221360928884514619392 h, 95% CI [-75.0966, -72.6897], half-width 1.2035 h. completion-time decrease (Delta T < 0). Constraints: see scenario level; e.g. turnover 0.5h overlap requires two-bay logistics; duration changes are process/capacity decisions. within the frozen H1/NO_PM/K12 model world; model-internal sensitivity, NOT a real-world causal claim.
- **F4-E** (rank 2, F4_E_M10): dT=-75411539817269246226233/2213609288845146193920 h, 95% CI [-35.0392, -33.0952], half-width 0.972 h. completion-time decrease (Delta T < 0). Constraints: see scenario level; e.g. turnover 0.5h overlap requires two-bay logistics; duration changes are process/capacity decisions. within the frozen H1/NO_PM/K12 model world; model-internal sensitivity, NOT a real-world causal claim.
- **F4-A** (rank 3, F4_A_P10): dT=2222614363734444994005/147573952589676412928 h, 95% CI [14.1160, 16.0061], half-width 0.9451 h. completion-time increase (Delta T > 0). Constraints: see scenario level. within the frozen H1/NO_PM/K12 model world; model-internal sensitivity, NOT a real-world causal claim.
- **F4-C** (rank 4, F4_C_P10): dT=3461/256 h, 95% CI [12.4404, 14.5987], half-width 1.0791 h. completion-time increase (Delta T > 0). Constraints: see scenario level. within the frozen H1/NO_PM/K12 model world; model-internal sensitivity, NOT a real-world causal claim.
- **Q-B** (rank 5, QB_HIGH): dT=389356343656323731063/110680464442257309696 h, 95% CI [2.6856, 4.3501], half-width 0.8323 h. completion-time increase (Delta T > 0). Constraints: model/parameter inputs; not a management lever. within the frozen H1/NO_PM/K12 model world; model-internal sensitivity, NOT a real-world causal claim.
- **E** (rank 6, E_LOW): dT=-392754955344523336305/147573952589676412928 h, 95% CI [-3.5609, -1.7619], half-width 0.8995 h. completion-time decrease (Delta T < 0). Constraints: model/parameter inputs; not a management lever. within the frozen H1/NO_PM/K12 model world; model-internal sensitivity, NOT a real-world causal claim.
- **F4-B** (rank 7, F4_B_P10): dT=1001/1280 h, 95% CI [0.3902, 1.1739], half-width 0.3918 h. completion-time increase (Delta T > 0). Constraints: see scenario level. within the frozen H1/NO_PM/K12 model world; model-internal sensitivity, NOT a real-world causal claim.
- **Q-A** (rank 8, QA_HIGH): dT=350505282497034893921/221360928884514619392 h, 95% CI [0.6318, 2.5350], half-width 0.9516 h. completion-time increase (Delta T > 0). Constraints: model/parameter inputs; not a management lever. within the frozen H1/NO_PM/K12 model world; model-internal sensitivity, NOT a real-world causal claim.
- **F3** (rank 9, F3_TAU210): dT=290862671124309017435/442721857769029238784 h, 95% CI [0.2107, 1.1032], half-width 0.4463 h. completion-time increase (Delta T > 0). Constraints: model/parameter inputs; not a management lever. within the frozen H1/NO_PM/K12 model world; model-internal sensitivity, NOT a real-world causal claim.
- **F5** (rank 10, F5_CONSTANT_HAZARD): dT=-2935757529566958647/147573952589676412928 h, 95% CI [-0.1584, 0.1186], half-width 0.1385 h. completion-time decrease (Delta T < 0). Constraints: model/parameter inputs; not a management lever. within the frozen H1/NO_PM/K12 model world; model-internal sensitivity, NOT a real-world causal claim.

> Q4_EVALUATION is the ONLY final-inference CI source; screening data never pooled. F3 = COUNTERFACTUAL_ONLY (未观察到明确改善 / 点估计 / CI 跨 0 依正式结果而定); F5 = MODEL_SEMANTIC_ONLY. 数学影响排序 ≠ 管理实施优先级.
