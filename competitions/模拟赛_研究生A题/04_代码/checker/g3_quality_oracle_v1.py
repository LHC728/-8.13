# -*- coding: utf-8 -*-
"""G3-SPEC-V1.0 S4: C06 full G3-layer independent quality-separation oracle (E2).

Role
----
Independent (heterogeneous-source) oracle for ``CR-V3.1/C06`` at the full G3
layer (G3-SPEC-V1.0 section 9 ``c06_quality_separation``).  Given ONLY the
immutable ``event_log`` of the keyed random DES
(``04_代码/main_model/g3/random_des_v1.py``, S3), the frozen
``random_des_config_v1`` config and the shared frozen ``parameters.csv``, the
oracle INDEPENDENTLY recomputes every per-device terminal-quality quantity
required by section 9:

  * true terminal state (``PASSED`` / ``EXITED``),
  * D generation (generated or not, plus the value ``normal`` / ``problem``),
  * final pass / exit,
  * the four-cell category ``GP`` / ``BP`` / ``GE`` / ``BE``,
  * ``PL`` contribution and ``PW`` contribution,

and cross-checks them per device against the DES event log (全等/差异报告).
It never imports, reads or executes the main DES; the DES's recorded ``u`` /
``u_key`` / ``true_state`` values are never read (the canonical world U is
recomputed from the key schema; see ``test_..._log_u_values_ignored``).

Derivation principle (frozen V3.1 section 9; 小问依赖与检查器接口.md item 12)
-----------------------------------------------------------------------------
The quality items are time-layer-free.  Under the frozen conditions (fixed
true-state and effective-observation band; no repair / skip / extra test /
censoring; interruption and cancellation produce no result and do not change
the true state; the kernel does not depend on calendar / fatigue / equipment
age; equipment failure does not damage the device; the strategy is
non-anticipatory, fair and almost-surely-completing; same-instant completion
settles first), each device's absorption result is uniquely determined by its
FIXED effective observation sequence.  The oracle therefore:

  * recomputes the canonical world ``U_X`` / ``U_D`` / ``U_Y`` from
    ``g3.key_schema_v1`` (S1, the frozen shared schema P061) with the SAME
    ``(namespace, replicate_id, master_seed)`` as the DES -- it never reads
    the DES log's ``u``/``u_key``/``true_state`` values (the values are
    derived, not copied);
  * forward-chains each device's absorption chain (A/B/C attempt 1, full
    retest on first abnormal; D at A/B/C all-PASS; E attempt 1, retest) from
    the recomputed U, the frozen observation kernel (P050-P057) and the
    frozen defect probabilities (P026-P029);
  * derives the terminal state, D generation, four-cell category and
    PL/PW contribution from that chain;
  * uses the event log ONLY for the structural facts to be verified: which
    devices exist, which ``(device, process, effective_attempt_no)``
    observations were actually materialized, and the recorded
    ``DEVICE_TERMINAL`` / ``D_CREATED`` / outcome fields.

Time-layer quantities (T, YXB, cancelled fragments, equipment age /
generation / replacement counts, ``U_L`` lifetimes) are deliberately OUT OF
SCOPE: the separation proposition states the strategy changes only those, so
the oracle never parses event times and never touches ``U_L``.

Isolation (CR-V3.1/C19 principle, G3-SPEC-V1.0 section 12)
----------------------------------------------------------
This module imports ONLY the Python standard library plus ``g3.key_schema_v1``
(the frozen shared random-key schema P061; explicitly allowed by the task
package: "需要时用 key_schema_v1 重算同一 canonical world 的 U").  It NEVER
imports ``random_des_v1``, ``des.*``, ``lifetime_regeneration_v1``, any other
checker or test module, and never launches the main engine.  Static and
dynamic isolation proofs live in ``04_代码/tests/test_g3_quality_oracle_v1.py``.

Exactness / determinism
-----------------------
Every canonical value is an exact ``fractions.Fraction``; binary float is
forbidden in the oracle source and rejected in its inputs (config kernel
alpha/beta, parameters.csv defect probabilities).  The same
(log + config + parameters.csv) always yields a byte-identical canonical
report.

Output contract (frozen G3-SPEC-V1.0 section 9)
-----------------------------------------------
Per device: ``device_id``, ``true_terminal_state``, ``d_generated`` (+ value),
``final_pass_exit``, ``category`` (GP/BP/GE/BE), ``pl_contribution``,
``pw_contribution``.  Plus the per-device 对拍 (oracle vs DES) with
全等/差异 and the batch aggregates ``S`` / ``PL`` / ``PW`` / four-cell counts.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

from g3 import key_schema_v1 as ks

# ---------------------------------------------------------------------------
# Frozen vocabulary, restated independently (never imported from the DES).
# Literals come from the frozen problem contract / V3.1 / G3-SPEC-V1.0 and the
# shared event-log vocabulary; restating them keeps this module independent.
# ---------------------------------------------------------------------------

PROCESSES: tuple[str, ...] = ("A", "B", "C", "E")
ABC: tuple[str, ...] = ("A", "B", "C")

OUTCOME_PASS: str = "PASS"
OUTCOME_ABNORMAL: str = "ABNORMAL"

TERMINAL_PASSED: str = "PASSED"
TERMINAL_EXITED: str = "EXITED"

FINAL_PASS: str = "pass"
FINAL_EXIT: str = "exit"

D_NOT_CREATED: str = "not_created"
D_NORMAL: str = "normal"
D_PROBLEM: str = "problem"

# Frozen four-cell terminal categories (V3.1 section 5; P045-P047):
#   GP = passed with all generated real states normal (真正常通过)
#   BP = passed with >= 1 generated real problem (带问题通过)
#   GE = exited with all generated real states normal (正常退出)
#   BE = exited with >= 1 generated real problem (带问题退出)
CATEGORY_GP: str = "GP"
CATEGORY_BP: str = "BP"
CATEGORY_GE: str = "GE"
CATEGORY_BE: str = "BE"
CATEGORIES: tuple[str, ...] = (CATEGORY_GP, CATEGORY_BP, CATEGORY_GE, CATEGORY_BE)

# Frozen parameters.csv rows owned by this oracle (defect probabilities used to
# threshold the recomputed U_X/U_D; shared read-only parameters, never
# duplicated as module constants -- the csv is the single authoritative source).
PARAMETER_Q_ROWS: dict[str, str] = {
    "P026": "q_A",
    "P027": "q_B",
    "P028": "q_C",
    "P029": "q_D",
}

REGISTRY_VERSION: str = "CR-V3.1"
CHECK_IDS: tuple[str, ...] = ("C06",)

__all__ = [
    "PROCESSES",
    "ABC",
    "OUTCOME_PASS",
    "OUTCOME_ABNORMAL",
    "TERMINAL_PASSED",
    "TERMINAL_EXITED",
    "FINAL_PASS",
    "FINAL_EXIT",
    "D_NOT_CREATED",
    "D_NORMAL",
    "D_PROBLEM",
    "CATEGORY_GP",
    "CATEGORY_BP",
    "CATEGORY_GE",
    "CATEGORY_BE",
    "CATEGORIES",
    "QualityOracleError",
    "QualityOracleInputError",
    "QualityOracleConfig",
    "OracleDeviceResult",
    "DesDeviceFact",
    "DeviceComparison",
    "OracleReport",
    "frac_to_str",
    "parse_fraction",
    "u_x",
    "u_y",
    "u_d",
    "observation_outcome",
    "derive_device_final",
    "load_parameters",
    "parse_config",
    "build_des_device_facts",
    "QualityOracle",
    "check_quality_oracle",
]

# ---------------------------------------------------------------------------
# Errors and exact helpers
# ---------------------------------------------------------------------------


class QualityOracleError(Exception):
    """Base class for oracle failures."""


class QualityOracleInputError(QualityOracleError):
    """Invalid input (config / parameters / event log envelope); explicit
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
        raise QualityOracleInputError(f"{name}: boolean is not a rational")
    if isinstance(value, float):
        raise QualityOracleInputError(
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
            raise QualityOracleInputError(f"{name}: empty rational string")
        try:
            return Fraction(text)
        except (ValueError, ZeroDivisionError) as exc:
            raise QualityOracleInputError(
                f"{name}: not a valid rational string: {value!r}"
            ) from exc
    raise QualityOracleInputError(
        f"{name}: unsupported type {type(value).__name__}: {value!r}"
    )


# ---------------------------------------------------------------------------
# Canonical U recomputation (S1 key schema; same world as the DES)
# ---------------------------------------------------------------------------


def u_x(namespace: str, replicate_id: int, device_id: int, subsystem: str,
        master_seed: int) -> Fraction:
    """Recompute the canonical true-state uniform for one device subsystem
    (A/B/C) from ``g3.key_schema_v1`` -- the same world the DES lives in
    (same namespace / replicate_id / master_seed).  The DES log's recorded U
    is never read; the value is derived, not copied."""
    return ks.u_x(namespace, replicate_id, device_id, subsystem, master_seed)


def u_y(namespace: str, replicate_id: int, device_id: int, process: str,
        attempt: int, master_seed: int) -> Fraction:
    """Recompute the canonical observation uniform for one effective attempt
    from ``g3.key_schema_v1`` (consumed only by a valid completion; a retry of
    the same effective attempt reuses the same keyed U)."""
    return ks.u_y(namespace, replicate_id, device_id, process, attempt, master_seed)


def u_d(namespace: str, replicate_id: int, device_id: int,
        master_seed: int) -> Fraction:
    """Recompute the canonical D-materialization uniform from
    ``g3.key_schema_v1`` (dedicated stream; consumed exactly once at a legal
    D materialization)."""
    return ks.u_d(namespace, replicate_id, device_id, master_seed)


def observation_outcome(true_problem: bool, u: Fraction, alpha: Fraction,
                        beta: Fraction) -> str:
    """Apply the frozen observation kernel (V3.1 section 4; P050-P057) to a
    keyed observation U:

        P(ABNORMAL | true normal)  = alpha   (U < alpha)
        P(ABNORMAL | true problem) = 1 - beta (U < 1 - beta)

    Independent restatement of the frozen kernel semantics; binary float is
    rejected by ``parse_fraction`` callers."""
    if true_problem:
        return OUTCOME_ABNORMAL if u < Fraction(1) - beta else OUTCOME_PASS
    return OUTCOME_ABNORMAL if u < alpha else OUTCOME_PASS


# ---------------------------------------------------------------------------
# Configuration (frozen subset of random_des_config_v1; time-layer fields are
# deliberately NOT consumed -- the oracle is time-layer-free by construction)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityOracleConfig:
    """The frozen config subset the oracle consumes.

    Only the canonical-world identity (``namespace`` / ``master_seed`` /
    ``replicate_id``), the batch size (device set) and the frozen observation
    kernel (P050-P057) matter for the quality derivation.  Durations,
    transport, scenario, shift calendar, turnover profile and ``tau_pm`` are
    time-layer quantities and are ignored by design (the separation
    proposition says they change only T/YXB/fragments/equipment, never the
    quality terms).
    """

    namespace: str
    master_seed: int
    replicate_id: int
    batch_size: int
    kernel: dict[str, dict[str, Fraction]]  # process -> {alpha, beta}
    key_schema_version: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "QualityOracleConfig":
        if not isinstance(raw, dict):
            raise QualityOracleInputError("config must be a JSON object")
        if raw.get("schema_version") != "random_des_config_v1":
            raise QualityOracleInputError(
                "config.schema_version must be 'random_des_config_v1'"
            )
        schema = raw.get("key_schema_version")
        if schema is not None and schema != ks.KEY_SCHEMA_VERSION:
            raise QualityOracleInputError(
                f"config.key_schema_version must be '{ks.KEY_SCHEMA_VERSION}', "
                f"got {schema!r} (P061)"
            )
        namespace = raw.get("namespace")
        if namespace not in ks.NAMESPACES:
            raise QualityOracleInputError(
                f"config.namespace must be one of the six frozen namespaces "
                f"{ks.NAMESPACES}, got {namespace!r}"
            )
        master_seed = raw.get("master_seed")
        if isinstance(master_seed, bool) or not isinstance(master_seed, int) \
                or master_seed < 0:
            raise QualityOracleInputError(
                "config.master_seed must be a non-negative int"
            )
        replicate_id = raw.get("replicate_id")
        if isinstance(replicate_id, bool) or not isinstance(replicate_id, int) \
                or replicate_id < 0:
            raise QualityOracleInputError(
                "config.replicate_id must be a non-negative int"
            )
        batch_size = raw.get("batch_size")
        if not isinstance(batch_size, int) or batch_size < 1:
            raise QualityOracleInputError(
                "config.batch_size must be a positive int"
            )
        kernel_raw = raw.get("observation_kernel")
        if not isinstance(kernel_raw, dict):
            raise QualityOracleInputError(
                "config.observation_kernel must be an object"
            )
        kernel: dict[str, dict[str, Fraction]] = {}
        for proc in PROCESSES:
            entry = kernel_raw.get(proc)
            if not isinstance(entry, dict) or set(entry) != {"alpha", "beta"}:
                raise QualityOracleInputError(
                    f"config.observation_kernel[{proc}] must have exactly "
                    f"alpha and beta"
                )
            alpha = parse_fraction(entry["alpha"], f"observation_kernel[{proc}].alpha")
            beta = parse_fraction(entry["beta"], f"observation_kernel[{proc}].beta")
            if not (Fraction(0) <= alpha <= Fraction(1)):
                raise QualityOracleInputError(
                    f"observation_kernel[{proc}].alpha must be in [0, 1]"
                )
            if not (Fraction(0) <= beta <= Fraction(1)):
                raise QualityOracleInputError(
                    f"observation_kernel[{proc}].beta must be in [0, 1]"
                )
            kernel[proc] = {"alpha": alpha, "beta": beta}
        return cls(
            namespace=namespace,
            master_seed=master_seed,
            replicate_id=replicate_id,
            batch_size=batch_size,
            kernel=kernel,
            key_schema_version=ks.KEY_SCHEMA_VERSION,
        )

    def to_dict(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization (exact fraction strings)."""
        return {
            "namespace": self.namespace,
            "master_seed": self.master_seed,
            "replicate_id": self.replicate_id,
            "batch_size": self.batch_size,
            "observation_kernel": {
                proc: {
                    "alpha": frac_to_str(self.kernel[proc]["alpha"]),
                    "beta": frac_to_str(self.kernel[proc]["beta"]),
                }
                for proc in PROCESSES
            },
            "key_schema_version": self.key_schema_version,
        }


def parse_config(config: Any) -> QualityOracleConfig:
    """Parse a ``random_des_config_v1`` dict (or ``QualityOracleConfig``) into
    the frozen subset the oracle consumes."""
    if isinstance(config, QualityOracleConfig):
        return config
    return QualityOracleConfig.from_dict(config)


# ---------------------------------------------------------------------------
# Frozen parameters.csv (defect probabilities P026-P029; shared read-only)
# ---------------------------------------------------------------------------


def load_parameters(csv_path: Any) -> dict[str, Fraction]:
    """Read the shared frozen ``parameters.csv`` and extract the defect
    probabilities the oracle needs to threshold the recomputed U_X/U_D:

        P026 q_A = 0.025, P027 q_B = 0.03, P028 q_C = 0.02, P029 q_D = 0.001

    Also verifies P061 ``key_schema`` == ``key_schema_v1`` (the oracle's U
    derivation depends on the frozen schema).  A missing row, a drifted value
    or a non-parseable value raises ``QualityOracleInputError`` (fail loudly;
    never silently accept a drifted parameter).  Returns ``{q_A, q_B, q_C,
    q_D}`` as exact Fractions.
    """
    path = Path(csv_path)
    q: dict[str, Fraction] = {}
    key_schema_seen: Optional[str] = None
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                pid = (row.get("parameter_id") or "").strip()
                value_raw = (row.get("value") or "").strip()
                if pid in PARAMETER_Q_ROWS:
                    try:
                        value = Fraction(value_raw)
                    except (ValueError, ZeroDivisionError) as exc:
                        raise QualityOracleInputError(
                            f"parameters.csv row {pid}: cannot parse value "
                            f"{value_raw!r}"
                        ) from exc
                    if not (Fraction(0) < value < Fraction(1)):
                        raise QualityOracleInputError(
                            f"parameters.csv row {pid}: defect probability "
                            f"must lie in (0, 1), got {value!r}"
                        )
                    q[PARAMETER_Q_ROWS[pid]] = value
                elif pid == "P061":
                    key_schema_seen = value_raw
    except OSError as exc:
        raise QualityOracleInputError(
            f"cannot read parameters.csv: {exc}"
        ) from exc
    missing = [
        pid for pid in PARAMETER_Q_ROWS if PARAMETER_Q_ROWS[pid] not in q
    ]
    if missing:
        raise QualityOracleInputError(
            f"parameters.csv missing frozen rows: {missing}"
        )
    if key_schema_seen != ks.KEY_SCHEMA_VERSION:
        raise QualityOracleInputError(
            f"parameters.csv P061 key_schema must be "
            f"'{ks.KEY_SCHEMA_VERSION}', got {key_schema_seen!r}"
        )
    return q


# ---------------------------------------------------------------------------
# Oracle-side per-device derivation (time-layer-free forward chain)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OracleDeviceResult:
    """The oracle's independently derived per-device terminal-quality result
    (G3-SPEC-V1.0 section 9 output contract)."""

    device_id: int
    true_terminal_state: str            # PASSED | EXITED
    d_generated: bool
    d_value: str                        # normal | problem | not_created
    final_pass_exit: str                # pass | exit
    category: str                       # GP | BP | GE | BE
    pl_contribution: int                # 1 iff passed with a generated problem
    pw_contribution: int                # 1 iff exited with no generated problem
    true_abc: dict[str, bool]           # recomputed U_X < q_p (A/B/C)
    expected_observations: dict[tuple[str, int], str]  # (process, attempt) -> canonical outcome


def _kernel_outcome(config: QualityOracleConfig, true_problem: bool, u: Fraction,
                    process: str) -> str:
    entry = config.kernel[process]
    return observation_outcome(true_problem, u, entry["alpha"], entry["beta"])


def derive_device_final(config: QualityOracleConfig, q: dict[str, Fraction],
                        device_id: int) -> OracleDeviceResult:
    """Forward-chain one device's absorption in the canonical world.

    Frozen semantics (V3.1 section 9; problem contract 1.1/1.2): A/B/C each
    run attempt 1 and, on a first ABNORMAL, a full retest (attempt 2); a
    second ABNORMAL exits the device.  D materializes exactly once when A/B/C
    are all PASS and the device is still pending (its value is U_D < q_D).
    E runs once (attempt 1, retest on ABNORMAL) with true problem = any(A/B/C)
    or D; the device passes iff E's final observation is PASS, exits iff any
    chain reaches two ABNORMALs.

    All U values are recomputed from ``g3.key_schema_v1`` in the same
    (namespace, replicate_id, master_seed) world; nothing is read from the
    DES log.  The result is a pure function of (config, q, device_id).
    """
    ns = config.namespace
    rep = config.replicate_id
    seed = config.master_seed

    # 1) true states (U_X threshold vs P026-P028)
    true_abc: dict[str, bool] = {
        proc: u_x(ns, rep, device_id, proc, seed) < q[f"q_{proc}"]
        for proc in ABC
    }

    # 2) A/B/C chains: attempt 1, retry on first abnormal
    chain: dict[str, tuple[str, ...]] = {}
    expected: dict[tuple[str, int], str] = {}
    for proc in ABC:
        out1 = _kernel_outcome(
            config, true_abc[proc], u_y(ns, rep, device_id, proc, 1, seed), proc
        )
        expected[(proc, 1)] = out1
        if out1 == OUTCOME_ABNORMAL:
            out2 = _kernel_outcome(
                config, true_abc[proc], u_y(ns, rep, device_id, proc, 2, seed), proc
            )
            expected[(proc, 2)] = out2
            chain[proc] = (out1, out2)
        else:
            chain[proc] = (out1,)

    # 3) D materialization (exactly once at A/B/C all-PASS)
    abc_all_pass = all(chain[proc][-1] == OUTCOME_PASS for proc in ABC)
    d_value = D_NOT_CREATED
    if abc_all_pass:
        d_problem = u_d(ns, rep, device_id, seed) < q["q_D"]
        d_value = D_PROBLEM if d_problem else D_NORMAL

    # 4) E chain (only reachable when A/B/C all passed)
    e_chain: tuple[str, ...] = ()
    if abc_all_pass:
        true_e = any(true_abc[proc] for proc in ABC) or d_value == D_PROBLEM
        e1 = _kernel_outcome(
            config, true_e, u_y(ns, rep, device_id, "E", 1, seed), "E"
        )
        expected[("E", 1)] = e1
        if e1 == OUTCOME_ABNORMAL:
            e2 = _kernel_outcome(
                config, true_e, u_y(ns, rep, device_id, "E", 2, seed), "E"
            )
            expected[("E", 2)] = e2
            e_chain = (e1, e2)
        else:
            e_chain = (e1,)

    # 5) terminal state: A/B/C all-PASS is false iff some ABC chain reached
    #    two ABNORMALs (its final is ABNORMAL) -> exit via that chain;
    #    otherwise the only remaining chain is E (exit iff E2 ABNORMAL).
    if not abc_all_pass:
        terminal = TERMINAL_EXITED
    else:
        terminal = (
            TERMINAL_EXITED
            if len(e_chain) == 2 and e_chain[1] == OUTCOME_ABNORMAL
            else TERMINAL_PASSED
        )

    # 6) four-cell category and PL/PW contributions (V3.1 section 5;
    #    P045-P047; 提前退出时 D 不存在, so D only counts when created)
    generated_problems = [proc for proc in ABC if true_abc[proc]]
    if d_value == D_PROBLEM:
        generated_problems.append("D")
    has_problem = bool(generated_problems)
    if terminal == TERMINAL_PASSED:
        category = CATEGORY_BP if has_problem else CATEGORY_GP
        pl = 1 if has_problem else 0
        pw = 0
    else:
        category = CATEGORY_BE if has_problem else CATEGORY_GE
        pl = 0
        pw = 1 if not has_problem else 0

    return OracleDeviceResult(
        device_id=device_id,
        true_terminal_state=terminal,
        d_generated=d_value != D_NOT_CREATED,
        d_value=d_value,
        final_pass_exit=FINAL_PASS if terminal == TERMINAL_PASSED else FINAL_EXIT,
        category=category,
        pl_contribution=pl,
        pw_contribution=pw,
        true_abc=dict(true_abc),
        expected_observations=dict(expected),
    )


# ---------------------------------------------------------------------------
# DES-side facts (event log structure only; DES U values never read)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DesDeviceFact:
    """Per-device structural facts extracted from the DES event log.

    Only structure is extracted (which observations were materialized, the
    recorded terminal/D state and outcome fields).  The DES's recorded ``u`` /
    ``u_key`` / ``true_state`` values are deliberately NOT part of this fact
    set: the canonical world U is recomputed, never copied.
    """

    device_id: int
    terminal_state: str                 # PASSED | EXITED
    d_value: str                        # normal | problem | not_created
    observed_outcomes: dict[tuple[str, int], str]  # (process, attempt) -> recorded outcome


def _empty_device_entry() -> dict[str, Any]:
    return {
        "terminal": None,
        "terminal_count": 0,
        "d": D_NOT_CREATED,
        "d_count": 0,
        "obs": {},
    }


def build_des_device_facts(event_log: Any) -> tuple[dict[int, DesDeviceFact], list[str]]:
    """Parse the event log's quality-relevant structure.

    Returns ``(facts, issues)``: ``facts`` maps device_id -> ``DesDeviceFact``
    for every device with a valid ``DEVICE_TERMINAL``; ``issues`` lists every
    structural problem found (invalid required fields, duplicate observations,
    devices without a terminal, ...).  All other event types (ACTIVITY_*,
    TASK_*, EQUIPMENT_*, TURNOVER_*, SHIFT_CHANGE, WAKE_UP, SIMULATION_END,
    ...) are time-layer records and are deliberately ignored.
    """
    issues: list[str] = []
    devices: dict[int, dict[str, Any]] = {}

    def _bad(loc: str, message: str) -> None:
        issues.append(f"{loc}: {message}")

    if isinstance(event_log, dict) and isinstance(event_log.get("records"), list):
        records_list = event_log["records"]
    elif isinstance(event_log, list):
        records_list = event_log
    else:
        raise QualityOracleInputError(
            "event_log must be a JSON array or an envelope {records: [...]}"
        )

    for idx, rec in enumerate(records_list):
        loc = f"record[{idx}]"
        if not isinstance(rec, dict):
            _bad(loc, "record is not an object")
            continue
        event_type = rec.get("event_type")
        if event_type == "TRUE_STATE_GENERATED":
            dev = rec.get("device_id")
            if not isinstance(dev, int) or dev < 1:
                _bad(loc, f"TRUE_STATE_GENERATED invalid device_id {dev!r}")
                continue
            devices.setdefault(dev, _empty_device_entry())
        elif event_type == "DEVICE_TERMINAL":
            dev = rec.get("device_id")
            terminal = rec.get("terminal_state")
            if not isinstance(dev, int) or dev < 1:
                _bad(loc, f"DEVICE_TERMINAL invalid device_id {dev!r}")
                continue
            if terminal not in (TERMINAL_PASSED, TERMINAL_EXITED):
                _bad(loc, f"DEVICE_TERMINAL invalid terminal_state {terminal!r}")
                continue
            entry = devices.setdefault(dev, _empty_device_entry())
            entry["terminal"] = terminal
            entry["terminal_count"] += 1
        elif event_type == "D_CREATED":
            dev = rec.get("device_id")
            d_state = rec.get("d_state")
            if not isinstance(dev, int) or dev < 1:
                _bad(loc, f"D_CREATED invalid device_id {dev!r}")
                continue
            if d_state not in (D_NORMAL, D_PROBLEM):
                _bad(loc, f"D_CREATED invalid d_state {d_state!r}")
                continue
            entry = devices.setdefault(dev, _empty_device_entry())
            entry["d_count"] += 1
            if entry["d_count"] > 1:
                _bad(loc, f"device {dev}: more than one D_CREATED")
                continue
            entry["d"] = d_state
        elif event_type == "OBSERVATION_MATERIALIZED":
            dev = rec.get("device_id")
            proc = rec.get("process")
            att = rec.get("effective_attempt_no")
            outcome = rec.get("outcome")
            if not isinstance(dev, int) or dev < 1:
                _bad(loc, f"OBSERVATION_MATERIALIZED invalid device_id {dev!r}")
                continue
            if proc not in PROCESSES:
                _bad(loc, f"OBSERVATION_MATERIALIZED invalid process {proc!r}")
                continue
            if att not in (1, 2):
                _bad(loc, f"OBSERVATION_MATERIALIZED invalid effective_attempt_no {att!r}")
                continue
            if outcome not in (OUTCOME_PASS, OUTCOME_ABNORMAL):
                _bad(loc, f"OBSERVATION_MATERIALIZED invalid outcome {outcome!r}")
                continue
            entry = devices.setdefault(dev, _empty_device_entry())
            key = (proc, att)
            if key in entry["obs"]:
                _bad(loc, f"device {dev}: duplicate observation for {key}")
                continue
            entry["obs"][key] = outcome

    facts: dict[int, DesDeviceFact] = {}
    for dev in sorted(devices):
        entry = devices[dev]
        if entry["terminal"] is None:
            issues.append(
                f"device {dev}: no valid DEVICE_TERMINAL in the log "
                f"(incomplete or corrupted log)"
            )
            continue
        if entry["terminal_count"] > 1:
            issues.append(
                f"device {dev}: {entry['terminal_count']} DEVICE_TERMINAL "
                f"records (expected exactly one)"
            )
            continue
        facts[dev] = DesDeviceFact(
            device_id=dev,
            terminal_state=entry["terminal"],
            d_value=entry["d"],
            observed_outcomes=dict(entry["obs"]),
        )
    return facts, issues


# ---------------------------------------------------------------------------
# Comparison and report
# ---------------------------------------------------------------------------


def _categorize_des(terminal_state: str, d_value: str,
                    true_abc: dict[str, bool]) -> tuple[str, int, int]:
    """Four-cell category / PL / PW computed from DES structural facts (the
    terminal state and D value it recorded) plus the oracle's recomputed
    true states (the only true-state source; the DES log's true_state values
    are never read)."""
    generated = [proc for proc in ABC if true_abc[proc]]
    if d_value == D_PROBLEM:
        generated.append("D")
    has_problem = bool(generated)
    if terminal_state == TERMINAL_PASSED:
        return (CATEGORY_BP if has_problem else CATEGORY_GP), (1 if has_problem else 0), 0
    return (CATEGORY_BE if has_problem else CATEGORY_GE), 0, (1 if not has_problem else 0)


@dataclass(frozen=True)
class DeviceComparison:
    """Per-device 对拍 (oracle vs DES): equal, or the precise differences."""

    device_id: int
    equal: bool
    differences: list[str]
    oracle: OracleDeviceResult
    des: Optional[DesDeviceFact]


@dataclass(frozen=True)
class OracleReport:
    """Deterministic report of one oracle run (C06 full-layer 对拍)."""

    verdict: str                        # PASS | FAIL
    comparisons: dict[int, DeviceComparison]
    oracle_aggregate: dict[str, int]    # S/PL/PW/GP/BP/GE/BE/exited
    des_aggregate: dict[str, int]       # S/PL/PW/GP/BP/GE/BE/exited
    issues: list[str]
    config: dict[str, Any]              # canonical frozen subset consumed
    metrics_crosscheck: Optional[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization (sorted keys, exact strings)."""
        return {
            "envelope_type": "g3_quality_oracle_report",
            "schema_version": "g3_quality_oracle_report_v1",
            "registry_version": REGISTRY_VERSION,
            "check_ids": list(CHECK_IDS),
            "verdict": self.verdict,
            "config": self.config,
            "oracle_aggregate": self.oracle_aggregate,
            "des_aggregate": self.des_aggregate,
            "issues": self.issues,
            "devices": {
                str(dev_id): {
                    "device_id": dev_id,
                    "equal": comp.equal,
                    "differences": comp.differences,
                    "oracle": {
                        "true_terminal_state": comp.oracle.true_terminal_state,
                        "d_generated": comp.oracle.d_generated,
                        "d_value": comp.oracle.d_value,
                        "final_pass_exit": comp.oracle.final_pass_exit,
                        "category": comp.oracle.category,
                        "pl_contribution": comp.oracle.pl_contribution,
                        "pw_contribution": comp.oracle.pw_contribution,
                    },
                    "des": (
                        None
                        if comp.des is None
                        else {
                            "terminal_state": comp.des.terminal_state,
                            "d_value": comp.des.d_value,
                            "observed_outcomes": {
                                f"{p},{a}": out
                                for (p, a), out in sorted(comp.des.observed_outcomes.items())
                            },
                        }
                    ),
                }
                for dev_id, comp in sorted(self.comparisons.items())
            },
        }

    def summarize(self) -> str:
        n_equal = sum(1 for c in self.comparisons.values() if c.equal)
        n_total = len(self.comparisons)
        agg = self.oracle_aggregate
        return (
            f"{self.verdict} {n_equal}/{n_total} devices equal "
            f"S={agg['S']} PL={agg['PL']} PW={agg['PW']} "
            f"({len(self.issues)} issues)"
        )


class QualityOracle:
    """The C06 full G3-layer quality-separation oracle.

    Construction requires the parsed frozen config subset and the frozen
    defect probabilities (from parameters.csv); ``check`` then produces the
    per-device 对拍 report against one immutable event log.
    """

    def __init__(self, config: QualityOracleConfig,
                 defect_q: dict[str, Fraction]) -> None:
        self.config = config
        self.q = defect_q

    # -- derivation ---------------------------------------------------------

    def derive_device_final(self, device_id: int) -> OracleDeviceResult:
        """Independent per-device derivation (see :func:`derive_device_final`)."""
        return derive_device_final(self.config, self.q, device_id)

    # -- comparison ---------------------------------------------------------

    def compare_device(self, ores: OracleDeviceResult,
                       dfact: DesDeviceFact) -> DeviceComparison:
        """Compare one oracle derivation against one DES structural fact set."""
        diffs: list[str] = []

        if ores.true_terminal_state != dfact.terminal_state:
            diffs.append(
                f"terminal state: canonical world implies {ores.true_terminal_state}, "
                f"DES recorded {dfact.terminal_state}"
            )
        des_d_generated = dfact.d_value != D_NOT_CREATED
        if ores.d_generated != des_d_generated:
            diffs.append(
                f"D generation: canonical world implies generated={ores.d_generated}, "
                f"DES implies generated={des_d_generated} (d_value={dfact.d_value!r})"
            )
        if ores.d_value != dfact.d_value:
            diffs.append(
                f"D value: canonical world implies {ores.d_value!r}, "
                f"DES recorded {dfact.d_value!r}"
            )
        des_final = FINAL_PASS if dfact.terminal_state == TERMINAL_PASSED else FINAL_EXIT
        if ores.final_pass_exit != des_final:
            diffs.append(
                f"final pass/exit: canonical world implies {ores.final_pass_exit}, "
                f"DES terminal implies {des_final}"
            )
        des_cat, des_pl, des_pw = _categorize_des(
            dfact.terminal_state, dfact.d_value, ores.true_abc
        )
        if ores.category != des_cat:
            diffs.append(
                f"category: canonical world implies {ores.category}, "
                f"DES facts imply {des_cat}"
            )
        if ores.pl_contribution != des_pl:
            diffs.append(
                f"PL contribution: canonical world implies {ores.pl_contribution}, "
                f"DES facts imply {des_pl}"
            )
        if ores.pw_contribution != des_pw:
            diffs.append(
                f"PW contribution: canonical world implies {ores.pw_contribution}, "
                f"DES facts imply {des_pw}"
            )

        # observation-level consistency: every DES-materialized observation
        # must lie in the canonical absorption chain and match the outcome the
        # canonical world implies for that keyed U.
        consumed = set(dfact.observed_outcomes)
        expected = set(ores.expected_observations)
        for key in sorted(consumed):
            if key not in expected:
                diffs.append(
                    f"observation {key[0]},attempt{key[1]}: consumed by the DES but "
                    f"outside the canonical absorption chain"
                )
                continue
            canonical = ores.expected_observations[key]
            recorded = dfact.observed_outcomes[key]
            if canonical != recorded:
                diffs.append(
                    f"observation {key[0]},attempt{key[1]}: canonical world implies "
                    f"{canonical}, DES recorded {recorded}"
                )
        # set relations (separation proposition: a passing device consumes its
        # whole effective-observation band; an exited device consumes a subset
        # -- attempts still in flight at the exit instant are cancelled).
        if ores.true_terminal_state == TERMINAL_PASSED:
            missing = sorted(expected - consumed)
            if missing:
                diffs.append(
                    f"PASSED device missing canonical observations: "
                    f"{[f'{p},attempt{a}' for p, a in missing]}"
                )
        else:
            extra = sorted(consumed - expected)
            if extra:
                diffs.append(
                    f"EXITED device consumed observations outside the canonical "
                    f"chain: {[f'{p},attempt{a}' for p, a in extra]}"
                )

        return DeviceComparison(
            device_id=ores.device_id,
            equal=not diffs,
            differences=diffs,
            oracle=ores,
            des=dfact,
        )

    # -- full check ---------------------------------------------------------

    def check(self, event_log: Any, metrics: Optional[dict[str, Any]] = None) -> OracleReport:
        """Run the full C06 对拍: derive every device, extract the DES facts,
        compare per device, aggregate, and return the report."""
        facts, issues = build_des_device_facts(event_log)
        expected_devices = set(range(1, self.config.batch_size + 1))
        log_devices = set(facts)
        if log_devices != expected_devices:
            extra = sorted(log_devices - expected_devices)
            missing = sorted(expected_devices - log_devices)
            if extra:
                issues.append(
                    f"devices present in the log but outside 1..batch_size: {extra}"
                )
            if missing:
                issues.append(
                    f"devices in 1..batch_size missing from the log: {missing}"
                )

        comparisons: dict[int, DeviceComparison] = {}
        oracle_agg = {
            "S": 0, "PL": 0, "PW": 0, "exited": 0,
            "GP": 0, "BP": 0, "GE": 0, "BE": 0,
        }
        des_agg = {
            "S": 0, "PL": 0, "PW": 0, "exited": 0,
            "GP": 0, "BP": 0, "GE": 0, "BE": 0,
        }
        all_devices = sorted(expected_devices | log_devices)
        for device_id in all_devices:
            ores = self.derive_device_final(device_id)
            oracle_agg["S"] += 1 if ores.true_terminal_state == TERMINAL_PASSED else 0
            oracle_agg["exited"] += 1 if ores.true_terminal_state == TERMINAL_EXITED else 0
            oracle_agg["PL"] += ores.pl_contribution
            oracle_agg["PW"] += ores.pw_contribution
            oracle_agg[ores.category] += 1
            dfact = facts.get(device_id)
            if dfact is None:
                # a device that should exist (or does exist structurally) but
                # has no valid terminal: already reported in issues; still emit
                # the comparison so the report shows the derivation.
                comp = DeviceComparison(
                    device_id=device_id, equal=False,
                    differences=["no valid DES terminal fact to compare"],
                    oracle=ores, des=None,
                )
                comparisons[device_id] = comp
                continue
            comp = self.compare_device(ores, dfact)
            comparisons[device_id] = comp
            des_cat, des_pl, des_pw = _categorize_des(
                dfact.terminal_state, dfact.d_value, ores.true_abc
            )
            des_agg["S"] += 1 if dfact.terminal_state == TERMINAL_PASSED else 0
            des_agg["exited"] += 1 if dfact.terminal_state == TERMINAL_EXITED else 0
            des_agg["PL"] += des_pl
            des_agg["PW"] += des_pw
            des_agg[des_cat] += 1

        metrics_crosscheck: Optional[dict[str, Any]] = None
        if isinstance(metrics, dict):
            metrics_crosscheck = {}
            for name in ("S", "PL", "PW"):
                value = metrics.get(name)
                if value is None:
                    continue
                if not isinstance(value, int):
                    issues.append(f"metrics.{name} must be an int, got {value!r}")
                    continue
                metrics_crosscheck[name] = value
                if value != oracle_agg[name]:
                    issues.append(
                        f"batch aggregate {name}: oracle derives {oracle_agg[name]}, "
                        f"DES metrics report {value}"
                    )

        all_equal = all(comp.equal for comp in comparisons.values())
        verdict = "PASS" if all_equal and not issues else "FAIL"
        return OracleReport(
            verdict=verdict,
            comparisons=comparisons,
            oracle_aggregate=oracle_agg,
            des_aggregate=des_agg,
            issues=issues,
            config=self.config.to_dict(),
            metrics_crosscheck=metrics_crosscheck,
        )


def _load_event_log(event_log: Any) -> Any:
    """Accept a list, an envelope ``{records: [...]}``, or a JSON/JSONL file
    path."""
    if isinstance(event_log, (str, Path)):
        path = Path(event_log)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise QualityOracleInputError(f"cannot read event log: {exc}") from exc
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
                    raise QualityOracleInputError(
                        f"event log line is not valid JSON: {line[:80]!r}"
                    ) from exc
            return records
    return event_log


def check_quality_oracle(
    event_log: Any,
    config: Any,
    parameters_csv: Any = None,
    metrics: Optional[dict[str, Any]] = None,
) -> OracleReport:
    """Run the C06 full G3-layer quality-separation oracle.

    ``event_log``: the DES's immutable event log (list / {records: [...]} /
    JSON or JSONL file path).  ``config``: the frozen ``random_des_config_v1``
    dict (or a ``QualityOracleConfig``).  ``parameters_csv``: the shared
    frozen ``parameters.csv`` (required; supplies P026-P029 defect
    probabilities).  ``metrics``: optional DES run metrics block (S/PL/PW)
    for a batch-aggregate cross-check.
    """
    cfg = parse_config(config)
    if parameters_csv is None:
        raise QualityOracleInputError(
            "parameters_csv is required (shared frozen parameters.csv, "
            "P026-P029 defect probabilities)"
        )
    defect_q = load_parameters(parameters_csv)
    oracle = QualityOracle(cfg, defect_q)
    return oracle.check(_load_event_log(event_log), metrics=metrics)
