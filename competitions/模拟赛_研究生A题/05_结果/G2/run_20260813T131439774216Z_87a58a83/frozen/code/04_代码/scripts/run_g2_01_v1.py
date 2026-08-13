#!/usr/bin/env python3
"""Mechanical evidence runner for frozen G2-01-SPEC-V1.1.10."""

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_PATH = Path(sys.executable).resolve()
TASK_PACKAGE_VERSION = "G2-01-SPEC-V1.1.10"
SEMANTICS = ("single_test_unconditional_v1", "standard_chain_v1")
FROZEN_HASHES = {
    "G2-01_观测核标定最小基线.yaml": "cac6d68980cd4fbc74c7750bd772ad2879cce84018381aec4f750f86304d47b5",
    "parameters.csv": "0461da2e0de09090673192d9eb0fde6fe5e70b1d22ef61fe13cdb878c449f07e",
    "observation_calibration_v1.schema.json": "7fc96c53e924f6e184f4093589402737295dcf4bdd0671b6667e805da55e0c80",
    "observation_calibration_oracles_v1.json": "3f3c30118e1c4444e217c30118aa1ba13b26f78606c2c23b034d624bab7ad2e4",
}
SOURCE_TO_FROZEN = {
    "task_package": "G2-01_观测核标定最小基线.yaml",
    "parameters": "parameters.csv",
    "schema": "observation_calibration_v1.schema.json",
    "fixture": "observation_calibration_oracles_v1.json",
}
CORE_ARTIFACT_ROLES = {
    "frozen/G2-01_观测核标定最小基线.yaml": "task_package",
    "frozen/parameters.csv": "parameters",
    "frozen/observation_calibration_v1.schema.json": "schema",
    "frozen/observation_calibration_oracles_v1.json": "oracle_fixture",
    "single_test_unconditional_v1/request.json": "request",
    "single_test_unconditional_v1/response.json": "response",
    "single_test_unconditional_v1/check_report.json": "check_report",
    "standard_chain_v1/request.json": "request",
    "standard_chain_v1/response.json": "response",
    "standard_chain_v1/check_report.json": "check_report",
    "commands.json": "command_log",
}
LOG_ARTIFACT_ROLES = {
    f"{sem}/{stage}.{stream}.txt": f"{stream}_log"
    for sem in SEMANTICS for stage in ("e1", "e2") for stream in ("stdout", "stderr")
}
CODE_ROLES = {
    "04_代码/main_model/observation_calibration_v1.py": "source_code",
    "04_代码/checker/observation_calibration_checker_v1.py": "source_code",
    "04_代码/scripts/run_g2_01_v1.py": "source_code",
    "04_代码/tests/test_observation_calibration_main_v1.py": "test_code",
    "04_代码/tests/test_observation_calibration_checker_v1.py": "test_code",
    "04_代码/tests/test_run_g2_01_v1.py": "test_code",
}
CODE_SOURCES = {relative: (PROJECT_ROOT / relative).resolve() for relative in CODE_ROLES}
CODE_ARTIFACT_ROLES = {f"frozen/code/{relative}": role for relative, role in CODE_ROLES.items()}
PACKAGE_FILES = set(CORE_ARTIFACT_ROLES) | set(LOG_ARTIFACT_ROLES) | {
    "run_manifest.json", "commands.json", "file_hashes.sha256"
} | set(CODE_ARTIFACT_ROLES)


@dataclass(frozen=True)
class RunConfig:
    parameters: Path
    task_package: Path
    schema: Path
    fixture: Path
    output_root: Path


