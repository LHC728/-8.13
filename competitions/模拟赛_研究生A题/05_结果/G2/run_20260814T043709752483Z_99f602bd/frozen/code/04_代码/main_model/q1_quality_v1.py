"""G2-02 E1 Q1 probability/quality chain orchestrator (Python standard library only).

Implements the frozen G2-02-SPEC-V1.0.3 Q1 chain: stage_0 upstream A/B/C kernels
(canonical bound_frozen or derive_from_values), stage_1 closed-form q_E, stage_2 E
kernel calibration (reusing the accepted observation_calibration_v1 solver), stage_3
E rates, stage_4 final fourfold with E[S]/E[PL]/E[PW], stage_5 lambda (event-level
main table + tilde) and multinomial, all cross-checked across three independent routes
(closed form / 16-state enumeration / absorption chain).

Exact frozen CLI:
  python 04_代码/main_model/q1_quality_v1.py --request <request.json>
      --parameters <parameters.csv> --upstream <upstream_response.json>
      --schema <schema.json> --output <response.json>
Exit codes:
  0  request valid and completed (including HAS_INFEASIBLE / HAS_INDETERMINATE)
  2  input envelope / binding / hash / parameter-CSV validation failure (no partial
     response written)
  3  numerical failure or three-route comparison out of tolerance (full valid
     response written first)
  4  file I/O or unrecoverable serialization failure

Only this orchestrator holds shared input parsing, schema validation, Decimal
utilities and serialization.  The three route files never import each other and never
share core summation/transition/feasibility functions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

from q1_routes import absorption_chain_v1, closed_form_v1, enumeration_v1

try:
    import observation_calibration_v1 as _calibrator
except ImportError:  # pragma: no cover - surfaced at CLI as I/O failure
    _calibrator = None

SCHEMA_VERSION = "q1_quality_v1"
SINGLE = "single_test_unconditional_v1"
CHAIN = "standard_chain_v1"
PROCESSES = ("A", "B", "C")
ROUTE_NAMES = ("closed_form", "enumeration", "absorption_chain")
ROUTE_MODULES = {
    "closed_form": closed_form_v1,
    "enumeration": enumeration_v1,
    "absorption_chain": absorption_chain_v1,
}

FROZEN_UPSTREAM_SHA256 = {
    SINGLE: "355af00ce77791208af17303912ed5972619ad89116f3d0d05f46494d534d0ea",
    CHAIN: "e71473ce391da82d7711ceff872b031ec307aa6d8e524f3ff1cd5c5a440542fd",
}
# G2-02-SPEC-V1.0.3 frozen bindings (task package frozen_sha256).
FROZEN_SCHEMA_SHA256 = "0bb93b122572b85833c539bc6f2bee273e04a6c0984933aafa5ed6d3e66dec4d"
FROZEN_FIXTURE_SHA256 = "13efa773aaa2b057be33d2c511e4bc4be078a6817d47e2dc09aad9da2db5fb0f"
CROSS_ROUTE_TOLERANCE = Decimal("1e-15")
CONSERVATION_TOLERANCE = Decimal("1e-15")
ZERO = Decimal(0)
ONE = Decimal(1)
HUNDRED = Decimal(100)
DECIMAL_PROBABILITY = re.compile(r"^(?:0(?:\.[0-9]+)?|1(?:\.0+)?)$")
# Every legal lexical zero form of the frozen decimalProbability grammar
# (regex-equivalent to ^0(?:\.0+)?$): "0", "0.0", "0.00", "0.000000", ...
Q_E_ZERO_TEXT = re.compile(r"^0(?:\.0+)?$")


class ValidationError(Exception):
    """Input envelope / binding / hash / parameter-CSV validation failure (exit 2)."""


class NumericalError(Exception):
    """Numerical failure (exit 3, full response written)."""


class ResponseValidationError(Exception):
    """Internal invariant: the generated response does not satisfy the frozen schema."""


# --------------------------------------------------------------------------- #
# Decimal utilities (shared infrastructure, no core math)
# --------------------------------------------------------------------------- #

def _plain(value: Decimal, significant: int = 17) -> str:
    """Serialize a finite Decimal as a plain decimal string with `significant`
    significant digits; negative zero is normalized to 0."""
    if not value.is_finite():
        raise NumericalError("non-finite Decimal during serialization")
    if value == ZERO:
        return "0"
    adjustment = value.copy_abs().adjusted()
    quantum = Decimal(1).scaleb(adjustment - significant + 1)
    value = value.quantize(quantum)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def _significant_digits(value: Decimal) -> int:
    """Frozen lexical significant-digit rule (leading zeros stripped)."""
    digits = "".join(str(digit) for digit in value.as_tuple().digits)
    stripped = digits.lstrip("0")
    return len(stripped) if stripped else 1


def _decimal_probability_string(value: str, label: str) -> Decimal:
    if not isinstance(value, str) or not DECIMAL_PROBABILITY.fullmatch(value):
        raise ValidationError(f"{label} must be a canonical decimal probability string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError(f"{label} is not a finite decimal") from exc
    if not number.is_finite() or number < ZERO or number > ONE:
        raise ValidationError(f"{label} is outside [0,1]")
    return number


def _working_precision(inputs: list[str]) -> int:
    """p0 = max(120, max_input_significant_digits + 80)."""
    digits = [_significant_digits(Decimal(value)) for value in inputs]
    return max(120, max(digits) + 80)


def _dsum(values: list[Decimal], precision: int) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = precision
        total = ZERO
        for value in values:
            total += value
        return total


# --------------------------------------------------------------------------- #
# Minimal JSON-Schema (2020-12 subset) validator for the frozen envelopes
# --------------------------------------------------------------------------- #

def _schema_validate(subschema: dict[str, Any], value: Any, path: str, root: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if "$ref" in subschema:
        ref = subschema["$ref"]
        if not ref.startswith("#/$defs/"):
            errors.append(f"{path}: unsupported $ref {ref}")
            return errors
        errors.extend(_schema_validate(root["$defs"][ref[len("#/$defs/"):]], value, path, root))
        return errors
    if "type" in subschema:
        expected = subschema["type"]
        kinds = expected if isinstance(expected, list) else [expected]
        type_ok = any({
            "string": isinstance(value, str),
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "null": value is None,
        }.get(kind, False) for kind in kinds)
        if not type_ok:
            errors.append(f"{path}: expected type {expected}")
    if "const" in subschema and value != subschema["const"]:
        errors.append(f"{path}: value must be {subschema['const']!r}")
    if "enum" in subschema and value not in subschema["enum"]:
        errors.append(f"{path}: value not in enum {subschema['enum']}")
    if isinstance(value, str) and "pattern" in subschema and re.fullmatch(subschema["pattern"], value) is None:
        errors.append(f"{path}: pattern mismatch")
    if isinstance(value, (int, float)) and "minimum" in subschema and not isinstance(value, bool) and value < subschema["minimum"]:
        errors.append(f"{path}: below minimum")
    if isinstance(value, dict):
        if "properties" in subschema:
            for key, sub in subschema["properties"].items():
                if key in value:
                    errors.extend(_schema_validate(sub, value[key], f"{path}.{key}", root))
        if subschema.get("additionalProperties") is False:
            extra = set(value) - set(subschema.get("properties", {}))
            if extra:
                errors.append(f"{path}: unexpected properties {sorted(extra)}")
        if "required" in subschema:
            for key in subschema["required"]:
                if key not in value:
                    errors.append(f"{path}: missing required {key}")
    if isinstance(value, list):
        if "items" in subschema:
            for index, item in enumerate(value):
                errors.extend(_schema_validate(subschema["items"], item, f"{path}[{index}]", root))
        if "minItems" in subschema and len(value) < subschema["minItems"]:
            errors.append(f"{path}: fewer than minItems")
        if "maxItems" in subschema and len(value) > subschema["maxItems"]:
            errors.append(f"{path}: more than maxItems")
        if subschema.get("uniqueItems") and len(set(value)) != len(value):
            errors.append(f"{path}: items not unique")
    if "oneOf" in subschema:
        matches = 0
        for sub in subschema["oneOf"]:
            if not _schema_validate(sub, value, path, root):
                matches += 1
        if matches != 1:
            errors.append(f"{path}: oneOf matched {matches} schemas")
    if "allOf" in subschema:
        for sub in subschema["allOf"]:
            errors.extend(_schema_validate(sub, value, path, root))
    if "if" in subschema:
        if not _schema_validate(subschema["if"], value, path, root):
            if "then" in subschema:
                errors.extend(_schema_validate(subschema["then"], value, path, root))
    return errors


def _validate_request(request: Any, schema_root: dict[str, Any]) -> None:
    errors = _schema_validate(schema_root["$defs"]["requestEnvelope"], request, "request", schema_root)
    if errors:
        raise ValidationError("request envelope invalid: " + "; ".join(errors[:8]))


def _validate_response(response: Any, schema_root: dict[str, Any]) -> None:
    """Validate the generated response envelope strictly against the frozen schema
    (the V1.0.3 schema admits nullable leaves, so the response validates directly,
    no placeholder schema view is needed) and enforce the NA/null consistency
    contract:
      - lambda.na=true  => lambda.main.A..D, lambda.sum, lambda.max_abs_deviation
                           and route_agreement.lambda_A..D are all null;
      - lambda.na=false => the same fields are all numeric decimal strings;
      - q_E is a mathematical zero (any legal lexical zero form of the
        decimalProbability grammar) => lambda.tilde.A..D and
        route_agreement.tilde_A..D are all null; otherwise they are numeric.
    """
    errors = _schema_validate(schema_root["$defs"]["responseEnvelope"], response, "response", schema_root)
    if errors:
        raise ResponseValidationError("generated response fails schema validation: " + "; ".join(errors[:8]))
    block = response.get("lambda")
    if not isinstance(block, dict):
        return
    na = block.get("na")
    main = block.get("main")
    if isinstance(main, dict):
        for key in ("A", "B", "C", "D"):
            main_value = main.get(key)
            if na and main_value is not None:
                raise ResponseValidationError(f"NA lambda main.{key} must be null")
            if na is False and main_value is None:
                raise ResponseValidationError(f"non-NA lambda main.{key} must be a value")
    if na:
        if block.get("sum") is not None:
            raise ResponseValidationError("NA lambda.sum must be null")
        if block.get("max_abs_deviation") is not None:
            raise ResponseValidationError("NA lambda.max_abs_deviation must be null")
    else:
        if not isinstance(block.get("sum"), str):
            raise ResponseValidationError("non-NA lambda.sum must be a numeric string")
        if not isinstance(block.get("max_abs_deviation"), str):
            raise ResponseValidationError("non-NA lambda.max_abs_deviation must be a numeric string")
    q_e_text = response.get("q_E")
    q_e_zero = isinstance(q_e_text, str) and Q_E_ZERO_TEXT.fullmatch(q_e_text) is not None
    tilde = block.get("tilde")
    if isinstance(tilde, dict):
        for key in ("A", "B", "C", "D"):
            tilde_value = tilde.get(key)
            if q_e_zero and tilde_value is not None:
                raise ResponseValidationError(f"q_E=0 lambda tilde.{key} must be null")
            if not q_e_zero and tilde_value is None:
                raise ResponseValidationError(f"q_E!=0 lambda tilde.{key} must be a value")
    agreement = response.get("route_agreement")
    if isinstance(agreement, dict):
        for key in ("lambda_A", "lambda_B", "lambda_C", "lambda_D"):
            agree_value = agreement.get(key)
            if na and agree_value is not None:
                raise ResponseValidationError(f"NA route_agreement.{key} must be null")
            if na is False and not isinstance(agree_value, str):
                raise ResponseValidationError(f"non-NA route_agreement.{key} must be a numeric string")
        for key in ("tilde_A", "tilde_B", "tilde_C", "tilde_D"):
            agree_value = agreement.get(key)
            if q_e_zero and agree_value is not None:
                raise ResponseValidationError(f"q_E=0 route_agreement.{key} must be null")
            if not q_e_zero and agree_value is None:
                raise ResponseValidationError(f"q_E!=0 route_agreement.{key} must be a value")


# --------------------------------------------------------------------------- #
# File I/O and hashing
# --------------------------------------------------------------------------- #

def _load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle, parse_float=Decimal)
    except OSError as exc:
        raise IOError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"cannot parse JSON {path}: {exc}") from exc


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError as exc:
        raise IOError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _write_response(path: str, response: dict[str, Any]) -> None:
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(response, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
    except OSError as exc:
        raise IOError(f"cannot write {path}: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise IOError(f"cannot serialize {path}: {exc}") from exc


# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #

def _read_parameters(path: str) -> dict[str, str]:
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        raise ValidationError(f"cannot read parameter CSV {path}: {exc}") from exc
    found: dict[str, str] = {}
    for row in rows:
        parameter_id = row.get("parameter_id")
        if parameter_id in {None, ""}:
            continue
        if parameter_id in found:
            raise ValidationError(f"duplicate parameter_id {parameter_id}")
        found[parameter_id] = row.get("value", "")
    return found


def _param_probability(params: dict[str, str], parameter_id: str, low: Decimal, high: Decimal) -> Decimal:
    if parameter_id not in params:
        raise ValidationError(f"missing parameter_id {parameter_id}")
    try:
        value = Decimal(params[parameter_id])
    except InvalidOperation as exc:
        raise ValidationError(f"parameter {parameter_id} is not a finite decimal") from exc
    if not value.is_finite() or not (low <= value <= high):
        raise ValidationError(f"parameter {parameter_id} outside [{low},{high}]")
    return value


def _param_int(params: dict[str, str], parameter_id: str) -> int:
    if parameter_id not in params:
        raise ValidationError(f"missing parameter_id {parameter_id}")
    raw = params[parameter_id]
    if not re.fullmatch(r"[0-9]+", raw):
        raise ValidationError(f"parameter {parameter_id} is not a non-negative integer")
    return int(raw)


# --------------------------------------------------------------------------- #
# Stage 0: upstream A/B/C kernels
# --------------------------------------------------------------------------- #

def _parse_upstream_kernels(upstream_data: Any, semantics: str) -> dict[str, dict[str, Any]]:
    if not isinstance(upstream_data, dict) or upstream_data.get("envelope_type") != "calibration_response":
        raise ValidationError("upstream envelope_type must be calibration_response")
    request_id = upstream_data.get("request_id")
    if not isinstance(request_id, str) or not request_id.endswith(":" + semantics):
        raise ValidationError("upstream request semantics does not match request semantics")
    results = upstream_data.get("results")
    if not isinstance(results, list) or [r.get("process_id") for r in results] != list("ABC"):
        raise ValidationError("upstream results must contain A,B,C in that exact order")
    kernels: dict[str, dict[str, Any]] = {}
    for result in results:
        process_id = result["process_id"]
        if result.get("status") != "UNIQUE_SOLUTION":
            raise ValidationError(f"canonical upstream {process_id} must be UNIQUE_SOLUTION")
        q = _decimal_probability_string(result.get("q"), f"upstream {process_id} q")
        e = _decimal_probability_string(result.get("e"), f"upstream {process_id} e")
        alpha = _decimal_probability_string(result.get("alpha"), f"upstream {process_id} alpha")
        beta = _decimal_probability_string(result.get("beta"), f"upstream {process_id} beta")
        kernels[process_id] = {
            "q": q, "e": e, "alpha": alpha, "beta": beta,
            "status": "UNIQUE_SOLUTION", "free_parameters": [], "source": "upstream_bound",
        }
    return kernels


def _derive_abc_kernels(values: dict[str, str], semantics: str) -> dict[str, dict[str, Any]]:
    if _calibrator is None:
        raise IOError("observation_calibration_v1 solver is unavailable")
    solver = _calibrator.solve_single if semantics == SINGLE else _calibrator.solve_chain
    q_map = {"A": values["q_a"], "B": values["q_b"], "C": values["q_c"]}
    e_map = {"A": values["e_a"], "B": values["e_b"], "C": values["e_c"]}
    kernels: dict[str, dict[str, Any]] = {}
    for process_id in PROCESSES:
        q = _decimal_probability_string(q_map[process_id], f"{process_id} q")
        e = _decimal_probability_string(e_map[process_id], f"{process_id} e")
        try:
            result = solver(process_id, q, e)
        except Exception as exc:  # solver NumericalError / Decimal errors -> NUMERICAL_FAILURE
            raise NumericalError(f"{process_id} kernel solver failure: {exc}") from exc
        alpha = result.get("alpha")
        beta = result.get("beta")
        kernels[process_id] = {
            "q": q, "e": e,
            "alpha": None if alpha is None else Decimal(alpha),
            "beta": None if beta is None else Decimal(beta),
            "status": result["status"],
            "free_parameters": list(result.get("free_parameters") or []),
            "source": "derived",
        }
    return kernels


def _abc_indeterminate(kernels: dict[str, dict[str, Any]]) -> bool:
    """Zero-weight determinism for A/B/C: free beta_j vanishes iff q_j=0 (v_j only
    multiplies q_j); free alpha_j vanishes iff q_j=1 (u_j only multiplies 1-q_j)."""
    for process_id in PROCESSES:
        kernel = kernels[process_id]
        if kernel["status"] != "NONIDENTIFIABLE_FAMILY":
            continue
        for free in kernel["free_parameters"]:
            if free == "beta" and kernel["q"] != ZERO:
                return True
            if free == "alpha" and kernel["q"] != ONE:
                return True
    return False


def _e_indeterminate(status: str, free_parameters: list[str], q_e: Decimal, z0: Decimal, z1: Decimal) -> bool:
    if status != "NONIDENTIFIABLE_FAMILY":
        return False
    for free in free_parameters:
        if free == "beta" and q_e != ZERO and z1 != ZERO:
            return True
        if free == "alpha" and q_e != ONE and z0 != ZERO:
            return True
    return False


# --------------------------------------------------------------------------- #
# E kernel (stage 2) and route comparison
# --------------------------------------------------------------------------- #

def _solve_e_kernel(q_e: Decimal, e_e: Decimal, semantics: str) -> dict[str, Any]:
    if _calibrator is None:
        raise IOError("observation_calibration_v1 solver is unavailable")
    solver = _calibrator.solve_single if semantics == SINGLE else _calibrator.solve_chain
    try:
        return solver("E", q_e, e_e)
    except Exception as exc:  # solver NumericalError / Decimal errors -> NUMERICAL_FAILURE
        raise NumericalError(f"E kernel solver failure: {exc}") from exc


def _compare_pre_e(pre_results: dict[str, dict[str, Any]]) -> Decimal:
    names = list(pre_results)
    max_deviation = ZERO
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            left = pre_results[names[a]]
            right = pre_results[names[b]]
            for key in ("q_E", "G", "Z_0", "Z_1"):
                deviation = abs(left[key] - right[key])
                if deviation > max_deviation:
                    max_deviation = deviation
            for index in range(16):
                deviation = abs(left["reach_E_distribution"][index] - right["reach_E_distribution"][index])
                if deviation > max_deviation:
                    max_deviation = deviation
    return max_deviation


def _compare_downstream(down_results: dict[str, dict[str, Any]]) -> tuple[Decimal, Decimal, Decimal]:
    names = list(down_results)
    max_all = ZERO
    max_fourfold = ZERO
    max_lambda = ZERO
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            left = down_results[names[a]]
            right = down_results[names[b]]
            for key in ("first_abnormal", "process_exit", "device_total_exit"):
                deviation = abs(left["E_rates"][key] - right["E_rates"][key])
                max_all = max(max_all, deviation)
            for key in ("p_GP", "p_BP", "p_GE", "p_BE"):
                deviation = abs(left["fourfold"][key] - right["fourfold"][key])
                max_all = max(max_all, deviation)
                max_fourfold = max(max_fourfold, deviation)
            for key in ("E_S", "E_PL", "E_PW"):
                deviation = abs(left["anchors"][key] - right["anchors"][key])
                max_all = max(max_all, deviation)
            for key in ("event_level", "first_test_only", "at_most_once_per_device"):
                deviation = abs(left["counts"][key] - right["counts"][key])
                max_all = max(max_all, deviation)
                max_lambda = max(max_lambda, deviation)
            for index in range(4):
                deviation = abs(left["multinomial_p"][index] - right["multinomial_p"][index])
                max_all = max(max_all, deviation)
                if left["lambda_main"][index] is not None and right["lambda_main"][index] is not None:
                    deviation = abs(left["lambda_main"][index] - right["lambda_main"][index])
                    max_all = max(max_all, deviation)
                    max_lambda = max(max_lambda, deviation)
                if left["lambda_tilde"][index] is not None and right["lambda_tilde"][index] is not None:
                    deviation = abs(left["lambda_tilde"][index] - right["lambda_tilde"][index])
                    max_all = max(max_all, deviation)
                    max_lambda = max(max_lambda, deviation)
    return max_all, max_fourfold, max_lambda


# --------------------------------------------------------------------------- #
# Response builders
# --------------------------------------------------------------------------- #

def _abc_kernels_public(kernels: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for process_id in PROCESSES:
        kernel = kernels[process_id]
        item: dict[str, Any] = {
            "process_id": process_id,
            "q": _plain(kernel["q"]),
            "e": _plain(kernel["e"]),
            "status": kernel["status"],
            "free_parameters": list(kernel["free_parameters"]),
            "source": kernel["source"],
        }
        if kernel["alpha"] is not None:
            item["alpha"] = _plain(kernel["alpha"], 17)
        if kernel["beta"] is not None:
            item["beta"] = _plain(kernel["beta"], 17)
        items.append(item)
    return items


def _base_response(request: dict[str, Any], kernels: dict[str, dict[str, Any]],
                   overall_status: str) -> dict[str, Any]:
    response: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "envelope_type": "q1_response",
        "request_id": request["request_id"],
        "scenario_role": request["scenario_role"],
        "semantics": request["semantics"],
        "overall_status": overall_status,
        "abc_kernels": _abc_kernels_public(kernels),
    }
    return response


def _downstream_nulls(response: dict[str, Any]) -> dict[str, Any]:
    """The frozen schema forces the downstream blocks to be ABSENT (not null) for
    HAS_INFEASIBLE / HAS_INDETERMINATE: the response envelope leaf types (object)
    and the HAS_INFEASIBLE then-branch (type null) cannot both hold for a present
    key, so omission is the only schema-valid representation ("null means absent
    by construction" in the fixture grammar)."""
    for key in ("E_rates", "fourfold", "anchors", "lambda", "multinomial", "route_agreement"):
        response.pop(key, None)
    return response


def _e_kernel_public(e_kernel_result: dict[str, Any], semantics: str) -> dict[str, Any]:
    diagnostics = e_kernel_result.get("diagnostics") or {}
    block: dict[str, Any] = {
        "status": e_kernel_result["status"],
        "free_parameters": list(e_kernel_result.get("free_parameters") or []),
        "diagnostics": {
            "method": diagnostics.get("method", ""),
            "feasibility": diagnostics.get("feasibility", ""),
            "notes": list(diagnostics.get("notes") or []),
        },
    }
    if e_kernel_result.get("alpha") is not None:
        block["alpha_E"] = e_kernel_result["alpha"]
    if e_kernel_result.get("beta") is not None:
        block["beta_E"] = e_kernel_result["beta"]
    if semantics == SINGLE and e_kernel_result.get("e_max") is not None:
        block["e_max_E"] = e_kernel_result["e_max"]
    return block


def _build_infeasible_response(request: dict[str, Any], kernels: dict[str, dict[str, Any]],
                               stage: str, notes: list[str]) -> dict[str, Any]:
    response = _base_response(request, kernels, "HAS_INFEASIBLE")
    response["infeasible_stage"] = stage
    _downstream_nulls(response)
    response["diagnostics"] = {"notes": notes}
    return response


def _build_e_infeasible_response(request: dict[str, Any], kernels: dict[str, dict[str, Any]],
                                 pre_results: dict[str, dict[str, Any]],
                                 e_kernel_result: dict[str, Any], notes: list[str]) -> dict[str, Any]:
    response = _build_infeasible_response(request, kernels, "E_KERNEL", notes)
    pre = pre_results["closed_form"]
    response["q_E"] = _plain(pre["q_E"], 17)
    response["G"] = _plain(pre["G"], 17)
    response["Z_0"] = _plain(pre["Z_0"], 17)
    response["Z_1"] = _plain(pre["Z_1"], 17)
    response["reach_E_distribution"] = [_plain(value, 17) for value in pre["reach_E_distribution"]]
    response["E_kernel"] = _e_kernel_public(e_kernel_result, request["semantics"])
    return response


def _build_indeterminate_response(request: dict[str, Any], kernels: dict[str, dict[str, Any]],
                                  stage: str, notes: list[str]) -> dict[str, Any]:
    response = _base_response(request, kernels, "HAS_INDETERMINATE")
    response["infeasible_stage"] = stage
    _downstream_nulls(response)
    response["diagnostics"] = {"notes": notes}
    return response


def _build_numerical_failure_response(request: dict[str, Any], kernels: dict[str, dict[str, Any]],
                                      notes: list[str]) -> dict[str, Any]:
    response = _base_response(request, kernels, "NUMERICAL_FAILURE")
    response["diagnostics"] = {"notes": notes}
    return response


def _build_full_response(request: dict[str, Any], kernels: dict[str, dict[str, Any]],
                         pre_results: dict[str, dict[str, Any]],
                         down_results: dict[str, dict[str, Any]],
                         e_kernel_result: dict[str, Any], e_kernel: dict[str, Decimal],
                         overall_status: str, maxdev_pre: Decimal, maxdev_down: Decimal,
                         maxdev_fourfold: Decimal, maxdev_lambda: Decimal,
                         notes: list[str]) -> dict[str, Any]:
    pre = pre_results["closed_form"]
    down = down_results["closed_form"]
    q_e = pre["q_E"]
    beta_e = e_kernel["beta"]
    na = (q_e == ZERO) or (beta_e == ONE)
    response = _base_response(request, kernels, overall_status)
    response["q_E"] = _plain(q_e, 17)
    response["G"] = _plain(pre["G"], 17)
    response["Z_0"] = _plain(pre["Z_0"], 17)
    response["Z_1"] = _plain(pre["Z_1"], 17)
    response["reach_E_distribution"] = [_plain(value, 17) for value in pre["reach_E_distribution"]]
    response["E_kernel"] = _e_kernel_public(e_kernel_result, request["semantics"])
    rates = down["E_rates"]
    response["E_rates"] = {
        "first_abnormal": _plain(rates["first_abnormal"], 17),
        "process_exit": _plain(rates["process_exit"], 17),
        "device_total_exit": _plain(rates["device_total_exit"], 17),
    }
    fourfold = down["fourfold"]
    four_sum = _dsum([fourfold["p_GP"], fourfold["p_BP"], fourfold["p_GE"], fourfold["p_BE"]], 200)
    response["fourfold"] = {
        "p_GP": _plain(fourfold["p_GP"], 17),
        "p_BP": _plain(fourfold["p_BP"], 17),
        "p_GE": _plain(fourfold["p_GE"], 17),
        "p_BE": _plain(fourfold["p_BE"], 17),
        "sum": _plain(four_sum, 17),
        "per_route": {
            name: {
                "p_GP": _plain(down_results[name]["fourfold"]["p_GP"], 17),
                "p_BP": _plain(down_results[name]["fourfold"]["p_BP"], 17),
                "p_GE": _plain(down_results[name]["fourfold"]["p_GE"], 17),
                "p_BE": _plain(down_results[name]["fourfold"]["p_BE"], 17),
            }
            for name in ROUTE_NAMES
        },
        "max_abs_deviation": _plain(maxdev_fourfold, 17),
    }
    anchors = down["anchors"]
    response["anchors"] = {
        "E_S": _plain(anchors["E_S"], 17),
        "E_PL": _plain(anchors["E_PL"], 17),
        "E_PW": _plain(anchors["E_PW"], 17),
    }
    main_raw = down["lambda_main"]
    tilde_raw = down["lambda_tilde"]
    if na:
        # V1.0.3: NA must never masquerade as a number.
        main_public: dict[str, Any] = {"A": None, "B": None, "C": None, "D": None}
        lambda_sum_public: str | None = None
    else:
        main_public = {
            "A": _plain(main_raw[0], 17), "B": _plain(main_raw[1], 17),
            "C": _plain(main_raw[2], 17), "D": _plain(main_raw[3], 17),
        }
        lambda_sum_public = _plain(_dsum([v for v in main_raw if v is not None], 200), 17)
    if q_e == ZERO:
        tilde_public: dict[str, Any] = {"A": None, "B": None, "C": None, "D": None}
    else:
        tilde_public = {
            "A": _plain(tilde_raw[0], 17), "B": _plain(tilde_raw[1], 17),
            "C": _plain(tilde_raw[2], 17), "D": _plain(tilde_raw[3], 17),
        }
    counts = down["counts"]
    response["lambda"] = {
        "main": main_public,
        "sum": lambda_sum_public,
        "counts": {
            "event_level": _plain(counts["event_level"], 17),
            "first_test_only": _plain(counts["first_test_only"], 17),
            "at_most_once_per_device": _plain(counts["at_most_once_per_device"], 17),
        },
        "tilde": tilde_public,
        "na": na,
        "max_abs_deviation": None if na else _plain(maxdev_lambda, 17),
    }
    response["multinomial"] = {
        "N": 100,
        "p": [_plain(value, 17) for value in down["multinomial_p"]],
    }
    # V1.0.3: route_agreement.lambda_* is null whenever lambda.na is true (the
    # formal predicate is na = (q_E==0 OR beta_E==1), not q_E==0 alone); the old
    # raw-route-value emission on NA is gone.  route_agreement.tilde_* is null
    # when q_E is a mathematical zero, numeric otherwise.
    if na:
        lambda_agree: list[str | None] = [None, None, None, None]
    else:
        lambda_agree = [_plain(value, 17) for value in main_raw]
    if q_e == ZERO:
        tilde_agree: list[str | None] = [None, None, None, None]
    else:
        tilde_agree = [_plain(value, 17) for value in tilde_raw]
    response["route_agreement"] = {
        "q_E": _plain(q_e, 17),
        "G": _plain(pre["G"], 17),
        "Z_0": _plain(pre["Z_0"], 17),
        "Z_1": _plain(pre["Z_1"], 17),
        "p_GP": _plain(fourfold["p_GP"], 17),
        "p_BP": _plain(fourfold["p_BP"], 17),
        "p_GE": _plain(fourfold["p_GE"], 17),
        "p_BE": _plain(fourfold["p_BE"], 17),
        "lambda_A": lambda_agree[0],
        "lambda_B": lambda_agree[1],
        "lambda_C": lambda_agree[2],
        "lambda_D": lambda_agree[3],
        "tilde_A": tilde_agree[0],
        "tilde_B": tilde_agree[1],
        "tilde_C": tilde_agree[2],
        "tilde_D": tilde_agree[3],
    }
    response["diagnostics"] = {"notes": notes}
    return response


# --------------------------------------------------------------------------- #
# Main orchestration
# --------------------------------------------------------------------------- #

def _run(arguments: argparse.Namespace) -> tuple[dict[str, Any] | None, int]:
    schema_root = _load_json(arguments.schema)
    if _sha256_file(arguments.schema) != FROZEN_SCHEMA_SHA256:
        raise ValidationError("schema SHA-256 does not match frozen G2-02 binding")
    request = _load_json(arguments.request)
    _validate_request(request, schema_root)
    semantics = request["semantics"]
    params = _read_parameters(arguments.parameters)

    if request["upstream"]["mode"] == "bound_frozen":
        reference = request["upstream"]["reference"]
        if reference.get("semantics_expect") != semantics:
            raise ValidationError("upstream.reference.semantics_expect must equal request.semantics")
        actual_hash = _sha256_file(arguments.upstream)
        if actual_hash != reference.get("sha256"):
            raise ValidationError("upstream SHA-256 does not match reference.sha256")
        if actual_hash != FROZEN_UPSTREAM_SHA256[semantics]:
            raise ValidationError("upstream SHA-256 does not match frozen G2-02 binding")
        upstream_data = _load_json(arguments.upstream)
        kernels = _parse_upstream_kernels(upstream_data, semantics)
        q_d = _param_probability(params, "P029", ZERO, ONE)
        e_e = _param_probability(params, "P033", ZERO, ONE)
        precision_inputs = (
            [str(kernels[pid]["q"]) for pid in PROCESSES]
            + [str(kernels[pid]["e"]) for pid in PROCESSES]
            + [str(q_d), str(e_e)]
        )
        upstream_note = f"upstream_sha256={actual_hash} verified"
    else:
        values = request["upstream"]["values"]
        kernels = _derive_abc_kernels(values, semantics)
        q_d = _decimal_probability_string(values["q_d"], "q_d")
        e_e = _decimal_probability_string(values["e_e"], "e_e")
        precision_inputs = [values[key] for key in ("q_a", "q_b", "q_c", "q_d", "e_a", "e_b", "e_c", "e_e")]
        upstream_note = "upstream_mode=derive_from_values"
    n_two = _param_int(params, "P037")
    if n_two != 100:
        raise ValidationError("P037 N_2 must equal 100")
    p0 = _working_precision(precision_inputs)

    # Stage 0 outcomes.
    if any(kernels[pid]["status"] == "INFEASIBLE" for pid in PROCESSES):
        notes = [upstream_note, f"p0={p0}",
                 "upstream A/B/C kernel infeasible; q_E and downstream are null (no clipping)"]
        return _build_infeasible_response(request, kernels, "ABC_KERNEL", notes), 0
    if _abc_indeterminate(kernels):
        notes = [upstream_note, f"p0={p0}",
                 "upstream nonidentifiable free parameter does not vanish; downstream null"]
        return _build_indeterminate_response(request, kernels, "ABC_KERNEL", notes), 0

    concrete = {
        pid: {
            "q": kernels[pid]["q"],
            "alpha": ZERO if kernels[pid]["alpha"] is None else kernels[pid]["alpha"],
            "beta": ZERO if kernels[pid]["beta"] is None else kernels[pid]["beta"],
        }
        for pid in PROCESSES
    }

    # Stage 1: three routes compute the pre-E block independently.
    pre_results: dict[str, dict[str, Any]] = {}
    try:
        for name, module in ROUTE_MODULES.items():
            pre_results[name] = module.compute_pre_e(concrete, q_d, p0)
        maxdev_pre = _compare_pre_e(pre_results)

        # Stage 2: E kernel on the closed-form q_E.
        q_e = pre_results["closed_form"]["q_E"]
        e_kernel_result = _solve_e_kernel(q_e, e_e, semantics)
        e_status = e_kernel_result["status"]
        e_free = list(e_kernel_result.get("free_parameters") or [])
        z0 = pre_results["closed_form"]["Z_0"]
        z1 = pre_results["closed_form"]["Z_1"]
        if e_status == "INFEASIBLE":
            notes = [upstream_note, f"p0={p0}",
                     f"E kernel infeasible for q_E={_plain(q_e, 17)}, e_E={_plain(e_e, 17)}; "
                     "E_rates/fourfold/anchors/lambda/multinomial are null (no projection)"]
            return _build_e_infeasible_response(request, kernels, pre_results, e_kernel_result, notes), 0
        if e_status == "NONIDENTIFIABLE_FAMILY":
            if _e_indeterminate(e_status, e_free, q_e, z0, z1):
                notes = [upstream_note, f"p0={p0}",
                         "E kernel nonidentifiable free parameter does not vanish; downstream null"]
                return _build_indeterminate_response(request, kernels, "E_KERNEL", notes), 0
            alpha_e = e_kernel_result.get("alpha")
            beta_e = e_kernel_result.get("beta")
            alpha_e_value = ZERO if alpha_e is None else Decimal(alpha_e)
            beta_e_value = ZERO if beta_e is None else Decimal(beta_e)
        else:
            alpha_e_value = Decimal(e_kernel_result["alpha"])
            beta_e_value = Decimal(e_kernel_result["beta"])
        e_kernel = {"alpha": alpha_e_value, "beta": beta_e_value}

        # Stages 3-5: three routes compute the downstream block independently.
        down_results: dict[str, dict[str, Any]] = {}
        for name, module in ROUTE_MODULES.items():
            down_results[name] = module.compute_downstream(concrete, q_d, pre_results[name], e_kernel, p0)
        maxdev_down, maxdev_fourfold, maxdev_lambda = _compare_downstream(down_results)

        # Conservation invariants.
        four = down_results["closed_form"]["fourfold"]
        four_sum = _dsum([four["p_GP"], four["p_BP"], four["p_GE"], four["p_BE"]], p0)
        lambda_sum: Decimal | None = None
        if q_e != ZERO and beta_e_value != ONE:
            lambda_sum = _dsum([value for value in down_results["closed_form"]["lambda_main"] if value is not None], p0)
        if abs(four_sum - ONE) > CONSERVATION_TOLERANCE:
            notes = [upstream_note, f"p0={p0}", f"fourfold sum deviation from 1 exceeds tolerance: {_plain(abs(four_sum - ONE), 17)}"]
            return _build_numerical_failure_response(request, kernels, notes), 3
        if lambda_sum is not None and abs(lambda_sum - ONE) > CONSERVATION_TOLERANCE:
            notes = [upstream_note, f"p0={p0}", f"lambda sum deviation from 1 exceeds tolerance: {_plain(abs(lambda_sum - ONE), 17)}"]
            return _build_numerical_failure_response(request, kernels, notes), 3
    except NumericalError as exc:
        print(f"numerical failure: {exc}", file=sys.stderr)
        return _build_numerical_failure_response(request, kernels, [upstream_note, str(exc)]), 3
    except (InvalidOperation, ArithmeticError) as exc:
        print(f"numerical failure: {exc}", file=sys.stderr)
        return _build_numerical_failure_response(request, kernels, [upstream_note, str(exc)]), 3

    mismatch = maxdev_pre > CROSS_ROUTE_TOLERANCE or maxdev_down > CROSS_ROUTE_TOLERANCE
    overall_status = "ROUTE_MISMATCH" if mismatch else "ALL_ROUTES_AGREE"
    notes = [
        upstream_note,
        f"p0={p0}",
        f"three_route_pre_e_max_abs_deviation={_plain(maxdev_pre, 17)}",
        f"three_route_downstream_max_abs_deviation={_plain(maxdev_down, 17)}",
        f"fourfold_sum_deviation_from_1={_plain(abs(four_sum - ONE), 17)}",
    ]
    if lambda_sum is not None:
        notes.append(f"lambda_sum_deviation_from_1={_plain(abs(lambda_sum - ONE), 17)}")
    if (q_e == ZERO) or (beta_e_value == ONE):
        notes.append("lambda main table NA (q_E=0 or beta_E=1); lambda.main/sum/max_abs_deviation and route_agreement.lambda_* are null")
    if q_e == ZERO:
        notes.append("tilde NA (q_E=0); lambda.tilde and route_agreement.tilde_* are null")
    if mismatch:
        notes.append("route comparison exceeded frozen tolerance; overall_status=ROUTE_MISMATCH")
    response = _build_full_response(request, kernels, pre_results, down_results, e_kernel_result,
                                    e_kernel, overall_status, maxdev_pre, maxdev_down,
                                    maxdev_fourfold, maxdev_lambda, notes)
    return response, (3 if mismatch else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="q1_quality_v1")
    parser.add_argument("--request", required=True)
    parser.add_argument("--parameters", required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args(argv)

    try:
        response, exit_code = _run(arguments)
    except ValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2
    except NumericalError as exc:
        # Only reachable if the frozen A/B/C solver itself fails numerically on a
        # derive request (unreachable for valid [0,1] inputs); no kernel values
        # exist to serialize, so no response file is written.
        print(f"numerical failure: {exc}", file=sys.stderr)
        return 3
    except IOError as exc:
        print(f"I/O failure: {exc}", file=sys.stderr)
        return 4
    except ResponseValidationError as exc:
        print(f"internal response validation failure: {exc}", file=sys.stderr)
        return 4

    if response is None:
        print("internal error: no response produced", file=sys.stderr)
        return 4
    try:
        schema_root = _load_json(arguments.schema)
        _validate_response(response, schema_root)
    except ResponseValidationError as exc:
        print(f"internal response validation failure: {exc}", file=sys.stderr)
        return 4
    try:
        _write_response(arguments.output, response)
    except IOError as exc:
        print(f"I/O failure: {exc}", file=sys.stderr)
        return 4
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
