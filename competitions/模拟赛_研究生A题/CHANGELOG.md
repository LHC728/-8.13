# CHANGELOG

本文件只记录会改变当前入口、权威版本、模型含义、阶段状态或文件结构的变更。详细论证保留在签字口径、评审响应和 AI 使用日志中。

## 2026-08-17 / `HG-Q4-REVIEWER-01`（Q4 FINAL SEMANTIC REVIEW = PASS / CLOSED；READY_FOR_PAPER；G7 AUTHORIZED_FOR_PAPER_FREEZE）

### 修改

- **Human Gate final semantic closure（reviewer = GPT-5.6 Sol，verdict = PASS_WITH_CAVEAT）落地**：**Q4 FINAL SEMANTIC REVIEW = PASS / CLOSED；Q4 FINAL STATUS = READY_FOR_PAPER；G7 = AUTHORIZED_FOR_PAPER_FREEZE**；**DeepSeek Pro-Max final review = SUPERSEDED / NOT REQUIRED**（Human Gate 授权 reviewer 替换；未伪造 Pro-Max runtime receipt；本阶段 Pro-Max calls = 0；无新 simulation / 无 rerun）。
- **RA-S1（条件边际 direct paired CI）PASS**：从 accepted `T_by_rep.json` 逐 rep 计算 `T(INT) − T(F2)`（R=128，rep 100..227，t_{0.975,127}=1.9793）：cond E−10 = **−3.5648 h**（SE 0.2336，95% CI [−4.027, −3.103]，half-width 0.462）；cond E+10 = **+91.3330 h**（SE 0.5599，95% CI [90.225, 92.441]，half-width 1.108）；mean 与 accepted exact 值一致；**conditional-margin CI 与 I_minus/I_plus interaction-contrast CI 语义不同、不得混用**（写入 `Q4_FINAL_INTERACTION_TABLE.md` / `Q4_FINAL_MANAGEMENT_RECOMMENDATIONS.md` / `Q4_FINAL_PROVENANCE.json`）。
- **RA-S2（Q-A 措辞）PASS**：删除「重标定核被证明抵消 q 变化」断言；冻结表述 = 「在本次联合重标定链下，Q-A 的工期响应小于 Q-B；这一结果与观测核随 q 重标定产生补偿作用的解释相一致，但本实验未单独识别各传播通道的独立贡献」（MECHANISM_EXPLANATION / Q4_FINAL_MECHANISM_NARRATIVE / 管理建议 R4 同步）。
- **RA-S3（scope hardening）PASS**：A「快周转 + E 能力保持是稳健组合」→「在本次已测试模型情景内，实施快周转时同步维持 E 工序节拍是更稳妥的组合」（禁 universal robustness）；B Q-B 明确 = **q_A/q_B/q_C/q_D joint proportional scale = 0.8/1.2**（非单独一个 q）；C e 明确 = **e_A/e_B/e_C/e_E joint proportional scale = 0.8/1.2**（非单独一个测手参数）；D factor table 加 scope「本排序仅在本次预注册 factor levels / perturbation range 内成立，不是因素全参数域的全局敏感度排序」。
- **reviewer governance 落文**（`Q4_FINAL_PROVENANCE.json` / `Q4_FINAL_SCOPE_AUDIT.json`）：HG-Q4-REVIEWER-01 / GPT-5.6 Sol / PASS_WITH_CAVEAT / Pro-Max SUPERSEDED（reason：Human Gate 授权 reviewer 替换，GPT-5.6 Sol 在 numeric acceptance 后独立审阅冻结证据）。
- **CURRENT_STATE 同步**：state version → `STATE-2026-08-17-Q4-READY-FOR-PAPER`；Q4 FINAL STATUS = READY_FOR_PAPER；G7 = AUTHORIZED_FOR_PAPER_FREEZE；下一阶段 = G7 PAPER FREEZE。
- **mechanical closure checker**（`tmp/closure_checker_hg_q4_reviewer.py`）：RA-S1 算术 / RA-S2 措辞 / RA-S3 guards / accepted numerics·T_by_rep·ledger_by_rep·registry 未改 / Q3·H1·K12·H2 未改 / new simulations = 0 / Pro-Max = 0——ALL PASS。

## 2026-08-17 / `HG-Q4-NUMERIC-01`（Q4 numeric FINAL PASS / ACCEPTED + interpretation repair）

### 修改

- **Human Gate 裁决 HG-Q4-NUMERIC-01（accepted HEAD `8096d80`）落地**：**Q4 NUMERIC RESULTS = FINAL PASS / ACCEPTED**（Q4 FORMAL FACTOR RANK = ACCEPTED；Q4 INTERACTION NUMERICS = ACCEPTED）；**NO NEW SIMULATION / NO Q4_EVALUATION RERUN / NO Q3 CHANGE（H1、K\*=K12 UNCHANGED）；G7 = NOT AUTHORIZED YET**。
- **interaction 解释修正（关键；数值未改）**：删除「turnover 0.5h 后 E ±10% 边际都大幅萎缩 / E_P10 惩罚被中和」错误表述；冻结解释 = **方向非对称**：`cond_E_M10_given_F2 ≈ −3.57 h`（STRONG DIMINISHING BENEFIT）、`cond_E_P10_given_F2 ≈ +91.33 h`（STRONG AMPLIFICATION OF PENALTY）；机械验证 `I_minus = cond_M10 − standalone_M10 = +30.50 h`、`I_plus = cond_P10 − standalone_P10 = +73.17 h`（exact Fraction 算术 PASS）。
- **管理建议修正**（`MANAGEMENT_RECOMMENDATION_DRAFT.md`）：R1 改「若现实中运出/运入充分重叠…具体工程方案需评估」（不把工程方案写成题面事实）；R2 增加条件边际 −3.57 h；**新增 INTERACTION WARNING：fast-turnover 下 E 工序时长 +10% → 相对 fast-turnover 状态 +91.33 h，快周转对 E 工序恶化更敏感，须避免 E 能力退化**（MODEL-INTERNAL）。
- **F3 措辞（HG 批准）**：三个预注册阈值 {150,180,210} h 均未观察到缩短总完成时间的证据（tau150 不明确；tau180/210 小幅延长）；**不得推广为所有 preventive replacement 策略必然无效**；Q3 正式策略 H1、K\*=K12 UNCHANGED。
- **F5 措辞（HG 批准窄表述）**：仅「分段线性 vs 常风险率」两种语义比较下差异很小、未观察到明确影响；**不宣称对所有可能寿命分布普遍鲁棒**（无 equivalence margin，不做等价声明）。
- **factor-rank 呈现**：表头用「rank by |standardized effect|」，方向符号另列；e 因子显示名 = operator-error environment（测手差错环境 e），避免与工序 E 混淆。
- **paper-facing 包**：`05_结果/Q4/final_handoff/`（Q4_FINAL_NUMERIC_RESULT.md / Q4_FINAL_FACTOR_TABLE.md / Q4_FINAL_INTERACTION_TABLE.md / Q4_FINAL_MECHANISM_NARRATIVE.md / Q4_FINAL_MANAGEMENT_RECOMMENDATIONS.md / Q4_FINAL_PROVENANCE.json / Q4_FINAL_SCOPE_AUDIT.json）＝ **NUMERIC_ACCEPTED / SEMANTIC_REVIEW_PENDING（NOT READY_FOR_PAPER）**。
- **CURRENT_STATE 同步**：state version → `STATE-2026-08-17-Q4-NUMERIC-ACCEPTED`；Q4 paper interpretation = REPAIRED / WAITING FINAL SEMANTIC REVIEW；**FINAL STATUS = Q4_NUMERIC_ACCEPTED_WAITING_FINAL_SEMANTIC_REVIEW**；下一阶段 = Q4 FINAL PAPER SEMANTIC REVIEW（低价时段 ONE fresh Pro-Max；本阶段 Pro-Max calls = 0）→ Human Gate → G7 PAPER FREEZE。
- **mechanical checker**（`tmp/repair_checker_hg_q4_numeric.py`）：numeric exact-equal accepted / 无模拟重跑 / T_by_rep·ledger_by_rep·registry·results 未改 / 条件边际与 I 算术正确 / F3 scope guard / F5 无普遍鲁棒声明 / 无全局因果 / 无 T=sum(ledger) / Q3·H1·K12·H2 无变化——ALL PASS。

## 2026-08-17 / `Q4 PHASE 1B + FORMAL EVALUATION + TOP-2 INTERACTION`（Human Gate 一体化授权执行包）

### 修改

- **CURRENT_STATE 状态同步**：Q4 PHASE 1A = FINAL PASS / ACCEPTED（evidence `05_结果/Q4/screening/phase_1a/20260817T060454057035Z_c516bd6c/`）；Q4 = AUTHORIZED_FOR_PHASE_1B_AND_FORMAL_EVALUATION（Human Gate 一体化授权包：Phase 1B q/e screening + Q4 FORMAL EVALUATION + Top-2 interaction（F2×F4-E））；**本包 Pro-Max calls = 0**。
- **F3 措辞红线落文（Human Gate 纠正）**：Phase 1A F3 screening 结论只可写「未观察到明确改善；点估计为正但 CI 跨 0；正式结论待独立 Q4_EVALUATION」，禁止「PM 干预无益 / 已证明不能改善 / 提前更换一定更差」；修正 addendum 见 `05_结果/Q4/screening/phase_1a/20260817T060454057035Z_c516bd6c/F3_SCREENING_WORDING_CORRECTION.md`。
- **Q4_PHASE1B_REGISTRY.json 冻结（PRE_DATA / IMMUTABLE；commit `0b532a0`）**：q4_screening / seed 7 / **rep 20..39**（与 Phase 1A 0..19 隔离）；q 因素 = GLOBAL PROPORTIONAL DEFECT-PRESSURE SCALE（scale∈{0.8,1.2}）：Q-A = CALIBRATION_INPUT（A/B/C kernel 重标定 → q_E 经冻结 Q1 closed-form 传播 → E 重标定；e baseline）、Q-B = INCOMING_DEFECT_PRESSURE（kernel 冻结 baseline，只改真实问题率）；e 因素 = E-ERROR_ENVIRONMENT（e_A/B/C/E 同 scale，feasibility ladder ±20%→±10%→±5%，全链可行、无 clip，确定性选级 ±20%）；baseline config_hash = 618d24ab…（= Phase 1A baseline，byte-identical）。
- **runner `run_q4_phase1b_v1.py`**：q 覆盖经模块级 DEFECT_PROBS_ABC/DEFECT_PROB_D_VALUE 同 U 阈值变换 adapter（try/finally 恢复，不改 core；与 F5 constant-hazard adapter 同模式）；q_E 传播用 `main_model.q1_routes.closed_form_v1`（冻结公式，baseline 复现 17-sig-fig 冻结常量）；checks：only-one-factor-diff（scenario_id 视为 metadata）/ CRN / evaluation-firewall / domain-isolation / core hashes。
- **Q4 Phase 1B screening 执行**（evidence `05_结果/Q4/screening/phase_1b/20260817T063533732938Z_b520fc8e/`）：QB_LOW −4.55 h（CI [−7.73, −1.37]）、QB_HIGH +3.90 h（CI [0.84, 6.96]）、QA_LOW −3.95 h（CI [−7.16, −0.74]）、E_LOW −1.275 h、E_HIGH +0.90 h、QA_HIGH +0.625 h；机制 = E 重测链 + 班外停工。
- **合并 screening factor rank**（`05_结果/Q4/screening/merged/Q4_SCREENING_MERGED_FACTOR_RANKING.json/.md`）：F2 −9.58 > F4-E −5.37 > F4-C +3.60 > F4-A +2.25 > Q-B −0.67 > Q-A −0.58 > F3 +0.41 > E −0.29 > F4-B ±0.22 > F5 +0.22；candidate Top-2 = F2 + F4-E（Human Gate 已冻结 interaction = F2×F4-E）。
- **Q4_EVALUATION_REGISTRY.json 冻结（PRE_DATA / IMMUTABLE；commit `356660d`）**：q4_evaluation / seed 7 / 初始 R=64（rep 100..163）/ **target 95% CI half-width = 2.0 h**（t_{0.975,63}=1.9983，t_{0.975,127}=1.9793 冻结制表值）/ two-stage：任一正式 scenario 或 interaction CI half-width>2.0h → 全 scenarios 统一扩 R=128（追加 rep 164..227；禁 factor-specific optional stopping）；22 预注册 scenarios（baseline + F2 + F3×3 + F4×8 + F5 + Q-A×2 + Q-B×2 + E×2 + INT_F2_05_E_M10/P10）；F1 K = REUSED_ACCEPTED_FORMAL_EVIDENCE；formal factor rank = factor_score = max(|std|) per factor（main scenarios only）；interaction contrasts I_minus/I_plus（replicate-level paired；CI 含 0 → 未观察到明确 interaction；排除 0 → 模型内非加性交互，禁现实因果）。
- **runner `run_q4_evaluation_v1.py`**：含 R=64→R=128 two-stage 统一扩样 + 原始模拟数据持久化（T_by_rep.json / ledger_by_rep.json）+ `--resume`（崩溃恢复，确定性 CRN 保证重放一致）；报告阶段两处 bug 已修复（`_recommendations` dict 解包 + Fraction 字符串 float 解析；模拟数据经 resume 复用，未重跑）。
- **Q4 FORMAL EVALUATION 执行**（evidence `05_结果/Q4/evaluation/20260817T065336055564Z_b46f9219/`）：**R=128 / rep 100..227；two-stage 扩样触发（stage-1 max half-width 2.0930 h > 2.0 h → 全 scenarios 统一扩 R=128；final max half-width ≈ 1.37 h < 2.0 h 达成目标）**；checks 全 PASS（only-one-factor-diff / CRN / screening-firewall=0 / domain-isolation / core hashes）。
  - 正式主 scenarios（paired ΔT vs baseline，95% CI）：F2 −73.89 h [−75.10, −72.69]（ALL_NEG）；F4-E M10 −34.07 h [−35.04, −33.10]；F4-E P10 +18.16 h [17.11, 19.22]；F4-A P10 +15.06 h [14.12, 16.01]；F4-C P10 +13.52 h [12.44, 14.60]；Q-B HIGH +3.52 h [2.69, 4.35] / LOW −2.37 h [−3.03, −1.70]；E LOW −2.66 h [−3.56, −1.76] / HIGH +2.20 h [1.28, 3.12]；Q-A HIGH +1.58 h [0.63, 2.54] / LOW −1.19 h [−2.16, −0.23]；F3 tau150 +0.30 h [−0.11, 0.71]（跨 0）/ tau180 +0.59 h [0.10, 1.07] / tau210 +0.66 h [0.21, 1.10]（COUNTERFACTUAL_ONLY）；F5 −0.02 h [−0.16, 0.12]（MODEL_SEMANTIC_ONLY）。
  - 正式 factor rank：F2 −10.74 > F4-E −6.13 > F4-A +2.79 > F4-C +2.19 > Q-B +0.74 > E −0.52 > F4-B +0.35 > Q-A +0.29 > F3 +0.26 > F5 −0.03。
  - **Top-2 interaction（F2×F4-E）**：INT_M10 −77.46 h、INT_P10 +17.44 h；**I_minus = +30.50 h（CI [29.45, 31.55]）、I_plus = +73.17 h（CI [71.80, 74.54]）均排除 0 → 模型内强非加性交互**（0.5h 周转消除调度空档后 E 时长边际影响大幅萎缩）；禁现实因果。
  - **F3 正式结论（红线措辞）**：未观察到 preventive replacement 缩短完成时间的明确改善（点估计 +0.30~+0.66 h；tau150 CI 跨 0；tau180/210 不含 0 但 <1.1 h）；COUNTERFACTUAL_ONLY；不构成政策变更建议（Q3 正式策略 = H1、K\*=K12 UNCHANGED）。
  - 机制解释 `MECHANISM_EXPLANATION.md` + 管理建议草案 `MANAGEMENT_RECOMMENDATION_DRAFT.md`（DRAFT_FOR_HUMAN_GATE；数学影响排序 ≠ 管理实施优先级）。
- **CURRENT_STATE 终态**：FINAL STATUS = **Q4_NUMERIC_RESULTS_READY_FOR_HUMAN_GATE**；**STOP**（不自动进入 G7 final paper freeze、不写 final paper claim、不改 Q3；final 论文语义审查留待 Human Gate 后低价时段另行 Pro-Max 执行）。

## 2026-08-17 / `HG-Q4-NS-01 + Q4 PHASE 1A`（Q4 additive random-domain extension；namespace blocker RESOLVED BY OPTION A）

### 修改

- **Human Gate 裁决 HG-Q4-NS-01（OPTION A / ACCEPTED）**：新增 additive Q4 物理命名空间 `q4_screening` / `q4_evaluation`（`NAMESPACE_Q4_SCREENING` / `NAMESPACE_Q4_EVALUATION` / `Q4_NAMESPACES` / `PHYSICAL_EXPERIMENT_NAMESPACES = NAMESPACES + Q4_NAMESPACES`）；**legacy NAMESPACES / ALL_NAMESPACES / H2_NAMESPACES byte-identical，旧 canonical keys 100% 不变**；serializer 域与 physical helper allowlist additive 扩展；**H2 post helpers 仍只接受 H2 域（Q4 拒绝）**；`RandomDesConfig` namespace 校验改为接受 PHYSICAL_EXPERIMENT_NAMESPACES（fail-closed，H2 仍排除出 physical DES）。
- **测试 NS-01..09**（`tests/test_q4_namespace_extension_v1.py`）：legacy byte identity / q4 接受 / screening↔evaluation↔q3 域分离 / H2 防火墙 / arbitrary 拒绝 / config 通过+fail-closed / legacy 回归。**回归 182/182 PASS**（G3 random_des、Q3 H1、H2 P1 firewall、H2 density、key_schema、Q4 NS）。
- **BACKWARD-COMPATIBLE ADDITIVE EXTENSION**：G3/Q2/Q3 accepted runs 无需 invalidation（旧 canonical keys 未变）；extension 记录见 `01_审计/INVALIDATION_REPORT_Q4_NAMESPACE_EXTENSION.md`（changed_semantics=NO、schema_additive=YES）。
- **Q4_SCREENING_REGISTRY.json（PRE-DATA / IMMUTABLE_FOR_PHASE_1A）**：namespace=q4_screening、master_seed=7、replicate 0..19（R=20）、13 scenarios + baseline（F2 turnover 0.5h / F3 tau 150·180·210 / F4 A·B·C·E ±10% / F5 constant-hazard）、factor levels 冻结。
- **Pro-Max pre-screening review（fresh，1 次）**：**PASS_WITH_CAVEAT**；BACKWARD_COMPATIBLE=true、OLD_KEYS_IDENTICAL=true、Q4_DOMAIN_ISOLATION=PASS、H2_FIREWALL=PASS、NEW_AUTHORITY_CONFLICT=false、NEW_SUBSTANTIVE_BLOCKER=false；R1–R7 全机械项（登记/证据/hash 验证/docstring/映射确认/防火墙）→ Harness 闭合 → **SCREENING_EXECUTION_RECOMMENDATION = AUTHORIZED**。
- **CURRENT_STATE §6 同步**：Q4_SCREENING_ONLY = AUTHORIZED（Phase 1A）；Q4_EVALUATION / Top-2 / final inference / final recommendation = NOT AUTHORIZED；Q3 = FINAL / IMMUTABLE。
- 旧 blocker 文件 `SUBSTANTIVE_BLOCKER_NAMESPACE.md` = **RESOLVED_BY_HG_Q4_NS_01_OPTION_A**（保留为历史证据）。

