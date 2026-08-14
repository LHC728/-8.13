"""G3-SPEC-V1.0 S6 (CR-V3.1/C16): G3 experiment-level random inspection
acceptance tests.

This file is the C16 experiment-layer acceptance test of the frozen G3-SPEC-V1.0
contract.  It tests ONLY the frozen experiment-separation acceptance points
(G3-SPEC-V1.0 section 11 ``c16_experiment_checks``) plus the section-3
``random_key_architecture`` checks listed in the task package.  Semantics are
frozen; this file never modifies any implementation.  It is built entirely on
the accepted S1-S5 APIs (``main_model.g3.key_schema_v1``,
``main_model.g3.lifetime_regeneration_v1``, ``main_model.g3.random_des_v1``,
``checker.g3_quality_oracle_v1``, ``checker.g3_replay_checker_v1``) and on the
shared frozen ``02_数据/parameters.csv``.

Coverage mapping (each frozen item -> test class / test):

  G3-SPEC-V1.0 section 11 (c16_experiment_checks):
    * container-iteration permutation does not change canonical U/events
        -> TestContainerOrderIndependence
    * intended-CRN comparisons share one underlying random world
        -> TestCrnSharedRandomWorld
    * interrupted fragments consume no observation U
        -> TestInterruptedFragmentsConsumeNoObservationU
    * pilot/tuning/holdout/formal namespaces never collide
        -> TestNamespaceNonCollision
    * same seed + config + code -> byte/canonical reproducible output
      (explicit run metadata excepted)
        -> TestReproducibility
    * config validation addendum (S6-detected defect): a calendar scenario
      (q2_single_shift / q3_two_shift) whose task durations exceed the shift
      length can never start any task, so the batch would silently never
      terminate; ``RandomDesConfig.from_dict`` must reject it explicitly
      (CR-V3.1/C18 liveness; AGENTS.md 参数无效必须显式失败), while
      duration == shift length stays legal (恰班末完成允许, P062)
        -> TestShiftLengthConfigValidation

  G3-SPEC-V1.0 section 3 (random_key_architecture):
    * physical keys never contain run_id/execution_no/restart_no/wall-clock/
      container iteration/event insertion/strategy/policy/squad/worker/agent
        -> TestForbiddenPhysicalKeyFields
    * the six experiment namespaces are pairwise disjoint
      (development_unit/pilot/h1_tuning/g3_holdout/q2_formal/q3_formal)
        -> TestNamespaceNonCollision
    * CRN: same seed + namespace + replicate under different tau_pm strategies
      share the same U world (U_X/U_Y/U_L agree; only T/YXB/cancelled
      fragments/equipment age/replacement counts/hat e may differ)
        -> TestCrnSharedRandomWorld
    * exactness: no binary float in any canonical path (mapping, engine log,
      metrics, consumed-U summary)
        -> TestCanonicalExactness

  G3-SPEC-V1.0 section 8 (data_separation) mechanism checks (G3-DEC-03/04):
    * tuning comparisons share identical canonical CRN worlds across candidates
      (namespace = h1_tuning)
        -> TestCrnSharedRandomWorld.test_multi_replicate_tuning_worlds_shared_across_candidates
    * holdout/tuning seed pools never collide even with equal seeds
        -> TestNamespaceNonCollision.test_seed_pool_separation_across_namespaces

All runs are small (batch <= 100, wall-clock trivial); no formal competition
numbers are produced.  All expectations derive from the frozen G3-SPEC-V1.0
contract and parameters.csv.
"""

from __future__ import annotations

import ast
import inspect
import itertools
import json
import random
import re
import subprocess
import sys
import textwrap
import unittest
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]          # competitions/模拟赛_研究生A题
CODE_DIR = BASE / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(CODE_DIR), str(MAIN_MODEL)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from checker import g3_quality_oracle_v1 as qo  # noqa: E402
from checker import g3_replay_checker_v1 as rck  # noqa: E402
from des import state_models_v1 as sm  # noqa: E402
from g3 import key_schema_v1 as ks  # noqa: E402
from g3 import lifetime_regeneration_v1 as lr  # noqa: E402
from g3 import random_des_v1 as rd  # noqa: E402

PARAMS_CSV = BASE / "02_数据" / "parameters.csv"

NS = ks.NAMESPACE_DEVELOPMENT_UNIT
SEED = 7
REP = 0

# Frozen defect probabilities (parameters.csv P026-P029), restated only for
# building the frozen single-test kernels (the checker reads the csv itself).
DEFECT_Q: dict[str, Fraction] = {
    "A": Fraction(25, 1000),
    "B": Fraction(3, 100),
    "C": Fraction(2, 100),
}

# Frozen single-test unconditional error rates (parameters.csv P060).
FROZEN_E: dict[str, Fraction] = {
    "A": Fraction(3, 100),
    "B": Fraction(4, 100),
    "C": Fraction(2, 100),
}

# Canonical-key shape of every physical U key (frozen field order and type
# tags): key_schema_v1 | i:seed | s:namespace | i:replicate | <entity> |
# <process_or_subsystem> | <attempt_or_generation>, where entity is i:<int> or
# s:<A|B|C|E>, and the two trailing slots are empty or a tagged value.
CANONICAL_KEY_PATTERN = re.compile(
    r"^key_schema_v1\|i:\d+\|s:(development_unit|pilot|h1_tuning|g3_holdout|"
    r"q2_formal|q3_formal)\|i:\d+\|(i:\d+|s:[ABCE])\|(s:[ABCE]|)\|(i:\d+|)$"
)

# Forbidden physical key tokens (frozen; substring scan over real keys).
FORBIDDEN_TOKENS: tuple[str, ...] = (
    "run_id",
    "execution_no",
    "restart_no",
    "wall",
    "timestamp",
    "iteration",
    "insertion",
    "strategy",
    "policy",
    "squad",
    "worker",
    "agent",
)

# CRN pair used throughout: same world, two tau_pm strategies, with
# deterministic preventive replacement (d=40, N=4: the 4th A-test idles at age
# exactly 120 h -> tau_pm=120 preventive-replaces while NO_PM serves the head).
CRN_DURATIONS: dict[str, str] = {"A": "40", "B": "40", "C": "40", "E": "3"}


