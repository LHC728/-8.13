# INVALIDATION_REPORT — Q3-H2 P3-C 决策语义失效（decision-semantics requalification）

> 日期：2026-08-16
> 依据：Human Gate BLOCKER（Q3-H2-P3 重新认证 —— 决策状态 / 首动作 / DP 随机键语义修复）
> 路由：MMR V2.1.2 = **YELLOW**（implementation-vs-frozen-contract semantic repair；Risk Card `05_结果/governance/model_routing/v2_1_2/routing_risk_card_p3_requal.json`）
> 冻结权威：`Q3_H2_BOOTSTRAP_SPEC_DRAFT.md` FINAL_FREEZE_ACCEPTED；检查注册表 CR-V3.1

## 1. 失效证据根（永久保留，数字不改）

- 旧 P3-C root：`05_结果/H2/tuning/stability/run_20260816T101049163825Z_791506d8`
- 状态：**INVALIDATED_FOR_DECISION_SEMANTICS**
- 该 root 的 n / agreement_b / agreement_c / deviation_count / deviation_rate / CP95 / checks / manifest / file_hashes **一律不改写**；其治理状态标记文件（`INVALIDATION_STATUS.json`、本报告）以叠加方式写入，**不进入原 file_hashes 清单**（原清单与 manifest 保持不变，可复验）。
- 该 root **不再作为 H2 DELETE 的最终决策证据**。

## 2. 失效原因（Human Gate 指定 A–D）

- **A. 决策时刻状态**：P3-C 离线重建决策状态时，使用了同一时刻已包含 H1 派工结果（ACTIVITY_START 等）的日志前缀，可能把「动作执行后状态」错误当成「动作执行前决策状态」。冻结语义要求 candidate action 在决策边界 s 上比较，Q_hat 状态必须是 PRE-ACTION STATE。
- **B. 资源空闲条件缺失**：`reconstruct_decision_points()` 未严格检查资源必须处于 idle/available，可能在资源已 testing / calibration / replacement / failed 时仍伪造 dispatch decision point。
- **C. candidate first-action 未严格生效**：RolloutEngine 中 START_HEAD / WAIT_EVENT 未按冻结 candidate first-action 语义生效（`decision_resource` 默认 None 时 START_HEAD 为空操作、WAIT_EVENT 不阻止派工），候选动作可能实际退化成相同或近似相同的续演路径。
- **D. dp 随机键语义**：P3-C 离线稳定性使用跨 batch 全局 sample index 作为 dp，不符合冻结的「每批内已评估 H2 决策点 0-based 序号」语义（§6.2），且与 production online quota 的 dp 分配不一致。

## 3. 失效范围（targeted requalification）

| 组件 | 状态 | 说明 |
|---|---|---|
| P3-A | **REQUALIFICATION（仅 decision-point reconstruction / resource idle / decision boundary 相关）** | `decision_point_v1.py` 修复 + DP-IDLE/PRE 测试 |
| P3-B | **REQUALIFICATION（仅 candidate first-action semantics + 其上的 Q_hat/SE + 修复后 cost calibration）** | `h2_policy_v1.py` / `rollout_engine_v1.py` 修复 + ACT 测试 + 成本重认证 |
| P3-C | **完全失效，必须重跑** | 旧 root 保留为 INVALIDATED_FOR_DECISION_SEMANTICS；重跑用全新 run root |
| P1 information firewall | UNAFFECTED（除非修复暴露新 C23 违规） | 修复不触及 h2 包 import 边界 |
| P2 posterior / conditional lifetime mathematics | UNAFFECTED | 不修改 |
| Q3 H1 formal / Q2 / G3 accepted evidence | UNAFFECTED | 不修改 |
| **Density** | **UNAFFECTED_BY_P3_DECISION_RECONSTRUCTION**（dependency audit 见下） | density analyzer 独立实现 |

## 4. Density dependency audit（证据）

