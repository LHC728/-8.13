# INVALIDATION_REPORT (SECOND) — Q3-H2-P3 B-1 冻结样本与 rollout world 语义

> 日期：2026-08-16
> 依据：Human Gate 第二次语义重新认证（`e4fd435` 的 H2 DELETE 暂不接受；撤销「quota-evaluated = B-1 population」解释）
> 路由：targeted requalification（不重做 P1/P2/Q3-H1）；MMR V2.1.2 下登记 `MODEL_ROUTING_MISS-001`（frozen population supersession 应 RED/HUMAN_GATE_REQUIRED；本次由 HG-Q3-H2-DP-DIAG-01 完成最小澄清，不重设计 MMR）

## 1. 失效证据根（保留、数字不改）

- **`run_20260816T150705443207Z_4f60db0d`**（最新 P3-C root）：新增治理状态
  **INVALIDATED_FOR_FROZEN_SAMPLE_AND_ROLLOUT_WORLD_SEMANTICS**
  （`INVALIDATION_STATUS_SECOND.json` 叠加；n=79 / agreement_b=1.0000 / agreement_c=1.0000 / deviation_count=0 等数字一律不改写；不再作为 H2 决策证据）。
- **`run_20260816T101049163825Z_791506d8`**：保持原失效状态（INVALIDATED_FOR_DECISION_SEMANTICS，数字未改）。

## 2. 失效原因（A/B/C）

- **A. B-1 population 错误**：`build_b1_sample` 先经 `quota_simulate_batch()`（production-contract 在线 quota）再构造 B-1，把 §4 冻结的
  「ALL H2-ELIGIBLE DECISION POINTS（前 50 wait-eligible 含 both + 前 50 PM-only、补足、cap 120、n<50→DELETE、不受 C_eval\* 约束）」错误缩小为 quota 选中子集。
- **B. rollout world 未逐 m 重建**：`evaluate_decision_point` 把调用方提供的**固定 world/provider** 传给全部 m；
  冻结语义要求每个 m 由该 m 的 `h2_rollout` post keys（U_X/U_D/U_L）逐 m 后验重建 `world_m`（同 m 跨 action 共享 → 跨动作 CRN）。
  物理泄漏风险：H2BatchRunner 曾用固定 `u_x=1/2、u_d=1/3、u_l=1/3` 构造 world；offline 亦不应让 physical h2_tuning hidden world 决定 policy rollout 的后验状态。
- **C. decision legality / mandatory replacement 未闭合**：
  - `a + d > 240`（mandatory replacement）不应产生 H2 候选决策点（不得创建 START_HEAD/WAIT/optional PM 比较点）；
  - `a + d == 240`（exact_240）不应提供 optional PM 候选；
  - 同一 closure 中 equipment failure / illegal-240 / post-completion mandatory 形成的 replacement_pending 必须在 H2 pre-action 状态可见（不得投影为 idle/available），且不暴露 hidden lifetime。

## 3. 修复范围（本包）

| 组件 | 内容 |
|---|---|
| B-1 | 恢复 ALL H2-eligible population；dp_diag = 每批内 (time, canonical resource order) 0-based 序号（HG-Q3-H2-DP-DIAG-01）；B1-OFFLINE-01/02/03 机械证明 |
| rollout world | evaluate_decision_point 逐 m 由 h2_rollout keys 重建 world_m/provider_m；同 m 跨 action 共享；移除 caller-provided fixed world 依赖；WORLD-M-01..06 |
| 物理泄漏 | policy rollout 的后验状态（x_abc/x_d/residual lifetime）只来自 h2_rollout keys 后验重采样；physical_post_provider 仅生成物理批；H2BatchRunner 移除固定 world |
| mandatory/age | AGE-LEGAL-01/02/03（a+d>240 无点；==240 无 optional PM；<240 正常） |
| replacement_pending | PENDING-01..04（same-timestamp failure/cancel/mandatory 在 pre-action 状态可见） |
| 重新认证 | P3-B Q_hat/SE/CRN/M8-M16 prefix；成本重认证（world_m 重建后）；fresh Pro-Max（A–H 八问） |
| P3-C | 再次重跑（h2_tuning/seed 6/rep 0..9/K=10.5/normal+ALT/0.95/2SE/冻结 B-1 ALL-ELIGIBLE）；deviation_count=0 → H2 DELETE → STOP Human Gate；>0 且全门 PASS → P3-C PASS（cross-K transfer 恢复但仍先 STOP） |

## 4. 治理

- 冻结模型/参数/动作/2SE/0.95/seed/namespace/C25/C23 authority **不修改**；
  HG-Q3-H2-DP-DIAG-01 为唯一冻结澄清（追加 addendum，不重写历史条款）。
- 禁止：用 online C_eval 缩小 B-1；降 2SE；改 0.95；换 seed；加 sample；用 holdout/q3_formal；改 action set/C25/M grid；用 physical hidden world 代替 posterior rollout world；覆盖旧失败 evidence。
- cross-K transfer / h2_holdout / C25：**NOT RUN / NOT AUTHORIZED**（本包全程）。
