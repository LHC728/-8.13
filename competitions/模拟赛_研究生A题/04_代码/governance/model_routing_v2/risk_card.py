"""MATHEMATICAL_MODELING_ROUTER_V2.1 — risk card model (LAYER 1/2).

Universal risk dimensions R1..R10, authority states, modeling stages, and
the deterministic RiskCard structure.  This module is part of the UNIVERSAL
CORE: it must never reference project-specific symbols (generalization guard
scans it).

Python 3.12, standard library only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

ROUTER_VERSION = "MMR_V2.1.1"

# --- authority states (spec 6) -------------------------------------------------
AUTHORITY_STATES = ("EXPLORATORY", "PROPOSED", "FROZEN", "HUMAN_ACCEPTED")

# --- modeling stages (spec 7) --------------------------------------------------
STAGES = (
    "PROBLEM_UNDERSTANDING", "DATA_UNDERSTANDING", "EXPLORATORY_MODELING",
    "ASSUMPTION_DESIGN", "FORMULATION", "IMPLEMENTATION", "CALIBRATION",
    "VALIDATION", "FORMAL_EVALUATION", "RECOMMENDATION", "WRITING",
    "GOVERNANCE",
)

# --- universal risk dimensions R1..R10 (spec 9) --------------------------------
RISK_DIMENSIONS = (
    "problem_semantics",          # R1
    "modeling_assumption",        # R2
    "mathematical_formulation",   # R3
    "data_semantics",             # R4
    "statistical_inference",      # R5
    "algorithmic_semantics",      # R6
    "numerical_method",           # R7
    "validation_interpretation",  # R8
    "formal_result_impact",       # R9
    "governance_authority",       # R10
)

# --- engineering escalation signals S1..S7 (spec 13) ---------------------------
ENGINEERING_SIGNALS = (
    "new_complex_seam",           # S1
    "repeat_failure_count",       # S2 (int)
    "checker_disagreement",       # S3
    "checker_independence_concern",  # S4
    "claimed_coverage_not_exercised",  # S5
    "unexpected_behavior_after_pass",  # S6
    "formal_numeric_shift",       # S7
)

# --- checkpoints (spec 15) ------------------------------------------------------
CHECKPOINTS = ("R0", "R1", "R2", "R3", "R4")


@dataclass
class EngineeringSignals:
    new_complex_seam: bool = False
    repeat_failure_count: int = 0
    checker_disagreement: bool = False
    checker_independence_concern: bool = False
    claimed_coverage_not_exercised: bool = False
    unexpected_behavior_after_pass: bool = False
    formal_numeric_shift: bool = False


@dataclass
class RiskCard:
    """The routing risk card (spec 10).  Every substantive task produces one."""
    task_id: str
    semantic_issue_id: Optional[str] = None
    stage: str = "FORMULATION"
    authority_state: str = "EXPLORATORY"
    formal_scope: bool = True
    risk: dict[str, bool] = field(default_factory=dict)
    multiple_plausible_interpretations: bool = False
    authority_ambiguity: bool = False
    uncertainty_present: bool = False
    frozen_mechanical_execution: bool = False
    engineering_signals: EngineeringSignals = field(default_factory=EngineeringSignals)
    green_allowlist_class: Optional[str] = None
    authority_refs: list[str] = field(default_factory=list)
    risk_evidence: list[dict[str, str]] = field(default_factory=list)
    computed_route: Optional[str] = None
    route_reason: list[str] = field(default_factory=list)
    checkpoint: str = "R0"

    def __post_init__(self) -> None:
        if self.stage not in STAGES:
            raise ValueError(f"unknown stage {self.stage!r}")
        if self.authority_state not in AUTHORITY_STATES:
            raise ValueError(f"unknown authority_state {self.authority_state!r}")
        if self.checkpoint not in CHECKPOINTS:
            raise ValueError(f"unknown checkpoint {self.checkpoint!r}")
        for dim in RISK_DIMENSIONS:
            if dim not in self.risk:
                self.risk[dim] = False
        if not isinstance(self.engineering_signals, EngineeringSignals):
            self.engineering_signals = EngineeringSignals(
                **self.engineering_signals)

    def risk_true(self) -> list[str]:
        return [d for d in RISK_DIMENSIONS if self.risk.get(d)]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["router_version"] = ROUTER_VERSION
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))


def risk_card_from_dict(data: dict[str, Any]) -> RiskCard:
    """Rebuild a card from a stored dict (schema round-trip)."""
    es = data.get("engineering_signals") or {}
    payload = dict(data)
    payload.pop("router_version", None)
    payload["engineering_signals"] = EngineeringSignals(
        **{k: es.get(k, False if k != "repeat_failure_count" else 0)
           for k in ENGINEERING_SIGNALS})
    payload.setdefault("authority_refs", [])
    return RiskCard(**payload)


ROUTING_INVALID = "ROUTING_INVALID"

# GREEN classes whose meaning depends on a frozen/accepted authority (spec 14):
# they require authority_refs to be identifiable.
_AUTHORITY_DEPENDENT_GREEN = (
    "MECHANICAL_DATA_TRANSFORM_UNDER_FROZEN_EXACT_RULE",
    "MECHANICAL_FORMULA_IMPLEMENTATION_UNDER_FROZEN_EXACT_FORMULA",
    "MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
    "PLOT_FROM_FROZEN_DATA_AND_SPEC",
    "REPRODUCE_ACCEPTED_RESULT_WITHOUT_METHOD_CHANGE",
)


class RiskCardInvalid(ValueError):
    """Fail-closed rejection of a malformed risk card (ROUTING_INVALID)."""


def validate_card_fail_closed(card: RiskCard) -> None:
    """Mandatory fail-closed validation (V2.1.1, spec 12/13/14).

    Raises RiskCardInvalid on ANY malformed card: a malformed card yields
    ROUTING_INVALID and can never formal-PASS.  Rejected at minimum:

    * risk dimension true without risk_evidence for that dimension;
    * risk_evidence naming a dimension that is false (unless informational);
    * unknown risk dimensions / invalid authority state / invalid stage;
    * GREEN allowlist class without mechanical evidence and, for
      authority-dependent classes, without identifiable authority_refs;
    * contradictory mechanical/semantic fields (a frozen mechanical task
      must have its semantic risk fields FALSE — see spec 13).
    """
    for dim in card.risk:
        if dim not in RISK_DIMENSIONS:
            raise RiskCardInvalid(f"unknown risk dimension {dim!r}")
    for dim in card.risk_true():
        if not any(e.get("dimension") == dim for e in card.risk_evidence):
            raise RiskCardInvalid(
                f"risk dimension {dim} is true without risk_evidence")
    for e in card.risk_evidence:
        dim = e.get("dimension")
        if dim is None:
            continue
        if dim not in RISK_DIMENSIONS:
            raise RiskCardInvalid(
                f"risk_evidence references unknown dimension {dim!r}")
        if e.get("informational"):
            continue
        if not card.risk.get(dim):
            raise RiskCardInvalid(
                f"risk_evidence references {dim} while the flag is false "
                "(mark informational=True to reference a non-flagged dimension)")
    if card.green_allowlist_class is not None:
        if not card.frozen_mechanical_execution:
            raise RiskCardInvalid(
                "green_allowlist_class requires frozen_mechanical_execution")
        if card.green_allowlist_class in _AUTHORITY_DEPENDENT_GREEN \
                and not card.authority_refs:
            raise RiskCardInvalid(
                f"green_allowlist_class {card.green_allowlist_class} requires "
                "authority_refs (frozen/accepted authority must be identifiable)")
    # spec 13: risk fields represent UNRESOLVED CURRENT RISK; a genuinely
    # frozen mechanical task has risk fields false.  Flagging a semantic risk
    # while claiming frozen mechanical execution is contradictory.
    if card.frozen_mechanical_execution and card.risk_true():
        raise RiskCardInvalid(
            "frozen_mechanical_execution=true with flagged semantic risk is "
            "contradictory: risk fields represent unresolved current risk")


def validate_card(card: RiskCard) -> list[str]:
    """Soft integrity report (informational only).  Routing NEVER uses this
    for a gate: fail-closed validation is mandatory before route computation
    (see validate_card_fail_closed)."""
    problems: list[str] = []
    try:
        validate_card_fail_closed(card)
    except RiskCardInvalid as exc:
        problems.append(str(exc))
    if card.green_allowlist_class is not None and not card.frozen_mechanical_execution:
        problems.append("green_allowlist_class without frozen_mechanical_execution")
    return problems
