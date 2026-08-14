"""G3-SPEC-V1.0 S3: keyed random DES with equipment lifetime/replacement and
the fixed H1 FCFS baseline (Python standard library only, Python 3.12).

This module implements the frozen G3-SPEC-V1.0 contract on top of the
accepted G2-03 deterministic DES semantics (``des.deterministic_des_v1`` is
read-only reference; this module is an independent implementation that reuses
the G2 explicit-state vocabulary from ``des.state_models_v1`` and the frozen
G3 key/lifetime seams from ``g3.key_schema_v1`` (S1) and
``g3.lifetime_regeneration_v1`` (S2); no logic is copied from them).

Frozen contract sources (authoritative, in order):
  * G3-SPEC-V1.0 section 2 ``frozen_upstream_semantics`` (G2 accepted
    semantics, unchanged) and section 6 ``h1_baseline`` (fixed global FCFS);
  * G3-SPEC-V1.0 section 3 ``random_key_architecture`` (U_X/U_D/U_Y/U_L
    consumption legality, six disjoint namespaces, no-observation-consumed-by);
  * G3-SPEC-V1.0 section 5 ``regeneration_semantics`` (a+d boundaries,
    random-failure interruption, replacement/calibration, same-instant
    completion-first, illegal-crossing backstop);
  * G3-SPEC-V1.0 section 7 ``c26_preventive_replacement`` (triggered A-H);
  * G3-SPEC-V1.0 section 13 ``c18_liveness``;
  * G3-SPEC-V1.0 section 15 ``c24_exit_instrumentation`` (H2 admission
    instruments; H2 itself is NOT implemented);
  * V3.1 section 10 (same-timestamp event order) and section 7 (equipment
    failure / 240 h / regeneration);
  * problem contract section 1.1/1.2 and parameters.csv (P006-P009 durations,
    P014/P015 transport, P026-P029 defect probabilities, P037-P042 calendar,
    P049/P059 turnover profiles).

The observation kernel (P050-P057, ``待求`` in parameters.csv) is a frozen
*input* to the engine: ``observation_kernel`` maps each process A/B/C/E to
``{alpha, beta}`` with alpha = P(ABNORMAL | true normal) and
beta = P(NORMAL | true problem). The engine only *applies* the kernel to the
keyed U_Y observation; it never calibrates alpha/beta (that is the frozen
G2/Q1 calibration task). A pure helper implementing the frozen literal
main-semantics closed form ``(1-q)*alpha = q*beta = e/2`` is provided for
tests/pilots; the engine itself accepts any valid kernel.

Canonical time is an exact ``fractions.Fraction`` in hours; binary float is
forbidden on every canonical path (validated and statically audited by
tests). The event log is append-only and deterministic; the same
seed+config+code yields a byte/canonical identical event log (explicit run
metadata lives outside the log by construction).

Stream consumption legality (frozen section 3, caller-enforced here):
  * U_X(device, subsystem in {A,B,C}) -- consumed exactly once per device
    entry ("真实状态在装置进入时生成一次", no repair);
  * U_D(device) -- consumed exactly once, only at the legal D materialization
    (A/B/C all PASS while the device is still pending; E retests never redraw);
  * U_Y(device, process, effective_attempt_no) -- consumed only by a valid
    completion; failure interruption / terminal cancellation / shift deferral
    / never-started tasks consume nothing (the retry of the same effective
    attempt reuses the same keyed U_Y);
  * U_L(resource, generation) -- consumed exactly once per (resource,
    generation), at device initialization (generation 1) and at each
    replacement (new generation).

H1 dispatch (frozen section 6): fixed global FCFS key
(release_time, device_id, process_order, effective_attempt_no); after every
event closure the engine starts all mutually non-conflicting legal FCFS
heads completable within the current shift. No SPT/LPT/ATC/metaheuristic;
preventive replacement (C26) is the only added policy dimension.

C24 instruments (frozen section 15, H2 NOT implemented). The spec freezes
only the field names; the numeric values are to be frozen after real H1 logs
exist. This module defines the following operationalizations (documented,
deterministic, and reported to the coordinator):

  * decision-point count / density: closures at which a resource is IDLE with
    an available device and a non-empty queue while a shift is active
    (trigger A); density = count / T (per calendar hour);
  * legal action count: decision points at which a legal action was executed
    (serve head, mandatory replace-first, preventive replace);
  * waiting-opportunity count: decision points at which the frozen head was
    not startable (E prereq / shift fit / device state), i.e. the head had to
    wait; invariant decision-point == legal-action + waiting-opportunity;
  * preventive-replacement opportunity count: decision points at which the
    frozen physical constraint age >= 120 h holds (independent of tau_pm);
  * estimated rollout branching burden = decision-point count +
    preventive-replacement opportunity count (serve action at every decision
    point plus one preventive-replacement branch wherever age >= 120 h).
"""

from __future__ import annotations

import csv
import enum
import heapq
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

from . import key_schema_v1 as ks
from . import lifetime_regeneration_v1 as lr

# ``des`` is a sibling top-level package (``04_代码/main_model`` is on
# sys.path in every runner/test; ``main_model`` itself has no __init__.py).
from des import state_models_v1 as sm  # noqa: E402

RESOURCES: tuple[str, ...] = sm.RESOURCES
PROCESS_ORDER: dict[str, int] = sm.PROCESS_ORDER

# ---------------------------------------------------------------------------
# Frozen constants (parameters.csv; exact rational values)
# ---------------------------------------------------------------------------

# P006-P009: frozen test durations (hours).
DEFAULT_DURATIONS_H: dict[str, Fraction] = {
    "A": Fraction(5, 2),  # P006 t_A = 2.5 h
    "B": Fraction(2, 1),  # P007 t_B = 2 h
    "C": Fraction(5, 2),  # P008 t_C = 2.5 h
    "E": Fraction(3, 1),  # P009 t_E = 3 h
}

# P014/P015: transport-out / transport-in (hours).
DEFAULT_TRANSPORT_OUT_H: Fraction = Fraction(1, 2)  # P014 t_out = 0.5 h
DEFAULT_TRANSPORT_IN_H: Fraction = Fraction(1, 2)   # P015 t_in = 0.5 h

# P026-P029: frozen true-defect probabilities (independent main model).
DEFECT_PROB_A: Fraction = Fraction(25, 1000)  # P026 q_A = 0.025
DEFECT_PROB_B: Fraction = Fraction(3, 100)    # P027 q_B = 0.03
DEFECT_PROB_C: Fraction = Fraction(2, 100)    # P028 q_C = 0.02
DEFECT_PROB_D: Fraction = Fraction(1, 1000)   # P029 q_D = 0.001

DEFECT_PROBS_ABC: dict[str, Fraction] = {
    "A": DEFECT_PROB_A,
    "B": DEFECT_PROB_B,
    "C": DEFECT_PROB_C,
}
DEFECT_PROB_D_VALUE: Fraction = DEFECT_PROB_D

# Frozen parameters.csv rows owned by this module, parameter_id -> exact value.
FROZEN_CSV_ROWS: dict[str, Fraction] = {
    "P006": DEFAULT_DURATIONS_H["A"],
    "P007": DEFAULT_DURATIONS_H["B"],
    "P008": DEFAULT_DURATIONS_H["C"],
    "P009": DEFAULT_DURATIONS_H["E"],
    "P014": DEFAULT_TRANSPORT_OUT_H,
    "P015": DEFAULT_TRANSPORT_IN_H,
    "P026": DEFECT_PROB_A,
    "P027": DEFECT_PROB_B,
    "P028": DEFECT_PROB_C,
    "P029": DEFECT_PROB_D,
}

# New (S3) event types. Shared G2 event types reuse ``sm.EventType`` values.
EVENT_TRUE_STATE_GENERATED = "TRUE_STATE_GENERATED"
EVENT_EQUIPMENT_FAILURE = "EQUIPMENT_FAILURE"
EVENT_EQUIPMENT_REPLACEMENT_START = "EQUIPMENT_REPLACEMENT_START"
EVENT_EQUIPMENT_CALIBRATION_COMPLETE = "EQUIPMENT_CALIBRATION_COMPLETE"
EVENT_EQUIPMENT_REPLACEMENT_DEFERRED = "EQUIPMENT_REPLACEMENT_DEFERRED"

CANCEL_REASON_EQUIPMENT_FAILURE = "EQUIPMENT_FAILURE"
CANCEL_REASON_ILLEGAL_240_INTERRUPT = "ILLEGAL_240_INTERRUPT"

# C26 replacement kinds and triggers (documented; frozen kind vocabulary from
# G3-SPEC-V1.0 sections 5/7).
REPLACEMENT_KIND_FAILURE = "failure"
REPLACEMENT_KIND_MANDATORY_240 = "mandatory_240"
REPLACEMENT_KIND_PREVENTIVE = "preventive"

REPLACEMENT_TRIGGER_MID_FRAGMENT_FAILURE = "mid_fragment_failure"
REPLACEMENT_TRIGGER_FAILURE_AT_END = "failure_at_end"
REPLACEMENT_TRIGGER_CANCEL_REACHED_LIMIT = "cancel_reached_limit"
REPLACEMENT_TRIGGER_POST_COMPLETION_240 = "post_completion_240"
REPLACEMENT_TRIGGER_A_PLUS_D_GT_240 = "a_plus_d_gt_240"
REPLACEMENT_TRIGGER_ILLEGAL_CROSSING_BACKSTOP = "illegal_crossing_backstop"
REPLACEMENT_TRIGGER_PREVENTIVE = "preventive"

# Frozen preventive-replacement physical constraint (P016): only when age >= 120.
MIN_PREVENTIVE_AGE_H: Fraction = lr.MIN_PREVENTIVE_AGE_H
# Mandatory replacement age (P017): 240 h.
MANDATORY_REPLACE_AGE_H: Fraction = lr.MANDATORY_REPLACE_AGE_H

