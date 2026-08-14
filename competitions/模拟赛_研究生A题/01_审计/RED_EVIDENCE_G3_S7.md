# RED EVIDENCE PACK — G3 Pilot #2 S7（2026-08-14）

> 触发点：S7 H1 调优运行暴露 S3/S5 两处验收级实现缺陷；调优结果标注 VALIDATION_FAILED。
> 性质：RED（涉及冻结 C11 FCFS 语义与 checker 验收正确性）。**未静默修复**；等待 Human Gate。
> 复现脚本（scratch，gitignored）：`tmp/red_fcfs_repro.py`。

## 发现 A — S3 引擎：FCFS 派工取头违反冻结最小键序（C11）

- **文件**：`04_代码/main_model/g3/random_des_v1.py`
- **机理**：`_equipment_and_dispatch`（line 1772）派工直接取 `queue[0]`（入队序头），不按冻结 FCFS 键全序重排；而 `_release_tasks`（line 1690-1719）入队序 = creations（device_id 排序）→ retests → E。
- **违反**：冻结 C11「选择当前合法候选最小键」；冻结 FCFS 键 `(release_time, device_id, process_order, effective_attempt_no)` 字典序。
- **最小复现**（`tmp/red_fcfs_repro.py`，机械确认）：
  - 同 release_time=5 时：retest 键 `(5, d5, B, 2)` < creation 键 `(5, d6, B, 1)`（device_id 5<6）
  - 但入队序：creations 先入（device 6），retests 后入（device 5）→ `queue[0]=(5,d6,B,1)` → 派工先派 device 6，违反最小键
- **影响**：同 release_time 下 retest 与 creation 竞争时派工序错误；调优（tau_168/192/216/NO_PM 受影响，rep=4 复现 D95_B 重测被 D96_B 首测插队）；**调优结果有效性受损**。
- **修复方向（待裁决）**：派工取头前对 WAITING 队首候选按 FCFS 键全序选择最小者（或入队按键序插入）；修复后用**同一 20 CRN worlds** 重跑 S7（世界与策略无关）。

## 发现 B — S5 checker：同刻多台退出时 DEVICE_EXIT/DEVICE_TERMINAL 跨装置误配（C18 误报）

- **文件**：`04_代码/checker/g3_replay_checker_v1.py`
- **机理**：`first_last`（line 2234-2238）在同一时间戳 group 内收集**全部装置**某类型 seq 取全局 min/max；`check_pair`（line 2251-2258）用 `last(A.seq) >= first(B.seq)` 判序。多台同刻退出时跨装置比较无意义。
- **最小复现**（S7 rep=9，t=465，dev56/dev57 同刻退出）：dev57 EXIT seq1394 > dev56 TERMINAL seq1393 → 全局 last(EXIT)=1394 ≥ first(TERMINAL)=1393 → 误报"C18 EXIT 必须严格先于 TERMINAL"（实为不同装置）。
- **影响**：14/200 调优运行 C17 误 FAIL（tau_144 时刻表偏移未触发、20/20 PASS）；checker 验收正确性受损。
- **修复方向（待裁决）**：check_pair 按 device_id 配对后比较（或仅同装置内判序）；修复后 checker 重跑（引擎日志无需重跑）。

## 其他（子 Agent 报告、非 RED）

- 解释性：tie-break 规则 3「NO_PM 最不激进获胜」按全平局最不激进者获胜实现；E 核取 Q1 冻结 q_E 经冻结闭式重算，与 Q1 输出 alpha_E/beta_E 差 ~6e-18（Q1 输出 18 位舍入）。均已落文。
- 中间调优运行：`05_结果/G3/tuning/` 4 个目录（`b9fe7d80`/`33da177a`/`09e7d0b7` 中途 + `48028e83` 交付），数字相同、三重可复现；保留为不可变中间证据（处置待裁决）。

## 需要 Human Gate 裁决

1. 发现 A：确认引擎缺陷 → 授权修复（键序取头）+ 同 20 CRN worlds 重跑 S7？
2. 发现 B：确认 checker 缺陷 → 授权修复（按 device_id 配对）？
3. 中间调优运行处置：保留 or 清理？
4. 修复后 S7 重跑协议确认？