## 2026-08-17 / `Q4 PHASE 1A — SUBSTANTIVE BLOCKER`（namespace 冻结冲突 → STOP HUMAN_GATE_REQUIRED）

### 修改

- **Blocker**：HG 指定的 `Q4_SCREENING` 命名空间不被冻结 key_schema 接受（六命名空间 + H2 reserved；`Q4_SCREENING` 被拒）——key_schema 属 accepted DES core / P0 冻结项，修改需 Human Gate 授权。
- **未执行任何 Q4_SCREENING simulation**；Q4_EVALUATION / Top-2 interaction UNTOUCHED。
- 已完成：repo startup check（HEAD==62ebe5f==upstream）、CURRENT_STATE Gate 同步（Q4_SCREENING_ONLY AUTHORIZED）、Q4_G6_EXPERIMENT_SPEC_DRAFT.md 冻结标记（SCREENING_SPEC_FROZEN / PRE-DATA / HUMAN_GATE_AUTHORIZED）、scenario adapter 可行性确认（F2 turnover_profile / F3 tau_pm / F4 durations 均经 default_config 参数实现，不改 core；F5 用冻结 constant-hazard sensitivity 构造）。
- 待 Human Gate 裁决命名空间方案：A. 授权 key_schema_v1 扩展 Q4_SCREENING/Q4_EVALUATION 域；B. 授权 Q4 复用现有冻结域（如 q3_formal + 新 master_seed）；C. 其他。
- 裁决后恢复：冻结 Q4_SCREENING_REGISTRY → 1 次 fresh Pro-Max pre-screening review → PASS 后执行 Phase 1A。

## 2026-08-17 / `HG-Q4-F3-01`（Q4 F3 authority 裁决：RA1 = OPTION B / ACCEPTED）

### 修改

- **Human Gate 裁决**：F3 preventive replacement threshold = **AUTHORIZED_AS_HYPOTHETICAL_COUNTERFACTUAL_SENSITIVITY**——作为模型内 what-if 因素改变预防更换阈值；计算相对正式 H1 baseline 的 paired Delta T；参与 Q4 数学因素影响排序；可支撑有条件的管理建议。
- **冻结边界（F3 may NOT）**：不得 reopen Q3 policy selection、不得替换 H1、不得改变 K\*、不得宣称「PM beats H1」、不得宣称新最优政策、不得成为 H2'、不得追溯修改 Q3 结论。**Q3 formal strategy = H1 / NO_PM_BEFORE_MANDATORY UNCHANGED；K\*=K12 UNCHANGED**。
- **authority_conflict = RESOLVED_BY_HUMAN_GATE**；RA1 = CLOSED（Pro-Max 设计审查的 BLOCKED 解除——initial BLOCKED 由该裁决解决）。
- `Q4_G6_EXPERIMENT_SPEC_DRAFT.md` F3 更新为 AUTHORIZED（含 may / may NOT 冻结边界）；`q4_design_risk_card.json` design_review 更新（authority_conflict=RESOLVED_BY_HUMAN_GATE、required_actions_closed=true）。
- Q4 仍 = **AUTHORIZED_FOR_DESIGN_AND_PREREGISTRATION_ONLY**；正式执行 NOT RUN；Q4_EVALUATION domain UNTOUCHED；**Q4_SPEC_READY_FOR_HUMAN_GATE**（正式 Q4 execution 仍待 Human Gate 另行授权）。

## 2026-08-17 / `Q3 STATE FINAL REPAIR + Q4/G6 BOOTSTRAP`（设计预注册；Q4 = AUTHORIZED_FOR_DESIGN_AND_PREREGISTRATION_ONLY）

### 修改

- **CURRENT_STATE 顶部最终修复**：状态版本 `STATE-2026-08-17-Q3-FINAL-Q4-BOOTSTRAP`；顶部当前 Gate = Q3 FINAL MODEL SELECTION CLOSED（G2/G3/Q2/Q3 逐项状态；H1 正式主策略；K12 范围限定；H2 FINAL DELETE / ACCEPTED AS CHALLENGER RESULT；cross-K/holdout/C25 = NOT_APPLICABLE_AFTER_H2_DELETE）+ **Q4 = AUTHORIZED_FOR_DESIGN_AND_PREREGISTRATION_ONLY**（非 Q4 FORMAL AUTHORIZED）。
- **§6 当前禁止修复**：删除失效项（「不实现 H2 rollout」「不比 H1 vs H2」「不枚举 K」「不推荐 K」「不启动 Q3 七 K」「不启动 Q4」等，历史事实保留于历史段落）；新增 H2 冻结禁令（重开 H2/H2'/重调 H2/重跑 P3-C/cross-K·holdout·C25）、Q3 策略冻结（重调 H1/改 K recommendation）、Q4 授权限定（只 DESIGN/PREREGISTRATION；正式 sensitivity runs 待 Q4 spec Human Gate；禁消耗 Q4_EVALUATION random domain）、不改 G3/Q2/Q3 accepted core。
- **自检**：`05_结果/Q3/final_closure/CURRENT_STATE_SYNC_CHECK.json` = **PASS**（top_gate / current_prohibitions / next_stage；stale 短语 0 违规；历史段落显式标记）。
- **HG-Q4-H2-NA-01（additive addendum）**：Q4 中 H2 因素 = **NOT_APPLICABLE_AFTER_H2_DELETE**（historically NOT RUN）；禁止为补因素数量重激活 H2 / 设计 H2' / 发明替代策略；Q4 输入固定 H1 + K12 + NO_PM_BEFORE_MANDATORY（`08_项目管理/任务包/Q4_H2_NA_01_ADDENDUM.md`；不重写历史问题契约）。
- **Q4/G6 EXPERIMENT SPEC DRAFT**：`08_项目管理/任务包/Q4_G6_EXPERIMENT_SPEC_DRAFT.md`（基准情景机械绑定 Q3 accepted H1+K12；机制时间账本非加法；一级因素 F1-K 复用 / F2-turnover / F3-preventive-threshold（**BLOCKED 待 Human Gate**）/ F4-A/B/C/E 时长扰动 / F5-failure 语义；H2 = NOT_APPLICABLE；二级 q/e 双语义严格分开；CRN paired Delta T / batch replicate / 95% CI；Q4_SCREENING/Q4_EVALUATION 隔离；精度规则；因素排序 vs 管理优先级；Top-2 交互；管理建议绑定）。
- **Pro-Max 设计审查（fresh）**：**BLOCKED / authority_conflict=true**（F3 preventive-replacement-threshold 无法在冻结 NO_PM_BEFORE_MANDATORY policy family 内定义 → HUMAN_GATE_REQUIRED；MMR V2.1.2 PASS/CAVEAT 与 conflict 组合永不通过）。RA2（screening 数据绝对排除出最终 CI）与 RA3（Q4_SCREENING ID registry 预注册）已在 spec 闭合；RA1（F3 二选一裁决）留 Human Gate。
- **Q4 状态**：Q4 = AUTHORIZED_FOR_DESIGN_AND_PREREGISTRATION_ONLY；**正式执行 NOT RUN；Q4_EVALUATION domain UNTOUCHED；FINAL STATUS = BLOCKED（F3 待 Human Gate 裁决）**。

## 2026-08-17 / `Q3 FINAL CLOSURE — CURRENT_STATE 状态修复`（Human Gate：authoritative header + prohibitions 过时矛盾）

### 修改

- **CURRENT_STATE.md 权威头部重写**（状态版本 `STATE-2026-08-17-Q3-FINAL`）：当前 Gate = **Q3 FINAL MODEL SELECTION CLOSED（H1 正式主策略、k\*=K12 范围限定、H2 = FINAL DELETE / ACCEPTED AS CHALLENGER RESULT、Q3 FINAL STATUS = READY_FOR_PAPER）**；Q4 = NOT STARTED（状态修复后待授权）；历史链压缩为最终 accepted 状态（Q2 H1 `2d1466ba`、Q3 H1 FORMAL `7ee48fc0`+`f4da8f9d`、Q3-H2 全链 FINAL DELETE `7b490ce6`、论文包 ACCEPTED）。
- **第 6 节「当前禁止」重写**：删除过期禁令（「不实现 H2 rollout」「不选 rollout M」「不比 H1 vs H2」「不枚举 K、不推荐 K」「P3-C 重跑待执行」「cross-K = 下一授权步骤」等）；新增 **H2 冻结禁令（FROZEN_HISTORICAL_CHALLENGER）**、**论文措辞禁令**（K12 非全局最优 / H2 非失败 / agreement=1 非 H2 优于 H1 / 0/100 非全状态相等 / cross-K·holdout·C25 非 PASS 非 FAILED）、**不自动进入 Q4**、不重跑 Q1/Q2/已接受 H1 formal、不删 H2 负证据。
- **第 7 节「下一出口」清理**：移除已完成的旧自动推进路线段（density→P1→P2→P3 链），仅保留 Q3 全封闭 → 论文写作 → Human Gate 审阅 → 不自动进入 Q4。
- 其余 Q3/H2 模型结果与 evidence 一律未改（immutable）。

## 2026-08-17 / `Q3 FINAL CLOSURE`（H2 DELETE Human Gate 落地 + H1/H2 对比 + 论文结果包）

### 修改

- **Human Gate 最终裁决落地**：**Q3-H2 = FINAL DELETE / ACCEPTED**（reason = H2_NO_EFFECTIVE_DEVIATION；accepted final evidence = `05_结果/H2/tuning/stability/run_20260816T175317829317Z_7b490ce6`：n=100、agreement_b=1.0000、agreement_c=1.0000、deviation_count=0；governance closure = `a56a2cd`——FINAL NARROW Pro-Max 真实 session identity receipt：child `2174b107…`、deepseek-pro-max / deepseek-v4-pro / reasoningEffort=max、read-only 62/62、workspace_delta=0、reviewed code `439e1e1`）。
- **H2 后续 Gate 关闭**：cross-K transfer / h2_holdout / C25 = **NOT_APPLICABLE_AFTER_H2_DELETE**（historically NOT RUN；非 PASS 非 FAILED；H2 已在更早冻结删除门淘汰，后续验证链不再适用）。
- **H2 冻结为 FROZEN_HISTORICAL_CHALLENGER**（高级候选/对照模型）：禁止修改 action set / 2SE / M\* / C_eval\* / B-1 / seed/salt；禁止加 tuning sample / 重跑 P3-C / 设计 H2' / cross-K / h2_holdout / C25 / 为论文制造 deviation；除非未来 Human Gate 明确重新授权。
- **Q3 正式主策略 = H1**（不重算）：七 K（K=9, 9.5, 10, 10.5, 11, 11.5, 12）全部来自 accepted H1 formal chain（`05_结果/Q3/formal/reissue_20260815T150613626910Z_f4da8f9d` 等）；k\*=**K12** = 「七个 K + 冻结 H1 政策集（NO_PM_BEFORE_MANDATORY）」范围内的 strong winner（tier1/tier2 配对 CI 均支持且排除 0）；**保留范围限定**：非全局最优、不宣称 K=12 弱支配、不宣称「K 越大一定越优」。
- **论文结果包**：`05_结果/Q3/final_closure/`（Q3_FINAL_RESULT.md、Q3_H1_H2_COMPARISON.md、Q3_H1_H2_PAPER_TABLE.md、Q3_H1_H2_PAPER_NARRATIVE.md、Q3_FINAL_PROVENANCE.json、Q3_FINAL_SCOPE_AUDIT.json）；H1/H2 对比与叙事经 fresh Pro-Max 论文语义审查（见该目录/治理证据）。
- **Q3 状态**：FINAL MODEL SELECTION CLOSED；Q3 FINAL STATUS = READY_FOR_PAPER；**不自动进入 Q4**。
- 所有历史 H2 evidence（含 invalidated roots）保持 immutable。

## 2026-08-16 / `Q3-H2-P3 FINAL NARROW REQUALIFICATION`（PM_IDLE legality + completion-boundary failure 可见性 + 最终代码 Pro-Max）

### 修改

- **PM_IDLE 年龄语义修复**：`decision_point_v1.reconstruct_decision_points` 与 checker own 推导——a+d mandatory 检查**只作用于 DISPATCH 点（存在合法 frozen head）**（a+d>240 → MANDATORY_REPLACE_FIRST → 无 H2 dispatch 决策点；==240 → START_HEAD 合法、PM_WITH_HEAD 永不当候选；<240 → 正常）；**MAINTENANCE/PM_IDLE 只按冻结 §10/§12 判断**（idle/available、age∈[120,240)、非 replacement-pending、future demand、calibration 本班可完成），**不使用假想任务 duration**——PMIDLE-AGE-01/02（age=238/239 无合法 head → {H1_NOOP, PM_IDLE}）、PMIDLE-AGE-03（age=240 → 不合法）、PMIDLE-AGE-04（head+a+d>240 → 无 dispatch 点）。
- **PENDING-05（completion-boundary failure 可观察闭合）**：`rollout_engine_v1._post_fragment_end`——uncensored 自然 lifetime 恰在 fragment completion 达到时：**completion-first 保持**（ACTIVITY_COMPLETE 结果有效），equipment 进入 failure replacement_pending，并写出 **SAFE 可观察 `EQUIPMENT_FAILURE` marker**（trigger=failure_at_end；仅 event_time/resource_id/trigger/已完成 fragment identity；**禁止 hidden lifetime/U_L/u_key/future info**）→ 同 timestamp `project_pre_action_state()` 得到 resource failed/unavailable → 不产生 H2 决策点；**G3 accepted core 未修改**（marker 只在 H2 continuation 引擎的安全可观察路径）。
- **B-1 报告字段分离**：`build_b1_sample`/`result_summary` 明确区分 **population_wait / population_pm**（ALL-eligible 候选总数）与 **selected_wait / selected_pm / selected_both / sample_n**（冻结选择：first 50 wait-eligible 含 both + first 50 PM-only + top-up + cap 120）。
- **Pro-Max 最终代码审查（fresh）**：**PASS_WITH_CAVEAT**，`authority_conflict=false`，8 项检查全 PASS（PM_IDLE high-age / dispatch a+d mandatory / failure-at-end completion-first + observable pending / bay occupancy 3d32d8f / ALL-eligible B-1 / posterior world_m / C23 无 hidden leakage / online-offline）；R1（tests_report 最终代码重生成 **323/323** = 169 回归 + 154 requal）、R2（checker kind 对齐）、R3（状态登记）闭合。
- **P3-C 最终重跑（FINAL NARROW 语义，新 root `run_20260816T175317829317Z_7b490ce6`）= COMPLETED → H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE（冻结硬门；AUTOPILOT STOP）**：ALL-eligible B-1 **n=100**；**population_wait=74 / population_pm=5396 / selected_wait=50 / selected_pm=50 / selected_both=18**（字段分离报告）；dp_diag per batch；posterior world_m；PMIDLE-AGE / PENDING-05 / bay-occupancy 闭合；**agreement_b = 1.0000（100/100）PASS**（CP95 [0.9638, 1.0] 仅披露）；**agreement_c = 1.0000（100/100）PASS**；C23 policy PASS；tests 20/20 + 回归 28/36/38/23/44/26 PASS；**deviation_count = 0 → H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE**（2SE/0.95/样本/动作集未改）；证据 fail-closed probe/confirm/promote/final 验证 PASS；ledger 追加 `P3-C-...7b490ce6`；**cross-K transfer / h2_holdout / C25 = NOT RUN，保持 NOT AUTHORIZED 直至 Human Gate final Q3 review**；结论：H2 在最终语义（PM_IDLE legality、failure-at-end 可见性、ALL-eligible B-1、posterior world_m）下依然无有效偏离 → DELETE 建议成立 → STOP Human Gate。
- **阶段状态**：P3-C 最终重跑（FINAL NARROW）= **已完成（H2_DELETE）**；**cross-K transfer / h2_holdout / C25 保持 NOT AUTHORIZED 直至 Human Gate final Q3 review**；Density / P1 / P2 / P3-A / P3-B / Q2 / G3 accepted 证据 = UNAFFECTED。

## 2026-08-16 / `Q3-H2-P3 第二次语义重新认证`（B-1 冻结样本恢复 + posterior world_m + mandatory/replacement 闭合）

### 修改

