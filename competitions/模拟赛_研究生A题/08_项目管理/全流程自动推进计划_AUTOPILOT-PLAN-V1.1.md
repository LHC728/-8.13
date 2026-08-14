# 全流程自动推进框架（Pilot #1 正式治理版）——AUTOPILOT-PLAN-V1.1-FINAL

> 文档版本：`AUTOPILOT-PLAN-V1.1-FINAL`
> 定稿日期：2026-08-14
> 当前授权：**AUTOPILOT PILOT #1：G2-03 S2 完成节点 → Whole G2 Macro Gate**
> 授权起点候选：`689d0c253be63a889c163b2e473f9226b0899c3e`
> 授权终点：`Whole G2 Macro Gate`，无论 PASS/FAIL 均强制停机
> 关联：`AGENTS.md`、`CURRENT_STATE.md`、`CHANGELOG.md`、`01_审计/问题契约.md`、`01_审计/检查注册表_V3.1.md`、`08_项目管理/模型分级与任务路由规则.md`、当前冻结任务包
> 性质：本计划**不改变任何已签字数学口径、检查口径或冻结模型语义**；只规定自动推进、模型路由、风险升级、证据失效、恢复、预算、并发与人工停点。
> 生效条件：必须先完成本文第 2 节 `AUTOPILOT BOOTSTRAP`；Bootstrap 未提交并推送前，本计划不得被视为已激活。

---

## 0. 核心结论

本项目已经进入适合开始自动化的阶段，但当前只授权**渐进式自动驾驶**，不授权从 G2 直接无人值守跑到 G7。

Pilot #1 自动范围：

```text
G2-03 S2 completed
  → S3：DES / CP-SAT / hand 三方机械对拍
  → G2-03 收口
  → G2-04：独立 event-log replay checker
  → fault injection / reproducibility / one-command verification
  → Whole G2 formal candidate evidence
  → Whole G2 独立 L3 只读验收
  → MACRO STOP
```

目标不是减少检查，而是把：

> 每个小阶段人工中转

改成：

> **冻结规格 → E 执行 → 独立 E2 核验 → 风险分级 → 自动继续 / D 审阅 / Human Gate。**

外部 GPT 不再参与普通 GREEN 小阶段；只在 Macro Gate、RED 或队伍主动请求时介入。

---

## 1. 启动快照与当前边界

### 1.1 启动时必须机械确认的事实

Pilot #1 Bootstrap 开始时，Coordinator 必须重新确认，而不是仅相信聊天报告：

* branch = `g2-02-impl`；
* HEAD = `689d0c253be63a889c163b2e473f9226b0899c3e`，或 Human Gate 明确批准的其直系后续治理 commit；
* accepted S1 deterministic DES commit = `31b0bffb72d6b805ae313ddb9e5e0ae9a83c16ab`；
* S2 CP-SAT commit = `689d0c253be63a889c163b2e473f9226b0899c3e`；
* S1 accepted，S2 implementation completed，三方对拍未闭合；
* G2-04 未开始；
* Whole G2 未 PASS；
* G3、H1 formal、H2、100-device formal run 均未开始。

若 Git / 文件事实与以上不一致，不得自行“按最新看起来合理的状态”继续，先进入 `BOOTSTRAP_STATE_RECONCILIATION`。

### 1.2 Pilot #1 明确不授权

Whole G2 Macro Gate 之前禁止自动进入：

* G3 keyed RNG / 随机寿命 / 设备再生；
* H1 正式实验；
* H2；
* 100-device formal run；
* Q2 正式结果冻结；
* Q3 K 推荐；
* Q4 管理建议；
* G7 最终论文提交。

Whole G2 即使全部绿色，也必须停机。

---

## 2. AUTOPILOT BOOTSTRAP：自动驾驶正式启用前的原子交接

Bootstrap 是 Pilot #1 的第一个任务，但**不做模型计算**。它只负责让治理文件、状态和工作树与本 FINAL 版一致。

### 2.1 治理冲突必须先消除

当前治理文件中若仍存在以下旧规则：

* 把具体 GPT 型号永久写死为 L0–L4 唯一路由；
* “所有 L2 必须 D 审阅后才能放行”；
* 与本计划 `L2-GREEN 可自动放行` 冲突的条款；

则 Pilot #1 不得直接启动 S3。

Bootstrap 必须同步修改：

1. `AGENTS.md`；
2. `08_项目管理/模型分级与任务路由规则.md`；
3. `CURRENT_STATE.md`；
4. `CHANGELOG.md`；
5. 将本 FINAL 文件正式落入 `08_项目管理/`。

