# -*- coding: utf-8 -*-
"""G2-03 S3 三方对拍比较器测试（test_three_way_crosscheck_v1.py）

覆盖范围（7 项要求全部落实）：
 1. 14 个 concrete fixture（F1..F12 + F4b/F9b）全部可比较且比较器自身 PASS
    （DES 与 CP-SAT 语义无差异；hand 转录无错误）；
 2. 每 fixture 三方 T 一致（小时与 tick）：F1 33t/5.5h；F2 51t/8.5h；F3 42t/7h；
    F4 63t/10.5h；F4b 48t/8h；F5 30t/5h；F6 72t/12h；F7 72t/12h；F8 84t/14h；
    F9 72t/12h；F9b 90t/15h；F10 69t/11.5h；F11 72t/12h；F12 33t/5.5h；
 3. K9/F8 专项 tick 断言（release=51/start=54/finish=66、E 66..84、T=84、B1 finish=51
    ABNORMAL、B2 attempt=2）；
 4. tick<->hour 精确换算（含非整数小时显式拒绝、float 输入显式拒绝）；
 5. 比较器自身错误注入：人为制造 tick 偏移（oracle 侧 start、DES 侧 finish），
    比较器能检测出差异（证明比较器不是恒 PASS）；
 6. 无 float canonical 比较（值类型 + 模块源码卫生）；
 7. 重复运行比较结果确定（比较器本身确定性；CP-SAT 侧由 num_search_workers=1 /
    random_seed=0 保证）。

本测试不修改任何既有文件；只读 fixture JSON / DES / CP-SAT / hand 常量。
"""

import copy
import json
import pathlib
import sys
import unittest
from fractions import Fraction

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import three_way_crosscheck_v1 as xcheck  # noqa: E402

FIXTURES_FILE = _HERE / "fixtures" / "des_fixtures_F1_F12_v1.json"
_FIXTURE_DATA = json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))
FIXTURES = {f["fixture_id"]: f for f in _FIXTURE_DATA["fixtures"]}
CONCRETE_CASES = xcheck.FIXTURES_ORDER


def _report(fid: str):
    fixture = FIXTURES[fid]
    return xcheck.crosscheck_fixture(
        fixture, xcheck.run_des_fixture(fixture), xcheck.run_oracle_fixture(fixture))


def _row(report, device, process, attempt):
    for r in report.rows:
        if r.key == (device, process, attempt):
            return r
    raise AssertionError("row not found: (%d,%s,%d)" % (device, process, attempt))


def _ticks(value_str):
    return xcheck.hours_to_ticks(xcheck.parse_hours(value_str))


class TestAllFixturesComparableAndPass(unittest.TestCase):
    """要求 1：14 个 fixture 全部可比较且比较器 PASS（无 DES/CP-SAT 语义差异）。"""

    def test_all_14_concrete_cases_pass(self):
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                report = _report(fid)
                self.assertEqual(report.fixture_id, fid)
                self.assertEqual(report.verdict, "PASS", "diffs: %s" % report.diffs)
                self.assertEqual(report.diffs, [], fid)
                self.assertGreater(len(report.rows), 0, fid)

    def test_hand_T_matches_acceptance_T(self):
        # 机械转录一致性：hand T 常量 == fixture acceptance.T（捕捉转录错误）
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                acc_t = Fraction(FIXTURES[fid]["acceptance"]["T"])
                self.assertEqual(xcheck.EXPECTED_T_HOURS[fid], acc_t, fid)
                self.assertEqual(xcheck.hours_to_ticks(acc_t),
                                 xcheck.EXPECTED_T_TICKS[fid], fid)

    def test_k9_authoritative_file_referenced(self):
        self.assertTrue(xcheck.K9_AUTHORITATIVE_PATH.exists(),
                        "K9 权威手算文件缺失: %s" % xcheck.K9_AUTHORITATIVE_PATH)


