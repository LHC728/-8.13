#!/usr/bin/env python3
"""Q3-H2-P2 independent posterior checker (SPEC section 8 PRIMARY).

Independent verification of the frozen posterior defect-state generator.
The checker NEVER imports or calls the implementer posterior core
(``posterior_generator_v1``) as an oracle: it re-derives the frozen
formulas itself (shared only: frozen parameter values and Fraction
utilities).  The implementer output is compared against the checker's own
expected vectors.

Checks:
  * reachable-pattern enumerator: obs_j in {empty,[N],[A],[A,N],[A,A]} for
    A/B/C, obs_E in the same set, restricted to the frozen reachable
    patterns (obs_E nonempty => A/B/C all end with a valid N pass; any
    obs_j == [A,A] => device exited => obs_E empty).  Total <= 625.
  * PRIMARY deterministic: for every reachable pattern, the checker
    computes the exact posterior vector (16 states for reached-E devices,
    8 states otherwise) and compares with the implementer output
    state-by-state; exact Fraction equality is required (both sides exact).
  * H_ABC-nonempty corollary: P(x_D=1 | obs, ABC) == q_D whenever ABC is
    not all-clear (E carries no information about x_D); only ABC all-clear
    allows the E observation to update D.
  * same observable history / different hidden world: projecting two logs
    that are identical in observable content but differ in hidden
    annotations through PosteriorState.from_observable yields identical
    posterior states (deterministic, hidden-free).

Python 3.12, standard library only.
"""
from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from main_model.h2 import frozen_params_v1 as fp  # noqa: E402
from main_model.h2 import posterior_generator_v1 as pg  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from main_model.h2 import observable_state_v1 as obs  # noqa: E402

N, A = "N", "A"
PATTERN_SET = ((), (N,), (A,), (A, N), (A, A))


def _ends_n(seq: tuple[str, ...]) -> bool:
    return len(seq) > 0 and seq[-1] == N


def reachable_patterns() -> list[tuple[tuple[str, ...], tuple[str, ...],
                                       tuple[str, ...], tuple[str, ...]]]:
    """Deterministic frozen enumerator of reachable observation patterns
    (obs_A, obs_B, obs_C, obs_E); total <= 625."""
    out: list[tuple[tuple[str, ...], tuple[str, ...],
                    tuple[str, ...], tuple[str, ...]]] = []
    for oa in PATTERN_SET:
        for ob in PATTERN_SET:
            for oc in PATTERN_SET:
                exited = (oa == (A, A)) or (ob == (A, A)) or (oc == (A, A))
                for oe in PATTERN_SET:
                    if oe and exited:
                        continue  # exited device -> obs_E empty
                    if oe and not (_ends_n(oa) and _ends_n(ob) and _ends_n(oc)):
                        continue  # obs_E nonempty requires A/B/C valid N end
                    out.append((oa, ob, oc, oe))
    return out


# -- checker's OWN posterior formulas (independent of implementer core) ----

KERNEL: dict[str, dict[str, Fraction]] = fp.observation_kernel()


def _single_lik(seq: tuple[str, ...], x: int, proc: str) -> Fraction:
    alpha = KERNEL[proc]["alpha"]
    beta = KERNEL[proc]["beta"]
    p = Fraction(1)
    for y in seq:
        if x == 0:
            p *= (Fraction(1) - alpha) if y == N else alpha
        else:
            p *= beta if y == N else (Fraction(1) - beta)
    return p


def _e_lik(seq: tuple[str, ...], h: bool) -> Fraction:
    alpha = KERNEL["E"]["alpha"]
    beta = KERNEL["E"]["beta"]
    p = Fraction(1)
    for y in seq:
        if h:
            p *= beta if y == N else (Fraction(1) - beta)
        else:
            p *= (Fraction(1) - alpha) if y == N else alpha
    return p


def checker_joint_16(oa, ob, oc, oe) -> dict[tuple[int, int, int, int], Fraction]:
    w: dict[tuple[int, int, int, int], Fraction] = {}
    for xa in (0, 1):
        for xb in (0, 1):
            for xc in (0, 1):
                for xd in (0, 1):
                    weight = (Fraction(1)
                              * (fp.Q_ABC["A"] if xa else 1 - fp.Q_ABC["A"])
                              * (fp.Q_ABC["B"] if xb else 1 - fp.Q_ABC["B"])
                              * (fp.Q_ABC["C"] if xc else 1 - fp.Q_ABC["C"])
                              * (fp.Q_D if xd else 1 - fp.Q_D))
                    weight *= _single_lik(oa, xa, "A")
                    weight *= _single_lik(ob, xb, "B")
                    weight *= _single_lik(oc, xc, "C")
                    weight *= _e_lik(oe, (xa or xb or xc or xd) == 1)
                    w[(xa, xb, xc, xd)] = weight
    total = sum(w.values(), Fraction(0))
    return {k: v / total for k, v in w.items()}


