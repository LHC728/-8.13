# 模拟赛_研究生A题：项目协作规则

## 唯一入口

任何新对话或新执行任务，先读：

1. `CURRENT_STATE.md`
2. `01_审计/问题契约.md`
3. `01_审计/检查注册表_V3.1.md`
4. `02_数据/parameters.csv`
5. `03_模型/00_模型总览.md`

只在任务需要时再读 `08_项目管理/项目计划.md`、风险清单或专项模型文档。不要默认读取历史评审、旧注册表或旧方案。

## 当前权威顺序

若内容冲突，按以下顺序处理；不得自行挑选方便的解释：

1. `CURRENT_STATE.md` 中的当前版本指针和阶段边界
2. 队伍最新签字口径与 `01_审计/问题契约.md`
3. 当前检查注册表 `CR-V3.1`
4. `02_数据/parameters.csv` 与 `02_数据/configs/` 中当前配置
5. `03_模型/` 的当前模型文档
6. `08_项目管理/项目计划.md`
7. `99_归档/` 和其他历史材料
8. 聊天记录

注意：`CURRENT_STATE.md` 只负责指向当前权威版本和陈述阶段状态；它不能单方面创造或改变数学口径。若它与已签字问题契约实质冲突，立即停止并上报。

## 阶段治理

- 当前 Gate、正在执行的任务和阶段禁止项只从 `CURRENT_STATE.md` 读取。
- 只执行当前 Gate 与检查注册表明确授权的工作；不得因后续目录已存在而提前实现、运行或冻结结果。
- 任何阶段状态改变都必须同步更新 `CURRENT_STATE.md` 和 `CHANGELOG.md`。

## 目录职责

- `00_题目/`：只读原始输入和来源清单。
- `01_审计/`：问题契约、签字口径、歧义、检查标准和手算 oracle。
- `02_数据/`：机器可读参数及唯一正式配置目录 `configs/`。
- `03_模型/`：数学模型、公式和方法边界。
- `04_代码/main_model/` 与 `04_代码/checker/`：主模型和独立检查器，禁止相互导入核心逻辑。
- `04_代码/tests/`：测试；`scripts/`：运行编排；`src/` 仅放明确归属的公共非判断基础设施，禁止放主模型/checker共用核心计算。
- `05_结果/`：唯一运行结果根目录；每次运行必须单独目录并绑定 manifest。图表统一进入 `05_结果/figures/`，不能另建第二结果源。
- `06_论文/`：表达层，不重新发明公式或手录结果数字。
- `07_AI使用记录/`：AI 使用留痕，不作为口径来源。
- `08_项目管理/`：计划、风险、任务路由和模型分工；当前数学模型只进入 `03_模型/`。
- `99_归档/`：旧注册表、历史评审和旧模型方案的只读追溯区；不得作为当前实现输入。

## 实现与结果纪律

- 所有检查引用写为 `CR-V3.1/Cxx`，不裸写 `Cxx`。
- 参数或配置无效时必须显式失败，禁止裁剪概率、改期望值或删除失败样本。
- 代码、配置、结果、日志和检查报告必须可逐次追溯。
- 运行前必须有冻结任务包；执行者若需要作数学或业务决定，任务自动升级。

## 子 Agent 调用纪律（`SA-V1.0`）

