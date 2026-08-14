# -*- coding: utf-8 -*-
"""G2-03 S2 独立 CP-SAT oracle 测试（test_cp_sat_oracle_v1.py）

覆盖范围（22 项）：
 1  OR-Tools 精确版本守卫
 2  10 分钟 tick 转换
 3  无 float canonical 时间
 4  全部 14 个 concrete fixture 可解（F1-F12 + F4b/F9b）
 5  确定性重复求解逐字段一致
 6  F1 A/B/C 并行
 7  F2 资源容量 + FCFS
 8  F3 B 重测与 A/C 重叠
 9  F4 t*=7.5 同刻（d1 A2 二次异常 + d2 C2 PASS）
10  F4b 终端取消 / 任务存在性
11  F5 提前退出后无 E/D 下游任务
12  F6 班末禁启
13  F7 恰好班末结束允许
14  F8 K9：T=14(84 ticks)、B 重测 release=51/start=54/finish=66、E=66..84
15  F9 1h 周转
16  F9b 并发 bay 运输（SEM-23）
17  F10 0.5h 重叠周转
18  F11 下一班调度 / 活性等价
19  F12 末台终态 makespan、无必要末台周转
20  无 DES import
21  无 DES 派生输入
22  单 worker 确定性 solver

独立性：本测试不 import 主 DES 的确定性实现、显式状态模型或其测试文件；
直接 fixture primitive input -> CP-SAT oracle -> 冻结 fixture/hand acceptance。
"""

import copy
import json
import pathlib
import sys
import unittest
from fractions import Fraction

import ortools

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import cp_sat_oracle_v1 as oracle  # noqa: E402

FIXTURES_FILE = _HERE / "fixtures" / "des_fixtures_F1_F12_v1.json"
_FIXTURE_DATA = json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))
FIXTURES = {f["fixture_id"]: f for f in _FIXTURE_DATA["fixtures"]}
CONCRETE_CASES = ["F1", "F2", "F3", "F4", "F4b", "F5", "F6", "F7", "F8", "F9", "F9b", "F10", "F11", "F12"]


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

def find_task(result, device, process, attempt):
    for t in result.tasks:
        if t.device_id == device and t.process == process and t.effective_attempt_no == attempt:
            return t
    raise AssertionError("task not found: device=%s process=%s attempt=%s" % (device, process, attempt))


def find_turnover(result, bay, kind):
    for tv in result.turnovers:
        if tv.bay_id == bay and tv.kind == kind:
            return tv
    raise AssertionError("turnover not found: bay=%s kind=%s" % (bay, kind))


def find_device(result, device_id):
    for dv in result.devices:
        if dv.device_id == device_id:
            return dv
    raise AssertionError("device not found: %s" % device_id)


def quality_summary(result, fixture):
    """由 primitive real state + CP-SAT 终态独立给出 S/PL/PW 计数（fixture 断言用）。

    属最小终端状态计数，不是 G2-04 的完整指标日志复算。"""
    real = fixture["scripted_real_states"]
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


def process_runtime_ticks(result, process):
    """已完成任务的运行片段总时长（ticks），供 K9 YXB 只读断言。"""
    total = 0
    for t in result.tasks:
        if t.exists and t.status == "COMPLETED" and t.process == process:
            total += t.duration_tick
    return total


# ---------------------------------------------------------------------------
# 1. OR-Tools 精确版本守卫
# ---------------------------------------------------------------------------

class TestVersionGuard(unittest.TestCase):
    def test_pinned_version_present(self):
        self.assertEqual(ortools.__version__, "9.15.6755")
        self.assertEqual(oracle.ORTOOLS_PINNED_VERSION, "9.15.6755")
        self.assertEqual(oracle.require_ortools_version(), "9.15.6755")

    def test_mismatch_raises(self):
        old = ortools.__version__
        try:
            ortools.__version__ = "9.0.0"
            with self.assertRaises(oracle.ORTOOLS_VERSION_MISMATCH):
                oracle.require_ortools_version()
        finally:
            ortools.__version__ = old

    def test_cp_model_import_ok(self):
        from ortools.sat.python import cp_model
        self.assertTrue(hasattr(cp_model, "CpModel"))


