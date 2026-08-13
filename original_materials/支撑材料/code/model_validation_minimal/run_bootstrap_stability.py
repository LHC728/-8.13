#!/usr/bin/env python3
"""Reproduce the 2000-sample strategy-selection bootstrap from screening data."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCREEN_PATH = (
    ROOT
    / "output"
    / "problem3_is_mcrfo_v2_2_2"
    / "screening_replications_corrected.csv"
)
OUT_DIR = ROOT / "output" / "model_validation_minimal"
REPLICATIONS_PATH = OUT_DIR / "bootstrap_replications.csv"
SUMMARY_PATH = OUT_DIR / "bootstrap_selection_frequency.csv"
BOOTSTRAP_SEED = 20260730
N_BOOTSTRAP = 2000
CURRENT = {"N": 378, "q_max": 21, "B": 0, "h": 45}


def main() -> int:
    frame = pd.read_csv(SCREEN_PATH)
    seeds = np.array(sorted(frame["seed"].astype(int).unique()))
    if len(frame) != 920 or len(seeds) != 10:
        raise ValueError(
            f"Expected 920 screening rows and 10 seeds, got {len(frame)} and {len(seeds)}"
        )

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows: list[dict[str, object]] = []

    for bootstrap_id in range(N_BOOTSTRAP):
        sampled_seeds = rng.choice(seeds, size=len(seeds), replace=True)
        sampled = pd.concat(
            [frame.loc[frame["seed"].astype(int) == int(seed)] for seed in sampled_seeds],
            ignore_index=True,
        )

        y_ref = float(
            sampled.loc[sampled["scheme"] == "A", "annual_output"].mean()
        )
        y_min = 0.95 * y_ref
        candidates = (
            sampled.loc[sampled["scheme"] == "C"]
            .groupby(["N", "q_max", "B", "h"], as_index=False)
            .agg(
                mean_output=("annual_output", "mean"),
                mean_loss=("mean_daily_loss", "mean"),
            )
        )
        candidates["feasible"] = candidates["mean_output"] >= y_min
        feasible = candidates.loc[candidates["feasible"]].copy()

        if feasible.empty:
            ranked = candidates.sort_values(
                ["mean_output", "mean_loss", "N", "q_max", "B", "h"],
                ascending=[False, True, True, True, True, True],
            ).reset_index(drop=True)
        else:
            ranked = feasible.sort_values(
                ["mean_loss", "mean_output", "N", "q_max", "B", "h"],
                ascending=[True, False, True, True, True, True],
            ).reset_index(drop=True)

        best = ranked.iloc[0]
        current_mask = (
            (candidates["N"].astype(int) == CURRENT["N"])
            & (candidates["q_max"].astype(int) == CURRENT["q_max"])
            & (candidates["B"].astype(int) == CURRENT["B"])
            & (candidates["h"].astype(int) == CURRENT["h"])
        )
        current = candidates.loc[current_mask].iloc[0]
        rank_mask = (
            (ranked["N"].astype(int) == CURRENT["N"])
            & (ranked["q_max"].astype(int) == CURRENT["q_max"])
            & (ranked["B"].astype(int) == CURRENT["B"])
            & (ranked["h"].astype(int) == CURRENT["h"])
        )
        current_rank = (
            int(np.flatnonzero(rank_mask.to_numpy())[0] + 1)
            if rank_mask.any()
            else 999
        )

        rows.append(
            {
                "bootstrap_id": bootstrap_id,
                "Y_ref": y_ref,
                "Y_min": y_min,
                "chosen_N": int(best["N"]),
                "chosen_q_max": int(best["q_max"]),
                "chosen_B": int(best["B"]),
                "chosen_h": int(best["h"]),
                "chosen_loss": float(best["mean_loss"]),
                "chosen_output": float(best["mean_output"]),
                "current_policy_feasible": bool(current["feasible"]),
                "current_policy_rank": current_rank,
            }
        )

    result = pd.DataFrame(rows)
    result.to_csv(REPLICATIONS_PATH, index=False, encoding="utf-8-sig")
    exact_current = (
        (result["chosen_N"] == CURRENT["N"])
        & (result["chosen_q_max"] == CURRENT["q_max"])
        & (result["chosen_B"] == CURRENT["B"])
        & (result["chosen_h"] == CURRENT["h"])
    )

    summary_rows = [
        ("current_selected_pct", 100 * exact_current.mean()),
        ("current_feasible_pct", 100 * result["current_policy_feasible"].mean()),
        ("current_top3_pct", 100 * (result["current_policy_rank"] <= 3).mean()),
        ("N_378_selected_pct", 100 * (result["chosen_N"] == 378).mean()),
        ("q_21_selected_pct", 100 * (result["chosen_q_max"] == 21).mean()),
        ("q_28_selected_pct", 100 * (result["chosen_q_max"] == 28).mean()),
        ("B_0_selected_pct", 100 * (result["chosen_B"] == 0).mean()),
        ("h_45_selected_pct", 100 * (result["chosen_h"] == 45).mean()),
        ("no_feasible_pct", 100 * (result["current_policy_rank"] == 999).mean()),
    ]
    summary = pd.DataFrame(summary_rows, columns=["metric", "value"])
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    print(f"Bootstrap seed: {BOOTSTRAP_SEED}")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
