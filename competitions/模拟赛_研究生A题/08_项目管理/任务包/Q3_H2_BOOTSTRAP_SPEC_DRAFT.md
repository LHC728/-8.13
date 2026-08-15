# Q3 + H2 ADVANCED SCHEDULING BOOTSTRAP — 设计规格草案（Human Gate 审核稿）

> 文档状态：**FINAL_FREEZE_ACCEPTED / HUMAN_GATE_PASS**（2026-08-15 Human Gate VERIFIED FINAL PASS / DESIGN FREEZE APPROVED；D-01..D-25 冻结；BOUNDARY 契约同步已完成；**H2 实现仍 NOT AUTHORIZED**；不授权任何实现或运行）
> 起草日期：2026-08-15（本版含 L4 裁决最小修订）
> 起草角色：Q3 Coordinator / Executor（D 层设计草案；不自我批准）
> 仓库检查点：`859bac97df42b37a467dc4f6f56e678932f305c1`（branch `g2-02-impl`）
> 独立审计：fresh semantic reviewer（`Q3H2_SEMANTIC_REVIEWER`；requested model = `deepseek-v4-pro`；reasoningEffort = **UNVERIFIED / adapter default not mechanically proven**）+ fresh E2 机械一致性（`Q3H2_MECHANICAL_CHECKER`；requested model = `deepseek-v4-flash`；reasoningEffort = **UNVERIFIED**）——审计记录见本文 §21 追加区；**未取得任何 child session 的 request/header 机械证据，不声称 verified**
> L4 独立设计裁决（Human Gate 转交，2026-08-15）：claimed/requested `deepseek-v4-pro/max`；**actual request-header verification not available here**（按 L4 第 10 条如实记录，不伪写 mechanically verified）——逐条处置见 §21.4
> cross-model review（Human Gate，2026-08-15）：**Q3/H2 BOOTSTRAP = CONDITIONAL PASS（NOT FINAL FREEZE；H2 实现仍 NOT AUTHORIZED）**——5 类修订处置见 §21.5
> final-freeze review（Human Gate，2026-08-15）：距 FINAL FREEZE 仅剩 3 项（PM_IDLE 决策点语义与 H1 baseline 动作 / Pro-high 身份证据去过度声明 / §22 标记 superseded）——处置见 §21.6；本轮仅最小文档修订 + 机械复核
> final-freeze VERIFIED review（Human Gate，2026-08-15）：**已直接审阅 587 行原文件**；FINAL FREEZE 仅剩 1 个 blocker（§2 quota selection 在线因果闭合 + D-08 一般化）——处置见 §21.7；本轮仅最小规格修订 + 机械复核
> **FINAL FREEZE LANDING（2026-08-15，Human Gate FINAL DECISION）**：Q3/H2 BOOTSTRAP = **VERIFIED FINAL PASS / DESIGN FREEZE APPROVED**；本文件 = 冻结权威规格（Human Gate 已直接审阅 623 行版本）；BOUNDARY 契约同步、H2 权威规格同步、CURRENT_STATE/CHANGELOG 落库见 §21.8
> 本文件所有「冻结」字样均指**本草案提议冻结、待 Human Gate 最终裁决**，未裁决前一律视为未冻结；已签字权威口径（G2/G3/Q2 accepted）不得因本草案改变。

---

## 0. 范围、状态基线与权威来源

### 0.1 本草案做什么 / 不做什么

**做什么**：形成 Q3 + H2 ADVANCED SCHEDULING BOOTSTRAP 的完整设计规格草案，覆盖 17 个必达项（rollout M、每批 H2 评估上限、墙钟软硬预算、动作稳定性、样本划分、随机命名空间/CRN、C23 信息边界、后验缺陷重采样、条件剩余寿命重采样、H2 动作集、strategic-wait 定义、optional PM / mandatory 区别、H1 fallback、Q3 七 K H1 基线实验、Q3 H2 密度复核、C25 保留/删除规则、正式输出/provenance），以及风险点与 Human Gate 决策清单。

**不做什么（本阶段边界）**：
- 不实现 H2 rollout / 后验生成器 / 任何 H2 代码路径；
- 不运行 H2 政策实验、不消耗新随机世界做 H2 调优；
- 不运行 Q3 七 K 正式实验、不推荐最优 K、不冻结任何 Q3 数字；
- 不修改已冻结 Q2/G3 accepted 结论（run `2d1466ba` 的 Q2 数字、tau_pm=198 的 FORMALLY_NOT_SELECTED 状态、G3 引擎语义等）；
- 不把本草案落成 accepted；不更新 `CURRENT_STATE.md` 为 accepted；
- 不写论文正式结果。

### 0.2 权威来源（本草案唯一语义来源；禁用 99_归档/旧评审/聊天摘要补默认值）

1. `AGENTS.md`（项目级）与 `CURRENT_STATE.md`（仅阶段事实）
2. `01_审计/问题契约.md`（题意/状态/指标实质定义；§4 Q3、§7 冻结输入）
3. `01_审计/检查注册表_V3.1.md`（C15/C16/C23/C24/C25/C26 语义）
4. `01_审计/关键歧义与候选约定.md`（A03/A05/A08/A09、B05/B10/B16/B17/B18/B19 已签字口径）
5. `01_审计/H2_ADMISSION_C24_EVIDENCE_DRAFT.md`（机会密度证据；旧 `waiting_opportunity_count` 为 forced-wait 仪表，**不得复用为 H2 密度**）
6. `02_数据/parameters.csv` 与 `02_数据/configs/README.md`（P016/P017/P038-P042/P048/P049/P059/P060-P064）
7. `03_模型/00_模型总览.md`、`02_H1基线与离散事件模型.md`、`03_H2后验Rollout候选.md`、`高级模型技术补充_V3.1.md`（§5 H2 模块）
8. `08_项目管理/任务包/G3_公共随机DES与H1基线.yaml`（key_schema_v1、六命名空间、C26、数据分离、C16/C24）
9. `08_项目管理/任务包/Q2_单班制H1正式评估.yaml`（正式运行/统计/证据契约样板）
10. `08_项目管理/模型分级与任务路由规则.md`、`全流程自动推进计划_AUTOPILOT-PLAN-V1.1.md`
11. 已 accepted 上游接口：`random_des_v1.py`（决策点结构 `_equipment_and_dispatch`）、`key_schema_v1.py`（canonical 键、六命名空间 + `h2_future` reserved）、`h2_admission_opportunity_analyzer_v1.py`（STRICT/BOUNDARY/NONSTRICT 定义）

### 0.3 冻结状态基线（本草案引用的不可变事实）

- Whole G2 = PASS / ACCEPTED；G3 = PASS / ACCEPTED；Q2 H1 FORMAL = PASS / ACCEPTED（accepted run `run_20260815T061803446274Z_2d1466ba`）。
- **Q2 主情景 H1 政策 = `NO_PM_BEFORE_MANDATORY`**（正式选择；tau_pm=198 = HISTORICAL_TUNING_SELECTED_CANDIDATE / FORMALLY_NOT_SELECTED_FOR_Q2_PRIMARY，不宣称最优）。
- H2 = **ADMITTED_FOR_DESIGN_ONLY**（Human Gate 2026-08-15；非 FINAL ACCEPTANCE；实现 NOT YET AUTHORIZED）。
- C24：opportunity-density evidence = PASS；budget/spec freeze = PENDING；C23 = PENDING；C25 = PENDING；Q3 = NOT STARTED。
- 机会密度（仅 density，NO_PM / G3 tuning 20 批）：legal dispatch ≈ 413.1/批、strategic wait strict ≈ 11.4/批（~2.8%）、optional PM feasible ≈ 168.8/批（~41%）、both ≈ 4.5/批、meaningful fraction ≈ 0.429、零机会批次比例 0%。
- Q2 accepted 分析流样板：`namespace=q2_formal_analysis_bootstrap_v1`、seed=30003、B=10000（仅重采样批次索引，不影响 DES 物理流）。
- 六不相交实验命名空间（G3-SPEC-V1.0 冻结）：`development_unit / pilot / h1_tuning / g3_holdout / q2_formal / q3_formal`；H2 流为 reserved only（`h2_future`），**新增 H2 命名空间属 key_schema 扩展，需 Human Gate 批准（见 §6/D-05）**。
- 引擎决策点（accepted，不动）：`_equipment_and_dispatch` 内每个「资源空闲 + 设备可用 + 队列非空 + 队首 WAITING + 活跃班内」闭包恰一个决策点（`_c24_decision_points`）。**H2 层另增 `MAINTENANCE_DECISION_POINT`（§10，仅 H2 激活时存在；H2 删除后无残留）**，覆盖 queue-empty 与 queue-nonempty-but-no-legal-head 的 PM_IDLE 状态；不改 accepted 引擎核心语义。
- Q3 已签字口径：A08（两班各 K h、停工 24−2K h、班末禁启为操作约束、七点全枚举、不称 K=12 弱支配）、A09（完全重置）、B10（YXB 分母使用 K）、B17（两队同核）、B19（跨队全局 FCFS、待重测保留原 release_time 与 attempt=2）。

---

## 1. rollout M 候选与选择依据

### 1.1 估计量（冻结，不改写）

决策点 s、候选首动作 a 的 rollout 值（`03_H2后验Rollout候选.md` §3 / R46，候选动作共享同一续演样本）：

\[
\widehat Q_M(s,a)=\frac1M\sum_{m=1}^{M}\left[T_{end}^{(m)}(s;\,a\to \mathrm{H1})-t(s)\right]
\]

- 每个续演世界 m 从**可观察后验状态**克隆重建（§7/§8/§9），以 H1 基线政策（Q3 主基线 = `NO_PM_BEFORE_MANDATORY`，§14）推演到本批吸收；吸收态剩余值为 0，**禁止截断零尾值、禁止有限视野**（R46）。
- 同一决策点 s 的全部候选动作共享同一组 M 个续演世界（跨动作 CRN，§6），因此动作差 `D_m = T_end^{(m)}(a) − T_end^{(m)}(a_H1)` 是配对差。**`a_H1`（H1 基线动作）对每类决策点都有定义（§10）**：dispatch decision point → `A0=START_HEAD`；maintenance decision point → `A0b=H1_NOOP / ADVANCE_EVENT`（无合法队首时的 H1 默认续演）；**禁止拿 `PM_IDLE` 与不合法的 `START_HEAD` 比较**。
- M 与续演子流键完全解耦：子流键只由（§6 的 `rollout_seed(dp, m)`）决定，M 变化只改变取均值的世界数，**不改变任何物理世界**。

### 1.2 M 候选集与选择规则（冻结，禁止实现者自选）

- **候选网格（M, C_eval）冻结为三个点**：`(4, 8)`、`(8, 6)`、`(8, 8)`（C_eval 定义见 §2）。最坏情形 rollout 数 = C_eval × 3 动作 × M = 96 / 144 / 192，均 ≤ 每批硬上限 `C_rollout = 200`（§2）。
- **选择规则（成本导向、非结果导向，预注册）**：在 `h2_tuning` 命名空间（§5）前 5 批（replicate_ids 0..4，K=10.5）上测量中位单次 rollout 墙钟 `c_r`（引擎-only，不含 C06/C17）；对每个网格点计算最坏情形每批墙钟 `w_p = base + (C_eval×3×M)×c_r`（base = 该批无 rollout 的引擎墙钟，同批测量）；选择**最大的 M**（M 相同取更大 C_eval）且满足 `w_p ≤ 90 s` 的点作为冻结 (M*, C_eval*)；若三点均不满足 → 记为 **H2_BUDGET_INFEASIBLE → H2 删除**（预注册触发，不静默放宽）。
- **M 的统计依据（为什么 4–8 量级）**：单点每批 T 的续演噪声 σ 约为批量级（Q2 正式证据：政策级配对 ΔT≈1.3 h/批、SE 达亚小时量级），单点动作效应亚小时级；M∈{4,8} 下 SE_M = σ/√M 仍大于单点效应，因此**单点决策不能依赖显著性**——H2 只在「自信偏离」阈值下偏离（§4，δ=2·SE_M），单点噪声在批内多决策点间平均化，最终由批级配对 C25 检验裁定（§16）。M 更大（16/32）使每批可评估点数下降（预算不变）或超 C_rollout 硬上限，覆盖损失大于方差收益。
- **M=8 不满足时的处置**：选择规则已覆盖（降为 (8,6)/(4,8) 或删除）；**禁止**事后按结果好坏重选 M、禁止在 holdout/formal 上重校。

### 1.3 M 充分性验证（并入 §4 离线稳定性诊断）

M* 充分性验证 = §4 (b)(c) 的**离线诊断样本**（定义与样本规则见 §4）：来源只能是 `h2_tuning`；不驱动 holdout/formal 选择；不受在线政策 `C_eval*` 上限约束；其 rollout 计算量与墙钟计入 §3「H2 开发预算账本」；采样顺序/分层确定性冻结；报告实际样本数。失败（含样本不足）→ H2 删除。

---

## 2. H2 每 batch 最大 evaluation cap

