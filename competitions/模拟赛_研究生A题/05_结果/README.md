# 结果目录规范

`05_结果/` 是本项目唯一运行结果根目录。是否已有正式运行结果只看项目根 `CURRENT_STATE.md` 和本目录中的实际 `run_manifest.json`。

## 1. 运行目录

每次运行使用不可变目录：

```text
05_结果/
└─ G2/
   └─ run_YYYYMMDD_HHMMSS_<shortid>/
      ├─ run_manifest.json
      ├─ config.yaml
      ├─ checks.json
      ├─ calibration_report.json
      ├─ quality_anchor.json
      └─ logs_or_tables...
```

阶段可为 `G2/`、`G3/`、`formal/`、`sensitivity/`。不得使用 `final2`、`最终最新版` 等可覆盖命名；运行目录生成后不得静默改写。

## 2. `run_manifest.json` 最低字段

- `run_id`、创建时间、Gate、用途（debug/pilot/tuning/heldout/formal）；
- 问题契约版本、`registry_version`、所需检查 ID；
- `parameters.csv` 哈希、配置文件及哈希；
- 代码版本或代码树哈希、环境摘要；
- 随机主种子与键规范版本；
- 输入、输出文件清单及 SHA256；
- 检查报告路径和整体状态；
- 是否允许进入论文数字来源表。

## 3. 数字冻结

- debug、手算 fixture 和外部评审估值不得标记为 formal；
- 只有适用硬门全部通过、失败样本已处理且 manifest 完整的结果，才能进入 `06_论文/数字来源表.md`；
- `figures/` 中的每张正式图必须记录来源 `run_id`、数据文件和作图脚本；
- 删除或覆盖任何运行目录前必须由队伍明确授权。

## 4. 结果组织（按题目号导航）

```text
05_结果/
├─ G2/   # 历史 Gate 证据；内含 Q1（第一问）不可变 accepted run
├─ G3/   # 公共随机 DES / H1 开发证据
├─ H2/   # H2 challenger 证据
├─ Q1/   # Q1 导航 + 派生 final handoff（数字权威仍在 G2）
├─ Q2/
├─ Q3/
├─ Q4/
└─ governance/
```

- **Q1 的原始不可变正式证据仍在 `05_结果/G2/run_20260814T130947069958Z_4bb92eda/`**（G2-02 = 第一问「概率与质量解析链」，按开发 Gate 组织时期完成）。
- `Q1/` 目录（`README.md` / `final_handoff/` / `final_closure/`）只用于**按题号一致导航**，**不是新的正式运行**；其数值全部机械派生自 G2 accepted run，不重新计算。
- 导航/摘要与原始 evidence 冲突时，以原始 accepted run 为准（见 `05_结果/Q1/final_closure/Q1_FINAL_AUTHORITY_MAP.json`）。