class TestTMakespanAgreement(unittest.TestCase):
    """要求 2：每 fixture 三方 T 一致（小时与 tick）。"""

    EXPECTED = {
        "F1": (33, Fraction(11, 2)), "F2": (51, Fraction(17, 2)), "F3": (42, Fraction(7)),
        "F4": (63, Fraction(21, 2)), "F4b": (48, Fraction(8)), "F5": (30, Fraction(5)),
        "F6": (72, Fraction(12)), "F7": (72, Fraction(12)), "F8": (84, Fraction(14)),
        "F9": (72, Fraction(12)), "F9b": (90, Fraction(15)), "F10": (69, Fraction(23, 2)),
        "F11": (72, Fraction(12)), "F12": (33, Fraction(11, 2)),
    }

    def test_three_way_T_per_fixture(self):
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                report = _report(fid)
                exp_tick, exp_hours = self.EXPECTED[fid]
                self.assertEqual(report.des_T_tick, exp_tick, fid)
                self.assertEqual(report.oracle_T_tick, exp_tick, fid)
                self.assertEqual(report.hand_T_tick, exp_tick, fid)
                self.assertEqual(report.des_T_h, exp_hours, fid)
                self.assertEqual(report.oracle_T_h, exp_hours, fid)
                self.assertEqual(report.hand_T_h, exp_hours, fid)
                self.assertEqual(report.des_T_h, report.oracle_T_h, fid)
                self.assertEqual(report.oracle_T_h, report.hand_T_h, fid)


class TestK9SpecialAssertions(unittest.TestCase):
    """要求 3：K9/F8 tick 断言（release=51/start=54/finish=66、E 66..84、T=84）。"""

    @classmethod
    def setUpClass(cls):
        cls.report = _report("F8")

    def test_all_named_assertions_pass(self):
        self.assertEqual(self.report.verdict, "PASS")
        self.assertEqual(len(self.report.special_assertions), 8)
        for item in self.report.special_assertions:
            self.assertTrue(item["ok"], "%s: %s" % (item["name"], item["detail"]))

    def test_T_84_ticks(self):
        self.assertEqual([self.report.des_T_tick, self.report.oracle_T_tick,
                          self.report.hand_T_tick], [84, 84, 84])
        self.assertEqual(self.report.des_T_h, Fraction(14))

    def test_d3_B1_finish_51_abnormal(self):
        row = _row(self.report, 3, "B", 1)
        self.assertEqual(row.finish, ["17/2", "17/2", "17/2"])
        self.assertEqual([_ticks(v) for v in row.finish], [51, 51, 51])
        self.assertEqual(row.outcome, ["ABNORMAL", "ABNORMAL", "ABNORMAL"])

    def test_d3_B2_release_start_finish(self):
        row = _row(self.report, 3, "B", 2)
        self.assertEqual(row.release, ["17/2", "17/2", "17/2"])  # 51 ticks, never rewritten
        self.assertEqual([_ticks(v) for v in row.release], [51, 51, 51])
        self.assertEqual(row.start, ["9", "9", "9"])             # 54 ticks
        self.assertEqual([_ticks(v) for v in row.start], [54, 54, 54])
        self.assertEqual(row.finish, ["11", "11", "11"])         # 66 ticks
        self.assertEqual([_ticks(v) for v in row.finish], [66, 66, 66])
        self.assertEqual(row.key[2], 2)                          # effective_attempt_no = 2

    def test_d3_E_66_84(self):
        row = _row(self.report, 3, "E", 1)
        self.assertEqual(row.start, ["11", "11", "11"])
        self.assertEqual([_ticks(v) for v in row.start], [66, 66, 66])
        self.assertEqual(row.finish, ["14", "14", "14"])
        self.assertEqual([_ticks(v) for v in row.finish], [84, 84, 84])

    def test_k9_yxb_readonly(self):
        # 三方 YXB 对齐（hand: 5/12, 4/9, 5/12, 1/2；分母 18h=108 ticks）
        for item in self.report.metric_rows:
            if item["metric"].startswith("YXB_"):
                self.assertTrue(item["match"], item)
        des_metrics = xcheck.run_des_fixture(FIXTURES["F8"]).metrics
        self.assertEqual(Fraction(des_metrics["YXB_A"]), Fraction(5, 12))
        self.assertEqual(Fraction(des_metrics["YXB_B"]), Fraction(4, 9))
        self.assertEqual(Fraction(des_metrics["YXB_C"]), Fraction(5, 12))
        self.assertEqual(Fraction(des_metrics["YXB_E"]), Fraction(1, 2))

    def test_k9_device_terminals(self):
        by_id = {d["device_id"]: d for d in self.report.device_rows}
        self.assertEqual(by_id[1]["terminal"], ["11/2", "11/2", "11/2"])
        self.assertEqual(by_id[2]["terminal"], ["17/2", "17/2", "17/2"])
        self.assertEqual(by_id[3]["terminal"], ["14", "14", "14"])
        self.assertEqual(by_id[3]["d_created"], ["11", "11", "11"])