- `checker/h2_q3_density_analyzer_v1.py` imports = {stdlib, `checker.h2_admission_opportunity_analyzer_v1`}——**无任何 main_model / decision_point_v1 依赖**（独立离线重建，注释明确 "independent; no main-model dispatch"）。
- `checker/h2_q3_density_checker_v1.py` imports = {stdlib, `checker.h2_q3_density_analyzer_v1`}。
- `checker/h2_admission_opportunity_analyzer_v1.py` imports = {stdlib}。
- 结论：**DENSITY = UNAFFECTED_BY_P3_DECISION_RECONSTRUCTION**（无需扩大 invalidation）。

## 5. 治理状态

- 冻结模型（题意/动作定义/2SE/0.95/样本规则/random protocol/M 网格/C25/C23 authority）**不修改**；本任务为实现-契约语义修复（YELLOW），非 RED authority mutation。
- 若修复中必须改动上述任一冻结项 → 立即 RED → HUMAN_GATE_REQUIRED（不得实现）。
- 在 Pro-Max outcome-aware review 真正 PASS 且 required actions 闭合之前，不得重新接受 P3-C；在此之前禁止 cross-K transfer / h2_holdout / C25。

## 6. 修复完成状态（P3-A + P3-B 落地）

| 项 | 状态 | 证据 |
|---|---|---|
| P3-A（决策边界 + idle guard） | **已修复 + 测试 PASS** | `main_model/h2/decision_point_v1.py`（pre_action_log / project_pre_action_state / reconstruct 逐 closure pre-action 视图 + dispatch 点 idle 要求）；`checker/h2_p3_mechanics_checker_v1.py` requalified；`tests/test_h2_p3_requal_v1.py`（DP-IDLE-01..04 / PRE-01..04）|
| P3-B（candidate first-action 严格生效） | **已修复 + 测试 PASS** | `main_model/h2_rollout/rollout_engine_v1.py`（decision_resource/decision_head/decision_kind 上下文 + START_HEAD fail-closed 启动冻结 head + WAIT_EVENT hold 至 anchor + PM fail-closed + h2_wait_wake）；`h2_policy_v1.py`（evaluate_decision_point 传 decision_head）；`h2_batch_runner_v1.py`（_h2_step 用 pre-action 状态与 head）|
| P3-B 离线 dp 语义 | **已修复** | `scripts/run_h2_p3c_stability_v1.py`：样本点 = production-contract 在线 quota（C_eval*=8/W_cap=4/P_cap=4）实际评估的决策点，dp = 每批 evaluated-point 0-based 序号（SPEC 6.2）；`_point_context` 用 pre-action 投影 |
| checker | **requalified** | `checker/h2_p3b_checker_v1.py` check_rollout_kernel：每个 first action 绑定冻结决策上下文（own head 推导 + own 期望效果断言），fail-closed head 不匹配验证 |
| 测试 | **124/124 PASS（5 套 requal 套件）+ 169/169 回归 PASS** | `tests/test_h2_p3c_requal_v1.py`（ACT-01..08 / DPKEY-01..05 / QUOTA-DP-01..03 / SAMPLE-01..04）等；`05_结果/H2/requalification/2026-08-16_decision_semantics/tests_report.json` |
| 成本重认证 | 待执行 | 冻结网格 (4,8)/(8,6)/(8,8)，成本导向；若仍选 (8,8) 恢复冻结继续，否则 HUMAN_GATE_REQUIRED |
| Pro-Max outcome-aware review | 待执行 | fresh pro_max_review（YELLOW）；PASS/CAVEAT+PASS 且 required_actions_closed=true ∧ authority_conflict=false 才可重跑 P3-C |
| P3-C 重跑 | **待执行** | 新 run root；deviation_count=0 → H2_DELETE → STOP Human Gate |

修复后的 P3-C 语义（重跑时生效）：样本点来自 quota 评估流；每个点在其 PRE-ACTION 决策边界状态上评估并绑定冻结 FCFS head；候选首动作（START_HEAD / WAIT_EVENT / PM）在 rollout 中严格生效（fail-closed）；normal / ALT / M=16 同点共享 (batch, dp) 的 CRN 键。
