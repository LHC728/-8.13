"""MATHEMATICAL_MODELING_ROUTER_V2.1.1 — Route Sentinel V1 (LAYER 3, spec 16-17
as repaired: P0-2 runtime enforcement + §9 never-de-escalate matrix).

The Sentinel is a low-cost (Flash/E2) CLASSIFICATION_AUDITOR_ONLY reviewer:
it audits ONLY risk-classification omissions, never the final mathematical
verdict.  Formal GREEN at R4 is enforced by route_gate_v2_1_1 and REQUIRES
an actual Sentinel run with verdict AGREE_GREEN; missing/malformed Sentinel
output -> ROUTING_BLOCKED (a synthetic parser test is not enforcement).

Python 3.12, standard library only.
"""
from __future__ import annotations

import json
from typing import Any, Optional

SENTINEL_VERDICTS = (
    "AGREE_GREEN", "AGREE_YELLOW", "AGREE_RED",
    "RISK_OMISSION", "ROUTE_TOO_LOW",
)

from .route_engine import (  # noqa: E402
    GREEN, YELLOW, RED, ROUTING_BLOCKED)


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
            "modify files. Do not invoke another subagent. Reply with exactly "
            "one line: "
            "SENTINEL_VERDICT: AGREE_GREEN|AGREE_YELLOW|AGREE_RED|"
            "RISK_OMISSION|ROUTE_TOO_LOW, then missing_risk_dimensions: [...] "
            "and reason: ..."),
    }, ensure_ascii=False)


def parse_sentinel_verdict(text: str) -> dict[str, Any]:
    """Deterministic parse of the sentinel's reply.

    Raises ValueError on malformed output (no recognized verdict).  The gate
    treats a malformed Sentinel as missing -> ROUTING_BLOCKED for formal
    GREEN (fail-closed)."""
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
    """V2.1.1 never-de-escalate escalation matrix (spec 9).

    proposed GREEN:
      AGREE_GREEN -> GREEN; AGREE_YELLOW -> YELLOW; AGREE_RED -> RED;
      RISK_OMISSION / ROUTE_TOO_LOW -> YELLOW minimum.
    proposed YELLOW:
      AGREE_GREEN -> remains YELLOW (never de-escalate);
      AGREE_YELLOW -> YELLOW; AGREE_RED -> RED;
      RISK_OMISSION / ROUTE_TOO_LOW -> remains >= YELLOW.
    proposed RED: all Sentinel outcomes -> remain RED.
    Malformed/unknown Sentinel output: for formal GREEN -> ROUTING_BLOCKED
    (fail-closed; handled by the caller via the raised ValueError).
    """
    verdict = sentinel_result.get("verdict")
    if verdict not in SENTINEL_VERDICTS:
        raise ValueError(f"malformed Sentinel verdict {verdict!r}")
    if proposed_route == GREEN:
        if verdict == "AGREE_GREEN":
            return {"upgraded": False, "route": GREEN,
                    "reason": "Sentinel AGREE_GREEN"}
        if verdict == "AGREE_YELLOW":
            return {"upgraded": True, "route": YELLOW,
                    "reason": "Sentinel AGREE_YELLOW upgrades GREEN"}
        if verdict == "AGREE_RED":
            return {"upgraded": True, "route": RED,
                    "reason": "Sentinel AGREE_RED upgrades GREEN"}
        return {"upgraded": True, "route": YELLOW,
                "reason": f"Sentinel {verdict} -> YELLOW minimum"}
    if proposed_route == YELLOW:
        if verdict == "AGREE_RED":
            return {"upgraded": True, "route": RED,
                    "reason": "Sentinel AGREE_RED upgrades YELLOW"}
        return {"upgraded": False, "route": YELLOW,
                "reason": f"Sentinel {verdict}; YELLOW never de-escalates"}
    if proposed_route == RED:
        return {"upgraded": False, "route": RED,
                "reason": f"Sentinel {verdict}; RED never de-escalates"}
    raise ValueError(f"unknown proposed route {proposed_route!r}")
