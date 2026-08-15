# CHANGELOG

本文件只记录会改变当前入口、权威版本、模型含义、阶段状态或文件结构的变更。详细论证保留在签字口径、评审响应和 AI 使用日志中。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q3 H1 FORMAL FINAL PASS / ACCEPTED（Density Gate 激活）`

### 修改

- **Q3 H1 FORMAL = FINAL PASS / ACCEPTED（Human Gate 2026-08-15）**。accepted physical run = `run_20260815T133840057668Z_7ee48fc0`；accepted final provenance reissue = `05_结果/Q3/formal/reissue_20260815T150613626910Z_f4da8f9d`；**C21 = PASS / REQUALIFIED**（hash DAG 无环 + manifest/inventory 三向一致 + recommendation 措辞 orientation-neutral）。
- **Tier 1 H1 基线预注册报告**：k\* = **K12**（strong、co-best=[]）——**措辞限定**「七个 K + 冻结 H1 政策集（NO_PM_BEFORE_MANDATORY）内」；**非全局最优、非 K12 弱支配、非 final Q3 overall recommendation**（H2 challenger 尚未完成 Density/C25）。
- **Roadmap 更新（Human Gate 裁决）**：Q3 H1 accepted → **Q3 七 K H2 opportunity-density recheck（Density Gate，本执行包）** → Density FAIL → DELETE H2、Q3 H1-only、不实现 P1；Density PASS → STOP 回 Human Gate → Human Gate 再决定是否授权 P1。**P1 / C23 仍 NOT AUTHORIZED**。
- 状态同步：`CURRENT_STATE.md`（Gate 行更新：Q3 H1 FORMAL = FINAL PASS / ACCEPTED；Q3 H2 opportunity-density recheck = ACTIVE）。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q3-H1-E2 FINAL PROVENANCE CONSISTENCY CLOSURE`

### 修改

- **Q3-H1-E2（Final Provenance Consistency Closure）完成**：修复 E1 clean reissue 的最后一个 provenance bug——E1 `run_manifest.json` 记录的 `C21_REQUALIFICATION_REPORT.json` SHA（`5afd45ce…`）与最终 `file_hashes.sha256`（`83521c37…`）不一致（E1 脚本在 manifest 生成后回写 `inventory_count` 重写 C21 report，仅重生成 file_hashes，未重生成 manifest）。未重跑任何 Q3 DES batch、未消费新 q3_formal 随机世界、未改变任何 T/S/PL/PW/YXB。
- **根因修复原则（已落实）**：所有被 manifest 记录 SHA 的 artifact 必须在 manifest 生成前 FINALIZED，之后绝不再修改；写入顺序 = 物理 cells → 衍生分析 → checks/commands/env/config/input hashes → **FINALIZE C21 report（inventory_count 由计划最终集合预先确定）** → FINALIZE task_package_snapshot → 由 FINAL 字节构建 manifest outputs[] → 写 run_manifest.json → **file_hashes.sha256 最后写**（含 run_manifest 与 C21，永不含自身）→ 只读 verify（禁止 verify 后写回任何已哈希 artifact）。
- **新增 fail-closed checker** `verify_manifest_inventory_consistency()`：验证 manifest.outputs[].sha256 == actual == file_hashes 条目（对重叠文件 100% 一致），并专项检查 C21 report 三向一致。
- **E2 clean reissue**：`05_结果/Q3/formal/reissue_20260815T150613626910Z_f4da8f9d/`（type = Q3_H1_FORMAL_FINAL_PROVENANCE_REISSUE；physical_source_run `run_20260815T133840057668Z_7ee48fc0`；physical_source_commit `a2a9690…`；supersedes_provenance_reissue = E1 reissue；new_physical_simulation = NO；new_q3_formal_random_world_consumption = NO）。**14/14 cell 与源字节一致**；衍生数值 0 差异；k\* = K12、strong = TRUE（两 tier）；21/21 pair CI 排除 0；**HASH_GRAPH_ACYCLIC = PASS、HASH_INVENTORY = 28/28、MANIFEST_OUTPUT_HASHES = 27/27、MANIFEST_INVENTORY_CROSSCHECK = 27/27、C21_REPORT_SHA_CONSISTENCY = PASS（C21 三向 SHA = `9bb544a5…`）**；task_package_snapshot SHA `a0864c87…` 一致；`C21_REQUALIFICATION_REPORT.json` verdict = PASS。
- **状态标记**：源物理 run（`7ee48fc0`）物理结果有效、provenance packaging 已被 E1/E2 逐级 supersede；E1 reissue（`ee6c5ab7`）= **HISTORICAL_PROVENANCE_REISSUE_WITH_STALE_MANIFEST_ARTIFACT_HASH**（保留不可改，物理/衍生数值不声明错误）；E2 reissue 为提交 Human Gate 最终验收的证据。
- **状态**：Q3 H1 FORMAL = **EXECUTION COMPLETED / FINAL PROVENANCE REQUALIFICATION COMPLETED / AWAITING HUMAN GATE FINAL REVIEW**（非 ACCEPTED；最终 Q3 K 推荐待 Human Gate）；Density recheck / P1 / C23 / C25 未执行。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q3-H1-E1 PROVENANCE CLEAN REISSUE COMPLETED`

### 修改

- **Q3-H1-E1（Formal Provenance Clean Reissue）完成**（Human Gate 审计发现两项正式证据问题已修复；未重跑任何 Q3 DES batch、未消费新 q3_formal 随机世界、未改变任何 T/S/PL/PW/YXB）。
- **F1 — C21 hash cycle 修复**：源 run `run_20260815T133840057668Z_7ee48fc0` 存在 `run_manifest.json ↔ file_hashes.sha256` 互相记录对方 SHA 的循环。新证据采用 **ACYCLIC HASH INVENTORY（RULE A）**：run_manifest 只以 `hash_inventory_path` 指向 `file_hashes.sha256`、**不记录其自身哈希**；`file_hashes.sha256` 哈希全部 artifact（含 run_manifest.json 与 task_package_snapshot.yaml）、**永不哈希自身**；无 mutual edge、无 self hash。runner 新增 `verify_hash_dag()`（fail-closed 自检）+ DAG 回归测试。
- **F2 — recommendation 措辞修正**：strong 措辞由固定「CI 完全 <0」改为 **orientation-neutral**（「k* 相对其余全部 K 的配对 CI 均位于支持 k* 完成时间更短的一侧并排除 0（左端更快=CI<0；右端更快=CI>0）」）；a2a9690 的 strong/co-best 计算逻辑未推翻，仅文字修正。
- **Task package snapshot 补齐**：clean reissue 新增 `task_package_snapshot.yaml`（byte-exact 拷贝，SHA256 `a0864c8728603ef85c12eff91500c78909f70d74738cb42765212d0c035b4472` 已验证）。
- **Clean reissue**：`05_结果/Q3/formal/reissue_20260815T145531744357Z_ee6c5ab7/`（type = Q3_H1_FORMAL_PROVENANCE_CLEAN_REISSUE；physical_source_run / physical_source_commit = `a2a9690…`；new_physical_simulation = NO；new_q3_formal_random_world_consumption = NO）。**14/14 cell 与源 run 字节一致**；衍生分析（family_aggregates、tier1/2 pairwise、recommendation、quality、rare-event）由源 cell artifacts 重新生成——**除 recommendation 文字/provenance 字段外数值全等（0 差异）**；k\* = K12、strong = TRUE（两 tier）；Tier 1/Tier 2 各 21/21 pair CI 排除 0（按文件排序 pair 定义全部 CI>0）；HASH_GRAPH_ACYCLIC = PASS、HASH_INVENTORY = 28/28 PASS；`C21_REQUALIFICATION_REPORT.json` = **PASS**。
- **源 run 标记**：`run_20260815T133840057668Z_7ee48fc0` = **HISTORICAL_Q3_H1_FORMAL_EXECUTION_WITH_SUPERSEDED_PROVENANCE_PACKAGING**（保留不可改；其物理模拟结果不声明为错误；superseded 的仅为 provenance packaging 与 recommendation wording artifact）。
- **YXB 披露纠正（§13）**：此前 Harness summary 误写「S/PL/PW/YXB 跨 K 完全一致」——**正确表述**：S/PL/PW 与 four-cell 质量计数跨 K 保持一致（C06 pathwise 分离验证）；**YXB 是设备利用率指标，随 K 改变，不要求跨 K 相等**（物理 YXB 数值未改）。
- **状态**：Q3 H1 FORMAL = **EXECUTION COMPLETED / PROVENANCE REQUALIFICATION COMPLETED / AWAITING HUMAN GATE FINAL REVIEW**（非 ACCEPTED）；clean reissue 为提交 Human Gate 最终验收的证据；Density recheck / P1 / C23 / C25 未执行。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q3 H1 FORMAL EXECUTION COMPLETED / AWAITING HUMAN GATE REVIEW`

### 修改

- **Q3 H1 七 K 正式基线（Tier 1 + Tier 2）执行完成**（Q3-H1-FORMAL-SPEC-V1.0；绑定 code/config commit `a2a9690d70bf6514f1db7427d549be8e75b01145`；preflight PASS；正式运行 exit 0）。
- **正式 run**：`05_结果/Q3/formal/run_20260815T133840057668Z_7ee48fc0/`；namespace=q3_formal、master_seed=5、replicate_ids 0..199；Tier 1（single_test_unconditional_v1 × 1h_literal × NO_PM_BEFORE_MANDATORY）7 K × 200 批 + Tier 2（standard_chain_v1 × 1h × NO_PM）7 K × 200 批 = **2800 批 / 280 000 台**；族墙钟 2923.6 s。
- **检查**：CR-V3.1 C06 = **2800/2800 PASS**、C17 = **2800/2800 PASS**（逐批）；C13/C14/C15/C16/C18/C26/C21/C19/C20 = PASS；C07 = 族级诊断（GP/BP/GE/BE 烟测，非硬门）。checks.json overall = **PASS**。
- **Tier 1 主结果（预注册统计报告；非 Human Gate ACCEPTED）**：每 K mean T 单调随 K 减小——K09 ≈ 601.3 h / 25.05 d → K12 ≈ 417.8 h / 17.41 d（SE 8.98–13.55 h）；21 个两两配对 CI 全部显著；**k\* = K12，strong_recommendation = TRUE（在七个 K + 冻结候选政策集内）**；co-best = ∅。质量跨 K 完全一致（S=94.47、PL=1.76%、PW=0.085%，C06 pathwise 分离验证）；PL 稀有事件池化 352/20000（CP95% [0.01582,0.01952]）、PW 17/20000（[0.000495,0.001361]）。
- **Tier 2（chain 独立全链）**：同型——K09 ≈ 594.9 h → K12 ≈ 413.2 h；k\* = K12、strong；S=93.66、PL=0.965%、PW=0.10%。
- **证据 finalization 说明**：evidence 的 `file_hashes.sha256` 于 runner 生成后做了机械补全（覆盖含 run_manifest.json 的全部 26 个文件；清单不含自身；已验证 26/26 一致）。runner 顺序沿用 accepted Q2 惯例（manifest 最后写入），未改动任何结果字节。
- **状态**：Q3 H1 FORMAL = **EXECUTION COMPLETED / AWAITING HUMAN GATE REVIEW**（非 Human Gate ACCEPTED）；**最终 Q3 K 推荐待 Human Gate review**（k\* 为预注册统计报告，不视为已批准推荐）；不宣称 K=12 弱支配/全局最优；Density recheck / P1 / C23 / C25 未执行。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `ROADMAP SYNC: Q3 H1 FIRST（P0 关闭）`

