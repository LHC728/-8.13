# H2 ADMISSION C24 EVIDENCE DRAFT

> 日期：2026-08-15
> 阶段：H2 ADMISSION EVIDENCE AUDIT ONLY（Human Gate；H2 实现 = NOT AUTHORIZED）
> 状态：**H2_ADMISSION_EVIDENCE_READY_WAITING_FOR_HUMAN_GATE**
> 性质：机会/分支密度诊断（admission diagnostic），非 H2 政策实现；不估计 H2 T 改善/最优政策/rollout/M/Q3 K。
> 修正记录：初版 analyzer 的设备年龄未在替换处重置，导致 mandatory/pm 误分；已修复（reset-aware age，逐资源与引擎 age 精确匹配）并重跑；本版为修正后数值。

## 0. 证据来源（Human Gate §3：仅 PRE-FORMAL G3 数据）

- 主：G3 H1 tuning `run_20260814T174022592173Z_01b7c7e7`（h1_tuning、master_seed=1、20 shared worlds；NO_PM_BEFORE_MANDATORY 为主候选）
- 敏感性：同 run 的 tau_pm_198 候选（机会密度是否依赖 tau_pm）
- 次级上下文：G3 holdout `run_20260814T180238855262Z_020bc637`（**全 100 批**、master_seed=2、tau_pm=198）
- **未使用** `05_结果/Q2/formal/**`（q2_formal worlds 是论文权威 Q2 证据，不做 H2 设计/调优）
- 引擎确定性重放重建 accepted 日志（log_hashes.json SHA-256 逐批匹配：NO_PM 20/20、tau198 20/20、holdout 100/100），不消耗新随机世界、不修改任何 accepted 证据目录
- 可复现：`04_代码/scripts/run_h2_admission_evidence_v1.py` → `tmp/h2_admission_analysis.json`

## 1. 现有 C24 计数器测的是什么（Human Gate §11 问题 1-3）

| 引擎计数器 | 语义（random_des_v1 源码） | 对 H2 决策的对应 |
|---|---|---|
| `_c24_decision_points` | active shift 下每个 WAITING FCFS head 的决策点 | 分母 |
| `_c24_waiting_opportunities` | **head 不能合法启动**（forced wait / infeasibility） | **不是 H2 strategic wait**（Human Gate 确认）；H1 强制等待仪表 |
| `_c24_pm_opportunities` | age>=120 时计数（未区分可选/强制） | 部分对应可选 PM（需分离 mandatory） |
| `_c24_legal_actions` | 实际执行的合法动作 | 非机会 |

**结论（问题 7/8 核心）**：`_c24_waiting_opportunities` 直接**高估** H2 战略等待机会（测的是 forced wait）；`_c24_pm_opportunities` **未区分**可选 PM 与强制。旧 C24 标签对 H2 选择密度**不具代表性**。

## 2. 离线重建结果（reset-aware；ACTIVITY_START 锚点）

### NO_PM（tuning，主，20 批）

| 指标 | mean | median | P90 | min | max |
|---|---|---|---|---|---|
| legal_h1_dispatch_decision_point_count | 413.1 | 413 | 420 | 407 | 424 |
| **strategic_wait_strict_count** | **11.4** | 12 | 16 | 3 | 19 |
| strategic_wait_boundary_count | 1.6 | 2 | 3 | 0 | 4 |
| strategic_wait_nonstrict_count | 12.8 | 13 | 18 | 5 | 20 |
| raw_pm_age_eligible_count | 168.8 | 175 | 177 | 141 | 181 |
| **pm_immediately_feasible_count** | **168.8** | 175 | 177 | 141 | 181 |
| mandatory_replacement_count | **0.0** | 0 | 0 | 0 | 0 |
| exact_240_count | 2.7 | 3 | 3 | 1 | 3 |
| both_wait_and_pm_count | 4.5 | 5 | 8 | 0 | 8 |
| **meaningful_h2_choice_point_count** | **177.1** | 182 | 188 | 151 | 192 |
| **meaningful_choice_fraction** | **0.429** | 0.44 | 0.50 | 0.36 | 0.46 |

zero-机会批次比例：strategic=0.0、PM=0.0、meaningful=0.0（每批都有机会）。
每 100 台：meaningful choice ≈ 177 点/100 台。每 100 日历小时（T≈830h/批）：≈ **21 点/100h**。

### 敏感性（tau_pm 是否影响机会密度）

| 指标 | NO_PM | tau_pm_198 | holdout(tau198, 全100) |
|---|---|---|---|
| strategic_wait_strict | 11.4 | 13.6 | 13.5 |
| pm_immediately_feasible | 168.8 | 125.4 | 127.1 |
| meaningful_choice_fraction | 0.429 | 0.332 | 0.336 |
| mandatory_replacement | 0.0 | 0.0 | 0.0 |
| exact_240 | 2.7 | 0.0 | 0.0 |

