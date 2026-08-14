"""Unit tests for G3-SPEC-V1.0 section 3 key_schema_v1 (stdlib only).

Covers the frozen keyed-uniform contract:

 1. same key -> same U (determinism)
 2. any single field change -> different U
 3. U in [0,1) exact rational (Fraction, denominator 2^65, no binary float)
 4. field-order normalization: same logical content in any argument order
    (positional, keyword, dict **kwargs insertion order) -> same key
 5. six experiment namespaces disjoint (+ H2 reserved placeholder distinct)
 6. order independence: pure functions, no container iteration, no runtime
    default hash(), no module-level RNG state
 7. no float canonical U anywhere (return types + static source checks)
 8. namespace constants complete: six + H2 reserved
 9. forbidden physical key fields never appear as API parameters (static
    AST + inspect.signature checks) and injection through string slots raises
10. CRN: same seed + same world -> same canonical U shared by strategies;
    scenario/config identifiers never enter physical U keys
11. reproducibility: same seed + config -> byte/canonical reproducible,
    including across importlib.reload
12. schema JSON parseable and describes key structure / namespaces /
    forbidden fields, consistent with the module constants

Plus: stream disjointness (U_X/U_D/U_Y/U_L), subsystem A/B/C explicitness,
process/resource/attempt/generation validation, invalid-input rejection, H2
reserved non-consumability, independent re-computation of the mapping
formula, and canonical-key pattern coverage against the schema.

No formal competition numbers are produced; all expectations derive from the
frozen G3-SPEC-V1.0 section 3 contract.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import itertools
import json
import re
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

SCHEMA_PATH = CODE_DIR / "src/schemas" / "g3_key_schema_v1.schema.json"
SOURCE_PATH = Path(ks.__file__)

SEED = 20260814
REP = 3
DEVICE = 7
NS = ks.NAMESPACE_H1_TUNING


def independent_expected_u(key: str) -> Fraction:
    """Recompute the frozen mapping independently (not via the module)."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    head = int.from_bytes(digest[:8], byteorder="big")  # uint64 big-endian
    return Fraction(2 * head + 1, 1 << 65)


def _module_ast() -> ast.Module:
    return ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))


def _module_function_param_names() -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_module_ast()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for group in (args.posonlyargs, args.args, args.kwonlyargs):
                for a in group:
                    names.add(a.arg)
            if args.vararg is not None:
                names.add(args.vararg.arg)
            if args.kwarg is not None:
                names.add(args.kwarg.arg)
    return names


def _module_calls_builtin_hash() -> bool:
    for node in ast.walk(_module_ast()):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "hash"
        ):
            return True
    return False


def _base_key(**overrides) -> str:
    params = dict(
        namespace=NS,
        replicate_id=REP,
        entity_id=DEVICE,
        process_or_subsystem="A",
        attempt_or_generation=1,
        master_seed=SEED,
    )
    params.update(overrides)
    return ks.canonical_key(**params)


