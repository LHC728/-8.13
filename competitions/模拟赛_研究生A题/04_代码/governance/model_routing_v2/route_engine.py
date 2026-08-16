"""MATHEMATICAL_MODELING_ROUTER_V2.1.1 — deterministic route engine (LAYER 2).

compute_model_route_v2_1_1: purely mechanical, order-fixed rules.  V2.1.1
repairs (per Human Gate review of V2.1):

* P0-1 identity/outcome separation: VERIFIED_PRO_MAX proves only REVIEW
  IDENTITY (fresh_spawn / provider / model / effort / delta); the REVIEW
  OUTCOME (verdict + required_actions_closed + authority_conflict) decides
  the gate.  VERIFIED_PRO_MAX never means semantic PASS.
* P0-2 runtime Sentinel Gate: formal GREEN at R4 requires an actual
  low-cost Sentinel run with verdict AGREE_GREEN; missing/malformed ->
  ROUTING_BLOCKED.
* P1-2 fail-closed Risk Card validation: a malformed card is ROUTING_INVALID
  and can never formal-PASS.
* P1-3 (spec 13) frozen_mechanical_execution is NO LONGER a global override:
  risk fields represent unresolved current risk; any flagged semantic risk
  -> YELLOW unless the RED rule supersedes.  A genuinely frozen mechanical
  task has risk fields false + authority_refs.

GREEN_ALLOWLIST, engineering escalation, uncertainty escalation, dynamic
reclassification and semantic-issue dedup semantics follow the V2.1 design.

Python 3.12, standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .risk_card import (
    RiskCard, validate_card_fail_closed, RiskCardInvalid, ROUTING_INVALID)

GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"

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

_STRONG_ESCALATION = (
    "checker_disagreement",
    "checker_independence_concern",
    "claimed_coverage_not_exercised",
    "unexpected_behavior_after_pass",
    "formal_numeric_shift",
)


@dataclass
class RouteResult:
    route: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"route": self.route, "reasons": self.reasons}


def _engineering_escalated(card: RiskCard) -> bool:
    if not card.formal_scope:
        return False
    s = card.engineering_signals
    if any(getattr(s, name) for name in _STRONG_ESCALATION):
        return True
    if (s.new_complex_seam or s.repeat_failure_count >= 2) \
            and not card.frozen_mechanical_execution:
        return True
    return False


def compute_model_route_v2_1_1(card: RiskCard) -> RouteResult:
    """Deterministic route computation (V2.1.1 semantics).

    FAIL-CLOSED: the card is validated first; a malformed card raises
    RiskCardInvalid (ROUTING_INVALID) and can never formal-PASS.

    Order (spec 11 as repaired by spec 13):
      1) RED: governance_authority mutation of FROZEN/HUMAN_ACCEPTED
      2) any semantic risk field true -> YELLOW (NO frozen-mechanical bypass)
      3) uncertainty -> YELLOW
      4) multiple plausible interpretations -> YELLOW
      5) authority ambiguity -> YELLOW
      6) engineering escalation -> YELLOW
      7) GREEN allowlist membership (frozen mechanical, authority_refs
         validated) -> GREEN
      8) default YELLOW (cannot prove GREEN).
    """
    validate_card_fail_closed(card)  # ROUTING_INVALID on malformed cards
    reasons: list[str] = []

    if card.risk.get("governance_authority") \
            and card.authority_state in ("FROZEN", "HUMAN_ACCEPTED"):
        reasons.append(
            "governance_authority with authority_state="
            f"{card.authority_state} -> mutation of frozen/accepted authority")
        return RouteResult(RED, reasons)

    if card.risk_true():
        reasons.append("semantic risk present ("
                       + ", ".join(card.risk_true())
                       + ") -> YELLOW (risk fields represent unresolved "
                         "current risk; no frozen-mechanical bypass)")
        return RouteResult(YELLOW, reasons)

    if card.uncertainty_present:
        reasons.append("uncertainty_present -> cannot route GREEN")
        return RouteResult(YELLOW, reasons)

    if card.multiple_plausible_interpretations:
        reasons.append("multiple_plausible_interpretations")
        return RouteResult(YELLOW, reasons)

    if card.authority_ambiguity:
        reasons.append("authority_ambiguity")
        return RouteResult(YELLOW, reasons)

    if _engineering_escalated(card):
        reasons.append("engineering escalation (formal scope)")
        return RouteResult(YELLOW, reasons)

    if card.green_allowlist_class is not None:
        if card.green_allowlist_class in GREEN_ALLOWLIST:
            reasons.append(
                f"green allowlist class {card.green_allowlist_class} "
                f"(authority_refs={card.authority_refs})")
            return RouteResult(GREEN, reasons)
        reasons.append(f"green_allowlist_class {card.green_allowlist_class} "
                       "not in allowlist -> default YELLOW")
        return RouteResult(YELLOW, reasons)

    reasons.append("no GREEN allowlist class; cannot prove GREEN -> YELLOW")
    return RouteResult(YELLOW, reasons)


# backward-compatible alias (V2.1 callers); V2.1.1 semantics
compute_model_route_v2_1 = compute_model_route_v2_1_1


# ---------------------------------------------------------------------------
# gate-time enforcement (V2.1.1: identity/outcome separation + Sentinel Gate)
# ---------------------------------------------------------------------------

ROUTING_BLOCKED = "ROUTING_BLOCKED"
HUMAN_GATE_REQUIRED = "HUMAN_GATE_REQUIRED"
GATE_PASS = "PASS"
GATE_PASS_CAVEAT = "PASS_WITH_CAVEAT"

REVIEW_VERDICTS = ("PASS", "PASS_WITH_CAVEAT", "BLOCKED", "HUMAN_GATE_REQUIRED")
HUMAN_GATE_VERDICTS = ("PENDING", "ACCEPTED", "REJECTED")
SENTINEL_VERDICTS = ("AGREE_GREEN", "AGREE_YELLOW", "AGREE_RED",
                     "RISK_OMISSION", "ROUTE_TOO_LOW")


def route_gate_v2_1_1(
        route: str, *,
        review_identity_verified: bool = False,
        review_verdict: Optional[str] = None,
        required_actions_closed: bool = False,
        authority_conflict: bool = False,
        human_gate_verdict: str = "PENDING",
        sentinel_required: bool = False,
        sentinel_identity_verified: bool = False,
        sentinel_verdict: Optional[str] = None,
        checkpoint: str = "R0",
        formal_scope: bool = True,
) -> dict[str, Any]:
    """Fail-closed, outcome-aware gate decision (V2.1.1).

    REVIEW IDENTITY (review_identity_verified) proves only that the review
    ran on the verified channel — it is NEVER semantic approval.

    YELLOW:
      identity=false                    -> ROUTING_BLOCKED
      verdict missing/unknown           -> ROUTING_BLOCKED
      verdict=BLOCKED                   -> ROUTING_BLOCKED
      verdict=HUMAN_GATE_REQUIRED       -> HUMAN_GATE_REQUIRED
      verdict=PASS & actions closed     -> PASS
      verdict=PASS & actions open       -> ROUTING_BLOCKED
      verdict=PASS_WITH_CAVEAT & closed -> PASS (caveat recorded)
      verdict=PASS_WITH_CAVEAT & open   -> ROUTING_BLOCKED

    RED: human_gate_verdict ACCEPTED -> PASS; PENDING -> HUMAN_GATE_REQUIRED;
         REJECTED/unknown -> ROUTING_BLOCKED.  A gate that merely "happened"
         is never acceptance.

    GREEN (formal_scope + checkpoint=R4): runtime Sentinel Gate — requires
      sentinel_required=true, an actual low-cost Sentinel run
      (sentinel_identity_verified) and sentinel_verdict=AGREE_GREEN;
      missing/malformed -> ROUTING_BLOCKED.  GREEN outside the R4 formal
      gate passes without the Sentinel requirement.
    """
    if route == RED:
        if human_gate_verdict == "ACCEPTED":
            return {"status": GATE_PASS, "route": route,
                    "note": "human gate accepted"}
        if human_gate_verdict == "PENDING":
            return {"status": HUMAN_GATE_REQUIRED, "route": route,
                    "note": "human gate pending; no Pro-Max self-approval"}
        return {"status": ROUTING_BLOCKED, "route": route,
                "note": f"human gate {human_gate_verdict!r} is not acceptance"}

    if route == YELLOW:
        if not review_identity_verified:
            return {"status": ROUTING_BLOCKED, "route": route,
                    "note": "review identity not verified -> BLOCKED"}
        if review_verdict not in REVIEW_VERDICTS:
            return {"status": ROUTING_BLOCKED, "route": route,
                    "note": f"unknown/missing review verdict {review_verdict!r} "
                            "-> BLOCKED"}
        if review_verdict == "BLOCKED":
            return {"status": ROUTING_BLOCKED, "route": route,
                    "note": "review verdict BLOCKED -> BLOCKED"}
        if review_verdict == "HUMAN_GATE_REQUIRED":
            return {"status": HUMAN_GATE_REQUIRED, "route": route,
                    "note": "review verdict HUMAN_GATE_REQUIRED"}
        if review_verdict == "PASS":
            if required_actions_closed:
                return {"status": GATE_PASS, "route": route,
                        "note": "review PASS with required actions closed"}
            return {"status": ROUTING_BLOCKED, "route": route,
                    "note": "review PASS but required actions open -> BLOCKED"}
        # PASS_WITH_CAVEAT
        if required_actions_closed:
            return {"status": GATE_PASS, "route": route,
                    "caveat_recorded": True,
                    "note": "PASS_WITH_CAVEAT with actions closed -> PASS; "
                            "caveat state recorded"}
        return {"status": ROUTING_BLOCKED, "route": route,
                "note": "PASS_WITH_CAVEAT with unresolved caveat actions "
                        "-> BLOCKED"}

    if route == GREEN:
        if formal_scope and checkpoint == "R4":
            if not sentinel_required:
                return {"status": ROUTING_BLOCKED, "route": route,
                        "note": "formal GREEN at R4 without Sentinel "
                                "requirement -> BLOCKED"}
            if not sentinel_identity_verified:
                return {"status": ROUTING_BLOCKED, "route": route,
                        "note": "formal GREEN at R4: Sentinel identity not "
                                "verified -> BLOCKED"}
            if sentinel_verdict != "AGREE_GREEN":
                return {"status": ROUTING_BLOCKED, "route": route,
                        "note": f"formal GREEN at R4: Sentinel verdict "
                                f"{sentinel_verdict!r} is not AGREE_GREEN "
                                "-> BLOCKED"}
            return {"status": GATE_PASS, "route": route,
                    "note": "formal GREEN at R4 with Sentinel AGREE_GREEN"}
        return {"status": GATE_PASS, "route": route,
                "note": "GREEN route (outside the R4 formal gate)"}

    raise ValueError(f"unknown route {route!r}")


# backward-compatible alias (V2.1 callers) — NOTE: the old boolean
# verified_pro_max argument no longer exists; callers must use the
# outcome-aware arguments.
route_gate_v2_1 = route_gate_v2_1_1


# ---------------------------------------------------------------------------
# semantic issue dedup (spec 20/21 as repaired by spec 6)
# ---------------------------------------------------------------------------

SEMANTIC_STATUSES = ("OPEN", "RESOLVED", "BLOCKED", "HUMAN_PENDING")

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
    """Durable semantic-issue store.  V2.1.1 repair: identity verification is
    strictly separated from issue resolution.  An issue may be deduped
    ("no repeated Pro-Max required") ONLY when:

      review_identity_verified = true
      AND review_verdict is an acceptable terminal outcome
      AND required_actions_closed = true
      AND contract_hash unchanged.

    BLOCKED never becomes RESOLVED merely because the reviewer identity was
    verified; HUMAN_GATE_REQUIRED never resolves without accepted Human Gate
    evidence; PASS_WITH_CAVEAT stays open while caveat actions are open.
    """

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
        if not rec.get("review_identity_verified"):
            return True
        if rec.get("semantic_status") in ("BLOCKED", "HUMAN_PENDING"):
            return True
        if rec.get("semantic_status") != "RESOLVED":
            return True
        if not rec.get("required_actions_closed"):
            return True
        if rec.get("contract_hash") != contract_hash:
            return True
        return False

    def rereview_required(self, issue_id: str,
                          signals: dict[str, bool]) -> bool:
        rec = self._issues.get(issue_id)
        if rec is None:
            return True
        for key in REVIEW_CONDITIONS:
            if signals.get(key):
                return True
        return False

    def record(self, issue_id: str, contract_hash: str, verdict: str,
               semantic_status: str, *, review_identity_verified: bool,
               required_actions_closed: bool,
               commit_sha: str = "") -> None:
        if verdict not in REVIEW_VERDICTS:
            raise ValueError(f"unknown review verdict {verdict!r}")
        if semantic_status not in SEMANTIC_STATUSES:
            raise ValueError(f"unknown semantic status {semantic_status!r}")
        # V2.1.1 invariants: BLOCKED/HUMAN_PENDING can never be stored as
        # RESOLVED; identity verification never implies resolution.
        if semantic_status == "RESOLVED":
            if verdict in ("BLOCKED", "HUMAN_GATE_REQUIRED"):
                raise ValueError(
                    f"verdict {verdict} cannot be stored as RESOLVED")
            if not required_actions_closed:
                raise ValueError(
                    "RESOLVED requires required_actions_closed=true")
        self._issues[issue_id] = {
            "issue_id": issue_id, "contract_hash": contract_hash,
            "review_verdict": verdict,
            "semantic_status": semantic_status,
            "review_identity_verified": review_identity_verified,
            "required_actions_closed": required_actions_closed,
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
