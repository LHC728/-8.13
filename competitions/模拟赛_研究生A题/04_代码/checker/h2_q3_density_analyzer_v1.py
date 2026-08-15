#!/usr/bin/env python3
"""Q3 seven-K H2 opportunity-density analyzer (Density Gate; read-only).

Q3-H2-DENSITY-E1 TEMPORAL RECONSTRUCTION REQUALIFICATION (Human Gate
repair package): this revision replaces the final-state reconstruction
defects with a TIME-INDEXED observable reconstruction.  The accepted
Q2-admission analyzer (h2_admission_opportunity_analyzer_v1) is NOT
modified; Q3 keeps its own Q3-specific time-causal layer.

Human Gate VERIFIED findings fixed here:
  F1 future_potential_demand used the FINAL terminal set / FINAL pass
     status  -> replaced by future_potential_demand_at(resource, t),
     which reads ONLY records with event_time <= t (entered-at-t,
     non-terminal-at-t, not-yet-passed-at-t, or batch not fully entered).
  F2 head_candidate was not time-causal (no release_time <= t filter;
     terminal_devs from the FINAL terminal set; 'started' detected by
     st_time == rel_time) -> replaced by fcfs_head_at(resource, t) with
     frozen global FCFS (release_time, device_id, process_order,
     effective_attempt_no) over WAITING tasks at t only.
  F3 proc_passed was the FINAL pass status -> replaced by
     process_passed_at_or_before(device, process, t) for E prerequisites.
  F4 mandatory was counted only at ACTIVITY_START anchors (age+d>240)
     which the engine NEVER reaches (mandatory replacement happens
     PRE-START) -> mandatory is now reconstructed from the frozen
     EQUIPMENT_REPLACEMENT_START kind/trigger vocabulary
     (kind=mandatory_240; triggers a_plus_d_gt_240 / post_completion_240
     / illegal_crossing_backstop) and cross-checked against the
     pre-replacement closure state.

Reconstruction (time-indexed, all predicates from event_time <= t):
  entered_at_or_before / terminal_at_or_before /
  process_passed_at_or_before / task_released_at_or_before /
  task_started_at_or_before / task_cancelled_at_or_before /
  waiting_tasks_at / fcfs_head_at / future_potential_demand_at /
  equipment_age_at / equipment_available_at / resource_idle_at.

Decision closure enumeration (frozen engine semantics, Q3-H2-DENSITY-E1
section 7): the accepted engine runs _closure(t) at every event time and
at every shift boundary; _equipment_and_dispatch is the single
equipment/dispatch closure.  The closure set is reconstructed as the
distinct canonical event_time values over ALL records plus the Q3 shift
starts (SHIFT_CHANGE / WAKE_UP / TASK_RELEASE / ACTIVITY_COMPLETE /
TASK_CANCEL / EQUIPMENT_REPLACEMENT_START / calibration-complete
closures are all covered because every closure emits records).  At most
one decision point per (resource, closure).

Classification (frozen, D-14):
  * DISPATCH_DECISION_POINT anchored at each ACTIVITY_START (a legal
    head was dispatched): legal_dispatch, STRICT/BOUNDARY/NONSTRICT
    strategic wait, optional PM_WITH_HEAD, both, meaningful, exact_240
    (a+d==240), mandatory_at_dispatch_diagnostic (a+d>240 anomaly).
  * MAINTENANCE_DECISION_POINT at closures where the resource is
    idle/available with NO legal START_HEAD and the frozen maintenance
    conditions hold (age in [120,240), calibration fits the shift,
    future potential demand at t): candidate A0b/A2b (PM_IDLE).
    queue-empty and queue-nonempty-no-legal-head both qualify.
  * FORCED_WAIT: closure with idle/available resource, waiting head that
    cannot legally start NOW (time-causal legality).  Cross-checked per
    batch against the accepted engine c24.waiting_opportunity_count
    (forced-wait instrument) in the runner.
  * MANDATORY: EQUIPMENT_REPLACEMENT_START kind=mandatory_240 counts
    (trigger breakdown); exact_240 at dispatch anchors (a+d==240,
    engine serves the head first).
  * meaningful fraction (D-14, admission-comparable) = meaningful
    DISPATCH choice points / legal DISPATCH decision points.  PM_IDLE is
    reported separately as the frozen maintenance-point count and never
    enters the D-14 denominator.
  * zero-opportunity disclosure: zero_dispatch_opportunity_batch
    (D-14 frozen comparable, meaningful==0) and
    zero_full_action_space_opportunity_batch (meaningful==0 AND
    pm_idle==0) as descriptive diagnostics; thresholds unchanged.

Python 3.12, standard library only.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from checker import h2_admission_opportunity_analyzer_v1 as adm  # noqa: E402

# Frozen constants (reused read-only from the accepted admission analyzer;
# time-safe primitives only: latest_legal_start, calendar helpers).
RESOURCES = adm.RESOURCES
PROCESS_ORDER = adm.PROCESS_ORDER
DEFAULT_DURATIONS_H = dict(adm.DEFAULT_DURATIONS_H)
CALIBRATION_MINUTES = adm.CALIBRATION_MINUTES
MIN_PREVENTIVE_AGE_H = adm.MIN_PREVENTIVE_AGE_H
MANDATORY_AGE_H = adm.MANDATORY_AGE_H
latest_legal_start = adm.latest_legal_start

BATCH_SIZE = 100  # P040 (frozen Q3 batch)

# Frozen replacement vocabulary (accepted engine, random_des_v1).
REPLACEMENT_KIND_MANDATORY = "mandatory_240"
TRIGGER_A_PLUS_D_GT_240 = "a_plus_d_gt_240"
TRIGGER_POST_COMPLETION_240 = "post_completion_240"
TRIGGER_ILLEGAL_CROSSING_BACKSTOP = "illegal_crossing_backstop"
TRIGGER_PREVENTIVE = "preventive"
CANCEL_REASON_DEVICE_EXIT = "DEVICE_EXIT"

EV_ACTIVITY_START = "ACTIVITY_START"
EV_ACTIVITY_COMPLETE = "ACTIVITY_COMPLETE"
EV_TASK_RELEASE = "TASK_RELEASE"
EV_TASK_CANCEL = "TASK_CANCEL"
EV_OBSERVATION = "OBSERVATION_MATERIALIZED"
EV_DEVICE_TERMINAL = "DEVICE_TERMINAL"
EV_TRUE_STATE = "TRUE_STATE_GENERATED"
EV_REPLACEMENT_START = "EQUIPMENT_REPLACEMENT_START"
EV_REPLACEMENT_DEFERRED = "EQUIPMENT_REPLACEMENT_DEFERRED"


def frac(value: Any) -> Fraction:
    return Fraction(value)


# ---------------------------------------------------------------------------
# Q3 two-shift K calendar
# ---------------------------------------------------------------------------


def q3_shift_grid(K: Fraction) -> list[tuple[Fraction, Fraction]]:
    """Day d: shift 1=[24d, 24d+K), shift 2=[24d+K, 24d+2K), off
    [24d+2K, 24(d+1)).  Horizon 400 days is far beyond any 100-device Q3
    batch."""
    out: list[tuple[Fraction, Fraction]] = []
    for d in range(0, 400):
        s1 = Fraction(24) * d
        out.append((s1, s1 + K))
        out.append((s1 + K, s1 + 2 * K))
    return out


def active_shift(shifts: list[tuple[Fraction, Fraction]], t: Fraction
                 ) -> Optional[tuple[Fraction, Fraction]]:
    for s, e in shifts:
        if s <= t < e:
            return (s, e)
    return None


# ---------------------------------------------------------------------------
# Time-indexed observable reconstruction (Q3-H2-DENSITY-E1 sections 4-6)
# ---------------------------------------------------------------------------


@dataclass
class TimeIndexedView:
    """Read-only time-indexed reconstruction.  Every predicate below uses
    ONLY records with event_time <= t (no future terminal / future PASS /
    future release / future start / future cancellation)."""

    log: list[dict[str, Any]] = field(default_factory=list)
    # ACTIVITY_START: (event_time, device, process, attempt, resource,
    #                 scheduled_end)
    starts: list[tuple[Fraction, int, str, int, str, Fraction]] = field(
        default_factory=list)
    # ACTIVITY_COMPLETE: (event_time, device, process, attempt, resource)
    completes: list[tuple[Fraction, int, str, int, str]] = field(
        default_factory=list)
    # TASK_CANCEL: (event_time, device, process, attempt, resource,
    #               cancel_reason)
    cancels: list[tuple[Fraction, int, str, int, str, str]] = field(
        default_factory=list)
    # TASK_RELEASE: (event_time, resource, device, process, attempt)
    releases: list[tuple[Fraction, str, int, str, int]] = field(
        default_factory=list)
    # PASS observations: (event_time, device, process)
    obs_passed: list[tuple[Fraction, int, str]] = field(default_factory=list)
    # DEVICE_TERMINAL: (event_time, device)
    terminals: list[tuple[Fraction, int]] = field(default_factory=list)
    # TRUE_STATE_GENERATED (device entry): (event_time, device)
    entries: list[tuple[Fraction, int]] = field(default_factory=list)
    # EQUIPMENT_REPLACEMENT_START: (event_time, resource, cal_start,
    #                               cal_end, kind, trigger)
    replacements: list[tuple[Fraction, str, Fraction, Fraction, str, str]] = field(
        default_factory=list)
    # EQUIPMENT_REPLACEMENT_DEFERRED: (event_time, resource)
    deferrals: list[tuple[Fraction, str]] = field(default_factory=list)
    # resources that DISPATCHED at each closure time (ACTIVITY_START at t):
    # the engine has at most ONE decision point per (resource, closure), so
    # a closure where a resource dispatched is a DISPATCH point, never a
    # maintenance/forced-wait point (E1 closure semantics).
    dispatch_at: dict[Fraction, set[str]] = field(default_factory=dict)
    # distinct canonical event_time closures (sorted)
    event_times: list[Fraction] = field(default_factory=list)
    batch_end: Fraction = Fraction(0)


def build_time_index(event_log: list[dict[str, Any]]) -> TimeIndexedView:
    view = TimeIndexedView(log=event_log)
    times: set[Fraction] = set()
    for rec in event_log:
        et = rec.get("event_type")
        t = frac(rec["event_time"]) if rec.get("event_time") is not None else None
        if t is None:
            continue
        times.add(t)
        if et == EV_ACTIVITY_START:
            view.starts.append((
                t, rec["device_id"], rec["process"], rec["effective_attempt_no"],
                rec["resource_id"], frac(rec["attempt_end_time"]),
            ))
            view.dispatch_at.setdefault(t, set()).add(rec["resource_id"])
        elif et == EV_ACTIVITY_COMPLETE:
            view.completes.append((
                t, rec["device_id"], rec["process"],
                rec["effective_attempt_no"], rec["resource_id"],
            ))
        elif et == EV_TASK_CANCEL:
            view.cancels.append((
                t, rec["device_id"], rec["process"],
                rec["effective_attempt_no"], rec["resource_id"],
                rec.get("cancel_reason") or "",
            ))
        elif et == EV_TASK_RELEASE:
            view.releases.append((
                t, rec["resource_id"], rec["device_id"], rec["process"],
                rec["effective_attempt_no"],
            ))
        elif et == EV_OBSERVATION:
            if rec.get("outcome") == "PASS":
                view.obs_passed.append((t, rec["device_id"], rec["process"]))
        elif et == EV_DEVICE_TERMINAL:
            view.terminals.append((t, rec["device_id"]))
        elif et == EV_TRUE_STATE:
            view.entries.append((t, rec["device_id"]))
        elif et == EV_REPLACEMENT_START:
            view.replacements.append((
                t, rec["resource_id"], frac(rec["calibration_start"]),
                frac(rec["calibration_end"]), rec.get("kind") or "",
                rec.get("trigger") or "",
            ))
        elif et == EV_REPLACEMENT_DEFERRED:
            view.deferrals.append((t, rec["resource_id"]))
    view.event_times = sorted(times)
    view.batch_end = (
        max(t for t, _d in view.terminals) if view.terminals
        else (max(view.event_times) if view.event_times else Fraction(0))
    )
    return view


# -- time-causal predicates (all event_time <= t) ---------------------------


def entered_at_or_before(view: TimeIndexedView, device: int, t: Fraction) -> bool:
    return any(t0 <= t for t0, d in view.entries if d == device)


def terminal_at_or_before(view: TimeIndexedView, device: int, t: Fraction) -> bool:
    return any(t0 <= t for t0, d in view.terminals if d == device)


def process_passed_at_or_before(view: TimeIndexedView, device: int,
                                process: str, t: Fraction) -> bool:
    return any(t0 <= t and d == device and p == process
               for t0, d, p in view.obs_passed)


def task_released_at_or_before(view: TimeIndexedView, device: int,
                               process: str, attempt: int, t: Fraction) -> bool:
    return any(t0 <= t and r == process and d == device and p == process
               and a == attempt for t0, r, d, p, a in view.releases)


def _fragment_settled_at_or_before(view: TimeIndexedView, device: int,
                                   process: str, attempt: int,
                                   start_time: Fraction, t: Fraction) -> bool:
    """The FRAGMENT of the exact task that started at ``start_time`` has a
    completion or cancellation record <= t (fragments are identified by
    attempt_start_time; a requeued task has several fragments)."""
    for t0, d, p, a, _r in view.completes:
        if t0 <= t and d == device and p == process and a == attempt:
            s_raw = _start_of(view, device, process, attempt, t0)
            if s_raw is not None and s_raw == start_time:
                return True
    for t0, d, p, a, _r, _c in view.cancels:
        if t0 <= t and d == device and p == process and a == attempt:
            s_raw = _start_of(view, device, process, attempt, t0)
            if s_raw is not None and s_raw == start_time:
                return True
    return False


def _start_of(view: TimeIndexedView, device: int, process: str, attempt: int,
              settle_time: Fraction) -> Optional[Fraction]:
    """attempt_start_time of the settle record for (device, process,
    attempt) at ``settle_time`` (from ACTIVITY_COMPLETE / TASK_CANCEL)."""
    for rec in view.log:
        if rec.get("event_type") not in (EV_ACTIVITY_COMPLETE, EV_TASK_CANCEL):
            continue
        if rec.get("device_id") != device or rec.get("process") != process:
            continue
        if rec.get("effective_attempt_no") != attempt:
            continue
        if frac(rec["event_time"]) != settle_time:
            continue
        if rec.get("attempt_start_time") is not None:
            return frac(rec["attempt_start_time"])
    return None


def task_running_at(view: TimeIndexedView, device: int, process: str,
                    attempt: int, t: Fraction) -> bool:
    """The exact task currently occupies the resource at t: a FRAGMENT of it
    started at s <= t with no fragment-settle <= t and scheduled end > t.
    (Fragments are identified by their start time; a requeued task has
    several fragments.)"""
    for s, d, p, a, _r, end in view.starts:
        if d == device and p == process and a == attempt:
            if s <= t and not _fragment_settled_at_or_before(
                    view, device, process, attempt, s, t) and t < end:
                return True
    return False


def task_completed_at_or_before(view: TimeIndexedView, device: int,
                                process: str, attempt: int, t: Fraction) -> bool:
    return any(t0 <= t and d == device and p == process and a == attempt
               for t0, d, p, a, _r in view.completes)


def waiting_tasks_at(view: TimeIndexedView, resource: str, t: Fraction
                     ) -> list[tuple[Fraction, int, str, int]]:
    """WAITING tasks for resource at t: released at rel <= t, device not
    terminal at t, task not completed, task not currently running."""
    out: list[tuple[Fraction, int, str, int]] = []
    seen: set[tuple[int, str, int]] = set()
    for rel, rsrc, dev, proc, att in view.releases:
        if rsrc != resource:
            continue
        if rel > t:
            continue
        if (dev, proc, att) in seen:
            continue
        seen.add((dev, proc, att))
        if terminal_at_or_before(view, dev, t):
            continue
        if task_completed_at_or_before(view, dev, proc, att, t):
            continue
        if task_running_at(view, dev, proc, att, t):
            continue
        out.append((rel, dev, proc, att))
    out.sort(key=lambda item: (
        item[0], item[1], PROCESS_ORDER.get(item[2], 9), item[3]))
    return out


def fcfs_head_at(view: TimeIndexedView, resource: str, t: Fraction
                 ) -> Optional[tuple[int, str, int]]:
    """Frozen global FCFS head (release_time, device_id, process_order,
    effective_attempt_no) among WAITING tasks only."""
    waiting = waiting_tasks_at(view, resource, t)
    if not waiting:
        return None
    _rel, dev, proc, att = waiting[0]
    return (dev, proc, att)


def head_is_legal_at(view: TimeIndexedView, head: tuple[int, str, int],
                     t: Fraction, d: Fraction, shift_end: Fraction) -> bool:
    """Time-causal legality: device not terminal at t; E prereq by PASS
    observation time <= t; duration fits the shift (恰班末完成允许)."""
    dev, proc, att = head
    if terminal_at_or_before(view, dev, t):
        return False
    if proc == "E":
        if not all(process_passed_at_or_before(view, dev, p, t)
                   for p in ("A", "B", "C")):
            return False
    return t + d <= shift_end


def future_potential_demand_at(view: TimeIndexedView, resource: str, t: Fraction,
                               batch_size: int = BATCH_SIZE) -> bool:
    """Frozen condition at t (only records <= t):
      A) an entered-at-t, non-terminal-at-t device that has not yet validly
         passed this process; OR
      B) the batch is not yet fully entered (entered_count(t) < batch_size).
    The FINAL terminal set is never used."""
    entered = {d for t0, d in view.entries if t0 <= t}
    for dev in entered:
        if terminal_at_or_before(view, dev, t):
            continue
        if not process_passed_at_or_before(view, dev, resource, t):
            return True
    if len(entered) < batch_size:
        return True
    return False


def equipment_age_at(view: TimeIndexedView, resource: str, t: Fraction) -> Fraction:
    """Time-causal equipment age: sum of test-fragment elapsed durations
    (ACTIVITY_COMPLETE / TASK_CANCEL) ending <= t within the current
    generation (latest EQUIPMENT_REPLACEMENT_START at or before t resets
    age to 0).  Calibration is not counted."""
    gen_start = Fraction(0)
    for t0, r, _cs, _ce, _k, _tr in view.replacements:
        if r == resource and t0 <= t:
            gen_start = max(gen_start, t0)
    age = Fraction(0)
    for rec in view.log:
        if rec.get("event_type") not in (EV_ACTIVITY_COMPLETE, EV_TASK_CANCEL):
            continue
        if rec.get("resource_id") != resource:
            continue
        s_raw = rec.get("attempt_start_time")
        e_raw = rec.get("event_time")
        if s_raw is None or e_raw is None:
            continue
        s = frac(s_raw)
        e = frac(e_raw)
        if s < gen_start:
            continue
        if e <= t:
            age += e - s
    return age


def equipment_available_at(view: TimeIndexedView, resource: str, t: Fraction) -> bool:
    """Equipment usable at t: not inside a replacement window
    [pending_time, calibration_end).  Windows come from
    EQUIPMENT_REPLACEMENT_START (pending+calibration from its event time)
    and EQUIPMENT_REPLACEMENT_DEFERRED (pending from the deferral time
    until the next replacement's calibration end)."""
    windows: list[tuple[Fraction, Fraction]] = []
    for t0, r, cs, ce, _k, _tr in view.replacements:
        if r == resource:
            windows.append((t0, ce))
    # deferral -> pending window until the next replacement's cal end
    for td, r in view.deferrals:
        if r != resource:
            continue
        nxt = None
        for t0, r2, _cs, ce, _k, _tr in view.replacements:
            if r2 == resource and t0 >= td:
                if nxt is None or ce < nxt:
                    nxt = ce
        if nxt is not None:
            windows.append((td, nxt))
    windows.sort()
    merged: list[tuple[Fraction, Fraction]] = []
    for s, e in windows:
        if merged and s < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return not any(s <= t < e for s, e in merged)


def resource_idle_at(view: TimeIndexedView, resource: str, t: Fraction) -> bool:
    """Resource idle at t: no test FRAGMENT in flight (fragment started at
    s <= t < scheduled end with no fragment-settle <= t) and no
    calibration interval covering t."""
    for s, _d, _p, _a, r, end in view.starts:
        if r != resource:
            continue
        if s <= t < end and not _fragment_settled_at_or_before(
                view, _d, _p, _a, s, t):
            return False
    for t0, r, cs, ce, _k, _tr in view.replacements:
        if r == resource and cs <= t < ce:
            return False
    return True


def other_same_device_completions(view: TimeIndexedView, t: Fraction,
                                  device: int) -> list[Fraction]:
    """Scheduled completion times (attempt_end_time) of same-device
    activities already started with start < t < scheduled end (time-causal:
    reads only already-started activities)."""
    out = []
    for s, d, _p, _a, _r, end in view.starts:
        if d == device and s < t < end:
            out.append(end)
    return sorted(out)


def closure_times(view: TimeIndexedView,
                  shifts: list[tuple[Fraction, Fraction]]) -> list[Fraction]:
    """Q3-H2-DENSITY-E1 section 7: the decision closure set =
    distinct canonical event_time values over ALL records (covers
    TASK_RELEASE / ACTIVITY_COMPLETE / cancellation-failure /
    calibration-complete / WAKE_UP / SHIFT_CHANGE closures, because every
    engine closure emits records) plus the Q3 shift starts (necessary
    shift-start boundaries).  Closures at/after batch_end are filtered by
    the caller."""
    times = set(view.event_times)
    for s, _e in shifts:
        times.add(s)
    return sorted(times)


# ---------------------------------------------------------------------------
# Q3 decision-point classification
# ---------------------------------------------------------------------------


@dataclass
class DensityBatchStats:
    k_label: str
    k_hours: str
    batch_index: int
    # dispatch-side (anchored at ACTIVITY_START; unchanged by E1)
    legal_dispatch_decision_points: int = 0
    strategic_strict: int = 0
    strategic_boundary: int = 0
    strategic_nonstrict: int = 0
    raw_pm_age_eligible: int = 0
    pm_with_head: int = 0
    both_wait_and_pm: int = 0
    meaningful_h2_choice: int = 0
    exact_240: int = 0
    mandatory_at_dispatch_diagnostic: int = 0
    # maintenance / forced-wait / mandatory (E1 requalified)
    forced_wait: int = 0
    pm_idle: int = 0
    queue_empty_pm_idle: int = 0
    queue_nonempty_no_legal_head_pm_idle: int = 0
    maintenance_decision_points: int = 0
    mandatory_replacement: int = 0
    mandatory_a_plus_d_gt_240: int = 0
    mandatory_post_completion_240: int = 0
    mandatory_illegal_crossing_backstop: int = 0
    # zero-opportunity disclosure (D-14 frozen comparable + diagnostic)
    zero_opportunity: bool = True          # D-14: meaningful_dispatch == 0
    zero_dispatch_opportunity: bool = True  # alias of the D-14 metric
    zero_full_action_space_opportunity: bool = True  # incl. PM_IDLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "K": self.k_label, "K_hours": self.k_hours,
            "batch_index": self.batch_index,
            "legal_dispatch_decision_point_count": self.legal_dispatch_decision_points,
            "forced_wait_count": self.forced_wait,
            "strategic_wait_strict_count": self.strategic_strict,
            "strategic_wait_boundary_count": self.strategic_boundary,
            "strategic_wait_nonstrict_count": self.strategic_nonstrict,
            "raw_pm_age_eligible_count": self.raw_pm_age_eligible,
            "pm_with_head_count": self.pm_with_head,
            "pm_idle_count": self.pm_idle,
            "queue_empty_pm_idle_count": self.queue_empty_pm_idle,
            "queue_nonempty_no_legal_head_pm_idle_count": (
                self.queue_nonempty_no_legal_head_pm_idle),
            "maintenance_decision_point_count": self.maintenance_decision_points,
            "optional_pm_total_count": self.pm_with_head + self.pm_idle,
            "mandatory_replacement_count": self.mandatory_replacement,
            "mandatory_trigger_a_plus_d_gt_240_count": self.mandatory_a_plus_d_gt_240,
            "mandatory_trigger_post_completion_240_count": self.mandatory_post_completion_240,
            "mandatory_trigger_illegal_crossing_backstop_count": (
                self.mandatory_illegal_crossing_backstop),
            "mandatory_at_dispatch_diagnostic_count": self.mandatory_at_dispatch_diagnostic,
            "exact_240_count": self.exact_240,
            "both_wait_and_pm_count": self.both_wait_and_pm,
            "meaningful_h2_choice_point_count": self.meaningful_h2_choice,
            "zero_opportunity_batch": self.zero_opportunity,
            "zero_dispatch_opportunity_batch": self.zero_dispatch_opportunity,
            "zero_full_action_space_opportunity_batch": (
                self.zero_full_action_space_opportunity),
        }


