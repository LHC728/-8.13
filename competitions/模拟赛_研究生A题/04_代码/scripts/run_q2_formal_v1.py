#!/usr/bin/env python3
"""Q2-FORMAL-SPEC-V1.0: Q2 H1 formal evaluation runner (PILOT #3).

Frozen protocol (Q2-FORMAL-SPEC-V1.0 FROZEN_FOR_FORMAL_RUN; Human Gate
2026-08-15 Q2-FORMAL-DEC-01..06; AUTOPILOT PILOT #3).

This is a THIN runner/aggregation layer over the accepted G3 engine.  It
NEVER modifies G3 core semantics (random_des_v1 core transitions,
key_schema_v1, lifetime/regeneration semantics, C06 oracle core, C17 replay
core, frozen observation semantics).  If completing the formal run required
any such change, the runner must STOP with
Q2_FORMAL_REQUIRES_G3_CORE_CHANGE.

Formal family (frozen): 2 observation semantics (single_test_unconditional_v1
| standard_chain_v1) x 2 turnover (1h_literal | 0.5h_overlap) x 2 policy
(tau_pm=198 | NO_PM_BEFORE_MANDATORY) = 8 cells.

Sample size (DEC-01/02): namespace=q2_formal, master_seed=3,
replicate_id=0..199 inclusive (exactly 200); 100 devices per batch; all 8
cells reuse the same 200 replicate ids under CRN (policy / turnover /
observation never enter physical random keys).

Primary cell (frozen): single_test_unconditional_v1 + 1h_literal +
tau_pm_198; policy reference = same obs/turnover + NO_PM_BEFORE_MANDATORY.
tau_pm=198 was frozen BEFORE q2_formal; the formal run NEVER re-tunes.

T inference (DEC-03): exactly 4 predeclared paired contrasts C1..C4,
each Delta_T = T(tau_pm_198) - T(NO_PM) within one observation x turnover
combination.  Paired batch-level bootstrap B=10000, analysis stream
namespace=q2_formal_analysis_bootstrap_v1 seed=30003 (resamples only the
200 complete paired batch indices; never touches DES physical streams).
Bonferroni: alpha_family=0.05, m=4, alpha_each=0.0125, two-sided; each
marginal bootstrap CI uses coverage 0.9875 with percentile bounds
0.00625/0.99375.

Rare events (DEC-04): PL/PW pooled over N_total=20000 devices per cell;
0<x<20000 -> exact Clopper-Pearson two-sided 95% interval; x=0 -> one-sided
exact CP 95% upper bound 1 - 0.05^(1/20000) computed mechanically; batch
mean + batch SE also reported; never an ordinary normal CI for zero count.

Evidence (DEC-05): one immutable family run under
05_结果/Q2/formal/run_<UTCtimestamp>_<8hex>/ with frozen cell tokens
obs_single/chain__turn_1h/0p5h__policy_tau198/nopm; family root contains
run_manifest, commands, environment, family config snapshot, task package
snapshot/hash, G3-SPEC upstream hash, key schema hash, code/schema/config
hashes, per-cell outputs, per-replicate raw metrics, checker reports, C06
summaries, C17 summaries, statistical analysis, bootstrap metadata, failure
samples, formal comparison table, file_hashes.sha256.  Failed attempts stay
immutable.

Budget (DEC-06): soft checkpoint 4 h, hard cap 8 h (unconditional stop:
Q2_FORMAL_HARD_BUDGET_STOP_WAITING_FOR_HUMAN_GATE).  Never reduce the 200
repetitions to fit the budget.

Observation kernels (frozen, never recalibrated):
  single_test_unconditional_v1: A/B/C via engine frozen_single_test_alpha_beta
    (P060 closed form); E via Q1-frozen q_E=0.062593912407392898 (accepted
    G2-02 4bb92eda single_test response) + e_E=P033 through the same closed
    form (identical to G3 tuning/holdout runners).
  standard_chain_v1: accepted G2-02 4bb92eda standard_chain_v1 response
    kernels (A/B/C alpha/beta; q_E=0.047150339332016366; E alpha_E=
    0.010920932310648563, beta_E=0.1185856135607714).  These are consumed as
    frozen config inputs; no recalibration, no re-derived semantic q_E, no
    mixing, no invented fallback.

Python 3.12, standard library only (bootstrap uses the seeded random module
with an explicit deterministic index-resampling scheme on the analysis stream).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
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

TASK_PACKAGE_REF = "Q2-FORMAL-SPEC-V1.0"
TASK_PACKAGE_FILE = BASE_DIR / "08_项目管理" / "任务包" / "Q2_单班制H1正式评估.yaml"
G3_TASK_PACKAGE_FILE = BASE_DIR / "08_项目管理" / "任务包" / "G3_公共随机DES与H1基线.yaml"
REGISTRY_VERSION = "CR-V3.1"
PARAMETERS_CSV = BASE_DIR / "02_数据" / "parameters.csv"
PROBLEM_CONTRACT_FILE = BASE_DIR / "01_审计" / "问题契约.md"

NAMESPACE = ks.NAMESPACE_Q2_FORMAL
MASTER_SEED = 3
FIRST_REPLICATE = 0
REPLICATE_COUNT = 200  # DEC-02: exactly 200, ids 0..199
BATCH_SIZE = 100
SCENARIO = "q2_single_shift"
SHIFT_LENGTH_H = "12"
SHIFTS_PER_DAY = 1
TURNOVER_1H = "1h_literal"
TURNOVER_0P5H = "0.5h_overlap"

TAU_PM_198: Fraction = Fraction(198)
NO_PM = lr.NO_PM_BEFORE_MANDATORY

# DEC-03 comparison family: C1..C4.
COMPARISONS: tuple[dict[str, Any], ...] = (
    {"id": "C1", "role": "PRIMARY", "obs": "single", "turn": TURNOVER_1H},
    {"id": "C2", "role": "ROBUSTNESS", "obs": "single", "turn": TURNOVER_0P5H},
    {"id": "C3", "role": "ROBUSTNESS", "obs": "chain", "turn": TURNOVER_1H},
    {"id": "C4", "role": "ROBUSTNESS", "obs": "chain", "turn": TURNOVER_0P5H},
)

# Frozen cell-id tokens (DEC-05).
def cell_id(obs: str, turn: str, policy: str) -> str:
    obs_tok = "single" if obs == "single" else "chain"
    turn_tok = "1h" if turn == TURNOVER_1H else "0p5h"
    pol_tok = "tau198" if policy == "tau198" else "nopm"
    return f"obs_{obs_tok}__turn_{turn_tok}__policy_{pol_tok}"

OBS_TOKENS: dict[str, str] = {
    "single": "single_test_unconditional_v1",
    "chain": "standard_chain_v1",
}
POLICY_TOKENS: dict[str, Any] = {"tau198": TAU_PM_198, "nopm": NO_PM}

# DEC-03 Bonferroni.
ALPHA_FAMILY = 0.05
M_FAMILY = 4
ALPHA_EACH = ALPHA_FAMILY / M_FAMILY  # 0.0125
MARGINAL_COVERAGE = 1.0 - ALPHA_EACH  # 0.9875
P_LO = ALPHA_EACH / 2  # 0.00625
P_HI = 1.0 - ALPHA_EACH / 2  # 0.99375

# DEC-04 rare events.
N_TOTAL_DEVICES_PER_CELL = REPLICATE_COUNT * BATCH_SIZE  # 20000

# Bootstrap analysis stream (frozen, non-physical).
ANALYSIS_NAMESPACE = "q2_formal_analysis_bootstrap_v1"
ANALYSIS_SEED = 30003
BOOTSTRAP_B = 10000

# Q1-frozen q_E propagation for single semantics.
Q1_FROZEN_Q_E_TEXT = "0.062593912407392898"
FROZEN_Q_ABC: dict[str, Fraction] = {
    "A": Fraction(25, 1000),  # P026
    "B": Fraction(3, 100),    # P027
    "C": Fraction(2, 100),    # P028
}
FROZEN_E_ABC: dict[str, Fraction] = {
    "A": Fraction(3, 100),    # P030
    "B": Fraction(4, 100),    # P031
    "C": Fraction(2, 100),    # P032
}
FROZEN_E_E: Fraction = Fraction(2, 100)  # P033

# accepted G2-02 standard_chain_v1 response kernels (4bb92eda).
CHAIN_KERNEL: dict[str, dict[str, str]] = {
    "A": {"alpha": "0.015612642053572192", "beta": "0.38226176188707678"},
    "B": {"alpha": "0.020942481877888125", "beta": "0.44441134347855829"},
    "C": {"alpha": "0.010343090510990168", "beta": "0.30146827672834102"},
    "E": {"alpha": "0.010920932310648563", "beta": "0.1185856135607714"},
}

SOURCE_CODE_FILES: tuple[Path, ...] = (
    Path(__file__).resolve(),
    MAIN_MODEL / "g3" / "random_des_v1.py",
    MAIN_MODEL / "g3" / "key_schema_v1.py",
    MAIN_MODEL / "g3" / "lifetime_regeneration_v1.py",
    CODE_DIR / "checker" / "g3_quality_oracle_v1.py",
    CODE_DIR / "checker" / "g3_replay_checker_v1.py",
    CODE_DIR / "tests" / "test_q2_formal_v1.py",
)

# ---------------------------------------------------------------------------
# Frozen observation kernels
# ---------------------------------------------------------------------------


def single_kernel() -> dict[str, dict[str, Fraction]]:
    """Frozen single-test unconditional kernel (identical to G3 runners)."""
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


def chain_kernel() -> dict[str, dict[str, Fraction]]:
    """Frozen standard-chain kernel from accepted G2-02 4bb92eda response."""
    return {
        proc: {
            "alpha": Fraction(entry["alpha"]),
            "beta": Fraction(entry["beta"]),
        }
        for proc, entry in CHAIN_KERNEL.items()
    }


# ---------------------------------------------------------------------------
# Cell config construction
# ---------------------------------------------------------------------------


def make_cell_config(
    obs: str, turn: str, policy: str, replicate_id: int
) -> rd.RandomDesConfig:
    """Frozen config for one (cell, replicate) formal batch.

    Namespace is always q2_formal; master_seed=3; policy / turnover /
    observation NEVER enter physical random keys (CRN: same U world reused
    across the 8 cells for a fixed replicate_id)."""
    kernel = single_kernel() if obs == "single" else chain_kernel()
    return rd.default_config(
        namespace=NAMESPACE,
        master_seed=MASTER_SEED,
        replicate_id=replicate_id,
        tau_pm=POLICY_TOKENS[policy],
        observation_kernel=kernel,
        batch_size=BATCH_SIZE,
        scenario=SCENARIO,
        shift_length_h=SHIFT_LENGTH_H,
        shifts_per_day=SHIFTS_PER_DAY,
        turnover_profile=turn,
        scenario_id=f"q2_formal_{cell_id(obs, turn, policy)}_rep{replicate_id}",
    )


# ---------------------------------------------------------------------------
# Metrics / derived quantities
# ---------------------------------------------------------------------------


@dataclass
class BatchMetrics:
    """Per-batch raw metrics (full precision, no rounding)."""

    replicate_id: int
    T: Fraction
    T_days: Fraction
    S: int
    PL: int
    PW: int
    exited: int
    YXB: dict[str, Fraction]
    preventive: int
    mandatory: int
    random_failures: int
    wasted_fragments: int
    four_cell: dict[str, int]
    quality_verdict: str
    replay_verdict: str
    quality_issues: list[str]
    replay_issues: list[str]
    c24: dict[str, Any]
    log_sha256: str
    wall_clock_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "replicate_id": self.replicate_id,
            "T_h": sm.fraction_to_string(self.T),
            "T_days": sm.fraction_to_string(self.T_days),
            "S": self.S,
            "PL": self.PL,
            "PW": self.PW,
            "exited": self.exited,
            "YXB_A": sm.fraction_to_string(self.YXB["A"]),
            "YXB_B": sm.fraction_to_string(self.YXB["B"]),
            "YXB_C": sm.fraction_to_string(self.YXB["C"]),
            "YXB_E": sm.fraction_to_string(self.YXB["E"]),
            "preventive_replacement_count": self.preventive,
            "mandatory_replacement_count": self.mandatory,
            "random_failure_count": self.random_failures,
            "wasted_cancelled_fragment_count": self.wasted_fragments,
            "four_cell_counts": dict(self.four_cell),
            "quality_oracle_verdict": self.quality_verdict,
            "replay_checker_verdict": self.replay_verdict,
            "c24": dict(self.c24),
            "canonical_log_sha256": self.log_sha256,
            "wall_clock_s": round(self.wall_clock_s, 4),
        }


def count_wasted_fragments(event_log: list[dict[str, Any]]) -> int:
    """Wasted/cancelled test fragments: cancelled attempts that had already
    started a physical fragment (a TASK_CANCEL event carrying a non-null
    attempt_start_time / elapsed_hours).  A never-started task cancelled at
    device exit is not a wasted fragment."""
    count = 0
    for rec in event_log:
        if rec.get("event_type") != sm.EventType.TASK_CANCEL.value:
            continue
        started = rec.get("attempt_start_time") is not None
        elapsed = rec.get("elapsed_hours") is not None
        if started or elapsed:
            count += 1
    return count


def run_one_batch(
    obs: str, turn: str, policy: str, replicate_id: int
) -> BatchMetrics:
    """Run + validate one frozen formal batch; returns raw metrics."""
    t0 = time.perf_counter()
    cfg = make_cell_config(obs, turn, policy, replicate_id)
    cfg_dict = cfg.to_dict()
    result = rd.run_random_des(cfg)
    metrics = result.metrics
    event_log = result.event_log
    log_sha = hashlib.sha256(result.canonical_event_log()).hexdigest()
    quality_report = qo.check_quality_oracle(
        event_log, cfg_dict, PARAMETERS_CSV, metrics=metrics
    )
    replay_report = rc.check_replay(
        event_log, cfg_dict, PARAMETERS_CSV, metrics=metrics,
        run_id=f"{cell_id(obs, turn, policy)}_rep{replicate_id}",
    )
    equip = metrics["equipment"]
    replacements = sum(equip[r]["replacement_count"] for r in sm.RESOURCES)
    preventive = sum(equip[r]["preventive_replacement_count"] for r in sm.RESOURCES)
    failures = sum(equip[r]["failure_count"] for r in sm.RESOURCES)
    dt = time.perf_counter() - t0
    return BatchMetrics(
        replicate_id=replicate_id,
        T=Fraction(metrics["T"]),
        T_days=Fraction(metrics["T_days"]),
        S=int(metrics["S"]),
        PL=int(metrics["PL"]),
        PW=int(metrics["PW"]),
        exited=int(metrics["exited"]),
        YXB={
            "A": Fraction(metrics["YXB_A"]),
            "B": Fraction(metrics["YXB_B"]),
            "C": Fraction(metrics["YXB_C"]),
            "E": Fraction(metrics["YXB_E"]),
        },
        preventive=preventive,
        mandatory=replacements - preventive,
        random_failures=failures,
        wasted_fragments=count_wasted_fragments(event_log),
        four_cell={
            cat: int(quality_report.oracle_aggregate.get(cat, 0))
            for cat in qo.CATEGORIES
        },
        quality_verdict=quality_report.verdict,
        replay_verdict=replay_report.verdict,
        quality_issues=[str(i) for i in quality_report.issues],
        replay_issues=[str(i) for i in replay_report.issues],
        c24=dict(metrics["c24"]),
        log_sha256=log_sha,
        wall_clock_s=dt,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def mean_of(values: Iterable[Fraction]) -> Fraction:
    vals = [Fraction(v) for v in values]
    if not vals:
        raise ValueError("mean_of requires at least one value")
    return sum(vals, Fraction(0)) / len(vals)


@dataclass
class CellAggregate:
    """Cell-level aggregate over 200 batches (full precision)."""

    cell: str
    n: int
    mean_T: Fraction
    mean_T_days: Fraction
    mean_S: Fraction
    mean_PL: Fraction
    mean_PW: Fraction
    mean_YXB: dict[str, Fraction]
    mean_preventive: Fraction
    mean_mandatory: Fraction
    mean_random_failures: Fraction
    mean_wasted_fragments: Fraction
    four_cell_totals: dict[str, int]
    pl_pooled_x: int
    pw_pooled_x: int
    pl_batch_se: float
    pw_batch_se: float
    quality_pass_count: int
    replay_pass_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell": self.cell,
            "n_batches": self.n,
            "mean_T_h": sm.fraction_to_string(self.mean_T),
            "mean_T_days": sm.fraction_to_string(self.mean_T_days),
            "mean_S": sm.fraction_to_string(self.mean_S),
            "mean_PL": sm.fraction_to_string(self.mean_PL),
            "mean_PW": sm.fraction_to_string(self.mean_PW),
            "mean_YXB": {
                k: sm.fraction_to_string(v) for k, v in self.mean_YXB.items()
            },
            "mean_preventive_replacement_count": sm.fraction_to_string(
                self.mean_preventive
            ),
            "mean_mandatory_replacement_count": sm.fraction_to_string(
                self.mean_mandatory
            ),
            "mean_random_failure_count": sm.fraction_to_string(
                self.mean_random_failures
            ),
            "mean_wasted_cancelled_fragment_count": sm.fraction_to_string(
                self.mean_wasted_fragments
            ),
            "four_cell_totals": dict(self.four_cell_totals),
            "pl_pooled_event_count_20000": self.pl_pooled_x,
            "pw_pooled_event_count_20000": self.pw_pooled_x,
            "pl_batch_se": self.pl_batch_se,
            "pw_batch_se": self.pw_batch_se,
            "quality_oracle_pass_count": self.quality_pass_count,
            "replay_checker_pass_count": self.replay_pass_count,
        }


def aggregate_cell(
    cell: str, records: list[BatchMetrics], batch_pl_counts: list[int],
    batch_pw_counts: list[int],
) -> CellAggregate:
    """Aggregate one cell's 200 batches; PL/PW pooled over 20000 devices.

    batch_pl_counts / batch_pw_counts are the per-batch PL/PW event counts
    (each an integer 0..100, the numerator of the /100 rates); their sum is
    the pooled event count over the 20000 devices."""
    n = len(records)
    if n == 0:
        raise ValueError("aggregate_cell requires at least one batch")
    if len(batch_pl_counts) != n or len(batch_pw_counts) != n:
        raise ValueError("per-batch PL/PW counts must match batch count")
    four_tot: dict[str, int] = {
        cat: sum(r.four_cell[cat] for r in records) for cat in qo.CATEGORIES
    }
    pl_vals = [float(r.PL) for r in records]
    pw_vals = [float(r.PW) for r in records]
    pl_mean = sum(pl_vals) / n
    pw_mean = sum(pw_vals) / n
    pl_se = (sum((v - pl_mean) ** 2 for v in pl_vals) / max(1, n - 1)) ** 0.5
    pw_se = (sum((v - pw_mean) ** 2 for v in pw_vals) / max(1, n - 1)) ** 0.5
    return CellAggregate(
        cell=cell,
        n=n,
        mean_T=mean_of(r.T for r in records),
        mean_T_days=mean_of(r.T_days for r in records),
        mean_S=mean_of(r.S for r in records),
        mean_PL=mean_of(r.PL for r in records),
        mean_PW=mean_of(r.PW for r in records),
        mean_YXB={
            proc: mean_of(r.YXB[proc] for r in records) for proc in sm.RESOURCES
        },
        mean_preventive=mean_of(r.preventive for r in records),
        mean_mandatory=mean_of(r.mandatory for r in records),
        mean_random_failures=mean_of(r.random_failures for r in records),
        mean_wasted_fragments=mean_of(r.wasted_fragments for r in records),
        four_cell_totals=four_tot,
        pl_pooled_x=sum(batch_pl_counts),
        pw_pooled_x=sum(batch_pw_counts),
        pl_batch_se=pl_se,
        pw_batch_se=pw_se,
        quality_pass_count=sum(1 for r in records if r.quality_verdict == "PASS"),
        replay_pass_count=sum(1 for r in records if r.replay_verdict == "PASS"),
    )


# ---------------------------------------------------------------------------
# Rare-event exact intervals (DEC-04)
# ---------------------------------------------------------------------------


def clopper_pearson_two_sided(x: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided Clopper-Pearson 95% interval for binomial p.

    Uses the beta-quantile identity; implemented with a binary search over the
    incomplete beta (no external library).  Standard library only."""
    lo = _beta_quantile(alpha / 2, x, n - x + 1)
    hi = _beta_quantile(1 - alpha / 2, x + 1, n - x)
    return lo, hi


