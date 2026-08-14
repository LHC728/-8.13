"""Unit tests for G3-SPEC-V1.0 sections 4/5 (CR-V3.1/C13, C14):
lifetime_regeneration_v1 (stdlib only, Python 3.12).

Frozen-contract coverage (the 12 required points plus extras):

  1. F(120) = F_120 and F(240) = F_240 for all four resources (P018-P025)
  2. inverse-CDF three branches hit: 0-120 h, 120-240 h, U > F(240)
     right-censored
  3. node neighborhoods below/above 120 and 240 (CDF and inverse CDF)
  4. U > F(240) -> is_right_censored = True, no renormalization of the
     [0,240] CDF
  5. a+d three boundaries: < 240 / = 240 / > 240
  6. = 240 completion-settles-first semantic marker
  7. preventive decision: a >= tau_pm prevents; NO_PM never; mandatory
     priority; legal-idle-decision-point constraint
  8. calibration durations correct (30/20/20/40 min), not counting age,
     no-cross-shift marker; parameters.csv row consistency
  9. exactly one U_L per (resource, generation): same pair -> same lifetime,
     generation change -> different lifetime
 10. illegal crossing of 240 h triggers the mandatory-interrupt fallback
 11. constant-hazard sensitivity functions independently usable (h1/h2,
     exponential sampling, piecewise-constant-hazard inverse CDF)
 12. no binary float in any canonical path (runtime types + AST source scan)

Plus: input validation (float rejection, out-of-range ages/durations/tau_pm),
failure-impact fragment accounting, frozen-parameter queries and the
parameters.csv audit helper. No formal competition numbers are produced; all
expectations derive from the frozen G3-SPEC-V1.0 sections 4/5/7 and
parameters.csv.
"""

from __future__ import annotations

import ast
import math
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
CODE_DIR = BASE / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from g3 import key_schema_v1 as ks  # noqa: E402
from g3 import lifetime_regeneration_v1 as lr  # noqa: E402

PARAMS_CSV = BASE / "02_数据" / "parameters.csv"
SOURCE_PATH = Path(lr.__file__)

SEED = 20260814
REP = 3
NS = ks.NAMESPACE_H1_TUNING

# Frozen CDF nodes, independently restated from parameters.csv P018-P025.
RESOURCE_CDF: dict[str, tuple[Fraction, Fraction]] = {
    "A": (Fraction(3, 100), Fraction(5, 100)),  # P018 / P022
    "B": (Fraction(4, 100), Fraction(7, 100)),  # P019 / P023
    "C": (Fraction(2, 100), Fraction(6, 100)),  # P020 / P024
    "E": (Fraction(3, 100), Fraction(5, 100)),  # P021 / P025
}

# Frozen calibration durations in minutes, restated from P010-P013.
RESOURCE_CAL_MINUTES: dict[str, Fraction] = {
    "A": Fraction(30, 1),
    "B": Fraction(20, 1),
    "C": Fraction(20, 1),
    "E": Fraction(40, 1),
}


def _first_non_censored_generation(
    resource: str, start: int = 1, bound: int = 5000
) -> tuple[int, tuple[Fraction | None, bool]]:
    """Deterministic scan (fixed seed): first generation >= ``start`` whose
    frozen-parameter sampled lifetime is NOT right-censored.

    With the frozen nodes P(F(240) <= 0.07) the probability that no
    generation in [start, bound) is non-censored is <= 0.95^4999 ~ 1e-112;
    SHA256 is treated as a random oracle (the same practical-determinism
    assumption the sibling key_schema tests rely on).
    """
    for gen in range(start, bound):
        sample = lr.sample_lifetime_frozen(NS, REP, resource, gen, SEED)
        if not sample[1]:
            return gen, sample
    raise AssertionError(
        f"no non-censored generation found for resource {resource!r} in "
        f"[{start}, {bound})"
    )


def _module_ast() -> ast.Module:
    return ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))


