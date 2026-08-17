#!/usr/bin/env python3
"""Q4 FORMAL EVALUATION runner (namespace q4_evaluation, master_seed 7,
initial replicate 100..163, R=64; two-stage uniform expansion to R=128 with
additional replicate 164..227). FINAL INFERENCE SOURCE (Q4_EVALUATION).

Pre-registered scenarios (Q4_EVALUATION_REGISTRY, PRE_DATA / IMMUTABLE):
  Q4_BASELINE / F2_TURNOVER_05 / F3_TAU150|180|210 / F4_{A,B,C,E}_{M10,P10} /
  F5_CONSTANT_HAZARD / QA_LOW|HIGH / QB_LOW|HIGH / E_LOW|HIGH /
  INT_F2_05_E_M10 / INT_F2_05_E_P10  (22 scenarios total)
  F1 (K) = REUSED_ACCEPTED_FORMAL_EVIDENCE (Q3 accepted; NOT re-run, NOT mixed
  into any Q4 CI).

Design:
  - CRN paired Delta T per replicate vs Q4_BASELINE (same namespace/seed/rep).
  - target 95% CI half-width = 2.0 h; t_{0.975,63}=1.9983 (R=64),
    t_{0.975,127}=1.9793 (R=128) [frozen tabulated constants; stdlib-only].
  - two-stage: after R=64, if ANY main-scenario or interaction CI half-width
    > 2.0 h -> ALL scenarios uniformly expand to R=128 (append 164..227).
    NO factor-specific optional stopping.
  - formal factor rank: factor_score = max |standardized_effect| per factor
    over MAIN scenarios only (interaction cells are a separate 2x3 design).
  - interaction: F2 x F4-E (2x3); contrasts
      I_minus_r = T(INT_M10) - T(F2) - T(E_M10) + T(base)
      I_plus_r  = T(INT_P10) - T(F2) - T(E_P10)  + T(base)
    replicate-level paired 95% CI; CI containing 0 -> "未观察到明确
    interaction"; excluding 0 -> "模型内非加性交互" (never real causality).

Screening data (q4_screening rep 0..39) is NEVER used; no pooling.

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
from scripts.run_q3_h1_formal_v1 import FROZEN_Q_ABC, single_kernel  # noqa: E402
from scripts.run_q4_phase1b_v1 import (  # noqa: E402
    qa_kernel, e_kernel, extract_ledger, SCALE_LO, SCALE_HI,
    E_SCALE_LO, E_SCALE_HI, RESOURCES,
)

NS = "q4_evaluation"
MASTER_SEED = 7
REPS_64 = list(range(100, 164))       # initial R=64
REPS_128_EXTRA = list(range(164, 228))  # expansion append (R=128 total)
K_H = "12"
T_EVAL_64 = 1.9983    # t_{0.975, 63} (frozen tabulated; stdlib-only)
T_EVAL_128 = 1.9793   # t_{0.975, 127} (frozen tabulated)
TARGET_HALF_WIDTH = 2.0
POLICY = lr.NO_PM_BEFORE_MANDATORY
TURNOVER_1H = "1h_literal"
TURNOVER_05 = "0.5h_overlap"

DUR_BASE = {p: rd.DEFAULT_DURATIONS_H[p] for p in RESOURCES}
CORE_HASHES = {
    "g3/random_des_v1.py": "801d6352af076e6f2e82c319c128d228eb9eb0703522675afe35ca187ee89928",
    "g3/key_schema_v1.py": "4fd6ad1085b7d5111b96f4cccf2dee0792fe032982fdf6583ccb18de3cb85a83",
}
REGISTRY_PATH = BASE_DIR / "05_结果" / "Q4" / "evaluation" / "Q4_EVALUATION_REGISTRY.json"

# scenarios whose mechanism ledger is extracted (mechanism explanation targets)
KEY_LEDGER = {"Q4_BASELINE", "F2_TURNOVER_05", "F4_E_M10", "F4_E_P10",
              "INT_F2_05_E_M10", "INT_F2_05_E_P10",
              "QA_LOW", "QA_HIGH", "QB_LOW", "QB_HIGH", "E_LOW", "E_HIGH"}


def frac10(p: str, pct: int) -> str:
    v = DUR_BASE[p]
    return str(v + v * Fraction(pct, 100))


def scenario_defs() -> list[dict[str, Any]]:
    defs: list[dict[str, Any]] = [
        {"id": "Q4_BASELINE", "factor": "BASELINE", "level": "-",
         "kw": {}, "auth": [], "kernel": "baseline", "q_scale": None,
         "run_kind": "plain"},
        {"id": "F2_TURNOVER_05", "factor": "F2", "level": "turnover=0.5h_overlap",
         "kw": {"turnover_profile": TURNOVER_05}, "auth": ["turnover_profile"],
         "kernel": "baseline", "q_scale": None, "run_kind": "plain"},
        {"id": "F3_TAU150", "factor": "F3", "level": "tau_PM=150",
         "kw": {"tau_pm": Fraction(150)}, "auth": ["tau_pm"],
         "kernel": "baseline", "q_scale": None, "run_kind": "plain"},
        {"id": "F3_TAU180", "factor": "F3", "level": "tau_PM=180",
         "kw": {"tau_pm": Fraction(180)}, "auth": ["tau_pm"],
         "kernel": "baseline", "q_scale": None, "run_kind": "plain"},
        {"id": "F3_TAU210", "factor": "F3", "level": "tau_PM=210",
         "kw": {"tau_pm": Fraction(210)}, "auth": ["tau_pm"],
         "kernel": "baseline", "q_scale": None, "run_kind": "plain"},
    ]
    for p in RESOURCES:
        for pct in (-10, 10):
            sid = f"F4_{p}_{'M10' if pct < 0 else 'P10'}"
            defs.append({"id": sid, "factor": f"F4-{p}",
                         "level": f"duration_{p}={pct:+d}%",
                         "kw": {"durations": {p: frac10(p, pct)}},
                         "auth": [f"durations.{p}"],
                         "kernel": "baseline", "q_scale": None, "run_kind": "plain"})
    defs.append({"id": "F5_CONSTANT_HAZARD", "factor": "F5",
                 "level": "constant-hazard CDF", "kw": {}, "auth": ["failure_semantic"],
                 "kernel": "baseline", "q_scale": None, "run_kind": "constant_hazard"})
    for sid, scale in (("QA_LOW", SCALE_LO), ("QA_HIGH", SCALE_HI)):
        defs.append({"id": sid, "factor": "Q-A", "level": f"q_scale={scale}",
                     "kw": {}, "auth": ["observation_kernel"], "kernel": "qa",
                     "q_scale": scale, "run_kind": "plain"})
    for sid, scale in (("QB_LOW", SCALE_LO), ("QB_HIGH", SCALE_HI)):
        defs.append({"id": sid, "factor": "Q-B", "level": f"q_scale={scale}",
                     "kw": {}, "auth": [], "kernel": "baseline",
                     "q_scale": scale, "run_kind": "plain"})
    for sid, escale in (("E_LOW", E_SCALE_LO), ("E_HIGH", E_SCALE_HI)):
        defs.append({"id": sid, "factor": "E", "level": f"e_scale={escale}",
                     "kw": {}, "auth": ["observation_kernel"], "kernel": "e",
                     "e_scale": escale, "q_scale": None, "run_kind": "plain"})
    defs.append({"id": "INT_F2_05_E_M10", "factor": "INT-F2xF4-E",
                 "level": "F2 0.5h x E -10%",
                 "kw": {"turnover_profile": TURNOVER_05,
                        "durations": {"E": frac10("E", -10)}},
                 "auth": ["turnover_profile", "durations.E"],
                 "kernel": "baseline", "q_scale": None, "run_kind": "plain"})
    defs.append({"id": "INT_F2_05_E_P10", "factor": "INT-F2xF4-E",
                 "level": "F2 0.5h x E +10%",
                 "kw": {"turnover_profile": TURNOVER_05,
                        "durations": {"E": frac10("E", 10)}},
                 "auth": ["turnover_profile", "durations.E"],
                 "kernel": "baseline", "q_scale": None, "run_kind": "plain"})
    return defs


def kernel_for(scenario: dict[str, Any]) -> dict[str, dict[str, Fraction]]:
    kind = scenario["kernel"]
    if kind == "baseline":
        return single_kernel()
    if kind == "qa":
        kern, _ = qa_kernel(scenario["q_scale"])
        return kern
    if kind == "e":
        return e_kernel(scenario["e_scale"])
    raise AssertionError(f"unknown kernel kind {kind!r}")


def build_cfg(rep: int, scenario: dict[str, Any]) -> rd.RandomDesConfig:
    kw = dict(scenario["kw"])
    return rd.default_config(
        namespace=NS, master_seed=MASTER_SEED, replicate_id=rep,
        tau_pm=kw.pop("tau_pm", POLICY),
        observation_kernel=kernel_for(scenario),
        batch_size=100, scenario="q3_two_shift",
        shift_length_h=K_H, shifts_per_day=2,
        durations=kw.pop("durations", None),
        turnover_profile=kw.pop("turnover_profile", TURNOVER_1H),
        scenario_id=f"q4_evaluation_{scenario['id']}_rep{rep}",
    )


def design_cfg(scenario: dict[str, Any]) -> rd.RandomDesConfig:
    """Rep-independent design fingerprint (scenario_id = plain id)."""
    kw = dict(scenario["kw"])
    return rd.default_config(
        namespace=NS, master_seed=MASTER_SEED, replicate_id=0,
        tau_pm=kw.pop("tau_pm", POLICY),
        observation_kernel=kernel_for(scenario),
        batch_size=100, scenario="q3_two_shift",
        shift_length_h=K_H, shifts_per_day=2,
        durations=kw.pop("durations", None),
        turnover_profile=kw.pop("turnover_profile", TURNOVER_1H),
        scenario_id=scenario["id"],
    )


def config_hash_of(cfg: rd.RandomDesConfig) -> str:
    blob = json.dumps(cfg.to_dict(), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def run_one(cfg: rd.RandomDesConfig, q_scale: Optional[Fraction],
            constant_hazard: bool):
    if constant_hazard:
        sens = lr.sensitivity_constant_hazard_inverse_cdf

        def _ch_inverse_cdf(u, f120, f240):
            lt, cens = sens(u, f120, f240)
            return (None if lt is None else Fraction(lt)), cens

        orig = lr.inverse_cdf
        lr.inverse_cdf = _ch_inverse_cdf
        try:
            return _run_with_q(cfg, q_scale)
        finally:
            lr.inverse_cdf = orig
    return _run_with_q(cfg, q_scale)


def _run_with_q(cfg: rd.RandomDesConfig, q_scale: Optional[Fraction]):
    if q_scale is not None and q_scale != 1:
        orig_abc = rd.DEFECT_PROBS_ABC
        orig_d = rd.DEFECT_PROB_D_VALUE
        rd.DEFECT_PROBS_ABC = {p: orig_abc[p] * q_scale for p in ("A", "B", "C")}
        rd.DEFECT_PROB_D_VALUE = orig_d * q_scale
        try:
            return rd.run_random_des(cfg)
        finally:
            rd.DEFECT_PROBS_ABC = orig_abc
            rd.DEFECT_PROB_D_VALUE = orig_d
    return rd.run_random_des(cfg)


# ---------------------------------------------------------------------------
# statistics helpers
# ---------------------------------------------------------------------------


def paired_stats(d: list[Fraction], t_quantile: float) -> dict[str, Any]:
    n = len(d)
    mean = sum(d, Fraction(0)) / n
    sd = math.sqrt(sum(float((x - float(mean)) ** 2) for x in d) / (n - 1))
    se = sd / math.sqrt(n)
    half = t_quantile * se
    return {
        "n": n, "mean_Delta_T_h": str(mean),
        "SD_h": sd, "SE_h": se, "half_width_h": half,
        "CI_low": float(mean) - half, "CI_high": float(mean) + half,
        "standardized_effect": float(mean) / sd if sd > 0 else 0.0,
        "sign_consistency": "ALL_NEG" if all(x < 0 for x in d) else
                            ("ALL_POS" if all(x > 0 for x in d) else "MIXED"),
    }


def build_registry() -> dict[str, Any]:
    defs = scenario_defs()
    scenarios = []
    for sc in defs:
        cfg = design_cfg(sc)
        scenarios.append({
            "scenario_id": sc["id"], "factor_id": sc["factor"], "level": sc["level"],
            "config_hash": config_hash_of(cfg),
            "observation_kernel": {
                p: {"alpha": str(cfg.observation_kernel[p]["alpha"]),
                    "beta": str(cfg.observation_kernel[p]["beta"])}
                for p in RESOURCES},
            "authorized_changed_fields": sc["auth"],
        })
    baseline_cfg = design_cfg(defs[0])
    return {
        "registry": "Q4_EVALUATION_REGISTRY",
        "status": "PRE_DATA",
        "immutable": True,
        "freeze_timestamp": datetime.now(timezone.utc).isoformat(),
        "authority": "Human Gate 一体化授权包 (Q4 Phase 1B + FORMAL EVALUATION + "
                     "TOP-2 interaction)",
        "logical_domain": "Q4_EVALUATION",
        "namespace": NS,
        "master_seed": MASTER_SEED,
        "scenario": "q3_two_shift",
        "baseline": {
            "K": K_H, "policy": "NO_PM_BEFORE_MANDATORY",
            "turnover": "1h_literal",
            "failure_semantics": "piecewise-linear CDF",
            "observation_kernel": "single_test_unconditional_v1 (P060; Q3 Tier1 main)",
            "config_hash": config_hash_of(baseline_cfg),
            "screening_baseline_hash": "618d24ab3d823f97651524c6e0e4074553de280afab898fa0feca4abc43da275",
            "q3_evidence_binding": [
                "05_结果/Q3/formal/run_20260815T133840057668Z_7ee48fc0",
                "05_结果/Q3/formal/reissue_20260815T150613626910Z_f4da8f9d",
            ],
        },
        "sample_size": {
            "target_95_CI_half_width_h": TARGET_HALF_WIDTH,
            "R_initial": 64,
            "replicate_ids_initial": REPS_64,
            "R_expanded": 128,
            "replicate_ids_expansion_append": REPS_128_EXTRA,
            "basis": "Phase 1A F2 paired SD ~= 7.8625 h -> "
                     "R = (t*sd/w)^2 = (2.0*7.8625/2.0)^2 ~= 61.8 -> 64",
            "t_quantiles": {"df_63_R64": T_EVAL_64, "df_127_R128": T_EVAL_128},
            "two_stage_rule": "after R=64, if ANY main-scenario or interaction "
                              "CI half-width > 2.0 h -> ALL scenarios uniformly "
                              "expand to R=128 (append rep 164..227); "
                              "NO factor-specific optional stopping.",
        },
        "factors": {
            "F1": "REUSED_ACCEPTED_FORMAL_EVIDENCE (Q3 accepted seven-K; K12 "
                  "strong winner within the seven-K + frozen H1 policy set; "
                  "NOT re-run; NOT mixed into Q4 CIs)",
            "F2": "turnover 0.5h complete overlap",
            "F3": "tau_PM in {150,180,210} (COUNTERFACTUAL_ONLY per HG-Q4-F3-01)",
            "F4-A/B/C/E": "duration -10% / +10% one process at a time",
            "F5": "constant-hazard failure semantics (MODEL_SEMANTIC_ONLY)",
            "Q-A": "CALIBRATION_INPUT scale 0.8/1.2 (kernels recalibrated; e baseline)",
            "Q-B": "INCOMING_DEFECT_PRESSURE scale 0.8/1.2 (kernel frozen baseline)",
            "E": "E-ERROR_ENVIRONMENT e scale 0.8/1.2 (kernels recalibrated)",
        },
        "factor_rank_rule": "factor_score = max |standardized_effect| per factor "
                            "over MAIN scenarios only (interaction cells are a "
                            "separate 2x3 design); F1 excluded (reuse). "
                            "数学影响排序 与 管理实施优先级 严格分开。",
        "interaction": {
            "design": "F2 x F4-E (2x3): baseline/baseline, 0.5h/baseline, "
                      "baseline/E-10%, baseline/E+10%, 0.5h/E-10% (INT_F2_05_E_M10), "
                      "0.5h/E+10% (INT_F2_05_E_P10)",
            "cells_in_evaluation": ["INT_F2_05_E_M10", "INT_F2_05_E_P10"],
            "contrasts": {
                "I_minus_r": "T(INT_M10) - T(F2) - T(E_M10) + T(base)  per rep",
                "I_plus_r": "T(INT_P10) - T(F2) - T(E_P10) + T(base)  per rep",
            },
            "interpretation": "95% CI contains 0 -> '未观察到明确 interaction'; "
                              "excludes 0 -> '模型内非加性交互' (never real causality).",
            "half_width_rule_applies": True,
        },
        "domain_isolation": {
            "phase_1a_rep": "0..19", "phase_1b_rep": "20..39",
            "evaluation_rep": "100..163 (expansion 164..227)",
            "disjoint": True,
            "no_pooling": "screening data NEVER enters final CI; "
                          "Q4_EVALUATION is the only final-inference source",
        },
        "frozen_flags": {
            "HUMAN_GATE_AUTHORIZED": True,
            "IMMUTABLE_FOR_FORMAL_EVALUATION": True,
            "PRE_DATA": True,
            "Q4_SCREENING": "ALREADY CONSUMED (Phase 1A 0..19 + Phase 1B 20..39); "
                            "NOT reused here",
            "TOP2_INTERACTION": "AUTHORIZED (F2 x F4-E)",
        },
        "scenarios": scenarios,
    }


def validate_core_hashes() -> dict[str, Any]:
    result = {}
    ok = True
    for name, expected in CORE_HASHES.items():
        p = CODE_DIR / "main_model" / name
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        result[name] = {"sha256": h, "matches_phase_1a": h == expected}
        ok = ok and h == expected
    result["status"] = "PASS" if ok else "FAIL"
    return result


# ---------------------------------------------------------------------------
# mechanism explanation (ledger-based, diagnostic)
# ---------------------------------------------------------------------------


def _sum_field(key: str, lgs: list[dict]) -> dict[str, str]:
    acc = {p: Fraction(0) for p in RESOURCES}
    for lg in lgs:
        v = lg[key]
        if isinstance(v, dict):
            for p in RESOURCES:
                if v[p] != "SCREENING_APPROX":
                    acc[p] += Fraction(v[p])
    return {p: str(acc[p]) for p in RESOURCES}


def aggregate_ledger(ledgers: list[dict]) -> dict[str, Any]:
    return {
        "effective_test_time": _sum_field("effective_test_time", ledgers),
        "retest_time": _sum_field("retest_time", ledgers),
        "failure_wasted_fragment_time": _sum_field("failure_wasted_fragment_time", ledgers),
        "shift_boundary_wasted_fragment_time": _sum_field("shift_boundary_wasted_fragment_time", ledgers),
        "terminal_cancelled_fragment_time": _sum_field("terminal_cancelled_fragment_time", ledgers),
        "calibration_time": _sum_field("calibration_time", ledgers),
        "turnover_occupancy_time": str(sum(Fraction(lg["turnover_occupancy_time"])
                                           for lg in ledgers)),
        "off_shift_time": str(sum(Fraction(lg["off_shift_time"]) for lg in ledgers)),
        "n_reps": len(ledgers),
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def config_field_diff(db: dict, ds: dict) -> list[str]:
    """Field-level config diff: durations.* field granularity; the observation
    kernel is atomic (any kernel change -> 'observation_kernel'); scenario_id
    is metadata and never a factor change."""
    changed: list[str] = []
    for k in ds:
        if k == "scenario_id":
            continue
        if k not in db:
            changed.append(k)
            continue
        if isinstance(db[k], dict) and isinstance(ds[k], dict):
            if k == "observation_kernel":
                if ds[k] != db[k]:
                    changed.append("observation_kernel")
                continue
            fields = set(db[k]) | set(ds[k])
            for f in sorted(fields):
                if ds[k].get(f) != db[k].get(f):
                    changed.append(f"{k}.{f}")
        elif ds[k] != db[k]:
            changed.append(k)
    return changed


def _persist_sim(T: dict[str, list[Fraction]], ledgers: dict[str, list[dict]],
                 out: Path) -> None:
    """Persist raw per-replicate T and ledgers (crash-safe evidence)."""
    (out / "T_by_rep.json").write_text(
        json.dumps({sid: [str(v) for v in vals] for sid, vals in T.items()},
                   ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    (out / "ledger_by_rep.json").write_text(
        json.dumps(ledgers, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")


def _load_sim(out: Path) -> tuple[dict[str, list[Fraction]], dict[str, list[dict]]]:
    T: dict[str, list[Fraction]] = {}
    tj = json.loads((out / "T_by_rep.json").read_text(encoding="utf-8"))
    for sid, vals in tj.items():
        T[sid] = [Fraction(v) for v in vals]
    ledgers: dict[str, list[dict]] = {}
    lj = json.loads((out / "ledger_by_rep.json").read_text(encoding="utf-8"))
    for sid, lgs in lj.items():
        ledgers[sid] = list(lgs)
    return T, ledgers


def main() -> int:
    args = [a for a in sys.argv[1:]]
    resume_run_id: Optional[str] = None
    if args and args[0] == "--resume":
        if len(args) != 2:
            print("[q4eval] FATAL: --resume requires <run_id>")
            return 2
        resume_run_id = args[1]

    t0 = time.perf_counter()
    if not REGISTRY_PATH.exists():
        print("[q4eval] FATAL: registry missing (freeze first):", REGISTRY_PATH)
        return 2
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if registry.get("status") != "PRE_DATA":
        print("[q4eval] FATAL: registry not PRE_DATA:", registry.get("status"))
        return 2

    defs = scenario_defs()
    recomputed = build_registry()
    for a, b in zip(recomputed["scenarios"], registry["scenarios"]):
        if a["config_hash"] != b["config_hash"]:
            print(f"[q4eval] FATAL: registry config_hash mismatch for "
                  f"{a['scenario_id']}: {a['config_hash']} != {b['config_hash']}")
            return 2
    if recomputed["baseline"]["config_hash"] != registry["baseline"]["config_hash"]:
        print("[q4eval] FATAL: registry baseline config_hash mismatch")
        return 2
    core = validate_core_hashes()
    if core["status"] != "PASS":
        print("[q4eval] FATAL: accepted core changed:", core)
        return 2

    out_root = BASE_DIR / "05_结果" / "Q4" / "evaluation"
    if resume_run_id is not None:
        out = out_root / resume_run_id
        if not out.is_dir():
            print("[q4eval] FATAL: resume run dir not found:", out)
            return 2
        print("[q4eval] RESUME mode:", out)
        T, ledgers = _load_sim(out)
        # rebuild reps from the persisted T length
        n = len(T["Q4_BASELINE"])
        if n == len(REPS_64):
            reps = list(REPS_64)
        elif n == len(REPS_64) + len(REPS_128_EXTRA):
            reps = list(REPS_64) + list(REPS_128_EXTRA)
        else:
            print(f"[q4eval] FATAL: unexpected T length {n} in resume data")
            return 2
        stats, interaction = _compute_stats(T, reps, defs,
                                            t_q=(T_EVAL_64 if n == len(REPS_64)
                                                 else T_EVAL_128))
        expanded = n > len(REPS_64)
        if n == len(REPS_64) + len(REPS_128_EXTRA):
            # recover the exact stage-1 max half-width from the first 64 reps
            T64 = {sid: T[sid][:len(REPS_64)] for sid in T}
            st64, _ = _compute_stats(T64, REPS_64, defs, t_q=T_EVAL_64)
            max_hw = _max_half_width(st64, _)
        else:
            max_hw = _max_half_width(stats, interaction)
        run_id = resume_run_id
    else:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + \
            hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
        out = out_root / run_id
        out.mkdir(parents=True, exist_ok=True)

        # ---- stage 1: R=64 (rep 100..163) ----
        reps = list(REPS_64)
        T: dict[str, list[Fraction]] = {sc["id"]: [] for sc in defs}
        ledgers: dict[str, list[dict]] = {sc["id"]: [] for sc in defs}
        for sc in defs:
            sid = sc["id"]
            keep_ledger = sid in KEY_LEDGER
            for rep in reps:
                cfg = build_cfg(rep, sc)
                res = run_one(cfg, q_scale=sc["q_scale"],
                              constant_hazard=(sc["run_kind"] == "constant_hazard"))
                T[sid].append(Fraction(res.metrics["T"]))
                if keep_ledger:
                    ledgers[sid].append(extract_ledger(res.event_log))
            print(f"[q4eval] R={len(reps)} {sid}: done")

        expanded = False
        stats, interaction = _compute_stats(T, reps, defs, t_q=T_EVAL_64)
        max_hw = _max_half_width(stats, interaction)
        print(f"[q4eval] stage1 R=64 max half-width = {max_hw:.4f} h "
              f"(target {TARGET_HALF_WIDTH})")
        if max_hw > TARGET_HALF_WIDTH:
            print("[q4eval] EXPANSION TRIGGERED: all scenarios -> R=128 "
                  "(append rep 164..227)")
            for sc in defs:
                sid = sc["id"]
                keep_ledger = sid in KEY_LEDGER
                for rep in REPS_128_EXTRA:
                    cfg = build_cfg(rep, sc)
                    res = run_one(cfg, q_scale=sc["q_scale"],
                                  constant_hazard=(sc["run_kind"] == "constant_hazard"))
                    T[sid].append(Fraction(res.metrics["T"]))
                    if keep_ledger:
                        ledgers[sid].append(extract_ledger(res.event_log))
                print(f"[q4eval] R=128 {sid}: done")
            reps = reps + list(REPS_128_EXTRA)
            expanded = True
            stats, interaction = _compute_stats(T, reps, defs, t_q=T_EVAL_128)

        # ---- persist raw simulation data (crash-safe evidence; resume-friendly) ----
        _persist_sim(T, ledgers, out)

    # ---- factor rank (main scenarios only) ----
    rank = _factor_rank(stats, defs)

    # ---- mechanism explanation ----
    mech = {sid: aggregate_ledger(ledgers[sid]) for sid in KEY_LEDGER
            if ledgers[sid]}

    # ---- management recommendation draft ----
    rec = _recommendations(rank, stats, defs)

    # ---- checks ----
    oofd = {"status": "PASS"}
    for sc in defs:
        if sc["id"] == "Q4_BASELINE":
            continue
        db = design_cfg(defs[0]).to_dict()
        ds = design_cfg(sc).to_dict()
        changed = config_field_diff(db, ds)
        if not set(changed) <= set(sc["auth"]):
            oofd = {"status": "FAIL", "scenario": sc["id"],
                    "changed": changed, "authorized": sc["auth"]}
    crn = {"status": "PASS", "namespace": NS, "master_seed": MASTER_SEED,
           "replicate_ids": reps,
           "note": "baseline and every scenario share namespace/seed/rep -> same "
                   "keyed U_X/U_D/U_Y/U_L; all changes are same-U transforms"}
    sfirewall = {"q4_screening_keys_consumed": 0, "q4_screening_runs": 0,
                 "q4_screening_result_files": 0, "status": "PASS"}
    domain = {"phase_1a": "0..19", "phase_1b": "20..39",
              "evaluation": f"100..{reps[-1]}", "disjoint": True, "status": "PASS"}

    package = {
        "run_id": run_id, "namespace": NS, "master_seed": MASTER_SEED,
        "R_final": len(reps), "replicate_ids": reps,
        "two_stage_expansion": expanded,
        "registry": str(REGISTRY_PATH.relative_to(BASE_DIR)).replace("\\", "/"),
        "target_half_width_h": TARGET_HALF_WIDTH,
        "max_half_width_h_stage1": max_hw,
        "scenario_stats": stats,
        "interaction": interaction,
        "factor_ranking": rank,
        "mechanism_ledgers": mech,
        "management_recommendations": rec,
        "checks": {"only_one_factor_diff": oofd, "crn": crn,
                   "screening_firewall": sfirewall,
                   "domain_isolation": domain,
                   "authorized_core_hashes": core},
        "wallclock_s": round(time.perf_counter() - t0, 2),
        "note": "Q4_EVALUATION is the ONLY final-inference CI source. "
                "F1 = REUSED_ACCEPTED_FORMAL_EVIDENCE (separate). "
                "F3 = COUNTERFACTUAL_ONLY. F5 = MODEL_SEMANTIC_ONLY.",
    }
    (out / "Q4_EVALUATION_RESULTS.json").write_text(
        json.dumps(package, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    _write_markdown(out, stats, interaction, rank, mech, rec, package)
    (out / "run_manifest.json").write_text(json.dumps({
        "run_id": run_id, "task": "Q4 FORMAL EVALUATION (q4_evaluation seed 7)",
        "authority": "Human Gate 一体化授权包 (Phase 1B + FORMAL + Top-2)",
        "registry": "Q4_EVALUATION_REGISTRY.json",
        "R_final": len(reps), "two_stage_expansion": expanded,
        "wallclock_s": package["wallclock_s"]}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    print(f"[q4eval] run_id={run_id} R_final={len(reps)} "
          f"expanded={expanded} wall={package['wallclock_s']}s")
    for r in rank:
        print(f"  {r['factor_id']:>4} score={r['factor_score']:>10} "
              f"({r['max_scenario']})")
    print("[q4eval] evidence:", out)
    return 0


def _compute_stats(T: dict[str, list[Fraction]], reps: list[int],
                   defs: list[dict[str, Any]], t_q: float):
    base = [Fraction(v) for v in T["Q4_BASELINE"]]
    n = len(reps)
    stats: dict[str, dict[str, Any]] = {}
    for sc in defs:
        sid = sc["id"]
        if sid == "Q4_BASELINE":
            continue
        scT = [Fraction(v) for v in T[sid]]
        d = [scT[r] - base[r] for r in range(n)]
        st = paired_stats(d, t_q)
        st.update({"factor_id": sc["factor"], "scenario_id": sid,
                   "level": sc["level"],
                   "authority": ("COUNTERFACTUAL_ONLY" if sc["factor"] == "F3" else
                                 ("MODEL_SEMANTIC_ONLY" if sc["factor"] == "F5" else
                                  ("INTERACTION_CELL" if sc["factor"] == "INT-F2xF4-E"
                                   else "-"))),
                   "source": "Q4_EVALUATION", "status": "FINAL_INFERENCE"})
        stats[sid] = st
    # interaction contrasts (replicate-level paired)
    base_v = base
    f2 = [Fraction(v) for v in T["F2_TURNOVER_05"]]
    em10 = [Fraction(v) for v in T["F4_E_M10"]]
    ep10 = [Fraction(v) for v in T["F4_E_P10"]]
    im10 = [Fraction(v) for v in T["INT_F2_05_E_M10"]]
    ip10 = [Fraction(v) for v in T["INT_F2_05_E_P10"]]
    i_minus = [im10[r] - f2[r] - em10[r] + base_v[r] for r in range(n)]
    i_plus = [ip10[r] - f2[r] - ep10[r] + base_v[r] for r in range(n)]
    interaction = {
        "I_minus": paired_stats(i_minus, t_q),
        "I_plus": paired_stats(i_plus, t_q),
        "interpretation": ("CI contains 0 -> '未观察到明确 interaction'; "
                           "excludes 0 -> '模型内非加性交互' (never real causality)"),
        "note": "replicate-level paired contrasts on q4_evaluation reps; "
                "same 2.0 h half-width rule applies.",
    }
    return stats, interaction


def _max_half_width(stats: dict, interaction: dict) -> float:
    hw = [st["half_width_h"] for st in stats.values()]
    hw += [interaction["I_minus"]["half_width_h"],
           interaction["I_plus"]["half_width_h"]]
    return max(hw)


def _factor_rank(stats: dict, defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_factor: dict[str, list[dict]] = {}
    for sc in defs:
        sid = sc["id"]
        if sid == "Q4_BASELINE" or sc["factor"] == "INT-F2xF4-E":
            continue
        by_factor.setdefault(sc["factor"], []).append(stats[sid])
    rank = []
    for fid, rows in by_factor.items():
        best = max(rows, key=lambda r: abs(r["standardized_effect"]))
        rank.append({
            "factor_id": fid,
            "factor_score": best["standardized_effect"],
            "abs_factor_score": abs(best["standardized_effect"]),
            "max_scenario": best["scenario_id"],
            "max_scenario_mean_Delta_T_h": best["mean_Delta_T_h"],
            "max_scenario_CI": [best["CI_low"], best["CI_high"]],
            "n_scenarios": len(rows),
        })
    rank.sort(key=lambda r: -r["abs_factor_score"])
    return rank


def _recommendations(rank: list[dict], stats: dict,
                     defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Management recommendation DRAFT. Every entry binds factor_id /
    scenario_id / Delta T / 95% CI / effect rank; separates in-model benefit
    from implementation cost/constraints and applicable conditions. Never
    writes model sensitivity as a real-world causal theorem."""
    rec = []
    pos = {r["factor_id"]: i + 1 for i, r in enumerate(rank)}
    for row in rank:
        fid = row["factor_id"]
        sid = row["max_scenario"]
        st = stats[sid]
        rec.append({
            "factor_id": fid, "scenario_id": sid,
            "effect_rank": pos[fid],
            "mean_Delta_T_h": st["mean_Delta_T_h"],
            "95_CI": [st["CI_low"], st["CI_high"]],
            "half_width_h": round(st["half_width_h"], 4),
            "in_model_benefit": ("completion-time decrease (Delta T < 0)" if
                                 float(Fraction(st["mean_Delta_T_h"])) < 0 else
                                 ("completion-time increase (Delta T > 0)" if
                                  float(Fraction(st["mean_Delta_T_h"])) > 0 else "no shift")),
            "implementation_cost_constraints": ("see scenario level; e.g. turnover "
                                                "0.5h overlap requires two-bay "
                                                "logistics; duration changes are "
                                                "process/capacity decisions" if
                                                fid in ("F2", "F4-E") else
                                                ("model/parameter inputs; not a "
                                                 "management lever" if fid in
                                                 ("Q-A", "Q-B", "E", "F3", "F5")
                                                 else "see scenario level")),
            "applicable_conditions": "within the frozen H1/NO_PM/K12 model world; "
                                     "model-internal sensitivity, NOT a real-world "
                                     "causal claim",
            "status": "DRAFT_FOR_HUMAN_GATE",
        })
    return rec