# ---------------------------------------------------------------------------
# 2. 10 分钟 tick 转换
# ---------------------------------------------------------------------------

class TestTickConversion(unittest.TestCase):
    def test_exact_ticks(self):
        self.assertEqual(oracle.hours_to_ticks("2.5"), 15)
        self.assertEqual(oracle.hours_to_ticks("2"), 12)
        self.assertEqual(oracle.hours_to_ticks("2.5"), 15)
        self.assertEqual(oracle.hours_to_ticks("3"), 18)
        self.assertEqual(oracle.hours_to_ticks("0.5"), 3)
        self.assertEqual(oracle.hours_to_ticks("9"), 54)
        self.assertEqual(oracle.hours_to_ticks("1000000"), 6000000)
        self.assertEqual(oracle.hours_to_ticks(Fraction(11, 2)), 33)

    def test_non_integer_tick_fails(self):
        for bad in ("2.7", "0.1", "1/60"):
            with self.assertRaises(oracle.NON_INTEGER_CP_SAT_TICK):
                oracle.hours_to_ticks(bad)

    def test_float_input_rejected(self):
        with self.assertRaises(oracle.NON_INTEGER_CP_SAT_TICK):
            oracle.hours_to_ticks(2.5)

    def test_roundtrip_exact(self):
        self.assertEqual(oracle.ticks_to_hours(33), Fraction(11, 2))
        self.assertEqual(oracle.ticks_to_hours(84), Fraction(14, 1))
        self.assertEqual(oracle.tick_to_hour_str(51), "8.5")
        self.assertEqual(oracle.tick_to_hour_str(84), "14")


# ---------------------------------------------------------------------------
# 3. 无 float canonical 时间
# ---------------------------------------------------------------------------

class TestNoFloatCanonicalTime(unittest.TestCase):
    def test_result_times_are_int_or_fraction(self):
        r = oracle.solve_fixture(FIXTURES["F8"])
        self.assertIsInstance(r.makespan_tick, int)
        self.assertEqual(r.makespan_hours(), Fraction(14, 1))
        self.assertIsInstance(r.makespan_hours_str(), str)
        for t in r.tasks:
            for fld in ("release_tick", "start_tick", "finish_tick", "scheduled_finish_tick", "duration_tick"):
                v = getattr(t, fld)
                if v is not None:
                    self.assertIsInstance(v, int)
        for tv in r.turnovers:
            self.assertIsInstance(tv.start_tick, int)
            self.assertIsInstance(tv.finish_tick, int)
        for dv in r.devices:
            self.assertIsInstance(dv.entry_tick, int)
            self.assertIsInstance(dv.terminal_tick, int)

    def test_source_has_no_float_arith(self):
        src = pathlib.Path(oracle.__file__).read_text(encoding="utf-8")
        for token in ("float(", "round(", "int(float", "math.", "epsilon"):
            self.assertNotIn(token, src)


# ---------------------------------------------------------------------------
# 4. 全部 14 个 concrete fixture 求解
# ---------------------------------------------------------------------------

class TestAllFixturesSolve(unittest.TestCase):
    def test_all_concrete_cases_optimal_and_T(self):
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                r = oracle.solve_fixture(FIXTURES[fid])
                self.assertEqual(r.status, "OPTIMAL", fid)
                self.assertEqual(r.fixture_id, fid)
                acc_t = Fraction(FIXTURES[fid]["acceptance"]["T"])
                self.assertEqual(r.makespan_tick, int(acc_t * oracle.TICKS_PER_HOUR), fid)
                self.assertEqual(r.makespan_hours(), acc_t, fid)

    def test_quality_summary_matches_acceptance(self):
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                r = oracle.solve_fixture(FIXTURES[fid])
                q = quality_summary(r, FIXTURES[fid])
                acc = FIXTURES[fid]["acceptance"]
                self.assertEqual(q["S"], acc["S"], fid)
                self.assertEqual(q["PL"], acc["PL"], fid)
                self.assertEqual(q["PW"], acc["PW"], fid)