- **Human Gate 裁决（e4fd435 的 H2 DELETE 暂不接受）**：撤销第一轮把「production quota-evaluated points」延伸为 §4 B-1 采样总体的解释；**B-1 = ALL H2-ELIGIBLE DECISION POINTS**（冻结 §1.3/§4；不受在线 C_eval\* 约束；50+50+top-up+cap120，n<50→DELETE）。登记 **HG-Q3-H2-DP-DIAG-01**（`08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT_ADDENDUM_DP_DIAG_01.md`，追加不重写）：production `dp_online` 不变；offline `dp_diag` = 每批内 (time, canonical resource order) 排序的 0-based 序号（仅对进入 B-1 且被重评估的点）；normal/ALT/2M\* 同点共享 (replicate_id, dp_diag)；2M\* 前 M\* 个 m 键与 M\* 完全一致；action 不入 seed。
- **MMR 漏判登记**：`05_结果/governance/model_routing/MODEL_ROUTING_MISS_001.json`——implementation repair 改变 FROZEN diagnostic population/sample semantics 而描述为 implementation-only requalification：原 route YELLOW，正确行为 RED/HUMAN_GATE_REQUIRED；本次由 HG-Q3-H2-DP-DIAG-01 最小澄清（不重设计 MMR）。
- **最新 P3-C root 失效**：`run_20260816T150705443207Z_4f60db0d` = **INVALIDATED_FOR_FROZEN_SAMPLE_AND_ROLLOUT_WORLD_SEMANTICS**（`INVALIDATION_STATUS_SECOND.json`；数字不改；原因 A B-1 population 错用 quota 子集 / B rollout world 未逐 m 重建 / C mandatory+replacement 未闭合）。旧 root `791506d8` 保持原失效。
- **B-1 恢复**：`run_h2_p3c_stability_v1.py build_b1_sample` 从 `collect_eligible_points`（ALL eligible）构造，**不经 `quota_simulate_batch`**（后者仅用于独立 quota 测试与 production runner）；dp_diag 映射；B1-OFFLINE-01/02/03 机械证明。
- **posterior world_m（核心）**：`h2_policy_v1.evaluate_decision_point` 移除 caller 提供的固定 world/provider，**每个 m 由该 m 的 h2_rollout post keys（U_X/U_D/U_L）重建 world_m + provider_m**；同 m 的**全部候选动作共享同一 world_m**（跨动作 CRN）；不同 m 后验世界允许不同；`h2_batch_runner_v1._h2_step` 删除 dummy `u_x=1/2、u_d=1/3、u_l=1/3` 固定世界；**physical h2_tuning hidden world 不再进入 policy rollout**（x_abc/x_d/residual lifetime 只由 h2_rollout keys 后验重采样）。
- **AGE-LEGAL-01/02/03**：`decision_point_v1.reconstruct` —— a+d>240（mandatory）→ 无任何 H2 决策点；a+d==240（exact_240）→ START_HEAD 可（完成优先）、PM_WITH_HEAD 永不当候选；a+d<240 → 冻结规则。P3-A PM-R2 测试与 checker `MANDATORY_OPTIONAL_PM` 依新裁决 requalified。
- **PENDING-01..04**：`observable_state_v1._observable_pending_status` —— 同 timestamp EQUIPMENT_FAILURE → failed；illegal_240 TASK_CANCEL → replacement；可观察 age≥240（post-completion mandatory）→ replacement；仅用可观察事件/age/generation/status（不读 hidden lifetime）；replacement 完成即恢复；普通 idle 不受影响。
- **P3-B Q_hat/SE 重新认证**：WORLD-M-01..06 + DPKEY-01..05（dp_diag）——Q_hat/配对 D_m/SE_M/2SE/跨动作 CRN/M8-M16 prefix 公式未改，机械 PASS。
- **成本重新认证（SECOND）**：c_r 现含 per-m world_m 重建 + engine run（旧值不继承）；冻结网格 (4,8)/(8,6)/(8,8)、w_p≤90s、max M 再大 C_eval → 仍选 **(8,8)** → **冻结恢复 M\* = 8、C_eval\* = 8、W_cap\* = 4、P_cap\* = 4**（`cost_requalification_report.json`）。
- **测试**：requal **145/145** + 回归 **169/169** PASS（合计 314；含 B1-OFFLINE / AGE-LEGAL / PENDING / WORLD-M / DPKEY-dp_diag / RELEASE-GUARD / INFLIGHT / PM-R2 requal）。
- **Pro-Max 第二轮审查（fresh）**：**PASS_WITH_CAVEAT**，`authority_conflict=false`，A–H 八问全 YES；R1/R2 闭合、R3（P3-C 重跑）执行授权。
- **P3-C 重跑（第二次重认证语义，新 root `run_20260816T170310179282Z_ea3354ba`）= COMPLETED → H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE（冻结硬门；AUTOPILOT STOP）**：ALL-eligible B-1 样本 **n=100**（wait=50、pm=50、both=18；wait 候选 74、PM 候选 5396；dp_diag per batch）；**agreement_b = 1.0000（100/100）PASS**（CP95 [0.9638, 1.0] 仅披露）；**agreement_c = 1.0000（100/100）PASS**；C23 policy PASS；tests 20/20 + 回归 28/36/38/23/44/26 PASS；**deviation_count = 0 → H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE**（2SE/0.95/样本/动作集未改）；证据 fail-closed probe/confirm/promote/final 验证 PASS；ledger 追加 `P3-C-...ea3354ba` wall=845.0s；**cross-K transfer / h2_holdout / C25 = NOT RUN，保持 NOT AUTHORIZED 直至 Human Gate final Q3 review**；结论：H2 在第二次重认证语义（ALL-eligible B-1、posterior world_m、AGE-LEGAL、PENDING、bay-occupancy 修复）下依然无有效偏离 → DELETE 建议成立 → STOP Human Gate。
- **阶段状态**：P3-C 重跑（第二次重认证）= **已完成（H2_DELETE）**；**cross-K transfer / h2_holdout / C25 保持 NOT AUTHORIZED 直至 Human Gate final Q3 review**；Density / P1 / P2 / P3-A / P3-B / Q2 / G3 accepted 证据 = UNAFFECTED。

## 2026-08-16 / `Q3-H2-P3-C 决策语义重新认证`（第一轮，被第二次裁决撤销部分语义）

### 修改

- **旧 P3-C root 失效**：`05_结果/H2/tuning/stability/run_20260816T101049163825Z_791506d8` 标记 **INVALIDATED_FOR_DECISION_SEMANTICS**（n=100 / agreement_b=0.9900 / agreement_c=1.0000 / deviation_count=0 等数字保留不改；不再作为 H2 DELETE 决策证据；`INVALIDATION_STATUS.json` 叠加记录，不进入原 file_hashes 清单）。
- **失效原因（Human Gate BLOCKER A–D）**：A 决策时刻状态（用含 H1 派工结果的日志前缀当 pre-action 状态）；B 决策点未检查资源 idle/available；C candidate first-action（START_HEAD/WAIT_EVENT）未严格生效；D dp 用跨 batch 全局 sample index 而非 per-batch evaluated-point 0-based 序号。
- **P3-A 修复**：`decision_point_v1.py` 逐 closure 用 pre-action 视图（同 timestamp dispatch 记录排除）+ DISPATCH 点要求资源 idle；checker `h2_p3_mechanics_checker_v1.py` requalified（own pre-action view + own idle guard）；DP-IDLE-01..04 / PRE-01..04 测试。
- **P3-B 修复**：`rollout_engine_v1.py` 新增冻结决策上下文（decision_resource/decision_head/decision_kind）——START_HEAD fail-closed 启动冻结 head（缺上下文/队列空/head 不匹配/不合法均 raise）、WAIT_EVENT hold 至冻结 anchor（wait_holds + h2_wait_wake）、PM fail-closed、H1_NOOP 无操作；`h2_policy_v1.py` `evaluate_decision_point(decision_head=...)` 绑定进每个候选 rollout；`h2_batch_runner_v1.py` `_h2_step` 用 pre-action 状态与冻结 head；`run_h2_p3c_stability_v1.py` B-1 样本 = production-contract 在线 quota（C_eval\*=8/W_cap=4/P_cap=4）实际评估的决策点，dp = 每批 evaluated-point 0-based 序号（SPEC 6.2），点上下文 = pre-action 投影；checker `h2_p3b_checker_v1.py` `check_rollout_kernel` requalified（own head 推导 + own 首动作期望）。
- **重跑预备修复（offline-rebuild release guard）**：首次重跑（`20260816T141252994705Z_b9766950`）触发 fail-closed runaway（t=174 E 资源点 head (37,E,2)）——`RolloutEngine._release_tasks` 在离线重建中把**已测过的 attempt-1** 重新 release（已完成任务不在重建后的 `self.tasks`，tid guard 失效）→ 堵死 FCFS 队头 → 日历空 → runaway；修复：A/B/C 与 E 的 att1 release 仅当 process state = PENDING（PASSED/IN_PROGRESS/AWAITING_RETEST 均跳过；fresh-batch 与 retest 路径不变）；负证据 `failed_rerun_negative_evidence.txt`；RELEASE-GUARD-01/02/03 + INFLIGHT-01/03 测试。
- **测试与回归**：requal 套件 **128/128 PASS** + 回归 **169/169 PASS**（`tests/test_h2_p3c_requal_v1.py` ACT-01..08 / DPKEY-01..05 / QUOTA-DP-01..03 / SAMPLE-01..04 / INFLIGHT-01..03 / RELEASE-GUARD-01..03 等；证据 `05_结果/H2/requalification/2026-08-16_decision_semantics/tests_report.json`）。
- **成本重认证**：冻结网格 (4,8)/(8,6)/(8,8)（w_p≤90s；max M 再大 C_eval）三候选全可行 → 仍选 **(8,8)** → **冻结恢复 M\* = 8、C_eval\* = 8、W_cap\* = 4、P_cap\* = 4**（`cost_requalification_report.json`；实测 w_p_median (4,8)=3.40s / (8,6)=5.00s / (8,8)=6.60s；测量先于 release-guard 修复，修复为成本单调且最坏 7.08s << 90s，无需重测）。
- **Pro-Max outcome-aware 审查（MMR V2.1.2 YELLOW 门，两轮）**：fresh `deepseek-pro-max/deepseek-v4-pro/max` 只读审查 → **PASS_WITH_CAVEAT**（主审查 + 增量审查），`authority_conflict=false`（两轮），`required_actions`（R1 状态同步、R2 负证据 + 成本时序说明、R3 E 路径 fixture）**全部闭合** → `required_actions_closed=true` → **P3-C 重跑 AUTHORIZED（最终代码）**（证据 `05_结果/governance/model_routing/v2_1_2/p3_requal_pro_max/`，含 `pro_max_review_incremental.txt`）。
- **P3-C 重跑（修复后语义，新 root `run_20260816T150705443207Z_4f60db0d`）= COMPLETED → H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE（冻结硬门；AUTOPILOT STOP）**：quota-evaluated B-1 样本 n=79（wait=39、pm=40、both=5）；**agreement_b = 1.0000（79/79）PASS**（CP95 [0.9544, 1.0] 仅披露）；**agreement_c = 1.0000 PASS**；C23 policy PASS；tests 20/20 + 回归 28/36/38/23/44/26 PASS；**deviation_count = 0 → H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE**（2SE 阈值/样本/动作集未改）；证据 fail-closed probe/confirm/promote/final 验证 PASS；ledger 追加 `P3-C-...4f60db0d` wall=982.1s → 累计 **1737.76s（0.4827h）**（soft 4h / hard 8h 未达）；**cross-K transfer / h2_holdout / C25 = NOT RUN，保持 NOT AUTHORIZED 直至 Human Gate final Q3 review**；结论：H2 在修复后（pre-action 决策边界 / 冻结 head / 严格 first-action / per-batch evaluated dp）语义下依然无有效偏离 → DELETE 建议成立 → STOP Human Gate。
- **阶段状态**：P3-C 重跑 = **已完成（H2_DELETE）**；**cross-K transfer / h2_holdout / C25 保持 NOT AUTHORIZED 直至 Human Gate final Q3 review**；Density / P1 / P2 / P3-A / P3-B / Q2 / G3 accepted 证据 = UNAFFECTED。

## 2026-08-16 / `MATHEMATICAL_MODELING_ROUTER_V2.1.2` — **Human Gate ACCEPTED**

### 修改

- **Human Gate 验收落文（2026-08-16）**：Reviewer Verdict = **PASS**；Human Gate = **ACCEPTED**；Phase A = ACCEPTED（UNCHANGED，`7f670557…`）；Phase B = ACCEPTED；Ending commit = **`193d3722579a60307ad1969502d4e66d1a67e1c1`**；Status = **READY_FOR_GENERAL_MATHEMATICAL_MODELING_AUTOPILOT**。
- `08_项目管理/模型路由/MATHEMATICAL_MODELING_ROUTER_V2.1.2.md` 状态更新为 **HUMAN_ACCEPTED**；`CURRENT_STATE.md` 同步记录该治理验收。
- 该验收仅固化路由治理；不改变、不重启任何 Q3/H2/formal 建模工作（保持 STOP 状态）。

## 2026-08-16 / `MATHEMATICAL_MODELING_ROUTER_V2.1.2`（FINAL HARDENING；V2.1.1 路由门被取代）

### 修改

- **§1 authority_conflict fail-closed（P0）**：`route_gate_v2_1_1` 现在消费 `authority_conflict`——YELLOW + conflict=true → **HUMAN_GATE_REQUIRED**（任何本可通过的 verdict）；PASS / PASS_WITH_CAVEAT 与 conflict=true 组合永不 formal-pass（不变量；F-01/02/03）。
- **§2 Authority-Backed GREEN**：authority 依赖 GREEN 类（UNDER_FROZEN_EXACT_RULE / UNDER_FROZEN_EXACT_FORMULA / UNDER_FROZEN_CONFIG / PLOT_FROM_FROZEN_DATA_AND_SPEC / REPRODUCE_ACCEPTED_RESULT_WITHOUT_METHOD_CHANGE）要求 `authority_state ∈ {FROZEN, HUMAN_ACCEPTED}` 且 `authority_refs` 非空；EXPLORATORY/PROPOSED + UNDER_FROZEN... → `RiskCardInvalid`（ROUTING_INVALID）。
- **§3 可解析 Authority Receipt**：Risk Card 新增 `authority_receipts: [{ref, exists, sha256, authority_state}]`；`verify_authority_receipts(card, workspace_root)` 校验 workspace-relative 文件存在 + sha256（记录时）+ state∈{FROZEN,HUMAN_ACCEPTED}；自由文本不算正式证据。fixture：`v2_1_2/fixtures/frozen_solver_fixture_spec.json`（authority_state=FROZEN，合成）。
- **§5 Sentinel 运行时身份 Receipt**：`v2_1_2/sentinel_request_header.json` 从**既有已持久化**的 Sentinel child session（`5562219f-…`）的 request/header+context 事件提取（deepseek-official/deepseek-v4-flash/effort=high/1e6/fresh/只读工具/delta=0）——与 Pro-Max identity 证据同标准；**未发起新模型调用**。旧 SENTINEL-LIVE-001 "frozen solver specification v1" 仅作 runtime-channel 历史证据，不声称 authority 验证（§4）。
- **§6 Formal GREEN Receipt 强制**：formal GREEN @ R4 门新增 `authority_receipt_verified` 要求（sentinel_required + sentinel_identity_verified + AGREE_GREEN + receipt verified 全满足才 PASS）；formal checker 层要求 receipt 工件存在（调用方布尔值单独不构成验证；F-09/10）。
- **§7 BLOCKED Dedup 语义**：`SemanticIssueStore` 分离 `needs_review()` 与 `is_resolved()`——BLOCKED + 同 contract + 无新 re-review 条件 → 未解决但**不自动重复 Pro-Max**（保持 BLOCKED 等决策层）；仅 contract 改变/新反例/新 authority 证据/checker 矛盾/required action 实质变化/新 formal implication/先前 caveat 变实质才 re-review。
- **最终检查器 `check_mathematical_modeling_router_v2_1_2.py`：F-01..F-15 = 15/15 PASS**（全部从 artifact/计算得出；`v2_1_2/final_checker_result.json`）。
- **测试**：**103/103 PASS**（新增 authority_conflict 门 / authority-backed GREEN / receipt 解析 / BLED 无自动重审；V2.1.1 与 V2.1 检查器在新语义下保持可运行）。
- **版本**：ROUTER_VERSION=`MMR_V2.1.2`；V2.1.1 文档标记 **SUPERSEDED_FOR_FINAL_GATE by V2.1.2**（历史保留）；`08_项目管理/模型路由/MATHEMATICAL_MODELING_ROUTER_V2.1.2.md`（最终版权威）；AGENTS.md 更新为 V2.1.2 权威。
- **预算**：新 Pro-Max 调用 = **0**；新 Flash 调用 = **0**；无 Q3/H2/formal modeling 执行；Phase-A route/tool/config、Harness core、formal 建模代码/结果零修改。

## 2026-08-16 / `MATHEMATICAL_MODELING_ROUTER_V2.1.1`（Phase B REPAIR；V2.1 路由门被取代）

### 修改

- **Human Gate 评审（V2.1 STATUS=BLOCKED）五项修复**：
  - **P0-1 identity/outcome 分离**：`review_identity_verified`（fresh/provider/model/effort/delta）与 `review_verdict`（PASS/PASS_WITH_CAVEAT/BLOCKED/HUMAN_GATE_REQUIRED）+ `required_actions_closed`/`authority_conflict` 分开；**VERIFIED_PRO_MAX 绝不等于语义 PASS**。`route_gate_v2_1_1` outcome-aware：BLOCKED→BLOCKED、PASS+actions closed→PASS、PASS_WITH_CAVEAT+closed→PASS（caveat 保留记录）、HUMAN_GATE_REQUIRED→HUMAN_GATE_REQUIRED、缺失/未知 verdict→BLOCKED。
  - **P0-2 runtime Sentinel Gate**：formal GREEN @ R4 必须 `sentinel_required=true` + 实际低成本 Flash/E2 Sentinel（identity verified）+ `AGREE_GREEN`，缺失/畸形→ROUTING_BLOCKED；`sentinel_upgrade` 永不降级矩阵（GREEN+AGREE_YELLOW→YELLOW、+AGREE_RED→RED、RISK_OMISSION/ROUTE_TOO_LOW→YELLOW minimum；YELLOW/RED 不动摇）。**真实 Flash Sentinel 已执行**：SENTINEL-LIVE-001（child `5562219f-…`，deepseek-official/deepseek-v4-flash，只读工具，AGREE_GREEN，identity 实测，packet `v2_1_1/sentinel_live_packet.txt`，sha 73349418…）→ formal GREEN gate PASS（`v2_1_1/sentinel_live_result.json`）。
  - **P1-1 双语方法族分类**：16 族中英模式（解析解/概率统计/优化/运筹/图网络/DES/蒙特卡洛/ODE-PDE/物理/多指标/空间GIS/数值计算…）；**§16 DES 细化**：generic simulation/simulate/仿真 不再自动归 DES（需离散事件证据）。
  - **P1-2 Risk Card fail-closed + 移除 frozen-mechanical 全局旁路**：`validate_card_fail_closed` 在路由计算前强制（畸形→`ROUTING_INVALID`/RiskCardInvalid，永不 formal PASS）；拒绝 risk true 无 evidence、evidence 引用 false 维度（除非 informational）、未知维度、非法 state/stage、GREEN 类缺 mechanical evidence、FROZEN/ACCEPTED 依赖类缺 `authority_refs`、机械/语义矛盾；任一语义 risk true → YELLOW（无旁路）。
  - **P1-3 治理优先级显式化**：AGENTS.md 增加 V2.1.1 权威 + 优先级（MMR 管分类；PRO_MAX_V1.0 管 HOW；AUTOPILOT-V1.1 管阶段/预算/停机/产物纪律，其旧风险措辞不覆盖 MMR）；Human Gate 最终权威。