def _maintenance_eligible(view: TimeIndexedView, rsrc: str, t: Fraction,
                          shift_end: Fraction, batch_size: int) -> bool:
    """Frozen MAINTENANCE_DECISION_POINT conditions (E1 section 9):
    resource idle/available (checked by caller), NO legal START_HEAD
    (caller distinguishes queue-empty vs no-legal-head), age in
    [120, 240) (>=120 optional-PM; >=240 is mandatory, not preventive),
    calibration fits the current shift, future potential demand at t."""
    age = equipment_age_at(view, rsrc, t)
    if age < MIN_PREVENTIVE_AGE_H:
        return False
    if age >= MANDATORY_AGE_H:
        return False  # mandatory due (a+d>240 / post-completion); not PM_IDLE
    cal = CALIBRATION_MINUTES[rsrc] / Fraction(60)
    if t + cal > shift_end:
        return False
    if not future_potential_demand_at(view, rsrc, t, batch_size):
        return False
    return True


def classify_batch_q3(event_log: list[dict[str, Any]], K: Fraction,
                      k_label: str, k_hours: str, batch_index: int,
                      durations: Optional[dict[str, Fraction]] = None,
                      batch_size: int = BATCH_SIZE) -> DensityBatchStats:
    """Classify H2 opportunity structure on one accepted Q3 Tier 1 batch
    with the time-indexed reconstruction (E1)."""
    dur = dict(durations if durations is not None else DEFAULT_DURATIONS_H)
    stats = DensityBatchStats(k_label=k_label, k_hours=k_hours,
                              batch_index=batch_index)
    view = build_time_index(event_log)
    shifts = q3_shift_grid(K)

    # --- DISPATCH_DECISION_POINT: anchored at ACTIVITY_START ---
    # (real legal dispatch is exactly the accepted ACTIVITY_START set;
    #  E1 does not change this side)
    for s, dev, proc, att, rsrc, _end in view.starts:
        sh = active_shift(shifts, s)
        if sh is None:
            continue
        stats.legal_dispatch_decision_points += 1
        d = dur[proc]
        latest_start = latest_legal_start(sh[1], d)
        completions = other_same_device_completions(view, s, dev)
        has_strict = any(c < latest_start for c in completions)
        has_boundary = any(c == latest_start for c in completions)
        has_nonstrict = any(c <= latest_start for c in completions)
        strategic_yes = has_strict or has_boundary
        if has_strict:
            stats.strategic_strict += 1
        if has_boundary:
            stats.strategic_boundary += 1
        if has_nonstrict:
            stats.strategic_nonstrict += 1
        age = equipment_age_at(view, rsrc, s)
        a_plus_d = age + d
        pm_head = False
        if a_plus_d > MANDATORY_AGE_H:
            # Engine never reaches this state (mandatory replaces FIRST);
            # reconstructed only as a diagnostic anomaly.
            stats.mandatory_at_dispatch_diagnostic += 1
        elif a_plus_d == MANDATORY_AGE_H:
            stats.exact_240 += 1
        else:
            if age >= MIN_PREVENTIVE_AGE_H:
                stats.raw_pm_age_eligible += 1
                cal = CALIBRATION_MINUTES[rsrc] / Fraction(60)
                if s + cal <= sh[1]:
                    stats.pm_with_head += 1
                    pm_head = True
        if strategic_yes and pm_head:
            stats.both_wait_and_pm += 1
        if strategic_yes or pm_head:
            stats.meaningful_h2_choice += 1

    # --- MANDATORY: from the frozen replacement event vocabulary ---
    # (F4: pre-start mandatory is NOT observable at ACTIVITY_START; the
    #  engine records EQUIPMENT_REPLACEMENT_START kind=mandatory_240 with
    #  the frozen trigger before the head could ever start)
    for _t0, _r, _cs, _ce, kind, trigger in view.replacements:
        if kind != REPLACEMENT_KIND_MANDATORY:
            continue
        stats.mandatory_replacement += 1
        if trigger == TRIGGER_A_PLUS_D_GT_240:
            stats.mandatory_a_plus_d_gt_240 += 1
        elif trigger == TRIGGER_POST_COMPLETION_240:
            stats.mandatory_post_completion_240 += 1
        elif trigger == TRIGGER_ILLEGAL_CROSSING_BACKSTOP:
            stats.mandatory_illegal_crossing_backstop += 1

    # --- MAINTENANCE / FORCED-WAIT at the reconstructed closure set ---
    # (E1 section 7/9/10: at most one decision point per (resource,
    #  closure); dispatch closures are anchored by their ACTIVITY_START)
    for t in closure_times(view, shifts):
        if t >= view.batch_end:
            continue
        sh = active_shift(shifts, t)
        if sh is None:
            continue
        for rsrc in RESOURCES:
            if rsrc in view.dispatch_at.get(t, ()):
                continue  # DISPATCH point at this closure (anchored at its
                          # ACTIVITY_START); one decision point per
                          # (resource, closure) -- never also maintenance
            if not resource_idle_at(view, rsrc, t):
                continue
            if not equipment_available_at(view, rsrc, t):
                continue
            head = fcfs_head_at(view, rsrc, t)
            if head is None:
                if _maintenance_eligible(view, rsrc, t, sh[1], batch_size):
                    stats.pm_idle += 1
                    stats.queue_empty_pm_idle += 1
                continue
            d_head = dur[head[1]]
            if head_is_legal_at(view, head, t, d_head, sh[1]):
                continue  # dispatch point (anchored at its ACTIVITY_START)
            stats.forced_wait += 1
            if _maintenance_eligible(view, rsrc, t, sh[1], batch_size):
                stats.pm_idle += 1
                stats.queue_nonempty_no_legal_head_pm_idle += 1

    stats.maintenance_decision_points = stats.pm_idle
    stats.zero_opportunity = stats.meaningful_h2_choice == 0
    stats.zero_dispatch_opportunity = stats.zero_opportunity
    stats.zero_full_action_space_opportunity = (
        stats.meaningful_h2_choice == 0 and stats.pm_idle == 0
    )
    return stats