# ---------------------------------------------------------------------------
# 5. 确定性重复求解
# ---------------------------------------------------------------------------

class TestDeterministicSolve(unittest.TestCase):
    def test_repeated_solve_field_identical(self):
        for fid in ("F4b", "F8", "F9b"):
            with self.subTest(fid=fid):
                r1 = oracle.solve_fixture(FIXTURES[fid])
                r2 = oracle.solve_fixture(FIXTURES[fid])
                self.assertEqual(r1.to_dict(), r2.to_dict())


# ---------------------------------------------------------------------------
# 6. F1 A/B/C 并行
# ---------------------------------------------------------------------------

class TestF1Parallel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F1"])

    def test_abc_start_at_zero(self):
        for p in ("A", "B", "C"):
            t = find_task(self.r, 1, p, 1)
            self.assertTrue(t.exists)
            self.assertEqual(t.start_tick, 0)

    def test_b_finishes_before_ac(self):
        self.assertEqual(find_task(self.r, 1, "B", 1).finish_tick, 12)
        self.assertEqual(find_task(self.r, 1, "A", 1).finish_tick, 15)
        self.assertEqual(find_task(self.r, 1, "C", 1).finish_tick, 15)

    def test_e_after_abc(self):
        e = find_task(self.r, 1, "E", 1)
        self.assertEqual(e.release_tick, 15)
        self.assertEqual(e.start_tick, 15)
        self.assertEqual(e.finish_tick, 33)
        self.assertEqual(e.status, "COMPLETED")
        self.assertEqual(e.outcome, "PASS")

    def test_no_turnover_and_makespan(self):
        self.assertEqual(self.r.turnovers, [])
        self.assertEqual(self.r.makespan_tick, 33)
        self.assertEqual(find_device(self.r, 1).terminal_state, "PASSED")


# ---------------------------------------------------------------------------
# 7. F2 资源容量 + FCFS
# ---------------------------------------------------------------------------

class TestF2ResourceFCFS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F2"])

    def test_capacity_one_serializes(self):
        # 同资源上 device1 先派（release 同刻 0 -> device_id 小者先）
        self.assertEqual(find_task(self.r, 1, "A", 1).start_tick, 0)
        self.assertEqual(find_task(self.r, 2, "A", 1).start_tick, 15)
        self.assertEqual(find_task(self.r, 1, "B", 1).start_tick, 0)
        self.assertEqual(find_task(self.r, 2, "B", 1).start_tick, 12)
        self.assertEqual(find_task(self.r, 1, "C", 1).start_tick, 0)
        self.assertEqual(find_task(self.r, 2, "C", 1).start_tick, 15)

    def test_no_self_overlap_same_process(self):
        for p in ("A", "B", "C"):
            t1 = find_task(self.r, 1, p, 1)
            t2 = find_task(self.r, 2, p, 1)
            self.assertLessEqual(t1.finish_tick, t2.start_tick)

    def test_device2_e_after_device1_e(self):
        e1 = find_task(self.r, 1, "E", 1)
        e2 = find_task(self.r, 2, "E", 1)
        self.assertEqual(e1.start_tick, 15)
        self.assertEqual(e1.finish_tick, 33)
        self.assertEqual(e2.release_tick, 30)
        self.assertEqual(e2.start_tick, 33)
        self.assertEqual(e2.finish_tick, 51)

    def test_makespan(self):
        self.assertEqual(self.r.makespan_tick, 51)  # 8.5 h


# ---------------------------------------------------------------------------
# 8. F3 B 重测与 A/C 重叠
# ---------------------------------------------------------------------------