def checker_abc_8(oa, ob, oc, oe) -> dict[tuple[int, int, int], Fraction]:
    w: dict[tuple[int, int, int], Fraction] = {}
    for xa in (0, 1):
        for xb in (0, 1):
            for xc in (0, 1):
                weight = (Fraction(1)
                          * (fp.Q_ABC["A"] if xa else 1 - fp.Q_ABC["A"])
                          * (fp.Q_ABC["B"] if xb else 1 - fp.Q_ABC["B"])
                          * (fp.Q_ABC["C"] if xc else 1 - fp.Q_ABC["C"]))
                weight *= _single_lik(oa, xa, "A")
                weight *= _single_lik(ob, xb, "B")
                weight *= _single_lik(oc, xc, "C")
                h_abc = (xa or xb or xc) == 1
                le1 = _e_lik(oe, True)
                le0 = _e_lik(oe, h_abc)
                weight *= (fp.Q_D * le1 + (1 - fp.Q_D) * le0)
                w[(xa, xb, xc)] = weight
    total = sum(w.values(), Fraction(0))
    return {k: v / total for k, v in w.items()}


def checker_d_given_abc(oe, abc) -> Fraction:
    h_abc = abc[0] or abc[1] or abc[2]
    le1 = _e_lik(oe, True)
    le0 = _e_lik(oe, bool(h_abc))
    w1 = fp.Q_D * le1
    w0 = (1 - fp.Q_D) * le0
    return w1 / (w1 + w0)


# ---------------------------------------------------------------------------


def check_deterministic() -> dict[str, Any]:
    patterns = reachable_patterns()
    mismatches: list[str] = []
    n_states = 0
    n_checked = 0
    for oa, ob, oc, oe in patterns:
        reached_e = len(oe) > 0
        if reached_e:
            expected = checker_joint_16(oa, ob, oc, oe)
            got = pg.joint_posterior_16({"A": oa, "B": ob, "C": oc}, oe)
        else:
            expected = checker_abc_8(oa, ob, oc, oe)
            got = pg.abc_posterior_8({"A": oa, "B": ob, "C": oc}, oe)
        n_states += len(expected)
        n_checked += 1
        if set(expected) != set(got):
            mismatches.append(
                f"pattern ({oa},{ob},{oc},{oe}): state set mismatch")
            continue
        for key, e in expected.items():
            g = got[key]
            if g != e:
                mismatches.append(
                    f"pattern ({oa},{ob},{oc},{oe}) state {key}: "
                    f"expected {e} got {g}")
    return {
        "check": "POSTERIOR_PRIMARY_DETERMINISTIC",
        "status": "PASS" if not mismatches else "FAIL",
        "reachable_patterns": len(patterns),
        "states_compared": n_states,
        "max_abs_error": 0 if not mismatches else None,
        "mismatches": mismatches[:20],
        "n_mismatches": len(mismatches),
    }


def check_d_corollary() -> dict[str, Any]:
    patterns = [p for p in reachable_patterns() if len(p[3]) > 0]
    failures: list[str] = []
    checked = 0
    for oa, ob, oc, oe in patterns:
        joint = pg.joint_posterior_16({"A": oa, "B": ob, "C": oc}, oe)
        for (xa, xb, xc, _xd), _p in joint.items():
            abc = (xa, xb, xc)
            p1 = pg.d_given_abc(oe, abc)
            if (xa or xb or xc):
                # H_ABC nonempty -> E carries no information about x_D
                if p1 != fp.Q_D:
                    failures.append(f"pattern ({oa},{ob},{oc},{oe}) ABC={abc}: "
                                    f"P(x_D=1)={p1} != q_D={fp.Q_D}")
                checked += 1
            else:
                # ABC all-clear -> E may update D; must equal the checker's
                # independent derivation
                expected = checker_d_given_abc(oe, abc)
                if p1 != expected:
                    failures.append(f"pattern ({oa},{ob},{oc},{oe}) ABC={abc}: "
                                    f"got {p1} expected {expected}")
                checked += 1
    return {
        "check": "POSTERIOR_D_COROLLARY",
        "status": "PASS" if not failures else "FAIL",
        "cases_checked": checked,
        "failures": failures[:20],
    }


