#!/usr/bin/env python3
"""Tests for Q3-H2-P1: ObservableState/PosteriorState information firewall
and the C23 P1-applicable checker (T1-T17).

Covers:
  T1  whitelist exactness
  T2  nested-object whitelist
  T3  true_state rejection
  T4  live lifetime rejection
  T5  raw u_key rejection
  T6  same observable history + different ABC hidden state
  T7  same observable history + different D hidden state
  T8  same observable history + different equipment lifetime
  T9  same observable history + different future observation/random values
  T10 event-log temporal prefix: future terminal cannot affect state(t)
  T11 future PASS cannot affect state(t)
  T12 future release/start cannot affect state(t)
  T13 deterministic ordering / serialization
  T14 no raw live-object references retained
  T15 H2 import/AST isolation
  T16 READY / running / queue / terminal observable-state boundary sanity
  T17 D materialized boolean only

Python 3.12, standard library only.
"""
from __future__ import annotations

import ast
import dataclasses
import json
import sys
import unittest
from fractions import Fraction
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as post  # noqa: E402
from checker import h2_p1_firewall_checker_v1 as chk  # noqa: E402


def _base_log() -> list[dict]:
    return chk._mk_log()


def _with_future(log: list[dict], future: list[dict]) -> list[dict]:
    out = list(log) + list(future)
    out.sort(key=lambda r: Fraction(r["event_time"]))
    return out


