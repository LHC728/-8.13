# Q4 / G6 EXPERIMENT SPEC DRAFT（实验设计与预注册草稿）

> 状态：**DRAFT / PREREGISTRATION（F3 经 HG-Q4-F3-01 授权为假设性反事实敏感性；authority_conflict = RESOLVED_BY_HUMAN_GATE）**。本轮只设计、预注册，不正式跑大规模情景。
> 权威：问题契约 §5；项目计划 G6；Q3 FINAL CLOSURE（`05_结果/Q3/final_closure/`）；HG-Q4-H2-NA-01（`08_项目管理/任务包/Q4_H2_NA_01_ADDENDUM.md`）。
> 本轮授权：Q4 = **AUTHORIZED_FOR_DESIGN_AND_PREREGISTRATION_ONLY**（不得执行正式 Q4；不得消耗 Q4_EVALUATION random domain）。
> 正式执行须：本 spec 经 Pro-Max 设计审查（required actions 闭合）+ Human Gate 批准后另行授权。

## 1. 基准情景（baseline）

Q4 baseline 机械绑定 Q3 accepted 配置（**禁止重新拟合 baseline**）：

| 项 | 冻结值 | 来源 |
|---|---|---|
| 正式策略 | H1（固定 FCFS + 班历 + 立即启动合法队首） | Q3 FINAL MODEL SELECTION CLOSED |
| K baseline | **K12（12 h）** | Q3 accepted H1 formal（k\*=K12，seven-K + frozen policy set 范围） |
| H1 政策 | NO_PM_BEFORE_MANDATORY | Q2 主情景选中 + Q3 冻结 |
| 主周转 | 1 h（同槽顺序 0.5+0.5） | 问题契约（B05） |
| 故障语义（主） | 分段线性 CDF（等长年龄区间同无条件故障概率） | 问题契约 |
| 观测语义 | 当前 accepted 观测核（single_test_unconditional_v1 等冻结项） | Q3/H1 formal |
| mandatory replacement | 当前 H1 mandatory 规则（a+d>240 → MANDATORY_REPLACE_FIRST；==240 → complete-first） | Q3 冻结 |

Baseline evidence / config hash（机械绑定）：`05_结果/Q3/formal/run_20260815T133840057668Z_7ee48fc0`（K12 cell）+ provenance reissue `reissue_20260815T150613626910Z_f4da8f9d`（config snapshot / input_hashes 即 config hash 引用）；正式执行前在 Q4 包中固化 baseline run_id + manifest hash。

## 2. 机制时间账本（mechanism ledger）

按资源 **A/B/C/E** 分别保存（机制账本，**不是 T 的严格加法分解**——并行活动会重叠，**禁止写 `T = A时间+B时间+C时间+…`**）：

- `effective_test_time_j`：有效测试片段时长（按资源 j）
- `retest_time_j`：完成重测片段时长
- `failure_wasted_fragment_time_j`：中途故障作废片段时长
- `shift_boundary_wasted_fragment_time_j`：班界作废片段时长
- `terminal_cancelled_fragment_time_j`：终态取消片段时长
- `calibration_time_j`：更换—校准时长
- `turnover_occupancy_time`：台位周转占位时长
- `queue_blocking_time`：队列阻塞时长
- `active_wait_time`：主动等待时长
- `off_shift_time`：班外停工时长

账本用途：筛选候选重要因素 + 解释 sensitivity 结果（不用于构造 T 分解）。

## 3. 一级因素（level-1）

| ID | 因素 | 定义（预注册） | 执行约束 |
|---|---|---|---|
| F1 | K | `{9,9.5,10,10.5,11,11.5,12}` | **优先复用 Q3 accepted formal results**（`7ee48fc0` 各 K cell），不得无意义重跑；复用角色 = 「已冻结 Q3 因素 K 的已有正式证据」，非 Q4 新选择数据 |
| F2 | turnover | baseline 1.0 h vs 替代 0.5 h（完全重叠） | 优先检查已有 accepted compatible evidence（G3/B05 替代敏感性）是否可复用；不可复用才在 Q4_SCREENING 域补跑 |
| F3 | preventive replacement threshold | **AUTHORIZED_AS_HYPOTHETICAL_COUNTERFACTUAL_SENSITIVITY（HG-Q4-F3-01，Human Gate 2026-08-17：RA1 = OPTION B / ACCEPTED）**——作为模型内 what-if 因素改变预防更换阈值；计算相对正式 H1 baseline 的 paired Delta T；参与 Q4 数学因素影响排序；可支撑有条件的管理建议。**冻结边界（F3 may NOT）**：不得 reopen Q3 policy selection、不得替换 H1、不得改变 K\*、不得宣称「PM beats H1」、不得宣称新最优政策、不得成为 H2'、不得追溯修改 Q3 结论。正式策略保持 H1 / NO_PM_BEFORE_MANDATORY（UNCHANGED），K\*=K12（UNCHANGED）。 | 若未来需要改变正式 H1 policy family → `authority_conflict=true` → **HUMAN_GATE_REQUIRED**（不得自动运行） |
| F4-A/B/C/E | 各工序 duration 统一比例扰动 | 对称、简单预注册 levels（默认 ±10%；若仓库已有冻结 level 定义则优先使用冻结定义） | 不得偷偷调整 levels 使排名“好看” |
| F5 | failure semantics | 分段线性 CDF（主） vs 常风险率替代 | 只称**模型语义敏感性**，不称现实因果 |
| H2 | （historical） | **NOT_APPLICABLE_AFTER_H2_DELETE**（HG-Q4-H2-NA-01） | 禁止重新激活 H2 / H2' / 发明替代策略补因素数量 |

