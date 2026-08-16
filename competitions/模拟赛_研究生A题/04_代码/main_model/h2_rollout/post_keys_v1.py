#!/usr/bin/env python3
"""Q3-H2-P3-A-E1 rollout post-key adapter (SPEC section 6.2, frozen).

Closes ``rollout_seed(dp, m) -> h2_rollout post draws`` WITHOUT touching the
P1 import firewall: this module lives OUTSIDE ``main_model/h2`` (a sibling
``main_model/h2_rollout`` package), so importing the accepted P0/P2
``key_schema_v1`` (g3) is allowed here while ``main_model/h2`` stays
engine-free.

Adapter contract (frozen):
  * seed = rollout_seed(master_seed_h2, replicate_id, dp, m)  (SPEC 6.2);
  * namespace = h2_rollout;
  * per entity (device): U_X_post (per subsystem slot, canonical "A" slot
    used for the single ABC-posterior categorical draw, mirroring the
    accepted P2 smoke) and U_D_post;
  * per resource: U_L_post (generation slot);
  * U_Y_post interface (attempt slot) is DEFINED here but NEVER consumed in
    this package (a valid completion consumes it, caller-enforced);
  * CRN: the same (dp, m, entity) across ALL candidate actions yields
    EXACT IDENTICAL post draws (the seed contains no action / policy /
    strategy / run_id / worker); different dp or different m separate the
    streams;
  * the P2 generator-validation synthetic entity/generation mapping
    (100001 + ...) is NEVER used here: production rollout keys use the real
    device ids / resources / generations passed in.

Pure stdlib (hashlib + the accepted key_schema / rollout_seed).

Python 3.12, standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Optional

from main_model.g3 import key_schema_v1 as ks  # noqa: E402
from main_model.h2.rollout_seed_v1 import rollout_seed  # noqa: E402

ROLLOUT_NAMESPACE: str = ks.NAMESPACE_H2_ROLLOUT
# canonical slot for the single ABC-posterior categorical draw (accepted P2
# smoke used subsystem "A" for that one draw; frozen slot semantics §6.2).
ABC_CATEGORICAL_SUBSYSTEM: str = "A"


@dataclass(frozen=True)
class RolloutPostKeys:
    """Deterministic post-key bundle for one (dp, m) continuation world."""
    master_seed_h2: int
    replicate_id: int
    dp: int
    m: int
    seed: int
    namespace: str
    u_x_by_device: dict[int, Fraction] = field(default_factory=dict)
    u_d_by_device: dict[int, Fraction] = field(default_factory=dict)
    u_l_by_resource: dict[str, Fraction] = field(default_factory=dict)
    # U_Y_post interface (attempt slot); consumed ONLY on a valid completion
    # by the continuation event engine (not in this package).
    u_y_lookup: Optional[Callable[[int, str, int], Fraction]] = None

    def u_y(self, device: int, process: str, attempt: int) -> Fraction:
        if self.u_y_lookup is None:
            raise ValueError("U_Y_post interface not bound")
        return self.u_y_lookup(device, process, attempt)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "master_seed_h2": self.master_seed_h2,
            "replicate_id": self.replicate_id,
            "dp": self.dp,
            "m": self.m,
            "seed": self.seed,
            "namespace": self.namespace,
            "u_x_by_device": {str(k): str(v)
                              for k, v in sorted(self.u_x_by_device.items())},
            "u_d_by_device": {str(k): str(v)
                              for k, v in sorted(self.u_d_by_device.items())},
            "u_l_by_resource": {k: str(v)
                                for k, v in sorted(self.u_l_by_resource.items())},
            "u_y_interface": "defined; never consumed in this package",
        }


def rollout_post_keys(master_seed_h2: int, replicate_id: int, dp: int, m: int,
                      devices: tuple[int, ...],
                      resources: tuple[str, ...],
                      generations: dict[str, int]) -> RolloutPostKeys:
    """Derive the h2_rollout post-key bundle for one (dp, m) world.

    CRN: the returned bundle depends ONLY on (master_seed_h2, replicate_id,
    dp, m) and the entity/resource keys -- never on an action / policy /
    run_id -- so all candidate actions of the same decision point share the
    same m-world draws (frozen CRN rule, SPEC 6.2).
    """
    seed = rollout_seed(master_seed_h2, replicate_id, dp, m)
    u_x: dict[int, Fraction] = {}
    u_d: dict[int, Fraction] = {}
    for dev in devices:
        u_x[dev] = ks.u_x_post(ROLLOUT_NAMESPACE, replicate_id, dev,
                               ABC_CATEGORICAL_SUBSYSTEM, seed)
        u_d[dev] = ks.u_d_post(ROLLOUT_NAMESPACE, replicate_id, dev, seed)
    u_l: dict[str, Fraction] = {}
    for r in resources:
        gen = generations[r]
        u_l[r] = ks.u_l_post(ROLLOUT_NAMESPACE, replicate_id, r, gen, seed)

    def _u_y(device: int, process: str, attempt: int) -> Fraction:
        return ks.u_y_post(ROLLOUT_NAMESPACE, replicate_id, device, process,
                           attempt, seed)

    return RolloutPostKeys(
        master_seed_h2=master_seed_h2, replicate_id=replicate_id, dp=dp, m=m,
        seed=seed, namespace=ROLLOUT_NAMESPACE,
        u_x_by_device=u_x, u_d_by_device=u_d, u_l_by_resource=u_l,
        u_y_lookup=_u_y)