### 2.2 D / E 角色抽象

治理层只冻结能力角色，不永久绑定某个产品名：

* `E = Execution`：执行已冻结规格；
* `E2 = Independent Execution/Checker`：异源独立核验；
* `D = Decision / Reviewer`：处理语义、设计、接口高风险与 Macro 审阅；
* `D-red = independent D reviewer`：L4 / 关键 Macro 的反方审阅。

当前 DeepSeek Harness 的 Pilot #1 runtime mapping 冻结为：

| 角色                    | 当前映射                      | 默认 reasoning |
| --------------------- | ------------------------- | ------------ |
| E / Coordinator 子执行   | `deepseek-v4-flash`       | medium/high  |
| E1 受控实现               | `deepseek-v4-flash`       | high         |
| E2 / oracle / checker | fresh `deepseek-v4-flash` | high         |
| D / YELLOW reviewer   | fresh `deepseek-v4-pro`   | high         |
| D / Macro proposal    | fresh `deepseek-v4-pro`   | high         |

该映射属于 runtime mapping，不改变 D/E 治理定义。未来模型变化只更新 mapping，不改风险规则。

### 2.3 L2 放行规则正式修改

旧规则“L2 一律必须 D 审阅”废止，替换为：

#### L2-GREEN

只有同时满足以下条件，L2 才可不经 D 自动放行：

1. 数学/业务语义已冻结；
2. 输入、输出、边界、失败行为已写明；
3. 有明确机器验收或 hand / analytical / independent oracle；
4. 主实现与独立核验不是同一 Agent 实例；
5. checker 不依赖主实现内部状态或主派生输入；
6. 所有冻结 hard checks PASS；
7. 无 spec / fixture / oracle / acceptance 修改需求；
8. 无未解释差异；
9. 无强结论输出；
10. 当前风险判定为 GREEN。

满足时：`E1 + E2 + mechanical acceptance` 可自动进入下一任务，不强制调用 D。

#### L2-YELLOW

出现新接口接缝、首次复杂集成、可定位但非纯机械差异、实现可能静默偏离冻结语义时，必须 fresh D 审阅；最多允许一次受限 patch/rebind。

#### L2-RED

只要涉及题意、公式、状态转移、指标、容差、搜索空间、oracle 真实性或强结论，立即 Human Gate。

### 2.4 旧 untracked 审阅稿的处理

若存在：

`08_项目管理/全流程自动推进计划_待审阅.md`

且 SHA-256 等于此前登记值：

`8903f98622531727f11775b0171e9d997541af45309bb3e42c13a265d3db9113`

则 Bootstrap 获得一次性授权：

* **不得删除内容**；
* 将其保存到 `99_归档/自动推进计划/` 下作为 `AUTOPILOT-PLAN-V1.0_待审阅_20260814.md` 或等价无冲突名称；
* 将本 FINAL 版落为当前正式计划；
* 取消该草稿的 `KNOWN_TOLERATED_UNTRACKED` 临时例外。

若 hash 不同，视为另一个 writer 已修改，立即 BLOCK，不自动归档。

### 2.5 状态同步

Bootstrap 必须把 `CURRENT_STATE.md` 更新为至少包含：

* S1 deterministic DES = ACCEPTED；
* S2 CP-SAT oracle = COMPLETED，待 S3 三方对拍；
* `AUTOPILOT-PLAN-V1.1-FINAL` = ACTIVE FOR PILOT #1；
* Pilot #1 start checkpoint；
* Pilot #1 Macro Stop = Whole G2；
* G2-04 / G3 / H1 formal / H2 当前真实状态；
* runtime budget 来源为 launch parameters，而非本文写死金额。

`CHANGELOG.md` 记录：

* D/E role abstraction；
* L2-GREEN 自动放行规则；
* Pilot #1 起点与终点；
* Bootstrap 治理 commit；
* 旧 V1.0 草稿归档。

### 2.6 Bootstrap commit

Bootstrap 的改动必须作为一个明确治理 checkpoint 提交并 push。

建议 commit message：

`activate AUTOPILOT Pilot #1 governance`

Bootstrap commit 成功前，不得启动 S3。

---

## 3. 风险分级：GREEN / YELLOW / RED

每个子任务开始前、每次失败后、每次 patch 后，都必须重新计算 `risk_level`。

