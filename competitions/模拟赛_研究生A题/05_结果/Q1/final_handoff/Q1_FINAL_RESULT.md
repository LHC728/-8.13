# Q1 FINAL RESULT

> **Status: ACCEPTED / DERIVED FROM IMMUTABLE G2 AUTHORITY / READY_FOR_PAPER_REFERENCE**
>
> **Authority source:** `05_结果/G2/run_20260814T130947069958Z_4bb92eda/`
>
> **本文档不重新计算 Q1。** 所有数值必须来自上述 accepted run；若本文档与原始 run evidence 冲突，**以原始 accepted run 为准**（provenance 见 `Q1_FINAL_PROVENANCE.json`；权威解析见 `05_结果/Q1/final_closure/Q1_FINAL_AUTHORITY_MAP.json`）。

- run_id: `20260814T130947069958Z_4bb92eda`（overall_status = PASS；provenance-clean accepted reissue）
- main semantic: `single_test_unconditional_v1`（冻结主/字面语义）
- alternative semantic: `standard_chain_v1`（accepted 替代/稳健语义，**禁止与主语义混用**）

## 1. 主语义 single_test_unconditional_v1

来源：`05_结果/G2/run_20260814T130947069958Z_4bb92eda/single_test_unconditional_v1/response.json`（check_report：checker_status=PASS，route_table_verdict=PASS，90 items 全 PASS；response overall_status=ALL_ROUTES_AGREE）。

### 1.1 观测核（A/B/C，字段 `abc_kernels[]`）

| process | q | e | alpha | beta |
|---|---|---|---|---|
| A | 0.025 | 0.03 | 0.015384615384615385 (=1/65) | 0.6 (=3/5) |
| B | 0.03 | 0.04 | 0.020618556701030928 (=2/97) | 0.66666666666666667 (=2/3) |
| C | 0.02 | 0.02 | 0.010204081632653061 (=1/98) | 0.5 (=1/2) |

### 1.2 E 链（字段 `q_E` / `E_kernel` / `E_rates` / `anchors`）

| 量 | 值 |
|---|---|
| q_E（E 真实问题率，传播值） | 0.062593912407392898 |
| alpha_E | 0.010667735288215836 |
| beta_E | 0.15975994494344646 |
| G | 0.98697794813801809 |
| Z_0 | 0.92519913690423862 |
| Z_1 | 0.061778811233779475 |
| E_rates.first_abnormal | 0.062593912407392898 |
| E_rates.process_exit | 0.044298189209709522 |
| **E_rates.device_total_exit（综合测试测出系统有问题的概率）** | **0.056743387754410703** |
| anchors.E_S | 94.32566122455893 |
| anchors.E_PL | 0.018162763536211106 |
| anchors.E_PW | 0.00081502602845540441 |

> 注：「综合测试测出系统有问题的概率」以 accepted 字段 `E_rates.device_total_exit` 表示（= fourfold 的 p_GE + p_BE，见下）；该值直接来自 accepted evidence，未手动推导。

### 1.3 fourfold 表（字段 `fourfold`，sum = 1）

| p_GP | p_BP | p_GE | p_BE |
|---|---|---|---|
| 0.92509384870937819 | 0.018162763536211106 | 0.00081502602845540441 | 0.055928361725955299 |

### 1.4 指向标签 λ（字段 `lambda`；main 与 tilde；na=false）

| λ | main | tilde |
|---|---|---|
| λ_A | 0.32975380570149444 | 0.33692132073820691 |
| λ_B | 0.41973208538979114 | 0.42762828904182145 |
| λ_C | 0.23503400916343889 | 0.24086884006858082 |
| λ_D | 0.015480099745275524 | 0.015975994494344646 |

λ 三种计数口径（字段 `lambda.counts`，问题契约 `SD-G2-02-LAMBDA-ONCE`）：

| 口径 | 值 |
|---|---|
| event_level | 1.5462434051779937 |
| first_test_only | 0.84024005505655354 |
| at_most_once_per_device | 0.84024005505655354 |

### 1.5 多项分布（字段 `multinomial`）

N = 100；p = [0.92509384870937819, 0.018162763536211106, 0.00081502602845540441, 0.055928361725955299]。

## 2. 替代语义 standard_chain_v1（稳健解释）

来源：`05_结果/G2/run_20260814T130947069958Z_4bb92eda/standard_chain_v1/response.json`（checker_status=PASS，route_table_verdict=PASS，90 items 全 PASS；response overall_status=ALL_ROUTES_AGREE）。

**这是 accepted 的替代语义/稳健解释，不得与主语义混用**（不混用 alpha/beta 与下游概率；不是另一组同时的「主答案」）。

| 量 | 值 |
|---|---|
| q_E | 0.047150339332016366 |
| G | 0.97095851568604639 |
| A alpha / beta | 0.015612642053572192 / 0.38226176188707678 |
| B alpha / beta | 0.020942481877888125 / 0.44441134347855829 |
| C alpha / beta | 0.010343090510990168 / 0.30146827672834102 |
| alpha_E / beta_E | 0.010920932310648563 / 0.1185856135607714 |
| fourfold p_GP/p_BP/p_GE/p_BE | 0.92506714926987526 / 0.010214143691850879 / 0.00084174713433481158 / 0.063876959903939049 |
| λ counts event_level / first_test_only / at_most_once | 1.6583057070612704 / 0.8814143864392286 / 0.8814143864392286 |

## 3. Scope guards

- 结果以「操作误差」的冻结解释为前提（`single_test_unconditional_v1` 主语义）。
- `single_test_unconditional_v1` 与 `standard_chain_v1` 是**两个分离的语义情景**：禁止混用其 alpha/beta 或下游概率。
- 不声称题意歧义只有一种可能解释。
- paper-facing 主结果必须遵循当前权威指定（主语义 = single_test_unconditional_v1）。
- 本文档**不引入任何新解释**；所有数值均为 accepted evidence 的机械摘录。
