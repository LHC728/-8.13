"""P0: H2 key schema bootstrap tests (Q3/H2 BOOTSTRAP SPEC section 6.1/D-05).

Four test groups:

  A. H2 key schema unit tests
     - exact frozen namespaces: h2_tuning / h2_holdout / h2_rollout
     - h2_future stays a historical placeholder
     - exact frozen post streams: U_X_post / U_D_post / U_Y_post / U_L_post
     - determinism, valid combinations, invalid combinations
  B. Legacy byte-for-byte golden regression
     - expected values ONLY from the exact pre-change oracle fixture
       (04_代码/tests/fixtures/g3_key_schema_legacy_golden_v1.json,
       oracle commit 1de71824..., blob 8a8f1089...)
     - canonical UTF-8 bytes + Fraction numerator/denominator 100% identical
     - expected are never regenerated from the new implementation
  C. Namespace consumption firewall (negative tests)
     - legacy physical helper + h2_tuning / h2_holdout / h2_rollout ->
       REJECTED
     - legacy physical helper + h2_future -> REJECTED
     - H2 post helper + legacy namespace / h2_future -> REJECTED
  D. Isolation / no-pollution
     - H2 canonical keys never equal any legacy canonical key
     - post streams domain-separated across H2 namespaces and streams

P0 scope: no posterior, no rollout_seed(dp,m), no rollout, no H2 policy.
"""

from __future__ import annotations

import importlib
import json
import sys
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

FIXTURE_PATH = (
    CODE_DIR / "tests" / "fixtures" / "g3_key_schema_legacy_golden_v1.json"
)
ORACLE_COMMIT = "1de71824e668f3815f58112cb3c42c9633b2da16"
ORACLE_BLOB_SHA = "8a8f10895ee9751fb7c3c93093c3cdac25b4b632"
FROZEN_SIX = (
    "development_unit",
    "pilot",
    "h1_tuning",
    "g3_holdout",
    "q2_formal",
    "q3_formal",
)
H2_THREE = ("h2_tuning", "h2_holdout", "h2_rollout")
POST_FOUR = ("U_X_post", "U_D_post", "U_Y_post", "U_L_post")

SEED = 20260815
REP = 3
DEVICE = 7


