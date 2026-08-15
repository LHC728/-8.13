# -*- coding: utf-8 -*-
"""G3-SPEC-V1.0 S5: C17 full G3-layer independent full-log replay checker (E2).

Role
----
This module is the INDEPENDENT (heterogeneous-source) full-log replay checker
of G3-SPEC-V1.0 section 12 (``c17_full_replay``, CR-V3.1/C17 at the full G3
layer).  Given ONLY the immutable ``event_log`` of the keyed random DES
(``04_代码/main_model/g3/random_des_v1.py``, S3), the frozen
``random_des_config_v1`` config, the shared frozen ``parameters.csv`` and
(optionally) the run ``metrics`` block, it INDEPENDENTLY recomputes every
frozen replay quantity and cross-checks it against the log (对拍):

  * resource occupancy / bay occupancy / shift calendar;
  * task release / start / end / attempt / observation / cancellation;
  * equipment age / generation / sampled lifetime / failure interruption /
    replacement / calibration / turnover;
  * terminal state / T / S / PL / PW / YXB;
  * resource ledger coverage over ``[0, T)``.

Random extension items (G3-SPEC-V1.0 section 12, second bullet) are recomputed
independently: equipment age, generation, sampled lifetime (``U_L`` from the
frozen key schema + the frozen piecewise-linear CDF nodes), failure
interruption, replacement and calibration are all derived from the frozen
inputs (config + parameters.csv + ``g3.key_schema_v1`` /
``g3.lifetime_regeneration_v1``), never copied from the log.  The DES's
recorded ``u`` / ``u_key`` / ``true_state`` / age / generation values are the
*actual* side of the 对拍; the *expected* side is always re-derived from the
canonical world.

Isolation (CR-V3.1/C19 principle; G3-SPEC-V1.0 section 12 ``isolation``)
-------------------------------------------------------------------------
This module imports ONLY the Python standard library plus
``g3.key_schema_v1`` (the frozen random-key schema P061) and
``g3.lifetime_regeneration_v1`` (the frozen C13/C14 lifetime/regeneration
semantic constants; explicitly allowed by the task package: "可复用
g3.key_schema_v1 / g3.lifetime_regeneration_v1（只读共享冻结语义常量，不共享
主 DES 逻辑）").  It NEVER imports ``random_des_v1``, ``des.*`` or any other
main-model DES module, never imports other checker or test modules, never
launches the main engine as a child process, and never reads the main DES
memory state.  Static and dynamic isolation proofs live in
``04_代码/tests/test_g3_replay_checker_v1.py``.

Exactness / determinism
-----------------------
Every canonical value is an exact ``fractions.Fraction``; binary float is
forbidden in the checker source and rejected in its inputs (config kernel
alpha/beta, parameters.csv values, log time/age fields).  The same
(log + config + parameters.csv) always yields a byte-identical canonical
report.

Output contract
---------------
Per run: verdict (PASS/FAIL), the list of precise differences (check_id,
location, expected, actual, message), and the ``recomputed`` block: T, S, PL,
PW, exited, YXB_A..E, shift_count, yxb_denominator_h, elapsed_by_process,
resource busy intervals (test + calibration), bay coverage intervals, per
resource equipment summary (age/generation/counts/lifetime/censoring/
availability), per generation sampled lifetimes, device/task/FCFS-key
summaries and U consumption counts.

Registry: ``CR-V3.1``; check ids C09/C10/C11/C12/C13/C14/C17/C18.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

from g3 import key_schema_v1 as ks
from g3 import lifetime_regeneration_v1 as lr

# ---------------------------------------------------------------------------
# Frozen vocabulary, restated independently (never imported from the DES).
# ---------------------------------------------------------------------------

PROCESSES: tuple[str, ...] = ("A", "B", "C", "E")
ABC: tuple[str, ...] = ("A", "B", "C")
BAY_IDS: tuple[int, ...] = (1, 2)
PROCESS_ORDER: dict[str, int] = {"A": 0, "B": 1, "C": 2, "E": 3}

OUTCOME_PASS: str = "PASS"
OUTCOME_ABNORMAL: str = "ABNORMAL"
OUTCOME_NONE: str = "NONE"

TERMINAL_PASSED: str = "PASSED"
TERMINAL_EXITED: str = "EXITED"
TERMINAL_REASON_SECOND_ABNORMAL: str = "process_second_abnormal"

D_NOT_CREATED: str = "not_created"
D_NORMAL: str = "normal"
D_PROBLEM: str = "problem"

# G3 event types (frozen S3 vocabulary, restated).
EVENT_TRUE_STATE_GENERATED: str = "TRUE_STATE_GENERATED"
EVENT_EQUIPMENT_FAILURE: str = "EQUIPMENT_FAILURE"
EVENT_EQUIPMENT_REPLACEMENT_START: str = "EQUIPMENT_REPLACEMENT_START"
EVENT_EQUIPMENT_CALIBRATION_COMPLETE: str = "EQUIPMENT_CALIBRATION_COMPLETE"
EVENT_EQUIPMENT_REPLACEMENT_DEFERRED: str = "EQUIPMENT_REPLACEMENT_DEFERRED"

EVENT_TYPES: frozenset[str] = frozenset({
    "ACTIVITY_START", "ACTIVITY_COMPLETE", "OBSERVATION_MATERIALIZED",
    "D_CREATED", "TASK_RELEASE", "DEVICE_EXIT", "TASK_CANCEL",
    "TURNOVER_OUT_START", "TURNOVER_OUT_COMPLETE", "TURNOVER_IN_START",
    "TURNOVER_IN_COMPLETE", "SHIFT_CHANGE", "WAKE_UP", "DEVICE_TERMINAL",
    "SIMULATION_END",
    EVENT_TRUE_STATE_GENERATED, EVENT_EQUIPMENT_FAILURE,
    EVENT_EQUIPMENT_REPLACEMENT_START, EVENT_EQUIPMENT_CALIBRATION_COMPLETE,
    EVENT_EQUIPMENT_REPLACEMENT_DEFERRED,
})

CANCEL_REASON_EQUIPMENT_FAILURE: str = "EQUIPMENT_FAILURE"
CANCEL_REASON_ILLEGAL_240_INTERRUPT: str = "ILLEGAL_240_INTERRUPT"
CANCEL_REASON_DEVICE_EXIT: str = "DEVICE_EXIT"
CANCEL_REASONS: frozenset[str] = frozenset({
    CANCEL_REASON_EQUIPMENT_FAILURE,
    CANCEL_REASON_ILLEGAL_240_INTERRUPT,
    CANCEL_REASON_DEVICE_EXIT,
})

REPLACEMENT_KIND_FAILURE: str = "failure"
REPLACEMENT_KIND_MANDATORY_240: str = "mandatory_240"
REPLACEMENT_KIND_PREVENTIVE: str = "preventive"
REPLACEMENT_KINDS: frozenset[str] = frozenset({
    REPLACEMENT_KIND_FAILURE, REPLACEMENT_KIND_MANDATORY_240,
    REPLACEMENT_KIND_PREVENTIVE,
})

REPLACEMENT_TRIGGER_MID_FRAGMENT_FAILURE: str = "mid_fragment_failure"
REPLACEMENT_TRIGGER_FAILURE_AT_END: str = "failure_at_end"
REPLACEMENT_TRIGGER_CANCEL_REACHED_LIMIT: str = "cancel_reached_limit"
REPLACEMENT_TRIGGER_POST_COMPLETION_240: str = "post_completion_240"
REPLACEMENT_TRIGGER_A_PLUS_D_GT_240: str = "a_plus_d_gt_240"
REPLACEMENT_TRIGGER_ILLEGAL_CROSSING_BACKSTOP: str = "illegal_crossing_backstop"
REPLACEMENT_TRIGGER_PREVENTIVE: str = "preventive"
REPLACEMENT_TRIGGERS: frozenset[str] = frozenset({
    REPLACEMENT_TRIGGER_MID_FRAGMENT_FAILURE,
    REPLACEMENT_TRIGGER_FAILURE_AT_END,
    REPLACEMENT_TRIGGER_CANCEL_REACHED_LIMIT,
    REPLACEMENT_TRIGGER_POST_COMPLETION_240,
    REPLACEMENT_TRIGGER_A_PLUS_D_GT_240,
    REPLACEMENT_TRIGGER_ILLEGAL_CROSSING_BACKSTOP,
    REPLACEMENT_TRIGGER_PREVENTIVE,
})

# Frozen trigger -> allowed kind mapping (G3-SPEC-V1.0 sections 5/7).
_TRIGGER_KIND: dict[str, str] = {
    REPLACEMENT_TRIGGER_MID_FRAGMENT_FAILURE: REPLACEMENT_KIND_FAILURE,
    REPLACEMENT_TRIGGER_FAILURE_AT_END: REPLACEMENT_KIND_FAILURE,
    REPLACEMENT_TRIGGER_POST_COMPLETION_240: REPLACEMENT_KIND_MANDATORY_240,
    REPLACEMENT_TRIGGER_A_PLUS_D_GT_240: REPLACEMENT_KIND_MANDATORY_240,
    REPLACEMENT_TRIGGER_ILLEGAL_CROSSING_BACKSTOP: REPLACEMENT_KIND_MANDATORY_240,
    REPLACEMENT_TRIGGER_PREVENTIVE: REPLACEMENT_KIND_PREVENTIVE,
}

# Per-event-type required fields (mirrors the S3 DES _record calls; the shared
# event-log vocabulary).
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    EVENT_TRUE_STATE_GENERATED: (
        "device_id", "entry_time", "bay_id", "true_state", "u_keys", "u"),
    "TASK_RELEASE": (
        "device_id", "process", "effective_attempt_no", "resource_id",
        "task_id", "release_time"),
    "ACTIVITY_START": (
        "device_id", "process", "effective_attempt_no", "resource_id",
        "bay_id", "task_id", "attempt_id", "attempt_start_time",
        "attempt_end_time", "outcome", "release_time",
        "equipment_age_at_start", "equipment_generation"),
    "ACTIVITY_COMPLETE": (
        "device_id", "process", "effective_attempt_no", "resource_id",
        "bay_id", "task_id", "attempt_id", "attempt_start_time",
        "attempt_end_time", "outcome", "elapsed_hours",
        "equipment_age_at_end", "equipment_generation"),
    "OBSERVATION_MATERIALIZED": (
        "device_id", "process", "effective_attempt_no", "resource_id",
        "task_id", "attempt_id", "outcome", "true_state", "u_key", "u"),
    "D_CREATED": ("device_id", "d_state", "bay_id", "u_key", "u"),
    "DEVICE_EXIT": ("device_id", "process", "effective_attempt_no"),
    "DEVICE_TERMINAL": ("device_id", "terminal_state"),
    "TASK_CANCEL": (
        "device_id", "process", "effective_attempt_no", "resource_id",
        "bay_id", "task_id", "outcome", "cancel_reason", "elapsed_hours"),
    "TURNOVER_OUT_START": ("bay_id", "device_id"),
    "TURNOVER_OUT_COMPLETE": ("bay_id", "device_id"),
    "TURNOVER_IN_START": ("bay_id", "device_id"),
    "TURNOVER_IN_COMPLETE": ("bay_id", "device_id"),
    "SHIFT_CHANGE": ("shift_index", "shift_start", "shift_end", "on_duty_squad"),
    "WAKE_UP": (),
    "SIMULATION_END": (),
    EVENT_EQUIPMENT_FAILURE: (
        "resource_id", "task_id", "attempt_id", "device_id", "process",
        "effective_attempt_no", "fragment_start", "fragment_end",
        "elapsed_hours", "equipment_age_at_failure", "equipment_generation"),
    EVENT_EQUIPMENT_REPLACEMENT_START: (
        "resource_id", "kind", "trigger", "old_generation", "new_generation",
        "age_before", "calibration_duration_hours", "calibration_start",
        "calibration_end", "u_key", "u"),
    EVENT_EQUIPMENT_CALIBRATION_COMPLETE: (
        "resource_id", "generation", "calibration_end"),
    EVENT_EQUIPMENT_REPLACEMENT_DEFERRED: (
        "resource_id", "kind", "trigger", "reason", "next_wake"),
}

TIME_FIELDS: tuple[str, ...] = (
    "event_time", "entry_time", "attempt_start_time", "attempt_end_time",
    "elapsed_hours", "release_time", "shift_start", "shift_end",
    "fragment_start", "fragment_end", "calibration_start", "calibration_end",
    "age_before", "equipment_age_at_start", "equipment_age_at_end",
    "equipment_age_at_failure", "next_wake", "calibration_duration_hours",
)

REGISTRY_VERSION: str = "CR-V3.1"
CHECK_IDS: tuple[str, ...] = (
    "C09", "C10", "C11", "C12", "C13", "C14", "C17", "C18",
)

# Frozen parameters.csv rows consumed by the checker.
_PARAMETER_ROWS: dict[str, tuple[str, str]] = {
    "P010": ("calibration_minutes", "A"),
    "P011": ("calibration_minutes", "B"),
    "P012": ("calibration_minutes", "C"),
    "P013": ("calibration_minutes", "E"),
    "P016": ("min_preventive_age_h", None),
    "P017": ("mandatory_age_h", None),
    "P018": ("f120", "A"),
    "P019": ("f120", "B"),
    "P020": ("f120", "C"),
    "P021": ("f120", "E"),
    "P022": ("f240", "A"),
    "P023": ("f240", "B"),
    "P024": ("f240", "C"),
    "P025": ("f240", "E"),
    "P026": ("q", "A"),
    "P027": ("q", "B"),
    "P028": ("q", "C"),
    "P029": ("q", "D"),
}

__all__ = [
    "PROCESSES",
    "ABC",
    "BAY_IDS",
    "PROCESS_ORDER",
    "OUTCOME_PASS",
    "OUTCOME_ABNORMAL",
    "OUTCOME_NONE",
    "TERMINAL_PASSED",
    "TERMINAL_EXITED",
    "TERMINAL_REASON_SECOND_ABNORMAL",
    "D_NOT_CREATED",
    "D_NORMAL",
    "D_PROBLEM",
    "EVENT_TRUE_STATE_GENERATED",
    "EVENT_EQUIPMENT_FAILURE",
    "EVENT_EQUIPMENT_REPLACEMENT_START",
    "EVENT_EQUIPMENT_CALIBRATION_COMPLETE",
    "EVENT_EQUIPMENT_REPLACEMENT_DEFERRED",
    "CANCEL_REASON_EQUIPMENT_FAILURE",
    "CANCEL_REASON_ILLEGAL_240_INTERRUPT",
    "CANCEL_REASON_DEVICE_EXIT",
    "REPLACEMENT_KIND_FAILURE",
    "REPLACEMENT_KIND_MANDATORY_240",
    "REPLACEMENT_KIND_PREVENTIVE",
    "REPLACEMENT_TRIGGER_MID_FRAGMENT_FAILURE",
    "REPLACEMENT_TRIGGER_FAILURE_AT_END",
    "REPLACEMENT_TRIGGER_POST_COMPLETION_240",
    "REPLACEMENT_TRIGGER_A_PLUS_D_GT_240",
    "REPLACEMENT_TRIGGER_ILLEGAL_CROSSING_BACKSTOP",
    "REPLACEMENT_TRIGGER_PREVENTIVE",
    "ReplayCheckerError",
    "ReplayCheckerInputError",
    "frac_to_str",
    "parse_fraction",
    "load_parameters",
    "ReplayConfig",
    "parse_config",
    "DeviceChain",
    "derive_device_chain",
    "ReplayIssue",
    "ReplayReport",
    "G3ReplayChecker",
    "check_replay",
]


# ---------------------------------------------------------------------------
# Errors and exact helpers
# ---------------------------------------------------------------------------


class ReplayCheckerError(Exception):
    """Base class for replay-checker failures."""


class ReplayCheckerInputError(ReplayCheckerError):
    """Invalid input (config / parameters / event-log envelope); explicit
    failure, never a silent default."""


def frac_to_str(f: Fraction) -> str:
    """Serialize a Fraction exactly: integer form when the denominator is 1,
    otherwise ``num/den``.  Never a JSON float."""
    f = Fraction(f)
    if f.denominator == 1:
        return str(f.numerator)
    return f"{f.numerator}/{f.denominator}"


def parse_fraction(value: Any, name: str) -> Fraction:
    """Parse an exact rational; binary float and bool are explicitly rejected
    so they can never enter a canonical path."""
    if isinstance(value, bool):
        raise ReplayCheckerInputError(f"{name}: boolean is not a rational")
    if isinstance(value, float):
        raise ReplayCheckerInputError(
            f"{name}: float is forbidden as a canonical value ({value!r}); "
            f"use an exact rational string or Fraction"
        )
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Fraction):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ReplayCheckerInputError(f"{name}: empty rational string")
        try:
            return Fraction(text)
        except (ValueError, ZeroDivisionError) as exc:
            raise ReplayCheckerInputError(
                f"{name}: not a valid rational string: {value!r}"
            ) from exc
    raise ReplayCheckerInputError(
        f"{name}: unsupported type {type(value).__name__}: {value!r}"
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Fraction):
        return frac_to_str(value)
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# Frozen parameters.csv loader (shared read-only input; never duplicated as
# module constants -- the csv is the single authoritative source)
# ---------------------------------------------------------------------------


def load_parameters(csv_path: Any) -> dict[str, Any]:
    """Read the shared frozen ``parameters.csv`` and extract the frozen
    semantic rows the checker needs:

        P010-P013  calibration durations (minutes per resource)
        P016       minimum preventive age (120 h)
        P017       mandatory replacement age (240 h)
        P018-P025  piecewise-linear CDF nodes F_*_120 / F_*_240
        P026-P029  true-defect probabilities q_A..q_D
        P061       key schema (must be ``key_schema_v1``)

    Every value is cross-checked against the frozen shared constants in
    ``g3.lifetime_regeneration_v1``; a missing row, a drifted value or a
    non-parseable value raises ``ReplayCheckerInputError`` (fail loudly;
    never silently accept a drifted parameter).  Returns a dict with keys
    ``calibration_minutes``, ``min_preventive_age_h``, ``mandatory_age_h``,
    ``f120``, ``f240``, ``q`` (all exact Fractions)."""
    path = Path(csv_path)
    parsed: dict[tuple[str, str], Fraction] = {}
    key_schema_seen: Optional[str] = None
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                pid = (row.get("parameter_id") or "").strip()
                value_raw = (row.get("value") or "").strip()
                if pid == "P061":
                    key_schema_seen = value_raw
                    continue
                if pid not in _PARAMETER_ROWS:
                    continue
                try:
                    value = Fraction(value_raw)
                except (ValueError, ZeroDivisionError) as exc:
                    raise ReplayCheckerInputError(
                        f"parameters.csv row {pid}: cannot parse value "
                        f"{value_raw!r}"
                    ) from exc
                kind, resource = _PARAMETER_ROWS[pid]
                parsed[(kind, resource)] = value
    except OSError as exc:
        raise ReplayCheckerInputError(
            f"cannot read parameters.csv: {exc}"
        ) from exc

    missing = [pid for pid in _PARAMETER_ROWS if _PARAMETER_ROWS[pid] not in parsed]
    if missing:
        raise ReplayCheckerInputError(
            f"parameters.csv missing frozen rows: {missing}"
        )
    if key_schema_seen != ks.KEY_SCHEMA_VERSION:
        raise ReplayCheckerInputError(
            f"parameters.csv P061 key_schema must be "
            f"'{ks.KEY_SCHEMA_VERSION}', got {key_schema_seen!r}"
        )

    calibration_minutes: dict[str, Fraction] = {
        r: parsed[("calibration_minutes", r)] for r in PROCESSES
    }
    for r in PROCESSES:
        if calibration_minutes[r] != lr.CALIBRATION_DURATION_MINUTES_FROZEN[r]:
            raise ReplayCheckerInputError(
                f"parameters.csv P0{10 + PROCESS_ORDER[r]}: calibration "
                f"duration for {r} disagrees with the frozen shared constant "
                f"{lr.CALIBRATION_DURATION_MINUTES_FROZEN[r]!r}"
            )
    min_age = parsed[("min_preventive_age_h", None)]
    if min_age != lr.MIN_PREVENTIVE_AGE_H:
        raise ReplayCheckerInputError(
            f"parameters.csv P016 must equal {lr.MIN_PREVENTIVE_AGE_H!r}, "
            f"got {min_age!r}"
        )
    mandatory_age = parsed[("mandatory_age_h", None)]
    if mandatory_age != lr.MANDATORY_REPLACE_AGE_H:
        raise ReplayCheckerInputError(
            f"parameters.csv P017 must equal {lr.MANDATORY_REPLACE_AGE_H!r}, "
            f"got {mandatory_age!r}"
        )
    f120: dict[str, Fraction] = {r: parsed[("f120", r)] for r in PROCESSES}
    f240: dict[str, Fraction] = {r: parsed[("f240", r)] for r in PROCESSES}
    for r in PROCESSES:
        if f120[r] != lr.frozen_f120(r) or f240[r] != lr.frozen_f240(r):
            raise ReplayCheckerInputError(
                f"parameters.csv CDF nodes for {r} disagree with the frozen "
                f"shared constants f120={lr.frozen_f120(r)!r}, "
                f"f240={lr.frozen_f240(r)!r}"
            )
    q: dict[str, Fraction] = {r: parsed[("q", r)] for r in ("A", "B", "C", "D")}
    return {
        "calibration_minutes": calibration_minutes,
        "min_preventive_age_h": min_age,
        "mandatory_age_h": mandatory_age,
        "f120": f120,
        "f240": f240,
        "q": q,
    }


# ---------------------------------------------------------------------------
# Frozen config subset (random_des_config_v1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplayConfig:
    """The frozen ``random_des_config_v1`` subset the replay checker consumes.

    Unlike the C06 quality oracle (which is time-layer-free), the replay
    checker needs the full time-layer configuration: scenario, batch size,
    shift calendar, durations, transport, turnover profile, the canonical
    world identity (namespace/master_seed/replicate_id), ``tau_pm`` and the
    observation kernel.
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
    tau_pm: Any  # Fraction | lr.NO_PM_BEFORE_MANDATORY
    observation_kernel: dict[str, dict[str, Fraction]]
    key_schema_version: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ReplayConfig":
        if not isinstance(raw, dict):
            raise ReplayCheckerInputError("config must be a JSON object")
        if raw.get("schema_version") != "random_des_config_v1":
            raise ReplayCheckerInputError(
                "config.schema_version must be 'random_des_config_v1'"
            )
        schema = raw.get("key_schema_version")
        if schema != ks.KEY_SCHEMA_VERSION:
            raise ReplayCheckerInputError(
                f"config.key_schema_version must be '{ks.KEY_SCHEMA_VERSION}', "
                f"got {schema!r} (P061)"
            )
        scenario = raw.get("scenario")
        if scenario not in ("q2_single_shift", "q3_two_shift", "isolated_small_case"):
            raise ReplayCheckerInputError(
                f"config.scenario invalid: {scenario!r}"
            )
        scenario_id = raw.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ReplayCheckerInputError(
                "config.scenario_id must be a non-empty string"
            )
        batch_size = raw.get("batch_size")
        if not isinstance(batch_size, int) or batch_size < 1:
            raise ReplayCheckerInputError(
                "config.batch_size must be a positive integer"
            )
        shift_length_h = parse_fraction(
            raw.get("shift_length_h"), "config.shift_length_h"
        )
        if shift_length_h <= 0:
            raise ReplayCheckerInputError("config.shift_length_h must be positive")
        shifts_per_day = raw.get("shifts_per_day")
        if not isinstance(shifts_per_day, int) or shifts_per_day < 1:
            raise ReplayCheckerInputError(
                "config.shifts_per_day must be a positive integer"
            )
        durations_raw = raw.get("durations")
        if not isinstance(durations_raw, dict):
            raise ReplayCheckerInputError("config.durations must be an object")
        durations: dict[str, Fraction] = {}
        for proc in PROCESSES:
            if proc not in durations_raw:
                raise ReplayCheckerInputError(
                    f"config.durations missing process {proc}"
                )
            d = parse_fraction(durations_raw[proc], f"config.durations.{proc}")
            if d <= 0:
                raise ReplayCheckerInputError(
                    f"config.durations.{proc} must be positive"
                )
            durations[proc] = d
        transport_out = parse_fraction(
            raw.get("transport_out_h"), "config.transport_out_h"
        )
        transport_in = parse_fraction(
            raw.get("transport_in_h"), "config.transport_in_h"
        )
        if transport_out < 0 or transport_in < 0:
            raise ReplayCheckerInputError(
                "config transport durations must be non-negative"
            )
        profile = raw.get("turnover_profile")
        if profile not in ("1h_literal", "0.5h_overlap"):
            raise ReplayCheckerInputError(
                f"config.turnover_profile invalid: {profile!r}"
            )
        initial = raw.get("deterministic_initial_state")
        if not isinstance(initial, dict):
            raise ReplayCheckerInputError(
                "config.deterministic_initial_state must be an object"
            )
        if initial.get("all_calibrated") is not True \
                or initial.get("queues_empty") is not True:
            raise ReplayCheckerInputError(
                "config.deterministic_initial_state.all_calibrated/"
                "queues_empty must be true"
            )
        preloaded = initial.get("preloaded_devices")
        if not isinstance(preloaded, list) or not preloaded:
            raise ReplayCheckerInputError(
                "config.deterministic_initial_state.preloaded_devices invalid"
            )
        expected_preload = [1] if batch_size == 1 else [1, 2]
        if list(preloaded) != expected_preload:
            raise ReplayCheckerInputError(
                "SEM-21 initial-state rule: batch_size==%d requires "
                "preloaded_devices == %r, got %r"
                % (batch_size, expected_preload, list(preloaded))
            )
        namespace = raw.get("namespace")
        if namespace not in ks.NAMESPACES:
            raise ReplayCheckerInputError(
                f"config.namespace must be one of the six frozen namespaces "
                f"{ks.NAMESPACES}, got {namespace!r}"
            )
        master_seed = raw.get("master_seed")
        replicate_id = raw.get("replicate_id")
        if isinstance(master_seed, bool) or not isinstance(master_seed, int) \
                or master_seed < 0:
            raise ReplayCheckerInputError(
                "config.master_seed must be a non-negative int"
            )
        if isinstance(replicate_id, bool) or not isinstance(replicate_id, int) \
                or replicate_id < 0:
            raise ReplayCheckerInputError(
                "config.replicate_id must be a non-negative int"
            )
        tau_raw = raw.get("tau_pm")
        if tau_raw == "NO_PM_BEFORE_MANDATORY":
            tau_pm: Any = lr.NO_PM_BEFORE_MANDATORY
        else:
            tau_pm = parse_fraction(tau_raw, "config.tau_pm")
            if not (lr.MIN_PREVENTIVE_AGE_H <= tau_pm
                    < lr.MANDATORY_REPLACE_AGE_H):
                raise ReplayCheckerInputError(
                    "numeric tau_pm must be in [120, 240) hours (240 is "
                    "mandatory semantics, never a preventive threshold)"
                )
        kernel_raw = raw.get("observation_kernel")
        if not isinstance(kernel_raw, dict):
            raise ReplayCheckerInputError(
                "config.observation_kernel must be an object"
            )
        kernel: dict[str, dict[str, Fraction]] = {}
        for proc in PROCESSES:
            entry = kernel_raw.get(proc)
            if not isinstance(entry, dict) or set(entry) != {"alpha", "beta"}:
                raise ReplayCheckerInputError(
                    f"config.observation_kernel[{proc}] must have exactly "
                    f"alpha and beta"
                )
            alpha = parse_fraction(entry["alpha"], f"observation_kernel[{proc}].alpha")
            beta = parse_fraction(entry["beta"], f"observation_kernel[{proc}].beta")
            if not (Fraction(0) <= alpha <= Fraction(1)):
                raise ReplayCheckerInputError(
                    f"observation_kernel[{proc}].alpha must be in [0, 1]"
                )
            if not (Fraction(0) <= beta <= Fraction(1)):
                raise ReplayCheckerInputError(
                    f"observation_kernel[{proc}].beta must be in [0, 1]"
                )
            kernel[proc] = {"alpha": alpha, "beta": beta}
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
            turnover_profile=profile,
            preloaded_devices=tuple(preloaded),
            namespace=namespace,
            master_seed=master_seed,
            replicate_id=replicate_id,
            tau_pm=tau_pm,
            observation_kernel=kernel,
            key_schema_version=ks.KEY_SCHEMA_VERSION,
        )