- **决策点评估上限**：`C_eval*`（来自 §1.2 选择，∈ {6, 8}）——每批内执行 rollout 前瞻的 H2 决策点数硬上限。
- **rollout 模拟硬上限**：`C_rollout = 200`（次/批）——runner 以**计数不变量**强制：实际 rollout 数超过 200 → 验证失败（FAIL，不是静默截断）；`C_eval*` 超限同理。（离线点级诊断如 §4(c) 的 2M* 参考运行、§15 的重放分析不受此计数约束。）
- **每批墙钟护栏**：600 s（诊断记录；系统性超时触发 §3 预算检查，不自动判错）。
- **决策点选择规则（冻结、结果无关、确定性、**在线因果闭合**；含 B-3 归属规则；final-freeze VERIFIED review 第 1–3 条）**：
  - 「H2 可选」决策点 = 至少存在一个非 H1 动作：**dispatch decision point**（该资源存在合法队首）上的 wait-legal（STRICT/BOUNDARY，§11）或 `PM_WITH_HEAD`，以及 **maintenance decision point**（该资源无合法队首、设备 idle+age≥120+非 mandatory+未来需求+校准可完成，§10）上的 `PM_IDLE`。
  - **B-3 唯一确定性归属（冻结）**：一个决策点**只能拥有一个 quota class**；同时满足 wait-legal 与 PM-eligible 的 both 点，**wait classification 优先**（计入 wait 配额，不重复计入 PM 配额）；PM 配额只从 **PM-only 候选** 中产生（maintenance 点天然 PM-only；dispatch 点中 wait 不合法者亦为 PM-only）；**禁止重复计数**。
  - **ONLINE HARD CAPS（冻结）**：`W_cap = ⌈C_eval*/2⌉`、`P_cap = ⌊C_eval*/2⌋`（**C_eval*=6 → W_cap=3, P_cap=3；C_eval*=8 → W_cap=4, P_cap=4**）。两侧配额为**独立在线硬上限**：
    - **wait 未用额度不得借给 PM，PM 未用额度不得借给 wait**（无跨侧事后 borrowing）；
    - 未使用额度在 batch 结束时**直接失效**（C_eval* 是最大 evaluation 数，**不要求每批必须凑满**）；
    - 每个 decision point 是否 rollout **必须在该点发生时**、**仅根据当前/过去的 observable history 与当前 quota state** 决定：`selected_for_rollout(t) = f(history ≤ t, quota_state(t))`（纯函数）；**禁止读取未来 candidate count / 未来年龄桶是否出现；禁止 batch 结束后回溯补选历史 decision point**。
  - **wait 侧在线规则（冻结）**：按事件发生时间在线选择前 `W_cap` 个 wait-class 决策点（含 both 点）；达到 W_cap 后，后续 wait-class 点不再 rollout；**不得因未来 PM 数量不足而回溯增加 wait quota**。
  - **PM 侧在线规则（冻结，无事后 backfill）**：保留三个年龄桶 `B1=[120,160)`、`B2=[160,200)`、`B3=[200,240)`，**每桶至多保留 1 个 bucket-first slot**：
    - 某桶**首次**出现 PM-only decision point 时，若该桶 slot 尚未使用 → **立即 evaluate 并占用该 slot**；
    - `P_cap = 4` 时**另有且仅有 1 个 extra PM slot**：第一个「其所属 bucket-first slot 已经使用、且 PM 总 cap 尚未耗尽」的**后续** PM-only 点，在其发生时**立即**占用 extra slot；`P_cap = 3` 时**无 extra slot**；
    - 某年龄桶整批未出现 → 其预留额度**直接失效**；**不跨桶事后回补、不回溯历史点、不读取未来年龄桶是否出现**。
  - checker 必须**独立复算** quota class、`dp` 索引与 selected set（与主实现异源），并断言：无重复计数、无配额越界、**`wait_selected ≤ W_cap`、`PM_selected ≤ P_cap`、`selected_total ≤ C_eval*`**（含配置断言 C_eval*=6 → 3+3、C_eval*=8 → 4+4），且 **`selected_for_rollout(t)` 只依赖 history ≤ t**（causality 断言：构造「截至 t 完全相同、t 之后 candidate 序列不同」的两份历史，断言 t 处 rollout selection 完全相同；§22.3）。
  - **quota class ≠ 动作可用性（澄清，cross-model review 第 1 条）**：quota class 只是**决策点采样分类**，不影响该点本来的合法动作集；both 点即使归入 wait quota，其在该点本合法的 PM 动作（`A2a`/`A2b`）仍在该点动作集中参与 §4 决策。
  - 禁止按结果/按 T 影响事后挑选决策点。
- 覆盖率声明（论文边界）：H2 仅在每批 ≤ C_eval* 个可选点上偏离 H1，政策级效应受覆盖率限制；C25 检验即在此覆盖率下进行，**不声称全决策点 H2**。

---

## 3. soft / hard wallclock 预算

- **阶段墙钟预算：soft 4 h / hard 8 h**（沿用 G3/Q2 冻结惯例；从本阶段实施启动时刻起算，不含本设计阶段）。
- **工作优先级（预算检查点顺序，冻结）**：
  1. Q3 H1 基线 Tier 1（§14，必须完成）；
  2. Q3 H1 基线 Tier 2（§14，契约必做，必须完成）；
  3. Q3 H2 密度复核（§15，廉价、从 Tier 1 日志重放，必须完成）；
  4. H2 调优/校准/稳定性验证（h2_tuning，§5）；
  5. H2 holdout（h2_holdout，C25 + 论文 H2 表，§5/§16）；
  6. Q3 H1 基线 Tier 3 稳健性（§14，**可选，soft 预算到达即最先丢弃**）。
- **soft 4 h 到达**：停止一切非必要工作（Tier 3、额外 reviewer、可选敏感性、非必需重跑），只继续必需验收与正式工作。
- **hard 8 h 到达**：无条件停止并回 Human Gate；**若停止发生在 h2_holdout 完成之前 → H2 = NOT RETAINED（预注册结论）**；Q3 H1 Tier 1/2 证据不受影响。
- 禁止为赶预算削减已冻结重复数/样本量/检查强度；禁止自行提高预算。
- **H2 开发预算账本（冻结）**：所有**离线诊断**（§4 稳定性样本、§4.1 跨 K transfer、§8/§9 生成器验证、§1.2 成本测量）的 rollout 计算量与墙钟必须逐项入账（`05_结果/H2/dev_budget_ledger.json`），并计入阶段墙钟预算（soft/hard 之内）；离线诊断不受每批在线 `C_rollout=200` 计数约束，但**墙钟必须入账**，禁止以「离线」名义绕过预算。
- 规划估计（非权威、非 manifest 证据；正式墙钟以 §17 实测量为准）：Q2 accepted manifest 记录族级墙钟 ≈ 0.34 h（1600 批含 C06+C17，≈ 0.77 s/批）→ 引擎-only 单批推断 ≈ 0.2–0.6 s；Tier 1+2 ≈ 2800 批 ≈ 0.5–1.5 h；h2_tuning ≈ ≤0.5–1 h；h2_holdout 140 个 H2 批 × ≤90 s ≈ ≤3.5 h；含 Tier 3（1400 批）的最坏全族路径 ≈ 5–7 h。正式 runner 须把真实逐批/逐单元/族总墙钟写入证据（§17）。

---

## 4. action stability criterion（动作稳定性准则）

四支判定，全部预注册；任一失败 → H2 删除：

- **(a) 确定性（恒成立项）**：相同（世界、配置、代码、键）→ 相同动作；由键控流与纯函数实现保证，并在 C23 检查中验证「相同可观察历史 → 相同动作」。
- **(b) 续演种子稳定性（h2_tuning，离线诊断）** 与 **(c) M 秩稳定性（h2_tuning，离线诊断）**：样本与执行规则统一冻结为 **B-1 离线诊断样本**：
  - **来源**：只能是 `h2_tuning` 日志（replicate 0..9，K=10.5）；
  - **不驱动** holdout/formal 选择；**不受在线政策 `C_eval*` 上限约束**（离线重评估，非批内在线 rollout）；
  - **采样规则（确定性冻结）**：从 tuning 批 0..9 的全部 H2 可选决策点中，按「批升序、批内时间序」各取前 50 个 wait-eligible（含 both 点）与前 50 个 PM-eligible（PM-only），构成**目标样本 100 点**；某类型不足 50 则取该类型全部并从另一类型按冻结序补足；总样本上限 120；**实际样本数 n 必须报告**；若 n < 50 → 样本不足 → H2 删除（预注册）；
  - **墙钟**：本诊断的 rollout 计算量与墙钟计入 §3 H2 开发预算账本（离线，不受 C_rollout 计数约束但必须入账）；
  - **阈值与报告（语义闭合，cross-model review 第 4 条）**：**agreement 点估计 ≥ 95% = Human Gate 预注册工程阈值（本诊断唯一硬门）**；95% Clopper–Pearson 区间**必须报告，但仅为 uncertainty disclosure，不是独立 pass/fail 门**——本轮**不新增「CI 下界 ≥ 95%」第二硬门**（除非 Human Gate 后续另行批准）。同时必须报告 **H2 对 H1 的实际 deviation rate**（偏离决策点 / 评估决策点）与 **actual n**；若 deviation rate = 0，表示 H2 在该诊断域未表现出区别于 H1 的有效动作证据，按冻结 H2 admission/fallback 规则（§13/§16）处理，不视为稳定 PASS。
  - (b) 使用第二冻结分析盐 `ROLLOUT_ALT_SALT`（§6.2）重派生续演种子重评；(c) 用 M* vs 2M* 重评 argmin 动作；两者均要求动作选择一致率 ≥ 95%。
- **(d) 政策级符号稳定（h2_holdout，预注册推断稳健性）**：配对 ΔT = T(H2) − T(H1) 的符号在两个独立分析 bootstrap 种子（40007 / 40008，见 §5 表与 §16）下**每个 K 都不翻转**。
- **偏离阈值（冻结）**：决策点 s 上，仅当 `argmin_a Q̂_M(s,a) = a* ≠ a_H1(s)` 且 `Q̂_M(s,a*) < Q̂_M(s,a_H1) − 2·SE_M(s, a* vs a_H1)` 时 H2 偏离 H1；其中 **`a_H1(s)` = 该决策点类型的 H1 默认动作**（dispatch decision point → `A0=START_HEAD`；maintenance decision point → `A0b=H1_NOOP / ADVANCE_EVENT`，§10）；`SE_M` 为 M 个配对差 `D_m` 的样本标准差 / √M。否则执行 H1 默认动作。该规则使 H2 ≈「仅在 rollout 自信时才偏离」，噪声由 C25 批级检验兜底。
- **数据域边界（C16/R38）**：M/阈值选择与 (b)(c) 稳定性验证**只允许使用 h2_tuning**；h2_holdout **仅**用于 (d) 预注册符号稳健性与 C25 推断，永不参与任何 M/阈值/动作选择；q3_formal 永不参与 H2 任何环节。

### 4.1 跨 K action-transfer diagnostic（预注册诊断 / 早期预警，非 C25 替代；cross-model review 第 2 条）

- **目的**：验证在 K=10.5 上确定的**统一 H2 设计**（M*、C_eval*、动作集、偏离阈值）是否发生明显跨 K 结构不稳定；**本项目不采用 seven separate per-K H2 tuning**（复杂度/过拟合控制，L4 第 5 条）。
- **d_K 定义（冻结）**：`d_K` = 在 `h2_tuning` 世界的相同 replicate physical worlds（0..14）、K 班历配置下，统一 H2 政策离线重放时**评估决策点中偏离 H1 的占比**（偏离 = §4 自信偏离规则触发）；同时报告偏离类型的构成（wait / pm_with_head / pm_idle）与 agreement rate。**单一 deviation rate 相同不保证发生偏离的是相同类型决策**，故本诊断必须结合偏离类型构成一起解读。
- **执行（只读/离线）**：同 replicate worlds × 7 K 班历；来源仅 h2_tuning；墙钟计入 §3 H2 开发预算账本；不驱动 holdout/formal 选择；结果入 `05_结果/H2/tuning/`（非论文数字）。
- **带宽 0.10 = Human Gate / DESIGN CHOICE（非数学必然）**：`|d_K − d_{10.5}| ≤ 0.10` 是预注册**早期预警带**，**不得仅凭单一比例超带即自动宣称统计失败或自动 DELETE H2**。
- **定位（冻结）**：本诊断 = **PRE-REGISTERED DIAGNOSTIC / EARLY WARNING**，**不替代 C25 的最终收益硬门**；正式 H2 retain/delete 的核心统计门仍为 **C25**（配对 holdout 改进、simultaneous CI、action stability、budget、C23，§16）。
- **不稳定时路由（冻结）**：若诊断显示**明显结构不稳定**（如多个 K 超带、wait/PM 偏离类型构成翻转、agreement 崩塌），返回 **Human Gate 裁决**，或按预注册路线 **DELETE H2 / RETURN TO H1**；不以单值自动判失败、不自动调阈值。
- **禁止**：为跨 K 适配而临时进行 seven separate per-K tuning；看到结果后按 K 临时改任何规则/阈值/动作集。

---

## 5. tuning / holdout / formal 样本划分

| 用途 | namespace（新，需 D-05 批准） | master_seed | replicate_ids | K | 批数 | 允许/禁止 |
|---|---|---|---|---|---|---|
| Q3 H1 正式（论文 Q3 唯一权威） | `q3_formal`（已预留） | 5 | 0..199 | 全 7 K | 200/单元×族（§14） | 禁用于 H2 任何环节 |
| Q3 H2 密度复核 | 重放 Q3 H1 Tier 1 accepted 日志 | — | — | 全 7 K | — | 只读重放，无新随机世界 |
| H2 M/C_eval 校准 | `h2_tuning` | 6 | 0..14 | K=10.5 | 15（其中 replicate 0..4 兼作 §1.2 成本测量） | 禁入论文数字 |
| H2 动作稳定性（离线诊断，§4 (b)(c)）+ 跨 K transfer（§4.1） | `h2_tuning` | 6 | 稳定性 0..9；transfer 0..14 | 稳定性 K=10.5；transfer 全 7 K | 离线重评估（目标样本 100 点，n<50 删除）；rollout 墙钟计入 §3 开发预算账本 | 禁入论文数字；不驱动 holdout/formal |
| H2 后验/寿命生成器验证（§8/§9 校准） | `h2_tuning` | 6 | 0..4（子集） | K=10.5 | 按 §8/§9 冻结模式与样本数 | 同上 |
| C25 准入 + 论文 H2 表（预注册双职） | `h2_holdout` | 7 | 0..19 | 全 7 K | 每 K 20 H2 + 20 H1（同 id 双政策 CRN 配对），7 K 共 280 批；§3 预算按 140 个 H2 批计（H1 配对批近零成本） | C25 与正式 H2 表共用；禁用于任何调优/选择 |
| Q3 H1 分析流 | `q3_formal_analysis_bootstrap_v1` | 40003 | — | — | B=10000 | 只重采样批次索引 |
| H2 分析流 | `h2_holdout_analysis_bootstrap_v1` | 40007（稳定性用 40008） | — | — | B=10000 | 只重采样批次索引 |

