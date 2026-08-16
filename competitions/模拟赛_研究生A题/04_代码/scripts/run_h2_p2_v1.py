#!/usr/bin/env python3
"""Q3-H2-P2 evidence runner: posterior + conditional-lifetime generators.

Runs:
  * posterior PRIMARY deterministic checker (h2_posterior_checker_v1);
  * lifetime PRIMARY deterministic checker (h2_residual_lifetime_checker_v1);
  * P2 unit tests (test_h2_p2_v1.py) + P1 firewall regressions +
    deterministic regressions (key_schema / Density E2 / Q3 H1 / G3);
  * frozen SECONDARY stochastic smokes (section 8: 8 patterns x N=5000 x
    32 marginal z, accept #(|z|>3.5)<=1; section 9: 4 resources x 8 ages x
    N=2000, Pearson chi-square, accept #(p<0.001)<=1);
  * C23 P2 checks (same observable history -> identical posterior; same
    key -> identical sampled hidden state);
then writes an immutable evidence root with the acyclic hash DAG,
semantic evidence mapping and fail-closed verification (verified staging
promoted byte-identical to the final root; post-promotion read-only
re-verify).

Random streams (frozen): namespace=h2_tuning, master_seed=6, U_X_post /
U_D_post / U_L_post ONLY (never U_Y_post, never h2_holdout, never
q3_formal).  Actual namespace/seed/replicate/keys are recorded.

Evidence root: 05_结果/H2/p2/run_<UTC>_<8hex>/

Python 3.12, standard library only.
"""
from __future__ import annotations

import io
import json
import math
import secrets
import shutil
import sys
import time
import unittest
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from g3 import key_schema_v1 as ks  # noqa: E402
from scripts import run_q3_h1_formal_v1 as frm  # noqa: E402
from main_model.h2 import frozen_params_v1 as fp  # noqa: E402
from main_model.h2 import posterior_generator_v1 as pg  # noqa: E402
from main_model.h2 import lifetime_generator_v1 as lg  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from checker import h2_posterior_checker_v1 as pchk  # noqa: E402
from checker import h2_residual_lifetime_checker_v1 as lchk  # noqa: E402

PACKAGE_REF = "Q3-H2-P2"
BOOTSTRAP_SPEC_FILE = frm.BOOTSTRAP_SPEC_FILE
FORMAL_TASK_PACKAGE_FILE = frm.TASK_PACKAGE_FILE
FORMAL_TASK_PACKAGE_SHA = frm.TASK_PACKAGE_SNAPSHOT_SHA
REGISTRY_VERSION = "CR-V3.1"

# frozen random streams for generator validation (SPEC section 6.1 / P2-E1)
# P2-E1 F1: replicate_id MUST be in {0,1,2,3,4} ONLY; N=5000/2000 are
# sample counts, NOT replicate ids (mapping: replicate = sample_idx % 5;
# synthetic entity/generation slot = 100001 + idx*1000 + sample_idx//5).
NS = ks.NAMESPACE_H2_TUNING          # "h2_tuning"
SEED = 6
VALID_REPLICATES = (0, 1, 2, 3, 4)
POST_SAMPLES = tuple(range(5000))   # posterior smoke N=5000 per pattern
LIFE_SAMPLES = tuple(range(2000))   # lifetime smoke N=2000 per config
ENTITY_BASE = 100001                # validation-only synthetic slot base

SCOPE_AUDIT = {
    "density_accepted_evidence_modified": "NO",
    "h1_engine_semantics_modified": "NO",
    "key_schema_modified": "NO",
    "posterior_math_implemented": "YES (SPEC section 8, frozen)",
    "conditional_lifetime_implemented": "YES (SPEC section 9, frozen)",
    "h2_policy_implemented": "NO",
    "rollout_implemented": "NO",
    "q_hat": "NO", "m_selection": "NO", "c_eval": "NO", "quota": "NO",
    "h2_holdout": "NOT USED",
    "u_y_post_consumed": "NO",
    "new_random_worlds": "NO",
    "random_streams": {
        "namespace": NS, "master_seed": SEED,
        "replicate_ids": [0, 1, 2, 3, 4],
        "posterior_smoke": "8 patterns x N=5000 (replicate=sample_idx%5, "
                           "synthetic entity=100001+pat*1000+sample_idx//5)",
        "lifetime_smoke": "32 configs x N=2000 (replicate=sample_idx%5, "
                          "synthetic generation=100001+sample_idx//5)",
        "streams": ["U_X_post", "U_D_post", "U_L_post"],
        "h2_holdout_used": False, "q3_formal_used": False,
        "u_y_post_used": False,
    },
    "c25": "NO", "q4": "NO",
}

REGRESSION_PATTERNS = (
    "test_h2_p1_firewall_v1.py",
    "test_h2_q3_density_v1.py",
    "test_g3_key_schema_v1.py",
    "test_q3_h1_formal_v1.py",
    "test_g3_random_des_v1.py",
)

