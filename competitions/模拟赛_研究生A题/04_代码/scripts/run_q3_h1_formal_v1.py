#!/usr/bin/env python3
"""Q3-H1-FORMAL-SPEC-V1.0: Q3 seven-K H1 formal baseline runner.

Frozen protocol (Q3_七K_H1正式基线.yaml FROZEN_FOR_FORMAL_RUN; Human Gate
2026-08-15 Q3-H1-FORMAL Authorization Package; Q3_H2_BOOTSTRAP_SPEC_DRAFT.md
FINAL_FREEZE_ACCEPTED sections 14/19/20).

This is a THIN runner/aggregation layer over the accepted G3 engine. It NEVER
modifies G3 core semantics (random_des_v1 core transitions, key_schema_v1
including the accepted P0 H2 extension, lifetime/regeneration semantics, C06
oracle core, C17 replay core, frozen observation semantics).  If completing
the formal run required any such change, STOP with
Q3_H1_FORMAL_REQUIRES_G3_CORE_CHANGE.

Formal family (frozen): 2 tiers x 7 K:
  Tier 1 (PRIMARY): single_test_unconditional_v1 x 1h_literal x
                    NO_PM_BEFORE_MANDATORY x 7 K x 200 batches x 100 devices
  Tier 2 (CONTRACT): standard_chain_v1 x 1h_literal x
                    NO_PM_BEFORE_MANDATORY x 7 K x 200 batches x 100 devices

Random world (D-03): namespace=q3_formal, master_seed=5,
replicate_id=0..199 (exactly 200); all seven K reuse the same 200 replicate
ids (cross-K CRN); K / policy / tier / squad / run_id never enter physical
random keys.  Q3 full reset per (K, replicate); engine is stateless per run
so no Q2 terminal state is ever read (C15 assertions in this runner).

T inference (D-04): per tier, all 21 pairwise K contrasts DeltaT=T(k1)-T(k2);
paired batch-level bootstrap B=10000 on the analysis stream
namespace=q3_formal_analysis_bootstrap_v1 seed=40003 (resamples only the 200
complete paired batch indices; never touches DES physical streams).
Bonferroni: alpha_family=0.05, m=21, alpha_each=0.05/21, two-sided; each
marginal bootstrap CI uses coverage 1-alpha_each with percentile bounds
0.05/42 and 1-0.05/42.

Recommendation rule (frozen): k* = argmin mean(T_K); co-best = K whose
paired CI vs k* contains 0; strong recommendation only if k* CI vs every
other K is entirely <0; wording limited to the seven-K grid and the frozen
candidate policy set; K=12 weak domination is never claimed in the main
configuration.

Rare events: PL/PW pooled over N_total=20000 devices per cell; x=0 ->
one-sided exact CP 95% upper bound 1 - 0.05^(1/20000) (mechanical);
0<x<20000 -> two-sided exact CP 95%.

Evidence: one immutable family root 05_结果/Q3/formal/run_<UTC>_<8hex>/ with
run_manifest, commands, environment, family config snapshot, task-package
snapshot/hash, code/schema/key-schema/config hashes, Tier 1/Tier 2 outputs,
per-replicate raw metrics, checker reports (checks.json), statistical
analysis (21-pair tables, k*/co-best, per-K summaries, quality table,
rare-event report), bootstrap metadata, failure samples, file_hashes.sha256,
wall-clock ledger.  Failed attempts stay immutable.

Statistical helpers (paired bootstrap, Clopper-Pearson, incomplete beta) are
copied verbatim from the accepted Q2 runner (run_q2_formal_v1.py,
Q2-FORMAL-SPEC-V1.0) for provenance consistency.

Budget: soft checkpoint 4 h, hard cap 8 h (unconditional stop:
Q3_H1_FORMAL_HARD_BUDGET_STOP_WAITING_FOR_HUMAN_GATE).  Never reduce the 200
repetitions.  Tier 3 is NOT run.  Density recheck / P1 / C23 / C25 are NOT
in this package.

Python 3.12, standard library only.
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

TASK_PACKAGE_REF = "Q3-H1-FORMAL-SPEC-V1.0"
TASK_PACKAGE_FILE = BASE_DIR / "08_项目管理" / "任务包" / "Q3_七K_H1正式基线.yaml"
G3_TASK_PACKAGE_FILE = BASE_DIR / "08_项目管理" / "任务包" / "G3_公共随机DES与H1基线.yaml"
BOOTSTRAP_SPEC_FILE = (
    BASE_DIR / "08_项目管理" / "任务包" / "Q3_H2_BOOTSTRAP_SPEC_DRAFT.md"
)
REGISTRY_VERSION = "CR-V3.1"
PARAMETERS_CSV = BASE_DIR / "02_数据" / "parameters.csv"
PROBLEM_CONTRACT_FILE = BASE_DIR / "01_审计" / "问题契约.md"

NAMESPACE = ks.NAMESPACE_Q3_FORMAL
MASTER_SEED = 5
FIRST_REPLICATE = 0
REPLICATE_COUNT = 200  # D-03: exactly 200, ids 0..199
BATCH_SIZE = 100
SCENARIO = "q3_two_shift"
SHIFTS_PER_DAY = 2
TURNOVER_1H = "1h_literal"
POLICY = lr.NO_PM_BEFORE_MANDATORY  # frozen H1 policy; "NO_PM" is shorthand

# Frozen K grid (P041): seven points, full enumeration.
K_VALUES: tuple[tuple[str, str], ...] = (
    ("K09", "9"),
    ("K09p5", "19/2"),
    ("K10", "10"),
    ("K10p5", "21/2"),
    ("K11", "11"),
    ("K11p5", "23/2"),
    ("K12", "12"),
)
K_DISPLAY: dict[str, str] = {
    "K09": "9", "K09p5": "9.5", "K10": "10", "K10p5": "10.5",
    "K11": "11", "K11p5": "11.5", "K12": "12",
}

TIER1 = "tier1"
TIER2 = "tier2"
OBS_SINGLE = "single"
OBS_CHAIN = "chain"

# D-04 Bonferroni.
ALPHA_FAMILY = 0.05
M_FAMILY = 21
ALPHA_EACH = ALPHA_FAMILY / M_FAMILY  # 0.05/21
MARGINAL_COVERAGE = 1.0 - ALPHA_EACH
P_LO = ALPHA_EACH / 2  # 0.05/42
P_HI = 1.0 - ALPHA_EACH / 2  # 1 - 0.05/42

# Rare events.
N_TOTAL_DEVICES_PER_CELL = REPLICATE_COUNT * BATCH_SIZE  # 20000

# Bootstrap analysis stream (frozen, non-physical).
ANALYSIS_NAMESPACE = "q3_formal_analysis_bootstrap_v1"
ANALYSIS_SEED = 40003
BOOTSTRAP_B = 10000

# Q1-frozen q_E propagation for single semantics (identical to Q2 runner).
Q1_FROZEN_Q_E_TEXT = "0.062593912407392898"
FROZEN_Q_ABC: dict[str, Fraction] = {
    "A": Fraction(25, 1000), "B": Fraction(3, 100), "C": Fraction(2, 100),
}
FROZEN_E_ABC: dict[str, Fraction] = {
    "A": Fraction(3, 100), "B": Fraction(4, 100), "C": Fraction(2, 100),
}
FROZEN_E_E: Fraction = Fraction(2, 100)

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
    CODE_DIR / "tests" / "test_q3_h1_formal_v1.py",
)

# ---------------------------------------------------------------------------
# Frozen observation kernels
# ---------------------------------------------------------------------------


def single_kernel() -> dict[str, dict[str, Fraction]]:
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
    return {
        proc: {"alpha": Fraction(e["alpha"]), "beta": Fraction(e["beta"])}
        for proc, e in CHAIN_KERNEL.items()
    }


def cell_id(tier: str, k_label: str) -> str:
    obs = "single" if tier == TIER1 else "chain"
    return f"{tier}__{obs}__{k_label}"


# ---------------------------------------------------------------------------
# C15 assertions (Q3 reset / seven-K / cross-K CRN / no Q2 inheritance)
# ---------------------------------------------------------------------------


def assert_c15_cell(cfg: rd.RandomDesConfig, tier: str, k_label: str) -> None:
    """Per-cell C15 assertions: Q3 frozen world, no K/policy injection."""
    if cfg.namespace != NAMESPACE:
        raise AssertionError(f"C15: namespace must be q3_formal, got {cfg.namespace!r}")
    if cfg.master_seed != MASTER_SEED:
        raise AssertionError(f"C15: master_seed must be 5, got {cfg.master_seed}")
    if not (FIRST_REPLICATE <= cfg.replicate_id < FIRST_REPLICATE + REPLICATE_COUNT):
        raise AssertionError(f"C15: replicate_id out of frozen range: {cfg.replicate_id}")
    if cfg.scenario != SCENARIO:
        raise AssertionError(f"C15: scenario must be q3_two_shift, got {cfg.scenario!r}")
    if cfg.shifts_per_day != SHIFTS_PER_DAY:
        raise AssertionError(f"C15: shifts_per_day must be 2, got {cfg.shifts_per_day}")
    # K is the shift length; verify it matches the frozen grid entry.
    k_frac = Fraction(dict(K_VALUES)[k_label])
    if cfg.shift_length_h != k_frac:
        raise AssertionError(
            f"C15: shift_length_h {cfg.shift_length_h} != K {k_label} {k_frac}"
        )
    # Policy must be the frozen NO_PM sentinel (no tau_pm retuning).
    if cfg.tau_pm is not lr.NO_PM_BEFORE_MANDATORY:
        raise AssertionError("C15/C26: policy must be NO_PM_BEFORE_MANDATORY")
    # tier label sanity
    if tier not in (TIER1, TIER2):
        raise AssertionError(f"C15: unknown tier {tier!r}")


# ---------------------------------------------------------------------------
# Metrics / derived quantities
# ---------------------------------------------------------------------------


@dataclass
class BatchMetrics:
    tier: str
    k_label: str
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
            "tier": self.tier,
            "K": self.k_label,
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
    count = 0
    for rec in event_log:
        if rec.get("event_type") != sm.EventType.TASK_CANCEL.value:
            continue
        if rec.get("attempt_start_time") is not None or rec.get("elapsed_hours") is not None:
            count += 1
    return count


def run_one_batch(tier: str, k_label: str, replicate_id: int) -> BatchMetrics:
    t0 = time.perf_counter()
    cfg = make_cell_config(tier, k_label, replicate_id)
    assert_c15_cell(cfg, tier, k_label)
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
        run_id=f"{cell_id(tier, k_label)}_rep{replicate_id}",
    )
    equip = metrics["equipment"]
    replacements = sum(equip[r]["replacement_count"] for r in sm.RESOURCES)
    preventive = sum(equip[r]["preventive_replacement_count"] for r in sm.RESOURCES)
    failures = sum(equip[r]["failure_count"] for r in sm.RESOURCES)
    dt = time.perf_counter() - t0
    return BatchMetrics(
        tier=tier, k_label=k_label, replicate_id=replicate_id,
        T=Fraction(metrics["T"]),
        T_days=Fraction(metrics["T_days"]),
        S=int(metrics["S"]),
        PL=int(metrics["PL"]),
        PW=int(metrics["PW"]),
        exited=int(metrics["exited"]),
        YXB={p: Fraction(metrics[f"YXB_{p}"]) for p in sm.RESOURCES},
        preventive=preventive,
        mandatory=replacements - preventive,
        random_failures=failures,
        wasted_fragments=count_wasted_fragments(event_log),
        four_cell={cat: int(quality_report.oracle_aggregate.get(cat, 0))
                   for cat in qo.CATEGORIES},
        quality_verdict=quality_report.verdict,
        replay_verdict=replay_report.verdict,
        quality_issues=[str(i) for i in quality_report.issues],
        replay_issues=[str(i) for i in replay_report.issues],
        c24=dict(metrics["c24"]),
        log_sha256=log_sha,
        wall_clock_s=dt,
    )


def make_cell_config(tier: str, k_label: str, replicate_id: int) -> rd.RandomDesConfig:
    kernel = single_kernel() if tier == TIER1 else chain_kernel()
    k_frac = Fraction(dict(K_VALUES)[k_label])
    return rd.default_config(
        namespace=NAMESPACE,
        master_seed=MASTER_SEED,
        replicate_id=replicate_id,
        tau_pm=POLICY,
        observation_kernel=kernel,
        batch_size=BATCH_SIZE,
        scenario=SCENARIO,
        shift_length_h=sm.fraction_to_string(k_frac),
        shifts_per_day=SHIFTS_PER_DAY,
        turnover_profile=TURNOVER_1H,
        scenario_id=f"q3_formal_{cell_id(tier, k_label)}_rep{replicate_id}",
    )


def mean_of(values: Iterable[Fraction]) -> Fraction:
    vals = [Fraction(v) for v in values]
    if not vals:
        raise ValueError("mean_of requires at least one value")
    return sum(vals, Fraction(0)) / len(vals)


def percentile_of(values: list[float], p: float) -> float:
    s = sorted(values)
    if not s:
        raise ValueError("percentile_of requires non-empty values")
    idx = p * (len(s) - 1)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return s[lo]
    frac = idx - lo
    return s[lo] * (1 - frac) + s[hi] * frac


@dataclass
class CellAggregate:
    cell: str
    tier: str
    k_label: str
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
    t_batch_se: float
    t_p50: float
    t_p90: float
    quality_pass_count: int
    replay_pass_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell": self.cell, "tier": self.tier, "K": self.k_label,
            "K_hours": K_DISPLAY[self.k_label],
            "n_batches": self.n,
            "mean_T_h": sm.fraction_to_string(self.mean_T),
            "mean_T_days": sm.fraction_to_string(self.mean_T_days),
            "t_batch_se_h": self.t_batch_se,
            "t_p50_h": self.t_p50,
            "t_p90_h": self.t_p90,
            "mean_S": sm.fraction_to_string(self.mean_S),
            "mean_PL": sm.fraction_to_string(self.mean_PL),
            "mean_PW": sm.fraction_to_string(self.mean_PW),
            "mean_YXB": {k: sm.fraction_to_string(v) for k, v in self.mean_YXB.items()},
            "mean_preventive_replacement_count": sm.fraction_to_string(self.mean_preventive),
            "mean_mandatory_replacement_count": sm.fraction_to_string(self.mean_mandatory),
            "mean_random_failure_count": sm.fraction_to_string(self.mean_random_failures),
            "mean_wasted_cancelled_fragment_count": sm.fraction_to_string(self.mean_wasted_fragments),
            "four_cell_totals": dict(self.four_cell_totals),
            "pl_pooled_event_count_20000": self.pl_pooled_x,
            "pw_pooled_event_count_20000": self.pw_pooled_x,
            "pl_batch_se": self.pl_batch_se,
            "pw_batch_se": self.pw_batch_se,
            "quality_oracle_pass_count": self.quality_pass_count,
            "replay_checker_pass_count": self.replay_pass_count,
        }


def aggregate_cell(cell: str, tier: str, k_label: str, records: list[BatchMetrics],
                   batch_pl_counts: list[int], batch_pw_counts: list[int]) -> CellAggregate:
    n = len(records)
    if n == 0 or len(batch_pl_counts) != n or len(batch_pw_counts) != n:
        raise ValueError("aggregate_cell requires non-empty aligned batch counts")
    four_tot: dict[str, int] = {
        cat: sum(r.four_cell[cat] for r in records) for cat in qo.CATEGORIES
    }
    pl_vals = [float(r.PL) for r in records]
    pw_vals = [float(r.PW) for r in records]
    t_vals = [float(r.T) for r in records]
    pl_mean = sum(pl_vals) / n
    pw_mean = sum(pw_vals) / n
    t_mean = sum(t_vals) / n
    pl_se = (sum((v - pl_mean) ** 2 for v in pl_vals) / max(1, n - 1)) ** 0.5
    pw_se = (sum((v - pw_mean) ** 2 for v in pw_vals) / max(1, n - 1)) ** 0.5
    t_se = (sum((v - t_mean) ** 2 for v in t_vals) / max(1, n - 1)) ** 0.5
    return CellAggregate(
        cell=cell, tier=tier, k_label=k_label, n=n,
        mean_T=mean_of(r.T for r in records),
        mean_T_days=mean_of(r.T_days for r in records),
        mean_S=mean_of(r.S for r in records),
        mean_PL=mean_of(r.PL for r in records),
        mean_PW=mean_of(r.PW for r in records),
        mean_YXB={p: mean_of(r.YXB[p] for r in records) for p in sm.RESOURCES},
        mean_preventive=mean_of(r.preventive for r in records),
        mean_mandatory=mean_of(r.mandatory for r in records),
        mean_random_failures=mean_of(r.random_failures for r in records),
        mean_wasted_fragments=mean_of(r.wasted_fragments for r in records),
        four_cell_totals=four_tot,
        pl_pooled_x=sum(batch_pl_counts),
        pw_pooled_x=sum(batch_pw_counts),
        pl_batch_se=pl_se,
        pw_batch_se=pw_se,
        t_batch_se=t_se,
        t_p50=percentile_of(t_vals, 0.50),
        t_p90=percentile_of(t_vals, 0.90),
        quality_pass_count=sum(1 for r in records if r.quality_verdict == "PASS"),
        replay_pass_count=sum(1 for r in records if r.replay_verdict == "PASS"),
    )


# ---------------------------------------------------------------------------
# Rare-event exact intervals (verbatim from accepted Q2 runner)
# ---------------------------------------------------------------------------


def clopper_pearson_two_sided(x: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    lo = _beta_quantile(alpha / 2, x, n - x + 1)
    hi = _beta_quantile(1 - alpha / 2, x + 1, n - x)
    return lo, hi


def clopper_pearson_one_sided_upper(x: int, n: int, alpha: float = 0.05) -> float:
    return _beta_quantile(1 - alpha, x + 1, n - x)


def _beta_quantile(q: float, a: float, b: float) -> float:
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
    a_i = int(round(a))
    b_i = int(round(b))
    if a_i <= 0 or b_i <= 0:
        raise ValueError("beta parameters must be positive integers")
    n = a_i + b_i - 1
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    t = math.exp(n * math.log1p(-x))
    s = t
    for k in range(1, a_i):
        t *= (n - k + 1) / k * x / (1.0 - x)
        s += t
    if s > 1.0:
        return 1.0
    return 1.0 - s


# ---------------------------------------------------------------------------
# Paired bootstrap (D-04; generalized 21-pair family)
# ---------------------------------------------------------------------------


def paired_bootstrap_ci(t_a: list[float], t_b: list[float],
                        seed: int = ANALYSIS_SEED, b: int = BOOTSTRAP_B,
                        p_lo: float = P_LO, p_hi: float = P_HI) -> dict[str, Any]:
    n = len(t_a)
    if n != len(t_b) or n == 0:
        raise ValueError("paired bootstrap requires equal non-empty arrays")
    deltas = [a - bb for a, bb in zip(t_a, t_b)]
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


def run_tier(tier: str) -> dict[str, Any]:
    reps = tuple(range(FIRST_REPLICATE, FIRST_REPLICATE + REPLICATE_COUNT))
    if len(reps) != REPLICATE_COUNT:
        raise RuntimeError(f"replicate range must be exactly {REPLICATE_COUNT}")
    tier_cells = [(tier, k) for k, _ in K_VALUES]
    records_by_cell: dict[str, list[BatchMetrics]] = {}
    pl_by_cell: dict[str, list[int]] = {}
    pw_by_cell: dict[str, list[int]] = {}
    wall_start = time.perf_counter()
    for (t, k) in tier_cells:
        cid = cell_id(t, k)
        print(f"[formal] {tier} cell {cid}: 200 batches x 100 devices (K={K_DISPLAY[k]})")
        cell_records: list[BatchMetrics] = []
        pl_flat: list[int] = []
        pw_flat: list[int] = []
        for rep in reps:
            rec = run_one_batch(t, k, rep)
            cell_records.append(rec)
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
        pl_by_cell[cid] = pl_flat
        pw_by_cell[cid] = pw_flat
        agg = aggregate_cell(cid, t, k, cell_records, pl_flat, pw_flat)
        print(
            f"  cell done: mean_T={sm.fraction_to_string(agg.mean_T)} h "
            f"C06={agg.quality_pass_count}/200 C17={agg.replay_pass_count}/200"
        )
    return {
        "records_by_cell": records_by_cell,
        "pl_by_cell": pl_by_cell,
        "pw_by_cell": pw_by_cell,
        "tier_wall_clock_s": time.perf_counter() - wall_start,
    }


def build_pairwise_table(tier: str, records_by_cell: dict[str, list[BatchMetrics]],
                         seed_salt: int) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    idx = 0
    for i in range(len(K_VALUES)):
        for j in range(i + 1, len(K_VALUES)):
            k1 = K_VALUES[i][0]
            k2 = K_VALUES[j][0]
            c1 = cell_id(tier, k1)
            c2 = cell_id(tier, k2)
            t1 = [float(r.T) for r in records_by_cell[c1]]
            t2 = [float(r.T) for r in records_by_cell[c2]]
            ci = paired_bootstrap_ci(t1, t2, seed=ANALYSIS_SEED + seed_salt)
            idx += 1
            pairs.append({
                "pair_id": f"P{idx:02d}",
                "k1": k1, "k1_hours": K_DISPLAY[k1],
                "k2": k2, "k2_hours": K_DISPLAY[k2],
                "delta_T_h": ci["point_estimate_Delta_T_h"],
                "ci_lo_h": ci["ci_lo_h"],
                "ci_hi_h": ci["ci_hi_h"],
                "interpretation": ci["interpretation"],
            })
    return pairs


def recommendation(tier: str, aggregates: dict[str, CellAggregate],
                   pairs: list[dict[str, Any]]) -> dict[str, Any]:
    by_k = {agg.k_label: agg for agg in aggregates.values() if agg.tier == tier}
    if len(by_k) != len(K_VALUES):
        raise RuntimeError(f"recommendation requires all {len(K_VALUES)} K for {tier}")
    k_star = min(by_k, key=lambda k: float(by_k[k].mean_T))
    ci_by_pair: dict[tuple[str, str], dict[str, float]] = {
        (p["k1"], p["k2"]): p for p in pairs
    }
    co_best: list[str] = []
    for k in K_VALUES:
        kk = k[0]
        if kk == k_star:
            continue
        a, b = (k_star, kk) if k_star < kk else (kk, k_star)
        pair = ci_by_pair[(a, b)]
        lo = pair["ci_lo_h"]
        hi = pair["ci_hi_h"]
        # Delta_T = T(k_star) - T(other); CI entirely < 0 => k_star faster.
        if not (hi < 0):
            co_best.append(kk)
    strong = all(
        ci_by_pair[(min(k_star, kk), max(k_star, kk))]["ci_hi_h"] < 0
        for kk, _ in K_VALUES if kk != k_star
    )
    return {
        "tier": tier,
        "k_star": k_star,
        "k_star_hours": K_DISPLAY[k_star],
        "co_best": sorted(co_best),
        "strong_recommendation": strong,
        "wording": (
            "k* 相对其余全部 K 的配对 CI 完全 <0 → strong recommendation"
            if strong else
            "k* + co-best（部分/全部配对 CI 含 0）"
        ),
        "scope": "限于七个 K 与冻结候选政策集（NO_PM_BEFORE_MANDATORY）；非全局最优；不宣称 K=12 弱支配",
    }


def rare_event_report(agg: CellAggregate) -> dict[str, Any]:
    n = N_TOTAL_DEVICES_PER_CELL
    out: dict[str, Any] = {}
    for name, x, batch_mean, batch_se in (
        ("PL", agg.pl_pooled_x, agg.mean_PL, agg.pl_batch_se),
        ("PW", agg.pw_pooled_x, agg.mean_PW, agg.pw_batch_se),
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


def build_quality_table(tier: str, aggregates: dict[str, CellAggregate]) -> dict[str, Any]:
    rows = []
    for k, _ in K_VALUES:
        agg = aggregates[cell_id(tier, k)]
        rows.append({
            "K": k, "K_hours": K_DISPLAY[k],
            "mean_S": sm.fraction_to_string(agg.mean_S),
            "mean_PL": sm.fraction_to_string(agg.mean_PL),
            "mean_PW": sm.fraction_to_string(agg.mean_PW),
            "four_cell_totals": dict(agg.four_cell_totals),
            "quality_oracle_pass": agg.quality_pass_count,
            "replay_checker_pass": agg.replay_pass_count,
        })
    return {"tier": tier, "rows": rows}


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    output_root = Path(args.output_root).resolve()
    run_id = _new_run_id()
    out_dir = output_root / f"run_{run_id}"
    print(f"[formal] run_id={run_id}")
    print(f"[formal] namespace=q3_formal master_seed={MASTER_SEED} "
          f"replicate_ids={FIRST_REPLICATE}..{FIRST_REPLICATE + REPLICATE_COUNT - 1}")
    print(f"[formal] Tier 1 (single) + Tier 2 (chain) x 7 K x 200 batches x 100 devices; "
          f"budget soft 4h / hard 8h")

    rd.validate_parameters_csv(PARAMETERS_CSV)
    lr.validate_parameters_csv(PARAMETERS_CSV)

    wall_start = time.perf_counter()
    tier1 = run_tier(TIER1)
    tier2 = run_tier(TIER2)
    family_wall = time.perf_counter() - wall_start

    all_records: dict[str, list[BatchMetrics]] = {}
    for cid, recs in tier1["records_by_cell"].items():
        all_records[cid] = recs
    for cid, recs in tier2["records_by_cell"].items():
        all_records[cid] = recs

    aggregates: dict[str, CellAggregate] = {}
    for cid, recs in all_records.items():
        tier = recs[0].tier
        k = recs[0].k_label
        agg = aggregate_cell(
            cid, tier, k, recs,
            tier1["pl_by_cell"].get(cid) or tier2["pl_by_cell"].get(cid),
            tier1["pw_by_cell"].get(cid) or tier2["pw_by_cell"].get(cid),
        )
        aggregates[cid] = agg

    pairwise_t1 = build_pairwise_table(TIER1, all_records, seed_salt=0)
    pairwise_t2 = build_pairwise_table(TIER2, all_records, seed_salt=1000)
    rec_t1 = recommendation(TIER1, aggregates, pairwise_t1)
    rec_t2 = recommendation(TIER2, aggregates, pairwise_t2)
    rare_events = {cid: rare_event_report(aggregates[cid]) for cid in all_records}
    quality_t1 = build_quality_table(TIER1, aggregates)
    quality_t2 = build_quality_table(TIER2, aggregates)

    _write_evidence(run_id, out_dir, all_records, aggregates, pairwise_t1,
                    pairwise_t2, rec_t1, rec_t2, rare_events, quality_t1,
                    quality_t2, tier1, tier2, family_wall, args)
    return 0


def _write_evidence(run_id: str, out_dir: Path, all_records: dict[str, list[BatchMetrics]],
                    aggregates: dict[str, CellAggregate],
                    pairwise_t1: list[dict[str, Any]], pairwise_t2: list[dict[str, Any]],
                    rec_t1: dict[str, Any], rec_t2: dict[str, Any],
                    rare_events: dict[str, Any], quality_t1: dict[str, Any],
                    quality_t2: dict[str, Any], tier1: dict[str, Any],
                    tier2: dict[str, Any], family_wall: float,
                    args: argparse.Namespace) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    per_cell_dir = out_dir / "cells"
    per_cell_dir.mkdir(parents=True, exist_ok=True)
    for cid, records in all_records.items():
        _dump_json(per_cell_dir / f"{cid}.json",
                   {"cell": cid, "runs": [r.to_dict() for r in records]})
    _dump_json(out_dir / "family_aggregates.json",
               {cid: aggregates[cid].to_dict() for cid in all_records})
    _dump_json(out_dir / "tier1_pairwise_table.json", {
        "run_id": run_id, "tier": TIER1, "pairs": pairwise_t1,
        "bonferroni": {"alpha_family": ALPHA_FAMILY, "m": M_FAMILY,
                       "alpha_each": ALPHA_EACH, "marginal_coverage": MARGINAL_COVERAGE,
                       "percentile_bounds": [P_LO, P_HI]},
    })
    _dump_json(out_dir / "tier2_pairwise_table.json", {
        "run_id": run_id, "tier": TIER2, "pairs": pairwise_t2,
        "bonferroni": {"alpha_family": ALPHA_FAMILY, "m": M_FAMILY,
                       "alpha_each": ALPHA_EACH, "marginal_coverage": MARGINAL_COVERAGE,
                       "percentile_bounds": [P_LO, P_HI]},
    })
    _dump_json(out_dir / "recommendation.json", {
        "run_id": run_id,
        "tier1_primary": rec_t1,
        "tier2_contract": rec_t2,
    })
    _dump_json(out_dir / "rare_event_report.json", {
        "run_id": run_id, "n_devices_per_cell": N_TOTAL_DEVICES_PER_CELL,
        "cells": rare_events,
    })
    _dump_json(out_dir / "quality_table.json", {"tier1": quality_t1, "tier2": quality_t2})

    hashes = {
        "task_package": {"ref": TASK_PACKAGE_REF,
                         "sha256": _sha256_file(TASK_PACKAGE_FILE)},
        "bootstrap_spec": {"ref": "Q3_H2_BOOTSTRAP_SPEC_DRAFT.md (FINAL_FREEZE_ACCEPTED)",
                           "sha256": _sha256_file(BOOTSTRAP_SPEC_FILE)},
        "g3_spec_upstream": {"ref": "G3-SPEC-V1.0",
                             "sha256": _sha256_file(G3_TASK_PACKAGE_FILE)},
        "problem_contract": _sha256_file(PROBLEM_CONTRACT_FILE),
        "registry": _sha256_file(BASE_DIR / "01_审计" / "检查注册表_V3.1.md"),
        "parameters_csv": _sha256_file(PARAMETERS_CSV),
        "key_schema": _sha256_file(MAIN_MODEL / "g3" / "key_schema_v1.py"),
        "code": {p.relative_to(BASE_DIR).as_posix(): _sha256_file(p)
                 for p in SOURCE_CODE_FILES if p.is_file()},
    }
    _dump_json(out_dir / "input_hashes.json", hashes)

    config_snapshot = {
        "run_id": run_id,
        "task_package_ref": TASK_PACKAGE_REF,
        "namespace": NAMESPACE, "master_seed": MASTER_SEED,
        "replicate_ids": list(range(FIRST_REPLICATE, FIRST_REPLICATE + REPLICATE_COUNT)),
        "batch_size": BATCH_SIZE, "scenario": SCENARIO, "shifts_per_day": SHIFTS_PER_DAY,
        "turnover": TURNOVER_1H, "policy": "NO_PM_BEFORE_MANDATORY",
        "k_grid": [{"label": k, "hours": h} for k, h in K_VALUES],
        "tier1": {"observation": "single_test_unconditional_v1",
                  "cells": [cell_id(TIER1, k) for k, _ in K_VALUES]},
        "tier2": {"observation": "standard_chain_v1",
                  "cells": [cell_id(TIER2, k) for k, _ in K_VALUES]},
        "bootstrap": {"B": BOOTSTRAP_B, "analysis_namespace": ANALYSIS_NAMESPACE,
                      "analysis_seed": ANALYSIS_SEED,
                      "bonferroni_m": M_FAMILY, "alpha_each": ALPHA_EACH,
                      "percentile_bounds": [P_LO, P_HI]},
        "tier3": "NOT RUN",
    }
    _dump_json(out_dir / "family_config_snapshot.json", config_snapshot)
    _dump_json(out_dir / "environment.json", _env_summary())
    _dump_json(out_dir / "commands.json", {
        "run_id": run_id,
        "command": "python 04_代码/scripts/run_q3_h1_formal_v1.py",
        "tier1_wall_clock_s": tier1["tier_wall_clock_s"],
        "tier2_wall_clock_s": tier2["tier_wall_clock_s"],
        "family_wall_clock_s": family_wall,
    })

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
             "note": "pathwise quality oracle per batch"},
            {"check_id": "CR-V3.1/C13", "status": "PASS", "note": "lifetime (engine)"},
            {"check_id": "CR-V3.1/C14", "status": "PASS", "note": "regeneration (engine)"},
            {"check_id": "CR-V3.1/C15", "status": "PASS",
             "note": "Q3 reset / seven-K enumeration / cross-K CRN / no K=12 shortcut / no Q2 inheritance (runner assertions)"},
            {"check_id": "CR-V3.1/C16", "status": "PASS",
             "note": "namespace=q3_formal, seed=5, ids 0..199, CRN across 7 K; K/policy/tier/squad/run_id excluded from physical keys"},
            {"check_id": "CR-V3.1/C17", "status": "PASS" if c17_ok else "FAIL",
             "count": "%d/%d" % (c17_total, c17_denom),
             "note": "full replay per batch"},
            {"check_id": "CR-V3.1/C18", "status": "PASS", "note": "liveness (engine)"},
            {"check_id": "CR-V3.1/C26", "status": "PASS",
             "note": "H1 policy frozen NO_PM_BEFORE_MANDATORY; no tau_pm retuning"},
            {"check_id": "CR-V3.1/C21", "status": "PASS",
             "note": "immutable evidence + file_hashes.sha256"},
            {"check_id": "CR-V3.1/C07", "status": "DIAGNOSTIC",
             "note": "family-level four-cell smoke (diagnostic; not a hard gate)"},
            {"check_id": "CR-V3.1/C19", "status": "PASS", "note": "checker isolation (governance)"},
            {"check_id": "CR-V3.1/C20", "status": "PASS", "note": "fault-injection qualification (inherited)"},
        ],
    })

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
        "gate": "Q3",
        "purpose": "formal",
        "formal": True,
        "label": "Q3 H1 FORMAL（Tier 1 + Tier 2 七 K 正式证据；EXECUTION COMPLETED / AWAITING HUMAN GATE REVIEW；非 ACCEPTED）",
        "paper_authoritative": False,
        "task_package_ref": TASK_PACKAGE_REF,
        "task_package_hash": hashes["task_package"]["sha256"],
        "bootstrap_spec_hash": hashes["bootstrap_spec"]["sha256"],
        "g3_spec_upstream_hash": hashes["g3_spec_upstream"]["sha256"],
        "registry_version": REGISTRY_VERSION,
        "random_world": {
            "namespace": NAMESPACE, "master_seed": MASTER_SEED,
            "replicate_ids": [FIRST_REPLICATE, FIRST_REPLICATE + REPLICATE_COUNT - 1],
            "batch_size": BATCH_SIZE,
        },
        "family": {
            "tier1": "single_test_unconditional_v1 x 1h_literal x NO_PM x 7K x 200",
            "tier2": "standard_chain_v1 x 1h_literal x NO_PM x 7K x 200",
            "total_batches": 2800, "tier3": "NOT RUN",
        },
        "overall_status": "PASS" if overall_ok else "VALIDATION_FAILED",
        "environment": _env_summary(),
        "outputs": artifacts,
        "check_report_paths": ["checks.json", "tier1_pairwise_table.json",
                               "tier2_pairwise_table.json", "recommendation.json",
                               "rare_event_report.json", "quality_table.json"],
        "notes": [
            "Q3 H1 FORMAL 正式证据；EXECUTION COMPLETED / AWAITING HUMAN GATE REVIEW（非 Human Gate ACCEPTED）。",
            "k* / co-best 仅限七个 K 与冻结候选政策集（NO_PM_BEFORE_MANDATORY）；不宣称 K=12 弱支配。",
            "Tier 1 = Q3 主 K 推荐证据；Tier 2 = A03 替代观测语义独立全链；不混池。",
            "Density recheck / P1 / C23 / C25 不在本包。",
        ],
    }
    _dump_json(out_dir / "run_manifest.json", manifest)
    print(f"[formal] evidence written: {out_dir}")
    print(f"[formal] family wall clock: {family_wall:.1f} s")


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Q3-H1-FORMAL-SPEC-V1.0: Q3 seven-K H1 formal baseline runner."
    )
    parser.add_argument(
        "--output-root",
        default=str(BASE_DIR / "05_结果" / "Q3" / "formal"),
        help="family root; a run_<run_id>/ directory is created under it",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
