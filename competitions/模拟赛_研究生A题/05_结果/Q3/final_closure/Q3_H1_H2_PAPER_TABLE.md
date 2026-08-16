# Q3 H1 vs H2 PAPER TABLE（论文可直接使用）

> 数值机械读取自 accepted evidence：
> H1：`05_结果/Q3/formal/reissue_20260815T150613626910Z_f4da8f9d/recommendation.json`（k\*=K12，限定七个 K + 冻结政策集）。
> H2：`05_结果/H2/tuning/stability/run_20260816T175317829317Z_7b490ce6/result_summary.json`（n=100、agreement_b/c=1.0000、deviation_count=0）。
> 成本：`05_结果/H2/requalification/2026-08-16_decision_semantics/cost_requalification_report.json`（(8,8) 冻结恢复）。

| 比较项目 | H1 | H2 |
|---|---|---|
| 策略类型 | 规则型调度（FCFS + 班历 + NO_PM_BEFORE_MANDATORY） | 后验 rollout 动态调度（challenger） |
| 状态信息 | 当前可观察状态 | ObservableState + PosteriorState |
| 候选动作 | H1 固定规则（无候选比较） | START_HEAD / WAIT_EVENT / PM_WITH_HEAD / PM_IDLE / H1_NOOP |
| 随机模拟 | 无额外 rollout | M\*=8 posterior rollouts（每 m 由 h2_rollout keys 重建 world_m，CRN） |
| 决策置信门 | 不适用 | 2SE confident-deviation（配对 D_m、SE_M = SD/√M） |
| 计算复杂度 | 低（常数规则开销） | 高（候选动作数 × M 次续演 + 每 m world 重建） |
| 稳定性 | 基线 | ALT-salt agreement = 1.0000；M\*=8 vs 2M\*=16 agreement = 1.0000 |
| 有效偏离 | 基线 | **0/100**（deviation_count=0，ALL-eligible B-1 n=100） |
| 最终角色 | 正式采用 | 高级候选、经预注册门槛淘汰（FROZEN_HISTORICAL_CHALLENGER） |
| 推荐 | **YES**（k\*=K12，strong_recommendation=true；七个 K + 冻结 H1 政策集范围内，非全局最优） | **NO** |

引用注：H2 的 agreement=1 仅表示 H2 自身决策稳定，不构成对 H1 的优势证据；DELETE 由 deviation_count=0 触发（预注册冻结门）。
