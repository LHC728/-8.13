# CURRENT_STATE

> 最后更新：2026-08-14
> 状态版本：`STATE-2026-08-13-G2.4`
> 当前 Gate：**AUTOPILOT PILOT #1 = STOPPED（Macro Stop 已到达）；WHOLE_G2_GOVERNANCE_AND_EVIDENCE_REPAIR 授权执行中：G2-04-SPEC-V1.0 已冻结（FROZEN_PENDING_REBIND），rebind 与新 qualifying Macro L3 待完成；Whole G2 = NOT PASS；G3/H1/H2/100-device/Q2/Q3/Q4 = NOT STARTED**
> 当前检查注册表：[`CR-V3.1`](01_审计/检查注册表_V3.1.md)

## 1. 新对话只需先读

1. 本文件；
2. [`01_审计/问题契约.md`](01_审计/问题契约.md)；
3. [`01_审计/检查注册表_V3.1.md`](01_审计/检查注册表_V3.1.md)；
4. [`02_数据/parameters.csv`](02_数据/parameters.csv)；
5. [`03_模型/00_模型总览.md`](03_模型/00_模型总览.md)。

不要默认读取 V2/V3 历史评审、旧注册表或旧聊天。需要追溯某次决策时，再从 `CHANGELOG.md` 进入相应证据。

## 2. 当前权威来源

| 层级 | 当前来源 | 作用 |
|---:|---|---|
| 1 | 本文件 | 当前 Gate、当前版本指针、正在做与禁止事项 |
| 2 | 队伍最新签字口径、`01_审计/问题契约.md` | 题意、状态、流程和指标的实质定义 |
| 3 | `01_审计/检查注册表_V3.1.md` | 验收定义、阶段和失败处置 |
| 4 | `02_数据/parameters.csv` 与 `02_数据/configs/` | 机器可读参数与运行情景 |
| 5 | `03_模型/` 当前文档 | 数学模型、推导和算法边界 |
| 6 | `08_项目管理/项目计划.md` | 阶段节奏与分工 |
| 7 | `99_归档/` 中的历史评审和旧版本 | 仅用于追溯，不得覆盖当前口径 |
| 8 | 聊天记录 | 非权威输入；决定只有落文后生效 |

若本文件与已签字问题契约出现实质冲突，不得按层级自动覆盖，应立即上报并修正文档漂移。

## 3. G1 状态

G1 已完成并通过签字冻结。已完成：

- 题面、数据和队伍讨论稿审计；
- 问题契约、数据字典、小问依赖、风险和不超过三条路线比较；
- A03 观测语义再签字、B05 周转、B18 班界活动、B19 跨班队列；
- V3 路线再裁决及检查注册表升级到 `CR-V3.1`。

## 4. 当前冻结口径摘要

- 同一装置的 A/B/C 可占不同专用设备并行测试；E 等待三项流程通过。
- 无维修；E 首次异常后完整重做 E，指向标签只统计 `lambda`，不改变流程。
- D 只在联接时生成一次，E 重测不重抽真实状态。
- 字面主情景：一次测试总体中 `(1-q)alpha=q beta=e/2`；标准初测—触发重测链为关键替代。两情景必须全链独立运行。
- 主周转为同槽顺序运出 0.5 h、运入 0.5 h，共 1 h；0.5 h 为完整重叠替代情景。
- 测试、换新—校准、完整周转均不可跨班；只有能在本班完整结束才启动。班末禁启是操作约束，不宣称已证明弱支配。
- 换班只改变值班分队，不清空全局队列；待重测保留首败、原释放时刻和有效尝试号 2，可由下一班另一分队完整执行。
- Q3 必须枚举 `K={9,9.5,10,10.5,11,11.5,12}`；主配置不能预先断言 `K=12` 最优。
- λ 三种计数口径（`SD-G2-02-LAMBDA-ONCE`，2026-08-13 签字）：事件级期望 `(1-β_E)(2-β_E)`；「仅初测」与「每台至多一次」同按首次 E 有效真阳性计，期望 `1-β_E`；三种口径归一来源比例总体相等，计数尺度只有事件级与装置级两种。
- H1/R1 是强制基线；H2 只有 G3 出口通过 `CR-V3.1/C23–C25` 才可能保留。