| 风险         | 典型情形                                                             | 默认动作                                       |
| ---------- | ---------------------------------------------------------------- | ------------------------------------------ |
| **GREEN**  | 冻结 spec 下实现、测试、hash、schema、runner、既有 oracle 对拍、显式路径 commit       | 自动执行；E / E2 / 本地工具；不找 D、不找外部 GPT           |
| **YELLOW** | 新接口接缝、首次复杂 runner、非语义 schema 兼容、可定位实现偏差、跨模块集成风险                  | fresh D/high 只读审阅；确认不改语义后最多一次 patch/rebind |
| **RED**    | 题意歧义、冻结 spec 冲突、公式/状态转移/指标/容差/搜索空间变化、oracle 冲突、checker 独立性失效、强结论 | 立即硬停；Human Gate                            |

### 3.1 第一次出现就必须 RED

以下事项不适用“先自动修两次”：

* 修改 `问题契约.md`；
* 修改冻结公式、观测语义、状态转移或同刻事件顺序；
* 修改指标定义、分母、容差；
* 缩小/扩大策略搜索空间；
* hand / analytical / independent oracle 与主实现存在无法由实现 bug 解释的矛盾；
* 为了 PASS 必须改 fixture / oracle / acceptance；
* checker 读取主模型内部状态、共享 transition、共享 DES-derived input；
* 冻结依赖版本必须改变；
* 最优 K、H2 去留、管理建议、论文强结论。

### 3.2 自动修复预算

* GREEN：同类机械错误最多自动修 **2 次**；仍失败 → YELLOW。
* YELLOW：最多 **1 次 D 审阅 + 1 次 patch/rebind**；仍失败 → RED。
* RED：**0 次静默自动修复**。
* 禁止通过扩大容差、删测试、改 oracle、改 hand truth、覆盖失败证据来消除失败。

---

## 4. 标准自动循环

```text
读取 CURRENT_STATE / authoritative spec
  → 确认 ownership / read-write scope
  → 风险分级
  → GREEN：E1 / E2 / runner / mechanical acceptance
  → 证据失效分析
  → 必要重跑
  → acceptance PASS
  → Coordinator 更新 CURRENT_STATE / CHANGELOG
  → commit / push
  → 若未触及 Macro Stop，自动进入下一任务

YELLOW：fresh D → 最多一次受限 patch/rebind → 重新验收
RED：立即 Human Gate
```

只有 formal run 建立不可变 evidence package；单测 / smoke test 不伪装成 formal evidence。

---

## 5. 权威来源与防上下文漂移

### 5.1 模型语义权威

1. 已签字 Human Gate；
2. `01_审计/问题契约.md`；
3. `01_审计/检查注册表_V3.1.md`；
4. 当前冻结 task package；
5. 当前冻结 `03_模型/**`；
6. implementation / tests；
7. 聊天摘要、Agent 自述、代码注释。

### 5.2 当前状态权威

1. `CURRENT_STATE.md`；
2. `CHANGELOG.md`；
3. Git commit / evidence manifest；
4. 聊天报告。

若状态文件与 Git 事实冲突，不能简单按“状态文件层级更高”继续；进入 `STATE_RECONCILIATION`，由 Coordinator 用 commit / manifest /测试事实修复状态漂移。

### 5.3 执行治理权威

Bootstrap 完成后：

1. `AGENTS.md`；
2. 当前冻结 task package ownership / scope；
3. `AUTOPILOT-PLAN-V1.1-FINAL`；
4. `模型分级与任务路由规则.md` 的详细路由说明。

这些文件必须在 Bootstrap 中被同步到互不冲突。若再次发生实质冲突，至少 YELLOW；涉及语义则 RED。

### 5.4 上下文最小化

fresh Agent 只读当前任务必要权威文件；禁止默认灌入：

* 全历史聊天；
* 旧 task package；
* `99_归档/**`；
* 其他 Agent 的推理摘要。

---

## 6. 独立核验规则

E2 / checker / oracle 必须：

* 不导入主模型核心；
* 不读取主模型派生 release/start/finish 作为输入；
* 不共享主 transition；
* 不共享主 dispatch loop / queue mutation；
* 只共享 primitive input、参数、schema、task identity、冻结语义常量；
* 与 E1 使用不同 Agent 实例；
* 需要时使用不同算法路径或独立 replay / solver formulation。

checker 独立性一旦失效，直接 RED。

---

## 7. 证据与“修改后证据失效”规则

### 7.1 Formal evidence

正式运行必须：