def _function_bodies_float_free() -> dict[str, list[str]]:
    """AST scan: every function whose name does not start with
    ``sensitivity_`` must contain no float literal, no ``float(...)`` call
    and no ``math.*`` call in its body (binary float is forbidden in the
    canonical path). Returns {function_name: [violation descriptions]}.
    """
    violations: dict[str, list[str]] = {}
    tree = _module_ast()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("sensitivity_"):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, float):
                violations.setdefault(node.name, []).append(
                    f"float literal {sub.value!r} at line {sub.lineno}"
                )
            elif isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Name) and func.id == "float":
                    violations.setdefault(node.name, []).append(
                        f"float() call at line {sub.lineno}"
                    )
                elif (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "math"
                ):
                    violations.setdefault(node.name, []).append(
                        f"math.{func.attr}() call at line {sub.lineno}"
                    )
    return violations


class PiecewiseLinearCDFTests(unittest.TestCase):
    """C13 main model: F(t) exact, node hits, neighborhoods (items 1, 3)."""

    def test_f120_f240_nodes_all_four_resources(self):
        # Requirement 1: F(120) = F_120, F(240) = F_240 for A/B/C/E.
        for resource, (f120, f240) in RESOURCE_CDF.items():
            with self.subTest(resource=resource):
                self.assertEqual(
                    lr.piecewise_linear_f(Fraction(120), f120, f240), f120
                )
                self.assertEqual(
                    lr.piecewise_linear_f(Fraction(240), f120, f240), f240
                )
                # frozen-parameter query matches the CSV-derived node
                self.assertEqual(lr.frozen_f120(resource), f120)
                self.assertEqual(lr.frozen_f240(resource), f240)

    def test_segment_formulas_exact(self):
        # F(60) = F_120/2 (first segment midpoint); F(180) = midpoint node.
        f120, f240 = RESOURCE_CDF["A"]
        self.assertEqual(
            lr.piecewise_linear_f(Fraction(60), f120, f240), f120 / 2
        )
        self.assertEqual(
            lr.piecewise_linear_f(Fraction(180), f120, f240),
            (f120 + f240) / 2,
        )

    def test_neighborhood_below_above_120(self):
        # Requirement 3: continuity and monotonicity across the 120 h node.
        f120, f240 = RESOURCE_CDF["A"]
        t_below = Fraction(11995, 100)  # 119.95 h
        t_above = Fraction(12005, 100)  # 120.05 h
        f_below = lr.piecewise_linear_f(t_below, f120, f240)
        f_mid = lr.piecewise_linear_f(Fraction(120), f120, f240)
        f_above = lr.piecewise_linear_f(t_above, f120, f240)
        self.assertEqual(f_mid, f120)
        self.assertLess(f_below, f_mid)
        self.assertLess(f_mid, f_above)
        # both branches agree at the node (continuity by construction)
        self.assertEqual(f120 * Fraction(120) / Fraction(120), f_mid)
        self.assertEqual(
            f120 + (f240 - f120) * (t_above - Fraction(120)) / Fraction(120),
            f_above,
        )

    def test_neighborhood_below_240_and_out_of_range(self):
        f120, f240 = RESOURCE_CDF["B"]
        t_below = Fraction(23995, 100)
        self.assertLess(lr.piecewise_linear_f(t_below, f120, f240), f240)
        self.assertEqual(
            lr.piecewise_linear_f(Fraction(240), f120, f240), f240
        )
        with self.assertRaises(ValueError):
            lr.piecewise_linear_f(Fraction(240) + Fraction(1, 1000), f120, f240)
        with self.assertRaises(ValueError):
            lr.piecewise_linear_f(Fraction(-1), f120, f240)
        with self.assertRaises(TypeError):
            lr.piecewise_linear_f(119.95, f120, f240)  # binary float rejected
        with self.assertRaises(ValueError):
            lr.piecewise_linear_f(Fraction(60), f120, f120)  # f120==f240