- **Q3 H1 无调优、无 holdout**：H1 政策为冻结 Q2-accepted 主政策（§14），禁止在 Q3 上重开 C26 网格/局部细化（选择/正式分离）。
- **命名空间禁碰撞**（C16）：`development_unit / pilot / h1_tuning / g3_holdout / q2_formal` 在本阶段一律只读引用，不得写入、不得复用其 replicate/seed 池；旧 `waiting_opportunity_count` 仪表不得充当 H2 密度。
- **h2_holdout 的 H1 配对批**：与 H2 批同 replicate ids、同 namespace（策略不同），构成批级 CRN 配对（§6）。
- R38 边界：调优/校准值（h2_tuning）永不为论文数字；h2_holdout 仅承担 C25 与预注册 H2 表；q3_formal 仅承担 Q3 正式数字。

---

## 6. randomness namespace / CRN 设计

### 6.1 key_schema 扩展（需 Human Gate 批准；不改 frozen 语义）

- `key_schema_v1` 的 canonical 键串、字段序、U 映射公式（SHA256→uint64_be→Fraction）、六个既有命名空间**逐字节保持不变**（扩展后跑字节兼容回归：既有命名空间的全部既有键重新生成逐字节一致）。
- 新增命名空间（字面量冻结）：`h2_tuning`、`h2_holdout`、`h2_rollout`；`h2_future` 占位保留为历史注释。
- 新增流（仅 H2 代码路径使用；G3 引擎永不消费）：`U_X_post`（后验缺陷重采样）、`U_D_post`（D 后验/先验重采样）、`U_Y_post`（续演观测）、`U_L_post`（续演剩余寿命）。**禁止**把 policy/action/run_id/execution_no/squad_id/worker 注入物理键（沿用 frozen forbidden 清单）。

### 6.2 续演子流键（冻结公式，精确有理数）

- 决策点索引 `dp` = 本批内**已评估的 H2 决策点序号**（0 基，单调递增，纯函数于（世界、历史、配置、代码））。
- 续演世界种子（每 (dp, m) 一个）：`rollout_seed(dp, m) = uint64_be(SHA256(UTF8("h2_rollout|" + str(master_seed_h2) + "|" + str(replicate_id) + "|" + str(dp) + "|" + str(m) + "|" + ROLLOUT_SALT))[0:8])`；`master_seed_h2` = 6（tuning）/7（holdout）所在批；`ROLLOUT_SALT` = 冻结字面量（草案值 `"q3h2-bootstrap-v1"`）；备选盐 `ROLLOUT_ALT_SALT` = `"q3h2-bootstrap-alt-v1"`（仅 §4(b) 稳定性用）。
- 续演键 = canonical 键构造：`key_schema_v1 | rollout_seed(dp,m) | h2_rollout | replicate_id | entity_id | process_or_subsystem | attempt_or_generation`，按各流语义填槽（`U_X_post`/`U_D_post`/`U_Y_post` 的 attempt 槽、`U_L_post` 的 generation 槽；`U_Y_post` 只由有效完成消费，中断/取消/班界/未启动不消费——沿用 NO_OBSERVATION_CONSUMED_BY）。
- **CRN 规则**：同一决策点 s 的**全部候选动作共享同一组 M 个世界**（种子不含动作）；不同决策点种子不相交；同批内不同 K（仅 holdout 配对批）共享 replicate_ids；`h2_rollout` 与 `q3_formal`/`h2_tuning`/`h2_holdout` 的物理流完全不相交。
- 正式/调优/留出三套 H2 世界不可互串（C16）。

---

## 7. C23 observable-information boundary

- **可观察状态 S（H2 可读全集，冻结）**：`(t, n, {h_b}_{b=1..2}, {r_j, a_j, ℓ_j, g_j}_{j∈{A,B,C,E}}, 队列与 FCFS 键, release_time, 有效尝试号, 各装置已完成观测序列, D 是否已联接, 终态, 班历/值班分队)`——即 `高级模型技术补充_V3.1` §5.1 的 S，全部来自事件日志/可观察字段。
- **可观察字段白名单（冻结，L4 第 4 条）**：H2 policy / posterior / rollout **只能**通过冻结的 `PosteriorState` / `ObservableState` 接口读取下列字段（其余一律拒绝）：时间与班历、尚未进入装置数 n、台位占用/周转状态、各资源状态（空闲/在测/故障/更换/校准）、设备年龄 a_j、在途剩余时长 ℓ_j、代次 g_j、队列条目与 FCFS 键（`release_time, device_id, process_order, effective_attempt_no`）、各装置已完成尝试的观测结果序列与有效尝试号、D 是否已物化（仅布尔标志）、装置终态、值班分队、已完成更换/校准历史。
- **禁止读取/解析（冻结清单）**：H2 不得直接读取或解析任何含 live hidden information 的原始 DES 对象/日志字段，包括但不限于：`true_state`、`x_A/x_B/x_C/x_D`、live `U_L`、live lifetime、future observation U、**u_key 中可恢复未来信息的字段**（原始键材料一律不进入 ObservableState）、`is_right_censored` 的未来实现信息、未物化 D 真值。禁止「按事件执行顺序取随机数」。
- **强制分离实现**：主 DES 的隐藏字段（`device.true_state`、`equipment.lifetime` 等）**不进入** H2 策略接口；H2 只接收 `PosteriorState`（可观察投影 + 后验对象，§8/§9）。续演世界**必须**从后验重建，禁止深拷贝 live hidden world（R45）。
- **相同观察史 ⇒ 相同动作**：H2 策略是（可观察状态、配置、键）的纯函数。
- **独立 checker 规划（冻结，L4 第 4 条）**：① **字段白名单检查**——对 `ObservableState`/`PosteriorState` 接口做字段级静态核对，断言其只暴露白名单字段；② **import/AST 隔离**——H2 模块不得 import 主 DES 内部状态类/隐藏字段访问路径，checker 用 AST/import 静态扫描断言隔离；③ **same-observed-history / different-hidden-world 动作逐位一致测试**——人为构造多份隐藏世界不同、可观察历史相同的日志，断言 H2 动作输出逐位一致。
- **wait 锚有限且取消即重判**：WAIT 只锚定一个已排定的同装置完成事件（§10/§11）；事件发生后（或任何使其失效的事件闭包后）立即重判，等待期间事件日历非空（C18），禁止永久饥饿（R40）。
- **C23 检查器独立性**：独立实现后验/条件寿命/动作边界复算，不导入主 DES transition；共享只读 canonical 参数与 schema（C19 原则）。

---

## 8. posterior defect-state resampling 规则（冻结）

- **先验**：`x_j ~ Bernoulli(q_j)`（j=A,B,C，P026–P028），`x_D ~ Bernoulli(q_D)`（P029，联接时生成一次）；跨子系统/跨装置独立（主基线联合分布，B12）。**E 不是独立子系统**：E 是整机二元检测，其观测核只依赖事件 `H={A,B,C,D 缺陷集合} 非空`——`α_E = P(Y_E=1 | H=∅)`、`β_E = P(Y_E=0 | H≠∅)`（冻结观测核）。
- **单子系统观测似然（A/B/C）**：对装置 i、子系统 j 的已完成有效尝试观测序列 `obs_{i,j}`，

\[
L_j(obs\mid x)=\prod_{\text{attempt}}\begin{cases}1-\alpha_j,\; Y=0;\ \alpha_j,\; Y=1 & x=0\\ \beta_j,\; Y=0;\ 1-\beta_j,\; Y=1 & x=1\end{cases}
\]

（α_j、β_j 取冻结观测核；`Y=1` 为异常。）
- **E 观测似然（冻结）**：逐次有效 E 尝试，H 非空时 `P(Y_E=1)=1-β_E、P(Y_E=0)=β_E`；H 空时 `P(Y_E=1)=α_E、P(Y_E=0)=1-α_E`。**E 观测不直接测 x_D**，只测「装置有缺陷」这一事件。
- **联合后验（精确 Fraction 贝叶斯，冻结公式）**：给定装置 i 的全部观测 `obs=(obs_A,obs_B,obs_C,obs_E)`：

\[
P(x_A,x_B,x_C,x_D\mid obs)\;\propto\;
\left[\prod_{j\in\{A,B,C\}} q_j^{x_j}(1-q_j)^{1-x_j}\,L_j(obs_j\mid x_j)\right]
\cdot q_D^{x_D}(1-q_D)^{1-x_D}
\cdot L_E\!\big(obs_E\mid \mathbf 1\{H\neq\emptyset\}\big)
\]

  续演按该联合分布分层采样：
  1. 先采 (x_A,x_B,x_C)：把 x_D 从联合中积分掉（E 似然对 x_D 求和）后按三子系统联合后验采样；
  2. 再按 `P(x_D\mid obs,x_A,x_B,x_C) \propto q_D^{x_D}(1-q_D)^{1-x_D}\cdot L_E(obs_E\mid \mathbf 1\{H\neq\emptyset\})` 采样 x_D。
  推论（必须一致实现）：若 `H_{ABC}` 已非空，E 观测对 x_D **无信息**（`P(x_D=1|·)=q_D`）；只有 `H_{ABC}=∅` 时 E 观测才更新 x_D。
- **装置级规则（冻结）**：
  - 已终态（通过/退出）装置：吸收，不重采样（不再影响调度）；
  - 未进入大厅装置：续演中按先验采样（A/B/C/D 各先验）；
  - 未到达 E 的装置（A/B/C 未全通过或 E 未启动）：无 `obs_E`；D 在真实世界未物化；续演中**仅在续演到达联接点时**按先验 q_D 物化一次（禁止在提前退出装置上反事实生成 D，P046/PW 语义一致）；A/B/C 按各自 obs 后验；
  - 已到达 E 的装置：按上述联合后验采样（**A/B/C 边缘后验亦受 obs_E 影响**，因 E 观测与「H 非空」相关）；
  - 在途无结果尝试不进入后验更新（中断/取消无观测，B02）。
- **续演采样**：每个世界 m 对每台相关装置按联合后验独立采样（`U_X_post`/`U_D_post` 键，§6.2）；采样分布只依赖可观察历史（相同历史 → 相同分布）。
- **生成器验证（两层，冻结；L4 第 9 条 + cross-model review 第 3 条）**：
  - **A. PRIMARY DETERMINISTIC CHECK（主门；独立 checker）**：对冻结测试历史模式（**全部可达模式**：`obs_j ∈ {∅, [N], [A], [A,N], [A,A]}`（j=A,B,C；[N]=初测正常、[A]=初测异常待重测、[A,N]=重测通过、[A,A]=退出）、`obs_E ∈ {∅, [N], [A], [A,N], [A,A]}`，受冻结流程可达性约束（`obs_E` 非空 ⟹ A/B/C 均以 N 结尾有效通过；任一 `obs_j=[A,A]` ⟹ 装置退出 ⟹ `obs_E=∅`）；总数 ≤625，由**确定性冻结枚举器**生成并与 checker 对拍），独立 checker **不调用/不导入** implementer 后验核心函数，自行计算**完整后验概率向量**（装置已到 E 且有 `obs_E` → 16 状态 `(x_A,x_B,x_C,x_D)`；未到 E → 8 状态 `(x_A,x_B,x_C)`，D 未物化不参与），**逐状态**与 H2 posterior module 输出对拍；容差冻结：**逐状态 |Δ| ≤ 1e-12（绝对概率）**（两边均为精确 Fraction 时应逐位相等）。
  - **B. SECONDARY STOCHASTIC SMOKE TEST（烟测，非硬门）**：Monte Carlo 分布检查定位为 sampler smoke test，**不使用「数千格各自 ≤2pp」的未校正大规模硬门**（multiplicity 不可控）；统计协议全部冻结：代表性子集 = **8 个核心模式**（单工序 5 模式 `{∅,[N],[A],[A,N],[A,A]}` 以 A 工序为代表 + E 层 3 模式（ABC 全通过且 `obs_E ∈ {∅,[N],[A]}`））；每模式重采样 **N=5000**；统计量 = 逐（模式, 子系统）边际 `z = (p̂−π)/√(π(1−π)/N)`（π=解析边际后验），共 4×8=32 个；**接受判据（multiplicity treatment 冻结，全局判据）**：`#(|z| > 3.5) ≤ 1`；同时报告全部 z、p̂、π 与实际样本数。同历史 → 同分布；独立 checker 用同式复算。

---

## 9. residual lifetime conditional-survival resampling（冻结）

- **对象**：仅**当前代**设备（过去代次寿命已观测，属可观察历史，不重采样）。
- **条件生存**：对存活至年龄 a 的设备 j，剩余寿命 τ 的后验分布 = 条件生存分布（主情景分段线性 CDF，P018–P025，`F_j(t)` 精确分段线性）：

\[
P(L_j-a_j>u\mid L_j>a_j)=\frac{1-F_j(a_j+u)}{1-F_j(a_j)},\quad u\ge 0
\]

- **重采样（精确条件分位，冻结公式）**：设条件分布下「随机寿命未超过 240 h」的概率为

\[
p_{\max}(a_j)=\frac{F_j(240)-F_j(a_j)}{1-F_j(a_j)}.
\]

  对每个世界 m，取 `v = U_L_post ∈ (0,1)`：
  - `v ≤ p_max(a_j)`：自然故障年龄 `τ^{(m)} = F_j^{-1}\!\big(F_j(a_j)+v\,(1-F_j(a_j))\big) − a_j`（分段线性 CDF 的精确反演，Fraction；与无条件采样器同一 `F_j^{-1}`，只是输入改为条件概率值）；
  - `v > p_max(a_j)`：右删失分支——随机剩余寿命超过 `240−a_j`，续演中该设备以 240 h 确定性强制更换处理（`τ` 截为 `240−a_j`）。
  禁止把 [0,240] 内 CDF 重新归一化（R39）；`a_j=0` 时 `p_max=F_j(240)`，退化为与 G3 引擎一致的无条件采样器。
