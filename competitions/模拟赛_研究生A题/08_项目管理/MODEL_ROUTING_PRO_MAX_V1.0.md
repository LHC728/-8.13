# MODEL_ROUTING_PRO_MAX_V1.0 — Pro-Max Dedicated Route（设计文档）

> 状态：IMPLEMENTED（additive；Harness core 未修改）
> 日期：2026-08-16
> Harness：DeepSeek Harness `0.1.0-rc.5`（checkout commit `47f943859b`）
> 关联：`05_结果/governance/model_routing/`（证据根）

## 1. 目标与边界

在**不修改 Harness core source**的前提下，为项目增加一个可验证的独立高级 reviewer
通道：fresh child + `deepseek-pro-max` route + `deepseek-v4-pro` +
`reasoning_effort=max`。现有 Flash Coordinator、Flash workers、`deepseek-official`
route、数学模型代码与 frozen governance 全部不变。这是 **additive change**。

**禁止修改**：`packages/core/*`、`packages/llm/llm/*`、`packages/subagent/*` 源码；
尤其禁止给 `AgentOptions` 增加 `reasoningEffort`（属另一套长期方案）。

## 2. 架构

```
pro_max_review（tool-subagent instance, provider=spawn）
  └─ fresh spawn child（无 parent transcript，共享 cwd/workspace）
       └─ agentOptions: provider=deepseek-pro-max, model=deepseek-v4-pro,
                        maxTokens=256000
            └─ llm-pi-ai route deepseek-pro-max
                 ├─ apiKeyEnv=DEEPSEEK_API_KEY（复用现有 credential ref）
                 ├─ baseURL=https://api.deepseek.com（复用现有 endpoint）
                 ├─ reasoning=max（route 默认 → request 缺省 effort 时 materialize max）
                 ├─ compat: thinkingFormat=deepseek, supportsReasoningEffort=true
                 └─ models: deepseek-v4-pro（contextWindow=1_000_000,
                            maxTokens=256_000,
                            reasoningEfforts: high→high, max→max）
```

- 工具实例：`$DSH_HOME/cordis.patch.yml`（home-level user layer，`insert:` 行，
  `toolName=pro_max_review`，`enableRunInBackground=false`，`backgroundMode=one-shot`，
  `maxDepth=1`，persona=`READ_ONLY_SEMANTIC_REVIEWER`，toolFilter deny 全部 mutation
  tools）。
- 路由：`$DSH_HOME/settings.yaml` 的 `llm-pi-ai:` 节（settings seam 动态注册，
  chokidar 热加载；pi-ai adapter 挂载于 dormant 态，加节即注册）。
- 两个文件均为纯配置；**rollback = 删除上述两处配置**，不需要改 Harness core，
  也不需要动 Flash 链。

## 3. Provider 隔离

- `deepseek-pro-max` 是 pi-ai adapter 的独立 route key；`deepseek-official` 仍由
  `@deepseek-ai/dsh-llm-deepseek` 拥有（composition row `llm-deepseek`）。
- pi-ai `providers` 是 dict，route key 结构性去重；registry 原子注册，route 冲突
  时整组失败且不覆盖已有 route。
- `agent-default-model`（deepseek-official / deepseek-v4-flash / reasoningEffort=max
  ——max 为既有设置，非本包引入）未改动。
- 验证：`wire_semantic_check.mjs` T5（pi-ai 解析后 routes = {deepseek-pro-max}，
  deepseek-official 注册事实不变）+ 前后 composition diff（
  `composition_before.yml` / `composition_after.yml`，仅新增 tool 行）。

## 4. 路由规则（项目级 MODEL_ROUTING_V1.0）

| 级别 | 定义 | 执行者 |
|---|---|---|
| L1 | mechanical（test 执行、格式化、路径修复、简单 import、确定性重跑） | Flash |
| L2 | engineering（清晰 spec 下的机械实现 + 需要时 fresh Flash checker） | Flash |
| L3 / YELLOW | 语义（见 §5 触发清单） | **MUST pro_max_review（VERIFIED_PRO_MAX）** |
| L4 | 核心设计（见 §6 触发清单） | **MUST pro_max_review；建议第二个 independent fresh pro_max_review（adversarial）** |
| RED | Human Gate | 停止 |

