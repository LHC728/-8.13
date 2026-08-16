#!/usr/bin/env python3
"""Q3-H2-P3-B-E1 evidence runner: current-generation residual lifetime
coordinate repair + cost requalification (Human Gate narrow repair).

Runs:
  * independent P3-B-E1 mechanics checker (h2_p3b_checker_v1, 16 checks):
    the 11 P3-B checks plus CURRENT_GENERATION_LIFETIME (CURR-LIFE-01..05),
    CURRENT_GENERATION_FAILURE_TIMING (INDEPENDENT_FROZEN_ORACLE,
    nonzero-age mid-fragment natural failure), RIGHT_CENSOR_240,
    NO_PM_STRING_SEMANTICS, NONZERO_AGE_RUNTIME_SANITY (age>=120);
  * P3-B-E1 unit tests (test_h2_p3b_v1.py);
  * deterministic regressions (P1 firewall / Density E2 / key_schema /
    Q3 H1 / G3 random DES);
  * cost REQUALIFICATION (h2_tuning selection domain rep 0..4 K=10.5;
    base_r runtime via development_unit PERFORMANCE_ONLY_BASE_SURROGATE;
    single-rollout c_r via the h2 continuation engine) and the frozen
    three-point (M*, C_eval*) selection (w_p<=90s, max M, then larger
    C_eval);
then writes a NEW immutable evidence root with the acyclic hash DAG,
semantic evidence mapping and fail-closed verification.

The prior P3-B evidence roots are immutable:
  * run_20260816T072245476180Z_45e12558 (final P3-B) is marked
    HISTORICAL_P3_B_EXECUTION_WITH_CURRENT_GENERATION_RESIDUAL_LIFETIME_COORDINATE_BUG;
  * run_...12160c66 / ...2bede6c9 / ...36291377 (dev iterations) are
    immutable historical roots.  Their quota / CRN / D / U_Y / Q-estimator
    results may serve as auxiliary historical evidence; the rollout-kernel
    final qualification and the cost freeze are covered by THIS E1
    requalification.

P3-B-E1 scope (Human Gate at 841bafc): F1 current-generation residual
lifetime coordinate (absolute failure age = current_age + tau; right-
censored -> 240); G1 RESULT numbers mechanically generated from the final
evidence (RESULT_SOURCE_RUN_ID assertion); G2 base_runtime_role =
PERFORMANCE_ONLY_BASE_SURROGATE disclosure.  NOT authorized: action
stability §4(b)(c), cross-K transfer, h2_tuning policy experiments beyond
this cost requalification, h2_holdout, C25, final H2 numbers, Q3 K
recommendation.  No new formal / holdout worlds.

Evidence root: 05_结果/H2/tuning/cost_calibration/requalification/
run_<UTC>_<8hex>/

Python 3.12, standard library only.
"""
from __future__ import annotations

import io
import json
import secrets
import shutil
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from scripts import run_q3_h1_formal_v1 as frm  # noqa: E402
from scripts import run_h2_p3b_cost_v1 as cost  # noqa: E402
from checker import h2_p3b_checker_v1 as chk  # noqa: E402

PACKAGE_REF = "Q3-H2-P3-B-E1"
BOOTSTRAP_SPEC_FILE = frm.BOOTSTRAP_SPEC_FILE
FORMAL_TASK_PACKAGE_FILE = frm.TASK_PACKAGE_FILE
FORMAL_TASK_PACKAGE_SHA = frm.TASK_PACKAGE_SNAPSHOT_SHA
REGISTRY_VERSION = "CR-V3.1"

P3B_HISTORICAL_ROOTS = (
    "run_20260816T072245476180Z_45e12558",
    "run_20260816T072040837798Z_36291377",
    "run_20260816T071937230365Z_2bede6c9",
    "run_20260816T071906544944Z_12160c66",
)
HISTORICAL_MARKER = "HISTORICAL_P3_B_EXECUTION_WITH_CURRENT_GENERATION_RESIDUAL_LIFETIME_COORDINATE_BUG"

