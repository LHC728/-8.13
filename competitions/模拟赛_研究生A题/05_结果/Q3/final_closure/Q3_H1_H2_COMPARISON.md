# Q3 H1 vs H2 COMPARISON（第三问主策略 vs 高级候选）

> 所有数值机械引用自 accepted evidence（H1：`05_结果/Q3/formal/`；H2：`05_结果/H2/tuning/stability/run_20260816T175317829317Z_7b490ce6` + cost evidence）。

## A. 模型定位

- **H1**：规则型、可解释、低计算成本的**正式调度策略**（FCFS 全局队列 + NO_PM_BEFORE_MANDATORY + 班历约束；七 K 全部 accepted）。
- **H2**：基于 **ObservableState + PosteriorState + Monte Carlo rollout + CRN + 2SE confident-deviation** 的**高级动态 challenger**（在合法决策点比较 START_HEAD / WAIT_EVENT / PM_WITH_HEAD / PM_IDLE / H1_NOOP，用后验 rollout 估计未来代价）。

## B. 决策复杂度

- **H1**：直接按冻结调度规则行动（无候选比较、无前瞻模拟）。
- **H2**：每个被评估决策点对全部合法候选动作运行 M\*=8 个后验续演（每 m 由 h2_rollout post keys 重建 posterior world_m；同 m 跨动作共享 → CRN），并以 2SE 配对置信准则决定是否偏离 H1。

## C. 计算成本

- 冻结配置（cost requalification evidence，`cost_requalification_report.json`）：**M\*=8、C_eval\*=8、W_cap\*=4、P_cap\*=4**；w_p ≤ 90 s 预算下三候选全可行，(8,8) 选中。
- **H2 相对 H1 增加的复杂度**：每个评估点（候选动作数 × M）次完整 continuation rollout + 每 m 一次 posterior world 重建（qualitative：显著高于 H1 的常数规则开销）。**未编造任何运行时间**；可靠 wallclock 均来自 ledger/evidence（例如 P3-C 最终重跑 845.0 s 计入开发预算账本——属离线诊断成本，非生产每批成本）。

## D. 决策差异（最终 P3-C，ALL-eligible B-1 n=100）

- selected_wait=50、selected_pm=50、selected_both=18；population_wait=74、population_pm=5396。
- **agreement_b=1.0000**（ALT salt）、**agreement_c=1.0000**（M\*=8 vs 2M\*=16）。
- **deviation_count=0**：在冻结 2SE 有效偏离准则下，**100 个代表性 H2 决策点中没有一个点能够稳定证明非 H1 动作优于 H1**。

## E. 稳定性（正确解读）

- ALT salt agreement = 1.0000、M 翻倍 agreement = 1.0000 → **只说明 H2 自身决策在随机扰动与 M 翻倍下稳定**（诊断质量良好）。
- **不得**把 agreement=1 解释为「H2 优于 H1」。
- 真正导致 DELETE 的是 **deviation_count=0**（预注册冻结门）。

## F. 最终模型选择

- H2 **不是**因程序失败而淘汰：经决策状态修复、首动作语义、posterior world_m、ALL-eligible B-1、PM_IDLE legality、failure-at-end 可见性、bay occupancy、四轮 Pro-Max 语义审查、Human Gate 重新认证后，**仍为 0/100 有效偏离**。
- 因此按**预注册复杂度—收益筛选规则**（有效偏离门槛 + 成本约束）选择 **H1**。
- 措辞：**「未观察到稳定的边际决策收益」「未达到预设有效偏离门槛」「复杂度增加未转化为可验证的策略收益」**；禁止「H2 失败」「H2 无效」「复杂模型一定不如简单模型」。
