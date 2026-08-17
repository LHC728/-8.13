"""G3 key_schema_v1: canonical keyed uniform random infrastructure.

Frozen contract: G3-SPEC-V1.0 section 3 (random_key_architecture) and
V3.1 section 8 (keyed underlying random band). This module implements ONLY
the key schema: canonical-key serialization and the SHA256-based uniform
mapping. It performs no sampling, no CDF inversion and no policy logic; the
legality of a consumption event (which event may consume which U) is the
caller's responsibility (S3 DES integration) and is documented below.

Canonical key (frozen field order; NOTE-3: namespace precedes replicate_id)::

    key_schema_v1 | master_seed | namespace | replicate_id | entity_id
                  | process_or_subsystem | attempt_or_generation

Mapping (frozen; exact rational; binary float is forbidden in the canonical
U)::

    U = (uint64_be(SHA256(UTF8(canonical_key))[0:8]) + 1/2) / 2^64
      = (2 * uint64_be(SHA256(UTF8(canonical_key))[0:8]) + 1) / 2^65

``uniform_from_key`` returns a ``fractions.Fraction`` with denominator 2^65,
i.e. always in (0, 1), a subset of the required [0, 1).

Serialization: every field is normalized to UTF-8 with an explicit type tag
(``i:<decimal>`` for integers, ``s:<value>`` for strings), joined by the
literal separator ``|``; the leading key_schema_version literal is untagged.
Optional slots (process_or_subsystem for U_X/U_D/U_L, attempt_or_generation
for U_X/U_D) serialize as empty segments. The runtime builtin ``hash()`` is
never used; only ``hashlib.sha256``.

Five logical streams (frozen; H2 reserved only)::

    U_X  (namespace, replicate_id, device_id, subsystem)   subsystem in {A,B,C}
    U_D  (namespace, replicate_id, device_id)              dedicated stream
    U_Y  (namespace, replicate_id, device_id, process, effective_attempt_no)
    U_L  (namespace, replicate_id, resource, generation_no)
    H2   reserved only; not implemented; stream helpers reject the namespace.

Six disjoint experiment namespaces (frozen): development_unit / pilot /
h1_tuning / g3_holdout / q2_formal / q3_formal, plus the H2 reserved
placeholder namespace. G3-SPEC-V1.0 freezes the H2 stream as reserved only
and does not fix its literal; this module chooses ``h2_future``.

Consumption-side API semantics (enforced by the caller, not here): an
observation U must be consumed only by a valid completion; no observation U
is consumed by failure interruption, terminal cancellation, shift deferral or
never-started tasks (see NO_OBSERVATION_CONSUMED_BY); U_D is consumed only at
a legal D materialization; U_L is consumed exactly once per (resource,
generation).

P0 extension (Q3/H2 BOOTSTRAP SPEC section 6.1 / D-05, 2026-08-15): three
formal H2 namespaces (h2_tuning / h2_holdout / h2_rollout) and four H2 post
streams (U_X_post / U_D_post / U_Y_post / U_L_post) are added additively.
The frozen legacy constants, serializer field order, hashing and Fraction
mapping are untouched. Namespace consumption is gated by an explicit
firewall: legacy physical helpers consume the legacy six experiment
namespaces plus the Human-Gate-authorized additive Q4 namespaces
(q4_screening / q4_evaluation, HG-Q4-NS-01); H2 post helpers consume only
the three H2 namespaces;
h2_future stays a reserved-only historical placeholder. rollout_seed(dp,m)
and rollout substream derivation are NOT implemented here (later rollout
layer; P0 lays namespace + post-stream infrastructure only).

Main-model dependency limit: Python standard library only (no third-party
imports), per G3-SPEC-V1.0.
"""

from __future__ import annotations

import hashlib
from fractions import Fraction

# ---------------------------------------------------------------------------
# Frozen constants (G3-SPEC-V1.0 section 3)
# ---------------------------------------------------------------------------

KEY_SCHEMA_VERSION: str = "key_schema_v1"

# Frozen canonical field order (NOTE-3: namespace precedes replicate_id).
CANONICAL_KEY_FIELD_ORDER: tuple[str, ...] = (
    "key_schema_version",
    "master_seed",
    "namespace",
    "replicate_id",
    "entity_id",
    "process_or_subsystem",
    "attempt_or_generation",
)

