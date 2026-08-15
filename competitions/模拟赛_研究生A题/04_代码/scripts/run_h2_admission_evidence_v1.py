#!/usr/bin/env python3
"""H2 admission evidence runner (READ-ONLY offline analysis; NOT H2).

Human Gate 2026-08-15: H2 ADMISSION EVIDENCE AUDIT ONLY.

Reproducibly runs the independent H2 admission opportunity analyzer over the
PRE-FORMAL G3 accepted worlds (deterministic replay reproduces accepted log
hashes; no new random worlds consumed; no accepted evidence modified) and
persists the aggregate statistics for Human Gate.

Source evidence (primary): G3 tuning run_20260814T174022592173Z_01b7c7e7
  NO_PM_BEFORE_MANDATORY (20 shared h1_tuning worlds, master_seed=1) and
  tau_pm_198 sensitivity; secondary context: G3 holdout
  run_20260814T180238855262Z_020bc637 (100 batches, master_seed=2).
  q2_formal/** is NEVER used for H2 design/tuning/admission.

The analyzer (04_代码/checker/h2_admission_opportunity_analyzer_v1.py) is
stdlib-only and never imports the main DES dispatch; it measures ONLY
opportunity/branching density (no H2 policy, no T-improvement estimate).

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
SCRIPTS = CODE_DIR / "scripts"
CHECKER = CODE_DIR / "checker"
for _entry in (str(MAIN_MODEL), str(CODE_DIR), str(SCRIPTS), str(CHECKER)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from g3 import random_des_v1 as rd  # noqa: E402
from g3 import lifetime_regeneration_v1 as lr  # noqa: E402

# load analyzer without importing main dispatch
_ANALYZER_SPEC = importlib.util.spec_from_file_location(
    "h2_admission_opportunity_analyzer_v1",
    CHECKER / "h2_admission_opportunity_analyzer_v1.py")
ANALYZER = importlib.util.module_from_spec(_ANALYZER_SPEC)
sys.modules[_ANALYZER_SPEC.name] = ANALYZER
_ANALYZER_SPEC.loader.exec_module(ANALYZER)

# load tuning runner for its frozen kernel/config builder
_TUN_SPEC = importlib.util.spec_from_file_location(
    "run_g3_h1_tuning_v1", SCRIPTS / "run_g3_h1_tuning_v1.py")
TUN = importlib.util.module_from_spec(_TUN_SPEC)
sys.modules[_TUN_SPEC.name] = TUN
_TUN_SPEC.loader.exec_module(TUN)

TUNING_RUN = BASE_DIR / "05_结果" / "G3" / "tuning" / "run_20260814T174022592173Z_01b7c7e7"
HOLDOUT_RUN = BASE_DIR / "05_结果" / "G3" / "holdout" / "run_20260814T180238855262Z_020bc637"


def replay_batch(tau, ns, seed, rep):
    kernel = TUN.frozen_observation_kernel()
    cfg = rd.default_config(
        namespace=ns, master_seed=seed, replicate_id=rep, tau_pm=tau,
        observation_kernel=kernel, batch_size=100,
        scenario="q2_single_shift", shift_length_h="12", shifts_per_day=1,
        turnover_profile="1h_literal")
    return cfg, rd.run_random_des(cfg)


def verify_hash(log_sha256: str, expected: str, label: str) -> None:
    if log_sha256 != expected:
        raise RuntimeError(
            f"deterministic replay mismatch: {label}\n"
            f"  recomputed={log_sha256}\n  expected ={expected}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="H2 admission evidence offline analysis (read-only).")
    parser.add_argument("--output", default=str(BASE_DIR / "tmp" / "h2_admission_analysis.json"),
                        help="persisted analysis JSON path")
    args = parser.parse_args(argv)

    kernel = TUN.frozen_observation_kernel()

    # primary: NO_PM tuning worlds (20)
    no_pm_logs: list[list[dict[str, Any]]] = []
    lh = json.loads((TUNING_RUN / "log_hashes.json").read_text(encoding="utf-8"))[
        "canonical_event_log_sha256"]
    for rep in range(20):
        _cfg, res = replay_batch(lr.NO_PM_BEFORE_MANDATORY, "h1_tuning", 1, rep)
        h = hashlib.sha256(res.canonical_event_log()).hexdigest()
        verify_hash(h, lh[f"NO_PM_BEFORE_MANDATORY__rep{rep}"], f"tuning NO_PM rep{rep}")
        no_pm_logs.append(res.event_log)

    # sensitivity: tau_pm_198 tuning worlds (20)
    tau_logs: list[list[dict[str, Any]]] = []
    for rep in range(20):
        _cfg, res = replay_batch(Fraction(198), "h1_tuning", 1, rep)
        h = hashlib.sha256(res.canonical_event_log()).hexdigest()
        verify_hash(h, lh[f"tau_pm_198__rep{rep}"], f"tuning tau198 rep{rep}")
        tau_logs.append(res.event_log)

    # secondary context: holdout tau198 (FULL 100 batches)
    hlh = json.loads((HOLDOUT_RUN / "log_hashes.json").read_text(encoding="utf-8"))[
        "canonical_event_log_sha256"]
    holdout_logs: list[list[dict[str, Any]]] = []
    for rep in range(100):
        _cfg, res = replay_batch(Fraction(198), "g3_holdout", 2, rep)
        h = hashlib.sha256(res.canonical_event_log()).hexdigest()
        verify_hash(h, hlh[f"rep{rep}"], f"holdout rep{rep}")
        holdout_logs.append(res.event_log)

    cells = {
        "tuning_NO_PM": no_pm_logs,
        "tuning_tau198": tau_logs,
        "holdout_tau198_full100": holdout_logs,
    }
    result = ANALYZER.analyze_logs(cells)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    print("H2 admission analysis persisted ->", out_path)
    print("cells:", {k: len(v) for k, v in cells.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
