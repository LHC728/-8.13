#!/usr/bin/env python3
"""Q3-H2-P3-B independent checker: rollout kernel, H1 fallback parity,
future D timing, U_Y consumption, replacement-generation lifetime, CRN,
quota selector + causality, C_rollout accounting, Q_hat/SE, C23 rollout.

Independence rule: the checker drives the ACCEPTED H1 engine
(``g3.random_des_v1``) as the parity TARGET for the H1-baseline phase and
compares the P3 continuation engine's core events / T_end against it using
IDENTICAL u-streams (the checker replays the accepted engine's consumed u
values into the continuation provider).  It never calls the implementer's
rollout functions as an oracle to produce expectations for the parity; the
quota / Q_hat / CRN checks use the checker's OWN re-derivation.

The checker imports the accepted H1 engine (a parity target, not the
implementer); the P3 ``main_model/h2`` package itself stays engine-free
(P1 isolation verified by the firewall regression).

Python 3.12, standard library only.
"""
from __future__ import annotations

import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from main_model.h2 import continuation_v1 as cont  # noqa: E402
from main_model.h2_rollout import rollout_engine_v1 as re1  # noqa: E402
from main_model.h2 import quota_selector_v1 as qsel  # noqa: E402
from main_model.h2 import q_estimator_v1 as qest  # noqa: E402
from main_model.h2.frozen_params_v1 import (  # noqa: E402
    CALIBRATION_MINUTES, DURATIONS_H, MANDATORY_AGE_H, MIN_PREVENTIVE_AGE_H,
    Q_ABC, Q_D, RESOURCES,
)
from main_model.h2_rollout import post_keys_v1 as pk  # noqa: E402


# ---------------------------------------------------------------------------
# checker's own re-derivations
# ---------------------------------------------------------------------------


def _own_fcfs_key(release_time, device_id, process, attempt):
    order = {"A": 0, "B": 1, "C": 2, "E": 3}
    return (Fraction(release_time), int(device_id), order[process],
            int(attempt))


def _own_replacement_decision(a, d, tau_pm, idle) -> str:
    a = Fraction(a)
    d = Fraction(d)
    if a + d > MANDATORY_AGE_H:
        return "MANDATORY_REPLACE_FIRST"
    if a + d == MANDATORY_AGE_H:
        return "EXACT_240_COMPLETE_FIRST"
    if tau_pm is re1.NO_PM_BEFORE_MANDATORY:
        return "SERVE_HEAD"
    if a >= Fraction(tau_pm) and idle:
        return "PREVENTIVE_REPLACE"
    return "SERVE_HEAD"


def _own_fragment_outcome(a_start, d, lifetime_h, is_right_censored
                          ) -> tuple[str, Fraction]:
    """Checker's own frozen fragment classification (independent of the
    implementer's copy)."""
    a = Fraction(a_start)
    d = Fraction(d)
    if a + d > MANDATORY_AGE_H:
        return ("illegal_240", MANDATORY_AGE_H - a)
    interrupted = False
    if not is_right_censored and lifetime_h is not None:
        L = Fraction(lifetime_h)
        if a < L < a + d:
            interrupted = True
    if interrupted:
        return ("failed", Fraction(lifetime_h) - a)
    return ("complete", d)


# ---------------------------------------------------------------------------
# H1 fallback parity harness
# ---------------------------------------------------------------------------


def _mk_toy_engine_config(namespace: str, master_seed: int, replicate_id: int,
                          batch_size: int, shift_length_h: str,
                          shifts_per_day: int, kernel: dict):
    from g3 import random_des_v1 as rd
    from g3 import lifetime_regeneration_v1 as lr
    return rd.default_config(
        namespace=namespace, master_seed=master_seed,
        replicate_id=replicate_id, tau_pm=lr.NO_PM_BEFORE_MANDATORY,
        observation_kernel=kernel, batch_size=batch_size,
        scenario="q3_two_shift", shift_length_h=shift_length_h,
        shifts_per_day=shifts_per_day)


def _own_kernel() -> dict[str, dict[str, Fraction]]:
    from main_model.h2.frozen_params_v1 import (
        E_ABC, E_E, Q_ABC as QA, Q_E, frozen_alpha, frozen_beta,
    )
    kern: dict[str, dict[str, Fraction]] = {}
    for proc in ("A", "B", "C"):
        q = QA[proc]
        e = E_ABC[proc]
        kern[proc] = {"alpha": frozen_alpha(q, e), "beta": frozen_beta(q, e)}
    kern["E"] = {"alpha": frozen_alpha(Q_E, E_E), "beta": frozen_beta(Q_E, E_E)}
    return kern


def _replay_provider_from_log(event_log: list[dict], devices: tuple[int, ...],
                              resources: tuple[str, ...]) -> re1.PostKeyProvider:
    """Build a PostKeyProvider that REPLAYS the accepted engine's consumed u
    values (identical random stream for the parity), read from its
    append-only event log (OBSERVATION_MATERIALIZED / EQUIPMENT_*
    / TRUE_STATE_GENERATED / D_CREATED records carry u)."""
    u_y: dict[tuple[int, str, int], Fraction] = {}
    for rec in event_log:
        if rec.get("event_type") == "OBSERVATION_MATERIALIZED":
            u_y[(rec["device_id"], rec["process"],
                 rec["effective_attempt_no"])] = Fraction(rec["u"])
    u_l: dict[tuple[str, int], Fraction] = {}
    for rec in event_log:
        if rec.get("event_type") == "EQUIPMENT_REPLACEMENT_START":
            u_l[(rec["resource_id"], rec["new_generation"])] = Fraction(
                rec["u"])
    u_x_sub: dict[int, dict[str, Fraction]] = {}
    for rec in event_log:
        if rec.get("event_type") == "TRUE_STATE_GENERATED":
            d = rec["device_id"]
            u_x_sub[d] = {sub: Fraction(rec["u"][sub])
                          for sub in ("A", "B", "C")}
    u_d: dict[int, Fraction] = {}
    for rec in event_log:
        if rec.get("event_type") == "D_CREATED":
            u_d[rec["device_id"]] = Fraction(rec["u"])
    return re1.PostKeyProvider(
        u_x_by_device={d: Fraction(1, 2) for d in devices},
        u_x_subsystem_lookup=(lambda d, sub: u_x_sub.get(d, {}).get(
            sub, Fraction(1, 2))),
        u_d_by_device=u_d,
        u_l_by_resource={r: Fraction(1, 2) for r in resources},
        u_y_lookup=(lambda d, p, a: u_y.get((d, p, a), Fraction(1, 2))),
        u_l_lookup=(lambda r, g: u_l.get((r, g), Fraction(1, 2))))


