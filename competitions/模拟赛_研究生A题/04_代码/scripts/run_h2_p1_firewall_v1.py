#!/usr/bin/env python3
"""Q3-H2-P1-E1 evidence runner (C23 firewall semantics repair; F1/F2/F3).

Runs the independent C23 firewall checker (h2_p1_firewall_checker_v1), the
P1 test suite (test_h2_p1_firewall_v1.py) and the required deterministic
regression suites, then writes an immutable evidence root with the
repository's acyclic hash-inventory DAG.

F3 (fail-closed C21 / hash verification): the runner's success exit
EXPLICITLY depends on the ACTUAL results of verify_hash_dag and
verify_manifest_inventory_consistency:
  * hash_graph_acyclic == True
  * inventory mismatches == []
  * manifest/inventory consistency == PASS
  * C21 required consistency == PASS
Two-phase evidence build: phase 1 probes the identical evidence structure
in a git-ignored staging dir to obtain the real verification results;
phase 2 writes the FINAL evidence with C21/checks/manifest statuses
computed from those ACTUAL results (C21a/C21b are NEVER hard-coded PASS
before verification passes).  If any verification fails, the runner exits
non-zero and never prints overall PASS.

Evidence root: 05_结果/H2/p1/requalification/run_<UTC>_<8hex>/

Python 3.12, standard library only.
"""
from __future__ import annotations

import io
import json
import secrets
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
from checker import h2_p1_firewall_checker_v1 as fw  # noqa: E402

PACKAGE_REF = "Q3-H2-P1-E1"
BOOTSTRAP_SPEC_FILE = frm.BOOTSTRAP_SPEC_FILE
FORMAL_TASK_PACKAGE_FILE = frm.TASK_PACKAGE_FILE
FORMAL_TASK_PACKAGE_SHA = frm.TASK_PACKAGE_SNAPSHOT_SHA
REGISTRY_VERSION = "CR-V3.1"
# Original P1 evidence root (immutable; marked historical in the report).
ORIGINAL_P1_EVIDENCE = (BASE_DIR / "05_结果" / "H2" / "p1"
                        / "run_20260816T043411841146Z_3d4c6d46")

SCOPE_AUDIT = {
    "density_accepted_evidence_modified": "NO",
    "h1_engine_semantics_modified": "NO",
    "key_schema_modified": "NO",
    "posterior_math_implemented": "NO",
    "lifetime_resampling_implemented": "NO",
    "h2_policy_implemented": "NO",
    "rollout_implemented": "NO",
    "new_random_worlds": "NO",
    "h2_tuning_consumed": "NO",
    "h2_holdout_consumed": "NO",
    "c25_run": "NO",
    "q4": "NO",
    "original_p1_evidence": (
        f"{ORIGINAL_P1_EVIDENCE.name} = "
        "HISTORICAL_P1_EXECUTION_WITH_C23_FIREWALL_REVIEW_FINDINGS "
        "(immutable; not modified)"),
    "repair_closures": {
        "F1": "replacement_history completed-only (ReplacementObs.completed "
              "removed; CALIBRATION_COMPLETE <= t required)",
        "F2": "AST checker covers dict subscript + dict.get forbidden keys",
        "F3": "C21/hash verification truly fail-closed (two-phase evidence "
              "build; exit depends on actual verifier results)",
    },
    "implemented": [
        "main_model/h2/observable_state_v1.py (F1 fix)",
        "checker/h2_p1_firewall_checker_v1.py (F2 fix + semantic invariant + "
        "AST negatives + frozen-per-class)",
        "tests/test_h2_p1_firewall_v1.py (T18-T20 + AST negatives + "
        "all-DTO-frozen)",
    ],
}

REGRESSION_PATTERNS = (
    "test_g3_key_schema_v1.py",
    "test_h2_q3_density_v1.py",
    "test_q3_h1_formal_v1.py",
    "test_g3_random_des_v1.py",
)


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
        "log_tail": buf.getvalue()[-2000:],
    }


