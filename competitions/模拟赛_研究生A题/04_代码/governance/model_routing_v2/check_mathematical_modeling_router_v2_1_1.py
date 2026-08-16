#!/usr/bin/env python3
"""MATHEMATICAL_MODELING_ROUTER_V2.1.1 — repair checker R-01..R-22 (spec 20).

Every critical gate is COMPUTED from actual artifacts or from the router's
deterministic behaviour — never hard-coded PASS.

Usage: python check_mathematical_modeling_router_v2_1_1.py <evidence_root>

Evidence root: 05_结果/governance/model_routing
  phase_a_replay_result.json               (A1)
  v2/phase_a_exact_smoke_result.json       (A2)
  v2/routing_events.jsonl                  (R0-R4 + routing events)
  v2/semantic_issues.json                  (dedup store, V2.1.1 semantics)
  v2/demo_risk_cards.json                  (R0-R4 demo cards)
  v2/live_integration/routing_verification.json  (LIVE-001 BLOCKED)
  v2_1_1/sentinel_live_result.json         (§10 live Flash Sentinel)
  v2_1_1/sentinel_live_packet.txt

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
    GREEN, YELLOW, RED, ROUTING_BLOCKED, HUMAN_GATE_REQUIRED, GATE_PASS)
from governance.model_routing_v2.sentinel import (  # noqa: E402
    parse_sentinel_verdict, sentinel_upgrade)
from governance.model_routing_v2.method_families import (  # noqa: E402
    classify_method_families, DISCRETE_EVENT_SIMULATION)
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
    v211 = root / "v2_1_1"
    checks: list[dict] = []
    ok_all = True

    def add(cid: str, ok: bool, detail: str) -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        checks.append({"check": cid, "status": "PASS" if ok else "FAIL",
                       "detail": detail})

    # ---- R-01: YELLOW + verified identity + verdict BLOCKED cannot PASS ---
    g = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                          review_verdict="BLOCKED")
    add("R-01", g["status"] == ROUTING_BLOCKED,
        f"identity verified + verdict BLOCKED -> {g['status']}")

    # ---- R-02: YELLOW + PASS can PASS only with actions closed ------------
    g1 = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                           review_verdict="PASS", required_actions_closed=True)
    g2 = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                           review_verdict="PASS", required_actions_closed=False)
    add("R-02", g1["status"] == GATE_PASS and g2["status"] == ROUTING_BLOCKED,
        f"closed={g1['status']} open={g2['status']}")

    # ---- R-03: PASS_WITH_CAVEAT unresolved cannot PASS --------------------
    g1 = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                           review_verdict="PASS_WITH_CAVEAT",
                           required_actions_closed=False)
    g2 = route_gate_v2_1_1(YELLOW, review_identity_verified=True,
                           review_verdict="PASS_WITH_CAVEAT",
                           required_actions_closed=True)
    add("R-03", g1["status"] == ROUTING_BLOCKED
        and g2["status"] == GATE_PASS and g2.get("caveat_recorded") is True,
        f"caveat open={g1['status']} closed={g2['status']} "
        f"caveat_recorded={g2.get('caveat_recorded')}")

    # ---- R-04: BLOCKED semantic issue is not dedup-resolved ---------------
    store = SemanticIssueStore(str(v2 / "semantic_issues.json"))
    rec = store.snapshot().get("SAMPLING-LIVE-001") or {}
    blocked_not_resolved = (rec.get("semantic_status") == "BLOCKED"
                            and rec.get("review_verdict") == "BLOCKED"
                            and store.needs_pro_max("SAMPLING-LIVE-001",
                                                    "contract-v1") is True)
    add("R-04", blocked_not_resolved,
        f"semantic_status={rec.get('semantic_status')} "
        f"verdict={rec.get('review_verdict')} needs_pro_max="
        f"{store.needs_pro_max('SAMPLING-LIVE-001', 'contract-v1')}")

    # ---- R-05/06/07: Human Gate verdicts ----------------------------------
    g_pending = route_gate_v2_1_1(RED, human_gate_verdict="PENDING")
    g_rejected = route_gate_v2_1_1(RED, human_gate_verdict="REJECTED")
    g_accepted = route_gate_v2_1_1(RED, human_gate_verdict="ACCEPTED")
    add("R-05", g_pending["status"] == HUMAN_GATE_REQUIRED,
        f"PENDING -> {g_pending['status']}")
    add("R-06", g_rejected["status"] == ROUTING_BLOCKED,
        f"REJECTED -> {g_rejected['status']}")
    add("R-07", g_accepted["status"] == GATE_PASS,
        f"ACCEPTED -> {g_accepted['status']}")

    # ---- R-08/09: formal GREEN Sentinel enforcement ------------------------
    g_no = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                             sentinel_required=True)
    live = v211 / "sentinel_live_result.json"
    if live.is_file():
        sl = json.loads(live.read_text(encoding="utf-8"))
        sentinel_ok = (sl.get("sentinel_verdict") == "AGREE_GREEN"
                       and sl.get("execution", {}).get("identity_verified")
                       is True
                       and sl.get("gate", {}).get("status") == "PASS")
    else:
        sentinel_ok = False
    g_yes = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True,
                              sentinel_identity_verified=True,
                              sentinel_verdict="AGREE_GREEN")
    add("R-08", g_no["status"] == ROUTING_BLOCKED,
        f"formal GREEN without Sentinel -> {g_no['status']}")
    add("R-09", g_yes["status"] == GATE_PASS and sentinel_ok,
        f"formal GREEN with actual Sentinel AGREE_GREEN -> {g_yes['status']} "
        f"(live artifact ok={sentinel_ok})")

    # ---- R-10/11: Sentinel upgrades ----------------------------------------
    up_y = sentinel_upgrade(GREEN, {"verdict": "AGREE_YELLOW"})
    up_r = sentinel_upgrade(GREEN, {"verdict": "AGREE_RED"})
    add("R-10", up_y["route"] == YELLOW, f"GREEN+AGREE_YELLOW -> {up_y['route']}")
    add("R-11", up_r["route"] == RED, f"GREEN+AGREE_RED -> {up_r['route']}")

    # ---- R-12: malformed Sentinel fails closed -----------------------------
    try:
        parse_sentinel_verdict("no verdict present")
        malformed_rejected = False
    except ValueError:
        malformed_rejected = True
    g_mal = route_gate_v2_1_1(GREEN, checkpoint="R4", formal_scope=True,
                              sentinel_required=True,
                              sentinel_identity_verified=True,
                              sentinel_verdict=None)
    add("R-12", malformed_rejected and g_mal["status"] == ROUTING_BLOCKED,
        f"parse rejected={malformed_rejected} gate={g_mal['status']}")

    # ---- R-13: invalid Risk Card fails closed ------------------------------
    try:
        compute_model_route_v2_1_1(_card(risk={"data_semantics": True}))
        invalid_rejected = False
    except RiskCardInvalid:
        invalid_rejected = True
    add("R-13", invalid_rejected,
        "risk-flag-without-evidence card -> RiskCardInvalid (ROUTING_INVALID)")

    # ---- R-14: semantic risk cannot be hidden by frozen_mechanical_execution
    try:
        compute_model_route_v2_1_1(_card(
            risk={"statistical_inference": True},
            frozen_mechanical_execution=True,
            risk_evidence=[{"dimension": "statistical_inference",
                            "evidence": "choice"}]))
        bypass_open = True
    except RiskCardInvalid:
        bypass_open = False
    add("R-14", not bypass_open,
        "frozen_mechanical_execution + flagged semantic risk is rejected "
        "(no global bypass)")

    # ---- R-15: risk_evidence/flag contradiction rejected -------------------
    try:
        compute_model_route_v2_1_1(_card(
            risk_evidence=[{"dimension": "data_semantics",
                            "evidence": "flag false"}]))
        contradiction_rejected = False
    except RiskCardInvalid:
        contradiction_rejected = True
    add("R-15", contradiction_rejected,
        "evidence referencing a false dimension is rejected (fail-closed)")

    # ---- R-16..20: Chinese method classification ---------------------------
    add("R-16", "OPTIMIZATION" in classify_method_families(
        "建立整数规划模型求最优调度方案"),
        "Chinese optimization classification")
    add("R-17", "PROBABILITY_STATISTICS" in classify_method_families(
        "概率统计中的假设检验与置信区间"),
        "Chinese statistics classification")
    add("R-18", "ODE_PDE_DYNAMICAL_SYSTEM" in classify_method_families(
        "建立微分方程描述运动过程") and
        "PHYSICS_MECHANISM" in classify_method_families(
            "建立微分方程描述运动过程"),
        "Chinese physics/ODE classification")
    add("R-19", DISCRETE_EVENT_SIMULATION in classify_method_families(
        "建立离散事件仿真模拟排队系统"),
        "Chinese DES classification")
    add("R-20", "MULTI_CRITERIA_EVALUATION" in classify_method_families(
        "使用TOPSIS和熵权法进行综合评价"),
        "Chinese MCDM classification")

    # ---- R-21: generic simulation alone does not imply DES ----------------
    generic_not_des = (DISCRETE_EVENT_SIMULATION
                       not in classify_method_families(
                           "simulation of the whole system"))
    chinese_not_des = (DISCRETE_EVENT_SIMULATION
                       not in classify_method_families("对系统整体进行仿真"))
    add("R-21", generic_not_des and chinese_not_des,
        f"generic EN simulation not DES={generic_not_des}; "
        f"generic CN simulation not DES={chinese_not_des}")

    # ---- R-22: AGENTS routing precedence explicit --------------------------
    agents = (Path(__file__).resolve().parents[3] / "AGENTS.md")  # project root
    if agents.is_file():
        text = agents.read_text(encoding="utf-8")
        precedence_ok = (
            "MATHEMATICAL_MODELING_ROUTER_V2.1.1" in text
            and ("是通用数学建模路由权威" in text or "authoritative" in text)
            and "MODEL_ROUTING_PRO_MAX_V1.0" in text)
    else:
        precedence_ok = False
    add("R-22", precedence_ok,
        "AGENTS.md declares MMR V2.1.1 as the universal modeling routing "
        "authority with explicit precedence")

    result = {"checker": "MATHEMATICAL_MODELING_ROUTER_V2.1.1",
              "overall": "PASS" if ok_all else "FAIL", "checks": checks}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
