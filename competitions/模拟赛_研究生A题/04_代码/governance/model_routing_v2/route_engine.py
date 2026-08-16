"""MATHEMATICAL_MODELING_ROUTER_V2.1 — deterministic route engine (LAYER 2).

compute_model_route_v2_1: purely mechanical, order-fixed rules (spec 11).
GREEN_ALLOWLIST (spec 12), engineering escalation (spec 13), uncertainty
escalation (spec 14), gate-time enforcement with VERIFIED_PRO_MAX and the
fail-closed ROUTING_BLOCKED path (spec 15/18/41), and semantic-issue dedup
(spec 20/21).

This module is part of the UNIVERSAL CORE (generalization guard scans it).
Python 3.12, standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .risk_card import RiskCard, RISK_DIMENSIONS

GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"

# spec 12: GREEN is only reachable through this allowlist
GREEN_ALLOWLIST = frozenset({
    "RUN_EXISTING_TEST",
    "RUN_EXISTING_CHECKER",
    "REGRESSION_EXECUTION",
    "FORMAT_ONLY",
    "TYPO_FIX",
    "IMPORT_PATH_FIX",
    "JSON_SCHEMA_FIELD_FIX",
    "REPORT_FIELD_SYNC",
    "HASH_PROVENANCE",
    "EVIDENCE_PACKAGING",
    "MECHANICAL_DATA_TRANSFORM_UNDER_FROZEN_EXACT_RULE",
    "MECHANICAL_FORMULA_IMPLEMENTATION_UNDER_FROZEN_EXACT_FORMULA",
    "MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
    "PLOT_FROM_FROZEN_DATA_AND_SPEC",
    "SEMANTICS_PRESERVING_REFACTOR",
    "REPRODUCE_ACCEPTED_RESULT_WITHOUT_METHOD_CHANGE",
})

# soft escalation signals with formal scope (spec 13)
_STRONG_ESCALATION = (
    "checker_disagreement",              # S3
    "checker_independence_concern",      # S4
    "claimed_coverage_not_exercised",    # S5
    "unexpected_behavior_after_pass",    # S6
    "formal_numeric_shift",              # S7
)


@dataclass
class RouteResult:
    route: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"route": self.route, "reasons": self.reasons}


def _engineering_escalated(card: RiskCard) -> bool:
    """spec 13: formal_scope + S3..S7 -> YELLOW; S1/S2 -> YELLOW unless the
    task is provably pure-mechanical (frozen_mechanical_execution)."""
    if not card.formal_scope:
        return False
    s = card.engineering_signals
    if any(getattr(s, name) for name in _STRONG_ESCALATION):
        return True
    if (s.new_complex_seam or s.repeat_failure_count >= 2) \
            and not card.frozen_mechanical_execution:
        return True
    return False


def compute_model_route_v2_1(card: RiskCard) -> RouteResult:
    """Deterministic route computation with the fixed order of spec 11.
    The final fallback is YELLOW: failing to prove GREEN is YELLOW, never
    'no danger found -> GREEN'."""
    reasons: list[str] = []

    # 1) RED: governance_authority mutation of FROZEN/HUMAN_ACCEPTED authority
    if card.risk.get("governance_authority") \
            and card.authority_state in ("FROZEN", "HUMAN_ACCEPTED"):
        reasons.append(
            "R10 governance_authority with authority_state="
            f"{card.authority_state} -> mutation of frozen/accepted authority")
        return RouteResult(RED, reasons)

    # 2) any semantic risk without frozen mechanical execution -> YELLOW
    any_risk = bool(card.risk_true())
    if any_risk and not card.frozen_mechanical_execution:
        reasons.append("semantic risk present ("
                       + ", ".join(card.risk_true())
                       + ") and not frozen_mechanical_execution")
        return RouteResult(YELLOW, reasons)

    # 3) uncertainty escalation
    if card.uncertainty_present:
        reasons.append("uncertainty_present -> cannot route GREEN")
        return RouteResult(YELLOW, reasons)

    # 4) multiple plausible interpretations
    if card.multiple_plausible_interpretations:
        reasons.append("multiple_plausible_interpretations")
        return RouteResult(YELLOW, reasons)

    # 5) authority ambiguity
    if card.authority_ambiguity:
        reasons.append("authority_ambiguity")
        return RouteResult(YELLOW, reasons)

    # 6) engineering escalation
    if _engineering_escalated(card):
        reasons.append("engineering escalation (formal scope)")
        return RouteResult(YELLOW, reasons)

    # 7) GREEN allowlist membership (no RED/YELLOW trigger survived above)
    if card.green_allowlist_class is not None:
        if card.green_allowlist_class in GREEN_ALLOWLIST:
            reasons.append(f"green allowlist class {card.green_allowlist_class}")
            return RouteResult(GREEN, reasons)
        reasons.append(f"green_allowlist_class {card.green_allowlist_class} "
                       "not in allowlist -> default YELLOW")
        return RouteResult(YELLOW, reasons)

    # 8) default: cannot prove GREEN -> YELLOW
    reasons.append("no GREEN allowlist class; cannot prove GREEN -> YELLOW")
    return RouteResult(YELLOW, reasons)


# ---------------------------------------------------------------------------
# gate-time enforcement (spec 15/18/19/41)
# ---------------------------------------------------------------------------

ROUTING_BLOCKED = "ROUTING_BLOCKED"
HUMAN_GATE_REQUIRED = "HUMAN_GATE_REQUIRED"
GATE_PASS = "PASS"


def route_gate_v2_1(route: str, verified_pro_max: bool = False,
                    human_gate_done: bool = False) -> dict[str, Any]:
    """Fail-closed gate decision.

    - RED: formal pass requires the human gate; without it the branch is
      stopped (HUMAN_GATE_REQUIRED / ROUTING_BLOCKED) — a frozen mutation can
      never formal-pass silently.
    - YELLOW: mandatory VERIFIED_PRO_MAX; missing -> ROUTING_BLOCKED.  No
      fallback to Flash or Pro/high is ever produced here.
    - GREEN: pass.
    """
    if route == RED:
        if human_gate_done:
            return {"status": GATE_PASS, "route": route,
                    "note": "human gate accepted"}
        return {"status": HUMAN_GATE_REQUIRED, "route": route,
                "note": "frozen/authority mutation requires Human Gate; "
                        "no Pro-Max self-approval"}
    if route == YELLOW:
        if verified_pro_max:
            return {"status": GATE_PASS, "route": route,
                    "note": "VERIFIED_PRO_MAX present"}
        return {"status": ROUTING_BLOCKED, "route": route,
                "note": "YELLOW without VERIFIED_PRO_MAX -> BLOCKED; "
                        "fallback to Flash/Pro-high is forbidden"}
    if route == GREEN:
        return {"status": GATE_PASS, "route": route,
                "note": "GREEN allowlist route (Sentinel acceptance applies "
                        "at the R4 gate per routing policy)"}
    raise ValueError(f"unknown route {route!r}")


# ---------------------------------------------------------------------------
# semantic issue dedup (spec 20/21)
# ---------------------------------------------------------------------------

REVIEW_CONDITIONS = {
    "semantic_contract_changed": "semantic contract changed",
    "new_counterexample": "new counterexample",
    "new_authority_evidence": "new authority evidence",
    "checker_contradiction": "checker contradiction",
    "previous_required_action_unresolved": "previous required action unresolved",
    "new_formal_implication": "new formal implication",
    "previous_caveat_material": "previous caveat becomes material",
}


class SemanticIssueStore:
    """Durable semantic-issue verdict store with contract-hash dedup."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self._issues: dict[str, dict[str, Any]] = {}
        if path is not None:
            import json
            from pathlib import Path
            p = Path(path)
            if p.is_file():
                self._issues = json.loads(p.read_text(encoding="utf-8"))

    def needs_pro_max(self, issue_id: str, contract_hash: str) -> bool:
        rec = self._issues.get(issue_id)
        if rec is None:
            return True
        if not rec.get("verified"):
            return True
        if rec.get("contract_hash") != contract_hash:
            return True
        return False

    def rereview_required(self, issue_id: str,
                          signals: dict[str, bool]) -> bool:
        rec = self._issues.get(issue_id)
        if rec is None:
            return True
        for key, _label in REVIEW_CONDITIONS.items():
            if signals.get(key):
                return True
        return False

    def record(self, issue_id: str, contract_hash: str, verdict: str,
               verified: bool, commit_sha: str = "") -> None:
        self._issues[issue_id] = {
            "issue_id": issue_id, "contract_hash": contract_hash,
            "verdict": verdict, "verified": verified,
            "commit_sha": commit_sha,
        }
        if self.path is not None:
            import json
            from pathlib import Path
            Path(self.path).write_text(
                json.dumps(self._issues, ensure_ascii=False, sort_keys=True,
                           indent=1) + "\n", encoding="utf-8", newline="\n")

    def snapshot(self) -> dict[str, Any]:
        return dict(self._issues)
