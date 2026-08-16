#!/usr/bin/env python3
"""Q3-H2-P3-B parameterized online evaluation-quota selector (SPEC 2 / D-08,
frozen).

Per batch (online, causal):
  * C_eval parameterized (supports 6 and 8);
  * W_cap = ceil(C_eval/2), P_cap = floor(C_eval/2)
    (C_eval=6 -> W=3,P=3; C_eval=8 -> W=4,P=4);
  * every H2-eligible decision point gets EXACTLY ONE quota class:
      - both (wait-legal AND PM-legal)  -> WAIT (wait classification wins);
      - wait-legal only                 -> WAIT;
      - PM-legal only                   -> PM-only;
      - maintenance points are naturally PM-only (no wait action);
    quota class != action availability (a both point keeps its legal PM
    action);
  * WAIT side: online first W_cap wait-class points by decision time;
    reaching the cap stops further wait rollouts; no future-PM lookahead, no
    batch-end backfill, no borrowing from the PM side;
  * PM side (no post-hoc backfill): age buckets B1=[120,160), B2=[160,200),
    B3=[200,240); each bucket's FIRST PM-only point occupies its
    bucket-first slot; when P_cap==4 there is EXACTLY ONE extra PM slot
    taken by the first LATER PM-only point whose bucket-first slot is
    already used and whose PM cap is not yet exhausted; P_cap==3 has NO
    extra slot; missing buckets expire unused; no cross-bucket backfill, no
    retroactive selection, no future-bucket lookahead;
  * selected_for_rollout(t) depends ONLY on history <= t and the current
    quota state (causality, verified by the checker);
  * invariants: wait_selected <= W_cap, PM_selected <= P_cap,
    selected_total <= C_eval; no duplicate decision point.

Pure stdlib; no live-DES imports (C23 isolation).

Python 3.12, standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Optional

# frozen age buckets (SPEC 2 / D-08)
PM_BUCKETS: tuple[tuple[Fraction, Fraction], ...] = (
    (Fraction(120), Fraction(160)),
    (Fraction(160), Fraction(200)),
    (Fraction(200), Fraction(240)),
)

# quota classes
WAIT_CLASS = "WAIT"
PM_CLASS = "PM"


@dataclass(frozen=True)
class DecisionPointEvent:
    """The online event view of one H2-eligible decision point."""
    dp: int
    time: Fraction
    resource: str
    kind: str                 # "dispatch" | "maintenance"
    wait_legal: bool
    pm_legal: bool            # PM_WITH_HEAD (dispatch) or PM_IDLE (maint)
    age_h: Fraction           # resource equipment age at the point
    head: Optional[tuple[int, str, int]] = None

    @property
    def quota_class(self) -> str:
        return WAIT_CLASS if self.wait_legal else PM_CLASS

    @property
    def is_both(self) -> bool:
        return self.wait_legal and self.pm_legal


@dataclass
class QuotaState:
    """Online quota state (mutated as points are processed in time order)."""
    c_eval: int
    w_cap: int
    p_cap: int
    wait_selected: int = 0
    pm_selected: int = 0
    bucket_used: dict[int, bool] = field(
        default_factory=lambda: {0: False, 1: False, 2: False})
    extra_slot_used: bool = False
    extra_slot_available: bool = False  # P_cap==4 -> True
    selected_dps: list[int] = field(default_factory=list)

    def __init__(self, c_eval: int):
        if c_eval not in (6, 8):
            raise ValueError(f"C_eval must be 6 or 8 (frozen), got {c_eval}")
        self.c_eval = c_eval
        self.w_cap = (c_eval + 1) // 2
        self.p_cap = c_eval // 2
        self.wait_selected = 0
        self.pm_selected = 0
        self.bucket_used = {0: False, 1: False, 2: False}
        self.extra_slot_used = False
        self.extra_slot_available = (c_eval == 8)  # P_cap=4 -> 1 extra
        self.selected_dps = []

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "c_eval": self.c_eval, "w_cap": self.w_cap, "p_cap": self.p_cap,
            "wait_selected": self.wait_selected,
            "pm_selected": self.pm_selected,
            "bucket_used": self.bucket_used,
            "extra_slot_used": self.extra_slot_used,
            "extra_slot_available": self.extra_slot_available,
            "selected_dps": self.selected_dps,
        }


def _bucket_index(age_h: Fraction) -> Optional[int]:
    for i, (lo, hi) in enumerate(PM_BUCKETS):
        if lo <= age_h < hi:
            return i
    return None


def select_point(state: QuotaState, point: DecisionPointEvent
                 ) -> tuple[bool, str, QuotaState]:
    """Online selection for one decision point (pure function of history <= t
    + quota state).  Returns (selected, quota_class, next_state)."""
    cls = point.quota_class
    if point.dp in state.selected_dps:
        raise ValueError(f"duplicate decision point dp={point.dp}")
    if cls == WAIT_CLASS:
        if state.wait_selected < state.w_cap:
            ns = _copy_state(state)
            ns.wait_selected += 1
            ns.selected_dps.append(point.dp)
            return True, cls, ns
        return False, cls, state
    # PM-only
    bi = _bucket_index(point.age_h)
    if bi is None:
        # age outside [120,240) cannot be a PM point by construction
        return False, cls, state
    if not state.bucket_used[bi]:
        ns = _copy_state(state)
        ns.bucket_used[bi] = True
        ns.pm_selected += 1
        ns.selected_dps.append(point.dp)
        return True, cls, ns
    if (state.extra_slot_available and not state.extra_slot_used
            and state.pm_selected < state.p_cap):
        ns = _copy_state(state)
        ns.extra_slot_used = True
        ns.pm_selected += 1
        ns.selected_dps.append(point.dp)
        return True, cls, ns
    return False, cls, state


def _copy_state(s: QuotaState) -> QuotaState:
    ns = QuotaState(s.c_eval)
    ns.wait_selected = s.wait_selected
    ns.pm_selected = s.pm_selected
    ns.bucket_used = dict(s.bucket_used)
    ns.extra_slot_used = s.extra_slot_used
    ns.selected_dps = list(s.selected_dps)
    return ns


def run_online_selection(c_eval: int,
                         points: list[DecisionPointEvent]
                         ) -> dict[str, Any]:
    """Process the batch's eligible decision points IN TIME ORDER (frozen
    online rule) and return the selection summary + final quota state."""
    state = QuotaState(c_eval)
    ordered = sorted(points, key=lambda p: (p.time, p.resource, p.dp))
    rows: list[dict[str, Any]] = []
    for p in ordered:
        selected, cls, state = select_point(state, p)
        rows.append({
            "dp": p.dp, "time": str(p.time), "resource": p.resource,
            "kind": p.kind, "quota_class": cls, "is_both": p.is_both,
            "wait_legal": p.wait_legal, "pm_legal": p.pm_legal,
            "age_h": str(p.age_h), "selected_for_rollout": selected,
            "state_after": state.to_canonical_dict()})
    return {
        "c_eval": c_eval, "w_cap": state.w_cap, "p_cap": state.p_cap,
        "wait_selected": state.wait_selected,
        "pm_selected": state.pm_selected,
        "selected_total": len(state.selected_dps),
        "selected_dps": state.selected_dps,
        "rows": rows,
    }


def check_invariants(result: dict[str, Any]) -> list[str]:
    """Assert the frozen caps; return failures (empty = PASS)."""
    failures: list[str] = []
    c_eval = result["c_eval"]
    if result["wait_selected"] > result["w_cap"]:
        failures.append("wait_selected exceeds W_cap")
    if result["pm_selected"] > result["p_cap"]:
        failures.append("PM_selected exceeds P_cap")
    if result["selected_total"] > c_eval:
        failures.append("selected_total exceeds C_eval")
    if len(result["selected_dps"]) != len(set(result["selected_dps"])):
        failures.append("duplicate dp in selected set")
    return failures
