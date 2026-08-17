# CURRENT_STATE

> 最后更新：2026-08-17
> 状态版本：`STATE-2026-08-17-Q4-FINAL-CLOSED`（HG-Q4-FINAL-SEAL-01 密封后更新；前版 `STATE-2026-08-17-Q4-READY-FOR-PAPER` 已废弃）
> 当前 Gate：**Q3 FINAL MODEL SELECTION CLOSED（Whole G2 = PASS / ACCEPTED；G3 = PASS / ACCEPTED；Q2 = FINAL PASS / ACCEPTED（`2d1466ba`）；Q3 正式主策略 = H1；Q3 推荐 K = K12（12 h），仅限七个 K + 冻结 H1 policy set（NO_PM_BEFORE_MANDATORY），非全局最优、不宣称弱支配；Q3-H2 = FINAL DELETE / ACCEPTED AS CHALLENGER RESULT（evidence `7b490ce6`；H2 = FROZEN_HISTORICAL_CHALLENGER；H2' = NOT PLANNED；cross-K / h2_holdout / C25 = NOT_APPLICABLE_AFTER_H2_DELETE、historically NOT RUN）；Q3 FINAL STATUS = READY_FOR_PAPER）**；**Q4 PHASE 1A（FAST SCREENING）= FINAL PASS / ACCEPTED**（evidence `05_结果/Q4/screening/phase_1a/20260817T060454057035Z_c516bd6c/`）；**Q4 NUMERIC RESULTS = FINAL PASS / ACCEPTED（HG-Q4-NUMERIC-01，accepted HEAD `8096d80`）**——Q4 FORMAL FACTOR RANK = ACCEPTED、Q4 INTERACTION NUMERICS = ACCEPTED；**Q4 FINAL SEMANTIC REVIEW = PASS / CLOSED（HG-Q4-REVIEWER-01：reviewer = GPT-5.6 Sol，verdict = PASS_WITH_CAVEAT；DeepSeek Pro-Max final review = SUPERSEDED / NOT REQUIRED——Human Gate 授权 reviewer 替换，未伪造 Pro-Max runtime receipt）**——RA-S1（条件边际 direct paired CI：cond E−10 = −3.5648 h，95% CI [−4.027, −3.103]；cond E+10 = +91.3330 h，95% CI [90.225, 92.441]，t_{0.975,127}=1.9793，**独立于 interaction-contrast CI、不得混用**）、RA-S2（Q-A 措辞）、RA-S3（scope hardening：robust 组合措辞 / Q-B·e joint proportional scale / factor-table scope）全 PASS；**Q4 FINAL STATUS = READY_FOR_PAPER；G7 = AUTHORIZED_FOR_PAPER_FREEZE**；paper-facing 包 `05_结果/Q4/final_handoff/`；**Q4 new simulations = NOT REQUIRED；Q4 evaluation rerun = NOT REQUIRED；Pro-Max calls = 0**；**Q4 FINAL SEAL = HG-Q4-FINAL-SEAL-01（AUTHORIZED_BY_HUMAN_GATE）——Q4 = FINAL CLOSED / IMMUTABLE / READY_FOR_PAPER；sealed head `a94bcd0`；final closure root `05_结果/Q4/final_closure/`（receipt / hash manifest / authority map / reopen policy / audit）；任何实质变更须 HUMAN_GATE_REOPEN_Q4**。下一阶段：**G7 PAPER FREEZE（已授权；不得自动开始，等待 Human Gate）**。F3 措辞红线：禁止「PM 干预无益 / 已证明不能改善 / 提前更换一定更差」；正式措辞 = 三个预注册阈值（{150,180,210} h）均未观察到缩短总完成时间的证据（tau150 不明确；tau180/210 小幅延长），**不得推广为所有 preventive replacement 策略必然无效**；Q3 正式策略 H1、K\*=K12 UNCHANGED。历史链：G2 = PASS / ACCEPTED；G3 = PASS / ACCEPTED（C17 REQUALIFIED_AFTER_C10_C12_CHECKER_FIXES）；Q2 H1 FORMAL = PASS / ACCEPTED（accepted run `2d1466ba`；Q2 主情景选中 H1 政策 = NO_PM_BEFORE_MANDATORY）；Q3/H2 BOOTSTRAP = FINAL PASS / ACCEPTED（D-01..D-25 冻结；冻结权威规格 `08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT.md` = FINAL_FREEZE_ACCEPTED + ADDENDUM DP_DIAG_01）；P0 = VERIFIED FINAL PASS / ACCEPTED（已关闭）；Q3 H1 FORMAL = FINAL PASS / ACCEPTED（accepted physical run `run_20260815T133840057668Z_7ee48fc0`；accepted final provenance reissue `05_结果/Q3/formal/reissue_20260815T150613626910Z_f4da8f9d`；Tier 1/2 预注册报告 k\*=K12 strong、co-best=[]——**措辞限于「七个 K + 冻结 H1 政策集内」，非全局最优、非 K12 弱支配、非 final Q3 overall recommendation**）；Q3-H2 Density = FINAL PASS / ACCEPTED（D-14 A 7/7 + B 7/7；E1 `a2669aa9` + E2 `0713f171`）；Q3-H2-P1/P2/P3-A/P3-B（含 E1 各轮）= FINAL PASS / ACCEPTED（`08488e4` / `31f13f9`+`a5d2faf` / `b285131`+`fcf07f6` / `841bafc`→`10a6491`→`c271a62`）；**Q3-H2 = FINAL DELETE / ACCEPTED（Human Gate 2026-08-17；accepted evidence `05_结果/H2/tuning/stability/run_20260816T175317829317Z_7b490ce6`：n=100、agreement_b=1.0000、agreement_c=1.0000、deviation_count=0 → H2_NO_EFFECTIVE_DEVIATION；governance closure `a56a2cd`；H2 = FROZEN_HISTORICAL_CHALLENGER；H2' = NOT PLANNED；cross-K / h2_holdout / C25 = NOT_APPLICABLE_AFTER_H2_DELETE（historically NOT RUN，非 PASS 非 FAILED））**；C23/C25 按 H2 DELETE 不再需要（historically PENDING → NOT_APPLICABLE_AFTER_H2_DELETE）；**Q3 论文包 = ACCEPTED（`05_结果/Q3/final_closure/`：Q3_FINAL_RESULT / Q3_H1_H2_COMPARISON / Q3_H1_H2_PAPER_TABLE / Q3_H1_H2_PAPER_NARRATIVE + provenance/scope audit；fresh Pro-Max 论文语义审查 PASS_WITH_CAVEAT、authority_conflict=false、actions closed）**。
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
  - （历史状态快照，Q2 激活前）：H1/Q2 formal evaluation = NOT STARTED；H2 = NOT STARTED / NOT AUTHORIZED；Q3 FORMAL = NOT STARTED；Q4 = NOT STARTED。→ **Q2 H1 FORMAL 已由 Human Gate 2026-08-15 授权激活（见下 Q2 段）**。
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

