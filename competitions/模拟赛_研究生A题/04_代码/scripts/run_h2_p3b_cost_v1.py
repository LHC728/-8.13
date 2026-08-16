#!/usr/bin/env python3
"""Q3-H2-P3-B cost calibration: h2_tuning replicate 0..4, K=10.5 (SPEC
1.2 / 18 / 19 / 20 / 21 / 22, frozen).

Measures, on the FIRST 5 tuning batches (namespace=h2_tuning,
master_seed=6, replicate_ids 0..4, K=10.5):
  * base_r  : the batch's engine-only wallclock (no rollout);
  * c_r     : the single-rollout wallclock (samples);
  * base    : frozen aggregate of the 5 base values (median; all 5 batches
    reported; per-batch worst disclosed) -- SPEC 19: if authority has not
    specified the aggregate, report all 5 bases and use the MEDIAN base
    conservatively for the unified calculation, disclosing the per-batch
    worst estimate.

Candidate estimates (frozen grid ONLY): (4,8)->96, (8,6)->144, (8,8)->192
  w_p = base + (C_eval * 3 * M) * c_r
Selection (frozen): feasible iff w_p <= 90 s; among feasible pick MAX M,
then larger C_eval; none feasible -> H2_BUDGET_INFEASIBLE (pre-registered
DELETE trigger).  NEVER chosen by Q values / T improvement / action results.

Base and rollout wallclocks EXCLUDE C06/C17/bootstrap/statistical
postprocessing (engine-only).  New formal/holdout worlds: none.

Python 3.12, standard library only.
"""
from __future__ import annotations

import statistics
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

