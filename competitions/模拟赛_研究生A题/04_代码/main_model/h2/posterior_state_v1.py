#!/usr/bin/env python3
"""Q3-H2-P2 PosteriorState: the H2-facing posterior / lifetime boundary.

Frozen authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED
sections 7 (``PosteriorState`` = observable projection + posterior object),
8 (posterior defect-state resampling) and 9 (conditional residual lifetime).

P2 contract (frozen):
  * PosteriorState is IMMUTABLE and DETERMINISTIC;
  * it is constructed ONLY from an ObservableState (the safe projection)
    plus frozen parameters -- it NEVER receives raw DES / event log /
    DeviceState / EquipmentState / true_state / lifetime / u / u_key;
  * it stores DISTRIBUTION / posterior information, never the hidden true
    answer (no x_* values, no live lifetime, no u);
  * per-device: exact 8-state ABC posterior (x_D integrated out; D not
    prematurely materialized) for devices not yet at E, and the exact
    16-state joint posterior for devices at E (obs_E nonempty); terminal
    devices are absorbed (never resampled);
  * per-resource: current-generation conditional-survival information
    (age, generation, p_max) for the residual-lifetime generator.

Python 3.12, standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Optional

from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2.frozen_params_v1 import F120, F240
from main_model.h2.posterior_generator_v1 import (  # noqa: E402
    ABNORMAL, NORMAL, abc_posterior_8, d_given_abc, joint_posterior_16,
    marginal_abc,
)
from main_model.h2.lifetime_generator_v1 import p_max  # noqa: E402

# P1 seam marker is superseded by the formal P2 schema.
P1_SEAM_STATUS: str = "SCHEMA_IMPLEMENTED_IN_P2"


def _to_vocabulary(outcome: str) -> str:
    """Engine outcome vocabulary -> posterior vocabulary (PASS -> N,
    ABNORMAL -> A)."""
    if outcome == "PASS":
        return NORMAL
    if outcome == "ABNORMAL":
        return ABNORMAL
    raise ValueError(f"unexpected observation outcome {outcome!r}")


def _observations_by_process(
        device: obs.DeviceObs) -> dict[str, tuple[str, ...]]:
    """Completed materialized observation history per process, in
    chronological attempt order (interrupted/cancelled/in-flight attempts
    never appear in ObservableState.observations, so only completed
    effective attempts are used -- frozen section 8)."""
    out: dict[str, list[str]] = {}
    for o in device.observations:
        out.setdefault(o.process, []).append(_to_vocabulary(o.outcome))
    return {p: tuple(v) for p, v in out.items()}


@dataclass(frozen=True)
class DevicePosteriorView:
    """Per-device posterior distribution information (no hidden truth)."""
    device_id: int
    entered: bool
    terminal: bool              # absorbed; never resampled
    reached_e: bool             # obs_E nonempty -> full 16-state posterior
    abc_posterior: tuple[tuple[tuple[int, int, int], str], ...]
    joint_posterior: Optional[tuple[tuple[tuple[int, int, int, int], str], ...]]
    d_posterior_given_abc: tuple[tuple[tuple[int, int, int], str], ...]


@dataclass(frozen=True)
class ResourceLifetimeView:
    """Per-resource current-generation conditional-survival information."""
    resource: str
    generation: int
    age_h: Fraction
    p_max: Fraction


@dataclass(frozen=True)
class PosteriorState:
    """Immutable H2-facing posterior object: distribution information
    computed from an ObservableState + frozen parameters ONLY."""
    time: Fraction
    devices: tuple[DevicePosteriorView, ...]
    resources: tuple[ResourceLifetimeView, ...]

    @classmethod
    def from_observable(cls, state: obs.ObservableState) -> "PosteriorState":
        """Build the posterior from the safe projection ONLY.  Never
        touches raw logs / engine / hidden state."""
        device_views: list[DevicePosteriorView] = []
        for dev in state.devices:
            history = _observations_by_process(dev)
            obs_e = history.get("E", ())
            reached_e = len(obs_e) > 0
            if reached_e:
                joint = joint_posterior_16(history, obs_e)
                abc = marginal_abc(joint)
            else:
                abc = abc_posterior_8(history, ())
                joint = None
            d_given: dict[tuple[int, int, int], Fraction] = {}
            for key in abc:
                d_given[key] = d_given_abc(obs_e, key)
            device_views.append(DevicePosteriorView(
                device_id=dev.device_id, entered=True,
                terminal=dev.terminal_state is not None,
                reached_e=reached_e,
                abc_posterior=tuple(
                    (key, str(value)) for key, value in
                    sorted(abc.items())),
                joint_posterior=(None if joint is None else tuple(
                    (key, str(value)) for key, value in
                    sorted(joint.items()))),
                d_posterior_given_abc=tuple(
                    (key, str(value)) for key, value in
                    sorted(d_given.items())),
            ))
        resource_views = []
        for r in state.resources:
            f120 = F120[r.resource]
            f240 = F240[r.resource]
            resource_views.append(ResourceLifetimeView(
                resource=r.resource, generation=r.generation,
                age_h=r.age_h, p_max=p_max(r.age_h, f120, f240)))
        return cls(time=state.time, devices=tuple(device_views),
                   resources=tuple(resource_views))
