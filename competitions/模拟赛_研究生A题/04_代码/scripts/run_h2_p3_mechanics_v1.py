#!/usr/bin/env python3
"""Q3-H2-P3-A evidence runner: decision-point mechanics, action
semantics, rollout seed + CRN, continuation-world rebuild, C23 end-to-end
mechanics, H1 parity.

Runs:
  * independent P3-A mechanics checker (h2_p3_mechanics_checker_v1):
    DECISION_POINT_CLASSIFICATION, CANONICAL_ORDERING, ROLLOUT_SEED,
    CRN_SAME_WORLD_ACROSS_ACTIONS, C23_MECHANICS, H1_PARITY;
  * P3-A unit tests (test_h2_p3_mechanics_v1.py);
  * deterministic regressions (P1 firewall / Density E2 / key_schema /
    Q3 H1 / G3 random DES);
  * C23 mechanics (hidden-world variants -> identical ObservableState /
    PosteriorState / decision points / dp / rollout keys);
then writes an immutable evidence root with the acyclic hash DAG,
semantic evidence mapping and fail-closed verification (verified staging
promoted byte-identical to the final root; post-promotion read-only
re-verify).

P3-A scope (authorized by Human Gate at a5d2faf): decision-point
reconstruction & canonical ordering; legal action set; START_HEAD /
H1_NOOP / WAIT_EVENT / PM_WITH_HEAD / PM_IDLE continuation semantics;
rollout_seed(dp, m) + h2_rollout substream; continuation world rebuild
from ObservableState + PosteriorState + rollout post keys; C23
same-observed-history end-to-end mechanics; independent checker +
deterministic toy tests.

NOT AUTHORIZED in P3-A: M*/C_eval* selection, deviation threshold tuning,
action stability (b)/(c), cross-K transfer, h2_holdout, C25, paper H2
numbers.  No stochastic rollout is executed; the P3-A smoke is
deterministic only.

Evidence root: 05_结果/H2/p3/mechanics/run_<UTC>_<8hex>/

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
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from scripts import run_q3_h1_formal_v1 as frm  # noqa: E402
from main_model.h2 import frozen_params_v1 as fp  # noqa: E402
from main_model.h2 import decision_point_v1 as dp  # noqa: E402
from main_model.h2 import action_semantics_v1 as asem  # noqa: E402
from main_model.h2 import rollout_seed_v1 as rs  # noqa: E402
from main_model.h2 import continuation_v1 as cont  # noqa: E402
from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from checker import h2_p3_mechanics_checker_v1 as chk  # noqa: E402

PACKAGE_REF = "Q3-H2-P3-A"
BOOTSTRAP_SPEC_FILE = frm.BOOTSTRAP_SPEC_FILE
FORMAL_TASK_PACKAGE_FILE = frm.TASK_PACKAGE_FILE
FORMAL_TASK_PACKAGE_SHA = frm.TASK_PACKAGE_SNAPSHOT_SHA
REGISTRY_VERSION = "CR-V3.1"

SCOPE_AUDIT = {
    "decision_point_reconstruction": "YES (SPEC sections 2/5/10/11/12)",
    "canonical_ordering": "YES (A/B/C/E, at most one point per "
                          "(resource, closure), dp 0-based pure function)",
    "legal_action_set": "YES (START_HEAD / H1_NOOP / WAIT_EVENT / "
                        "PM_WITH_HEAD / PM_IDLE)",
    "continuation_semantics": "YES (pure continuation-step functions; "
                              "WAIT anchored to a finite scheduled "
                              "same-device event; STRICT/BOUNDARY; "
                              "mandatory/exact_240 never policy choices)",
    "rollout_seed": "YES (SPEC section 6.2 formula; seed does not contain "
                    "action/policy/strategy/run_id -> CRN across actions)",
    "continuation_world": "YES (rebuild from ObservableState + "
                          "PosteriorState + rollout post keys only)",
    "c23_end_to_end_mechanics": "YES (hidden-world variants -> identical "
                                "observable/posterior/decision points/dp/"
                                "rollout keys); full production C23 "
                                "PENDING UNTIL FINAL POLICY CONFIG",
    "m_star_selection": "NO", "c_eval_selection": "NO",
    "deviation_threshold_tuning": "NO", "action_stability": "NO",
    "cross_k_transfer": "NO", "h2_holdout": "NOT USED",
    "c25": "NO", "paper_h2_numbers": "NO",
    "stochastic_rollout_executed": "NO (P3-A smoke is deterministic only)",
    "random_streams": {
        "namespace": "h2_rollout (rollout_seed formula only; no key "
                     "consumption in P3-A)",
        "master_seed": 6, "replicate_ids": "validation toy (0..4)",
        "h2_holdout_used": False, "q3_formal_used": False,
        "u_y_post_used": False,
    },
    "p2_math_modified": "NO",
}

REGRESSION_PATTERNS = (
    "test_h2_p1_firewall_v1.py",
    "test_h2_q3_density_v1.py",
    "test_g3_key_schema_v1.py",
    "test_q3_h1_formal_v1.py",
    "test_g3_random_des_v1.py",
)

REPORT_MAPPING: dict[str, str] = {
    "DECISION_POINT_CLASSIFICATION": "decision_point_classification_report.json",
    "CANONICAL_ORDERING": "canonical_ordering_report.json",
    "ROLLOUT_SEED": "rollout_seed_report.json",
    "CRN_SAME_WORLD_ACROSS_ACTIONS": "crn_report.json",
    "C23_MECHANICS": "c23_mechanics_report.json",
    "H1_PARITY": "h1_parity_report.json",
    "CONTINUATION_WORLD_SMOKE": "continuation_world_smoke_report.json",
    "ACTION_SEMANTICS_SMOKE": "action_semantics_smoke_report.json",
    "TOY_LOG_SUMMARY": "toy_log_summary_report.json",
    "EVIDENCE_SEMANTIC_MAPPING": "evidence_semantic_mapping_report.json",
}


def continuation_world_smoke() -> dict[str, Any]:
    """Deterministic smoke: rebuild a continuation world from a toy log's
    ObservableState + PosteriorState + provided post draws; assert the
    world contains only the sampled hidden state / lifetimes and that
    rebuilding twice with the same draws is identical (determinism), and
    that hidden-world variants leave the world unchanged."""
    log, K, tend = (chk._toy_logs()[0][1], chk._toy_logs()[0][2],
                    chk._toy_logs()[0][3])
    st = obs.project_log_prefix(log, Fraction(0), batch_size=2)
    post = ps.PosteriorState.from_observable(st)
    draws = {"u_x": Fraction(1, 3), "u_d": Fraction(1, 2),
             "u_l": {r: Fraction(1, 4) for r in fp.RESOURCES}}
    w1 = cont.rebuild_continuation_world(
        st, post, draws["u_x"], draws["u_d"], draws["u_l"])
    w2 = cont.rebuild_continuation_world(
        st, post, draws["u_x"], draws["u_d"], draws["u_l"])
    same = (w1.decision_time == w2.decision_time
            and w1.devices == w2.devices
            and w1.residual_lifetimes == w2.residual_lifetimes)
    # hidden-world variants (true_state differs) -> same rebuilt world
    variants_ok = True
    for mut in (lambda r: r.update(true_state={"A": True, "B": True,
                                               "C": True}),
                lambda r: r.update(lifetime_h="999"),
                lambda r: r.update(u="0.999")):
        vlog = [dict(r) for r in log]
        for r in vlog:
            mut(r)
        sv = obs.project_log_prefix(vlog, Fraction(0), batch_size=2)
        if sv.fingerprint() != st.fingerprint():
            variants_ok = False
            continue
        postv = ps.PosteriorState.from_observable(sv)
        wv = cont.rebuild_continuation_world(
            sv, postv, draws["u_x"], draws["u_d"], draws["u_l"])
        if not (wv.devices == w1.devices
                and wv.residual_lifetimes == w1.residual_lifetimes):
            variants_ok = False
    ok = same and variants_ok and len(w1.devices) >= 1
    return {
        "check": "CONTINUATION_WORLD_SMOKE",
        "status": "PASS" if ok else "FAIL",
        "decision_time": str(w1.decision_time),
        "n_devices": len(w1.devices),
        "n_resources_with_lifetime": len(w1.residual_lifetimes),
        "deterministic_rebuild": same,
        "hidden_variants_identical_world": variants_ok,
        "note": "pure-function rebuild; no live-DES objects; no hidden "
                "fields read (C23)",
    }


def action_semantics_smoke() -> dict[str, Any]:
    """Deterministic smoke over the five action continuations: verify the
    emitted records' fields and next times."""
    failures: list[str] = []
    # START_HEAD
    s = asem.apply_start_head((1, "B", 1), Fraction(0))
    if s.next_time != Fraction(2) or not s.events:
        failures.append("START_HEAD next_time/events")
    rec = s.events[0]
    if not (rec["event_type"] == "ACTIVITY_START"
            and rec["device_id"] == 1 and rec["process"] == "B"
            and rec["attempt_end_time"] == "2"):
        failures.append("START_HEAD record fields")
    # H1_NOOP
    n = asem.apply_h1_noop(Fraction(1), Fraction(7))
    if n.next_time != Fraction(7) or n.events != ():
        failures.append("H1_NOOP next_time/events")
    # WAIT_EVENT (STRICT and BOUNDARY both advance to the anchor)
    w = asem.apply_wait_event(Fraction(5, 2), Fraction(1))
    if w.next_time != Fraction(5, 2) or w.events != ():
        failures.append("WAIT_EVENT advance")
    try:
        asem.apply_wait_event(Fraction(1), Fraction(1))
        failures.append("WAIT_EVENT must reject non-future anchor")
    except ValueError:
        pass
    # PM_WITH_HEAD / PM_IDLE
    p = asem.apply_pm("A", Fraction(0), dp.A_PM_WITH_HEAD, generation=1)
    if p.next_time != Fraction(1, 2):
        failures.append("PM next_time (calibration 30 min)")
    if len(p.events) != 2:
        failures.append("PM must emit replacement-start + calibration-complete")
    for e in p.events:
        if e["event_type"] not in ("EQUIPMENT_REPLACEMENT_START",
                                   "EQUIPMENT_CALIBRATION_COMPLETE"):
            failures.append("PM unexpected event type")
    p2 = asem.apply_pm("B", Fraction(0), dp.A_PM_IDLE, generation=2)
    if p2.next_time != Fraction(1, 3):
        failures.append("PM B next_time (calibration 20 min)")
    return {
        "check": "ACTION_SEMANTICS_SMOKE",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def toy_log_summary() -> dict[str, Any]:
    """Record the toy logs' reconstructed decision points (evidence of a
    NON-VACUOUS checker: real dispatch/maintenance points exist)."""
    rows = []
    for label, log, K, tend in chk._toy_logs():
        pts = dp.reconstruct_decision_points(log, K, batch_size=2,
                                             t_end=tend)
        rows.append({
            "label": label, "K": str(K), "t_end": str(tend),
            "n_points": len(pts),
            "points": [p.to_canonical_dict() for p in pts]})
    return {"check": "TOY_LOG_SUMMARY", "status": "PASS",
            "note": "evidence that the checker exercised REAL points",
            "rows": rows}


def c23_mechanics() -> dict[str, Any]:
    """C23 end-to-end mechanics (delegates to the independent checker)."""
    return chk.check_c23_mechanics()


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
        "log_tail": buf.getvalue()[-1500:],
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


def evidence_mapping_check(evidence_dir: Path) -> dict[str, Any]:
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
    return {"check": "EVIDENCE_SEMANTIC_MAPPING",
            "status": "PASS" if ok else "FAIL", "files": results}


def _verify(out_dir: Path) -> dict[str, Any]:
    try:
        dag = frm.verify_hash_dag(out_dir)
        cons = frm.verify_manifest_inventory_consistency(out_dir)
        mapping = evidence_mapping_check(out_dir)
        ok = (dag["hash_graph_acyclic"] is True and dag["mismatches"] == 0
              and "PASS" in cons["manifest_output_hashes"]
              and "PASS" in cons["manifest_inventory_crosscheck"]
              and cons["c21_report_sha_consistency"] == "PASS"
              and mapping["status"] == "PASS")
        return {"ok": ok, "hash_graph_acyclic": dag["hash_graph_acyclic"],
                "inventory_n": dag["inventory_n"], "mismatches": dag["mismatches"],
                "manifest_output_hashes": cons["manifest_output_hashes"],
                "manifest_inventory_crosscheck": cons["manifest_inventory_crosscheck"],
                "c21_report_sha_consistency": cons["c21_report_sha_consistency"],
                "evidence_semantic_mapping": mapping["status"],
                "detail": {"dag": dag, "consistency": cons, "mapping": mapping}}
    except AssertionError as exc:
        return {"ok": False, "error": f"AssertionError: {exc}"}


def _build_evidence(out_dir: Path, run_id: str, checks: dict[str, Any],
                    test_report: dict[str, Any],
                    regressions: list[dict[str, Any]],
                    verification: Optional[dict[str, Any]],
                    wall_total: float) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_bytes = Path(BOOTSTRAP_SPEC_FILE).read_bytes()
    spec_sha = _sha256_bytes(spec_bytes)
    (out_dir / "bootstrap_spec_snapshot.md").write_bytes(spec_bytes)
    (out_dir / "task_package_snapshot.yaml").write_text(
        "# Q3-H2-P3-A task-package snapshot\n"
        f"package_ref: {PACKAGE_REF}\n"
        "authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED "
        "sections 2/5/6.2/7/8/9/10/11/12 + Q3-H2-P3-A Human Gate "
        "authorization (P2 FINAL PASS/ACCEPTED at a5d2faf)\n"
        f"bootstrap_spec_snapshot: bootstrap_spec_snapshot.md\n"
        f"bootstrap_spec_sha256: {spec_sha}\n"
        f"formal_task_package_sha256: {FORMAL_TASK_PACKAGE_SHA}\n"
        "p1: FINAL PASS / ACCEPTED (08488e4)\n"
        "p2: FINAL PASS / ACCEPTED (a5d2faf)\n"
        "p3: NOT AUTHORIZED beyond P3-A mechanics; M*/C_eval*/tuning/"
        "stability/cross-K/holdout/C25 NOT AUTHORIZED\n"
        "evidence_rule: ACYCLIC hash DAG (RULE A)\n",
        encoding="utf-8", newline="\n")
    _dump_json(out_dir / "commands.json", {
        "run_id": run_id,
        "command": "python 04_代码/scripts/run_h2_p3_mechanics_v1.py",
        "wall_clock_s": round(wall_total, 2)})
    _dump_json(out_dir / "environment.json", frm._env_summary())
    _dump_json(out_dir / "scope_audit.json", SCOPE_AUDIT)
    _dump_json(out_dir / "test_report.json", test_report)
    _dump_json(out_dir / "regression_report.json", {
        "regressions": regressions,
        "note": "deterministic suites; commands/exit codes/test counts "
                "truthfully recorded"})
    for check in checks["checks"]:
        fname = REPORT_MAPPING.get(check["check"])
        if fname is not None:
            _dump_json(out_dir / fname, check)
    mapping_result = evidence_mapping_check(out_dir)
    _dump_json(out_dir / "evidence_semantic_mapping_report.json", mapping_result)
    # dev budget ledger snapshot: current append-only ledger state
    ledger_path = BASE_DIR / "05_结果" / "H2" / "dev_budget_ledger.json"
    if ledger_path.is_file():
        _dump_json(out_dir / "dev_budget_ledger_snapshot.json",
                   json.loads(ledger_path.read_text(encoding="utf-8")))

    hashes = {
        "task_package_snapshot": _sha256_file(out_dir / "task_package_snapshot.yaml"),
        "bootstrap_spec": spec_sha,
        "formal_task_package": _sha256_file(FORMAL_TASK_PACKAGE_FILE),
        "frozen_params": _sha256_file(MAIN_MODEL / "h2" / "frozen_params_v1.py"),
        "observable_state": _sha256_file(MAIN_MODEL / "h2" / "observable_state_v1.py"),
        "posterior_state": _sha256_file(MAIN_MODEL / "h2" / "posterior_state_v1.py"),
        "decision_point": _sha256_file(MAIN_MODEL / "h2" / "decision_point_v1.py"),
        "action_semantics": _sha256_file(MAIN_MODEL / "h2" / "action_semantics_v1.py"),
        "rollout_seed": _sha256_file(MAIN_MODEL / "h2" / "rollout_seed_v1.py"),
        "continuation": _sha256_file(MAIN_MODEL / "h2" / "continuation_v1.py"),
        "p3_checker": _sha256_file(CODE_DIR / "checker" / "h2_p3_mechanics_checker_v1.py"),
        "tests": _sha256_file(CODE_DIR / "tests" / "test_h2_p3_mechanics_v1.py"),
        "runner": _sha256_file(Path(__file__).resolve()),
        "key_schema": _sha256_file(MAIN_MODEL / "g3" / "key_schema_v1.py"),
        "engine": _sha256_file(MAIN_MODEL / "g3" / "random_des_v1.py"),
        "problem_contract": _sha256_file(frm.PROBLEM_CONTRACT_FILE),
        "parameters_csv": _sha256_file(frm.PARAMETERS_CSV),
        "registry": _sha256_file(BASE_DIR / "01_审计" / "检查注册表_V3.1.md"),
    }
    _dump_json(out_dir / "input_hashes.json", hashes)

    verify_ok = verification is not None and verification.get("ok") is True
    c21a = ("PASS" if verify_ok else
            ("PENDING_PROBE" if verification is None else "FAIL"))
    overall_ok = (checks["overall"] == "PASS"
                  and test_report["ok"]
                  and all(r["ok"] for r in regressions)
                  and verify_ok)
    _dump_json(out_dir / "C21_REQUALIFICATION_REPORT.json", {
        "run_id": run_id, "check_id": "CR-V3.1/C21",
        "scope": "Q3-H2-P3-A mechanics evidence root",
        "status": "PASS" if overall_ok else "FAIL",
        "verification": verification,
        "items": [
            {"id": "C21a", "status": c21a,
             "note": "acyclic hash inventory (RULE A); status from actual "
                     "verifier"},
            {"id": "C21b", "status": c21a,
             "note": "manifest/inventory/actual SHA consistency; status "
                     "from actual verifier"},
            {"id": "C21c", "status": "PASS" if overall_ok else "FAIL",
             "note": "P3-A mechanics checker + tests + regressions"}]})
    _dump_json(out_dir / "checks.json", {
        "run_id": run_id, "registry_version": REGISTRY_VERSION,
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
                "evidence_semantic_mapping") if verification else None},
        "items": [
            {"check_id": c["check"], "status": c["status"]}
            for c in checks["checks"]] +
            [{"check_id": "TESTS", "status": "PASS" if test_report["ok"]
              else "FAIL",
              "count": f"{test_report['tests_run'] - test_report['failures'] - test_report['errors']}"
                       f"/{test_report['tests_run']}"},
             {"check_id": "REGRESSIONS", "status": "PASS" if all(
                 r["ok"] for r in regressions) else "FAIL",
              "detail": [{"pattern": r["command"].split("'")[1],
                          "exit_code": r["exit_code"],
                          "tests_run": r["tests_run"]} for r in regressions]},
             {"check_id": "CR-V3.1/C21", "status": "PASS" if overall_ok
              else "FAIL",
              "note": "acyclic hash inventory + manifest/inventory "
                      "consistency (fail-closed)"}]})

    artifacts = [
        {"path": p.relative_to(out_dir).as_posix(),
         "bytes": p.stat().st_size, "sha256": _sha256_file(p)}
        for p in sorted(out_dir.rglob("*"))
        if p.is_file() and p.name != "file_hashes.sha256"]
    _dump_json(out_dir / "run_manifest.json", {
        "run_id": run_id, "created_at": _utc_now(), "gate": "Q3",
        "purpose": "h2_p3_mechanics", "formal": True,
        "label": "Q3-H2-P3-A decision mechanics and rollout foundation",
        "paper_authoritative": False,
        "task_package_ref": PACKAGE_REF,
        "task_package_snapshot_path": "task_package_snapshot.yaml",
        "bootstrap_spec_sha256": spec_sha,
        "formal_task_package_sha256": FORMAL_TASK_PACKAGE_SHA,
        "registry_version": REGISTRY_VERSION,
        "hash_inventory_path": "file_hashes.sha256",
        "hash_inventory_rule": (
            "ACYCLIC DAG (RULE A): run_manifest does not hash "
            "file_hashes.sha256; file_hashes covers all artifacts incl. "
            "run_manifest and task_package_snapshot, never itself."),
        "random_domain": {
            "namespace": "h2_rollout (rollout_seed formula only; P3-A "
                         "executes no stochastic rollout / no key "
                         "consumption)",
            "master_seed": 6,
            "replicate_ids": [0, 1, 2, 3, 4],
            "h2_holdout_used": False,
            "q3_formal_used": False,
            "U_Y_post_used": False,
            "new_random_keys_outside_frozen_p2_domain": "NO",
        },
        "p1": "FINAL PASS / ACCEPTED (08488e4)",
        "p2": "FINAL PASS / ACCEPTED (a5d2faf)",
        "p3": {"p3a_mechanics": "implemented (SPEC 2/5/6.2/10/11/12)",
               "p3_tuning": "NOT AUTHORIZED",
               "c23_full_end_to_end": "PENDING UNTIL FINAL POLICY CONFIG"},
        "c25": "NOT AUTHORIZED",
        "verification_fail_closed": (
            verification if verification is not None else "PROBE_PHASE"),
        "overall_status": "PASS" if overall_ok else "FAIL",
        "environment": frm._env_summary(), "outputs": artifacts,
        "check_report_paths": [
            "checks.json", "decision_point_classification_report.json",
            "canonical_ordering_report.json", "rollout_seed_report.json",
            "crn_report.json", "c23_mechanics_report.json",
            "h1_parity_report.json", "continuation_world_smoke_report.json",
            "action_semantics_smoke_report.json",
            "toy_log_summary_report.json", "regression_report.json",
            "test_report.json", "scope_audit.json",
            "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "Q3-H2-P3-A：决策点重建 + canonical ordering + 五动作续演语义 "
            "+ rollout_seed(dp,m)/CRN + continuation world 重建 + C23 "
            "end-to-end mechanics + 独立 checker + deterministic toy tests。",
            "P3-A 为纯机制/确定性范围，不执行随机 rollout；M*/C_eval* / "
            "deviation tuning / action stability / cross-K / h2_holdout / "
            "C25 / 论文数字均 NOT AUTHORIZED。",
            "C23 措辞：本包只声明 C23 END-TO-END MECHANICS PASS；full "
            "production C23 PENDING UNTIL FINAL POLICY CONFIG。",
            "C21 fail-closed + semantic evidence mapping。"],
    })

    lines = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "file_hashes.sha256":
            rel = path.relative_to(out_dir).as_posix()
            lines.append(f"{_sha256_file(path)}  {rel}")
    (out_dir / "file_hashes.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _promote(staging: Path, final: Path) -> dict[str, Any]:
    if final.exists():
        shutil.rmtree(final)
    shutil.copytree(staging, final)
    mismatches = []
    for p in sorted(staging.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(staging)
        q = final / rel
        if not q.is_file() or _sha256_file(p) != _sha256_file(q):
            mismatches.append(rel.as_posix())
    return {"ok": len(mismatches) == 0,
            "files_copied": sum(1 for p in staging.rglob("*") if p.is_file()),
            "sha_mismatches": mismatches}


def main(argv: Optional[list[str]] = None) -> int:
    output_root = BASE_DIR / "05_结果" / "H2" / "p3" / "mechanics"
    run_id = _new_run_id()
    final_dir = output_root / f"run_{run_id}"
    staging_dir = BASE_DIR / ".." / "tmp" / f"p3_staging_{run_id}"
    print(f"[p3a] run_id={run_id}")
    t0 = time.perf_counter()
    checks = {
        "overall": "PASS",
        "checks": [
            chk.check_decision_points(),
            chk.check_ordering(),
            chk.check_rollout_seed(),
            chk.check_crn(),
            chk.check_c23_mechanics(),
            chk.check_h1_parity(),
            continuation_world_smoke(),
            action_semantics_smoke(),
            toy_log_summary(),
        ]}
    checks["overall"] = ("PASS" if all(c["status"] == "PASS"
                                       for c in checks["checks"]) else "FAIL")
    test_report = _run_suite("test_h2_p3_mechanics_v1.py")
    regressions = [_run_suite(p) for p in REGRESSION_PATTERNS]
    wall_total = time.perf_counter() - t0
    # ---- dev budget ledger (F2): append this run's entry; snapshot ----
    ledger_path = BASE_DIR / "05_结果" / "H2" / "dev_budget_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry_ids = {e.get("entry_id") for e in ledger["entries"]}
    p3a_entry_id = f"P3-A-{run_id}"
    if p3a_entry_id not in entry_ids:
        ledger["entries"].append({
            "entry_id": p3a_entry_id,
            "task": "Q3-H2-P3-A decision mechanics / rollout foundation",
            "run_id": run_id,
            "wall_clock_s": round(wall_total, 4),
            "status": "COMPLETED / AWAITING HUMAN GATE P3-A REVIEW",
            "category": "P3-A mechanics (deterministic; no stochastic "
                        "rollout)",
            "namespace": "h2_rollout (formula only)",
            "note": "decision points / actions / rollout_seed / CRN / "
                    "continuation world / C23 mechanics / H1 parity",
            "date": "2026-08-16"})
    ledger["cumulative_wall_clock_s"] = round(
        sum(e["wall_clock_s"] for e in ledger["entries"]), 4)
    ledger["cumulative_wall_clock_h"] = round(
        ledger["cumulative_wall_clock_s"] / 3600.0, 6)
    ledger["soft_budget_reached"] = (
        ledger["cumulative_wall_clock_h"] >= ledger["soft_budget_h"])
    ledger["hard_budget_reached"] = (
        ledger["cumulative_wall_clock_h"] >= ledger["hard_budget_h"])
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False,
                                      sort_keys=True, indent=1) + "\n",
                           encoding="utf-8", newline="\n")
    print(f"[p3a] checker overall={checks['overall']} "
          f"tests={test_report['tests_run']} "
          f"regressions={[r['tests_run'] for r in regressions]}")
    for c in checks["checks"]:
        print(f"  {c['check']}: {c['status']}")
    _build_evidence(staging_dir, run_id, checks, test_report, regressions,
                    verification=None, wall_total=wall_total)
    probe = _verify(staging_dir)
    print(f"[p3a] probe verification ok={probe.get('ok')} {probe.get('error', '')}")
    if not probe.get("ok"):
        return 1
    _build_evidence(staging_dir, run_id, checks, test_report, regressions,
                    verification=probe, wall_total=wall_total)
    confirm = _verify(staging_dir)
    if not confirm.get("ok"):
        print(f"[p3a] FAIL final-content verification {confirm.get('error', '')}")
        return 1
    promo = _promote(staging_dir, final_dir)
    if not promo["ok"]:
        print(f"[p3a] FAIL promote {promo['sha_mismatches']}")
        return 1
    final_verify = _verify(final_dir)
    ok = (probe.get("ok") and confirm.get("ok") and promo["ok"]
          and final_verify.get("ok")
          and checks["overall"] == "PASS"
          and test_report["ok"] and all(r["ok"] for r in regressions))
    print(f"[p3a] evidence written: {final_dir}")
    print(f"[p3a] DONE overall={'PASS' if ok else 'FAIL'} wall={wall_total:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
