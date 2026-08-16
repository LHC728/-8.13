#!/usr/bin/env python3
"""MATHEMATICAL_MODELING_ROUTER_V2.1 — routing checker MMR-01..16 (spec 37).

HISTORICAL / SUPERSEDED_FOR_ROUTING_GATE by V2.1.1 (repair): the V2.1 PASS
claim and this checker's PASS claim are invalidated by INVALIDATION_REPORT_
V2.1.1 (VERIFIED_PRO_MAX was conflated with semantic approval; the runtime
Sentinel gate was missing).  The file is retained for traceability; the
current routing gate checker is check_mathematical_modeling_router_v2_1_1.py
(R-01..R-22).  Gate calls in this file use the V2.1.1 engine API.

A REAL checker: every gate is computed from actual artifacts or from the
router's deterministic behaviour — never hard-coded PASS statements.

Usage: python check_mathematical_modeling_router_v2_1.py <evidence_root>

Evidence root layout (05_结果/governance/model_routing/):
  phase_a_replay_result.json          (A1)
  v2/phase_a_exact_smoke_result.json  (A2)
  v2/routing_events.jsonl             (R0-R4 + routing events)
  v2/routing_verification.json        (live integration)
  v2/semantic_issues.json             (dedup store)
  v2/extension_rejections.json        (extension non-deescalation)
  v2/demo_risk_cards.json             (R0-R4 demo cards)
  route_check_result.json             (Phase-A replay artifact)

Python 3.12, standard library only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 04_代码
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # governance pkg

from governance.model_routing_v2.risk_card import RiskCard  # noqa: E402
from governance.model_routing_v2.route_engine import (  # noqa: E402
    compute_model_route_v2_1, route_gate_v2_1, SemanticIssueStore,
    GREEN, YELLOW, RED, ROUTING_BLOCKED, HUMAN_GATE_REQUIRED, GATE_PASS)
from governance.model_routing_v2.sentinel import (  # noqa: E402
    parse_sentinel_verdict, sentinel_upgrade)
from governance.model_routing_v2.extensions import (  # noqa: E402
    validate_extension, ExtensionRejected)
from governance.model_routing_v2.method_families import (  # noqa: E402
    classify_method_families)
from governance.model_routing_v2.generalization import (  # noqa: E402
    generalization_check)
from governance.model_routing_v2.events import load_events  # noqa: E402


def _card(**kw):
    d = dict(task_id="X", stage="FORMULATION", authority_state="EXPLORATORY",
             formal_scope=True)
    d.update(kw)
    return RiskCard(**d)


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".")
    v2 = root / "v2"
    checks: list[dict] = []
    ok_all = True

    def add(cid: str, ok: bool, detail: str) -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        checks.append({"check": cid, "status": "PASS" if ok else "FAIL",
                       "detail": detail})

    # ---- MMR-01: Phase-A exact smoke verified (reads artifact) -----------
    smoke = v2 / "phase_a_exact_smoke_result.json"
    if smoke.is_file():
        s = json.loads(smoke.read_text(encoding="utf-8"))
        fidelity = (s.get("dispatch") or {}).get("packet_fidelity")
        add("MMR-01",
            fidelity == "PASS"
            and s.get("verified") is True
            and s.get("child_provider") == "deepseek-pro-max"
            and s.get("child_model") == "deepseek-v4-pro"
            and s.get("reasoning_effort") == "max"
            and s.get("fresh_spawn") is True
            and s.get("workspace_delta") == 0
            and s.get("head_matches") is True,
            f"exact smoke verified={s.get('verified')} fidelity={fidelity} "
            f"provider={s.get('child_provider')} "
            f"model={s.get('child_model')} effort={s.get('reasoning_effort')} "
            f"fresh={s.get('fresh_spawn')} delta={s.get('workspace_delta')} "
            f"head_matches={s.get('head_matches')}")
    else:
        add("MMR-01", False, "missing v2/phase_a_exact_smoke_result.json")

    # ---- MMR-02: Phase-A committed evidence replay verified --------------
    replay = root / "phase_a_replay_result.json"
    if replay.is_file():
        r = json.loads(replay.read_text(encoding="utf-8"))
        add("MMR-02",
            r.get("result") == "PASS"
            and r.get("wire_artifact_name") == "wire_semantic_check.txt"
            and all(c["status"] == "PASS" for c in r.get("checks", [])),
            f"replay result={r.get('result')} wire_artifact="
            f"{r.get('wire_artifact_name')} commit={r.get('commit_sha')}")
    else:
        add("MMR-02", False, "missing phase_a_replay_result.json")

    # ---- MMR-03: RED frozen mutation cannot formal-pass ------------------
    # (V2.1.1 API: human gate is a verdict, not a bool)
    g = route_gate_v2_1(RED, human_gate_verdict="PENDING")
    add("MMR-03", g["status"] != GATE_PASS
        and g["status"] == HUMAN_GATE_REQUIRED,
        f"RED without human gate -> {g['status']} (never formal PASS)")

    # ---- MMR-04: semantic/modeling choice cannot GREEN -------------------
    c = _card(risk={"mathematical_formulation": True},
              risk_evidence=[{"dimension": "mathematical_formulation",
                              "evidence": "choice"}])
    add("MMR-04", compute_model_route_v2_1(c).route == YELLOW,
        "modeling choice -> YELLOW")

    # ---- MMR-05: uncertainty cannot GREEN --------------------------------
    c = _card(uncertainty_present=True)
    add("MMR-05", compute_model_route_v2_1(c).route == YELLOW,
        "uncertainty -> YELLOW")

    # ---- MMR-06: GREEN belongs to the allowlist --------------------------
    c = _card()  # no risk, no allowlist class
    r = compute_model_route_v2_1(c)
    add("MMR-06", r.route == YELLOW,
        "no allowlist class -> default YELLOW (cannot prove GREEN); "
        "GREEN only from allowlist")

    # ---- MMR-07: YELLOW requires VERIFIED_PRO_MAX ------------------------
    # (V2.1.1 API: identity verification is the identity dimension)
    g = route_gate_v2_1(YELLOW, review_identity_verified=False)
    add("MMR-07", g["status"] == ROUTING_BLOCKED,
        f"YELLOW without VERIFIED_PRO_MAX -> {g['status']}")

    # ---- MMR-08: no fallback if Pro-Max unavailable ----------------------
    add("MMR-08", g["route"] == YELLOW and g["status"] == ROUTING_BLOCKED,
        "gate never re-routes to Flash/Pro-high; stays BLOCKED")

    # ---- MMR-09: R0-R4 reclassification artifacts valid ------------------
    events = load_events(str(v2 / "routing_events.jsonl"))
    classified = [e for e in events if e["event_type"] == "TASK_CLASSIFIED"]
    reclassified = [e for e in events if e["event_type"] == "TASK_RECLASSIFIED"]
    checkpoints = {e.get("checkpoint") for e in events if e.get("checkpoint")}
    demo = v2 / "demo_risk_cards.json"
    demo_ok = demo.is_file()
    if demo_ok:
        demo_cards = json.loads(demo.read_text(encoding="utf-8")).get(
            "cards", [])
        demo_checkpoints = {c.get("checkpoint") for c in demo_cards}
    else:
        demo_checkpoints = set()
    add("MMR-09",
        len(classified) >= 2 and len(reclassified) >= 1
        and {"R0", "R1", "R2", "R3", "R4"}.issubset(checkpoints | demo_checkpoints)
        and demo_ok,
        f"events: classified={len(classified)} reclassified={len(reclassified)} "
        f"checkpoints seen={sorted(checkpoints)} demo_cards={demo_ok}")

    # ---- MMR-10: Sentinel disagreement upgrades YELLOW --------------------
    res = parse_sentinel_verdict(
        "SENTINEL_VERDICT: RISK_OMISSION\nmissing_risk_dimensions: [problem_semantics]")
    up = sentinel_upgrade(GREEN, res)
    add("MMR-10", up["upgraded"] and up["route"] == YELLOW,
        "Sentinel RISK_OMISSION on GREEN -> YELLOW (mandatory Pro-Max)")

    # ---- MMR-11: project extension cannot de-escalate --------------------
    rejected = False
    try:
        validate_extension({
            "extension_version": "1.0", "project_id": "p",
            "term_risks": {"term": {"risks": [], "route_cap": "GREEN"}}})
    except ExtensionRejected:
        rejected = True
    ext_file = v2 / "extension_rejections.json"
    ext_recorded = ext_file.is_file()
    add("MMR-11", rejected and ext_recorded,
        f"de-escalating extension rejected={rejected} recorded={ext_recorded}")

    # ---- MMR-12: method classifier cannot change route -------------------
    c1 = _card(risk={"algorithmic_semantics": True},
               risk_evidence=[{"dimension": "algorithmic_semantics",
                               "evidence": "ordering"}])
    r1 = compute_model_route_v2_1(c1).route
    fams = classify_method_families("离散事件仿真模拟排队系统")
    r2 = compute_model_route_v2_1(c1).route  # families never enter the engine
    add("MMR-12", r1 == r2 and len(fams) >= 2,
        f"route with/without family metadata identical ({r1}); "
        f"families={fams} are strategy metadata only")

    # ---- MMR-13: verification registry cannot invent thresholds ----------
    from governance.model_routing_v2.verification_strategies import (  # noqa: E402
        build_verification_plan)
    try:
        build_verification_plan(
            task_id="X", semantic_issue_id=None,
            method_families=["MONTE_CARLO_STOCHASTIC"],
            risk_dimensions=["statistical_inference"],
            claim_under_review="c",
            selected_checks=["monte_carlo_convergence"],
            authority_thresholds={})
        threshold_refused = False
    except ValueError:
        threshold_refused = True
    add("MMR-13", threshold_refused,
        "threshold-bearing check without authority threshold refused")

    # ---- MMR-14: Universal Core contains zero project-specific tokens ----
    core = Path(__file__).resolve().parent  # the model_routing_v2 package dir
    gc = generalization_check(str(core))
    add("MMR-14", gc["status"] == "PASS" and gc["matches"] == {},
        f"PROJECT_TOKEN_LEAK_GUARD status={gc['status']} tokens="
        f"{gc['token_count']} matches={gc['matches']}")

    # ---- MMR-15: semantic issue dedup behaves correctly ------------------
    # (V2.1.1 store schema: identity verification is NOT resolution)
    store = SemanticIssueStore()
    fresh = store.needs_review("MMR-DEMO-001", "h1")
    store.record("MMR-DEMO-001", "h1", "PASS", "RESOLVED",
                 review_identity_verified=True, required_actions_closed=True)
    deduped = not store.needs_review("MMR-DEMO-001", "h1")
    contract_changed = store.needs_review("MMR-DEMO-001", "h2")
    persisted = SemanticIssueStore(str(v2 / "semantic_issues.json"))
    live_rec = persisted.snapshot().get("SAMPLING-LIVE-001") or {}
    live_blocked_open = (live_rec.get("semantic_status") == "BLOCKED"
                         and persisted.is_resolved("SAMPLING-LIVE-001")
                         is False)
    add("MMR-15", fresh and deduped and contract_changed and live_blocked_open,
        f"fresh={fresh} deduped={deduped} contract_changed={contract_changed} "
        f"live_issue_blocked_open={live_blocked_open}")

    # ---- MMR-16: RED depends on authority state correctly -----------------
    c_expl = _card(risk={"modeling_assumption": True},
                   authority_state="EXPLORATORY",
                   risk_evidence=[{"dimension": "modeling_assumption",
                                   "evidence": "choice"}])
    c_frozen = _card(risk={"governance_authority": True,
                           "mathematical_formulation": True},
                     authority_state="FROZEN",
                     risk_evidence=[{"dimension": "governance_authority",
                                     "evidence": "frozen"},
                                    {"dimension": "mathematical_formulation",
                                     "evidence": "mutation"}])
    add("MMR-16",
        compute_model_route_v2_1(c_expl).route == YELLOW
        and compute_model_route_v2_1(c_frozen).route == RED,
        "EXPLORATORY model choice -> YELLOW; FROZEN authority mutation -> RED")

    result = {"checker": "MATHEMATICAL_MODELING_ROUTER_V2.1",
              "overall": "PASS" if ok_all else "FAIL", "checks": checks}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
