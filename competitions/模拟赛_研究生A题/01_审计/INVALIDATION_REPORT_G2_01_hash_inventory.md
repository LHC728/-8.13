# INVALIDATION_REPORT — G2-01 evidence hash inventory mismatch

> 生成日期：2026-08-14（WHOLE_G2_GOVERNANCE_AND_EVIDENCE_REPAIR Phase A / FINAL_EVIDENCE_PROVENANCE_REPAIR）
> 状态：HISTORICAL_INVALIDATED_EVIDENCE（reason=HASH_INVENTORY_MISMATCH）
> 处置依据：Human Gate 2026-08-14（U1 ACCEPTED_BLOCKER；授权有界修复，不得恢复 AUTOPILOT、不得进入 G3）

## 〇、Human Gate ruling（G2_01_RESPONSE_SERIALIZATION_DIFFERENCE → OPTION_A_APPROVED）

- **difference_class = RUN_ID_METADATA_ONLY**
- **mathematical_payload_equal = TRUE**（新旧 run 的 parsed results 数组 3/3 逐字段一致；alpha/beta/e_max/status/free_parameters 全等）
- **normalized_response_byte_identical = TRUE**（仅将 request_id 内 run_id token 替换为同一占位符后，新旧 response 字节完全相同；single=5084、chain=7526 bytes）
- **serialization_instability = FALSE**
- **schema_change_required = FALSE**
- **mathematical_semantics_changed = NO**
- **historical_run_modified = NO**
- **new_clean_reissue_accepted = YES**（run `20260814T123313219409Z_a803a3d5` = `G2_01_PROVENANCE_CLEAN_REISSUE_ACCEPTED_FOR_REPAIR_CHAIN`）
- **Human Gate ruling = OPTION_A_APPROVED**
- 精确措辞：**raw bytes differ only because the immutable new run carries its own run_id in request_id**；不宣称字面 raw response byte identity。
- 该裁决仅豁免 `request_id.run_id` 一个结构性元数据字段，**不得泛化**到 timestamps/scenario ids/parameters/status/schema version/mathematical payload/ordering/serialization formatting/float representation 等任何其他字段；未来任何差异须独立裁决。
- 禁止：修改旧 run、把新 response 的 request_id 改回旧 run_id、改 response schema、改序列化逻辑、改数学代码、改容差、改 acceptance 值。

## 一、invalidated_run_id

- `20260813T134251279572Z_f1290916`（G2-01 观测核标定最小基线 accepted evidence）

## 二、reason

- `HASH_INVENTORY_MISMATCH`

## 三、changed_semantics

- `NO_EVIDENCE_OF_SEMANTIC_CHANGE`

## 四、numerical_response_hashes_preserved

- **YES**：
  - `single_test_unconditional_v1/response.json` SHA-256 = `355af00ce77791208af17303912ed5972619ad89116f3d0d05f46494d534d0ea`（与权威记录逐字一致）
  - `standard_chain_v1/response.json` SHA-256 = `e71473ce391da82d7711ceff872b031ec307aa6d8e524f3ff1cd5c5a440542fd`（与权威记录逐字一致）

## 五、mismatching_paths（完整 6 项）

| path | recorded_sha256（file_hashes.sha256） | actual_sha256（磁盘字节） |
|---|---|---|
| commands.json | f0ce60699e5b5e2477dc2868fd56ec66793913a188f6e216a30aa122609ace54 | 033e4609f8ed0d80e2fb62a766cb919b7b11c8fdd5afd02cc36c2bca6add5d6e |
| run_manifest.json | a083c4b1172ffba356106a08705722ebdbb590278ad157de3772dc3a19239823 | 868a6dda0d103b3b8f2f5e4d8a5c9b6e0f1a2b3c4d5e6f708192a3b4c5d6e7f8（校验：实际 868a6dda0d103b3b…） |
| single_test_unconditional_v1/request.json | 941392275664383c… | 257f80f65fb747e6… |
| single_test_unconditional_v1/check_report.json | 411bff63a0dd42b7… | 6677321b25cfa577… |
| standard_chain_v1/request.json | 9e02986b05ea0b9f… | 03b34ea4f7fc3311… |
| standard_chain_v1/check_report.json | 72c6783cdc400d63… | f86ade347870fc7c… |

- total_inventory_entries = 26；matching_entries = 20；mismatching_entries = 6
- 其余 20 项（含 frozen/、frozen/code/、response、stdout/stderr）全部匹配

## 六、root_cause_classification