class TestAH2Schema(unittest.TestCase):
    """A. H2 key schema unit tests."""

    def test_namespaces_exact(self) -> None:
        self.assertEqual(ks.H2_NAMESPACES, H2_THREE)
        self.assertEqual(tuple(ks.NAMESPACES), FROZEN_SIX)  # legacy unchanged
        # ALL_NAMESPACES stays frozen: six + h2_future placeholder only.
        self.assertEqual(ks.ALL_NAMESPACES, FROZEN_SIX + (ks.H2_RESERVED_NAMESPACE,))
        self.assertEqual(ks.H2_RESERVED_NAMESPACE, "h2_future")
        self.assertNotIn("h2_tuning", ks.ALL_NAMESPACES)  # not merged into legacy set
        self.assertEqual(len(ks.ALL_NAMESPACES), 7)
        self.assertEqual(len(set(ks.NAMESPACES)), 6)

    def test_post_streams_exact(self) -> None:
        self.assertEqual(ks.H2_POST_STREAMS, POST_FOUR)
        for name in ("u_x_post", "u_d_post", "u_y_post", "u_l_post"):
            self.assertTrue(hasattr(ks, name), f"missing {name}")

    def test_deterministic(self) -> None:
        for ns in ks.H2_NAMESPACES:
            self.assertEqual(
                ks.u_x_post(ns, REP, DEVICE, "A", SEED),
                ks.u_x_post(ns, REP, DEVICE, "A", SEED),
            )
            self.assertEqual(
                ks.u_d_post(ns, REP, DEVICE, SEED),
                ks.u_d_post(ns, REP, DEVICE, SEED),
            )
            self.assertEqual(
                ks.u_y_post(ns, REP, DEVICE, "B", 1, SEED),
                ks.u_y_post(ns, REP, DEVICE, "B", 1, SEED),
            )
            self.assertEqual(
                ks.u_l_post(ns, REP, "A", 1, SEED),
                ks.u_l_post(ns, REP, "A", 1, SEED),
            )

    def test_valid_in_all_h2_namespaces(self) -> None:
        for ns in ks.H2_NAMESPACES:
            for u in (
                ks.u_x_post(ns, 0, 1, "C", 0),
                ks.u_d_post(ns, 0, 1, 0),
                ks.u_y_post(ns, 0, 1, "E", 2, 0),
                ks.u_l_post(ns, 0, "B", 240, 0),
            ):
                self.assertIsInstance(u, Fraction)
                self.assertGreater(u, Fraction(0))
                self.assertLess(u, Fraction(1))
                self.assertEqual(u.denominator, 1 << 65)  # exact U mapping

    def test_canonical_roundtrip_structure(self) -> None:
        # Post keys serialize to the frozen canonical field order.
        key = ks.canonical_key(
            ks.NAMESPACE_H2_ROLLOUT, 5, DEVICE, "A", None, 7
        )
        fields = key.split("|")
        self.assertEqual(fields[0], ks.KEY_SCHEMA_VERSION)
        self.assertEqual(fields[1], "i:7")  # master_seed
        self.assertEqual(fields[2], "s:h2_rollout")  # namespace
        self.assertEqual(fields[3], "i:5")  # replicate_id
        self.assertEqual(fields[4], "i:7")  # entity
        self.assertEqual(fields[5], "s:A")  # subsystem
        self.assertEqual(fields[6], "")  # attempt slot empty
        self.assertEqual(ks.uniform_from_key(key), ks.u_x_post(
            ks.NAMESPACE_H2_ROLLOUT, 5, DEVICE, "A", 7
        ))

    def test_invalid_combinations(self) -> None:
        # unknown namespace (each post helper rejects fail-closed)
        with self.assertRaises(ValueError):
            ks.u_x_post("bogus_namespace", 0, 1, "A", SEED)
        with self.assertRaises(ValueError):
            ks.u_d_post("bogus_namespace", 0, 1, SEED)
        with self.assertRaises(ValueError):
            ks.u_y_post("bogus_namespace", 0, 1, "A", 1, SEED)
        with self.assertRaises(ValueError):
            ks.u_l_post("bogus_namespace", 0, "A", 1, SEED)
        # invalid subsystem / process / resource / attempt / generation
        with self.assertRaises(ValueError):
            ks.u_x_post(ks.NAMESPACE_H2_TUNING, 0, 1, "X", SEED)
        with self.assertRaises(ValueError):
            ks.u_y_post(ks.NAMESPACE_H2_TUNING, 0, 1, "X", 1, SEED)
        with self.assertRaises(ValueError):
            ks.u_y_post(ks.NAMESPACE_H2_TUNING, 0, 1, "A", 0, SEED)
        with self.assertRaises(ValueError):
            ks.u_l_post(ks.NAMESPACE_H2_TUNING, 0, "X", 1, SEED)
        with self.assertRaises(ValueError):
            ks.u_l_post(ks.NAMESPACE_H2_TUNING, 0, "A", 0, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key("unknown", 0, 1, None, None, 0)


class TestBLegacyGolden(unittest.TestCase):
    """B. Legacy byte-for-byte golden regression (oracle-only expected)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        assert cls.fixture["oracle_commit"] == ORACLE_COMMIT
        assert cls.fixture["oracle_blob_sha"] == ORACLE_BLOB_SHA

    def _recompute(self, v: dict):
        helper = v["helper"]
        a = v["args"]
        if helper == "u_x":
            u = ks.u_x(a["namespace"], a["rep"], a["device"], a["subsystem"], a["seed"])
            key = ks.canonical_key(
                a["namespace"], a["rep"], a["device"], a["subsystem"], None, a["seed"]
            )
        elif helper == "u_d":
            u = ks.u_d(a["namespace"], a["rep"], a["device"], a["seed"])
            key = ks.canonical_key(a["namespace"], a["rep"], a["device"], None, None, a["seed"])
        elif helper == "u_y":
            u = ks.u_y(a["namespace"], a["rep"], a["device"], a["process"], a["attempt"], a["seed"])
            key = ks.canonical_key(
                a["namespace"], a["rep"], a["device"], a["process"], a["attempt"], a["seed"]
            )
        elif helper == "u_l":
            u = ks.u_l(a["namespace"], a["rep"], a["resource"], a["generation"], a["seed"])
            key = ks.canonical_key(a["namespace"], a["rep"], a["resource"], None, a["generation"], a["seed"])
        elif helper == "canonical_key":
            key = ks.canonical_key(
                a["namespace"], a["rep"], a["entity"],
                a["process_or_subsystem"], a["attempt_or_generation"], a["seed"],
            )
            u = ks.uniform_from_key(key)
        else:  # pragma: no cover
            raise AssertionError(f"unknown helper {helper!r} in fixture")
        return key, u

    def test_fixture_metadata(self) -> None:
        self.assertEqual(self.fixture["fixture"], "g3_key_schema_legacy_golden_v1")
        self.assertEqual(self.fixture["oracle_key_schema_version"], "key_schema_v1")
        self.assertEqual(self.fixture["legacy_namespaces"], list(FROZEN_SIX))

    def test_byte_for_byte_identical(self) -> None:
        mismatches: list[dict] = []
        for v in self.fixture["vectors"]:
            key, u = self._recompute(v)
            if key != v["canonical_key"]:
                mismatches.append({"vector": v, "kind": "canonical_key", "got": key})
                continue
            if key.encode("utf-8").hex() != v["canonical_utf8_hex"]:
                mismatches.append({"vector": v, "kind": "utf8_hex"})
                continue
            if u.numerator != v["fraction_num"] or u.denominator != v["fraction_den"]:
                mismatches.append(
                    {
                        "vector": v,
                        "kind": "fraction",
                        "got": (u.numerator, u.denominator),
                    }
                )
        self.assertEqual(
            mismatches,
            [],
            f"legacy byte-compat mismatches: {len(mismatches)}; first: {mismatches[:1]}",
        )

    def test_coverage(self) -> None:
        fams = {v["family"] for v in self.fixture["vectors"]}
        self.assertTrue({"U_X", "U_D", "U_Y", "U_L", "CANONICAL_KEY"} <= fams)
        nss = {v["args"]["namespace"] for v in self.fixture["vectors"]}
        # All six legacy namespaces covered; the only extra namespace in the
        # fixture is the pure-serializer h2_future placeholder case.
        self.assertTrue(set(FROZEN_SIX) <= nss)
        self.assertTrue(nss <= set(FROZEN_SIX) | {"h2_future"})
        self.assertGreaterEqual(len(self.fixture["vectors"]), 300)


class TestCNamespaceFirewall(unittest.TestCase):
    """C. Namespace consumption firewall (negative tests)."""

    LEGACY_HELPERS = (ks.u_x, ks.u_d, ks.u_y, ks.u_l)
    POST_HELPERS = (ks.u_x_post, ks.u_d_post, ks.u_y_post, ks.u_l_post)

    def test_legacy_helper_rejects_all_h2_namespaces(self) -> None:
        for ns in ks.H2_NAMESPACES + (ks.H2_RESERVED_NAMESPACE,):
            with self.assertRaises(ValueError):
                ks.u_x(ns, 0, 1, "A", 0)
            with self.assertRaises(ValueError):
                ks.u_d(ns, 0, 1, 0)
            with self.assertRaises(ValueError):
                ks.u_y(ns, 0, 1, "A", 1, 0)
            with self.assertRaises(ValueError):
                ks.u_l(ns, 0, "A", 1, 0)

    def test_legacy_physical_helper_plus_h2_rollout_rejected(self) -> None:
        # The single most important firewall case.
        ns = ks.NAMESPACE_H2_ROLLOUT
        with self.assertRaises(ValueError):
            ks.u_x(ns, 0, 1, "A", 0)
        with self.assertRaises(ValueError):
            ks.u_d(ns, 0, 1, 0)
        with self.assertRaises(ValueError):
            ks.u_y(ns, 0, 1, "A", 1, 0)
        with self.assertRaises(ValueError):
            ks.u_l(ns, 0, "A", 1, 0)

    def test_post_helper_rejects_legacy_namespaces_and_placeholder(self) -> None:
        for ns in ks.NAMESPACES + (ks.H2_RESERVED_NAMESPACE,):
            with self.assertRaises(ValueError):
                ks.u_x_post(ns, 0, 1, "A", 0)
            with self.assertRaises(ValueError):
                ks.u_d_post(ns, 0, 1, 0)
            with self.assertRaises(ValueError):
                ks.u_y_post(ns, 0, 1, "A", 1, 0)
            with self.assertRaises(ValueError):
                ks.u_l_post(ns, 0, "A", 1, 0)

    def test_h2_future_not_upgraded(self) -> None:
        # h2_future stays a historical placeholder: no helper consumes it.
        ns = ks.H2_RESERVED_NAMESPACE
        with self.assertRaises(ValueError):
            ks.u_x(ns, 0, 1, "A", 0)
        with self.assertRaises(ValueError):
            ks.u_d(ns, 0, 1, 0)
        with self.assertRaises(ValueError):
            ks.u_y(ns, 0, 1, "A", 1, 0)
        with self.assertRaises(ValueError):
            ks.u_l(ns, 0, "A", 1, 0)
        with self.assertRaises(ValueError):
            ks.u_x_post(ns, 0, 1, "A", 0)
        with self.assertRaises(ValueError):
            ks.u_d_post(ns, 0, 1, 0)
        with self.assertRaises(ValueError):
            ks.u_y_post(ns, 0, 1, "A", 1, 0)
        with self.assertRaises(ValueError):
            ks.u_l_post(ns, 0, "A", 1, 0)


class TestDIsolation(unittest.TestCase):
    """D. Isolation / no-pollution."""

    def test_h2_namespace_domain_separation(self) -> None:
        for a, b in (
            ("h2_tuning", "h2_holdout"),
            ("h2_tuning", "h2_rollout"),
            ("h2_holdout", "h2_rollout"),
        ):
            self.assertNotEqual(
                ks.u_x_post(a, REP, DEVICE, "A", SEED),
                ks.u_x_post(b, REP, DEVICE, "A", SEED),
            )
            self.assertNotEqual(
                ks.u_y_post(a, REP, DEVICE, "B", 1, SEED),
                ks.u_y_post(b, REP, DEVICE, "B", 1, SEED),
            )
            self.assertNotEqual(
                ks.u_l_post(a, REP, "A", 1, SEED),
                ks.u_l_post(b, REP, "A", 1, SEED),
            )

    def test_post_stream_separation(self) -> None:
        ux = ks.u_x_post("h2_rollout", REP, DEVICE, "A", SEED)
        ud = ks.u_d_post("h2_rollout", REP, DEVICE, SEED)
        uy = ks.u_y_post("h2_rollout", REP, DEVICE, "A", 1, SEED)
        ul = ks.u_l_post("h2_rollout", REP, "A", 1, SEED)
        self.assertEqual(len({ux, ud, uy, ul}), 4)

    def test_post_vs_legacy_cross_domain_distinct(self) -> None:
        # Same logical slots in legacy vs H2 domains never collide.
        self.assertNotEqual(
            ks.u_x_post("h2_tuning", REP, DEVICE, "A", SEED),
            ks.u_x("h1_tuning", REP, DEVICE, "A", SEED),
        )
        self.assertNotEqual(
            ks.u_l_post("h2_holdout", REP, "A", 1, SEED),
            ks.u_l("g3_holdout", REP, "A", 1, SEED),
        )

    def test_h2_keys_never_equal_any_legacy_key(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        legacy_keys = {v["canonical_key"] for v in fixture["vectors"]}
        h2_keys = [
            ks.canonical_key("h2_tuning", 0, 1, "A", None, 0),
            ks.canonical_key("h2_holdout", 0, 1, "A", None, 0),
            ks.canonical_key("h2_rollout", 0, 1, "A", None, 0),
            ks.canonical_key("h2_rollout", 0, "A", None, 1, 0),
        ]
        for key in h2_keys:
            self.assertNotIn(key, legacy_keys)

    def test_legacy_reload_stable(self) -> None:
        # Re-importing must not change legacy outputs (no module-level RNG).
        before = ks.u_y(ks.NAMESPACE_Q3_FORMAL, REP, DEVICE, "B", 2, SEED)
        importlib.reload(ks)
        after = ks.u_y(ks.NAMESPACE_Q3_FORMAL, REP, DEVICE, "B", 2, SEED)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