* 绑定 run_id；
* 保存 input/config、代码/参数/spec hash；
* 保存原始输出、checker report、exit code；
* evidence directory 不覆盖、不改写；
* failed formal run 同样保留；
* 论文数字只来自 accepted/frozen run。

### 7.2 Invalidation Report

任何 patch / rebind / spec / config 变化后，在继续使用旧 PASS 前，Coordinator 必须产生一个机械的 `INVALIDATION_REPORT`，至少回答：

* changed_files；
* changed_semantics = YES/NO；
* affected_tests；
* affected_checkers；
* affected_formal_runs；
* affected_paper_numbers；
* required_reruns；
* still_valid_evidence。

### 7.3 最小失效原则

* **spec / 问题契约变化**：所有依赖该语义的下游 evidence 失效；通常 RED/Human Gate。
* **主代码变化**：该代码生成的旧 formal output 不得继续作为当前代码的证据；相关 tests/checkers/formal run 必须重跑。
* **checker 代码变化**：旧 checker PASS 失效；若主 output hash 未变，可对同一 immutable output 重新跑 checker，不要求无理由重跑主模型。
* **config / parameter 变化**：受影响运行全部失效；不受影响的其他 scenario 可保留。
* **schema 变化**：所有依赖该 schema 的 producer/consumer acceptance 至少重跑接口测试。
* **纯文档/注释且明确不改变语义/接口**：可标记 `NO_RUNTIME_INVALIDATION`，但必须由 diff/检查证明。

禁止“修完 bug 后沿用修复前 formal PASS”。

---

## 8. 崩溃、断线与恢复协议

AUTOPILOT 不得依赖某个聊天 session 的记忆恢复。

### 8.1 恢复时只信磁盘和 Git

Coordinator 重启后依次读取：

1. `AGENTS.md`；
2. `CURRENT_STATE.md`；
3. `CHANGELOG.md` 最近相关条目；
4. 当前 task package；
5. Git HEAD / status / ahead-behind；
6. 最近 accepted commit / run manifest；
7. 当前阶段明确的 worktree sentinel。

### 8.2 恢复分类

* `CLEAN_ACCEPTED_CHECKPOINT`：可以从下一任务继续。
* `CLEAN_CANDIDATE_COMMIT_NOT_ACCEPTED`：重做 acceptance，不得直接晋级。
* `DIRTY_AUTHORIZED_PATHS_ONLY`：视为中断中的候选工作；重新执行该阶段完整机械验收后才能继续。
* `DIRTY_UNKNOWN_PATH`：BLOCK。
* `EVIDENCE_DIR_PARTIAL`：不得把半成品 run 当 formal；按 runner 规则生成新 run_id，保留残缺目录或按既有失败证据规则处理，禁止覆盖。
* `STATE_GIT_MISMATCH`：进入 `STATE_RECONCILIATION`。

### 8.3 禁止的恢复方式

不得：

* 猜“上一个 Agent 应该已经做完”；
* 根据聊天摘要直接写 PASS；
* reset/clean 掉不明工作；
* 复用不完整 formal run 目录；
* 跳过 acceptance 直接从中断处向后推进。

---

## 9. Git / 并发 writer / 工作树纪律

* 一个文件同一时刻只能有一个 writer；
* 同一 working tree 禁止两个顶层 writer 修改重叠路径；
* 显式 path staging；禁止 `git add .` / `git add -A` / `git add --all`；
* 禁止 reset / clean / force push / amend/rebase 已进入证据链的历史，除非 Human Gate 特批；
* 出现未授权 tracked/untracked 默认 BLOCK；
* 不擅自删除、移动、提交、忽略外部文件；
* Human Gate 可登记 `KNOWN_TOLERATED_UNTRACKED`，必须 path + SHA-256；
* tolerated sentinel hash 改变 = concurrent writer → RED/BLOCK。

Bootstrap 正式归档旧 V1.0 草稿后，应不存在针对该草稿的临时 tolerated exception。

---

## 10. Pilot #1 自动推进范围

Pilot #1 允许自动完成：

1. **S3 三方对拍**：accepted DES vs independent CP-SAT vs frozen hand；
2. G2-03 收口；
3. G2-04 independent event-log replay checker；
4. 最小 keyed checks / accounting replay / checker isolation；
5. fault injection；
6. reproducibility / one-command verification skeleton；
7. Whole G2 formal candidate run + immutable evidence package；
8. fresh D / Pro-high Whole G2 只读 L3；
9. 形成 Whole G2 Macro Gate 报告；
10. **无条件停机**。

