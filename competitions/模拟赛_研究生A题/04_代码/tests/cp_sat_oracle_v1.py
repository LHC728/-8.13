# -*- coding: utf-8 -*-
"""G2-03 S2：独立 CP-SAT oracle（CR-V3.1/C08 确定性小例异源核验）

独立性硬隔离
============
本模块是 G2-03 的独立验证实现（G2_03_S2_CP_SAT_ORACLE_IMPLEMENTER）：
- 不读取、不 import、不通过外部进程调用主 DES 的确定性实现、显式状态模型或
  主 DES 测试文件；
- 不读取任何 DES 派生数据（事件日志、时间线、汇总、DES 计算的
  release/start/finish、队列顺序、终态）；
- 求解输入只取 fixture primitive 字段（fixture_id / config / scripted_outcomes /
  scripted_real_states，见 extract_fixture_primitive）；验收断言是测试侧只读材料，
  绝不进入求解。

时间建模（整数 tick）
====================
CP-SAT 内部只用整数 tick：1 tick = 10 min = 1/6 h。fixture 时间先经
fractions.Fraction 精确解析，验证 time*6 为整数，否则显式失败
NON_INTEGER_CP_SAT_TICK。禁止 float 运算、round、容差阈值及任何
int(x*6) 式近似换算（float 输入一律显式拒绝）。
输出：整数 tick + 精确 Fraction/字符串小时表示。

建模范式（禁止 event-loop 伪装）
================================
只用 CP-SAT 变量、interval、precedence、capacity、calendar-domain 与 reified 逻辑
约束建模；没有事件日历、dispatch 循环、优先级队列或队列可变模拟；与主 DES 不共享
任何 transition function / dispatch loop / queue mutation 逻辑。

为什么得到 fixed-FCFS earliest canonical 时间线，而非自由最优调度
------------------------------------------------------------------
1) 固定 FCFS 顺序：每类资源（A/B/C/E）的任务按冻结键
   (release_time, device_id, process_order, effective_attempt_no) 全序排列。
   资源内 process 恒定，因此只比较 (release, device, attempt)。release 是
   CP-SAT 自己的变量（重测 release = 首败完成时刻；E release = A/B/C 全 PASS
   时刻；周转引入的新装置 release = 周转完成时刻），因此用 reified 的
   lt/eq/gt 比较 + 蕴含编码任务先后，绝不读 DES 队列顺序。
2) 最早期望 canonicalization：H1 的『合法队首尽快启动』等价于每个任务在其硬下界
   （release、前序任务资源占用结束、班窗可行时刻）处启动。本系统中一切 release
   约束对更早的完成时刻单调不减（更早完成只会更早释放下游任务），因此逐任务
   最早期望调度是唯一的，且恰为『最小化全部任务 start 之和』的解。
   仅 Minimize(makespan) 会允许任务被任意推迟而不改变 T（例如 F9b 中 device3
   的 A 可晚启动而 T 仍为 15），那不是冻结的 canonical 时间线。目标函数因此取
   sum(start of every released task) + sum(turnover 起始时刻)，其中 turnover
   起始用于钉住『device 3 进入先空闲 bay』的 argmin 比较。
3) 装置入场 FCFS：装置按批次序号排队；device 3 进入第一个完成周转的 bay
   （end_tv_1 与 end_tv_2 的 reified 比较），device 4 进入另一个 bay；
   entry_3 < entry_4 由该 argmin 结构自动成立。不同 bay 的 turnover 不共享
   任何全局运输资源（SEM-23），模型中没有全局 transport capacity 约束。

内生 release 独立推导（严禁读 DES release）
===========================================
- retest_release(j) = finish(first_effective_attempt(j))，finish 取自 CP-SAT
  自己的变量；
- E_release = A/B/C 三条 flow 全部 PASS 后的时刻（max of pass ends，CP-SAT
  自己的 A/B/C 完成变量 + 脚本化结果推导）；
- turnover 引入的新装置 A/B/C release = CP-SAT 自己的 turnover 完成时刻；
- D 不作为随机/调度决策变量；其逻辑创建时刻 = E logical release tick
  （= ABC fully PASS 且装置仍 PENDING 的时刻），仅作报告字段。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from fractions import Fraction

import ortools
from ortools.sat.python import cp_model

ORTOOLS_PINNED_VERSION = "9.15.6755"
TICKS_PER_HOUR = 6
PROCESSES = ("A", "B", "C", "E")
ABC = ("A", "B", "C")
DEFAULT_SOLVER_PARAMETERS = {
    "num_search_workers": 1,
    "random_seed": 0,
    "max_time_in_seconds": 120.0,
}


class OracleError(Exception):
    """CP-SAT oracle 错误基类。"""


class ORTOOLS_VERSION_MISMATCH(OracleError):
    """ORTools 版本与冻结版本 9.15.6755 不一致（禁止 unversioned fallback）。"""


class NON_INTEGER_CP_SAT_TICK(OracleError):
    """时间不是 1/6 h（10 min）的整数倍，无法进入整数 tick 域。"""


class INVALID_FIXTURE(OracleError):
    """fixture primitive 数据违反冻结契约（SEM-21 等）。"""


class CP_SAT_NO_SOLUTION(OracleError):
    """CP-SAT 无可行解 / 未在时限内求解。"""


def _check_ortools_version() -> None:
    if ortools.__version__ != ORTOOLS_PINNED_VERSION:
        raise ORTOOLS_VERSION_MISMATCH(
            "预期 ortools==%s，实际 %r；禁止静默使用其他版本。" % (ORTOOLS_PINNED_VERSION, ortools.__version__))


_check_ortools_version()


def require_ortools_version() -> str:
    """启动版本守卫：ortools.__version__ == '9.15.6755'，不一致显式 FAIL。"""
    _check_ortools_version()
    return ortools.__version__


# ---------------------------------------------------------------------------
# 精确时间转换（无 float）
# ---------------------------------------------------------------------------

def parse_hours_exact(value) -> Fraction:
    """把小时值精确解析为 Fraction；float/布尔输入显式拒绝。"""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise NON_INTEGER_CP_SAT_TICK("布尔值不能作为小时输入: %r" % (value,))
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        raise NON_INTEGER_CP_SAT_TICK("禁止 float 小时输入: %r；请用字符串/Fraction 精确表示" % (value,))
    return Fraction(str(value).strip())


def hours_to_ticks(value) -> int:
    """小时 -> 整数 tick；非 1/6 h 整数倍时显式 FAIL：NON_INTEGER_CP_SAT_TICK。"""
    f = parse_hours_exact(value)
    t = f * TICKS_PER_HOUR
    if t.denominator != 1:
        raise NON_INTEGER_CP_SAT_TICK(
            "时间 %s h 不是 1/6 h 的整数倍（= %s tick）" % (f, t))
    return int(t)


def ticks_to_hours(tick: int) -> Fraction:
    """整数 tick -> 精确小时 Fraction（tick / 6）。"""
    return Fraction(int(tick), TICKS_PER_HOUR)


def fraction_to_decimal_str(f: Fraction) -> str:
    """有限十进制展开的分数输出十进制字符串，否则输出 a/b 分数串。"""
    f = Fraction(f)
    x = f.denominator
    while x % 2 == 0:
        x //= 2
    while x % 5 == 0:
        x //= 5
    if x != 1:
        return "%d/%d" % (f.numerator, f.denominator)
    getcontext().prec = 80
    return format(Decimal(f.numerator) / Decimal(f.denominator), "f")


def tick_to_hour_str(tick: int) -> str:
    return fraction_to_decimal_str(ticks_to_hours(tick))


# ---------------------------------------------------------------------------
# Oracle 输出数据结构（稳定公开接口）
# ---------------------------------------------------------------------------

@dataclass
class OracleTask:
    device_id: int
    process: str
    effective_attempt_no: int
    exists: bool
    status: str            # COMPLETED | CANCELLED | NOT_RELEASED
    resource: str
    release_tick: int | None = None
    start_tick: int | None = None
    finish_tick: int | None = None          # 完成时刻或取消（退出）时刻
    scheduled_finish_tick: int | None = None  # start + duration（计划完成）
    bay_id: int | None = None
    duration_tick: int | None = None
    outcome: str | None = None              # PASS | ABNORMAL | None(取消)


@dataclass
class OracleTurnover:
    bay_id: int
    profile: str           # 1h_literal | 0.5h_overlap
    kind: str              # OUT | IN | OVERLAP
    start_tick: int
    finish_tick: int


@dataclass
class OracleDevice:
    device_id: int
    bay_id: int
    entry_tick: int
    terminal_state: str    # PASSED | EXITED
    terminal_tick: int
    exit_tick: int | None = None
    d_created_tick: int | None = None       # = E logical release tick
    pass_processes: list = field(default_factory=list)
    exit_process: str | None = None


@dataclass
class OracleResult:
    fixture_id: str
    status: str
    solver_status: str
    tasks: list
    turnovers: list
    devices: list
    makespan_tick: int
    solver_parameters: dict

    def makespan_hours(self) -> Fraction:
        return ticks_to_hours(self.makespan_tick)

    def makespan_hours_str(self) -> str:
        return tick_to_hour_str(self.makespan_tick)

    def to_dict(self) -> dict:
        """确定性序列化（tick + 精确小时字符串），用于重复求解逐字段比较。"""
        return {
            "fixture_id": self.fixture_id,
            "status": self.status,
            "solver_status": self.solver_status,
            "makespan_tick": self.makespan_tick,
            "makespan_hours": self.makespan_hours_str(),
            "solver_parameters": dict(self.solver_parameters),
            "tasks": [{
                "device_id": t.device_id,
                "process": t.process,
                "effective_attempt_no": t.effective_attempt_no,
                "exists": t.exists,
                "status": t.status,
                "resource": t.resource,
                "bay_id": t.bay_id,
                "duration_tick": t.duration_tick,
                "release_tick": t.release_tick,
                "release_h": tick_to_hour_str(t.release_tick) if t.release_tick is not None else None,
                "start_tick": t.start_tick,
                "start_h": tick_to_hour_str(t.start_tick) if t.start_tick is not None else None,
                "finish_tick": t.finish_tick,
                "finish_h": tick_to_hour_str(t.finish_tick) if t.finish_tick is not None else None,
                "scheduled_finish_tick": t.scheduled_finish_tick,
                "outcome": t.outcome,
            } for t in self.tasks],
            "turnovers": [{
                "bay_id": tv.bay_id,
                "profile": tv.profile,
                "kind": tv.kind,
                "start_tick": tv.start_tick,
                "start_h": tick_to_hour_str(tv.start_tick),
                "finish_tick": tv.finish_tick,
                "finish_h": tick_to_hour_str(tv.finish_tick),
            } for tv in self.turnovers],
            "devices": [{
                "device_id": dv.device_id,
                "bay_id": dv.bay_id,
                "entry_tick": dv.entry_tick,
                "entry_h": tick_to_hour_str(dv.entry_tick),
                "terminal_state": dv.terminal_state,
                "terminal_tick": dv.terminal_tick,
                "terminal_h": tick_to_hour_str(dv.terminal_tick),
                "exit_tick": dv.exit_tick,
                "d_created_tick": dv.d_created_tick,
                "pass_processes": list(dv.pass_processes),
                "exit_process": dv.exit_process,
            } for dv in self.devices],
        }


# ---------------------------------------------------------------------------
# fixture primitive 提取（拒绝任何 DES 派生字段进入求解）
# ---------------------------------------------------------------------------

PRIMITIVE_FIELDS = ("fixture_id", "config", "scripted_outcomes", "scripted_real_states")


def extract_fixture_primitive(fixture_record: dict) -> dict:
    """只提取 primitive 输入字段；任何其他字段（含验收断言/DES 派生数据）一律忽略。"""
    if not isinstance(fixture_record, dict):
        raise INVALID_FIXTURE("fixture_record 必须是 dict")
    out = {}
    for k in PRIMITIVE_FIELDS:
        if k not in fixture_record:
            raise INVALID_FIXTURE("fixture 缺少 primitive 字段: %s" % k)
        out[k] = fixture_record[k]
    return out


# ---------------------------------------------------------------------------
# CP-SAT 内部模型
# ---------------------------------------------------------------------------

@dataclass
class _TaskModel:
    device_id: int
    process: str
    attempt: int
    duration: int
    start: object          # cp_model.IntVar
    end: object
    occ_end: object        # 资源占用结束：完成时刻 或 取消（退出）时刻
    rel: object            # 逻辑 release（CP-SAT 变量）
    interval: object
    completed: bool
    outcome: str | None
    cancelled: bool


def _add_shift_window(model, start_var, duration, shifts, name):
    """活动必须完整落在一个合法班窗内：存在 shift s 使
    shift_start <= start 且 start + duration <= shift_end（恰好班末结束允许）。"""
    in_shift = [model.NewBoolVar("%s_in_shift_%d" % (name, i)) for i in range(len(shifts))]
    model.AddExactlyOne(in_shift)
    for i, (ss, se) in enumerate(shifts):
        model.Add(start_var >= ss).OnlyEnforceIf(in_shift[i])
        model.Add(start_var + duration <= se).OnlyEnforceIf(in_shift[i])


def _add_fcfs_pair(model, ti, tj, b):
    """b == 1 当且仅当 ti 在 FCFS 键 (release, device, attempt) 上先于 tj。

    release 是 CP-SAT 变量：用 reified lt/eq/gt 比较 + 蕴含编码先后，
    绝不读取 DES 队列顺序。"""
    lt = model.NewBoolVar("lt_%s" % b.Name())
    eq = model.NewBoolVar("eq_%s" % b.Name())
    gt = model.NewBoolVar("gt_%s" % b.Name())
    model.AddExactlyOne(lt, eq, gt)
    model.Add(ti.rel <= tj.rel - 1).OnlyEnforceIf(lt)
    model.Add(tj.rel <= ti.rel - 1).OnlyEnforceIf(gt)
    model.Add(ti.rel == tj.rel).OnlyEnforceIf(eq)
    model.Add(b == 1).OnlyEnforceIf(lt)
    if ti.device_id < tj.device_id:
        model.Add(b == 1).OnlyEnforceIf(eq)
    else:
        model.Add(b == 0).OnlyEnforceIf(eq)
    model.Add(b == 0).OnlyEnforceIf(gt)


def _solve_primitive(prim: dict) -> OracleResult:
    fixture_id = prim["fixture_id"]
    cfg = prim["config"]

    N = int(cfg["batch_size"])
    scenario = cfg["scenario"]
    durations = {p: hours_to_ticks(cfg["durations"][p]) for p in PROCESSES}
    out_t = hours_to_ticks(cfg["transport_out_h"])
    in_t = hours_to_ticks(cfg["transport_in_h"])
    profile = cfg["turnover_profile"]
    if profile == "1h_literal":
        tdur = out_t + in_t
    elif profile == "0.5h_overlap":
        tdur = out_t  # 完整重叠：周转时长 = 单侧运输时长（0.5h = 3 ticks）
    else:
        raise INVALID_FIXTURE("fixture %s: 未知 turnover_profile %r" % (fixture_id, profile))

    pre = cfg.get("deterministic_initial_state", {}).get("preloaded_devices")
    if N == 1:
        if pre != [1]:
            raise INVALID_FIXTURE("fixture %s: SEM-21 违反，batch_size==1 必须 preloaded_devices=[1]" % fixture_id)
    else:
        if pre != [1, 2]:
            raise INVALID_FIXTURE("fixture %s: SEM-21 违反，batch_size>=2 必须 preloaded_devices=[1,2]" % fixture_id)

    # ---- 脚本化结果 -> 固定常数推导（任务存在性 / 终态，独立于 DES） ----
    outcomes = {}
    for rec in prim["scripted_outcomes"]:
        outcomes[(int(rec["device_id"]), rec["process"], int(rec["effective_attempt_no"]))] = rec["outcome"]

    def must_out(d, p, a):
        v = outcomes.get((d, p, a))
        if v is None:
            raise INVALID_FIXTURE("fixture %s: 缺少脚本化结果 (device=%d process=%s attempt=%d)"
                                  % (fixture_id, d, p, a))
        return v

    dev_meta = {}
    for d in range(1, N + 1):
        pass_p, abn_p = {}, {}
        for p in ABC:
            o1 = must_out(d, p, 1)
            o2 = outcomes.get((d, p, 2))
            if o1 == "PASS":
                pass_p[p], abn_p[p] = True, False
            elif o2 is None:
                # 首败 -> 重测被释放但未完成（装置退出时取消）：该工序永不 PASS
                pass_p[p], abn_p[p] = False, False
            elif o2 == "PASS":
                pass_p[p], abn_p[p] = True, False
            else:
                pass_p[p], abn_p[p] = False, True
        all_pass = all(pass_p.values())
        e1_out = must_out(d, "E", 1) if all_pass else None
        e2_out = outcomes.get((d, "E", 2)) if (all_pass and e1_out == "ABNORMAL") else None
        if all_pass and e1_out == "ABNORMAL" and e2_out is None:
            raise INVALID_FIXTURE("fixture %s: E 重测必须完整完成并给出脚本化结果 (device=%d)" % (fixture_id, d))
        exit_by = None
        for p in ABC:
            if abn_p[p]:
                exit_by = p
        if all_pass and e1_out == "ABNORMAL" and e2_out == "ABNORMAL":
            exit_by = "E"
        if (not all_pass) and exit_by is None:
            raise INVALID_FIXTURE("fixture %s: device %d 既未全 PASS 也无二次异常终态" % (fixture_id, d))
        term_type = "EXITED" if exit_by is not None else "PASSED"
        dev_meta[d] = {"pass_p": pass_p, "abn_p": abn_p, "all_pass": all_pass,
                       "e1_out": e1_out, "e2_out": e2_out, "exit_by": exit_by,
                       "term_type": term_type}

    # ---- horizon 与班历 ----
    per_dev_worst = 2 * (durations["A"] + durations["B"] + durations["C"]) + 2 * durations["E"]
    H = (N + 1) * per_dev_worst + (N + 1) * tdur + 60
    if scenario == "isolated_small_case":
        shift_len = hours_to_ticks(cfg["shift_length_h"])
        if shift_len < H:
            raise INVALID_FIXTURE("fixture %s: isolated 单班长度不足以容纳 horizon" % fixture_id)
        shifts = [(0, shift_len)]
    elif scenario == "q3_two_shift":
        K = hours_to_ticks(cfg["shift_length_h"])
        shifts = []
        max_days = (H + 40) // (24 * TICKS_PER_HOUR) + 2
        for day in range(max_days):
            s0 = day * 24 * TICKS_PER_HOUR
            shifts.append((s0, s0 + K))
            shifts.append((s0 + K, s0 + 2 * K))
            if s0 + 2 * K >= H + 40:
                break
        H = max(H, shifts[-1][1])
    else:
        raise INVALID_FIXTURE("fixture %s: 未知 scenario %r" % (fixture_id, scenario))
    H_DOM = H + 100

    # ---- CP-SAT 模型 ----
    model = cp_model.CpModel()

    entry = {d: model.NewIntVar(0, H_DOM, "entry_%d" % d) for d in range(1, N + 1)}
    terminal = {d: model.NewIntVar(0, H_DOM, "terminal_%d" % d) for d in range(1, N + 1)}
    exitv = {d: model.NewIntVar(0, H_DOM, "exit_%d" % d) for d in range(1, N + 1)}
    bay = {d: model.NewIntVar(1, 2, "bay_%d" % d) for d in range(1, N + 1)}
    occ_end = {d: model.NewIntVar(0, H_DOM, "occ_end_%d" % d) for d in range(1, N + 1)}

    model.Add(entry[1] == 0)
    if N >= 2:
        model.Add(entry[2] == 0)
    model.Add(bay[1] == 1)
    if N >= 2:
        model.Add(bay[2] == 2)
    for d in range(1, N + 1):
        model.Add(exitv[d] == terminal[d])
        model.Add(occ_end[d] >= entry[d])

    # ---- 任务变量（存在性已由脚本化结果+冻结流程规则固定） ----
    tasks = []
    tasks_by_key = {}
    pass_end_var = {}
    rel_e1_var = {}

    for d in range(1, N + 1):
        meta = dev_meta[d]
        for p in ABC:
            dur = durations[p]
            o1 = must_out(d, p, 1)
            s1 = model.NewIntVar(0, H_DOM, "s_%d_%s_1" % (d, p))
            e1 = model.NewIntVar(0, H_DOM, "e_%d_%s_1" % (d, p))
            model.Add(e1 == s1 + dur)
            iv1 = model.NewIntervalVar(s1, dur, e1, "iv_%d_%s_1" % (d, p))
            t1 = _TaskModel(d, p, 1, dur, s1, e1, e1, entry[d], iv1, True, o1, False)
            model.Add(s1 >= entry[d])
            tasks.append(t1)
            tasks_by_key[(d, p, 1)] = t1
            if o1 == "ABNORMAL":
                o2 = outcomes.get((d, p, 2))
                s2 = model.NewIntVar(0, H_DOM, "s_%d_%s_2" % (d, p))
                e2 = model.NewIntVar(0, H_DOM, "e_%d_%s_2" % (d, p))
                if o2 is not None:
                    model.Add(e2 == s2 + dur)
                    iv2 = model.NewIntervalVar(s2, dur, e2, "iv_%d_%s_2" % (d, p))
                    t2 = _TaskModel(d, p, 2, dur, s2, e2, e2, e1, iv2, True, o2, False)
                else:
                    # 重测被装置退出取消：end == 退出时刻；已启动且严格早于退出
                    model.Add(e2 == exitv[d])
                    model.Add(s2 >= e1)
                    model.Add(s2 + 1 <= exitv[d])
                    model.Add(exitv[d] <= s2 + dur - 1)
                    # 取消片段的资源占用区间 [start, exit)，长度是单变量（affine）
                    sz2 = model.NewIntVar(1, H_DOM, "sz_%d_%s_2" % (d, p))
                    model.Add(sz2 == e2 - s2)
                    iv2 = model.NewIntervalVar(s2, sz2, e2, "iv_%d_%s_2" % (d, p))
                    t2 = _TaskModel(d, p, 2, dur, s2, e2, e2, e1, iv2, False, None, True)
                model.Add(s2 >= e1)
                tasks.append(t2)
                tasks_by_key[(d, p, 2)] = t2
            if meta["pass_p"][p]:
                if o1 == "PASS":
                    pass_end_var[(d, p)] = e1
                else:
                    pass_end_var[(d, p)] = tasks_by_key[(d, p, 2)].end

        if meta["all_pass"]:
            rel_e1 = model.NewIntVar(0, H_DOM, "rel_E_%d" % d)
            model.AddMaxEquality(rel_e1, [pass_end_var[(d, p)] for p in ABC])
            rel_e1_var[d] = rel_e1
            e1o = meta["e1_out"]
            sE1 = model.NewIntVar(0, H_DOM, "s_%d_E_1" % d)
            eE1 = model.NewIntVar(0, H_DOM, "e_%d_E_1" % d)
            model.Add(eE1 == sE1 + durations["E"])
            ivE1 = model.NewIntervalVar(sE1, durations["E"], eE1, "iv_%d_E_1" % d)
            tE1 = _TaskModel(d, "E", 1, durations["E"], sE1, eE1, eE1, rel_e1, ivE1, True, e1o, False)
            model.Add(sE1 >= rel_e1)
            tasks.append(tE1)
            tasks_by_key[(d, "E", 1)] = tE1
            if e1o == "ABNORMAL":
                e2o = meta["e2_out"]
                sE2 = model.NewIntVar(0, H_DOM, "s_%d_E_2" % d)
                eE2 = model.NewIntVar(0, H_DOM, "e_%d_E_2" % d)
                model.Add(eE2 == sE2 + durations["E"])
                ivE2 = model.NewIntervalVar(sE2, durations["E"], eE2, "iv_%d_E_2" % d)
                tE2 = _TaskModel(d, "E", 2, durations["E"], sE2, eE2, eE2, eE1, ivE2, True, e2o, False)
                model.Add(sE2 >= eE1)
                tasks.append(tE2)
                tasks_by_key[(d, "E", 2)] = tE2

        # ---- 终态 ----
        if meta["term_type"] == "EXITED":
            if meta["exit_by"] == "E":
                cand = [tasks_by_key[(d, "E", 2)].end]
            else:
                cand = [tasks_by_key[(d, meta["exit_by"], 2)].end]
            model.AddMaxEquality(terminal[d], cand)
        else:
            if meta["e1_out"] == "PASS":
                model.Add(terminal[d] == tasks_by_key[(d, "E", 1)].end)
            else:
                model.Add(terminal[d] == tasks_by_key[(d, "E", 2)].end)

    # ---- 班窗可行性（no-cross-shift；恰好班末结束允许） ----
    for i, t in enumerate(tasks):
        _add_shift_window(model, t.start, t.duration, shifts, "tw_%d" % i)

    # ---- 每类资源容量 1 + 固定 FCFS 顺序（reified release 比较） ----
    by_res = {r: [] for r in PROCESSES}
    for t in tasks:
        by_res[t.process].append(t)
    for r in PROCESSES:
        lst = by_res[r]
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                ti, tj = lst[i], lst[j]
                if ti.device_id == tj.device_id:
                    # 同装置：attempt 1 恒先于 attempt 2（release 严格递增）
                    if ti.attempt > tj.attempt:
                        ti, tj = tj, ti
                    model.Add(tj.start >= ti.occ_end)
                else:
                    b = model.NewBoolVar("ord_%s_%d_%d__%d_%d"
                                         % (r, ti.device_id, ti.attempt, tj.device_id, tj.attempt))
                    _add_fcfs_pair(model, ti, tj, b)
                    model.Add(tj.start >= ti.occ_end).OnlyEnforceIf(b)
                    model.Add(ti.start >= tj.occ_end).OnlyEnforceIf(b.Not())

    # ---- 每类资源容量 1：NoOverlap（与 FCFS 全序一致，显式表示容量 1） ----
    for r in PROCESSES:
        r_ivs = [t.interval for t in by_res[r] if t.interval is not None]
        if r_ivs:
            model.AddNoOverlap(r_ivs)

    # ---- 台位（bay）与周转 ----
    start_tv = end_tv = succ3_eq1 = None
    tv_ivs = {}
    if N >= 3:
        start_tv = {b: model.NewIntVar(0, H_DOM, "tv_start_%d" % b) for b in (1, 2)}
        end_tv = {b: model.NewIntVar(0, H_DOM, "tv_end_%d" % b) for b in (1, 2)}
        model.Add(start_tv[1] >= terminal[1])
        model.Add(start_tv[2] >= terminal[2])
        for b in (1, 2):
            model.Add(end_tv[b] == start_tv[b] + tdur)
            _add_shift_window(model, start_tv[b], tdur, shifts, "tv_%d" % b)
        # device 3 进入先完成周转的 bay（canonical 装置入场 FCFS）
        succ3_eq1 = model.NewBoolVar("succ3_eq1")
        model.Add(end_tv[1] <= end_tv[2]).OnlyEnforceIf(succ3_eq1)
        model.Add(end_tv[1] >= end_tv[2] + 1).OnlyEnforceIf(succ3_eq1.Not())
        model.Add(bay[3] == 1).OnlyEnforceIf(succ3_eq1)
        model.Add(bay[3] == 2).OnlyEnforceIf(succ3_eq1.Not())
        model.Add(entry[3] == end_tv[1]).OnlyEnforceIf(succ3_eq1)
        model.Add(entry[3] == end_tv[2]).OnlyEnforceIf(succ3_eq1.Not())
        if N == 4:
            model.Add(bay[4] == 2).OnlyEnforceIf(succ3_eq1)
            model.Add(bay[4] == 1).OnlyEnforceIf(succ3_eq1.Not())
            model.Add(entry[4] == end_tv[2]).OnlyEnforceIf(succ3_eq1)
            model.Add(entry[4] == end_tv[1]).OnlyEnforceIf(succ3_eq1.Not())
        # 每个 bay 的周转存在性（N==4 两 bay 都有后继；N==3 只有 succ3 所在 bay）
        for b in (1, 2):
            if N == 4:
                has_tv = model.NewBoolVar("has_tv_%d" % b)
                model.Add(has_tv == 1)
            else:
                has_tv = succ3_eq1 if b == 1 else succ3_eq1.Not()
            tv_ivs[b] = model.NewOptionalIntervalVar(
                start_tv[b], tdur, end_tv[b], has_tv, "tv_iv_%d" % b)
    # 装置占位到自身终态；周转作为独立 interval 占用 bay（[terminal_pred, entry_succ)）
    for d in range(1, N + 1):
        model.Add(occ_end[d] == terminal[d])

    # bay 容量显式表示：每 bay 同时至多一台装置占用 + 至多一次周转，全局两台位
    for b in (1, 2):
        ivs = []
        for d in range(1, N + 1):
            is_in = model.NewBoolVar("in_bay_%d_dev_%d" % (b, d))
            model.Add(bay[d] == b).OnlyEnforceIf(is_in)
            model.Add(bay[d] != b).OnlyEnforceIf(is_in.Not())
            sz = model.NewIntVar(0, H_DOM, "sz_occ_%d_bay_%d" % (d, b))
            model.Add(sz == occ_end[d] - entry[d])
            ivs.append(model.NewOptionalIntervalVar(
                entry[d], sz, occ_end[d], is_in, "occ_iv_dev_%d_bay_%d" % (d, b)))
        if N >= 3:
            ivs.append(tv_ivs[b])
        if ivs:
            model.AddNoOverlap(ivs)

    # ---- makespan 与 canonical 目标 ----
    makespan = model.NewIntVar(0, H_DOM, "makespan")
    model.AddMaxEquality(makespan, [terminal[d] for d in range(1, N + 1)])

    obj = [t.start for t in tasks]
    if N >= 3:
        obj.append(start_tv[1])
        obj.append(start_tv[2])
    model.Minimize(sum(obj))

    # ---- 求解（确定性：单 worker + 固定种子） ----
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = DEFAULT_SOLVER_PARAMETERS["num_search_workers"]
    solver.parameters.random_seed = DEFAULT_SOLVER_PARAMETERS["random_seed"]
    solver.parameters.max_time_in_seconds = DEFAULT_SOLVER_PARAMETERS["max_time_in_seconds"]
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise CP_SAT_NO_SOLUTION("fixture %s: CP-SAT 返回 %s（无可行解或超时）"
                                 % (fixture_id, solver.StatusName(status)))
    solver_status = solver.StatusName(status)

    # ---- 结果抽取 ----
    out_tasks = []
    for d in range(1, N + 1):
        bay_d = solver.Value(bay[d])
        for p in ABC:
            for a in (1, 2):
                t = tasks_by_key.get((d, p, a))
                out_tasks.append(_task_to_output(t, solver, d, p, a, bay_d))
        for a in (1, 2):
            t = tasks_by_key.get((d, "E", a))
            out_tasks.append(_task_to_output(t, solver, d, "E", a, bay_d))

    out_tvs = []
    if N >= 3:
        for b in (1, 2):
            if N == 4:
                present = True
            else:
                present = (solver.Value(succ3_eq1) == 1) if b == 1 else (solver.Value(succ3_eq1) == 0)
            if present:
                s = solver.Value(start_tv[b])
                e = solver.Value(end_tv[b])
                if profile == "1h_literal":
                    out_tvs.append(OracleTurnover(b, profile, "OUT", s, s + out_t))
                    out_tvs.append(OracleTurnover(b, profile, "IN", s + out_t, e))
                else:
                    out_tvs.append(OracleTurnover(b, profile, "OVERLAP", s, e))

    out_devs = []
    for d in range(1, N + 1):
        meta = dev_meta[d]
        ts = meta["term_type"]
        d_created = solver.Value(rel_e1_var[d]) if meta["all_pass"] else None
        out_devs.append(OracleDevice(
            device_id=d,
            bay_id=solver.Value(bay[d]),
            entry_tick=solver.Value(entry[d]),
            terminal_state=ts,
            terminal_tick=solver.Value(terminal[d]),
            exit_tick=solver.Value(terminal[d]) if ts == "EXITED" else None,
            d_created_tick=d_created,
            pass_processes=[p for p in ABC if meta["pass_p"][p]] + (["E"] if ts == "PASSED" else []),
            exit_process=meta["exit_by"],
        ))

    mk = solver.Value(makespan)
    for t in out_tasks:
        if t.exists and t.status == "COMPLETED":
            if t.finish_tick != t.start_tick + t.duration_tick:
                raise OracleError("内部一致性: 完成任务 finish != start + duration (%s)" % (t,))
    if max(dv.terminal_tick for dv in out_devs) != mk:
        raise OracleError("内部一致性: makespan != max(terminal)")

    return OracleResult(fixture_id=fixture_id, status=solver_status, solver_status=solver_status,
                        tasks=out_tasks, turnovers=out_tvs, devices=out_devs,
                        makespan_tick=mk, solver_parameters=dict(DEFAULT_SOLVER_PARAMETERS))


def _task_to_output(t, solver, device_id, process, attempt, bay_val):
    if t is None:
        return OracleTask(device_id=device_id, process=process, effective_attempt_no=attempt,
                          exists=False, status="NOT_RELEASED", resource=process, bay_id=None)
    start = solver.Value(t.start)
    occ_end = solver.Value(t.occ_end)
    return OracleTask(
        device_id=device_id, process=process, effective_attempt_no=attempt,
        exists=True,
        status="COMPLETED" if t.completed else "CANCELLED",
        resource=process, bay_id=bay_val,
        release_tick=solver.Value(t.rel),
        start_tick=start,
        finish_tick=occ_end,
        scheduled_finish_tick=start + t.duration,
        duration_tick=t.duration,
        outcome=t.outcome,
    )


# ---------------------------------------------------------------------------
# 稳定公开接口
# ---------------------------------------------------------------------------

def solve_fixture(fixture_record: dict) -> OracleResult:
    """fixture primitive input -> 独立 CP-SAT canonical 时间线。

    只使用 primitive 字段求解；验收断言/DES 派生字段绝不进入。"""
    require_ortools_version()
    prim = extract_fixture_primitive(fixture_record)
    return _solve_primitive(prim)