- 每次调用子 Agent 前，必须在 commentary 中向用户标明：Agent 名称、任务等级、任务类型、请求模型、reasoning effort、选择理由、上下文方式、允许读写路径及是否允许继续生成子 Agent。并行调用可合并为一张表，但不得省略任一 Agent。调用信息属于透明披露；在 `AUTOPILOT-PLAN-V1.1-FINAL` 激活的 GREEN 阶段，披露不等于需要等待用户逐个批准。
- 默认显式指定模型和 reasoning effort。若因完整上下文继承而未显式指定，必须写“继承主 Agent，精确型号未独立验证”；不得把计划型号、主 Agent 型号或模型家族猜测成实际型号。
- **D/E 角色抽象（Bootstrap 2026-08-14，`AUTOPILOT-PLAN-V1.1-FINAL`）**：治理层只冻结能力角色，不永久绑定产品名。`E=Execution`、`E2=Independent Execution/Checker`、`D=Decision/Reviewer`、`D-red=independent D reviewer`。Pilot #1 runtime mapping 冻结为：E/E1/E2 = `deepseek-v4-flash`（high），D/YELLOW、D/Macro = `deepseek-v4-pro`（high）。具体映射见 `08_项目管理/模型分级与任务路由规则.md` 与 `08_项目管理/全流程自动推进计划_AUTOPILOT-PLAN-V1.1.md`；未来模型变化只更新 mapping，不改风险规则。
- **L2 放行规则（Bootstrap 2026-08-14）**：旧规则“所有 L2 必须 D 审阅”废止。满足 `AUTOPILOT-PLAN-V1.1-FINAL` §2.3 全部 10 条条件时 L2-GREEN 可经 `E1 + E2 + mechanical acceptance` 自动放行（不强制 D）；存在新接口接缝/可定位差异等为 L2-YELLOW（fresh D/Pro-high 只读审阅，最多 1 次 D adjudication + 1 次受限 patch/rebind，仍失败升 RED）；涉及题意/公式/状态转移/指标/容差/搜索空间/oracle 真实性/强结论为 L2-RED（立即 Human Gate，0 次静默自动修复）。
- 子 Agent 默认 `may_spawn_children=false`，不得自行创建孙级 Agent；需要多级委派时，必须在派单包中给出原因、数量上限、模型路由和文件所有权。
- 一个文件同一时刻只能有一个写入 Agent；未明确授予写权限的子 Agent 一律只读。checker Agent 只能读取冻结契约、参数、schema、原始输出和必要日志，不接收主实现者的推理摘要。
- 子 Agent 完成后，主 Agent 必须汇报 Agent ID、请求模型、模型来源（显式/继承）、运行时型号是否可独立验证、实际改动、验收结果和是否生成下级 Agent。详细协议见 `08_项目管理/模型分级与任务路由规则.md`，派单必须使用 `执行模型派单模板.yaml`。

## 模型路由（`MODEL_ROUTING_PRO_MAX_V1.0`）

- **L3/YELLOW 与 L4 semantic review 必须走 `pro_max_review` 且 `VERIFIED_PRO_MAX`**（fresh spawn + `deepseek-pro-max`/`deepseek-v4-pro` + reasoning=max + workspace delta=0）；无 VERIFIED_PRO_MAX 不得 PASS formal task；Pro-Max 失败禁止 fallback 到 Flash/Pro-high（ROUTING_BLOCKED → STOP）。触发清单、packet 模板与 ROUTE-01..12 见 `08_项目管理/MODEL_ROUTING_PRO_MAX_V1.0.md`；路由证据根 `05_结果/governance/model_routing/`。

## 自动驾驶治理（`AUTOPILOT-PLAN-V1.1-FINAL`，Pilot #1）

- 当前自动推进治理依据：`08_项目管理/全流程自动推进计划_AUTOPILOT-PLAN-V1.1.md`。
- Pilot #1 授权范围：G2-03 S2 完成节点 → Whole G2 Macro Gate（无条件停机）。禁止自动进入 G3 / H1 formal / H2 / 100-device formal run / Q2 正式结果 / Q3 K 推荐 / Q4 建议 / G7 提交。
- 风险分级：GREEN（自动）/ YELLOW（fresh D 只读，最多一次受限 patch）/ RED（立即 Human Gate，0 次静默修复）。
- 任何 patch / rebind / spec / config / checker / schema 变化后必须产出 `INVALIDATION_REPORT` 才能复用旧 PASS；禁止“修完 bug 后沿用修复前 formal PASS”。
- 正式运行必须绑定 run_id + hash + immutable evidence 目录；失败 formal run 保留不覆盖；chat/debug/手算不得作为论文正式数字源。
- 崩溃恢复只信磁盘与 Git（AGENTS.md → CURRENT_STATE → CHANGELOG → task package → Git HEAD/status → 最近 accepted commit → run manifest），禁止靠聊天记忆或 reset/clean 不明工作。
- 预算：soft_budget 到达后停止非必要 D/Pro 与探索支线但继续必要硬检查；hard_budget 到达立即停止等 Human Gate；不得自行提高预算。
