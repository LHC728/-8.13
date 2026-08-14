# -*- coding: utf-8 -*-
"""G2-02 L1 evidence runner (run_g2_02_v1).

Role
----
Orchestrates one immutable canonical run for task package
G2-02-SPEC-V1.0.3 (V1.0.3 rebind: NA/null interface contract, frozen
2026-08-14; frozen spec commit 4936327440238b442ec02edaba8226b90426300b,
implementation baseline d644e58f5beaa6d203d5a48179b2d3066d192a21):
it freezes the frozen inputs and the nine source/test files, generates the
two canonical requests, executes the frozen E1/E2 copies via subprocess
(``shell=False``, exact argv arrays), and builds the evidence package
(run_manifest.json, commands.json, file_hashes.sha256) under
``05_结果/G2/run_<run_id>/``.

Boundaries (frozen)
-------------------
* Orchestration structure ONLY.  The runner never imports E1/E2 modules, never
  computes any formula, never recomputes any numeric value, and never decides
  PASS/FAIL from numeric content.  PASS requires structural evidence: both E1
  and both E2 subprocesses exit 0, both ``check_report.json`` exist with
  ``checker_status == "PASS"``, both response/check_report envelopes conform
  to the V1.0.3 schema (envelope level), the nine code snapshots have
  hash-before == snapshot-hash == hash-after, frozen input hashes match the
  task package ``frozen_sha256``, and every declared artifact exists.
* V1.0.3 compatibility: lambda NA (na=true) is expressed with null main
  leaves, sum and max_abs_deviation (never numeric 0); q_E is never judged
  numerically (no ``q_E == "0"`` string check); standard_chain_v1 responses
  may omit e_max_E entirely.
* run_id = UTC ``YYYYMMDDTHHMMSSffffffZ_`` + 8 hex chars
  (secrets.token_hex(4)).  If the run directory already exists the runner
  FAILS; it never overwrites.
* The formal CLI accepts exactly the six frozen options (--parameters,
  --task-package, --schema, --fixture, --upstream-run-root, --output-root);
  no --run-id, --e1, --e2, executable override or algorithm override.
* E1/E2 child argv[1] always points at the run's frozen code copy
  (``frozen/code/...``), never at the working tree.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys

SCHEMA_VERSION = "q1_quality_v1"
ENVELOPE_MANIFEST = "q1_run_manifest"
ENVELOPE_COMMANDS = "q1_command_log"

# Project root derived from this file (04_代码/scripts/run_g2_02_v1.py):
# .. -> 04_代码/scripts, ../.. -> 04_代码, ../../.. -> project root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SEMANTICS = ("single_test_unconditional_v1", "standard_chain_v1")
UPSTREAM_RUN_ROOT_PREFIX = "run_"
# Immutable run directory name per evidence_package_contract root
# "05_结果/G2/run_<immutable_run_id>/" (the manifest run_id itself stays bare).
RUN_DIR_PREFIX = "run_"
RUN_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{12}Z_[0-9a-f]{8}$")

# ---- V1.0.3 frozen bindings (documented + enforced for spec/version/hashes) ----
SPEC_VERSION = "G2-02-SPEC-V1.0.3"
SCHEMA_SHA256_FROZEN = "0bb93b122572b85833c539bc6f2bee273e04a6c0984933aafa5ed6d3e66dec4d"
FIXTURE_SHA256_FROZEN = "13efa773aaa2b057be33d2c511e4bc4be078a6817d47e2dc09aad9da2db5fb0f"
FROZEN_SPEC_COMMIT = "4936327440238b442ec02edaba8226b90426300b"
IMPLEMENTATION_BASELINE = "d644e58f5beaa6d203d5a48179b2d3066d192a21"

SCENARIO_ROLES = ("canonical_g2_02", "generic", "test_oracle")
OVERALL_STATUSES = ("ALL_ROUTES_AGREE", "ROUTE_MISMATCH", "HAS_INFEASIBLE",
                    "HAS_INDETERMINATE", "FAILED_VALIDATION", "NUMERICAL_FAILURE")
PROCESS_STATUSES = ("UNIQUE_SOLUTION", "NONIDENTIFIABLE_FAMILY", "INFEASIBLE")
CHECKER_STATUSES = ("PASS", "FAIL")
MANIFEST_STATUSES = ("PASS", "FAIL", "INCOMPLETE")
DECIMAL_PROB_RE = re.compile(r"^(0(?:\.[0-9]+)?|1(?:\.0+)?)$")
DECIMAL_SIGNED_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# (project-relative source path, manifest role)
CODE_SNAPSHOTS = [
    ("04_代码/main_model/q1_quality_v1.py", "source_code"),
    ("04_代码/main_model/q1_routes/closed_form_v1.py", "source_code"),
    ("04_代码/main_model/q1_routes/enumeration_v1.py", "source_code"),
    ("04_代码/main_model/q1_routes/absorption_chain_v1.py", "source_code"),
    ("04_代码/checker/q1_quality_checker_v1.py", "source_code"),
    ("04_代码/scripts/run_g2_02_v1.py", "source_code"),
    ("04_代码/tests/test_q1_quality_main_v1.py", "test_code"),
    ("04_代码/tests/test_q1_quality_checker_v1.py", "test_code"),
    ("04_代码/tests/test_run_g2_02_v1.py", "test_code"),
]

# Frozen input files: (source relative path, frozen relative path, frozen_sha256 key)
FROZEN_INPUTS = [
    ("parameters", "frozen/parameters.csv", "parameters_csv"),
    ("task_package", "frozen/G2-02_Q1概率与质量解析链.yaml", None),  # not self-referenced
    ("schema", "frozen/q1_quality_v1.schema.json", "schema"),
    ("fixture", "frozen/q1_quality_oracles_v1.json", "oracle_fixture"),
]


class RunnerError(Exception):
    """Fatal runner error: keep evidence, exit non-zero."""


# --------------------------------------------------------------------------
# Pure helpers (unit-testable without CLI options)
# --------------------------------------------------------------------------

def new_run_id(now_utc, token):
    """run_id = YYYYMMDDTHHMMSSffffffZ_ + 8 hex chars."""
    return now_utc.strftime("%Y%m%dT%H%M%S%fZ") + "_" + token


def _generate_run_id(now_utc=None):
    """Internal run-id generator (test seam; never exposed as a CLI option)."""
    if now_utc is None:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
    return new_run_id(now_utc, secrets.token_hex(4))


def is_valid_run_id(run_id):
    return isinstance(run_id, str) and bool(RUN_ID_RE.match(run_id))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_bytes(path, data):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def write_json(path, obj):
    """UTF-8, sort_keys, compact separators, trailing LF."""
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n"
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def posix_rel(path):
    return path.replace(os.sep, "/")


def code_source_path(rel):
    """Absolute path of a project-relative code snapshot source."""
    return os.path.join(PROJECT_ROOT, *rel.split("/"))


def snapshot_code(src_path, dst_path):
    """Copy src -> dst with hash-before = snapshot-hash = hash-after.

    Returns (hash_before, hash_snapshot, hash_after).  Raises OSError /
    RunnerError if the source is missing or the three hashes differ (the
    source changed inside the copy window).
    """
    with open(src_path, "rb") as f:
        data_before = f.read()
    hash_before = sha256_bytes(data_before)
    parent = os.path.dirname(dst_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dst_path, "wb") as f:
        f.write(data_before)
    with open(dst_path, "rb") as f:
        data_snapshot = f.read()
    hash_snapshot = sha256_bytes(data_snapshot)
    with open(src_path, "rb") as f:
        data_after = f.read()
    hash_after = sha256_bytes(data_after)
    if not (hash_before == hash_snapshot == hash_after):
        raise RunnerError(
            "code snapshot hash mismatch for %s: before=%s snapshot=%s after=%s"
            % (src_path, hash_before, hash_snapshot, hash_after))
    return hash_before, hash_snapshot, hash_after


def extract_frozen_sha256(yaml_text):
    """Extract the ``frozen_sha256`` mapping from the frozen task package
    (line-based; the block is regular ``key: value`` lines under the
    ``frozen_sha256:`` key)."""
    result = {}
    in_block = False
    block_indent = None
    for raw in yaml_text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        s = raw.strip()
        if in_block:
            if indent <= block_indent:
                in_block = False
            else:
                if ":" in s:
                    k, v = s.split(":", 1)
                    v = v.strip()
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                        v = v[1:-1]
                    result[k.strip()] = v
                continue
        if s.rstrip().endswith(":") and s.split(":", 1)[0].strip() == "frozen_sha256":
            in_block = True
            block_indent = indent
    return result


def extract_task_package_version(yaml_text):
    """Extract the top-level ``task_package_version`` scalar."""
    for raw in yaml_text.splitlines():
        s = raw.strip()
        if s.startswith("task_package_version:"):
            v = s.split(":", 1)[1].strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            return v
    return None


def check_spec_bindings(tp_text, frozen_sha256):
    """V1.0.3 binding checks: task package version and the frozen schema /
    fixture SHA-256 values must equal the frozen V1.0.3 bindings.

    Returns a list of error strings (empty == bound).  A mismatch means the
    runner must not start E1/E2.
    """
    errors = []
    ver = extract_task_package_version(tp_text)
    if ver != SPEC_VERSION:
        errors.append("task_package_version %r != frozen %s" % (ver, SPEC_VERSION))
    if frozen_sha256.get("schema") != SCHEMA_SHA256_FROZEN:
        errors.append(
            "frozen_sha256.schema %s != V1.0.3 binding %s"
            % (frozen_sha256.get("schema"), SCHEMA_SHA256_FROZEN))
    if frozen_sha256.get("oracle_fixture") != FIXTURE_SHA256_FROZEN:
        errors.append(
            "frozen_sha256.oracle_fixture %s != V1.0.3 binding %s"
            % (frozen_sha256.get("oracle_fixture"), FIXTURE_SHA256_FROZEN))
    return errors


def ensure_run_dir_absent(output_root, run_id):
    """Fail (raise RunnerError) if the run directory already exists; the
    runner never overwrites an existing evidence package.  The immutable run
    directory is named ``run_<run_id>`` per evidence_package_contract root
    ``05_结果/G2/run_<immutable_run_id>/``."""
    run_root = os.path.join(output_root, RUN_DIR_PREFIX + run_id)
    if os.path.exists(run_root):
        raise RunnerError(
            "run directory already exists, refusing to overwrite: %s" % run_root)
    return run_root


def build_request(run_id, semantics, upstream_run_id, upstream_file_rel,
                  upstream_sha256, semantics_expect=None):
    """Canonical request envelope (bound_frozen upstream)."""
    if semantics_expect is None:
        semantics_expect = semantics
    return {
        "schema_version": SCHEMA_VERSION,
        "envelope_type": "q1_request",
        "request_id": "%s:%s" % (run_id, semantics),
        "scenario_role": "canonical_g2_02",
        "semantics": semantics,
        "upstream": {
            "mode": "bound_frozen",
            "reference": {
                "run_id": upstream_run_id,
                "file": posix_rel(upstream_file_rel),
                "sha256": upstream_sha256,
                "semantics_expect": semantics_expect,
            },
        },
    }


def build_commands(entries):
    """q1_command_log envelope from command entry dicts (frozen order)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "envelope_type": ENVELOPE_COMMANDS,
        "commands": entries,
    }


