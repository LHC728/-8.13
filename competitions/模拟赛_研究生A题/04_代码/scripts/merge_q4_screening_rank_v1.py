#!/usr/bin/env python3
"""Q4 merged screening factor rank: per-factor factor_score = max(|std effect|)
across Phase 1A + Phase 1B screening scenarios (SCREENING_ONLY / NON_FINAL).

The rank rule is frozen (Q4 spec §8): standardized effect + CI + separate
management priority; factor_score = max |standardized_effect| per factor.
F1 (K) is NOT re-screened: REUSED_ACCEPTED_FORMAL_EVIDENCE (Q3 accepted).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
PHASE_1A = BASE_DIR / "05_结果" / "Q4" / "screening" / "phase_1a" / \
    "20260817T060454057035Z_c516bd6c" / "screening_results.json"
PHASE_1B_DIR = BASE_DIR / "05_结果" / "Q4" / "screening" / "phase_1b"
OUT_DIR = BASE_DIR / "05_结果" / "Q4" / "screening" / "merged"

FACTOR_META = {
    "F1": "REUSED_ACCEPTED_FORMAL_EVIDENCE (Q3 accepted seven-K; K12 strong winner "
          "within the seven-K + frozen H1 policy set; NOT re-run in Q4 screening)",
    "F2": "turnover 1.0h -> 0.5h complete overlap (level-1 controllable)",
    "F3": "preventive replacement threshold (COUNTERFACTUAL_ONLY per HG-Q4-F3-01)",
    "F4-A": "duration_A +-10%", "F4-B": "duration_B +-10%",
    "F4-C": "duration_C +-10%", "F4-E": "duration_E +-10%",
    "F5": "failure semantics constant-hazard (MODEL_SEMANTIC_ONLY)",
    "Q-A": "q = calibration input (scale 0.8/1.2; kernels recalibrated; e baseline)",
    "Q-B": "q = incoming defect pressure (scale 0.8/1.2; kernel frozen baseline)",
    "E": "e = error environment (e_A/B/C/E scale 0.8/1.2; kernels recalibrated)",
}


def load_phase1a(path: Path) -> list[dict]:
    pkg = json.loads(path.read_text(encoding="utf-8"))
    return pkg["screening_rows"]


def load_phase1b() -> list[dict]:
    # newest run dir
    runs = sorted([p for p in PHASE_1B_DIR.iterdir() if p.is_dir()])
    if not runs:
        raise SystemExit("no phase_1b run dir found")
    run_dir = runs[-1]
    pkg = json.loads((run_dir / "phase1b_screening_results.json").read_text(encoding="utf-8"))
    return pkg["screening_rows"]


def main() -> int:
    rows_1a = load_phase1a(PHASE_1A)
    rows_1b = load_phase1b()
    all_rows = rows_1a + rows_1b

    by_factor: dict[str, list[dict]] = {}
    for r in all_rows:
        by_factor.setdefault(r["factor_id"], []).append(r)

    merged = []
    for fid, rows in by_factor.items():
        best = max(rows, key=lambda r: abs(r["standardized_effect"]))
        merged.append({
            "factor_id": fid,
            "factor_score": best["standardized_effect"],
            "abs_factor_score": abs(best["standardized_effect"]),
            "max_scenario": best["scenario_id"],
            "max_scenario_mean_Delta_T_h": best["mean_Delta_T_h"],
            "max_scenario_CI": [best["screening_CI_low"], best["screening_CI_high"]],
            "n_scenarios": len(rows),
            "scenario_rows": [{
                "scenario_id": r["scenario_id"], "source": r["source"],
                "mean_Delta_T_h": r["mean_Delta_T_h"],
                "CI": [r["screening_CI_low"], r["screening_CI_high"]],
                "standardized_effect": r["standardized_effect"],
                "sign_consistency": r["sign_consistency"],
            } for r in sorted(rows, key=lambda r: -abs(r["standardized_effect"]))],
            "meta": FACTOR_META.get(fid, ""),
        })
    merged.sort(key=lambda m: -m["abs_factor_score"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "Q4_SCREENING_MERGED_FACTOR_RANKING.json").write_text(
        json.dumps({"status": "SCREENING_ONLY_NON_FINAL",
                    "rule": "factor_score = max |standardized_effect| per factor "
                            "(frozen Q4 spec §8); screening domains Phase 1A "
                            "(rep 0..19) + Phase 1B (rep 20..39) are separate "
                            "paired experiments; NOT pooled; NOT final inference",
                    "factor_ranking": merged},
                   ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")

    lines = ["# Q4 SCREENING MERGED MATHEMATICAL EFFECT RANK (screening-only)",
             "",
             "| rank | factor | factor_score (std) | max scenario | mean dT (h) | CI |",
             "|---|---|---|---|---|---|"]
    for i, m in enumerate(merged, 1):
        ci = f"[{m['max_scenario_CI'][0]}, {m['max_scenario_CI'][1]}]"
        lines.append(f"| {i} | {m['factor_id']} | {m['factor_score']} | "
                     f"{m['max_scenario']} | {m['max_scenario_mean_Delta_T_h']} | {ci} |")
    lines += ["",
              "> SCREENING_ONLY / NON_FINAL_INFERENCE. F3 rows COUNTERFACTUAL_ONLY "
              "(HG-Q4-F3-01); F5 MODEL_SEMANTIC_ONLY. F1 = REUSED_ACCEPTED_FORMAL_"
              "EVIDENCE (not re-run). 数学影响排序 ≠ 管理实施优先级.",
              "> 正式结论唯一证据源 = Q4_EVALUATION（本 screening 数据绝不进入最终 CI）。"]
    (OUT_DIR / "Q4_SCREENING_MERGED_FACTOR_RANKING.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    for i, m in enumerate(merged, 1):
        print(f"  {i:>2} {m['factor_id']:>4} score={m['factor_score']:>10} "
              f"({m['max_scenario']})")
    print("merged rank written:", OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
