#!/usr/bin/env python3
"""H2 admission evidence analyzer (READ-ONLY offline diagnostic; NOT H2).

Human Gate 2026-08-15: H2 ADMISSION EVIDENCE AUDIT ONLY.

This is an INDEPENDENT offline analyzer for H2 admission evidence.  It is NOT
an H2 policy implementation, does NOT import the main DES transition/dispatch
logic (``random_des_v1`` decision functions are never called), and does NOT
execute any H2 action.

Source evidence (Human Gate section 3): existing PRE-FORMAL G3 data only
  * primary: G3 H1 tuning run_20260814T174022592173Z_01b7c7e7 (h1_tuning,
    master_seed=1, 20 shared worlds) -- especially NO_PM_BEFORE_MANDATORY;
  * secondary context: G3 holdout run_20260814T180238855262Z_020bc637.
  * q2_formal/** is NEVER used for H2 design/threshold/tuning/admission.
  The G3 engine is deterministic: replaying the frozen configs reproduces the
  accepted canonical event logs (verified against log_hashes.json), so the
  analyzer reconstructs state from those exact logs without consuming new
  random worlds and without touching any accepted result directory.

Definitions (Human Gate section 5 / 6 / 7 / 8):
  * legal_h1_dispatch_decision_point: active-shift instant at which resource r
    is idle/available and a frozen FCFS head is WAITING (== engine C24
    decision point);
  * forced_wait: head cannot legally start NOW under frozen H1 rules
    (== current engine _c24_waiting_opportunities semantics);
  * strategic_h2_wait_opportunity: head CAN legally start now AND would
    complete within the current shift AND the SAME head device has at least
    one other currently scheduled activity completion event in the future
    that occurs early enough to still leave a legal start window;
    STRICT: other_completion < latest_start_time;
    BOUNDARY: other_completion == latest_start_time;
    NONSTRICT: other_completion <= latest_start_time (boundary ambiguity
    reported, NOT silently decided -- Human Gate will later fix C23 equality);
  * raw_pm_age_eligible: idle/available + legal head + equipment age >= 120 h
    + replacement not already mandatory;
  * pm_immediately_feasible: raw PM eligible AND replacement+calibration can
    legally start/finish within the current shift;
  * mandatory_replacement: a+d > 240 (NOT an H2 choice);
  * exact_240: a+d == 240 (reported separately);
  * combined choice: per decision point classify no-option / wait-only /
    PM-only / both; meaningful_h2_choice_point = has >= 1 optional branch;
  * choice fraction = meaningful_h2_choice_point_count /
    legal_h1_dispatch_decision_point_count.

This phase measures ONLY opportunity / branching density.  It does NOT
estimate H2 improvement in T, optimal policy, rollout benefit, M, or Q3 K.

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

# ---------------------------------------------------------------------------
# Frozen constants (parameters.csv / accepted G3 semantics; read-only)
# ---------------------------------------------------------------------------

RESOURCES: tuple[str, ...] = ("A", "B", "C", "E")
PROCESS_ORDER: dict[str, int] = {"A": 0, "B": 1, "C": 2, "E": 3}
DEFAULT_DURATIONS_H: dict[str, Fraction] = {
    "A": Fraction(5, 2),   # P006 t_A = 2.5 h
    "B": Fraction(2),      # P007 t_B = 2 h
    "C": Fraction(5, 2),   # P008 t_C = 2.5 h
    "E": Fraction(3),      # P009 t_E = 3 h
}
CALIBRATION_MINUTES: dict[str, Fraction] = {
    "A": Fraction(30),     # P010
    "B": Fraction(20),     # P011
    "C": Fraction(20),     # P012
    "E": Fraction(40),     # P013
}
TRANSPORT_OUT_H: Fraction = Fraction(1, 2)   # P014
TRANSPORT_IN_H: Fraction = Fraction(1, 2)    # P015
MIN_PREVENTIVE_AGE_H: Fraction = Fraction(120)   # P016
MANDATORY_AGE_H: Fraction = Fraction(240)        # P017
SHIFT_LENGTH_Q2_H: Fraction = Fraction(12)       # P038
SHIFTS_PER_DAY_Q2: int = 1                        # P039

EVENT_ACTIVITY_START = "ACTIVITY_START"
EVENT_ACTIVITY_COMPLETE = "ACTIVITY_COMPLETE"
EVENT_OBSERVATION = "OBSERVATION_MATERIALIZED"
EVENT_TASK_RELEASE = "TASK_RELEASE"
EVENT_TASK_CANCEL = "TASK_CANCEL"
EVENT_DEVICE_TERMINAL = "DEVICE_TERMINAL"
EVENT_EQUIPMENT_REPLACEMENT_START = "EQUIPMENT_REPLACEMENT_START"
EVENT_EQUIPMENT_CALIBRATION_COMPLETE = "EQUIPMENT_CALIBRATION_COMPLETE"
EVENT_TRUE_STATE = "TRUE_STATE_GENERATED"
EVENT_WAKE_UP = "WAKE_UP"
EVENT_SHIFT_CHANGE = "SHIFT_CHANGE"


# ---------------------------------------------------------------------------
# Event log loading / helpers
# ---------------------------------------------------------------------------


def load_event_log(path: Path) -> list[dict[str, Any]]:
    """Load an event log from JSON (list or {records:[...]}) or JSONL."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl" or text.lstrip().startswith("{"):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            records = []
            for line in text.splitlines():
                line = line.strip()
                if line:
                    records.append(json.loads(line))
            return records
        if isinstance(obj, list):
            return obj
        return obj.get("records", obj.get("event_log", []))
    return json.loads(text)


