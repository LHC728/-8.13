import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


PROJECT = Path(__file__).resolve().parents[2]
RUNNER_PATH = PROJECT / "04_代码/scripts/run_g2_01_v1.py"
PARAMETERS = PROJECT / "02_数据/parameters.csv"
TASK_PACKAGE = PROJECT / "08_项目管理/任务包/G2-01_观测核标定最小基线.yaml"
SCHEMA_PATH = PROJECT / "04_代码/src/schemas/observation_calibration_v1.schema.json"
FIXTURE_PATH = PROJECT / "04_代码/tests/fixtures/observation_calibration_oracles_v1.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

SPEC = importlib.util.spec_from_file_location("run_g2_01_v1_under_test", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RunnerTests(unittest.TestCase):
    def assert_schema(self, instance, definition_name):
        self._assert_schema_node(instance, SCHEMA["$defs"][definition_name])

    def _assert_schema_node(self, instance, node):
        if "oneOf" in node:
            matches = 0
            for candidate in node["oneOf"]:
                try:
                    self._assert_schema_node(instance, candidate)
                    matches += 1
                except self.failureException:
                    pass
            self.assertEqual(matches, 1)
            return
        if "$ref" in node:
            self._assert_schema_node(instance, SCHEMA["$defs"][node["$ref"].split("/")[-1]])
            return
        if "required" in node:
            self.assertIsInstance(instance, dict)
            self.assertTrue(set(node["required"]).issubset(instance))
        if "const" in node:
            self.assertEqual(instance, node["const"])
        if "enum" in node:
            self.assertIn(instance, node["enum"])
        kind = node.get("type")
        if kind == "object" or (kind is None and "properties" in node):
            self.assertIsInstance(instance, dict)
            required = set(node.get("required", []))
            self.assertTrue(required.issubset(instance))
            if node.get("additionalProperties") is False:
                self.assertTrue(set(instance).issubset(node.get("properties", {})))
            for key, value in instance.items():
                if key in node.get("properties", {}):
                    self._assert_schema_node(value, node["properties"][key])
        elif kind == "array" or (
            kind is None
            and any(keyword in node for keyword in ("items", "minItems", "maxItems", "uniqueItems", "contains"))
        ):
            self.assertIsInstance(instance, list)
            self.assertGreaterEqual(len(instance), node.get("minItems", 0))
            if "maxItems" in node:
                self.assertLessEqual(len(instance), node["maxItems"])
            if node.get("uniqueItems"):
                normalized = [json.dumps(value, sort_keys=True) for value in instance]
                self.assertEqual(len(normalized), len(set(normalized)))
            if "items" in node:
                for value in instance:
                    self._assert_schema_node(value, node["items"])
            if "contains" in node:
                matches = 0
                for value in instance:
                    try:
                        self._assert_schema_node(value, node["contains"])
                        matches += 1
                    except self.failureException:
                        pass
                self.assertGreaterEqual(matches, node.get("minContains", 1))
        elif kind == "string":
            self.assertIsInstance(instance, str)
            self.assertGreaterEqual(len(instance), node.get("minLength", 0))
            if "pattern" in node:
                self.assertIsNotNone(re.fullmatch(node["pattern"], instance))
            if node.get("format") == "date-time":
                datetime.fromisoformat(instance.replace("Z", "+00:00"))
        elif kind == "integer":
            self.assertIsInstance(instance, int)
            self.assertGreaterEqual(instance, node.get("minimum", instance))
            self.assertLessEqual(instance, node.get("maximum", instance))
        elif kind == "null":
            self.assertIsNone(instance)
        elif isinstance(kind, list):
            allowed = {
                "string": isinstance(instance, str),
                "null": instance is None,
                "integer": isinstance(instance, int),
                "array": isinstance(instance, list),
                "object": isinstance(instance, dict),
            }
            self.assertTrue(any(allowed.get(candidate, False) for candidate in kind))
        for rule in node.get("allOf", []):
            condition = rule.get("if", {})
            required = set(condition.get("required", []))
            properties = condition.get("properties", {})
            matches = isinstance(instance, dict) and required.issubset(instance)
            if matches:
                for key, constraint in properties.items():
                    if key in instance and "enum" in constraint and instance[key] not in constraint["enum"]:
                        matches = False
                    if key in instance and "const" in constraint and instance[key] != constraint["const"]:
                        matches = False
                    if key in instance and "contains" in constraint:
                        contained = constraint["contains"]
                        if not isinstance(instance[key], list):
                            matches = False
                        elif "const" in contained and contained["const"] not in instance[key]:
                            matches = False
            branch = rule.get("then") if matches else rule.get("else")
            if branch is not None:
                self._assert_schema_node(instance, branch)

    def make_config(self, output_root, parameters=PARAMETERS):
        return RUNNER.RunConfig(
            parameters=Path(parameters).resolve(),
            task_package=TASK_PACKAGE.resolve(),
            schema=SCHEMA_PATH.resolve(),
            fixture=FIXTURE_PATH.resolve(),
            output_root=Path(output_root).resolve(),
        )

    def invoke_relative_exact_cli(self, output_root):
        relative_output = os.path.relpath(output_root, PROJECT)
        return subprocess.run(
            [
                sys.executable,
                str(RUNNER_PATH.relative_to(PROJECT)),
                "--parameters", str(PARAMETERS.relative_to(PROJECT)),
                "--task-package", str(TASK_PACKAGE.relative_to(PROJECT)),
                "--schema", str(SCHEMA_PATH.relative_to(PROJECT)),
                "--fixture", str(FIXTURE_PATH.relative_to(PROJECT)),
                "--output-root", relative_output,
            ],
            cwd=PROJECT,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_real_cli_relative_paths_produces_complete_pass_evidence(self):
        control = {case["case_id"]: case for case in FIXTURE["evidence_envelope_control_tests"]["cases"]}
        with tempfile.TemporaryDirectory(dir=PROJECT / "04_代码/tests") as temporary:
            output_root = Path(temporary) / "relative-output"
            completed = self.invoke_relative_exact_cli(output_root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dirs = list(output_root.glob("run_*"))
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]
            expected_files = {"run_manifest.json", "commands.json", "file_hashes.sha256"}
            expected_files.update(f"frozen/{name}" for name in RUNNER.FROZEN_HASHES)
            expected_files.update(RUNNER.CODE_ARTIFACT_ROLES)
            for semantics in RUNNER.SEMANTICS:
                expected_files.update({
                    f"{semantics}/request.json", f"{semantics}/response.json", f"{semantics}/check_report.json",
                    f"{semantics}/e1.stdout.txt", f"{semantics}/e1.stderr.txt",
                    f"{semantics}/e2.stdout.txt", f"{semantics}/e2.stderr.txt",
                })
            actual_files = {path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file()}
            self.assertEqual(actual_files, expected_files)

            manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
            commands = json.loads((run_dir / "commands.json").read_text(encoding="utf-8"))
            self.assert_schema(manifest, "runManifestEnvelope")
            self.assert_schema(commands, "commandLogEnvelope")
            pass_control = control["pass_requires_semantic_minimum"]
            self.assertEqual(pass_control["required_semantic_artifact_count_minimum"], 17)
            self.assertEqual(
                pass_control["required_semantic_artifact_composition"],
                "11 base artifacts plus 3 source_code snapshots plus 3 test_code snapshots; stdout/stderr artifacts are additional actual-file records and are not counted in this minimum.",
            )
            self.assertEqual(manifest["overall_status"], pass_control["overall_status"])
            self.assertGreaterEqual(len(manifest["artifacts"]), pass_control["required_semantic_artifact_count_minimum"])
            self.assertGreaterEqual(len(manifest["artifacts"]), 17)
            self.assertEqual(len(commands["commands"]), pass_control["required_command_count_exact"])

            requests = []
            for semantics in RUNNER.SEMANTICS:
                request = json.loads((run_dir / semantics / "request.json").read_text(encoding="utf-8"))
                requests.append(request)
                self.assertEqual([item["process_id"] for item in request["items"]], ["A", "B", "C"])
                self.assertTrue(all(item["canonical_parameter_ref"]["source"] == "02_数据/parameters.csv" for item in request["items"]))
                report = json.loads((run_dir / semantics / "check_report.json").read_text(encoding="utf-8"))
                self.assert_schema(report, "checkReportEnvelope")
                self.assertEqual(report["checker_status"], "PASS")
                self.assertEqual(report["response_sha256"], sha256(run_dir / semantics / "response.json"))
                self.assertEqual(report["parameters_sha256"], RUNNER.FROZEN_HASHES["parameters.csv"])
                self.assertEqual(report["schema_sha256"], RUNNER.FROZEN_HASHES["observation_calibration_v1.schema.json"])
                self.assertEqual(report["task_package_sha256"], RUNNER.FROZEN_HASHES["G2-01_观测核标定最小基线.yaml"])
                self.assertEqual(report["checked_result_count"], 3)
                self.assertEqual([item["process_id"] for item in report["items"]], ["A", "B", "C"])
                for item in report["items"]:
                    self.assertEqual(item["status"], "PASS")
                    self.assertEqual(item["response_result_status"], "UNIQUE_SOLUTION")
                    self.assertEqual(item["response_free_parameters"], [])
                    self.assertEqual(item["independent_result_status"], "UNIQUE_SOLUTION")
                    self.assertEqual(item["independent_free_parameters"], [])
                    self.assertIsNotNone(item["independent_alpha"])
                    self.assertIsNotNone(item["independent_beta"])
                    self.assertIsNotNone(item["independent_certificate"])
                    self.assertIsNotNone(item["independent_residuals"])
                    self.assertIsNotNone(item["max_original_residual"])
                    self.assertIsNotNone(item["existence_diagnostics"])
                    self.assertEqual(
                        set(item["independent_certificate"]),
                        set(FIXTURE["checker_structured_report_control_tests"]["required_unique_certificate_fields"]),
                    )
                    self.assertEqual(len(item["independent_certificate"]), 12)
                    self.assertEqual(
                        set(item["independent_residuals"]),
                        set(SCHEMA["$defs"]["residuals"]["required"]),
                    )
                    self.assertEqual(len(item["independent_residuals"]), 3)
                    self.assertEqual(
                        set(item["existence_diagnostics"]),
                        set(SCHEMA["$defs"]["existenceDiagnostics"]["required"]),
                    )
                    self.assertEqual(len(item["existence_diagnostics"]), 8)
                    self.assertIsNotNone(item["existence_diagnostics"]["root_internal_max_residual"])
            self.assertEqual([request["semantics"] for request in requests], list(RUNNER.SEMANTICS))

            expected_argv = RUNNER._expected_commands(run_dir)
            for index, record in enumerate(commands["commands"]):
                self.assertEqual(record["argv"], expected_argv[index])
                self.assertEqual(record["cwd"], ".")
                self.assertTrue(Path(record["argv"][0]).is_file())
                self.assertTrue(Path(record["argv"][1]).is_file())
                for argument_index in range(3, len(record["argv"]), 2):
                    argument_path = Path(record["argv"][argument_index])
                    self.assertTrue(argument_path.is_absolute())
                    self.assertTrue(argument_path.exists() or argument_path.parent.is_dir())

            artifacts = manifest["artifacts"]
            artifact_paths = [record["path"] for record in artifacts]
            self.assertEqual(len(artifact_paths), len(set(artifact_paths)))
            self.assertTrue(set(RUNNER.CORE_ARTIFACT_ROLES).issubset(artifact_paths))
            self.assertTrue(set(RUNNER.LOG_ARTIFACT_ROLES).issubset(artifact_paths))
            self.assertTrue(set(RUNNER.CODE_ARTIFACT_ROLES).issubset(artifact_paths))
            for record in artifacts:
                path = run_dir / record["path"]
                self.assertEqual(record["sha256"], sha256(path))
                self.assertEqual(record["bytes"], path.stat().st_size)
                if record["role"] in {"source_code", "test_code"}:
                    source_relative = record["path"].removeprefix("frozen/code/")
                    source_path = PROJECT / source_relative
                    self.assertEqual(record["role"], RUNNER.CODE_ROLES[source_relative])
                    self.assertEqual(record["source_sha256_before"], record["sha256"])
                    self.assertEqual(record["source_sha256_after"], record["sha256"])
                    self.assertEqual(record["sha256"], sha256(source_path))

            inventory_lines = (run_dir / "file_hashes.sha256").read_text(encoding="utf-8").splitlines()
            inventory_paths = [line.split("  ", 1)[1] for line in inventory_lines]
            self.assertEqual(inventory_paths, sorted(inventory_paths))
            self.assertNotIn("file_hashes.sha256", inventory_paths)
            self.assertEqual(set(inventory_paths), actual_files - {"file_hashes.sha256"})
            for line in inventory_lines:
                digest, relative = line.split("  ", 1)
                self.assertEqual(digest, sha256(run_dir / relative))

            for record in commands["commands"]:
                executed = Path(record["argv"][1])
                self.assertTrue(executed.is_relative_to(run_dir / "frozen/code"))
                self.assertNotIn(executed, {RUNNER.CODE_SOURCES[relative] for relative in RUNNER.CODE_ROLES})

    def test_bad_hash_produces_schema_valid_zero_command_incomplete(self):
        control = next(case for case in FIXTURE["evidence_envelope_control_tests"]["cases"] if case["case_id"] == "early_failure_zero_commands_schema_valid")
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            altered = temporary / "parameters.csv"
            altered.write_bytes(PARAMETERS.read_bytes() + b"\n")
            result, run_dir = RUNNER._run(self.make_config(temporary / "out", altered))
            self.assertEqual(result, 1)
            manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
            commands = json.loads((run_dir / "commands.json").read_text(encoding="utf-8"))
            self.assert_schema(manifest, "runManifestEnvelope")
            self.assert_schema(commands, "commandLogEnvelope")
            self.assertEqual(manifest["overall_status"], control["overall_status"])
            self.assertEqual(len(manifest["artifacts"]), control["artifact_count"])
            self.assertEqual(len(commands["commands"]), control["command_count"])
            self.assertFalse(control["expected_pass_semantics"])

    def test_nonunique_and_misreported_endpoint_check_items_are_schema_valid(self):
        controls = {
            case["case_id"]: case
            for case in FIXTURE["checker_structured_report_control_tests"]["cases"]
        }
        control = controls["endpoint_report_null_certificate_valid"]
        item = {
            "process_id": "endpoint",
            "status": "PASS",
            "response_result_status": control["response_result_status"],
            "response_free_parameters": control["response_free_parameters"],
            "independent_result_status": control["independent_result_status"],
            "independent_free_parameters": control["independent_free_parameters"],
            "independent_alpha": control["independent_alpha"],
            "independent_beta": control["independent_beta"],
            "independent_residuals": control["independent_residuals"],
            "max_original_residual": control["max_original_residual"],
            "independent_certificate": control["independent_certificate"],
            "existence_diagnostics": {
                "method": "endpoint_analysis",
                "alpha_outer_R_lower": None,
                "alpha_outer_R_upper": None,
                "inner_bracket_status": "NOT_APPLICABLE",
                "inner_bracket_count": 0,
                "root_internal_max_residual": None,
                "response_certificate_status": "NOT_APPLICABLE",
                "root_relation": "NOT_APPLICABLE",
            },
            "message": "endpoint nonidentifiable family independently confirmed",
        }
        self.assertTrue(control["expected_schema_valid"])
        self.assert_schema(item, "checkItem")

        mismatch = controls["response_unique_independent_nonidentifiable_schema_valid_fail"]
        mismatched_item = {
            "process_id": "misreported-endpoint",
            "status": mismatch["expected_item_status"],
            "response_result_status": mismatch["response_result_status"],
            "response_free_parameters": mismatch["response_free_parameters"],
            "independent_result_status": mismatch["independent_result_status"],
            "independent_free_parameters": mismatch["independent_free_parameters"],
            "independent_alpha": mismatch["independent_alpha"],
            "independent_beta": mismatch["independent_beta"],
            "independent_residuals": mismatch["independent_residuals"],
            "max_original_residual": mismatch["max_original_residual"],
            "independent_certificate": mismatch["independent_certificate"],
            "existence_diagnostics": mismatch["existence_diagnostics"],
            "message": "response classification disagrees with independent endpoint analysis",
        }
        self.assertEqual(mismatch["expected_checker_status"], "FAIL")
        self.assertNotEqual(
            mismatched_item["response_result_status"],
            mismatched_item["independent_result_status"],
        )
        self.assertEqual(mismatched_item["status"], "FAIL")
        self.assertTrue(mismatch["expected_schema_valid"])
        self.assert_schema(mismatched_item, "checkItem")

    def test_real_preflight_failure_has_logs_and_no_fabricated_report(self):
        control = next(case for case in FIXTURE["evidence_envelope_control_tests"]["cases"] if case["case_id"] == "preflight_failure_logs_without_report")
        original = RUNNER._canonical_request

        def malformed_request(run_id, semantics):
            request = original(run_id, semantics)
            request["request_id"] = "malformed:" + semantics
            return request

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(RUNNER, "_canonical_request", malformed_request):
            result, run_dir = RUNNER._run(self.make_config(Path(temporary) / "out"))
            self.assertEqual(result, 1)
            manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
            commands = json.loads((run_dir / "commands.json").read_text(encoding="utf-8"))
            self.assert_schema(manifest, "runManifestEnvelope")
            self.assert_schema(commands, "commandLogEnvelope")
            self.assertEqual(manifest["overall_status"], control["overall_status"])
            roles = {record["role"] for record in manifest["artifacts"]}
            self.assertTrue(set(control["required_actual_roles"]).issubset(roles))
            self.assertTrue(set(control["forbidden_fabricated_roles"]).isdisjoint(roles))
            self.assertFalse((run_dir / RUNNER.SEMANTICS[0] / "check_report.json").exists())
            self.assertIn("REPORT_CONTEXT_PREFLIGHT_FAILED", manifest["notes"][0])
            self.assertEqual(commands["commands"][-1]["exit_code"], 2)
            stderr_path = run_dir / commands["commands"][-1]["stderr_path"]
            self.assertIn("report-context preflight failed", stderr_path.read_text(encoding="utf-8"))

    def test_source_change_during_snapshot_blocks_all_subprocesses(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            fake_sources = {}
            for index, relative in enumerate(RUNNER.CODE_ROLES):
                source = temporary / "sources" / relative
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(f"source-{index}\n", encoding="utf-8")
                fake_sources[relative] = source
            real_copyfile = RUNNER.shutil.copyfile
            changed_relative = next(iter(RUNNER.CODE_ROLES))

            def copy_and_change(source, destination):
                result = real_copyfile(source, destination)
                if Path(source) == fake_sources[changed_relative]:
                    Path(source).write_text("changed-in-copy-window\n", encoding="utf-8")
                return result

            with mock.patch.dict(RUNNER.CODE_SOURCES, fake_sources, clear=True), mock.patch.object(RUNNER.shutil, "copyfile", side_effect=copy_and_change):
                result, run_dir = RUNNER._run(self.make_config(temporary / "out"))
            self.assertEqual(result, 1)
            commands = json.loads((run_dir / "commands.json").read_text(encoding="utf-8"))
            manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(commands["commands"], [])
            self.assertEqual(manifest["overall_status"], "INCOMPLETE")
            self.assertTrue(any(note.startswith("RUNNER_FAILURE:source changed during snapshot copy:") for note in manifest["notes"]))
            snapshot_path = f"frozen/code/{changed_relative}"
            evidence = next(record for record in manifest["artifacts"] if record["path"] == snapshot_path)
            self.assertNotEqual(evidence["source_sha256_before"], evidence["source_sha256_after"])
            self.assertEqual(evidence["source_sha256_before"], evidence["sha256"])

    def test_formal_cli_rejects_all_override_options(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = [
                sys.executable, str(RUNNER_PATH),
                "--parameters", str(PARAMETERS), "--task-package", str(TASK_PACKAGE),
                "--schema", str(SCHEMA_PATH), "--fixture", str(FIXTURE_PATH),
                "--output-root", str(Path(temporary) / "out"),
            ]
            for option in ("--run-id", "--e1", "--e2", "--python"):
                with self.subTest(option=option):
                    completed = subprocess.run(base + [option, "malicious"], cwd=PROJECT, shell=False, capture_output=True)
                    self.assertEqual(completed.returncode, 2)
            self.assertFalse((Path(temporary) / "out").exists())

    def test_duplicate_internal_run_id_does_not_overwrite(self):
        fixed_run_id = "20260813T123456123456Z_deadbeef"
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            altered = temporary / "parameters.csv"
            altered.write_bytes(PARAMETERS.read_bytes() + b"\n")
            config = self.make_config(temporary / "out", altered)
            with mock.patch.object(RUNNER, "_new_run_id", return_value=fixed_run_id):
                first_result, run_dir = RUNNER._run(config)
                before = {path.relative_to(run_dir): path.read_bytes() for path in run_dir.rglob("*") if path.is_file()}
                second_result, second_dir = RUNNER._run(config)
            self.assertEqual(first_result, 1)
            self.assertEqual(second_result, 2)
            self.assertEqual(run_dir, second_dir)
            self.assertEqual(before, {path.relative_to(run_dir): path.read_bytes() for path in run_dir.rglob("*") if path.is_file()})


if __name__ == "__main__":
    unittest.main()
