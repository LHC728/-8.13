#!/usr/bin/env python3
"""Q3-H2-P3-A continuation-world rebuild from the safe projections
(SPEC sections 8/9/13/14/15, frozen).

STRICTLY forbidden: deepcopy of the live hidden DES world; reading
true_state / live lifetime / future U / live u_key.  The continuation
starting point is built ONLY from:
  * ObservableState (safe projection);
  * PosteriorState (P2 distribution objects);
  * rollout post keys (provided by the caller: U_X_post / U_D_post /
    U_L_post derived from rollout_seed(dp, m) substreams in the h2_rollout
    domain).

Hidden defect state: sampled with the P2 posterior sampler (8-state ABC
posterior, then x_D given ABC).  Terminal devices are absorbed (never
resampled).  Current-generation equipment residual lifetime: sampled with
the P2 conditional-lifetime generator.  Future observations: U_Y_post is
consumed ONLY on a valid completion (caller-enforced; the h2 package never
consumes keys itself).

TEMPORAL CAUSALITY: the continuation starts from the decision time t state
built from records <= t only; future terminal / observation / release /
failure / lifetime realizations never enter the initial state.

The module is a pure-function library over u values; it imports no live-DES
engine (C23 isolation).

Python 3.12, standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Optional

from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2.frozen_params_v1 import Q_ABC, Q_D  # noqa: E402
from main_model.h2.posterior_generator_v1 import (  # noqa: E402
    sample_abc, sample_d, sample_prior_abc_components,
)
from main_model.h2.lifetime_generator_v1 import (  # noqa: E402
    conditional_residual_frozen,
)


@dataclass(frozen=True)
class ContinuationDevice:
    """Rebuilt hidden state for one device in one continuation world
    (VALIDATION-ONLY diagnostic representation; carries the sampled x_* for
    the continuation engine -- this object is consumed by the continuation
    engine, never exposed to H2 policy through the firewalled interfaces)."""
    device_id: int
    terminal: bool
    reached_e: bool
    x_abc: tuple[int, int, int]
    x_d: Optional[int]
    obs_e: tuple[str, ...]


@dataclass(frozen=True)
class ContinuationWorld:
    """One rebuilt continuation world from the safe projections + post
    keys.  Contains ONLY the sampled hidden state / lifetime needed to
    advance the continuation; never the live DES objects."""
    decision_time: Fraction
    devices: tuple[ContinuationDevice, ...]
    residual_lifetimes: dict[str, tuple[Optional[Fraction], bool]]


def rebuild_continuation_world(state: obs.ObservableState,
                               posterior: ps.PosteriorState,
                               u_x_abc: Fraction, u_d: Fraction,
                               u_l: dict[str, Fraction]
                               ) -> ContinuationWorld:
    """Deterministically rebuild ONE continuation world at the decision
    time from the safe projections and the provided post draws.  Terminal
    devices are absorbed; not-yet-entered devices are NOT resampled here
    (they enter later from the prior; D is drawn only at the junction);
    devices with observations use the posterior sampler."""
    devices: list[ContinuationDevice] = []
    post_devices = {d.device_id: d for d in posterior.devices}
    for dev in state.devices:
        if dev.terminal_state is not None:
            devices.append(ContinuationDevice(
                device_id=dev.device_id, terminal=True, reached_e=False,
                x_abc=(0, 0, 0), x_d=None, obs_e=()))
            continue
        pv = post_devices.get(dev.device_id)
        if pv is None or not pv.entered:
            continue
        abc_post = dict((tuple(k), Fraction(v))
                        for k, v in pv.abc_posterior)
        abc = sample_abc(abc_post, u_x_abc)
        obs_e = tuple()
        if pv.reached_e:
            d_given = dict((tuple(k), Fraction(v))
                           for k, v in pv.d_posterior_given_abc)
            obs_e = tuple()
        xd = sample_d(obs_e if pv.reached_e else (), abc, u_d)
        devices.append(ContinuationDevice(
            device_id=dev.device_id, terminal=False,
            reached_e=pv.reached_e, x_abc=abc, x_d=xd if pv.reached_e else None,
            obs_e=obs_e))
    lifetimes = {}
    for r in state.resources:
        u = u_l.get(r.resource, Fraction(1, 2))
        lifetimes[r.resource] = conditional_residual_frozen(
            u, r.age_h, r.resource)
    return ContinuationWorld(decision_time=state.time,
                             devices=tuple(devices),
                             residual_lifetimes=lifetimes)
