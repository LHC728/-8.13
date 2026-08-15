# Q2-FORMAL-SPEC-V1.0 评审记录与修复对照

> 日期：2026-08-15
> 阶段：Q2_H1_FORMAL_SPEC_DESIGN（Q2 FORMAL SPEC DESIGN = AUTHORIZED；Q2 FORMAL RUN = NOT YET AUTHORIZED）
> 状态：**初评 FAIL（两项实质问题）→ 修复 → Human Gate CONDITIONAL PASS → Phase A 全部决策落文 → Phase B fresh FINAL spec review → 冻结条件满足后 FROZEN_FOR_FORMAL_RUN**

## 0. Phase A 更新（Human Gate 2026-08-15 CONDITIONAL PASS 决策落文）

Human Gate 已裁决 Q2-FORMAL-DEC-01..06 及 bootstrap 分析随机性，全部精确落文至 `Q2_单班制H1正式评估.yaml`：

- DEC-01：200 批/单元 × 8 单元 = 1600 批；每批 100 台 → 160 000 device-simulations；不得事后增减；硬资源失败 STOP 回 Human Gate。
- DEC-02：namespace=q2_formal、master_seed=3、replicate_id=0..199（恰 200）；8 单元 CRN 复用同一 200 ids；禁注入 policy/turnover/observation/run_id/execution_no/restart_no；key_schema_v1 byte/semantic 保留。
- DEC-03：恰 4 个配对 Delta_T 对比（C1 PRIMARY single+1h；C2/C3/C4 ROBUSTNESS）；Bonferroni m=4、alpha_each=0.0125、双侧、边缘 coverage 0.9875、percentile 0.00625/0.99375；解释规则；不事后重调。
- DEC-04：PL/PW 池化 20000 台；0<x<20000 → 精确 CP 双侧 95%；x=0 → 单侧 CP 95% 上界 `1-0.05^(1/20000)` 机械计算；批级均值/SE；零事件禁正态 CI；质量结论从属 C06/解析锚。
- DEC-05：族级根 `05_结果/Q2/formal/run_<UTC>_<8hex>/`；冻结 8 cell tokens（obs_single/chain__turn_1h/0p5h__policy_tau198/nopm）；token→config 机械映射；族根最小内容清单；失败尝试不可变。
- DEC-06：soft 4h / hard 8h；hard cap 无条件停止；不削减重复数。
- bootstrap 分析流：namespace=q2_formal_analysis_bootstrap_v1、analysis seed=30003、B=10000；仅重采样 200 个完整配对批次索引。
- `decision_required: []`（无任何决策留给实现者）。
- 观测绑定冻结（禁止再标定）+ G3 core 保护条款（Q2_FORMAL_REQUIRES_G3_CORE_CHANGE）。

## 1. Reviewer 与机械验证

- Reviewer：`Q2_FORMAL_SPEC_L3_REVIEWER`（workflow 派发恰 1 个 fresh child，read_only，无孙级）。
- 路由：`agent({provider: "deepseek-official", model: "deepseek-v4-pro"})`。
- **runtime 机械验证**（Harness session JSONL 多帧 zstd 解码，session `558ea880-983c-4181-9aeb-ff17ade6cf6d`）：
  - `request/header` config = `provider: deepseek-official, model: deepseek-v4-pro, maxTokens: 256000, reasoningEffort: high`；
  - `request/context` = `deepseek-official / deepseek-v4-pro / contextWindow 1000000`。
- 结论（评审时点）：**overall_decision = FAIL / confidence = HIGH**；freshness = VERIFIED；read_only = VERIFIED。

## 2. 评审发现（16 项 + 2 方法项）

| # | 项 | 初评 | 处置 |
|---|---|---|---|
| 1 | 冻结上游绑定 | **FAIL**（g3_spec_hash 错误） | 已修复：`2553ad5d…` → 真实文件 SHA-256 `b818f92a5fb90acd9bda6052e8e16d425452a73b9e6951b1eb3279fb4912e796`（与 G3 全部 run manifest / S9 evidence task_package_hash 一致）；tau_pm=198 冻结、无重调/重开网格/事后选择 192-204、NO_PM 参考正确 |
| 2 | 8 单元情景族 | PASS | — |
| 3 | 主/敏感性预声明 | PASS | — |
| 4 | 正式样本量 200 | PASS | — |
| 5 | CRN 规则 | PASS | — |
| 6 | Q2 班历/初态 | PASS | — |
| 7 | 正式输出契约 | PASS | — |
| 8 | 主估计量 | PASS | — |
| 9 | 统计程序（bootstrap+Bonferroni B=10000 95%；4 对比族；稀有事件精确单侧） | PASS | — |
| 10 | checker 要求 | PASS | — |
| 11 | C07 边界 | PASS | — |
| 12 | 证据/论文权威 | PASS（附 1 项依赖：上游 hash 修复后追溯链完整） | 随 1 修复 |
| 13 | 无 H2/Q3/Q4 泄漏 | PASS | — |
| 14 | 运行时预算 | **FAIL/INFO**（"0.5-1.2 s/批"不可追溯） | 已修复：改标"本地运行观察、非 manifest 固化数据"，正式 runner 记录逐批 wall-clock；soft 4h / hard 8h 保留且进 decision_required |
| 15 | decision_required | PASS（6 项真实未决） | — |
| 16 | 实现者决策自由度 | INFO（label→token 映射未显式） | 已补：label_to_token_mapping（literal_1h→1h_literal、full_overlap_0_5h→0.5h_overlap、tau_pm_198→Fraction(198)、NO_PM→哨兵） |
| M1 | 观测核可构造性 | PASS（single/chain 均 UNIQUE_SOLUTION；chain q_E=0.047150339332016366、E alpha/beta 冻结） | — |
| M2 | 引擎可实施性 | PASS（通用 observation_kernel 接口；0.5h_overlap 已支持；8 单元无需引擎语义变更） | — |

