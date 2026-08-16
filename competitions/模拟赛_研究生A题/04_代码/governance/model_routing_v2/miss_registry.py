"""MATHEMATICAL_MODELING_ROUTER_V2.1 — routing miss registry (spec 35).

MODEL_ROUTING_MISS_REGISTRY: structured lessons from routing misses.
Only cross-contest failure patterns qualify for the UNIVERSAL rule set;
contest-specific experience stays PROJECT_SPECIFIC (project extensions).

This module is part of the UNIVERSAL CORE (generalization guard scans it).
Python 3.12, standard library only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MISS_REGISTRY_SCHEMA = {
    "miss_id": "str", "date": "str", "domain": "str",
    "original_route": "str", "correct_route": "str",
    "universal_risk_dimension": "str", "failure_pattern": "str",
    "new_general_rule": "str", "scope": "UNIVERSAL|PROJECT_SPECIFIC",
    "status": "str",
}


def validate_miss_registry(data: dict[str, Any]) -> dict[str, Any]:
    """Validate MODEL_ROUTING_MISS_REGISTRY: fixed fields and legal scope."""
    entries = data.get("entries", [])
    for entry in entries:
        for key in MISS_REGISTRY_SCHEMA:
            if key not in entry:
                raise ValueError(f"miss entry missing field {key!r}: {entry}")
        if entry["scope"] not in ("UNIVERSAL", "PROJECT_SPECIFIC"):
            raise ValueError(f"bad scope {entry['scope']!r} in miss "
                             f"{entry['miss_id']}")
    return data


def load_miss_registry(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_miss_registry(data)
