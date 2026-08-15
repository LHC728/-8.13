# G3 C17 Requalification Record（C10+C12 组合修复，supplemental）

> 日期：2026-08-15
> 状态：**C10（cancelled-attempt）与 C12（terminal-horizon calibration）两处独立 checker 缺陷均已修复；combined patched checker 全量回归 + 只读重放验证；等待 fresh Pro/high requalification reviewer**
> 依据：Human Gate OPTION A + OPTION A2 APPROVED；`01_审计/INVALIDATION_REPORT_G3_C17_CANCELLED_ATTEMPT.md` + `01_审计/INVALIDATION_REPORT_G3_C17_TERMINAL_HORIZON.md`

## 1. 绑定（hash）

| 项 | 值 |
|---|---|
| 旧 checker hash（修复前） | 提交 `6adc57c` 时 g3_replay_checker_v1.py |
| C10 修复后 hash | 提交 `023020e` 时 g3_replay_checker_v1.py（INVALIDATION_REPORT_CANCELLED_ATTEMPT） |
| C12 修复后 hash（combined） | 本记录关联提交 g3_replay_checker_v1.py（INVALIDATION_REPORT_TERMINAL_HORIZON） |
| 精确 diff | `git diff` 各修复提交：C10 = derive_device_chain completed_observations；C12 = busy/calibration horizon clip |
| INVALIDATION_REPORT ×2 | CANCELLED_ATTEMPT（C10）+ TERMINAL_HORIZON（C12）；均 changed_semantics=NO / main_engine=NO / checker_core=YES |
| main DES hash 不变 | 未触碰 random_des_v1.py（git diff 空） |
| key_schema/lifetime/G3 spec/Q2 spec hash 不变 | 未触碰（git diff 空） |

## 2. 回归输出（combined patched checker）

- **C10 cancelled-attempt 回归（6 tests）**：A/B/C/D/E + core repair unit 全 PASS（chain cancelled-attempt2 exit=[B]；single 等价；同刻双退出保留；中断 attempt2 无假退出；cancelled+pass-U 无观测；completed_observations 过滤）。
- **C12 terminal-horizon 回归（7 tests，A2-1..A2-7）全 PASS**：A2-1 替换恰在 T 且计划 end>T 无 post-T 完成事件 → PASS；A2-2 有效占用 clip 于 T、busy_total 仅 pre-T；A2-3 test 片段不被 clip（全部 test_intervals ≤ T）；A2-4 event_time>T 记录仍 FAIL；A2-5 计划校准跨班界仍 FAIL（raw 检查）；A2-6 [0,T) 内重叠仍容量 FAIL；A2-7 Q2 seed3 rep88 残余闭合。
- **全量 G3 回归：315 tests OK（skipped=1）**（308 + 7 新增；原 PASS 全保持）。
- **Q2 runner 回归：13 tests OK**。
- **accepted G3 holdout 只读重放（combined patched checker）：100/100 PASS**。
- **失败 Q2 run（daead4cf）只读重放（C06/C17 分开）**：旧 21 个 C17 失败（20 chain C10 + 1 single C12）**全部闭合**；C06 各单元 200/200。

## 3. 结论与建议

- C10 + C12 两处独立 checker 缺陷均按 Human Gate OPTION A / A2 完成 bounded 修复；combined patched checker 全量回归 + accepted holdout 重放 + 旧失败 run 重放全部干净。
- **Requalification reviewer（§14）`G3_C17_REQUALIFICATION_L3_REVIEWER`（session `ab890743-3260-4a22-9af1-5a6c4383be56`，runtime 机械验证 deepseek-official/deepseek-v4-pro/high）= PASS / HIGH / changed_semantics_assessment=NO / c17_requalified=YES / g3_final_pass_reuse_allowed=YES，无阻塞关切**。
- **CR-V3.1/C17 G3 full layer = PASS / REQUALIFIED_AFTER_C10_C12_CHECKER_FIXES**；G3 = PASS / ACCEPTED（supplemental C17 requalification provenance）。
- 旧 Q2 run 保持 HISTORICAL_FAILED_FORMAL_ATTEMPT / VALIDATION_FAILED / paper_authoritative=false（不追溯升级）。
- Q2 clean reissue 与 Q2 Macro L3 在 requalification 通过后执行。

## 1. 绑定（hash）

