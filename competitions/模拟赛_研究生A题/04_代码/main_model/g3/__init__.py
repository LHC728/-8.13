"""G3 keyed random infrastructure package (key_schema_v1).

Frozen by G3-SPEC-V1.0 section 3 (random_key_architecture). Public API:

* ``canonical_key(...)`` -- normalized UTF-8 canonical key string
* ``uniform_from_key(canonical_key)`` -- exact uniform U (Fraction) in [0, 1)
* ``u_x`` / ``u_d`` / ``u_y`` / ``u_l`` -- the four consumable stream helpers
* frozen constants: namespaces (six + H2 reserved), canonical field order,
  forbidden physical key fields, no-observation-consumed-by semantics

Standard library only (no third-party imports).
"""

from .key_schema_v1 import (
    ALL_NAMESPACES,
    CANONICAL_KEY_FIELD_ORDER,
    FORBIDDEN_PHYSICAL_KEY_FIELDS,
    H2_RESERVED_NAMESPACE,
    KEY_SCHEMA_VERSION,
    MAPPING_DESCRIPTION,
    NAMESPACE_DEVELOPMENT_UNIT,
    NAMESPACE_G3_HOLDOUT,
    NAMESPACE_H1_TUNING,
    NAMESPACE_PILOT,
    NAMESPACE_Q2_FORMAL,
    NAMESPACE_Q3_FORMAL,
    NAMESPACES,
    NO_OBSERVATION_CONSUMED_BY,
    PROCESSES,
    SUBSYSTEMS,
    canonical_key,
    u_d,
    u_l,
    u_x,
    u_y,
    uniform_from_key,
)

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
]
