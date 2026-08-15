# INVALIDATION_REPORT：G3 C17 terminal-horizon calibration replay

> 日期：2026-08-15
> 触发：Q2 失败 run（run_20260815T043849677911Z_daead4cf）在 cancelled-attempt 修复后只读重放时，发现残余 C12 失败（single+1h+nopm rep88）
> 依据：Human Gate OPTION A2 APPROVED（G3_C17_PATCH_RESIDUAL_FAILURE → 授权第二个 bounded checker 修复）

## 1. 变更分类

| 维度 | 值 |
|---|---|
| changed_semantics | **NO**（冻结语义不变：T=末台 DEVICE_TERMINAL 时刻；占用/记账地平线=[0,T)；a+d=240 完成先结算、同闭包强制替换不扩展 T；不新增"末台跳过强制替换"例外） |
| changed_main_engine | **NO**（random_des_v1 未改；t=T 的替换/代次/U_L/计数/分类保持冻结闭包语义） |
| changed_checker_core | **YES**（g3_replay_checker_v1.py：C12/C17 资源占用/校准地平线逻辑） |
| changed_key_schema | **NO** |
| changed_lifetime_model | **NO** |
| changed_observation_kernel | **NO** |
| changed_H1_policy | **NO** |
| changed_tau_pm | **NO** |

## 2. 缺陷与修复（摘要）

- 缺陷：checker C12/C17 把**整个计划校准区间** `[calibration_start, calibration_end)` 当作资源占用并要求 `end <= T`；但占用/记账定义于 `[0, T)`。末台 terminal 同闭包内触发的强制替换（计划 calibration_end > T、无 post-T 完成事件）被误报 "busy interval ends after T"。
- 修复：占用使用**半开地平线交集** `effective = [cs, min(ce, T))`；`cs >= T` 时贡献 0（不制造零长区间触发无关 "end<=start"）。**计划区间合法性/班界检查仍用原始 `[cs, ce)`**（duration 匹配、起始合法、不跨班界等保持严格）。
- 关键区分（冻结）：**计划区间合法性 vs 有效 [0,T) 占用**是两个独立概念；**test 片段不被 relax**（真实 test end>T 仍 C12 FAIL）；**任何 event_time > T 的事件记录仍 C12 FAIL**；**容量/重叠检查用 effective interval 且严格**。
- 未改动：main DES、key_schema、寿命/再生、观测语义、C06 oracle core、G3-SPEC、问题契约、CR-V3.1、tau_pm。

## 3. 受影响的 accepted 声明

- **CR-V3.1/C17 G3 full replay layer**：保持 **REQUALIFICATION_REQUIRED**，直到 combined（C10+C12）patched checker 通过最终 requalification。
- **第一个 C10 cancelled-attempt 修复不被无效化**：本报告为**独立的第二个 checker 缺陷**。
- 明确不全局失效：C06/C13/C14/C16/C18/C26、key_schema_v1、lifetime/regeneration、random DES core、H1 tau_pm=198（本修复调查未发现实际受影响）。

## 4. 旧证据地位

- G3 原始证据与 Macro report 保持不可变历史证据。
- Q2 首跑 = HISTORICAL_FAILED_FORMAL_ATTEMPT / VALIDATION_FAILED / paper_authoritative=false（不追溯升级）。

## 5. 修复后验证（见 REQUALIFICATION_RECORD_G3_C17.md 更新）

- A2 回归 7 tests（A2-1..A2-7）全 PASS；cancelled-attempt 6 tests 保持 PASS。
- 全量 G3 回归 315 tests OK（skipped=1）；Q2 runner 13 tests OK。
- accepted G3 holdout 只读重放：100/100 PASS。
- 失败 Q2 run 只读重放：C06 与 C17 分开报告；旧 21 个 C17 失败（20 chain C10 + 1 single C12）全部闭合。