### 修改

- **Roadmap governance sync（仅阶段事实，无数学语义变更）**：最新 Human Gate 决策——P0 = **VERIFIED FINAL PASS / ACCEPTED（P0 关闭）**；下一大阶段正式切换为 **Q3 H1 FIRST**。
- 路线（Human Gate 决策）：**① Q3 H1 七 K 正式基线（Tier 1 + Tier 2）→ ② Human Gate H1 formal review → ③ 基于 accepted Tier 1 日志的确定性只读 Q3 七 K H2 opportunity-density recheck（Density FAIL → DELETE H2、Q3 H1-only；Density PASS → 才允许 Human Gate 授权 P1）**。
- **P1 / C23 / posterior / rollout 当前仍 NOT AUTHORIZED**；Density recheck 不包含在当前 Q3 H1 formal 执行包中；Q3 K 推荐须等 Human Gate H1 formal review。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§6 禁止、§7 路线）更新为「Q3 = ACTIVE（Q3 H1 七 K 正式基线执行中/待审；无 K 推荐）」。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `P0-E1 TEST EVIDENCE CLOSURE`

### 修改

- **P0-E1（Human Gate Test Evidence Closure）**：在 exact commit `9f6099c71e09844079801222b7dc2fa1db6cee45` 重跑 P0 声明的全部测试，并落库执行证据 `01_审计/P0_H2_KEY_SCHEMA_TEST_EVIDENCE.md`。
- 结果：A `test_p0_h2_key_schema_bootstrap_v1` 18 / B `test_g3_key_schema_v1` 38 / C `test_g3_c16_experiment_separation_v1` 36 / D random_des 4 类子集 16 / E `test_g3_lifetime_regeneration_v1` 42 —— 全部 exit 0 / PASS；golden **620 vectors** canonical UTF-8 + Fraction mismatch = **0**（LEGACY KEY BYTE COMPATIBILITY = PASS）；tiny 确定性引擎批 pre/post canonical SHA 精确一致（log `d202fb91…`、summary `dc8715a6…`）。
- **无生产代码修改**；未进入 P1；未运行 Q3 formal / holdout / C25；expected fixture 未重新生成；Gate 状态不变（H2 NOT IMPLEMENTED、C23/C25 PENDING、Q3 NOT STARTED）。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `P0 H2 KEY SCHEMA BOOTSTRAP IMPLEMENTATION COMPLETED`

### 修改

- **P0（Q3/H2 IMPLEMENTATION BOOTSTRAP 子包 1）实现完成**（Human Gate P0 SPEC = PASS / READY TO EXECUTE；authority anchor `1de71824e668f3815f58112cb3c42c9633b2da16` 已核验；pre-change key_schema blob SHA `8a8f1089…`）。
- `04_代码/main_model/g3/key_schema_v1.py`：新增 3 个正式 H2 namespace（`h2_tuning` / `h2_holdout` / `h2_rollout`）与 4 个 H2 post stream helper（`u_x_post` / `u_d_post` / `u_y_post` / `u_l_post`）；`h2_future` 保留为历史占位（未被升级）；**legacy 常量与序列化/哈希/Fraction 映射逐字节不变**（`NAMESPACES` / `ALL_NAMESPACES` 未动，既有 38+36 个冻结断言保持通过）；**namespace consumption firewall 显式实现**（legacy physical helper 拒绝全部 H2 namespace 与 h2_future；H2 post helper 拒绝 legacy namespace 与 h2_future）。
- 新增 legacy golden fixture `04_代码/tests/fixtures/g3_key_schema_legacy_golden_v1.json`（**620 vectors**；expected 仅来自 exact pre-change oracle——commit `1de71824` blob `8a8f10895ee9751fb7c3c93093c3cdac25b4b632`；修改后未重新生成 expected）+ 生成脚本 `run_p0_legacy_oracle_golden_v1.py` + P0 测试 `test_p0_h2_key_schema_bootstrap_v1.py`（18 tests：A 单元 / B golden 回归 / C firewall / D 隔离）。
- **Legacy 兼容验证**：golden regression 620/620 **canonical UTF-8 bytes + Fraction numerator/denominator 100% identical**（LEGACY KEY BYTE COMPATIBILITY = PASS）；既有回归 `test_g3_key_schema_v1`（38）/ `test_g3_c16_experiment_separation_v1`（36）/ `test_g3_random_des_v1` 子集（16）/ `test_g3_lifetime_regeneration_v1`（42）全 PASS；tiny 确定性引擎批 pre/post canonical SHA 一致（log `d202fb91…`、summary `dc8715a6…`）。
- **未实现**：posterior、rollout_seed(dp,m)、rollout、H2 policy、C23 判定、C25、Q3 formal；未修改 DES/H1/Q2 语义；未运行任何正式实验。
- **Gate 状态不变**：H2 仍 **NOT IMPLEMENTED**；C23/C25 = PENDING；Q3 = NOT STARTED（无 K 推荐）；**P0 完成不升级任何正式 Gate**（CURRENT_STATE 未改动）。

### 影响与边界

- P0 只铺设 H2 随机键基础设施；后续（须 Human Gate 另发执行授权）：H2 posterior/rollout 层、C23 实现与检查、Q3 七 K 运行、H2 管线（density recheck → tuning → holdout → C25）。
- 引擎 `RandomDesConfig` 仍只接受 6 个 legacy namespace（`ks.NAMESPACES` 未动；`h2_*` 配置仍 fail closed）；未来 H2 批在 `h2_tuning` / `h2_holdout` 上运行需在 H2 runner 包中做显式、受审计的引擎 namespace 扩展（P0 不做，本包范围外）。
- `rollout_seed(dp,m)` 与续演子流派生属于后续 rollout 层（冻结 Bootstrap §6.2），P0 未实现（模块内 TODO 记录）。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q3/H2 BOOTSTRAP DESIGN FREEZE APPROVED`

### 修改

- **Q3/H2 BOOTSTRAP = FINAL PASS / ACCEPTED（Human Gate 2026-08-15 VERIFIED FINAL PASS / DESIGN FREEZE APPROVED；已直接审阅 623 行版本）**。冻结权威规格 = `08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT.md`（状态 **FINAL_FREEZE_ACCEPTED / HUMAN_GATE_PASS**）；§19 **D-01..D-25 全部冻结，不得重开**。
- **BOUNDARY 契约同步（D-11/D-25 批准）**：`e == latest_start` 为合法 WAIT——`01_审计/问题契约.md`（§1.3.2、§7.5）与 `03_模型/高级模型技术补充_V3.1.md`（§5.3）中 H2 strategic-wait 语义由「早于最迟启动时刻」同步为「**早于或等于最迟启动时刻**」；`now + duration ≤ shift_end`（恰班末完成合法）保持；未扩大到其他班界/启动规则。
- **H2 权威规格同步**：`03_模型/03_H2后验Rollout候选.md` 更新为冻结设计——动作集 `A0=START_HEAD / A0b=H1_NOOP·ADVANCE_EVENT / A1=WAIT_EVENT / A2a=PM_WITH_HEAD / A2b=PM_IDLE`；两类决策点 `DISPATCH_DECISION_POINT / MAINTENANCE_DECISION_POINT`（queue empty 与 queue-nonempty-but-no-legal-head 均可产生 maintenance 点；每资源每闭包至多一个；canonical 序 A/B/C/E）；PM_IDLE vs A0b；quota class ≠ action availability；**ONLINE quota**：`W_cap=⌈C_eval*/2⌉ / P_cap=⌊C_eval*/2⌋`（C_eval*=6→3+3、8→4+4）、independent caps、no cross-side borrowing、unused expires、no future candidate count、no retroactive selection、wait 前 W_cap 个、PM B1/B2/B3 bucket-first + P_cap=4 恰 1 个 extra slot（P_cap=3 无）。
- **PM_IDLE action-space 闭合**：核心边界 = equipment idle + PM physical/calendar legality，不以队列是否为空为边界；forced-wait 队列非空情形纳入 maintenance 机会。
- **在线因果 quota 闭合**：删除跨侧事后 borrowing；`selected_for_rollout(t)=f(history ≤ t, quota_state(t))`；checker 断言 `wait_selected ≤ W_cap`、`PM_selected ≤ P_cap`、`selected_total ≤ C_eval*`。
- **C24 = PASS**（opportunity-density evidence = PASS；budget/spec freeze = PASS——两子项闭合）。**H2 = NOT IMPLEMENTED**；**C23 = PENDING**；**C25 = PENDING**；**Q3 formal = NOT STARTED（无 Q3 K 推荐）**。
- **Provenance**：Bootstrap 审计链（`Q3H2_SEMANTIC_REVIEWER` / `Q3H2_MECHANICAL_CHECKER`）及外部 L4 裁决凡无 session request/header 机械证据处，reasoningEffort 一律记为 **UNVERIFIED**（不伪写 mechanically verified；不据提示词/平台默认推定 high）。
- **下一阶段（未授权）**：Q3/H2 IMPLEMENTATION BOOTSTRAP + C23 实现与检查，须 Human Gate **另发执行授权**。

### 影响与边界

- 设计冻结 ≠ 实现授权：H2 不实现、Q3 七 K 不运行、无 K 推荐、无 tuning/holdout/formal 新实验。
- tuning/诊断值（机会密度、M 校准、稳定性样本、跨 K transfer 诊断）**非论文正式数字**。
- 不重开 D-01..D-25；不改已冻结 Q2/G3 accepted 结论（run `2d1466ba` 数字、NO_PM 主政策、tau_pm=198 FORMALLY_NOT_SELECTED）。
- 后续实现/运行须按 CR-V3.1 / AUTOPILOT 治理另发授权；Macro 停点回 Human Gate。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `H2 ADMITTED FOR DESIGN ONLY`

### 修改

- **H2 ADMISSION OPPORTUNITY EVIDENCE = PASS；H2 = ADMITTED_FOR_DESIGN_ONLY**（Human Gate 2026-08-15；非 H2 FINAL ACCEPTANCE；H2 实现 NOT YET AUTHORIZED）。
- **证据**：`01_审计/H2_ADMISSION_C24_EVIDENCE_DRAFT.md` + `01_审计/H2_ADMISSION_EVIDENCE_L3_REVIEW_RECORD.md`；工具 `04_代码/checker/h2_admission_opportunity_analyzer_v1.py`（独立、stdlib-only、无 main DES import）、`04_代码/scripts/run_h2_admission_evidence_v1.py`（纯 orchestration/reporting wrapper，RUNNER_GOVERNANCE_DEVIATION=CLOSED_BY_HUMAN_GATE_CONDITIONAL_AUTHORIZATION）、`04_代码/tests/test_h2_admission_opportunity_analyzer_v1.py`（12 tests）。
- **机会密度（仅 density，非性能声明；NO_PM / G3 tuning 20 批 + holdout 全 100 上下文）**：legal dispatch ≈413.1/批；**strategic wait strict ≈11.4/批（~2.8%）**；**optional PM feasible ≈168.8/批（~41%）**；both ≈4.5/批；**meaningful H2 choice fraction ≈0.429**；零机会批次比例 0%（strategic/PM/meaningful）。
- **C24 审计**：旧 `waiting_opportunity_count` 测的是 **forced wait / 当前非法性**，**不是 H2 战略等待密度**；比离线 strategic wait 高约一个数量级（150/批 vs 11.4/批），**不得复用为 H2 strategic-wait 计数**。未来 H2 用修正定义（STRICT/BOUNDARY/NONSTRICT + optional PM 与 mandatory 分离）。
- **C24 状态拆分**：opportunity-density evidence = **PASS**；budget/spec freeze = **PENDING**（不标 full C24 PASS）。**C23 = PENDING / NOT YET EXECUTED**；**C25 = PENDING / NOT YET EXECUTED**。
- **证据来源分离**：仅 G3 tuning `01b7c7e7` + holdout `020bc637`（确定性重放、hash 逐批匹配）；**q2_formal design leakage = NONE**；无新随机模拟。
- **Reviewer provenance**：v1 FAIL（analyzer 设备年龄未重置缺陷）保留历史；v2 `H2_ADMISSION_EVIDENCE_L3_REVIEWER`（session `2cea14f5-4d6b-491d-b845-795b47cfccc2`，机械验证 deepseek-official/deepseek-v4-pro/high）= PASS/HIGH/evidence_integrity=HIGH；advisory density=MODERATE、recommendation=**ADMIT_FOR_DESIGN**。
- **状态更新**：Q2 H1 FORMAL = PASS/ACCEPTED、G3 = PASS/ACCEPTED 不变；Q2 主情景 H1 政策 = NO_PM_BEFORE_MANDATORY 不变；tau_pm=198 = HISTORICAL_TUNING_SELECTED_CANDIDATE / FORMALLY_NOT_SELECTED_FOR_Q2_PRIMARY 不变；Q3/Q4 = NOT STARTED。

### 影响与边界

- **H2 admission 不重开 Q2**；不宣称 Q2 H1 次优；不宣称 H2 改善 T / 最优 / 应进论文 / 任何 rollout M / 任何 Q3 K。
- 下一阶段：**Q3 + H2 ADVANCED SCHEDULING BOOTSTRAP**——新 Human Gate/新会话先冻结 rollout M、每批 H2 评估上限、墙钟软硬预算、动作稳定性、样本划分、C23、Q3 七 K 基线协议、Q3 H2 密度复核方式；本 landing 不选这些值。
- 禁止：实现 H2 rollout、选 M、跑 H2 政策实验、消费新随机世界、改 accepted DES 语义、改 accepted Q2/G3 结果、启动 Q3 七 K 模拟、推荐 K、启动 Q4、改手稿。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q2 H1 FORMAL FINAL PASS`

