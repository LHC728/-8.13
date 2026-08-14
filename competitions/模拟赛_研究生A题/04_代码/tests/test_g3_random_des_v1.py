"""Unit tests for G3-SPEC-V1.0 S3: random_des_v1 (stdlib only, Python 3.12).

Frozen-contract coverage (the 14 required points plus extras):

  1. small-batch random true-state/observation stream driving correctness
     (U_X/U_D/U_Y/U_L consumption legality and exact keyed values)
  2. interruptions never consume observation U; same seed + two policies ->
     U_Y key->value alignment (CRN)
  3. random failure interruption: age/YXB counted, no observation, effective
     attempt unchanged, device unavailable -> replacement + calibration
  4. replacement: generation+1, age reset to 0, new generation binds a new U_L
  5. preventive replacement triggers (a >= tau_pm) and NO_PM never triggers
  6. a+d > 240 mandatory replace-first; a+d == 240 completion-settles-first
     then mandatory replacement
  7. fixed FCFS preserved (no SPT/LPT: per-resource start order is
     non-decreasing in the frozen FCFS key)
  8. deterministic reproducibility (same seed+config -> byte-identical
     canonical event log)
  9. namespace isolation (h1_tuning vs g3_holdout -> different U / logs)
 10. C18 liveness (strictly advancing time, finite same-instant closures,
     no deadlock, WAKE_UP on empty calendar)
 11. exactly-at-shift-end completion allowed; shift-end blocking enforced
 12. last-device terminal stops the clock (T == last DEVICE_TERMINAL time;
     no turnover after the last terminal)
 13. small-batch (N=60) S/PL/PW/YXB structural sanity
 14. C24 instrument fields exist and satisfy the documented invariants

Plus: D materialized exactly once at E-eligibility (never redrawn by an E
retest; never created for early exits), SEM-21 preload rule, config/kernel/
float validation, parameters.csv audit, no binary float in canonical paths
(AST scan), q2/q3 calendar interface (C15; no formal runs), and the
illegal-crossing 240 backstop seam.

All expectations derive from the frozen G3-SPEC-V1.0 contract and
parameters.csv; no formal competition numbers are produced. Observation
kernels: A/B/C use the frozen literal main-semantics closed form
((1-q)alpha = q beta = e/2, P060); the E kernel is a frozen test input
(P056/P057 are 待求; the engine accepts any valid kernel). Some tests use
custom durations purely to force deterministic boundary/trigger moments;
the frozen durations P006-P009 drive the structural and FCFS tests.
"""

from __future__ import annotations

import ast
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

from des import state_models_v1 as sm  # noqa: E402
from g3 import key_schema_v1 as ks  # noqa: E402
from g3 import lifetime_regeneration_v1 as lr  # noqa: E402
from g3 import random_des_v1 as rd  # noqa: E402

PARAMS_CSV = BASE / "02_数据" / "parameters.csv"
SOURCE_PATH = Path(rd.__file__)

NS = ks.NAMESPACE_DEVELOPMENT_UNIT
SEED = 7
REP = 0

# Frozen defect probabilities (P026-P029), independently restated.
DEFECT_Q: dict[str, Fraction] = {
    "A": Fraction(25, 1000),
    "B": Fraction(3, 100),
    "C": Fraction(2, 100),
}
DEFECT_Q_D = Fraction(1, 1000)

# Frozen single-test unconditional kernels (P060; (1-q)alpha = q beta = e/2).
FROZEN_E: dict[str, Fraction] = {
    "A": Fraction(3, 100),
    "B": Fraction(4, 100),
    "C": Fraction(2, 100),
}


def frozen_kernel() -> dict[str, dict[str, Fraction]]:
    kernel: dict[str, dict[str, Fraction]] = {}
    for proc in ("A", "B", "C"):
        alpha, beta = rd.frozen_single_test_alpha_beta(DEFECT_Q[proc], FROZEN_E[proc])
        kernel[proc] = {"alpha": alpha, "beta": beta}
    # E kernel: frozen test input (P056/P057 are 待求; any valid kernel is
    # accepted by the engine).
    kernel["E"] = {"alpha": Fraction(1, 50), "beta": Fraction(1, 2)}
    return kernel


def make_config(
    batch_size: int = 3,
    namespace: str = NS,
    master_seed: int = SEED,
    replicate_id: int = REP,
    tau_pm=lr.NO_PM_BEFORE_MANDATORY,
    kernel=None,
    scenario: str = "isolated_small_case",
    shift_length_h: str = "1000000",
    shifts_per_day: int = 1,
    durations=None,
    turnover_profile: str = "1h_literal",
) -> rd.RandomDesConfig:
    if kernel is None:
        kernel = frozen_kernel()
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
    )


def run(config: rd.RandomDesConfig, **kwargs) -> rd.RandomDesResult:
    return rd.run_random_des(config, **kwargs)


def records(log: list[dict], event_type: str) -> list[dict]:
    return [r for r in log if r["event_type"] == event_type]


def recs_for(log: list[dict], event_type: str, **fields) -> list[dict]:
    out = []
    for r in log:
        if r["event_type"] != event_type:
            continue
        if all(r.get(key) == value for key, value in fields.items()):
            out.append(r)
    return out


class _Base(unittest.TestCase):
    """Shared helpers."""

    @staticmethod
    def u_x(device: int, sub: str, namespace: str = NS, seed: int = SEED, rep: int = REP):
        return str(ks.u_x(namespace, rep, device, sub, seed))

    @staticmethod
    def u_y(device: int, process: str, attempt: int, namespace: str = NS, seed: int = SEED, rep: int = REP):
        return str(ks.u_y(namespace, rep, device, process, attempt, seed))

    @staticmethod
    def u_d(device: int, namespace: str = NS, seed: int = SEED, rep: int = REP):
        return str(ks.u_d(namespace, rep, device, seed))

    @staticmethod
    def u_l(resource: str, generation: int, namespace: str = NS, seed: int = SEED, rep: int = REP):
        return str(ks.u_l(namespace, rep, resource, generation, seed))


