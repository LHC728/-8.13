# P0 H2 Key Schema — Test Execution Evidence（P0-E1 closure）

> 性质：**TEST EVIDENCE CLOSURE ONLY**（非实现包；Human Gate 独立核验材料）
> 生成：2026-08-15（UTC 13:21:34Z）
> 测试对象 commit：`9f6099c71e09844079801222b7dc2fa1db6cee45`（g2-02-impl，anchor 精确匹配）
> 运行时：Python 3.12.10；Microsoft Windows NT 10.0.26200.0
> 证据类型：HARNESS EXECUTION EVIDENCE（awaiting Human Gate verification）
> 本包未修改任何生产代码、未进入 P1、未运行 Q3 formal / holdout / C25。

---

## 1. 锚点与范围

- branch：`g2-02-impl`
- expected / actual starting HEAD：`9f6099c71e09844079801222b7dc2fa1db6cee45`（`git fetch` 后 `origin/g2-02-impl` 精确匹配）
- 测试后工作树：干净（`## g2-02-impl...origin/g2-02-impl`，无未提交修改）
- 生产代码修改：**NO**（本包未触碰 `key_schema_v1.py` / `random_des_v1.py` / H1 / H2 / Q2 / Q3 配置 / D-01..D-25）
- formal experiment run：**NO**

## 2. 测试结果（在 exact commit 9f6099c 上重跑）

### A. test_p0_h2_key_schema_bootstrap_v1.py
- command：`python -m unittest discover -s competitions\模拟赛_研究生A题\04_代码\tests -p test_p0_h2_key_schema_bootstrap_v1.py`
- exit code：0
- tests run：18
- result：**PASS**（Ran 18 tests in 0.010s OK）

### B. test_g3_key_schema_v1.py
- command：`python -m unittest discover -s ... -p test_g3_key_schema_v1.py`
- exit code：0
- tests run：38
- result：**PASS**（Ran 38 tests in 0.010s OK）

### C. test_g3_c16_experiment_separation_v1.py
- command：`python -m unittest discover -s ... -p test_g3_c16_experiment_separation_v1.py`
- exit code：0
- tests run：36
- result：**PASS**（Ran 36 tests in 0.433s OK）

### D. random_des deterministic / stream / namespace / validation 子集
- 选择方式（显式）：`unittest.TestLoader().loadTestsFromNames([...])`，精确 4 个测试类：
  - `test_g3_random_des_v1.TestStreamConsumption`（5 tests）
  - `test_g3_random_des_v1.TestDeterminism`（2 tests）
  - `test_g3_random_des_v1.TestNamespaceIsolation`（1 test）
  - `test_g3_random_des_v1.TestValidation`（8 tests）
- command：`python tmp\p0_run_random_des_subset.py`（runner 内容如上选择；tmp 为 git-ignored 瞬态目录）
- exit code：0
- tests run：16
- result：**PASS**（Ran 16 tests in 0.050s OK）

### E. test_g3_lifetime_regeneration_v1.py
- command：`python -m unittest discover -s ... -p test_g3_lifetime_regeneration_v1.py`
- exit code：0
- tests run：42
- result：**PASS**（Ran 42 tests in 0.016s OK）

### F. tiny deterministic engine pre/post compatibility
- 配置：`namespace=development_unit, master_seed=7, replicate_id=0, NO_PM_BEFORE_MANDATORY, batch_size=3, isolated_small_case, shift_length_h=1000000, 1h_literal`（与 P0 报告相同）
- pre-change reference（捕获于 `1de71824`，修改前）：
  - log_sha256：`d202fb91e30c6040676a0b9535d22b6e08d9de6842804549dc792a53d15e7f62`
  - summary_sha256：`dc8715a602b69bc54bdf125833c45e5349acfd44fa26bafed777f568333ab45c`
- current P0 commit（`9f6099c`）重跑：
  - log_sha256：`d202fb91e30c6040676a0b9535d22b6e08d9de6842804549dc792a53d15e7f62`
  - summary_sha256：`dc8715a602b69bc54bdf125833c45e5349acfd44fa26bafed777f568333ab45c`
- exit code：0
- 精确一致：**YES**（canonical log 与 summary 均逐字节一致 → accepted baseline 随机世界未变）

## 3. Legacy Golden 再核验（只读 frozen fixture，未重新生成 expected）

- oracle_commit：`1de71824e668f3815f58112cb3c42c9633b2da16`
- oracle_blob_sha：`8a8f10895ee9751fb7c3c93093c3cdac25b4b632`
- vectors：**620**
- canonical UTF-8 mismatch：**0**
- Fraction numerator/denominator mismatch：**0**

**LEGACY KEY BYTE COMPATIBILITY: PASS**

## 4. git status（测试执行后、evidence commit 前）

```
## g2-02-impl...origin/g2-02-impl
（工作树干净）
```

## 5. 本包声明

- 生产代码修改：NO
- P1 开始：NO
- Q3 formal / holdout / C25 运行：NO
- H2 实现新增：NO
- expected fixture 重新生成：NO
- 未写任何无法机械证明的模型身份/推理强度声明。

---

*Evidence 文件本身与最小 CHANGELOG 记录随 P0-E1 evidence commit 落库（见该 commit）。*
