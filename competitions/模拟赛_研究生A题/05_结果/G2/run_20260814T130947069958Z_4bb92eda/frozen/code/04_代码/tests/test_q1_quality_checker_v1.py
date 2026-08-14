# -*- coding: utf-8 -*-
"""Unit tests for the E2 independent checker (q1_quality_checker_v1).

Oracle expectations come EXCLUSIVELY from the ``E2_embedded_oracles`` section
of the frozen task package G2-02-SPEC-V1.0.4 (this module never reads the
external fixture ``04_代码/tests/fixtures/q1_quality_oracles_v1.json``, never
reads request files, never reads main_model sources or project documents).

Coverage required by the frozen spec (``E2_embedded_oracles.coverage_requirement``):
both semantics' perfect full chain, upstream infeasible, E infeasible; single
additionally the NA branch and the concentration/count-pinning case; plus
isolation (file-access) tests proving the checker code never opens forbidden
paths, and CLI contract tests (--request rejection, preflight sentinel).

V1.0.4 rebind coverage: the lambda NA/null contract (main/sum/max_abs_deviation
and route_agreement.lambda_* null when na=true; tilde null when q_E == 0 and
numeric when q_E > 0; a numeric "0" in any NA field must FAIL) and the
e_max_E semantic gate (single asserts numerically; chain emits NOT_APPLICABLE
and an omitted e_max_E must not fail).
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import inspect
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from decimal import Decimal, getcontext
from fractions import Fraction

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_ROOT = os.path.dirname(TESTS_DIR)          # 04_代码
PROJECT_ROOT = os.path.dirname(CODE_ROOT)        # 模拟赛_研究生A题
sys.path.insert(0, CODE_ROOT)

from checker import q1_quality_checker_v1 as chk  # noqa: E402

REAL_SCHEMA = os.path.join(CODE_ROOT, "src", "schemas", "q1_quality_v1.schema.json")

RUN_ID = "20260813T134251279572Z_abcd1234"


def fr(s):
    """'num/den' or decimal string -> Fraction."""
    if "/" in s:
        n, d = s.split("/")
        return Fraction(int(n), int(d))
    return Fraction(Decimal(s))


def dec_of(fr_val):
    return Decimal(fr_val.numerator) / Decimal(fr_val.denominator)


def assert_close(testcase, computed, expected, tol="1e-15"):
    testcase.assertIsNotNone(computed, "expected a value, got None")
    dev = abs(Decimal(computed) - dec_of(fr(expected)))
    testcase.assertLessEqual(dev, Decimal(tol),
                             "deviation %s exceeds %s (computed=%s expected=%s)"
                             % (dev, tol, computed, expected))


# --------------------------------------------------------------------------
# E2_embedded_oracles (verbatim from the frozen task package)
# --------------------------------------------------------------------------

ORACLES = [
    {
        "id": "O1_perfect_symmetric",
        "semantics": chk.SEMANTICS_SINGLE,
        "input": {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
                  "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"},
        "expected": {
            "upstream": ["UNIQUE_SOLUTION", "UNIQUE_SOLUTION", "UNIQUE_SOLUTION"],
            "overall": "ALL_ROUTES_AGREE",
            "q_E": "1/4",
            "E_kernel": {"status": "UNIQUE_SOLUTION", "alpha_E": "0/1", "beta_E": "0/1"},
            "fourfold": ["81/256", "0/1", "0/1", "175/256"],
            "lambda_main": ["0/1", "0/1", "0/1", "1/1"],
            "counts": ["2/1", "1/1", "1/1"],
            "tilde": ["0/1", "0/1", "0/1", "1/1"],
        },
    },
    {
        "id": "O2_upstream_infeasible",
        "semantics": chk.SEMANTICS_SINGLE,
        "input": {"q_a": "0", "q_b": "0", "q_c": "0", "q_d": "0",
                  "e_a": "0.02", "e_b": "0.02", "e_c": "0.02", "e_e": "0.02"},
        "expected": {
            "upstream": ["INFEASIBLE", "INFEASIBLE", "INFEASIBLE"],
            "overall": "HAS_INFEASIBLE",
            "stage": "ABC_KERNEL",
        },
    },
    {
        "id": "O3_E_infeasible",
        "semantics": chk.SEMANTICS_SINGLE,
        "input": {"q_a": "0.5", "q_b": "0.5", "q_c": "0.5", "q_d": "0.5",
                  "e_a": "0.5", "e_b": "0.5", "e_c": "0.5", "e_e": "0.5"},
        "expected": {
            "upstream": ["UNIQUE_SOLUTION", "UNIQUE_SOLUTION", "UNIQUE_SOLUTION"],
            "overall": "HAS_INFEASIBLE",
            "stage": "E_KERNEL",
            "q_E": "15/16",
            "E_kernel": {"status": "INFEASIBLE", "e_max_E": "1/8"},
        },
    },
    {
        "id": "O5_NA_beta1",
        "semantics": chk.SEMANTICS_SINGLE,
        "input": {"q_a": "0.125", "q_b": "0.125", "q_c": "0.125", "q_d": "0.125",
                  "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0.25"},
        "expected": {
            "upstream": ["UNIQUE_SOLUTION", "UNIQUE_SOLUTION", "UNIQUE_SOLUTION"],
            "overall": "ALL_ROUTES_AGREE",
            "q_E": "1/8",
            "E_kernel": {"status": "UNIQUE_SOLUTION", "alpha_E": "1/7", "beta_E": "1/1"},
            "fourfold": ["147/256", "343/4096", "49/4096", "169/512"],
            "lambda_main": [None, None, None, None],
            "counts": ["0/1", "0/1", "0/1"],
            "tilde": ["0/1", "0/1", "0/1", "1/1"],
        },
    },
    {
        "id": "O6_concentration",
        "semantics": chk.SEMANTICS_SINGLE,
        "input": {"q_a": "0.25", "q_b": "0", "q_c": "0", "q_d": "0",
                  "e_a": "0.375", "e_b": "0", "e_c": "0", "e_e": "0.25"},
        "expected": {
            "upstream": ["UNIQUE_SOLUTION", "NONIDENTIFIABLE_FAMILY", "NONIDENTIFIABLE_FAMILY"],
            "overall": "ALL_ROUTES_AGREE",
            "q_E": "1/4",
            "E_kernel": {"status": "UNIQUE_SOLUTION", "alpha_E": "1/6", "beta_E": "1/2"},
            "fourfold": ["175/256", "45/256", "17/256", "19/256"],
            "lambda_main": ["1/1", "0/1", "0/1", "0/1"],
            "counts": ["3/4", "1/2", "1/2"],
            "tilde": ["1/1", "0/1", "0/1", "0/1"],
        },
    },
    {
        "id": "O1c_perfect_symmetric",
        "semantics": chk.SEMANTICS_CHAIN,
        "input": {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
                  "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"},
        "expected": {
            "upstream": ["UNIQUE_SOLUTION", "UNIQUE_SOLUTION", "UNIQUE_SOLUTION"],
            "overall": "ALL_ROUTES_AGREE",
            "q_E": "1/4",
            "E_kernel": {"status": "UNIQUE_SOLUTION", "alpha_E": "0/1", "beta_E": "0/1"},
            "fourfold": ["81/256", "0/1", "0/1", "175/256"],
            "lambda_main": ["0/1", "0/1", "0/1", "1/1"],
            "counts": ["2/1", "1/1", "1/1"],
            "tilde": ["0/1", "0/1", "0/1", "1/1"],
        },
    },
    {
        "id": "O2c_upstream_infeasible",
        "semantics": chk.SEMANTICS_CHAIN,
        "input": {"q_a": "0", "q_b": "0", "q_c": "0", "q_d": "0",
                  "e_a": "0.02", "e_b": "0.02", "e_c": "0.02", "e_e": "0.02"},
        "expected": {
            "upstream": ["INFEASIBLE", "INFEASIBLE", "INFEASIBLE"],
            "overall": "HAS_INFEASIBLE",
            "stage": "ABC_KERNEL",
        },
    },
    {
        "id": "O3c_E_infeasible",
        "semantics": chk.SEMANTICS_CHAIN,
        "input": {"q_a": "0.5", "q_b": "0.5", "q_c": "0.5", "q_d": "0.5",
                  "e_a": "0.5", "e_b": "0.5", "e_c": "0.5", "e_e": "0.5"},
        "expected": {
            "upstream": ["UNIQUE_SOLUTION", "UNIQUE_SOLUTION", "UNIQUE_SOLUTION"],
            "overall": "HAS_INFEASIBLE",
            "stage": "E_KERNEL",
            "q_E": "15/16",
            "E_kernel": {"status": "INFEASIBLE"},
        },
    },
]


def _run_oracle(case, Num):
    inp = case["input"]
    q = {k: (Decimal(v) if Num is Decimal else fr(v)) for k, v in inp.items()}
    return chk.compute_independent_full(
        case["semantics"], q["q_a"], q["q_b"], q["q_c"], q["q_d"],
        q["e_a"], q["e_b"], q["e_c"], q["e_e"], Num=Num)


class OracleCoverageTests(unittest.TestCase):
    """Every E2_embedded_oracles case, evaluated with Decimal >= 120."""

    def test_all_embedded_oracles(self):
        for case in ORACLES:
            with self.subTest(case=case["id"]):
                result = _run_oracle(case, Decimal)
                exp = case["expected"]
                self.assertEqual([k["status"] for k in result["abc_kernels"]],
                                 exp["upstream"], case["id"])
                self.assertEqual(result["overall_status"], exp["overall"], case["id"])
                if "stage" in exp:
                    self.assertEqual(result["infeasible_stage"], exp["stage"], case["id"])
                if "q_E" in exp:
                    assert_close(self, result["q_E"], exp["q_E"])
                if "E_kernel" in exp:
                    ek = result["E_kernel"]
                    self.assertEqual(ek["status"], exp["E_kernel"]["status"], case["id"])
                    if "alpha_E" in exp["E_kernel"]:
                        assert_close(self, ek["alpha"], exp["E_kernel"]["alpha_E"])
                    if "beta_E" in exp["E_kernel"]:
                        assert_close(self, ek["beta"], exp["E_kernel"]["beta_E"])
                    if "e_max_E" in exp["E_kernel"]:
                        assert_close(self, ek["e_max"], exp["E_kernel"]["e_max_E"], "5e-12")
                if "fourfold" in exp and result["fourfold"] is not None:
                    for name, expected in zip(("p_GP", "p_BP", "p_GE", "p_BE"),
                                              exp["fourfold"]):
                        assert_close(self, result["fourfold"][name], expected)
                if "lambda_main" in exp and result["lambda"] is not None:
                    for m, expected in zip("ABCD", exp["lambda_main"]):
                        if expected is None:
                            self.assertIsNone(result["lambda"]["main"][m], case["id"])
                        else:
                            assert_close(self, result["lambda"]["main"][m], expected)
                if "counts" in exp and result["lambda"] is not None:
                    for name, expected in zip(("event_level", "first_test_only",
                                               "at_most_once_per_device"), exp["counts"]):
                        assert_close(self, result["lambda"]["counts"][name], expected)
                if "tilde" in exp and result["lambda"] is not None:
                    for m, expected in zip("ABCD", exp["tilde"]):
                        assert_close(self, result["lambda"]["tilde"][m], expected)

    def test_fraction_exactness_single(self):
        """The single-semantics path is pure rational arithmetic: Fraction mode
        reproduces the oracle fractions EXACTLY (Fraction 处理有理数)."""
        for case in ORACLES:
            if case["semantics"] != chk.SEMANTICS_SINGLE:
                continue
            with self.subTest(case=case["id"]):
                result = _run_oracle(case, Fraction)
                exp = case["expected"]
                if "q_E" in exp:
                    self.assertEqual(result["q_E"], fr(exp["q_E"]), case["id"])
                if "E_kernel" in exp and "alpha_E" in exp["E_kernel"]:
                    self.assertEqual(result["E_kernel"]["alpha"], fr(exp["E_kernel"]["alpha_E"]), case["id"])
                    self.assertEqual(result["E_kernel"]["beta"], fr(exp["E_kernel"]["beta_E"]), case["id"])
                if "fourfold" in exp and result["fourfold"] is not None:
                    for name, expected in zip(("p_GP", "p_BP", "p_GE", "p_BE"),
                                              exp["fourfold"]):
                        self.assertEqual(result["fourfold"][name], fr(expected), case["id"])
                if "lambda_main" in exp and result["lambda"] is not None:
                    for m, expected in zip("ABCD", exp["lambda_main"]):
                        if expected is None:
                            self.assertIsNone(result["lambda"]["main"][m], case["id"])
                        else:
                            self.assertEqual(result["lambda"]["main"][m], fr(expected), case["id"])
                if "counts" in exp and result["lambda"] is not None:
                    for name, expected in zip(("event_level", "first_test_only",
                                               "at_most_once_per_device"), exp["counts"]):
                        self.assertEqual(result["lambda"]["counts"][name], fr(expected), case["id"])
                if "tilde" in exp and result["lambda"] is not None:
                    for m, expected in zip("ABCD", exp["tilde"]):
                        self.assertEqual(result["lambda"]["tilde"][m], fr(expected), case["id"])

    def test_na_branch_semantics(self):
        """O5: lambda main all NA (beta_E=1), tilde still computed, counts 0."""
        result = _run_oracle(ORACLES[3], Decimal)
        self.assertEqual(result["lambda"]["na"], True)
        self.assertTrue(all(result["lambda"]["main"][m] is None for m in "ABCD"))
        self.assertIsNone(result["lambda"]["sum"])
        assert_close(self, result["lambda"]["tilde"]["D"], "1/1")
        assert_close(self, result["lambda"]["counts"]["event_level"], "0/1")
        # tilde is NOT NA when only beta_E == 1 (NA only when q_E == 0)
        self.assertIsNotNone(result["lambda"]["tilde"]["D"])

    def test_concentration_counts_pinning(self):
        """O6: upstream NONIDENTIFIABLE but downstream determined; lambda and
        counts pin SD-G2-02-LAMBDA-ONCE."""
        result = _run_oracle(ORACLES[4], Decimal)
        self.assertEqual([k["status"] for k in result["abc_kernels"]],
                         ["UNIQUE_SOLUTION", "NONIDENTIFIABLE_FAMILY", "NONIDENTIFIABLE_FAMILY"])
        self.assertEqual([k["free_parameters"] for k in result["abc_kernels"]],
                         [[], ["beta"], ["beta"]])
        assert_close(self, result["lambda"]["main"]["A"], "1/1")
        for m in "BCD":
            assert_close(self, result["lambda"]["main"][m], "0/1")
        assert_close(self, result["lambda"]["counts"]["event_level"], "3/4")
        assert_close(self, result["lambda"]["counts"]["first_test_only"], "1/2")
        assert_close(self, result["lambda"]["counts"]["at_most_once_per_device"], "1/2")

    def test_e_infeasible_no_projection(self):
        """O3/O3c: E INFEASIBLE, alpha_E/beta_E null, q_E preserved."""
        for case in (ORACLES[2], ORACLES[7]):
            with self.subTest(case=case["id"]):
                result = _run_oracle(case, Decimal)
                self.assertEqual(result["overall_status"], "HAS_INFEASIBLE")
                self.assertEqual(result["infeasible_stage"], "E_KERNEL")
                self.assertEqual(result["E_kernel"]["status"], "INFEASIBLE")
                self.assertIsNone(result["E_kernel"]["alpha"])
                self.assertIsNone(result["E_kernel"]["beta"])
                self.assertIsNone(result["fourfold"])
                self.assertIsNone(result["lambda"])
                assert_close(self, result["q_E"], case["expected"]["q_E"])


# --------------------------------------------------------------------------
# Isolation tests
# --------------------------------------------------------------------------

FORBIDDEN_PATH_MARKERS = (
    "fixtures", "request.json", "main_model", "01_审计", "03_模型", "99_归档",
    "CURRENT_STATE.md", "q1_quality_oracles_v1.json",
)


class _OpenTracer:
    def __init__(self):
        self.opened = []
        self._original = builtins.open

    def __call__(self, file, *args, **kwargs):
        self.opened.append(str(file))
        return self._original(file, *args, **kwargs)


@contextmanager
def _tracing_open():
    tracer = _OpenTracer()
    builtins.open = tracer
    try:
        yield tracer
    finally:
        builtins.open = tracer._original


class IsolationTests(unittest.TestCase):
    def test_no_forbidden_imports(self):
        """The checker module imports no main_model / checker / fixture code."""
        source = inspect.getsource(chk)
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for mod in imported:
            self.assertFalse(mod.startswith("main_model"),
                             "checker imports main_model: %s" % mod)
            self.assertFalse(mod.startswith("checker.") or mod == "checker",
                             "checker imports another checker module: %s" % mod)
        self.assertTrue(imported, "expected at least stdlib imports")

    def test_file_access_isolation(self):
        """Running the full CLI verification path must never open request
        files, the external fixture, main_model sources or project docs."""
        with tempfile.TemporaryDirectory(prefix="e2_isolation_test_") as tmp:
            params, upstream, schema, task_pkg, response, report = \
                _make_cli_inputs(tmp, tamper_q_e=None)
            argv = _cli_argv(response, params, upstream, schema, task_pkg, report)
            with _tracing_open() as tracer:
                code = chk.main(argv)
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(report))
            for opened in tracer.opened:
                for marker in FORBIDDEN_PATH_MARKERS:
                    self.assertNotIn(marker, opened,
                                     "checker opened forbidden path %s" % opened)

    def test_compute_path_opens_no_files(self):
        """The pure computation functions perform no file I/O at all."""
        with _tracing_open() as tracer:
            chk.compute_independent_full(
                chk.SEMANTICS_SINGLE,
                Fraction(1, 4), Fraction(1, 4), Fraction(1, 4), Fraction(1, 4),
                Fraction(0), Fraction(0), Fraction(0), Fraction(0),
                Num=Fraction)
        self.assertEqual(tracer.opened, [])


# --------------------------------------------------------------------------
# CLI contract tests
# --------------------------------------------------------------------------

def _make_parameters_csv(path, values=None):
    values = values or {
        "P026": "0.25", "P027": "0.25", "P028": "0.25", "P029": "0.25",
        "P030": "0", "P031": "0", "P032": "0", "P033": "0", "P037": "100",
    }
    header = ("parameter_id,symbol,code_name,entity,value,unit,source_page,"
              "source_type,availability,valid_range_or_set,planned_use,semantic_issue")
    rows = [header]
    for pid, val in values.items():
        rows.append("%s,x,x,x,%s,x,1,x,x,[0,1],x,x" % (pid, val))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rows) + "\n")


def _make_task_package(path, params_hash, upstream_hash, schema_hash,
                       wrong_params=False, version="G2-02-SPEC-V1.0.5"):
    p = ("0" * 64) if wrong_params else params_hash
    doc = (
        "task_package_version: \"%s\"\n"
        "shared_read_only_artifacts:\n"
        "  frozen_sha256:\n"
        "    parameters_csv: \"%s\"\n"
        "    schema: \"%s\"\n"
        "    oracle_fixture: \"%s\"\n"
        "    upstream_single_response: \"%s\"\n"
        "    upstream_chain_response: \"%s\"\n"
        "    upstream_file_hashes: \"%s\"\n"
        "numeric_policy:\n"
        "  tolerances:\n"
        "    cross_channel_qE_distribution_absolute: \"1e-15（q_E,G,Z_0,Z_1,reach）\"\n"
        "    cross_channel_kernel_alpha_beta_absolute: \"5e-11\"\n"
        "    cross_channel_e_max_absolute: \"5e-12\"\n"
        "    cross_channel_aggregate_absolute: \"1e-9\"\n"
        "    conservation_absolute: \"1e-15\"\n"
        "    cross_route_absolute: \"1e-15\"\n"
        "    E2_independent_residual_absolute: \"2e-12\"\n"
        "  serialization:\n"
        "    significant_decimal_digits: 17\n"
    ) % (version, p, schema_hash, "0" * 64, upstream_hash, upstream_hash, "0" * 64)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(doc)


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _scenario_inputs(scenario):
    """(parameters values, semantics) for a synthetic CLI scenario.

    The parameter values mirror the E2_embedded_oracles inputs so the
    response and the independent recomputation share the same bindings.
    """
    o1 = {
        "P026": "0.25", "P027": "0.25", "P028": "0.25", "P029": "0.25",
        "P030": "0", "P031": "0", "P032": "0", "P033": "0", "P037": "100",
    }
    o5 = {
        "P026": "0.125", "P027": "0.125", "P028": "0.125", "P029": "0.125",
        "P030": "0", "P031": "0", "P032": "0", "P033": "0.25", "P037": "100",
    }
    half = {
        "P026": "0.5", "P027": "0.5", "P028": "0.5", "P029": "0.5",
        "P030": "0.5", "P031": "0.5", "P032": "0.5", "P033": "0.5", "P037": "100",
    }
    zero = {
        "P026": "0", "P027": "0", "P028": "0", "P029": "0",
        "P030": "0", "P031": "0", "P032": "0", "P033": "0", "P037": "100",
    }
    if scenario == "o5":
        return o5, chk.SEMANTICS_SINGLE
    if scenario in ("o3", "o3c"):
        return half, (chk.SEMANTICS_CHAIN if scenario == "o3c" else chk.SEMANTICS_SINGLE)
    if scenario == "zero_qe":
        return zero, chk.SEMANTICS_SINGLE
    if scenario == "o1c":
        return o1, chk.SEMANTICS_CHAIN
    return o1, chk.SEMANTICS_SINGLE


def _pub_scalar(x):
    """Fraction or Decimal -> 17-significant-digit public decimal string."""
    if isinstance(x, Fraction):
        return chk.to_public(Decimal(x.numerator) / Decimal(x.denominator))
    return chk.to_public(Decimal(x))


def _scenario_compute(scenario):
    """Independent recomputation of the scenario values (the checker's own
    math path; Fraction for the rational single cases, Decimal for the chain
    semantics which requires Decimal arithmetic for e>0)."""
    params, sem = _scenario_inputs(scenario)
    Num = Decimal if sem == chk.SEMANTICS_CHAIN else Fraction
    values = [Decimal(v) if Num is Decimal else fr(v) for v in (
        params["P026"], params["P027"], params["P028"], params["P029"],
        params["P030"], params["P031"], params["P032"], params["P033"])]
    res = chk.compute_independent_full(
        sem, values[0], values[1], values[2], values[3],
        values[4], values[5], values[6], values[7], Num=Num)
    return sem, params, res


def _make_response(path, run_id=RUN_ID, tamper_q_e=None, scenario="o1",
                   mutate=None):
    """Write a synthetic canonical q1_response for a CLI scenario.

    ``scenario`` selects the parameter/response values: o1 / o1c non-NA full
    chain, o5 NA branch (beta_E=1), o3 / o3c E infeasible, zero_qe (q_E == 0,
    emitted with the legal zero lexical form "0.000000").  ``mutate`` is an
    optional in-place document mutator used by the negative tests.  For
    standard_chain_v1 the response omits ``E_kernel.e_max_E`` per the frozen
    V1.0.4 contract (E1 omits the key; E2 emits NOT_APPLICABLE).
    """
    sem, params, res = _scenario_compute(scenario)
    pub = _pub_scalar
    na = res["lambda"]["na"] if res["lambda"] is not None else False
    tilde_na = (res["lambda"] is not None and res["lambda"]["tilde"]["A"] is None)
    e_infeasible = res["overall_status"] == "HAS_INFEASIBLE"

    def kern_item(pid, idx):
        k = res["abc_kernels"][idx]
        return {
            "process_id": pid,
            "q": params["P02%d" % (6 + idx)],
            "e": params["P03%d" % idx],
            "alpha": None if k["alpha"] is None else pub(k["alpha"]),
            "beta": None if k["beta"] is None else pub(k["beta"]),
            "status": k["status"],
            "free_parameters": list(k["free_parameters"]),
            "source": "upstream_bound",
        }

    def e_kernel_block(ek):
        block = {
            "status": ek["status"],
            "alpha_E": None if ek["alpha"] is None else pub(ek["alpha"]),
            "beta_E": None if ek["beta"] is None else pub(ek["beta"]),
            "free_parameters": list(ek["free_parameters"]),
            "diagnostics": {"method": ek["method"], "feasibility": ek["feasibility"],
                            "notes": ["synthetic"]},
        }
        if sem == chk.SEMANTICS_SINGLE:
            block["e_max_E"] = pub(ek["e_max"])
        return block

    doc = {
        "schema_version": "q1_quality_v1",
        "envelope_type": "q1_response",
        "request_id": "%s:%s" % (run_id, sem),
        "scenario_role": "canonical_g2_02",
        "semantics": sem,
        "overall_status": res["overall_status"],
        "abc_kernels": [kern_item("A", 0), kern_item("B", 1), kern_item("C", 2)],
        "diagnostics": {"notes": ["synthetic response for unit tests"]},
    }
    if e_infeasible:
        doc["infeasible_stage"] = res["infeasible_stage"]
        doc["q_E"] = pub(res["q_E"])
        doc["G"] = pub(res["G"])
        doc["Z_0"] = pub(res["Z_0"])
        doc["Z_1"] = pub(res["Z_1"])
        doc["reach_E_distribution"] = [pub(x) for x in res["reach_E_distribution"]]
        doc["E_kernel"] = e_kernel_block(res["E_kernel"])
        for null_field in ("E_rates", "fourfold", "anchors", "lambda",
                           "multinomial", "route_agreement"):
            doc[null_field] = None
    else:
        doc["q_E"] = ("0.000000" if scenario == "zero_qe"
                      else (pub(res["q_E"]) if tamper_q_e is None else tamper_q_e))
        doc["G"] = pub(res["G"])
        doc["Z_0"] = pub(res["Z_0"])
        doc["Z_1"] = pub(res["Z_1"])
        doc["reach_E_distribution"] = [pub(x) for x in res["reach_E_distribution"]]
        doc["E_kernel"] = e_kernel_block(res["E_kernel"])
        er = res["E_rates"]
        doc["E_rates"] = {k: pub(v) for k, v in er.items()}
        four = res["fourfold"]
        four_pub = {k: pub(v) for k, v in four.items()}
        per_route = {"closed_form": four_pub, "enumeration": four_pub,
                     "absorption_chain": four_pub}
        doc["fourfold"] = dict(four_pub, sum="1", per_route=per_route,
                               max_abs_deviation="0")
        an = res["anchors"]
        doc["anchors"] = {k: pub(v) for k, v in an.items()}
        lam = res["lambda"]
        doc["lambda"] = {
            "main": {m: (None if lam["main"][m] is None else pub(lam["main"][m]))
                     for m in "ABCD"},
            "sum": None if lam["sum"] is None else pub(lam["sum"]),
            "counts": {k: pub(v) for k, v in lam["counts"].items()},
            "tilde": {m: (None if lam["tilde"][m] is None else pub(lam["tilde"][m]))
                      for m in "ABCD"},
            "na": bool(lam["na"]),
            "max_abs_deviation": None if na else "0",
        }
        doc["multinomial"] = {"N": 100,
                              "p": [pub(x) for x in res["multinomial"]["p"]]}
        ra = {k: "0" for k in ("q_E", "G", "Z_0", "Z_1", "p_GP", "p_BP",
                               "p_GE", "p_BE")}
        for m in "ABCD":
            ra["lambda_%s" % m] = None if na else "0"
            ra["tilde_%s" % m] = None if tilde_na else "0"
        doc["route_agreement"] = ra
    if mutate is not None:
        mutate(doc)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(doc, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n")
    return doc


def _make_cli_inputs(tmp, tamper_q_e=None, wrong_params_hash=False,
                     scenario="o1", mutate=None):
    params_values, _ = _scenario_inputs(scenario)
    params = os.path.join(tmp, "parameters.csv")
    upstream = os.path.join(tmp, "upstream_response.json")
    schema = os.path.join(tmp, "schema.json")
    task_pkg = os.path.join(tmp, "task_package.yaml")
    response = os.path.join(tmp, "response.json")
    report = os.path.join(tmp, "check_report.json")
    _make_parameters_csv(params, values=params_values)
    with open(upstream, "w", encoding="utf-8") as f:
        f.write("{\"envelope_type\":\"calibration_response\"}\n")
    shutil_copy = __import__("shutil").copyfile
    shutil_copy(REAL_SCHEMA, schema)
    _make_task_package(task_pkg, _sha(params), _sha(upstream), _sha(schema),
                       wrong_params=wrong_params_hash)
    _make_response(response, tamper_q_e=tamper_q_e, scenario=scenario,
                   mutate=mutate)
    return params, upstream, schema, task_pkg, response, report


def _cli_argv(response, params, upstream, schema, task_pkg, report):
    return [
        "--response", response,
        "--parameters", params,
        "--upstream", upstream,
        "--schema", schema,
        "--task-package", task_pkg,
        "--report", report,
    ]


class CliContractTests(unittest.TestCase):
    def test_full_pass(self):
        with tempfile.TemporaryDirectory(prefix="e2_cli_pass_") as tmp:
            params, upstream, schema, task_pkg, response, report = _make_cli_inputs(tmp)
            code = chk.main(_cli_argv(response, params, upstream, schema, task_pkg, report))
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(report))
            with open(report, "r", encoding="utf-8") as f:
                rep = json.load(f)
            self.assertEqual(rep["checker_status"], "PASS")
            self.assertEqual(rep["envelope_type"], "q1_check_report")
            self.assertEqual(rep["report_context_run_id"], RUN_ID)
            self.assertEqual(rep["semantics"], "single_test_unconditional_v1")
            self.assertEqual(rep["frozen_input_hashes"]["parameters_sha256"], _sha(params))
            self.assertEqual(rep["frozen_input_hashes"]["upstream_sha256"], _sha(upstream))
            self.assertEqual(rep["route_table_verdict"], "PASS")
            self.assertEqual(rep["errors"], [])
            self.assertIsNotNone(rep["E_kernel_independent"])
            q = [it for it in rep["items"] if it["quantity"] == "q_E"][0]
            self.assertEqual(q["verdict"], "PASS")

    def test_tampered_response_fails(self):
        with tempfile.TemporaryDirectory(prefix="e2_cli_fail_") as tmp:
            params, upstream, schema, task_pkg, response, report = _make_cli_inputs(
                tmp, tamper_q_e="0.26")
            code = chk.main(_cli_argv(response, params, upstream, schema, task_pkg, report))
            self.assertEqual(code, 1)
            with open(report, "r", encoding="utf-8") as f:
                rep = json.load(f)
            self.assertEqual(rep["checker_status"], "FAIL")
            q = [it for it in rep["items"] if it["quantity"] == "q_E"][0]
            self.assertEqual(q["verdict"], "FAIL")

    def test_wrong_frozen_params_hash_validation_error(self):
        with tempfile.TemporaryDirectory(prefix="e2_cli_hash_") as tmp:
            params, upstream, schema, task_pkg, response, report = _make_cli_inputs(
                tmp, wrong_params_hash=True)
            code = chk.main(_cli_argv(response, params, upstream, schema, task_pkg, report))
            self.assertEqual(code, 2)
            self.assertTrue(os.path.isfile(report))
            with open(report, "r", encoding="utf-8") as f:
                rep = json.load(f)
            self.assertEqual(rep["checker_status"], "FAIL")
            self.assertTrue(rep["errors"])
            self.assertEqual(rep["report_context_run_id"], RUN_ID)

    def test_cli_rejects_request_option(self):
        argv = ["--request", "somewhere/request.json"] + _cli_argv(
            "r.json", "p.csv", "u.json", "s.json", "t.yaml", "out.json")
        code = chk.main(argv)
        self.assertEqual(code, 2)

    def test_preflight_sentinel_untouched(self):
        with tempfile.TemporaryDirectory(prefix="e2_preflight_") as tmp:
            params, upstream, schema, task_pkg, response, report = _make_cli_inputs(tmp)
            # malformed request_id (invalid run_id prefix)
            _make_response(response, run_id="NOT_A_RUN_ID_abcd1234")
            sentinel = b"PRESERVE-ME"
            with open(report, "wb") as f:
                f.write(sentinel)
            code = chk.main(_cli_argv(response, params, upstream, schema, task_pkg, report))
            self.assertEqual(code, 2)
            with open(report, "rb") as f:
                self.assertEqual(f.read(), sentinel)

    def test_preflight_no_report_created(self):
        with tempfile.TemporaryDirectory(prefix="e2_preflight2_") as tmp:
            params, upstream, schema, task_pkg, response, report = _make_cli_inputs(tmp)
            _make_response(response, run_id="NOT_A_RUN_ID_abcd1234")
            code = chk.main(_cli_argv(response, params, upstream, schema, task_pkg, report))
            self.assertEqual(code, 2)
            self.assertFalse(os.path.exists(report))

    def test_preflight_wrong_role(self):
        with tempfile.TemporaryDirectory(prefix="e2_role_") as tmp:
            params, upstream, schema, task_pkg, response, report = _make_cli_inputs(tmp)
            with open(response, "r", encoding="utf-8") as f:
                doc = json.load(f)
            doc["scenario_role"] = "generic"
            with open(response, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            code = chk.main(_cli_argv(response, params, upstream, schema, task_pkg, report))
            self.assertEqual(code, 2)
            self.assertFalse(os.path.exists(report))

    def test_upstream_hash_mismatch_validation_error(self):
        with tempfile.TemporaryDirectory(prefix="e2_up_hash_") as tmp:
            params, upstream, schema, task_pkg, response, report = _make_cli_inputs(tmp)
            with open(upstream, "w", encoding="utf-8") as f:
                f.write("{\"tampered\":true}\n")  # changes the upstream hash
            code = chk.main(_cli_argv(response, params, upstream, schema, task_pkg, report))
            self.assertEqual(code, 2)
            self.assertTrue(os.path.isfile(report))

    def test_stale_v103_task_package_validation_error(self):
        """V1.0.4 strict version binding at the CLI: a V1.0.3 task package is
        refused with exit 2 and a VALIDATION_ERROR report (no active V1.0.3
        binding survives the rebind)."""
        with tempfile.TemporaryDirectory(prefix="e2_version_") as tmp:
            params, upstream, schema, task_pkg, response, report = _make_cli_inputs(tmp)
            _make_task_package(task_pkg, _sha(params), _sha(upstream), _sha(schema),
                               version="G2-02-SPEC-V1.0.3")
            code = chk.main(_cli_argv(response, params, upstream, schema, task_pkg, report))
            self.assertEqual(code, 2)
            self.assertTrue(os.path.isfile(report))
            with open(report, "r", encoding="utf-8") as f:
                rep = json.load(f)
            self.assertEqual(rep["checker_status"], "FAIL")
            self.assertEqual(rep["report_context_run_id"], RUN_ID)
            self.assertTrue(any("task_package_version" in e for e in rep["errors"]),
                            "expected a task_package_version error, got %r" % rep["errors"])


class NaNullContractTests(unittest.TestCase):
    """V1.0.4 NA/null contract: when lambda.na=true the main A/B/C/D leaves,
    sum, max_abs_deviation and route_agreement.lambda_A..D must all be null
    (a numeric "0" or any other number must FAIL); tilde A/B/C/D and
    route_agreement.tilde_A..D must be null when q_E == 0 and numeric when
    q_E > 0.  No tilde_na boolean is introduced."""

    def _run(self, scenario="o1", mutate=None):
        with tempfile.TemporaryDirectory(prefix="e2_na_") as tmp:
            params, upstream, schema, task_pkg, response, report = \
                _make_cli_inputs(tmp, scenario=scenario, mutate=mutate)
            code = chk.main(_cli_argv(response, params, upstream, schema,
                                      task_pkg, report))
            with open(report, "r", encoding="utf-8") as f:
                rep = json.load(f)
            return code, rep

    def _items(self, rep):
        return {it["quantity"]: it for it in rep["items"]}

    def test_o5_na_contract_pass(self):
        """O5-style NA response (beta_E=1, q_E>0): main/sum/max_abs_deviation
        and route_agreement.lambda_* null; tilde numeric -> PASS."""
        code, rep = self._run(scenario="o5")
        self.assertEqual(code, 0)
        self.assertEqual(rep["checker_status"], "PASS")
        by_q = self._items(rep)
        self.assertEqual(by_q["lambda.na"]["verdict"], "PASS")
        self.assertEqual(by_q["lambda.sum"]["verdict"], "PASS")
        self.assertEqual(by_q["lambda.max_abs_deviation"]["verdict"], "PASS")
        for m in "ABCD":
            self.assertEqual(by_q["lambda.main.%s" % m]["verdict"], "PASS")
            self.assertEqual(by_q["route_agreement.lambda_%s" % m]["verdict"], "PASS")
            self.assertEqual(by_q["lambda.tilde.%s" % m]["verdict"], "PASS")
            self.assertEqual(by_q["route_agreement.tilde_%s" % m]["verdict"], "PASS")

    def test_na_true_but_main_numeric_fails(self):
        code, rep = self._run(scenario="o5",
                              mutate=lambda d: d["lambda"]["main"].update({"A": "0.5"}))
        self.assertEqual(code, 1)
        self.assertEqual(rep["checker_status"], "FAIL")
        self.assertEqual(self._items(rep)["lambda.main.A"]["verdict"], "FAIL")

    def test_na_true_but_sum_zero_fails(self):
        code, rep = self._run(scenario="o5",
                              mutate=lambda d: d["lambda"].update({"sum": "0"}))
        self.assertEqual(code, 1)
        self.assertEqual(rep["checker_status"], "FAIL")
        self.assertEqual(self._items(rep)["lambda.sum"]["verdict"], "FAIL")

    def test_na_true_but_max_abs_deviation_numeric_fails(self):
        code, rep = self._run(scenario="o5",
                              mutate=lambda d: d["lambda"].update({"max_abs_deviation": "0"}))
        self.assertEqual(code, 1)
        self.assertEqual(rep["checker_status"], "FAIL")
        self.assertEqual(self._items(rep)["lambda.max_abs_deviation"]["verdict"], "FAIL")

    def test_na_true_but_route_lambda_numeric_fails(self):
        code, rep = self._run(scenario="o5",
                              mutate=lambda d: d["route_agreement"].update({"lambda_A": "0"}))
        self.assertEqual(code, 1)
        self.assertEqual(rep["checker_status"], "FAIL")
        self.assertEqual(self._items(rep)["route_agreement.lambda_A"]["verdict"], "FAIL")

    def test_qe_zero_tilde_null_contract_pass(self):
        """q_E == 0 (legal zero lexical form "0.000000"): tilde and
        route_agreement.tilde_* must be null -> PASS (main lambda NA too)."""
        code, rep = self._run(scenario="zero_qe")
        self.assertEqual(code, 0)
        self.assertEqual(rep["checker_status"], "PASS")
        by_q = self._items(rep)
        for m in "ABCD":
            self.assertEqual(by_q["lambda.tilde.%s" % m]["verdict"], "PASS")
            self.assertEqual(by_q["route_agreement.tilde_%s" % m]["verdict"], "PASS")
            self.assertEqual(by_q["lambda.main.%s" % m]["verdict"], "PASS")

    def test_qe_zero_but_tilde_numeric_fails(self):
        code, rep = self._run(scenario="zero_qe",
                              mutate=lambda d: d["lambda"]["tilde"].update({"A": "0.5"}))
        self.assertEqual(code, 1)
        self.assertEqual(rep["checker_status"], "FAIL")
        self.assertEqual(self._items(rep)["lambda.tilde.A"]["verdict"], "FAIL")

    def test_qe_positive_but_tilde_null_fails(self):
        code, rep = self._run(scenario="o1",
                              mutate=lambda d: d["lambda"]["tilde"].update({"A": None}))
        self.assertEqual(code, 1)
        self.assertEqual(rep["checker_status"], "FAIL")
        self.assertEqual(self._items(rep)["lambda.tilde.A"]["verdict"], "FAIL")


class EmaxSemanticGateTests(unittest.TestCase):
    """V1.0.4 e_max_E semantic gate: single_test_unconditional_v1 keeps the
    numeric e_max_E assertion; standard_chain_v1 emits NOT_APPLICABLE and a
    chain response that omits e_max_E must NOT fail."""

    def _run(self, scenario="o1", mutate=None):
        with tempfile.TemporaryDirectory(prefix="e2_emax_") as tmp:
            params, upstream, schema, task_pkg, response, report = \
                _make_cli_inputs(tmp, scenario=scenario, mutate=mutate)
            code = chk.main(_cli_argv(response, params, upstream, schema,
                                      task_pkg, report))
            with open(report, "r", encoding="utf-8") as f:
                rep = json.load(f)
            return code, rep

    def _items(self, rep):
        return {it["quantity"]: it for it in rep["items"]}

    def test_chain_omitted_e_max_passes(self):
        """standard_chain_v1 response without E_kernel.e_max_E -> PASS with a
        NOT_APPLICABLE item (no numeric consistency assertion)."""
        code, rep = self._run(scenario="o1c")
        self.assertEqual(code, 0)
        self.assertEqual(rep["checker_status"], "PASS")
        item = self._items(rep)["E_kernel.e_max_E"]
        self.assertEqual(item["verdict"], "NOT_APPLICABLE")
        self.assertIsNone(item["response_value"])

    def test_chain_e_infeasible_omitted_e_max_passes(self):
        """standard_chain_v1 E INFEASIBLE response without e_max_E -> PASS."""
        code, rep = self._run(scenario="o3c")
        self.assertEqual(code, 0)
        self.assertEqual(rep["checker_status"], "PASS")

    def test_single_wrong_e_max_fails(self):
        """single_test_unconditional_v1 with a wrong E_kernel.e_max_E -> FAIL."""
        code, rep = self._run(scenario="o1",
                              mutate=lambda d: d["E_kernel"].update({"e_max_E": "0.3"}))
        self.assertEqual(code, 1)
        self.assertEqual(rep["checker_status"], "FAIL")
        self.assertEqual(self._items(rep)["E_kernel.e_max_E"]["verdict"], "FAIL")

    def test_single_e_infeasible_e_max_asserted(self):
        """single E INFEASIBLE keeps the numeric e_max_E assertion (O3 pins
        e_max_E = 1/8) -> PASS."""
        code, rep = self._run(scenario="o3")
        self.assertEqual(code, 0)
        self.assertEqual(rep["checker_status"], "PASS")
        self.assertEqual(self._items(rep)["E_kernel.e_max_E"]["verdict"], "PASS")


class SerializationTests(unittest.TestCase):
    def test_to_public(self):
        cases = {
            "0.015612642053572192": "0.015612642053572192",
            "0.31640625": "0.31640625",
            "1": "1",
            "2": "2",
            "0": "0",
            "-0": "0",
            "0.00000000000000000053": "0.00000000000000000053",
            "0.5": "0.5",
            "100": "100",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(chk.to_public(Decimal(raw)), expected)

    def test_parse_finite_decimal_rejects_exponent(self):
        for bad in ("1e-5", "1E5", "NaN", "Infinity"):
            with self.subTest(bad=bad):
                with self.assertRaises(chk.CheckerValidationError):
                    chk.parse_finite_decimal(bad)


class YamlParserTests(unittest.TestCase):
    def test_parse_real_task_package(self):
        tp_path = os.path.join(PROJECT_ROOT, "08_项目管理", "任务包",
                               "G2-02_Q1概率与质量解析链.yaml")
        self.assertTrue(os.path.isfile(tp_path))
        tp = chk.load_task_package(tp_path)
        # formal spec binding: the checker is bound to the frozen V1.0.5
        # (V1.0.5 = provenance-clean upstream rebind only; strict equality)
        self.assertEqual(tp["task_package_version"], "G2-02-SPEC-V1.0.5")
        self.assertEqual(
            tp["frozen_sha256"]["parameters_csv"],
            "0461da2e0de09090673192d9eb0fde6fe5e70b1d22ef61fe13cdb878c449f07e")
        self.assertEqual(
            tp["frozen_sha256"]["upstream_single_response"],
            "afc6f8b20635af3a6414ff41f5d2a86c39892103c272d603e557817b5db993c7")
        self.assertEqual(tp["significant_decimal_digits"], 17)
        # tolerance entries carry trailing commentary; the numeric token leads
        self.assertEqual(chk._tol_value(tp["tolerances"]["cross_channel_qE_distribution_absolute"]),
                         "1e-15")
        self.assertEqual(chk._tol_value(tp["tolerances"]["cross_channel_kernel_alpha_beta_absolute"]),
                         "5e-11")

    def test_stale_v103_task_package_rejected(self):
        """V1.0.5 strict version binding: a task package still bound to the
        previous active spec G2-02-SPEC-V1.0.3 must be refused; the real
        V1.0.5 package is the only accepted version (no startswith /
        multi-version acceptance)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "task_package.yaml")
            _make_task_package(path, "0" * 64, "0" * 64, "0" * 64,
                               version="G2-02-SPEC-V1.0.3")
            with self.assertRaises(chk.CheckerValidationError):
                chk.load_task_package(path)

    def test_v105_task_package_accepted(self):
        """The current frozen G2-02-SPEC-V1.0.5 package loads cleanly."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "task_package.yaml")
            _make_task_package(path, "0" * 64, "0" * 64, "0" * 64,
                               version="G2-02-SPEC-V1.0.5")
            tp = chk.load_task_package(path)
            self.assertEqual(tp["task_package_version"], "G2-02-SPEC-V1.0.5")


class ParametersTests(unittest.TestCase):
    def test_real_parameters_parse(self):
        p = chk.load_parameters(os.path.join(PROJECT_ROOT, "02_数据", "parameters.csv"))
        self.assertEqual(p["q_a"], Decimal("0.025"))
        self.assertEqual(p["q_d"], Decimal("0.001"))
        self.assertEqual(p["e_e"], Decimal("0.02"))
        self.assertEqual(p["N_2"], 100)

    def test_duplicate_parameter_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "parameters.csv")
            _make_parameters_csv(path)
            with open(path, "a", encoding="utf-8") as f:
                f.write("P026,x,x,x,0.5,x,1,x,x,[0,1],x,x\n")
            with self.assertRaises(chk.CheckerValidationError):
                chk.load_parameters(path)

    def test_domain_violation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "parameters.csv")
            _make_parameters_csv(path, values={
                "P026": "1.5", "P027": "0.25", "P028": "0.25", "P029": "0.25",
                "P030": "0", "P031": "0", "P032": "0", "P033": "0", "P037": "100"})
            with self.assertRaises(chk.CheckerValidationError):
                chk.load_parameters(path)


if __name__ == "__main__":
    unittest.main()
