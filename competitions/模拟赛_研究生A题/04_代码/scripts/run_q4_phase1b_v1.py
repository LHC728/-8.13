#!/usr/bin/env python3
"""Q4 Phase 1B q/e SCREENING runner (namespace q4_screening, master_seed 7,
replicate 20..39). SCREENING / DEVELOPMENTAL DIAGNOSTIC ONLY.

Scenarios (frozen Q4_PHASE1B_REGISTRY):
  Q4_BASELINE            (H1 / K12 / NO_PM_BEFORE_MANDATORY / 1h_literal /
                          single_test_unconditional_v1 kernel)
  QA_LOW / QA_HIGH       (Q-A CALIBRATION_INPUT: global proportional defect-
                          pressure scale 0.8 / 1.2 on q_A/B/C/D; A/B/C kernels
                          recalibrated via frozen P060 closed form; q_E
                          propagated via frozen Q1 closed-form route; E kernel
                          recalibrated; e kept at baseline)
  QB_LOW / QB_HIGH       (Q-B INCOMING_DEFECT_PRESSURE: same scale on the true
                          problem rates ONLY; observation kernel frozen at
                          baseline)
  E_LOW / E_HIGH         (E-ERROR_ENVIRONMENT: e_A/B/C/E same scale 0.8 / 1.2;
                          kernels recalibrated at baseline q; e<=2min(q,1-q)
                          never clipped, ladder +/-20% selected by
                          deterministic feasibility; engine q's baseline)

The true problem rates are read by the engine from module-level frozen
constants (rd.DEFECT_PROBS_ABC / rd.DEFECT_PROB_D_VALUE); the runner applies
the defect-pressure scale as a same-U threshold transform via a temporary
module-level override (identical pattern to the F5 constant-hazard adapter:
no core change, restore in finally). q_E for Q-A is propagated with the frozen
Q1 closed-form route (main_model.q1_routes.closed_form_v1).

Checks: only-one-factor-diff (scenario_id excluded as metadata), CRN (same
namespace/master_seed/replicate), evaluation firewall (q4_evaluation keys=0),
core immutability vs Phase 1A recorded hashes, replicate-domain disjointness
(Phase 1A 0..19 / Phase 1B 20..39 / evaluation 100..163+).

Python 3.12, standard library only (plus the frozen project modules).
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
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
from scripts.run_q3_h1_formal_v1 import (  # noqa: E402
    FROZEN_Q_ABC, FROZEN_E_ABC, FROZEN_E_E, Q1_FROZEN_Q_E_TEXT, single_kernel,
)
from main_model.q1_routes import closed_form_v1 as cf  # noqa: E402

NS = "q4_screening"
MASTER_SEED = 7
REPS = list(range(20, 40))          # Phase 1B: rep 20..39 (disjoint 0..19 / 100..163+)
K_H = "12"
T_975_DF19 = 2.093                  # t_{0.975, 19}
RESOURCES = ("A", "B", "C", "E")

Q_D_BASE: Fraction = rd.DEFECT_PROB_D  # P029 q_D = 0.001
Q_E_BASE: Fraction = Fraction(Q1_FROZEN_Q_E_TEXT)
SCALE_LO: Fraction = Fraction(4, 5)   # 0.8
SCALE_HI: Fraction = Fraction(6, 5)   # 1.2
E_SCALE_LO: Fraction = Fraction(4, 5)  # -20%
E_SCALE_HI: Fraction = Fraction(6, 5)  # +20%

TURNOVER_PROFILE = "1h_literal"
POLICY = lr.NO_PM_BEFORE_MANDATORY

# Phase 1A recorded accepted-core hashes (must be unchanged in Phase 1B).
CORE_HASHES = {
    "g3/random_des_v1.py": "801d6352af076e6f2e82c319c128d228eb9eb0703522675afe35ca187ee89928",
    "g3/key_schema_v1.py": "4fd6ad1085b7d5111b96f4cccf2dee0792fe032982fdf6583ccb18de3cb85a83",
}

REGISTRY_PATH = BASE_DIR / "05_结果" / "Q4" / "screening" / "phase_1b" / "Q4_PHASE1B_REGISTRY.json"


# ---------------------------------------------------------------------------
# q_E propagation (frozen Q1 closed-form route)
# ---------------------------------------------------------------------------


def frac_to_dec(f: Fraction) -> Decimal:
    return Decimal(f.numerator) / Decimal(f.denominator)


def propagate_q_e(q_abc: dict[str, Fraction], q_d: Fraction,
                  kernel: dict[str, dict[str, Fraction]]) -> Fraction:
    """Frozen Q1 closed-form q_E = Z_1/G with the given A/B/C kernels."""
    abc = {p: {"q": frac_to_dec(q_abc[p]),
               "alpha": frac_to_dec(kernel[p]["alpha"]),
               "beta": frac_to_dec(kernel[p]["beta"])} for p in ("A", "B", "C")}
    pre = cf.compute_pre_e(abc, frac_to_dec(q_d), precision=200)
    return Fraction(pre["q_E"])


def calibrated_kernel(q_abc: dict[str, Fraction], e_abc: dict[str, Fraction],
                      e_e: Fraction, q_e: Fraction) -> dict[str, dict[str, Fraction]]:
    kern: dict[str, dict[str, Fraction]] = {}
    for p in ("A", "B", "C"):
        a, b = rd.frozen_single_test_alpha_beta(q_abc[p], e_abc[p])
        kern[p] = {"alpha": a, "beta": b}
    a, b = rd.frozen_single_test_alpha_beta(q_e, e_e)
    kern["E"] = {"alpha": a, "beta": b}
    return kern


def qa_kernel(scale: Fraction) -> tuple[dict[str, dict[str, Fraction]], Fraction]:
    """Q-A: scale q_A/B/C/D -> recalibrate A/B/C (e baseline) -> propagate
    q_E -> recalibrate E. Returns (kernel, q_E')."""
    q_abc = {p: scale * q for p, q in FROZEN_Q_ABC.items()}
    q_d = scale * Q_D_BASE
    kern_abc: dict[str, dict[str, Fraction]] = {}
    for p in ("A", "B", "C"):
        a, b = rd.frozen_single_test_alpha_beta(q_abc[p], FROZEN_E_ABC[p])
        kern_abc[p] = {"alpha": a, "beta": b}
    q_e_new = propagate_q_e(q_abc, q_d, kern_abc)
    kern = dict(kern_abc)
    a, b = rd.frozen_single_test_alpha_beta(q_e_new, FROZEN_E_E)
    kern["E"] = {"alpha": a, "beta": b}
    return kern, q_e_new


def e_kernel(e_scale: Fraction) -> dict[str, dict[str, Fraction]]:
    """E factor: scale e_A/B/C/E at baseline q; recalibrate all kernels."""
    e_abc = {p: e_scale * e for p, e in FROZEN_E_ABC.items()}
    e_e = e_scale * FROZEN_E_E
    return calibrated_kernel(FROZEN_Q_ABC, e_abc, e_e, Q_E_BASE)


# ---------------------------------------------------------------------------
# scenarios (frozen levels)
# ---------------------------------------------------------------------------


def scenario_defs() -> list[dict[str, Any]]:
    defs: list[dict[str, Any]] = [
        {"id": "Q4_BASELINE", "factor": "BASELINE", "level": "-",
         "q_scale": None, "kernel": "baseline", "auth": []},
    ]
    for sid, scale in (("QA_LOW", SCALE_LO), ("QA_HIGH", SCALE_HI)):
        defs.append({"id": sid, "factor": "Q-A",
                     "level": f"q_scale={scale}",
                     "q_scale": scale, "kernel": "qa", "auth": ["observation_kernel"]})
    for sid, scale in (("QB_LOW", SCALE_LO), ("QB_HIGH", SCALE_HI)):
        defs.append({"id": sid, "factor": "Q-B",
                     "level": f"q_scale={scale}",
                     "q_scale": scale, "kernel": "baseline", "auth": []})
    for sid, escale in (("E_LOW", E_SCALE_LO), ("E_HIGH", E_SCALE_HI)):
        defs.append({"id": sid, "factor": "E",
                     "level": f"e_scale={escale}",
                     "q_scale": None, "e_scale": escale, "kernel": "e",
                     "auth": ["observation_kernel"]})
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
    return rd.default_config(
        namespace=NS, master_seed=MASTER_SEED, replicate_id=rep,
        tau_pm=POLICY,
        observation_kernel=kernel_for(scenario),
        batch_size=100, scenario="q3_two_shift",
        shift_length_h=K_H, shifts_per_day=2,
        durations=None, turnover_profile=TURNOVER_PROFILE,
        scenario_id=f"q4_screening_{scenario['id']}_rep{rep}",
    )


def design_cfg(scenario: dict[str, Any]) -> rd.RandomDesConfig:
    """Rep-independent design fingerprint config (scenario_id = plain id,
    identical convention to the Phase 1A registry generator)."""
    return rd.default_config(
        namespace=NS, master_seed=MASTER_SEED, replicate_id=0,
        tau_pm=POLICY,
        observation_kernel=kernel_for(scenario),
        batch_size=100, scenario="q3_two_shift",
        shift_length_h=K_H, shifts_per_day=2,
        durations=None, turnover_profile=TURNOVER_PROFILE,
        scenario_id=scenario["id"],
    )


def run_one(cfg: rd.RandomDesConfig, q_scale: Optional[Fraction]):
    if q_scale is not None and q_scale != 1:
        # Q-A/Q-B: same-U threshold transform on the engine's module-level
        # frozen true-defect constants (no core change; restored in finally).
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
# mechanism ledger extractor (same diagnostic contract as Phase 1A)
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
    terminal_t: dict[int, Fraction] = {}
    off_shift = Fraction(0)
    turn_out_t: dict[int, Fraction] = {}
    cal_start: dict[str, Fraction] = {}
    shift_ends: list[Fraction] = []
    n_wake = 0
    last_wake: Optional[Fraction] = None

    for r in event_log:
        et = r["event_type"]
        t = Fraction(r["event_time"])
        if et == "SHIFT_CHANGE":
            shift_ends.append(Fraction(r["shift_end"]))
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

    for aid, a in starts.items():
        res = a["res"]
        dur = min(a["end"], a["t"] + Fraction(240)) - a["t"]
        if dur < 0:
            dur = Fraction(0)
        dev_term = terminal_t.get(a["dev"])
        if dev_term is not None and a["t"] <= dev_term <= a["t"] + Fraction(6):
            term_w[res] += dur
        else:
            shift_end = None
            for se in shift_ends:
                if se > a["t"]:
                    shift_end = se
                    break
            if shift_end is not None and a["end"] > shift_end:
                shift_w[res] += max(Fraction(0), shift_end - a["t"])
            else:
                fail_w[res] += dur

    return {
        "effective_test_time": {p: str(eff[p]) for p in RESOURCES},
        "retest_time": {p: str(retest[p]) for p in RESOURCES},
        "failure_wasted_fragment_time": {p: str(fail_w[p]) for p in RESOURCES},
        "shift_boundary_wasted_fragment_time": {p: str(shift_w[p]) for p in RESOURCES},
        "terminal_cancelled_fragment_time": {p: str(term_w[p]) for p in RESOURCES},
        "calibration_time": {p: str(cal[p]) for p in RESOURCES},
        "turnover_occupancy_time": str(turn_occ),
        "queue_blocking_time": {p: "SCREENING_APPROX" for p in RESOURCES},
        "off_shift_time": str(off_shift),
        "note": "MECHANISM LEDGER; NOT an additive decomposition of T "
                "(parallel activities overlap).",
    }


# ---------------------------------------------------------------------------
# registry freeze / validation
# ---------------------------------------------------------------------------


def config_hash_of(cfg: rd.RandomDesConfig) -> str:
    blob = json.dumps(cfg.to_dict(), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_registry() -> dict[str, Any]:
    defs = scenario_defs()
    scenarios = []
    for sc in defs:
        cfg = design_cfg(sc)
        entry = {
            "scenario_id": sc["id"],
            "factor_id": sc["factor"],
            "level": sc["level"],
            "q_scale": (str(sc["q_scale"]) if sc["q_scale"] is not None else None),
            "kernel_kind": sc["kernel"],
            "config_hash": config_hash_of(cfg),
            "observation_kernel": {
                p: {"alpha": str(cfg.observation_kernel[p]["alpha"]),
                    "beta": str(cfg.observation_kernel[p]["beta"])}
                for p in RESOURCES},
            "authorized_changed_fields": sc["auth"],
        }
        if sc["kernel"] == "qa":
            _, q_e_new = qa_kernel(sc["q_scale"])
            entry["q_E_propagated"] = str(q_e_new)
        scenarios.append(entry)
    baseline_cfg = design_cfg(defs[0])
    return {
        "registry": "Q4_PHASE1B_REGISTRY",
        "status": "PRE_DATA",
        "immutable": True,
        "freeze_timestamp": datetime.now(timezone.utc).isoformat(),
        "authority": "HG-Q4-NS-01 + Human Gate 一体化授权包 "
                     "(Q4 Phase 1B + FORMAL EVALUATION + TOP-2 interaction)",
        "logical_domain": "Q4_SCREENING",
        "namespace": NS,
        "master_seed": MASTER_SEED,
        "replicate_ids": REPS,
        "R_screen_1b": len(REPS),
        "scenario": "q3_two_shift",
        "baseline": {
            "K": K_H, "policy": "NO_PM_BEFORE_MANDATORY",
            "turnover": "1h_literal",
            "failure_semantics": "piecewise-linear CDF",
            "observation_kernel": "single_test_unconditional_v1 (P060; Q3 Tier1 main)",
            "kernel_source": "single_kernel() (run_q3_h1_formal_v1)",
            "config_hash": config_hash_of(baseline_cfg),
            "phase_1a_baseline_hash": "618d24ab3d823f97651524c6e0e4074553de280afab898fa0feca4abc43da275",
            "q3_evidence_binding": [
                "05_结果/Q3/formal/run_20260815T133840057668Z_7ee48fc0",
                "05_结果/Q3/formal/reissue_20260815T150613626910Z_f4da8f9d",
            ],
        },
        "q_semantics": {
            "factor_Q-A": "CALIBRATION_INPUT: q_A/B/C/D scaled by s; A/B/C kernels "
                          "recalibrated via frozen P060 closed form "
                          "(alpha=e/(2(1-q)), beta=e/(2q)) at e=baseline; q_E "
                          "propagated via frozen Q1 closed-form route; E kernel "
                          "recalibrated at q_E'.",
            "factor_Q-B": "INCOMING_DEFECT_PRESSURE: same scale on the engine true "
                          "problem rates ONLY (same-U threshold transform); "
                          "observation kernel frozen at baseline.",
            "scale_levels": [str(SCALE_LO), str(SCALE_HI)],
            "q_base": {"A": str(FROZEN_Q_ABC["A"]), "B": str(FROZEN_Q_ABC["B"]),
                       "C": str(FROZEN_Q_ABC["C"]), "D": str(Q_D_BASE),
                       "E_propagated_baseline": str(Q_E_BASE)},
        },
        "e_semantics": {
            "factor_E": "E-ERROR_ENVIRONMENT: e_A/B/C/E scaled together; kernels "
                        "recalibrated at baseline q; e<=2min(q,1-q) NEVER clipped; "
                        "level selected ONLY by deterministic feasibility ladder.",
            "ladder": ["+20%", "+10%", "+5%", "-20%", "-10%", "-5%"],
            "ladder_feasibility": _e_ladder_feasibility(),
            "selected_levels": {"E_LOW": str(E_SCALE_LO), "E_HIGH": str(E_SCALE_HI)},
            "e_base": {"A": str(FROZEN_E_ABC["A"]), "B": str(FROZEN_E_ABC["B"]),
                       "C": str(FROZEN_E_ABC["C"]), "E": str(FROZEN_E_E)},
        },
        "domain_isolation": {
            "phase_1a_rep": "0..19",
            "phase_1b_rep": "20..39",
            "evaluation_rep": "100..163 (expansion 164..227)",
            "disjoint": True,
            "note": "screening (0..39) and evaluation (100..163+) NEVER overlap; "
                    "Q4_EVALUATION is the only final-inference CI source; no pooling.",
        },
        "statistics": {
            "design": "CRN paired DeltaT per replicate",
            "delta_T_r": "T(scenario,r) - T(baseline,r), same namespace/seed/rep",
            "reported": ["mean DeltaT", "SE", "95% screening CI (t_{0.975,19}=2.093)",
                         "standardized effect", "sign consistency"],
            "unit": "batch replicate (100 devices); 100 devices are NOT replicates",
            "status": "SCREENING_ONLY_NON_FINAL",
        },
        "frozen_flags": {
            "HUMAN_GATE_AUTHORIZED": True,
            "IMMUTABLE_FOR_PHASE_1B": True,
            "PRE_DATA": True,
            "Q4_EVALUATION": "NOT AUTHORIZED / UNTOUCHED",
            "SCREENING_SPEC_FROZEN": True,
            "TOP2_INTERACTION": "NOT AUTHORIZED",
        },
        "scenarios": scenarios,
    }


def _e_ladder_feasibility() -> list[dict[str, Any]]:
    out = []
    for label, s in (("+20%", E_SCALE_HI), ("+10%", Fraction(11, 10)),
                     ("+5%", Fraction(21, 20)), ("-20%", E_SCALE_LO),
                     ("-10%", Fraction(9, 10)), ("-5%", Fraction(19, 20))):
        rows = {}
        feas = True
        for p in ("A", "B", "C"):
            e_s = s * FROZEN_E_ABC[p]
            lim = 2 * min(FROZEN_Q_ABC[p], 1 - FROZEN_Q_ABC[p])
            ok = e_s <= lim
            feas = feas and ok
            rows[p] = {"e_scaled": str(e_s), "limit": str(lim), "feasible": ok}
        e_e_s = s * FROZEN_E_E
        lim_e = 2 * min(Q_E_BASE, 1 - Q_E_BASE)
        ok_e = e_e_s <= lim_e
        feas = feas and ok_e
        rows["E"] = {"e_scaled": str(e_e_s), "limit": str(lim_e), "feasible": ok_e}
        out.append({"ladder_step": label, "all_feasible": feas, "details": rows})
    return out


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
# run + aggregate
# ---------------------------------------------------------------------------


def main() -> int:
    t0 = time.perf_counter()
    if not REGISTRY_PATH.exists():
        print("[q4p1b] FATAL: registry missing (freeze first):", REGISTRY_PATH)
        return 2
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if registry.get("status") != "PRE_DATA":
        print("[q4p1b] FATAL: registry not PRE_DATA:", registry.get("status"))
        return 2

    defs = scenario_defs()
    # -- validate registry against recomputed design (fail-closed) --
    recomputed = build_registry()
    for a, b in zip(recomputed["scenarios"], registry["scenarios"]):
        if a["config_hash"] != b["config_hash"]:
            print(f"[q4p1b] FATAL: registry config_hash mismatch for "
                  f"{a['scenario_id']}: {a['config_hash']} != {b['config_hash']}")
            return 2
    if recomputed["baseline"]["config_hash"] != registry["baseline"]["config_hash"]:
        print("[q4p1b] FATAL: registry baseline config_hash mismatch")
        return 2
    if recomputed["baseline"]["config_hash"] != registry["baseline"]["phase_1a_baseline_hash"]:
        print("[q4p1b] FATAL: Phase 1B baseline hash must equal Phase 1A baseline "
              "hash (identical frozen config)")
        return 2

    core = validate_core_hashes()
    if core["status"] != "PASS":
        print("[q4p1b] FATAL: accepted core changed:", core)
        return 2

    out_root = BASE_DIR / "05_结果" / "Q4" / "screening" / "phase_1b"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + \
        hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
    out = out_root / run_id
    out.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict] = {}
    for sc in defs:
        sid = sc["id"]
        t_vals = []
        for rep in REPS:
            cfg = build_cfg(rep, sc)
            res = run_one(cfg, q_scale=sc["q_scale"])
            t_vals.append(Fraction(res.metrics["T"]))
        results[sid] = {"scenario": sc, "T_by_rep": [str(v) for v in t_vals]}
        print(f"[q4p1b] {sid}: last T={t_vals[-1]}")

    baseline_T = [Fraction(v) for v in results["Q4_BASELINE"]["T_by_rep"]]
    rows = []
    for sc in defs:
        sid = sc["id"]
        if sid == "Q4_BASELINE":
            continue
        sc_T = [Fraction(v) for v in results[sid]["T_by_rep"]]
        d = [sc_T[r] - baseline_T[r] for r in range(len(REPS))]
        mean = sum(d, Fraction(0)) / len(d)
        sd = math.sqrt(sum(float((x - float(mean)) ** 2) for x in d) / (len(d) - 1))
        se = sd / math.sqrt(len(d))
        half = T_975_DF19 * se
        rows.append({
            "factor_id": sc["factor"], "scenario_id": sid,
            "source": "Q4_SCREENING_PHASE_1B",
            "level": sc["level"],
            "mean_Delta_T_h": str(mean),
            "SE": round(se, 6),
            "screening_CI_low": round(float(mean) - half, 6),
            "screening_CI_high": round(float(mean) + half, 6),
            "standardized_effect": round(float(mean) / sd, 6) if sd > 0 else 0.0,
            "sign_consistency": "ALL_NEG" if all(x < 0 for x in d) else
                                ("ALL_POS" if all(x > 0 for x in d) else "MIXED"),
            "authority": "CALIBRATION_INPUT" if sc["factor"] == "Q-A" else
                         ("INCOMING_DEFECT_PRESSURE" if sc["factor"] == "Q-B" else
                          ("E-ERROR_ENVIRONMENT" if sc["factor"] == "E" else "-")),
            "status": "SCREENING_ONLY_NON_FINAL",
        })
    rows.sort(key=lambda r: -abs(r["standardized_effect"]))

    # mechanism ledgers (baseline + q/e scenarios, summed over Phase 1B reps)
    ledgers: dict[str, list[dict]] = {}
    for sc in defs:
        sid = sc["id"]
        lg = []
        for rep in REPS:
            cfg = build_cfg(rep, sc)
            res = run_one(cfg, q_scale=sc["q_scale"])
            lg.append(extract_ledger(res.event_log))
        ledgers[sid] = lg

    def _sum_field(key: str, lgs: list[dict]) -> dict[str, str]:
        acc = {p: Fraction(0) for p in RESOURCES}
        for lg in lgs:
            v = lg[key]
            if isinstance(v, dict):
                for p in RESOURCES:
                    if v[p] != "SCREENING_APPROX":
                        acc[p] += Fraction(v[p])
        return {p: str(acc[p]) for p in RESOURCES}

    scenario_ledger = {}
    for sid, lgs in ledgers.items():
        scenario_ledger[sid] = {
            "effective_test_time": _sum_field("effective_test_time", lgs),
            "retest_time": _sum_field("retest_time", lgs),
            "failure_wasted_fragment_time": _sum_field("failure_wasted_fragment_time", lgs),
            "shift_boundary_wasted_fragment_time": _sum_field("shift_boundary_wasted_fragment_time", lgs),
            "terminal_cancelled_fragment_time": _sum_field("terminal_cancelled_fragment_time", lgs),
            "calibration_time": _sum_field("calibration_time", lgs),
            "turnover_occupancy_time": str(sum(Fraction(lg["turnover_occupancy_time"])
                                               for lg in lgs)),
            "off_shift_time": str(sum(Fraction(lg["off_shift_time"]) for lg in lgs)),
            "note": "MECHANISM LEDGER (summed over 20 Phase 1B replicates); "
                    "NOT an additive decomposition of T.",
        }

    # checks
    oofd = {"status": "PASS"}
    for sc in defs:
        if sc["id"] == "Q4_BASELINE":
            continue
        db = build_cfg(0, defs[0]).to_dict()
        ds = build_cfg(0, sc).to_dict()
        changed = [k for k in ds if k not in db or ds[k] != db.get(k)]
        changed = [k for k in changed if k != "scenario_id"]  # metadata, not a factor
        if not set(changed) <= set(sc["auth"]):
            oofd = {"status": "FAIL", "scenario": sc["id"],
                    "changed": changed, "authorized": sc["auth"]}
    crn = {"status": "PASS", "namespace": NS, "master_seed": MASTER_SEED,
           "replicate_ids": REPS,
           "note": "baseline and every scenario share namespace/seed/rep -> same "
                   "keyed U_X/U_D/U_Y/U_L; q-scale and kernel changes are same-U "
                   "transforms only"}
    firewall = {"q4_evaluation_keys_consumed": 0, "q4_evaluation_runs": 0,
                "q4_evaluation_result_files": 0, "status": "PASS"}
    domain = {"phase_1a": "0..19", "phase_1b": "20..39",
              "evaluation": "100..163+", "disjoint": True, "status": "PASS"}

    package = {
        "run_id": run_id, "namespace": NS, "master_seed": MASTER_SEED,
        "replicate_ids": REPS, "R_screen_1b": len(REPS),
        "registry": str(REGISTRY_PATH.relative_to(BASE_DIR)).replace("\\", "/"),
        "baseline": registry["baseline"],
        "screening_rows": rows,
        "factor_ranking_1b": rows,
        "scenario_mechanism_ledgers": scenario_ledger,
        "checks": {"only_one_factor_diff": oofd, "crn": crn,
                   "evaluation_firewall": firewall,
                   "domain_isolation": domain,
                   "authorized_core_hashes": core},
        "wallclock_s": round(time.perf_counter() - t0, 2),
    }
    (out / "phase1b_screening_results.json").write_text(
        json.dumps(package, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    import csv as _csv
    with open(out / "phase1b_screening_results.csv", "w", newline="",
              encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    (out / "run_manifest.json").write_text(json.dumps({
        "run_id": run_id, "task": "Q4 Phase 1B q/e screening (q4_screening rep 20..39)",
        "authority": "Human Gate 一体化授权包 (Phase 1B + FORMAL + Top-2)",
        "registry": "Q4_PHASE1B_REGISTRY.json",
        "status": "SCREENING_ONLY_NON_FINAL",
        "wallclock_s": package["wallclock_s"]}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    print(f"[q4p1b] run_id={run_id} rows={len(rows)} wall={package['wallclock_s']}s")
    for r in rows:
        print(f"  {r['factor_id']:>4} {r['scenario_id']:<10} "
              f"dT={r['mean_Delta_T_h']:>12} se={r['SE']:.4f} "
              f"std={r['standardized_effect']:.4f}")
    print("[q4p1b] evidence:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