S3 若出现：

* 纯实现/桥接错误且冻结 oracle 明确 → YELLOW；
* hand/spec/oracle 语义冲突 → RED。

---

## 11. Macro Gate 规则

### 11.1 Macro Gate A：Whole G2

必须停。检查：

* deterministic DES；
* DES / CP-SAT / hand 三方一致性；
* replay checker；
* fault injection；
* reproducibility；
* formal evidence；
* G2 检查注册表闭合；
* 自动化质量；
* 是否允许进入 G3。

### 11.2 Macro Gate 的失败规则

Macro Gate 的 final L3 只要给出：

* FAIL；
* BLOCKED；
* unresolved semantic concern；
* confidence 不足以签字；

则立即：

`AUTOPILOT_MACRO_GATE_WHOLE_G2_STOPPED`

**不允许**在 Macro Gate 结论出来以后自动再修一轮、自动重跑一轮然后自己翻成 PASS。

Macro Gate 后任何 patch 都必须由 Human Gate 重新授权一个明确修复阶段。

### 11.3 后续 Macro Gate（本 FINAL 只定义，不提前授权）

* B：G3 / C24 / H2；
* C：Q2 pilot + 正式实验；
* D：Q3 / K 推荐；
* E：Q4 / 管理建议；
* F：论文最终冻结。

Pilot #1 PASS 只表示可以**考虑**授权 Pilot #2，不代表自动获得授权。

---

## 12. Pilot #1 出口条件

到达 Whole G2 Macro Stop 前必须同时满足：

1. S3 三方对拍 PASS；
2. G2-04 checker 独立性 PASS；
3. fault injection 能抓住预注册错误；
4. replay/accounting 独立复算关键状态；
5. reproducibility / one-command skeleton PASS；
6. formal evidence 完整、hash 绑定、失败 evidence 未覆盖；
7. Whole G2 fresh D L3 已运行并给出明确结论；
8. 没有未解决 RED；
9. 工作树没有未知 writer；
10. 所有 patch 已执行 invalidation analysis 和必要 rerun；
11. CURRENT_STATE / CHANGELOG / Git / evidence 相互一致；
12. 到达后强制停止自动推进。

---

## 13. 自动化质量验收

Whole G2 停机时，除数学结果外，还必须审自动化本身：

| 项目                    | PASS 条件                                       |
| --------------------- | --------------------------------------------- |
| 越权写入                  | 0 个未授权路径                                      |
| 语义漂移                  | 未经 Human Gate 不修改冻结语义                         |
| L2-GREEN 放行           | 仅在 10 条条件全部满足时使用                              |
| checker 独立性           | 无主模型内部依赖                                      |
| 失败处理                  | 正确升级，不静默改 oracle                              |
| evidence invalidation | patch 后旧证据正确失效并重跑                             |
| 恢复纪律                  | 无靠聊天猜状态；仅从 accepted checkpoint 恢复             |
| 状态一致性                 | CURRENT_STATE / CHANGELOG / Git / evidence 一致 |
| 并发安全                  | 无未知 writer                                    |
| 成本                    | 未超过 runtime hard budget                       |
| Agent 路由              | D 未用于纯机械任务；E 未裁决 RED                          |
| Macro Stop            | Whole G2 后未进入 G3                              |

任一关键项失败，即使模型结果 PASS，也不得扩大 Autopilot 授权。

---

## 14. 成本策略

长期治理只冻结政策，不写死余额和价格。

* E/Flash 默认；
* D/Pro 只用于 YELLOW、L3/L4、Macro；
* 普通子任务默认最多 1 个 fresh child，除非 task package 明确授权并行；
* YELLOW 最多 1 次 D adjudication + 1 次 patch；
* 达预算阈值不得自动提高预算。

每次 Pilot 启动必须从 launch command 读取：

* `soft_budget`；
* `hard_budget`。

两者状态为：

`REQUIRED_AT_LAUNCH`

若缺失：

`AUTOPILOT_BOOTSTRAP_BLOCKED_MISSING_RUNTIME_BUDGET`

规则：

* soft budget 达到：停止新增非必要 D/Pro 和探索支线；
* hard budget 达到：立即 RED/Human Gate。

---

## 15. 时间策略：timebox + quality gate

> **Timebox 控制投入；Quality Gate 控制能否前进。**

* 不因赶时间降低 checker、放宽容差、删测试；
* 时间不足先删可选复杂支线，不删硬检查；
* H2 是典型 timebox candidate；
* Q4 只做最重要的少数交互；
* 论文必须保留独立时间。