### 修改

- **Human Gate 2026-08-15 FINAL PASS：Q2 H1 FORMAL = PASSED / ACCEPTED；AUTOPILOT PILOT #3 = COMPLETED AT MACRO STOP**。
- **Accepted qualifying reviewer**：`Q2_FORMAL_MACRO_L3_REVIEWER`；session `137d4fc1-d2de-4f49-a250-f1418703604f`；runtime 机械验证 = deepseek-official / deepseek-v4-pro / high；overall_decision = **PASS** / confidence = **HIGH** / formal_result_integrity = **HIGH**。
- **Accepted formal run = `run_20260815T061803446274Z_2d1466ba`**（05_结果/Q2/formal/）：8 cells × 200 批 × 100 台；namespace=q2_formal、master_seed=3、replicate_ids=0..199；**C06=1600/1600、C17=1600/1600 PASS**；C13/C14/C16/C18/C26 PASS（applicable formal scope）；无正式重调。
- **Q2 主情景正式 H1 政策选择 = NO_PM_BEFORE_MANDATORY**：主单元（single_test_unconditional_v1 × 1h_literal）ΔT = T(tau198)−T(NO_PM) = **+1.2892 h**，98.75% Bonferroni CI **[0.4625, 2.1942]** 完全>0 → **NO_PM 完成时间更短**（不主动预防更换，保留全部冻结强制更换规则）。
- **tau_pm=198 = HISTORICAL_TUNING_SELECTED_CANDIDATE / FORMALLY_NOT_SELECTED_FOR_Q2_PRIMARY**：正式前选出、从未用 q2_formal 重调；不宣称最优；不删除/改写调优历史。
- **4 预声明对比（98.75% CI）**：C1 PRIMARY single+1h +1.2892 [0.4625,2.1942] → NO_PM 更短；C2 single+0.5h +4.2292 [3.1983,5.2963] → NO_PM 更短；C3 chain+1h −0.1281 [−1.1146,0.8000] → 不可稳定区分（不转为 tau198 优越证据）；C4 chain+0.5h +5.3211 [4.1314,6.6234] → NO_PM 更短。整体：3/4 对比偏好 NO_PM 且区间完全>0，1 个不可区分，无一正式支持 tau198 更短。
- **主单元正式聚合**（accepted）：mean T=332831/400 h、mean S=18851/200、PL pooled=383/20000、PW pooled=17/20000；稀有事件精确 CP 95%：PL [0.017296,0.021146]、PW [0.000495,0.001361]。tau198 与 NO_PM 单元质量输出相同（C06 分离命题一致）。
- **Q2 论文数字权威现已可用** = run `2d1466ba`（formal_comparison_table.json + rare_event_report.json + family_aggregates.json + per-batch raw + checker/evidence reports）；禁手录、禁用失败 run `daead4cf`、禁用调优/holdout 值替代。
- **旧 run `daead4cf` 保持永久 HISTORICAL_FAILED_FORMAL_ATTEMPT / VALIDATION_FAILED / paper_authoritative=false**（旧 C17 checker C10/C12 缺陷；RED + INVALIDATION_REPORT ×2 + REQUALIFICATION_RECORD 保留，不追溯升级）。
- **G3 C17 supplemental requalification 链**：CR-V3.1/C17 = PASS / REQUALIFIED_AFTER_C10_C12_CHECKER_FIXES（reviewer `G3_C17_REQUALIFICATION_L3_REVIEWER` session `ab890743` verified Pro/high）；G3 = PASS/ACCEPTED；新旧 DES 数学在相同世界下精确相等（唯一差异 = 21 条 checker 判定翻转 + 墙钟/hash）。
- **H2/Q3/Q4 保持未启动/未授权（适用处）**；无重调、无新实验、无代码/spec/证据修改（state landing only）。

### 影响与边界

- Whole G2 = PASS；G3 = PASS/ACCEPTED；Q2 H1 FORMAL = PASS/ACCEPTED；Pilot #3 = COMPLETED AT MACRO STOP。
- Q2 paper numbers = AVAILABLE / AUTHORITATIVE FROM ACCEPTED FORMAL RUN；H2 = NOT AUTHORIZED / ADMISSION DECISION PENDING；Q3/Q4 = NOT STARTED。
- 下一 Human Gate：评估 C24 实际 H1 决策机会证据 → 裁决 H2 admission vs deletion/skip → Q3。不暗示 H2 自动继续。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q2 H1 FORMAL Macro L3 PASS — PILOT #3 COMPLETED AT MACRO STOP`

### 修改

- **Q2 H1 FORMAL clean reissue 完成**（commit `aa8657c`）：run `run_20260815T061803446274Z_2d1466ba`（05_结果/Q2/formal/）完整 8×200 = 1600 批/160 000 台；**C06=1600/1600、C17=1600/1600 PASS**（每单元 200/200）；C13/C14/C16/C18/C26 PASS；`paper_authoritative=false`（非论文权威，待 Human Gate）。
- **C17 checker 两处独立缺陷修复（Human Gate OPTION A + A2）**：C10 cancelled-attempt（`023020e`）+ C12 terminal-horizon calibration（`b300473`）；INVALIDATION_REPORT ×2（均 changed_semantics=NO / main_engine=NO / checker_core=YES）；**CR-V3.1/C17 G3 full layer = PASS / REQUALIFIED_AFTER_C10_C12_CHECKER_FIXES**（`G3_C17_REQUALIFICATION_L3_REVIEWER` PASS/HIGH，session `ab890743`）；G3 = PASS/ACCEPTED（supplemental provenance）。首跑 `daead4cf` 保持 HISTORICAL_FAILED_FORMAL_ATTEMPT。
- **新旧确定性等价**：clean reissue vs 首跑 1600 批 DES 数学字段逐项相等（T/S/PL/PW/YXB/四格/替换/故障/片段/日志 hash 0 差异）；唯一差异 = 21 条 checker FAIL→PASS 翻转 + 墙钟/hash（允许）。
- **Q2 Macro L3 = PASS / HIGH / formal_result_integrity=HIGH**（`Q2_FORMAL_MACRO_L3_REVIEWER`，session `137d4fc1-d2de-4f49-a250-f1418703604f`，runtime 机械验证 deepseek-official/deepseek-v4-pro/high）。报告：`01_审计/MACRO_REPORT_Q2_L3.md`。
- **Q2 正式结果方向（4 预声明对比，ΔT=T(tau198)−T(NO_PM)，98.75% CI）**：C1 PRIMARY single+1h **+1.29h [0.46,2.19]**（完全>0 → 支持 NO_PM 更短）；C2 single+0.5h +4.23h [3.20,5.30]；C3 chain+1h −0.13h [−1.11,0.80]（含 0 → 不可稳定区分）；C4 chain+0.5h +5.32h [4.13,6.62]。**tau_pm=198 候选在主单元未改善完成时间**；不隐藏、不重调。
- **PILOT #3 = COMPLETED AT MACRO STOP；Q2_FORMAL_MACRO_L3_PASS_WAITING_FOR_HUMAN_GATE——无条件停机**。

### 影响与边界

- G2 = PASS；G3 = PASS/ACCEPTED（C17 REQUALIFIED）；Q2 H1 FORMAL candidate = 完整且非论文权威；H2 = NOT AUTHORIZED；Q3/Q4 = NOT STARTED；论文 Q2 数字 = NOT AVAILABLE。
- 停机后不自动 land Q2 FINAL PASS、不写论文数字、不实现 H2、不启动 Q3/Q4、不重调 tau_pm；下一阶段需新 Human Gate。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q2-FORMAL-SPEC-V1.0 FROZEN / PILOT #3 ACTIVE`