完整定义以问题契约为准，本节只作导航摘要。

## 5. 当前正在做：G2

G2 的唯一目标是证明最小数学核和最小事件引擎算对，而不是获得正式竞赛答案。

已完成子任务：

- `G2-01-SPEC-V1.1.11` 观测核标定最小基线已通过最终 L3 验收；不可变证据目录为 `05_结果/G2/run_20260813T134251279572Z_f1290916/`。
- **`G2-02`（Q1 概率与质量解析链）= PASSED**：Q1 闭式解析链、16 状态枚举、吸收链、E2 独立 checker 均完成；两种观测语义（`single_test_unconditional_v1` / `standard_chain_v1`）均完成正式 canonical 并通过 D/L3 Semantic Acceptance（PASS / HIGH）。**G2-02 / Q1 正式运行结果已验收**。
  - 任务包：`G2-02-SPEC-V1.0.4`；accepted run：`05_结果/G2/run_20260814T062114478293Z_52f4ebc4/`（evidence commit `700898bfabbf4cf169049baf91084f79cc61a488`）。
  - 本范围检查全部 PASS：`CR-V3.1/C01、C02、C03、C04、C05、C19、C21、C27`。
  - evidence SHA：run_manifest `b7219b85…`；single check_report `092c4e1f…`；chain check_report `c761e828…`；file_hashes `f8145e75…`。
  - 历史失败（保留为不可变证据，未修改）：① `run_20260814T043709752483Z_99f602bd`（V1.0.3 frozen runtime dependency snapshot gap → V1.0.4 快照 9→10 + RUNNER rebind 闭合）；② `run_20260814T053311144723Z_a694e8f9`（E1 route_agreement 错误输出代表值而非三路线最大绝对偏差 → L3 semantic adjudication + E1 correction 闭合）。
  - 限制：**whole G2 Gate != PASS**；G2-03/G2-04 见下节（candidates，均未最终验收）；G3 = NOT STARTED；H1 formal experiment = NOT STARTED；H2 = NOT STARTED；100-device formal run = NOT STARTED；不发布论文正式数字；Q2/Q3 尚未开始。

- **`G2-03`（确定性最小并行 DES）= COMPLETED_CANDIDATE**（AUTOPILOT PILOT #1 已 Macro Stop；最终整体判定待 Whole G2）：
  - 任务包：`G2-03-SPEC-V1.0.2`（V1.0 freeze commit `cecaa97e21d1a7f70a61e96455deabc15aded783`；V1.0.1 governance commit `37150f2af0b047725b84ef6fa802638d329f1447`；V1.0.2 L3 fixture adjudication commit `e89a237aca095965863cf6248321d6a203730307`）。
  - **S1 deterministic DES baseline = ACCEPTED**：accepted commit `31b0bffb72d6b805ae313ddb9e5e0ae9a83c16ab`（V1.0.2 rebind）。验收记录：24 semantics implemented；F1-F12 family PASS；F4b PASS；F9b PASS（SEM-23 并发运输，T=15）；F8 K9 PASS（T=14）；py_compile PASS；unittest 27/27 PASS；main DES stdlib-only；D E2 timing PASS；SEM21 PASS；SEM23 PASS。
  - **S2 independent CP-SAT oracle = COMPLETED**：commit `689d0c253be63a889c163b2e473f9226b0899c3e`（独立约束模型；OR-Tools 9.15.6755 版本守卫；14 concrete fixtures + K9 全 PASS；unittest 72/72；无 DES import/读取；num_search_workers=1、random_seed=0）。
  - **S3 三方对拍 = PASS**：commit `add95095c31d7743d70554847b8288f59584c70f`（比较器 `04_代码/tests/three_way_crosscheck_v1.py`；DES/CP-SAT/hand 14/14 一致；F8 K9 T=84 ticks、B2 release=51/start=54/finish=66、E 66..84 三方对齐；unittest 24/24；全量回归 123/123）。**C08 确定性小例对拍子项 = 闭合候选**。
  - **`a515960cfd4f0c14e8c1952a558a56a59f87ef9f` = historical pre-V1.0.2 implementation candidate**（保留，不得 reset/revert/amend/force-push）。
  - **`AUTOPILOT-PLAN-V1.1-FINAL` = STOPPED FOR PILOT #1**（治理文件见 `08_项目管理/全流程自动推进计划_AUTOPILOT-PLAN-V1.1.md`；Pilot #1 start checkpoint = `689d0c2`；Macro Stop = Whole G2 已到达，无条件停机）。
  - **G2-03 overall = NOT PASS（最终判定待 Whole G2 L3）**。