_BASE_DIR = Path(__file__).resolve().parents[2]
_CODE_DIR = _BASE_DIR / "04_代码"
_MAIN_MODEL = _CODE_DIR / "main_model"
for _entry in (str(_MAIN_MODEL), str(_CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from g3 import key_schema_v1 as ks  # noqa: E402
from g3 import random_des_v1 as rd  # noqa: E402

NS = ks.NAMESPACE_H2_TUNING          # "h2_tuning" (calibration selection domain)
# P3-B-E1 Human Gate disposition (2026-08-16): base_r MAY use
# development_unit ONLY as a PERFORMANCE_ONLY_BASE_SURROGATE.  The
# accepted H1 engine structurally rejects the h2_tuning namespace (P0/C16
# firewall: H2 namespaces are reserved for the H2 post streams), so the
# engine-only base runtime is measured on the identical world structure
# (batch 100, K=10.5 two shifts, seed 6, rep 0..4) under development_unit.
# This is NOT h2_tuning physical-world evidence; it measures runtime only,
# reads no physical results, and never participates in benefit/action
# selection.  The exception is LIMITED to the §1.2 cost runtime; it NEVER
# authorizes development_unit for action stability / cross-K transfer /
# h2_holdout / C25 / H2 benefit statistics.
BASE_NS = ks.NAMESPACE_DEVELOPMENT_UNIT
BASE_RUNTIME_ROLE = "PERFORMANCE_ONLY_BASE_SURROGATE"
MASTER_SEED = 6
REPLICATES = (0, 1, 2, 3, 4)
K = Fraction(21, 2)                  # 10.5 h
BATCH_SIZE = 100
CANDIDATES: tuple[tuple[int, int], ...] = ((4, 8), (8, 6), (8, 8))
WORST_ROLLOUTS = {c: c[1] * 3 * c[0] for c in CANDIDATES}  # 96/144/192
WP_BUDGET_S = 90.0


def _tuning_config(rep: int):
    from g3 import lifetime_regeneration_v1 as lr
    from main_model.h2.frozen_params_v1 import observation_kernel
    return rd.default_config(
        namespace=BASE_NS, master_seed=MASTER_SEED, replicate_id=rep,
        tau_pm=lr.NO_PM_BEFORE_MANDATORY,
        observation_kernel=observation_kernel(),
        batch_size=BATCH_SIZE, scenario="q3_two_shift",
        shift_length_h="21/2", shifts_per_day=2)


def measure_base(rep: int, samples: int = 1) -> float:
    """Engine-only wallclock of one h2_tuning batch (no rollout, no C06/C17/
    bootstrap)."""
    cfg = _tuning_config(rep)
    times: list[float] = []
    for _ in range(samples):
        t0 = time.perf_counter()
        rd.run_random_des(cfg)
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


def _single_rollout_wallclock(rep: int, n: int = 3) -> float:
    """Wallclock of ONE posterior-world rollout (from a decision point in
    a batch of batch_size=100; deterministic small world).  Uses the P3
    continuation engine; excludes C06/C17/bootstrap.

    SECOND REQUALIFICATION (world_m): the measured c_r now includes the
    per-m posterior-world REBUILD (rebuild_continuation_world from the
    m-th h2_rollout post-key bundle) plus the engine run -- exactly the
    per-m cost the repaired policy evaluator pays for each m."""
    from main_model.h2 import observable_state_v1 as obs
    from main_model.h2 import posterior_state_v1 as ps
    from main_model.h2 import continuation_v1 as cont
    from main_model.h2_rollout import rollout_engine_v1 as re1
    from main_model.h2_rollout import post_keys_v1 as pk

    cfg = _tuning_config(rep)
    ref = rd.RandomDesEngine(cfg)
    refres = ref.run()
    # decision time t=0 prefix
    log0 = [r for r in refres.event_log
            if Fraction(r["event_time"]) <= Fraction(0)]
    st = obs.project_log_prefix(log0, Fraction(0), batch_size=BATCH_SIZE)
    post = ps.PosteriorState.from_observable(st)
    gen = {r: 1 for r in ("A", "B", "C", "E")}
    all_devices = tuple(range(1, BATCH_SIZE + 1))  # future devices included
    res_tuple = ("A", "B", "C", "E")
    cfg_roll = re1.RolloutConfig(
        batch_size=BATCH_SIZE, shift_length_h=K, shifts_per_day=2,
        scenario="q3_two_shift", tau_pm=re1.NO_PM_BEFORE_MANDATORY)
    times: list[float] = []
    for m in range(n):
        k = pk.rollout_post_keys(MASTER_SEED, rep, 0, m,
                                 all_devices, res_tuple, gen)
        t0 = time.perf_counter()
        world = cont.rebuild_continuation_world(
            st, post,
            u_x_by_device=k.u_x_by_device,
            u_d_by_device=k.u_d_by_device,
            u_l_by_resource=k.u_l_by_resource)
        prov = re1.PostKeyProvider(
            u_x_by_device=k.u_x_by_device,
            u_x_subsystem_lookup=(
                lambda d, s, _k=k: _k.u_x_subsystem_by_device[d][s]),
            u_d_by_device=k.u_d_by_device,
            u_l_by_resource=k.u_l_by_resource,
            u_y_lookup=k.u_y_lookup, u_l_lookup=k.u_l_lookup)
        eng = re1.RolloutEngine(st, post, world, prov, cfg_roll,
                                first_action=re1.A_H1_NOOP,
                                log_prefix=refres.event_log)
        eng.run()
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


def run_cost_measurement(base_samples: int = 1,
                         rollout_samples: int = 3) -> dict[str, Any]:
    """Full frozen cost measurement + (M*, C_eval*) selection."""
    base_rows: list[dict[str, Any]] = []
    rollout_rows: list[dict[str, Any]] = []
    for rep in REPLICATES:
        base_r = measure_base(rep, base_samples)
        c_r = _single_rollout_wallclock(rep, rollout_samples)
        base_rows.append({"replicate_id": rep, "base_r_s": round(base_r, 6),
                          "c_r_s": round(c_r, 6)})
        rollout_rows.append({"replicate_id": rep, "c_r_s": round(c_r, 6)})
    bases = [r["base_r_s"] for r in base_rows]
    c_rs = [r["c_r_s"] for r in rollout_rows]
    base_median = statistics.median(bases)
    base_worst = max(bases)
    c_r_median = statistics.median(c_rs)
    c_r_worst = max(c_rs)
    # frozen conservative unified estimate: median base + median c_r; also
    # disclose the per-batch worst estimate
    estimates: dict[str, dict[str, Any]] = {}
    for (m, c) in CANDIDATES:
        worst_rollouts = WORST_ROLLOUTS[(m, c)]
        w_p_median = base_median + worst_rollouts * c_r_median
        w_p_worst = base_worst + worst_rollouts * c_r_worst
        estimates[f"({m},{c})"] = {
            "M": m, "C_eval": c, "worst_rollouts": worst_rollouts,
            "w_p_median_s": round(w_p_median, 4),
            "w_p_worst_s": round(w_p_worst, 4),
            "feasible": w_p_median <= WP_BUDGET_S,
            "w_p_using_worst": round(w_p_worst, 4)}
    feasible = [key for key, v in estimates.items() if v["feasible"]]
    if feasible:
        # pick max M, then larger C_eval
        def _key(k):
            m, c = estimates[k]["M"], estimates[k]["C_eval"]
            return (m, c)
        best_key = max(feasible, key=_key)
        est = estimates[best_key]
        m_star, c_eval_star = est["M"], est["C_eval"]
        w_cap = (c_eval_star + 1) // 2
        p_cap = c_eval_star // 2
        selected = {"M": m_star, "C_eval": c_eval_star, "W_cap": w_cap,
                    "P_cap": p_cap, "w_p_median_s": est["w_p_median_s"]}
        status = "COMPLETED"
    else:
        selected = None
        status = "H2_BUDGET_INFEASIBLE"
    return {
        "check": "COST_CALIBRATION",
        "status": "PASS" if selected is not None else "FAIL",
        "calibration_selection_domain": {
            "namespace": NS, "master_seed": MASTER_SEED,
            "replicate_ids": list(REPLICATES), "K": str(K),
            "purpose": "M/C_eval cost calibration only"},
        "base_runtime_namespace": BASE_NS,
        "base_runtime_role": BASE_RUNTIME_ROLE,
        "base_runtime_note": (
            "development_unit used ONLY as a performance surrogate for the "
            "engine-only base runtime (the accepted H1 engine structurally "
            "rejects h2_tuning per P0/C16); identical world structure "
            "(batch 100, K=10.5 two shifts, seed 6, rep 0..4); NOT "
            "h2_tuning physical-world evidence; never used for benefit/"
            "action selection; exception limited to the §1.2 cost runtime"),
        "batch_size": BATCH_SIZE,
        "base_rows": base_rows, "rollout_rows": rollout_rows,
        "base_median_s": round(base_median, 6),
        "base_worst_s": round(base_worst, 6),
        "c_r_median_s": round(c_r_median, 6),
        "c_r_worst_s": round(c_r_worst, 6),
        "estimates": estimates,
        "wp_budget_s": WP_BUDGET_S,
        "selection_rule": "feasible w_p<=90s; max M; then larger C_eval",
        "selected": selected,
        "budget_infeasible": status == "H2_BUDGET_INFEASIBLE",
        "pre_registered_delete_trigger": (
            "H2_BUDGET_INFEASIBLE" if selected is None else None),
    }