### 修改

- **Q2-FORMAL-SPEC-V1.0 冻结**（FROZEN_FOR_FORMAL_RUN）：Human Gate 2026-08-15 对 Q2-FORMAL-SPEC-V1.0-DRAFT = CONDITIONAL PASS（初评 `Q2_FORMAL_SPEC_L3_REVIEWER` = FAIL/HIGH，两项实质问题修复后保持历史证据，不升级）→ Phase B fresh FINAL reviewer `Q2_FORMAL_SPEC_FINAL_L3_REVIEWER`（session `698f74c3-d26b-4742-9270-e079b65b82a6`，runtime 机械验证 deepseek-official/deepseek-v4-pro/high）= **PASS / HIGH / implementation_ready=YES**，初评发现 A/B/C 全部闭合 → 冻结。
- **Human Gate 决策全部落文（Q2-FORMAL-DEC-01..06 + bootstrap 分析流）**：200 批/单元 × 8 单元 = 1600 批/160 000 台；namespace=q2_formal、master_seed=3、replicate_id=0..199（恰 200）；恰 4 个配对 Delta_T 对比（C1 PRIMARY single+1h；C2-C4 稳健），Bonferroni m=4、alpha_each=0.0125、双侧、边缘 CI coverage 0.9875（percentile 0.00625/0.99375）；PL/PW 池化 20000 台精确 CP 区间（x=0 → 单侧上界 `1-0.05^(1/20000)`）；族级证据根 `05_结果/Q2/formal/run_<UTC>_<8hex>/` + 冻结 8 cell tokens；soft 4h / hard 8h；bootstrap 分析流 namespace=q2_formal_analysis_bootstrap_v1、seed=30003、B=10000；`decision_required: []`。
- **tau_pm = 198 h 正式前冻结**（主单元 = single_test_unconditional_v1 + 1h_literal + tau_pm_198；政策参考 = 同观测/周转 + NO_PM_BEFORE_MANDATORY）；正式运行不重选 tau_pm。
- **AUTOPILOT PILOT #3 = ACTIVE**：Q2 H1 FORMAL 执行（thin formal runner over accepted G3 engine，不改 G3 core 语义）→ 完整 8×200 族运行 → 配对推断 → Q2 Macro L3（fresh verified Pro/high）→ Q2 Macro Gate 无条件停机。
- **正式证据在 Q2 Macro L3 + Human Gate 前非论文权威**（NOT PAPER-AUTHORITATIVE）；论文 Q2 数字 = NOT AVAILABLE。
- CURRENT_STATE 更新：Q2 H1 FORMAL = ACTIVE、Q2-FORMAL-SPEC-V1.0 = FROZEN、Pilot #3 ACTIVE、tau_pm 候选 198h、H2/Q3/Q4 未授权。

### 影响与边界

- G2 = PASS；G3 = PASS / ACCEPTED；Q2 H1 FORMAL = ACTIVE（Pilot #3 至 Q2 Macro Gate 无条件停机）。
- H2 = NOT AUTHORIZED；Q3 = NOT STARTED；Q4 = NOT STARTED；论文 Q2 数字 = NOT AVAILABLE。
- 禁止：改 G3 accepted 核心（需改 → STOP Q2_FORMAL_REQUIRES_G3_CORE_CHANGE）、实现 H2、枚举 K、启动 Q3/Q4、写论文。
- 软墙钟 4h / 硬墙钟 8h（Q2 正式运行预算）；hard cap 无条件停止。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `G3 FINAL PASS`

### 修改

- **Human Gate 2026-08-15 FINAL PASS：G3 = PASSED / ACCEPTED；AUTOPILOT PILOT #2 = COMPLETED AT MACRO STOP**。
- **Qualifying G3 Macro L3 reviewer accepted**：`G3_MACRO_L3_REVIEWER`；session `b0f56d04-90aa-4ed8-a4bd-b5b7847f9a8c`；runtime 机械验证 = deepseek-official / deepseek-v4-pro / high；overall_decision = **PASS** / confidence = **HIGH**。
- **S1-S9 accepted**：S1 key_schema / S2 寿命再生 / S3 随机 DES+H1 / S4 C06 oracle / S5 C17 replay / S6 C16 分离 / S7 H1 C26 tuning（accepted run `01b7c7e7`）/ S8 holdout（accepted run `020bc637`，C06/C17 100/100 PASS、C07 诊断 flagged 7/100、holdout_retune=FALSE）/ S9 evidence package（run `fc3fe3e6`，INDEX_OK）。
- **tau_pm = 198 h 为冻结 H1 候选（仅候选政策）**：在授权 h1_tuning worlds 上选出并在 g3_holdout 上未重调验证；授权作为进入未来 Q2 正式评估的候选政策。**不是 Q2 最终推荐、不是论文结果、不证明全局最优、不是管理结论**；不发布其调优 mean T 作为 Q2 结果。
- **G3 accepted 范围（CR-V3.1）**：C06（full）/C07（诊断层）/C13/C14/C15（G3 接口/重置层，Q3 七 K 未开始）/C16（分离层）/C17（full replay 层）/C18/C26 = PASS；C24（仪表/数据收集能力）= PASS；**C23/C25/H2 准入不声明 PASS；H2 仍未实现且未授权**。
- **Q2 formal / H2 / Q3 / Q4 保持 NOT STARTED**；论文正式 Q2 数字 = NOT AVAILABLE；下一阶段需新 Human Gate。
- **CURRENT_STATE 清理**：移除 stale active 措辞（"当前正在做：G2"、"不冻结预防更换阈值"、"只有 G2 … 才进入 G3"、"等待 Human Gate"、G3 Macro Gate PASSED 等待字眼）与重复 G3 bullet（状态/预算/禁止行）；更新当前边界（G3 = PASS/ACCEPTED、tau_pm 候选、Q2 formal/H2/Q3/Q4 NOT STARTED、next phase 需新 Human Gate）。
- **KNOWN_NONBLOCKING_DOCUMENTATION_FOLLOWUP**：G3-SPEC-V1.0 `approval_gate` 保留历史冻结阶段措辞"本阶段仍不实现 random DES"，而同一冻结治理随后授权了 Pilot #2 实现。分类 **STALE_FREEZE_STAGE_WORDING_ONLY**；不影响数学语义/实现行为/hash/tests/accepted 结果/G3 PASS；**不修改 G3-SPEC-V1.0**（避免 accepted 证据链 spec-hash/provenance 失效），保持 spec byte 不变。
- **无数学/代码/spec/证据变更**：本轮仅 3 个治理文件（CURRENT_STATE.md、CHANGELOG.md、07_AI使用记录/AI使用日志.md）；无结果再生成。

### 影响与边界

- Whole G2 = PASS；G3 = PASS / ACCEPTED；G3-SPEC-V1.0 = ACCEPTED；Pilot #2 = COMPLETED AT MACRO STOP。
- H1/Q2 formal evaluation = NOT STARTED；H2 = NOT STARTED / NOT AUTHORIZED；Q2 FORMAL = NOT STARTED；Q3 FORMAL = NOT STARTED；Q4 = NOT STARTED。
- **Pilot #2 绝对停机**：不启动 Q2 formal、不运行 q2_formal 命名空间、不生成正式 T/S/PL/PW/YXB、不实现 H2、不选 rollout M、不启动 Q3、不枚举 K、不启动 Q4、不写论文正式数字。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G3 MACRO L3 PASS — PILOT #2 COMPLETED AT MACRO STOP`

### 修改

- **G3 Macro L3 终审 = PASS / HIGH**（commit 见下）：
  - reviewer = `G3_MACRO_L3_REVIEWER`（workflow 派发恰 1 个 fresh child，无孙级）；session `b0f56d04-90aa-4ed8-a4bd-b5b7847f9a8c`，**runtime 机械验证 = deepseek-official / deepseek-v4-pro / high**（request/header + request/context + assistant source 三处一致）；freshness = VERIFIED、read_only = VERIFIED。
  - 审阅 16 项全 PASS：key_schema/寿命再生/H1+C26/C16 分离/C06 oracle/C17 replay/C18 活性/C24 仪表/§16 无 CI tie/S7 run/S8 run/S9 evidence/范围边界/YELLOW 修复×2/GREEN 修复；**G3 全套 302 tests OK（skipped=1）**。
  - 范围泄漏检查：无 Q2 formal 数字、无 H2、无 K 推荐、无论文；工作树干净；问题契约/CR-V3.1/数学模型/G2 accepted 未被 G3 链修改。
  - 报告落文 `01_审计/MACRO_REPORT_G3_L3.md`。
- **PILOT #2 = COMPLETED AT MACRO STOP**：S1-S9 全部完成（S1 `5a437dc`、S2 `7ccb550`、S3 `6418818`/`d88c7a3`/`617722e`、S4 `d88c7a3`、S5 `9a2b192`/`617722e`、S6 `2fdd332`、S7 `5b70446`、S8 `fad658f`、S9 `f279ae6`）；**无条件停机回 Human Gate**。

### 影响与边界

- G3 Macro Gate = PASSED（等待 Human Gate 接受）；终态标记 `G3_MACRO_L3_PASS_WAITING_FOR_HUMAN_GATE`。
- H1 formal / H2 / 100-device formal Q2 / Q3 formal / Q4 = NOT STARTED；Q2 formal/Q3/H2 非授权。
- 软墙钟 4h / 硬墙钟 8h 预算：已到达 Macro Stop，不再消耗。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G3 S9 EVIDENCE PACKAGE COMPLETED`

### 修改

- **S9 immutable evidence package 完成**（commit `f279ae6`）：
  - 新增 `04_代码/scripts/run_g3_evidence_v1.py` + `04_代码/tests/test_g3_evidence_v1.py`（11 tests，G3 全套 299 PASS）。
  - run `run_20260814T180658183615Z_fc3fe3e6`（INDEX_OK）：聚合 15 个 G3 源码文件 hash、task package/parameters/问题契约 hash、9 个 run 目录（tuning 6 + holdout 3）全部 file_hashes.sha256 复核一致、git 链、环境版本、命令。
  - **accepted = S7 tuning `01b7c7e7` + S8 holdout `020bc637`**；7 个失败/被替代 run（5 个 VALIDATION_FAILED tuning + 2 个 C07 方法缺陷 holdout）保留不可变并标注 superseded。
  - S9 仅聚合/校验，不重新生成任何仿真数字；G3 数据均标非 Q2 正式。

### 影响与边界

- Pilot #2 S1-S9 全部完成；下一步 **G3 Macro L3（fresh verified Pro/high 终审）**，之后无条件停机。
- 软墙钟 4h / 硬墙钟 8h 预算继续适用；Q2 formal/Q3/H2 非授权。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G3 S7 TUNING + S8 HOLDOUT COMPLETED`

### 修改