class DeterminismAndReproducibilityTests(unittest.TestCase):
    """Requirements 1, 2, 11."""

    def test_same_key_same_u_determinism(self):
        key = ks.canonical_key(NS, REP, DEVICE, "A", 1, SEED)
        self.assertEqual(ks.uniform_from_key(key), ks.uniform_from_key(key))
        self.assertEqual(
            ks.u_x(NS, REP, DEVICE, "A", SEED), ks.u_x(NS, REP, DEVICE, "A", SEED)
        )
        self.assertEqual(
            ks.u_d(NS, REP, DEVICE, SEED), ks.u_d(NS, REP, DEVICE, SEED)
        )
        self.assertEqual(
            ks.u_y(NS, REP, DEVICE, "A", 1, SEED),
            ks.u_y(NS, REP, DEVICE, "A", 1, SEED),
        )
        self.assertEqual(
            ks.u_l(NS, REP, "A", 1, SEED), ks.u_l(NS, REP, "A", 1, SEED)
        )

    def test_different_key_different_u(self):
        base = _base_key()
        base_u = ks.uniform_from_key(base)
        variants = [
            {"master_seed": SEED + 1},
            {"namespace": ks.NAMESPACE_PILOT},
            {"replicate_id": REP + 1},
            {"entity_id": DEVICE + 1},
            {"process_or_subsystem": "B"},
            {"attempt_or_generation": 2},
        ]
        for override in variants:
            key = _base_key(**override)
            self.assertNotEqual(key, base)
            self.assertNotEqual(ks.uniform_from_key(key), base_u)

    def test_bytes_reproducible(self):
        k1 = ks.canonical_key(NS, REP, DEVICE, "A", 1, SEED)
        k2 = ks.canonical_key(NS, REP, DEVICE, "A", 1, SEED)
        self.assertEqual(k1, k2)
        self.assertEqual(k1.encode("utf-8"), k2.encode("utf-8"))
        self.assertEqual(
            hashlib.sha256(k1.encode("utf-8")).digest(),
            hashlib.sha256(k2.encode("utf-8")).digest(),
        )

    def test_reproducible_across_reload(self):
        before = ks.u_y(NS, REP, DEVICE, "A", 2, SEED)
        key_before = ks.canonical_key(NS, REP, DEVICE, "A", 2, SEED)
        reloaded = importlib.reload(ks)
        after = reloaded.u_y(NS, REP, DEVICE, "A", 2, SEED)
        key_after = reloaded.canonical_key(NS, REP, DEVICE, "A", 2, SEED)
        self.assertEqual(before, after)
        self.assertEqual(key_before, key_after)
        self.assertEqual(key_before.encode("utf-8"), key_after.encode("utf-8"))


class RangeAndExactnessTests(unittest.TestCase):
    """Requirements 3 and 7."""

    def test_u_in_unit_interval_exact(self):
        seeds = (0, 1, 42, SEED, (1 << 64) - 1)
        for seed in seeds:
            for device in (1, 2, 7, 100):
                for subsystem in ks.SUBSYSTEMS:
                    u = ks.u_x(NS, REP, device, subsystem, seed)
                    self.assertIsInstance(u, Fraction)
                    self.assertTrue(0 <= u < 1, f"U out of [0,1): {u}")
                    self.assertEqual(u.denominator, 1 << 65)
                    self.assertEqual(u.numerator % 2, 1)
                ud = ks.u_d(NS, REP, device, seed)
                uy = ks.u_y(NS, REP, device, "E", 2, seed)
                ul = ks.u_l(NS, REP, "C", 3, seed)
                for u in (ud, uy, ul):
                    self.assertIsInstance(u, Fraction)
                    self.assertTrue(0 <= u < 1)
                    self.assertEqual(u.denominator, 1 << 65)

    def test_no_float_canonical_u(self):
        for u in (
            ks.u_x(NS, REP, DEVICE, "A", SEED),
            ks.u_d(NS, REP, DEVICE, SEED),
            ks.u_y(NS, REP, DEVICE, "B", 1, SEED),
            ks.u_l(NS, REP, "E", 2, SEED),
            ks.uniform_from_key(_base_key()),
        ):
            self.assertIs(type(u), Fraction)
            self.assertNotIsInstance(u, float)
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("float(", source)
        self.assertNotIn("0.5", source)
        # NB: "1.0" is NOT checked: the frozen spec reference "G3-SPEC-V1.0"
        # legitimately contains that substring.

    def test_mapping_formula_independent_recomputation(self):
        keys = [
            _base_key(),
            _base_key(attempt_or_generation=2, process_or_subsystem="E"),
            ks.canonical_key(NS, 0, "A", None, 7, 0),
            ks.canonical_key(ks.NAMESPACE_Q3_FORMAL, 99, 100, "C", 1, SEED),
        ]
        for key in keys:
            self.assertEqual(ks.uniform_from_key(key), independent_expected_u(key))


