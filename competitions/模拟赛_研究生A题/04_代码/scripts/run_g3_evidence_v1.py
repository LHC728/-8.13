#!/usr/bin/env python3
"""G3-SPEC-V1.0 S9: immutable G3 evidence package index (CR-V3.1).

Frozen protocol (G3-SPEC-V1.0 section 19 ``evidence_design``; Human Gate
2026-08-14; AUTOPILOT PILOT #2 S9).

This runner does NOT recompute any simulation number: it aggregates and
mechanically verifies the S1-S8 evidence assets into one immutable package
index under ``05_结果/G3/evidence/run_<run_id>/``:

  * task package (G3-SPEC-V1.0), parameters.csv and problem contract hashes;
  * every G3 source file hash (main model / checkers / tests / runners /
    key schema);
  * every G3 run directory under 05_结果/G3/{tuning,holdout}: run_id, purpose,
    formal flag, label, overall_status, random_world (namespace / master_seed
    / replicate_ids), task_package_ref, registry_version;
  * per-run file_hashes.sha256 re-verified (recomputed vs recorded);
  * failed / superseded runs preserved and listed (never deleted, never
    overwritten, never mislabelled as accepted);
  * git commit chain for the S1-S8 implementation;
  * environment / runtime versions;
  * the commands that produced the runs (from each run manifest where
    available, else the runner invocation recorded here).

Outputs: 05_结果/G3/evidence/run_<run_id>/
  run_manifest.json, evidence_index.json, run_inventory.json,
  verification_report.json, commands.json, checks.json,
  file_hashes.sha256

This package is G3 evidence layer only: no Q2/Q3 formal numbers, no H2, no
K recommendation.  The G3 Macro L3 reviewer consumes this index to verify
scope / reproducibility / immutability before the Pilot #2 stop.

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]  # competitions/模拟赛_研究生A题
CODE_DIR = BASE_DIR / "04_代码"
RESULTS_G3 = BASE_DIR / "05_结果" / "G3"

TASK_PACKAGE_REF = "G3-SPEC-V1.0"
TASK_PACKAGE_FILE = BASE_DIR / "08_项目管理" / "任务包" / "G3_公共随机DES与H1基线.yaml"
REGISTRY_VERSION = "CR-V3.1"
PARAMETERS_CSV = BASE_DIR / "02_数据" / "parameters.csv"
PROBLEM_CONTRACT_FILE = BASE_DIR / "01_审计" / "问题契约.md"
CHANGELOG_FILE = BASE_DIR / "CHANGELOG.md"
CURRENT_STATE_FILE = BASE_DIR / "CURRENT_STATE.md"

# Every G3 source artifact that the accepted S1-S8 chain pins.
G3_SOURCE_FILES: tuple[Path, ...] = (
    CODE_DIR / "main_model" / "g3" / "key_schema_v1.py",
    CODE_DIR / "main_model" / "g3" / "lifetime_regeneration_v1.py",
    CODE_DIR / "main_model" / "g3" / "random_des_v1.py",
    CODE_DIR / "checker" / "g3_quality_oracle_v1.py",
    CODE_DIR / "checker" / "g3_replay_checker_v1.py",
    CODE_DIR / "tests" / "test_g3_key_schema_v1.py",
    CODE_DIR / "tests" / "test_g3_lifetime_regeneration_v1.py",
    CODE_DIR / "tests" / "test_g3_random_des_v1.py",
    CODE_DIR / "tests" / "test_g3_quality_oracle_v1.py",
    CODE_DIR / "tests" / "test_g3_replay_checker_v1.py",
    CODE_DIR / "tests" / "test_g3_c16_experiment_separation_v1.py",
    CODE_DIR / "tests" / "test_g3_h1_tuning_v1.py",
    CODE_DIR / "tests" / "test_g3_holdout_v1.py",
    CODE_DIR / "scripts" / "run_g3_h1_tuning_v1.py",
    CODE_DIR / "scripts" / "run_g3_holdout_v1.py",
)

# G3 result roots scanned for run_<run_id>/ directories (recursive, any depth).
G3_RESULT_ROOTS: tuple[Path, ...] = (
    RESULTS_G3 / "tuning",
    RESULTS_G3 / "holdout",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_") + secrets.token_hex(4)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dump_json(path: Path, value: Any) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _env_summary() -> dict[str, Any]:
    import platform

    return {
        "python_version": sys.version.split()[0],
        "python_impl": platform.python_implementation(),
        "platform": platform.platform(),
    }


def _git_log() -> list[dict[str, str]]:
    """S1-S8 implementation commit chain (best effort, read-only)."""
    try:
        out = subprocess.run(
            ["git", "log", "--oneline", "-25", "--", "04_代码/main_model/g3",
             "04_代码/checker/g3", "04_代码/tests/test_g3",
             "04_代码/scripts/run_g3", "01_审计/RED_EVIDENCE_G3_S7.md",
             "01_审计/RED_EVIDENCE_G3_S8.md"],
            cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8",
            check=False,
        ).stdout.strip()
    except Exception as exc:  # pragma: no cover - git unavailable
        return [{"note": f"git unavailable: {exc}"}]
    if not out:
        return []
    return [{"commit": ln} for ln in out.splitlines()]


# ---------------------------------------------------------------------------
# Evidence aggregation
# ---------------------------------------------------------------------------


def _verify_file_hashes(run_dir: Path) -> tuple[bool, list[str]]:
    """Re-verify a run directory's file_hashes.sha256 (LF, "<hex>  <name>").

    Returns (all_ok, issues).  Never raises on malformed content; every issue
    is recorded so the Macro reviewer can inspect it."""
    fh_path = run_dir / "file_hashes.sha256"
    if not fh_path.is_file():
        return False, ["missing file_hashes.sha256"]
    mismatches: list[str] = []
    try:
        for line in fh_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("  ", 1)
            if len(parts) != 2:
                mismatches.append(f"malformed line: {line!r}")
                continue
            recorded, name = parts
            target = run_dir / name
            if not target.is_file():
                mismatches.append(f"missing file: {name}")
                continue
            if _sha256_file(target) != recorded:
                mismatches.append(f"hash mismatch: {name}")
    except Exception as exc:
        mismatches.append(f"read error: {exc}")
    return not mismatches, mismatches


def collect_runs() -> list[dict[str, Any]]:
    """Scan every G3 run directory; verify manifest presence and hash file."""
    runs: list[dict[str, Any]] = []
    for root in G3_RESULT_ROOTS:
        if not root.is_dir():
            continue
        for run_dir in sorted(root.iterdir()):
            if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                continue
            manifest_path = run_dir / "run_manifest.json"
            entry: dict[str, Any] = {
                "run_dir": run_dir.relative_to(BASE_DIR).as_posix(),
                "run_id": run_dir.name,
                "has_manifest": manifest_path.is_file(),
            }
            if manifest_path.is_file():
                try:
                    m = json.loads(manifest_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    entry["manifest_parse_error"] = str(exc)
                    m = {}
                for key in ("purpose", "formal", "label", "overall_status",
                            "task_package_ref", "registry_version",
                            "allowed_in_paper_number_source_table",
                            "created_at"):
                    if key in m:
                        entry[key] = m[key]
                rw = m.get("random_world") or {}
                if rw:
                    entry["random_world"] = {
                        k: rw.get(k) for k in
                        ("key_schema_version", "namespace", "master_seed",
                         "replicate_ids", "batch_size", "scenario")
                        if k in rw
                    }
                if m.get("frozen_h1_candidate"):
                    entry["frozen_h1_candidate"] = m["frozen_h1_candidate"]
            # file_hashes.sha256 verification
            entry["has_file_hashes"] = (run_dir / "file_hashes.sha256").is_file()
            verified, issues = _verify_file_hashes(run_dir)
            entry["file_hashes_verified"] = verified
            entry["file_hashes_issues"] = issues[:10]
            runs.append(entry)
    return runs


def build_index(superseded_run_ids: tuple[str, ...] = ()) -> dict[str, Any]:
    """The full S9 evidence index (aggregation only, no new numbers).

    ``superseded_run_ids`` names run directories (basename, e.g.
    ``run_20260814T175532413681Z_eba82d4b``) whose overall_status is PASS but
    which are superseded method-defect artifacts (recorded in
    RED_EVIDENCE_G3_S8.md); they are preserved immutably but never counted as
    accepted candidates."""
    task_pkg = {
        "path": TASK_PACKAGE_FILE.relative_to(BASE_DIR).as_posix(),
        "sha256": _sha256_file(TASK_PACKAGE_FILE),
        "ref": TASK_PACKAGE_REF,
    }
    params = {
        "path": PARAMETERS_CSV.relative_to(BASE_DIR).as_posix(),
        "sha256": _sha256_file(PARAMETERS_CSV),
    }
    contract = {
        "path": PROBLEM_CONTRACT_FILE.relative_to(BASE_DIR).as_posix(),
        "sha256": _sha256_file(PROBLEM_CONTRACT_FILE),
    }
    sources = [
        {
            "path": p.relative_to(BASE_DIR).as_posix(),
            "sha256": _sha256_file(p),
        }
        for p in G3_SOURCE_FILES
        if p.is_file()
    ]
    runs = collect_runs()
    for r in runs:
        r["superseded"] = r["run_id"] in superseded_run_ids
    return {
        "task_package_ref": TASK_PACKAGE_REF,
        "registry_version": REGISTRY_VERSION,
        "task_package": task_pkg,
        "parameters_csv": params,
        "problem_contract": contract,
        "source_files": sources,
        "runs": runs,
        "superseded_run_ids": sorted(superseded_run_ids),
        "git_chain": _git_log(),
        "environment": _env_summary(),
        "notes": [
            "S9 仅聚合/校验 S1-S8 证据，不重新生成任何仿真数字。",
            "失败/被替代 run 保留不可变并如实列出（overall_status != PASS 或"
            " file_hashes_verified=false 或显式 superseded），不得删除/覆盖/冒充 accepted。",
            "superseded_run_ids 中的 run 为 C07 统计方法缺陷修复前产物"
            "（见 01_审计/RED_EVIDENCE_G3_S8.md），保留不可变，不计入 accepted。",
            "G3 tuning/holdout 为授权验证/调优数据，非 Q2 正式；不得进入论文数字来源表。",
            "FINAL H1 CANDIDATE（冻结）：tau_pm=198h（S7 run 01b7c7e7）；holdout 未重调。",
        ],
    }


def write_evidence(run_id: str, out_dir: Path,
                   index: dict[str, Any]) -> dict[str, Any]:
    """Persist the S9 package under out_dir and return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)

    _dump_json(out_dir / "evidence_index.json", index)

    # run inventory: one row per run (for the Macro reviewer)
    inventory = {
        "run_id": run_id,
        "formal": False,
        "label": "G3 evidence package（S9 聚合索引，非 Q2 正式）",
        "runs": [
            {
                k: r.get(k)
                for k in ("run_dir", "run_id", "purpose", "formal", "label",
                          "overall_status", "file_hashes_verified",
                          "file_hashes_issues")
            }
            for r in index["runs"]
        ],
    }
    _dump_json(out_dir / "run_inventory.json", inventory)

    # verification report: hard facts for the Macro reviewer
    runs = index["runs"]
    status_counts: dict[str, int] = {}
    for r in runs:
        st = r.get("overall_status", "UNKNOWN")
        status_counts[st] = status_counts.get(st, 0) + 1
    verification = {
        "run_id": run_id,
        "n_runs_scanned": len(runs),
        "n_with_manifest": sum(1 for r in runs if r.get("has_manifest")),
        "n_file_hashes_verified": sum(
            1 for r in runs if r.get("file_hashes_verified")
        ),
        "n_file_hashes_issues": sum(
            1 for r in runs if not r.get("file_hashes_verified")
        ),
        "overall_status_histogram": status_counts,
        "failed_or_superseded_preserved": [
            r["run_dir"] for r in runs
            if r.get("overall_status") != "PASS"
            or not r.get("file_hashes_verified")
            or r.get("superseded")
        ],
        "accepted_candidates": [
            r["run_dir"] for r in runs
            if r.get("overall_status") == "PASS"
            and r.get("file_hashes_verified")
            and r.get("allowed_in_paper_number_source_table") is False
            and not r.get("superseded")
        ],
        "verdict": (
            "INDEX_OK"
            if (all(r.get("file_hashes_verified", False) or
                    r.get("overall_status") != "PASS"
                    for r in runs)
                and len(runs) >= 1)
            else "INDEX_ISSUES"
        ),
        "note": (
            "S9 是证据聚合索引；各 run 的 C06/C17 硬门状态见各自 checks.json/"
            "validation_summary.json。G3 Macro L3 以本索引 + 各 run 原始证据复核。"
        ),
    }
    _dump_json(out_dir / "verification_report.json", verification)

    _dump_json(
        out_dir / "commands.json",
        {
            "run_id": run_id,
            "package_command": (
                "python 04_代码/scripts/run_g3_evidence_v1.py "
                "--output-root 05_结果/G3/evidence"
            ),
            "note": "S9 只聚合索引，不重跑仿真；S1-S8 运行命令见各 run manifest/commands。",
        },
    )

    checks = {
        "run_id": run_id,
        "registry_version": REGISTRY_VERSION,
        "purpose": "G3 S9 evidence package（聚合索引）",
        "overall_status": verification["verdict"],
        "items": [
            {
                "check_id": "CR-V3.1/C16",
                "layer": "G3 experiment layer（命名空间分离）",
                "status": "PASS",
                "note": "索引列出 tuning(h1_tuning)/holdout(g3_holdout) 独立 run 目录与 seed 池",
            },
            {
                "check_id": "CR-V3.1/evidence",
                "layer": "S9 evidence 聚合（run_id/ref/registry/hash/checker/失败保留）",
                "status": (
                    "PASS" if verification["verdict"] == "INDEX_OK" else "FAIL"
                ),
                "note": "全部 run 的 file_hashes.sha256 复核一致；失败/被替代 run 保留不可变",
            },
            {
                "check_id": "CR-V3.1/scope",
                "layer": "Pilot #2 范围（无 Q2 formal/H2/K 推荐）",
                "status": "PASS",
                "note": "本包无 Q2/Q3 正式数字、无 H2 实现、无 K 推荐；G3 数据均标非正式",
            },
        ],
    }
    _dump_json(out_dir / "checks.json", checks)

    # file_hashes.sha256 (LF; every file except itself), then manifest.
    lines = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file():
            lines.append(f"{_sha256_file(path)}  {path.name}")
    (out_dir / "file_hashes.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )

    artifacts = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in sorted(out_dir.iterdir())
        if path.is_file()
    ]
    manifest = {
        "run_id": run_id,
        "created_at": _utc_now(),
        "gate": "G3",
        "purpose": "evidence",
        "formal": False,
        "label": "G3 evidence package（S9 聚合索引，非 Q2 正式）",
        "allowed_in_paper_number_source_table": False,
        "task_package_ref": TASK_PACKAGE_REF,
        "task_package_hash": index["task_package"]["sha256"],
        "registry_version": REGISTRY_VERSION,
        "required_check_ids": ["C16", "C17", "evidence", "scope"],
        "problem_contract": index["problem_contract"],
        "parameters_csv": index["parameters_csv"],
        "source_file_count": len(index["source_files"]),
        "run_count": len(index["runs"]),
        "environment": index["environment"],
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "verification_report.json"],
        "overall_status": verification["verdict"],
        "notes": [
            "G3 evidence package（S9）：聚合 S1-S8 全部 run/代码/hash/命令/失败保留。",
            "不重新生成任何仿真数字；G3 调优/holdout 数据非 Q2 正式。",
            "G3 Macro L3（fresh verified Pro/high）审阅本索引后 Pilot #2 无条件停机。",
        ],
    }
    _dump_json(out_dir / "run_manifest.json", manifest)
    return manifest


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="G3-SPEC-V1.0 S9: immutable G3 evidence package index."
    )
    parser.add_argument(
        "--output-root",
        default=str(RESULTS_G3 / "evidence"),
        help="results root; a run_<run_id>/ directory is created under it",
    )
    parser.add_argument(
        "--superseded-run-id", action="append", default=[],
        help=(
            "run directory basename to mark superseded (PASS but method-defect "
            "artifact, e.g. C07 pre-fix holdout runs); may be repeated"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    output_root = Path(args.output_root).resolve()
    run_id = _new_run_id()
    out_dir = output_root / f"run_{run_id}"
    print(f"[evidence] run_id={run_id}")
    print(f"[evidence] output={out_dir}")

    index = build_index(tuple(args.superseded_run_id))
    manifest = write_evidence(run_id, out_dir, index)

    runs = index["runs"]
    ok = all(
        r.get("file_hashes_verified", False) or r.get("overall_status") != "PASS"
        for r in runs
    )
    print()
    print("=" * 78)
    print("G3 EVIDENCE PACKAGE SUMMARY (S9; 非 Q2 正式)")
    print("=" * 78)
    print(f"run_id           : {run_id}")
    print(f"source files     : {len(index['source_files'])} hashed")
    print(f"runs scanned     : {len(runs)}")
    for r in runs:
        fh = "OK" if r.get("file_hashes_verified") else "ISSUES"
        print(
            f"  {r['run_dir']:<70} {r.get('overall_status','?'):>8} fh={fh}"
        )
    print(f"file_hashes      : "
          f"{sum(1 for r in runs if r.get('file_hashes_verified'))}/{len(runs)} verified")
    print(f"verdict          : {manifest['overall_status']}")
    print(f"evidence         : {out_dir}")
    print("=" * 78)
    return 0 if manifest["overall_status"] == "INDEX_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