class TestStreamConsumption(_Base):
    """Required point 1: U_X/U_D/U_Y/U_L consumption correctness on a small
    batch, plus D materialization timing (E2 before E release; exactly once;
    never redrawn by an E retest; never for early exits)."""

    def test_u_x_consumed_once_per_device_subsystem(self) -> None:
        res = run(make_config(batch_size=3))
        generated = records(res.event_log, rd.EVENT_TRUE_STATE_GENERATED)
        self.assertEqual(len(generated), 3)
        for rec in generated:
            device = rec["device_id"]
            for sub in ("A", "B", "C"):
                self.assertEqual(rec["u"][sub], self.u_x(device, sub))
                expected_problem = Fraction(self.u_x(device, sub)) < DEFECT_Q[sub]
                self.assertIs(rec["true_state"][sub], expected_problem)
        # exactly 3*N U_X consumed
        self.assertEqual(res.summary["u_consumption_counts"]["u_x"], 9)

    def test_u_y_consumed_only_on_valid_completion(self) -> None:
        res = run(make_config(batch_size=3))
        obs = records(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)
        self.assertGreaterEqual(len(obs), 3 * 4)  # >= A/B/C/E per device
        for rec in obs:
            self.assertEqual(
                rec["u"],
                self.u_y(rec["device_id"], rec["process"], rec["effective_attempt_no"]),
            )
        self.assertEqual(
            res.summary["u_consumption_counts"]["u_y"], len(obs)
        )

    def test_u_d_consumed_once_at_e_eligibility(self) -> None:
        # A/B/C always PASS (alpha=0,beta=1), E always ABNORMAL (alpha=1,beta=0):
        # every device reaches E exactly once -> D materialized exactly once,
        # E retest never redraws D, device exits via E.
        kernel = {
            p: {"alpha": Fraction(0), "beta": Fraction(1)} for p in ("A", "B", "C")
        }
        kernel["E"] = {"alpha": Fraction(1), "beta": Fraction(0)}
        res = run(make_config(batch_size=3, kernel=kernel))
        d_created = records(res.event_log, sm.EventType.D_CREATED.value)
        self.assertEqual(len(d_created), 3)  # once per device, no redraw
        for rec in d_created:
            self.assertEqual(rec["u"], self.u_d(rec["device_id"]))
            self.assertIn(rec["d_state"], ("normal", "problem"))
        # every device exits via E after E1+E2 abnormal; no D for early exits
        self.assertEqual(
            [r["device_id"] for r in d_created], [1, 2, 3]
        )
        # D_CREATED seq < E TASK_RELEASE seq at the same timestamp
        for rec in d_created:
            e_release = recs_for(
                res.event_log, sm.EventType.TASK_RELEASE.value,
                device_id=rec["device_id"], process="E", effective_attempt_no=1,
            )
            self.assertEqual(len(e_release), 1)
            self.assertLess(rec["seq"], e_release[0]["seq"])

    def test_early_exit_never_materializes_d(self) -> None:
        # all-ABNORMAL kernel: devices exit before A/B/C all-PASS -> no D.
        kernel = {
            p: {"alpha": Fraction(1), "beta": Fraction(0)} for p in ("A", "B", "C", "E")
        }
        res = run(make_config(batch_size=2, kernel=kernel))
        self.assertEqual(len(records(res.event_log, sm.EventType.D_CREATED.value)), 0)
        self.assertEqual(
            [d for d in res.summary["devices"].values()],
            [d for d in res.summary["devices"].values() if d["terminal_state"] == "EXITED"],
        )

    def test_u_l_exactly_once_per_resource_generation(self) -> None:
        # seed 51: B generation-1 lifetime in (5,55)h -> failure -> replacement
        # (generation 2) binds a new U_L; initial U_L for all four resources.
        res = run(
            make_config(batch_size=1, master_seed=51, durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"})
        )
        replacements = records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START)
        self.assertEqual(len(replacements), 1)
        rep = replacements[0]
        self.assertEqual(rep["resource_id"], "B")
        self.assertEqual(rep["old_generation"], 1)
        self.assertEqual(rep["new_generation"], 2)
        self.assertEqual(rep["u"], self.u_l("B", 2, seed=51))
        self.assertEqual(res.summary["u_consumption_counts"]["u_l"], 4 + 1)


class TestObservationAlignment(_Base):
    """Required point 2: interruptions never consume observation U; same seed
    + two policies -> the U_Y key->value map aligns (CRN)."""

    def test_no_observation_consumed_by_failure_interruption(self) -> None:
        # seed 51: B1 interrupted by equipment failure; the retry of the SAME
        # effective attempt (1) consumes the SAME keyed U_Y.
        cfg = make_config(
            batch_size=1, master_seed=51,
            durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"},
        )
        res = run(cfg)
        fails = records(res.event_log, rd.EVENT_EQUIPMENT_FAILURE)
        self.assertEqual(len(fails), 1)
        fail = fails[0]
        # no observation at the failure instant for that attempt
        at_fail = recs_for(
            res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value,
            device_id=fail["device_id"], process="B",
            effective_attempt_no=fail["effective_attempt_no"],
        )
        obs_times = {r["event_time"] for r in at_fail}
        self.assertNotIn(fail["event_time"], obs_times)
        # the retry completes and consumes the same keyed U_Y (attempt 1)
        b_obs = recs_for(
            res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value,
            device_id=1, process="B", effective_attempt_no=1,
        )
        self.assertEqual(len(b_obs), 1)
        self.assertEqual(b_obs[0]["u"], self.u_y(1, "B", 1, seed=51))

    def test_same_seed_two_policies_uy_alignment(self) -> None:
        # d=40, N=4, seed 7: NO_PM serves the 4th A-test at age 120, while
        # tau_pm=120 preventive-replaces first -> different schedules, same
        # keyed U_Y values for shared completions.
        kwargs = dict(
            batch_size=4,
            durations={"A": "40", "B": "40", "C": "40", "E": "3"},
        )
        res_nopm = run(make_config(tau_pm=lr.NO_PM_BEFORE_MANDATORY, **kwargs))
        res_pm = run(make_config(tau_pm=Fraction(120), **kwargs))
        map_nopm = {
            (r["device_id"], r["process"], r["effective_attempt_no"]): r["u"]
            for r in records(res_nopm.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)
        }
        map_pm = {
            (r["device_id"], r["process"], r["effective_attempt_no"]): r["u"]
            for r in records(res_pm.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)
        }
        # interruption-free principle: the keyed U is execution-order
        # independent, so shared keys agree exactly.
        shared = set(map_nopm) & set(map_pm)
        self.assertGreater(len(shared), 0)
        for key in shared:
            self.assertEqual(map_nopm[key], map_pm[key])
            self.assertEqual(
                map_nopm[key],
                self.u_y(key[0], key[1], key[2]),
            )
        # both runs consume U_Y only for valid completions
        self.assertEqual(
            res_nopm.summary["u_consumption_counts"]["u_y"], len(map_nopm)
        )
        self.assertEqual(res_pm.summary["u_consumption_counts"]["u_y"], len(map_pm))