- **（历史，Q3/H2 早期阶段）`H2 ADMISSION`（opportunity evidence audit）= ADMITTED_FOR_DESIGN_ONLY**（Human Gate 2026-08-15；非 H2 FINAL ACCEPTANCE；H2 实现 NOT YET AUTHORIZED；**当前状态 = Q3-H2 FINAL DELETE / ACCEPTED，见顶部**）：
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

## 5.1 Q3-H2 实施链（P0 → P2 → P3-A，Human Gate 逐包裁决）

- **路由治理（独立于建模任务）**：**MATHEMATICAL_MODELING_ROUTER_V2.1.2 = HUMAN_ACCEPTED（2026-08-16；Reviewer Verdict PASS；Ending commit `193d3722579a60307ad1969502d4e66d1a67e1c1`；READY_FOR_GENERAL_MATHEMATICAL_MODELING_AUTOPILOT）**——通用数学建模路由权威（V2.1/V2.1.1 历史 superseded；Phase-A PRO-MAX ROUTING V1.0 ACCEPTED 不变）。该治理验收不改变任何建模阶段状态；Q3/H2 工作保持 STOP。

- **P0（H2 key schema bootstrap）= VERIFIED FINAL PASS / ACCEPTED**（Human Gate；P0 关闭；`g3/key_schema_v1.py` 六命名空间 + `h2_future` reserved）。
- **Q3-H2 Density = FINAL PASS / ACCEPTED**（D-14 A 7/7 + B 7/7；E1 时间因果重建 `a2669aa9`；E2 fragment-aware checker `0713f171`；Density 历史 `4a867e83` immutable）。
- **Q3-H2-P1（信息防火墙 + C23 P1-applicable）= FINAL PASS / ACCEPTED**（Human Gate 2026-08-16；P1 `db2e894` + P1-E1 `3568010` + P1-E2 `08488e4`；ObservableState/PosteriorState 白名单接口；h2 包零 g3/des import）。
- **P2 + P2-E1 = FINAL PASS / ACCEPTED**（Human Gate 2026-08-16；original P2 `31f13f9`（PRIMARY 数学有效，旧 smoke superseded）+ P2-E1 `a5d2faf`（random-domain/budget requalification）；后验 §8 + 条件寿命 §9 生成器 + 独立 deterministic checker + 冻结 secondary smoke；证据 `05_结果/H2/p2/requalification/run_20260816T054219773348Z_14a587d7`）。
- **Q3-H2-P3-A + P3-A-E1 = FINAL PASS / ACCEPTED（Human Gate 2026-08-16；accepted lineage：P3-A original `b285131` + P3-A-E1 closure `fcf07f6`；C23 mechanics/continuation = PASS；C23 full production = PENDING）**：决策点两类（dispatch / maintenance）+ canonical A/B/C/E ordering + dp 0-based 纯函数；五动作续演语义（START_HEAD / H1_NOOP / WAIT_EVENT STRICT|BOUNDARY / PM_WITH_HEAD / PM_IDLE；mandatory/exact_240 永非 policy choice）；rollout_seed(dp,m) 公式 + CRN（seed 不含 action/policy/run_id）+ **P3-A-E1 rollout post-key adapter**（h2_rollout namespace；同 (dp,m,entity) 跨动作 exact identical；dp/m 分离；不用 P2 synthetic mapping）；continuation world 重建（仅 ObservableState + PosteriorState + rollout post keys，严禁 deepcopy live world / 读隐藏字段）；P3-A-E1（Human Gate narrow repair）：F1 活动 fragment WAIT 锚、F2 WaitAnchor 真实 in-flight 事件身份、F3 per-device U_X_post/U_D_post + reached-E D posterior（fail-close）、F4 PM age_before = 设备 age_h；独立 checker 15/15 + tests 45/45 + regressions 28/36/38/23/44；证据 `05_结果/H2/p3/mechanics/requalification/run_20260816T063153810486Z_1b405934`。
- **Q3-H2-P3-B + P3-B-E1 = FINAL PASS / ACCEPTED（Human Gate 2026-08-16 PASS WITH CAVEAT / ACCEPTED；accepted lineage：`841bafc` → `10a6491` → `c271a62`；accepted evidence `05_结果/H2/tuning/cost_calibration/requalification/run_20260816T074652976919Z_60a958e8`；冻结配置 **M\* = 8、C_eval\* = 8、W_cap\* = 4、P_cap\* = 4**）**：完整 rollout 执行核 + current-generation residual lifetime 坐标修复**：fresh continuation rollout engine（首动作后 H1 回退至吸收；future D 在合法联接点按 prior q_D 物化一次；U_Y_post 仅有效完成消费；新代 U_L_post）；**P3-B-E1 F1：current-generation residual lifetime（P2 返回 residual tau）统一为绝对故障年龄坐标（lifetime_h = current_age + tau；right-censored → 240；P2 conditional_residual_frozen API 不变）**；H1 fallback parity 6 场景 + **P3-B-E1 独立 frozen oracle 非零 age 故障时序（age=150、residual=3/2 → 绝对故障 151.5、fragment 中途故障、requeue、replacement）**；Q_hat_M + 配对 D_m/SE_M；online quota selector（C_eval 6/8）；C_rollout=200 硬上限；独立 checker 16/16 + tests 26/26 + regressions 28/36/38/23/44；**成本 requalification（selection domain = h2_tuning rep 0..4、K=10.5；base_runtime = development_unit PERFORMANCE_ONLY_BASE_SURROGATE；c_r = h2 continuation engine）→ 三候选全可行（(4,8)=5.75s、(8,6)=8.48s、(8,8)=11.20s ≤90s），按冻结规则选 (M*,C_eval*)=(8,8)、W_cap*=4、P_cap*=4 → PROVISIONAL RECONFIRMED / AWAITING HUMAN GATE FINAL FREEZE**；C23 rollout path = PASS（full final policy C23 PENDING）；证据 `05_结果/H2/tuning/cost_calibration/requalification/run_20260816T074652976919Z_60a958e8`（RESULT 数字由 final evidence 机械生成，RESULT_SOURCE_RUN_ID 断言；原 P3-B root `45e12558` 标记 HISTORICAL_P3_B_EXECUTION_WITH_CURRENT_GENERATION_RESIDUAL_LIFETIME_COORDINATE_BUG）。**action stability / cross-K transfer / h2_holdout / C25 仍 NOT AUTHORIZED**。
- **Q3-H2 = FINAL DELETE / ACCEPTED（Human Gate 最终裁决 2026-08-17；Q3 FINAL CLOSURE）**：accepted final evidence = `05_结果/H2/tuning/stability/run_20260816T175317829317Z_7b490ce6`（n=100、agreement_b=1.0000、agreement_c=1.0000、deviation_count=0 → **H2_NO_EFFECTIVE_DEVIATION → DELETE**）；governance closure = `a56a2cd`（FINAL NARROW Pro-Max 真实 session identity receipt：child `2174b107…`、deepseek-pro-max/deepseek-v4-pro/max、read-only 62/62、delta=0）；**H2' = NOT PLANNED；H2 substantive implementation = FROZEN_HISTORICAL_CHALLENGER**（高级候选/对照模型，不再修改：禁改 action set/2SE/M\*/C_eval\*/B-1/seed/salt、禁加 tuning sample、禁重跑 P3-C、禁设计 H2'、禁 cross-K/holdout/C25、禁为论文制造 deviation）；**cross-K transfer / h2_holdout / C25 = NOT_APPLICABLE_AFTER_H2_DELETE（historically NOT RUN，非 PASS 非 FAILED）**；**Q3 正式主策略 = H1**（七 K accepted formal chain；k\*=K12 为「七个 K + 冻结 H1 政策集（NO_PM_BEFORE_MANDATORY）」范围内的 strong winner，**非全局最优、不宣称弱支配**）；**Q3 FINAL MODEL SELECTION CLOSED；Q3 FINAL STATUS = READY_FOR_PAPER**；H1/H2 对比与论文叙事包 = `05_结果/Q3/final_closure/`（Q3_FINAL_RESULT / Q3_H1_H2_COMPARISON / Q3_H1_H2_PAPER_TABLE / Q3_H1_H2_PAPER_NARRATIVE + provenance/scope audit）。
- **（历史，第二轮）Q3-H2-P3 第二次语义重新认证（e4fd435 的 H2 DELETE 暂不接受；撤销「quota-evaluated = B-1 population」解释；HG-Q3-H2-DP-DIAG-01 + MODEL_ROUTING_MISS-001）**：B-1 恢复 ALL-eligible + dp_diag；posterior world_m；AGE-LEGAL/PENDING-01..04；bay-occupancy 修复；成本 (8,8) 冻结恢复；Pro-Max 第二轮 PASS_WITH_CAVEAT（A–H 全 YES）；第二轮 P3-C 重跑 root `run_20260816T170310179282Z_ea3354ba` = **H2_DELETE（该轮结论由本 FINAL NARROW 轮接管，root 数字保留）**；cross-K transfer / h2_holdout / C25 保持 NOT AUTHORIZED。
- **（历史，第一轮）Q3-H2-P3-C 决策语义重新认证（MMR V2.1.2 YELLOW；Human Gate BLOCKER A–D；其「quota-evaluated = B-1 population」解释已被第二次裁决撤销）**：旧 P3-C root `791506d8` = INVALIDATED_FOR_DECISION_SEMANTICS；P3-A/P3-B 修复 + first-action fail-closed + release-guard + 两轮 Pro-Max PASS_WITH_CAVEAT；第一轮 P3-C 重跑 root `4f60db0d` = **INVALIDATED_FOR_FROZEN_SAMPLE_AND_ROLLOUT_WORLD_SEMANTICS**（数字不改，不再作为决策证据）；cross-K transfer / h2_holdout / C25 保持 NOT AUTHORIZED。

