import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "04_代码" / "checker" / "observation_calibration_checker_v1.py"
PACKAGE = ROOT / "08_项目管理" / "任务包" / "G2-01_观测核标定最小基线.yaml"
PARAMETERS = ROOT / "02_数据" / "parameters.csv"
SCHEMA = ROOT / "04_代码" / "src" / "schemas" / "observation_calibration_v1.schema.json"
SPEC = importlib.util.spec_from_file_location("checker_under_test", CHECKER)
CHECKER_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER_MODULE)
RUN_ID = "20260813T123456123456Z_deadbeef"


def _diagnostics():
    return {"method":"closed_form","feasibility":"FEASIBLE","uniqueness":"UNIQUE","iterations":0,
            "bracket":{"variable":"NONE","lower":None,"upper":None,"final_width":None},
            "residuals":{"equation_1_abs":"0","equation_2_abs":"0","balance_abs":"0"},
            "tolerance_profile":"observation_calibration_v1_tol"}


def endpoint_diagnostics(status):
    return {"method":"endpoint_analysis" if status == "NONIDENTIFIABLE_FAMILY" else "feasibility_only",
            "feasibility":"FEASIBLE" if status == "NONIDENTIFIABLE_FAMILY" else "INFEASIBLE",
            "uniqueness":"NONIDENTIFIABLE_FAMILY" if status == "NONIDENTIFIABLE_FAMILY" else "NO_SOLUTION",
            "iterations":0,"bracket":{"variable":"NONE","lower":None,"upper":None,"final_width":None},
            "residuals":None,"tolerance_profile":"observation_calibration_v1_tol"}


def item(pid, q, e, alpha, beta, emax):
    return {"process_id":pid,"status":"UNIQUE_SOLUTION","q":q,"e":e,"alpha":alpha,"beta":beta,"e_max":emax,
            "free_parameters":[],"diagnostics":_diagnostics()}


def attach_certificate(result, semantics):
    q, e = Decimal(result["q"]), Decimal(result["e"])
    solved = (CHECKER_MODULE._single_solve(q, e) if semantics == "single_test_unconditional_v1"
              else CHECKER_MODULE._chain_solve(q, e))
    cert = solved[-1]
    result["diagnostics"]["notes"] = [
        key+"="+CHECKER_MODULE._certificate_number(cert[key]) for key in CHECKER_MODULE.CERT_KEYS
    ]
    with localcontext() as ctx:
        ctx.prec = CHECKER_MODULE._p0(q, e)
        public = CHECKER_MODULE._residuals(q, e, Decimal(result["alpha"]), Decimal(result["beta"]), semantics)
    result["diagnostics"]["residuals"] = {
        key: CHECKER_MODULE._number(value)
        for key, value in zip(("equation_1_abs", "equation_2_abs", "balance_abs"), public)
    }
    return result


