"""Route C: absorption-chain computation of the Q1 chain.

Frozen G2-02-SPEC-V1.0.3 route_C_absorption_chain: per-H (including the D branch)
transition-matrix construction and absorption-probability linear solves
((I-Q)x = b, dense Gaussian elimination, Decimal >= 120, partial pivoting).
Pre-E phases per process j in {A,B,C} are F_j/R_j/P_j(absorbing)/X_j(absorbing);
the device pre-E stage is the 64 product states.  Any X_j sends the device to the
exit absorber; (P_A,P_B,P_C) enters the E stage, where the E_F entry splits by
Bernoulli(q_D) into (E_F,d=0)/(E_F,d=1).  Expected true-positive counts use the
expected-visit linear system on the E-branch chain (E_F/E_R visit expectations times
P(Y_E=1|H)).  This file MUST NOT import the other route modules or any shared core
summation/transition/feasibility code.  Standard library only.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Any

ZERO = Decimal(0)
ONE = Decimal(1)
TWO = Decimal(2)
HUNDRED = Decimal(100)
PROCESSES = ("A", "B", "C")


def _gauss_solve(n: int, qmat: list[list[Decimal]], b: list[Decimal], precision: int) -> list[Decimal]:
    """Solve (I-Q)x = b by dense Gaussian elimination with partial pivoting."""
    with localcontext() as ctx:
        ctx.prec = precision
        matrix: list[list[Decimal]] = []
        for r in range(n):
            row = [ZERO] * (n + 1)
            for c in range(n):
                row[c] = (ONE if r == c else ZERO) - qmat[r][c]
            row[n] = b[r]
            matrix.append(row)
        for col in range(n):
            pivot = max(range(col, n), key=lambda r: abs(matrix[r][col]))
            if matrix[pivot][col] == ZERO:
                raise ArithmeticError("singular absorption matrix")
            if pivot != col:
                matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
            pivot_value = matrix[col][col]
            for r in range(col + 1, n):
                factor = matrix[r][col] / pivot_value
                if factor == ZERO:
                    continue
                row_r = matrix[r]
                row_c = matrix[col]
                for c in range(col, n + 1):
                    row_r[c] = row_r[c] - factor * row_c[c]
        x = [ZERO] * n
        for r in range(n - 1, -1, -1):
            acc = matrix[r][n]
            for c in range(r + 1, n):
                acc = acc - matrix[r][c] * x[c]
            x[r] = acc / matrix[r][r]
        return x


def _pass_j(abc: dict[str, dict[str, Any]], process: str, x: int) -> Decimal:
    """Per-attempt clear probability for process j given real state x (own code)."""
    alpha = abc[process]["alpha"]
    beta = abc[process]["beta"]
    return (ONE - alpha) if x == 0 else beta


def _product_index(s_a: int, s_b: int, s_c: int) -> int:
    # Phase codes: 0=F (first test), 1=R (retest), 2=P (passed), 3=X (exited).
    return s_a * 16 + s_b * 4 + s_c


def _next_states(abc: dict[str, dict[str, Any]], x_a: int, x_b: int, x_c: int) -> dict[int, list[tuple[Any, Decimal]]]:
    """Transitions over all 64 product states (sequential A -> B -> C flow).

    next is a product-state index, None for the device exit absorber, or "E" for
    entry into the E stage.
    """
    transitions: dict[int, list[tuple[Any, Decimal]]] = {}
    for s_a in range(4):
        for s_b in range(4):
            for s_c in range(4):
                index = _product_index(s_a, s_b, s_c)
                outs: list[tuple[Any, Decimal]]
                if 3 in (s_a, s_b, s_c):
                    outs = [(None, ONE)]  # any X_j -> device exit absorber
                elif s_a in (0, 1):
                    p = _pass_j(abc, "A", x_a)
                    if s_a == 0:
                        outs = [(_product_index(2, s_b, s_c), p), (_product_index(1, s_b, s_c), ONE - p)]
                    else:
                        outs = [(_product_index(2, s_b, s_c), p), (_product_index(3, s_b, s_c), ONE - p)]
                elif s_b in (0, 1):
                    p = _pass_j(abc, "B", x_b)
                    if s_b == 0:
                        outs = [(_product_index(s_a, 2, s_c), p), (_product_index(s_a, 1, s_c), ONE - p)]
                    else:
                        outs = [(_product_index(s_a, 2, s_c), p), (_product_index(s_a, 3, s_c), ONE - p)]
                elif s_c in (0, 1):
                    p = _pass_j(abc, "C", x_c)
                    if s_c == 0:
                        outs = [(_product_index(s_a, s_b, 2), p), (_product_index(s_a, s_b, 1), ONE - p)]
                    else:
                        outs = [(_product_index(s_a, s_b, 2), p), (_product_index(s_a, s_b, 3), ONE - p)]
                else:  # s_a == s_b == s_c == 2 -> all passed, enter E stage
                    outs = [("E", ONE)]
                transitions[index] = outs
    return transitions


def _reachable_states(transitions: dict[int, list[tuple[Any, Decimal]]], start: int) -> list[int]:
    seen = {start}
    stack = [start]
    while stack:
        state = stack.pop()
        for nxt, _prob in transitions[state]:
            if nxt is not None and nxt != "E" and nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return sorted(seen)


def _solve_pre_e(abc: dict[str, dict[str, Any]], x_a: int, x_b: int, x_c: int, precision: int) -> Decimal:
    """P(enter E stage) for a device with real A/B/C states, by absorption solve."""
    with localcontext() as ctx:
        ctx.prec = precision
        transitions = _next_states(abc, x_a, x_b, x_c)
        states = _reachable_states(transitions, _product_index(0, 0, 0))
        position = {state: i for i, state in enumerate(states)}
        n = len(states)
        qmat: list[list[Decimal]] = [[ZERO] * n for _ in range(n)]
        b = [ZERO] * n
        for state in states:
            row = position[state]
            for nxt, prob in transitions[state]:
                if nxt == "E":
                    b[row] += prob  # direct transition into the E-stage absorber
                elif nxt is not None:
                    qmat[row][position[nxt]] += prob
                # nxt is None -> device exit absorber: mass leaves the system,
                # it contributes neither to Q nor to the E-absorption RHS.
        solution = _gauss_solve(n, qmat, b, precision)
        return solution[position[_product_index(0, 0, 0)]]


def _solve_e_branch(p_ok: Decimal, p_bad: Decimal, precision: int) -> tuple[Decimal, Decimal]:
    """Absorption solve on the 4-state E-branch chain: return (P(pass), P(exit))."""
    with localcontext() as ctx:
        ctx.prec = precision
        qmat: list[list[Decimal]] = [[ZERO, ZERO], [ZERO, ZERO]]
        b_pass = [ZERO, ZERO]
        qmat[0][1] = p_bad   # E_F -> E_R
        b_pass[0] = p_ok     # E_F -> PASS
        b_pass[1] = p_ok     # E_R -> PASS
        solution = _gauss_solve(2, qmat, b_pass, precision)
        p_pass = solution[0]
        return p_pass, ONE - p_pass


def _solve_visits(qmat: list[list[Decimal]], start: int, precision: int) -> list[Decimal]:
    """Expected-visit system (I-Q)^T v = e_start.

    With row-stochastic Q, (I-Q)^{-1}[i][j] is the expected number of visits to j
    starting from i, so the visit vector from `start` is the start-th ROW of
    (I-Q)^{-1}, obtained by solving the transposed system.
    """
    with localcontext() as ctx:
        ctx.prec = precision
        n = len(qmat)
        qmat_transpose = [[qmat[c][r] for c in range(n)] for r in range(n)]
        b = [ZERO] * n
        b[start] = ONE
        return _gauss_solve(n, qmat_transpose, b, precision)


def _p_abc(abc: dict[str, dict[str, Any]], x_a: int, x_b: int, x_c: int) -> Decimal:
    """Own product code for P(X_A, X_B, X_C)."""
    product = ONE
    for process, x in (("A", x_a), ("B", x_b), ("C", x_c)):
        q = abc[process]["q"]
        product = product * (q if x else (ONE - q))
    return product


def compute_pre_e(abc: dict[str, dict[str, Any]], q_d: Decimal, precision: int = 200) -> dict[str, Any]:
    """Stage 1 via per-H absorption chains: G, Z_0, Z_1, q_E, reach_E_distribution."""
    with localcontext() as ctx:
        ctx.prec = precision
        g_total = ZERO
        z0 = ZERO
        weights = [ZERO] * 16
        per_x: dict[tuple[int, int, int], Decimal] = {}
        for x_a in (0, 1):
            for x_b in (0, 1):
                for x_c in (0, 1):
                    p_abc = _p_abc(abc, x_a, x_b, x_c)
                    p_enter = _solve_pre_e(abc, x_a, x_b, x_c, precision)
                    per_x[(x_a, x_b, x_c)] = p_enter
                    for x_d in (0, 1):
                        p_d = q_d if x_d else (ONE - q_d)
                        weight = p_abc * p_enter * p_d
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
            "per_x": per_x,
        }


def compute_downstream(abc: dict[str, dict[str, Any]], q_d: Decimal, pre: dict[str, Any],
                       e_kernel: dict[str, Decimal], precision: int = 200) -> dict[str, Any]:
    """Stages 3-5 via per-H chains: fourfold, lambda, counts, E_rates, anchors."""
    with localcontext() as ctx:
        ctx.prec = precision
        alpha_e = e_kernel["alpha"]
        beta_e = e_kernel["beta"]
        q_e = pre["q_E"]
        g_total = pre["G"]
        p_gp = ZERO
        p_bp = ZERO
        p_ge = ZERO
        p_be = ZERO
        numerator = [ZERO] * 4
        tilde_numerator = [ZERO] * 4
        denominator = q_e * g_total
        # E-stage branch chains: H empty (d=0 branch of all-normal) vs H nonempty.
        pass_empty, exit_empty = _solve_e_branch(ONE - alpha_e, alpha_e, precision)
        pass_defect, exit_defect = _solve_e_branch(beta_e, ONE - beta_e, precision)
        for x_a in (0, 1):
            for x_b in (0, 1):
                for x_c in (0, 1):
                    p_abc = _p_abc(abc, x_a, x_b, x_c)
                    p_enter = pre["per_x"][(x_a, x_b, x_c)]
                    exit_pre_e = ONE - p_enter
                    members: list[int] = []
                    if x_a:
                        members.append(0)
                    if x_b:
                        members.append(1)
                    if x_c:
                        members.append(2)
                    w0 = p_abc * p_enter * (ONE - q_d)  # d=0 (D normal) branch
                    w1 = p_abc * p_enter * q_d          # d=1 (D defective) branch
                    if not members:
                        p_gp += w0 * pass_empty
                        p_ge += p_abc * exit_pre_e + w0 * exit_empty
                        p_bp += w1 * pass_defect
                        p_be += w1 * exit_defect
                        if q_e != ZERO:
                            numerator[3] += w1
                            tilde_numerator[3] += w1
                    else:
                        p_bp += (w0 + w1) * pass_defect
                        p_be += p_abc * exit_pre_e + (w0 + w1) * exit_defect
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
        # Expected true-positive counts: E-branch (defective) visit expectations times
        # P(Y_E=1 | H) = 1 - beta_E.
        p_bad = ONE - beta_e
        visits = _solve_visits([[ZERO, p_bad], [ZERO, ZERO]], 0, precision)
        visit_ef = visits[0]
        visit_er = visits[1]
        true_positive_per_visit = ONE - beta_e
        counts = {
            "event_level": (visit_ef + visit_er) * true_positive_per_visit,
            "first_test_only": visit_ef * true_positive_per_visit,
            "at_most_once_per_device": visit_ef * true_positive_per_visit,
        }
        return {
            "E_rates": {
                "first_abnormal": q_e * p_bad + (ONE - q_e) * alpha_e,
                "process_exit": q_e * p_bad * p_bad + (ONE - q_e) * alpha_e * alpha_e,
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
            "counts": counts,
            "multinomial_p": [p_gp, p_bp, p_ge, p_be],
        }