__all__ = [
    "RESOURCES",
    "PROCESS_ORDER",
    "DEFAULT_DURATIONS_H",
    "DEFAULT_TRANSPORT_OUT_H",
    "DEFAULT_TRANSPORT_IN_H",
    "DEFECT_PROB_A",
    "DEFECT_PROB_B",
    "DEFECT_PROB_C",
    "DEFECT_PROB_D",
    "DEFECT_PROBS_ABC",
    "DEFECT_PROB_D_VALUE",
    "FROZEN_CSV_ROWS",
    "EVENT_TRUE_STATE_GENERATED",
    "EVENT_EQUIPMENT_FAILURE",
    "EVENT_EQUIPMENT_REPLACEMENT_START",
    "EVENT_EQUIPMENT_CALIBRATION_COMPLETE",
    "EVENT_EQUIPMENT_REPLACEMENT_DEFERRED",
    "CANCEL_REASON_EQUIPMENT_FAILURE",
    "CANCEL_REASON_ILLEGAL_240_INTERRUPT",
    "REPLACEMENT_KIND_FAILURE",
    "REPLACEMENT_KIND_MANDATORY_240",
    "REPLACEMENT_KIND_PREVENTIVE",
    "REPLACEMENT_TRIGGER_MID_FRAGMENT_FAILURE",
    "REPLACEMENT_TRIGGER_FAILURE_AT_END",
    "REPLACEMENT_TRIGGER_CANCEL_REACHED_LIMIT",
    "REPLACEMENT_TRIGGER_POST_COMPLETION_240",
    "REPLACEMENT_TRIGGER_A_PLUS_D_GT_240",
    "REPLACEMENT_TRIGGER_ILLEGAL_CROSSING_BACKSTOP",
    "REPLACEMENT_TRIGGER_PREVENTIVE",
    "MIN_PREVENTIVE_AGE_H",
    "MANDATORY_REPLACE_AGE_H",
    "RandomDesError",
    "RandomDesConfigError",
    "RandomDesPreloadRuleError",
    "LivenessError",
    "ZeroTimeLoopError",
    "FragmentOutcomeKind",
    "FragmentOutcome",
    "EquipmentState",
    "RandomDesConfig",
    "RandomDesResult",
    "fragment_outcome",
    "observation_outcome",
    "frozen_single_test_alpha_beta",
    "validate_observation_kernel",
    "make_fcfs_key",
    "RandomDesEngine",
    "run_random_des",
    "validate_parameters_csv",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RandomDesError(Exception):
    """Base class for random-DES failures."""


class RandomDesConfigError(RandomDesError):
    """Invalid random-DES configuration."""


class RandomDesPreloadRuleError(RandomDesConfigError):
    """SEM-21 initial-state rule violation (batch_size==1 -> [1];
    batch_size>=2 -> [1,2])."""


class LivenessError(RandomDesError):
    """Unfinished work exists but the calendar is empty and there is no
    future shift boundary (CR-V3.1/C18 violation)."""


class ZeroTimeLoopError(RandomDesError):
    """An event would re-schedule at the same timestamp (no zero-time
    loops allowed)."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _as_fraction(value: Any, name: str) -> Fraction:
    """Coerce to an exact Fraction; binary float is rejected so it can never
    enter a canonical path."""
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise TypeError(
            f"{name} must be an int or Fraction (binary float is forbidden as "
            f"canonical), got {type(value).__name__}"
        )
    return value if isinstance(value, Fraction) else Fraction(value)


def _parse_rational_string(value: Any, name: str) -> Fraction:
    if not isinstance(value, str):
        raise RandomDesConfigError(f"config.{name} must be a rational string")
    try:
        fraction = sm.string_to_fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise RandomDesConfigError(
            f"config.{name} is not a valid rational: {value!r}"
        ) from exc
    return fraction


def _parse_positive(value: Any, name: str) -> Fraction:
    fraction = _parse_rational_string(value, name)
    if fraction <= 0:
        raise RandomDesConfigError(f"config.{name} must be positive")
    return fraction


def _parse_nonnegative(value: Any, name: str) -> Fraction:
    fraction = _parse_rational_string(value, name)
    if fraction < 0:
        raise RandomDesConfigError(f"config.{name} must be non-negative")
    return fraction


class FragmentOutcomeKind(str, enum.Enum):
    """Kind of a physical test fragment (one execution of one effective
    attempt). ``COMPLETE`` settles as a valid completion; ``FAILED`` is a
    random-equipment failure strictly before the task end; ``ILLEGAL_240`` is
    the mandatory-240 illegal-crossing backstop force-interrupt
    (G3-SPEC-V1.0 section 5 ``illegal_crossing_fallback``)."""

    COMPLETE = "complete"
    FAILED = "failed"
    ILLEGAL_240 = "illegal_240_interrupt"


@dataclass(frozen=True)
class FragmentOutcome:
    """Pure outcome of scheduling one fragment at start age ``a_start`` with
    duration ``d`` and the generation's sampled lifetime."""

    kind: FragmentOutcomeKind
    fragment_duration_h: Fraction
    failure_age_h: Optional[Fraction] = None  # equipment age at interruption


def fragment_outcome(
    a_start: Any, d: Any, lifetime_h: Any, is_right_censored: bool
) -> FragmentOutcome:
    """Pure fragment classification (G3-SPEC-V1.0 section 5; reuses the S2
    seams ``lr.mandatory_240_interrupt_fallback`` and ``lr.failure_impact``;
    no logic is re-implemented here).

    Priority (frozen): the illegal-crossing backstop (a_start + d > 240)
    force-interrupts at age 240 first; otherwise a random failure strictly
    before the end interrupts the fragment; a failure exactly at the end
    settles as a completion (same-instant completion first); otherwise the
    fragment completes.
    """
    a = _as_fraction(a_start, "a_start")
    d = _as_fraction(d, "d")
    crossing = lr.mandatory_240_interrupt_fallback(a, d)
    if crossing.triggered:
        return FragmentOutcome(
            FragmentOutcomeKind.ILLEGAL_240, crossing.fragment_duration_h
        )
    impact = lr.failure_impact(a, d, lifetime_h, is_right_censored)
    if impact.interrupted:
        return FragmentOutcome(
            FragmentOutcomeKind.FAILED,
            impact.fragment_duration_h,
            failure_age_h=a + impact.fragment_duration_h,
        )
    return FragmentOutcome(FragmentOutcomeKind.COMPLETE, d)


def observation_outcome(
    true_problem: bool, u_y: Fraction, alpha: Any, beta: Any
) -> str:
    """Apply the frozen observation kernel to a keyed observation U_Y.

    With U uniform on [0,1): P(ABNORMAL | normal) = alpha (U < alpha);
    P(NORMAL | problem) = beta (U >= 1 - beta), i.e. P(ABNORMAL | problem) =
    1 - beta (U < 1 - beta). Returns the ``sm.Outcome`` value string.
    """
    u = _as_fraction(u_y, "u_y")
    a = _as_fraction(alpha, "alpha")
    b = _as_fraction(beta, "beta")
    _validate_probability(a, "alpha")
    _validate_probability(b, "beta")
    if true_problem:
        return (
            sm.Outcome.ABNORMAL.value if u < Fraction(1) - b else sm.Outcome.PASS.value
        )
    return sm.Outcome.ABNORMAL.value if u < a else sm.Outcome.PASS.value


def _validate_probability(value: Fraction, name: str) -> None:
    if value < Fraction(0) or value > Fraction(1):
        raise ValueError(f"{name} must be in [0, 1], got {value!r}")


def frozen_single_test_alpha_beta(q: Any, e: Any) -> tuple[Fraction, Fraction]:
    """Frozen literal main-semantics observation kernel (parameters.csv P060
    ``single_test_unconditional_v1``; rho=0.5 FP/FN split P034/P035):
    ``(1-q)*alpha = q*beta = e/2``, solved exactly:

        alpha = e / (2*(1-q)),   beta = e / (2*q)

    Feasibility (frozen P060): ``e <= 2*min(q, 1-q)`` is required so both
    alpha and beta land in (0, 1]; an infeasible pair raises ``ValueError``
    (report, never clip). This is a pure helper implementing the frozen
    formula; the engine itself accepts any valid kernel as config input.
    """
    q = _as_fraction(q, "q")
    e = _as_fraction(e, "e")
    if not (Fraction(0) < q < Fraction(1)):
        raise ValueError(f"q must be in (0, 1), got {q!r}")
    if not (Fraction(0) < e <= Fraction(2) * min(q, Fraction(1) - q)):
        raise ValueError(
            "frozen single-test semantics requires 0 < e <= 2*min(q, 1-q) "
            f"(P060 feasibility), got q={q!r}, e={e!r}"
        )
    alpha = e / (Fraction(2) * (Fraction(1) - q))
    beta = e / (Fraction(2) * q)
    return alpha, beta


def validate_observation_kernel(kernel: dict[str, dict[str, Any]]) -> None:
    """Validate an observation kernel: every process A/B/C/E present with
    alpha, beta exact Fractions in [0, 1] (binary float rejected)."""
    if not isinstance(kernel, dict):
        raise RandomDesConfigError("observation_kernel must be an object")
    for proc in RESOURCES:
        entry = kernel.get(proc)
        if not isinstance(entry, dict):
            raise RandomDesConfigError(
                f"observation_kernel missing process {proc}"
            )
        if set(entry) != {"alpha", "beta"}:
            raise RandomDesConfigError(
                f"observation_kernel[{proc}] must have exactly alpha and beta"
            )
        alpha = _as_fraction(entry["alpha"], f"observation_kernel[{proc}].alpha")
        beta = _as_fraction(entry["beta"], f"observation_kernel[{proc}].beta")
        _validate_probability(alpha, f"observation_kernel[{proc}].alpha")
        _validate_probability(beta, f"observation_kernel[{proc}].beta")


def make_fcfs_key(
    release_time: Fraction, device_id: int, process: str, attempt_no: int
) -> tuple:
    """Frozen canonical FCFS key (G3-SPEC-V1.0 section 2 / G2-03):
    (release_time, device_id, process_order, effective_attempt_no)."""
    if not isinstance(release_time, Fraction):
        release_time = sm.string_to_fraction(str(release_time))
    return (release_time, device_id, PROCESS_ORDER[process], attempt_no)


# ---------------------------------------------------------------------------
# Equipment state
# ---------------------------------------------------------------------------


@dataclass
class EquipmentState:
    """One equipment device (A/B/C/E), generation/age/lifetime with the
    replacement/calibration lifecycle.

    Invariants (frozen section 5): age accumulates only actual test fragments
    (completed, failed, cancelled, illegal-240) and never calibration or idle;
    the device is ``available=False`` from the moment a replacement is pending
    until its calibration completes; generation increases by exactly one per
    replacement; each generation binds exactly one U_L.
    """

    resource_id: str
    age: Fraction = Fraction(0)
    generation: int = 1
    lifetime_h: Optional[Fraction] = None  # None when right-censored
    is_right_censored: bool = False
    available: bool = True  # False while replacement+calibration outstanding
    replacement_pending: bool = False
    pending_kind: Optional[str] = None  # failure | mandatory_240 | preventive
    pending_trigger: Optional[str] = None
    calibration_in_flight: bool = False
    calibration_start: Optional[Fraction] = None
    calibration_end: Optional[Fraction] = None
    deferral_emitted: bool = False  # EQUIPMENT_REPLACEMENT_DEFERRED once/episode
    replacement_count: int = 0
    preventive_count: int = 0
    failure_count: int = 0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RandomDesConfig:
    """Frozen random-DES configuration (G3-SPEC-V1.0; ``random_des_config_v1``).

    Fields: scenario/calendar (q2_single_shift | q3_two_shift |
    isolated_small_case), batch size, durations, transport, turnover profile,
    G2 initial state, plus the G3 layer: ``namespace`` (one of the six frozen
    namespaces), ``master_seed`` / ``replicate_id`` (canonical key fields),
    ``tau_pm`` (numeric in [120, 240) or ``lr.NO_PM_BEFORE_MANDATORY``) and
    ``observation_kernel`` ({process: {alpha, beta}}; P050-P057 are frozen
    *inputs*, never calibrated here).
    """

    schema_version: str
    scenario_id: str
    scenario: str
    batch_size: int
    shift_length_h: Fraction
    shifts_per_day: int
    durations: dict[str, Fraction]
    transport_out_h: Fraction
    transport_in_h: Fraction
    turnover_profile: str
    preloaded_devices: tuple[int, ...]
    namespace: str
    master_seed: int
    replicate_id: int
    tau_pm: Any  # Fraction | lr.NO_PM_BEFORE_MANDATORY sentinel
    observation_kernel: dict[str, dict[str, Fraction]]
    key_schema_version: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RandomDesConfig":
        if not isinstance(raw, dict):
            raise RandomDesConfigError("config must be a JSON object")
        if raw.get("schema_version") != "random_des_config_v1":
            raise RandomDesConfigError(
                "config.schema_version must be 'random_des_config_v1'"
            )
        if raw.get("key_schema_version") != ks.KEY_SCHEMA_VERSION:
            raise RandomDesConfigError(
                f"config.key_schema_version must be '{ks.KEY_SCHEMA_VERSION}'"
            )

        scenario = raw.get("scenario")
        if scenario not in sm.SCENARIOS:
            raise RandomDesConfigError(f"config.scenario must be one of {sm.SCENARIOS}")
        scenario_id = raw.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise RandomDesConfigError("config.scenario_id must be a non-empty string")

        batch_size = raw.get("batch_size")
        if not isinstance(batch_size, int) or batch_size < 1:
            raise RandomDesConfigError("config.batch_size must be a positive integer")

        shift_length_h = _parse_positive(raw.get("shift_length_h"), "shift_length_h")
        shifts_per_day = raw.get("shifts_per_day")
        if not isinstance(shifts_per_day, int) or shifts_per_day < 1:
            raise RandomDesConfigError("config.shifts_per_day must be a positive integer")

        durations_raw = raw.get("durations")
        if not isinstance(durations_raw, dict):
            raise RandomDesConfigError("config.durations must be an object")
        durations: dict[str, Fraction] = {}
        for proc in RESOURCES:
            if proc not in durations_raw:
                raise RandomDesConfigError(f"config.durations missing process {proc}")
            durations[proc] = _parse_positive(durations_raw[proc], f"durations.{proc}")

        transport_out = _parse_nonnegative(raw.get("transport_out_h"), "transport_out_h")
        transport_in = _parse_nonnegative(raw.get("transport_in_h"), "transport_in_h")
        turnover_profile = raw.get("turnover_profile")
        if turnover_profile not in sm.TURNOVER_PROFILES:
            raise RandomDesConfigError(
                f"config.turnover_profile must be one of {sm.TURNOVER_PROFILES}"
            )

        initial = raw.get("deterministic_initial_state")
        if not isinstance(initial, dict):
            raise RandomDesConfigError(
                "config.deterministic_initial_state must be an object"
            )
        if initial.get("all_calibrated") is not True:
            raise RandomDesConfigError("deterministic_initial_state.all_calibrated must be true")
        if initial.get("queues_empty") is not True:
            raise RandomDesConfigError("deterministic_initial_state.queues_empty must be true")
        preloaded = initial.get("preloaded_devices")
        if not isinstance(preloaded, list) or not preloaded:
            raise RandomDesConfigError(
                "deterministic_initial_state.preloaded_devices must be a non-empty list"
            )
        if any(not isinstance(p, int) or p < 1 for p in preloaded):
            raise RandomDesConfigError("preloaded_devices must contain positive integers")
        expected_preload = [1] if batch_size == 1 else [1, 2]
        if preloaded != expected_preload:
            raise RandomDesPreloadRuleError(
                f"SEM-21 initial-state rule: batch_size=={batch_size} requires "
                f"deterministic_initial_state.preloaded_devices == "
                f"{expected_preload!r}, got {preloaded!r}"
            )

        namespace = raw.get("namespace")
        if namespace not in ks.NAMESPACES:
            raise RandomDesConfigError(
                f"config.namespace must be one of the six frozen namespaces "
                f"{ks.NAMESPACES}, got {namespace!r} (H2 is reserved only)"
            )
        master_seed = raw.get("master_seed")
        replicate_id = raw.get("replicate_id")
        if isinstance(master_seed, bool) or not isinstance(master_seed, int) or master_seed < 0:
            raise RandomDesConfigError("config.master_seed must be a non-negative int")
        if isinstance(replicate_id, bool) or not isinstance(replicate_id, int) or replicate_id < 0:
            raise RandomDesConfigError("config.replicate_id must be a non-negative int")

        tau_raw = raw.get("tau_pm")
        if tau_raw == "NO_PM_BEFORE_MANDATORY":
            tau_pm: Any = lr.NO_PM_BEFORE_MANDATORY
        else:
            tau_pm = _parse_rational_string(tau_raw, "tau_pm")
            if not (lr.MIN_PREVENTIVE_AGE_H <= tau_pm < lr.MANDATORY_REPLACE_AGE_H):
                raise RandomDesConfigError(
                    "numeric tau_pm must be in [120, 240) hours; 240 is "
                    "mandatory semantics, never a preventive threshold; "
                    "NO_PM_BEFORE_MANDATORY is the no-prevention policy"
                )

        kernel_raw = raw.get("observation_kernel")
        if not isinstance(kernel_raw, dict):
            raise RandomDesConfigError("config.observation_kernel must be an object")
        kernel: dict[str, dict[str, Fraction]] = {}
        for proc in RESOURCES:
            entry = kernel_raw.get(proc)
            if not isinstance(entry, dict) or set(entry) != {"alpha", "beta"}:
                raise RandomDesConfigError(
                    f"config.observation_kernel[{proc}] must have alpha and beta"
                )
            kernel[proc] = {
                "alpha": _parse_rational_string(entry["alpha"], f"observation_kernel[{proc}].alpha"),
                "beta": _parse_rational_string(entry["beta"], f"observation_kernel[{proc}].beta"),
            }
        validate_observation_kernel(kernel)

        return cls(
            schema_version="random_des_config_v1",
            scenario_id=scenario_id,
            scenario=scenario,
            batch_size=batch_size,
            shift_length_h=shift_length_h,
            shifts_per_day=shifts_per_day,
            durations=durations,
            transport_out_h=transport_out,
            transport_in_h=transport_in,
            turnover_profile=turnover_profile,
            preloaded_devices=tuple(preloaded),
            namespace=namespace,
            master_seed=master_seed,
            replicate_id=replicate_id,
            tau_pm=tau_pm,
            observation_kernel=kernel,
            key_schema_version=ks.KEY_SCHEMA_VERSION,
        )

    def to_dict(self) -> dict[str, Any]:
        tau: Any
        if self.tau_pm is lr.NO_PM_BEFORE_MANDATORY:
            tau = "NO_PM_BEFORE_MANDATORY"
        else:
            tau = sm.fraction_to_string(self.tau_pm)
        return {
            "schema_version": "random_des_config_v1",
            "scenario_id": self.scenario_id,
            "scenario": self.scenario,
            "batch_size": self.batch_size,
            "shift_length_h": sm.fraction_to_string(self.shift_length_h),
            "shifts_per_day": self.shifts_per_day,
            "durations": {p: sm.fraction_to_string(self.durations[p]) for p in RESOURCES},
            "transport_out_h": sm.fraction_to_string(self.transport_out_h),
            "transport_in_h": sm.fraction_to_string(self.transport_in_h),
            "turnover_profile": self.turnover_profile,
            "deterministic_initial_state": {
                "preloaded_devices": list(self.preloaded_devices),
                "all_calibrated": True,
                "queues_empty": True,
            },
            "namespace": self.namespace,
            "master_seed": self.master_seed,
            "replicate_id": self.replicate_id,
            "tau_pm": tau,
            "observation_kernel": {
                p: {
                    "alpha": sm.fraction_to_string(self.observation_kernel[p]["alpha"]),
                    "beta": sm.fraction_to_string(self.observation_kernel[p]["beta"]),
                }
                for p in RESOURCES
            },
            "key_schema_version": self.key_schema_version,
        }


def _coerce_fraction(value: Any, name: str) -> Fraction:
    """Accept int/Fraction (exact) or a rational string; binary float is
    rejected so it can never enter a canonical path."""
    if isinstance(value, str):
        try:
            return sm.string_to_fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise RandomDesConfigError(f"{name} is not a valid rational: {value!r}") from exc
    return _as_fraction(value, name)


def default_config(
    namespace: str,
    master_seed: int,
    replicate_id: int,
    tau_pm: Any,
    observation_kernel: dict[str, dict[str, Any]],
    batch_size: int = 100,
    scenario: str = "q2_single_shift",
    shift_length_h: str = "12",
    shifts_per_day: int = 1,
    durations: Optional[dict[str, str]] = None,
    transport_out_h: str = "0.5",
    transport_in_h: str = "0.5",
    turnover_profile: str = "1h_literal",
    scenario_id: Optional[str] = None,
) -> RandomDesConfig:
    """Convenience builder with the frozen parameters.csv defaults (P006-P009
    durations, P014/P015 transport, Q2 calendar defaults P037-P039 for the
    q2_single_shift scenario). The observation kernel is REQUIRED (P050-P057
    are frozen inputs, never silently defaulted). ``tau_pm`` and kernel
    alpha/beta may be exact Fractions/ints or rational strings."""
    dur = {
        p: sm.fraction_to_string(DEFAULT_DURATIONS_H[p])
        for p in RESOURCES
    }
    if durations is not None:
        for p in RESOURCES:
            if p in durations:
                dur[p] = durations[p]
    raw: dict[str, Any] = {
        "schema_version": "random_des_config_v1",
        "scenario_id": scenario_id or f"s3_{namespace}_seed{master_seed}_rep{replicate_id}",
        "scenario": scenario,
        "batch_size": batch_size,
        "shift_length_h": shift_length_h,
        "shifts_per_day": shifts_per_day,
        "durations": dur,
        "transport_out_h": transport_out_h,
        "transport_in_h": transport_in_h,
        "turnover_profile": turnover_profile,
        "deterministic_initial_state": {
            "preloaded_devices": [1] if batch_size == 1 else [1, 2],
            "all_calibrated": True,
            "queues_empty": True,
        },
        "namespace": namespace,
        "master_seed": master_seed,
        "replicate_id": replicate_id,
        "tau_pm": (
            "NO_PM_BEFORE_MANDATORY"
            if tau_pm is lr.NO_PM_BEFORE_MANDATORY
            else sm.fraction_to_string(_coerce_fraction(tau_pm, "tau_pm"))
        ),
        "observation_kernel": {
            p: {
                "alpha": sm.fraction_to_string(
                    _coerce_fraction(observation_kernel[p]["alpha"], "alpha")
                ),
                "beta": sm.fraction_to_string(
                    _coerce_fraction(observation_kernel[p]["beta"], "beta")
                ),
            }
            for p in RESOURCES
        },
        "key_schema_version": ks.KEY_SCHEMA_VERSION,
    }
    return RandomDesConfig.from_dict(raw)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class RandomDesResult:
    """Run result: deterministic append-only event log (G2 event vocabulary
    plus S3 random events), metrics, per-device/equipment summary, and
    explicit run metadata (never part of the canonical log)."""

    config: RandomDesConfig
    event_log: list[dict[str, Any]]
    metrics: dict[str, Any]
    summary: dict[str, Any]
    run_metadata: dict[str, Any]

    def canonical_event_log(self) -> bytes:
        """Byte/canonical serialization of the event log (JSON, sorted keys,
        exact fraction strings, no floats). Reproducible for the same
        seed+config+code; run metadata is excluded by construction."""
        return (
            json_dumps_canonical(self.event_log).encode("utf-8")
        )


def _canonicalize_value(value: Any) -> Any:
    """Recursively convert Fractions (and containers of Fractions) to exact
    fraction strings; bool/int/str pass through; binary float is rejected."""
    if isinstance(value, Fraction):
        return sm.fraction_to_string(value)
    if isinstance(value, bool) or isinstance(value, (int, str)):
        return value
    if isinstance(value, dict):
        return {k: _canonicalize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize_value(v) for v in value]
    raise TypeError(
        f"cannot canonicalize log value of type {type(value).__name__}"
    )


def json_dumps_canonical(value: Any) -> str:
    """Canonical JSON (sort_keys, ensure_ascii=False, compact separators).
    All log values are str/int/bool/None already; no float is ever present."""
    import json

    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RandomDesEngine:
    """Keyed random parallel DES engine (G3-SPEC-V1.0 S3).

    Deterministic fixed-global-FCFS H1 dispatch; equipment lifetime /
    regeneration / preventive replacement per the frozen contract; exact
    Fraction time; append-only deterministic event log.
    """

    def __init__(self, config: RandomDesConfig) -> None:
        self.config = config
        self.now: Fraction = Fraction(0)
        self._seq: int = 0
        self.log: list[dict[str, Any]] = []
        self._calendar: list[tuple[Fraction, int, str, Any]] = []
        self._cal_seq: int = 0
        self._cancelled_attempts: set[str] = set()
        self.devices: dict[int, sm.DeviceState] = {}
        self.resources: dict[str, sm.ResourceState] = {}
        self.bays: dict[int, sm.BayState] = {}
        self.tasks: dict[str, sm.TaskState] = {}
        self.attempts: dict[str, sm.TestAttemptState] = {}
        self.queues: dict[str, list[sm.QueueEntry]] = {r: [] for r in RESOURCES}
        self.shift_state: sm.ShiftCalendarState = sm.ShiftCalendarState(
            scenario=config.scenario,
            shift_length_h=config.shift_length_h,
            shifts_per_day=config.shifts_per_day,
        )
        self.equipment: dict[str, EquipmentState] = {
            r: EquipmentState(resource_id=r) for r in RESOURCES
        }
        self.true_states: dict[int, dict[str, bool]] = {}
        self.d_states: dict[int, str] = {}
        self.ledger_elapsed: dict[str, Fraction] = {r: Fraction(0) for r in RESOURCES}
        self.consumed_u: dict[str, Fraction] = {}
        self._pending_retests: dict[tuple[int, str], Fraction] = {}
        self._pending_creations: list[int] = []
        self._created_count: int = 0
        self._fragment_counter: dict[str, int] = {}
        # C24 instruments (documented operationalizations in module docstring).
        self._c24_decision_points: int = 0
        self._c24_legal_actions: int = 0
        self._c24_waiting_opportunities: int = 0
        self._c24_pm_opportunities: int = 0
        self._init_state()

    # -- initialization ----------------------------------------------------

    def _init_state(self) -> None:
        for r in RESOURCES:
            self.resources[r] = sm.ResourceState(resource_id=r)
            self._sample_generation_1(r)
        for bay_id in (1, 2):
            self.bays[bay_id] = sm.BayState(
                bay_id=bay_id,
                status=sm.BayStatus.EMPTY,
                turnover_profile=self.config.turnover_profile,
            )
        for idx, device_id in enumerate(self.config.preloaded_devices):
            bay_id = idx + 1
            self._create_device(device_id, Fraction(0), bay_id)
            self._pending_creations.append(device_id)

    def _sample_generation_1(self, resource: str) -> None:
        """Draw the generation-1 U_L for ``resource`` (initial equipment is
        calibrated, age=0, generation=1, lifetime sampled; C15 reset per run)."""
        equip = self.equipment[resource]
        u = ks.u_l(
            self.config.namespace,
            self.config.replicate_id,
            resource,
            1,
            self.config.master_seed,
        )
        key = ks.canonical_key(
            self.config.namespace,
            self.config.replicate_id,
            resource,
            None,
            1,
            self.config.master_seed,
        )
        self.consumed_u[key] = u
        lifetime, censored = lr.inverse_cdf(
            u, lr.frozen_f120(resource), lr.frozen_f240(resource)
        )
        equip.lifetime_h = lifetime
        equip.is_right_censored = censored

    def _create_device(self, device_id: int, entry_time: Fraction, bay_id: int) -> None:
        device = sm.DeviceState(
            device_id=device_id,
            entry_time=entry_time,
            bay_id=bay_id,
            process_state={p: sm.ProcessState(process=p) for p in RESOURCES},
        )
        self.devices[device_id] = device
        self._created_count = max(self._created_count, device_id)
        bay = self.bays[bay_id]
        bay.current_device_id = device_id
        bay.status = sm.BayStatus.OCCUPIED_TESTING
        bay.transport_phase = "none"
        # U_X true states: drawn once at entry, never repaired (契约 1.2).
        true_state: dict[str, bool] = {}
        u_vals: dict[str, Fraction] = {}
        u_keys: dict[str, str] = {}
        for sub in ("A", "B", "C"):
            u = ks.u_x(
                self.config.namespace,
                self.config.replicate_id,
                device_id,
                sub,
                self.config.master_seed,
            )
            key = ks.canonical_key(
                self.config.namespace,
                self.config.replicate_id,
                device_id,
                sub,
                None,
                self.config.master_seed,
            )
            u_vals[sub] = u
            u_keys[sub] = key
            self.consumed_u[key] = u
            true_state[sub] = u < DEFECT_PROBS_ABC[sub]
        self.true_states[device_id] = true_state
        self._record(
            EVENT_TRUE_STATE_GENERATED,
            device_id=device_id,
            entry_time=entry_time,
            bay_id=bay_id,
            true_state={s: true_state[s] for s in ("A", "B", "C")},
            u_keys={s: u_keys[s] for s in ("A", "B", "C")},
            u={s: u_vals[s] for s in ("A", "B", "C")},
        )

    # -- log / calendar helpers --------------------------------------------

    def _record(self, event_type: str, **fields: Any) -> dict[str, Any]:
        self._seq += 1
        rec: dict[str, Any] = {
            "seq": self._seq,
            "event_time": sm.fraction_to_string(self.now),
            "event_type": event_type,
        }
        for name, value in fields.items():
            if value is None:
                continue
            rec[name] = _canonicalize_value(value)
        self.log.append(rec)
        return rec

    def _schedule(self, kind: str, time: Fraction, token: Any) -> None:
        self._cal_seq += 1
        heapq.heappush(self._calendar, (time, self._cal_seq, kind, token))

    def _calendar_min(self) -> Optional[Fraction]:
        if not self._calendar:
            return None
        return self._calendar[0][0]

    # -- shift calendar -----------------------------------------------------

    def _shift_start(self, index: int) -> Optional[Fraction]:
        scenario = self.config.scenario
        if scenario == "q3_two_shift":
            day = index // self.config.shifts_per_day
            slot = index % self.config.shifts_per_day
            return day * Fraction(24) + slot * self.config.shift_length_h
        if scenario == "q2_single_shift":
            return index * Fraction(24)
        if index == 0:  # isolated_small_case: one very long single shift
            return Fraction(0)
        return None

    def _shift_end(self, index: int) -> Optional[Fraction]:
        start = self._shift_start(index)
        if start is None:
            return None
        return start + self.config.shift_length_h

    def _squad(self, index: int) -> int:
        if self.config.scenario == "q3_two_shift":
            return 1 if index % 2 == 0 else 2
        return 1

    def _shift_at(self, t: Fraction) -> Optional[sm.ShiftInfo]:
        index = 0
        while True:
            start = self._shift_start(index)
            if start is None:
                return None
            end = self._shift_end(index)
            assert end is not None
            if start <= t < end:
                return sm.ShiftInfo(index, start, end, self._squad(index))
            if t < start:
                return None
            index += 1

    def _next_shift_boundary_after(self, t: Fraction) -> Optional[Fraction]:
        index = 0
        while True:
            start = self._shift_start(index)
            if start is None:
                return None
            end = self._shift_end(index)
            assert end is not None
            if t < start:
                return start
            if t < end:
                return end
            index += 1

    # -- FCFS / release -----------------------------------------------------

    def _task_id(self, device_id: int, process: str, attempt_no: int) -> str:
        return f"D{device_id:03d}_{process}_{attempt_no}"

    def _release_task(
        self, device_id: int, process: str, attempt_no: int, release_time: Fraction
    ) -> sm.TaskState:
        task_id = self._task_id(device_id, process, attempt_no)
        if task_id in self.tasks:
            raise RandomDesError(f"task {task_id} already exists")
        task = sm.TaskState(
            task_id=task_id,
            resource_id=process,
            device_id=device_id,
            process=process,
            effective_attempt_no=attempt_no,
            release_time=release_time,  # frozen at creation, never rewritten
        )
        self.tasks[task_id] = task
        key = make_fcfs_key(release_time, device_id, process, attempt_no)
        entry = sm.QueueEntry(queue_id=process, task_id=task_id, fcfs_key=key)
        self.queues[process].append(entry)
        self._record(
            sm.EventType.TASK_RELEASE.value,
            device_id=device_id,
            process=process,
            effective_attempt_no=attempt_no,
            resource_id=process,
            task_id=task_id,
            release_time=release_time,
        )
        return task

    # -- main loop ----------------------------------------------------------

    def run(self) -> RandomDesResult:
        self._closure(Fraction(0))
        while True:
            if self._is_terminal():
                self._record(sm.EventType.SIMULATION_END.value)
                break
            nxt = self._next_event_time()
            if nxt <= self.now:
                raise ZeroTimeLoopError(
                    f"no progress: next event time {nxt} not after current time {self.now}"
                )
            cal_min = self._calendar_min()
            boundary = self._next_shift_boundary_after(self.now)
            if cal_min is None and boundary is not None and nxt == boundary:
                # Pure liveness wake-up (CR-V3.1/C18): calendar empty but
                # unfinished work exists -> jump to the next shift boundary.
                self.now = nxt
                self._record(sm.EventType.WAKE_UP.value)
            self._closure(nxt)
        return RandomDesResult(
            config=self.config,
            event_log=list(self.log),
            metrics=self._metrics(),
            summary=self._summary(),
            run_metadata={},
        )

    def _next_event_time(self) -> Fraction:
        candidates: list[Fraction] = []
        cal_min = self._calendar_min()
        if cal_min is not None:
            candidates.append(cal_min)
        boundary = self._next_shift_boundary_after(self.now)
        if boundary is not None:
            candidates.append(boundary)
        if not candidates:
            raise LivenessError(
                "calendar empty and no future shift boundary while work is unfinished"
            )
        return min(candidates)

    def _is_terminal(self) -> bool:
        """C18 / 契约 1.1: the run stops at the instant the LAST device gets
        its terminal decision (末台终态停止计时; no transport-out after the
        last device). Stale calendar events (cancelled fragments of exited
        devices) are ignored: they carry no work."""
        if any(d.terminal_state == sm.TerminalState.PENDING for d in self.devices.values()):
            return False
        if any(b.turnover_pending for b in self.bays.values()):
            return False
        return True

    # -- same-timestamp closure (V3.1 section 10 order) ---------------------

    def _closure(self, t: Fraction) -> None:
        self.now = t
        completed, failed, illegal, calib_done, turnover_out_done, turnover_in_done = (
            self._settle(t)
        )
        self._observe(completed)
        self._classify(completed)
        exit_devices = self._apply_exits(completed)
        self._cancel_unfinished(exit_devices)
        self._materialize_d()
        self._shift_change()
        self._release_tasks()
        self._equipment_and_dispatch()
        self._start_turnovers()

    # -- A. settle completed activities -------------------------------------

    def _settle(self, t: Fraction):
        completed: list[sm.TestAttemptState] = []
        failed: list[tuple[sm.TestAttemptState, sm.TaskState]] = []
        illegal: list[tuple[sm.TestAttemptState, sm.TaskState]] = []
        calib_done: list[str] = []
        turnover_out_done: list[int] = []
        turnover_in_done: list[int] = []
        while self._calendar and self._calendar[0][0] == t:
            _time, _cseq, kind, token = heapq.heappop(self._calendar)
            if kind == "test_complete":
                if token in self._cancelled_attempts:
                    continue  # lazy deletion of cancelled fragments
                attempt = self.attempts[token]
                attempt.status = sm.AttemptStatus.COMPLETED
                attempt.end_time = t
                task = self.tasks[attempt.task_id]
                task.status = sm.TaskStatus.COMPLETED
                res = self.resources[task.resource_id]
                res.status = sm.ResourceStatus.IDLE
                res.current_activity = None
                elapsed = attempt.end_time - attempt.start_time
                assert elapsed is not None and elapsed > Fraction(0)
                self.ledger_elapsed[task.process] += elapsed
                self.equipment[task.resource_id].age += elapsed
                completed.append(attempt)
            elif kind == "test_failed":
                if token in self._cancelled_attempts:
                    continue
                attempt = self.attempts[token]
                attempt.status = sm.AttemptStatus.CANCELLED
                attempt.end_time = t
                task = self.tasks[attempt.task_id]
                task.status = sm.TaskStatus.READY  # requeued below, attempt unchanged
                res = self.resources[task.resource_id]
                res.status = sm.ResourceStatus.IDLE
                res.current_activity = None
                elapsed = t - attempt.start_time
                assert elapsed is not None and elapsed > Fraction(0)
                self.ledger_elapsed[task.process] += elapsed
                self.equipment[task.resource_id].age += elapsed
                failed.append((attempt, task))
            elif kind == "test_240_interrupt":
                if token in self._cancelled_attempts:
                    continue
                attempt = self.attempts[token]
                attempt.status = sm.AttemptStatus.CANCELLED
                attempt.end_time = t
                task = self.tasks[attempt.task_id]
                task.status = sm.TaskStatus.READY
                res = self.resources[task.resource_id]
                res.status = sm.ResourceStatus.IDLE
                res.current_activity = None
                elapsed = t - attempt.start_time
                assert elapsed is not None and elapsed > Fraction(0)
                self.ledger_elapsed[task.process] += elapsed
                self.equipment[task.resource_id].age += elapsed
                illegal.append((attempt, task))
            elif kind == "calibration_complete":
                resource = token
                equip = self.equipment[resource]
                equip.available = True
                equip.replacement_pending = False
                equip.pending_kind = None
                equip.pending_trigger = None
                equip.calibration_in_flight = False
                equip.calibration_start = None
                equip.calibration_end = None
                res = self.resources[resource]
                res.status = sm.ResourceStatus.IDLE
                res.current_activity = None
                calib_done.append(resource)
            elif kind == "turnover_out_complete":
                turnover_out_done.append(token)
            elif kind == "turnover_in_complete":
                turnover_in_done.append(token)

        # Settle completions first (same-instant completion priority), then
        # failures, then illegal-240 backstops; deterministic order.
        def _attempt_sort_key(attempt: sm.TestAttemptState):
            return (
                attempt.device_id,
                PROCESS_ORDER[attempt.process],
                attempt.effective_attempt_no,
            )

        completed.sort(key=_attempt_sort_key)
        for attempt in completed:
            task = self.tasks[attempt.task_id]
            self._record(
                sm.EventType.ACTIVITY_COMPLETE.value,
                device_id=attempt.device_id,
                process=attempt.process,
                effective_attempt_no=attempt.effective_attempt_no,
                resource_id=task.resource_id,
                bay_id=self.devices[attempt.device_id].bay_id,
                squad_id=attempt.result_squad_id,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                attempt_start_time=attempt.start_time,
                attempt_end_time=attempt.end_time,
                outcome=sm.Outcome.NONE.value,
                elapsed_hours=attempt.end_time - attempt.start_time,
                equipment_age_at_end=self.equipment[task.resource_id].age,
                equipment_generation=self.equipment[task.resource_id].generation,
            )

        failed.sort(key=lambda pair: _attempt_sort_key(pair[0]))
        for attempt, task in failed:
            resource = task.resource_id
            elapsed = attempt.end_time - attempt.start_time
            self._record(
                sm.EventType.TASK_CANCEL.value,
                device_id=attempt.device_id,
                process=attempt.process,
                effective_attempt_no=attempt.effective_attempt_no,
                resource_id=resource,
                bay_id=self.devices[attempt.device_id].bay_id,
                squad_id=attempt.result_squad_id,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                attempt_start_time=attempt.start_time,
                attempt_end_time=attempt.end_time,
                outcome=sm.Outcome.NONE.value,
                cancel_reason=CANCEL_REASON_EQUIPMENT_FAILURE,
                elapsed_hours=elapsed,
            )
            self._record(
                EVENT_EQUIPMENT_FAILURE,
                resource_id=resource,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                device_id=attempt.device_id,
                process=attempt.process,
                effective_attempt_no=attempt.effective_attempt_no,
                fragment_start=attempt.start_time,
                fragment_end=attempt.end_time,
                elapsed_hours=elapsed,
                equipment_age_at_failure=self.equipment[resource].age,
                equipment_generation=self.equipment[resource].generation,
            )
            self.equipment[resource].failure_count += 1
            self._requeue_task(task)
            self._set_replacement_pending(
                resource, REPLACEMENT_KIND_FAILURE, REPLACEMENT_TRIGGER_MID_FRAGMENT_FAILURE
            )

        illegal.sort(key=lambda pair: _attempt_sort_key(pair[0]))
        for attempt, task in illegal:
            resource = task.resource_id
            elapsed = attempt.end_time - attempt.start_time
            self._record(
                sm.EventType.TASK_CANCEL.value,
                device_id=attempt.device_id,
                process=attempt.process,
                effective_attempt_no=attempt.effective_attempt_no,
                resource_id=resource,
                bay_id=self.devices[attempt.device_id].bay_id,
                squad_id=attempt.result_squad_id,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                attempt_start_time=attempt.start_time,
                attempt_end_time=attempt.end_time,
                outcome=sm.Outcome.NONE.value,
                cancel_reason=CANCEL_REASON_ILLEGAL_240_INTERRUPT,
                elapsed_hours=elapsed,
            )
            self._requeue_task(task)
            self._set_replacement_pending(
                resource,
                REPLACEMENT_KIND_MANDATORY_240,
                REPLACEMENT_TRIGGER_ILLEGAL_CROSSING_BACKSTOP,
            )

        for resource in sorted(calib_done):
            equip = self.equipment[resource]
            self._record(
                EVENT_EQUIPMENT_CALIBRATION_COMPLETE,
                resource_id=resource,
                generation=equip.generation,
                calibration_start=equip.calibration_start,
                calibration_end=self.now,
            )
            equip.calibration_start = None
            equip.calibration_end = None

        # Turnover out completion -> in phase (or instantaneous for overlap).
        for bay_id in sorted(turnover_out_done):
            bay = self.bays[bay_id]
            self._record(
                sm.EventType.TURNOVER_OUT_COMPLETE.value,
                bay_id=bay_id,
                device_id=bay.current_device_id,
            )
            if self.config.turnover_profile == "0.5h_overlap":
                self._record(
                    sm.EventType.TURNOVER_IN_START.value,
                    bay_id=bay_id,
                    device_id=bay.current_device_id,
                )
                self._record(
                    sm.EventType.TURNOVER_IN_COMPLETE.value,
                    bay_id=bay_id,
                    device_id=bay.current_device_id,
                )
                self._finish_turnover_in(bay, t)
            else:
                bay.status = sm.BayStatus.OCCUPIED_TRANSPORT_IN
                bay.transport_phase = "in"
                self._record(
                    sm.EventType.TURNOVER_IN_START.value,
                    bay_id=bay_id,
                    device_id=bay.current_device_id,
                )
                self._schedule(
                    "turnover_in_complete", t + self.config.transport_in_h, bay_id
                )
        for bay_id in sorted(turnover_in_done):
            bay = self.bays[bay_id]
            self._record(
                sm.EventType.TURNOVER_IN_COMPLETE.value,
                bay_id=bay_id,
                device_id=bay.current_device_id,
            )
            self._finish_turnover_in(bay, t)

        # Post-fragment-end equipment check: after any fragment end
        # (completion, cancellation), if the equipment age reached its sampled
        # lifetime (uncensored) or the mandatory 240 h, the equipment has
        # failed at that instant (completion already settled first) and must
        # be replaced. The failed/illegal paths set the pending directly above.
        for attempt in completed:
            resource = self.tasks[attempt.task_id].resource_id
            self._post_fragment_end(resource)

        return completed, failed, illegal, calib_done, turnover_out_done, turnover_in_done

    def _post_fragment_end(self, resource: str) -> None:
        """Uniform rule after a fragment end (completion or cancellation):
        age == 240 -> mandatory replacement (completion-settled-first);
        uncensored lifetime L and age == L -> random failure at that instant
        (same-instant completion wins, then replacement)."""
        equip = self.equipment[resource]
        if equip.replacement_pending:
            return
        if equip.age >= MANDATORY_REPLACE_AGE_H:
            self._set_replacement_pending(
                resource,
                REPLACEMENT_KIND_MANDATORY_240,
                REPLACEMENT_TRIGGER_POST_COMPLETION_240,
            )
            return
        if not equip.is_right_censored and equip.lifetime_h is not None:
            if equip.age >= equip.lifetime_h:
                self._set_replacement_pending(
                    resource,
                    REPLACEMENT_KIND_FAILURE,
                    REPLACEMENT_TRIGGER_FAILURE_AT_END,
                )

    def _requeue_task(self, task: sm.TaskState) -> None:
        """Re-insert a failure-interrupted task at the FCFS head position:
        the frozen FCFS key is unchanged (release_time immutable, effective
        attempt unchanged), so its key is strictly smaller than every other
        queued task of the same resource."""
        key = make_fcfs_key(
            task.release_time, task.device_id, task.process, task.effective_attempt_no
        )
        entry = sm.QueueEntry(
            queue_id=task.resource_id, task_id=task.task_id, fcfs_key=key
        )
        self.queues[task.resource_id].insert(0, entry)

    def _set_replacement_pending(
        self, resource: str, kind: str, trigger: str
    ) -> None:
        equip = self.equipment[resource]
        equip.available = False
        equip.replacement_pending = True
        equip.pending_kind = kind
        equip.pending_trigger = trigger
        equip.deferral_emitted = False

    # -- B. materialize observations ----------------------------------------

    def _observe(self, completed: list[sm.TestAttemptState]) -> None:
        for attempt in completed:
            task = self.tasks[attempt.task_id]
            device_id = attempt.device_id
            process = attempt.process
            attempt_no = attempt.effective_attempt_no
            true_problem = self._true_problem_for(device_id, process)
            u = ks.u_y(
                self.config.namespace,
                self.config.replicate_id,
                device_id,
                process,
                attempt_no,
                self.config.master_seed,
            )
            key = ks.canonical_key(
                self.config.namespace,
                self.config.replicate_id,
                device_id,
                process,
                attempt_no,
                self.config.master_seed,
            )
            self.consumed_u[key] = u
            kernel = self.config.observation_kernel[process]
            outcome = observation_outcome(true_problem, u, kernel["alpha"], kernel["beta"])
            attempt.outcome = outcome
            task.outcome = outcome
            self._record(
                sm.EventType.OBSERVATION_MATERIALIZED.value,
                device_id=device_id,
                process=process,
                effective_attempt_no=attempt_no,
                resource_id=task.resource_id,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                outcome=outcome,
                true_state=true_problem,
                u_key=key,
                u=u,
            )

    def _true_problem_for(self, device_id: int, process: str) -> bool:
        """True problem state of the device for the tested process: A/B/C use
        the entry-generated U_X state; E uses 'any generated true problem'
        over A/B/C plus D (D materialized exactly once at E-eligibility)."""
        if process in ("A", "B", "C"):
            return self.true_states[device_id][process]
        # E
        if any(self.true_states[device_id][p] for p in ("A", "B", "C")):
            return True
        d_state = self.d_states.get(device_id)
        return d_state == sm.DState.PROBLEM.value

    # -- C. classify outcomes -----------------------------------------------

    def _classify(self, completed: list[sm.TestAttemptState]) -> None:
        for attempt in completed:
            device = self.devices[attempt.device_id]
            ps = device.process_state[attempt.process]
            ps.outcome_history.append(attempt.outcome)
            if attempt.outcome == sm.Outcome.PASS.value:
                ps.process_status = sm.ProcessStatus.PASSED
            else:  # ABNORMAL
                if attempt.effective_attempt_no == 1:
                    ps.process_status = sm.ProcessStatus.AWAITING_RETEST
                    ps.first_failure_time = self.now
                    self._pending_retests[(attempt.device_id, attempt.process)] = self.now
                else:
                    # second effective abnormal -> exit (recorded in D)
                    pass

    # -- D. apply device exit / terminal ------------------------------------

    def _apply_exits(self, completed: list[sm.TestAttemptState]) -> list[int]:
        exit_devices: list[tuple[int, str]] = []
        passed_devices: list[int] = []
        for attempt in completed:
            if attempt.outcome == sm.Outcome.ABNORMAL.value and attempt.effective_attempt_no == 2:
                exit_devices.append((attempt.device_id, attempt.process))
            if attempt.outcome == sm.Outcome.PASS.value and attempt.process == "E":
                passed_devices.append(attempt.device_id)
        exit_device_ids = sorted({device_id for device_id, _proc in exit_devices})
        for device_id in exit_device_ids:
            device = self.devices[device_id]
            device.terminal_state = sm.TerminalState.EXITED
            device.exit_reason = sm.TERMINAL_REASON_SECOND_ABNORMAL
            self._record(
                sm.EventType.DEVICE_EXIT.value,
                device_id=device_id,
                process=",".join(
                    sorted(proc for dev_id, proc in exit_devices if dev_id == device_id)
                ),
                effective_attempt_no=2,
            )
            self._record(
                sm.EventType.DEVICE_TERMINAL.value,
                device_id=device_id,
                terminal_state=sm.TerminalState.EXITED.value,
                terminal_reason=sm.TERMINAL_REASON_SECOND_ABNORMAL,
            )
        for device_id in sorted(set(passed_devices) - set(exit_device_ids)):
            device = self.devices[device_id]
            device.terminal_state = sm.TerminalState.PASSED
            self._record(
                sm.EventType.DEVICE_TERMINAL.value,
                device_id=device_id,
                terminal_state=sm.TerminalState.PASSED.value,
                terminal_reason=None,
            )
        return exit_device_ids

    # -- E. cancel unfinished -----------------------------------------------

    def _cancel_unfinished(self, exit_device_ids: list[int]) -> None:
        for device_id in exit_device_ids:
            for task in sorted(
                (task for task in self.tasks.values() if task.device_id == device_id),
                key=lambda task: (
                    PROCESS_ORDER[task.process],
                    task.effective_attempt_no,
                    task.task_id,
                ),
            ):
                if task.status == sm.TaskStatus.COMPLETED:
                    continue
                if task.status == sm.TaskStatus.RUNNING:
                    attempt = self._running_attempt_of(task)
                    if attempt is None:  # pragma: no cover - defensive
                        continue
                    attempt.status = sm.AttemptStatus.CANCELLED
                    attempt.end_time = self.now
                    self._cancelled_attempts.add(attempt.attempt_id)
                    res = self.resources[task.resource_id]
                    res.status = sm.ResourceStatus.IDLE
                    res.current_activity = None
                    elapsed = self.now - attempt.start_time
                    assert elapsed is not None and elapsed > Fraction(0)
                    self.ledger_elapsed[task.process] += elapsed
                    self.equipment[task.resource_id].age += elapsed
                    task.status = sm.TaskStatus.CANCELLED
                    self._record(
                        sm.EventType.TASK_CANCEL.value,
                        device_id=device_id,
                        process=task.process,
                        effective_attempt_no=task.effective_attempt_no,
                        resource_id=task.resource_id,
                        bay_id=self.devices[device_id].bay_id,
                        squad_id=attempt.result_squad_id,
                        task_id=task.task_id,
                        attempt_id=attempt.attempt_id,
                        attempt_start_time=attempt.start_time,
                        attempt_end_time=self.now,
                        outcome=sm.Outcome.NONE.value,
                        cancel_reason=sm.CancelReason.DEVICE_EXIT.value,
                        elapsed_hours=elapsed,
                    )
                    self._post_fragment_end(task.resource_id)
                else:  # READY (never started): no runtime fragment
                    self._remove_queue_entry(task)
                    task.status = sm.TaskStatus.CANCELLED
                    self._record(
                        sm.EventType.TASK_CANCEL.value,
                        device_id=device_id,
                        process=task.process,
                        effective_attempt_no=task.effective_attempt_no,
                        resource_id=task.resource_id,
                        bay_id=self.devices[device_id].bay_id,
                        task_id=task.task_id,
                        outcome=sm.Outcome.NONE.value,
                        cancel_reason=sm.CancelReason.DEVICE_EXIT.value,
                        elapsed_hours=Fraction(0),
                    )

    # -- E2. materialize D for newly E-eligible devices ---------------------

    def _materialize_d(self) -> None:
        for device_id in sorted(self.devices):
            device = self.devices[device_id]
            if device.terminal_state != sm.TerminalState.PENDING:
                continue
            if device.d_state != sm.DState.NOT_CREATED:
                continue  # already materialized (E retest / later closures)
            if not all(
                device.process_state[p].process_status == sm.ProcessStatus.PASSED
                for p in ("A", "B", "C")
            ):
                continue
            e_task_id = self._task_id(device_id, "E", 1)
            if e_task_id in self.tasks:
                continue
            # Consume U_D exactly once at the legal materialization.
            u = ks.u_d(
                self.config.namespace,
                self.config.replicate_id,
                device_id,
                self.config.master_seed,
            )
            key = ks.canonical_key(
                self.config.namespace,
                self.config.replicate_id,
                device_id,
                None,
                None,
                self.config.master_seed,
            )
            self.consumed_u[key] = u
            d_state = (
                sm.DState.PROBLEM if u < DEFECT_PROB_D_VALUE else sm.DState.NORMAL
            )
            device.d_state = d_state
            self.d_states[device_id] = d_state.value
            squad = None
            if self.shift_state.active_shift is not None:
                squad = self.shift_state.active_shift.on_duty_squad
            self._record(
                sm.EventType.D_CREATED.value,
                device_id=device_id,
                d_state=d_state.value,
                bay_id=device.bay_id,
                squad_id=squad,
                u_key=key,
                u=u,
            )

    # -- SHIFT_CHANGE -------------------------------------------------------

    def _shift_change(self) -> None:
        new_shift = self._shift_at(self.now)
        if new_shift != self.shift_state.active_shift:
            self.shift_state.active_shift = new_shift
            if new_shift is not None:
                self.shift_state.next_shift_wake_up_time = (
                    self._next_shift_boundary_after(self.now)
                )
                self._record(
                    sm.EventType.SHIFT_CHANGE.value,
                    shift_index=new_shift.shift_index,
                    shift_start=new_shift.shift_start,
                    shift_end=new_shift.shift_end,
                    on_duty_squad=new_shift.on_duty_squad,
                    squad_id=new_shift.on_duty_squad,
                )

    # -- F. release tasks ---------------------------------------------------

    def _release_tasks(self) -> None:
        for device_id in sorted(self._pending_creations):
            device = self.devices[device_id]
            for proc in ("A", "B", "C"):
                device.process_state[proc].process_status = sm.ProcessStatus.IN_PROGRESS
                self._release_task(device_id, proc, 1, device.entry_time)
        self._pending_creations.clear()

        for (device_id, process), release_time in sorted(self._pending_retests.items()):
            device = self.devices[device_id]
            if device.terminal_state != sm.TerminalState.PENDING:
                continue  # device exited in this closure; retest is moot
            self._release_task(device_id, process, 2, release_time)
        self._pending_retests.clear()

        for device_id in sorted(self.devices):
            device = self.devices[device_id]
            if device.terminal_state != sm.TerminalState.PENDING:
                continue
            if device.process_state["E"].process_status == sm.ProcessStatus.PASSED:
                continue
            e_task_id = self._task_id(device_id, "E", 1)
            if e_task_id in self.tasks:
                continue
            if all(
                device.process_state[p].process_status == sm.ProcessStatus.PASSED
                for p in ("A", "B", "C")
            ):
                device.process_state["E"].process_status = sm.ProcessStatus.IN_PROGRESS
                self._release_task(device_id, "E", 1, self.now)

        for bay_id in sorted(self.bays):
            bay = self.bays[bay_id]
            if bay.turnover_pending or bay.current_device_id is None:
                continue
            if bay.status != sm.BayStatus.OCCUPIED_TESTING:
                continue
            device = self.devices[bay.current_device_id]
            if device.terminal_state == sm.TerminalState.PENDING:
                continue
            if self._next_device_to_create() > self.config.batch_size:
                bay.status = sm.BayStatus.TERMINAL_OCCUPIED_UNTIL_STOP
                continue
            bay.turnover_pending = True

    # -- G + H. equipment decisions + fixed-FCFS dispatch --------------------

    def _equipment_and_dispatch(self) -> None:
        starts: list[tuple[tuple, dict[str, Any], sm.TestAttemptState]] = []
        for resource_id in RESOURCES:
            resource = self.resources[resource_id]
            equip = self.equipment[resource_id]

            # 1) Pending replacement + calibration not yet in flight: start it
            # now if the no-cross-shift rule permits, else defer to the next
            # legal shift (wake-up) without consuming anything.
            if equip.replacement_pending and not equip.calibration_in_flight:
                self._begin_replacement(resource_id)

            # 2) Legal idle decision point (C26 trigger A..H).
            if resource.status != sm.ResourceStatus.IDLE:
                continue
            if not equip.available:
                continue
            queue = self.queues[resource_id]
            if not queue:
                continue
            head = queue[0]
            if head.status != sm.QueueEntryStatus.WAITING:
                continue
            # Decision point (only during an active shift: off-shift all work
            # stops, so no action is possible in a gap -- P039).
            if self.shift_state.active_shift is None:
                continue
            self._c24_decision_points += 1
            if not self._is_legal(head):
                self._c24_waiting_opportunities += 1
                continue
            if equip.age >= MIN_PREVENTIVE_AGE_H:
                self._c24_pm_opportunities += 1
            d = self.config.durations[resource_id]
            a = equip.age
            decision = lr.replacement_decision(
                a, d, self.config.tau_pm, is_idle_decision_point=True
            )
            if decision == lr.ReplacementDecision.MANDATORY_REPLACE_FIRST:
                # D: a+d > 240 -> forced replacement before serving the head
                # (never a preventive choice).
                self._c24_legal_actions += 1
                self._set_replacement_pending(
                    resource_id,
                    REPLACEMENT_KIND_MANDATORY_240,
                    REPLACEMENT_TRIGGER_A_PLUS_D_GT_240,
                )
                self._begin_replacement(resource_id)
            elif decision == lr.ReplacementDecision.PREVENTIVE_REPLACE:
                # F: a >= tau_pm (numeric policy) -> preventive replace first.
                self._c24_legal_actions += 1
                self._set_replacement_pending(
                    resource_id,
                    REPLACEMENT_KIND_PREVENTIVE,
                    REPLACEMENT_TRIGGER_PREVENTIVE,
                )
                self._begin_replacement(resource_id)
            else:
                # E (EXACT_240_COMPLETE_FIRST: may complete; completion
                # settles first, then mandatory replacement) or SERVE_HEAD
                # (including G under NO_PM_BEFORE_MANDATORY).
                self._c24_legal_actions += 1
                attempt = self._start_task(head)
                starts.append(
                    (head.fcfs_key, self._start_payload(attempt), attempt)
                )

        # Emit ACTIVITY_START in frozen FCFS-key order (G2 observable pattern).
        starts.sort(key=lambda item: item[0])
        for _key, payload, _attempt in starts:
            self._record(sm.EventType.ACTIVITY_START.value, **payload)

    def _begin_replacement(self, resource_id: str) -> None:
        """Start the replacement+calibration service for a pending equipment
        (G3-SPEC-V1.0 section 5 ``replacement``/``calibration`` and section 7
        H): replacement is instantaneous (age=0, generation+1, new U_L), the
        calibration duration (30/20/20/40 min) is the downtime and must not
        cross a shift boundary; if it cannot complete within the current
        shift, nothing is started and the next legal shift wakes the run."""
        equip = self.equipment[resource_id]
        kind = equip.pending_kind
        trigger = equip.pending_trigger
        cal = lr.calibration_duration_hours(resource_id)
        shift = self.shift_state.active_shift
        if shift is None or self.now + cal > shift.shift_end:
            if not equip.deferral_emitted:
                next_wake = self._next_shift_boundary_after(self.now)
                self._record(
                    EVENT_EQUIPMENT_REPLACEMENT_DEFERRED,
                    resource_id=resource_id,
                    kind=kind,
                    trigger=trigger,
                    reason="no_cross_shift",
                    next_wake=next_wake,
                )
                equip.deferral_emitted = True
            return  # stays pending; the run loop wakes at the next boundary
        equip.deferral_emitted = False
        old_gen = equip.generation
        new_gen = old_gen + 1
        age_before = equip.age
        equip.age = Fraction(0)
        equip.generation = new_gen
        # New generation binds a new U_L (exactly one per (resource,generation)).
        u = ks.u_l(
            self.config.namespace,
            self.config.replicate_id,
            resource_id,
            new_gen,
            self.config.master_seed,
        )
        key = ks.canonical_key(
            self.config.namespace,
            self.config.replicate_id,
            resource_id,
            None,
            new_gen,
            self.config.master_seed,
        )
        self.consumed_u[key] = u
        lifetime, censored = lr.inverse_cdf(
            u, lr.frozen_f120(resource_id), lr.frozen_f240(resource_id)
        )
        equip.lifetime_h = lifetime
        equip.is_right_censored = censored
        equip.calibration_in_flight = True
        equip.calibration_start = self.now
        equip.calibration_end = self.now + cal
        equip.replacement_count += 1
        if kind == REPLACEMENT_KIND_PREVENTIVE:
            equip.preventive_count += 1
        resource = self.resources[resource_id]
        resource.status = sm.ResourceStatus.BUSY
        resource.current_activity = {
            "kind": "calibration",
            "resource_id": resource_id,
            "start_time": self.now,
            "end_time": self.now + cal,
        }
        self._schedule("calibration_complete", self.now + cal, resource_id)
        self._record(
            EVENT_EQUIPMENT_REPLACEMENT_START,
            resource_id=resource_id,
            kind=kind,
            trigger=trigger,
            old_generation=old_gen,
            new_generation=new_gen,
            age_before=age_before,
            calibration_duration_hours=cal,
            calibration_start=self.now,
            calibration_end=self.now + cal,
            u_key=key,
            u=u,
        )

    def _is_legal(self, entry: sm.QueueEntry) -> bool:
        """Normal prerequisites of the frozen head (C26 trigger C): device
        pending, bay testing, E prereq, active shift, duration fits the shift.
        The a+d age rules are the D/E/F decision, not part of C."""
        task = self.tasks[entry.task_id]
        device = self.devices[task.device_id]
        if device.terminal_state != sm.TerminalState.PENDING:
            return False
        bay = self.bays[device.bay_id]
        if bay.status != sm.BayStatus.OCCUPIED_TESTING:
            return False
        if task.process == "E":
            for proc in ("A", "B", "C"):
                if device.process_state[proc].process_status != sm.ProcessStatus.PASSED:
                    return False
        shift = self.shift_state.active_shift
        if shift is None:
            return False  # outside any shift (gap): nothing starts
        if self.now + self.config.durations[task.process] > shift.shift_end:
            return False  # would cross the shift boundary (P062)
        return True  # start + duration == shift_end is legal (恰班末完成允许)

    def _start_task(self, head: sm.QueueEntry) -> sm.TestAttemptState:
        task = self.tasks[head.task_id]
        resource_id = task.resource_id
        device = self.devices[task.device_id]
        equip = self.equipment[resource_id]
        shift = self.shift_state.active_shift
        squad = shift.on_duty_squad if shift is not None else None
        a = equip.age
        d = self.config.durations[resource_id]
        outcome = fragment_outcome(
            a, d, equip.lifetime_h, equip.is_right_censored
        )
        if outcome.kind == FragmentOutcomeKind.COMPLETE:
            fragment_duration = outcome.fragment_duration_h
            event_kind = "test_complete"
        elif outcome.kind == FragmentOutcomeKind.FAILED:
            fragment_duration = outcome.fragment_duration_h
            event_kind = "test_failed"
        else:
            # illegal-crossing backstop (defensive; a legal dispatch never
            # reaches this branch because the D/E decision blocks it).
            fragment_duration = outcome.fragment_duration_h
            event_kind = "test_240_interrupt"
        self._fragment_counter[task.task_id] = (
            self._fragment_counter.get(task.task_id, 0) + 1
        )
        execution_no = self._fragment_counter[task.task_id]
        attempt_id = (
            f"A{task.device_id:03d}_{task.process}_"
            f"{task.effective_attempt_no}_{execution_no}"
        )
        attempt = sm.TestAttemptState(
            attempt_id=attempt_id,
            task_id=task.task_id,
            device_id=task.device_id,
            process=task.process,
            effective_attempt_no=task.effective_attempt_no,
            execution_no=execution_no,
            status=sm.AttemptStatus.RUNNING,
            start_time=self.now,
            result_squad_id=squad,
        )
        self.attempts[attempt_id] = attempt
        task.status = sm.TaskStatus.RUNNING
        self.devices[task.device_id].process_state[task.process].process_status = (
            sm.ProcessStatus.IN_PROGRESS
        )
        resource = self.resources[resource_id]
        resource.status = sm.ResourceStatus.BUSY
        resource.current_activity = {
            "kind": "test",
            "task_id": task.task_id,
            "attempt_id": attempt_id,
            "device_id": task.device_id,
            "process": task.process,
            "attempt_no": task.effective_attempt_no,
            "start_time": self.now,
            "end_time": self.now + fragment_duration,
        }
        head.status = sm.QueueEntryStatus.DISPATCHED
        self.queues[resource_id].pop(0)
        end = self.now + fragment_duration
        self._schedule(event_kind, end, attempt_id)
        return attempt

    def _start_payload(self, attempt: sm.TestAttemptState) -> dict[str, Any]:
        task = self.tasks[attempt.task_id]
        device = self.devices[attempt.device_id]
        equip = self.equipment[task.resource_id]
        activity = self.resources[task.resource_id].current_activity
        end = activity["end_time"] if activity else self.now
        return {
            "device_id": attempt.device_id,
            "process": attempt.process,
            "effective_attempt_no": attempt.effective_attempt_no,
            "resource_id": task.resource_id,
            "bay_id": device.bay_id,
            "squad_id": attempt.result_squad_id,
            "task_id": task.task_id,
            "attempt_id": attempt.attempt_id,
            "attempt_start_time": attempt.start_time,
            "attempt_end_time": end,
            "outcome": sm.Outcome.NONE.value,
            "release_time": task.release_time,
            "equipment_age_at_start": equip.age,
            "equipment_generation": equip.generation,
        }

    def _next_device_to_create(self) -> int:
        return self._created_count + 1

    def _running_attempt_of(self, task: sm.TaskState) -> Optional[sm.TestAttemptState]:
        for attempt in self.attempts.values():
            if attempt.task_id == task.task_id and attempt.status == sm.AttemptStatus.RUNNING:
                return attempt
        return None

    def _remove_queue_entry(self, task: sm.TaskState) -> None:
        queue = self.queues[task.resource_id]
        for idx, entry in enumerate(queue):
            if entry.task_id == task.task_id:
                entry.status = sm.QueueEntryStatus.REMOVED
                queue.pop(idx)
                return

    def _turnover_total_h(self) -> Fraction:
        if self.config.turnover_profile == "0.5h_overlap":
            return self.config.transport_out_h
        return self.config.transport_out_h + self.config.transport_in_h

    def _finish_turnover_in(self, bay: sm.BayState, t: Fraction) -> None:
        device_id = self._next_device_to_create()
        if device_id > self.config.batch_size:  # pragma: no cover - defensive
            raise RandomDesError("turnover_in without a next device")
        bay.status = sm.BayStatus.OCCUPIED_TESTING
        bay.transport_phase = "none"
        self._create_device(device_id, t, bay.bay_id)
        self._pending_creations.append(device_id)

    # -- H2. turnover starts ------------------------------------------------

    def _start_turnovers(self) -> None:
        for bay_id in sorted(self.bays):
            bay = self.bays[bay_id]
            if not bay.turnover_pending:
                continue
            if bay.status != sm.BayStatus.OCCUPIED_TESTING:
                continue
            shift = self.shift_state.active_shift
            if shift is None:
                continue
            total = self._turnover_total_h()
            if self.now + total > shift.shift_end:
                continue  # nonpreemptive within shift (P062): wait for next
            bay.turnover_pending = False
            bay.status = sm.BayStatus.OCCUPIED_TRANSPORT_OUT
            bay.transport_phase = "out"
            self._record(
                sm.EventType.TURNOVER_OUT_START.value,
                bay_id=bay_id,
                device_id=bay.current_device_id,
                squad_id=shift.on_duty_squad,
            )
            self._schedule(
                "turnover_out_complete", self.now + self.config.transport_out_h, bay_id
            )

    # -- metrics / summary --------------------------------------------------

    def _generated_problems(self, device: sm.DeviceState) -> list[str]:
        """Generated real problems among A/B/C and D (D only if created)."""
        problems: list[str] = []
        for proc in ("A", "B", "C"):
            if self.true_states[device.device_id][proc]:
                problems.append(proc)
        if device.d_state == sm.DState.PROBLEM:
            problems.append("D")
        return problems

    def _metrics(self) -> dict[str, Any]:
        t = self.now
        passed = [
            d for d in self.devices.values()
            if d.terminal_state == sm.TerminalState.PASSED
        ]
        exited = [
            d for d in self.devices.values()
            if d.terminal_state == sm.TerminalState.EXITED
        ]
        s = len(passed)
        pl = sum(1 for d in passed if self._generated_problems(d))
        pw = sum(1 for d in exited if not self._generated_problems(d))
        shift_count = 0
        index = 0
        while True:
            start = self._shift_start(index)
            if start is None:
                break
            if start < t:
                shift_count += 1
                index += 1
                continue
            break
        denominator = Fraction(shift_count) * self.config.shift_length_h
        yxb = {
            proc: (self.ledger_elapsed[proc] / denominator)
            for proc in RESOURCES
        }
        decision_point_density = (
            Fraction(self._c24_decision_points) / t if t > 0 else Fraction(0)
        )
        return {
            "T": sm.fraction_to_string(t),
            "T_days": sm.fraction_to_string(t / Fraction(24, 1)),
            "S": s,
            "PL": pl,
            "PW": pw,
            "exited": len(exited),
            "YXB_A": sm.fraction_to_string(yxb["A"]),
            "YXB_B": sm.fraction_to_string(yxb["B"]),
            "YXB_C": sm.fraction_to_string(yxb["C"]),
            "YXB_E": sm.fraction_to_string(yxb["E"]),
            "shift_count": shift_count,
            "yxb_denominator_h": sm.fraction_to_string(denominator),
            "equipment": {
                r: {
                    "age_h": sm.fraction_to_string(self.equipment[r].age),
                    "generation": self.equipment[r].generation,
                    "replacement_count": self.equipment[r].replacement_count,
                    "preventive_replacement_count": self.equipment[r].preventive_count,
                    "failure_count": self.equipment[r].failure_count,
                    "lifetime_h": (
                        sm.fraction_to_string(self.equipment[r].lifetime_h)
                        if self.equipment[r].lifetime_h is not None
                        else None
                    ),
                    "is_right_censored": self.equipment[r].is_right_censored,
                    "available": self.equipment[r].available,
                }
                for r in RESOURCES
            },
            "c24": {
                "decision_point_count": self._c24_decision_points,
                "legal_action_count": self._c24_legal_actions,
                "waiting_opportunity_count": self._c24_waiting_opportunities,
                "preventive_replacement_opportunity_count": self._c24_pm_opportunities,
                "decision_point_density": sm.fraction_to_string(decision_point_density),
                "estimated_rollout_branching_burden": (
                    self._c24_decision_points + self._c24_pm_opportunities
                ),
            },
        }

    def _summary(self) -> dict[str, Any]:
        devices: dict[str, Any] = {}
        for device_id in sorted(self.devices):
            device = self.devices[device_id]
            first_failure_times: dict[str, Any] = {}
            for proc in RESOURCES:
                fft = device.process_state[proc].first_failure_time
                first_failure_times[proc] = (
                    sm.fraction_to_string(fft) if fft is not None else None
                )
            devices[str(device_id)] = {
                "entry_time": sm.fraction_to_string(device.entry_time),
                "bay_id": device.bay_id,
                "terminal_state": device.terminal_state.value,
                "exit_reason": device.exit_reason,
                "d_state": device.d_state.value,
                "true_state": {
                    p: self.true_states[device_id][p] for p in ("A", "B", "C")
                },
                "process_status": {
                    proc: device.process_state[proc].process_status.value
                    for proc in RESOURCES
                },
                "first_failure_time": first_failure_times,
            }
        return {
            "devices": devices,
            "bays": {
                str(bay_id): {
                    "status": bay.status.value,
                    "current_device_id": bay.current_device_id,
                    "transport_phase": bay.transport_phase,
                    "turnover_pending": bay.turnover_pending,
                }
                for bay_id, bay in sorted(self.bays.items())
            },
            "ledger_elapsed_h": {
                proc: sm.fraction_to_string(self.ledger_elapsed[proc])
                for proc in RESOURCES
            },
            "equipment": {
                r: {
                    "age_h": sm.fraction_to_string(self.equipment[r].age),
                    "generation": self.equipment[r].generation,
                    "lifetime_h": (
                        sm.fraction_to_string(self.equipment[r].lifetime_h)
                        if self.equipment[r].lifetime_h is not None
                        else None
                    ),
                    "is_right_censored": self.equipment[r].is_right_censored,
                    "replacement_pending": self.equipment[r].replacement_pending,
                    "replacement_count": self.equipment[r].replacement_count,
                    "preventive_count": self.equipment[r].preventive_count,
                    "failure_count": self.equipment[r].failure_count,
                }
                for r in RESOURCES
            },
            "u_consumption_counts": {
                "u_x": 3 * len(self.devices),
                "u_d": sum(
                    1 for d in self.d_states.values()
                ),
                "u_y": sum(
                    1
                    for rec in self.log
                    if rec["event_type"] == sm.EventType.OBSERVATION_MATERIALIZED.value
                ),
                "u_l": 4 + sum(
                    self.equipment[r].replacement_count for r in RESOURCES
                ),
            },
            "consumed_u": {
                key: sm.fraction_to_string(u) for key, u in sorted(self.consumed_u.items())
            },
        }


def run_random_des(
    config: Any, run_metadata: Optional[dict[str, Any]] = None
) -> RandomDesResult:
    """Run the keyed random DES once. ``config`` is a ``RandomDesConfig`` or a
    ``random_des_config_v1`` dict. Deterministic: the same seed+config+code
    always yields a byte/canonical identical event_log (explicit
    ``run_metadata`` is stored on the result and never enters the log)."""
    if not isinstance(config, RandomDesConfig):
        config = RandomDesConfig.from_dict(config)
    engine = RandomDesEngine(config)
    result = engine.run()
    if run_metadata is not None:
        result.run_metadata = dict(run_metadata)
    return result


# ---------------------------------------------------------------------------
# parameters.csv audit (S3-owned rows)
# ---------------------------------------------------------------------------


def validate_parameters_csv(csv_path) -> dict[str, Fraction]:
    """Audit helper: verify that the frozen parameters.csv rows owned by this
    module (P006-P009 durations, P014/P015 transport, P026-P029 defect
    probabilities) exactly match the module constants. Raises ``ValueError``
    on a missing row or a value mismatch. Returns {parameter_id: Fraction}."""
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