def build_manifest(run_id, overall_status, artifacts, notes):
    """q1_run_manifest envelope."""
    return {
        "schema_version": SCHEMA_VERSION,
        "envelope_type": ENVELOPE_MANIFEST,
        "run_id": run_id,
        "overall_status": overall_status,
        "artifacts": artifacts,
        "notes": notes,
    }


def _artifact(rel_path, role, byte_size, sha, before=None, after=None):
    item = {
        "path": posix_rel(rel_path),
        "role": role,
        "bytes": byte_size,
        "sha256": sha,
    }
    if before is not None:
        item["source_sha256_before"] = before
    if after is not None:
        item["source_sha256_after"] = after
    return item


ARTIFACT_LAYOUT = [
    ("frozen/G2-02_Q1概率与质量解析链.yaml", "task_package"),
    ("frozen/parameters.csv", "parameters"),
    ("frozen/q1_quality_v1.schema.json", "schema"),
    ("frozen/q1_quality_oracles_v1.json", "fixture"),
    ("frozen/upstream/single_test_unconditional_v1/response.json", "upstream_response"),
    ("frozen/upstream/standard_chain_v1/response.json", "upstream_response"),
    ("frozen/upstream/file_hashes.sha256", "upstream_file_hashes"),
]
for _rel, _role in CODE_SNAPSHOTS:
    ARTIFACT_LAYOUT.append(("frozen/code/" + posix_rel(_rel), _role))