class InverseCDFTests(unittest.TestCase):
    """C13 inverse CDF: three branches, boundaries, right censoring
    (items 2, 3, 4)."""

    def test_three_branches_all_resources(self):
        # Requirement 2: one U in each branch for every resource.
        for resource, (f120, f240) in RESOURCE_CDF.items():
            with self.subTest(resource=resource):
                u_low = f120 / 2  # -> branch 0..120
                t_low, c_low = lr.inverse_cdf(u_low, f120, f240)
                self.assertFalse(c_low)
                self.assertEqual(t_low, Fraction(120) * u_low / f120)
                self.assertGreater(t_low, Fraction(0))
                self.assertLessEqual(t_low, Fraction(120))

                u_mid = (f120 + f240) / 2  # -> branch 120..240
                t_mid, c_mid = lr.inverse_cdf(u_mid, f120, f240)
                self.assertFalse(c_mid)
                self.assertEqual(
                    t_mid,
                    Fraction(120)
                    + Fraction(120) * (u_mid - f120) / (f240 - f120),
                )
                self.assertGreater(t_mid, Fraction(120))
                self.assertLessEqual(t_mid, Fraction(240))

                u_high = (f240 + Fraction(1)) / 2  # U > F(240)
                t_high, c_high = lr.inverse_cdf(u_high, f120, f240)
                self.assertTrue(c_high)
                self.assertIsNone(t_high)

    def test_branch_boundaries_exact(self):
        # U == F_120 -> t = 120; U == F_240 -> t = 240.
        f120, f240 = RESOURCE_CDF["C"]
        t1, c1 = lr.inverse_cdf(f120, f120, f240)
        self.assertEqual((t1, c1), (Fraction(120), False))
        t2, c2 = lr.inverse_cdf(f240, f120, f240)
        self.assertEqual((t2, c2), (Fraction(240), False))

    def test_inverse_neighborhood_around_nodes(self):
        # Requirement 3 (inverse side): below/above the nodes.
        f120, f240 = RESOURCE_CDF["A"]
        eps = Fraction(1, 10000)
        t_lo, _ = lr.inverse_cdf(f120 - eps, f120, f240)
        t_hi, _ = lr.inverse_cdf(f120 + eps, f120, f240)
        self.assertLess(t_lo, Fraction(120))
        self.assertGreater(t_hi, Fraction(120))
        t_mid_lo, _ = lr.inverse_cdf(f240 - eps, f120, f240)
        self.assertLess(t_mid_lo, Fraction(240))
        t_mid_hi, c_hi = lr.inverse_cdf(f240 + eps, f120, f240)
        self.assertTrue(c_hi)
        self.assertIsNone(t_mid_hi)

    def test_right_censored_no_renormalization(self):
        # Requirement 4: U > F(240) -> right-censored; the [0,240] CDF is
        # never renormalized onto U in [0, F(240)].
        f120, f240 = RESOURCE_CDF["A"]
        u = Fraction(9, 10)
        self.assertGreater(u, f240)
        t, censored = lr.inverse_cdf(u, f120, f240)
        self.assertIsNone(t)
        self.assertTrue(censored)
        # raw U stays raw: the renormalized value u / F(240) = 18 would lie
        # outside [0, 1) and is rejected -- i.e. renormalization is not
        # applied anywhere in this branch.
        with self.assertRaises(ValueError):
            lr.inverse_cdf(u / f240, f120, f240)
        # every U above F(240) is censored, none maps back into [0,240]
        for k in range(1, 10):
            uu = f240 + Fraction(k, 1000)
            self.assertTrue(uu > f240)
            t, censored = lr.inverse_cdf(uu, f120, f240)
            self.assertIsNone(t)
            self.assertTrue(censored)

    def test_invalid_u_rejected(self):
        f120, f240 = RESOURCE_CDF["A"]
        with self.assertRaises(ValueError):
            lr.inverse_cdf(Fraction(1), f120, f240)  # u == 1 not in [0,1)
        with self.assertRaises(ValueError):
            lr.inverse_cdf(Fraction(-1, 2), f120, f240)
        with self.assertRaises(TypeError):
            lr.inverse_cdf(0.5, f120, f240)  # binary float rejected


