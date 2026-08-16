#!/usr/bin/env python3
"""Q3-H2-P3-A-E1 continuation-world rebuild from the safe projections
(SPEC sections 8/9/13/14/15, frozen; F3 repair).

STRICTLY forbidden: deepcopy of the live hidden DES world; reading
true_state / live lifetime / future U / live u_key.  The continuation
starting point is built ONLY from:
  * ObservableState (safe projection);
  * PosteriorState (P2 distribution objects -- the accepted posterior
    authority, SPEC section 8);
  * rollout post keys provided by the caller (per-device U_X_post /
    U_D_post and per-resource U_L_post derived from rollout_seed(dp, m)
    substreams in the h2_rollout domain by the external adapter).

F3 (P3-A-E1) repairs:
  * per-device draws: every entered / non-terminal device uses its OWN
    U_X_post(device) and (once at E) its OWN U_D_post(device); a single
    global u is never reused across devices; a missing required draw
    FAILS (raises), never silently defaults;
  * reached-E D posterior: after sampling ABC from the ABC posterior, the
    device's D draw uses PosteriorState.d_posterior_given_abc[ABC]
    directly (P(x_D=1 | obs, ABC)); we NEVER re-derive an E history from
    the raw log and NEVER call sample_d with an empty obs_e -- the
    E->D posterior information carried by the accepted PosteriorState is
    used as-is;
  * not-reached-E devices: x_D is NOT materialized in the initial world
    (x_d = None); D is drawn only at the future legal junction point by
    the continuation event engine (DEFERRED_TO_CONTINUATION_EVENT_ENGINE);
  * U_L_post: per-resource residual-lifetime draws are required; a missing
    resource draw FAILS (no Fraction(1,2) fallback).

Hidden defect state: sampled with the P2 posterior sampler (8-state ABC
posterior; x_D per the D posterior above).  Terminal devices are absorbed
(never resampled).  Future observations: U_Y_post is consumed ONLY on a
valid completion (caller-enforced; the h2 package never consumes keys
itself).

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
from main_model.h2.posterior_generator_v1 import sample_abc  # noqa: E402
from main_model.h2.lifetime_generator_v1 import (  # noqa: E402
    conditional_residual_frozen,
)

# Marker: D of not-reached-E devices is deferred to the continuation event
# engine (drawn once at the future legal junction point per prior q_D).
DEFERRED_TO_CONTINUATION_EVENT_ENGINE: str = "DEFERRED_TO_CONTINUATION_EVENT_ENGINE"


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
    x_d: Optional[int]          # None for not-reached-E (deferred)
    obs_e: tuple[str, ...]


@dataclass(frozen=True)
class ContinuationWorld:
    """One rebuilt continuation world from the safe projections + post
    keys.  Contains ONLY the sampled hidden state / lifetime needed to
    advance the continuation; never the live DES objects."""
    decision_time: Fraction
    devices: tuple[ContinuationDevice, ...]
    residual_lifetimes: dict[str, tuple[Optional[Fraction], bool]]


def _abc_posterior_dict(pv: ps.DevicePosteriorView) -> dict[tuple[int, int, int], Fraction]:
    return dict((tuple(k), Fraction(v)) for k, v in pv.abc_posterior)


def _d_given_abc_dict(pv: ps.DevicePosteriorView) -> dict[tuple[int, int, int], Fraction]:
    return dict((tuple(k), Fraction(v)) for k, v in pv.d_posterior_given_abc)


def rebuild_continuation_world(state: obs.ObservableState,
                               posterior: ps.PosteriorState,
                               u_x_by_device: dict[int, Fraction],
                               u_d_by_device: dict[int, Fraction],
                               u_l_by_resource: dict[str, Fraction]
                               ) -> ContinuationWorld:
    """Deterministically rebuild ONE continuation world at the decision
    time from the safe projections and the provided per-device /
    per-resource post draws (F3).

    Required draws (missing -> ValueError, never a silent default):
      * u_x_by_device[dev] for every entered / non-terminal device;
      * u_d_by_device[dev] for every entered / non-terminal device that
        reached E (x_D drawn from the D posterior); not-reached-E devices
        do NOT need a D draw (x_D deferred);
      * u_l_by_resource[r] for every resource in the ObservableState.

    Terminal devices are absorbed (no draws needed).
    """
    post_devices = {d.device_id: d for d in posterior.devices}
    devices: list[ContinuationDevice] = []
    for dev in state.devices:
        if dev.terminal_state is not None:
            devices.append(ContinuationDevice(
                device_id=dev.device_id, terminal=True, reached_e=False,
                x_abc=(0, 0, 0), x_d=None, obs_e=()))
            continue
        pv = post_devices.get(dev.device_id)
        if pv is None or not pv.entered:
            continue
        # F3: per-device independent U_X_post(device)
        try:
            u_x = u_x_by_device[dev.device_id]
        except KeyError:
            raise ValueError(
                f"missing per-device U_X_post for entered device "
                f"{dev.device_id} (fail-close, no default)") from None
        abc_post = _abc_posterior_dict(pv)
        abc = sample_abc(abc_post, u_x)
        if pv.reached_e:
            # F3: D draw uses the accepted PosteriorState D posterior
            # P(x_D=1 | obs, ABC) -- E->D posterior information preserved.
            try:
                u_d = u_d_by_device[dev.device_id]
            except KeyError:
                raise ValueError(
                    f"missing per-device U_D_post for reached-E device "
                    f"{dev.device_id} (fail-close, no default)") from None
            p_d = _d_given_abc_dict(pv)[abc]
            xd = 1 if u_d < p_d else 0
        else:
            xd = None  # DEFERRED_TO_CONTINUATION_EVENT_ENGINE
        devices.append(ContinuationDevice(
            device_id=dev.device_id, terminal=False,
            reached_e=pv.reached_e, x_abc=abc, x_d=xd,
            obs_e=tuple()))
    lifetimes: dict[str, tuple[Optional[Fraction], bool]] = {}
    for r in state.resources:
        try:
            u = u_l_by_resource[r.resource]
        except KeyError:
            raise ValueError(
                f"missing per-resource U_L_post for resource {r.resource} "
                f"(fail-close, no default)") from None
        lifetimes[r.resource] = conditional_residual_frozen(
            u, r.age_h, r.resource)
    return ContinuationWorld(decision_time=state.time,
                             devices=tuple(devices),
                             residual_lifetimes=lifetimes)