def _run_tests() -> dict[str, Any]:
    return _run_suite("test_h2_p1_firewall_v1.py")


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


def _verify(out_dir: Path) -> dict[str, Any]:
    """Run the fail-closed verifiers; return ACTUAL results (never raises
    out of the runner; failures are returned as ok=False)."""
    try:
        dag = frm.verify_hash_dag(out_dir)
        cons = frm.verify_manifest_inventory_consistency(out_dir)
        ok = (dag["hash_graph_acyclic"] is True
              and dag["mismatches"] == 0
              and "PASS" in cons["manifest_output_hashes"]
              and "PASS" in cons["manifest_inventory_crosscheck"]
              and cons["c21_report_sha_consistency"] == "PASS")
        return {
            "ok": ok,
            "hash_graph_acyclic": dag["hash_graph_acyclic"],
            "inventory_n": dag["inventory_n"],
            "mismatches": dag["mismatches"],
            "manifest_output_hashes": cons["manifest_output_hashes"],
            "manifest_inventory_crosscheck": cons["manifest_inventory_crosscheck"],
            "c21_report_sha_consistency": cons["c21_report_sha_consistency"],
            "detail": {"dag": dag, "consistency": cons},
        }
    except AssertionError as exc:
        return {"ok": False, "error": f"AssertionError: {exc}"}