class SampleLifetimeTests(unittest.TestCase):
    """C13 per-generation single U_L via key_schema_v1.u_l (item 9)."""

    def test_one_u_l_per_generation_same_value(self):
        # Requirement 9: the same (namespace, rep, resource, generation)
        # consumes exactly one U_L and yields the same lifetime.
        f120, f240 = RESOURCE_CDF["A"]
        r1 = lr.sample_lifetime(NS, REP, "A", 1, SEED, f120, f240)
        r2 = lr.sample_lifetime(NS, REP, "A", 1, SEED, f120, f240)
        self.assertEqual(r1, r2)
        # equals inverse_cdf of the keyed U_L
        u = ks.u_l(NS, REP, "A", 1, SEED)
        self.assertEqual(r1, lr.inverse_cdf(u, f120, f240))

    def test_generation_change_changes_lifetime(self):
        # Requirement 9: a different generation consumes a different U_L,
        # and two distinct interior U map to distinct lifetimes (the inverse
        # CDF is strictly increasing in both branches).
        u1 = ks.u_l(NS, REP, "A", 1, SEED)
        u2 = ks.u_l(NS, REP, "A", 2, SEED)
        self.assertNotEqual(u1, u2)
        # injectivity of the inverse CDF on the interior (synthetic U)
        f120, f240 = RESOURCE_CDF["A"]
        ta, _ = lr.inverse_cdf(f120 / 2, f120, f240)
        tb, _ = lr.inverse_cdf(f120 / 3, f120, f240)
        self.assertNotEqual(ta, tb)
        # real sampled generations: two distinct non-censored draws differ
        gen1, r1 = _first_non_censored_generation("A", 1)
        gen2, r2 = _first_non_censored_generation("A", gen1 + 1)
        self.assertNotEqual(gen1, gen2)
        self.assertIsInstance(r1[0], Fraction)
        self.assertIsInstance(r2[0], Fraction)
        self.assertNotEqual(r1, r2)

    def test_resource_slot_distinct(self):
        # different resource -> different U_L stream slot; with both draws
        # in the interior branch the lifetimes differ.
        u_a = ks.u_l(NS, REP, "A", 1, SEED)
        u_e = ks.u_l(NS, REP, "E", 1, SEED)
        self.assertNotEqual(u_a, u_e)
        _, la = _first_non_censored_generation("A", 1)
        _, le = _first_non_censored_generation("E", 1)
        self.assertIsInstance(la[0], Fraction)
        self.assertIsInstance(le[0], Fraction)
        self.assertNotEqual(la, le)

    def test_sample_lifetime_frozen_consistent_with_explicit(self):
        for resource in "ABCE":
            with self.subTest(resource=resource):
                f120, f240 = RESOURCE_CDF[resource]
                explicit = lr.sample_lifetime(NS, REP, resource, 4, SEED, f120, f240)
                frozen = lr.sample_lifetime_frozen(NS, REP, resource, 4, SEED)
                self.assertEqual(explicit, frozen)
        # right-censored shape is allowed (U > F(240)) and is (None, True)
        t, censored = lr.sample_lifetime_frozen(NS, REP, "B", 4, SEED)
        if t is None:
            self.assertTrue(censored)
        else:
            self.assertFalse(censored)
            self.assertIsInstance(t, Fraction)

    def test_invalid_resource_rejected(self):
        with self.assertRaises(ValueError):
            lr.sample_lifetime(NS, REP, "D", 1, SEED, *RESOURCE_CDF["A"])
        with self.assertRaises(ValueError):
            lr.frozen_f120("X")


