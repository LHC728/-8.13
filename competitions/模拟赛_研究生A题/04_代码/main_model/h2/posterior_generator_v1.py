#!/usr/bin/env python3
"""Q3-H2-P2 posterior defect-state generator (SPEC section 8, frozen).

Implements the frozen joint posterior over the hidden defect states
``(x_A, x_B, x_C, x_D)`` given the OBSERVABLE materialized observation
history (section 8):

  * priors ``x_j ~ Bernoulli(q_j)`` (j = A/B/C) and ``x_D ~ Bernoulli(q_D)``;
  * single-subsystem likelihood ``L_j(obs | x)`` per completed effective
    attempt: x=0 -> P(Y=0)=1-alpha_j, P(Y=1)=alpha_j; x=1 -> P(Y=0)=beta_j,
    P(Y=1)=1-beta_j.  Interrupted/cancelled/in-flight attempts contribute
    NO observation (not counted);
  * E is NOT an independent hidden subsystem: ``H = {at least one of
    x_A,x_B,x_C,x_D is a defect}``; ``L_E(obs_E | H nonempty)`` uses
    beta_E / 1-beta_E, ``L_E(obs_E | H empty)`` uses 1-alpha_E / alpha_E;
  * exact 16-state joint posterior ``P(x_A,x_B,x_C,x_D | obs)`` for devices
    that reached E (obs_E nonempty), exact Fractions, no float
    normalization;
  * exact 8-state ABC posterior (x_D integrated out) for devices NOT yet at
    E (obs_E empty; D is NOT prematurely materialized, no counterfactual D);
  * stratified resampling (frozen): first draw (x_A,x_B,x_C) from the
    x_D-integrated 8-state posterior using U_X_post; then draw x_D from
    ``P(x_D | obs, ABC)`` using U_D_post.  Frozen corollary: if H_ABC is
    already nonempty, E carries NO information about x_D
    (``P(x_D=1 | obs, ABC) = q_D``); only when ABC is all-clear does the E
    observation update D.

Device-level rules (frozen):
  * terminal devices: absorbed, never resampled;
  * not-yet-entered devices: A/B/C sampled from prior; D is NOT materialized
    now -- it is generated once from the prior q_D only when the
    continuation actually reaches the junction point;
  * devices not yet at E: no obs_E; A/B/C updated from their own
    observations; D unmaterialized in the real world is not written into
    ObservableState and is drawn from the prior at the junction;
  * devices at E: full 16-state posterior.

This module is a PURE function library over exact Fractions; the actual
U_X_post / U_D_post draws are provided by the caller (the h2 package never
imports the live DES engine / key schema -- C23 isolation).  Sampling
functions accept ``u`` directly and are deterministic.

Python 3.12, standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Optional

from main_model.h2.frozen_params_v1 import Q_ABC, Q_D, observation_kernel

# outcome vocabulary used by the posterior (frozen): "N" = normal (PASS),
# "A" = abnormal (ABNORMAL).  The mapping from the engine's observation
# history to this vocabulary happens at the PosteriorState boundary.
NORMAL = "N"
ABNORMAL = "A"


def single_likelihood(obs: tuple[str, ...], x: int,
                      alpha: Fraction, beta: Fraction) -> Fraction:
    """L_j(obs | x): product over completed effective attempts."""
    p = Fraction(1)
    for outcome in obs:
        if x == 0:
            p *= (Fraction(1) - alpha) if outcome == NORMAL else alpha
        else:
            p *= beta if outcome == NORMAL else (Fraction(1) - beta)
    return p


def e_likelihood(obs_e: tuple[str, ...], h_nonempty: bool,
                 alpha_e: Fraction, beta_e: Fraction) -> Fraction:
    """L_E(obs_E | H nonempty / H empty).  E observes only the event
    ``H = {x_A or x_B or x_C or x_D is a defect}``."""
    p = Fraction(1)
    for outcome in obs_e:
        if h_nonempty:
            p *= beta_e if outcome == NORMAL else (Fraction(1) - beta_e)
        else:
            p *= (Fraction(1) - alpha_e) if outcome == NORMAL else alpha_e
    return p


def _kernel() -> dict[str, dict[str, Fraction]]:
    return observation_kernel()


def abc_posterior_8(obs: dict[str, tuple[str, ...]],
                    obs_e: tuple[str, ...]) -> dict[tuple[int, int, int], Fraction]:
    """8-state posterior over (x_A, x_B, x_C) with x_D integrated out
    (frozen formula; exact Fractions, normalized).  Used for devices NOT
    yet at E AND as the first stage of the stratified sampler for devices
    at E.  The E likelihood is summed over x_D=0/1 (each weighted by its
    prior), which is the frozen marginalization."""
    kern = _kernel()
    weights: dict[tuple[int, int, int], Fraction] = {}
    for xa in (0, 1):
        for xb in (0, 1):
            for xc in (0, 1):
                w = Fraction(1)
                for proc, x in (("A", xa), ("B", xb), ("C", xc)):
                    w *= (Q_ABC[proc] if x else (Fraction(1) - Q_ABC[proc]))
                    w *= single_likelihood(obs.get(proc, ()), x,
                                           kern[proc]["alpha"],
                                           kern[proc]["beta"])
                h_abc = (xa or xb or xc) == 1
                # sum over x_D (prior-weighted E likelihood): x_D=1 always
                # makes H nonempty; x_D=0 keeps H = H_ABC
                le_d1 = e_likelihood(obs_e, True,
                                     kern["E"]["alpha"], kern["E"]["beta"])
                le_d0 = e_likelihood(obs_e, h_abc,
                                     kern["E"]["alpha"], kern["E"]["beta"])
                w *= (Q_D * le_d1 + (Fraction(1) - Q_D) * le_d0)
                weights[(xa, xb, xc)] = w
    total = sum(weights.values(), Fraction(0))
    if total == 0:
        raise ArithmeticError("zero-mass ABC posterior")
    return {key: value / total for key, value in weights.items()}


def joint_posterior_16(obs: dict[str, tuple[str, ...]],
                       obs_e: tuple[str, ...]) -> dict[tuple[int, int, int, int], Fraction]:
    """Exact 16-state joint posterior P(x_A,x_B,x_C,x_D | obs) (frozen
    formula; exact Fractions, normalized).  Devices that reached E
    (obs_E nonempty)."""
    kern = _kernel()
    weights: dict[tuple[int, int, int, int], Fraction] = {}
    for xa in (0, 1):
        for xb in (0, 1):
            for xc in (0, 1):
                for xd in (0, 1):
                    w = Fraction(1)
                    for proc, x in (("A", xa), ("B", xb), ("C", xc)):
                        w *= (Q_ABC[proc] if x else (Fraction(1) - Q_ABC[proc]))
                        w *= single_likelihood(obs.get(proc, ()), x,
                                               kern[proc]["alpha"],
                                               kern[proc]["beta"])
                    w *= (Q_D if xd else (Fraction(1) - Q_D))
                    h = (xa or xb or xc or xd) == 1
                    w *= e_likelihood(obs_e, h, kern["E"]["alpha"],
                                      kern["E"]["beta"])
                    weights[(xa, xb, xc, xd)] = w
    total = sum(weights.values(), Fraction(0))
    if total == 0:
        raise ArithmeticError("zero-mass joint posterior")
    return {key: value / total for key, value in weights.items()}


def marginal_abc(posterior_16: dict[tuple[int, int, int, int], Fraction]
                 ) -> dict[tuple[int, int, int], Fraction]:
    """Marginal ABC posterior from the 16-state joint (sum over x_D)."""
    out: dict[tuple[int, int, int], Fraction] = {}
    for (xa, xb, xc, _xd), p in posterior_16.items():
        key = (xa, xb, xc)
        out[key] = out.get(key, Fraction(0)) + p
    return out


def d_given_abc(obs_e: tuple[str, ...], abc: tuple[int, int, int]
                ) -> Fraction:
    """P(x_D=1 | obs, ABC) (frozen corollary).  If H_ABC is nonempty, the E
    likelihood is identical for x_D=0 and x_D=1, hence the posterior equals
    the prior q_D (E carries NO information about x_D); only when ABC is
    all-clear does the E observation update D."""
    kern = _kernel()
    h_abc = abc[0] or abc[1] or abc[2]
    le1 = e_likelihood(obs_e, h_abc or True, kern["E"]["alpha"],
                       kern["E"]["beta"])
    le0 = e_likelihood(obs_e, h_abc, kern["E"]["alpha"], kern["E"]["beta"])
    w1 = Q_D * le1
    w0 = (Fraction(1) - Q_D) * le0
    return w1 / (w1 + w0)


def sample_categorical(weights: dict[tuple, Fraction], u: Fraction) -> tuple:
    """Deterministic stratified draw from a normalized/unnormalized weight
    dict using u in [0,1): the smallest state whose cumulative weight
    strictly exceeds u (ties broken by deterministic state order)."""
    if not weights:
        raise ValueError("empty categorical")
    total = sum(weights.values(), Fraction(0))
    if total <= 0:
        raise ArithmeticError("non-positive mass")
    u = Fraction(u)
    acc = Fraction(0)
    for key in sorted(weights):
        acc += weights[key]
        if u < acc / total:
            return key
    # u == 1.0 or numerical tail: return the last state deterministically
    return sorted(weights)[-1]


def sample_abc(posterior_abc: dict[tuple[int, int, int], Fraction],
               u_x: Fraction) -> tuple[int, int, int]:
    """First stratified stage: draw (x_A, x_B, x_C) from the x_D-integrated
    8-state posterior using U_X_post."""
    return sample_categorical(posterior_abc, u_x)


def sample_d(obs_e: tuple[str, ...], abc: tuple[int, int, int],
             u_d: Fraction) -> int:
    """Second stratified stage: draw x_D from P(x_D | obs, ABC) using
    U_D_post."""
    p1 = d_given_abc(obs_e, abc)
    return 1 if u_d < p1 else 0


def sample_prior_abc_components(ua: Fraction, ub: Fraction,
                                uc: Fraction) -> tuple[int, int, int]:
    """Not-yet-entered device prior ABC draw: one U_X_post per subsystem."""
    return (1 if ua < Q_ABC["A"] else 0,
            1 if ub < Q_ABC["B"] else 0,
            1 if uc < Q_ABC["C"] else 0)


def prior_d(u_d: Fraction) -> int:
    """Prior x_D draw (used only at the continuation junction point)."""
    return 1 if u_d < Q_D else 0


@dataclass(frozen=True)
class DevicePosterior:
    """Per-device posterior information (distribution ONLY, never the true
    hidden state)."""
    device_id: int
    entered: bool
    terminal: bool            # absorbed; never resampled
    reached_e: bool           # obs_E nonempty -> full 16-state posterior
    abc_posterior: dict[tuple[int, int, int], Fraction]
    joint_posterior: Optional[dict[tuple[int, int, int, int], Fraction]]
    d_posterior_given_abc: Optional[dict[tuple[int, int, int], Fraction]]
