# H2 ADMISSION EVIDENCE L3 REVIEW RECORD

> 日期：2026-08-15
> 阶段：H2 ADMISSION EVIDENCE AUDIT ONLY（Human Gate；H2 实现 = NOT AUTHORIZED）
> 结果：**v2 reviewer = PASS / HIGH / evidence_integrity=HIGH**；advisory：**h2_opportunity_density_classification = MODERATE**；**h2_admission_recommendation = ADMIT_FOR_DESIGN**

## 1. Reviewer 与机械验证

- Reviewer：`H2_ADMISSION_EVIDENCE_L3_REVIEWER`（workflow 派发恰 1 个 fresh child，read_only，无孙级）。
- **v1**（session `—`，初评）：**FAIL**——发现 analyzer 设备年龄未在替换处重置（引擎 age=0），误分 mandatory（37→0）、高估 fraction（0.446→0.429）；holdout 只用前 20 批；无持久化输出/committed runner；draft §5 百分比不一致。
- **v2**（session `2cea14f5-4d6b-491d-b845-795b47cfccc2`，runtime 机械验证 = deepseek-official / deepseek-v4-pro / high）：**PASS / HIGH / evidence_integrity=HIGH / MODERATE / ADMIT_FOR_DESIGN**。

## 2. v2 审阅结论（8 项全 PASS，机械验证）

1. **年龄重置修复确认真实完整**：`_equipment_age_at` reset-aware（gen_start=最近替换 ≤ t，仅计该代次 ACTIVITY_COMPLETE/TASK_CANCEL 片段 elapsed，排除校准）；探针 NO_PM rep0/1/2/19 引擎 age（A=15 B=204 C=15 E=75）与 analyzer 逐资源匹配；served 资源 age 永不超 240（max B=204）、mandatory=0 全单元。
2. **修正后聚合确认**：tuning_NO_PM mandatory=0.0、exact_240=2.7、pm_feas=168.8、meaningful=177.05、fraction=0.4287（取代 v1 buggy 37.5/3.0/176.4/184.2/0.446）。
3. **strategic-wait 分类年龄无关且正确**（构造上只用同装置完成调度 vs latest_start，从不读 age）：strict NO_PM=11.4、tau198=13.6、holdout=13.5；STRICT/BOUNDARY/NONSTRICT 独立；test_e 锁 BOUNDARY 不静默判等。
4. **holdout 全 100 批**（n=100：strict=13.5、pm=127.09、fraction=0.336）。
5. **持久化输出 + committed runner 可复现**：`run_h2_admission_evidence_v1.py` exit 0、140 log_hashes 全验证（20+20+100）、输出与 `tmp/h2_admission_analysis.json` 字节一致。
6. **draft §5 百分比内部一致**（wait-only/PM-only/both/无可选 ≈ 100%）。
7. **治理/泄漏干净**：untracked 恰 4 文件（analyzer/tests/runner/draft）、0 modified、tmp/ gitignored；analyzer stdlib-only 无 main DES import；runner 只读 G3 tuning+holdout（不读 q2_formal）；无 H2 实现、无新随机世界。
8. **无正式性能声明**：仅机会/分支密度。

## 3. 非阻塞关切（3 条，均为 Human Gate scope 决策，非证据缺陷）

- 密度由可选 PM 主导（~41%）；纯 strategic-wait 稀疏（~2.8%）。H2 是否值得预算取决于 scope 是否含可选 PM（稠密但 checker/oracle 复杂）——**Human Gate 决策**。
- draft §5 wait-only 舍入 0.1pp（13.0 vs 精确 12.75）——建议对齐 12.75。
- C23 BOUNDARY 等号语义保留待 Human Gate（draft 分别报告 boundary bucket，不静默决定）——by design。

## 4. 证据要点（供 Human Gate）

- **strategic wait（defer-to-event）**：~11.4 严格/批（~2.8% 决策点）——SPARSE。
- **可选预防更换**：~169/批（~41% 决策点）——DENSE（NO_PM 下）。
- **meaningful choice fraction ≈ 0.429**（~43% 决策点有 ≥1 可选分支，PM 主导）；每批零机会比例全 0。
- **旧 C24 `waiting_opportunity_count`（150/批 forced wait）严重高估 H2 strategic wait（11.4/批）**（13 倍）。
- 机会密度：wait 侧不依赖 tau_pm；PM 侧因政策而异（NO_PM 168.8 > tau198 125.4）。
- **advisory recommendation = ADMIT_FOR_DESIGN**（最终预算/范围决策归 Human Gate）。
