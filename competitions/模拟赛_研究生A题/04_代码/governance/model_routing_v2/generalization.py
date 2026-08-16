"""MATHEMATICAL_MODELING_ROUTER_V2.1.1 — project-token leak guard (spec 34 as
repaired by §18) and routing miss registry (spec 35).

PROJECT_TOKEN_LEAK_GUARD (renamed from GENERALIZATION_CHECK for accuracy):
zero token matches proves ONLY that the KNOWN current-project tokens did not
leak into the Universal Core source.  It does NOT by itself prove cross-domain
or cross-language generalization — generalization evidence must additionally
include the cross-domain tests (spec 38), the Chinese/English method-family
tests (spec 17), and the verification-family tests (spec 39).

This module is part of the UNIVERSAL CORE (the guard scans it).
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
    """PROJECT_TOKEN_LEAK_GUARD: scan Universal Core source for KNOWN
    project-specific tokens (whole-word match, fail-closed).

    Zero matches proves only that the known current-project tokens did not
    leak into the Universal Core source.  It does NOT by itself prove
    cross-domain or cross-language generalization — that evidence comes from
    the cross-domain tests, the Chinese/English method-family tests, and the
    verification-family tests (see the V2.1.1 authority doc §18)."""
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
    return {"check": "PROJECT_TOKEN_LEAK_GUARD", "status": "PASS" if ok else "FAIL",
            "scanned_files": list(UNIVERSAL_CORE_FILES),
            "token_count": len(tokens),
            "matches": matches}
