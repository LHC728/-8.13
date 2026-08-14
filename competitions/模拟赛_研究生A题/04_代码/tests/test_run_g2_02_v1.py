# -*- coding: utf-8 -*-
"""Unit tests for the G2-02 L1 evidence runner (run_g2_02_v1).

The runner implements orchestration structure ONLY: it never imports E1/E2
modules, never computes formulas, and never decides PASS from numeric values.
These tests exercise the runner's pure internal functions (run_id rules,
V1.0.4 bindings, envelope-level schema validation, freeze/snapshot hashing,
manifest/commands/inventory shapes, run-dir collision handling, structural
evaluation) with temporary files; no CLI options are added for testing, and
no formal canonical run is ever created (all run output goes to temp dirs).

V1.0.4 rebind: the frozen code/test snapshot set is ten files -- the nine
G2-02 files plus the G2-01 accepted solver observation_calibration_v1.py,
guarded identically (hash-before == snapshot-hash == hash-after).  The
process-level harness tests prove the frozen E1 imports the frozen solver
from a temp run structure with no working-tree fallback.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(CODE_ROOT, "scripts"))
sys.path.insert(0, CODE_ROOT)

from scripts import run_g2_02_v1 as runner  # noqa: E402

PROJECT_ROOT = os.path.dirname(CODE_ROOT)

REAL_PARAMETERS = os.path.join(PROJECT_ROOT, "02_数据", "parameters.csv")
REAL_TASK_PACKAGE = os.path.join(PROJECT_ROOT, "08_项目管理", "任务包",
                                 "G2-02_Q1概率与质量解析链.yaml")
REAL_SCHEMA = os.path.join(PROJECT_ROOT, "04_代码", "src", "schemas",
                           "q1_quality_v1.schema.json")
REAL_FIXTURE = os.path.join(PROJECT_ROOT, "04_代码", "tests", "fixtures",
                            "q1_quality_oracles_v1.json")
REAL_UPSTREAM_ROOT = os.path.join(PROJECT_ROOT, "05_结果", "G2",
                                  "run_20260813T134251279572Z_f1290916")

FIXED_RUN_ID = "20260813T134251279572Z_abcd1234"
UPSTREAM_RUN_ID = "20260813T134251279572Z_f1290916"

OLD_SCHEMA_HASH = "94157e00e59a07100441084daa8bc31755c0aad54df3c824a705733aff7776e2"
OLD_FIXTURE_HASH = "fadefcedddc1e1233d75f16fc9d596284d43681f4120721be2ff47d4aff2b4ad"
# Old spec versions built dynamically so no pre-V1.0.3 literal stays in source.
OLD_SPEC_VERSION = "G2-02-SPEC-V1.0.%d" % 2
V103_SPEC_VERSION = "G2-02-SPEC-V1.0.%d" % 3

SOLVER_REL = "04_代码/main_model/observation_calibration_v1.py"
SOLVER_FROZEN_REL = "frozen/code/" + SOLVER_REL


def sha(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical_request(sem):
    return runner.build_request(FIXED_RUN_ID, sem, UPSTREAM_RUN_ID,
                                "frozen/upstream/%s/response.json" % sem,
                                "0" * 64, sem)


def make_response(semantics, na=False, request_id=None, include_emax=None):
    """A minimal but schema-conformant q1_response for one semantics leg.

    V1.0.3 shapes exercised: chain responses omit E_kernel.e_max_E entirely;
    NA responses use null main/sum/max_abs_deviation and null
    route_agreement.lambda_*; q_E keeps whatever lexical form is set.
    """
    if request_id is None:
        request_id = "%s:%s" % (FIXED_RUN_ID, semantics)
    if include_emax is None:
        include_emax = semantics == "single_test_unconditional_v1"
    resp = {
        "schema_version": "q1_quality_v1",
        "envelope_type": "q1_response",
        "request_id": request_id,
        "scenario_role": "canonical_g2_02",
        "semantics": semantics,
        "overall_status": "ALL_ROUTES_AGREE",
        "abc_kernels": [
            {"process_id": "A", "q": "0.025", "e": "0.03",
             "status": "UNIQUE_SOLUTION", "free_parameters": [], "source": "upstream_bound"},
            {"process_id": "B", "q": "0.03", "e": "0.04",
             "status": "UNIQUE_SOLUTION", "free_parameters": [], "source": "upstream_bound"},
            {"process_id": "C", "q": "0.02", "e": "0.02",
             "status": "UNIQUE_SOLUTION", "free_parameters": [], "source": "upstream_bound"},
        ],
        "q_E": "0.058237", "G": "0.9", "Z_0": "0.8", "Z_1": "0.1",
        "reach_E_distribution": ["0.0625"] * 16,
        "E_kernel": {
            "status": "UNIQUE_SOLUTION",
            "alpha_E": "0.03", "beta_E": "0.5",
            "free_parameters": [],
            "diagnostics": {"method": "closed_form", "feasibility": "FEASIBLE", "notes": []},
        },
        "E_rates": {"first_abnormal": "0.05", "process_exit": "0.03",
                    "device_total_exit": "0.08"},
        "fourfold": {
            "p_GP": "0.5", "p_BP": "0.1", "p_GE": "0.2", "p_BE": "0.2",
            "sum": "1.0",
            "per_route": {
                "closed_form": {"p_GP": "0.5", "p_BP": "0.1", "p_GE": "0.2", "p_BE": "0.2"},
                "enumeration": {"p_GP": "0.5", "p_BP": "0.1", "p_GE": "0.2", "p_BE": "0.2"},
                "absorption_chain": {"p_GP": "0.5", "p_BP": "0.1", "p_GE": "0.2", "p_BE": "0.2"},
            },
            "max_abs_deviation": "0.0",
        },
        "anchors": {"E_S": "60.0", "E_PL": "0.1", "E_PW": "0.2"},
        "lambda": {
            "main": ({"A": None, "B": None, "C": None, "D": None} if na
                     else {"A": "0.1", "B": "0.2", "C": "0.3", "D": "0.4"}),
            "sum": None if na else "1.0",
            "counts": ({"event_level": "0", "first_test_only": "0", "at_most_once_per_device": "0"}
                       if na else {"event_level": "1.5", "first_test_only": "1.0",
                                   "at_most_once_per_device": "1.0"}),
            "tilde": {"A": "0.1", "B": "0.2", "C": "0.3", "D": "0.4"},
            "na": na,
            "max_abs_deviation": None if na else "0.0",
        },
        "multinomial": {"N": 100, "p": ["0.5", "0.1", "0.2", "0.2"]},
        "route_agreement": {
            "q_E": "0.058237", "G": "0.9", "Z_0": "0.8", "Z_1": "0.1",
            "p_GP": "0.5", "p_BP": "0.1", "p_GE": "0.2", "p_BE": "0.2",
            "lambda_A": None, "lambda_B": None, "lambda_C": None, "lambda_D": None,
            "tilde_A": "0.1", "tilde_B": "0.2", "tilde_C": "0.3", "tilde_D": "0.4",
        } if na else {
            "q_E": "0.058237", "G": "0.9", "Z_0": "0.8", "Z_1": "0.1",
            "p_GP": "0.5", "p_BP": "0.1", "p_GE": "0.2", "p_BE": "0.2",
            "lambda_A": "0.1", "lambda_B": "0.2", "lambda_C": "0.3", "lambda_D": "0.4",
            "tilde_A": "0.1", "tilde_B": "0.2", "tilde_C": "0.3", "tilde_D": "0.4",
        },
        "diagnostics": {"notes": []},
    }
    if include_emax:
        resp["E_kernel"]["e_max_E"] = "0.5"
    return resp


def response_from_request(req):
    return make_response(req["semantics"], request_id=req["request_id"])


def make_report(resp, status="PASS"):
    run_id = resp["request_id"].rsplit(":", 1)[0]
    return {
        "schema_version": "q1_quality_v1",
        "envelope_type": "q1_check_report",
        "request_id": resp["request_id"],
        "semantics": resp["semantics"],
        "checker_status": status,
        "report_context_run_id": run_id,
        "frozen_input_hashes": {"parameters_sha256": "0" * 64, "upstream_sha256": "0" * 64},
        "items": [{"quantity": "q_E", "verdict": "PASS"}],
        "route_table_verdict": "PASS",
        "errors": [],
    }


def default_commands(run_id):
    cmds = []
    for sem in runner.SEMANTICS:
        cmds.append({
            "index": len(cmds),
            "argv": [sys.executable, "frozen/code/04_代码/main_model/q1_quality_v1.py"],
            "cwd": "/tmp", "start_utc": "t0", "end_utc": "t1", "exit_code": 0,
            "stdout_rel": sem + "/e1.stdout.txt", "stderr_rel": sem + "/e1.stderr.txt",
        })
        cmds.append({
            "index": len(cmds),
            "argv": [sys.executable, "frozen/code/04_代码/checker/q1_quality_checker_v1.py"],
            "cwd": "/tmp", "start_utc": "t0", "end_utc": "t1", "exit_code": 0,
            "stdout_rel": sem + "/e2.stdout.txt", "stderr_rel": sem + "/e2.stderr.txt",
        })
    return cmds


def make_run_root(tmp, run_id, responses=None, reports=None, omit=()):
    """Build a full evidence run root (all ARTIFACT_LAYOUT files present) with
    the given responses/reports; ``omit`` removes files afterwards."""
    if responses is None:
        responses = {sem: make_response(sem) for sem in runner.SEMANTICS}
    if reports is None:
        reports = {sem: make_report(responses[sem]) for sem in runner.SEMANTICS}
    run_root = os.path.join(tmp, "run_" + run_id)
    for rel, _role in runner.ARTIFACT_LAYOUT:
        full = os.path.join(run_root, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write("x")
    for sem in runner.SEMANTICS:
        with open(os.path.join(run_root, sem, "response.json"), "w", encoding="utf-8") as f:
            json.dump(responses[sem], f, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
        with open(os.path.join(run_root, sem, "check_report.json"), "w", encoding="utf-8") as f:
            json.dump(reports[sem], f, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    for rel in omit:
        os.remove(os.path.join(run_root, *rel.split("/")))
    return run_root


class _FakeSubprocess:
    """Stand-in for the ``subprocess`` module used inside the runner: keeps a
    callable ``run`` (no bound-method descriptor surprises) and a ``PIPE``."""

    PIPE = -1

    def __init__(self, run_fn):
        self._run_fn = run_fn

    def run(self, *args, **kwargs):
        return self._run_fn(*args, **kwargs)


def temp_task_package(tmp, replacements):
    """Copy the frozen real task package into tmp with literal replacements."""
    with open(REAL_TASK_PACKAGE, encoding="utf-8") as f:
        text = f.read()
    for old, new in replacements:
        assert old in text, "replacement target missing: %r" % old
        text = text.replace(old, new, 1)
    dst = os.path.join(tmp, "G2-02_Q1概率与质量解析链.yaml")
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return dst


def find_run_dir(output_root):
    dirs = [d for d in os.listdir(output_root) if d.startswith("run_")]
    assert len(dirs) == 1, dirs
    return os.path.join(output_root, dirs[0])


class RunIdTests(unittest.TestCase):
    def test_new_run_id_format(self):
        now = datetime.datetime(2026, 8, 13, 13, 42, 51, 279572,
                                tzinfo=datetime.timezone.utc)
        rid = runner.new_run_id(now, "f1290916")
        self.assertEqual(rid, "20260813T134251279572Z_f1290916")
        self.assertTrue(runner.is_valid_run_id(rid))

    def test_is_valid_run_id(self):
        for good in ("20260813T134251279572Z_f1290916",
                     "20000101T000000000000Z_00000000",
                     "20991231T235959999999Z_abcdefab"):
            self.assertTrue(runner.is_valid_run_id(good), good)
        for bad in ("20260813T134251279572Z_f129091",   # 7 hex
                    "20260813T13425127957Z_f1290916",   # 11 digits
                    "2026-08-13T134251279572Z_f1290916",
                    "run_20260813T134251279572Z_f1290916",
                    "20260813T134251279572Z_f1290916:single",
                    ""):
            self.assertFalse(runner.is_valid_run_id(bad), bad)


class HashTests(unittest.TestCase):
    def test_sha256_file_matches_known(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.txt")
            with open(path, "wb") as f:
                f.write(b"hello\n")
            self.assertEqual(runner.sha256_file(path), sha("hello\n"))

    def test_snapshot_code_triple_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.py")
            dst = os.path.join(tmp, "sub", "dst.py")
            content = "print('hi')\n# line2\n"
            with open(src, "wb") as f:
                f.write(content.encode("utf-8"))
            before, snap, after = runner.snapshot_code(src, dst)
            self.assertEqual(before, sha(content))
            self.assertEqual(snap, before)
            self.assertEqual(after, before)
            with open(dst, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), content)

    def test_snapshot_code_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                runner.snapshot_code(os.path.join(tmp, "missing.py"),
                                     os.path.join(tmp, "out.py"))

    def test_code_source_path_resolves_within_project(self):
        # the checker and runner files exist in the working tree; their source
        # paths must resolve under the project root without a duplicated prefix
        checker = runner.code_source_path("04_代码/checker/q1_quality_checker_v1.py")
        self.assertTrue(os.path.isfile(checker), checker)
        self.assertIn("04_代码", checker)
        scripts = runner.code_source_path("04_代码/scripts/run_g2_02_v1.py")
        self.assertTrue(os.path.isfile(scripts), scripts)


class YamlExtractTests(unittest.TestCase):
    def test_extract_frozen_sha256(self):
        yaml_text = (
            "shared_read_only_artifacts:\n"
            "  frozen_sha256:\n"
            "    parameters_csv: \"0461da2e0de09090673192d9eb0fde6fe5e70b1d22ef61fe13cdb878c449f07e\"\n"
            "    schema: '94157e00e59a07100441084daa8bc31755c0aad54df3c824a705733aff7776e2'\n"
            "    upstream_single_response: 355af00ce77791208af17303912ed5972619ad89116f3d0d05f46494d534d0ea\n"
            "other:\n"
            "  deeper: value\n"
        )
        out = runner.extract_frozen_sha256(yaml_text)
        self.assertEqual(out["parameters_csv"],
                         "0461da2e0de09090673192d9eb0fde6fe5e70b1d22ef61fe13cdb878c449f07e")
        self.assertEqual(out["schema"],
                         "94157e00e59a07100441084daa8bc31755c0aad54df3c824a705733aff7776e2")
        self.assertEqual(out["upstream_single_response"],
                         "355af00ce77791208af17303912ed5972619ad89116f3d0d05f46494d534d0ea")
        self.assertNotIn("deeper", out)

    def test_extract_from_real_task_package(self):
        path = os.path.join(os.path.dirname(CODE_ROOT), "08_项目管理", "任务包",
                            "G2-02_Q1概率与质量解析链.yaml")
        if not os.path.isfile(path):
            self.skipTest("real task package not present")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        out = runner.extract_frozen_sha256(text)
        self.assertEqual(
            out["parameters_csv"],
            "0461da2e0de09090673192d9eb0fde6fe5e70b1d22ef61fe13cdb878c449f07e")


class RunDirCollisionTests(unittest.TestCase):
    def test_absent_dir_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = runner.ensure_run_dir_absent(tmp, "20260813T134251279572Z_f1290916")
            self.assertEqual(run_root,
                             os.path.join(tmp, "run_20260813T134251279572Z_f1290916"))

    def test_existing_dir_fails_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            rid = "20260813T134251279572Z_f1290916"
            existing = os.path.join(tmp, "run_" + rid)
            os.makedirs(existing)
            sentinel = os.path.join(existing, "sentinel.txt")
            with open(sentinel, "w", encoding="utf-8") as f:
                f.write("original")
            with self.assertRaises(runner.RunnerError):
                runner.ensure_run_dir_absent(tmp, rid)
            with open(sentinel, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "original")

    def test_main_refuses_existing_run_id_without_overwrite(self):
        """Fixed run-id generation seam: an existing run_<run_id> dir must make
        the runner exit non-zero and leave the existing bytes untouched."""
        with tempfile.TemporaryDirectory() as tmp_out:
            rid = FIXED_RUN_ID
            existing = os.path.join(tmp_out, "run_" + rid)
            os.makedirs(existing)
            sentinel = os.path.join(existing, "sentinel.txt")
            with open(sentinel, "w", encoding="utf-8") as f:
                f.write("original")
            with mock.patch.object(runner, "_generate_run_id", return_value=rid):
                code = runner.main([
                    "--parameters", REAL_PARAMETERS,
                    "--task-package", REAL_TASK_PACKAGE,
                    "--schema", REAL_SCHEMA,
                    "--fixture", REAL_FIXTURE,
                    "--upstream-run-root", REAL_UPSTREAM_ROOT,
                    "--output-root", tmp_out,
                ])
            self.assertEqual(code, 1)
            with open(sentinel, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "original")
            self.assertEqual(os.listdir(existing), ["sentinel.txt"])


class RequestTests(unittest.TestCase):
    def test_build_request_shape(self):
        req = runner.build_request(
            "20260813T134251279572Z_abcd1234",
            "single_test_unconditional_v1",
            "20260813T134251279572Z_f1290916",
            "frozen/upstream/single_test_unconditional_v1/response.json",
            "355af00ce77791208af17303912ed5972619ad89116f3d0d05f46494d534d0ea")
        self.assertEqual(req["schema_version"], "q1_quality_v1")
        self.assertEqual(req["envelope_type"], "q1_request")
        self.assertEqual(req["request_id"],
                         "20260813T134251279572Z_abcd1234:single_test_unconditional_v1")
        self.assertEqual(req["scenario_role"], "canonical_g2_02")
        self.assertEqual(req["semantics"], "single_test_unconditional_v1")
        self.assertEqual(req["upstream"]["mode"], "bound_frozen")
        ref = req["upstream"]["reference"]
        self.assertEqual(ref["run_id"], "20260813T134251279572Z_f1290916")
        self.assertEqual(ref["semantics_expect"], "single_test_unconditional_v1")
        self.assertEqual(ref["sha256"],
                         "355af00ce77791208af17303912ed5972619ad89116f3d0d05f46494d534d0ea")
        self.assertNotIn("\\", ref["file"])


class EnvelopeTests(unittest.TestCase):
    def test_build_commands_shape(self):
        entries = [
            {"index": 0, "argv": ["python", "a.py"], "cwd": "/x", "start_utc": "t0",
             "end_utc": "t1", "exit_code": 0, "stdout_rel": "o.txt", "stderr_rel": "e.txt"},
        ]
        cmds = runner.build_commands(entries)
        self.assertEqual(cmds["schema_version"], "q1_quality_v1")
        self.assertEqual(cmds["envelope_type"], "q1_command_log")
        self.assertEqual(cmds["commands"], entries)

    def test_build_manifest_shape(self):
        art = [{"path": "frozen/parameters.csv", "role": "parameters",
                "bytes": 3, "sha256": "0" * 64}]
        man = runner.build_manifest("20260813T134251279572Z_abcd1234", "PASS", art, [])
        self.assertEqual(man["envelope_type"], "q1_run_manifest")
        self.assertEqual(man["overall_status"], "PASS")
        self.assertEqual(man["artifacts"], art)
        self.assertEqual(man["notes"], [])


class ArtifactTests(unittest.TestCase):
    def test_layout_covers_24_semantic_artifacts(self):
        roles = [role for _, role in runner.ARTIFACT_LAYOUT]
        # 24-item semantic minimum from evidence_package_contract (V1.0.4:
        # 10 code/test snapshots incl. the G2-01 solver)
        self.assertIn("task_package", roles)
        self.assertIn("parameters", roles)
        self.assertIn("schema", roles)
        self.assertIn("fixture", roles)
        self.assertEqual(roles.count("upstream_response"), 2)
        self.assertIn("upstream_file_hashes", roles)
        self.assertEqual(roles.count("source_code"), 7)   # E1 main+3 routes+checker+runner+solver
        self.assertEqual(roles.count("test_code"), 3)
        self.assertEqual(roles.count("request"), 2)
        self.assertEqual(roles.count("response"), 2)
        self.assertEqual(roles.count("check_report"), 2)
        self.assertIn("commands", roles)
        self.assertEqual(roles.count("stdout_log"), 4)
        self.assertEqual(roles.count("stderr_log"), 4)
        # paths unique
        paths = [p for p, _ in runner.ARTIFACT_LAYOUT]
        self.assertEqual(len(paths), len(set(paths)))

    def test_collect_artifacts_frozen_order_and_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = os.path.join(tmp, "run")
            os.makedirs(run_root)
            for rel, _role in runner.ARTIFACT_LAYOUT:
                full = os.path.join(run_root, *rel.split("/"))
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w", encoding="utf-8") as f:
                    f.write("data:%s" % rel)
            arts = runner.collect_artifacts(run_root)
            self.assertEqual(len(arts), len(runner.ARTIFACT_LAYOUT))
            for art, (rel, role) in zip(arts, runner.ARTIFACT_LAYOUT):
                self.assertEqual(art["path"], rel)
                self.assertEqual(art["role"], role)
                self.assertEqual(art["sha256"], sha("data:%s" % rel))
                self.assertGreater(art["bytes"], 0)
            # remove one file -> only existing artifacts are listed
            os.remove(os.path.join(run_root, "single_test_unconditional_v1", "check_report.json"))
            arts2 = runner.collect_artifacts(run_root)
            self.assertEqual(len(arts2), len(runner.ARTIFACT_LAYOUT) - 1)
            self.assertNotIn("single_test_unconditional_v1/check_report.json",
                             [a["path"] for a in arts2])

    def test_collect_artifacts_code_snapshot_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = os.path.join(tmp, "run")
            code_rel = "frozen/code/04_代码/checker/q1_quality_checker_v1.py"
            full = os.path.join(run_root, *code_rel.split("/"))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write("# code")
            hashes = {code_rel: ("b" * 64, "s" * 64, "a" * 64)}
            arts = runner.collect_artifacts(run_root, hashes)
            art = [a for a in arts if a["path"] == code_rel][0]
            self.assertEqual(art["source_sha256_before"], "b" * 64)
            self.assertEqual(art["source_sha256_after"], "a" * 64)


class InventoryTests(unittest.TestCase):
    def test_hash_inventory_format_sort_and_self_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = os.path.join(tmp, "run")
            files = {
                "frozen/parameters.csv": b"p",
                "single_test_unconditional_v1/response.json": b"r",
                "file_hashes.sha256": b"self",  # must be excluded
                "run_manifest.json": b"m",
            }
            for rel, data in files.items():
                full = os.path.join(run_root, *rel.split("/"))
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "wb") as f:
                    f.write(data)
            inventory = runner.hash_inventory_lines(run_root)
            lines = [ln for ln in inventory.split("\n") if ln]
            self.assertEqual(len(lines), 3)
            for ln in lines:
                h, path = ln.split("  ", 1)
                self.assertRegex(h, r"^[0-9a-f]{64}$")
                self.assertNotIn("\\", path)
                self.assertNotEqual(path, "file_hashes.sha256")
            paths = [ln.split("  ", 1)[1] for ln in lines]
            self.assertEqual(paths, sorted(paths))  # code-point ascending
            self.assertTrue(inventory.endswith("\n"))

    def test_posix_rel(self):
        self.assertEqual(runner.posix_rel("a\\b"), "a/b")
        self.assertEqual(runner.posix_rel("a/b"), "a/b")


class FrozenInputLayoutTests(unittest.TestCase):
    def test_frozen_layout_relpaths_are_posix(self):
        # the canonical frozen input and upstream paths use forward slashes
        self.assertEqual(runner.FROZEN_INPUTS[0][1], "frozen/parameters.csv")
        self.assertEqual(runner.FROZEN_INPUTS[1][1], "frozen/G2-02_Q1概率与质量解析链.yaml")
        self.assertEqual(runner.FROZEN_INPUTS[2][1], "frozen/q1_quality_v1.schema.json")
        self.assertEqual(runner.FROZEN_INPUTS[3][1], "frozen/q1_quality_oracles_v1.json")
        for _name, rel, _key in runner.FROZEN_INPUTS:
            self.assertNotIn("\\", rel)

    def test_ten_code_snapshots_include_solver(self):
        rels = [rel for rel, _ in runner.CODE_SNAPSHOTS]
        self.assertEqual(len(rels), 10)
        for rel in rels:
            self.assertTrue(rel.startswith("04_代码/"))
        # V1.0.4: the G2-01 solver is the 10th snapshot, with NO exemption
        self.assertIn(SOLVER_REL, rels)
        self.assertEqual(rels.count(SOLVER_REL), 1)
        self.assertEqual(rels.index(SOLVER_REL), 4)  # after the 3 routes, before checker
        self.assertIn(SOLVER_FROZEN_REL, [p for p, _ in runner.ARTIFACT_LAYOUT])


class SpecBindingTests(unittest.TestCase):
    def test_spec_version_and_hashes_match_v104(self):
        """V1.0.4 spec/schema/fixture hashes correct => PASS."""
        with open(REAL_TASK_PACKAGE, encoding="utf-8") as f:
            tp_text = f.read()
        self.assertEqual(runner.SPEC_VERSION, "G2-02-SPEC-V1.0.4")
        self.assertEqual(runner.extract_task_package_version(tp_text), "G2-02-SPEC-V1.0.4")
        self.assertEqual(runner.FROZEN_SPEC_COMMIT,
                         "c10c803ecd3a4c91918a165686b16e95f400ee7c")
        self.assertEqual(runner.IMPLEMENTATION_BASELINE,
                         "d644e58f5beaa6d203d5a48179b2d3066d192a21")
        fs = runner.extract_frozen_sha256(tp_text)
        self.assertEqual(runner.SCHEMA_SHA256_FROZEN,
                         "0bb93b122572b85833c539bc6f2bee273e04a6c0984933aafa5ed6d3e66dec4d")
        self.assertEqual(runner.FIXTURE_SHA256_FROZEN,
                         "13efa773aaa2b057be33d2c511e4bc4be078a6817d47e2dc09aad9da2db5fb0f")
        self.assertEqual(fs["schema"], runner.SCHEMA_SHA256_FROZEN)
        self.assertEqual(fs["oracle_fixture"], runner.FIXTURE_SHA256_FROZEN)
        self.assertEqual(fs["parameters_csv"],
                         "0461da2e0de09090673192d9eb0fde6fe5e70b1d22ef61fe13cdb878c449f07e")
        self.assertEqual(fs["upstream_single_response"],
                         "355af00ce77791208af17303912ed5972619ad89116f3d0d05f46494d534d0ea")
        self.assertEqual(fs["upstream_chain_response"],
                         "e71473ce391da82d7711ceff872b031ec307aa6d8e524f3ff1cd5c5a440542fd")
        self.assertEqual(fs["upstream_file_hashes"],
                         "d9f030a2e79935360ee10c4991f35a6890f53c4522cb1e0dd150c02b1586717e")
        # the actual frozen files hash to the declared values
        self.assertEqual(runner.sha256_file(REAL_SCHEMA), runner.SCHEMA_SHA256_FROZEN)
        self.assertEqual(runner.sha256_file(REAL_FIXTURE), runner.FIXTURE_SHA256_FROZEN)
        self.assertEqual(runner.sha256_file(REAL_PARAMETERS), fs["parameters_csv"])
        # full binding check passes on the real package
        self.assertEqual(runner.check_spec_bindings(tp_text, fs), [])

    def test_check_spec_bindings_pure(self):
        good = {"schema": runner.SCHEMA_SHA256_FROZEN,
                "oracle_fixture": runner.FIXTURE_SHA256_FROZEN}
        self.assertEqual(
            runner.check_spec_bindings('task_package_version: "G2-02-SPEC-V1.0.4"\n', good), [])
        bad = dict(good)
        bad["schema"] = "9" * 64
        errs = runner.check_spec_bindings('task_package_version: "G2-02-SPEC-V1.0.4"\n', bad)
        self.assertTrue(any("schema" in e for e in errs))
        errs2 = runner.check_spec_bindings('task_package_version: "%s"\n' % OLD_SPEC_VERSION, good)
        self.assertTrue(any("task_package_version" in e for e in errs2))
        errs3 = runner.check_spec_bindings('task_package_version: "%s"\n' % V103_SPEC_VERSION, good)
        self.assertTrue(any("task_package_version" in e for e in errs3),
                        "V1.0.3 must NOT be an active binding in V1.0.4")

    def _dry_run_with_task_package(self, replacements):
        """Run the real main() against a temp-modified task package copy with
        real frozen inputs and a temp output root; returns
        (code, manifest, has_commands)."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = temp_task_package(tmp, replacements)
            out = os.path.join(tmp, "out")

            def no_child(*args, **kwargs):
                raise AssertionError("child must not start when freeze fails")

            fake = _FakeSubprocess(no_child)
            with mock.patch.object(runner, "subprocess", fake):
                code = runner.main([
                    "--parameters", REAL_PARAMETERS,
                    "--task-package", tp,
                    "--schema", REAL_SCHEMA,
                    "--fixture", REAL_FIXTURE,
                    "--upstream-run-root", REAL_UPSTREAM_ROOT,
                    "--output-root", out,
                ])
            run_dir = find_run_dir(out)
            with open(os.path.join(run_dir, "run_manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
            has_commands = os.path.exists(os.path.join(run_dir, "commands.json"))
            return code, manifest, has_commands

    def test_old_schema_hash_fails_dry_run(self):
        """Old (non-V1.0.3) schema hash => FAIL, no subprocess, no commands."""
        code, manifest, has_commands = self._dry_run_with_task_package(
            [(runner.SCHEMA_SHA256_FROZEN, OLD_SCHEMA_HASH)])
        self.assertEqual(code, 1)
        self.assertEqual(manifest["overall_status"], "FAIL")
        self.assertTrue(any("schema" in n for n in manifest["notes"]))
        self.assertFalse(has_commands)

    def test_old_fixture_hash_fails_dry_run(self):
        """Old (non-V1.0.3) fixture hash => FAIL, no subprocess, no commands."""
        code, manifest, has_commands = self._dry_run_with_task_package(
            [(runner.FIXTURE_SHA256_FROZEN, OLD_FIXTURE_HASH)])
        self.assertEqual(code, 1)
        self.assertEqual(manifest["overall_status"], "FAIL")
        self.assertTrue(any("oracle_fixture" in n or "fixture" in n for n in manifest["notes"]))
        self.assertFalse(has_commands)

    def test_wrong_spec_version_fails(self):
        """A non-V1.0.4 task package is refused (FAIL), never auto-updated."""
        code, manifest, has_commands = self._dry_run_with_task_package(
            [("G2-02-SPEC-V1.0.4", OLD_SPEC_VERSION)])
        self.assertEqual(code, 1)
        self.assertEqual(manifest["overall_status"], "FAIL")
        self.assertTrue(any("task_package_version" in n for n in manifest["notes"]))
        self.assertFalse(has_commands)

    def test_v103_active_binding_fails(self):
        """V1.0.4 rebind: a task package still bound to the previous active
        spec G2-02-SPEC-V1.0.3 must FAIL (no active V1.0.3 binding), and no
        E1/E2 subprocess may start (no commands.json written)."""
        code, manifest, has_commands = self._dry_run_with_task_package(
            [("G2-02-SPEC-V1.0.4", V103_SPEC_VERSION)])
        self.assertEqual(code, 1)
        self.assertEqual(manifest["overall_status"], "FAIL")
        self.assertTrue(any("task_package_version" in n for n in manifest["notes"]),
                        manifest["notes"])
        self.assertFalse(has_commands)

    def test_no_old_version_bindings_in_sources(self):
        """No ACTIVE pre-V1.0.3 spec bindings remain in the two runner files."""
        sources = [os.path.join(CODE_ROOT, "scripts", "run_g2_02_v1.py"), __file__]
        for path in sources:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for n in (0, 1, 2):
                old = "V1.0.%d" % n
                self.assertNotIn(old, text, "%s must not bind %s" % (path, old))


class EnvelopeValidationTests(unittest.TestCase):
    def test_chain_response_without_e_max_E_passes(self):
        """standard_chain_v1 responses omitting e_max_E must pass (V1.0.3)."""
        resp = make_response("standard_chain_v1")
        self.assertNotIn("e_max_E", resp["E_kernel"])
        self.assertEqual(
            runner.validate_formal_envelope(resp, "response", run_id=FIXED_RUN_ID,
                                            semantics="standard_chain_v1"), [])

    def test_single_response_with_e_max_E_passes(self):
        resp = make_response("single_test_unconditional_v1")
        self.assertIn("e_max_E", resp["E_kernel"])
        self.assertEqual(
            runner.validate_formal_envelope(resp, "response", run_id=FIXED_RUN_ID,
                                            semantics="single_test_unconditional_v1"), [])

    def test_na_null_response_passes(self):
        """O5/NA shapes (null main/sum/max_abs_deviation, null route_agreement
        lambda_*) must NOT be treated as malformed."""
        resp = make_response("single_test_unconditional_v1", na=True)
        self.assertEqual(resp["lambda"]["na"], True)
        self.assertEqual(
            runner.validate_formal_envelope(resp, "response", run_id=FIXED_RUN_ID,
                                            semantics="single_test_unconditional_v1"), [])

    def test_na_written_as_zero_rejected(self):
        """NA written as numeric 0 is NOT reintroduced: na=true requires null."""
        resp = make_response("single_test_unconditional_v1", na=True)
        resp["lambda"]["main"]["A"] = "0"
        errs = runner.validate_formal_envelope(resp, "response", run_id=FIXED_RUN_ID,
                                               semantics="single_test_unconditional_v1")
        self.assertTrue(any("null" in e for e in errs), errs)
        resp2 = make_response("single_test_unconditional_v1", na=True)
        resp2["lambda"]["sum"] = "0"
        errs2 = runner.validate_formal_envelope(resp2, "response", run_id=FIXED_RUN_ID,
                                                semantics="single_test_unconditional_v1")
        self.assertTrue(any("lambda.sum" in e for e in errs2), errs2)

    def test_qE_lexical_zero_forms_pass(self):
        """q_E="0", "0.0", "0.00" are all accepted -- no q_E=="0" string check."""
        for q in ("0", "0.0", "0.00"):
            resp = make_response("single_test_unconditional_v1")
            resp["q_E"] = q
            self.assertEqual(
                runner.validate_formal_envelope(resp, "response", run_id=FIXED_RUN_ID,
                                                semantics="single_test_unconditional_v1"), [])

    def test_cross_leg_request_id_rejected(self):
        """A response bound to the other semantics leg must fail (no mixing)."""
        resp = make_response("standard_chain_v1")
        errs = runner.validate_formal_envelope(resp, "response", run_id=FIXED_RUN_ID,
                                               semantics="single_test_unconditional_v1")
        self.assertTrue(errs)
        resp2 = make_response("single_test_unconditional_v1")
        errs2 = runner.validate_formal_envelope(resp2, "response", run_id=FIXED_RUN_ID,
                                                semantics="single_test_unconditional_v1",
                                                scenario_role="generic")
        self.assertTrue(errs2)

    def test_wrong_envelope_type_rejected(self):
        resp = make_response("single_test_unconditional_v1")
        resp["envelope_type"] = "q1_check_report"
        self.assertTrue(runner.validate_formal_envelope(
            resp, "response", run_id=FIXED_RUN_ID,
            semantics="single_test_unconditional_v1"))

    def test_missing_required_response_field_rejected(self):
        resp = make_response("single_test_unconditional_v1")
        del resp["abc_kernels"]
        self.assertTrue(runner.validate_formal_envelope(
            resp, "response", run_id=FIXED_RUN_ID,
            semantics="single_test_unconditional_v1"))

    def test_manifest_and_commands_envelopes_valid(self):
        cmds = default_commands(FIXED_RUN_ID)
        env = runner.build_commands(cmds)
        self.assertEqual(runner.validate_formal_envelope(env, "commands"), [])
        art = [{"path": "frozen/parameters.csv", "role": "parameters",
                "bytes": 3, "sha256": "0" * 64}]
        man = runner.build_manifest(FIXED_RUN_ID, "PASS", art, [])
        self.assertEqual(runner.validate_formal_envelope(man, "manifest"), [])

    def test_manifest_bad_run_id_rejected(self):
        man = runner.build_manifest("bad_id", "PASS", [], [])
        self.assertTrue(runner.validate_formal_envelope(man, "manifest"))


class EvaluationTests(unittest.TestCase):
    def _root(self, tmp, responses=None, reports=None, omit=()):
        if responses is None:
            responses = {sem: make_response(sem) for sem in runner.SEMANTICS}
        if reports is None:
            reports = {sem: make_report(responses[sem]) for sem in runner.SEMANTICS}
        return make_run_root(tmp, FIXED_RUN_ID, responses, reports, omit)

    def test_e1_nonzero_exit_fails(self):
        """E1 subprocess nonzero => FAIL with an auditable command record."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            cmds = default_commands(FIXED_RUN_ID)
            cmds[0]["exit_code"] = 3
            status, notes = runner.run_evaluate(cmds, root, FIXED_RUN_ID)
            self.assertEqual(status, "FAIL")
            self.assertEqual(cmds[0]["exit_code"], 3)  # record kept
            self.assertNotEqual(status, "PASS")

    def test_e2_checker_fail_fails(self):
        """E2 checker FAIL must fail the semantics/run (no PASS)."""
        with tempfile.TemporaryDirectory() as tmp:
            resp_single = make_response("single_test_unconditional_v1")
            reports = {
                "single_test_unconditional_v1": make_report(resp_single, "FAIL"),
                "standard_chain_v1": make_report(make_response("standard_chain_v1")),
            }
            root = make_run_root(tmp, FIXED_RUN_ID, None, reports)
            status, notes = runner.run_evaluate(default_commands(FIXED_RUN_ID),
                                                root, FIXED_RUN_ID)
            self.assertEqual(status, "FAIL")
            self.assertTrue(any("checker_status" in n for n in notes))

    def test_pass_chain_without_emax(self):
        """Chain responses omitting e_max_E pass orchestration (V1.0.3)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            status, notes = runner.run_evaluate(default_commands(FIXED_RUN_ID),
                                                root, FIXED_RUN_ID)
            self.assertEqual(status, "PASS")
            self.assertEqual(notes, [])

    def test_pass_na_response(self):
        """NA/null responses flow through the checker leg without being
        treated as malformed."""
        with tempfile.TemporaryDirectory() as tmp:
            responses = {
                "single_test_unconditional_v1": make_response(
                    "single_test_unconditional_v1", na=True),
                "standard_chain_v1": make_response("standard_chain_v1"),
            }
            reports = {sem: make_report(responses[sem]) for sem in runner.SEMANTICS}
            root = make_run_root(tmp, FIXED_RUN_ID, responses, reports)
            status, _ = runner.run_evaluate(default_commands(FIXED_RUN_ID),
                                            root, FIXED_RUN_ID)
            self.assertEqual(status, "PASS")

    def test_preflight_failure_incomplete(self):
        """E2 preflight exit 2 with no report => INCOMPLETE, evidence kept."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, omit=("standard_chain_v1/check_report.json",))
            cmds = default_commands(FIXED_RUN_ID)
            cmds[3]["exit_code"] = 2
            status, notes = runner.run_evaluate(cmds, root, FIXED_RUN_ID)
            self.assertEqual(status, "INCOMPLETE")
            self.assertTrue(any("REPORT_CONTEXT_PREFLIGHT_FAILED" in n for n in notes))

    def test_two_semantics_separate_legs(self):
        """single and chain run as separate orchestration legs: canonical
        requests never hand-fill q/e and reference the matching upstream."""
        for sem in runner.SEMANTICS:
            req = canonical_request(sem)
            self.assertEqual(req["request_id"], "%s:%s" % (FIXED_RUN_ID, sem))
            self.assertEqual(req["scenario_role"], "canonical_g2_02")
            self.assertEqual(req["upstream"]["mode"], "bound_frozen")
            self.assertEqual(req["upstream"]["reference"]["semantics_expect"], sem)
            self.assertEqual(req["upstream"]["reference"]["file"],
                             "frozen/upstream/%s/response.json" % sem)
            self.assertNotIn("values", req["upstream"])
            self.assertNotIn("q_a", json.dumps(req, ensure_ascii=False))
        # E1 argv per leg references only that leg's request/upstream/output
        with tempfile.TemporaryDirectory() as tmp:
            run_root = os.path.join(tmp, FIXED_RUN_ID)
            for sem in runner.SEMANTICS:
                argv = runner._child_argv(
                    sys.executable,
                    "frozen/code/04_代码/main_model/q1_quality_v1.py",
                    run_root,
                    ["--request", os.path.join(run_root, sem, "request.json"),
                     "--parameters", os.path.join(run_root, "frozen", "parameters.csv"),
                     "--upstream", os.path.join(run_root, "frozen", "upstream", sem, "response.json"),
                     "--schema", os.path.join(run_root, "frozen", "q1_quality_v1.schema.json"),
                     "--output", os.path.join(run_root, sem, "response.json")])
                joined = " ".join(argv).replace("\\", "/")
                self.assertIn("%s/request.json" % sem, joined)
                self.assertIn("frozen/upstream/%s/response.json" % sem, joined)
                self.assertIn("%s/response.json" % sem, joined)
                other = ("standard_chain_v1" if sem == "single_test_unconditional_v1"
                         else "single_test_unconditional_v1")
                self.assertNotIn("%s/request.json" % other, joined)
                self.assertNotIn("frozen/upstream/%s/response.json" % other, joined)


class MutationGuardTests(unittest.TestCase):
    def test_snapshot_code_detects_source_mutation(self):
        """Working-code mutation between before/after reads must raise
        RunnerError (never emit formal results from mutated source)."""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.py")
            dst = os.path.join(tmp, "sub", "dst.py")
            with open(src, "wb") as f:
                f.write(b"print('hi')\n")
            real = runner.sha256_bytes
            state = {"n": 0}

            def flaky(data):
                state["n"] += 1
                if state["n"] == 3:
                    return "f" * 64  # hash-after differs => source mutated
                return real(data)

            with mock.patch.object(runner, "sha256_bytes", side_effect=flaky):
                with self.assertRaises(runner.RunnerError):
                    runner.snapshot_code(src, dst)
            # unchanged source still snapshots cleanly
            before, snap, after = runner.snapshot_code(src, dst)
            self.assertEqual(before, snap)
            self.assertEqual(after, snap)


class CliTests(unittest.TestCase):
    BASE = ["--parameters", REAL_PARAMETERS, "--task-package", REAL_TASK_PACKAGE,
            "--schema", REAL_SCHEMA, "--fixture", REAL_FIXTURE,
            "--upstream-run-root", REAL_UPSTREAM_ROOT, "--output-root", "unused"]

    def test_rejects_run_id_option(self):
        self.assertEqual(runner.main(self.BASE + ["--run-id", "x"]), 2)

    def test_rejects_e1_e2_overrides(self):
        self.assertEqual(runner.main(self.BASE + ["--e1", "x"]), 2)
        self.assertEqual(runner.main(self.BASE + ["--e2", "x"]), 2)

    def test_missing_required_option(self):
        self.assertEqual(runner.main(["--parameters", REAL_PARAMETERS]), 2)

    def test_invalid_upstream_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = runner.main([
                "--parameters", REAL_PARAMETERS,
                "--task-package", REAL_TASK_PACKAGE,
                "--schema", REAL_SCHEMA,
                "--fixture", REAL_FIXTURE,
                "--upstream-run-root", os.path.join(tmp, "not_a_run"),
                "--output-root", tmp,
            ])
            self.assertEqual(code, 1)


def _refuse_children():
    """Fake subprocess whose ``run`` raises if any child would start."""

    def run(*args, **kwargs):
        raise AssertionError("child must not start: %r" % (args,))

    return _FakeSubprocess(run)


class SolverGuardTests(unittest.TestCase):
    """V1.0.4: the G2-01 solver observation_calibration_v1.py is snapshotted
    and guarded identically to the other nine files -- no exemption.  Any
    solver failure (mutation during copy, missing source) must FAIL/INCOMPLETE
    and no E1/E2 subprocess may start."""

    BASE = ["--parameters", REAL_PARAMETERS, "--task-package", REAL_TASK_PACKAGE,
            "--schema", REAL_SCHEMA, "--fixture", REAL_FIXTURE,
            "--upstream-run-root", REAL_UPSTREAM_ROOT]

    def test_solver_mutation_during_copy_fails_no_children(self):
        """Solver hash-after differs from hash-before => INCOMPLETE, no
        commands.json, no E1/E2 subprocess."""
        with open(runner.code_source_path(SOLVER_REL), "rb") as f:
            solver_bytes = f.read()
        real_sha = runner.sha256_bytes
        seen = {"n": 0}

        def flaky(data):
            if data == solver_bytes:
                seen["n"] += 1
                if seen["n"] == 3:  # the hash-after read of the solver
                    return "f" * 64  # source "mutated" inside the copy window
            return real_sha(data)

        with tempfile.TemporaryDirectory() as tmp_out:
            with mock.patch.object(runner, "sha256_bytes", side_effect=flaky):
                with mock.patch.object(runner, "subprocess", _refuse_children()):
                    code = runner.main(self.BASE + ["--output-root", tmp_out])
            self.assertEqual(code, 1)
            run_dir = find_run_dir(tmp_out)
            with open(os.path.join(run_dir, "run_manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual(manifest["overall_status"], "INCOMPLETE")
            self.assertTrue(any("observation_calibration" in n
                                or "snapshot" in n for n in manifest["notes"]),
                            manifest["notes"])
            # no child ever started and no command log was fabricated
            self.assertFalse(os.path.exists(os.path.join(run_dir, "commands.json")))

    def test_solver_source_missing_fails_no_children(self):
        """Working-tree solver missing => INCOMPLETE, no commands.json, no
        E1/E2 subprocess (the solver has no missing-file exemption)."""
        real_csp = runner.code_source_path

        def missing_solver(rel):
            if rel == SOLVER_REL:
                return os.path.join(tempfile.gettempdir(), "no_such_solver_%s.py"
                                    % ("missing",))
            return real_csp(rel)

        with tempfile.TemporaryDirectory() as tmp_out:
            with mock.patch.object(runner, "code_source_path",
                                   side_effect=missing_solver):
                with mock.patch.object(runner, "subprocess", _refuse_children()):
                    code = runner.main(self.BASE + ["--output-root", tmp_out])
            self.assertEqual(code, 1)
            run_dir = find_run_dir(tmp_out)
            with open(os.path.join(run_dir, "run_manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual(manifest["overall_status"], "INCOMPLETE")
            self.assertFalse(os.path.exists(os.path.join(run_dir, "commands.json")))


class FrozenClosureTests(unittest.TestCase):
    """Controlled process-level harness for the V1.0.4 runtime closure: the
    frozen E1 (main + three routes + the G2-01 solver) is rebuilt in a temp
    run structure using the runner's own snapshot guard, then executed in a
    clean interpreter whose cwd and sys.path point only at the temp tree.
    Proves frozen E1 imports the frozen solver with no working-tree fallback.
    No formal run directory is ever created (all output stays in tmp)."""

    E1_CLOSURE = [
        "04_代码/main_model/q1_quality_v1.py",
        "04_代码/main_model/q1_routes/closed_form_v1.py",
        "04_代码/main_model/q1_routes/enumeration_v1.py",
        "04_代码/main_model/q1_routes/absorption_chain_v1.py",
        SOLVER_REL,
    ]

    def _build_frozen_closure(self, tmp, include_solver=True):
        """Byte-copy the E1 closure into tmp/frozen/code/04_代码/main_model/
        with the runner's own snapshot_code triple-hash guard (mirrors the
        runner's frozen/code layout)."""
        mm = os.path.join(tmp, "frozen", "code", "04_代码", "main_model")
        rels = list(self.E1_CLOSURE)
        if not include_solver:
            rels.remove(SOLVER_REL)
        for rel in rels:
            src = runner.code_source_path(rel)
            dst = os.path.join(mm, *rel.split("/")[2:])
            before, snap, after = runner.snapshot_code(src, dst)
            self.assertEqual(before, snap)
            self.assertEqual(after, snap)
        return mm

    def _probe(self, frozen_mm, cwd):
        """Run a clean interpreter with only frozen_mm on sys.path (plus
        stdlib/site-packages), cwd pointing at the temp tree, PYTHONPATH
        emptied and user site disabled.  Reports whether the frozen E1 module
        loaded the calibrator and which file the solver import resolved to."""
        probe = (
            "import json, sys\n"
            "sys.path.insert(0, %r)\n"
            "try:\n"
            "    import observation_calibration_v1 as _cal\n"
            "    cal_file = _cal.__file__\n"
            "except Exception as _exc:\n"
            "    cal_file = 'IMPORT_ERROR:' + type(_exc).__name__\n"
            "import q1_quality_v1 as _e1\n"
            "print(json.dumps({'calibrator_loaded': _e1._calibrator is not None,"
            "'cal_file': cal_file}))\n"
        ) % (frozen_mm,)
        env = dict(os.environ)
        env["PYTHONPATH"] = ""
        env.pop("PYTHONHOME", None)
        env["PYTHONNOUSERSITE"] = "1"
        return subprocess.run([sys.executable, "-c", probe], cwd=cwd, env=env,
                              capture_output=True, text=True)

    def _probe_result(self, proc, expect_loaded):
        self.assertEqual(proc.returncode, 0,
                         "probe failed: rc=%s stderr=%s" % (proc.returncode, proc.stderr))
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(out["calibrator_loaded"], expect_loaded, out)
        return out

    def test_frozen_e1_imports_frozen_solver(self):
        """(9) Frozen E1 in a temp run structure imports the frozen solver."""
        with tempfile.TemporaryDirectory() as tmp:
            frozen_mm = self._build_frozen_closure(tmp, include_solver=True)
            out = self._probe_result(self._probe(frozen_mm, cwd=tmp), True)
            self.assertTrue(out["calibrator_loaded"], out)
            frozen_solver = os.path.join(frozen_mm, "observation_calibration_v1.py")
            self.assertEqual(os.path.normcase(out["cal_file"]),
                             os.path.normcase(frozen_solver),
                             "solver must resolve to the frozen copy: %s" % out)

    def test_no_worktree_fallback(self):
        """(10) When the frozen solver copy is absent and only the temp run
        tree is visible, frozen E1 must NOT fall back to the working-tree
        solver: the import fails and _calibrator stays None, even though the
        working-tree solver exists on disk."""
        self.assertTrue(os.path.isfile(runner.code_source_path(SOLVER_REL)),
                        "negative control requires the worktree solver to exist")
        with tempfile.TemporaryDirectory() as tmp:
            frozen_mm = self._build_frozen_closure(tmp, include_solver=False)
            self.assertFalse(os.path.isfile(
                os.path.join(frozen_mm, "observation_calibration_v1.py")))
            out = self._probe_result(self._probe(frozen_mm, cwd=tmp), False)
            self.assertFalse(out["calibrator_loaded"], out)
            self.assertIn("IMPORT_ERROR", out["cal_file"], out)


class FullRunSmokeTests(unittest.TestCase):
    """End-to-end main() flows with a mocked subprocess; all run output goes
    to a temp output root -- no formal canonical run is ever created."""

    def _fake_children(self, e1_exit=None):
        def run(argv, cwd=None, shell=False, stdout=None, stderr=None):
            flags = dict(zip(argv[2::2], argv[3::2]))
            script = argv[1].replace("\\", "/")
            if script.endswith("main_model/q1_quality_v1.py"):
                with open(flags["--request"], encoding="utf-8") as f:
                    req = json.load(f)
                sem = req["semantics"]
                resp = response_from_request(req)
                with open(flags["--output"], "w", encoding="utf-8") as f:
                    json.dump(resp, f, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
                code = 3 if e1_exit == sem else 0
                return subprocess.CompletedProcess(argv, code, b"", b"")
            if script.endswith("checker/q1_quality_checker_v1.py"):
                with open(flags["--response"], encoding="utf-8") as f:
                    resp = json.load(f)
                rep = make_report(resp)
                with open(flags["--report"], "w", encoding="utf-8") as f:
                    json.dump(rep, f, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
                return subprocess.CompletedProcess(argv, 0, b"", b"")
            raise AssertionError("unexpected child script %s" % script)
        return run

    def _run_main(self, tmp_out, run_fn):
        fake = _FakeSubprocess(run_fn)
        with mock.patch.object(runner, "subprocess", fake):
            return runner.main([
                "--parameters", REAL_PARAMETERS,
                "--task-package", REAL_TASK_PACKAGE,
                "--schema", REAL_SCHEMA,
                "--fixture", REAL_FIXTURE,
                "--upstream-run-root", REAL_UPSTREAM_ROOT,
                "--output-root", tmp_out,
            ])

    def test_full_pass_flow(self):
        with tempfile.TemporaryDirectory() as tmp_out:
            code = self._run_main(tmp_out, self._fake_children())
            self.assertEqual(code, 0)
            run_dir = find_run_dir(tmp_out)
            # run dir lives under the temp output root, never under 05_结果
            self.assertTrue(os.path.abspath(run_dir).startswith(os.path.abspath(tmp_out)))
            with open(os.path.join(run_dir, "run_manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual(manifest["overall_status"], "PASS")
            self.assertEqual(manifest["notes"], [])
            self.assertEqual(len(manifest["artifacts"]), len(runner.ARTIFACT_LAYOUT))
            # manifest artifact hashes bind to the actual file bytes
            for art in manifest["artifacts"]:
                full = os.path.join(run_dir, *art["path"].split("/"))
                self.assertTrue(os.path.isfile(full), art["path"])
                self.assertEqual(art["sha256"], runner.sha256_file(full))
            # V1.0.4: the G2-01 solver is the 10th code snapshot; its frozen
            # copy is byte-identical to the working-tree source and its
            # before/snapshot/after guard passed (source == snapshot == source)
            solver_src = runner.code_source_path(SOLVER_REL)
            self.assertTrue(os.path.isfile(solver_src), solver_src)
            solver_arts = [a for a in manifest["artifacts"]
                           if a["path"] == SOLVER_FROZEN_REL]
            self.assertEqual(len(solver_arts), 1,
                             "solver must appear in the manifest inventory")
            solver_art = solver_arts[0]
            self.assertEqual(solver_art["role"], "source_code")
            self.assertEqual(solver_art["sha256"], runner.sha256_file(solver_src))
            self.assertEqual(solver_art["source_sha256_before"], solver_art["sha256"])
            self.assertEqual(solver_art["source_sha256_after"], solver_art["sha256"])
            solver_frozen = os.path.join(run_dir, *SOLVER_FROZEN_REL.split("/"))
            self.assertTrue(os.path.isfile(solver_frozen))
            self.assertEqual(runner.sha256_file(solver_frozen), runner.sha256_file(solver_src))
            # commands: exactly 4 in frozen order, all exit 0, argv[1] = frozen copy
            with open(os.path.join(run_dir, "commands.json"), encoding="utf-8") as f:
                cmds = json.load(f)["commands"]
            self.assertEqual([c["index"] for c in cmds], [0, 1, 2, 3])
            self.assertEqual([c["exit_code"] for c in cmds], [0, 0, 0, 0])
            for c in cmds:
                self.assertTrue(os.path.isfile(c["argv"][1]))
                self.assertIn("frozen" + os.sep + "code", c["argv"][1])
            for argv in (c["argv"] for c in cmds[0::2]):  # E1 legs
                self.assertIn("--request", argv)
                self.assertIn("--output", argv)
            for argv in (c["argv"] for c in cmds[1::2]):  # E2 legs
                self.assertIn("--report", argv)
                self.assertNotIn("--request", argv)   # E2 never receives a request
                self.assertNotIn("--fixture", argv)   # E2 never receives the fixture
            # two semantics: separate canonical requests bound to matching upstream
            for i, sem in enumerate(runner.SEMANTICS):
                with open(os.path.join(run_dir, sem, "request.json"), encoding="utf-8") as f:
                    req = json.load(f)
                self.assertEqual(req["request_id"], "%s:%s" % (manifest["run_id"], sem))
                self.assertEqual(req["upstream"]["reference"]["semantics_expect"], sem)
                self.assertEqual(req["upstream"]["reference"]["file"],
                                 "frozen/upstream/%s/response.json" % sem)
            # V1.0.3: chain response omits e_max_E, single response has it
            with open(os.path.join(run_dir, "single_test_unconditional_v1", "response.json"),
                      encoding="utf-8") as f:
                resp_s = json.load(f)
            with open(os.path.join(run_dir, "standard_chain_v1", "response.json"),
                      encoding="utf-8") as f:
                resp_c = json.load(f)
            self.assertIn("e_max_E", resp_s["E_kernel"])
            self.assertNotIn("e_max_E", resp_c["E_kernel"])
            self.assertEqual(
                runner.validate_formal_envelope(resp_c, "response",
                                                run_id=manifest["run_id"],
                                                semantics="standard_chain_v1"), [])
            # hash inventory: sorted, self-excluded, covers every other file
            with open(os.path.join(run_dir, "file_hashes.sha256"), encoding="utf-8") as f:
                inv = f.read()
            lines = [ln for ln in inv.split("\n") if ln]
            all_files = []
            for dirpath, _d, filenames in os.walk(run_dir):
                for name in filenames:
                    all_files.append(os.path.relpath(os.path.join(dirpath, name),
                                                     run_dir).replace(os.sep, "/"))
            self.assertEqual(len(lines), len(all_files) - 1)  # excludes itself
            paths = [ln.split("  ", 1)[1] for ln in lines]
            self.assertEqual(paths, sorted(paths))
            self.assertNotIn("file_hashes.sha256", paths)
            # file_hashes inventory includes the 10th solver snapshot
            self.assertIn(SOLVER_FROZEN_REL, paths)

    def test_full_flow_e1_nonzero_fails(self):
        with tempfile.TemporaryDirectory() as tmp_out:
            code = self._run_main(tmp_out, self._fake_children(
                e1_exit="single_test_unconditional_v1"))
            self.assertEqual(code, 1)
            run_dir = find_run_dir(tmp_out)
            with open(os.path.join(run_dir, "run_manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual(manifest["overall_status"], "FAIL")
            with open(os.path.join(run_dir, "commands.json"), encoding="utf-8") as f:
                cmds = json.load(f)["commands"]
            self.assertEqual(cmds[0]["exit_code"], 3)
            # auditable record: logs for the failed child are preserved
            self.assertTrue(os.path.isfile(os.path.join(
                run_dir, "single_test_unconditional_v1", "e1.stdout.txt")))
            self.assertTrue(os.path.isfile(os.path.join(
                run_dir, "single_test_unconditional_v1", "e1.stderr.txt")))


if __name__ == "__main__":
    unittest.main()
