#!/usr/bin/env python3
"""Q3-H2-P3-C frozen H2 policy: Q_hat / SE / 2SE confident deviation
(SPEC 4 / D-10, frozen; final policy config authorized at c271a62).

For each quota-selected decision point s:
  * legal actions (dispatch: {START_HEAD, WAIT_EVENT?, PM_WITH_HEAD?};
    maintenance: {H1_NOOP, PM_IDLE}) with a_H1:
      dispatch -> START_HEAD; maintenance -> H1_NOOP;
  * for every legal candidate action a: M=8 continuation rollouts
    (CRN: same rollout_seed(dp,m) across actions -> same m worlds);
  * Q_hat_M(s,a) = 1/M * sum_m [T_end^(m)(s; a -> H1) - t(s)];
  * paired D_m(a) = T_end^(m)(a) - T_end^(m)(a_H1),
    SE_M = sample_sd(D_m)/sqrt(M);
  * deviate iff argmin_a Q_hat = a* != a_H1 AND
    Q_hat(a*) < Q_hat(a_H1) - 2*SE_M(a* vs a_H1);
  * otherwise execute a_H1.

Tie-breaking for equal Q_hat values: the frozen canonical action order is
taken from the accepted P3 action module (decision_point_v1 action-name
constants, declaration order): START_HEAD < H1_NOOP < WAIT_EVENT <
PM_WITH_HEAD < PM_IDLE.  If the authority did not specify a tie order,
this deterministic declaration order is used (documented; no invention of
new rules).

This module is PURE (no live-DES imports; consumes post keys via the
provider); the batch driver supplies the provider / world.

Python 3.12, standard library only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Optional

from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from main_model.h2 import continuation_v1 as cont  # noqa: E402
from main_model.h2_rollout import rollout_engine_v1 as re1  # noqa: E402
from main_model.h2_rollout.post_keys_v1 import rollout_post_keys  # noqa: E402

M_STAR = 8
C_EVAL_STAR = 8
W_CAP_STAR = 4
P_CAP_STAR = 4

# canonical action tie order (accepted P3 module declaration order)
ACTION_ORDER = (re1.A_START_HEAD, re1.A_H1_NOOP, re1.A_WAIT_EVENT,
                re1.A_PM_WITH_HEAD, re1.A_PM_IDLE)
ACTION_RANK = {name: i for i, name in enumerate(ACTION_ORDER)}


@dataclass(frozen=True)
class ActionEstimate:
    action: str
    t_end_by_world: tuple[Fraction, ...]
    q_hat: Fraction
    d_m: tuple[Fraction, ...]
    se_m: Optional[float]

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "t_end_by_world": [str(x) for x in self.t_end_by_world],
            "q_hat": str(self.q_hat),
            "d_m": [str(x) for x in self.d_m],
            "se_m": self.se_m,
        }


@dataclass(frozen=True)
class PolicyDecision:
    dp: int
    time: Fraction
    resource: str
    kind: str                     # "dispatch" | "maintenance"
    quota_class: str              # "WAIT" | "PM"
    legal_actions: tuple[str, ...]
    a_h1: str
    estimates: dict[str, ActionEstimate]
    argmin: str
    chosen: str
    deviated: bool

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "dp": self.dp, "time": str(self.time), "resource": self.resource,
            "kind": self.kind, "quota_class": self.quota_class,
            "legal_actions": list(self.legal_actions), "a_h1": self.a_h1,
            "estimates": {a: e.to_canonical_dict()
                          for a, e in sorted(self.estimates.items())},
            "argmin": self.argmin, "chosen": self.chosen,
            "deviated": self.deviated,
        }


def _sample_sd(values: tuple[Fraction, ...]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values, Fraction(0)) / len(values)
    ss = sum((v - mean) ** 2 for v in values)
    return math.sqrt(float(ss / (len(values) - 1)))


def _argmin_action(estimates: dict[str, ActionEstimate]) -> str:
    """argmin Q_hat with the frozen canonical action-order tie-break."""
    best = min(estimates, key=lambda a: (estimates[a].q_hat,
                                         ACTION_RANK[a]))
    return best


def evaluate_decision_point(
        state: obs.ObservableState,
        posterior: ps.PosteriorState,
        world: cont.ContinuationWorld,
        provider: re1.PostKeyProvider,
        cfg: re1.RolloutConfig,
        dp: int, resource: str, kind: str, quota_class: str,
        legal_actions: tuple[str, ...],
        log_prefix: Optional[list[dict[str, Any]]],
        master_seed_h2: int, replicate_id: int,
        wait_anchor_time: Optional[Fraction] = None,
        M: int = M_STAR,
        salt: str = "q3h2-bootstrap-v1",
) -> PolicyDecision:
    """Evaluate one decision point: run M rollouts per legal action (CRN:
    same (dp, m) post-key bundle across actions) and apply the 2SE rule.
    ``salt`` selects the rollout salt (normal ROLLOUT_SALT or the frozen
    ALT salt for stability (b))."""
    a_h1 = (re1.A_START_HEAD if kind == "dispatch" else re1.A_H1_NOOP)
    actions = tuple(legal_actions) if legal_actions else (a_h1,)
    if a_h1 not in actions:
        actions = (a_h1,) + tuple(a for a in actions if a != a_h1)
    estimates: dict[str, ActionEstimate] = {}
    t_h1: Optional[tuple[Fraction, ...]] = None
    # Rollout keys must cover EVERY device that the continuation may create
    # (turnover-in devices with ids up to cfg.batch_size draw U_X_post /
    # U_D_post when they enter; only the devices present at the decision
    # point would KeyError).  The full id range 1..batch_size is fixed per
    # batch world and identical across all candidate actions, so CRN is
    # preserved (same (dp, m, device) -> same draws).
    device_ids = tuple(range(1, cfg.batch_size + 1))
    for a in actions:
        t_ends: list[Fraction] = []
        for m in range(M):
            keys = rollout_post_keys(master_seed_h2, replicate_id, dp, m,
                                     device_ids,
                                     tuple(r.resource for r in state.resources),
                                     {r.resource: r.generation
                                      for r in state.resources},
                                     salt=salt)
            eng_prov = re1.PostKeyProvider(
                u_x_by_device=keys.u_x_by_device,
                u_x_subsystem_lookup=(
                    lambda d, s, _k=keys: _k.u_x_subsystem_by_device[d][s]),
                u_d_by_device=keys.u_d_by_device,
                u_l_by_resource=keys.u_l_by_resource,
                u_y_lookup=keys.u_y_lookup, u_l_lookup=keys.u_l_lookup)
            first_action = a
            pm_resource = resource if a in (re1.A_PM_WITH_HEAD,
                                            re1.A_PM_IDLE) else None
            anchor = wait_anchor_time if a == re1.A_WAIT_EVENT else None
            eng = re1.RolloutEngine(
                state, posterior, world, eng_prov, cfg,
                first_action=first_action, wait_anchor_time=anchor,
                pm_resource=pm_resource, log_prefix=log_prefix)
            out = eng.run()
            t_ends.append(out.t_end)
        tw = tuple(t_ends)
        if a == a_h1:
            t_h1 = tw
        estimates[a] = ActionEstimate(action=a, t_end_by_world=tw,
                                      q_hat=sum(tw, Fraction(0)) / M - state.time,
                                      d_m=(), se_m=None)
    # paired SE vs a_H1
    if t_h1 is not None:
        for a in actions:
            e = estimates[a]
            d_m = tuple(e.t_end_by_world[i] - t_h1[i]
                        for i in range(M))
            se = _sample_sd(d_m) / math.sqrt(M)
            estimates[a] = ActionEstimate(action=a, t_end_by_world=e.t_end_by_world,
                                          q_hat=e.q_hat, d_m=d_m, se_m=se)
    argmin = _argmin_action(estimates)
    chosen = a_h1
    deviated = False
    if argmin != a_h1:
        e_star = estimates[argmin]
        e_h1 = estimates[a_h1]
        if (e_star.se_m is not None
                and e_star.q_hat < e_h1.q_hat - 2 * Fraction(e_star.se_m)):
            chosen = argmin
            deviated = True
    return PolicyDecision(
        dp=dp, time=state.time, resource=resource, kind=kind,
        quota_class=quota_class, legal_actions=actions, a_h1=a_h1,
        estimates=estimates, argmin=argmin, chosen=chosen, deviated=deviated)


def evaluate_batch_sample(
        sample_points: list[dict[str, Any]],
        state_builder,  # callable(dp info) -> (state, posterior, world, cfg, log_prefix)
        master_seed_h2: int, replicate_id: int,
) -> dict[str, Any]:
    """Evaluate a deterministic sample of decision points (B-1 stability /
    transfer diagnostics).  ``sample_points`` = list of dicts with
    dp/time/resource/kind/quota_class/legal_actions; ``state_builder`` is a
    callable returning the evaluation context for one point."""
    rows = []
    n_wait = 0
    n_pm = 0
    n_both = 0
    n_dev = 0
    dev_types: dict[str, int] = {}
    for p in sample_points:
        ctx = state_builder(p)
        dec = evaluate_decision_point(
            ctx["state"], ctx["posterior"], ctx["world"], ctx["provider"],
            ctx["cfg"], p["dp"], p["resource"], p["kind"], p["quota_class"],
            tuple(p["legal_actions"]), ctx["log_prefix"],
            master_seed_h2, replicate_id,
            wait_anchor_time=p.get("wait_anchor_time"),
            M=p.get("M", M_STAR))
        cls = p["quota_class"]
        if cls == "WAIT":
            n_wait += 1
        else:
            n_pm += 1
        if p.get("is_both"):
            n_both += 1
        if dec.deviated:
            n_dev += 1
            dev_types[dec.chosen] = dev_types.get(dec.chosen, 0) + 1
        rows.append(dec.to_canonical_dict())
    n = len(rows)
    return {
        "n": n, "n_wait": n_wait, "n_pm": n_pm, "n_both": n_both,
        "n_deviated": n_dev,
        "deviation_rate": (n_dev / n) if n else 0.0,
        "deviation_types": dev_types,
        "rows": rows,
    }