| 项 | 值 |
|---|---|
| 旧 checker hash（修复前） | 提交 `6adc57c` 时的 g3_replay_checker_v1.py |
| C10 修复后 hash | 提交 `023020e` 时 g3_replay_checker_v1.py（INVALIDATION_REPORT_CANCELLED_ATTEMPT） |
| C12 修复后 hash（combined） | 提交 `b300473` 时 g3_replay_checker_v1.py（INVALIDATION_REPORT_TERMINAL_HORIZON） |
| 精确 diff | C10 = derive_device_chain completed_observations（签名+过滤+调用点）；C12 = busy/calibration horizon clip（raw [cs,ce) 用于合法性/班界，effective [cs,min(ce,T)) 用于占用） |
| INVALIDATION_REPORT ×2 | CANCELLED_ATTEMPT（C10）+ TERMINAL_HORIZON（C12）；均 changed_semantics=NO / main_engine=NO / checker_core=YES |
| main DES hash 不变 | 未触碰 `random_des_v1.py`（git diff 空） |
| key_schema/lifetime/G3 spec/Q2 spec hash 不变 | 未触碰（git diff 空） |

## 2. 回归输出（combined patched checker）

- **targeted 新增回归（13 tests 全 PASS）**：C10 族 6 tests（chain cancelled-attempt2 exit=[B]；single 等价；同刻双退出保留；中断 attempt2 无假退出；cancelled+pass-U 无观测；completed_observations 过滤）+ C12 族 7 tests（A2-1..A2-7：替换恰在 T 计划 end>T 无 post-T 完成 → PASS；有效占用 clip 于 T；test 片段不被 clip；event_time>T 记录 FAIL；计划校准跨班界 FAIL；[0,T) 重叠容量 FAIL；Q2 seed3 rep88 残余闭合）。
- **全量 G3 回归：315 tests OK（skipped=1）**（308 + 7 新增；原 PASS 全保持）。
- **Q2 runner 回归：13 tests OK**。
- **accepted G3 holdout 只读重放（combined patched checker）：100/100 PASS**（兼容性保持，旧 accepted 证据不重写）。
- **失败 Q2 run 只读重放（C06/C17 分开）**：旧 21 个 C17 失败（20 chain C10 + 1 single C12）**全部闭合**；完整 8×200 重放 C06/C17 = 200/200 per cell（ALL_CELLS_CLEAN）。

## 3. Requalification reviewer 裁决（2026-08-15）

- **overall_decision = PASS / confidence = HIGH**；changed_semantics_assessment = NO；c17_requalified = YES；g3_final_pass_reuse_allowed = YES；无阻塞关切。
- 审阅确认：C10 根因正确、patch 最小、同刻多退出保留、独立重推保持、隔离不变；C12 根因正确、占用地平线 [0,T)、test 不 relax、event>T 记录仍 FAIL、容量严格、raw 合法性/班界单独检查、t=T 替换不静默移除；315+13 测试、holdout 100/100、旧 21 失败闭合均独立复算 PASS；git 范围仅 checker+tests+reports；失效范围正确（C06/C13/C14/C16/C18/C26 未全局失效）。
- 非阻塞建议（记录）：①旧 C10-only 正文已归档为本文件历史附录（下方）；②Q2 runner checks.json C06/C17 分开计数——run_q2_formal_v1.py `_write_evidence` 仍用合并 all_ok（C06 与 C17 同判），属 runner-only 报告精度，将在 Q2 clean reissue 时顺带修正（不改变本次 checker 修复）；③失败 run cells/*.json 未持久化 replay_issues 字段——证据完整性小缺口，已在 RED evidence 叙事与记录中说明。

## 4. 历史附录（C10-only 阶段记录，superseded by combined record）

以下为 OPTION A（cancelled-attempt）修复阶段的历史正文，现由上方 combined 记录取代；保留以供追溯，不再作为当前状态。

### 4.1 残余缺陷（当时发现，现已在 OPTION A2 修复）

- **现象**：`resource(E).busy: busy interval ends after T (expected='<= T', actual='2468/3')`，仅 Q2 seed=3 rep88（single+1h+nopm）1 批。
- **根因**：末台 DEVICE_TERMINAL(822) 的同刻闭包内，设备 E 触发替换+校准（EQUIPMENT_REPLACEMENT_START 822, calibration_end=2468/3=822.67）；SIMULATION_END 在同刻 822 记录（末台 terminal 优先停止 T），但替换校准 completion 时间 822.67 写入事件。checker C12 将 [822, 822.67) 视为忙区间"越界 T"。
- **判定**：DES 的 T=822（末台 terminal）符合冻结语义；末台后设备替换收尾的 completion 不应影响 [0,T) 忙区间覆盖。**checker C12 对"terminal 同刻设备替换收尾"的边界处理缺陷**（与 cancelled-attempt 无关）。
- **处置**：按 Human Gate §9 规则（残余失败且根因不同 → STOP: G3_C17_PATCH_RESIDUAL_FAILURE），已由 OPTION A2 授权修复（见上方 §2 C12 族）。