- **240 h 规则在续演中不变**：`a+τ ≤ 240` 才可能自然故障；`a+d>240` 启动前强制换新（非 H2 选择）；`a+d=240` 完成优先后强制换；故障/240 同刻先结算完成（C13/C14 语义原样带入续演）。
- **生成器验证（两层，冻结；L4 第 9 条 + cross-model review 第 3 条）**：
  - **A. PRIMARY DETERMINISTIC CHECK（主门；独立 checker）**：冻结 **age 网格** `a ∈ {0,30,60,90,120,150,180,210}` × **U 网格** `u ∈ {0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, p_max−ε, p_max, p_max+ε}`（ε=1e-9，精确有理数），独立 checker **不调用/不导入** implementer 核心函数，按 `p_max(a)`、条件逆 CDF、右删失（`v>p_max` → 存活至 240）、240 h 边界（`a+d=240`、`a+d>240`）**逐点计算期望结果**（自然故障年龄 τ 或右删失标记），与 generator 输出对拍；容差冻结：**逐点 |Δ| ≤ 1e-9（小时）或右删失标记一致**（精确 Fraction 时应逐位相等）。
  - **B. SECONDARY STOCHASTIC SMOKE TEST（烟测，非硬门）**：配置 = **4 资源 × 8 年龄** `a ∈ {0,30,60,90,120,150,180,210}` = 32；每配置重采样 **N=2000**；桶定义 = 剩余寿命 `[0, 240−a)` 上每 24 h 一个左闭右开桶（`[0,24), [24,48), …`）+ **右删失桶**「存活至 240」（对应 `v > p_max`）；统计量 = 每配置 Pearson χ²（E<5 的桶按冻结规则并入下一桶）；共 32 个统计量；**接受判据（multiplicity treatment 冻结，全局判据）**：`#(p < 0.001) ≤ 1`；同时报告全部 p、桶观测/期望频率与实际样本数。

---

## 10. H2 action set（冻结）

决策点 s 上的原子动作集（按可选性取子集）：

| 动作 | 定义 | 合法条件 |
|---|---|---|
| `A0 = START_HEAD`（H1 默认，dispatch 点） | 立即启动合法 FCFS 队首 | 队首 H1-合法（本班可完整完成） |
| `A0b = H1_NOOP / ADVANCE_EVENT`（H1 默认续演，maintenance 点） | 当前无合法 `A0` 时：**不主动 PM、保持资源 idle、推进至下一已排定事件 / 下一合法 wakeup**，随后重新执行事件闭包与派工判断 | maintenance decision point 的 H1 基线（`a_H1`）；**非战略等待、非 WAIT_EVENT、不改变 FCFS** |
| `A1 = WAIT_EVENT` | 暂缓队首启动，锚定**同装置另一在途任务已排定的完成事件 e**，e 后（或失效闭包处）重判 | STRICT（`t<e<latest_start`）或 BOUNDARY（`e==latest_start`），§11；锚定事件存在且日历非空 |
| `A2a = PM_WITH_HEAD`（DISPATCH_DECISION_POINT 候选） | 存在合法 FCFS 队首时，**先预防更换（+校准）再重新判队首**；校准后于下一闭包重判 | optional-PM-eligible 且队首存在（§12）；校准须本班完整完成（B18） |
| `A2b = PM_IDLE`（MAINTENANCE_DECISION_POINT 候选） | **资源设备空闲**时对老设备主动预防更换（+校准）；校准后于下一闭包**重新判定合法队首**（含 FCFS 重判）；**不越过 FCFS**；**与 `A0b=H1_NOOP` 比较** | 同时满足（冻结；核心边界 = **equipment idle + PM physical/calendar legality**，**不以「队列是否为空」为边界**）：① 资源设备空闲（无在测任务、设备可用）；② 设备年龄 `a ≥ 120h`；③ 不是 mandatory replacement；④ 本批仍存在未来可能需要该资源的未终态装置（存在至少一台未终态装置，其尚未有效通过该资源对应工序）；⑤ 换新+校准可在本班完整结束。**B 情形含：队列中可能存在当前尚不合法/forced-wait 的任务——不得仅因「队列非空」自动禁止主动 PM**。PM_IDLE 是 H2 候选动作，**不是强制动作**（按 §4 偏离规则才执行） |

- **两类决策点（冻结，final-freeze review 第 1 条）**：
  - **DISPATCH_DECISION_POINT**（原引擎决策点语义）：该资源存在**合法 FCFS 队首**（`A0=START_HEAD` 合法）时的决策点；候选动作 ⊂ `{A0, A1(若 STRICT/BOUNDARY), A2a(若 eligible)}`；`a_H1 = A0`。
  - **MAINTENANCE_DECISION_POINT**（H2-only 新增，仅 H2 激活时存在）：该资源**当前不存在合法 START_HEAD**，但同时满足（冻结）：① 资源/设备 idle and available（无在测任务）；② `age ≥ 120h`；③ 非 mandatory replacement；④ 批中仍存在 future potential demand（存在未终态装置且尚未有效通过该资源对应工序）；⑤ 换新+校准可在当前班完整结束。此点可在 **queue empty** 或 **queue nonempty but no legal START_HEAD** 两种情形出现；候选动作 = `{A0b=H1_NOOP, A2b=PM_IDLE}`；`a_H1 = A0b`。
  - **不重复生成（冻结）**：同一资源在同一事件闭包内**至多一个决策点**——存在合法队首 → dispatch point；否则满足维护条件 → maintenance point；否则无决策点。禁止同时生成 dispatch 与 maintenance 两个重复决策点。
- **dp ordering（冻结）**：同一事件闭包内按**固定资源序 `A/B/C/E`**（沿用引擎 canonical `RESOURCES` 序）逐资源判定；每资源至多一个决策点；`dp` 索引（§6.2）= 本批内已评估 H2 决策点序号（0 基），是（世界、历史、配置、代码）的纯函数；checker 独立复算决策点类型、顺序与索引。
- **PM_IDLE 的 rollout 基线**：必须比较 `PM_IDLE vs A0b=H1_NOOP / ADVANCE_EVENT`；**不得拿 `PM_IDLE` 与不合法的 `START_HEAD` 比较**（合法队首存在时走 dispatch point / `A2a`）。
- **A0b 语义（冻结）**：当前无合法 `A0=START_HEAD` 时，H1 的默认行为 = 不主动 PM、保持资源 idle、推进至下一已排定事件/下一合法 wakeup，随后重新执行事件闭包与派工判断。**A0b 不是战略等待、不是 WAIT_EVENT、不改变 FCFS**，只是 H1 在「当前无合法服务动作」状态下的 baseline continuation。
- **WAIT 后 PM、PM 后 WAIT 等组合**由顺序重判自然表达（每次闭包重新决策），**不设第 4 个原子动作**；「both」情形（~4.5/批）按此顺序语义处理，quota 归属按 §2 B-3 规则（wait 优先）。
- **quota class ≠ 动作可用性（澄清）**：both 点归入 wait quota 只是采样分类，其合法 PM 动作仍在该点动作集中（§2 澄清）。
- **禁止**：越过队首选择另一装置（R32）、自由重排装置、改变测试内容、读隐藏真相。
- **政策执行**：真实批中在每个决策点按 §4 偏离规则选动作并推进；续演仅用于估计，不改变真实世界随机流。

---

## 11. strategic-wait 严格定义与边界（冻结；含 C23 等式裁定）

- `latest_start(head) = shift_end − duration(head)`（冻结：`now + duration ≤ shift_end` 才可启动）。
- **STRICT**：同装置存在已排定完成事件 e，满足 `t < e < latest_start(head)`，且队首当前 H1-合法（可立即启动）。→ 合法 WAIT 动作。
- **BOUNDARY（C23 等式裁定：合法）**：`e == latest_start(head)`。等待至 e 时队首恰在**最迟合法启动时刻**启动、恰班末完成——符合冻结「恰好班末结束可启动」，**是合法 WAIT 动作**；不再视为歧义（`h2_admission_opportunity_analyzer_v1.py` 第 32–33 行标注的「boundary ambiguity，NOT silently decided」由此裁定闭合）。
- **BOUNDARY_CONTRACT_CHANGE_REQUIRED（L4 第 7 条，冻结记录）**：BOUNDARY 合法化是对契约 §1.3.2/§7.5「早于最迟启动时刻」措辞的扩展（→「早于或等于」）。**本轮仅在草案中记录，不静默修改权威问题契约**；最终 freeze 获批时，必须**同步**更新：① 问题契约；② CHANGELOG；③ 对应 H2 规格；**否则不得实现该扩展**（维持 STRICT 口径）。
- **NONSTRICT**：`e ≤ latest_start`（= STRICT ∪ BOUNDARY）——**仅测量分类**，不单独构成动作。
- **forced wait**：队首当前不 H1-合法（引擎旧 `waiting_opportunity_count` 语义）——**非战略等待、非 H2 动作**，仅测量。
- 口径与 accepted 证据可比性：本定义与 `h2_admission_opportunity_analyzer_v1.py` 第 27–33 行逐条对齐（除 BOUNDARY 由草案裁定为合法外，无其他差异）；Q3 密度复核（§15）沿用同一口径。

---

## 12. optional PM / mandatory replacement 的区别（冻结）

| 类别 | 触发 | 是否为 H2 选择 |
|---|---|---|
| MANDATORY（强制） | 队首任务 `a+d>240` → 启动前强制换新+校准；`a+d==240` → 完成优先随后强制换；随机故障 → 换新+校准 | **否**（H1/H2 同规则，引擎强制） |
| OPTIONAL PM（可选）— **PM_WITH_HEAD** | 资源空闲/可用、**队首存在**、设备年龄 `a≥120`、队首 `a+d≤240`（否则已是强制）、换新+校准可在本班完整完成 | **是**（`A2a`） |
| OPTIONAL PM（可选）— **PM_IDLE** | 资源设备空闲（无在测任务）、设备年龄 `a≥120`、非 mandatory、本批仍有未来可能需要该资源的未终态装置、换新+校准可在本班完整完成；**在 MAINTENANCE_DECISION_POINT（无合法 START_HEAD，queue empty 或 queue 非空但 forced-wait）上作为候选**（PM 后重新判定合法队首，不越过 FCFS） | **是**（`A2b`，非强制动作；与 `A0b=H1_NOOP` 比较） |
| exact_240 | `a+d==240` | 否（报告单独列） |

- 计数分离（C24 修正仪表）：`optional_pm`（含 `pm_with_head` 与 `pm_idle` 两个子计数）与 `mandatory`、`exact_240` 分开记录；`raw_pm_age_eligible`（age≥120 未排除强制）仅作中间量，不得当 H2 可选密度（沿用 `H2_ADMISSION_C24_EVIDENCE_DRAFT.md` 修正结论）。
- PM_IDLE 已按 L4 第 2 条纳入（INCLUDE_PM_IDLE）：不得把已签字 H2 候选「空闲老设备主动预防更换」静默收窄为「只有队首存在时才能换」；同时 PM_IDLE 只作为 H2 候选（MAINTENANCE_DECISION_POINT，§10），**其 H1 baseline = `A0b=H1_NOOP / ADVANCE_EVENT`，不得与不合法的 START_HEAD 比较**；**不写成强制动作**。
- `tau_pm=240` 语义不成立（240 是强制节点）；`NO_PM_BEFORE_MANDATORY` = 永不主动预防，仅保留强制规则（冻结哨兵语义不变）。

---

## 13. H1 fallback 条件（冻结触发清单）

满足任一 → H2 立即删除/不保留，Q3 正式路线 = H1/R1（Q3 H1 基线证据不受影响）：

1. **C23 违例**：后验/续演读取 live hidden world、动作越队首、wait 锚无限/饥饿、相同观察史不同动作（§7）；
2. **预算不可行**：§1.2 三点均超 `w_p≤90 s`，或 hard 8 h 在 h2_holdout 完成前到达（§3）；
3. **动作不稳定 / transfer 预警**：§4 (b)/(c)/(d) 任一失败 → H2 删除；§4.1 跨 K transfer 为预注册诊断/早期预警——**明显结构不稳定**（多个 K 超带或偏离类型构成翻转）→ 回 Human Gate 裁决或按预注册路线 DELETE H2，**不因单一 `|d_K − d_{10.5}| > 0.10` 自动判失败**；正式 retain/delete 统计门 = C25；
4. **密度复核失败**：§15 下限任一不满足；
5. **C25 失败**：§16 保留规则不满足；
6. **正式运行验证失败**：H2 相关 runner/checker 在正式范围暴露无法由实现 bug 解释的语义错误（RED，0 次静默修复，回 Human Gate）。

fallback 后：H2 负结果仅在模型选择节披露（R55），**不以验证工程补位第三项创新**；Q3 论文 = H1 七 K 基线（Tier 1/2/3 视预算）。

---

## 14. Q3 七 K H1 baseline experiment design（冻结）

### 14.1 正式家族与优先级

- K 集合：`{9, 9.5, 10, 10.5, 11, 11.5, 12}`（P041；七点全枚举，C15）。
- **Tier 1（主，必做）**：`obs=single_test_unconditional_v1 × turn=1h_literal × policy=NO_PM_BEFORE_MANDATORY × 7 K × 200 批`（1400 批；每批 100 台）。**主 K 推荐证据**。
- **Tier 2（契约必做，A03 全链独立）**：`obs=standard_chain_v1 × turn=1h_literal × policy=NO_PM × 7 K × 200 批`（1400 批）。替代语义的 K 比较（独立全链；E 核用 accepted 4bb92eda standard_chain 值）。
- **Tier 3（稳健性，可选，soft 预算最先丢弃）**：(i) `obs=single_test_unconditional_v1 × turn=0.5h_overlap × policy=NO_PM_BEFORE_MANDATORY × 7 K × 100 批`；(ii) `obs=single × turn=1h_literal × policy=tau_pm_198 × 7 K × 100 批`（合计 1400 批）。只用于 K 推荐的稳健性陈述，不参与主 K 选择。tau_pm_198 为 HISTORICAL_TUNING_SELECTED_CANDIDATE / FORMALLY_NOT_SELECTED，Q3 不重调、不宣称最优。
- 完整族最坏 4200 批 ≈ 规划 1–2.5 h（非权威估计；按 §3 速率口径；含 H2 管线的全阶段最坏 ≈5–7 h 见 §3/§18 R-Q3-2）。

### 14.2 随机世界与配对