# Frozen mapping, written with 1/2 so the module source stays free of binary
# float literals; equivalent to (uint64_be(...) + one half) / 2^64.
MAPPING_DESCRIPTION: str = (
    "U = (uint64_be(SHA256(UTF8(canonical_key))[0:8]) + 1/2) / 2^64; "
    "exact Fraction with denominator 2^65; binary float forbidden"
)

NAMESPACE_DEVELOPMENT_UNIT: str = "development_unit"
NAMESPACE_PILOT: str = "pilot"
NAMESPACE_H1_TUNING: str = "h1_tuning"
NAMESPACE_G3_HOLDOUT: str = "g3_holdout"
NAMESPACE_Q2_FORMAL: str = "q2_formal"
NAMESPACE_Q3_FORMAL: str = "q3_formal"

# Six disjoint experiment namespaces (frozen).
NAMESPACES: tuple[str, ...] = (
    NAMESPACE_DEVELOPMENT_UNIT,
    NAMESPACE_PILOT,
    NAMESPACE_H1_TUNING,
    NAMESPACE_G3_HOLDOUT,
    NAMESPACE_Q2_FORMAL,
    NAMESPACE_Q3_FORMAL,
)

# H2 future stream: reserved only (namespace placeholder); G3 does not
# implement H2. The literal is not fixed by the spec; chosen here to mirror
# the frozen stream name H2_future_stream.
H2_RESERVED_NAMESPACE: str = "h2_future"
ALL_NAMESPACES: tuple[str, ...] = NAMESPACES + (H2_RESERVED_NAMESPACE,)

# ---------------------------------------------------------------------------
# P0: H2 key domain extension (Q3/H2 BOOTSTRAP SPEC section 6.1 / D-05,
# 2026-08-15 Human Gate DESIGN FREEZE APPROVED). Purely additive: the frozen
# legacy constants above (NAMESPACES / ALL_NAMESPACES / H2_RESERVED_NAMESPACE)
# are left byte-identical so every legacy canonical key is unchanged.
# ---------------------------------------------------------------------------

# Three formal H2 experiment namespaces (frozen literals).
NAMESPACE_H2_TUNING: str = "h2_tuning"
NAMESPACE_H2_HOLDOUT: str = "h2_holdout"
NAMESPACE_H2_ROLLOUT: str = "h2_rollout"
H2_NAMESPACES: tuple[str, ...] = (
    NAMESPACE_H2_TUNING,
    NAMESPACE_H2_HOLDOUT,
    NAMESPACE_H2_ROLLOUT,
)

# H2 posterior / random-resampling streams (frozen names; exactly four, no
# renaming, no fifth stream, no merging).
H2_POST_STREAMS: tuple[str, ...] = ("U_X_post", "U_D_post", "U_Y_post", "U_L_post")

# ---------------------------------------------------------------------------
# Q4 additive random-domain extension (HG-Q4-NS-01, 2026-08-17 OPTION A /
# ACCEPTED). Purely additive: the frozen legacy constants above (NAMESPACES /
# ALL_NAMESPACES / H2_RESERVED_NAMESPACE) and the P0 H2 constants stay
# byte-identical, so every legacy canonical key is unchanged. The two Q4
# logical domains map to two independent physical namespaces; both share the
# same master_seed with Q2/Q3-style real-state / observation / equipment
# lifetime physical DES streams, and the namespace is part of the canonical
# key so q4_screening and q4_evaluation are physically separated.
# ---------------------------------------------------------------------------

NAMESPACE_Q4_SCREENING: str = "q4_screening"
NAMESPACE_Q4_EVALUATION: str = "q4_evaluation"
Q4_NAMESPACES: tuple[str, ...] = (
    NAMESPACE_Q4_SCREENING,
    NAMESPACE_Q4_EVALUATION,
)

# Physical experiment namespace universe = legacy six frozen namespaces +
# Human-Gate-authorized additive Q4 namespaces (additive; legacy six remain
# frozen and unchanged).
PHYSICAL_EXPERIMENT_NAMESPACES: tuple[str, ...] = NAMESPACES + Q4_NAMESPACES

