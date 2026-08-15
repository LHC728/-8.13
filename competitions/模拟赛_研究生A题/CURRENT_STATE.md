# CURRENT_STATE

> 最后更新：2026-08-15
> 状态版本：`STATE-2026-08-13-G2.4`
> 当前 Gate：**Whole G2 = PASS；G3 = PASS / ACCEPTED（C17 REQUALIFIED_AFTER_C10_C12_CHECKER_FIXES）；Q2 H1 FORMAL = PASS / ACCEPTED（accepted run `2d1466ba`；Q2 主情景选中 H1 政策 = NO_PM_BEFORE_MANDATORY）；Q3/H2 BOOTSTRAP = FINAL PASS / ACCEPTED（Human Gate 2026-08-15 VERIFIED FINAL PASS / DESIGN FREEZE APPROVED；D-01..D-25 冻结；冻结权威规格 = `08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT.md` = FINAL_FREEZE_ACCEPTED；BOUNDARY 契约同步完成）；P0（H2 key schema bootstrap）= VERIFIED FINAL PASS / ACCEPTED（Human Gate；P0 关闭）；**Q3 H1 FORMAL = EXECUTION COMPLETED / AWAITING HUMAN GATE REVIEW**（正式 run `run_20260815T133840057668Z_7ee48fc0`；C06/C17 2800/2800；Tier 1 预注册报告 k\*=K12 strong（七个 K + 冻结政策集内）；**最终 Q3 K 推荐待 Human Gate review，不视为已批准**）；H2 = ADMITTED_FOR_DESIGN_ONLY / DESIGN FREEZE APPROVED（非 H2 FINAL ACCEPTANCE；**H2 实现仍 NOT YET AUTHORIZED / NOT IMPLEMENTED**）；CR-V3.1/C24 = PASS（opportunity-density evidence = PASS、budget/spec freeze = PASS）；C23 = PENDING / NOT YET EXECUTED；C25 = PENDING / NOT YET EXECUTED；Q3 = ACTIVE（七 K 正式基线已完成/待审；**无已批准 Q3 K 推荐**）；Q4 = NOT STARTED；Q2 paper numbers = AVAILABLE / AUTHORITATIVE FROM ACCEPTED FORMAL RUN；**下一阶段：Human Gate Q3 H1 formal review → 基于 accepted Tier 1 日志的确定性只读 Q3 七 K H2 opportunity-density recheck（Density FAIL → DELETE H2、Q3 H1-only；Density PASS → 才允许 Human Gate 授权 P1）**；**P1 / C23 当前仍 NOT AUTHORIZED**；Q3/H2 IMPLEMENTATION BOOTSTRAP（P1 及之后子包）未授权**
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

## 5. 已接受阶段状态（G2 = PASS；G3 = PASS / ACCEPTED）

G2 的唯一目标是证明最小数学核和最小事件引擎算对，而不是获得正式竞赛答案。**G2 = PASS / ACCEPTED（Human Gate 2026-08-14）**。已完成子任务（历史记录）：

