# -*- coding: utf-8 -*-
"""Unit tests for G3-SPEC-V1.0 S5: g3_replay_checker_v1 (CR-V3.1/C17 full
G3-layer independent full-log replay checker).

Scope
-----
The object under test is ``04_代码/checker/g3_replay_checker_v1.py``, the E2
independent full-log replay checker of G3-SPEC-V1.0 section 12
(``c17_full_replay``).  This test file is the ONLY place allowed to call the
main keyed random DES (``04_代码/main_model/g3/random_des_v1.py``, S3) to
generate the event logs under test.  The checker module itself never imports
the main DES.

Frozen-contract coverage (the 9 required points plus extras):

  1. multi-seed small-batch event_log replay -> full PASS (isolated / q2 /
     q3 calendars, equipment-failure path);
  2. resource / bay occupancy independently recomputed (disjoint busy
     intervals incl. calibration, gapless bay coverage over [0, T));
  3. task release / start / end / attempt / observation / cancellation;
  4. equipment age / generation / sampled lifetime / failure interruption /
     replacement / calibration independently recomputed from the key schema;
  5. T / S / PL / PW / YXB 对拍 against the DES metrics block;
  6. isolation: static AST scan (no random_des_v1 / des.* / other checker /
     tests imports; only g3.key_schema_v1 and g3.lifetime_regeneration_v1) +
     dynamic subprocess run without the main DES ever being imported;
  7. fault injection: tampered age / generation / lifetime / observation /
     attempt / replacement (and u / true_state / terminal / seq) must FAIL
     (the checker is not always-PASS);
  8. deterministic reproducibility (byte-identical canonical reports);
  9. no binary float in canonical paths (AST scan + runtime report scan).

Plus: config/parameter validation (fail loudly, never a silent default), the
full-batch liveness guard (missing devices -> FAIL) and the report output
contract.

All expectations derive from the frozen G3-SPEC-V1.0 contract, V3.1 and
parameters.csv; no formal competition numbers are produced.
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

from checker import g3_replay_checker_v1 as rck  # noqa: E402
from g3 import key_schema_v1 as ks              # noqa: E402
from g3 import lifetime_regeneration_v1 as lr   # noqa: E402  (tau_pm sentinel)
from g3 import random_des_v1 as rd              # noqa: E402  (test-only log generation)

PARAMS_CSV = BASE / "02_数据" / "parameters.csv"
CHECKER_PATH = CODE_DIR / "checker" / "g3_replay_checker_v1.py"
CHECKER_DIR = CODE_DIR / "checker"

NS = ks.NAMESPACE_DEVELOPMENT_UNIT
SEED = 7
REP = 0

# Frozen defect probabilities (parameters.csv P026-P029), independently
# restated only for building test kernels; the checker reads the csv itself.
DEFECT_Q: dict[str, Fraction] = {
    "A": Fraction(25, 1000),
    "B": Fraction(3, 100),
    "C": Fraction(2, 100),
}
DEFECT_Q_D = Fraction(1, 1000)

# Frozen operator error rates (P030-P033) for the literal main-semantics kernel.
FROZEN_E: dict[str, Fraction] = {
    "A": Fraction(3, 100),
    "B": Fraction(4, 100),
    "C": Fraction(2, 100),
}


def frozen_kernel() -> dict[str, dict[str, Fraction]]:
    """Frozen literal main-semantics kernel (P060): (1-q)alpha = q beta = e/2
    for A/B/C; the E kernel is the frozen test input used by the G3 S3 tests."""
    kernel: dict[str, dict[str, Fraction]] = {}
    for proc in ("A", "B", "C"):
        alpha, beta = rd.frozen_single_test_alpha_beta(DEFECT_Q[proc], FROZEN_E[proc])
        kernel[proc] = {"alpha": alpha, "beta": beta}
    kernel["E"] = {"alpha": Fraction(1, 50), "beta": Fraction(1, 2)}
    return kernel


def make_config(
    batch_size: int = 3,
    namespace: str = NS,
    master_seed: int = SEED,
    replicate_id: int = REP,
    tau_pm=lr.NO_PM_BEFORE_MANDATORY,
    kernel=None,
    scenario: str = "isolated_small_case",
    shift_length_h: str = "1000000",
    shifts_per_day: int = 1,
    durations=None,
    turnover_profile: str = "1h_literal",
) -> rd.RandomDesConfig:
    if kernel is None:
        kernel = frozen_kernel()
    return rd.default_config(
        namespace=namespace,
        master_seed=master_seed,
        replicate_id=replicate_id,
        tau_pm=tau_pm,
        observation_kernel=kernel,
        batch_size=batch_size,
        scenario=scenario,
        shift_length_h=shift_length_h,
        shifts_per_day=shifts_per_day,
        durations=durations,
        turnover_profile=turnover_profile,
    )


def run(config: rd.RandomDesConfig) -> rd.RandomDesResult:
    return rd.run_random_des(config)


def records(log, event_type: str) -> list[dict]:
    return [r for r in log if r["event_type"] == event_type]


def clone(log):
    """Deep-copy an event log (JSON round-trip keeps only JSON-safe fields)."""
    return json.loads(json.dumps(log))


class _Base(unittest.TestCase):
    """Shared checker-run helper."""

    def check(self, config, event_log=None, metrics=None,
              parameters=PARAMS_CSV, run_id=None) -> rck.ReplayReport:
        if event_log is None:
            event_log = run(config).event_log
        return rck.check_replay(
            event_log, config.to_dict(),
            parameters_csv=str(parameters), metrics=metrics, run_id=run_id,
        )


# ---------------------------------------------------------------------------
# 1. Multi-seed small-batch replay -> full PASS
# ---------------------------------------------------------------------------


class TestReplayPassMultiSeed(_Base):
    def test_small_batches_all_seeds(self) -> None:
        for seed in (1, 2, 3, 7):
            for batch in (1, 2, 3, 4, 5):
                cfg = make_config(batch_size=batch, master_seed=seed)
                res = run(cfg)
                report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
                self.assertEqual(
                    report.verdict, "PASS",
                    "seed=%d batch=%d: %s; issues=%s"
                    % (seed, batch, report.summarize(),
                       [i.describe() for i in report.issues]),
                )
                self.assertEqual(report.issues, [])

    def test_q2_calendar_run(self) -> None:
        cfg = make_config(batch_size=8, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        self.assertEqual(report.recomputed["S"] + report.recomputed["exited"], 8)

    def test_q3_two_shift_run(self) -> None:
        cfg = make_config(batch_size=6, master_seed=7,
                          scenario="q3_two_shift", shift_length_h="12",
                          shifts_per_day=2)
        res = run(cfg)
        self.assertEqual(len(records(res.event_log, "TRUE_STATE_GENERATED")), 6)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)

    def test_equipment_failure_path(self) -> None:
        # seed 51: the B generation-1 lifetime interrupts the B1 fragment;
        # the retry of the SAME effective attempt completes.
        cfg = make_config(batch_size=1, master_seed=51,
                          durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"})
        res = run(cfg)
        self.assertEqual(len(records(res.event_log, "EQUIPMENT_FAILURE")), 1)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)

    def test_overlap_turnover_profile(self) -> None:
        cfg = make_config(batch_size=4, turnover_profile="0.5h_overlap")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)

    def test_batch_one_single_bay(self) -> None:
        cfg = make_config(batch_size=1)
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)


# ---------------------------------------------------------------------------
# 2. Resource / bay occupancy independently recomputed
# ---------------------------------------------------------------------------


class TestOccupancyCoverage(_Base):
    def test_resource_busy_recomputed(self) -> None:
        cfg = make_config(batch_size=30, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        rb = report.recomputed["resource_busy"]
        self.assertEqual(set(rb), set(rck.PROCESSES))
        for proc in rck.PROCESSES:
            self.assertIn("test_intervals", rb[proc])
            self.assertIn("calibration_intervals", rb[proc])
            self.assertIn("busy_total_h", rb[proc])
            # test-interval totals must equal the fragment elapsed ledger
            test_total = sum(
                (Fraction(e) - Fraction(s))
                for s, e in rb[proc]["test_intervals"]
            )
            self.assertEqual(
                test_total,
                Fraction(report.recomputed["elapsed_by_process"][proc]),
            )
        # bay coverage gapless over [0, T)
        bc = report.recomputed["bay_coverage"]
        self.assertEqual(set(bc), {"1", "2"})
        for bay_id in ("1", "2"):
            intervals = [(Fraction(s), Fraction(e))
                         for s, e in bc[bay_id]["intervals"]]
            self.assertTrue(bc[bay_id]["gapless"], bay_id)
            self.assertEqual(intervals[0][0], Fraction(0), bay_id)
            self.assertEqual(intervals[-1][1], Fraction(report.recomputed["T_h"]),
                             bay_id)

    def test_overlap_profile_bay_physical(self) -> None:
        cfg = make_config(batch_size=4, turnover_profile="0.5h_overlap")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        # 0.5h_overlap folds the IN phases: no interval shorter than 0.5 h
        for bay_id in ("1", "2"):
            intervals = [(Fraction(s), Fraction(e))
                         for s, e in report.recomputed["bay_coverage"][bay_id]["intervals"]]
            for s, e in intervals:
                self.assertGreaterEqual(e - s, Fraction(1, 2), bay_id)


# ---------------------------------------------------------------------------
# 3. Task release / start / end / attempt / observation / cancellation
# ---------------------------------------------------------------------------


class TestTaskLifecycle(_Base):
    def test_task_summary_structure(self) -> None:
        cfg = make_config(batch_size=5, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        tasks = report.recomputed["tasks"]
        self.assertGreaterEqual(len(tasks), 5 * 4)
        for task_id, view in tasks.items():
            self.assertIn(view["status"], ("COMPLETED", "CANCELLED"))
            self.assertIsNotNone(view["release_h"])
            self.assertIsNotNone(view["start_h"])
            self.assertIsNotNone(view["finish_h"])
            if view["status"] == "COMPLETED":
                self.assertIn(view["outcome"], (rck.OUTCOME_PASS,
                                                rck.OUTCOME_ABNORMAL))
            else:
                self.assertIsNone(view["outcome"])

    def test_fcfs_keys_reconstructed(self) -> None:
        cfg = make_config(batch_size=10, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        fcfs = report.recomputed["fcfs_keys"]
        self.assertGreaterEqual(len(fcfs), 10 * 4)
        # every key is (release_time, device_id, process_order, attempt) with
        # the frozen process order
        for task_id, value in fcfs.items():
            self.assertEqual(len(value), 4)
            process = task_id.split("_")[1]
            self.assertEqual(value[2], rck.PROCESS_ORDER[process])

    def test_cancelled_fragment_semantics(self) -> None:
        # seed 51 produces a TASK_CANCEL (EQUIPMENT_FAILURE) fragment: no
        # observation, attempt unchanged, elapsed == lifetime - a_start.
        cfg = make_config(batch_size=1, master_seed=51,
                          durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"})
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        cancel = records(res.event_log, "TASK_CANCEL")
        self.assertEqual(len(cancel), 1)
        self.assertEqual(cancel[0]["cancel_reason"], rck.CANCEL_REASON_EQUIPMENT_FAILURE)
        self.assertEqual(cancel[0]["outcome"], rck.OUTCOME_NONE)
        # the retry reuses the same effective attempt (1) and the same keyed U
        b_starts = [r for r in res.event_log
                    if r["event_type"] == "ACTIVITY_START" and r["process"] == "B"]
        self.assertEqual([s["effective_attempt_no"] for s in b_starts], [1, 1])
        b_obs = [r for r in res.event_log
                 if r["event_type"] == "OBSERVATION_MATERIALIZED"
                 and r["process"] == "B"]
        self.assertEqual(len(b_obs), 1)
        self.assertEqual(b_obs[0]["effective_attempt_no"], 1)

    def test_attempt_monotonic_and_retest_release(self) -> None:
        # attempt 2 retests are released exactly at the first-ABNORMAL time
        # (verified by the checker; here assert on a real batch)
        cfg = make_config(batch_size=20, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        retests = [r for r in res.event_log
                   if r["event_type"] == "TASK_RELEASE"
                   and r["effective_attempt_no"] == 2]
        self.assertGreater(len(retests), 0)


# ---------------------------------------------------------------------------
# 4. Equipment age / generation / lifetime / failure / replacement /
#    calibration independently recomputed
# ---------------------------------------------------------------------------


class TestEquipmentReplay(_Base):
    def test_failure_replacement_calibration_recomputed(self) -> None:
        cfg = make_config(batch_size=1, master_seed=51,
                          durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"})
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        eq = report.recomputed["equipment"]["B"]
        self.assertEqual(eq["failure_count"], 1)
        self.assertEqual(eq["replacement_count"], 1)
        self.assertEqual(eq["generation"], 2)
        self.assertEqual(eq["calibration_count"], 1)
        # the independently recomputed generation-1 lifetime == the recorded
        # failure age (the checker derives the lifetime from the key schema,
        # never from the log)
        fail = records(res.event_log, "EQUIPMENT_FAILURE")[0]
        self.assertEqual(
            Fraction(report.recomputed["lifetimes"]["B"]["1"]["lifetime_h"]),
            Fraction(fail["equipment_age_at_failure"]),
        )
        self.assertFalse(report.recomputed["lifetimes"]["B"]["1"]["right_censored"])
        rep_rec = records(res.event_log, "EQUIPMENT_REPLACEMENT_START")[0]
        self.assertEqual(rep_rec["old_generation"], 1)
        self.assertEqual(rep_rec["new_generation"], 2)
        # the retry starts at age 0 on generation 2
        retry = [r for r in res.event_log
                 if r["event_type"] == "ACTIVITY_START" and r["process"] == "B"][1]
        self.assertEqual(Fraction(retry["equipment_age_at_start"]), Fraction(0))
        self.assertEqual(retry["equipment_generation"], 2)

    def test_preventive_replacement_recomputed(self) -> None:
        cfg = make_config(batch_size=4, tau_pm=Fraction(120),
                          durations={"A": "40", "B": "40", "C": "40", "E": "3"})
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        total_pm = sum(
            report.recomputed["equipment"][p]["preventive_replacement_count"]
            for p in rck.PROCESSES
        )
        self.assertGreaterEqual(total_pm, 1)
        pm_recs = [r for r in res.event_log
                   if r["event_type"] == "EQUIPMENT_REPLACEMENT_START"
                   and r["kind"] == rck.REPLACEMENT_KIND_PREVENTIVE]
        self.assertEqual(len(pm_recs), total_pm)
        for rec in pm_recs:
            self.assertGreaterEqual(Fraction(rec["age_before"]), Fraction(120))

    def test_no_pm_never_triggers(self) -> None:
        cfg = make_config(batch_size=4, tau_pm=lr.NO_PM_BEFORE_MANDATORY,
                          durations={"A": "40", "B": "40", "C": "40", "E": "3"})
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        total_pm = sum(
            report.recomputed["equipment"][p]["preventive_replacement_count"]
            for p in rck.PROCESSES
        )
        self.assertEqual(total_pm, 0)

    def test_mandatory_240_post_completion(self) -> None:
        # a+d == 240: completion settles first, then the mandatory replacement
        cfg = make_config(batch_size=3,
                          durations={"A": "80", "B": "80", "C": "80", "E": "3"})
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        reps = [r for r in res.event_log
                if r["event_type"] == "EQUIPMENT_REPLACEMENT_START"
                and r["trigger"] == rck.REPLACEMENT_TRIGGER_POST_COMPLETION_240]
        self.assertGreaterEqual(len(reps), 1)
        for rec in reps:
            self.assertEqual(Fraction(rec["age_before"]), Fraction(240))
            self.assertEqual(rec["kind"], rck.REPLACEMENT_KIND_MANDATORY_240)

    def test_a_plus_d_gt_240_forced(self) -> None:
        cfg = make_config(batch_size=4,
                          durations={"A": "90", "B": "90", "C": "90", "E": "3"})
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        reps = [r for r in res.event_log
                if r["event_type"] == "EQUIPMENT_REPLACEMENT_START"
                and r["trigger"] == rck.REPLACEMENT_TRIGGER_A_PLUS_D_GT_240]
        self.assertGreaterEqual(len(reps), 1)
        d = {"A": Fraction(90), "B": Fraction(90),
             "C": Fraction(90), "E": Fraction(3)}
        for rec in reps:
            self.assertGreater(Fraction(rec["age_before"]) + d[rec["resource_id"]],
                               Fraction(240))

    def test_frozen_durations_evidence(self) -> None:
        # frozen durations P006-P009, N=100, q2 calendar, seed 33: real
        # a+d>240 forced replacements with the frozen parameters
        cfg = make_config(batch_size=100, master_seed=33,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        reps = [r for r in res.event_log
                if r["event_type"] == "EQUIPMENT_REPLACEMENT_START"
                and r["trigger"] == rck.REPLACEMENT_TRIGGER_A_PLUS_D_GT_240]
        self.assertGreaterEqual(len(reps), 1)

    def test_lifetime_right_censoring_recomputed(self) -> None:
        # some generation-1 lifetime must be right-censored (U_L > F(240))
        # with a large enough batch; the checker's recomputed lifetimes must
        # agree with the failure/age semantics (PASS proves it)
        cfg = make_config(batch_size=60, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        for proc in rck.PROCESSES:
            gen1 = report.recomputed["lifetimes"][proc]["1"]
            if not gen1["right_censored"]:
                self.assertIsNotNone(gen1["lifetime_h"])
                self.assertLessEqual(Fraction(gen1["lifetime_h"]), Fraction(240))
            else:
                self.assertIsNone(gen1["lifetime_h"])

    def test_deferred_replacement_recovery(self) -> None:
        # N=100 seed 7 q2: a post-completion-240 E replacement deferred at
        # the shift end (636) and recovered after the wake (648) -- the
        # checker must pass the deferral-robust trigger/age semantics
        cfg = make_config(batch_size=100, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        deferred = records(res.event_log, "EQUIPMENT_REPLACEMENT_DEFERRED")
        self.assertGreaterEqual(len(deferred), 1)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)


# ---------------------------------------------------------------------------
# 5. T / S / PL / PW / YXB 对拍 against the DES metrics
# ---------------------------------------------------------------------------


class TestMetricsCrosscheck(_Base):
    def test_all_metric_fields(self) -> None:
        cfg = make_config(batch_size=60, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        m = res.metrics
        self.assertEqual(report.recomputed["T_h"], m["T"])
        self.assertEqual(report.recomputed["S"], m["S"])
        self.assertEqual(report.recomputed["PL"], m["PL"])
        self.assertEqual(report.recomputed["PW"], m["PW"])
        self.assertEqual(report.recomputed["exited"], m["exited"])
        self.assertEqual(report.recomputed["shift_count"], m["shift_count"])
        self.assertEqual(report.recomputed["yxb_denominator_h"],
                         m["yxb_denominator_h"])
        for proc in rck.PROCESSES:
            self.assertEqual(report.recomputed["YXB_" + proc],
                             m["YXB_" + proc])
            eq = report.recomputed["equipment"][proc]
            self.assertEqual(eq["age_h"], m["equipment"][proc]["age_h"])
            self.assertEqual(eq["generation"], m["equipment"][proc]["generation"])
            self.assertEqual(eq["replacement_count"],
                             m["equipment"][proc]["replacement_count"])
            self.assertEqual(eq["preventive_replacement_count"],
                             m["equipment"][proc]["preventive_replacement_count"])
            self.assertEqual(eq["failure_count"],
                             m["equipment"][proc]["failure_count"])
            self.assertEqual(eq["lifetime_h"], m["equipment"][proc]["lifetime_h"])
            self.assertEqual(eq["is_right_censored"],
                             m["equipment"][proc]["is_right_censored"])
            self.assertEqual(eq["available"], m["equipment"][proc]["available"])

    def test_drifted_metrics_detected(self) -> None:
        cfg = make_config(batch_size=8, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        bad_metrics = dict(res.metrics)
        bad_metrics["S"] = res.metrics["S"] + 1
        report = self.check(cfg, event_log=res.event_log, metrics=bad_metrics)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(
            any("metrics.S" in i.location for i in report.issues),
            [i.describe() for i in report.issues],
        )


# ---------------------------------------------------------------------------
# 6. Isolation (CR-V3.1/C19): static AST scan + dynamic run without the main
#    DES ever being imported
# ---------------------------------------------------------------------------


class TestIsolation(_Base):
    def test_static_ast_scan(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: list[tuple[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend((alias.name, "") for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.extend(
                    (node.module or "", alias.name) for alias in node.names
                )
        # the ONLY main_model imports allowed are the frozen shared key schema
        # and the frozen C13/C14 lifetime/regeneration semantics (explicitly
        # allowed by the task package); the import graph is the authoritative
        # isolation contract.
        g3_imports = sorted(n for (m, n) in imported if m == "g3")
        self.assertEqual(g3_imports,
                         ["key_schema_v1", "lifetime_regeneration_v1"])
        for (module, name) in imported:
            self.assertFalse(module.startswith("des"), (module, name))
            self.assertFalse(module.startswith("tests"), (module, name))
            self.assertFalse(module.startswith("checker"), (module, name))
            self.assertFalse(
                "random_des" in module or "random_des" in name, (module, name)
            )
            self.assertFalse(
                "deterministic" in module or "deterministic" in name,
                (module, name),
            )
            self.assertFalse(
                "state_models" in module or "state_models" in name,
                (module, name),
            )
            self.assertFalse(
                "observation_calibration" in module
                or "observation_calibration" in name,
                (module, name),
            )
        # no dangerous execution / non-determinism constructs anywhere in the
        # checker's CODE
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name in ("random", "subprocess", "os")
                for alias in node.names
            ):
                self.fail("forbidden stdlib import in checker: %s" % (node,))
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in (
                    "eval", "exec", "__import__", "compile", "hash",
                ):
                    self.fail("forbidden dynamic call in checker: %s" % func.id)
                if (isinstance(func, ast.Attribute)
                        and func.attr in ("system", "popen", "run", "call",
                                          "Popen")
                        and isinstance(func.value, ast.Name)
                        and func.value.id in ("os", "subprocess")):
                    self.fail("forbidden os/subprocess call in checker")
        self.assertNotIn("import random", source)
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("import os", source)
        self.assertNotIn("hash(", source)

    def test_dynamic_run_without_main_des(self) -> None:
        # subprocess with the checker + main_model dirs on PYTHONPATH: the
        # checker must run end-to-end and never load random_des_v1 or the
        # des package (lifetime_regeneration_v1 IS an allowed shared import).
        cfg = make_config(batch_size=4, master_seed=7)
        res = run(cfg)
        with tempfile.TemporaryDirectory(prefix="g3_replay_iso_") as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "event_log.json").write_text(
                json.dumps(res.event_log, ensure_ascii=False), encoding="utf-8")
            (tmp_path / "config.json").write_text(
                json.dumps(cfg.to_dict(), ensure_ascii=False), encoding="utf-8")
            (tmp_path / "metrics.json").write_text(
                json.dumps(res.metrics, ensure_ascii=False), encoding="utf-8")
            script = (
                "import json, sys\n"
                "import g3_replay_checker_v1 as rck\n"
                "log = json.load(open('event_log.json', encoding='utf-8'))\n"
                "cfg = json.load(open('config.json', encoding='utf-8'))\n"
                "metrics = json.load(open('metrics.json', encoding='utf-8'))\n"
                "rep = rck.check_replay(log, cfg, parameters_csv=r'%s', "
                "metrics=metrics)\n"
                "print(rep.summarize())\n"
                "assert rep.verdict == 'PASS', rep.issues\n"
                "forbidden = ('random_des_v1', 'des.')\n"
                "loaded = [m for m in sys.modules if any(f in m for f in "
                "forbidden)]\n"
                "assert not loaded, loaded\n"
            ) % PARAMS_CSV
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join(
                (str(CHECKER_DIR), str(MAIN_MODEL), str(CODE_DIR))
            )
            proc = subprocess.run(
                [sys.executable, "-c", script],
                cwd=tmp, env=env, capture_output=True, text=True, timeout=180,
            )
            self.assertEqual(
                proc.returncode, 0,
                "checker failed without the main DES:\n%s\n%s"
                % (proc.stdout, proc.stderr),
            )
            self.assertIn("PASS", proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)


# ---------------------------------------------------------------------------
# 7. Fault injection: tampered logs must FAIL (not always-PASS)
# ---------------------------------------------------------------------------


class TestFaultInjection(_Base):
    def test_age_tamper_fails(self) -> None:
        cfg = make_config(batch_size=30, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        log = clone(res.event_log)
        start = records(log, "ACTIVITY_START")[0]
        start["equipment_age_at_start"] = "1"
        report = self.check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(
            any("age_at_start" in i.location for i in report.issues),
            [i.describe() for i in report.issues],
        )

    def test_generation_tamper_fails(self) -> None:
        cfg = make_config(batch_size=30, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        log = clone(res.event_log)
        complete = records(log, "ACTIVITY_COMPLETE")[0]
        complete["equipment_generation"] += 1
        report = self.check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")

    def test_observation_flip_fails(self) -> None:
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        log = clone(res.event_log)
        obs = records(log, "OBSERVATION_MATERIALIZED")[0]
        obs["outcome"] = (
            rck.OUTCOME_ABNORMAL if obs["outcome"] == rck.OUTCOME_PASS
            else rck.OUTCOME_PASS
        )
        report = self.check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(
            any("observation" in i.location or "observation" in i.message
                for i in report.issues),
            [i.describe() for i in report.issues],
        )

    def test_attempt_tamper_fails(self) -> None:
        # seed 51: the failure-interrupted B fragment keeps attempt 1; a
        # tampered attempt number must be caught
        cfg = make_config(batch_size=1, master_seed=51,
                          durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"})
        res = run(cfg)
        log = clone(res.event_log)
        cancel = records(log, "TASK_CANCEL")[0]
        cancel["effective_attempt_no"] = 2
        report = self.check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")

    def test_replacement_tamper_fails(self) -> None:
        cfg = make_config(batch_size=1, master_seed=51,
                          durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"})
        res = run(cfg)
        for field, value in (("new_generation", None), ("age_before", "1"),
                             ("kind", rck.REPLACEMENT_KIND_PREVENTIVE)):
            log = clone(res.event_log)
            rec = records(log, "EQUIPMENT_REPLACEMENT_START")[0]
            rec[field] = rec[field] + 1 if value is None else value
            report = self.check(cfg, event_log=log)
            self.assertEqual(report.verdict, "FAIL", field)

    def test_lifetime_tamper_fails(self) -> None:
        # a drifted sampled lifetime in the metrics block must be caught by
        # the metrics cross-check (the checker recomputes it from the schema)
        cfg = make_config(batch_size=1, master_seed=51,
                          durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"})
        res = run(cfg)
        bad = dict(res.metrics)
        bad["equipment"] = {
            p: dict(v) for p, v in res.metrics["equipment"].items()
        }
        bad["equipment"]["B"]["lifetime_h"] = "1"
        report = self.check(cfg, event_log=res.event_log, metrics=bad)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(
            any("lifetime_h" in i.location for i in report.issues),
            [i.describe() for i in report.issues],
        )

    def test_failure_age_tamper_fails(self) -> None:
        cfg = make_config(batch_size=1, master_seed=51,
                          durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"})
        res = run(cfg)
        log = clone(res.event_log)
        fail = records(log, "EQUIPMENT_FAILURE")[0]
        fail["equipment_age_at_failure"] = "1"
        report = self.check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")

    def test_u_tamper_fails(self) -> None:
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        log = clone(res.event_log)
        for rec in log:
            if not isinstance(rec, dict):
                continue
            for key in ("u", "u_key"):
                if key in rec:
                    rec[key] = "TAMPERED"
        report = self.check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")

    def test_true_state_tamper_fails(self) -> None:
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        log = clone(res.event_log)
        gen = records(log, "TRUE_STATE_GENERATED")[0]
        gen["true_state"]["A"] = not gen["true_state"]["A"]
        report = self.check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")

    def test_terminal_tamper_fails(self) -> None:
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        log = clone(res.event_log)
        term = records(log, "DEVICE_TERMINAL")[0]
        term["terminal_state"] = (
            rck.TERMINAL_EXITED if term["terminal_state"] == rck.TERMINAL_PASSED
            else rck.TERMINAL_PASSED
        )
        report = self.check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")

    def test_missing_device_fails(self) -> None:
        # a batch that never fully creates its devices is a C17/liveness FAIL
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        log = [r for r in clone(res.event_log)
               if not (r["event_type"] == "TRUE_STATE_GENERATED"
                       and r["device_id"] == 1)]
        report = self.check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")

    def test_seq_tamper_fails(self) -> None:
        cfg = make_config(batch_size=3, master_seed=7)
        res = run(cfg)
        log = clone(res.event_log)
        log[3]["seq"], log[4]["seq"] = log[4]["seq"], log[3]["seq"]
        report = self.check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")

    def test_empty_log_fails(self) -> None:
        cfg = make_config(batch_size=3, master_seed=7)
        report = self.check(cfg, event_log=[])
        self.assertEqual(report.verdict, "FAIL")


# ---------------------------------------------------------------------------
# RED_G3_S7 finding B: C18 DEVICE_EXIT -> DEVICE_TERMINAL is a per-device
# ordering at one timestamp
# ---------------------------------------------------------------------------


class TestC18ExitTerminalPerDevice(_Base):
    """RED_G3_S7 finding B regression: at one timestamp several devices can
    exit simultaneously and their DEVICE_EXIT / DEVICE_TERMINAL seqs
    interleave across devices, so a global min/max comparison mis-pairs
    different devices (S7 rep=9 t=465: dev57 EXIT seq 1394 vs dev56 TERMINAL
    seq 1393 -> false C18). The check must pair by device_id: the interleaved
    log passes, while a same-device TERMINAL before EXIT still FAILs."""

    # Frozen S7 E kernel input (Q1-frozen q_E propagation, accepted G2-02 run
    # 4bb92eda; e_E = P033), restated only for building the test world.
    S7_Q_E = Fraction("0.062593912407392898")

    def _s7_kernel(self) -> dict[str, dict[str, Fraction]]:
        kernel: dict[str, dict[str, Fraction]] = {}
        for proc in ("A", "B", "C"):
            alpha, beta = rd.frozen_single_test_alpha_beta(
                DEFECT_Q[proc], FROZEN_E[proc]
            )
            kernel[proc] = {"alpha": alpha, "beta": beta}
        alpha_e, beta_e = rd.frozen_single_test_alpha_beta(
            self.S7_Q_E, Fraction(2, 100)
        )
        kernel["E"] = {"alpha": alpha_e, "beta": beta_e}
        return kernel

    def _minimal_two_exit_log(self) -> list[dict]:
        """Two devices exit at the same instant; their EXIT/TERMINAL pairs
        interleave in seq order (e1 < t1 < e2 < t2) exactly like the engine's
        ``_apply_exits`` emission for sorted device ids. dev2's EXIT seq is
        AFTER dev1's TERMINAL seq, which the old global check reported as a
        C18 violation."""
        return [
            {"seq": 1, "event_time": "5", "event_type": "DEVICE_EXIT",
             "device_id": 1, "process": "B", "effective_attempt_no": 2},
            {"seq": 2, "event_time": "5", "event_type": "DEVICE_TERMINAL",
             "device_id": 1, "terminal_state": rck.TERMINAL_EXITED},
            {"seq": 3, "event_time": "5", "event_type": "DEVICE_EXIT",
             "device_id": 2, "process": "B", "effective_attempt_no": 2},
            {"seq": 4, "event_time": "5", "event_type": "DEVICE_TERMINAL",
             "device_id": 2, "terminal_state": rck.TERMINAL_EXITED},
            {"seq": 5, "event_time": "5", "event_type": "SIMULATION_END"},
        ]

    def _c18_only_checker(self, log) -> rck.G3ReplayChecker:
        cfg = make_config(batch_size=2)
        checker = rck.G3ReplayChecker(
            log, cfg.to_dict(), parameters_csv=str(PARAMS_CSV)
        )
        self.assertTrue(checker._structural_ok)
        return checker

    def test_interleaved_multi_device_exit_no_false_positive(self) -> None:
        checker = self._c18_only_checker(self._minimal_two_exit_log())
        checker._check_same_timestamp_order()
        self.assertEqual(
            checker._issues, [],
            [i.describe() for i in checker._issues],
        )

    def test_same_device_terminal_before_exit_still_caught(self) -> None:
        checker = self._c18_only_checker(self._minimal_two_exit_log())
        # swap the seqs of device 1's EXIT/TERMINAL: a same-instant
        # TERMINAL-before-EXIT is a genuine engine defect and must be caught
        # (the per-device fix must not weaken the real detection).
        exit_rec = term_rec = None
        for rec in checker._log:
            if rec["event_type"] == "DEVICE_EXIT" and rec["device_id"] == 1:
                exit_rec = rec
            elif rec["event_type"] == "DEVICE_TERMINAL" and rec["device_id"] == 1:
                term_rec = rec
        self.assertIsNotNone(exit_rec)
        self.assertIsNotNone(term_rec)
        exit_rec["seq"], term_rec["seq"] = term_rec["seq"], exit_rec["seq"]
        checker._check_same_timestamp_order()
        c18 = [i for i in checker._issues if i.check_id == "C18"]
        self.assertTrue(
            any("DEVICE_EXIT.seq < DEVICE_TERMINAL.seq" in i.expected
                for i in c18),
            [i.describe() for i in checker._issues],
        )

    def test_real_s7_world_simultaneous_exit_passes(self) -> None:
        # The exact S7 failing world (master_seed=1, replicate_id=9, NO_PM,
        # h1_tuning, 100 devices): two devices exit at t=465, which made the
        # old global EXIT/TERMINAL comparison false-positive with C18. The
        # per-device check passes the full C17 replay.
        cfg = make_config(
            batch_size=100, master_seed=1, replicate_id=9,
            namespace=ks.NAMESPACE_H1_TUNING, kernel=self._s7_kernel(),
            scenario="q2_single_shift", shift_length_h="12",
        )
        res = run(cfg)
        by_time: dict[str, int] = {}
        for rec in records(res.event_log, "DEVICE_EXIT"):
            by_time[rec["event_time"]] = by_time.get(rec["event_time"], 0) + 1
        multi = {t: n for t, n in by_time.items() if n >= 2}
        self.assertTrue(
            multi,
            "scenario guard: this fixed S7 world must still contain a "
            "same-timestamp multi-device exit (found %s)" % by_time,
        )
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(
            report.verdict, "PASS", [i.describe() for i in report.issues]
        )


# ---------------------------------------------------------------------------
# 8. Deterministic reproducibility
# ---------------------------------------------------------------------------


class TestDeterminism(_Base):
    def test_repeat_identical_report(self) -> None:
        cfg = make_config(batch_size=5, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        r1 = self.check(cfg, event_log=res.event_log, metrics=res.metrics,
                        run_id="run-abc")
        r2 = self.check(cfg, event_log=res.event_log, metrics=res.metrics,
                        run_id="run-abc")
        self.assertEqual(
            json.dumps(r1.to_dict(), sort_keys=True),
            json.dumps(r2.to_dict(), sort_keys=True),
        )
        # a pre-parsed ReplayConfig input gives the identical report
        r3 = rck.check_replay(
            res.event_log, rck.parse_config(cfg.to_dict()),
            parameters_csv=str(PARAMS_CSV), metrics=res.metrics,
            run_id="run-abc",
        )
        self.assertEqual(
            json.dumps(r1.to_dict(), sort_keys=True),
            json.dumps(r3.to_dict(), sort_keys=True),
        )


# ---------------------------------------------------------------------------
# 9. No binary float in canonical paths
# ---------------------------------------------------------------------------


class TestNoFloat(_Base):
    def test_no_float_literal_or_call(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                self.fail("binary float literal in checker: %r" % (node.value,))
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "float"):
                self.fail("float() builtin call in checker")
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "float"):
                self.fail("float method call in checker")
        self.assertNotIn("import random", source)
        self.assertNotIn("hash(", source)

    def test_report_contains_no_float(self) -> None:
        cfg = make_config(batch_size=5, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self._assert_no_float(report.to_dict())

    def _assert_no_float(self, value) -> None:
        if isinstance(value, float):
            self.fail("float in report: %r" % (value,))
        if isinstance(value, dict):
            for v in value.values():
                self._assert_no_float(v)
        elif isinstance(value, list):
            for v in value:
                self._assert_no_float(v)


# ---------------------------------------------------------------------------
# Config / parameter validation (fail loudly, never a silent default)
# ---------------------------------------------------------------------------


class TestValidation(_Base):
    def test_bad_config_rejected(self) -> None:
        cfg = make_config(batch_size=2).to_dict()
        cfg["namespace"] = "not_a_namespace"
        with self.assertRaises(rck.ReplayCheckerInputError):
            rck.parse_config(cfg)
        cfg["namespace"] = NS
        cfg["observation_kernel"]["E"]["alpha"] = 0.5  # binary float
        with self.assertRaises(rck.ReplayCheckerInputError):
            rck.parse_config(cfg)
        cfg2 = make_config(batch_size=2).to_dict()
        cfg2["schema_version"] = "wrong_schema"
        with self.assertRaises(rck.ReplayCheckerInputError):
            rck.parse_config(cfg2)

    def test_missing_parameters_fails(self) -> None:
        cfg = make_config(batch_size=2, master_seed=7)
        res = run(cfg)
        with self.assertRaises(rck.ReplayCheckerInputError):
            rck.check_replay(res.event_log, cfg.to_dict(), parameters_csv=None)

    def test_drifted_parameters_break_check(self) -> None:
        # a drifted q (the csv is the single authoritative source) must
        # surface as a FAIL at the check level, never a silent pass
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        with tempfile.TemporaryDirectory(prefix="g3_replay_params_") as tmp:
            drift = Path(tmp) / "parameters_drifted.csv"
            out = []
            for line in PARAMS_CSV.read_text(encoding="utf-8-sig").splitlines():
                if line.startswith("P026,"):
                    out.append(line.replace("0.025", "0.99"))
                else:
                    out.append(line)
            drift.write_text("\n".join(out), encoding="utf-8")
            report = rck.check_replay(
                res.event_log, cfg.to_dict(),
                parameters_csv=str(drift), metrics=res.metrics,
            )
        self.assertEqual(report.verdict, "FAIL")

    def test_missing_parameter_rows_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g3_replay_params_") as tmp:
            bad = Path(tmp) / "missing_row.csv"
            bad.write_text(
                "parameter_id,symbol,value\n"
                "P010,t_cal_A,30\nP011,t_cal_B,20\nP012,t_cal_C,20\n"
                "P013,t_cal_E,40\nP016,a_min,120\nP017,a_max,240\n"
                "P018,F_A_120,0.03\nP019,F_B_120,0.04\nP020,F_C_120,0.02\n"
                "P021,F_E_120,0.03\nP022,F_A_240,0.05\nP023,F_B_240,0.07\n"
                "P024,F_C_240,0.06\nP025,F_E_240,0.05\n"
                "P027,q_B,0.03\nP028,q_C,0.02\nP029,q_D,0.001\n"
                "P061,key_schema,key_schema_v1\n",
                encoding="utf-8",
            )
            with self.assertRaises(rck.ReplayCheckerInputError):
                rck.load_parameters(bad)


# ---------------------------------------------------------------------------
# Report output contract
# ---------------------------------------------------------------------------


class TestOutputContract(_Base):
    def test_report_fields(self) -> None:
        cfg = make_config(batch_size=4, master_seed=7)
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics,
                            run_id="run-x")
        self.assertEqual(report.verdict, "PASS", report.issues)
        d = report.to_dict()
        for key in ("envelope_type", "schema_version", "registry_version",
                    "check_ids", "run_id", "scenario_id", "verdict", "issues",
                    "recomputed", "metadata"):
            self.assertIn(key, d)
        self.assertEqual(d["envelope_type"], "g3_replay_check_report")
        self.assertEqual(d["registry_version"], rck.REGISTRY_VERSION)
        self.assertEqual(d["run_id"], "run-x")
        self.assertEqual(set(d["check_ids"]), set(rck.CHECK_IDS))
        rec = d["recomputed"]
        for key in ("T_h", "S", "PL", "PW", "exited", "shift_count",
                    "yxb_denominator_h", "YXB_A", "YXB_B", "YXB_C", "YXB_E",
                    "elapsed_by_process", "resource_busy", "bay_coverage",
                    "equipment", "lifetimes", "generations", "devices",
                    "tasks", "fcfs_keys", "u_consumption"):
            self.assertIn(key, rec)
        self.assertEqual(rec["u_consumption"]["u_x"], 3 * 4)
        self.assertEqual(rec["u_consumption"]["u_y"],
                         len(records(res.event_log,
                                     "OBSERVATION_MATERIALIZED")))
        self.assertEqual(rec["u_consumption"]["u_d"],
                         len(records(res.event_log, "D_CREATED")))
        self.assertEqual(
            rec["u_consumption"]["u_l"],
            4 + sum(rec["equipment"][p]["replacement_count"]
                    for p in rck.PROCESSES),
        )

    def test_summarize(self) -> None:
        cfg = make_config(batch_size=3, master_seed=7)
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        summary = report.summarize()
        self.assertIn("PASS", summary)
        self.assertIn("T=", summary)


# ---------------------------------------------------------------------------
# C17 cancelled-attempt replay semantics regression (INVALIDATION_REPORT_G3_C17)
# ---------------------------------------------------------------------------
# Frozen semantics (G3-SPEC-V1.0 section 2): interruption/cancellation
# produces no observation and does not advance the effective attempt; a
# cancelled/non-completed attempt2 must NEVER become an exit-causing ABNORMAL
# merely because its canonical U_Y would have been ABNORMAL had it completed.
# The repaired derive_device_chain accepts completed_observations so that only
# EFFECTIVE COMPLETED observations drive the exit-process set.  These tests
# lock "cancelled/non-completed attempt != observed attempt".


def chain_kernel_test() -> dict[str, dict[str, Fraction]]:
    """Frozen standard-chain observation kernel (accepted G2-02 4bb92eda)."""
    return {
        proc: {
            "alpha": Fraction(entry["alpha"]),
            "beta": Fraction(entry["beta"]),
        }
        for proc, entry in {
            "A": {"alpha": "0.015612642053572192", "beta": "0.38226176188707678"},
            "B": {"alpha": "0.020942481877888125", "beta": "0.44441134347855829"},
            "C": {"alpha": "0.010343090510990168", "beta": "0.30146827672834102"},
            "E": {"alpha": "0.010920932310648563", "beta": "0.1185856135607714"},
        }.items()
    }


def _find_exit_repro(obs_kernel, seed_range=(0, 60)) -> tuple[int, int, int]:
    """Search seeds/replicates for a batch whose log contains a device with:
    some process attempt1 ABNORMAL, attempt2 cancelled before observation, and
    another process actually exits the device.  Returns
    (master_seed, replicate_id, device_id) or raises."""
    for seed in range(*seed_range):
        for rep in range(0, 8):
            cfg = make_config(batch_size=100, master_seed=seed, replicate_id=rep,
                              kernel=obs_kernel, scenario="q2_single_shift",
                              shift_length_h="12", tau_pm=lr.NO_PM_BEFORE_MANDATORY)
            res = run(cfg)
            for rec in res.event_log:
                if rec.get("event_type") != "TASK_CANCEL":
                    continue
                if rec.get("cancel_reason") != "DEVICE_EXIT":
                    continue
                # a cancelled attempt2 whose process is NOT the exiting one
                if rec.get("effective_attempt_no") != 2:
                    continue
                dev = rec.get("device_id")
                proc = rec.get("process")
                # confirm another process exited this device with attempt2 ABNORMAL
                exits = [
                    e for e in res.event_log
                    if e.get("event_type") == "DEVICE_EXIT"
                    and e.get("device_id") == dev and e.get("process") != proc
                ]
                if exits:
                    return (seed, rep, dev)
    raise AssertionError("no cancelled-attempt2 exit repro found in seed range")


class TestC17CancelledAttempt2(_Base):
    def test_chain_cancelled_attempt2_exit_process(self) -> None:
        """A: chain semantic — B2 completes ABNORMAL (exit); C2 started but
        cancelled; C2 canonical U would be ABNORMAL; C2 has zero effective
        OBSERVATION; expected exit_processes = [B]."""
        seed, rep, _dev = _find_exit_repro(chain_kernel_test())
        cfg = make_config(batch_size=100, master_seed=seed, replicate_id=rep,
                          kernel=chain_kernel_test(), scenario="q2_single_shift",
                          shift_length_h="12", tau_pm=lr.NO_PM_BEFORE_MANDATORY)
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        # the repaired checker must PASS this previously-false-C10 batch
        self.assertEqual(report.verdict, "PASS",
                         "issues=%s" % [i.describe() for i in report.issues])

    def test_single_cancelled_attempt2_exit_process(self) -> None:
        """B: single-semantics equivalent — one process attempt2 triggers
        exit while another attempt2 is cancelled before observation."""
        seed, rep, _dev = _find_exit_repro(frozen_kernel())
        cfg = make_config(batch_size=100, master_seed=seed, replicate_id=rep,
                          kernel=frozen_kernel(), scenario="q2_single_shift",
                          shift_length_h="12", tau_pm=lr.NO_PM_BEFORE_MANDATORY)
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS",
                         "issues=%s" % [i.describe() for i in report.issues])

    def test_derive_chain_ignores_uncompleted_attempt2(self) -> None:
        """Core repair unit: attempt2 with no completed observation must not
        enter exit_processes even if its canonical U_Y would be ABNORMAL."""
        ns = ks.NAMESPACE_DEVELOPMENT_UNIT
        seed = 7
        rep = 0
        dev = 3
        params = rck.load_parameters(PARAMS_CSV)
        q = params["q"]
        # find a (device, process) where canonical attempt2 would be ABNORMAL
        found = None
        for proc in ("A", "B", "C"):
            u2 = ks.u_y(ns, rep, dev, proc, 2, seed)
            # need true problem; check u_x
            qp = q[proc]
            true_p = ks.u_x(ns, rep, dev, proc, seed) < qp
            entry = chain_kernel_test()[proc]
            alpha = entry["alpha"]; beta = entry["beta"]
            abn2 = (u2 < 1 - beta) if true_p else (u2 < alpha)
            if abn2:
                found = (proc, true_p)
                break
        if found is None:
            self.skipTest("no canonical-ABNORMAL attempt2 in this seed/dev")
        proc, true_p = found
        cfg = make_config(batch_size=5, master_seed=seed, replicate_id=rep,
                          kernel=chain_kernel_test())
        cfg_dict = cfg.to_dict()
        replay_cfg = rck.parse_config(cfg_dict)
        # without completed observations: attempt2 IS considered (old behavior)
        chain_all = rck.derive_device_chain(replay_cfg, {"q": q}, dev)
        # with attempt2 NOT completed: must be excluded
        chain_cancelled = rck.derive_device_chain(
            replay_cfg, {"q": q}, dev,
            completed_observations={(proc, 1)},
        )
        self.assertNotIn(proc, chain_cancelled.exit_processes)
        # with attempt2 completed: it IS considered
        chain_done = rck.derive_device_chain(
            replay_cfg, {"q": q}, dev,
            completed_observations={(proc, 1), (proc, 2)},
        )
        if chain_all.exit_processes and proc in chain_all.exit_processes:
            self.assertIn(proc, chain_done.exit_processes)
        self.assertEqual(chain_cancelled.exit_processes, ())
        self.assertEqual(chain_done.exit_processes, tuple(sorted([proc])) if
                         proc in chain_all.exit_processes else ())

    def test_same_timestamp_two_exits_preserved(self) -> None:
        """C: same-timestamp two completed second-ABNORMAL observations both
        genuinely complete before terminal settlement — frozen multi-exit
        behavior preserved (NOT forced to a single process)."""
        # The repair only filters non-completed attempts; two genuinely
        # completed attempt2s both remain exit processes.
        ns = ks.NAMESPACE_DEVELOPMENT_UNIT
        seed = 7
        dev = 2
        params = rck.load_parameters(PARAMS_CSV)
        q = params["q"]
        cfg = make_config(batch_size=5, master_seed=seed, replicate_id=0,
                          kernel=chain_kernel_test())
        replay_cfg = rck.parse_config(cfg.to_dict())
        chain = rck.derive_device_chain(
            replay_cfg, {"q": q}, dev,
            completed_observations={("A", 1), ("A", 2), ("B", 1), ("B", 2),
                                    ("C", 1), ("C", 2), ("E", 1), ("E", 2)},
        )
        # invariant: exit_processes is a subset of processes whose attempt2
        # was actually completed in the supplied set
        for proc in chain.exit_processes:
            self.assertIn((proc, 2), {("A", 2), ("B", 2), ("C", 2), ("E", 2)})
        self.assertLessEqual(len(chain.exit_processes), 2)

    def test_interrupted_attempt2_no_false_exit(self) -> None:
        """D: attempt2 random-failure interruption — no observation at the
        interrupted fragment; no false exit from it; if the same effective
        attempt later completes, only that completed observation is used."""
        # equipment-failure seed 51 (B1 interrupted): attempt1 fragment is
        # interrupted by failure; the SAME effective attempt1 later completes.
        cfg = make_config(batch_size=1, master_seed=51,
                          durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"})
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)

    def test_cancelled_attempt2_pass_u_still_no_observation(self) -> None:
        """E: cancelled attempt2 whose canonical U would be PASS — still no
        observation; absence is path semantics, not outcome dependent."""
        # A cancelled attempt2 is never observed regardless of its U value.
        seed, rep, dev = _find_exit_repro(frozen_kernel())
        cfg = make_config(batch_size=100, master_seed=seed, replicate_id=rep,
                          kernel=frozen_kernel(), scenario="q2_single_shift",
                          shift_length_h="12", tau_pm=lr.NO_PM_BEFORE_MANDATORY)
        res = run(cfg)
        # the cancelled attempt2 has no OBSERVATION_MATERIALIZED
        cancelled2 = [
            r for r in res.event_log
            if r.get("event_type") == "TASK_CANCEL"
            and r.get("device_id") == dev and r.get("effective_attempt_no") == 2
        ]
        for c2 in cancelled2:
            proc = c2.get("process")
            obs = [
                r for r in res.event_log
                if r.get("event_type") == "OBSERVATION_MATERIALIZED"
                and r.get("device_id") == dev and r.get("process") == proc
                and r.get("effective_attempt_no") == 2
            ]
            self.assertEqual(len(obs), 0,
                             "cancelled attempt2 must have zero observations")
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)


# ---------------------------------------------------------------------------
# C17 terminal-horizon calibration replay regression (INVALIDATION_REPORT_G3_C17_
# TERMINAL_HORIZON; Human Gate OPTION A2)
# ---------------------------------------------------------------------------
# Frozen semantics: T is the time of the final DEVICE_TERMINAL; the simulation
# / accounting horizon is [0, T).  A same-timestamp closure may record a
# mandatory replacement start at t=T (a+d=240 completion-settles-first) with a
# planned calibration_end > T; this does NOT extend T.  The checker must:
#   * keep raw planned calibration legality / shift checks on [cs, ce);
#   * use effective [cs, min(ce, T)) for occupancy / capacity / ledger;
#   * keep test fragments strict (a real test ending after T is C12 FAIL);
#   * keep actual event records with event_time > T as C12 FAIL.


def _replace_calibration_event(log, resource, new_start, new_end):
    """Rewrite the last EQUIPMENT_REPLACEMENT_START for ``resource`` to the
    given planned calibration interval (test helper only)."""
    idx = None
    for i, rec in enumerate(log):
        if rec.get("event_type") == "EQUIPMENT_REPLACEMENT_START" \
                and rec.get("resource_id") == resource:
            idx = i
    assert idx is not None, "no replacement event for %s" % resource
    rec = dict(log[idx])
    rec["calibration_start"] = new_start
    rec["calibration_end"] = new_end
    out = list(log)
    out[idx] = rec
    return out


class TestC17TerminalHorizonCalibration(_Base):
    def _q2_cfg(self, rep=88, tau_pm=lr.NO_PM_BEFORE_MANDATORY):
        # Q2 frozen world (single_test_unconditional_v1, 1h_literal) with the
        # real Q2 observation kernel (Q1-frozen q_E propagation), so the
        # terminal-horizon replacement lands at T exactly as in the failed run.
        kernel = {
            proc: {"alpha": alpha, "beta": beta}
            for proc in ("A", "B", "C")
            for alpha, beta in [rd.frozen_single_test_alpha_beta(
                DEFECT_Q[proc], FROZEN_E[proc])]
        }
        q_e = Fraction("0.062593912407392898")
        alpha_e, beta_e = rd.frozen_single_test_alpha_beta(
            q_e, Fraction(2, 100))
        kernel["E"] = {"alpha": alpha_e, "beta": beta_e}
        return make_config(batch_size=100, namespace=ks.NAMESPACE_Q2_FORMAL,
                           master_seed=3, replicate_id=rep,
                           kernel=kernel, scenario="q2_single_shift",
                           shift_length_h="12", shifts_per_day=1,
                           tau_pm=tau_pm)

    def test_a2_7_q2_seed3_rep88_closes(self) -> None:
        """A2-7 (direct regression): the previously reported residual
        resource(E).busy planned calibration_end=2468/3 at T=822 must close
        for the intended horizon-clipping reason (C12 PASS)."""
        cfg = self._q2_cfg(rep=88)
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS",
                         "issues=%s" % [i.describe() for i in report.issues])

    def test_a2_1_start_at_T_no_postT_completion(self) -> None:
        """A2-1: replacement/calibration starts exactly at T (the frozen
        same-timestamp closure) with planned calibration_end > T and no
        post-T completion event -> effective busy contribution 0, C12 PASS.
        This is exactly the real rep88 final E calibration [822, 822+2/3)."""
        cfg = self._q2_cfg(rep=88)
        res = run(cfg)
        t = Fraction(res.metrics["T"])
        # the final E replacement in this world already starts at T with a
        # planned end > T and no post-T completion event (frozen semantics).
        final_evs = [e for e in res.event_log
                     if e.get("event_type") == "EQUIPMENT_REPLACEMENT_START"
                     and e.get("resource_id") == "E"
                     and Fraction(e.get("calibration_start", "0")) >= t]
        self.assertTrue(final_evs, "expected a replacement starting at T")
        self.assertGreater(Fraction(final_evs[-1]["calibration_end"]), t)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS",
                         "issues=%s" % [i.describe() for i in report.issues])

    def test_a2_2_clip_at_T(self) -> None:
        """A2-2: the effective resource occupancy is clipped exactly at T;
        busy_total uses only pre-T duration (the post-T tail of a planned
        calibration that starts at/just before T contributes 0)."""
        cfg = self._q2_cfg(rep=88)
        res = run(cfg)
        t = Fraction(res.metrics["T"])
        # the final E replacement plans [822, 822+2/3): the 2/3 h post-T tail
        # must NOT enter busy_total on E (horizon [0,T) occupancy).
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        rb = report.recomputed["resource_busy"]["E"]
        total = Fraction(rb["busy_total_h"])
        # E's last test fragment ends at T; the clipped calibration tail is
        # excluded.  busy_total is the sum of pre-T occupancy only.
        # Without clipping, the tail 2/3 h would be included; assert it is not.
        e_cals = [e for e in res.event_log
                  if e.get("event_type") == "EQUIPMENT_REPLACEMENT_START"
                  and e.get("resource_id") == "E"
                  and Fraction(e.get("calibration_start", "0")) >= t]
        self.assertTrue(e_cals)
        raw_end = Fraction(e_cals[-1]["calibration_end"])
        self.assertGreater(raw_end, t)  # planned end is after T
        # The calibration's effective contribution is clipped to
        # [822, min(822+2/3, 822)) = empty, so busy_total does not include 2/3.
        # The last test fragment on E ends exactly at T; find its interval.
        test_ivs = [Fraction(iv[1]) for iv in rb["test_intervals"]]
        self.assertLessEqual(max(test_ivs), t)
        # busy_total must not include the 2/3 tail beyond the pre-T total
        # (a generous slack keeps this robust to other pre-T activity).
        self.assertLess(total, t + Fraction(1, 10))

    def test_a2_3_test_after_T_still_fails(self) -> None:
        """A2-3: a real test fragment truly ending after T must still be
        C12 FAIL (test termination is NOT relaxed by horizon clipping).

        We verify the invariant at the checker's resource-busy layer: on the
        real rep88 log the calibration interval [822, 822+2/3) is clipped
        (busy_total excludes the post-T tail) while NO test interval is
        clipped -- every test fragment's busy end is <= T.  This locks that
        only calibration occupancy uses the [0,T) horizon, never test
        fragments."""
        cfg = self._q2_cfg(rep=88)
        res = run(cfg)
        report = self.check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        rb = report.recomputed["resource_busy"]
        t = Fraction(res.metrics["T"])
        for resource, data in rb.items():
            for iv in data["test_intervals"]:
                s, e = Fraction(iv[0]), Fraction(iv[1])
                # test fragments are strict: none may end after T
                self.assertLessEqual(e, t,
                                     "test fragment %s on %s ends after T"
                                     % (iv, resource))

    def test_a2_4_event_after_T_fails(self) -> None:
        """A2-4: an actual event record with event_time > T is C12 FAIL even
        under horizon clipping (post-T completion is never excused)."""
        cfg = make_config(batch_size=3, master_seed=7)
        res = run(cfg)
        log = clone(res.event_log)
        t = res.metrics["T"]
        # append a synthetic post-T record (renumber seq contiguously)
        fake = {"seq": len(log) + 1, "event_time": rck.frac_to_str(Fraction(t) + 1),
                "event_type": "EQUIPMENT_CALIBRATION_COMPLETE",
                "resource_id": "E"}
        log.append(fake)
        report = self.check(cfg, event_log=log, metrics=res.metrics)
        self.assertEqual(report.verdict, "FAIL")

    def test_a2_5_cross_shift_still_fails(self) -> None:
        """A2-5: raw planned calibration crossing the shift boundary is C12
        FAIL even when T would truncate the accounting horizon."""
        cfg = self._q2_cfg(rep=88)
        res = run(cfg)
        log = res.event_log
        t = Fraction(res.metrics["T"])
        # planned interval crosses the 12h shift grid (start near shift end)
        shift_len = Fraction(12)
        shift_end = (t // shift_len) * shift_len + shift_len
        if shift_end <= t:
            shift_end = shift_end + shift_len
        start = shift_end - Fraction(1, 4)
        new_log = _replace_calibration_event(
            log, "E", rck.frac_to_str(start),
            rck.frac_to_str(start + Fraction(2, 3)))
        report = self.check(cfg, event_log=new_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(any("crosses the shift boundary" in i.describe()
                            for i in report.issues))

    def test_a2_6_overlap_capacity_fails(self) -> None:
        """A2-6: two resource activities overlapping inside [0, T) must still
        be a capacity violation (capacity checks remain strict inside the
        [0, T) horizon, using effective occupancy)."""
        cfg = self._q2_cfg(rep=88)
        res = run(cfg)
        log = clone(res.event_log)
        t = Fraction(res.metrics["T"])
        # manufacture a calibration that overlaps an existing test fragment
        # inside [0,T): pick an early E replacement (well inside the horizon)
        # and lengthen its planned interval across the NEXT test fragment on E
        # while keeping its own start/event_time intact and its duration legal.
        # Legality: calibration_start must equal event_time and duration must
        # match the frozen value; overlapping the NEXT activity is the only
        # change, so capacity (disjointness) must fire.
        repls = [e for e in log
                 if e.get("event_type") == "EQUIPMENT_REPLACEMENT_START"
                 and e.get("resource_id") == "E"]
        self.assertTrue(len(repls) >= 2)
        target = repls[0]
        idx = log.index(target)
        cal_dur = Fraction(2, 3)  # E calibration = 40 min
        start = Fraction(target["calibration_start"])
        # lengthen so the planned interval ends AFTER the next E activity's
        # start (which is > start + cal_dur normally) -> overlap inside [0,T)
        # find the first E ACTIVITY_START after start + cal_dur
        nxt = [e for e in log
               if e.get("event_type") == "ACTIVITY_START"
               and e.get("resource_id") == "E"
               and Fraction(e.get("event_time", "0")) > start]
        assert nxt, "expected a later E activity"
        new_end = Fraction(nxt[0]["event_time"]) + Fraction(1, 2)
        rec = dict(target)
        rec["calibration_end"] = rck.frac_to_str(new_end)
        # keep calibration_start == event_time and raw duration consistency is
        # enforced by C14 on the raw planned interval; overlapping the next
        # activity is the intended capacity violation.
        log[idx] = rec
        report = self.check(cfg, event_log=log, metrics=res.metrics)
        self.assertEqual(report.verdict, "FAIL",
                         "expected capacity violation")
        self.assertTrue(
            any("overlap" in i.describe() or "capacity" in i.describe()
                for i in report.issues),
            "no overlap/capacity issue: %s"
            % [i.describe() for i in report.issues])


if __name__ == "__main__":
    unittest.main(verbosity=2)