class TestFirewallChecker(unittest.TestCase):
    def test_checker_overall(self):
        result = chk.run_all()
        self.assertEqual(result["overall"], "PASS", result)
        self.assertEqual(
            result["full_c23_end_to_end"],
            "PENDING (action/policy path not implemented; "
            "same-observed-history action-equivalence "
            "DEFERRED_TO_POLICY_STAGE)")

    def test_t1_whitelist_exactness(self):
        res = chk.check_field_whitelist()
        self.assertEqual(res["status"], "PASS", res)
        fields = {f.name for f in dataclasses.fields(obs.ObservableState)}
        self.assertEqual(fields, chk.WHITELIST["ObservableState"])
        self.assertTrue(obs.ObservableState.__dataclass_params__.frozen)

    def test_t2_nested_object_whitelist(self):
        res = chk.check_field_whitelist()
        self.assertEqual(res["status"], "PASS")
        # nested DTO classes are all whitelisted
        for cls in chk.DTO_CLASSES:
            self.assertIn(cls.__name__, chk.WHITELIST)

    def test_t3_true_state_rejection(self):
        self.assertFalse(hasattr(obs.ObservableState, "true_state"))
        self.assertFalse(hasattr(obs.ResourceObs, "lifetime_h"))
        res = chk.check_negative_leaks()
        self.assertTrue(res["rejection_detected"]["top_level_forbidden_field"])

    def test_t4_live_lifetime_rejection(self):
        self.assertFalse(any("lifetime" in f.name for f in
                             dataclasses.fields(obs.ObservableState)))
        res = chk.check_negative_leaks()
        self.assertTrue(res["rejection_detected"]["nested_forbidden_object"])

    def test_t5_raw_ukey_rejection(self):
        self.assertFalse(any("u_key" in f.name or f.name == "u" for f in
                             dataclasses.fields(obs.ObservableState)))
        res = chk.check_negative_leaks()
        self.assertTrue(res["rejection_detected"]["raw_hidden_dict_key"])

    def test_t6_t9_same_observable_history(self):
        res = chk.check_same_observable_history(Fraction(3))
        self.assertEqual(res["status"], "PASS", res)
        self.assertEqual(len(res["pairs"]), 5)
        for p in res["pairs"]:
            self.assertTrue(p["fingerprints_equal"], p)

    def test_t10_future_terminal_ignored(self):
        base = _base_log()
        future = [{"event_type": "DEVICE_TERMINAL", "event_time": "20",
                   "device_id": 1, "terminal_state": "PASSED"}]
        t = Fraction(3)
        fp1 = obs.project_log_prefix(base, t, batch_size=2).fingerprint()
        fp2 = obs.project_log_prefix(_with_future(base, future), t,
                                     batch_size=2).fingerprint()
        self.assertEqual(fp1, fp2)
        st = obs.project_log_prefix(_with_future(base, future), t, batch_size=2)
        self.assertIsNone(st.devices[0].terminal_state)

    def test_t11_future_pass_ignored(self):
        base = _base_log()
        future = [{"event_type": "OBSERVATION_MATERIALIZED",
                   "event_time": "10", "device_id": 1, "process": "A",
                   "effective_attempt_no": 1, "resource_id": "A",
                   "outcome": "ABNORMAL"}]
        t = Fraction(3)
        fp1 = obs.project_log_prefix(base, t, batch_size=2).fingerprint()
        fp2 = obs.project_log_prefix(_with_future(base, future), t,
                                     batch_size=2).fingerprint()
        self.assertEqual(fp1, fp2)
        st = obs.project_log_prefix(_with_future(base, future), t, batch_size=2)
        self.assertEqual(len(st.devices[0].observations), 1)  # only the t=5/2 one

    def test_t12_future_release_start_ignored(self):
        base = _base_log()
        future = [{"event_type": "TASK_RELEASE", "event_time": "10",
                   "resource_id": "B", "device_id": 1, "process": "B",
                   "effective_attempt_no": 1},
                  {"event_type": "ACTIVITY_START", "event_time": "10",
                   "device_id": 1, "process": "B",
                   "effective_attempt_no": 1, "resource_id": "B",
                   "attempt_start_time": "10", "attempt_end_time": "12",
                   "outcome": "NONE"}]
        t = Fraction(3)
        fp1 = obs.project_log_prefix(base, t, batch_size=2).fingerprint()
        fp2 = obs.project_log_prefix(_with_future(base, future), t,
                                     batch_size=2).fingerprint()
        self.assertEqual(fp1, fp2)
        st = obs.project_log_prefix(_with_future(base, future), t, batch_size=2)
        self.assertTrue(all(q.process_order != 1 for q in st.queue))

    def test_t13_deterministic_ordering(self):
        log = _base_log()
        s1 = obs.project_log_prefix(log, Fraction(3), batch_size=2)
        s2 = obs.project_log_prefix(list(reversed(log)), Fraction(3),
                                    batch_size=2)
        self.assertEqual(s1.fingerprint(), s2.fingerprint())
        resources = [r.resource for r in s1.resources]
        self.assertEqual(resources, ["A", "B", "C", "E"])
        # canonical dict has no object ids / unordered keys
        d = s1.to_canonical_dict()
        self.assertIsInstance(d, dict)
        json_str = str(d)
        self.assertNotIn("0x", json_str)

    def test_t14_no_raw_live_references(self):
        s = obs.project_log_prefix(_base_log(), Fraction(3), batch_size=2)
        for f in dataclasses.fields(obs.ObservableState):
            value = getattr(s, f.name)
            self.assertFalse(isinstance(value, (list, dict)),
                             f"{f.name} must not be a mutable container")
            if value is not None and not isinstance(value, tuple):
                self.assertTrue(isinstance(value, (int, str, bool, Fraction)),
                                f"{f.name} has unexpected type {type(value)}")

    def test_t15_h2_import_ast_isolation(self):
        res = chk.check_import_isolation()
        self.assertEqual(res["status"], "PASS", res)
        res2 = chk.check_forbidden_access()
        self.assertEqual(res2["status"], "PASS", res2)

    def test_t16_boundary_sanity(self):
        # A log with: a waiting B task, an in-flight A fragment, a terminal
        # device, a queued E head.
        log = [
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 1,
             "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 2,
             "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "TASK_RELEASE", "event_time": "0",
             "resource_id": "A", "device_id": 1, "process": "A",
             "effective_attempt_no": 1},
            {"event_type": "ACTIVITY_START", "event_time": "0", "device_id": 1,
             "process": "A", "effective_attempt_no": 1, "resource_id": "A",
             "attempt_start_time": "0", "attempt_end_time": "5/2",
             "outcome": "NONE"},
            {"event_type": "TASK_RELEASE", "event_time": "1",
             "resource_id": "B", "device_id": 2, "process": "B",
             "effective_attempt_no": 1},
            {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
             "shift_start": "0", "shift_end": "10", "on_duty_squad": 0,
             "squad_id": 0},
        ]
        s = obs.project_log_prefix(log, Fraction(1), batch_size=4)
        self.assertEqual(s.remaining_not_entered, 2)  # 4 - 2 entered
        rsrc_a = next(r for r in s.resources if r.resource == "A")
        self.assertEqual(rsrc_a.status, "testing")
        self.assertEqual(rsrc_a.in_flight_remaining_h, Fraction(3, 2))
        self.assertTrue(any(q.process_order == 1 and q.device_id == 2
                            for q in s.queue))  # B waiting (FCFS order 1)
        self.assertEqual(s.active_shift, (Fraction(0), Fraction(10)))
        self.assertEqual(s.on_duty_squad, 0)

    def test_t17_d_materialized_boolean_only(self):
        s = obs.project_log_prefix(_base_log(), Fraction(3), batch_size=2)
        dev = s.devices[0]
        self.assertTrue(dev.d_materialized)  # D_CREATED at 5/2 <= 3
        self.assertIsInstance(dev.d_materialized, bool)
        self.assertFalse(any("d_state" in f.name for f in
                             dataclasses.fields(obs.DeviceObs)))

    def test_posterior_seam_no_math(self):
        res = chk.check_posterior_seam()
        self.assertEqual(res["status"], "PASS", res)
        self.assertEqual(post.P1_SEAM_STATUS, "SCHEMA_DEFERRED_TO_P2")
        self.assertFalse(res["posterior_math_detected"])
        self.assertEqual(res["numeric_placeholders_detected"], [])

    # ---- Q3-H2-P1-E1 closures: replacement-history semantics (F1) ----

    def test_t18_ongoing_replacement_not_in_completed_history(self):
        log = [
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 1,
             "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
             "shift_start": "0", "shift_end": "10", "on_duty_squad": 0,
             "squad_id": 0},
            {"event_type": "EQUIPMENT_REPLACEMENT_START", "event_time": "1",
             "resource_id": "A", "kind": "preventive", "trigger": "preventive",
             "old_generation": 1, "new_generation": 2, "age_before": "1",
             "calibration_duration_hours": "1/2", "calibration_start": "1",
             "calibration_end": "3/2", "u_key": "k_L_A_2", "u": "0.5"},
        ]
        s = obs.project_log_prefix(log, Fraction(5, 4), batch_size=2)
        self.assertEqual(len(s.replacement_history), 0)  # ongoing, not completed
        rsrc_a = next(r for r in s.resources if r.resource == "A")
        self.assertEqual(rsrc_a.status, "calibration")
        self.assertEqual(rsrc_a.in_flight_remaining_h, Fraction(1, 4))

    def test_t19_completed_replacement_enters_history(self):
        log = [
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 1,
             "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
             "shift_start": "0", "shift_end": "10", "on_duty_squad": 0,
             "squad_id": 0},
            {"event_type": "EQUIPMENT_REPLACEMENT_START", "event_time": "1",
             "resource_id": "A", "kind": "preventive", "trigger": "preventive",
             "old_generation": 1, "new_generation": 2, "age_before": "1",
             "calibration_duration_hours": "1/2", "calibration_start": "1",
             "calibration_end": "3/2", "u_key": "k_L_A_2", "u": "0.5"},
            {"event_type": "EQUIPMENT_CALIBRATION_COMPLETE",
             "event_time": "3/2", "resource_id": "A", "generation": 2,
             "calibration_start": "1", "calibration_end": "3/2"},
        ]
        s = obs.project_log_prefix(log, Fraction(2), batch_size=2)
        entries = [rh for rh in s.replacement_history
                   if rh.resource == "A"
                   and rh.calibration_end == Fraction(3, 2)]
        self.assertEqual(len(entries), 1)  # exactly once, completed
        self.assertFalse(hasattr(entries[0], "completed"))

    def test_t20_future_completion_must_not_leak(self):
        log = [
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 1,
             "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
             "shift_start": "0", "shift_end": "10", "on_duty_squad": 0,
             "squad_id": 0},
            {"event_type": "EQUIPMENT_REPLACEMENT_START", "event_time": "1",
             "resource_id": "A", "kind": "preventive", "trigger": "preventive",
             "old_generation": 1, "new_generation": 2, "age_before": "1",
             "calibration_duration_hours": "1/2", "calibration_start": "1",
             "calibration_end": "3/2", "u_key": "k_L_A_2", "u": "0.5"},
            {"event_type": "EQUIPMENT_CALIBRATION_COMPLETE",
             "event_time": "3/2", "resource_id": "A", "generation": 2,
             "calibration_start": "1", "calibration_end": "3/2"},
        ]
        s = obs.project_log_prefix(log, Fraction(5, 4), batch_size=2)
        self.assertEqual(len(s.replacement_history), 0)  # future completion

    def test_replacement_history_semantics_check(self):
        res = chk.check_replacement_history_semantics()
        self.assertEqual(res["status"], "PASS", res)

    # ---- Q3-H2-P1-E1 closures: AST detector negatives (F2 / section 7) ----

    def test_ast_negative_cases(self):
        res = chk.check_ast_negative_cases()
        self.assertEqual(res["status"], "PASS", res)
        for label, case in res["cases"].items():
            self.assertTrue(case["passed"], (label, case))
        self.assertTrue(res["cases"]["NEG-A"]["rejected"])   # rec["true_state"]
        self.assertTrue(res["cases"]["NEG-B"]["rejected"])   # rec.get("u_key")
        self.assertTrue(res["cases"]["NEG-C"]["rejected"])   # rec["lifetime_h"]
        self.assertTrue(res["cases"]["NEG-D"]["rejected"])   # device.true_state
        self.assertFalse(res["cases"]["LEGAL"]["rejected"])  # allowed keys

    def test_all_dtos_frozen(self):
        res = chk.check_field_whitelist()
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(len(res["frozen_per_class"]), len(chk.DTO_CLASSES))
        for entry in res["frozen_per_class"]:
            self.assertTrue(entry["frozen"], entry)
        for cls in chk.DTO_CLASSES:
            self.assertTrue(dataclasses.is_dataclass(cls))
            self.assertTrue(cls.__dataclass_params__.frozen)

    # ---- Q3-H2-P1-E2 closures: raw-U firewall + evidence packaging ----

    def test_t23_raw_u_subscript_rejected(self):
        tree = ast.parse("x = rec[\"u\"]")
        issues = chk._scan_forbidden(tree, "<T23>")
        self.assertTrue(len(issues) > 0, issues)
        res = chk.check_ast_negative_cases()
        self.assertTrue(res["cases"]["NEG-U1"]["rejected"])

    def test_t24_raw_u_dict_get_rejected(self):
        tree = ast.parse("x = rec.get(\"u\")")
        issues = chk._scan_forbidden(tree, "<T24>")
        self.assertTrue(len(issues) > 0, issues)
        res = chk.check_ast_negative_cases()
        self.assertTrue(res["cases"]["NEG-U2"]["rejected"])
        # legitimate keys containing the letter 'u' must NOT be rejected
        tree_legal = ast.parse("a = rec[\"outcome\"]\n"
                               "b = rec.get(\"resource_id\")\n"
                               "c = rec[\"duration\"]")
        self.assertEqual(chk._scan_forbidden(tree_legal, "<T24-legal>"), [])

    def test_t25_evidence_report_mapping_exact(self):
        import tempfile
        from scripts import run_h2_p1_firewall_v1 as rp1
        tmp = Path(tempfile.mkdtemp())
        dummy = {"overall": "PASS", "checks": [
            {"check": cid, "status": "PASS"}
            for cid in ("A_FIELD_WHITELIST", "B_FORBIDDEN_ACCESS",
                        "B_AST_NEGATIVE_CASES", "C_IMPORT_AST_ISOLATION",
                        "D_SAME_OBSERVABLE_HISTORY", "E_NEGATIVE_LEAK_TESTS",
                        "REPLACEMENT_HISTORY_SEMANTICS",
                        "POSTERIOR_STATE_P1_SEAM")]}
        trep = {"ok": True, "tests_run": 0, "failures": 0, "errors": 0}
        rp1._build_evidence(tmp, "T25", dummy, trep, [], verification=None,
                            wall_total=0.0)
        res = rp1.evidence_mapping_check(tmp)
        self.assertEqual(res["status"], "PASS", res)
        self.assertTrue((tmp / "forbidden_access_report.json").is_file())
        self.assertTrue((tmp / "ast_negative_cases_report.json").is_file())
        self.assertTrue((tmp / "import_isolation_report.json").is_file())
        self.assertTrue((tmp / "negative_leak_tests.json").is_file())
        # no fuzzy ast_import_isolation_report.json single-file overwrite
        self.assertFalse((tmp / "ast_import_isolation_report.json").exists())

    def test_t26_swapped_evidence_report_rejected(self):
        import tempfile
        from scripts import run_h2_p1_firewall_v1 as rp1
        tmp = Path(tempfile.mkdtemp())
        dummy = {"overall": "PASS", "checks": [
            {"check": cid, "status": "PASS"}
            for cid in ("A_FIELD_WHITELIST", "B_FORBIDDEN_ACCESS",
                        "B_AST_NEGATIVE_CASES", "C_IMPORT_AST_ISOLATION",
                        "D_SAME_OBSERVABLE_HISTORY", "E_NEGATIVE_LEAK_TESTS",
                        "REPLACEMENT_HISTORY_SEMANTICS",
                        "POSTERIOR_STATE_P1_SEAM")]}
        trep = {"ok": True, "tests_run": 0, "failures": 0, "errors": 0}
        rp1._build_evidence(tmp, "T26", dummy, trep, [], verification=None,
                            wall_total=0.0)
        # swap: forbidden_access_report.json now carries E_NEGATIVE_LEAK_TESTS
        swapped = {"check": "E_NEGATIVE_LEAK_TESTS", "status": "PASS"}
        (tmp / "forbidden_access_report.json").write_text(
            json.dumps(swapped), encoding="utf-8")
        res = rp1.evidence_mapping_check(tmp)
        self.assertEqual(res["status"], "FAIL", res)
        self.assertFalse(res["files"]["forbidden_access_report.json"]["ok"])
        self.assertEqual(
            res["files"]["forbidden_access_report.json"]["got"],
            "E_NEGATIVE_LEAK_TESTS")

    def test_t27_promoted_final_root_byte_identical(self):
        import tempfile
        from scripts import run_h2_p1_firewall_v1 as rp1
        staging = Path(tempfile.mkdtemp()) / "staging"
        final = Path(tempfile.mkdtemp()) / "final"
        dummy = {"overall": "PASS", "checks": [
            {"check": cid, "status": "PASS"}
            for cid in ("A_FIELD_WHITELIST", "B_FORBIDDEN_ACCESS",
                        "B_AST_NEGATIVE_CASES", "C_IMPORT_AST_ISOLATION",
                        "D_SAME_OBSERVABLE_HISTORY", "E_NEGATIVE_LEAK_TESTS",
                        "REPLACEMENT_HISTORY_SEMANTICS",
                        "POSTERIOR_STATE_P1_SEAM")]}
        trep = {"ok": True, "tests_run": 0, "failures": 0, "errors": 0}
        rp1._build_evidence(staging, "T27", dummy, trep, [],
                            verification=None, wall_total=0.0)
        promo = rp1._promote(staging, final)
        self.assertTrue(promo["ok"], promo)
        self.assertEqual(promo["sha_mismatches"], [])
        for p in staging.rglob("*"):
            if p.is_file():
                rel = p.relative_to(staging)
                self.assertTrue((final / rel).is_file())
                self.assertEqual(rp1._sha256_file(p),
                                 rp1._sha256_file(final / rel))

    def test_t28_hash_tamper_negative_path(self):
        import tempfile
        from scripts import run_h2_p1_firewall_v1 as rp1
        tmp = Path(tempfile.mkdtemp())
        dummy = {"overall": "PASS", "checks": [
            {"check": cid, "status": "PASS"}
            for cid in ("A_FIELD_WHITELIST", "B_FORBIDDEN_ACCESS",
                        "B_AST_NEGATIVE_CASES", "C_IMPORT_AST_ISOLATION",
                        "D_SAME_OBSERVABLE_HISTORY", "E_NEGATIVE_LEAK_TESTS",
                        "REPLACEMENT_HISTORY_SEMANTICS",
                        "POSTERIOR_STATE_P1_SEAM")]}
        trep = {"ok": True, "tests_run": 0, "failures": 0, "errors": 0}
        rp1._build_evidence(tmp, "T28", dummy, trep, [], verification=None,
                            wall_total=0.0)
        self.assertTrue(rp1._verify(tmp)["ok"])
        # tamper an artifact AFTER file_hashes was generated
        with open(tmp / "checks.json", "a", encoding="utf-8") as fh:
            fh.write("\n# tampered\n")
        self.assertFalse(rp1._verify(tmp)["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