- **`G2-04`（独立日志重放与 Whole G2 证据）= COMPLETED_CANDIDATE + pre-existing task-package governance gap 已发现**（Human Gate 2026-08-14 确认：既有实现/证据先于 G2-04 冻结任务包存在，不能直接作为 governed accepted evidence）：
  - 历史实现（pre-spec candidate）：`04_代码/checker/des_checker_v1.py`、`04_代码/tests/test_des_checker_v1.py`、`04_代码/scripts/run_g2_04_verification_v1.py`、`04_代码/scripts/run_g2_whole_v1.py`；commit `961b64ddd3360d8335380c4a01465ecd105f7db9`。
  - 历史 formal runs（pre-G2-04-spec candidates，保留不可覆盖）：`05_结果/G2/run_20260814T110423672057Z_032dfffc`（CRLF 变体，commit `2cee5e6`）、`05_结果/G2/run_20260814T110513112626Z_81563471`（LF-clean，commit `f0daa43`）。
  - **current G2-04 task package = `G2-04-SPEC-V1.0`，status = FROZEN_PENDING_REBIND**（`08_项目管理/任务包/G2-04_独立日志重放与WholeG2证据.yaml`）；rebind 与 governed formal run 待 WHOLE_G2_GOVERNANCE_AND_EVIDENCE_REPAIR Phase B。
  - **Whole G2 = NOT PASS**。当前 blocker：① G2-04 spec/evidence rebind pending；② fresh qualifying Pro/high Macro L3 pending。
  - 状态：G3 = NOT STARTED；H1 formal = NOT STARTED；H2 = NOT STARTED；100-device formal run = NOT STARTED；Q2/Q3/Q4 = NOT STARTED。

1. 实现并诊断单次无条件主观测核（G2-01 已完成）；
2. 实现标准链关键替代观测核（G2-01 已完成）；
3. 完成 Q1 闭式、16 状态枚举、吸收链与独立回代（G2-02 已完成并验收）；
4. 完成无随机的最小并行 DES；
5. 对拍 1—4 台手算小例，包括 K=9 三台跨班重测；
6. 建立最小独立 checker 和故障注入；
7. 通过 `CR-V3.1` 的 G2 适用项：`C01–C06,C08–C12,C16–C21,C27` 文档部分。

## 6. 当前禁止

- 不运行 100 台正式主实验；
- 不编码或调参 H2；
- 不冻结最优 K、预防更换阈值或管理建议；
- 不做正式敏感性和正式图表；
- 不向论文填入结果数字；
- 不修改已签字口径；若实现暴露新歧义，回到变更控制而不是自行决定。

## 7. 下一出口

只有 G2 适用硬门全部通过并形成可重放证据包，项目才进入 G3。G3 才加入键控随机状态/观测、设备寿命与再生、完整班历、周转和 H1 决策机会日志；H2 是否值得实现到 G3 出口再决定。

## 8. 当前目录映射

本轮已迁移经核验的高风险历史文件；其余材料不做无差别搬运：

| 逻辑职责 | 当前路径 | 迁移状态 |
|---|---|---|
| 数学模型 | `03_模型/` | 已建立；新模型只写这里 |
| 主模型与 checker | `04_代码/` | 已由空的 `03_代码/` 安全迁移 |
| 正式配置 | `02_数据/configs/` | 已建立；是唯一正式配置目录 |
| 结果 | `05_结果/` | 已由空的 `04_结果/` 安全迁移；成为唯一结果根目录 |
| 图表 | `05_结果/figures/` | 已由空的 `05_图表/` 安全迁移；图表仍须绑定 run_id |
| 历史评审/旧版本 | `99_归档/` | 第一至第三轮评审、V2 方案和 `CR-V3.0` 已迁入；其他历史材料按需渐进迁移 |

任何后续路径迁移必须先生成引用清单、修复链接并验证，再移除旧路径。