class SnapshotError(RuntimeError):
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_run_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_") + secrets.token_hex(4)


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dump_json(path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _relative(path, root):
    return Path(path).relative_to(root).as_posix()


def _canonical_request(run_id, semantics):
    """Pure construction function; tests may replace it without exposing CLI hooks."""
    bindings = (("A", "P026", "P030"), ("B", "P027", "P031"), ("C", "P028", "P032"))
    items = [
        {
            "process_id": process_id,
            "canonical_parameter_ref": {
                "source": "02_数据/parameters.csv",
                "q_parameter_id": q_parameter_id,
                "e_parameter_id": e_parameter_id,
            },
        }
        for process_id, q_parameter_id, e_parameter_id in bindings
    ]
    return {
        "schema_version": "observation_calibration_v1",
        "envelope_type": "calibration_request",
        "request_id": f"{run_id}:{semantics}",
        "scenario_role": "canonical_g2_abc",
        "semantics": semantics,
        "items": items,
    }


def _resolved_config(arguments):
    """Resolve every public path before any subprocess changes cwd."""
    return RunConfig(
        parameters=Path(arguments.parameters).resolve(),
        task_package=Path(arguments.task_package).resolve(),
        schema=Path(arguments.schema).resolve(),
        fixture=Path(arguments.fixture).resolve(),
        output_root=Path(arguments.output_root).resolve(),
    )


def _source_paths(config):
    return {
        "task_package": config.task_package,
        "parameters": config.parameters,
        "schema": config.schema,
        "fixture": config.fixture,
    }


def _verify_source_hashes(config):
    for key, source in _source_paths(config).items():
        target_name = SOURCE_TO_FROZEN[key]
        if not source.is_file():
            raise RuntimeError(f"frozen input is not a file: {source}")
        if _sha256(source) != FROZEN_HASHES[target_name]:
            raise RuntimeError(f"frozen SHA-256 mismatch for {target_name}")


def _copy_frozen(config, run_dir):
    frozen_dir = run_dir / "frozen"
    frozen_dir.mkdir()
    for key, source in _source_paths(config).items():
        name = SOURCE_TO_FROZEN[key]
        destination = frozen_dir / name
        shutil.copyfile(source, destination)
        if _sha256(destination) != FROZEN_HASHES[name]:
            raise RuntimeError(f"copied frozen SHA-256 mismatch for {name}")


def _snapshot_code_files(run_dir):
    """Copy the six traceability sources with a source/snapshot/source fence."""
    evidence = {}
    for relative_path in CODE_ROLES:
        source = CODE_SOURCES[relative_path]
        snapshot = run_dir / "frozen" / "code" / relative_path
        source_sha256_before = _sha256(source)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, snapshot)
        snapshot_sha256 = _sha256(snapshot)
        source_sha256_after = _sha256(source)
        artifact_path = _relative(snapshot, run_dir)
        evidence[artifact_path] = {
            "source_sha256_before": source_sha256_before,
            "sha256": snapshot_sha256,
            "source_sha256_after": source_sha256_after,
        }
        if not source_sha256_before == snapshot_sha256 == source_sha256_after:
            raise SnapshotError(f"source changed during snapshot copy: {relative_path}", evidence)
    return evidence


def _execute(command, run_dir, stdout_path, stderr_path, sequence):
    started_utc = _utc_now()
    completed = subprocess.run(command, cwd=str(run_dir), shell=False, capture_output=True)
    finished_utc = _utc_now()
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    return {
        "sequence": sequence,
        "argv": command,
        "cwd": ".",
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "exit_code": completed.returncode,
        "stdout_path": _relative(stdout_path, run_dir),
        "stderr_path": _relative(stderr_path, run_dir),
    }


def _command_log(run_id, commands):
    return {
        "schema_version": "observation_calibration_v1",
        "envelope_type": "calibration_command_log",
        "run_id": run_id,
        "commands": commands,
    }


def _artifact_role(relative_path):
    return (CORE_ARTIFACT_ROLES.get(relative_path) or LOG_ARTIFACT_ROLES.get(relative_path)
            or CODE_ARTIFACT_ROLES.get(relative_path))


