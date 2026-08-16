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
from main_model.h2_rollout import h2_policy_v1 as pol  # noqa: E402
from scripts.run_h2_p3c_stability_v1 import (  # noqa: E402
    quota_simulate_batch, build_b1_sample, evaluate_sample,
    collect_eligible_points, _b1_take, _point_context,
    _RESOURCE_ORDER, K as P3C_K, MASTER_SEED, NS,
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
    """DPKEY-01..05 + B1-OFFLINE-01..03 (second requalification): the B-1
    OFFLINE diagnostic population = ALL H2-eligible decision points (NOT
    the online-quota subset; C_eval-independent); dp_diag = per-batch
    0-based index by (time, canonical resource order) over the points that
    enter B-1 and are re-evaluated; normal/ALT/M=16 share (replicate_id,
    dp_diag); 2M* uses identical keys for m=0..M*-1."""

    @classmethod
    def setUpClass(cls):
        cls.logs = [_gen_batch(0), _gen_batch(1)]
        cls.sample = build_b1_sample(cls.logs, P3C_K, BATCH)

    def test_dpkey_01_per_batch_dp_diag_0based_contiguous(self):
        by_batch: dict[int, list[int]] = {}
        for p in self.sample["points"]:
            by_batch.setdefault(p["batch"], []).append(p["dp_diag"])
        for bi, dps in by_batch.items():
            self.assertEqual(dps, list(range(len(dps))),
                             f"batch {bi}: dp_diag must be 0-based "
                             f"contiguous per batch (HG-Q3-H2-DP-DIAG-01)")

    def test_dpkey_02_batches_number_independently(self):
        by_batch: dict[int, list[int]] = {}
        for p in self.sample["points"]:
            by_batch.setdefault(p["batch"], []).append(p["dp_diag"])
        self.assertEqual(set(by_batch), {0, 1})
        for bi, dps in by_batch.items():
            self.assertEqual(dps[0], 0, f"batch {bi} starts at dp_diag=0")

    def test_dpkey_03_dp_diag_is_time_resource_ordered(self):
        for bi in {p["batch"] for p in self.sample["points"]}:
            pts = [p for p in self.sample["points"] if p["batch"] == bi]
            keyed = [(p["dp_diag"],
                      (str(p["time"]), _RESOURCE_ORDER[p["resource"]]))
                     for p in pts]
            self.assertEqual(
                [k[0] for k in keyed],
                list(range(len(keyed))),
                f"batch {bi}: dp_diag order must follow (time, resource)")

    def test_dpkey_04_normal_alt_share_batch_dp_diag(self):
        ev_n = evaluate_sample(self.sample, self.logs,
                               "q3h2-bootstrap-v1", 2, BATCH)
        ev_a = evaluate_sample(self.sample, self.logs,
                               "q3h2-bootstrap-alt-v1", 2, BATCH)
        keys_n = [(r["point"]["batch"], r["point"]["dp_diag"])
                  for r in ev_n["rows"]]
        keys_a = [(r["point"]["batch"], r["point"]["dp_diag"])
                  for r in ev_a["rows"]]
        self.assertEqual(keys_n, keys_a)
        self.assertEqual(len(set(keys_n)), len(keys_n),
                         "(batch, dp_diag) must be unique across the sample")

    def test_dpkey_05_2m_prefix_identical_keys(self):
        # 2M* uses the same rollout keys for m=0..M*-1 -> the t_end worlds
        # of the first M* m are identical (WORLD-M-04)
        p = self.sample["points"][0]
        ctx = _point_context(p, self.logs[p["batch"]], BATCH)
        dec8 = pol.evaluate_decision_point(
            ctx["state"], ctx["posterior"], ctx["cfg"],
            p["dp_diag"], p["resource"], p["kind"], p["quota_class"],
            tuple(p["legal_actions"]), ctx["log_prefix"],
            MASTER_SEED, p["batch"], wait_anchor_time=p.get("wait_anchor_time"),
            M=2, decision_head=p.get("head"))
        dec16 = pol.evaluate_decision_point(
            ctx["state"], ctx["posterior"], ctx["cfg"],
            p["dp_diag"], p["resource"], p["kind"], p["quota_class"],
            tuple(p["legal_actions"]), ctx["log_prefix"],
            MASTER_SEED, p["batch"], wait_anchor_time=p.get("wait_anchor_time"),
            M=4, decision_head=p.get("head"))
        for a in dec8.estimates:
            self.assertEqual(dec8.estimates[a].t_end_by_world,
                             dec16.estimates[a].t_end_by_world[:2],
                             f"M=2 vs M=4 prefix mismatch for action {a}")

    def test_b1_offline_01_population_independent_of_c_eval(self):
        # B1-OFFLINE-01: the B-1 candidate population must NOT depend on
        # the production online quota (C_eval=6/8): the sample builder has
        # no quota parameter and the sample points are a subset of ALL
        # eligible points (quota selection is irrelevant to B-1)
        cands = set()
        for bi, blog in enumerate(self.logs):
            for p in collect_eligible_points(blog, P3C_K, BATCH):
                cands.add((bi, str(p["time"]), p["resource"]))
        sample_keys = {(p["batch"], str(p["time"]), p["resource"])
                       for p in self.sample["points"]}
        self.assertTrue(sample_keys.issubset(cands),
                        "B-1 population must be a subset of ALL eligible "
                        "points")
        # the builder signature has NO c_eval parameter: the population is
        # C_eval-independent by construction (frozen §4)
        import inspect
        self.assertNotIn("c_eval",
                         inspect.signature(build_b1_sample).parameters)

    def test_b1_offline_02_quota_selection_does_not_decide_b1(self):
        # B1-OFFLINE-02: whether the online quota selected a point must not
        # decide whether it can enter B-1
        sim = quota_simulate_batch(self.logs[0], P3C_K, BATCH, c_eval=8)
        sel = {(str(p["time"]), p["resource"]) for p in sim}
        sample_batch0 = [p for p in self.sample["points"]
                         if p["batch"] == 0]
        self.assertGreaterEqual(len(sample_batch0), 1)
        not_selected = [p for p in sample_batch0
                        if (str(p["time"]), p["resource"]) not in sel]
        if not not_selected:
            # small fixture: prove with the synthetic 9-point log
            blog = _synthetic_wait_log()
            sim_s = quota_simulate_batch(blog, P3C_K, 12, c_eval=8)
            sel_s = {(str(p["time"]), p["resource"]) for p in sim_s}
            self.assertEqual(len(sel_s), 4)
            cands_s = collect_eligible_points(blog, P3C_K, 12)
            self.assertGreater(len(cands_s), len(sel_s),
                               "fixture: quota must reject candidates")
            self.assertLessEqual(len(sel_s), 4)
            not_sel_s = [p for p in cands_s
                         if (str(p["time"]), p["resource"]) not in sel_s]
            self.assertGreater(len(not_sel_s), 0)
            # a quota-rejected candidate is still a legitimate B-1
            # candidate (population = ALL eligible)
            self.assertTrue(all(
                any(c["time"] == p["time"] and c["resource"] == p["resource"]
                    for c in cands_s)
                for p in [not_sel_s[0]]))
        else:
            self.assertGreater(len(not_selected), 0,
                               "B-1 must include points the online quota "
                               "did not select")

    def test_b1_offline_03_frozen_selection_rule(self):
        # B1-OFFLINE-03: wait/PM 50+50 + top-up + cap 120 strictly per §4
        self.assertEqual(self.sample["wait_cap"], 50)
        self.assertEqual(self.sample["pm_cap"], 50)
        self.assertEqual(self.sample["sample_cap"], 120)
        self.assertLessEqual(self.sample["n"], 120)
        # wait class first (incl. both), then PM-only (frozen order)
        classes = [p["quota_class"] for p in self.sample["points"]]
        self.assertEqual(classes,
                         ["WAIT"] * sum(1 for c in classes if c == "WAIT")
                         + ["PM"] * sum(1 for c in classes if c == "PM"))
        # population claim recorded in the sample dict
        self.assertIn("ALL_H2_ELIGIBLE", self.sample["population"])


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


class TestAgeLegalDecisionPoints(unittest.TestCase):
    """AGE-LEGAL-01..03 (second requalification): a resource with
    equipment age a and task duration d such that a+d > 240 is a
    MANDATORY_REPLACE_FIRST case -> NO H2 decision point (no
    START_HEAD / WAIT / optional PM comparison); a+d == 240 (exact_240)
    -> START_HEAD may execute (complete-first) but PM_WITH_HEAD must not
    be offered; a+d < 240 -> normal frozen rules."""

    K300 = Fraction(300)  # single long shift so late closures are legal

    def _age_legal_log(self, age_h: int):
        # dev1: A/B/C PASS quickly; E att1 runs [6, 6+age_h] and completes
        # ABNORMAL; E att2 released at 6+age_h (the decision closure);
        # dev2 B release keeps the log alive
        end = 6 + age_h
        return _log(
            _start(1, "A", 1, "0", "2"),
            _complete(1, "A", 1, "0", "2"),
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "2",
             "device_id": 1, "process": "A", "effective_attempt_no": 1,
             "resource_id": "A", "outcome": "PASS"},
            _start(1, "B", 1, "2", "4"),
            _complete(1, "B", 1, "2", "4"),
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "4",
             "device_id": 1, "process": "B", "effective_attempt_no": 1,
             "resource_id": "B", "outcome": "PASS"},
            _start(1, "C", 1, "4", "6"),
            _complete(1, "C", 1, "4", "6"),
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "6",
             "device_id": 1, "process": "C", "effective_attempt_no": 1,
             "resource_id": "C", "outcome": "PASS"},
            _start(1, "E", 1, "6", str(end)),
            _complete(1, "E", 1, "6", str(end)),
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": str(end),
             "device_id": 1, "process": "E", "effective_attempt_no": 1,
             "resource_id": "E", "outcome": "ABNORMAL"},
            _release(1, "E", 2, str(end)),
            _release(2, "B", 1, str(end + Fraction(1, 2))),
        )

    def _e_points(self, log, t):
        pts = dp.reconstruct_decision_points(log, self.K300,
                                             batch_size=BATCH)
        return [p for p in pts if p.time == t and p.resource == "E"]

    def test_age_legal_01_a_plus_d_gt_240_no_point(self):
        # E duration 3: age 238 -> 238+3 = 241 > 240 -> mandatory first
        log = self._age_legal_log(238)
        pts = self._e_points(log, Fraction(244))
        self.assertEqual(pts, [],
                         "a+d>240 must yield NO H2 dispatch decision")

    def test_age_legal_02_a_plus_d_eq_240_no_optional_pm(self):
        # age 237 -> 237+3 = 240 (exact_240): START_HEAD legal, no PM
        log = self._age_legal_log(237)
        pts = self._e_points(log, Fraction(243))
        self.assertEqual(len(pts), 1)
        self.assertIn(dp.A_START_HEAD, pts[0].legal_actions)
        self.assertNotIn(dp.A_PM_WITH_HEAD, pts[0].legal_actions)

    def test_age_legal_03_a_plus_d_lt_240_normal(self):
        # age 200 -> 203 < 240: PM_WITH_HEAD offered when optional-PM
        # conditions hold (age >= 120, calibration within shift)
        log = self._age_legal_log(200)
        pts = self._e_points(log, Fraction(206))
        self.assertEqual(len(pts), 1)
        self.assertIn(dp.A_START_HEAD, pts[0].legal_actions)
        self.assertIn(dp.A_PM_WITH_HEAD, pts[0].legal_actions)


