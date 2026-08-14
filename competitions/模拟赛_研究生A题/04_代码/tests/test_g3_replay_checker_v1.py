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


if __name__ == "__main__":
    unittest.main(verbosity=2)