class TestFailureInterruption(_Base):
    """Required point 3: random failure interruption -> fragment counts
    age/YXB, no observation, effective attempt unchanged, device unavailable
    and replaced + calibrated."""

    def test_failure_fragment_accounting(self) -> None:
        cfg = make_config(
            batch_size=1, master_seed=51,
            durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"},
        )
        res = run(cfg)
        fails = records(res.event_log, rd.EVENT_EQUIPMENT_FAILURE)
        self.assertEqual(len(fails), 1)
        fail = fails[0]
        self.assertEqual(fail["resource_id"], "B")
        self.assertEqual(fail["effective_attempt_no"], 1)
        elapsed = Fraction(fail["elapsed_hours"])
        self.assertGreater(elapsed, Fraction(0))
        self.assertLess(elapsed, Fraction(60))  # strictly before task end
        # fragment counts age: equipment age at failure == elapsed (started at 0)
        self.assertEqual(Fraction(fail["equipment_age_at_failure"]), elapsed)
        # fragment counts YXB numerator: the ledger includes the failed
        # fragment (plus any later fragments, e.g. the retry)
        self.assertGreaterEqual(
            Fraction(res.summary["ledger_elapsed_h"]["B"]), elapsed
        )
        # no observation for the interrupted fragment
        cancel = recs_for(
            res.event_log, sm.EventType.TASK_CANCEL.value,
            process="B", cancel_reason=rd.CANCEL_REASON_EQUIPMENT_FAILURE,
        )
        self.assertEqual(len(cancel), 1)
        self.assertEqual(cancel[0]["outcome"], sm.Outcome.NONE.value)
        # attempt unchanged: the retry keeps effective_attempt_no == 1
        b_starts = recs_for(res.event_log, sm.EventType.ACTIVITY_START.value, process="B")
        self.assertEqual([s["effective_attempt_no"] for s in b_starts], [1, 1])
        # device unavailable -> replacement + calibration before the retry
        replacements = records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START)
        self.assertEqual(len(replacements), 1)
        self.assertEqual(replacements[0]["kind"], rd.REPLACEMENT_KIND_FAILURE)
        self.assertEqual(replacements[0]["trigger"], rd.REPLACEMENT_TRIGGER_MID_FRAGMENT_FAILURE)
        # retry starts at age 0 (after calibration)
        self.assertEqual(
            Fraction(b_starts[1]["equipment_age_at_start"]), Fraction(0)
        )
        cal_done = records(res.event_log, rd.EVENT_EQUIPMENT_CALIBRATION_COMPLETE)
        self.assertEqual(len(cal_done), 1)
        self.assertEqual(cal_done[0]["resource_id"], "B")
        # calibration duration frozen: 20 min = 1/3 h (P011)
        self.assertEqual(
            Fraction(replacements[0]["calibration_duration_hours"]), Fraction(1, 3)
        )


class TestReplacement(_Base):
    """Required point 4: replacement -> generation+1, age reset, new U_L."""

    def test_replacement_generation_age_ul(self) -> None:
        cfg = make_config(
            batch_size=1, master_seed=51,
            durations={"A": "2.5", "B": "60", "C": "2.5", "E": "3"},
        )
        res = run(cfg)
        fail = records(res.event_log, rd.EVENT_EQUIPMENT_FAILURE)[0]
        rep = records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START)[0]
        self.assertEqual(rep["old_generation"], 1)
        self.assertEqual(rep["new_generation"], 2)
        # the replaced device was at its sampled failure age
        self.assertEqual(
            Fraction(rep["age_before"]), Fraction(fail["equipment_age_at_failure"])
        )
        # new generation binds a new U_L: exact keyed value
        self.assertEqual(rep["u"], self.u_l("B", 2, seed=51))
        self.assertNotEqual(rep["u"], self.u_l("B", 1, seed=51))
        # metrics reflect generation 2 and one replacement
        self.assertEqual(res.metrics["equipment"]["B"]["generation"], 2)
        self.assertEqual(res.metrics["equipment"]["B"]["replacement_count"], 1)

    def test_mandatory_240_replacement_generation(self) -> None:
        # deterministic a+d==240 construction: d=80, N=3 -> device 3's A/B/C
        # complete at age exactly 240 -> post-completion mandatory replacement.
        cfg = make_config(
            batch_size=3, durations={"A": "80", "B": "80", "C": "80", "E": "3"}
        )
        res = run(cfg)
        reps = records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START)
        self.assertGreaterEqual(len(reps), 3)
        for rep in reps:
            self.assertEqual(rep["kind"], rd.REPLACEMENT_KIND_MANDATORY_240)
            self.assertEqual(rep["trigger"], rd.REPLACEMENT_TRIGGER_POST_COMPLETION_240)
            self.assertEqual(rep["old_generation"], 1)
            self.assertEqual(rep["new_generation"], 2)
            self.assertEqual(rep["u"], self.u_l(rep["resource_id"], 2))