- `namespace=q3_formal`、`master_seed=5`、`replicate_ids=0..199`（恰 200，冻结，禁事后增减）；族内 7 K 全部复用同一 replicate 集（CRN 配对，C15/C16）；不同 tier 单元同一 id 语义相同。
- 初态：A09 完全重置（年龄 0、代次重置、独立新寿命、首两台在位、已校准）；时钟 0 起；Q3 永不读取 Q2 终态（C15 断言）。
- 班历：第 d 天班 1=[24d, 24d+K)、班 2=[24d+K, 24d+2K)、停工 [24d+2K, 24(d+1))；`squad_id = shift_index mod 2`（仅物理片段日志；B17 使分队不可观测差异）。
- 跨队语义（B19 显式重述）：换班只更新 `on_duty_squad`，不清空/重建全局就绪队列；已就绪未执行任务保留原 FCFS 键；待重测保留首败记录、原 `release_time`、`effective_attempt_no=2`，由下一班另一分队完整执行，不插队、持续占台；`squad_id` 不进任务身份、FCFS 键或 `U_Y`。
- 禁：用 K=12 弱支配替代七点枚举（主配置，C15/R29）；Q3 上重调 tau_pm（C26 关闭）；注入 policy/K 到物理键。

### 14.3 统计程序（冻结）

- 主估计量：每 K 的批级 `T`（日历小时→/24 天，P044）；`S/PL/PW/YXB_j`（YXB 分母 = K，B10/P048；YXB 分子为两队合并的同类组全部实际运行片段，B10）独立报告。
- 比较族：**全部 21 个两两 K 配对对比**（CRN 配对差 ΔT = T(k1) − T(k2)）；paired batch-level bootstrap，B=10000，族水平 95%，Bonferroni m=21 → `alpha_each = 0.05/21`（双侧；边缘 percentile 界 `0.05/42` 与 `1−0.05/42`）。
- 推荐规则：`k* = argmin_k mean T`（数据决定，但推断族为预注册全对族）；co-best 集 = {k : CI(k* vs k) 含 0}；推荐 = k*，并披露 co-best 集；k* 对所有 k 的 CI 全部 <0 时为强推荐。**最优声明限于七个 K 与候选策略集**（R21）；主配置不宣称 K=12 弱支配（C15/R29）。
- 质量：S/PL/PW 按 accepted 质量分离（C06 逐台 pathwise 相等 → 跨 K 应为常数，验证）；PL/PW 稀有事件池化 20000 台/单元，x=0 → 单侧精确 CP 95% 上界 `1−0.05^(1/20000)`（沿用 Q2-FORMAL-DEC-04）。
- 分析流：`namespace=q3_formal_analysis_bootstrap_v1`、seed=40003、B=10000，仅重采样 200 个完整配对批次索引。
- 解释约束：不因某 K 更优而事后扩族/换比较；C3 式「不可区分」不得翻转为优越证据。

### 14.4 检查范围

每批：C06/C13/C14/C16/C17/C18/C26（适用正式范围）+ C15（Q3 重置、七 K 配对、无 K=12 捷径）；族级：C21 不可变证据、C20 适用故障注入资格、C07 烟测诊断、C19 checker 隔离。Q3 H1 无新增调优项。

---

## 15. Q3 H2 opportunity-density recheck 设计（冻结）

- **目的**：把 accepted H2 admission 密度证据（Q2 单班 12 h 日历）复测到 Q3 双班 K 日历下，决定 H2 是否值得进入 C25。
- **数据源**：Q3 H1 Tier 1 accepted 日志（7 K）确定性重放重建（与 admission 相同的 hash 逐批校验方法；**不消耗新随机世界、不修改 accepted 证据目录**）。
- **口径**：与 §11/§12 冻结定义完全一致（STRICT/BOUNDARY/NONSTRICT、forced_wait、optional_pm（**含 pm_with_head 与 pm_idle 两个子计数，L4 第 2 条**）、mandatory/exact_240、meaningful fraction）；复用/扩展 `h2_admission_opportunity_analyzer_v1.py`（Q3 班历支持 + PM_IDLE 计数为 checker 侧扩展，需独立验收）。
- **逐 K 输出**：legal dispatch、strict/boundary/nonstrict wait、optional PM（pm_with_head / pm_idle 分列）、mandatory、exact_240、both、meaningful fraction、零机会批次比例。
- **下限（预注册）**：`meaningful_choice_fraction ≥ 0.20` 于**全部 7 K**，且 `strategic_wait_strict ≥ 2/批` 于 **≥6/7 K**；否则 → H2 删除（不执行 C25）。依据（分开陈述）：meaningful 下限 0.20 ≈ admission 值 0.429 的约半数（容忍班历差异）；strict-wait 下限 2/批 ≈ admission 值 11.4/批 的约 1/6，为独立设定的「每批至少保留 2 个 wait 侧评估点」覆盖下限，**不以「约半数」为依据**。
- 输出物：`05_结果/H2/density_recheck/` 报告 + 逐 K 表；与 admission 证据的可比性声明（同口径、同方法）。

---

## 16. C25 retain/delete H2 判定规则（冻结）

- **证据**：`h2_holdout`（§5）7 K × 20 批，H2 vs H1 批级 CRN 配对；每 K 主对比 `ΔT_K = T(H2)_K − T(H1)_K`。
- **推断**：族 = 7 个 K 对比；paired batch bootstrap B=10000；族水平 95%，Bonferroni m=7 → `alpha_each = 0.05/7`（双侧；边缘 percentile 界 `0.05/14` 与 `1−0.05/14`）；分析流 `h2_holdout_analysis_bootstrap_v1` seed=40007（符号稳定复验 seed=40008，§4(d)）。
- **保留（RETAIN）当且仅当全部满足**：
  1. **≥5/7 个 K** 的族调整 CI 完全 <0（H2 完成时间更短）；
  2. **0 个 K** 的 CI 完全 >0（无显著恶化）；
  3. 动作稳定性 §4 全通过；
  4. 实测墙钟在 hard 预算内（§3）；
  5. 无 C23 违例（§13 触发 1）。
- **否则删除（DELETE）**：Q3 正式 = H1-only；H2 表不发布；H2 负结果在模型选择节披露。
- **政策阈值声明（L4 第 6 条，冻结）**：「≥5/7 个 K」与「0 个 K 显著恶化」是 **Human Gate 预注册政策阈值（policy threshold），不是数学定理**；不赋予超出预注册的解释力（不宣称 H2「理应如此」或「一般优越」，不因「差 1 个 K」重开或降阈）。
- 次级报告（不用于判定）：跨 K 的「K 内配对 ΔT 均值之均值」+ 边际 95% bootstrap CI；逐 K 边际 CI；决策点偏离率与覆盖率审计。
- 注意（诚实性声明）：给定 Q2 正式证据（政策级配对 ΔT≈1.3 h/批、SE 亚小时量级）与每批 ≤ C_eval* 点的覆盖率，**本规则下 H2 保留的概率不高**；这是预注册结论，不是失败。

---

## 17. formal outputs / logs / provenance 要求（冻结）

### 17.1 Q3 H1 族级证据根

`05_结果/Q3/formal/run_<UTC>_<8hex>/`（每次完整正式尝试恰一个不可变根；失败尝试保留不可覆盖）：
run_manifest、commands、environment/runtime、family config snapshot、task package 快照/hash、key schema hash、code/schema/config hashes、逐单元（7 K × tier）输出、逐 replicate 原始指标、checker reports（C06/C13/C14/C16/C17/C18/C26/C15）、统计分析与 bootstrap 元数据、formal comparison table（21 对 ΔT + k* + co-best + 每 K mean/SE/P50/P90）、质量表（S/PL/PW/YXB per K + 稀有事件 CP）、failure samples、file_hashes.sha256、逐批/逐单元/族总墙钟账本。

### 17.2 H2 证据根

`05_结果/H2/`：`density_recheck/`（§15，含 pm_idle 计数）、`tuning/`（h2_tuning：M/C_eval 校准、§4 稳定性诊断、§4.1 跨 K transfer、§8/§9 生成器验证——**非论文数字**）、`holdout/run_<UTC>_<8hex>/`（h2_holdout：C25 报告 + 论文 H2 表）、`dev_budget_ledger.json`（§3 H2 开发预算账本：全部离线诊断 rollout 计数与墙钟）。H2 额外日志：逐批决策日志（decision_point_index、**decision point type（dispatch/maintenance）**、quota class、state_hash、候选动作（含 `a_H1`）、各 Q̂ 与 SE、所选动作、rollout 计数）、续演子流 manifest（rollout_seed 派生公式与盐）、后验/条件寿命验证报告、动作稳定性报告（含 deviation rate / agreement rate / 二项区间）、跨 K transfer 报告、墙钟账本。

### 17.3 可追溯性与权威规则

- 一切数字绑定 `run_id + task_package_ref + config/code/schema/key-schema/log hash + checker report + commands + env + file_hashes.sha256`；聚合前不四舍五入（沿用 Q2 契约）。
- **论文数字权威**：Q3 数字只来自 accepted `q3_formal` 运行；H2 数字（若保留）只来自 accepted `h2_holdout` 运行；**h2_tuning 与任何重放/诊断值禁入论文**；禁手录、禁失败 run、禁调优值替代。
- 失败/被替代 run 保留不可变并标注；H2 删除路径的负结果记录同样不可变。

---

## 18. 风险点（明示）

1. **R-Q3-1（日历结构主导）**：Q3 的 E[T] 受「每日工作小时 = 2K」支配，K=12 大概率在 E[T] 上胜出（更多工作小时/天）；主配置不得据此宣称弱支配（C15/R29），论文须在七 K 与候选集内如实报告，并独立呈现 YXB（分母 K）与停工 24−2K 上下文；禁止加权目标（R10）。
2. **R-Q3-2（预算-样本张力）**：Tier 1+2 必做 2800 批（规划 ≈0.5–1.5 h）+ H2 管线（tuning ≤0.5–1 h + holdout ≤3.5 h）+ 可选 Tier 3（≈0.5–1 h）的最坏路径 ≈ 5–7 h，逼近 hard 8 h；优先级与「hard 停 → H2 不保留」是预注册防线；Tier 3 可能被 soft 预算丢弃（可接受，预注册）。
3. **R-H2-1（成本模型不确定）**：单次续演墙钟未知，直接决定 (M*, C_eval*) 与可行性；已用成本导向选择规则 + 预算不可行删除触发兜底，禁止按结果重选。
4. **R-H2-2（C25 功效现实）**：Q2 正式证据表明政策级 ΔT 极小（~1.3 h/批、SE 亚小时级），20 批/K × 7 K 的族调整检验大概率含 0 → H2 删除为最可能预注册结局；诚实披露，不以「差一点」重开或降阈。
5. **R-H2-3（泄漏/后验正确性）**：后验贝叶斯与条件 CDF 反演必须精确（Fraction）；C23 硬门（同史同动作、禁读隐藏字段）+ 独立生成器验证（§8/§9）；泄漏一旦发现 = RED，0 次静默修复。
6. **R-H2-4（决策点选择覆盖偏差）**：每批仅评估 ≤C_eval* 个点（wait 按时间序、PM 按年龄分层）——结果无关但覆盖受限；政策级效应受覆盖率限制，C25 在此覆盖率下判定；论文不得声称全决策点 H2。
7. **R-KEY-1（key_schema 扩展）**：新增命名空间不得改变既有键字节（回归必须逐字节一致）；`h2_rollout` 种子派生公式冻结，防止同键碰撞或动作注入。
8. **R-CAL-1（跨 K/跨班边界）**：不同 K 班界不嵌套（C15）；wait 锚不得跨班（e < latest_start ≤ shift_end 自动保证）；校准/周转不可跨班（B18）。
9. **R-GOV-1（自我批准禁令）**：本草案为 D 层草案，须经 Human Gate + 独立审阅（§21）后才可冻结；实现者不得补默认值（AGENTS.md §3）。
10. **R-DOC-1（旧仪表误用）**：引擎旧 `waiting_opportunity_count`（forced-wait）不得当 H2 密度；`raw_pm_age_eligible` 不得当可选 PM 密度（C24 修正口径）。

---

## 19. Human Gate 决策清单（本草案待裁决项）

