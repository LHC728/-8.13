"""Unit tests for the G2-03 deterministic minimal parallel DES (stdlib only).

Covers the 22 frozen items: F1-F12 loadability and semantics, K9 authoritative
timeline (CR-V3.1/C08), Fraction exactness, no-float canonical time,
deterministic event order, repeat determinism, explicit MISSING_SCRIPTED_OUTCOME
failure, FCFS release-time immutability, squad exclusion from the FCFS key,
no ortools/third-party import in the main DES, and event-log field sufficiency
for an independent replay (G2-04 seam).

All expected values are read from the frozen fixture file
(des_fixtures_F1_F12_v1.json); no formal competition numbers are produced.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
PROJECT = BASE  # competitions/模拟赛_研究生A题
CODE_DIR = BASE / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from des import state_models_v1 as sm  # noqa: E402
from des import deterministic_des_v1 as de  # noqa: E402

FIXTURES_PATH = CODE_DIR / "tests/fixtures/des_fixtures_F1_F12_v1.json"
K9_AUTHORITATIVE = PROJECT / "01_审计/手算样例_K9跨班重测.md"
REQUIRED_EVENT_TYPES = {
    "ACTIVITY_START", "ACTIVITY_COMPLETE", "OBSERVATION_MATERIALIZED",
    "D_CREATED", "TASK_RELEASE", "DEVICE_TERMINAL",
    "TURNOVER_OUT_START", "TURNOVER_OUT_COMPLETE",
    "TURNOVER_IN_START", "TURNOVER_IN_COMPLETE",
    "SHIFT_CHANGE", "SIMULATION_END",
}


def frac(value: str) -> Fraction:
    return Fraction(value)


class DesMainTestCase(unittest.TestCase):
    """Shared fixture loading and run helpers."""

    fixtures: dict[str, dict]
    fixtures_order: list[str]

    @classmethod
    def setUpClass(cls) -> None:
        with open(FIXTURES_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        cls.fixtures = {f["fixture_id"]: f for f in data["fixtures"]}
        cls.fixtures_order = [f["fixture_id"] for f in data["fixtures"]]

    def fixture(self, fixture_id: str) -> dict:
        return self.fixtures[fixture_id]

    def run_fixture(self, fixture_id: str) -> de.DesRunResult:
        fixture = self.fixture(fixture_id)
        return de.run_des(fixture["config"], fixture)

    @staticmethod
    def records(log: list[dict], event_type: str) -> list[dict]:
        return [r for r in log if r["event_type"] == event_type]

    @staticmethod
    def recs_for(log: list[dict], event_type: str, **fields) -> list[dict]:
        out = []
        for r in log:
            if r["event_type"] != event_type:
                continue
            if all(r.get(key) == value for key, value in fields.items()):
                out.append(r)
        return out

    def assert_metric(self, result: de.DesRunResult, key: str, expected) -> None:
        self.assertEqual(result.metrics[key], expected, f"metrics.{key}")

    # ------------------------------------------------------------------
    # 1. F1-F12 all loadable
    # ------------------------------------------------------------------
    def test_01_all_fixtures_loadable(self) -> None:
        self.assertEqual(self.fixtures_order,
                         ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"])
        for fixture_id in self.fixtures_order:
            fixture = self.fixture(fixture_id)
            config = de.DesConfig.from_dict(fixture["config"])
            scripted = de.ScriptedFixture.from_dict(fixture)
            acceptance = fixture["acceptance"]
            for key in ("T", "S", "PL", "PW"):
                self.assertIn(key, acceptance, f"{fixture_id} acceptance missing {key}")
            self.assertIn(fixture_id, scripted.fixture_id or "", fixture_id)
            self.assertTrue(config.batch_size >= 1, fixture_id)
            self.assertFalse(config.random_enabled, fixture_id)

    # ------------------------------------------------------------------
    # 2. F1 true parallelism
    # ------------------------------------------------------------------
    def test_02_F1_true_parallelism(self) -> None:
        result = self.run_fixture("F1")
        starts = self.records(result.event_log, "ACTIVITY_START")
        t0 = [r for r in starts if r["event_time"] == "0"]
        self.assertEqual(len(t0), 3)
        self.assertEqual({r["process"] for r in t0}, {"A", "B", "C"})
        self.assertTrue(all(r["device_id"] == 1 for r in t0))
        # B completes 2.0; A/C complete 2.5
        b_complete = self.recs_for(result.event_log, "ACTIVITY_COMPLETE", process="B")[0]
        self.assertEqual(b_complete["event_time"], "2")
        ac = self.recs_for(result.event_log, "ACTIVITY_COMPLETE", process="A")
        self.assertEqual(ac[0]["event_time"], "5/2")
        # E 2.5..5.5
        e_start = self.recs_for(result.event_log, "ACTIVITY_START", process="E")[0]
        e_complete = self.recs_for(result.event_log, "ACTIVITY_COMPLETE", process="E")[0]
        self.assertEqual(e_start["event_time"], "5/2")
        self.assertEqual(e_complete["event_time"], "11/2")
        self.assert_metric(result, "T", "11/2")
        self.assert_metric(result, "S", 1)
        self.assert_metric(result, "PL", 0)
        self.assert_metric(result, "PW", 0)
        self.assertEqual(self.records(result.event_log, "TURNOVER_OUT_START"), [])

    # ------------------------------------------------------------------
    # 3. F2 capacity + FCFS
    # ------------------------------------------------------------------
    def test_03_F2_capacity_and_fcfs(self) -> None:
        result = self.run_fixture("F2")
        starts = self.records(result.event_log, "ACTIVITY_START")
        for resource, expected in {
            "A": [(1, "0"), (2, "5/2")],
            "B": [(1, "0"), (2, "2")],
            "C": [(1, "0"), (2, "5/2")],
            "E": [(1, "5/2"), (2, "11/2")],
        }.items():
            seq = sorted(
                (r["device_id"], r["event_time"])
                for r in starts
                if r["resource_id"] == resource
            )
            self.assertEqual(seq, expected, f"resource {resource}")
        self.assert_metric(result, "T", "17/2")
        self.assert_metric(result, "S", 2)

    # ------------------------------------------------------------------
    # 4. F3 retest semantics
    # ------------------------------------------------------------------
    def test_04_F3_retest(self) -> None:
        result = self.run_fixture("F3")
        # A first abnormal at 2.5
        obs_a1 = self.recs_for(result.event_log, "OBSERVATION_MATERIALIZED",
                               process="A", effective_attempt_no=1)[0]
        self.assertEqual(obs_a1["event_time"], "5/2")
        self.assertEqual(obs_a1["outcome"], "ABNORMAL")
        # A retest released at 2.5 with attempt 2 and release_time 2.5
        rel = self.recs_for(result.event_log, "TASK_RELEASE", process="A",
                            effective_attempt_no=2)[0]
        self.assertEqual(rel["event_time"], "5/2")
        self.assertEqual(rel["release_time"], "5/2")
        # A retest PASS at 5.0
        obs_a2 = self.recs_for(result.event_log, "OBSERVATION_MATERIALIZED",
                               process="A", effective_attempt_no=2)[0]
        self.assertEqual(obs_a2["event_time"], "5")
        self.assertEqual(obs_a2["outcome"], "PASS")
        # B/C not cancelled; E only after A PASSED
        self.assertEqual(self.records(result.event_log, "TASK_CANCEL"), [])
        e_start = self.recs_for(result.event_log, "ACTIVITY_START", process="E")[0]
        self.assertEqual(e_start["event_time"], "5")
        self.assert_metric(result, "T", "8")
        self.assert_metric(result, "S", 1)

    # ------------------------------------------------------------------
    # 5. F4 same-tick settlement before exit
    # ------------------------------------------------------------------
    def test_05_F4_same_tick_settle_before_exit(self) -> None:
        result = self.run_fixture("F4")
        # device1 EXITED at 6.0 via B second abnormal
        terminal = self.recs_for(result.event_log, "DEVICE_TERMINAL", device_id=1)[0]
        self.assertEqual(terminal["event_time"], "6")
        self.assertEqual(terminal["terminal_state"], "EXITED")
        self.assertEqual(terminal["terminal_reason"], "process_second_abnormal")
        # A/C retests cancelled at 6.0: outcome NONE, elapsed 1h, attempt unchanged
        for process in ("A", "C"):
            cancels = self.recs_for(result.event_log, "TASK_CANCEL",
                                    device_id=1, process=process,
                                    effective_attempt_no=2)
            self.assertEqual(len(cancels), 1, process)
            self.assertEqual(cancels[0]["event_time"], "6")
            self.assertEqual(cancels[0]["cancel_reason"], "DEVICE_EXIT")
            self.assertEqual(cancels[0]["outcome"], "NONE")
            self.assertEqual(cancels[0]["elapsed_hours"], "1")
            # no completion / observation for the cancelled fragments
            self.assertEqual(
                self.recs_for(result.event_log, "ACTIVITY_COMPLETE",
                              device_id=1, process=process,
                              effective_attempt_no=2), [],
                f"cancelled {process} retest must not complete")
        # device2 results preserved; E completes PASS at 8.0
        e_obs = self.recs_for(result.event_log, "OBSERVATION_MATERIALIZED",
                              device_id=2, process="E")[0]
        self.assertEqual(e_obs["event_time"], "8")
        self.assertEqual(e_obs["outcome"], "PASS")
        self.assert_metric(result, "T", "8")
        self.assert_metric(result, "S", 1)
        self.assert_metric(result, "PW", 1)

    # ------------------------------------------------------------------
    # 6. F5 D not_created
    # ------------------------------------------------------------------
    def test_06_F5_d_not_created(self) -> None:
        result = self.run_fixture("F5")
        self.assertEqual(self.records(result.event_log, "D_CREATED"), [])
        summary = result.summary["devices"]["1"]
        self.assertEqual(summary["d_state"], "not_created")
        self.assertEqual(summary["terminal_state"], "EXITED")
        self.assertEqual(summary["exit_reason"], "process_second_abnormal")
        self.assert_metric(result, "T", "5")
        self.assert_metric(result, "S", 0)
        self.assert_metric(result, "PW", 1)

    # ------------------------------------------------------------------
    # 7. F6 shift-end ban
    # ------------------------------------------------------------------
    def test_07_F6_shift_end_ban(self) -> None:
        result = self.run_fixture("F6")
        rel = self.recs_for(result.event_log, "TASK_RELEASE", process="E",
                            effective_attempt_no=2)[0]
        self.assertEqual(rel["event_time"], "8")
        self.assertEqual(rel["release_time"], "8")
        e2_starts = self.recs_for(result.event_log, "ACTIVITY_START", process="E",
                                  effective_attempt_no=2)
        self.assertEqual(len(e2_starts), 1)
        self.assertEqual(e2_starts[0]["event_time"], "9")  # not 8: 8+3 > 9
        self.assertEqual(e2_starts[0]["squad_id"], 2)
        e2_obs = self.recs_for(result.event_log, "OBSERVATION_MATERIALIZED",
                               process="E", effective_attempt_no=2)[0]
        self.assertEqual(e2_obs["event_time"], "12")
        self.assertEqual(e2_obs["outcome"], "PASS")
        self.assert_metric(result, "T", "12")

    # ------------------------------------------------------------------
    # 8. F7 exactly-at-shift-end allowed
    # ------------------------------------------------------------------
    def test_08_F7_exact_shift_end_allowed(self) -> None:
        result = self.run_fixture("F7")
        # device2 A/C start 6.5, complete exactly 9.0
        d2a_start = self.recs_for(result.event_log, "ACTIVITY_START",
                                  device_id=2, process="A")[0]
        self.assertEqual(d2a_start["event_time"], "13/2")
        d2a_obs = self.recs_for(result.event_log, "OBSERVATION_MATERIALIZED",
                                device_id=2, process="A")[0]
        self.assertEqual(d2a_obs["event_time"], "9")
        self.assertEqual(d2a_obs["outcome"], "PASS")
        # settle before shift change (seq ordering)
        shift = self.records(result.event_log, "SHIFT_CHANGE")[1]  # second shift change (9.0)
        self.assertEqual(shift["event_time"], "9")
        self.assertEqual(shift["on_duty_squad"], 2)
        self.assertLess(d2a_obs["seq"], shift["seq"])
        # E starts at 9.0 in shift 2
        d2e_start = self.recs_for(result.event_log, "ACTIVITY_START",
                                  device_id=2, process="E")[0]
        self.assertEqual(d2e_start["event_time"], "9")
        self.assert_metric(result, "T", "12")
        self.assert_metric(result, "S", 2)

    # ------------------------------------------------------------------
    # 9. F8 K9 authoritative timeline
    # ------------------------------------------------------------------
    def test_09_F8_K9_authoritative_timeline(self) -> None:
        # The authoritative hand-timeline file must exist and be referenced.
        self.assertTrue(K9_AUTHORITATIVE.exists(),
                        f"K9 authoritative file missing: {K9_AUTHORITATIVE}")
        result = self.run_fixture("F8")
        log = result.event_log
        self.assert_metric(result, "T", "14")
        self.assert_metric(result, "S", 3)
        self.assert_metric(result, "PL", 0)
        self.assert_metric(result, "PW", 0)
        self.assert_metric(result, "YXB_A", "5/12")   # 7.5/18
        self.assert_metric(result, "YXB_B", "4/9")    # 8/18
        self.assert_metric(result, "YXB_C", "5/12")   # 7.5/18
        self.assert_metric(result, "YXB_E", "1/2")    # 9/18
        self.assert_metric(result, "yxb_denominator_h", "18")

        # device1: B [0,2), A/C [0,2.5), E [2.5,5.5) -> terminal 5.5
        self.assertEqual(
            self.recs_for(log, "ACTIVITY_START", device_id=1, process="B")[0]["event_time"], "0")
        self.assertEqual(
            self.recs_for(log, "ACTIVITY_COMPLETE", device_id=1, process="B")[0]["event_time"], "2")
        self.assertEqual(
            self.recs_for(log, "ACTIVITY_START", device_id=1, process="E")[0]["event_time"], "5/2")
        self.assertEqual(
            self.recs_for(log, "ACTIVITY_COMPLETE", device_id=1, process="E")[0]["event_time"], "11/2")
        term1 = self.recs_for(log, "DEVICE_TERMINAL", device_id=1)[0]
        self.assertEqual((term1["event_time"], term1["terminal_state"]), ("11/2", "PASSED"))

        # bay1 turnover [5.5,6.5) 1h literal
        out_start = self.recs_for(log, "TURNOVER_OUT_START", bay_id=1)[0]
        self.assertEqual(out_start["event_time"], "11/2")
        self.assertEqual(self.recs_for(log, "TURNOVER_OUT_COMPLETE", bay_id=1)[0]["event_time"], "6")
        self.assertEqual(self.recs_for(log, "TURNOVER_IN_START", bay_id=1)[0]["event_time"], "6")
        self.assertEqual(self.recs_for(log, "TURNOVER_IN_COMPLETE", bay_id=1)[0]["event_time"], "13/2")

        # device2: E [5.5,8.5) released at 5.0, terminal 8.5; bay2 no turnover
        self.assertEqual(
            self.recs_for(log, "TASK_RELEASE", device_id=2, process="E")[0]["release_time"], "5")
        self.assertEqual(
            self.recs_for(log, "ACTIVITY_START", device_id=2, process="E")[0]["event_time"], "11/2")
        term2 = self.recs_for(log, "DEVICE_TERMINAL", device_id=2)[0]
        self.assertEqual((term2["event_time"], term2["terminal_state"]), ("17/2", "PASSED"))
        self.assertEqual(self.recs_for(log, "TURNOVER_OUT_START", bay_id=2), [])

        # device3 enters at 6.5; A/C [6.5,9.0), B initial [6.5,8.5) ABNORMAL
        for proc in ("A", "B", "C"):
            self.assertEqual(
                self.recs_for(log, "TASK_RELEASE", device_id=3, process=proc)[0]["release_time"],
                "13/2")
            self.assertEqual(
                self.recs_for(log, "ACTIVITY_START", device_id=3, process=proc)[0]["event_time"],
                "13/2")
        self.assertEqual(
            self.recs_for(log, "OBSERVATION_MATERIALIZED", device_id=3, process="B",
                          effective_attempt_no=1)[0]["outcome"], "ABNORMAL")

        # B retest: release 8.5 (17/2), attempt 2, constant release_time, no start at 8.5
        b_rel = self.recs_for(log, "TASK_RELEASE", device_id=3, process="B",
                              effective_attempt_no=2)
        self.assertEqual(len(b_rel), 1)
        self.assertEqual(b_rel[0]["event_time"], "17/2")
        self.assertEqual(b_rel[0]["release_time"], "17/2")
        b2_starts = self.recs_for(log, "ACTIVITY_START", device_id=3, process="B",
                                  effective_attempt_no=2)
        self.assertEqual(len(b2_starts), 1)
        self.assertEqual(b2_starts[0]["event_time"], "9")  # not 8.5: 8.5+2 > 9
        self.assertEqual(b2_starts[0]["squad_id"], 2)     # executed by squad 2
        self.assertEqual(b2_starts[0]["release_time"], "17/2")  # key kept across shift
        b2_obs = self.recs_for(log, "OBSERVATION_MATERIALIZED", device_id=3, process="B",
                               effective_attempt_no=2)[0]
        self.assertEqual((b2_obs["event_time"], b2_obs["outcome"]), ("11", "PASS"))

        # A/C complete at 9.0 settled BEFORE shift change (not cancelled by shift)
        for proc in ("A", "C"):
            obs = self.recs_for(log, "OBSERVATION_MATERIALIZED", device_id=3,
                                process=proc, effective_attempt_no=1)[0]
            self.assertEqual(obs["event_time"], "9")
            self.assertEqual(obs["outcome"], "PASS")
        shift_at_9 = [r for r in self.records(log, "SHIFT_CHANGE") if r["event_time"] == "9"]
        self.assertEqual(len(shift_at_9), 1)
        self.assertEqual(shift_at_9[0]["on_duty_squad"], 2)
        for proc in ("A", "C"):
            obs = self.recs_for(log, "OBSERVATION_MATERIALIZED", device_id=3,
                                process=proc, effective_attempt_no=1)[0]
            self.assertLess(obs["seq"], shift_at_9[0]["seq"])

        # E 11..14, terminal 14, SIMULATION_END 14
        self.assertEqual(
            self.recs_for(log, "ACTIVITY_START", device_id=3, process="E")[0]["event_time"], "11")
        self.assertEqual(
            self.recs_for(log, "ACTIVITY_COMPLETE", device_id=3, process="E")[0]["event_time"], "14")
        term3 = self.recs_for(log, "DEVICE_TERMINAL", device_id=3)[0]
        self.assertEqual((term3["event_time"], term3["terminal_state"]), ("14", "PASSED"))
        end = self.records(log, "SIMULATION_END")
        self.assertEqual(len(end), 1)
        self.assertEqual(end[0]["event_time"], "14")

        # device3 B retest release_time is never rewritten: only one TASK_RELEASE,
        # and the ACTIVITY_START at 9.0 still carries release_time 8.5.
        self.assertEqual(result.summary["bays"]["2"]["status"],
                         "TERMINAL_OCCUPIED_UNTIL_STOP")

    # ------------------------------------------------------------------
    # 10. F9 1h literal turnover
    # ------------------------------------------------------------------
    def test_10_F9_turnover_1h(self) -> None:
        result = self.run_fixture("F9")
        log = result.event_log
        self.assertEqual(self.recs_for(log, "TURNOVER_OUT_START", bay_id=1)[0]["event_time"], "11/2")
        self.assertEqual(self.recs_for(log, "TURNOVER_OUT_COMPLETE", bay_id=1)[0]["event_time"], "6")
        self.assertEqual(self.recs_for(log, "TURNOVER_IN_START", bay_id=1)[0]["event_time"], "6")
        self.assertEqual(self.recs_for(log, "TURNOVER_IN_COMPLETE", bay_id=1)[0]["event_time"], "13/2")
        # no test activity on bay 1 during (5.5, 6.5)
        for r in self.records(log, "ACTIVITY_START"):
            if r["bay_id"] == 1 and "11/2" < r["event_time"] < "13/2":
                self.fail(f"test started on bay 1 during turnover: {r}")
        # device2 enters at 6.5
        self.assertEqual(
            self.recs_for(log, "TASK_RELEASE", device_id=2, process="A")[0]["release_time"], "13/2")
        self.assert_metric(result, "T", "12")
        self.assert_metric(result, "S", 2)

    # ------------------------------------------------------------------
    # 11. F10 0.5h overlap turnover (isolated profile)
    # ------------------------------------------------------------------
    def test_11_F10_turnover_overlap(self) -> None:
        result = self.run_fixture("F10")
        log = result.event_log
        self.assertEqual(result.config.turnover_profile, "0.5h_overlap")
        self.assertEqual(self.recs_for(log, "TURNOVER_OUT_START", bay_id=1)[0]["event_time"], "11/2")
        for event_type in ("TURNOVER_OUT_COMPLETE", "TURNOVER_IN_START", "TURNOVER_IN_COMPLETE"):
            self.assertEqual(self.recs_for(log, event_type, bay_id=1)[0]["event_time"], "6")
        # device2 enters at 6.0
        self.assertEqual(
            self.recs_for(log, "TASK_RELEASE", device_id=2, process="A")[0]["release_time"], "6")
        self.assert_metric(result, "T", "23/2")
        self.assert_metric(result, "S", 2)
        # profile isolation vs F9 (manifest separation)
        self.assertEqual(self.run_fixture("F9").config.turnover_profile, "1h_literal")

    # ------------------------------------------------------------------
    # 12. F11 liveness wake-up
    # ------------------------------------------------------------------
    def test_12_F11_liveness_wakeup(self) -> None:
        result = self.run_fixture("F11")
        wake = self.records(result.event_log, "WAKE_UP")
        self.assertEqual(len(wake), 1)
        self.assertEqual(wake[0]["event_time"], "9")
        e2_start = self.recs_for(result.event_log, "ACTIVITY_START", process="E",
                                 effective_attempt_no=2)[0]
        self.assertEqual(e2_start["event_time"], "9")
        self.assert_metric(result, "T", "12")
        times = [frac(r["event_time"]) for r in result.event_log]
        self.assertTrue(all(times[i] <= times[i + 1] for i in range(len(times) - 1)))
        self.assertEqual(len({frac(r["event_time"]) for r in result.event_log}), len(set(times)))

    # ------------------------------------------------------------------
    # 13. F12 no terminal turnover
    # ------------------------------------------------------------------
    def test_13_F12_no_terminal_turnover(self) -> None:
        result = self.run_fixture("F12")
        log = result.event_log
        turnover_types = [t for t in ("TURNOVER_OUT_START", "TURNOVER_OUT_COMPLETE",
                                      "TURNOVER_IN_START", "TURNOVER_IN_COMPLETE")
                          if self.records(log, t)]
        self.assertEqual(turnover_types, [])
        end = self.records(log, "SIMULATION_END")[0]
        self.assertEqual(end["event_time"], "11/2")
        self.assertEqual(result.summary["bays"]["1"]["status"],
                         "TERMINAL_OCCUPIED_UNTIL_STOP")
        self.assert_metric(result, "T", "11/2")
        self.assert_metric(result, "S", 1)

    # ------------------------------------------------------------------
    # 14. Fraction exactness (including non-dyadic 1/6-hour times)
    # ------------------------------------------------------------------
    def test_14_fraction_exactness(self) -> None:
        # synthetic: all durations 1/6 h -> T = 2/6 = 1/3, an exact non-dyadic value
        config = {
            "schema_version": "des_config_v1",
            "scenario_id": "synthetic_16h",
            "scenario": "isolated_small_case",
            "batch_size": 1,
            "shift_length_h": "1000000",
            "shifts_per_day": 1,
            "durations": {"A": "1/6", "B": "1/6", "C": "1/6", "E": "1/6"},
            "transport_out_h": "0.5",
            "transport_in_h": "0.5",
            "turnover_profile": "1h_literal",
            "deterministic_initial_state": {"preloaded_devices": [1], "all_calibrated": True,
                                            "queues_empty": True},
            "random_enabled": False,
            "key_schema_version": "key_schema_v1",
        }
        scripted = {
            "fixture_id": "synthetic_16h",
            "scripted_real_states": {"1": {"A": "normal", "B": "normal", "C": "normal", "D": "normal"}},
            "scripted_outcomes": [
                {"device_id": 1, "process": "A", "effective_attempt_no": 1, "outcome": "PASS"},
                {"device_id": 1, "process": "B", "effective_attempt_no": 1, "outcome": "PASS"},
                {"device_id": 1, "process": "C", "effective_attempt_no": 1, "outcome": "PASS"},
                {"device_id": 1, "process": "E", "effective_attempt_no": 1, "outcome": "PASS"},
            ],
        }
        result = de.run_des(config, scripted)
        self.assert_metric(result, "T", "1/3")
        e_complete = self.recs_for(result.event_log, "ACTIVITY_COMPLETE", process="E")[0]
        self.assertEqual(frac(e_complete["event_time"]), Fraction(1, 3))
        # F8 ledger: exact sums
        result8 = self.run_fixture("F8")
        ledger = result8.summary["ledger_elapsed_h"]
        self.assertEqual(ledger["A"], "15/2")
        self.assertEqual(ledger["B"], "8")
        self.assertEqual(ledger["C"], "15/2")
        self.assertEqual(ledger["E"], "9")

    # ------------------------------------------------------------------
    # 15. No float canonical time
    # ------------------------------------------------------------------
    def test_15_no_float_canonical_time(self) -> None:
        time_fields = {"event_time", "attempt_start_time", "attempt_end_time",
                       "release_time", "elapsed_hours", "shift_start", "shift_end"}
        for fixture_id in self.fixtures_order:
            result = self.run_fixture(fixture_id)
            for record in result.event_log:
                for key, value in record.items():
                    self.assertFalse(
                        isinstance(value, float),
                        f"{fixture_id}: float value in log field {key}")
                    if key in time_fields:
                        self.assertIsInstance(value, str, f"{fixture_id}: {key}")
                        frac(value)  # must parse exactly
        # engine internals are Fractions, never floats
        fixture = self.fixture("F8")
        engine = de.DeterministicDesEngine(
            de.DesConfig.from_dict(fixture["config"]),
            de.ScriptedFixture.from_dict(fixture),
        )
        engine.run()
        self.assertIsInstance(engine.now, Fraction)
        # source hygiene: no third-party / float-time constructs in the DES modules
        for module_file in (MAIN_MODEL / "des/deterministic_des_v1.py",
                            MAIN_MODEL / "des/state_models_v1.py"):
            source = module_file.read_text(encoding="utf-8").lower()
            for banned in ("ortools", "numpy", "pandas", "scipy", "simpy",
                           "networkx", "import random", "from random"):
                self.assertNotIn(banned, source, f"{module_file.name} contains {banned}")

    # ------------------------------------------------------------------
    # 16. Deterministic event order
    # ------------------------------------------------------------------
    def test_16_deterministic_event_order(self) -> None:
        for fixture_id in self.fixtures_order:
            result = self.run_fixture(fixture_id)
            seqs = [r["seq"] for r in result.event_log]
            self.assertEqual(seqs, list(range(1, len(seqs) + 1)), fixture_id)
            times = [frac(r["event_time"]) for r in result.event_log]
            for i in range(len(times) - 1):
                self.assertLessEqual(times[i], times[i + 1], fixture_id)

    # ------------------------------------------------------------------
    # 17. Repeat determinism (byte-identical logs and metrics)
    # ------------------------------------------------------------------
    def test_17_repeat_determinism(self) -> None:
        for fixture_id in self.fixtures_order:
            first = self.run_fixture(fixture_id)
            second = self.run_fixture(fixture_id)
            self.assertEqual(
                json.dumps(first.event_log, ensure_ascii=False, sort_keys=False),
                json.dumps(second.event_log, ensure_ascii=False, sort_keys=False),
                fixture_id)
            self.assertEqual(first.metrics, second.metrics, fixture_id)

    # ------------------------------------------------------------------
    # 18. Missing scripted outcome -> explicit FAIL
    # ------------------------------------------------------------------
    def test_18_missing_scripted_outcome(self) -> None:
        fixture = self.fixture("F1")
        scripted = dict(fixture)
        scripted["scripted_outcomes"] = [
            item for item in fixture["scripted_outcomes"]
            if not (item["process"] == "B" and item["effective_attempt_no"] == 1)
        ]
        with self.assertRaises(de.MissingScriptedOutcome) as ctx:
            de.run_des(fixture["config"], scripted)
        self.assertEqual(ctx.exception.device_id, 1)
        self.assertEqual(ctx.exception.process, "B")
        self.assertEqual(ctx.exception.attempt_no, 1)
        self.assertIn("MISSING_SCRIPTED_OUTCOME", str(ctx.exception))

    # ------------------------------------------------------------------
    # 19. FCFS release_time immutable
    # ------------------------------------------------------------------
    def test_19_fcfs_release_time_immutable(self) -> None:
        result = self.run_fixture("F8")
        log = result.event_log
        rel = self.recs_for(log, "TASK_RELEASE", device_id=3, process="B",
                            effective_attempt_no=2)
        self.assertEqual(len(rel), 1)
        self.assertEqual(rel[0]["release_time"], "17/2")
        # every record carrying a release_time for this task keeps 8.5
        for record in log:
            if record.get("task_id") == "D003_B_2" and "release_time" in record:
                self.assertEqual(record["release_time"], "17/2", record)
        # no release at 9.0 (not rewritten at the shift change)
        for record in log:
            if record["event_type"] == "TASK_RELEASE" and record.get("task_id") == "D003_B_2":
                self.assertEqual(record["event_time"], "17/2")

    # ------------------------------------------------------------------
    # 20. squad_id excluded from FCFS key
    # ------------------------------------------------------------------
    def test_20_squad_excluded_from_fcfs(self) -> None:
        # the frozen key constructor takes exactly (release_time, device_id,
        # process, attempt_no); squad_id / execution_no / restart_no are not
        # parameters and never enter the key
        key_a = de.make_fcfs_key(Fraction("17/2"), 3, "B", 2)
        self.assertEqual(key_a, (Fraction(17, 2), 3, 1, 2))
        self.assertEqual(len(key_a), 4)
        self.assertEqual(de.make_fcfs_key(Fraction(0), 2, "A", 1),
                         (Fraction(0), 2, 0, 1))
        # log-level reconstruction for F8: every started task's key is exactly
        # the 4-tuple built from release_time/device/process_order/attempt
        result = self.run_fixture("F8")
        log = result.event_log
        for r in self.records(log, "ACTIVITY_START"):
            reconstructed = de.make_fcfs_key(
                frac(r["release_time"]), r["device_id"], r["process"],
                r["effective_attempt_no"])
            self.assertEqual(len(reconstructed), 4)
            self.assertIsInstance(reconstructed[0], Fraction)
        # D003_B_2 (squad 2 execution at 9.0) keeps the frozen key built at
        # release 8.5: no squad component, no jump (K9 hard assertion 3)
        b2 = self.recs_for(log, "ACTIVITY_START", device_id=3, process="B",
                           effective_attempt_no=2)[0]
        self.assertEqual(de.make_fcfs_key(frac(b2["release_time"]), 3, "B", 2),
                         (Fraction(17, 2), 3, 1, 2))
        self.assertEqual(b2["squad_id"], 2)

    # ------------------------------------------------------------------
    # 21. No ortools import in the main DES
    # ------------------------------------------------------------------
    def test_21_no_ortools_import(self) -> None:
        for module_file in (MAIN_MODEL / "des/deterministic_des_v1.py",
                            MAIN_MODEL / "des/state_models_v1.py"):
            source = module_file.read_text(encoding="utf-8")
            self.assertNotIn("ortools", source.lower())
            self.assertNotIn("cp_model", source)
            self.assertNotIn("import random", source)
            self.assertNotIn("from random", source)

    # ------------------------------------------------------------------
    # 22. event_log core field sufficiency (G2-04 replay seam)
    # ------------------------------------------------------------------
    def test_22_event_log_core_field_sufficiency(self) -> None:
        result = self.run_fixture("F8")
        log = result.event_log
        present = {r["event_type"] for r in log}
        self.assertTrue(REQUIRED_EVENT_TYPES.issubset(present), present)
        # per-type structural requirements
        for r in self.records(log, "ACTIVITY_START"):
            for field in ("device_id", "process", "effective_attempt_no",
                          "resource_id", "bay_id", "squad_id",
                          "attempt_start_time", "attempt_end_time", "release_time"):
                self.assertIn(field, r)
        for r in self.records(log, "TASK_RELEASE"):
            self.assertIn("release_time", r)
        for r in self.records(log, "ACTIVITY_COMPLETE"):
            for field in ("elapsed_hours", "attempt_start_time", "attempt_end_time"):
                self.assertIn(field, r)
        for r in self.records(log, "TASK_CANCEL"):
            self.assertIn("cancel_reason", r)
        for r in self.records(log, "D_CREATED"):
            self.assertIn("d_state", r)
        for r in self.records(log, "DEVICE_TERMINAL"):
            self.assertIn("terminal_state", r)
        for r in self.records(log, "SHIFT_CHANGE"):
            for field in ("shift_start", "shift_end", "on_duty_squad"):
                self.assertIn(field, r)

        # independent recompute smoke test (log only, no state machine):
        # (a) per-process elapsed = sum of elapsed_hours over complete+cancel records
        elapsed: dict[str, Fraction] = {p: Fraction(0) for p in ("A", "B", "C", "E")}
        for r in log:
            if r["event_type"] in ("ACTIVITY_COMPLETE", "TASK_CANCEL") and r.get("process"):
                elapsed[r["process"]] += frac(r["elapsed_hours"])
        ledger = result.summary["ledger_elapsed_h"]
        denominator = frac(result.metrics["yxb_denominator_h"])
        for process in ("A", "B", "C", "E"):
            self.assertEqual(sm.fraction_to_string(elapsed[process]), ledger[process], process)
            # YXB seam: elapsed / (shift_count * shift_length) == metrics.YXB_<p>
            self.assertEqual(sm.fraction_to_string(elapsed[process] / denominator),
                             result.metrics["YXB_" + process], process)
        # (b) T = SIMULATION_END time = last DEVICE_TERMINAL time
        end = self.records(log, "SIMULATION_END")[0]
        self.assertEqual(end["event_time"], result.metrics["T"])
        last_term = max(frac(r["event_time"]) for r in self.records(log, "DEVICE_TERMINAL"))
        self.assertEqual(sm.fraction_to_string(last_term), result.metrics["T"])
        # (c) attempt monotonicity per (device, process): 1 before 2
        for r in self.records(log, "OBSERVATION_MATERIALIZED"):
            if r["effective_attempt_no"] == 2:
                first = self.recs_for(log, "OBSERVATION_MATERIALIZED",
                                      device_id=r["device_id"], process=r["process"],
                                      effective_attempt_no=1)
                self.assertEqual(len(first), 1)
                self.assertLess(first[0]["seq"], r["seq"])
        # (d) bay occupancy coverage: for every bay hosting devices, the union
        #     of device residency intervals [entry, terminal-or-T) and turnover
        #     intervals covers [0, T) without gaps or overlaps.
        device_entries: dict[int, Fraction] = {}
        device_terminals: dict[int, Fraction] = {}
        device_bay: dict[int, int] = {}
        for r in log:
            if r["event_type"] == "TASK_RELEASE" and r.get("process") == "A":
                device_entries[r["device_id"]] = frac(r["release_time"])
            if r["event_type"] == "DEVICE_TERMINAL":
                device_terminals[r["device_id"]] = frac(r["event_time"])
            if r["event_type"] == "ACTIVITY_START" and r.get("device_id") is not None:
                device_bay.setdefault(r["device_id"], r["bay_id"])
        turnover_out_by_bay: dict[int, list[Fraction]] = {}
        for r in log:
            if r["event_type"] == "TURNOVER_OUT_START":
                turnover_out_by_bay.setdefault(r["bay_id"], []).append(frac(r["event_time"]))

        def bay_intervals(bay_id: int) -> list[tuple[Fraction, Fraction]]:
            intervals: list[tuple[Fraction, Fraction]] = []
            for dev in sorted(d for d, b in device_bay.items() if b == bay_id):
                entry = device_entries[dev]
                term = device_terminals[dev]
                followed = any(os >= term for os in turnover_out_by_bay.get(bay_id, []))
                end = term if followed else frac(result.metrics["T"])
                intervals.append((entry, end))
            for r in log:
                if r.get("bay_id") != bay_id:
                    continue
                if r["event_type"] == "TURNOVER_OUT_START":
                    end_t = frac(self.recs_for(log, "TURNOVER_OUT_COMPLETE",
                                               bay_id=bay_id)[0]["event_time"])
                    intervals.append((frac(r["event_time"]), end_t))
                elif r["event_type"] == "TURNOVER_IN_START":
                    end_t = frac(self.recs_for(log, "TURNOVER_IN_COMPLETE",
                                               bay_id=bay_id)[0]["event_time"])
                    intervals.append((frac(r["event_time"]), end_t))
            intervals.sort()
            return intervals

        for bay_id in (1, 2):
            intervals = bay_intervals(bay_id)
            if not intervals:
                continue
            # ordered, gapless, coverage of [0, T)
            self.assertEqual(intervals[0][0], Fraction(0), f"bay {bay_id}")
            self.assertEqual(intervals[-1][1], frac(result.metrics["T"]), f"bay {bay_id}")
            for i in range(len(intervals) - 1):
                self.assertEqual(intervals[i][1], intervals[i + 1][0], f"bay {bay_id}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