## 5.2 Q4 / G6（正式 sensitivity 实验链）——Phase 1A FINAL + Phase 1B/FORMAL 执行包 ACTIVE

- **Q4 设计权威**：`08_项目管理/任务包/Q4_G6_EXPERIMENT_SPEC_DRAFT.md`（SCREENING_SPEC_FROZEN / PRE-DATA / HUMAN_GATE_AUTHORIZED）；addendums：`Q4_H2_NA_01_ADDENDUM.md`（H2 = NOT_APPLICABLE_AFTER_H2_DELETE）、`Q4_F3_01_ADDENDUM.md`（F3 = AUTHORIZED_AS_HYPOTHETICAL_COUNTERFACTUAL_SENSITIVITY，RA1 = OPTION B）。
- **随机域（HG-Q4-NS-01 additive 扩展后）**：legacy 六域 + `q4_screening` / `q4_evaluation`（`PHYSICAL_EXPERIMENT_NAMESPACES`）；H2 三域只进 post streams；master_seed 7（Q4 专用）。**隔离硬约束：screening（rep 0..39）与 evaluation（rep 100..163 / 164..227）完全不重叠；Q4_EVALUATION 是正式 CI 唯一证据源；禁止 pooling。**
- **Phase 1A FAST SCREENING = FINAL PASS / ACCEPTED**（evidence `05_结果/Q4/screening/phase_1a/20260817T060454057035Z_c516bd6c/`；R=20、rep 0..19、13 scenarios + baseline；paired DeltaT / SE / 95% screening CI（t_{0.975,19}=2.093）/ standardized effect / sign consistency；checks：only-one-factor-diff / CRN / evaluation-firewall / authorized-core-delta）。
  - **screening 数学效应排序（std effect）**：F2 turnover 0.5h **-9.58**（dT=-75.35h）> F4-E -10% **-5.37**（dT=-35.49h）> F4-C +10% **+3.60**（+15.9h）> F4-E +10% **+2.58**（+17.97h）> F4-A +10% **+2.25**（+13.65h）> F3 tau150/180/210（+0.41/+0.29/+0.26，CI 均跨 0，COUNTERFACTUAL_ONLY）> F4-C -10% -0.24 / F4-B ±0.22 / F5 +0.22（MODEL_SEMANTIC_ONLY）。
  - **candidate Top-2 = F2 + F4-E**（Human Gate 已冻结正式 interaction = **F2 turnover × F4-E duration**，2×3 设计）。
  - **F3 措辞红线（Human Gate 纠正，本包落文修正）**：screening 结果不得写成「PM 干预无益 / 已证明不能改善 / 提前更换一定更差」；只可「**未观察到明确改善；点估计为正但 CI 跨 0；正式结论待独立 Q4_EVALUATION**」。