REPORT_MAPPING: dict[str, str] = {
    "POSTERIOR_PRIMARY_DETERMINISTIC": "posterior_deterministic_report.json",
    "POSTERIOR_D_COROLLARY": "posterior_d_corollary_report.json",
    "POSTERIOR_SAME_OBSERVABLE_HISTORY": "posterior_same_observable_report.json",
    "POSTERIOR_STOCHASTIC_SMOKE": "posterior_smoke_report.json",
    "POSTERIOR_RANDOM_DOMAIN": "posterior_random_domain_report.json",
    "LIFETIME_PRIMARY_DETERMINISTIC": "lifetime_deterministic_report.json",
    "LIFETIME_AGE0_DEGENERATE": "lifetime_age0_degenerate_report.json",
    "LIFETIME_240_BOUNDARY": "lifetime_240_boundary_report.json",
    "LIFETIME_STOCHASTIC_SMOKE": "lifetime_smoke_report.json",
    "LIFETIME_RANDOM_DOMAIN": "lifetime_random_domain_report.json",
    "C23_P2": "c23_p2_report.json",
    "EVIDENCE_SEMANTIC_MAPPING": "evidence_semantic_mapping_report.json",
}


# ---------------------------------------------------------------------------
# Secondary stochastic smokes
# ---------------------------------------------------------------------------


def posterior_smoke() -> dict[str, Any]:
    """Frozen section-8 secondary smoke: 8 representative patterns x
    N=5000 stratified draws; 32 marginal z statistics; accept
    #(|z|>3.5) <= 1.  P2-E1 F1: replicate_id = sample_idx % 5 (in
    {0..4}); validation-only synthetic entity_id =
    100001 + pattern_idx*1000 + sample_idx//5 (5 replicates x 1000 entity
    slots = 5000 samples)."""
    N = len(POST_SAMPLES)
    pats = []
    for oa in ((), ("N",), ("A",), ("A", "N"), ("A", "A")):
        pats.append(("A-only", oa, (), (), ()))
    for oe in ((), ("N",), ("A",)):
        pats.append(("E-layer", ("N",), ("N",), ("N",), oe))
    rows = []
    z_list: list[float] = []
    used_reps: set[int] = set()
    used_entities: set[int] = set()
    for pat_idx, (label, oa, ob, oc, oe) in enumerate(pats):
        abc_post = pg.abc_posterior_8(
            {"A": oa, "B": ob, "C": oc}, oe)
        pi_abc = {
            "A": sum(p for (xa, _b, _c), p in abc_post.items() if xa == 1),
            "B": sum(p for (_a, xb, _c), p in abc_post.items() if xb == 1),
            "C": sum(p for (_a, _b, xc), p in abc_post.items() if xc == 1),
        }
        pi_d = sum(abc_post[abc] * pg.d_given_abc(oe, abc)
                   for abc in abc_post)
        pi = {"A": pi_abc["A"], "B": pi_abc["B"], "C": pi_abc["C"],
              "D": pi_d}
        counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        for sample_idx in POST_SAMPLES:
            rep = sample_idx % 5
            entity = ENTITY_BASE + pat_idx * 1000 + sample_idx // 5
            used_reps.add(rep)
            used_entities.add(entity)
            ua = ks.u_x_post(NS, rep, entity, "A", SEED)
            abc = pg.sample_abc(abc_post, ua)  # one U_X_post for ABC draw
            # NOTE: the stratified ABC draw uses a single U_X_post for the
            # ABC posterior (frozen: one draw from the ABC posterior).
            u_d = ks.u_d_post(NS, rep, entity, SEED)
            xd = pg.sample_d(oe, abc, u_d)
            counts["A"] += abc[0]
            counts["B"] += abc[1]
            counts["C"] += abc[2]
            counts["D"] += xd
        for sub in ("A", "B", "C", "D"):
            p_hat = counts[sub] / N
            p = pi[sub]
            se = math.sqrt(float(p) * (1.0 - float(p)) / N)
            z = (p_hat - float(p)) / se if se > 0 else 0.0
            z_list.append(z)
            rows.append({"pattern": label, "obs": {
                "A": list(oa), "B": list(ob), "C": list(oc),
                "E": list(oe)}, "subsystem": sub, "p_hat": p_hat,
                "pi": float(p), "z": z, "n": N})
    n_extreme = sum(1 for z in z_list if abs(z) > 3.5)
    return {
        "check": "POSTERIOR_STOCHASTIC_SMOKE",
        "status": "PASS" if n_extreme <= 1 else "FAIL",
        "n_statistics": len(z_list),
        "n_abs_z_gt_3.5": n_extreme,
        "acceptance": "#(|z|>3.5) <= 1",
        "n_per_pattern": N,
        "replicate_ids_used": sorted(used_reps),
        "synthetic_entities_used": len(used_entities),
        "rows": rows,
    }