class TestPreventivePolicy(_Base):
    """Required point 5: preventive replacement triggers only when
    a >= tau_pm; NO_PM never triggers (G)."""

    def test_preventive_triggers_at_tau_pm(self) -> None:
        # d=40, N=4: after 3 A-tests the age is exactly 120 -> at the idle
        # decision point for the 4th A-test, tau_pm=120 preventive-replaces.
        cfg = make_config(
            batch_size=4, tau_pm=Fraction(120),
            durations={"A": "40", "B": "40", "C": "40", "E": "3"},
        )
        res = run(cfg)
        pm = [
            r for r in records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START)
            if r["kind"] == rd.REPLACEMENT_KIND_PREVENTIVE
        ]
        self.assertGreaterEqual(len(pm), 1)
        for rep in pm:
            self.assertEqual(rep["trigger"], rd.REPLACEMENT_TRIGGER_PREVENTIVE)
            self.assertGreaterEqual(Fraction(rep["age_before"]), Fraction(120))
        # after a preventive replacement the next A-test starts at age 0
        a_starts = recs_for(res.event_log, sm.EventType.ACTIVITY_START.value, process="A")
        ages = [Fraction(s["equipment_age_at_start"]) for s in a_starts]
        self.assertIn(Fraction(0), ages)
        # the preventive counts are reported
        total_pm = sum(
            res.metrics["equipment"][r]["preventive_replacement_count"]
            for r in ("A", "B", "C", "E")
        )
        self.assertEqual(total_pm, len(pm))

    def test_no_pm_never_triggers(self) -> None:
        cfg = make_config(
            batch_size=4, tau_pm=lr.NO_PM_BEFORE_MANDATORY,
            durations={"A": "40", "B": "40", "C": "40", "E": "3"},
        )
        res = run(cfg)
        pm = [
            r for r in records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START)
            if r["kind"] == rd.REPLACEMENT_KIND_PREVENTIVE
        ]
        self.assertEqual(len(pm), 0)
        # the 4th A-test is served with age 120 under NO_PM
        a_starts = recs_for(res.event_log, sm.EventType.ACTIVITY_START.value, process="A")
        ages = [Fraction(s["equipment_age_at_start"]) for s in a_starts]
        self.assertIn(Fraction(120), ages)
        self.assertEqual(
            sum(res.metrics["equipment"][r]["preventive_replacement_count"] for r in ("A", "B", "C", "E")),
            0,
        )

    def test_preventive_opportunity_counting_consistency(self) -> None:
        # The c24 preventive-opportunity counter counts decision points with
        # age >= 120; each executed preventive replacement consumes exactly
        # one such opportunity, and the mandatory-240/a+d>240 replacements
        # are never counted as preventive (frozen constraint).
        cfg = make_config(
            batch_size=4, tau_pm=Fraction(120),
            durations={"A": "40", "B": "40", "C": "40", "E": "3"},
        )
        res = run(cfg)
        pm = [
            r for r in records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START)
            if r["kind"] == rd.REPLACEMENT_KIND_PREVENTIVE
        ]
        opps = res.metrics["c24"]["preventive_replacement_opportunity_count"]
        self.assertGreaterEqual(opps, len(pm))
        # every preventive replacement is reported in the equipment metrics
        total_pm = sum(
            res.metrics["equipment"][r]["preventive_replacement_count"]
            for r in ("A", "B", "C", "E")
        )
        self.assertEqual(total_pm, len(pm))


class TestMandatory240(_Base):
    """Required point 6: a+d > 240 forced replace-first (never preventive);
    a+d == 240 completion-settles-first then mandatory replacement."""

    def test_a_plus_d_gt_240_forced_replace_first(self) -> None:
        # deterministic: d=90, N=4 -> 4th A-test would cross (180+90=270>240);
        # the head must NOT start before the forced replacement.
        cfg = make_config(
            batch_size=4, durations={"A": "90", "B": "90", "C": "90", "E": "3"}
        )
        res = run(cfg)
        reps = [
            r for r in records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START)
            if r["trigger"] == rd.REPLACEMENT_TRIGGER_A_PLUS_D_GT_240
        ]
        self.assertGreaterEqual(len(reps), 1)
        for rep in reps:
            self.assertEqual(rep["kind"], rd.REPLACEMENT_KIND_MANDATORY_240)
            d = {"A": Fraction(90), "B": Fraction(90), "C": Fraction(90), "E": Fraction(3)}[rep["resource_id"]]
            self.assertGreater(Fraction(rep["age_before"]) + d, Fraction(240))
            # the blocked head is served after the calibration at age 0
            # (queue/release preserved; replacement is NOT a preventive choice);
            # the service may begin at the same instant the calibration
            # completes (later seq), so compare by seq, not by event_time.
            cal = recs_for(
                res.event_log, rd.EVENT_EQUIPMENT_CALIBRATION_COMPLETE,
                resource_id=rep["resource_id"],
            )
            self.assertGreaterEqual(len(cal), 1)
            next_start = next(
                r for r in res.event_log
                if r["event_type"] == sm.EventType.ACTIVITY_START.value
                and r["resource_id"] == rep["resource_id"]
                and r["seq"] > cal[0]["seq"]
            )
            self.assertEqual(
                Fraction(next_start["equipment_age_at_start"]), Fraction(0)
            )

    def test_a_plus_d_gt_240_frozen_durations_evidence(self) -> None:
        # frozen durations P006-P009, N=100, q2 calendar, seed 33.
        res = run(
            make_config(
                batch_size=100, master_seed=33,
                scenario="q2_single_shift", shift_length_h="12",
            )
        )
        reps = [
            r for r in records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START)
            if r["trigger"] == rd.REPLACEMENT_TRIGGER_A_PLUS_D_GT_240
        ]
        self.assertGreaterEqual(len(reps), 1)
        rep = reps[0]
        d = {
            "A": Fraction(5, 2), "B": Fraction(2), "C": Fraction(5, 2), "E": Fraction(3)
        }[rep["resource_id"]]
        self.assertGreater(Fraction(rep["age_before"]) + d, Fraction(240))

    def test_a_plus_d_equals_240_completion_first(self) -> None:
        # deterministic: d=80, N=3 -> device 3's A/B/C complete at age exactly
        # 240: the completion and its observation settle BEFORE the mandatory
        # replacement.
        cfg = make_config(
            batch_size=3, durations={"A": "80", "B": "80", "C": "80", "E": "3"}
        )
        res = run(cfg)
        reps = [
            r for r in records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_START)
            if r["trigger"] == rd.REPLACEMENT_TRIGGER_POST_COMPLETION_240
        ]
        self.assertGreaterEqual(len(reps), 1)
        rep = reps[0]
        t = rep["event_time"]
        # a completion at age 240 at the same instant, with the observation
        # materialized before the replacement (completion-settles-first)
        comps = [
            r for r in records(res.event_log, sm.EventType.ACTIVITY_COMPLETE.value)
            if r["event_time"] == t and r.get("equipment_age_at_end") == "240"
        ]
        self.assertGreaterEqual(len(comps), 1)
        obs = [
            r for r in records(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)
            if r["event_time"] == t
        ]
        self.assertTrue(obs)
        self.assertLess(max(o["seq"] for o in obs), rep["seq"])

    def test_illegal_crossing_backstop_seam(self) -> None:
        # pure seam: a running task with a_start + d > 240 force-interrupts at
        # age 240 (G3-SPEC-V1.0 section 5 illegal_crossing_fallback).
        out = rd.fragment_outcome(Fraction(230), Fraction(20), None, True)
        self.assertEqual(out.kind, rd.FragmentOutcomeKind.ILLEGAL_240)
        self.assertEqual(out.fragment_duration_h, Fraction(10))
        # a+d == 240 is legal (completion)
        out2 = rd.fragment_outcome(Fraction(230), Fraction(10), None, True)
        self.assertEqual(out2.kind, rd.FragmentOutcomeKind.COMPLETE)
        # failure strictly before end interrupts
        out3 = rd.fragment_outcome(Fraction(10), Fraction(20), Fraction(25), False)
        self.assertEqual(out3.kind, rd.FragmentOutcomeKind.FAILED)
        self.assertEqual(out3.fragment_duration_h, Fraction(15))
        # failure exactly at end -> completion (same-instant completion first)
        out4 = rd.fragment_outcome(Fraction(10), Fraction(20), Fraction(30), False)
        self.assertEqual(out4.kind, rd.FragmentOutcomeKind.COMPLETE)


