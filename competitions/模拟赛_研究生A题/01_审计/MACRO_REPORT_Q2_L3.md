# Q2 H1 FORMAL Macro L3 终审报告（Q2_FORMAL_MACRO_L3_REVIEWER）

> 日期：2026-08-15
> 结论：**overall_decision = PASS / confidence = HIGH / formal_result_integrity = HIGH**
> freshness = VERIFIED；read_only = VERIFIED
> 状态：**Q2_FORMAL_MACRO_L3_PASS_WAITING_FOR_HUMAN_GATE**（无条件停机；不自动 land Q2 FINAL PASS）

## 0. Reviewer 与机械验证

- Reviewer：`Q2_FORMAL_MACRO_L3_REVIEWER`（workflow 派发恰 1 个 fresh child，read_only，无孙级）。
- Session：`137d4fc1-d2de-4f49-a250-f1418703604f`；runtime 机械验证（session JSONL 解码）= **deepseek-official / deepseek-v4-pro / high**（request/header + request/context 一致）。

## 1. 审阅的完整 provenance 链

1. 首跑失败 run `run_20260815T043849677911Z_daead4cf`（HISTORICAL_FAILED_FORMAL_ATTEMPT / VALIDATION_FAILED / paper_authoritative=false，未改动）；
2. RED 证据 `RED_EVIDENCE_Q2_FIRST_RUN_C17.md`；
3. Human Gate OPTION A → C10 cancelled-attempt 修复（`INVALIDATION_REPORT_G3_C17_CANCELLED_ATTEMPT.md`，commit `023020e`）；
4. Human Gate OPTION A2 → C12 terminal-horizon 修复（`INVALIDATION_REPORT_G3_C17_TERMINAL_HORIZON.md`，commit `b300473`）；
5. combined G3 C17 requalification（`REQUALIFICATION_RECORD_G3_C17.md`；reviewer `G3_C17_REQUALIFICATION_L3_REVIEWER` PASS/HIGH，session `ab890743`）；
6. **clean reissue run `run_20260815T061803446274Z_2d1466ba`**（全 8 cells C06/C17 各 200/200 = 1600/1600 PASS）；
7. 新旧确定性 DES 数学等价（1600 批逐字段 0 差异；仅 21 条 checker 判定 FAIL→PASS 翻转 + wall_clock，属允许差异）；
8. 统计族（4 对比 Bonferroni + bootstrap + rare-event CP）。

## 2. 正式结果表（唯一论文数字来源候选，待 Human Gate 接受）

主单元 = single_test_unconditional_v1 × 1h_literal；政策参考 = 同观测/周转 + NO_PM_BEFORE_MANDATORY。
Delta_T = T(tau_pm_198) − T(NO_PM)；98.75% 边缘 bootstrap CI（Bonferroni m=4, alpha_each=0.0125, B=10000, seed=30003, percentile 0.00625/0.99375）。

| 对比 | 角色 | 观测 | 周转 | ΔT (h) | CI (h) | 解释 |
|---|---|---|---|---|---|---|
| C1 | PRIMARY | single | 1h | **+1.289** | [0.463, 2.194] | 完全>0 → 支持 NO_PM 更短 T |
| C2 | ROBUSTNESS | single | 0.5h | +4.229 | [3.198, 5.296] | 完全>0 → NO_PM 更短 |
| C3 | ROBUSTNESS | chain | 1h | −0.128 | [−1.115, 0.800] | 含 0 → 不可稳定区分 |
| C4 | ROBUSTNESS | chain | 0.5h | +5.321 | [4.131, 6.623] | 完全>0 → NO_PM 更短 |

**要点**：主对比 C1 的 CI 完全>0，按冻结解释规则 = **NO_PM 更短 T（tau_pm=198 候选在主单元未改善完成时间，约慢 1.3h）**。不得改写或隐藏该方向；不重调 tau_pm。

质量（稀有事件，池化 20000 台，精确 Clopper-Pearson）：chain PL=212→[0.00923,0.01212]、PW=17→[0.00050,0.00136]；single PL=383→[0.01730,0.02115]。PL/PW 在 tau198 与 NO_PM 单元**完全相同**（CRN 配对正确；质量分布不随政策变，符合 C06 分离命题）。

## 3. Reviewer 结论与建议

- 证据链完整、内部一致、可复现（bootstrap 与 CP 独立重算吻合）；哈希端到端核验通过；G3 核心无漂移。
- paper_number_source_recommendation：Q2 论文数字唯一来源（Human Gate 接受后）= `run_20260815T061803446274Z_2d1466ba/formal_comparison_table.json` + `rare_event_report.json`；逐字段引用，不手录/外推。
- 非阻塞观察（记录）：①checks.json 中 C13/C14/C18 为 runner 断言（engine hash 一致 + C17 全量重放覆盖语义 + G3 315 回归）；②REQUALIFICATION_RECORD 有重复段落（文档卫生）；③x=0 单侧 CP 分支本轮未触发（已实现，符合 DEC-04）。

## 4. 停机

Q2 Macro reviewer 后 **STOP UNCONDITIONALLY**。不自动 land Q2 FINAL PASS、不写论文数字、不实现 H2、不启动 Q3/Q4、不重调 tau_pm。等待 Human Gate。