SCOPE_AUDIT = {
    "f1_current_generation_lifetime_coordinate": "YES (absolute failure "
        "age = current_age + residual_tau; right-censored -> 240; P2 "
        "conditional_residual_frozen API unchanged)",
    "new_generation_lifetime": "YES (age=0 unconditional sampler -> "
        "absolute failure age from generation birth; conversion never adds "
        "age to a new-generation draw)",
    "g1_result_sourced_from_final_evidence": "YES (base rows / c_r rows / "
        "median / worst / candidate w_p / selected config mechanically "
        "generated from cost_summary.json + mc_eval_selection.json; "
        "RESULT_SOURCE_RUN_ID asserted)",
    "g2_base_runtime_surrogate": f"YES (base_runtime_namespace="
        f"{cost.BASE_NS}, base_runtime_role={cost.BASE_RUNTIME_ROLE}; "
        f"Human Gate performance-only exception for the §1.2 cost runtime "
        f"only; never for stability/transfer/holdout/C25/benefit stats)",
    "calibration_selection_domain": "h2_tuning / seed 6 / rep 0..4 / K=10.5",
    "rollout_kernel": "YES (first-action-then-H1; absorption)",
    "action_stability": "NO", "cross_k_transfer": "NO",
    "h2_tuning_policy_experiment_beyond_cost": "NO",
    "h2_holdout": "NOT USED", "c25": "NO", "paper_h2_numbers": "NO",
    "q3_k_recommendation": "NO",
    "new_formal_worlds": "NO", "new_holdout_worlds": "NO",
    "random_streams": {
        "cost_selection_domain": "h2_tuning", "cost_master_seed": 6,
        "cost_replicate_ids": [0, 1, 2, 3, 4], "cost_K": "10.5",
        "base_runtime_namespace": "development_unit",
        "base_runtime_role": "PERFORMANCE_ONLY_BASE_SURROGATE",
        "rollout_namespace": "h2_rollout (post-key adapter formula)",
        "h2_holdout_used": False, "q3_formal_used": False,
    },
    "p1_p2_p3a_accepted_modified": "NO",
    "historical_p3b_roots": {
        root: HISTORICAL_MARKER for root in P3B_HISTORICAL_ROOTS
    },
}

REGRESSION_PATTERNS = (
    "test_h2_p1_firewall_v1.py",
    "test_h2_q3_density_v1.py",
    "test_g3_key_schema_v1.py",
    "test_q3_h1_formal_v1.py",
    "test_g3_random_des_v1.py",
)

REPORT_MAPPING: dict[str, str] = {
    "ROLLOUT_KERNEL": "rollout_kernel_report.json",
    "H1_FALLBACK_PARITY": "h1_fallback_parity_report.json",
    "FUTURE_D_MATERIALIZATION": "future_d_materialization_report.json",
    "U_Y_CONSUMPTION": "u_y_consumption_report.json",
    "LIFETIME_GENERATION": "lifetime_generation_report.json",
    "CRN_WORLD": "crn_world_report.json",
    "QUOTA_SELECTOR": "quota_selector_report.json",
    "QUOTA_CAUSALITY": "quota_causality_report.json",
    "ROLLOUT_COUNT": "rollout_count_report.json",
    "Q_ESTIMATOR": "q_estimator_report.json",
    "C23_ROLLOUT": "c23_rollout_report.json",
    "CURRENT_GENERATION_LIFETIME": "current_generation_lifetime_report.json",
    "CURRENT_GENERATION_FAILURE_TIMING":
        "current_generation_failure_timing_report.json",
    "RIGHT_CENSOR_240": "right_censor_240_report.json",
    "NO_PM_STRING_SEMANTICS": "no_pm_string_semantics_report.json",
    "NONZERO_AGE_RUNTIME_SANITY": "nonzero_age_runtime_sanity_report.json",
    "COST_CALIBRATION": "cost_summary.json",
    "COST_RAW": "cost_measurement_raw.json",
    "M_CEVAL_SELECTION": "mc_eval_selection.json",
    "EVIDENCE_SEMANTIC_MAPPING": "evidence_semantic_mapping_report.json",
}


def _run_suite(pattern: str) -> dict[str, Any]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(CODE_DIR / "tests"), pattern=pattern)
    buf = io.StringIO()
    runner = unittest.TextTestRunner(stream=buf, verbosity=1)
    result = runner.run(suite)
    return {
        "command": f"python -m unittest discover -s tests -p {pattern!r}",
        "exit_code": 0 if result.wasSuccessful() else 1,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "ok": result.wasSuccessful(),
        "log_tail": buf.getvalue()[-1500:],
    }


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_") + secrets.token_hex(4)


