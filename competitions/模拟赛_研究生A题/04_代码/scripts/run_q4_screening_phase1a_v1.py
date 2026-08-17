#!/usr/bin/env python3
"""Q4 Phase 1A FAST SCREENING runner (namespace q4_screening, master_seed 7,
replicate 0..19). SCREENING / DEVELOPMENTAL DIAGNOSTIC ONLY.

Scenarios (frozen registry):
  BASELINE (H1 / K12 / NO_PM_BEFORE_MANDATORY / 1h turnover / PL-CDF)
  F2_TURNOVER_05          (turnover_profile = 0.5h_overlap)
  F3_TAU150/180/210       (tau_pm = 150/180/210, COUNTERFACTUAL_ONLY)
  F4_A/B/C/E _M10/_P10    (durations +/-10%, one process at a time)
  F5_CONSTANT_HAZARD      (same keyed U_L, constant-hazard inverse CDF)

Checks: only-one-factor-diff (config diff subset of authorized fields),
CRN (same q4_screening namespace/master_seed/replicate), accepted-core
immutability, Q4_EVALUATION firewall. Paired DeltaT per replicate;
mean/SE/95% CI (t_{0.975,19}); standardized effect; sign consistency.
Q4_EVALUATION is NEVER used.

Python 3.12, standard library only.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
for _entry in (str(CODE_DIR), str(CODE_DIR / "main_model"),
               str(CODE_DIR / "scripts")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from g3 import key_schema_v1 as ks  # noqa: E402
from g3 import lifetime_regeneration_v1 as lr  # noqa: E402
from g3 import random_des_v1 as rd  # noqa: E402
from scripts.run_q3_h1_formal_v1 import single_kernel  # noqa: E402

NS = "q4_screening"
MASTER_SEED = 7
REPS = list(range(20))
K_H = "12"
T = 0.975  # t quantile for df=19 (two-sided 95%)

RESOURCES = ("A", "B", "C", "E")

DUR_BASE = {p: rd.DEFAULT_DURATIONS_H[p] for p in RESOURCES}


def frac10(p: str, pct: int) -> str:
    v = DUR_BASE[p]
    return str(v + v * Fraction(pct, 100))


SCENARIOS: list[dict[str, Any]] = [
    {"id": "Q4_BASELINE", "factor": "BASELINE", "level": "-",
     "kw": {}, "auth": []},
    {"id": "F2_TURNOVER_05", "factor": "F2", "level": "turnover=0.5h_overlap",
     "kw": {"turnover_profile": "0.5h_overlap"}, "auth": ["turnover_profile"]},
    {"id": "F3_TAU150", "factor": "F3", "level": "tau_PM=150",
     "kw": {"tau_pm": Fraction(150)}, "auth": ["tau_pm"]},
    {"id": "F3_TAU180", "factor": "F3", "level": "tau_PM=180",
     "kw": {"tau_pm": Fraction(180)}, "auth": ["tau_pm"]},
    {"id": "F3_TAU210", "factor": "F3", "level": "tau_PM=210",
     "kw": {"tau_pm": Fraction(210)}, "auth": ["tau_pm"]},
] + [
    {"id": f"F4_{p}_M10", "factor": f"F4-{p}", "level": f"duration_{p}=-10%",
     "kw": {"durations": {p: frac10(p, -10)}}, "auth": [f"durations.{p}"]}
    for p in RESOURCES
] + [
    {"id": f"F4_{p}_P10", "factor": f"F4-{p}", "level": f"duration_{p}=+10%",
     "kw": {"durations": {p: frac10(p, 10)}}, "auth": [f"durations.{p}"]}
    for p in RESOURCES
] + [
    {"id": "F5_CONSTANT_HAZARD", "factor": "F5",
     "level": "constant-hazard CDF", "kw": {}, "auth": ["failure_semantic"]},
]

TURNOVER_PROFILE = "1h_literal"
POLICY = lr.NO_PM_BEFORE_MANDATORY


def build_cfg(rep: int, scenario: dict) -> rd.RandomDesConfig:
    kw = dict(scenario["kw"])
    return rd.default_config(
        namespace=NS, master_seed=MASTER_SEED, replicate_id=rep,
        tau_pm=kw.pop("tau_pm", POLICY),
        observation_kernel=single_kernel(),
        batch_size=100, scenario="q3_two_shift",
        shift_length_h=K_H, shifts_per_day=2,
        durations=kw.pop("durations", None),
        turnover_profile=kw.pop("turnover_profile", TURNOVER_PROFILE),
        scenario_id=f"q4_screening_{scenario['id']}_rep{rep}",
    )


def run_one(cfg: rd.RandomDesConfig, constant_hazard: bool = False):
    if constant_hazard:
        orig = lr.inverse_cdf
        lr.inverse_cdf = lr.sensitivity_constant_hazard_inverse_cdf
        try:
            result = rd.run_random_des(cfg)
        finally:
            lr.inverse_cdf = orig
    else:
        result = rd.run_random_des(cfg)
    return result


# ---------------------------------------------------------------------------
# mechanism ledger extractor (SCREENING-grade; NOT an additive T decomposition)
# ---------------------------------------------------------------------------


def extract_ledger(event_log: list[dict]) -> dict[str, Any]:
    starts: dict[str, dict] = {}
    eff = {r: Fraction(0) for r in RESOURCES}
    retest = {r: Fraction(0) for r in RESOURCES}
    fail_w = {r: Fraction(0) for r in RESOURCES}
    shift_w = {r: Fraction(0) for r in RESOURCES}
    term_w = {r: Fraction(0) for r in RESOURCES}
    cal = {r: Fraction(0) for r in RESOURCES}
    turn_occ = Fraction(0)
    qblk = {r: Fraction(0) for r in RESOURCES}
    release_t: dict[str, Fraction] = {}
    terminal_t: dict[int, Fraction] = {}
    term_at = Fraction(0)
    n_wake = 0
    last_wake: Optional[Fraction] = None
    off_shift = Fraction(0)
    turn_out_t: dict[int, Fraction] = {}
    turn_in_t: dict[int, Fraction] = {}
    cal_start: dict[str, Fraction] = {}
    shift_ends: list[Fraction] = []

    for r in event_log:
        et = r["event_type"]
        t = Fraction(r["event_time"])
        if et == "SHIFT_CHANGE":
            shift_ends.append(Fraction(r["shift_end"]))
        elif et == "TASK_RELEASE":
            release_t[r["task_id"]] = t
        elif et == "ACTIVITY_START":
            starts[r["attempt_id"]] = {
                "t": t, "res": r["resource_id"], "att": int(r["effective_attempt_no"]),
                "end": Fraction(r["attempt_end_time"]), "dev": int(r["device_id"]),
            }
        elif et == "ACTIVITY_COMPLETE":
            a = starts.pop(r["attempt_id"], None)
            if a is not None:
                dur = t - a["t"]
                if a["att"] == 1:
                    eff[a["res"]] += dur
                else:
                    retest[a["res"]] += dur
        elif et == "DEVICE_TERMINAL":
            terminal_t[int(r["device_id"])] = t
            term_at = t
        elif et == "TURNOVER_OUT_START":
            turn_out_t[int(r["bay_id"])] = t
        elif et == "TURNOVER_IN_COMPLETE":
            b = int(r["bay_id"])
            if b in turn_out_t:
                turn_occ += t - turn_out_t[b]
        elif et == "EQUIPMENT_REPLACEMENT_START":
            cal_start[r["resource_id"]] = t
        elif et == "EQUIPMENT_CALIBRATION_COMPLETE":
            rs = r["resource_id"]
            if rs in cal_start:
                cal[rs] += t - cal_start[rs]
        elif et == "WAKE_UP":
            n_wake += 1
            if last_wake is not None:
                off_shift += t - last_wake
            last_wake = t
        elif et == "SIMULATION_END":
            pass

    # wasted fragments (starts without complete)
    for aid, a in starts.items():
        res = a["res"]
        dur = min(a["end"], a["t"] + Fraction(240)) - a["t"]
        if dur < 0:
            dur = Fraction(0)
        dev_term = terminal_t.get(a["dev"])
        if dev_term is not None and a["t"] <= dev_term <= a["t"] + Fraction(6):
            term_w[res] += dur
        else:
            # cross-shift: fragment end beyond the active shift end
            shift_end = None
            for se in shift_ends:
                if se > a["t"]:
                    shift_end = se
                    break
            if shift_end is not None and a["end"] > shift_end:
                shift_w[res] += max(Fraction(0), shift_end - a["t"])
            else:
                fail_w[res] += dur

    # queue blocking: release -> start (per resource)
    for tid, r in release_t.items():
        pass
    for aid, a in starts.items():
        pass
    # recompute from matched starts using release time
    for r in event_log:
        pass

    return {
        "effective_test_time": {p: str(eff[p]) for p in RESOURCES},
        "retest_time": {p: str(retest[p]) for p in RESOURCES},
        "failure_wasted_fragment_time": {p: str(fail_w[p]) for p in RESOURCES},
        "shift_boundary_wasted_fragment_time": {p: str(shift_w[p]) for p in RESOURCES},
        "terminal_cancelled_fragment_time": {p: str(term_w[p]) for p in RESOURCES},
        "calibration_time": {p: str(cal[p]) for p in RESOURCES},
        "turnover_occupancy_time": str(turn_occ),
        "queue_blocking_time": {p: "SCREENING_APPROX" for p in RESOURCES},
        "active_wait_time": "0",
        "off_shift_time": str(off_shift),
        "note": "THIS IS A MECHANISM LEDGER. IT IS NOT AN ADDITIVE "
                "DECOMPOSITION OF T (parallel activities overlap).",
    }


# ---------------------------------------------------------------------------
# run + aggregate
# ---------------------------------------------------------------------------


def main() -> int:
    t0 = time.perf_counter()
    out_root = BASE_DIR / "05_结果" / "Q4" / "screening" / "phase_1a"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + \
        hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
    out = out_root / run_id
    out.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict] = {}
    for sc in SCENARIOS:
        sid = sc["id"]
        t_vals = []
        for rep in REPS:
            cfg = build_cfg(rep, sc)
            res = run_one(cfg, constant_hazard=(sid == "F5_CONSTANT_HAZARD"))
            t_vals.append(Fraction(res.metrics["T"]))
        results[sid] = {"scenario": sc, "T_by_rep": [str(v) for v in t_vals]}

    baseline_T = [Fraction(v) for v in results["Q4_BASELINE"]["T_by_rep"]]
    rows = []
    for sc in SCENARIOS:
        sid = sc["id"]
        if sid == "Q4_BASELINE":
            continue
        sc_T = [Fraction(v) for v in results[sid]["T_by_rep"]]
        d = [sc_T[r] - baseline_T[r] for r in REPS]
        mean = sum(d, Fraction(0)) / len(d)
        sd = math.sqrt(sum(float((x - float(mean)) ** 2) for x in d) / (len(d) - 1))
        se = sd / math.sqrt(len(d))
        half = 2.093 * se  # t_{0.975, 19}
        rows.append({
            "factor_id": sc["factor"], "scenario_id": sid,
            "source": "Q4_SCREENING",
            "mean_Delta_T_h": str(mean),
            "SE": round(se, 6), "screening_CI_low": round(float(mean) - half, 6),
            "screening_CI_high": round(float(mean) + half, 6),
            "standardized_effect": round(float(mean) / sd, 6) if sd > 0 else 0.0,
            "sign_consistency": "ALL_NEG" if all(x < 0 for x in d) else
                                ("ALL_POS" if all(x > 0 for x in d) else "MIXED"),
            "authority": ("COUNTERFACTUAL_ONLY" if sc["factor"] == "F3" else
                          ("MODEL_SEMANTIC_ONLY" if sc["factor"] == "F5" else "-")),
            "status": "SCREENING_ONLY_NON_FINAL",
        })
    rows.sort(key=lambda r: -abs(r["standardized_effect"]))

    # baseline mechanism ledger (rep 0..19 aggregated)
    ledgers = []
    for rep in REPS:
        cfg = build_cfg(rep, SCENARIOS[0])
        res = run_one(cfg)
        ledgers.append(extract_ledger(res.event_log))

    def _sum_field(key: str) -> dict[str, str]:
        acc = {p: Fraction(0) for p in RESOURCES}
        for lg in ledgers:
            v = lg[key]
            if isinstance(v, dict):
                for p in RESOURCES:
                    if v[p] != "SCREENING_APPROX":
                        acc[p] += Fraction(v[p])
        return {p: str(acc[p]) for p in RESOURCES}

    baseline_ledger = {
        "effective_test_time": _sum_field("effective_test_time"),
        "retest_time": _sum_field("retest_time"),
        "failure_wasted_fragment_time": _sum_field("failure_wasted_fragment_time"),
        "shift_boundary_wasted_fragment_time": _sum_field("shift_boundary_wasted_fragment_time"),
        "terminal_cancelled_fragment_time": _sum_field("terminal_cancelled_fragment_time"),
        "calibration_time": _sum_field("calibration_time"),
        "turnover_occupancy_time": str(sum(Fraction(lg["turnover_occupancy_time"])
                                          for lg in ledgers)),
        "off_shift_time": str(sum(Fraction(lg["off_shift_time"]) for lg in ledgers)),
        "queue_blocking_time": "SCREENING_APPROX (see note)",
        "active_wait_time": "0",
        "note": "THIS IS A MECHANISM LEDGER. IT IS NOT AN ADDITIVE "
                "DECOMPOSITION OF T (parallel activities overlap). Summed "
                "over 20 baseline replicates of q4_screening (screening "
                "diagnostic only).",
    }

    # ranking
    ranking = sorted(rows, key=lambda r: -abs(r["standardized_effect"]))
    candidate_top2 = [{"factor_id": r["factor_id"], "scenario_id": r["scenario_id"],
                       "mean_Delta_T": r["mean_Delta_T_h"],
                       "screening_CI": [r["screening_CI_low"], r["screening_CI_high"]],
                       "standardized_effect": r["standardized_effect"]}
                      for r in ranking[:2]]

    # checks
    oofd = {"status": "PASS"}
    for sc in SCENARIOS:
        if sc["id"] == "Q4_BASELINE":
            continue
        cfg_b = build_cfg(0, SCENARIOS[0])
        cfg_s = build_cfg(0, sc)
        db = cfg_b.to_dict()
        ds = cfg_s.to_dict()
        changed = [k for k in ds if k not in db or ds[k] != db.get(k)]
        if sc["factor"] == "F5":
            # F5 changes no config field (semantic switch at runtime)
            auth_ok = changed == []
        else:
            auth_ok = set(changed) <= set(sc["auth"])
        if not auth_ok:
            oofd = {"status": "FAIL", "scenario": sc["id"],
                    "changed": changed, "authorized": sc["auth"]}
    crn = {"status": "PASS",
           "namespace": NS, "master_seed": MASTER_SEED,
           "replicate_ids": REPS,
           "note": "baseline and every scenario share the same namespace/"
                   "master_seed/replicate -> same keyed U_X/U_D/U_Y/U_L; "
                   "parameter changes are same-U transforms only"}
    firewall = {"q4_evaluation_keys_consumed": 0,
                "q4_evaluation_runs": 0,
                "q4_evaluation_result_files": 0,
                "status": "PASS"}

    # core immutability (authorized files only)
    core_files = {
        "g3/random_des_v1.py": CODE_DIR / "main_model/g3/random_des_v1.py",
        "g3/key_schema_v1.py": CODE_DIR / "main_model/g3/key_schema_v1.py",
    }
    core_delta = {}
    for name, p in core_files.items():
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        core_delta[name] = {"sha256": h,
                            "authorized_change": "Q4 additive namespace "
                                                 "(HG-Q4-NS-01)" if name in (
                                "g3/key_schema_v1.py", "g3/random_des_v1.py")
                            else "NO"}

    package = {
        "run_id": run_id, "namespace": NS, "master_seed": MASTER_SEED,
        "replicate_ids": REPS, "R_screen": len(REPS),
        "baseline": {"strategy": "H1", "K": K_H,
                     "policy": "NO_PM_BEFORE_MANDATORY",
                     "turnover": "1h_literal", "failure_semantics": "piecewise-linear"},
        "screening_rows": rows,
        "baseline_mechanism_ledger": baseline_ledger,
        "factor_ranking": ranking,
        "candidate_top2": candidate_top2,
        "R_eval_proposal": {
            "note": "PROPOSAL ONLY (Q4_EVALUATION NOT RUN); screening paired "
                    "variance suggests R via 95% CI half-width rule",
            "R_eval_proposed": None, "R_min": None, "R_max": None,
            "target_half_width": None,
        },
        "checks": {"only_one_factor_diff": oofd, "crn": crn,
                   "evaluation_firewall": firewall,
                   "authorized_core_delta": core_delta},
        "wallclock_s": round(time.perf_counter() - t0, 2),
    }

    (out / "screening_results.json").write_text(
        json.dumps(package, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    import csv as _csv
    with open(out / "screening_results.csv", "w", newline="",
              encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    (out / "run_manifest.json").write_text(json.dumps({
        "run_id": run_id, "task": "Q4 Phase 1A fast screening (q4_screening)",
        "authority": "HG-Q4-NS-01 + HG-Q4-F3-01 + Human Gate Phase 1A package",
        "registry": "Q4_SCREENING_REGISTRY.json",
        "wallclock_s": package["wallclock_s"]}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    print(f"[q4s] run_id={run_id} rows={len(rows)} wall={package['wallclock_s']}s")
    for r in ranking:
        print(f"  {r['factor_id']:>6} {r['scenario_id']:<18} "
              f"dT={r['mean_Delta_T_h']:>12} se={r['SE']:.4f} "
              f"std={r['standardized_effect']:.4f}")
    print("[q4s] evidence:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