def frozen_kernel() -> dict[str, dict[str, Fraction]]:
    """Frozen literal main-semantics kernel (P060; (1-q)alpha = q beta = e/2)
    for A/B/C; the E kernel is the frozen test input used by the G3 S3 tests."""
    kernel: dict[str, dict[str, Fraction]] = {}
    for proc in ("A", "B", "C"):
        alpha, beta = rd.frozen_single_test_alpha_beta(DEFECT_Q[proc], FROZEN_E[proc])
        kernel[proc] = {"alpha": alpha, "beta": beta}
    kernel["E"] = {"alpha": Fraction(1, 50), "beta": Fraction(1, 2)}
    return kernel


def make_config(
    batch_size: int = 3,
    namespace: str = NS,
    master_seed: int = SEED,
    replicate_id: int = REP,
    tau_pm=None,
    kernel=None,
    scenario: str = "isolated_small_case",
    shift_length_h: str = "1000000",
    shifts_per_day: int = 1,
    durations=None,
    turnover_profile: str = "1h_literal",
    scenario_id: str | None = None,
) -> rd.RandomDesConfig:
    if kernel is None:
        kernel = frozen_kernel()
    # Resolve the NO_PM sentinel at CALL time (not as a function default) so
    # the identity check inside ``random_des_v1.default_config`` never sees a
    # stale sentinel object (e.g. after importlib.reload in the reload test).
    if tau_pm is None:
        tau_pm = lr.NO_PM_BEFORE_MANDATORY
    return rd.default_config(
        namespace=namespace,
        master_seed=master_seed,
        replicate_id=replicate_id,
        tau_pm=tau_pm,
        observation_kernel=kernel,
        batch_size=batch_size,
        scenario=scenario,
        shift_length_h=shift_length_h,
        shifts_per_day=shifts_per_day,
        durations=durations,
        turnover_profile=turnover_profile,
        scenario_id=scenario_id,
    )


def run(config: rd.RandomDesConfig, **kwargs) -> rd.RandomDesResult:
    return rd.run_random_des(config, **kwargs)


def records(log: list[dict], event_type: str) -> list[dict]:
    return [r for r in log if r["event_type"] == event_type]


def recs_for(log: list[dict], event_type: str, **fields) -> list[dict]:
    return [
        r for r in log
        if r["event_type"] == event_type
        and all(r.get(key) == value for key, value in fields.items())
    ]


def observation_u_map(res: rd.RandomDesResult) -> dict[tuple[int, str, int], str]:
    """(device, process, effective_attempt_no) -> recorded keyed U_Y."""
    return {
        (r["device_id"], r["process"], r["effective_attempt_no"]): r["u"]
        for r in records(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)
    }


def consumed_u_map(res: rd.RandomDesResult) -> dict[str, str]:
    """canonical key -> recorded U (the engine's full consumption summary)."""
    return dict(res.summary["consumed_u"])


def assert_pure_keyed_world(test: unittest.TestCase, res: rd.RandomDesResult) -> None:
    """Every U consumed by the engine equals the pure canonical-key function
    ``uniform_from_key`` -- i.e. no execution-related entropy is ever injected."""
    for key, value in consumed_u_map(res).items():
        test.assertEqual(
            str(ks.uniform_from_key(key)),
            value,
            f"consumed U for key {key!r} is not the pure canonical mapping",
        )


