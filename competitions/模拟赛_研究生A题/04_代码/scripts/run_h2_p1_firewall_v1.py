#!/usr/bin/env python3
"""Q3-H2-P1-E2 evidence runner (raw-U static firewall + evidence packaging
final closure; F2a/F2b/F3).

Runs the independent C23 firewall checker (h2_p1_firewall_checker_v1), the
P1 test suite (test_h2_p1_firewall_v1.py) and the required deterministic
regression suites, then writes an immutable evidence root with the
repository's acyclic hash-inventory DAG.

E2 closures:
  F2a  raw-U firewall: the AST checker rejects EXACT forbidden raw keys
       (``u``) in dict subscript / dict.get / attribute access, in addition
       to the substring forbidden fragments (no false positives on
       ``resource`` / ``outcome`` / ``duration``).
  F2b  evidence packaging: precise per-check-ID report files
       (forbidden_access_report.json / ast_negative_cases_report.json /
       import_isolation_report.json / negative_leak_tests.json) -- no fuzzy
       filename mapping that can overwrite one report with another; plus an
       evidence SEMANTIC mapping self-check (the file that claims to be a
       given check really is that check).
  F3   final-root verification provenance (section 7, plan A):
       1. build the FULL staging evidence root (final file_hashes /
          manifest / checks);
       2. run the complete verification on staging: verify_hash_dag +
          verify_manifest_inventory_consistency + evidence semantic
          mapping; any failure -> STOP / non-zero;
       3. if all PASS, REBUILD staging with the ACTUAL verification results
          persisted, regenerate file_hashes, re-verify the final-content
          bytes;
       4. promote the verified staging bytes to the final immutable root
          (per-file SHA identity enforced; staging == final bytes);
       5. re-verify the final root read-only.
       The runner's exit depends on every verification; it never prints
       overall PASS unless all of them pass.

Evidence root: 05_结果/H2/p1/requalification_e2/run_<UTC>_<8hex>/

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
from checker import h2_p1_firewall_checker_v1 as fw  # noqa: E402

PACKAGE_REF = "Q3-H2-P1-E2"
BOOTSTRAP_SPEC_FILE = frm.BOOTSTRAP_SPEC_FILE
FORMAL_TASK_PACKAGE_FILE = frm.TASK_PACKAGE_FILE
FORMAL_TASK_PACKAGE_SHA = frm.TASK_PACKAGE_SNAPSHOT_SHA
REGISTRY_VERSION = "CR-V3.1"
ORIGINAL_P1_EVIDENCE = (BASE_DIR / "05_结果" / "H2" / "p1"
                        / "run_20260816T043411841146Z_3d4c6d46")
E1_REQUAL_EVIDENCE = (BASE_DIR / "05_结果" / "H2" / "p1" / "requalification"
                     / "run_20260816T045451170450Z_89984d8b")

SCOPE_AUDIT = {
    "density_accepted_evidence_modified": "NO",
    "h1_engine_semantics_modified": "NO",
    "key_schema_modified": "NO",
    "replacement_history_semantics": "UNCHANGED / VERIFIED (F1 closed; NOT "
                                     "re-modified)",
    "posterior_math_implemented": "NO",
    "lifetime_resampling_implemented": "NO",
    "h2_policy_implemented": "NO",
    "rollout_implemented": "NO",
    "new_random_worlds": "NO",
    "h2_tuning_consumed": "NO",
    "h2_holdout_consumed": "NO",
    "c25_run": "NO",
    "q4": "NO",
    "original_p1_evidence": f"{ORIGINAL_P1_EVIDENCE.name} = immutable "
                             "(HISTORICAL_P1_EXECUTION_WITH_C23_FIREWALL_"
                             "REVIEW_FINDINGS)",
    "e1_requal_evidence": f"{E1_REQUAL_EVIDENCE.name} = immutable "
                          "(P1-E1 EXECUTION WITH FINAL HUMAN-GATE FINDINGS)",
    "repair_closures": {
        "F2a": "raw-U exact forbidden key in AST checker (dict subscript / "
               "dict.get / attribute)",
        "F2b": "precise per-check-ID evidence report files + evidence "
               "semantic mapping self-check",
        "F3": "final-root verification provenance: verified staging "
              "promoted byte-identical to final; post-promotion read-only "
              "re-verify",
    },
    "implemented": [
        "checker/h2_p1_firewall_checker_v1.py (F2a: EXACT_FORBIDDEN_KEYS + "
        "NEG-U1/NEG-U2)",
        "scripts/run_h2_p1_firewall_v1.py (F2b/F3: precise report mapping + "
        "semantic mapping check + promote-with-identity)",
        "tests/test_h2_p1_firewall_v1.py (T23-T28)",
    ],
}

REGRESSION_PATTERNS = (
    "test_g3_key_schema_v1.py",
    "test_h2_q3_density_v1.py",
    "test_q3_h1_formal_v1.py",
    "test_g3_random_des_v1.py",
)

# Precise per-check-ID evidence report file mapping (F2b).
REPORT_MAPPING: dict[str, str] = {
    "A_FIELD_WHITELIST": "field_whitelist_report.json",
    "B_FORBIDDEN_ACCESS": "forbidden_access_report.json",
    "B_AST_NEGATIVE_CASES": "ast_negative_cases_report.json",
    "C_IMPORT_AST_ISOLATION": "import_isolation_report.json",
    "D_SAME_OBSERVABLE_HISTORY": "same_observable_hidden_world_report.json",
    "E_NEGATIVE_LEAK_TESTS": "negative_leak_tests.json",
    "REPLACEMENT_HISTORY_SEMANTICS": "replacement_history_semantic_report.json",
    "POSTERIOR_STATE_P1_SEAM": "posterior_state_seam_report.json",
}


def evidence_mapping_check(evidence_dir: Path) -> dict[str, Any]:
    """Semantic evidence mapping (section 6): every report file must carry
    the check ID it claims to be.  A file with the right hash but the wrong
    content for its filename is FAIL."""
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
    return {
        "check": "EVIDENCE_SEMANTIC_MAPPING",
        "status": "PASS" if ok else "FAIL",
        "files": results,
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
    """Run the fail-closed verifiers: verify_hash_dag +
    verify_manifest_inventory_consistency + evidence semantic mapping.
    Returns ACTUAL results; failures are returned as ok=False."""
    try:
        dag = frm.verify_hash_dag(out_dir)
        cons = frm.verify_manifest_inventory_consistency(out_dir)
        mapping = evidence_mapping_check(out_dir)
        ok = (dag["hash_graph_acyclic"] is True
              and dag["mismatches"] == 0
              and "PASS" in cons["manifest_output_hashes"]
              and "PASS" in cons["manifest_inventory_crosscheck"]
              and cons["c21_report_sha_consistency"] == "PASS"
              and mapping["status"] == "PASS")
        return {
            "ok": ok,
            "hash_graph_acyclic": dag["hash_graph_acyclic"],
            "inventory_n": dag["inventory_n"],
            "mismatches": dag["mismatches"],
            "manifest_output_hashes": cons["manifest_output_hashes"],
            "manifest_inventory_crosscheck": cons["manifest_inventory_crosscheck"],
            "c21_report_sha_consistency": cons["c21_report_sha_consistency"],
            "evidence_semantic_mapping": mapping["status"],
            "detail": {"dag": dag, "consistency": cons, "mapping": mapping},
        }
    except AssertionError as exc:
        return {"ok": False, "error": f"AssertionError: {exc}"}


def _build_evidence(out_dir: Path, run_id: str, checks: dict[str, Any],
                    test_report: dict[str, Any],
                    regressions: list[dict[str, Any]],
                    verification: Optional[dict[str, Any]],
                    wall_total: float) -> None:
    """Build the full evidence.  ``verification`` is None in the probe pass
    (C21 statuses PENDING_PROBE) or the actual verifier result in the final
    pass (C21 statuses = real).  Precise per-check-ID report files (F2b)."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_bytes = Path(BOOTSTRAP_SPEC_FILE).read_bytes()
    spec_sha = _sha256_bytes(spec_bytes)
    (out_dir / "bootstrap_spec_snapshot.md").write_bytes(spec_bytes)
    package_yaml = (
        "# Q3-H2-P1-E2 task-package snapshot (Human Gate narrow final "
        "repair)\n"
        f"package_ref: {PACKAGE_REF}\n"
        "authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED "
        "section 7 (C23 observable-information boundary) + Q3-H2-P1-E2 "
        "Human Gate package (F2a/F2b/F3)\n"
        f"bootstrap_spec_snapshot: bootstrap_spec_snapshot.md\n"
        f"bootstrap_spec_sha256: {spec_sha}\n"
        f"formal_task_package_sha256: {FORMAL_TASK_PACKAGE_SHA}\n"
        "density_lineage: FINAL PASS / ACCEPTED (D-14 A 7/7 B 7/7; E1 "
        "43fc39a + E2 79f5c0f)\n"
        "f1_replacement_history: VERIFIED CLOSED (UNCHANGED in E2)\n"
        "repair: F2a raw-U exact forbidden key; F2b precise evidence report "
        "mapping; F3 verified-staging promoted byte-identical to final\n"
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
    # precise per-check-ID reports (F2b): NEVER overwrite one check with
    # another via fuzzy filename conditions.
    for check in checks["checks"]:
        fname = REPORT_MAPPING.get(check["check"])
        if fname is not None:
            _dump_json(out_dir / fname, check)
    mapping_result = evidence_mapping_check(out_dir)
    _dump_json(out_dir / "evidence_semantic_mapping_report.json", mapping_result)

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
        "scope": "Q3-H2-P1-E2 evidence root",
        "status": "PASS" if overall_ok else "FAIL",
        "verification": verification,
        "items": [
            {"id": "C21a", "status": c21a,
             "note": "acyclic hash inventory (RULE A) -- status from the "
                     "ACTUAL fail-closed verifier result"},
            {"id": "C21b", "status": c21b,
             "note": "manifest/inventory/actual SHA consistency -- status "
                     "from the ACTUAL fail-closed verifier result"},
            {"id": "C21c", "status": "PASS" if overall_ok else "FAIL",
             "note": "P1-E2 firewall checker overall + tests + regressions"},
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
            "evidence_semantic_mapping": verification.get(
                "evidence_semantic_mapping") if verification else None,
        },
        "items": [
            {"check_id": "CR-V3.1/C23", "status": checks["overall"],
             "note": ("C23 INFORMATION-FIREWALL / P1-APPLICABLE CLAUSES = "
                      f"{checks['overall']}; FULL C23 END-TO-END = PENDING "
                      "(action/policy path not implemented)")},
            {"check_id": "B_FORBIDDEN_ACCESS", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "B_FORBIDDEN_ACCESS")},
            {"check_id": "B_AST_NEGATIVE_CASES", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "B_AST_NEGATIVE_CASES")},
            {"check_id": "C_IMPORT_AST_ISOLATION", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "C_IMPORT_AST_ISOLATION")},
            {"check_id": "A_FIELD_WHITELIST", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "A_FIELD_WHITELIST")},
            {"check_id": "D_SAME_OBSERVABLE_HISTORY", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "D_SAME_OBSERVABLE_HISTORY")},
            {"check_id": "E_NEGATIVE_LEAK_TESTS", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "E_NEGATIVE_LEAK_TESTS")},
            {"check_id": "REPLACEMENT_HISTORY_SEMANTICS", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "REPLACEMENT_HISTORY_SEMANTICS")},
            {"check_id": "POSTERIOR_STATE_P1_SEAM", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "POSTERIOR_STATE_P1_SEAM")},
            {"check_id": "EVIDENCE_SEMANTIC_MAPPING",
             "status": mapping_result["status"]},
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
        "purpose": "h2_p1_c23_firewall_final_closure",
        "formal": True,
        "label": ("Q3-H2-P1-E2 raw-U static firewall + evidence packaging "
                  "final closure (F2a/F2b/F3)"),
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
        "f1_replacement_history": "VERIFIED CLOSED / UNCHANGED",
        "repair": {
            "F2a": "EXACT_FORBIDDEN_KEYS=('u',) in AST checker; NEG-U1/U2 "
                   "reject rec['u'] / rec.get('u')",
            "F2b": "precise per-check-ID report files + evidence semantic "
                   "mapping check",
            "F3": "verified staging promoted byte-identical to final; "
                  "post-promotion read-only re-verify",
        },
        "c23": {"applicable_clauses": checks["overall"],
                "full_end_to_end": "PENDING",
                "action_equivalence": "DEFERRED_TO_POLICY_STAGE"},
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
                               "forbidden_access_report.json",
                               "ast_negative_cases_report.json",
                               "import_isolation_report.json",
                               "negative_leak_tests.json",
                               "replacement_history_semantic_report.json",
                               "same_observable_hidden_world_report.json",
                               "posterior_state_seam_report.json",
                               "evidence_semantic_mapping_report.json",
                               "test_report.json", "regression_report.json",
                               "scope_audit.json",
                               "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "Q3-H2-P1-E2：F2a raw-U 精确禁读键（u）进入 AST checker（subscript/"
            "dict.get/attribute；不误杀 resource/outcome/duration）；F2b 按 "
            "check ID 精确映射报告文件 + evidence semantic mapping 自检；F3 "
            "最终根 verification provenance（验证过的 staging 字节一致 promote "
            "到最终根 + promote 后只读复验）。",
            "F1 replacement_history completed-only = VERIFIED CLOSED（本包未改动）。",
            "C23 P1-APPLICABLE = PASS/FAIL（按实际条件）；FULL C23 END-TO-END "
            "= PENDING；action-equivalence DEFERRED_TO_POLICY_STAGE。",
            "P1 FINAL = NOT YET HUMAN-GATE ACCEPTED；P2/P3 = NOT AUTHORIZED；"
            "C25 = NOT AUTHORIZED。",
            "原 P1 evidence 3d4c6d46 与 E1 requalification evidence 89984d8b "
            "均 immutable（未修改）。",
            "C21：acyclic hash inventory（DAG）+ manifest/inventory/actual 一致"
            "性（fail-closed）；C21a/C21b 状态来自实际 verification。",
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


