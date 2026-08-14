# -*- coding: utf-8 -*-
"""Whole G2 formal candidate evidence runner (CR-V3.1/C21, AUTOPILOT Pilot #1).

Role
----
Mechanical orchestration ONLY (Coordinator-written, L0/L1; no LLM child).
Runs the full G2 acceptance chain and lands an IMMUTABLE evidence package:

  1. accepted main DES (04_代码/main_model/des/deterministic_des_v1.py) on all
     14 concrete fixtures (F1..F12 + F4b/F9b) -> event_log + metrics;
  2. independent checker (04_代码/checker/des_checker_v1.py) on every event_log
     (checker never imports the main engine);
  3. three-way crosscheck (04_代码/tests/three_way_crosscheck_v1.py):
     DES vs independent CP-SAT vs frozen hand;
  4. writes run_manifest.json / commands.json / file_hashes.sha256 plus
     frozen inputs, event_logs, check_reports, metrics and crosscheck report
     into 05_结果/G2/run_<immutable_run_id>/ .

Evidence policy
---------------
* 05_结果/G2/run_*  is byte-preserved by .gitattributes (-text -eol).
* Failed formal runs must be preserved; run_id collisions FAIL (no overwrite).
* file_hashes.sha256: lowercase SHA-256, two spaces, POSIX relative paths,
  sorted by path Unicode code-point, LF, excludes itself, no directories.
* Python 3.12, standard library only. run_id = UTC YYYYMMDDTHHMMSSffffffZ_+8hex.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "04_代码"
RESULT_ROOT = PROJECT_ROOT / "05_结果" / "G2"
FIXTURES_PATH = CODE_DIR / "tests/fixtures/des_fixtures_F1_F12_v1.json"
PARAMETERS_PATH = PROJECT_ROOT / "02_数据/parameters.csv"
SPEC_PATH = PROJECT_ROOT / "08_项目管理/任务包/G2-03_无随机最小并行DES.yaml"
CHECKER_PATH = CODE_DIR / "checker/des_checker_v1.py"
MAIN_DES_PATH = CODE_DIR / "main_model/des/deterministic_des_v1.py"
STATE_MODELS_PATH = CODE_DIR / "main_model/des/state_models_v1.py"
CROSSCHECK_PATH = CODE_DIR / "tests/three_way_crosscheck_v1.py"
CP_SAT_PATH = CODE_DIR / "tests/cp_sat_oracle_v1.py"
SCHEMA_DIR = CODE_DIR / "src/schemas"

FIXTURES_ORDER = [
    "F1", "F2", "F3", "F4", "F4b", "F5", "F6", "F7", "F8", "F9", "F9b",
    "F10", "F11", "F12",
]

CODE_SNAPSHOT_PATHS = [
    MAIN_DES_PATH, STATE_MODELS_PATH, CHECKER_PATH, CP_SAT_PATH,
    CROSSCHECK_PATH, Path(__file__),
]
SCHEMA_PATHS = [
    SCHEMA_DIR / "des_config_v1.schema.json",
    SCHEMA_DIR / "des_event_log_v1.schema.json",
    SCHEMA_DIR / "des_run_manifest_v1.schema.json",
]


def new_run_id(now_utc: datetime.datetime | None = None) -> str:
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
    _join_imports()
    from des import deterministic_des_v1 as de
    return de.run_des(fixture["config"], fixture)


def run_checker(fixture: dict, event_log: list, metrics: dict):
    _join_imports()
    from checker import des_checker_v1 as chk
    return chk.check_event_log(event_log, fixture["config"], fixture,
                               parameters=str(PARAMETERS_PATH), metrics=metrics)


def run_crosscheck_fixture(fixture: dict, des_result):
    _join_imports()
    from tests import three_way_crosscheck_v1 as xc
    oracle_result = xc.run_oracle_fixture(fixture)
    report = xc.crosscheck_fixture(fixture, des_result, oracle_result)
    return xc.report_to_dict(report)


def write_json(path: Path, obj: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def write_file_hashes(run_dir: Path) -> None:
    """file_hashes.sha256: lowercase SHA-256, 2 spaces, POSIX path, code-point
    sorted, LF, excludes itself, files only (relative to run_dir)."""
    lines: list[str] = []
    for p in sorted(run_dir.rglob("*"), key=lambda x: str(x.relative_to(run_dir))):
        if p.is_file() and p.name != "file_hashes.sha256":
            rel = p.relative_to(run_dir).as_posix()
            lines.append(f"{sha256_file(p)}  {rel}")
    (run_dir / "file_hashes.sha256").write_text("\n".join(lines) + "\n",
                                                encoding="utf-8", newline="\n")


def main() -> int:
    fixtures = load_fixtures()
    run_id = new_run_id()
    run_dir = RESULT_ROOT / ("run_" + run_id)
    if run_dir.exists():
        raise SystemExit(f"RUN_ID_COLLISION {run_dir}")

    event_logs: dict[str, list] = {}
    metrics_map: dict[str, dict] = {}
    reports: dict[str, dict] = {}
    crosscheck_map: dict[str, dict] = {}
    issues_map: dict[str, list] = {}

    for fid in FIXTURES_ORDER:
        result = run_des_fixture(fixtures[fid])
        event_logs[fid] = result.event_log
        metrics_map[fid] = result.metrics
        report = run_checker(fixtures[fid], result.event_log, result.metrics)
        reports[fid] = report.to_dict()
        issues_map[fid] = [i.describe() for i in report.issues]
        crosscheck_map[fid] = run_crosscheck_fixture(fixtures[fid], result)

    passed = [fid for fid in FIXTURES_ORDER if reports[fid]["verdict"] == "PASS"]
    cross_passed = [fid for fid in FIXTURES_ORDER
                    if crosscheck_map[fid].get("verdict") == "PASS"]
    all_pass = (len(passed) == len(FIXTURES_ORDER)
                and len(cross_passed) == len(FIXTURES_ORDER))
    exit_code = 0 if all_pass else 1

    # ---- land evidence package ----
    frozen_dir = run_dir / "frozen"
    frozen_dir.mkdir(parents=True, exist_ok=True)
    (frozen_dir / "task_package_G2_03.yaml").write_bytes(SPEC_PATH.read_bytes())
    (frozen_dir / "parameters.csv").write_bytes(PARAMETERS_PATH.read_bytes())
    (frozen_dir / "fixtures_des_F1_F12_v1.json").write_bytes(FIXTURES_PATH.read_bytes())
    for sp in SCHEMA_PATHS:
        (frozen_dir / sp.name).write_bytes(sp.read_bytes())

    ev_dir = run_dir / "event_logs"
    for fid in FIXTURES_ORDER:
        write_json(ev_dir / f"{fid}.json", event_logs[fid])

    rep_dir = run_dir / "check_reports"
    for fid in FIXTURES_ORDER:
        write_json(rep_dir / f"{fid}.json", reports[fid])

    write_json(run_dir / "metrics.json", metrics_map)
    write_json(run_dir / "crosscheck_report.json", crosscheck_map)

    config_blob = "".join(json.dumps(fixtures[fid]["config"], sort_keys=True, ensure_ascii=False)
                          for fid in FIXTURES_ORDER)
    log_blob = "".join(json.dumps(event_logs[fid], sort_keys=True, ensure_ascii=False)
                       for fid in FIXTURES_ORDER)

    manifest = {
        "run_id": run_id,
        "registry_version": "CR-V3.1",
        "task_package_ref": "G2-03-SPEC-V1.0.2",
        "scenario_ids": {fid: fixtures[fid]["config"]["scenario_id"] for fid in FIXTURES_ORDER},
        "config_hash": sha256_bytes(config_blob.encode("utf-8")),
        "event_log_hash": sha256_bytes(log_blob.encode("utf-8")),
        "scripted_fixture_hash": sha256_file(FIXTURES_PATH),
        "parameters_hash": sha256_file(PARAMETERS_PATH),
        "spec_hash": sha256_file(SPEC_PATH),
        "code_snapshots": [
            {"path": p.relative_to(PROJECT_ROOT).as_posix(), "sha256": sha256_file(p)}
            for p in CODE_SNAPSHOT_PATHS
        ],
        "schema_snapshots": [
            {"path": p.relative_to(PROJECT_ROOT).as_posix(), "sha256": sha256_file(p)}
            for p in SCHEMA_PATHS
        ],
        "fixture_results": {fid: reports[fid]["verdict"] for fid in FIXTURES_ORDER},
        "crosscheck_results": {fid: crosscheck_map[fid].get("verdict") for fid in FIXTURES_ORDER},
        "T_h": {fid: str(metrics_map[fid]["T"]) for fid in FIXTURES_ORDER},
        "passed_count": len(passed),
        "crosscheck_passed_count": len(cross_passed),
        "total_count": len(FIXTURES_ORDER),
        "exit_code": exit_code,
        "checker_issues": {fid: issues_map[fid] for fid in FIXTURES_ORDER if issues_map[fid]},
        "evidence_root": str(run_dir.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }
    write_json(run_dir / "run_manifest.json", manifest)

    commands = {
        "run_id": run_id,
        "des": "python -m des.deterministic_des_v1 (via runner)",
        "checker": "python 04_代码/checker/des_checker_v1.py --event-log <log> --config <cfg> --fixture <fid>",
        "crosscheck": "python -m tests.three_way_crosscheck_v1 (crosscheck_all)",
        "runner": "python 04_代码/scripts/run_g2_whole_v1.py",
        "unittest": "python -m unittest discover -s 04_代码/tests -p 'test_*.py'",
    }
    write_json(run_dir / "commands.json", commands)
    write_file_hashes(run_dir)

    # ---- console summary ----
    print("=== Whole G2 formal candidate evidence ===")
    print("run_id: %s" % run_id)
    print("evidence_root: %s" % run_dir)
    print("%-6s %-8s %-10s %-10s" % ("fixture", "T(h)", "checker", "crosscheck"))
    for fid in FIXTURES_ORDER:
        print("%-6s %-8s %-10s %-10s" % (
            fid, str(metrics_map[fid]["T"]), reports[fid]["verdict"],
            crosscheck_map[fid].get("verdict")))
    print("checker PASS %d/%d" % (len(passed), len(FIXTURES_ORDER)))
    print("crosscheck PASS %d/%d" % (len(cross_passed), len(FIXTURES_ORDER)))
    print("exit code: %d" % exit_code)
    print("manifest: %s" % str(run_dir / "run_manifest.json"))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