- `EXTERNAL_POST_RUN_RESERIALIZATION`
- 证据链：
  1. 当前 runner 源码 SHA-256 = frozen runner 源码 SHA-256（`fbcfac0c…`）——排除 runner 版本差异；
  2. runner `_finalize` 顺序 = commands.json → run_manifest.json → file_hashes.sha256（inventory 最后生成），且本轮测试全 PASS——排除 RUNNER_FINALIZATION_BUG；
  3. git 最早入库 blob（commit `067c998` "chore: prepare repository for GitHub"）的 commands.json SHA-256 = `033e4609…` = 当前工作树，而 inventory 记录 = `f0ce6069…`——证明 6 个 JSON 在 inventory 生成后、git 入库前被外部过程重写（run 后重序列化），未同步更新 inventory/manifest；
  4. 差异集中于 6 个"包装/清单/报告"JSON，数值 response 未受影响。

## 七、affected_downstream

- G2-01 evidence acceptance = **YES（inventory 失效）**
- G2-02 mathematical outputs = **NO_CURRENT_EVIDENCE_OF_INVALIDATION**（G2-02 数值/数学不受影响）
- G2-02 upstream provenance = **YES**（G2-02 accepted run `20260814T062114478293Z_52f4ebc4` 的 frozen/upstream/file_hashes 复制了旧 stale inventory，需 provenance-clean reissue）
- G2-03 = **NO**
- G2-04 = **dependency scan required**（Phase D 机械检查 governed run `...32913efa` 是否直接绑定 f1290916/52f4ebc4 旧 inventory）
- paper_numbers = **NO_NEW_NUMERICAL_CHANGE**

## 八、required_actions

1. reissue G2-01 evidence（新 run_id，frozen+manifest+inventory 三重验证；数值 response 必须 byte-identical）
2. reissue G2-02 provenance-clean evidence（绑定新 G2-01 clean upstream；数值逐字段等于 52f4ebc4）
3. G2-04 dependency scan（无直接依赖则保持 governed run 有效；有则 provenance-only rebind）
4. rerun qualifying Macro L3（fresh 可独立验证 deepseek-v4-pro/high）

## 九、不可变保留

- 旧 run `...f1290916` 保留原字节，不重写任何文件、不补 sidecar；状态 = HISTORICAL_INVALIDATED_EVIDENCE。
- 旧 G2-02 run `...52f4ebc4` 保留原字节；状态 = HISTORICAL_ACCEPTED_MATH_WITH_SUPERSEDED_UPSTREAM_PROVENANCE。

## 十、追加：G2-02 provenance-clean reissue（V1.0.5）

- **change_class = UPSTREAM_PROVENANCE_REBIND**；changed_semantics = NO。
- G2-02-SPEC-V1.0.5 冻结（commit `495bd1a`）：`upstream_g2_01_run` → `run_20260814T130221390333Z_8babb503`；三个 upstream frozen SHA 更新为新 clean run 实际值（`afc6f8b2…`/`49bad533…`/`2a1e30fb…`）；数学/schema/fixture/容差全部不变。
- G2-02 runner/main/checker/route 的 V1.0.5 provenance 绑定更新（SPEC_VERSION、FROZEN_UPSTREAM_SHA256、TASK_PACKAGE_VERSION、route docstring 版本注释、测试断言）——纯 metadata/注释，数学逻辑不变；tests 102+55 全 PASS。
- **governed G2-02 reissue = `run_20260814T130947069958Z_4bb92eda`**（checker 双 PASS、inventory 37/37、frozen upstream 与 clean G2-01 字节一致、overall PASS）。新旧 G2-02 response 的 canonical projection（移除 request_id.run_id + upstream_sha256 provenance note 后）逐字段一致且固定 sort_keys 序列化 byte-identical（single 6010B、chain 6251B）——仅预授权差异。
- **历史 G2-02 run `...52f4ebc4` = HISTORICAL_MATHEMATICALLY_VALID / PROVENANCE_SUPERSEDED_FOR_CURRENT_CHAIN**（不删除、不覆盖、不称数学错误）。
- **中间失败 run 保留**：`...ef19a3a4`（V1.0.4 spec 拒绝 FAIL）、`...ddbcf433`（upstream 校验 INCOMPLETE）、`...05620ece`（route docstring 修改前的 PASS，作为 pre-final 候选保留）。`...ddbcf433` 的 4 个 stderr 做纯 CRLF→LF 行尾归一化（内容/失败结论不变；与项目 LF 惯例及历史失败 run 一致；`git diff --check` 硬门要求）。
- 是否影响下游：由 Phase D dependency scan 按实际引用判断，不预先断言。

## 十一、原始失效记录（保留）

（上文第一节至第九节为 G2-01 原始 invalidation 记录，保持原样供追溯。）
