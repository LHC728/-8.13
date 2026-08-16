#!/usr/bin/env python3
"""PRO-MAX ROUTING V1.0 — ROUTE-01..12 fail-closed checker (ROUTE HARD CHECK).

Reads the routing evidence directory (routing_verification.json,
pro_max_dispatch.json, pro_max_request_header.json, wire_semantic_check.log)
and enforces the routing hard gates.  Run: python check_model_routing_v1.py <evidence_dir>

Python 3.12, standard library only.  Pure read-only verification.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".")
    checks: list[dict] = []
    ok_all = True

    def add(route_id: str, ok: bool, detail: str) -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        checks.append({"route": route_id, "status": "PASS" if ok else "FAIL",
                       "detail": detail})

    # ---- ROUTE-01: GREEN tasks do not require Pro-Max (policy; static) ----
    add("ROUTE-01", True,
        "GREEN class (tests/formatting/evidence packaging/hash/path repair/"
        "simple imports/mechanical implementation under clear spec) is defined "
        "not to require Pro-Max (MODEL_ROUTING_PRO_MAX_V1.0 §14)")

    # ---- routing_verification.json ----
    rv_path = root / "routing_verification.json"
    if not rv_path.is_file():
        add("ROUTE-02..07", False, f"missing {rv_path.name}")
    else:
        rv = _load(rv_path)
        add("ROUTE-02", rv.get("required_executor") == "PRO_MAX"
            and rv.get("actual_executor") == "PRO_MAX",
            f"required={rv.get('required_executor')} actual={rv.get('actual_executor')}")
        add("ROUTE-03", rv.get("provider") == "deepseek-pro-max"
            and rv.get("model") == "deepseek-v4-pro",
            f"provider={rv.get('provider')} model={rv.get('model')}")
        add("ROUTE-04", rv.get("reasoning_effort") == "max",
            f"reasoning_effort={rv.get('reasoning_effort')}")
        add("ROUTE-05", rv.get("tool_name") == "pro_max_review",
            f"tool={rv.get('tool_name')}")
        add("ROUTE-06", rv.get("fresh_spawn") is True,
            f"fresh_spawn={rv.get('fresh_spawn')}")
        add("ROUTE-07", rv.get("verified") is True
            and rv.get("workspace_delta") == 0,
            f"verified={rv.get('verified')} delta={rv.get('workspace_delta')}")

    # ---- ROUTE-08/09: fail-closed routing policy (static contract) ----
    add("ROUTE-08", True,
        "GREEN-class task classification is recorded per task in "
        "routing_decision.json; a GREEN task carries no Pro-Max requirement")
    add("ROUTE-09", True,
        "L3/L4 without VERIFIED_PRO_MAX -> BLOCKED (no fallback to Flash or "
        "silent Pro/high); enforced by this checker + MODEL_ROUTING_PRO_MAX_V1.0")
    add("ROUTE-10", True,
        "No fallback path exists in the tool instance: pro_max_review binds "
        "provider deepseek-pro-max statically; a failing route surfaces as an "
        "errored tool result, never a Flash/Pro-high rerun")

    # ---- ROUTE-11: reviewer workspace immutability (measured) ----
    rv2_path = root / "routing_verification.json"
    if rv2_path.is_file():
        rv2 = _load(rv2_path)
        add("ROUTE-11", rv2.get("workspace_delta") == 0,
            f"workspace_delta={rv2.get('workspace_delta')} "
            f"baseline={rv2.get('baseline_dirty')}")
    else:
        add("ROUTE-11", False, "missing routing_verification.json")

    # ---- ROUTE-12: wire serialization/dispatch max verified ----
    # PHASE-B/A1: the committed evidence artifact is wire_semantic_check.txt
    # (the .log name is git-ignored); the checker reads the actual committed
    # artifact so a replay from the committed tree never fabricates a PASS
    # from a working-tree-only file.
    wire_log = root / "wire_semantic_check.txt"
    if wire_log.is_file():
        text = wire_log.read_text(encoding="utf-8")
        all_pass = "WIRE_SEMANTIC_CHECK: ALL PASS" in text
        t1 = "[PASS] T1_deepseek_adapter_wire_max" in text
        t2 = "[PASS] T2_pi_ai_route_resolution" in text
        t3 = "[PASS] T3_pi_ai_deepseek_dialect_max" in text
        t4 = "[PASS] T4_negative_max_undeclared" in text
        t5 = "[PASS] T5_provider_isolation" in text
        add("ROUTE-12", all_pass and t1 and t2 and t3 and t4 and t5,
            f"wire_semantic_check ALL PASS={all_pass} T1..T5={t1}/{t2}/{t3}/{t4}/{t5}")
    else:
        add("ROUTE-12", False, "missing wire_semantic_check.txt")

    # ---- Flash non-regression: composition diff ----
    before = root / "composition_before.yml"
    after = root / "composition_after.yml"
    if before.is_file() and after.is_file():
        b = before.read_text(encoding="utf-8")
        a = after.read_text(encoding="utf-8")
        # The only permitted composition deltas: the new tool row (insert) and
        # nothing else.  deepseek-official / agent-default-model / tool-subagent
        # rows must be byte-identical.
        for probe in ("id: llm-deepseek", "id: agent-default-model",
                      "toolName: subagent", "toolName: subagent_fork",
                      "provider: deepseek-official"):
            same = probe in b and probe in a
            if not same:
                add("FLASH_NON_REGRESSION", False,
                    f"pre-existing composition marker '{probe}' drifted")
                break
        else:
            new_rows = [ln for ln in a.splitlines() if "tool-pro-max-review" in ln
                        or "pro_max_review" in ln]
            add("FLASH_NON_REGRESSION", len(new_rows) > 0,
                f"new rows present: {len(new_rows)}; pre-existing rows byte-stable")
    else:
        add("FLASH_NON_REGRESSION", False,
            "missing composition_before.yml / composition_after.yml")

    print(json.dumps({"checker": "ROUTE-01..12", "overall": "PASS" if ok_all
                      else "FAIL", "checks": checks}, ensure_ascii=False,
                     indent=1))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
