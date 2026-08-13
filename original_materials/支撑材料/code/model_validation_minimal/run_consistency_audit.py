#!/usr/bin/env python3
"""Parse Table 5 from LaTeX and compare all 93 fields with the source CSV."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
TEX_PATH = ROOT / "latex-template" / "texfile" / "5MakeModel.tex"
PLAN_PATH = ROOT / "output" / "problem2_fixed_cohort_final_start_plan.csv"
OUT_DIR = ROOT / "output" / "model_validation_minimal"
AUDIT_PATH = OUT_DIR / "table5_field_audit.csv"
SUMMARY_PATH = OUT_DIR / "paper_data_consistency_audit.csv"


def _integer(text: str) -> int:
    return int(re.sub(r"\s+", "", text))


def parse_table5(tex: str) -> pd.DataFrame:
    label_pos = tex.find(r"\label{tab:batch-start}")
    if label_pos < 0:
        raise ValueError("Table 5 label tab:batch-start was not found")

    start = tex.find(r"\midrule", label_pos)
    end = tex.find(r"\bottomrule", start)
    if start < 0 or end < 0:
        raise ValueError("Table 5 body boundaries were not found")

    records: list[dict[str, int]] = []
    for raw_line in tex[start + len(r"\midrule") : end].splitlines():
        line = raw_line.strip()
        if "&" not in line:
            continue
        line = re.sub(r"\\\\\s*$", "", line)
        cells = [cell.strip() for cell in line.split("&")]
        if len(cells) != 6:
            raise ValueError(f"Unexpected Table 5 row: {raw_line!r}")

        for offset in (0, 3):
            if cells[offset] == "--":
                if cells[offset + 1] != "--" or cells[offset + 2] != "--":
                    raise ValueError(f"Incomplete blank batch triplet: {raw_line!r}")
                continue
            records.append(
                {
                    "batch_id": _integer(cells[offset]),
                    "start_day": _integer(cells[offset + 1]),
                    "batch_size": _integer(cells[offset + 2]),
                }
            )

    frame = pd.DataFrame(records)
    if len(frame) != 31:
        raise ValueError(f"Table 5 contains {len(frame)} batch records, expected 31")
    if frame["batch_id"].duplicated().any():
        duplicates = frame.loc[frame["batch_id"].duplicated(), "batch_id"].tolist()
        raise ValueError(f"Duplicated batch IDs in Table 5: {duplicates}")
    expected_ids = set(range(1, 32))
    actual_ids = set(frame["batch_id"].astype(int))
    if actual_ids != expected_ids:
        raise ValueError(
            f"Batch ID set mismatch: missing={sorted(expected_ids-actual_ids)}, "
            f"extra={sorted(actual_ids-expected_ids)}"
        )
    return frame.sort_values("batch_id").reset_index(drop=True)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tex_frame = parse_table5(TEX_PATH.read_text(encoding="utf-8"))
    csv_frame = (
        pd.read_csv(PLAN_PATH)[["batch_id", "start_day", "batch_size"]]
        .astype(int)
        .sort_values("batch_id")
        .reset_index(drop=True)
    )

    rows: list[dict[str, object]] = []
    for batch_id in range(1, 32):
        tex_row = tex_frame.loc[tex_frame["batch_id"] == batch_id].iloc[0]
        csv_row = csv_frame.loc[csv_frame["batch_id"] == batch_id].iloc[0]
        for field in ("batch_id", "start_day", "batch_size"):
            tex_value = int(tex_row[field])
            csv_value = int(csv_row[field])
            rows.append(
                {
                    "batch_id": batch_id,
                    "field": field,
                    "tex_value": tex_value,
                    "csv_value": csv_value,
                    "pass": tex_value == csv_value,
                }
            )

    audit = pd.DataFrame(rows)
    audit.to_csv(AUDIT_PATH, index=False, encoding="utf-8-sig")
    passed = int(audit["pass"].sum())
    total = len(audit)

    existing = (
        pd.read_csv(SUMMARY_PATH)
        if SUMMARY_PATH.exists()
        else pd.DataFrame(columns=["check", "result"])
    )
    existing = existing[existing["check"] != "P2 Table 5: 93 fields"]
    extra = pd.DataFrame(
        [
            {
                "check": "P2 Table 5: 93 fields",
                "result": f"{'OK' if passed == total == 93 else 'FAIL'} ({passed}/{total})",
            }
        ]
    )
    pd.concat([existing, extra], ignore_index=True).to_csv(
        SUMMARY_PATH, index=False, encoding="utf-8-sig"
    )

    print(f"Table 5 records: {len(tex_frame)} unique batches")
    print(f"Field comparison: {passed}/{total} passed")
    print(f"Audit CSV: {AUDIT_PATH}")
    return 0 if passed == total == 93 else 1


if __name__ == "__main__":
    sys.exit(main())
