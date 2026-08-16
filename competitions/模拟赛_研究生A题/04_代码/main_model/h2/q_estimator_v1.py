#!/usr/bin/env python3
"""Q3-H2-P3-B Q_hat_M estimator and paired SE (SPEC section 1.1, frozen).

Q_hat_M(s, a) = 1/M * sum_m [ T_end^(m)(s; a -> H1) - t(s) ]

  * each world m is rebuilt from the SAME ObservableState / PosteriorState
    with rollout_seed(dp, m) post keys;
  * candidate first action a applies only to the first step; afterwards the
    accepted H1 baseline (NO_PM_BEFORE_MANDATORY) runs to batch absorption;
  * absorption-tail value is 0 (no truncation / no finite horizon / no
    terminal-tail approximation / no second H2 call / no candidate-action-
    specific random seed).

Paired differences vs a_H1(s) (frozen):
  D_m(a) = T_end^(m)(a) - T_end^(m)(a_H1)
  SE_M   = sample_sd(D_m) / sqrt(M)

This module ONLY computes and validates; it never adjusts M / C_eval / the
action set from Q results (SPEC 1.2: M/C_eval are cost-driven only).

Python 3.12, standard library only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Callable, Optional

# frozen a_H1 per decision-point class (SPEC 10)
A_H1_DISPATCH = "START_HEAD"
A_H1_MAINTENANCE = "H1_NOOP"


@dataclass(frozen=True)
class QEstimate:
    """Q_hat_M(s,a) plus the paired SE against a_H1(s)."""
    dp: int
    action: str
    a_h1: str
    t_s: Fraction
    M: int
    t_end_by_world: tuple[Fraction, ...]
    q_hat: Fraction
    d_m: tuple[Fraction, ...]          # D_m(a) = T_end(a) - T_end(a_H1)
    se_m: Optional[float]              # sample_sd(D_m)/sqrt(M)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "dp": self.dp, "action": self.action, "a_h1": self.a_h1,
            "t_s": str(self.t_s), "M": self.M,
            "t_end_by_world": [str(x) for x in self.t_end_by_world],
            "q_hat": str(self.q_hat),
            "d_m": [str(x) for x in self.d_m],
            "se_m": self.se_m,
        }


def sample_sd(values: tuple[Fraction, ...]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values, Fraction(0)) / len(values)
    ss = sum((v - mean) ** 2 for v in values)
    return math.sqrt(float(ss / (len(values) - 1)))


def q_hat_from_t_end(t_s: Fraction, t_end_by_world: tuple[Fraction, ...],
                     dp: int, action: str, a_h1: str,
                     t_end_h1_by_world: Optional[tuple[Fraction, ...]] = None,
                     ) -> QEstimate:
    """Build a Q estimate from per-world T_end values.  ``t_end_h1_by_world``
    (the a_H1 worlds, same m index) is required to compute the paired D_m
    and SE_M; the caller must ensure CRN pairing (same m -> same world)."""
    M = len(t_end_by_world)
    if M == 0:
        raise ValueError("empty world set")
    q = (sum(t_end_by_world, Fraction(0)) / M) - t_s
    d_m: tuple[Fraction, ...] = ()
    se: Optional[float] = None
    if t_end_h1_by_world is not None:
        if len(t_end_h1_by_world) != M:
            raise ValueError("a_H1 world count must equal M (CRN pairing)")
        d_m = tuple(t_end_by_world[i] - t_end_h1_by_world[i]
                    for i in range(M))
        se = sample_sd(d_m) / math.sqrt(M)
    return QEstimate(dp=dp, action=action, a_h1=a_h1, t_s=t_s, M=M,
                     t_end_by_world=t_end_by_world, q_hat=q, d_m=d_m, se_m=se)


def estimate_action_values(
        dp: int, t_s: Fraction,
        t_end_by_action: dict[str, tuple[Fraction, ...]],
        decision_class: str) -> dict[str, QEstimate]:
    """Compute Q_hat for every candidate action of one decision point with
    paired SE vs a_H1 (CRN: the same m index across actions is the same
    world).  decision_class: "dispatch" | "maintenance"."""
    a_h1 = (A_H1_DISPATCH if decision_class == "dispatch"
            else A_H1_MAINTENANCE)
    if a_h1 not in t_end_by_action:
        raise ValueError(f"a_H1 action {a_h1} missing for dp {dp}")
    h1_worlds = t_end_by_action[a_h1]
    out: dict[str, QEstimate] = {}
    for action, worlds in t_end_by_action.items():
        out[action] = q_hat_from_t_end(
            t_s, worlds, dp, action, a_h1, h1_worlds)
    return out


def confident_deviation(estimates: dict[str, QEstimate]) -> Optional[str]:
    """Frozen deviation rule (SPEC 4): deviate iff
    argmin_a Q_hat(s,a) = a* != a_H1(s) AND
    Q_hat(a*) < Q_hat(a_H1) - 2 * SE_M(a* vs a_H1).  Returns the chosen
    action or None (H1 default).  Validation-only; NOT used for any tuning
    in this package."""
    a_h1 = next(e.a_h1 for e in estimates.values())
    best = min(estimates, key=lambda a: estimates[a].q_hat)
    if best == a_h1:
        return None
    e_best = estimates[best]
    e_h1 = estimates[a_h1]
    if e_best.se_m is None:
        return None
    if e_best.q_hat < e_h1.q_hat - 2 * Fraction(e_best.se_m):
        return best
    return None