具体 timebox 属于 runtime launch / 后续 Macro 授权，不写死为本 FINAL 的数学门槛。

---

## 16. H2 规则（仅定义未来治理，不在 Pilot #1 授权）

* 不预先删除 H2；
* 不预先承诺 H2；
* G3 出口按 C24 检查机会密度、M、预算、墙钟、样本划分；
* 未准入则保留 H1/R1；
* 准入后仍需独立留出评估和稳定性检查；
* H2 去留属于强结论，Human Gate 签字。

---

## 17. 自动化禁止事项

Agent 永远不得：

* 自行改题意口径；
* 自行改检查注册表硬门；
* 为 PASS 修改 oracle / hand truth；
* 用主模型输出喂独立 checker；
* 覆盖失败 evidence；
* patch 后沿用已失效 formal PASS；
* 把 debug 数字写论文；
* 自动冻结最优 K；
* 自动把模型内反事实写成现实因果；
* 自动提交最终竞赛作品；
* 为省钱降低冻结核验强度；
* 在 Macro Gate FAIL 后自行修复并跨 Gate。

---

## 18. Pilot #1 状态机

```text
AUTOPILOT_BOOTSTRAP_PENDING
  ↓
AUTOPILOT_PILOT_1_READY
  ↓
AUTOPILOT_ACTIVE_GREEN
  ↓（接口/实现风险）
AUTOPILOT_ACTIVE_YELLOW_REVIEW
  ↓（D 确认无语义变化 + 允许一次 patch）
AUTOPILOT_ACTIVE_GREEN
  ↓（RED）
AUTOPILOT_HARD_STOP_RED

AUTOPILOT_ACTIVE_GREEN
  ↓（Whole G2 candidate ready）
AUTOPILOT_MACRO_GATE_WHOLE_G2_REVIEW
  ↓
AUTOPILOT_MACRO_GATE_WHOLE_G2_WAITING_FOR_HUMAN
```

崩溃恢复状态额外允许：

```text
AUTOPILOT_RECOVERY_REQUIRED
AUTOPILOT_STATE_RECONCILIATION
AUTOPILOT_BLOCKED_UNKNOWN_WORKTREE
```

不得存在 Whole G2 → G3 的自动转移。

---

## 19. Pilot #1 启动合同

### 19.1 已由 Human Gate 确认

* Pilot #1 范围：`APPROVED`；
* GREEN 自动推进：`APPROVED`；
* L2-GREEN 无强制 D：`APPROVED`；
* YELLOW 可自动调用一次 fresh D/Pro-high：`APPROVED`；
* RED 必停：`APPROVED`；
* Whole G2 必停：`APPROVED`；
* D/E 角色抽象 + runtime mapping：`APPROVED`；
* 最终竞赛提交由队伍执行：`APPROVED`。

### 19.2 启动时必须提供

以下不是本 FINAL 的固定内容，而是每次启动的 runtime 参数：

```text
soft_budget = REQUIRED_AT_LAUNCH
hard_budget = REQUIRED_AT_LAUNCH
```

可选：

```text
timebox = OPTIONAL_RUNTIME_PARAMETER
```

### 19.3 Pilot #1 第一个模型任务

Bootstrap 完成并 push 后，第一个自动模型任务是：

> **G2-03 S3：accepted deterministic DES / independent CP-SAT / frozen hand fixture 三方机械对拍。**

不得重新实现 S1/S2。

---

## 20. 最终定稿声明

本文件已经完成 V1.1 审阅修订，并纳入以下关键修正：

* 从“所有 L2 必须 D 审阅”改为风险驱动 `L2-GREEN / YELLOW / RED`；
* D/E 角色与具体模型解耦；
* Pilot #1 当前 runtime 映射为 DeepSeek Flash=E、Pro=D；
* 增加原子 Bootstrap，先同步 AGENTS / routing / CURRENT_STATE / CHANGELOG；
* 增加修改后 evidence invalidation；
* 增加崩溃/断线 recovery；
* Macro Gate FAIL 后禁止自动修复翻盘；
* runtime budget 改为启动参数，不写死余额/价格；
* 保留 checker 异源、Git、安全、不可变 evidence、Macro Stop 等硬门。

正式项目内文件建议命名：

`08_项目管理/全流程自动推进计划_AUTOPILOT-PLAN-V1.1.md`

Pilot #1 Bootstrap 落库后，本文件即成为当前自动推进治理依据之一。