- **本包执行结果（EXECUTED / Q4_NUMERIC_RESULTS_READY_FOR_HUMAN_GATE；Pro-Max calls = 0）**：
  - **Phase 1B q/e screening**（q4_screening/seed 7/rep 20..39；evidence `05_结果/Q4/screening/phase_1b/20260817T063533732938Z_b520fc8e/`）：QB_LOW −4.55 h（CI [−7.73, −1.37]）、QB_HIGH +3.90 h（CI [0.84, 6.96]）、QA_LOW −3.95 h（CI [−7.16, −0.74]）、E_LOW −1.275 h、E_HIGH +0.90 h、QA_HIGH +0.625 h（screening CI，t_{0.975,19}）；机制 = E 重测链 + 班外停工。
  - **合并 screening factor rank**（`05_结果/Q4/screening/merged/`）：F2 −9.58 > F4-E −5.37 > F4-C +3.60 > F4-A +2.25 > Q-B −0.67 > Q-A −0.58 > F3 +0.41 > E −0.29 > F4-B ±0.22 > F5 +0.22；**candidate Top-2 = F2 + F4-E（Human Gate 已冻结 interaction）**。
  - **Q4 FORMAL EVALUATION**（q4_evaluation/seed 7；**R=128 / rep 100..227**；two-stage 扩样已触发——stage-1 max half-width 2.0930 h > 2.0 h → 全 scenarios 统一扩 R=128；target 2.0 h 达成，final max half-width ≈ 1.37 h；evidence `05_结果/Q4/evaluation/20260817T065336055564Z_b46f9219/`；Q4_EVALUATION_REGISTRY = PRE-DATA / IMMUTABLE；checks 全 PASS：only-one-factor-diff / CRN / screening-firewall（0 keys）/ domain-isolation（100..227 与 0..39 不重叠）/ core hashes）：
    - **正式主 scenarios（paired ΔT vs baseline，95% CI）**：F2 −73.89 h [−75.10, −72.69]（ALL_NEG）；F4-E M10 −34.07 h [−35.04, −33.10]（ALL_NEG）；F4-E P10 +18.16 h [17.11, 19.22]（ALL_POS）；F4-A P10 +15.06 h [14.12, 16.01]；F4-C P10 +13.52 h [12.44, 14.60]；Q-B HIGH +3.52 h [2.69, 4.35] / LOW −2.37 h [−3.03, −1.70]；E LOW −2.66 h [−3.56, −1.76] / HIGH +2.20 h [1.28, 3.12]；Q-A HIGH +1.58 h [0.63, 2.54] / LOW −1.19 h [−2.16, −0.23]；F3 tau150 +0.30 h [−0.11, 0.71]（跨 0）/ tau180 +0.59 h [0.10, 1.07] / tau210 +0.66 h [0.21, 1.10]（COUNTERFACTUAL_ONLY）；F5 −0.02 h [−0.16, 0.12]（MODEL_SEMANTIC_ONLY）。
    - **正式 factor rank（factor_score = max |std|）**：F2 −10.74 > F4-E −6.13 > F4-A +2.79 > F4-C +2.19 > Q-B +0.74 > E −0.52 > F4-B +0.35 > Q-A +0.29 > F3 +0.26 > F5 −0.03。
    - **Top-2 interaction（F2×F4-E，2×3）**：INT_M10 −77.46 h、INT_P10 +17.44 h；**I_minus = +30.50 h（CI [29.45, 31.55]）、I_plus = +73.17 h（CI [71.80, 74.54]）均排除 0 → 模型内强非加性交互，且方向非对称（HG-Q4-NUMERIC-01 修正解释）**：E−10% 在 fast-turnover 下条件边际 ≈ **−3.57 h**（收益显著递减）；E+10% 在 fast-turnover 下条件边际 ≈ **+91.33 h**（惩罚显著放大）；联合措施不可简单相加；禁现实因果。
    - **F3 正式结论（红线措辞）**：未观察到 preventive replacement 缩短完成时间的明确改善（点估计 +0.30~+0.66 h；tau150 CI 跨 0；tau180/210 不含 0 但 <1.1 h）；COUNTERFACTUAL_ONLY，不构成对 H1/NO_PM 政策的变更建议（Q3 正式策略 = H1、K\*=K12 UNCHANGED）。
    - 机制解释见 `MECHANISM_EXPLANATION.md`；管理建议草案见 `MANAGEMENT_RECOMMENDATION_DRAFT.md`（DRAFT_FOR_HUMAN_GATE；数学影响排序 ≠ 管理实施优先级）。
  - **本包输出 FINAL STATUS = Q4_NUMERIC_RESULTS_READY_FOR_HUMAN_GATE**；**完成后 STOP**（不自动进入 G7 final paper freeze、不写 final paper claim、不改 Q3；final 论文语义审查留待 Human Gate 后低价时段另行 Pro-Max 执行）。
  - **HG-Q4-NUMERIC-01（Human Gate 裁决，accepted HEAD `8096d80`）已落地**：**Q4 NUMERIC RESULTS = FINAL PASS / ACCEPTED**（Q4 FORMAL FACTOR RANK = ACCEPTED；Q4 INTERACTION NUMERICS = ACCEPTED；NO NEW SIMULATION / NO RERUN / NO Q3 CHANGE）。
    - **interaction 解释修正（关键）**：旧表述「turnover 0.5h 后 E 时长 ±10% 的边际影响都大幅萎缩 / E_P10 惩罚被中和」**已删除**；冻结解释 = **方向非对称**：E−10% 在 fast-turnover 下条件边际 ≈ **−3.57 h**（STRONG DIMINISHING BENEFIT）、E+10% ≈ **+91.33 h**（STRONG AMPLIFICATION OF PENALTY）；`I_minus = cond_M10 − standalone_M10 = +30.50 h`、`I_plus = cond_P10 − standalone_P10 = +73.17 h`（机械验证 PASS）。
    - **管理建议修正**：R1 不把「0.5h complete overlap」等价成未经冻结的工程方案（改「若现实中运出/运入充分重叠…具体工程方案需评估」）；R2 增加条件边际 −3.57 h；**新增 INTERACTION WARNING：fast-turnover 下 E 工序时长 +10% → 相对 fast-turnover 状态 +91.33 h，快周转对 E 工序恶化更敏感，须避免 E 能力退化**（MODEL-INTERNAL）。
    - **F3 措辞（HG 批准）**：三个预注册阈值 {150,180,210} h 均未观察到缩短总完成时间的证据（tau150 不明确；tau180/210 小幅延长）；**不得推广为所有 preventive replacement 策略必然无效**；Q3 正式策略 H1、K\*=K12 UNCHANGED。
    - **F5 措辞（HG 批准窄表述）**：仅「分段线性 vs 常风险率」两种语义比较下差异很小、未观察到明确影响；**不宣称对所有可能寿命分布普遍鲁棒**（无 equivalence margin，不做等价声明）。
    - **factor-rank 呈现**：表头用「rank by |standardized effect|」，方向符号另列；e 因子显示名 = operator-error environment（测手差错环境 e），避免与工序 E 混淆。
    - **paper-facing 包**：`05_结果/Q4/final_handoff/`（Q4_FINAL_NUMERIC_RESULT / FACTOR_TABLE / INTERACTION_TABLE / MECHANISM_NARRATIVE / MANAGEMENT_RECOMMENDATIONS / PROVENANCE / SCOPE_AUDIT）＝ **NUMERIC_ACCEPTED / SEMANTIC_REVIEW_PENDING（NOT READY_FOR_PAPER）**。
    - **FINAL STATUS = Q4_NUMERIC_ACCEPTED_WAITING_FINAL_SEMANTIC_REVIEW**；**G7 = NOT AUTHORIZED YET**；下一阶段 = Q4 FINAL PAPER SEMANTIC REVIEW（低价时段 fresh Pro-Max，本阶段 0 次调用）→ Human Gate → G7 PAPER FREEZE。
  - **HG-Q4-REVIEWER-01（final semantic closure，reviewer = GPT-5.6 Sol，verdict = PASS_WITH_CAVEAT）已落地**：**Q4 FINAL SEMANTIC REVIEW = PASS / CLOSED；Q4 FINAL STATUS = READY_FOR_PAPER；G7 = AUTHORIZED_FOR_PAPER_FREEZE**。
    - **RA-S1（条件边际 direct paired CI，PASS）**：从 accepted `T_by_rep.json` 逐 rep 计算 `T(INT) − T(F2)`（R=128，rep 100..227，t_{0.975,127}=1.9793）：cond E−10 = **−3.5648 h**（SE 0.2336，95% CI [−4.027, −3.103]，half-width 0.462）；cond E+10 = **+91.3330 h**（SE 0.5599，95% CI [90.225, 92.441]，half-width 1.108）；mean 与 accepted exact 值一致；**conditional-margin CI 与 I_minus/I_plus interaction-contrast CI 语义不同，不得混用**（已写入 Q4_FINAL_INTERACTION_TABLE / Q4_FINAL_MANAGEMENT_RECOMMENDATIONS / Q4_FINAL_PROVENANCE）。
    - **RA-S2（Q-A 措辞，PASS）**：删除「重标定核被证明抵消 q 变化」断言；冻结表述 = 「在本次联合重标定链下，Q-A 的工期响应小于 Q-B；这一结果与观测核随 q 重标定产生补偿作用的解释相一致，但本实验未单独识别各传播通道的独立贡献」。
    - **RA-S3（scope hardening，PASS）**：A「快周转 + E 能力保持是稳健组合」→「在本次已测试模型情景内，实施快周转时同步维持 E 工序节拍是更稳妥的组合」（禁 universal robustness）；B Q-B 明确 = q_A/q_B/q_C/q_D joint proportional scale 0.8/1.2（非单独一个 q）；C e 明确 = e_A/e_B/e_C/e_E joint proportional scale 0.8/1.2（非单独一个测手参数）；D factor table 加 scope「本排序仅在本次预注册 factor levels / perturbation range 内成立，不是因素全参数域的全局敏感度排序」。
    - **reviewer governance**：HG-Q4-REVIEWER-01；DeepSeek Pro-Max final review = **SUPERSEDED / NOT REQUIRED**（Human Gate 授权 reviewer 替换；**未伪造 Pro-Max runtime receipt**）；本阶段 Pro-Max calls = 0。
    - 机械 closure checker 全 PASS（accepted numerics / T_by_rep / ledger_by_rep / registry 未改；Q3 / H1 / K12 / H2 未改；new simulations = 0）。
  - **HG-Q4-FINAL-SEAL-01（FINAL SEAL / FINAL CLOSURE，AUTHORIZED_BY_HUMAN_GATE；sealed head `a94bcd0`）已落地**：**Q4 = FINAL CLOSED / IMMUTABLE / READY_FOR_PAPER**；**G7 = AUTHORIZED_FOR_PAPER_FREEZE**。
    - **final closure root** `05_结果/Q4/final_closure/`（6 件）：`Q4_FINAL_CLOSURE_RECEIPT.json/.md`（closure_id=HG-Q4-FINAL-SEAL-01；formal numeric root + paper-facing root + formal design q4_evaluation/seed7/R=128/rep 100..227/two-stage 2.0930→2.0→R=128；semantic review HG-Q4-REVIEWER-01 PASS_WITH_CAVEAT；Pro-Max SUPERSEDED；0 sims / 0 reruns / Q3·H1·K12·H2 changed=false）、`Q4_FINAL_HASH_MANIFEST.json`（final_handoff 7/7 + formal core + registry + report/provenance + Q3 引用 的 SHA256；mutable_after_seal=false）、`Q4_FINAL_AUTHORITY_MAP.json`（paper number authority = final_handoff；formal numeric evidence = accepted evaluation root；seal/provenance = final_closure；screening = 历史 selection trail 仅追溯；historical drafts 以 final_handoff 为准）、`Q4_FINAL_REOPEN_POLICY.md`（HUMAN_GATE_REOPEN_Q4 清单 + G7 允许的语义等价论文化操作 + 发现实质错误 STOP）、`Q4_FINAL_CLOSURE_AUDIT.json`（55 项机械检查全 PASS：formal numeric integrity / conditional margins / interaction / factor rank / F3·F5 scope / Q-A·Q-B·e semantics / ledger non-additivity / Q3·H1·K12·H2 immutable / final_handoff 0 实质修改）。
    - **seal 验证**：HEAD==`a94bcd0`==origin；final_handoff 7/7 存在且本包 0 修改；accepted numerics git-diff 为空；新 simulation = 0、rerun = 0、Pro-Max calls = 0。
    - **任何未来实质 Q4 变更 → HUMAN_GATE_REOPEN_Q4（作废当前 seal）**；G7 仅允许语义等价的论文化操作。
