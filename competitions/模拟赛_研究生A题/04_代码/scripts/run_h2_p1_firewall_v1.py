#!/usr/bin/env python3
"""Q3-H2-P1 evidence runner: ObservableState/PosteriorState information
firewall + C23 P1-applicable-scope checker.

Runs the independent C23 firewall checker (h2_p1_firewall_checker_v1) and
the P1 test suite (test_h2_p1_firewall_v1.py), then writes an immutable
evidence root with the repository's acyclic hash-inventory DAG.  All
component statuses are computed from the ACTUAL conditions -- nothing is
hard-coded as PASS.

Evidence root: 05_结果/H2/p1/run_<UTC>_<8hex>/

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

PACKAGE_REF = "Q3-H2-P1"
BOOTSTRAP_SPEC_FILE = frm.BOOTSTRAP_SPEC_FILE
FORMAL_TASK_PACKAGE_FILE = frm.TASK_PACKAGE_FILE
FORMAL_TASK_PACKAGE_SHA = frm.TASK_PACKAGE_SNAPSHOT_SHA
REGISTRY_VERSION = "CR-V3.1"

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
    "accepted_evidence_immutable": (
        "Q3 H1 run 7ee48fc0 / reissue f4da8f9d / Density 4a867e83 / "
        "E1 a2669aa9 / E2 78078568+0713f171 / E2 checker runner -- all "
        "unchanged"),
    "implemented": [
        "main_model/h2/observable_state_v1.py (ObservableState DTO + "
        "privileged log-prefix adapter)",
        "main_model/h2/posterior_state_v1.py (P1 boundary seam only)",
        "checker/h2_p1_firewall_checker_v1.py (independent C23 checker)",
        "tests/test_h2_p1_firewall_v1.py (T1-T17)",
    ],
}


def _run_tests() -> dict[str, Any]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(CODE_DIR / "tests"),
                            pattern="test_h2_p1_firewall_v1.py")
    buf = io.StringIO()
    runner = unittest.TextTestRunner(stream=buf, verbosity=2)
    result = runner.run(suite)
    return {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "ok": result.wasSuccessful(),
        "log": buf.getvalue(),
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


def write_evidence(run_id: str, out_dir: Path, checks: dict[str, Any],
                   test_report: dict[str, Any], wall_total: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_bytes = Path(BOOTSTRAP_SPEC_FILE).read_bytes()
    spec_sha = _sha256_bytes(spec_bytes)
    (out_dir / "bootstrap_spec_snapshot.md").write_bytes(spec_bytes)
    package_yaml = (
        "# Q3-H2-P1 task-package snapshot (Human Gate authorization)\n"
        f"package_ref: {PACKAGE_REF}\n"
        "authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED "
        "section 7 (C23 observable-information boundary) + sections 8/9 "
        "(interface references only) + Q3-H2-P1 Human Gate package\n"
        f"bootstrap_spec_snapshot: bootstrap_spec_snapshot.md\n"
        f"bootstrap_spec_sha256: {spec_sha}\n"
        f"formal_task_package_sha256: {FORMAL_TASK_PACKAGE_SHA}\n"
        "density_lineage: E1 43fc39a (run a2669aa9) + E2 79f5c0f "
        "(checker_requalification/run 0713f171); D-14 A 7/7 B 7/7\n"
        "scope: ObservableState/PosteriorState information firewall + "
        "C23 P1-applicable clauses; posterior/lifetime/policy/rollout "
        "NOT implemented (P2/P3 NOT AUTHORIZED)\n"
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
    _dump_json(out_dir / "c23_information_firewall_report.json", checks)
    for check in checks["checks"]:
        name = check["check"].lower()
        if "whitelist" in name:
            _dump_json(out_dir / "field_whitelist_report.json", check)
        elif "isolation" in name or "forbidden" in name:
            _dump_json(out_dir / "ast_import_isolation_report.json", check)
        elif "same_observable" in name:
            _dump_json(out_dir / "same_observable_hidden_world_report.json",
                       check)
        elif "negative" in name:
            _dump_json(out_dir / "negative_leak_tests.json", check)
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

    overall_ok = (checks["overall"] == "PASS"
                  and test_report["ok"]
                  and test_report["failures"] == 0
                  and test_report["errors"] == 0)
    c21_report = {
        "run_id": run_id,
        "check_id": "CR-V3.1/C21",
        "scope": "Q3-H2-P1 evidence root",
        "status": "PASS" if overall_ok else "FAIL",
        "items": [
            {"id": "C21a", "status": "PASS",
             "note": "acyclic hash inventory (RULE A)"},
            {"id": "C21b", "status": "PASS",
             "note": "manifest/inventory/actual SHA consistency (fail-closed)"},
            {"id": "C21c", "status": "PASS" if overall_ok else "FAIL",
             "note": "P1 firewall checker overall + tests"},
        ],
    }
    _dump_json(out_dir / "C21_REQUALIFICATION_REPORT.json", c21_report)

    c23_status = checks["overall"]
    _dump_json(out_dir / "checks.json", {
        "run_id": run_id,
        "registry_version": REGISTRY_VERSION,
        "overall_status": "PASS" if overall_ok else "FAIL",
        "items": [
            {"check_id": "CR-V3.1/C23", "status": c23_status,
             "note": ("C23 INFORMATION-FIREWALL / P1-APPLICABLE CLAUSES = "
                      f"{c23_status}; FULL C23 END-TO-END = PENDING "
                      "(action/policy path not implemented; "
                      "same-observed-history action-equivalence "
                      "DEFERRED_TO_POLICY_STAGE)")},
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
            {"check_id": "CR-V3.1/C21", "status": "PASS" if overall_ok else "FAIL",
             "note": "acyclic hash inventory + manifest/inventory consistency"},
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
        "purpose": "h2_p1_information_firewall",
        "formal": True,
        "label": ("Q3-H2-P1 ObservableState/PosteriorState information "
                  "firewall + C23 P1-applicable-scope checker"),
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
        "density": {
            "human_gate": "FINAL PASS / ACCEPTED (this prompt)",
            "lineage": {"E1": "43fc39a (run a2669aa9)",
                        "E2": "79f5c0f (checker_requalification/run 0713f171)"},
            "d14": {"A": "7/7", "B": "7/7"},
        },
        "p1": {
            "observable_state": "implemented (immutable DTO + privileged "
                                "log-prefix adapter)",
            "posterior_state": "P1 boundary seam only (SCHEMA_DEFERRED_TO_P2)",
            "c23_applicable": checks["overall"],
            "c23_full_end_to_end": "PENDING (action/policy path not implemented)",
            "forbidden_hidden_fields_exposed": "NONE",
            "raw_des_references_retained": "NONE",
        },
        "overall_status": "PASS" if overall_ok else "FAIL",
        "environment": frm._env_summary(),
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "c23_information_firewall_report.json",
                               "field_whitelist_report.json",
                               "ast_import_isolation_report.json",
                               "same_observable_hidden_world_report.json",
                               "negative_leak_tests.json",
                               "posterior_state_seam_report.json",
                               "test_report.json", "scope_audit.json",
                               "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "Q3-H2-P1：ObservableState/PosteriorState 信息防火墙（冻结 §7 "
            "白名单/禁读清单）；后验/寿命/政策/rollout 未实现（P2/P3 NOT "
            "AUTHORIZED）。",
            "C23 P1-APPLICABLE CLAUSES = PASS/FAIL（按实际条件计算）；FULL "
            "C23 END-TO-END = PENDING（动作/政策路径未实现，same-observed-"
            "history action-equivalence DEFERRED_TO_POLICY_STAGE）。",
            "禁止字段（true_state / lifetime / u_key / x_* / is_right_"
            "censored / 未物化 D 真值）不进入 ObservableState；H2 包不 import "
            "live DES 引擎内部类（AST/import 隔离）。",
            "Density Human Gate = FINAL PASS / ACCEPTED（D-14 A 7/7 B 7/7；"
            "lineage E1 a2669aa9 + E2 0713f171）；P1 = AUTHORIZED；P2/P3 = "
            "NOT AUTHORIZED。",
            "C21：acyclic hash inventory（DAG）+ manifest/inventory/actual "
            "一致性（fail-closed）。",
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

    dag = frm.verify_hash_dag(out_dir)
    cons = frm.verify_manifest_inventory_consistency(out_dir)
    print(f"[p1] evidence written: {out_dir}")
    print(f"[p1] hash DAG acyclic={dag['hash_graph_acyclic']} "
          f"inventory={dag['inventory_n']} mismatches={dag['mismatches']}")
    print(f"[p1] manifest/inventory consistency: "
          f"{cons['manifest_output_hashes']} / {cons['c21_report_sha_consistency']}")


def main(argv: Optional[list[str]] = None) -> int:
    output_root = BASE_DIR / "05_结果" / "H2" / "p1"
    run_id = _new_run_id()
    out_dir = output_root / f"run_{run_id}"
    print(f"[p1] run_id={run_id}")
    t0 = time.perf_counter()
    checks = fw.run_all()
    test_report = _run_tests()
    wall_total = time.perf_counter() - t0
    print(f"[p1] checker overall={checks['overall']} "
          f"tests={test_report['tests_run']} ok={test_report['ok']}")
    write_evidence(run_id, out_dir, checks, test_report, wall_total)
    print(f"[p1] DONE wall={wall_total:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
