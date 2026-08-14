"""Unit tests for the G2-02 E1 Q1 chain (q1_quality_v1 orchestrator + three routes).

Covers: all frozen fixture cases (q1_quality_oracles_v1.json) under both observation
semantics, the O5 device_total_exit = 1401/4096 correction, three-route agreement,
canonical bound_frozen runs on the real G2-01 upstream files, CLI validation/error
behaviors, upstream hash mismatch, infeasible/NA behaviors, route-mismatch and
numerical-failure paths, negative-zero normalization, and route-file independence.
Python standard library only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
PROJECT = BASE  # 模拟赛_研究生A题
CODE_DIR = BASE / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR), str(PROJECT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import q1_quality_v1 as q1  # noqa: E402

PARAMS = str(PROJECT / "02_数据/parameters.csv")
SCHEMA = str(CODE_DIR / "src/schemas/q1_quality_v1.schema.json")
FIXTURE = str(CODE_DIR / "tests/fixtures/q1_quality_oracles_v1.json")
UPSTREAM_ROOT = PROJECT / "05_结果/G2/run_20260813T134251279572Z_f1290916"
UP_SINGLE = str(UPSTREAM_ROOT / "single_test_unconditional_v1/response.json")
UP_CHAIN = str(UPSTREAM_ROOT / "standard_chain_v1/response.json")

FROZEN_FIXTURE_SHA256 = "13efa773aaa2b057be33d2c511e4bc4be078a6817d47e2dc09aad9da2db5fb0f"
FROZEN_SCHEMA_SHA256 = "0bb93b122572b85833c539bc6f2bee273e04a6c0984933aafa5ed6d3e66dec4d"
FROZEN_SPEC_VERSION = "G2-02-SPEC-V1.0.3"
FROZEN_UP_SINGLE_SHA256 = "355af00ce77791208af17303912ed5972619ad89116f3d0d05f46494d534d0ea"
FROZEN_UP_CHAIN_SHA256 = "e71473ce391da82d7711ceff872b031ec307aa6d8e524f3ff1cd5c5a440542fd"
TOL = Decimal("1e-15")


def sha256_text(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def as_fraction(expected: str) -> Fraction:
    return Fraction(expected)


def assert_fraction_equal(test: unittest.TestCase, expected: str, actual: str | None,
                          tolerance: Decimal = TOL) -> None:
    test.assertIsNotNone(actual, "expected a value but got null/absent")
    expected_value = as_fraction(expected)
    actual_value = Decimal(actual)
    deviation = abs(actual_value - Decimal(expected_value.numerator) / Decimal(expected_value.denominator))
    test.assertLessEqual(deviation, tolerance,
                         f"expected {expected} ({expected_value}) but got {actual}")


def make_derive_request(values: dict[str, str], semantics: str,
                        scenario_role: str = "test_oracle") -> dict:
    return {
        "schema_version": "q1_quality_v1",
        "envelope_type": "q1_request",
        "request_id": "test:" + semantics,
        "scenario_role": scenario_role,
        "semantics": semantics,
        "upstream": {
            "mode": "derive_from_values",
            "values": {
                "q_a": values["q_a"], "q_b": values["q_b"], "q_c": values["q_c"],
                "q_d": values["q_d"], "e_a": values["e_a"], "e_b": values["e_b"],
                "e_c": values["e_c"], "e_e": values["e_e"],
            },
        },
    }


class Q1ChainTestCase(unittest.TestCase):
    """Base: shared tempdir, request/response paths, schema root."""

    tempdir: tempfile.TemporaryDirectory
    tmp: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory(prefix="q1_main_test_")
        cls.tmp = cls.tempdir.name
        cls.schema_root = q1._load_json(SCHEMA)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tempdir.cleanup()

    def _paths(self, name: str) -> tuple[str, str]:
        return os.path.join(self.tmp, f"{name}_request.json"), os.path.join(self.tmp, f"{name}_response.json")

    def _run(self, name: str, request: dict, upstream: str | None = None,
             params: str = PARAMS) -> tuple[int, dict | None]:
        request_path, response_path = self._paths(name)
        with open(request_path, "w", encoding="utf-8") as handle:
            json.dump(request, handle)
        argv = [
            "--request", request_path,
            "--parameters", params,
            "--upstream", upstream if upstream is not None else request_path,
            "--schema", SCHEMA,
            "--output", response_path,
        ]
        code = q1.main(argv)
        response = None
        if os.path.exists(response_path):
            with open(response_path, "r", encoding="utf-8") as handle:
                response = json.load(handle)
        return code, response

    def assert_response_valid(self, response: dict) -> None:
        q1._validate_response(response, self.schema_root)

    def assert_three_route_agreement(self, response: dict) -> None:
        self.assertIn("route_agreement", response)
        self.assertIn("fourfold", response)
        per_route = response["fourfold"]["per_route"]
        self.assertEqual(sorted(per_route), ["absorption_chain", "closed_form", "enumeration"])
        for route in ("closed_form", "enumeration", "absorption_chain"):
            for key in ("p_GP", "p_BP", "p_GE", "p_BE"):
                public = Decimal(response["fourfold"][key])
                route_value = Decimal(per_route[route][key])
                self.assertLessEqual(abs(public - route_value), TOL,
                                     f"{route}.{key} deviates from public fourfold")
        # Approved L3 ruling: route_agreement's 16 fields are the PER-QUANTITY
        # maximum absolute pairwise deviation across the three routes, never the
        # quantity values.  q_E/G/Z_0/Z_1/p_* are deviations; lambda_* is the
        # deviation of the lambda main leaves (null iff lambda.na); tilde_* is
        # the deviation of the tilde leaves (null iff q_E is a mathematical zero).
        for key in ("q_E", "G", "Z_0", "Z_1"):
            deviation = Decimal(response["route_agreement"][key])
            self.assertGreaterEqual(deviation, Decimal(0))
            self.assertLessEqual(deviation, TOL, f"route_agreement.{key} exceeds tolerance")
            if response[key] != "0":
                self.assertNotEqual(response["route_agreement"][key], response[key],
                                    f"route_agreement.{key} must be a deviation, not the quantity")
        for key in ("p_GP", "p_BP", "p_GE", "p_BE"):
            deviation = Decimal(response["route_agreement"][key])
            self.assertGreaterEqual(deviation, Decimal(0))
            self.assertLessEqual(deviation, TOL, f"route_agreement.{key} exceeds tolerance")
            if response["fourfold"][key] != "0":
                self.assertNotEqual(response["route_agreement"][key], response["fourfold"][key],
                                    f"route_agreement.{key} must be a deviation, not the quantity")
            # Cross-check the per-quantity deviation against the per-route public
            # fourfold table within tolerance.
            route_values = [Decimal(per_route[route][key])
                            for route in ("closed_form", "enumeration", "absorption_chain")]
            self.assertLessEqual(abs(deviation - q1._pairwise_max_abs_deviation(route_values)),
                                 TOL, f"route_agreement.{key} inconsistent with per_route fourfold")
        # V1.0.3 NA/null contract on route_agreement (unchanged):
        # lambda_* null iff lambda.na; tilde_* null iff q_E is a mathematical zero.
        if response["lambda"]["na"]:
            for key in ("lambda_A", "lambda_B", "lambda_C", "lambda_D"):
                self.assertIsNone(response["route_agreement"][key],
                                  f"NA route_agreement.{key} must be null")
        else:
            for key, leaf in (("lambda_A", "A"), ("lambda_B", "B"),
                              ("lambda_C", "C"), ("lambda_D", "D")):
                deviation = Decimal(response["route_agreement"][key])
                self.assertGreaterEqual(deviation, Decimal(0))
                self.assertLessEqual(deviation, TOL, f"route_agreement.{key} exceeds tolerance")
                if response["lambda"]["main"][leaf] != "0":
                    self.assertNotEqual(response["route_agreement"][key],
                                        response["lambda"]["main"][leaf],
                                        f"route_agreement.{key} must be a deviation, not the quantity")
        q_e_zero = response["q_E"] == "0"
        for key, leaf in (("tilde_A", "A"), ("tilde_B", "B"),
                          ("tilde_C", "C"), ("tilde_D", "D")):
            if q_e_zero:
                self.assertIsNone(response["route_agreement"][key],
                                  f"q_E=0 route_agreement.{key} must be null")
            else:
                deviation = Decimal(response["route_agreement"][key])
                self.assertGreaterEqual(deviation, Decimal(0))
                self.assertLessEqual(deviation, TOL, f"route_agreement.{key} exceeds tolerance")
                if response["lambda"]["tilde"][leaf] != "0":
                    self.assertNotEqual(response["route_agreement"][key],
                                        response["lambda"]["tilde"][leaf],
                                        f"route_agreement.{key} must be a deviation, not the quantity")
        # reach_E_distribution sums to 1
        dist_sum = sum((Decimal(v) for v in response["reach_E_distribution"]), Decimal(0))
        self.assertLessEqual(abs(dist_sum - Decimal(1)), TOL, "reach_E_distribution does not sum to 1")
        # fourfold sum
        four_sum = sum((Decimal(response["fourfold"][k]) for k in ("p_GP", "p_BP", "p_GE", "p_BE")), Decimal(0))
        self.assertLessEqual(abs(four_sum - Decimal(1)), TOL, "fourfold does not sum to 1")


class TestFrozenArtifacts(Q1ChainTestCase):
    def test_fixture_hash_matches_frozen_binding(self) -> None:
        self.assertEqual(sha256_text(FIXTURE), FROZEN_FIXTURE_SHA256)

    def test_schema_hash_matches_frozen_binding(self) -> None:
        self.assertEqual(sha256_text(SCHEMA), FROZEN_SCHEMA_SHA256)

    def test_upstream_hashes_match_frozen_binding(self) -> None:
        self.assertEqual(sha256_text(UP_SINGLE), FROZEN_UP_SINGLE_SHA256)
        self.assertEqual(sha256_text(UP_CHAIN), FROZEN_UP_CHAIN_SHA256)

    def test_old_v1_fixture_hash_not_used(self) -> None:
        source = Path(q1.__file__).read_text(encoding="utf-8")
        old_v1_hash = "7f2cd3" + "bc"  # frozen V1.0.0/V1.0.1 fixture binding; must never be referenced
        self.assertNotIn(old_v1_hash, source)

    def test_v103_spec_bindings_in_source(self) -> None:
        code_files = [
            Path(q1.__file__),
            MAIN_MODEL / "q1_routes/closed_form_v1.py",
            MAIN_MODEL / "q1_routes/enumeration_v1.py",
            MAIN_MODEL / "q1_routes/absorption_chain_v1.py",
        ]
        for path in code_files:
            source = path.read_text(encoding="utf-8")
            self.assertIn(FROZEN_SPEC_VERSION, source,
                          f"{path.name} must bind {FROZEN_SPEC_VERSION}")
            for old in ("G2-02-SPEC-V1.0.0", "G2-02-SPEC-V1.0.1", "G2-02-SPEC-V1.0.2"):
                self.assertNotIn(old, source, f"{path.name} must not bind {old}")
        main_source = Path(q1.__file__).read_text(encoding="utf-8")
        self.assertIn(FROZEN_SCHEMA_SHA256, main_source,
                      "main module must bind the frozen schema SHA")
        self.assertIn(FROZEN_FIXTURE_SHA256, main_source,
                      "main module must bind the frozen fixture SHA")
        test_source = Path(__file__).read_text(encoding="utf-8")
        self.assertIn(FROZEN_SPEC_VERSION, test_source,
                      "test module must bind the frozen spec version")


class TestFixtureCases(Q1ChainTestCase):
    def load_fixture(self) -> list[dict]:
        with open(FIXTURE, "r", encoding="utf-8") as handle:
            return json.load(handle)["cases"]

    def assert_kernel_statuses(self, response: dict, expected: dict) -> None:
        actual = {item["process_id"]: item["status"] for item in response["abc_kernels"]}
        self.assertEqual(actual, expected)

    def assert_e_kernel(self, response: dict, expected: dict) -> None:
        actual = response["E_kernel"]
        self.assertEqual(actual["status"], expected["status"])
        self.assertEqual(actual["free_parameters"], expected.get("free_parameters", []))
        if expected.get("alpha_E") is None:
            self.assertNotIn("alpha_E", actual)
        else:
            assert_fraction_equal(self, expected["alpha_E"], actual["alpha_E"])
        if expected.get("beta_E") is None:
            self.assertNotIn("beta_E", actual)
        else:
            assert_fraction_equal(self, expected["beta_E"], actual["beta_E"])
        if expected.get("e_max_E") is None:
            self.assertNotIn("e_max_E", actual)
        else:
            assert_fraction_equal(self, expected["e_max_E"], actual["e_max_E"])

    def assert_rates(self, response: dict, expected: dict) -> None:
        for key in ("first_abnormal", "process_exit", "device_total_exit"):
            assert_fraction_equal(self, expected[key], response["E_rates"][key])

    def assert_fourfold(self, response: dict, expected: dict) -> None:
        for key in ("p_GP", "p_BP", "p_GE", "p_BE"):
            assert_fraction_equal(self, expected[key], response["fourfold"][key])

    def assert_anchors(self, response: dict, expected: dict) -> None:
        for key in ("E_S", "E_PL", "E_PW"):
            assert_fraction_equal(self, expected[key], response["anchors"][key])

    def assert_lambda(self, response: dict, expected: dict) -> None:
        block = response["lambda"]
        self.assertEqual(block["na"], expected["na"])
        # V1.0.3 NA/null contract: na=true => sum and max_abs_deviation are null;
        # na=false => both are numeric decimal strings.
        if expected["na"]:
            self.assertIsNone(block.get("sum"))
            self.assertIsNone(block.get("max_abs_deviation"))
        else:
            self.assertIsInstance(block.get("sum"), str)
            self.assertIsInstance(block.get("max_abs_deviation"), str)
        for key in ("A", "B", "C", "D"):
            if expected["main"][key] is None:
                self.assertIsNone(block["main"][key])
            else:
                assert_fraction_equal(self, expected["main"][key], block["main"][key])
        for key in ("event_level", "first_test_only", "at_most_once_per_device"):
            assert_fraction_equal(self, expected["counts"][key], block["counts"][key])
        for key in ("A", "B", "C", "D"):
            if expected["tilde"][key] is None:
                self.assertIsNone(block["tilde"][key])
            else:
                assert_fraction_equal(self, expected["tilde"][key], block["tilde"][key])

    def run_fixture_case(self, case: dict) -> dict:
        semantics = case["semantics"]
        request = make_derive_request(case["input"], semantics)
        code, response = self._run(case["case_id"], request)
        self.assertEqual(code, 0, f"exit code {code} for {case['case_id']}")
        self.assertIsNotNone(response)
        self.assert_response_valid(response)
        expected = case["expected"]
        self.assertEqual(response["overall_status"], expected["overall_status"])
        self.assert_kernel_statuses(response, expected["upstream_statuses"])
        if expected.get("infeasible_stage") is not None:
            self.assertEqual(response["infeasible_stage"], expected["infeasible_stage"])
        return response

    def test_o1_perfect_symmetric_single(self) -> None:
        case = next(c for c in self.load_fixture() if c["case_id"] == "O1_perfect_symmetric_single")
        response = self.run_fixture_case(case)
        expected = case["expected"]
        assert_fraction_equal(self, expected["q_E"], response["q_E"])
        self.assert_e_kernel(response, expected["E_kernel"])
        self.assert_rates(response, expected["E_rates"])
        self.assert_fourfold(response, expected["fourfold"])
        self.assert_anchors(response, expected["anchors"])
        self.assert_lambda(response, expected["lambda"])
        self.assert_three_route_agreement(response)
        # lambda sum is exactly 1
        self.assertEqual(response["lambda"]["sum"], "1")

    def test_o2_upstream_infeasible_single(self) -> None:
        case = next(c for c in self.load_fixture() if c["case_id"] == "O2_upstream_infeasible_single")
        response = self.run_fixture_case(case)
        self.assertEqual(response["overall_status"], "HAS_INFEASIBLE")
        self.assertEqual(response["infeasible_stage"], "ABC_KERNEL")
        self.assertNotIn("q_E", response)
        self.assertNotIn("E_kernel", response)
        for key in ("E_rates", "fourfold", "anchors", "lambda", "multinomial", "route_agreement"):
            self.assertNotIn(key, response)

    def test_o3_e_infeasible_single(self) -> None:
        case = next(c for c in self.load_fixture() if c["case_id"] == "O3_E_infeasible_single")
        response = self.run_fixture_case(case)
        expected = case["expected"]
        assert_fraction_equal(self, expected["q_E"], response["q_E"])
        self.assert_e_kernel(response, expected["E_kernel"])
        for key in ("E_rates", "fourfold", "anchors", "lambda", "multinomial", "route_agreement"):
            self.assertNotIn(key, response)

    def test_o4_interior_exact_single(self) -> None:
        case = next(c for c in self.load_fixture() if c["case_id"] == "O4_interior_exact_single")
        response = self.run_fixture_case(case)
        expected = case["expected"]
        assert_fraction_equal(self, expected["q_E"], response["q_E"])
        self.assert_e_kernel(response, expected["E_kernel"])
        # Downstream is not frozen for O4: only three-route agreement is verified.
        self.assert_three_route_agreement(response)
        for key in ("E_rates", "fourfold", "anchors", "lambda"):
            self.assertIsNotNone(response[key])

    def test_o5_na_lambda_beta1_single(self) -> None:
        case = next(c for c in self.load_fixture() if c["case_id"] == "O5_NA_lambda_beta1_single")
        response = self.run_fixture_case(case)
        expected = case["expected"]
        assert_fraction_equal(self, expected["q_E"], response["q_E"])
        self.assert_e_kernel(response, expected["E_kernel"])
        self.assert_rates(response, expected["E_rates"])
        self.assert_fourfold(response, expected["fourfold"])
        self.assert_anchors(response, expected["anchors"])
        self.assert_lambda(response, expected["lambda"])
        self.assert_three_route_agreement(response)
        # V1.0.3 NA/null contract: main four leaves, sum and max_abs_deviation are
        # null while tilde stays the mathematically defined numeric values
        # (q_E=1/8 > 0); route_agreement.lambda_* null, route_agreement.tilde_*
        # numeric.
        self.assertTrue(response["lambda"]["na"])
        self.assertIsNone(response["lambda"]["sum"])
        self.assertIsNone(response["lambda"]["max_abs_deviation"])
        for key in ("A", "B", "C", "D"):
            self.assertIsNone(response["lambda"]["main"][key])
            self.assertIsNotNone(response["lambda"]["tilde"][key])
        for key in ("lambda_A", "lambda_B", "lambda_C", "lambda_D"):
            self.assertIsNone(response["route_agreement"][key])
        for key in ("tilde_A", "tilde_B", "tilde_C", "tilde_D"):
            self.assertIsNotNone(response["route_agreement"][key])
        # Strict schema validation of the nullable / if-then contract (zero errors).
        errors = q1._schema_validate(self.schema_root["$defs"]["responseEnvelope"],
                                     response, "response", self.schema_root)
        self.assertEqual(errors, [])
        # The frozen V1.0.2 oracle correction (kept through V1.0.3):
        # device_total_exit = p_GE + p_BE = 1401/4096.
        assert_fraction_equal(self, "1401/4096", response["E_rates"]["device_total_exit"])
        combined = Decimal(response["fourfold"]["p_GE"]) + Decimal(response["fourfold"]["p_BE"])
        self.assertEqual(Decimal(response["E_rates"]["device_total_exit"]), combined)

    def test_o6_defect_concentration_single(self) -> None:
        case = next(c for c in self.load_fixture() if c["case_id"] == "O6_defect_concentration_single")
        response = self.run_fixture_case(case)
        expected = case["expected"]
        assert_fraction_equal(self, expected["q_E"], response["q_E"])
        self.assert_e_kernel(response, expected["E_kernel"])
        self.assert_rates(response, expected["E_rates"])
        self.assert_fourfold(response, expected["fourfold"])
        self.assert_anchors(response, expected["anchors"])
        self.assert_lambda(response, expected["lambda"])
        self.assert_three_route_agreement(response)
        # Upstream NONIDENTIFIABLE kernels with zero weight must be reported exactly.
        kernels = {item["process_id"]: item for item in response["abc_kernels"]}
        self.assertEqual(kernels["B"]["status"], "NONIDENTIFIABLE_FAMILY")
        self.assertEqual(kernels["C"]["status"], "NONIDENTIFIABLE_FAMILY")
        self.assertEqual(kernels["B"]["free_parameters"], ["beta"])
        self.assertEqual(kernels["C"]["free_parameters"], ["beta"])
        self.assertEqual(kernels["B"]["alpha"], "0")
        self.assertNotIn("beta", kernels["B"])

    def test_o1c_perfect_symmetric_chain(self) -> None:
        case = next(c for c in self.load_fixture() if c["case_id"] == "O1c_perfect_symmetric_chain")
        response = self.run_fixture_case(case)
        expected = case["expected"]
        assert_fraction_equal(self, expected["q_E"], response["q_E"])
        self.assert_e_kernel(response, expected["E_kernel"])
        self.assert_rates(response, expected["E_rates"])
        self.assert_fourfold(response, expected["fourfold"])
        self.assert_anchors(response, expected["anchors"])
        self.assert_lambda(response, expected["lambda"])
        self.assert_three_route_agreement(response)

    def test_o2c_upstream_infeasible_chain(self) -> None:
        case = next(c for c in self.load_fixture() if c["case_id"] == "O2c_upstream_infeasible_chain")
        response = self.run_fixture_case(case)
        self.assertEqual(response["overall_status"], "HAS_INFEASIBLE")
        self.assertEqual(response["infeasible_stage"], "ABC_KERNEL")
        self.assertNotIn("q_E", response)

    def test_o3c_e_infeasible_chain(self) -> None:
        case = next(c for c in self.load_fixture() if c["case_id"] == "O3c_E_infeasible_chain")
        response = self.run_fixture_case(case)
        expected = case["expected"]
        assert_fraction_equal(self, expected["q_E"], response["q_E"])
        self.assert_e_kernel(response, expected["E_kernel"])
        for key in ("E_rates", "fourfold", "anchors", "lambda", "multinomial", "route_agreement"):
            self.assertNotIn(key, response)

    def test_o5c_e_infeasible_chain(self) -> None:
        case = next(c for c in self.load_fixture() if c["case_id"] == "O5c_E_infeasible_chain")
        response = self.run_fixture_case(case)
        expected = case["expected"]
        assert_fraction_equal(self, expected["q_E"], response["q_E"])
        self.assert_e_kernel(response, expected["E_kernel"])
        self.assertEqual(response["E_kernel"]["status"], "INFEASIBLE")
        for key in ("E_rates", "fourfold", "anchors", "lambda", "multinomial", "route_agreement"):
            self.assertNotIn(key, response)

    def test_all_fixture_cases_run_exit_zero(self) -> None:
        for case in self.load_fixture():
            with self.subTest(case=case["case_id"]):
                self.run_fixture_case(case)

    def test_all_full_chain_cases_route_agreement_within_tolerance(self) -> None:
        for case in self.load_fixture():
            if case["expected"]["overall_status"] not in ("ALL_ROUTES_AGREE",):
                continue
            with self.subTest(case=case["case_id"]):
                response = self.run_fixture_case(case)
                self.assert_three_route_agreement(response)
                maxdev = Decimal(response["fourfold"]["max_abs_deviation"])
                self.assertLessEqual(maxdev, TOL)
                if response["lambda"]["na"]:
                    # V1.0.3: NA lambda carries no numeric max_abs_deviation.
                    self.assertIsNone(response["lambda"]["max_abs_deviation"])
                else:
                    lambda_maxdev = Decimal(response["lambda"]["max_abs_deviation"])
                    self.assertLessEqual(lambda_maxdev, TOL)


class TestCanonicalRuns(Q1ChainTestCase):
    def make_canonical_request(self, semantics: str) -> dict:
        up_hash = FROZEN_UP_SINGLE_SHA256 if semantics == q1.SINGLE else FROZEN_UP_CHAIN_SHA256
        file_rel = f"05_结果/G2/run_20260813T134251279572Z_f1290916/{semantics}/response.json"
        return {
            "schema_version": "q1_quality_v1",
            "envelope_type": "q1_request",
            "request_id": f"20260813T134251279572Z_f1290916:{semantics}",
            "scenario_role": "canonical_g2_02",
            "semantics": semantics,
            "upstream": {
                "mode": "bound_frozen",
                "reference": {
                    "run_id": "20260813T134251279572Z_f1290916",
                    "file": file_rel,
                    "sha256": up_hash,
                    "semantics_expect": semantics,
                },
            },
        }

    def run_canonical(self, semantics: str) -> dict:
        upstream = UP_SINGLE if semantics == q1.SINGLE else UP_CHAIN
        code, response = self._run(f"canonical_{semantics}", self.make_canonical_request(semantics), upstream=upstream)
        self.assertEqual(code, 0)
        self.assertIsNotNone(response)
        self.assert_response_valid(response)
        self.assertEqual(response["overall_status"], "ALL_ROUTES_AGREE")
        self.assertEqual(response["semantics"], semantics)
        for item in response["abc_kernels"]:
            self.assertEqual(item["status"], "UNIQUE_SOLUTION")
            self.assertEqual(item["source"], "upstream_bound")
            self.assertEqual(item["free_parameters"], [])
        return response

    def test_canonical_single(self) -> None:
        response = self.run_canonical(q1.SINGLE)
        self.assert_three_route_agreement(response)
        # abc kernels must reproduce the frozen upstream public alpha/beta strings.
        with open(UP_SINGLE, "r", encoding="utf-8") as handle:
            upstream = json.load(handle)
        kernels = {item["process_id"]: item for item in response["abc_kernels"]}
        for result in upstream["results"]:
            pid = result["process_id"]
            self.assertEqual(kernels[pid]["alpha"], result["alpha"])
            self.assertEqual(kernels[pid]["beta"], result["beta"])
            self.assertEqual(kernels[pid]["q"], result["q"])
            self.assertEqual(kernels[pid]["e"], result["e"])
        self.assertNotEqual(response["lambda"]["na"], True)

    def test_canonical_chain(self) -> None:
        response = self.run_canonical(q1.CHAIN)
        self.assert_three_route_agreement(response)
        with open(UP_CHAIN, "r", encoding="utf-8") as handle:
            upstream = json.load(handle)
        kernels = {item["process_id"]: item for item in response["abc_kernels"]}
        for result in upstream["results"]:
            pid = result["process_id"]
            self.assertEqual(kernels[pid]["alpha"], result["alpha"])
            self.assertEqual(kernels[pid]["beta"], result["beta"])

    def test_canonical_requires_bound_frozen(self) -> None:
        request = self.make_canonical_request(q1.SINGLE)
        request["upstream"] = {"mode": "derive_from_values", "values": {
            "q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
            "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0",
        }}
        code, response = self._run("canonical_misbound", request, upstream=UP_SINGLE)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_generic_requires_derive(self) -> None:
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        request["scenario_role"] = "generic"
        request["upstream"] = {"mode": "bound_frozen", "reference": {
            "run_id": "20260813T134251279572Z_f1290916",
            "file": "05_结果/G2/run_20260813T134251279572Z_f1290916/single_test_unconditional_v1/response.json",
            "sha256": FROZEN_UP_SINGLE_SHA256,
            "semantics_expect": q1.SINGLE,
        }}
        code, response = self._run("generic_misbound", request, upstream=UP_SINGLE)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_canonical_reference_hash_mismatch(self) -> None:
        request = self.make_canonical_request(q1.SINGLE)
        request["upstream"]["reference"]["sha256"] = "0" * 64
        code, response = self._run("canonical_badhash", request, upstream=UP_SINGLE)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_canonical_semantics_expect_mismatch(self) -> None:
        request = self.make_canonical_request(q1.SINGLE)
        request["upstream"]["reference"]["semantics_expect"] = q1.CHAIN
        code, response = self._run("canonical_badsem", request, upstream=UP_SINGLE)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_upstream_file_tampered_hash_mismatch(self) -> None:
        tampered = os.path.join(self.tmp, "tampered_upstream_single.json")
        with open(UP_SINGLE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        data["overall_status"] = "TAMPERED"
        with open(tampered, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        request = self.make_canonical_request(q1.SINGLE)  # reference carries the frozen hash
        code, response = self._run("canonical_tampered", request, upstream=tampered)
        self.assertEqual(code, 2)
        self.assertIsNone(response)


class TestValidationAndErrorBehavior(Q1ChainTestCase):
    def test_malformed_request_json(self) -> None:
        request_path, response_path = self._paths("malformed")
        with open(request_path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        code = q1.main(["--request", request_path, "--parameters", PARAMS, "--upstream", request_path,
                        "--schema", SCHEMA, "--output", response_path])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(response_path))

    def test_missing_request_field(self) -> None:
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        del request["semantics"]
        code, response = self._run("missing_field", request)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_invalid_semantics(self) -> None:
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        request["semantics"] = "bogus_semantics_v9"
        code, response = self._run("bad_semantics", request)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_invalid_envelope_type(self) -> None:
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        request["envelope_type"] = "q1_response"
        code, response = self._run("bad_envelope", request)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_extra_request_field(self) -> None:
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        request["rogue"] = 1
        code, response = self._run("extra_field", request)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_q_out_of_range(self) -> None:
        request = make_derive_request(
            {"q_a": "1.5", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        code, response = self._run("q_out_of_range", request)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_n_two_must_be_100(self) -> None:
        temp_csv = os.path.join(self.tmp, "bad_n2.csv")
        with open(temp_csv, "w", encoding="utf-8") as handle:
            handle.write("parameter_id,value\nP029,0.001\nP033,0.02\nP037,99\n")
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        code, response = self._run("bad_n2", request, params=temp_csv)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_duplicate_parameter_id(self) -> None:
        temp_csv = os.path.join(self.tmp, "dup_params.csv")
        with open(temp_csv, "w", encoding="utf-8") as handle:
            handle.write("parameter_id,value\nP029,0.001\nP033,0.02\nP037,100\nP037,100\n")
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        code, response = self._run("dup_params", request, params=temp_csv)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_missing_parameter(self) -> None:
        temp_csv = os.path.join(self.tmp, "missing_params.csv")
        with open(temp_csv, "w", encoding="utf-8") as handle:
            handle.write("parameter_id,value\nP029,0.001\nP033,0.02\n")  # P037 missing
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        code, response = self._run("missing_param", request, params=temp_csv)
        self.assertEqual(code, 2)
        self.assertIsNone(response)

    def test_missing_request_file_io_error(self) -> None:
        response_path = os.path.join(self.tmp, "io_response.json")
        code = q1.main(["--request", os.path.join(self.tmp, "no_such_request.json"),
                        "--parameters", PARAMS, "--upstream", UP_SINGLE,
                        "--schema", SCHEMA, "--output", response_path])
        self.assertEqual(code, 4)
        self.assertFalse(os.path.exists(response_path))

    def test_output_path_is_directory_io_error(self) -> None:
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        request_path, _ = self._paths("io_dir")
        with open(request_path, "w", encoding="utf-8") as handle:
            json.dump(request, handle)
        code = q1.main(["--request", request_path, "--parameters", PARAMS, "--upstream", request_path,
                        "--schema", SCHEMA, "--output", self.tmp])
        self.assertEqual(code, 4)

    def test_unknown_cli_option_exits_2(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            q1.main(["--request", "x", "--parameters", "y", "--upstream", "z",
                     "--schema", "w", "--output", "o", "--bogus"])
        self.assertEqual(ctx.exception.code, 2)


class TestRouteMismatchAndNumerical(Q1ChainTestCase):
    def _o1_request(self) -> dict:
        return make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)

    def test_route_mismatch_exit_3_with_full_response(self) -> None:
        original = q1.enumeration_v1.compute_downstream

        def corrupted(abc, q_d, pre, e_kernel, precision=200):
            result = original(abc, q_d, pre, e_kernel, precision)
            result = dict(result)
            result["fourfold"] = dict(result["fourfold"])
            result["fourfold"]["p_GP"] = result["fourfold"]["p_GP"] + Decimal("1e-10")
            return result

        q1.enumeration_v1.compute_downstream = corrupted
        try:
            code, response = self._run("route_mismatch", self._o1_request())
        finally:
            q1.enumeration_v1.compute_downstream = original
        self.assertEqual(code, 3)
        self.assertIsNotNone(response)
        self.assertEqual(response["overall_status"], "ROUTE_MISMATCH")
        self.assert_response_valid(response)
        self.assertIn("route_agreement", response)
        self.assertIn("fourfold", response)

    def test_numerical_failure_exit_3(self) -> None:
        original_solver = q1._solve_e_kernel

        def broken_solver(q_e, e_e, semantics):
            raise q1.NumericalError("injected E kernel failure")

        q1._solve_e_kernel = broken_solver
        try:
            code, response = self._run("numerical_failure", self._o1_request())
        finally:
            q1._solve_e_kernel = original_solver
        self.assertEqual(code, 3)
        self.assertIsNotNone(response)
        self.assertEqual(response["overall_status"], "NUMERICAL_FAILURE")
        self.assert_response_valid(response)


class TestSerialization(Q1ChainTestCase):
    def test_negative_zero_normalized(self) -> None:
        self.assertEqual(q1._plain(Decimal("-0")), "0")
        self.assertEqual(q1._plain(Decimal("-0.0"), 17), "0")
        self.assertEqual(q1._plain(Decimal(0)), "0")

    def test_no_negative_zero_in_serialized_response(self) -> None:
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        request_path, response_path = self._paths("negzero")
        with open(request_path, "w", encoding="utf-8") as handle:
            json.dump(request, handle)
        code = q1.main(["--request", request_path, "--parameters", PARAMS, "--upstream", request_path,
                        "--schema", SCHEMA, "--output", response_path])
        self.assertEqual(code, 0)
        with open(response_path, "r", encoding="utf-8") as handle:
            raw = handle.read()
        self.assertNotIn('"-0', raw)

    def test_serialization_shape(self) -> None:
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        request_path, response_path = self._paths("shape")
        with open(request_path, "w", encoding="utf-8") as handle:
            json.dump(request, handle)
        code = q1.main(["--request", request_path, "--parameters", PARAMS, "--upstream", request_path,
                        "--schema", SCHEMA, "--output", response_path])
        self.assertEqual(code, 0)
        with open(response_path, "r", encoding="utf-8") as handle:
            raw = handle.read()
        self.assertTrue(raw.endswith("\n"), "response must end with a single trailing LF")
        self.assertEqual(raw.count("\n"), 1)
        self.assertIn('"schema_version":"q1_quality_v1"', raw)
        self.assertIn('"envelope_type":"q1_response"', raw)
        # sort_keys + compact separators: no spaces after colons/commas
        self.assertNotIn('": "', raw)

    def test_abc_kernels_ordering_a_b_c(self) -> None:
        request = make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)
        code, response = self._run("ordering", request)
        self.assertEqual(code, 0)
        self.assertEqual([item["process_id"] for item in response["abc_kernels"]], ["A", "B", "C"])
        self.assertEqual(len(response["reach_E_distribution"]), 16)


class TestRouteIndependence(Q1ChainTestCase):
    def test_route_files_do_not_import_each_other(self) -> None:
        routes_dir = MAIN_MODEL / "q1_routes"
        files = {
            "closed_form_v1.py": ("enumeration_v1", "absorption_chain_v1", "observation_calibration"),
            "enumeration_v1.py": ("closed_form_v1", "absorption_chain_v1", "observation_calibration"),
            "absorption_chain_v1.py": ("closed_form_v1", "enumeration_v1", "observation_calibration"),
        }
        for filename, forbidden in files.items():
            with open(routes_dir / filename, "r", encoding="utf-8") as handle:
                source = handle.read()
            for token in forbidden:
                self.assertNotIn(token, source,
                                 f"{filename} must not reference {token}")
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    self.assertNotIn("q1_routes", stripped)
                    self.assertNotIn("observation_calibration", stripped)

    def test_routes_only_use_stdlib(self) -> None:
        import ast
        for filename in ("closed_form_v1.py", "enumeration_v1.py", "absorption_chain_v1.py"):
            with open(MAIN_MODEL / "q1_routes" / filename, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            imports: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or "")
            for module in imports:
                self.assertIn(module, ("decimal", "typing", "__future__"),
                              f"{filename} uses unexpected import: {module}")
                self.assertNotIn(module, ("q1_routes", "observation_calibration", "closed_form_v1",
                                          "enumeration_v1", "absorption_chain_v1"))


class TestQeZeroLexicalAndNaContract(Q1ChainTestCase):
    """V1.0.3 NA/null contract: a mathematical-zero q_E must be recognized in every
    legal lexical zero form of the frozen decimalProbability grammar ("0", "0.0",
    "0.00", "0.000000", ...), and the internal validator must enforce the
    na <-> null equivalence (na=true => main/sum/max_abs_deviation/route_agreement
    lambda all null; q_E=0 => tilde and route_agreement tilde all null)."""

    ZERO_FORMS = ("0", "0.0", "0.00", "0.000000")

    def make_all_zero_request(self) -> dict:
        # q_A=q_B=q_C=q_D=0 with e_E=0 yields Z_1=0 => q_E is a mathematical zero
        # with a fully determinate downstream (E kernel beta_E free but weight 0).
        return make_derive_request(
            {"q_a": "0", "q_b": "0", "q_c": "0", "q_d": "0",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)

    def _all_zero_base(self, name: str) -> dict:
        code, response = self._run(name, self.make_all_zero_request())
        self.assertEqual(code, 0)
        self.assertIsNotNone(response)
        return response

    def test_q_e_zero_natural_chain_full_response(self) -> None:
        response = self._all_zero_base("qe_zero_natural")
        self.assertEqual(response["overall_status"], "ALL_ROUTES_AGREE")
        self.assertEqual(response["q_E"], "0")
        self.assert_three_route_agreement(response)
        block = response["lambda"]
        self.assertTrue(block["na"])
        for key in ("A", "B", "C", "D"):
            self.assertIsNone(block["main"][key])
            self.assertIsNone(block["tilde"][key])
        self.assertIsNone(block["sum"])
        self.assertIsNone(block["max_abs_deviation"])
        for key in ("lambda_A", "lambda_B", "lambda_C", "lambda_D"):
            self.assertIsNone(response["route_agreement"][key])
        for key in ("tilde_A", "tilde_B", "tilde_C", "tilde_D"):
            self.assertIsNone(response["route_agreement"][key])
        # Strict schema validation of the nullable / if-then contract.
        self.assert_response_valid(response)
        errors = q1._schema_validate(self.schema_root["$defs"]["responseEnvelope"],
                                     response, "response", self.schema_root)
        self.assertEqual(errors, [])

    def test_q_e_zero_lexical_forms_tilde_null(self) -> None:
        base = self._all_zero_base("qe_zero_lexical_base")
        for form in self.ZERO_FORMS:
            with self.subTest(q_e=form):
                response = copy.deepcopy(base)
                response["q_E"] = form
                self.assert_response_valid(response)
                for key in ("A", "B", "C", "D"):
                    self.assertIsNone(response["lambda"]["tilde"][key])
                    self.assertIsNone(response["route_agreement"]["tilde_" + key])

    def test_q_e_zero_lexical_forms_reject_numeric_tilde(self) -> None:
        base = self._all_zero_base("qe_zero_lexical_base2")
        for form in self.ZERO_FORMS:
            with self.subTest(q_e=form):
                response = copy.deepcopy(base)
                response["q_E"] = form
                response["lambda"]["tilde"]["A"] = "0.5"
                response["route_agreement"]["tilde_A"] = "0.5"
                with self.assertRaises(q1.ResponseValidationError):
                    self.assert_response_valid(response)

    def test_q_e_positive_tilde_must_be_numeric(self) -> None:
        # O5 has q_E=1/8 > 0 and lambda.na=true: tilde stays numeric; nulling it
        # must be rejected by the validator.
        with open(FIXTURE, "r", encoding="utf-8") as handle:
            fixture = json.load(handle)
        case = next(c for c in fixture["cases"] if c["case_id"] == "O5_NA_lambda_beta1_single")
        code, response = self._run("o5_na_base", make_derive_request(case["input"], case["semantics"]))
        self.assertEqual(code, 0)
        self.assertIsNotNone(response)
        for key in ("A", "B", "C", "D"):
            self.assertIsNotNone(response["lambda"]["tilde"][key])
            self.assertIsNotNone(response["route_agreement"]["tilde_" + key])
        tampered = copy.deepcopy(response)
        tampered["lambda"]["tilde"]["A"] = None
        tampered["route_agreement"]["tilde_A"] = None
        with self.assertRaises(q1.ResponseValidationError):
            self.assert_response_valid(tampered)

    def test_na_consistency_rejects_numeric_lambda_when_na(self) -> None:
        base = self._all_zero_base("na_consistency_base")
        tampered = copy.deepcopy(base)
        tampered["lambda"]["main"]["A"] = "0.5"
        with self.assertRaises(q1.ResponseValidationError):
            self.assert_response_valid(tampered)
        tampered = copy.deepcopy(base)
        tampered["lambda"]["sum"] = "1"
        with self.assertRaises(q1.ResponseValidationError):
            self.assert_response_valid(tampered)
        tampered = copy.deepcopy(base)
        tampered["lambda"]["max_abs_deviation"] = "0"
        with self.assertRaises(q1.ResponseValidationError):
            self.assert_response_valid(tampered)
        tampered = copy.deepcopy(base)
        tampered["route_agreement"]["lambda_A"] = "0.5"
        with self.assertRaises(q1.ResponseValidationError):
            self.assert_response_valid(tampered)

    def test_na_consistency_rejects_null_lambda_when_not_na(self) -> None:
        # O1 is non-NA: null main/sum/max_abs_deviation must be rejected.
        with open(FIXTURE, "r", encoding="utf-8") as handle:
            fixture = json.load(handle)
        case = next(c for c in fixture["cases"] if c["case_id"] == "O1_perfect_symmetric_single")
        code, response = self._run("o1_na_false_base", make_derive_request(case["input"], case["semantics"]))
        self.assertEqual(code, 0)
        self.assertIsNotNone(response)
        self.assertFalse(response["lambda"]["na"])
        for key in ("A", "B", "C", "D"):
            self.assertIsNotNone(response["lambda"]["main"][key])
            self.assertIsNotNone(response["lambda"]["tilde"][key])
            self.assertIsNotNone(response["route_agreement"]["lambda_" + key])
            self.assertIsNotNone(response["route_agreement"]["tilde_" + key])
        self.assertIsInstance(response["lambda"]["sum"], str)
        self.assertIsInstance(response["lambda"]["max_abs_deviation"], str)
        tampered = copy.deepcopy(response)
        tampered["lambda"]["main"]["A"] = None
        with self.assertRaises(q1.ResponseValidationError):
            self.assert_response_valid(tampered)


class TestRouteAgreementDeviationSemantics(Q1ChainTestCase):
    """L3 approved ruling: route_agreement's 16 fields are PER-QUANTITY maximum
    absolute pairwise deviations across the three E1 routes, never quantity
    values; NA rules unchanged (lambda.na=true => lambda_* null; q_E=0 =>
    tilde_* null)."""

    def _o1_request(self) -> dict:
        return make_derive_request(
            {"q_a": "0.25", "q_b": "0.25", "q_c": "0.25", "q_d": "0.25",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE)

    # TEST 1 (semantic lock / regression): q_E != 0 with all three routes
    # agreeing exactly on q_E => response.q_E is the non-"0" quantity while
    # route_agreement.q_E is the deviation "0".  Proves deviation, not quantity.
    def test_semantic_lock_deviation_not_quantity(self) -> None:
        code, response = self._run("ra_semantic_lock", self._o1_request())
        self.assertEqual(code, 0)
        self.assertIsNotNone(response)
        self.assertEqual(response["overall_status"], "ALL_ROUTES_AGREE")
        self.assertNotEqual(response["q_E"], "0")
        self.assertEqual(response["route_agreement"]["q_E"], "0")
        self.assertNotEqual(response["route_agreement"]["q_E"], response["q_E"])

    # TEST 2a: the pure helper computes the known max pairwise deviation.
    def test_pairwise_max_abs_deviation_known_value(self) -> None:
        self.assertEqual(
            q1._pairwise_max_abs_deviation(
                [Decimal("0.10"), Decimal("0.11"), Decimal("0.095")]),
            Decimal("0.015"))
        self.assertEqual(q1._pairwise_max_abs_deviation([Decimal("0.1")]), Decimal(0))
        self.assertEqual(q1._pairwise_max_abs_deviation([Decimal("0.1"), Decimal("0.1")]), Decimal(0))
        self.assertEqual(q1._pairwise_max_abs_deviation([]), Decimal(0))

    # TEST 2b: per-quantity builder with seam inputs closed=0.10, enum=0.11,
    # abs=0.095 for a pre-route quantity (q_E) and a downstream quantity
    # (lambda_A/tilde_A); p_GP uses 0.20/0.21/0.205.
    def test_route_agreement_deviations_known_seam(self) -> None:
        pre_results = {
            "closed_form": {"q_E": Decimal("0.10"), "G": Decimal("0.5"),
                            "Z_0": Decimal("0.4"), "Z_1": Decimal("0.1")},
            "enumeration": {"q_E": Decimal("0.11"), "G": Decimal("0.5"),
                            "Z_0": Decimal("0.4"), "Z_1": Decimal("0.1")},
            "absorption_chain": {"q_E": Decimal("0.095"), "G": Decimal("0.5"),
                                 "Z_0": Decimal("0.4"), "Z_1": Decimal("0.1")},
        }
        down_results = {
            "closed_form": {
                "fourfold": {"p_GP": Decimal("0.20"), "p_BP": Decimal("0.1"),
                             "p_GE": Decimal("0.1"), "p_BE": Decimal("0.6")},
                "lambda_main": [Decimal("0.10"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")],
                "lambda_tilde": [Decimal("0.10"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")],
            },
            "enumeration": {
                "fourfold": {"p_GP": Decimal("0.21"), "p_BP": Decimal("0.1"),
                             "p_GE": Decimal("0.1"), "p_BE": Decimal("0.6")},
                "lambda_main": [Decimal("0.11"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")],
                "lambda_tilde": [Decimal("0.11"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")],
            },
            "absorption_chain": {
                "fourfold": {"p_GP": Decimal("0.205"), "p_BP": Decimal("0.1"),
                             "p_GE": Decimal("0.1"), "p_BE": Decimal("0.6")},
                "lambda_main": [Decimal("0.095"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")],
                "lambda_tilde": [Decimal("0.095"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")],
            },
        }
        dev = q1._route_agreement_deviations(pre_results, down_results, na=False, q_e_zero=False)
        # pre-route quantity: max(|0.10-0.11|, |0.10-0.095|, |0.11-0.095|) = 0.015
        self.assertEqual(dev["q_E"], Decimal("0.015"))
        self.assertEqual(dev["G"], Decimal(0))
        self.assertEqual(dev["Z_0"], Decimal(0))
        self.assertEqual(dev["Z_1"], Decimal(0))
        # downstream quantity: max(|0.20-0.21|, |0.20-0.205|, |0.21-0.205|) = 0.01
        self.assertEqual(dev["p_GP"], Decimal("0.01"))
        self.assertEqual(dev["p_BP"], Decimal(0))
        # downstream quantity: lambda_A = 0.015 and tilde_A = 0.015
        self.assertEqual(dev["lambda_A"], Decimal("0.015"))
        self.assertEqual(dev["lambda_D"], Decimal(0))
        self.assertEqual(dev["tilde_A"], Decimal("0.015"))
        # never the quantity values themselves
        self.assertNotEqual(dev["q_E"], Decimal("0.10"))
        self.assertNotEqual(dev["p_GP"], Decimal("0.20"))
        self.assertNotEqual(dev["lambda_A"], Decimal("0.10"))

    # TEST 5: lambda NA.  lambda.na=true => route_agreement.lambda_* stay null
    # (the helper must not turn them into "0").
    def test_lambda_na_deviations_are_null(self) -> None:
        down_results = {
            "closed_form": {"lambda_main": [Decimal("0.10"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")]},
            "enumeration": {"lambda_main": [Decimal("0.11"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")]},
            "absorption_chain": {"lambda_main": [Decimal("0.095"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")]},
        }
        dev = q1._route_agreement_deviations({}, down_results, na=True, q_e_zero=False)
        for key in ("lambda_A", "lambda_B", "lambda_C", "lambda_D"):
            self.assertIsNone(dev[key], f"NA lambda deviation {key} must stay null, never '0'")
        # End-to-end: O5 (beta_E=1 => lambda.na=true) keeps lambda_* null.
        with open(FIXTURE, "r", encoding="utf-8") as handle:
            fixture = json.load(handle)
        case = next(c for c in fixture["cases"] if c["case_id"] == "O5_NA_lambda_beta1_single")
        code, response = self._run("ra_lambda_na", make_derive_request(case["input"], case["semantics"]))
        self.assertEqual(code, 0)
        self.assertIsNotNone(response)
        self.assertTrue(response["lambda"]["na"])
        for key in ("lambda_A", "lambda_B", "lambda_C", "lambda_D"):
            self.assertIsNone(response["route_agreement"][key])

    # TEST 6: tilde NA.  q_E=0 => route_agreement.tilde_* stay null (the helper
    # must not turn them into "0").
    def test_tilde_na_deviations_are_null(self) -> None:
        down_results = {
            "closed_form": {"lambda_tilde": [Decimal("0.10"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")]},
            "enumeration": {"lambda_tilde": [Decimal("0.11"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")]},
            "absorption_chain": {"lambda_tilde": [Decimal("0.095"), Decimal("0.0"), Decimal("0.0"), Decimal("0.9")]},
        }
        dev = q1._route_agreement_deviations({}, down_results, na=True, q_e_zero=True)
        for key in ("tilde_A", "tilde_B", "tilde_C", "tilde_D"):
            self.assertIsNone(dev[key], f"q_E=0 tilde deviation {key} must stay null, never '0'")
        # End-to-end: q_E=0 keeps route_agreement.tilde_* null.
        code, response = self._run("ra_tilde_na", make_derive_request(
            {"q_a": "0", "q_b": "0", "q_c": "0", "q_d": "0",
             "e_a": "0", "e_b": "0", "e_c": "0", "e_e": "0"}, q1.SINGLE))
        self.assertEqual(code, 0)
        self.assertIsNotNone(response)
        self.assertEqual(response["q_E"], "0")
        for key in ("tilde_A", "tilde_B", "tilde_C", "tilde_D"):
            self.assertIsNone(response["route_agreement"][key])

    # TEST 4: over tolerance.  Three routes get distinct fourfold p_GP offsets
    # (closed +0.10, enum +0.11, abs +0.095): max pairwise deviation = 0.015 >
    # 1e-15 => the existing route-mismatch mechanism yields ROUTE_MISMATCH (exit
    # 3) with the full response recording the ACTUAL deviation, not only status.
    def test_over_tolerance_records_actual_deviation_and_mismatch(self) -> None:
        originals = {name: q1.ROUTE_MODULES[name].compute_downstream for name in q1.ROUTE_NAMES}
        offsets = {"closed_form": Decimal("0.10"), "enumeration": Decimal("0.11"),
                   "absorption_chain": Decimal("0.095")}

        def make_wrapper(base_fn, offset: Decimal):
            def wrapped_fn(abc, q_d, pre, e_kernel, precision=200):
                result = dict(base_fn(abc, q_d, pre, e_kernel, precision))
                result["fourfold"] = dict(result["fourfold"])
                result["fourfold"]["p_GP"] = result["fourfold"]["p_GP"] + offset
                # Keep the per-route fourfold normalized (p_BE = residual) so the
                # closed-form conservation invariant still holds.
                result["fourfold"]["p_BE"] = (Decimal(1) - result["fourfold"]["p_GP"]
                                              - result["fourfold"]["p_BP"]
                                              - result["fourfold"]["p_GE"])
                return result
            return wrapped_fn

        try:
            for name in q1.ROUTE_NAMES:
                q1.ROUTE_MODULES[name].compute_downstream = make_wrapper(originals[name], offsets[name])
            code, response = self._run("ra_over_tolerance", self._o1_request())
        finally:
            for name in q1.ROUTE_NAMES:
                q1.ROUTE_MODULES[name].compute_downstream = originals[name]
        self.assertEqual(code, 3)
        self.assertIsNotNone(response)
        self.assertEqual(response["overall_status"], "ROUTE_MISMATCH")
        self.assert_response_valid(response)
        # actual deviation: |(0.31640625+0.10)-(0.31640625+0.11)| = 0.01,
        # |(0.31640625+0.10)-(0.31640625+0.095)| = 0.005,
        # |(0.31640625+0.11)-(0.31640625+0.095)| = 0.015 => max = 0.015.
        self.assertEqual(response["route_agreement"]["p_GP"], "0.015")
        self.assertNotEqual(response["route_agreement"]["p_GP"], response["fourfold"]["p_GP"])


class TestRouteAgreementCanonicalDeviation(TestCanonicalRuns):
    """L3-approved deviation semantics on the real canonical-like responses
    (canonical single: q_E/G/Z_0/p_GP/lambda_A agree exactly across the three
    routes -> deviations serialize to "0"; downstream p_BP micro-differs -> the
    true nonzero deviation is carried, never force-zero)."""

    # TEST 3: nonzero within tolerance.  The three routes micro-differ on
    # downstream fourfold (p_BP max deviation > 0 but <= 1e-15); route_agreement
    # carries the nonzero deviation (never force-zero) and overall_status stays
    # ALL_ROUTES_AGREE.
    def test_nonzero_deviation_within_tolerance_carried(self) -> None:
        response = self.run_canonical(q1.SINGLE)
        self.assertEqual(response["overall_status"], "ALL_ROUTES_AGREE")
        deviation = Decimal(response["route_agreement"]["p_BP"])
        self.assertGreater(deviation, Decimal(0))
        self.assertLessEqual(deviation, TOL)
        self.assertNotEqual(response["route_agreement"]["p_BP"], response["fourfold"]["p_BP"])

    # TEST 7: canonical-like nonzero.  Clearly nonzero q_E/p_GP/lambda with
    # route_agreement.* being deviations, never the quantity values: exact
    # agreement -> "0"; micro-differences -> the true max deviation.
    def test_canonical_nonzero_route_agreement_is_deviation(self) -> None:
        response = self.run_canonical(q1.SINGLE)
        self.assertNotEqual(response["q_E"], "0")
        for key in ("q_E", "G", "Z_0"):
            self.assertEqual(response["route_agreement"][key], "0")
            self.assertNotEqual(response["route_agreement"][key], response[key])
        self.assertEqual(response["route_agreement"]["p_GP"], "0")
        self.assertNotEqual(response["route_agreement"]["p_GP"], response["fourfold"]["p_GP"])
        self.assertEqual(response["route_agreement"]["lambda_A"], "0")
        self.assertNotEqual(response["route_agreement"]["lambda_A"],
                            response["lambda"]["main"]["A"])
        # p_BP micro-difference: true nonzero deviation, not the quantity value.
        self.assertGreater(Decimal(response["route_agreement"]["p_BP"]), Decimal(0))
        self.assertNotEqual(response["route_agreement"]["p_BP"], response["fourfold"]["p_BP"])
        # route_agreement never mirrors any single route's representative value.
        for key in ("p_GP", "p_BP", "p_GE", "p_BE"):
            for route in ("closed_form", "enumeration", "absorption_chain"):
                self.assertNotEqual(response["route_agreement"][key],
                                    response["fourfold"]["per_route"][route][key])


if __name__ == "__main__":
    unittest.main()
