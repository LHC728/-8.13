"""Route B: explicit 16-state enumeration of the Q1 chain.

Frozen G2-02-SPEC-V1.0.3 route_B_enumeration: loop over the 16 H states with this
route's own multiplication code for P(H), and P(reach_E|H) = prod_{j in A,B,C}
pass_j(X_j) written explicitly through the two-attempt flow:
pass_j(0) = (1-alpha_j) + alpha_j*(1-alpha_j),
pass_j(1) = beta_j + (1-beta_j)*beta_j.
The E entry splits D by Bernoulli(q_D) per state.  Fourfold, lambda share 1/|H|,
counting conventions and tilde are accumulated state by state.  This file MUST NOT
import the other route modules or any shared core summation/feasibility code.
Standard library only.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Any

ZERO = Decimal(0)
ONE = Decimal(1)
TWO = Decimal(2)
HUNDRED = Decimal(100)
PROCESSES = ("A", "B", "C")


def _p_abc(abc: dict[str, dict[str, Any]], x_a: int, x_b: int, x_c: int) -> Decimal:
    """Own product code for P(X_A, X_B, X_C)."""
    product = ONE
    for process, x in (("A", x_a), ("B", x_b), ("C", x_c)):
        q = abc[process]["q"]
        product = product * (q if x else (ONE - q))
    return product


def _pass_j(abc: dict[str, dict[str, Any]], process: str, x: int) -> Decimal:
    """Pass probability through two attempts for process j given real state x.

    Explicit two-attempt flow (no u/v helper):
      normal (x=0): first test clear (1-alpha) or first abnormal (alpha) then retest clear;
      defective (x=1): first test clear (beta) or first abnormal (1-beta) then retest clear.
    """
    alpha = abc[process]["alpha"]
    beta = abc[process]["beta"]
    if x == 0:
        return (ONE - alpha) + alpha * (ONE - alpha)
    return beta + (ONE - beta) * beta


def _pass_product(abc: dict[str, dict[str, Any]], x_a: int, x_b: int, x_c: int) -> Decimal:
    return _pass_j(abc, "A", x_a) * _pass_j(abc, "B", x_b) * _pass_j(abc, "C", x_c)


def compute_pre_e(abc: dict[str, dict[str, Any]], q_d: Decimal, precision: int = 200) -> dict[str, Any]:
    """Stage 1 by 16-state enumeration: G, Z_0, Z_1, q_E, reach_E_distribution."""
    with localcontext() as ctx:
        ctx.prec = precision
        g_total = ZERO
        z0 = ZERO
        weights = [ZERO] * 16
        for x_a in (0, 1):
            for x_b in (0, 1):
                for x_c in (0, 1):
                    p_abc = _p_abc(abc, x_a, x_b, x_c)
                    pass_abc = _pass_product(abc, x_a, x_b, x_c)
                    for x_d in (0, 1):
                        p_d = q_d if x_d else (ONE - q_d)
                        weight = p_abc * pass_abc * p_d
                        g_total += weight
                        index = x_a + 2 * x_b + 4 * x_c + 8 * x_d
                        weights[index] += weight
                        if not (x_a or x_b or x_c or x_d):
                            z0 += weight
        z1 = g_total - z0
        q_e = z1 / g_total if g_total != ZERO else ZERO
        distribution = [w / g_total if g_total != ZERO else ZERO for w in weights]
        return {
            "q_E": q_e,
            "G": g_total,
            "Z_0": z0,
            "Z_1": z1,
            "reach_E_distribution": distribution,
        }


def compute_downstream(abc: dict[str, dict[str, Any]], q_d: Decimal, pre: dict[str, Any],
                       e_kernel: dict[str, Decimal], precision: int = 200) -> dict[str, Any]:
    """Stages 3-5 by 16-state enumeration: fourfold, lambda, counts, E_rates, anchors."""
    with localcontext() as ctx:
        ctx.prec = precision
        alpha_e = e_kernel["alpha"]
        beta_e = e_kernel["beta"]
        q_e = pre["q_E"]
        g_total = pre["G"]
        u_e = ONE - alpha_e * alpha_e
        v_e = TWO * beta_e - beta_e * beta_e
        p_gp = ZERO
        p_bp = ZERO
        p_ge = ZERO
        p_be = ZERO
        numerator = [ZERO] * 4
        tilde_numerator = [ZERO] * 4
        denominator = q_e * g_total
        for x_a in (0, 1):
            for x_b in (0, 1):
                for x_c in (0, 1):
                    p_abc = _p_abc(abc, x_a, x_b, x_c)
                    pass_abc = _pass_product(abc, x_a, x_b, x_c)
                    fail_abc = ONE - pass_abc
                    members: list[int] = []
                    if x_a:
                        members.append(0)
                    if x_b:
                        members.append(1)
                    if x_c:
                        members.append(2)
                    w0 = p_abc * pass_abc * (ONE - q_d)  # D normal branch
                    w1 = p_abc * pass_abc * q_d          # D defective branch
                    if not members:
                        # A/B/C all normal; H empty only in the d=0 branch.
                        p_gp += w0 * u_e
                        p_ge += p_abc * fail_abc + w0 * alpha_e * alpha_e
                        p_bp += w1 * v_e
                        p_be += w1 * (ONE - beta_e) * (ONE - beta_e)
                        if q_e != ZERO:
                            numerator[3] += w1
                            tilde_numerator[3] += w1
                    else:
                        # H nonempty in both D branches.
                        p_bp += (w0 + w1) * v_e
                        p_be += p_abc * fail_abc + (w0 + w1) * (ONE - beta_e) * (ONE - beta_e)
                        if q_e != ZERO:
                            h0 = list(members)
                            h1 = list(members) + [3]
                            share0 = w0 / Decimal(len(h0))
                            share1 = w1 / Decimal(len(h1))
                            for member in h0:
                                numerator[member] += share0
                                tilde_numerator[member] += w0
                            for member in h1:
                                numerator[member] += share1
                                tilde_numerator[member] += w1
        main: list[Decimal | None] = [None] * 4
        tilde: list[Decimal | None] = [None] * 4
        if q_e != ZERO:
            main = [numerator[m] / denominator for m in range(4)]
            tilde = [tilde_numerator[m] / denominator for m in range(4)]
        return {
            "E_rates": {
                "first_abnormal": q_e * (ONE - beta_e) + (ONE - q_e) * alpha_e,
                "process_exit": q_e * (ONE - beta_e) * (ONE - beta_e) + (ONE - q_e) * alpha_e * alpha_e,
                "device_total_exit": p_ge + p_be,
            },
            "fourfold": {"p_GP": p_gp, "p_BP": p_bp, "p_GE": p_ge, "p_BE": p_be},
            "anchors": {
                "E_S": HUNDRED * (p_gp + p_bp),
                "E_PL": p_bp,
                "E_PW": p_ge,
            },
            "lambda_main": main,
            "lambda_tilde": tilde,
            "counts": {
                "event_level": (ONE - beta_e) * (TWO - beta_e),
                "first_test_only": ONE - beta_e,
                "at_most_once_per_device": ONE - beta_e,
            },
            "multinomial_p": [p_gp, p_bp, p_ge, p_be],
        }
