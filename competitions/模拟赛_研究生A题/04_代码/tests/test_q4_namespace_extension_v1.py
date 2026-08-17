#!/usr/bin/env python3
"""Q4 additive random-domain extension tests (HG-Q4-NS-01, 2026-08-17
OPTION A / ACCEPTED).

NS-01 legacy byte identity (six frozen namespaces: canonical key string
and U unchanged)
NS-02 q4_screening accepted (canonical_key + u_x/u_d/u_y/u_l)
NS-03 q4_evaluation accepted
NS-04 screening vs evaluation domain separation (different key/U)
NS-05 Q4 vs Q3 separation
NS-06 H2 firewall: Q4 namespaces rejected by u_*_post
NS-07 arbitrary namespace rejection (q4_fake / screening / foo)
NS-08 RandomDesConfig: q4_screening/q4_evaluation PASS; unknown FAIL CLOSED
NS-09 legacy RandomDesConfig regression (six namespaces unchanged)

Python 3.12, standard library only.
"""
from __future__ import annotations

import sys
import unittest
from fractions import Fraction
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from g3 import key_schema_v1 as ks  # noqa: E402
from g3 import lifetime_regeneration_v1 as lr  # noqa: E402
from g3 import random_des_v1 as rd  # noqa: E402

SEED = 7
REP = 3


def independent_expected_u(key: str) -> Fraction:
    """Frozen mapping recomputed independently (G3-SPEC-V1.0 section 3)."""
    import hashlib
    h = hashlib.sha256(key.encode("utf-8")).digest()[:8]
    head = int.from_bytes(h, "big")
    return Fraction(2 * head + 1, 1 << 65)


class TestLegacyByteIdentity(unittest.TestCase):
    def test_ns_01_legacy_namespaces_frozen(self):
        self.assertEqual(ks.NAMESPACES, (
            "development_unit", "pilot", "h1_tuning", "g3_holdout",
            "q2_formal", "q3_formal"))
        self.assertEqual(ks.ALL_NAMESPACES,
                         ks.NAMESPACES + ("h2_future",))
        self.assertEqual(ks.H2_NAMESPACES,
                         ("h2_tuning", "h2_holdout", "h2_rollout"))

    def test_ns_01_legacy_canonical_key_unchanged(self):
        # frozen canonical field order and serialization (byte-identity):
        # key_schema_v1 | master_seed | namespace | replicate_id | entity_id
        #              | process_or_subsystem | attempt_or_generation
        for ns in ks.NAMESPACES:
            key = ks.canonical_key(ns, REP, 7, "A", 1, SEED)
            expected = (f"key_schema_v1|i:{SEED}|s:{ns}|i:{REP}|i:7|s:A|i:1")
            self.assertEqual(key, expected, f"legacy key changed for {ns}")

    def test_ns_01_legacy_u_identical(self):
        for ns in ks.NAMESPACES:
            u = ks.u_x(ns, REP, 1, "A", SEED)
            key = ks.canonical_key(ns, REP, 1, "A", None, SEED)
            self.assertEqual(u, independent_expected_u(key), f"U_X changed for {ns}")
            self.assertEqual(u, ks.uniform_from_key(key))


