# FROZEN AUTHORITY ADDENDUM — HG-Q3-H2-DP-DIAG-01

> 性质：**追加**到冻结权威 `Q3_H2_BOOTSTRAP_SPEC_DRAFT.md`（FINAL_FREEZE_ACCEPTED）的裁决澄清。
> **不重写任何历史冻结条款**；本文件只补充唯一缺失的 offline 诊断键映射。
> 日期：2026-08-16；来源：Human Gate 第二次语义重新认证任务包（e4fd435 的 H2 DELETE 暂不接受）。
> 状态：**HUMAN GATE 裁决 = 冻结澄清（权威）**。

## 1. 背景与撤销

上一轮 Human Gate repair prompt 曾把 "production quota-evaluated points" 错误延伸为 P3-C §4 B-1 的采样总体。
**该解释正式撤销。** 冻结 §1.3 / §4 明确规定：P3-C stability (b)(c) 是 **OFFLINE DIAGNOSTIC**；
B-1 来自 h2_tuning / master_seed=6 / replicate 0..9 / K=10.5 十批中的 **ALL H2-ELIGIBLE DECISION POINTS**
（批升序、批内冻结时间/资源顺序：前 50 wait-eligible 含 both + 前 50 PM-only；一类不足从另一类按冻结顺序补足；cap=120；actual n 报告；n<50 → DELETE）。
在线 quota（C_eval\*=8 / W_cap\*=4 / P_cap\*=4）**只属于 production policy**，**不得**用于缩小 §4 offline B-1 population。

## 2. 裁决内容（唯一澄清）

### 2.1 production dp（不变）

冻结 §6.2 的 production dp：

```
dp_online = 本批内实际被在线 H2 quota 选择并执行 rollout 的 decision point 0-based 序号
```

保持不变。

### 2.2 offline diagnostic dp（唯一补充映射）

对 §4 (b)(c) B-1 OFFLINE DIAGNOSTIC（明确不受 C_eval\* 约束），补充唯一 offline key 映射：

```
dp_diag = 在一个 batch 内，最终进入 B-1 且实际被该 offline diagnostic 重评估的点，
          按该 batch 内 (time, canonical resource order) 排序后的 0-based 序号
```

要求：

1. 每个 batch 独立从 0 开始；
2. normal M\*、ALT M\*、normal 2M\* 对同一 physical B-1 point 必须使用相同 `replicate_id` 与 `dp_diag`；
3. 2M\* 的前 M\* 个 m 必须与 M\* 完全一致（rollout keys 是 (master_seed_h2, replicate_id, dp_diag, m, salt) 的确定性函数）；
4. candidate action 不得进入 seed（CRN 不变）。

### 2.3 边界（不得改变）

本澄清**只**作用于 §4 B-1 OFFLINE DIAGNOSTIC 的键映射，**不得改变**：

- production `dp_online`；
- online quota / C_eval\* / W_cap\* / P_cap\*；
- B-1 population（ALL H2-eligible，50+50+top-up+cap120，n<50→DELETE）；
- 2SE confident deviation；
- agreement 0.95 点估计硬门（CP95 仅披露）；
- seed / namespace / salts / K / replicate 域。

## 3. 引用

- 冻结 §4(b)(c) B-1：`Q3_H2_BOOTSTRAP_SPEC_DRAFT.md` §4（"不受在线政策 C_eval* 上限约束"）+ §1.3/§5 表。
- production quota / dp_online：§2 D-08 / §6.2。
- 本裁决登记：`CHANGELOG.md`（2026-08-16 / Q3-H2-P3 第二次语义重新认证条目）。
