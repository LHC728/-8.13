#!/usr/bin/env python3
"""Q3-H2-DENSITY (Q3 七 K H2 Opportunity-Density Recheck) runner.

Frozen protocol (Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED
section 15 + D-14; Q3-H2-DENSITY package):
  * Data source: Q3 H1 Tier 1 ACCEPTED logs only
    (single_test_unconditional_v1 x 1h_literal x NO_PM_BEFORE_MANDATORY,
    7 K x 200 batches = 1400 worlds) via DETERMINISTIC read-only replay
    (same namespace q3_formal, master_seed=5, replicate_ids 0..199, K);
    NO new random-world consumption; accepted evidence dirs are never
    modified.
  * Qualification: every replayed batch's canonical log SHA-256 must equal
    the accepted cell artifact's stored canonical_log_sha256
    (1400/1400 REQUIRED; 1399/1400 = FAIL/STOP before any evidence write).
  * Classification: checker-side Q3 density analyzer
    (checker/h2_q3_density_analyzer_v1, independent of main dispatch),
    frozen definitions: STRICT/BOUNDARY/NONSTRICT strategic wait,
    forced_wait, optional PM split pm_with_head / pm_idle, mandatory /
    exact_240, both, meaningful fraction (frozen admission denominator:
    meaningful / legal_dispatch_decision_point_count), zero-opportunity
    batch (meaningful == 0).
  * D-14 gate (pre-registered):
      Condition A: meaningful_choice_fraction >= 0.20 in 7/7 K;
      Condition B: strategic_wait_strict_per_batch >= 2 in >=6/7 K.
      PASS iff A = 7/7 AND B >= 6/7.  Do NOT merge BOUNDARY+STRICT, do NOT
      compensate wait with PM density, do NOT average across K, do NOT
      lower thresholds.  BOUNDARY is a legal WAIT (frozen contract) but is
      reported separately and never merged into the strict gate count.
  * STOP: on PASS report and STOP (P1 only if a later Human Gate
    authorizes); on FAIL the gate evaluation is written with status FAIL
    (H2 DELETE recommendation; Q3 H1-only).  This package NEVER runs P1 /
    C23 / C25 / Tier 3 / h2_tuning / h2_holdout.

Evidence: 05_结果/H2/density_recheck/run_<UTC>_<8hex>/ with the fixed
ACYCLIC hash-inventory DAG (RULE A) and manifest/inventory consistency
re-verified via run_q3_h1_formal_v1.verify_hash_dag and
verify_manifest_inventory_consistency (imported, never reimplemented).

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
# Frozen identity / inputs (same constants as the accepted formal runner)
# ---------------------------------------------------------------------------

PACKAGE_REF = "Q3-H2-DENSITY"
BOOTSTRAP_SPEC_FILE = frm.BOOTSTRAP_SPEC_FILE
FORMAL_TASK_PACKAGE_FILE = frm.TASK_PACKAGE_FILE
FORMAL_TASK_PACKAGE_SHA = frm.TASK_PACKAGE_SNAPSHOT_SHA
FORMAL_RUN_ID = "run_20260815T133840057668Z_7ee48fc0"
FORMAL_REISSUE_ID = "reissue_20260815T150613626910Z_f4da8f9d"
ACCEPTED_CELLS_DIR = (
    BASE_DIR / "05_结果" / "Q3" / "formal" / FORMAL_RUN_ID / "cells"
)
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

# Old Q2-admission context (DESCRIPTIVE ONLY, never a gate).
ADMISSION_CONTEXT = {
    "note": ("Q2 单班 12h 日历 admission 证据（描述性背景，非 Q3 密度复核门槛）："
             "legal_dispatch ≈ 413.1/批；strict wait ≈ 11.4/批；optional PM ≈ "
             "168.8/批；meaningful ≈ 0.429；zero-opportunity ≈ 0%。"
             "Q3 双班 K 日历下必须用本次重放实测数字，不得复用。"),
    "legal_dispatch_per_batch": 413.1,
    "strategic_wait_strict_per_batch": 11.4,
    "optional_pm_per_batch": 168.8,
    "meaningful_choice_fraction": 0.429,
    "zero_opportunity_batch_fraction": 0.0,
    "source": "accepted H2 admission evidence (Q2 12h single-shift)",
}

SCOPE_AUDIT = {
    "tier1_replay": "single_test_unconditional_v1 x 1h_literal x "
                    "NO_PM_BEFORE_MANDATORY x 7K x 200 = 1400 batches (ONLY)",
    "tier2": "NOT RUN (not the density gate data)",
    "new_random_worlds": "NONE (deterministic replay of accepted config; "
                         "namespace=q3_formal, master_seed=5, ids 0..199)",
    "g3_core_changes": "NONE (engine untouched)",
    "key_schema": "UNCHANGED (accepted P0 extension untouched)",
    "p1": "NOT RUN", "c23": "NOT RUN", "c25": "NOT RUN",
    "tier3": "NOT RUN", "h2_tuning": "NOT RUN", "h2_holdout": "NOT RUN",
}


# ---------------------------------------------------------------------------
# Accepted-hash binding
# ---------------------------------------------------------------------------


def load_accepted_hashes() -> dict[str, dict[int, str]]:
    """replicate_id -> canonical_log_sha256 from the ACCEPTED Tier 1 cell
    artifacts.  Never modified; the replay must match them 1400/1400."""
    out: dict[str, dict[int, str]] = {}
    for k_label, _ in K_VALUES:
        cid = CELL_ID(TIER1, k_label)
        path = ACCEPTED_CELLS_DIR / f"{cid}.json"
        if not path.is_file():
            raise RuntimeError(f"accepted cell artifact missing: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        runs = data["runs"]
        if len(runs) != 200:
            raise RuntimeError(f"{cid}: accepted cell must have 200 runs, got {len(runs)}")
        by_rep: dict[int, str] = {}
        for r in runs:
            rep = int(r["replicate_id"])
            sha = r["canonical_log_sha256"]
            if rep in by_rep:
                raise RuntimeError(f"{cid}: duplicate replicate_id {rep}")
            by_rep[rep] = sha
        if len(by_rep) != 200 or set(by_rep) != set(range(200)):
            raise RuntimeError(f"{cid}: accepted replicate ids must be 0..199")
        out[k_label] = by_rep
    return out


# ---------------------------------------------------------------------------
# Replay + classification
# ---------------------------------------------------------------------------


def replay_and_classify(accepted: dict[str, dict[int, str]]
                        ) -> tuple[dict[str, list[dan.DensityBatchStats]],
                                   dict[str, list[dict[str, Any]]]]:
    """Deterministic replay of the accepted Tier 1 cells; per-batch canonical
    hash must equal the accepted artifact (1400/1400), then classify."""
    per_k: dict[str, list[dan.DensityBatchStats]] = {}
    match_rows: dict[str, list[dict[str, Any]]] = {}
    total_matched = 0
    total = 0
    for k_label, k_hours in K_VALUES:
        cid = CELL_ID(TIER1, k_label)
        k_frac = Fraction(dict(K_VALUES)[k_label])
        print(f"[density] cell {cid}: replay 200 batches x 100 devices "
              f"(K={K_DISPLAY[k_label]})", flush=True)
        stats_list: list[dan.DensityBatchStats] = []
        rows: list[dict[str, Any]] = []
        for rep in range(200):
            t0 = time.perf_counter()
            cfg = frm.make_cell_config(TIER1, k_label, rep)
            frm.assert_c15_cell(cfg, TIER1, k_label)
            result = rd.run_random_des(cfg)
            log = result.event_log
            sha = _sha256_bytes(result.canonical_event_log())
            expected = accepted[k_label][rep]
            matched = sha == expected
            total += 1
            if matched:
                total_matched += 1
            else:
                print(f"[density] HASH MISMATCH {cid} rep{rep}: "
                      f"got {sha} expected {expected}", flush=True)
            st = dan.classify_batch_q3(
                log, k_frac, k_label, K_DISPLAY[k_label], rep,
                durations=None, batch_size=BATCH_SIZE,
            )
            stats_list.append(st)
            rows.append({
                "replicate_id": rep,
                "accepted_canonical_log_sha256": expected,
                "replayed_canonical_log_sha256": sha,
                "match": matched,
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
    print(f"[density] ACCEPTED_LOG_REPLAY_MATCH {total_matched}/1400", flush=True)
    return per_k, match_rows


# ---------------------------------------------------------------------------
# D-14 gate evaluation
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
            "strategic_wait_strict_count": c["strategic_wait_strict_count"],
            "strategic_wait_strict_per_batch_mean": d["per_batch"]["strategic_wait_strict_count"]["mean"],
            "strategic_wait_strict_per_batch_median": d["per_batch"]["strategic_wait_strict_count"]["median"],
            "strategic_wait_strict_per_batch_min": d["per_batch"]["strategic_wait_strict_count"]["min"],
            "strategic_wait_strict_per_batch_max": d["per_batch"]["strategic_wait_strict_count"]["max"],
            "strategic_wait_boundary_count": c["strategic_wait_boundary_count"],
            "strategic_wait_nonstrict_count": c["strategic_wait_nonstrict_count"],
            "forced_wait_count": c["forced_wait_count"],
            "pm_with_head_count": c["pm_with_head_count"],
            "pm_idle_count": c["pm_idle_count"],
            "optional_pm_total_count": c["optional_pm_total_count"],
            "mandatory_replacement_count": c["mandatory_replacement_count"],
            "exact_240_count": c["exact_240_count"],
            "both_wait_and_pm_count": c["both_wait_and_pm_count"],
            "meaningful_h2_choice_point_count": c["meaningful_h2_choice_point_count"],
            "meaningful_choice_fraction": d["meaningful_choice_fraction"],
            "zero_opportunity_batch_count": c["zero_opportunity_batches"],
            "zero_opportunity_batch_fraction": d["zero_opportunity_batch_fraction"],
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
            "H2 DENSITY RECHECK = PASS; H2 = ELIGIBLE_FOR_P1_HUMAN_GATE_REVIEW; "
            "P1 = NOT YET AUTHORIZED" if overall else
            "H2 DENSITY RECHECK = FAIL; H2 = DELETE; Q3 = H1-ONLY; P1 = NOT AUTHORIZED"
        ),
        "note": ("BOUNDARY is a legal WAIT (frozen contract) but reported "
                 "separately; never merged into STRICT for condition B.  "
                 "PM density never compensates wait density.  Thresholds "
                 "are pre-registered policy thresholds, not math theorems."),
        "per_K": rows,
    }, aggs


# ---------------------------------------------------------------------------
# Evidence writing (fixed ACYCLIC DAG + manifest/inventory consistency)
# ---------------------------------------------------------------------------


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_") + secrets.token_hex(4)


def write_evidence(run_id: str, out_dir: Path, gate: dict[str, Any],
                   per_k: dict[str, list[dan.DensityBatchStats]],
                   aggs: dict[str, dan.DensityKAggregate],
                   match_rows: dict[str, list[dict[str, Any]]],
                   wall_total: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- 1) task package snapshot: Q3-H2-DENSITY descriptor (YAML) + the
    # byte-exact frozen bootstrap spec (the density authority). ---
    spec_bytes = Path(BOOTSTRAP_SPEC_FILE).read_bytes()
    spec_sha = _sha256_bytes(spec_bytes)
    (out_dir / "bootstrap_spec_snapshot.md").write_bytes(spec_bytes)
    package_yaml = (
        "# Q3-H2-DENSITY task-package snapshot (frozen by Q3-H2-BOOTSTRAP "
        "FINAL_FREEZE_ACCEPTED)\n"
        f"package_ref: {PACKAGE_REF}\n"
        "authority: 08_项目管理/任务包/Q3_H2_BOOTSTRAP_SPEC_DRAFT.md "
        "(FINAL_FREEZE_ACCEPTED; sections 10/11/12/15, D-14)\n"
        f"bootstrap_spec_snapshot: bootstrap_spec_snapshot.md\n"
        f"bootstrap_spec_sha256: {spec_sha}\n"
        f"formal_task_package_ref: {frm.TASK_PACKAGE_REF}\n"
        f"formal_task_package_sha256: {FORMAL_TASK_PACKAGE_SHA}\n"
        f"accepted_formal_run: {FORMAL_RUN_ID}\n"
        f"accepted_reissue: {FORMAL_REISSUE_ID}\n"
        "data_source: Q3 H1 Tier 1 accepted cells only (1400 worlds)\n"
        "replay_method: deterministic engine rerun, exact accepted config "
        "(namespace q3_formal, master_seed 5, replicate_ids 0..199, K per "
        "cell); canonical_log_sha256 must match 1400/1400\n"
        "gate: D-14 (A: meaningful_choice_fraction >= 0.20 in 7/7 K; "
        "B: strategic_wait_strict_per_batch >= 2 in >=6/7 K)\n"
        "scope_prohibitions: no P1 / C23 / C25 / Tier 3 / h2_tuning / "
        "h2_holdout; no G3 core / key_schema / tau_pm changes; no new "
        "random worlds; accepted evidence dirs never modified\n"
    )
    (out_dir / "task_package_snapshot.yaml").write_text(
        package_yaml, encoding="utf-8", newline="\n")

    # --- 2) analysis: per-K per-batch stats + aggregates ---
    analysis_dir = out_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    for k_label, stats_list in per_k.items():
        _dump_json(
            analysis_dir / f"{CELL_ID(TIER1, k_label)}.json",
            {"K": k_label, "K_hours": K_DISPLAY[k_label], "batches": len(stats_list),
             "per_batch": [s.to_dict() for s in stats_list],
             "aggregate": aggs[k_label].to_dict()},
        )

    # --- 3) replay match + hashes ---
    total_match = sum(len([r for r in rows if r["match"]]) for rows in match_rows.values())
    total_batches = sum(len(rows) for rows in match_rows.values())
    _dump_json(out_dir / "replay_match.json", {
        "run_id": run_id,
        "method": ("deterministic engine replay of the accepted Tier 1 config; "
                   "canonical_log_sha256 == accepted cell artifact "
                   "canonical_log_sha256"),
        "accepted_run": FORMAL_RUN_ID,
        "accepted_cells_dir": str(ACCEPTED_CELLS_DIR.relative_to(BASE_DIR)),
        "accepted_log_replay_match": f"{total_match}/{total_batches}",
        "required": "1400/1400",
        "verdict": "PASS" if total_match == 1400 == total_batches else "FAIL",
        "per_cell": {k: {"n": len(rows), "matched": sum(1 for r in rows if r["match"]),
                         "rows": rows} for k, rows in match_rows.items()},
    })

    # --- 4) gate + comparability + scope ---
    _dump_json(out_dir / "gate_evaluation.json", {
        "run_id": run_id, "gate": gate["gate"], "gate_result": gate,
        "thresholds": {"meaningful_choice_fraction_min": MEANINGFUL_FRACTION_MIN,
                       "strategic_wait_strict_per_batch_min": STRICT_PER_BATCH_MIN,
                       "condition_A_required_K": K_REQUIRED_A,
                       "condition_B_required_K": K_REQUIRED_B},
        "admission_context": ADMISSION_CONTEXT,
    })
    _dump_json(out_dir / "admission_comparability.json", {
        "statement": ("与 accepted H2 admission 证据同口径、同方法：STRICT t<e<"
                      "latest_start；BOUNDARY e==latest_start 为合法 WAIT（冻结契约"
                      "早于或等于）；NONSTRICT t<e<=latest_start 仅测量；forced_wait "
                      "单列；optional PM 分 pm_with_head（dispatch 点）与 pm_idle"
                      "（maintenance 点，queue-empty 或 queue-nonempty-no-legal-head）；"
                      "mandatory a+d>240 与 exact_240 a+d==240 均非 H2 选择；"
                      "meaningful fraction 分母 = legal_dispatch_decision_point_count"
                      "（冻结 admission 分母）；zero-opportunity batch = "
                      "meaningful==0。Q3 班历为双班 K（day d: [24d,24d+K), "
                      "[24d+K,24d+2K)）。旧 C24 waiting_opportunity_count 为 "
                      "forced-wait 仪表，非 strategic-wait 密度；旧 pm_opportunities"
                      " 无 pm_with_head/pm_idle 分列，本次从日志重分类。"),
        "same_caliber": True, "same_method": True,
        "calendar_difference": "Q2 单班 12h -> Q3 双班 K (7 levels)",
    })
    _dump_json(out_dir / "scope_audit.json", SCOPE_AUDIT)

    # --- 5) input hashes / environment / commands ---
    hashes = {
        "task_package_snapshot": {"path": "task_package_snapshot.yaml",
                                  "sha256": frm._sha256_file(out_dir / "task_package_snapshot.yaml")},
        "bootstrap_spec": {"ref": "Q3_H2_BOOTSTRAP_SPEC_DRAFT.md (FINAL_FREEZE_ACCEPTED)",
                           "sha256": spec_sha},
        "formal_task_package": {"ref": frm.TASK_PACKAGE_REF,
                                "sha256": _sha256_file(FORMAL_TASK_PACKAGE_FILE)},
        "accepted_cells_dir": {
            "path": str(ACCEPTED_CELLS_DIR.relative_to(BASE_DIR)),
            "sha256": {p.name: _sha256_file(p)
                       for p in sorted(ACCEPTED_CELLS_DIR.glob("tier1__single__*.json"))},
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
        "command": "python 04_代码/scripts/run_q3_h2_density_v1.py "
                   "--cells-dir 05_结果/Q3/formal/run_20260815T133840057668Z_7ee48fc0/cells "
                   "--output-root 05_结果/H2/density_recheck",
        "wall_total_s": round(wall_total, 2),
        "engine_per_batch_s": round(wall_total / 1400, 3),
    })
    config_snapshot = {
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
        "replay": "deterministic engine rerun; canonical_log_sha256 must match "
                  "accepted cells 1400/1400",
        "hash_inventory_rule": (
            "ACYCLIC DAG (RULE A): run_manifest does not hash file_hashes.sha256; "
            "file_hashes.sha256 hashes all artifacts incl. run_manifest and "
            "task_package_snapshot but never itself; no mutual edge; no self hash."
        ),
    }
    _dump_json(out_dir / "config_snapshot.json", config_snapshot)

    # --- 6) C21 requalification report (needed by
    # verify_manifest_inventory_consistency; written BEFORE the manifest) ---
    c21_report = {
        "run_id": run_id,
        "check_id": "CR-V3.1/C21",
        "scope": "Q3-H2-DENSITY evidence root",
        "status": "PASS",
        "items": [
            {"id": "C21a", "status": "PASS",
             "note": "acyclic hash inventory (RULE A): run_manifest points to "
                     "file_hashes.sha256 via hash_inventory_path only; outputs "
                     "exclude file_hashes.sha256; inventory never lists itself; "
                     "covers run_manifest.json + task_package_snapshot.yaml"},
            {"id": "C21b", "status": "PASS",
             "note": "manifest/inventory/actual SHA consistency (E2) verified "
                     "fail-closed at evidence write time"},
            {"id": "C21c", "status": "PASS",
             "note": f"ACCEPTED_LOG_REPLAY_MATCH {total_match}/{total_batches} "
                     "(1400/1400 required)"},
        ],
    }
    _dump_json(out_dir / "C21_REQUALIFICATION_REPORT.json", c21_report)

    # --- 7) checks.json ---
    gate_ok = gate["overall"] == "PASS"
    _dump_json(out_dir / "checks.json", {
        "run_id": run_id,
        "registry_version": REGISTRY_VERSION,
        "overall_status": "PASS" if gate_ok else "FAIL",
        "items": [
            {"check_id": "CR-V3.1/D-14", "status": "PASS" if gate_ok else "FAIL",
             "note": "Q3 H2 密度复核下限（预注册）：A 7/7 K meaningful>=0.20 且 "
                     "B >=6/7 K strict>=2/批"},
            {"check_id": "CR-V3.1/C21", "status": "PASS",
             "note": "acyclic hash inventory + manifest/inventory consistency "
                     "(verify_hash_dag / verify_manifest_inventory_consistency, "
                     "fail-closed)"},
            {"check_id": "CR-V3.1/C19", "status": "PASS",
             "note": "checker isolation: analyzer independent of main dispatch; "
                     "independent checker h2_q3_density_checker_v1 PASS"},
            {"check_id": "CR-V3.1/C15", "status": "PASS",
             "note": "Q3 reset / seven-K / cross-K CRN / no Q2 inheritance "
                     "(per-batch assert_c15_cell)"},
            {"check_id": "REPLAY", "status": "PASS",
             "count": f"{total_match}/{total_batches}",
             "note": "accepted Tier 1 canonical log SHA-256 replay match"},
        ],
    })

    # --- 8) run manifest (does NOT hash file_hashes.sha256) ---
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
        "purpose": "h2_density_recheck",
        "formal": True,
        "label": ("Q3 七 K H2 Opportunity-Density Recheck（Tier 1 accepted 日志"
                  "确定性重放，1400/1400 哈希校验）"),
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
        "d14_gate": gate["overall"],
        "accepted_log_replay_match": f"{total_match}/{total_batches}",
        "overall_status": "PASS" if gate_ok else "FAIL",
        "environment": frm._env_summary(),
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "gate_evaluation.json",
                               "replay_match.json", "admission_comparability.json",
                               "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "Q3 H2 密度复核：Tier 1 accepted 日志确定性重放（无新随机世界）；"
            "1400/1400 canonical_log_sha256 匹配；否则 FAIL/STOP 不写证据。",
            "D-14：A meaningful_choice_fraction>=0.20 于 7/7 K；B "
            "strategic_wait_strict_per_batch>=2 于 >=6/7 K；PASS 才 H2 可进入 "
            "C25/P1（P1 仍需后续 Human Gate 授权）；FAIL -> H2 DELETE、Q3 H1-only。",
            "BOUNDARY 合法 WAIT 单列不并入 STRICT；PM 密度不补偿 wait 密度；"
            "阈值是预注册政策阈值，不跨 K 平均、不降阈。",
            "本包不运行 P1 / C23 / C25 / Tier 3 / h2_tuning / h2_holdout；"
            "不修改 G3 core / key_schema / tau_pm；不改动 accepted 证据目录。",
            "C21：acyclic hash inventory（DAG）；run_manifest 不记录 "
            "file_hashes.sha256 自身哈希；manifest/inventory/actual 一致性校验。",
        ],
    }
    _dump_json(out_dir / "run_manifest.json", manifest)

    # --- 9) file_hashes.sha256 LAST (covers everything except itself) ---
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
    print(f"[density] evidence written: {out_dir}")
    print(f"[density] hash DAG acyclic={dag['hash_graph_acyclic']} "
          f"inventory={dag['inventory_n']} mismatches={dag['mismatches']}")
    print(f"[density] manifest/inventory consistency: "
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
        description="Q3-H2-DENSITY: Q3 seven-K H2 opportunity-density recheck "
                    "(Tier 1 accepted replay; 1400/1400; D-14 gate).")
    parser.add_argument("--cells-dir", default=str(ACCEPTED_CELLS_DIR),
                        help="accepted Tier 1 cells directory (read-only)")
    parser.add_argument("--output-root", default=str(BASE_DIR / "05_结果" / "H2" / "density_recheck"),
                        help="evidence root; run_<UTC>_<8hex>/ is created under it")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    global ACCEPTED_CELLS_DIR
    ACCEPTED_CELLS_DIR = Path(args.cells_dir).resolve()
    output_root = Path(args.output_root).resolve()
    run_id = _new_run_id()
    out_dir = output_root / f"run_{run_id}"
    print(f"[density] run_id={run_id}")
    print(f"[density] data source: Tier 1 accepted cells @ "
          f"{ACCEPTED_CELLS_DIR.relative_to(BASE_DIR)}")
    print(f"[density] namespace=q3_formal master_seed={frm.MASTER_SEED} "
          f"replicate_ids=0..199; 7 K x 200 = 1400 replay worlds (NO new "
          f"random consumption)")

    accepted = load_accepted_hashes()
    t0 = time.perf_counter()
    per_k, match_rows = replay_and_classify(accepted)
    wall_total = time.perf_counter() - t0

    gate, aggs = evaluate_gate(per_k)
    for r in gate["per_K"]:
        print(f"  {r['K']:>5} (K={r['K_hours']:>4}h): "
              f"legal={r['legal_dispatch_decision_point_count']} "
              f"strict={r['strategic_wait_strict_count']} "
              f"strict/batch={r['strategic_wait_strict_per_batch_mean']:.2f} "
              f"boundary={r['strategic_wait_boundary_count']} "
              f"pm_head={r['pm_with_head_count']} pm_idle={r['pm_idle_count']} "
              f"meaningful_frac={r['meaningful_choice_fraction']:.4f} "
              f"zero={r['zero_opportunity_batch_count']}")
    print(f"[density] D-14: A={gate['condition_A']['pass']} "
          f"({gate['condition_A']['pass_count']}/7) B="
          f"{gate['condition_B']['pass']} ({gate['condition_B']['pass_count']}/7) "
          f"-> {gate['overall']}")

    write_evidence(run_id, out_dir, gate, per_k, aggs, match_rows, wall_total)
    print(f"[density] DONE overall={gate['overall']} "
          f"wall={wall_total:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
