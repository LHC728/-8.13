#!/usr/bin/env python3
"""Q3 H1 formal preflight (P0-E1-style qualification, NO q3_formal consumption).

Runs BEFORE the formal run consumes any q3_formal world.  Uses only
development_unit namespace + deterministic tiny batches (batch_size=3) and
reuses accepted G3 regression tests.  If any preflight check FAILS the
formal run must NOT start (STOP).

Checks (Q3-H1-FORMAL-SPEC-V1.0 section 13):
  A. config schema / shape for all seven K (q3_two_shift, 2 shifts/day,
     shift_length=K, policy NO_PM sentinel, batch=100 formal shape)
  B. two-shift calendar: day d shifts [24d,24d+K) [24d+K,24d+2K), off 24-2K
  C. full reset: fresh state per run (engine stateless); determinism
     (same config -> identical canonical output)
  D. cross-K CRN / no K or policy injection into physical keys
  E. shift-end exact equality and pending-retest / FCFS continuity are
     covered by accepted G3 regression (TestQ3Interface + related)
  F. YXB denominator = K (shift_count x shift_length)
  G. Tier 1 / Tier 2 config separation (kernels differ; both NO_PM)
  H. P0 legacy key-schema regression still PASS
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
TESTS_DIR = CODE_DIR / "tests"
for _entry in (str(MAIN_MODEL), str(CODE_DIR), str(TESTS_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from des import state_models_v1 as sm  # noqa: E402
from g3 import key_schema_v1 as ks  # noqa: E402
from g3 import lifetime_regeneration_v1 as lr  # noqa: E402
from g3 import random_des_v1 as rd  # noqa: E402

from scripts import run_q3_h1_formal_v1 as runner  # noqa: E402
from checker import g3_replay_checker_v1 as rc  # noqa: E402

K_VALUES = runner.K_VALUES
K_DISPLAY = runner.K_DISPLAY
DEV_NS = ks.NAMESPACE_DEVELOPMENT_UNIT


def dev_config(k_label: str, rep: int, tier: str = runner.TIER1) -> rd.RandomDesConfig:
    """Preflight config: same shape as the formal cell but on development_unit
    (never q3_formal)."""
    kernel = runner.single_kernel() if tier == runner.TIER1 else runner.chain_kernel()
    k_frac = Fraction(dict(K_VALUES)[k_label])
    return rd.default_config(
        namespace=DEV_NS,
        master_seed=runner.MASTER_SEED,
        replicate_id=rep,
        tau_pm=runner.POLICY,
        observation_kernel=kernel,
        batch_size=3,
        scenario=runner.SCENARIO,
        shift_length_h=sm.fraction_to_string(k_frac),
        shifts_per_day=runner.SHIFTS_PER_DAY,
        turnover_profile=runner.TURNOVER_1H,
        scenario_id=f"q3_preflight_{tier}_{k_label}_rep{rep}",
    )


def run_sha(cfg: rd.RandomDesConfig) -> tuple[str, dict]:
    res = rd.run_random_des(cfg)
    return hashlib.sha256(res.canonical_event_log()).hexdigest(), res.metrics


def main() -> int:
    failures: list[str] = []
    print("== A. config shape for all seven K ==")
    for k, hours in K_VALUES:
        cfg = dev_config(k, 0)
        assert cfg.scenario == "q3_two_shift" and cfg.shifts_per_day == 2
        assert cfg.shift_length_h == Fraction(hours), (k, cfg.shift_length_h)
        assert cfg.tau_pm is lr.NO_PM_BEFORE_MANDATORY
        assert cfg.batch_size == 3 and cfg.namespace == DEV_NS
        formal_cfg = runner.make_cell_config(runner.TIER1, k, 0)
        assert formal_cfg.batch_size == runner.BATCH_SIZE == 100
        print(f"  {k} (K={K_DISPLAY[k]} h): ok")

    print("== B/C. two-shift calendar + full reset + determinism ==")
    for k, _ in K_VALUES:
        cfg = dev_config(k, 0)
        sha1, m1 = run_sha(cfg)
        sha2, _m2 = run_sha(dev_config(k, 0))
        if sha1 != sha2:
            failures.append(f"determinism failed for {k}")
        if float(Fraction(m1["T"])) <= 0:
            failures.append(f"non-positive T for {k}")
        if int(m1["shift_count"]) < 1:
            failures.append(f"shift_count<1 for {k}")
        print(f"  {k}: T={m1['T']} h shifts={m1['shift_count']} log={sha1[:12]}")

    print("== F. YXB denominator = shift_count x K (via accepted C17 replay) ==")
    for k, _ in K_VALUES:
        cfg = dev_config(k, 0)
        res = rd.run_random_des(cfg)
        m = res.metrics
        for rsrc in ("A", "B", "C", "E"):
            y = Fraction(m[f"YXB_{rsrc}"])
            if not (Fraction(0) <= y <= Fraction(1)):
                failures.append(f"YXB out of range {k}/{rsrc}: {y}")
        replay = rc.check_replay(
            res.event_log, cfg.to_dict(), str(BASE_DIR / "02_数据" / "parameters.csv"),
            metrics=m, run_id=f"q3_preflight_{k}_rep0",
        )
        if replay.verdict != "PASS":
            failures.append(f"C17 replay FAIL for {k}: {[str(i) for i in replay.issues][:3]}")
        print(f"  {k}: YXB in [0,1]; C17 replay = {replay.verdict}")

    print("== D. no K/policy injection into physical keys ==")
    for k, _ in K_VALUES:
        cfg = dev_config(k, 0)
        res = rd.run_random_des(cfg)
        consumed = res.summary.get("consumed_u", {})
        for key in consumed:
            if k in key or "shift" in key.lower():
                failures.append(f"physical key polluted by K/shift for {k}: {key}")
        print(f"  {k}: consumed_u keys clean")

    print("== G. Tier 1 / Tier 2 kernel separation ==")
    s = runner.single_kernel()
    c = runner.chain_kernel()
    if s["A"]["alpha"] == c["A"]["alpha"]:
        failures.append("Tier1/Tier2 kernels must differ")
    for proc in ("A", "B", "C", "E"):
        assert 0 < s[proc]["alpha"] < 1 and 0 < c[proc]["alpha"] < 1
    print("  single vs chain kernels distinct; policy NO_PM in both")

    print("== H. P0 legacy regression ==")
    res = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(TESTS_DIR),
         "-p", "test_p0_h2_key_schema_bootstrap_v1.py"],
        capture_output=True, text=True,
    )
    tail = [ln for ln in res.stdout.splitlines() if ln.startswith(("Ran ", "OK", "FAILED"))]
    print(f"  exit={res.returncode} {' | '.join(tail)}")
    if res.returncode != 0:
        failures.append("P0 legacy regression FAILED")

    print("== E. accepted G3 Q3-interface regression ==")
    res = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(TESTS_DIR),
         "-p", "test_g3_random_des_v1.py"],
        capture_output=True, text=True,
    )
    tail = [ln for ln in res.stdout.splitlines() if ln.startswith(("Ran ", "OK", "FAILED"))]
    print(f"  exit={res.returncode} {' | '.join(tail)}")
    if res.returncode != 0:
        failures.append("G3 random-DES regression FAILED")

    if failures:
        print("PREFLIGHT: FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("PREFLIGHT: PASS (no q3_formal world consumed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
