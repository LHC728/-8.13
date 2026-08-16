"""MATHEMATICAL_MODELING_ROUTER_V2.1 — generalization guard (spec 34) and
routing miss registry (spec 35).

GENERALIZATION_CHECK: the Universal Core source must contain zero
project-specific tokens (read from data/project_specific_tokens.json).
Only project-level patterns may live in the miss registry; cross-contest
patterns qualify for the universal rule set.

This module is part of the UNIVERSAL CORE (generalization guard scans it).
Python 3.12, standard library only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .miss_registry import (  # noqa: F401  (kept importable from here)
    MISS_REGISTRY_SCHEMA, validate_miss_registry, load_miss_registry)

# Universal Core source files scanned by the guard (this module and the
# checker are governance tooling, not Universal Core source).
UNIVERSAL_CORE_FILES = (
    "risk_card.py",
    "route_engine.py",
    "method_families.py",
    "verification_strategies.py",
    "sentinel.py",
    "extensions.py",
    "miss_registry.py",
    "events.py",
)

_TOKEN_FILE = Path(__file__).parent / "data" / "project_specific_tokens.json"


def load_project_tokens(path: Path = _TOKEN_FILE) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(f"project token file missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("project_specific_tokens", []))


def generalization_check(core_dir: str, token_file: str | None = None
                         ) -> dict[str, Any]:
    """Scan Universal Core source for project-specific tokens.

    Tokens are matched as whole words so a token cannot hide inside a longer
    identifier.  Returns PASS/FAIL with per-file matches (fail-closed)."""
    root = Path(core_dir)
    tokens = load_project_tokens(Path(token_file) if token_file else _TOKEN_FILE)
    matches: dict[str, list[str]] = {}
    for name in UNIVERSAL_CORE_FILES:
        p = root / name
        if not p.is_file():
            matches[name] = ["FILE MISSING"]
            continue
        text = p.read_text(encoding="utf-8")
        hits = []
        for token in tokens:
            if re.search(r"\b" + re.escape(token) + r"\b", text):
                hits.append(token)
        if hits:
            matches[name] = hits
    ok = not matches
    return {"check": "GENERALIZATION_CHECK", "status": "PASS" if ok else "FAIL",
            "scanned_files": list(UNIVERSAL_CORE_FILES),
            "token_count": len(tokens),
            "matches": matches}