## 5. YELLOW / L3 触发清单

以下任一触发即 L3，不得由 Flash 自行降级为 GREEN：

frozen spec interpretation；authority ambiguity；random-key semantics；
random-domain semantics；CRN semantics；posterior/lifetime mathematics；
probability/statistical interpretation；decision-point identity semantics；
H1/H2 transition semantics；C23 information firewall；observable vs hidden-state
boundary；checker vs implementation semantic disagreement；repair changes formal
numeric result；first complex cross-module semantic seam；unexplained checker
PASS/behavior contradiction；holdout/tuning contamination concern；
bootstrap / C25 inference semantics。

## 6. L4 触发清单

change frozen mathematical model；change policy definition；change random
protocol；change sample split；change statistical test；change threshold；
change action space；change C23 authority；change C25 retain/delete rule；
reinterpret problem statement that changes formal results。

若 Pro-Max 建议真实修改 frozen design：再做 independent adversarial
Pro-Max review；两者重大冲突 → HUMAN_GATE_REQUIRED → STOP。

## 7. GREEN 任务（不要求 Pro-Max）

test execution；formatting；evidence packaging；hash/provenance；path repair；
simple import bug；ordinary exception；mechanical implementation under clear
spec；JSON/report field repair；deterministic rerun；known regression execution。
目的：不滥用 Max。

## 8. Fail-closed 路由

- L3/L4 任务若没有 `VERIFIED_PRO_MAX`（routing_verification.verified=true），
  formal task status 不得 PASS。
- **禁止 fallback**：Pro-Max failed → Flash decides anyway；Pro-Max failed →
  silent Pro/high。允许 provider retry policy 正常 retry；retry 耗尽 →
  `ROUTING_BLOCKED` → STOP。
- 负例：`wire_semantic_check.mjs` T4（未声明 max 的 model 不提供 max，request
  在网络 I/O 前以 UNSUPPORTED_REASONING_EFFORT 拒绝 → L3/L4 = BLOCKED）。

## 9. 验证程序（MAX VERIFICATION）

判定 `VERIFIED_PRO_MAX` 只依据 child run 的真实请求头（session JSONL 中
request/header + adapterDefaults）与 dispatch 事实：

- provider = `deepseek-pro-max`
- model = `deepseek-v4-pro`
- reasoningEffort = `max`（route `reasoning: max` 默认 → adapter resolveModel
  defaultEffort=max；request header 记录 adapterDefaults.reasoningEffort=true）
- fresh child = true（spawn：child session 无 parent transcript，首条消息即 packet）
- workspace delta = 0（reviewer 不产生任何 git delta）

任一不满足 → `UNVERIFIED_PRO_MAX`，该 review 不具备 L3/L4 Gate 资格。

## 10. Wire 语义（§19，已确定性验证）

- 官方 DeepSeek adapter（deepseek-official 路径）：`serializeRequest` 对
  `reasoningEffort=max` 输出 `thinking:{type:'enabled'}` + `reasoning_effort:'max'`
  （`packages/llm/llm-deepseek/src/serialize.ts` resolveThinking）。
- pi-ai route（deepseek-pro-max 路径）：`compat.thinkingFormat='deepseek'` +
  level max → pi-ai 0.82.1 `dist/api/openai-completions.js` deepseek 分支输出
  `thinking:{type:'enabled'}` + `reasoning_effort = thinkingLevelMap['max'] = 'max'`。
- 证据：`tools/wire_semantic_check.mjs` T1/T2/T3 ALL PASS。

## 11. Review Packet（每次调用必须是 standalone packet）

```
REVIEW_PACKET_VERSION: V1.0
TASK_ID:
RISK_LEVEL:
ROLE: READ_ONLY_SEMANTIC_REVIEWER
CURRENT_COMMIT:
AUTHORITY_FILES:
RELEVANT_SOURCE:
RELEVANT_EVIDENCE:
QUESTION:
IMPLEMENTER_CLAIM:
KNOWN_COUNTEREXAMPLE:
PERMITTED: read-only inspection; small independent calculation; source/evidence review
FORBIDDEN: repair; write; threshold change; authority mutation; self-approval
EXPECTED_OUTPUT:
VERDICT / FINDINGS / AUTHORITY_CONFLICT / REQUIRED_ACTION / CONFIDENCE
```