def check_same_observable() -> dict[str, Any]:
    """Same observable history + different hidden world -> identical
    PosteriorState (project through the P1 boundary, then posterior)."""
    base = obs.project_log_prefix(_mk_log(), Fraction(3), batch_size=2)
    variants = [
        _mk_log(hidden_abc={1: {"A": True, "B": True, "C": True}}),
        _mk_log(hidden_d={1: "problem"}),
        _mk_log(hidden_lifetime={"A": "999"}),
        _mk_log(hidden_u={("A", 1, 1): "0.999", ("L", "A", 2): "0.001"}),
    ]
    fp_base = ps.PosteriorState.from_observable(base).__repr__()
    results = []
    ok = True
    for variant in variants:
        st = obs.project_log_prefix(variant, Fraction(3), batch_size=2)
        fp_var = ps.PosteriorState.from_observable(st).__repr__()
        same = fp_var == fp_base
        ok = ok and same
        results.append({"fingerprints_equal": same})
    return {
        "check": "POSTERIOR_SAME_OBSERVABLE_HISTORY",
        "status": "PASS" if ok else "FAIL",
        "variants": results,
    }


def _mk_log(hidden_abc=None, hidden_d=None, hidden_lifetime=None,
            hidden_u=None, extra_future=None):
    abc = hidden_abc if hidden_abc is not None else {
        1: {"A": False, "B": False, "C": False}}
    d_state = hidden_d if hidden_d is not None else {}
    life = hidden_lifetime if hidden_lifetime is not None else {}
    uvals = hidden_u if hidden_u is not None else {}

    def _u(key):
        return uvals.get(key, "0.5")

    log = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": abc[1]},
        {"event_type": "TASK_RELEASE", "event_time": "0",
         "resource_id": "A", "device_id": 1, "process": "A",
         "effective_attempt_no": 1},
        {"event_type": "ACTIVITY_START", "event_time": "0", "device_id": 1,
         "process": "A", "effective_attempt_no": 1, "resource_id": "A",
         "attempt_start_time": "0", "attempt_end_time": "5/2",
         "outcome": "NONE"},
        {"event_type": "ACTIVITY_COMPLETE", "event_time": "5/2",
         "device_id": 1, "process": "A", "effective_attempt_no": 1,
         "resource_id": "A", "attempt_start_time": "0",
         "attempt_end_time": "5/2", "outcome": "NONE"},
        {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "5/2",
         "device_id": 1, "process": "A", "effective_attempt_no": 1,
         "resource_id": "A", "outcome": "PASS", "true_state": abc[1],
         "u_key": "k_A_1", "u": _u(("A", 1, 1))},
        {"event_type": "D_CREATED", "event_time": "5/2", "device_id": 1,
         "d_state": d_state.get(1, "normal"), "bay_id": 1, "squad_id": 0,
         "u_key": "k_D_1", "u": _u(("D", 1, 0))},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "10", "on_duty_squad": 0,
         "squad_id": 0},
        {"event_type": "EQUIPMENT_REPLACEMENT_START", "event_time": "1",
         "resource_id": "A", "kind": "preventive", "trigger": "preventive",
         "old_generation": 1, "new_generation": 2, "age_before": "1",
         "calibration_duration_hours": "1/2", "calibration_start": "1",
         "calibration_end": "3/2", "u_key": "k_L_A_2",
         "u": _u(("L", "A", 2)), "lifetime_h": life.get("A", "250")},
    ]
    for rec in extra_future or []:
        log.append(rec)
    log.sort(key=lambda r: Fraction(r["event_time"]))
    return log


def run_all() -> dict[str, Any]:
    checks = [check_deterministic(), check_d_corollary(),
              check_same_observable()]
    all_ok = all(c["status"] == "PASS" for c in checks)
    return {"overall": "PASS" if all_ok else "FAIL", "checks": checks}


if __name__ == "__main__":
    result = run_all()
    print(result["overall"])
    for c in result["checks"]:
        print(f"  {c['check']}: {c['status']}")
        for m in c.get("mismatches", [])[:5] + c.get("failures", [])[:5]:
            print(f"    - {m}")
    sys.exit(0 if result["overall"] == "PASS" else 1)