- `G2-01-SPEC-V1.1.11` 观测核标定最小基线已通过最终 L3 验收；历史不可变证据目录 `05_结果/G2/run_20260813T134251279572Z_f1290916/`（**HISTORICAL_INVALIDATED_EVIDENCE**，hash inventory mismatch；当前 accepted = clean reissue `run_20260814T130221390333Z_8babb503`，见下节）。
- **`G2-02`（Q1 概率与质量解析链）= PASSED**：Q1 闭式解析链、16 状态枚举、吸收链、E2 独立 checker 均完成；两种观测语义（`single_test_unconditional_v1` / `standard_chain_v1`）均完成正式 canonical 并通过 D/L3 Semantic Acceptance（PASS / HIGH）。**G2-02 / Q1 正式运行结果已验收**（当前 accepted = provenance-clean reissue `run_20260814T130947069958Z_4bb92eda`，spec V1.0.5，见下节）。
  - 历史任务包/run（保留为 superseded 记录）：`G2-02-SPEC-V1.0.4`；`05_结果/G2/run_20260814T062114478293Z_52f4ebc4/`（**HISTORICAL_ACCEPTED_MATH_WITH_SUPERSEDED_UPSTREAM_PROVENANCE**；evidence commit `700898bfabbf4cf169049baf91084f79cc61a488`）。
  - 本范围检查全部 PASS：`CR-V3.1/C01、C02、C03、C04、C05、C19、C21、C27`。
  - evidence SHA：run_manifest `b7219b85…`；single check_report `092c4e1f…`；chain check_report `c761e828…`；file_hashes `f8145e75…`。
  - 历史失败（保留为不可变证据，未修改）：① `run_20260814T043709752483Z_99f602bd`（V1.0.3 frozen runtime dependency snapshot gap → V1.0.4 快照 9→10 + RUNNER rebind 闭合）；② `run_20260814T053311144723Z_a694e8f9`（E1 route_agreement 错误输出代表值而非三路线最大绝对偏差 → L3 semantic adjudication + E1 correction 闭合）。
  - 限制：**Whole G2 = FINAL PASS（Human Gate 2026-08-14）**；G2-01/G2-02/G2-03/G2-04 见下节（均 PASSED）；G3 = NOT STARTED；H1 formal experiment = NOT STARTED；H2 = NOT STARTED；100-device formal run = NOT STARTED；不发布论文正式数字；Q2/Q3 尚未开始。

- **`G2-01`（观测核标定）= PASSED**（Whole G2 Macro L3 + Human Gate FINAL PASS）：历史 run `run_20260813T134251279572Z_f1290916` = **HISTORICAL_INVALIDATED_EVIDENCE**（reason=HASH_INVENTORY_MISMATCH，保留不改，INVALIDATION_REPORT 见 `01_审计/INVALIDATION_REPORT_G2_01_hash_inventory.md`）；**accepted clean reissue = `run_20260814T130221390333Z_8babb503`**（数学输出与历史逐字一致，差异仅 request_id.run_id 经 Human Gate OPTION A 批准）。
- **`G2-02`（Q1 概率与质量解析链）= PASSED**（Whole G2 Macro L3 + Human Gate FINAL PASS）：spec `G2-02-SPEC-V1.0.5`（upstream rebind only）；历史 run `run_20260814T062114478293Z_52f4ebc4` = **HISTORICAL_ACCEPTED_MATH_WITH_SUPERSEDED_UPSTREAM_PROVENANCE**（保留不改）；**accepted governed reissue = `run_20260814T130947069958Z_4bb92eda`**（数学结果与 52f4ebc4 逐字段一致，仅 upstream provenance 更新）。
- **Whole G2 = PASS**。**U0 = CLOSED**（qualifying Macro reviewer = `G2_WHOLE_MACRO_L3_WORKFLOW_PRO_REVIEWER`，child/session `8abb6c32-9dc8-444c-ae3e-f8d9f062f7b5`，runtime 机械验证 deepseek-official/deepseek-v4-pro/high，overall=PASS/confidence=HIGH，freshness/read_only VERIFIED）；**U1 = CLOSED**（G2-01/G2-02 provenance repair 完成）。
- **`G2-03`（确定性最小并行 DES）= PASSED / ACCEPTED**（Whole G2 Macro L3 + Human Gate FINAL PASS）：
  - 任务包：`G2-03-SPEC-V1.0.2`（V1.0 freeze commit `cecaa97e21d1a7f70a61e96455deabc15aded783`；V1.0.1 governance commit `37150f2af0b047725b84ef6fa802638d329f1447`；V1.0.2 L3 fixture adjudication commit `e89a237aca095965863cf6248321d6a203730307`）。
  - **S1 deterministic DES baseline = ACCEPTED**：accepted commit `31b0bffb72d6b805ae313ddb9e5e0ae9a83c16ab`（V1.0.2 rebind）。验收记录：24 semantics implemented；F1-F12 family PASS；F4b PASS；F9b PASS（SEM-23 并发运输，T=15）；F8 K9 PASS（T=14）；py_compile PASS；unittest 27/27 PASS；main DES stdlib-only；D E2 timing PASS；SEM21 PASS；SEM23 PASS。
  - **S2 independent CP-SAT oracle = COMPLETED**：commit `689d0c253be63a889c163b2e473f9226b0899c3e`（独立约束模型；OR-Tools 9.15.6755 版本守卫；14 concrete fixtures + K9 全 PASS；unittest 72/72；无 DES import/读取；num_search_workers=1、random_seed=0）。
  - **S3 三方对拍 = PASS**：commit `add95095c31d7743d70554847b8288f59584c70f`（比较器 `04_代码/tests/three_way_crosscheck_v1.py`；DES/CP-SAT/hand 14/14 一致；F8 K9 T=84 ticks、B2 release=51/start=54/finish=66、E 66..84 三方对齐；unittest 24/24；全量回归 123/123）。**C08 确定性小例对拍子项 = 闭合（accepted）**。
  - **`a515960cfd4f0c14e8c1952a558a56a59f87ef9f` = historical pre-V1.0.2 implementation candidate**（保留，不得 reset/revert/amend/force-push）。
  - **`AUTOPILOT-PLAN-V1.1-FINAL` = COMPLETED AT MACRO STOP**（治理文件见 `08_项目管理/全流程自动推进计划_AUTOPILOT-PLAN-V1.1.md`；Pilot #1 start checkpoint = `689d0c2`；Macro Stop = Whole G2 已到达，无条件停机）。
  - **G2-03 overall = PASSED / ACCEPTED**（Whole G2 Macro L3 + Human Gate）。