- **§5 LIVE-001 证据修复（无新 Pro-Max 调用）**：已提交评审原文 VERDICT: BLOCKED 保留；`semantic_issues.json` 修正为 `review_verdict=BLOCKED / semantic_status=BLOCKED / identity verified=true / actions closed=false`；LIVE-002 "已解决" dedup 事件替换为 "BLOCKED not dedup-resolved"（repeated Pro-Max required）；`live_integration/routing_verification.json` 增加 review_verdict/semantic_status 字段。
- **§6 dedup 修复**：`SemanticIssueStore` 新增 semantic_status（OPEN/RESOLVED/BLOCKED/HUMAN_PENDING）；仅 identity verified ∧ 可接受终态 ∧ actions closed ∧ contract 未变才 dedup；BLOCKED/HUMAN_PENDING 永不被身份验证解决；存储层拒绝 BLOCKED/HUMAN_GATE_REQUIRED 记为 RESOLVED。
- **§18 命名与表述**：`GENERALIZATION_CHECK` → **`PROJECT_TOKEN_LEAK_GUARD`**（零匹配只证明已知 token 未泄漏；泛化证据 = 跨域测试 + 中英测试 + 验证族测试）。
- **检查器**：新增 `check_mathematical_modeling_router_v2_1_1.py` **R-01..R-22 = 22/22 PASS**（从 artifact/计算得出）；V2.1 检查器 MMR-01..16 标记 SUPERSEDED_FOR_ROUTING_GATE 并在新引擎语义下可运行（16/16）。
- **测试**：原 T01..T26 保留 + 中英分类（§17 12 项）+ DES 细化 + Sentinel 门负例 + Risk Card fail-closed + outcome-aware 门 + Human Gate 矩阵 + dedup 修复 = **96/96 PASS**。
- **事件/metrics 重生成**：`v2/routing_events.jsonl`（21 事件；LIVE-001 BLOCKED、LIVE-002 not-dedup、D3 Sentinel AGREE_GREEN）；`v2/metrics.json`（10 tasks：2 GREEN/7 YELLOW/1 RED；3 blocks；1 sentinel review；dedup avoided=0——如实）。
- **文档**：`08_项目管理/模型路由/MATHEMATICAL_MODELING_ROUTER_V2.1.1.md`（修复版权威）；`MATHEMATICAL_MODELING_ROUTER_V2.1.md` 标记 **SUPERSEDED_FOR_ROUTING_GATE**；`05_结果/governance/model_routing/v2_1_1/INVALIDATION_REPORT_V2.1.1.md`（失效 V2.1 PASS / MMR PASS / 旧 dedup 证据；不失效 Phase-A、Q3/H1/H2 证据）。
- **约束**：Phase-A route/tool/config 零修改；Harness core 零修改；formal 建模代码/结果零修改；未做 Q3/H2 正式执行；仅一次新的低成本 live 调用（Flash Sentinel，非 Pro-Max）。

## 2026-08-16 / `MATHEMATICAL_MODELING_ROUTER_V2.1`（通用数学建模风险路由，Phase B，additive）

### 修改

- **Phase-A carry-forward closure**：
  - **A1 committed evidence replay**：`check_model_routing_v1.py` 改为读取 committed artifact `wire_semantic_check.txt`（.log 名被 gitignore，不再引用）；从 committed state 重跑 → ROUTE-01..12 + FLASH_NON_REGRESSION 全 PASS；`phase_a_replay_result.json`（commit_sha / checker_path / evidence_root / wire_artifact_name / result / checks）。
  - **A2 exact Pro-Max smoke**：固定 packet artifact `v2/phase_a_exact_smoke_packet.txt`（TASK_ID=PHASE_A_EXACT_SMOKE、ROLE=READ_ONLY_SMOKE_REVIEWER、双 mandatory clause）。两次 headless coordinator 尝试失败（空 prompt / coordinator 自答 packet，均丢弃）；改用 coordinator-free 通道：in-process 启动 runner-free profile（dsh-base only）+ `ctx.subagents.start('spawn', ...)` 携带 **tool-pro-max-review 实例的完全一致配置**（该 tool 的 execute() 即此路径）→ packet 逐字传输（fidelity=PASS by construction）。child `364c6002-...`：request/header `deepseek-pro-max`/`deepseek-v4-pro`/`reasoningEffort=max`（adapterDefaults），fresh spawn（仅 packet），只使用 read/glob（deny-list 生效），输出 `PRO_MAX_SMOKE_OK` + `HEAD=7f670557...` 与 dispatch 前记录一致，workspace delta=0；`phase_a_exact_smoke_result.json`。
  - **A3 static ≠ runtime 已落文**：Phase-A ROUTE-08/09/10 仅证明 policy contract + dedicated-route fail-closed；任务层运行时强制由 Phase B 实现（Risk Card / deterministic route / gate / MMR checker）。
- **Universal Risk Router（`04_代码/governance/model_routing_v2/`，stdlib-only）**：R1..R10 风险维度；Risk Card V2.1（schema 见 `08_项目管理/模型路由/ROUTING_RISK_CARD_SCHEMA.json`）；确定性路由引擎 `compute_model_route_v2_1`（RED=frozen/accepted authority mutation；语义风险→YELLOW；uncertainty/interpretation/ambiguity→YELLOW；engineering escalation S1-S7；GREEN 仅 16 项白名单；默认 YELLOW——无法证明 GREEN）；R0-R4 动态重分类；`route_gate_v2_1` fail-closed（YELLOW 无 VERIFIED_PRO_MAX → ROUTING_BLOCKED，禁止 fallback；RED 无 Human Gate → HUMAN_GATE_REQUIRED）；semantic issue dedup（contract hash + re-review 条件）。
- **Route Sentinel V1**：CLASSIFICATION_AUDITOR_ONLY（Flash 低成本）；AGREE_*/RISK_OMISSION/ROUTE_TOO_LOW；分歧自动升级 YELLOW → mandatory Pro-Max，Flash 不得否决；触发 A-E。
- **Method Family Registry V1.0**（16 族 multi-label，HYBRID_OTHER 兜底；family 不进入路由引擎——结构性隔离）+ **Verification Strategy Registry V1.0**（分族优先武器 + 11 项 Universal Baseline；`build_verification_plan` 对 threshold-bearing check 缺 authority 阈值即拒绝——注册表永不发明阈值）。
- **Project Extension 层**：仅保持/升级风险；YELLOW→GREEN、RED→YELLOW 一律 REJECTED（`ExtensionRejected`）；**Generalization Guard**：Universal Core 8 个源文件扫描 12 个项目专属 token（`data/project_specific_tokens.json`），`GENERALIZATION_CHECK` = PASS（0 matches）；**MODEL_ROUTING_MISS_REGISTRY.json**（6 条抽象 pattern，UNIVERSAL scope）。
- **测试**：跨域合成 T01–T26（26/26，含 T17 EXPLORATORY→YELLOW not RED、T18/T19 FROZEN/HUMAN_ACCEPTED→RED、T20 GREEN→YELLOW 重分类、T24/T25 Sentinel、T26 extension 拒绝）+ verification-family 测试 + 负例（YELLOW+Pro-Max 不可用→ROUTING_BLOCKED）+ dedup + generalization = **47/47 PASS**。
- **§40 live integration（唯一一次真实 Pro-Max 集成）**：LIVE-001（bootstrap sampling unit row vs subject，authority 未定义）→ Risk Card `statistical_inference=true, multiple_plausible_interpretations=true` → YELLOW → 真实 dispatch → child `29c42845-...` header `deepseek-pro-max`/`deepseek-v4-pro`/`reasoningEffort=max`、fresh、只读工具（glob/grep/read，926 reasoning chunks）、VERDICT=BLOCKED（决策层冻结前不得继续——语义正确、非项目答案）；`v2/live_integration/`（routing_risk_card / verification_plan / dispatch / request_header / review / verification）。
- **路由事件与指标**：`v2/routing_events.jsonl`（TASK_CLASSIFIED/TASK_RECLASSIFIED/SENTINEL_REVIEW/PRO_MAX_REQUIRED/PRO_MAX_DISPATCHED/PRO_MAX_VERIFIED/ROUTING_BLOCKED/HUMAN_GATE_REQUIRED 等 19 事件）；`v2/metrics.json`（10 tasks：2 GREEN / 7 YELLOW / 1 RED；1 sentinel review；1 GREEN→YELLOW upgrade；2 VERIFIED_PRO_MAX；1 dedup 避免；1 block；1 human-gate miss；不设占比目标）。
- **Router checker `check_mathematical_modeling_router_v2_1.py`：MMR-01..16 = 16/16 PASS**（关键 Gate 全部来自真实 artifact/计算：exact smoke / replay / RED gate / YELLOW gate / allowlist / R0-R4 事件 / sentinel 升级 / extension 拒绝 / family 不影响 route / 阈值纪律 / generalization / dedup / authority-state）。
- **文档**：`08_项目管理/模型路由/`（MATHEMATICAL_MODELING_ROUTER_V2.1.md、METHOD_FAMILY_REGISTRY_V1.0.md、VERIFICATION_STRATEGY_REGISTRY_V1.0.md、PROJECT_ROUTING_EXTENSION_SCHEMA.md、ROUTING_RISK_CARD_SCHEMA.json、VERIFICATION_PLAN_SCHEMA.json、MODEL_ROUTING_MISS_REGISTRY.json、ROUTE_SENTINEL_V1.md）；`AGENTS.md` 增加 V2.1 authority 短规则；Phase-A 文档未覆盖。
- **约束**：Phase-A route/tool/config 零修改（只读调用）；Harness core 零修改；模型/数学/formal evidence/C25 零触碰；未重跑 Q3 正式模拟、未做 H2 tuning/transfer/holdout/C25/Q4。

## 2026-08-16 / `MODEL_ROUTING_PRO_MAX_V1.0`（Pro-Max 独立 reviewer 通道，additive）

### 修改

- **新增 harness 级独立 reviewer 通道（additive；Harness core 零修改）**：`deepseek-pro-max` provider route（llm-pi-ai，复用 `DEEPSEEK_API_KEY` credential ref 与 `https://api.deepseek.com` endpoint；model `deepseek-v4-pro`（contextWindow 1,000,000 / maxTokens 256,000，均继承官方 route 已验证容量）；`reasoning: max` 路由默认；`compat.thinkingFormat=deepseek` + `supportsReasoningEffort=true`；`reasoningEfforts: high→high, max→max`）+ `pro_max_review` tool instance（spawn provider、fresh child、`enableRunInBackground=false`、`backgroundMode=one-shot`、`maxDepth=1`、persona=`READ_ONLY_SEMANTIC_REVIEWER`、toolFilter deny 全部 mutation tools）。配置位置：`$DSH_HOME/settings.yaml`（llm-pi-ai 节）与 `$DSH_HOME/cordis.patch.yml`（home user layer insert 行）；**rollback = 删除两处配置（已验证）**。
- **验证**：SOURCE AUTHORITY facts A–E 全 PASS（无 drift）；`pro_max_precheck_report.json`；wire_semantic_check T1–T5 ALL PASS（官方 adapter max→`thinking:{type:enabled}`+`reasoning_effort:max`；pi-ai deepseek 方言同语义；负例：未声明 max 不提供、request 在 I/O 前拒绝 → L3/L4 BLOCKED 无 fallback；隔离：pi-ai routes 仅含 deepseek-pro-max）；**smoke = PASS**（headless driver 经 `pro_max_review` → fresh child 实测 request/header `provider=deepseek-pro-max, model=deepseek-v4-pro, reasoningEffort=max`（含 adapterDefaults），child session 无 parent transcript、零工具调用、输出 `PRO_MAX_SMOKE_OK`，workspace delta=0）；Flash non-regression = PASS（父 run header `deepseek-official/deepseek-v4-flash` 不变，reasoningEffort=max 为既有设置）；**ROUTE-01..12 + FLASH_NON_REGRESSION 全部 PASS**（`tools/check_model_routing_v1.py`）；rollback 测试 = PASS（删除配置后 composition 不再含 tool 行，恢复后复现）。
- **文档**：`08_项目管理/MODEL_ROUTING_PRO_MAX_V1.0.md`（架构/隔离/路由规则/L3·L4 触发/fail-closed/验证程序/wire 语义/packet 模板/ROUTE-01..12/rollback）；`AGENTS.md` 增加短规则引用（L3/L4 必须 `pro_max_review` 且 `VERIFIED_PRO_MAX`，禁止 fallback）。
- **路由证据根**：`05_结果/governance/model_routing/`（precheck/composition before·after/workspace before·after/wire check/dispatch/request header/review/verification/decision/route check result）。
- **模型/数学/evidence 零触碰**：Q3 模型、H1/H2 代码语义、冻结阈值、formal evidence、C25、CURRENT numeric conclusions 均未修改。

## 2026-08-16 / `STATE-2026-08-13-G2.4` / `Q3-H2-P3-C action stability diagnostics = COMPLETED → H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE（AUTOPILOT STOP）`

### 修改

- **Q3-H2-P3-C（action stability，SPEC §4/D-10）在冻结 H2 政策（M\*=8、C_eval\*=8、W_cap\*=4、P_cap\*=4、2SE confident deviation、canonical tie order）下完成**；证据根 `05_结果/H2/tuning/stability/run_20260816T101049163825Z_791506d8`（fail-closed probe/confirm/promote/final 四段验证；ACYCLIC hash DAG（RULE A）+ manifest/inventory 一致 + semantic mapping；RESULT 数字由 final evidence 机械生成）。
- **B-1 样本**：h2_tuning/seed 6/rep 0..9/K=10.5 十个物理批（H1 baseline；批升序→批内时间序取前 50 wait-eligible + 前 50 PM-only）→ **n=100（wait=50、PM=50、both=20，≥50 硬门 PASS）**；每点评估全部合法动作 Q_hat_M（M=8、跨动作 CRN rollout_seed(dp,m)）。
- **stability (a) 确定性 / C23 policy**：hidden 变异（true_state / lifetime_h / raw u）不改变 policy decision = **PASS**。
- **stability (b) ALT-salt agreement = 0.9900（99/100）≥ 0.95 点估计硬门 = PASS**（Clopper-Pearson 95% [0.9455, 0.9997] 仅披露、不设第二门；唯一不匹配点 = ALT salt 恰在 2SE 边界偏离一次，normal salt deviation_count=0）。
- **stability (c) M=8 vs M=16 = 1.0000（100/100）≥ 0.95 = PASS**（生产 M\*=8 不变；M=16 仅离线诊断）。
- **deviation_count = 0（normal salt，100 点全部选 a_H1）→ 冻结硬门 H2_NO_EFFECTIVE_DEVIATION → H2 = DELETE**（未降低 2SE 阈值、未换样本、未重跑、未改动作集；deviation_rate=0.0000、deviation_types={} 如实披露）。
- **P3-C 阶段实现修复（engine FIX）**：`main_model/h2_rollout/rollout_engine_v1.py` `_init_from_projections` 重建「决策时刻 in-flight calibration」资源时**未调度 calibration_complete** → 资源永久卡在校准、队列积压、日历清空、`_is_terminal()` 永假 → `run()` 沿班界推进并记录 `WAKE_UP` 无限循环（now 膨胀至 ~8M h、log 无界增长 → 首次完整运行 MemoryError/0xC0000005 失败，保留为负证据处理）。修复：重建时按 `state.time + r.in_flight_remaining_h` 调度 `calibration_complete`（与 `_begin_replacement` 一致）；另加 **fail-closed runaway guard**（`MAX_CLOSURES=1_000_000`，触发即 `RuntimeError`，将任何未来非终止转为可检测失败）。新增 3 项回归测试（`test_h2_p3c_v1.py`：calibration_completion_is_scheduled / rollout_terminates_with_in_flight_calibration / runaway_guard_raises_fail_closed）；修复后 100 样本点逐点 M=1 复检全部终止（NO RUNAWAY FOUND）。
- **新增/修改实现**：`main_model/h2_rollout/h2_policy_v1.py`（冻结政策：M_STAR/C_EVAL_STAR/W_CAP_STAR/P_CAP_STAR、ACTION_ORDER canonical、ActionEstimate/PolicyDecision、evaluate_decision_point：M 轮询 Q_hat + 配对 D_m/SE_M + 2SE confident deviation + ACTION_RANK tie-break；rollout 键覆盖 1..batch_size 全部设备——续演中 turnover 会创建后续设备，仅覆盖决策时刻已进入设备会导致 KeyError）；`main_model/h2_rollout/h2_batch_runner_v1.py`（H2BatchRunner：决策点重建→online quota（C_eval\*=8、W_cap\*=4、P_cap\*=4）→冻结政策评估→动作注入（WAIT hold / PM pending / START_HEAD·H1_NOOP 走引擎默认）；fresh batch 自动 seed TRUE_STATE_GENERATED+SHIFT_CHANGE 进引擎日志，保证后续可观测投影/决策重建看到已进入设备）；`main_model/h2_rollout/post_keys_v1.py`（rollout_post_keys 加 salt 参数：normal `q3h2-bootstrap-v1` / ALT `q3h2-bootstrap-alt-v1`；physical_post_provider 供 h2_tuning/h2_holdout 物理世界键）。
- **tests / 回归**：`tests/test_h2_p3c_v1.py` **20/20 PASS**（冻结常量/canonical 顺序/2SE 不变量/CRN+salt 分离/physical provider 确定性/H2BatchRunner smoke/CP95 独立 beta oracle 回归/calibration 回归）；回归 P1 防火墙 28 / Density E2 36 / key_schema 38 / Q3 H1 23 / G3 44 / P3-B 26 全 PASS。
- **dev budget ledger 追加**：entry `P3-C-20260816T101049163825Z_791506d8` wall_clock=685.53s；累计 **755.70s（0.2099h）**；soft 4h / hard 8h 均未达；旧 entries 保留。
- **AUTOPILOT STOP（冻结授权链）**：action stability = AUTHORIZED → 执行 → deviation_count=0 → H2 DELETE；cross-K transfer = AUTHORIZED CONDITIONAL ON STABILITY PASS → 条件未满足 → **NOT RUN**；h2_holdout / C25 = **NOT RUN**；**未创建 transfer/holdout/C25 commit**；等待 Human Gate final Q3 review。
- 范围审计：cross-K transfer、h2_holdout、C25、per-K tuning、H2 正式收益统计、Q3 K 推荐 = 全部 **NO**；P1/P2/P3-A/P3-B accepted 数学与 checker 未修改；无新 formal/holdout worlds；`development_unit` 未被本包使用。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§5.1、§6 禁止、§7 下一出口）。