- **S7 H1 tuning（C26）完成**（修复后引擎/checker 重跑，commit `5b70446`）：
  - run `run_20260814T174022592173Z_01b7c7e7`（namespace=h1_tuning、master_seed=1、20 共享 CRN worlds、100-device 批次；G3 调优数据，非 Q2 正式）。
  - 粗网格 {120,144,168,192,216}+NO_PM_BEFORE_MANDATORY → 粗胜者 tau_pm_192（mean T 精确最小）→ G3-DEC-02 局部细化 {180,186,198,204} → **FINAL H1 CANDIDATE = tau_pm 198h**（mean T=3323/4h=830.75h=3323/96 天、mean PM=15/4）；C06/C17 全候选 PASS，VALIDATION=PASS。
  - 旧失效中间 run（`b9fe7d80`/`33da177a`/`09e7d0b7`/`09d2992c`/`48028e83`）保留不可变（发现 A/B 修复前产物）。
- **S8 holdout（G3-DEC-04 + C07）完成**（commit `fad658f`）：
  - run `run_20260814T180238855262Z_020bc637`（namespace=g3_holdout、master_seed=2 独立 seed 池、100 独立 100-device 批次、冻结 tau_pm=198h；G3 holdout 数据，非 Q2 正式）。
  - **C06/C17：100/100 批 PASS**；C07 四格烟测 flagged=7/100（Binomial(100,0.05) 预期 5，正常）、investigate=False；经验事件级 lambda mean=9.76 vs 解析锚 9.6785（相对偏差 0.8%）；C24 仪表聚合输出。
  - **C07 统计方法两处缺陷已调查并修复（GREEN 级，`01_审计/RED_EVIDENCE_G3_S8.md`）**：① GE 小期望单元（N·p=0.0815<<1）卡方不适用 → GE 移出 X² 作单独诊断；② 初版统计量用 `Σ(n-Np)²/(Np(1-p))` 非 Pearson 形式，对 GP(p≈0.925) 放大 ~13 倍致 flag 率失真 → 改标准 Pearson `Σ(n-Np)²/(Np)`（GP/BP/BE、2df）。修复后同批数据 flagged 15→7。未改任何冻结契约/锚/语义/代码路径；holdout 绝不重调。
  - 修复前 run `eba82d4b`、`1dfbec68` 保留不可变（C07 方法缺陷产物，非 accepted）。
- 新增 `04_代码/scripts/run_g3_holdout_v1.py` + `04_代码/tests/test_g3_holdout_v1.py`（23 tests）；G3 全套测试 288 PASS。

### 影响与边界

- **FINAL H1 CANDIDATE = tau_pm 198h（冻结值）**：仅用于 holdout/后续 G3 验证，非 Q2 正式推荐。
- holdout 结果未用于重调（禁 holdout 破 tie / 禁因 holdout 改策略）。
- G3 状态：S1-S8 完成；S9 evidence package 与 G3 Macro L3 待执行；G3 Macro Gate 后无条件停机。
- 软墙钟 4h / 硬墙钟 8h 预算继续适用；Q2 formal/Q3/H2 非授权。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-04 REBIND TO SPEC V1.0`

### 修改

- **G2-04 implementation/evidence rebind 到 G2-04-SPEC-V1.0 完成**（WHOLE_G2_GOVERNANCE_AND_EVIDENCE_REPAIR Phase B）：
  - diff audit：checker core（des_checker_v1.py）完全符合 G2-04-SPEC-V1.0（checker_interface 合规、replay_acceptance 18 项全覆盖、fault_injection 族①②④ checker 真实捕获）；**checker core changed = NO**。
  - runner `04_代码/scripts/run_g2_whole_v1.py` 机械修改：task_package_ref → `G2-04-SPEC-V1.0`；spec_hash → G2-04 实际 hash `20e173c2…`；code_snapshots 增加 G2-04 spec + upstream G2-03-SPEC-V1.0.2（8 条）；frozen/ 写 `task_package_G2_04.yaml` + `task_package_G2_03_upstream.yaml`；manifest notes 记录 task_package / upstream_frozen_dependency（`eebdaa94…`）/ fault_injection 族③ = G2_INTERFACE_ONLY / G3_FULL（G2 无 RNG，未伪造随机测试）/ 族①②④ = checker-caught FAIL。
  - **governed formal run = `run_20260814T114143591701Z_32913efa`**（checker 14/14、crosscheck 14/14、exit 0、file_hashes 匹配）。
  - rerun 全 PASS：DES 27 / CP-SAT 72 / crosscheck 24 / checker 12 / one-command exit 0。
  - **G2-04 = IMPLEMENTATION_AND_VERIFICATION_COMPLETED_CANDIDATE**。
- 旧 formal runs `...032dfffc`、`...81563471` = **PRE_G2_04_SPEC_HISTORICAL_CANDIDATE**，保留不可覆盖。
- **Whole G2 = NOT PASS**（fresh qualifying Pro/high Macro L3 pending）。

### 影响与边界

- 无语义变化（INVALIDATION_REPORT：changed_semantics=NO）；未改 checker/tests/fixtures/schemas/specs/CR-V3.1。
- G3 / H1 formal / H2 / 100-device / Q2 / Q3 / Q4 = NOT STARTED。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G3-SPEC-V1.0 FROZEN / PILOT #2 ACTIVE`

### 修改

- **G3-SPEC-V1.0 冻结**（FROZEN_FOR_IMPLEMENTATION）：Human Gate G3_SPEC_DRAFT CONDITIONAL PASS → Phase A 落文全部决策（G3-DEC-01 粗网格 120/144/168/192/216 + NO_PM_BEFORE_MANDATORY、DEC-02 ±12h/6h 单轮细化、DEC-03 调优 20 配对批次、DEC-04 holdout 100 批次、DEC-05 六命名空间 + 物理键禁执行元数据 + 流键结构、DEC-06 paired bootstrap+Bonferroni B=10000/95%、DEC-07 软 4h/硬 8h）→ Phase B fresh verified Pro/high 终审（`G3_SPEC_FINAL_L3_REVIEWER`，session `f5550518-edfa-48cc-9213-da37ffd789bd`，request.config 机械验证 deepseek-v4-pro/high）overall=PASS/confidence=HIGH/implementation_ready=YES → 冻结。decision_required=[]；终审 5 条 NOTE 已闭合（决策落文、NO_PM 记号、canonical 键序冻结、C14 240h 兜底、pilot 职责）。
- **AUTOPILOT PILOT #2 = ACTIVE**：G3 实现（S1 key_schema → S2 寿命/再生 → S3 随机 DES+H1 → S4 C06 oracle → S5 C17 replay → S6 C16 实验分离 → S7 H1 tuning（C26）→ S8 holdout → S9 evidence）至 **G3 Macro Gate 无条件停机**。
- **CURRENT_STATE**：G3 = IMPLEMENTATION ACTIVE、Pilot #2 ACTIVE；H1 formal/H2/100-device formal Q2/Q3 formal/Q4 均 NOT STARTED。
- **G3 tuning/holdout 100-device 批次属授权验证/调优，与 Q2 FORMAL 明确区分**；Q2 formal/Q3/H2 非授权。

### 影响与边界

- 软墙钟 4h / 硬墙钟 8h（hard cap 无条件停止）；禁止发布/冻结 Q2 正式数字、写论文、实现 H2、枚举 K、推荐 K。
- G3 Macro Gate 后无条件停机；Pilot #2 结束需新 Human Gate。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `WHOLE G2 FINAL PASS`

### 修改

- **Whole G2 = FINAL PASS（Human Gate 2026-08-14 正式接受）**；**U0 = CLOSED、U1 = CLOSED**。
- **U1（evidence/provenance repair）闭合**：G2-01 clean reissue `run_20260814T130221390333Z_8babb503` accepted；G2-02 provenance-clean reissue（`G2-02-SPEC-V1.0.5`，run `run_20260814T130947069958Z_4bb92eda`）accepted。
- **U0（qualifying Macro reviewer route）闭合**：reviewer = `G2_WHOLE_MACRO_L3_WORKFLOW_PRO_REVIEWER`；child/session = `8abb6c32-9dc8-444c-ae3e-f8d9f062f7b5`；runtime 由 Harness session JSONL request.config 机械验证 = deepseek-official / **deepseek-v4-pro** / high；overall_decision = **PASS**、confidence = **HIGH**；freshness = VERIFIED、read_only = VERIFIED。先前 Flash reviewer 保留为 **ADVISORY_NONQUALIFYING_MACRO_REVIEW**（未用作 qualifying acceptance）。
- **G2-03 / G2-04 promotion to accepted**：G2-03（deterministic DES + 独立 CP-SAT + DES/CP-SAT/hand 三方对拍，spec V1.0.2）与 G2-04（独立 replay/checker/evidence，governed run `32913efa`，spec V1.0）均在 Whole G2 Macro L3 + Human Gate 下 PASSED / ACCEPTED。
- **G2 registry（G2 层 accepted）**：C01-C05、C06（G2 最小层）/G3 full DEFERRED_BY_REGISTRY、C08-C12、C16（G2 键骨架层）/G3 experiment DEFERRED、C17（G2 最小层）/G3 full DEFERRED、C18-C21、C27（document part）——未过度声明 scope，G3-only/full 层全部保留 DEFERRED。
- **KNOWN_NONBLOCKING_DOCUMENTATION_FOLLOWUPS（3 项，不阻塞、不重开 G2）**：① C20 manifest 措辞略强于独立负面注入证据；② canonical 序列化字节计数呈现有次要文档级差异；③ G2-03 spec 一处 provenance 引用措辞。全部不影响数学/冻结语义/DES/CP-SAT/checker 结果/accepted hashes/Whole G2 PASS；本 state-landing 不授权修复。
- 本条目为 state-landing only：无数学/代码/证据变更，无 settings 变更，无结果再生成。

### 影响与边界

- AUTOPILOT PILOT #1 = COMPLETED AT MACRO STOP；G3 = NOT STARTED；H1 formal = NOT STARTED；H2 = NOT STARTED；100-device formal = NOT STARTED；Q2/Q3/Q4 formal work = NOT STARTED。下一阶段（G3 等）需新 Human Gate。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-01 CLEAN REISSUE + G2-02 V1.0.5 PROVENANCE REBIND`

### 修改

- **G2-01 evidence clean reissue**（commit `13d9edf`）：新 run `run_20260814T130221390333Z_8babb503`（LF-clean、inventory 26/26、数学 payload 与历史 `f1290916` 逐字段一致、归一化 byte-identical；差异仅 request_id.run_id，Human Gate OPTION A APPROVED）。旧 run `f1290916` 保留为 HISTORICAL_INVALIDATED_EVIDENCE（HASH_INVENTORY_MISMATCH）。G2-01 runner/checker 增加 evidence-finalization LF newline（非数学）。
- **G2-02-SPEC-V1.0.5 冻结**（commit `495bd1a`）：provenance-clean upstream rebind only（OPTION B APPROVED）；upstream 整体切换至 clean G2-01 `8babb503`；数学/schema/fixture/容差不变。
- **G2-02 provenance-clean reissue**（commit 见本条目）：governed run `run_20260814T130947069958Z_4bb92eda`（checker 双 PASS、inventory 37/37、frozen upstream 与 clean G2-01 一致；新旧 response canonical projection 逐字段一致 + byte-identical）。旧 run `52f4ebc4` = HISTORICAL_MATHEMATICALLY_VALID / PROVENANCE_SUPERSEDED_FOR_CURRENT_CHAIN。
- 中间失败 run（`ef19a3a4`/`ddbcf433`/`05620ece`）保留；`ddbcf433` stderr 纯 CRLF→LF 行尾归一化（内容不变，diff --check 硬门）。
- 数学/数值无任何变化；INVALIDATION_REPORT 已更新。