def result_summary_from_evidence(evidence_root: Path) -> dict[str, Any]:
    """G1: mechanically generate the RESULT numbers from the FINAL immutable
    evidence root (cost_summary.json + mc_eval_selection.json).  Never mixes
    old dev-iteration numbers; asserts RESULT_SOURCE_RUN_ID."""
    cost_summary = json.loads(
        (evidence_root / "cost_summary.json").read_text(encoding="utf-8"))
    selection = json.loads(
        (evidence_root / "mc_eval_selection.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (evidence_root / "run_manifest.json").read_text(encoding="utf-8"))
    run_id = manifest.get("run_id")
    base_rows = cost_summary.get("base_rows", [])
    c_r_rows = cost_summary.get("rollout_rows", cost_summary.get("c_r_rows", []))
    estimates = selection.get("estimates", {})
    sel = selection.get("selected")
    return {
        "RESULT_SOURCE_RUN_ID": run_id,
        "base_rows": base_rows,
        "c_r_rows": c_r_rows,
        "base_median_s": cost_summary.get("base_median_s"),
        "base_worst_s": cost_summary.get("base_worst_s"),
        "c_r_median_s": cost_summary.get("c_r_median_s"),
        "c_r_worst_s": cost_summary.get("c_r_worst_s"),
        "candidate_estimates": estimates,
        "selected": sel,
        "calibration_selection_domain": cost_summary.get(
            "calibration_selection_domain"),
        "base_runtime_namespace": cost_summary.get("base_runtime_namespace"),
        "base_runtime_role": cost_summary.get("base_runtime_role"),
        "wp_budget_s": cost_summary.get("wp_budget_s"),
    }


def _sha256_file(path: Path) -> str:
    return frm._sha256_file(path)


def _sha256_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dump_json(path: Path, value: Any) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n", encoding="utf-8", newline="\n")


def evidence_mapping_check(evidence_dir: Path) -> dict[str, Any]:
    results: dict[str, Any] = {}
    ok = True
    for check_id, fname in REPORT_MAPPING.items():
        p = evidence_dir / fname
        if not p.is_file():
            results[fname] = {"ok": False, "expected": check_id,
                              "got": None, "missing": True}
            ok = False
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            got = data.get("check") or data.get("id")
        except (json.JSONDecodeError, OSError) as exc:
            results[fname] = {"ok": False, "expected": check_id,
                              "got": None, "error": str(exc)}
            ok = False
            continue
        match = (got == check_id) or (
            check_id in ("COST_RAW", "M_CEVAL_SELECTION")
            and got in ("COST_RAW", "M_CEVAL_SELECTION"))
        ok = ok and match
        results[fname] = {"ok": match, "expected": check_id, "got": got}
    return {"check": "EVIDENCE_SEMANTIC_MAPPING",
            "status": "PASS" if ok else "FAIL", "files": results}


def _verify(out_dir: Path) -> dict[str, Any]:
    try:
        dag = frm.verify_hash_dag(out_dir)
        cons = frm.verify_manifest_inventory_consistency(out_dir)
        mapping = evidence_mapping_check(out_dir)
        ok = (dag["hash_graph_acyclic"] is True and dag["mismatches"] == 0
              and "PASS" in cons["manifest_output_hashes"]
              and "PASS" in cons["manifest_inventory_crosscheck"]
              and cons["c21_report_sha_consistency"] == "PASS"
              and mapping["status"] == "PASS")
        return {"ok": ok, "hash_graph_acyclic": dag["hash_graph_acyclic"],
                "inventory_n": dag["inventory_n"], "mismatches": dag["mismatches"],
                "manifest_output_hashes": cons["manifest_output_hashes"],
                "manifest_inventory_crosscheck": cons["manifest_inventory_crosscheck"],
                "c21_report_sha_consistency": cons["c21_report_sha_consistency"],
                "evidence_semantic_mapping": mapping["status"],
                "detail": {"dag": dag, "consistency": cons, "mapping": mapping}}
    except AssertionError as exc:
        return {"ok": False, "error": f"AssertionError: {exc}"}


def _build_evidence(out_dir: Path, run_id: str, checks: dict[str, Any],
                    cost_result: dict[str, Any],
                    test_report: dict[str, Any],
                    regressions: list[dict[str, Any]],
                    verification: Optional[dict[str, Any]],
                    wall_total: float) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_bytes = Path(BOOTSTRAP_SPEC_FILE).read_bytes()
    spec_sha = _sha256_bytes(spec_bytes)
    (out_dir / "bootstrap_spec_snapshot.md").write_bytes(spec_bytes)
    (out_dir / "task_package_snapshot.yaml").write_text(
        "# Q3-H2-P3-B-E1 task-package snapshot\n"
        f"package_ref: {PACKAGE_REF}\n"
        "authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED "
        "sections 1/1.2/3/6/7/9/13 + Q3-H2-P3-B-E1 Human Gate narrow "
        "repair authorization (F1 current-generation residual lifetime "
        "coordinate; G1 RESULT-from-evidence; G2 base-runtime surrogate; "
        "starting HEAD 841bafc)\n"
        f"bootstrap_spec_snapshot: bootstrap_spec_snapshot.md\n"
        f"bootstrap_spec_sha256: {spec_sha}\n"
        f"formal_task_package_sha256: {FORMAL_TASK_PACKAGE_SHA}\n"
        "p1: FINAL PASS / ACCEPTED (08488e4)\n"
        "p2: FINAL PASS / ACCEPTED (a5d2faf; conditional_residual_frozen "
        "API unchanged)\n"
        "p3a: FINAL PASS / ACCEPTED (b285131 + fcf07f6)\n"
        "p3b: HISTORICAL_P3_B_EXECUTION_WITH_CURRENT_GENERATION_RESIDUAL_"
        "LIFETIME_COORDINATE_BUG (immutable roots listed in scope_audit)\n"
        "p3b_e1: current-generation residual lifetime coordinate repair + "
        "cost requalification\n"
        "action stability / cross-K transfer / holdout / C25: NOT "
        "AUTHORIZED\n"
        "evidence_rule: ACYCLIC hash DAG (RULE A)\n",
        encoding="utf-8", newline="\n")
    _dump_json(out_dir / "commands.json", {
        "run_id": run_id,
        "command": "python 04_代码/scripts/run_h2_p3b_e1_v1.py",
        "wall_clock_s": round(wall_total, 2)})
    _dump_json(out_dir / "environment.json", frm._env_summary())
    _dump_json(out_dir / "scope_audit.json", SCOPE_AUDIT)
    _dump_json(out_dir / "test_report.json", test_report)
    _dump_json(out_dir / "regression_report.json", {
        "regressions": regressions,
        "note": "deterministic suites; commands/exit codes/test counts "
                "truthfully recorded"})
    for check in checks["checks"]:
        fname = REPORT_MAPPING.get(check["check"])
        if fname is not None:
            _dump_json(out_dir / fname, check)
    cost_summary = dict(cost_result)
    cost_summary.pop("base_rows", None)
    cost_summary.pop("rollout_rows", None)
    _dump_json(out_dir / "cost_summary.json", cost_summary)
    raw = dict(cost_result)
    raw["check"] = "COST_RAW"
    raw["id"] = "COST_RAW"
    _dump_json(out_dir / "cost_measurement_raw.json", raw)
    sel = {
        "id": "M_CEVAL_SELECTION",
        "check": "M_CEVAL_SELECTION",
        "selected": cost_result.get("selected"),
        "estimates": cost_result.get("estimates"),
        "selection_rule": cost_result.get("selection_rule"),
        "wp_budget_s": cost_result.get("wp_budget_s"),
        "budget_infeasible": cost_result.get("budget_infeasible"),
        "pre_registered_delete_trigger": cost_result.get(
            "pre_registered_delete_trigger"),
        "calibration_selection_domain": cost_result.get(
            "calibration_selection_domain"),
        "base_runtime_namespace": cost_result.get("base_runtime_namespace"),
        "base_runtime_role": cost_result.get("base_runtime_role"),
        "cost_summary": {k: v for k, v in cost_result.items()
                         if k in ("base_median_s", "base_worst_s",
                                  "c_r_median_s", "c_r_worst_s")},
    }
    _dump_json(out_dir / "mc_eval_selection.json", sel)
    mapping_result = evidence_mapping_check(out_dir)
    _dump_json(out_dir / "evidence_semantic_mapping_report.json", mapping_result)
    ledger_path = BASE_DIR / "05_结果" / "H2" / "dev_budget_ledger.json"
    if ledger_path.is_file():
        _dump_json(out_dir / "dev_budget_ledger_snapshot.json",
                   json.loads(ledger_path.read_text(encoding="utf-8")))

    hashes = {
        "task_package_snapshot": _sha256_file(out_dir / "task_package_snapshot.yaml"),
        "bootstrap_spec": spec_sha,
        "formal_task_package": _sha256_file(FORMAL_TASK_PACKAGE_FILE),
        "frozen_params": _sha256_file(MAIN_MODEL / "h2" / "frozen_params_v1.py"),
        "observable_state": _sha256_file(MAIN_MODEL / "h2" / "observable_state_v1.py"),
        "posterior_state": _sha256_file(MAIN_MODEL / "h2" / "posterior_state_v1.py"),
        "lifetime_generator": _sha256_file(
            MAIN_MODEL / "h2" / "lifetime_generator_v1.py"),
        "decision_point": _sha256_file(MAIN_MODEL / "h2" / "decision_point_v1.py"),
        "action_semantics": _sha256_file(MAIN_MODEL / "h2" / "action_semantics_v1.py"),
        "rollout_seed": _sha256_file(MAIN_MODEL / "h2" / "rollout_seed_v1.py"),
        "continuation": _sha256_file(MAIN_MODEL / "h2" / "continuation_v1.py"),
        "rollout_engine": _sha256_file(
            MAIN_MODEL / "h2_rollout" / "rollout_engine_v1.py"),
        "quota_selector": _sha256_file(MAIN_MODEL / "h2" / "quota_selector_v1.py"),
        "q_estimator": _sha256_file(MAIN_MODEL / "h2" / "q_estimator_v1.py"),
        "rollout_post_keys_adapter": _sha256_file(
            MAIN_MODEL / "h2_rollout" / "post_keys_v1.py"),
        "p3b_checker": _sha256_file(CODE_DIR / "checker" / "h2_p3b_checker_v1.py"),
        "tests": _sha256_file(CODE_DIR / "tests" / "test_h2_p3b_v1.py"),
        "cost_script": _sha256_file(CODE_DIR / "scripts" / "run_h2_p3b_cost_v1.py"),
        "runner": _sha256_file(Path(__file__).resolve()),
        "key_schema": _sha256_file(MAIN_MODEL / "g3" / "key_schema_v1.py"),
        "engine": _sha256_file(MAIN_MODEL / "g3" / "random_des_v1.py"),
        "problem_contract": _sha256_file(frm.PROBLEM_CONTRACT_FILE),
        "parameters_csv": _sha256_file(frm.PARAMETERS_CSV),
        "registry": _sha256_file(BASE_DIR / "01_审计" / "检查注册表_V3.1.md"),
    }
    _dump_json(out_dir / "input_hashes.json", hashes)

    verify_ok = verification is not None and verification.get("ok") is True
    c21a = ("PASS" if verify_ok else
            ("PENDING_PROBE" if verification is None else "FAIL"))
    cost_ok = cost_result.get("status") == "PASS"
    overall_ok = (checks["overall"] == "PASS"
                  and test_report["ok"]
                  and all(r["ok"] for r in regressions)
                  and cost_ok
                  and verify_ok)
    _dump_json(out_dir / "C21_REQUALIFICATION_REPORT.json", {
        "run_id": run_id, "check_id": "CR-V3.1/C21",
        "scope": "Q3-H2-P3-B-E1 current-generation lifetime repair + cost "
                 "requalification evidence root",
        "status": "PASS" if overall_ok else "FAIL",
        "verification": verification,
        "items": [
            {"id": "C21a", "status": c21a,
             "note": "acyclic hash inventory (RULE A); status from actual "
                     "verifier"},
            {"id": "C21b", "status": c21a,
             "note": "manifest/inventory/actual SHA consistency; status "
                     "from actual verifier"},
            {"id": "C21c", "status": "PASS" if overall_ok else "FAIL",
             "note": "P3-B-E1 lifetime/parity/quota/CRN + tests + "
                     "regressions + cost requalification"}]})
    _dump_json(out_dir / "checks.json", {
        "run_id": run_id, "registry_version": REGISTRY_VERSION,
        "overall_status": "PASS" if overall_ok else "FAIL",
        "verification_fail_closed": {
            "hash_graph_acyclic": verification.get("hash_graph_acyclic")
            if verification else None,
            "inventory_mismatches": verification.get("mismatches")
            if verification else None,
            "manifest_inventory_consistency": verification.get(
                "manifest_inventory_crosscheck") if verification else None,
            "c21_report_sha_consistency": verification.get(
                "c21_report_sha_consistency") if verification else None,
            "evidence_semantic_mapping": verification.get(
                "evidence_semantic_mapping") if verification else None},
        "items": [
            {"check_id": c["check"], "status": c["status"]}
            for c in checks["checks"]] +
            [{"check_id": "COST_CALIBRATION",
              "status": cost_result.get("status"),
              "selected": cost_result.get("selected")},
             {"check_id": "TESTS", "status": "PASS" if test_report["ok"]
              else "FAIL",
              "count": f"{test_report['tests_run'] - test_report['failures'] - test_report['errors']}"
                       f"/{test_report['tests_run']}"},
             {"check_id": "REGRESSIONS", "status": "PASS" if all(
                 r["ok"] for r in regressions) else "FAIL",
              "detail": [{"pattern": r["command"].split("'")[1],
                          "exit_code": r["exit_code"],
                          "tests_run": r["tests_run"]} for r in regressions]},
             {"check_id": "CR-V3.1/C21", "status": "PASS" if overall_ok
              else "FAIL",
              "note": "acyclic hash inventory + manifest/inventory "
                      "consistency (fail-closed)"}]})

    artifacts = [
        {"path": p.relative_to(out_dir).as_posix(),
         "bytes": p.stat().st_size, "sha256": _sha256_file(p)}
        for p in sorted(out_dir.rglob("*"))
        if p.is_file() and p.name != "file_hashes.sha256"]
    sel_status = ("COMPLETED / AWAITING HUMAN GATE FINAL P3-B REVIEW"
                  if cost_result.get("selected") is not None
                  else "H2_BUDGET_INFEASIBLE")
    _dump_json(out_dir / "run_manifest.json", {
        "run_id": run_id, "created_at": _utc_now(), "gate": "Q3",
        "purpose": "h2_p3b_e1_lifetime_repair_cost_requalification",
        "formal": True,
        "label": "Q3-H2-P3-B-E1 current-generation residual lifetime "
                 "coordinate repair + cost requalification",
        "paper_authoritative": False,
        "task_package_ref": PACKAGE_REF,
        "task_package_snapshot_path": "task_package_snapshot.yaml",
        "bootstrap_spec_sha256": spec_sha,
        "formal_task_package_sha256": FORMAL_TASK_PACKAGE_SHA,
        "registry_version": REGISTRY_VERSION,
        "hash_inventory_path": "file_hashes.sha256",
        "hash_inventory_rule": (
            "ACYCLIC DAG (RULE A): run_manifest does not hash "
            "file_hashes.sha256; file_hashes covers all artifacts incl. "
            "run_manifest and task_package_snapshot, never itself."),
        "historical_p3b_roots": {
            root: HISTORICAL_MARKER for root in P3B_HISTORICAL_ROOTS
        },
        "random_domain": {
            "calibration_selection_domain": {
                "namespace": "h2_tuning", "master_seed": 6,
                "replicate_ids": [0, 1, 2, 3, 4], "K": "10.5",
                "purpose": "M/C_eval cost calibration only"},
            "base_runtime_namespace": "development_unit",
            "base_runtime_role": "PERFORMANCE_ONLY_BASE_SURROGATE",
            "rollout_namespace": "h2_rollout (post-key adapter formula)",
            "h2_holdout_used": False, "q3_formal_used": False,
            "new_formal_worlds": False, "new_holdout_worlds": False,
        },
        "p1": "FINAL PASS / ACCEPTED (08488e4)",
        "p2": "FINAL PASS / ACCEPTED (a5d2faf; lifetime API unchanged)",
        "p3a": "FINAL PASS / ACCEPTED (b285131 + fcf07f6)",
        "p3b": HISTORICAL_MARKER,
        "p3b_e1": {
            "f1_current_generation_lifetime_coordinate": "repaired",
            "g1_result_sourced_from_final_evidence": True,
            "g2_base_runtime_surrogate": cost.BASE_RUNTIME_ROLE,
            "cost_calibration": sel_status,
            "selected": cost_result.get("selected"),
            "action_stability": "NOT AUTHORIZED",
            "cross_k_transfer": "NOT AUTHORIZED",
            "h2_holdout": "NOT AUTHORIZED",
            "c25": "NOT AUTHORIZED",
            "c23_rollout_path": "PASS; full final policy C23 PENDING"},
        "verification_fail_closed": (
            verification if verification is not None else "PROBE_PHASE"),
        "overall_status": "PASS" if overall_ok else "FAIL",
        "environment": frm._env_summary(), "outputs": artifacts,
        "check_report_paths": [
            "checks.json", "rollout_kernel_report.json",
            "h1_fallback_parity_report.json",
            "future_d_materialization_report.json",
            "u_y_consumption_report.json", "lifetime_generation_report.json",
            "crn_world_report.json", "quota_selector_report.json",
            "quota_causality_report.json", "rollout_count_report.json",
            "q_estimator_report.json", "c23_rollout_report.json",
            "current_generation_lifetime_report.json",
            "current_generation_failure_timing_report.json",
            "right_censor_240_report.json",
            "no_pm_string_semantics_report.json",
            "nonzero_age_runtime_sanity_report.json",
            "cost_measurement_raw.json", "cost_summary.json",
            "mc_eval_selection.json", "regression_report.json",
            "test_report.json", "scope_audit.json",
            "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "Q3-H2-P3-B-E1：current-generation residual lifetime 坐标修复 "
            "（absolute failure age = current_age + tau；right-censored -> "
            "240；P2 API 不变）+ 独立 frozen oracle 非零 age 故障时序 + "
            "NO_PM 字符串语义 + 成本 requalification。",
            "base_runtime_role = PERFORMANCE_ONLY_BASE_SURROGATE "
            "（development_unit；Human Gate 限 §1.2 成本 runtime 的例外；"
            "非 h2_tuning physical-world evidence）。",
            "P3-B 旧 evidence roots immutable 标记 HISTORICAL_...（quota/"
            "CRN/D/U_Y/Q-estimator 可作历史辅助；rollout kernel 终审与 "
            "cost freeze 由本 E1 覆盖）。",
            "action stability / cross-K transfer / h2_holdout / C25 / 论文"
            " H2 数字 NOT AUTHORIZED。",
            "C21 fail-closed + semantic evidence mapping。"],
    })

    lines = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "file_hashes.sha256":
            rel = path.relative_to(out_dir).as_posix()
            lines.append(f"{_sha256_file(path)}  {rel}")
    (out_dir / "file_hashes.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _promote(staging: Path, final: Path) -> dict[str, Any]:
    if final.exists():
        shutil.rmtree(final)
    shutil.copytree(staging, final)
    mismatches = []
    for p in sorted(staging.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(staging)
        q = final / rel
        if not q.is_file() or _sha256_file(p) != _sha256_file(q):
            mismatches.append(rel.as_posix())
    return {"ok": len(mismatches) == 0,
            "files_copied": sum(1 for p in staging.rglob("*") if p.is_file()),
            "sha_mismatches": mismatches}


def main(argv: Optional[list[str]] = None) -> int:
    output_root = (BASE_DIR / "05_结果" / "H2" / "tuning" / "cost_calibration"
                   / "requalification")
    run_id = _new_run_id()
    final_dir = output_root / f"run_{run_id}"
    staging_dir = BASE_DIR / ".." / "tmp" / f"p3be1_staging_{run_id}"
    print(f"[p3b-e1] run_id={run_id}")
    t0 = time.perf_counter()
    checks = {
        "overall": "PASS",
        "checks": [
            chk.check_rollout_kernel(),
            chk.check_h1_fallback_parity(),
            chk.check_future_d_materialization(),
            chk.check_u_y_consumption(),
            chk.check_lifetime_generation(),
            chk.check_crn_world(),
            chk.check_quota_selector(),
            chk.check_quota_causality(),
            chk.check_rollout_count(),
            chk.check_q_estimator(),
            chk.check_c23_rollout(),
            chk.check_current_generation_lifetime(),
            chk.check_current_generation_failure_timing(),
            chk.check_right_censor_240(),
            chk.check_no_pm_string_semantics(),
            chk.check_nonzero_age_runtime_sanity(),
        ]}
    checks["overall"] = ("PASS" if all(c["status"] == "PASS"
                                       for c in checks["checks"]) else "FAIL")
    test_report = _run_suite("test_h2_p3b_v1.py")
    regressions = [_run_suite(p) for p in REGRESSION_PATTERNS]
    cost_result = cost.run_cost_measurement(base_samples=1,
                                            rollout_samples=3)
    wall_total = time.perf_counter() - t0
    # ---- dev budget ledger: append this run's entry ----
    ledger_path = BASE_DIR / "05_结果" / "H2" / "dev_budget_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry_ids = {e.get("entry_id") for e in ledger["entries"]}
    p3be1_entry_id = f"P3-B-E1-{run_id}"
    if p3be1_entry_id not in entry_ids:
        ledger["entries"].append({
            "entry_id": p3be1_entry_id,
            "task": "Q3-H2-P3-B-E1 current-generation residual lifetime "
                    "coordinate repair + cost requalification",
            "run_id": run_id,
            "wall_clock_s": round(wall_total, 4),
            "status": ("COMPLETED / AWAITING HUMAN GATE FINAL P3-B REVIEW"
                       if cost_result.get("selected") is not None
                       else "H2_BUDGET_INFEASIBLE"),
            "category": "P3-B-E1 lifetime repair diagnostics + §1.2 cost "
                        "requalification",
            "namespace": "h2_tuning (selection domain) / development_unit "
                         "(base-runtime surrogate) / h2_rollout (formula)",
            "note": "F1 current-generation residual lifetime coordinate; "
                    "cost freeze requalified",
            "date": "2026-08-16"})
    ledger["cumulative_wall_clock_s"] = round(
        sum(e["wall_clock_s"] for e in ledger["entries"]), 4)
    ledger["cumulative_wall_clock_h"] = round(
        ledger["cumulative_wall_clock_s"] / 3600.0, 6)
    ledger["soft_budget_reached"] = (
        ledger["cumulative_wall_clock_h"] >= ledger["soft_budget_h"])
    ledger["hard_budget_reached"] = (
        ledger["cumulative_wall_clock_h"] >= ledger["hard_budget_h"])
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False,
                                      sort_keys=True, indent=1) + "\n",
                           encoding="utf-8", newline="\n")
    print(f"[p3b-e1] checker overall={checks['overall']} "
          f"tests={test_report['tests_run']} "
          f"regressions={[r['tests_run'] for r in regressions]}")
    print(f"[p3b-e1] cost status={cost_result['status']} "
          f"selected={cost_result.get('selected')}")
    for c in checks["checks"]:
        print(f"  {c['check']}: {c['status']}")
    _build_evidence(staging_dir, run_id, checks, cost_result, test_report,
                    regressions, verification=None, wall_total=wall_total)
    probe = _verify(staging_dir)
    print(f"[p3b-e1] probe verification ok={probe.get('ok')} {probe.get('error', '')}")
    if not probe.get("ok"):
        return 1
    _build_evidence(staging_dir, run_id, checks, cost_result, test_report,
                    regressions, verification=probe, wall_total=wall_total)
    confirm = _verify(staging_dir)
    if not confirm.get("ok"):
        print(f"[p3b-e1] FAIL final-content verification {confirm.get('error', '')}")
        return 1
    promo = _promote(staging_dir, final_dir)
    if not promo["ok"]:
        print(f"[p3b-e1] FAIL promote {promo['sha_mismatches']}")
        return 1
    final_verify = _verify(final_dir)
    # G1: mechanically generate the RESULT numbers from the final evidence;
    # assert the source run_id is THIS run (never old dev-iteration numbers)
    result_src = result_summary_from_evidence(final_dir)
    src_ok = result_src["RESULT_SOURCE_RUN_ID"] == run_id
    if not src_ok:
        print(f"[p3b-e1] FAIL RESULT_SOURCE_RUN_ID: {result_src.get('RESULT_SOURCE_RUN_ID')} != {run_id}")
        return 1
    sel = result_src.get("selected") or {}
    print(f"[p3b-e1] RESULT_SOURCE_RUN_ID={run_id}")
    print(f"[p3b-e1] base_median={result_src.get('base_median_s')} "
          f"c_r_median={result_src.get('c_r_median_s')}")
    print(f"[p3b-e1] selected={sel}")
    ok = (probe.get("ok") and confirm.get("ok") and promo["ok"]
          and final_verify.get("ok") and src_ok
          and checks["overall"] == "PASS"
          and test_report["ok"] and all(r["ok"] for r in regressions)
          and cost_result.get("status") == "PASS")
    print(f"[p3b-e1] evidence written: {final_dir}")
    print(f"[p3b-e1] DONE overall={'PASS' if ok else 'FAIL'} wall={wall_total:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