## 2026-08-16 / `STATE-2026-08-13-G2.4` / `Q3-H2-P3-B-E1 current-generation residual lifetime 坐标修复 + 成本 requalification = COMPLETED / AWAITING HUMAN GATE FINAL P3-B REVIEW`

### 修改

- **Human Gate narrow repair（起始锚点 `841bafc`）：P3-B = BLOCKED / NARROW REPAIR REQUIRED（F1 current-generation residual lifetime 坐标；G1 RESULT 数字由 final evidence 生成；G2 base_runtime surrogate 如实披露）；P3-A = FINAL PASS / ACCEPTED 不受影响**。
- **F1 — 统一 lifetime_h 坐标语义**：`main_model/h2_rollout/rollout_engine_v1.py` 的 current-generation 初始化改为 **ABSOLUTE EQUIPMENT AGE OF NATURAL FAILURE** 坐标——P2 `conditional_residual_frozen` 返回 `(tau, right_censored)`（tau = 当前年龄起的 residual lifetime），现在：`right_censored=False → lifetime_h = current_age + tau`；`right_censored=True → lifetime_h = 240, is_right_censored = True`（存活至 240，无 240 前自然故障；240 边界仍由 mandatory rule 处理）。`_fragment_outcome` / `_post_fragment_end` 看到的是一致的绝对设备年龄坐标。**P2 API 保持 accepted，未修改**。
- **new-generation lifetime 保持**：replacement 后 age=0，P2/G3 无条件 inverse sampler 返回的 lifetime 本就是代出生起的绝对年龄 → `lifetime_h = sampled lifetime`，不再加 age；新增 checker guard 验证 current-generation 转换不破坏 new-generation 采样。
- **CURR-LIFE-01..05 deterministic tests**：age150+residual50→abs200；age150+failure200、task 自 age190 起 duration20 → 10h 后自然故障（非启动即 inconsistent）；age150+right-censored residual90→存活至 240；age0→退化为 G3 无条件语义；age210+residual10→abs220。
- **独立 checker**：`checker/h2_p3b_checker_v1.py` 新增 5 项——`CURRENT_GENERATION_LIFETIME`（独立计算 absolute_failure_age = current_age + residual_tau，不调 engine conversion helper 作 oracle；natural/right-censored/age0 分支 + NEW-GEN guard）、`CURRENT_GENERATION_FAILURE_TIMING`（**INDEPENDENT_FROZEN_ORACLE**，非伪 accepted-engine parity：C23 禁止向 live engine 注入 conditional posterior world；age=150、residual=3/2 → 绝对故障 151.5，fragment 中途故障、TASK_CANCEL/requeue、replacement trigger、T_end）、`RIGHT_CENSOR_240`、`NO_PM_STRING_SEMANTICS`（`_replacement_decision` 改用 `str(tau_pm) == str(NO_PM_BEFORE_MANDATORY)` 值比较，动态构造同值字符串验证不会进入 Fraction(tau_pm) 数值路径）、`NONZERO_AGE_RUNTIME_SANITY`（age≥120 current-generation 状态完整续演至吸收，不 crash / no-progress / 错误 immediate failure；仅 correctness/performance disclosure，不改冻结 c_r aggregation 或 M/C_eval selection）。
- **G2 — base_runtime surrogate 如实披露**：cost 报告/manifest/scope_audit 明确分别写 `calibration_selection_domain: h2_tuning / seed 6 / rep 0..4 / K=10.5`、`base_runtime_namespace: development_unit`、`base_runtime_role: PERFORMANCE_ONLY_BASE_SURROGATE`（Human Gate 本轮批准的唯一用途：§1.2 cost runtime 性能代理——accepted H1 engine 结构性拒绝 h2_tuning（P0/C16）；base_r 只测 engine runtime、不读物理结果、不参与收益/动作选择）；不再写成 "base batch is h2_tuning batch"。**绝不授权 development_unit 用于 action stability / cross-K transfer / h2_holdout / C25 / H2 benefit statistics**。
- **成本 requalification（§11）**：因 rollout kernel 语义修复，重新运行 final cost calibration（仍只允许三点 (4,8)/(8,6)/(8,8)；w_p≤90s、max M、M 同取大 C_eval）→ 三候选全可行（(4,8)=5.75s、(8,6)=8.48s、(8,8)=11.20s）→ 选 **(M*,C_eval*)=(8,8)、W_cap*=4、P_cap*=4 → PROVISIONAL RECONFIRMED / AWAITING HUMAN GATE FINAL FREEZE**（未利用旧 45e12558 直接宣布）。
- **G1 — RESULT 数字由 final evidence 机械生成**：runner 增加 `result_summary_from_evidence()`，最终 RESULT 的 base rows / c_r rows / median / worst / 三候选 w_p / selected config 全部从本次 final immutable 的 `cost_summary.json` + `mc_eval_selection.json` 读取；`RESULT_SOURCE_RUN_ID` 断言 = final evidence run_id（避免再次出现 evidence 与 RESULT 数字不一致）。
- **其余 P3-B regression 全部 PASS**：future D / U_Y consumption / new-generation lifetime / cross-action CRN / quota selector / quota causality / C_rollout / Q estimator / C23 rollout；P1 防火墙 28 / Density E2 36 / key_schema 38 / Q3 H1 23 / G3 44 回归全 PASS；`test_h2_p3b_v1.py` **26/26 PASS**（新增 10 项 E1 测试）；独立 checker **16/16 PASS**。
- **证据根** `05_结果/H2/tuning/cost_calibration/requalification/run_20260816T074652976919Z_60a958e8/`：checker 16/16 + tests 26/26 + 回归全 PASS + cost PASS；ACYCLIC hash DAG + manifest/inventory 31/31 + semantic mapping + C21 = PASS（fail-closed promote + 只读复验）；原 P3-B roots（`45e12558` 及 dev roots `12160c66`/`2bede6c9`/`36291377`）标记 **HISTORICAL_P3_B_EXECUTION_WITH_CURRENT_GENERATION_RESIDUAL_LIFETIME_COORDINATE_BUG**（immutable；quota/CRN/D/U_Y/Q-estimator 可作历史辅助证据；rollout kernel 终审与 cost freeze 由本 E1 覆盖）。
- **dev budget ledger 追加**：entry `P3-B-E1-20260816T074652976919Z_60a958e8` wall_clock=8.0s；累计 **70.18s（0.0195h）**；soft 4h / hard 8h 均未达；旧 P3-B entries 保留。
- **状态**：**P3-B-E1 = COMPLETED / AWAITING HUMAN GATE FINAL P3-B REVIEW**；**P3-B FINAL = NOT YET HUMAN-GATE ACCEPTED**；**M*/C_eval* = PROVISIONAL RECONFIRMED FROM E1（(8,8)、W*=4、P*=4）**；**action stability = NOT STARTED**；**cross-K transfer = NOT STARTED**；**h2_holdout = NOT AUTHORIZED**；**C25 = NOT AUTHORIZED**。
- 范围审计：action stability §4(b)(c)、cross-K transfer、h2_tuning policy experiments beyond this cost requalification、h2_holdout、C25、final H2 numbers、Q3 K recommendation = 全部 **NO**；P1/P2 math/P3-A semantics/key_schema/accepted DES/Density·H1 evidence 未修改；无新 formal/holdout worlds。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§5.1、§6 禁止、§7 下一出口）。

## 2026-08-16 / `STATE-2026-08-13-G2.4` / `Q3-H2-P3-B 完整 rollout 执行核 + (M*,C_eval*) 成本冻结 = COMPLETED / AWAITING HUMAN GATE`

### 修改

- **Human Gate 落文：Q3-H2-P3-A = FINAL PASS / ACCEPTED（accepted lineage：P3-A original `b285131` + P3-A-E1 closure `fcf07f6`；C23 mechanics/continuation = PASS；C23 full production = PENDING）；P3-B = AUTHORIZED（起始锚点 `fcf07f6`）**。
- **fresh continuation rollout event engine**：`main_model/h2_rollout/rollout_engine_v1.py`（**H2 package 外**——P1 防火墙只扫描 `main_model/h2/*.py`，引擎内部需携带重建的隐藏状态，故与 post-key adapter 同放 `h2_rollout` 包）：起点仅 ObservableState + PosteriorState + ContinuationWorld + post keys（禁 deepcopy live DES / 读 live true_state/lifetime/raw log/u_key）；首动作（START_HEAD / H1_NOOP / WAIT_EVENT / PM_WITH_HEAD / PM_IDLE）只作用于第一步，之后切回 accepted H1 baseline（NO_PM_BEFORE_MANDATORY）至 batch 吸收；same-timestamp closure 序（settle→observe→classify→exits→cancel→materialize D→shift→release→dispatch→turnovers）与 accepted engine 对齐；FCFS min-key dispatch、fragment outcome（illegal-240 后随机故障先于末端则中断、恰末端故障按完成）、replacement_decision（a+d>240 强制先换 / ==240 完成优先 / NO_PM 永不预防）、post-fragment-end 240/lifetime 检查、turnover out/in（1h_literal 与 0.5h_overlap）。
- **future D materialization（§6）**：未到 E 设备 x_D=None（DEFERRED_TO_CONTINUATION_EVENT_ENGINE）；仅在合法联接点（A/B/C 全 PASSED、E 未释放）消费一次 U_D_post、按 prior q_D 物化；提前退出不反事实生成；同 device 只生成一次。
- **U_Y_post 仅有效完成消费（§7）**：未启动 / 班末禁启 / 中断 / cancelled / equipment-failure interruption / 无结果 fragment / terminal 后取消任务一律不消费（NO_OBSERVATION_CONSUMED_BY）。
- **equipment lifetime continuation（§8）**：当前代用 P2 conditional residual（ContinuationWorld.residual_lifetimes）；每次 replacement 后新 generation 绑定新 U_L_post(resource, new_gen)（provider.u_l_lookup）；不用 P2 validation synthetic generation mapping。
- **Q_hat_M + paired SE（§1.1/§10）**：`main_model/h2/q_estimator_v1.py`——`Q_hat = 1/M Σ[T_end(m; a→H1) − t(s)]`；配对差 `D_m = T_end(a) − T_end(a_H1)`、`SE_M = sample_sd/√M`；a_H1(dispatch)=START_HEAD、a_H1(maintenance)=H1_NOOP；纯计算、不据 Q 调 M/C_eval/动作集。
- **online quota selector（§2/D-08，参数化）**：`main_model/h2/quota_selector_v1.py`——C_eval ∈ {6,8}；W_cap=⌈C/2⌉、P_cap=⌊C/2⌋（6→3+3、8→4+4）；quota class（both→WAIT 优先；quota class ≠ 动作可用性，both 点保留合法 PM 动作）；wait 在线前 W_cap 个 wait-class 点；PM 桶 B1=[120,160)/B2=[160,200)/B3=[200,240) bucket-first +（P_cap=4 时恰 1 个 extra slot）在线算法；无未来查看 / 无跨桶 backfill / 无批末回溯 / 无跨侧 borrowing；不变量 wait≤W、PM≤P、total≤C_eval、无重复 DP。
- **C_rollout 硬上限（§2）**：200/batch；候选 (4,8)→96、(8,6)→144、(8,8)→192 均 ≤200（checker 断言）。
- **H1 fallback parity（§9）**：checker 驱动 accepted H1 engine（`g3.random_des_v1`，parity target 非 oracle 循环），把同一 u 流重放进 continuation provider，6 个确定性场景（normal dispatch chain / retest / random failure / replacement / shift boundary / exact240 / terminal absorption）核心事件 + 最终 T_end 逐场景一致。
- **独立 checker 11/11 + tests 17/17**：`checker/h2_p3b_checker_v1.py`（ROLLOUT_KERNEL / H1_FALLBACK_PARITY / FUTURE_D_MATERIALIZATION / U_Y_CONSUMPTION / LIFETIME_GENERATION / CRN_WORLD / QUOTA_SELECTOR / QUOTA_CAUSALITY / ROLLOUT_COUNT / Q_ESTIMATOR / C23_ROLLOUT）+ `tests/test_h2_p3b_v1.py`；P1 防火墙回归 28 保持 PASS（引擎移至 h2_rollout 包，h2 包零 g3/des import 不变）。
- **§1.2 成本测量 + (M*,C_eval*) 冻结**：`scripts/run_h2_p3b_cost_v1.py`——前 5 批（replicate 0..4、K=10.5、batch 100）测 engine-only base_r 与 single-rollout c_r（不含 C06/C17/bootstrap）；base_median=0.264s、c_r_median=0.046s；三候选 w_p = base + (C_eval×3×M)×c_r：(4,8)=4.73s、(8,6)=6.71s、(8,8)=9.19s 全部 ≤90s 可行 → **按冻结规则（max M、M 同取大 C_eval）选 (M*,C_eval*)=(8,8)、W_cap*=4、P_cap*=4**；不存在 H2_BUDGET_INFEASIBLE。**测量命名空间说明**：base_r 在 legacy `development_unit` 下测（accepted engine 结构性拒绝 h2_tuning——P0/C16 防火墙；墙钟与键域无关；c_r 由 h2 continuation engine 在 h2_rollout post keys 下测；scope note，非规则变更）。
- **C23 rollout path（§24）**：same ObservableState + same PosteriorState + same keys + same config + same first action → 隐藏 live world 改变 → 完整 rollout T_end identical（PASS）；full final policy C23 仍 PENDING UNTIL FINAL POLICY CONFIG。
- **证据根** `05_结果/H2/tuning/cost_calibration/run_20260816T072245476180Z_45e12558/`：checker 11/11 + tests 17/17 + 回归 28/36/38/23/44 + cost PASS；ACYCLIC hash DAG + manifest/inventory 26/26 + semantic mapping + C21 = PASS（fail-closed promote + 只读复验）。
- **dev budget ledger 追加**：entry `P3-B-20260816T072245476180Z_45e12558` wall_clock=6.63s；累计 **62.18s（0.0173h）**；soft 4h / hard 8h 均未达。早期三个 dev 迭代 run（`...12160c66` / `...2bede6c9` / `...36291377`，均为 engine 迁移至 h2_rollout / evidence-mapping 修复前的中间尝试）在 ledger 标注 **SUPERSEDED_DEV_ITERATION**（墙钟保留入账，证据根 immutable 保留；最终 = `45e12558`）。
- **状态**：**P3-B rollout kernel + cost calibration = COMPLETED / AWAITING HUMAN GATE**；**M* = 8、C_eval* = 8、W_cap* = 4、P_cap* = 4**；**action stability = NOT STARTED**；**cross-K transfer = NOT STARTED**；**h2_holdout = NOT AUTHORIZED**；**C25 = NOT AUTHORIZED**。
- 范围审计：action stability §4(b)(c)、cross-K transfer §4.1、h2_tuning policy experiments、h2_holdout、C25、final H2 numbers、Q3 K recommendation = 全部 **NO**；P1/P2/P3-A accepted 未修改；未消费 h2_holdout/q3_formal；无新 formal/holdout worlds。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§5.1、§6 禁止、§7 下一出口）。

## 2026-08-16 / `STATE-2026-08-13-G2.4` / `Q3-H2-P3-A-E1 WAIT fragment identity + continuation posterior world = COMPLETED / AWAITING HUMAN GATE FINAL P3-A REVIEW`

### 修改

