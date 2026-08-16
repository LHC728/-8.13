# Q3-H2 P3 SECOND REQUALIFICATION RESULT

STATUS: **PASS** (package delivered; final H2 = DELETE, awaiting Human Gate)

old root 791506d8: **INVALIDATED** (INVALIDATED_FOR_DECISION_SEMANTICS, retained immutable)
root 4f60db0d: **INVALIDATED_FOR_FROZEN_SAMPLE_AND_ROLLOUT_WORLD_SEMANTICS** (retained immutable, numbers unchanged)

B-1 population: **ALL_H2_ELIGIBLE** (frozen §4; NOT the online quota subset; C_eval-independent)
offline C_eval independent: **PASS** (B1-OFFLINE-01/02/03)
HG-Q3-H2-DP-DIAG-01: **LANDED** (addendum `08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT_ADDENDUM_DP_DIAG_01.md` + CHANGELOG; production dp_online unchanged)
dp_diag per batch: **PASS** (per-batch 0-based index by (time, canonical resource order) over B-1-evaluated points; normal/ALT/2M* share (replicate_id, dp_diag); 2M* keys identical for m=0..M*-1; action never in seed)
posterior world_m per rollout: **PASS** (evaluate_decision_point rebuilds world_m + provider_m from the m-th h2_rollout U_X/U_D/U_L keys; exactly M rebuilds shared across the actions of each m)
physical-world leakage: **NONE** (caller fixed world/provider removed; h2_batch_runner dummy world removed; x_abc/x_d/residual lifetimes resampled from rollout keys only; WORLD-M-05 bit-identical under hidden annotations)
M8/M16 prefix: **PASS** (identical keys for m=0..M*-1; DPKEY-05/WORLD-M-04)
cross-action CRN: **PASS** (WORLD-M-03: exactly M world rebuilds shared across actions)
mandatory age legality: **PASS** (AGE-LEGAL-01/02/03: a+d>240 -> no H2 decision point; a+d==240 -> START_HEAD legal, PM_WITH_HEAD never offered; P3-A PM-R2 + checker requalified)
pre-action replacement_pending: **PASS** (PENDING-01..04: same-timestamp failure / illegal-240 cancel / post-completion mandatory visible in pre-action state; observable events only, no hidden lifetime read; bay-occupancy projection fix included)
online/offline policy parity: **PASS** (WORLD-M-06; both paths delegate to the same evaluate_decision_point)

P3-B requalification: **PASS** (Q_hat / paired D_m / SE_M / 2SE / CRN / M8-M16 prefix re-certified; formulas unchanged)

cost grid: **(4,8)/(8,6)/(8,8) ONLY**
selected: **(8,8) -> M*=8, C_eval*=8, W_cap*=4, P_cap*=4 (FREEZE RESTORED; c_r includes per-m world rebuild; w_p_median 8.16s <= 90s)**

VERIFIED_PRO_MAX: **true** (fresh deepseek-pro-max / deepseek-v4-pro / reasoning=max / read-only; workspace delta=0)
review_verdict: **PASS_WITH_CAVEAT** (second-requalification review; A-H all YES)
required_actions_closed: **true** (R1 state sync, R2 evidence wording regenerated, R3 rerun executed)
authority_conflict: **false**

new P3-C: **RUN** (root run_20260816T170310179282Z_ea3354ba)
n: **100** (>=50 PASS)
wait: **50** (candidates 74)
pm: **50** (candidates 5396)
both: **18**
agreement_b: **1.0000** (100/100; CP95 [0.9638, 1.0] disclosure only)
agreement_c: **1.0000** (100/100)
deviation_count: **0** -> H2_NO_EFFECTIVE_DEVIATION
final H2: **DELETE** (frozen hard gate; AUTOPILOT STOP)
cross-K transfer: **NOT RUN**
h2_holdout: **NOT RUN**
C25: **NOT RUN**

Evidence: 05_结果/H2/requalification/2026-08-16_decision_semantics/ (INVALIDATION_REPORT_SECOND.md, B1_OFFLINE / AGE_LEGAL / PENDING / WORLD_M / DP_KEY-dp_diag / COST_REQUALIFICATION_SECOND / tests 316/316); 05_结果/governance/model_routing/v2_1_2/p3_requal_pro_max/pro_max_review_second.txt; MODEL_ROUTING_MISS_001.json.
Commits: b6a6aa8 (second requalification) -> 558a6b0 (Pro-Max + cost SECOND) -> 3d32d8f (bay-occupancy fix) -> ae945ee (P3-C rerun) (+ state sync to follow). branch g2-02-impl.

**STOP** (AUTOPILOT STOP -> Human Gate final Q3 review; H2 = DELETE_AWAITING_HUMAN_GATE; no automatic progression).