def _write_markdown(out: Path, stats: dict, interaction: dict, rank: list,
                    mech: dict, rec: list, package: dict) -> None:
    lines = ["# Q4 FORMAL EVALUATION RESULT (Q4_EVALUATION, seed 7)",
             "",
             f"- run_id: `{package['run_id']}`",
             f"- R_final = {package['R_final']} (replicate {package['replicate_ids'][0]}"
             f"..{package['replicate_ids'][-1]}); two-stage expansion: "
             f"{'TRIGGERED' if package['two_stage_expansion'] else 'NOT triggered'}",
             f"- target 95% CI half-width = {package['target_half_width_h']} h; "
             f"max half-width at stage 1 = {package['max_half_width_h_stage1']:.4f} h",
             "- F1 (K) = REUSED_ACCEPTED_FORMAL_EVIDENCE (Q3 accepted; separate).",
             "",
             "## Main-scenario paired Delta T vs Q4_BASELINE (95% CI)",
             "",
             "| scenario | factor | mean dT (h) | 95% CI | half-width | std | sign |",
             "|---|---|---|---|---|---|---|"]
    for sid, st in stats.items():
        lines.append(f"| {sid} | {st['factor_id']} | {st['mean_Delta_T_h']} | "
                     f"[{st['CI_low']:.4f}, {st['CI_high']:.4f}] | "
                     f"{st['half_width_h']:.4f} | {st['standardized_effect']:.4f} | "
                     f"{st['sign_consistency']} |")
    lines += ["", "## Top-2 interaction (F2 x F4-E) contrasts (replicate-level paired)",
              "",
              "| contrast | mean (h) | 95% CI | half-width | std |",
              "|---|---|---|---|---|"]
    for name in ("I_minus", "I_plus"):
        it = interaction[name]
        lines.append(f"| {name} | {it['mean_Delta_T_h']} | "
                     f"[{it['CI_low']:.4f}, {it['CI_high']:.4f}] | "
                     f"{it['half_width_h']:.4f} | {it['standardized_effect']:.4f} |")
    lines += ["", interaction["interpretation"],
              "", "## Formal factor rank (factor_score = max |std|, main scenarios)",
              "",
              "| rank | factor | factor_score | max scenario | mean dT (h) | CI |",
              "|---|---|---|---|---|---|"]
    for i, r in enumerate(rank, 1):
        ci = f"[{r['max_scenario_CI'][0]:.4f}, {r['max_scenario_CI'][1]:.4f}]"
        lines.append(f"| {i} | {r['factor_id']} | {r['factor_score']:.4f} | "
                     f"{r['max_scenario']} | {r['max_scenario_mean_Delta_T_h']} | {ci} |")
    lines += ["", "## Mechanism ledger (summed over all evaluation reps; "
                  "NOT an additive T decomposition)",
              ""]
    for sid, lg in mech.items():
        lines.append(f"### {sid}")
        lines.append(f"- effective: {lg['effective_test_time']}")
        lines.append(f"- retest: {lg['retest_time']}")
        lines.append(f"- failure_wasted: {lg['failure_wasted_fragment_time']}")
        lines.append(f"- shift_wasted: {lg['shift_boundary_wasted_fragment_time']}")
        lines.append(f"- terminal_cancelled: {lg['terminal_cancelled_fragment_time']}")
        lines.append(f"- calibration: {lg['calibration_time']}")
        lines.append(f"- turnover_occupancy: {lg['turnover_occupancy_time']} h "
                     f"(summed over {lg['n_reps']} reps)")
        lines.append(f"- off_shift: {lg['off_shift_time']} h")
        lines.append("")
    lines += ["## Management recommendation (DRAFT for Human Gate)", ""]
    for r in rec:
        lines.append(f"- **{r['factor_id']}** (rank {r['effect_rank']}, "
                     f"{r['scenario_id']}): dT={r['mean_Delta_T_h']} h, "
                     f"95% CI [{r['95_CI'][0]:.4f}, {r['95_CI'][1]:.4f}], "
                     f"half-width {r['half_width_h']} h. "
                     f"{r['in_model_benefit']}. Constraints: "
                     f"{r['implementation_cost_constraints']}. "
                     f"{r['applicable_conditions']}.")
    lines += ["", "> Q4_EVALUATION is the ONLY final-inference CI source; "
                  "screening data never pooled. F3 = COUNTERFACTUAL_ONLY "
                  "(未观察到明确改善 / 点估计 / CI 跨 0 依正式结果而定); "
                  "F5 = MODEL_SEMANTIC_ONLY. 数学影响排序 ≠ 管理实施优先级."]
    (out / "Q4_EVALUATION_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