- **D-01**：Q3 H1 主政策 = `NO_PM_BEFORE_MANDATORY`（冻结 Q2-accepted 主政策；Q3 不重开 C26 调优）。
- **D-02**：Q3 正式家族 = Tier 1（7K×200，single×1h×NO_PM，主）+ Tier 2（7K×200，chain×1h×NO_PM，契约必做）+ Tier 3（7K×100×2 组，可选）；优先级 T1>T2>T3。
- **D-03**：`q3_formal` 随机世界 = master_seed 5、replicate_ids 0..199、跨 K CRN。
- **D-04**：Q3 H1 统计 = 21 两两配对对比 + Bonferroni m=21 + bootstrap B=10000 + k*/co-best 规则；分析流 `q3_formal_analysis_bootstrap_v1` seed=40003。（备注：21 对为**预注册全对族**——读取数据前声明，非机会主义（G3-SPEC §16）；Bonferroni m=21 保守于冻结参考族 m=6；若 Human Gate 偏好参考族，须另冻结 k* 参考选择规则。）
- **D-05**：key_schema 扩展：新增 `h2_tuning` / `h2_holdout` / `h2_rollout` 命名空间与 `U_*_post` 流（既有键字节不变）。
- **D-06**：H2 样本划分 = h2_tuning（K=10.5，15 批）/ h2_holdout（7K×20 批，CRN）/ 论文 H2 表 = h2_holdout（预注册双职）。
- **D-07**：M 网格 `{(4,8),(8,6),(8,8)}` + 成本导向选择规则（`w_p≤90 s`，非结果导向）；`C_rollout=200` 硬上限。
- **D-08**：决策点选择规则（**一般形式，不写死 4+4**）：`wait cap = ⌈C_eval*/2⌉`、`PM cap = ⌊C_eval*/2⌋`（**C_eval*=6 → 3+3；C_eval*=8 → 4+4**）；**independent online caps、no cross-side borrowing、unused capacity expires**；wait 侧在线取前 W_cap 个 wait-class 点（含 both 点）；PM 侧按年龄桶 B1/B2/B3 的 **bucket-first +（P_cap=4 时恰 1 个 extra slot）在线算法**（无事后 backfill）；dispatch 与 maintenance 决策点统一进入 quota classification；每资源每闭包至多一个决策点；`selected_for_rollout(t)` 只依赖 history ≤ t（在线因果闭合）。
- **D-09**：阶段墙钟 soft 4 h / hard 8 h + 优先级 + hard 停 → H2 不保留。
- **D-10**：动作稳定性准则（§4 (a)–(d)，稳定性 = 离线诊断样本：来源仅 h2_tuning、不驱动 holdout/formal、不受在线 C_eval* 约束、墙钟入开发预算账本、确定性采样、报告实际 n；**agreement 点估计 ≥95% = 唯一稳定性硬门；CP 区间 = uncertainty disclosure，非独立 pass/fail 门，本轮不设 CI 下界第二硬门**）+ 2·SE_M 自信偏离阈值。
- **D-11**：C23 等式裁定：BOUNDARY（`e==latest_start`）为合法 WAIT；NONSTRICT 仅测量。**BOUNDARY_CONTRACT_CHANGE_REQUIRED**：最终 freeze 获批时必须同步更新问题契约、CHANGELOG、H2 规格；否则不实现该扩展（维持 STRICT 口径）。
- **D-12**：后验缺陷重采样（§8 联合后验公式）与条件剩余寿命重采样（§9 条件分位公式）规则冻结。
- **D-13**：H1 fallback 触发清单（§13）。
- **D-14**：Q3 H2 密度复核口径与下限（meaningful ≥0.20 全 K；strict wait ≥2/批 于 ≥6/7 K）。
- **D-15**：C25 保留/删除规则（≥5/7 K CI<0、0 显著恶化、稳定、预算、无 C23 违例）。
- **D-16**：证据/日志/provenance 契约（§17）。
- **D-17**：论文数字权威规则（仅 accepted q3_formal + h2_holdout；调优值禁入）。
- **D-18**：H2 动作集冻结（§10）：A0=START_HEAD / **A0b=H1_NOOP / ADVANCE_EVENT（无合法队首时的 H1 默认续演，maintenance 点 `a_H1`）** / A1=WAIT_EVENT（STRICT/BOUNDARY）/ A2a=PM_WITH_HEAD（dispatch 点）/ A2b=PM_IDLE（maintenance 点，与 A0b 比较，不与非合法 START_HEAD 比较）；两类决策点（dispatch / maintenance）每资源每闭包至多一个；dp ordering = 固定资源序 A/B/C/E 的纯函数；组合由顺序重判表达；禁止越队/重排装置/改测试内容/读隐藏真相。
- **D-19**：optional PM / mandatory 区别冻结（§12）：触发条件与计数分离；`a+d>240`、`a+d==240`、随机故障均为强制（非选择）；`raw_pm_age_eligible` 仅中间量，不得当可选密度。
- **D-20**：**INCLUDE_PM_IDLE（L4 第 2 条 + cross-model review 第 1 条 + final-freeze review 第 1 条）**：PM_IDLE 在 **MAINTENANCE_DECISION_POINT** 上作为候选（§10 A2b / §12），核心边界 = **equipment idle + PM physical/calendar legality**（age≥120、无在测、非 mandatory、本批仍可能需要该资源、校准本班可完成）；**不以「队列是否为空」为边界**——queue empty 与 queue 非空但无合法 START_HEAD（forced-wait）均可出现 maintenance point；候选 = `{A0b=H1_NOOP, PM_IDLE}`，**PM_IDLE 必须与 H1_NOOP 比较**；PM 后重新判定合法队首、不越过 FCFS；**非强制动作**。
- **D-21**：**both 点归属规则（L4 第 3 条 + final-freeze VERIFIED review）**：wait classification 优先；一个决策点只有一个 quota class；**maintenance 点天然 PM-only（无 wait 动作）**；**quota 为独立在线硬上限：no cross-side borrowing、unused expires、无事后回溯补选（在线因果闭合，§2）**；禁止重复计数；checker 独立复算 quota class、dp 索引与 selected set（§2）。
- **D-22**：**生成器验证校准冻结（L4 第 9 条 + cross-model review 第 3 条）**：两层验证——**A. PRIMARY DETERMINISTIC CHECK**：后验 = 冻结可达模式（≤625）× 独立 checker 计算完整 16/8 状态后验向量逐状态对拍（|Δ|≤1e-12，不调用 implementer 核心）；寿命 = 冻结 age/U 网格 × 独立 checker 逐点计算 p_max / 条件逆 CDF / 右删失 / 240 边界期望（|Δ|≤1e-9）；**B. SECONDARY STOCHASTIC SMOKE TEST**：后验 = 8 核心模式 × N=5000 × 32 个边际 z 检验 × 全局判据 `#(|z|>3.5)≤1`；寿命 = 32 配置 × N=2000 × Pearson χ² × 全局判据 `#(p<0.001)≤1`；multiplicity 与统计协议全部冻结，不留实现者默认。
- **D-23**：**跨 K action-transfer diagnostic（L4 第 5 条 + cross-model review 第 2 条）**：h2_tuning 同 replicate 世界 × 7 K 班历的只读/离线诊断；**d_K = 统一 H2 政策偏离 H1 的评估决策点占比**（须结合偏离类型构成解读）；带宽 `|d_K − d_{10.5}| ≤ 0.10` = **Human Gate / DESIGN CHOICE（早期预警带，非数学必然）**；定位 = **PRE-REGISTERED DIAGNOSTIC / EARLY WARNING，不替代 C25 最终收益硬门**；明显结构不稳定（多 K 超带或偏离类型翻转）→ 回 Human Gate 或预注册 DELETE；不因单值自动判失败；**不采用 seven separate per-K H2 tuning**；禁止按 K 临时改规则（§4.1）。
- **D-24**：**C25 政策阈值声明（L4 第 6 条）**：「≥5/7 K」与「0 显著恶化」为 Human Gate 预注册政策阈值，非数学定理（§16）。
- **D-25**：**BOUNDARY_CONTRACT_CHANGE_REQUIRED（L4 第 7 条）**：BOUNDARY 合法化须在最终 freeze 时同步 问题契约/CHANGELOG/H2 规格，否则不实现该扩展（§11/D-11）。

---

## 20. 停止边界与后续授权条件

- 本规格已于 2026-08-15 经 Human Gate **VERIFIED FINAL PASS / DESIGN FREEZE APPROVED** 冻结（landing 标记 `Q3_H2_BOOTSTRAP_FINAL_FREEZE_LANDED_READY_FOR_HUMAN_GATE_VERIFY`）。**FINAL FREEZE 不授权实现**：后续 H2 模块实现、C23 实现与检查、Q3 七 K 运行、H2 管线运行均需**另发执行授权**。
- Human Gate 最终裁决本草案（含 §19 决策清单 D-01..D-25）后，需**另发授权**方可：① key_schema 扩展与回归（L2）；② H2 后验/续演/政策模块实现 + 独立 C23 checker（L2，先小例对拍 + 生成器验证）；③ Q3 H1 正式 runner 与运行（Pilot）；④ H2 管线运行（tuning→holdout→C25）。每一步仍按 CR-V3.1 / AUTOPILOT 治理执行，Macro 停点回 Human Gate。
- 本草案不改变任何 accepted 证据；不冻结任何 Q3/H2 数字。

---

## 21. 独立审阅追加区（草稿审计已回填）

> 审计方式：workflow `q3h2-bootstrap-audit`，两个并行 fresh 只读审计者，`may_spawn_children=false`，写路径 NONE。（模型请求见文档头：`deepseek-v4-pro` / `deepseek-v4-flash`；**reasoningEffort 未取得机械证据 = UNVERIFIED**。）

### 21.1 Q3H2_SEMANTIC_REVIEWER（D / L3–L4 / fresh semantic reviewer；requested model = `deepseek-v4-pro`；reasoningEffort = **UNVERIFIED**（adapter default，未机械证明）；只读）

- **overall = PARTIAL / confidence = HIGH**（方向正确、覆盖完整、无 frozen 事实违反；两处核心公式未达可冻结精度）。
- **BLOCKING-1（已修复 → §8）**：D 后验原表述会把 E 当作「x_D 的直接检测」；E 是整机二元检测、似然依赖 `H={A,B,C,D} 非空`。已冻结联合后验公式与分层采样（先积分掉 x_D 采 A/B/C，再条件采 x_D；`H_ABC` 非空时 E 对 x_D 无信息）。
- **BLOCKING-2（已修复 → §9）**：条件寿命重采样右删失阈值原写作 `F_j(240)`；正确为 `p_max=(F(240)−F(a))/(1−F(a))`。已冻结条件分位公式（`v≤p_max` 自然故障；`v>p_max` 存活至 240 右删失），保留 R39 禁重归一化；`a=0` 退化为无条件采样器。
- **NONBLOCKING（已处置）**：① §4(d) 与「稳定性只用 h2_tuning」的措辞矛盾 → 已改为数据域边界分句（M/阈值与 (b)(c) 用 h2_tuning；(d) 为预注册 holdout 稳健性）；② D-11 BOUNDARY 属契约术语扩展 → 已在 D-11 备注「批准后同步更新问题契约+CHANGELOG，否则维持 STRICT」；③ §5「15+5」歧义 → 改为「15（其中 0..4 兼作成本测量）」；④ h2_holdout 批数歧义 → 表内明确「每 K 20 H2+20 H1，共 280；§3 预算按 140 个 H2 批计」；⑤ §14.2/§14.3 B19 与 YXB 合并两队 → 已显式重述；⑥ Tier 3(i) 政策缺省 → 已显式 policy=NO_PM；⑦ 2M* 与 C_rollout 冲突 → §4(c)/§2 已豁免为离线点级诊断；⑧ m=21 全对族与 G3 §16「不用机会主义全对族」的张力 → D-04 已注明预注册全对族、m=21 保守于 m=6，Human Gate 可选参考族（需另冻结 k* 参考规则）。

### 21.2 Q3H2_MECHANICAL_CHECKER（E2 / L2 / requested model = `deepseek-v4-flash`；reasoningEffort = **UNVERIFIED**（adapter default，未机械证明）；只读）

- **overall = PASS / confidence = HIGH**。核心数字全部独立重算并与 accepted 证据一致：新种子 5/6/7 与分析种子 40003/40007/40008 与已用池（1/2/3、30003）零碰撞；replicate 范围与批数（200/15/20+20；1400/2800/1400/4200/140）逐项吻合；rollout 96/144/192 ≤ C_rollout=200；Bonferroni 0.002381/0.0011905 与 0.007143/0.003571 准确；soft 4h/hard 8h 与 140×90s≈3.5h 成立；机会密度引用（413.1/11.4/168.8/4.5/0.429）与 Q2 基线（run 2d1466ba、NO_PM、ΔT=+1.2892h、CI[0.4625,2.1942]）与磁盘证据一致；草案无禁止行为。
- **六处 NONBLOCKING（已处置）**：① §4(d) 交叉引用 §6 → 改为 §5 表与 §16；② §3「实测 1–2 h」与 manifest（族级墙钟 ≈0.34 h）不符 → 改为 manifest 口径 + 非权威规划估计；③ 2M* 与 C_rollout → 同 21.1⑦；④ §19 缺 H2 动作集/PM 区别专属裁决 → 新增 D-18/D-19；⑤ §15 strict-wait 下限「约半数」不成立 → 分开陈述独立依据（2/批 ≈ 11.4/6 覆盖下限）；⑥ R-Q3-2「7–8 h」口径 → 改为分量和 5–7 h 最坏（含 Tier 3）。

### 21.3 处置结论（首轮）

两项 BLOCKING 已通过公式级改写闭合；其余全部 NONBLOCKING 已按上述回填到正文。**本草案在首轮审阅后的状态 = READY_FOR_HUMAN_GATE（待 Human Gate 裁决 §19 D-01..D-19）；审阅本身不构成批准，不授权实现。**

### 21.4 L4 独立设计裁决处置记录（Human Gate 转交，2026-08-15）

**L4 身份证据（第 10 条，如实记录）**：
> L4 adjudication supplied to coordinator; claimed/requested `deepseek-v4-pro/max`; actual request-header verification not available here.
（当前仓库/会话无该外部裁决的 session/request header 证据可机械核验；**不伪写 mechanically verified**。若后续取得可访问的 request header 证据，只按真实字段记录 model 与 reasoningEffort。）