class TestContainerOrderIndependence(unittest.TestCase):
    """G3-SPEC-V1.0 section 11 item 1 (and section 3 ``order_independence``):
    container-iteration permutation never changes the canonical U / events."""

    def test_canonical_key_argument_order_permutation(self) -> None:
        """Same logical fields in any argument-passing order -> same key/U."""
        base = dict(
            namespace=ks.NAMESPACE_H1_TUNING,
            replicate_id=3,
            entity_id=7,
            process_or_subsystem="B",
            attempt_or_generation=2,
            master_seed=20260814,
        )
        base_key = ks.canonical_key(**base)
        # canonical frozen field order is fixed (NOTE-3: namespace precedes
        # replicate_id)
        self.assertEqual(
            base_key,
            "key_schema_v1|i:20260814|s:h1_tuning|i:3|i:7|s:B|i:2",
        )
        for perm in itertools.permutations(base):
            kwargs = {name: base[name] for name in perm}
            self.assertEqual(ks.canonical_key(**kwargs), base_key)
            self.assertEqual(ks.uniform_from_key(ks.canonical_key(**kwargs)),
                             ks.uniform_from_key(base_key))
        # also the positional form matches the keyword form
        self.assertEqual(
            ks.canonical_key(
                base["namespace"], base["replicate_id"], base["entity_id"],
                base["process_or_subsystem"], base["attempt_or_generation"],
                base["master_seed"],
            ),
            base_key,
        )

    def test_config_dict_key_order_permutation_identical_log(self) -> None:
        """Reordering the config dict (top level, observation_kernel, durations)
        never changes the canonical event log / U values."""
        cfg = make_config(
            batch_size=4, scenario="q2_single_shift", shift_length_h="12",
        )
        raw = cfg.to_dict()

        def _shuffled(mapping: dict, rng_seed: int) -> dict:
            items = list(mapping.items())
            random.Random(rng_seed).shuffle(items)
            return dict(items)

        variants: list[dict] = [raw]
        # reversed top level
        variants.append(dict(reversed(list(raw.items()))))
        # seeded-shuffled top level
        variants.append(_shuffled(raw, 1))
        # inner containers reordered
        inner = dict(raw)
        inner["observation_kernel"] = _shuffled(raw["observation_kernel"], 2)
        inner["durations"] = _shuffled(raw["durations"], 3)
        variants.append(inner)
        # everything reordered
        everything = dict(_shuffled(raw, 4))
        everything["observation_kernel"] = _shuffled(raw["observation_kernel"], 5)
        everything["durations"] = _shuffled(raw["durations"], 6)
        variants.append(everything)

        base_log = run(cfg).canonical_event_log()
        for idx, variant in enumerate(variants[1:], start=1):
            cfg_v = rd.RandomDesConfig.from_dict(variant)
            self.assertEqual(
                run(cfg_v).canonical_event_log(),
                base_log,
                f"config variant {idx}: container-iteration order changed the log",
            )

    def test_engine_u_is_pure_keyed_function_of_key(self) -> None:
        """The engine's generated U/events are canonical-key functions: every
        log-recorded U equals the direct key-schema call built from the record's
        frozen fields (any traversal order yields the same value)."""
        cfg = make_config(
            batch_size=6, scenario="q2_single_shift", shift_length_h="12",
        )
        res = run(cfg)
        ns, rep, seed = cfg.namespace, cfg.replicate_id, cfg.master_seed
        mismatches = 0
        for rec in records(res.event_log, rd.EVENT_TRUE_STATE_GENERATED):
            for sub in ("A", "B", "C"):
                if rec["u"][sub] != str(ks.u_x(ns, rep, rec["device_id"], sub, seed)):
                    mismatches += 1
        for rec in records(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value):
            if rec["u"] != str(ks.u_y(
                ns, rep, rec["device_id"], rec["process"], rec["effective_attempt_no"], seed
            )):
                mismatches += 1
        for rec in records(res.event_log, sm.EventType.D_CREATED.value):
            if rec["u"] != str(ks.u_d(ns, rep, rec["device_id"], seed)):
                mismatches += 1
        for rec in records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START):
            if rec["u"] != str(ks.u_l(
                ns, rep, rec["resource_id"], rec["new_generation"], seed
            )):
                mismatches += 1
        self.assertEqual(mismatches, 0)
        assert_pure_keyed_world(self, res)

    def test_canonical_log_json_stable_and_float_free(self) -> None:
        """The canonical serialization is deterministic, sort-keyed JSON with no
        binary float anywhere."""
        cfg = make_config(batch_size=4, scenario="q2_single_shift", shift_length_h="12")
        res = run(cfg)
        text = res.canonical_event_log().decode("utf-8")
        parsed = json.loads(text)

        def _has_float(value) -> bool:
            if isinstance(value, float):
                return True
            if isinstance(value, dict):
                return any(_has_float(v) for v in value.values())
            if isinstance(value, list):
                return any(_has_float(v) for v in value)
            return False

        self.assertFalse(_has_float(parsed), "binary float inside canonical log")
        # sort_keys serialization: re-serializing with json's own sort_keys
        # reproduces the exact bytes (canonical ordering, not insertion order)
        self.assertEqual(
            json.dumps(parsed, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8"),
            res.canonical_event_log(),
        )


class TestCrnSharedRandomWorld(unittest.TestCase):
    """G3-SPEC-V1.0 section 11 item 2 + section 3 ``crn_rule`` / section 8:
    intended-CRN strategy comparisons share one underlying canonical U world;
    scenario/config identifiers never enter physical U keys."""

    def _pair(self, tau_pm, **overrides):
        kwargs = dict(
            batch_size=4, durations=CRN_DURATIONS, namespace=ks.NAMESPACE_H1_TUNING,
        )
        kwargs.update(overrides)
        return make_config(tau_pm=tau_pm, **kwargs)

    def test_different_tau_pm_share_canonical_u_world(self) -> None:
        """NO_PM vs tau_pm=120 with the same (namespace, seed, replicate):
        every shared canonical key has the identical U; the whole consumption is
        a pure keyed function; U_X/U_Y/U_L/U_D agree on shared keys."""
        res_nopm = run(self._pair(lr.NO_PM_BEFORE_MANDATORY))
        res_pm = run(self._pair(Fraction(120)))
        u_nopm = consumed_u_map(res_nopm)
        u_pm = consumed_u_map(res_pm)
        shared = set(u_nopm) & set(u_pm)
        self.assertGreater(len(shared), 0)
        for key in shared:
            self.assertEqual(u_nopm[key], u_pm[key], f"shared key {key!r} diverged")
        assert_pure_keyed_world(self, res_nopm)
        assert_pure_keyed_world(self, res_pm)
        # U_X maps (per device) are identical across strategies
        def _ux(res):
            return {
                r["device_id"]: r["u"]
                for r in records(res.event_log, rd.EVENT_TRUE_STATE_GENERATED)
            }
        self.assertEqual(_ux(res_nopm), _ux(res_pm))
        # event-level: shared completed observations agree
        o_nopm = observation_u_map(res_nopm)
        o_pm = observation_u_map(res_pm)
        for key in set(o_nopm) & set(o_pm):
            self.assertEqual(o_nopm[key], o_pm[key])
        # the shared U_Y / U_L keys carry identical values
        for key in shared:
            if "|i:" in key and ("|s:A|i:" in key or "|s:B|i:" in key
                                 or "|s:C|i:" in key or "|s:E|i:" in key):
                self.assertEqual(u_nopm[key], u_pm[key])  # U_Y
            elif re.search(r"\|s:[ABCE]\|\|i:\d+$", key):
                self.assertEqual(u_nopm[key], u_pm[key])  # U_L

    def test_strategy_changes_only_time_layer_quantities(self) -> None:
        """Section 9 scope_limits: a strategy changes only T/YXB/cancelled
        fragments/equipment age/replacement counts (hat e is out of G3 scope),
        never the quality terms (S/PL/PW, true states, D, keyed observations)."""
        res_nopm = run(self._pair(lr.NO_PM_BEFORE_MANDATORY))
        res_pm = run(self._pair(Fraction(120)))
        # quality terms identical
        for name in ("S", "PL", "PW", "exited"):
            self.assertEqual(res_nopm.metrics[name], res_pm.metrics[name], name)
        # T and YXB differ (preventive replacement changes the schedule)
        self.assertNotEqual(res_nopm.metrics["T"], res_pm.metrics["T"])
        self.assertTrue(
            any(
                res_nopm.metrics[f"YXB_{p}"] != res_pm.metrics[f"YXB_{p}"]
                for p in ("A", "B", "C", "E")
            ),
            "YXB must be allowed to differ across strategies",
        )
        # replacement counts differ: NO_PM never prevents, tau=120 does
        def _pm_total(res):
            return sum(
                res.metrics["equipment"][r]["preventive_replacement_count"]
                for r in ("A", "B", "C", "E")
            )
        self.assertEqual(_pm_total(res_nopm), 0)
        self.assertGreater(_pm_total(res_pm), 0)

    def test_crn_paired_runs_pass_independent_oracle_and_replay(self) -> None:
        """Both CRN-paired runs independently replay clean (C17/S5) and pass the
        C06/S4 quality oracle with identical per-device quality facts -- the
        strategy changes only the time layer."""
        res_nopm = run(self._pair(lr.NO_PM_BEFORE_MANDATORY))
        res_pm = run(self._pair(Fraction(120)))
        for res in (res_nopm, res_pm):
            report = qo.check_quality_oracle(
                res.event_log, res.config.to_dict(),
                parameters_csv=str(PARAMS_CSV), metrics=res.metrics,
            )
            self.assertEqual(report.verdict, "PASS")
            replay = rck.check_replay(
                res.event_log, res.config.to_dict(),
                parameters_csv=str(PARAMS_CSV), metrics=res.metrics,
            )
            self.assertEqual(replay.verdict, "PASS")
        rep_n = qo.check_quality_oracle(
            res_nopm.event_log, res_nopm.config.to_dict(),
            parameters_csv=str(PARAMS_CSV), metrics=res_nopm.metrics,
        )
        rep_p = qo.check_quality_oracle(
            res_pm.event_log, res_pm.config.to_dict(),
            parameters_csv=str(PARAMS_CSV), metrics=res_pm.metrics,
        )
        self.assertEqual(rep_n.oracle_aggregate, rep_p.oracle_aggregate)
        # per-device quality facts (terminal / D / observations) are identical
        # across strategies (quality terms are time-layer-free)
        self.assertEqual(rep_n.to_dict()["devices"], rep_p.to_dict()["devices"])

    def test_multi_replicate_tuning_worlds_shared_across_candidates(self) -> None:
        """G3-DEC-03 mechanism: within one tuning comparison every candidate
        runs on the SAME canonical CRN worlds (namespace=h1_tuning); per
        replicate the candidates share the underlying U world."""
        for rep, seed in ((0, 7), (1, 11), (2, 13)):
            res_a = run(self._pair(lr.NO_PM_BEFORE_MANDATORY, master_seed=seed,
                                   replicate_id=rep))
            res_b = run(self._pair(Fraction(120), master_seed=seed,
                                   replicate_id=rep))
            u_a, u_b = consumed_u_map(res_a), consumed_u_map(res_b)
            shared = set(u_a) & set(u_b)
            self.assertGreater(len(shared), 0, f"rep={rep} seed={seed}")
            for key in shared:
                self.assertEqual(u_a[key], u_b[key])
            assert_pure_keyed_world(self, res_a)
            assert_pure_keyed_world(self, res_b)
            # U_X per device is identical across the two candidates
            def _ux(res):
                return {
                    r["device_id"]: r["u"]
                    for r in records(res.event_log, rd.EVENT_TRUE_STATE_GENERATED)
                }
            self.assertEqual(_ux(res_a), _ux(res_b))

    def test_scenario_config_label_not_in_physical_key(self) -> None:
        """``scenario_id`` (a config label) never enters the physical U keys and
        never changes the canonical output for the same world."""
        raw_a = make_config(batch_size=3, scenario="q2_single_shift",
                            shift_length_h="12", scenario_id="label_A").to_dict()
        raw_b = make_config(batch_size=3, scenario="q2_single_shift",
                            shift_length_h="12", scenario_id="label_B").to_dict()
        log_a = run(rd.RandomDesConfig.from_dict(raw_a)).canonical_event_log()
        log_b = run(rd.RandomDesConfig.from_dict(raw_b)).canonical_event_log()
        self.assertEqual(log_a, log_b)
        res = run(rd.RandomDesConfig.from_dict(raw_a))
        for key in consumed_u_map(res):
            self.assertNotIn("label_A", key)
            self.assertNotIn("label_B", key)
            self.assertRegex(key, CANONICAL_KEY_PATTERN)

    def test_same_world_different_scenario_shares_u(self) -> None:
        """Scenario (calendar) is not a physical key field: two scenarios over
        the same world share identical U values for every common key."""
        res_iso = run(make_config(batch_size=3, namespace=ks.NAMESPACE_G3_HOLDOUT,
                                  master_seed=9, replicate_id=1,
                                  scenario="isolated_small_case",
                                  shift_length_h="1000000"))
        res_q2 = run(make_config(batch_size=3, namespace=ks.NAMESPACE_G3_HOLDOUT,
                                 master_seed=9, replicate_id=1,
                                 scenario="q2_single_shift", shift_length_h="12"))
        u_iso, u_q2 = consumed_u_map(res_iso), consumed_u_map(res_q2)
        shared = set(u_iso) & set(u_q2)
        self.assertGreater(len(shared), 0)
        for key in shared:
            self.assertEqual(u_iso[key], u_q2[key])
        # the same canonical absorption chains are completed in both scenarios
        self.assertEqual(observation_u_map(res_iso), observation_u_map(res_q2))


class TestInterruptedFragmentsConsumeNoObservationU(unittest.TestCase):
    """G3-SPEC-V1.0 section 11 item 3 + section 3
    ``no_observation_u_consumed_by``: failure interruption, terminal
    cancellation, shift deferral and never-started tasks consume no
    observation U (a retry of the same effective attempt reuses the same keyed
    U_Y)."""

    def test_failure_interruption_no_observation_u(self) -> None:
        """seed 51: B's generation-1 lifetime interrupts the B fragment; the
        interruption consumes no U_Y and the retry reuses the same keyed U_Y."""
        cfg = make_config(
            batch_size=1, master_seed=51,
            durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"},
        )
        res = run(cfg)
        fails = records(res.event_log, rd.EVENT_EQUIPMENT_FAILURE)
        self.assertEqual(len(fails), 1)
        fail = fails[0]
        self.assertEqual((fail["device_id"], fail["process"],
                          fail["effective_attempt_no"]), (1, "B", 1))
        # no observation at the failure instant for that effective attempt
        at_fail = recs_for(
            res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value,
            device_id=1, process="B", effective_attempt_no=1,
        )
        self.assertNotIn(fail["event_time"], {r["event_time"] for r in at_fail})
        # the cancellation record carries no outcome
        cancels = recs_for(
            res.event_log, sm.EventType.TASK_CANCEL.value,
            device_id=1, process="B",
            cancel_reason=rd.CANCEL_REASON_EQUIPMENT_FAILURE,
        )
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["outcome"], sm.Outcome.NONE.value)
        # the retry (same effective attempt 1) consumes the same keyed U_Y
        b_obs = recs_for(
            res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value,
            device_id=1, process="B", effective_attempt_no=1,
        )
        self.assertEqual(len(b_obs), 1)
        self.assertEqual(
            b_obs[0]["u"],
            str(ks.u_y(res.config.namespace, res.config.replicate_id, 1, "B", 1,
                       res.config.master_seed)),
        )
        # attempt unchanged across the interruption
        b_starts = recs_for(res.event_log, sm.EventType.ACTIVITY_START.value,
                            device_id=1, process="B")
        self.assertEqual([s["effective_attempt_no"] for s in b_starts], [1, 1])

    def test_terminal_cancellation_of_running_fragment_no_observation(self) -> None:
        """A device exit (second effective abnormal) cancels a still-RUNNING
        fragment of another process; the cancelled fragment consumes no U_Y."""
        kernel = {
            "A": {"alpha": Fraction(1), "beta": Fraction(0)},
            "B": {"alpha": Fraction(0), "beta": Fraction(1)},
            "C": {"alpha": Fraction(0), "beta": Fraction(1)},
            "E": {"alpha": Fraction(0), "beta": Fraction(1)},
        }
        cfg = make_config(
            batch_size=1, master_seed=3, kernel=kernel,
            durations={"A": "5/2", "B": "10", "C": "5/2", "E": "3"},
        )
        res = run(cfg)
        # device 1 exits via the second ABNORMAL on A at t=5
        terms = records(res.event_log, sm.EventType.DEVICE_TERMINAL.value)
        self.assertEqual([(t["device_id"], t["terminal_state"]) for t in terms],
                         [(1, sm.TerminalState.EXITED.value)])
        # B's fragment (still RUNNING at the exit instant) is cancelled
        cancel = recs_for(
            res.event_log, sm.EventType.TASK_CANCEL.value,
            device_id=1, process="B",
            cancel_reason=sm.CancelReason.DEVICE_EXIT.value,
        )
        self.assertEqual(len(cancel), 1)
        self.assertEqual(cancel[0]["outcome"], sm.Outcome.NONE.value)
        self.assertGreater(Fraction(cancel[0]["elapsed_hours"]), Fraction(0))
        # no observation U was ever consumed for B
        self.assertEqual(
            recs_for(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value,
                     device_id=1, process="B"),
            [],
        )
        self.assertEqual(
            res.summary["u_consumption_counts"]["u_y"],
            len(records(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)),
        )

    def test_never_started_ready_task_cancelled_no_observation(self) -> None:
        """A READY (released but never started, shift-fit blocked) task is
        cancelled on device exit with elapsed 0 and consumes no U_Y."""
        kernel = {
            "A": {"alpha": Fraction(1), "beta": Fraction(0)},
            "B": {"alpha": Fraction(1), "beta": Fraction(0)},
            "C": {"alpha": Fraction(0), "beta": Fraction(1)},
            "E": {"alpha": Fraction(0), "beta": Fraction(1)},
        }
        cfg = make_config(
            batch_size=1, master_seed=11, kernel=kernel,
            scenario="q2_single_shift", shift_length_h="12",
            durations={"A": "7", "B": "4", "C": "5/2", "E": "3"},
        )
        res = run(cfg)
        # A2 released at t=7 (fits no shift: 7+7=14 > 12) stays READY; device
        # exits via B's second ABNORMAL at t=8 -> A2 cancelled as never-started
        release = recs_for(res.event_log, sm.EventType.TASK_RELEASE.value,
                           device_id=1, process="A", effective_attempt_no=2)
        self.assertEqual(len(release), 1)
        cancel = recs_for(res.event_log, sm.EventType.TASK_CANCEL.value,
                          device_id=1, process="A", effective_attempt_no=2,
                          cancel_reason=sm.CancelReason.DEVICE_EXIT.value)
        self.assertEqual(len(cancel), 1)
        self.assertEqual(Fraction(cancel[0]["elapsed_hours"]), Fraction(0))
        self.assertEqual(cancel[0]["outcome"], sm.Outcome.NONE.value)
        # never started: no ACTIVITY_START for (1, A, 2)
        self.assertEqual(
            recs_for(res.event_log, sm.EventType.ACTIVITY_START.value,
                     device_id=1, process="A", effective_attempt_no=2),
            [],
        )
        # no observation U for the never-started attempt
        self.assertEqual(
            recs_for(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value,
                     device_id=1, process="A", effective_attempt_no=2),
            [],
        )
        self.assertEqual(
            res.summary["u_consumption_counts"]["u_y"],
            len(records(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)),
        )

    def test_shift_deferral_consumes_no_observation_u(self) -> None:
        """A replacement deferred at a shift end (no-cross-shift, trigger H)
        consumes no observation randomness between the deferral and the next
        legal shift (N=100, q2 12h, seed 7; frozen durations)."""
        cfg = make_config(
            batch_size=100, master_seed=7,
            scenario="q2_single_shift", shift_length_h="12",
        )
        res = run(cfg)
        deferred = records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_DEFERRED)
        self.assertGreaterEqual(len(deferred), 1)
        d0 = deferred[0]
        self.assertEqual(d0["reason"], "no_cross_shift")
        self.assertEqual(d0["resource_id"], "E")
        self.assertEqual(d0["event_time"], "636")
        self.assertEqual(d0["next_wake"], "648")
        between = [
            r for r in res.event_log
            if Fraction(r["event_time"]) > Fraction(636)
            and Fraction(r["event_time"]) < Fraction(648)
        ]
        self.assertFalse(
            any(r["event_type"] == sm.EventType.OBSERVATION_MATERIALIZED.value
                for r in between),
            "an observation U was consumed during the deferral gap",
        )

    def test_uy_consumption_count_invariant_across_runs(self) -> None:
        """For several worlds, the engine's U_Y consumption count equals the
        number of materialized observations (no observation is consumed by
        anything but a valid completion)."""
        configs = [
            make_config(batch_size=3),
            make_config(batch_size=4, master_seed=51,
                        durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"}),
            make_config(batch_size=5, scenario="q2_single_shift",
                        shift_length_h="12"),
            make_config(batch_size=4, scenario="q3_two_shift",
                        shift_length_h="10", shifts_per_day=2),
        ]
        for cfg in configs:
            res = run(cfg)
            self.assertEqual(
                res.summary["u_consumption_counts"]["u_y"],
                len(records(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)),
            )


class TestNamespaceNonCollision(unittest.TestCase):
    """G3-SPEC-V1.0 section 11 item 4 + section 3 ``experiment_namespaces`` /
    section 8 ``data_separation``: the six namespaces are pairwise disjoint and
    pilot/tuning/holdout/formal worlds never collide."""

    FROZEN_SIX: tuple[str, ...] = (
        "development_unit", "pilot", "h1_tuning", "g3_holdout", "q2_formal",
        "q3_formal",
    )

    def test_six_namespaces_frozen_pairwise_disjoint(self) -> None:
        self.assertEqual(ks.NAMESPACES, self.FROZEN_SIX)
        self.assertEqual(len(set(ks.NAMESPACES)), 6)
        self.assertEqual(ks.ALL_NAMESPACES,
                         self.FROZEN_SIX + (ks.H2_RESERVED_NAMESPACE,))
        # same world identity under every pair of namespaces -> distinct U
        for a, b in itertools.combinations(ks.NAMESPACES, 2):
            self.assertNotEqual(ks.u_x(a, 0, 1, "A", 7), ks.u_x(b, 0, 1, "A", 7))
            self.assertNotEqual(ks.u_y(a, 0, 1, "B", 1, 7), ks.u_y(b, 0, 1, "B", 1, 7))
            self.assertNotEqual(ks.u_l(a, 0, "E", 1, 7), ks.u_l(b, 0, "E", 1, 7))
        # H2 is reserved only: no stream U may be consumed under it
        for helper, args in (
            (ks.u_x, (ks.H2_RESERVED_NAMESPACE, 0, 1, "A", 7)),
            (ks.u_d, (ks.H2_RESERVED_NAMESPACE, 0, 1, 7)),
            (ks.u_y, (ks.H2_RESERVED_NAMESPACE, 0, 1, "A", 1, 7)),
            (ks.u_l, (ks.H2_RESERVED_NAMESPACE, 0, "A", 1, 7)),
        ):
            with self.assertRaises(ValueError):
                helper(*args)

    def test_runs_in_every_namespace_pairwise_distinct(self) -> None:
        """Same seed/replicate in all six namespaces -> pairwise distinct
        canonical logs and distinct U_X; each run is internally consistent with
        its own namespace."""
        logs: dict[str, bytes] = {}
        ux: dict[str, dict[int, dict[str, str]]] = {}
        for ns in ks.NAMESPACES:
            res = run(make_config(batch_size=3, namespace=ns))
            logs[ns] = res.canonical_event_log()
            ux[ns] = {
                r["device_id"]: r["u"]
                for r in records(res.event_log, rd.EVENT_TRUE_STATE_GENERATED)
            }
            self.assertEqual(
                ux[ns][1]["A"],
                str(ks.u_x(ns, REP, 1, "A", SEED)),
                f"run in {ns} not consistent with its own namespace",
            )
        for a, b in itertools.combinations(ks.NAMESPACES, 2):
            self.assertNotEqual(logs[a], logs[b], f"{a} vs {b} logs collided")
            self.assertNotEqual(ux[a][1], ux[b][1], f"{a} vs {b} U_X collided")

    def test_same_namespace_seed_and_replicate_separation(self) -> None:
        """Within one namespace, different master seeds or replicate ids give
        distinct canonical worlds."""
        base = ks.u_x(ks.NAMESPACE_PILOT, 0, 1, "A", 7)
        self.assertNotEqual(base, ks.u_x(ks.NAMESPACE_PILOT, 0, 1, "A", 8))
        self.assertNotEqual(base, ks.u_x(ks.NAMESPACE_PILOT, 1, 1, "A", 7))
        r0 = run(make_config(batch_size=3, namespace=ks.NAMESPACE_PILOT,
                             master_seed=7, replicate_id=0))
        r1 = run(make_config(batch_size=3, namespace=ks.NAMESPACE_PILOT,
                             master_seed=8, replicate_id=0))
        r2 = run(make_config(batch_size=3, namespace=ks.NAMESPACE_PILOT,
                             master_seed=7, replicate_id=1))
        self.assertNotEqual(r0.canonical_event_log(), r1.canonical_event_log())
        self.assertNotEqual(r0.canonical_event_log(), r2.canonical_event_log())

    def test_seed_pool_separation_across_namespaces(self) -> None:
        """Section 8: each namespace uses an independent seed pool -- equal
        seeds in different namespaces never collide (the namespace is a first-
        class physical key field)."""
        worlds = {}
        for ns in (ks.NAMESPACE_PILOT, ks.NAMESPACE_H1_TUNING,
                   ks.NAMESPACE_G3_HOLDOUT, ks.NAMESPACE_Q2_FORMAL):
            u = ks.u_x(ns, 0, 1, "A", 12345)
            worlds[ns] = u
            res = run(make_config(batch_size=2, namespace=ns, master_seed=12345))
            # each world is internally a pure canonical-key world
            assert_pure_keyed_world(self, res)
        for a, b in itertools.combinations(worlds, 2):
            self.assertNotEqual(worlds[a], worlds[b], f"{a} == {b} under seed 12345")
        # h1_tuning vs g3_holdout with the SAME seed produce disjoint key sets
        res_t = run(make_config(batch_size=3, namespace=ks.NAMESPACE_H1_TUNING,
                                master_seed=99, replicate_id=0))
        res_h = run(make_config(batch_size=3, namespace=ks.NAMESPACE_G3_HOLDOUT,
                                master_seed=99, replicate_id=0))
        keys_t = set(consumed_u_map(res_t))
        keys_h = set(consumed_u_map(res_h))
        self.assertEqual(keys_t & keys_h, set(),
                         "h1_tuning and g3_holdout key sets must be disjoint")
        self.assertNotEqual(res_t.canonical_event_log(), res_h.canonical_event_log())


class TestReproducibility(unittest.TestCase):
    """G3-SPEC-V1.0 section 11 item 5: same seed + config + code ->
    byte/canonical reproducible output; explicit run metadata is the only
    allowed difference."""

    def test_byte_identical_canonical_log_repeated_runs(self) -> None:
        cfg = make_config(batch_size=5, scenario="q2_single_shift",
                          shift_length_h="12")
        results = [run(cfg) for _ in range(3)]
        for other in results[1:]:
            self.assertEqual(results[0].canonical_event_log(),
                             other.canonical_event_log())
            self.assertEqual(results[0].metrics, other.metrics)
            self.assertEqual(results[0].summary, other.summary)

    def test_config_dict_roundtrip_reproducible(self) -> None:
        cfg = make_config(batch_size=4)
        cfg2 = rd.RandomDesConfig.from_dict(cfg.to_dict())
        self.assertEqual(run(cfg).canonical_event_log(),
                         run(cfg2).canonical_event_log())

    def test_run_metadata_excluded_from_canonical_log(self) -> None:
        cfg = make_config(batch_size=3)
        base = run(cfg).canonical_event_log()
        r1 = run(cfg, run_metadata={"run_id": "run-abc", "wall_clock": "x"})
        r2 = run(cfg, run_metadata={"run_id": "run-def", "wall_clock": "y"})
        self.assertEqual(r1.canonical_event_log(), base)
        self.assertEqual(r2.canonical_event_log(), base)
        self.assertEqual(r1.run_metadata["run_id"], "run-abc")
        self.assertEqual(r2.run_metadata["run_id"], "run-def")

    def test_interleaved_runs_no_global_state(self) -> None:
        """Engine instances are stateless w.r.t. each other: running another
        config in between never perturbs the canonical output."""
        cfg_a = make_config(batch_size=4, scenario="q2_single_shift",
                            shift_length_h="12")
        cfg_b = make_config(batch_size=3, namespace=ks.NAMESPACE_PILOT,
                            master_seed=11)
        log_a1 = run(cfg_a).canonical_event_log()
        _ = run(cfg_b).canonical_event_log()
        log_a2 = run(cfg_a).canonical_event_log()
        self.assertEqual(log_a1, log_a2)

    def test_reproducible_across_module_reload(self) -> None:
        """Reloading the S1/S2/S3 modules (same code) does not change the
        canonical output (no hidden module-level RNG state).  This check runs
        in a subprocess so the reload cannot perturb the module identities
        that sibling test suites in this process rely on."""
        cfg = make_config(batch_size=4)
        raw_json = json.dumps(cfg.to_dict(), ensure_ascii=False)
        script = textwrap.dedent(
            """
            import importlib, json, sys
            from pathlib import Path
            BASE = Path({base!r})
            CODE = BASE / "04_代码"
            sys.path.insert(0, str(CODE / "main_model"))
            sys.path.insert(0, str(CODE))
            from g3 import key_schema_v1 as ks
            from g3 import lifetime_regeneration_v1 as lr
            from g3 import random_des_v1 as rd
            raw = json.loads(sys.argv[1])
            log_before = rd.run_random_des(
                rd.RandomDesConfig.from_dict(raw)
            ).canonical_event_log()
            importlib.reload(ks)
            importlib.reload(lr)
            importlib.reload(rd)
            log_after = rd.run_random_des(
                rd.RandomDesConfig.from_dict(raw)
            ).canonical_event_log()
            if log_before != log_after:
                sys.exit(1)
            print("RELOAD_REPRODUCIBLE")
            """
        ).format(base=str(BASE))
        result = subprocess.run(
            [sys.executable, "-c", script, raw_json],
            capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(
            result.returncode, 0,
            f"reload reproducibility failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("RELOAD_REPRODUCIBLE", result.stdout)


class TestForbiddenPhysicalKeyFields(unittest.TestCase):
    """G3-SPEC-V1.0 section 3 ``forbidden_in_physical_keys``: run_id /
    execution_no / restart_no / wall-clock / container iteration / event
    insertion / strategy / policy / squad / worker / agent never enter a
    canonical U key."""

    def test_forbidden_fields_list_matches_frozen_contract(self) -> None:
        self.assertEqual(
            ks.FORBIDDEN_PHYSICAL_KEY_FIELDS,
            (
                "run_id", "execution_no", "restart_no", "wall-clock timestamp",
                "container iteration order", "event insertion order",
                "strategy_id", "policy_id", "squad_id", "worker_id", "agent_id",
            ),
        )

    def test_api_signature_excludes_forbidden_fields(self) -> None:
        params: set[str] = set()
        for func in (ks.canonical_key, ks.u_x, ks.u_d, ks.u_y, ks.u_l):
            params.update(inspect.signature(func).parameters)
        forbidden = set(ks.FORBIDDEN_PHYSICAL_KEY_FIELDS)
        # map the frozen literals to the tokens they forbid
        tokens = {
            "run_id", "execution_no", "restart_no", "strategy", "policy",
            "squad", "worker", "agent", "timestamp", "iteration", "insertion",
            "wall",
        }
        self.assertEqual(params & tokens, set(),
                         f"forbidden tokens leaked into API parameters: "
                         f"{sorted(params & tokens)}")

    def test_forbidden_token_injection_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, "run_id", None, None, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, "squad_id", None, None, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, 1, "policy_id", None, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, 1, "agent_id", None, SEED)
        with self.assertRaises(ValueError):
            ks.canonical_key(NS, REP, 1, "execution_no", None, SEED)

    def test_consumed_keys_match_pattern_and_never_contain_forbidden_tokens(
        self,
    ) -> None:
        """Every physical U key consumed by real experiments (all six
        namespaces, both calendars, both strategies) matches the canonical
        pattern and contains no forbidden execution-metadata token."""
        configs = [
            make_config(batch_size=3, namespace=ks.NAMESPACE_DEVELOPMENT_UNIT),
            make_config(batch_size=3, namespace=ks.NAMESPACE_PILOT, master_seed=11),
            make_config(batch_size=3, namespace=ks.NAMESPACE_H1_TUNING, master_seed=13),
            make_config(batch_size=3, namespace=ks.NAMESPACE_G3_HOLDOUT, master_seed=17),
            make_config(batch_size=3, namespace=ks.NAMESPACE_Q2_FORMAL, master_seed=19),
            make_config(batch_size=3, namespace=ks.NAMESPACE_Q3_FORMAL, master_seed=23),
            make_config(batch_size=4, namespace=ks.NAMESPACE_Q3_FORMAL,
                        master_seed=5, replicate_id=2, scenario="q3_two_shift",
                        shift_length_h="10", shifts_per_day=2),
            self._crn_pair_config(tau_pm=Fraction(120)),
        ]
        for cfg in configs:
            res = run(cfg)
            keys = consumed_u_map(res)
            self.assertGreater(len(keys), 0)
            for key in keys:
                self.assertRegex(key, CANONICAL_KEY_PATTERN, key)
                for token in FORBIDDEN_TOKENS:
                    self.assertNotIn(token, key, f"forbidden token {token!r} in {key!r}")

    @staticmethod
    def _crn_pair_config(tau_pm):
        return make_config(
            batch_size=4, namespace=ks.NAMESPACE_H1_TUNING, tau_pm=tau_pm,
            durations=CRN_DURATIONS,
        )

    def test_uy_keys_exclude_squad_execution_restart(self) -> None:
        """In a two-squad run (q3_two_shift) the keyed U_Y is a function of only
        (namespace, replicate, device, process, attempt, seed): squads /
        execution numbering / restarts are visible in the log but never in the
        physical keys."""
        cfg = make_config(
            batch_size=4, namespace=ks.NAMESPACE_Q3_FORMAL,
            master_seed=5, replicate_id=2, scenario="q3_two_shift",
            shift_length_h="10", shifts_per_day=2,
        )
        res = run(cfg)
        # both squads really appear in the run
        squads = {r["squad_id"] for r in records(res.event_log,
                                                 sm.EventType.ACTIVITY_START.value)}
        self.assertTrue({1, 2} <= squads)
        ns, rep, seed = cfg.namespace, cfg.replicate_id, cfg.master_seed
        for rec in records(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value):
            expected = ks.canonical_key(
                ns, rep, rec["device_id"], rec["process"],
                rec["effective_attempt_no"], seed,
            )
            self.assertEqual(rec["u_key"], expected)
            self.assertEqual(rec["u"], str(ks.u_y(
                ns, rep, rec["device_id"], rec["process"],
                rec["effective_attempt_no"], seed,
            )))
            for token in ("squad", "execution_no", "restart_no"):
                self.assertNotIn(token, rec["u_key"])


class TestCanonicalExactness(unittest.TestCase):
    """G3-SPEC-V1.0 section 3 mapping: no binary float anywhere on canonical
    paths; the keyed mapping and the engine's U values are exact Fractions."""

    def test_no_float_literal_in_canonical_modules(self) -> None:
        for module in (ks, rd):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, float):
                    self.fail(
                        f"binary float literal in canonical module "
                        f"{Path(module.__file__).name}: {node.value!r}"
                    )

    def test_no_runtime_hash_or_order_rng_in_canonical_modules(self) -> None:
        for module in (ks, rd):
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertNotIn("import random", source)
            self.assertNotIn("from random", source)
            self.assertNotIn("os.urandom", source)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "hash"
                ):
                    self.fail(
                        f"runtime builtin hash() call in "
                        f"{Path(module.__file__).name} (language runtime hash "
                        f"is forbidden)"
                    )

    def test_uniform_mapping_returns_exact_fraction(self) -> None:
        key = ks.canonical_key(ks.NAMESPACE_H1_TUNING, 3, 7, "A", 1, 20260814)
        u = ks.uniform_from_key(key)
        self.assertIsInstance(u, Fraction)
        self.assertGreaterEqual(u, Fraction(0))
        self.assertLess(u, Fraction(1))
        # denominator is exactly 2^65 (the frozen mapping (2*head+1)/2^65)
        self.assertEqual(u.denominator, 1 << 65)

    def test_consumed_u_and_metrics_are_exact_fractions(self) -> None:
        res = run(make_config(batch_size=4, scenario="q2_single_shift",
                              shift_length_h="12"))
        for key, value in consumed_u_map(res).items():
            frac = Fraction(value)
            self.assertTrue(0 <= frac < 1, key)
        for name in ("T", "T_days", "YXB_A", "YXB_B", "YXB_C", "YXB_E"):
            Fraction(res.metrics[name])  # must parse as an exact rational
        self.assertNotIn("float", str(type(res.metrics["T"])))


