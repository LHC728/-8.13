# Q4 PHASE 1A — SUBSTANTIVE BLOCKER（STOP HUMAN_GATE_REQUIRED）

> 日期：2026-08-17；包：Q4/G6 PHASE 1A（FAST SCREENING）
> 状态：**BLOCKED**（未运行任何 Q4_SCREENING simulation；Q4_EVALUATION UNTOUCHED）

## 1. Blocker

**Q4_SCREENING 命名空间不被冻结 key_schema 接受。**

- HG 任务包指定：`namespace: Q4_SCREENING`（Phase 1A 固定域）。
- 冻结 `main_model/g3/key_schema_v1.py`（P0 验收，六命名空间 + H2 reserved）在
  `RandomDesConfig.from_dict` 拒绝：
  `config.namespace must be one of the six frozen namespaces
  ('development_unit','pilot','h1_tuning','g3_holdout','q2_formal','q3_formal'),
  got 'Q4_SCREENING' (H2 is reserved only)`。
- key_schema 属 **accepted DES core / P0 冻结项**：修改 = 需 Human Gate 授权；
  本包规则明确「如果必须修改 accepted core → STOP HUMAN_GATE_REQUIRED；不得擅改 core」。

## 2. 可选解决方向（供 Human Gate 裁决，本包不自行选择）

- **A. 授权 key_schema_v1 扩展**：新增 `Q4_SCREENING` / `Q4_EVALUATION` 两个冻结命名空间
  （P0 六域 + h2 reserved → 追加 Q4 域；改 accepted core，须 Human Gate 批准并登记
  CHANGELOG + INVALIDATION/extension 记录；CRN 语义与现有 key 派生公式不变）。
- **B. 授权 Q4 复用现有冻结域**：如 `q3_formal`（master_seed 7 新 seed，rep 0..19）承载
  Q4 screening 键控流；需明确 provenance 语义（Q4 baseline 与 Q3 K12 rep 0..19 同世界——
  可直接复用 Q3 accepted 作为 baseline，scenario 用同键控流新 config）；或 `development_unit`
  （非正式域，provenance 更弱）。需 Human Gate 批准域映射与 CRN 配对语义。
- **C. 其他 Human Gate 指定方案**。

## 3. 已完成（无 simulation）

- Startup repo check：HEAD = 62ebe5f == upstream；无未授权 substantive 修改。
- CURRENT_STATE §1 Gate 同步为 Q4_SCREENING_ONLY AUTHORIZED（其余 NOT AUTHORIZED）。
- `Q4_G6_EXPERIMENT_SPEC_DRAFT.md` 冻结标记（SCREENING_SPEC_FROZEN / PRE-DATA /
  HUMAN_GATE_AUTHORIZED）。
- 接口确认：F2（turnover_profile 0.5h_overlap）、F3（tau_pm=150/180/210 数值）、
  F4（durations 覆盖 ±10%）均可经 `default_config` 参数实现（不改 core）；
  F5 有冻结 constant-hazard sensitivity 构造（`sensitivity_constant_hazard_inverse_cdf`，
  同 U_L 不同 inverse transform）。
- **未执行**：Q4_SCREENING_REGISTRY.json 生成（build_config 被 key_schema 拒绝）、
  Pro-Max pre-screening review（协议含未决 namespace → 留待裁决后执行）、
  任何 screening simulation / baseline ledger。

## 4. 待 Human Gate

裁决命名空间方案（A/B/C）后，本包恢复：冻结 registry → 1 次 fresh Pro-Max
pre-screening review → PASS 后执行 Phase 1A screening。