class TestFcfsOrder(_Base):
    """Required point 7: fixed FCFS preserved (no SPT/LPT/metaheuristic)."""

    def test_per_resource_start_order_is_fcfs(self) -> None:
        res = run(
            make_config(
                batch_size=60, scenario="q2_single_shift", shift_length_h="12",
            )
        )
        starts = records(res.event_log, sm.EventType.ACTIVITY_START.value)
        for resource in ("A", "B", "C", "E"):
            seqs = [
                (r["seq"], r["device_id"], r["effective_attempt_no"])
                for r in starts if r["resource_id"] == resource
            ]
            self.assertGreater(len(seqs), 0, resource)
            # reconstruct the FCFS keys from TASK_RELEASE records
            release = {
                (r["device_id"], r["process"], r["effective_attempt_no"]): Fraction(r["release_time"])
                for r in records(res.event_log, sm.EventType.TASK_RELEASE.value)
                if r["process"] == resource
            }
            keys = [
                (
                    release[(d, resource, a)],
                    d,
                    sm.PROCESS_ORDER[resource],
                    a,
                )
                for (_s, d, a) in seqs
            ]
            self.assertEqual(keys, sorted(keys), f"resource {resource} FCFS order")
        # H1 never lets a later-released task jump the queue: the first start
        # of each resource is its FCFS head at that instant.
        self.assertGreater(len(starts), 0)

    def test_no_duration_based_reordering(self) -> None:
        # A longer task never jumps ahead of a shorter one on the same
        # resource: covered by the FCFS-key monotonicity above; additionally
        # assert the very first A start is device 1 and the second is device 2
        # (release_time 0 ordering by device_id, not by duration).
        res = run(make_config(batch_size=3))
        a_starts = recs_for(res.event_log, sm.EventType.ACTIVITY_START.value, process="A")
        self.assertEqual([s["device_id"] for s in a_starts][:2], [1, 2])


class TestDeterminism(_Base):
    """Required point 8: same seed+config -> byte/canonical identical log."""

    def test_canonical_reproducibility(self) -> None:
        cfg = make_config(
            batch_size=5, scenario="q2_single_shift", shift_length_h="12",
        )
        r1 = run(cfg)
        r2 = run(cfg)
        self.assertEqual(r1.canonical_event_log(), r2.canonical_event_log())
        self.assertEqual(r1.metrics, r2.metrics)
        # run metadata is explicit and outside the canonical log
        r3 = run(cfg, run_metadata={"run_id": "abc", "wall_clock": "x"})
        self.assertEqual(r3.canonical_event_log(), r1.canonical_event_log())
        self.assertEqual(r3.run_metadata["run_id"], "abc")

    def test_config_dict_roundtrip(self) -> None:
        cfg = make_config(batch_size=4)
        cfg2 = rd.RandomDesConfig.from_dict(cfg.to_dict())
        self.assertEqual(
            run(cfg).canonical_event_log(), run(cfg2).canonical_event_log()
        )


class TestNamespaceIsolation(_Base):
    """Required point 9: h1_tuning vs g3_holdout -> different U / logs."""

    def test_namespace_isolation(self) -> None:
        r1 = run(make_config(namespace=ks.NAMESPACE_H1_TUNING))
        r2 = run(make_config(namespace=ks.NAMESPACE_G3_HOLDOUT))
        g1 = records(r1.event_log, rd.EVENT_TRUE_STATE_GENERATED)[0]
        g2 = records(r2.event_log, rd.EVENT_TRUE_STATE_GENERATED)[0]
        self.assertNotEqual(g1["u"], g2["u"])
        self.assertNotEqual(r1.canonical_event_log(), r2.canonical_event_log())
        # each run is internally consistent with ITS namespace
        self.assertEqual(
            g1["u"]["A"],
            str(ks.u_x(ks.NAMESPACE_H1_TUNING, REP, 1, "A", SEED)),
        )
        self.assertEqual(
            g2["u"]["A"],
            str(ks.u_x(ks.NAMESPACE_G3_HOLDOUT, REP, 1, "A", SEED)),
        )