for _sem in SEMANTICS:
    ARTIFACT_LAYOUT.extend([
        (_sem + "/request.json", "request"),
        (_sem + "/response.json", "response"),
        (_sem + "/check_report.json", "check_report"),
        (_sem + "/e1.stdout.txt", "stdout_log"),
        (_sem + "/e1.stderr.txt", "stderr_log"),
        (_sem + "/e2.stdout.txt", "stdout_log"),
        (_sem + "/e2.stderr.txt", "stderr_log"),
    ])
ARTIFACT_LAYOUT.append(("commands.json", "commands"))
# NOTE: file_hashes.sha256 is deliberately NOT in the layout: it is created
# after the manifest (the manifest's hash is recorded inside it), it is not
# one of the 23 semantic artifacts, and requiring it here would make the
# PASS presence check impossible (it does not exist at evaluation time).


def collect_artifacts(run_root, code_snapshot_hashes=None):
    """Build the manifest artifacts array in frozen order; only existing files
    are included.  ``code_snapshot_hashes`` maps the frozen code relative path
    to (hash_before, hash_snapshot, hash_after) for the nine code files."""
    code_snapshot_hashes = code_snapshot_hashes or {}
    artifacts = []
    for rel, role in ARTIFACT_LAYOUT:
        full = os.path.join(run_root, *rel.split("/"))
        if not os.path.isfile(full):
            continue
        with open(full, "rb") as f:
            data = f.read()
        before = after = None
        if role in ("source_code", "test_code"):
            h = code_snapshot_hashes.get(rel)
            if h is not None:
                before, _, after = h
        artifacts.append(_artifact(rel, role, len(data), sha256_bytes(data), before, after))
    return artifacts


