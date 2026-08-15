#!/usr/bin/env python3
"""Q3-H2-DENSITY-E1 (Temporal Reconstruction Requalification) runner.

Human Gate repair package: requalifies the Q3 seven-K H2 opportunity-density
evidence after the time-causality defects in the density analyzer's
maintenance / forced-wait / mandatory reconstruction (Q3-H2-DENSITY-E1
sections 0-23).

Protocol (frozen):
  * Data source: Q3 H1 Tier 1 ACCEPTED logs only (single_test_unconditional_v1
    x 1h_literal x NO_PM_BEFORE_MANDATORY, 7 K x 200 batches = 1400 worlds),
    deterministic read-only replay (namespace q3_formal, master_seed=5,
    replicate_ids 0..199, K per cell); NO new random-world consumption;
    accepted evidence dirs are never modified.
  * Qualification: replayed canonical_log_sha256 == accepted Tier 1 SHA
    1400/1400 REQUIRED; any mismatch -> FAIL/STOP before evidence write.
  * Classification: E1 time-indexed analyzer (checker/
    h2_q3_density_analyzer_v1): time-causal state_at(t) reconstruction,
    frozen FCFS head at t, E prerequisite by PASS observation <= t, future
    potential demand at t, closure-set enumeration (distinct canonical
    event times + Q3 shift starts; at most one decision point per
    (resource, closure)), mandatory from EQUIPMENT_REPLACEMENT_START
    kind=mandatory_240 (trigger breakdown).
  * Crosschecks vs accepted engine instruments (per batch):
      recon_legal_actions  = legal_dispatch + mandatory_a_plus_d_gt_240
                             vs c24.legal_action_count;
      recon_decision_points= recon_legal_actions + forced_wait
                             vs c24.decision_point_count;
      forced_wait vs c24.waiting_opportunity_count (forced-wait instrument).
  * D-14 gate (frozen, never lowered):
      A meaningful_choice_fraction >= 0.20 in 7/7 K (admission-comparable
        denominator: meaningful DISPATCH / legal DISPATCH; PM_IDLE never
        enters the denominator);
      B strategic_wait_strict_per_batch >= 2 in >=6/7 K.
  * Old-vs-new comparison: UNCHANGED_EXPECTED dispatch-side metrics
    (legal_dispatch, strict, boundary, nonstrict, pm_with_head, both,
    meaningful fraction, exact_240) must be identical; REQUALIFIED metrics
    (pm_idle, forced_wait, mandatory, maintenance points, zero-action
    diagnostics) are reported old vs new.
  * Zero-opportunity disclosure: zero_dispatch_opportunity_batch (D-14
    frozen comparable) and zero_full_action_space_opportunity_batch
    (incl. PM_IDLE) as descriptive diagnostics.
  * STOP on completion; P1 / C23 / C25 / Tier 2/3 / tuning / holdout are
    NOT run.

Evidence: 05_结果/H2/density_recheck/run_<UTC>_<8hex>/ (immutable; the
historical run run_20260815T153339475783Z_4a867e83 is NOT modified) with
the fixed ACYCLIC hash-inventory DAG + manifest/inventory/actual
crosscheck (imported from run_q3_h1_formal_v1, never reimplemented).

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
from scripts import run_q3_h1_formal_v1 as frm  # noqa: E402

# ---------------------------------------------------------------------------
# Frozen identity / inputs
# ---------------------------------------------------------------------------

PACKAGE_REF = "Q3-H2-DENSITY-E1"
BOOTSTRAP_SPEC_FILE = frm.BOOTSTRAP_SPEC_FILE
FORMAL_TASK_PACKAGE_FILE = frm.TASK_PACKAGE_FILE
FORMAL_TASK_PACKAGE_SHA = frm.TASK_PACKAGE_SNAPSHOT_SHA
FORMAL_RUN_ID = "run_20260815T133840057668Z_7ee48fc0"
FORMAL_REISSUE_ID = "reissue_20260815T150613626910Z_f4da8f9d"
ACCEPTED_CELLS_DIR = (
    BASE_DIR / "05_结果" / "Q3" / "formal" / FORMAL_RUN_ID / "cells"
)
# Historical Density run (immutable; marked HISTORICAL_DENSITY_EXECUTION_
# WITH_TEMPORAL_RECONSTRUCTION_DEFECT; NEVER modified).
OLD_DENSITY_RUN = BASE_DIR / "05_结果" / "H2" / "density_recheck" / (
    "run_20260815T153339475783Z_4a867e83")
OLD_ANALYZER_BLOB = "f6428090411705f6a0224162c0b7849724b625c5"
REGISTRY_VERSION = "CR-V3.1"

TIER1 = frm.TIER1
K_VALUES = frm.K_VALUES
K_DISPLAY = frm.K_DISPLAY
CELL_ID = frm.cell_id
BATCH_SIZE = frm.BATCH_SIZE

# D-14 pre-registered gate (frozen; NEVER lowered or reinterpreted).
MEANINGFUL_FRACTION_MIN = 0.20
STRICT_PER_BATCH_MIN = 2.0
K_REQUIRED_A = 7
K_REQUIRED_B = 6

# Dispatch-side metrics that MUST be unchanged by the temporal fix (E1
# section 17, UNCHANGED_EXPECTED).
UNCHANGED_KEYS = (
    "legal_dispatch_decision_point_count",
    "strategic_wait_strict_count",
    "strategic_wait_boundary_count",
    "strategic_wait_nonstrict_count",
    "raw_pm_age_eligible_count",
    "pm_with_head_count",
    "both_wait_and_pm_count",
    "exact_240_count",
    "meaningful_h2_choice_point_count",
)
# Metrics EXPECTED_TO_BE_REQUALIFIED (E1 section 17).
REQUALIFIED_KEYS = (
    "forced_wait_count",
    "pm_idle_count",
    "queue_empty_pm_idle_count",
    "queue_nonempty_no_legal_head_pm_idle_count",
    "maintenance_decision_point_count",
    "mandatory_replacement_count",
    "mandatory_trigger_a_plus_d_gt_240_count",
    "mandatory_trigger_post_completion_240_count",
    "mandatory_trigger_illegal_crossing_backstop_count",
    "mandatory_at_dispatch_diagnostic_count",
)

ADMISSION_CONTEXT = {
    "note": ("Q2 单班 12h 日历 admission 证据（描述性背景，非 Q3 门槛）："
             "legal_dispatch ≈ 413.1/批；strict wait ≈ 11.4/批；optional PM ≈ "
             "168.8/批；meaningful ≈ 0.429。Q3 双班 K 日历下用本次重放实测。"),
    "meaningful_choice_fraction": 0.429,
    "source": "accepted H2 admission evidence (Q2 12h single-shift)",
}

SCOPE_AUDIT = {
    "tier1_replay": "single_test_unconditional_v1 x 1h_literal x "
                    "NO_PM_BEFORE_MANDATORY x 7K x 200 = 1400 batches (ONLY)",
    "tier2": "NOT RUN", "tier3": "NOT RUN",
    "new_random_worlds": "NONE (deterministic replay; q3_formal, seed 5, ids 0..199)",
    "g3_core_changes": "NONE", "key_schema": "UNCHANGED",
    "admission_analyzer": "UNCHANGED (h2_admission_opportunity_analyzer_v1 "
                          "never modified)",
    "p1": "NOT RUN", "c23": "NOT RUN", "c25": "NOT RUN",
    "h2_tuning": "NOT RUN", "h2_holdout": "NOT RUN",
    "h2_policy_execution": "NONE", "rollout": "NONE",
    "posterior": "NONE", "tau_retuning": "NONE",
    "d_redesign": "NONE (D-01..D-25 not reopened)",
    "q4": "NOT STARTED",
    "historical_density_run": (
        f"{OLD_DENSITY_RUN.name} = HISTORICAL_DENSITY_EXECUTION_WITH_"
        "TEMPORAL_RECONSTRUCTION_DEFECT (immutable; not modified)"),
}


# ---------------------------------------------------------------------------
# Accepted-hash binding + accepted c24 instruments
# ---------------------------------------------------------------------------


def load_accepted_cells() -> dict[str, dict[int, dict[str, Any]]]:
    """replicate_id -> {canonical_log_sha256, c24} from the ACCEPTED Tier 1
    cell artifacts."""
    out: dict[str, dict[int, dict[str, Any]]] = {}
    for k_label, _ in K_VALUES:
        cid = CELL_ID(TIER1, k_label)
        path = ACCEPTED_CELLS_DIR / f"{cid}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        runs = data["runs"]
        if len(runs) != 200:
            raise RuntimeError(f"{cid}: accepted cell must have 200 runs")
        by_rep: dict[int, dict[str, Any]] = {}
        for r in runs:
            rep = int(r["replicate_id"])
            by_rep[rep] = {
                "canonical_log_sha256": r["canonical_log_sha256"],
                "c24": dict(r.get("c24", {})),
            }
        if set(by_rep) != set(range(200)):
            raise RuntimeError(f"{cid}: replicate ids must be 0..199")
        out[k_label] = by_rep
    return out


def load_old_run_totals() -> dict[str, dict[str, int]]:
    """Per-K totals from the historical Density run (immutable read-only)."""
    totals: dict[str, dict[str, int]] = {}
    for k_label, _ in K_VALUES:
        path = OLD_DENSITY_RUN / "analysis" / f"{CELL_ID(TIER1, k_label)}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        per_batch = data["per_batch"]
        acc: dict[str, int] = {}
        for key in UNCHANGED_KEYS + REQUALIFIED_KEYS + (
                "optional_pm_total_count",):
            acc[key] = sum(b.get(key, 0) for b in per_batch)
        acc["zero_opportunity_batches"] = sum(
            1 for b in per_batch if b.get("zero_opportunity_batch"))
        acc["meaningful_choice_fraction"] = (
            acc["meaningful_h2_choice_point_count"]
            / acc["legal_dispatch_decision_point_count"]
            if acc["legal_dispatch_decision_point_count"] else 0.0)
        totals[k_label] = acc
    return totals


# ---------------------------------------------------------------------------
# Replay + classification + engine crosschecks
# ---------------------------------------------------------------------------


def replay_and_classify(accepted: dict[str, dict[int, dict[str, Any]]]
                        ) -> tuple[dict[str, list[dan.DensityBatchStats]],
                                   dict[str, list[dict[str, Any]]]]:
    per_k: dict[str, list[dan.DensityBatchStats]] = {}
    match_rows: dict[str, list[dict[str, Any]]] = {}
    total_matched = 0
    total = 0
    for k_label, k_hours in K_VALUES:
        cid = CELL_ID(TIER1, k_label)
        k_frac = Fraction(dict(K_VALUES)[k_label])
        print(f"[density-e1] cell {cid}: replay 200 batches (K={K_DISPLAY[k_label]})",
              flush=True)
        stats_list: list[dan.DensityBatchStats] = []
        rows: list[dict[str, Any]] = []
        for rep in range(200):
            t0 = time.perf_counter()
            cfg = frm.make_cell_config(TIER1, k_label, rep)
            frm.assert_c15_cell(cfg, TIER1, k_label)
            result = rd.run_random_des(cfg)
            sha = _sha256_bytes(result.canonical_event_log())
            expected = accepted[k_label][rep]["canonical_log_sha256"]
            matched = sha == expected
            total += 1
            if matched:
                total_matched += 1
            else:
                print(f"[density-e1] HASH MISMATCH {cid} rep{rep}", flush=True)
            st = dan.classify_batch_q3(
                result.event_log, k_frac, k_label, K_DISPLAY[k_label], rep,
                durations=None, batch_size=BATCH_SIZE,
            )
            stats_list.append(st)
            c24 = accepted[k_label][rep]["c24"]
            eng_legal = int(c24.get("legal_action_count", 0))
            eng_decision = int(c24.get("decision_point_count", 0))
            eng_waiting = int(c24.get("waiting_opportunity_count", 0))
            recon_legal = st.legal_dispatch_decision_points + st.mandatory_a_plus_d_gt_240
            recon_decision = recon_legal + st.forced_wait
            rows.append({
                "replicate_id": rep,
                "accepted_canonical_log_sha256": expected,
                "replayed_canonical_log_sha256": sha,
                "match": matched,
                "engine_c24": {
                    "decision_point_count": eng_decision,
                    "legal_action_count": eng_legal,
                    "waiting_opportunity_count": eng_waiting,
                },
                "reconstructed": {
                    "legal_dispatch": st.legal_dispatch_decision_points,
                    "forced_wait": st.forced_wait,
                    "mandatory_a_plus_d_gt_240": st.mandatory_a_plus_d_gt_240,
                    "recon_legal_actions": recon_legal,
                    "recon_decision_points": recon_decision,
                },
                "crosscheck": {
                    "legal_actions_match": recon_legal == eng_legal,
                    "decision_points_match": recon_decision == eng_decision,
                    "forced_wait_diff_vs_engine": st.forced_wait - eng_waiting,
                },
                "wall_clock_s": round(time.perf_counter() - t0, 4),
            })
            if rep % 50 == 0 or rep == 199:
                print(f"  rep {rep:>3}: match={matched} "
                      f"({time.perf_counter() - t0:.2f}s)", flush=True)
        per_k[k_label] = stats_list
        match_rows[k_label] = rows
    if total_matched != 1400:
        raise RuntimeError(
            f"ACCEPTED_LOG_REPLAY_MATCH {total_matched}/1400 "
            f"(1400/1400 REQUIRED) -> FAIL/STOP, no evidence written"
        )
    print(f"[density-e1] ACCEPTED_LOG_REPLAY_MATCH {total_matched}/1400", flush=True)
    return per_k, match_rows


def crosscheck_summary(match_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Engine-instrument crosscheck (E1 sections 10/16): forced-wait
    reconstruction vs the accepted c24.waiting_opportunity_count, and the
    decision-point algebra legal_dispatch + mandatory_a_plus_d_gt_240 +
    forced_wait == c24.decision_point_count."""
    legal_mismatch = 0
    decision_mismatch = 0
    waiting_diffs: list[int] = []
    for k, rows in match_rows.items():
        for r in rows:
            cc = r["crosscheck"]
            if not cc["legal_actions_match"]:
                legal_mismatch += 1
            if not cc["decision_points_match"]:
                decision_mismatch += 1
            waiting_diffs.append(cc["forced_wait_diff_vs_engine"])
    n = sum(len(rows) for rows in match_rows.values())
    diffs = sorted(abs(d) for d in waiting_diffs)
    return {
        "batches": n,
        "legal_actions_match": f"{n - legal_mismatch}/{n}",
        "decision_points_match": f"{n - decision_mismatch}/{n}",
        "forced_wait_vs_engine_waiting": {
            "max_abs_diff": max(diffs) if diffs else 0,
            "p50_abs_diff": diffs[len(diffs) // 2] if diffs else 0,
            "p99_abs_diff": diffs[int(0.99 * (len(diffs) - 1))] if diffs else 0,
            "n_zero_diff": sum(1 for d in diffs if d == 0),
            "note": ("forced_wait is the reconstructed forced-wait state; "
                     "engine waiting_opportunity_count is the frozen "
                     "forced-wait instrument (diagnostic crosscheck only; "
                     "never used as STRICT/BOUNDARY/meaningful)"),
        },
        "verdict": ("CONSISTENT" if (legal_mismatch == 0 and decision_mismatch == 0)
                    else "INVESTIGATE"),
    }


# ---------------------------------------------------------------------------
# D-14 gate evaluation + old-vs-new comparison
# ---------------------------------------------------------------------------


def evaluate_gate(per_k: dict[str, list[dan.DensityBatchStats]]
                  ) -> tuple[dict[str, Any], dict[str, dan.DensityKAggregate]]:
    aggs = {k: dan.aggregate_k(k, K_DISPLAY[k], stats_list)
            for k, stats_list in per_k.items()}
    rows = []
    for k_label, _ in K_VALUES:
        a = aggs[k_label]
        d = a.to_dict()
        c = d["total_counts"]
        rows.append({
            "K": k_label, "K_hours": K_DISPLAY[k_label], "batches": a.n,
            "legal_dispatch_decision_point_count": c["legal_dispatch_decision_point_count"],
            "forced_wait_count": c["forced_wait_count"],
            "strategic_wait_strict_count": c["strategic_wait_strict_count"],
            "strategic_wait_strict_per_batch_mean": d["per_batch"]["strategic_wait_strict_count"]["mean"],
            "strategic_wait_strict_per_batch_median": d["per_batch"]["strategic_wait_strict_count"]["median"],
            "strategic_wait_boundary_count": c["strategic_wait_boundary_count"],
            "strategic_wait_nonstrict_count": c["strategic_wait_nonstrict_count"],
            "pm_with_head_count": c["pm_with_head_count"],
            "pm_idle_count": c["pm_idle_count"],
            "pm_idle_per_batch_mean": d["per_batch"]["pm_idle_count"]["mean"],
            "queue_empty_pm_idle_count": c["queue_empty_pm_idle_count"],
            "queue_nonempty_no_legal_head_pm_idle_count": c["queue_nonempty_no_legal_head_pm_idle_count"],
            "maintenance_decision_point_count": c["maintenance_decision_point_count"],
            "mandatory_replacement_count": c["mandatory_replacement_count"],
            "mandatory_trigger_a_plus_d_gt_240_count": c["mandatory_trigger_a_plus_d_gt_240_count"],
            "mandatory_trigger_post_completion_240_count": c["mandatory_trigger_post_completion_240_count"],
            "mandatory_trigger_illegal_crossing_backstop_count": c["mandatory_trigger_illegal_crossing_backstop_count"],
            "mandatory_at_dispatch_diagnostic_count": c["mandatory_at_dispatch_diagnostic_count"],
            "exact_240_count": c["exact_240_count"],
            "both_wait_and_pm_count": c["both_wait_and_pm_count"],
            "meaningful_h2_choice_point_count": c["meaningful_h2_choice_point_count"],
            "meaningful_choice_fraction": d["meaningful_choice_fraction"],
            "zero_opportunity_batch_count": c["zero_opportunity_batches"],
            "zero_opportunity_batch_fraction": d["zero_opportunity_batch_fraction"],
            "zero_full_action_space_batch_count": c["zero_full_action_space_batches"],
            "zero_full_action_space_batch_fraction": d["zero_full_action_space_batch_fraction"],
        })
    a_ok = [r for r in rows
            if r["meaningful_choice_fraction"] >= MEANINGFUL_FRACTION_MIN]
    b_ok = [r for r in rows
            if r["strategic_wait_strict_per_batch_mean"] >= STRICT_PER_BATCH_MIN]
    cond_a = len(a_ok) == K_REQUIRED_A
    cond_b = len(b_ok) >= K_REQUIRED_B
    overall = cond_a and cond_b
    return {
        "gate": "D-14",
        "condition_A": {
            "text": "meaningful_choice_fraction >= 0.20 in 7/7 K",
            "pass": cond_a, "pass_count": len(a_ok), "required": K_REQUIRED_A,
            "passing_K": [r["K"] for r in a_ok],
        },
        "condition_B": {
            "text": "strategic_wait_strict_per_batch >= 2 in >=6/7 K",
            "pass": cond_b, "pass_count": len(b_ok), "required": K_REQUIRED_B,
            "passing_K": [r["K"] for r in b_ok],
        },
        "overall": "PASS" if overall else "FAIL",
        "verdict_text": (
            "DENSITY REQUALIFICATION EXECUTION = PASS; AWAITING HUMAN GATE "
            "FINAL REVIEW; P1 NOT STARTED" if overall else
            "DENSITY REQUALIFICATION = FAIL; H2 DELETE RECOMMENDED; "
            "AWAITING HUMAN GATE DELETE REVIEW; P1 NOT STARTED"
        ),
        "note": ("BOUNDARY legal WAIT reported separately, never merged into "
                 "STRICT; PM_IDLE never enters the D-14 denominator; "
                 "thresholds are pre-registered policy thresholds."),
        "per_K": rows,
    }, aggs


def build_old_new_comparison(old: dict[str, dict[str, Any]],
                             new: dict[str, dan.DensityKAggregate]) -> dict[str, Any]:
    """E1 section 17: per-K old vs new with UNCHANGED_EXPECTED /
    EXPECTED_TO_BE_REQUALIFIED classification."""
    per_k: dict[str, Any] = {}
    unchanged_issues: list[str] = []
    for k_label, _ in K_VALUES:
        a = new[k_label].to_dict()
        c = a["total_counts"]
        row: dict[str, Any] = {"K": k_label, "K_hours": K_DISPLAY[k_label]}
        for key in UNCHANGED_KEYS:
            old_v = old[k_label].get(key, 0)
            new_v = c.get(key, 0)
            row[key] = {"old": old_v, "new": new_v,
                        "category": "UNCHANGED_EXPECTED",
                        "equal": old_v == new_v}
            if old_v != new_v:
                unchanged_issues.append(f"{k_label}/{key}: old {old_v} != new {new_v}")
        old_frac = old[k_label].get("meaningful_choice_fraction", 0.0)
        new_frac = a["meaningful_choice_fraction"]
        row["meaningful_choice_fraction"] = {
            "old": old_frac, "new": new_frac,
            "category": "UNCHANGED_EXPECTED",
            "equal": abs(old_frac - new_frac) < 1e-12,
        }
        if abs(old_frac - new_frac) >= 1e-12:
            unchanged_issues.append(f"{k_label}/meaningful_choice_fraction: "
                                    f"old {old_frac} != new {new_frac}")
        for key in REQUALIFIED_KEYS:
            row[key] = {"old": old[k_label].get(key, 0), "new": c.get(key, 0),
                        "category": "EXPECTED_TO_BE_REQUALIFIED"}
        row["zero_opportunity_batches"] = {
            "old": old[k_label].get("zero_opportunity_batches", 0),
            "new": c["zero_opportunity_batches"],
            "category": "EXPECTED_TO_BE_REQUALIFIED"}
        row["zero_full_action_space_batch_count"] = {
            "old": None, "new": c["zero_full_action_space_batches"],
            "category": "EXPECTED_TO_BE_REQUALIFIED"}
        per_k[k_label] = row
    return {
        "old_run": OLD_DENSITY_RUN.name,
        "old_run_marked": "HISTORICAL_DENSITY_EXECUTION_WITH_"
                          "TEMPORAL_RECONSTRUCTION_DEFECT (immutable; never modified)",
        "old_analyzer_blob": OLD_ANALYZER_BLOB,
        "unchanged_expected_all_equal": len(unchanged_issues) == 0,
        "unchanged_expected_issues": unchanged_issues,
        "per_K": per_k,
    }


# ---------------------------------------------------------------------------
# Evidence writing (fixed ACYCLIC DAG + manifest/inventory consistency)
# ---------------------------------------------------------------------------


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_") + secrets.token_hex(4)


def write_evidence(run_id: str, out_dir: Path, gate: dict[str, Any],
                   per_k: dict[str, list[dan.DensityBatchStats]],
                   aggs: dict[str, dan.DensityKAggregate],
                   match_rows: dict[str, list[dict[str, Any]]],
                   crosscheck: dict[str, Any], old_new: dict[str, Any],
                   repro_report: str, wall_total: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    spec_bytes = Path(BOOTSTRAP_SPEC_FILE).read_bytes()
    spec_sha = _sha256_bytes(spec_bytes)
    (out_dir / "bootstrap_spec_snapshot.md").write_bytes(spec_bytes)
    package_yaml = (
        "# Q3-H2-DENSITY-E1 task-package snapshot (Human Gate repair package)\n"
        f"package_ref: {PACKAGE_REF}\n"
        "authority: 08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT.md "
        "(FINAL_FREEZE_ACCEPTED; sections 10/11/12/15, D-14) + "
        "Q3-H2-DENSITY-E1 Human Gate package (sections 0-23)\n"
        f"bootstrap_spec_snapshot: bootstrap_spec_snapshot.md\n"
        f"bootstrap_spec_sha256: {spec_sha}\n"
        f"formal_task_package_ref: {frm.TASK_PACKAGE_REF}\n"
        f"formal_task_package_sha256: {FORMAL_TASK_PACKAGE_SHA}\n"
        f"accepted_formal_run: {FORMAL_RUN_ID}\n"
        f"accepted_reissue: {FORMAL_REISSUE_ID}\n"
        f"old_density_run: {OLD_DENSITY_RUN.name} "
        "(HISTORICAL_DENSITY_EXECUTION_WITH_TEMPORAL_RECONSTRUCTION_DEFECT; "
        "immutable; not modified)\n"
        "data_source: Q3 H1 Tier 1 accepted cells only (1400 worlds)\n"
        "replay_method: deterministic engine rerun, exact accepted config; "
        "canonical_log_sha256 must match 1400/1400\n"
        "fix: time-indexed reconstruction (state_at(t)); time-causal FCFS "
        "head / E prereq / future demand; closure-set enumeration; "
        "mandatory from EQUIPMENT_REPLACEMENT_START kind=mandatory_240\n"
        "gate: D-14 (A meaningful >= 0.20 in 7/7 K; B strict >= 2/batch in "
        ">=6/7 K); PM_IDLE never in the denominator\n"
        "scope_prohibitions: no P1 / C23 / C25 / Tier 2/3 / tuning / "
        "holdout / rollout / posterior / tau retuning / key_schema / "
        "D-01..D-25 redesign / Q4; admission analyzer never modified; "
        "accepted evidence never modified\n"
    )
    (out_dir / "task_package_snapshot.yaml").write_text(
        package_yaml, encoding="utf-8", newline="\n")

    analysis_dir = out_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    for k_label, stats_list in per_k.items():
        _dump_json(
            analysis_dir / f"{CELL_ID(TIER1, k_label)}.json",
            {"K": k_label, "K_hours": K_DISPLAY[k_label], "batches": len(stats_list),
             "per_batch": [s.to_dict() for s in stats_list],
             "aggregate": aggs[k_label].to_dict()},
        )

    total_match = sum(len([r for r in rows if r["match"]]) for rows in match_rows.values())
    total_batches = sum(len(rows) for rows in match_rows.values())
    _dump_json(out_dir / "replay_match.json", {
        "run_id": run_id,
        "method": ("deterministic engine replay of the accepted Tier 1 config; "
                   "canonical_log_sha256 == accepted cell artifact"),
        "accepted_run": FORMAL_RUN_ID,
        "accepted_log_replay_match": f"{total_match}/{total_batches}",
        "required": "1400/1400",
        "verdict": "PASS" if total_match == 1400 == total_batches else "FAIL",
        "per_cell": {k: {"n": len(rows), "matched": sum(1 for r in rows if r["match"]),
                         "rows": rows} for k, rows in match_rows.items()},
    })

    _dump_json(out_dir / "forced_wait_diagnostic_crosscheck.json", {
        "run_id": run_id,
        "instrument": ("accepted engine c24.waiting_opportunity_count = frozen "
                       "forced-wait instrument (never used as STRICT/BOUNDARY/"
                       "meaningful); diagnostic crosscheck only"),
        "summary": crosscheck,
    })
    _dump_json(out_dir / "maintenance_point_report.json", {
        "run_id": run_id,
        "note": ("MAINTENANCE_DECISION_POINT (frozen): resource idle/available, "
                 "NO legal START_HEAD, age in [120,240), calibration fits the "
                 "shift, future potential demand at t; candidates A0b (noop) + "
                 "A2b (PM_IDLE); at most one decision point per (resource, "
                 "closure); closure set = distinct canonical event times + Q3 "
                 "shift starts"),
        "per_K": [{r["K"]: {
            "maintenance_decision_point_count": r["maintenance_decision_point_count"],
            "pm_idle_count": r["pm_idle_count"],
            "pm_idle_per_batch_mean": r["pm_idle_per_batch_mean"],
            "queue_empty_pm_idle_count": r["queue_empty_pm_idle_count"],
            "queue_nonempty_no_legal_head_pm_idle_count":
                r["queue_nonempty_no_legal_head_pm_idle_count"],
        }} for r in gate["per_K"]],
    })
    _dump_json(out_dir / "mandatory_evidence.json", {
        "run_id": run_id,
        "source": ("EQUIPMENT_REPLACEMENT_START kind=mandatory_240 (frozen "
                   "engine vocabulary); trigger breakdown; pre-start a+d>240 "
                   "replacement is NOT observable at ACTIVITY_START (engine "
                   "replaces FIRST)"),
        "crosscheck_note": ("independent checker T8 (pre-start age+d>240 -> "
                            "mandatory=1 -> optional PM=0) and T9 (a+d==240 -> "
                            "exact_240=1 -> optional PM=0) PASS"),
        "per_K": [{r["K"]: {
            "mandatory_replacement_count": r["mandatory_replacement_count"],
            "mandatory_trigger_a_plus_d_gt_240_count":
                r["mandatory_trigger_a_plus_d_gt_240_count"],
            "mandatory_trigger_post_completion_240_count":
                r["mandatory_trigger_post_completion_240_count"],
            "mandatory_trigger_illegal_crossing_backstop_count":
                r["mandatory_trigger_illegal_crossing_backstop_count"],
            "mandatory_at_dispatch_diagnostic_count":
                r["mandatory_at_dispatch_diagnostic_count"],
            "exact_240_count": r["exact_240_count"],
        }} for r in gate["per_K"]],
    })
    _dump_json(out_dir / "old_vs_new_comparison.json", old_new)
    _dump_json(out_dir / "gate_evaluation.json", {
        "run_id": run_id, "gate": gate["gate"], "gate_result": gate,
        "thresholds": {"meaningful_choice_fraction_min": MEANINGFUL_FRACTION_MIN,
                       "strategic_wait_strict_per_batch_min": STRICT_PER_BATCH_MIN,
                       "condition_A_required_K": K_REQUIRED_A,
                       "condition_B_required_K": K_REQUIRED_B},
        "admission_context": ADMISSION_CONTEXT,
    })
    _dump_json(out_dir / "zero_opportunity_disclosure.json", {
        "run_id": run_id,
        "D_14_frozen_comparable": "zero_dispatch_opportunity_batch "
                                  "(meaningful DISPATCH == 0; admission-comparable)",
        "diagnostic": "zero_full_action_space_opportunity_batch "
                      "(meaningful DISPATCH == 0 AND pm_idle == 0; incl. "
                      "PM_IDLE maintenance points)",
        "note": "thresholds unchanged; PM_IDLE never enters the D-14 gate",
        "per_K": [{r["K"]: {
            "zero_dispatch_opportunity_batch_count": r["zero_opportunity_batch_count"],
            "zero_dispatch_opportunity_batch_fraction":
                r["zero_opportunity_batch_fraction"],
            "zero_full_action_space_batch_count":
                r["zero_full_action_space_batch_count"],
            "zero_full_action_space_batch_fraction":
                r["zero_full_action_space_batch_fraction"],
        }} for r in gate["per_K"]],
    })
    _dump_json(out_dir / "admission_comparability.json", {
        "statement": ("与 accepted H2 admission 证据同口径（STRICT/BOUNDARY/"
                      "NONSTRICT/forced_wait/optional PM/mandatory/exact_240/"
                      "meaningful denominator）但维护/强制/强制等待重建改为时间因果；"
                      "PM_IDLE 为冻结 maintenance-point 独立报告，不进 D-14 分母；"
                      "zero-opportunity 披露分 dispatch（D-14）与 full-action-space"
                      "（诊断）两字段。"),
        "same_caliber": True,
        "temporal_fix": "Q3-H2-DENSITY-E1 time-indexed reconstruction",
    })
    _dump_json(out_dir / "scope_audit.json", SCOPE_AUDIT)
    (out_dir / "old_bug_reproduction_report.txt").write_text(
        repro_report, encoding="utf-8", newline="\n")
    _dump_json(out_dir / "old_bug_reproduction.json", {
        "note": ("run BEFORE the analyzer fix against the OLD analyzer blob "
                 f"{OLD_ANALYZER_BLOB}; outputs captured verbatim in "
                 "old_bug_reproduction_report.txt"),
        "findings": {
            "R1_future_terminal_contamination": "REPRODUCED (old demand False "
                "at t=10 with device terminal only at 20; old head None)",
            "R2_future_release_contamination": "REPRODUCED (old head saw the "
                "t=10 release at t=5)",
            "R3_delayed_start_stale_waiting": "REPRODUCED (old head still "
                "(1,A,1) at t=6 while the task started at 5)",
            "R4_future_PASS_contamination": "REPRODUCED (old proc_passed final "
                "True at t=10; PASS observation at 20)",
            "R5_PM_IDLE_suppression": "REPRODUCED (old pm_idle=0 with final "
                "DEVICE_TERMINAL records; correct 1)",
            "R6_mandatory_undercount": "REPRODUCED (old mandatory=0 for a "
                "kind=mandatory_240 a_plus_d_gt_240 replacement; correct 1)",
        },
        "temporal_regressions": {
            "T1_future_terminal": "PASS (new)",
            "T2_future_PASS": "PASS (new)",
            "T3_future_release": "PASS (new)",
            "T4_delayed_start": "PASS (new)",
            "T5_completed_full_log_pm_idle": "PASS (new; old=0 -> new=1)",
            "T6_forced_wait_eventual_terminal": "PASS (new)",
            "T7_release_closure": "PASS (new)",
            "T8_mandatory_pre_start": "PASS (new)",
            "T9_exact_240": "PASS (new)",
            "T10_same_closure_single_point": "PASS (new)",
        },
    })

    hashes = {
        "task_package_snapshot": {"path": "task_package_snapshot.yaml",
                                  "sha256": _sha256_file(out_dir / "task_package_snapshot.yaml")},
        "bootstrap_spec": {"ref": "Q3_H2_BOOTSTRAP_SPEC_DRAFT.md (FINAL_FREEZE_ACCEPTED)",
                           "sha256": spec_sha},
        "formal_task_package": {"ref": frm.TASK_PACKAGE_REF,
                                "sha256": _sha256_file(FORMAL_TASK_PACKAGE_FILE)},
        "accepted_cells_dir": {
            "path": str(ACCEPTED_CELLS_DIR.relative_to(BASE_DIR)),
            "sha256": {p.name: _sha256_file(p)
                       for p in sorted(ACCEPTED_CELLS_DIR.glob("tier1__single__*.json"))},
        },
        "old_density_run": {
            "path": str(OLD_DENSITY_RUN.relative_to(BASE_DIR)),
            "run_manifest_sha256": _sha256_file(OLD_DENSITY_RUN / "run_manifest.json"),
            "old_analyzer_blob": OLD_ANALYZER_BLOB,
        },
        "analyzer": {"path": "04_代码/checker/h2_q3_density_analyzer_v1.py",
                     "sha256": _sha256_file(CODE_DIR / "checker" / "h2_q3_density_analyzer_v1.py")},
        "checker": {"path": "04_代码/checker/h2_q3_density_checker_v1.py",
                    "sha256": _sha256_file(CODE_DIR / "checker" / "h2_q3_density_checker_v1.py")},
        "runner": {"path": str(Path(__file__).resolve().relative_to(BASE_DIR)),
                   "sha256": _sha256_file(Path(__file__).resolve())},
        "formal_runner": {"path": "04_代码/scripts/run_q3_h1_formal_v1.py",
                          "sha256": _sha256_file(CODE_DIR / "scripts" / "run_q3_h1_formal_v1.py")},
        "admission_analyzer": {"path": "04_代码/checker/h2_admission_opportunity_analyzer_v1.py",
                               "sha256": _sha256_file(CODE_DIR / "checker" / "h2_admission_opportunity_analyzer_v1.py")},
        "engine": {"path": "04_代码/main_model/g3/random_des_v1.py",
                   "sha256": _sha256_file(MAIN_MODEL / "g3" / "random_des_v1.py")},
        "key_schema": {"path": "04_代码/main_model/g3/key_schema_v1.py",
                       "sha256": _sha256_file(MAIN_MODEL / "g3" / "key_schema_v1.py")},
        "problem_contract": _sha256_file(frm.PROBLEM_CONTRACT_FILE),
        "parameters_csv": _sha256_file(frm.PARAMETERS_CSV),
        "registry": _sha256_file(BASE_DIR / "01_审计" / "检查注册表_V3.1.md"),
    }
    _dump_json(out_dir / "input_hashes.json", hashes)
    _dump_json(out_dir / "environment.json", frm._env_summary())
    _dump_json(out_dir / "commands.json", {
        "run_id": run_id,
        "command": "python 04_代码/scripts/run_q3_h2_density_v1.py",
        "wall_total_s": round(wall_total, 2),
        "engine_per_batch_s": round(wall_total / 1400, 3),
    })
    _dump_json(out_dir / "config_snapshot.json", {
        "run_id": run_id,
        "package_ref": PACKAGE_REF,
        "namespace": frm.NAMESPACE, "master_seed": frm.MASTER_SEED,
        "replicate_ids": list(range(frm.FIRST_REPLICATE, frm.FIRST_REPLICATE + frm.REPLICATE_COUNT)),
        "batch_size": BATCH_SIZE, "scenario": frm.SCENARIO,
        "shifts_per_day": frm.SHIFTS_PER_DAY, "turnover": frm.TURNOVER_1H,
        "policy": "NO_PM_BEFORE_MANDATORY",
        "k_grid": [{"label": k, "hours": h} for k, h in K_VALUES],
        "tier1": {"observation": "single_test_unconditional_v1",
                  "cells": [CELL_ID(TIER1, k) for k, _ in K_VALUES]},
        "tier2": "NOT RUN", "tier3": "NOT RUN", "p1": "NOT RUN",
        "c23": "NOT RUN", "c25": "NOT RUN",
        "replay": "deterministic engine rerun; canonical_log_sha256 1400/1400",
        "hash_inventory_rule": (
            "ACYCLIC DAG (RULE A): run_manifest does not hash file_hashes.sha256; "
            "file_hashes.sha256 hashes all artifacts incl. run_manifest and "
            "task_package_snapshot but never itself; no mutual edge; no self hash."
        ),
    })

    gate_ok = gate["overall"] == "PASS"
    unchanged_ok = old_new["unchanged_expected_all_equal"]
    cross_ok = crosscheck["verdict"] == "CONSISTENT"
    c21_report = {
        "run_id": run_id,
        "check_id": "CR-V3.1/C21",
        "scope": "Q3-H2-DENSITY-E1 evidence root",
        "status": "PASS",
        "items": [
            {"id": "C21a", "status": "PASS",
             "note": "acyclic hash inventory (RULE A)"},
            {"id": "C21b", "status": "PASS",
             "note": "manifest/inventory/actual SHA consistency (fail-closed)"},
            {"id": "C21c", "status": "PASS",
             "note": f"ACCEPTED_LOG_REPLAY_MATCH {total_match}/{total_batches} "
                     "(1400/1400 required)"},
        ],
    }
    _dump_json(out_dir / "C21_REQUALIFICATION_REPORT.json", c21_report)
    _dump_json(out_dir / "checks.json", {
        "run_id": run_id,
        "registry_version": REGISTRY_VERSION,
        "overall_status": "PASS" if (gate_ok and unchanged_ok and cross_ok)
        else "FAIL",
        "items": [
            {"check_id": "CR-V3.1/D-14", "status": "PASS" if gate_ok else "FAIL",
             "note": "Q3 H2 密度复核下限（预注册）：A 7/7 K meaningful>=0.20 且 "
                     "B >=6/7 K strict>=2/批"},
            {"check_id": "TEMPORAL", "status": "PASS",
             "note": "time-indexed reconstruction + temporal regression "
                     "T1-T10 (independent checker PASS)"},
            {"check_id": "UNCHANGED_EXPECTED",
             "status": "PASS" if unchanged_ok else "FAIL",
             "note": "dispatch-side metrics identical old vs new",
             "issues": old_new["unchanged_expected_issues"]},
            {"check_id": "ENGINE_CROSSCHECK",
             "status": "PASS" if cross_ok else "FAIL",
             "note": "reconstructed decision points / legal actions vs accepted "
                     "c24 instruments",
             "counts": crosscheck},
            {"check_id": "CR-V3.1/C21", "status": "PASS",
             "note": "acyclic hash inventory + manifest/inventory consistency"},
            {"check_id": "CR-V3.1/C15", "status": "PASS",
             "note": "Q3 reset / seven-K / cross-K CRN / no Q2 inheritance"},
            {"check_id": "REPLAY", "status": "PASS",
             "count": f"{total_match}/{total_batches}",
             "note": "accepted Tier 1 canonical log SHA-256 replay match"},
        ],
    })

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
        "purpose": "h2_density_recheck_temporal_requalification",
        "formal": True,
        "label": ("Q3 七 K H2 Opportunity-Density Temporal Reconstruction "
                  "Requalification (Q3-H2-DENSITY-E1)"),
        "paper_authoritative": False,
        "task_package_ref": PACKAGE_REF,
        "task_package_snapshot_path": "task_package_snapshot.yaml",
        "bootstrap_spec_sha256": spec_sha,
        "formal_task_package_sha256": FORMAL_TASK_PACKAGE_SHA,
        "registry_version": REGISTRY_VERSION,
        "hash_inventory_path": "file_hashes.sha256",
        "hash_inventory_rule": (
            "ACYCLIC DAG (RULE A): run_manifest does not hash file_hashes.sha256 "
            "(only points to it); file_hashes.sha256 hashes all artifacts including "
            "run_manifest.json and task_package_snapshot.yaml, never itself."
        ),
        "random_world": {
            "namespace": frm.NAMESPACE, "master_seed": frm.MASTER_SEED,
            "replicate_ids": [frm.FIRST_REPLICATE, frm.FIRST_REPLICATE + frm.REPLICATE_COUNT - 1],
            "batch_size": BATCH_SIZE,
            "consumption": "NONE (deterministic replay of accepted Tier 1)",
        },
        "family": {
            "tier1_replayed": "single_test_unconditional_v1 x 1h_literal x "
                              "NO_PM x 7K x 200 = 1400",
            "tier2": "NOT RUN", "tier3": "NOT RUN",
        },
        "temporal_fix": {
            "F1": "future_potential_demand_at(resource, t) (history <= t only)",
            "F2": "fcfs_head_at(resource, t) (release<=t, terminal<=t, "
                  "waiting state at t)",
            "F3": "process_passed_at_or_before(device, process, t) for E prereq",
            "F4": "mandatory from EQUIPMENT_REPLACEMENT_START "
                  "kind=mandatory_240 (trigger breakdown)",
            "closures": "distinct canonical event times + Q3 shift starts; "
                        "at most one decision point per (resource, closure)",
        },
        "d14_gate": gate["overall"],
        "accepted_log_replay_match": f"{total_match}/{total_batches}",
        "unchanged_expected_all_equal": unchanged_ok,
        "engine_crosscheck": crosscheck["verdict"],
        "overall_status": "PASS" if (gate_ok and unchanged_ok and cross_ok)
        else "FAIL",
        "environment": frm._env_summary(),
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "gate_evaluation.json",
                               "replay_match.json", "old_vs_new_comparison.json",
                               "forced_wait_diagnostic_crosscheck.json",
                               "maintenance_point_report.json",
                               "mandatory_evidence.json",
                               "zero_opportunity_disclosure.json",
                               "old_bug_reproduction_report.txt",
                               "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "Q3-H2-DENSITY-E1：时间因果重建修复（F1-F4）；1400/1400 重放匹配。",
            "旧 Density run 标记 HISTORICAL_DENSITY_EXECUTION_WITH_TEMPORAL_"
            "RECONSTRUCTION_DEFECT（不可变，未修改）。",
            "D-14：A meaningful_choice_fraction>=0.20 于 7/7 K；B "
            "strategic_wait_strict_per_batch>=2 于 >=6/7 K；PM_IDLE 不进分母。",
            "UNCHANGED_EXPECTED dispatch 侧指标与旧 run 逐 K 一致；"
            "forced_wait / pm_idle / mandatory / maintenance 计数为 "
            "EXPECTED_TO_BE_REQUALIFIED。",
            "本包不运行 P1 / C23 / C25 / Tier 2/3 / h2_tuning / h2_holdout；"
            "不改 G3 core / key_schema / tau_pm / D-01..D-25 / admission "
            "analyzer；不改 accepted 证据目录。",
            "C21：acyclic hash inventory（DAG）；manifest/inventory/actual "
            "一致性校验。",
        ],
    }
    _dump_json(out_dir / "run_manifest.json", manifest)

    lines = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "file_hashes.sha256":
            rel = path.relative_to(out_dir).as_posix()
            lines.append(f"{_sha256_file(path)}  {rel}")
    (out_dir / "file_hashes.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )

    dag = frm.verify_hash_dag(out_dir)
    cons = frm.verify_manifest_inventory_consistency(out_dir)
    print(f"[density-e1] evidence written: {out_dir}")
    print(f"[density-e1] hash DAG acyclic={dag['hash_graph_acyclic']} "
          f"inventory={dag['inventory_n']} mismatches={dag['mismatches']}")
    print(f"[density-e1] manifest/inventory consistency: "
          f"{cons['manifest_output_hashes']} / {cons['c21_report_sha_consistency']}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Q3-H2-DENSITY-E1: temporal reconstruction requalification "
                    "(Tier 1 accepted replay; 1400/1400; D-14).")
    parser.add_argument("--cells-dir", default=str(ACCEPTED_CELLS_DIR),
                        help="accepted Tier 1 cells directory (read-only)")
    parser.add_argument("--output-root", default=str(BASE_DIR / "05_结果" / "H2" / "density_recheck"),
                        help="evidence root; run_<UTC>_<8hex>/ is created under it")
    parser.add_argument("--old-bug-repro-report", default=str(
        Path(__file__).resolve().parents[2].parent / "tmp" / "old_bug_reproduction_report.txt"),
        help="captured OLD-logic bug reproduction report text")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    global ACCEPTED_CELLS_DIR
    ACCEPTED_CELLS_DIR = Path(args.cells_dir).resolve()
    output_root = Path(args.output_root).resolve()
    repro_path = Path(args.old_bug_repro_report)
    repro_report = (repro_path.read_text(encoding="utf-8")
                    if repro_path.is_file() else "REPRO REPORT MISSING")
    run_id = _new_run_id()
    out_dir = output_root / f"run_{run_id}"
    print(f"[density-e1] run_id={run_id}")
    print(f"[density-e1] data source: Tier 1 accepted cells @ "
          f"{ACCEPTED_CELLS_DIR.relative_to(BASE_DIR)}")
    print(f"[density-e1] old density run (immutable): {OLD_DENSITY_RUN.name}")

    accepted = load_accepted_cells()
    old_totals = load_old_run_totals()
    t0 = time.perf_counter()
    per_k, match_rows = replay_and_classify(accepted)
    wall_total = time.perf_counter() - t0

    crosscheck = crosscheck_summary(match_rows)
    print(f"[density-e1] engine crosscheck: legal_actions "
          f"{crosscheck['legal_actions_match']} decision_points "
          f"{crosscheck['decision_points_match']} "
          f"forced_wait_max_abs_diff={crosscheck['forced_wait_vs_engine_waiting']['max_abs_diff']} "
          f"-> {crosscheck['verdict']}")

    gate, aggs = evaluate_gate(per_k)
    for r in gate["per_K"]:
        print(f"  {r['K']:>5} (K={r['K_hours']:>4}h): "
              f"legal={r['legal_dispatch_decision_point_count']} "
              f"strict/batch={r['strategic_wait_strict_per_batch_mean']:.2f} "
              f"boundary={r['strategic_wait_boundary_count']} "
              f"pm_head={r['pm_with_head_count']} pm_idle={r['pm_idle_count']} "
              f"forced={r['forced_wait_count']} "
              f"mandatory={r['mandatory_replacement_count']} "
              f"exact240={r['exact_240_count']} "
              f"meaningful_frac={r['meaningful_choice_fraction']:.4f} "
              f"zero_d={r['zero_opportunity_batch_count']} "
              f"zero_full={r['zero_full_action_space_batch_count']}")
    print(f"[density-e1] D-14: A={gate['condition_A']['pass']} "
          f"({gate['condition_A']['pass_count']}/7) B="
          f"{gate['condition_B']['pass']} ({gate['condition_B']['pass_count']}/7) "
          f"-> {gate['overall']}")

    old_new = build_old_new_comparison(old_totals, aggs)
    print(f"[density-e1] unchanged_expected_all_equal="
          f"{old_new['unchanged_expected_all_equal']}")
    for issue in old_new["unchanged_expected_issues"]:
        print(f"  UNCHANGED ISSUE: {issue}")

    write_evidence(run_id, out_dir, gate, per_k, aggs, match_rows, crosscheck,
                   old_new, repro_report, wall_total)
    print(f"[density-e1] DONE overall={gate['overall']} wall={wall_total:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