- **Q3-H2-P3-A-E1（Human Gate narrow repair；起始锚点 `b285131`）完成**：P3-A 主架构不推翻（两类决策点 / canonical A/B/C/E / 每资源每闭包至多 1 点 / STRICT|BOUNDARY 数值定义 / rollout_seed 公式 / CRN / P1 / P2 accepted 保持）；修复四项 + 真实回归。
- **F1 — 活动 fragment 才能成为 WAIT anchor**：`decision_point_v1._active_fragments`（exact-fragment reconstruction）取代旧的「只看 ACTIVITY_START + future end」逻辑——candidate 必须存在 ACTIVITY_START（device_id, process, effective_attempt_no, attempt_start_time）且 `start ≤ t < end`，且 ≤t prefix 中无与该 exact fragment 匹配的 ACTIVITY_COMPLETE / TASK_CANCEL（matching identity 含 attempt_start_time）；旧 CANCEL 不 settle 新 fragment、新 fragment 不被旧 CANCEL 抹掉（Density E2 fragment-aware 原则，P3 checker 独立实现、不调 Density analyzer）。
- **F2 — WaitAnchor 保存真实 in-flight event identity**：`WaitAnchor` 增加 `effective_attempt_no` / `attempt_start_time` / `resource` 字段，process 等指向**被等待的 fragment**（如 A 在跑、B 是 head → anchor.process == "A"，绝不记录成 B）；WAIT_EVENT 等待「同设备另一项当前仍 in-flight 的具体 fragment」，不是「某个时间点」。
- **WAIT candidate 确定性选择**：同一设备多 active fragments 时优先最早 completion_time；相同时 tie-break = resource A/B/C/E（process_order）→ effective_attempt_no → attempt_start_time；不依赖 event insertion order / dict 序。
- **真实 WAIT regression（WAIT-R1..R5）**：R1 cancelled old fragment 不得 anchor；R2 cancelled-then-restarted fragment（fragment2 start=2/end=4）anchor 必须 process=A、attempt_start_time=2、completion_time=4（不被 fragment1 CANCEL settle）；R3 completed fragment 不得 anchor；R4 anchor identity = in-flight A（非 head B）；R5 terminal / head-change 后下一 closure 重新 reconstruct、旧 anchor/WAIT_EVENT 不沿用。
- **F3 — continuation 每设备独立 posterior draws**：`rebuild_continuation_world(state, posterior, u_x_by_device, u_d_by_device, u_l_by_resource)`——每 entered/non-terminal 设备用自己的 U_X_post(device)、reached-E 设备用自己的 U_D_post(device)；**缺 required draw 一律 raise（fail-close），无静默 0.5 fallback**。
- **reached-E D posterior 使用 P2 PosteriorState**：采出 ABC 后 `p_D = PosteriorState.d_posterior_given_abc[ABC]`，`x_D = 1 if U_D_post < p_D else 0`；不再伪造 obs_e=() 调 sample_d(empty)、不再重读 raw log 重建 E history。
- **reached-E deterministic counterexample**：ABC 全过 + E ABNORMAL，ABC sampled=(0,0,0) 时 `P(D=1|obs,ABC=000) ≠ q_D`（q_D=1/1000，p_D≈0.0731）；选 U_D 于两者之间 → 正确 continuation draw（用 posterior）= 1，错误 prior draw = 0，证明 E→D 后验真实进入 continuation。
- **多设备 independence（§11）**：两设备同 posterior、u1/u2 落不同 categorical 区间 → 各自 ABC 不同；交换 u1/u2 → 结果随设备 key 交换；D 同理 per-device（u_d_lo→x_D=1、u_d_hi→x_D=0）。
- **rollout post-key adapter（§12）**：新增 `main_model/h2_rollout/post_keys_v1.py`（**H2 package 外**，不破坏 P1 import firewall）：`rollout_seed(dp,m) → h2_rollout namespace → U_X_post/U_D_post/U_L_post`（U_Y_post 接口仅定义不消费）；同 (dp,m,entity) 跨动作 exact identical（CRN）、不同 dp/m 分离；**不用 P2 generator-validation synthetic entity/generation mapping**。
- **F4 — PM age_before = 设备 age_h**：`apply_pm(resource, t, kind, generation, age_h)`，replacement record `age_before = age_h`（非墙钟 t）；PM-R1（t=200、age_h=135 → age_before=135）。
- **PM / mandatory 真实覆盖**：PM-R2（age=240 + 合法 head → PM_WITH_HEAD 不得成为 policy action）、PM-R3（age=240 + 其余条件满足 → PM_IDLE 不得成为 policy action）、PM-R4（age=120 → optional PM 出现）、PM_WITH_HEAD positive（age=120 + head → 出现）。
- **real H1 parity（§17）**：`check_h1_real_parity` 驱动 accepted H1 engine（`g3.random_des_v1`，parity target 非 oracle 循环）——A. START_HEAD：engine 默认 dispatch 产出 ACTIVITY_START（device 1, B, att 1, @0→2）与 P3 apply_start_head 逐字段一致；B. H1_NOOP：maintenance 态 engine 推进至真实下一事件（5/2）且无主动 PM，与 P3 apply_h1_noop 一致；不消费 formal/holdout worlds。
- **C23 continuation（§18）**：隐藏世界不同 + ObservableState/PosteriorState 相同 + 同 rollout post keys → ContinuationWorld 完全一致；同 observable 不同 (dp,m) keys → world 实际不同（差异来自冻结随机子流，非 live hidden world）。
- **独立 checker**：`checker/h2_p3_mechanics_checker_v1.py` 独立实现 `active_fragment_at`（own `_own_active_fragments` + `_own_fragment_settled`，exact identity + prefix settle matching）、`scheduled_completion_candidates`、`wait_anchor_expected`（own `_own_wait_anchor`，含 tie-break）——不复制旧逻辑、不调 Density analyzer / implementer 作 oracle；**15/15 PASS**。
- **测试**：`tests/test_h2_p3_mechanics_v1.py` **45/45 PASS**（新增 WAIT-R1..R5 / PM-R1..R4 / continuation posterior counterexample / per-device independence / fail-close / adapter CRN / C23 continuation / real H1 parity）。
- **证据根** `05_结果/H2/p3/mechanics/requalification/run_20260816T063153810486Z_1b405934/`：checker **15/15 PASS** + tests 45/45 + 回归 P1 防火墙 28 / Density E2 36 / key_schema 38 / Q3 H1 23 / G3 44 全 PASS；ACYCLIC hash DAG + manifest/inventory 一致性 + semantic evidence mapping + C21 = PASS（fail-closed；verified staging 字节一致 promote + promote 后只读复验）；原 P3-A 两 root（`...d5eafe0e` / `...a5f9bd4e`）标记 **HISTORICAL_P3_A_EXECUTION_WITH_WAIT_AND_CONTINUATION_REVIEW_FINDINGS**（immutable，未改写）。
- **dev budget ledger 追加（F2）**：entry `P3-A-E1-20260816T063153810486Z_1b405934` wall_clock=10.0243s；累计 **33.4482s（0.0093h）**；soft 4h / hard 8h 均未达；历史 P3-A entries 保留不删。
- **状态**：**P3-A-E1 mechanics requalification = COMPLETED / AWAITING HUMAN GATE FINAL P3-A REVIEW**；**P3-A FINAL = NOT YET HUMAN-GATE ACCEPTED**；**C23 = MECHANICS REQUALIFIED / FULL PRODUCTION FINAL PENDING**；**P3 tuning / M* / C_eval* / deviation threshold / action stability / cross-K transfer / h2_holdout / C25 = NOT AUTHORIZED**。
- 范围审计：M*/C_eval* 选择、deviation tuning、action stability、cross-K transfer、h2_tuning policy experiments、h2_holdout、C25、final H2 numbers、Q3 K recommendation = 全部 **NO**；P1/P2 accepted 数学/接口未修改；未执行随机 rollout、未消费随机键、无新 formal/holdout worlds。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§5.1、§6 禁止、§7 下一出口）。

## 2026-08-16 / `STATE-2026-08-13-G2.4` / `Q3-H2-P3-A 决策机制与 rollout 基础 = COMPLETED / AWAITING HUMAN GATE P3-A REVIEW`

### 修改

- **Q3-H2-P3-A（决策点重建 + canonical ordering + 五动作续演语义 + rollout_seed/CRN + continuation world + C23 end-to-end mechanics）完成**：Human Gate 授权锚点 = P2 FINAL PASS/ACCEPTED at `a5d2faf`；本包为**纯确定性机制包**（未执行随机 rollout、未消费任何随机键、不改 P2 数学）。
- **决策点重建（§2/§5/§10/§11/§12）**：`main_model/h2/decision_point_v1.py`——两类决策点（**dispatch** = 存在合法 FCFS head（E 需 A/B/C 全 PASS 前置 + 班内可完成）；**maintenance** = 无合法 head + 资源 idle + `120≤age<240` + 非 mandatory + 未来需求（未进入装置 >0 或存在未 PASS 该工序的非终态装置）+ 校准本班可完成，queue empty 或 nonempty-no-legal-head 均可）；canonical 序 **A/B/C/E**、每资源每闭包至多 1 点、`dp` = 0-based 批内索引纯函数；closure = 去重事件时刻 ∪ Q3 shift starts；WAIT 锚 = 同装置已排定完成事件 `e`（**STRICT** `t<e<latest_start` / **BOUNDARY** `e==latest_start` 合法，锚失效即重判）。
- **动作续演语义（§10）**：`main_model/h2/action_semantics_v1.py`——`START_HEAD`（只启动 FCFS 合法 head，事件字段与 H1 引擎逐字段一致）、`H1_NOOP`（无合法 head 时保持 idle 推进至下一事件，非战略等待）、`WAIT_EVENT`（推进至有限锚事件 e，无无限等待）、`PM_WITH_HEAD`（dispatch 点先 PM 再重判 head）、`PM_IDLE`（maintenance 点与 H1_NOOP 比较）；**mandatory / exact_240 永非 policy choice**（引擎事实，不进入合法动作集）。
- **rollout_seed + CRN（§6.2）**：`main_model/h2/rollout_seed_v1.py`——`rollout_seed(dp,m) = uint64_be(SHA256(UTF8("h2_rollout|"+master_seed+"|"+rep+"|"+dp+"|"+m+"|"+salt))[0:8])`；ROLLOUT_SALT=`q3h2-bootstrap-v1`、ALT=`q3h2-bootstrap-alt-v1`；**seed 不含 action/policy/strategy/run_id → 同 dp,m 所有候选动作共享同一组 m 世界（CRN）**；不同 dp / 不同 m 分离流。
- **continuation world 重建（§8/§9/§13）**：`main_model/h2/continuation_v1.py`——只从 **ObservableState + PosteriorState + 上层提供的 rollout post 键值**（U_X_ABC/U_D/U_L）重建；严禁 deepcopy live world / 读隐藏字段；终态吸收、未进入不重采样、到 E 装置 D 仅在联接点物化；残寿命用 P2 条件寿命生成器（`conditional_residual_frozen`）。
- **Q3 shift calendar 补位**：`observable_state_v1.py` 增加冻结 Q3 两班历纯函数 `q3_shift_grid(K)` / `active_shift`（implementer 自带副本，checker 保留独立副本；不 import checker）。
- **独立 checker（主硬门）**：`checker/h2_p3_mechanics_checker_v1.py`——独立重推（不调 implementer 作 oracle）：**DECISION_POINT_CLASSIFICATION**（两类点 + 合法动作集逐闭包比对，含 checker 自有 WAIT STRICT/BOUNDARY 重推）、**CANONICAL_ORDERING**、**ROLLOUT_SEED**（自有 SHA256/uint64 重推逐例相等）、**CRN_SAME_WORLD_ACROSS_ACTIONS**、**C23_MECHANICS**（隐藏世界不同/观察史相同 → ObservableState/PosteriorState/决策点/dp 逐字段一致）、**H1_PARITY**；toy logs 非空（dispatch 玩具产出 B@t0 `{START_HEAD,WAIT_EVENT}` STRICT 锚 + C@t0；maintenance 玩具产出 t=120 `{H1_NOOP,PM_IDLE}`）。
- **测试**：`tests/test_h2_p3_mechanics_v1.py` **25/25 PASS**（DP-01..05 / WAIT-01..05 / PM-01..06 / CRN-01..05 / C23-01/02 / H1-01/02 / checker overall）。
- **证据根** `05_结果/H2/p3/mechanics/run_20260816T060111865845Z_d5eafe0e/`：checker **9/9 PASS**（9 checks）+ tests 25/25 + 回归 P1 防火墙 28 / Density E2 36 / key_schema 38 / Q3 H1 23 / G3 44 全 PASS；ACYCLIC hash DAG + manifest/inventory 一致性 + semantic evidence mapping + C21 = PASS（fail-closed；verified staging 字节一致 promote + promote 后只读复验）；`dev_budget_ledger_snapshot.json` 含 ledger 快照。历史 superseded run `run_20260816T055931412559Z_a5f9bd4e/`（checker unused-import cleanup，无逻辑变更；PRIMARY mechanics 有效；ledger status = SUPERSEDED_FOR_CHECKER_CLEANUP）。
- **dev budget ledger 追加（F2）**：entry `P3-A-20260816T060111865845Z_d5eafe0e` wall_clock=5.0696s（另含 superseded `...a5f9bd4e` 5.135s）；累计 **23.4239s（0.0065h）**；soft 4h / hard 8h 均未达。
- **状态**：**P3-A mechanics = COMPLETED / AWAITING HUMAN GATE P3-A REVIEW**；**C23 = END-TO-END MECHANICS PASS（full production C23 PENDING UNTIL FINAL POLICY CONFIG）**；**P3 tuning / M* / C_eval* / deviation threshold / action stability / cross-K transfer / h2_holdout / C25 均 NOT AUTHORIZED**；不自行启动 P3 tuning。
- 范围审计：M*/C_eval* 选择、deviation tuning、action stability (b)/(c)、cross-K transfer、h2_holdout、C25、论文 H2 数字 = 全部 **NO**；P2 数学 / key_schema / DES engine / H1 / Density accepted evidence / D-01..D-25 未修改；未执行随机 rollout、未消费随机键。
- 状态同步：`CURRENT_STATE.md`（Gate 行、新增 §5.1、§6 禁止、§7 下一出口）。

## 2026-08-16 / `STATE-2026-08-13-G2.4` / `Q3-H2-P2-E1 h2_tuning 随机域隔离 + 开发预算账本 = COMPLETED / AWAITING HUMAN GATE FINAL P2 REVIEW`

### 修改

- **Q3-H2-P2-E1（h2_tuning 随机域隔离 + 开发预算账本闭环；Human Gate narrow governance requalification）完成**：P2 数学核心（后验/条件寿命）已由 Human Gate **VERIFIED PASS，本包未重写**；只修两个治理问题（F1/F2）。
- **F1 — stochastic smoke replicate 范围修正**：`run_h2_p2_v1.py` 的 smoke 不再使用 replicate_id 0..4999 / 0..1999；**所有 stochastic validation key 的 replicate_id 严格 ∈ {0,1,2,3,4}**：
  - 后验 N=5000 = 每模式 sample count：`replicate_id = sample_idx % 5`；validation-only synthetic `entity_id = 100001 + pattern_idx*1000 + floor(sample_idx/5)`（5 合法 replicate × 1000 synthetic entity slots = 5000）；synthetic id 仅用于 generator diagnostic，非真实批次 device ID，不进入 P3 rollout key 语义。
  - 寿命 N=2000 = 每配置 sample count：`replicate_id = sample_idx % 5`；validation-only synthetic `generation = 100001 + floor(sample_idx/5)`（5 合法 replicate × 400 generation slots = 2000）；resource 仍 A/B/C/E、age 不进随机键、不同 age 共享同 U 序列（CRN-style）。
  - **随机域硬检查**：新增 `POSTERIOR_RANDOM_DOMAIN` / `LIFETIME_RANDOM_DOMAIN`（实际使用 replicate：min=0、max=4、unique=[0,1,2,3,4]；任何 rep>4 FAIL；N 不减少：5000/2000）；两项全 PASS。
- **F2 — dev budget ledger**：新建 `05_结果/H2/dev_budget_ledger.json`（append-only governance record，冻结 §3）：第一条历史 entry = Q3-H2-P2 原生成器验证（run `20260816T052713579034Z_3fc5e200`、wall_clock 6.69s、status=SUPERSEDED_FOR_RANDOM_SCOPE_REQUALIFICATION、note=原 smoke 用越界 replicate、PRIMARY 数学仍有效）；第二条 = P2-E1（wall_clock 6.53s）；累计 13.22s（0.0037h）；soft 4h / hard 8h 均未达；未知历史墙钟标记 UNAVAILABLE 不猜测；证据内含 `dev_budget_ledger_snapshot.json`。
- **PRIMARY deterministic 重确认（回归，不改变数学）**：posterior 157 可达模式 / 1512 状态 / max_abs_error=0；lifetime 320 点 / max_abs_error_h=0——全 PASS（数学核心未改）。
- **新 smoke（冻结映射，只跑一次）**：后验 8 模式 × N=5000 → 32 z，`#(|z|>3.5)=0 ≤1` PASS；寿命 32 配置 × N=2000 → Pearson χ²，`#(p<0.001)=0 ≤1` PASS；未换映射/换 seed/增 N。
- **Manifest 措辞**：随机使用改为准确 `random_domain` 字段（namespace=h2_tuning、master_seed=6、replicate_ids=[0,1,2,3,4]、purpose=P2 generator validation only、N 5000/2000、h2_holdout/q3_formal/U_Y_post 均 false、new random keys outside frozen P2 domain = NO）；不再写 consumption=NONE。
- **回归**：P1 防火墙 28 + Density E2 36 + key_schema 38 + Q3 H1 23 + G3 44 全 PASS；`test_h2_p2_v1.py` 25/25 PASS；C23 P2 PASS。
- **新证据根** `05_结果/H2/p2/requalification/run_20260816T054219773348Z_14a587d7/`：ACYCLIC hash DAG + manifest/inventory 一致性 + semantic evidence mapping + C21 = PASS（fail-closed；verified staging 字节一致 promote + promote 后只读复验）；checks.json overall = PASS（12 项全 PASS）。
- **原 P2 evidence `run_20260816T052713579034Z_3fc5e200` = HISTORICAL_P2_EXECUTION_WITH_H2_TUNING_REPLICATE_SCOPE_VIOLATION**（immutable，未修改；PRIMARY 数学证据有效，SECONDARY smoke 不作最终资格证据）。
- **状态**：**P2-E1 random-domain / budget requalification = COMPLETED / AWAITING HUMAN GATE FINAL P2 REVIEW**；**P2 FINAL = NOT YET HUMAN-GATE ACCEPTED**；**P3 = NOT AUTHORIZED**；**C23 full end-to-end = PENDING**；**C25 = NOT AUTHORIZED**；不自行启动 P3。
- 范围审计：P3 / action set / decision-point injection / rollout / rollout_seed / WAIT/PM policy / M / C_eval / quota / stability / transfer / C25 = 全部 **NO**；数学核心（posterior_generator / lifetime_generator / frozen_params / PRIMARY oracle）未改；ObservableState / replacement_history / raw-u 防火墙 / Density / H1 / DES engine / key_schema / D-01..D-25 未改；未使用 h2_holdout / q3_formal。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§6 禁止、§7 下一出口）。

