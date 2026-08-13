from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "04_代码" / "main_model" / "observation_calibration_v1.py"
FIXTURE_PATH = ROOT / "04_代码" / "tests" / "fixtures" / "observation_calibration_oracles_v1.json"
PARAMETERS_PATH = ROOT / "02_数据" / "parameters.csv"
spec = importlib.util.spec_from_file_location("calibration", MODULE_PATH)
calibration = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(calibration)


def request(semantics: str, q: str, e: str, process: str = "X") -> dict:
    return {"schema_version": "observation_calibration_v1", "envelope_type": "calibration_request",
            "request_id": "test-request", "scenario_role": "test_oracle", "semantics": semantics,
            "items": [{"process_id": process, "direct_values": {"q": q, "e": e}}]}


class ObservationCalibrationMainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.parameters = Path(self.temp.name) / "parameters.csv"
        shutil.copyfile(PARAMETERS_PATH, self.parameters)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def solve(self, semantics: str, q: str, e: str) -> dict:
        return calibration.calibrate(request(semantics, q, e), self.parameters)["results"][0]

    def assert_unique_public_certificate(self, result: dict, semantics: str) -> dict[str, str]:
        notes = dict(entry.split("=", 1) for entry in result["diagnostics"]["notes"] if "=" in entry)
        required = {"root_alpha_lo", "root_alpha_hi", "root_alpha_span", "root_beta_lo", "root_beta_hi", "root_beta_span",
                    "reported_alpha_lo", "reported_alpha_hi", "reported_alpha_span", "reported_beta_lo", "reported_beta_hi", "reported_beta_span"}
        self.assertEqual(set(notes), required)
        public_alpha, public_beta = Decimal(result["alpha"]), Decimal(result["beta"])
        for parameter, public in (("alpha", public_alpha), ("beta", public_beta)):
            root_lo, root_hi = Decimal(notes[f"root_{parameter}_lo"]), Decimal(notes[f"root_{parameter}_hi"])
            reported_lo = Decimal(notes[f"reported_{parameter}_lo"])
            reported_hi = Decimal(notes[f"reported_{parameter}_hi"])
            with localcontext() as ctx:
                ctx.prec = 1000
                root_span = root_hi - root_lo
                reported_span = reported_hi - reported_lo
                self.assertLessEqual(root_lo, root_hi)
                self.assertLessEqual(root_span, Decimal("1e-12"))
                self.assertEqual(Decimal(notes[f"root_{parameter}_span"]), root_span)
                self.assertEqual(reported_lo, min(root_lo, public))
                self.assertEqual(reported_hi, max(root_hi, public))
                self.assertEqual(Decimal(notes[f"reported_{parameter}_span"]), reported_span)
                self.assertLessEqual(reported_span, Decimal("1e-12"))
        q, e = Decimal(result["q"]), Decimal(result["e"])
        p0 = max(120, max(calibration._significant_digits(q), calibration._significant_digits(e)) + 80)
        with localcontext() as ctx:
            ctx.prec = p0
            expected_residuals = calibration._residuals(q, e, public_alpha, public_beta, semantics)
        self.assertEqual(result["diagnostics"]["residuals"], expected_residuals)
        self.assertLessEqual(max(Decimal(value) for value in expected_residuals.values()), Decimal("5e-12"))
        return notes

    def test_fixture_all_cases(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            if case.get("oracle_scope") == "EXACT_FRACTION_ALGEBRA_ONLY_NOT_PUBLIC_API":
                continue
            raw_q, raw_e = case["input"]["q"], case["input"]["e"]
            if "/" in raw_q:  # test harness converts exact fixture syntax to request decimal syntax.
                with localcontext() as ctx:
                    ctx.prec = 100
                    raw_q = str(Decimal(raw_q.split("/")[0]) / Decimal(raw_q.split("/")[1]))
            if "/" in raw_e:
                with localcontext() as ctx:
                    ctx.prec = 100
                    raw_e = str(Decimal(raw_e.split("/")[0]) / Decimal(raw_e.split("/")[1]))
            result = self.solve(case["semantics"], raw_q, raw_e)
            self.assertEqual(result["status"], case["expected"]["status"], case["case_id"])
            if "free_parameters" in case["expected"]:
                self.assertEqual(result["free_parameters"], case["expected"]["free_parameters"], case["case_id"])
            if result["status"] == "UNIQUE_SOLUTION":
                self.assert_unique_public_certificate(result, case["semantics"])

    def test_single_nonterminating_public_value_and_minimal_hull(self) -> None:
        result = self.solve(calibration.SINGLE, "0.025", "0.03")
        self.assertEqual(result["status"], "UNIQUE_SOLUTION")
        self.assertEqual(result["alpha"], "0.015384615384615385")
        notes = self.assert_unique_public_certificate(result, calibration.SINGLE)
        with localcontext() as ctx:
            ctx.prec = 160
            exact_alpha = Decimal(3) / Decimal(195)
        self.assertLessEqual(Decimal(notes["root_alpha_lo"]), exact_alpha)
        self.assertGreaterEqual(Decimal(notes["root_alpha_hi"]), exact_alpha)
        self.assertNotEqual(Decimal(result["alpha"]), exact_alpha)

    def test_single_unique_boundaries_have_public_certificates(self) -> None:
        for q, e in (("0.37", "0"), ("0.25", "0.5"), ("0.75", "0.5"), ("0.5", "1")):
            result = self.solve(calibration.SINGLE, q, e)
            self.assertEqual(result["status"], "UNIQUE_SOLUTION")
            self.assert_unique_public_certificate(result, calibration.SINGLE)

    def test_finite_decimal_two_thirds_e_one_is_infeasible(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 100
            q = str(Decimal(2) / Decimal(3))
        self.assertEqual(self.solve(calibration.CHAIN, q, "1")["status"], "INFEASIBLE")

    def test_long_decimal_precision_is_stable_or_reports_numerical_failure(self) -> None:
        q = "0.0100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001"
        e = "0.0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001"
        try:
            first = self.solve(calibration.CHAIN, q, e)
            second = self.solve(calibration.CHAIN, q, e)
        except calibration.NumericalError:
            return
        self.assertEqual(first["status"], second["status"])
        self.assertEqual(first["alpha"], second["alpha"])
        self.assertEqual(first["beta"], second["beta"])

    def test_single_long_decimal_exact_boundary_and_adjacent_points(self) -> None:
        q_text = "0.25" + ("0" * 147) + "1"
        q = Decimal(q_text)
        with localcontext() as ctx:
            ctx.prec = 260
            boundary = q * Decimal("2")
            below = boundary - Decimal("1e-151")
            above = boundary + Decimal("1e-151")
        boundary_result = self.solve(calibration.SINGLE, q_text, calibration._plain(boundary))
        self.assertEqual(boundary_result["status"], "UNIQUE_SOLUTION")
        self.assertEqual(boundary_result["beta"], "1")
        self.assert_unique_public_certificate(boundary_result, calibration.SINGLE)
        self.assertEqual(self.solve(calibration.SINGLE, q_text, calibration._plain(below))["status"], "UNIQUE_SOLUTION")
        self.assertEqual(self.solve(calibration.SINGLE, q_text, calibration._plain(above))["status"], "INFEASIBLE")

    def test_codomain_intersection_boundary_certificates(self) -> None:
        for q_text, t_text, expected_alpha, expected_beta in [
            ("0.01", "0", ("0", "0"), ("0", "0")),
            ("0.01", "0.01", None, ("1", "1")),
            ("0.9", "0.2", ("1", "1"), None),
        ]:
            q, t = Decimal(q_text), Decimal(t_text)
            alpha_bounds, beta_bounds = calibration._chain_parameter_bounds(q, t, t, 160)
            for bounds in (alpha_bounds, beta_bounds):
                self.assertGreaterEqual(bounds[0], Decimal("0"))
                self.assertLessEqual(bounds[1], Decimal("1"))
            if expected_alpha is not None:
                self.assertEqual(tuple(map(str, alpha_bounds)), expected_alpha)
            if expected_beta is not None:
                self.assertEqual(tuple(map(str, beta_bounds)), expected_beta)

    def test_quarter_emax_near_degenerate_is_not_false_out_of_domain(self) -> None:
        q = Decimal("0.01")
        e_max, _ = calibration._chain_e_max(q, 160)
        result = self.solve(calibration.CHAIN, "0.01", calibration._plain(e_max / Decimal("4")))
        self.assertEqual(result["status"], "UNIQUE_SOLUTION")

    def test_exact_values_and_boundary_statuses(self) -> None:
        result = self.solve(calibration.SINGLE, "0.25", "0.25")
        self.assertEqual(result["alpha"], "0.16666666666666667")
        self.assertEqual(result["beta"], "0.5")
        self.assertEqual(self.solve(calibration.SINGLE, "0.25", "0.5")["beta"], "1")
        self.assertEqual(self.solve(calibration.SINGLE, "0.25", "0.50000000000000000001")["status"], "INFEASIBLE")
        result = self.solve(calibration.CHAIN, "0.5", "0.5")
        self.assertEqual(result["alpha"], "0.5")
        self.assertEqual(result["beta"], "0.5")
        self.assertEqual(self.solve(calibration.CHAIN, "0.5", "0.76393202250021030358")["status"], "UNIQUE_SOLUTION")
        self.assertEqual(self.solve(calibration.CHAIN, "0.5", "0.76393202250021030360")["status"], "INFEASIBLE")

    def test_canonical_binding_and_csv_perturbation(self) -> None:
        items = []
        for process, (q_id, e_id) in calibration.BINDINGS.items():
            items.append({"process_id": process, "canonical_parameter_ref": {"source": "02_数据/parameters.csv", "q_parameter_id": q_id, "e_parameter_id": e_id}})
        base = {"schema_version": "observation_calibration_v1", "envelope_type": "calibration_request", "request_id": "canonical",
                "scenario_role": "canonical_g2_abc", "semantics": calibration.SINGLE, "items": items}
        original = calibration.calibrate(base, self.parameters)
        text = self.parameters.read_text(encoding="utf-8")
        self.parameters.write_text(text.replace("P026,q_A,defect_probability_A", "P026,q_A,defect_probability_A").replace(",0.025,probability,1,", ",0.02,probability,1,"), encoding="utf-8")
        changed = calibration.calibrate(base, self.parameters)
        self.assertNotEqual(original["results"][0]["q"], changed["results"][0]["q"])

    def test_schema_source_canonical_request_is_accepted_and_wrong_source_is_rejected(self) -> None:
        items = [{"process_id": process, "canonical_parameter_ref": {
            "source": "02_数据/parameters.csv", "q_parameter_id": q_id, "e_parameter_id": e_id,
        }} for process, (q_id, e_id) in calibration.BINDINGS.items()]
        canonical = {"schema_version": "observation_calibration_v1", "envelope_type": "calibration_request",
                     "request_id": "schema-source-canonical", "scenario_role": "canonical_g2_abc",
                     "semantics": calibration.SINGLE, "items": items}
        response = calibration.calibrate(canonical, self.parameters)
        self.assertEqual(response["overall_status"], "ALL_IDENTIFIED")
        self.assertEqual([item["q"] for item in response["results"]], ["0.025", "0.03", "0.02"])
        canonical["items"][0]["canonical_parameter_ref"]["source"] = "02_错误/parameters.csv"
        with self.assertRaises(calibration.ValidationError):
            calibration.calibrate(canonical, self.parameters)

    def test_canonical_chain_residuals_exactly_match_public_values_at_p0(self) -> None:
        items = [{"process_id": process, "canonical_parameter_ref": {
            "source": "02_数据/parameters.csv", "q_parameter_id": q_id, "e_parameter_id": e_id,
        }} for process, (q_id, e_id) in calibration.BINDINGS.items()]
        canonical = {"schema_version": "observation_calibration_v1", "envelope_type": "calibration_request",
                     "request_id": "canonical-chain-public-residuals", "scenario_role": "canonical_g2_abc",
                     "semantics": calibration.CHAIN, "items": items}

        # Deliberately vary the caller context: the public diagnostics are
        # required to be functions of q/e/public alpha/beta and frozen p0 only.
        with localcontext() as ctx:
            ctx.prec = 19
            low_context_response = calibration.calibrate(canonical, self.parameters)
        with localcontext() as ctx:
            ctx.prec = 500
            high_context_response = calibration.calibrate(canonical, self.parameters)
        self.assertEqual(low_context_response, high_context_response)

        def lexical_significant_digits(text: str) -> int:
            digits = text.replace("-", "").replace(".", "").lstrip("0")
            return len(digits) if digits else 1

        def normalize_public_decimal(value: Decimal) -> Decimal:
            if value == 0:
                return Decimal(0)
            quantum = Decimal(1).scaleb(value.copy_abs().adjusted() - 16)
            return value.quantize(quantum)

        for result in low_context_response["results"]:
            self.assertEqual(result["status"], "UNIQUE_SOLUTION")
            q_text, e_text = result["q"], result["e"]
            p0 = max(120, max(lexical_significant_digits(q_text), lexical_significant_digits(e_text)) + 80)
            with localcontext() as ctx:
                ctx.prec = p0
                q, e = Decimal(q_text), Decimal(e_text)
                alpha, beta = Decimal(result["alpha"]), Decimal(result["beta"])
                d_value = Decimal(1) + (Decimal(1) - q) * alpha + q * (Decimal(1) - beta)
                a_value = (Decimal(1) - q) * (alpha + alpha * alpha)
                b_value = q * (Decimal(2) * beta - beta * beta)
                target = e * d_value / Decimal(2)
                independently_recomputed = {
                    "equation_1_abs": normalize_public_decimal(abs(a_value - target)),
                    "equation_2_abs": normalize_public_decimal(abs(b_value - target)),
                    "balance_abs": normalize_public_decimal(abs(a_value - b_value)),
                }
            diagnostics = result["diagnostics"]["residuals"]
            self.assertEqual(set(diagnostics), set(independently_recomputed))
            for key, expected in independently_recomputed.items():
                self.assertEqual(Decimal(diagnostics[key]), expected, (result["process_id"], key))
                self.assertLessEqual(expected, Decimal("5e-12"), (result["process_id"], key))

    def test_rejects_invalid_extra_duplicate_and_forbidden_canonical(self) -> None:
        invalid = request(calibration.SINGLE, "0.2", "0.1")
        invalid["extra"] = True
        with self.assertRaises(calibration.ValidationError): calibration.calibrate(invalid, self.parameters)
        duplicate = request(calibration.SINGLE, "0.2", "0.1")
        duplicate["items"].append(duplicate["items"][0].copy())
        with self.assertRaises(calibration.ValidationError): calibration.calibrate(duplicate, self.parameters)
        bad_decimal = request(calibration.SINGLE, "1e-1", "0")
        with self.assertRaises(calibration.ValidationError): calibration.calibrate(bad_decimal, self.parameters)
        canonical_e = request(calibration.SINGLE, "0.2", "0.1", "E")
        canonical_e["scenario_role"] = "canonical_g2_abc"
        with self.assertRaises(calibration.ValidationError): calibration.calibrate(canonical_e, self.parameters)

    def test_endpoints_infeasible_and_missing_or_duplicate_csv_ids(self) -> None:
        self.assertEqual(self.solve(calibration.SINGLE, "0", "0")["free_parameters"], ["beta"])
        self.assertEqual(self.solve(calibration.CHAIN, "1", "0")["free_parameters"], ["alpha"])
        self.assertEqual(self.solve(calibration.CHAIN, "1", "0.1")["status"], "INFEASIBLE")
        canonical = {"schema_version": "observation_calibration_v1", "envelope_type": "calibration_request", "request_id": "canonical",
                     "scenario_role": "canonical_g2_abc", "semantics": calibration.SINGLE,
                     "items": [{"process_id": "A", "canonical_parameter_ref": {"source": "02_数据/parameters.csv", "q_parameter_id": "P026", "e_parameter_id": "P030"}},
                               {"process_id": "B", "canonical_parameter_ref": {"source": "02_数据/parameters.csv", "q_parameter_id": "P027", "e_parameter_id": "P031"}},
                               {"process_id": "C", "canonical_parameter_ref": {"source": "02_数据/parameters.csv", "q_parameter_id": "P028", "e_parameter_id": "P032"}}]}
        self.parameters.write_text(self.parameters.read_text(encoding="utf-8").replace("P030,e_A", "P030X,e_A"), encoding="utf-8")
        with self.assertRaises(calibration.ValidationError): calibration.calibrate(canonical, self.parameters)


if __name__ == "__main__":
    unittest.main()