class TestTickHourConversion(unittest.TestCase):
    """要求 4：tick<->hour 精确换算（含非整数小时拒绝）。"""

    def test_exact_conversions(self):
        self.assertEqual(xcheck.hours_to_ticks(Fraction(11, 2)), 33)
        self.assertEqual(xcheck.hours_to_ticks(Fraction(14, 1)), 84)
        self.assertEqual(xcheck.hours_to_ticks("2.5"), 15)
        self.assertEqual(xcheck.hours_to_ticks("0.5"), 3)
        self.assertEqual(xcheck.hours_to_ticks("9"), 54)
        self.assertEqual(xcheck.ticks_to_hours(33), Fraction(11, 2))
        self.assertEqual(xcheck.ticks_to_hours(84), Fraction(14, 1))
        self.assertEqual(xcheck.ticks_to_hours(51), Fraction(17, 2))

    def test_roundtrip_all_fixture_T(self):
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                t = xcheck.EXPECTED_T_TICKS[fid]
                self.assertEqual(xcheck.hours_to_ticks(xcheck.ticks_to_hours(t)), t, fid)

    def test_non_integer_tick_rejected(self):
        for bad in ("2.7", "1/60", "0.1"):
            with self.subTest(bad=bad):
                with self.assertRaises(xcheck.NonIntegerTickError):
                    xcheck.hours_to_ticks(bad)
        with self.assertRaises(xcheck.NonIntegerTickError):
            xcheck.hours_to_ticks(Fraction(1, 60))

    def test_float_input_rejected(self):
        with self.assertRaises(xcheck.NonIntegerTickError):
            xcheck.hours_to_ticks(2.5)
        with self.assertRaises(xcheck.NonIntegerTickError):
            xcheck.parse_hours(2.5)
        with self.assertRaises(xcheck.NonIntegerTickError):
            xcheck.parse_hours(True)


class TestErrorInjectionDetected(unittest.TestCase):
    """要求 5：比较器自身错误注入 -> 比较器能检测出差异（非恒 PASS）。"""

    def _baseline(self, fid):
        fixture = FIXTURES[fid]
        return fixture, xcheck.run_des_fixture(fixture), xcheck.run_oracle_fixture(fixture)

    def test_oracle_start_tick_offset_detected(self):
        fixture, des_result, oracle_result = self._baseline("F1")
        baseline = xcheck.crosscheck_fixture(fixture, des_result, oracle_result)
        self.assertEqual(baseline.verdict, "PASS")
        mutated = copy.deepcopy(oracle_result)
        for t in mutated.tasks:
            if t.exists and t.device_id == 1 and t.process == "B" and t.effective_attempt_no == 1:
                t.start_tick += 1  # 人为 +1 tick（10min）
                break
        report = xcheck.crosscheck_fixture(fixture, des_result, mutated)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(any(d.field == "start" and d.location.startswith("task(1,B,1)")
                            for d in report.diffs),
                        "expected a start diff on task(1,B,1), got: %s" % report.diffs)

    def test_des_finish_time_offset_detected(self):
        fixture, des_result, oracle_result = self._baseline("F1")
        mutated = copy.deepcopy(des_result)
        for rec in mutated.event_log:
            if (rec["event_type"] == "ACTIVITY_COMPLETE"
                    and rec["device_id"] == 1 and rec["process"] == "A"):
                rec["event_time"] = "8/3"  # 5/2 + 1/6 h（+1 tick）
                break
        report = xcheck.crosscheck_fixture(fixture, mutated, oracle_result)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(any(d.field == "finish" and d.location.startswith("task(1,A,1)")
                            for d in report.diffs),
                        "expected a finish diff on task(1,A,1), got: %s" % report.diffs)

    def test_existence_injection_detected(self):
        # 人为让 oracle 丢失一个任务 -> existence 差异被检出
        fixture, des_result, oracle_result = self._baseline("F8")
        mutated = copy.deepcopy(oracle_result)
        for t in mutated.tasks:
            if t.exists and t.device_id == 3 and t.process == "B" and t.effective_attempt_no == 2:
                t.exists = False
                break
        report = xcheck.crosscheck_fixture(fixture, des_result, mutated)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(any(d.field == "exists" for d in report.diffs), report.diffs)