## 2026-08-16 / `STATE-2026-08-13-G2.4` / `Q3-H2-P2 后验缺陷状态 + 条件剩余寿命生成器 = COMPLETED / AWAITING HUMAN GATE REVIEW`

### 修改

- **Q3-H2-P1 = FINAL PASS / ACCEPTED（Human Gate 2026-08-16；closure `08488e4`；lineage P1 `db2e894` + P1-E1 `3568010` + P1-E2 `08488e4`；C23 P1-applicable = PASS / ACCEPTED；C23 full end-to-end = PENDING）**；**P2 = AUTHORIZED → 本包执行完成**。
- **P2-A 后验缺陷状态生成器（§8）**：`main_model/h2/posterior_generator_v1.py`——16-state 精确 Fraction 联合后验 `P(x_A,x_B,x_C,x_D|obs)`（已到 E 装置）+ 8-state ABC 后验（x_D 积分掉；未到 E 装置，D 不提前物化）+ 单工序似然（仅已完成有效 attempt；中断/取消/在途不计）+ E 非独立子系统（H={x_A..x_D 至少一缺陷}；E 似然只依赖 H 非空）+ 分层采样（U_X_post 采 ABC → U_D_post 采 x_D）；**推论**：H_ABC 非空 ⟹ `P(x_D=1|obs,ABC)=q_D`（E 对 x_D 无信息），仅 ABC 全清时 E 更新 D；装置级：终态吸收、未进入按先验（D 仅在续演到达联接点时按 q_D 物化一次）、未到 E 8-state、到 E 16-state。
- **P2-B 条件剩余寿命生成器（§9）**：`main_model/h2/lifetime_generator_v1.py`——`p_max(a)=[F(240)-F(a)]/[1-F(a)]`、条件逆 CDF（与 accepted G3 同一分段线性 CDF/逆，仅输入改为条件概率值）、`v>p_max` 右删失分支（τ 截为 `240-a`、survive_to_240 标记）、[0,240] CDF 不重归一（R39）、`a=0` 退化为 G3 无条件采样器、240 边界（`a+τ≤240` 才自然故障；`a+d>240` 启动前强制、`a+d==240` 完成优先——均非 optional PM）。
- **PosteriorState 正式 schema（P2）**：`posterior_state_v1.py` 由 P1 seam 升级为正式不可变 schema（`from_observable(ObservableState)` 构造；只含分布信息——后验向量/寿命条件信息，无隐藏真值/u/u_key；`P1_SEAM_STATUS=SCHEMA_IMPLEMENTED_IN_P2`）；P1 checker 的 `POSTERIOR_STATE_P1_SEAM` 检查更新为 C23 P2 合同（immutable、from_observable、无禁读字段名）。
- **独立 deterministic checker（主硬门）**：`checker/h2_posterior_checker_v1.py`（独立重推后验公式，不 import implementer core）——**157 个冻结可达模式、1512 个状态逐状态精确相等、0 mismatch**；H_ABC 非空 ⟹ D=q_D 推论 PASS；same-observable ⟹ same posterior PASS。`checker/h2_residual_lifetime_checker_v1.py`——**4 资源 × 8 年龄 × 10 U 点 = 320 点，max_abs_error=0（精确相等）**；age=0 退化 PASS；240 边界/右删失标记 PASS。
- **冻结 secondary smoke（次级，非硬门）**：后验 8 代表模式 × N=5000 × 32 边际 z，`#(|z|>3.5)=0 ≤1` PASS；寿命 32 配置 × N=2000 × Pearson χ²（E<5 并桶），`#(p<0.001)=0 ≤1` PASS；全部 z/p̂/π/χ²/obs/exp/N 入 evidence。
- **随机流（冻结）**：仅 `namespace=h2_tuning`、`master_seed=6`，消费 `U_X_post`/`U_D_post`/`U_L_post`（后验 smoke replicate 0..4999；寿命 smoke replicate 0..1999，记录于 evidence）；**未消费 U_Y_post / h2_holdout / q3_formal**；key_schema 未修改。
- **C23 继续生效**：P1 防火墙回归（field whitelist / forbidden raw-access / raw-u / import isolation / same-observable）= 28 tests PASS；C23 P2（same observable ⟹ same posterior；same key ⟹ same sampled hidden state）PASS；Density E2 36 / key_schema 38 / Q3 H1 23 / G3 44 回归全 PASS；`test_h2_p2_v1.py` **25/25 PASS**（POST-01..14 + LIFE-01..10）。
- **新证据根** `05_结果/H2/p2/run_20260816T052713579034Z_3fc5e200/`：ACYCLIC hash DAG + manifest/inventory 一致性 + semantic evidence mapping + C21 = PASS（fail-closed：verified staging 字节一致 promote 到最终根 + promote 后只读复验）；checks.json overall = PASS（10 项全 PASS）。
- **状态**：**P2 posterior + conditional lifetime = COMPLETED / AWAITING HUMAN GATE REVIEW**；**P3 = NOT AUTHORIZED**；**C23 full end-to-end = PENDING**；**C25 = NOT AUTHORIZED**；不自行启动 P3。
- 范围审计：H2 policy / action execution / rollout / Q-hat / M / C_eval / quota / h2_holdout / C25 / Q4 = 全部 **NO**；key_schema / DES engine / H1 / Density accepted evidence / D-01..D-25 未修改。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§6 禁止、§7 下一出口）。

## 2026-08-16 / `STATE-2026-08-13-G2.4` / `Q3-H2-P1-E2 raw-U 防火墙 + Evidence Packaging 最终闭环 = COMPLETED / AWAITING HUMAN GATE FINAL P1 REVIEW`

### 修改

- **Q3-H2-P1-E2（C23 raw-U 静态防火墙 + Evidence Packaging 最终闭环；Human Gate narrow final repair）完成**：P1-E1 = BLOCKED / NARROW FINAL REPAIR（F1 replacement_history completed-only = **VERIFIED CLOSED，本包未再改动**）；本包闭合 F2a / F2b / F3：
  - **F2a — raw `u` 进入 forbidden checker**：新增 `EXACT_FORBIDDEN_KEYS = ("u",)`（精确键匹配，**不**用 substring `"u"` 以免误杀 `resource`/`outcome`/`duration`）；`_scan_forbidden` 对 `ast.Attribute` / `ast.Subscript`（常量字符串键）/ `ast.Call *.get("KEY")` 同时应用 substring fragments + 精确禁读键；新增 **NEG-U1（`rec["u"]`）/ NEG-U2（`rec.get("u")`）必须拒绝**，合法片段 `rec["event_time"]` / `rec.get("resource_id")` / `rec["outcome"]` / `rec.get("duration")` 必须通过；对 `04_代码/main_model/h2/` 全量重扫：raw `u` / u_key / true_state / lifetime / x_* / d_state 值 / is_right_censored 访问 = **NONE**。
  - **F2b — Evidence 文件不得相互覆盖**：废弃模糊文件名 `ast_import_isolation_report.json`（曾被 E_NEGATIVE_LEAK_TESTS 覆盖）；改为按 check ID 精确映射：`forbidden_access_report.json`（B_FORBIDDEN_ACCESS）、`ast_negative_cases_report.json`（B_AST_NEGATIVE_CASES）、`import_isolation_report.json`（C_IMPORT_AST_ISOLATION）、`negative_leak_tests.json`（E_NEGATIVE_LEAK_TESTS）等 8 个精确报告文件；新增 **evidence semantic mapping 自检**（`evidence_mapping_check`：文件内 `check` 字段必须等于其文件名对应的 check ID——"文件是否真的声称自己是该证据"）。
  - **F3 — final root verification provenance（§7 方案 A）**：staging 完整构建（最终 file_hashes/manifest/checks）→ 对 staging 做完整验证（verify_hash_dag + verify_manifest_inventory_consistency + evidence semantic mapping）→ 全部 PASS 后以实际验证结果重建最终内容并再次验证 → **将 verified staging 字节一致 promote（copy + 逐文件 SHA 身份校验）到最终 immutable root** → promote 后只读复验；`probe 验证对象 == final accepted evidence bytes`；runner 成功退出显式依赖全部验证（probe / final-content / promote / final 四阶段），任何失败 non-zero 且不输出 overall PASS。
  - **§8 负路径真实测试**：T28 hash 篡改（生成 file_hashes 后篡改 artifact → verifier FAIL `inventory mismatches: 1`）；T26 swapped-report（`forbidden_access_report.json` 内容换成 E_NEGATIVE_LEAK_TESTS → 即使文件自身 hash 可重算，semantic mapping 也必须 FAIL）。
- **测试**：`test_h2_p1_firewall_v1.py` **28/28 PASS**（原 22 + T23 raw-u subscript rejected + T24 raw-u dict.get rejected + T25 evidence report mapping exact + T26 swapped report rejected + T27 promoted final root byte-identical + T28 hash tamper negative）；checker 8 项检查全 PASS。
- **回归（写入 evidence，真实 command/exit/test-count）**：key_schema 38、Density E2 checker 36、Q3 H1 formal 23、G3 random_des 44 —— 全部 exit 0；**未跑 formal 1400 worlds**。
- **新证据根** `05_结果/H2/p1/requalification_e2/run_20260816T050635039392Z_b8ff180e/`：ACYCLIC hash DAG + manifest/inventory 一致性 + C21 = PASS（fail-closed；verification_fail_closed 记录真实 verifier 结果）；checks.json overall = PASS（13 项：C23 / B_FORBIDDEN_ACCESS / B_AST_NEGATIVE_CASES / C_IMPORT_AST_ISOLATION / A / D / E / REPLACEMENT_HISTORY_SEMANTICS / POSTERIOR_STATE_P1_SEAM / EVIDENCE_SEMANTIC_MAPPING / TESTS / REGRESSIONS / C21）；含 4 个精确报告文件 + evidence_semantic_mapping_report。
- **原证据 immutable**：`run_20260816T043411841146Z_3d4c6d46` = HISTORICAL_P1_EXECUTION_WITH_C23_FIREWALL_REVIEW_FINDINGS；`requalification/run_20260816T045451170450Z_89984d8b` = P1-E1 EXECUTION WITH FINAL HUMAN-GATE FINDINGS——均未修改。
- **状态**：**P1-E2 EXECUTION PASS / AWAITING HUMAN GATE FINAL P1 REVIEW**；**P1 HUMAN GATE ACCEPTED = 不写**；C23 P1-applicable = EXECUTION PASS / AWAITING HUMAN GATE；C23 full end-to-end = **PENDING**；**P2 / P3 = NOT AUTHORIZED**（不授权 P2）；C25 = NOT AUTHORIZED。
- 范围审计：posterior / lifetime / policy / rollout / tuning / holdout / C25 / Q4 = 全部 **NO**；F1 replacement_history / Density / H1 / DES engine / key_schema / D-01..D-25 未改动；无新随机世界。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§6 禁止、§7 下一出口）。

## 2026-08-16 / `STATE-2026-08-13-G2.4` / `Q3-H2-P1-E1 C23 防火墙语义闭环修复 = COMPLETED / AWAITING HUMAN GATE REVIEW`

### 修改

- **Q3-H2-P1-E1（C23 信息防火墙语义闭环修复；Human Gate narrow repair）完成**：Human Gate 独立审计 P1 = BLOCKED / NARROW REPAIR REQUIRED（主体设计不推翻），本包闭合 3 个闭环（F1/F2/F3）：
  - **F1 — replacement_history 只含已完成更换/校准**：`observable_state_v1.py` 改为仅当存在匹配 `EQUIPMENT_CALIBRATION_COMPLETE` 且 `completion_time <= t` 时记录才进入 `replacement_history`（进行中 `replacement_start <= t < calibration_complete` 期间不得进入；未来完成不泄漏）；**删除 `ReplacementObs.completed` 字段**（已完成记录一律 completed，字段冗余；无 frozen authority 支持不保留）；当前状态继续由 `ResourceObs.status / in_flight_remaining_h / generation` 表达。
  - **F2 — AST checker 覆盖 dict 访问**：`check_forbidden_access` 重构为可复用 `_scan_forbidden`，除 `ast.Attribute` 外新增 `ast.Subscript`（常量字符串 slice）与 `ast.Call *.get("KEY")` 的禁读字段检测（true_state / x_A..x_D / lifetime_h / u_key / is_right_censored / d_state 值等）；新增 **AST 负例检查 `B_AST_NEGATIVE_CASES`**（NEG-A `rec["true_state"]`、NEG-B `rec.get("u_key")`、NEG-C `rec["lifetime_h"]`、NEG-D `device.true_state` 必须拒绝；合法片段 `rec["event_time"]` / `rec.get("resource_id")` 必须通过）；privileged adapter 同样受扫（不读取禁读字段；`d_materialized` 仅由 `D_CREATED` 事件存在性构建，不读 `d_state` 值）。
  - **F3 — C21/hash 验证真正 fail-closed**：runner 两阶段 evidence build（phase-1 在 git-ignored staging 目录探测真实 verifier 结果 → phase-2 以实际结果写最终 evidence；`C21a/C21b` 状态来自实际 `verify_hash_dag` / `verify_manifest_inventory_consistency`，非硬编码 PASS）；成功退出显式依赖 `hash_graph_acyclic==True`、`inventory mismatches==[]`、`manifest/inventory consistency==PASS`、`C21 consistency==PASS`；**已实证负路径**（hash 后篡改 artifact → verifier 报 `inventory mismatches: 1` → 不会输出 overall PASS）。
  - **§8 修复**：`check_field_whitelist` frozen 检查按每个 DTO 类逐一验证（修复原缩进缺陷——旧代码只检查最后一个 cls）；新增 `frozen_per_class` 逐类报告与 all-DTO-frozen 测试。
  - **§11 语义不变量**：新增 `REPLACEMENT_HISTORY_SEMANTICS` 检查（非仅字段名检查：投影真实日志，验证进行中记录不进入历史、未来完成不泄漏、完成后恰一次进入、全部成员已 completed）。
- **测试**：`test_h2_p1_firewall_v1.py` **22/22 PASS**（原 16 + T18 ongoing replacement 不入历史 + T19 完成后恰一次进入 + T20 未来完成不泄漏 + AST 负例 + all-DTO-frozen）；checker 8 项检查全 PASS（A / B_FORBIDDEN_ACCESS / B_AST_NEGATIVE_CASES / C / D / E / REPLACEMENT_HISTORY_SEMANTICS / POSTERIOR_STATE_P1_SEAM）。
- **回归（写入 evidence，真实 command/exit/test-count）**：key_schema 38、Density E2 checker 36、Q3 H1 formal 23、G3 random_des 44 —— 全部 exit 0；**未跑 formal 1400 worlds**。
- **新证据根** `05_结果/H2/p1/requalification/run_20260816T045451170450Z_89984d8b/`：ACYCLIC hash DAG + manifest/inventory 一致性 + C21 = PASS（fail-closed；C21a/b 状态 = 实际 verification）；checks.json overall = PASS（verification_fail_closed 字段记录真实 verifier 结果）；含 replacement_history_semantic_report / regression_report（真实 command/exit/test-count）。
- **原 P1 evidence `run_20260816T043411841146Z_3d4c6d46` = HISTORICAL_P1_EXECUTION_WITH_C23_FIREWALL_REVIEW_FINDINGS**（immutable，未修改）。
- **状态**：**P1-E1 C23 firewall requalification = COMPLETED / AWAITING HUMAN GATE REVIEW**；**P1 FINAL = NOT YET HUMAN-GATE ACCEPTED**；C23 P1-applicable = EXECUTION PASS / AWAITING HUMAN GATE；C23 full end-to-end = **PENDING**；**P2 / P3 = NOT AUTHORIZED**；**C25 = NOT AUTHORIZED**；不提前授权 P2。
- 范围审计：posterior / lifetime / H2 policy / rollout / tuning / holdout / C25 / Q4 = 全部 **NO**；Density accepted evidence / H1 engine / key_schema / D-01..D-25 / E2 checker runner 未修改；无新随机世界。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§6 禁止、§7 下一出口）。

## 2026-08-16 / `STATE-2026-08-13-G2.4` / `Q3-H2 DENSITY = FINAL PASS / ACCEPTED；P1 信息防火墙 = COMPLETED / AWAITING HUMAN GATE REVIEW`

### 修改

- **Q3-H2 Density Gate = FINAL PASS / ACCEPTED（Human Gate 2026-08-16）**：D-14 A 7/7（meaningful>=0.20）+ B 7/7（strict>=2/批）；accepted lineage = E1 temporal reconstruction `43fc39a`（evidence `05_结果/H2/density_recheck/run_20260815T173625059534Z_a2669aa9`）+ E2 fragment-aware checker requalification `79f5c0f`（evidence `05_结果/H2/density_recheck/checker_requalification/run_20260815T214701262919Z_0713f171`）。**P1 = AUTHORIZED**（仅 ObservableState/PosteriorState 信息防火墙 + C23 P1-applicable 条款）。
- **Q3-H2-P1 完成（ObservableState / PosteriorState information firewall + C23 P1-applicable-scope checker）**：
  - `04_代码/main_model/h2/observable_state_v1.py`：不可变 `ObservableState` DTO（冻结 §7 白名单：时间/班历/值班分队、未进入装置数 n、台位/周转、资源状态 idle/testing/failed/replacement/calibration、年龄 a_j、在途剩余 ℓ_j、代次 g_j、队列与 FCFS 键、各装置已完成观测序列与有效尝试号、D 物化仅布尔、终态、已完成更换/校准历史）+ 特权 log-prefix 投影适配器（**时间因果**：仅 event_time<=t；**fragment-aware**：fragment 只被相同 attempt_start_time 的 COMPLETE/CANCEL 结算——E1/E2 教训复用）；不保留任何原始 log/engine/device/equipment 引用；canonical dict + SHA-256 fingerprint。
  - `04_代码/main_model/h2/posterior_state_v1.py`：PosteriorState **P1 边界 seam 仅**（`SCHEMA_DEFERRED_TO_P2`；无后验数学、无 fake 数字；§8 后验/§9 条件寿命 = P2，未实现）。
  - `04_代码/checker/h2_p1_firewall_checker_v1.py`（独立 checker，不调用 H2 实现作 oracle）：A 字段白名单（递归 introspection，嵌套 DTO 隐藏信息仍算泄漏）；B 禁读字段/名称/AST 访问扫描（true_state / lifetime / u_key / x_* / is_right_censored / d_state 值）；C import/AST 隔离（H2 包不 import live DES 引擎内部类）；D same-observed-history / different-hidden-world 投影一致性（ABC / D / lifetime / future-U / 全隐藏 5 变体指纹相等）；E 负向泄漏测试（构造带禁读字段的 fixture 并证明被拒绝）；+ PosteriorState seam 无数学检查——**全部按实际条件计算（无硬编码 PASS）**。
  - `04_代码/tests/test_h2_p1_firewall_v1.py`：**T1-T17 全 PASS（16 tests）**；Q3-H1 formal / admission / Density E2 / key_schema / G3 回归全部 exit 0。
  - **证据根** `05_结果/H2/p1/run_20260816T043411841146Z_3d4c6d46/`：ACYCLIC hash DAG（RULE A）+ manifest/inventory 一致性 + C21 = PASS；checks.json overall = PASS（C23 P1-applicable / A / B / C / D / E / PosteriorState seam / TESTS / C21）。
  - **C23 措辞（冻结）**：`C23 INFORMATION-FIREWALL / P1-APPLICABLE CLAUSES = PASS`；`FULL C23 END-TO-END = PENDING`（动作/政策路径未实现；same-observed-history action-equivalence = DEFERRED_TO_POLICY_STAGE）；不写 FULL C23 FINAL PASS。