class TestF3RetestOverlaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F3"])

    def test_b_first_abnormal_no_cancel(self):
        b1 = find_task(self.r, 1, "B", 1)
        self.assertEqual(b1.outcome, "ABNORMAL")
        self.assertEqual(b1.finish_tick, 12)
        a1 = find_task(self.r, 1, "A", 1)
        c1 = find_task(self.r, 1, "C", 1)
        self.assertEqual(a1.status, "COMPLETED")
        self.assertEqual(c1.status, "COMPLETED")
        self.assertEqual(a1.finish_tick, 15)
        self.assertEqual(c1.finish_tick, 15)

    def test_retest_release_and_overlap(self):
        b2 = find_task(self.r, 1, "B", 2)
        self.assertTrue(b2.exists)
        self.assertEqual(b2.effective_attempt_no, 2)
        self.assertEqual(b2.release_tick, 12)   # 首败完成时刻
        self.assertEqual(b2.start_tick, 12)
        self.assertEqual(b2.finish_tick, 24)
        self.assertEqual(b2.outcome, "PASS")
        # [12,24) 与 A/C [0,15) 在 [12,15) 真实重叠（不同资源）
        self.assertLess(b2.start_tick, find_task(self.r, 1, "A", 1).finish_tick)
        self.assertLess(b2.start_tick, find_task(self.r, 1, "C", 1).finish_tick)

    def test_e_release_and_makespan(self):
        e = find_task(self.r, 1, "E", 1)
        self.assertEqual(e.release_tick, 24)
        self.assertEqual(e.start_tick, 24)
        self.assertEqual(e.finish_tick, 42)
        self.assertEqual(self.r.makespan_tick, 42)  # 7 h


# ---------------------------------------------------------------------------
# 9. F4 t*=7.5 同刻（先结算后退出）
# ---------------------------------------------------------------------------

class TestF4SameTickSettleThenExit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F4"])

    def test_simultaneous_completion_at_7_5(self):
        self.assertEqual(find_task(self.r, 1, "A", 2).finish_tick, 45)   # 7.5h 二次异常
        self.assertEqual(find_task(self.r, 2, "C", 2).finish_tick, 45)   # 7.5h PASS
        self.assertEqual(find_task(self.r, 1, "A", 2).outcome, "ABNORMAL")
        self.assertEqual(find_task(self.r, 2, "C", 2).outcome, "PASS")

    def test_device1_exited_device2_passed(self):
        self.assertEqual(find_device(self.r, 1).terminal_state, "EXITED")
        self.assertEqual(find_device(self.r, 1).terminal_tick, 45)
        self.assertEqual(find_device(self.r, 2).terminal_state, "PASSED")
        self.assertEqual(find_device(self.r, 2).terminal_tick, 63)

    def test_no_e_for_exited_device(self):
        self.assertFalse(find_task(self.r, 1, "E", 1).exists)
        self.assertIsNone(find_device(self.r, 1).d_created_tick)

    def test_device2_e_and_makespan(self):
        e2 = find_task(self.r, 2, "E", 1)
        self.assertEqual(e2.release_tick, 45)
        self.assertEqual(e2.start_tick, 45)
        self.assertEqual(e2.finish_tick, 63)
        self.assertEqual(self.r.makespan_tick, 63)  # 10.5 h


# ---------------------------------------------------------------------------
# 10. F4b 终端取消 / 任务存在性
# ---------------------------------------------------------------------------

class TestF4bTerminalCancellation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F4b"])

    def test_exit_via_b2_second_abnormal(self):
        b2 = find_task(self.r, 1, "B", 2)
        self.assertEqual(b2.outcome, "ABNORMAL")
        self.assertEqual(b2.finish_tick, 36)   # 6h
        self.assertEqual(find_device(self.r, 1).terminal_state, "EXITED")
        self.assertEqual(find_device(self.r, 1).terminal_tick, 36)
        self.assertEqual(find_device(self.r, 1).exit_process, "B")

    def test_cancelled_retests(self):
        for p in ("A", "C"):
            t = find_task(self.r, 1, p, 2)
            self.assertTrue(t.exists)
            self.assertEqual(t.status, "CANCELLED")
            self.assertIsNone(t.outcome)
            self.assertEqual(t.release_tick, 15)
            self.assertEqual(t.start_tick, 30)
            self.assertEqual(t.finish_tick, 36)          # 取消 = 退出时刻
            self.assertEqual(t.scheduled_finish_tick, 45)  # 计划 7.5h 被截断

    def test_no_e_for_exited_device(self):
        self.assertFalse(find_task(self.r, 1, "E", 1).exists)
        self.assertIsNone(find_device(self.r, 1).d_created_tick)

    def test_device2_e_and_makespan(self):
        e2 = find_task(self.r, 2, "E", 1)
        self.assertEqual(e2.release_tick, 30)
        self.assertEqual(e2.start_tick, 30)
        self.assertEqual(e2.finish_tick, 48)
        self.assertEqual(self.r.makespan_tick, 48)  # 8 h