### 影响与边界

- Whole G2 仍 NOT PASS（qualifying Pro/high Macro L3 pending）；G3/H1/H2/100-device/Q2/Q3/Q4 NOT STARTED。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `WHOLE G2 MACRO STOP / GOVERNANCE REPAIR AUTHORIZED`

### 修改

- **AUTOPILOT PILOT #1 到达 Macro Stop**（Human Gate 审阅 Macro Report 后裁决：WHOLE G2 = BLOCKED_PENDING_GOVERNANCE_REPAIR；授权有界 `WHOLE_G2_GOVERNANCE_AND_EVIDENCE_REPAIR`，不重新启动 AUTOPILOT，不扩大到 G3）。
- **G2-04 implementation candidate 已存在**（commit `961b64d`：des_checker_v1.py、test_des_checker_v1.py、run_g2_04_verification_v1.py、run_g2_whole_v1.py）；**formal candidate 已存在**（CRLF run `...032dfffc` commit `2cee5e6`；LF run `...81563471` commit `f0daa43`）。
- **prior Macro review = ADVISORY_NONQUALIFYING**：原 Whole G2 L3 reviewer 模型来源为 INHERITED（报告 deepseek-v4-flash/high），exact runtime model 未独立验证，不满足 Pilot #1 D/Macro = fresh deepseek-v4-pro/high 冻结要求；其结论不得作为 formal Whole G2 D/L3 acceptance。
- **missing G2-04 task package 由 Human Gate 发现**（BLOCKER-A）：`08_项目管理/任务包/` 原只有 G2-01/G2-02/G2-03；AGENTS.md 要求运行前必须有冻结任务包；G2-03-SPEC-V1.0.2 ownership_draft 明确 des_checker_v1.py 属 G2-04 任务包。既有 G2-04 实现/formal candidate 保留为历史 candidate，不能直接作为 governed accepted evidence。
- **BLOCKER-B**：原 Macro reviewer 不满足 D/Macro runtime mapping（fresh deepseek-v4-pro/high 可独立验证）。
- **G2-04-SPEC-V1.0 已冻结**：`08_项目管理/任务包/G2-04_独立日志重放与WholeG2证据.yaml`（status FROZEN_PENDING_REBIND；scope=C06 G2 最小/C16 G2 键骨架/C17 G2 最小/C19/C20 G2 最小/C21 G2 骨架 + 对 G2-03 C08-C12/C18 的 replay 复核；checker 冻结接口；replay acceptance；fault injection 明列族；Whole G2 evidence interface 绑定 G2-04-SPEC-V1.0 + upstream G2-03-SPEC-V1.0.2）。
- **旧 formal runs 保留**：`...032dfffc`、`...81563471` 标 PRE_G2_04_SPEC_HISTORICAL_CANDIDATE，不删除、不覆盖、不冒充 governed current evidence。
- **Whole G2 仍 NOT PASS**；G3 未授权。

### 影响与边界

- 修复阶段允许修改：`08_项目管理/任务包/G2-04_独立日志重放与WholeG2证据.yaml`、`CURRENT_STATE.md`、`CHANGELOG.md`、`07_AI使用记录/AI使用日志.md`（Phase A）；Phase B 仅机械 rebind runner/evidence metadata；Phase C fresh qualifying Pro/high Macro L3。
- 不写 Whole G2 PASS / G2-04 accepted / formal evidence accepted（Phase A 阶段）。
- G3 / H1 formal / H2 / 100-device / Q2 / Q3 / Q4 = NOT STARTED。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-03 S3 THREE-WAY CROSSCHECK PASS`

### 修改

- **G2-03 S3 三方机械对拍 = PASS**（commit `add95095c31d7743d70554847b8288f59584c70f`）：accepted DES（`31b0bff`）vs independent CP-SAT（`689d0c2`）vs frozen hand 在 14 个 concrete fixture（F1-F12 + F4b + F9b）上全部一致，0 diffs。
- 新增比较器 `04_代码/tests/three_way_crosscheck_v1.py` + `04_代码/tests/test_three_way_crosscheck_v1.py`（24 项；tick↔Fraction 精确换算、错误注入证明非恒 PASS、重复运行确定）。
- F8 K9 三方对齐：T=84 ticks（14h）；d3 B1 finish=51 ABNORMAL；B2 release=51/start=54/finish=66/attempt=2；E 66..84；YXB 只读断言 5/12、4/9、5/12、1/2。
- 全量回归 123/123（DES 27 + CP-SAT 72 + crosscheck 24）。
- **CR-V3.1/C08 确定性小例对拍子项 = 闭合候选**；G2-03 收口完成（candidate），G2-04 进入 ACTIVE。
- 无 spec/fixture/DES/CP-SAT 修改；比较器自身 2 处 bug 已修复（字段映射、行 key 笔误），未触碰被比较方。

### 影响与边界

- G2-03 overall 最终判定待 Whole G2 L3；G2-04 = ACTIVE；Whole G2 = NOT PASS；G3/H1/H2/100-device = NOT STARTED。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `AUTOPILOT PILOT #1 BOOTSTRAP`

### 修改

- **AUTOPILOT PILOT #1 正式启动（Bootstrap）**：`AUTOPILOT-PLAN-V1.1-FINAL` 落库为 `08_项目管理/全流程自动推进计划_AUTOPILOT-PLAN-V1.1.md`（原样全文，未删减）。授权起点候选 `689d0c253be63a889c163b2e473f9226b0899c3e`；授权终点 = Whole G2 Macro Gate（无论 PASS/FAIL 均无条件停机）。
- **D/E 角色抽象**：治理层只冻结能力角色（E=Execution、E2=Independent Execution/Checker、D=Decision/Reviewer、D-red=independent D reviewer），不再把具体 GPT 产品名写死为 L0–L4 唯一路由。Pilot #1 runtime mapping 冻结：E/E1/E2 = `deepseek-v4-flash`（high），D/YELLOW、D/Macro = `deepseek-v4-pro`（high）。同步更新 `AGENTS.md`（SA-V1.0 段）与 `08_项目管理/模型分级与任务路由规则.md`（§2.1/路由优先级/L2 行）。
- **L2 放行规则**：旧规则“所有 L2 必须 D 审阅”废止，替换为风险驱动 L2-GREEN（10 条条件全满足时 E1+E2+mechanical acceptance 自动放行）/ L2-YELLOW（fresh D/Pro-high 只读，最多 1 次 D adjudication + 1 次受限 patch/rebind）/ L2-RED（涉及题意/公式/状态转移/指标/容差/搜索空间/oracle 真实性/强结论 → 立即 Human Gate，0 次静默修复）。
- **旧 V1.0 草稿归档**：`08_项目管理/全流程自动推进计划_待审阅.md`（SHA-256 `8903f98622531727f11775b0171e9d997541af45309bb3e42c13a265d3db9113` 校验一致）无损归档至 `99_归档/自动推进计划/AUTOPILOT-PLAN-V1.0_待审阅_20260814.md`；`KNOWN_TOLERATED_UNTRACKED` 临时例外取消。
- **S1/S2 状态落文**：S1 deterministic DES = ACCEPTED（`31b0bff`）；S2 independent CP-SAT oracle = COMPLETED（`689d0c2`），待 S3 三方对拍闭合 C08；G2-03 overall = NOT PASS。
- 本条目即 **Bootstrap 治理 commit**（message `activate AUTOPILOT Pilot #1 governance`）。

### 影响与边界

- Pilot #1 自动范围：S3 三方对拍 → G2-03 收口 → G2-04（replay/accounting/keyed/isolation/fault injection/reproducibility/one-command）→ Whole G2 formal candidate evidence → fresh D/Pro-high Whole G2 只读 L3 → Whole G2 Macro Gate → 停机。
- 禁止自动进入：G3 / H1 formal / H2 / 100-device formal run / Q2 正式结果 / Q3 K 推荐 / Q4 建议 / G7 提交。
- runtime budget 来自 launch parameters（soft=¥10、hard=¥20、timebox=NONE），达到 hard budget 立即停机，不得自行提高。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-03 S1 FINAL PASS / S2 CP-SAT ACTIVE`

### 修改

- **G2-03 S1 deterministic DES baseline = FINAL PASS / ACCEPTED**（Human Gate 2026-08-14）。
- spec = `G2-03-SPEC-V1.0.2`；accepted S1 commit = `31b0bffb72d6b805ae313ddb9e5e0ae9a83c16ab`（V1.0.2 rebind）。
- 验收记录：24 semantics implemented；F1-F12 family + F4b + F9b PASS；F8 K9 PASS（T=14）；py_compile PASS；unittest 27/27 PASS；main DES stdlib-only；D E2 timing / SEM21 / SEM23 PASS。
- historical `a515960cfd4f0c14e8c1952a558a56a59f87ef9f` retained（pre-V1.0.2 implementation candidate，不得 reset/revert/amend/force-push）。
- **G2-03 S2 独立 CP-SAT oracle = IMPLEMENTATION ACTIVE**（本轮授权实现；OR-Tools 9.15.6755 仅 CR-V3.1/C08 独立验证侧，不传播到 main DES/G3/H1/H2/100-device formal run）。
- G2-03 overall = NOT PASS（CP-SAT oracle 尚未实现/验收，C08 三方对拍未闭合）；无 formal evidence。

### 影响与边界

- G2-04 = NOT STARTED；DES formal evidence = NOT STARTED；100-device formal run = NOT STARTED；G3 / H1 formal / H2 = NOT STARTED。
- 下一授权：S2 CP-SAT oracle 实现 + 机械验收；最终 DES-vs-CP-SAT-vs-hand 三方对拍待后续 Human Gate。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-03-SPEC-V1.0.2`

### 修改

