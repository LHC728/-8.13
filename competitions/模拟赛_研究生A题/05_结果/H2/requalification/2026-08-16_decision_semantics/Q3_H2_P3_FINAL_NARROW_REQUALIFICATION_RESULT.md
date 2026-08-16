# Q3-H2 P3 FINAL NARROW REQUALIFICATION RESULT

PM_IDLE high-age: **PASS** (PMIDLE-AGE-01 age=238 no legal head -> MAINTENANCE {H1_NOOP, PM_IDLE}; -02 age=239 -> PM_IDLE legal; -03 age=240 -> PM_IDLE illegal; -04 legal head + a+d>240 -> mandatory -> no H2 dispatch decision point; a+d check applies ONLY to DISPATCH points; checker own derivation, independent)
failure-at-end observable: **PASS** (PENDING-05: uncensored natural lifetime reached exactly at fragment completion -> completion-first preserved (ACTIVITY_COMPLETE stands) + SAFE EQUIPMENT_FAILURE marker (trigger=failure_at_end, fragment identity only; no hidden lifetime/U_L/u_key) -> same-timestamp pre-action resource failed/unavailable -> no H2 dispatch/PM decision; G3 accepted core NOT modified)
bay fix reviewed by final Pro-Max: **PASS** (3d32d8f TRUE_STATE_GENERATED bay occupant, consistent)
B-1:
population_wait=**74**
population_pm=**5396**
selected_wait=**50**
selected_pm=**50**
selected_both=**18**
n=**100**
(ALL-eligible, C_eval-independent; frozen 50+50+top-up+cap120; dp_diag per batch; population/selected explicitly split)

posterior world_m: **PASS** (per-m rebuild from h2_rollout keys; cross-action CRN; no physical hidden world; 2M* prefix identical)

VERIFIED_PRO_MAX: **true** (fresh deepseek-pro-max / deepseek-v4-pro / reasoning=max / read-only / workspace delta=0; final-code review)
review_verdict: **PASS_WITH_CAVEAT** (8 checks all PASS)
authority_conflict: **false**

new P3-C: **RUN** (root run_20260816T175317829317Z_7b490ce6)
agreement_b: **1.0000** (100/100; CP95 [0.9638, 1.0] disclosure only)
agreement_c: **1.0000** (100/100)
deviation_count: **0** -> H2_NO_EFFECTIVE_DEVIATION
final H2: **DELETE** (frozen hard gate; AUTOPILOT STOP)

transfer: **NOT RUN**
holdout: **NOT RUN**
C25: **NOT RUN**

Evidence: 05_结果/H2/requalification/2026-08-16_decision_semantics/ (pmidle_age / pending_05 / bay_occupancy / tests_report 323/323 = 169 regression + 154 requal, final code); 05_结果/governance/model_routing/v2_1_2/p3_requal_pro_max/pro_max_review_final_narrow.txt.
Commits: 439e1e1 (PM_IDLE + PENDING-05 + B-1 split) -> e279b8a (final Pro-Max + R1/R2/R3) -> 50ddec4 (P3-C final rerun) (+ state sync). branch g2-02-impl.

**STOP** (AUTOPILOT STOP -> Human Gate final Q3 review; H2 = DELETE_AWAITING_HUMAN_GATE; no automatic progression).