def _build_evidence(out_dir: Path, run_id: str, checks: dict[str, Any],
                    test_report: dict[str, Any],
                    regressions: list[dict[str, Any]],
                    verification: Optional[dict[str, Any]],
                    wall_total: float) -> None:
    """Build the full evidence.  ``verification`` is None in the phase-1
    probe (C21 statuses marked PENDING_PROBE) or the actual verifier result
    in the final build (C21 statuses = real)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_bytes = Path(BOOTSTRAP_SPEC_FILE).read_bytes()
    spec_sha = _sha256_bytes(spec_bytes)
    (out_dir / "bootstrap_spec_snapshot.md").write_bytes(spec_bytes)
    package_yaml = (
        "# Q3-H2-P1-E1 task-package snapshot (Human Gate narrow repair)\n"
        f"package_ref: {PACKAGE_REF}\n"
        "authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED "
        "section 7 (C23 observable-information boundary) + Q3-H2-P1-E1 "
        "Human Gate package (F1/F2/F3)\n"
        f"bootstrap_spec_snapshot: bootstrap_spec_snapshot.md\n"
        f"bootstrap_spec_sha256: {spec_sha}\n"
        f"formal_task_package_sha256: {FORMAL_TASK_PACKAGE_SHA}\n"
        "density_lineage: FINAL PASS / ACCEPTED (D-14 A 7/7 B 7/7; E1 "
        "43fc39a + E2 79f5c0f)\n"
        "repair: F1 replacement_history completed-only; F2 AST forbidden "
        "dict-subscript/get; F3 C21 fail-closed two-phase\n"
        "original_p1_evidence: run_20260816T043411841146Z_3d4c6d46 = "
        "HISTORICAL_P1_EXECUTION_WITH_C23_FIREWALL_REVIEW_FINDINGS "
        "(immutable)\n"
        "evidence_rule: ACYCLIC hash DAG (RULE A)\n"
    )
    (out_dir / "task_package_snapshot.yaml").write_text(
        package_yaml, encoding="utf-8", newline="\n")

    _dump_json(out_dir / "commands.json", {
        "run_id": run_id,
        "command": "python 04_代码/scripts/run_h2_p1_firewall_v1.py",
        "wall_clock_s": round(wall_total, 2),
    })
    _dump_json(out_dir / "environment.json", frm._env_summary())
    _dump_json(out_dir / "scope_audit.json", SCOPE_AUDIT)
    _dump_json(out_dir / "test_report.json", test_report)
    _dump_json(out_dir / "regression_report.json", {
        "note": ("deterministic regression suites; commands / exit codes / "
                 "test counts recorded truthfully; no formal 1400 worlds"),
        "regressions": regressions,
    })
    _dump_json(out_dir / "c23_information_firewall_report.json", checks)
    for check in checks["checks"]:
        name = check["check"].lower()
        if "whitelist" in name:
            _dump_json(out_dir / "field_whitelist_report.json", check)
        elif "isolation" in name or "forbidden" in name \
                or "negative" in name:
            _dump_json(out_dir / "ast_import_isolation_report.json", check)
        elif "same_observable" in name:
            _dump_json(out_dir / "same_observable_hidden_world_report.json",
                       check)
        elif "replacement_history" in name:
            _dump_json(out_dir / "replacement_history_semantic_report.json",
                       check)
    _dump_json(out_dir / "negative_leak_tests.json",
               next(c for c in checks["checks"]
                    if c["check"] == "E_NEGATIVE_LEAK_TESTS"))
    _dump_json(out_dir / "posterior_state_seam_report.json",
               next(c for c in checks["checks"]
                    if c["check"] == "POSTERIOR_STATE_P1_SEAM"))

    hashes = {
        "task_package_snapshot": {"path": "task_package_snapshot.yaml",
                                  "sha256": _sha256_file(out_dir / "task_package_snapshot.yaml")},
        "bootstrap_spec": {"sha256": spec_sha},
        "formal_task_package": {"sha256": _sha256_file(FORMAL_TASK_PACKAGE_FILE)},
        "observable_state": _sha256_file(MAIN_MODEL / "h2" / "observable_state_v1.py"),
        "posterior_state": _sha256_file(MAIN_MODEL / "h2" / "posterior_state_v1.py"),
        "firewall_checker": _sha256_file(CODE_DIR / "checker" / "h2_p1_firewall_checker_v1.py"),
        "tests": _sha256_file(CODE_DIR / "tests" / "test_h2_p1_firewall_v1.py"),
        "runner": _sha256_file(Path(__file__).resolve()),
        "engine": _sha256_file(MAIN_MODEL / "g3" / "random_des_v1.py"),
        "key_schema": _sha256_file(MAIN_MODEL / "g3" / "key_schema_v1.py"),
        "problem_contract": _sha256_file(frm.PROBLEM_CONTRACT_FILE),
        "parameters_csv": _sha256_file(frm.PARAMETERS_CSV),
        "registry": _sha256_file(BASE_DIR / "01_审计" / "检查注册表_V3.1.md"),
    }
    _dump_json(out_dir / "input_hashes.json", hashes)

    # ---- C21 / checks / manifest statuses from ACTUAL conditions ----
    verify_ok = verification is not None and verification.get("ok") is True
    c21a = ("PASS" if verify_ok else
            ("PENDING_PROBE" if verification is None else "FAIL"))
    c21b = c21a
    overall_ok = (checks["overall"] == "PASS"
                  and test_report["ok"]
                  and all(r["ok"] for r in regressions)
                  and verify_ok)
    c21_report = {
        "run_id": run_id,
        "check_id": "CR-V3.1/C21",
        "scope": "Q3-H2-P1-E1 evidence root",
        "status": "PASS" if overall_ok else "FAIL",
        "verification": verification,
        "items": [
            {"id": "C21a", "status": c21a,
             "note": ("acyclic hash inventory (RULE A) -- status from the "
                      "ACTUAL fail-closed verifier result")},
            {"id": "C21b", "status": c21b,
             "note": ("manifest/inventory/actual SHA consistency -- status "
                      "from the ACTUAL fail-closed verifier result")},
            {"id": "C21c", "status": "PASS" if overall_ok else "FAIL",
             "note": "P1-E1 firewall checker overall + tests + regressions"},
        ],
    }
    _dump_json(out_dir / "C21_REQUALIFICATION_REPORT.json", c21_report)

    _dump_json(out_dir / "checks.json", {
        "run_id": run_id,
        "registry_version": REGISTRY_VERSION,
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
        },
        "items": [
            {"check_id": "CR-V3.1/C23", "status": checks["overall"],
             "note": ("C23 INFORMATION-FIREWALL / P1-APPLICABLE CLAUSES = "
                      f"{checks['overall']}; FULL C23 END-TO-END = PENDING "
                      "(action/policy path not implemented)")},
            {"check_id": "REPLACEMENT_HISTORY_SEMANTICS", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "REPLACEMENT_HISTORY_SEMANTICS")},
            {"check_id": "B_AST_NEGATIVE_CASES", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "B_AST_NEGATIVE_CASES")},
            {"check_id": "A_FIELD_WHITELIST", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "A_FIELD_WHITELIST")},
            {"check_id": "B_FORBIDDEN_ACCESS", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "B_FORBIDDEN_ACCESS")},
            {"check_id": "C_IMPORT_AST_ISOLATION", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "C_IMPORT_AST_ISOLATION")},
            {"check_id": "D_SAME_OBSERVABLE_HISTORY", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "D_SAME_OBSERVABLE_HISTORY")},
            {"check_id": "E_NEGATIVE_LEAK_TESTS", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "E_NEGATIVE_LEAK_TESTS")},
            {"check_id": "POSTERIOR_STATE_P1_SEAM", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "POSTERIOR_STATE_P1_SEAM")},
            {"check_id": "TESTS", "status": "PASS" if test_report["ok"] else "FAIL",
             "count": f"{test_report['tests_run'] - test_report['failures'] - test_report['errors']}"
                      f"/{test_report['tests_run']}"},
            {"check_id": "REGRESSIONS", "status": "PASS" if all(
                r["ok"] for r in regressions) else "FAIL",
             "detail": [{"pattern": r["command"].split("'")[1],
                         "exit_code": r["exit_code"],
                         "tests_run": r["tests_run"]} for r in regressions]},
            {"check_id": "CR-V3.1/C21", "status": "PASS" if overall_ok else "FAIL",
             "note": "acyclic hash inventory + manifest/inventory consistency "
                     "(fail-closed; status from actual verification)"},
        ],
    })

    artifacts = [
        {"path": p.relative_to(out_dir).as_posix(),
         "bytes": p.stat().st_size, "sha256": _sha256_file(p)}
        for p in sorted(out_dir.rglob("*"))
        if p.is_file() and p.name != "file_hashes.sha256"
    ]
    manifest = {
        "run_id": run_id,
        "created_at": _utc_now(),
        "gate": "Q3",
        "purpose": "h2_p1_c23_firewall_requalification",
        "formal": True,
        "label": ("Q3-H2-P1-E1 C23 observable-state firewall semantics "
                  "repair (F1/F2/F3)"),
        "paper_authoritative": False,
        "task_package_ref": PACKAGE_REF,
        "task_package_snapshot_path": "task_package_snapshot.yaml",
        "bootstrap_spec_sha256": spec_sha,
        "formal_task_package_sha256": FORMAL_TASK_PACKAGE_SHA,
        "registry_version": REGISTRY_VERSION,
        "hash_inventory_path": "file_hashes.sha256",
        "hash_inventory_rule": (
            "ACYCLIC DAG (RULE A): run_manifest does not hash file_hashes.sha256 "
            "(only points to it); file_hashes.sha256 hashes all artifacts "
            "including run_manifest.json and task_package_snapshot.yaml, "
            "never itself."
        ),
        "random_world": {"consumption": "NONE"},
        "density": {"human_gate": "FINAL PASS / ACCEPTED",
                    "d14": {"A": "7/7", "B": "7/7"}},
        "repair": {
            "F1": "replacement_history completed-only (completed flag removed; "
                  "CALIBRATION_COMPLETE <= t required)",
            "F2": "AST checker covers Attribute + Subscript(const str) + "
                  "dict.get forbidden keys; AST negative cases PASS",
            "F3": "C21/hash verification fail-closed: exit depends on actual "
                  "verify_hash_dag / verify_manifest_inventory_consistency",
        },
        "c23": {
            "applicable_clauses": checks["overall"],
            "full_end_to_end": "PENDING",
            "action_equivalence": "DEFERRED_TO_POLICY_STAGE",
        },
        "p1_final": "NOT YET HUMAN-GATE ACCEPTED",
        "p2": "NOT AUTHORIZED",
        "p3": "NOT AUTHORIZED",
        "verification_fail_closed": (
            verification if verification is not None else "PROBE_PHASE"),
        "overall_status": "PASS" if overall_ok else "FAIL",
        "environment": frm._env_summary(),
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "c23_information_firewall_report.json",
                               "field_whitelist_report.json",
                               "ast_import_isolation_report.json",
                               "replacement_history_semantic_report.json",
                               "same_observable_hidden_world_report.json",
                               "negative_leak_tests.json",
                               "posterior_state_seam_report.json",
                               "test_report.json", "regression_report.json",
                               "scope_audit.json",
                               "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "Q3-H2-P1-E1：F1 replacement_history 只含已完成更换/校准；F2 AST "
            "checker 覆盖 dict subscript / dict.get 禁读字段 + AST 负例；F3 "
            "C21/hash 验证真正 fail-closed（两阶段 build；exit 依赖实际 "
            "verifier 结果）。",
            "C23 P1-APPLICABLE = PASS/FAIL（按实际条件）；FULL C23 END-TO-END "
            "= PENDING；action-equivalence DEFERRED_TO_POLICY_STAGE。",
            "P1 FINAL = NOT YET HUMAN-GATE ACCEPTED；P2/P3 = NOT AUTHORIZED；"
            "C25 = NOT AUTHORIZED。",
            "原 P1 evidence run_20260816T043411841146Z_3d4c6d46 = "
            "HISTORICAL_P1_EXECUTION_WITH_C23_FIREWALL_REVIEW_FINDINGS "
            "（immutable，未修改）。",
            "C21：acyclic hash inventory（DAG）+ manifest/inventory/actual "
            "一致性（fail-closed）；C21a/C21b 状态来自实际 verification。",
        ],
    }
    _dump_json(out_dir / "run_manifest.json", manifest)

    lines = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "file_hashes.sha256":
            rel = path.relative_to(out_dir).as_posix()
            lines.append(f"{_sha256_file(path)}  {rel}")
    (out_dir / "file_hashes.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv: Optional[list[str]] = None) -> int:
    output_root = BASE_DIR / "05_结果" / "H2" / "p1" / "requalification"
    run_id = _new_run_id()
    final_dir = output_root / f"run_{run_id}"
    staging_dir = BASE_DIR / ".." / "tmp" / f"p1_staging_{run_id}"
    print(f"[p1-e1] run_id={run_id}")
    t0 = time.perf_counter()
    checks = fw.run_all()
    test_report = _run_tests()
    regressions = [_run_suite(p) for p in REGRESSION_PATTERNS]
    wall_total = time.perf_counter() - t0
    print(f"[p1-e1] checker={checks['overall']} tests={test_report['tests_run']} "
          f"regressions={[r['tests_run'] for r in regressions]}")

    # ---- F3: two-phase fail-closed evidence build ----
    _build_evidence(staging_dir, run_id, checks, test_report, regressions,
                    verification=None, wall_total=wall_total)
    probe = _verify(staging_dir)
    print(f"[p1-e1] phase-1 (staging) verification ok={probe.get('ok')} "
          f"{probe.get('error', '')}")
    if not probe.get("ok"):
        print("[p1-e1] FAIL: phase-1 hash/C21 verification failed; no final "
              "evidence written")
        return 1
    _build_evidence(final_dir, run_id, checks, test_report, regressions,
                    verification=probe, wall_total=wall_total)
    final_verify = _verify(final_dir)
    print(f"[p1-e1] phase-2 (final) verification ok={final_verify.get('ok')} "
          f"{final_verify.get('error', '')}")
    ok = (probe.get("ok") and final_verify.get("ok")
          and checks["overall"] == "PASS"
          and test_report["ok"] and all(r["ok"] for r in regressions))
    print(f"[p1-e1] evidence written: {final_dir}")
    print(f"[p1-e1] DONE overall={'PASS' if ok else 'FAIL'} "
          f"wall={wall_total:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