- **禁止信息零泄漏**：ObservableState 无 true_state / x_A..x_D / live U_L / live lifetime / future U / u_key / is_right_censored / 未物化 D 真值 / 原始 DES 引用；随机键防火墙保持（key_schema 未修改，不消费 u_x_post/u_d_post/u_y_post/u_l_post）。
- **状态**：P1 ObservableState/PosteriorState information firewall = **COMPLETED / AWAITING HUMAN GATE REVIEW**；C23 P1-applicable = **EXECUTION PASS / AWAITING HUMAN GATE**；C23 full end-to-end = **PENDING**；**P2 / P3 = NOT AUTHORIZED**；**C25 = NOT AUTHORIZED**；不写 P1 HUMAN GATE ACCEPTED / P1 READY TO AUTO START。
- 范围审计：posterior math / lifetime resampling / H2 policy / rollout / tuning / holdout / C25 / Q4 = 全部 **NO**；Density accepted evidence / H1 engine / key_schema / D-01..D-25 / E2 checker runner 未修改；无新随机世界。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§6 禁止、§7 下一出口）。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q3 H2 DENSITY E2 CHECKER REQUALIFICATION COMPLETED / AWAITING HUMAN GATE FINAL REVIEW`

### 修改

- **Q3-H2-DENSITY-E2（Fragment-aware independent PM_IDLE checker requalification；Human Gate E2 包）完成**：关闭 E1 Human Gate 审计发现的最后一个独立 checker 缺口——checker 的 prefix state reconstruction 未按 `attempt_start_time` 区分同一 effective attempt 的不同 execution fragments（equipment-failure / illegal-240 interruption → TASK_CANCEL → requeue → 重新 ACTIVITY_START）。
- **checker 修复（仅 `h2_q3_density_checker_v1.py`；analyzer / E1 runner 未修改）**：新增独立 `prefix_fragment_settled` / `prefix_running`（fragment identity = (device, process, effective_attempt_no, attempt_start_time)；fragment 只被相同 attempt_start_time 的 COMPLETE/CANCEL 结算）；`prefix_idle` / `prefix_head_waiting` / `prefix_legal_head` 全部 fragment-aware；新增 `prefix_available`（replacement/deferral 窗口）与 `prefix_maintenance_counts`（pm_idle + queue-empty + queue-nonempty split，含 dispatch-closure skip）；`build_prefix_index` 只记录带 attempt_start_time 的 fragment cancel（READY-task cancel 无 runtime fragment、elapsed 0，不得污染 age——首轮 E2 run 1400/1400 中 1 批（K11 rep86）因此发现并修复：checker age 误含 READY cancel → 86 个 maintenance 点漏计）；**不调用 analyzer 维护 helper 作 oracle（analyzer_functions_used_as_oracle: NONE）**。
- **T11-T15 fragment/requeue 回归**（checker run_checks + `test_h2_q3_density_v1.py`）：T11 cancel→requeue between fragments；T12 restarted fragment running（旧 fragment CANCEL 不得 settle 新 fragment——Human Gate defect 核心回归）；T13 second fragment complete；T14 PM_IDLE false during restarted fragment（age>=120、demand TRUE 下仍 MUST=0，因 resource BUSY）；T15 post-cancel legal/illegal FCFS head——**全 PASS**；测试 **36/36 PASS**。
- **accepted Tier 1 1400 worlds 确定性只读重放**：ACCEPTED_LOG_REPLAY_MATCH = **1400/1400**（q3_formal、seed 5、ids 0..199；无新随机世界、不消费 h2_tuning/h2_holdout/h2_rollout）。
- **独立 PM_IDLE 交叉校验（逐批 exact）**：checker OWN prefix pm_idle == analyzer pm_idle **1400/1400**；queue-empty split **1400/1400**；queue-nonempty-no-legal-head split **1400/1400**。
- **requeue coverage（1400 accepted logs，按 K 见 requeue_coverage.json）**：batches_with_cancelled_fragment = 311；batches_with_requeued_same_effective_attempt = 266；total_cancelled_fragments = 385；total_restarted_fragments = 287——T11-T15 非仅 synthetic，正式日志 requeue 机制已被 E2 checker 覆盖（未删除/筛选任何 batch）。
- **既有结果不变**：D-14 dispatch-side（legal_dispatch/strict/boundary/nonstrict/pm_with_head/both/meaningful/exact_240）与 E1 证据 `run_20260815T173625059534Z_a2669aa9` **逐 K 完全一致**（unchanged_dispatch_crosscheck all_equal）；D-14 阈值不变（A meaningful>=0.20 于 7/7 K；B strict>=2/批 于 >=6/7 K）= **PASS**；引擎交叉校验 forced_wait max_abs_diff=0、legal/decision points 1400/1400；mandatory/exact_240 未重设计。
- **新证据根** `05_结果/H2/density_recheck/checker_requalification/run_20260815T214701262919Z_0713f171/`：ACYCLIC hash DAG（RULE A）+ manifest/inventory/actual 一致性 + C21 report = **PASS**；checks.json overall = PASS（TEMPORAL_FRAGMENT_IDENTITY / T11_T15 / ACCEPTED_LOG_REPLAY_MATCH / PM_IDLE_INDEPENDENT_CROSSCHECK / PM_IDLE_QUEUE_SPLIT_CROSSCHECK / ENGINE_FORCED_WAIT_CROSSCHECK / UNCHANGED_DISPATCH / D14 / C21）。首轮 E2 run `run_20260815T204440346754Z_78078568`（PM_IDLE 1399/1400，checker READY-cancel age 缺陷）= INTERMEDIATE_ATTEMPT（保留不可变，被修复 run supersede）。
- **状态**：**Q3-H2-DENSITY-E2 = COMPLETED / AWAITING HUMAN GATE FINAL REVIEW**；**Q3-H2 Density Human Gate final acceptance = NOT YET**；**P1 = NOT AUTHORIZED**；**C23 = NOT AUTHORIZED**；不写 Density FINAL ACCEPTED / P1 READY TO AUTO START。
- 范围审计：P1/C23/Posterior/ObservableState/lifetime/rollout/tuning/holdout/C25/Q4 = 全部 **NO**；D-01..D-25 / key_schema / accepted H1 evidence / 旧 Density evidence / E1 final evidence / analyzer / formal seeds 未修改；`run_q3_h2_density_v1.py`（E1 runner）未修改（E2 新增 checker-only runner `run_q3_h2_density_checker_requal_v1.py`）。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§6 禁止、§7 下一出口）。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q3 H2 DENSITY TEMPORAL REQUALIFICATION COMPLETED / AWAITING HUMAN GATE FINAL REVIEW`

### 修改

- **Q3-H2-DENSITY-E1（Temporal Reconstruction Requalification；Human Gate repair package）完成**：修复 density analyzer 的 maintenance / forced-wait / mandatory 时间因果缺陷，accepted Tier 1 日志 1400 worlds 确定性重放 **ACCEPTED_LOG_REPLAY_MATCH = 1400/1400**（无新随机世界、未修改 accepted 证据目录）。
- **时间因果重建（F1-F4）**：`state_at(t)`（仅 event_time<=t）：`entered/terminal/process_passed_at_or_before`、`waiting_tasks_at`、`fcfs_head_at`（frozen FCFS：release_time/device/process_order/attempt，仅 waiting 任务）、`future_potential_demand_at`（A：entered-at-t 非 terminal 未通过；B：batch 未满）、`equipment_age_at`、`equipment_available_at`（replacement/deferral 窗口）、`resource_idle_at`；closure set = 全部 distinct canonical event_time + Q3 shift starts；每 (resource, closure) 至多一个 decision point；**mandatory 从 `EQUIPMENT_REPLACEMENT_START` kind=mandatory_240（trigger a_plus_d_gt_240 / post_completion_240 / illegal_crossing_backstop 分列）恢复**（pre-start a+d>240 在 ACTIVITY_START 上不可观测——引擎先换后启）。
- **E1 复跑两处修复（引擎交叉校验发现并闭合）**：① dispatch-closure skip——已 dispatch 的 closure 是 DISPATCH 点，不再同时计 maintenance/forced-wait；② per-fragment settle——重排队任务（equipment-failure / illegal-240 requeue）同任务身份多片段，in-flight 片段只由相同 attempt_start_time 的 COMPLETE/CANCEL 结算。修复后 **forced_wait 与引擎 c24.waiting_opportunity_count 逐批 1:1 一致**；首个 E1 run `run_20260815T163348765115Z_268e1443` = INTERMEDIATE_ATTEMPT_WITH_ENGINE_CROSSCHECK_INVESTIGATE（保留不可变，被修复 run supersede，不作 accepted 证据）。
- **旧 bug 复现（全部 REPRODUCED，输出与旧 analyzer blob `f6428090…` 入证据）**：R1 future-terminal contamination（final terminals 抑制 demand/head）；R2 future-release contamination（t=5 看到 t=10 的 release）；R3 delayed-start stale waiting（release=0 start=5 在 t=6 仍 waiting）；R4 future-PASS contamination（E prereq 读到未来 PASS）；R5 PM_IDLE suppression（final DEVICE_TERMINAL -> old pm_idle=0，new=1）；R6 mandatory undercount（old anchor 计数=0，new=1）。
- **独立 checker 升级**：`h2_q3_density_checker_v1.py` 8 边界例 + **T1-T10 时间回归** + checker 自己的 log-prefix 独立复算（不调用 analyzer 作 oracle）= **全 PASS**；`test_h2_q3_density_v1.py` **31/31 PASS**；Q3-H1 formal / admission / G3 回归全部 exit 0。
- **引擎交叉校验（逐批 1400/1400）**：`legal_dispatch + mandatory_a_plus_d_gt_240 == c24.legal_action_count`；`+ forced_wait == c24.decision_point_count`；`forced_wait == c24.waiting_opportunity_count`（forced-wait 仪表；仅诊断 crosscheck，不作 STRICT/BOUNDARY/meaningful）。
- **D-14（冻结口径，PM_IDLE 不进分母）**：Condition A meaningful>=0.20 于 **7/7 K** = PASS（0.4310–0.4548）；Condition B strict>=2/批 于 **7/7 K** = PASS（7.20–26.16）；**DENSITY REQUALIFICATION EXECUTION = PASS / AWAITING HUMAN GATE FINAL REVIEW**（不写 HUMAN GATE ACCEPTED；P1 未开始）。
- **OLD vs NEW 逐 K**：UNCHANGED_EXPECTED（legal_dispatch / strict / boundary / nonstrict / pm_with_head / both / exact_240 / meaningful fraction）= **逐 K 完全一致**；EXPECTED_TO_BE_REQUALIFIED（forced_wait：old 0 -> new ≈引擎 waiting（9.7k–36.2k/K）；pm_idle：old 0 -> new 时间因果 maintenance 计数（66.4k–83.1k/K）；mandatory：old ~0 -> new mandatory_240 替换事件 579/K；maintenance points；zero-action diagnostics）如实报告。
- **旧 Density run `run_20260815T153339475783Z_4a867e83` = HISTORICAL_DENSITY_EXECUTION_WITH_TEMPORAL_RECONSTRUCTION_DEFECT**（immutable；未修改、未覆盖、未删除）；1400/1400 physical replay match 本身不声明错误。
- **新证据根** `05_结果/H2/density_recheck/run_20260815T173625059534Z_a2669aa9/`：ACYCLIC hash DAG（RULE A）+ manifest/inventory/actual 一致性 + C21 report = **PASS**；checks.json overall = PASS（D-14 / TEMPORAL / UNCHANGED_EXPECTED / ENGINE_CROSSCHECK / C21 / C15 / REPLAY）。
- **状态**：Q3 H1 FORMAL = **FINAL PASS / ACCEPTED**（不变）；Q3 H2 DENSITY = **TEMPORAL REQUALIFICATION COMPLETED / AWAITING HUMAN GATE FINAL REVIEW**；H2 = **NOT YET AUTHORIZED FOR P1**；**P1 = NOT AUTHORIZED**（P1/C23/C25 仍须 Human Gate 另发授权）。
- 范围审计：Tier 2/3、P1、C23、C25、h2_tuning/holdout、rollout、posterior、tau 重调、key_schema、D-01..D-25 重设计、Q4 = 全部 **NO**；admission analyzer（`h2_admission_opportunity_analyzer_v1.py`）未修改；G3 core 未修改。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§6 禁止、§7 下一出口）。

## 2026-08-15 / `STATE-2026-08-13-G2.4` / `Q3 H2 DENSITY RECHECK = PASS（H2 = ELIGIBLE_FOR_P1_HUMAN_GATE_REVIEW）`

### 修改

- **Q3 七 K H2 opportunity-density recheck = PASS（Q3-H2-DENSITY 包；D-14 预注册下限全满足）**。数据源 = Q3 H1 **Tier 1 accepted** 日志（`single_test_unconditional_v1 × 1h_literal × NO_PM_BEFORE_MANDATORY × 7 K × 200 批 = 1400 worlds`，accepted physical run `run_20260815T133840057668Z_7ee48fc0`），**确定性只读重放**（namespace=`q3_formal`、master_seed=5、replicate_ids 0..199、逐 K 同配置）；**未消耗任何新随机世界、未修改 accepted 证据目录**。
- **ACCEPTED_LOG_REPLAY_MATCH = 1400/1400**：逐批 `canonical_log_sha256` 与 accepted cell artifact 完全一致（不足 1400 → FAIL/STOP 不写证据）。
- **独立 checker** `04_代码/checker/h2_q3_density_checker_v1.py`（不调用 analyzer 的 classify 作 oracle，独立复算）：8 个确定性边界小例（STRICT / BOUNDARY / NONSTRICT-not-legal / PM_WITH_HEAD / PM_IDLE queue-empty / PM_IDLE forced-wait / exact_240 / mandatory）+ K 特定班历边界 + `e==latest_start` + 队列非空无合法头 + `a+d==240` + `a+d>240` + 确定性 / 资源规范顺序 A/B/C/E = **全 PASS**；测试 `04_代码/tests/test_h2_q3_density_v1.py` **21/21 PASS**；Q3 H1 formal 回归测试仍 exit 0。
- **D-14 门槛（逐 K 实测）**：meaningful_choice_fraction = K09 0.4380 / K09p5 0.4548 / K10 0.4331 / K10p5 0.4310 / K11 0.4329 / K11p5 0.4338 / K12 0.4372 → Condition A **7/7 K ≥ 0.20 = PASS**；strategic_wait_strict_per_batch = 12.45 / 26.16 / 9.76 / 7.20 / 9.05 / 7.79 / 11.27 → Condition B **7/7 K ≥ 2 = PASS**；**overall = PASS**。BOUNDARY 合法 WAIT 单列（407/16/18/146/40/417/274）不并入 STRICT；PM 密度不补偿 wait；不跨 K 平均；不降阈。零机会批次 = 0/1400；pm_idle = 0（维护点条件全满足的 PM-only 机会在本数据集中为 0，描述性计数，非门槛）。旧 admission 密度（413.1/11.4/168.8/0.429）仅作描述性对照，非门槛。
- **证据根** `05_结果/H2/density_recheck/run_20260815T153339475783Z_4a867e83/`：ACYCLIC hash DAG（RULE A）+ manifest/inventory 一致性（复用 `verify_hash_dag` / `verify_manifest_inventory_consistency`，fail-closed）= **HASH_GRAPH_ACYCLIC = PASS、INVENTORY = 20/20、MANIFEST_OUTPUT_HASHES = 19/19、MANIFEST_INVENTORY_CROSSCHECK = 19/19、C21_REPORT_SHA_CONSISTENCY = PASS**；`C21_REQUALIFICATION_REPORT.json` verdict = PASS；家族墙钟 1687.2 s。
- **状态**：**H2 = ELIGIBLE_FOR_P1_HUMAN_GATE_REVIEW（非授权）**；**P1 = NOT YET AUTHORIZED**（P1 / C23 / C25 / rollout / posterior 仍须 Human Gate 另发授权）；Q3 = ACTIVE（H1 accepted；K 推荐措辞不变：k\*=K12 strong、co-best=[]，限于七个 K + 冻结 H1 政策集）。
- **范围审计**：Tier 2 / Tier 3 / P1 / C23 / C25 / h2_tuning / h2_holdout = 全部 **NOT RUN**；G3 core / `key_schema_v1`（accepted P0 扩展）/ tau_pm 未改动；无新随机世界。
- 状态同步：`CURRENT_STATE.md`（Gate 行、§6 禁止、§7 下一出口）。

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