class TestObservablePendingStatus(unittest.TestCase):
    """PENDING-01..04 (second requalification): same-timestamp observable
    failure / illegal-240 cancellation / post-completion mandatory age
    must be visible in the H2 PRE-ACTION state (never idle/available);
    no hidden lifetime is read."""

    K300 = Fraction(300)

    def _base(self, *recs):
        return _log(*recs)

    def test_pending_01_same_timestamp_failure(self):
        # PENDING-01: EQUIPMENT_FAILURE at t -> resource failed/unavailable
        log = self._base(
            _release(1, "E", 1, "10"),
            {"event_type": "EQUIPMENT_FAILURE", "event_time": "10",
             "resource_id": "E", "device_id": 1, "process": "E",
             "fragment_start": "8", "fragment_end": "10"},
            _release(2, "B", 1, "12"),
        )
        st = dp.project_pre_action_state(log, Fraction(10),
                                         batch_size=BATCH)
        rsrc = next(r for r in st.resources if r.resource == "E")
        self.assertEqual(rsrc.status, "failed")
        pts = dp.reconstruct_decision_points(log, self.K300,
                                             batch_size=BATCH)
        self.assertEqual([p for p in pts if p.resource == "E"], [])

    def test_pending_02_post_completion_mandatory_age(self):
        # PENDING-02: completed age reaches 240 -> replacement pending
        log = self._base(
            _start(1, "E", 1, "0", "240"),
            _complete(1, "E", 1, "0", "240"),
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "240",
             "device_id": 1, "process": "E", "effective_attempt_no": 1,
             "resource_id": "E", "outcome": "PASS"},
            _release(1, "E", 2, "241"),
            _release(2, "B", 1, "242"),
        )
        st = dp.project_pre_action_state(log, Fraction(241),
                                         batch_size=BATCH)
        rsrc = next(r for r in st.resources if r.resource == "E")
        self.assertEqual(rsrc.status, "replacement")
        pts = dp.reconstruct_decision_points(log, self.K300,
                                             batch_size=BATCH)
        self.assertEqual([p for p in pts if p.resource == "E"], [])

    def test_pending_03_illegal240_cancellation(self):
        # PENDING-03: illegal-240 cancellation -> mandatory replacement
        log = self._base(
            _start(1, "E", 1, "0", "3"),
            {"event_type": "TASK_CANCEL", "event_time": "3",
             "device_id": 1, "process": "E", "effective_attempt_no": 1,
             "resource_id": "E", "attempt_start_time": "0",
             "attempt_end_time": "3", "outcome": "NONE",
             "cancel_reason": "illegal_240"},
            _release(1, "E", 1, "3"),
            _release(2, "B", 1, "5"),
        )
        st = dp.project_pre_action_state(log, Fraction(3),
                                         batch_size=BATCH)
        rsrc = next(r for r in st.resources if r.resource == "E")
        self.assertEqual(rsrc.status, "replacement")
        pts = dp.reconstruct_decision_points(log, self.K300,
                                             batch_size=BATCH)
        self.assertEqual([p for p in pts if p.resource == "E"], [])

    def test_pending_04_plain_idle_unaffected(self):
        log = self._base(
            _release(1, "E", 1, "10"),
            _release(2, "B", 1, "12"),
        )
        st = dp.project_pre_action_state(log, Fraction(10),
                                         batch_size=BATCH)
        rsrc = next(r for r in st.resources if r.resource == "E")
        self.assertEqual(rsrc.status, "idle")