def _promote(staging: Path, final: Path) -> dict[str, Any]:
    """Promote the verified staging bytes to the final immutable root via
    copy; require per-file SHA identity between staging and final (every
    file, including file_hashes.sha256)."""
    if final.exists():
        shutil.rmtree(final)
    shutil.copytree(staging, final)
    mismatches: list[str] = []
    for p in sorted(staging.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(staging)
        q = final / rel
        if not q.is_file() or _sha256_file(p) != _sha256_file(q):
            mismatches.append(rel.as_posix())
    return {
        "ok": len(mismatches) == 0,
        "files_copied": sum(1 for p in staging.rglob("*") if p.is_file()),
        "sha_mismatches": mismatches,
    }


def main(argv: Optional[list[str]] = None) -> int:
    output_root = BASE_DIR / "05_结果" / "H2" / "p1" / "requalification_e2"
    run_id = _new_run_id()
    final_dir = output_root / f"run_{run_id}"
    staging_dir = BASE_DIR / ".." / "tmp" / f"p1_e2_staging_{run_id}"
    print(f"[p1-e2] run_id={run_id}")
    t0 = time.perf_counter()
    checks = fw.run_all()
    test_report = _run_tests()
    regressions = [_run_suite(p) for p in REGRESSION_PATTERNS]
    wall_total = time.perf_counter() - t0
    print(f"[p1-e2] checker={checks['overall']} tests={test_report['tests_run']} "
          f"regressions={[r['tests_run'] for r in regressions]}")

    # ---- F3 (plan A): probe -> final-content build -> promote -> re-verify ----
    _build_evidence(staging_dir, run_id, checks, test_report, regressions,
                    verification=None, wall_total=wall_total)
    probe = _verify(staging_dir)
    print(f"[p1-e2] probe verification ok={probe.get('ok')} "
          f"{probe.get('error', '')}")
    if not probe.get("ok"):
        print("[p1-e2] FAIL: probe verification failed; no final evidence "
              "written")
        return 1
    # final-content build with the ACTUAL verification persisted
    _build_evidence(staging_dir, run_id, checks, test_report, regressions,
                    verification=probe, wall_total=wall_total)
    confirm = _verify(staging_dir)
    print(f"[p1-e2] final-content verification ok={confirm.get('ok')} "
          f"{confirm.get('error', '')}")
    if not confirm.get("ok"):
        print("[p1-e2] FAIL: final-content verification failed")
        return 1
    promo = _promote(staging_dir, final_dir)
    print(f"[p1-e2] promote ok={promo['ok']} files={promo['files_copied']} "
          f"sha_mismatches={promo['sha_mismatches']}")
    if not promo["ok"]:
        print("[p1-e2] FAIL: staging -> final byte identity broken")
        return 1
    final_verify = _verify(final_dir)
    print(f"[p1-e2] final-root read-only verification ok="
          f"{final_verify.get('ok')} {final_verify.get('error', '')}")
    ok = (probe.get("ok") and confirm.get("ok") and promo["ok"]
          and final_verify.get("ok")
          and checks["overall"] == "PASS"
          and test_report["ok"] and all(r["ok"] for r in regressions))
    print(f"[p1-e2] evidence written: {final_dir}")
    print(f"[p1-e2] DONE overall={'PASS' if ok else 'FAIL'} "
          f"wall={wall_total:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