- **G2-03-SPEC-V1.0.2 L3 correction（fixture / executable event-order semantic correction）**：来源 = `G2_03_S1_FIXTURE_SEMANTIC_ADJUDICATOR`（fresh Pro/high L3 adjudication，overall=SPEC_AND_IMPLEMENTATION_PATCH_REQUIRED，confidence=HIGH）+ 2026-08-14 Human Gate final ruling。**core process semantics unchanged**，但以下发生冻结澄清与修正：
  - **F3 corrected**：重构为 B 首败（B1 ABNORMAL@2.0、B2 retest 2..4 与 A/C 0..2.5 在 [2,2.5) 真实并行），T=8→7；删除旧 A-abnormal 构造。
  - **F4 restored + F4b**：F4 恢复 t*=7.5 跨装置同刻 PASS（d1 A2 与 d2 C2 严格同刻，先结算后退出，T=10.5、S=1、PW=1）；F4b 为取消分支 subcase（B2 二次异常@6.0 退出，取消运行中 A2/C2，elapsed=1h each，无观测）；删除错误 NOTE『literal alignment unreachable』。
  - **F7/F9/F10 SEM-21 corrected**：batch_size=3、preloaded=[1,2]（不再 batch=2+preloaded=[1]）；F7 T=12（d3 A/C 6.5..9.0 恰班末完成）；F9 T=12（d3 entry 6.5）；F10 T=11.5（d3 entry 6.0）。
  - **F9b added for SEM-23 coverage**：batch=4、preloaded=[1,2]；[6.0,6.5) bay1 TRANSPORT_IN ∥ bay2 TRANSPORT_OUT 并发运输；预计 T=15（实现者须按冻结规则运行确认，不得手改）。
  - **D timing clarified to E2 before E release**：D 不在 E ACTIVITY_START 生成；canonical_D_creation_time = A/B/C 全 PASS 的同一 timestamp = E logical release timestamp；D_CREATED.seq < E TASK_RELEASE.seq；E 等待期间 D=CREATED；同刻 second abnormal exit 不得生成 D；E retest 不重新生成 D；early exit 保持 not_created。
  - **EMPTY edge case frozen**：BayStatus.EMPTY 仅允许 batch_size==1 或显式终止设计；batch_size>=2 必须 preloaded=[1,2]，不得用 EMPTY 规避 SEM-21。
  - **shift ordering retained**：E2 → SHIFT_CHANGE → F；完成永远先于换班（L3：CURRENT_IMPLEMENTATION_CONFORMANT，NO SPEC CHANGE REQUIRED 之外补 E2 显式步骤）。
  - **0.5h overlap log representation clarified**：真实占用 [start,start+0.5h)，IN 子相为零时长日志表示，非额外 0.5h IN。
  - fixture_family_count=12（F4b/F9b 为 subcase，不注册 F13/F14）。
- **`a515960cfd4f0c14e8c1952a558a56a59f87ef9f` 保留**为 historical S1 implementation candidate（基于 V1.0.1，需 V1.0.2 rebind；不是 accepted baseline）。

### 影响与边界

- S1 implementation 需按 V1.0.2 rebind（Phase B）；S1 是否最终 accepted 待下一 Human Gate。
- 未实现 CP-SAT / checker / runner；无 formal evidence；G2-04 / G3 / H1 formal / H2 均 NOT STARTED；whole G2 Gate != PASS。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-03 IMPLEMENTATION ACTIVE`

### 修改

- **Human Gate approved `G2-03-SPEC-V1.0.1`** 并授权进入 G2-03 确定性最小并行 DES 实现阶段（仅状态切换，本轮未写任何代码）。
- V1.0 freeze commit 保留：`cecaa97e21d1a7f70a61e96455deabc15aded783`（message `freeze G2-03 deterministic DES spec v1.0`）。
- V1.0.1 仅修正 governance/documentation consistency（commit `37150f2af0b047725b84ef6fa802638d329f1447`，message `correct G2-03 spec v1.0.1 governance consistency`）：`draft_notes` → `freeze_notes`；删除非法 `CR-V3.1/C28` 占位；stdlib-only 政策表述收敛为任务包自身边界；`out_of_scope` 按 stage 修正（C18 的 G2 部分明确 IN_SCOPE，C06/C16/C17 保留 G2-04 reservation）；H1 wording 修正为"不构成 H1 正式实验/参数冻结"。
- **无数学/事件语义变更**：24 semantics、same_timestamp_event_order、FCFS 键、F1-F12、K9、CP-SAT oracle 14 条边界、release_independence（exogenous/endogenous、no_des_derived_input、FCFS independent encoding）、schemas/event_log_contract/ownership_draft、G2-03/G2-04 split 全部不变。
- **CP-SAT 依赖未变**：OR-Tools 9.15.6755（仅 C08 独立 oracle）、Python 3.12.10、10 min/tick、6 ticks/hour；主 DES stdlib-only。
- `CURRENT_STATE.md` 切换：**G2-03 IMPLEMENTATION ACTIVE**（implementation authorized = YES；completed = NO；DES formal evidence = NOT STARTED）。

### 影响与边界

- 无任何 `04_代码` 文件创建；未运行 DES / CP-SAT fixture / formal evidence；未启动 G3 / H1 formal experiment / H2 / 100-device formal run。
- 不得宣称 G2-03 PASSED、G2 COMPLETE、G3 allowed 或 Q2 formal result available；whole G2 Gate != PASS；G2-04 = NOT STARTED。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-02 D Acceptance PASS`

### 修改

- **G2-02 / Q1 概率与质量解析链正式验收**：D/L3 Semantic Acceptance = PASS（confidence HIGH）。
- 任务包：`G2-02-SPEC-V1.0.4`；accepted run_id：`20260814T062114478293Z_52f4ebc4`；successful evidence commit：`700898bfabbf4cf169049baf91084f79cc61a488`。
- accepted checks（G2-02 范围）：`CR-V3.1/C01、C02、C03、C04、C05、C19、C21、C27` 全部 PASS。
- evidence SHA：run_manifest `b7219b85aede18857611075a059d609dca00bd0f4bb3637939a4d70c12c5250d`（`05_结果/G2/run_20260814T062114478293Z_52f4ebc4/run_manifest.json`）；single check_report `092c4e1f468882ff6a6bef6a711df836f4d5f74626404be56ab3cb78e54130e6`；chain check_report `c761e8281baf9c58d46eb30e2acabdf504fae26a125e9cf8a29547f976028cf6`；file_hashes `f8145e754cf5f279c3e45dcca861113e8d247523d2dddcb06af0189238bb7aba`。
- 历史失败证据保留（未修改）：`run_20260814T043709752483Z_99f602bd`（V1.0.3 frozen runtime dependency snapshot gap，V1.0.4 快照 9→10 + RUNNER rebind 闭合）、`run_20260814T053311144723Z_a694e8f9`（E1 route_agreement 输出代表值而非偏差，L3 adjudication + E1 correction 闭合）。

### 影响与边界

- **whole G2 Gate = NOT PASS**；DES = NOT STARTED；G3 = NOT STARTED；H2 = NOT STARTED；H1/R1 仍为强制基线，H2 仅条件候选。
- 未发布论文正式数字；`G2-02 / Q1` 正式运行结果仅在本题 G2-02 范围内 accepted；Q2/Q3 尚未开始。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-02-SPEC-V1.0.4`

### 修改

- 任务包 `G2-02_Q1概率与质量解析链.yaml` 由 `G2-02-SPEC-V1.0.3` 升级至 `G2-02-SPEC-V1.0.4`，经人工 Gate 裁决（FROZEN_RUNTIME_DEPENDENCY_SNAPSHOT_GAP，批准升级）。
- **runtime dependency snapshot closure correction only**：首次 V1.0.3 formal canonical attempt（failed run_id `20260814T043709752483Z_99f602bd`）暴露 frozen/code 快照缺少 G2-01 求解器 `04_代码/main_model/observation_calibration_v1.py`（E1 合法依赖，E1 allowed_read_paths 早已含该文件），正式 canonical 从 frozen/code 执行 E1 时 import 失败（E1 exit 4）。本修订：RUNNER allowed_read_paths 增加该文件；evidence_package_contract.exact_layout 增加 `frozen/code/04_代码/main_model/observation_calibration_v1.py`；正式 code/test 快照数量 9→10（solver 与其余冻结代码同执行 source-before=snapshot=source-after 守卫）。solver 静态 import 审计确认仅标准库（SINGLE_FILE_CONFIRMED）。
- 失败证据已作为不可变 evidence 提交并推送：commit `472ed00a3d6a41f586ce2fe48ec72deb4f0d3eae`（g2-02-impl）。

### 影响与边界

- **math_semantics_changed = NO**；**schema_changed = NO**（SHA 保持 `0bb93b12…`）；**fixture_changed = NO**（SHA 保持 `13efa773…`）；parameters 与 upstream 哈希均不变。
- S1/S2 数学实现仍保持已验证；RUNNER 需后续 V1.0.4 rebind；不得称 G2-02 PASS；S4/D acceptance 未完成；下一次 canonical 必须等待 runner V1.0.4 rebind + 人工 Gate。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-02-SPEC-V1.0.3`

### 修改

- 任务包 `G2-02_Q1概率与质量解析链.yaml` 由 `G2-02-SPEC-V1.0.2` 升级至 `G2-02-SPEC-V1.0.3`，经人工 Gate（NA Schema L3 reviewer PASS）批准。
- **NA/null interface contract correction**：`lambda.na=true` 时 `lambda.main` 四叶、`lambda.sum`、`lambda.max_abs_deviation` 必须全为 null（NA 不得伪装为数值 0；schema 新增 `nullableDecimalProbability`/`nullableDecimalSigned` 并以 if/then 严格强制 na 与 null 等价）；`route_agreement.lambda_A..D` 在 lambda=NA 时（谓词=na）为 null；`tilde` 四叶及 `route_agreement.tilde_*` 在 `q_E=0` 时为 null；不新增 `tilde_na` 布尔。
- 澄清：chain 语义 `e_max_E` 为 NOT_APPLICABLE（E2 仅 single 语义断言数值，E2 代码更新待后续 rebind）；infeasible/indeterminate 下游保持"省略/absent（fixture null=absent by construction）"契约。
- schema SHA：`94157e00…` → `acc9d641…` → `0bb93b12…`（q_E 零值词法在 schema 契约层归一化：零分支使用 `^0(?:\.0+)?$`，非零分支使用其真补集 pattern，覆盖 `"0"/"0.0"/"0.00"/"0.000000"` 等全部合法零字符串，不再依赖 `const "0"`；机械修正，不改变语义）；fixture SHA：`fadefced…` → `13efa773…`（O5 lambda 块补 `sum: null`、`max_abs_deviation: null`；O5 数学值不变）。

### 影响与边界