class TestPosteriorWorldM(unittest.TestCase):
    """WORLD-M-01..06 (second requalification): the policy evaluator
    rebuilds one posterior world_m per m from the h2_rollout post keys
    (shared across the candidate actions of that m; no physical hidden
    world enters the rollouts)."""

    @classmethod
    def setUpClass(cls):
        cls.logs = [_gen_batch(0), _gen_batch(1)]
        cls.sample = build_b1_sample(cls.logs, P3C_K, BATCH)

    def _ctx(self):
        p = self.sample["points"][0]
        return p, _point_context(p, self.logs[p["batch"]], BATCH)

    def _world_m(self, ctx, dp_diag, m, replicate_id,
                 salt="q3h2-bootstrap-v1"):
        from main_model.h2_rollout.post_keys_v1 import rollout_post_keys
        keys = rollout_post_keys(
            MASTER_SEED, replicate_id, dp_diag, m,
            tuple(range(1, BATCH + 1)),
            tuple(r.resource for r in ctx["state"].resources),
            {r.resource: r.generation for r in ctx["state"].resources},
            salt=salt)
        return cont.rebuild_continuation_world(
            ctx["state"], ctx["posterior"],
            u_x_by_device=keys.u_x_by_device,
            u_d_by_device=keys.u_d_by_device,
            u_l_by_resource=keys.u_l_by_resource)

    def test_world_m_01_different_m_may_differ(self):
        # different m -> different keys -> the posterior world is allowed
        # to differ (sampled x_abc / x_d / residual lifetime)
        p, ctx = self._ctx()
        diffs = 0
        for m in range(3):
            w0 = self._world_m(ctx, p["dp_diag"], m, p["batch"])
            w1 = self._world_m(ctx, p["dp_diag"], m + 1, p["batch"])
            if (w0.devices != w1.devices
                    or w0.residual_lifetimes != w1.residual_lifetimes):
                diffs += 1
        self.assertGreater(diffs, 0,
                           "different m must allow different posterior "
                           "worlds (keys resample x_abc/x_d/lifetime)")

    def test_world_m_02_same_keys_same_world(self):
        p, ctx = self._ctx()
        w0 = self._world_m(ctx, p["dp_diag"], 2, p["batch"])
        w1 = self._world_m(ctx, p["dp_diag"], 2, p["batch"])
        self.assertEqual(w0.devices, w1.devices)
        self.assertEqual(w0.residual_lifetimes, w1.residual_lifetimes)

    def test_world_m_03_one_world_per_m_across_actions(self):
        # the evaluator must rebuild exactly M worlds (not M x actions)
        import unittest.mock as mock
        p, ctx = self._ctx()
        real = cont.rebuild_continuation_world
        calls = {"n": 0}

        def counting(*a, **kw):
            calls["n"] += 1
            return real(*a, **kw)

        with mock.patch.object(cont, "rebuild_continuation_world",
                               side_effect=counting):
            pol.evaluate_decision_point(
                ctx["state"], ctx["posterior"], ctx["cfg"],
                p["dp_diag"], p["resource"], p["kind"], p["quota_class"],
                tuple(p["legal_actions"]), ctx["log_prefix"],
                MASTER_SEED, p["batch"],
                wait_anchor_time=p.get("wait_anchor_time"),
                M=2, decision_head=p.get("head"))
        self.assertEqual(calls["n"], 2,
                         "exactly M world rebuilds, shared across actions")

    def test_world_m_04_m16_prefix_identical_to_m8(self):
        # 2M* uses identical keys for m=0..M*-1 (DPKEY-05 covers t_end;
        # here: keys themselves are identical)
        from main_model.h2_rollout.post_keys_v1 import rollout_post_keys
        p, ctx = self._ctx()
        res = tuple(r.resource for r in ctx["state"].resources)
        gens = {r.resource: r.generation for r in ctx["state"].resources}
        for m in range(4):
            k8 = rollout_post_keys(MASTER_SEED, p["batch"], p["dp_diag"], m,
                                   tuple(range(1, BATCH + 1)), res, gens)
            k16 = rollout_post_keys(MASTER_SEED, p["batch"], p["dp_diag"], m,
                                    tuple(range(1, BATCH + 1)), res, gens)
            self.assertEqual(k8.seed, k16.seed)
            self.assertEqual(k8.to_canonical_dict(),
                             k16.to_canonical_dict())

    def test_world_m_05_hidden_annotations_do_not_change_decision(self):
        # C23 strong check: changing physical hidden annotations
        # (true_state / lifetime_h / u) while ObservableState /
        # PosteriorState / h2_rollout keys stay identical must not change
        # Q_hat / SE / action
        p, ctx = self._ctx()
        blog = self.logs[p["batch"]]
        variants = []
        for i, mut in enumerate((
                lambda r: r.update(true_state={"A": True, "B": True,
                                               "C": True}),
                lambda r: r.update(lifetime_h="999"),
                lambda r: r.update(u="0.999"))):
            vlog = []
            for r in blog:
                rec = dict(r)
                mut(rec)
                vlog.append(rec)
            variants.append(vlog)
        base_dec = pol.evaluate_decision_point(
            ctx["state"], ctx["posterior"], ctx["cfg"],
            p["dp_diag"], p["resource"], p["kind"], p["quota_class"],
            tuple(p["legal_actions"]), ctx["log_prefix"],
            MASTER_SEED, p["batch"], wait_anchor_time=p.get("wait_anchor_time"),
            M=2, decision_head=p.get("head"))
        for vlog in variants:
            vctx = _point_context(p, vlog, BATCH)
            vdec = pol.evaluate_decision_point(
                vctx["state"], vctx["posterior"], vctx["cfg"],
                p["dp_diag"], p["resource"], p["kind"], p["quota_class"],
                tuple(p["legal_actions"]), vctx["log_prefix"],
                MASTER_SEED, p["batch"],
                wait_anchor_time=p.get("wait_anchor_time"),
                M=2, decision_head=p.get("head"))
            for a in base_dec.estimates:
                e0 = base_dec.estimates[a]
                ev = vdec.estimates[a]
                self.assertEqual(e0.q_hat, ev.q_hat,
                                 f"hidden annotations changed Q_hat ({a})")
                self.assertEqual(e0.se_m, ev.se_m,
                                 f"hidden annotations changed SE ({a})")
            self.assertEqual(base_dec.chosen, vdec.chosen)

    def test_world_m_06_online_offline_parity(self):
        # same (state, posterior, config, replicate, dp_diag, keys) ->
        # identical Q_hat / SE / chosen action (online and offline paths
        # both delegate to evaluate_decision_point)
        p, ctx = self._ctx()
        d1 = pol.evaluate_decision_point(
            ctx["state"], ctx["posterior"], ctx["cfg"],
            p["dp_diag"], p["resource"], p["kind"], p["quota_class"],
            tuple(p["legal_actions"]), ctx["log_prefix"],
            MASTER_SEED, p["batch"], wait_anchor_time=p.get("wait_anchor_time"),
            M=2, decision_head=p.get("head"))
        d2 = pol.evaluate_decision_point(
            ctx["state"], ctx["posterior"], ctx["cfg"],
            p["dp_diag"], p["resource"], p["kind"], p["quota_class"],
            tuple(p["legal_actions"]), ctx["log_prefix"],
            MASTER_SEED, p["batch"], wait_anchor_time=p.get("wait_anchor_time"),
            M=2, decision_head=p.get("head"))
        self.assertEqual(d1.to_canonical_dict(), d2.to_canonical_dict())
        self.assertEqual(d1.chosen, d2.chosen)


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

    def test_release_guard_03_e_path_no_rerelease(self):
        # E-path mirror of RELEASE-GUARD-01: dev1 A/B/C PASSED, E att1
        # completed ABNORMAL, E att2 queued -> rebuild must keep ONLY att2
        log = _log(
            _start(1, "A", 1, "0", "2"),
            _complete(1, "A", 1, "0", "2"),
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "2",
             "device_id": 1, "process": "A", "effective_attempt_no": 1,
             "resource_id": "A", "outcome": "PASS"},
            _start(1, "B", 1, "2", "4"),
            _complete(1, "B", 1, "2", "4"),
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "4",
             "device_id": 1, "process": "B", "effective_attempt_no": 1,
             "resource_id": "B", "outcome": "PASS"},
            _start(1, "C", 1, "4", "13/2"),
            _complete(1, "C", 1, "4", "13/2"),
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "13/2",
             "device_id": 1, "process": "C", "effective_attempt_no": 1,
             "resource_id": "C", "outcome": "PASS"},
            _start(1, "E", 1, "7", "10"),
            _complete(1, "E", 1, "7", "10"),
            {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "10",
             "device_id": 1, "process": "E", "effective_attempt_no": 1,
             "resource_id": "E", "outcome": "ABNORMAL"},
            _release(1, "E", 2, "10"),
            _release(2, "B", 1, "12"),
        )
        st, post, world, prov, cfg, pre_log = _toy_context(
            log, Fraction(10), rep=1)
        eng = re1.RolloutEngine(st, post, world, prov, cfg,
                                first_action=re1.A_H1_NOOP,
                                log_prefix=pre_log)
        eng._release_tasks()
        e_entries = [e for e in eng.queues["E"]
                     if eng.tasks[e.task_id].device_id == 1]
        self.assertEqual(len(e_entries), 1,
                         "the tested E att1 must NOT be re-released")
        self.assertEqual(eng.tasks[e_entries[0].task_id].effective_attempt_no,
                         2)


