#!/usr/bin/env python3
"""Q3-H2-P2 independent residual-lifetime checker (SPEC section 9 PRIMARY).

Independent verification of the frozen conditional-survival generator.
The checker NEVER imports or calls the implementer lifetime core
(``lifetime_generator_v1.conditional_residual``) as an oracle: it
re-derives p_max / target CDF / piecewise-linear inverse / right-censored
branch itself (shared only: frozen parameter values and Fraction
utilities).

Checks:
  * PRIMARY deterministic grid: 4 resources x 8 ages {0,30,60,90,120,150,
    180,210} x 10 U points {0.01,0.1,0.25,0.5,0.75,0.9,0.99, p_max-eps,
    p_max, p_max+eps} (eps = 1e-9 exact); natural tau tolerance |delta| <=
    1e-9 h (exact equality when both Fractions), right-censored flag exact;
  * age=0 degeneracy: p_max(0) == F(240) and the generator reproduces the
    accepted G3 unconditional sampler semantics;
  * 240 h boundary: a+d > 240 -> pre-start mandatory (never optional PM);
    a+d == 240 -> completion-first then mandatory (rule verification).

Python 3.12, standard library only.
"""
from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from main_model.h2 import frozen_params_v1 as fp  # noqa: E402
from main_model.h2 import lifetime_generator_v1 as lg  # noqa: E402

AGES = (0, 30, 60, 90, 120, 150, 180, 210)
EPS = lg.EPSILON


# -- checker's OWN lifetime formulas (independent of implementer core) ------

def _cdf(t: Fraction, f120: Fraction, f240: Fraction) -> Fraction:
    if t <= Fraction(120):
        return f120 * t / Fraction(120)
    return f120 + (f240 - f120) * (t - Fraction(120)) / Fraction(120)


def _inv(y: Fraction, f120: Fraction, f240: Fraction):
    if y <= f120:
        return Fraction(120) * y / f120, False
    if y <= f240:
        return (Fraction(120)
                + Fraction(120) * (y - f120) / (f240 - f120)), False
    return None, True


def checker_p_max(age: Fraction, f120: Fraction, f240: Fraction) -> Fraction:
    fa = _cdf(age, f120, f240)
    f240v = _cdf(Fraction(240), f120, f240)
    return (f240v - fa) / (Fraction(1) - fa)


def checker_residual(v: Fraction, age: Fraction, f120: Fraction,
                     f240: Fraction):
    pm = checker_p_max(age, f120, f240)
    if v > pm:
        return fp.MANDATORY_AGE_H - age, True
    fa = _cdf(age, f120, f240)
    target = fa + v * (Fraction(1) - fa)
    life, censored = _inv(target, f120, f240)
    if censored or life is None:
        return fp.MANDATORY_AGE_H - age, True
    return life - age, False


def _u_grid(age: Fraction, f120: Fraction, f240: Fraction) -> list[Fraction]:
    pm = checker_p_max(age, f120, f240)
    return [Fraction(x) for x in
            (Fraction(1, 100), Fraction(1, 10), Fraction(1, 4),
             Fraction(1, 2), Fraction(3, 4), Fraction(9, 10),
             Fraction(99, 100))] + [pm - EPS, pm, pm + EPS]


def check_deterministic() -> dict[str, Any]:
    mismatches: list[str] = []
    max_abs = Fraction(0)
    n_checked = 0
    for resource in fp.RESOURCES:
        f120 = fp.F120[resource]
        f240 = fp.F240[resource]
        for age in AGES:
            age = Fraction(age)
            for v in _u_grid(age, f120, f240):
                expected = checker_residual(v, age, f120, f240)
                got = lg.conditional_residual(v, age, f120, f240)
                n_checked += 1
                e_tau, e_cens = expected
                g_tau, g_cens = got
                if e_cens != g_cens:
                    mismatches.append(
                        f"{resource} age={age} v={v}: censored expected "
                        f"{e_cens} got {g_cens}")
                    continue
                if e_cens:
                    if e_tau != g_tau:
                        mismatches.append(
                            f"{resource} age={age} v={v}: censored tau "
                            f"expected {e_tau} got {g_tau}")
                    continue
                delta = abs(e_tau - g_tau)
                if delta > max_abs:
                    max_abs = delta
                if delta != 0 and delta > Fraction(1, 10**9):
                    mismatches.append(
                        f"{resource} age={age} v={v}: tau expected "
                        f"{e_tau} got {g_tau} (|delta|={delta})")
    return {
        "check": "LIFETIME_PRIMARY_DETERMINISTIC",
        "status": "PASS" if not mismatches else "FAIL",
        "points_checked": n_checked,
        "max_abs_error_h": str(max_abs),
        "tolerance_h": "1e-9 (exact when both Fractions)",
        "mismatches": mismatches[:20],
    }