class CheckerTests(unittest.TestCase):
    def test_frozen_task_package_version_binding(self):
        self.assertIn('task_package_version: "G2-01-SPEC-V1.1.11"', PACKAGE.read_text(encoding="utf-8"))

    def canonical_response(self):
        response = {"schema_version":"observation_calibration_v1","envelope_type":"calibration_response",
                "request_id":RUN_ID+":single_test_unconditional_v1","scenario_role":"canonical_g2_abc",
                "semantics":"single_test_unconditional_v1","overall_status":"ALL_IDENTIFIED","results":[
                    item("A","0.025","0.03","0.015384615384615385","0.6","0.05"),
                    item("B","0.03","0.04","0.020618556701030928","0.66666666666666667","0.06"),
                    item("C","0.02","0.02","0.010204081632653061","0.5","0.04")]}
        for result in response["results"]:
            attach_certificate(result, response["semantics"])
        return response

    def invoke(self, response, sentinel=None):
        with tempfile.TemporaryDirectory() as td:
            rp, report = Path(td)/"response.json", Path(td)/"report.json"
            rp.write_text(json.dumps(response), encoding="utf-8")
            if sentinel is not None: report.write_bytes(sentinel)
            proc = subprocess.run([sys.executable, str(CHECKER), "--response",str(rp),"--parameters",str(PARAMETERS),
                                   "--schema",str(SCHEMA),"--task-package",str(PACKAGE),"--report",str(report)],
                                  capture_output=True, text=True)
            return proc, (report.read_bytes() if report.exists() else None)

    def test_canonical_run_id_is_inherited(self):
        proc, raw = self.invoke(self.canonical_response())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(raw)
        self.assertEqual(report["run_id"], RUN_ID)
        self.assertEqual(report["checker_status"], "PASS")
        for checked in report["items"]:
            self.assertEqual(set(checked), {
                "process_id", "status", "response_result_status", "response_free_parameters",
                "independent_result_status", "independent_free_parameters",
                "independent_alpha", "independent_beta", "independent_residuals",
                "max_original_residual", "independent_certificate", "existence_diagnostics", "message"
            })
            self.assertEqual(set(checked["independent_certificate"]), set(CHECKER_MODULE.CERT_KEYS))
            self.assertEqual(set(checked["existence_diagnostics"]), {
                "method", "alpha_outer_R_lower", "alpha_outer_R_upper", "inner_bracket_status",
                "inner_bracket_count", "root_internal_max_residual", "response_certificate_status", "root_relation"
            })
            residual_values = {key: Decimal(value) for key, value in checked["independent_residuals"].items()}
            self.assertEqual(Decimal(checked["max_original_residual"]), max(residual_values.values()))

    def test_preflight_rejects_without_touching_report(self):
        variants = []
        malformed = self.canonical_response(); malformed["request_id"] = "bad:single_test_unconditional_v1"; variants.append(malformed)
        mismatch = self.canonical_response(); mismatch["request_id"] = RUN_ID+":standard_chain_v1"; variants.append(mismatch)
        noncanonical = self.canonical_response(); noncanonical["scenario_role"] = "generic"; variants.append(noncanonical)
        for response in variants:
            proc, raw = self.invoke(response, b"sentinel")
            self.assertEqual(proc.returncode, 2)
            self.assertTrue(proc.stderr)
            self.assertEqual(raw, b"sentinel")
            proc, raw = self.invoke(response)
            self.assertEqual(proc.returncode, 2)
            self.assertIsNone(raw)

    def test_post_preflight_validation_writes_report(self):
        response = self.canonical_response(); response["results"][0].pop("beta")
        proc, raw = self.invoke(response)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(raw)["checker_status"], "VALIDATION_ERROR")
        self.assertEqual(json.loads(raw)["run_id"], RUN_ID)

    def test_overall_status_mismatch_preserves_schema_item_shape(self):
        response = self.canonical_response()
        response["overall_status"] = "HAS_INFEASIBLE"
        proc, raw = self.invoke(response)
        report = json.loads(raw)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report["checker_status"], "FAIL")
        self.assertEqual(report["checked_result_count"], 3)
        self.assertEqual(len(report["items"]), 3)
        self.assertTrue(all(item["process_id"] in {"A", "B", "C"} for item in report["items"]))

    def test_exact_fraction_global_boundary_is_not_an_api_case(self):
        q, e, alpha, beta = Fraction(2, 3), Fraction(1), Fraction(1), Fraction(1)
        d = 1 + (1-q)*alpha + q*(1-beta)
        self.assertEqual((d, (1-q)*(alpha+alpha*alpha), q*(2*beta-beta*beta)),
                         (Fraction(4,3), Fraction(2,3), Fraction(2,3)))

    def test_embedded_oracle_status_and_free_parameters_for_both_semantics(self):
        """Task-package embedded cases only; no external fixture is opened."""
        endpoint_cases = (
            ("0", "0", "NONIDENTIFIABLE_FAMILY", Decimal(0), None, ["beta"]),
            ("1", "0", "NONIDENTIFIABLE_FAMILY", None, Decimal(0), ["alpha"]),
            ("0.37", "0", "UNIQUE_SOLUTION", Decimal(0), Decimal(0), []),
            ("0", "0.0001", "INFEASIBLE", None, None, []),
            ("1", "0.0001", "INFEASIBLE", None, None, []),
        )
        for semantics in ("single_test_unconditional_v1", "standard_chain_v1"):
            solve = CHECKER_MODULE._single_solve if semantics == "single_test_unconditional_v1" else CHECKER_MODULE._chain_solve
            for q_text, e_text, status, alpha, beta, free in endpoint_cases:
                actual = solve(Decimal(q_text), Decimal(e_text))
                self.assertEqual(actual[:3], (status, alpha, beta))
                self.assertEqual(actual[4], free)

    def test_nonunique_and_infeasible_report_null_rules(self):
        for status, q, e, alpha, beta, emax, free in (
            ("NONIDENTIFIABLE_FAMILY", "0", "0", "0", None, "0", ["beta"]),
            ("INFEASIBLE", "0", "0.0001", None, None, "0", []),
        ):
            result = {"process_id":"endpoint", "status":status, "q":q, "e":e,
                      "alpha":alpha, "beta":beta, "e_max":emax, "free_parameters":free,
                      "diagnostics":endpoint_diagnostics(status)}
            checked = CHECKER_MODULE._check_item(result, "single_test_unconditional_v1", "generic", {})
            self.assertEqual(checked["status"], "PASS", checked["message"])
            self.assertIsNone(checked["independent_residuals"])
            self.assertIsNone(checked["max_original_residual"])
            self.assertIsNone(checked["independent_certificate"])
            self.assertEqual(checked["independent_result_status"], status)
            self.assertEqual(checked["independent_free_parameters"], free)
            self.assertEqual(checked["existence_diagnostics"]["response_certificate_status"], "NOT_APPLICABLE")
            result["diagnostics"]["notes"] = ["root_alpha_lo=0"]
            claimed = CHECKER_MODULE._check_item(result, "single_test_unconditional_v1", "generic", {})
            self.assertEqual(claimed["status"], "FAIL")
            self.assertIn("must not claim a parameter certificate", claimed["message"])

    def test_wrong_unique_endpoint_is_schema_shaped_fail_with_true_independent_status(self):
        """V1.1.10 regression: response status never controls independent nullability."""
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        required_item = set(schema["$defs"]["checkItem"]["required"])
        required_report = set(schema["$defs"]["checkReportEnvelope"]["required"])
        for semantics in ("single_test_unconditional_v1", "standard_chain_v1"):
            wrong = item("wrong-endpoint", "0", "0", "0", "0", "0")
            wrong["diagnostics"]["method"] = "closed_form" if semantics == "single_test_unconditional_v1" else "scalar_t_bisection"
            wrong["diagnostics"]["notes"] = [key+"=0" for key in CHECKER_MODULE.CERT_KEYS]
            checked = CHECKER_MODULE._check_item(wrong, semantics, "generic", {})
            self.assertEqual(set(checked), required_item)
            self.assertEqual(checked["status"], "FAIL")
            self.assertEqual(checked["response_result_status"], "UNIQUE_SOLUTION")
            self.assertEqual(checked["response_free_parameters"], [])
            self.assertEqual(checked["independent_result_status"], "NONIDENTIFIABLE_FAMILY")
            self.assertEqual(checked["independent_free_parameters"], ["beta"])
            self.assertEqual(checked["independent_alpha"], "0")
            self.assertIsNone(checked["independent_beta"])
            self.assertIsNone(checked["independent_residuals"])
            self.assertIsNone(checked["max_original_residual"])
            self.assertIsNone(checked["independent_certificate"])
            existence = checked["existence_diagnostics"]
            self.assertEqual(existence, {
                "method":"endpoint_analysis", "alpha_outer_R_lower":None,
                "alpha_outer_R_upper":None, "inner_bracket_status":"NOT_APPLICABLE",
                "inner_bracket_count":0, "root_internal_max_residual":None,
                "response_certificate_status":"FAIL", "root_relation":"NOT_APPLICABLE",
            })
            report = {
                "schema_version":"observation_calibration_v1", "envelope_type":"calibration_check_report",
                "run_id":RUN_ID, "registry_version":"CR-V3.1",
                "check_ids":["CR-V3.1/C01","CR-V3.1/C02"], "scenario_role":"canonical_g2_abc",
                "semantics":semantics, "checker_status":"FAIL", "response_sha256":"0"*64,
                "parameters_sha256":"0"*64, "schema_sha256":"0"*64,
                "task_package_sha256":"0"*64, "checked_result_count":1, "items":[checked],
            }
            self.assertTrue(required_report.issubset(report))
            self.assertEqual(json.loads(json.dumps(report, sort_keys=True))["items"][0], checked)

    def test_high_q_and_zero_error_regressions(self):
        with localcontext() as ctx:
            ctx.prec = 100
            for q_text in ("0.01", "0.7", "0.9"):
                q = Decimal(q_text)
                status, alpha, beta, emax, free, cert = CHECKER_MODULE._chain_solve(q, Decimal(0))
                self.assertEqual((status, alpha, beta, free), ("UNIQUE_SOLUTION", Decimal(0), Decimal(0), []))
                self.assertGreater(emax, Decimal(0))
                self.assertIn("root_alpha_lo", cert)
            for q_text in ("0.7", "0.9"):
                q = Decimal(q_text)
                beta = Decimal(1) - (Decimal(1)-Decimal(2)*(Decimal(1)-q)/q).sqrt()
                emax = Decimal(4)*(Decimal(1)-q)/(Decimal(1)+(Decimal(1)-q)+q*(Decimal(1)-beta))
                self.assertEqual(CHECKER_MODULE._chain_solve(q, emax+Decimal("1e-8"))[0], "INFEASIBLE")

    def test_near_degenerate_and_long_decimal_precision(self):
        q = Decimal("0.01")
        status, alpha, beta, _, _, cert = CHECKER_MODULE._chain_solve(q, Decimal("0.000000000000000000000000000001"))
        self.assertEqual(status, "UNIQUE_SOLUTION")
        self.assertLessEqual(cert["root_alpha_span"], Decimal("1e-12"))
        self.assertLessEqual(cert["root_beta_span"], Decimal("1e-12"))
        self.assertLessEqual(cert["reported_alpha_span"], Decimal("1e-12"))
        self.assertLessEqual(cert["reported_beta_span"], Decimal("1e-12"))
        self.assertGreaterEqual(CHECKER_MODULE._p0(Decimal("0." + "1"*251), Decimal("0")), 331)

    def test_qhalf_near_irrational_response_certificate(self):
        """Self-constructed response: checker validates all twelve E1 fields."""
        q, e = Decimal("0.5"), Decimal("0.7639")
        status, alpha, beta, emax, free, cert = CHECKER_MODULE._chain_solve(q, e)
        self.assertEqual(status, "UNIQUE_SOLUTION")
        response_item = item("synthetic", "0.5", "0.7639",
                             CHECKER_MODULE._number(alpha), CHECKER_MODULE._number(beta),
                             CHECKER_MODULE._number(emax))
        response_item["diagnostics"]["method"] = "scalar_t_bisection"
        response_item["diagnostics"]["notes"] = [key+"="+CHECKER_MODULE._certificate_number(cert[key]) for key in CHECKER_MODULE.CERT_KEYS]
        with localcontext() as ctx:
            ctx.prec = CHECKER_MODULE._p0(q, e)
            public = CHECKER_MODULE._residuals(q, e, Decimal(response_item["alpha"]), Decimal(response_item["beta"]), "standard_chain_v1")
        response_item["diagnostics"]["residuals"] = {key: CHECKER_MODULE._number(value) for key, value in zip(("equation_1_abs", "equation_2_abs", "balance_abs"), public)}
        checked = CHECKER_MODULE._check_item(response_item, "standard_chain_v1", "generic", {})
        self.assertEqual(checked["status"], "PASS", checked["message"])
        original = list(response_item["diagnostics"]["notes"])
        public_alpha = Decimal(response_item["alpha"])
        fake_lo, fake_hi = public_alpha+Decimal("5e-13"), public_alpha+Decimal("6e-13")
        replacements = {
            "root_alpha_lo": fake_lo, "root_alpha_hi": fake_hi, "root_alpha_span": fake_hi-fake_lo,
            "reported_alpha_lo": public_alpha, "reported_alpha_hi": fake_hi,
            "reported_alpha_span": fake_hi-public_alpha,
        }
        response_item["diagnostics"]["notes"] = [
            key+"="+CHECKER_MODULE._certificate_number(replacements[key])
            if (key := value.split("=", 1)[0]) in replacements else value
            for value in original
        ]
        fake_checked = CHECKER_MODULE._check_item(response_item, "standard_chain_v1", "generic", {})
        self.assertEqual(fake_checked["status"], "FAIL")
        self.assertIn("chain alpha root certificates do not intersect", fake_checked["message"])
        response_item["diagnostics"]["notes"] = original
        response_item["diagnostics"]["notes"][-1] = "reported_beta_span=1"
        self.assertEqual(CHECKER_MODULE._check_item(response_item, "standard_chain_v1", "generic", {})["status"], "FAIL")

    def test_structured_existence_diagnostics_and_certificate_tamper_status(self):
        for semantics, q_text, e_text in (
            ("single_test_unconditional_v1", "0.25", "0.25"),
            ("standard_chain_v1", "0.5", "0.5"),
        ):
            solve = CHECKER_MODULE._single_solve if semantics == "single_test_unconditional_v1" else CHECKER_MODULE._chain_solve
            status, alpha, beta, emax, _, _ = solve(Decimal(q_text), Decimal(e_text))
            self.assertEqual(status, "UNIQUE_SOLUTION")
            result = item("structured", q_text, e_text, CHECKER_MODULE._number(alpha),
                          CHECKER_MODULE._number(beta), CHECKER_MODULE._number(emax))
            attach_certificate(result, semantics)
            checked = CHECKER_MODULE._check_item(result, semantics, "generic", {})
            existence = checked["existence_diagnostics"]
            self.assertEqual(checked["status"], "PASS", checked["message"])
            self.assertEqual(existence["response_certificate_status"], "PASS")
            if semantics == "single_test_unconditional_v1":
                self.assertEqual(existence["method"], "closed_form_back_substitution")
                self.assertEqual(existence["inner_bracket_status"], "NOT_APPLICABLE")
                self.assertEqual(existence["root_relation"], "CLOSED_FORM_ROOT_CONTAINED")
            else:
                self.assertEqual(existence["method"], "independent_nested_alpha_beta_bisection")
                self.assertEqual(existence["inner_bracket_status"], "ALL_VALID")
                self.assertGreater(existence["inner_bracket_count"], 0)
                self.assertLessEqual(Decimal(existence["alpha_outer_R_lower"]), Decimal(0))
                self.assertGreaterEqual(Decimal(existence["alpha_outer_R_upper"]), Decimal(0))
                self.assertEqual(existence["root_relation"], "ROOT_INTERVALS_INTERSECT")
            result["diagnostics"]["notes"] = [
                "root_alpha_lo=1" if value.startswith("root_alpha_lo=") else value
                for value in result["diagnostics"]["notes"]
            ]
            tampered = CHECKER_MODULE._check_item(result, semantics, "generic", {})
            self.assertEqual(tampered["status"], "FAIL")
            self.assertEqual(tampered["existence_diagnostics"]["response_certificate_status"], "FAIL")
            self.assertEqual(tampered["existence_diagnostics"]["root_relation"], "FAILED")

    def test_response_diagnostic_inner_and_root_claim_tampering_fails(self):
        result = item("claims", "0.5", "0.5", "0.5", "0.5", "0.7639320225002103")
        attach_certificate(result, "standard_chain_v1")
        result["diagnostics"]["feasibility"] = "INFEASIBLE"
        result["diagnostics"]["uniqueness"] = "NO_SOLUTION"
        checked = CHECKER_MODULE._check_item(result, "standard_chain_v1", "generic", {})
        self.assertEqual(checked["status"], "FAIL")
        self.assertIn("feasibility/uniqueness mismatch", checked["message"])

    def test_codomain_intersection_boundary_certificates(self):
        """t=0 and both t_max shapes retain endpoint enclosures in [0,1]."""
        for q_text, e_text, endpoint in (("0.01", "0", "zero"), ("0.01", None, "beta"), ("0.9", None, "alpha")):
            q = Decimal(q_text)
            if e_text is None:
                e_text = CHECKER_MODULE._number(CHECKER_MODULE._chain_solve(q, Decimal(0))[3] - Decimal("1e-8"))
            status, alpha, beta, _, _, cert = CHECKER_MODULE._chain_solve(q, Decimal(e_text))
            self.assertEqual(status, "UNIQUE_SOLUTION")
            for key in ("root_alpha_lo", "root_alpha_hi", "root_beta_lo", "root_beta_hi",
                        "reported_alpha_lo", "reported_alpha_hi", "reported_beta_lo", "reported_beta_hi"):
                self.assertGreaterEqual(cert[key], Decimal(0))
                self.assertLessEqual(cert[key], Decimal(1))
            if endpoint == "zero": self.assertEqual((alpha, beta), (Decimal(0), Decimal(0)))
            if endpoint == "beta": self.assertGreater(beta, Decimal("0.99"))
            if endpoint == "alpha": self.assertGreater(alpha, Decimal("0.99"))

    def test_pathological_beta_certificate_maps_full_alpha_envelope(self):
        """Near beta=1, endpoint propagation prevents midpoint-only undercoverage."""
        cases = ((Decimal("0.01"), Decimal("0.01980390195507347100477")),
                 (Decimal("0.01"), Decimal("0.0198038")))
        for q, e in cases:
            status, alpha, beta, _, _, cert = CHECKER_MODULE._chain_solve(q, e)
            self.assertEqual(status, "UNIQUE_SOLUTION")
            with localcontext() as ctx:
                ctx.prec = 200
                blo, bhi = CHECKER_MODULE._beta_envelope(q, cert["root_alpha_lo"], cert["root_alpha_hi"])
            self.assertLessEqual(cert["root_beta_lo"], blo)
            self.assertGreaterEqual(cert["root_beta_hi"], bhi)
            self.assertLessEqual(cert["root_beta_span"], Decimal("1e-12"))
            self.assertLessEqual(max(CHECKER_MODULE._residuals(q, e, alpha, beta, "standard_chain_v1")), Decimal("5e-12"))

    def test_single_uses_p0_for_150_digit_exact_boundary_and_sides(self):
        q_text = "0.25" + "0"*147 + "1"
        with localcontext() as ctx:
            ctx.prec = 260
            q = Decimal(q_text)
            boundary = Decimal(2)*q
            status, _, _, emax, _, _ = CHECKER_MODULE._single_solve(q, boundary)
            self.assertEqual(status, "UNIQUE_SOLUTION")
            self.assertEqual(emax, boundary)
            self.assertEqual(CHECKER_MODULE._single_solve(q, boundary-boundary.scaleb(-210))[0], "UNIQUE_SOLUTION")
            self.assertEqual(CHECKER_MODULE._single_solve(q, boundary+boundary.scaleb(-210))[0], "INFEASIBLE")

    def test_chain_qhalf_180_digit_boundary_sides(self):
        with localcontext() as ctx:
            ctx.prec = 220
            boundary = Decimal(3)-Decimal(5).sqrt()
            quantum = Decimal(1).scaleb(-180)
            below = boundary.quantize(quantum, rounding="ROUND_FLOOR")
            above = below+quantum
        self.assertEqual(CHECKER_MODULE._chain_solve(Decimal("0.5"), below)[0], "UNIQUE_SOLUTION")
        self.assertEqual(CHECKER_MODULE._chain_solve(Decimal("0.5"), above)[0], "INFEASIBLE")

    def test_single_balance_uses_raw_sides_not_absolute_residual_difference(self):
        q, e = Decimal("0.5"), Decimal("0.5")
        delta = Decimal("1e-10")
        alpha, beta = Decimal("0.5")+delta*2, Decimal("0.5")-delta*2
        first, second, balance = CHECKER_MODULE._residuals(q, e, alpha, beta, "single_test_unconditional_v1")
        self.assertEqual(first, second)
        self.assertEqual(balance, Decimal("2e-10"))
        self.assertGreater(balance, Decimal("5e-12"))
        response_item = item("synthetic-single", "0.5", "0.5",
                             CHECKER_MODULE._number(alpha), CHECKER_MODULE._number(beta), "1")
        checked = CHECKER_MODULE._check_item(
            response_item, "single_test_unconditional_v1", "generic", {}
        )
        self.assertEqual(checked["status"], "FAIL")
        self.assertIn("reported original residual exceeds", checked["message"])

    def test_single_certificate_rejects_fake_hull_and_public_residual_tamper(self):
        result = item("single-oracle", "0.25", "0.25", "0.16666666666666667", "0.5", "0.5")
        attach_certificate(result, "single_test_unconditional_v1")
        self.assertEqual(CHECKER_MODULE._check_item(result, "single_test_unconditional_v1", "generic", {})["status"], "PASS")
        original = list(result["diagnostics"]["notes"])
        public_alpha = result["alpha"]
        result["diagnostics"]["notes"] = [
            ("reported_alpha_lo="+public_alpha if value.startswith("reported_alpha_lo=") else
             "reported_alpha_hi="+public_alpha if value.startswith("reported_alpha_hi=") else
             "reported_alpha_span=0" if value.startswith("reported_alpha_span=") else value)
            for value in original
        ]
        fake_hull_checked = CHECKER_MODULE._check_item(result, "single_test_unconditional_v1", "generic", {})
        self.assertEqual(fake_hull_checked["status"], "FAIL")
        self.assertIn("reported_alpha certificate is not the minimal root/public hull", fake_hull_checked["message"])
        result["diagnostics"]["notes"] = original
        public_alpha = Decimal(result["alpha"])
        fake_lo, fake_hi = public_alpha+Decimal("5e-13"), public_alpha+Decimal("6e-13")
        replacements = {
            "root_alpha_lo": fake_lo, "root_alpha_hi": fake_hi, "root_alpha_span": fake_hi-fake_lo,
            "reported_alpha_lo": public_alpha, "reported_alpha_hi": fake_hi,
            "reported_alpha_span": fake_hi-public_alpha,
        }
        result["diagnostics"]["notes"] = [
            key+"="+CHECKER_MODULE._certificate_number(replacements[key])
            if (key := value.split("=", 1)[0]) in replacements else value
            for value in original
        ]
        fake_root_checked = CHECKER_MODULE._check_item(result, "single_test_unconditional_v1", "generic", {})
        self.assertEqual(fake_root_checked["status"], "FAIL")
        self.assertIn("single closed-form roots are outside supplied root certificate", fake_root_checked["message"])
        result["diagnostics"]["notes"] = original
        result["diagnostics"]["residuals"]["equation_1_abs"] = "0"
        self.assertEqual(CHECKER_MODULE._check_item(result, "single_test_unconditional_v1", "generic", {})["status"], "FAIL")

    def test_file_access_monitor_restricts_checker_to_declared_inputs(self):
        """Pure monitor: no forbidden file is read to construct this test."""
        import builtins
        response = self.canonical_response()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            response_path = td_path/"response.json"
            report_path = td_path/"report.json"
            response_path.write_text(json.dumps(response), encoding="utf-8")
            allowed = {path.resolve() for path in (response_path, PARAMETERS, SCHEMA, PACKAGE, report_path)}
            opened = []
            original_open = builtins.open
            original_path_open = Path.open
            def monitored_open(file, *args, **kwargs):
                resolved = Path(file).resolve()
                opened.append(resolved)
                if resolved not in allowed:
                    raise AssertionError(f"forbidden open: {resolved}")
                return original_open(file, *args, **kwargs)
            def monitored_path_open(path_self, *args, **kwargs):
                return monitored_open(path_self, *args, **kwargs)
            builtins.open = monitored_open
            Path.open = monitored_path_open
            try:
                code = CHECKER_MODULE.main([
                    "--response", str(response_path), "--parameters", str(PARAMETERS),
                    "--schema", str(SCHEMA), "--task-package", str(PACKAGE),
                    "--report", str(report_path),
                ])
            finally:
                Path.open = original_path_open
                builtins.open = original_open
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["checker_status"], "PASS")
            self.assertTrue(set(opened).issubset(allowed))

    def test_cli_rejects_request_option_before_opening_it(self):
        with tempfile.TemporaryDirectory() as td:
            report = Path(td)/"report.json"
            report.write_bytes(b"sentinel")
            with self.assertRaises(SystemExit) as caught:
                CHECKER_MODULE.main([
                    "--response", str(Path(td)/"response.json"), "--parameters", str(PARAMETERS),
                    "--schema", str(SCHEMA), "--task-package", str(PACKAGE),
                    "--report", str(report), "--request", str(Path(td)/"must_not_open.json"),
                ])
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(report.read_bytes(), b"sentinel")


if __name__ == "__main__":
    unittest.main()