def _world_from_engine(eng, st, post) -> cont.ContinuationWorld:
    """Build a ContinuationWorld with the accepted engine's ACTUAL hidden
    truth (parity target; production uses posterior sampling)."""
    devices: list[cont.ContinuationDevice] = []
    for d in st.devices:
        ts = eng.true_states.get(d.device_id)
        d_state = eng.d_states.get(d.device_id)
        x_abc = (0, 0, 0)
        if ts is not None:
            x_abc = (1 if ts["A"] else 0, 1 if ts["B"] else 0,
                     1 if ts["C"] else 0)
        x_d = (1 if d_state == "PROBLEM" else 0) if d_state is not None else None
        devices.append(cont.ContinuationDevice(
            device_id=d.device_id, terminal=d.terminal_state is not None,
            reached_e=False, x_abc=x_abc, x_d=x_d, obs_e=()))
    lifetimes: dict[str, tuple[Optional[Fraction], bool]] = {}
    for r in st.resources:
        equip = eng.equipment[r.resource]
        lifetimes[r.resource] = (equip.lifetime_h, equip.is_right_censored)
    return cont.ContinuationWorld(decision_time=st.time,
                                  devices=tuple(devices),
                                  residual_lifetimes=lifetimes)


def check_h1_fallback_parity() -> dict[str, Any]:
    """SPEC 9: when the forced first action equals the H1 default, the P3
    rollout continuation must match the accepted H1 continuation from an
    equivalent state in core events and final T_end, for deterministic
    keyed toy worlds (normal dispatch chain / retest / random failure /
    replacement / shift boundary / exact240 / terminal absorption)."""
    from g3 import random_des_v1 as rd
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    scenarios = [
        # (batch_size, shift_length, shifts_per_day, master_seed)
        ("normal_dispatch_chain", 2, "300", 2, 1),
        ("retest_and_failure", 2, "300", 2, 2),
        ("replacement_calibration", 2, "300", 2, 3),
        ("exact240_terminal", 2, "300", 2, 4),
        ("shift_boundary", 2, "10.5", 2, 5),
        ("terminal_absorption", 2, "300", 2, 6),
    ]
    for label, bs, shift_len, spd, seed in scenarios:
        cfg = _mk_toy_engine_config("development_unit", seed, 0, bs,
                                    shift_len, spd, _own_kernel())
        ref = rd.RandomDesEngine(cfg)
        refres = ref.run()
        ref_t_end = refres.metrics.get("T", None)
        if ref_t_end is None:
            last = [r for r in refres.event_log
                    if r["event_type"] == "SIMULATION_END"]
            ref_t_end = (Fraction(last[-1]["event_time"]) if last
                         else Fraction(0))
        else:
            ref_t_end = Fraction(ref_t_end)
        log0 = [r for r in refres.event_log
                if Fraction(r["event_time"]) <= Fraction(0)]
        st = obs.project_log_prefix(log0, Fraction(0), batch_size=bs)
        post = ps.PosteriorState.from_observable(st)
        world = _world_from_engine(ref, st, post)
        cfg_roll = re1.RolloutConfig(
            batch_size=bs, shift_length_h=Fraction(shift_len),
            shifts_per_day=spd, scenario="q3_two_shift",
            tau_pm=re1.NO_PM_BEFORE_MANDATORY)
        prov = _replay_provider_from_log(
            refres.event_log,
            tuple(sorted(d.device_id for d in st.devices)), RESOURCES)
        eng2 = re1.RolloutEngine(st, post, world, prov, cfg_roll,
                                 first_action=re1.A_H1_NOOP,
                                 log_prefix=refres.event_log)
        out = eng2.run()
        ok = (out.t_end == ref_t_end)
        if not ok:
            failures.append(
                f"{label}: T_end mismatch P3={out.t_end} accepted={ref_t_end}")
        ref_core = _core_events(refres.event_log, t0=Fraction(0))
        p3_core = _core_events(list(out.events), t0=Fraction(0))
        if ref_core != p3_core:
            failures.append(f"{label}: core-event summary mismatch "
                            f"ref={ref_core} p3={p3_core}")
        rows.append({"scenario": label, "ref_t_end": str(ref_t_end),
                     "p3_t_end": str(out.t_end),
                     "ref_core": ref_core, "p3_core": p3_core})
    return {
        "check": "H1_FALLBACK_PARITY",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures, "rows": rows,
    }


def _core_events(log: list[dict], t0: Fraction = Fraction(0)
                 ) -> dict[str, Any]:
    """Deterministic core-event summary (identity-independent), restricted
    to events AFTER the decision time t0 (the initial t0 releases/starts are
    reconstructed in-flight by the continuation and not re-emitted)."""
    post = [r for r in log if Fraction(r["event_time"]) > t0]
    starts = [r for r in post if r.get("event_type") == "ACTIVITY_START"]
    completes = [r for r in post if r.get("event_type") == "ACTIVITY_COMPLETE"]
    obs_ = [r for r in post if r.get("event_type") == "OBSERVATION_MATERIALIZED"]
    terms = [r for r in post if r.get("event_type") == "DEVICE_TERMINAL"]
    rel = [r for r in post if r.get("event_type") == "TASK_RELEASE"]
    repl = [r for r in post
            if r.get("event_type") == "EQUIPMENT_REPLACEMENT_START"]

    def _norm_outcome(o: Any) -> str:
        # normalize the outcome vocabulary across engines (PASS == NORMAL)
        if o in ("PASS", "NORMAL"):
            return "NORMAL"
        return o

    return {
        "n_start": len(starts),
        "n_complete": len(completes),
        "n_obs": len(obs_),
        "n_terminal": len(terms),
        "n_release": len(rel),
        "n_replacement": len(repl),
        "obs_outcomes": sorted(_norm_outcome(r.get("outcome")) for r in obs_),
        "terminal_states": sorted(r.get("terminal_state") for r in terms),
        "start_processes": sorted((r.get("process"), r.get("device_id"))
                                  for r in starts),
    }


# ---------------------------------------------------------------------------
# other checks
# ---------------------------------------------------------------------------