- **`G2-04`（独立日志重放与 Whole G2 证据）= PASSED / ACCEPTED**（Whole G2 Macro L3 + Human Gate FINAL PASS；pre-existing task-package governance gap 已由 G2-04-SPEC-V1.0 冻结 + rebind 闭合）：
  - 历史实现（pre-spec candidate）：`04_代码/checker/des_checker_v1.py`、`04_代码/tests/test_des_checker_v1.py`、`04_代码/scripts/run_g2_04_verification_v1.py`、`04_代码/scripts/run_g2_whole_v1.py`；commit `961b64ddd3360d8335380c4a01465ecd105f7db9`。
  - 历史 formal runs（pre-G2-04-spec candidates，保留不可覆盖）：`05_结果/G2/run_20260814T110423672057Z_032dfffc`（CRLF 变体，commit `2cee5e6`）、`05_结果/G2/run_20260814T110513112626Z_81563471`（LF-clean，commit `f0daa43`）。
  - **current G2-04 task package = `G2-04-SPEC-V1.0`，status = FROZEN（PASSED/ACCEPTED）**（`08_项目管理/任务包/G2-04_独立日志重放与WholeG2证据.yaml`）。
  - **G2-04 = PASSED / ACCEPTED（rebind 后）**：runner `run_g2_whole_v1.py` 已机械 rebind（task_package_ref=G2-04-SPEC-V1.0、spec_hash=G2-04 实际 hash、upstream G2-03-SPEC-V1.0.2 进 code_snapshots/notes/frozen；fault_injection 族③标注 G2_INTERFACE_ONLY/G3_FULL 于 manifest notes；checker core changed = NO）。**accepted governed formal run = `05_结果/G2/run_20260814T114143591701Z_32913efa/`**（checker 14/14 + crosscheck 14/14、exit 0、file_hashes 匹配）。
  - 旧 formal runs（`...032dfffc`、`...81563471`）= **PRE_G2_04_SPEC_HISTORICAL_CANDIDATE**，保留不可覆盖，不冒充 governed evidence。
  - 状态：G2-04 完成（PASSED/ACCEPTED）。