# ---------------------------------------------------------------------------
# 11. F5 提前退出后无 E/D 下游任务
# ---------------------------------------------------------------------------

class TestF5NoDownstreamAfterExit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F5"])

    def test_exit_at_5h(self):
        a2 = find_task(self.r, 1, "A", 2)
        self.assertEqual(a2.outcome, "ABNORMAL")
        self.assertEqual(a2.finish_tick, 30)
        self.assertEqual(find_device(self.r, 1).terminal_state, "EXITED")
        self.assertEqual(find_device(self.r, 1).terminal_tick, 30)
        self.assertEqual(find_device(self.r, 1).exit_process, "A")

    def test_no_e_and_no_d(self):
        self.assertFalse(find_task(self.r, 1, "E", 1).exists)
        self.assertFalse(find_task(self.r, 1, "E", 2).exists)
        self.assertIsNone(find_device(self.r, 1).d_created_tick)

    def test_bc_completed(self):
        self.assertEqual(find_task(self.r, 1, "B", 1).status, "COMPLETED")
        self.assertEqual(find_task(self.r, 1, "C", 1).status, "COMPLETED")

    def test_makespan(self):
        self.assertEqual(self.r.makespan_tick, 30)  # 5 h


# ---------------------------------------------------------------------------
# 12. F6 班末禁启
# ---------------------------------------------------------------------------

class TestF6ShiftEndBan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F6"])

    def test_e_retest_not_started_in_shift1(self):
        e2 = find_task(self.r, 1, "E", 2)
        self.assertTrue(e2.exists)
        self.assertEqual(e2.release_tick, 48)   # 8h
        self.assertEqual(e2.start_tick, 54)     # 9h（班1 余 1h < 3h 禁启 -> 班2 起点）
        self.assertEqual(e2.finish_tick, 72)
        self.assertEqual(e2.outcome, "PASS")

    def test_e1_abnormal_at_8h(self):
        e1 = find_task(self.r, 1, "E", 1)
        self.assertEqual(e1.outcome, "ABNORMAL")
        self.assertEqual(e1.finish_tick, 48)

    def test_d_created_once_at_e_release(self):
        self.assertEqual(find_device(self.r, 1).d_created_tick, 30)  # 5h

    def test_makespan(self):
        self.assertEqual(self.r.makespan_tick, 72)  # 12 h


# ---------------------------------------------------------------------------
# 13. F7 恰好班末结束允许
# ---------------------------------------------------------------------------

class TestF7ExactShiftEndAllowed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F7"])

    def test_device3_ac_finish_exactly_at_shift_end(self):
        a1 = find_task(self.r, 3, "A", 1)
        c1 = find_task(self.r, 3, "C", 1)
        self.assertEqual(a1.start_tick, 39)
        self.assertEqual(a1.finish_tick, 54)   # 9.0h == shift_end（合法）
        self.assertEqual(c1.finish_tick, 54)
        self.assertEqual(a1.status, "COMPLETED")

    def test_device3_entry_and_turnover(self):
        self.assertEqual(find_device(self.r, 3).entry_tick, 39)
        tv_out = find_turnover(self.r, 1, "OUT")
        tv_in = find_turnover(self.r, 1, "IN")
        self.assertEqual((tv_out.start_tick, tv_out.finish_tick), (33, 36))
        self.assertEqual((tv_in.start_tick, tv_in.finish_tick), (36, 39))

    def test_device3_e_in_shift2(self):
        e = find_task(self.r, 3, "E", 1)
        self.assertEqual(e.release_tick, 54)
        self.assertEqual(e.start_tick, 54)
        self.assertEqual(e.finish_tick, 72)

    def test_makespan(self):
        self.assertEqual(self.r.makespan_tick, 72)  # 12 h


