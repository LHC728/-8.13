# G3 C17 Requalification Record（cancelled-attempt 修复，supplemental）

> 日期：2026-08-15
> 状态：**部分 requalification——cancelled-attempt 缺陷（C10）已修复并闭合；发现残余独立缺陷（C12 terminal 同刻替换收尾）→ STOP: G3_C17_PATCH_RESIDUAL_FAILURE**
> 依据：Human Gate OPTION A APPROVED；`01_审计/INVALIDATION_REPORT_G3_C17_CANCELLED_ATTEMPT.md`

## 1. 绑定（hash）

| 项 | 值 |
|---|---|
| 旧 checker hash（修复前） | 提交 `6adc57c` 时的 g3_replay_checker_v1.py |
| 新 checker hash（修复后） | 本记录关联提交的 g3_replay_checker_v1.py（见 git diff） |
| 精确 diff | `git diff HEAD -- 04_代码/checker/g3_replay_checker_v1.py`（仅 derive_device_chain 签名 + completed_observations 过滤 + 调用点传入） |
| INVALIDATION_REPORT | `01_审计/INVALIDATION_REPORT_G3_C17_CANCELLED_ATTEMPT.md`（changed_semantics=NO / changed_main_engine=NO / changed_checker_core=YES / 其余 NO） |
| main DES hash 不变 | 未触碰 `random_des_v1.py`（git diff 空） |
| key_schema/lifetime/G3 spec hash 不变 | 未触碰（git diff 空） |

## 2. 回归输出（修复后）

- **targeted 新增 checker 回归（6 tests，全部 PASS）**：A chain cancelled-attempt2（exit=[B]）；B single 等价；C 同刻双退出保留；D 中断 attempt2 无假退出；E cancelled attempt2 无观测（outcome 无关）；core repair unit（completed_observations 过滤）。
- **全量 G3 回归：308 tests OK（skipped=1）**（302 原有 + 6 新增；原 PASS 全部保持）。
- **accepted G3 holdout 只读重放（patched checker）：100/100 PASS**（兼容性保持，旧 accepted 证据无需重写）。
- **失败 Q2 run 只读重放（patched checker）**：
  - chain 单元 4×5 = 20 批旧 C10 失败：**全部闭合**（cancelled-attempt 缺陷修复）。
  - single+1h+nopm rep88：**残余 C12 失败**（不同根因，见 §3）。

## 3. 残余缺陷（独立，未在本授权内修复）

- **现象**：`resource(E).busy: busy interval ends after T (expected='<= T', actual='2468/3')`，仅 Q2 seed=3 rep88（single+1h+nopm）1 批。
- **根因**：末台 DEVICE_TERMINAL(822) 的同刻闭包内，设备 E 触发替换+校准（EQUIPMENT_REPLACEMENT_START 822, calibration_end=2468/3=822.67）；SIMULATION_END 在同刻 822 记录（末台 terminal 优先停止 T），但替换校准 completion 时间 822.67 写入事件。checker C12 将 [822, 822.67) 视为忙区间"越界 T"。
- **判定**：DES 的 T=822（末台 terminal）符合冻结语义；末台后设备替换收尾的 completion 不应影响 [0,T) 忙区间覆盖。**checker C12 对"terminal 同刻设备替换收尾"的边界处理缺陷**（与 cancelled-attempt 无关）。
- **影响范围**：G3 holdout 100/100 PASS（不触发）；仅 Q2 seed=3 特定世界触发。**cancelled-attempt 修复的有效性不受影响**。
- **处置**：按 Human Gate §9 规则（残余失败且根因不同 → STOP: G3_C17_PATCH_RESIDUAL_FAILURE），不自动扩大 patch。

## 4. 结论与建议

- cancelled-attempt 修复（OPTION A）已完成并验证：C10 缺陷闭合、G3 全量回归 PASS、holdout 兼容。
- **存在第二个独立 checker 边界缺陷（C12）** → 按规则 STOP，回 Human Gate。
- 建议（候选）：授权第二个 bounded checker 修复（C12：忙区间覆盖仅 [0,T) 内实际执行活动；terminal 同刻替换收尾的 completion 不计入越界），或裁决其它方向。修复后再做完整 requalification + Q2 reissue。
- 旧 Q2 run 保持 HISTORICAL_FAILED_FORMAL_ATTEMPT / VALIDATION_FAILED / paper_authoritative=false（不追溯升级）。