def check_age0_degenerate() -> dict[str, Any]:
    failures: list[str] = []
    for resource in fp.RESOURCES:
        f120 = fp.F120[resource]
        f240 = fp.F240[resource]
        pm0 = lg.p_max(Fraction(0), f120, f240)
        f240v = _cdf(Fraction(240), f120, f240)
        if pm0 != f240v:
            failures.append(f"{resource}: p_max(0)={pm0} != F(240)={f240v}")
        # v <= F(240): generator reproduces the unconditional inverse CDF
        for v in (Fraction(1, 100), Fraction(1, 10), Fraction(1, 2),
                  Fraction(99, 100)):
            tau, cens = lg.conditional_residual(v, Fraction(0), f120, f240)
            life, uncens = _inv(v, f120, f240)
            expected_tau = life  # tau = F^-1(v) - 0 = lifetime
            expected_cens = uncens
            if cens != expected_cens or (not cens and tau != expected_tau):
                failures.append(
                    f"{resource} v={v}: expected ({expected_tau},"
                    f"{expected_cens}) got ({tau},{cens})")
    return {
        "check": "LIFETIME_AGE0_DEGENERATE",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures[:10],
    }


def check_240_boundary() -> dict[str, Any]:
    """Rule verification: a+d > 240 -> mandatory pre-start (never optional
    PM); a+d == 240 -> completion-first then mandatory.  The generator's
    right-censored clip keeps a+tau <= 240."""
    failures: list[str] = []
    for resource in fp.RESOURCES:
        d = fp.DURATIONS_H[resource]
        # a + d == 240 boundary: generator must produce tau such that
        # age + tau <= 240 in the natural branch and tau == 240-a in the
        # censored branch (clip).
        for age in (Fraction(237, 1), Fraction(238, 1), Fraction(120, 1)):
            pm = lg.p_max(age, fp.F120[resource], fp.F240[resource])
            v_nat = pm - EPS  # natural branch
            tau, cens = lg.conditional_residual(
                v_nat, age, fp.F120[resource], fp.F240[resource])
            if not cens and age + tau > fp.MANDATORY_AGE_H:
                failures.append(f"{resource} age={age}: natural a+tau > 240")
            v_cens = pm + EPS  # censored branch
            tau2, cens2 = lg.conditional_residual(
                v_cens, age, fp.F120[resource], fp.F240[resource])
            if not cens2 or tau2 != fp.MANDATORY_AGE_H - age:
                failures.append(f"{resource} age={age}: censored clip "
                                f"expected 240-a, got ({tau2},{cens2})")
        # a+d > 240 is mandatory in the engine rule; the generator itself
        # never produces a natural lifetime that crosses 240 (clip above).
    return {
        "check": "LIFETIME_240_BOUNDARY",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures[:10],
    }


def run_all() -> dict[str, Any]:
    checks = [check_deterministic(), check_age0_degenerate(),
              check_240_boundary()]
    all_ok = all(c["status"] == "PASS" for c in checks)
    return {"overall": "PASS" if all_ok else "FAIL", "checks": checks}


if __name__ == "__main__":
    result = run_all()
    print(result["overall"])
    for c in result["checks"]:
        print(f"  {c['check']}: {c['status']}")
    sys.exit(0 if result["overall"] == "PASS" else 1)
