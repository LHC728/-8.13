# -*- coding: utf-8 -*-
"""G2-04 independent event-log replay checker unit tests (CR-V3.1 C08/C17/C19/C20/C21).

Scope
-----
Tests for ``04_代码/checker/des_checker_v1.py`` (the E2 independent checker of
task package G2-03-SPEC-V1.0.2 / G2-04).  The object under test is the
immutable event_log produced by the accepted main DES
(``04_代码/main_model/des/deterministic_des_v1.py``); the test file is the
only place allowed to CALL the main engine to generate those logs.

Covers (12 groups):
  1. all 14 concrete fixtures' event_logs pass the independent checker;
  2. F8 / K9 special assertions (T=84 ticks, B2 release=51/start=54/finish=66,
     E 66..84, YXB read-only);
  3. bay occupancy and A/B/C/E resource occupancy independently recomputed;
  4. release_time invariance across the shift change;
  5. effective_attempt_no never advanced by cancellation;
  6. D materialization timing (E2 before E release; no E-start D; no retest D;
     early-exit not_created);
  7. turnover (1h literal phases / 0.5h overlap zero-duration IN folding);
  8. same-timestamp settle-before-exit / settle-before-shift ordering;
  9. fault injection (C20): 5 injected mutations must all FAIL with precise
     differences (proving the checker is not always-PASS);
 10. checker isolation (C19): static AST scan + dynamic subprocess run without
     the main engine importable;
 11. empty / incomplete / seq-gapped event_logs must explicitly FAIL;
 12. repeated checker runs are deterministic (byte-identical reports).

The checker module itself never imports the main DES; this test file does
(only to generate the logs under test).
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]          # competitions/模拟赛_研究生A题
CODE_DIR = BASE / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(CODE_DIR), str(MAIN_MODEL)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from checker import des_checker_v1 as chk  # noqa: E402
from des import deterministic_des_v1 as de  # noqa: E402  (test-only fixture generation)

FIXTURES_PATH = CODE_DIR / "tests/fixtures/des_fixtures_F1_F12_v1.json"
PARAMETERS_PATH = BASE / "02_数据/parameters.csv"
CHECKER_PATH = CODE_DIR / "checker/des_checker_v1.py"
CHECKER_DIR = CODE_DIR / "checker"

FIXTURES_ORDER = [
    "F1", "F2", "F3", "F4", "F4b", "F5", "F6", "F7", "F8", "F9", "F9b",
    "F10", "F11", "F12",
]


def clone(log):
    """Deep-copy an event log (JSON round-trip keeps only JSON-safe fields)."""
    return json.loads(json.dumps(log))


class DesCheckerTestCase(unittest.TestCase):
    """Shared fixture loading / run helpers."""

    fixtures: dict[str, dict]

    @classmethod
    def setUpClass(cls) -> None:
        with open(FIXTURES_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        cls.fixtures = {f["fixture_id"]: f for f in data["fixtures"]}

    def fixture(self, fixture_id: str) -> dict:
        return self.fixtures[fixture_id]

    def run_fixture(self, fixture_id: str):
        fixture = self.fixture(fixture_id)
        return de.run_des(fixture["config"], fixture)

    def check(self, fixture_id: str, event_log=None, metrics=None):
        fixture = self.fixture(fixture_id)
        if event_log is None:
            event_log = self.run_fixture(fixture_id).event_log
        if metrics is None:
            metrics = self.run_fixture(fixture_id).metrics
        return chk.check_event_log(event_log, fixture["config"], fixture,
                                   parameters=str(PARAMETERS_PATH), metrics=metrics)

    @staticmethod
    def records(log, event_type: str) -> list[dict]:
        return [r for r in log if r["event_type"] == event_type]

    @staticmethod
    def frac(value) -> Fraction:
        return Fraction(value)

    # ------------------------------------------------------------------
    # 1. All 14 concrete fixtures PASS the independent checker
    # ------------------------------------------------------------------
    def test_01_all_14_fixtures_checker_pass(self) -> None:
        for fixture_id in FIXTURES_ORDER:
            report = self.check(fixture_id)
            self.assertEqual(report.verdict, "PASS",
                             "%s: %s" % (fixture_id,
                                         "; ".join(i.describe() for i in report.issues[:8])))
            self.assertEqual(report.issues, [], fixture_id)

    # ------------------------------------------------------------------
    # 2. F8 / K9 special assertions (authoritative hand timeline)
    # ------------------------------------------------------------------
    def test_02_F8_K9_special_assertions(self) -> None:
        report = self.check("F8")
        self.assertEqual(report.verdict, "PASS")
        r = report.recomputed
        self.assertEqual(r["T_h"], "14")
        self.assertEqual(r["T_ticks"], 84)
        self.assertEqual(r["S"], 3)
        self.assertEqual(r["PL"], 0)
        self.assertEqual(r["PW"], 0)
        # K9: B2 release=51 / start=54 / finish=66 ticks; E 66..84
        tasks = r["tasks"]
        self.assertEqual(tasks["D003_B_2"]["release_h"], "17/2")   # 51 ticks
        self.assertEqual(tasks["D003_B_2"]["start_h"], "9")        # 54 ticks
        self.assertEqual(tasks["D003_B_2"]["finish_h"], "11")      # 66 ticks
        self.assertEqual(tasks["D003_B_2"]["outcome"], "PASS")
        self.assertEqual(tasks["D003_E_1"]["start_h"], "11")       # 66 ticks
        self.assertEqual(tasks["D003_E_1"]["finish_h"], "14")      # 84 ticks
        # YXB read-only: 7.5/18=5/12, 8/18=4/9, 9/18=1/2
        self.assertEqual(r["YXB_A"], "5/12")
        self.assertEqual(r["YXB_B"], "4/9")
        self.assertEqual(r["YXB_C"], "5/12")
        self.assertEqual(r["YXB_E"], "1/2")
        self.assertEqual(r["yxb_denominator_h"], "18")
        # every named K9 assertion must hold
        for assertion in report.special_assertions:
            self.assertTrue(assertion["ok"], "%s: %s" % (assertion["name"], assertion["detail"]))
        # bay2 terminal-occupied-until-stop
        self.assertEqual(report.recomputed["bay_coverage"]["2"]["intervals"][0],
                         ["0", "14"])

    # ------------------------------------------------------------------
    # 3. Bay occupancy and resource occupancy recomputed from the log
    # ------------------------------------------------------------------
    def test_03_bay_and_resource_occupancy(self) -> None:
        # F8: bay1 tiles [0,14): dev1 [0,5.5) + OUT [5.5,6) + IN [6,6.5) + dev3 [6.5,14)
        report = self.check("F8")
        bay1 = report.recomputed["bay_coverage"]["1"]["intervals"]
        self.assertEqual(bay1, [["0", "11/2"], ["11/2", "6"], ["6", "13/2"], ["13/2", "14"]])
        bay2 = report.recomputed["bay_coverage"]["2"]["intervals"]
        self.assertEqual(bay2, [["0", "14"]])
        # resource busy totals: A 3x2.5=7.5, B 4x2=8, C 3x2.5=7.5, E 3x3=9
        busy = report.recomputed["resource_busy"]
        self.assertEqual(busy["A"]["total_h"], "15/2")
        self.assertEqual(busy["B"]["total_h"], "8")
        self.assertEqual(busy["C"]["total_h"], "15/2")
        self.assertEqual(busy["E"]["total_h"], "9")
        # F9b: concurrent transport on [6,6.5) across bays (SEM-23) without
        # overlap inside each bay; device3 stays in bay1 until T (terminal-
        # occupied-until-stop after its terminal at 12, since device4 is the
        # last device and occupies bay2)
        report = self.check("F9b")
        self.assertEqual(report.recomputed["bay_coverage"]["1"]["intervals"],
                         [["0", "11/2"], ["11/2", "6"], ["6", "13/2"], ["13/2", "15"]])
        self.assertEqual(report.recomputed["bay_coverage"]["2"]["intervals"],
                         [["0", "6"], ["6", "13/2"], ["13/2", "7"], ["7", "15"]])
        # F10: 0.5h overlap folded: physical [11/2,6) then dev3 [6, ...)
        report = self.check("F10")
        self.assertEqual(report.recomputed["bay_coverage"]["1"]["intervals"],
                         [["0", "11/2"], ["11/2", "6"], ["6", "23/2"]])
        # F1: single device, bay2 EMPTY (no records at all)
        report = self.check("F1")
        self.assertNotIn("2", report.recomputed.get("bay_coverage", {}))
        log = self.run_fixture("F1").event_log
        self.assertEqual([r for r in log if r.get("bay_id") == 2], [])

    # ------------------------------------------------------------------
    # 4. release_time invariance across the shift change (K9 path assertion)
    # ------------------------------------------------------------------
    def test_04_release_time_cross_shift(self) -> None:
        result = self.run_fixture("F8")
        log = result.event_log
        report = self.check("F8")
        self.assertEqual(report.verdict, "PASS")
        for record in log:
            if record.get("task_id") == "D003_B_2" and "release_time" in record:
                self.assertEqual(record["release_time"], "17/2", record)
        b2_start = [r for r in log
                    if r["event_type"] == "ACTIVITY_START" and r.get("task_id") == "D003_B_2"][0]
        self.assertEqual(b2_start["event_time"], "9")            # shift 2 start
        self.assertEqual(b2_start["release_time"], "17/2")       # key kept across shift
        # F6: E retest released at 8.0 but started at 9.0 with the frozen key
        result = self.run_fixture("F6")
        log = result.event_log
        e2_start = [r for r in log
                    if r["event_type"] == "ACTIVITY_START" and r.get("process") == "E"
                    and r.get("effective_attempt_no") == 2][0]
        self.assertEqual(e2_start["event_time"], "9")
        self.assertEqual(e2_start["release_time"], "8")
        self.assertEqual(self.check("F6").verdict, "PASS")

    # ------------------------------------------------------------------
    # 5. effective_attempt_no: cancellation never advances the attempt
    # ------------------------------------------------------------------
    def test_05_attempt_not_advanced_by_cancel(self) -> None:
        result = self.run_fixture("F4b")
        log = result.event_log
        report = self.check("F4b")
        self.assertEqual(report.verdict, "PASS")
        for cancel in self.records(log, "TASK_CANCEL"):
            self.assertEqual(cancel["effective_attempt_no"], 2, cancel)
        # no attempt 3 anywhere in the whole log
        for record in log:
            self.assertIn(record.get("effective_attempt_no"), (1, 2, None), record)
        # every attempt-2 observation is preceded by a completed first ABNORMAL
        result = self.run_fixture("F4")
        log = result.event_log
        for obs in self.records(log, "OBSERVATION_MATERIALIZED"):
            if obs["effective_attempt_no"] == 2:
                first = [r for r in self.records(log, "OBSERVATION_MATERIALIZED")
                         if r["device_id"] == obs["device_id"]
                         and r["process"] == obs["process"]
                         and r["effective_attempt_no"] == 1]
                self.assertEqual(len(first), 1, obs)
                self.assertEqual(first[0]["outcome"], "ABNORMAL", obs)
                self.assertLess(first[0]["seq"], obs["seq"], obs)
        # monotonic 1 < 2 per (device, process)
        for fixture_id in ("F3", "F4", "F4b", "F6", "F8"):
            log = self.run_fixture(fixture_id).event_log
            per_process: dict = {}
            for obs in self.records(log, "OBSERVATION_MATERIALIZED"):
                per_process.setdefault((obs["device_id"], obs["process"]), []).append(obs)
            for key, obs_list in per_process.items():
                attempts = [o["effective_attempt_no"] for o in obs_list]
                self.assertEqual(attempts, sorted(attempts), key)

    # ------------------------------------------------------------------
    # 6. D materialization timing (E2 rules, V1.0.2)
    # ------------------------------------------------------------------
    def test_06_d_materialization_timing(self) -> None:
        # F2: device2 D at 5.0 == E TASK_RELEASE, before E ACTIVITY_START 5.5
        result = self.run_fixture("F2")
        log = result.event_log
        d2 = [r for r in self.records(log, "D_CREATED") if r["device_id"] == 2][0]
        e_rel = [r for r in self.records(log, "TASK_RELEASE")
                 if r["device_id"] == 2 and r["process"] == "E"][0]
        e_start = [r for r in self.records(log, "ACTIVITY_START")
                   if r["device_id"] == 2 and r["process"] == "E"][0]
        self.assertEqual(d2["event_time"], "5")
        self.assertEqual(e_rel["event_time"], "5")
        self.assertLess(d2["seq"], e_rel["seq"])      # D_CREATED.seq < TASK_RELEASE(E).seq
        self.assertLess(self.frac(e_rel["event_time"]), self.frac(e_start["event_time"]))
        self.assertEqual(self.check("F2").verdict, "PASS")
        # F6: E retest (9.0..12.0) never regenerates D: exactly one D_CREATED at 5.0
        result = self.run_fixture("F6")
        log = result.event_log
        d_recs = self.records(log, "D_CREATED")
        self.assertEqual(len(d_recs), 1)
        self.assertEqual(d_recs[0]["event_time"], "5")
        e2_rel = [r for r in self.records(log, "TASK_RELEASE")
                  if r["process"] == "E" and r["effective_attempt_no"] == 2][0]
        self.assertEqual(e2_rel["event_time"], "8")
        self.assertNotEqual(e2_rel["event_time"], d_recs[0]["event_time"])
        # F5: early exit -> d_state stays not_created, no D_CREATED
        result = self.run_fixture("F5")
        log = result.event_log
        self.assertEqual(self.records(log, "D_CREATED"), [])
        self.assertEqual(self.check("F5").verdict, "PASS")

    # ------------------------------------------------------------------
    # 7. Turnover: 1h literal phases and 0.5h overlap folding
    # ------------------------------------------------------------------
    def test_07_turnover_folding(self) -> None:
        # F9: 1h literal OUT [5.5,6) + IN [6,6.5)
        result = self.run_fixture("F9")
        log = result.event_log
        out_start = [r for r in self.records(log, "TURNOVER_OUT_START")][0]
        out_comp = [r for r in self.records(log, "TURNOVER_OUT_COMPLETE")][0]
        in_start = [r for r in self.records(log, "TURNOVER_IN_START")][0]
        in_comp = [r for r in self.records(log, "TURNOVER_IN_COMPLETE")][0]
        self.assertEqual((out_start["event_time"], out_comp["event_time"]), ("11/2", "6"))
        self.assertEqual((in_start["event_time"], in_comp["event_time"]), ("6", "13/2"))
        # F10: 0.5h overlap — IN phases at one timestamp (zero-duration rep.),
        # physical bay occupancy strictly [5.5, 6.0) and NOT double counted
        result = self.run_fixture("F10")
        log = result.event_log
        for event_type in ("TURNOVER_OUT_COMPLETE", "TURNOVER_IN_START", "TURNOVER_IN_COMPLETE"):
            recs = self.records(log, event_type)
            self.assertEqual(len(recs), 1, event_type)
            self.assertEqual(recs[0]["event_time"], "6", event_type)
        report = self.check("F10")
        self.assertEqual(report.verdict, "PASS")
        bay1 = report.recomputed["bay_coverage"]["1"]["intervals"]
        self.assertEqual(bay1, [["0", "11/2"], ["11/2", "6"], ["6", "23/2"]])
        # F12: no turnover at all for the last device
        result = self.run_fixture("F12")
        self.assertEqual([r for r in result.event_log
                          if r["event_type"].startswith("TURNOVER")], [])

    # ------------------------------------------------------------------
    # 8. Same-timestamp: settle before exit / settle before shift change
    # ------------------------------------------------------------------
    def test_08_same_tick_settle_first(self) -> None:
        # F4: at t*=7.5 device2 C2 PASS settles before device1 EXIT
        result = self.run_fixture("F4")
        log = result.event_log
        c2_obs = [r for r in self.records(log, "OBSERVATION_MATERIALIZED")
                  if r["device_id"] == 2 and r["process"] == "C"
                  and r["effective_attempt_no"] == 2][0]
        exit_rec = [r for r in self.records(log, "DEVICE_EXIT")][0]
        self.assertEqual(c2_obs["event_time"], exit_rec["event_time"])
        self.assertLess(c2_obs["seq"], exit_rec["seq"])
        # F7: at 9.0 device3 A/C completions settle before SHIFT_CHANGE
        result = self.run_fixture("F7")
        log = result.event_log
        shift_at_9 = [r for r in self.records(log, "SHIFT_CHANGE")
                      if r["event_time"] == "9"][0]
        for process in ("A", "C"):
            obs = [r for r in self.records(log, "OBSERVATION_MATERIALIZED")
                   if r["device_id"] == 3 and r["process"] == process][0]
            self.assertLess(obs["seq"], shift_at_9["seq"], process)
        # F8: same rule at 9.0
        result = self.run_fixture("F8")
        log = result.event_log
        shift_at_9 = [r for r in self.records(log, "SHIFT_CHANGE")
                      if r["event_time"] == "9"][0]
        for process in ("A", "C"):
            obs = [r for r in self.records(log, "OBSERVATION_MATERIALIZED")
                   if r["device_id"] == 3 and r["process"] == process][0]
            self.assertLess(obs["seq"], shift_at_9["seq"], process)
        # F4b: at 6.0 DEVICE_EXIT before TASK_CANCEL
        result = self.run_fixture("F4b")
        log = result.event_log
        exit_rec = [r for r in self.records(log, "DEVICE_EXIT")][0]
        for cancel in self.records(log, "TASK_CANCEL"):
            self.assertLess(exit_rec["seq"], cancel["seq"])
        # D_CREATED before SHIFT_CHANGE and SHIFT_CHANGE before TASK_RELEASE at 9.0 (F7)
        result = self.run_fixture("F7")
        log = result.event_log
        d3 = [r for r in self.records(log, "D_CREATED") if r["device_id"] == 3][0]
        shift = [r for r in self.records(log, "SHIFT_CHANGE") if r["event_time"] == "9"][0]
        e_rel = [r for r in self.records(log, "TASK_RELEASE")
                 if r["device_id"] == 3 and r["process"] == "E"][0]
        self.assertLess(d3["seq"], shift["seq"])
        self.assertLess(shift["seq"], e_rel["seq"])

    # ------------------------------------------------------------------
    # 9. Fault injection (CR-V3.1/C20): checker must catch all five
    # ------------------------------------------------------------------
    def test_09_fault_injection(self) -> None:
        # --- (a) start_time offset +1 tick ----------------------------------
        result = self.run_fixture("F3")
        log = clone(result.event_log)
        for r in log:
            if r["event_type"] == "ACTIVITY_START" and r["process"] == "B" \
                    and r["effective_attempt_no"] == 2:
                r["event_time"] = "13/6"
                r["attempt_start_time"] = "13/6"
                r["attempt_end_time"] = "25/6"
        report = self.check("F3", event_log=log)
        self.assertEqual(report.verdict, "FAIL", "start offset must be caught")
        locations = {i.location for i in report.issues}
        self.assertTrue(any("task(1,B,2)" in loc for loc in locations), locations)

        # --- (b) delete one record -------------------------------------------
        result = self.run_fixture("F3")
        log = [r for r in result.event_log
               if not (r["event_type"] == "OBSERVATION_MATERIALIZED"
                       and r["process"] == "B" and r["effective_attempt_no"] == 1)]
        report = self.check("F3", event_log=log)
        self.assertEqual(report.verdict, "FAIL", "deleted record must be caught")
        self.assertTrue(any(i.location.startswith("record[") for i in report.issues),
                        [i.describe() for i in report.issues[:8]])

        # --- (c) tamper outcome PASS -> ABNORMAL ------------------------------
        result = self.run_fixture("F3")
        log = clone(result.event_log)
        for r in log:
            if r["event_type"] == "OBSERVATION_MATERIALIZED" \
                    and r["process"] == "B" and r["effective_attempt_no"] == 2:
                r["outcome"] = "ABNORMAL"
        report = self.check("F3", event_log=log)
        self.assertEqual(report.verdict, "FAIL", "outcome tamper must be caught")
        self.assertTrue(any("task(1,B,2).outcome" == i.location for i in report.issues),
                        [i.describe() for i in report.issues[:8]])

        # --- (d) tamper release_time ------------------------------------------
        result = self.run_fixture("F8")
        log = clone(result.event_log)
        for r in log:
            if r["event_type"] == "TASK_RELEASE" and r.get("task_id") == "D003_B_2":
                r["release_time"] = "9"
        report = self.check("F8", event_log=log)
        self.assertEqual(report.verdict, "FAIL", "release_time tamper must be caught")
        locations = {i.location for i in report.issues}
        self.assertTrue("task(3,B,2).release_time" in locations, locations)
        self.assertTrue(any(i.check_id == "C08" for i in report.issues),
                        "K9 release assertion must also fail")

        # --- (e) tamper attempt number 1 -> 2 ----------------------------------
        result = self.run_fixture("F8")
        log = clone(result.event_log)
        for r in log:
            if r["event_type"] == "OBSERVATION_MATERIALIZED" \
                    and r.get("device_id") == 3 and r["process"] == "B" \
                    and r["effective_attempt_no"] == 1:
                r["effective_attempt_no"] = 2
        report = self.check("F8", event_log=log)
        self.assertEqual(report.verdict, "FAIL", "attempt tamper must be caught")
        locations = {i.location for i in report.issues}
        self.assertTrue(any("device(3).B" in loc or "task(3,B,2)" in loc for loc in locations),
                        locations)

    # ------------------------------------------------------------------
    # 10. Checker isolation (CR-V3.1/C19): static + dynamic
    # ------------------------------------------------------------------
    def test_10_checker_isolation(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for mod in imported:
            self.assertFalse(mod.startswith("main_model"),
                             "checker imports main_model: %s" % mod)
            self.assertFalse(mod.startswith("des"),
                             "checker imports the DES package: %s" % mod)
            self.assertFalse(mod.startswith("tests"),
                             "checker imports test code: %s" % mod)
            self.assertFalse(mod.startswith("checker"),
                             "checker imports another checker module: %s" % mod)
        for banned in ("deterministic_des_v1", "state_models_v1", "subprocess"):
            self.assertNotIn(banned, source,
                             "checker source mentions a forbidden module: %s" % banned)

        # dynamic: run the CLI in a subprocess whose PYTHONPATH contains ONLY
        # the checker directory (main_model is not importable there)
        fixture = self.fixture("F1")
        result = self.run_fixture("F1")
        with tempfile.TemporaryDirectory(prefix="g2_04_isolation_") as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "event_log.json").write_text(
                json.dumps(result.event_log, ensure_ascii=False), encoding="utf-8")
            (tmp_path / "config.json").write_text(
                json.dumps(fixture["config"], ensure_ascii=False), encoding="utf-8")
            (tmp_path / "fixture.json").write_text(
                json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            (tmp_path / "metrics.json").write_text(
                json.dumps(result.metrics, ensure_ascii=False), encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(CHECKER_DIR)
            proc = subprocess.run(
                [sys.executable, str(CHECKER_PATH),
                 "--event-log", str(tmp_path / "event_log.json"),
                 "--config", str(tmp_path / "config.json"),
                 "--fixture", str(tmp_path / "fixture.json"),
                 "--parameters", str(PARAMETERS_PATH),
                 "--metrics", str(tmp_path / "metrics.json")],
                cwd=tmp, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0,
                             "checker CLI failed without the main engine:\n%s\n%s"
                             % (proc.stdout, proc.stderr))
            self.assertIn('"verdict": "PASS"', proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)

    # ------------------------------------------------------------------
    # 11. Empty / incomplete / gapped event_logs must explicitly FAIL
    # ------------------------------------------------------------------
    def test_11_empty_and_incomplete_logs_fail(self) -> None:
        fixture = self.fixture("F1")
        # empty log
        report = chk.check_event_log([], fixture["config"], fixture,
                                     parameters=str(PARAMETERS_PATH))
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(any("empty" in i.message.lower() for i in report.issues),
                        [i.describe() for i in report.issues])
        # empty envelope
        report = chk.check_event_log({"records": []}, fixture["config"], fixture)
        self.assertEqual(report.verdict, "FAIL")
        # missing SIMULATION_END
        result = self.run_fixture("F1")
        log = [r for r in result.event_log if r["event_type"] != "SIMULATION_END"]
        report = chk.check_event_log(log, fixture["config"], fixture,
                                     parameters=str(PARAMETERS_PATH),
                                     metrics=result.metrics)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(any("SIMULATION_END" in i.message for i in report.issues),
                        [i.describe() for i in report.issues])
        # seq gap
        log = clone(result.event_log)
        for r in log:
            if r["seq"] == 5:
                r["seq"] = 99
        report = chk.check_event_log(log, fixture["config"], fixture,
                                     parameters=str(PARAMETERS_PATH))
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(any("seq" in i.message for i in report.issues),
                        [i.describe() for i in report.issues])

    # ------------------------------------------------------------------
    # 12. Repeated checker runs are deterministic
    # ------------------------------------------------------------------
    def test_12_repeat_determinism(self) -> None:
        for fixture_id in ("F1", "F8", "F9b", "F10"):
            first = self.check(fixture_id)
            second = self.check(fixture_id)
            self.assertEqual(json.dumps(first.to_dict(), sort_keys=True),
                             json.dumps(second.to_dict(), sort_keys=True), fixture_id)
            self.assertEqual(first.verdict, second.verdict, fixture_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