class TestLiveness(_Base):
    """Required point 10: C18 liveness (strict time advance, finite closures,
    no deadlock, defined wake-up path)."""

    CONFIGS = [
        make_config(batch_size=3),
        make_config(batch_size=3, scenario="q2_single_shift", shift_length_h="12"),
        make_config(batch_size=3, scenario="q3_two_shift", shift_length_h="10", shifts_per_day=2),
    ]

    def test_termination_and_monotonicity(self) -> None:
        for cfg in self.CONFIGS:
            res = run(cfg)
            self.assertTrue(
                records(res.event_log, sm.EventType.SIMULATION_END.value),
                f"termination for {cfg.scenario}",
            )
            times = [Fraction(r["event_time"]) for r in res.event_log]
            self.assertTrue(
                all(times[i] <= times[i + 1] for i in range(len(times) - 1)),
                "event times non-decreasing",
            )
            seqs = [r["seq"] for r in res.event_log]
            self.assertTrue(
                all(seqs[i] < seqs[i + 1] for i in range(len(seqs) - 1)),
                "seq strictly increasing (finite same-instant closure)",
            )

    def test_wake_up_on_empty_calendar(self) -> None:
        res = run(
            make_config(batch_size=30, scenario="q2_single_shift", shift_length_h="12")
        )
        wakes = records(res.event_log, sm.EventType.WAKE_UP.value)
        self.assertGreaterEqual(len(wakes), 1)
        # wake-up times land on shift boundaries
        for w in wakes[:5]:
            self.assertIn(Fraction(w["event_time"]) % Fraction(24), (Fraction(0), Fraction(12)))

    def test_deferred_replacement_recovery(self) -> None:
        # Frozen durations, N=100, q2 12h calendar, seed 7: a post-completion
        # 240 replacement for E is due exactly at the shift end t=636, so the
        # calibration cannot start (no-cross-shift, H); the run defers it,
        # wakes at the next shift (648) and completes the calibration there.
        res = run(
            make_config(batch_size=100, master_seed=7,
                        scenario="q2_single_shift", shift_length_h="12")
        )
        deferred = records(res.event_log, rd.EVENT_EQUIPMENT_REPLACEMENT_DEFERRED)
        self.assertGreaterEqual(len(deferred), 1)
        d0 = deferred[0]
        self.assertEqual(d0["reason"], "no_cross_shift")
        self.assertEqual(d0["resource_id"], "E")
        self.assertEqual(d0["trigger"], rd.REPLACEMENT_TRIGGER_POST_COMPLETION_240)
        # 636 is a shift end (12 + 26*24); the next legal shift starts at 648
        self.assertEqual(d0["event_time"], "636")
        self.assertEqual(d0["next_wake"], "648")
        # recovery: E is eventually calibrated in the next shift
        e_cal = [
            r for r in records(res.event_log, rd.EVENT_EQUIPMENT_CALIBRATION_COMPLETE)
            if r["resource_id"] == "E"
        ]
        self.assertGreaterEqual(len(e_cal), 1)
        self.assertGreaterEqual(Fraction(e_cal[-1]["event_time"]), Fraction(648))
        # the deferred replacement consumed no observation randomness: no
        # OBSERVATION_MATERIALIZED between the deferral and the wake
        between = [
            r for r in res.event_log
            if Fraction(r["event_time"]) > Fraction(636)
            and Fraction(r["event_time"]) < Fraction(648)
        ]
        self.assertFalse(
            any(r["event_type"] == sm.EventType.OBSERVATION_MATERIALIZED.value for r in between)
        )
        self.assertTrue(records(res.event_log, sm.EventType.SIMULATION_END.value))


class TestShiftBoundary(_Base):
    """Required point 11: exactly-at-shift-end completion allowed; tasks that
    would cross the boundary are not started (P062)."""

    def test_exact_shift_end_completion_allowed(self) -> None:
        # q2 single shift of 7/2 h, N=1: A and C (5/2 h) start at t=0 and end
        # exactly at the shift end 5/2; E (3 h) would end 11/2 > 7/2 and is
        # blocked in shift 0 (starts at 24).
        res = run(
            make_config(
                batch_size=1, scenario="q2_single_shift", shift_length_h="7/2"
            )
        )
        starts0 = recs_for(res.event_log, sm.EventType.ACTIVITY_START.value, event_time="0")
        self.assertEqual(sorted(r["process"] for r in starts0), ["A", "B", "C"])
        ac = recs_for(res.event_log, sm.EventType.ACTIVITY_COMPLETE.value, process="A")
        self.assertEqual(ac[0]["event_time"], "5/2")  # exactly at shift end
        e_starts = recs_for(res.event_log, sm.EventType.ACTIVITY_START.value, process="E")
        self.assertEqual([r["event_time"] for r in e_starts], ["24"])
        # the E test then completes within shift 1
        self.assertEqual(res.metrics["T"], "27")


class TestLastTerminalStopsClock(_Base):
    """Required point 12: the clock stops at the last device terminal
    (契约 1.1: no transport-out after the last device)."""

    def test_t_equals_last_terminal_time(self) -> None:
        # all-ABNORMAL kernel (degenerate, test-only): deterministic exits with
        # stale cancellation events after the last terminal.
        kernel = {
            p: {"alpha": Fraction(1), "beta": Fraction(0)} for p in ("A", "B", "C", "E")
        }
        res = run(make_config(batch_size=2, kernel=kernel))
        terms = records(res.event_log, sm.EventType.DEVICE_TERMINAL.value)
        self.assertEqual(len(terms), 2)
        last = max(Fraction(r["event_time"]) for r in terms)
        end = records(res.event_log, sm.EventType.SIMULATION_END.value)[0]
        self.assertEqual(Fraction(end["event_time"]), last)
        self.assertEqual(Fraction(res.metrics["T"]), last)
        # no turnover after the last terminal
        after = [
            r for r in res.event_log if Fraction(r["event_time"]) > last
        ]
        self.assertFalse(any("TURNOVER" in r["event_type"] for r in after))
        self.assertEqual(len(records(res.event_log, sm.EventType.D_CREATED.value)), 0)