**结论**：**strategic-wait 机会对 tau_pm 不敏感**（11.4 vs 13.6 vs 13.5，年龄无关、由班历/寿命结构决定）；**可选 PM 机会因政策而异**（NO_PM 168.8 > tau198 125.4——预防政策消耗了可选 PM 空间；exact_240 同理）。H2 分支空间结构由设备寿命/班历主导，tau_pm 只改变 PM 侧密度。

## 3. forced wait：引擎 C24 vs 离线

- 引擎 NO_PM：`total_waiting_opportunity_count=3000`（20 批 = 150/批）——**forced wait**（head 不合法被跳过）。
- 离线 strategic_wait_strict：228（20 批 = 11.4/批）——真正的 H2 defer 机会。
- **对比**：引擎 C24 waiting（150/批）≈ 离线 strategic（11.4/批）的 **13 倍**。**旧 C24 `waiting_opportunity_count` 严重高估 H2 战略等待机会**（它测的是 forced/infeasible wait）。
- 离线 forced_wait=0（ACTIVITY_START 锚点只见合法启动）；forced wait 只能从引擎侧读——进一步证明旧 C24 waiting 字段是 H1 强制等待仪表。

## 4. PM 机会（可选 vs 强制分离，reset-aware）

- 可选 PM（age>=120、a+d<240、校准可完成）：NO_PM **168.8/批**（~41% 决策点）——**丰富**。
- 强制替换（a+d>240）：**0.0/批**（serve 锚点下不存在——引擎在 a+d>240 时强制替换而非启动 head，故 ACTIVITY_START 锚点无此情形；强制替换事件在引擎侧另行发生）。
- exact_240：NO_PM 2.7/批（单独报告）。
- **旧 C24 `_c24_pm_opportunities`（3430/20=171.5/批）≈ 可选 PM 上界（168.8）**——该字段在 NO_PM 下近似可选 PM，但语义上未排除 mandatory 且不含 reset-aware 校正，需谨慎引用。

## 5. 组合选择分类（§8）

- 决策点分类（NO_PM，20 批池化）：
  - 无可选分支：~57%（forced/mandatory/exact/serve-only）
  - wait-only（strict 或 boundary 且无 PM）：≈ (strategic_yes − both)/legal ≈ (13.0 − 4.5)/413 ≈ **2.1%**
  - PM-only：≈ (pm_feas − both)/legal ≈ (168.8 − 4.5)/413 ≈ **39.8%**
  - both（wait+PM 并存）：≈ 4.5/413 ≈ **1.1%**
- **meaningful_h2_choice_fraction ≈ 0.429**：约 43% 的合法 H1 派工决策点存在至少一个可选 H2 分支（PM 主导）。

## 6. 密度换算（§9 指标）

- choice_points_per_100_devices ≈ 177（每 100 台批次 ~177 个有意义 H2 选择点）。
- choice_points_per_100_calendar_hours ≈ 21（T≈830h/批）。
- 每批 0 机会比例：strategic=0%、PM=0%、meaningful=0%（无空批）。

## 7. 结论（Human Gate §11 问题 4-8）

1. 真正的 strategic wait 机会：**~11.4/批（strict）**——存在但**稀疏**（~2.8% 决策点）。
2. 可选预防更换机会：**~169/批**——**丰富**（~41% 决策点）。
3. 两者共存：~4.5/批——罕见但存在。
4. **H2 分支空间分类：MODERATE**（~43% 决策点有可选分支，PM 主导；wait 本身稀疏）。
5. **是否值得投入 H2 预算**：**决策权归 Human Gate**（本报告仅证据）。要点：
   - 若 H2 只做 strategic wait（defer-to-event）：空间稀疏（~3%），预算回报可能有限；
   - 若 H2 含可选预防更换：空间稠密（~43%），但**必须与强制替换/班界/寿命语义严格分离**（checker/oracle 复杂度高）；
   - 机会密度结构由寿命/班历主导（wait 侧不依赖 tau_pm）。
6. **C24 仪表修正建议**（供后续 Gate）：`waiting_opportunity_count` 更名/重定义为 forced_wait；新增 strategic_wait_strict/boundary 与 optional_pm（separated from mandatory）计数。

## 8. 边界声明

- 本阶段**未**估计：H2 T 改善、最优政策、rollout 收益、M、Q3 K。
- 未执行任何 H2 政策；未从 H1 日志虚构 counterfactual H2 结果。
- 仅测机会/分支密度。
- NO_PM 保持 Q2 accepted H1 baseline（不因 H2 admission 重开 Q2 选择）。