class TestNoFloatCanonical(unittest.TestCase):
    """要求 6：无 float canonical 比较。"""

    def test_report_values_never_float(self):
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                report = _report(fid)
                payload = xcheck.report_to_dict(report)

                def walk(node):
                    if isinstance(node, dict):
                        for v in node.values():
                            walk(v)
                    elif isinstance(node, list):
                        for v in node:
                            walk(v)
                    else:
                        self.assertFalse(isinstance(node, float),
                                         "%s: float value %r" % (fid, node))
                walk(payload)

    def test_comparator_source_has_no_float_arith(self):
        src = pathlib.Path(xcheck.__file__).read_text(encoding="utf-8")
        for token in ("float(", "round(", "epsilon", "math.", "int(0.5"):
            self.assertNotIn(token, src)
        # 顶层只允许标准库 import；DES/CP-SAT 是任务授权的桥接输入源，允许延迟导入
        allowed = {"annotations", "__future__", "json", "dataclasses", "fractions",
                   "pathlib", "typing", "sys", "des", "cp_sat_oracle_v1"}
        for line in src.splitlines():
            s = line.strip()
            if s.startswith("import ") or s.startswith("from "):
                mod = s.split()[1].split(".")[0]
                self.assertIn(mod, allowed, "比较器模块出现非允许 import: %s" % s)


class TestRepeatDeterminism(unittest.TestCase):
    """要求 7：重复运行比较结果确定。"""

    def test_crosscheck_all_twice_identical(self):
        first = xcheck.crosscheck_all(FIXTURES)
        second = xcheck.crosscheck_all(FIXTURES)
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                self.assertEqual(
                    json.dumps(xcheck.report_to_dict(first[fid]), ensure_ascii=False, sort_keys=True),
                    json.dumps(xcheck.report_to_dict(second[fid]), ensure_ascii=False, sort_keys=True),
                    fid)
                self.assertEqual(first[fid].verdict, "PASS", fid)

    def test_single_fixture_repeat_identical(self):
        for fid in ("F4b", "F8", "F9b"):
            with self.subTest(fid=fid):
                a = _report(fid)
                b = _report(fid)
                self.assertEqual(xcheck.report_to_dict(a), xcheck.report_to_dict(b), fid)


class TestMatrixCompleteness(unittest.TestCase):
    """对齐矩阵健全性：每行三方值精确可解析且 attempt 列正确。"""

    def test_rows_cover_expected_task_count(self):
        # 期望任务数（存在 + 不存在的负断言键）——来自 fixture 语义
        expected_counts = {
            "F1": 4, "F2": 8, "F3": 5, "F4": 10, "F4b": 11, "F5": 5, "F6": 6,
            "F7": 12, "F8": 13, "F9": 12, "F9b": 17, "F10": 12, "F11": 6, "F12": 4,
        }
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                report = _report(fid)
                self.assertEqual(len(report.rows), expected_counts[fid], fid)

    def test_all_rows_match(self):
        for fid in CONCRETE_CASES:
            with self.subTest(fid=fid):
                report = _report(fid)
                for r in report.rows:
                    self.assertTrue(r.match, "%s row %s" % (fid, r.key))


if __name__ == "__main__":
    unittest.main(verbosity=2)