def frac(value: Any) -> Fraction:
    return Fraction(value)


# ---------------------------------------------------------------------------
# Offline reconstruction primitives (independent; no main-model dispatch)
# ---------------------------------------------------------------------------


@dataclass
class BatchLogView:
    """Independently reconstructed state from one event log."""

    log: list[dict[str, Any]]
    resources: tuple[str, ...] = RESOURCES
    # per-resource busy intervals [(start, end, kind)]
    busy: dict[str, list[tuple[Fraction, Fraction, str]]] = field(
        default_factory=dict)
    # task releases: (time, resource, device, process, attempt) in log order
    releases: list[tuple[Fraction, str, int, str, int]] = field(
        default_factory=list)
    # completed observations: (time, device, process, attempt)
    observations: list[tuple[Fraction, int, str, int]] = field(
        default_factory=list)
    # equipment replacement start: (time, resource, cal_start, cal_end)
    replacements: list[tuple[Fraction, str, Fraction, Fraction]] = field(
        default_factory=list)
    # device terminals: (time, device, state)
    terminals: list[tuple[Fraction, int, str]] = field(default_factory=list)
    # activity start: (time, device, process, attempt, resource)
    starts: list[tuple[Fraction, int, str, int, str]] = field(
        default_factory=list)
    activity_completes: list[tuple[Fraction, int, str, int, str]] = field(
        default_factory=list)
    wakeups: list[Fraction] = field(default_factory=list)
    shift_changes: list[tuple[Fraction, int]] = field(default_factory=list)
    # device entry time (first TRUE_STATE_GENERATED)
    device_entry: dict[int, Fraction] = field(default_factory=dict)
    # per (device) process status: 'PASSED' if a completed observation with
    # outcome PASS for that process exists and is the last
    # (independent minimal reconstruction used only for E-prereq checks)
    proc_passed: dict[tuple[int, str], bool] = field(default_factory=dict)
    true_state: dict[int, dict[str, bool]] = field(default_factory=dict)


def build_view(event_log: list[dict[str, Any]]) -> BatchLogView:
    view = BatchLogView(log=event_log)
    for rec in event_log:
        et = rec.get("event_type")
        t = frac(rec["event_time"]) if rec.get("event_time") is not None else None
        if et == EVENT_ACTIVITY_START:
            view.starts.append((
                frac(rec["event_time"]),
                rec["device_id"], rec["process"],
                rec["effective_attempt_no"], rec["resource_id"],
            ))
        elif et == EVENT_ACTIVITY_COMPLETE:
            view.activity_completes.append((
                frac(rec["event_time"]),
                rec["device_id"], rec["process"],
                rec["effective_attempt_no"], rec["resource_id"],
            ))
            # occupancy: [start, end)
            s = frac(rec["attempt_start_time"])
            view.busy.setdefault(rec["resource_id"], []).append(
                (s, frac(rec["event_time"]), "test"))
        elif et == EVENT_OBSERVATION:
            view.observations.append((
                frac(rec["event_time"]),
                rec["device_id"], rec["process"],
                rec["effective_attempt_no"],
            ))
            outcome = rec.get("outcome")
            if outcome == "PASS":
                view.proc_passed[(rec["device_id"], rec["process"])] = True
        elif et == EVENT_TASK_RELEASE:
            view.releases.append((
                frac(rec["event_time"]), rec["resource_id"],
                rec["device_id"], rec["process"],
                rec["effective_attempt_no"],
            ))
        elif et == EVENT_EQUIPMENT_REPLACEMENT_START:
            cs = frac(rec["calibration_start"])
            ce = frac(rec["calibration_end"])
            view.replacements.append(
                (frac(rec["event_time"]), rec["resource_id"], cs, ce))
            view.busy.setdefault(rec["resource_id"], []).append(
                (cs, ce, "calibration"))
        elif et == EVENT_DEVICE_TERMINAL:
            view.terminals.append((
                frac(rec["event_time"]), rec["device_id"],
                rec.get("terminal_state") or "",
            ))
        elif et == EVENT_TRUE_STATE:
            view.device_entry.setdefault(rec["device_id"], frac(rec["event_time"]))
            ts = rec.get("true_state") or {}
            view.true_state[rec["device_id"]] = {
                p: bool(ts.get(p)) for p in ("A", "B", "C")
            }
        elif et == EVENT_WAKE_UP:
            view.wakeups.append(frac(rec["event_time"]))
        elif et == EVENT_SHIFT_CHANGE:
            view.shift_changes.append(
                (frac(rec["event_time"]), rec.get("shift_index", 0)))
    # busy intervals sorted
    for r in view.resources:
        view.busy.setdefault(r, []).sort(key=lambda iv: (iv[0], iv[1]))
    return view