class TestStructuralMetrics(_Base):
    """Required point 13: small batch S/PL/PW/YXB structural sanity
    (no formal assertions)."""

    def test_structural_sanity(self) -> None:
        res = run(
            make_config(batch_size=60, scenario="q2_single_shift", shift_length_h="12")
        )
        m = res.metrics
        s, pl, pw, exited = m["S"], m["PL"], m["PW"], m["exited"]
        self.assertEqual(s + exited, 60)
        self.assertGreaterEqual(s, 0)
        self.assertGreaterEqual(pl, 0)
        self.assertGreaterEqual(pw, 0)
        self.assertLessEqual(pl, s)
        self.assertLessEqual(pw, exited)
        self.assertGreater(Fraction(m["T"]), Fraction(0))
        self.assertEqual(Fraction(m["T"]), Fraction(m["T_days"]) * Fraction(24))
        for proc in ("A", "B", "C", "E"):
            yxb = Fraction(m[f"YXB_{proc}"])
            self.assertGreaterEqual(yxb, Fraction(0))
            self.assertLessEqual(yxb, Fraction(1))
        for proc in ("A", "B", "C", "E"):
            eq = m["equipment"][proc]
            self.assertGreaterEqual(Fraction(eq["age_h"]), Fraction(0))
            self.assertGreaterEqual(eq["generation"], 1)
            self.assertGreaterEqual(eq["replacement_count"], 0)
            self.assertGreaterEqual(eq["preventive_replacement_count"], 0)
            self.assertGreaterEqual(eq["failure_count"], 0)
        self.assertTrue(records(res.event_log, sm.EventType.SIMULATION_END.value))
        # stream counts are consistent with the log
        self.assertEqual(
            res.summary["u_consumption_counts"]["u_x"], 3 * 60
        )
        self.assertEqual(
            res.summary["u_consumption_counts"]["u_d"],
            len(records(res.event_log, sm.EventType.D_CREATED.value)),
        )
        self.assertEqual(
            res.summary["u_consumption_counts"]["u_y"],
            len(records(res.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)),
        )
        self.assertEqual(
            res.summary["u_consumption_counts"]["u_l"],
            4 + sum(
                m["equipment"][proc]["replacement_count"] for proc in ("A", "B", "C", "E")
            ),
        )


class TestC24Instruments(_Base):
    """Required point 14: C24 instrument fields exist and satisfy the
    documented invariants (H2 is NOT implemented)."""

    def test_c24_fields_and_invariants(self) -> None:
        res = run(
            make_config(batch_size=60, tau_pm=Fraction(120),
                        scenario="q2_single_shift", shift_length_h="12")
        )
        c24 = res.metrics["c24"]
        for key in (
            "decision_point_count",
            "legal_action_count",
            "waiting_opportunity_count",
            "preventive_replacement_opportunity_count",
            "decision_point_density",
            "estimated_rollout_branching_burden",
        ):
            self.assertIn(key, c24)
        dp = c24["decision_point_count"]
        legal = c24["legal_action_count"]
        waiting = c24["waiting_opportunity_count"]
        opp = c24["preventive_replacement_opportunity_count"]
        self.assertEqual(dp, legal + waiting)
        self.assertLessEqual(opp, dp)
        self.assertGreaterEqual(dp, 1)
        # density = count / T (per calendar hour)
        self.assertEqual(
            Fraction(c24["decision_point_density"]),
            Fraction(dp) / Fraction(res.metrics["T"]),
        )
        self.assertEqual(
            c24["estimated_rollout_branching_burden"], dp + opp
        )
        # h2 not implemented anywhere in the module
        self.assertFalse(records(res.event_log, "H2"))

    def test_c24_invariants_no_pm(self) -> None:
        res = run(
            make_config(batch_size=30, scenario="q2_single_shift", shift_length_h="12")
        )
        c24 = res.metrics["c24"]
        self.assertEqual(
            c24["decision_point_count"],
            c24["legal_action_count"] + c24["waiting_opportunity_count"],
        )
        self.assertEqual(
            c24["estimated_rollout_branching_burden"],
            c24["decision_point_count"] + c24["preventive_replacement_opportunity_count"],
        )


class TestQ3Interface(_Base):
    """C15 interface: q3_two_shift calendar with K in the frozen set; fresh
    per-run world (no Q2 state leak); CRN key alignment across K."""

    def test_q3_two_shift_calendar(self) -> None:
        # N=4 forces the batch past the second shift for every frozen K.
        for k_str in ("9", "19/2", "10", "12"):
            res = run(
                make_config(
                    batch_size=4, scenario="q3_two_shift",
                    shift_length_h=k_str, shifts_per_day=2,
                )
            )
            self.assertTrue(records(res.event_log, sm.EventType.SIMULATION_END.value))
            k = Fraction(k_str)
            shifts = records(res.event_log, sm.EventType.SHIFT_CHANGE.value)
            self.assertGreaterEqual(len(shifts), 2)
            # first day: shifts [0,K) and [K,2K)
            self.assertEqual(Fraction(shifts[0]["shift_start"]), Fraction(0))
            self.assertEqual(Fraction(shifts[0]["shift_end"]), k)
            self.assertEqual(Fraction(shifts[1]["shift_start"]), k)
            self.assertEqual(Fraction(shifts[1]["shift_end"]), 2 * k)

    def test_q3_full_batch_completion_all_k_batches_seeds(self) -> None:
        """Regression for the oracle-detected premature-stop defect (checker
        ``g3_quality_oracle_v1.test_q3_premature_stop_detected``): with the
        q3_two_shift calendar and K <= 10, batch >= 4, the DES used to stop
        after 3 devices -- ``_is_terminal`` treated in-flight turnovers
        (OCCUPIED_TRANSPORT_OUT/IN) as no work, so devices 4..N were never
        created (SIMULATION_END with a non-empty calendar; CR-V3.1/C18
        liveness violation). Fixed by counting in-flight turnovers as
        unfinished work and by the bay slot accounting (a second turnover is
        never started when only one next device remains -- no empty
        transport-in, C12). Every frozen K x batch 2..6 x seed must run the
        FULL batch (设备数 == batch_size) with T == the last DEVICE_TERMINAL
        time and no turnover after the last terminal (末台终态停止计时).
        The oracle-side test now skips via its own condition (created ==
        batch_size -> 'DES no longer reproduces the premature stop'); this
        positive assertion is the replacement evidence."""
        for k_str in ("9", "9.5", "10", "10.5", "11", "11.5", "12"):
            for batch in range(2, 7):
                for seed in (1, 7, 13):
                    res = run(
                        make_config(
                            batch_size=batch, master_seed=seed,
                            scenario="q3_two_shift",
                            shift_length_h=k_str, shifts_per_day=2,
                        )
                    )
                    log = res.event_log
                    created = len(records(log, rd.EVENT_TRUE_STATE_GENERATED))
                    self.assertEqual(
                        created, batch,
                        "K=%s batch=%d seed=%d: full batch must be created"
                        % (k_str, batch, seed),
                    )
                    terms = [
                        Fraction(r["event_time"])
                        for r in records(log, sm.EventType.DEVICE_TERMINAL.value)
                    ]
                    self.assertEqual(len(terms), batch)
                    ends = records(log, sm.EventType.SIMULATION_END.value)
                    self.assertEqual(len(ends), 1)
                    last_term = max(terms)
                    # 末台终态停止计时: SIMULATION_END / T == last terminal
                    self.assertEqual(Fraction(ends[0]["event_time"]), last_term)
                    self.assertEqual(Fraction(res.metrics["T"]), last_term)
                    # 末台不运出: no turnover of any kind after the last terminal
                    after = [r for r in log if Fraction(r["event_time"]) > last_term]
                    self.assertFalse(
                        any("TURNOVER" in r["event_type"] for r in after),
                        "turnover after last terminal K=%s batch=%d seed=%d"
                        % (k_str, batch, seed),
                    )
                    self.assertEqual(res.metrics["S"] + res.metrics["exited"], batch)

    def test_q3_racing_bays_single_slot_remains(self) -> None:
        """Two bays can hold terminal devices simultaneously while only one
        next device remains (e.g. devices 1 and 2 exit in the same closure
        with batch=4). The engine must start only one of the two turnovers --
        the extra bay stops (TERMINAL_OCCUPIED_UNTIL_STOP) instead of
        performing an empty transport-in. seed 7, batch 4, K=9 previously
        raised 'turnover_in without a next device' once the in-flight-
        turnover termination fix let the run continue."""
        for batch in (3, 4):
            res = run(
                make_config(
                    batch_size=batch, master_seed=7,
                    scenario="q3_two_shift",
                    shift_length_h="9", shifts_per_day=2,
                )
            )
            created = len(records(res.event_log, rd.EVENT_TRUE_STATE_GENERATED))
            self.assertEqual(created, batch, "batch=%d must be created fully" % batch)
            self.assertTrue(records(res.event_log, sm.EventType.SIMULATION_END.value))

    def test_q3_fresh_world_and_crn_across_k(self) -> None:
        # same seed, K=9 vs K=12: independent fresh worlds sharing the keyed U
        r9 = run(make_config(batch_size=3, scenario="q3_two_shift", shift_length_h="9", shifts_per_day=2))
        r12 = run(make_config(batch_size=3, scenario="q3_two_shift", shift_length_h="12", shifts_per_day=2))
        # shared completed (device, process, attempt) observations agree
        u9 = {
            (r["device_id"], r["process"], r["effective_attempt_no"]): r["u"]
            for r in records(r9.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)
        }
        u12 = {
            (r["device_id"], r["process"], r["effective_attempt_no"]): r["u"]
            for r in records(r12.event_log, sm.EventType.OBSERVATION_MATERIALIZED.value)
        }
        shared = set(u9) & set(u12)
        self.assertGreater(len(shared), 0)
        for key in shared:
            self.assertEqual(u9[key], u12[key])


