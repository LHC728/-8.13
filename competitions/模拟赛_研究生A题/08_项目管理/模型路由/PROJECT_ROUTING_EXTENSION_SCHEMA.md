# PROJECT_ROUTING_EXTENSION_SCHEMA — 项目路由扩展层

> 每道题可提供一份扩展；只允许"项目术语 → 风险维度 / 项目方法 → 方法族 / 历史错误 → regression pattern"。
> 扩展只能**保持或升级**风险；YELLOW→GREEN、RED→YELLOW 一律 REJECTED；禁止修改 Universal Core。
> 实现：`04_代码/governance/model_routing_v2/extensions.py`（validate_extension / apply_extension）。

## 结构

```json
{
  "extension_version": "1.0",
  "project_id": "<题目标识>",
  "term_risks": {
    "<项目术语>": {
      "risks": ["ALGORITHMIC_SEMANTICS", "FORMAL_RESULT_IMPACT"]
    }
  },
  "term_families": {
    "<项目方法术语>": ["OPTIMIZATION", "OPERATIONS_RESEARCH"]
  },
  "regression_patterns": [
    {"pattern": "<历史错误抽象模式>", "note": "..."}
  ]
}
```

## 约束

1. `risks` 只能是 Universal 风险维度（R1..R10 的 snake_case 名）。
2. `term_families` 只能是注册表 16 族。
3. 任何 `route_cap` / 降级语义字段 → `ExtensionRejected`（de-escalation 禁止）。
4. 未知字段名/未知维度/未知族 → `ExtensionRejected`（fail-closed，不做静默忽略）。
5. `apply_extension` 只做：命中术语 → 置风险维度为 true（只升不降）、追加方法族。

## 当前项目扩展

当前竞赛（模拟赛_研究生A题）未启用项目扩展：本阶段全部演示与测试均使用通用术语，保证 Router 的通用性（spec 34/36）。项目级经验只允许进入 `MODEL_ROUTING_MISS_REGISTRY.json`（PROJECT_SPECIFIC scope）或未来按本 schema 添加扩展。