- **`G3`（公共随机 DES 与 H1 基线）= PASS / ACCEPTED**（Human Gate 2026-08-15 FINAL PASS；G3-SPEC-V1.0 = accepted frozen implementation specification；AUTOPILOT PILOT #2 = COMPLETED AT MACRO STOP）：
  - 任务包：`G3-SPEC-V1.0`（status FROZEN_FOR_IMPLEMENTATION；`08_项目管理/任务包/G3_公共随机DES与H1基线.yaml`）。Human Gate G3_SPEC_DRAFT CONDITIONAL PASS → 全部决策（G3-DEC-01..07）落文 → fresh verified Pro/high 终审（session `f5550518-edfa-48cc-9213-da37ffd789bd`，deepseek-v4-pro/high）PASS/HIGH/implementation_ready=YES → 冻结。
  - Pilot #2 范围：G3-SPEC-V1.0 实现 S1→S9（key_schema → 寿命/再生 → 随机 DES+H1 → C06 oracle → C17 replay → C16 实验分离 → H1 tuning（C26）→ holdout → evidence）至 G3 Macro Gate；**无条件停机，不跨入 Q2 formal**。
  - **G3 tuning/holdout 100-device 批次（授权验证/调优）与 Q2 FORMAL 100-device 评估（未授权）明确区分**。
  - **Pilot #2 进度：S1-S9 全部完成并 accepted**（S1 key_schema commit `5a437dc`；S2 寿命/再生 `7ccb550`；S3 随机 DES `6418818`+`d88c7a3`+YELLOW `617722e`；S4 C06 oracle `d88c7a3`；S5 C17 replay `9a2b192`+YELLOW `617722e`；S6 C16 分离 `2fdd332`；S7 H1 tuning `5b70446`；S8 holdout `fad658f`；S9 evidence `f279ae6`）。YELLOW 修复（发现 A FCFS 派序 / 发现 B checker 配对）证据见 `01_审计/RED_EVIDENCE_G3_S7.md`；S8 C07 统计方法两处缺陷（GREEN）见 `01_审计/RED_EVIDENCE_G3_S8.md`。
  - **FINAL H1 CANDIDATE（冻结候选，非 Q2 最终推荐）**：tau_pm=198h（S7 accepted tuning run `01b7c7e7`；mean T=830.75h、mean PM=15/4；调优数据非 Q2 正式），在授权 h1_tuning worlds 上选出、并在 g3_holdout 上未重调验证（S8 accepted holdout run `020bc637`：C06/C17 100/100 PASS、C07 flagged=7/100 诊断正常、holdout_retune=FALSE）。**授权作为进入未来 Q2 正式评估的候选政策**；不是 Q2 最终推荐、不是论文结果、不证明 198h 全局最优、不是管理结论；不把其调优 mean T 作为 Q2 结果发布。
  - **S9 evidence package = run `fc3fe3e6`**（INDEX_OK；accepted = tuning `01b7c7e7` + holdout `020bc637`；7 个失败/被替代 run 保留不可变并标注 superseded）。
  - **G3 Macro L3 = PASS / HIGH**（qualifying reviewer `G3_MACRO_L3_REVIEWER`，session `b0f56d04-90aa-4ed8-a4bd-b5b7847f9a8c`，runtime 机械验证 deepseek-official/deepseek-v4-pro/high；freshness/read_only VERIFIED；302 G3 tests OK）。报告见 `01_审计/MACRO_REPORT_G3_L3.md`。**G3 Macro Gate = PASSED（Human Gate 2026-08-15 接受）；PILOT #2 COMPLETED AT MACRO STOP；无条件停机**。
  - **G3 accepted 范围（CR-V3.1）**：C06（G3 full layer）= PASS；C07（统计烟测/诊断层）= PASS（保留诊断解释）；C13/C14 = PASS；C15（G3 接口/重置层）= PASS（Q3 七 K 正式实验 = NOT STARTED）；C16（G3 实验分离层）= PASS；C17（G3 full replay 层）= PASS；C18 = PASS；C26（H1 政策/调优设计与冻结候选）= PASS；C24（仪表/数据收集能力）= PASS。**不声明 C23 PASS、C25 PASS、H2 准入 PASS；H2 仍未实现且未授权**。
  - 状态（Q2 激活前）：H1/Q2 formal evaluation = NOT STARTED；H2 = NOT STARTED / NOT AUTHORIZED；Q3 FORMAL = NOT STARTED；Q4 = NOT STARTED。→ **Q2 H1 FORMAL 已由 Human Gate 2026-08-15 授权激活（见下 Q2 段）**。
  - 预算：软墙钟 4h / 硬墙钟 8h（Pilot #2 已到达 Macro Stop，不再消耗）。
  - 禁止：发布/冻结 Q2 正式数字（T/S/PL/PW/YXB/管理建议）、写论文、实现 H2、枚举 K、推荐 K。