- **（历史）Q3-H2-P3-C（action stability diagnostics）= COMPLETED → H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE（冻结硬门；AUTOPILOT STOP，未运行 cross-K transfer / h2_holdout / C25）**（Human Gate 已授权本执行包自动推进链；起始锚点 `c271a62`）：**B-1 样本** h2_tuning/seed 6/rep 0..9/K=10.5 十批（H1 baseline，批升序→批内时间序前 50 wait-eligible + 前 50 PM-only）→ **n=100（wait=50、PM=50、both=20，≥50 PASS）**；stability (a) C23 policy（hidden true_state/lifetime/u 变异不改 action）= **PASS**；stability (b) **ALT-salt agreement = 0.9900（99/100）≥ 0.95 点估计硬门 = PASS**（CP95 [0.9455, 0.9997] 仅披露不设第二门；唯一不匹配 = ALT salt 恰在 2SE 边界偏离一次，normal salt deviation_count=0）；stability (c) **M=8 vs M=16 = 1.0000 = PASS**（生产 M\*=8 不变）；**deviation_count = 0（100 点全部选 a_H1）→ 冻结硬门 H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE**（未降 2SE 阈值、未换样本、未重跑、未改动作集）；tests 20/20 + 回归 28/36/38/23/44/26 全 PASS；**P3-C 阶段实现修复**：`rollout_engine_v1._init_from_projections` 重建 in-flight calibration 时未调度 calibration_complete → WAKE_UP runaway（now→~8M h、log 无界 → MemoryError，首次完整运行失败并保留负证据处理）→ 修复为按 `state.time + in_flight_remaining_h` 调度 + fail-closed `MAX_CLOSURES=1e6` guard + 3 项回归测试；runaway 复检 100/100 点全部终止；证据 `05_结果/H2/tuning/stability/run_20260816T101049163825Z_791506d8`（fail-closed probe/confirm/promote/final 四段验证；ACYCLIC hash DAG + manifest/inventory 一致 + semantic mapping；RESULT 数字由 final evidence 机械生成；C21a/C21b 证据完整性 = PASS，C21 整体 = FAIL 如实反映 DELETE 门）；ledger 追加 `P3-C-...791506d8` wall_clock=685.53s → 累计 **755.70s（0.2099h）**（soft 4h / hard 8h 未达）；**cross-K transfer = NOT RUN（授权条件 = stability PASS 未满足）/ h2_holdout = NOT RUN / C25 = NOT RUN**；**AUTOPILOT STOP → Human Gate final Q3 review**。**（2026-08-16 追加：本旧执行因决策语义缺陷（Human Gate BLOCKER A–D：pre-action 状态 / 资源 idle / first-action 生效 / dp 键）标记 INVALIDATED_FOR_DECISION_SEMANTICS；数字保留不改；不再作为 H2 DELETE 决策证据；见上一条目重认证状态。）**

