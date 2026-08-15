# H2：后验 Rollout 条件候选

> 当前状态：**设计已冻结（2026-08-15 Human Gate VERIFIED FINAL PASS / DESIGN FREEZE APPROVED；冻结权威规格 = `08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT.md`，状态 FINAL_FREEZE_ACCEPTED）；实现/调参仍 NOT AUTHORIZED。** H2 只有在 G3 出口通过 `CR-V3.1/C23–C25` 才能进入实验。

## 1. 为什么不是当前主模型

固定 FCFS 已大幅压缩派工自由度。H2 只有在 H1 日志显示存在足够多、且可能影响工期的启停或更新决策点时才有价值；否则其计算成本和信息泄漏风险不值得承担。

## 2. 允许的动作

- 合法 FCFS 队首立即启动；
- 暂缓到同一装置某个已排定的兄弟任务结果；
- 空闲老设备继续服务队首；
- 空闲老设备先预防更换。

不得越过队首、自由重排装置、改变测试内容或读取隐藏真相。

## 3. 信息边界

rollout 只读可观察历史。每个续演世界必须：

- 按已观察结果重新采样真实缺陷后验；
- 按设备已存活至当前年龄的条件分布重采样剩余寿命；
- 使用独立 rollout 子流生成未来观测；
- 禁止复制主 DES 的隐藏真实状态或预抽未来寿命。

候选首动作 `a` 后，统一按 H1 推演到全批吸收：

\[
\widehat Q_M(s,a)=\frac1M\sum_{m=1}^M
[T_{end}^{(m)}(s;a\rightarrow H1)-t(s)].
\]

## 4. 准入门

1. `CR-V3.1/C24`：H1 日志给出真实机会密度和墙钟预算，冻结 `M`、评估上限、稳定性与样本划分；
2. `CR-V3.1/C23`：后验、信息、动作和 FCFS 边界全部通过；
3. `CR-V3.1/C25`：留出批次的配对收益在预注册同时置信下排除 0，动作稳定且实测不超预算。

任一失败即删除 H2，正式路线保留 H1/R1。H2 删除后不以验证工程补位成第三项创新。

## 5. 冻结设计同步（2026-08-15 Human Gate DESIGN FREEZE APPROVED）

> 本节约定的冻结设计以 `08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT.md`（FINAL_FREEZE_ACCEPTED）为唯一权威细节来源；本节为该权威规格在 H2 模型层的最小同步摘要。若本节与权威规格冲突，以权威规格为准。

### 5.1 动作集（冻结）

- `A0 = START_HEAD`：立即启动合法 FCFS 队首（dispatch 点的 H1 默认）。
- `A0b = H1_NOOP / ADVANCE_EVENT`：无合法 START_HEAD 时 H1 的默认续演——不主动 PM、保持资源 idle、推进至下一已排定事件/下一合法 wakeup、重跑事件闭包与派工判断；**非战略等待、非 WAIT_EVENT、不改变 FCFS**；maintenance 点的 `a_H1`。
- `A1 = WAIT_EVENT`：暂缓队首启动，锚定同装置另一在途任务已排定的完成事件 e；合法当且仅当 STRICT（`t<e<latest_start`）或 **BOUNDARY（`e==latest_start`，已批准为合法 WAIT）**。
- `A2a = PM_WITH_HEAD`：存在合法队首时先预防更换（+校准）再重新判队首（dispatch 点）。
- `A2b = PM_IDLE`：设备空闲时主动预防更换（+校准）；**与 `A0b` 比较，不得与非合法 START_HEAD 比较**；非强制动作。

### 5.2 两类决策点（冻结）

- **DISPATCH_DECISION_POINT**：该资源存在合法 FCFS 队首；候选 ⊂ `{A0, A1(STRICT/BOUNDARY), A2a(若 eligible)}`；`a_H1 = A0`。
- **MAINTENANCE_DECISION_POINT**（H2-only）：该资源无合法 START_HEAD，且设备 idle and available、age≥120、非 mandatory、批中仍有 future potential demand、换新+校准可在当前班完整结束；可出现在 **queue empty** 或 **queue nonempty but no legal START_HEAD**；候选 = `{A0b, A2b}`；`a_H1 = A0b`。
- 同一资源同一事件闭包内**至多一个决策点**（dispatch 或 maintenance，禁止重复生成）；决策点按 **canonical 资源序 A/B/C/E** 逐资源判定；`dp` 索引为（世界、历史、配置、代码）的纯函数。
- **quota class ≠ action availability**：quota class 只是采样分类，不影响该点本来的合法候选动作。

### 5.3 ONLINE quota（冻结）

- `W_cap = ⌈C_eval*/2⌉`、`P_cap = ⌊C_eval*/2⌋`（C_eval*=6 → 3+3；C_eval*=8 → 4+4），为**独立在线硬上限**：no cross-side borrowing、unused capacity expires、no future candidate count、no retroactive selection；`selected_for_rollout(t)` 只依赖 history ≤ t。
- **wait**：按发生时间在线取前 W_cap 个 wait-class 点（含 both 点，B-3 归属 wait 优先）；达 cap 后不再 rollout。
- **PM**：年龄桶 B1=[120,160)、B2=[160,200)、B3=[200,240) 各至多 1 个 bucket-first slot（某桶首次 PM-only 点出现即占用）；P_cap=4 时恰 1 个 extra slot（bucket-first 已用且 PM cap 未耗尽的首个后续 PM-only 点即时占用）；P_cap=3 无 extra slot；未出现桶额度失效；不跨桶回补、不回溯、不读未来桶。

### 5.4 边界（BOUNDARY 契约同步）

- 「早于或等于最迟启动时刻的已排定完成事件」为合法 WAIT 条件（`问题契约.md` §1.3.2/§7.5、`高级模型技术补充_V3.1.md` §5.3 已同步）；`now + duration ≤ shift_end`（恰班末完成合法）保持；未扩大到其他班界/启动规则。