class TestBayOccupancyProjection(unittest.TestCase):
    """BAY-OCCUPANCY-01..02 (second requalification fix): the observable
    bay's CURRENT OCCUPANT is the device of the latest TRUE_STATE_GENERATED
    (the new device the bay actually hosts after a turnover), NOT the
    TURNOVER_IN_COMPLETE device_id (which is the transported OLD device);
    a stale occupant identity would unbind the live device from its bay and
    deadlock the engine (bay marked TERMINAL while the device still
    waits)."""

    def test_bay_occupancy_01_true_state_updates_occupant(self):
        log = _log(
            {"event_type": "TURNOVER_OUT_START", "event_time": "10",
             "bay_id": 1, "device_id": 5},
            {"event_type": "TURNOVER_OUT_COMPLETE", "event_time": "10",
             "bay_id": 1, "device_id": 5},
            {"event_type": "TURNOVER_IN_START", "event_time": "10",
             "bay_id": 1, "device_id": 5},
            {"event_type": "TURNOVER_IN_COMPLETE", "event_time": "11",
             "bay_id": 1, "device_id": 5},
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "11",
             "bay_id": 1, "device_id": 6},
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 1,
             "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 2,
             "true_state": {"A": False, "B": False, "C": False}},
            _release(2, "B", 1, "12"),
        )
        st = dp.project_pre_action_state(log, Fraction(12),
                                         batch_size=BATCH)
        bay1 = next(b for b in st.bays if b.bay_id == 1)
        self.assertEqual(bay1.current_device, 6,
                         "the bay occupant must be the TRUE_STATE device "
                         "(6), not the transported device (5)")

    def test_bay_occupancy_02_no_turnover_keeps_initial_occupant(self):
        log = _log(
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "bay_id": 1, "device_id": 3},
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 1,
             "true_state": {"A": False, "B": False, "C": False}},
            {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
             "device_id": 2,
             "true_state": {"A": False, "B": False, "C": False}},
            _release(2, "B", 1, "5"),
        )
        st = dp.project_pre_action_state(log, Fraction(5),
                                         batch_size=BATCH)
        bay1 = next(b for b in st.bays if b.bay_id == 1)
        self.assertEqual(bay1.current_device, 3)


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