class CanonicalizationTests(unittest.TestCase):
    """Requirement 4 plus frozen field-order verification."""

    def test_field_order_normalization(self):
        a = ks.canonical_key(
            namespace=NS,
            replicate_id=REP,
            entity_id=DEVICE,
            process_or_subsystem="A",
            attempt_or_generation=1,
            master_seed=SEED,
        )
        b = ks.canonical_key(
            master_seed=SEED,
            attempt_or_generation=1,
            process_or_subsystem="A",
            entity_id=DEVICE,
            replicate_id=REP,
            namespace=NS,
        )
        c = ks.canonical_key(NS, REP, DEVICE, "A", 1, SEED)  # positional
        d1 = dict(
            namespace=NS,
            replicate_id=REP,
            entity_id=DEVICE,
            process_or_subsystem="A",
            attempt_or_generation=1,
            master_seed=SEED,
        )
        d2 = dict(
            master_seed=SEED,
            namespace=NS,
            attempt_or_generation=1,
            replicate_id=REP,
            entity_id=DEVICE,
            process_or_subsystem="A",
        )
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertEqual(ks.canonical_key(**d1), ks.canonical_key(**d2))

    def test_frozen_field_order_in_canonical_string(self):
        key = ks.canonical_key(NS, REP, DEVICE, "A", 1, SEED)
        segments = key.split("|")
        self.assertEqual(len(segments), 7)
        self.assertEqual(segments[0], "key_schema_v1")
        self.assertEqual(segments[1], f"i:{SEED}")
        self.assertEqual(segments[2], f"s:{NS}")  # namespace precedes replicate_id
        self.assertEqual(segments[3], f"i:{REP}")
        self.assertEqual(segments[4], f"i:{DEVICE}")
        self.assertEqual(segments[5], "s:A")
        self.assertEqual(segments[6], "i:1")
        # namespace strictly precedes replicate_id in the serialized key
        self.assertLess(key.index(f"s:{NS}"), key.index(f"i:{REP}"))

    def test_empty_slots_serialize_as_empty_segments(self):
        ux_key = ks.canonical_key(NS, REP, DEVICE, "A", None, SEED)
        self.assertTrue(ux_key.endswith("|s:A|"))
        ud_key = ks.canonical_key(NS, REP, DEVICE, None, None, SEED)
        self.assertTrue(ud_key.endswith("||"))
        ul_key = ks.canonical_key(NS, REP, "A", None, 1, SEED)
        self.assertTrue(ul_key.endswith("||i:1"))


class NamespaceTests(unittest.TestCase):
    """Requirements 5 and 8."""

    def test_namespace_constants_complete(self):
        self.assertEqual(
            ks.NAMESPACES,
            (
                "development_unit",
                "pilot",
                "h1_tuning",
                "g3_holdout",
                "q2_formal",
                "q3_formal",
            ),
        )
        self.assertEqual(ks.NAMESPACE_DEVELOPMENT_UNIT, "development_unit")
        self.assertEqual(ks.NAMESPACE_PILOT, "pilot")
        self.assertEqual(ks.NAMESPACE_H1_TUNING, "h1_tuning")
        self.assertEqual(ks.NAMESPACE_G3_HOLDOUT, "g3_holdout")
        self.assertEqual(ks.NAMESPACE_Q2_FORMAL, "q2_formal")
        self.assertEqual(ks.NAMESPACE_Q3_FORMAL, "q3_formal")
        self.assertEqual(ks.H2_RESERVED_NAMESPACE, "h2_future")
        self.assertEqual(len(ks.ALL_NAMESPACES), 7)
        self.assertIn(ks.H2_RESERVED_NAMESPACE, ks.ALL_NAMESPACES)
        self.assertEqual(len(set(ks.ALL_NAMESPACES)), 7)

    def test_namespaces_disjoint(self):
        for ns_a, ns_b in itertools.combinations(ks.NAMESPACES, 2):
            u_a = ks.u_x(ns_a, REP, DEVICE, "A", SEED)
            u_b = ks.u_x(ns_b, REP, DEVICE, "A", SEED)
            self.assertNotEqual(u_a, u_b)
            self.assertNotEqual(
                ks.canonical_key(ns_a, REP, DEVICE, "A", 1, SEED),
                ks.canonical_key(ns_b, REP, DEVICE, "A", 1, SEED),
            )

    def test_h2_reserved_distinct_and_not_consumable(self):
        h2_key = ks.canonical_key(
            ks.H2_RESERVED_NAMESPACE, REP, DEVICE, "A", 1, SEED
        )
        for ns in ks.NAMESPACES:
            self.assertNotEqual(
                h2_key, ks.canonical_key(ns, REP, DEVICE, "A", 1, SEED)
            )
        for helper in (
            lambda: ks.u_x(ks.H2_RESERVED_NAMESPACE, REP, DEVICE, "A", SEED),
            lambda: ks.u_d(ks.H2_RESERVED_NAMESPACE, REP, DEVICE, SEED),
            lambda: ks.u_y(ks.H2_RESERVED_NAMESPACE, REP, DEVICE, "A", 1, SEED),
            lambda: ks.u_l(ks.H2_RESERVED_NAMESPACE, REP, "A", 1, SEED),
        ):
            with self.assertRaises(ValueError):
                helper()