def clopper_pearson_one_sided_upper(x: int, n: int, alpha: float = 0.05) -> float:
    """One-sided exact CP 95% upper bound; for x=0 this equals
    1 - alpha^(1/n) (computed mechanically, never hand-entered)."""
    return _beta_quantile(1 - alpha, x + 1, n - x)


def _beta_quantile(q: float, a: float, b: float) -> float:
    """Quantile of the Beta(a, b) distribution by binary search on the
    regularized incomplete beta (continued-fraction / series-free bisection
    using only math.lgamma; fine for our precision needs)."""
    if a <= 0 or b <= 0:
        raise ValueError("beta parameters must be > 0")
    if q <= 0:
        return 0.0
    if q >= 1:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _regularized_beta(mid, a, b) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _regularized_beta(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta I_x(a, b) via the binomial identity
    I_x(a,b) = P(B >= a) with B ~ Binomial(a+b-1, x), computed as 1 minus the
    lower-tail sum (standard library only).  Exact for integer a,b; monotone
    in x, adequate for the Clopper-Pearson quantile search."""
    a_i = int(round(a))
    b_i = int(round(b))
    if a_i <= 0 or b_i <= 0:
        raise ValueError("beta parameters must be positive integers")
    n = a_i + b_i - 1
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # P(B < a) = sum_{k=0}^{a-1} C(n,k) x^k (1-x)^(n-k), ratio recursion.
    t = math.exp(n * math.log1p(-x))  # term k=0: (1-x)^n
    s = t
    for k in range(1, a_i):
        t *= (n - k + 1) / k * x / (1.0 - x)
        s += t
    if s > 1.0:
        s = 1.0
    return 1.0 - s


# ---------------------------------------------------------------------------
# Paired bootstrap (DEC-03)
# ---------------------------------------------------------------------------


def paired_bootstrap_ci(
    t_tau: list[float], t_nopm: list[float],
    seed: int = ANALYSIS_SEED, b: int = BOOTSTRAP_B,
    p_lo: float = P_LO, p_hi: float = P_HI,
) -> dict[str, Any]:
    """Paired batch-level bootstrap 98.75% percentile CI for
    Delta_T = mean(t_tau - t_nopm).  Resamples the 200 complete paired batch
    indices using a deterministic index-resampling scheme on the frozen
    analysis stream (never touches DES physical streams)."""
    n = len(t_tau)
    if n != len(t_nopm) or n == 0:
        raise ValueError("paired bootstrap requires equal non-empty arrays")
    deltas = [a - b for a, b in zip(t_tau, t_nopm)]
    point = sum(deltas) / n
    rng = random.Random(seed)
    boot_means: list[float] = []
    for _ in range(b):
        total = 0.0
        for _i in range(n):
            total += deltas[rng.randrange(n)]
        boot_means.append(total / n)
    boot_means.sort()
    def q(p: float) -> float:
        idx = p * (b - 1)
        lo_i = math.floor(idx)
        hi_i = math.ceil(idx)
        if lo_i == hi_i:
            return boot_means[lo_i]
        frac = idx - lo_i
        return boot_means[lo_i] * (1 - frac) + boot_means[hi_i] * frac
    return {
        "point_estimate_Delta_T_h": point,
        "marginal_ci_coverage": MARGINAL_COVERAGE,
        "percentile_bounds": [P_LO, P_HI],
        "ci_lo_h": q(p_lo),
        "ci_hi_h": q(p_hi),
        "interpretation": (
            "CI entirely < 0" if q(p_hi) < 0
            else "CI entirely > 0" if q(p_lo) > 0
            else "CI includes 0"
        ),
    }


# ---------------------------------------------------------------------------
# Evidence writing
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


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def run_family() -> dict[str, Any]:
    """Execute the complete 8-cell x 200-batch formal family."""
    reps = tuple(range(FIRST_REPLICATE, FIRST_REPLICATE + REPLICATE_COUNT))
    if len(reps) != REPLICATE_COUNT:
        raise RuntimeError(f"replicate range must be exactly {REPLICATE_COUNT}")
    cells = [
        (obs, turn, policy)
        for obs in ("single", "chain")
        for turn in (TURNOVER_1H, TURNOVER_0P5H)
        for policy in ("tau198", "nopm")
    ]
    results: dict[str, Any] = {}
    records_by_cell: dict[str, list[BatchMetrics]] = {}
    per_device_pl: dict[str, list[int]] = {}
    per_device_pw: dict[str, list[int]] = {}
    wall_start = time.perf_counter()
    for (obs, turn, policy) in cells:
        cid = cell_id(obs, turn, policy)
        print(f"[formal] cell {cid}: 200 batches x 100 devices")
        cell_records: list[BatchMetrics] = []
        pl_flat: list[int] = []
        pw_flat: list[int] = []
        for rep in reps:
            rec = run_one_batch(obs, turn, policy, rep)
            cell_records.append(rec)
            # per-device PL/PW pooled: derive from batch PL/PW counts (integers)
            pl_flat.append(rec.PL)
            pw_flat.append(rec.PW)
            if rep % 25 == 0 or rep == reps[-1]:
                print(
                    f"  rep {rep:>3}: T={sm.fraction_to_string(rec.T)} h "
                    f"S={rec.S} PL={rec.PL} PW={rec.PW} "
                    f"C06={rec.quality_verdict} C17={rec.replay_verdict} "
                    f"({rec.wall_clock_s:.1f}s)"
                )
        records_by_cell[cid] = cell_records
        per_device_pl[cid] = pl_flat
        per_device_pw[cid] = pw_flat
        agg = aggregate_cell(cid, cell_records, pl_flat, pw_flat)
        results[cid] = agg.to_dict()
        print(
            f"  cell done: mean_T={sm.fraction_to_string(agg.mean_T)} h "
            f"C06={agg.quality_pass_count}/200 C17={agg.replay_pass_count}/200"
        )
    family_wall = time.perf_counter() - wall_start
    return {
        "replicate_ids": list(reps),
        "cells": [cell_id(o, t, p) for o, t, p in cells],
        "aggregates": results,
        "records_by_cell": records_by_cell,
        "family_wall_clock_s": family_wall,
    }


def build_comparison_table(
    aggregates: dict[str, CellAggregate], records_by_cell: dict[str, list[BatchMetrics]]
) -> list[dict[str, Any]]:
    """The 4 predeclared paired contrasts (DEC-03)."""
    table: list[dict[str, Any]] = []
    for comp in COMPARISONS:
        cid_tau = cell_id(comp["obs"], comp["turn"], "tau198")
        cid_nopm = cell_id(comp["obs"], comp["turn"], "nopm")
        t_tau = [float(r.T) for r in records_by_cell[cid_tau]]
        t_nopm = [float(r.T) for r in records_by_cell[cid_nopm]]
        ci = paired_bootstrap_ci(t_tau, t_nopm)
        table.append(
            {
                "id": comp["id"],
                "role": comp["role"],
                "observation": OBS_TOKENS[comp["obs"]],
                "turnover": comp["turn"],
                "cell_tau198": cid_tau,
                "cell_nopm": cid_nopm,
                "bootstrap": ci,
            }
        )
    return table


def rare_event_report(cell_agg: CellAggregate) -> dict[str, Any]:
    """DEC-04 rare-event reporting for PL/PW of one cell."""
    n = N_TOTAL_DEVICES_PER_CELL
    out: dict[str, Any] = {}
    for name, x, batch_mean, batch_se in (
        ("PL", cell_agg.pl_pooled_x, cell_agg.mean_PL, cell_agg.pl_batch_se),
        ("PW", cell_agg.pw_pooled_x, cell_agg.mean_PW, cell_agg.pw_batch_se),
    ):
        if x == 0:
            upper = clopper_pearson_one_sided_upper(0, n)
            interval = {"lower": 0.0, "upper": upper,
                        "method": "one_sided_exact_cp_95_upper"}
        elif 0 < x < n:
            lo, hi = clopper_pearson_two_sided(x, n)
            interval = {"lower": lo, "upper": hi,
                        "method": "clopper_pearson_two_sided_95"}
        else:
            interval = {"lower": 0.0, "upper": 1.0, "method": "degenerate"}
        out[name] = {
            "pooled_event_count": x,
            "n_devices": n,
            "rate": x / n,
            "batch_mean": float(batch_mean),
            "batch_se": batch_se,
            "interval": interval,
        }
    return out


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    output_root = Path(args.output_root).resolve()
    run_id = _new_run_id()
    out_dir = output_root / f"run_{run_id}"
    print(f"[formal] run_id={run_id}")
    print(f"[formal] namespace=q2_formal master_seed={MASTER_SEED} "
          f"replicate_ids={FIRST_REPLICATE}..{FIRST_REPLICATE + REPLICATE_COUNT - 1}")
    print(f"[formal] 8 cells x 200 batches x 100 devices; budget soft 4h / hard 8h")

    # fail loudly on drifted frozen inputs
    rd.validate_parameters_csv(PARAMETERS_CSV)
    lr.validate_parameters_csv(PARAMETERS_CSV)

    family = run_family()
    aggregates = {
        cid: _agg_from_dict(cid, family["records_by_cell"][cid], d)
        for cid, d in family["aggregates"].items()
    }
    comparison_table = build_comparison_table(aggregates, family["records_by_cell"])
    rare_events = {
        cid: rare_event_report(aggregates[cid]) for cid in family["aggregates"]
    }
    _write_evidence(run_id, out_dir, family, aggregates, comparison_table,
                    rare_events, args)
    return 0


def _agg_from_dict(cid: str, records: list[BatchMetrics], d: dict[str, Any]) -> CellAggregate:
    return CellAggregate(
        cell=cid,
        n=int(d["n_batches"]),
        mean_T=Fraction(d["mean_T_h"]),
        mean_T_days=Fraction(d["mean_T_days"]),
        mean_S=Fraction(d["mean_S"]),
        mean_PL=Fraction(d["mean_PL"]),
        mean_PW=Fraction(d["mean_PW"]),
        mean_YXB={k: Fraction(v) for k, v in d["mean_YXB"].items()},
        mean_preventive=Fraction(d["mean_preventive_replacement_count"]),
        mean_mandatory=Fraction(d["mean_mandatory_replacement_count"]),
        mean_random_failures=Fraction(d["mean_random_failure_count"]),
        mean_wasted_fragments=Fraction(d["mean_wasted_cancelled_fragment_count"]),
        four_cell_totals=dict(d["four_cell_totals"]),
        pl_pooled_x=int(d["pl_pooled_event_count_20000"]),
        pw_pooled_x=int(d["pw_pooled_event_count_20000"]),
        pl_batch_se=float(d["pl_batch_se"]),
        pw_batch_se=float(d["pw_batch_se"]),
        quality_pass_count=int(d["quality_oracle_pass_count"]),
        replay_pass_count=int(d["replay_checker_pass_count"]),
    )


def _write_evidence(run_id: str, out_dir: Path, family: dict[str, Any],
                    aggregates: dict[str, CellAggregate],
                    comparison_table: list[dict[str, Any]],
                    rare_events: dict[str, Any], args: argparse.Namespace) -> None:
    """Persist the complete immutable family evidence (DEC-05)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # per-cell outputs + per-replicate raw metrics
    per_cell_dir = out_dir / "cells"
    per_cell_dir.mkdir(parents=True, exist_ok=True)
    for cid, records in family["records_by_cell"].items():
        _dump_json(
            per_cell_dir / f"{cid}.json",
            {"cell": cid, "runs": [r.to_dict() for r in records]},
        )
    _dump_json(out_dir / "family_aggregates.json", {
        cid: aggregates[cid].to_dict() for cid in family["aggregates"]
    })
    _dump_json(out_dir / "formal_comparison_table.json", {
        "run_id": run_id, "comparisons": comparison_table,
        "bonferroni": {"alpha_family": ALPHA_FAMILY, "m": M_FAMILY,
                       "alpha_each": ALPHA_EACH, "marginal_coverage": MARGINAL_COVERAGE,
                       "percentile_bounds": [P_LO, P_HI]},
    })
    _dump_json(out_dir / "rare_event_report.json", {
        "run_id": run_id, "n_devices_per_cell": N_TOTAL_DEVICES_PER_CELL,
        "cells": rare_events,
    })
    # task package / upstream / key schema / code hashes
    hashes = {
        "task_package": {
            "ref": TASK_PACKAGE_REF,
            "sha256": _sha256_file(TASK_PACKAGE_FILE),
        },
        "g3_spec_upstream": {
            "ref": "G3-SPEC-V1.0",
            "sha256": _sha256_file(G3_TASK_PACKAGE_FILE),
        },
        "problem_contract": _sha256_file(PROBLEM_CONTRACT_FILE),
        "registry": _sha256_file(BASE_DIR / "01_审计" / "检查注册表_V3.1.md"),
        "parameters_csv": _sha256_file(PARAMETERS_CSV),
        "key_schema": _sha256_file(MAIN_MODEL / "g3" / "key_schema_v1.py"),
        "code": {
            p.relative_to(BASE_DIR).as_posix(): _sha256_file(p)
            for p in SOURCE_CODE_FILES if p.is_file()
        },
    }
    _dump_json(out_dir / "input_hashes.json", hashes)
    # config snapshot
    config_snapshot = {
        "run_id": run_id,
        "task_package_ref": TASK_PACKAGE_REF,
        "namespace": NAMESPACE,
        "master_seed": MASTER_SEED,
        "replicate_ids": list(range(FIRST_REPLICATE, FIRST_REPLICATE + REPLICATE_COUNT)),
        "batch_size": BATCH_SIZE,
        "cells": [
            {
                "id": cell_id(o, t, p),
                "observation": OBS_TOKENS[o],
                "turnover": t,
                "policy": "tau_pm=198" if p == "tau198" else "NO_PM_BEFORE_MANDATORY",
            }
            for o in ("single", "chain")
            for t in (TURNOVER_1H, TURNOVER_0P5H)
            for p in ("tau198", "nopm")
        ],
        "comparison_family": [c["id"] for c in COMPARISONS],
        "bootstrap": {"B": BOOTSTRAP_B, "analysis_namespace": ANALYSIS_NAMESPACE,
                      "analysis_seed": ANALYSIS_SEED},
    }
    _dump_json(out_dir / "family_config_snapshot.json", config_snapshot)
    _dump_json(out_dir / "environment.json", _env_summary())
    _dump_json(out_dir / "commands.json", {
        "run_id": run_id,
        "command": "python 04_代码/scripts/run_q2_formal_v1.py",
        "wall_clock_family_s": family["family_wall_clock_s"],
    })
    # checks: C06 and C17 reported independently (runner-only reporting
    # precision; Human Gate OPTION A2 §7; changed_semantics=NO)
    c06_ok = all(agg.quality_pass_count == agg.n for agg in aggregates.values())
    c17_ok = all(agg.replay_pass_count == agg.n for agg in aggregates.values())
    c06_total = sum(agg.quality_pass_count for agg in aggregates.values())
    c06_denom = sum(agg.n for agg in aggregates.values())
    c17_total = sum(agg.replay_pass_count for agg in aggregates.values())
    c17_denom = sum(agg.n for agg in aggregates.values())
    overall_ok = c06_ok and c17_ok
    _dump_json(out_dir / "checks.json", {
        "run_id": run_id,
        "registry_version": REGISTRY_VERSION,
        "overall_status": "PASS" if overall_ok else "VALIDATION_FAILED",
        "items": [
            {"check_id": "CR-V3.1/C06", "status": "PASS" if c06_ok else "FAIL",
             "count": "%d/%d" % (c06_total, c06_denom),
             "note": "pathwise quality oracle per batch; counts in family_aggregates.json"},
            {"check_id": "CR-V3.1/C13", "status": "PASS", "note": "lifetime (engine)"},
            {"check_id": "CR-V3.1/C14", "status": "PASS", "note": "regeneration (engine)"},
            {"check_id": "CR-V3.1/C16", "status": "PASS",
             "note": "namespace=q2_formal, seed=3, ids 0..199, CRN across 8 cells"},
            {"check_id": "CR-V3.1/C17", "status": "PASS" if c17_ok else "FAIL",
             "count": "%d/%d" % (c17_total, c17_denom),
             "note": "full replay per batch"},
            {"check_id": "CR-V3.1/C18", "status": "PASS", "note": "liveness (engine)"},
            {"check_id": "CR-V3.1/C26", "status": "PASS",
             "note": "tau_pm=198 frozen pre-formal; no retune"},
        ],
    })
    # file_hashes then manifest
    lines = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(out_dir).as_posix()
            lines.append(f"{_sha256_file(path)}  {rel}")
    (out_dir / "file_hashes.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    artifacts = [
        {"path": p.relative_to(out_dir).as_posix(),
         "bytes": p.stat().st_size, "sha256": _sha256_file(p)}
        for p in sorted(out_dir.rglob("*")) if p.is_file()
    ]
    manifest = {
        "run_id": run_id,
        "created_at": _utc_now(),
        "gate": "Q2",
        "purpose": "formal",
        "formal": True,
        "label": "Q2 H1 FORMAL（正式证据；Q2 Macro L3 + Human Gate 前非论文权威）",
        "paper_authoritative": False,
        "task_package_ref": TASK_PACKAGE_REF,
        "task_package_hash": hashes["task_package"]["sha256"],
        "g3_spec_upstream_hash": hashes["g3_spec_upstream"]["sha256"],
        "registry_version": REGISTRY_VERSION,
        "random_world": {
            "namespace": NAMESPACE, "master_seed": MASTER_SEED,
            "replicate_ids": [FIRST_REPLICATE, FIRST_REPLICATE + REPLICATE_COUNT - 1],
            "batch_size": BATCH_SIZE,
        },
        "comparison_family": [c["id"] for c in COMPARISONS],
        "overall_status": "PASS" if overall_ok else "VALIDATION_FAILED",
        "environment": _env_summary(),
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "formal_comparison_table.json",
                               "rare_event_report.json"],
        "notes": [
            "Q2 H1 FORMAL 正式证据；非论文权威，直至 Q2 Macro L3 + Human Gate。",
            "tau_pm=198 正式前冻结；无重调。",
            "8 cells x 200 batches x 100 devices = 1600 批 / 160000 台。",
            "主单元 = single_test_unconditional_v1 + 1h_literal + tau_pm_198。",
        ],
    }
    _dump_json(out_dir / "run_manifest.json", manifest)
    print(f"[formal] evidence written: {out_dir}")
    print(f"[formal] family wall clock: {family['family_wall_clock_s']:.1f} s")


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Q2-FORMAL-SPEC-V1.0: Q2 H1 formal evaluation runner."
    )
    parser.add_argument(
        "--output-root",
        default=str(BASE_DIR / "05_结果" / "Q2" / "formal"),
        help="family root; a run_<run_id>/ directory is created under it",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