class TestQ4NamespacesAccepted(unittest.TestCase):
    def test_ns_02_q4_screening_accepted(self):
        key = ks.canonical_key("q4_screening", REP, 7, "A", 1, SEED)
        self.assertIn("s:q4_screening|", key)
        self.assertEqual(ks.u_x("q4_screening", REP, 1, "A", SEED),
                         independent_expected_u(
                             ks.canonical_key("q4_screening", REP, 1, "A", None, SEED)))
        self.assertIsInstance(ks.u_d("q4_screening", REP, 1, SEED), Fraction)
        self.assertIsInstance(ks.u_y("q4_screening", REP, 1, "A", 1, SEED), Fraction)
        self.assertIsInstance(ks.u_l("q4_screening", REP, "A", 1, SEED), Fraction)

    def test_ns_03_q4_evaluation_accepted(self):
        key = ks.canonical_key("q4_evaluation", REP, 7, "A", 1, SEED)
        self.assertIn("s:q4_evaluation|", key)
        self.assertIsInstance(ks.u_x("q4_evaluation", REP, 1, "A", SEED), Fraction)
        self.assertIsInstance(ks.u_l("q4_evaluation", REP, "A", 1, SEED), Fraction)

    def test_ns_04_screening_evaluation_separation(self):
        k_s = ks.canonical_key("q4_screening", REP, 7, "A", 1, SEED)
        k_e = ks.canonical_key("q4_evaluation", REP, 7, "A", 1, SEED)
        self.assertNotEqual(k_s, k_e)
        self.assertNotEqual(ks.u_x("q4_screening", REP, 1, "A", SEED),
                            ks.u_x("q4_evaluation", REP, 1, "A", SEED))
        self.assertNotEqual(ks.u_l("q4_screening", REP, "A", 1, SEED),
                            ks.u_l("q4_evaluation", REP, "A", 1, SEED))

    def test_ns_05_q4_vs_q3_separation(self):
        self.assertNotEqual(ks.u_x("q3_formal", REP, 1, "A", SEED),
                            ks.u_x("q4_screening", REP, 1, "A", SEED))
        self.assertNotEqual(ks.u_x("q3_formal", REP, 1, "A", SEED),
                            ks.u_x("q4_evaluation", REP, 1, "A", SEED))


class TestFirewall(unittest.TestCase):
    def test_ns_06_h2_post_rejects_q4(self):
        for ns in ("q4_screening", "q4_evaluation"):
            calls = [
                lambda: ks.u_x_post(ns, REP, 1, "A", SEED),
                lambda: ks.u_d_post(ns, REP, 1, SEED),
                lambda: ks.u_y_post(ns, REP, 1, "A", 1, SEED),
                lambda: ks.u_l_post(ns, REP, "A", 1, SEED),
            ]
            for call in calls:
                with self.assertRaises(ValueError):
                    call()

    def test_ns_07_arbitrary_namespace_rejected(self):
        for bad in ("q4_fake", "screening", "foo"):
            with self.assertRaises(ValueError):
                ks.u_x(bad, REP, 1, "A", SEED)
            with self.assertRaises(ValueError):
                ks.u_l(bad, REP, "A", 1, SEED)

    def test_ns_07b_h2_not_in_physical(self):
        for ns in ("h2_tuning", "h2_holdout", "h2_rollout"):
            with self.assertRaises(ValueError):
                ks.u_x(ns, REP, 1, "A", SEED)


class TestRandomDesConfigNamespace(unittest.TestCase):
    def _cfg(self, ns: str):
        return rd.default_config(
            namespace=ns, master_seed=SEED, replicate_id=REP,
            tau_pm=lr.NO_PM_BEFORE_MANDATORY,
            observation_kernel={
                p: {"alpha": Fraction(1, 40), "beta": Fraction(1, 40)}
                for p in rd.RESOURCES},
            batch_size=2, scenario="q3_two_shift",
            shift_length_h="12", shifts_per_day=2)

    def test_ns_08_q4_configs_pass(self):
        for ns in ("q4_screening", "q4_evaluation"):
            cfg = self._cfg(ns)
            self.assertEqual(cfg.namespace, ns)

    def test_ns_08b_unknown_fails_closed(self):
        with self.assertRaises(rd.RandomDesConfigError):
            self._cfg("q4_fake")
        with self.assertRaises(rd.RandomDesConfigError):
            self._cfg("foo")

    def test_ns_09_legacy_configs_regression(self):
        for ns in ks.NAMESPACES:
            cfg = self._cfg(ns)
            self.assertEqual(cfg.namespace, ns)


if __name__ == "__main__":
    unittest.main(verbosity=2)
