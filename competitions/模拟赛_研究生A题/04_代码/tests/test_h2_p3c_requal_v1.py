#!/usr/bin/env python3
"""Q3-H2-P3 requalification tests (decision-semantics repair, P3-B/P3-C):

ACT-01..07   candidate FIRST ACTION really takes effect on the FROZEN
             decision context (START_HEAD at t / fail-closed head mismatch /
             WAIT_EVENT hold until the anchor / PM_WITH_HEAD / PM_IDLE /
             H1_NOOP no optional PM / H1 baseline after the first step);
             section-8 path differentiation (START_HEAD vs WAIT_EVENT,
             PM candidate vs H1 baseline);
DPKEY-01..05 per-batch EVALUATED dp semantics (SPEC 6.2): 0-based index of
             the points the frozen online quota actually evaluates;
QUOTA-DP-01..03 quota simulation matches the frozen selector, caps hold,
             age comes from the pre-action decision-boundary state;
SAMPLE-01..03 frozen B-1 top-up arithmetic.

Frozen domain: K = 21/2, two-shift calendar, h2_tuning master_seed 6.
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

from main_model.h2 import decision_point_v1 as dp  # noqa: E402
from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as ps  # noqa: E402
from main_model.h2 import continuation_v1 as cont  # noqa: E402
from main_model.h2 import quota_selector_v1 as qsel  # noqa: E402
from main_model.h2_rollout import rollout_engine_v1 as re1  # noqa: E402
from main_model.h2_rollout import post_keys_v1 as pk  # noqa: E402
from main_model.h2_rollout import h2_batch_runner_v1 as br  # noqa: E402
from scripts.run_h2_p3c_stability_v1 import (  # noqa: E402
    quota_simulate_batch, build_b1_sample, evaluate_sample,
    collect_eligible_points, _b1_take, K as P3C_K, MASTER_SEED, NS,
    WAIT_CAP, PM_CAP, SAMPLE_CAP)

K = Fraction(21, 2)
BATCH = 6


def _log(*records: dict) -> list[dict]:
    base = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
    ]
    return base + list(records)


def _release(device: int, process: str, att: int, at: str) -> dict:
    return {"event_type": "TASK_RELEASE", "event_time": at,
            "device_id": device, "process": process,
            "effective_attempt_no": att, "resource_id": process,
            "release_time": at}


def _complete(device: int, process: str, att: int, s: str, e: str) -> dict:
    return {"event_type": "ACTIVITY_COMPLETE", "event_time": e,
            "device_id": device, "process": process,
            "effective_attempt_no": att, "resource_id": process,
            "attempt_start_time": s, "attempt_end_time": e, "outcome": "PASS"}


def _start(device: int, process: str, att: int, s: str, e: str) -> dict:
    return {"event_type": "ACTIVITY_START", "event_time": s,
            "device_id": device, "process": process,
            "effective_attempt_no": att, "resource_id": process,
            "attempt_start_time": s, "attempt_end_time": e, "outcome": "NONE"}


def _toy_context(log: list[dict], t: Fraction, rep: int = 0):
    """(state, posterior, world, provider, cfg) at the PRE-ACTION boundary
    of closure t; log_prefix = the pre-action log view."""
    st = dp.project_pre_action_state(log, t, batch_size=BATCH)
    post = ps.PosteriorState.from_observable(st)
    prov = pk.physical_post_provider(NS, MASTER_SEED, rep, BATCH,
                                     ("A", "B", "C", "E"))
    ux = {d.device_id: prov.u_x(d.device_id) for d in st.devices}
    ud = {d.device_id: prov.u_d(d.device_id) for d in st.devices}
    ul = {r: prov.u_l(r, 1) for r in ("A", "B", "C", "E")}
    world = cont.rebuild_continuation_world(st, post, ux, ud, ul)
    cfg = re1.RolloutConfig(batch_size=BATCH, shift_length_h=K,
                            shifts_per_day=2, scenario="q3_two_shift",
                            tau_pm=re1.NO_PM_BEFORE_MANDATORY)
    return st, post, world, prov, cfg, dp.pre_action_log(log, t)


def _run_first_action(log: list[dict], t: Fraction, action: str,
                      resource: str, head, *, wait_anchor=None,
                      pm_resource=None) -> re1.RolloutResult:
    st, post, world, prov, cfg, pre_log = _toy_context(log, t)
    eng = re1.RolloutEngine(
        st, post, world, prov, cfg,
        first_action=action, wait_anchor_time=wait_anchor,
        pm_resource=pm_resource, log_prefix=pre_log,
        decision_resource=resource, decision_head=head,
        decision_kind="dispatch")
    return eng.run()


def _find(log, event_type: str, **kw):
    return [r for r in log if r.get("event_type") == event_type
            and all(r.get(k) == v for k, v in kw.items())]


# ---------------------------------------------------------------------------
# ACT-01..07: candidate first action strictly takes effect
# ---------------------------------------------------------------------------


class TestFirstActionSemantics(unittest.TestCase):
    """ACT-01..07: the candidate action must really act on the FROZEN
    decision context (never a silent no-op)."""

    def _start_head_log(self):
        # t=1: resource A idle, FCFS head (1, A, 1) released at 1
        return _log(_release(1, "A", 1, "1"), _release(2, "B", 1, "4"))

    def test_act_01_start_head_records_activity_start_at_t(self):
        log = self._start_head_log()
        out = _run_first_action(log, Fraction(1), re1.A_START_HEAD,
                                "A", (1, "A", 1))
        hits = _find(out.events, "ACTIVITY_START", device_id=1,
                     process="A", effective_attempt_no=1, event_time="1")
        self.assertEqual(len(hits), 1,
                         "START_HEAD must record ACTIVITY_START of the "
                         "frozen head at the decision time t")

    def test_act_01b_head_mismatch_fails_closed(self):
        log = self._start_head_log()
        with self.assertRaises(ValueError):
            _run_first_action(log, Fraction(1), re1.A_START_HEAD,
                              "A", (2, "B", 1))  # not the queue head

    def test_act_01c_missing_context_fails_closed(self):
        st, post, world, prov, cfg, pre_log = _toy_context(
            self._start_head_log(), Fraction(1))
        with self.assertRaises(ValueError):
            re1.RolloutEngine(
                st, post, world, prov, cfg, first_action=re1.A_START_HEAD,
                log_prefix=pre_log, decision_resource=None,
                decision_head=None, decision_kind="dispatch")

    def _wait_log(self):
        # t=2: resource B idle, head (1, B, 1); device1's A fragment runs
        # until 5 -> STRICT wait anchor at 5 (2 < 5 < 10.5-2)
        return _log(
            _start(1, "A", 1, "1", "5"),
            _release(1, "B", 1, "2"),
            _release(2, "C", 1, "6"),
        )

    def test_act_02_wait_event_holds_dispatch_until_anchor(self):
        log = self._wait_log()
        out = _run_first_action(log, Fraction(2), re1.A_WAIT_EVENT,
                                "B", (1, "B", 1), wait_anchor=Fraction(5))
        starts = _find(out.events, "ACTIVITY_START", process="B")
        self.assertGreaterEqual(len(starts), 1)
        first = min(Fraction(r["event_time"]) for r in starts)
        self.assertEqual(first, Fraction(5),
                         "WAIT_EVENT must hold B's dispatch until the "
                         "anchor (no B ACTIVITY_START in [t, anchor))")

    def test_act_03b_hold_released_at_anchor_h1_resumes(self):
        # same run as ACT-02: after the anchor the H1 baseline dispatches
        log = self._wait_log()
        out = _run_first_action(log, Fraction(2), re1.A_WAIT_EVENT,
                                "B", (1, "B", 1), wait_anchor=Fraction(5))
        # A's fragment completes at 5 and the FROZEN head (1,B,1) starts
        # at 5 (H1 resume after the hold release)
        self.assertEqual(
            len(_find(out.events, "ACTIVITY_COMPLETE", process="A",
                      device_id=1)), 1)
        starts_b = _find(out.events, "ACTIVITY_START", process="B",
                         device_id=1, effective_attempt_no=1)
        self.assertEqual(len(starts_b), 1)
        self.assertEqual(starts_b[0]["event_time"], "5")

    def test_act_03_start_head_vs_wait_event_paths_differ(self):
        """§8 path differentiation: the two legal candidates must lead to
        different event paths on the same decision point."""
        log = self._wait_log()
        out_sh = _run_first_action(log, Fraction(2), re1.A_START_HEAD,
                                   "B", (1, "B", 1))
        out_w = _run_first_action(log, Fraction(2), re1.A_WAIT_EVENT,
                                  "B", (1, "B", 1), wait_anchor=Fraction(5))
        b_sh = _find(out_sh.events, "ACTIVITY_START", process="B")
        b_w = _find(out_w.events, "ACTIVITY_START", process="B")
        self.assertEqual(b_sh[0]["event_time"], "2")
        self.assertEqual(b_w[0]["event_time"], "5")
        self.assertNotEqual(b_sh[0]["event_time"], b_w[0]["event_time"])
        # the continuation paths differ (not only the start time)
        self.assertNotEqual(
            [r for r in out_sh.events if r["event_type"] in
             ("ACTIVITY_START", "ACTIVITY_COMPLETE")],
            [r for r in out_w.events if r["event_type"] in
             ("ACTIVITY_START", "ACTIVITY_COMPLETE")])

    def test_act_04_pm_with_head_replaces_then_serves_head(self):
        log = self._start_head_log()
        out = _run_first_action(log, Fraction(1), re1.A_PM_WITH_HEAD,
                                "A", (1, "A", 1), pm_resource="A")
        repls = _find(out.events, "EQUIPMENT_REPLACEMENT_START",
                      resource_id="A")
        self.assertEqual(len(repls), 1,
                         "PM_WITH_HEAD must begin the preventive replacement")
        self.assertEqual(repls[0]["kind"], "preventive")
        # the head is served only AFTER the replacement calibration
        a_starts = _find(out.events, "ACTIVITY_START", process="A",
                         device_id=1)
        self.assertEqual(len(a_starts), 1)
        self.assertGreaterEqual(Fraction(a_starts[0]["event_time"]),
                                Fraction(repls[0]["calibration_end"]))

    def test_act_05_pm_idle_replaces(self):
        log = self._start_head_log()
        out = _run_first_action(log, Fraction(1), re1.A_PM_IDLE,
                                "A", (1, "A", 1), pm_resource="A")
        repls = _find(out.events, "EQUIPMENT_REPLACEMENT_START",
                      resource_id="A")
        self.assertEqual(len(repls), 1)

    def test_act_06_h1_noop_no_optional_pm(self):
        log = self._start_head_log()
        out = _run_first_action(log, Fraction(1), re1.A_H1_NOOP,
                                "A", (1, "A", 1))
        repls = _find(out.events, "EQUIPMENT_REPLACEMENT_START",
                      resource_id="A")
        self.assertEqual(repls, [],
                         "H1_NOOP must not trigger an optional PM")
        # H1 serves the head directly
        self.assertEqual(
            len(_find(out.events, "ACTIVITY_START", process="A",
                      device_id=1, event_time="1")), 1)

    def test_act_07_h1_baseline_after_first_step(self):
        # after the first action the engine follows the H1 baseline: the
        # device-1 B task (auto-released by the H1 rules) is later served
        # without any further candidate injection
        log = self._start_head_log()
        out = _run_first_action(log, Fraction(1), re1.A_START_HEAD,
                                "A", (1, "A", 1))
        b_starts = _find(out.events, "ACTIVITY_START", process="B",
                         device_id=1)
        self.assertGreaterEqual(len(b_starts), 1,
                                "H1 baseline must continue serving after "
                                "the first action")

    def test_act_08_pm_path_differs_from_h1_baseline(self):
        """§8 path differentiation: the PM candidate continuation must
        differ from the H1 baseline continuation on the same point."""
        log = self._start_head_log()
        out_pm = _run_first_action(log, Fraction(1), re1.A_PM_IDLE,
                                   "A", (1, "A", 1), pm_resource="A")
        out_h1 = _run_first_action(log, Fraction(1), re1.A_H1_NOOP,
                                   "A", (1, "A", 1))
        core = lambda o: [r for r in o.events  # noqa: E731
                          if r["event_type"] in
                          ("EQUIPMENT_REPLACEMENT_START", "ACTIVITY_START")]
        self.assertNotEqual(core(out_pm), core(out_h1))
        self.assertEqual(len(_find(out_pm.events,
                                   "EQUIPMENT_REPLACEMENT_START")), 1)
        self.assertEqual(len(_find(out_h1.events,
                                   "EQUIPMENT_REPLACEMENT_START")), 0)


# ---------------------------------------------------------------------------
# DPKEY: per-batch evaluated dp (SPEC 6.2)
# ---------------------------------------------------------------------------


def _gen_batch(rep: int, batch_size: int = BATCH) -> list[dict]:
    """One small h2_tuning physical batch under the H1 baseline."""
    log0 = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 2, "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "300", "on_duty_squad": 0,
         "squad_id": 0},
    ]
    st = obs.project_log_prefix(log0, Fraction(0), batch_size=batch_size)
    post = ps.PosteriorState.from_observable(st)
    prov = pk.physical_post_provider(NS, MASTER_SEED, rep, batch_size,
                                     ("A", "B", "C", "E"))
    ux = {d.device_id: prov.u_x(d.device_id) for d in st.devices}
    ud = {d.device_id: prov.u_d(d.device_id) for d in st.devices}
    ul = {r: prov.u_l(r, 1) for r in ("A", "B", "C", "E")}
    world = cont.rebuild_continuation_world(st, post, ux, ud, ul)
    cfg = re1.RolloutConfig(batch_size=batch_size, shift_length_h=K,
                            shifts_per_day=2, scenario="q3_two_shift",
                            tau_pm=re1.NO_PM_BEFORE_MANDATORY)
    eng = br.H2BatchRunner(st, post, world, prov, cfg, None,
                           MASTER_SEED, rep, policy_enabled=False)
    return eng.run().events


def _synthetic_wait_log() -> list[dict]:
    """Deterministic synthetic log with 9 WAIT-eligible decision points
    (resource IDLE at the point time; STRICT/BOUNDARY anchors on a
    same-device in-flight fragment; complete fragment histories so the
    queue heads advance; E never eligible: E requires A/B/C PASSED while
    its anchor needs an in-flight fragment -> frozen semantics):
      t=1:    B(dev1, anchor dev1-A@2)
      t=3:    C(dev1, anchor dev1-B@4)
      t=5:    B(dev2, anchor dev2-A@6)
      t=7:    C(dev2, anchor dev2-B@8  BOUNDARY)
      t=11:   B(dev3, anchor dev3-A@12)
      t=23/2: B(dev3, anchor dev3-A@12)
      t=15:   B(dev5, anchor dev5-A@16)
      t=17:   C(dev6, anchor dev6-B@18)
      t=24:   B(dev8, anchor dev8-A@26, shift-start closure)
    Resource fragments are serial per resource (A: 1,2,3,5,8; B: 1,2,3,6;
    C: 1,2,6).  All heads legal in their shift (t+DUR <= shift end)."""
    recs = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": d,
         "true_state": {"A": False, "B": False, "C": False}}
        for d in range(1, 12)
    ]
    recs.append({"event_type": "SHIFT_CHANGE", "event_time": "0",
                 "shift_index": 0, "shift_start": "0", "shift_end": "300",
                 "on_duty_squad": 0, "squad_id": 0})
    # fragments with completions: (device, process, start, end)
    frags = (
        (1, "A", "0", "2"), (2, "A", "4", "6"), (3, "A", "10", "12"),
        (5, "A", "14", "16"), (8, "A", "20", "25"),
        (1, "B", "2", "4"), (2, "B", "6", "8"), (3, "B", "13", "15"),
        (6, "B", "16", "18"), (5, "B", "18", "20"),
        (1, "C", "4", "13/2"), (2, "C", "9", "23/2"), (6, "C", "18", "41/2"),
    )
    for d, p, s, e in frags:
        recs.append(_start(d, p, 1, s, e))
        recs.append(_complete(d, p, 1, s, e))
    # waiting heads
    for d, p, at in ((1, "B", "1"), (1, "C", "3"), (2, "B", "5"),
                     (2, "C", "7"), (3, "B", "11"), (5, "B", "15"),
                     (6, "C", "17"), (8, "B", "24")):
        recs.append(_release(d, p, 1, at))
    return recs


class TestDPKeySemantics(unittest.TestCase):
    """DPKEY-01..05: dp = per-batch 0-based index of QUOTA-EVALUATED
    points; shared across normal/ALT/M=16 evaluations of the same point."""

    @classmethod
    def setUpClass(cls):
        cls.logs = [_gen_batch(0), _gen_batch(1)]
        cls.sample = build_b1_sample(cls.logs, P3C_K, BATCH)

    def test_dpkey_01_per_batch_evaluated_index_0based_contiguous(self):
        by_batch: dict[int, list[int]] = {}
        for p in self.sample["points"]:
            by_batch.setdefault(p["batch"], []).append(p["dp"])
        for bi, dps in by_batch.items():
            self.assertEqual(dps, list(range(len(dps))),
                             f"batch {bi}: evaluated dps must be 0-based "
                             f"contiguous per batch")

    def test_dpkey_02_batches_number_independently(self):
        by_batch: dict[int, list[int]] = {}
        for p in self.sample["points"]:
            by_batch.setdefault(p["batch"], []).append(p["dp"])
        self.assertEqual(set(by_batch), {0, 1})
        for bi, dps in by_batch.items():
            self.assertEqual(dps[0], 0, f"batch {bi} starts at dp=0")

    def test_dpkey_03_sample_dp_matches_quota_simulation(self):
        for bi, blog in enumerate(self.logs):
            evals = quota_simulate_batch(blog, P3C_K, BATCH)
            evals_by_key = {(str(p["time"]), p["resource"]): p["dp"]
                            for p in evals}
            for p in self.sample["points"]:
                if p["batch"] != bi:
                    continue
                self.assertEqual(
                    p["dp"], evals_by_key[(str(p["time"]), p["resource"])],
                    f"sample dp must equal the quota-evaluated dp "
                    f"(batch {bi} {p['time']} {p['resource']})")

    def test_dpkey_04_normal_alt_share_batch_dp(self):
        ev_n = evaluate_sample(self.sample, self.logs,
                               "q3h2-bootstrap-v1", 2, BATCH)
        ev_a = evaluate_sample(self.sample, self.logs,
                               "q3h2-bootstrap-alt-v1", 2, BATCH)
        keys_n = [(r["point"]["batch"], r["point"]["dp"])
                  for r in ev_n["rows"]]
        keys_a = [(r["point"]["batch"], r["point"]["dp"])
                  for r in ev_a["rows"]]
        self.assertEqual(keys_n, keys_a)
        self.assertEqual(len(set(keys_n)), len(keys_n),
                         "(batch, dp) must be unique across the sample")

    def test_dpkey_05_evaluated_dp_is_not_candidate_dp_when_quota_rejects(self):
        # synthetic log with 9 wait-eligible points (3 closures x 3
        # resources, all STRICT anchors): C_eval=8 must reject >=1 candidate
        # and the evaluated dp sequence re-numbers the SELECTED points
        # 0..k-1 (per-batch evaluated index, SPEC 6.2)
        blog = _synthetic_wait_log()
        cands = collect_eligible_points(blog, P3C_K, 12)
        evals = quota_simulate_batch(blog, P3C_K, 12)
        self.assertGreater(len(cands), 8,
                           "fixture must exceed C_eval=8 eligible points")
        self.assertLess(len(evals), len(cands),
                        "quota must reject at least one candidate")
        self.assertEqual([p["dp"] for p in evals],
                         list(range(len(evals))))
        self.assertLessEqual(len(evals), 8)


class TestQuotaDP(unittest.TestCase):
    """QUOTA-DP-01..03: offline quota simulation == frozen online selector."""

    @classmethod
    def setUpClass(cls):
        cls.logs = [_gen_batch(0), _gen_batch(1)]
        cls.sample = build_b1_sample(cls.logs, P3C_K, BATCH)

    def _events_for_batch(self, blog):
        events = []
        for i, p in enumerate(collect_eligible_points(blog, P3C_K, BATCH)):
            st = dp.project_pre_action_state(blog, p["time"],
                                             batch_size=BATCH)
            rsrc = next(r for r in st.resources
                        if r.resource == p["resource"])
            events.append(qsel.DecisionPointEvent(
                dp=i, time=p["time"], resource=p["resource"],
                kind=p["kind"], wait_legal=p["wait_legal"],
                pm_legal=p["pm_legal"], age_h=rsrc.age_h, head=p["head"]))
        return events

    def test_quota_dp_01_selection_matches_online_selector(self):
        for blog in self.logs:
            sim = quota_simulate_batch(blog, P3C_K, BATCH)
            ref = qsel.run_online_selection(8, self._events_for_batch(blog))
            sel_ref = {(str(r["time"]), r["resource"])
                       for r in ref["rows"] if r["selected_for_rollout"]}
            sel_sim = {(str(p["time"]), p["resource"]) for p in sim}
            self.assertEqual(sel_sim, sel_ref)
            self.assertEqual(qsel.check_invariants(ref), [])

    def test_quota_dp_02_caps_hold_per_batch(self):
        for bi, blog in enumerate(self.logs):
            evals = quota_simulate_batch(blog, P3C_K, BATCH)
            n_w = sum(1 for p in evals if p["quota_class"] == "WAIT")
            n_p = sum(1 for p in evals if p["quota_class"] == "PM")
            self.assertLessEqual(n_w, 4, f"batch {bi} W_cap")
            self.assertLessEqual(n_p, 4, f"batch {bi} P_cap")
            self.assertLessEqual(len(evals), 8, f"batch {bi} C_eval")

    def test_quota_dp_03_age_from_pre_action_state(self):
        for blog in self.logs:
            for p in quota_simulate_batch(blog, P3C_K, BATCH):
                st = dp.project_pre_action_state(blog, p["time"],
                                                 batch_size=BATCH)
                rsrc = next(r for r in st.resources
                            if r.resource == p["resource"])
                self.assertEqual(p["age_h"], rsrc.age_h)


class TestInFlightTestingRebuild(unittest.TestCase):
    """INFLIGHT-01..03 (P3-C rerun fix): a rebuild from a decision-boundary
    state with an in-flight TESTING resource must bind the fragment (task
    + attempt + scheduled outcome event, mirror of the calibration FIX);
    otherwise the calendar empties and run() runaway-guards."""

    def _engine_at_t1(self):
        # t=1: resource A testing (fragment dev1-A [0,2]), resource B idle
        # with FCFS head (1,B,1)
        log = _log(_start(1, "A", 1, "0", "2"), _release(1, "B", 1, "1"))
        st, post, world, prov, cfg, pre_log = _toy_context(log, Fraction(1))
        rsrc_a = next(r for r in st.resources if r.resource == "A")
        self.assertEqual(rsrc_a.status, "testing")
        self.assertGreater(rsrc_a.in_flight_remaining_h, 0)
        eng = re1.RolloutEngine(st, post, world, prov, cfg,
                                first_action=re1.A_H1_NOOP,
                                log_prefix=pre_log)
        return eng

    def test_inflight_01_fragment_rebuilt_and_completes(self):
        eng = self._engine_at_t1()
        out = eng.run()  # must terminate (no runaway)
        self.assertGreater(out.t_end, 0)
        self.assertLess(out.t_end, Fraction(240) * 2)
        comps = _find(out.events, "ACTIVITY_COMPLETE", process="A",
                      device_id=1)
        self.assertEqual(len(comps), 1,
                         "the rebuilt in-flight fragment must complete")

    def test_inflight_03_queue_resumes_after_completion(self):
        eng = self._engine_at_t1()
        out = eng.run()
        # resource B is idle: the H1 baseline serves the B head at the
        # decision time (parallel to the in-flight A fragment)
        b_starts = _find(out.events, "ACTIVITY_START", process="B",
                         device_id=1)
        self.assertGreaterEqual(len(b_starts), 1)
        self.assertEqual(b_starts[0]["event_time"], "1")


class TestReleaseGuardRebuild(unittest.TestCase):
    """RELEASE-GUARD-01..02 (P3-C rerun fix): an offline rebuild must not
    re-release an attempt that was ALREADY TESTED (completed tasks are not
    in the rebuilt self.tasks, so the tid guard alone cannot see them); a
    re-released attempt would sit at the FCFS head forever and starve the
    queue (runaway)."""

    def _abnormal_retest_log(self):
        # dev1: A att1 completed ABNORMAL at 2; A att2 queued at 2
        return _log(
            _start(1, "A", 1, "0", "2"),
            _complete(1, "A", 1, "0", "2"),
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "2",
             "device_id": 1, "process": "A", "effective_attempt_no": 1,
             "resource_id": "A", "outcome": "ABNORMAL"},
            _release(1, "A", 2, "2"),
            _release(2, "B", 1, "3"),
        )

    def test_release_guard_01_no_rerelease_of_tested_attempt(self):
        log = self._abnormal_retest_log()
        st, post, world, prov, cfg, pre_log = _toy_context(
            log, Fraction(2), rep=1)
        eng = re1.RolloutEngine(st, post, world, prov, cfg,
                                first_action=re1.A_H1_NOOP,
                                log_prefix=pre_log)
        eng._release_tasks()
        a_entries = [e for e in eng.queues["A"]
                     if eng.tasks[e.task_id].device_id == 1]
        self.assertEqual(len(a_entries), 1,
                         "the tested A att1 must NOT be re-released")
        self.assertEqual(eng.tasks[a_entries[0].task_id].effective_attempt_no,
                         2)

    def test_release_guard_02_rebuild_terminates(self):
        log = self._abnormal_retest_log()
        st, post, world, prov, cfg, pre_log = _toy_context(
            log, Fraction(2), rep=1)
        eng = re1.RolloutEngine(st, post, world, prov, cfg,
                                first_action=re1.A_H1_NOOP,
                                log_prefix=pre_log)
        out = eng.run()  # must terminate (no runaway)
        self.assertGreater(out.t_end, 0)
        self.assertLess(out.t_end, Fraction(240) * 2)
        self.assertEqual(out.devices_passed + out.devices_exited, BATCH)


class TestSampleTopUp(unittest.TestCase):
    """SAMPLE-01..03: frozen B-1 top-up arithmetic."""

    def test_sample_01_wait_shortfall_topped_up_from_pm(self):
        tw, tp = _b1_take(30, 80)
        self.assertEqual((tw, tp), (30, 70))
        self.assertEqual(tw + tp, 100)

    def test_sample_02_pm_shortfall_topped_up_from_wait(self):
        tw, tp = _b1_take(80, 20)
        self.assertEqual((tw, tp), (80, 20))
        self.assertEqual(tw + tp, 100)

    def test_sample_03_caps_and_fail_safe_cap(self):
        tw, tp = _b1_take(70, 70)
        self.assertEqual((tw, tp), (50, 50))  # first-50 rule, no top-up
        # fail-safe total cap 120 (unreachable under 50/50 + top-up)
        tw, tp = _b1_take(0, 500)
        self.assertLessEqual(tw + tp, SAMPLE_CAP)
        self.assertEqual((tw, tp), (0, 100))
        self.assertEqual(WAIT_CAP, 50)
        self.assertEqual(PM_CAP, 50)
        self.assertEqual(SAMPLE_CAP, 120)

    def test_sample_04_real_sample_respects_frozen_order(self):
        logs = [_gen_batch(0), _gen_batch(1)]
        sample = build_b1_sample(logs, P3C_K, BATCH)
        pts = sample["points"]
        keys = [(p["batch"], str(p["time"]), p["resource"]) for p in pts]
        self.assertEqual(keys, sorted(keys),
                         "sample must be in batch order then intra-batch "
                         "time order")
        self.assertGreaterEqual(sample["n"], 1)
        self.assertLessEqual(sample["n"], SAMPLE_CAP)
        # wait class first (both included), then pm-only
        classes = [p["quota_class"] for p in pts]
        self.assertEqual(classes,
                         ["WAIT"] * sum(1 for c in classes if c == "WAIT")
                         + ["PM"] * sum(1 for c in classes if c == "PM"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
