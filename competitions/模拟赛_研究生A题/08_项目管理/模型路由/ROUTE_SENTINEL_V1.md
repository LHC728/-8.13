# ROUTE_SENTINEL_V1 — 路由哨兵

> 目的：解决 executor 自己漏填 Risk Card 导致 FALSE GREEN。使用**低成本 Flash / E2 reviewer**，不使用 Pro-Max。
> 实现：`04_代码/governance/model_routing_v2/sentinel.py`

## 角色

`CLASSIFICATION_AUDITOR_ONLY`：只审计"风险分类是否有遗漏 / 路由是否过低"。

**Sentinel 禁止**：做最终数学裁决；改变 frozen authority；修代码；把 YELLOW 降成 GREEN；把 RED 降成 YELLOW。

## 输入

task description、Risk Card、relevant diff summary、relevant authority references、diagnosis。

## 输出

```
SENTINEL_VERDICT: AGREE_GREEN | AGREE_YELLOW | AGREE_RED | RISK_OMISSION | ROUTE_TOO_LOW
missing_risk_dimensions: [...]
reason: ...
```

## 触发条件（控制成本，不每个 shell command 都跑）

A. formal_scope=true 且 proposed route=GREEN 的 R4 Gate
B. GREEN 任务曾发生 R1/R2/R3 reclassification candidate
C. 任务产生 formal result
D. 涉及新 cross-module semantic seam
E. 正式 reviewer 即将 PASS

## 分歧升级（不可否决）

- AGREE_GREEN → GREEN 可继续。
- RISK_OMISSION / ROUTE_TOO_LOW → 自动 YELLOW → mandatory Pro-Max（VERIFIED_PRO_MAX）。
- Flash 不得自行否决 Sentinel 分歧（`sentinel_upgrade` 是确定性的；分歧即升级）。

## 验证

- T24：formal GREEN + Sentinel 发现遗漏 modeling assumption → YELLOW。
- T25：Sentinel 同意机械冻结执行 → 保持 GREEN。
- MMR-10：Sentinel 分歧升级为 YELLOW（检查器）。