Review 输出格式：

```
# PRO_MAX_REVIEW
VERDICT: PASS | PASS_WITH_CAVEAT | BLOCKED | HUMAN_GATE_REQUIRED
RISK_CLASS:
AUTHORITY_CHECK: PASS | CONFLICT
FINDINGS: F1..Fn (severity / evidence / reason / required_action)
IMPLEMENTATION_CHANGE_ALLOWED: NO
NEXT_ROUTE: CONTINUE_FLASH | PATCH_THEN_REVIEW | HUMAN_GATE
```

## 12. Routing 证据（每次 L3/L4 至少记录）

证据根：`05_结果/governance/model_routing/`

- `routing_decision.json`：task_id / risk_level / reason / required_executor /
  actual_executor
- `pro_max_dispatch.json`：tool_name / provider / model / maxTokens / fresh_spawn /
  child_run_id
- `pro_max_request_header.json`：child run 真实 request/header（provider/model/
  reasoningEffort/adapterDefaults）
- `pro_max_review.txt`：reviewer 全文输出
- `routing_verification.json`：task_id / risk_level / required_executor /
  actual_executor / tool_name / child_run_id / fresh_spawn / provider / model /
  reasoning_effort / verdict / workspace_delta / verified

## 13. ROUTE-01..12 硬检查（tools/check_model_routing_v1.py）

ROUTE-01 GREEN 不要求 Pro-Max；ROUTE-02/03 L3/L4 必须 verified Pro-Max；
ROUTE-04 reasoningEffort != max → FAIL；ROUTE-05 model != deepseek-v4-pro → FAIL；
ROUTE-06 provider != deepseek-pro-max → FAIL；ROUTE-07 fresh_spawn != true → FAIL；
ROUTE-08 GREEN 无 Pro-Max 要求；ROUTE-09 YELLOW/L4 缺 Pro-Max → BLOCKED；
ROUTE-10 Pro-Max 失败禁止 fallback；ROUTE-11 reviewer workspace delta=0；
ROUTE-12 wire max 已验证。任一 FAIL → 本包 STATUS=BLOCKED。

## 14. Enforcement Gap（MODEL_ROUTING_ENFORCEMENT_GAP 闭合）

每个任务开始时、每次 semantic failure 后、每次 semantic-changing patch 后，
重新记录 `ROUTING_DECISION`（risk_level / reason / required_executor）。若
YELLOW/L3/L4 而无 VERIFIED_PRO_MAX：formal task status 不得 PASS。

## 15. Rollback（纯配置）

1. 删除 `$DSH_HOME/cordis.patch.yml` 中的 `tool-pro-max-review` insert 行（或整文件）；
2. 删除 `$DSH_HOME/settings.yaml` 的 `llm-pi-ai:` 节；
3. 验证 `dsh --profile web --dump-config` / `--profile headless --dump-config`
   不再出现该 tool 行；Flash 链（deepseek-official / agent-default-model /
   tool-subagent / tool-subagent-fork）完全不变。
不需要修改 Harness core；不需要重启 web 会话（config-only HMR；即便重启也无副作用）。

## 16. 已执行验证（本包）

- SOURCE AUTHORITY：facts A–E 全部 PASS，无 drift。
- PRO_MAX_PRECHECK：`pro_max_precheck_report.json`。
- wire_semantic_check：T1–T5 ALL PASS（含负例 T4 与隔离 T5）。
- composition diff：`composition_before.yml` / `composition_after.yml`，
  仅新增 tool-pro-max-review 行。
- smoke：`pro_max_smoke.log` + session JSONL 请求头验证（provider/model/
  reasoning_effort/fresh/delta）。
- Flash non-regression：headless 父 run 请求头仍为 deepseek-official /
  deepseek-v4-flash（reasoningEffort=max 为既有设置）。
- 最终：`check_model_routing_v1.py` ROUTE-01..12。
