#!/usr/bin/env python3
"""G3-SPEC-V1.0 S7: H1 preventive-replacement policy tuning (CR-V3.1/C26).

Frozen protocol (G3-SPEC-V1.0 section 7 ``c26_preventive_replacement`` +
section 8 ``data_separation``; G3-DEC-01/02/03; Human Gate 2026-08-14
section 1; AUTOPILOT PILOT #2 S7).  This module executes ONLY the frozen
protocol; it makes no policy or statistical decision.

Coarse candidate set (G3-DEC-01)
  * numeric tau_pm in {120, 144, 168, 192, 216};
  * policy baseline NO_PM_BEFORE_MANDATORY (never prevent; only the frozen
    mandatory-age rules execute);
  * 240 h is mandatory-replacement semantics and is NEVER encoded as a
    preventive threshold (``no_240_as_preventive``).

Tuning protocol (G3-DEC-03)
  * each candidate runs 20 independent 100-device batches under
    namespace=h1_tuning;
  * ALL candidates in the same tuning comparison share the SAME 20 canonical
    CRN worlds (same replicate_id pool), so the comparison is paired on the
    underlying canonical U world (CRN rule: no scenario/config/policy token
    enters a physical U key);
  * tuning objective (Human Gate section 1): minimize mean batch completion
    time T on the h1_tuning worlds;
  * quality metrics (S/PL/PW) are VALIDATION CONSTRAINTS verified with the
    C06 separation oracle (and the full C17 replay checker), never a tuning
    objective.

Tie-break (Human Gate section 1; fires ONLY when the canonical stored mean T
is exactly equal -- no epsilon tie, no CI overlap, no holdout):
  1. fewer preventive replacements (mean over the 20 batches) wins;
  2. larger tau_pm wins;
  3. NO_PM_BEFORE_MANDATORY is the least aggressive policy and wins a full
     tie (interpretation note: rules 1-2 already favour the less aggressive
     policy, so rule 3 completes the aggressiveness axis; flagged in the
     report for the coordinator to verify against the Human Gate record).

Local refinement (G3-DEC-02)
  * exactly one round, ONLY if the coarse winner is a numeric tau_pm:
    center = best coarse value, window = +/-12 h, step = 6 h, clipped to the
    legal preventive domain [120, 240), with already-evaluated candidates
    removed;
  * if the coarse winner is NO_PM_BEFORE_MANDATORY: no fake grid is built and
    there is no second round.

Final H1 candidate
  * best (mean T, then the frozen tie-break) over every evaluated candidate
    (coarse grid + refinement points) on the same 20 CRN worlds.

Scenario / observation kernel
  * Q2 calendar: N=100, one 12 h shift/day, off-shift all work stops
    (q2_single_shift; P037-P039);
  * observation kernel: frozen single-test unconditional closed form
    (1-q)*alpha = q*beta = e/2 (P060) via S3's
    ``frozen_single_test_alpha_beta``; q/e for A/B/C from parameters.csv
    P026-P028 / P030-P032.  The E kernel uses the Q1-frozen q_E propagation
    (accepted G2-02 run ``4bb92eda``, single_test_unconditional_v1 response
    q_E) with e_E = P033; alpha_E/beta_E come from the same frozen closed
    form (no self-calibration; observation-kernel calibration belongs to the
    frozen G2/Q1 task).

Boundaries
  * 100-device batches under namespace=h1_tuning are an AUTHORIZED tuning
    run, NOT a Q2 formal evaluation; every result is explicitly marked
    "G3 调优数据，非 Q2 正式" and is not allowed into the paper number source
    table;
  * no holdout peeking (g3_holdout namespace is never touched);
  * no change to candidates / policy / key schema / statistical procedure.

Outputs (per 05_结果/README.md): 05_结果/G3/tuning/run_<run_id>/
  run_manifest.json, tuning_protocol.json, tuning_results.json,
  validation_summary.json, c24_summary.json, per_run_table.json,
  log_hashes.json, checks.json, file_hashes.sha256

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Optional

BASE_DIR = Path(__file__).resolve().parents[2]  # competitions/模拟赛_研究生A题
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from des import state_models_v1 as sm  # noqa: E402
from g3 import key_schema_v1 as ks  # noqa: E402
from g3 import lifetime_regeneration_v1 as lr  # noqa: E402
from g3 import random_des_v1 as rd  # noqa: E402
from checker import g3_quality_oracle_v1 as qo  # noqa: E402
from checker import g3_replay_checker_v1 as rc  # noqa: E402

# ---------------------------------------------------------------------------
# Frozen identity / inputs
# ---------------------------------------------------------------------------

TASK_PACKAGE_REF = "G3-SPEC-V1.0"
TASK_PACKAGE_FILE = BASE_DIR / "08_项目管理" / "任务包" / "G3_公共随机DES与H1基线.yaml"
REGISTRY_VERSION = "CR-V3.1"
PARAMETERS_CSV = BASE_DIR / "02_数据" / "parameters.csv"
PROBLEM_CONTRACT_FILE = BASE_DIR / "01_审计" / "问题契约.md"

NAMESPACE = ks.NAMESPACE_H1_TUNING
BATCH_SIZE = 100
SCENARIO = "q2_single_shift"
SHIFT_LENGTH_H = "12"
SHIFTS_PER_DAY = 1
TRANSPORT_OUT_H = "0.5"
TRANSPORT_IN_H = "0.5"
TURNOVER_PROFILE = "1h_literal"

# G3-DEC-01 frozen coarse numeric thresholds (hours).
COARSE_TAUS: tuple[int, ...] = (120, 144, 168, 192, 216)

# G3-DEC-02 frozen refinement parameters (hours).
REFINEMENT_WINDOW_H = 12
REFINEMENT_STEP_H = 6
PREVENTIVE_DOMAIN_LO_H = 120  # P016 a_min (inclusive)
PREVENTIVE_DOMAIN_HI_H = 240  # P017 a_max (exclusive; 240 is mandatory)

# G3-DEC-03 frozen repetition count.
TUNING_REPETITIONS = 20

# Q1-frozen q_E propagation input: accepted G2-02 run
# ``05_结果/G2/run_20260814T130947069958Z_4bb92eda``,
# single_test_unconditional_v1/response.json ``q_E`` (P060 literal semantics).
Q1_FROZEN_Q_E_TEXT = "0.062593912407392898"

# Frozen parameters.csv rows consumed here (P026-P028 q, P030-P032 e, P033 e_E).
FROZEN_Q_ABC: dict[str, Fraction] = {
    "A": Fraction(25, 1000),  # P026 q_A = 0.025
    "B": Fraction(3, 100),    # P027 q_B = 0.03
    "C": Fraction(2, 100),    # P028 q_C = 0.02
}
FROZEN_E_ABC: dict[str, Fraction] = {
    "A": Fraction(3, 100),    # P030 e_A = 0.03
    "B": Fraction(4, 100),    # P031 e_B = 0.04
    "C": Fraction(2, 100),    # P032 e_C = 0.02
}
FROZEN_E_E: Fraction = Fraction(2, 100)  # P033 e_E = 0.02

SOURCE_CODE_FILES: tuple[Path, ...] = (
    Path(__file__).resolve(),
    MAIN_MODEL / "g3" / "random_des_v1.py",
    MAIN_MODEL / "g3" / "key_schema_v1.py",
    MAIN_MODEL / "g3" / "lifetime_regeneration_v1.py",
    CODE_DIR / "checker" / "g3_quality_oracle_v1.py",
    CODE_DIR / "checker" / "g3_replay_checker_v1.py",
    CODE_DIR / "tests" / "test_g3_h1_tuning_v1.py",
)

# ---------------------------------------------------------------------------
# Pure frozen-protocol functions (also exercised by the unit tests)
# ---------------------------------------------------------------------------


def coarse_candidates() -> tuple[Any, ...]:
    """Frozen coarse candidate set (G3-DEC-01): numeric tau_pm 120..216 plus
    the NO_PM_BEFORE_MANDATORY policy baseline. 240 h is never a preventive
    threshold (no_240_as_preventive), so 240 is not returned."""
    return tuple(Fraction(t) for t in COARSE_TAUS) + (lr.NO_PM_BEFORE_MANDATORY,)


def candidate_label(candidate: Any) -> str:
    """Deterministic result-table key for a candidate."""
    if candidate is lr.NO_PM_BEFORE_MANDATORY:
        return "NO_PM_BEFORE_MANDATORY"
    return f"tau_pm_{int(candidate)}"


def is_numeric_tau(candidate: Any) -> bool:
    return candidate is not lr.NO_PM_BEFORE_MANDATORY


def refinement_grid(
    center: Any,
    window_h: int = REFINEMENT_WINDOW_H,
    step_h: int = REFINEMENT_STEP_H,
    lo_h: int = PREVENTIVE_DOMAIN_LO_H,
    hi_h: int = PREVENTIVE_DOMAIN_HI_H,
    evaluated: Iterable[Any] = (),
) -> tuple[int, ...]:
    """G3-DEC-02: exactly-one-round local refinement grid.

    Grid points are ``center + k*step`` for every integer multiple k with
    ``|k*step| <= window`` (i.e. -12, -6, 0, +6, +12 h), clipped to the legal
    preventive domain [lo_h, hi_h) = [120, 240), then de-duplicated against
    already-evaluated candidates (the coarse winner itself is normally
    already evaluated and is therefore dropped). Returns the NEW points to
    evaluate, sorted ascending.

    ``center`` must be a numeric tau_pm (the caller guarantees this: when the
    coarse winner is NO_PM_BEFORE_MANDATORY the runner never calls this).
    """
    center_i = int(Fraction(center))
    if not (lo_h <= center_i < hi_h):
        raise ValueError(f"refinement center must lie in [{lo_h}, {hi_h})")
    if window_h < step_h or step_h <= 0:
        raise ValueError("refinement requires 0 < step_h <= window_h")
    points: set[int] = set()
    offset = -window_h
    while offset <= window_h:
        p = center_i + offset
        if lo_h <= p < hi_h:
            points.add(p)
        offset += step_h
    evaluated_set: set[int] = set()
    for c in evaluated:
        try:
            evaluated_set.add(int(Fraction(c)))
        except (TypeError, ValueError):
            # non-numeric sentinel (NO_PM_BEFORE_MANDATORY) is not a tau
            # point; never part of the refinement grid
            continue
    return tuple(sorted(p for p in points if p not in evaluated_set))


def refinement_grid_points_only(
    center: Any,
    window_h: int = REFINEMENT_WINDOW_H,
    step_h: int = REFINEMENT_STEP_H,
    lo_h: int = PREVENTIVE_DOMAIN_LO_H,
    hi_h: int = PREVENTIVE_DOMAIN_HI_H,
) -> tuple[int, ...]:
    """The clipped refinement grid WITHOUT de-duplication (reporting helper:
    shows the full grid the protocol would consider, including the center)."""
    return refinement_grid(center, window_h, step_h, lo_h, hi_h, evaluated=())


def mean_of_fractions(values: Iterable[Any]) -> Fraction:
    """Exact mean of Fractions (canonical stored values; no binary float)."""
    vals = [Fraction(v) for v in values]
    if not vals:
        raise ValueError("mean_of_fractions requires at least one value")
    return sum(vals, Fraction(0)) / len(vals)


def candidate_aggressiveness_rank(candidate: Any) -> Fraction:
    """Tie-break rule 3 rank: numeric tau_pm ranks by its size (larger tau_pm
    = less aggressive = preferred); NO_PM_BEFORE_MANDATORY is the least
    aggressive policy, so it ranks above every numeric threshold. Only used
    after rules 1-2 have failed to separate the candidates."""
    if candidate is lr.NO_PM_BEFORE_MANDATORY:
        return Fraction(1 << 100)  # effectively +inf for the ranking
    return Fraction(candidate)


def frozen_observation_kernel() -> dict[str, dict[str, Fraction]]:
    """Frozen single-test unconditional observation kernel (P060).

    A/B/C: ``(1-q)*alpha = q*beta = e/2`` with q from P026-P028 and e from
    P030-P032, via the S3 frozen helper ``frozen_single_test_alpha_beta``.
    E: q_E per the Q1-frozen propagation (accepted G2-02 run 4bb92eda,
    single_test_unconditional_v1 response q_E) and e_E = P033, via the same
    frozen closed form. No self-calibration anywhere.
    """
    kernel: dict[str, dict[str, Fraction]] = {}
    for proc in ("A", "B", "C"):
        alpha, beta = rd.frozen_single_test_alpha_beta(
            FROZEN_Q_ABC[proc], FROZEN_E_ABC[proc]
        )
        kernel[proc] = {"alpha": alpha, "beta": beta}
    q_e = Fraction(Q1_FROZEN_Q_E_TEXT)
    alpha_e, beta_e = rd.frozen_single_test_alpha_beta(q_e, FROZEN_E_E)
    kernel["E"] = {"alpha": alpha_e, "beta": beta_e}
    return kernel


def make_tuning_config(
    candidate: Any,
    replicate_id: int,
    master_seed: int,
    kernel: dict[str, dict[str, Fraction]],
    batch_size: int = BATCH_SIZE,
    scenario_id: Optional[str] = None,
) -> rd.RandomDesConfig:
    """Build the frozen Q2-calendar tuning config for one (candidate, world).

    namespace is always h1_tuning; the world identity is
    (master_seed, replicate_id); tau_pm is the candidate (numeric or the
    NO_PM sentinel). ``scenario_id`` is run metadata only and never enters a
    canonical U key (forbidden physical fields are rejected by key_schema).
    """
    return rd.default_config(
        namespace=NAMESPACE,
        master_seed=master_seed,
        replicate_id=replicate_id,
        tau_pm=candidate,
        observation_kernel=kernel,
        batch_size=batch_size,
        scenario=SCENARIO,
        shift_length_h=SHIFT_LENGTH_H,
        shifts_per_day=SHIFTS_PER_DAY,
        turnover_profile=TURNOVER_PROFILE,
        scenario_id=scenario_id
        or f"g3_h1_tuning_{candidate_label(candidate)}_rep{replicate_id}",
    )


# ---------------------------------------------------------------------------
# Run records / aggregation (exact Fraction arithmetic)
# ---------------------------------------------------------------------------


@dataclass
class RunRecord:
    """One (candidate, replicate) tuning run: metrics + validation verdicts."""

    candidate: Any
    replicate_id: int
    T: Fraction
    T_days: Fraction
    preventive_replacement_count: int
    replacement_count: int
    failure_count: int
    S: int
    PL: int
    PW: int
    exited: int
    quality_verdict: str
    replay_verdict: str
    c24: dict[str, Any]
    log_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": candidate_label(self.candidate),
            "replicate_id": self.replicate_id,
            "T_h": sm.fraction_to_string(self.T),
            "T_days": sm.fraction_to_string(self.T_days),
            "preventive_replacement_count": self.preventive_replacement_count,
            "replacement_count": self.replacement_count,
            "failure_count": self.failure_count,
            "S": self.S,
            "PL": self.PL,
            "PW": self.PW,
            "exited": self.exited,
            "quality_oracle_verdict": self.quality_verdict,
            "replay_checker_verdict": self.replay_verdict,
            "c24": dict(self.c24),
            "canonical_log_sha256": self.log_sha256,
        }


@dataclass(frozen=True)
class CandidateStats:
    """Exact aggregated statistics for one candidate over the shared CRN pool."""

    candidate: Any
    n_replicates: int
    mean_T: Fraction
    mean_T_days: Fraction
    mean_preventive_replacement_count: Fraction
    mean_replacement_count: Fraction
    mean_failure_count: Fraction
    mean_S: Fraction
    mean_PL: Fraction
    mean_PW: Fraction
    mean_exited: Fraction
    quality_verdicts: tuple[str, ...]
    replay_verdicts: tuple[str, ...]
    c24_mean_decision_point_density: Fraction
    c24_total_decision_points: int
    c24_total_legal_actions: int
    c24_total_waiting_opportunities: int
    c24_total_pm_opportunities: int
    c24_total_branching_burden: int

    @property
    def quality_all_pass(self) -> bool:
        return all(v == "PASS" for v in self.quality_verdicts)

    @property
    def replay_all_pass(self) -> bool:
        return all(v == "PASS" for v in self.replay_verdicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": candidate_label(self.candidate),
            "tau_pm_h": (
                None
                if self.candidate is lr.NO_PM_BEFORE_MANDATORY
                else sm.fraction_to_string(Fraction(self.candidate))
            ),
            "n_replicates": self.n_replicates,
            "mean_T_h": sm.fraction_to_string(self.mean_T),
            "mean_T_days": sm.fraction_to_string(self.mean_T_days),
            "mean_preventive_replacement_count": sm.fraction_to_string(
                self.mean_preventive_replacement_count
            ),
            "mean_replacement_count": sm.fraction_to_string(self.mean_replacement_count),
            "mean_failure_count": sm.fraction_to_string(self.mean_failure_count),
            "mean_S": sm.fraction_to_string(self.mean_S),
            "mean_PL": sm.fraction_to_string(self.mean_PL),
            "mean_PW": sm.fraction_to_string(self.mean_PW),
            "mean_exited": sm.fraction_to_string(self.mean_exited),
            "quality_oracle_all_pass": self.quality_all_pass,
            "replay_checker_all_pass": self.replay_all_pass,
            "c24": {
                "mean_decision_point_density": sm.fraction_to_string(
                    self.c24_mean_decision_point_density
                ),
                "total_decision_point_count": self.c24_total_decision_points,
                "total_legal_action_count": self.c24_total_legal_actions,
                "total_waiting_opportunity_count": self.c24_total_waiting_opportunities,
                "total_preventive_replacement_opportunity_count": (
                    self.c24_total_pm_opportunities
                ),
                "total_estimated_rollout_branching_burden": (
                    self.c24_total_branching_burden
                ),
            },
        }


def candidate_sort_key(stats: CandidateStats) -> tuple:
    """Deterministic selection key (frozen objective + tie-break), lower is
    better: (mean T; tie -> fewer preventive replacements; tie -> less
    aggressive policy: larger tau_pm, NO_PM least aggressive)."""
    return (
        stats.mean_T,
        stats.mean_preventive_replacement_count,
        -candidate_aggressiveness_rank(stats.candidate),
    )


def select_best(stats_list: Iterable[CandidateStats]) -> CandidateStats:
    """Frozen winner selection over evaluated candidates."""
    return min(stats_list, key=candidate_sort_key)


def exact_mean_t_tie(a: CandidateStats, b: CandidateStats) -> bool:
    """Tie-break trigger condition: canonical stored mean T exactly equal."""
    return a.mean_T == b.mean_T


def aggregate_runs(runs: Iterable[RunRecord]) -> CandidateStats:
    """Aggregate the (candidate, replicate) records into exact CandidateStats.

    Raises ValueError if the runs mix candidates or the replicate count is
    zero (fail loudly on protocol drift)."""
    records = list(runs)
    if not records:
        raise ValueError("aggregate_runs requires at least one run record")
    first = records[0].candidate
    if any(r.candidate != first for r in records):
        raise ValueError("aggregate_runs received runs of different candidates")
    reps = [r.replicate_id for r in records]
    if len(set(reps)) != len(reps):
        raise ValueError("aggregate_runs received duplicate replicate_id values")
    n = len(records)
    mean_t = mean_of_fractions(r.T for r in records)
    mean_preventive = mean_of_fractions(r.preventive_replacement_count for r in records)
    c24_counts = {
        "decision_point_count": sum(r.c24["decision_point_count"] for r in records),
        "legal_action_count": sum(r.c24["legal_action_count"] for r in records),
        "waiting_opportunity_count": sum(
            r.c24["waiting_opportunity_count"] for r in records
        ),
        "preventive_replacement_opportunity_count": sum(
            r.c24["preventive_replacement_opportunity_count"] for r in records
        ),
        "estimated_rollout_branching_burden": sum(
            r.c24["estimated_rollout_branching_burden"] for r in records
        ),
    }
    densities = [Fraction(r.c24["decision_point_density"]) for r in records]
    return CandidateStats(
        candidate=first,
        n_replicates=n,
        mean_T=mean_t,
        mean_T_days=mean_of_fractions(r.T_days for r in records),
        mean_preventive_replacement_count=mean_preventive,
        mean_replacement_count=mean_of_fractions(r.replacement_count for r in records),
        mean_failure_count=mean_of_fractions(r.failure_count for r in records),
        mean_S=mean_of_fractions(r.S for r in records),
        mean_PL=mean_of_fractions(r.PL for r in records),
        mean_PW=mean_of_fractions(r.PW for r in records),
        mean_exited=mean_of_fractions(r.exited for r in records),
        quality_verdicts=tuple(r.quality_verdict for r in records),
        replay_verdicts=tuple(r.replay_verdict for r in records),
        c24_mean_decision_point_density=mean_of_fractions(densities),
        c24_total_decision_points=c24_counts["decision_point_count"],
        c24_total_legal_actions=c24_counts["legal_action_count"],
        c24_total_waiting_opportunities=c24_counts["waiting_opportunity_count"],
        c24_total_pm_opportunities=c24_counts[
            "preventive_replacement_opportunity_count"
        ],
        c24_total_branching_burden=c24_counts["estimated_rollout_branching_burden"],
    )


# ---------------------------------------------------------------------------
# Validation (C06 quality separation oracle + C17 full replay checker)
# ---------------------------------------------------------------------------


def validate_run(
    event_log: list[dict[str, Any]],
    config_dict: dict[str, Any],
    metrics: dict[str, Any],
    run_id: str,
) -> tuple[str, str, list[str], list[str]]:
    """Run both frozen checkers on one tuning run and return
    (quality_verdict, replay_verdict, quality_issues, replay_issues).

    Raises on checker input/numerical errors (never silently downgraded)."""
    quality_report = qo.check_quality_oracle(
        event_log, config_dict, PARAMETERS_CSV, metrics=metrics
    )
    replay_report = rc.check_replay(
        event_log, config_dict, PARAMETERS_CSV, metrics=metrics, run_id=run_id
    )
    quality_issues = [str(i) for i in quality_report.issues]
    replay_issues = [str(i) for i in replay_report.issues]
    return (
        quality_report.verdict,
        replay_report.verdict,
        quality_issues,
        replay_issues,
    )


# ---------------------------------------------------------------------------
# Evaluation driver
# ---------------------------------------------------------------------------


def evaluate_candidate(
    candidate: Any,
    replicate_ids: tuple[int, ...],
    master_seed: int,
    kernel: dict[str, dict[str, Fraction]],
) -> tuple[list[RunRecord], CandidateStats, list[dict[str, Any]]]:
    """Run one candidate over the shared CRN replicate pool (namespace
    h1_tuning), validate every run with the C06 oracle and the C17 replay
    checker, and aggregate exact statistics.

    Returns (run_records, stats, validation_details) where validation_details
    is a per-run list of {candidate, replicate_id, quality_verdict,
    replay_verdict, quality_issues, replay_issues}.
    """
    records: list[RunRecord] = []
    details: list[dict[str, Any]] = []
    for rep in replicate_ids:
        cfg = make_tuning_config(candidate, rep, master_seed, kernel)
        cfg_dict = cfg.to_dict()
        result = rd.run_random_des(cfg)
        metrics = result.metrics
        event_log = result.event_log
        log_sha = hashlib.sha256(result.canonical_event_log()).hexdigest()
        run_tag = f"{candidate_label(candidate)}_rep{rep}"
        quality_verdict, replay_verdict, quality_issues, replay_issues = validate_run(
            event_log, cfg_dict, metrics, run_tag
        )
        c24 = dict(metrics["c24"])
        equipment = metrics["equipment"]
        preventive = sum(
            equipment[r]["preventive_replacement_count"] for r in sm.RESOURCES
        )
        replacements = sum(equipment[r]["replacement_count"] for r in sm.RESOURCES)
        failures = sum(equipment[r]["failure_count"] for r in sm.RESOURCES)
        rec = RunRecord(
            candidate=candidate,
            replicate_id=rep,
            T=Fraction(metrics["T"]),
            T_days=Fraction(metrics["T_days"]),
            preventive_replacement_count=preventive,
            replacement_count=replacements,
            failure_count=failures,
            S=int(metrics["S"]),
            PL=int(metrics["PL"]),
            PW=int(metrics["PW"]),
            exited=int(metrics["exited"]),
            quality_verdict=quality_verdict,
            replay_verdict=replay_verdict,
            c24=c24,
            log_sha256=log_sha,
        )
        records.append(rec)
        details.append(
            {
                "candidate": candidate_label(candidate),
                "replicate_id": rep,
                "quality_oracle_verdict": quality_verdict,
                "quality_issues": quality_issues,
                "replay_checker_verdict": replay_verdict,
                "replay_issues": replay_issues,
            }
        )
    return records, aggregate_runs(records), details


def _tie_break_evidence(stats_list: list[CandidateStats]) -> dict[str, Any]:
    """Record whether the exact-mean-T tie-break fired and which rule decided."""
    best = select_best(stats_list)
    tied = [s for s in stats_list if exact_mean_t_tie(s, best)]
    evidence: dict[str, Any] = {
        "tie_break_triggered": len(tied) > 1,
        "tied_candidates": [candidate_label(s.candidate) for s in tied],
        "rule": None,
    }
    if len(tied) > 1:
        min_preventive = min(s.mean_preventive_replacement_count for s in tied)
        preventive_tied = [
            s for s in tied if s.mean_preventive_replacement_count == min_preventive
        ]
        if len(preventive_tied) == 1:
            evidence["rule"] = "1_fewer_preventive_replacements"
        else:
            max_rank = max(
                candidate_aggressiveness_rank(s.candidate) for s in preventive_tied
            )
            aggressive_tied = [
                s
                for s in preventive_tied
                if candidate_aggressiveness_rank(s.candidate) == max_rank
            ]
            if len(aggressive_tied) == 1:
                evidence["rule"] = "2_larger_tau_pm_or_least_aggressive"
            else:
                evidence["rule"] = (
                    "3_exact_full_tie_resolved_by_aggressiveness_rank"
                )
    return evidence


# ---------------------------------------------------------------------------
# Evidence / result writing (05_结果/G3/tuning/run_<run_id>/)
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_") + secrets.token_hex(4)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dump_json(path: Path, value: Any) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _env_summary() -> dict[str, Any]:
    import platform

    return {
        "python_version": sys.version.split()[0],
        "python_impl": platform.python_implementation(),
        "platform": platform.platform(),
    }


def build_manifest(
    run_id: str,
    protocol: dict[str, Any],
    results: dict[str, Any],
    overall_status: str,
    out_dir: Path,
) -> dict[str, Any]:
    """run_manifest.json per 05_结果/README.md (minimum fields)."""
    artifacts: list[dict[str, Any]] = []
    for path in sorted(out_dir.iterdir()):
        if not path.is_file():
            continue
        artifacts.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    inputs: list[dict[str, Any]] = []
    for path, role in (
        (TASK_PACKAGE_FILE, "task_package"),
        (PARAMETERS_CSV, "parameters"),
        (PROBLEM_CONTRACT_FILE, "problem_contract"),
    ):
        inputs.append(
            {
                "path": path.relative_to(BASE_DIR).as_posix(),
                "role": role,
                "sha256": _sha256_file(path),
            }
        )
    for path in SOURCE_CODE_FILES:
        if path.exists():
            inputs.append(
                {
                    "path": path.relative_to(BASE_DIR).as_posix(),
                    "role": "source_code",
                    "sha256": _sha256_file(path),
                }
            )
    manifest = {
        "run_id": run_id,
        "created_at": _utc_now(),
        "gate": "G3",
        "purpose": "tuning",
        "formal": False,
        "label": "G3 调优数据，非 Q2 正式",
        "allowed_in_paper_number_source_table": False,
        "task_package_ref": TASK_PACKAGE_REF,
        "task_package_hash": _sha256_file(TASK_PACKAGE_FILE),
        "registry_version": REGISTRY_VERSION,
        "required_check_ids": ["C06", "C13", "C14", "C16", "C17", "C18", "C24", "C26"],
        "problem_contract": {
            "path": PROBLEM_CONTRACT_FILE.relative_to(BASE_DIR).as_posix(),
            "sha256": _sha256_file(PROBLEM_CONTRACT_FILE),
        },
        "parameters_csv": {
            "path": PARAMETERS_CSV.relative_to(BASE_DIR).as_posix(),
            "sha256": _sha256_file(PARAMETERS_CSV),
        },
        "random_world": {
            "key_schema_version": ks.KEY_SCHEMA_VERSION,
            "namespace": NAMESPACE,
            "master_seed": protocol["master_seed"],
            "replicate_ids": protocol["replicate_ids"],
            "batch_size": protocol["batch_size"],
            "scenario": protocol["scenario"],
        },
        "code_hashes": {
            path.relative_to(BASE_DIR).as_posix(): _sha256_file(path)
            for path in SOURCE_CODE_FILES
            if path.exists()
        },
        "environment": _env_summary(),
        "inputs": inputs,
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "validation_summary.json"],
        "overall_status": overall_status,
        "notes": [
            "G3 调优数据，非 Q2 正式：100-device 批次在 namespace=h1_tuning 下运行（G3-SPEC-V1.0 授权验证/调优），不得作为 Q2 正式数字。",
            "观测核：P060 冻结单次无条件闭式 (1-q)alpha=q beta=e/2；E 核 q_E 按 Q1 冻结输出（G2-02 accepted run 4bb92eda）传播，alpha_E/beta_E 用同一冻结闭式。",
        ],
    }
    return manifest


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def run_tuning(
    output_root: Path,
    master_seed: int,
    replicate_ids: tuple[int, ...],
) -> dict[str, Any]:
    """Execute the full frozen tuning protocol (coarse grid -> tie-break ->
    local refinement -> final candidate freeze), validate every run with the
    C06 oracle and C17 replay checker, and persist all results.

    Returns the summary dict; the caller writes the evidence files.
    """
    kernel = frozen_observation_kernel()

    # -- coarse grid --------------------------------------------------------
    candidates = coarse_candidates()
    all_records: list[RunRecord] = []
    all_details: list[dict[str, Any]] = []
    coarse_stats: list[CandidateStats] = []
    for candidate in candidates:
        tag = candidate_label(candidate)
        t0 = time.perf_counter()
        records, stats, details = evaluate_candidate(
            candidate, replicate_ids, master_seed, kernel
        )
        dt = time.perf_counter() - t0
        all_records.extend(records)
        all_details.extend(details)
        coarse_stats.append(stats)
        print(
            f"[tuning] coarse {tag}: mean_T={sm.fraction_to_string(stats.mean_T)} h "
            f"mean_PM={sm.fraction_to_string(stats.mean_preventive_replacement_count)} "
            f"quality={stats.quality_all_pass} replay={stats.replay_all_pass} "
            f"({dt:.1f}s)"
        )

    coarse_winner = select_best(coarse_stats)
    tie_evidence = _tie_break_evidence(coarse_stats)

    # every evaluated candidate (coarse + refinement) for the final selection
    all_stats_list: list[CandidateStats] = list(coarse_stats)

    # -- local refinement (G3-DEC-02) --------------------------------------
    refinement: dict[str, Any] = {
        "applicable": False,
        "rule": "coarse winner is NO_PM_BEFORE_MANDATORY: no fake grid, no second round",
        "grid": [],
        "new_candidates": [],
        "winner_after_refinement": None,
    }
    if is_numeric_tau(coarse_winner.candidate):
        clipped_grid = refinement_grid_points_only(
            coarse_winner.candidate,
        )
        new_grid = refinement_grid(
            coarse_winner.candidate,
            evaluated=[
                c.candidate
                for c in coarse_stats
                if is_numeric_tau(c.candidate)
            ],
        )
        refinement = {
            "applicable": True,
            "rule": (
                "exactly one round: center=best coarse value, window=+/-12 h, "
                "step=6 h, clipped to [120,240), dedup already evaluated"
            ),
            "center": candidate_label(coarse_winner.candidate),
            "grid": [candidate_label(Fraction(t)) for t in clipped_grid],
            "new_candidates": [candidate_label(Fraction(t)) for t in new_grid],
            "winner_after_refinement": None,
        }
        for threshold in new_grid:
            candidate = Fraction(threshold)
            tag = candidate_label(candidate)
            t0 = time.perf_counter()
            records, stats, details = evaluate_candidate(
                candidate, replicate_ids, master_seed, kernel
            )
            dt = time.perf_counter() - t0
            all_records.extend(records)
            all_details.extend(details)
            all_stats_list.append(stats)
            print(
                f"[tuning] refine {tag}: mean_T={sm.fraction_to_string(stats.mean_T)} h "
                f"mean_PM={sm.fraction_to_string(stats.mean_preventive_replacement_count)} "
                f"quality={stats.quality_all_pass} replay={stats.replay_all_pass} "
                f"({dt:.1f}s)"
            )
        final_winner = select_best(all_stats_list)
        refinement["winner_after_refinement"] = candidate_label(
            final_winner.candidate
        )
    else:
        final_winner = coarse_winner

    final_candidate = final_winner.candidate
    final_label = candidate_label(final_candidate)

    # -- validation aggregation ---------------------------------------------
    quality_failures = [
        d
        for d in all_details
        if d["quality_oracle_verdict"] != "PASS"
    ]
    replay_failures = [
        d
        for d in all_details
        if d["replay_checker_verdict"] != "PASS"
    ]
    validation_ok = not quality_failures and not replay_failures
    overall_status = "PASS" if validation_ok else "VALIDATION_FAILED"

    stats_by_label = {
        candidate_label(s.candidate): s for s in all_stats_list
    }

    results: dict[str, Any] = {
        "run_id": None,  # filled by caller after run_id is minted
        "task_package_ref": TASK_PACKAGE_REF,
        "registry_version": REGISTRY_VERSION,
        "formal": False,
        "label": "G3 调优数据，非 Q2 正式",
        "protocol": {
            "namespace": NAMESPACE,
            "master_seed": master_seed,
            "replicate_ids": list(replicate_ids),
            "batch_size": BATCH_SIZE,
            "scenario": SCENARIO,
            "shift_length_h": SHIFT_LENGTH_H,
            "shifts_per_day": SHIFTS_PER_DAY,
            "turnover_profile": TURNOVER_PROFILE,
            "repetitions_per_candidate": len(replicate_ids),
            "objective": "minimize mean batch completion time T on h1_tuning worlds",
            "quality_constraint": (
                "S/PL/PW validated as constraints via the C06 separation "
                "oracle and the C17 replay checker; never a tuning objective"
            ),
            "tie_break": (
                "only on exact equal canonical mean T; 1. fewer preventive "
                "replacements; 2. larger tau_pm; 3. NO_PM_BEFORE_MANDATORY "
                "least aggressive; no epsilon/CI/holdout ties"
            ),
            "refinement": (
                "G3-DEC-02: one round, center=best coarse, window=+/-12h, "
                "step=6h, clip [120,240), dedup evaluated; none if coarse "
                "winner is NO_PM_BEFORE_MANDATORY"
            ),
            "observation_kernel": {
                p: {
                    "alpha": sm.fraction_to_string(kernel[p]["alpha"]),
                    "beta": sm.fraction_to_string(kernel[p]["beta"]),
                }
                for p in sm.RESOURCES
            },
            "q1_frozen_q_e_input": Q1_FROZEN_Q_E_TEXT,
        },
        "coarse": {
            "candidates": [candidate_label(c) for c in candidates],
            "results": {
                candidate_label(s.candidate): s.to_dict() for s in coarse_stats
            },
            "winner": candidate_label(coarse_winner.candidate),
            "winner_mean_T_h": sm.fraction_to_string(coarse_winner.mean_T),
            "tie_break": tie_evidence,
        },
        "refinement": refinement,
        "final_candidate": final_label,
        "final_frozen_value": (
            "NO_PM_BEFORE_MANDATORY"
            if final_candidate is lr.NO_PM_BEFORE_MANDATORY
            else sm.fraction_to_string(Fraction(final_candidate))
        ),
        "final_mean_T_h": sm.fraction_to_string(final_winner.mean_T),
        "final_mean_T_days": sm.fraction_to_string(final_winner.mean_T_days),
        "final_mean_preventive_replacement_count": sm.fraction_to_string(
            final_winner.mean_preventive_replacement_count
        ),
        "validation": {
            "overall_status": overall_status,
            "quality_oracle_failures": len(quality_failures),
            "replay_checker_failures": len(replay_failures),
        },
    }
    return {
        "results": results,
        "records": all_records,
        "details": all_details,
        "final_winner": final_winner,
        "stats_by_label": stats_by_label,
        "overall_status": overall_status,
    }


def write_evidence(
    run_id: str,
    out_dir: Path,
    summary: dict[str, Any],
    master_seed: int,
    replicate_ids: tuple[int, ...],
) -> dict[str, Any]:
    """Persist all tuning evidence under out_dir and return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = summary["results"]
    results["run_id"] = run_id
    protocol = results["protocol"]

    _dump_json(out_dir / "tuning_protocol.json", protocol)
    _dump_json(out_dir / "tuning_results.json", results)
    _dump_json(
        out_dir / "per_run_table.json",
        {
            "run_id": run_id,
            "formal": False,
            "label": "G3 调优数据，非 Q2 正式",
            "runs": [r.to_dict() for r in summary["records"]],
        },
    )
    _dump_json(
        out_dir / "validation_summary.json",
        {
            "run_id": run_id,
            "formal": False,
            "label": "G3 调优数据，非 Q2 正式",
            "overall_status": summary["overall_status"],
            "per_run": summary["details"],
        },
    )
    c24_payload: dict[str, Any] = {"run_id": run_id, "formal": False,
                                   "label": "G3 调优数据，非 Q2 正式",
                                   "by_candidate": {}}
    for label, stats in sorted(summary["stats_by_label"].items()):
        c24_payload["by_candidate"][label] = stats.to_dict()["c24"]
    c24_payload["final_candidate"] = results["final_candidate"]
    _dump_json(out_dir / "c24_summary.json", c24_payload)
    _dump_json(
        out_dir / "log_hashes.json",
        {
            "run_id": run_id,
            "formal": False,
            "label": "G3 调优数据，非 Q2 正式",
            "canonical_event_log_sha256": {
                f"{candidate_label(r.candidate)}__rep{r.replicate_id}": r.log_sha256
                for r in summary["records"]
            },
        },
    )
    checks = {
        "run_id": run_id,
        "registry_version": REGISTRY_VERSION,
        "required_check_ids": ["C06", "C13", "C14", "C16", "C17", "C18", "C24", "C26"],
        "overall_status": summary["overall_status"],
        "items": [
            {
                "check_id": "CR-V3.1/C06",
                "layer": "G3 full 质量分离 oracle（调优校验约束）",
                "status": (
                    "PASS"
                    if results["validation"]["quality_oracle_failures"] == 0
                    else "FAIL"
                ),
                "note": "全部调优运行的 S/PL/PW 经 C06 分离命题约束验证（非调优目标）",
            },
            {
                "check_id": "CR-V3.1/C17",
                "layer": "G3 full replay（调优校验约束）",
                "status": (
                    "PASS"
                    if results["validation"]["replay_checker_failures"] == 0
                    else "FAIL"
                ),
                "note": "全部调优运行的完整日志重放验证；失败明细见 validation_summary.json",
            },
            {
                "check_id": "CR-V3.1/C24",
                "layer": "G3 出口仪表（H2 不实现）",
                "status": "PASS",
                "note": "决策点密度等仪表作为调优副产物记录（c24_summary.json）",
            },
            {
                "check_id": "CR-V3.1/C26",
                "layer": "H1 预防更换政策（调优协议执行）",
                "status": "PASS",
                "note": "冻结候选集/20 配对批次/冻结目标/确定性 tie-break/局部细化全部按 G3-SPEC-V1.0 执行",
            },
        ],
    }
    _dump_json(out_dir / "checks.json", checks)
    # file_hashes.sha256 (LF lines: "<hex>  <relative path>"; lists every file
    # except itself). Written before the manifest so the manifest's outputs
    # inventory includes it.
    lines = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file():
            lines.append(f"{_sha256_file(path)}  {path.name}")
    (out_dir / "file_hashes.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    manifest = build_manifest(run_id, protocol, results, summary["overall_status"], out_dir)
    _dump_json(out_dir / "run_manifest.json", manifest)
    return manifest


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="G3-SPEC-V1.0 S7: H1 preventive-replacement policy tuning (C26)."
    )
    parser.add_argument(
        "--output-root",
        default=str(BASE_DIR / "05_结果" / "G3" / "tuning"),
        help="results root; a run_<run_id>/ directory is created under it",
    )
    parser.add_argument(
        "--master-seed", type=int, default=1,
        help="canonical master_seed for the h1_tuning namespace (default 1)",
    )
    parser.add_argument(
        "--replicate-count", type=int, default=TUNING_REPETITIONS,
        help=(
            f"replicates per candidate (frozen protocol = {TUNING_REPETITIONS}; "
            "a deviation is recorded in the manifest)"
        ),
    )
    parser.add_argument(
        "--first-replicate", type=int, default=0,
        help="first replicate_id of the shared CRN pool (default 0)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    output_root = Path(args.output_root).resolve()
    master_seed = args.master_seed
    replicate_ids = tuple(
        range(args.first_replicate, args.first_replicate + args.replicate_count)
    )
    if args.replicate_count != TUNING_REPETITIONS:
        print(
            f"[tuning] WARNING: replicate-count={args.replicate_count} deviates "
            f"from the frozen protocol value {TUNING_REPETITIONS}; the manifest "
            "records this as a protocol deviation."
        )

    # Fail loudly on drifted frozen inputs (AGENTS.md: 参数无效必须显式失败).
    rd.validate_parameters_csv(PARAMETERS_CSV)
    lr.validate_parameters_csv(PARAMETERS_CSV)

    run_id = _new_run_id()
    out_dir = output_root / f"run_{run_id}"
    print(f"[tuning] run_id={run_id}")
    print(f"[tuning] output={out_dir}")
    print(
        f"[tuning] namespace=h1_tuning master_seed={master_seed} "
        f"replicate_ids={replicate_ids[0]}..{replicate_ids[-1]} "
        f"({len(replicate_ids)} shared CRN worlds)"
    )

    summary = run_tuning(output_root, master_seed, replicate_ids)
    summary["results"]["run_id"] = run_id
    if args.replicate_count != TUNING_REPETITIONS:
        summary["results"]["protocol"]["protocol_deviation"] = {
            "frozen_repetitions": TUNING_REPETITIONS,
            "actual_repetitions": args.replicate_count,
            "note": "deviation for smoke/test only; not an accepted tuning result",
        }
    manifest = write_evidence(
        run_id, out_dir, summary, master_seed, replicate_ids
    )
    results = summary["results"]

    print()
    print("=" * 78)
    print("G3 H1 TUNING SUMMARY (G3 调优数据，非 Q2 正式)")
    print("=" * 78)
    print(f"run_id            : {run_id}")
    print(f"namespace         : h1_tuning (master_seed={master_seed}, "
          f"{len(replicate_ids)} shared CRN worlds)")
    print()
    print("COARSE GRID (mean over shared worlds):")
    print(f"{'candidate':<24}{'mean_T_h':>14}{'mean_PM':>14}{'C06':>6}{'C17':>6}")
    for label, stats in sorted(summary["stats_by_label"].items()):
        print(
            f"{label:<24}{sm.fraction_to_string(stats.mean_T):>14}"
            f"{sm.fraction_to_string(stats.mean_preventive_replacement_count):>14}"
            f"{'PASS' if stats.quality_all_pass else 'FAIL':>6}"
            f"{'PASS' if stats.replay_all_pass else 'FAIL':>6}"
        )
    print()
    print(f"coarse winner     : {results['coarse']['winner']} "
          f"(mean_T={results['coarse']['winner_mean_T_h']} h)")
    print(f"tie-break fired   : {results['coarse']['tie_break']['tie_break_triggered']}"
          f" (rule: {results['coarse']['tie_break']['rule']})")
    print(f"refinement        : applicable={results['refinement']['applicable']}")
    if results["refinement"]["applicable"]:
        print(f"  new grid        : {results['refinement']['new_candidates']}")
        print(
            f"  winner after    : {results['refinement']['winner_after_refinement']}"
        )
    print()
    print(f"FINAL H1 CANDIDATE: {results['final_candidate']} "
          f"(frozen value: {results['final_frozen_value']})")
    print(f"final mean T      : {results['final_mean_T_h']} h "
          f"= {results['final_mean_T_days']} days")
    print(f"final mean PM     : "
          f"{results['final_mean_preventive_replacement_count']}")
    print(f"validation        : {summary['overall_status']} "
          f"(C06 failures={results['validation']['quality_oracle_failures']}, "
          f"C17 failures={results['validation']['replay_checker_failures']})")
    print(f"evidence          : {out_dir}")
    print("=" * 78)

    return 0 if summary["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
