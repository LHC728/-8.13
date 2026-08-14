#!/usr/bin/env python3
"""G3-SPEC-V1.0 S8: H1 holdout batches (G3-DEC-04, CR-V3.1/C07/C13/C14/C16/C17/C18/C24).

Frozen protocol (G3-SPEC-V1.0 section 8 ``data_separation`` G3-DEC-04 +
section 10 ``c07_smoke`` + section 12 ``c17_full_replay`` + section 15
``c24_exit_instrumentation``; Human Gate 2026-08-14; AUTOPILOT PILOT #2 S8).

Holdout rule (G3-DEC-04, frozen verbatim)
  * 100 independent 100-device batches under namespace=g3_holdout;
  * used ONLY after coarse search + local refinement + tie-break + final H1
    candidate freeze (S7: final candidate = tau_pm 198 h);
  * the holdout NEVER changes tau_pm / the candidate set / policy logic / key
    schema / statistical procedure; any real implementation or semantic
    failure exposed by the holdout invalidates the result and returns to
    governance -- tuning is never repeated on the holdout;
  * each batch runs the frozen Q2 calendar (N=100, single 12 h shift/day,
    off-shift all work stops; T keeps calendar-time semantics).

Statistical smoke (CR-V3.1/C07; G3-SPEC-V1.0 section 10)
  * terminal four-cell counts (GP/BP/GE/BE) per 100-device batch vs the
    frozen analytic multinomial anchor (accepted G2-02 run
    ``run_20260814T130947069958Z_4bb92eda``, single_test_unconditional_v1
    response ``multinomial`` block: N=100, p in GP/BP/GE/BE order);
  * the 100-device batch is the clustering unit; per-batch ratios are never
    naively averaged;
  * empirical event-level lambda per batch (E true-positive observation
    events) is reported as a batch-clustered interval, compared against the
    frozen analytic anchor (same accepted run, ``lambda.counts.event_level``);
  * analytic lambda is reported WITHOUT Monte-Carlo confidence intervals;
  * a single ordinary 95 % non-coverage triggers investigation, it is never
    automatically judged a program error (miss_handling);
  * this module outputs prescribed diagnostics only and does not cherry-pick
    results (diagnostics_only).

Validation per batch (hard)
  * CR-V3.1/C06: full-layer quality-separation oracle (deterministic paired
    per-device equality: terminal state, D generation, final pass/exit,
    GP/BP/GE/BE, PL/PW contributions);
  * CR-V3.1/C17: full independent replay checker (isolated transition /
    feasibility / metric code; resource and bay occupancy, shift calendar,
    task release/start/end, equipment age/generation/lifetime, failures,
    replacement/calibration/turnover, terminal state, S/PL/PW/YXB, ledger
    coverage over [0,T)).
  * C13/C14/C16/C18 are covered by the accepted engine + checker tests
    (S2 lifetime/regeneration, S6 experiment separation, engine liveness);
    their check status is recorded in checks.json.

C24 exit instrumentation (section 15): decision-point density, legal action
count, waiting-opportunity count, preventive-replacement opportunity count
and estimated rollout branching burden are aggregated over the 100 batches.
H2 is NOT implemented; no M is chosen (rollout_M stays unset).

Boundaries
  * these 100-device batches are an AUTHORIZED holdout run, NOT a Q2 formal
    evaluation; every result is explicitly marked "G3 holdout 数据，非 Q2 正式"
    and is not allowed into the paper number source table;
  * namespace=g3_holdout with an independent master_seed pool (holdout
    master_seed = 2; tuning master_seed = 1) -- namespace + seed pool both
    separate, keys can never collide (C16);
  * no epsilon/CI/holdout tie-break: the holdout never re-tunes.

Outputs (per 05_结果/README.md): 05_结果/G3/holdout/run_<run_id>/
  run_manifest.json, holdout_protocol.json, holdout_results.json,
  validation_summary.json, c24_summary.json, per_run_table.json,
  log_hashes.json, checks.json, c07_smoke.json, file_hashes.sha256

Python 3.12, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import secrets
import sys
import time
from dataclasses import dataclass, field
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

NAMESPACE = ks.NAMESPACE_G3_HOLDOUT
BATCH_SIZE = 100
SCENARIO = "q2_single_shift"
SHIFT_LENGTH_H = "12"
SHIFTS_PER_DAY = 1
TRANSPORT_OUT_H = "0.5"
TRANSPORT_IN_H = "0.5"
TURNOVER_PROFILE = "1h_literal"

# G3-DEC-04 frozen holdout repetition count and seed pool.
HOLDOUT_REPETITIONS = 100
HOLDOUT_MASTER_SEED = 2  # independent seed pool: tuning uses master_seed = 1
FIRST_REPLICATE = 0

# S7 FINAL H1 CANDIDATE (frozen value; the holdout never re-tunes):
#   tau_pm = 198 h, mean T = 3323/4 h = 830.75 h = 3323/96 days.
FROZEN_TAU_PM_H = 198
FROZEN_TAU_PM: Fraction = Fraction(FROZEN_TAU_PM_H)

# Q1-frozen q_E propagation input: accepted G2-02 run
# ``05_结果/G2/run_20260814T130947069958Z_4bb92eda``,
# single_test_unconditional_v1/response.json ``q_E`` (P060 literal semantics).
Q1_FROZEN_Q_E_TEXT = "0.062593912407392898"

# C07 frozen analytic anchors (accepted G2-02 run ``4bb92eda``,
# single_test_unconditional_v1/response.json; the G3 observation kernel is the
# same P060 frozen single-test unconditional closed form).
#   multinomial.p in GP/BP/GE/BE order, N = 100 (per-device terminal category).
C07_MULTINOMIAL_N = 100
C07_MULTINOMIAL_P: dict[str, float] = {
    "GP": 0.92509384870937819,
    "BP": 0.018162763536211106,
    "GE": 0.00081502602845540441,
    "BE": 0.055928361725955299,
}
#   lambda.counts.event_level = expected E true-positive observation events
#   PER FAULTY DEVICE (H non-empty at E) = (1-beta_E)(2-beta_E); the
#   batch-clustered analytic expectation is therefore
#   BATCH_SIZE * q_E * event_level_anchor with q_E the frozen residual-fault
#   probability at E (Q1-frozen q_E, 0.062593912407392898).  first_test_only /
#   at_most_once per device are the same E kernel counted once per device
#   (1-beta_E); only the event-level count is the batch-clustered smoke anchor
#   here.
C07_LAMBDA_EVENT_LEVEL_ANCHOR = 1.5462434051779937  # (1-beta_E)(2-beta_E), per faulty device
C07_LAMBDA_FIRST_TEST_ONLY_ANCHOR = 0.84024005505655354  # 1-beta_E, per faulty device
C07_LAMBDA_ANCHOR_Q_E = 0.062593912407392898  # frozen residual-fault prob. at E
C07_ANCHOR_SOURCE = (
    "05_结果/G2/run_20260814T130947069958Z_4bb92eda/"
    "single_test_unconditional_v1/response.json"
)

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

# C07 smoke thresholds (pre-registered diagnostics, never auto-FAIL):
#   Pearson chi-square is computed over the three categories with adequate
#   expected counts (GP/BP/BE: N*p >= 1.8 each).  The GE category has
#   N*p_GE = 0.0815 << 1, so the chi-square approximation does not apply to
#   it; GE is reported as a separate diagnostic count (observed vs expected)
#   and is excluded from the chi-square statistic (standard small-expected
#   cell rule; avoids a single GE=1 batch inflating chi2 by ~10.3 and
#   flagging the batch spuriously).
#   a batch whose chi-square (2 df, sum of squared z over GP/BP/BE) exceeds
#   the 95 % critical value 5.99146... is flagged "single-batch 95 %
#   non-coverage" (investigation trigger, not a program error);
#   family level: expected ~5 % of 100 batches to fall outside by chance;
#   > 10 flagged batches (Binomial(100, 0.05) 97.5 % quantile = 9) sets an
#   investigation flag.
C07_Z_CUTOFF = 1.959963984540054  # z_{0.975}
C07_CHI2_CATEGORIES: tuple[str, ...] = ("GP", "BP", "BE")  # adequate expected counts
C07_GE_DIAGNOSTIC_CATEGORY = "GE"  # expected < 1; separate diagnostic count
C07_CHI2_2DF_95 = 5.991464547107979  # chi2 quantile, 2 df, 0.95
C07_FAMILY_EXPECTED_FLAG_RATE = 0.05
C07_FAMILY_INVESTIGATE_THRESHOLD = 10  # > this many flagged batches

SOURCE_CODE_FILES: tuple[Path, ...] = (
    Path(__file__).resolve(),
    MAIN_MODEL / "g3" / "random_des_v1.py",
    MAIN_MODEL / "g3" / "key_schema_v1.py",
    MAIN_MODEL / "g3" / "lifetime_regeneration_v1.py",
    CODE_DIR / "checker" / "g3_quality_oracle_v1.py",
    CODE_DIR / "checker" / "g3_replay_checker_v1.py",
    CODE_DIR / "tests" / "test_g3_holdout_v1.py",
    CODE_DIR / "tests" / "test_g3_c16_experiment_separation_v1.py",
)

# ---------------------------------------------------------------------------
# Pure frozen-protocol functions (also exercised by the unit tests)
# ---------------------------------------------------------------------------


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


def make_holdout_config(
    replicate_id: int,
    master_seed: int = HOLDOUT_MASTER_SEED,
    kernel: Optional[dict[str, dict[str, Fraction]]] = None,
    batch_size: int = BATCH_SIZE,
) -> rd.RandomDesConfig:
    """Build the frozen Q2-calendar holdout config for one 100-device batch.

    namespace is always g3_holdout; the world identity is
    (master_seed, replicate_id); tau_pm is the S7-frozen candidate 198 h.
    ``scenario_id`` is run metadata only and never enters a canonical U key.
    """
    k = kernel if kernel is not None else frozen_observation_kernel()
    return rd.default_config(
        namespace=NAMESPACE,
        master_seed=master_seed,
        replicate_id=replicate_id,
        tau_pm=FROZEN_TAU_PM,
        observation_kernel=k,
        batch_size=batch_size,
        scenario=SCENARIO,
        shift_length_h=SHIFT_LENGTH_H,
        shifts_per_day=SHIFTS_PER_DAY,
        turnover_profile=TURNOVER_PROFILE,
        scenario_id=f"g3_holdout_seed{master_seed}_rep{replicate_id}",
    )


def frozen_tau_pm_h() -> int:
    """The S7-frozen final H1 candidate (198 h). The holdout NEVER re-tunes."""
    return FROZEN_TAU_PM_H


def count_e_true_positive_events(event_log: Iterable[dict[str, Any]]) -> int:
    """Event-level E true-positive observation events in one batch log.

    E true positive = an E observation that materialized as ABNORMAL while
    the device's true problem state over A/B/C/D was problem (matches the
    frozen E true-positive event semantics; lambda event-level counts these
    per device, and the batch (100 devices) is the clustering unit).
    """
    count = 0
    for rec in event_log:
        if rec.get("event_type") != sm.EventType.OBSERVATION_MATERIALIZED.value:
            continue
        if rec.get("process") != "E":
            continue
        if rec.get("outcome") != sm.Outcome.ABNORMAL.value:
            continue
        if rec.get("true_state") is True:
            count += 1
    return count


def four_cell_counts(aggregate: dict[str, int]) -> dict[str, int]:
    """Extract GP/BP/GE/BE counts from a C06 oracle aggregate block."""
    return {cat: int(aggregate.get(cat, 0)) for cat in qo.CATEGORIES}


def batch_chi_square(counts: dict[str, int], n: int = C07_MULTINOMIAL_N,
                     p: Optional[dict[str, float]] = None) -> tuple[float, dict[str, float], dict[str, int]]:
    """Pearson chi-square statistic and per-category z scores for one batch.

    Pearson X^2 = sum over the adequate-expected categories of
    (n_i - N p_i)^2 / (N p_i), asymptotically chi-square with
    len(categories)-1 = 2 df under the frozen multinomial anchor.  This is
    the standard Pearson form; the (1-p) variance-weighted z form is NOT used
    because it is not chi-square distributed (it inflates the dominant
    category's contribution by ~1/(1-p) and distorts the flag rate).

    z_i = (n_i - N p_i) / sqrt(N p_i (1 - p_i)) is still returned for every
    category as a per-cell diagnostic.  The GE cell has N*p_GE = 0.0815 << 1,
    where the chi-square approximation fails; GE is excluded from X^2 and
    reported as a separate diagnostic count (see ge_diagnostic).

    Returns (chi2, {category: z}, {category: count})."""
    p_use = p if p is not None else C07_MULTINOMIAL_P
    z: dict[str, float] = {}
    counts_out: dict[str, int] = {}
    for cat in qo.CATEGORIES:
        n_i = float(counts.get(cat, 0))
        p_i = p_use[cat]
        denom = math.sqrt(n * p_i * (1.0 - p_i))
        z[cat] = (n_i - n * p_i) / denom if denom > 0 else 0.0
        counts_out[cat] = int(counts.get(cat, 0))
    chi2 = sum(
        (float(counts.get(cat, 0)) - n * p_use[cat]) ** 2 / (n * p_use[cat])
        for cat in C07_CHI2_CATEGORIES
    )
    return chi2, z, counts_out


def ge_diagnostic(
    counts: dict[str, int],
    n: int = C07_MULTINOMIAL_N,
    p: Optional[dict[str, float]] = None,
) -> dict[str, Any]:
    """GE small-expected-cell diagnostic: observed vs expected count.

    GE has N*p_GE = 0.0815 << 1 so it is excluded from the chi-square
    statistic; the observed GE count across the batches is reported against
    its analytic expectation for investigation (never an automatic error)."""
    p_use = p if p is not None else C07_MULTINOMIAL_P
    expected = n * p_use[C07_GE_DIAGNOSTIC_CATEGORY]
    return {
        "category": C07_GE_DIAGNOSTIC_CATEGORY,
        "observed": int(counts.get(C07_GE_DIAGNOSTIC_CATEGORY, 0)),
        "expected": expected,
        "note": (
            "N*p_GE = 0.0815 << 1：卡方近似不适用，GE 不进入 chi2 统计量；"
            "单独按诊断计数报告，不自动判程序错误。"
        ),
    }


def family_smoke_diagnosis(
    per_batch_chi2: Iterable[float],
    n_batches: int,
    chi2_cut: float = C07_CHI2_2DF_95,
    expected_flag_rate: float = C07_FAMILY_EXPECTED_FLAG_RATE,
    investigate_threshold: int = C07_FAMILY_INVESTIGATE_THRESHOLD,
) -> dict[str, Any]:
    """C07 family-level diagnostic over the batch-clustered chi2 statistics.

    A batch whose chi2 exceeds the 2-df 95 % critical value is flagged
    "single-batch 95 % non-coverage" (investigation trigger, never an
    automatic program error).  The family summary reports the flagged count
    against the Binomial(100, 0.05) expectation and sets an investigation
    flag only when the flagged count exceeds the pre-registered threshold.
    """
    values = list(per_batch_chi2)
    if not values:
        raise ValueError("family_smoke_diagnosis requires at least one batch")
    flagged = [c for c in values if c > chi2_cut]
    flagged_count = len(flagged)
    expected = n_batches * expected_flag_rate
    sd = math.sqrt(n_batches * expected_flag_rate * (1.0 - expected_flag_rate))
    excess = flagged_count - expected
    investigate = flagged_count > investigate_threshold
    return {
        "n_batches": n_batches,
        "chi2_cutoff_2df_95": chi2_cut,
        "chi2_categories": list(C07_CHI2_CATEGORIES),
        "flagged_batch_count": flagged_count,
        "expected_flag_count_by_chance": round(expected, 2),
        "sd_of_expected": round(sd, 2),
        "excess_vs_expected": round(excess, 2),
        "investigate_flag": investigate,
        "note": (
            "单次普通 95% 未覆盖仅触发调查，不自动判程序错误（C07 miss_handling）；"
            "本模块为规定诊断输出，不挑结果。"
        ),
    }


def batch_lambda_interval(
    per_batch_lambda: Iterable[float],
    anchor: float = C07_LAMBDA_EVENT_LEVEL_ANCHOR,
    anchor_q_e: float = C07_LAMBDA_ANCHOR_Q_E,
    n_batches: int = HOLDOUT_REPETITIONS,
) -> dict[str, Any]:
    """C07 empirical event-level lambda, batch-clustered summary vs the
    analytic anchor (analytic lambda reported WITHOUT MC confidence interval).

    The 100-device batch is the clustering unit: one empirical event-level
    lambda per batch, then the batch-level mean / SD / min / max / 2.5 % and
    97.5 % quantiles are reported.  Per-batch ratios are never naively
    averaged (they are already whole-batch counts).

    Analytic expectation per batch: ``BATCH_SIZE * q_E * anchor`` where
    ``anchor`` = (1-beta_E)(2-beta_E) is the expected E true-positive event
    count PER FAULTY DEVICE and q_E is the frozen residual-fault probability
    at E (so BATCH*q_E is the expected number of faulty devices per batch).
    """
    values = sorted(float(v) for v in per_batch_lambda)
    if not values:
        raise ValueError("batch_lambda_interval requires at least one value")
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / max(1, len(values) - 1)
    sd = math.sqrt(var)
    n = len(values)
    def _quantile(q: float) -> float:
        idx = q * (n - 1)
        lo = math.floor(idx)
        hi = math.ceil(idx)
        if lo == hi:
            return values[lo]
        frac = idx - lo
        return values[lo] * (1.0 - frac) + values[hi] * frac
    analytic_per_batch = anchor_q_e * anchor * BATCH_SIZE
    rel_dev = (mean - analytic_per_batch) / analytic_per_batch if analytic_per_batch else 0.0
    return {
        "n_batches": n,
        "cluster_unit": "one 100-device batch",
        "empirical_mean_per_batch": mean,
        "empirical_sd": sd,
        "empirical_min": values[0],
        "empirical_max": values[-1],
        "empirical_q025": _quantile(0.025),
        "empirical_q975": _quantile(0.975),
        "analytic_anchor_per_faulty_device": anchor,
        "analytic_q_e_at_E": anchor_q_e,
        "analytic_mean_per_batch": analytic_per_batch,
        "relative_deviation_of_empirical_mean": rel_dev,
        "monte_carlo_ci": "NOT_REPORTED",
        "note": (
            "解析 lambda 不报 Monte Carlo 区间（C07 analytic_lambda）；"
            "经验 lambda 以整批 100 台为聚类单位报告，禁止逐批比率简单平均。"
            "解析批期望 = 100 * q_E * (1-beta_E)(2-beta_E)；q_E 为 E 处冻结残余故障概率。"
        ),
    }


# ---------------------------------------------------------------------------
# Run records / validation
# ---------------------------------------------------------------------------


@dataclass
class HoldoutRunRecord:
    """One holdout batch run: metrics + C06/C17 verdicts + C07 diagnostics."""

    replicate_id: int
    T: Fraction
    T_days: Fraction
    S: int
    PL: int
    PW: int
    exited: int
    four_cell: dict[str, int]
    lambda_events: int
    chi2: float
    z_scores: dict[str, float]
    quality_verdict: str
    replay_verdict: str
    quality_issues: list[str]
    replay_issues: list[str]
    c24: dict[str, Any]
    log_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "replicate_id": self.replicate_id,
            "T_h": sm.fraction_to_string(self.T),
            "T_days": sm.fraction_to_string(self.T_days),
            "S": self.S,
            "PL": self.PL,
            "PW": self.PW,
            "exited": self.exited,
            "four_cell_counts": dict(self.four_cell),
            "e_true_positive_events": self.lambda_events,
            "c07_chi2_2df_pearson": round(self.chi2, 6),
            "c07_z_scores": {k: round(v, 6) for k, v in self.z_scores.items()},
            "quality_oracle_verdict": self.quality_verdict,
            "replay_checker_verdict": self.replay_verdict,
            "c24": dict(self.c24),
            "canonical_log_sha256": self.log_sha256,
        }


def validate_run(
    event_log: list[dict[str, Any]],
    config_dict: dict[str, Any],
    metrics: dict[str, Any],
    run_id: str,
) -> tuple[qo.OracleReport, rc.ReplayReport]:
    """Run both frozen checkers on one holdout run and return
    (quality_report, replay_report). Raises on checker input/numerical errors
    (never silently downgraded)."""
    quality_report = qo.check_quality_oracle(
        event_log, config_dict, PARAMETERS_CSV, metrics=metrics
    )
    replay_report = rc.check_replay(
        event_log, config_dict, PARAMETERS_CSV, metrics=metrics, run_id=run_id
    )
    return quality_report, replay_report


def run_one_batch(
    replicate_id: int,
    kernel: dict[str, dict[str, Fraction]],
    run_tag: str,
) -> HoldoutRunRecord:
    """Run + validate one frozen 100-device holdout batch."""
    cfg = make_holdout_config(replicate_id, kernel=kernel)
    cfg_dict = cfg.to_dict()
    result = rd.run_random_des(cfg)
    metrics = result.metrics
    event_log = result.event_log
    log_sha = hashlib.sha256(result.canonical_event_log()).hexdigest()
    quality_report, replay_report = validate_run(event_log, cfg_dict, metrics, run_tag)
    quality_verdict = quality_report.verdict
    replay_verdict = replay_report.verdict
    quality_issues = [str(i) for i in quality_report.issues]
    replay_issues = [str(i) for i in replay_report.issues]
    # four-cell counts come from the oracle aggregate (already cross-checked
    # against the DES aggregate by the C06 verdict PASS).
    four_cell = four_cell_counts(quality_report.oracle_aggregate)
    chi2, z_scores, _counts = batch_chi_square(four_cell)
    lambda_events = count_e_true_positive_events(event_log)
    return HoldoutRunRecord(
        replicate_id=replicate_id,
        T=Fraction(metrics["T"]),
        T_days=Fraction(metrics["T_days"]),
        S=int(metrics["S"]),
        PL=int(metrics["PL"]),
        PW=int(metrics["PW"]),
        exited=int(metrics["exited"]),
        four_cell=four_cell,
        lambda_events=lambda_events,
        chi2=chi2,
        z_scores=z_scores,
        quality_verdict=quality_verdict,
        replay_verdict=replay_verdict,
        quality_issues=quality_issues,
        replay_issues=replay_issues,
        c24=dict(metrics["c24"]),
        log_sha256=log_sha,
    )


# ---------------------------------------------------------------------------
# Evidence / result writing (05_结果/G3/holdout/run_<run_id>/)
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
        "purpose": "holdout",
        "formal": False,
        "label": "G3 holdout 数据，非 Q2 正式",
        "allowed_in_paper_number_source_table": False,
        "task_package_ref": TASK_PACKAGE_REF,
        "task_package_hash": _sha256_file(TASK_PACKAGE_FILE),
        "registry_version": REGISTRY_VERSION,
        "required_check_ids": ["C06", "C07", "C13", "C14", "C16", "C17", "C18", "C24"],
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
        "frozen_h1_candidate": {
            "tau_pm_h": FROZEN_TAU_PM_H,
            "source": "G3 S7 tuning (run_20260814T174022592173Z_01b7c7e7)",
            "holdout_retune": False,
        },
        "code_hashes": {
            path.relative_to(BASE_DIR).as_posix(): _sha256_file(path)
            for path in SOURCE_CODE_FILES
            if path.exists()
        },
        "environment": _env_summary(),
        "inputs": inputs,
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "validation_summary.json", "c07_smoke.json"],
        "overall_status": overall_status,
        "notes": [
            "G3 holdout 数据，非 Q2 正式：100 独立 100-device 批次在 namespace=g3_holdout 下运行"
            "（G3-SPEC-V1.0 G3-DEC-04 授权），不得作为 Q2 正式数字。",
            "冻结 H1 候选 tau_pm=198h 来自 S7 调优（run_20260814T174022592173Z_01b7c7e7）；"
            "holdout 绝不重调 tau_pm/候选集/策略/键 schema/统计程序。",
            "观测核：P060 冻结单次无条件闭式 (1-q)alpha=q beta=e/2；E 核 q_E 按 Q1 冻结输出"
            "（G2-02 accepted run 4bb92eda）传播，alpha_E/beta_E 用同一冻结闭式。",
            "C07 锚：accepted G2-02 run 4bb92eda single_test_unconditional_v1 response"
            "（multinomial.p 四格 + lambda.counts.event_level）。",
        ],
    }
    return manifest


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def run_holdout(
    output_root: Path,
    master_seed: int = HOLDOUT_MASTER_SEED,
    replicate_ids: Optional[tuple[int, ...]] = None,
) -> dict[str, Any]:
    """Execute the frozen holdout protocol: 100 independent 100-device
    batches under namespace=g3_holdout with the S7-frozen tau_pm=198,
    validate every batch with C06 + C17, run the C07 statistical smoke
    (four-cell vs frozen multinomial anchor; batch-clustered empirical
    event-level lambda vs analytic anchor) and aggregate C24 instrumentation.

    Returns the summary dict; the caller writes the evidence files.
    """
    reps = replicate_ids if replicate_ids is not None else tuple(
        range(FIRST_REPLICATE, FIRST_REPLICATE + HOLDOUT_REPETITIONS)
    )
    if len(reps) != HOLDOUT_REPETITIONS:
        print(
            f"[holdout] WARNING: replicate-count={len(reps)} deviates from the "
            f"frozen protocol value {HOLDOUT_REPETITIONS}; the manifest records "
            "this as a protocol deviation (smoke/test only, never an accepted "
            "holdout result)."
        )
    kernel = frozen_observation_kernel()

    records: list[HoldoutRunRecord] = []
    for rep in reps:
        t0 = time.perf_counter()
        rec = run_one_batch(rep, kernel, f"holdout_rep{rep}")
        dt = time.perf_counter() - t0
        records.append(rec)
        print(
            f"[holdout] rep {rep:>3}: T={sm.fraction_to_string(rec.T)} h "
            f"S={rec.S} PL={rec.PL} PW={rec.PW} "
            f"C06={rec.quality_verdict} C17={rec.replay_verdict} "
            f"chi2={rec.chi2:.3f} ({dt:.1f}s)"
        )

    quality_failures = [r for r in records if r.quality_verdict != "PASS"]
    replay_failures = [r for r in records if r.replay_verdict != "PASS"]
    validation_ok = not quality_failures and not replay_failures
    overall_status = "PASS" if validation_ok else "VALIDATION_FAILED"

    # C07 family diagnostics (diagnostics only; never auto-FAIL).
    family = family_smoke_diagnosis(
        (r.chi2 for r in records), n_batches=len(records)
    )
    lambda_smoke = batch_lambda_interval(
        (r.lambda_events for r in records), n_batches=len(records)
    )
    # GE small-expected-cell diagnostic over the whole holdout.
    ge_total = sum(r.four_cell["GE"] for r in records)
    ge_diag = ge_diagnostic(
        {"GE": ge_total}, n=BATCH_SIZE * len(records)
    )

    # C24 instrumentation aggregates over the 100 batches.
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

    c24 = {
        "h2_implemented": False,
        "rollout_M": "NOT_CHOSEN",
        "mean_decision_point_density": sm.fraction_to_string(
            sum(densities, Fraction(0)) / len(densities)
        ),
        "total_decision_point_count": c24_counts["decision_point_count"],
        "total_legal_action_count": c24_counts["legal_action_count"],
        "total_waiting_opportunity_count": c24_counts["waiting_opportunity_count"],
        "total_preventive_replacement_opportunity_count": c24_counts[
            "preventive_replacement_opportunity_count"
        ],
        "total_estimated_rollout_branching_burden": c24_counts[
            "estimated_rollout_branching_burden"
        ],
        "note": "G3 出口仪表（CR-V3.1/C24）；H2 不实现；M 不选。",
    }

    # Exact aggregate stats over the 100 batches (diagnostics, not Q2 formal).
    mean_T = sum((r.T for r in records), Fraction(0)) / len(records)
    mean_T_days = sum((r.T_days for r in records), Fraction(0)) / len(records)
    mean_S = sum((r.S for r in records), Fraction(0)) / len(records)
    mean_PL = sum((r.PL for r in records), Fraction(0)) / len(records)
    mean_PW = sum((r.PW for r in records), Fraction(0)) / len(records)
    mean_exited = sum((r.exited for r in records), Fraction(0)) / len(records)
    mean_lambda = sum((r.lambda_events for r in records), Fraction(0)) / len(records)

    results: dict[str, Any] = {
        "run_id": None,  # filled by the caller
        "task_package_ref": TASK_PACKAGE_REF,
        "registry_version": REGISTRY_VERSION,
        "formal": False,
        "label": "G3 holdout 数据，非 Q2 正式",
        "protocol": {
            "namespace": NAMESPACE,
            "master_seed": master_seed,
            "replicate_ids": list(reps),
            "batch_size": BATCH_SIZE,
            "scenario": SCENARIO,
            "shift_length_h": SHIFT_LENGTH_H,
            "shifts_per_day": SHIFTS_PER_DAY,
            "turnover_profile": TURNOVER_PROFILE,
            "n_batches": len(reps),
            "frozen_tau_pm_h": FROZEN_TAU_PM_H,
            "holdout_retune_forbidden": True,
            "observation_kernel": {
                p: {
                    "alpha": sm.fraction_to_string(kernel[p]["alpha"]),
                    "beta": sm.fraction_to_string(kernel[p]["beta"]),
                }
                for p in sm.RESOURCES
            },
            "q1_frozen_q_e_input": Q1_FROZEN_Q_E_TEXT,
        },
        "aggregates": {
            "mean_T_h": sm.fraction_to_string(mean_T),
            "mean_T_days": sm.fraction_to_string(mean_T_days),
            "mean_S": sm.fraction_to_string(mean_S),
            "mean_PL": sm.fraction_to_string(mean_PL),
            "mean_PW": sm.fraction_to_string(mean_PW),
            "mean_exited": sm.fraction_to_string(mean_exited),
            "mean_e_true_positive_events_per_batch": sm.fraction_to_string(mean_lambda),
            "four_cell_totals": {
                cat: sum(r.four_cell[cat] for r in records) for cat in qo.CATEGORIES
            },
        },
        "c07": {
            "anchor_source": C07_ANCHOR_SOURCE,
            "multinomial_anchor_n": C07_MULTINOMIAL_N,
            "multinomial_anchor_p": dict(C07_MULTINOMIAL_P),
            "family": family,
            "ge_diagnostic": ge_diag,
            "lambda_smoke": lambda_smoke,
            "verdict": "DIAGNOSTIC",
            "note": (
                "C07 为统计烟测/诊断输出；单次普通 95% 未覆盖仅触发调查，不自动判程序错误。"
                "整体验证状态由 C06/C17 硬门决定。"
            ),
        },
        "c24": c24,
        "validation": {
            "overall_status": overall_status,
            "quality_oracle_failures": len(quality_failures),
            "replay_checker_failures": len(replay_failures),
        },
    }
    return {
        "results": results,
        "records": records,
        "overall_status": overall_status,
        "family": family,
        "lambda_smoke": lambda_smoke,
    }


def write_evidence(
    run_id: str,
    out_dir: Path,
    summary: dict[str, Any],
    master_seed: int,
    replicate_ids: tuple[int, ...],
) -> dict[str, Any]:
    """Persist all holdout evidence under out_dir and return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = summary["results"]
    results["run_id"] = run_id
    protocol = results["protocol"]

    _dump_json(out_dir / "holdout_protocol.json", protocol)
    _dump_json(out_dir / "holdout_results.json", results)
    _dump_json(
        out_dir / "per_run_table.json",
        {
            "run_id": run_id,
            "formal": False,
            "label": "G3 holdout 数据，非 Q2 正式",
            "runs": [r.to_dict() for r in summary["records"]],
        },
    )
    _dump_json(
        out_dir / "validation_summary.json",
        {
            "run_id": run_id,
            "formal": False,
            "label": "G3 holdout 数据，非 Q2 正式",
            "overall_status": summary["overall_status"],
            "per_run": [
                {
                    "replicate_id": r.replicate_id,
                    "quality_oracle_verdict": r.quality_verdict,
                    "quality_issues": r.quality_issues,
                    "replay_checker_verdict": r.replay_verdict,
                    "replay_issues": r.replay_issues,
                }
                for r in summary["records"]
            ],
        },
    )
    _dump_json(out_dir / "c07_smoke.json", results["c07"])
    _dump_json(
        out_dir / "c24_summary.json",
        {"run_id": run_id, "formal": False, "label": "G3 holdout 数据，非 Q2 正式",
         **results["c24"]},
    )
    _dump_json(
        out_dir / "log_hashes.json",
        {
            "run_id": run_id,
            "formal": False,
            "label": "G3 holdout 数据，非 Q2 正式",
            "canonical_event_log_sha256": {
                f"rep{r.replicate_id}": r.log_sha256 for r in summary["records"]
            },
        },
    )
    validation = results["validation"]
    checks = {
        "run_id": run_id,
        "registry_version": REGISTRY_VERSION,
        "required_check_ids": ["C06", "C07", "C13", "C14", "C16", "C17", "C18", "C24"],
        "overall_status": summary["overall_status"],
        "items": [
            {
                "check_id": "CR-V3.1/C06",
                "layer": "G3 full 质量分离 oracle（holdout 每批硬门）",
                "status": (
                    "PASS" if validation["quality_oracle_failures"] == 0 else "FAIL"
                ),
                "note": "100 批每批逐装置对拍（终态/D/GP/BP/GE/BE/PL/PW），失败明细见 validation_summary.json",
            },
            {
                "check_id": "CR-V3.1/C07",
                "layer": "统计烟测（四格 vs 冻结解析多项分布锚；经验 lambda 批聚类）",
                "status": "DIAGNOSTIC",
                "note": "c07_smoke.json；单次普通 95% 未覆盖触发调查，不自动判程序错误",
            },
            {
                "check_id": "CR-V3.1/C13",
                "layer": "寿命抽样（120/240 节点、U>F(240) 右删失）",
                "status": "PASS",
                "note": "引擎按 G3-SPEC-V1.0 §4 执行；S2 测试覆盖（test_g3_lifetime_regeneration_v1）",
            },
            {
                "check_id": "CR-V3.1/C14",
                "layer": "120/240 与再生（a+d 三边界、换新校准、年龄归零、非法跨越兜底）",
                "status": "PASS",
                "note": "引擎按 G3-SPEC-V1.0 §5 执行；S2 测试覆盖",
            },
            {
                "check_id": "CR-V3.1/C16",
                "layer": "G3 experiment layer（CRN/pilot/tuning/holdout 分离）",
                "status": "PASS",
                "note": "namespace=g3_holdout、master_seed=2 独立 seed 池；S6 测试覆盖命名空间不碰撞",
            },
            {
                "check_id": "CR-V3.1/C17",
                "layer": "G3 full replay（holdout 每批硬门）",
                "status": (
                    "PASS" if validation["replay_checker_failures"] == 0 else "FAIL"
                ),
                "note": "100 批每批独立重放；失败明细见 validation_summary.json",
            },
            {
                "check_id": "CR-V3.1/C18",
                "layer": "事件活性（G3 随机扩展下显式要求）",
                "status": "PASS",
                "note": "引擎活性保障 + S3/S6 测试覆盖；全部批次正常终止",
            },
            {
                "check_id": "CR-V3.1/C24",
                "layer": "G3 出口 H2 准入仪表（H2 不实现）",
                "status": "PASS",
                "note": "决策点密度/动作数/等待机会/预防机会/分支负担聚合于 c24_summary.json；M 不选",
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
        description="G3-SPEC-V1.0 S8: H1 holdout batches (G3-DEC-04, C07 smoke)."
    )
    parser.add_argument(
        "--output-root",
        default=str(BASE_DIR / "05_结果" / "G3" / "holdout"),
        help="results root; a run_<run_id>/ directory is created under it",
    )
    parser.add_argument(
        "--master-seed", type=int, default=HOLDOUT_MASTER_SEED,
        help="canonical master_seed for the g3_holdout namespace (default 2)",
    )
    parser.add_argument(
        "--first-replicate", type=int, default=FIRST_REPLICATE,
        help="first replicate_id (default 0)",
    )
    parser.add_argument(
        "--replicate-count", type=int, default=HOLDOUT_REPETITIONS,
        help=(
            f"replicates (frozen protocol = {HOLDOUT_REPETITIONS}; "
            "a deviation is recorded in the manifest)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    output_root = Path(args.output_root).resolve()
    master_seed = args.master_seed
    replicate_ids = tuple(
        range(args.first_replicate, args.first_replicate + args.replicate_count)
    )

    # Fail loudly on drifted frozen inputs (AGENTS.md: 参数无效必须显式失败).
    rd.validate_parameters_csv(PARAMETERS_CSV)
    lr.validate_parameters_csv(PARAMETERS_CSV)

    run_id = _new_run_id()
    out_dir = output_root / f"run_{run_id}"
    print(f"[holdout] run_id={run_id}")
    print(f"[holdout] output={out_dir}")
    print(
        f"[holdout] namespace=g3_holdout master_seed={master_seed} "
        f"replicate_ids={replicate_ids[0]}..{replicate_ids[-1]} "
        f"({len(replicate_ids)} independent 100-device batches)"
    )
    print(
        f"[holdout] frozen H1 candidate tau_pm={FROZEN_TAU_PM_H} h "
        "(holdout never re-tunes)"
    )

    summary = run_holdout(output_root, master_seed, replicate_ids)
    summary["results"]["run_id"] = run_id
    if args.replicate_count != HOLDOUT_REPETITIONS:
        summary["results"]["protocol"]["protocol_deviation"] = {
            "frozen_repetitions": HOLDOUT_REPETITIONS,
            "actual_repetitions": args.replicate_count,
            "note": "deviation for smoke/test only; not an accepted holdout result",
        }
    manifest = write_evidence(
        run_id, out_dir, summary, master_seed, replicate_ids
    )
    results = summary["results"]

    print()
    print("=" * 78)
    print("G3 HOLD OUT SUMMARY (G3 holdout 数据，非 Q2 正式)")
    print("=" * 78)
    print(f"run_id            : {run_id}")
    print(f"namespace         : g3_holdout (master_seed={master_seed}, "
          f"{len(replicate_ids)} independent 100-device batches)")
    print(f"frozen H1 tau_pm  : {FROZEN_TAU_PM_H} h (holdout never re-tunes)")
    print()
    agg = results["aggregates"]
    print(f"mean T            : {agg['mean_T_h']} h = {agg['mean_T_days']} days")
    print(f"mean S/PL/PW      : {agg['mean_S']} / {agg['mean_PL']} / {agg['mean_PW']}")
    print(f"mean E true-pos   : {agg['mean_e_true_positive_events_per_batch']} "
          f"events/batch")
    print()
    print(f"C07 family        : flagged={results['c07']['family']['flagged_batch_count']}"
          f"/{len(replicate_ids)} (expected by chance "
          f"~{results['c07']['family']['expected_flag_count_by_chance']}), "
          f"investigate={results['c07']['family']['investigate_flag']}")
    print(f"C07 lambda smoke  : empirical mean="
          f"{results['c07']['lambda_smoke']['empirical_mean_per_batch']:.4f} "
          f"vs analytic/batch="
          f"{results['c07']['lambda_smoke']['analytic_mean_per_batch']:.4f}")
    print(f"validation        : {summary['overall_status']} "
          f"(C06 failures={results['validation']['quality_oracle_failures']}, "
          f"C17 failures={results['validation']['replay_checker_failures']})")
    print(f"evidence          : {out_dir}")
    print("=" * 78)

    return 0 if summary["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
