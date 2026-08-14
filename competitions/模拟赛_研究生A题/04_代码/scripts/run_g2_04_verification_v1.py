# -*- coding: utf-8 -*-
"""G2-04 one-command verification skeleton (CR-V3.1/C21).

Role
----
One script that, in a single run, performs the G2-04 verification chain for
the accepted deterministic minimal parallel DES (G2-03-SPEC-V1.0.2):

  1. runs the main DES (``04_代码/main_model/des/deterministic_des_v1.py``)
     on all 14 concrete fixtures (F1..F12 + subcases F4b/F9b) to produce the
     immutable event_log + metrics blocks (the DES is the OBJECT UNDER TEST
     here, exactly as the G2-04 task requires);
  2. runs the independent checker (``04_代码/checker/des_checker_v1.py``) on
     every event_log (checker never imports the main engine) and asserts each
     report is PASS;
  3. aggregates the per-fixture PASS/FAIL summary;
  4. emits the run_manifest skeleton fields: run_id (UTC
     YYYYMMDDTHHMMSSffffffZ_ + 8 hex via secrets.token_hex(4)),
     config/event_log/scripted-fixture/parameters/spec SHA-256 placeholder
     hashes, code snapshot hashes, raw-output references and the exit code.

Boundaries
----------
* Verification skeleton ONLY.  This script never writes to ``05_结果/`` and
  produces no formal evidence; the formal immutable run with
  run_manifest.json / commands.json / file_hashes.sha256 is executed by the
  Whole-G2 phase, not here.
* The script is the only non-test layer that may CALL the main DES: the
  checker module itself stays fully isolated (CR-V3.1/C19) and is only given
  the event_log, config, fixture, parameters and metrics.
* Python 3.12, standard library only.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]          # competitions/模拟赛_研究生A题
CODE_DIR = PROJECT_ROOT / "04_代码"
FIXTURES_PATH = CODE_DIR / "tests/fixtures/des_fixtures_F1_F12_v1.json"
PARAMETERS_PATH = PROJECT_ROOT / "02_数据/parameters.csv"
SPEC_PATH = PROJECT_ROOT / "08_项目管理/任务包/G2-03_无随机最小并行DES.yaml"
CHECKER_PATH = CODE_DIR / "checker/des_checker_v1.py"
MAIN_DES_PATH = CODE_DIR / "main_model/des/deterministic_des_v1.py"
STATE_MODELS_PATH = CODE_DIR / "main_model/des/state_models_v1.py"
TEST_CHECKER_PATH = CODE_DIR / "tests/test_des_checker_v1.py"
SCRIPT_PATH = CODE_DIR / "scripts/run_g2_04_verification_v1.py"

FIXTURES_ORDER = [
    "F1", "F2", "F3", "F4", "F4b", "F5", "F6", "F7", "F8", "F9", "F9b",
    "F10", "F11", "F12",
]

# Files whose SHA-256 go into the run_manifest skeleton code_snapshots.
CODE_SNAPSHOT_PATHS = [
    MAIN_DES_PATH,
    STATE_MODELS_PATH,
    CHECKER_PATH,
    TEST_CHECKER_PATH,
    SCRIPT_PATH,
]


def new_run_id(now_utc: datetime.datetime | None = None) -> str:
    """run_id = UTC YYYYMMDDTHHMMSSffffffZ_ + 8 hex chars (secrets.token_hex(4))."""
    if now_utc is None:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
    return now_utc.strftime("%Y%m%dT%H%M%S%fZ") + "_" + secrets.token_hex(4)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _join_imports() -> None:
    for entry in (str(CODE_DIR), str(CODE_DIR / "main_model")):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def load_fixtures() -> dict[str, dict]:
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    return {f["fixture_id"]: f for f in data["fixtures"]}


def run_des_fixture(fixture: dict):
    """Run the accepted main DES once (the object under test)."""
    _join_imports()
    from des import deterministic_des_v1 as de  # noqa: E402
    return de.run_des(fixture["config"], fixture)


def run_checker(fixture: dict, event_log: list, metrics: dict):
    """Run the independent checker (never imports the main engine)."""
    _join_imports()
    from checker import des_checker_v1 as chk  # noqa: E402
    return chk.check_event_log(event_log, fixture["config"], fixture,
                               parameters=str(PARAMETERS_PATH), metrics=metrics)


def compute_manifest_hashes(fixtures: dict[str, dict],
                            event_logs: dict[str, list],
                            run_id: str) -> dict:
    """Placeholder hash computation for the run_manifest skeleton.

    config_hash / event_log_hash: SHA-256 of the deterministic concatenation
    (sorted by fixture id, JSON with sort_keys) of all fixture configs /
    event logs.  scripted_fixture_hash / parameters_hash / spec_hash: SHA-256
    of the frozen files themselves.  code_snapshots: per-file SHA-256.
    """
    config_blob = "".join(
        json.dumps(fixtures[fid]["config"], sort_keys=True, ensure_ascii=False)
        for fid in FIXTURES_ORDER)
    log_blob = "".join(
        json.dumps(event_logs[fid], sort_keys=True, ensure_ascii=False)
        for fid in FIXTURES_ORDER)
    return {
        "run_id": run_id,
        "scenario_ids": {fid: fixtures[fid]["config"]["scenario_id"] for fid in FIXTURES_ORDER},
        "config_hash": sha256_bytes(config_blob.encode("utf-8")),
        "event_log_hash": sha256_bytes(log_blob.encode("utf-8")),
        "scripted_fixture_hash": sha256_file(FIXTURES_PATH),
        "parameters_hash": sha256_file(PARAMETERS_PATH),
        "spec_hash": sha256_file(SPEC_PATH),
        "task_package_ref": "G2-03-SPEC-V1.0.2",
        "registry_version": "CR-V3.1",
        "code_snapshots": [
            {"path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
             "sha256": sha256_file(path)}
            for path in CODE_SNAPSHOT_PATHS
        ],
        "raw_output_refs": {
            "fixtures": str(FIXTURES_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "parameters": str(PARAMETERS_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "event_logs": "generated in-memory per fixture (not persisted by this skeleton)",
            "check_reports": "generated in-memory per fixture (not persisted by this skeleton)",
        },
    }


def run_verification() -> dict:
    """Execute the full chain and return the skeleton result (no 05_结果 write)."""
    fixtures = load_fixtures()
    event_logs: dict[str, list] = {}
    metrics_map: dict[str, dict] = {}
    reports: dict[str, dict] = {}
    issues_map: dict[str, list] = {}
    for fid in FIXTURES_ORDER:
        result = run_des_fixture(fixtures[fid])
        event_logs[fid] = result.event_log
        metrics_map[fid] = result.metrics
        report = run_checker(fixtures[fid], result.event_log, result.metrics)
        reports[fid] = report.to_dict()
        issues_map[fid] = [i.describe() for i in report.issues]
    run_id = new_run_id()
    manifest = compute_manifest_hashes(fixtures, event_logs, run_id)
    passed = [fid for fid in FIXTURES_ORDER if reports[fid]["verdict"] == "PASS"]
    exit_code = 0 if len(passed) == len(FIXTURES_ORDER) else 1
    return {
        "run_id": run_id,
        "fixture_results": {fid: reports[fid]["verdict"] for fid in FIXTURES_ORDER},
        "T_h": {fid: metrics_map[fid]["T"] for fid in FIXTURES_ORDER},
        "passed_count": len(passed),
        "total_count": len(FIXTURES_ORDER),
        "exit_code": exit_code,
        "manifest_skeleton": manifest,
        "check_issues": {fid: issues_map[fid] for fid in FIXTURES_ORDER if issues_map[fid]},
    }


def format_report(result: dict) -> str:
    lines = [
        "=== G2-04 one-command verification skeleton (CR-V3.1/C21) ===",
        "run_id: %s" % result["run_id"],
        "%-6s %-8s %-6s" % ("fixture", "T(h)", "verdict"),
    ]
    for fid in FIXTURES_ORDER:
        lines.append("%-6s %-8s %-6s" % (fid, result["T_h"][fid], result["fixture_results"][fid]))
    lines.append("PASS %d/%d" % (result["passed_count"], result["total_count"]))
    lines.append("exit code: %d" % result["exit_code"])
    lines.append("manifest skeleton: %s" % json.dumps(
        result["manifest_skeleton"], ensure_ascii=False, indent=2, sort_keys=True))
    if result["check_issues"]:
        lines.append("checker issues (should be empty):")
        for fid, issues in result["check_issues"].items():
            for issue in issues:
                lines.append("  %s: %s" % (fid, issue))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI options in the skeleton
    result = run_verification()
    print(format_report(result))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