**逐条处置（1–11）**：
1. **B-1（闭合 → §1.3/§4/§5 表/§3 账本）**：稳定性验证改为**离线诊断样本**——来源仅 h2_tuning（replicate 0..9）；不驱动 holdout/formal 选择；不受在线 `C_eval*` 约束；rollout 计算量与墙钟入 §3「H2 开发预算账本」；确定性采样（wait 50 + PM 50 按批序/时间序，上限 120，n<50 删除）；报告实际 n；95% 为预注册工程阈值；新增必须报告 deviation rate（H2 对 H1）、agreement rate 及 95% Clopper–Pearson 二项区间，防空洞稳定。
2. **B-2（采用，INCLUDE_PM_IDLE → §10/§12/§15/§19 D-20）**：PM_REPLACE 拆为 `A2a=PM_WITH_HEAD`（队首存在，先 PM 再重判）与 `A2b=PM_IDLE`（队列为空 + age≥120 + 无在测 + 非 mandatory + 本批仍有未来需要该资源的未终态装置 + 校准本班可完成）；PM_IDLE 为 H2 候选**非强制**；§15 复核增加 pm_idle 计数；「forced wait + 队首存在」的 PM 上下文本轮不在范围内。
3. **B-3（闭合 → §2）**：both 点唯一确定性归属——wait classification 优先；一点一 quota class；PM 配额从 PM-only 候选按冻结序补足；禁重复计数；checker 独立复算 quota class / dp 索引 / selected set。
4. **C23 加强（→ §7）**：冻结可观察字段白名单 + 禁读清单（true_state、x_A/B/C/D、live U_L、live lifetime、future observation U、可恢复未来信息的 u_key 字段、is_right_censored 未来实现信息、未物化 D 真值）；仅经 `PosteriorState`/`ObservableState` 接口读状态；独立 checker = 字段白名单检查 + import/AST 隔离 + same-observed-history / different-hidden-world 动作逐位一致测试。
5. **跨 K transfer diagnostic（→ §4.1/§19 D-23）**：h2_tuning 同 replicate 世界 × 7 K 班历的只读/离线 action-transfer 诊断；判据 `|d_K − d_{10.5}| ≤ 0.10`；不稳定 → DELETE H2 / RETURN TO H1；不采用 per-K 独立 tuning；禁止按 K 临时改规则。
6. **C25 政策阈值声明（→ §16/§19 D-24）**：「≥5/7」与「0 显著恶化」= Human Gate 预注册政策阈值，非数学定理。
7. **BOUNDARY_CONTRACT_CHANGE_REQUIRED（→ §11/D-11/§19 D-25）**：本轮仅在草案记录，不静默修改权威问题契约；最终 freeze 获批时须同步 问题契约/CHANGELOG/H2 规格，否则不实现该扩展。
8. **公式保持（无重写）**：joint 16-state 后验、whole-device E 似然、条件剩余寿命、`p_max(a)=(F(240)−F(a))/(1−F(a))` 均保持 Pro/high + Pro/max 独立复核后的当前公式（§8/§9），不做无理由重写。
9. **验证口径补齐（→ §8/§9/§19 D-22）**：后验经验频差冻结为「冻结可达历史模式清单 × N=2000/模式 × 边际频差 ≤2pp」；寿命条件分布桶检验冻结为「4 资源 × 8 年龄 × N=5000 × 24 h 桶 + 右删失桶 × 桶偏差 ≤2pp」；不再留「3pp」类阈值给实现者解释。（**注：该 2pp/N 单格协议已被 cross-model review 两层验证取代，见 §21.5 第 4 条 / §22.1；本条仅历史追溯，无当前 normative effect。**）
10. **L4 身份证据**：见本节首行记录。
11. **本轮边界**：仅文档/引用/数字/内部一致性机械复核（§22）；无新模型设计、无代码实现、无实验运行。

**新增 Human Gate choice（并入 §19）**：D-20（PM_IDLE）、D-21（both 归属）、D-22（验证校准冻结）、D-23（跨 K transfer）、D-24（C25 政策阈值声明）、D-25（BOUNDARY_CONTRACT_CHANGE_REQUIRED）。

**修订后状态**：**DRAFT_WAITING_FOR_FINAL_HUMAN_GATE**（待 Human Gate 最终裁决 §19 D-01..D-25；L4 裁决不构成批准，不授权实现）。

### 21.5 cross-model review 处置记录（Human Gate，2026-08-15：CONDITIONAL PASS，NOT FINAL FREEZE）

> Human Gate 裁决：Q3/H2 BOOTSTRAP = **CONDITIONAL PASS**；**NOT FINAL FREEZE**；**H2 实现仍 NOT AUTHORIZED**。本轮仅修订本草案 5 类问题；不重新设计整套 H2、不实现代码、不运行 Q3 七 K / 随机实验、不改 CURRENT_STATE / CHANGELOG / accepted evidence、不 commit / push。

1. **PM action space 完整闭合（→ §10 A2b / §12 / D-20）**：PM_IDLE 核心边界改为 **equipment idle + PM physical/calendar legality**，**不以「队列是否为空」为边界**——A 情形（存在合法 FCFS 服务动作 → 先 PM 再重判队首）走 `A2a`；B 情形（当前不存在合法可启动服务动作，含队列存在 forced-wait/暂不合法任务）走 `A2b`；PM 后必须重新判定合法队首、不越过 FCFS；§21.4 第 2 条「队列为空」「forced-wait 不在范围」表述被本条取代（历史记录保留，以本条为准）。
2. **both 点 quota class 澄清（→ §2/§10）**：quota class 只是**决策点采样分类**，不得因归入 wait quota 删除该点本合法的 PM 动作。
3. **跨 K transfer 修订（→ §4.1 / §13 / D-23）**：`d_K` 定义冻结；0.10 带宽标记为 **Human Gate / DESIGN CHOICE（非数学必然）**；定位 = **PRE-REGISTERED DIAGNOSTIC / EARLY WARNING，不替代 C25 最终收益硬门**；明显结构不稳定 → 回 Human Gate 或预注册 DELETE，不因单值自动判失败；正式 retain/delete 统计门仍为 C25（paired holdout 改进、simultaneous CI、action stability、budget、C23）；不采用 per-K 独立 tuning。
4. **生成器验证两层化（→ §8 / §9 / D-22）**：A. PRIMARY DETERMINISTIC CHECK（独立 checker 逐状态后验向量对拍 |Δ|≤1e-12、逐点 p_max/条件逆 CDF/右删失/240 边界期望对拍 |Δ|≤1e-9，不调用 implementer 核心）；B. SECONDARY STOCHASTIC SMOKE TEST（后验 8 核心模式 × N=5000 × 32 边际 z × 全局判据 `#(|z|>3.5)≤1`；寿命 32 配置 × N=2000 × Pearson χ² × 全局判据 `#(p<0.001)≤1`）；**废除「数千格各自 ≤2pp」未校正大规模硬门**；multiplicity/统计协议全部冻结。
5. **stability CI 语义闭合（→ §4(b) / D-10）**：agreement 点估计 ≥95% = 唯一稳定性硬门（Human Gate 预注册工程阈值）；CP 区间必须报告但 = **uncertainty disclosure，非独立 pass/fail 门**；不新增「CI 下界 ≥95%」第二硬门（除非 Human Gate 另行批准）；保留 deviation rate / agreement rate / CP interval / actual n；deviation rate=0 → 按冻结 admission/fallback 规则处理。

**本轮新增/修订 Human Gate choice（并入 §19）**：D-10 / D-20 / D-22 / D-23 更新；无新增编号（D-01..D-25 不变）。

**修订后状态**：**DRAFT_WAITING_FOR_FINAL_HUMAN_GATE**（待 Human Gate 最终裁决；cross-model review = CONDITIONAL PASS 不构成 FINAL FREEZE，不授权实现）。

### 21.6 final-freeze review 处置记录（Human Gate，2026-08-15）

> Human Gate：Q3/H2 BOOTSTRAP = CONDITIONAL PASS；距 FINAL FREEZE 仅剩 3 项。本轮只做最小文档修订 + 机械一致性复核；不重新设计 H2、不实现代码、不运行 Q3/H2 实验、不改 CURRENT_STATE / accepted evidence、不 commit / push。

1. **BLOCKING：PM_IDLE 决策点语义与 H1 baseline action（→ §1.1/§2/§4/§10/§12/D-08/D-18/D-20/D-21/§17.2/§22.1）**：
   - A. 新增 **`A0b = H1_NOOP / ADVANCE_EVENT`**（无合法 START_HEAD 时 H1 的默认续演：不主动 PM、保持 idle、推进至下一已排定事件/下一合法 wakeup、重跑闭包与派工判断；非战略等待、非 WAIT_EVENT、不改 FCFS）；**PM_IDLE 必须与 A0b 比较，不得与非合法 START_HEAD 比较**；`a_H1` 对两类决策点均有定义（dispatch=A0；maintenance=A0b）。
   - B. 冻结 **MAINTENANCE_DECISION_POINT**（H2-only，仅 H2 激活时存在）：资源/设备 idle and available + age≥120 + 非 mandatory + 批中仍存在 future potential demand + 校准本班可完整结束 + 无在测任务；可出现在 **queue empty** 或 **queue nonempty but no legal START_HEAD**；候选 = `{A0b, PM_IDLE}`；dispatch point（存在合法队首）候选 = `{A0, A1?, A2a?}`。
   - C. 冻结 **dp ordering**：同闭包内按固定资源序 A/B/C/E 逐资源判定；每资源至多一个决策点（dispatch 或 maintenance，**禁止重复生成**）；`dp` 索引 = （世界、历史、配置、代码）的纯函数；checker 独立复算类型/顺序/索引。
   - D. 动作数上界：dispatch ≤3 / maintenance =2 → `C_eval*×3×M*` = 96/144/192 ≤ C_rollout=200 保持（以正式动作定义说明，不再使用未定义 no-op）。
2. **Pro/high 身份证据去过度声明（→ 文档头 / §21 引言 / §21.1 / §21.2）**：无 child session request/header 机械证据 → 统一改为「requested model = `deepseek-v4-pro`（/`deepseek-v4-flash`）；reasoningEffort = **UNVERIFIED / adapter default not mechanically proven**」；禁止根据提示词/报告自称/平台默认推定 high；不写「fresh verified Pro/high」。
3. **§22 标记 superseded（→ §22 标题横幅 / §21.4 第 9 条注）**：§22 标记 **HISTORICAL / SUPERSEDED BY §22.1**；旧 2pp/N 数字仅历史追溯、无当前 normative effect；当前唯一有效验证规格 = §8 + §9 + D-22 + §22.1。

**本轮无新增 D 编号**（D-01..D-25 不变；D-08/D-18/D-20/D-21 按上述更新）。

**修订后状态**：**DRAFT_WAITING_FOR_FINAL_HUMAN_GATE**（待 Human Gate FINAL FREEZE 裁决）。

### 21.7 final-freeze VERIFIED review 处置记录（Human Gate，2026-08-15）

> Human Gate：已直接审阅 587 行原文件；**FINAL FREEZE 仅剩 1 个 blocker**（§2 evaluation quota selection 未严格 online/causal 闭合；D-08 写死 wait 4 + PM 4 与 C_eval*=6 冲突）。本轮只做最小规格修订 + 机械复核；不实现代码、不运行仿真、不改 CURRENT_STATE / accepted evidence、不 commit / push、不重新设计 H2、**不改 M/C_eval 候选网格、不改 C25 / stability / posterior / lifetime 等已冻结设计**。

1. **BLOCKING 闭合（→ §2 / D-08 / D-21）**：删除跨侧事后 borrowing（「某侧不足则从另一侧补足」「不足 C_eval* 则全取」及同义表述）；冻结 **W_cap=⌈C_eval*/2⌉、P_cap=⌊C_eval*/2⌋**（C_eval*=6 → 3+3；C_eval*=8 → 4+4）为**独立在线硬上限**（wait/PM 互不借用、未用额度批末失效、C_eval* 为最大数不要求凑满、每点选择仅依 history ≤ t + 当前 quota state、禁读未来 candidate count、禁事后回溯补选）；**PM 年龄桶在线算法**（B1/B2/B3 各至多 1 个 bucket-first slot，首次出现即占用；P_cap=4 时恰 1 个 extra slot 由「bucket-first 已用且 PM cap 未耗尽」的首个后续 PM-only 点即时占用；P_cap=3 无 extra；未出现桶额度失效；不跨桶回补、不回溯、不读未来桶）；**wait 在线规则**（按发生时间取前 W_cap 个 wait-class 点，达 cap 后不再 rollout，不得因未来 PM 不足回溯加 wait）。
2. **checker causality 断言（→ §2 checker 行 / §22.3）**：`selected_for_rollout(t)` 只依赖 history ≤ t；构造「截至 t 相同、t 后 candidate 序列不同」双历史断言 t 处选择相同；禁 future candidate count / future bucket presence；禁 retroactive selection；配置断言 C_eval*=6 → 3+3、C_eval*=8 → 4+4；`wait_selected ≤ W_cap`、`PM_selected ≤ P_cap`、`selected_total ≤ C_eval*`。
3. **D-08 一般化**：不再写死 4+4，改一般形式（ceil/floor caps + 在线算法要点）；**D-21 同步 no-borrowing / online-causal 说明**；**不新增 D 编号**（D-01..D-25 不变）。
4. **保持已 VERIFIED 项不变**：A0b=H1_NOOP、DISPATCH/MAINTENANCE 决策点、PM_IDLE vs A0b、dp ordering A/B/C/E、Pro/high reasoningEffort=UNVERIFIED、§22 HISTORICAL 横幅、§8/§9 两层验证、cross-K diagnostic、C25、M/C_eval 网格与 C_rollout=200——**均未改写**。

**修订后状态**：**DRAFT_WAITING_FOR_FINAL_HUMAN_GATE**（待 Human Gate VERIFIED FINAL GATE）。

### 21.8 FINAL FREEZE LANDING 记录（Human Gate FINAL DECISION，2026-08-15）

> Human Gate FINAL DECISION：**Q3/H2 BOOTSTRAP = VERIFIED FINAL PASS；DESIGN FREEZE APPROVED**（已直接审阅本文件最终 623 行版本）。本轮仅执行 FREEZE LANDING；不实现 H2、不运行 Q3/H2 仿真/tuning/holdout/formal、不改变已通过审核的设计选择、不重开 D-01..D-25。

- **本文件状态**：`DRAFT_WAITING_FOR_FINAL_HUMAN_GATE` → **`FINAL_FREEZE_ACCEPTED / HUMAN_GATE_PASS`**（文档头）；作为 Q3/H2 Bootstrap 的**冻结权威规格**落库（路径保持 Human Gate 指定 authority candidate 路径；文件名为历史延续，未自行改名）。
- **冻结范围**：§19 D-01..D-25 全部冻结；§1–§18 全部规范条款冻结；**C24 = PASS**（opportunity-density PASS + budget/spec freeze PASS）；**H2 = NOT IMPLEMENTED**；**C23 = PENDING（实现/检查未执行）**；**C25 = PENDING**；**Q3 formal = NOT STARTED**；**无任何 Q3 K 推荐**。
- **BOUNDARY 契约同步（D-11/D-25 批准项）**：`e == latest_start` 为合法 WAIT——`01_审计/问题契约.md`（§1.3.2、§7.5）与 `03_模型/高级模型技术补充_V3.1.md`（§5.3）中 H2 strategic-wait 语义「早于最迟启动时刻」精确同步为「**早于或等于最迟启动时刻**」；`now + duration ≤ shift_end`（恰班末完成合法）保持；未扩大到其他班界/启动规则。
- **H2 权威规格同步**：`03_模型/03_H2后验Rollout候选.md` 同步冻结设计（A0/A0b/A1/A2a/A2b、DISPATCH/MAINTENANCE_DECISION_POINT、PM_IDLE vs A0b、queue empty / queue-nonempty-but-no-legal-head maintenance 机会、每资源每闭包至多一个决策点、canonical 资源序 A/B/C/E、quota class ≠ action availability、ONLINE quota W_cap=⌈C_eval*/2⌉/P_cap=⌊C_eval*/2⌋、6→3+3、8→4+4、no cross-side borrowing、unused expires、no future candidate count、no retroactive selection、wait 前 W_cap、PM B1/B2/B3 bucket-first、P_cap=4 恰 1 extra slot、P_cap=3 无 extra）。
- **CURRENT_STATE / CHANGELOG**：同步落库（见仓库根文件）。
- **Provenance**：本规格审计链中凡无 session request/header 机械证据处，reasoningEffort 一律记为 **UNVERIFIED**（文档头/§21.1/§21.2/§21.4 已如实记录）。
- **不升级**：任何 tuning/诊断值（含机会密度、M 校准、稳定性样本）均**不是论文正式数字**。
- **下一阶段（未授权）**：Q3/H2 implementation bootstrap + C23 实现与检查；需 Human Gate **另发执行授权**。