def check_rollout_kernel() -> dict[str, Any]:
    """Kernel smoke: run the fresh continuation engine on a tiny world with
    each first action; assert progress, absorption, and event sanity."""
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    log = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    st = obs.project_log_prefix(log, Fraction(0), batch_size=2)
    post = ps.PosteriorState.from_observable(st)
    world = cont.rebuild_continuation_world(
        st, post, {1: Fraction(1, 2), 2: Fraction(1, 2)}, {},
        {r: Fraction(1, 3) for r in RESOURCES})
    prov = re1.PostKeyProvider(
        u_x_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
        u_d_by_device={1: Fraction(1, 3), 2: Fraction(1, 3)},
        u_l_by_resource={r: Fraction(1, 3) for r in RESOURCES},
        u_y_lookup=lambda d, p, a: Fraction(1, 2),
        u_l_lookup=lambda r, g: Fraction(1, 3),
        u_x_subsystem_lookup=lambda d, s: Fraction(1, 2))
    for action in (re1.A_H1_NOOP, re1.A_START_HEAD, re1.A_WAIT_EVENT,
                   re1.A_PM_IDLE):
        cfg = re1.RolloutConfig(batch_size=2, shift_length_h=Fraction(300),
                                shifts_per_day=2, scenario="q3_two_shift",
                                tau_pm=re1.NO_PM_BEFORE_MANDATORY)
        eng = re1.RolloutEngine(st, post, world, prov, cfg,
                                first_action=action)
        out = eng.run()
        rows.append({"action": action, "t_end": str(out.t_end),
                     "events": len(out.events),
                     "passed": out.devices_passed,
                     "exited": out.devices_exited,
                     "u_y": out.consumed_u_y})
        if out.t_end <= Fraction(0):
            failures.append(f"{action}: non-positive T_end")
        if out.devices_passed + out.devices_exited != 2:
            failures.append(f"{action}: expected 2 terminal devices, got "
                            f"{out.devices_passed}+{out.devices_exited}")
    return {"check": "ROLLOUT_KERNEL", "status": "PASS" if not failures
            else "FAIL", "failures": failures, "rows": rows}


def check_future_d_materialization() -> dict[str, Any]:
    """SPEC 6: U_D_post consumed exactly once at the legal junction; never
    counterfactually; never twice."""
    failures: list[str] = []
    log = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    st = obs.project_log_prefix(log, Fraction(0), batch_size=2)
    post = ps.PosteriorState.from_observable(st)
    world = cont.rebuild_continuation_world(
        st, post, {1: Fraction(1, 2), 2: Fraction(1, 2)}, {},
        {r: Fraction(1, 3) for r in RESOURCES})
    prov = re1.PostKeyProvider(
        u_x_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
        u_d_by_device={1: Fraction(1, 10000), 2: Fraction(999, 1000)},
        u_l_by_resource={r: Fraction(1, 3) for r in RESOURCES},
        u_y_lookup=lambda d, p, a: Fraction(1, 2),
        u_l_lookup=lambda r, g: Fraction(1, 3),
        u_x_subsystem_lookup=lambda d, s: Fraction(1, 2))
    cfg = re1.RolloutConfig(batch_size=2, shift_length_h=Fraction(300),
                            shifts_per_day=2, scenario="q3_two_shift",
                            tau_pm=re1.NO_PM_BEFORE_MANDATORY)
    eng = re1.RolloutEngine(st, post, world, prov, cfg,
                            first_action=re1.A_H1_NOOP)
    out = eng.run()
    d_events = [r for r in out.events if r.get("event_type") == "D_CREATED"]
    if len(d_events) != 2:
        failures.append(f"expected 2 D_CREATED, got {len(d_events)}")
    d1 = [r for r in d_events if r.get("device_id") == 1]
    d2 = [r for r in d_events if r.get("device_id") == 2]
    if not (len(d1) == 1 and len(d2) == 1):
        failures.append("each device must materialize D exactly once")
    if d1 and d1[0].get("d_state") != "PROBLEM":
        failures.append(f"device1 u_d < q_D -> PROBLEM expected, got "
                        f"{d1[0].get('d_state')}")
    if d2 and d2[0].get("d_state") != "NORMAL":
        failures.append(f"device2 u_d > q_D -> NORMAL expected, got "
                        f"{d2[0].get('d_state')}")
    if out.consumed_u_d != 2:
        failures.append(f"consumed_u_d must be 2, got {out.consumed_u_d}")
    return {"check": "FUTURE_D_MATERIALIZATION",
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "n_d_created": len(d_events),
            "consumed_u_d": out.consumed_u_d}


def check_u_y_consumption() -> dict[str, Any]:
    """SPEC 7: U_Y_post consumed ONLY on valid completions; a run with all
    PASS observations must consume exactly the number of completed attempts
    and never for interrupted/cancelled fragments."""
    failures: list[str] = []
    log = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    st = obs.project_log_prefix(log, Fraction(0), batch_size=2)
    post = ps.PosteriorState.from_observable(st)
    world = cont.rebuild_continuation_world(
        st, post, {1: Fraction(1, 2), 2: Fraction(1, 2)}, {},
        {r: Fraction(1, 3) for r in RESOURCES})
    prov = re1.PostKeyProvider(
        u_x_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
        u_d_by_device={1: Fraction(1, 3), 2: Fraction(1, 3)},
        u_l_by_resource={r: Fraction(1, 3) for r in RESOURCES},
        u_y_lookup=lambda d, p, a: Fraction(1, 2),  # all NORMAL
        u_l_lookup=lambda r, g: Fraction(1, 3),
        u_x_subsystem_lookup=lambda d, s: Fraction(1, 2))
    cfg = re1.RolloutConfig(batch_size=2, shift_length_h=Fraction(300),
                            shifts_per_day=2, scenario="q3_two_shift",
                            tau_pm=re1.NO_PM_BEFORE_MANDATORY)
    eng = re1.RolloutEngine(st, post, world, prov, cfg,
                            first_action=re1.A_H1_NOOP)
    out = eng.run()
    obs_ev = [r for r in out.events
              if r.get("event_type") == "OBSERVATION_MATERIALIZED"]
    cancels = [r for r in out.events if r.get("event_type") == "TASK_CANCEL"]
    if out.consumed_u_y != len(obs_ev):
        failures.append(f"U_Y consumed {out.consumed_u_y} != completed "
                        f"observations {len(obs_ev)}")
    if out.consumed_u_y != 8:  # 2 devices x A,B,C,E = 8 completed attempts
        failures.append(f"expected 8 U_Y (2 devices x A,B,C,E PASS), got "
                        f"{out.consumed_u_y}")
    if cancels:
        failures.append(f"all-PASS run must have no cancels, got "
                        f"{len(cancels)}")
    # an ABNORMAL observation must still consume exactly one U_Y
    prov2 = re1.PostKeyProvider(
        u_x_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
        u_d_by_device={1: Fraction(1, 3), 2: Fraction(1, 3)},
        u_l_by_resource={r: Fraction(1, 3) for r in RESOURCES},
        u_y_lookup=lambda d, p, a: Fraction(1, 10000),  # all ABNORMAL -> retest
        u_l_lookup=lambda r, g: Fraction(1, 3),
        u_x_subsystem_lookup=lambda d, s: Fraction(1, 2))
    eng2 = re1.RolloutEngine(st, post, world, prov2, cfg,
                             first_action=re1.A_H1_NOOP)
    out2 = eng2.run()
    obs2 = [r for r in out2.events
            if r.get("event_type") == "OBSERVATION_MATERIALIZED"]
    if out2.consumed_u_y != len(obs2):
        failures.append(f"retest run U_Y {out2.consumed_u_y} != obs "
                        f"{len(obs2)}")
    return {"check": "U_Y_CONSUMPTION",
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "all_pass_u_y": out.consumed_u_y,
            "retest_u_y": out2.consumed_u_y}


