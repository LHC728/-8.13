# INVALIDATION / EXTENSION RECORD — Q4 additive random-domain extension

> 依据：HG-Q4-NS-01（Human Gate 2026-08-17，OPTION A / ACCEPTED）。
> 性质：**BACKWARD-COMPATIBLE ADDITIVE EXTENSION**（非 invalidation）。

| 项 | 值 |
|---|---|
| changed_semantics | **NO** |
| main_engine (DES event semantics) | **NO**（random_des_v1 引擎事件/状态机未动） |
| schema_additive | **YES**（key_schema_v1 追加 Q4 命名空间常量 + allowlist 扩展） |
| random mapping | 未变（SHA256→Fraction、字段序、分隔符、type tags 原样） |
| legacy canonical keys | **byte-identical**（NS-01 断言：六 legacy 域 key 字符串与独立重算 U 完全一致） |
| H2 firewall | 未破（u_*_post 仍只接受 H2 域；Q4 拒绝；h2 域仍排除出 physical DES） |
| G3/Q2/Q3 accepted runs invalidation | **NO / NONE**（旧 canonical keys 不变 → 输出可复现） |

改动文件（authorized）：
- `04_代码/main_model/g3/key_schema_v1.py`：新增 Q4 常量 + `PHYSICAL_EXPERIMENT_NAMESPACES` + `_SERIALIZABLE_NAMESPACES` 扩展 + `_require_legacy_namespace` allowlist 扩展（docstring 同步）。
- `04_代码/main_model/g3/random_des_v1.py`：`RandomDesConfig.from_dict` namespace 校验改收 `PHYSICAL_EXPERIMENT_NAMESPACES`（fail-closed）。

回归：`tests/test_q4_namespace_extension_v1.py`（NS-01..09）+ G3/Q3-H1/H2-P1-firewall/H2-density/key_schema 回归 = 182/182 PASS（Q4 extension 未打开 H2 information seam）。
