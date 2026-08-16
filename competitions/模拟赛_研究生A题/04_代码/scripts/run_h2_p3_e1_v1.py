#!/usr/bin/env python3
"""Q3-H2-P3-A-E1 evidence runner: WAIT fragment identity + continuation
posterior world requalification (Human Gate narrow repair).

Runs:
  * independent P3-A-E1 mechanics checker (h2_p3_mechanics_checker_v1, 15
    checks): decision-point classification (with WAIT anchor identity
    agreement), canonical ordering, rollout_seed, CRN, C23 mechanics,
    H1 parity, WAIT_FRAGMENT_IDENTITY (WAIT-R1..R4), WAIT_INVALIDATION
    (WAIT-R5), CONTINUATION_POSTERIOR (F3 reached-E D posterior +
    counterexample + fail-close), PER_DEVICE_POST_DRAW (section 11),
    ROLLOUT_POST_KEYS (section 12 adapter CRN), PM_AGE_SEMANTICS (F4/PM-R1),
    MANDATORY_OPTIONAL_PM (PM-R2/R3/R4 + PM_WITH_HEAD positive),
    H1_REAL_PARITY (accepted H1 engine parity target), C23_CONTINUATION;
  * P3-A-E1 unit tests (test_h2_p3_mechanics_v1.py);
  * deterministic regressions (P1 firewall / Density E2 / key_schema /
    Q3 H1 / G3 random DES);
then writes a NEW immutable evidence root with the acyclic hash DAG,
semantic evidence mapping and fail-closed verification (verified staging
promoted byte-identical to the final root; post-promotion read-only
re-verify).

The prior P3-A roots are immutable:
  * run_20260816T060111865845Z_d5eafe0e (final P3-A) and
  * run_20260816T055931412559Z_a5f9bd4e (superseded) are marked
  HISTORICAL_P3_A_EXECUTION_WITH_WAIT_AND_CONTINUATION_REVIEW_FINDINGS
  (marker recorded here / CURRENT_STATE / ledger; the roots themselves are
  never rewritten).

P3-A-E1 scope (Human Gate repair at b285131): F1 active-fragment WAIT
anchors; F2 WaitAnchor true event identity; F3 per-device continuation
draws + reached-E D posterior; F4 PM age_before.  NOT AUTHORIZED in
P3-A-E1: M*/C_eval* selection, deviation threshold tuning, action
stability, cross-K transfer, h2_tuning policy experiments, h2_holdout,
C25, final H2 numbers, Q3 K recommendation.  No stochastic rollout is
executed; no new formal / holdout worlds.

Evidence root: 05_结果/H2/p3/mechanics/requalification/run_<UTC>_<8hex>/

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
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from scripts import run_q3_h1_formal_v1 as frm  # noqa: E402
from main_model.h2 import frozen_params_v1 as fp  # noqa: E402
from main_model.h2 import decision_point_v1 as dp  # noqa: E402
from main_model.h2 import action_semantics_v1 as asem  # noqa: E402
from main_model.h2 import rollout_seed_v1 as rs  # noqa: E402
from main_model.h2 import continuation_v1 as cont  # noqa: E402
from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from main_model.h2_rollout import post_keys_v1 as pk  # noqa: E402
from checker import h2_p3_mechanics_checker_v1 as chk  # noqa: E402

PACKAGE_REF = "Q3-H2-P3-A-E1"
BOOTSTRAP_SPEC_FILE = frm.BOOTSTRAP_SPEC_FILE
FORMAL_TASK_PACKAGE_FILE = frm.TASK_PACKAGE_FILE
FORMAL_TASK_PACKAGE_SHA = frm.TASK_PACKAGE_SNAPSHOT_SHA
REGISTRY_VERSION = "CR-V3.1"

P3A_HISTORICAL_ROOTS = (
    "run_20260816T060111865845Z_d5eafe0e",
    "run_20260816T055931412559Z_a5f9bd4e",
)
HISTORICAL_MARKER = "HISTORICAL_P3_A_EXECUTION_WITH_WAIT_AND_CONTINUATION_REVIEW_FINDINGS"

SCOPE_AUDIT = {
    "decision_point_reconstruction": "YES (SPEC sections 2/5/10/11/12)",
    "canonical_ordering": "YES (A/B/C/E, at most one point per "
                          "(resource, closure), dp 0-based pure function)",
    "legal_action_set": "YES (START_HEAD / H1_NOOP / WAIT_EVENT / "
                        "PM_WITH_HEAD / PM_IDLE)",
    "f1_active_fragment_wait_anchor": "YES (exact-fragment identity; "
                                      "COMPLETE/CANCEL settle matching; "
                                      "old CANCEL never settles a new "
                                      "fragment)",
    "f2_wait_anchor_true_identity": "YES (WaitAnchor stores the in-flight "
                                    "fragment process/attempt/"
                                    "attempt_start_time/resource, NOT the "
                                    "head's fields)",
    "f3_per_device_continuation_draws": "YES (per-device U_X_post / "
                                        "U_D_post; reached-E D posterior "
                                        "from PosteriorState."
                                        "d_posterior_given_abc; fail-close "
                                        "on missing draws)",
    "f4_pm_age_before": "YES (replacement age_before == equipment age_h, "
                        "never the wall-clock time)",
    "rollout_post_key_adapter": "YES (SPEC 6.2: rollout_seed(dp,m) -> "
                                "h2_rollout namespace post keys; CRN "
                                "across actions; no P2 synthetic mapping)",
    "continuation_world": "YES (rebuild from ObservableState + "
                          "PosteriorState + rollout post keys only)",
    "c23_end_to_end_mechanics": "YES (hidden-world variants -> identical "
                                "observable/posterior/decision points/dp/"
                                "rollout keys/ContinuationWorld); full "
                                "production C23 PENDING UNTIL FINAL POLICY "
                                "CONFIG",
    "m_star_selection": "NO", "c_eval_selection": "NO",
    "deviation_threshold_tuning": "NO", "action_stability": "NO",
    "cross_k_transfer": "NO", "h2_tuning_policy_experiment": "NO",
    "h2_holdout": "NOT USED", "c25": "NO", "paper_h2_numbers": "NO",
    "new_formal_worlds": "NO", "new_holdout_worlds": "NO",
    "stochastic_rollout_executed": "NO (P3-A-E1 smoke is deterministic only)",
    "p2_math_modified": "NO",
    "p1_p2_accepted_modified": "NO",
    "random_streams": {
        "namespace": "h2_rollout (post-key adapter formula only; no key "
                     "consumption in P3-A-E1)",
        "master_seed": 6, "replicate_ids": "validation toy (0..4)",
        "h2_holdout_used": False, "q3_formal_used": False,
        "u_y_post_used": False,
    },
    "historical_p3a_roots": {
        root: HISTORICAL_MARKER for root in P3A_HISTORICAL_ROOTS
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
    "DECISION_POINT_CLASSIFICATION": "decision_point_classification_report.json",
    "CANONICAL_ORDERING": "canonical_ordering_report.json",
    "ROLLOUT_SEED": "rollout_seed_report.json",
    "CRN_SAME_WORLD_ACROSS_ACTIONS": "crn_report.json",
    "C23_MECHANICS": "c23_mechanics_report.json",
    "H1_PARITY": "h1_parity_report.json",
    "WAIT_FRAGMENT_IDENTITY": "wait_fragment_identity_report.json",
    "WAIT_INVALIDATION": "wait_invalidation_report.json",
    "CONTINUATION_POSTERIOR": "continuation_posterior_report.json",
    "PER_DEVICE_POST_DRAW": "per_device_post_draw_report.json",
    "ROLLOUT_POST_KEYS": "rollout_post_key_report.json",
    "PM_AGE_SEMANTICS": "pm_age_semantics_report.json",
    "MANDATORY_OPTIONAL_PM": "mandatory_optional_pm_report.json",
    "H1_REAL_PARITY": "h1_real_parity_report.json",
    "C23_CONTINUATION": "c23_continuation_report.json",
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
            got = data.get("check")
        except (json.JSONDecodeError, OSError) as exc:
            results[fname] = {"ok": False, "expected": check_id,
                              "got": None, "error": str(exc)}
            ok = False
            continue
        match = got == check_id
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
        "# Q3-H2-P3-A-E1 task-package snapshot\n"
        f"package_ref: {PACKAGE_REF}\n"
        "authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED "
        "sections 2/5/6.2/7/8/9/10/11/12 + Q3-H2-P3-A-E1 Human Gate narrow "
        "repair authorization (F1..F4; starting HEAD b285131)\n"
        f"bootstrap_spec_snapshot: bootstrap_spec_snapshot.md\n"
        f"bootstrap_spec_sha256: {spec_sha}\n"
        f"formal_task_package_sha256: {FORMAL_TASK_PACKAGE_SHA}\n"
        "p1: FINAL PASS / ACCEPTED (08488e4)\n"
        "p2: FINAL PASS / ACCEPTED (a5d2faf)\n"
        "p3a: HISTORICAL_P3_A_EXECUTION_WITH_WAIT_AND_CONTINUATION_"
        "REVIEW_FINDINGS (immutable roots: run_...d5eafe0e / "
        "run_...a5f9bd4e)\n"
        "p3a_e1: WAIT fragment identity + continuation posterior world "
        "requalification\n"
        "p3 tuning / M* / C_eval* / holdout / C25: NOT AUTHORIZED\n"
        "evidence_rule: ACYCLIC hash DAG (RULE A)\n",
        encoding="utf-8", newline="\n")
    _dump_json(out_dir / "commands.json", {
        "run_id": run_id,
        "command": "python 04_代码/scripts/run_h2_p3_e1_v1.py",
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
        "decision_point": _sha256_file(MAIN_MODEL / "h2" / "decision_point_v1.py"),
        "action_semantics": _sha256_file(MAIN_MODEL / "h2" / "action_semantics_v1.py"),
        "rollout_seed": _sha256_file(MAIN_MODEL / "h2" / "rollout_seed_v1.py"),
        "continuation": _sha256_file(MAIN_MODEL / "h2" / "continuation_v1.py"),
        "rollout_post_keys_adapter": _sha256_file(
            MAIN_MODEL / "h2_rollout" / "post_keys_v1.py"),
        "p3_checker": _sha256_file(CODE_DIR / "checker" / "h2_p3_mechanics_checker_v1.py"),
        "tests": _sha256_file(CODE_DIR / "tests" / "test_h2_p3_mechanics_v1.py"),
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
    overall_ok = (checks["overall"] == "PASS"
                  and test_report["ok"]
                  and all(r["ok"] for r in regressions)
                  and verify_ok)
    _dump_json(out_dir / "C21_REQUALIFICATION_REPORT.json", {
        "run_id": run_id, "check_id": "CR-V3.1/C21",
        "scope": "Q3-H2-P3-A-E1 mechanics requalification evidence root",
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
             "note": "P3-A-E1 mechanics checker + tests + regressions"}]})
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
            [{"check_id": "TESTS", "status": "PASS" if test_report["ok"]
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
    _dump_json(out_dir / "run_manifest.json", {
        "run_id": run_id, "created_at": _utc_now(), "gate": "Q3",
        "purpose": "h2_p3_e1_mechanics_requalification", "formal": True,
        "label": "Q3-H2-P3-A-E1 WAIT fragment identity + continuation "
                 "posterior world requalification",
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
        "historical_p3a_roots": {
            root: HISTORICAL_MARKER for root in P3A_HISTORICAL_ROOTS
        },
        "random_domain": {
            "namespace": "h2_rollout (post-key adapter formula only; "
                         "P3-A-E1 executes no stochastic rollout / no key "
                         "consumption)",
            "master_seed": 6,
            "replicate_ids": [0, 1, 2, 3, 4],
            "h2_holdout_used": False,
            "q3_formal_used": False,
            "U_Y_post_used": False,
            "new_random_keys_outside_frozen_domains": "NO",
        },
        "p1": "FINAL PASS / ACCEPTED (08488e4)",
        "p2": "FINAL PASS / ACCEPTED (a5d2faf)",
        "p3a": HISTORICAL_MARKER,
        "p3a_e1": {"f1_active_fragment_wait": "implemented",
                   "f2_wait_anchor_true_identity": "implemented",
                   "f3_per_device_posterior_world": "implemented",
                   "f4_pm_age_before": "implemented",
                   "rollout_post_key_adapter": "implemented",
                   "c23_full_end_to_end": "PENDING UNTIL FINAL POLICY "
                                          "CONFIG"},
        "p3_tuning": "NOT AUTHORIZED", "h2_holdout": "NOT AUTHORIZED",
        "c25": "NOT AUTHORIZED",
        "verification_fail_closed": (
            verification if verification is not None else "PROBE_PHASE"),
        "overall_status": "PASS" if overall_ok else "FAIL",
        "environment": frm._env_summary(), "outputs": artifacts,
        "check_report_paths": [
            "checks.json", "decision_point_classification_report.json",
            "canonical_ordering_report.json", "rollout_seed_report.json",
            "crn_report.json", "c23_mechanics_report.json",
            "h1_parity_report.json", "wait_fragment_identity_report.json",
            "wait_invalidation_report.json",
            "continuation_posterior_report.json",
            "per_device_post_draw_report.json",
            "rollout_post_key_report.json", "pm_age_semantics_report.json",
            "mandatory_optional_pm_report.json", "h1_real_parity_report.json",
            "c23_continuation_report.json", "regression_report.json",
            "test_report.json", "scope_audit.json",
            "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "Q3-H2-P3-A-E1：Human Gate narrow repair（F1 活动 fragment WAIT "
            "锚；F2 WaitAnchor 真实事件身份；F3 per-device 后验续演世界 + "
            "reached-E D posterior；F4 PM age_before）+ WAIT-R1..R5 / "
            "PM-R1..R4 / real H1 parity / C23 continuation / rollout "
            "post-key adapter。",
            "P3-A-E1 为纯确定性机制包；不执行随机 rollout、不消费随机键、"
            "不产生新 formal/holdout worlds。",
            "C23 措辞：MECHANICS REQUALIFIED；full production C23 PENDING "
            "UNTIL FINAL POLICY CONFIG。",
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
    output_root = BASE_DIR / "05_结果" / "H2" / "p3" / "mechanics" / "requalification"
    run_id = _new_run_id()
    final_dir = output_root / f"run_{run_id}"
    staging_dir = BASE_DIR / ".." / "tmp" / f"p3e1_staging_{run_id}"
    print(f"[p3a-e1] run_id={run_id}")
    t0 = time.perf_counter()
    checks = {
        "overall": "PASS",
        "checks": [
            chk.check_decision_points(),
            chk.check_ordering(),
            chk.check_rollout_seed(),
            chk.check_crn(),
            chk.check_c23_mechanics(),
            chk.check_h1_parity(),
            chk.check_wait_fragment_identity(),
            chk.check_wait_invalidation(),
            chk.check_continuation_posterior(),
            chk.check_per_device_post_draw(),
            chk.check_rollout_post_keys(),
            chk.check_pm_age_semantics(),
            chk.check_mandatory_optional_pm(),
            chk.check_h1_real_parity(),
            chk.check_c23_continuation(),
        ]}
    checks["overall"] = ("PASS" if all(c["status"] == "PASS"
                                       for c in checks["checks"]) else "FAIL")
    test_report = _run_suite("test_h2_p3_mechanics_v1.py")
    regressions = [_run_suite(p) for p in REGRESSION_PATTERNS]
    wall_total = time.perf_counter() - t0
    # ---- dev budget ledger (F2): append this run's entry; snapshot ----
    ledger_path = BASE_DIR / "05_结果" / "H2" / "dev_budget_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry_ids = {e.get("entry_id") for e in ledger["entries"]}
    p3ae1_entry_id = f"P3-A-E1-{run_id}"
    if p3ae1_entry_id not in entry_ids:
        ledger["entries"].append({
            "entry_id": p3ae1_entry_id,
            "task": "Q3-H2-P3-A-E1 WAIT fragment identity + continuation "
                    "posterior world requalification",
            "run_id": run_id,
            "wall_clock_s": round(wall_total, 4),
            "status": "COMPLETED / AWAITING HUMAN GATE FINAL P3-A REVIEW",
            "category": "P3-A-E1 mechanics requalification (deterministic; "
                        "no stochastic rollout)",
            "namespace": "h2_rollout (formula only)",
            "note": "F1 active-fragment WAIT anchor; F2 WaitAnchor true "
                    "identity; F3 per-device continuation posterior; F4 PM "
                    "age_before; rollout post-key adapter; historical P3-A "
                    "roots immutable",
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
    print(f"[p3a-e1] checker overall={checks['overall']} "
          f"tests={test_report['tests_run']} "
          f"regressions={[r['tests_run'] for r in regressions]}")
    for c in checks["checks"]:
        print(f"  {c['check']}: {c['status']}")
    _build_evidence(staging_dir, run_id, checks, test_report, regressions,
                    verification=None, wall_total=wall_total)
    probe = _verify(staging_dir)
    print(f"[p3a-e1] probe verification ok={probe.get('ok')} {probe.get('error', '')}")
    if not probe.get("ok"):
        return 1
    _build_evidence(staging_dir, run_id, checks, test_report, regressions,
                    verification=probe, wall_total=wall_total)
    confirm = _verify(staging_dir)
    if not confirm.get("ok"):
        print(f"[p3a-e1] FAIL final-content verification {confirm.get('error', '')}")
        return 1
    promo = _promote(staging_dir, final_dir)
    if not promo["ok"]:
        print(f"[p3a-e1] FAIL promote {promo['sha_mismatches']}")
        return 1
    final_verify = _verify(final_dir)
    ok = (probe.get("ok") and confirm.get("ok") and promo["ok"]
          and final_verify.get("ok")
          and checks["overall"] == "PASS"
          and test_report["ok"] and all(r["ok"] for r in regressions))
    print(f"[p3a-e1] evidence written: {final_dir}")
    print(f"[p3a-e1] DONE overall={'PASS' if ok else 'FAIL'} wall={wall_total:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