def parse_config(config: Any) -> ReplayConfig:
    """Parse a ``random_des_config_v1`` dict (or a ``ReplayConfig``)."""
    if isinstance(config, ReplayConfig):
        return config
    return ReplayConfig.from_dict(config)


# ---------------------------------------------------------------------------
# Canonical quality chain (G3-SPEC-V1.0 section 9; time-layer-free forward
# chain recomputed from the key schema -- the same world the DES lives in)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceChain:
    """One device's canonical absorption chain, derived from the key schema.

    All values are recomputed from ``g3.key_schema_v1`` with the same
    (namespace, replicate_id, master_seed) as the DES; nothing is read from
    the log.  The DES's recorded outcomes/terminal/D/true states are the
    *actual* side of the 对拍.
    """

    device_id: int
    true_abc: dict[str, bool]
    d_value: str                      # normal | problem | not_created
    terminal: str                     # PASSED | EXITED
    expected_observations: dict[tuple[str, int], str]  # (process, attempt) -> outcome
    exit_processes: tuple[str, ...]   # processes whose chain ended ABNORMAL


def _kernel_outcome(cfg: ReplayConfig, true_problem: bool, u: Fraction,
                    process: str) -> str:
    entry = cfg.observation_kernel[process]
    alpha = entry["alpha"]
    beta = entry["beta"]
    if true_problem:
        return OUTCOME_ABNORMAL if u < Fraction(1) - beta else OUTCOME_PASS
    return OUTCOME_ABNORMAL if u < alpha else OUTCOME_PASS


def derive_device_chain(cfg: ReplayConfig, params: dict[str, Any],
                        device_id: int,
                        completed_observations: Optional[set[tuple[str, int]]] = None
                        ) -> DeviceChain:
    """Forward-chain one device's absorption in the canonical world.

    Frozen semantics (V3.1 section 9; problem contract 1.1/1.2): A/B/C each
    run attempt 1 and, on a first ABNORMAL, a full retest (attempt 2); a
    second ABNORMAL exits the device.  D materializes exactly once when A/B/C
    are all PASS; E runs with true problem = any(A/B/C) or D, retesting once
    on ABNORMAL; the device passes iff E's final observation is PASS, exits
    iff any chain reaches two ABNORMALs.

    Cancellation / non-observation semantics (G3-SPEC-V1.0 section 2; frozen):
    an interrupted/cancelled/non-completed attempt produces NO observation and
    does NOT advance the effective attempt.  A process may therefore be
    classified as an actual exit-causing process ONLY from an EFFECTIVE
    COMPLETED observation path: attempt1 completed with OBSERVATION=ABNORMAL
    AND attempt2 completed with OBSERVATION=ABNORMAL, both valid under the
    frozen same-timestamp / cancellation semantics.

    ``completed_observations`` (optional): the set of (process, attempt_no)
    pairs that ACTUALLY completed an observation in the event log (derived
    from OBSERVATION_MATERIALIZED records).  When supplied, an attempt2 that
    was never started / shifted / interrupted / terminal-cancelled / otherwise
    has no effective completed observation is NEVER treated as an exit-causing
    ABNORMAL merely because its canonical U_Y would map to ABNORMAL had it
    completed.  The canonical U/outcome is still recomputed to VERIFY an
    actually completed observation (independent replay); a non-observed
    counterfactual U is never turned into a real observation.
    """
    ns = cfg.namespace
    rep = cfg.replicate_id
    seed = cfg.master_seed
    q = params["q"]

    true_abc: dict[str, bool] = {
        proc: ks.u_x(ns, rep, device_id, proc, seed) < q[proc]
        for proc in ABC
    }
    expected: dict[tuple[str, int], str] = {}
    abc_all_pass = True
    exit_processes: list[str] = []
    for proc in ABC:
        out1 = _kernel_outcome(
            cfg, true_abc[proc], ks.u_y(ns, rep, device_id, proc, 1, seed), proc
        )
        expected[(proc, 1)] = out1
        if out1 == OUTCOME_ABNORMAL:
            out2 = _kernel_outcome(
                cfg, true_abc[proc], ks.u_y(ns, rep, device_id, proc, 2, seed), proc
            )
            expected[(proc, 2)] = out2
            # cancelled/non-completed attempt2 must not become an exit process
            attempt2_completed = (
                completed_observations is None
                or (proc, 2) in completed_observations
            )
            if out2 == OUTCOME_ABNORMAL and attempt2_completed:
                abc_all_pass = False
                exit_processes.append(proc)

    d_value = D_NOT_CREATED
    if abc_all_pass:
        d_problem = ks.u_d(ns, rep, device_id, seed) < q["D"]
        d_value = D_PROBLEM if d_problem else D_NORMAL

    if not abc_all_pass:
        terminal = TERMINAL_EXITED
    else:
        true_e = any(true_abc[proc] for proc in ABC) or d_value == D_PROBLEM
        e1 = _kernel_outcome(
            cfg, true_e, ks.u_y(ns, rep, device_id, "E", 1, seed), "E"
        )
        expected[("E", 1)] = e1
        if e1 == OUTCOME_ABNORMAL:
            e2 = _kernel_outcome(
                cfg, true_e, ks.u_y(ns, rep, device_id, "E", 2, seed), "E"
            )
            expected[("E", 2)] = e2
            e2_completed = (
                completed_observations is None
                or ("E", 2) in completed_observations
            )
            if e2 == OUTCOME_ABNORMAL and e2_completed:
                terminal = TERMINAL_EXITED
                exit_processes.append("E")
            else:
                terminal = TERMINAL_PASSED
        else:
            terminal = TERMINAL_PASSED

    return DeviceChain(
        device_id=device_id,
        true_abc=true_abc,
        d_value=d_value,
        terminal=terminal,
        expected_observations=dict(expected),
        exit_processes=tuple(sorted(exit_processes)),
    )


# ---------------------------------------------------------------------------
# Report structures
# ---------------------------------------------------------------------------


@dataclass
class ReplayIssue:
    """One precise difference found by the checker."""

    check_id: str
    location: str
    expected: Any
    actual: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "location": self.location,
            "expected": _json_safe(self.expected),
            "actual": _json_safe(self.actual),
            "message": self.message,
        }

    def describe(self) -> str:
        return "[%s] %s: %s (expected=%r, actual=%r)" % (
            self.check_id, self.location, self.message,
            _json_safe(self.expected), _json_safe(self.actual),
        )


