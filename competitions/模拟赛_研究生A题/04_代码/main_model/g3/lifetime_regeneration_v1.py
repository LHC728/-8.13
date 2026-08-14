"""G3-SPEC-V1.0 sections 4/5 (CR-V3.1/C13, C14): equipment lifetime model
and regeneration semantics.

Frozen contract sources (authoritative, in order):
  * G3-SPEC-V1.0 section 4 ``lifetime_model`` (C13): piecewise-linear CDF
    main model, exact inverse-CDF three-branch sampling, exactly one U_L per
    (resource, generation), no renormalization of the [0,240] CDF.
  * G3-SPEC-V1.0 section 5 ``regeneration_semantics`` (C14): the a+d
    boundary rules, replacement/calibration, event order (same-instant
    completion settles first), and the ``illegal_crossing_fallback``
    (mandatory-240 force-interrupt backstop for S3 integration and fault
    injection).
  * G3-SPEC-V1.0 section 7 ``c26_preventive_replacement`` triggered A-H:
    this module provides ONLY the pure preventive-replacement decision seam;
    dispatch/queue/shift integration is S3's responsibility.
  * V3.1 section 7 (device failure / 240 h / regeneration) and the signed
    problem contract section 1.2.
  * parameters.csv rows P010-P013 (frozen calibration durations),
    P016 (120 h minimum preventive age), P017 (240 h mandatory age),
    P018-P025 (F_*_120 / F_*_240 CDF nodes).

Canonical time is an exact ``fractions.Fraction`` in hours; binary float is
forbidden in every canonical path. The only float-returning functions are the
constant-hazard *sensitivity* constructs (``sensitivity_*``), which are
independent of the main path by G3-SPEC-V1.0 section 4 ``sensitivity`` and
never feed the main model.

No dispatch and no policy decision are made here: every public function is
pure; S3 integrates them into the DES state machine.

Python 3.12, standard library only.
"""

from __future__ import annotations

import csv
import math
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import NamedTuple

from . import key_schema_v1

# ---------------------------------------------------------------------------
# Frozen parameters (parameters.csv; exact rational values)
# ---------------------------------------------------------------------------

# P017: mandatory replacement age, 240 h (a_max).
MANDATORY_REPLACE_AGE_H: Fraction = Fraction(240, 1)
# P016: minimum age for preventive replacement, 120 h (a_min).
MIN_PREVENTIVE_AGE_H: Fraction = Fraction(120, 1)

# P018-P021: F_*_120 CDF nodes (self-0h cumulative probability at 120 h).
FROZEN_F120: dict[str, Fraction] = {
    "A": Fraction(3, 100),  # P018 F_A_120 = 0.03
    "B": Fraction(4, 100),  # P019 F_B_120 = 0.04
    "C": Fraction(2, 100),  # P020 F_C_120 = 0.02
    "E": Fraction(3, 100),  # P021 F_E_120 = 0.03
}

# P022-P025: F_*_240 CDF nodes (cumulative probability at 240 h).
FROZEN_F240: dict[str, Fraction] = {
    "A": Fraction(5, 100),  # P022 F_A_240 = 0.05
    "B": Fraction(7, 100),  # P023 F_B_240 = 0.07
    "C": Fraction(6, 100),  # P024 F_C_240 = 0.06
    "E": Fraction(5, 100),  # P025 F_E_240 = 0.05
}

# P010-P013: frozen resource calibration durations after replacement, minutes.
CALIBRATION_DURATION_MINUTES_FROZEN: dict[str, Fraction] = {
    "A": Fraction(30, 1),  # P010 t_cal_A = 30 min
    "B": Fraction(20, 1),  # P011 t_cal_B = 20 min
    "C": Fraction(20, 1),  # P012 t_cal_C = 20 min
    "E": Fraction(40, 1),  # P013 t_cal_E = 40 min
}

# Frozen C14 semantics markers (G3-SPEC-V1.0 section 5 ``calibration``;
# V3.1 section 7; P062 nonpreemptive_within_shift_v1):
# calibration does NOT accumulate device test age, and calibration is NOT
# allowed to cross a shift boundary (换新+校准 must complete within one shift).
CALIBRATION_COUNTS_AGE: bool = False
CALIBRATION_CROSS_SHIFT_ALLOWED: bool = False

