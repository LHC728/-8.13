# Q3-H2 决策语义重新认证结果

> 包：`Q3-H2-P3 重新认证 —— 决策状态 / 首动作 / DP 随机键语义修复`（Human Gate BLOCKER A–D）
> 路由：MMR V2.1.2 **YELLOW**（authority_state=FROZEN，非 RED）；冻结权威 `Q3_H2_BOOTSTRAP_SPEC_DRAFT.md` FINAL_FREEZE_ACCEPTED + CR-V3.1
> 日期：2026-08-16；branch `g2-02-impl`；最终 HEAD `3d5e7af`（已 push、fetch 后 0/0 同步）
> **STATUS: PASS（包完成）——最终决策结论：H2 = DELETE（AWAITING_HUMAN_GATE）**

## 1. 旧证据处理（immutable）

- 旧 P3-C root `05_结果/H2/tuning/stability/run_20260816T101049163825Z_791506d8` **永久保留，数字一律未改**（n=100 / agreement_b=0.9900 / agreement_c=1.0000 / deviation_count=0 / CP95 / checks / manifest / file_hashes 原样），仅叠加治理标记 `INVALIDATION_STATUS.json` = **INVALIDATED_FOR_DECISION_SEMANTICS**（不进入原 file_hashes 清单）。
- `INVALIDATION_REPORT.md`（含失效原因 A–D、失效范围表、density dependency audit = UNAFFECTED_BY_P3_DECISION_RECONSTRUCTION）已落文。

## 2. P3-A 修复（decision state / resource idle）

- `main_model/h2/decision_point_v1.py`：`pre_action_log`（同 timestamp dispatch 阶段记录排除，phase-semantics）与 `project_pre_action_state`；`reconstruct_decision_points` 逐 closure 在 PRE-ACTION 视图上判定，DISPATCH 点额外要求资源 `status == "idle"`（testing/calibration/replacement/failed 无点）。
- checker `h2_p3_mechanics_checker_v1.py` requalified（own pre-action view + own idle guard + own fragment identity）。
- 测试：`test_h2_p3_requal_v1.py` DP-IDLE-01..04 / PRE-01..04；P3-A mechanics 套件 45/45。

## 3. P3-B 修复（first-action 严格生效）

- `rollout_engine_v1.py`：RolloutEngine 绑定冻结决策上下文（decision_resource / decision_head / decision_kind）；`_apply_first_action_if_dispatch` **fail-closed**：
  - START_HEAD → `_start_frozen_head`（缺上下文 / 队列空 / frozen head ≠ 队头 / 不合法均 raise），`_record_activity_start` 于 t 记录 ACTIVITY_START；
  - WAIT_EVENT → `wait_holds[resource]=anchor` + `h2_wait_wake`；`_equipment_and_dispatch` 在 [t, anchor) 跳过该资源；anchor 处 hold 解除、H1 恢复；
  - PM_WITH_HEAD / PM_IDLE → 缺 pm/decision resource 则 raise，开始 preventive replacement；
  - H1_NOOP → 无操作（无 optional PM）。
- `h2_policy_v1.py`：`evaluate_decision_point(..., decision_head=...)` 绑定进每个候选 rollout（ACT-01..08 验证路径差异化）。
- `h2_batch_runner_v1.py`：`_h2_step` 用 pre-action 投影状态与冻结 head；dp = per-batch evaluated 序号。
- checker `h2_p3b_checker_v1.py` `check_rollout_kernel` requalified（own head 推导 + own 期望效果）。

## 4. 随机键（dp 语义，SPEC 6.2）

- 离线 B-1 样本 = **production-contract 在线 quota（C_eval\*=8 / W_cap=4 / P_cap=4 / age buckets）实际评估的决策点**；dp = **每批 evaluated-point 0-based 序号**（非跨 batch 全局 sample index）；normal / ALT / M=16 同 (batch, dp) 共享 CRN 键。
- `_point_context` 用 pre-action 投影；冻结 head 传入每个候选 rollout。
- 测试：DPKEY-01..05（含 9 点合成 log 验证 quota 拒绝后重编号）、QUOTA-DP-01..03、SAMPLE-01..04（50/50/120 top-up 冻结算术不变）。

## 5. 样本与失效范围

