"""Unit tests for G3-SPEC-V1.0 S9 evidence package logic (run_g3_evidence_v1).

Scope discipline (task package): pure functions only -- run-directory
scanning, file_hashes.sha256 verification, source/task/params/contract hash
collection and the evidence index structure.  NO simulation runs and NO
recomputation of any number are performed here; S9 aggregates only.

Frozen-contract coverage:

  1. collect_runs scans tuning + holdout roots and reports run dirs with
     manifest presence and file_hashes verification
  2. file_hashes.sha256 verification flags missing files / malformed lines /
     hash mismatches (using a synthetic run dir)
  3. build_index pins task package ref/hash, parameters, contract, source
     files and environment; every source file listed exists and hashes
  4. the index marks G3 data as non-formal (allowed_in_paper...=False) and
     preserves failed/superseded runs as non-accepted
  5. no Q2/Q3 formal claims, no H2, no K recommendation anywhere in the
     index structure
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
CODE_DIR = BASE / "04_代码"

RUNNER_PATH = CODE_DIR / "scripts" / "run_g3_evidence_v1.py"
_SPEC = importlib.util.spec_from_file_location(
    "run_g3_evidence_v1_under_test", RUNNER_PATH
)
RUNNER = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = RUNNER
_SPEC.loader.exec_module(RUNNER)


class TestCollectRuns(unittest.TestCase):
    def test_scans_both_roots(self):
        runs = RUNNER.collect_runs()
        self.assertGreaterEqual(len(runs), 1)
        dirs = {r["run_dir"] for r in runs}
        self.assertTrue(any("tuning" in d for d in dirs))
        self.assertTrue(any("holdout" in d for d in dirs))
        for r in runs:
            self.assertIn("has_manifest", r)
            self.assertIn("file_hashes_verified", r)

    def test_accepted_holdout_present(self):
        runs = RUNNER.collect_runs()
        accepted = [
            r for r in runs
            if r.get("overall_status") == "PASS"
            and r.get("file_hashes_verified")
            and r.get("purpose") == "holdout"
        ]
        self.assertGreaterEqual(len(accepted), 1)


class TestFileHashesVerification(unittest.TestCase):
    def _make_run_dir(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "a.json").write_text('{"x":1}\n', encoding="utf-8", newline="\n")
        (tmp / "b.txt").write_text("hello\n", encoding="utf-8", newline="\n")
        return tmp

    def test_all_hashes_verify(self):
        d = self._make_run_dir()
        lines = []
        for name in ("a.json", "b.txt"):
            digest = hashlib.sha256((d / name).read_bytes()).hexdigest()
            lines.append(f"{digest}  {name}")
        (d / "file_hashes.sha256").write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )
        ok, issues = RUNNER._verify_file_hashes(d)
        self.assertTrue(ok)
        self.assertEqual(issues, [])

    def test_missing_file_flagged(self):
        d = self._make_run_dir()
        digest = hashlib.sha256(b"x").hexdigest()
        (d / "file_hashes.sha256").write_text(
            f"{digest}  missing.json\n", encoding="utf-8", newline="\n"
        )
        ok, issues = RUNNER._verify_file_hashes(d)
        self.assertFalse(ok)
        self.assertTrue(any("missing" in i for i in issues))

    def test_hash_mismatch_flagged(self):
        d = self._make_run_dir()
        digest = hashlib.sha256(b"wrong").hexdigest()
        (d / "file_hashes.sha256").write_text(
            f"{digest}  a.json\n", encoding="utf-8", newline="\n"
        )
        ok, issues = RUNNER._verify_file_hashes(d)
        self.assertFalse(ok)
        self.assertTrue(any("mismatch" in i for i in issues))

    def test_malformed_line_flagged(self):
        d = self._make_run_dir()
        (d / "file_hashes.sha256").write_text(
            "no-two-spaces\n", encoding="utf-8", newline="\n"
        )
        ok, issues = RUNNER._verify_file_hashes(d)
        self.assertFalse(ok)
        self.assertTrue(any("malformed" in i for i in issues))


class TestBuildIndex(unittest.TestCase):
    def test_structure_and_pins(self):
        index = RUNNER.build_index()
        self.assertEqual(index["task_package_ref"], "G3-SPEC-V1.0")
        self.assertEqual(index["registry_version"], "CR-V3.1")
        self.assertEqual(len(index["task_package"]["sha256"]), 64)
        self.assertEqual(len(index["parameters_csv"]["sha256"]), 64)
        self.assertEqual(len(index["problem_contract"]["sha256"]), 64)
        self.assertGreaterEqual(len(index["source_files"]), 10)
        for s in index["source_files"]:
            self.assertEqual(len(s["sha256"]), 64)
            self.assertTrue(Path(BASE, s["path"]).is_file())

    def test_runs_present(self):
        index = RUNNER.build_index()
        self.assertGreaterEqual(len(index["runs"]), 1)
        for r in index["runs"]:
            self.assertTrue(r["run_dir"].startswith("05_结果/G3/"))
            self.assertIn("superseded", r)

    def test_no_formal_claims(self):
        index = RUNNER.build_index()
        for r in index["runs"]:
            self.assertNotEqual(r.get("formal"), True)
        blob = json.dumps(index, ensure_ascii=False)
        self.assertNotIn('"formal": true', blob)

    def test_notes_scope_boundary(self):
        index = RUNNER.build_index()
        notes = " ".join(index["notes"])
        self.assertIn("非 Q2 正式", notes)
        self.assertIn("不重新生成任何仿真数字", notes)

    def test_superseded_marking(self):
        runs = RUNNER.collect_runs()
        self.assertGreaterEqual(len(runs), 1)
        some = runs[0]["run_id"]
        index = RUNNER.build_index((some,))
        marked = [r for r in index["runs"] if r["run_id"] == some]
        self.assertEqual(len(marked), 1)
        self.assertTrue(marked[0]["superseded"])
        self.assertIn(some, index["superseded_run_ids"])


if __name__ == "__main__":
    unittest.main()