- **`Q2_H1_FORMAL`（单班制 H1 正式评估）= ACTIVE**（Human Gate 2026-08-15：Q2-FORMAL-SPEC-V1.0-DRAFT = CONDITIONAL PASS → Phase B fresh FINAL reviewer `Q2_FORMAL_SPEC_FINAL_L3_REVIEWER`（session `698f74c3-d26b-4742-9270-e079b65b82a6`，runtime 机械验证 deepseek-official/deepseek-v4-pro/high）= **PASS / HIGH / implementation_ready=YES** → 冻结；初评 FAIL 保持历史证据）：
  - 任务包：`Q2-FORMAL-SPEC-V1.0`（status **FROZEN_FOR_FORMAL_RUN**；`08_项目管理/任务包/Q2_单班制H1正式评估.yaml`）。评审记录：`08_项目管理/任务包/Q2_FORMAL_SPEC_DRAFT_REVIEW_RECORD.md`。
  - **冻结决策（Q2-FORMAL-DEC-01..06 + bootstrap 分析流）**：200 批/单元 × 8 单元 = 1600 批 / 160 000 台；namespace=q2_formal、master_seed=3、replicate_id=0..199；恰 4 个配对 Delta_T 对比（C1 PRIMARY single+1h；C2-C4 稳健），Bonferroni m=4、alpha_each=0.0125、边缘 CI coverage 0.9875（percentile 0.00625/0.99375）；PL/PW 池化 20000 台精确 CP 区间（x=0 → 单侧上界 `1-0.05^(1/20000)`）；族级证据根 `05_结果/Q2/formal/run_<UTC>_<8hex>/`；soft 4h / hard 8h；bootstrap 分析流 namespace=q2_formal_analysis_bootstrap_v1、seed=30003、B=10000。`decision_required: []`。
  - **tau_pm 候选 = 198 h**（正式前冻结；主单元 = single_test_unconditional_v1 + 1h_literal + tau_pm_198；政策参考 = 同观测/周转 + NO_PM_BEFORE_MANDATORY）；正式运行不重选 tau_pm。
  - **AUTOPILOT PILOT #3 = COMPLETED AT MACRO STOP → Q2 H1 FORMAL = PASS / ACCEPTED**（Human Gate 2026-08-15 FINAL PASS）：
    - **accepted Q2 formal run `run_20260815T061803446274Z_2d1466ba`**（05_结果/Q2/formal/）：8 cells × 200 批 × 100 台；namespace=q2_formal、master_seed=3、replicate_ids=0..199；**C06=1600/1600、C17=1600/1600 PASS**；C13/C14/C16/C18/C26 PASS（applicable formal scope）；无正式重调。
    - **Q2 主情景（single_test_unconditional_v1 × 1h_literal）正式 H1 政策选择 = NO_PM_BEFORE_MANDATORY**：ΔT = T(tau_pm_198) − T(NO_PM) = **+1.2892 h**，98.75% Bonferroni CI **[0.4625, 2.1942]** 完全>0 → 按冻结预注册解释规则：**NO_PM 完成时间更短**（不主动预防更换；保留全部冻结强制更换规则）。
    - **tau_pm=198 = HISTORICAL_TUNING_SELECTED_CANDIDATE / FORMALLY_NOT_SELECTED_FOR_Q2_PRIMARY**：正式前选出、从未用 q2_formal 重调；不宣称其最优、不删除/改写其调优历史。
    - **4 预声明对比（98.75% CI）**：C1 PRIMARY single+1h +1.2892 [0.4625,2.1942] → NO_PM 更短；C2 single+0.5h +4.2292 [3.1983,5.2963] → NO_PM 更短；C3 chain+1h −0.1281 [−1.1146,0.8000] → 不可稳定区分（不转为 tau198 优越证据）；C4 chain+0.5h +5.3211 [4.1314,6.6234] → NO_PM 更短。**整体措辞**：4 对比中 3 个偏好 NO_PM 且区间完全>0，1 个（chain+1h）不可区分，无一正式支持 tau198 更短。
    - **主单元正式聚合（accepted）**：mean T=332831/400 h（=832.0775h=34.6699d）、mean S=18851/200（94.255/100 台）、PL pooled=383/20000（0.01915）、PW pooled=17/20000（0.00085）；稀有事件精确 CP 95%：PL [0.017296,0.021146]、PW [0.000495,0.001361]（rare_event_report.json）。tau198 与 NO_PM 单元质量输出相同（C06 分离命题一致）。
    - **Q2 论文数字权威 = run `2d1466ba`**（formal_comparison_table.json + rare_event_report.json + family_aggregates.json + per-batch raw + checker/evidence reports）；禁手录数字、禁用失败 run `daead4cf`、禁用调优/holdout 值替代；手稿数值必须机械可追溯至 accepted formal 证据。
    - **首跑 `daead4cf` 保持永久 HISTORICAL_FAILED_FORMAL_ATTEMPT / VALIDATION_FAILED / paper_authoritative=false**（旧 C17 checker 的 C10/C12 缺陷；RED 证据 + INVALIDATION_REPORT ×2 + REQUALIFICATION_RECORD 保留）。
    - **CR-V3.1/C17 G3 full layer = PASS / REQUALIFIED_AFTER_C10_C12_CHECKER_FIXES**（reviewer `G3_C17_REQUALIFICATION_L3_REVIEWER`，session `ab890743`，verified Pro/high，PASS/HIGH/NO/YES/YES）；G3 = PASS/ACCEPTED；不重开无关 G3 阶段。
    - **KNOWN_NONBLOCKING_FOLLOWUPS**（不重开 Q2）：A) checks.json 中 C13/C14/C18 为 runner 断言（engine hash 不变 + C17 全量重放覆盖 + requalified G3 回归）；B) REQUALIFICATION_RECORD 有重复历史段（provenance 保留）；C) x=0 单侧 CP 分支本轮未触发（已实现，DEC-04）。
    - **Pilot #3 无条件停机**；下一 Human Gate：评估 C24 实际 H1 决策机会证据 → 裁决 H2 admission vs deletion/skip → Q3。
  - **Q2 论文数字 = AVAILABLE / AUTHORITATIVE FROM ACCEPTED FORMAL RUN `2d1466ba`**（formal_comparison_table.json + rare_event_report.json 等；禁手录、禁失败 run、禁调优/holdout 值替代）。
  - 禁止：改 G3/Q2 accepted 核心（需改 → STOP 回 Human Gate）、实现 H2、枚举 K、推荐 K、启动 Q3/Q4、写论文。

