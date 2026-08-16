"""MATHEMATICAL_MODELING_ROUTER_V2.1 — project extension layer (spec 33).

PROJECT_ROUTING_EXTENSION: per-contest mappings from project vocabulary to
universal risk dimensions and method families, plus regression patterns.
Extensions may only keep or ESCALATE risk — a YELLOW->GREEN or RED->YELLOW
mapping is rejected.  The Universal Core is never modified.

This module is part of the UNIVERSAL CORE (generalization guard scans it).
Python 3.12, standard library only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .risk_card import RISK_DIMENSIONS
from .method_families import FAMILIES


class ExtensionRejected(Exception):
    """Raised when an extension tries to de-escalate or use unknown ids."""


def validate_extension(data: dict[str, Any]) -> dict[str, Any]:
    """Validate one PROJECT_ROUTING_EXTENSION document.  Only escalations are
    legal: term_risks / family mapping additions may flag risk dimensions or
    add families; any mapping that would REMOVE a risk or downgrade a route
    class is rejected."""
    if not isinstance(data, dict):
        raise ExtensionRejected("extension must be a mapping")
    version = data.get("extension_version")
    if version is None:
        raise ExtensionRejected("extension_version required")
    project = data.get("project_id")
    if not project:
        raise ExtensionRejected("project_id required")
    for term, spec in (data.get("term_risks") or {}).items():
        risks = spec.get("risks", [])
        for r in risks:
            if r not in RISK_DIMENSIONS:
                raise ExtensionRejected(
                    f"term {term!r}: unknown risk dimension {r!r}")
        if spec.get("route_cap") is not None:
            raise ExtensionRejected(
                f"term {term!r}: route_cap would de-escalate; extensions may "
                "only keep or escalate risk")
    for term, families in (data.get("term_families") or {}).items():
        for f in families:
            if f not in FAMILIES:
                raise ExtensionRejected(f"unknown method family {f!r}")
    for pattern in (data.get("regression_patterns") or []):
        if not isinstance(pattern, dict) or "pattern" not in pattern:
            raise ExtensionRejected("regression_patterns entries need 'pattern'")
    return data


def apply_extension(risk_card: dict[str, Any], extension: dict[str, Any],
                    task_text: str) -> dict[str, Any]:
    """Apply an already-validated extension: flag the mapped risk dimensions
    (escalation only) and append method families."""
    validated = validate_extension(extension)
    card = dict(risk_card)
    risk = dict(card.get("risk", {}))
    families = list(card.get("method_families", []))
    for term, spec in (validated.get("term_risks") or {}).items():
        if term.lower() in task_text.lower():
            for r in spec.get("risks", []):
                risk[r] = True
    for term, fams in (validated.get("term_families") or {}).items():
        if term.lower() in task_text.lower():
            for f in fams:
                if f not in families:
                    families.append(f)
    card["risk"] = risk
    card["method_families"] = families
    return card


def load_extension(path: str) -> dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return validate_extension(data)