# Frozen parameters.csv rows owned by this module, parameter_id -> exact value.
FROZEN_CSV_ROWS: dict[str, Fraction] = {
    "P010": CALIBRATION_DURATION_MINUTES_FROZEN["A"],
    "P011": CALIBRATION_DURATION_MINUTES_FROZEN["B"],
    "P012": CALIBRATION_DURATION_MINUTES_FROZEN["C"],
    "P013": CALIBRATION_DURATION_MINUTES_FROZEN["E"],
    "P016": MIN_PREVENTIVE_AGE_H,
    "P017": MANDATORY_REPLACE_AGE_H,
    "P018": FROZEN_F120["A"],
    "P019": FROZEN_F120["B"],
    "P020": FROZEN_F120["C"],
    "P021": FROZEN_F120["E"],
    "P022": FROZEN_F240["A"],
    "P023": FROZEN_F240["B"],
    "P024": FROZEN_F240["C"],
    "P025": FROZEN_F240["E"],
}

# ---------------------------------------------------------------------------
# Enums / sentinels
# ---------------------------------------------------------------------------


class ReplacementDecision(Enum):
    """Pure outcome of the C26 triggered A-H preventive-replacement seam.

    Frozen member semantics (G3-SPEC-V1.0 section 5 ``cases`` and section 7
    ``positive_preventive_trigger`` A-H):

    * MANDATORY_REPLACE_FIRST -- a+d > 240: the head task cannot start;
      force replace + calibrate before serving the head (D; NOT preventive).
    * EXACT_240_COMPLETE_FIRST -- a+d == 240: the task may complete; the
      same-instant completion is settled first, then the mandatory
      replacement follows (E; completion-settles-first semantic marker).
    * PREVENTIVE_REPLACE -- a+d < 240 and a >= tau_pm (numeric policy) and
      the moment is a legal idle decision point (F + A).
    * SERVE_HEAD -- otherwise: serve the FCFS head (includes G: under
      NO_PM_BEFORE_MANDATORY preventive never triggers; and the idle-point
      constraint).
    """

    PREVENTIVE_REPLACE = "preventive_replace"
    SERVE_HEAD = "serve_head"
    MANDATORY_REPLACE_FIRST = "mandatory_replace_first"
    EXACT_240_COMPLETE_FIRST = "exact_240_complete_first"