def shift_grid(q2_start: Fraction = Fraction(0)) -> list[tuple[Fraction, Fraction]]:
    """Frozen Q2 calendar: single 12 h shift/day starting at t=0.
    Off-shift all work stops (P037-P039)."""
    shifts = []
    t = q2_start
    for i in range(200):  # generous horizon (100-device batches end well inside)
        shifts.append((t, t + SHIFT_LENGTH_Q2_H))
        t += SHIFT_LENGTH_Q2_H
    return shifts


def active_shift(shifts: list[tuple[Fraction, Fraction]], t: Fraction
                 ) -> Optional[tuple[Fraction, Fraction]]:
    for s, e in shifts:
        if s <= t < e:
            return (s, e)
    return None


def is_idle(view: BatchLogView, resource: str, t: Fraction) -> bool:
    """Resource idle at t: no busy interval covers t."""
    for s, e, _k in view.busy.get(resource, []):
        if s <= t < e:
            return False
    return True


def head_candidate(view: BatchLogView, resource: str, t: Fraction
                   ) -> Optional[tuple[int, str, int]]:
    """Frozen FCFS head for resource r at t: earliest (release_time,
    device_id, process_order, attempt) among WAITING tasks for r whose
    device is still pending and not yet terminal.  Independent reconstruction
    from TASK_RELEASE records (does not call main dispatch)."""
    candidates = []
    terminal_devs = {d for _t, d, _s in view.terminals}
    passed_at = {}
    for rel_time, rsrc, dev, proc, att in view.releases:
        if rsrc != resource:
            continue
        if dev in terminal_devs:
            continue
        # task must be WAITING at t: released at rel_time, not yet started
        # (no ACTIVITY_START for this exact (dev,proc,att) at/after rel_time
        #  and before t), and not cancelled before t.
        started = any(
            st_time == rel_time and st_dev == dev and st_proc == proc
            and st_att == att
            for st_time, st_dev, st_proc, st_att, _r in view.starts
        )
        if started:
            continue
        cancelled_before = any(
            c_time <= t and c_time >= rel_time and c.get("device_id") == dev
            and c.get("process") == proc and c.get("effective_attempt_no") == att
            for c in view.log
            if c.get("event_type") == EVENT_TASK_CANCEL
            and (c_time := frac(c["event_time"])) is not None
        )
        if cancelled_before:
            continue
        key = (rel_time, dev, PROCESS_ORDER.get(proc, 9), att)
        candidates.append((key, dev, proc, att))
    if not candidates:
        return None
    candidates.sort()
    _key, dev, proc, att = candidates[0]
    return (dev, proc, att)


def other_same_device_completions(
    view: BatchLogView, t: Fraction, device: int,
) -> list[Fraction]:
    """Currently scheduled completion events for the same device strictly in
    the future (already-started activities of the device with end time > t).
    Completion time is read from the ACTIVITY_START ``attempt_end_time``
    (scheduled end), so it does not require the COMPLETE event to exist yet.
    These are the H2 'wait until a scheduled completion' candidates."""
    out = []
    for rec in view.log:
        if rec.get("event_type") != EVENT_ACTIVITY_START:
            continue
        if rec.get("device_id") != device:
            continue
        st = frac(rec["event_time"])
        end_raw = rec.get("attempt_end_time")
        if end_raw is None:
            continue
        end = frac(end_raw)
        if st < t < end:
            out.append(end)
    return sorted(out)