class ReplacementDecisionTests(unittest.TestCase):
    """C14/C26 decision seam: a+d boundaries, preventive rules (items 5, 6,
    7)."""

    def test_a_plus_d_three_boundaries(self):
        # Requirement 5: a+d < 240 / = 240 / > 240.
        a = Fraction(100)
        self.assertEqual(
            lr.replacement_decision(a, Fraction(139), lr.NO_PM_BEFORE_MANDATORY, True),
            lr.ReplacementDecision.SERVE_HEAD,  # 239 < 240
        )
        self.assertEqual(
            lr.replacement_decision(a, Fraction(140), lr.NO_PM_BEFORE_MANDATORY, True),
            lr.ReplacementDecision.EXACT_240_COMPLETE_FIRST,  # = 240
        )
        self.assertEqual(
            lr.replacement_decision(a, Fraction(141), lr.NO_PM_BEFORE_MANDATORY, True),
            lr.ReplacementDecision.MANDATORY_REPLACE_FIRST,  # 241 > 240
        )

    def test_exact_240_completion_first_marker(self):
        # Requirement 6: a+d == 240 carries the completion-settles-first
        # semantic marker (E: may complete; completion first, then replace).
        decision = lr.replacement_decision(
            Fraction(120), Fraction(120), Fraction(120), True
        )
        self.assertIs(decision, lr.ReplacementDecision.EXACT_240_COMPLETE_FIRST)
        self.assertEqual(decision.name, "EXACT_240_COMPLETE_FIRST")
        self.assertEqual(decision.value, "exact_240_complete_first")
        # the enum's frozen documentation states the completion-first rule
        doc = lr.ReplacementDecision.__doc__ or ""
        self.assertIn("EXACT_240_COMPLETE_FIRST", doc)
        self.assertIn("completion", doc.lower())
        self.assertIn("settled first", doc.lower())

    def test_preventive_requires_idle_decision_point(self):
        # Requirement 7: preventive only at a legal idle decision point (A).
        a, d, tau = Fraction(130), Fraction(10), Fraction(120)
        self.assertEqual(
            lr.replacement_decision(a, d, tau, True),
            lr.ReplacementDecision.PREVENTIVE_REPLACE,
        )
        self.assertEqual(
            lr.replacement_decision(a, d, tau, False),
            lr.ReplacementDecision.SERVE_HEAD,
        )

    def test_preventive_age_boundary_inclusive(self):
        # a == tau_pm (>=) triggers preventive; a < tau_pm does not.
        self.assertEqual(
            lr.replacement_decision(Fraction(120), Fraction(10), Fraction(120), True),
            lr.ReplacementDecision.PREVENTIVE_REPLACE,
        )
        self.assertEqual(
            lr.replacement_decision(Fraction(119), Fraction(10), Fraction(120), True),
            lr.ReplacementDecision.SERVE_HEAD,
        )

    def test_no_pm_never_prevents(self):
        # Requirement 7 (G): NO_PM_BEFORE_MANDATORY never prevents, even at
        # an idle decision point with a large age (d kept small so every
        # a+d stays strictly below 240 and mandatory rules do not fire).
        for a in (Fraction(130), Fraction(200), Fraction(239)):
            with self.subTest(a=a):
                self.assertEqual(
                    lr.replacement_decision(
                        a, Fraction(1, 2), lr.NO_PM_BEFORE_MANDATORY, True
                    ),
                    lr.ReplacementDecision.SERVE_HEAD,
                )

    def test_mandatory_priority_over_preventive(self):
        # Requirement 7 (D): mandatory replacement outranks preventive choice.
        for tau in (Fraction(120), Fraction(216), lr.NO_PM_BEFORE_MANDATORY):
            with self.subTest(tau=tau):
                self.assertEqual(
                    lr.replacement_decision(Fraction(239), Fraction(2), tau, True),
                    lr.ReplacementDecision.MANDATORY_REPLACE_FIRST,
                )
        # age exactly 240 with any positive d is also mandatory
        self.assertEqual(
            lr.replacement_decision(
                Fraction(240), Fraction(1), lr.NO_PM_BEFORE_MANDATORY, True
            ),
            lr.ReplacementDecision.MANDATORY_REPLACE_FIRST,
        )

    def test_validation_rejects_invalid_inputs(self):
        tau = Fraction(120)
        with self.assertRaises(ValueError):
            lr.replacement_decision(Fraction(240) + Fraction(1), Fraction(1), tau, True)
        with self.assertRaises(ValueError):
            lr.replacement_decision(Fraction(-1), Fraction(1), tau, True)
        with self.assertRaises(ValueError):
            lr.replacement_decision(Fraction(100), Fraction(0), tau, True)
        with self.assertRaises(ValueError):
            lr.replacement_decision(Fraction(100), Fraction(-1), tau, True)
        with self.assertRaises(TypeError):
            lr.replacement_decision(100.5, Fraction(1), tau, True)  # float age
        with self.assertRaises(TypeError):
            lr.replacement_decision(Fraction(100), Fraction(1), tau, 1)  # not bool
        # 240 is mandatory semantics, never a preventive threshold
        with self.assertRaises(ValueError):
            lr.replacement_decision(Fraction(100), Fraction(1), Fraction(240), True)
        # tau_pm below the legal preventive domain
        with self.assertRaises(ValueError):
            lr.replacement_decision(Fraction(100), Fraction(1), Fraction(119), True)
        # a fractional tau in [120, 240) is legal
        self.assertIsInstance(
            lr.replacement_decision(
                Fraction(130), Fraction(10), Fraction(241, 2), True
            ),
            lr.ReplacementDecision,
        )