class _NoPMBeforeMandatoryType:
    """Sentinel type for the frozen policy NO_PM_BEFORE_MANDATORY
    (G3-SPEC-V1.0 section 7 ``coarse_candidates``)."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "NO_PM_BEFORE_MANDATORY"


# Independent policy baseline: never do preventive replacement; only the
# frozen mandatory-age rules apply. NOT tau_pm = 240 (G3-SPEC-V1.0 section 7
# ``no_240_as_preventive``).
NO_PM_BEFORE_MANDATORY = _NoPMBeforeMandatoryType()


class IllegalCrossingOutcome(NamedTuple):
    """Outcome of the mandatory-240 illegal-crossing backstop
    (G3-SPEC-V1.0 section 5 ``illegal_crossing_fallback``).

    When a running task's scheduled end would cross 240 h
    (``a_start + d > 240``), the underlying state machine force-interrupts it
    at age 240: the fragment accumulates age/YXB up to the 240 h boundary, no
    observation is produced, the effective attempt number is unchanged, the
    device becomes unavailable and must be replaced + calibrated.
    """

    triggered: bool
    interrupt_age_h: Fraction | None = None
    fragment_duration_h: Fraction | None = None
    no_observation: bool = False
    attempt_unchanged: bool = False
    device_unavailable_after: bool = False
    replacement_required_after: bool = False


class FailureImpactOutcome(NamedTuple):
    """C14 random-failure impact of a task fragment (G3-SPEC-V1.0 section 5
    ``cases``: random failure before task completion).

    A failure earlier than the task end interrupts the fragment: the fragment
    counts age/YXB, produces no observation, leaves the effective attempt
    unchanged, makes the device unavailable and requires replacement +
    calibration. A failure exactly at the task end is settled by the
    same-instant completion-first rule (not an interruption).
    """

    interrupted: bool
    fragment_duration_h: Fraction | None = None
    no_observation: bool = False
    attempt_unchanged: bool = False
    device_unavailable_after: bool = False
    replacement_required_after: bool = False


# ---------------------------------------------------------------------------
# Input validation helpers (canonical values are int or Fraction; binary
# float is rejected so it can never enter a canonical path)
# ---------------------------------------------------------------------------


def _as_fraction(value, name: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise TypeError(
            f"{name} must be an int or Fraction (binary float is forbidden "
            f"as canonical), got {type(value).__name__}"
        )
    return value if isinstance(value, Fraction) else Fraction(value)


def _validate_u(u: Fraction) -> None:
    if u < Fraction(0) or u >= Fraction(1):
        raise ValueError(f"u must be in [0, 1), got {u!r}")


def _validate_cdf_nodes(f120: Fraction, f240: Fraction) -> None:
    if not (Fraction(0) < f120 < f240 < Fraction(1)):
        raise ValueError(
            "frozen CDF nodes must satisfy 0 < f120 < f240 < 1 "
            f"(inverse-CDF branch 2 divides by F_240-F_120), got "
            f"f120={f120!r}, f240={f240!r}"
        )


def _require_resource(resource) -> str:
    if resource not in key_schema_v1.PROCESSES:
        raise ValueError(
            f"resource must be one of {key_schema_v1.PROCESSES}, got {resource!r}"
        )
    return resource


# ---------------------------------------------------------------------------
# C13: piecewise-linear CDF main model (G3-SPEC-V1.0 section 4; V3.1 section 7)
# ---------------------------------------------------------------------------


def piecewise_linear_f(t, f120, f240) -> Fraction:
    """Piecewise-linear CDF F(t), exact Fraction:

        F(t) = F_120 * t/120              for 0 <= t <= 120
        F(t) = F_120 + (F_240-F_120) * (t-120)/120   for 120 < t <= 240

    ``t`` must lie in [0, 240] hours (the main model defines F only there;
    ages beyond 240 are unreachable because the device is deterministically
    force-replaced at 240 h -- P017). ``f120``/``f240`` are the frozen CDF
    nodes (0 < f120 < f240 < 1). Returns a ``Fraction``; no binary float.
    """
    t = _as_fraction(t, "t")
    f120 = _as_fraction(f120, "f120")
    f240 = _as_fraction(f240, "f240")
    _validate_cdf_nodes(f120, f240)
    if t < Fraction(0) or t > MANDATORY_REPLACE_AGE_H:
        raise ValueError(
            f"t must be in [0, 240] hours (F is defined only on [0,240] by "
            f"G3-SPEC-V1.0 section 4), got {t!r}"
        )
    if t <= Fraction(120, 1):
        return f120 * t / Fraction(120, 1)
    return f120 + (f240 - f120) * (t - Fraction(120, 1)) / Fraction(120, 1)


def inverse_cdf(u, f120, f240) -> tuple[Fraction | None, bool]:
    """Exact three-branch inverse CDF (G3-SPEC-V1.0 section 4
    ``inverse_cdf_cases``). Returns ``(lifetime_hour, is_right_censored)``:

    * ``0..120 h`` branch:  t = 120*U/F_120            for U <= F_120
    * ``120..240 h`` branch: t = 120 + 120*(U-F_120)/(F_240-F_120)
                                                       for F_120 < U <= F_240
    * ``U > F(240)``: right-censored lifetime > 240 h -> ``(None, True)``.

    The [0,240] CDF is NEVER renormalized to U in [0, F(240)] (forbidden by
    the spec): the raw U is compared against the raw F_240 node. ``u`` must
    be an exact Fraction in [0, 1).
    """
    u = _as_fraction(u, "u")
    f120 = _as_fraction(f120, "f120")
    f240 = _as_fraction(f240, "f240")
    _validate_u(u)
    _validate_cdf_nodes(f120, f240)
    if u <= f120:
        return Fraction(120, 1) * u / f120, False
    if u <= f240:
        return (
            Fraction(120, 1)
            + Fraction(120, 1) * (u - f120) / (f240 - f120),
            False,
        )
    return None, True


def sample_lifetime(
    namespace, rep, resource, generation, seed, f120, f240
) -> tuple[Fraction | None, bool]:
    """Sample one lifetime for a device generation (G3-SPEC-V1.0 section 4
    ``per_generation``): exactly one U_L from key_schema_v1.u_l
    (namespace, rep, resource, generation, seed), then the exact
    three-branch inverse CDF. The pair (resource, generation) fully
    determines the canonical key, so the same pair always yields the same
    U_L and the same lifetime. Returns the same tuple contract as
    :func:`inverse_cdf`.
    """
    f120 = _as_fraction(f120, "f120")
    f240 = _as_fraction(f240, "f240")
    _validate_cdf_nodes(f120, f240)
    u = key_schema_v1.u_l(namespace, rep, resource, generation, seed)
    return inverse_cdf(u, f120, f240)


def sample_lifetime_frozen(
    namespace, rep, resource, generation, seed
) -> tuple[Fraction | None, bool]:
    """Convenience: :func:`sample_lifetime` with the frozen parameters.csv
    CDF nodes for ``resource`` (P018-P025)."""
    return sample_lifetime(
        namespace,
        rep,
        resource,
        generation,
        seed,
        frozen_f120(resource),
        frozen_f240(resource),
    )


# ---------------------------------------------------------------------------
# Frozen parameter queries (parameters.csv)
# ---------------------------------------------------------------------------


def frozen_f120(resource) -> Fraction:
    """F_*_120 CDF node for ``resource`` (P018-P021), exact Fraction."""
    resource = _require_resource(resource)
    return FROZEN_F120[resource]


def frozen_f240(resource) -> Fraction:
    """F_*_240 CDF node for ``resource`` (P022-P025), exact Fraction."""
    resource = _require_resource(resource)
    return FROZEN_F240[resource]


def calibration_duration_minutes(resource) -> Fraction:
    """Frozen calibration duration for ``resource`` (P010-P013), in minutes
    as an exact Fraction (30/20/20/40 min for A/B/C/E)."""
    resource = _require_resource(resource)
    return CALIBRATION_DURATION_MINUTES_FROZEN[resource]


def calibration_duration_hours(resource) -> Fraction:
    """Frozen calibration duration for ``resource`` in hours, exact Fraction
    (canonical time unit): A=1/2 h, B=1/3 h, C=1/3 h, E=2/3 h."""
    return calibration_duration_minutes(resource) / Fraction(60, 1)


def validate_parameters_csv(csv_path) -> dict[str, Fraction]:
    """Audit helper: read ``parameters.csv`` and verify that the frozen rows
    owned by this module (P010-P013, P016-P018, P018-P025) exactly match the
    module constants. Raises ``ValueError`` on a missing row or a value
    mismatch (fail loudly; never silently accept a drifted parameter).
    Returns ``{parameter_id: Fraction}`` for the verified rows.
    """
    path = Path(csv_path)
    verified: dict[str, Fraction] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pid = (row.get("parameter_id") or "").strip()
            if pid not in FROZEN_CSV_ROWS:
                continue
            raw = (row.get("value") or "").strip()
            try:
                value = Fraction(raw)
            except (ValueError, ZeroDivisionError) as exc:
                raise ValueError(
                    f"parameters.csv row {pid}: cannot parse value {raw!r}"
                ) from exc
            if value != FROZEN_CSV_ROWS[pid]:
                raise ValueError(
                    f"parameters.csv row {pid}: frozen value mismatch: "
                    f"expected {FROZEN_CSV_ROWS[pid]!r}, got {value!r}"
                )
            verified[pid] = value
    missing = [pid for pid in FROZEN_CSV_ROWS if pid not in verified]
    if missing:
        raise ValueError(f"parameters.csv missing frozen rows: {missing}")
    return verified


# ---------------------------------------------------------------------------
# C14: regeneration semantics (G3-SPEC-V1.0 section 5)
# ---------------------------------------------------------------------------


def replacement_decision(
    a, d, tau_pm_or_NO_PM, is_idle_decision_point
) -> ReplacementDecision:
    """Pure C26 triggered A-H decision seam (G3-SPEC-V1.0 section 7), with
    ``a`` = current equipment age (h), ``d`` = requested head-task duration
    (h), ``tau_pm_or_NO_PM`` = numeric preventive threshold in [120, 240) or
    the sentinel ``NO_PM_BEFORE_MANDATORY``, ``is_idle_decision_point`` =
    whether this is a legal idle decision point (trigger A).

    Frozen priority (section 7 ``positive_preventive_trigger`` A-H, and
    section 5 ``cases``):

    1. ``a+d > 240``  -> MANDATORY_REPLACE_FIRST (forced, never preventive).
    2. ``a+d == 240`` -> EXACT_240_COMPLETE_FIRST (may complete; completion
       settles first, then mandatory replacement).
    3. otherwise, preventive only if ``tau_pm`` is numeric AND
       ``a >= tau_pm`` AND ``is_idle_decision_point`` ->
       PREVENTIVE_REPLACE.
    4. everything else -> SERVE_HEAD. Under NO_PM_BEFORE_MANDATORY (G),
       preventive never triggers; 240 is mandatory semantics, never encoded
       as a preventive threshold (``no_240_as_preventive``).

    This function makes no dispatch decision; the caller (S3) integrates the
    result with the shift calendar and the FCFS queue.
    """
    a = _as_fraction(a, "a")
    d = _as_fraction(d, "d")
    if a < Fraction(0) or a > MANDATORY_REPLACE_AGE_H:
        raise ValueError(
            f"a (current age) must be in [0, 240] hours, got {a!r}"
        )
    if d <= Fraction(0):
        raise ValueError(f"d (requested duration) must be > 0, got {d!r}")
    if not isinstance(is_idle_decision_point, bool):
        raise TypeError(
            "is_idle_decision_point must be a bool, got "
            f"{type(is_idle_decision_point).__name__}"
        )
    if tau_pm_or_NO_PM is NO_PM_BEFORE_MANDATORY:
        tau_pm: Fraction | None = None
    else:
        tau_pm = _as_fraction(tau_pm_or_NO_PM, "tau_pm")
        if not (MIN_PREVENTIVE_AGE_H <= tau_pm < MANDATORY_REPLACE_AGE_H):
            raise ValueError(
                "numeric tau_pm must be in [120, 240) hours "
                "(240 is mandatory semantics, never a preventive threshold; "
                f"NO_PM_BEFORE_MANDATORY is the no-prevention policy), got "
                f"{tau_pm!r}"
            )

    if a + d > MANDATORY_REPLACE_AGE_H:
        return ReplacementDecision.MANDATORY_REPLACE_FIRST
    if a + d == MANDATORY_REPLACE_AGE_H:
        return ReplacementDecision.EXACT_240_COMPLETE_FIRST
    # a + d < 240
    if tau_pm is None:
        return ReplacementDecision.SERVE_HEAD
    if a >= tau_pm and is_idle_decision_point:
        return ReplacementDecision.PREVENTIVE_REPLACE
    return ReplacementDecision.SERVE_HEAD


def mandatory_240_interrupt_fallback(
    a_start, d
) -> IllegalCrossingOutcome:
    """Mandatory-240 illegal-crossing backstop (G3-SPEC-V1.0 section 5
    ``illegal_crossing_fallback``; V3.1 section 7): if a running task with
    start age ``a_start`` and duration ``d`` would end past 240 h
    (``a_start + d > 240``), the state machine force-interrupts it at age
    240. This is the fault-injection backstop kept for S3 integration; a
    legal task always satisfies ``a_start + d <= 240``.

    Outcome fields (when triggered): ``interrupt_age_h = 240``,
    ``fragment_duration_h = 240 - a_start`` (the fragment counts age/YXB up
    to the boundary), ``no_observation = True``, ``attempt_unchanged = True``,
    ``device_unavailable_after = True``, ``replacement_required_after = True``.
    ``a_start + d == 240`` is legal (completion settles first) and does NOT
    trigger. ``a_start`` must be < 240 h (a device at/after age 240 is
    force-replaced and cannot run a task).
    """
    a_start = _as_fraction(a_start, "a_start")
    d = _as_fraction(d, "d")
    if a_start < Fraction(0) or a_start >= MANDATORY_REPLACE_AGE_H:
        raise ValueError(
            f"a_start must be in [0, 240) hours (the device is force-"
            f"replaced at 240 h), got {a_start!r}"
        )
    if d <= Fraction(0):
        raise ValueError(f"d must be > 0, got {d!r}")
    if a_start + d <= MANDATORY_REPLACE_AGE_H:
        return IllegalCrossingOutcome(triggered=False)
    return IllegalCrossingOutcome(
        triggered=True,
        interrupt_age_h=MANDATORY_REPLACE_AGE_H,
        fragment_duration_h=MANDATORY_REPLACE_AGE_H - a_start,
        no_observation=True,
        attempt_unchanged=True,
        device_unavailable_after=True,
        replacement_required_after=True,
    )


def failure_impact(
    a_start, d, lifetime_h, is_right_censored
) -> FailureImpactOutcome:
    """C14 random-failure impact of a task fragment (G3-SPEC-V1.0 section 5
    ``cases``: random failure earlier than task completion).

    ``a_start`` = age at fragment start, ``d`` = fragment duration,
    ``lifetime_h`` = the generation's sampled failure age (a Fraction) or
    None when ``is_right_censored`` (lifetime > 240 h, no failure inside the
    model horizon). Returns:

    * interrupted=False -- the fragment completes: no failure before the
      end, or the failure hits exactly at the end instant, in which case the
      same-instant completion settles first (section 5 ``event_order``).
    * interrupted=True -- failure at age ``a_start < L < a_start + d``: the
      fragment is interrupted; ``fragment_duration_h = L - a_start`` counts
      age/YXB, no observation, effective attempt unchanged, device
      unavailable, replacement + calibration required.

    A lifetime ``L <= a_start`` is an inconsistent state (the device should
    already have failed and been replaced) and raises ``ValueError``.
    """
    a_start = _as_fraction(a_start, "a_start")
    d = _as_fraction(d, "d")
    if a_start < Fraction(0):
        raise ValueError(f"a_start must be >= 0, got {a_start!r}")
    if d <= Fraction(0):
        raise ValueError(f"d must be > 0, got {d!r}")
    if not isinstance(is_right_censored, bool):
        raise TypeError(
            "is_right_censored must be a bool, got "
            f"{type(is_right_censored).__name__}"
        )
    if is_right_censored:
        if lifetime_h is not None:
            raise ValueError(
                "right-censored lifetime must pass lifetime_h=None "
                "(lifetime > 240 h)"
            )
        return FailureImpactOutcome(interrupted=False)
    if lifetime_h is None:
        raise ValueError(
            "a non-censored lifetime must be provided (lifetime_h is None)"
        )
    lifetime_h = _as_fraction(lifetime_h, "lifetime_h")
    if lifetime_h <= Fraction(0):
        raise ValueError(f"lifetime must be > 0, got {lifetime_h!r}")
    if lifetime_h <= a_start:
        raise ValueError(
            f"inconsistent state: generation lifetime {lifetime_h!r} <= "
            f"current age {a_start!r}; the device should already have failed "
            f"and been replaced"
        )
    end = a_start + d
    if lifetime_h > end:
        return FailureImpactOutcome(interrupted=False)
    if lifetime_h == end:
        # same-instant: completion settles first (section 5 event_order)
        return FailureImpactOutcome(interrupted=False)
    return FailureImpactOutcome(
        interrupted=True,
        fragment_duration_h=lifetime_h - a_start,
        no_observation=True,
        attempt_unchanged=True,
        device_unavailable_after=True,
        replacement_required_after=True,
    )


# ---------------------------------------------------------------------------
# Constant-hazard sensitivity constructs (G3-SPEC-V1.0 section 4
# ``sensitivity``; V3.1 section 7). Independent of the main path; float.
# ---------------------------------------------------------------------------


def sensitivity_h1_h2(f120, f240) -> tuple[float, float]:
    """Constant-hazard sensitivity rates (V3.1 section 7), exact node hits:

        h1 = -ln(1-F_120)/120
        h2 = -ln((1-F_240)/(1-F_120))/120

    Sensitivity only (returns binary floats; the main model stays exact
    piecewise-linear). ``f120``/``f240`` are the frozen CDF nodes.
    """
    f120 = _as_fraction(f120, "f120")
    f240 = _as_fraction(f240, "f240")
    _validate_cdf_nodes(f120, f240)
    f1 = float(f120)
    f2 = float(f240)
    h1 = -math.log(1.0 - f1) / 120.0
    h2 = -math.log((1.0 - f2) / (1.0 - f1)) / 120.0
    return h1, h2


def sensitivity_exponential_sample(h, u) -> float:
    """Exponential sampling under a constant hazard ``h > 0``:

        T = -ln(1-U)/h  (hours, float)

    Sensitivity only; ``u`` is an exact Fraction in [0, 1).
    """
    if isinstance(h, bool) or not isinstance(h, (int, float)):
        raise TypeError(f"h must be an int or float, got {type(h).__name__}")
    h_f = float(h)
    if not math.isfinite(h_f) or h_f <= 0.0:
        raise ValueError(f"h must be a positive finite rate, got {h!r}")
    u = _as_fraction(u, "u")
    _validate_u(u)
    return -math.log(1.0 - float(u)) / h_f


def sensitivity_constant_hazard_inverse_cdf(
    u, f120, f240
) -> tuple[float | None, bool]:
    """Sensitivity: inverse CDF of the piecewise-constant-hazard lifetime
    model with rates :func:`sensitivity_h1_h2` (h1 on [0,120), h2 on
    [120,240)), hitting the two nodes exactly. Returns
    ``(lifetime_hour_float | None, is_right_censored)`` with the same
    right-censoring convention as :func:`inverse_cdf`. Sensitivity only
    (float); never enters the main path.
    """
    f120 = _as_fraction(f120, "f120")
    f240 = _as_fraction(f240, "f240")
    _validate_cdf_nodes(f120, f240)
    u = _as_fraction(u, "u")
    _validate_u(u)
    h1, h2 = sensitivity_h1_h2(f120, f240)
    fu = float(u)
    f1 = float(f120)
    f2 = float(f240)
    if fu <= f1:
        return -math.log(1.0 - fu) / h1, False
    if fu <= f2:
        return 120.0 + math.log((1.0 - f1) / (1.0 - fu)) / h2, False
    return None, True


__all__ = [
    "MANDATORY_REPLACE_AGE_H",
    "MIN_PREVENTIVE_AGE_H",
    "FROZEN_F120",
    "FROZEN_F240",
    "CALIBRATION_DURATION_MINUTES_FROZEN",
    "CALIBRATION_COUNTS_AGE",
    "CALIBRATION_CROSS_SHIFT_ALLOWED",
    "FROZEN_CSV_ROWS",
    "ReplacementDecision",
    "NO_PM_BEFORE_MANDATORY",
    "IllegalCrossingOutcome",
    "FailureImpactOutcome",
    "piecewise_linear_f",
    "inverse_cdf",
    "sample_lifetime",
    "sample_lifetime_frozen",
    "frozen_f120",
    "frozen_f240",
    "calibration_duration_minutes",
    "calibration_duration_hours",
    "validate_parameters_csv",
    "replacement_decision",
    "mandatory_240_interrupt_fallback",
    "failure_impact",
    "sensitivity_h1_h2",
    "sensitivity_exponential_sample",
    "sensitivity_constant_hazard_inverse_cdf",
]
