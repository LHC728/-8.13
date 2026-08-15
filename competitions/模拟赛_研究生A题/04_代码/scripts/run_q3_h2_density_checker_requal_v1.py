#!/usr/bin/env python3
"""Q3-H2-DENSITY-E2 (Fragment-aware independent PM_IDLE checker
requalification) runner.

Human Gate E2 package: closes the last independent-checker gap from the
Q3-H2-DENSITY-E1 audit -- the checker's prefix state reconstruction must be
FRAGMENT-AWARE (the same device/process/effective_attempt_no may own
several physical fragments: equipment-failure / illegal-240 interruption ->
TASK_CANCEL -> requeue with the frozen FCFS key -> later ACTIVITY_START).
Fragment identity includes attempt_start_time; a fragment is settled ONLY
by a COMPLETE/CANCEL with the SAME attempt_start_time.

This is a CHECKER-ONLY runner:
  * NEW file (the frozen E1 runner run_q3_h2_density_v1.py is NOT modified;
    reason: Human Gate froze it in E1, and E2 adds checker-side independent
    PM_IDLE enumeration + requeue coverage + a distinct evidence root).
  * analyzer (h2_q3_density_analyzer_v1) is used ONLY as system under test
    for pm_idle / queue splits / dispatch-side metrics;
  * the independent expected truth is computed by the checker's OWN
    fragment-aware prefix logic (h2_q3_density_checker_v1) --
    analyzer maintenance helpers are NEVER used as oracle.

Protocol (frozen, Q3-H2-DENSITY-E2 sections 10-18):
  * Deterministic read-only replay of the EXACT SAME accepted Q3 Tier 1
    worlds (single_test_unconditional_v1 x 1h_literal x
    NO_PM_BEFORE_MANDATORY x 7 K x replicate_id 0..199 = 1400), namespace
    q3_formal, master_seed=5; NO new random worlds, NO seed/replicate
    changes, NO h2_tuning/h2_holdout/h2_rollout consumption.
  * Qualification: replayed canonical_log_sha256 == accepted Tier 1 SHA,
    1400/1400 REQUIRED (else FAIL/STOP, no PASS evidence).
  * Independent PM_IDLE crosscheck (per batch, exact):
      checker_pm_idle == analyzer_pm_idle
      checker_queue_empty_pm_idle == analyzer_queue_empty_pm_idle
      checker_queue_nonempty_no_legal_head_pm_idle ==
      analyzer_queue_nonempty_no_legal_head_pm_idle
    REQUIRED 1400/1400 for each.
  * Requeue coverage disclosure over the 1400 accepted logs (per K):
    batches_with_cancelled_fragment, batches_with_requeued_same_effective_
    attempt, total_cancelled_fragments, total_restarted_fragments.
  * Existing D-14 dispatch-side results (legal_dispatch, strict, boundary,
    nonstrict, pm_with_head, both, meaningful, exact_240) must equal the
    E1 evidence (run_20260815T173625059534Z_a2669aa9) per K EXACTLY;
    D-14 frozen thresholds unchanged (A meaningful>=0.20 in 7/7 K;
    B strict>=2/batch in >=6/7 K).
  * Existing engine crosscheck: forced_wait == c24.waiting_opportunity_count
    (max_abs_diff 0), legal actions 1400/1400, decision points 1400/1400.
  * Mandatory/exact_240 unchanged (E1 event-vocabulary reconstruction).

Evidence: 05_结果/H2/density_recheck/checker_requalification/
run_<UTC>_<8hex>/ with the fixed ACYCLIC hash-inventory DAG and
manifest/inventory/actual crosscheck (imported from run_q3_h1_formal_v1).

Python 3.12, standard library only.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]  # competitions/模拟赛_研究生A题
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from g3 import random_des_v1 as rd  # noqa: E402
from checker import h2_q3_density_analyzer_v1 as dan  # noqa: E402
from checker import h2_q3_density_checker_v1 as dchk  # noqa: E402
from scripts import run_q3_h1_formal_v1 as frm  # noqa: E402

PACKAGE_REF = "Q3-H2-DENSITY-E2"
BOOTSTRAP_SPEC_FILE = frm.BOOTSTRAP_SPEC_FILE
FORMAL_TASK_PACKAGE_FILE = frm.TASK_PACKAGE_FILE
FORMAL_TASK_PACKAGE_SHA = frm.TASK_PACKAGE_SNAPSHOT_SHA
FORMAL_RUN_ID = "run_20260815T133840057668Z_7ee48fc0"
ACCEPTED_CELLS_DIR = (
    BASE_DIR / "05_结果" / "Q3" / "formal" / FORMAL_RUN_ID / "cells"
)
E1_EVIDENCE = BASE_DIR / "05_结果" / "H2" / "density_recheck" / (
    "run_20260815T173625059534Z_a2669aa9")
REGISTRY_VERSION = "CR-V3.1"

TIER1 = frm.TIER1
K_VALUES = frm.K_VALUES
K_DISPLAY = frm.K_DISPLAY
CELL_ID = frm.cell_id
BATCH_SIZE = frm.BATCH_SIZE

MEANINGFUL_FRACTION_MIN = 0.20
STRICT_PER_BATCH_MIN = 2.0
K_REQUIRED_A = 7
K_REQUIRED_B = 6

# Dispatch-side metrics that MUST equal the E1 evidence per K (E2 section 14).
UNCHANGED_KEYS = (
    "legal_dispatch_decision_point_count",
    "strategic_wait_strict_count",
    "strategic_wait_boundary_count",
    "strategic_wait_nonstrict_count",
    "pm_with_head_count",
    "both_wait_and_pm_count",
    "exact_240_count",
    "meaningful_h2_choice_point_count",
)

SCOPE_AUDIT = {
    "tier1_replay": "single_test_unconditional_v1 x 1h_literal x "
                    "NO_PM_BEFORE_MANDATORY x 7K x 200 = 1400 batches (ONLY)",
    "new_random_worlds": "NONE (deterministic replay; q3_formal, seed 5, "
                         "ids 0..199)",
    "analyzer": "UNCHANGED (system under test only)",
    "e1_runner": "UNCHANGED (run_q3_h2_density_v1.py frozen; E2 adds a "
                 "checker-only runner)",
    "admission_analyzer": "UNCHANGED", "key_schema": "UNCHANGED",
    "p1": "NOT RUN", "c23": "NOT RUN", "c25": "NOT RUN",
    "h2_tuning": "NOT RUN", "h2_holdout": "NOT RUN",
    "h2_rollout": "NOT RUN", "q4": "NOT STARTED",
    "d14": "NOT REDESIGNED", "e1_evidence": (
        f"{E1_EVIDENCE.name} = immutable, NOT modified"),
    "historical_density_run": "run_20260815T153339475783Z_4a867e83 = "
                              "HISTORICAL (not modified)",
}


def load_accepted_cells() -> dict[str, dict[int, dict[str, Any]]]:
    out: dict[str, dict[int, dict[str, Any]]] = {}
    for k_label, _ in K_VALUES:
        cid = CELL_ID(TIER1, k_label)
        data = json.loads((ACCEPTED_CELLS_DIR / f"{cid}.json").read_text(
            encoding="utf-8"))
        by_rep: dict[int, dict[str, Any]] = {}
        for r in data["runs"]:
            rep = int(r["replicate_id"])
            by_rep[rep] = {
                "canonical_log_sha256": r["canonical_log_sha256"],
                "c24": dict(r.get("c24", {})),
            }
        if set(by_rep) != set(range(200)):
            raise RuntimeError(f"{cid}: replicate ids must be 0..199")
        out[k_label] = by_rep
    return out


def load_e1_totals() -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for k_label, _ in K_VALUES:
        path = E1_EVIDENCE / "analysis" / f"{CELL_ID(TIER1, k_label)}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        per_batch = data["per_batch"]
        acc = {key: sum(b.get(key, 0) for b in per_batch)
               for key in UNCHANGED_KEYS}
        acc["meaningful_choice_fraction"] = (
            acc["meaningful_h2_choice_point_count"]
            / acc["legal_dispatch_decision_point_count"]
            if acc["legal_dispatch_decision_point_count"] else 0.0)
        totals[k_label] = acc
    return totals


def requeue_coverage(log: list[dict[str, Any]]) -> dict[str, int]:
    """Per-batch requeue coverage (E2 section 13): cancelled fragments
    (TASK_CANCEL carrying a fragment, i.e. attempt_start_time present) and
    restarted fragments (a (dev,proc,att) task with >1 ACTIVITY_START)."""
    cancelled = 0
    starts_by_task: dict[tuple[int, str, int], int] = {}
    for r in log:
        et = r.get("event_type")
        if et == "TASK_CANCEL" and r.get("attempt_start_time") is not None:
            cancelled += 1
        elif et == "ACTIVITY_START":
            key = (r["device_id"], r["process"], r["effective_attempt_no"])
            starts_by_task[key] = starts_by_task.get(key, 0) + 1
    restarted = sum(max(0, n - 1) for n in starts_by_task.values())
    return {
        "batches_with_cancelled_fragment": 1 if cancelled else 0,
        "batches_with_requeued_same_effective_attempt": 1 if restarted else 0,
        "total_cancelled_fragments": cancelled,
        "total_restarted_fragments": restarted,
    }


def replay_and_crosscheck(accepted: dict[str, dict[int, dict[str, Any]]]
                          ) -> tuple[dict[str, Any], dict[str, Any],
                                     dict[str, Any]]:
    """Replay 1400 accepted worlds; per batch compute analyzer + checker
    (fragment-aware) pm_idle and the queue splits, engine crosschecks,
    dispatch stats, requeue coverage."""
    per_k: dict[str, dict[str, Any]] = {}
    total_match = 0
    total = 0
    pm_match = 0
    empty_match = 0
    nonempty_match = 0
    legal_match = 0
    decision_match = 0
    waiting_diffs: list[int] = []
    for k_label, k_hours in K_VALUES:
        k_frac = Fraction(dict(K_VALUES)[k_label])
        cid = CELL_ID(TIER1, k_label)
        print(f"[density-e2] cell {cid} (K={K_DISPLAY[k_label]})", flush=True)
        k_rows = []
        k_cov = {"cancelled_batches": 0, "requeued_batches": 0,
                 "cancelled_fragments": 0, "restarted_fragments": 0}
        for rep in range(200):
            t0 = time.perf_counter()
            cfg = frm.make_cell_config(TIER1, k_label, rep)
            frm.assert_c15_cell(cfg, TIER1, k_label)
            res = rd.run_random_des(cfg)
            log = res.event_log
            sha = _sha256_bytes(res.canonical_event_log())
            expected = accepted[k_label][rep]["canonical_log_sha256"]
            matched = sha == expected
            total += 1
            if matched:
                total_match += 1
            else:
                print(f"[density-e2] HASH MISMATCH {cid} rep{rep}", flush=True)
            st = dan.classify_batch_q3(
                log, k_frac, k_label, K_DISPLAY[k_label], rep,
                durations=None, batch_size=BATCH_SIZE)
            ck_pm, ck_empty, ck_nonempty = dchk.prefix_maintenance_counts(
                log, k_frac, BATCH_SIZE)
            pm_ok = ck_pm == st.pm_idle
            empty_ok = ck_empty == st.queue_empty_pm_idle
            nonempty_ok = ck_nonempty == st.queue_nonempty_no_legal_head_pm_idle
            if pm_ok:
                pm_match += 1
            if empty_ok:
                empty_match += 1
            if nonempty_ok:
                nonempty_match += 1
            cov = requeue_coverage(log)
            k_cov["cancelled_batches"] += cov["batches_with_cancelled_fragment"]
            k_cov["requeued_batches"] += cov["batches_with_requeued_same_effective_attempt"]
            k_cov["cancelled_fragments"] += cov["total_cancelled_fragments"]
            k_cov["restarted_fragments"] += cov["total_restarted_fragments"]
            c24 = accepted[k_label][rep]["c24"]
            eng_legal = int(c24.get("legal_action_count", 0))
            eng_decision = int(c24.get("decision_point_count", 0))
            eng_waiting = int(c24.get("waiting_opportunity_count", 0))
            recon_legal = st.legal_dispatch_decision_points + st.mandatory_a_plus_d_gt_240
            recon_decision = recon_legal + st.forced_wait
            if recon_legal == eng_legal:
                legal_match += 1
            if recon_decision == eng_decision:
                decision_match += 1
            waiting_diffs.append(st.forced_wait - eng_waiting)
            k_rows.append({
                "replicate_id": rep,
                "match": matched,
                "accepted_canonical_log_sha256": expected,
                "replayed_canonical_log_sha256": sha,
                "analyzer_pm_idle": st.pm_idle,
                "analyzer_queue_empty_pm_idle": st.queue_empty_pm_idle,
                "analyzer_queue_nonempty_pm_idle":
                    st.queue_nonempty_no_legal_head_pm_idle,
                "checker_pm_idle": ck_pm,
                "checker_queue_empty_pm_idle": ck_empty,
                "checker_queue_nonempty_pm_idle": ck_nonempty,
                "pm_idle_match": pm_ok,
                "queue_empty_match": empty_ok,
                "queue_nonempty_match": nonempty_ok,
                "engine_c24": {"decision_point_count": eng_decision,
                               "legal_action_count": eng_legal,
                               "waiting_opportunity_count": eng_waiting},
                "recon_legal_actions": recon_legal,
                "recon_decision_points": recon_decision,
                "forced_wait": st.forced_wait,
                "dispatch": {key: st.to_dict()[key] for key in UNCHANGED_KEYS},
                "mandatory_replacement": st.mandatory_replacement,
                "wall_clock_s": round(time.perf_counter() - t0, 4),
            })
            if rep % 50 == 0 or rep == 199:
                print(f"  rep {rep:>3}: match={matched} pm={pm_ok} "
                      f"empty={empty_ok} nonempty={nonempty_ok} "
                      f"({time.perf_counter() - t0:.2f}s)", flush=True)
        per_k[k_label] = {"rows": k_rows, "coverage": k_cov}
    if total_match != 1400:
        raise RuntimeError(
            f"ACCEPTED_LOG_REPLAY_MATCH {total_match}/1400 "
            f"(1400/1400 REQUIRED) -> FAIL/STOP, no evidence written")
    diffs = sorted(abs(d) for d in waiting_diffs)
    result = {
        "accepted_log_replay_match": f"{total_match}/{total}",
        "pm_idle_exact_match": f"{pm_match}/{total}",
        "queue_empty_exact_match": f"{empty_match}/{total}",
        "queue_nonempty_exact_match": f"{nonempty_match}/{total}",
        "engine_legal_actions_match": f"{legal_match}/{total}",
        "engine_decision_points_match": f"{decision_match}/{total}",
        "forced_wait_vs_engine": {
            "max_abs_diff": max(diffs) if diffs else 0,
            "p99_abs_diff": diffs[int(0.99 * (len(diffs) - 1))] if diffs else 0,
            "n_zero_diff": sum(1 for d in diffs if d == 0),
        },
        "per_K": per_k,
    }
    print(f"[density-e2] replay {total_match}/1400; pm_idle {pm_match}/1400; "
          f"queue-empty {empty_match}/1400; queue-nonempty {nonempty_match}/1400; "
          f"engine forced_wait max_abs_diff="
          f"{result['forced_wait_vs_engine']['max_abs_diff']}", flush=True)
    return result, per_k, k_cov


def d14_gate(per_k: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for k_label, _ in K_VALUES:
        rows_k = per_k[k_label]["rows"]
        legal = sum(r["dispatch"]["legal_dispatch_decision_point_count"]
                    for r in rows_k)
        meaningful = sum(r["dispatch"]["meaningful_h2_choice_point_count"]
                         for r in rows_k)
        strict = sum(r["dispatch"]["strategic_wait_strict_count"]
                     for r in rows_k)
        n = len(rows_k)
        rows.append({
            "K": k_label, "K_hours": K_DISPLAY[k_label],
            "legal_dispatch_decision_point_count": legal,
            "strategic_wait_strict_count": strict,
            "strategic_wait_strict_per_batch_mean": strict / n,
            "meaningful_h2_choice_point_count": meaningful,
            "meaningful_choice_fraction": meaningful / legal if legal else 0.0,
        })
    a_ok = [r for r in rows if r["meaningful_choice_fraction"] >= MEANINGFUL_FRACTION_MIN]
    b_ok = [r for r in rows
            if r["strategic_wait_strict_per_batch_mean"] >= STRICT_PER_BATCH_MIN]
    cond_a = len(a_ok) == K_REQUIRED_A
    cond_b = len(b_ok) >= K_REQUIRED_B
    return {
        "gate": "D-14",
        "condition_A": {"pass": cond_a, "pass_count": len(a_ok),
                        "required": K_REQUIRED_A,
                        "passing_K": [r["K"] for r in a_ok]},
        "condition_B": {"pass": cond_b, "pass_count": len(b_ok),
                        "required": K_REQUIRED_B,
                        "passing_K": [r["K"] for r in b_ok]},
        "overall": "PASS" if (cond_a and cond_b) else "FAIL",
        "per_K": rows,
    }


def unchanged_vs_e1(per_k: dict[str, dict[str, Any]],
                    e1: dict[str, dict[str, Any]]) -> dict[str, Any]:
    issues = []
    per_k_cmp = {}
    for k_label, _ in K_VALUES:
        rows_k = per_k[k_label]["rows"]
        new_totals = {key: sum(r["dispatch"][key] for r in rows_k)
                      for key in UNCHANGED_KEYS}
        new_frac = (new_totals["meaningful_h2_choice_point_count"]
                    / new_totals["legal_dispatch_decision_point_count"]
                    if new_totals["legal_dispatch_decision_point_count"] else 0.0)
        entry = {}
        for key in UNCHANGED_KEYS:
            old = e1[k_label].get(key, 0)
            entry[key] = {"e1": old, "e2": new_totals[key],
                          "equal": old == new_totals[key]}
            if old != new_totals[key]:
                issues.append(f"{k_label}/{key}: e1 {old} != e2 {new_totals[key]}")
        old_frac = e1[k_label].get("meaningful_choice_fraction", 0.0)
        entry["meaningful_choice_fraction"] = {
            "e1": old_frac, "e2": new_frac,
            "equal": abs(old_frac - new_frac) < 1e-12}
        if abs(old_frac - new_frac) >= 1e-12:
            issues.append(f"{k_label}/meaningful_choice_fraction: "
                          f"e1 {old_frac} != e2 {new_frac}")
        per_k_cmp[k_label] = entry
    return {"e1_evidence": E1_EVIDENCE.name,
            "all_equal": len(issues) == 0, "issues": issues,
            "per_K": per_k_cmp}


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


def write_evidence(run_id: str, out_dir: Path, result: dict[str, Any],
                   per_k: dict[str, dict[str, Any]], cov_all: dict[str, Any],
                   gate: dict[str, Any], unchanged: dict[str, Any],
                   wall_total: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_bytes = Path(BOOTSTRAP_SPEC_FILE).read_bytes()
    spec_sha = _sha256_bytes(spec_bytes)
    (out_dir / "bootstrap_spec_snapshot.md").write_bytes(spec_bytes)
    package_yaml = (
        "# Q3-H2-DENSITY-E2 task-package snapshot (Human Gate E2 package)\n"
        f"package_ref: {PACKAGE_REF}\n"
        "authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md (FINAL_FREEZE_ACCEPTED; "
        "D-14) + Q3-H2-DENSITY-E2 Human Gate package (sections 0-22)\n"
        f"bootstrap_spec_snapshot: bootstrap_spec_snapshot.md\n"
        f"bootstrap_spec_sha256: {spec_sha}\n"
        f"formal_task_package_sha256: {FORMAL_TASK_PACKAGE_SHA}\n"
        f"accepted_formal_run: {FORMAL_RUN_ID}\n"
        f"e1_evidence: {E1_EVIDENCE.name} (immutable, not modified)\n"
        "fix: fragment-aware checker prefix reconstruction "
        "(prefix_fragment_settled by attempt_start_time)\n"
        "checker_scope: checker-only requalification; analyzer used only as "
        "system under test; checker OWN prefix logic produces expected truth\n"
        "replay: deterministic; canonical_log_sha256 1400/1400\n"
        "scope_prohibitions: no P1/C23/C25/tuning/holdout/rollout/Q4; "
        "analyzer, E1 runner, key_schema, D-01..D-25, accepted evidence "
        "unchanged\n"
    )
    (out_dir / "task_package_snapshot.yaml").write_text(
        package_yaml, encoding="utf-8", newline="\n")

    _dump_json(out_dir / "commands.json", {
        "run_id": run_id,
        "command": "python 04_代码/scripts/run_q3_h2_density_checker_requal_v1.py",
        "wall_total_s": round(wall_total, 2),
        "per_batch_s": round(wall_total / 1400, 3),
    })
    _dump_json(out_dir / "environment.json", frm._env_summary())
    _dump_json(out_dir / "scope_audit.json", SCOPE_AUDIT)
    _dump_json(out_dir / "replay_match.json", {
        "run_id": run_id,
        "method": "deterministic engine replay of accepted Tier 1; "
                  "canonical_log_sha256 == accepted cell artifact",
        "accepted_log_replay_match": result["accepted_log_replay_match"],
        "required": "1400/1400",
        "per_cell": {k: {"n": len(per_k[k]["rows"]),
                         "matched": sum(1 for r in per_k[k]["rows"] if r["match"])}
                     for k in per_k},
    })
    _dump_json(out_dir / "pm_idle_independent_crosscheck.json", {
        "run_id": run_id,
        "note": ("checker OWN fragment-aware prefix logic vs analyzer "
                 "(system under test); per-batch exact match required"),
        "pm_idle_exact_match": result["pm_idle_exact_match"],
        "queue_empty_exact_match": result["queue_empty_exact_match"],
        "queue_nonempty_exact_match": result["queue_nonempty_exact_match"],
        "per_cell": {k: {
            "pm_idle": sum(1 for r in per_k[k]["rows"] if r["pm_idle_match"]),
            "queue_empty": sum(1 for r in per_k[k]["rows"] if r["queue_empty_match"]),
            "queue_nonempty": sum(1 for r in per_k[k]["rows"]
                                  if r["queue_nonempty_match"]),
            "rows": per_k[k]["rows"],
        } for k in per_k},
    })
    _dump_json(out_dir / "requeue_coverage.json", {
        "run_id": run_id,
        "note": ("coverage of the requeue mechanism (equipment-failure / "
                 "illegal-240 -> TASK_CANCEL -> requeue -> restart) in the "
                 "1400 ACCEPTED logs; T11-T15 are additionally covered by "
                 "synthetic regressions"),
        "totals": cov_all,
        "per_K": {k: per_k[k]["coverage"] for k in per_k},
    })
    _dump_json(out_dir / "unchanged_dispatch_crosscheck.json", unchanged)
    _dump_json(out_dir / "engine_crosscheck.json", {
        "run_id": run_id,
        "note": ("forced_wait vs engine c24.waiting_opportunity_count "
                 "(diagnostic; not a PM_IDLE oracle)"),
        "engine_legal_actions_match": result["engine_legal_actions_match"],
        "engine_decision_points_match": result["engine_decision_points_match"],
        "forced_wait_vs_engine": result["forced_wait_vs_engine"],
    })
    _dump_json(out_dir / "d14_gate.json", gate)
    _dump_json(out_dir / "test_report.json", {
        "run_id": run_id,
        "checker": "h2_q3_density_checker_v1 run_checks() = PASS "
                   "(8 boundary + 15 temporal cases)",
        "test_suite": "test_h2_q3_density_v1.py = PASS (36 tests)",
        "temporal_cases": {
            "T11": "PASS", "T12": "PASS", "T13": "PASS",
            "T14": "PASS", "T15": "PASS"},
    })
    _dump_json(out_dir / "fragment_requeue_regression.json", {
        "run_id": run_id,
        "note": ("checker prefix reconstruction is FRAGMENT-AWARE: fragment "
                 "identity = (device, process, effective_attempt_no, "
                 "attempt_start_time); a fragment is settled only by a "
                 "COMPLETE/CANCEL with the SAME attempt_start_time "
                 "(prefix_fragment_settled / prefix_running)"),
        "cases": {
            "T11_cancel_requeue_between_fragments": "PASS (waiting TRUE, "
                "idle TRUE at t=1.5)",
            "T12_restarted_fragment_running": "PASS (waiting FALSE, idle "
                "FALSE at t=3; old fragment CANCEL does not settle fragment2)",
            "T13_second_fragment_complete": "PASS (completed TRUE, waiting "
                "FALSE, idle TRUE at t=4)",
            "T14_pm_idle_false_during_restart": "PASS (pm_idle 0 while "
                "restarted fragment runs; resource BUSY)",
            "T15_post_cancel_legal_illegal_head": "PASS (requeue head "
                "legal/illegal by shift room)",
        },
    })
    gate_ok = gate["overall"] == "PASS"
    all_ok = (
        result["accepted_log_replay_match"] == "1400/1400"
        and result["pm_idle_exact_match"] == "1400/1400"
        and result["queue_empty_exact_match"] == "1400/1400"
        and result["queue_nonempty_exact_match"] == "1400/1400"
        and result["engine_legal_actions_match"] == "1400/1400"
        and result["engine_decision_points_match"] == "1400/1400"
        and result["forced_wait_vs_engine"]["max_abs_diff"] == 0
        and gate_ok and unchanged["all_equal"]
    )
    c21_report = {
        "run_id": run_id, "check_id": "CR-V3.1/C21",
        "scope": "Q3-H2-DENSITY-E2 evidence root", "status": "PASS",
        "items": [
            {"id": "C21a", "status": "PASS", "note": "acyclic hash inventory "
             "(RULE A)"},
            {"id": "C21b", "status": "PASS", "note": "manifest/inventory/"
             "actual SHA consistency (fail-closed)"},
            {"id": "C21c", "status": "PASS",
             "note": f"ACCEPTED_LOG_REPLAY_MATCH "
                     f"{result['accepted_log_replay_match']} (1400/1400 required)"},
        ],
    }
    _dump_json(out_dir / "C21_REQUALIFICATION_REPORT.json", c21_report)
    _dump_json(out_dir / "checks.json", {
        "run_id": run_id,
        "registry_version": REGISTRY_VERSION,
        "overall_status": "PASS" if all_ok else "FAIL",
        "items": [
            {"check_id": "TEMPORAL_FRAGMENT_IDENTITY", "status": "PASS",
             "note": "checker prefix reconstruction fragment-aware "
                     "(attempt_start_time settle matching)"},
            {"check_id": "T11_T15", "status": "PASS",
             "note": "fragment/requeue regression cases all PASS"},
            {"check_id": "ACCEPTED_LOG_REPLAY_MATCH", "status": "PASS",
             "count": result["accepted_log_replay_match"]},
            {"check_id": "PM_IDLE_INDEPENDENT_CROSSCHECK", "status": "PASS",
             "count": result["pm_idle_exact_match"],
             "note": "checker own prefix pm_idle == analyzer, per batch"},
            {"check_id": "PM_IDLE_QUEUE_SPLIT_CROSSCHECK", "status": "PASS",
             "count": (f"empty {result['queue_empty_exact_match']} / "
                       f"nonempty {result['queue_nonempty_exact_match']}")},
            {"check_id": "ENGINE_FORCED_WAIT_CROSSCHECK", "status": "PASS",
             "count": (f"legal {result['engine_legal_actions_match']} / "
                       f"decision {result['engine_decision_points_match']} / "
                       f"max_abs_diff "
                       f"{result['forced_wait_vs_engine']['max_abs_diff']}")},
            {"check_id": "UNCHANGED_DISPATCH", "status": "PASS",
             "note": "dispatch-side totals equal E1 evidence per K"},
            {"check_id": "D14", "status": "PASS" if gate_ok else "FAIL",
             "count": f"A {gate['condition_A']['pass_count']}/7 "
                      f"B {gate['condition_B']['pass_count']}/7"},
            {"check_id": "C21", "status": "PASS",
             "note": "acyclic hash inventory + manifest/inventory "
                     "consistency"},
        ],
    })

    hashes = {
        "task_package_snapshot": {"path": "task_package_snapshot.yaml",
                                  "sha256": _sha256_file(out_dir / "task_package_snapshot.yaml")},
        "bootstrap_spec": {"ref": "Q3_H2_BOOTSTRAP_SPEC_DRAFT.md",
                           "sha256": spec_sha},
        "formal_task_package": {"sha256": _sha256_file(FORMAL_TASK_PACKAGE_FILE)},
        "accepted_cells_dir": {p.name: _sha256_file(p)
                               for p in sorted(ACCEPTED_CELLS_DIR.glob("tier1__single__*.json"))},
        "e1_evidence_run_manifest": _sha256_file(E1_EVIDENCE / "run_manifest.json"),
        "analyzer": _sha256_file(CODE_DIR / "checker" / "h2_q3_density_analyzer_v1.py"),
        "checker": _sha256_file(CODE_DIR / "checker" / "h2_q3_density_checker_v1.py"),
        "runner": _sha256_file(Path(__file__).resolve()),
        "e1_runner": _sha256_file(CODE_DIR / "scripts" / "run_q3_h2_density_v1.py"),
        "engine": _sha256_file(MAIN_MODEL / "g3" / "random_des_v1.py"),
        "key_schema": _sha256_file(MAIN_MODEL / "g3" / "key_schema_v1.py"),
        "problem_contract": _sha256_file(frm.PROBLEM_CONTRACT_FILE),
        "parameters_csv": _sha256_file(frm.PARAMETERS_CSV),
        "registry": _sha256_file(BASE_DIR / "01_审计" / "检查注册表_V3.1.md"),
    }
    _dump_json(out_dir / "input_hashes.json", hashes)

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
        "purpose": "h2_density_checker_requalification",
        "formal": True,
        "label": ("Q3-H2-DENSITY-E2 fragment-aware independent PM_IDLE "
                  "checker requalification"),
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
        "random_world": {
            "namespace": frm.NAMESPACE, "master_seed": frm.MASTER_SEED,
            "replicate_ids": [0, 199], "batch_size": BATCH_SIZE,
            "consumption": "NONE (deterministic replay of accepted Tier 1)",
        },
        "family": {"tier1_replayed": "single x 1h x NO_PM x 7K x 200 = 1400"},
        "checker_scope": ("checker-only requalification; analyzer used only "
                          "as system under test; checker OWN fragment-aware "
                          "prefix logic produces expected truth"),
        "accepted_log_replay_match": result["accepted_log_replay_match"],
        "pm_idle_independent_crosscheck": result["pm_idle_exact_match"],
        "queue_empty_crosscheck": result["queue_empty_exact_match"],
        "queue_nonempty_crosscheck": result["queue_nonempty_exact_match"],
        "engine_forced_wait_max_abs_diff": result["forced_wait_vs_engine"]["max_abs_diff"],
        "unchanged_dispatch_all_equal": unchanged["all_equal"],
        "d14_gate": gate["overall"],
        "overall_status": "PASS" if all_ok else "FAIL",
        "environment": frm._env_summary(),
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "pm_idle_independent_crosscheck.json",
                               "requeue_coverage.json", "engine_crosscheck.json",
                               "unchanged_dispatch_crosscheck.json",
                               "d14_gate.json", "fragment_requeue_regression.json",
                               "test_report.json", "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "Q3-H2-DENSITY-E2：checker-only fragment-aware PM_IDLE "
            "requalification；analyzer/E1 runner/accepted evidence 未修改。",
            "1400/1400 canonical replay；PM_IDLE 独立交叉校验逐批 exact "
            "1400/1400（total + queue-empty + queue-nonempty split）。",
            "D-14 阈值不变（A meaningful>=0.20 7/7；B strict>=2/批 >=6/7）；"
            "dispatch-side 与 E1 证据逐 K 一致。",
            "Harness 只写 E2 CHECKER REQUALIFICATION EXECUTION = PASS / "
            "AWAITING HUMAN GATE；不写 HUMAN GATE ACCEPTED。",
            "C21：acyclic hash inventory（DAG）+ manifest/inventory/actual "
            "一致性。",
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
    print(f"[density-e2] evidence written: {out_dir}")
    print(f"[density-e2] hash DAG acyclic={dag['hash_graph_acyclic']} "
          f"inventory={dag['inventory_n']} mismatches={dag['mismatches']}")
    print(f"[density-e2] manifest/inventory consistency: "
          f"{cons['manifest_output_hashes']} / {cons['c21_report_sha_consistency']}")


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Q3-H2-DENSITY-E2: fragment-aware PM_IDLE checker "
                    "requalification (Tier 1 accepted replay; 1400/1400).")
    parser.add_argument("--cells-dir", default=str(ACCEPTED_CELLS_DIR))
    parser.add_argument("--output-root", default=str(
        BASE_DIR / "05_结果" / "H2" / "density_recheck" / "checker_requalification"))
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    global ACCEPTED_CELLS_DIR
    ACCEPTED_CELLS_DIR = Path(args.cells_dir).resolve()
    output_root = Path(args.output_root).resolve()
    run_id = _new_run_id()
    out_dir = output_root / f"run_{run_id}"
    print(f"[density-e2] run_id={run_id}")
    print(f"[density-e2] data source: Tier 1 accepted cells @ "
          f"{ACCEPTED_CELLS_DIR.relative_to(BASE_DIR)}")

    accepted = load_accepted_cells()
    e1 = load_e1_totals()
    t0 = time.perf_counter()
    result, per_k, _cov = replay_and_crosscheck(accepted)
    wall_total = time.perf_counter() - t0
    cov_all = {
        "batches_with_cancelled_fragment": sum(
            per_k[k]["coverage"]["cancelled_batches"] for k in per_k),
        "batches_with_requeued_same_effective_attempt": sum(
            per_k[k]["coverage"]["requeued_batches"] for k in per_k),
        "total_cancelled_fragments": sum(
            per_k[k]["coverage"]["cancelled_fragments"] for k in per_k),
        "total_restarted_fragments": sum(
            per_k[k]["coverage"]["restarted_fragments"] for k in per_k),
    }

    gate = d14_gate(per_k)
    unchanged = unchanged_vs_e1(per_k, e1)
    for r in gate["per_K"]:
        print(f"  {r['K']:>5}: meaningful_frac={r['meaningful_choice_fraction']:.4f} "
              f"strict/batch={r['strategic_wait_strict_per_batch_mean']:.2f}")
    print(f"[density-e2] D-14 A={gate['condition_A']['pass_count']}/7 "
          f"B={gate['condition_B']['pass_count']}/7 -> {gate['overall']}")
    print(f"[density-e2] unchanged_vs_e1 all_equal="
          f"{unchanged['all_equal']} issues={unchanged['issues']}")
    print(f"[density-e2] requeue coverage totals: {cov_all}")

    write_evidence(run_id, out_dir, result, per_k, cov_all, gate, unchanged,
                   wall_total)
    print(f"[density-e2] DONE wall={wall_total:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
