# RED 调查证据：Q2 首跑暴露 G3 accepted C17 checker C10 缺陷

> 级别：**RED → Human Gate**（Q2-FORMAL-SPEC-V1.0 §6：修改 C17 replay core = Q2_FORMAL_REQUIRES_G3_CORE_CHANGE，必须 STOP 回 Human Gate，不静默 patch）
> 日期：2026-08-15
> 任务：Q2 H1 FORMAL 首跑（AUTOPILOT PILOT #3）
> 关联 run：`05_结果/Q2/formal/run_20260815T043849677911Z_daead4cf`（**保留为不可变失败证据**，VALIDATION_FAILED，非论文权威）

## 1. 现象

Q2 正式族首跑（8 cells × 200 batches × 100 devices，namespace=q2_formal、master_seed=3、ids 0..199）完成：
族墙钟 1275.5 s；**C06 = 200/200 PASS（每单元）**，但 **C17 = 195/200**（5 批 FAIL），overall = VALIDATION_FAILED。

C17 非 PASS 分布：
- chain 单元（4 个）：各 5 批 FAIL（replicate 15/143/144 等；因 CRN 复用，同一批 replicate 在 4 个 chain 单元同批失败）
- single+1h+nopm：1 批 FAIL（replicate 88）

## 2. 根因（可复现，checker 独立重推逻辑缺陷）

以 chain+1h+tau198 rep15 device 23 为例：
- 真状态：B=true、C=true（U_X canonical）。
- DES 日志：B attempt1 ABNORMAL → B attempt2 ABNORMAL → **DEVICE_EXIT(process=B, attempt=2)**；C attempt1 ABNORMAL → C attempt2 ACTIVITY_START（已启动）→ 被 B 退出 **TASK_CANCEL（DEVICE_EXIT 原因），C attempt2 OBSERVATION 数 = 0**（片段取消，无观测、不推进）。
- **C06 oracle = PASS**（独立 oracle 逐装置全等：terminal=EXITED、final=exit、差异=[]）。DES 行为正确。
- **C17 checker 的 C10 缺陷**（`g3_replay_checker_v1.py` L720-770 派生 `exit_processes` + L1686-1698 判定）：
  - checker 用 canonical U 无条件重推 C 的 attempt2 观测：`u_C2 < 1-beta_C` → ABNORMAL（该 U 确为异常区）。
  - 于是 `exit_processes = [B, C]`，与 DES 记录的 `DEVICE_EXIT.process = B` 不符 → C10 误报。
  - **checker 未检查"被取消片段不得消费观测 U、不推进 attempt"**（G3-SPEC §2 frozen："中断/取消无观测、不推进 effective_attempt_no"）——它把未实际完成的 attempt2 的 canonical U 重推结果错误纳入退出链。

同一机制解释其它 FAIL：
- chain 单元：任何"工序 ABNORMAL 且其 attempt2 将被另一工序退出取消"的多异常真状态组合都会触发。
- single+1h+nopm rep88：single 语义下同机制（E 或 A/B/C 的 attempt2 被取消）。

## 3. 严重性评估

- **DES / C06 正确**：C06 独立 oracle 200/200 PASS 证明引擎路径全等正确。
- **checker C10 重推缺陷**：违反"取消片段无观测"冻结语义，是 **G3 accepted C17 checker 的核心缺陷**，由 Q2 formal 首次触发（G3 阶段仅用 single kernel 且样本未命中该组合，302 tests 未覆盖）。
- 影响：本正式 run 的 C17 硬门失败；**G3 accepted C17 结论在"取消 attempt2 观测重推"边界上需要复核**（G3 阶段 302 tests 全过但该路径未被覆盖）。

## 4. 处置（遵循 Q2 spec §6 与治理）

- **不静默 patch G3 accepted checker**。修改 C17 replay core 属于
  `Q2_FORMAL_REQUIRES_G3_CORE_CHANGE` → **STOP 回 Human Gate**。
- 本 run 保留为不可变失败证据（VALIDATION_FAILED、paper_authoritative=False）。
- 待 Human Gate 裁决方向（候选）：
  A. 授权修复 C17 checker C10（YELLOW 级，bounded：exit_processes 派生须先判"attempt2 实际完成观测"，取消片段不推进），并出 INVALIDATION_REPORT + 重跑 checker 全量回归（含新增 chain 取消路径测试），再重跑 Q2 formal；
  B. 裁定 Q2 chain 单元另作处理；
  C. 其它（Human Gate 指定）。

## 5. 附注（runner 聚合精度）

Q2 runner 的 checks.json 将 C06/C17 用同一 `all_ok` 判 FAIL（C06 实际 200/200 PASS）。这是 runner-only 聚合细节（非 G3 core），可在修复时顺带精确化（C06 与 C17 分开计数）。
