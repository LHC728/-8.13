"""Frozen G2-01 E1 observation-kernel calibrator (standard library only)."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, localcontext
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "observation_calibration_v1"
SINGLE = "single_test_unconditional_v1"
CHAIN = "standard_chain_v1"
TOL = Decimal("1e-12")
WIDTH_TOL = Decimal("1e-14")
NEAR_BOUNDARY = Decimal("1e-30")
MAX_ITERATIONS = 300
MAX_PRECISION_INCREMENT = 800
ZERO = Decimal(0)
ONE = Decimal(1)
TWO = Decimal(2)
DECIMAL_PROBABILITY = re.compile(r"^(?:0(?:\.[0-9]+)?|1(?:\.0+)?)$")
BINDINGS = {"A": ("P026", "P030"), "B": ("P027", "P031"), "C": ("P028", "P032")}


class ValidationError(Exception):
    pass


class NumericalError(Exception):
    pass


def _decimal_string(value: Any, label: str) -> Decimal:
    if not isinstance(value, str) or not DECIMAL_PROBABILITY.fullmatch(value):
        raise ValidationError(f"{label} must be a canonical decimal probability string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError(f"{label} is not a finite decimal") from exc
    if not number.is_finite() or number < ZERO or number > ONE:
        raise ValidationError(f"{label} is outside [0,1]")
    return number


def _plain(value: Decimal, significant: int | None = None) -> str:
    if not value.is_finite():
        raise NumericalError("non-finite Decimal during serialization")
    if value == ZERO:
        return "0"
    if significant is not None:
        adjustment = value.copy_abs().adjusted()
        quantum = Decimal(1).scaleb(adjustment - significant + 1)
        value = value.quantize(quantum)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def _input_plain(value: Decimal) -> str:
    """Keep request q/e exact so a checker can reproduce near-boundary classes."""
    return _plain(value)


def _significant_digits(value: Decimal) -> int:
    """Frozen lexical significant-digit rule; Decimal preserves input trailing zeroes."""
    digits = "".join(str(digit) for digit in value.as_tuple().digits)
    stripped = digits.lstrip("0")
    return len(stripped) if stripped else 1


def _outward(value: Decimal, precision: int, rounding: str) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = precision
        ctx.rounding = rounding
        return +value


def _sqrt_interval(value: Decimal, precision: int) -> tuple[Decimal, Decimal]:
    if value < ZERO:
        raise NumericalError("square-root radicand outside frozen domain")
    with localcontext() as ctx:
        ctx.prec = precision + 20
        root = value.sqrt()
        low_raw, high_raw = root.next_minus(), root.next_plus()
    return _outward(low_raw, precision, ROUND_FLOOR), _outward(high_raw, precision, ROUND_CEILING)


def _interval_add(left: tuple[Decimal, Decimal], right: tuple[Decimal, Decimal], precision: int) -> tuple[Decimal, Decimal]:
    return (_outward(left[0] + right[0], precision, ROUND_FLOOR), _outward(left[1] + right[1], precision, ROUND_CEILING))


def _interval_sub(left: tuple[Decimal, Decimal], right: tuple[Decimal, Decimal], precision: int) -> tuple[Decimal, Decimal]:
    return (_outward(left[0] - right[1], precision, ROUND_FLOOR), _outward(left[1] - right[0], precision, ROUND_CEILING))


def _interval_mul_nonnegative(left: tuple[Decimal, Decimal], right: tuple[Decimal, Decimal], precision: int) -> tuple[Decimal, Decimal]:
    if left[0] < ZERO or right[0] < ZERO:
        raise NumericalError("negative interval supplied to nonnegative multiplication")
    return (_outward(left[0] * right[0], precision, ROUND_FLOOR), _outward(left[1] * right[1], precision, ROUND_CEILING))


def _interval_div_positive(left: tuple[Decimal, Decimal], right: tuple[Decimal, Decimal], precision: int) -> tuple[Decimal, Decimal]:
    if right[0] <= ZERO:
        raise NumericalError("non-positive denominator interval")
    return (_outward(left[0] / right[1], precision, ROUND_FLOOR), _outward(left[1] / right[0], precision, ROUND_CEILING))


def _probability_codomain(bounds: tuple[Decimal, Decimal]) -> tuple[Decimal, Decimal]:
    """Intersect a complete outward parameter enclosure with its proven [0,1] codomain."""
    lower, upper = max(bounds[0], ZERO), min(bounds[1], ONE)
    if lower > upper:
        raise NumericalError("parameter interval has empty intersection with [0,1]")
    return lower, upper


def _certificate_notes(root_alpha: tuple[Decimal, Decimal], root_beta: tuple[Decimal, Decimal],
                       reported_alpha: Decimal, reported_beta: Decimal) -> list[str]:
    reported_alpha_bounds = (min(root_alpha[0], reported_alpha), max(root_alpha[1], reported_alpha))
    reported_beta_bounds = (min(root_beta[0], reported_beta), max(root_beta[1], reported_beta))
    return [
        f"root_alpha_lo={_plain(root_alpha[0])}", f"root_alpha_hi={_plain(root_alpha[1])}",
        f"root_alpha_span={_plain(root_alpha[1] - root_alpha[0])}",
        f"root_beta_lo={_plain(root_beta[0])}", f"root_beta_hi={_plain(root_beta[1])}",
        f"root_beta_span={_plain(root_beta[1] - root_beta[0])}",
        f"reported_alpha_lo={_plain(reported_alpha_bounds[0])}", f"reported_alpha_hi={_plain(reported_alpha_bounds[1])}",
        f"reported_alpha_span={_plain(reported_alpha_bounds[1] - reported_alpha_bounds[0])}",
        f"reported_beta_lo={_plain(reported_beta_bounds[0])}", f"reported_beta_hi={_plain(reported_beta_bounds[1])}",
        f"reported_beta_span={_plain(reported_beta_bounds[1] - reported_beta_bounds[0])}",
    ]


def _round_trip(bounds_alpha: tuple[Decimal, Decimal], bounds_beta: tuple[Decimal, Decimal],
                q: Decimal, e: Decimal, semantics: str) -> tuple[Decimal, Decimal, dict[str, str]]:
    alpha_midpoint = (bounds_alpha[0] + bounds_alpha[1]) / TWO
    beta_midpoint = (bounds_beta[0] + bounds_beta[1]) / TWO
    alpha_text = _plain(alpha_midpoint, 17)
    beta_text = _plain(beta_midpoint, 17)
    parsed_alpha = Decimal(alpha_text)
    parsed_beta = Decimal(beta_text)
    residuals = _public_residuals(q, e, alpha_text, beta_text, semantics)
    if max(Decimal(item) for item in residuals.values()) > Decimal("5e-12"):
        raise NumericalError("17-digit serialized round-trip residual exceeds frozen tolerance")
    return parsed_alpha, parsed_beta, residuals


def _certified_public_solution(root_alpha: tuple[Decimal, Decimal], root_beta: tuple[Decimal, Decimal],
                               q: Decimal, e: Decimal, semantics: str) -> tuple[Decimal, Decimal, dict[str, str], list[str]]:
    root_alpha_span = root_alpha[1] - root_alpha[0]
    root_beta_span = root_beta[1] - root_beta[0]
    if root_alpha_span > Decimal("1e-12") or root_beta_span > Decimal("1e-12"):
        raise NumericalError("true-root parameter interval exceeds frozen span")
    public_alpha, public_beta, residuals = _round_trip(root_alpha, root_beta, q, e, semantics)
    reported_alpha_span = max(root_alpha[1], public_alpha) - min(root_alpha[0], public_alpha)
    reported_beta_span = max(root_beta[1], public_beta) - min(root_beta[0], public_beta)
    if reported_alpha_span > Decimal("1e-12") or reported_beta_span > Decimal("1e-12"):
        raise NumericalError("reported public hull exceeds frozen span")
    notes = _certificate_notes(root_alpha, root_beta, public_alpha, public_beta)
    return public_alpha, public_beta, residuals, notes


def _single_parameter_bounds(q: Decimal, e: Decimal, precision: int) -> tuple[tuple[Decimal, Decimal], tuple[Decimal, Decimal]]:
    with localcontext() as ctx:
        ctx.prec = precision
        denominator_alpha = TWO * (ONE - q)
        denominator_beta = TWO * q
    with localcontext() as ctx:
        ctx.prec = precision
        ctx.rounding = ROUND_FLOOR
        alpha_lo = e / denominator_alpha
        beta_lo = e / denominator_beta
    with localcontext() as ctx:
        ctx.prec = precision
        ctx.rounding = ROUND_CEILING
        alpha_hi = e / denominator_alpha
        beta_hi = e / denominator_beta
    alpha_bounds = _probability_codomain((alpha_lo, alpha_hi))
    beta_bounds = _probability_codomain((beta_lo, beta_hi))
    if e == ZERO:
        return (ZERO, ZERO), (ZERO, ZERO)
    if e == denominator_alpha:
        alpha_bounds = (ONE, ONE)
    if e == denominator_beta:
        beta_bounds = (ONE, ONE)
    return alpha_bounds, beta_bounds


def _residuals(q: Decimal, e: Decimal, alpha: Decimal, beta: Decimal, semantics: str) -> dict[str, str]:
    precision = max(120, max(_significant_digits(q), _significant_digits(e)) + 80)
    with localcontext() as ctx:
        ctx.prec = precision
        if semantics == SINGLE:
            left_1 = (ONE - q) * alpha
            left_2 = q * beta
            target = e / TWO
            values = (abs(left_1 - target), abs(left_2 - target), abs(left_1 - left_2))
        else:
            d_value = ONE + (ONE - q) * alpha + q * (ONE - beta)
            a_value = (ONE - q) * (alpha + alpha * alpha)
            b_value = q * (TWO * beta - beta * beta)
            target = e * d_value / TWO
            values = (abs(a_value - target), abs(b_value - target), abs(a_value - b_value))
        return {
            "equation_1_abs": _plain(values[0], 17),
            "equation_2_abs": _plain(values[1], 17),
            "balance_abs": _plain(values[2], 17),
        }


def _public_residuals(q: Decimal, e: Decimal, alpha_text: str, beta_text: str, semantics: str) -> dict[str, str]:
    """Reparse actual public strings and evaluate at frozen p0, independent of caller context."""
    return _residuals(q, e, Decimal(alpha_text), Decimal(beta_text), semantics)


def _diagnostics(method: str, feasibility: str, uniqueness: str, iterations: int, variable: str,
                 lower: Decimal | None, upper: Decimal | None, residuals: dict[str, str] | None,
                 notes: list[str] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "method": method,
        "feasibility": feasibility,
        "uniqueness": uniqueness,
        "iterations": iterations,
        "bracket": {
            "variable": variable,
            "lower": None if lower is None else _plain(lower),
            "upper": None if upper is None else _plain(upper),
            "final_width": None if lower is None or upper is None else _plain(upper - lower),
        },
        "residuals": residuals,
        "tolerance_profile": "observation_calibration_v1_tol",
    }
    if notes:
        item["notes"] = notes
    return item


def _result(process_id: str, status: str, q: Decimal, e: Decimal, alpha: Decimal | None,
            beta: Decimal | None, e_max: Decimal, free: list[str], diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "process_id": process_id,
        "status": status,
        "q": _input_plain(q),
        "e": _input_plain(e),
        "alpha": None if alpha is None else _plain(alpha, 17),
        "beta": None if beta is None else _plain(beta, 17),
        "e_max": _plain(e_max, 17),
        "free_parameters": free,
        "diagnostics": diagnostics,
    }


def _endpoint(process_id: str, q: Decimal, e: Decimal, semantics: str) -> dict[str, Any]:
    if e != ZERO:
        return _result(process_id, "INFEASIBLE", q, e, None, None, ZERO, [], _diagnostics(
            "feasibility_only", "INFEASIBLE", "NO_SOLUTION", 0, "NONE", None, None, None,
            ["endpoint permits only e=0"]))
    if q == ZERO:
        return _result(process_id, "NONIDENTIFIABLE_FAMILY", q, e, ZERO, None, ZERO, ["beta"], _diagnostics(
            "endpoint_analysis", "FEASIBLE", "NONIDENTIFIABLE_FAMILY", 0, "NONE", None, None,
            None, ["beta is free on [0,1]"]))
    return _result(process_id, "NONIDENTIFIABLE_FAMILY", q, e, None, ZERO, ZERO, ["alpha"], _diagnostics(
        "endpoint_analysis", "FEASIBLE", "NONIDENTIFIABLE_FAMILY", 0, "NONE", None, None,
        None, ["alpha is free on [0,1]"]))


def solve_single(process_id: str, q: Decimal, e: Decimal) -> dict[str, Any]:
    p0 = max(120, max(_significant_digits(q), _significant_digits(e)) + 80)
    with localcontext() as ctx:
        ctx.prec = p0
        if q == ZERO or q == ONE:
            return _endpoint(process_id, q, e, SINGLE)
        e_max = TWO * min(q, ONE - q)
        if e > e_max:
            return _result(process_id, "INFEASIBLE", q, e, None, None, e_max, [], _diagnostics(
                "feasibility_only", "INFEASIBLE", "NO_SOLUTION", 0, "NONE", None, None, None,
                ["e exceeds exact single-test feasibility bound"]))
        root_alpha, root_beta = _single_parameter_bounds(q, e, p0)
        alpha, beta, residuals, notes = _certified_public_solution(root_alpha, root_beta, q, e, SINGLE)
        return _result(process_id, "UNIQUE_SOLUTION", q, e, alpha, beta, e_max, [], _diagnostics(
            "closed_form", "FEASIBLE", "UNIQUE", 0, "NONE", None, None, residuals,
            notes))


def _chain_values(q: Decimal, t: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    alpha_radicand = ONE + (Decimal(4) * t / (ONE - q))
    beta_radicand = ONE - (t / q)
    if alpha_radicand < ZERO or beta_radicand < ZERO:
        raise NumericalError("square-root radicand outside frozen domain")
    alpha = (-ONE + alpha_radicand.sqrt()) / TWO
    beta = ONE - beta_radicand.sqrt()
    d_value = ONE + (ONE - q) * alpha + q * (ONE - beta)
    if d_value <= ZERO:
        raise NumericalError("non-positive standard-chain D")
    return alpha, beta, d_value, TWO * t / d_value


def _chain_parameter_bounds(q: Decimal, lower: Decimal, upper: Decimal, precision: int) -> tuple[tuple[Decimal, Decimal], tuple[Decimal, Decimal]]:
    """Map the monotone t bracket through outward-rounded formula intervals."""
    with localcontext() as ctx:
        ctx.prec = precision + 20
        alpha_low_arg = ONE + Decimal(4) * lower / (ONE - q)
        alpha_high_arg = ONE + Decimal(4) * upper / (ONE - q)
        beta_low_arg = ONE - upper / q
        beta_high_arg = ONE - lower / q
    alpha_low_sqrt, _ = _sqrt_interval(alpha_low_arg, precision)
    _, alpha_high_sqrt = _sqrt_interval(alpha_high_arg, precision)
    beta_low_sqrt, _ = _sqrt_interval(beta_low_arg, precision)
    _, beta_high_sqrt = _sqrt_interval(beta_high_arg, precision)
    with localcontext() as ctx:
        ctx.prec = precision
        alpha_bounds = (_outward((alpha_low_sqrt - ONE) / TWO, precision, ROUND_FLOOR),
                        _outward((alpha_high_sqrt - ONE) / TWO, precision, ROUND_CEILING))
        beta_bounds = (_outward(ONE - beta_high_sqrt, precision, ROUND_FLOOR),
                       _outward(ONE - beta_low_sqrt, precision, ROUND_CEILING))
    alpha_bounds, beta_bounds = _probability_codomain(alpha_bounds), _probability_codomain(beta_bounds)
    # Exact algebraic endpoint identities are retained after the complete map.
    if lower == upper == ZERO:
        return (ZERO, ZERO), (ZERO, ZERO)
    if lower == upper == q and q < TWO * (ONE - q):
        beta_bounds = (ONE, ONE)
    if lower == upper == TWO * (ONE - q) and TWO * (ONE - q) < q:
        alpha_bounds = (ONE, ONE)
    return alpha_bounds, beta_bounds


def _chain_e_max(q: Decimal, precision: int) -> tuple[Decimal, Decimal]:
    with localcontext() as ctx:
        ctx.prec = precision
        t_max = min(TWO * (ONE - q), q)
        return _chain_values(q, t_max)[3], t_max


def _chain_e_max_interval(q: Decimal, precision: int) -> tuple[Decimal, Decimal, Decimal]:
    with localcontext() as ctx:
        ctx.prec = precision + 20
        t_max = min(TWO * (ONE - q), q)
        alpha_arg = ONE + Decimal(4) * t_max / (ONE - q)
        beta_arg = ONE - t_max / q
    alpha_root_low, alpha_root_high = _sqrt_interval(alpha_arg, precision)
    beta_root_low, beta_root_high = _sqrt_interval(beta_arg, precision)
    with localcontext() as ctx:
        ctx.prec = precision
        alpha_bounds = (_outward((alpha_root_low - ONE) / TWO, precision, ROUND_FLOOR),
                        _outward((alpha_root_high - ONE) / TWO, precision, ROUND_CEILING))
        beta_bounds = (_outward(ONE - beta_root_high, precision, ROUND_FLOOR),
                       _outward(ONE - beta_root_low, precision, ROUND_CEILING))
        alpha_bounds = _probability_codomain(alpha_bounds)
        beta_bounds = _probability_codomain(beta_bounds)
        d_bounds = _interval_add((ONE, ONE), _interval_mul_nonnegative((ONE - q, ONE - q), alpha_bounds, precision), precision)
        d_bounds = _interval_add(d_bounds, _interval_mul_nonnegative((q, q), (ONE - beta_bounds[1], ONE - beta_bounds[0]), precision), precision)
        e_bounds = _interval_div_positive((TWO * t_max, TWO * t_max), d_bounds, precision)
    return e_bounds[0], e_bounds[1], t_max


def solve_chain(process_id: str, q: Decimal, e: Decimal) -> dict[str, Any]:
    if q == ZERO or q == ONE:
        return _endpoint(process_id, q, e, CHAIN)
    p0 = max(120, max(_significant_digits(q), _significant_digits(e)) + 80)
    precision: int | None = None
    feasibility: str | None = None
    e_max = t_max = None
    for candidate_precision in range(p0, p0 + MAX_PRECISION_INCREMENT + 1, 80):
        lower_e_max, upper_e_max, candidate_t_max = _chain_e_max_interval(q, candidate_precision)
        if e < lower_e_max:
            feasibility = "FEASIBLE"
            precision, t_max = candidate_precision, candidate_t_max
            with localcontext() as ctx:
                ctx.prec = precision
                e_max, _ = _chain_e_max(q, precision)
            break
        if e > upper_e_max:
            feasibility = "INFEASIBLE"
            precision, t_max = candidate_precision, candidate_t_max
            with localcontext() as ctx:
                ctx.prec = precision
                e_max, _ = _chain_e_max(q, precision)
            break
    if precision is None or e_max is None or t_max is None or feasibility is None:
        raise NumericalError("standard-chain feasibility interval unresolved at frozen precision limit")
    with localcontext() as ctx:
        ctx.prec = precision
        if feasibility == "INFEASIBLE":
            return _result(process_id, "INFEASIBLE", q, e, None, None, e_max, [], _diagnostics(
                "feasibility_only", "INFEASIBLE", "NO_SOLUTION", 0, "t", ZERO, t_max, None,
                ["e exceeds strict standard-chain e_max"]))
        if e == ZERO:
            root_alpha = root_beta = (ZERO, ZERO)
            alpha, beta, residuals, notes = _certified_public_solution(root_alpha, root_beta, q, e, CHAIN)
            return _result(process_id, "UNIQUE_SOLUTION", q, e, alpha, beta, e_max, [], _diagnostics(
                "scalar_t_bisection", "FEASIBLE", "UNIQUE", 0, "t", ZERO, ZERO,
                residuals, ["lower endpoint", *notes] ))
        if e == e_max:
            root_alpha, root_beta = _chain_parameter_bounds(q, t_max, t_max, precision)
            alpha, beta, residuals, notes = _certified_public_solution(root_alpha, root_beta, q, e, CHAIN)
            return _result(process_id, "UNIQUE_SOLUTION", q, e, alpha, beta, e_max, [], _diagnostics(
                "scalar_t_bisection", "FEASIBLE", "UNIQUE", 0, "t", t_max, t_max,
                residuals, ["upper endpoint", *notes] ))

        lower, upper = ZERO, t_max
        _, _, _, h_lower = _chain_values(q, lower)
        _, _, _, h_upper = _chain_values(q, upper)
        if not (h_lower < e < h_upper):
            raise NumericalError("strict standard-chain root bracket not established")
        for iteration in range(1, MAX_ITERATIONS + 1):
            midpoint = (lower + upper) / TWO
            alpha, beta, _, h_mid = _chain_values(q, midpoint)
            if h_mid == e:
                alpha_bounds, beta_bounds = _chain_parameter_bounds(q, midpoint, midpoint, precision)
                alpha, beta, residuals, notes = _certified_public_solution(alpha_bounds, beta_bounds, q, e, CHAIN)
                return _result(process_id, "UNIQUE_SOLUTION", q, e, alpha, beta, e_max, [], _diagnostics(
                    "scalar_t_bisection", "FEASIBLE", "UNIQUE", iteration, "t", midpoint, midpoint, residuals,
                    notes))
            if h_mid < e:
                lower = midpoint
            else:
                upper = midpoint
            candidate = (lower + upper) / TWO
            alpha, beta, _, _ = _chain_values(q, candidate)
            alpha_bounds, beta_bounds = _chain_parameter_bounds(q, lower, upper, precision)
            alpha_span = alpha_bounds[1] - alpha_bounds[0]
            beta_span = beta_bounds[1] - beta_bounds[0]
            if upper - lower <= WIDTH_TOL and alpha_span <= Decimal("1e-12") and beta_span <= Decimal("1e-12"):
                try:
                    alpha, beta, residuals, notes = _certified_public_solution(alpha_bounds, beta_bounds, q, e, CHAIN)
                except NumericalError:
                    continue
                return _result(process_id, "UNIQUE_SOLUTION", q, e, alpha, beta, e_max, [], _diagnostics(
                    "scalar_t_bisection", "FEASIBLE", "UNIQUE", iteration, "t", lower, upper, residuals,
                    notes))
        raise NumericalError("standard-chain bisection exhausted frozen iteration limit")


def _read_parameters(path: Path) -> dict[str, str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        raise ValidationError(f"cannot read parameter CSV: {exc}") from exc
    found: dict[str, str] = {}
    for row in rows:
        parameter_id = row.get("parameter_id")
        if parameter_id in {None, ""}:
            continue
        if parameter_id in found:
            raise ValidationError(f"duplicate parameter_id {parameter_id}")
        # The CSV contains non-numeric decision entries outside this task's
        # bindings.  Parsing is deliberately deferred to the requested IDs.
        found[parameter_id] = row.get("value", "")
    return found


def _require_keys(value: dict[str, Any], allowed: set[str], required: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    missing = required - value.keys()
    extra = value.keys() - allowed
    if missing or extra:
        raise ValidationError(f"{label} has invalid fields (missing={sorted(missing)}, extra={sorted(extra)})")


def _parse_request(request: Any, parameters: dict[str, str]) -> tuple[str, str, str, list[tuple[str, Decimal, Decimal]]]:
    _require_keys(request, {"schema_version", "envelope_type", "request_id", "scenario_role", "semantics", "items"},
                  {"schema_version", "envelope_type", "request_id", "scenario_role", "semantics", "items"}, "request")
    if request["schema_version"] != SCHEMA_VERSION or request["envelope_type"] != "calibration_request":
        raise ValidationError("wrong schema_version or envelope_type")
    request_id = request["request_id"]
    if not isinstance(request_id, str) or not (1 <= len(request_id) <= 128):
        raise ValidationError("request_id must be a non-empty stable string")
    role, semantics, items = request["scenario_role"], request["semantics"], request["items"]
    if role not in {"canonical_g2_abc", "generic", "test_oracle"} or semantics not in {SINGLE, CHAIN}:
        raise ValidationError("invalid scenario_role or semantics")
    if not isinstance(items, list) or not (1 <= len(items) <= 64):
        raise ValidationError("items must be a non-empty array with at most 64 entries")
    parsed: list[tuple[str, Decimal, Decimal]] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        _require_keys(item, {"process_id", "canonical_parameter_ref", "direct_values"}, {"process_id"}, f"items[{index}]")
        process_id = item["process_id"]
        if not isinstance(process_id, str) or not (1 <= len(process_id) <= 64) or process_id in seen:
            raise ValidationError(f"items[{index}].process_id is invalid or duplicate")
        seen.add(process_id)
        has_ref, has_direct = "canonical_parameter_ref" in item, "direct_values" in item
        if has_ref == has_direct:
            raise ValidationError(f"items[{index}] needs exactly one value source")
        if has_direct:
            direct = item["direct_values"]
            _require_keys(direct, {"q", "e"}, {"q", "e"}, f"items[{index}].direct_values")
            q, e = _decimal_string(direct["q"], "q"), _decimal_string(direct["e"], "e")
        else:
            ref = item["canonical_parameter_ref"]
            _require_keys(ref, {"source", "q_parameter_id", "e_parameter_id"},
                          {"source", "q_parameter_id", "e_parameter_id"}, f"items[{index}].canonical_parameter_ref")
            if ref["source"] != "02_数据/parameters.csv":
                raise ValidationError("canonical source must be 02_数据/parameters.csv")
            q_id, e_id = ref["q_parameter_id"], ref["e_parameter_id"]
            if not isinstance(q_id, str) or not re.fullmatch(r"P[0-9]{3}", q_id) or not isinstance(e_id, str) or not re.fullmatch(r"P[0-9]{3}", e_id):
                raise ValidationError("canonical parameter IDs are invalid")
            if q_id not in parameters or e_id not in parameters:
                raise ValidationError("canonical parameter_id missing from CSV")
            try:
                q, e = Decimal(parameters[q_id]), Decimal(parameters[e_id])
            except InvalidOperation as exc:
                raise ValidationError("canonical q/e is not a finite decimal") from exc
            if not (q.is_finite() and e.is_finite() and ZERO <= q <= ONE and ZERO <= e <= ONE):
                raise ValidationError("canonical q/e is outside [0,1]")
        parsed.append((process_id, q, e))
    if role == "canonical_g2_abc":
        if [entry[0] for entry in parsed] != ["A", "B", "C"]:
            raise ValidationError("canonical_g2_abc must contain A,B,C in that exact order")
        for item, (process_id, _, _) in zip(items, parsed):
            ref = item.get("canonical_parameter_ref")
            if ref is None or (ref["q_parameter_id"], ref["e_parameter_id"]) != BINDINGS[process_id]:
                raise ValidationError("canonical item has a forbidden parameter binding")
    elif any("canonical_parameter_ref" in item for item in items):
        raise ValidationError("canonical_parameter_ref is only allowed for canonical_g2_abc")
    return request_id, role, semantics, parsed


def calibrate(request: Any, parameters_path: Path) -> dict[str, Any]:
    parameters = _read_parameters(parameters_path)
    request_id, role, semantics, items = _parse_request(request, parameters)
    solver = solve_single if semantics == SINGLE else solve_chain
    results = [solver(process_id, q, e) for process_id, q, e in items]
    statuses = {result["status"] for result in results}
    overall = "HAS_INFEASIBLE" if "INFEASIBLE" in statuses else ("HAS_NONIDENTIFIABLE" if "NONIDENTIFIABLE_FAMILY" in statuses else "ALL_IDENTIFIED")
    return {"schema_version": SCHEMA_VERSION, "envelope_type": "calibration_response", "request_id": request_id,
            "scenario_role": role, "semantics": semantics, "overall_status": overall, "results": results}


def _load_request(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle, parse_float=Decimal)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load request JSON: {exc}") from exc


def _write_response(path: Path, response: dict[str, Any]) -> None:
    try:
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(response, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
    except (OSError, TypeError, ValueError) as exc:
        raise OSError(f"cannot serialize response: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--parameters", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args(argv)
    try:
        response = calibrate(_load_request(Path(arguments.request)), Path(arguments.parameters))
    except ValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2
    except (NumericalError, InvalidOperation, ArithmeticError) as exc:
        print(f"numerical failure: {exc}", file=sys.stderr)
        return 3
    try:
        _write_response(Path(arguments.output), response)
    except OSError as exc:
        print(f"I/O failure: {exc}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