def _chi2_sf(dof: int, x: float) -> float:
    """Chi-square survival P(X > x) = Q(dof/2, x/2) via the regularized
    upper incomplete gamma (series; dof small)."""
    if x <= 0:
        return 1.0
    a = dof / 2.0
    # P(a, x/2) lower tail by series, then 1 - P
    x2 = x / 2.0
    ln_pre = -x2 + a * math.log(x2) - math.lgamma(a + 1.0)
    if ln_pre < -745:
        return 0.0  # underflow -> upper tail 0
    pre = math.exp(ln_pre)
    term = 1.0
    s = 1.0
    k = 0
    while True:
        k += 1
        term *= x2 / (a + k)
        s += term
        if abs(term) < 1e-15 * abs(s):
            break
        if k > 10000:
            break
    lower = pre * s
    return max(0.0, min(1.0, 1.0 - lower))


def lifetime_smoke() -> dict[str, Any]:
    """Frozen section-9 secondary smoke: 4 resources x 8 ages = 32 configs
    x N=2000; 24h left-closed-right-open buckets on [0, 240-a) plus the
    survive-to-240 right-censored bucket; Pearson chi-square (E<5 buckets
    merged into the next bucket); accept #(p<0.001) <= 1.
    P2-E1 F1: replicate_id = sample_idx % 5 (in {0..4}); validation-only
    synthetic generation = 100001 + sample_idx//5 (5 replicates x 400
    generation slots = 2000 samples); age does not enter the random key;
    different ages share the same U sequence (CRN-style smoke)."""
    N = len(LIFE_SAMPLES)
    ages = (0, 30, 60, 90, 120, 150, 180, 210)
    rows = []
    p_list: list[float] = []
    used_reps: set[int] = set()
    used_generations: set[int] = set()
    for resource in fp.RESOURCES:
        f120 = fp.F120[resource]
        f240 = fp.F240[resource]
        for age in ages:
            age = Fraction(age)
            pm = lg.p_max(age, f120, f240)
            horizon = Fraction(240) - age
            # expected bucket probabilities (conditional survival)
            buckets = []
            t = Fraction(0)
            while t < horizon:
                t2 = min(t + Fraction(24), horizon)
                p_bucket = (lg.cdf(age + t2, f120, f240)
                            - lg.cdf(age + t, f120, f240)) / (
                    Fraction(1) - lg.cdf(age, f120, f240))
                buckets.append({"lo": t, "hi": t2, "p": p_bucket})
                t = t2
            p_cens = Fraction(1) - pm  # survive to 240
            buckets.append({"lo": horizon, "hi": None, "p": p_cens})
            expected = [float(b["p"]) * N for b in buckets]
            # count observed draws per original bucket
            obs_counts = [0] * len(buckets)
            for sample_idx in LIFE_SAMPLES:
                rep = sample_idx % 5
                gen = ENTITY_BASE + sample_idx // 5
                used_reps.add(rep)
                used_generations.add(gen)
                v = ks.u_l_post(NS, rep, resource, gen, SEED)
                tau, cens = lg.conditional_residual(v, age, f120, f240)
                if cens:
                    obs_counts[-1] += 1
                else:
                    for i, b in enumerate(buckets[:-1]):
                        if b["lo"] <= tau < b["hi"]:
                            obs_counts[i] += 1
                            break
            # aggregate observed counts onto merged buckets
            # (merge by cumulative expected >= 5, deterministic)
            merged_obs = []
            merged_exp2 = []
            carry_e = 0.0
            carry_o = 0.0
            for e, o in zip(expected, obs_counts):
                carry_e += e
                carry_o += o
                if carry_e >= 5:
                    merged_exp2.append(carry_e)
                    merged_obs.append(carry_o)
                    carry_e = 0.0
                    carry_o = 0.0
            if carry_e > 0:
                # leftover small-mass buckets appended to the last bucket
                if merged_exp2:
                    merged_exp2[-1] += carry_e
                    merged_obs[-1] += carry_o
                else:
                    merged_exp2.append(carry_e)
                    merged_obs.append(carry_o)
            chi2 = 0.0
            df = 0
            for e, o in zip(merged_exp2, merged_obs):
                if e > 0:
                    chi2 += (o - e) ** 2 / e
                    df += 1
            df = max(1, df - 1)
            pval = _chi2_sf(df, chi2)
            p_list.append(pval)
            rows.append({"resource": resource, "age": str(age),
                         "N": N, "chi2": chi2, "df": df, "p": pval,
                         "observed": merged_obs,
                         "expected": merged_exp2})
    n_sig = sum(1 for p in p_list if p < 0.001)
    return {
        "check": "LIFETIME_STOCHASTIC_SMOKE",
        "status": "PASS" if n_sig <= 1 else "FAIL",
        "n_configs": len(rows),
        "n_p_lt_0.001": n_sig,
        "acceptance": "#(p<0.001) <= 1",
        "n_per_config": N,
        "replicate_ids_used": sorted(used_reps),
        "synthetic_generations_used": len(used_generations),
        "rows": rows,
    }