# Serializer-visible universe = frozen public constants + formal H2
# namespaces + additive Q4 namespaces. canonical_key serializes any
# registered namespace; consumption is gated per family by the stream
# helpers (namespace firewall). Private: not exported, public legacy
# constants stay untouched.
_SERIALIZABLE_NAMESPACES: tuple[str, ...] = (
    ALL_NAMESPACES + H2_NAMESPACES + Q4_NAMESPACES
)

# U_X true-state subsystems (frozen: subsystem explicitly A/B/C). E has no
# independent true-state draw; its distribution is derived from A/B/C/D.
SUBSYSTEMS: tuple[str, ...] = ("A", "B", "C")

# U_Y processes and U_L resources (frozen upstream: A/B/C/E).
PROCESSES: tuple[str, ...] = ("A", "B", "C", "E")

# Forbidden physical key fields: never enter a canonical U key (frozen).
FORBIDDEN_PHYSICAL_KEY_FIELDS: tuple[str, ...] = (
    "run_id",
    "execution_no",
    "restart_no",
    "wall-clock timestamp",
    "container iteration order",
    "event insertion order",
    "strategy_id",
    "policy_id",
    "squad_id",
    "worker_id",
    "agent_id",
)

# Events that must never consume an observation U (caller-enforced).
NO_OBSERVATION_CONSUMED_BY: tuple[str, ...] = (
    "failure interruption",
    "terminal cancellation",
    "shift deferral",
    "never-started task",
)

_FIELD_SEPARATOR: str = "|"

__all__ = [
    "KEY_SCHEMA_VERSION",
    "CANONICAL_KEY_FIELD_ORDER",
    "MAPPING_DESCRIPTION",
    "NAMESPACE_DEVELOPMENT_UNIT",
    "NAMESPACE_PILOT",
    "NAMESPACE_H1_TUNING",
    "NAMESPACE_G3_HOLDOUT",
    "NAMESPACE_Q2_FORMAL",
    "NAMESPACE_Q3_FORMAL",
    "NAMESPACES",
    "H2_RESERVED_NAMESPACE",
    "ALL_NAMESPACES",
    "NAMESPACE_H2_TUNING",
    "NAMESPACE_H2_HOLDOUT",
    "NAMESPACE_H2_ROLLOUT",
    "H2_NAMESPACES",
    "H2_POST_STREAMS",
    "NAMESPACE_Q4_SCREENING",
    "NAMESPACE_Q4_EVALUATION",
    "Q4_NAMESPACES",
    "PHYSICAL_EXPERIMENT_NAMESPACES",
    "SUBSYSTEMS",
    "PROCESSES",
    "FORBIDDEN_PHYSICAL_KEY_FIELDS",
    "NO_OBSERVATION_CONSUMED_BY",
    "canonical_key",
    "uniform_from_key",
    "u_x",
    "u_d",
    "u_y",
    "u_l",
    "u_x_post",
    "u_d_post",
    "u_y_post",
    "u_l_post",
]


# ---------------------------------------------------------------------------
# Field serialization (explicit types, fixed UTF-8 normalization)
# ---------------------------------------------------------------------------


def _require_non_negative_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative int, got {value!r}")
    return value


def _require_positive_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < 1:
        raise ValueError(f"{name} must be a positive int (>= 1), got {value!r}")
    return value


def _reject_forbidden_token(value: str, name: str) -> None:
    if value in FORBIDDEN_PHYSICAL_KEY_FIELDS:
        raise ValueError(
            f"{name}={value!r} is a forbidden physical key field "
            f"(run_id/execution_no/restart_no/timestamp/iteration order/"
            f"insertion order/strategy_id/policy_id/squad_id/worker_id/"
            f"agent_id); it must never enter a canonical U key"
        )