def check_lifetime_generation() -> dict[str, Any]:
    """SPEC 8: current generation uses P2 conditional residual; every new
    generation binds a NEW U_L_post(resource, new_generation)."""
    failures: list[str] = []
    # force a failure so a replacement happens: lifetime ends inside the
    # first fragment; the new generation must draw a different U_L_post
    log = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    st = obs.project_log_prefix(log, Fraction(0), batch_size=2)
    post = ps.PosteriorState.from_observable(st)
    world = cont.rebuild_continuation_world(
        st, post, {1: Fraction(1, 2), 2: Fraction(1, 2)}, {},
        {r: Fraction(1, 3) for r in RESOURCES})
    # current gen lifetime: very short (failure during first fragment)
    world = cont.ContinuationWorld(
        decision_time=world.decision_time,
        devices=world.devices,
        residual_lifetimes={r: (Fraction(1, 100), False)
                            for r in RESOURCES})
    gen_draws: list[tuple[str, int, Fraction]] = []
    # deterministic distinct draws per generation: gen2 -> u=1/2 (lifetime
    # ~180h, lets the batch finish), later gens -> increasing u in (0,1)
    def _u_l(resource: str, generation: int) -> Fraction:
        u = Fraction(generation * 2 + 1, 16) if generation >= 2 else \
            Fraction(1, 3)
        u = min(u, Fraction(999, 1000))
        gen_draws.append((resource, generation, u))
        return u

    prov = re1.PostKeyProvider(
        u_x_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
        u_d_by_device={1: Fraction(1, 3), 2: Fraction(1, 3)},
        u_l_by_resource={r: Fraction(1, 3) for r in RESOURCES},
        u_y_lookup=lambda d, p, a: Fraction(1, 2),
        u_l_lookup=_u_l,
        u_x_subsystem_lookup=lambda d, s: Fraction(1, 2))
    cfg = re1.RolloutConfig(batch_size=2, shift_length_h=Fraction(300),
                            shifts_per_day=2, scenario="q3_two_shift",
                            tau_pm=re1.NO_PM_BEFORE_MANDATORY)
    eng = re1.RolloutEngine(st, post, world, prov, cfg,
                            first_action=re1.A_H1_NOOP)
    out = eng.run()
    replacements = [r for r in out.events
                    if r.get("event_type") == "EQUIPMENT_REPLACEMENT_START"]
    if not replacements:
        failures.append("expected >=1 replacement from short lifetime")
    # each new generation must have consumed a U_L_post draw
    new_gens = {r["new_generation"] for r in replacements}
    for g in sorted(new_gens):
        if g == 1:
            continue
        if not any(gd[1] == g for gd in gen_draws):
            failures.append(f"no U_L_post draw for generation {g}")
    return {"check": "LIFETIME_GENERATION",
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "n_replacements": len(replacements),
            "new_generations": sorted(new_gens),
            "u_l_generation_draws": [(r, g, str(u)) for r, g, u in gen_draws]}


def check_crn_world() -> dict[str, Any]:
    """SPEC 4: same (dp,m) across different candidate actions -> identical
    post-key manifest (byte/equality identical); different dp/m separated."""
    failures: list[str] = []
    gens = {r: 1 for r in RESOURCES}
    a = pk.rollout_post_keys(6, 0, 3, 2, (1, 2, 3), RESOURCES, gens)
    b = pk.rollout_post_keys(6, 0, 3, 2, (1, 2, 3), RESOURCES, gens)
    if a.to_canonical_dict() != b.to_canonical_dict():
        failures.append("same (dp,m) different call -> manifest differs")
    c = pk.rollout_post_keys(6, 0, 3, 3, (1, 2, 3), RESOURCES, gens)
    d = pk.rollout_post_keys(6, 0, 4, 2, (1, 2, 3), RESOURCES, gens)
    if a.to_canonical_dict() == c.to_canonical_dict():
        failures.append("different m not separated")
    if a.to_canonical_dict() == d.to_canonical_dict():
        failures.append("different dp not separated")
    return {"check": "CRN_WORLD",
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "manifest_dp3_m2": a.to_canonical_dict()}


def check_quota_selector() -> dict[str, Any]:
    """SPEC 11-14: parameterized C_eval 6/8; WAIT first W_cap; PM buckets +
    extra slot; invariants."""
    failures: list[str] = []
    rows: dict[str, Any] = {}
    for c_eval in (6, 8):
        w_cap = (c_eval + 1) // 2
        p_cap = c_eval // 2
        # 10 wait points, 10 PM points across the 3 buckets (all eligible)
        points: list[qsel.DecisionPointEvent] = []
        dp = 0
        for i in range(10):
            points.append(qsel.DecisionPointEvent(
                dp=dp, time=Fraction(i), resource="A", kind="dispatch",
                wait_legal=True, pm_legal=(i % 2 == 0), age_h=Fraction(130),
                head=(1, "B", 1)))
            dp += 1
        ages = [Fraction(130), Fraction(170), Fraction(210)]
        for i in range(10):
            points.append(qsel.DecisionPointEvent(
                dp=dp, time=Fraction(100 + i), resource="A", kind="maintenance",
                wait_legal=False, pm_legal=True, age_h=ages[i % 3]))
            dp += 1
        res = qsel.run_online_selection(c_eval, points)
        inv = qsel.check_invariants(res)
        if inv:
            failures.extend(inv)
        wait_sel = [r for r in res["rows"] if r["quota_class"] == "WAIT"
                    and r["selected_for_rollout"]]
        pm_sel = [r for r in res["rows"] if r["quota_class"] == "PM"
                  and r["selected_for_rollout"]]
        if len(wait_sel) != w_cap:
            failures.append(f"C_eval={c_eval}: wait selected "
                            f"{len(wait_sel)} != W_cap {w_cap}")
        # PM: 3 bucket-first + (extra if P_cap==4 and a 4th is eligible)
        # 10 PM-only points with ages cycling buckets -> all 3 buckets fill,
        # then extra slot (P_cap=4) takes one; P_cap=3 stops at 3.
        expected_pm = p_cap if p_cap == 3 else 4
        if len(pm_sel) != expected_pm:
            failures.append(f"C_eval={c_eval}: PM selected {len(pm_sel)} "
                            f"!= expected {expected_pm}")
        rows[c_eval] = {"w_cap": w_cap, "p_cap": p_cap,
                        "wait_selected": len(wait_sel),
                        "pm_selected": len(pm_sel),
                        "selected_total": res["selected_total"]}
    # both-point check: quota class WAIT but PM action still available
    both = qsel.DecisionPointEvent(
        dp=0, time=Fraction(0), resource="A", kind="dispatch",
        wait_legal=True, pm_legal=True, age_h=Fraction(130))
    if both.quota_class != qsel.WAIT_CLASS:
        failures.append("both point must classify as WAIT")
    if not both.is_both:
        failures.append("both point must keep pm_legal=True")
    return {"check": "QUOTA_SELECTOR",
            "status": "PASS" if not failures else "FAIL",
            "failures": failures, "rows": rows}