def posterior_random_domain(posterior_result: dict[str, Any]) -> dict[str, Any]:
    """P2-E1 F1 hard check (section 8): every replicate id actually used by
    the posterior smoke is in {0..4}; N per pattern is exactly 5000."""
    reps = posterior_result.get("replicate_ids_used", [])
    n = posterior_result.get("n_per_pattern", 0)
    ok = (set(reps) == set(VALID_REPLICATES)
          and all(r in VALID_REPLICATES for r in reps)
          and n == len(POST_SAMPLES) == 5000)
    return {
        "check": "POSTERIOR_RANDOM_DOMAIN",
        "status": "PASS" if ok else "FAIL",
        "replicate_ids_used": reps,
        "min": min(reps) if reps else None,
        "max": max(reps) if reps else None,
        "unique": sorted(set(reps)),
        "n_per_pattern": n,
        "valid_replicates": list(VALID_REPLICATES),
        "out_of_scope_replicates": sorted(set(reps) - set(VALID_REPLICATES)),
    }


def lifetime_random_domain(lifetime_result: dict[str, Any]) -> dict[str, Any]:
    """P2-E1 F1 hard check (section 8): every replicate id actually used by
    the lifetime smoke is in {0..4}; N per config is exactly 2000."""
    reps = lifetime_result.get("replicate_ids_used", [])
    n = lifetime_result.get("n_per_config", 0)
    ok = (set(reps) == set(VALID_REPLICATES)
          and all(r in VALID_REPLICATES for r in reps)
          and n == len(LIFE_SAMPLES) == 2000)
    return {
        "check": "LIFETIME_RANDOM_DOMAIN",
        "status": "PASS" if ok else "FAIL",
        "replicate_ids_used": reps,
        "min": min(reps) if reps else None,
        "max": max(reps) if reps else None,
        "unique": sorted(set(reps)),
        "n_per_config": n,
        "valid_replicates": list(VALID_REPLICATES),
        "out_of_scope_replicates": sorted(set(reps) - set(VALID_REPLICATES)),
    }


def c23_p2_check() -> dict[str, Any]:
    """C23 P2: same observable history -> identical posterior; same
    observable + same frozen key -> identical sampled hidden state."""
    from main_model.h2 import observable_state_v1 as obs
    log = pchk._mk_log()
    st1 = obs.project_log_prefix(log, Fraction(3), batch_size=2)
    st2 = obs.project_log_prefix(list(log), Fraction(3), batch_size=2)
    p1 = ps.PosteriorState.from_observable(st1)
    p2 = ps.PosteriorState.from_observable(st2)
    same_posterior = p1 == p2
    # same key -> same sampled hidden state
    abc1 = pg.sample_abc(pg.abc_posterior_8({}, ()), Fraction(1, 3))
    abc2 = pg.sample_abc(pg.abc_posterior_8({}, ()), Fraction(1, 3))
    same_draw = abc1 == abc2
    same_obs = pchk.check_same_observable()
    ok = same_posterior and same_draw and same_obs["status"] == "PASS"
    return {
        "check": "C23_P2",
        "status": "PASS" if ok else "FAIL",
        "same_observable_same_posterior": same_posterior,
        "same_key_same_draw": same_draw,
        "hidden_world_independent": same_obs["status"],
    }


def _run_suite(pattern: str) -> dict[str, Any]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(CODE_DIR / "tests"), pattern=pattern)
    buf = io.StringIO()
    runner = unittest.TextTestRunner(stream=buf, verbosity=1)
    result = runner.run(suite)
    return {
        "command": f"python -m unittest discover -s tests -p {pattern!r}",
        "exit_code": 0 if result.wasSuccessful() else 1,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "ok": result.wasSuccessful(),
        "log_tail": buf.getvalue()[-1500:],
    }


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_") + secrets.token_hex(4)


def _sha256_file(path: Path) -> str:
    return frm._sha256_file(path)


def _sha256_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dump_json(path: Path, value: Any) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n", encoding="utf-8", newline="\n")


def evidence_mapping_check(evidence_dir: Path) -> dict[str, Any]:
    results: dict[str, Any] = {}
    ok = True
    for check_id, fname in REPORT_MAPPING.items():
        p = evidence_dir / fname
        if not p.is_file():
            results[fname] = {"ok": False, "expected": check_id,
                              "got": None, "missing": True}
            ok = False
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            got = data.get("check")
        except (json.JSONDecodeError, OSError) as exc:
            results[fname] = {"ok": False, "expected": check_id,
                              "got": None, "error": str(exc)}
            ok = False
            continue
        match = got == check_id
        ok = ok and match
        results[fname] = {"ok": match, "expected": check_id, "got": got}
    return {"check": "EVIDENCE_SEMANTIC_MAPPING",
            "status": "PASS" if ok else "FAIL", "files": results}