- B-1 规则（前 50 wait-eligible 含 both + 前 50 PM-only、类不足跨类补足、cap 120）**未改**（`_b1_take` 纯函数化，行为一致）。
- 失效范围：P3-A/P3-B/P3-C 三组件 requalified；**P1 / P2 / Q3 H1 / Q2 / G3 / Density = UNAFFECTED**（修复不触及 h2 包 import 边界、不修改冻结数学/动作/参数/随机域）。

## 6. 成本重认证（§13）

- 冻结网格 (4,8) / (8,6) / (8,8)，成本导向（w_p≤90s；max M 再大 C_eval）：三候选全可行（w_p_median 3.40 / 5.00 / 6.60 s）→ 仍选 **(8,8)** → **冻结恢复 M\* = 8、C_eval\* = 8、W_cap\* = 4、P_cap\* = 4**（`cost_requalification_report.json`）。
- 时序说明：成本测量先于 release-guard 修复；修复为成本单调（仅抑制重复 release），最坏 7.08s << 90s，无需重测（已记录）。

## 7. Pro-Max outcome-aware 审查（§14，YELLOW 门）

- 两轮 fresh `deepseek-pro-max / deepseek-v4-pro / reasoning=max` 只读审查：**PASS_WITH_CAVEAT ×2**，`authority_conflict=false`（两轮），`required_actions`（R1 状态同步、R2 失败重跑负证据 + 成本时序、R3 E 路径 fixture）全部闭合 → `required_actions_closed=true` → P3-C 重跑 AUTHORIZED（最终代码）。
- 证据：`05_结果/governance/model_routing/v2_1_2/p3_requal_pro_max/`（request header / dispatch / review ×2 / verification）。

## 8. P3-C 重跑（§15/16，修复后语义）

- 新 root `05_结果/H2/tuning/stability/run_20260816T150705443207Z_4f60db0d`（fail-closed probe/confirm/promote/final 验证 PASS）：
  - B-1 样本 **n=79**（wait=39、pm=40、both=5，quota-evaluated 集合）；
  - **agreement_b = 1.0000（79/79）PASS**（CP95 [0.9544, 1.0] 仅披露）；**agreement_c = 1.0000（79/79）PASS**；C23 policy PASS；
  - **deviation_count = 0 → 冻结硬门 H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE**（2SE / 0.95 / 样本 / 动作集未改）；
  - tests 20/20 + 回归 28/36/38/23/44/26 全 PASS；ledger 追加 982.1s → 累计 **1737.76s（0.4827h）**（soft 4h / hard 8h 未达）。
- 途中 fail-closed 负证据：首次重跑 runaway（`20260816T141252994705Z_b9766950`，t=174 E 资源点）→ offline-rebuild release-guard 修复（`_release_tasks` 状态守卫，已测 attempt-1 不再重 release）+ RELEASE-GUARD-01/02/03 / INFLIGHT-01/03 测试 → `failed_rerun_negative_evidence.txt` 保留。

## 9. 后续阶段（本包之后）

- **cross-K transfer / h2_holdout / C25 = NOT RUN，且保持 NOT AUTHORIZED**，直至 Human Gate final Q3 review（H2 = DELETE 建议在修复后语义下由有效证据支撑）。
- 若 Human Gate 不认可 DELETE 结论并要求保留 H2，则需另发授权（冻结项不得由实现侧更改）。

## 10. 治理与最终建议

- 冻结模型零修改（动作定义 / 2SE / 0.95 / 样本规则 / random protocol / M 网格 / C25 / C23 authority 全部未动）；所有改动为实现-契约语义修复（YELLOW 域内）。
- 测试合计：requal 套件 **128/128** + 回归 **169/169** PASS；证据 `05_结果/H2/requalification/2026-08-16_decision_semantics/`（tests_report / first_action / wait_hold / dp_key / quota_dp / sample_topup / checker_requal / cost_requalification / p3b_requal_summary / failed_rerun_negative_evidence）。
- 最终建议：**H2_DELETE_AWAITING_HUMAN_GATE**（修复后语义下 deviation_count=0，2SE confident deviation 下 H2 政策无有效偏离 H1）；提交链 `6c65593 → a08f2b4 → be55a3d → e531871 → 8dcb991 → 3d5e7af` 已 push 且 fetch 验证同步。
- **本包 STOP**（AUTOPILOT STOP → Human Gate final Q3 review；不自动进入下一 Gate）。
