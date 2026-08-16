"""MATHEMATICAL_MODELING_ROUTER_V2.1 — routing events + metrics (spec 42-43).

routing_events.jsonl records every classification/reclassification/sentinel/
dispatch/verification/block/gate event.  Metrics are computed from the event
stream (no invented targets: no GREEN-percentage or Pro-Max-count targets).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

EVENT_TYPES = (
    "TASK_CLASSIFIED", "TASK_RECLASSIFIED", "SENTINEL_REVIEW",
    "RISK_OMISSION_DETECTED", "PRO_MAX_REQUIRED", "PRO_MAX_DISPATCHED",
    "PRO_MAX_VERIFIED", "PRO_MAX_FAILED", "ROUTING_BLOCKED",
    "HUMAN_GATE_REQUIRED",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_event(path: str, *, event_type: str, task_id: str,
                 semantic_issue_id: Optional[str] = None,
                 checkpoint: Optional[str] = None,
                 old_route: Optional[str] = None,
                 new_route: Optional[str] = None,
                 reason: str = "",
                 commit_sha: str = "") -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown routing event type {event_type!r}")
    rec = {
        "timestamp": _now(),
        "event_type": event_type,
        "task_id": task_id,
        "semantic_issue_id": semantic_issue_id,
        "checkpoint": checkpoint,
        "old_route": old_route,
        "new_route": new_route,
        "reason": reason,
        "commit_sha": commit_sha,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    return rec


def load_events(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        return []
    return [json.loads(line) for line in
            p.read_text(encoding="utf-8").splitlines() if line.strip()]


def compute_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Phase metrics from the event stream (spec 43).  No targets are set."""
    classified = [e for e in events if e["event_type"] == "TASK_CLASSIFIED"]
    reclassified = [e for e in events if e["event_type"] == "TASK_RECLASSIFIED"]
    sentinel = [e for e in events if e["event_type"] == "SENTINEL_REVIEW"]
    omissions = [e for e in events
                 if e["event_type"] == "RISK_OMISSION_DETECTED"]
    upgrades = [e for e in reclassified
                if e.get("old_route") == "GREEN"
                and e.get("new_route") == "YELLOW"]
    verified = [e for e in events if e["event_type"] == "PRO_MAX_VERIFIED"]
    dispatched = [e for e in events if e["event_type"] == "PRO_MAX_DISPATCHED"]
    blocked = [e for e in events if e["event_type"] == "ROUTING_BLOCKED"]
    human_gate = [e for e in events if e["event_type"] == "HUMAN_GATE_REQUIRED"]
    dedup_avoided = sum(1 for e in events
                        if e.get("reason", "").startswith("dedup:"))

    def count_route(route: str) -> int:
        return sum(1 for e in classified
                   if e.get("new_route") == route)

    return {
        "total_substantive_tasks": len(classified),
        "green_count": count_route("GREEN"),
        "yellow_count": count_route("YELLOW"),
        "red_count": count_route("RED"),
        "sentinel_reviews": len(sentinel),
        "sentinel_disagreements": len(omissions),
        "green_to_yellow_upgrades": len(upgrades),
        "verified_pro_max_calls": len(verified),
        "pro_max_dispatched": len(dispatched),
        "deduplicated_max_calls_avoided": dedup_avoided,
        "routing_blocks": len(blocked),
        "human_gate_routing_misses": len(human_gate),
        "no_targets_set": True,
    }