def hash_inventory_lines(run_root):
    """SHA-256 inventory: lowercase hash, two spaces, POSIX relative path,
    sorted by path Unicode code-point ascending, LF; excludes
    ``file_hashes.sha256`` itself; files only."""
    entries = []
    for dirpath, dirnames, filenames in os.walk(run_root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = posix_rel(os.path.relpath(full, run_root))
            if rel == "file_hashes.sha256":
                continue
            with open(full, "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
            entries.append((rel, digest))
    entries.sort(key=lambda pair: pair[0])
    return "".join("%s  %s\n" % (digest, rel) for rel, digest in entries)


def utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# --------------------------------------------------------------------------
# V1.0.3 envelope-level schema validation (structural only)
# --------------------------------------------------------------------------

def _is_str(v):
    return isinstance(v, str) and v != ""


def _is_decimal_prob(v):
    """Schema ``decimalProbability``: string in [0,1]; lexical zero forms
    "0", "0.0", "0.00", ... all match (never judged numerically)."""
    return isinstance(v, str) and bool(DECIMAL_PROB_RE.match(v))


def _is_decimal_signed(v):
    return isinstance(v, str) and bool(DECIMAL_SIGNED_RE.match(v))


def _is_sha256(v):
    return isinstance(v, str) and bool(SHA256_RE.match(v))


def _check_lambda_block(lam, errors):
    """V1.0.3 lambda rules: na=true requires null main A..D, sum and
    max_abs_deviation (NA must never be written as numeric 0); na=false
    requires decimal main/sum/max_abs_deviation; tilde leaves are
    decimal-or-null.  q_E is never judged numerically here."""
    if not isinstance(lam, dict):
        errors.append("lambda must be an object")
        return
    na = lam.get("na")
    if na is True:
        main = lam.get("main")
        if not isinstance(main, dict) or any(main.get(k) is not None
                                             for k in ("A", "B", "C", "D")):
            errors.append("lambda.main A..D must be null when lambda.na=true")
        if lam.get("sum") is not None:
            errors.append("lambda.sum must be null when lambda.na=true")
        if lam.get("max_abs_deviation") is not None:
            errors.append("lambda.max_abs_deviation must be null when lambda.na=true")
    elif na is False:
        main = lam.get("main")
        if not isinstance(main, dict) or any(not _is_decimal_prob(main.get(k))
                                             for k in ("A", "B", "C", "D")):
            errors.append("lambda.main A..D must be decimal probabilities when lambda.na=false")
        if not _is_decimal_signed(lam.get("sum")):
            errors.append("lambda.sum must be a signed decimal when lambda.na=false")
        if not _is_decimal_signed(lam.get("max_abs_deviation")):
            errors.append("lambda.max_abs_deviation must be a signed decimal when lambda.na=false")
    else:
        errors.append("lambda.na must be a boolean")
    tilde = lam.get("tilde")
    if not isinstance(tilde, dict):
        errors.append("lambda.tilde must be an object")
    else:
        for k in ("A", "B", "C", "D"):
            v = tilde.get(k)
            if v is not None and not _is_decimal_prob(v):
                errors.append("lambda.tilde.%s must be a decimal probability or null" % k)


def _check_e_kernel(ek, errors):
    """E_kernel block.  e_max_E is optional and may be omitted entirely
    (standard_chain_v1 responses omit it -- V1.0.3)."""
    if not isinstance(ek, dict):
        errors.append("E_kernel must be an object")
        return
    if ek.get("status") not in PROCESS_STATUSES:
        errors.append("E_kernel.status invalid: %r" % ek.get("status"))
    fp = ek.get("free_parameters")
    if not isinstance(fp, list) or any(p not in ("alpha", "beta") for p in fp):
        errors.append("E_kernel.free_parameters must be a list of alpha/beta")
    if not isinstance(ek.get("diagnostics"), dict):
        errors.append("E_kernel.diagnostics must be an object")
    for key in ("alpha_E", "beta_E", "e_max_E"):
        if key in ek:
            v = ek[key]
            if v is None or not _is_decimal_prob(v):
                errors.append("E_kernel.%s must be a decimal probability string when present" % key)


def _check_response(obj, errors, run_id, semantics, scenario_role):
    if not isinstance(obj, dict):
        errors.append("response must be a JSON object")
        return
    if obj.get("schema_version") != SCHEMA_VERSION:
        errors.append("response schema_version must be %r" % SCHEMA_VERSION)
    if obj.get("envelope_type") != "q1_response":
        errors.append("response envelope_type must be q1_response")
    if not _is_str(obj.get("request_id")):
        errors.append("response request_id must be a non-empty string")
    if obj.get("scenario_role") not in SCENARIO_ROLES:
        errors.append("response scenario_role invalid: %r" % obj.get("scenario_role"))
    if obj.get("semantics") not in SEMANTICS:
        errors.append("response semantics invalid: %r" % obj.get("semantics"))
    if obj.get("overall_status") not in OVERALL_STATUSES:
        errors.append("response overall_status invalid: %r" % obj.get("overall_status"))
    if semantics is not None and obj.get("semantics") != semantics:
        errors.append("response semantics %r != leg semantics %r"
                      % (obj.get("semantics"), semantics))
    if scenario_role is not None and obj.get("scenario_role") != scenario_role:
        errors.append("response scenario_role %r != %r"
                      % (obj.get("scenario_role"), scenario_role))
    if run_id is not None and semantics is not None:
        expected = "%s:%s" % (run_id, semantics)
        if obj.get("request_id") != expected:
            errors.append("response request_id %r != %r (cross-leg mixing forbidden)"
                          % (obj.get("request_id"), expected))
    abc = obj.get("abc_kernels")
    if not isinstance(abc, list) or len(abc) != 3:
        errors.append("response abc_kernels must be a 3-item array")
    else:
        for item in abc:
            if not isinstance(item, dict):
                errors.append("abc_kernels item must be an object")
                continue
            if item.get("process_id") not in ("A", "B", "C"):
                errors.append("abc_kernels process_id invalid: %r" % item.get("process_id"))
            if not _is_decimal_prob(item.get("q")):
                errors.append("abc_kernels q must be a decimal probability: %r" % item.get("q"))
            if not _is_decimal_prob(item.get("e")):
                errors.append("abc_kernels e must be a decimal probability: %r" % item.get("e"))
            if item.get("status") not in PROCESS_STATUSES:
                errors.append("abc_kernels status invalid: %r" % item.get("status"))
            if item.get("source") not in ("upstream_bound", "derived"):
                errors.append("abc_kernels source invalid: %r" % item.get("source"))
    status = obj.get("overall_status")
    if status in ("ALL_ROUTES_AGREE", "ROUTE_MISMATCH"):
        for field in ("q_E", "G", "Z_0", "Z_1", "reach_E_distribution", "E_kernel",
                      "E_rates", "fourfold", "anchors", "lambda", "multinomial",
                      "route_agreement", "diagnostics"):
            if field not in obj:
                errors.append("response missing %s for overall_status=%s" % (field, status))
        _check_e_kernel(obj.get("E_kernel"), errors)
        _check_lambda_block(obj.get("lambda"), errors)
        ra = obj.get("route_agreement")
        lam = obj.get("lambda")
        if isinstance(ra, dict) and isinstance(lam, dict) and lam.get("na") is True:
            for key in ("lambda_A", "lambda_B", "lambda_C", "lambda_D"):
                if ra.get(key) is not None:
                    errors.append("route_agreement.%s must be null when lambda.na=true" % key)
    elif status == "HAS_INFEASIBLE":
        if obj.get("infeasible_stage") not in ("ABC_KERNEL", "E_KERNEL"):
            errors.append("response infeasible_stage invalid: %r" % obj.get("infeasible_stage"))
        if not isinstance(obj.get("diagnostics"), dict):
            errors.append("response diagnostics must be an object")
    # NOTE: q_E is deliberately NOT judged here -- no q_E == "0" string check
    # (V1.0.3).  Lexical zero forms ("0", "0.0", "0.00", ...) all pass; the
    # runner never decides anything from q_E numeric content.


def _check_check_report(obj, errors, run_id, semantics):
    if not isinstance(obj, dict):
        errors.append("check_report must be a JSON object")
        return
    if obj.get("schema_version") != SCHEMA_VERSION:
        errors.append("check_report schema_version must be %r" % SCHEMA_VERSION)
    if obj.get("envelope_type") != "q1_check_report":
        errors.append("check_report envelope_type must be q1_check_report")
    if not _is_str(obj.get("request_id")):
        errors.append("check_report request_id must be a non-empty string")
    if obj.get("semantics") not in SEMANTICS:
        errors.append("check_report semantics invalid: %r" % obj.get("semantics"))
    if obj.get("checker_status") not in CHECKER_STATUSES:
        errors.append("check_report checker_status invalid: %r" % obj.get("checker_status"))
    rid = obj.get("report_context_run_id")
    if not (isinstance(rid, str) and RUN_ID_RE.match(rid)):
        errors.append("check_report report_context_run_id invalid: %r" % rid)
    if run_id is not None and semantics is not None:
        if rid != run_id:
            errors.append("check_report report_context_run_id %r != run_id %r" % (rid, run_id))
        expected = "%s:%s" % (run_id, semantics)
        if obj.get("request_id") != expected:
            errors.append("check_report request_id %r != %r" % (obj.get("request_id"), expected))
        if obj.get("semantics") != semantics:
            errors.append("check_report semantics %r != leg semantics %r"
                          % (obj.get("semantics"), semantics))
    fih = obj.get("frozen_input_hashes")
    if not isinstance(fih, dict):
        errors.append("check_report frozen_input_hashes must be an object")
    else:
        if not _is_sha256(fih.get("parameters_sha256")):
            errors.append("check_report frozen_input_hashes.parameters_sha256 invalid")
        if not _is_sha256(fih.get("upstream_sha256")):
            errors.append("check_report frozen_input_hashes.upstream_sha256 invalid")
    items = obj.get("items")
    if not isinstance(items, list):
        errors.append("check_report items must be an array")
    else:
        for it in items:
            if not isinstance(it, dict):
                errors.append("check_report item must be an object")
                continue
            if not _is_str(it.get("quantity")):
                errors.append("check_report item quantity must be a non-empty string")
            if it.get("verdict") not in ("PASS", "FAIL", "NOT_APPLICABLE"):
                errors.append("check_report item verdict invalid: %r" % it.get("verdict"))
    if obj.get("route_table_verdict") not in ("PASS", "FAIL"):
        errors.append("check_report route_table_verdict invalid: %r"
                      % obj.get("route_table_verdict"))


def _check_manifest(obj, errors):
    if not isinstance(obj, dict):
        errors.append("manifest must be a JSON object")
        return
    if obj.get("schema_version") != SCHEMA_VERSION:
        errors.append("manifest schema_version must be %r" % SCHEMA_VERSION)
    if obj.get("envelope_type") != ENVELOPE_MANIFEST:
        errors.append("manifest envelope_type must be %r" % ENVELOPE_MANIFEST)
    rid = obj.get("run_id")
    if not (isinstance(rid, str) and RUN_ID_RE.match(rid)):
        errors.append("manifest run_id invalid: %r" % rid)
    if obj.get("overall_status") not in MANIFEST_STATUSES:
        errors.append("manifest overall_status invalid: %r" % obj.get("overall_status"))
    arts = obj.get("artifacts")
    if not isinstance(arts, list):
        errors.append("manifest artifacts must be an array")
        return
    for art in arts:
        if not isinstance(art, dict):
            errors.append("manifest artifact must be an object")
            continue
        p = art.get("path")
        if not (isinstance(p, str) and p and "\\" not in p
                and not p.startswith("/") and not re.match(r"^[A-Za-z]:", p)
                and ".." not in p.split("/")):
            errors.append("manifest artifact path invalid: %r" % p)
        if not _is_str(art.get("role")):
            errors.append("manifest artifact role invalid: %r" % art.get("role"))
        if not isinstance(art.get("bytes"), int) or art.get("bytes") < 0:
            errors.append("manifest artifact bytes invalid: %r" % art.get("bytes"))
        if not _is_sha256(art.get("sha256")):
            errors.append("manifest artifact sha256 invalid")
        for key in ("source_sha256_before", "source_sha256_after"):
            if key in art and not _is_sha256(art.get(key)):
                errors.append("manifest artifact %s invalid" % key)


def _check_commands(obj, errors):
    if not isinstance(obj, dict):
        errors.append("commands must be a JSON object")
        return
    if obj.get("schema_version") != SCHEMA_VERSION:
        errors.append("commands schema_version must be %r" % SCHEMA_VERSION)
    if obj.get("envelope_type") != ENVELOPE_COMMANDS:
        errors.append("commands envelope_type must be %r" % ENVELOPE_COMMANDS)
    cmds = obj.get("commands")
    if not isinstance(cmds, list):
        errors.append("commands must be an array")
        return
    for i, c in enumerate(cmds):
        if not isinstance(c, dict):
            errors.append("commands[%d] must be an object" % i)
            continue
        if not isinstance(c.get("index"), int):
            errors.append("commands[%d].index invalid" % i)
        if not isinstance(c.get("argv"), list) or not all(isinstance(a, str) for a in c.get("argv")):
            errors.append("commands[%d].argv must be an array of strings" % i)
        if not _is_str(c.get("cwd")):
            errors.append("commands[%d].cwd invalid" % i)
        if not _is_str(c.get("start_utc")) or not _is_str(c.get("end_utc")):
            errors.append("commands[%d] timestamps invalid" % i)
        if not isinstance(c.get("exit_code"), int):
            errors.append("commands[%d].exit_code invalid" % i)
        for key in ("stdout_rel", "stderr_rel"):
            v = c.get(key)
            if v is not None and not _is_str(v):
                errors.append("commands[%d].%s invalid" % (i, key))


def validate_formal_envelope(obj, kind, run_id=None, semantics=None,
                             scenario_role=None):
    """Envelope-level V1.0.3 schema conformance checks for the four formal
    envelope types (q1_response / q1_check_report / q1_run_manifest /
    q1_command_log).

    Structural only: never judges q_E/e/alpha/beta numeric values, never
    recomputes anything, never "corrects" E1/E2 output.  Returns a list of
    error strings (empty == conformant).

    V1.0.3 compatibility:
    * lambda.na=true requires lambda.main A..D, sum, max_abs_deviation and
      route_agreement.lambda_A..D to be null (NA must never be written as 0).
    * q_E is not judged numerically -- no ``q_E == "0"`` string check;
      lexical zero forms ("0", "0.0", "0.00", ...) all pass.
    * E_kernel.e_max_E is optional; standard_chain_v1 responses may omit it.
    """
    errors = []
    if kind == "response":
        _check_response(obj, errors, run_id, semantics, scenario_role)
    elif kind == "check_report":
        _check_check_report(obj, errors, run_id, semantics)
    elif kind == "manifest":
        _check_manifest(obj, errors)
    elif kind == "commands":
        _check_commands(obj, errors)
    else:
        errors.append("unknown envelope kind %r" % kind)
    return errors


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def _run_command(argv, cwd, stdout_rel, stderr_rel, run_root):
    """Execute one frozen child with shell=False; persist raw stdout/stderr."""
    start = utc_now_iso()
    proc = subprocess.run(argv, cwd=cwd, shell=False,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    end = utc_now_iso()
    out_bytes = proc.stdout or b""
    err_bytes = proc.stderr or b""
    write_bytes(os.path.join(run_root, *stdout_rel.split("/")), out_bytes)
    write_bytes(os.path.join(run_root, *stderr_rel.split("/")), err_bytes)
    return {
        "argv": list(argv),
        "cwd": str(cwd),
        "start_utc": start,
        "end_utc": end,
        "exit_code": int(proc.returncode),
        "stdout_rel": stdout_rel,
        "stderr_rel": stderr_rel,
    }


def _child_argv(interpreter, code_rel, run_root, args):
    return [interpreter, os.path.join(run_root, *code_rel.split("/"))] + args


def run_evaluate(commands, run_root, run_id, code_snapshot_hashes=None):
    """Structural evaluation of a completed run: returns (overall_status,
    notes).

    Orchestration-only: command exit codes, response/check_report envelope
    validity (V1.0.3), check_report checker_status == "PASS", artifact
    presence and E2 preflight-failure detection.  Never judges numeric
    content, never modifies any E1/E2 output.
    """
    notes = []
    all_exit_zero = all(c.get("exit_code") == 0 for c in commands)
    reports_ok = True
    responses_ok = True
    preflight_failed = False
    for sem in SEMANTICS:
        rp = os.path.join(run_root, sem, "response.json")
        if os.path.isfile(rp):
            try:
                with open(rp, "r", encoding="utf-8") as f:
                    resp = json.load(f)
            except (OSError, ValueError) as exc:
                notes.append("unreadable response %s: %s" % (sem, exc))
                responses_ok = False
            else:
                errs = validate_formal_envelope(
                    resp, "response", run_id=run_id, semantics=sem,
                    scenario_role="canonical_g2_02")
                if errs:
                    notes.append("response %s schema invalid: %s" % (sem, "; ".join(errs)))
                    responses_ok = False
        else:
            notes.append("missing response for %s" % sem)
            responses_ok = False
        cr = os.path.join(run_root, sem, "check_report.json")
        if os.path.isfile(cr):
            try:
                with open(cr, "r", encoding="utf-8") as f:
                    rep = json.load(f)
            except (OSError, ValueError) as exc:
                notes.append("unreadable check_report %s: %s" % (sem, exc))
                reports_ok = False
            else:
                errs = validate_formal_envelope(
                    rep, "check_report", run_id=run_id, semantics=sem)
                if errs:
                    notes.append("check_report %s schema invalid: %s"
                                 % (sem, "; ".join(errs)))
                    reports_ok = False
                elif rep.get("checker_status") != "PASS":
                    notes.append("check_report %s checker_status=%r (expected PASS)"
                                 % (sem, rep.get("checker_status")))
                    reports_ok = False
        else:
            notes.append("missing check_report for %s" % sem)
            reports_ok = False
    # E2 preflight failure (exit 2, no report) is a legal failure shape
    for sem, c in zip(SEMANTICS, commands[1::2]):
        if c.get("exit_code") == 2 and not os.path.isfile(
                os.path.join(run_root, sem, "check_report.json")):
            preflight_failed = True
            notes.append("REPORT_CONTEXT_PREFLIGHT_FAILED for %s (E2 exit 2, no report)" % sem)
    artifacts = collect_artifacts(run_root, code_snapshot_hashes)
    layout_rel = [rel for rel, _ in ARTIFACT_LAYOUT]
    all_artifacts_present = all(
        os.path.isfile(os.path.join(run_root, *rel.split("/"))) for rel in layout_rel
    )
    if (all_exit_zero and reports_ok and responses_ok and all_artifacts_present
            and not preflight_failed and not notes):
        overall_status = "PASS"
    elif all_artifacts_present and not preflight_failed:
        overall_status = "FAIL"
    else:
        overall_status = "INCOMPLETE"
    if not notes and overall_status != "PASS":
        notes.append("evidence package incomplete for %s" % overall_status)
    return overall_status, notes


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="run_g2_02_v1",
        description="G2-02 L1 evidence runner (frozen E1/E2 orchestration only)",
        allow_abbrev=False,
    )
    parser.add_argument("--parameters", required=True)
    parser.add_argument("--task-package", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--upstream-run-root", required=True)
    parser.add_argument("--output-root", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 2

    output_root = os.path.abspath(args.output_root)
    try:
        os.makedirs(output_root, exist_ok=True)
    except OSError as exc:
        sys.stderr.write("runner IO failure: %s\n" % exc)
        return 1

    # ---- task package: version + frozen_sha256 ----
    try:
        tp_text = read_text(args.task_package)
    except OSError as exc:
        sys.stderr.write("runner IO failure reading task package: %s\n" % exc)
        return 1
    frozen_sha256 = extract_frozen_sha256(tp_text)

    # ---- upstream run id ----
    upstream_root_abs = os.path.abspath(args.upstream_run_root)
    upstream_dir_name = os.path.basename(os.path.normpath(upstream_root_abs))
    if not upstream_dir_name.startswith(UPSTREAM_RUN_ROOT_PREFIX):
        sys.stderr.write("runner: --upstream-run-root must be a run_<run_id> directory\n")
        return 1
    upstream_run_id = upstream_dir_name[len(UPSTREAM_RUN_ROOT_PREFIX):]
    if not is_valid_run_id(upstream_run_id):
        sys.stderr.write("runner: invalid upstream run id %r\n" % upstream_run_id)
        return 1

    # ---- run id (collision => fail, never overwrite) ----
    run_id = _generate_run_id()
    try:
        run_root = ensure_run_dir_absent(output_root, run_id)
    except RunnerError as exc:
        sys.stderr.write("runner failure: %s\n" % exc)
        return 1
    os.makedirs(run_root)
    for _rel in ("frozen", "frozen/upstream", "frozen/code"):
        os.makedirs(os.path.join(run_root, *(_rel.split("/"))), exist_ok=True)
    for _sem in SEMANTICS:
        os.makedirs(os.path.join(run_root, "frozen", "upstream", _sem), exist_ok=True)
        os.makedirs(os.path.join(run_root, _sem), exist_ok=True)

    notes = []
    overall_status = "INCOMPLETE"
    hash_mismatch = False

    # ---- V1.0.3 binding checks: spec version + frozen schema/fixture SHAs ----
    freeze_errors = check_spec_bindings(tp_text, frozen_sha256)
    if freeze_errors:
        hash_mismatch = True

    # ---- freeze inputs (hash verification before any child starts) ----
    for name, rel, sha_key in FROZEN_INPUTS:
        src = {"parameters": args.parameters, "task_package": args.task_package,
               "schema": args.schema, "fixture": args.fixture}[name]
        dst = os.path.join(run_root, *rel.split("/"))
        try:
            shutil.copyfile(src, dst)
        except OSError as exc:
            freeze_errors.append("%s: %s" % (name, exc))
            continue
        if sha_key and sha_key in frozen_sha256:
            h = sha256_file(dst)
            if h != frozen_sha256[sha_key]:
                freeze_errors.append(
                    "%s SHA-256 %s != frozen_sha256.%s %s" % (name, h, sha_key, frozen_sha256[sha_key]))
                hash_mismatch = True
    upstream_files = {}
    upstream_short = {SEMANTICS[0]: "single", SEMANTICS[1]: "chain"}
    for sem in SEMANTICS:
        src = os.path.join(upstream_root_abs, sem, "response.json")
        dst = os.path.join(run_root, "frozen", "upstream", sem, "response.json")
        try:
            shutil.copyfile(src, dst)
        except OSError as exc:
            freeze_errors.append("upstream %s: %s" % (sem, exc))
            continue
        h = sha256_file(dst)
        upstream_files[sem] = h
        expected_key = "upstream_%s_response" % upstream_short[sem]
        if expected_key in frozen_sha256 and h != frozen_sha256[expected_key]:
            freeze_errors.append(
                "upstream %s SHA-256 %s != frozen_sha256.%s %s"
                % (sem, h, expected_key, frozen_sha256[expected_key]))
            hash_mismatch = True
    src_fh = os.path.join(upstream_root_abs, "file_hashes.sha256")
    dst_fh = os.path.join(run_root, "frozen", "upstream", "file_hashes.sha256")
    try:
        shutil.copyfile(src_fh, dst_fh)
    except OSError as exc:
        freeze_errors.append("upstream file_hashes.sha256: %s" % exc)
    else:
        h = sha256_file(dst_fh)
        if "upstream_file_hashes" in frozen_sha256 and h != frozen_sha256["upstream_file_hashes"]:
            freeze_errors.append(
                "upstream file_hashes.sha256 SHA-256 %s != frozen_sha256.upstream_file_hashes %s"
                % (h, frozen_sha256["upstream_file_hashes"]))
            hash_mismatch = True

    code_snapshot_hashes = {}
    if not freeze_errors:
        # ---- snapshot the nine code/test files (hash-before=snapshot=after) ----
        for rel, _role in CODE_SNAPSHOTS:
            src = code_source_path(rel)
            dst = os.path.join(run_root, "frozen", "code", *rel.split("/"))
            try:
                before, snap, after = snapshot_code(src, dst)
            except (OSError, RunnerError) as exc:
                freeze_errors.append("code snapshot %s: %s" % (rel, exc))
                break
            code_snapshot_hashes["frozen/code/" + posix_rel(rel)] = (before, snap, after)

    if freeze_errors:
        notes = freeze_errors
        overall_status = "FAIL" if hash_mismatch else "INCOMPLETE"
    else:
        # ---- canonical requests ----
        for sem in SEMANTICS:
            req = build_request(run_id, sem, upstream_run_id,
                                "frozen/upstream/%s/response.json" % sem,
                                upstream_files[sem], sem)
            write_json(os.path.join(run_root, sem, "request.json"), req)

        # ---- frozen child commands (E1 single, E2 single, E1 chain, E2 chain) ----
        interpreter = sys.executable
        commands = []
        for sem in SEMANTICS:
            e1_argv = _child_argv(interpreter, "frozen/code/04_代码/main_model/q1_quality_v1.py",
                                  run_root, [
                                      "--request", os.path.join(run_root, sem, "request.json"),
                                      "--parameters", os.path.join(run_root, "frozen", "parameters.csv"),
                                      "--upstream", os.path.join(run_root, "frozen", "upstream", sem, "response.json"),
                                      "--schema", os.path.join(run_root, "frozen", "q1_quality_v1.schema.json"),
                                      "--output", os.path.join(run_root, sem, "response.json"),
                                  ])
            commands.append(_run_command(e1_argv, run_root,
                                         "%s/e1.stdout.txt" % sem, "%s/e1.stderr.txt" % sem, run_root))
            e2_argv = _child_argv(interpreter, "frozen/code/04_代码/checker/q1_quality_checker_v1.py",
                                  run_root, [
                                      "--response", os.path.join(run_root, sem, "response.json"),
                                      "--parameters", os.path.join(run_root, "frozen", "parameters.csv"),
                                      "--upstream", os.path.join(run_root, "frozen", "upstream", sem, "response.json"),
                                      "--schema", os.path.join(run_root, "frozen", "q1_quality_v1.schema.json"),
                                      "--task-package", os.path.join(run_root, "frozen", "G2-02_Q1概率与质量解析链.yaml"),
                                      "--report", os.path.join(run_root, sem, "check_report.json"),
                                  ])
            commands.append(_run_command(e2_argv, run_root,
                                         "%s/e2.stdout.txt" % sem, "%s/e2.stderr.txt" % sem, run_root))
        # commandLogEnvelope requires an "index" per command entry (frozen order)
        for _i, _c in enumerate(commands):
            _c["index"] = _i

        cmds_env = build_commands(commands)
        write_json(os.path.join(run_root, "commands.json"), cmds_env)

        # ---- structural evaluation (V1.0.3 envelope validation included) ----
        overall_status, notes = run_evaluate(commands, run_root, run_id,
                                             code_snapshot_hashes)
        self_errs = validate_formal_envelope(cmds_env, "commands")
        if self_errs:
            notes.append("runner-internal commands envelope invalid: %s" % "; ".join(self_errs))
            if overall_status == "PASS":
                overall_status = "FAIL"

    artifacts = collect_artifacts(run_root, code_snapshot_hashes)
    manifest = build_manifest(run_id, overall_status, artifacts, notes)
    self_errs = validate_formal_envelope(manifest, "manifest")
    if self_errs:
        notes.append("runner-internal manifest envelope invalid: %s" % "; ".join(self_errs))
        overall_status = "FAIL"
        manifest = build_manifest(run_id, overall_status, artifacts, notes)
    write_json(os.path.join(run_root, "run_manifest.json"), manifest)
    inventory = hash_inventory_lines(run_root)
    with open(os.path.join(run_root, "file_hashes.sha256"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write(inventory)

    print("runner run_id=%s overall_status=%s root=%s" % (run_id, overall_status, run_root))
    if overall_status == "PASS":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
