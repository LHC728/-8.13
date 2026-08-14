"""Route A: closed-form Q1 chain (frozen G2-02 stage 1-5 formulas).

Frozen G2-02-SPEC-V1.0.5 route_A_closed_form: direct application of the stage_1 to
stage_5 formulas with Decimal arithmetic at precision >= 120.  P(H) uses this route's
own closed-form product helper.  This file is one of three independent cross-check
routes: it MUST NOT import the other route modules, the reusable solver, or any shared
core summation/transition/feasibility code.  Standard library only.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Any

ZERO = Decimal(0)
ONE = Decimal(1)
TWO = Decimal(2)
HUNDRED = Decimal(100)
PROCESSES = ("A", "B", "C")


def _p_h(abc: dict[str, dict[str, Any]], q_d: Decimal, x_a: int, x_b: int, x_c: int, x_d: int) -> Decimal:
    """Own closed-form product helper: P(H) = prod_j q_j^{x_j} (1-q_j)^{1-x_j}."""
    product = ONE
    for process, x in (("A", x_a), ("B", x_b), ("C", x_c)):
        q = abc[process]["q"]
        product = product * (q if x else (ONE - q))
    product = product * (q_d if x_d else (ONE - q_d))
    return product


def _pass_product(abc: dict[str, dict[str, Any]], u: dict[str, Decimal], v: dict[str, Decimal],
                  x_a: int, x_b: int, x_c: int) -> Decimal:
    """Own helper: P(reach_E | H) = prod_{j in A,B,C} pass_j(X_j), pass_j(0)=u_j, pass_j(1)=v_j."""
    product = ONE
    for process, x in (("A", x_a), ("B", x_b), ("C", x_c)):
        product = product * (u[process] if x == 0 else v[process])
    return product


def _probability_products(abc: dict[str, dict[str, Any]], q_d: Decimal,
                          precision: int) -> tuple[dict[str, Decimal], dict[str, Decimal],
                                                    Decimal, Decimal, Decimal, Decimal, Decimal]:
    """Stage-1 closed-form products (route A's own arithmetic)."""
    u: dict[str, Decimal] = {}
    v: dict[str, Decimal] = {}
    for process in PROCESSES:
        alpha = abc[process]["alpha"]
        beta = abc[process]["beta"]
        q = abc[process]["q"]
        u[process] = ONE - alpha * alpha
        v[process] = TWO * beta - beta * beta
    g = {process: (ONE - abc[process]["q"]) * u[process] + abc[process]["q"] * v[process]
         for process in PROCESSES}
    g_total = g["A"] * g["B"] * g["C"]
    q0 = (ONE - abc["A"]["q"]) * (ONE - abc["B"]["q"]) * (ONE - abc["C"]["q"])
    u_total = u["A"] * u["B"] * u["C"]
    z0 = (ONE - q_d) * q0 * u_total
    return u, v, g_total, q0, u_total, z0, g_total - z0


def compute_pre_e(abc: dict[str, dict[str, Any]], q_d: Decimal, precision: int = 200) -> dict[str, Any]:
    """Stage 1: q_E, G, Z_0, Z_1 and the 16-entry reach_E_distribution (index i=A+2B+4C+8D)."""
    with localcontext() as ctx:
        ctx.prec = precision
        u, v, g_total, q0, u_total, z0, z1 = _probability_products(abc, q_d, precision)
        q_e = z1 / g_total if g_total != ZERO else ZERO
        distribution: list[Decimal] = []
        for index in range(16):
            x_a = index & 1
            x_b = (index >> 1) & 1
            x_c = (index >> 2) & 1
            x_d = (index >> 3) & 1
            weight = _p_h(abc, q_d, x_a, x_b, x_c, x_d) * _pass_product(abc, u, v, x_a, x_b, x_c)
            distribution.append(weight / g_total if g_total != ZERO else ZERO)
        return {
            "q_E": q_e,
            "G": g_total,
            "Z_0": z0,
            "Z_1": z1,
            "Q_0": q0,
            "U": u_total,
            "reach_E_distribution": distribution,
        }


def compute_downstream(abc: dict[str, dict[str, Any]], q_d: Decimal, pre: dict[str, Any],
                       e_kernel: dict[str, Decimal], precision: int = 200) -> dict[str, Any]:
    """Stages 3-5: E_rates, fourfold, anchors, lambda (raw), counts, multinomial p."""
    with localcontext() as ctx:
        ctx.prec = precision
        alpha_e = e_kernel["alpha"]
        beta_e = e_kernel["beta"]
        q_e = pre["q_E"]
        g_total = pre["G"]
        z0 = pre["Z_0"]
        z1 = pre["Z_1"]
        u_e = ONE - alpha_e * alpha_e
        v_e = TWO * beta_e - beta_e * beta_e
        p_gp = z0 * u_e
        p_bp = z1 * v_e
        p_ge = pre["Q_0"] * (ONE - pre["U"]) + z0 * alpha_e * alpha_e
        p_be = ONE - p_gp - p_bp - p_ge
        first_abnormal = q_e * (ONE - beta_e) + (ONE - q_e) * alpha_e
        process_exit = q_e * (ONE - beta_e) * (ONE - beta_e) + (ONE - q_e) * alpha_e * alpha_e
        device_total_exit = p_ge + p_be
        counts = {
            "event_level": (ONE - beta_e) * (TWO - beta_e),
            "first_test_only": ONE - beta_e,
            "at_most_once_per_device": ONE - beta_e,
        }
        main: list[Decimal | None] = [None] * 4
        tilde: list[Decimal | None] = [None] * 4
        if q_e != ZERO:
            u, v, _g2, _q02, _u2, _z02, _z12 = _probability_products(abc, q_d, precision)
            numerator = [ZERO] * 4
            tilde_numerator = [ZERO] * 4
            denominator = q_e * g_total
            for index in range(16):
                x_a = index & 1
                x_b = (index >> 1) & 1
                x_c = (index >> 2) & 1
                x_d = (index >> 3) & 1
                members: list[int] = []
                if x_a:
                    members.append(0)
                if x_b:
                    members.append(1)
                if x_c:
                    members.append(2)
                if x_d:
                    members.append(3)
                if not members:
                    continue
                weight = _p_h(abc, q_d, x_a, x_b, x_c, x_d) * _pass_product(abc, u, v, x_a, x_b, x_c)
                share = weight / Decimal(len(members))
                for member in members:
                    numerator[member] += share
                    tilde_numerator[member] += weight
            main = [numerator[m] / denominator for m in range(4)]
            tilde = [tilde_numerator[m] / denominator for m in range(4)]
        return {
            "E_rates": {
                "first_abnormal": first_abnormal,
                "process_exit": process_exit,
                "device_total_exit": device_total_exit,
            },
            "fourfold": {"p_GP": p_gp, "p_BP": p_bp, "p_GE": p_ge, "p_BE": p_be},
            "anchors": {
                "E_S": HUNDRED * (p_gp + p_bp),
                "E_PL": p_bp,
                "E_PW": p_ge,
            },
            "lambda_main": main,
            "lambda_tilde": tilde,
            "counts": counts,
            "multinomial_p": [p_gp, p_bp, p_ge, p_be],
        }