class StreamTests(unittest.TestCase):
    """Five-stream structure: disjointness, subsystem/process/attempt rules."""

    def test_streams_disjoint_same_entity(self):
        entity = "A"  # valid entity string and valid U_L resource
        values = {
            "U_X": ks.u_x(NS, REP, entity, "B", SEED),
            "U_D": ks.u_d(NS, REP, entity, SEED),
            "U_Y": ks.u_y(NS, REP, entity, "C", 1, SEED),
            "U_L": ks.u_l(NS, REP, entity, 1, SEED),
        }
        keys = {
            "U_X": ks.canonical_key(NS, REP, entity, "B", None, SEED),
            "U_D": ks.canonical_key(NS, REP, entity, None, None, SEED),
            "U_Y": ks.canonical_key(NS, REP, entity, "C", 1, SEED),
            "U_L": ks.canonical_key(NS, REP, entity, None, 1, SEED),
        }
        for name_a in values:
            for name_b in values:
                if name_a < name_b:
                    self.assertNotEqual(values[name_a], values[name_b])
                    self.assertNotEqual(keys[name_a], keys[name_b])

    def test_u_x_subsystem_abc_explicit(self):
        us = {sub: ks.u_x(NS, REP, DEVICE, sub, SEED) for sub in ks.SUBSYSTEMS}
        self.assertEqual(len(set(us.values())), 3)
        for bad in ("D", "E", "a", "", None):
            with self.assertRaises(ValueError):
                ks.u_x(NS, REP, DEVICE, bad, SEED)

    def test_u_y_process_and_attempt(self):
        keys = {
            proc: ks.canonical_key(NS, REP, DEVICE, proc, 1, SEED)
            for proc in ks.PROCESSES
        }
        self.assertEqual(len(set(keys.values())), 4)
        self.assertNotEqual(
            ks.u_y(NS, REP, DEVICE, "A", 1, SEED),
            ks.u_y(NS, REP, DEVICE, "A", 2, SEED),
        )
        with self.assertRaises(ValueError):
            ks.u_y(NS, REP, DEVICE, "X", 1, SEED)
        with self.assertRaises(ValueError):
            ks.u_y(NS, REP, DEVICE, "A", 0, SEED)
        with self.assertRaises(TypeError):
            ks.u_y(NS, REP, DEVICE, "A", "1", SEED)

    def test_u_l_generation(self):
        self.assertNotEqual(
            ks.u_l(NS, REP, "A", 1, SEED), ks.u_l(NS, REP, "A", 2, SEED)
        )
        self.assertNotEqual(
            ks.u_l(NS, REP, "A", 1, SEED), ks.u_l(NS, REP, "B", 1, SEED)
        )
        with self.assertRaises(ValueError):
            ks.u_l(NS, REP, "A", 0, SEED)
        with self.assertRaises(ValueError):
            ks.u_l(NS, REP, "X", 1, SEED)
        with self.assertRaises(TypeError):
            ks.u_l(NS, REP, "A", "1", SEED)


class OrderIndependenceTests(unittest.TestCase):
    """Requirement 6: pure functions, no container iteration, no runtime hash."""

    def test_pure_function_no_hidden_state(self):
        expected = [ks.u_y(NS, REP, d, "B", 2, SEED) for d in (1, 2, 3)]
        # interleave unrelated stream draws (would disturb a sequential RNG)
        for d in (1, 2, 3):
            ks.u_x(NS, REP, d, "A", SEED)
        ks.u_d(NS, REP, 9, SEED)
        ks.u_l(NS, REP, "E", 5, SEED)
        actual = [ks.u_y(NS, REP, d, "B", 2, SEED) for d in (1, 2, 3)]
        self.assertEqual(expected, actual)

    def test_kwargs_insertion_order_independent(self):
        base = dict(
            namespace=NS,
            replicate_id=REP,
            entity_id=DEVICE,
            process_or_subsystem="A",
            attempt_or_generation=1,
            master_seed=SEED,
        )
        reversed_order = {k: base[k] for k in reversed(list(base))}
        self.assertEqual(
            ks.canonical_key(**base), ks.canonical_key(**reversed_order)
        )

    def test_no_runtime_default_hash(self):
        self.assertFalse(_module_calls_builtin_hash())
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import random", source)
        self.assertNotIn("from random", source)