# ---------------------------------------------------------------------------
# Aggregation (per K)
# ---------------------------------------------------------------------------


@dataclass
class DensityKAggregate:
    k_label: str
    k_hours: str
    n: int
    counts: dict[str, int]
    per_batch: dict[str, dict[str, float]]  # mean / median / min / max

    def to_dict(self) -> dict[str, Any]:
        return {
            "K": self.k_label, "K_hours": self.k_hours, "batches": self.n,
            "total_counts": self.counts,
            "per_batch": self.per_batch,
            "meaningful_choice_fraction": (
                self.counts["meaningful_h2_choice_point_count"]
                / self.counts["legal_dispatch_decision_point_count"]
                if self.counts["legal_dispatch_decision_point_count"] else 0.0
            ),
            "zero_opportunity_batch_fraction": (
                self.counts["zero_opportunity_batches"] / self.n if self.n else 0.0
            ),
            "zero_full_action_space_batch_fraction": (
                self.counts["zero_full_action_space_batches"] / self.n if self.n else 0.0
            ),
        }


def _stats_summ(vals: list[int]) -> dict[str, float]:
    n = len(vals)
    s = sorted(vals)
    return {
        "mean": sum(vals) / n if n else 0.0,
        "median": s[n // 2] if n else 0.0,
        "min": s[0] if n else 0.0,
        "max": s[-1] if n else 0.0,
    }


COUNT_KEYS = (
    "legal_dispatch_decision_point_count",
    "forced_wait_count",
    "strategic_wait_strict_count",
    "strategic_wait_boundary_count",
    "strategic_wait_nonstrict_count",
    "raw_pm_age_eligible_count",
    "pm_with_head_count",
    "pm_idle_count",
    "queue_empty_pm_idle_count",
    "queue_nonempty_no_legal_head_pm_idle_count",
    "maintenance_decision_point_count",
    "optional_pm_total_count",
    "mandatory_replacement_count",
    "mandatory_trigger_a_plus_d_gt_240_count",
    "mandatory_trigger_post_completion_240_count",
    "mandatory_trigger_illegal_crossing_backstop_count",
    "mandatory_at_dispatch_diagnostic_count",
    "exact_240_count",
    "both_wait_and_pm_count",
    "meaningful_h2_choice_point_count",
)


def aggregate_k(k_label: str, k_hours: str,
                batches: list[DensityBatchStats]) -> DensityKAggregate:
    n = len(batches)
    counts = {key: sum(b.to_dict()[key] for b in batches) for key in COUNT_KEYS}
    counts["zero_opportunity_batches"] = sum(1 for b in batches if b.zero_opportunity)
    counts["zero_full_action_space_batches"] = sum(
        1 for b in batches if b.zero_full_action_space_opportunity)
    per_batch = {
        key: _stats_summ([b.to_dict()[key] for b in batches]) for key in COUNT_KEYS
    }
    return DensityKAggregate(k_label=k_label, k_hours=k_hours, n=n,
                             counts=counts, per_batch=per_batch)
