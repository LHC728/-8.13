"""MATHEMATICAL_MODELING_ROUTER_V2.1 — Route Sentinel V1 (LAYER 3, spec 16-17).

The Sentinel is a low-cost (Flash) CLASSIFICATION_AUDITOR_ONLY reviewer: it
checks for risk-classification OMISSIONS in a Risk Card, never the final
mathematical verdict.  It can agree (AGREE_GREEN/YELLOW/RED) or flag
RISK_OMISSION / ROUTE_TOO_LOW.  A disagreement AUTOMATICALLY upgrades the
proposed route to YELLOW (mandatory Pro-Max) and may not be vetoed by the
current Flash executor.

This module is part of the UNIVERSAL CORE (generalization guard scans it).
Python 3.12, standard library only.
"""
from __future__ import annotations

import json
from typing import Any, Optional

SENTINEL_VERDICTS = (
    "AGREE_GREEN", "AGREE_YELLOW", "AGREE_RED",
    "RISK_OMISSION", "ROUTE_TOO_LOW",
)


def build_sentinel_packet(*, task_id: str, task_description: str,
                          risk_card: dict[str, Any],
                          diff_summary: str,
                          authority_references: list[str],
                          diagnosis: str) -> str:
    """Standalone packet for the low-cost classification auditor."""
    return json.dumps({
        "SENTINEL_PACKET_VERSION": "V1",
        "role": "CLASSIFICATION_AUDITOR_ONLY",
        "task_id": task_id,
        "task_description": task_description,
        "risk_card": risk_card,
        "diff_summary": diff_summary,
        "authority_references": authority_references,
        "diagnosis": diagnosis,
        "instructions": (
            "Audit ONLY whether the risk classification omits risk dimensions "
            "or routes too low. Do NOT adjudicate the mathematics. Do not "
            "modify files. Reply with exactly one line: "
            "SENTINEL_VERDICT: AGREE_GREEN|AGREE_YELLOW|AGREE_RED|"
            "RISK_OMISSION|ROUTE_TOO_LOW, then missing_risk_dimensions: [...] "
            "and reason: ..."),
    }, ensure_ascii=False)


def parse_sentinel_verdict(text: str) -> dict[str, Any]:
    """Deterministic parse of the sentinel's reply."""
    verdict = None
    for cand in SENTINEL_VERDICTS:
        if f"SENTINEL_VERDICT: {cand}" in text:
            verdict = cand
            break
    if verdict is None:
        raise ValueError(f"no recognized SENTINEL_VERDICT in: {text[:200]}")
    missing: list[str] = []
    if "missing_risk_dimensions:" in text:
        seg = text.split("missing_risk_dimensions:", 1)[1].split("reason:", 1)[0]
        import re
        missing = re.findall(r"[A-Za-z_]+", seg)
    return {"verdict": verdict, "missing_risk_dimensions": missing,
            "raw": text}


def sentinel_upgrade(proposed_route: str, sentinel_result: dict[str, Any]
                     ) -> dict[str, Any]:
    """spec 17: RISK_OMISSION / ROUTE_TOO_LOW forces YELLOW (mandatory
    Pro-Max); the Flash executor cannot veto a Sentinel disagreement."""
    verdict = sentinel_result["verdict"]
    if verdict in ("RISK_OMISSION", "ROUTE_TOO_LOW"):
        if proposed_route == "GREEN":
            return {"upgraded": True, "route": "YELLOW",
                    "reason": f"Sentinel {verdict} -> mandatory Pro-Max"}
        if proposed_route in ("YELLOW", "RED"):
            return {"upgraded": False, "route": proposed_route,
                    "reason": f"Sentinel {verdict}; route already >= YELLOW"}
    return {"upgraded": False, "route": proposed_route,
            "reason": f"Sentinel {verdict}; no upgrade"}