# ---------------------------------------------------------------------------
# 14. F8 K9 权威手算
# ---------------------------------------------------------------------------

class TestF8K9(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F8"])

    def test_makespan_84_ticks_14h(self):
        self.assertEqual(self.r.makespan_tick, 84)
        self.assertEqual(self.r.makespan_hours(), Fraction(14, 1))

    def test_device3_b_retest_release_never_rewritten(self):
        b2 = find_task(self.r, 3, "B", 2)
        self.assertTrue(b2.exists)
        self.assertEqual(b2.effective_attempt_no, 2)
        self.assertEqual(b2.release_tick, 51)   # 8.5h 恒为 51，不得改写为 54
        self.assertEqual(b2.start_tick, 54)     # 9h（班1 余 0.5h < 2h 禁启）
        self.assertEqual(b2.finish_tick, 66)    # 11h
        self.assertEqual(b2.outcome, "PASS")
        self.assertEqual(b2.status, "COMPLETED")

    def test_device3_e_66_84(self):
        e = find_task(self.r, 3, "E", 1)
        self.assertEqual(e.release_tick, 66)
        self.assertEqual(e.start_tick, 66)
        self.assertEqual(e.finish_tick, 84)

    def test_device3_ac_complete_at_9h_before_shift_change(self):
        a1 = find_task(self.r, 3, "A", 1)
        c1 = find_task(self.r, 3, "C", 1)
        self.assertEqual(a1.finish_tick, 54)
        self.assertEqual(c1.finish_tick, 54)
        self.assertEqual(a1.status, "COMPLETED")
        self.assertEqual(c1.status, "COMPLETED")

    def test_devices_terminal_times(self):
        self.assertEqual(find_device(self.r, 1).terminal_tick, 33)
        self.assertEqual(find_device(self.r, 2).terminal_tick, 51)
        self.assertEqual(find_device(self.r, 3).terminal_tick, 84)
        for d in (1, 2, 3):
            self.assertEqual(find_device(self.r, d).terminal_state, "PASSED")

    def test_bay2_no_turnover_last_occupant(self):
        self.assertFalse(any(tv.bay_id == 2 for tv in self.r.turnovers))
        self.assertEqual(find_device(self.r, 3).bay_id, 1)

    def test_yxb_readonly_hand_assertions(self):
        denom = 108  # 2 shifts x 9h = 18h = 108 ticks
        self.assertEqual(Fraction(process_runtime_ticks(self.r, "A"), denom), Fraction(5, 12))   # 7.5/18
        self.assertEqual(Fraction(process_runtime_ticks(self.r, "B"), denom), Fraction(4, 9))    # 8/18
        self.assertEqual(Fraction(process_runtime_ticks(self.r, "C"), denom), Fraction(5, 12))   # 7.5/18
        self.assertEqual(Fraction(process_runtime_ticks(self.r, "E"), denom), Fraction(1, 2))    # 9/18


# ---------------------------------------------------------------------------
# 15. F9 1h 周转
# ---------------------------------------------------------------------------

class TestF9Turnover1h(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F9"])

    def test_turnover_phases(self):
        tv_out = find_turnover(self.r, 1, "OUT")
        tv_in = find_turnover(self.r, 1, "IN")
        self.assertEqual((tv_out.start_tick, tv_out.finish_tick), (33, 36))   # 5.5..6.0
        self.assertEqual((tv_in.start_tick, tv_in.finish_tick), (36, 39))     # 6.0..6.5
        self.assertEqual(tv_out.profile, "1h_literal")

    def test_device3_entry_and_tasks(self):
        self.assertEqual(find_device(self.r, 3).entry_tick, 39)
        self.assertEqual(find_task(self.r, 3, "A", 1).finish_tick, 54)
        self.assertEqual(find_task(self.r, 3, "B", 1).finish_tick, 51)
        e = find_task(self.r, 3, "E", 1)
        self.assertEqual(e.start_tick, 54)
        self.assertEqual(e.finish_tick, 72)

    def test_makespan(self):
        self.assertEqual(self.r.makespan_tick, 72)  # 12 h


# ---------------------------------------------------------------------------
# 16. F9b 并发 bay 运输（SEM-23）
# ---------------------------------------------------------------------------

class TestF9bConcurrentTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F9b"])

    def test_bay1_in_overlaps_bay2_out(self):
        bay1_in = find_turnover(self.r, 1, "IN")
        bay2_out = find_turnover(self.r, 2, "OUT")
        self.assertEqual((bay1_in.start_tick, bay1_in.finish_tick), (36, 39))
        self.assertEqual((bay2_out.start_tick, bay2_out.finish_tick), (36, 39))
        # [6.0,6.5) bay1 IN 与 bay2 OUT 同时存在（无全局运输容量）
        self.assertLess(bay1_in.start_tick, bay2_out.finish_tick)
        self.assertLess(bay2_out.start_tick, bay1_in.finish_tick)

    def test_device2_exit_triggers_bay2_turnover(self):
        self.assertEqual(find_device(self.r, 2).terminal_state, "EXITED")
        self.assertEqual(find_device(self.r, 2).terminal_tick, 36)
        tv_out = find_turnover(self.r, 2, "OUT")
        tv_in = find_turnover(self.r, 2, "IN")
        self.assertEqual((tv_out.start_tick, tv_out.finish_tick), (36, 39))
        self.assertEqual((tv_in.start_tick, tv_in.finish_tick), (39, 42))

    def test_device4_entry_and_e(self):
        self.assertEqual(find_device(self.r, 4).entry_tick, 42)
        e4 = find_task(self.r, 4, "E", 1)
        self.assertEqual(e4.start_tick, 72)
        self.assertEqual(e4.finish_tick, 90)

    def test_makespan_15h(self):
        self.assertEqual(self.r.makespan_tick, 90)  # T=15（机械确认，非手改）
        self.assertEqual(self.r.makespan_hours(), Fraction(15, 1))


# ---------------------------------------------------------------------------
# 17. F10 0.5h 重叠周转
# ---------------------------------------------------------------------------

class TestF10OverlapTurnover(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F10"])

    def test_overlap_turnover_0_5h(self):
        tv = find_turnover(self.r, 1, "OVERLAP")
        self.assertEqual((tv.start_tick, tv.finish_tick), (33, 36))   # 5.5..6.0
        self.assertEqual(tv.profile, "0.5h_overlap")
        self.assertEqual(len(self.r.turnovers), 1)

    def test_device3_entry_6h(self):
        self.assertEqual(find_device(self.r, 3).entry_tick, 36)
        self.assertEqual(find_task(self.r, 3, "A", 1).finish_tick, 51)
        self.assertEqual(find_task(self.r, 3, "B", 1).finish_tick, 48)
        e = find_task(self.r, 3, "E", 1)
        self.assertEqual(e.start_tick, 51)
        self.assertEqual(e.finish_tick, 69)

    def test_makespan_11_5h(self):
        self.assertEqual(self.r.makespan_tick, 69)  # 11.5h < 1h-literal 的 12h
        self.assertEqual(self.r.makespan_hours(), Fraction(23, 2))


# ---------------------------------------------------------------------------
# 18. F11 下一班调度 / 活性等价
# ---------------------------------------------------------------------------

class TestF11Liveness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F11"])

    def test_e_retest_wakes_next_shift(self):
        e2 = find_task(self.r, 1, "E", 2)
        self.assertTrue(e2.exists)
        self.assertEqual(e2.release_tick, 48)
        self.assertEqual(e2.start_tick, 54)   # 下一班起点唤醒并执行
        self.assertEqual(e2.finish_tick, 72)
        self.assertEqual(e2.outcome, "PASS")

    def test_no_deadlock_and_T(self):
        self.assertEqual(self.r.status, "OPTIMAL")
        self.assertEqual(self.r.makespan_tick, 72)


# ---------------------------------------------------------------------------
# 19. F12 末台终态 makespan、无必要末台周转
# ---------------------------------------------------------------------------

class TestF12LastDeviceNoTurnover(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = oracle.solve_fixture(FIXTURES["F12"])

    def test_no_turnover_events(self):
        self.assertEqual(self.r.turnovers, [])

    def test_makespan_at_terminal_judgment(self):
        self.assertEqual(self.r.makespan_tick, 33)   # 5.5h，末台不计运出
        self.assertEqual(find_device(self.r, 1).terminal_state, "PASSED")
        self.assertEqual(find_device(self.r, 1).terminal_tick, 33)


# ---------------------------------------------------------------------------
# 20. 无 DES import
# ---------------------------------------------------------------------------

class TestNoDESImports(unittest.TestCase):
    # 拼接构造，避免扫描 token 出现在本文件自身的字面量中
    _BANNED = ["deterministic_" + "des", "state_" + "models", "test_" + "des_main", "main_" + "model"]

    def test_oracle_module_imports_only_allowed(self):
        src = pathlib.Path(oracle.__file__).read_text(encoding="utf-8")
        for token in self._BANNED:
            self.assertNotIn(token, src)
        allowed = {"ortools", "cp_model", "dataclasses", "decimal", "fractions", "annotations", "__future__"}
        for line in src.splitlines():
            s = line.strip()
            if s.startswith("import ") or s.startswith("from "):
                mod = s.split()[1].split(".")[0]
                self.assertIn(mod, allowed, "oracle 模块出现非允许 import: %s" % s)

    def test_test_module_does_not_import_des(self):
        src = pathlib.Path(__file__).read_text(encoding="utf-8")
        for token in self._BANNED:
            self.assertNotIn(token, src)

    def test_oracle_module_has_no_event_loop(self):
        src = pathlib.Path(oracle.__file__).read_text(encoding="utf-8")
        for token in ("while True", "heapq", "queue.", "deque"):
            self.assertNotIn(token, src)


# ---------------------------------------------------------------------------
# 21. 无 DES 派生输入
# ---------------------------------------------------------------------------

class TestNoDESDerivedInput(unittest.TestCase):
    def test_acceptance_and_des_fields_ignored(self):
        base = FIXTURES["F8"]
        r1 = oracle.solve_fixture(base)
        mutated = copy.deepcopy(base)
        mutated["acceptance"]["T"] = "9999"
        mutated["acceptance"]["key_assertions"] = ["hacked"]
        mutated["des_event_log"] = {"records": [{"hacked": True}]}
        mutated["des_timeline"] = {"start": 0, "end": 1}
        r2 = oracle.solve_fixture(mutated)
        self.assertEqual(r1.to_dict(), r2.to_dict())

    def test_primitive_extraction_only(self):
        prim = oracle.extract_fixture_primitive(FIXTURES["F8"])
        self.assertEqual(set(prim.keys()), {"fixture_id", "config", "scripted_outcomes", "scripted_real_states"})

    def test_solver_source_does_not_reference_acceptance(self):
        src = pathlib.Path(oracle.__file__).read_text(encoding="utf-8")
        self.assertNotIn("acceptance", src)


# ---------------------------------------------------------------------------
# 22. 单 worker 确定性 solver
# ---------------------------------------------------------------------------

class TestSingleWorkerDeterminism(unittest.TestCase):
    def test_solver_parameters_pinned(self):
        r = oracle.solve_fixture(FIXTURES["F1"])
        self.assertEqual(r.solver_parameters["num_search_workers"], 1)
        self.assertEqual(r.solver_parameters["random_seed"], 0)
        self.assertEqual(oracle.DEFAULT_SOLVER_PARAMETERS["num_search_workers"], 1)
        self.assertEqual(oracle.DEFAULT_SOLVER_PARAMETERS["random_seed"], 0)

    def test_all_results_report_single_worker(self):
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                r = oracle.solve_fixture(FIXTURES[fid])
                self.assertEqual(r.solver_parameters["num_search_workers"], 1)
                self.assertEqual(r.solver_parameters["random_seed"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
