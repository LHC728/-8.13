# 最小检验结果说明

论文当前采用以下三项检验：

1. `table5_field_audit.csv`：表5的31批、93个字段逐项核验；
2. `problem3_calibration_replications.csv` 与 `problem3_calibration_summary.csv`：随机机制校准；
3. `bootstrap_replications.csv` 与 `bootstrap_selection_frequency.csv`：2000次Bootstrap策略稳定性分析。

对应的可重复计算脚本位于：

```text
code/model_validation_minimal/
├── run_consistency_audit.py
├── run_random_calibration.py
└── run_bootstrap_stability.py
```

`litter_distribution_robustness_*.csv`来自早期简化的出栏量实验，没有调用最终版完整反馈与羊栏损失逻辑，仅保留作研究过程记录，不作为论文结论或最终方案的验证证据。