class ForbiddenFieldTests(unittest.TestCase):
    """Requirement 9: forbidden physical key fields are never key parameters."""

    def test_forbidden_fields_constant(self):
        self.assertEqual(
            ks.FORBIDDEN_PHYSICAL_KEY_FIELDS,
            (
                "run_id",
                "execution_no",
                "restart_no",
                "wall-clock timestamp",
                "container iteration order",
                "event insertion order",
                "strategy_id",
                "policy_id",
                "squad_id",
                "worker_id",
                "agent_id",
            ),
        )

    def test_forbidden_not_in_api_signature(self):
        param_names = _module_function_param_names()
        self.assertTrue(param_names)
        self.assertEqual(
            param_names & set(ks.FORBIDDEN_PHYSICAL_KEY_FIELDS), set()
        )
        for func in (
            ks.canonical_key,
            ks.uniform_from_key,
            ks.u_x,
            ks.u_d,
            ks.u_y,
            ks.u_l,
        ):
            sig_params = set(inspect.signature(func).parameters)
            self.assertEqual(
                sig_params & set(ks.FORBIDDEN_PHYSICAL_KEY_FIELDS), set()
            )

    def test_api_signatures_match_documented_surface(self):
        self.assertEqual(
            list(inspect.signature(ks.canonical_key).parameters),
            [
                "namespace",
                "replicate_id",
                "entity_id",
                "process_or_subsystem",
                "attempt_or_generation",
                "master_seed",
            ],
        )
        self.assertEqual(
            list(inspect.signature(ks.u_x).parameters),
            ["namespace", "rep", "device", "subsystem", "seed"],
        )
        self.assertEqual(
            list(inspect.signature(ks.u_d).parameters),
            ["namespace", "rep", "device", "seed"],
        )
        self.assertEqual(
            list(inspect.signature(ks.u_y).parameters),
            ["namespace", "rep", "device", "process", "attempt", "seed"],
        )
        self.assertEqual(
            list(inspect.signature(ks.u_l).parameters),
            ["namespace", "rep", "resource", "generation", "seed"],
        )

    def test_forbidden_injection_rejected(self):
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, "run_id", None, None, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, "worker_id", None, None, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, "strategy_id", "A", 1, SEED)


class CrnTests(unittest.TestCase):
    """Requirement 10: CRN world sharing; scenario/config ids stay out of keys."""

    def test_crn_same_world_shared_u(self):
        # Two "strategies" both draw from the same canonical world: the raw U
        # must be identical, and any frozen-distribution transform applied to
        # it must agree across strategies.
        strategy_a = ks.u_x(NS, REP, DEVICE, "A", SEED)
        strategy_b = ks.u_x(NS, REP, DEVICE, "A", SEED)
        self.assertEqual(strategy_a, strategy_b)
        threshold = Fraction(3, 100)
        self.assertEqual(strategy_a < threshold, strategy_b < threshold)
        self.assertEqual(strategy_a >= threshold, strategy_b >= threshold)
        self.assertEqual(
            ks.u_y(NS, REP, DEVICE, "B", 1, SEED),
            ks.u_y(NS, REP, DEVICE, "B", 1, SEED),
        )
        self.assertEqual(
            ks.u_l(NS, REP, "C", 2, SEED), ks.u_l(NS, REP, "C", 2, SEED)
        )

    def test_scenario_config_identifiers_not_in_key(self):
        key = ks.canonical_key(NS, REP, DEVICE, "A", 1, SEED)
        for token in (
            "scenario",
            "config",
            "strategy",
            "policy",
            "squad",
            "q2_single_shift",
            "q3_two_shift",
        ):
            self.assertNotIn(token, key)