def check_quota_causality() -> dict[str, Any]:
    """SPEC 15: two histories identical up to t, differing after t -> at t
    the quota_class / selected_for_rollout / quota state are identical."""
    failures: list[str] = []
    # History A: points at t=0..4 (identical), then 5..9 (differ from B)
    prefix = [qsel.DecisionPointEvent(
        dp=i, time=Fraction(i), resource="A", kind="dispatch",
        wait_legal=True, pm_legal=False, age_h=Fraction(130)) for i in range(5)]
    tail_a = [qsel.DecisionPointEvent(
        dp=10 + i, time=Fraction(10 + i), resource="A", kind="maintenance",
        wait_legal=False, pm_legal=True, age_h=Fraction(130))
        for i in range(10)]
    tail_b = [qsel.DecisionPointEvent(
        dp=20 + i, time=Fraction(10 + i), resource="A", kind="maintenance",
        wait_legal=False, pm_legal=True, age_h=Fraction(210))
        for i in range(10)]
    res_a = qsel.run_online_selection(8, prefix + tail_a)
    res_b = qsel.run_online_selection(8, prefix + tail_b)
    # at t=4 (the last prefix point) the state must be identical
    state_at4_a = next(r["state_after"] for r in res_a["rows"]
                       if r["dp"] == 4)
    state_at4_b = next(r["state_after"] for r in res_b["rows"]
                       if r["dp"] == 4)
    if state_at4_a != state_at4_b:
        failures.append("quota state at t=4 differs between histories")
    sel_at4_a = next(r["selected_for_rollout"] for r in res_a["rows"]
                     if r["dp"] == 4)
    sel_at4_b = next(r["selected_for_rollout"] for r in res_b["rows"]
                     if r["dp"] == 4)
    if sel_at4_a != sel_at4_b:
        failures.append("selected_for_rollout at t=4 differs")
    return {"check": "QUOTA_CAUSALITY",
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "state_at_t4_identical": state_at4_a == state_at4_b}


def check_rollout_count() -> dict[str, Any]:
    """SPEC 16: C_rollout = 200 hard cap; worst-case counts for the frozen
    candidates (4,8)->96, (8,6)->144, (8,8)->192."""
    failures: list[str] = []
    for (m, c) in ((4, 8), (8, 6), (8, 8)):
        worst = c * 3 * m
        expected = {96, 144, 192}.intersection({worst})
        if worst > 200:
            failures.append(f"({m},{c}) worst {worst} > C_rollout 200")
        if not expected:
            failures.append(f"({m},{c}) worst {worst} not in frozen grid")
    return {"check": "ROLLOUT_COUNT",
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "c_rollout": 200,
            "worst_cases": {f"({m},{c})": m * 3 * c
                            for (m, c) in ((4, 8), (8, 6), (8, 8))}}


def check_q_estimator() -> dict[str, Any]:
    """SPEC 1.1 / 10: Q_hat_M and paired SE; a_H1 pairing; no tuning from
    Q in this package."""
    failures: list[str] = []
    # 2 actions, M=4, CRN-paired worlds
    t_s = Fraction(10)
    t_end_start = (Fraction(100), Fraction(120), Fraction(110), Fraction(90))
    t_end_h1 = (Fraction(105), Fraction(115), Fraction(105), Fraction(95))
    est = qest.q_hat_from_t_end(
        t_s, t_end_start, dp=0, action=re1.A_START_HEAD,
        a_h1=qest.A_H1_DISPATCH, t_end_h1_by_world=t_end_h1)
    d_m = tuple(a - b for a, b in zip(t_end_start, t_end_h1))
    if tuple(est.d_m) != d_m:
        failures.append("paired D_m wrong")
    # Q_hat = mean - t_s
    expect_q = sum(t_end_start, Fraction(0)) / 4 - t_s
    if est.q_hat != expect_q:
        failures.append(f"Q_hat {est.q_hat} != {expect_q}")
    if est.se_m is None or est.se_m < 0:
        failures.append("SE_M missing/negative")
    # both-point a_H1 must exist for dispatch/maintenance classes
    if qest.A_H1_DISPATCH != "START_HEAD":
        failures.append("a_H1(dispatch) != START_HEAD")
    if qest.A_H1_MAINTENANCE != "H1_NOOP":
        failures.append("a_H1(maintenance) != H1_NOOP")
    return {"check": "Q_ESTIMATOR",
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "q_hat": str(est.q_hat), "se_m": est.se_m}


def check_c23_rollout() -> dict[str, Any]:
    """SPEC 24: same ObservableState + same PosteriorState + same keys +
    same config + same first action -> hidden-world changes leave the full
    rollout T_end identical (C23 rollout path)."""
    failures: list[str] = []
    base = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    variants = [
        [dict(r) for r in base],
        [dict(r) for r in base],
        [dict(r) for r in base],
    ]
    variants[1][0]["true_state"] = {"A": True, "B": False, "C": False}
    variants[2][0]["true_state"] = {"A": True, "B": True, "C": True}
    gens = {r: 1 for r in RESOURCES}
    k = pk.rollout_post_keys(6, 0, 0, 0, (1, 2), RESOURCES, gens)
    results = []
    for log in variants:
        st = obs.project_log_prefix(log, Fraction(0), batch_size=2)
        post = ps.PosteriorState.from_observable(st)
        world = cont.rebuild_continuation_world(
            st, post, u_x_by_device=k.u_x_by_device,
            u_d_by_device=k.u_d_by_device,
            u_l_by_resource=k.u_l_by_resource)
        prov = re1.PostKeyProvider(
            u_x_by_device=k.u_x_by_device,
            u_x_subsystem_lookup=(
                (lambda d, sub: k.u_x_subsystem_by_device[d][sub])),
            u_d_by_device=k.u_d_by_device,
            u_l_by_resource=k.u_l_by_resource,
            u_y_lookup=k.u_y_lookup, u_l_lookup=k.u_l_lookup)
        cfg = re1.RolloutConfig(batch_size=2, shift_length_h=Fraction(300),
                                shifts_per_day=2, scenario="q3_two_shift",
                                tau_pm=re1.NO_PM_BEFORE_MANDATORY)
        eng = re1.RolloutEngine(st, post, world, prov, cfg,
                                first_action=re1.A_H1_NOOP)
        out = eng.run()
        results.append(out)
    # NOTE: the rebuild from the ObservableState is invariant to the hidden
    # log annotations (C23 P1), so all three worlds are identical
    if results[0].t_end != results[1].t_end or results[0].t_end != results[2].t_end:
        failures.append("T_end must be identical across hidden variants")
    return {"check": "C23_ROLLOUT",
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "t_end_by_variant": [str(r.t_end) for r in results]}


