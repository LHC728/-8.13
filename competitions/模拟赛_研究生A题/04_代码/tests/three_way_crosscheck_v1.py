# -*- coding: utf-8 -*-
"""G2-03 S3：三方机械对拍比较器（three-way crosscheck comparator；bridge，stdlib-only）

角色
====
本模块是 G2-03 S3 的比较器 / 桥接器，不是新实现：
- 不重新实现 DES 事件引擎，不重新实现 CP-SAT 约束模型；
- 只把三方的确定性输出归一到同一中立坐标后逐字段精确比较：
    1) accepted deterministic DES（04_代码/main_model/des/deterministic_des_v1.py，stdlib）；
    2) independent CP-SAT oracle（04_代码/tests/cp_sat_oracle_v1.py，OR-Tools 9.15.6755 版本守卫）；
    3) frozen hand 期望（fixture JSON acceptance 字段 + 01_审计/手算样例_K9跨班重测.md 的
       机械转录常量表，见本文件 HAND_* 常量；K9 权威文件路径见 K9_AUTHORITATIVE_PATH）。
- 本模块顶层只 import 标准库；DES / CP-SAT 模块在运行入口内延迟导入
  （主 DES stdlib-only 不变；oracle 自带 OR-Tools 版本守卫，缺失时 import 显式失败）。

时间归一（无 float）
====================
- DES 侧：事件日志时间是精确 Fraction 小时（如 "11/2"）。
- CP-SAT 侧：整数 tick，1 tick = 10 min = 1/6 h（G2-03-SPEC-V1.0.2 §9b.integer_time_scaling）。
- 统一坐标：小时（Fraction）。比较恒等式 tick*6 == hours（等价 hours*6 == tick 且为整数）。
  任何非 1/6h 整数倍的 hours 在换算到 tick 时显式失败（NonIntegerTickError），
  禁止浮点近似、四舍五入与容差比较。

canonical 规则（cp_sat_oracle_spec.comparison_output / release_independence）
============================================================================
- 冻结 FCFS canonical 时间线对每个 fixture 唯一（oracle 用 reified release 比较 +
  最小化全部 start 之和做最早期望 canonicalization），因此逐事件精确比较；
- 比较按任务键 (device_id, process, effective_attempt_no) 排序进行，不依赖任何一侧
  任务列表的内部排列顺序（多个合法 CP-SAT 解仅内部排列不同时被归一掉，不判 FAIL）；
- 只比较冻结 fixture 要求唯一的量：task existence、release/start/finish、resource、
  bay、attempt、terminal state/time、makespan(T)，外加 turnover 时序、S/PL/PW 与
  K9 YXB 只读断言。
- 三方一致 -> PASS；任一方与 frozen hand 或 DES-vs-CP-SAT 不一致 -> FAIL 并给出
  精确差异（fixture、字段、双方值），由调用方按规则分类（比较器 bug / 实现差异 /
  语义冲突），本模块不改写任何一侧输出。

判定纪律（本模块不修改任何既有文件）
====================================
- 只读输入：fixture JSON、DES event_log/metrics、oracle OracleResult、冻结 hand 常量。
- 不 patch DES / CP-SAT / fixture / spec；不写 05_结果；不运行 formal evidence。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 冻结常量（G2-03-SPEC-V1.0.2）
# ---------------------------------------------------------------------------

TICKS_PER_HOUR = 6  # 1 tick = 10 min = 1/6 h
PROCESSES = ("A", "B", "C", "E")
PROCESS_ORDER = {"A": 0, "B": 1, "C": 2, "E": 3}

# 14 个 concrete fixture（F4b/F9b 为 subcase，不注册为 F13/F14）
FIXTURES_ORDER = [
    "F1", "F2", "F3", "F4", "F4b", "F5", "F6", "F7", "F8", "F9", "F9b",
    "F10", "F11", "F12",
]

# 每 fixture 冻结 makespan（tick 与小时；来自 fixture JSON acceptance.T 的机械转录，
# 测试会再断言 == acceptance["T"] 以捕捉转录错误）
EXPECTED_T_TICKS: dict[str, int] = {
    "F1": 33, "F2": 51, "F3": 42, "F4": 63, "F4b": 48, "F5": 30, "F6": 72,
    "F7": 72, "F8": 84, "F9": 72, "F9b": 90, "F10": 69, "F11": 72, "F12": 33,
}
EXPECTED_T_HOURS: dict[str, Fraction] = {
    "F1": Fraction(11, 2), "F2": Fraction(17, 2), "F3": Fraction(7),
    "F4": Fraction(21, 2), "F4b": Fraction(8), "F5": Fraction(5),
    "F6": Fraction(12), "F7": Fraction(12), "F8": Fraction(14),
    "F9": Fraction(12), "F9b": Fraction(15), "F10": Fraction(23, 2),
    "F11": Fraction(12), "F12": Fraction(11, 2),
}

K9_AUTHORITATIVE_PATH = (
    Path(__file__).resolve().parents[2] / "01_审计" / "手算样例_K9跨班重测.md"
)


# ---------------------------------------------------------------------------
# 错误与精确时间换算
# ---------------------------------------------------------------------------


class CrosscheckError(Exception):
    """比较器错误基类。"""


class NonIntegerTickError(CrosscheckError):
    """小时不是 1/6 h（10 min）的整数倍，无法进入整数 tick 域（显式 FAIL）。"""


def parse_hours(value: Any) -> Fraction:
    """把小时值精确解析为 Fraction；float/布尔输入显式拒绝（禁止 float 近似）。"""
    if isinstance(value, bool):
        raise NonIntegerTickError("布尔值不能作为小时输入: %r" % (value,))
    if isinstance(value, float):
        raise NonIntegerTickError("禁止 float 小时输入: %r；请用字符串/Fraction 精确表示" % (value,))
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, Fraction):
        return value
    return Fraction(str(value).strip())


def hours_to_ticks(value: Any) -> int:
    """小时 -> 整数 tick；非 1/6h 整数倍时显式 FAIL：NonIntegerTickError。"""
    f = parse_hours(value)
    t = f * TICKS_PER_HOUR
    if t.denominator != 1:
        raise NonIntegerTickError("时间 %s h 不是 1/6 h 的整数倍（= %s tick）" % (f, t))
    return int(t)


def ticks_to_hours(tick: int) -> Fraction:
    """整数 tick -> 精确小时 Fraction（tick / 6）。"""
    if isinstance(tick, bool) or not isinstance(tick, int):
        raise CrosscheckError("tick 必须是整数，got %r" % (tick,))
    return Fraction(tick, TICKS_PER_HOUR)


def fmt_hours(h: Fraction) -> str:
    """Fraction -> 精确分数字符串（整数时不带分母），与 DES 序列化一致。"""
    h = Fraction(h)
    if h.denominator == 1:
        return str(h.numerator)
    return "%d/%d" % (h.numerator, h.denominator)


def fmt_opt(h: Optional[Fraction]) -> Optional[str]:
    return None if h is None else fmt_hours(h)


def fmt_ticks(h: Optional[Fraction]) -> Optional[int]:
    return None if h is None else hours_to_ticks(h)


# ---------------------------------------------------------------------------
# 冻结 hand 期望（机械转录：fixture JSON acceptance + 手算样例_K9跨班重测.md）
# 任务键 = (device_id, process, effective_attempt_no)；时间字段为分数字符串。
# 'exists': False 表示该任务不应存在（如退出装置无 E 任务）。
# ---------------------------------------------------------------------------

HAND_TASK_EXPECTATIONS: dict[str, dict[tuple[int, str, int], dict[str, Any]]] = {
    "F1": {
        (1, "A", 1): {"exists": True, "start": "0", "finish": "5/2"},
        (1, "B", 1): {"exists": True, "start": "0", "finish": "2"},
        (1, "C", 1): {"exists": True, "start": "0", "finish": "5/2"},
        (1, "E", 1): {"exists": True, "start": "5/2", "finish": "11/2"},
    },
    "F2": {
        (1, "A", 1): {"exists": True, "start": "0"},
        (1, "B", 1): {"exists": True, "start": "0"},
        (1, "C", 1): {"exists": True, "start": "0"},
        (1, "E", 1): {"exists": True, "start": "5/2", "finish": "11/2"},
        (2, "A", 1): {"exists": True, "start": "5/2"},
        (2, "B", 1): {"exists": True, "start": "2"},
        (2, "C", 1): {"exists": True, "start": "5/2"},
        (2, "E", 1): {"exists": True, "start": "11/2", "finish": "17/2"},
    },
    "F3": {
        (1, "A", 1): {"exists": True, "finish": "5/2", "outcome": "PASS"},
        (1, "B", 1): {"exists": True, "finish": "2", "outcome": "ABNORMAL"},
        (1, "B", 2): {"exists": True, "release": "2", "start": "2", "finish": "4", "outcome": "PASS"},
        (1, "C", 1): {"exists": True, "finish": "5/2", "outcome": "PASS"},
        (1, "E", 1): {"exists": True, "start": "4", "finish": "7", "outcome": "PASS"},
    },
    "F4": {
        (1, "A", 1): {"exists": True, "finish": "5/2", "outcome": "ABNORMAL"},
        (1, "A", 2): {"exists": True, "start": "5", "finish": "15/2", "outcome": "ABNORMAL"},
        (1, "B", 1): {"exists": True},
        (1, "C", 1): {"exists": True},
        (1, "E", 1): {"exists": False},
        (2, "A", 1): {"exists": True, "start": "5/2", "finish": "5", "outcome": "PASS"},
        (2, "B", 1): {"exists": True},
        (2, "C", 1): {"exists": True, "start": "5/2", "finish": "5", "outcome": "ABNORMAL"},
        (2, "C", 2): {"exists": True, "start": "5", "finish": "15/2", "outcome": "PASS"},
        (2, "E", 1): {"exists": True, "start": "15/2", "finish": "21/2", "outcome": "PASS"},
    },
    "F4b": {
        (1, "A", 1): {"exists": True, "finish": "5/2", "outcome": "ABNORMAL"},
        (1, "A", 2): {"exists": True, "release": "5/2", "start": "5", "finish": "6", "outcome": "NONE"},
        (1, "B", 1): {"exists": True, "finish": "2", "outcome": "ABNORMAL"},
        (1, "B", 2): {"exists": True, "start": "4", "finish": "6", "outcome": "ABNORMAL"},
        (1, "C", 1): {"exists": True, "finish": "5/2", "outcome": "ABNORMAL"},
        (1, "C", 2): {"exists": True, "release": "5/2", "start": "5", "finish": "6", "outcome": "NONE"},
        (1, "E", 1): {"exists": False},
        (2, "A", 1): {"exists": True},
        (2, "B", 1): {"exists": True},
        (2, "C", 1): {"exists": True},
        (2, "E", 1): {"exists": True, "start": "5", "finish": "8", "outcome": "PASS"},
    },
    "F5": {
        (1, "A", 1): {"exists": True, "finish": "5/2", "outcome": "ABNORMAL"},
        (1, "A", 2): {"exists": True, "start": "5/2", "finish": "5", "outcome": "ABNORMAL"},
        (1, "B", 1): {"exists": True, "outcome": "PASS"},
        (1, "C", 1): {"exists": True, "outcome": "PASS"},
        (1, "E", 1): {"exists": False},
    },
    "F6": {
        (1, "A", 1): {"exists": True, "outcome": "ABNORMAL"},
        (1, "A", 2): {"exists": True, "outcome": "PASS"},
        (1, "B", 1): {"exists": True},
        (1, "C", 1): {"exists": True},
        (1, "E", 1): {"exists": True, "finish": "8", "outcome": "ABNORMAL"},
        (1, "E", 2): {"exists": True, "release": "8", "start": "9", "finish": "12", "outcome": "PASS"},
    },
    "F7": {
        (1, "A", 1): {"exists": True},
        (1, "B", 1): {"exists": True},
        (1, "C", 1): {"exists": True},
        (1, "E", 1): {"exists": True, "finish": "11/2"},
        (2, "A", 1): {"exists": True},
        (2, "B", 1): {"exists": True},
        (2, "C", 1): {"exists": True},
        (2, "E", 1): {"exists": True, "finish": "17/2"},
        (3, "A", 1): {"exists": True, "start": "13/2", "finish": "9", "bay": 1},
        (3, "B", 1): {"exists": True, "start": "13/2", "bay": 1},
        (3, "C", 1): {"exists": True, "start": "13/2", "finish": "9", "bay": 1},
        (3, "E", 1): {"exists": True, "start": "9", "finish": "12", "bay": 1},
    },
    "F8": {
        (1, "A", 1): {"exists": True, "start": "0", "finish": "5/2", "outcome": "PASS"},
        (1, "B", 1): {"exists": True, "start": "0", "finish": "2", "outcome": "PASS"},
        (1, "C", 1): {"exists": True, "start": "0", "finish": "5/2", "outcome": "PASS"},
        (1, "E", 1): {"exists": True, "start": "5/2", "finish": "11/2", "outcome": "PASS"},
        (2, "A", 1): {"exists": True, "start": "5/2", "finish": "5", "outcome": "PASS"},
        (2, "B", 1): {"exists": True, "start": "2", "finish": "4", "outcome": "PASS"},
        (2, "C", 1): {"exists": True, "start": "5/2", "finish": "5", "outcome": "PASS"},
        (2, "E", 1): {"exists": True, "start": "11/2", "finish": "17/2", "outcome": "PASS"},
        (3, "A", 1): {"exists": True, "start": "13/2", "finish": "9", "outcome": "PASS", "bay": 1},
        (3, "B", 1): {"exists": True, "start": "13/2", "finish": "17/2", "outcome": "ABNORMAL", "bay": 1},
        (3, "B", 2): {"exists": True, "release": "17/2", "start": "9", "finish": "11",
                      "outcome": "PASS", "bay": 1},
        (3, "C", 1): {"exists": True, "start": "13/2", "finish": "9", "outcome": "PASS", "bay": 1},
        (3, "E", 1): {"exists": True, "start": "11", "finish": "14", "outcome": "PASS", "bay": 1},
    },
    "F9": {
        (1, "A", 1): {"exists": True},
        (1, "B", 1): {"exists": True},
        (1, "C", 1): {"exists": True},
        (1, "E", 1): {"exists": True, "finish": "11/2"},
        (2, "A", 1): {"exists": True},
        (2, "B", 1): {"exists": True},
        (2, "C", 1): {"exists": True},
        (2, "E", 1): {"exists": True, "finish": "17/2"},
        (3, "A", 1): {"exists": True, "start": "13/2", "finish": "9", "bay": 1},
        (3, "B", 1): {"exists": True, "start": "13/2", "finish": "17/2", "bay": 1},
        (3, "C", 1): {"exists": True, "start": "13/2", "finish": "9", "bay": 1},
        (3, "E", 1): {"exists": True, "start": "9", "finish": "12", "bay": 1},
    },
    "F9b": {
        (1, "A", 1): {"exists": True},
        (1, "B", 1): {"exists": True},
        (1, "C", 1): {"exists": True},
        (1, "E", 1): {"exists": True, "finish": "11/2"},
        (2, "A", 1): {"exists": True},
        (2, "B", 1): {"exists": True, "start": "2", "finish": "4", "outcome": "ABNORMAL"},
        (2, "B", 2): {"exists": True, "start": "4", "finish": "6", "outcome": "ABNORMAL"},
        (2, "C", 1): {"exists": True},
        (2, "E", 1): {"exists": False},
        (3, "A", 1): {"exists": True, "bay": 1},
        (3, "B", 1): {"exists": True, "bay": 1},
        (3, "C", 1): {"exists": True, "bay": 1},
        (3, "E", 1): {"exists": True, "bay": 1},
        (4, "A", 1): {"exists": True, "bay": 2},
        (4, "B", 1): {"exists": True, "bay": 2},
        (4, "C", 1): {"exists": True, "bay": 2},
        (4, "E", 1): {"exists": True, "start": "12", "finish": "15", "bay": 2},
    },
    "F10": {
        (1, "A", 1): {"exists": True},
        (1, "B", 1): {"exists": True},
        (1, "C", 1): {"exists": True},
        (1, "E", 1): {"exists": True, "finish": "11/2"},
        (2, "A", 1): {"exists": True},
        (2, "B", 1): {"exists": True},
        (2, "C", 1): {"exists": True},
        (2, "E", 1): {"exists": True, "finish": "17/2"},
        (3, "A", 1): {"exists": True, "start": "6", "finish": "17/2", "bay": 1},
        (3, "B", 1): {"exists": True, "start": "6", "finish": "8", "bay": 1},
        (3, "C", 1): {"exists": True, "start": "6", "finish": "17/2", "bay": 1},
        (3, "E", 1): {"exists": True, "start": "17/2", "finish": "23/2", "bay": 1},
    },
    "F11": {
        (1, "A", 1): {"exists": True, "outcome": "ABNORMAL"},
        (1, "A", 2): {"exists": True, "outcome": "PASS"},
        (1, "B", 1): {"exists": True},
        (1, "C", 1): {"exists": True},
        (1, "E", 1): {"exists": True, "finish": "8", "outcome": "ABNORMAL"},
        (1, "E", 2): {"exists": True, "start": "9", "finish": "12", "outcome": "PASS"},
    },
    "F12": {
        (1, "A", 1): {"exists": True, "start": "0"},
        (1, "B", 1): {"exists": True, "start": "0", "finish": "2"},
        (1, "C", 1): {"exists": True, "start": "0"},
        (1, "E", 1): {"exists": True, "start": "5/2", "finish": "11/2"},
    },
}

# 装置级期望：terminal_state / terminal（小时）/ d_created（小时；'d_created' 键存在
# 且值为 None 表示该装置不生成 D）/ bay。
HAND_DEVICE_EXPECTATIONS: dict[str, dict[int, dict[str, Any]]] = {
    "F1": {1: {"terminal_state": "PASSED", "terminal": "11/2", "d_created": "5/2", "bay": 1}},
    "F2": {1: {"terminal_state": "PASSED", "terminal": "11/2", "d_created": "5/2", "bay": 1},
           2: {"terminal_state": "PASSED", "terminal": "17/2", "d_created": "5", "bay": 2}},
    "F3": {1: {"terminal_state": "PASSED", "terminal": "7", "d_created": "4", "bay": 1}},
    "F4": {1: {"terminal_state": "EXITED", "terminal": "15/2", "d_created": None, "bay": 1},
           2: {"terminal_state": "PASSED", "terminal": "21/2", "d_created": "15/2", "bay": 2}},
    "F4b": {1: {"terminal_state": "EXITED", "terminal": "6", "d_created": None, "bay": 1},
            2: {"terminal_state": "PASSED", "terminal": "8", "d_created": "5", "bay": 2}},
    "F5": {1: {"terminal_state": "EXITED", "terminal": "5", "d_created": None, "bay": 1}},
    "F6": {1: {"terminal_state": "PASSED", "terminal": "12", "d_created": "5", "bay": 1}},
    "F7": {1: {"terminal_state": "PASSED", "terminal": "11/2", "d_created": "5/2", "bay": 1},
           2: {"terminal_state": "PASSED", "terminal": "17/2", "d_created": "5", "bay": 2},
           3: {"terminal_state": "PASSED", "terminal": "12", "d_created": "9", "bay": 1}},
    "F8": {1: {"terminal_state": "PASSED", "terminal": "11/2", "d_created": "5/2", "bay": 1},
           2: {"terminal_state": "PASSED", "terminal": "17/2", "d_created": "5", "bay": 2},
           3: {"terminal_state": "PASSED", "terminal": "14", "d_created": "11", "bay": 1}},
    "F9": {1: {"terminal_state": "PASSED", "terminal": "11/2", "d_created": "5/2", "bay": 1},
           2: {"terminal_state": "PASSED", "terminal": "17/2", "d_created": "5", "bay": 2},
           3: {"terminal_state": "PASSED", "terminal": "12", "d_created": "9", "bay": 1}},
    "F9b": {1: {"terminal_state": "PASSED", "terminal": "11/2", "d_created": "5/2", "bay": 1},
            2: {"terminal_state": "EXITED", "terminal": "6", "d_created": None, "bay": 2},
            3: {"terminal_state": "PASSED", "terminal": "12", "d_created": "9", "bay": 1},
            4: {"terminal_state": "PASSED", "terminal": "15", "d_created": "23/2", "bay": 2}},
    "F10": {1: {"terminal_state": "PASSED", "terminal": "11/2", "d_created": "5/2", "bay": 1},
            2: {"terminal_state": "PASSED", "terminal": "17/2", "d_created": "5", "bay": 2},
            3: {"terminal_state": "PASSED", "terminal": "23/2", "d_created": "17/2", "bay": 1}},
    "F11": {1: {"terminal_state": "PASSED", "terminal": "12", "d_created": "5", "bay": 1}},
    "F12": {1: {"terminal_state": "PASSED", "terminal": "11/2", "d_created": "5/2", "bay": 1}},
}

# 周转期望：(bay_id, kind, start_h, finish_h)；0.5h_overlap 用单一 OVERLAP 表示
# （物理占用 [start, start+0.5h)，零时长 IN 为日志表示，checker 不重复计占位）。
HAND_TURNOVER_EXPECTATIONS: dict[str, list[tuple[int, str, str, str]]] = {
    "F7": [(1, "OUT", "11/2", "6"), (1, "IN", "6", "13/2")],
    "F8": [(1, "OUT", "11/2", "6"), (1, "IN", "6", "13/2")],
    "F9": [(1, "OUT", "11/2", "6"), (1, "IN", "6", "13/2")],
    "F9b": [(1, "OUT", "11/2", "6"), (1, "IN", "6", "13/2"),
            (2, "OUT", "6", "13/2"), (2, "IN", "13/2", "7")],
    "F10": [(1, "OVERLAP", "11/2", "6")],
}

# S / PL / PW（来自 fixture acceptance）
HAND_METRICS: dict[str, dict[str, int]] = {
    "F1": {"S": 1, "PL": 0, "PW": 0}, "F2": {"S": 2, "PL": 0, "PW": 0},
    "F3": {"S": 1, "PL": 0, "PW": 0}, "F4": {"S": 1, "PL": 0, "PW": 1},
    "F4b": {"S": 1, "PL": 0, "PW": 1}, "F5": {"S": 0, "PL": 0, "PW": 1},
    "F6": {"S": 1, "PL": 0, "PW": 0}, "F7": {"S": 3, "PL": 0, "PW": 0},
    "F8": {"S": 3, "PL": 0, "PW": 0}, "F9": {"S": 3, "PL": 0, "PW": 0},
    "F9b": {"S": 3, "PL": 0, "PW": 1}, "F10": {"S": 3, "PL": 0, "PW": 0},
    "F11": {"S": 1, "PL": 0, "PW": 0}, "F12": {"S": 1, "PL": 0, "PW": 0},
}

# K9 只读 YXB 断言（7.5/18=5/12, 8/18=4/9, 9/18=1/2；分母 18h=108 ticks）
HAND_YXB: dict[str, Fraction] = {
    "A": Fraction(5, 12), "B": Fraction(4, 9), "C": Fraction(5, 12), "E": Fraction(1, 2),
}
K9_YXB_DENOMINATOR_TICKS = 108  # 2 班 x 9h = 18h


# ---------------------------------------------------------------------------
# 中立数据结构（DES 侧与 CP-SAT 侧统一为同一坐标系：小时 Fraction）
# ---------------------------------------------------------------------------


@dataclass
class TaskTiming:
    """一个 (device, process, attempt) 任务的中立时序视图。"""

    key: tuple
    exists: bool
    status: str  # COMPLETED | CANCELLED | RELEASED_UNFINISHED
    release_h: Optional[Fraction] = None
    start_h: Optional[Fraction] = None
    finish_h: Optional[Fraction] = None
    outcome: Optional[str] = None  # PASS | ABNORMAL | NONE
    resource: Optional[str] = None
    bay_id: Optional[int] = None


@dataclass
class DeviceTiming:
    device_id: int
    bay_id: Optional[int] = None
    terminal_state: Optional[str] = None
    terminal_h: Optional[Fraction] = None
    d_created_h: Optional[Fraction] = None


@dataclass
class TurnoverPhase:
    bay_id: int
    kind: str  # OUT | IN | OVERLAP
    start_h: Fraction
    finish_h: Fraction


@dataclass
class DesView:
    fixture_id: str
    tasks: dict
    devices: dict
    turnovers: list
    T_h: Fraction
    metrics: Optional[dict] = None


@dataclass
class OracleView:
    fixture_id: str
    tasks: dict
    devices: dict
    turnovers: list
    T_h: Fraction


def _task_key_of(rec: dict) -> tuple:
    return (rec["device_id"], rec["process"], rec["effective_attempt_no"])


def _des_turnover_phases(event_log: list, profile: str) -> list:
    """从 DES 事件日志提取物理周转区间。

    1h_literal：OUT [out_start, out_complete) + IN [in_start, in_complete)。
    0.5h_overlap：日志在同一时刻记录 OUT_COMPLETE/IN_START/IN_COMPLETE（零时长 IN
    日志表示），物理占用为单个 OVERLAP [out_start, out_complete)。"""
    by_bay: dict[int, dict[str, Fraction]] = {}
    for rec in event_log:
        et = rec.get("event_type")
        if et in ("TURNOVER_OUT_START", "TURNOVER_OUT_COMPLETE",
                  "TURNOVER_IN_START", "TURNOVER_IN_COMPLETE"):
            by_bay.setdefault(rec["bay_id"], {})[et] = parse_hours(rec["event_time"])
    phases: list[TurnoverPhase] = []
    for bay_id in sorted(by_bay):
        ev = by_bay[bay_id]
        if profile == "0.5h_overlap":
            phases.append(TurnoverPhase(bay_id, "OVERLAP",
                                        ev["TURNOVER_OUT_START"], ev["TURNOVER_OUT_COMPLETE"]))
        else:
            phases.append(TurnoverPhase(bay_id, "OUT",
                                        ev["TURNOVER_OUT_START"], ev["TURNOVER_OUT_COMPLETE"]))
            phases.append(TurnoverPhase(bay_id, "IN",
                                        ev["TURNOVER_IN_START"], ev["TURNOVER_IN_COMPLETE"]))
    phases.sort(key=lambda p: (p.bay_id, p.start_h, p.kind))
    return phases


def extract_des(event_log: list, metrics: Optional[dict] = None,
                turnover_profile: str = "1h_literal") -> DesView:
    """从 DES event_log（+metrics）提取中立任务/装置/周转/T 视图（只读，无状态机 import）。

    任务存在性 = 出现过 TASK_RELEASE 记录；取消片段用 TASK_CANCEL（finish=取消时刻，
    outcome=NONE）；完成片段用 ACTIVITY_COMPLETE（outcome 取 OBSERVATION）。"""
    releases: dict[tuple, tuple] = {}
    starts: dict[tuple, tuple] = {}
    completes: dict[tuple, Fraction] = {}
    cancels: dict[tuple, tuple] = {}
    observations: dict[tuple, str] = {}
    devices: dict[int, DeviceTiming] = {}
    sim_end: Optional[Fraction] = None

    for rec in event_log:
        et = rec.get("event_type")
        t = parse_hours(rec["event_time"])
        if et == "TASK_RELEASE":
            key = _task_key_of(rec)
            releases[key] = (parse_hours(rec["release_time"]), rec.get("resource_id"))
        elif et == "ACTIVITY_START":
            key = _task_key_of(rec)
            starts[key] = (t, rec.get("bay_id"))
        elif et == "ACTIVITY_COMPLETE":
            key = _task_key_of(rec)
            completes[key] = t
        elif et == "TASK_CANCEL":
            key = _task_key_of(rec)
            cancels[key] = (t, rec.get("bay_id"))
        elif et == "OBSERVATION_MATERIALIZED":
            key = _task_key_of(rec)
            observations[key] = rec.get("outcome")
        elif et == "DEVICE_TERMINAL":
            dev = devices.setdefault(rec["device_id"], DeviceTiming(device_id=rec["device_id"]))
            dev.terminal_state = rec.get("terminal_state")
            dev.terminal_h = t
        elif et == "D_CREATED":
            dev = devices.setdefault(rec["device_id"], DeviceTiming(device_id=rec["device_id"]))
            dev.d_created_h = t
        elif et == "SIMULATION_END":
            sim_end = t

    tasks: dict[tuple, TaskTiming] = {}
    for key, (release_h, resource_id) in releases.items():
        device_id, process, attempt = key
        start = starts.get(key)
        complete = completes.get(key)
        cancel = cancels.get(key)
        if complete is not None:
            status = "COMPLETED"
            finish: Optional[Fraction] = complete
            outcome = observations.get(key)
        elif cancel is not None:
            status = "CANCELLED"
            finish = cancel[0]
            outcome = "NONE"
        else:
            status = "RELEASED_UNFINISHED"
            finish = None
            outcome = None
        bay = start[1] if start else (cancel[1] if cancel else None)
        tasks[key] = TaskTiming(
            key=key, exists=True, status=status,
            release_h=release_h,
            start_h=start[0] if start else None,
            finish_h=finish,
            outcome=outcome,
            resource=resource_id,
            bay_id=bay,
        )

    for key, start in starts.items():
        dev = devices.setdefault(key[0], DeviceTiming(device_id=key[0]))
        if dev.bay_id is None:
            dev.bay_id = start[1]

    if sim_end is None:
        raise CrosscheckError("event_log 缺少 SIMULATION_END 记录")

    return DesView(fixture_id="des", tasks=tasks, devices=devices,
                   turnovers=_des_turnover_phases(event_log, turnover_profile),
                   T_h=sim_end, metrics=metrics)


def extract_oracle(result) -> OracleView:
    """从 CP-SAT OracleResult 提取中立视图（tick -> 精确小时 Fraction）。"""
    tasks: dict[tuple, TaskTiming] = {}
    for t in result.tasks:
        if not t.exists:
            continue
        key = (t.device_id, t.process, t.effective_attempt_no)
        outcome = t.outcome
        if t.status == "CANCELLED":
            outcome = "NONE"
        tasks[key] = TaskTiming(
            key=key, exists=True, status=t.status,
            release_h=ticks_to_hours(t.release_tick) if t.release_tick is not None else None,
            start_h=ticks_to_hours(t.start_tick) if t.start_tick is not None else None,
            finish_h=ticks_to_hours(t.finish_tick) if t.finish_tick is not None else None,
            outcome=outcome,
            resource=t.resource,
            bay_id=t.bay_id,
        )
    devices = {
        dv.device_id: DeviceTiming(
            device_id=dv.device_id, bay_id=dv.bay_id,
            terminal_state=dv.terminal_state,
            terminal_h=ticks_to_hours(dv.terminal_tick) if dv.terminal_tick is not None else None,
            d_created_h=ticks_to_hours(dv.d_created_tick) if dv.d_created_tick is not None else None,
        )
        for dv in result.devices
    }
    turnovers = sorted(
        (TurnoverPhase(tv.bay_id, tv.kind,
                       ticks_to_hours(tv.start_tick), ticks_to_hours(tv.finish_tick))
         for tv in result.turnovers),
        key=lambda p: (p.bay_id, p.start_h, p.kind),
    )
    return OracleView(fixture_id=result.fixture_id, tasks=tasks, devices=devices,
                      turnovers=turnovers, T_h=ticks_to_hours(result.makespan_tick))


def oracle_quality(result, fixture_record: dict) -> dict:
    """由 primitive real state + CP-SAT 终态独立给出 S/PL/PW（机械计数；
    与 test_cp_sat_oracle_v1.quality_summary 同口径）。"""
    real = fixture_record["scripted_real_states"]
    s = pl = pw = 0
    for dv in result.devices:
        states = real[str(dv.device_id)]
        generated = [states["A"], states["B"], states["C"]]
        if states.get("D", "not_created") != "not_created":
            generated.append(states["D"])
        if dv.terminal_state == "PASSED":
            s += 1
            if any(v == "problem" for v in generated):
                pl += 1
        else:
            if all(v == "normal" for v in generated):
                pw += 1
    return {"S": s, "PL": pl, "PW": pw}


def oracle_yxb(result, denominator_ticks: int = K9_YXB_DENOMINATOR_TICKS) -> dict:
    """K9 只读 YXB：每类资源已完成任务运行 tick 总和 / 108 ticks（18h）。"""
    total = {p: 0 for p in PROCESSES}
    for t in result.tasks:
        if t.exists and t.status == "COMPLETED":
            total[t.process] += t.duration_tick
    return {p: Fraction(total[p], denominator_ticks) for p in PROCESSES}


# ---------------------------------------------------------------------------
# 比较报告结构
# ---------------------------------------------------------------------------


@dataclass
class FieldDiff:
    """一个精确差异：位置 + 字段 + 三方值（hand 未冻结时为 None）。"""

    location: str
    field: str
    des: Any = None
    oracle: Any = None
    hand: Any = None
    note: str = ""

    def describe(self) -> str:
        return ("%s.%s: DES=%r ORACLE=%r HAND=%r%s" % (
            self.location, self.field, self.des, self.oracle, self.hand,
            (" [%s]" % self.note) if self.note else ""))


@dataclass
class TaskRow:
    """三方对齐矩阵的一行（des / oracle / hand 三列；None=无值或未冻结）。"""

    key: tuple
    exists: list
    release: list
    start: list
    finish: list
    outcome: list
    resource: list
    bay: list
    status: list
    match: bool


@dataclass
class FixtureComparisonReport:
    fixture_id: str
    des_T_h: Optional[Fraction]
    oracle_T_h: Optional[Fraction]
    hand_T_h: Optional[Fraction]
    des_T_tick: Optional[int]
    oracle_T_tick: Optional[int]
    hand_T_tick: Optional[int]
    rows: list = field(default_factory=list)
    device_rows: list = field(default_factory=list)
    turnover_rows: list = field(default_factory=list)
    metric_rows: list = field(default_factory=list)
    special_assertions: list = field(default_factory=list)
    diffs: list = field(default_factory=list)
    verdict: str = "FAIL"

    def summarize(self) -> str:
        return ("%s des_T=%s(%st) orc_T=%s(%st) hand_T=%s(%st) %s (%d diffs)" % (
            self.fixture_id,
            fmt_opt(self.des_T_h), self.des_T_tick,
            fmt_opt(self.oracle_T_h), self.oracle_T_tick,
            fmt_opt(self.hand_T_h), self.hand_T_tick,
            self.verdict, len(self.diffs)))


_MISSING = object()


def _check(diffs: list, location: str, field: str,
           dval: Any, oval: Any, hval: Any, note: str = "") -> bool:
    """精确比较三方值：DES==ORACLE 且（hand 冻结时）DES==HAND==ORACLE。"""
    ok = (dval == oval)
    if hval is not None:
        ok = ok and (dval == hval) and (oval == hval)
    if not ok:
        diffs.append(FieldDiff(location, field, dval, oval, hval, note=note))
    return ok


def _task_sort_key(key: tuple) -> tuple:
    return (key[0], PROCESS_ORDER[key[1]], key[2])


def compare_views(fid: str, des_view: DesView, orc_view: OracleView,
                  quality: Optional[dict] = None,
                  yxb: Optional[dict] = None) -> FixtureComparisonReport:
    """对三方（DES / CP-SAT / frozen hand）执行逐字段精确比较，产出报告。"""
    hand_tasks = HAND_TASK_EXPECTATIONS.get(fid, {})
    hand_devs = HAND_DEVICE_EXPECTATIONS.get(fid, {})
    hand_tvs = HAND_TURNOVER_EXPECTATIONS.get(fid, [])
    hand_T = EXPECTED_T_HOURS[fid]
    diffs: list[FieldDiff] = []
    rows: list[TaskRow] = []
    device_rows: list = []
    turnover_rows: list = []
    metric_rows: list = []
    special: list = []

    # ---- makespan / T ----------------------------------------------------
    des_T, orc_T = des_view.T_h, orc_view.T_h
    des_T_tick, orc_T_tick, hand_T_tick = (
        hours_to_ticks(des_T), hours_to_ticks(orc_T), hours_to_ticks(hand_T))
    if not (des_T == orc_T == hand_T):
        diffs.append(FieldDiff(
            "makespan", "T",
            "%s(%st)" % (fmt_hours(des_T), des_T_tick),
            "%s(%st)" % (fmt_hours(orc_T), orc_T_tick),
            "%s(%st)" % (fmt_hours(hand_T), hand_T_tick)))

    # ---- 任务级比较（按键排序 -> 内部排列差异归一） -----------------------
    keys = sorted(set(des_view.tasks) | set(orc_view.tasks) | set(hand_tasks),
                  key=_task_sort_key)
    for key in keys:
        d = des_view.tasks.get(key)
        o = orc_view.tasks.get(key)
        he = hand_tasks.get(key, {})
        d_ex = d.exists if d is not None else False
        o_ex = o.exists if o is not None else False
        h_ex = he.get("exists") if "exists" in he else None
        loc = "task(%d,%s,%d)" % key
        row_ok = True

        ok = _check(diffs, loc, "exists", d_ex, o_ex, h_ex)
        row_ok = row_ok and ok

        hand_rel = parse_hours(he["release"]) if "release" in he else None
        ok = _check(diffs, loc, "release",
                    d.release_h if d else None,
                    o.release_h if o else None,
                    hand_rel)
        row_ok = row_ok and ok

        hand_start = parse_hours(he["start"]) if "start" in he else None
        ok = _check(diffs, loc, "start",
                    d.start_h if d else None,
                    o.start_h if o else None,
                    hand_start)
        row_ok = row_ok and ok

        hand_fin = parse_hours(he["finish"]) if "finish" in he else None
        ok = _check(diffs, loc, "finish",
                    d.finish_h if d else None,
                    o.finish_h if o else None,
                    hand_fin)
        row_ok = row_ok and ok

        hand_out = he.get("outcome")
        ok = _check(diffs, loc, "outcome",
                    d.outcome if d else None,
                    o.outcome if o else None,
                    hand_out)
        row_ok = row_ok and ok

        ok = _check(diffs, loc, "resource",
                    d.resource if d else None,
                    o.resource if o else None,
                    None)
        row_ok = row_ok and ok

        hand_bay = he.get("bay")
        ok = _check(diffs, loc, "bay",
                    d.bay_id if d else None,
                    o.bay_id if o else None,
                    hand_bay)
        row_ok = row_ok and ok

        ok = _check(diffs, loc, "status",
                    d.status if d else None,
                    o.status if o else None,
                    None)
        row_ok = row_ok and ok

        rows.append(TaskRow(
            key=key,
            exists=[d_ex, o_ex, h_ex],
            release=[fmt_opt(d.release_h if d else None),
                     fmt_opt(o.release_h if o else None),
                     fmt_opt(hand_rel)],
            start=[fmt_opt(d.start_h if d else None),
                   fmt_opt(o.start_h if o else None),
                   fmt_opt(hand_start)],
            finish=[fmt_opt(d.finish_h if d else None),
                    fmt_opt(o.finish_h if o else None),
                    fmt_opt(hand_fin)],
            outcome=[d.outcome if d else None,
                     o.outcome if o else None,
                     hand_out],
            resource=[d.resource if d else None,
                      o.resource if o else None,
                      None],
            bay=[d.bay_id if d else None,
                 o.bay_id if o else None,
                 hand_bay],
            status=[d.status if d else None,
                    o.status if o else None,
                    None],
            match=row_ok,
        ))

    # ---- 装置级比较 -------------------------------------------------------
    for device_id in sorted(set(des_view.devices) | set(orc_view.devices) | set(hand_devs)):
        d = des_view.devices.get(device_id)
        o = orc_view.devices.get(device_id)
        he = hand_devs.get(device_id, {})
        loc = "device(%d)" % device_id
        row_ok = True

        h_term_state = he.get("terminal_state")
        ok = _check(diffs, loc, "terminal_state",
                    d.terminal_state if d else None,
                    o.terminal_state if o else None,
                    h_term_state)
        row_ok = row_ok and ok

        h_term = parse_hours(he["terminal"]) if "terminal" in he else None
        ok = _check(diffs, loc, "terminal_time",
                    d.terminal_h if d else None,
                    o.terminal_h if o else None,
                    h_term)
        row_ok = row_ok and ok

        d_dc = d.d_created_h if d else None
        o_dc = o.d_created_h if o else None
        if "d_created" in he:
            h_dc = parse_hours(he["d_created"]) if he["d_created"] is not None else None
        else:
            h_dc = _MISSING
        ok = (d_dc == o_dc)
        if h_dc is not _MISSING:
            ok = ok and (d_dc == h_dc) and (o_dc == h_dc)
        if not ok:
            diffs.append(FieldDiff(loc, "d_created", d_dc, o_dc,
                                   None if h_dc is _MISSING else h_dc))
        row_ok = row_ok and ok

        h_bay = he.get("bay")
        ok = _check(diffs, loc, "bay",
                    d.bay_id if d else None,
                    o.bay_id if o else None,
                    h_bay)
        row_ok = row_ok and ok

        device_rows.append({
            "device_id": device_id,
            "terminal_state": [d.terminal_state if d else None,
                               o.terminal_state if o else None,
                               h_term_state],
            "terminal": [fmt_opt(d.terminal_h if d else None),
                         fmt_opt(o.terminal_h if o else None),
                         fmt_opt(h_term)],
            "d_created": [fmt_opt(d_dc), fmt_opt(o_dc),
                          None if h_dc is _MISSING else fmt_opt(h_dc)],
            "bay": [d.bay_id if d else None, o.bay_id if o else None, h_bay],
            "match": row_ok,
        })

    # ---- 周转比较 ---------------------------------------------------------
    des_tv = sorted((p.bay_id, p.kind, p.start_h, p.finish_h) for p in des_view.turnovers)
    orc_tv = sorted((p.bay_id, p.kind, p.start_h, p.finish_h) for p in orc_view.turnovers)
    hand_tv = sorted((b, k, parse_hours(s), parse_hours(f)) for (b, k, s, f) in hand_tvs)
    ok = _check(diffs, "turnover", "phases",
                [(b, k, fmt_hours(s), fmt_hours(f)) for (b, k, s, f) in des_tv],
                [(b, k, fmt_hours(s), fmt_hours(f)) for (b, k, s, f) in orc_tv],
                [(b, k, fmt_hours(s), fmt_hours(f)) for (b, k, s, f) in hand_tv] if hand_tvs else None)
    # 对齐矩阵行：union of (bay, kind)
    tv_keys = sorted(set((p[0], p[1]) for p in des_tv) | set((p[0], p[1]) for p in orc_tv)
                     | set((p[0], p[1]) for p in hand_tv))
    for (bay_id, kind) in tv_keys:
        d_p = next((p for p in des_tv if p[0] == bay_id and p[1] == kind), None)
        o_p = next((p for p in orc_tv if p[0] == bay_id and p[1] == kind), None)
        h_p = next((p for p in hand_tv if p[0] == bay_id and p[1] == kind), None)
        def _iv(p):
            return None if p is None else "%s..%s" % (fmt_hours(p[2]), fmt_hours(p[3]))
        turnover_rows.append({
            "bay_id": bay_id, "kind": kind,
            "interval": [_iv(d_p), _iv(o_p), _iv(h_p)],
            "match": (d_p == o_p) and (h_p is None or h_p == d_p),
        })

    # ---- 质量指标 S/PL/PW（hand 冻结时） -----------------------------------
    if quality is not None and quality.get("hand") is not None:
        hand_m = quality["hand"]
        for m in ("S", "PL", "PW"):
            dval = (des_view.metrics or {}).get(m)
            oval = (quality.get("oracle") or {}).get(m)
            hval = hand_m.get(m)
            ok = _check(diffs, "metrics", m, dval, oval, hval)
            metric_rows.append({"metric": m, "des": dval, "oracle": oval, "hand": hval,
                                "match": ok})

    # ---- K9 YXB 只读断言（仅 F8 冻结） --------------------------------------
    if yxb is not None:
        for p in PROCESSES:
            dval = (yxb.get("des") or {}).get(p)
            oval = (yxb.get("oracle") or {}).get(p)
            hval = (yxb.get("hand") or {}).get(p)
            ok = _check(diffs, "yxb", p, dval, oval, hval)
            metric_rows.append({"metric": "YXB_%s" % p,
                                "des": fmt_opt(dval), "oracle": fmt_opt(oval),
                                "hand": fmt_opt(hval), "match": ok})

    # ---- K9/F8 专项命名断言 -------------------------------------------------
    if fid == "F8":
        def k9_ticks(key: tuple, field: str) -> list:
            d = des_view.tasks.get(key)
            o = orc_view.tasks.get(key)
            he = hand_tasks.get(key, {})
            dv = getattr(d, field, None) if d else None
            ov = getattr(o, field, None) if o else None
            # hand 表字段名与 TaskTiming 属性名不同（finish_h <-> finish 等）
            hand_field = {"finish_h": "finish", "start_h": "start", "release_h": "release"}[field]
            hv = parse_hours(he[hand_field]) if hand_field in he else None
            return [fmt_ticks(dv), fmt_ticks(ov), fmt_ticks(hv)]

        b1_out = ((des_view.tasks.get((3, "B", 1)).outcome if (3, "B", 1) in des_view.tasks else None)
                  == "ABNORMAL"
                  and (orc_view.tasks.get((3, "B", 1)).outcome if (3, "B", 1) in orc_view.tasks else None)
                  == "ABNORMAL")
        checks = [
            ("K9_T_84", [des_T_tick, orc_T_tick, hand_T_tick] == [84, 84, 84],
             "T = 84 ticks = 14 h"),
            ("K9_d3_B1_finish_51_ABNORMAL",
             k9_ticks((3, "B", 1), "finish_h") == [51, 51, 51] and b1_out,
             "d3 B1 finish = 51 ticks (8.5h) ABNORMAL"),
            ("K9_d3_B2_release_51", k9_ticks((3, "B", 2), "release_h") == [51, 51, 51],
             "d3 B2 release = 51 ticks (8.5h), never rewritten"),
            ("K9_d3_B2_start_54", k9_ticks((3, "B", 2), "start_h") == [54, 54, 54],
             "d3 B2 start = 54 ticks (9h), shift 2"),
            ("K9_d3_B2_finish_66", k9_ticks((3, "B", 2), "finish_h") == [66, 66, 66],
             "d3 B2 finish = 66 ticks (11h) PASS"),
            ("K9_d3_B2_attempt_2",
             (3, "B", 2)[2] == 2
             and all((3, "B", 2) in k for k in (des_view.tasks, orc_view.tasks, hand_tasks)),
             "d3 B2 effective_attempt_no = 2"),
            ("K9_d3_E_start_66", k9_ticks((3, "E", 1), "start_h") == [66, 66, 66],
             "d3 E start = 66 ticks (11h)"),
            ("K9_d3_E_finish_84", k9_ticks((3, "E", 1), "finish_h") == [84, 84, 84],
             "d3 E finish = 84 ticks (14h)"),
        ]
        for name, ok, detail in checks:
            special.append({"name": name, "ok": ok, "detail": detail})
            if not ok:
                diffs.append(FieldDiff("K9", name, None, None, None, note=detail))

    return FixtureComparisonReport(
        fixture_id=fid,
        des_T_h=des_T, oracle_T_h=orc_T, hand_T_h=hand_T,
        des_T_tick=des_T_tick, oracle_T_tick=orc_T_tick, hand_T_tick=hand_T_tick,
        rows=rows, device_rows=device_rows, turnover_rows=turnover_rows,
        metric_rows=metric_rows, special_assertions=special,
        diffs=diffs, verdict="PASS" if not diffs else "FAIL",
    )


# ---------------------------------------------------------------------------
# 运行入口（延迟导入 DES / CP-SAT，本模块顶层保持 stdlib-only）
# ---------------------------------------------------------------------------

_FIXTURES_DEFAULT = Path(__file__).resolve().parent / "fixtures" / "des_fixtures_F1_F12_v1.json"


def _load_des():
    import sys
    here = Path(__file__).resolve().parent          # 04_代码/tests
    code_dir = here.parent                          # 04_代码
    main_model = code_dir / "main_model"
    for _entry in (str(main_model), str(code_dir), str(here)):
        if _entry not in sys.path:
            sys.path.insert(0, _entry)
    from des import deterministic_des_v1 as de  # noqa: E402
    return de


def _load_oracle():
    import sys
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    import cp_sat_oracle_v1 as oracle  # noqa: E402
    return oracle


def run_des_fixture(fixture_record: dict):
    """运行 accepted DES 一次（stdlib）。"""
    de = _load_des()
    return de.run_des(fixture_record["config"], fixture_record)


def run_oracle_fixture(fixture_record: dict):
    """运行独立 CP-SAT oracle 一次（含 OR-Tools 版本守卫）。"""
    oracle = _load_oracle()
    return oracle.solve_fixture(fixture_record)


def crosscheck_fixture(fixture_record: dict, des_result, oracle_result) -> FixtureComparisonReport:
    """对单个 fixture 做三方对拍（DES / CP-SAT / frozen hand）。"""
    fid = fixture_record["fixture_id"]
    profile = fixture_record["config"]["turnover_profile"]
    des_view = extract_des(des_result.event_log, des_result.metrics, profile)
    orc_view = extract_oracle(oracle_result)
    quality = {
        "des": {k: des_result.metrics[k] for k in ("S", "PL", "PW")},
        "oracle": oracle_quality(oracle_result, fixture_record),
        "hand": HAND_METRICS.get(fid),
    }
    yxb = None
    if fid == "F8":
        yxb = {
            "des": {p: Fraction(des_result.metrics["YXB_" + p]) for p in PROCESSES},
            "oracle": oracle_yxb(oracle_result),
            "hand": HAND_YXB,
        }
    return compare_views(fid, des_view, orc_view, quality=quality, yxb=yxb)


def load_fixtures(path=None) -> dict:
    path = Path(path) if path else _FIXTURES_DEFAULT
    data = json.loads(path.read_text(encoding="utf-8"))
    return {f["fixture_id"]: f for f in data["fixtures"]}


def crosscheck_all(fixtures: Optional[dict] = None) -> dict:
    """对全部 14 个 concrete fixture 依次运行 DES + CP-SAT 并三方对拍。"""
    fixtures = fixtures if fixtures is not None else load_fixtures()
    reports: dict[str, FixtureComparisonReport] = {}
    for fid in FIXTURES_ORDER:
        fixture = fixtures[fid]
        reports[fid] = crosscheck_fixture(
            fixture, run_des_fixture(fixture), run_oracle_fixture(fixture))
    return reports


def report_to_dict(report: FixtureComparisonReport) -> dict:
    """把报告序列化为 JSON 安全的确定性 dict（Fraction -> 分数字符串）。"""
    def _v(x):
        if isinstance(x, Fraction):
            return fmt_hours(x)
        if isinstance(x, tuple):
            return [ _v(i) for i in x ]
        if isinstance(x, list):
            return [ _v(i) for i in x ]
        return x

    return {
        "fixture_id": report.fixture_id,
        "des_T_h": fmt_opt(report.des_T_h),
        "oracle_T_h": fmt_opt(report.oracle_T_h),
        "hand_T_h": fmt_opt(report.hand_T_h),
        "des_T_tick": report.des_T_tick,
        "oracle_T_tick": report.oracle_T_tick,
        "hand_T_tick": report.hand_T_tick,
        "rows": [{
            "key": list(r.key),
            "exists": r.exists, "release": r.release, "start": r.start,
            "finish": r.finish, "outcome": r.outcome, "resource": r.resource,
            "bay": r.bay, "status": r.status, "match": r.match,
        } for r in report.rows],
        "device_rows": [_v(r) for r in report.device_rows],
        "turnover_rows": [_v(r) for r in report.turnover_rows],
        "metric_rows": [_v(r) for r in report.metric_rows],
        "special_assertions": [_v(r) for r in report.special_assertions],
        "diffs": [[d.location, d.field, _v(d.des), _v(d.oracle), _v(d.hand), d.note]
                  for d in report.diffs],
        "verdict": report.verdict,
    }


def format_summary(reports: dict) -> str:
    lines = ["%s %-28s %s" % ("fixture", "T (des/orc/hand, ticks)", "verdict")]
    for fid in FIXTURES_ORDER:
        r = reports[fid]
        lines.append("%-6s %s" % (fid, r.summarize()))
    total = len(reports)
    passed = sum(1 for r in reports.values() if r.verdict == "PASS")
    lines.append("PASS %d/%d" % (passed, total))
    return "\n".join(lines)


if __name__ == "__main__":
    _reports = crosscheck_all()
    print(format_summary(_reports))
    for _fid in FIXTURES_ORDER:
        _r = _reports[_fid]
        if _r.verdict != "PASS":
            print("---- %s FAIL" % _fid)
            for _d in _r.diffs:
                print("  ", _d.describe())