class TestValidation(_Base):
    """Config/kernel/float validation, SEM-21 preload rule, parameters.csv
    audit, no binary float / no runtime hash in canonical paths."""

    def test_preload_rule(self) -> None:
        cfg = make_config(batch_size=1)
        self.assertEqual(cfg.preloaded_devices, (1,))
        cfg2 = make_config(batch_size=2)
        self.assertEqual(cfg2.preloaded_devices, (1, 2))
        raw = cfg.to_dict()
        raw["deterministic_initial_state"]["preloaded_devices"] = [1]
        raw["batch_size"] = 2
        with self.assertRaises(rd.RandomDesPreloadRuleError):
            rd.RandomDesConfig.from_dict(raw)

    def test_bad_namespace_and_h2_rejected(self) -> None:
        raw = make_config(batch_size=2).to_dict()
        raw["namespace"] = ks.H2_RESERVED_NAMESPACE
        with self.assertRaises(rd.RandomDesConfigError):
            rd.RandomDesConfig.from_dict(raw)
        raw["namespace"] = "not_a_namespace"
        with self.assertRaises(rd.RandomDesConfigError):
            rd.RandomDesConfig.from_dict(raw)

    def test_tau_pm_validation(self) -> None:
        raw = make_config(batch_size=2).to_dict()
        raw["tau_pm"] = "240"
        with self.assertRaises(rd.RandomDesConfigError):  # 240 is mandatory, not preventive
            rd.RandomDesConfig.from_dict(raw)
        raw["tau_pm"] = "100"
        with self.assertRaises(rd.RandomDesConfigError):  # below 120
            rd.RandomDesConfig.from_dict(raw)
        raw["tau_pm"] = "NO_PM_BEFORE_MANDATORY"
        self.assertEqual(
            rd.RandomDesConfig.from_dict(raw).tau_pm, lr.NO_PM_BEFORE_MANDATORY
        )

    def test_kernel_validation(self) -> None:
        raw = make_config(batch_size=2).to_dict()
        raw["observation_kernel"]["E"] = {"alpha": "1/2"}  # missing beta
        with self.assertRaises(rd.RandomDesConfigError):
            rd.RandomDesConfig.from_dict(raw)
        raw["observation_kernel"] = {
            "A": {"alpha": "1/2", "beta": "1/2"},
            "B": {"alpha": "1/2", "beta": "1/2"},
            "C": {"alpha": "1/2", "beta": "1/2"},
        }  # missing E
        with self.assertRaises(rd.RandomDesConfigError):
            rd.RandomDesConfig.from_dict(raw)

    def test_binary_float_rejected(self) -> None:
        with self.assertRaises(TypeError):
            rd.observation_outcome(False, Fraction(1, 2), 0.5, Fraction(1, 2))
        with self.assertRaises(TypeError):
            rd.fragment_outcome(0.5, Fraction(1), None, True)
        with self.assertRaises(TypeError):
            rd.frozen_single_test_alpha_beta(Fraction(1, 40), 0.03)

    def test_parameters_csv_audit(self) -> None:
        verified = rd.validate_parameters_csv(PARAMS_CSV)
        self.assertEqual(verified["P006"], rd.DEFAULT_DURATIONS_H["A"])
        self.assertEqual(verified["P029"], rd.DEFECT_PROB_D)

    def test_no_float_literal_in_module(self) -> None:
        tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                self.fail(f"binary float literal in canonical module: {node.value!r}")

    def test_no_runtime_hash_or_order_rng(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("hash(", source)
        self.assertNotIn("import random", source)
        self.assertNotIn("random.", source)


if __name__ == "__main__":
    unittest.main()