- **`H2 ADMISSION`（opportunity evidence audit）= ADMITTED_FOR_DESIGN_ONLY**（Human Gate 2026-08-15；非 H2 FINAL ACCEPTANCE；H2 实现 NOT YET AUTHORIZED）：
  - **H2 admission opportunity evidence = PASS**（reviewer `H2_ADMISSION_EVIDENCE_L3_REVIEWER` v2，session `2cea14f5-4d6b-491d-b845-795b47cfccc2`，runtime 机械验证 deepseek-official/deepseek-v4-pro/high，PASS/HIGH/evidence_integrity=HIGH；advisory：density=MODERATE、recommendation=ADMIT_FOR_DESIGN；v1 FAIL 历史保留）。
  - **机会密度统计（仅 density，非性能声明）**：NO_PM（G3 tuning 20 批）legal dispatch ≈413.1/批、**strategic wait strict ≈11.4/批（~2.8%）**、**optional PM feasible ≈168.8/批（~41%）**、both ≈4.5/批、**meaningful H2 choice fraction ≈0.429**、零机会批次比例 0%（strategic/PM/meaningful 均 0%）。holdout 全 100 批上下文一致。
  - **旧 C24 `waiting_opportunity_count` 审计结论**：其测量的是 **forced wait / 当前非法性**（head 不能合法启动），**不是 H2 战略等待密度**；与离线 strategic wait 相比约**高一个数量级**（150/批 vs 11.4/批），**不得复用为 H2 strategic-wait 计数**。未来 H2 admission/validation 必须使用修正定义（strategic wait 分 STRICT/BOUNDARY/NONSTRICT；optional PM 与 mandatory 分离）。
  - **C24 状态拆分**：opportunity-density evidence = **PASS**；budget/spec freeze = **PENDING**（不标记 full C24 PASS）。
  - **C23 = PENDING / NOT YET EXECUTED**；**C25 = PENDING / NOT YET EXECUTED**。
  - 证据来源分离：仅 G3 tuning `01b7c7e7` + holdout `020bc637`（确定性重放重建 accepted 日志、hash 逐批匹配）；**q2_formal design leakage = NONE**；无新随机模拟。
  - 证据文件：`01_审计/H2_ADMISSION_C24_EVIDENCE_DRAFT.md`、`01_审计/H2_ADMISSION_EVIDENCE_L3_REVIEW_RECORD.md`；工具：`04_代码/checker/h2_admission_opportunity_analyzer_v1.py`（独立、stdlib-only、无 main DES import）、`04_代码/scripts/run_h2_admission_evidence_v1.py`（纯 orchestration/reporting wrapper，RUNNER_GOVERNANCE_DEVIATION=CLOSED_BY_HUMAN_GATE_CONDITIONAL_AUTHORIZATION）、`04_代码/tests/test_h2_admission_opportunity_analyzer_v1.py`。
  - **证据支持 ADMIT_FOR_DESIGN，不证明**：H2 改善 T、H2 最优、H2 应进最终论文、任何 rollout M、任何 Q3 K。