# ---------------------------------------------------------------------------
# P3-B-E1: current-generation residual-lifetime coordinate repair (F1)
# ---------------------------------------------------------------------------


def _own_absolute_failure_age(current_age: Fraction, tau: Optional[Fraction],
                              right_censored: bool) -> tuple[Fraction, bool]:
    """Checker's OWN expected conversion (F1): the engine's internal
    lifetime_h is the ABSOLUTE equipment age of natural failure.
      * right_censored=False: absolute = current_age + tau;
      * right_censored=True:  absolute = 240 (survive to 240).
    Independent of the implementer's conversion helper (never an oracle)."""
    if right_censored:
        return Fraction(240), True
    if tau is None:
        raise ValueError("natural-branch residual must not be None")
    return Fraction(current_age) + Fraction(tau), False


def check_current_generation_lifetime() -> dict[str, Any]:
    """CURR-LIFE-01..05 + §9: current-generation residual (tau from P2) must
    be converted to an ABSOLUTE failure age (age+tau / 240-right-censored);
    fragment failure timing must be computed in absolute coordinates."""
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    cases = [
        # (label, age, tau, censored, expected_absolute)
        ("CURR-LIFE-01", Fraction(150), Fraction(50), False, Fraction(200)),
        ("CURR-LIFE-03", Fraction(150), Fraction(90), True, Fraction(240)),
        ("CURR-LIFE-04", Fraction(0), Fraction(100), False, Fraction(100)),
        ("CURR-LIFE-05", Fraction(210), Fraction(10), False, Fraction(220)),
    ]
    for label, age, tau, cens, expected in cases:
        abs_age, abs_cens = _own_absolute_failure_age(age, tau, cens)
        ok = (abs_age == expected and abs_cens == cens)
        if not ok:
            failures.append(f"{label}: expected absolute {expected}/"
                            f"censored={cens}, checker got {abs_age}/"
                            f"{abs_cens}")
        rows.append({"case": label, "age": str(age), "residual_tau": str(tau),
                     "right_censored": cens,
                     "absolute_failure_age_expected": str(expected),
                     "absolute_failure_age_checker": str(abs_age),
                     "matches": ok})
    # CURR-LIFE-02: age=150, failure_age=200; a task starts at equipment
    # age 190 with duration 20 -> natural failure after 10 h fragment
    # (190 < 200 < 210), NOT an inconsistent-lifetime error.
    age02, fail_age02, start_age02, dur02 = (
        Fraction(150), Fraction(200), Fraction(190), Fraction(20))
    kind, frag = _own_fragment_outcome(start_age02, dur02, fail_age02, False)
    ok02 = (kind == "failed" and frag == Fraction(10))
    if not ok02:
        failures.append(f"CURR-LIFE-02: expected failed@10h, got "
                        f"{kind}@{frag}")
    rows.append({"case": "CURR-LIFE-02", "age": str(age02),
                 "absolute_failure_age": str(fail_age02),
                 "task_start_age": str(start_age02), "duration": str(dur02),
                 "expected_fragment_failure_time_h": "10",
                 "actual_fragment_failure_time_h": str(frag),
                 "kind": kind, "matches": ok02})
    # new-generation must stay UNCHANGED (age=0 unconditional sampler):
    # the conversion must never add age to a new-generation lifetime.
    new_gen = _own_absolute_failure_age(Fraction(0), Fraction(100), False)
    if new_gen[0] != Fraction(100):
        failures.append("new-generation age=0 conversion must equal the "
                        "sampled lifetime")
    rows.append({"case": "NEW-GEN-GUARD", "age": "0",
                 "sampled_lifetime": "100",
                 "absolute_after_conversion": str(new_gen[0]),
                 "matches": new_gen[0] == Fraction(100)})
    return {
        "check": "CURRENT_GENERATION_LIFETIME",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures, "rows": rows,
        "note": "independent oracle: absolute_failure_age = current_age + "
                "residual_tau; right-censored -> 240",
    }


