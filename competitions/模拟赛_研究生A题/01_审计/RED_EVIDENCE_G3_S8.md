# RED/GREEN 调查证据：G3 S8 holdout C07 统计烟测方法缺陷（GE 小期望单元）

> 级别：GREEN（纯实现统计方法缺陷；未触碰任何冻结契约/锚/语义/代码路径）
> 日期：2026-08-14
> 任务：G3-SPEC-V1.0 S8 holdout（CR-V3.1/C07 统计烟测）
> 关联 run：修复前 `05_结果/G3/holdout/run_20260814T175532413681Z_eba82d4b`、
>          `run_20260814T175933514681Z_1dfbec68`（保留不可变）；
>          修复后正式 run 见 `05_结果/G3/holdout/`（本文件落文时以 `run_manifest.json` 为准）

## 1. 现象

首次正式 holdout（100 独立 100-device 批次，namespace=g3_holdout，
master_seed=2，冻结 tau_pm=198h）结果：

- C06/C17：100/100 批全 PASS（硬门全过）；
- C07 四格烟测：flagged=16/100（预期 ~5），`investigate_flag=True`；
- C07 lambda 烟测：经验 mean=9.76 事件/批 vs 解析锚 9.6785（相对偏差 0.8%，吻合）。

四格总数与冻结解析锚对比（10000 台）：

| 类别 | 观测 | 解析期望 | 差异 |
|---|---|---|---|
| GP | 9250 | 9250.94 | -0.94 |
| BP | 196 | 181.63 | +14.37 |
| GE | 9 | 8.15 | +0.85 |
| BE | 545 | 559.28 | -14.28 |

GP 与"带问题总数"（BP+BE=741 vs 740.9）均与锚吻合；BP/BE 的 ±14 属
Multinomial(10000, p) 正常波动（SD≈13.3）。

## 2. 根因（可定位差异，两处统计方法缺陷）

**缺陷一（GE 小期望单元）**：flagged 的 16 批中 8 批 GE≥1 且 8/8 全超界。
GE 类别解析概率 p_GE=0.000815 → 单批期望 N·p_GE=0.0815 << 1，卡方检验对
期望<1 的单元 χ² 近似不适用（单个 GE=1 使该类别贡献 ~10.3，直接假阳性）。

**缺陷二（统计量形式错误，主因）**：初版 runner 的批级统计量采用
`X² = Σ (n_i-Np_i)² / (N p_i (1-p_i))`（方差加权 z² 之和）。该量**不是
Pearson 卡方**，渐近分布不是 χ²(2)；对占主导的 GP 类别（p≈0.925），
`(1-p)` 因子把其贡献放大 ~13.3 倍，使 flag 率系统性偏高（修复前
flagged=15/100，预期 5）。改用标准 Pearson 形式
`X² = Σ (n_i-Np_i)² / (N p_i)`（GP/BP/BE 三类、2 df、95% 临界值
5.99146...）后，同一批数据 flagged=7/100（Binomial(100,0.05) 下
期望 5、SD 2.18，属正常波动）。四格总数与锚全部吻合（z_tot 均 |z|<1.1）
→ 引擎随机生成正确，失配全部来自统计检验方法错误。

## 3. 修复（GREEN；仅 runner 统计方法，未改冻结物）

`04_代码/scripts/run_g3_holdout_v1.py`：

- 批级统计量改为标准 Pearson 卡方 `Σ (n_i-Np_i)²/(Np_i)`，类别取期望充分
  的 GP/BP/BE（2 df，95% 临界值 5.99146...）；GE 作为单独诊断计数报告
  （观测 vs 期望 8.15/10000），不进入 X²（标准小期望单元规则）；
- `batch_chi_square` 返回 (chi2, z, counts)；z 仅作逐单元诊断保留；
  新增 `ge_diagnostic`；
- `C07_CHI2_2DF_95`、`C07_CHI2_CATEGORIES=(GP,BP,BE)`、
  `C07_GE_DIAGNOSTIC_CATEGORY=GE`；`family_smoke_diagnosis` 默认临界值改 2df；
- per-run 字段更名 `c07_chi2_2df_pearson`；
- `04_代码/tests/test_g3_holdout_v1.py` 同步更新（23 测试，含
  `test_chi2_is_pearson_form_over_adequate_cells`、
  `test_ge_excluded_from_chi2`）。

未改动：key_schema、寿命/再生、random_des、C06 oracle、C17 replay、
参数、锚、协议、候选集、tau_pm。holdout 绝不重调。

## 4. 裁决记录

- 现象与根因均已机械复现（GE≥1 批次 8/8 超界；Pearson 形式下同批数据
  flagged 15→7，回到 Binomial(100,0.05) 正常波动）；
- 修复为 GREEN 级（纯实现统计方法缺陷，冻结 oracle/锚/语义明确，无
  新接口接缝）；不升级 YELLOW/RED；
- 修复前 run `eba82d4b`、`1dfbec68` 保留不可变（C07 方法缺陷产物，
  非 accepted）；
- 修复后正式 holdout 重新运行，C07 flagged 应回到 ~5 的偶然水平；
- C07 为统计烟测/诊断（miss_handling：单次普通 95% 未覆盖触发调查，
  不自动判程序错误；diagnostics_only 规定诊断输出，不挑结果）；
  整体验证状态仍由 C06/C17 硬门决定。
