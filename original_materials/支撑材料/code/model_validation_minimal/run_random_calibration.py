#!/usr/bin/env python3
"""Recompute calibration estimates and confidence intervals from raw replications."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "output" / "model_validation_minimal"
INPUT_PATH = OUT_DIR / "problem3_calibration_replications.csv"
SUMMARY_PATH = OUT_DIR / "problem3_calibration_summary.csv"


def mean_ci(values: pd.Series) -> tuple[float, float, float]:
    data = values.astype(float).to_numpy()
    mean = float(np.mean(data))
    sem = float(np.std(data, ddof=1) / np.sqrt(len(data)))
    if len(data) != 10:
        raise ValueError("This validation uses exactly 10 independent replications")
    # Two-sided 95% Student-t critical value with 9 degrees of freedom.
    half = 2.2621571628540993 * sem
    return mean, mean - half, mean + half


def main() -> int:
    frame = pd.read_csv(INPUT_PATH)
    required = {
        "seed",
        "conception_rate",
        "litter_size",
        "n_births_eval",
        "gross_eval",
        "survival_rate",
        "cons_violations",
        "loss_violations",
        "csv_match",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing calibration columns: {sorted(missing)}")
    if len(frame) != 10:
        raise ValueError(f"Expected 10 calibration replications, found {len(frame)}")

    calculated_litter = frame["gross_eval"] / frame["n_births_eval"]
    if not np.allclose(calculated_litter, frame["litter_size"], atol=1e-12):
        raise ValueError("litter_size is not gross_eval / n_births_eval")
    if int(frame["cons_violations"].sum()) != 0:
        raise ValueError("Ewe conservation violations were found")
    if int(frame["loss_violations"].sum()) != 0:
        raise ValueError("Loss identity violations were found")
    if not frame["csv_match"].astype(bool).all():
        raise ValueError("CSV output totals do not match the simulation summaries")

    metrics = [
        ("conception_rate", 0.85),
        ("litter_size", 2.2),
        ("survival_rate", 0.97),
    ]
    rows = []
    for metric, target in metrics:
        mean, low, high = mean_ci(frame[metric])
        rows.append(
            {
                "metric": metric,
                "mean": mean,
                "ci_low": low,
                "ci_high": high,
                "target": target,
                "target_in_ci": low <= target <= high,
            }
        )
    summary = pd.DataFrame(rows)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    print(summary.to_string(index=False))
    print(
        "Completed lambings:",
        int(frame["n_births_eval"].sum()),
        "Gross lambs:",
        int(frame["gross_eval"].sum()),
    )
    return 0 if summary["target_in_ci"].all() else 1


if __name__ == "__main__":
    sys.exit(main())
