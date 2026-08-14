"""G2-03 explicit state objects and frozen constants (Python standard library only).

Implements the frozen explicit state model of G2-03-SPEC-V1.0.1 section 6
(state_models): DEVICE_STATE / RESOURCE_STATE / BAY_STATE / TASK_STATE /
TEST_ATTEMPT_STATE / SHIFT_CALENDAR_STATE / QUEUE_ENTRY / EVENT / LOG_RECORD,
plus the frozen enumerations and FCFS key components (section 7).

Time representation: every canonical time is a ``fractions.Fraction``.
Serialization to JSON uses exact fraction strings ("num/den") or integer
strings; JSON floats are forbidden by contract.

This module holds no scheduling logic; it only defines state objects and
constants so that ``deterministic_des_v1`` (and, in the future, an independent
checker reading only the event log) share one stable vocabulary.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Frozen constants (G2-03-SPEC-V1.0.1)
# ---------------------------------------------------------------------------

RESOURCES: tuple[str, ...] = ("A", "B", "C", "E")
PROCESS_ORDER: dict[str, int] = {"A": 0, "B": 1, "C": 2, "E": 3}
ATTEMPT_ORDER: dict[int, int] = {1: 0, 2: 1}  # 1 < 2 (used only for log ordering)

DEFAULT_DURATIONS_H: dict[str, str] = {"A": "2.5", "B": "2", "C": "2.5", "E": "3"}
DEFAULT_TRANSPORT_OUT_H: str = "0.5"
DEFAULT_TRANSPORT_IN_H: str = "0.5"

SCENARIOS: tuple[str, ...] = ("q2_single_shift", "q3_two_shift", "isolated_small_case")
TURNOVER_PROFILES: tuple[str, ...] = ("1h_literal", "0.5h_overlap")
CANCEL_REASONS: tuple[str, ...] = ("NONE", "DEVICE_EXIT", "SHIFT_INTERRUPT")
TERMINAL_REASON_SECOND_ABNORMAL: str = "process_second_abnormal"

KEY_SCHEMA_VERSION: str = "key_schema_v1"

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Outcome(str, enum.Enum):
    PASS = "PASS"
    ABNORMAL = "ABNORMAL"
    NONE = "NONE"


class ProcessStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_RETEST = "AWAITING_RETEST"
    PASSED = "PASSED"


class TerminalState(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    EXITED = "EXITED"


class DState(str, enum.Enum):
    NOT_CREATED = "not_created"
    NORMAL = "normal"
    PROBLEM = "problem"


class ResourceStatus(str, enum.Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"


class BayStatus(str, enum.Enum):
    OCCUPIED_TESTING = "OCCUPIED_TESTING"
    OCCUPIED_TRANSPORT_OUT = "OCCUPIED_TRANSPORT_OUT"
    OCCUPIED_TRANSPORT_IN = "OCCUPIED_TRANSPORT_IN"
    TERMINAL_OCCUPIED_UNTIL_STOP = "TERMINAL_OCCUPIED_UNTIL_STOP"
    # Engine-internal extension for fixtures whose initial preload leaves a bay
    # empty (e.g. F9/F10 preload only device 1). Not part of the frozen enum
    # semantics; such a bay produces no events and no occupancy.
    EMPTY = "EMPTY"


class TaskStatus(str, enum.Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AttemptStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class QueueEntryStatus(str, enum.Enum):
    WAITING = "WAITING"
    DISPATCHED = "DISPATCHED"
    REMOVED = "REMOVED"


class EventType(str, enum.Enum):
    ACTIVITY_START = "ACTIVITY_START"
    ACTIVITY_COMPLETE = "ACTIVITY_COMPLETE"
    OBSERVATION_MATERIALIZED = "OBSERVATION_MATERIALIZED"
    D_CREATED = "D_CREATED"
    TASK_RELEASE = "TASK_RELEASE"
    DEVICE_EXIT = "DEVICE_EXIT"
    TASK_CANCEL = "TASK_CANCEL"
    TURNOVER_OUT_START = "TURNOVER_OUT_START"
    TURNOVER_OUT_COMPLETE = "TURNOVER_OUT_COMPLETE"
    TURNOVER_IN_START = "TURNOVER_IN_START"
    TURNOVER_IN_COMPLETE = "TURNOVER_IN_COMPLETE"
    SHIFT_CHANGE = "SHIFT_CHANGE"
    WAKE_UP = "WAKE_UP"
    DEVICE_TERMINAL = "DEVICE_TERMINAL"
    SIMULATION_END = "SIMULATION_END"


class CancelReason(str, enum.Enum):
    NONE = "NONE"
    DEVICE_EXIT = "DEVICE_EXIT"
    SHIFT_INTERRUPT = "SHIFT_INTERRUPT"


class Scenario(str, enum.Enum):
    Q2_SINGLE_SHIFT = "q2_single_shift"
    Q3_TWO_SHIFT = "q3_two_shift"
    ISOLATED_SMALL_CASE = "isolated_small_case"


class TurnoverProfile(str, enum.Enum):
    LITERAL_1H = "1h_literal"
    OVERLAP_0_5H = "0.5h_overlap"


# ---------------------------------------------------------------------------
# Rational (de)serialization helpers
# ---------------------------------------------------------------------------


def fraction_to_string(value: Fraction) -> str:
    """Serialize a Fraction exactly: integer string when denominator is 1,
    otherwise "num/den". Never a JSON float."""
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def string_to_fraction(value: str) -> Fraction:
    """Parse a decimal or fraction string ("2.5", "5/2", "9") into a Fraction."""
    if not isinstance(value, str):
        raise TypeError(f"rational must be a string, got {type(value).__name__}: {value!r}")
    return Fraction(value)


# ---------------------------------------------------------------------------
# Explicit state objects (spec section 6)
# ---------------------------------------------------------------------------


@dataclass
class ProcessState:
    """One entry of DEVICE_STATE.process_state (per A/B/C/E)."""

    process: str
    effective_attempt_no: int = 1
    first_failure_time: Optional[Fraction] = None
    outcome_history: list[str] = field(default_factory=list)
    process_status: ProcessStatus = ProcessStatus.NOT_STARTED


@dataclass
class DeviceState:
    """DEVICE_STATE."""

    device_id: int
    entry_time: Fraction
    bay_id: int
    process_state: dict[str, ProcessState] = field(default_factory=dict)
    d_state: DState = DState.NOT_CREATED
    terminal_state: TerminalState = TerminalState.PENDING
    exit_reason: Optional[str] = None  # null | process_second_abnormal


@dataclass
class ResourceState:
    """RESOURCE_STATE."""

    resource_id: str
    capacity: int = 1
    status: ResourceStatus = ResourceStatus.IDLE
    current_activity: Optional[dict[str, Any]] = None  # task refs while BUSY


@dataclass
class BayState:
    """BAY_STATE."""

    bay_id: int
    status: BayStatus = BayStatus.EMPTY
    current_device_id: Optional[int] = None
    transport_phase: str = "none"  # none | out | in
    turnover_profile: str = "1h_literal"  # scenario constant, isolated per config
    turnover_pending: bool = False  # terminal device waiting for a feasible window


@dataclass
class TaskState:
    """TASK_STATE."""

    task_id: str
    resource_id: str
    device_id: int
    process: str
    effective_attempt_no: int
    release_time: Fraction  # frozen at creation; never rewritten
    status: TaskStatus = TaskStatus.READY
    outcome: str = "NONE"


@dataclass
class TestAttemptState:
    """TEST_ATTEMPT_STATE (one physical execution fragment)."""

    attempt_id: str
    task_id: str
    device_id: int
    process: str
    effective_attempt_no: int
    execution_no: int = 1
    status: AttemptStatus = AttemptStatus.SCHEDULED
    start_time: Optional[Fraction] = None
    end_time: Optional[Fraction] = None
    outcome: str = "NONE"
    result_squad_id: Optional[int] = None


@dataclass
class ShiftInfo:
    """A concrete shift interval [start, end) with its duty squad."""

    shift_index: int
    shift_start: Fraction
    shift_end: Fraction
    on_duty_squad: int


@dataclass
class ShiftCalendarState:
    """SHIFT_CALENDAR_STATE."""

    scenario: str
    shift_length_h: Fraction
    shifts_per_day: int
    active_shift: Optional[ShiftInfo] = None
    next_shift_wake_up_time: Optional[Fraction] = None


@dataclass
class QueueEntry:
    """QUEUE_ENTRY."""

    queue_id: str  # resource id
    task_id: str
    fcfs_key: tuple  # (release_time Fraction, device_id int, process_order int, attempt int)
    status: QueueEntryStatus = QueueEntryStatus.WAITING


@dataclass
class Event:
    """EVENT (internal scheduling event)."""

    event_id: int
    event_time: Fraction
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class LogRecord:
    """LOG_RECORD — one immutable, append-only log line.

    All optional fields default to None; the engine fills only the fields
    relevant to each event type. Times are Fractions and serialized as exact
    strings. This is the single interface contract for the future independent
    checker (G2-04), which must be able to recompute bay/resource occupancy,
    release/start/end, effective attempt, outcomes, cancellation, shifts,
    turnover, terminal state, T and the YXB/age ledger seam from the log alone.
    """

    seq: int
    event_time: Fraction
    event_type: str
    device_id: Optional[int] = None
    process: Optional[str] = None
    effective_attempt_no: Optional[int] = None
    resource_id: Optional[str] = None
    bay_id: Optional[int] = None
    squad_id: Optional[int] = None
    task_id: Optional[str] = None
    attempt_start_time: Optional[Fraction] = None
    attempt_end_time: Optional[Fraction] = None
    outcome: Optional[str] = None
    cancel_reason: Optional[str] = None
    release_time: Optional[Fraction] = None
    d_state: Optional[str] = None
    terminal_state: Optional[str] = None
    terminal_reason: Optional[str] = None
    elapsed_hours: Optional[Fraction] = None
    # SHIFT_CHANGE extras
    shift_index: Optional[int] = None
    shift_start: Optional[Fraction] = None
    shift_end: Optional[Fraction] = None
    on_duty_squad: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict. Fraction fields become exact
        fraction/integer strings; None stays null."""
        result: dict[str, Any] = {
            "seq": self.seq,
            "event_time": fraction_to_string(self.event_time),
            "event_type": self.event_type,
        }
        for name in (
            "device_id", "process", "effective_attempt_no", "resource_id",
            "bay_id", "squad_id", "task_id", "outcome", "cancel_reason",
            "d_state", "terminal_state", "terminal_reason", "shift_index",
            "on_duty_squad",
        ):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        for name in (
            "attempt_start_time", "attempt_end_time", "release_time",
            "elapsed_hours", "shift_start", "shift_end",
        ):
            value = getattr(self, name)
            if value is not None:
                result[name] = fraction_to_string(value)
        return result
