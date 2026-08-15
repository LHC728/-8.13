# INVALIDATION_REPORT：G3 C17 cancelled-attempt replay semantics

> 日期：2026-08-15
> 触发：Q2 首跑（run_20260815T043849677911Z_daead4cf）暴露未覆盖的 cancelled-attempt2 路径
> 依据：Human Gate OPTION A APPROVED（Q2_FORMAL_REQUIRES_G3_CORE_CHANGE → 授权 bounded checker-core repair）

## 1. 变更分类

| 维度 | 值 |
|---|---|
| changed_semantics | **NO**（冻结语义不变：取消/中断无观测、不推进 attempt；被取消/未完成 attempt 不得因其 canonical U_Y 本会 ABNORMAL 而被当作有效 ABNORMAL） |
| changed_main_engine | **NO**（random_des_v1 未改） |
| changed_checker_core | **YES**（g3_replay_checker_v1.py：derive_device_chain 的 exit_processes 派生边界） |
| changed_key_schema | **NO** |
| changed_lifetime_model | **NO** |
| changed_observation_kernel | **NO** |
| changed_H1_policy | **NO** |
| changed_tau_pm | **NO** |

## 2. 缺陷与修复（摘要）

- 缺陷：`derive_device_chain()` 在 attempt1 ABNORMAL 时无条件 canonical 求 attempt2 观测；若 attempt2 实际被取消/未完成（无 OBSERVATION），仍可能把其 canonical ABNORMAL 计入 `exit_processes`，产生反事实 `[B,C]` 而真实路径为 `[B]`。
- 修复：`derive_device_chain` 增加 `completed_observations`（该设备实际完成的 (process, attempt) 观测集合）；attempt2 仅在 **实际完成观测** 且 canonical outcome=ABNORMAL 时才成为 exit process。被取消/中断/未启动/班推迟的 attempt2 永不因其 counterfactual U 成为退出工序。checker 仍独立重推 canonical U 验证实际完成的观测（保持独立重放性质）；DEVICE_EXIT.process 仍是被检查值而非预期来源。同刻两个 attempt2 均真正完成观测时，多退出集按冻结批结算语义保留。
- 未改动：DES core、key_schema、寿命/再生、观测语义、C06 oracle core、G3-SPEC、问题契约、CR-V3.1、tau_pm。

## 3. 受影响的 accepted 声明

- **CR-V3.1/C17 G3 full replay layer**：受 checker 缺陷影响 → 临时分类 **REQUALIFICATION_REQUIRED**。
- **G3 Macro L3 acceptance**：insofar as it relied on the old C17 checker → 需 supplemental requalification provenance。
- **Q2 首跑验证状态**：VALIDATION_FAILED（保留）。
- 明确**不**全局失效：CR-V3.1/C06、C13、C14、C16、C18、C26、key_schema_v1、lifetime/regeneration、random DES core、H1 tau_pm=198 候选（除非修复调查证明其实际受影响——本修复调查未发现）。

## 4. 旧证据地位

- G3 原始证据与 Macro report 保持不可变历史证据，不重写。
- Q2 首跑 = HISTORICAL_FAILED_FORMAL_ATTEMPT / VALIDATION_FAILED / paper_authoritative=false（即使修复后 checker 可重放其日志，也不追溯升级）。

## 5. 修复后验证（见 requalification record）

- targeted 新 checker 回归（cancelled-attempt2 等 5 类）
- 全量 G3 测试回归（原 PASS 保持 + 新增）
- accepted G3 holdout 只读重放（兼容确认）
- 失败 Q2 run 只读重放（原 false C17 失败应全部闭合，残余另行识别）
- runner-only C06/C17 聚合修正（reporting-only，changed_semantics=NO）