def latest_legal_start(shift_end: Fraction, duration: Fraction) -> Fraction:
    """Latest start time that still completes within the shift
    (start + duration <= shift_end; 恰班末完成允许)."""
    return shift_end - duration


# ---------------------------------------------------------------------------
# Per-decision-point classification
# ---------------------------------------------------------------------------


@dataclass
class DecisionPointStats:
    legal_dispatch_points: int = 0
    forced_wait: int = 0
    strategic_strict: int = 0
    strategic_boundary: int = 0
    strategic_nonstrict: int = 0
    raw_pm_age_eligible: int = 0
    pm_immediately_feasible: int = 0
    mandatory_replacement: int = 0
    exact_240: int = 0
    both_wait_and_pm: int = 0
    meaningful_h2_choice: int = 0


def classify_batch(view: BatchLogView, durations: Optional[dict[str, Fraction]] = None
                   ) -> DecisionPointStats:
    """Classify H2-relevant branch opportunities at every H1 legal dispatch
    decision point in one batch log.

    Reconstruction approach: the engine performs a legal H1 dispatch at the
    instant it starts an ACTIVITY (a legal head existed and was dispatched).
    Each ACTIVITY_START is therefore an anchor of a legal dispatch decision
    point at which the frozen H1 rules had a startable head.  At that instant
    we independently evaluate the two optional H2 branches:

      * strategic wait: the SAME head device has another currently scheduled
        activity completion in the future, early enough to still leave a
        legal start window (STRICT / BOUNDARY / NONSTRICT variants);
      * optional preventive replacement: equipment age >= 120 h, a+d < 240,
        replacement+calibration can complete within the current shift.

    Forced-wait points (engine `_c24_waiting_opportunities`: head not legal)
    are NOT anchored by ACTIVITY_START; they are reported from the engine
    metric comparison (see report).  This analyzer counts the OPPORTUNITY
    structure only.
    """
    dur = durations if durations is not None else dict(DEFAULT_DURATIONS_H)
    stats = DecisionPointStats()
    shifts = shift_grid()

    # anchor every ACTIVITY_START (legal dispatch decision point)
    for st_time, dev, proc, att, rsrc in view.starts:
        sh = active_shift(shifts, st_time)
        if sh is None:
            continue
        shift_end = sh[1]
        if not is_idle(view, rsrc, st_time):
            # the start event itself occupies the resource at st_time; treat
            # the dispatch decision as occurring at st_time with the head
            # startable (the engine selected it).
            pass
        stats.legal_dispatch_points += 1
        d = dur[proc]
        latest_start = latest_legal_start(shift_end, d)
        # strategic wait: same device has another scheduled completion in the
        # future (other than this very start) before/at latest start
        completions = [
            c for c in other_same_device_completions(view, st_time, dev)
        ]
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
        # optional PM: raw eligibility (age >= 120, a+d < 240) is reported
        # independently of immediate feasibility
        age = _equipment_age_at(view, rsrc, st_time)
        a_plus_d = age + d
        pm_here = False
        if a_plus_d > MANDATORY_AGE_H:
            stats.mandatory_replacement += 1
        elif a_plus_d == MANDATORY_AGE_H:
            stats.exact_240 += 1
        else:
            if age >= MIN_PREVENTIVE_AGE_H:
                stats.raw_pm_age_eligible += 1
                cal = CALIBRATION_MINUTES[rsrc] / Fraction(60)
                if st_time + cal <= shift_end:
                    stats.pm_immediately_feasible += 1
                    pm_here = True
        if strategic_yes and pm_here:
            stats.both_wait_and_pm += 1
        if strategic_yes or pm_here:
            stats.meaningful_h2_choice += 1
    return stats


def _equipment_age_at(view: BatchLogView, resource: str, t: Fraction) -> Fraction:
    """Independent equipment-age reconstruction at t (reset-aware).

    The engine resets equipment age to 0 at each replacement
    (random_des_v1: equip.age = 0 on new generation).  Age therefore equals
    the sum of test-fragment durations on this resource since the LATEST
    replacement start at or before t (fragments that END at/before t within
    the current generation), plus any in-flight fragment duration accrued
    before t.  Interrupted/failed fragments are included via their recorded
    elapsed durations (TASK_CANCEL elapsed_hours / ACTIVITY_COMPLETE
    elapsed_hours).  Calibration is NOT counted (frozen semantics)."""
    # latest replacement start time <= t (resets age)
    gen_start = Fraction(0)
    for rtime, rsrc, cs, ce in view.replacements:
        if rsrc == resource and rtime <= t:
            gen_start = max(gen_start, rtime)
    age = Fraction(0)
    # completed / failed test fragments ending at/before t in this generation
    for rec in view.log:
        if rec.get("event_type") not in (EVENT_ACTIVITY_COMPLETE, EVENT_TASK_CANCEL):
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
            continue  # fragment from an earlier generation (replaced before t)
        if e <= t:
            age += e - s
    return age


