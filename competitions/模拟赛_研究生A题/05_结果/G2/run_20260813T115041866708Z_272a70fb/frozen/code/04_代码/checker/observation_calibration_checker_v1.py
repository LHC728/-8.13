"""Independent E2 checker for the frozen G2-01 calibration contract.

This module intentionally has no dependency on the E1 implementation.  In
particular, standard_chain_v1 is checked by a nested alpha/beta bisection over
the original equations, never by the E1 t/h reduction.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, localcontext
from fractions import Fraction
from pathlib import Path

ZERO, ONE, TWO = Decimal(0), Decimal(1), Decimal(2)
WIDTH = Decimal("1e-14")
RES_TOL = Decimal("2e-12")
CROSS_TOL = Decimal("5e-11")
EMAX_TOL = Decimal("5e-12")
DECIMAL_RE = re.compile(r"^(0(?:\.[0-9]+)?|1(?:\.0+)?)$")
NONNEGATIVE_RE = re.compile(r"^(0|[1-9][0-9]*)(?:\.[0-9]+)?$")
RUN_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{12}Z_[0-9a-f]{8}$")
SPAN_TOL = Decimal("1e-12")


class ValidationError(Exception):
    pass


class NumericalError(Exception):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dec(value, name: str) -> Decimal:
    if not isinstance(value, str) or not DECIMAL_RE.fullmatch(value):
        raise ValidationError(f"{name} must be a canonical decimal probability string")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError(f"invalid decimal for {name}") from exc


def _nonnegative_dec(value, name: str) -> Decimal:
    if not isinstance(value, str) or not NONNEGATIVE_RE.fullmatch(value):
        raise ValidationError(f"{name} must be a canonical nonnegative decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError(f"invalid decimal for {name}") from exc
    if not parsed.is_finite():
        raise ValidationError(f"{name} must be finite")
    return parsed


def _number(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value, ".17g")
    # Preserve the 17-digit rounding when expanding exponent notation to the
    # schema's required ordinary-decimal spelling.
    if "E" in text or "e" in text:
        text = format(Decimal(text), "f")
    return "0" if text in ("-0", "") else text


def _certificate_number(value: Decimal) -> str:
    """Certificates retain their working-precision endpoints, unlike API values."""
    if value == ZERO:
        return "0"
    return format(value, "f").rstrip("0").rstrip(".")


def _significant_digits(value: Decimal) -> int:
    text = format(value, "f").lstrip("-").replace(".", "")
    stripped = text.lstrip("0")
    return len(stripped) if stripped else 1


def _p0(q: Decimal, e: Decimal) -> int:
    return max(120, max(_significant_digits(q), _significant_digits(e)) + 80)


def _fraction(value: Decimal) -> Fraction:
    sign, digits, exponent = value.as_tuple()
    numerator = int("".join(str(digit) for digit in digits) or "0")
    if sign:
        numerator = -numerator
    if exponent >= 0:
        return Fraction(numerator * (10 ** exponent), 1)
    return Fraction(numerator, 10 ** (-exponent))


def _outward_pair(lo: Decimal, hi: Decimal) -> tuple[Decimal, Decimal]:
    """Expose a Decimal interval with explicitly outward-directed endpoints."""
    with localcontext() as ctx:
        ctx.rounding = ROUND_FLOOR
        left = +lo
        ctx.rounding = ROUND_CEILING
        right = +hi
    return left, right


def _codomain_interval(lo: Decimal, hi: Decimal) -> tuple[Decimal, Decimal]:
    """Intersect a completed numerical enclosure with the proven [0,1] range."""
    lo, hi = max(lo, ZERO), min(hi, ONE)
    if lo > hi:
        raise NumericalError("parameter enclosure has empty intersection with codomain [0,1]")
    return lo, hi


def _residuals(q: Decimal, e: Decimal, alpha: Decimal, beta: Decimal, semantics: str):
    if semantics == "single_test_unconditional_v1":
        left = (ONE-q)*alpha
        right = q*beta
        x = abs(left-e/TWO)
        y = abs(right-e/TWO)
        return x, y, abs(left-right)
    d = ONE+(ONE-q)*alpha+q*(ONE-beta)
    a = (ONE-q)*(alpha+alpha*alpha)
    b = q*(TWO*beta-beta*beta)
    target = e*d/TWO
    return abs(a-target), abs(b-target), abs(a-b)


def _chain_beta(q: Decimal, alpha: Decimal, span: Decimal = WIDTH):
    """Nested inner bisection on q(2 beta-beta^2)=(1-q)(alpha+alpha^2)."""
    target = (ONE-q)*(alpha+alpha*alpha)
    lo, hi = ZERO, ONE
    if target < ZERO or target > q:
        raise NumericalError("inner beta target lies outside its original-equation range")
    for _ in range(300):
        mid = (lo+hi)/TWO
        value = q*(TWO*mid-mid*mid)
        if value < target:
            lo = mid
        else:
            hi = mid
        if hi-lo <= span:
            lo, hi = _outward_pair(lo, hi)
            lo, hi = _codomain_interval(lo, hi)
            return (lo+hi)/TWO, lo, hi
    raise NumericalError("inner beta bisection exceeded 300 iterations")


def _chain_alpha_hi(q: Decimal) -> Decimal:
    r = ONE-q
    if TWO*r <= q:
        return ONE
    lo, hi = ZERO, ONE
    # This is an endpoint calculation, not the prescribed root stopping rule.
    # Keep all 300 independent bisection steps so its rounding error cannot
    # affect the required near-boundary classification.
    for _ in range(300):
        mid = (lo+hi)/TWO
        if r*(mid+mid*mid) < q:
            lo = mid
        else:
            hi = mid
    # lo is the feasible side: retaining it ensures the subsequent mandated
    # beta solve has a target no larger than q despite finite Decimal rounding.
    return lo


def _refine_monotone_root(lo: Decimal, hi: Decimal, target: Decimal, fn) -> tuple[Decimal, Decimal]:
    """One precision layer of at most 300 bisections, retaining both sides."""
    if fn(lo) > target or fn(hi) < target:
        raise NumericalError("endpoint refinement bracket is invalid")
    for _ in range(300):
        mid = (lo+hi)/TWO
        if fn(mid) < target:
            lo = mid
        else:
            hi = mid
    return _codomain_interval(*_outward_pair(lo, hi))


def _emax_interval(q: Decimal, precision: int, endpoint_state):
    """Directed original-equation e_max enclosure, wholly inside one context."""
    with localcontext() as ctx:
        ctx.prec = precision
        if TWO*(ONE-q) <= q:
            alpha_lo = alpha_hi = ONE
            beta_lo, beta_hi = endpoint_state if endpoint_state is not None else (ZERO, ONE)
            target = TWO*(ONE-q)
            beta_lo, beta_hi = _refine_monotone_root(
                beta_lo, beta_hi, target, lambda beta: q*(TWO*beta-beta*beta)
            )
            state = (beta_lo, beta_hi)
        else:
            beta_lo = beta_hi = ONE
            alpha_lo, alpha_hi = endpoint_state if endpoint_state is not None else (ZERO, ONE)
            target = q
            alpha_lo, alpha_hi = _refine_monotone_root(
                alpha_lo, alpha_hi, target,
                lambda alpha: (ONE-q)*(alpha+alpha*alpha),
            )
            state = (alpha_lo, alpha_hi)

        # e_max is increasing in both endpoint alpha and beta.  Lower uses a
        # downward numerator and upward denominator; upper reverses them.
        with localcontext(ctx) as down:
            down.rounding = ROUND_FLOOR
            numerator_lo = TWO*(ONE-q)*(alpha_lo+alpha_lo*alpha_lo)
            denominator_lo = ONE+(ONE-q)*alpha_hi+q*(ONE-beta_lo)
            lower = numerator_lo/denominator_lo
            lower = lower.next_minus()
        with localcontext(ctx) as up:
            up.rounding = ROUND_CEILING
            numerator_hi = TWO*(ONE-q)*(alpha_hi+alpha_hi*alpha_hi)
            denominator_hi = ONE+(ONE-q)*alpha_lo+q*(ONE-beta_hi)
            upper = numerator_hi/denominator_hi
            upper = upper.next_plus()
        if lower > upper:
            raise NumericalError("directed e_max enclosure inverted")
        return lower, upper, state, (alpha_lo, alpha_hi, beta_lo, beta_hi)


def _certificate(alpha_lo: Decimal, alpha_hi: Decimal, beta_lo: Decimal, beta_hi: Decimal,
                 alpha_reported: Decimal, beta_reported: Decimal) -> dict[str, Decimal]:
    """The frozen twelve-field root/report convex-hull certificate."""
    root_alpha_lo, root_alpha_hi = _outward_pair(alpha_lo, alpha_hi)
    root_beta_lo, root_beta_hi = _outward_pair(beta_lo, beta_hi)
    root_alpha_lo, root_alpha_hi = _codomain_interval(root_alpha_lo, root_alpha_hi)
    root_beta_lo, root_beta_hi = _codomain_interval(root_beta_lo, root_beta_hi)
    reported_alpha_lo, reported_alpha_hi = min(root_alpha_lo, alpha_reported), max(root_alpha_hi, alpha_reported)
    reported_beta_lo, reported_beta_hi = min(root_beta_lo, beta_reported), max(root_beta_hi, beta_reported)
    return {
        "root_alpha_lo": root_alpha_lo, "root_alpha_hi": root_alpha_hi,
        "root_alpha_span": root_alpha_hi-root_alpha_lo,
        "root_beta_lo": root_beta_lo, "root_beta_hi": root_beta_hi,
        "root_beta_span": root_beta_hi-root_beta_lo,
        "reported_alpha_lo": reported_alpha_lo, "reported_alpha_hi": reported_alpha_hi,
        "reported_alpha_span": reported_alpha_hi-reported_alpha_lo,
        "reported_beta_lo": reported_beta_lo, "reported_beta_hi": reported_beta_hi,
        "reported_beta_span": reported_beta_hi-reported_beta_lo,
    }


def _beta_envelope(q: Decimal, alpha_lo: Decimal, alpha_hi: Decimal) -> tuple[Decimal, Decimal]:
    """Propagate the whole monotone alpha root enclosure through inner solve."""
    _, beta_lo, _ = _chain_beta(q, alpha_lo)
    endpoint = _chain_alpha_hi(q)
    # Intersect the numerical alpha enclosure with its independently proved
    # feasibility-domain endpoint before applying beta(alpha).  This is an
    # interval-domain intersection, not projection of a candidate solution.
    alpha_hi = min(alpha_hi, endpoint)
    if alpha_lo > alpha_hi:
        raise NumericalError("alpha root enclosure misses beta mapping domain")
    _, _, beta_hi = _chain_beta(q, alpha_hi)
    return _codomain_interval(beta_lo, beta_hi)


CERT_KEYS = tuple((
    "root_alpha_lo", "root_alpha_hi", "root_alpha_span",
    "root_beta_lo", "root_beta_hi", "root_beta_span",
    "reported_alpha_lo", "reported_alpha_hi", "reported_alpha_span",
    "reported_beta_lo", "reported_beta_hi", "reported_beta_span",
))


def _chain_solve(q: Decimal, e: Decimal):
    """Independent two-dimensional original-equation back substitution."""
    if q == ZERO:
        return ("NONIDENTIFIABLE_FAMILY" if e == ZERO else "INFEASIBLE", ZERO if e == ZERO else None, None, ZERO, ["beta"] if e == ZERO else [], {})
    if q == ONE:
        return ("NONIDENTIFIABLE_FAMILY" if e == ZERO else "INFEASIBLE", None, ZERO if e == ZERO else None, ZERO, ["alpha"] if e == ZERO else [], {})
    p0 = _p0(q, e)
    selected_precision = None
    emax = None
    endpoint_state = None
    endpoint_interval = None
    for precision in range(p0, p0 + 801, 80):
        lower, upper, endpoint_state, endpoint_interval = _emax_interval(q, precision, endpoint_state)
        if e < lower:
            selected_precision, emax = precision, (lower+upper)/TWO
            break
        if e > upper:
            return "INFEASIBLE", None, None, (lower+upper)/TWO, [], {}
    if selected_precision is None:
        raise NumericalError("e_max classification remained unstable through p0+800")
    with localcontext() as ctx:
        ctx.prec = selected_precision
        alpha_ep_lo, alpha_ep_hi, beta_ep_lo, beta_ep_hi = endpoint_interval
        hi = (alpha_ep_lo+alpha_ep_hi)/TWO
        # Regardless of which alpha endpoint branch applied, recover beta via
        # the prescribed inner original-equation bisection.  For q < 2/3 this
        # naturally approaches beta=1; for q > 2/3 it is strictly below one.
        beta_hi = (beta_ep_lo+beta_ep_hi)/TWO
        a_hi = (ONE-q)*(hi+hi*hi)
        d_hi = ONE+(ONE-q)*hi+q*(ONE-beta_hi)
        emax = TWO*a_hi/d_hi
        if e == ZERO:
            return "UNIQUE_SOLUTION", ZERO, ZERO, emax, [], _certificate(ZERO, ZERO, ZERO, ZERO, ZERO, ZERO)
        lo = ZERO
        for _ in range(300):
                alpha = (lo+hi)/TWO
                beta, _, _ = _chain_beta(q, alpha)
                a = (ONE-q)*(alpha+alpha*alpha)
                d = ONE+(ONE-q)*alpha+q*(ONE-beta)
                r = TWO*a-e*d
                if r < ZERO:
                    lo = alpha
                else:
                    hi = alpha
                if hi-lo <= SPAN_TOL and hi-lo <= WIDTH:
                    alpha_lo, alpha_hi = _outward_pair(lo, hi)
                    alpha = (alpha_lo+alpha_hi)/TWO
                    beta, _, _ = _chain_beta(q, alpha)
                    # beta is monotone in alpha: root certificate must map the
                    # entire outer enclosure, not merely the alpha midpoint.
                    beta_lo, beta_hi = _beta_envelope(q, alpha_lo, alpha_hi)
                    # Contract requires 17-digit serialized values to be re-read.
                    alpha_rt, beta_rt = Decimal(_number(alpha)), Decimal(_number(beta))
                    errs = _residuals(q, e, alpha_rt, beta_rt, "standard_chain_v1")
                    certificate = _certificate(alpha_lo, alpha_hi, beta_lo, beta_hi, alpha_rt, beta_rt)
                    if (max(errs) <= Decimal("5e-12") and
                            certificate["root_alpha_span"] <= SPAN_TOL and certificate["root_beta_span"] <= SPAN_TOL and
                            certificate["reported_alpha_span"] <= SPAN_TOL and certificate["reported_beta_span"] <= SPAN_TOL):
                        return "UNIQUE_SOLUTION", alpha_rt, beta_rt, emax, [], certificate
                    # Near beta=1, the monotone inner mapping can magnify an
                    # alpha enclosure. Continue shrinking the outer bracket;
                    # the 300-iteration cap remains the numerical-failure
                    # boundary rather than treating a partial certificate as
                    # a solution.
                    continue
        raise NumericalError("outer alpha bisection exceeded 300 iterations")


def _single_solve(q: Decimal, e: Decimal):
    with localcontext() as ctx:
        ctx.prec = _p0(q, e)
        if q == ZERO:
            return ("NONIDENTIFIABLE_FAMILY" if e == ZERO else "INFEASIBLE", ZERO if e == ZERO else None, None, ZERO, ["beta"] if e == ZERO else [], {})
        if q == ONE:
            return ("NONIDENTIFIABLE_FAMILY" if e == ZERO else "INFEASIBLE", None, ZERO if e == ZERO else None, ZERO, ["alpha"] if e == ZERO else [], {})
        emax = TWO*min(q, ONE-q)
        if e > emax:
            return "INFEASIBLE", None, None, emax, [], {}
        alpha_denominator, beta_denominator = TWO*(ONE-q), TWO*q
        with localcontext(ctx) as down:
            down.rounding = ROUND_FLOOR
            alpha_lo = (e/alpha_denominator).next_minus()
            beta_lo = (e/beta_denominator).next_minus()
        with localcontext(ctx) as up:
            up.rounding = ROUND_CEILING
            alpha_hi = (e/alpha_denominator).next_plus()
            beta_hi = (e/beta_denominator).next_plus()
        alpha_lo, alpha_hi = _codomain_interval(alpha_lo, alpha_hi)
        beta_lo, beta_hi = _codomain_interval(beta_lo, beta_hi)
        alpha, beta = (alpha_lo+alpha_hi)/TWO, (beta_lo+beta_hi)/TWO
        alpha_public, beta_public = Decimal(_number(alpha)), Decimal(_number(beta))
        certificate = _certificate(alpha_lo, alpha_hi, beta_lo, beta_hi, alpha_public, beta_public)
        return "UNIQUE_SOLUTION", alpha, beta, emax, [], certificate


def _parameters(path: Path):
    found = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = row.get("parameter_id")
            if key in {"P026", "P027", "P028", "P030", "P031", "P032"}:
                if key in found:
                    raise ValidationError(f"duplicate parameter_id {key}")
                found[key] = _dec(row.get("value"), f"parameters[{key}].value")
    if len(found) != 6:
        raise ValidationError("canonical parameter ids P026-P028/P030-P032 are required exactly once")
    return found


def _validate_envelope(response):
    if not isinstance(response, dict) or set(response) - {"schema_version","envelope_type","request_id","scenario_role","semantics","overall_status","results","errors"}:
        raise ValidationError("response envelope has an invalid top-level shape")
    for key in ("schema_version","envelope_type","request_id","scenario_role","semantics","overall_status","results"):
        if key not in response:
            raise ValidationError(f"response missing {key}")
    if response["schema_version"] != "observation_calibration_v1" or response["envelope_type"] != "calibration_response":
        raise ValidationError("wrong response envelope identity")
    if response["scenario_role"] not in ("canonical_g2_abc","generic","test_oracle") or response["semantics"] not in ("single_test_unconditional_v1","standard_chain_v1"):
        raise ValidationError("invalid role or semantics")
    if not isinstance(response["results"], list) or not response["results"]:
        raise ValidationError("results must be a nonempty list")


def _check_item(item, semantics, role, params):
    required = {"process_id","status","q","e","alpha","beta","e_max","free_parameters","diagnostics"}
    if not isinstance(item, dict) or set(item) != required:
        raise ValidationError("result item does not match schema fields")
    q, e = _dec(item["q"], "result.q"), _dec(item["e"], "result.e")
    pid = item["process_id"]
    if not isinstance(pid, str) or not pid:
        raise ValidationError("invalid process_id")
    if role == "canonical_g2_abc":
        binding = {"A": ("P026","P030"), "B": ("P027","P031"), "C": ("P028","P032")}
        if pid not in binding:
            raise ValidationError("canonical results must be A/B/C")
        pq, pe = binding[pid]
        if (q, e) != (params[pq], params[pe]):
            raise ValidationError(f"canonical {pid} q/e do not bind to {pq}/{pe}")
    expected = _single_solve(q,e) if semantics == "single_test_unconditional_v1" else _chain_solve(q,e)
    want, ia, ib, ie_max, free, certificate = expected
    errors = []
    if item["status"] != want: errors.append(f"status expected {want}")
    if item["free_parameters"] != free: errors.append("free_parameters mismatch")
    for name, got, expected_value, tol in (("alpha",item["alpha"],ia,CROSS_TOL),("beta",item["beta"],ib,CROSS_TOL),("e_max",item["e_max"],ie_max,EMAX_TOL)):
        if expected_value is None:
            if got is not None: errors.append(f"{name} must be null")
        else:
            try: value = _dec(got, name)
            except ValidationError: errors.append(f"{name} invalid"); continue
            if abs(value-expected_value) > tol: errors.append(f"{name} differs from independent result")
    max_res = None
    ga = gb = None
    if ia is not None and ib is not None:
        with localcontext() as ctx:
            ctx.prec = _p0(q, e)
            independent_residuals = _residuals(q,e,ia,ib,semantics)
        max_res = max(independent_residuals)
        if max_res > RES_TOL: errors.append("independent original residual exceeds tolerance")
        # independently ensure the reported solution itself satisfies the raw equations
        try:
            ga, gb = _dec(item["alpha"],"alpha"), _dec(item["beta"],"beta")
            with localcontext() as ctx:
                ctx.prec = _p0(q, e)
                public_residuals = _residuals(q,e,ga,gb,semantics)
            if max(public_residuals) > Decimal("5e-12"):
                errors.append("reported original residual exceeds round-trip tolerance")
            diagnostics = item.get("diagnostics")
            supplied_residuals = diagnostics.get("residuals") if isinstance(diagnostics, dict) else None
            if not isinstance(supplied_residuals, dict) or set(supplied_residuals) != {"equation_1_abs", "equation_2_abs", "balance_abs"}:
                errors.append("diagnostics.residuals shape is invalid")
            else:
                for key, actual in zip(("equation_1_abs", "equation_2_abs", "balance_abs"), public_residuals):
                    try:
                        supplied = _nonnegative_dec(supplied_residuals[key], f"diagnostics.residuals.{key}")
                        if supplied != Decimal(_number(actual)):
                            errors.append(f"diagnostics.residuals.{key} does not equal public-value residual")
                    except ValidationError:
                        errors.append(f"diagnostics.residuals.{key} is invalid")
        except ValidationError: pass
    if want == "UNIQUE_SOLUTION":
        diagnostics = item.get("diagnostics")
        notes = diagnostics.get("notes") if isinstance(diagnostics, dict) else None
        if not isinstance(notes, list):
            errors.append("diagnostics.notes missing bracket certificate")
        else:
            pairs = [x.split("=", 1) for x in notes if isinstance(x, str) and "=" in x]
            supplied = dict(pairs)
            if any(sum(1 for key, _ in pairs if key == required_key) != 1 for required_key in CERT_KEYS):
                errors.append("each of the twelve bracket certificate fields must occur exactly once")
            try:
                with localcontext() as ctx:
                    ctx.prec = max(120, max(len(supplied[key].replace(".", "")) for key in CERT_KEYS) + 10)
                    parsed = {key: _dec(supplied[key], key) for key in CERT_KEYS}
                    for prefix in ("root_alpha", "root_beta", "reported_alpha", "reported_beta"):
                        if (parsed[prefix+"_hi"] < parsed[prefix+"_lo"] or
                                parsed[prefix+"_span"] != parsed[prefix+"_hi"]-parsed[prefix+"_lo"] or
                                parsed[prefix+"_span"] > SPAN_TOL):
                            errors.append(f"{prefix} certificate span is invalid")
                    ga, gb = _dec(item["alpha"], "alpha"), _dec(item["beta"], "beta")
                    if not (parsed["reported_alpha_lo"] <= ga <= parsed["reported_alpha_hi"] and parsed["reported_beta_lo"] <= gb <= parsed["reported_beta_hi"]):
                        errors.append("reported public values are outside reported certificate hull")
                    if not (parsed["reported_alpha_lo"] <= parsed["root_alpha_lo"] <= parsed["root_alpha_hi"] <= parsed["reported_alpha_hi"] and parsed["reported_beta_lo"] <= parsed["root_beta_lo"] <= parsed["root_beta_hi"] <= parsed["reported_beta_hi"]):
                        errors.append("reported certificate does not contain root certificate")
                    for parameter, public in (("alpha", ga), ("beta", gb)):
                        rlo, rhi = parsed[f"root_{parameter}_lo"], parsed[f"root_{parameter}_hi"]
                        expected_lo, expected_hi = min(rlo, public), max(rhi, public)
                        if parsed[f"reported_{parameter}_lo"] != expected_lo or parsed[f"reported_{parameter}_hi"] != expected_hi:
                            errors.append(f"reported_{parameter} certificate is not the minimal root/public hull")
                    if semantics == "single_test_unconditional_v1":
                        exact_q, exact_e = _fraction(q), _fraction(e)
                        exact_alpha = exact_e / (2 * (1-exact_q))
                        exact_beta = exact_e / (2 * exact_q)
                        if not (_fraction(parsed["root_alpha_lo"]) <= exact_alpha <= _fraction(parsed["root_alpha_hi"]) and
                                _fraction(parsed["root_beta_lo"]) <= exact_beta <= _fraction(parsed["root_beta_hi"])):
                            errors.append("single closed-form roots are outside supplied root certificate")
                    else:
                        if (max(parsed["root_alpha_lo"], certificate["root_alpha_lo"]) >
                                min(parsed["root_alpha_hi"], certificate["root_alpha_hi"])):
                            errors.append("chain alpha root certificates do not intersect")
                        if (max(parsed["root_beta_lo"], certificate["root_beta_lo"]) >
                                min(parsed["root_beta_hi"], certificate["root_beta_hi"])):
                            errors.append("chain beta root certificates do not intersect")
            except (KeyError, ValidationError):
                errors.append("bracket certificate fields are invalid")
    return {"process_id": pid, "status": "FAIL" if errors else "PASS", "independent_alpha": None if ia is None else _number(ia), "independent_beta": None if ib is None else _number(ib), "max_original_residual": None if max_res is None else _number(max_res), "message": "; ".join(errors) if errors else "independent back-substitution and binding passed"}


def _report_context(response_path: Path):
    """Top-level-only preflight; callers must not write a report on failure."""
    raw = json.loads(response_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationError("response top level is not an object")
    role, request_id, semantics = raw.get("scenario_role"), raw.get("request_id"), raw.get("semantics")
    if role != "canonical_g2_abc":
        raise ValidationError("report-context requires canonical_g2_abc")
    if not isinstance(request_id, str) or not isinstance(semantics, str) or ":" not in request_id:
        raise ValidationError("report-context request_id is malformed")
    run_id, suffix = request_id.rsplit(":", 1)
    if suffix != semantics or not RUN_ID_RE.fullmatch(run_id):
        raise ValidationError("report-context request_id suffix or parent run_id is invalid")
    return run_id


def check(response_path: Path, parameters_path: Path, schema_path: Path, package_path: Path, run_id: str):
    hashes = {"response_sha256": _sha(response_path), "parameters_sha256": _sha(parameters_path), "schema_sha256": _sha(schema_path), "task_package_sha256": _sha(package_path)}
    base = {"schema_version":"observation_calibration_v1", "envelope_type":"calibration_check_report", "run_id":run_id, "registry_version":"CR-V3.1", "check_ids":["CR-V3.1/C01","CR-V3.1/C02","CR-V3.1/C19","CR-V3.1/C21"], **hashes, "checked_result_count":0, "items":[], "errors":[]}
    try:
        # Parsing the frozen package is deliberately bounded: required identity and frozen hashes.
        package_text = package_path.read_text(encoding="utf-8")
        if "task_package_version: \"G2-01-SPEC-V1.1.7\"" not in package_text or "E2_embedded_oracles:" not in package_text:
            raise ValidationError("unrecognized frozen task package")
        if hashes["parameters_sha256"] != "0461da2e0de09090673192d9eb0fde6fe5e70b1d22ef61fe13cdb878c449f07e":
            raise ValidationError("parameters hash does not match the frozen task package")
        if hashes["schema_sha256"] != "8d067fa2ed387417fa7871164175d02443aa57b24b537085806a41c164628686":
            raise ValidationError("schema hash does not match the frozen task package")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("$id") != "observation_calibration_v1.schema.json":
            raise ValidationError("unrecognized schema")
        response = json.loads(response_path.read_text(encoding="utf-8"), parse_float=Decimal)
        _validate_envelope(response)
        params = _parameters(parameters_path)
        base["scenario_role"], base["semantics"] = response["scenario_role"], response["semantics"]
        pids = [x.get("process_id") if isinstance(x,dict) else None for x in response["results"]]
        if len(set(pids)) != len(pids): raise ValidationError("duplicate process_id")
        if response["scenario_role"] == "canonical_g2_abc" and pids != ["A","B","C"]: raise ValidationError("canonical order must be A,B,C")
        for item in response["results"]:
            base["items"].append(_check_item(item, response["semantics"], response["scenario_role"], params))
        base["checked_result_count"] = len(base["items"])
        result_statuses = [x["status"] for x in response["results"]]
        expected_overall = ("HAS_INFEASIBLE" if "INFEASIBLE" in result_statuses else
                            "HAS_NONIDENTIFIABLE" if "NONIDENTIFIABLE_FAMILY" in result_statuses else
                            "ALL_IDENTIFIED")
        if response["overall_status"] != expected_overall:
            base["items"].append({"process_id":"overall_status", "status":"FAIL", "independent_alpha":None,
                                  "independent_beta":None, "max_original_residual":None,
                                  "message":f"overall_status expected {expected_overall}"})
        base["checker_status"] = "PASS" if all(x["status"] == "PASS" for x in base["items"]) else "FAIL"
        return base, 0 if base["checker_status"] == "PASS" else 1
    except ValidationError as exc:
        base.update({"scenario_role":"generic", "semantics":"single_test_unconditional_v1", "checker_status":"VALIDATION_ERROR", "errors":[str(exc)]})
        return base, 2
    except (NumericalError, InvalidOperation) as exc:
        base.update({"scenario_role":"generic", "semantics":"standard_chain_v1", "checker_status":"NUMERICAL_ERROR", "errors":[str(exc)]})
        return base, 3


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", required=True); parser.add_argument("--parameters", required=True)
    parser.add_argument("--schema", required=True); parser.add_argument("--task-package", required=True); parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    try:
        try:
            run_id = _report_context(Path(args.response))
        except (ValidationError, json.JSONDecodeError, OSError) as exc:
            print(f"report-context preflight failed: {exc}", file=sys.stderr)
            return 2
        report, code = check(Path(args.response), Path(args.parameters), Path(args.schema), Path(args.task_package), run_id)
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        return code
    except (OSError, json.JSONDecodeError) as exc:
        print(f"I/O or serialization failure: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
