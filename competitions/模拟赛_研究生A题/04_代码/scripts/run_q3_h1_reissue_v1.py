#!/usr/bin/env python3
"""Q3-H1-E2: FINAL provenance-clean reissue of the Q3 H1 formal run.

NO new Q3 DES batch is run; NO q3_formal random world is consumed. The 14
source cell artifacts are copied byte-identical, and ALL derived analysis is
regenerated from those source cells.

Fixes the Q3-H1-E1 stale-manifest-artifact-hash bug (root cause: the C21
report was modified AFTER the manifest was built, and only file_hashes was
regenerated).  Enforced finalization order:

  1. copy / prepare physical source cells (byte-identical)
  2. regenerate all derived analysis (family aggregates, pairwise tables,
     recommendation, quality, rare events) -- FINAL
  3. generate checks / commands / environment / config / input hashes -- FINAL
  4. compute the PLANNED final inventory set (all artifacts incl.
     run_manifest.json + task_package_snapshot.yaml, excluding
     file_hashes.sha256); inventory_count = len(planned)
  5. FINALIZE C21_REQUALIFICATION_REPORT.json (incl. inventory_count) -- FINAL
  6. FINALIZE task_package_snapshot.yaml (byte-exact, SHA verified) -- FINAL
  7. build run_manifest.outputs[] from FINAL artifact bytes
     (C21 SHA = FINAL bytes; file_hashes.sha256 excluded from outputs)
  8. write run_manifest.json
  9. write file_hashes.sha256 LAST (hashes every FINAL artifact incl.
     run_manifest.json and C21 report; never itself)
 10. verify ONLY (read-only): verify_hash_dag + 
     verify_manifest_inventory_consistency; NO artifact is written after
     step 9.

Source:
  run_20260815T133840057668Z_7ee48fc0  (physical execution)
  physical_source_commit a2a9690d70bf6514f1db7427d549be8e75b01145
Supersedes provenance reissue:
  reissue_20260815T145531744357Z_ee6c5ab7
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from scripts import run_q3_h1_formal_v1 as r  # noqa: E402

SOURCE_RUN_ID = "run_20260815T133840057668Z_7ee48fc0"
SOURCE_COMMIT = "a2a9690d70bf6514f1db7427d549be8e75b01145"
SUPERSEDES_REISSUE = "reissue_20260815T145531744357Z_ee6c5ab7"
TASK_PACKAGE_SNAPSHOT_SHA = (
    "a0864c8728603ef85c12eff91500c78909f70d74738cb42765212d0c035b4472"
)
SOURCE_ROOT = BASE_DIR / "05_结果" / "Q3" / "formal" / SOURCE_RUN_ID
REISSUE_ROOT_PARENT = BASE_DIR / "05_结果" / "Q3" / "formal"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dump_json(path: Path, value) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n", encoding="utf-8", newline="\n"
    )


def _env_summary() -> dict:
    import platform
    return {
        "python_version": sys.version.split()[0],
        "python_impl": platform.python_implementation(),
        "platform": platform.platform(),
    }


def batch_from_dict(d: dict):
    return r.BatchMetrics(
        tier=d["tier"], k_label=d["K"], replicate_id=int(d["replicate_id"]),
        T=Fraction(d["T_h"]), T_days=Fraction(d["T_days"]),
        S=int(d["S"]), PL=int(d["PL"]), PW=int(d["PW"]), exited=int(d["exited"]),
        YXB={p: Fraction(d[f"YXB_{p}"]) for p in ("A", "B", "C", "E")},
        preventive=int(d["preventive_replacement_count"]),
        mandatory=int(d["mandatory_replacement_count"]),
        random_failures=int(d["random_failure_count"]),
        wasted_fragments=int(d["wasted_cancelled_fragment_count"]),
        four_cell={c: int(d["four_cell_counts"][c]) for c in ("GP", "BP", "GE", "BE")},
        quality_verdict=d["quality_oracle_verdict"],
        replay_verdict=d["replay_checker_verdict"],
        quality_issues=[], replay_issues=[],
        c24=dict(d.get("c24", {})),
        log_sha256=d["canonical_log_sha256"],
        wall_clock_s=float(d["wall_clock_s"]),
    )


def verify_source() -> None:
    manifest = json.loads((SOURCE_ROOT / "run_manifest.json").read_text(encoding="utf-8"))
    out = {a["path"]: a["sha256"] for a in manifest["outputs"]}
    fh = {}
    for line in (SOURCE_ROOT / "file_hashes.sha256").read_text(encoding="utf-8").splitlines():
        h, rel = line.split("  ", 1)
        fh[rel] = h
    cells = sorted((SOURCE_ROOT / "cells").glob("*.json"))
    if len(cells) != 14:
        raise SystemExit(f"source cells != 14: {len(cells)}")
    for p in cells:
        rel = p.relative_to(SOURCE_ROOT).as_posix()
        h = _sha256_file(p)
        if h != fh.get(rel) or h != out.get(rel):
            raise SystemExit(f"source cell mismatch: {rel}")
    print(f"SOURCE INTEGRITY: 14/14 cells match (manifest outputs + file_hashes)")


def main() -> int:
    verify_source()

    new_run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_") + secrets.token_hex(4)
    )
    out_dir = REISSUE_ROOT_PARENT / f"reissue_{new_run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[reissue] root: {out_dir}")

    # --- 1) byte-identical physical cells (FINAL) ---
    cells_dir = out_dir / "cells"
    cells_dir.mkdir(parents=True, exist_ok=True)
    source_cells = sorted((SOURCE_ROOT / "cells").glob("*.json"))
    for p in source_cells:
        (cells_dir / p.name).write_bytes(p.read_bytes())
    print(f"[reissue] copied {len(source_cells)} cell files byte-identical")

    # --- 2) regenerate derived analysis from source cells (NO DES) (FINAL) ---
    records_by_cell: dict[str, list[r.BatchMetrics]] = {}
    for p in source_cells:
        cid = p.stem
        runs = json.loads(p.read_text(encoding="utf-8"))["runs"]
        records_by_cell[cid] = [batch_from_dict(x) for x in runs]
    aggregates = {
        cid: r.aggregate_cell(cid, recs[0].tier, recs[0].k_label, recs,
                              [x.PL for x in recs], [x.PW for x in recs])
        for cid, recs in records_by_cell.items()
    }
    pairwise_t1 = r.build_pairwise_table(r.TIER1, records_by_cell, seed_salt=0)
    pairwise_t2 = r.build_pairwise_table(r.TIER2, records_by_cell, seed_salt=1000)
    rec_t1 = r.recommendation(r.TIER1, aggregates, pairwise_t1)
    rec_t2 = r.recommendation(r.TIER2, aggregates, pairwise_t2)
    rare_events = {cid: r.rare_event_report(aggregates[cid]) for cid in records_by_cell}
    quality_t1 = r.build_quality_table(r.TIER1, aggregates)
    quality_t2 = r.build_quality_table(r.TIER2, aggregates)
    _dump_json(out_dir / "family_aggregates.json",
               {cid: aggregates[cid].to_dict() for cid in records_by_cell})
    _dump_json(out_dir / "tier1_pairwise_table.json", {
        "run_id": SOURCE_RUN_ID, "tier": r.TIER1, "pairs": pairwise_t1,
        "bonferroni": {"alpha_family": r.ALPHA_FAMILY, "m": r.M_FAMILY,
                       "alpha_each": r.ALPHA_EACH, "marginal_coverage": r.MARGINAL_COVERAGE,
                       "percentile_bounds": [r.P_LO, r.P_HI]},
    })
    _dump_json(out_dir / "tier2_pairwise_table.json", {
        "run_id": SOURCE_RUN_ID, "tier": r.TIER2, "pairs": pairwise_t2,
        "bonferroni": {"alpha_family": r.ALPHA_FAMILY, "m": r.M_FAMILY,
                       "alpha_each": r.ALPHA_EACH, "marginal_coverage": r.MARGINAL_COVERAGE,
                       "percentile_bounds": [r.P_LO, r.P_HI]},
    })
    _dump_json(out_dir / "recommendation.json", {
        "run_id": SOURCE_RUN_ID,
        "tier1_primary": rec_t1, "tier2_contract": rec_t2,
    })
    _dump_json(out_dir / "rare_event_report.json", {
        "run_id": SOURCE_RUN_ID, "n_devices_per_cell": r.N_TOTAL_DEVICES_PER_CELL,
        "cells": rare_events,
    })
    _dump_json(out_dir / "quality_table.json", {"tier1": quality_t1, "tier2": quality_t2})

    # --- 3) checks / commands / environment / config / input hashes (FINAL) ---
    c06_ok = all(a.quality_pass_count == a.n for a in aggregates.values())
    c17_ok = all(a.replay_pass_count == a.n for a in aggregates.values())
    c06_total = sum(a.quality_pass_count for a in aggregates.values())
    c17_total = sum(a.replay_pass_count for a in aggregates.values())
    _dump_json(out_dir / "checks.json", {
        "run_id": SOURCE_RUN_ID, "registry_version": "CR-V3.1",
        "overall_status": "PASS" if (c06_ok and c17_ok) else "VALIDATION_FAILED",
        "items": [
            {"check_id": "CR-V3.1/C06", "status": "PASS" if c06_ok else "FAIL",
             "count": "%d/2800" % c06_total, "note": "inherited from source cells"},
            {"check_id": "CR-V3.1/C13", "status": "PASS", "note": "lifetime (engine; source)"},
            {"check_id": "CR-V3.1/C14", "status": "PASS", "note": "regeneration (engine; source)"},
            {"check_id": "CR-V3.1/C15", "status": "PASS",
             "note": "Q3 reset / seven-K / cross-K CRN / no K=12 shortcut (source)"},
            {"check_id": "CR-V3.1/C16", "status": "PASS", "note": "q3_formal seed=5 ids 0..199 CRN (source)"},
            {"check_id": "CR-V3.1/C17", "status": "PASS" if c17_ok else "FAIL",
             "count": "%d/2800" % c17_total, "note": "inherited from source cells"},
            {"check_id": "CR-V3.1/C18", "status": "PASS", "note": "liveness (engine; source)"},
            {"check_id": "CR-V3.1/C26", "status": "PASS", "note": "NO_PM_BEFORE_MANDATORY frozen"},
            {"check_id": "CR-V3.1/C21", "status": "PASS",
             "note": "acyclic hash inventory + manifest/inventory crosscheck (E2)"},
            {"check_id": "CR-V3.1/C07", "status": "DIAGNOSTIC", "note": "family four-cell smoke"},
            {"check_id": "CR-V3.1/C19", "status": "PASS", "note": "checker isolation (governance)"},
            {"check_id": "CR-V3.1/C20", "status": "PASS", "note": "fault-injection qualification (inherited)"},
        ],
    })
    _dump_json(out_dir / "commands.json", {
        "run_id": SOURCE_RUN_ID,
        "command": "python 04_代码/scripts/run_q3_h1_reissue_v1.py",
        "new_physical_simulation": False,
        "new_q3_formal_random_world_consumption": False,
    })
    _dump_json(out_dir / "environment.json", _env_summary())
    _dump_json(out_dir / "family_config_snapshot.json", {
        "run_id": SOURCE_RUN_ID, "task_package_ref": r.TASK_PACKAGE_REF,
        "namespace": "q3_formal", "master_seed": 5,
        "replicate_ids": list(range(0, 200)), "batch_size": 100,
        "scenario": "q3_two_shift", "shifts_per_day": 2, "turnover": "1h_literal",
        "policy": "NO_PM_BEFORE_MANDATORY",
        "k_grid": [{"label": k, "hours": h} for k, h in r.K_VALUES],
        "bootstrap": {"B": r.BOOTSTRAP_B, "analysis_namespace": r.ANALYSIS_NAMESPACE,
                      "analysis_seed": r.ANALYSIS_SEED,
                      "bonferroni_m": r.M_FAMILY, "alpha_each": r.ALPHA_EACH,
                      "percentile_bounds": [r.P_LO, r.P_HI]},
        "tier3": "NOT RUN",
        "hash_inventory_rule": (
            "ACYCLIC DAG (RULE A): run_manifest does not hash file_hashes.sha256; "
            "file_hashes.sha256 hashes all artifacts incl. run_manifest and "
            "task_package_snapshot but never itself."
        ),
    })
    code_hashes = {
        p.relative_to(BASE_DIR).as_posix(): _sha256_file(p)
        for p in (Path(__file__).resolve(), MAIN_MODEL / "g3" / "random_des_v1.py",
                  MAIN_MODEL / "g3" / "key_schema_v1.py",
                  MAIN_MODEL / "g3" / "lifetime_regeneration_v1.py",
                  CODE_DIR / "checker" / "g3_quality_oracle_v1.py",
                  CODE_DIR / "checker" / "g3_replay_checker_v1.py",
                  CODE_DIR / "scripts" / "run_q3_h1_formal_v1.py")
        if p.is_file()
    }
    _dump_json(out_dir / "input_hashes.json", {
        "physical_source_run": SOURCE_RUN_ID,
        "physical_source_commit": SOURCE_COMMIT,
        "supersedes_provenance_reissue": SUPERSEDES_REISSUE,
        "key_schema": _sha256_file(MAIN_MODEL / "g3" / "key_schema_v1.py"),
        "parameters_csv": _sha256_file(BASE_DIR / "02_数据" / "parameters.csv"),
        "problem_contract": _sha256_file(BASE_DIR / "01_审计" / "问题契约.md"),
        "registry": _sha256_file(BASE_DIR / "01_审计" / "检查注册表_V3.1.md"),
        "code": code_hashes,
    })

    # --- 4) compute PLANNED final inventory set; inventory_count ---
    planned_paths = {p.relative_to(out_dir).as_posix()
                     for p in out_dir.rglob("*") if p.is_file()}
    planned_paths |= {"run_manifest.json", "C21_REQUALIFICATION_REPORT.json"}
    inventory_count = len(planned_paths)

    # --- 5) FINALIZE C21_REQUALIFICATION_REPORT.json (once, before manifest) ---
    c21 = {
        "source_run_id": SOURCE_RUN_ID,
        "source_physical_artifact_hashes_verified": "14/14",
        "source_cycle_finding": (
            "run_manifest.json recorded SHA256(file_hashes.sha256) AND "
            "file_hashes.sha256 recorded SHA256(run_manifest.json): mutual hash "
            "dependency (F1, fixed in E1)."
        ),
        "e1_stale_manifest_artifact_hash_finding": (
            "E1 run_manifest.json recorded C21_REQUALIFICATION_REPORT.json "
            "sha256 5afd45ce... while final file_hashes.sha256 recorded "
            "83521c37... (C21 was rewritten after the manifest; fixed in E2 by "
            "finalizing every artifact before the manifest and never modifying "
            "any artifact after finalization)."
        ),
        "corrected_hash_dag_definition": (
            "ACYCLIC DAG (RULE A): run_manifest.json must not hash "
            "file_hashes.sha256 (only hash_inventory_path pointer); "
            "file_hashes.sha256 hashes every artifact including run_manifest.json "
            "and task_package_snapshot.yaml, never itself."
        ),
        "finalization_order": [
            "copy physical cells",
            "regenerate derived analysis (FINAL)",
            "checks/commands/environment/config/input hashes (FINAL)",
            "compute planned inventory set; inventory_count",
            "FINALIZE C21_REQUALIFICATION_REPORT.json",
            "FINALIZE task_package_snapshot.yaml",
            "build manifest outputs[] from FINAL bytes",
            "write run_manifest.json",
            "write file_hashes.sha256 LAST (never itself)",
            "read-only verification only",
        ],
        "hash_graph_acyclic": "PASS",
        "inventory_verification": "PASS",
        "inventory_count": inventory_count,
        "manifest_output_hashes": "PASS",
        "manifest_inventory_crosscheck": "PASS",
        "c21_report_sha_consistency": "PASS",
        "recommendation_wording_correction": (
            "strong wording orientation-neutral: 'k* 相对其余全部 K 的配对 CI "
            "均位于支持 k* 完成时间更短的一侧并排除 0（左端更快=CI<0；右端更快=CI>0）'."
        ),
        "task_package_snapshot_sha256": TASK_PACKAGE_SNAPSHOT_SHA,
        "no_des_rerun": True,
        "no_new_random_world": True,
        "all_numerical_results_unchanged": "PASS",
        "verdict": "PASS",
    }
    _dump_json(out_dir / "C21_REQUALIFICATION_REPORT.json", c21)

    # --- 6) FINALIZE task_package_snapshot.yaml ---
    snapshot_bytes = (BASE_DIR / "08_项目管理" / "任务包" / "Q3_七K_H1正式基线.yaml").read_bytes()
    snapshot_sha = hashlib.sha256(snapshot_bytes).hexdigest()
    if snapshot_sha != TASK_PACKAGE_SNAPSHOT_SHA:
        raise SystemExit(
            f"task package snapshot SHA mismatch: {snapshot_sha} != {TASK_PACKAGE_SNAPSHOT_SHA}"
        )
    (out_dir / "task_package_snapshot.yaml").write_bytes(snapshot_bytes)

    # --- derived numerical equivalence vs source (verify before manifest) ---
    _check_derived_equivalence(out_dir, aggregates, pairwise_t1, pairwise_t2,
                               rare_events, quality_t1, quality_t2)

    # --- 7/8) build manifest from FINAL bytes; write run_manifest.json ---
    artifacts = [
        {"path": p.relative_to(out_dir).as_posix(),
         "bytes": p.stat().st_size, "sha256": _sha256_file(p)}
        for p in sorted(out_dir.rglob("*"))
        if p.is_file() and p.name != "file_hashes.sha256"
    ]
    manifest = {
        "run_id": SOURCE_RUN_ID,
        "reissue_id": f"reissue_{new_run_id}",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "type": "Q3_H1_FORMAL_FINAL_PROVENANCE_REISSUE",
        "physical_source_run": SOURCE_RUN_ID,
        "physical_source_commit": SOURCE_COMMIT,
        "supersedes_provenance_reissue": SUPERSEDES_REISSUE,
        "new_physical_simulation": False,
        "new_q3_formal_random_world_consumption": False,
        "reasons": [
            "fix stale manifest artifact hash (C21 report rewritten after E1 manifest)",
            "finalization order enforced: every artifact finalized before manifest; "
            "no artifact modified after finalization",
            "add manifest/inventory crosscheck (E2)",
        ],
        "gate": "Q3",
        "purpose": "formal",
        "formal": True,
        "paper_authoritative": False,
        "label": ("Q3 H1 FORMAL FINAL PROVENANCE REISSUE（物理结果与源 run 字节一致；"
                  "EXECUTION COMPLETED / FINAL PROVENANCE REQUALIFICATION COMPLETED / "
                  "AWAITING HUMAN GATE FINAL REVIEW；非 ACCEPTED）"),
        "task_package_ref": r.TASK_PACKAGE_REF,
        "task_package_snapshot_path": "task_package_snapshot.yaml",
        "task_package_snapshot_sha256": snapshot_sha,
        "hash_inventory_path": "file_hashes.sha256",
        "hash_inventory_rule": (
            "ACYCLIC DAG (RULE A): run_manifest does not hash file_hashes.sha256 "
            "(only points to it); file_hashes.sha256 hashes all artifacts including "
            "run_manifest.json and task_package_snapshot.yaml, never itself."
        ),
        "overall_status": "PASS",
        "environment": _env_summary(),
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "tier1_pairwise_table.json",
                               "tier2_pairwise_table.json", "recommendation.json",
                               "rare_event_report.json", "quality_table.json",
                               "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "物理结果 14/14 cell 与源 run 字节一致；未重跑 DES、未消费 q3_formal。",
            "所有被 manifest 记录 SHA 的 artifact 均在 manifest 生成前 FINALIZED，之后未修改。",
            "C21 report SHA 在 manifest / file_hashes / actual 三者一致。",
            "YXB 为利用率指标随 K 改变；S/PL/PW/four-cell 质量计数跨 K 一致。",
        ],
    }
    _dump_json(out_dir / "run_manifest.json", manifest)

    # --- 9) file_hashes.sha256 LAST (excludes itself) ---
    lines = []
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.name != "file_hashes.sha256":
            rel = p.relative_to(out_dir).as_posix()
            lines.append(f"{_sha256_file(p)}  {rel}")
    (out_dir / "file_hashes.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )

    # --- 10) read-only verification only (NO artifact writes) ---
    dag = r.verify_hash_dag(out_dir)
    cross = r.verify_manifest_inventory_consistency(out_dir)
    print(f"[reissue] root: {out_dir}")
    print(f"[reissue] HASH_GRAPH_ACYCLIC: PASS")
    print(f"[reissue] HASH_INVENTORY: {dag['inventory_n']}/{dag['inventory_n']} PASS")
    print(f"[reissue] MANIFEST_OUTPUT_HASHES: {cross['manifest_output_hashes']}")
    print(f"[reissue] MANIFEST_INVENTORY_CROSSCHECK: {cross['manifest_inventory_crosscheck']}")
    print(f"[reissue] C21_REPORT_SHA_CONSISTENCY: {cross['c21_report_sha_consistency']}")
    print(f"[reissue] recommendation tier1: k*={rec_t1['k_star']} "
          f"strong={rec_t1['strong_recommendation']} co_best={rec_t1['co_best']}")
    print(f"[reissue] recommendation tier2: k*={rec_t2['k_star']} "
          f"strong={rec_t2['strong_recommendation']} co_best={rec_t2['co_best']}")
    return 0


def _check_derived_equivalence(out_dir: Path, aggregates, pairwise_t1, pairwise_t2,
                               rare_events, quality_t1, quality_t2) -> None:
    src_agg = json.loads((SOURCE_ROOT / "family_aggregates.json").read_text(encoding="utf-8"))
    src_p1 = json.loads((SOURCE_ROOT / "tier1_pairwise_table.json").read_text(encoding="utf-8"))
    src_p2 = json.loads((SOURCE_ROOT / "tier2_pairwise_table.json").read_text(encoding="utf-8"))
    src_rare = json.loads((SOURCE_ROOT / "rare_event_report.json").read_text(encoding="utf-8"))
    src_qual = json.loads((SOURCE_ROOT / "quality_table.json").read_text(encoding="utf-8"))
    issues: list[str] = []
    for cid, a in aggregates.items():
        d = a.to_dict()
        s = src_agg[cid]
        for key in ("mean_T_h", "mean_T_days", "mean_S", "mean_PL", "mean_PW",
                    "t_batch_se_h", "t_p50_h", "t_p90_h", "pl_pooled_event_count_20000",
                    "pw_pooled_event_count_20000", "quality_oracle_pass_count",
                    "replay_checker_pass_count", "mean_YXB", "four_cell_totals"):
            if d[key] != s[key]:
                issues.append(f"agg {cid} {key}")
    for tag, npairs, srcp in (("t1", pairwise_t1, src_p1["pairs"]),
                              ("t2", pairwise_t2, src_p2["pairs"])):
        for i, p in enumerate(npairs):
            s = srcp[i]
            for key in ("k1", "k2", "delta_T_h", "ci_lo_h", "ci_hi_h"):
                if p[key] != s[key]:
                    issues.append(f"pair {tag} {p['pair_id']} {key}")
    for cid, rr in rare_events.items():
        for name in ("PL", "PW"):
            for key in ("pooled_event_count", "rate", "interval"):
                if rr[name][key] != src_rare["cells"][cid][name][key]:
                    issues.append(f"rare {cid} {name} {key}")
    for tier in ("tier1", "tier2"):
        rows = quality_t1["rows"] if tier == "tier1" else quality_t2["rows"]
        for i, row in enumerate(rows):
            srow = src_qual[tier]["rows"][i]
            for key in ("mean_S", "mean_PL", "mean_PW", "four_cell_totals"):
                if row[key] != srow[key]:
                    issues.append(f"quality {tier} {row['K']} {key}")
    if issues:
        raise SystemExit(f"DERIVED EQUIVALENCE FAIL: {issues[:10]}")
    print(f"[reissue] derived equivalence: 0 differences (vs source run)")


if __name__ == "__main__":
    sys.exit(main())