class CalibrationTests(unittest.TestCase):
    """C14 calibration: durations, not counting age, no cross-shift
    (item 8); parameters.csv frozen-row consistency."""

    def test_durations_minutes_and_hours(self):
        # Requirement 8: 30/20/20/40 min for A/B/C/E.
        for resource, minutes in RESOURCE_CAL_MINUTES.items():
            with self.subTest(resource=resource):
                self.assertEqual(
                    lr.calibration_duration_minutes(resource), minutes
                )
                self.assertEqual(
                    lr.calibration_duration_hours(resource),
                    minutes / Fraction(60),
                )
        self.assertEqual(lr.calibration_duration_hours("A"), Fraction(1, 2))
        self.assertEqual(lr.calibration_duration_hours("B"), Fraction(1, 3))
        self.assertEqual(lr.calibration_duration_hours("C"), Fraction(1, 3))
        self.assertEqual(lr.calibration_duration_hours("E"), Fraction(2, 3))

    def test_calibration_semantics_markers(self):
        # Requirement 8: calibration does not count device test age and is
        # not allowed to cross a shift (P062 nonpreemptive_within_shift_v1).
        self.assertFalse(lr.CALIBRATION_COUNTS_AGE)
        self.assertFalse(lr.CALIBRATION_CROSS_SHIFT_ALLOWED)

    def test_parameters_csv_frozen_values(self):
        # The module constants must exactly match parameters.csv rows
        # P010-P013, P016-P017, P018-P025.
        self.assertTrue(PARAMS_CSV.is_file())
        verified = lr.validate_parameters_csv(PARAMS_CSV)
        self.assertEqual(verified["P010"], Fraction(30))
        self.assertEqual(verified["P013"], Fraction(40))
        self.assertEqual(verified["P018"], Fraction(3, 100))
        self.assertEqual(verified["P023"], Fraction(7, 100))
        self.assertEqual(verified["P016"], Fraction(120))
        self.assertEqual(verified["P017"], Fraction(240))
        self.assertEqual(set(verified), set(lr.FROZEN_CSV_ROWS))

    def test_parameters_csv_mismatch_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "parameters.csv"
            stub.write_text(
                "parameter_id,value\n"
                "P010,30\n"
                "P011,20\n"
                "P012,20\n"
                "P013,40\n"
                "P016,120\n"
                "P017,240\n"
                "P018,0.03\n"
                "P019,0.04\n"
                "P020,0.02\n"
                "P021,0.03\n"
                "P022,0.05\n"
                "P023,0.99\n"  # drifted from 0.07
                "P024,0.06\n"
                "P025,0.05\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                lr.validate_parameters_csv(stub)
            stub.write_text(
                "parameter_id,value\nP010,30\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                lr.validate_parameters_csv(stub)  # missing rows


class FallbackTests(unittest.TestCase):
    """C14 illegal-crossing backstop (item 10)."""

    def test_illegal_crossing_triggers(self):
        # Requirement 10: a running task whose end crosses 240 h is force
        # interrupted at age 240 with the correct fragment accounting.
        outcome = lr.mandatory_240_interrupt_fallback(Fraction(239), Fraction(2))
        self.assertTrue(outcome.triggered)
        self.assertEqual(outcome.interrupt_age_h, Fraction(240))
        self.assertEqual(outcome.fragment_duration_h, Fraction(1))
        self.assertTrue(outcome.no_observation)
        self.assertTrue(outcome.attempt_unchanged)
        self.assertTrue(outcome.device_unavailable_after)
        self.assertTrue(outcome.replacement_required_after)
        # a deeper illegal crossing
        outcome2 = lr.mandatory_240_interrupt_fallback(Fraction(100), Fraction(200))
        self.assertTrue(outcome2.triggered)
        self.assertEqual(outcome2.fragment_duration_h, Fraction(140))

    def test_legal_tasks_do_not_trigger(self):
        # a_start + d == 240 is legal (completion settles first); < 240 legal.
        self.assertFalse(
            lr.mandatory_240_interrupt_fallback(Fraction(100), Fraction(140)).triggered
        )
        self.assertFalse(
            lr.mandatory_240_interrupt_fallback(Fraction(100), Fraction(139)).triggered
        )
        self.assertFalse(
            lr.mandatory_240_interrupt_fallback(Fraction(0), Fraction(1)).triggered
        )

    def test_illegal_start_state_rejected(self):
        with self.assertRaises(ValueError):
            lr.mandatory_240_interrupt_fallback(Fraction(240), Fraction(1))
        with self.assertRaises(ValueError):
            lr.mandatory_240_interrupt_fallback(Fraction(241), Fraction(1))
        with self.assertRaises(ValueError):
            lr.mandatory_240_interrupt_fallback(Fraction(100), Fraction(0))


class FailureImpactTests(unittest.TestCase):
    """C14 random-failure fragment semantics."""

    def test_failure_before_completion_interrupts(self):
        outcome = lr.failure_impact(
            Fraction(50), Fraction(10), Fraction(55), False
        )
        self.assertTrue(outcome.interrupted)
        self.assertEqual(outcome.fragment_duration_h, Fraction(5))
        self.assertTrue(outcome.no_observation)
        self.assertTrue(outcome.attempt_unchanged)
        self.assertTrue(outcome.device_unavailable_after)
        self.assertTrue(outcome.replacement_required_after)

    def test_failure_at_end_settles_completion_first(self):
        # same-instant: completion settles first (section 5 event_order)
        outcome = lr.failure_impact(
            Fraction(50), Fraction(10), Fraction(60), False
        )
        self.assertFalse(outcome.interrupted)

    def test_no_failure_within_task_completes(self):
        outcome = lr.failure_impact(
            Fraction(50), Fraction(10), Fraction(61), False
        )
        self.assertFalse(outcome.interrupted)
        self.assertIsNone(outcome.fragment_duration_h)

    def test_right_censored_never_interrupts(self):
        outcome = lr.failure_impact(Fraction(50), Fraction(10), None, True)
        self.assertFalse(outcome.interrupted)
        with self.assertRaises(ValueError):
            lr.failure_impact(Fraction(50), Fraction(10), Fraction(55), True)

    def test_inconsistent_lifetime_rejected(self):
        with self.assertRaises(ValueError):
            lr.failure_impact(Fraction(60), Fraction(10), Fraction(55), False)
        with self.assertRaises(ValueError):
            lr.failure_impact(Fraction(60), Fraction(10), Fraction(60), False)


class SensitivityTests(unittest.TestCase):
    """C13 constant-hazard sensitivity constructs, independent of the main
    path (item 11)."""

    def test_h1_h2_formulas(self):
        f120, f240 = RESOURCE_CDF["A"]
        h1, h2 = lr.sensitivity_h1_h2(f120, f240)
        f1, f2 = float(f120), float(f240)
        expected_h1 = -math.log(1.0 - f1) / 120.0
        expected_h2 = -math.log((1.0 - f2) / (1.0 - f1)) / 120.0
        self.assertAlmostEqual(h1, expected_h1, places=12)
        self.assertAlmostEqual(h2, expected_h2, places=12)
        self.assertGreater(h1, 0.0)
        self.assertGreater(h2, 0.0)

    def test_exponential_sample(self):
        h1, _ = lr.sensitivity_h1_h2(*RESOURCE_CDF["A"])
        u = Fraction(1, 2)
        t = lr.sensitivity_exponential_sample(h1, u)
        self.assertAlmostEqual(t, -math.log(1.0 - 0.5) / h1, places=12)
        self.assertGreater(t, 0.0)
        with self.assertRaises(ValueError):
            lr.sensitivity_exponential_sample(0.0, u)
        with self.assertRaises(TypeError):
            lr.sensitivity_exponential_sample(True, u)

    def test_constant_hazard_inverse_cdf_hits_nodes(self):
        f120, f240 = RESOURCE_CDF["B"]
        t_at_f120, c1 = lr.sensitivity_constant_hazard_inverse_cdf(f120, f120, f240)
        self.assertFalse(c1)
        self.assertAlmostEqual(t_at_f120, 120.0, places=9)
        t_at_f240, c2 = lr.sensitivity_constant_hazard_inverse_cdf(f240, f120, f240)
        self.assertFalse(c2)
        self.assertAlmostEqual(t_at_f240, 240.0, places=9)
        # three branches
        t_low, c_low = lr.sensitivity_constant_hazard_inverse_cdf(
            f120 / 2, f120, f240
        )
        self.assertFalse(c_low)
        self.assertGreater(t_low, 0.0)
        self.assertLess(t_low, 120.0)
        t_mid, c_mid = lr.sensitivity_constant_hazard_inverse_cdf(
            (f120 + f240) / 2, f120, f240
        )
        self.assertFalse(c_mid)
        self.assertGreater(t_mid, 120.0)
        self.assertLess(t_mid, 240.0)
        t_high, c_high = lr.sensitivity_constant_hazard_inverse_cdf(
            (f240 + Fraction(1)) / 2, f120, f240
        )
        self.assertIsNone(t_high)
        self.assertTrue(c_high)

    def test_sensitivity_never_enters_main_path(self):
        # main-path results are exact regardless of the sensitivity values
        f120, f240 = RESOURCE_CDF["A"]
        t, censored = lr.inverse_cdf(f120 / 2, f120, f240)
        self.assertIsInstance(t, Fraction)
        self.assertEqual(t, Fraction(60))


class NoFloatCanonicalTests(unittest.TestCase):
    """Requirement 12: no binary float in any canonical path."""

    def test_main_path_outputs_are_fractions(self):
        f120, f240 = RESOURCE_CDF["A"]
        self.assertIsInstance(lr.piecewise_linear_f(Fraction(90), f120, f240), Fraction)
        t, censored = lr.inverse_cdf(f120 / 2, f120, f240)
        self.assertIsInstance(t, Fraction)
        self.assertIs(type(t), Fraction)
        self.assertIsInstance(lr.calibration_duration_hours("E"), Fraction)
        self.assertIsInstance(lr.frozen_f120("A"), Fraction)
        self.assertIsInstance(lr.frozen_f240("A"), Fraction)
        lt, lc = lr.sample_lifetime(NS, REP, "A", 1, SEED, f120, f240)
        self.assertTrue(lt is None or isinstance(lt, Fraction))
        self.assertIsInstance(lc, bool)
        decision = lr.replacement_decision(
            Fraction(130), Fraction(10), Fraction(120), True
        )
        self.assertIsInstance(decision, lr.ReplacementDecision)
        # outcomes carry Fraction durations when triggered
        fb = lr.mandatory_240_interrupt_fallback(Fraction(239), Fraction(2))
        self.assertIsInstance(fb.fragment_duration_h, Fraction)

    def test_source_has_no_float_in_canonical_functions(self):
        violations = _function_bodies_float_free()
        self.assertEqual(
            violations, {}, f"binary float found in canonical functions: {violations}"
        )
        # sanity: the sensitivity functions are exempt but do exist
        self.assertTrue(hasattr(lr, "sensitivity_h1_h2"))
        self.assertTrue(hasattr(lr, "sensitivity_exponential_sample"))
        self.assertTrue(hasattr(lr, "sensitivity_constant_hazard_inverse_cdf"))


class PublicAPIContractTests(unittest.TestCase):
    """Smoke: the required public API surface exists and is pure."""

    REQUIRED = [
        "piecewise_linear_f",
        "inverse_cdf",
        "sample_lifetime",
        "replacement_decision",
        "mandatory_240_interrupt_fallback",
        "calibration_duration_minutes",
        "calibration_duration_hours",
        "sensitivity_h1_h2",
        "sensitivity_exponential_sample",
        "sensitivity_constant_hazard_inverse_cdf",
        "frozen_f120",
        "frozen_f240",
        "NO_PM_BEFORE_MANDATORY",
        "ReplacementDecision",
        "IllegalCrossingOutcome",
        "FailureImpactOutcome",
        "validate_parameters_csv",
        "failure_impact",
    ]

    def test_required_api_present(self):
        for name in self.REQUIRED:
            with self.subTest(name=name):
                self.assertTrue(hasattr(lr, name), f"missing public API {name}")

    def test_decision_enum_members(self):
        for member in (
            "PREVENTIVE_REPLACE",
            "SERVE_HEAD",
            "MANDATORY_REPLACE_FIRST",
            "EXACT_240_COMPLETE_FIRST",
        ):
            with self.subTest(member=member):
                self.assertTrue(hasattr(lr.ReplacementDecision, member))

    def test_no_pm_is_sentinel_not_240(self):
        # NO_PM_BEFORE_MANDATORY is an independent policy baseline, not a
        # numeric tau_pm; numeric 240 is rejected as a preventive threshold.
        self.assertIsNot(lr.NO_PM_BEFORE_MANDATORY, Fraction(240))
        with self.assertRaises(ValueError):
            lr.replacement_decision(
                Fraction(100), Fraction(1), Fraction(240), True
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