- **`Q3/H2 BOOTSTRAP`（advanced scheduling design freeze）= FINAL PASS / ACCEPTED**（Human Gate 2026-08-15 VERIFIED FINAL PASS / DESIGN FREEZE APPROVED；已直接审阅最终 623 行版本）：
  - **冻结权威规格**：`08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT.md`（状态 **FINAL_FREEZE_ACCEPTED / HUMAN_GATE_PASS**）；§19 **D-01..D-25 全部冻结，不得重开**。
  - 冻结内容（摘要）：rollout M 网格 `{(4,8),(8,6),(8,8)}` + 成本导向选择（`w_p≤90 s`）；`C_rollout=200`；`C_eval*∈{6,8}` 的**在线因果配额**（`W_cap=⌈C_eval*/2⌉`、`P_cap=⌊C_eval*/2⌋`；6→3+3、8→4+4；no cross-side borrowing / no backfill / no future candidate count / no retroactive selection）；soft 4h / hard 8h + H2 开发预算账本；动作集 `A0/A0b/A1/A2a/A2b` + DISPATCH/MAINTENANCE 两类决策点 + dp ordering（A/B/C/E）；后验/寿命两层验证（deterministic primary + stochastic smoke）；跨 K transfer = 预注册诊断/早期预警（正式收益门 = C25）；C25 保留规则（≥5/7 K 族调整 CI<0、0 显著恶化、稳定、预算、无 C23 违例——Human Gate 预注册政策阈值）。
  - **BOUNDARY 契约同步（D-11/D-25 批准）**：`e == latest_start` 为合法 WAIT；`01_审计/问题契约.md` §1.3.2/§7.5、`03_模型/高级模型技术补充_V3.1.md` §5.3、`03_模型/03_H2后验Rollout候选.md` §5 已同步为「**早于或等于最迟启动时刻**」；`now + duration ≤ shift_end`（恰班末完成合法）保持。
  - **CR-V3.1/C24 = PASS**（opportunity-density evidence = PASS；budget/spec freeze = PASS——两子项均闭合）。
  - **H2 = NOT IMPLEMENTED**（设计冻结 ≠ 实现授权）；**C23 = PENDING / NOT YET EXECUTED**；**C25 = PENDING / NOT YET EXECUTED**；**Q3 formal = NOT STARTED；不存在任何 Q3 K 推荐**。
  - **下一阶段**：**Q3/H2 IMPLEMENTATION BOOTSTRAP + C23 实现与检查**——须由 Human Gate **另发执行授权**方可开始；未授权前不实现 H2、不运行 Q3 七 K / H2 管线实验。
  - Provenance：审计链中无 session request/header 机械证据处 reasoningEffort = **UNVERIFIED**（如实记录）；tuning/诊断值（机会密度、M 校准、稳定性样本、跨 K transfer 诊断）**非论文正式数字**。

