# -*- coding: utf-8 -*-
"""Unit tests for G3-SPEC-V1.0 S4: g3_quality_oracle_v1 (CR-V3.1/C06 full
G3-layer independent quality-separation oracle).

Scope
-----
The object under test is ``04_代码/checker/g3_quality_oracle_v1.py``, the E2
independent oracle of G3-SPEC-V1.0 section 9 (c06_quality_separation).  The
test file is the ONLY place allowed to call the main keyed random DES
(``04_代码/main_model/g3/random_des_v1.py``, S3) to generate the event logs
under test.  The oracle module itself never imports the main DES.

Frozen-contract coverage (the 9 required points plus extras):

  1. rebuild every device's terminal quality result from the event log and
     show 全等 with the DES (multi-seed, small batches; q2/q3 calendars;
     equipment-failure path);
  2. D-generation consistency, including the ``not_created`` case
     (early exit never materializes D; always-pass always creates it; an
     E-exit device keeps its created D; a frozen-kernel batch covers both);
  3. GP/BP/GE/BE four-cell categories agree per device and satisfy the frozen
     semantics (GP/BP only for passed; GE/BE only for exited; BP == PL;
     GE == PW);
  4. PL/PW contributions agree per device and match the DES batch metrics;
  5. policy variants (different tau_pm, same canonical world) leave every
     quality term invariant (the separation proposition) -- the oracle is
     time-layer-free by construction;
  6. isolation: static AST scan (no random_des_v1 / des.* /
     lifetime_regeneration_v1 / other checker / tests imports; only
     g3.key_schema_v1) + dynamic subprocess run without the main DES ever
     being imported;
  7. no binary float in canonical paths (AST scan + runtime report scan);
  8. deterministic reproducibility (byte-identical canonical reports);
  9. independent U derivation: the oracle recomputes U from key_schema_v1 in
     the same world and ignores the DES log's recorded ``u`` / ``u_key`` /
     ``true_state`` values (tamper test).

Plus: fault injection (flipped outcome / extra observation / wrong terminal /
wrong D state / missing terminal must FAIL, proving the oracle is not
always-PASS), config/parameter validation (fail loudly, never a silent
default), and the frozen output-field contract of the per-device report.

All expectations derive from the frozen G3-SPEC-V1.0 contract, V3.1 section 9
and parameters.csv; no formal competition numbers are produced.
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

from checker import g3_quality_oracle_v1 as qo  # noqa: E402
from g3 import key_schema_v1 as ks              # noqa: E402
from g3 import lifetime_regeneration_v1 as lr   # noqa: E402  (tau_pm sentinel)
from g3 import random_des_v1 as rd              # noqa: E402  (test-only log generation)
from des import state_models_v1 as sm           # noqa: E402

PARAMS_CSV = BASE / "02_数据" / "parameters.csv"
ORACLE_PATH = CODE_DIR / "checker" / "g3_quality_oracle_v1.py"
CHECKER_DIR = CODE_DIR / "checker"

NS = ks.NAMESPACE_DEVELOPMENT_UNIT
SEED = 7
REP = 0

# Frozen defect probabilities (parameters.csv P026-P029), independently
# restated only for building test kernels; the oracle reads the csv itself.
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
    """Shared oracle-run helper."""

    def oracle_check(self, config, event_log=None, metrics=None,
                     parameters=PARAMS_CSV) -> qo.OracleReport:
        if event_log is None:
            event_log = run(config).event_log
        return qo.check_quality_oracle(
            event_log, config.to_dict(),
            parameters_csv=str(parameters), metrics=metrics,
        )


# ---------------------------------------------------------------------------
# 1. Rebuild per-device finals from the event log == DES (multi-seed small
#    batches, q2/q3 calendars, equipment-failure path)
# ---------------------------------------------------------------------------


class TestRebuildMatchesDes(_Base):
    def test_multiseed_small_batches(self) -> None:
        for seed in (1, 2, 3, 7):
            for batch in (1, 3, 4, 5):
                cfg = make_config(batch_size=batch, master_seed=seed)
                res = run(cfg)
                report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
                self.assertEqual(report.verdict, "PASS",
                                 "%s; issues=%s" % (report.summarize(), report.issues))
                self.assertEqual(report.issues, [])
                for dev_id in range(1, batch + 1):
                    comp = report.comparisons[dev_id]
                    self.assertTrue(comp.equal,
                                    "device %d seed %d: %s" % (dev_id, seed, comp.differences))
                self.assertEqual(report.oracle_aggregate["S"], res.metrics["S"])
                self.assertEqual(report.oracle_aggregate["PL"], res.metrics["PL"])
                self.assertEqual(report.oracle_aggregate["PW"], res.metrics["PW"])

    def test_q2_single_shift_calendar(self) -> None:
        cfg = make_config(batch_size=8, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        self.assertEqual(len(report.comparisons), 8)
        # the oracle never parses times: report contains no time values
        self.assertEqual(report.to_dict()["devices"]["1"]["oracle"]["true_terminal_state"],
                         report.comparisons[1].oracle.true_terminal_state)

    def test_q3_two_shift_calendar(self) -> None:
        # K=12: the DES processes the whole batch (K<=10 with batch>=4 hits a
        # DES premature-termination path -- see test_q3_premature_stop_detected).
        cfg = make_config(batch_size=6, master_seed=7,
                          scenario="q3_two_shift", shift_length_h="12", shifts_per_day=2)
        res = run(cfg)
        self.assertEqual(
            len(records(res.event_log, "TRUE_STATE_GENERATED")), 6,
            "the DES must process the full batch (all 6 devices created)",
        )
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        self.assertEqual(len(report.comparisons), 6)

    def test_q3_premature_stop_detected(self) -> None:
        # REAL DES finding (not an injected fault), documented here as the
        # oracle's evidence: with the q3 calendar and K=9, batch>=4 the random
        # DES can terminate after 3 devices -- `_is_terminal` treats in-flight
        # turnovers as no work, so devices 4..N are never created (a full-batch
        # / C18-liveness violation; G3-SPEC-V1.0 sections 6 and 13).  The
        # oracle must FAIL with the missing devices, never silently pass.
        cfg = make_config(batch_size=6, master_seed=7,
                          scenario="q3_two_shift", shift_length_h="9", shifts_per_day=2)
        res = run(cfg)
        created = len(records(res.event_log, "TRUE_STATE_GENERATED"))
        if created == 6:
            # the DES was fixed upstream; the finding no longer reproduces.
            self.skipTest("DES no longer reproduces the premature stop")
        self.assertLess(created, 6, "current DES behavior: batch not fully created")
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(
            any("missing from the log" in issue for issue in report.issues),
            report.issues,
        )

    def test_equipment_failure_path(self) -> None:
        # seed 51: the B generation-1 lifetime interrupts the B1 fragment; the
        # retry of the SAME effective attempt completes and consumes the same
        # keyed U.  The oracle's effective-observation band is unaffected by
        # the interrupted fragment (separation proposition).
        cfg = make_config(batch_size=1, master_seed=51,
                          durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"})
        res = run(cfg)
        self.assertEqual(len(records(res.event_log, rd.EVENT_EQUIPMENT_FAILURE)), 1)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        self.assertTrue(report.comparisons[1].equal, report.comparisons[1].differences)


# ---------------------------------------------------------------------------
# 2. D generation consistency (including not_created)
# ---------------------------------------------------------------------------


class TestDGeneration(_Base):
    def test_early_exit_never_materializes_d(self) -> None:
        # all-ABNORMAL kernel: every device exits via A2 before A/B/C all-PASS
        # -> D is never created (not_created case).
        kernel = {p: {"alpha": Fraction(1), "beta": Fraction(0)}
                  for p in ("A", "B", "C", "E")}
        cfg = make_config(batch_size=6, kernel=kernel)
        res = run(cfg)
        self.assertEqual(len(records(res.event_log, "D_CREATED")), 0)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        for dev_id in range(1, 7):
            comp = report.comparisons[dev_id]
            self.assertFalse(comp.oracle.d_generated)
            self.assertEqual(comp.oracle.d_value, qo.D_NOT_CREATED)
            self.assertEqual(comp.des.d_value, qo.D_NOT_CREATED)
            self.assertEqual(comp.oracle.true_terminal_state, qo.TERMINAL_EXITED)

    def test_all_pass_always_creates_d(self) -> None:
        # always-PASS kernel: every device reaches E -> D created exactly once.
        kernel = {p: {"alpha": Fraction(0), "beta": Fraction(1)}
                  for p in ("A", "B", "C")}
        kernel["E"] = {"alpha": Fraction(0), "beta": Fraction(1)}
        cfg = make_config(batch_size=6, kernel=kernel)
        res = run(cfg)
        self.assertEqual(len(records(res.event_log, "D_CREATED")), 6)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        for dev_id in range(1, 7):
            comp = report.comparisons[dev_id]
            self.assertTrue(comp.oracle.d_generated)
            self.assertIn(comp.oracle.d_value, (qo.D_NORMAL, qo.D_PROBLEM))
            self.assertEqual(comp.oracle.true_terminal_state, qo.TERMINAL_PASSED)

    def test_e_exit_keeps_created_d(self) -> None:
        # A/B/C always pass, E always abnormal: D is created (A/B/C all-PASS)
        # and the device exits via the E retest -- D stays created.
        kernel = {p: {"alpha": Fraction(0), "beta": Fraction(1)}
                  for p in ("A", "B", "C")}
        kernel["E"] = {"alpha": Fraction(1), "beta": Fraction(0)}
        cfg = make_config(batch_size=5, kernel=kernel)
        res = run(cfg)
        self.assertEqual(len(records(res.event_log, "D_CREATED")), 5)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        for dev_id in range(1, 6):
            comp = report.comparisons[dev_id]
            self.assertTrue(comp.oracle.d_generated)
            self.assertEqual(comp.oracle.true_terminal_state, qo.TERMINAL_EXITED)

    def test_frozen_kernel_batch_covers_both_cases(self) -> None:
        # seed 7, N=30, frozen kernel: some devices exit early (no D) while
        # others create D (one exits via E with D kept) -- both cases in one
        # deterministic batch, and every device is 全等 with the DES.
        cfg = make_config(batch_size=30, master_seed=7)
        res = run(cfg)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        created = sum(1 for c in report.comparisons.values() if c.oracle.d_generated)
        not_created = sum(1 for c in report.comparisons.values() if not c.oracle.d_generated)
        self.assertGreater(created, 0)
        self.assertGreater(not_created, 0)
        self.assertEqual(created + not_created, 30)


# ---------------------------------------------------------------------------
# 3. GP/BP/GE/BE four-cell categories agree per device
# ---------------------------------------------------------------------------


class TestCategories(_Base):
    def test_four_cell_internal_consistency(self) -> None:
        cfg = make_config(batch_size=40, master_seed=7)
        res = run(cfg)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        agg = report.oracle_aggregate
        self.assertEqual(agg["S"], agg["GP"] + agg["BP"])
        self.assertEqual(agg["exited"], agg["GE"] + agg["BE"])
        self.assertEqual(agg["PL"], agg["BP"])
        self.assertEqual(agg["PW"], agg["GE"])
        self.assertEqual(agg["S"] + agg["exited"], 40)
        for comp in report.comparisons.values():
            self.assertIn(comp.oracle.category, qo.CATEGORIES)
            if comp.oracle.true_terminal_state == qo.TERMINAL_PASSED:
                self.assertIn(comp.oracle.category, (qo.CATEGORY_GP, qo.CATEGORY_BP))
            else:
                self.assertIn(comp.oracle.category, (qo.CATEGORY_GE, qo.CATEGORY_BE))

    def test_forced_ge_be(self) -> None:
        # all-ABNORMAL: every device exits; GE iff no A/B/C true problem,
        # BE iff at least one (D never created for early exits).
        kernel = {p: {"alpha": Fraction(1), "beta": Fraction(0)}
                  for p in ("A", "B", "C", "E")}
        cfg = make_config(batch_size=30, kernel=kernel)
        res = run(cfg)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        for comp in report.comparisons.values():
            self.assertIn(comp.oracle.category, (qo.CATEGORY_GE, qo.CATEGORY_BE))
            has_problem = any(comp.oracle.true_abc[p] for p in ("A", "B", "C"))
            if has_problem:
                self.assertEqual(comp.oracle.category, qo.CATEGORY_BE)
                self.assertEqual(comp.oracle.pl_contribution, 0)
                self.assertEqual(comp.oracle.pw_contribution, 0)
            else:
                self.assertEqual(comp.oracle.category, qo.CATEGORY_GE)
                self.assertEqual(comp.oracle.pw_contribution, 1)

    def test_forced_gp_bp(self) -> None:
        # always-PASS: every device passes; GP iff no generated problem
        # (A/B/C true states + created D), BP iff at least one.
        kernel = {p: {"alpha": Fraction(0), "beta": Fraction(1)}
                  for p in ("A", "B", "C")}
        kernel["E"] = {"alpha": Fraction(0), "beta": Fraction(1)}
        cfg = make_config(batch_size=30, kernel=kernel)
        res = run(cfg)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        for comp in report.comparisons.values():
            self.assertIn(comp.oracle.category, (qo.CATEGORY_GP, qo.CATEGORY_BP))
            has_problem = (
                any(comp.oracle.true_abc[p] for p in ("A", "B", "C"))
                or comp.oracle.d_value == qo.D_PROBLEM
            )
            if has_problem:
                self.assertEqual(comp.oracle.category, qo.CATEGORY_BP)
                self.assertEqual(comp.oracle.pl_contribution, 1)
            else:
                self.assertEqual(comp.oracle.category, qo.CATEGORY_GP)
                self.assertEqual(comp.oracle.pl_contribution, 0)


# ---------------------------------------------------------------------------
# 4. PL/PW contributions agree per device and with the DES metrics
# ---------------------------------------------------------------------------


class TestPlPw(_Base):
    def test_pl_pw_matches_des_metrics(self) -> None:
        cfg = make_config(batch_size=60, master_seed=7)
        res = run(cfg)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        self.assertEqual(report.oracle_aggregate["S"], res.metrics["S"])
        self.assertEqual(report.oracle_aggregate["PL"], res.metrics["PL"])
        self.assertEqual(report.oracle_aggregate["PW"], res.metrics["PW"])
        # per-device contributions sum to the aggregates
        self.assertEqual(
            sum(c.oracle.pl_contribution for c in report.comparisons.values()),
            report.oracle_aggregate["PL"],
        )
        self.assertEqual(
            sum(c.oracle.pw_contribution for c in report.comparisons.values()),
            report.oracle_aggregate["PW"],
        )

    def test_pl_pw_semantics_forced(self) -> None:
        # always-pass: PL == #devices with a generated problem; PW == 0
        kernel = {p: {"alpha": Fraction(0), "beta": Fraction(1)}
                  for p in ("A", "B", "C")}
        kernel["E"] = {"alpha": Fraction(0), "beta": Fraction(1)}
        cfg = make_config(batch_size=20, kernel=kernel)
        res = run(cfg)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        problems = sum(
            1 for c in report.comparisons.values()
            if any(c.oracle.true_abc[p] for p in ("A", "B", "C"))
            or c.oracle.d_value == qo.D_PROBLEM
        )
        self.assertEqual(report.oracle_aggregate["PL"], problems)
        self.assertEqual(report.oracle_aggregate["PW"], 0)
        # always-exit: PW == #exited with no generated problem; PL == 0
        kernel2 = {p: {"alpha": Fraction(1), "beta": Fraction(0)}
                   for p in ("A", "B", "C", "E")}
        cfg2 = make_config(batch_size=20, kernel=kernel2)
        res2 = run(cfg2)
        report2 = self.oracle_check(cfg2, event_log=res2.event_log, metrics=res2.metrics)
        self.assertEqual(report2.verdict, "PASS", report2.issues)
        normal_exited = sum(
            1 for c in report2.comparisons.values()
            if not any(c.oracle.true_abc[p] for p in ("A", "B", "C"))
        )
        self.assertEqual(report2.oracle_aggregate["PW"], normal_exited)
        self.assertEqual(report2.oracle_aggregate["PL"], 0)


# ---------------------------------------------------------------------------
# 5. Policy variants (different tau_pm, same canonical world): quality terms
#    invariant (separation proposition)
# ---------------------------------------------------------------------------


class TestPolicyVariantInvariance(_Base):
    def test_tau_pm_quality_invariance(self) -> None:
        kwargs = dict(
            batch_size=6,
            master_seed=7,
            durations={"A": "40", "B": "40", "C": "40", "E": "3"},
        )
        cfg_nopm = make_config(tau_pm=lr.NO_PM_BEFORE_MANDATORY, **kwargs)
        cfg_pm = make_config(tau_pm=Fraction(120), **kwargs)
        res_nopm = run(cfg_nopm)
        res_pm = run(cfg_pm)
        # the schedules genuinely differ (preventive replacement changes T)
        self.assertNotEqual(res_nopm.canonical_event_log(), res_pm.canonical_event_log())
        rep_nopm = self.oracle_check(cfg_nopm, event_log=res_nopm.event_log,
                                     metrics=res_nopm.metrics)
        rep_pm = self.oracle_check(cfg_pm, event_log=res_pm.event_log,
                                   metrics=res_pm.metrics)
        self.assertEqual(rep_nopm.verdict, "PASS", rep_nopm.issues)
        self.assertEqual(rep_pm.verdict, "PASS", rep_pm.issues)
        # per-device quality terms invariant across the policy variant
        for dev_id in range(1, 7):
            o1 = rep_nopm.comparisons[dev_id].oracle
            o2 = rep_pm.comparisons[dev_id].oracle
            self.assertEqual(o1.true_terminal_state, o2.true_terminal_state, dev_id)
            self.assertEqual(o1.d_generated, o2.d_generated, dev_id)
            self.assertEqual(o1.d_value, o2.d_value, dev_id)
            self.assertEqual(o1.final_pass_exit, o2.final_pass_exit, dev_id)
            self.assertEqual(o1.category, o2.category, dev_id)
            self.assertEqual(o1.pl_contribution, o2.pl_contribution, dev_id)
            self.assertEqual(o1.pw_contribution, o2.pw_contribution, dev_id)
        # batch aggregates invariant (the separation proposition)
        self.assertEqual(rep_nopm.oracle_aggregate, rep_pm.oracle_aggregate)
        self.assertEqual(res_nopm.metrics["S"], res_pm.metrics["S"])
        self.assertEqual(res_nopm.metrics["PL"], res_pm.metrics["PL"])
        self.assertEqual(res_nopm.metrics["PW"], res_pm.metrics["PW"])

    def test_tau_pm_168_variant(self) -> None:
        kwargs = dict(
            batch_size=6,
            master_seed=7,
            durations={"A": "40", "B": "40", "C": "40", "E": "3"},
        )
        cfg_a = make_config(tau_pm=lr.NO_PM_BEFORE_MANDATORY, **kwargs)
        cfg_b = make_config(tau_pm=Fraction(168), **kwargs)
        res_a = run(cfg_a)
        res_b = run(cfg_b)
        rep_a = self.oracle_check(cfg_a, event_log=res_a.event_log, metrics=res_a.metrics)
        rep_b = self.oracle_check(cfg_b, event_log=res_b.event_log, metrics=res_b.metrics)
        self.assertEqual(rep_a.verdict, "PASS", rep_a.issues)
        self.assertEqual(rep_b.verdict, "PASS", rep_b.issues)
        self.assertEqual(rep_a.oracle_aggregate, rep_b.oracle_aggregate)


# ---------------------------------------------------------------------------
# 6. Isolation (CR-V3.1/C19): static AST scan + dynamic run without the main
#    DES ever being imported
# ---------------------------------------------------------------------------


class TestIsolation(_Base):
    def test_static_ast_scan(self) -> None:
        source = ORACLE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: list[tuple[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend((alias.name, "") for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.extend(
                    (node.module or "", alias.name) for alias in node.names
                )
        # the ONLY main_model import allowed is the shared key schema (P061);
        # the import graph is the authoritative isolation contract.
        g3_imports = [(m, n) for (m, n) in imported if m == "g3"]
        self.assertEqual(g3_imports, [("g3", "key_schema_v1")])
        for (module, name) in imported:
            self.assertFalse(module.startswith("des"), (module, name))
            self.assertFalse(module.startswith("tests"), (module, name))
            self.assertFalse(module.startswith("checker"), (module, name))
            self.assertFalse(
                "random_des" in module or "random_des" in name, (module, name)
            )
            self.assertFalse(
                "lifetime" in module or "lifetime" in name, (module, name)
            )
            self.assertFalse(
                "deterministic" in module or "deterministic" in name,
                (module, name),
            )
            self.assertFalse(
                "state_models" in module or "state_models" in name, (module, name)
            )
            self.assertFalse(
                "observation_calibration" in module
                or "observation_calibration" in name,
                (module, name),
            )
        # no dangerous execution / non-determinism constructs anywhere in the
        # oracle's CODE (the module docstring may legitimately NAME the
        # forbidden modules while documenting the isolation boundary).
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name in ("random", "subprocess", "os")
                for alias in node.names
            ):
                self.fail("forbidden stdlib import in oracle: %s" % (node,))
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in (
                    "eval", "exec", "__import__", "compile", "hash",
                ):
                    self.fail("forbidden dynamic call in oracle: %s" % func.id)
                if (isinstance(func, ast.Attribute)
                        and func.attr in ("system", "popen", "run", "call", "Popen")
                        and isinstance(func.value, ast.Name)
                        and func.value.id in ("os", "subprocess")):
                    self.fail("forbidden os/subprocess call in oracle")
        self.assertNotIn("import random", source)
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("import os", source)
        self.assertNotIn("hash(", source)

    def test_dynamic_run_without_main_des(self) -> None:
        # subprocess with the checker + main_model dirs on PYTHONPATH: the
        # oracle must run end-to-end and never load random_des_v1 /
        # lifetime_regeneration_v1 / the des package.
        cfg = make_config(batch_size=4, master_seed=7)
        res = run(cfg)
        with tempfile.TemporaryDirectory(prefix="g3_oracle_iso_") as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "event_log.json").write_text(
                json.dumps(res.event_log, ensure_ascii=False), encoding="utf-8")
            (tmp_path / "config.json").write_text(
                json.dumps(cfg.to_dict(), ensure_ascii=False), encoding="utf-8")
            (tmp_path / "metrics.json").write_text(
                json.dumps(res.metrics, ensure_ascii=False), encoding="utf-8")
            script = (
                "import json, sys\n"
                "import g3_quality_oracle_v1 as qo\n"
                "log = json.load(open('event_log.json', encoding='utf-8'))\n"
                "cfg = json.load(open('config.json', encoding='utf-8'))\n"
                "metrics = json.load(open('metrics.json', encoding='utf-8'))\n"
                "rep = qo.check_quality_oracle(log, cfg, "
                "parameters_csv=r'%s', metrics=metrics)\n"
                "print(rep.summarize())\n"
                "assert rep.verdict == 'PASS', rep.issues\n"
                "forbidden = ('random_des_v1', 'lifetime_regeneration_v1', 'des')\n"
                "loaded = [m for m in sys.modules if any(f in m for f in forbidden)]\n"
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
                "oracle failed without the main DES:\n%s\n%s"
                % (proc.stdout, proc.stderr),
            )
            self.assertIn("PASS", proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)


# ---------------------------------------------------------------------------
# 7. No binary float in canonical paths
# ---------------------------------------------------------------------------


class TestNoFloat(_Base):
    def test_no_float_literal_or_call(self) -> None:
        source = ORACLE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                self.fail("binary float literal in oracle: %r" % (node.value,))
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "float"):
                self.fail("float() builtin call in oracle")
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "float"):
                self.fail("float method call in oracle")
        self.assertNotIn("import random", source)
        self.assertNotIn("hash(", source)

    def test_report_contains_no_float(self) -> None:
        cfg = make_config(batch_size=5, master_seed=7)
        res = run(cfg)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
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
# 8. Deterministic reproducibility
# ---------------------------------------------------------------------------


class TestDeterminism(_Base):
    def test_repeat_identical_report(self) -> None:
        cfg = make_config(batch_size=5, master_seed=7,
                          scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        r1 = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        r2 = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(
            json.dumps(r1.to_dict(), sort_keys=True),
            json.dumps(r2.to_dict(), sort_keys=True),
        )
        # a pre-parsed QualityOracleConfig input gives the identical report
        r3 = qo.check_quality_oracle(
            res.event_log, qo.parse_config(cfg.to_dict()),
            parameters_csv=str(PARAMS_CSV), metrics=res.metrics,
        )
        self.assertEqual(
            json.dumps(r1.to_dict(), sort_keys=True),
            json.dumps(r3.to_dict(), sort_keys=True),
        )


# ---------------------------------------------------------------------------
# 9. Independent U derivation: same-world recomputation; the DES log's
#    recorded u / u_key / true_state values are never read
# ---------------------------------------------------------------------------


class TestIndependentU(_Base):
    def test_recompute_matches_key_schema(self) -> None:
        for device in (1, 2, 3):
            for sub in ("A", "B", "C"):
                self.assertEqual(
                    qo.u_x(NS, REP, device, sub, SEED),
                    ks.u_x(NS, REP, device, sub, SEED),
                )
            for proc in ("A", "B", "C", "E"):
                for attempt in (1, 2):
                    self.assertEqual(
                        qo.u_y(NS, REP, device, proc, attempt, SEED),
                        ks.u_y(NS, REP, device, proc, attempt, SEED),
                    )
            self.assertEqual(
                qo.u_d(NS, REP, device, SEED),
                ks.u_d(NS, REP, device, SEED),
            )

    def test_log_u_values_ignored(self) -> None:
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        base = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(base.verdict, "PASS", base.issues)
        # tamper EVERY recorded u / u_key / true_state value in a deep copy
        tampered = clone(res.event_log)
        for rec in tampered:
            if not isinstance(rec, dict):
                continue
            for key in ("u", "u_key"):
                if key in rec:
                    rec[key] = "TAMPERED_VALUE"
            if "true_state" in rec:
                ts = rec["true_state"]
                rec["true_state"] = (
                    {k: (not v) for k, v in ts.items()}
                    if isinstance(ts, dict)
                    else (not ts)
                )
        tampered_report = self.oracle_check(cfg, event_log=tampered, metrics=res.metrics)
        self.assertEqual(
            json.dumps(base.to_dict(), sort_keys=True),
            json.dumps(tampered_report.to_dict(), sort_keys=True),
        )


# ---------------------------------------------------------------------------
# Fault injection: the oracle must FAIL on DES discrepancies (not always-PASS)
# ---------------------------------------------------------------------------


class TestFaultInjection(_Base):
    def test_flipped_observation_outcome_detected(self) -> None:
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        log = clone(res.event_log)
        obs = records(log, "OBSERVATION_MATERIALIZED")
        rec = obs[0]
        rec["outcome"] = (
            qo.OUTCOME_ABNORMAL if rec["outcome"] == qo.OUTCOME_PASS
            else qo.OUTCOME_PASS
        )
        report = self.oracle_check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")
        comp = report.comparisons[rec["device_id"]]
        self.assertFalse(comp.equal)
        self.assertTrue(
            any("observation" in d for d in comp.differences), comp.differences
        )

    def test_extra_observation_detected(self) -> None:
        # always-exit kernel: E is never reached, so a fabricated E
        # observation lies outside the canonical chain for every device.
        kernel = {p: {"alpha": Fraction(1), "beta": Fraction(0)}
                  for p in ("A", "B", "C", "E")}
        cfg = make_config(batch_size=4, kernel=kernel)
        res = run(cfg)
        log = clone(res.event_log)
        log.append({
            "seq": 999999,
            "event_time": "0",
            "event_type": "OBSERVATION_MATERIALIZED",
            "device_id": 1,
            "process": "E",
            "effective_attempt_no": 1,
            "outcome": "PASS",
        })
        report = self.oracle_check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(
            any("outside the canonical absorption chain" in d
                for d in report.comparisons[1].differences),
            report.comparisons[1].differences,
        )

    def test_wrong_terminal_detected(self) -> None:
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        log = clone(res.event_log)
        term = records(log, "DEVICE_TERMINAL")[0]
        term["terminal_state"] = (
            qo.TERMINAL_EXITED if term["terminal_state"] == qo.TERMINAL_PASSED
            else qo.TERMINAL_PASSED
        )
        report = self.oracle_check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")
        comp = report.comparisons[term["device_id"]]
        self.assertTrue(
            any("terminal state" in d for d in comp.differences), comp.differences
        )

    def test_wrong_d_state_detected(self) -> None:
        # always-pass kernel: every device creates D, so a corrupted D state is
        # always caught.
        kernel = {p: {"alpha": Fraction(0), "beta": Fraction(1)}
                  for p in ("A", "B", "C")}
        kernel["E"] = {"alpha": Fraction(0), "beta": Fraction(1)}
        cfg = make_config(batch_size=6, kernel=kernel)
        res = run(cfg)
        log = clone(res.event_log)
        d_recs = records(log, "D_CREATED")
        self.assertEqual(len(d_recs), 6)
        rec = d_recs[0]
        rec["d_state"] = (
            qo.D_NORMAL if rec["d_state"] == qo.D_PROBLEM else qo.D_PROBLEM
        )
        report = self.oracle_check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")
        comp = report.comparisons[rec["device_id"]]
        self.assertTrue(
            any("D value" in d for d in comp.differences), comp.differences
        )

    def test_missing_terminal_detected(self) -> None:
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        log = [
            r for r in clone(res.event_log)
            if not (r["event_type"] == "DEVICE_TERMINAL" and r["device_id"] == 1)
        ]
        report = self.oracle_check(cfg, event_log=log)
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(
            any("DEVICE_TERMINAL" in issue or "missing" in issue
                for issue in report.issues),
            report.issues,
        )

    def test_empty_log_fails(self) -> None:
        cfg = make_config(batch_size=3, master_seed=7)
        report = self.oracle_check(cfg, event_log=[])
        self.assertEqual(report.verdict, "FAIL")
        self.assertTrue(
            any("missing from the log" in issue for issue in report.issues),
            report.issues,
        )


# ---------------------------------------------------------------------------
# Config / parameter validation (fail loudly, never a silent default)
# ---------------------------------------------------------------------------


class TestValidation(_Base):
    def test_bad_config_rejected(self) -> None:
        cfg = make_config(batch_size=2).to_dict()
        cfg["namespace"] = "not_a_namespace"
        with self.assertRaises(qo.QualityOracleInputError):
            qo.parse_config(cfg)
        cfg["namespace"] = NS
        cfg["observation_kernel"]["E"]["alpha"] = 0.5  # binary float
        with self.assertRaises(qo.QualityOracleInputError):
            qo.parse_config(cfg)
        cfg2 = make_config(batch_size=2).to_dict()
        cfg2["schema_version"] = "wrong_schema"
        with self.assertRaises(qo.QualityOracleInputError):
            qo.parse_config(cfg2)

    def test_missing_parameters_fails(self) -> None:
        cfg = make_config(batch_size=2, master_seed=7)
        res = run(cfg)
        with self.assertRaises(qo.QualityOracleInputError):
            qo.check_quality_oracle(res.event_log, cfg.to_dict(), parameters_csv=None)

    def test_drifted_parameters_break_check(self) -> None:
        # a drifted q (the csv is the single authoritative source) must surface
        # as a FAIL at the check level, never a silent pass
        cfg = make_config(batch_size=6, master_seed=7)
        res = run(cfg)
        with tempfile.TemporaryDirectory(prefix="g3_oracle_params_") as tmp:
            drift = Path(tmp) / "parameters_drifted.csv"
            out = []
            for line in PARAMS_CSV.read_text(encoding="utf-8-sig").splitlines():
                if line.startswith("P026,"):
                    out.append(line.replace("0.025", "0.99"))
                else:
                    out.append(line)
            drift.write_text("\n".join(out), encoding="utf-8")
            report = qo.check_quality_oracle(
                res.event_log, cfg.to_dict(),
                parameters_csv=str(drift), metrics=res.metrics,
            )
        self.assertEqual(report.verdict, "FAIL")

    def test_invalid_parameters_rows_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g3_oracle_params_") as tmp:
            tmp_path = Path(tmp)
            # non-parseable value
            bad = tmp_path / "bad_value.csv"
            bad.write_text(
                "parameter_id,symbol,value\n"
                "P026,q_A,not_a_number\n"
                "P027,q_B,0.03\n"
                "P028,q_C,0.02\n"
                "P029,q_D,0.001\n"
                "P061,key_schema,key_schema_v1\n",
                encoding="utf-8",
            )
            with self.assertRaises(qo.QualityOracleInputError):
                qo.load_parameters(bad)
            # out-of-range probability
            bad2 = tmp_path / "bad_range.csv"
            bad2.write_text(
                "parameter_id,symbol,value\n"
                "P026,q_A,1\n"
                "P027,q_B,0.03\n"
                "P028,q_C,0.02\n"
                "P029,q_D,0.001\n"
                "P061,key_schema,key_schema_v1\n",
                encoding="utf-8",
            )
            with self.assertRaises(qo.QualityOracleInputError):
                qo.load_parameters(bad2)
            # wrong key schema
            bad3 = tmp_path / "bad_schema.csv"
            bad3.write_text(
                "parameter_id,symbol,value\n"
                "P026,q_A,0.025\n"
                "P027,q_B,0.03\n"
                "P028,q_C,0.02\n"
                "P029,q_D,0.001\n"
                "P061,key_schema,other_schema\n",
                encoding="utf-8",
            )
            with self.assertRaises(qo.QualityOracleInputError):
                qo.load_parameters(bad3)
            # missing row
            bad4 = tmp_path / "missing_row.csv"
            bad4.write_text(
                "parameter_id,symbol,value\n"
                "P026,q_A,0.025\n"
                "P027,q_B,0.03\n"
                "P028,q_C,0.02\n"
                "P061,key_schema,key_schema_v1\n",
                encoding="utf-8",
            )
            with self.assertRaises(qo.QualityOracleInputError):
                qo.load_parameters(bad4)


# ---------------------------------------------------------------------------
# Output-field contract of the per-device report (G3-SPEC-V1.0 section 9)
# ---------------------------------------------------------------------------


class TestOutputContract(_Base):
    def test_per_device_fields(self) -> None:
        cfg = make_config(batch_size=4, master_seed=7)
        res = run(cfg)
        report = self.oracle_check(cfg, event_log=res.event_log, metrics=res.metrics)
        self.assertEqual(report.verdict, "PASS", report.issues)
        for dev_id in range(1, 5):
            entry = report.to_dict()["devices"][str(dev_id)]
            self.assertEqual(entry["device_id"], dev_id)
            oracle_fields = entry["oracle"]
            for key in (
                "true_terminal_state",
                "d_generated",
                "d_value",
                "final_pass_exit",
                "category",
                "pl_contribution",
                "pw_contribution",
            ):
                self.assertIn(key, oracle_fields)
            self.assertIn(oracle_fields["category"], qo.CATEGORIES)
            self.assertIn(oracle_fields["true_terminal_state"],
                          (qo.TERMINAL_PASSED, qo.TERMINAL_EXITED))
            self.assertIn(oracle_fields["final_pass_exit"], (qo.FINAL_PASS, qo.FINAL_EXIT))
            self.assertIn(oracle_fields["d_value"],
                          (qo.D_NORMAL, qo.D_PROBLEM, qo.D_NOT_CREATED))
            self.assertEqual(oracle_fields["d_generated"],
                             oracle_fields["d_value"] != qo.D_NOT_CREATED)
            self.assertIn(oracle_fields["pl_contribution"], (0, 1))
            self.assertIn(oracle_fields["pw_contribution"], (0, 1))
        # batch aggregates
        agg = report.oracle_aggregate
        self.assertEqual(
            agg["S"] + agg["exited"], 4,
            "every device reaches a terminal state",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