def _verify(out_dir: Path) -> dict[str, Any]:
    try:
        dag = frm.verify_hash_dag(out_dir)
        cons = frm.verify_manifest_inventory_consistency(out_dir)
        mapping = evidence_mapping_check(out_dir)
        ok = (dag["hash_graph_acyclic"] is True and dag["mismatches"] == 0
              and "PASS" in cons["manifest_output_hashes"]
              and "PASS" in cons["manifest_inventory_crosscheck"]
              and cons["c21_report_sha_consistency"] == "PASS"
              and mapping["status"] == "PASS")
        return {"ok": ok, "hash_graph_acyclic": dag["hash_graph_acyclic"],
                "inventory_n": dag["inventory_n"], "mismatches": dag["mismatches"],
                "manifest_output_hashes": cons["manifest_output_hashes"],
                "manifest_inventory_crosscheck": cons["manifest_inventory_crosscheck"],
                "c21_report_sha_consistency": cons["c21_report_sha_consistency"],
                "evidence_semantic_mapping": mapping["status"],
                "detail": {"dag": dag, "consistency": cons, "mapping": mapping}}
    except AssertionError as exc:
        return {"ok": False, "error": f"AssertionError: {exc}"}


def _build_evidence(out_dir: Path, run_id: str, checks: dict[str, Any],
                    test_report: dict[str, Any],
                    regressions: list[dict[str, Any]],
                    verification: Optional[dict[str, Any]],
                    wall_total: float) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_bytes = Path(BOOTSTRAP_SPEC_FILE).read_bytes()
    spec_sha = _sha256_bytes(spec_bytes)
    (out_dir / "bootstrap_spec_snapshot.md").write_bytes(spec_bytes)
    (out_dir / "task_package_snapshot.yaml").write_text(
        "# Q3-H2-P2 task-package snapshot\n"
        f"package_ref: {PACKAGE_REF}\n"
        "authority: Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED "
        "sections 6.1/7/8/9 + Q3-H2-P2 Human Gate authorization\n"
        f"bootstrap_spec_snapshot: bootstrap_spec_snapshot.md\n"
        f"bootstrap_spec_sha256: {spec_sha}\n"
        f"formal_task_package_sha256: {FORMAL_TASK_PACKAGE_SHA}\n"
        "p1: FINAL PASS / ACCEPTED (08488e4)\n"
        "random_streams: namespace=h2_tuning seed=6; U_X_post/U_D_post/"
        "U_L_post only\n"
        "evidence_rule: ACYCLIC hash DAG (RULE A)\n",
        encoding="utf-8", newline="\n")
    _dump_json(out_dir / "commands.json", {
        "run_id": run_id,
        "command": "python 04_代码/scripts/run_h2_p2_v1.py",
        "wall_clock_s": round(wall_total, 2)})
    _dump_json(out_dir / "environment.json", frm._env_summary())
    _dump_json(out_dir / "scope_audit.json", SCOPE_AUDIT)
    _dump_json(out_dir / "test_report.json", test_report)
    _dump_json(out_dir / "regression_report.json", {
        "regressions": regressions,
        "note": "deterministic suites; commands/exit codes/test counts "
                "truthfully recorded; no 1400 formal worlds"})
    _dump_json(out_dir / "posterior_reachable_patterns.json", {
        "check": "POSTERIOR_REACHABLE_PATTERNS",
        "n_patterns": len(pchk.reachable_patterns()),
        "patterns": [list(map(list, p)) for p in pchk.reachable_patterns()]})
    _dump_json(out_dir / "lifetime_grid_report.json", {
        "check": "LIFETIME_GRID",
        "ages": [0, 30, 60, 90, 120, 150, 180, 210],
        "u_points": [0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99,
                     "p_max-1e-9", "p_max", "p_max+1e-9"],
        "resources": list(fp.RESOURCES)})
    for check in checks["checks"]:
        fname = REPORT_MAPPING.get(check["check"])
        if fname is not None:
            _dump_json(out_dir / fname, check)
    mapping_result = evidence_mapping_check(out_dir)
    _dump_json(out_dir / "evidence_semantic_mapping_report.json", mapping_result)
    # dev budget ledger snapshot (F2): current append-only ledger state
    ledger_path = BASE_DIR / "05_结果" / "H2" / "dev_budget_ledger.json"
    if ledger_path.is_file():
        _dump_json(out_dir / "dev_budget_ledger_snapshot.json",
                   json.loads(ledger_path.read_text(encoding="utf-8")))

    hashes = {
        "task_package_snapshot": _sha256_file(out_dir / "task_package_snapshot.yaml"),
        "bootstrap_spec": spec_sha,
        "formal_task_package": _sha256_file(FORMAL_TASK_PACKAGE_FILE),
        "frozen_params": _sha256_file(MAIN_MODEL / "h2" / "frozen_params_v1.py"),
        "posterior_generator": _sha256_file(MAIN_MODEL / "h2" / "posterior_generator_v1.py"),
        "lifetime_generator": _sha256_file(MAIN_MODEL / "h2" / "lifetime_generator_v1.py"),
        "posterior_state": _sha256_file(MAIN_MODEL / "h2" / "posterior_state_v1.py"),
        "observable_state": _sha256_file(MAIN_MODEL / "h2" / "observable_state_v1.py"),
        "posterior_checker": _sha256_file(CODE_DIR / "checker" / "h2_posterior_checker_v1.py"),
        "lifetime_checker": _sha256_file(CODE_DIR / "checker" / "h2_residual_lifetime_checker_v1.py"),
        "p1_firewall_checker": _sha256_file(CODE_DIR / "checker" / "h2_p1_firewall_checker_v1.py"),
        "tests": _sha256_file(CODE_DIR / "tests" / "test_h2_p2_v1.py"),
        "runner": _sha256_file(Path(__file__).resolve()),
        "key_schema": _sha256_file(MAIN_MODEL / "g3" / "key_schema_v1.py"),
        "engine": _sha256_file(MAIN_MODEL / "g3" / "random_des_v1.py"),
        "problem_contract": _sha256_file(frm.PROBLEM_CONTRACT_FILE),
        "parameters_csv": _sha256_file(frm.PARAMETERS_CSV),
        "registry": _sha256_file(BASE_DIR / "01_审计" / "检查注册表_V3.1.md"),
    }
    _dump_json(out_dir / "input_hashes.json", hashes)

    verify_ok = verification is not None and verification.get("ok") is True
    c21a = ("PASS" if verify_ok else
            ("PENDING_PROBE" if verification is None else "FAIL"))
    overall_ok = (checks["overall"] == "PASS"
                  and test_report["ok"]
                  and all(r["ok"] for r in regressions)
                  and verify_ok)
    _dump_json(out_dir / "C21_REQUALIFICATION_REPORT.json", {
        "run_id": run_id, "check_id": "CR-V3.1/C21",
        "scope": "Q3-H2-P2 evidence root",
        "status": "PASS" if overall_ok else "FAIL",
        "verification": verification,
        "items": [
            {"id": "C21a", "status": c21a,
             "note": "acyclic hash inventory (RULE A); status from actual "
                     "verifier"},
            {"id": "C21b", "status": c21a,
             "note": "manifest/inventory/actual SHA consistency; status "
                     "from actual verifier"},
            {"id": "C21c", "status": "PASS" if overall_ok else "FAIL",
             "note": "P2 generators + checkers + tests + regressions"}]})
    _dump_json(out_dir / "checks.json", {
        "run_id": run_id, "registry_version": REGISTRY_VERSION,
        "overall_status": "PASS" if overall_ok else "FAIL",
        "verification_fail_closed": {
            "hash_graph_acyclic": verification.get("hash_graph_acyclic")
            if verification else None,
            "inventory_mismatches": verification.get("mismatches")
            if verification else None,
            "manifest_inventory_consistency": verification.get(
                "manifest_inventory_crosscheck") if verification else None,
            "c21_report_sha_consistency": verification.get(
                "c21_report_sha_consistency") if verification else None,
            "evidence_semantic_mapping": verification.get(
                "evidence_semantic_mapping") if verification else None},
        "items": [
            {"check_id": "POSTERIOR_PRIMARY_DETERMINISTIC", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "POSTERIOR_PRIMARY_DETERMINISTIC")},
            {"check_id": "POSTERIOR_D_COROLLARY", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "POSTERIOR_D_COROLLARY")},
            {"check_id": "POSTERIOR_STOCHASTIC_SMOKE", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "POSTERIOR_STOCHASTIC_SMOKE"),
             "count": f"n_|z|>3.5={next(c['n_abs_z_gt_3.5'] for c in checks['checks'] if c['check'] == 'POSTERIOR_STOCHASTIC_SMOKE')}"},
            {"check_id": "POSTERIOR_RANDOM_DOMAIN", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "POSTERIOR_RANDOM_DOMAIN"),
             "count": f"reps={next(c['replicate_ids_used'] for c in checks['checks'] if c['check'] == 'POSTERIOR_RANDOM_DOMAIN')}"},
            {"check_id": "LIFETIME_PRIMARY_DETERMINISTIC", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "LIFETIME_PRIMARY_DETERMINISTIC")},
            {"check_id": "LIFETIME_STOCHASTIC_SMOKE", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "LIFETIME_STOCHASTIC_SMOKE"),
             "count": f"n_p_lt_0.001={next(c['n_p_lt_0.001'] for c in checks['checks'] if c['check'] == 'LIFETIME_STOCHASTIC_SMOKE')}"},
            {"check_id": "LIFETIME_RANDOM_DOMAIN", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "LIFETIME_RANDOM_DOMAIN"),
             "count": f"reps={next(c['replicate_ids_used'] for c in checks['checks'] if c['check'] == 'LIFETIME_RANDOM_DOMAIN')}"},
            {"check_id": "C23_P2", "status": next(
                c["status"] for c in checks["checks"]
                if c["check"] == "C23_P2")},
            {"check_id": "C23_P1_FIREWALL", "status": "PASS" if all(
                r["ok"] for r in regressions[:1]) else "FAIL",
             "note": "P1 firewall regressions included below"},
            {"check_id": "TESTS", "status": "PASS" if test_report["ok"] else "FAIL",
             "count": f"{test_report['tests_run'] - test_report['failures'] - test_report['errors']}"
                      f"/{test_report['tests_run']}"},
            {"check_id": "REGRESSIONS", "status": "PASS" if all(
                r["ok"] for r in regressions) else "FAIL",
             "detail": [{"pattern": r["command"].split("'")[1],
                         "exit_code": r["exit_code"],
                         "tests_run": r["tests_run"]} for r in regressions]},
            {"check_id": "CR-V3.1/C21", "status": "PASS" if overall_ok else "FAIL",
             "note": "acyclic hash inventory + manifest/inventory "
                     "consistency (fail-closed)"}]})

    artifacts = [
        {"path": p.relative_to(out_dir).as_posix(),
         "bytes": p.stat().st_size, "sha256": _sha256_file(p)}
        for p in sorted(out_dir.rglob("*"))
        if p.is_file() and p.name != "file_hashes.sha256"]
    _dump_json(out_dir / "run_manifest.json", {
        "run_id": run_id, "created_at": _utc_now(), "gate": "Q3",
        "purpose": "h2_p2_generators", "formal": True,
        "label": "Q3-H2-P2 posterior + conditional-lifetime generators",
        "paper_authoritative": False,
        "task_package_ref": PACKAGE_REF,
        "task_package_snapshot_path": "task_package_snapshot.yaml",
        "bootstrap_spec_sha256": spec_sha,
        "formal_task_package_sha256": FORMAL_TASK_PACKAGE_SHA,
        "registry_version": REGISTRY_VERSION,
        "hash_inventory_path": "file_hashes.sha256",
        "hash_inventory_rule": (
            "ACYCLIC DAG (RULE A): run_manifest does not hash "
            "file_hashes.sha256; file_hashes covers all artifacts incl. "
            "run_manifest and task_package_snapshot, never itself."),
        "random_domain": {
            "namespace": NS,
            "master_seed": SEED,
            "replicate_ids": [0, 1, 2, 3, 4],
            "purpose": "P2 generator validation only",
            "posterior_N_per_pattern": 5000,
            "lifetime_N_per_config": 2000,
            "h2_holdout_used": False,
            "q3_formal_used": False,
            "U_Y_post_used": False,
            "new_random_keys_outside_frozen_p2_domain": "NO",
        },
        "p1": "FINAL PASS / ACCEPTED (08488e4)",
        "p2": {"posterior": "implemented (SPEC 8)",
               "conditional_lifetime": "implemented (SPEC 9)",
               "c23_full_end_to_end": "PENDING"},
        "p3": "NOT AUTHORIZED", "c25": "NOT AUTHORIZED",
        "verification_fail_closed": (
            verification if verification is not None else "PROBE_PHASE"),
        "overall_status": "PASS" if overall_ok else "FAIL",
        "environment": frm._env_summary(), "outputs": artifacts,
        "check_report_paths": [
            "checks.json", "posterior_deterministic_report.json",
            "posterior_reachable_patterns.json", "posterior_smoke_report.json",
            "lifetime_deterministic_report.json", "lifetime_grid_report.json",
            "lifetime_smoke_report.json", "c23_p2_report.json",
            "regression_report.json", "test_report.json", "scope_audit.json",
            "C21_REQUALIFICATION_REPORT.json"],
        "notes": [
            "Q3-H2-P2：后验 §8 + 条件剩余寿命 §9 生成器 + 独立 deterministic "
            "checker + 冻结 secondary smoke；P3/C25 未授权。",
            "随机流仅 h2_tuning（master_seed=6）的 U_X_post/U_D_post/"
            "U_L_post；不消费 U_Y_post / h2_holdout / q3_formal。",
            "C23 继续生效（P1 防火墙 + same-observable -> same posterior）。",
            "C21 fail-closed + semantic evidence mapping。"],
    })

    lines = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "file_hashes.sha256":
            rel = path.relative_to(out_dir).as_posix()
            lines.append(f"{_sha256_file(path)}  {rel}")
    (out_dir / "file_hashes.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _promote(staging: Path, final: Path) -> dict[str, Any]:
    if final.exists():
        shutil.rmtree(final)
    shutil.copytree(staging, final)
    mismatches = []
    for p in sorted(staging.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(staging)
        q = final / rel
        if not q.is_file() or _sha256_file(p) != _sha256_file(q):
            mismatches.append(rel.as_posix())
    return {"ok": len(mismatches) == 0,
            "files_copied": sum(1 for p in staging.rglob("*") if p.is_file()),
            "sha_mismatches": mismatches}


def main(argv: Optional[list[str]] = None) -> int:
    output_root = BASE_DIR / "05_结果" / "H2" / "p2" / "requalification"
    run_id = _new_run_id()
    final_dir = output_root / f"run_{run_id}"
    staging_dir = BASE_DIR / ".." / "tmp" / f"p2_staging_{run_id}"
    print(f"[p2] run_id={run_id}")
    t0 = time.perf_counter()
    post_smoke = posterior_smoke()
    life_smoke = lifetime_smoke()
    checks = {
        "overall": "PASS",
        "checks": [
            pchk.check_deterministic(),
            pchk.check_d_corollary(),
            pchk.check_same_observable(),
            post_smoke,
            posterior_random_domain(post_smoke),
            lchk.check_deterministic(),
            lchk.check_age0_degenerate(),
            lchk.check_240_boundary(),
            life_smoke,
            lifetime_random_domain(life_smoke),
            c23_p2_check(),
        ]}
    checks["overall"] = ("PASS" if all(c["status"] == "PASS"
                                       for c in checks["checks"]) else "FAIL")
    test_report = _run_suite("test_h2_p2_v1.py")
    regressions = [_run_suite(p) for p in REGRESSION_PATTERNS]
    wall_total = time.perf_counter() - t0
    # ---- dev budget ledger (F2): append this run's entry; snapshot ----
    ledger_path = BASE_DIR / "05_结果" / "H2" / "dev_budget_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry_ids = {e.get("entry_id") for e in ledger["entries"]}
    e1_entry_id = f"P2-E1-{run_id}"
    if e1_entry_id not in entry_ids:
        ledger["entries"].append({
            "entry_id": e1_entry_id,
            "task": "Q3-H2-P2-E1 random-domain / budget requalification",
            "run_id": run_id,
            "wall_clock_s": round(wall_total, 4),
            "status": "COMPLETED / AWAITING HUMAN GATE FINAL P2 REVIEW",
            "category": "section 8/9 generator validation (requalified "
                        "random domain)",
            "namespace": "h2_tuning",
            "note": "replicate_ids restricted to {0..4}; synthetic "
                    "entity/generation slots for N=5000/2000",
            "date": "2026-08-16"})
    ledger["cumulative_wall_clock_s"] = round(
        sum(e["wall_clock_s"] for e in ledger["entries"]), 4)
    ledger["cumulative_wall_clock_h"] = round(
        ledger["cumulative_wall_clock_s"] / 3600.0, 6)
    ledger["soft_budget_reached"] = (
        ledger["cumulative_wall_clock_h"] >= ledger["soft_budget_h"])
    ledger["hard_budget_reached"] = (
        ledger["cumulative_wall_clock_h"] >= ledger["hard_budget_h"])
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False,
                                      sort_keys=True, indent=1) + "\n",
                           encoding="utf-8", newline="\n")
    print(f"[p2] checker overall={checks['overall']} tests={test_report['tests_run']} "
          f"regressions={[r['tests_run'] for r in regressions]}")
    for c in checks["checks"]:
        print(f"  {c['check']}: {c['status']}")
    _build_evidence(staging_dir, run_id, checks, test_report, regressions,
                    verification=None, wall_total=wall_total)
    probe = _verify(staging_dir)
    print(f"[p2] probe verification ok={probe.get('ok')} {probe.get('error', '')}")
    if not probe.get("ok"):
        return 1
    _build_evidence(staging_dir, run_id, checks, test_report, regressions,
                    verification=probe, wall_total=wall_total)
    confirm = _verify(staging_dir)
    if not confirm.get("ok"):
        print(f"[p2] FAIL final-content verification {confirm.get('error', '')}")
        return 1
    promo = _promote(staging_dir, final_dir)
    if not promo["ok"]:
        print(f"[p2] FAIL promote {promo['sha_mismatches']}")
        return 1
    final_verify = _verify(final_dir)
    ok = (probe.get("ok") and confirm.get("ok") and promo["ok"]
          and final_verify.get("ok")
          and checks["overall"] == "PASS"
          and test_report["ok"] and all(r["ok"] for r in regressions))
    print(f"[p2] evidence written: {final_dir}")
    print(f"[p2] DONE overall={'PASS' if ok else 'FAIL'} wall={wall_total:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