**Landing 标记**：`Q3_H2_BOOTSTRAP_FINAL_FREEZE_LANDED_READY_FOR_HUMAN_GATE_VERIFY`

---

## 22. 修订后机械一致性复核记录（L4 第 11 条；仅文档/引用/数字/内部一致性，无新模型设计）

> **⚠️ HISTORICAL / SUPERSEDED BY §22.1**：本节为 L4 修订轮的**历史复核记录**。其中第 5/8 条所载旧验证数字（`N=2000 / 2pp`、`N=5000 / 2pp`）**仅作历史追溯，不具当前 normative effect**；该单格协议已被 cross-model review 的两层验证取代。**当前唯一有效验证规格 = §8 + §9 + D-22 + §22.1**（PRIMARY deterministic checker + SECONDARY stochastic smoke）。

> 复核方式：确定性工具（grep/read/pwsh）逐项核对，不启动新模型设计、不实现代码、不运行实验。复核时间：2026-08-15（L4 修订后）。

**复核项与结果（全部 PASS，除 1 项已当场修复）**：

1. 命名空间/种子无碰撞：`q3_formal=5 / h2_tuning=6 / h2_holdout=7`；分析流 `40003 / 40007 / 40008`；与已用池 `1 / 2 / 3 / 30003` 全不相交（grep 核对）。
2. 批数算术不变：7K×200=1400×2=2800（Tier1+2）；Tier3 两组各 700、合计 1400；最坏 4200；h2_holdout 7×20=140 H2 批（+140 H1 配对）；h2_tuning 15（0..4 兼成本测量）。§5 表与 §3/§14 一致。
3. rollout 计数：`(4,8)=96 / (8,6)=144 / (8,8)=192 ≤ C_rollout=200`；动作数上界仍为 3（有队首：{A0,A1,A2a}；无队首：{A2b,no-op}——A2a/A2b 互斥，最坏 3 动作不变）。
4. Bonferroni：m=21 → 0.05/21（界 0.05/42）；m=7 → 0.05/7（界 0.05/14）；Q3 与 C25 两族数值正确。
5. 本轮新增数字自洽：B-1 稳定性目标样本 50+50=100、上限 120、下限 50；跨 K 带宽 0.10；验证校准 2pp / N=2000（后验）/ 4×8=32 配置 × N=5000 × 24 h 桶 + 右删失桶（寿命）；PM 配额 ⌊C_eval*/2⌋=4（C_eval*=8）且 from PM-only。
6. 决策清单：§19 恰 D-01..D-25（25 项）；17 必达项全部覆盖（H2 动作集=D-18/D-20、PM 区别=D-19、稳定性=D-10、样本划分=D-06、预算=D-09、密度复核=D-14、C25=D-15/D-24、provenance=D-16/D-17 等）。
7. 交叉引用：§4.1、§21.4、§22 存在；§4(b)→§6.2（ROLLOUT_ALT_SALT）、§10→§11/§12、§12→§10 A2b、§15→§11/§12、§16→§4(d)/§13 触发 1、§17.2→§3/§15/§8/§9/§4.1、D-20→§10/§12、D-22→§8/§9、D-23→§4.1、D-25→§11/D-11 均有效。
8. **1 项遗留已当场修复**：§8 生成器验证原残留「边际偏差 ≤ 3 个百分点」未冻结 → 已改为冻结校准（可达模式清单 + N=2000 + 2pp + 联合四格 2pp）；§9 桶检验同步冻结（32 配置 + N=5000 + 24 h 桶 + 右删失桶 + 2pp）。修复后 grep 确认规范正文无「3 个百分点」「A2 = PM_REPLACE」「15+5」「DRAFT_WAITING_FOR_HUMAN_GATE」残留（§21 历史记录内引用除外，属追溯性描述）。
9. 无禁止行为：git status 仅新增本草案文件（untracked），**无任何 accepted 证据/权威文件被修改**；HEAD 仍为 `859bac97df42b37a467dc4f6f56e678932f305c1`；未标 CURRENT_STATE accepted；无 K 推荐；无实现/运行指令。
10. 状态标记：文档头与 §21.4 均为 **DRAFT_WAITING_FOR_FINAL_HUMAN_GATE**。

**复核结论**：文档/引用/数字/内部一致性 PASS（1 项遗留已修复）；无 blocking ambiguity 残留；待 Human Gate 最终裁决。

### 22.1 二轮机械复核（cross-model review 修订后，2026-08-15）

> 复核方式：确定性工具（grep/read/pwsh）逐项核对；无新模型设计、无代码实现、无实验运行。

1. **PM action space**：§10 A2a/A2b 行、§12 表、D-20 三者一致（核心边界 = equipment idle + PM legality；不含「队列为空」边界；forced-wait 队列非空情形纳入 B 情形）；§2/§10 均有「quota class ≠ 动作可用性」澄清；无残留「队列为空」「forced-wait … 不在范围」规范表述（§21.4 历史记录内引用除外，已被 §21.5 第 1 条声明取代）。
2. **跨 K transfer**：§4.1 / §13 触发 3 / D-23 三者一致（d_K 定义、0.10 = DESIGN CHOICE、EARLY WARNING 定位、C25 为正式门、不自动单值判失败、无 per-K tuning）。
3. **生成器验证两层化**：§8 / §9 / D-22 三者一致（A 层确定性对拍容差 1e-12 / 1e-9；B 层协议：8 核心模式 × N=5000 × 32 边际 z × `#(|z|>3.5)≤1`；32 配置 × N=2000 × Pearson χ² × `#(p<0.001)≤1`）；全文无残留「2pp」「3pp」未校正大规模硬门表述。
4. **stability CI 语义**：§4(b) / D-10 一致（点估计 ≥95% 唯一硬门；CP = disclosure；无 CI 下界第二硬门）；deviation rate=0 路由 = §13/§16。
5. **数字不变性**：种子（5/6/7、40003/40007/40008）、批数（1400/2800/1400/4200/140）、rollout（96/144/192 ≤200）、Bonferroni（0.05/21、0.05/7）与上轮一致；§19 D-01..D-25 计数不变（25 项）；17 必达项覆盖不变。
6. **交叉引用**：§21.5、§22.1 存在；§4.1→§16/§13、§8/§9→D-22、§10→§12/D-20、§13 触发 3→§4.1/§16、D-10→§4(b)、D-23→§4.1 均有效。
7. **无禁止行为**：git status 仅本草案 untracked；无 tracked 修改；HEAD 不变；无 CURRENT_STATE/CHANGELOG/accepted evidence 变更；无实现/运行指令；未 commit/push。
8. **动作数上界（formal，final-freeze review 第 1 条）**：dispatch decision point 候选 ≤3 `{A0=START_HEAD, A1=WAIT_EVENT, A2a=PM_WITH_HEAD}`；maintenance decision point 候选 =2 `{A0b=H1_NOOP, A2b=PM_IDLE}`；每点最坏 3 动作 → `C_eval* × 3 × M*` = 96/144/192 ≤ `C_rollout=200` 上界保持（以**正式动作定义**说明，不再使用未定义的 no-op）；`a_H1` 对两类点均有定义（dispatch=A0；maintenance=A0b）；无未定义基线动作。

**二轮复核结论**：文档/引用/公式/内部一致性 PASS；无 unresolved ambiguity 残留；状态保持 **DRAFT_WAITING_FOR_FINAL_HUMAN_GATE**。

### 22.2 三轮机械复核（final-freeze review 修订后，2026-08-15）

> 复核方式：确定性工具（grep/read/pwsh）逐项核对；无新模型设计、无代码实现、无实验运行。按 final-freeze review 第 4 条检查清单逐项：

1. **PM_IDLE 每种场景都有明确 baseline action**：maintenance decision point 候选 = `{A0b=H1_NOOP, PM_IDLE}`（§10）；`a_H1 = A0b` 于 §1.1/§4/§10/D-18 一致；**无任何「PM_IDLE vs 非法 START_HEAD」表述**（grep 确认）。
2. **queue-empty PM opportunity 实际存在 decision point 定义**：MAINTENANCE_DECISION_POINT 明确覆盖 queue empty 与 queue nonempty-but-no-legal-head（§10/§12/D-20）。
3. **dispatch / maintenance 不重复**：「不重复生成」规则——每资源每闭包至多一个决策点（§10）。
4. **dp ordering 唯一**：固定资源序 A/B/C/E + `dp` 索引纯函数 + checker 独立复算（§10/§6.2）。
5. **action-count 上界 ≤3**：dispatch ≤3 `{A0,A1,A2a}`；maintenance =2 `{A0b,A2b}`；`C_eval*×3×M*` = 96/144/192 ≤ C_rollout=200 保持（§22.1 第 8 条；正式动作定义，无 no-op）。
6. **a_H1 对所有决策点有定义**：dispatch → A0；maintenance → A0b（§1.1/§4/§10）。
7. **Pro/high 身份证据无过度声明**：文档头 / §21 引言 / §21.1 / §21.2 均改为 requested model + reasoningEffort = UNVERIFIED；grep 确认无「fresh verified Pro/high」「/ high」残留于审计身份行。
8. **§22 historical vs §22.1 current normative 无歧义**：§22 标题横幅 HISTORICAL / SUPERSEDED BY §22.1；§21.4 第 9 条加历史追溯注；当前唯一有效验证规格 = §8+§9+D-22+§22.1。
9. **D-01..D-25 与正文一致**：§19 计数 25 项不变；D-08/D-18/D-20/D-21 更新与 §2/§10/§12/§4.1 一致；17 必达项覆盖不变；种子/批数/rollout/Bonferroni 数字不变。
10. **无禁止行为**：git status 仅本草案 untracked；无 tracked 修改；HEAD 不变；无 CURRENT_STATE/CHANGELOG/accepted evidence 变更；无实现/运行指令；未 commit/push。

**三轮复核结论**：全部检查项 PASS；无 blocking/unresolved ambiguity；状态 **DRAFT_WAITING_FOR_FINAL_HUMAN_GATE**（freeze candidate）。

### 22.3 四轮机械复核（final-freeze VERIFIED review 修订后，2026-08-15）

> 复核方式：确定性工具（grep/read/pwsh）逐项核对；无新模型设计、无代码实现、无实验运行。按 final-freeze VERIFIED review 第 1/4/5 条检查清单逐项：

1. **删除跨侧事后 borrowing**：grep 确认规范正文无「某侧不足则从另一侧补足」「不足 C_eval* 则全取」「按冻结顺序补足」「余量按时间序补足」等表述（§2 配额块已整体改写为 ONLINE HARD CAPS；§22 历史记录内引用除外）。
2. **在线硬上限**：`W_cap=⌈C_eval*/2⌉`、`P_cap=⌊C_eval*/2⌋`；C_eval*=6 → 3+3、C_eval*=8 → 4+4（§2/D-08 一致）；wait/PM 互不借用；未用额度批末失效；C_eval* 不要求凑满；`selected_for_rollout(t)=f(history ≤ t, quota_state(t))` 纯函数。
3. **PM 年龄桶在线算法**：B1=[120,160)/B2=[160,200)/B3=[200,240) 各至多 1 个 bucket-first slot（首次出现即占用）；P_cap=4 → 恰 1 个 extra slot（bucket-first 已用且 cap 未耗尽的首个后续 PM-only 点即时占用）；P_cap=3 → 无 extra；未出现桶额度失效；不跨桶回补、不回溯、不读未来桶（§2/D-08 一致）。
4. **wait 在线规则**：按发生时间取前 W_cap 个 wait-class 点（含 both 点）；达 cap 后不再 rollout；不得因未来 PM 不足回溯加 wait（§2/D-08 一致）。
5. **causality 断言（checker，§2 规范 + 本记录）**：`selected_for_rollout(t)` 只依赖 history ≤ t；构造「截至 t 完全相同、t 之后 candidate 序列不同」双历史 → t 处 rollout selection 必须相同；禁 future candidate count / future bucket presence 进入 selector；禁 retroactive selection。
6. **配额不变量**：配置断言 C_eval*=6 → 3+3、C_eval*=8 → 4+4；任一 batch `wait_selected ≤ W_cap`、`PM_selected ≤ P_cap`、`selected_total ≤ C_eval*`。
7. **D-01..D-25 一致**：§19 计数 25 项不变；D-08/D-21 更新与 §2 在线算法一致；D-18/D-20 未改动（已 VERIFIED 项）。
8. **已 VERIFIED 项未改动**：A0b / DISPATCH / MAINTENANCE / PM_IDLE vs A0b / dp ordering / UNVERIFIED / §22 横幅 / §8-§9 / cross-K / C25 / M/C_eval 网格与 C_rollout=200——grep 抽查与上轮一致。
9. **无禁止行为**：git status 仅本草案 untracked；无 tracked 修改；HEAD 不变；无 CURRENT_STATE/CHANGELOG/accepted evidence 变更；无实现/运行指令；未 commit/push。

**四轮复核结论**：全部检查项 PASS；无 blocking/unresolved ambiguity；状态 **DRAFT_WAITING_FOR_FINAL_HUMAN_GATE**（VERIFIED FINAL GATE candidate）。
