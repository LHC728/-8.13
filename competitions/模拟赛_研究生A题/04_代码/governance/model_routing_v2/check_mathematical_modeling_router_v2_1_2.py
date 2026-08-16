#!/usr/bin/env python3
"""MATHEMATICAL_MODELING_ROUTER_V2.1.2 — FINAL HARDENING checker F-01..F-15.

Every critical gate is COMPUTED from actual artifacts or from the router's
deterministic behaviour — never hard-coded PASS.

Usage: python check_mathematical_modeling_router_v2_1_2.py <evidence_root>

Evidence root: 05_结果/governance/model_routing
  v2_1_2/sentinel_request_header.json   (§5 actual request/header receipt)
  v2_1_2/fixtures/frozen_solver_fixture_spec.json (§3 fixture authority)
  v2/semantic_issues.json               (dedup store)
  v2/routing_events.jsonl

Python 3.12, standard library only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 04_代码
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # governance pkg

from governance.model_routing_v2.risk_card import (  # noqa: E402
    RiskCard, RiskCardInvalid)
from governance.model_routing_v2.route_engine import (  # noqa: E402
    compute_model_route_v2_1_1, route_gate_v2_1_1, SemanticIssueStore,
    verify_authority_receipts,
    GREEN, YELLOW, RED, ROUTING_BLOCKED, HUMAN_GATE_REQUIRED, GATE_PASS)
from governance.model_routing_v2.generalization import (  # noqa: E402
    generalization_check)


def _card(**kw):
    d = dict(task_id="X", stage="FORMULATION", authority_state="EXPLORATORY",
             formal_scope=True)
    d.update(kw)
    return RiskCard(**d)


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".")
    v2 = root / "v2"
    v212 = root / "v2_1_2"
    PROJECT = Path(__file__).resolve().parents[3]  # project root
    checks: list[dict] = []
    ok_all = True

    def add(cid: str, ok: bool, detail: str) -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        checks.append({"check": cid, "status": "PASS" if ok else "FAIL",
                       "detail": detail})

    # ---- F-01/02/03: authority_conflict fails closed (§1) -----------------
    g_pass = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                               review_verdict="PASS",
                               required_actions_closed=True,
                               authority_conflict=True)
    g_cav = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict="PASS_WITH_CAVEAT",
                              required_actions_closed=True,
                              authority_conflict=True)
    add("F-01", g_pass["status"] != GATE_PASS,
        f"PASS + authority_conflict -> {g_pass['status']} (cannot PASS)")
    add("F-02", g_cav["status"] != GATE_PASS,
        f"PASS_WITH_CAVEAT + authority_conflict -> {g_cav['status']} "
        "(cannot PASS)")
    add("F-03", g_pass["status"] == HUMAN_GATE_REQUIRED
        and g_cav["status"] == HUMAN_GATE_REQUIRED,
        f"authority_conflict -> {HUMAN_GATE_REQUIRED} (both verdicts)")

    # ---- F-04/05/06: authority-backed GREEN (§2) ---------------------------
    def try_route(card):
        try:
            return compute_model_route_v2_1_1(card).route
        except RiskCardInvalid:
            return "INVALID"

    c_expl = _card(authority_state="EXPLORATORY",
                   green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                   frozen_mechanical_execution=True, authority_refs=["r"])
    c_prop = _card(authority_state="PROPOSED",
                   green_allowlist_class="MECHANICAL_FORMULA_IMPLEMENTATION_UNDER_FROZEN_EXACT_FORMULA",
                   frozen_mechanical_execution=True, authority_refs=["r"])
    c_froz = _card(authority_state="FROZEN",
                   green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                   frozen_mechanical_execution=True,
                   authority_refs=["frozen solver spec"])
    add("F-04", try_route(c_expl) == "INVALID",
        "EXPLORATORY + UNDER_FROZEN_CONFIG is invalid")
    add("F-05", try_route(c_prop) == "INVALID",
        "PROPOSED + UNDER_FROZEN_EXACT_FORMULA is invalid")
    add("F-06", try_route(c_froz) == GREEN,
        "FROZEN + valid authority ref can qualify for mechanical GREEN")

    # ---- F-07/08: authority receipts (§3/§6) -------------------------------
    fixture_rel = "05_结果/governance/model_routing/v2_1_2/fixtures/" \
                  "frozen_solver_fixture_spec.json"
    c_good = _card(authority_state="FROZEN",
                   green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                   frozen_mechanical_execution=True,
                   authority_refs=[fixture_rel],
                   authority_receipts=[{
                       "ref": fixture_rel, "authority_state": "FROZEN"}])
    c_missing = _card(authority_state="FROZEN",
                      green_allowlist_class="MECHANICAL_SOLVER_EXECUTION_UNDER_FROZEN_CONFIG",
                      frozen_mechanical_execution=True,
                      authority_refs=[fixture_rel],
                      authority_receipts=[{
                          "ref": "does/not/exist.json",
                          "authority_state": "FROZEN"}])
    rec_good = verify_authority_receipts(c_good, str(PROJECT))
    rec_missing = verify_authority_receipts(c_missing, str(PROJECT))
    g_f07 = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True,
                              sentinel_identity_verified=True,
                              sentinel_verdict="AGREE_GREEN",
                              authority_receipt_verified=False)
    g_f08 = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True,
                              sentinel_identity_verified=True,
                              sentinel_verdict="AGREE_GREEN",
                              authority_receipt_verified=True)
    add("F-07", rec_missing["status"] == "FAIL"
        and g_f07["status"] == ROUTING_BLOCKED,
        f"missing authority file: receipt={rec_missing['status']} "
        f"gate={g_f07['status']}")
    add("F-08", rec_good["status"] == "PASS"
        and g_f08["status"] == GATE_PASS,
        f"valid authority receipt: receipt={rec_good['status']} "
        f"gate={g_f08['status']} (proceeds to Sentinel Gate)")

    # ---- F-09/10: Sentinel runtime identity receipt (§5/§6) ----------------
    srh = v212 / "sentinel_request_header.json"
    if srh.is_file():
        hdr = json.loads(srh.read_text(encoding="utf-8"))
        hcfg = hdr.get("request_header", {}).get("config", {})
        runtime_receipt = (hdr.get("identity_verified") is True
                           and hcfg.get("provider") == "deepseek-official"
                           and hcfg.get("model") == "deepseek-v4-flash"
                           and hdr.get("fresh_spawn") is True
                           and hdr.get("source", "").startswith("session JSONL"))
    else:
        runtime_receipt = False
    g_f10 = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True,
                              sentinel_identity_verified=True,
                              sentinel_verdict="AGREE_GREEN",
                              authority_receipt_verified=True)
    # F-10: caller booleans alone must not pass at the formal checker layer:
    # the checker requires the actual receipt artifact to exist.
    add("F-09", runtime_receipt,
        f"Sentinel runtime identity receipt based on actual session evidence "
        f"({srh.name}): ok={runtime_receipt}")
    add("F-10", runtime_receipt and g_f10["status"] == GATE_PASS,
        "formal GREEN passes only with receipt verification (artifact "
        "present + booleans consistent)")

    # ---- F-11/12/13: BLOCKED dedup semantics (§7) --------------------------
    store = SemanticIssueStore(str(v2 / "semantic_issues.json"))
    rec = store.snapshot().get("SAMPLING-LIVE-001") or {}
    f11 = (rec.get("semantic_status") == "BLOCKED"
           and store.is_resolved("SAMPLING-LIVE-001") is False)
    f12 = (store.needs_review("SAMPLING-LIVE-001", "contract-v1") is False)
    f13 = (store.needs_review("SAMPLING-LIVE-001", "contract-v2") is True
           or store.needs_review("SAMPLING-LIVE-001", "contract-v1",
                                 rereview_signals={
                                     "new_counterexample": True}) is True)
    add("F-11", f11, f"BLOCKED issue unresolved: {rec.get('semantic_status')}")
    add("F-12", f12,
        "BLOCKED unchanged issue does not automatically re-call Pro-Max")
    add("F-13", f13,
        "new contract/evidence can reopen review")

    # ---- F-14: Phase-A route unchanged ------------------------------------
    # Deterministic check of the Phase-A configuration facts recorded in the
    # Phase-A precheck: route id/model/credential/endpoint/reasoning must
    # still match (user-level config files are read-only here).
    import os
    settings = Path(os.path.expanduser("~")) / ".dsh" / "settings.yaml"
    patch = Path(os.path.expanduser("~")) / ".dsh" / "cordis.patch.yml"
    f14 = False
    if settings.is_file() and patch.is_file():
        s = settings.read_text(encoding="utf-8")
        p = patch.read_text(encoding="utf-8")
        f14 = ("deepseek-pro-max" in s and "deepseek-v4-pro" in s
               and "reasoning: max" in s
               and "pro_max_review" in p and "deepseek-pro-max" in p
               and "deepseek-official" in s)
    add("F-14", f14,
        "Phase-A route unchanged (deepseek-pro-max/deepseek-v4-pro/reasoning "
        "max/pro_max_review configs intact; deepseek-official intact)")

    # ---- F-15: V2.1.1 core behavior non-regression -------------------------
    # key V2.1.1 behaviors recomputed: identity/outcome gate, leak guard,
    # bilingual classifier, never-de-escalate sentinel.
    from governance.model_routing_v2.method_families import (  # noqa: E402
        classify_method_families, DISCRETE_EVENT_SIMULATION)
    from governance.model_routing_v2.sentinel import (  # noqa: E402
        sentinel_upgrade)
    core = Path(__file__).resolve().parent
    lg = generalization_check(str(core))
    f15 = (
        route_gate_v2_1_1(YELLOW, review_identity_verified=False)["status"]
        == ROUTING_BLOCKED
        and route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                              review_verdict="BLOCKED")["status"]
        == ROUTING_BLOCKED
        and route_gate_v2_1_1(RED, human_gate_verdict="PENDING")["status"]
        == HUMAN_GATE_REQUIRED
        and lg["status"] == "PASS"
        and "OPTIMIZATION" in classify_method_families("建立整数规划模型")
        and DISCRETE_EVENT_SIMULATION not in classify_method_families(
            "simulation of the whole system")
        and sentinel_upgrade(YELLOW, {"verdict": "AGREE_GREEN"})["route"]
        == YELLOW
    )
    add("F-15", f15,
        "V2.1.1 core behaviors non-regressed (identity/outcome gate, leak "
        "guard, bilingual classifier, DES refinement, sentinel never-de-"
        "escalate)")

    result = {"checker": "MATHEMATICAL_MODELING_ROUTER_V2.1.2",
              "overall": "PASS" if ok_all else "FAIL", "checks": checks}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