## 4. 二级因素 q / e（semantic propagation）

严格分开两种 q 语义：

- **Q-A（q = 标定输入不确定性）**：改变 q → **重新标定 alpha, beta** → A/B/C 先验 → q_E → E → 完整传播。
- **Q-B（q = 未来来料真实问题率变化）**：**冻结测手核** → 只改变真实问题率 → 完整传播。
- **e**：改变 e → **必须重新标定 alpha, beta** → 完整传播到 E。

**禁止**把 q / e / alpha / beta 作为 4 个相互独立因素。
本节属 YELLOW semantic risk（由 MMR Risk Card + Pro-Max 设计审查覆盖）。

## 5. 统计设计

- 主比较：**Common Random Numbers（CRN）paired Delta T**：
  `Delta T_r = T_scenario,r - T_baseline,r`（同一键控随机流）
- 报告：mean Delta T、SE、**95% CI**；必要时 standardized effect。
- 统计单位 = **batch replicate**；**禁止把 100 台设备当 100 个独立 replicate**。

## 6. selection / evaluation 隔离

预注册两个随机域：

- **Q4_SCREENING**：机制账本、粗筛、因素排序候选（只在此域消耗额度）。
- **Q4_EVALUATION**：冻结因素后的正式效应估计（**本轮不消耗；正式执行前冻结并另行授权**）。

两者 **replicate IDs 不重叠**。**screening 数据绝对排除在最终效应/CI 估计之外**（最终置信区间唯一证据来自 Q4_EVALUATION replicates；任何 pooling 都会引入 selection bias——措辞硬化，Pro-Max RA2）。
**禁止**使用 H2 tuning / H2 holdout / Q3 formal worlds 作为新 Q4 evaluation 数据。
允许复用 Q3 accepted K 结果，但角色必须明确为「已冻结 Q3 因素 K 的已有正式证据」。
**screening 前须预注册并冻结 Q4_SCREENING replicate-ID registry + manifest**（与 Q4_EVALUATION ID 不重叠机械可验证；Pro-Max RA3）。

## 7. 精度规则

- 不直接猜正式 repetitions：先设计小 pilot / screening 估计 paired Delta T 方差。
- 按预注册 **95% CI half-width** 确定 evaluation R；设置 `R_min` / `R_max` / target half-width。
- 具体数值：由现有项目统计精度规范 + pilot 后确定并冻结。
- **禁止**根据因素排名事后给不同因素随意增加 R 改变结果。

## 8. 因素排序

- 不使用 `|mean Delta T|` 粗暴排名。
- 预注册统一排序量（优先：**标准化效应 + CI + 实际可控性**作为管理层解释）。
- **「数学影响排序」与「管理实施优先级」必须分开**（某因素数学效应最大不代表现实中最值得花钱改）。

## 9. 两因素交互

- 只允许对 **SCREENING 后最重要的前 2 个一级可控因素** 做小型 interaction。
- **不得提前指定一定是 E/turnover**；不得对十几个因素做全组合。
- 允许 2×2 或 3×2；具体设计在 screening 后冻结。

## 10. 管理建议

每条建议必须绑定：`factor_id`、`scenario_id`、`Delta T`、`95% CI`、`effect rank`，并明确：建议内容、模型内收益、实施代价/约束、适用条件。
**禁止**把模型内敏感性写成现实因果定理。

---

### 本 spec 执行边界（PART E）

本包**禁止**：正式跑完整 Q4 sensitivity、消耗 Q4_EVALUATION、大规模 Monte Carlo、重跑 Q3、重调 H1、重开 H2/H2'、修改 accepted DES core、修改 Q3 K recommendation、为排名改 levels、提前跑 Top-2 interaction。
