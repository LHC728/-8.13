#!/usr/bin/env python3
"""Q3-H2-P2 residual lifetime conditional-survival generator (SPEC section
9, frozen).

Objects: the CURRENT-generation equipment only (past generations' observed
lifetimes are observable history and are never resampled).

  * conditional survival at age ``a``:
        P(L - a > u | L > a) = [1 - F(a+u)] / [1 - F(a)]
  * p_max(a) = [F(240) - F(a)] / [1 - F(a)]
  * given v = U_L_post in (0,1):
      - v <= p_max(a): natural residual lifetime
            tau = F^{-1}( F(a) + v*(1 - F(a)) ) - a
        using the SAME piecewise-linear CDF/inverse as the accepted G3
        lifetime sampler (input changed to the conditional probability
        value); exact Fraction;
      - v > p_max(a): RIGHT-CENSORED branch -- the random residual lifetime
        exceeds 240 - a; in continuation the equipment is deterministically
        force-replaced at 240 h (tau clipped to 240 - a, flag
        survive_to_240 / right_censored).
  * the [0,240] CDF is NEVER renormalized (R39); at a=0, p_max = F(240),
    i.e. the generator degenerates to the accepted G3 unconditional sampler.
  * the 240 h rule is unchanged in continuation: natural failure only when
    a + tau <= 240; a+d > 240 -> pre-start mandatory replacement (never an
    optional PM); a+d == 240 -> completion first, then mandatory
    replacement.

Piecewise-linear CDF (G3-SPEC-V1.0 section 4):
    F(t) = f120 * t / 120                         for t <= 120
    F(t) = f120 + (f240 - f120) * (t - 120) / 120 for 120 < t <= 240
inverse (three-branch, exact):
    t = 120 * y / f120                            for y <= f120
    t = 120 + 120 * (y - f120) / (f240 - f120)    for f120 < y <= f240
    y > f240 -> right-censored.

Pure function library over exact Fractions; the U_L_post draw is provided
by the caller (h2 package never imports the live DES engine / key schema).

Python 3.12, standard library only.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Optional

from main_model.h2.frozen_params_v1 import F120, F240, MANDATORY_AGE_H

# epsilon for the frozen U-grid boundary points (SPEC section 9).
EPSILON: Fraction = Fraction(1, 10**9)


def cdf(t: Fraction, f120: Fraction, f240: Fraction) -> Fraction:
    """Piecewise-linear CDF F(t) on [0, 240] (G3-SPEC-V1.0 section 4)."""
    t = Fraction(t)
    if t <= Fraction(120):
        return f120 * t / Fraction(120)
    return f120 + (f240 - f120) * (t - Fraction(120)) / Fraction(120)


def inverse_cdf(y: Fraction, f120: Fraction, f240: Fraction
                ) -> tuple[Fraction | None, bool]:
    """Exact three-branch inverse CDF.  Returns (lifetime_hour, right_
    censored); ``y > f240`` -> (None, True)."""
    y = Fraction(y)
    if y <= f120:
        return Fraction(120) * y / f120, False
    if y <= f240:
        return (Fraction(120)
                + Fraction(120) * (y - f120) / (f240 - f120)), False
    return None, True


def p_max(age: Fraction, f120: Fraction, f240: Fraction) -> Fraction:
    """p_max(a) = [F(240) - F(a)] / [1 - F(a)] (frozen)."""
    age = Fraction(age)
    fa = cdf(age, f120, f240)
    f240v = cdf(Fraction(240), f120, f240)
    return (f240v - fa) / (Fraction(1) - fa)


def conditional_residual(v: Fraction, age: Fraction, f120: Fraction,
                         f240: Fraction) -> tuple[Optional[Fraction], bool]:
    """Frozen conditional residual-lifetime draw.

    Returns ``(tau, right_censored)``:
      * tau = natural residual lifetime in hours (exact Fraction) with
        right_censored=False when v <= p_max(a);
      * tau = 240 - a with right_censored=True (survive_to_240) when
        v > p_max(a).
    """
    v = Fraction(v)
    age = Fraction(age)
    pm = p_max(age, f120, f240)
    if v > pm:
        return MANDATORY_AGE_H - age, True
    fa = cdf(age, f120, f240)
    target = fa + v * (Fraction(1) - fa)
    lifetime, censored = inverse_cdf(target, f120, f240)
    if censored or lifetime is None:
        # target <= F(240) by construction (v <= p_max); defensive
        return MANDATORY_AGE_H - age, True
    return lifetime - age, False


def p_max_frozen(age: Fraction, resource: str) -> Fraction:
    return p_max(age, F120[resource], F240[resource])


def conditional_residual_frozen(v: Fraction, age: Fraction, resource: str
                                ) -> tuple[Optional[Fraction], bool]:
    return conditional_residual(v, age, F120[resource], F240[resource])
