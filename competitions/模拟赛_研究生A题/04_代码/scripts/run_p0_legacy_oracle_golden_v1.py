#!/usr/bin/env python3
"""P0: generate the legacy key_schema_v1 golden fixture from the EXACT
pre-change oracle implementation (P0 / H2 key schema bootstrap).

The golden expected values MUST come from the pre-change oracle only:

    oracle_commit  = 1de71824e668f3815f58112cb3c42c9633b2da16
    oracle_blob_sha = 8a8f10895ee9751fb7c3c93093c3cdac25b4b632
                      (04_代码/main_model/g3/key_schema_v1.py at that commit)

Regenerate from that commit:

    git cat-file blob 8a8f10895ee9751fb7c3c93093c3cdac25b4b632 \\
        > /tmp/p0_legacy_oracle/key_schema_v1.py
    python run_p0_legacy_oracle_golden_v1.py \\
        /tmp/p0_legacy_oracle/key_schema_v1.py

Verify the extracted file with: git hash-object <file> == 8a8f1089...

This script uses ONLY the oracle module (loaded by path); it never imports
the current (possibly modified) implementation. The emitted fixture is
frozen evidence: do NOT regenerate expected values from the new
implementation and overwrite it.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ORACLE_COMMIT = "1de71824e668f3815f58112cb3c42c9633b2da16"
ORACLE_BLOB_SHA = "8a8f10895ee9751fb7c3c93093c3cdac25b4b632"

PROJECT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    PROJECT / "04_代码" / "tests" / "fixtures" / "g3_key_schema_legacy_golden_v1.json"
)


def load_oracle(oracle_path: str):
    p = Path(oracle_path).resolve()
    if not p.is_file():
        raise SystemExit(f"oracle file not found: {p}")
    spec = importlib.util.spec_from_file_location("_p0_legacy_oracle", p)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load oracle module from {p}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hex_utf8(s: str) -> str:
    return s.encode("utf-8").hex()


def collect(k: dict, family: str, helper: str, args: dict, canonical: str, frac) -> None:
    k["vectors"].append(
        {
            "family": family,
            "helper": helper,
            "args": args,
            "canonical_key": canonical,
            "canonical_utf8_hex": hex_utf8(canonical),
            "fraction_num": frac.numerator,
            "fraction_den": frac.denominator,
        }
    )


def build_vectors(k, oracle) -> None:
    namespaces = tuple(oracle.NAMESPACES)
    seeds = (0, 3, 65537)
    reps = (0, 199)

    # U_X: namespace x device x subsystem x seed x replicate
    for ns in namespaces:
        for device in (1, 100, 1000):
            for sub in ("A", "B", "C"):
                for seed in seeds:
                    for rep in reps:
                        u = oracle.u_x(ns, rep, device, sub, seed)
                        collect(
                            k, "U_X", "u_x",
                            {"namespace": ns, "rep": rep, "device": device,
                             "subsystem": sub, "seed": seed},
                            oracle.canonical_key(ns, rep, device, sub, None, seed), u,
                        )
    # U_D: namespace x device x seed x replicate
    for ns in namespaces:
        for device in (1, 7, 1000):
            for seed in (0, 3):
                for rep in reps:
                    u = oracle.u_d(ns, rep, device, seed)
                    collect(
                        k, "U_D", "u_d",
                        {"namespace": ns, "rep": rep, "device": device, "seed": seed},
                        oracle.canonical_key(ns, rep, device, None, None, seed), u,
                    )
    # U_Y: namespace x device x process x attempt x seed x replicate
    for ns in namespaces:
        for device in (1, 100):
            for proc in ("A", "C", "E"):
                for attempt in (1, 3):
                    for rep in (0, 199):
                        u = oracle.u_y(ns, rep, device, proc, attempt, 3)
                        collect(
                            k, "U_Y", "u_y",
                            {"namespace": ns, "rep": rep, "device": device,
                             "process": proc, "attempt": attempt, "seed": 3},
                            oracle.canonical_key(ns, rep, device, proc, attempt, 3), u,
                        )
    # U_L: namespace x resource x generation x seed x replicate
    for ns in namespaces:
        for res in ("A", "B", "E"):
            for gen in (1, 240):
                for seed in (0, 65537):
                    u = oracle.u_l(ns, 1, res, gen, seed)
                    collect(
                        k, "U_L", "u_l",
                        {"namespace": ns, "rep": 1, "resource": res,
                         "generation": gen, "seed": seed},
                        oracle.canonical_key(ns, 1, res, None, gen, seed), u,
                    )
    # canonical_key pure-serializer cases (incl. h2_future placeholder and
    # boundary values) — the serializer contract is part of the frozen API.
    serializer_cases = [
        ("development_unit", 0, 1, None, None, 0),
        ("pilot", 1, 7, "B", None, 1),
        ("h1_tuning", 3, 100, "E", 2, 1 << 31),
        ("g3_holdout", 199, 1000, "A", 3, 65537),
        ("q2_formal", 0, "res7", "C", None, 3),
        ("q3_formal", 99, 100, None, 5, 20260815),
        (oracle.H2_RESERVED_NAMESPACE, 0, 1, None, None, 0),
        ("q3_formal", 99, 100, "E", 2, 1 << 63),
    ]
    for ns, rep, ent, proc, att, seed in serializer_cases:
        key = oracle.canonical_key(ns, rep, ent, proc, att, seed)
        frac = oracle.uniform_from_key(key)
        collect(
            k, "CANONICAL_KEY", "canonical_key",
            {"namespace": ns, "rep": rep, "entity": ent, "process_or_subsystem": proc,
             "attempt_or_generation": att, "seed": seed},
            key, frac,
        )


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("oracle_path", help="path to the pre-change key_schema_v1.py")
    args = ap.parse_args(argv[1:])

    oracle = load_oracle(args.oracle_path)
    if oracle.KEY_SCHEMA_VERSION != "key_schema_v1":
        raise SystemExit("oracle KEY_SCHEMA_VERSION mismatch")
    if len(oracle.NAMESPACES) != 6:
        raise SystemExit("oracle NAMESPACES must be the frozen six")

    k = {
        "fixture": "g3_key_schema_legacy_golden_v1",
        "oracle_commit": ORACLE_COMMIT,
        "oracle_blob_sha": ORACLE_BLOB_SHA,
        "oracle_key_schema_version": oracle.KEY_SCHEMA_VERSION,
        "oracle_mapping": oracle.MAPPING_DESCRIPTION,
        "generator": "04_代码/scripts/run_p0_legacy_oracle_golden_v1.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "legacy_namespaces": list(oracle.NAMESPACES),
        "h2_reserved_placeholder": oracle.H2_RESERVED_NAMESPACE,
        "vectors": [],
    }
    build_vectors(k, oracle)
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps(k, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {FIXTURE_PATH}")
    print(f"vectors={len(k['vectors'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