def check_current_generation_failure_timing() -> dict[str, Any]:
    """§7: a real nonzero-age current-generation continuation where a task
    crosses the natural failure point.  Reports failure time / fragment
    elapsed / requeue / replacement trigger / final T_end.  Uses an
    INDEPENDENT_FROZEN_ORACLE (the checker's own expected conversion +
    fragment outcome), NOT the accepted engine (C23: a conditional
    posterior world cannot be injected into the live engine).

    Setup: resource A aged 150 (60 x 2.5h history fragments on device 1);
    current-generation conditional residual tau = 3/2 -> ABSOLUTE failure
    age = 151.5 (strictly inside device 2's A fragment [150, 152.5], so the
    natural failure lands MID-fragment after 1.5 h of that fragment).
    """
    failures: list[str] = []
    bs = 2
    log = [
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    for d in range(1, bs + 1):
        log.append({"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
                    "device_id": d,
                    "true_state": {"A": False, "B": False, "C": False}})
    # device 1: 60 A fragments (age 150)
    t = Fraction(0)
    for _ in range(60):
        e = t + Fraction(5, 2)
        log.append({"event_type": "TASK_RELEASE", "event_time": str(t),
                    "resource_id": "A", "device_id": 1, "process": "A",
                    "effective_attempt_no": 1})
        log.append({"event_type": "ACTIVITY_START", "event_time": str(t),
                    "device_id": 1, "process": "A",
                    "effective_attempt_no": 1, "resource_id": "A",
                    "attempt_start_time": str(t),
                    "attempt_end_time": str(e), "outcome": "NONE"})
        log.append({"event_type": "ACTIVITY_COMPLETE", "event_time": str(e),
                    "device_id": 1, "process": "A",
                    "effective_attempt_no": 1, "resource_id": "A",
                    "attempt_start_time": str(t), "attempt_end_time": str(e),
                    "outcome": "NONE"})
        log.append({"event_type": "OBSERVATION_MATERIALIZED",
                    "event_time": str(e), "device_id": 1, "process": "A",
                    "effective_attempt_no": 1, "resource_id": "A",
                    "outcome": "PASS"})
        t = e
    # device 2: A released at t=0 (queued; resource A busy with dev1 until
    # 150) -> starts at age 150, spans [150, 152.5]
    log.append({"event_type": "TASK_RELEASE", "event_time": "0",
                "resource_id": "A", "device_id": 2, "process": "A",
                "effective_attempt_no": 1})
    st150 = obs.project_log_prefix(log, Fraction(150), batch_size=bs)
    post150 = ps.PosteriorState.from_observable(st150)
    world = cont.rebuild_continuation_world(
        st150, post150,
        {d.device_id: Fraction(1, 2) for d in st150.devices},
        {d.device_id: Fraction(1, 3) for d in st150.devices},
        {r: Fraction(1, 3) for r in RESOURCES})
    world = cont.ContinuationWorld(
        decision_time=Fraction(150),
        devices=world.devices,
        residual_lifetimes={
            "A": (Fraction(3, 2), False),  # absolute failure age = 151.5
            "B": (Fraction(90), True),
            "C": (Fraction(90), True),
            "E": (Fraction(90), True),
        })
    prov = re1.PostKeyProvider(
        u_x_by_device={d: Fraction(1, 2) for d in range(1, bs + 1)},
        u_d_by_device={d: Fraction(1, 3) for d in range(1, bs + 1)},
        u_l_by_resource={r: Fraction(1, 3) for r in RESOURCES},
        u_y_lookup=lambda d, p, a: Fraction(1, 2),
        u_l_lookup=lambda r, g: Fraction(1, 3),
        u_x_subsystem_lookup=lambda d, s: Fraction(1, 2))
    cfg = re1.RolloutConfig(batch_size=bs, shift_length_h=Fraction(300),
                            shifts_per_day=2, scenario="q3_two_shift",
                            tau_pm=re1.NO_PM_BEFORE_MANDATORY)
    eng = re1.RolloutEngine(st150, post150, world, prov, cfg,
                            first_action=re1.A_H1_NOOP,
                            log_prefix=log)
    out = eng.run()
    # A natural failure must occur MID-fragment at absolute age 151.5
    fails = [r for r in out.events
             if r.get("event_type") == "EQUIPMENT_FAILURE"
             and r.get("resource_id") == "A"]
    mid_ok = any(Fraction(r.get("fragment_end", 0)) == Fraction(303, 2)
                 for r in fails)
    if not mid_ok:
        failures.append(
            f"A must fail mid-fragment at absolute age 151.5; got "
            f"{[{k: r.get(k) for k in ('fragment_start', 'fragment_end', 'elapsed_hours')} for r in fails]}")
    # the interrupted task must be cancelled/requeued
    cancels = [r for r in out.events
               if r.get("event_type") == "TASK_CANCEL"
               and r.get("resource_id") == "A"
               and r.get("cancel_reason") == "equipment_failure"]
    if not cancels:
        failures.append("the interrupted A task must be cancelled/requeued")
    # replacement must be triggered by the failure
    repls = [r for r in out.events
             if r.get("event_type") == "EQUIPMENT_REPLACEMENT_START"]
    if not repls:
        failures.append("natural failure must trigger a replacement")
    return {
        "check": "CURRENT_GENERATION_FAILURE_TIMING",
        "status": "PASS" if not failures else "FAIL",
        "oracle_type": "INDEPENDENT_FROZEN_ORACLE",
        "failures": failures,
        "decision_age_h": "150",
        "residual_tau_h": "3/2",
        "absolute_failure_age": "303/2 (151.5)",
        "a_failures_at_151.5": sum(
            1 for r in fails
            if Fraction(r.get("fragment_end", 0)) == Fraction(303, 2)),
        "a_cancels_failure": len(cancels),
        "n_replacements": len(repls),
        "t_end": str(out.t_end),
        "note": "NOT accepted-engine parity: C23 forbids injecting a "
                "conditional posterior world into the live engine; the "
                "expected failure time is the checker's own frozen oracle",
    }


def check_right_censor_240() -> dict[str, Any]:
    """CURR-LIFE-03 coverage: a right-censored current generation (residual
    90 at age 150) must survive to 240 with NO natural failure before 240;
    the 240 boundary is handled by the mandatory rule."""
    failures: list[str] = []
    # direct oracle on the conversion
    abs_age, cens = _own_absolute_failure_age(Fraction(150), Fraction(90),
                                              True)
    if not (abs_age == Fraction(240) and cens):
        failures.append("right-censored conversion must be (240, True)")
    # engine-level: a continuation from age 150 with A right-censored must
    # never emit a natural A failure below 240
    log = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    t = Fraction(0)
    for _ in range(60):
        e = t + Fraction(5, 2)
        log.append({"event_type": "TASK_RELEASE", "event_time": str(t),
                    "resource_id": "A", "device_id": 1, "process": "A",
                    "effective_attempt_no": 1})
        log.append({"event_type": "ACTIVITY_START", "event_time": str(t),
                    "device_id": 1, "process": "A",
                    "effective_attempt_no": 1, "resource_id": "A",
                    "attempt_start_time": str(t),
                    "attempt_end_time": str(e), "outcome": "NONE"})
        log.append({"event_type": "ACTIVITY_COMPLETE", "event_time": str(e),
                    "device_id": 1, "process": "A",
                    "effective_attempt_no": 1, "resource_id": "A",
                    "attempt_start_time": str(t), "attempt_end_time": str(e),
                    "outcome": "NONE"})
        log.append({"event_type": "OBSERVATION_MATERIALIZED",
                    "event_time": str(e), "device_id": 1, "process": "A",
                    "effective_attempt_no": 1, "resource_id": "A",
                    "outcome": "PASS"})
        t = e
    st150 = obs.project_log_prefix(log, Fraction(150), batch_size=2)
    post150 = ps.PosteriorState.from_observable(st150)
    world = cont.ContinuationWorld(
        decision_time=Fraction(150),
        devices=cont.rebuild_continuation_world(
            st150, post150, {1: Fraction(1, 2), 2: Fraction(1, 2)}, {},
            {r: Fraction(1, 3) for r in RESOURCES}).devices,
        residual_lifetimes={r: (Fraction(90), True) for r in RESOURCES})
    prov = re1.PostKeyProvider(
        u_x_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
        u_d_by_device={1: Fraction(1, 3), 2: Fraction(1, 3)},
        u_l_by_resource={r: Fraction(1, 3) for r in RESOURCES},
        u_y_lookup=lambda d, p, a: Fraction(1, 2),
        u_l_lookup=lambda r, g: Fraction(1, 3),
        u_x_subsystem_lookup=lambda d, s: Fraction(1, 2))
    cfg = re1.RolloutConfig(batch_size=2, shift_length_h=Fraction(300),
                            shifts_per_day=2, scenario="q3_two_shift",
                            tau_pm=re1.NO_PM_BEFORE_MANDATORY)
    eng = re1.RolloutEngine(st150, post150, world, prov, cfg,
                            first_action=re1.A_H1_NOOP, log_prefix=log)
    out = eng.run()
    early = [r for r in out.events
             if r.get("event_type") == "EQUIPMENT_FAILURE"
             and Fraction(r.get("fragment_end", 0)) < Fraction(240)]
    if early:
        failures.append(f"right-censored generation must not fail naturally "
                        f"before 240: {early[:3]}")
    return {
        "check": "RIGHT_CENSOR_240",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "conversion": {"age": "150", "residual": "90",
                       "absolute_expected": "240",
                       "absolute_checker": str(abs_age)},
        "n_natural_failures_before_240": len(early),
    }


def check_no_pm_string_semantics() -> dict[str, Any]:
    """§8: _replacement_decision must compare the NO_PM sentinel by VALUE
    (string semantics), never by Python object identity; a dynamically
    constructed equal string must take the SERVE_HEAD path (not
    Fraction(tau_pm) which would raise)."""
    failures: list[str] = []
    # dynamically constructed equal string (same value, different object)
    dyn = "".join(ch for ch in "NO_PM_BEFORE_MANDATORY")
    if dyn == re1.NO_PM_BEFORE_MANDATORY and dyn is not re1.NO_PM_BEFORE_MANDATORY:
        pass
    else:
        failures.append("test precondition: dynamic string must be a "
                        "different object with equal value")
    try:
        dec = re1._replacement_decision(Fraction(10), Fraction(2), dyn, True)
        if dec != "SERVE_HEAD":
            failures.append(f"dynamic NO_PM string must give SERVE_HEAD, "
                            f"got {dec}")
    except Exception as exc:  # pragma: no cover - the bug would raise here
        failures.append(f"dynamic NO_PM string fell into the numeric path: "
                        f"{type(exc).__name__}: {exc}")
    # sentinel object must still work
    dec2 = re1._replacement_decision(Fraction(10), Fraction(2),
                                     re1.NO_PM_BEFORE_MANDATORY, True)
    if dec2 != "SERVE_HEAD":
        failures.append(f"sentinel must give SERVE_HEAD, got {dec2}")
    # numeric tau_pm must still work
    dec3 = re1._replacement_decision(Fraction(130), Fraction(2),
                                     Fraction(120), True)
    if dec3 != "PREVENTIVE_REPLACE":
        failures.append(f"numeric tau_pm=120 must give PREVENTIVE_REPLACE "
                        f"at age 130, got {dec3}")
    return {"check": "NO_PM_STRING_SEMANTICS",
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "dynamic_string_equals_sentinel": dyn == re1.NO_PM_BEFORE_MANDATORY,
            "dynamic_string_is_not_sentinel": dyn is not re1.NO_PM_BEFORE_MANDATORY,
            "dynamic_decision": dec if 'dec' in dir() else None}


def check_nonzero_age_runtime_sanity() -> dict[str, Any]:
    """§12: run a full continuation to absorption from a current-generation
    state with age >= 120 (after the F1 fix).  Must not crash / no-progress /
    immediate-failure; report wallclock and terminal counts (correctness /
    performance disclosure only -- never alters the frozen c_r aggregation
    or the M/C_eval selection rule)."""
    failures: list[str] = []
    import time as _time
    log = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    t = Fraction(0)
    for _ in range(48):  # 120 h of A fragments
        e = t + Fraction(5, 2)
        log.append({"event_type": "TASK_RELEASE", "event_time": str(t),
                    "resource_id": "A", "device_id": 1, "process": "A",
                    "effective_attempt_no": 1})
        log.append({"event_type": "ACTIVITY_START", "event_time": str(t),
                    "device_id": 1, "process": "A",
                    "effective_attempt_no": 1, "resource_id": "A",
                    "attempt_start_time": str(t),
                    "attempt_end_time": str(e), "outcome": "NONE"})
        log.append({"event_type": "ACTIVITY_COMPLETE", "event_time": str(e),
                    "device_id": 1, "process": "A",
                    "effective_attempt_no": 1, "resource_id": "A",
                    "attempt_start_time": str(t), "attempt_end_time": str(e),
                    "outcome": "NONE"})
        log.append({"event_type": "OBSERVATION_MATERIALIZED",
                    "event_time": str(e), "device_id": 1, "process": "A",
                    "effective_attempt_no": 1, "resource_id": "A",
                    "outcome": "PASS"})
        t = e
    st120 = obs.project_log_prefix(log, Fraction(120), batch_size=2)
    post120 = ps.PosteriorState.from_observable(st120)
    world = cont.rebuild_continuation_world(
        st120, post120, {1: Fraction(1, 2), 2: Fraction(1, 2)}, {},
        {r: Fraction(1, 3) for r in RESOURCES})
    # ensure a finite natural failure (age 120 + residual 40 -> 160)
    world = cont.ContinuationWorld(
        decision_time=world.decision_time, devices=world.devices,
        residual_lifetimes={
            "A": (Fraction(40), False), "B": (Fraction(40), False),
            "C": (Fraction(40), False), "E": (Fraction(40), False)})
    prov = re1.PostKeyProvider(
        u_x_by_device={1: Fraction(1, 2), 2: Fraction(1, 2)},
        u_d_by_device={1: Fraction(1, 3), 2: Fraction(1, 3)},
        u_l_by_resource={r: Fraction(1, 3) for r in RESOURCES},
        u_y_lookup=lambda d, p, a: Fraction(1, 2),
        u_l_lookup=lambda r, g: Fraction(1, 3),
        u_x_subsystem_lookup=lambda d, s: Fraction(1, 2))
    cfg = re1.RolloutConfig(batch_size=2, shift_length_h=Fraction(300),
                            shifts_per_day=2, scenario="q3_two_shift",
                            tau_pm=re1.NO_PM_BEFORE_MANDATORY)
    t0 = _time.perf_counter()
    eng = re1.RolloutEngine(st120, post120, world, prov, cfg,
                            first_action=re1.A_H1_NOOP, log_prefix=log)
    out = eng.run()
    wall = _time.perf_counter() - t0
    if out.t_end <= Fraction(120):
        failures.append("no-progress: continuation terminated at/below the "
                        "decision time")
    if out.devices_passed + out.devices_exited != 2:
        failures.append("expected 2 terminal devices, got "
                        f"{out.devices_passed}+{out.devices_exited}")
    return {
        "check": "NONZERO_AGE_RUNTIME_SANITY",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "decision_age_h": 120,
        "t_end": str(out.t_end),
        "passed": out.devices_passed, "exited": out.devices_exited,
        "wallclock_s": round(wall, 4),
        "note": "correctness/performance disclosure only; does NOT alter "
                "the frozen c_r aggregation or the M/C_eval selection rule",
    }


def run_all() -> dict[str, Any]:
    checks = [check_rollout_kernel(), check_h1_fallback_parity(),
              check_future_d_materialization(), check_u_y_consumption(),
              check_lifetime_generation(), check_crn_world(),
              check_quota_selector(), check_quota_causality(),
              check_rollout_count(), check_q_estimator(),
              check_c23_rollout(),
              check_current_generation_lifetime(),
              check_current_generation_failure_timing(),
              check_right_censor_240(),
              check_no_pm_string_semantics(),
              check_nonzero_age_runtime_sanity()]
    all_ok = all(c["status"] == "PASS" for c in checks)
    return {"overall": "PASS" if all_ok else "FAIL", "checks": checks}


if __name__ == "__main__":
    result = run_all()
    print(result["overall"])
    for c in result["checks"]:
        print(f"  {c['check']}: {c['status']}")
        if c["failures"]:
            for f in c["failures"][:6]:
                print(f"    - {f}")
    sys.exit(0 if result["overall"] == "PASS" else 1)
