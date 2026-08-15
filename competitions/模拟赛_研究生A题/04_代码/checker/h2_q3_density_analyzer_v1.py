#!/usr/bin/env python3
"""Q3 seven-K H2 opportunity-density analyzer (Density Gate; read-only).

Deterministic, offline, read-only classification of H2-relevant branch
opportunities on the ACCEPTED Q3 H1 Tier 1 worlds (single_test_unconditional
x 1h_literal x NO_PM_BEFORE_MANDATORY, seven K, 200 batches each).  It
reconstructs state from the event log only (no main-model dispatch calls, no
H2 action execution, no rollout, no policy selection).

Reuses the frozen reconstruction primitives of the accepted admission
analyzer (h2_admission_opportunity_analyzer_v1.build_view / head_candidate /
other_same_device_completions / _equipment_age_at / latest_legal_start) and
implements the Q3-specific layer on top:

  * Q3 two-shift K calendar (day d: [24d,24d+K), [24d+K,24d+2K), off
    [24d+2K,24(d+1))) for EVERY K;
  * DISPATCH_DECISION_POINT: anchored at each ACTIVITY_START (a legal head
    was dispatched) -- classify strategic WAIT (STRICT/BOUNDARY/NONSTRICT),
    optional PM_WITH_HEAD, both, meaningful;
  * MAINTENANCE_DECISION_POINT: at idle-transition instants (busy-end or
    shift-start wake within an active shift) where NO legal START_HEAD
    exists (queue empty OR queue nonempty but no legal head) and the frozen
    maintenance conditions hold (equipment idle/available, age >= 120,
    not mandatory, future potential demand, replacement+calibration fits
    the current shift) -- candidate PM_IDLE (PM-only).

Definitions follow Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED
sections 10/11/12/15 and D-14:
  STRICT:  t < e < latest_start ; BOUNDARY: e == latest_start (legal WAIT);
  NONSTRICT: t < e <= latest_start (measurement only);
  forced wait: head exists but not legally startable (measured separately;
    NEVER counted as strategic wait);
  optional PM: age >= 120, a+d < 240 (mandatory/exact_240 excluded),
    calibration fits the shift; pm_with_head at dispatch points, pm_idle at
    maintenance points;
  both: same DISPATCH point with legal strategic WAIT AND legal
    PM_WITH_HEAD (maintenance points are PM-only);
  meaningful: dispatch point with >= 1 optional branch
    (frozen admission-comparable definition); meaningful fraction =
    meaningful / legal_dispatch_decision_point_count (frozen denominator);
  zero-opportunity batch: meaningful_h2_choice_point_count == 0.

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

# Frozen constants / reconstruction primitives (reused from the accepted
# admission analyzer; identical semantics).
RESOURCES = adm.RESOURCES
PROCESS_ORDER = adm.PROCESS_ORDER
DEFAULT_DURATIONS_H = dict(adm.DEFAULT_DURATIONS_H)
CALIBRATION_MINUTES = adm.CALIBRATION_MINUTES
MIN_PREVENTIVE_AGE_H = adm.MIN_PREVENTIVE_AGE_H
MANDATORY_AGE_H = adm.MANDATORY_AGE_H
build_view = adm.build_view
is_idle = adm.is_idle
head_candidate = adm.head_candidate
other_same_device_completions = adm.other_same_device_completions
latest_legal_start = adm.latest_legal_start
_equipment_age_at = adm._equipment_age_at

BATCH_SIZE = 100  # P040 (frozen Q3 batch)


def frac(value: Any) -> Fraction:
    return Fraction(value)


# ---------------------------------------------------------------------------
# Q3 two-shift K calendar
# ---------------------------------------------------------------------------


def q3_shift_grid(K: Fraction) -> list[tuple[Fraction, Fraction]]:
    """Day d: shift 1=[24d, 24d+K), shift 2=[24d+K, 24d+2K), off
    [24d+2K, 24(d+1)).  Horizon 400 days is far beyond any 100-device Q3
    batch (a batch ends well inside the calendar)."""
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
# Q3 decision-point classification
# ---------------------------------------------------------------------------


@dataclass
class DensityBatchStats:
    k_label: str
    k_hours: str
    batch_index: int
    legal_dispatch_decision_points: int = 0
    forced_wait: int = 0
    strategic_strict: int = 0
    strategic_boundary: int = 0
    strategic_nonstrict: int = 0
    raw_pm_age_eligible: int = 0
    pm_with_head: int = 0
    pm_idle: int = 0
    mandatory_replacement: int = 0
    exact_240: int = 0
    both_wait_and_pm: int = 0
    meaningful_h2_choice: int = 0
    zero_opportunity: bool = True

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
            "optional_pm_total_count": self.pm_with_head + self.pm_idle,
            "mandatory_replacement_count": self.mandatory_replacement,
            "exact_240_count": self.exact_240,
            "both_wait_and_pm_count": self.both_wait_and_pm,
            "meaningful_h2_choice_point_count": self.meaningful_h2_choice,
            "zero_opportunity_batch": self.zero_opportunity,
        }


def _head_is_legal(view: adm.BatchLogView, head: tuple[int, str, int],
                   t: Fraction, d: Fraction, shift_end: Fraction) -> bool:
    dev, proc, att = head
    if proc == "E":
        if not (view.proc_passed.get((dev, "A"))
                and view.proc_passed.get((dev, "B"))
                and view.proc_passed.get((dev, "C"))):
            return False
    return t + d <= shift_end


def _future_potential_demand(view: adm.BatchLogView, process: str,
                             batch_size: int = BATCH_SIZE) -> bool:
    """Frozen condition: the batch still has a non-terminal device that may
    need this resource -- either an entered non-terminal device that has not
    yet validly passed this process, or a device not yet entered (the batch
    is batch_size devices)."""
    entered = set(view.device_entry.keys())
    terminals = {dev for _t, dev, _s in view.terminals}
    for dev in entered - terminals:
        if not view.proc_passed.get((dev, process)):
            return True
    if len(entered) < batch_size:
        return True
    return False


def classify_batch_q3(event_log: list[dict[str, Any]], K: Fraction,
                      k_label: str, k_hours: str, batch_index: int,
                      durations: Optional[dict[str, Fraction]] = None,
                      batch_size: int = BATCH_SIZE) -> DensityBatchStats:
    """Classify H2 opportunity structure on one accepted Q3 Tier 1 batch.

    DISPATCH points are anchored at ACTIVITY_START (a legal head was
    dispatched by the frozen H1 rules at that instant).  MAINTENANCE points
    are enumerated at idle-transition instants (busy-end or shift-start wake
    within an active shift, before the batch end) with no legal START_HEAD.
    """
    dur = dict(durations if durations is not None else DEFAULT_DURATIONS_H)
    stats = DensityBatchStats(k_label=k_label, k_hours=k_hours,
                              batch_index=batch_index)
    view = build_view(event_log)
    shifts = q3_shift_grid(K)
    terminals = [t for t, _d, _s in view.terminals]
    batch_end = max(terminals) if terminals else max(
        (frac(r.get("event_time")) for r in event_log if r.get("event_time")), default=Fraction(0)
    )

    # --- DISPATCH_DECISION_POINT: anchored at ACTIVITY_START ---
    for st_time, dev, proc, att, rsrc in view.starts:
        sh = active_shift(shifts, st_time)
        if sh is None:
            continue
        stats.legal_dispatch_decision_points += 1
        d = dur[proc]
        latest_start = latest_legal_start(sh[1], d)
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
        age = _equipment_age_at(view, rsrc, st_time)
        a_plus_d = age + d
        pm_head = False
        if a_plus_d > MANDATORY_AGE_H:
            stats.mandatory_replacement += 1
        elif a_plus_d == MANDATORY_AGE_H:
            stats.exact_240 += 1
        else:
            if age >= MIN_PREVENTIVE_AGE_H:
                stats.raw_pm_age_eligible += 1
                cal = CALIBRATION_MINUTES[rsrc] / Fraction(60)
                if st_time + cal <= sh[1]:
                    stats.pm_with_head += 1
                    pm_head = True
        if strategic_yes and pm_head:
            stats.both_wait_and_pm += 1
        if strategic_yes or pm_head:
            stats.meaningful_h2_choice += 1

    # --- MAINTENANCE_DECISION_POINT: idle transitions with no legal head ---
    for rsrc in RESOURCES:
        idle_instants: set[Fraction] = set()
        for s, e, _k in view.busy.get(rsrc, []):
            idle_instants.add(e)
        for s, e in shifts:
            idle_instants.add(s)
        for t in sorted(idle_instants):
            if t >= batch_end:
                continue
            sh = active_shift(shifts, t)
            if sh is None:
                continue
            if not is_idle(view, rsrc, t):
                continue
            head = head_candidate(view, rsrc, t)
            if head is not None:
                d_head = dur[head[1]]
                if _head_is_legal(view, head, t, d_head, sh[1]):
                    continue  # dispatch point (anchored at its ACTIVITY_START)
                stats.forced_wait += 1
                # not a maintenance point if the waiting head triggers
                # mandatory replacement (a+d > 240) or exact_240
                age_h = _equipment_age_at(view, rsrc, t)
                if age_h + d_head > MANDATORY_AGE_H:
                    continue
                if age_h + d_head == MANDATORY_AGE_H:
                    stats.exact_240 += 1
                    continue
            # maintenance eligibility (PM_IDLE candidate)
            age = _equipment_age_at(view, rsrc, t)
            if age < MIN_PREVENTIVE_AGE_H:
                continue
            cal = CALIBRATION_MINUTES[rsrc] / Fraction(60)
            if t + cal > sh[1]:
                continue
            if not _future_potential_demand(view, rsrc, batch_size):
                continue
            stats.pm_idle += 1

    stats.zero_opportunity = stats.meaningful_h2_choice == 0
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
    "optional_pm_total_count",
    "mandatory_replacement_count",
    "exact_240_count",
    "both_wait_and_pm_count",
    "meaningful_h2_choice_point_count",
)


def aggregate_k(k_label: str, k_hours: str,
                batches: list[DensityBatchStats]) -> DensityKAggregate:
    n = len(batches)
    counts = {key: sum(b.to_dict()[key] for b in batches) for key in COUNT_KEYS}
    counts["zero_opportunity_batches"] = sum(1 for b in batches if b.zero_opportunity)
    per_batch = {
        key: _stats_summ([b.to_dict()[key] for b in batches]) for key in COUNT_KEYS
    }
    return DensityKAggregate(k_label=k_label, k_hours=k_hours, n=n,
                             counts=counts, per_batch=per_batch)