class TestShiftLengthConfigValidation(unittest.TestCase):
    """S6 acceptance addendum (CR-V3.1/C18 + AGENTS.md 参数无效必须显式失败):
    a calendar scenario (q2_single_shift / q3_two_shift) whose task durations
    exceed the shift length can never start any task (``_is_legal`` requires
    now + duration <= shift_end, and a shift is exactly ``shift_length_h``
    long), so such a batch would silently never terminate; it must be rejected
    explicitly at parse time.  Duration == shift length stays legal
    (恰班末完成允许, P062).  isolated_small_case keeps its existing behavior
    (the CRN fixtures run 40 h durations in a 1000000 h single shift)."""

    def test_calendar_duration_exceeding_shift_length_rejected(self) -> None:
        """Defect reproduction: durations 40 h in a 12 h single shift (or a
        10 h two-shift) were silently accepted and the batch never terminated;
        now ``RandomDesConfig.from_dict`` must raise ``RandomDesConfigError``
        for both calendar scenarios."""
        for scenario, shift_length_h, shifts_per_day in (
            ("q2_single_shift", "12", 1),
            ("q3_two_shift", "10", 2),
        ):
            with self.assertRaises(rd.RandomDesConfigError):
                make_config(
                    batch_size=2, scenario=scenario,
                    shift_length_h=shift_length_h,
                    shifts_per_day=shifts_per_day,
                    durations={"A": "40", "B": "40", "C": "40", "E": "3"},
                )

    def test_calendar_duration_equal_to_shift_length_still_legal(self) -> None:
        """Boundary: duration == shift length is exactly-at-shift-end legal
        (P062); the config is accepted and the batch terminates."""
        cfg = make_config(
            batch_size=2, scenario="q2_single_shift", shift_length_h="12",
            durations={"A": "12", "B": "12", "C": "12", "E": "3"},
        )
        self.assertEqual(cfg.durations["A"], Fraction(12))
        res = run(cfg)
        ends = records(res.event_log, sm.EventType.SIMULATION_END.value)
        self.assertEqual(len(ends), 1)

    def test_isolated_small_case_keeps_existing_behavior(self) -> None:
        """Non-calendar scenario is exempt from the shift-length check:
        durations longer than the nominal shift length stay accepted (the CRN
        fixture pattern) and the run still terminates."""
        cfg = make_config(
            batch_size=3, scenario="isolated_small_case",
            shift_length_h="1000000",
            durations={"A": "40", "B": "40", "C": "40", "E": "3"},
        )
        res = run(cfg)
        self.assertTrue(records(res.event_log, sm.EventType.SIMULATION_END.value))


if __name__ == "__main__":
    unittest.main()