@dataclass
class ReplayReport:
    """Deterministic report of one replay-checker run."""

    run_id: str
    scenario_id: str
    verdict: str  # PASS | FAIL
    issues: list[ReplayIssue] = field(default_factory=list)
    recomputed: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_type": "g3_replay_check_report",
            "schema_version": "g3_replay_check_report_v1",
            "registry_version": REGISTRY_VERSION,
            "check_ids": list(CHECK_IDS),
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "verdict": self.verdict,
            "issues": [i.to_dict() for i in self.issues],
            "recomputed": _json_safe(self.recomputed),
            "metadata": _json_safe(self.metadata),
        }

    def summarize(self) -> str:
        return "%s %s %s T=%s S=%s PL=%s PW=%s (%d issues)" % (
            self.run_id,
            self.scenario_id,
            self.verdict,
            self.recomputed.get("T_h"),
            self.recomputed.get("S"),
            self.recomputed.get("PL"),
            self.recomputed.get("PW"),
            len(self.issues),
        )


# ---------------------------------------------------------------------------
# The independent replay checker
# ---------------------------------------------------------------------------


class G3ReplayChecker:
    """Replays an immutable G3 event log and independently recomputes every
    frozen C17 quantity, comparing each against the log (对拍) and (optionally)
    against the run ``metrics`` block."""

    def __init__(self, event_log: Any, config: Any,
                 parameters_csv: Any,
                 metrics: Optional[dict[str, Any]] = None,
                 run_id: Optional[str] = None) -> None:
        self._issues: list[ReplayIssue] = []
        self._recomputed: dict[str, Any] = {}
        self._cfg = parse_config(config)
        self._params = load_parameters(parameters_csv)
        self._metrics = metrics if isinstance(metrics, dict) else None
        self._run_id = run_id or self._cfg.scenario_id
        self._log, self._structural_ok = self._parse_event_log(event_log)

        # replay views (built lazily)
        self._records_by_type: dict[str, list[dict[str, Any]]] = {}
        self._tasks: dict[tuple, dict[str, Any]] = {}
        self._attempts: dict[str, dict[str, Any]] = {}   # attempt_id -> view
        self._devices: dict[int, dict[str, Any]] = {}
        self._shifts: list[dict[str, Any]] = []
        self._turnovers: list[dict[str, Any]] = []
        self._T: Optional[Fraction] = None
        self._chains: dict[int, DeviceChain] = {}
        self._obs_by_attempt: dict[str, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # issue helper
    # ------------------------------------------------------------------

    def _issue(self, check_id: str, location: str, expected: Any, actual: Any,
               message: str) -> None:
        self._issues.append(ReplayIssue(check_id, location, expected, actual, message))

    def _f(self, value: Any, name: str) -> Fraction:
        return parse_fraction(value, name)

    # ------------------------------------------------------------------
    # structural parsing
    # ------------------------------------------------------------------

    def _parse_event_log(self, event_log: Any) -> tuple[list[dict[str, Any]], bool]:
        """Validate the envelope structure, seq monotonicity, event types,
        per-type required fields, exact times and the terminal SIMULATION_END.
        Returns ``(records, ok)``; every structural problem is recorded as an
        explicit issue (never a silent PASS)."""
        if isinstance(event_log, dict) and isinstance(event_log.get("records"), list):
            records = event_log["records"]
        elif isinstance(event_log, list):
            records = event_log
        else:
            self._issue("C17", "event_log", "list or {records: [...]}",
                        type(event_log).__name__,
                        "event_log must be a JSON array or an envelope object")
            return [], False
        if not records:
            self._issue("C17", "event_log", "non-empty", "empty",
                        "event_log is empty (explicit FAIL, never a silent PASS)")
            return [], False
        ok = True
        parsed: list[dict[str, Any]] = []
        expected_seq = 1
        prev_time: Optional[Fraction] = None
        for idx, rec in enumerate(records):
            loc = "record[%d]" % idx
            if not isinstance(rec, dict):
                self._issue("C17", loc, "object", type(rec).__name__,
                            "log record must be an object")
                ok = False
                continue
            seq = rec.get("seq")
            if not isinstance(seq, int) or seq != expected_seq:
                self._issue("C17", loc, "seq == %d" % expected_seq, seq,
                            "seq must be a strictly increasing integer "
                            "starting at 1 (no gaps, no duplicates)")
                ok = False
            expected_seq += 1
            event_type = rec.get("event_type")
            if event_type not in EVENT_TYPES:
                self._issue("C17", loc, "one of %s" % sorted(EVENT_TYPES),
                            event_type, "unknown event_type")
                ok = False
            try:
                t = self._f(rec.get("event_time"), "%s.event_time" % loc)
            except ReplayCheckerInputError as exc:
                self._issue("C17", loc, "exact rational string",
                            rec.get("event_time"),
                            "invalid canonical time: %s" % exc)
                ok = False
                t = None
            if t is not None:
                if prev_time is not None and t < prev_time:
                    self._issue("C18", loc, ">= %s" % frac_to_str(prev_time),
                                frac_to_str(t),
                                "event_time goes backwards (time must be "
                                "non-decreasing)")
                    ok = False
                prev_time = t
            # binary float anywhere in a canonical record is forbidden
            for key, value in rec.items():
                if isinstance(value, float):
                    self._issue("C17", "%s.%s" % (loc, key),
                                "exact rational / int / str / bool",
                                value, "binary float is forbidden in a "
                                       "canonical log record")
                    ok = False
            for field_name in TIME_FIELDS:
                if field_name in rec and not isinstance(rec[field_name], str) \
                        and not isinstance(rec[field_name], int) \
                        and not isinstance(rec[field_name], Fraction):
                    self._issue("C17", "%s.%s" % (loc, field_name),
                                "exact rational string", rec[field_name],
                                "time/age field must be an exact rational")
                    ok = False
            for field_name in REQUIRED_FIELDS.get(event_type, ()):
                if rec.get(field_name) is None:
                    self._issue("C17", "%s.%s" % (loc, event_type),
                                "present", None,
                                "missing required field %s for event_type %s"
                                % (field_name, event_type))
                    ok = False
            parsed.append(rec)
        sim_ends = [r for r in parsed if r.get("event_type") == "SIMULATION_END"]
        if len(sim_ends) != 1:
            self._issue("C17", "event_log", "exactly one SIMULATION_END",
                        len(sim_ends),
                        "SIMULATION_END must appear exactly once (an "
                        "incomplete log is an explicit FAIL)")
            ok = False
        elif parsed and parsed[-1].get("event_type") != "SIMULATION_END":
            self._issue("C18", "event_log", "SIMULATION_END as the last record",
                        parsed[-1].get("event_type"),
                        "SIMULATION_END must be the final record")
            ok = False
        return parsed, ok

    # ------------------------------------------------------------------
    # frozen calendar helpers (restated independently)
    # ------------------------------------------------------------------

    def _shift_interval(self, index: int) -> Optional[tuple[Fraction, Fraction, int]]:
        """(start, end, squad) of shift ``index`` per the frozen calendar."""
        scenario = self._cfg.scenario
        length = self._cfg.shift_length_h
        if scenario == "q3_two_shift":
            day = index // self._cfg.shifts_per_day
            slot = index % self._cfg.shifts_per_day
            start = Fraction(day) * Fraction(24) + Fraction(slot) * length
            squad = 1 if index % 2 == 0 else 2
            return (start, start + length, squad)
        if scenario == "q2_single_shift":
            start = Fraction(index) * Fraction(24)
            return (start, start + length, 1)
        if index == 0:
            return (Fraction(0), length, 1)
        return None

    def _shift_at(self, t: Fraction) -> Optional[tuple[Fraction, Fraction, int]]:
        index = 0
        while True:
            iv = self._shift_interval(index)
            if iv is None:
                return None
            start, end, squad = iv
            if start <= t < end:
                return iv
            if t < start:
                return None
            index += 1

    def _is_shift_boundary(self, t: Fraction) -> bool:
        """True iff ``t`` is the start or end of some frozen shift."""
        index = 0
        while True:
            iv = self._shift_interval(index)
            if iv is None:
                return False
            start, end, _squad = iv
            if t == start or t == end:
                return True
            if t < start:
                return False
            index += 1

    def _shift_count_up_to(self, t: Fraction) -> int:
        """Number of shifts whose start is strictly before ``t`` (the frozen
        YXB denominator rule: 首班到末班全部计划班次乘班长)."""
        count = 0
        index = 0
        while True:
            iv = self._shift_interval(index)
            if iv is None:
                break
            start, _end, _squad = iv
            if start < t:
                count += 1
                index += 1
                continue
            break
        return count

    # ------------------------------------------------------------------
    # replay views
    # ------------------------------------------------------------------

    def _build_views(self) -> None:
        self._records_by_type = {}
        for rec in self._log:
            self._records_by_type.setdefault(rec.get("event_type"), []).append(rec)

        # tasks: keyed by (device_id, process, effective_attempt_no)
        tasks: dict[tuple, dict[str, Any]] = {}
        for rec in self._log:
            et = rec.get("event_type")
            if et not in ("TASK_RELEASE", "ACTIVITY_START", "ACTIVITY_COMPLETE",
                          "TASK_CANCEL", "OBSERVATION_MATERIALIZED"):
                continue
            key = (rec.get("device_id"), rec.get("process"),
                   rec.get("effective_attempt_no"))
            if None in key:
                continue
            view = tasks.setdefault(key, {
                "release_time": None, "release_seq": None,
                "release_event_time": None,
                "starts": [], "completes": [], "cancels": [], "observations": [],
            })
            if et == "TASK_RELEASE":
                view["release_time"] = self._f(rec.get("release_time"),
                                               "TASK_RELEASE.release_time")
                view["release_event_time"] = self._f(rec.get("event_time"),
                                                     "TASK_RELEASE.event_time")
                view["release_seq"] = rec.get("seq")
            elif et == "ACTIVITY_START":
                view["starts"].append(rec)
            elif et == "ACTIVITY_COMPLETE":
                view["completes"].append(rec)
            elif et == "TASK_CANCEL":
                view["cancels"].append(rec)
            elif et == "OBSERVATION_MATERIALIZED":
                view["observations"].append(rec)
        self._tasks = tasks

        # attempts: keyed by attempt_id
        attempts: dict[str, dict[str, Any]] = {}
        for rec in self._log:
            et = rec.get("event_type")
            attempt_id = rec.get("attempt_id")
            if et not in ("ACTIVITY_START", "ACTIVITY_COMPLETE", "TASK_CANCEL",
                          "OBSERVATION_MATERIALIZED") or attempt_id is None:
                continue
            view = attempts.setdefault(attempt_id, {
                "start": None, "terminal": None, "terminal_type": None,
                "observation": None, "task_key": None,
            })
            if et == "ACTIVITY_START":
                view["start"] = rec
                view["task_key"] = (rec.get("device_id"), rec.get("process"),
                                    rec.get("effective_attempt_no"))
            elif et == "ACTIVITY_COMPLETE":
                view["terminal"] = rec
                view["terminal_type"] = "ACTIVITY_COMPLETE"
            elif et == "TASK_CANCEL":
                view["terminal"] = rec
                view["terminal_type"] = "TASK_CANCEL"
            elif et == "OBSERVATION_MATERIALIZED":
                view["observation"] = rec
        self._attempts = attempts

        # observations per attempt (for pairing checks)
        obs_by_attempt: dict[str, list[dict[str, Any]]] = {}
        for rec in self._log:
            if rec.get("event_type") == "OBSERVATION_MATERIALIZED":
                obs_by_attempt.setdefault(rec.get("attempt_id"), []).append(rec)
        self._obs_by_attempt = obs_by_attempt

        # devices
        devices: dict[int, dict[str, Any]] = {}
        for rec in self._log:
            et = rec.get("event_type")
            device_id = rec.get("device_id")
            if device_id is None or not isinstance(device_id, int):
                continue
            dev = devices.setdefault(device_id, {
                "terminal_state": None, "terminal_time": None,
                "terminal_reason": None, "terminal_count": 0,
                "d_created": None, "d_state": D_NOT_CREATED, "d_count": 0,
                "exit_seq": None, "bay_id": None, "entry_time": None,
                "true_state": None, "u_seen": False,
            })
            if et == EVENT_TRUE_STATE_GENERATED:
                dev["entry_time"] = self._f(rec.get("entry_time"),
                                            "TRUE_STATE_GENERATED.entry_time")
                dev["bay_id"] = rec.get("bay_id")
                dev["true_state"] = rec.get("true_state")
                dev["u_seen"] = True
            elif et == "DEVICE_TERMINAL":
                dev["terminal_state"] = rec.get("terminal_state")
                dev["terminal_time"] = self._f(rec.get("event_time"),
                                               "DEVICE_TERMINAL.event_time")
                dev["terminal_reason"] = rec.get("terminal_reason")
                dev["terminal_count"] += 1
            elif et == "DEVICE_EXIT":
                dev["exit_seq"] = rec.get("seq")
            elif et == "D_CREATED":
                dev["d_created"] = self._f(rec.get("event_time"),
                                           "D_CREATED.event_time")
                dev["d_state"] = rec.get("d_state")
                dev["d_count"] += 1
            elif et == "ACTIVITY_START":
                if dev["bay_id"] is None:
                    dev["bay_id"] = rec.get("bay_id")
        self._devices = devices

        # shifts
        self._shifts = []
        for rec in self._log:
            if rec.get("event_type") != "SHIFT_CHANGE":
                continue
            self._shifts.append({
                "seq": rec.get("seq"),
                "time": self._f(rec.get("event_time"), "SHIFT_CHANGE.event_time"),
                "shift_index": rec.get("shift_index"),
                "shift_start": self._f(rec.get("shift_start"),
                                       "SHIFT_CHANGE.shift_start"),
                "shift_end": self._f(rec.get("shift_end"),
                                     "SHIFT_CHANGE.shift_end"),
                "on_duty_squad": rec.get("on_duty_squad"),
            })

        # turnovers
        self._turnovers = []
        for rec in self._log:
            et = rec.get("event_type")
            if et in ("TURNOVER_OUT_START", "TURNOVER_OUT_COMPLETE",
                      "TURNOVER_IN_START", "TURNOVER_IN_COMPLETE"):
                self._turnovers.append({
                    "seq": rec.get("seq"),
                    "event_type": et,
                    "time": self._f(rec.get("event_time"), "%s.event_time" % et),
                    "bay_id": rec.get("bay_id"),
                    "device_id": rec.get("device_id"),
                })
        self._turnovers.sort(key=lambda x: (x["time"], x["seq"]))

        # T
        ends = [r for r in self._log if r.get("event_type") == "SIMULATION_END"]
        if ends:
            self._T = self._f(ends[-1]["event_time"], "SIMULATION_END.event_time")

    # ------------------------------------------------------------------
    # C17 envelope / termination
    # ------------------------------------------------------------------

    def _check_termination(self) -> None:
        """T == SIMULATION_END time == the last DEVICE_TERMINAL time; every
        record lies within [0, T]; the last device is never transported out."""
        if not self._structural_ok:
            return
        if self._T is None:
            return
        terminals = [dev["terminal_time"] for dev in self._devices.values()
                     if dev["terminal_time"] is not None]
        if terminals:
            max_term = max(terminals)
            if max_term != self._T:
                self._issue("C12", "T",
                            frac_to_str(self._T), frac_to_str(max_term),
                            "SIMULATION_END time must equal the last "
                            "DEVICE_TERMINAL time")
        for rec in self._log:
            t = self._f(rec["event_time"], "event_time")
            if t > self._T:
                self._issue("C12", "record[%s].event_time" % rec.get("seq"),
                            "<= T (%s)" % frac_to_str(self._T), frac_to_str(t),
                            "record after T")
        last = max(terminals) if terminals else None
        if last is not None:
            for tv in self._turnovers:
                if tv["time"] >= last:
                    self._issue("C12", "turnover.%s@%s"
                                % (tv["event_type"], frac_to_str(tv["time"])),
                                "no turnover at/after the last terminal (%s)"
                                % frac_to_str(last), frac_to_str(tv["time"]),
                                "the last device is never transported out "
                                "(末台不运出)")
        self._recomputed["T_h"] = frac_to_str(self._T)
        self._recomputed["T_days"] = frac_to_str(self._T / Fraction(24))

    # ------------------------------------------------------------------
    # C12 shift calendar
    # ------------------------------------------------------------------

    def _check_shift_calendar(self) -> None:
        """SHIFT_CHANGE events must match the frozen calendar exactly."""
        if not self._structural_ok:
            return
        if not self._shifts:
            self._issue("C12", "shift_calendar", ">= 1 SHIFT_CHANGE at t=0", 0,
                        "no SHIFT_CHANGE record in the event log")
            return
        horizon = self._T if self._T is not None else Fraction(0)
        expected: dict[Fraction, tuple[Any, ...]] = {}
        index = 0
        while True:
            iv = self._shift_interval(index)
            if iv is None:
                break
            start, end, squad = iv
            if start > horizon:
                break
            expected[start] = (index, start, end, squad)
            index += 1
        seen_times: set[Fraction] = set()
        for shift in self._shifts:
            t = shift["time"]
            seen_times.add(t)
            if t not in expected:
                self._issue("C12", "SHIFT_CHANGE@%s" % frac_to_str(t),
                            "one of %s" % sorted(frac_to_str(k) for k in expected),
                            frac_to_str(t),
                            "SHIFT_CHANGE at a non-boundary time")
                continue
            exp_index, exp_start, exp_end, exp_squad = expected[t]
            if shift["shift_index"] != exp_index:
                self._issue("C12", "SHIFT_CHANGE@%s.shift_index"
                            % frac_to_str(t), exp_index, shift["shift_index"],
                            "shift_index mismatch")
            if shift["shift_start"] != exp_start or shift["shift_end"] != exp_end:
                self._issue("C12", "SHIFT_CHANGE@%s.interval" % frac_to_str(t),
                            "%s..%s" % (frac_to_str(exp_start), frac_to_str(exp_end)),
                            "%s..%s" % (frac_to_str(shift["shift_start"]),
                                        frac_to_str(shift["shift_end"])),
                            "shift interval mismatch (half-open [start, end))")
            if shift["on_duty_squad"] != exp_squad:
                self._issue("C12", "SHIFT_CHANGE@%s.on_duty_squad"
                            % frac_to_str(t), exp_squad,
                            shift["on_duty_squad"], "on-duty squad mismatch")
        for t in expected:
            if t not in seen_times:
                self._issue("C12", "shift_boundary@%s" % frac_to_str(t),
                            "SHIFT_CHANGE present", "missing",
                            "missing SHIFT_CHANGE at the frozen shift boundary")

    # ------------------------------------------------------------------
    # C09/C10/C11 tasks, attempts, release, FCFS
    # ------------------------------------------------------------------

    def _check_tasks(self) -> None:
        """Per-task release/start/end, attempts, observations, cancellations,
        release frozenness, FCFS start order, E prerequisite and shift
        feasibility."""
        if not self._structural_ok:
            return
        durations = self._cfg.durations
        released_keys: set[tuple] = set()
        for rec in self._records_by_type.get("TASK_RELEASE", []):
            key = (rec.get("device_id"), rec.get("process"),
                   rec.get("effective_attempt_no"))
            if key in released_keys:
                self._issue("C09", "task(%d,%s,%d)" % key, "one TASK_RELEASE",
                            "multiple", "task released more than once")
            released_keys.add(key)
        terminal_at_end: dict[tuple, bool] = {}

        for key in sorted(self._tasks, key=lambda k: (k[0], PROCESS_ORDER[k[1]], k[2])):
            view = self._tasks[key]
            device_id, process, attempt = key
            loc = "task(%d,%s,%d)" % key
            release = view["release_time"]
            release_evt = view["release_event_time"]
            starts = view["starts"]
            completes = view["completes"]
            cancels = view["cancels"]
            observations = view["observations"]
            if release is None:
                self._issue("C09", loc, "TASK_RELEASE present", "missing",
                            "task activity without a TASK_RELEASE record")
                continue
            if release_evt is not None and release != release_evt:
                self._issue("C11", "%s.release_time" % loc,
                            frac_to_str(release_evt), frac_to_str(release),
                            "release_time must equal the TASK_RELEASE event "
                            "time")
            if len(observations) > 1:
                self._issue("C09", loc, "<= 1 OBSERVATION_MATERIALIZED",
                            len(observations),
                            "more than one observation for one task")
            completed = len(completes) == 1
            cancelled = len(cancels) >= 1
            if completed and len(completes) > 1:
                self._issue("C09", loc, "<= 1 ACTIVITY_COMPLETE",
                            len(completes), "task completed more than once")
            if completed and cancelled:
                # a completed task may have prior equipment-failure cancels
                # (retries of the same effective attempt), but never a cancel
                # AFTER its completion and never a READY cancel.
                last_cancel_seq = max(c["seq"] for c in cancels)
                complete_seq = completes[0]["seq"]
                if last_cancel_seq > complete_seq:
                    self._issue("C09", loc, "no TASK_CANCEL after completion",
                                last_cancel_seq,
                                "task cancelled after it completed")
                for c in cancels:
                    if self._f(c["elapsed_hours"], "cancel.elapsed") == 0:
                        self._issue("C09", loc, "no READY cancel for a "
                                   "completed task", c["seq"],
                                   "completed task has a never-started cancel")
            elif not completed and not cancelled:
                self._issue("C18", loc, "COMPLETED or CANCELLED",
                            "RELEASED_UNFINISHED",
                            "released task never reached a terminal state at "
                            "SIMULATION_END")
                continue
            terminal_at_end[key] = True

            # start / finish times
            start = None
            first_start = starts[0] if starts else None
            if first_start is not None:
                start = self._f(first_start["event_time"],
                                "%s.start" % loc)
                if self._f(first_start["attempt_start_time"],
                           "%s.attempt_start_time" % loc) != start:
                    self._issue("C09", "%s.attempt_start_time" % loc,
                                frac_to_str(start),
                                first_start.get("attempt_start_time"),
                                "ACTIVITY_START event_time != "
                                "attempt_start_time")
                if start < release:
                    self._issue("C11", "%s.start" % loc,
                                ">= %s" % frac_to_str(release),
                                frac_to_str(start),
                                "task started before its release_time")
                # squad must match the shift on duty
                if first_start.get("squad_id") is not None:
                    shift = self._shift_at(start)
                    if shift is not None and first_start["squad_id"] != shift[2]:
                        self._issue("C09", "%s.squad_id" % loc, shift[2],
                                    first_start["squad_id"],
                                    "squad_id does not match the on-duty "
                                    "shift at start")
                # E prerequisite: A/B/C all PASS before an E start
                if process == "E":
                    for p in ABC:
                        p_obs = [r for r in self._log
                                 if r.get("event_type") == "OBSERVATION_MATERIALIZED"
                                 and r.get("device_id") == device_id
                                 and r.get("process") == p
                                 and r.get("outcome") == OUTCOME_PASS]
                        if not p_obs or p_obs[-1]["seq"] >= first_start["seq"]:
                            self._issue("C09", "%s.E_prereq" % loc,
                                        "A/B/C all PASS before the E start",
                                        p,
                                        "E test started before process %s "
                                        "passed (E waits for the full "
                                        "A/B/C flow)" % p)
                            break
            # release frozenness
            for rec2 in self._log:
                if rec2.get("task_id") is not None and rec2.get("task_id") == \
                        ("D%03d_%s_%d" % key) and "release_time" in rec2:
                    if self._f(rec2["release_time"], "release_time") != release:
                        self._issue("C11", "%s.release_time" % loc,
                                    frac_to_str(release),
                                    rec2.get("release_time"),
                                    "release_time rewritten across records "
                                    "(must stay frozen)")
                        break
            # cancelled semantics
            for c in cancels:
                c_elapsed = self._f(c["elapsed_hours"], "cancel.elapsed")
                if c_elapsed == 0:
                    if c.get("attempt_id") is not None:
                        self._issue("C10", "%s.cancel" % loc,
                                    "no attempt_id for a READY cancel", c["seq"],
                                    "never-started cancel must carry no "
                                    "attempt_id")
                else:
                    if c.get("attempt_id") is None:
                        self._issue("C10", "%s.cancel" % loc,
                                    "attempt_id present for a fragment cancel",
                                    None,
                                    "fragment cancel with elapsed>0 lacks "
                                    "attempt_id")
                    reason = c.get("cancel_reason")
                    if reason not in CANCEL_REASONS:
                        self._issue("C10", "%s.cancel_reason" % loc,
                                    "EQUIPMENT_FAILURE|ILLEGAL_240_INTERRUPT|"
                                    "DEVICE_EXIT", reason,
                                    "invalid cancel reason")
                    if c.get("outcome") != OUTCOME_NONE:
                        self._issue("C10", "%s.outcome" % loc, OUTCOME_NONE,
                                    c.get("outcome"),
                                    "cancelled fragment must have outcome "
                                    "NONE (no observation)")
            # completed semantics
            if completed:
                complete = completes[0]
                end = self._f(complete["event_time"], "%s.complete" % loc)
                # the completing fragment is the one whose attempt_id matches
                # the ACTIVITY_COMPLETE (a failure-retried task starts more
                # than once; only the completing fragment's start is relevant)
                comp_start = None
                comp_attempt_id = complete.get("attempt_id")
                comp_attempt = self._attempts.get(comp_attempt_id) \
                    if comp_attempt_id is not None else None
                if comp_attempt is not None and comp_attempt.get("start") is not None:
                    comp_start = self._f(comp_attempt["start"]["event_time"],
                                         "completing fragment start")
                if comp_start is None:
                    self._issue("C09", "%s.completing_fragment" % loc,
                                "ACTIVITY_START matching the ACTIVITY_COMPLETE "
                                "attempt_id", "missing",
                                "completed fragment has no matching "
                                "ACTIVITY_START")
                else:
                    expected_end = comp_start + durations[process]
                    if end != expected_end:
                        self._issue("C09", "%s.finish" % loc,
                                    frac_to_str(expected_end),
                                    frac_to_str(end),
                                    "finish must equal the completing "
                                    "fragment's start + frozen duration")
                if not observations:
                    self._issue("C09", "%s.outcome" % loc,
                                "OBSERVATION_MATERIALIZED present", "missing",
                                "completed effective test has no observation")
                else:
                    obs = observations[0]
                    obs_time = self._f(obs["event_time"],
                                       "%s.observation_time" % loc)
                    if obs_time != end:
                        self._issue("C09", "%s.observation_time" % loc,
                                    frac_to_str(end), frac_to_str(obs_time),
                                    "observation must be materialized at the "
                                    "completion time")
                    if obs.get("outcome") not in (OUTCOME_PASS, OUTCOME_ABNORMAL):
                        self._issue("C09", "%s.outcome" % loc,
                                    "PASS|ABNORMAL", obs.get("outcome"),
                                    "observation outcome invalid")
            # attempt-2 release must equal the first-failure observation time
            if attempt == 2:
                first_abn = [r for r in self._log
                             if r.get("event_type") == "OBSERVATION_MATERIALIZED"
                             and r.get("device_id") == device_id
                             and r.get("process") == process
                             and r.get("effective_attempt_no") == 1
                             and r.get("outcome") == OUTCOME_ABNORMAL]
                if not first_abn:
                    self._issue("C10", "%s.attempt_2" % loc,
                                "a completed first ABNORMAL before it", 0,
                                "attempt 2 without a completed first ABNORMAL")
                else:
                    first_abn_time = self._f(first_abn[0]["event_time"],
                                             "first ABNORMAL time")
                    if release != first_abn_time:
                        self._issue("C11", "%s.attempt2_release" % loc,
                                    frac_to_str(first_abn_time),
                                    frac_to_str(release),
                                    "retest release_time must equal the first "
                                    "ABNORMAL observation time")
            # shift feasibility of every started fragment (the per-fragment
            # [start, end) shift containment is checked per attempt in
            # _check_resource_occupancy; here only the first start's shift
            # membership is verified at the task level)
            if start is not None:
                shift = self._shift_at(start)
                if shift is None:
                    self._issue("C12", "%s.start" % loc,
                                "within an active shift", frac_to_str(start),
                                "activity started outside any shift (shift gap)")
        # FCFS: per resource, ACTIVITY_START keys must be non-decreasing
        self._check_fcfs_order()

    def _check_fcfs_order(self) -> None:
        """Fixed global FCFS key (release_time, device_id, process_order,
        effective_attempt_no); per resource the start order must be
        non-decreasing in that key (no SPT/LPT/metaheuristic)."""
        release_of: dict[tuple, Fraction] = {}
        for rec in self._records_by_type.get("TASK_RELEASE", []):
            key = (rec.get("device_id"), rec.get("process"),
                   rec.get("effective_attempt_no"))
            if None in key:
                continue
            release_of[key] = self._f(rec.get("release_time"),
                                      "TASK_RELEASE.release_time")
        for resource in PROCESSES:
            seqs = []
            for rec in self._records_by_type.get("ACTIVITY_START", []):
                if rec.get("resource_id") != resource:
                    continue
                key = (rec.get("device_id"), rec.get("process"),
                       rec.get("effective_attempt_no"))
                if key not in release_of:
                    continue
                seqs.append((rec["seq"], key, rec["device_id"],
                             rec["effective_attempt_no"]))
            seqs.sort(key=lambda x: x[0])
            keys = []
            for _seq, key, device_id, attempt in seqs:
                fcfs = (
                    release_of[key], device_id,
                    PROCESS_ORDER[resource], attempt,
                )
                keys.append(fcfs)
                self._recomputed.setdefault("fcfs_keys", {})[
                    "D%03d_%s_%d" % key
                ] = [frac_to_str(k) if isinstance(k, Fraction) else k
                     for k in fcfs]
            if keys != sorted(keys):
                self._issue("C11", "resource(%s).fcfs_start_order" % resource,
                            "non-decreasing FCFS key order",
                            "violation",
                            "ACTIVITY_START order on resource %s is not "
                            "non-decreasing in the frozen FCFS key "
                            "(release_time, device_id, process_order, attempt)"
                            % resource)

    def _check_attempts(self) -> None:
        """effective_attempt_no per (device, process): 1 < 2 in seq order;
        cancelled fragments never advance the attempt."""
        if not self._structural_ok:
            return
        per_process: dict[tuple, list[dict[str, Any]]] = {}
        for rec in self._records_by_type.get("OBSERVATION_MATERIALIZED", []):
            key = (rec.get("device_id"), rec.get("process"))
            if None in key:
                continue
            per_process.setdefault(key, []).append(rec)
        for (device_id, process), obs_list in sorted(per_process.items()):
            obs_list.sort(key=lambda r: r["seq"])
            attempts = [r.get("effective_attempt_no") for r in obs_list]
            if any(a not in (1, 2) for a in attempts):
                self._issue("C10", "device(%d).%s" % (device_id, process),
                            "{1, 2}", attempts,
                            "effective_attempt_no must be 1 or 2")
            if attempts != sorted(attempts):
                self._issue("C10", "device(%d).%s" % (device_id, process),
                            "non-decreasing (1 < 2)", attempts,
                            "attempt numbers must be monotonic in seq order")

    # ------------------------------------------------------------------
    # C10/C17 devices, terminal state, D, true states, quality terms
    # ------------------------------------------------------------------

    def _check_devices_quality(self) -> None:
        """Terminal states, T, true states, D, observation chain, S/PL/PW."""
        if not self._structural_ok:
            return
        batch_size = self._cfg.batch_size
        # device set == 1..batch_size, exactly one TRUE_STATE_GENERATED each
        generated = self._records_by_type.get(EVENT_TRUE_STATE_GENERATED, [])
        if len(generated) != batch_size:
            self._issue("C17", "TRUE_STATE_GENERATED",
                        batch_size, len(generated),
                        "exactly one true-state generation per device "
                        "(created devices == batch_size)")
        seen_devices: set[int] = set()
        for rec in generated:
            device_id = rec.get("device_id")
            seen_devices.add(device_id)
        for device_id in range(1, batch_size + 1):
            if device_id not in seen_devices:
                self._issue("C17", "device(%d)" % device_id,
                            "TRUE_STATE_GENERATED present", "missing",
                            "device missing from the log")
        for device_id in range(1, batch_size + 1):
            loc = "device(%d)" % device_id
            dev = self._devices.get(device_id)
            chain = self._chains.get(device_id)
            if chain is None:
                # actual completed observations for this device (frozen
                # cancellation semantics: only EFFECTIVE completed attempts
                # consume an observation U and may drive the exit chain)
                completed: set[tuple[str, int]] = set()
                for rec in self._records_by_type.get("OBSERVATION_MATERIALIZED", []):
                    if rec.get("device_id") == device_id:
                        proc = rec.get("process")
                        att = rec.get("effective_attempt_no")
                        if proc is not None and att is not None:
                            completed.add((proc, int(att)))
                chain = derive_device_chain(
                    self._cfg, self._params, device_id, completed
                )
                self._chains[device_id] = chain
            if dev is None or dev["terminal_state"] is None:
                self._issue("C10", loc, "DEVICE_TERMINAL present", "missing",
                            "device has no terminal state at SIMULATION_END")
                continue
            if dev["terminal_count"] > 1:
                self._issue("C10", loc, "exactly one DEVICE_TERMINAL",
                            dev["terminal_count"],
                            "device terminal recorded more than once")
            terminal = dev["terminal_state"]
            if terminal == TERMINAL_PASSED:
                if dev["terminal_reason"] is not None:
                    self._issue("C10", "%s.terminal_reason" % loc, None,
                                dev["terminal_reason"],
                                "PASSED terminal_reason must be null")
            elif terminal == TERMINAL_EXITED:
                if dev["terminal_reason"] != TERMINAL_REASON_SECOND_ABNORMAL:
                    self._issue("C10", "%s.terminal_reason" % loc,
                                TERMINAL_REASON_SECOND_ABNORMAL,
                                dev["terminal_reason"],
                                "EXITED terminal_reason must be "
                                "process_second_abnormal")
                if dev["exit_seq"] is None:
                    self._issue("C10", loc, "DEVICE_EXIT present", "missing",
                                "EXITED device has no DEVICE_EXIT record")
            else:
                self._issue("C10", loc, "PASSED|EXITED", terminal,
                            "invalid terminal_state")
                continue
            # canonical chain comparison
            if terminal != chain.terminal:
                self._issue("C17", "%s.terminal_state" % loc, chain.terminal,
                            terminal,
                            "terminal state contradicts the canonical world "
                            "recomputed from the key schema")
            # true state
            if dev["true_state"] is not None:
                for p in ABC:
                    recorded = dev["true_state"].get(p)
                    expected = chain.true_abc[p]
                    if recorded is not None and bool(recorded) != expected:
                        self._issue("C17", "%s.true_state.%s" % (loc, p),
                                    expected, recorded,
                                    "true state contradicts U_X < q_p in the "
                                    "canonical world")
            # D
            if chain.d_value != D_NOT_CREATED:
                if dev["d_count"] != 1:
                    self._issue("C09", "%s.D" % loc,
                                "exactly 1 D_CREATED (E-eligible)", dev["d_count"],
                                "E-eligible device must materialize D exactly "
                                "once (an E retest must never regenerate D)")
                elif dev["d_state"] != chain.d_value:
                    self._issue("C09", "%s.d_state" % loc, chain.d_value,
                                dev["d_state"],
                                "D_CREATED d_state contradicts U_D < q_D in "
                                "the canonical world")
            else:
                if dev["d_count"] > 0:
                    self._issue("C09", "%s.D" % loc, "no D_CREATED "
                               "(early exit never materializes D)",
                                dev["d_count"],
                                "device that never became E-eligible must "
                                "not generate D (no anti-factual D)")
            # DEVICE_EXIT process set must match the chain's exit processes
            exit_recs = [r for r in self._records_by_type.get("DEVICE_EXIT", [])
                         if r.get("device_id") == device_id]
            for er in exit_recs:
                recorded_set = set((er.get("process") or "").split(",")) \
                    if er.get("process") else set()
                recorded_set = {p for p in recorded_set if p}
                if recorded_set and recorded_set != set(chain.exit_processes):
                    self._issue("C10", "%s.DEVICE_EXIT.process" % loc,
                                ",".join(sorted(chain.exit_processes)),
                                er.get("process"),
                                "DEVICE_EXIT process set does not match the "
                                "canonical exit chain")
        # observations vs canonical chain
        self._check_observations_chain()
        # S / PL / PW
        passed: list[int] = []
        exited: list[int] = []
        for device_id in range(1, batch_size + 1):
            chain = self._chains.get(device_id)
            dev = self._devices.get(device_id, {})
            terminal = dev.get("terminal_state")
            if chain is None:
                continue
            if terminal == TERMINAL_PASSED:
                passed.append(device_id)
            elif terminal == TERMINAL_EXITED:
                exited.append(device_id)

        def generated_problems(device_id: int) -> list[str]:
            chain = self._chains[device_id]
            problems = [p for p in ABC if chain.true_abc[p]]
            if chain.d_value == D_PROBLEM:
                problems.append("D")
            return problems

        pl = sum(1 for d in passed if generated_problems(d))
        pw = sum(1 for d in exited if not generated_problems(d))
        self._recomputed["S"] = len(passed)
        self._recomputed["exited"] = len(exited)
        self._recomputed["PL"] = pl
        self._recomputed["PW"] = pw

    def _check_observations_chain(self) -> None:
        """Every DES-materialized observation must lie in the canonical
        absorption chain and match its recomputed outcome; PASSED devices
        consume the whole chain; EXITED devices consume a subset."""
        for device_id in range(1, self._cfg.batch_size + 1):
            chain = self._chains.get(device_id)
            if chain is None:
                continue
            consumed: dict[tuple[str, int], str] = {}
            for rec in self._records_by_type.get("OBSERVATION_MATERIALIZED", []):
                if rec.get("device_id") != device_id:
                    continue
                key = (rec.get("process"), rec.get("effective_attempt_no"))
                if key in consumed:
                    self._issue("C17", "device(%d).observation.%s"
                                % (device_id, key), "at most one per "
                                "(process, attempt)", key,
                                "duplicate observation for the same keyed U_Y")
                consumed[key] = rec.get("outcome")
            for key, outcome in sorted(consumed.items()):
                if key not in chain.expected_observations:
                    self._issue("C17", "device(%d).observation.%s,%d"
                                % (device_id, key[0], key[1]),
                                "inside the canonical absorption chain",
                                "outside",
                                "observation consumed outside the canonical "
                                "absorption chain (interruptions/cancellations "
                                "must never consume observation U)")
                    continue
                canonical = chain.expected_observations[key]
                if outcome != canonical:
                    self._issue("C17", "device(%d).observation.%s,%d"
                                % (device_id, key[0], key[1]), canonical,
                                outcome,
                                "observation outcome contradicts the canonical "
                                "world (U_Y applied to the frozen kernel)")
            if chain.terminal == TERMINAL_PASSED:
                missing = sorted(set(chain.expected_observations) - set(consumed))
                if missing:
                    self._issue("C17", "device(%d).chain" % device_id,
                                "full canonical observation band", missing,
                                "PASSED device is missing canonical "
                                "observations")

    def _check_recorded_u(self) -> None:
        """对拍 of the DES's recorded derived values: every ``u`` / ``u_key``
        / ``true_state`` / ``d_state`` field must equal the value the checker
        independently recomputes from ``g3.key_schema_v1`` in the same
        canonical world (the expected side is always derived, never copied
        from the log)."""
        if not self._structural_ok:
            return
        ns = self._cfg.namespace
        rep = self._cfg.replicate_id
        seed = self._cfg.master_seed

        def u_matches(recorded: Any, expected: Fraction,
                      loc: str, field: str) -> None:
            if recorded is None:
                return
            try:
                recorded_f = self._f(recorded, loc)
            except ReplayCheckerInputError as exc:
                self._issue("C17", "%s.%s" % (loc, field),
                            frac_to_str(expected), recorded,
                            "recorded U is not a valid exact rational: %s"
                            % exc)
                return
            if recorded_f != expected:
                self._issue("C17", "%s.%s" % (loc, field),
                            frac_to_str(expected), recorded,
                            "recorded U does not match the canonical world")

        for rec in self._records_by_type.get(EVENT_TRUE_STATE_GENERATED, []):
            device_id = rec.get("device_id")
            loc = "TRUE_STATE_GENERATED.device(%d)" % device_id
            u_rec = rec.get("u")
            u_keys_rec = rec.get("u_keys")
            if not isinstance(u_rec, dict) or not isinstance(u_keys_rec, dict):
                self._issue("C17", loc, "object u/u_keys per subsystem",
                            (type(u_rec).__name__, type(u_keys_rec).__name__),
                            "TRUE_STATE_GENERATED u/u_keys must be objects")
                continue
            for sub in ABC:
                expected_u = ks.u_x(ns, rep, device_id, sub, seed)
                u_matches(u_rec.get(sub), expected_u, loc, "u.%s" % sub)
                expected_key = ks.canonical_key(ns, rep, device_id, sub, None, seed)
                recorded_key = u_keys_rec.get(sub)
                if recorded_key is not None and recorded_key != expected_key:
                    self._issue("C17", "%s.u_key.%s" % (loc, sub),
                                expected_key, recorded_key,
                                "recorded U_X key does not match the "
                                "canonical key")
        for rec in self._records_by_type.get("D_CREATED", []):
            device_id = rec.get("device_id")
            loc = "D_CREATED.device(%d)" % device_id
            u_matches(rec.get("u"), ks.u_d(ns, rep, device_id, seed), loc, "u")
            expected_key = ks.canonical_key(ns, rep, device_id, None, None, seed)
            if rec.get("u_key") is not None and rec["u_key"] != expected_key:
                self._issue("C17", "%s.u_key" % loc, expected_key,
                            rec.get("u_key"),
                            "recorded U_D key does not match the canonical key")
        for rec in self._records_by_type.get("OBSERVATION_MATERIALIZED", []):
            device_id = rec.get("device_id")
            process = rec.get("process")
            attempt = rec.get("effective_attempt_no")
            loc = "OBSERVATION.device(%d).%s,%d" % (device_id, process, attempt)
            u_matches(rec.get("u"),
                      ks.u_y(ns, rep, device_id, process, attempt, seed),
                      loc, "u")
            expected_key = ks.canonical_key(
                ns, rep, device_id, process, attempt, seed)
            if rec.get("u_key") is not None and rec["u_key"] != expected_key:
                self._issue("C17", "%s.u_key" % loc, expected_key,
                            rec.get("u_key"),
                            "recorded U_Y key does not match the canonical key")

    def _check_d_timing(self) -> None:
        """E2: D is created exactly once, at the A/B/C all-PASS timestamp, at
        the E initial TASK_RELEASE timestamp (D_CREATED.seq < TASK_RELEASE(E).seq),
        never at the E ACTIVITY_START, never regenerated by an E retest."""
        if not self._structural_ok:
            return
        for device_id in range(1, self._cfg.batch_size + 1):
            loc = "device(%d).D" % device_id
            d_recs = [r for r in self._records_by_type.get("D_CREATED", [])
                      if r.get("device_id") == device_id]
            e_rel = [r for r in self._records_by_type.get("TASK_RELEASE", [])
                     if r.get("device_id") == device_id
                     and r.get("process") == "E"
                     and r.get("effective_attempt_no") == 1]
            if e_rel:
                if len(d_recs) != 1:
                    continue  # already reported in _check_devices_quality
                d = d_recs[0]
                d_time = self._f(d["event_time"], "D_CREATED.event_time")
                e_time = self._f(e_rel[0]["event_time"],
                                 "E TASK_RELEASE.event_time")
                if d_time != e_time:
                    self._issue("C09", "%s.timing" % loc,
                                frac_to_str(e_time), frac_to_str(d_time),
                                "D_CREATED must share the E initial "
                                "TASK_RELEASE timestamp")
                if d.get("seq") >= e_rel[0].get("seq"):
                    self._issue("C09", "%s.seq_order" % loc,
                                "D_CREATED.seq < TASK_RELEASE(E).seq",
                                (d.get("seq"), e_rel[0].get("seq")),
                                "E2 (D) must precede F (E release) at the "
                                "same timestamp")
            # D must never be created at an E ACTIVITY_START timestamp unless
            # that timestamp also carries the E release
            e_starts = [r for r in self._records_by_type.get("ACTIVITY_START", [])
                        if r.get("device_id") == device_id
                        and r.get("process") == "E"]
            for est in e_starts:
                t = self._f(est["event_time"], "E.start")
                for d in d_recs:
                    if self._f(d["event_time"], "D_CREATED.event_time") == t \
                            and (not e_rel
                                 or self._f(e_rel[0]["event_time"], "E.rel") != t):
                        self._issue("C09", "%s.e_start_d" % loc,
                                    "no D at E ACTIVITY_START", frac_to_str(t),
                                    "D must not be generated at the E "
                                    "ACTIVITY_START timestamp")

    # ------------------------------------------------------------------
    # C12 turnover phases
    # ------------------------------------------------------------------

    def _check_turnovers(self) -> None:
        """Turnover event ordering, durations and the 0.5h_overlap folding
        rule."""
        if not self._structural_ok:
            return
        profile = self._cfg.turnover_profile
        out_h = self._cfg.transport_out_h
        in_h = self._cfg.transport_in_h
        by_bay: dict[int, list[dict[str, Any]]] = {}
        for tv in self._turnovers:
            by_bay.setdefault(tv["bay_id"], []).append(tv)
        for bay_id in sorted(by_bay):
            events = by_bay[bay_id]
            loc = "turnover.bay(%d)" % bay_id
            out_starts = [e for e in events if e["event_type"] == "TURNOVER_OUT_START"]
            out_completes = [e for e in events if e["event_type"] == "TURNOVER_OUT_COMPLETE"]
            in_starts = [e for e in events if e["event_type"] == "TURNOVER_IN_START"]
            in_completes = [e for e in events if e["event_type"] == "TURNOVER_IN_COMPLETE"]
            if not (len(out_starts) == len(out_completes)
                    == len(in_starts) == len(in_completes)):
                self._issue("C12", loc, "equal counts of OUT/IN phases",
                            (len(out_starts), len(out_completes),
                             len(in_starts), len(in_completes)),
                            "unbalanced turnover phases")
                continue
            for i in range(len(out_starts)):
                os_ = out_starts[i]["time"]
                oc = out_completes[i]["time"]
                is_ = in_starts[i]["time"]
                ic = in_completes[i]["time"]
                tloc = "%s[%d]" % (loc, i)
                if os_ >= oc:
                    self._issue("C12", tloc, "OUT_START < OUT_COMPLETE",
                                (frac_to_str(os_), frac_to_str(oc)),
                                "out phase not strictly increasing")
                if oc != is_:
                    self._issue("C12", tloc, "OUT_COMPLETE == IN_START",
                                (frac_to_str(oc), frac_to_str(is_)),
                                "turnover out and in phases must be contiguous")
                if profile == "0.5h_overlap":
                    if is_ != ic:
                        self._issue("C12", tloc,
                                    "IN_START == IN_COMPLETE (zero-duration "
                                    "IN log rep.)",
                                    (frac_to_str(is_), frac_to_str(ic)),
                                    "0.5h_overlap must record the IN phases "
                                    "at one timestamp")
                    if oc - os_ != out_h:
                        self._issue("C12", "%s.physical_duration" % tloc,
                                    frac_to_str(out_h), frac_to_str(oc - os_),
                                    "0.5h_overlap physical turnover occupancy "
                                    "must be transport_out_h")
                else:
                    if ic <= is_:
                        self._issue("C12", tloc, "IN_START < IN_COMPLETE",
                                    (frac_to_str(is_), frac_to_str(ic)),
                                    "in phase not strictly increasing")
                    if oc - os_ != out_h:
                        self._issue("C12", "%s.out_duration" % tloc,
                                    frac_to_str(out_h), frac_to_str(oc - os_),
                                    "OUT phase duration mismatch (P014)")
                    if ic - is_ != in_h:
                        self._issue("C12", "%s.in_duration" % tloc,
                                    frac_to_str(in_h), frac_to_str(ic - is_),
                                    "IN phase duration mismatch (P015)")
            for out_start in out_starts:
                departed = out_start.get("device_id")
                if departed is not None and departed == self._cfg.batch_size:
                    self._issue("C12", "%s.last_device" % loc,
                                "no turnover for the last device", departed,
                                "the last device must not be transported out")

    # ------------------------------------------------------------------
    # C12 bay coverage [0, T)
    # ------------------------------------------------------------------

    def _check_bay_coverage(self) -> None:
        """Bay occupancy: per bay, device residency intervals + physical
        turnover intervals must tile [0, T) without gaps or overlaps; the
        0.5h_overlap IN representation is folded (never double counted)."""
        if not self._structural_ok:
            return
        T = self._T
        if T is None:
            return
        preloaded = list(self._cfg.preloaded_devices)
        entry: dict[int, tuple[int, Fraction]] = {}
        for idx, device_id in enumerate(preloaded):
            entry[device_id] = (idx + 1, Fraction(0))
        next_device = len(preloaded) + 1
        for tv in sorted(self._turnovers, key=lambda x: x["seq"]):
            if tv["event_type"] != "TURNOVER_IN_COMPLETE":
                continue
            if next_device > self._cfg.batch_size:
                self._issue("C12", "turnover_in", "device <= batch_size",
                            next_device,
                            "turnover-in without a next device (empty "
                            "transport-in)")
                continue
            entry[next_device] = (tv["bay_id"], tv["time"])
            next_device += 1
        residency_end: dict[int, Fraction] = {}
        for device_id in range(1, self._cfg.batch_size + 1):
            residency_end[device_id] = T
        for tv in self._turnovers:
            if tv["event_type"] == "TURNOVER_OUT_START" \
                    and tv.get("device_id") is not None:
                residency_end[tv["device_id"]] = tv["time"]
        turnover_physical: dict[int, list[tuple[Fraction, Fraction]]] = {
            b: [] for b in BAY_IDS
        }
        profile = self._cfg.turnover_profile
        # pair the i-th OUT_START with the i-th OUT_COMPLETE / IN_START /
        # IN_COMPLETE per bay (a bay can host several turnover cycles, e.g.
        # dev1 -> dev3 -> dev5 ...; never pair across cycles with next()).
        phases: dict[int, dict[str, list[dict[str, Any]]]] = {
            b: {"out_start": [], "out_complete": [],
                "in_start": [], "in_complete": []} for b in BAY_IDS
        }
        _phase_key = {
            "TURNOVER_OUT_START": "out_start",
            "TURNOVER_OUT_COMPLETE": "out_complete",
            "TURNOVER_IN_START": "in_start",
            "TURNOVER_IN_COMPLETE": "in_complete",
        }
        for tv in self._turnovers:
            key = _phase_key.get(tv["event_type"])
            if tv["bay_id"] in phases and key is not None:
                phases[tv["bay_id"]][key].append(tv)
        for bay_id in BAY_IDS:
            os_list = phases[bay_id]["out_start"]
            oc_list = phases[bay_id]["out_complete"]
            is_list = phases[bay_id]["in_start"]
            ic_list = phases[bay_id]["in_complete"]
            n = min(len(os_list), len(oc_list), len(is_list), len(ic_list))
            for i in range(n):
                os_ = os_list[i]["time"]
                oc = oc_list[i]["time"]
                if profile == "0.5h_overlap":
                    turnover_physical[bay_id].append((os_, oc))
                else:
                    turnover_physical[bay_id].append((os_, oc))
                    turnover_physical[bay_id].append(
                        (is_list[i]["time"], ic_list[i]["time"]))
        for bay_id in BAY_IDS:
            bay_devices = sorted(d for d, (b, _t) in entry.items() if b == bay_id)
            if not bay_devices:
                bay_recs = [r for r in self._log if r.get("bay_id") == bay_id]
                if bay_recs:
                    self._issue("C12", "bay(%d)" % bay_id,
                                "no events (EMPTY bay)", len(bay_recs),
                                "EMPTY bay must not carry any event")
                continue
            intervals: list[tuple[Fraction, Fraction]] = []
            for device_id in bay_devices:
                _b, entry_t = entry[device_id]
                intervals.append((entry_t, residency_end[device_id]))
            for iv in turnover_physical[bay_id]:
                intervals.append(iv)
            intervals.sort(key=lambda iv: (iv[0], iv[1]))
            loc = "bay(%d).coverage" % bay_id
            merged: list[tuple[Fraction, Fraction]] = []
            for start, end in intervals:
                if end <= start:
                    self._issue("C12", loc, "end > start",
                                (frac_to_str(start), frac_to_str(end)),
                                "zero/negative bay interval")
                    continue
                if merged and start < merged[-1][1]:
                    self._issue("C12", loc, "non-overlapping intervals",
                                (frac_to_str(start), frac_to_str(merged[-1][1])),
                                "bay occupancy intervals overlap")
                    continue
                if merged and start != merged[-1][1]:
                    self._issue("C12", loc,
                                "gapless (prev_end == next_start)",
                                (frac_to_str(merged[-1][1]), frac_to_str(start)),
                                "bay occupancy has a gap")
                    continue
                merged.append((start, end))
            if merged:
                if merged[0][0] != Fraction(0):
                    self._issue("C12", loc, "coverage starts at 0",
                                frac_to_str(merged[0][0]),
                                "bay occupancy does not start at t=0")
                if merged[-1][1] != T:
                    self._issue("C12", loc,
                                "coverage ends at T (%s)" % frac_to_str(T),
                                frac_to_str(merged[-1][1]),
                                "bay occupancy does not cover [0, T)")
            # no test activity during a physical turnover interval
            for iv in turnover_physical[bay_id]:
                for rec in self._records_by_type.get("ACTIVITY_START", []):
                    if rec.get("bay_id") != bay_id:
                        continue
                    t = self._f(rec["event_time"], "ACTIVITY_START.event_time")
                    if iv[0] <= t < iv[1]:
                        self._issue("C12", "bay(%d).test_during_turnover"
                                    % bay_id, "no test on bay during turnover",
                                    frac_to_str(t),
                                    "test started on a bay inside a physical "
                                    "turnover interval")
                        break
            self._recomputed.setdefault("bay_coverage", {})[str(bay_id)] = {
                "intervals": [[frac_to_str(s), frac_to_str(e)]
                              for s, e in merged],
                "gapless": True,
            }
        # device bay/entry consistency vs TRUE_STATE_GENERATED
        for device_id in range(1, self._cfg.batch_size + 1):
            if device_id not in entry:
                continue
            bay_id, entry_t = entry[device_id]
            dev = self._devices.get(device_id, {})
            if dev.get("bay_id") is not None and dev["bay_id"] != bay_id:
                self._issue("C09", "device(%d).bay" % device_id, bay_id,
                            dev["bay_id"],
                            "device bay_id inconsistent across its records")
            if dev.get("entry_time") is not None \
                    and dev["entry_time"] != entry_t:
                self._issue("C09", "device(%d).entry_time" % device_id,
                            frac_to_str(entry_t), frac_to_str(dev["entry_time"]),
                            "TRUE_STATE_GENERATED entry_time disagrees with "
                            "the preload/turnover-in timeline")
            initials = [r for r in self._records_by_type.get("TASK_RELEASE", [])
                        if r.get("device_id") == device_id
                        and r.get("process") in ABC
                        and r.get("effective_attempt_no") == 1]
            for rec in initials:
                rel_t = self._f(rec.get("release_time"), "initial release")
                if rel_t != entry_t:
                    self._issue("C09", "device(%d).entry_time" % device_id,
                                frac_to_str(entry_t), frac_to_str(rel_t),
                                "initial A/B/C release_time must equal the "
                                "device entry time")
                    break

    # ------------------------------------------------------------------
    # C09/C17 resource occupancy (test + calibration) over [0, T)
    # ------------------------------------------------------------------

    def _check_resource_occupancy(self) -> None:
        """Per resource: capacity-1 BUSY intervals (test fragments AND
        calibration downtime) must be pairwise disjoint, within [0, T) and
        within a single shift; IDLE elsewhere."""
        if not self._structural_ok:
            return
        T = self._T
        busy: dict[str, list[tuple[Fraction, Fraction, str, tuple]]] = {
            r: [] for r in PROCESSES
        }
        # test fragments from the attempt views
        for attempt_id, view in sorted(self._attempts.items()):
            start_rec = view["start"]
            terminal = view["terminal"]
            if start_rec is None or terminal is None:
                continue
            resource = start_rec.get("resource_id")
            if resource not in PROCESSES:
                continue
            s = self._f(start_rec["event_time"], "ACTIVITY_START.event_time")
            e = self._f(terminal["event_time"], "terminal.event_time")
            if e > s:
                busy[resource].append((s, e, "test", (attempt_id,)))
        # calibration intervals
        for rec in self._records_by_type.get(EVENT_EQUIPMENT_REPLACEMENT_START, []):
            resource = rec.get("resource_id")
            cs = self._f(rec["calibration_start"], "calibration_start")
            ce = self._f(rec["calibration_end"], "calibration_end")
            if ce > cs:
                busy[resource].append((cs, ce, "calibration", ()))
        for resource in PROCESSES:
            intervals = busy[resource]
            intervals.sort(key=lambda iv: (iv[0], iv[1]))
            loc = "resource(%s).busy" % resource
            prev_end: Optional[Fraction] = None
            total = Fraction(0)
            for start, end, kind, _tag in intervals:
                if end <= start:
                    self._issue("C09", loc, "end > start",
                                (frac_to_str(start), frac_to_str(end)),
                                "non-positive busy interval")
                    continue
                if T is not None and end > T:
                    self._issue("C12", loc, "<= T", frac_to_str(end),
                                "busy interval ends after T")
                if prev_end is not None and start < prev_end:
                    self._issue("C09", loc, "disjoint intervals (capacity 1)",
                                (frac_to_str(start), frac_to_str(prev_end)),
                                "two activities overlap on resource %s"
                                % resource)
                total += end - start
                shift = self._shift_at(start)
                if shift is None:
                    self._issue("C12", loc,
                                "within an active shift", frac_to_str(start),
                                "%s started outside any shift (P039)"
                                % kind)
                elif end > shift[1]:
                    self._issue("C12", loc,
                                "end <= shift_end (%s)" % frac_to_str(shift[1]),
                                frac_to_str(end),
                                "%s crosses the shift boundary (P062)" % kind)
                prev_end = max(prev_end, end) if prev_end is not None else end
            self._recomputed.setdefault("resource_busy", {})[resource] = {
                "test_intervals": [
                    [frac_to_str(s), frac_to_str(e)]
                    for s, e, k, _t in intervals if k == "test"
                ],
                "calibration_intervals": [
                    [frac_to_str(s), frac_to_str(e)]
                    for s, e, k, _t in intervals if k == "calibration"
                ],
                "busy_total_h": frac_to_str(total),
            }

    # ------------------------------------------------------------------
    # C18 same-timestamp closure order + WAKE_UP
    # ------------------------------------------------------------------

    def _check_same_timestamp_order(self) -> None:
        """Frozen closure order at each timestamp (V3.1 section 10 as extended
        by G3-SPEC-V1.0 section 5): settle -> observe -> classify -> exit ->
        cancel -> D -> shift -> release -> equipment decisions -> dispatch ->
        turnovers."""
        if not self._structural_ok:
            return
        by_time: dict[Fraction, list[dict[str, Any]]] = {}
        for rec in self._log:
            t = self._f(rec["event_time"], "event_time")
            by_time.setdefault(t, []).append(rec)
        for t in sorted(by_time):
            group = by_time[t]
            group.sort(key=lambda r: r["seq"])
            loc = "order@%s" % frac_to_str(t)

            def first_last(event_type: str) -> Optional[tuple[int, int]]:
                seqs = [r["seq"] for r in group if r.get("event_type") == event_type]
                if not seqs:
                    return None
                return (min(seqs), max(seqs))

            wake = first_last("WAKE_UP")
            if wake is not None:
                if group[0].get("event_type") != "WAKE_UP":
                    self._issue("C18", loc, "WAKE_UP first at its timestamp",
                                group[0].get("event_type"),
                                "WAKE_UP must be the first record of its "
                                "timestamp")
                if not self._is_shift_boundary(t):
                    self._issue("C18", loc, "shift boundary", frac_to_str(t),
                                "WAKE_UP only at a shift boundary")

            def check_pair(a_type: str, b_type: str, note: str) -> None:
                a = first_last(a_type)
                b = first_last(b_type)
                if a is not None and b is not None and a[1] >= b[0]:
                    self._issue("C18", loc, "%s.seq < %s.seq (%s)"
                                % (a_type, b_type, note), (a[1], b[0]),
                                "%s must strictly precede %s at the same "
                                "timestamp" % (a_type, b_type))

            check_pair("ACTIVITY_COMPLETE", "OBSERVATION_MATERIALIZED",
                       "A settle -> B observe")
            check_pair("ACTIVITY_COMPLETE", EVENT_EQUIPMENT_FAILURE,
                       "settle completed loop -> failed loop")
            check_pair(EVENT_EQUIPMENT_FAILURE, "OBSERVATION_MATERIALIZED",
                       "settle failed loop -> observe")
            check_pair("ACTIVITY_COMPLETE", EVENT_EQUIPMENT_CALIBRATION_COMPLETE,
                       "settle completed loop -> calibration loop")
            check_pair(EVENT_EQUIPMENT_CALIBRATION_COMPLETE,
                       "OBSERVATION_MATERIALIZED", "settle -> observe")
            check_pair("OBSERVATION_MATERIALIZED", "DEVICE_EXIT",
                       "observe -> classify/exit")
            # DEVICE_EXIT -> DEVICE_TERMINAL is a *per-device* ordering at a
            # timestamp: several devices can exit simultaneously and their
            # EXIT/TERMINAL seqs interleave across devices, so a global
            # min/max comparison mis-pairs different devices (RED_G3_S7
            # finding B; S7 rep=9 t=465 dev56/dev57). Pair by device_id; a
            # same-device TERMINAL before EXIT is still a real defect and
            # must be caught. All other check_pair calls compare different
            # closure phases and keep the global first/last order.
            exit_seqs: dict[Any, list[int]] = {}
            term_seqs: dict[Any, list[int]] = {}
            for _rec in group:
                _et = _rec.get("event_type")
                if _et == "DEVICE_EXIT":
                    exit_seqs.setdefault(_rec.get("device_id"), []).append(
                        _rec["seq"]
                    )
                elif _et == "DEVICE_TERMINAL":
                    term_seqs.setdefault(_rec.get("device_id"), []).append(
                        _rec["seq"]
                    )
            for _dev in sorted(set(exit_seqs) & set(term_seqs)):
                _a = (min(exit_seqs[_dev]), max(exit_seqs[_dev]))
                _b = (min(term_seqs[_dev]), max(term_seqs[_dev]))
                if _a[1] >= _b[0]:
                    self._issue(
                        "C18", loc,
                        "DEVICE_EXIT.seq < DEVICE_TERMINAL.seq "
                        "(exit -> terminal, device %s)" % _dev,
                        (_a[1], _b[0]),
                        "DEVICE_EXIT must strictly precede DEVICE_TERMINAL "
                        "at the same timestamp for the same device",
                    )
            check_pair("DEVICE_TERMINAL", "TASK_CANCEL", "terminal -> cancel")
            check_pair("TASK_CANCEL", "D_CREATED", "cancel -> D")
            check_pair(EVENT_EQUIPMENT_CALIBRATION_COMPLETE, "D_CREATED",
                       "settle -> D")
            check_pair("D_CREATED", "SHIFT_CHANGE", "D -> shift change")
            check_pair("SHIFT_CHANGE", "TASK_RELEASE", "shift change -> release")
            check_pair("TASK_RELEASE", "ACTIVITY_START", "release -> dispatch")
            check_pair("TASK_RELEASE", EVENT_EQUIPMENT_REPLACEMENT_START,
                       "release -> equipment decisions")
            check_pair("TASK_RELEASE", EVENT_EQUIPMENT_REPLACEMENT_DEFERRED,
                       "release -> equipment decisions")
            check_pair(EVENT_EQUIPMENT_REPLACEMENT_START, "ACTIVITY_START",
                       "equipment decisions -> dispatch")
            check_pair(EVENT_EQUIPMENT_REPLACEMENT_DEFERRED, "ACTIVITY_START",
                       "equipment decisions -> dispatch")
            check_pair("TASK_RELEASE", "TURNOVER_OUT_START",
                       "release -> turnover start")
            check_pair("DEVICE_TERMINAL", "TURNOVER_OUT_START",
                       "terminal -> turnover start")
            check_pair(EVENT_EQUIPMENT_REPLACEMENT_START, "TURNOVER_OUT_START",
                       "equipment decisions -> turnover start")
            check_pair("ACTIVITY_START", "TURNOVER_OUT_START",
                       "dispatch -> turnover start")

    # ------------------------------------------------------------------
    # C17 ledger / YXB
    # ------------------------------------------------------------------

    def _check_ledger(self) -> None:
        """YXB / age ledger seam: per-process elapsed = sum of elapsed_hours
        over completed AND cancelled fragments; YXB_j = elapsed_j /
        (shift_count * shift_length); the resource busy ledger must equal the
        fragment totals."""
        if not self._structural_ok:
            return
        elapsed: dict[str, Fraction] = {p: Fraction(0) for p in PROCESSES}
        for rec in self._log:
            if rec.get("event_type") in ("ACTIVITY_COMPLETE", "TASK_CANCEL") \
                    and rec.get("process") in PROCESSES:
                elapsed[rec["process"]] += self._f(
                    rec.get("elapsed_hours"), "elapsed_hours")
        self._recomputed["elapsed_by_process"] = {
            p: frac_to_str(elapsed[p]) for p in PROCESSES
        }
        T = self._T
        shift_count = self._shift_count_up_to(T) if T is not None else 0
        denominator = Fraction(shift_count) * self._cfg.shift_length_h
        self._recomputed["shift_count"] = shift_count
        self._recomputed["yxb_denominator_h"] = frac_to_str(denominator)
        for proc in PROCESSES:
            if denominator == 0:
                self._recomputed["YXB_" + proc] = "NA"
            else:
                self._recomputed["YXB_" + proc] = frac_to_str(
                    elapsed[proc] / denominator)

    # ------------------------------------------------------------------
    # C13/C14 equipment replay (age / generation / lifetime / failure /
    # replacement / calibration) + C17 attempt-fragment classification
    # ------------------------------------------------------------------

    def _expected_lifetime(self, resource: str, generation: int):
        """Recompute the sampled lifetime for (resource, generation) from the
        key schema and the frozen CDF nodes (C13): the checker NEVER reads the
        DES log's recorded u for its own derivation."""
        u = ks.u_l(self._cfg.namespace, self._cfg.replicate_id, resource,
                   generation, self._cfg.master_seed)
        lifetime, censored = lr.inverse_cdf(
            u, self._params["f120"][resource], self._params["f240"][resource]
        )
        return u, lifetime, censored

    def _predict_fragment(self, a_s: Fraction, d: Fraction,
                          lifetime: Optional[Fraction],
                          is_right_censored: bool) -> tuple[str, Fraction]:
        """Fragment classification from the frozen inputs (G3-SPEC-V1.0
        section 5): illegal-crossing backstop first, then random failure
        strictly before the end, else completion (failure exactly at the end
        settles as a completion)."""
        if a_s + d > lr.MANDATORY_REPLACE_AGE_H:
            return ("illegal", lr.MANDATORY_REPLACE_AGE_H - a_s)
        if not is_right_censored and lifetime is not None \
                and a_s < lifetime < a_s + d:
            return ("failed", lifetime - a_s)
        return ("complete", d)

    def _check_equipment_and_fragments(self) -> None:
        """Replay the equipment layer and every test fragment from the log,
        verifying each recorded age/generation/lifetime/failure/replacement/
        calibration anchor against the independently recomputed state."""
        if not self._structural_ok:
            return
        mandatory_age = self._params["mandatory_age_h"]
        min_preventive = self._params["min_preventive_age_h"]
        tau_pm = self._cfg.tau_pm
        tau_is_no_pm = tau_pm is lr.NO_PM_BEFORE_MANDATORY

        equip: dict[str, dict[str, Any]] = {}
        for r in PROCESSES:
            u, lifetime, censored = self._expected_lifetime(r, 1)
            equip[r] = {
                "generation": 1,
                "age": Fraction(0),
                "lifetime": lifetime,
                "is_right_censored": censored,
                "u": u,
                "replacement_count": 0,
                "preventive_count": 0,
                "failure_count": 0,
                "calibration_count": 0,
                "available": True,
                "calibration_in_flight": False,
                "calibration_start": None,
                "deferral_emitted": False,
                "deferral_count": 0,
                "max_generation": 1,
            }
        open_attempts: dict[str, dict[str, Any]] = {}
        closed_attempts: dict[str, dict[str, Any]] = {}
        failure_records_by_resource: dict[str, list[dict[str, Any]]] = {
            r: [] for r in PROCESSES
        }
        illegal_cancels_by_resource: dict[str, list[dict[str, Any]]] = {
            r: [] for r in PROCESSES
        }
        for rec in self._log:
            et = rec.get("event_type")
            r = rec.get("resource_id")
            if r not in PROCESSES:
                continue
            if et == EVENT_EQUIPMENT_FAILURE:
                failure_records_by_resource[r].append(rec)
            if et == "TASK_CANCEL" \
                    and rec.get("cancel_reason") == CANCEL_REASON_ILLEGAL_240_INTERRUPT:
                illegal_cancels_by_resource[r].append(rec)

        def any_failure_at_age(resource: str, age: Fraction) -> bool:
            """True iff an EQUIPMENT_FAILURE record exists for ``resource``
            with exactly the given failure age (deferral-robust: the failure
            may precede the replacement start across a shift boundary)."""
            for rec in failure_records_by_resource[resource]:
                if self._f(rec["equipment_age_at_failure"],
                           "failure age") == age:
                    return True
            return False

        for rec in self._log:
            et = rec.get("event_type")
            t = self._f(rec["event_time"], "event_time")
            if et == "ACTIVITY_START":
                r = rec.get("resource_id")
                st = equip[r]
                a_s = self._f(rec["equipment_age_at_start"],
                              "equipment_age_at_start")
                gen = rec.get("equipment_generation")
                if gen != st["generation"]:
                    self._issue("C14", "equipment(%s).generation@%s"
                                % (r, frac_to_str(t)), st["generation"], gen,
                                "equipment_generation at ACTIVITY_START does "
                                "not match the replayed generation")
                if a_s != st["age"]:
                    self._issue("C14", "equipment(%s).age_at_start@%s"
                                % (r, frac_to_str(t)), frac_to_str(st["age"]),
                                frac_to_str(a_s),
                                "equipment_age_at_start does not match the "
                                "replayed age (age must be recomputed from "
                                "fragment elapsed hours)")
                attempt_id = rec.get("attempt_id")
                d = self._cfg.durations[r]
                if attempt_id in open_attempts:
                    self._issue("C17", "attempt(%s)" % attempt_id,
                                "one ACTIVITY_START", "duplicate",
                                "attempt started more than once")
                if not st["available"]:
                    self._issue("C14", "equipment(%s).start@%s" % (r, frac_to_str(t)),
                                "available equipment", "unavailable",
                                "task started while the equipment was "
                                "unavailable (replacement pending or "
                                "calibrating)")
                pred_kind, pred_duration = self._predict_fragment(
                    a_s, d, st["lifetime"], st["is_right_censored"]
                )
                if not st["is_right_censored"] and st["lifetime"] is not None \
                        and st["lifetime"] <= a_s:
                    self._issue("C14", "equipment(%s).lifetime@%s"
                                % (r, frac_to_str(t)),
                                "> a_start (%s)" % frac_to_str(a_s),
                                frac_to_str(st["lifetime"]),
                                "sampled lifetime not after the current age "
                                "(the device should already have failed)")
                start_t = t
                attempt_end = self._f(rec["attempt_end_time"],
                                      "ACTIVITY_START.attempt_end_time")
                expected_end = start_t + pred_duration
                if attempt_end != expected_end:
                    self._issue("C14", "attempt(%s).scheduled_end" % attempt_id,
                                frac_to_str(expected_end),
                                frac_to_str(attempt_end),
                                "ACTIVITY_START attempt_end_time must equal "
                                "start + the frozen fragment duration "
                                "(complete/failed/illegal)")
                open_attempts[attempt_id] = {
                    "start_rec": rec,
                    "resource": r,
                    "a_s": a_s,
                    "d": d,
                    "predicted_kind": pred_kind,
                    "predicted_duration": pred_duration,
                    "task_key": (rec.get("device_id"), rec.get("process"),
                                 rec.get("effective_attempt_no")),
                }
            elif et in ("ACTIVITY_COMPLETE", "TASK_CANCEL"):
                attempt_id = rec.get("attempt_id")
                if attempt_id is None:
                    # READY cancel (never-started task): no fragment
                    if et != "TASK_CANCEL":
                        self._issue("C17", "record[%s]" % rec.get("seq"),
                                    "attempt_id", None,
                                    "ACTIVITY_COMPLETE without attempt_id")
                    continue
                entry = open_attempts.pop(attempt_id, None)
                if entry is None:
                    self._issue("C17", "attempt(%s)" % attempt_id,
                                "open fragment", "missing",
                                "terminal record without a matching "
                                "ACTIVITY_START")
                    continue
                r = entry["resource"]
                st = equip[r]
                elapsed = self._f(rec["elapsed_hours"], "elapsed_hours")
                start_t = self._f(entry["start_rec"]["event_time"],
                                  "fragment start")
                end_t = t
                if end_t != start_t + elapsed:
                    self._issue("C10", "attempt(%s).time" % attempt_id,
                                frac_to_str(start_t + elapsed),
                                frac_to_str(end_t),
                                "terminal time must equal start + elapsed")
                if rec.get("attempt_end_time") is not None \
                        and self._f(rec["attempt_end_time"],
                                    "attempt_end_time") != end_t:
                    self._issue("C09", "attempt(%s).attempt_end_time"
                                % attempt_id, frac_to_str(end_t),
                                rec.get("attempt_end_time"),
                                "terminal attempt_end_time != event_time")
                st["age"] += elapsed
                closed_attempts[attempt_id] = {
                    "attempt_id": attempt_id,
                    "resource": r,
                    "a_s": entry["a_s"],
                    "d": entry["d"],
                    "predicted_kind": entry["predicted_kind"],
                    "predicted_duration": entry["predicted_duration"],
                    "elapsed": elapsed,
                    "task_key": entry["task_key"],
                    "terminal_type": et,
                    "terminal_time": end_t,
                    "start_rec": entry["start_rec"],
                }
                pred = entry["predicted_kind"]
                if et == "ACTIVITY_COMPLETE":
                    if pred != "complete":
                        self._issue("C14", "attempt(%s).fragment" % attempt_id,
                                    "interrupted (predicted %s, duration %s)"
                                    % (pred, frac_to_str(entry["predicted_duration"])),
                                    "completed",
                                    "fragment completed although the sampled "
                                    "lifetime/240 rule predicts an "
                                    "interruption")
                    if elapsed != entry["d"]:
                        self._issue("C09", "attempt(%s).elapsed" % attempt_id,
                                    frac_to_str(entry["d"]),
                                    frac_to_str(elapsed),
                                    "completed fragment elapsed_hours must "
                                    "equal the frozen duration")
                    if self._f(rec["equipment_age_at_end"],
                               "equipment_age_at_end") != st["age"]:
                        self._issue("C14", "attempt(%s).age_at_end" % attempt_id,
                                    frac_to_str(st["age"]),
                                    rec.get("equipment_age_at_end"),
                                    "equipment_age_at_end does not match the "
                                    "replayed age")
                    if rec.get("equipment_generation") != st["generation"]:
                        self._issue("C14", "attempt(%s).generation" % attempt_id,
                                    st["generation"],
                                    rec.get("equipment_generation"),
                                    "equipment_generation at completion does "
                                    "not match the replayed generation")
                else:  # TASK_CANCEL
                    reason = rec.get("cancel_reason")
                    if elapsed == 0:
                        self._issue("C10", "attempt(%s).cancel" % attempt_id,
                                    "elapsed > 0 for a started fragment",
                                    "0",
                                    "started fragment cancelled with zero "
                                    "elapsed")
                    elif reason == CANCEL_REASON_EQUIPMENT_FAILURE:
                        if pred != "failed":
                            self._issue("C14", "attempt(%s).fragment"
                                        % attempt_id,
                                        "complete (lifetime %s not inside "
                                        "(a_start, a_start+d))"
                                        % (frac_to_str(st["lifetime"])
                                           if st["lifetime"] is not None else "None"),
                                        "EQUIPMENT_FAILURE cancel",
                                        "fragment interrupted by equipment "
                                        "failure although the sampled "
                                        "lifetime does not fall strictly "
                                        "inside the fragment")
                        if elapsed != entry["predicted_duration"]:
                            self._issue("C14", "attempt(%s).failure_elapsed"
                                        % attempt_id,
                                        frac_to_str(entry["predicted_duration"]),
                                        frac_to_str(elapsed),
                                        "failed fragment elapsed must equal "
                                        "lifetime - a_start (the fragment "
                                        "counts age/YXB up to the sampled "
                                        "failure age)")
                    elif reason == CANCEL_REASON_ILLEGAL_240_INTERRUPT:
                        if pred != "illegal":
                            self._issue("C14", "attempt(%s).fragment"
                                        % attempt_id,
                                        "a_start + d <= 240", "illegal-240 "
                                        "interrupt",
                                        "illegal-crossing backstop fired "
                                        "although a_start + d <= 240")
                        if elapsed != entry["predicted_duration"]:
                            self._issue("C14", "attempt(%s).illegal_elapsed"
                                        % attempt_id,
                                        frac_to_str(entry["predicted_duration"]),
                                        frac_to_str(elapsed),
                                        "illegal-240 fragment elapsed must "
                                        "equal 240 - a_start")
                    elif reason == CANCEL_REASON_DEVICE_EXIT:
                        if elapsed >= entry["predicted_duration"]:
                            self._issue("C10", "attempt(%s).device_exit"
                                        % attempt_id,
                                        "elapsed < predicted fragment duration "
                                        "(%s)" % frac_to_str(entry["predicted_duration"]),
                                        frac_to_str(elapsed),
                                        "device-exit cancellation must occur "
                                        "strictly before the fragment's "
                                        "predicted end (completions/failures "
                                        "settle first at the same instant)")
                    else:
                        self._issue("C10", "attempt(%s).cancel_reason"
                                    % attempt_id, "EQUIPMENT_FAILURE|"
                                    "ILLEGAL_240_INTERRUPT|DEVICE_EXIT",
                                    reason, "invalid cancel reason")
            elif et == EVENT_EQUIPMENT_FAILURE:
                r = rec.get("resource_id")
                st = equip[r]
                if rec.get("equipment_generation") != st["generation"]:
                    self._issue("C14", "equipment(%s).failure_generation"
                                % r, st["generation"],
                                rec.get("equipment_generation"),
                                "equipment_generation at failure does not "
                                "match the replayed generation")
                fail_age = self._f(rec["equipment_age_at_failure"],
                                   "equipment_age_at_failure")
                if fail_age != st["age"]:
                    self._issue("C14", "equipment(%s).failure_age" % r,
                                frac_to_str(st["age"]), frac_to_str(fail_age),
                                "equipment_age_at_failure does not match the "
                                "replayed age (fragment elapsed must count "
                                "towards age)")
                if st["is_right_censored"] or st["lifetime"] is None:
                    self._issue("C13", "equipment(%s).failure" % r,
                                "uncensored generation with a sampled "
                                "lifetime <= 240 h", "right-censored",
                                "EQUIPMENT_FAILURE on a right-censored "
                                "generation (lifetime > 240 h never fails "
                                "inside the model horizon)")
                elif fail_age != st["lifetime"]:
                    self._issue("C13", "equipment(%s).failure_age" % r,
                                frac_to_str(st["lifetime"]),
                                frac_to_str(fail_age),
                                "failure age must equal the independently "
                                "recomputed sampled lifetime "
                                "(U_L inverse CDF)")
                st["failure_count"] += 1
                # the paired fragment must be the closed failed attempt
                attempt_id = rec.get("attempt_id")
                closed = closed_attempts.get(attempt_id)
                if closed is None or closed["predicted_kind"] != "failed":
                    self._issue("C14", "equipment(%s).failure_pair" % r,
                                "a failed fragment at the same instant",
                                attempt_id,
                                "EQUIPMENT_FAILURE without a matching failed "
                                "fragment (TASK_CANCEL EQUIPMENT_FAILURE)")
                else:
                    start_rec = closed.get("start_rec")
                    if start_rec is not None:
                        start_t = self._f(start_rec["event_time"],
                                          "fragment start")
                        if self._f(rec["fragment_start"], "fragment_start") != start_t:
                            self._issue("C14", "equipment(%s).failure_fragment"
                                        % r, frac_to_str(start_t),
                                        rec.get("fragment_start"),
                                        "EQUIPMENT_FAILURE fragment_start "
                                        "does not match the failed fragment's "
                                        "ACTIVITY_START")
                    if self._f(rec["fragment_end"], "fragment_end") != t:
                        self._issue("C14", "equipment(%s).failure_fragment"
                                    % r, frac_to_str(t), rec.get("fragment_end"),
                                    "EQUIPMENT_FAILURE fragment_end must equal "
                                    "the failure instant")
            elif et == EVENT_EQUIPMENT_REPLACEMENT_START:
                r = rec.get("resource_id")
                st = equip[r]
                old_gen = rec.get("old_generation")
                new_gen = rec.get("new_generation")
                if old_gen != st["generation"]:
                    self._issue("C14", "equipment(%s).old_generation" % r,
                                st["generation"], old_gen,
                                "old_generation does not match the replayed "
                                "generation")
                if new_gen != old_gen + 1:
                    self._issue("C14", "equipment(%s).new_generation" % r,
                                old_gen + 1, new_gen,
                                "generation must increase by exactly one per "
                                "replacement")
                age_before = self._f(rec["age_before"], "age_before")
                if age_before != st["age"]:
                    self._issue("C14", "equipment(%s).age_before" % r,
                                frac_to_str(st["age"]), frac_to_str(age_before),
                                "age_before does not match the replayed age "
                                "(age must be reset to 0 only at a "
                                "replacement)")
                kind = rec.get("kind")
                trigger = rec.get("trigger")
                if kind not in REPLACEMENT_KINDS or trigger not in REPLACEMENT_TRIGGERS:
                    self._issue("C14", "equipment(%s).replacement" % r,
                                "frozen kind/trigger vocabulary", (kind, trigger),
                                "unknown replacement kind/trigger")
                elif _TRIGGER_KIND.get(trigger) != kind:
                    self._issue("C14", "equipment(%s).replacement" % r,
                                _TRIGGER_KIND.get(trigger), kind,
                                "replacement kind does not match the frozen "
                                "trigger")
                # Trigger consistency, deferral-robust: a pending replacement
                # may be deferred across a shift boundary, so the replacement
                # START can occur at a later timestamp than the fragment end /
                # failure that triggered it.  The strong invariants are the
                # age checks (equipment age is frozen while pending -- no
                # fragment runs on unavailable equipment).
                if trigger == REPLACEMENT_TRIGGER_MID_FRAGMENT_FAILURE:
                    if not any_failure_at_age(r, age_before):
                        self._issue("C14", "equipment(%s).trigger" % r,
                                    "an EQUIPMENT_FAILURE at age %s"
                                    % frac_to_str(age_before),
                                    "missing",
                                    "mid_fragment_failure without an "
                                    "EQUIPMENT_FAILURE record at the same "
                                    "failure age")
                    if st["is_right_censored"] or st["lifetime"] is None \
                            or age_before != st["lifetime"]:
                        self._issue("C14", "equipment(%s).trigger_age" % r,
                                    frac_to_str(st["lifetime"])
                                    if st["lifetime"] is not None else "uncensored lifetime",
                                    frac_to_str(age_before),
                                    "mid_fragment_failure age_before must "
                                    "equal the sampled lifetime")
                elif trigger == REPLACEMENT_TRIGGER_FAILURE_AT_END:
                    if st["is_right_censored"] or st["lifetime"] is None \
                            or age_before != st["lifetime"]:
                        self._issue("C14", "equipment(%s).trigger_age" % r,
                                    frac_to_str(st["lifetime"])
                                    if st["lifetime"] is not None else "uncensored lifetime",
                                    frac_to_str(age_before),
                                    "failure_at_end age_before must equal the "
                                    "sampled lifetime")
                elif trigger == REPLACEMENT_TRIGGER_POST_COMPLETION_240:
                    if age_before != mandatory_age:
                        self._issue("C14", "equipment(%s).trigger_age" % r,
                                    frac_to_str(mandatory_age),
                                    frac_to_str(age_before),
                                    "post_completion_240 age_before must "
                                    "equal 240 h")
                elif trigger == REPLACEMENT_TRIGGER_A_PLUS_D_GT_240:
                    d = self._cfg.durations[r]
                    if age_before + d <= mandatory_age:
                        self._issue("C14", "equipment(%s).trigger" % r,
                                    "age_before + d > 240",
                                    frac_to_str(age_before + d),
                                    "a_plus_d_gt_240 without a+d > 240 (this "
                                    "is a FORCED replacement, never a "
                                    "preventive choice)")
                elif trigger == REPLACEMENT_TRIGGER_ILLEGAL_CROSSING_BACKSTOP:
                    if not illegal_cancels_by_resource[r]:
                        self._issue("C14", "equipment(%s).trigger" % r,
                                    "an ILLEGAL_240_INTERRUPT cancel",
                                    "missing",
                                    "illegal_crossing_backstop without the "
                                    "backstop interrupt record")
                    if age_before != mandatory_age:
                        self._issue("C14", "equipment(%s).trigger_age" % r,
                                    frac_to_str(mandatory_age),
                                    frac_to_str(age_before),
                                    "illegal-crossing age_before must equal "
                                    "240 h")
                elif trigger == REPLACEMENT_TRIGGER_PREVENTIVE:
                    if tau_is_no_pm:
                        self._issue("C14", "equipment(%s).preventive" % r,
                                    "never under NO_PM_BEFORE_MANDATORY (G)",
                                    "preventive replacement",
                                    "preventive replacement under the "
                                    "NO_PM_BEFORE_MANDATORY policy")
                    elif isinstance(tau_pm, Fraction) \
                            and age_before < tau_pm:
                        self._issue("C14", "equipment(%s).preventive" % r,
                                    ">= tau_pm (%s)" % frac_to_str(tau_pm),
                                    frac_to_str(age_before),
                                    "preventive replacement below the frozen "
                                    "threshold")
                    if age_before < min_preventive:
                        self._issue("C14", "equipment(%s).preventive" % r,
                                    ">= 120 h (P016)", frac_to_str(age_before),
                                    "preventive replacement below the frozen "
                                    "minimum preventive age")
                # new generation binds a new U_L (exactly one per generation)
                u_expected, lifetime, censored = self._expected_lifetime(
                    r, new_gen)
                try:
                    recorded_u = self._f(rec["u"], "replacement.u")
                except ReplayCheckerInputError as exc:
                    self._issue("C13", "equipment(%s).generation.%d.u"
                                % (r, new_gen), frac_to_str(u_expected),
                                rec.get("u"),
                                "replacement U_L is not a valid exact "
                                "rational: %s" % exc)
                    recorded_u = None
                if recorded_u is not None and recorded_u != u_expected:
                    self._issue("C13", "equipment(%s).generation.%d.u"
                                % (r, new_gen), frac_to_str(u_expected),
                                rec.get("u"),
                                "replacement U_L does not match the "
                                "independently recomputed U_L for the new "
                                "generation")
                expected_key = ks.canonical_key(
                    self._cfg.namespace, self._cfg.replicate_id, r, None,
                    new_gen, self._cfg.master_seed)
                if rec.get("u_key") is not None and rec["u_key"] != expected_key:
                    self._issue("C13", "equipment(%s).generation.%d.u_key"
                                % (r, new_gen), expected_key, rec.get("u_key"),
                                "replacement u_key does not match the "
                                "canonical key")
                cal = self._params["calibration_minutes"][r] / Fraction(60)
                cal_start = self._f(rec["calibration_start"], "calibration_start")
                cal_end = self._f(rec["calibration_end"], "calibration_end")
                if cal_end - cal_start != cal:
                    self._issue("C14", "equipment(%s).calibration_duration" % r,
                                frac_to_str(cal), frac_to_str(cal_end - cal_start),
                                "calibration duration must be the frozen "
                                "parameters.csv value (30/20/20/40 min)")
                if cal_start != t:
                    self._issue("C14", "equipment(%s).calibration_start" % r,
                                frac_to_str(t), frac_to_str(cal_start),
                                "calibration must start at the replacement "
                                "instant")
                if st["calibration_in_flight"]:
                    self._issue("C14", "equipment(%s).calibration" % r,
                                "no replacement while calibrating", "overlap",
                                "a second replacement started while a "
                                "calibration was in flight")
                # shift feasibility of the calibration (no-cross-shift, P062)
                shift = self._shift_at(cal_start)
                if shift is not None and cal_end > shift[1]:
                    self._issue("C12", "equipment(%s).calibration_shift" % r,
                                "calibration_end <= shift_end (%s)"
                                % frac_to_str(shift[1]),
                                frac_to_str(cal_end),
                                "calibration crosses the shift boundary (换新"
                                "+校准 must complete within one shift)")
                # reset the replayed state
                st["generation"] = new_gen
                st["age"] = Fraction(0)
                st["lifetime"] = lifetime
                st["is_right_censored"] = censored
                st["u"] = u_expected
                st["replacement_count"] += 1
                if kind == REPLACEMENT_KIND_PREVENTIVE:
                    st["preventive_count"] += 1
                st["available"] = False
                st["calibration_in_flight"] = True
                st["calibration_start"] = cal_start
                st["deferral_emitted"] = False
                st["max_generation"] = max(st["max_generation"], new_gen)
            elif et == EVENT_EQUIPMENT_CALIBRATION_COMPLETE:
                r = rec.get("resource_id")
                st = equip[r]
                if rec.get("generation") != st["generation"]:
                    self._issue("C14", "equipment(%s).calibration_generation"
                                % r, st["generation"], rec.get("generation"),
                                "calibration generation does not match the "
                                "replayed generation")
                if not st["calibration_in_flight"]:
                    self._issue("C14", "equipment(%s).calibration_complete" % r,
                                "calibration in flight", "none",
                                "EQUIPMENT_CALIBRATION_COMPLETE without a "
                                "started replacement")
                cal = self._params["calibration_minutes"][r] / Fraction(60)
                cal_end = self._f(rec["calibration_end"], "calibration_end")
                if cal_end != t:
                    self._issue("C14", "equipment(%s).calibration_end" % r,
                                frac_to_str(t), frac_to_str(cal_end),
                                "calibration must complete at this instant")
                if st["calibration_start"] is not None \
                        and cal_end - st["calibration_start"] != cal:
                    self._issue("C14", "equipment(%s).calibration_duration" % r,
                                frac_to_str(cal),
                                frac_to_str(cal_end - st["calibration_start"]),
                                "calibration duration must be the frozen "
                                "parameters.csv value")
                st["calibration_in_flight"] = False
                st["calibration_start"] = None
                st["available"] = True
                st["calibration_count"] += 1
            elif et == EVENT_EQUIPMENT_REPLACEMENT_DEFERRED:
                r = rec.get("resource_id")
                st = equip[r]
                if rec.get("reason") != "no_cross_shift":
                    self._issue("C14", "equipment(%s).deferred" % r,
                                "no_cross_shift", rec.get("reason"),
                                "replacement deferral must be a shift-boundary "
                                "fit rule")
                if st["calibration_in_flight"]:
                    self._issue("C14", "equipment(%s).deferred" % r,
                                "no calibration in flight", "in flight",
                                "replacement deferred while a calibration was "
                                "in flight")
                if st["deferral_emitted"]:
                    self._issue("C14", "equipment(%s).deferred" % r,
                                "at most one deferral per pending episode",
                                "duplicate",
                                "consecutive deferrals without an intervening "
                                "replacement start")
                st["deferral_emitted"] = True
                st["deferral_count"] += 1
                st["available"] = False
                next_wake = self._f(rec["next_wake"], "next_wake")
                if next_wake <= t:
                    self._issue("C14", "equipment(%s).deferred_wake" % r,
                                "> event_time", frac_to_str(next_wake),
                                "next wake must be in the future")
                if not self._is_shift_boundary(next_wake):
                    self._issue("C14", "equipment(%s).deferred_wake" % r,
                                "a shift boundary", frac_to_str(next_wake),
                                "next wake must be a frozen shift boundary")
                if rec.get("kind") not in REPLACEMENT_KINDS \
                        or rec.get("trigger") not in REPLACEMENT_TRIGGERS:
                    self._issue("C14", "equipment(%s).deferred" % r,
                                "frozen kind/trigger vocabulary",
                                (rec.get("kind"), rec.get("trigger")),
                                "unknown replacement kind/trigger")

        # dangling fragments at SIMULATION_END
        if open_attempts:
            for attempt_id in sorted(open_attempts):
                self._issue("C18", "attempt(%s)" % attempt_id,
                            "terminal record at SIMULATION_END", "dangling",
                            "started fragment has no terminal record "
                            "(dangling RUNNING)")

        # observations paired with completed fragments
        for attempt_id, view in sorted(self._attempts.items()):
            closed = closed_attempts.get(attempt_id)
            obs_list = self._obs_by_attempt.get(attempt_id, [])
            if len(obs_list) > 1:
                self._issue("C17", "attempt(%s)" % attempt_id,
                            "<= 1 OBSERVATION_MATERIALIZED", len(obs_list),
                            "more than one observation for one fragment")
            if closed is not None and closed["terminal_type"] == "ACTIVITY_COMPLETE":
                if not obs_list:
                    self._issue("C17", "attempt(%s)" % attempt_id,
                                "OBSERVATION_MATERIALIZED at completion",
                                "missing",
                                "completed fragment has no observation")
                else:
                    obs = obs_list[0]
                    obs_time = self._f(obs["event_time"], "observation time")
                    if obs_time != closed["terminal_time"]:
                        self._issue("C17", "attempt(%s).observation_time"
                                    % attempt_id,
                                    frac_to_str(closed["terminal_time"]),
                                    frac_to_str(obs_time),
                                    "observation must be materialized at the "
                                    "completion instant")
            elif closed is not None and obs_list:
                self._issue("C17", "attempt(%s)" % attempt_id,
                            "no observation for an interrupted/cancelled "
                            "fragment", "observation present",
                            "interruption/cancellation must consume no "
                            "observation U")

        # final recomputed equipment summary
        for r in PROCESSES:
            st = equip[r]
            self._recomputed.setdefault("equipment", {})[r] = {
                "age_h": frac_to_str(st["age"]),
                "generation": st["generation"],
                "replacement_count": st["replacement_count"],
                "preventive_replacement_count": st["preventive_count"],
                "failure_count": st["failure_count"],
                "calibration_count": st["calibration_count"],
                "lifetime_h": (
                    frac_to_str(st["lifetime"])
                    if st["lifetime"] is not None else None
                ),
                "is_right_censored": st["is_right_censored"],
                "available": st["available"],
            }
            self._recomputed.setdefault("generations", {})[r] = st["max_generation"]
            lifetimes: dict[str, Any] = {}
            for g in range(1, st["max_generation"] + 1):
                u, lifetime, censored = self._expected_lifetime(r, g)
                lifetimes[str(g)] = {
                    "u": frac_to_str(u),
                    "lifetime_h": (
                        frac_to_str(lifetime) if lifetime is not None else None
                    ),
                    "right_censored": censored,
                }
            self._recomputed.setdefault("lifetimes", {})[r] = lifetimes

        # U consumption counts (recomputed from the log structure)
        self._recomputed.setdefault("u_consumption", {})["u_x"] = (
            3 * len(self._records_by_type.get(EVENT_TRUE_STATE_GENERATED, []))
        )
        self._recomputed.setdefault("u_consumption", {})["u_d"] = len(
            self._records_by_type.get("D_CREATED", [])
        )
        self._recomputed.setdefault("u_consumption", {})["u_y"] = len(
            self._records_by_type.get("OBSERVATION_MATERIALIZED", [])
        )
        total_replacements = sum(
            self._recomputed["equipment"][r]["replacement_count"]
            for r in PROCESSES
        )
        self._recomputed.setdefault("u_consumption", {})["u_l"] = (
            4 + total_replacements
        )

    # ------------------------------------------------------------------
    # C17 metrics cross-check
    # ------------------------------------------------------------------

    def _check_metrics(self) -> None:
        """Recomputed T/S/PL/PW/YXB/equipment vs the optional run metrics."""
        if not self._structural_ok or self._metrics is None:
            return
        m = self._metrics
        for field, recomputed in (
            ("T", self._recomputed.get("T_h")),
            ("S", self._recomputed.get("S")),
            ("PL", self._recomputed.get("PL")),
            ("PW", self._recomputed.get("PW")),
            ("exited", self._recomputed.get("exited")),
        ):
            if field in m and str(recomputed) != str(m[field]):
                self._issue("C17", "metrics.%s" % field, recomputed, m[field],
                            "recomputed %s disagrees with the run metrics"
                            % field)
        if "T_days" in m and self._recomputed.get("T_days") is not None:
            if str(self._recomputed["T_days"]) != str(m["T_days"]):
                self._issue("C17", "metrics.T_days",
                            self._recomputed["T_days"], m["T_days"],
                            "recomputed T_days disagrees with the run metrics")
        for proc in PROCESSES:
            key = "YXB_" + proc
            if key in m and str(self._recomputed.get(key)) != str(m[key]):
                self._issue("C17", "metrics.%s" % key,
                            self._recomputed.get(key), m[key],
                            "recomputed %s disagrees with the run metrics" % key)
        if "shift_count" in m and m["shift_count"] != self._recomputed.get("shift_count"):
            self._issue("C17", "metrics.shift_count",
                        self._recomputed.get("shift_count"), m["shift_count"],
                        "recomputed shift_count disagrees with the run metrics")
        if "yxb_denominator_h" in m \
                and str(m["yxb_denominator_h"]) != str(self._recomputed.get("yxb_denominator_h")):
            self._issue("C17", "metrics.yxb_denominator_h",
                        self._recomputed.get("yxb_denominator_h"),
                        m["yxb_denominator_h"],
                        "recomputed YXB denominator disagrees with the run "
                        "metrics")
        eq_metrics = m.get("equipment")
        if isinstance(eq_metrics, dict):
            for r in PROCESSES:
                entry = eq_metrics.get(r)
                if not isinstance(entry, dict):
                    continue
                recomputed = self._recomputed.get("equipment", {}).get(r, {})
                for field in ("age_h", "generation", "replacement_count",
                              "preventive_replacement_count", "failure_count",
                              "lifetime_h", "is_right_censored", "available"):
                    if field in entry and str(recomputed.get(field)) != str(entry[field]):
                        self._issue("C17", "metrics.equipment.%s.%s" % (r, field),
                                    recomputed.get(field), entry[field],
                                    "recomputed equipment %s disagrees with "
                                    "the run metrics" % field)

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(self) -> ReplayReport:
        self._build_views()
        self._check_termination()
        self._check_shift_calendar()
        self._check_tasks()
        self._check_attempts()
        self._check_devices_quality()
        self._check_recorded_u()
        self._check_d_timing()
        self._check_turnovers()
        self._check_bay_coverage()
        self._check_resource_occupancy()
        self._check_same_timestamp_order()
        self._check_ledger()
        self._check_equipment_and_fragments()
        self._check_metrics()

        devices_summary: dict[str, Any] = {}
        for device_id in sorted(self._devices):
            dev = self._devices[device_id]
            devices_summary[str(device_id)] = {
                "terminal_state": dev["terminal_state"],
                "terminal_h": (
                    frac_to_str(dev["terminal_time"])
                    if dev["terminal_time"] is not None else None
                ),
                "d_state": dev["d_state"],
                "bay_id": dev["bay_id"],
                "entry_h": (
                    frac_to_str(dev["entry_time"])
                    if dev["entry_time"] is not None else None
                ),
            }
        self._recomputed["devices"] = devices_summary
        tasks_summary: dict[str, Any] = {}
        for key in sorted(self._tasks,
                          key=lambda k: (k[0], PROCESS_ORDER[k[1]], k[2])):
            view = self._tasks[key]
            status = "COMPLETED" if view["completes"] \
                else ("CANCELLED" if view["cancels"] else "RELEASED_UNFINISHED")
            finish = None
            if view["completes"]:
                finish = self._f(view["completes"][0]["event_time"], "finish")
            elif view["cancels"]:
                finish = self._f(view["cancels"][-1]["event_time"], "cancel")
            outcome = None
            if view["observations"]:
                outcome = view["observations"][0].get("outcome")
            tasks_summary["D%03d_%s_%d" % key] = {
                "status": status,
                "release_h": (
                    frac_to_str(view["release_time"])
                    if view["release_time"] is not None else None
                ),
                "start_h": (
                    frac_to_str(self._f(view["starts"][0]["event_time"], "start"))
                    if view["starts"] else None
                ),
                "finish_h": frac_to_str(finish) if finish is not None else None,
                "outcome": outcome,
            }
        self._recomputed["tasks"] = tasks_summary

        verdict = "PASS" if not self._issues else "FAIL"
        return ReplayReport(
            run_id=self._run_id,
            scenario_id=self._cfg.scenario_id,
            verdict=verdict,
            issues=self._issues,
            recomputed=self._recomputed,
            metadata={
                "registry_version": REGISTRY_VERSION,
                "check_ids": list(CHECK_IDS),
                "task_package_ref": "G3-SPEC-V1.0",
                "scenario": self._cfg.scenario,
                "batch_size": self._cfg.batch_size,
                "turnover_profile": self._cfg.turnover_profile,
                "namespace": self._cfg.namespace,
                "master_seed": self._cfg.master_seed,
                "replicate_id": self._cfg.replicate_id,
                "event_log_records": len(self._log),
            },
        )


def check_replay(event_log: Any, config: Any, parameters_csv: Any,
                 metrics: Optional[dict[str, Any]] = None,
                 run_id: Optional[str] = None) -> ReplayReport:
    """Run the C17 full G3-layer independent replay checker once.

    ``event_log``: the DES's immutable event log (list / {records: [...]} /
    JSON or JSONL file path).  ``config``: the frozen ``random_des_config_v1``
    dict (or a ``ReplayConfig``).  ``parameters_csv``: the shared frozen
    ``parameters.csv`` (required; supplies P010-P025/P026-P029 frozen
    semantics).  ``metrics``: optional DES run metrics block.  ``run_id``:
    optional run identifier for the report.
    """
    if parameters_csv is None:
        raise ReplayCheckerInputError(
            "parameters_csv is required (shared frozen parameters.csv, "
            "P010-P025 calibration/CDF nodes and P026-P029 defect "
            "probabilities)"
        )
    checker = G3ReplayChecker(event_log, config, parameters_csv,
                              metrics=metrics, run_id=run_id)
    return checker.run()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_event_log(event_log: Any) -> Any:
    """Accept a list, an envelope ``{records: [...]}``, or a JSON/JSONL file
    path."""
    if isinstance(event_log, (str, Path)):
        path = Path(event_log)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReplayCheckerInputError(
                f"cannot read event log: {exc}"
            ) from exc
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            records: list[Any] = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ReplayCheckerInputError(
                        f"event log line is not valid JSON: {line[:80]!r}"
                    ) from exc
            return records
    return event_log


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="G3-SPEC-V1.0 S5 independent full-log replay checker "
                    "(CR-V3.1 C17/C19).")
    parser.add_argument("--event-log", required=True,
                        help="immutable G3 event_log (JSON array or JSONL)")
    parser.add_argument("--config", required=True,
                        help="frozen random_des_config_v1 JSON")
    parser.add_argument("--parameters", required=True,
                        help="shared frozen parameters.csv")
    parser.add_argument("--metrics", default=None,
                        help="optional run metrics JSON")
    parser.add_argument("--run-id", default=None,
                        help="optional run identifier for the report")
    parser.add_argument("--report", default=None,
                        help="optional output path for the report JSON")
    args = parser.parse_args(argv)
    try:
        event_log = _load_event_log(args.event_log)
        with open(args.config, "r", encoding="utf-8") as handle:
            config = json.load(handle)
        metrics = None
        if args.metrics:
            with open(args.metrics, "r", encoding="utf-8") as handle:
                metrics = json.load(handle)
        report = check_replay(event_log, config, args.parameters,
                              metrics=metrics, run_id=args.run_id)
        output = json.dumps(report.to_dict(), ensure_ascii=False,
                            indent=2, sort_keys=True)
        if args.report:
            with open(args.report, "w", encoding="utf-8") as handle:
                handle.write(output + "\n")
        else:
            print(output)
        return 0 if report.verdict == "PASS" else 1
    except ReplayCheckerInputError as exc:
        print("CHECKER_VALIDATION_ERROR: %s" % exc, file=sys.stderr)
        return 2
    except ReplayCheckerError as exc:
        print("CHECKER_NUMERICAL_ERROR: %s" % exc, file=sys.stderr)
        return 3
    except OSError as exc:
        print("CHECKER_IO_ERROR: %s" % exc, file=sys.stderr)
        return 4
    except json.JSONDecodeError as exc:
        print("CHECKER_JSON_ERROR: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
