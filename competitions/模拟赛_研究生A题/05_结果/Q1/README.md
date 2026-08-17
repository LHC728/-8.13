# Q1 结果入口

## 为什么第一问的结果不在 Q1，而在 G2？

**Q1 已完成并 accepted。** 历史原因：Q1 是在较早的 **G2 阶段**完成的——当时仓库按**开发 Gate** 组织证据（G2-02 = 第一问的「概率与质量解析链」），而不是直接按题目号组织。

因此，**不可变的 accepted 来源仍在**：

```text
05_结果/G2/run_20260814T130947069958Z_4bb92eda/
```

新建的 `Q1/` 目录**不替换** G2 证据，只是**导航 + paper-facing 摘要层**。

## 权威层级

| 角色 | 位置 |
|---|---|
| **numeric/formal 权威** | `05_结果/G2/run_20260814T130947069958Z_4bb92eda/`（accepted，不可变） |
| Q1 导航/paper-facing 摘要 | `05_结果/Q1/final_handoff/` |
| 历史/debug/superseded 证据 | G2 下其它 run 目录（按各自 manifest / 当前权威文档判断） |

## 重要提醒

- **不要**从任意较旧的 G2 run 复制数字。
- 只使用 accepted run / `Q1 final_handoff` provenance。
- 若本导航层与原始 accepted run 冲突，**以原始 accepted run 为准**。

## 一句话关系

> **G2 = 历史执行/证据层；Q1 = 当前导航/交接层。** Q1 的数字全部派生自 G2 accepted run，未重新计算。