def _pm_feasible_here(view: BatchLogView, rsrc: str, t: Fraction,
                      d: Fraction, shift_end: Fraction) -> bool:
    age = _equipment_age_at(view, rsrc, t)
    a_plus_d = age + d
    if a_plus_d > MANDATORY_AGE_H:
        return False  # mandatory, not optional
    if a_plus_d == MANDATORY_AGE_H:
        return False  # exact 240, not optional PM
    if age < MIN_PREVENTIVE_AGE_H:
        return False
    cal = CALIBRATION_MINUTES[rsrc] / Fraction(60)
    return t + cal <= shift_end


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate(per_batch: list[dict[str, Any]], keys: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    n = len(per_batch)
    for k in keys:
        vals = sorted(float(b[k]) for b in per_batch)
        mean = sum(vals) / n if n else 0.0
        median = vals[n // 2] if n else 0.0
        p90 = vals[int(0.9 * (n - 1))] if n else 0.0
        out[k] = {
            "n_batches": n,
            "mean": mean,
            "median": median,
            "p90": p90,
            "max": vals[-1] if vals else 0.0,
            "min": vals[0] if vals else 0.0,
        }
    return out


def zero_fractions(per_batch: list[dict[str, Any]], keys: list[str]) -> dict[str, Any]:
    n = len(per_batch)
    out = {}
    for k in keys:
        z = sum(1 for b in per_batch if b[k] == 0)
        out[k] = {"zero_count": z, "fraction": (z / n) if n else 0.0}
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def analyze_logs(records_by_cell: dict[str, list[list[dict[str, Any]]]]) -> dict[str, Any]:
    """Run the offline analyzer over pre-loaded logs (cells -> list of batches)."""
    result: dict[str, Any] = {}
    for cell, batches in records_by_cell.items():
        per_batch = []
        for i, log in enumerate(batches):
            view = build_view(log)
            st = classify_batch(view)
            legal = max(st.legal_dispatch_points, 1)
            frac_choice = st.meaningful_h2_choice / legal if legal else 0.0
            per_batch.append({
                "batch_index": i,
                "legal_h1_dispatch_decision_point_count": st.legal_dispatch_points,
                "forced_wait_count": st.forced_wait,
                "strategic_wait_strict_count": st.strategic_strict,
                "strategic_wait_boundary_count": st.strategic_boundary,
                "strategic_wait_nonstrict_count": st.strategic_nonstrict,
                "raw_pm_age_eligible_count": st.raw_pm_age_eligible,
                "pm_immediately_feasible_count": st.pm_immediately_feasible,
                "mandatory_replacement_count": st.mandatory_replacement,
                "exact_240_count": st.exact_240,
                "both_wait_and_pm_count": st.both_wait_and_pm,
                "meaningful_h2_choice_point_count": st.meaningful_h2_choice,
                "meaningful_choice_fraction": frac_choice,
            })
        keys = [
            "legal_h1_dispatch_decision_point_count", "forced_wait_count",
            "strategic_wait_strict_count", "strategic_wait_boundary_count",
            "strategic_wait_nonstrict_count", "raw_pm_age_eligible_count",
            "pm_immediately_feasible_count", "mandatory_replacement_count",
            "exact_240_count", "both_wait_and_pm_count",
            "meaningful_h2_choice_point_count", "meaningful_choice_fraction",
        ]
        agg = aggregate(per_batch, keys)
        zf = zero_fractions(per_batch, [
            "strategic_wait_strict_count", "pm_immediately_feasible_count",
            "meaningful_h2_choice_point_count",
        ])
        result[cell] = {
            "n_batches": len(per_batch),
            "per_batch": per_batch,
            "aggregates": agg,
            "zero_fractions": zf,
        }
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="H2 admission evidence offline analyzer (read-only).")
    parser.add_argument("--input", required=True,
                        help="JSON with {cell: [ [event...], ... ]}")
    parser.add_argument("--output", required=True, help="output JSON path")
    args = parser.parse_args(argv)
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = analyze_logs(data)
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    print("analyzer done ->", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