def _collect_artifacts(run_dir, code_evidence):
    records = []
    for path in sorted((item for item in run_dir.rglob("*") if item.is_file()), key=lambda item: _relative(item, run_dir)):
        relative_path = _relative(path, run_dir)
        role = _artifact_role(relative_path)
        if role is not None:
            record = {
                "path": relative_path,
                "role": role,
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            if role in {"source_code", "test_code"}:
                hashes = code_evidence.get(relative_path)
                if hashes is None:
                    continue
                record.update({
                    "source_sha256_before": hashes["source_sha256_before"],
                    "source_sha256_after": hashes["source_sha256_after"],
                })
            records.append(record)
    return records


def _manifest(run_id, created_utc, artifacts, overall_status, notes):
    return {
        "schema_version": "observation_calibration_v1",
        "envelope_type": "calibration_run_manifest",
        "run_id": run_id,
        "state_version": "STATE-2026-08-13-G2.2",
        "registry_version": "CR-V3.1",
        "task_package_version": TASK_PACKAGE_VERSION,
        "created_utc": created_utc,
        "runner": "04_代码/scripts/run_g2_01_v1.py",
        "python_version": sys.version,
        "canonical_process_order": ["A", "B", "C"],
        "semantics_run_order": list(SEMANTICS),
        "artifacts": artifacts,
        "overall_status": overall_status,
        "notes": notes,
    }


def _write_inventory(run_dir):
    entries = []
    files = (item for item in run_dir.rglob("*") if item.is_file() and item.name != "file_hashes.sha256")
    for path in sorted(files, key=lambda item: _relative(item, run_dir)):
        entries.append(f"{_sha256(path)}  {_relative(path, run_dir)}")
    (run_dir / "file_hashes.sha256").write_text("\n".join(entries) + "\n", encoding="utf-8")


def _expected_commands(run_dir):
    frozen = run_dir / "frozen"
    frozen_e1 = run_dir / "frozen/code/04_代码/main_model/observation_calibration_v1.py"
    frozen_e2 = run_dir / "frozen/code/04_代码/checker/observation_calibration_checker_v1.py"
    expected = []
    for semantics in SEMANTICS:
        semantic_dir = run_dir / semantics
        expected.append([
            str(PYTHON_PATH), str(frozen_e1.resolve()),
            "--request", str((semantic_dir / "request.json").resolve()),
            "--parameters", str((frozen / "parameters.csv").resolve()),
            "--output", str((semantic_dir / "response.json").resolve()),
        ])
        expected.append([
            str(PYTHON_PATH), str(frozen_e2.resolve()),
            "--response", str((semantic_dir / "response.json").resolve()),
            "--parameters", str((frozen / "parameters.csv").resolve()),
            "--schema", str((frozen / "observation_calibration_v1.schema.json").resolve()),
            "--task-package", str((frozen / "G2-01_观测核标定最小基线.yaml").resolve()),
            "--report", str((semantic_dir / "check_report.json").resolve()),
        ])
    return expected


def _pass_contract_holds(run_dir, commands, artifacts):
    expected_commands = _expected_commands(run_dir)
    if len(commands) != 4 or any(command["sequence"] != index + 1 for index, command in enumerate(commands)):
        return False
    if any(command["argv"] != expected_commands[index] or command["exit_code"] != 0 for index, command in enumerate(commands)):
        return False
    artifact_paths = [record["path"] for record in artifacts]
    if len(artifact_paths) != len(set(artifact_paths)):
        return False
    if not set(CORE_ARTIFACT_ROLES).issubset(artifact_paths) or not set(LOG_ARTIFACT_ROLES).issubset(artifact_paths):
        return False
    if not set(CODE_ARTIFACT_ROLES).issubset(artifact_paths):
        return False
    actual_files = {_relative(path, run_dir) for path in run_dir.rglob("*") if path.is_file()}
    # Manifest and inventory are written after this gate, so the pre-finalize
    # exact set contains every frozen layout file except those two.
    if actual_files != PACKAGE_FILES - {"run_manifest.json", "file_hashes.sha256"}:
        return False
    for record in artifacts:
        path = run_dir / record["path"]
        if (not path.is_file() or record["role"] != _artifact_role(record["path"])
                or record["sha256"] != _sha256(path) or record["bytes"] != path.stat().st_size):
            return False
        if record["role"] in {"source_code", "test_code"}:
            if not (record.get("source_sha256_before") == record["sha256"]
                    == record.get("source_sha256_after")):
                return False
    for name, expected_hash in FROZEN_HASHES.items():
        if _sha256(run_dir / "frozen" / name) != expected_hash:
            return False
    for semantics in SEMANTICS:
        try:
            report = json.loads((run_dir / semantics / "check_report.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if report.get("checker_status") != "PASS":
            return False
        expected_report_fields = {
            "run_id": run_dir.name[4:],
            "scenario_role": "canonical_g2_abc",
            "semantics": semantics,
            "response_sha256": _sha256(run_dir / semantics / "response.json"),
            "parameters_sha256": FROZEN_HASHES["parameters.csv"],
            "schema_sha256": FROZEN_HASHES["observation_calibration_v1.schema.json"],
            "task_package_sha256": FROZEN_HASHES["G2-01_观测核标定最小基线.yaml"],
        }
        if any(report.get(key) != value for key, value in expected_report_fields.items()):
            return False
    return True


def _finalize(run_dir, run_id, created_utc, commands, status, notes, code_evidence, enumerate_artifacts=True):
    _dump_json(run_dir / "commands.json", _command_log(run_id, commands))
    artifacts = _collect_artifacts(run_dir, code_evidence) if enumerate_artifacts else []
    if status == "PASS" and not _pass_contract_holds(run_dir, commands, artifacts):
        status = "FAIL"
        notes.append("PASS_SEMANTIC_CONTRACT_FAILED")
    _dump_json(run_dir / "run_manifest.json", _manifest(run_id, created_utc, artifacts, status, notes))
    _write_inventory(run_dir)
    return 0 if status == "PASS" else 1


def _run(config):
    run_id = _new_run_id()
    created_utc = _utc_now()
    run_dir = config.output_root / f"run_{run_id}"
    if run_dir.exists():
        print("immutable run directory already exists", file=sys.stderr)
        return 2, run_dir
    run_dir.mkdir(parents=True)
    commands = []
    notes = []
    code_evidence = {}
    try:
        _verify_source_hashes(config)
    except (OSError, RuntimeError) as exc:
        notes.append(f"FROZEN_INPUT_PREFLIGHT_FAILED:{exc}")
        result = _finalize(run_dir, run_id, created_utc, commands, "INCOMPLETE", notes, code_evidence, enumerate_artifacts=False)
        print(str(exc), file=sys.stderr)
        return result, run_dir
    try:
        if not PYTHON_PATH.is_file():
            raise RuntimeError("frozen executable path is unavailable")
        _copy_frozen(config, run_dir)
        try:
            code_evidence = _snapshot_code_files(run_dir)
        except SnapshotError as exc:
            code_evidence = exc.evidence
            raise
        for semantics in SEMANTICS:
            semantic_dir = run_dir / semantics
            semantic_dir.mkdir()
            _dump_json(semantic_dir / "request.json", _canonical_request(run_id, semantics))
        expected_commands = _expected_commands(run_dir)
        for index, command in enumerate(expected_commands):
            semantics = SEMANTICS[index // 2]
            stage = "e1" if index % 2 == 0 else "e2"
            semantic_dir = run_dir / semantics
            record = _execute(
                command,
                run_dir,
                semantic_dir / f"{stage}.stdout.txt",
                semantic_dir / f"{stage}.stderr.txt",
                index + 1,
            )
            commands.append(record)
            if record["exit_code"] != 0:
                report_path = semantic_dir / "check_report.json"
                if stage == "e2" and record["exit_code"] == 2 and not report_path.exists():
                    notes.append(f"REPORT_CONTEXT_PREFLIGHT_FAILED:{semantics}")
                return _finalize(run_dir, run_id, created_utc, commands, "FAIL", notes, code_evidence), run_dir
        return _finalize(run_dir, run_id, created_utc, commands, "PASS", notes, code_evidence), run_dir
    except Exception as exc:
        notes.append(f"RUNNER_FAILURE:{exc}")
        result = _finalize(run_dir, run_id, created_utc, commands, "INCOMPLETE", notes, code_evidence)
        print(str(exc), file=sys.stderr)
        return result, run_dir


def _parse_arguments(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--parameters", required=True)
    parser.add_argument("--task-package", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output-root", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    arguments = _parse_arguments(argv)
    result, _ = _run(_resolved_config(arguments))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