def _require_non_empty_string(value, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str, got {type(value).__name__}")
    if value == "":
        raise ValueError(f"{name} must be a non-empty string")
    if _FIELD_SEPARATOR in value:
        raise ValueError(
            f"{name} must not contain the field separator {_FIELD_SEPARATOR!r}"
        )
    _reject_forbidden_token(value, name)
    return value


def _serialize_entity(entity_id) -> str:
    """Serialize the entity slot with an explicit type tag.

    Device ids are ints (1-based in the frozen model); U_L resources are
    strings ("A"/"B"/"C"/"E"). The tag makes the type explicit so entity 7
    and entity "7" are distinct canonical keys.
    """
    if isinstance(entity_id, bool):
        raise TypeError("entity_id must be a str or an int, got bool")
    if isinstance(entity_id, int):
        _require_positive_int(entity_id, "entity_id")
        return f"i:{entity_id}"
    return "s:" + _require_non_empty_string(entity_id, "entity_id")


def _serialize_optional_string(value, name: str) -> str:
    if value is None:
        return ""
    return "s:" + _require_non_empty_string(value, name)


def _serialize_optional_positive_int(value, name: str) -> str:
    if value is None:
        return ""
    return "i:" + str(_require_positive_int(value, name))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def canonical_key(
    namespace,
    replicate_id,
    entity_id,
    process_or_subsystem,
    attempt_or_generation,
    master_seed,
) -> str:
    """Build the normalized UTF-8 canonical key string.

    Frozen field order (G3-SPEC-V1.0 section 3)::

        key_schema_v1 | master_seed | namespace | replicate_id | entity_id
                      | process_or_subsystem | attempt_or_generation

    ``namespace`` must be one of the registered namespaces: the six frozen
    experiment namespaces, the H2 reserved placeholder ``h2_future``, the
    three formal H2 namespaces (``h2_tuning``/``h2_holdout``/``h2_rollout``),
    or the Human-Gate-authorized additive Q4 namespaces (``q4_screening`` /
    ``q4_evaluation``).
    Serialization accepts any registered namespace (pure serializer);
    consumption is gated per family by the stream helpers (namespace
    firewall: legacy physical helpers consume the legacy six + additive Q4
    namespaces; H2 post helpers only consume the three H2 namespaces).
    ``master_seed``/``replicate_id`` are non-negative ints;
    ``entity_id`` is a str or a positive int; ``process_or_subsystem`` is a
    non-empty str or None (empty slot); ``attempt_or_generation`` is a
    positive int or None (empty slot). Fields are normalized to UTF-8 with
    explicit type tags; the same logical content always serializes to the
    same string regardless of argument-passing order.

    Forbidden physical key fields (run_id, execution_no, restart_no,
    wall-clock timestamp, container iteration order, event insertion order,
    strategy_id, policy_id, squad_id, worker_id, agent_id) are not accepted
    by this API and are rejected if injected through a string slot.
    """
    if namespace not in _SERIALIZABLE_NAMESPACES:
        raise ValueError(
            f"unknown namespace {namespace!r}; allowed: "
            f"{', '.join(_SERIALIZABLE_NAMESPACES)}"
        )
    seed = _require_non_negative_int(master_seed, "master_seed")
    rep = _require_non_negative_int(replicate_id, "replicate_id")
    ent = _serialize_entity(entity_id)
    proc = _serialize_optional_string(process_or_subsystem, "process_or_subsystem")
    att = _serialize_optional_positive_int(
        attempt_or_generation, "attempt_or_generation"
    )
    return _FIELD_SEPARATOR.join(
        (KEY_SCHEMA_VERSION, f"i:{seed}", f"s:{namespace}", f"i:{rep}", ent, proc, att)
    )


def uniform_from_key(canonical_key: str) -> Fraction:
    """Map a canonical key to the exact uniform U in [0, 1).

    Frozen mapping::

        U = (uint64_be(SHA256(UTF8(canonical_key))[0:8]) + 1/2) / 2^64
          = (2 * uint64_be(SHA256(UTF8(canonical_key))[0:8]) + 1) / 2^65

    Returns a ``fractions.Fraction`` (never a binary float); U is always in
    (0, 1), a subset of [0, 1). ``canonical_key`` must be a str produced by
    :func:`canonical_key` (a wrong-schema key is rejected).
    """
    if not isinstance(canonical_key, str):
        raise TypeError("canonical_key must be a str")
    if not canonical_key.startswith(KEY_SCHEMA_VERSION + _FIELD_SEPARATOR):
        raise ValueError(
            "canonical_key must start with the key_schema_v1 version prefix; "
            "build keys with canonical_key()"
        )
    digest = hashlib.sha256(canonical_key.encode("utf-8")).digest()
    head = int.from_bytes(digest[:8], byteorder="big")  # uint64 big-endian
    return Fraction(2 * head + 1, 1 << 65)


def _require_legacy_namespace(namespace) -> None:
    """Namespace firewall (P0 + HG-Q4-NS-01): legacy physical stream helpers
    (``u_x`` / ``u_d`` / ``u_y`` / ``u_l``) may consume the six frozen
    experiment namespaces plus the Human-Gate-authorized additive Q4
    namespaces (``q4_screening`` / ``q4_evaluation``).

    The formal H2 namespaces (``h2_tuning``/``h2_holdout``/``h2_rollout``)
    are reserved for the H2 post streams, and ``h2_future`` remains a
    reserved-only placeholder; legacy physical helpers must never consume
    them (in particular legacy helper + ``h2_rollout`` is always rejected).
    """
    if namespace not in PHYSICAL_EXPERIMENT_NAMESPACES:
        raise ValueError(
            "legacy physical stream may only be consumed under the legacy "
            f"six frozen experiment namespaces {', '.join(NAMESPACES)} plus "
            f"the Human-Gate-authorized additive Q4 namespaces "
            f"{', '.join(Q4_NAMESPACES)}; H2 namespaces "
            f"{', '.join(H2_NAMESPACES)} are reserved for H2 post streams, and "
            f"the placeholder {H2_RESERVED_NAMESPACE!r} is reserved only"
        )


def _require_h2_namespace(namespace) -> None:
    """Namespace firewall (P0): H2 post stream helpers (``u_x_post`` /
    ``u_d_post`` / ``u_y_post`` / ``u_l_post``) may only consume the three
    formal H2 namespaces.

    Legacy experiment namespaces are physical domains and ``h2_future`` is
    reserved only; H2 post streams must never consume them, so H2 helpers
    cannot pollute the legacy random worlds.
    """
    if namespace not in H2_NAMESPACES:
        raise ValueError(
            "H2 post stream may only be consumed under the H2 namespaces "
            f"{', '.join(H2_NAMESPACES)}; legacy experiment namespaces "
            f"{', '.join(NAMESPACES)} are legacy physical domains, and the "
            f"placeholder {H2_RESERVED_NAMESPACE!r} is reserved only"
        )


def u_x(namespace, rep, device, subsystem, seed) -> Fraction:
    """U_X device true-state stream: (namespace, replicate_id, device_id,
    subsystem) with subsystem explicitly in {A, B, C}.

    Consumed once per device entry for each true-state subsystem; the
    subsystem is explicit so A/B/C slots are distinct. Never merged with the
    U_D slot (U_D is a dedicated stream). Legacy physical stream: the legacy
    six frozen experiment namespaces plus the additive Q4 namespaces are
    consumable (firewall).
    """
    _require_legacy_namespace(namespace)
    if subsystem not in SUBSYSTEMS:
        raise ValueError(
            f"U_X subsystem must be one of {SUBSYSTEMS}, got {subsystem!r}"
        )
    key = canonical_key(namespace, rep, device, subsystem, None, seed)
    return uniform_from_key(key)


def u_d(namespace, rep, device, seed) -> Fraction:
    """U_D D-materialization stream: (namespace, replicate_id, device_id).

    Dedicated stream; consume only at a legal D materialization (A/B/C all
    PASS while the device is still pending). Never merged into the A/B/C
    slots of U_X. Legacy physical stream: the legacy six frozen experiment
    namespaces plus the additive Q4 namespaces are consumable (firewall).
    """
    _require_legacy_namespace(namespace)
    key = canonical_key(namespace, rep, device, None, None, seed)
    return uniform_from_key(key)


def u_y(namespace, rep, device, process, attempt, seed) -> Fraction:
    """U_Y observation stream: (namespace, replicate_id, device_id, process,
    effective_attempt_no).

    Consume only on a valid completion; failure interruption, terminal
    cancellation, shift deferral and never-started tasks consume no U (the
    caller enforces this). ``process`` must be one of {A, B, C, E} and
    ``attempt`` a positive effective attempt number. Legacy physical stream:
    only the legacy six frozen experiment namespaces plus the additive Q4
    namespaces are consumable (firewall).
    """
    _require_legacy_namespace(namespace)
    if process not in PROCESSES:
        raise ValueError(
            f"U_Y process must be one of {PROCESSES}, got {process!r}"
        )
    key = canonical_key(namespace, rep, device, process, attempt, seed)
    return uniform_from_key(key)


def u_l(namespace, rep, resource, generation, seed) -> Fraction:
    """U_L equipment-lifetime stream: (namespace, replicate_id, resource,
    generation_no).

    Exactly one U_L per (resource, generation): the pair fully determines the
    key, so repeated draws with the same pair reuse the same U. ``resource``
    must be one of {A, B, C, E}; ``generation`` a positive generation number.
    Legacy physical stream: the legacy six frozen experiment namespaces
    plus the additive Q4 namespaces are consumable (firewall).
    consumable (firewall).
    """
    _require_legacy_namespace(namespace)
    if resource not in PROCESSES:
        raise ValueError(
            f"U_L resource must be one of {PROCESSES}, got {resource!r}"
        )
    key = canonical_key(namespace, rep, resource, None, generation, seed)
    return uniform_from_key(key)


# ---------------------------------------------------------------------------
# P0: H2 posterior / random-resampling streams (Q3/H2 BOOTSTRAP SPEC section
# 6.1 / D-05). Four post streams, same canonical slot patterns as their
# legacy counterparts, but only consumable under the three formal H2
# namespaces (namespace firewall). No rollout_seed(dp,m) / rollout substream
# derivation here: that belongs to a later rollout layer (P0 scope note).
# ---------------------------------------------------------------------------


def u_x_post(namespace, rep, device, subsystem, seed) -> Fraction:
    """U_X_post: H2 posterior defect-state resampling stream (SPEC 6.1).

    Same canonical slot pattern as U_X (namespace, replicate_id, device_id,
    subsystem); consumed only under h2_tuning / h2_holdout / h2_rollout.
    The legacy ``u_x`` never consumes H2 namespaces (firewall), so post and
    physical identities cannot collide.
    """
    _require_h2_namespace(namespace)
    if subsystem not in SUBSYSTEMS:
        raise ValueError(
            f"U_X_post subsystem must be one of {SUBSYSTEMS}, got {subsystem!r}"
        )
    key = canonical_key(namespace, rep, device, subsystem, None, seed)
    return uniform_from_key(key)


def u_d_post(namespace, rep, device, seed) -> Fraction:
    """U_D_post: H2 D posterior / prior resampling stream (SPEC 6.1).

    Same canonical slot pattern as U_D (namespace, replicate_id, device_id);
    consumed only under the formal H2 namespaces.
    """
    _require_h2_namespace(namespace)
    key = canonical_key(namespace, rep, device, None, None, seed)
    return uniform_from_key(key)


def u_y_post(namespace, rep, device, process, attempt, seed) -> Fraction:
    """U_Y_post: H2 rollout observation stream (SPEC 6.1).

    Same canonical slot pattern as U_Y (namespace, replicate_id, device_id,
    process, effective_attempt_no); consumed only under the formal H2
    namespaces; a rollout attempt consumes U_Y_post only on a valid
    completion (caller-enforced, mirroring NO_OBSERVATION_CONSUMED_BY).
    """
    _require_h2_namespace(namespace)
    if process not in PROCESSES:
        raise ValueError(
            f"U_Y_post process must be one of {PROCESSES}, got {process!r}"
        )
    key = canonical_key(namespace, rep, device, process, attempt, seed)
    return uniform_from_key(key)


def u_l_post(namespace, rep, resource, generation, seed) -> Fraction:
    """U_L_post: H2 conditional residual-lifetime resampling stream (SPEC
    6.1).

    Same canonical slot pattern as U_L (namespace, replicate_id, resource,
    generation_no); consumed only under the formal H2 namespaces.
    """
    _require_h2_namespace(namespace)
    if resource not in PROCESSES:
        raise ValueError(
            f"U_L_post resource must be one of {PROCESSES}, got {resource!r}"
        )
    key = canonical_key(namespace, rep, resource, None, generation, seed)
    return uniform_from_key(key)