class InvalidInputTests(unittest.TestCase):
    """Explicit rejection of malformed inputs (no silent defaults)."""

    def test_invalid_namespace(self):
        with self.assertRaises(ValueError):
            ks.canonical_key("bogus_namespace", REP, DEVICE, "A", 1, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key("", REP, DEVICE, "A", 1, SEED)

    def test_invalid_seed_and_rep(self):
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, DEVICE, "A", 1, -5)
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, -1, DEVICE, "A", 1, SEED)
        with self.assertRaises(TypeError):
            ks.canonical_key(NS, REP, DEVICE, "A", 1, True)

    def test_invalid_entity(self):
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, "", "A", 1, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, "a|b", "A", 1, SEED)
        with self.assertRaises(TypeError):
            ks.canonical_key(NS, REP, True, "A", 1, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, 0, "A", 1, SEED)

    def test_invalid_attempt_generation(self):
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, DEVICE, "A", 0, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, DEVICE, "A", -1, SEED)
        with self.assertRaises(TypeError):
            ks.canonical_key(NS, REP, DEVICE, "A", "1", SEED)

    def test_invalid_canonical_key_to_uniform(self):
        with self.assertRaises(TypeError):
            ks.uniform_from_key(b"key_schema_v1|i:0|s:pilot|i:0|i:1||")
        with self.assertRaises(ValueError):
            ks.uniform_from_key("not-a-canonical-key")


class SchemaTests(unittest.TestCase):
    """Requirement 12: schema JSON parseable and consistent with the module."""

    def test_schema_json_parseable(self):
        self.assertTrue(SCHEMA_PATH.is_file())
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertEqual(schema["type"], "object")

    def test_schema_describes_key_structure(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["properties"]["key_schema_version"]["const"],
            ks.KEY_SCHEMA_VERSION,
        )
        order = [
            item["const"]
            for item in schema["properties"]["canonical_key_field_order"][
                "prefixItems"
            ]
        ]
        self.assertEqual(order, list(ks.CANONICAL_KEY_FIELD_ORDER))
        self.assertEqual(
            schema["properties"]["mapping"]["const"], ks.MAPPING_DESCRIPTION
        )

    def test_schema_describes_namespaces(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        ns_enum = schema["properties"]["namespaces"]["properties"][
            "experiment_namespaces"
        ]["items"]["enum"]
        self.assertEqual(ns_enum, list(ks.NAMESPACES))
        self.assertEqual(
            schema["properties"]["namespaces"]["properties"]["h2_reserved"][
                "const"
            ],
            ks.H2_RESERVED_NAMESPACE,
        )

    def test_schema_describes_forbidden_fields(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        forbidden = schema["properties"]["forbidden_physical_key_fields"][
            "items"
        ]["enum"]
        self.assertEqual(forbidden, list(ks.FORBIDDEN_PHYSICAL_KEY_FIELDS))

    def test_schema_describes_streams(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        stream_keys = set(schema["properties"]["streams"]["properties"].keys())
        self.assertEqual(
            stream_keys,
            {
                "U_X_device_true_state",
                "U_D_d_materialization",
                "U_Y_observation",
                "U_L_equipment_lifetime",
                "H2_future_stream",
            },
        )
        h2 = schema["properties"]["streams"]["properties"]["H2_future_stream"]
        self.assertEqual(h2["properties"]["status"]["const"], "reserved_only")

    def test_schema_consumption_semantics(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        no_consume = schema["properties"]["consumption_semantics"][
            "properties"
        ]["no_observation_u_consumed_by"]["items"]["enum"]
        self.assertEqual(no_consume, list(ks.NO_OBSERVATION_CONSUMED_BY))

    def test_canonical_keys_match_schema_pattern(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        pattern = schema["$defs"]["canonicalKeyString"]["pattern"]
        keys = [
            ks.canonical_key(NS, REP, DEVICE, "A", 1, SEED),
            ks.canonical_key(NS, REP, DEVICE, None, None, SEED),
            ks.canonical_key(NS, REP, "A", None, 1, SEED),
            ks.canonical_key(NS, REP, "res7", "B", None, SEED),
            ks.canonical_key(ks.H2_RESERVED_NAMESPACE, 0, 1, None, None, 0),
            ks.canonical_key(ks.NAMESPACE_Q3_FORMAL, 99, 100, "E", 2, 1 << 63),
        ]
        for key in keys:
            self.assertIsNotNone(re.fullmatch(pattern, key), key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