## 6. 当前禁止

- **H2 冻结禁令（FROZEN_HISTORICAL_CHALLENGER）**：禁止重开 H2 / H2'、禁止重新调 H2、禁止修改 H2 action set / 2SE / M* / C_eval* / B-1 / seed/salt；禁止增加 tuning sample、重跑 P3-C、运行 H2 cross-K / holdout / C25、为论文效果制造 deviation；除非未来 Human Gate 明确重新授权。
- **Q3 策略冻结**：禁止重新调 H1、禁止修改已接受 H1 formal 与 Q3 K recommendation（k\*=K12，scope = 七个 K + 冻结 H1 policy set）；除非未来 Human Gate 明确重新授权。
- **论文措辞禁令**：禁止「K=12 全局最优」「K=12 理论上支配所有 K」「K 越大一定越优」；禁止「H2 失败/无效/算法错误」「复杂模型一定不如简单模型」；禁止把 agreement=1 解释为「H2 优于 H1」；禁止把 0/100 泛化为「H2 在所有状态下等于 H1」；禁止把 cross-K / h2_holdout / C25 写成 PASS 或 FAILED（= NOT_APPLICABLE_AFTER_H2_DELETE，historically NOT RUN）。
- 不重开 D-01..D-25、不修改冻结的 `Q3_H2_BOOTSTRAP_SPEC_DRAFT.md` 规范条款（如需 → STOP 回 Human Gate）。
- 不改 G3/Q2/Q3 accepted 核心（random_des_v1/key_schema_v1/寿命再生/C06/C17/冻结观测语义/Q2-FORMAL-SPEC/Q3 H1 formal 与 K recommendation）；若需改 → STOP 回 Human Gate。
- 不修改已签字口径与 accepted 证据（含全部 H2 evidence roots，immutable）；若实现暴露新歧义，回到变更控制而不是自行决定。
- 不手录数字为权威；手稿数值必须机械可追溯至 accepted formal 证据。
- 不把 tuning/诊断值（机会密度、M 校准、稳定性样本、跨 K transfer 诊断）当论文正式数字。
- 不把失败 run `daead4cf` 或 G3 调优/holdout 数据（含 tau_pm=198 候选的调优 mean T）当作 Q2 论文数字来源；论文数字只来自 accepted run `2d1466ba`。
- 不宣称 tau_pm=198 最优（= FORMALLY_NOT_SELECTED_FOR_Q2_PRIMARY）；不把 C3（不可区分）转为 tau198 优越证据；不因 H2 结果重开 Q2 或宣称 Q2 H1 次优。
- 不宣称 NO_PM 超越冻结模型/候选集范围的普适最优或一般工业管理定理。
- 不把旧 C24 `waiting_opportunity_count` 当作 H2 战略等待密度（= forced-wait 仪表）；未来任何 H2 复用作修正定义（strategic STRICT/BOUNDARY/NONSTRICT + optional PM 与 mandatory 分离）。
- **Q4 授权限定（HG-Q4-FINAL-SEAL-01 已密封）**：**Q4 = FINAL CLOSED / IMMUTABLE / READY_FOR_PAPER**（sealed head `a94bcd0`；closure `HG-Q4-FINAL-SEAL-01`）——formal numeric root = accepted evaluation root；paper-facing root = `05_结果/Q4/final_handoff/`（7/7 锁定，hash manifest 固化）；final closure root = `05_结果/Q4/final_closure/`；**Q4 new simulation = NOT AUTHORIZED / NOT REQUIRED；Q4 rerun = NOT AUTHORIZED / NOT REQUIRED**；**禁止修改 accepted numerics / T_by_rep / ledger_by_rep / registry / final_handoff**（任何实质变更 → HUMAN_GATE_REOPEN_Q4）；**禁止本阶段调用 Pro-Max**（final semantic review = CLOSED via HG-Q4-REVIEWER-01；Pro-Max = SUPERSEDED / NOT REQUIRED）；Q3 / H1 / K\*=K12 / H2 一律 UNCHANGED；**G7 = AUTHORIZED_FOR_PAPER_FREEZE（不得自动开始，等待 Human Gate）**。
- 不重跑 Q1/Q2、不重跑已接受 H1 formal、不删除 H2 负结果或旧 invalidated roots。