- 数学公式、q_E 定义、lambda 公式、`SD-G2-02-LAMBDA-ONCE`、tolerance 均未改变；canonical 非 NA 输出格式不变。
- S1/S2 现有实现需按 V1.0.3 重新 rebind（后续执行）；G2-02 未通过；S4/S5/S6 未开始；未运行 canonical；未 commit/push。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-02-SPEC-V1.0.2`

### 修改

- 任务包 `G2-02_Q1概率与质量解析链.yaml` 由 `G2-02-SPEC-V1.0.1` 升级至 `G2-02-SPEC-V1.0.2`，经人工 Gate 裁决（公式优先 / 修正 O5 fixture）。
- **frozen oracle bug correction**：`04_代码/tests/fixtures/q1_quality_oracles_v1.json` 案例 `O5_NA_lambda_beta1_single` 的 `E_rates.device_total_exit` 由 `169/512` 修正为 `1401/4096`（原值等于 `p_BE` 单项，遗漏 E 阶段假阳性退出分量 `Z_0·alpha_E^2=49/4096`）；冻结公式 `p_device_total_exit=p_GE+p_BE` 不变，O6 期望 `9/64` 不变。fixture SHA-256：`7f2cd3bc…` → `fadefced…`。
- 任务包内新增 V1.0.2 `revision_history` 记录；保留 V1.0.1 的 single-writer ownership 修正（`04_代码/scripts/run_g2_02_v1.py`、`04_代码/tests/test_run_g2_02_v1.py` 只归 RUNNER 所有，不恢复 E2 所有权）。

### 影响与边界

- 数学语义、公式、λ 裁决（`SD-G2-02-LAMBDA-ONCE`）、q_E 定义、schema、tolerance、E1/E2 算法要求、checker 隔离规则与 G2-01 上游证据均未改变。
- S1 因冻结冲突合规阻断（`BLOCKED_BY_FROZEN_SPEC`），等待按 V1.0.2 重新派单；S2 现有代码仅记为 `IMPLEMENTATION_CANDIDATE_PENDING_V1.0.2_REBIND`，未在当前冻结版本下正式验收。
- G2-02 未通过；S4/S5/S6 未开始；未运行 canonical；未 commit/push。

## 2026-08-14 / `STATE-2026-08-13-G2.4` / `G2-02-SPEC-V1.0.1`

### 修改

- 任务包 `G2-02_Q1概率与质量解析链.yaml` 由 `G2-02-SPEC-V1.0.0` 升级至 `G2-02-SPEC-V1.0.1`，经人工 Gate CONDITIONAL PASS 批准。
- 变更性质：`dispatch / single-writer ownership correction only`——E2 的 `allowed_write_paths` 移除两个 runner 实现文件（`04_代码/scripts/run_g2_02_v1.py`、`04_代码/tests/test_run_g2_02_v1.py`），该两文件只归 RUNNER 所有；E2 保留 checker 两份源码与两个 check_report 输出路径。
- 任务包内新增 `revision_history` 字段记录本修正；`CURRENT_STATE.md` 版本引用同步至 `V1.0.1`。

### 影响与边界

- 不改变任何数学语义、lambda 裁决、q_E 定义、schema、oracle fixture、tolerance、E1/E2 算法要求、checker 隔离规则或 G2-01 上游证据。
- 未运行任何 G2-02 数值实现，未启动 E1/E2/RUNNER；不得据此宣称 G2-02 已实现或已通过，不改变 G2 Gate 结论。
- 待人工批准后，方可按并行派单规划启动 E1 ∥ E2。

## 2026-08-13 / `STATE-2026-08-13-G2.4` / `G2-02-SPEC-V1.0.0`

### 修改

- 冻结 G2-02 任务包（Q1 概率与质量解析链）：q_E 闭式、E 核标定、终局四格、`E[S],E[PL],E[PW]` 与 `lambda` 两语义全链；三路线（闭式 / 16 状态枚举 / 吸收链）异源对拍与 E2 独立 oracle；`CR-V3.1/C01–C05,C19,C21,C27` 对应验收条件、极端参数 oracle 与不可行/不可识别传播规则全部写死。
- 新建 D 冻结契约物：`04_代码/src/schemas/q1_quality_v1.schema.json`、`04_代码/tests/fixtures/q1_quality_oracles_v1.json`（极端参数精确分数期望）。
- 人工裁决 `SD-G2-02-LAMBDA-ONCE`（选项 B）：`lambda`「每台至多一次」按该装置首次 E 有效真阳性计，与「仅初测」同期望 `1-β_E`；三种口径归一来源比例总体相等；已在 `03_模型/01_Q1概率与质量模型.md` 第 114 行落注。
- 修正 `03_模型/01_Q1概率与质量模型.md` 第 69 行 LaTeX 笔误（`qquad`→`\qquad`）。

### 影响与边界

- 尚未运行任何 G2-02 数值实现；`CR-V3.1/C03`、`C04`、`C05` 仍为 DEFERRED；canonical `q_E` 禁止猜测或手填。
- 不进入 DES、不进入 G3、不涉及 H2；任务包待人工批准后才派单 E1/E2/RUNNER。

## 2026-08-13 / `STATE-2026-08-13-G2.3` / `G2-01-SPEC-V1.1.11`

### 修改

- G2-01 观测核标定最小基线通过最终 L3 验收；`CURRENT_STATE.md` 不再声明“首个实现任务尚未执行”。
- `CR-V3.1/C01`、`C02`、`C19`、`C21` 仅在 G2-01 canonical A/B/C 标定子范围内记为 PASS。

### 不可变证据

- Run：`05_结果/G2/run_20260813T134251279572Z_f1290916/`
- 任务包：`G2-01-SPEC-V1.1.11`，SHA-256 `379402e3f69b3e9f1862a17bd7b7df9f605aac6d9449b3288ee88cd708d8745d`。
- `run_manifest.json`：SHA-256 `a083c4b1172ffba356106a08705722ebdbb590278ad157de3772dc3a19239823`。
- `single_test_unconditional_v1/check_report.json`：SHA-256 `411bff63a0dd42b7ef9810c6a03bf847c3e5e386f70b2c99c5c5b873c7c87765`。
- `standard_chain_v1/check_report.json`：SHA-256 `72c6783cdc400d63feb191f56ed8506176a9ac9d8529cf78e48d443122e4ca4d`。
- `file_hashes.sha256`：SHA-256 `4d0bacdbe49d37dd51b9c73dba4b88c29beb13f7fff78da46edb7d11c5f2f266`。

### 影响与边界

- G2-01 到此结束，其他 G2 项仍待闭合；不得据此宣布整个 G2 Gate 通过或进入 G3。
- `CR-V3.1/C03`、`C04`、canonical E 与 `q_E` 仍为 DEFERRED；禁止猜测或手填 `q_E`。
- 本记录不发布正式竞赛数字，不更新论文，也不改变其他检查状态。

## 2026-08-13 / `SA-V1.0`

### 修改

- 在项目 `AGENTS.md` 中增加子 Agent 调用纪律。
- 在模型路由规则中增加调用前公开标签、显式/继承模型的可验证性边界、脚本优先、禁止默认多级委派、单写者、checker 上下文隔离和调用后使用清单。
- 扩展执行模型派单模板，加入模型请求、reasoning effort、上下文方式、文件所有权、下级 Agent 权限及完成报告字段。

### 原因与影响

此前已有 D/E 和 L0–L4 任务路由，但未强制逐次公开子 Agent 的模型请求与继承状态。`SA-V1.0` 只增强调用透明度和审计，不改变数学口径、Gate 或检查注册表。

## 2026-08-13 / `STATE-2026-08-13-G2.2`

### 修改

- 在确认两个目录均无文件后，将空的 `04_结果/` 迁移为 `05_结果/`，将空的 `05_图表/` 迁入 `05_结果/figures/`。
- 新增结果目录规范与论文数字来源表；后续所有运行按不可变 `run_id` 建目录并绑定 manifest。
- 将 `CR-V3.0`、三轮评审响应和 V2 方案迁入 `99_归档/`，并记录旧路径、现路径和 SHA256；历史材料退出默认检索入口。
- 将数据审计与数据字典从机器数据层迁到 `01_审计/`；把 `08_项目管理/` 三份已迁移的长模型文档缩成兼容指针，消除重复正文。
- 为 `04_代码/` 增加职责与隔离说明；将模型总览分成执行规格、解释材料和条件候选，避免多份“当前方案”被同时执行。
- 收紧 README、项目规则、配置目录和论文骨架中的实时状态复述；当前 Gate 与实现进度只由 `CURRENT_STATE.md` 维护。

### 原因

G2 尚未开始运行，此时是消除目录编号冲突和第二图表源的最低风险窗口。

### 影响

- `05_结果/` 成为唯一运行结果根目录；旧 `04_结果/`、`05_图表/` 不再使用。
- 不产生任何实验结果，也不改变数学或阶段口径。

## 2026-08-13 / `STATE-2026-08-13-G2.1`

### 修改

- 新建工作空间和项目级 `AGENTS.md`，固定默认阅读顺序、目录职责与升级规则。
- 新建 `CURRENT_STATE.md`，将 G2 状态、当前权威文件、冻结摘要、正在做和禁止事项集中为单一快照。
- 新建本变更日志；README 缩减为导航页，历史评审退出默认阅读入口。
- 建立 `03_模型/`，把当前模型总览与专项模型放入数学层。
- 空的 `03_代码/` 安全迁移为 `04_代码/`，继续隔离 `main_model/` 与 `checker/`；新增 `tests/`、`scripts/`、`src/`。
- 建立唯一正式配置目录 `02_数据/configs/`。
- 当时暂未移动 `04_结果/`、`05_图表/`；二者随后在确认空目录后按 `STATE-2026-08-13-G2.2` 安全迁移。历史评审仍未批量移动。

### 原因

旧结构把 21 份当前与历史材料同时列为入口，且数学模型混在项目管理目录；新对话容易读取旧 `CR-V3.0`、旧差错语义或已被推翻的 K 结论。

### 影响

- 新任务以 `CURRENT_STATE.md → 问题契约 → CR-V3.1 → 参数/配置 → 03_模型` 为默认上下文。
- 本次结构改造不改变任何数学口径、不生成正式数字，也不改变 G2 的验收范围。

## 2026-08-13 / `CR-V3.1`

### 修改

- 单次无条件 `(1-q)alpha=q beta=e/2` 升为题面字面主情景；标准初测—触发重测链降为关键替代。
- 澄清三种 `lambda` 估计器相同的是归一来源比例，不是真阳性计数。
- 分离命题拆成分布不变主命题与键控随机世界下的逐台全等推论。
- 增加 K=9 三台跨班重测手算例、预防更换冻结门 `C26` 和来源分层检查 `C27`。

### 原因

第三轮独立评审、再裁决与队伍重新签字。

### 影响

Q1、Q2、Q3 的正式数字必须在两套观测语义下从 A/B/C 到 E、四格、工期和七个 K 全链独立重跑。

## 2026-08-13 / `CR-V3.0`

### 修改

- 冻结 B19：换班只改变值班分队；全局队列、待重测首败、释放时刻和有效尝试号保留。
- `squad_id` 不进入 FCFS 键或观测随机键，两分队共享同一固定观测核。
- 合并旧方案中的检查 ID 为单一注册表。

### 后续状态

已由 `CR-V3.1` 取代，只作为历史证据，不得用于当前验收。

## 2026-08-12 / G1 冻结

### 修改

- 完成题面、数据、讨论稿、歧义与候选路线审计。
- 冻结 A/B/C 并行、无维修、E 重做 E、D 联接时生成、终局 PL/PW、B05 主/替代周转、B18 班界活动及 V3 路线。

### 影响

G1 结束，项目获准进入 G2 最小可验证基线。