（历史记录：G2 完成前的 7 项实施目标——单次无条件/标准链观测核、Q1 闭式与吸收链、最小并行 DES、1—4 台对拍与 K=9 跨班、最小 checker 与故障注入、G2 适用检查——均已随 G2/G3 PASS 完成并验收，不再作为当前出口条件。）

## 6. 当前禁止

- **不实现 H2 rollout**；不选 rollout M；不运行 H2 政策实验；不消耗新随机世界；不比 H1 vs H2；
- 不枚举 K、不推荐 K；不启动 Q3 七 K 模拟；不启动 Q4；
- 不把失败 run `daead4cf` 或 G3 调优/holdout 数据（含 tau_pm=198 候选的调优 mean T）当作 Q2 论文数字来源；论文数字只来自 accepted run `2d1466ba`；
- 不手录数字为权威；手稿数值必须机械可追溯至 accepted formal 证据；
- 不宣称 tau_pm=198 最优（= FORMALLY_NOT_SELECTED_FOR_Q2_PRIMARY）；不把 C3（不可区分）转为 tau198 优越证据；不因 H2 admission 重开 Q2 或宣称 Q2 H1 次优；
- 不宣称 NO_PM 超越冻结模型/候选集范围的普适最优或一般工业管理定理；
- **不把旧 C24 `waiting_opportunity_count` 当作 H2 战略等待密度**（= forced-wait 仪表）；未来 H2 使用修正定义（strategic STRICT/BOUNDARY/NONSTRICT + optional PM 与 mandatory 分离）；
- 不改 G3/Q2 accepted 核心（random_des_v1/key_schema_v1/寿命再生/C06/C17/冻结观测语义/Q2-FORMAL-SPEC）；若需改 → STOP 回 Human Gate；
- 不修改已签字口径与 accepted 证据；若实现暴露新歧义，回到变更控制而不是自行决定；
- **不实现 H2**（Q3/H2 BOOTSTRAP 设计已冻结但实现未授权；P0 key schema 已 accepted 且 P0 已关闭）；**Q3 H1 七 K 正式基线（Tier 1 + Tier 2）为当前授权执行包**；**不运行 H2 tuning / holdout / formal 实验、不运行 density recheck、不运行 Tier 3**；**不推荐 Q3 K**（K 推荐须等 Human Gate H1 formal review）；
- **不重开 D-01..D-25**、不修改冻结的 `Q3_H2_BOOTSTRAP_SPEC_DRAFT.md` 规范条款（如需 → STOP 回 Human Gate）；
- **不把 tuning/诊断值**（机会密度、M 校准、稳定性样本、跨 K transfer 诊断）**当论文正式数字**；
- **不宣称 H2 已实现 / C23 PASS / C25 PASS / Q3 已启动**（均未发生）；Q3/H2 实施阶段须 Human Gate 另发执行授权。

## 7. 下一出口

G2/G3/Q2 H1 FORMAL 均已 PASS/ACCEPTED；**Q3/H2 BOOTSTRAP = FINAL PASS / ACCEPTED（D-01..D-25 冻结；冻结权威规格 = `08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT.md`）**；**P0（H2 key schema bootstrap）= VERIFIED FINAL PASS / ACCEPTED（已关闭）**；C24 = PASS；H2 = NOT IMPLEMENTED；C23 / C25 = PENDING；**Q3 = ACTIVE（Q3 H1 七 K 正式基线执行中/待 Human Gate review；无 K 推荐）**。**下一阶段路线（Human Gate 最新决策）**：**① Q3 H1 七 K 正式基线（Tier 1 + Tier 2）→ ② Human Gate H1 formal review → ③ 基于 accepted Tier 1 日志的确定性只读 Q3 七 K H2 opportunity-density recheck（Density FAIL → DELETE H2、Q3 H1-only；Density PASS → 才允许 Human Gate 授权 P1）**。**P1 / C23 / rollout / posterior 当前仍 NOT AUTHORIZED**；Density recheck 不包含在当前 Q3 H1 formal 执行包中。Q2 论文数字 = AVAILABLE / AUTHORITATIVE（accepted run `2d1466ba`）。

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