scope_leak_check：无 H2/Q3/Q4 泄漏、无调优泄漏、无 q2_formal 随机世界消费。治理注记（INFO）：授权 premise "Q2 FORMAL SPEC DESIGN = AUTHORIZED" 尚未写入 CURRENT_STATE/CHANGELOG —— 属冻结落文阶段事项，本轮不处理。

## 3. 修复对照（本文件落文时已验证）

- `g3_spec_hash` = `b818f92a…`（Get-FileHash + S9 manifest 双重一致；旧值 `2553ad5d…` 已移除）。
- runtime_budget_proposal：`observed_g3_perf` 明确标注"本地运行观察（近似），非 G3 manifest 固化数据；正式 runner 应记录真实 wall-clock"。
- `label_to_token_mapping` 补齐 6 个 label 的 engine token / 冻结数值 / accepted 输出绑定。

## 4. 返回 Human Gate 摘要

- draft 路径：`08_项目管理/任务包/Q2_单班制H1正式评估.yaml`（302 行；untracked，按 §20 draft 约定未 commit）
- reviewer session/runtime：`558ea880-983c-4181-9aeb-ff17ade6cf6d` / deepseek-official / deepseek-v4-pro / high
- reviewer 初评：FAIL / HIGH（两项实质问题均已在草案内修复；修复后关键点机械验证 PASS）
- decision_required（6 项）：200 批可行性 / replicate-id 范围与 master seed / Bonferroni 族编码 / 稀有事件区间实现 / 证据目录命名 / 运行时软硬上限
- 正式重复数：200 批 × 8 单元 = 1600 批；每批 100 台 → 160 000 device-simulations（预估 1-2 h 本地运行）
- 比较族：4 个预声明配对政策对比（T）：1 主（字面观测+1h 周转+tau_pm_198 vs NO_PM）+ 3 稳健（其余观测×周转组合）
- 改动文件：仅 `08_项目管理/任务包/Q2_单班制H1正式评估.yaml`（新增，untracked）
- git diff：无已跟踪文件变更；工作树新增 1 个 untracked draft

## 5. Phase B/C：FINAL spec review 与冻结

- **FINAL reviewer**：`Q2_FORMAL_SPEC_FINAL_L3_REVIEWER`（workflow 派发恰 1 个 fresh child，read_only，无孙级）。
- **Session**：`698f74c3-d26b-4742-9270-e079b65b82a6`；runtime 机械验证（session JSONL 解码）=
  `request/header` config `deepseek-official / deepseek-v4-pro / high`（maxTokens 256000, reasoningEffort high）。
- **结果**：**overall_decision = PASS / confidence = HIGH / implementation_ready = YES**；
  unresolved_concerns = 2 条治理性（非阻塞）；freshness = VERIFIED；read_only = VERIFIED。
- **初评 FAIL 发现闭合**：Finding A（g3_spec_hash 真实文件 SHA-256 `b818f92a…`，与 G3 manifest/S9 evidence 一致）= PASS；Finding B（runtime 标为非权威规划估计 + 正式 runner 记录 wall-clock）= PASS；Finding C（label→token 映射显式全量 + single 观测绑定 Q1 冻结 q_E）= PASS。
- **Human Gate 决策落文**：DEC-01..06 + bootstrap 分析随机性全部机械核对 PASS；`decision_required: []`；实现者零决策自由。
- **冻结**：status = `FROZEN_FOR_FORMAL_RUN`；AUTOPILOT PILOT #3 = ACTIVE（Q2 H1 FORMAL → Q2 Macro Gate 无条件停机）。
- **两条非阻塞治理意见处置**：①授权 premise + DEC-01..06 落文 CURRENT_STATE/CHANGELOG → 在冻结落文阶段完成；②§0 approval_gate 措辞澄清（FINAL PASS 是冻结前提，运行激活来自 Human Gate 预授权而非 reviewer 自动授权）→ 已修订草案 §0。

## 6. 停止边界

Q2 FORMAL RUN 冻结后执行至 Q2 Macro Gate 无条件停机；H2/Q3/Q4/论文写作未授权。