## 7. 下一出口

G2/G3/Q2 H1 FORMAL 均已 PASS/ACCEPTED；**Q3/H2 BOOTSTRAP = FINAL PASS / ACCEPTED（D-01..D-25 冻结；冻结权威规格 = `08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT.md`）**；**P0（H2 key schema bootstrap）= VERIFIED FINAL PASS / ACCEPTED（已关闭）**；C24 = PASS；**Q3-H2 Density = FINAL PASS / ACCEPTED（D-14 A 7/7 + B 7/7；E1 `a2669aa9` + E2 `0713f171`）**；**Q3-H2-P1（信息防火墙 + C23 P1-applicable）= FINAL PASS / ACCEPTED（`08488e4`）**；**P2 + P2-E1 = FINAL PASS / ACCEPTED（`31f13f9` + `a5d2faf`）**；**Q3-H2-P3-A + P3-A-E1 = FINAL PASS / ACCEPTED（`b285131` + `fcf07f6`）**；**Q3-H2-P3-B + P3-B-E1 = FINAL PASS / ACCEPTED（`841bafc`→`10a6491`→`c271a62`；冻结 M\*=8、C_eval\*=8、W_cap\*=4、P_cap\*=4）**；**Q3-H2 = FINAL DELETE / ACCEPTED（Human Gate 2026-08-17；accepted evidence `run_20260816T175317829317Z_7b490ce6`；H2_NO_EFFECTIVE_DEVIATION；H2 = FROZEN_HISTORICAL_CHALLENGER；cross-K / h2_holdout / C25 = NOT_APPLICABLE_AFTER_H2_DELETE（historically NOT RUN）；H2' = NOT PLANNED）**；**Q3 正式主策略 = H1（七 K accepted formal chain；k\*=K12 为「七个 K + 冻结 H1 政策集」范围内 strong winner，非全局最优、不宣称弱支配）**；**C23 = MECHANICS REQUALIFIED + ROLLOUT PATH PASS（full production C23 PENDING UNTIL FINAL POLICY CONFIG——H2 DELETE 后不再需要）**；C25 = NOT_APPLICABLE_AFTER_H2_DELETE；**Q3 FINAL MODEL SELECTION CLOSED；Q3 FINAL STATUS = READY_FOR_PAPER**。**Q4 PHASE 1A（FAST SCREENING）= FINAL PASS / ACCEPTED**（evidence `05_结果/Q4/screening/phase_1a/20260817T060454057035Z_c516bd6c/`；F3 措辞按 Human Gate 红线修正）；**Q4 NUMERIC RESULTS = FINAL PASS / ACCEPTED（HG-Q4-NUMERIC-01，accepted HEAD `8096d80`；Q4 FORMAL FACTOR RANK = ACCEPTED；Q4 INTERACTION NUMERICS = ACCEPTED）**；**Q4 FINAL SEMANTIC REVIEW = PASS / CLOSED（HG-Q4-REVIEWER-01：reviewer = GPT-5.6 Sol，verdict = PASS_WITH_CAVEAT；DeepSeek Pro-Max = SUPERSEDED / NOT REQUIRED，未伪造 runtime receipt）**——RA-S1（条件边际 direct paired CI：cond E−10 = −3.5648 h [−4.027, −3.103]、cond E+10 = +91.3330 h [90.225, 92.441]）、RA-S2（Q-A 措辞）、RA-S3（scope hardening）全 PASS；**Q4 FINAL SEAL = HG-Q4-FINAL-SEAL-01：Q4 = FINAL CLOSED / IMMUTABLE / READY_FOR_PAPER；G7 = AUTHORIZED_FOR_PAPER_FREEZE**；paper-facing 包 `05_结果/Q4/final_handoff/`（7/7 锁定）；final closure root `05_结果/Q4/final_closure/`；**Q4 new simulations = NOT REQUIRED；Q4 evaluation rerun = NOT REQUIRED；Pro-Max calls = 0**。**下一阶段（已授权，等待 Human Gate 启动）**：**G7 PAPER FREEZE**（Q4 paper-facing 包为唯一论文数字/措辞来源；Q3 = READY_FOR_PAPER 一并进入）→ 论文写作/提交。

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
