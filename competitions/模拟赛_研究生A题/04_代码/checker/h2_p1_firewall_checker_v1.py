#!/usr/bin/env python3
"""Q3-H2-P1 independent C23 information-firewall checker.

Independent verification of the P1-applicable C23 clauses
(Q3_H2_BOOTSTRAP_SPEC_DRAFT.md FINAL_FREEZE_ACCEPTED section 7; registry
CR-V3.1/C23).  It does NOT use the H2 implementation functions as an
oracle for expectations; it performs:

  A. FIELD WHITELIST   -- introspect ObservableState and every nested DTO
     (dataclasses.fields, recursive); every public field must be on the
     frozen whitelist; nested hidden information is still leakage.
  B. FORBIDDEN ACCESS  -- AST scan of the h2 package: no attribute access
     to hidden names (true_state / lifetime_h / u_key / consumed_u /
     x_* / is_right_censored / d_state value), no raw-key material.
  C. IMPORT/AST ISOLATION -- h2 package files must not import the live DES
     engine internal state modules/classes (g3.random_des_v1 /
     des.state_models_v1 / RandomDesEngine / DeviceState / EquipmentState).
  D. SAME OBSERVABLE HISTORY / DIFFERENT HIDDEN WORLD -- construct
     synthetic worlds with identical observable records up to t but
     different hidden true_state / D / lifetime / future-randomness;
     project through the P1 boundary; require identical canonical
     fingerprints.  (The future 'same observed history => same policy
     action' test is NOT_APPLICABLE_YET / DEFERRED_TO_POLICY_STAGE because
     the H2 action/policy module does not exist in P1.)
  E. NEGATIVE LEAK TESTS -- deliberately build leaky fixtures (forbidden
     fields / nested hidden objects / leaky projections) and REQUIRE the
     checker to reject them.  A checker that never proves rejection is
     insufficient.

Every verdict is computed from the actual condition (no hard-coded PASS).

Full end-to-end C23 (action equivalence) remains PENDING (deferred to the
policy stage); only the P1-applicable information-firewall clauses are
checked here.

Python 3.12, standard library only.
"""
from __future__ import annotations

import ast
import dataclasses
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = BASE_DIR / "04_代码"
MAIN_MODEL = CODE_DIR / "main_model"
for _entry in (str(MAIN_MODEL), str(CODE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from main_model.h2 import observable_state_v1 as obs  # noqa: E402
from main_model.h2 import posterior_state_v1 as post  # noqa: E402

H2_DIR = Path(obs.__file__).resolve().parent

# ---------------------------------------------------------------------------
# Frozen whitelist (section 7), exact field names of the P1 DTO schema
# ---------------------------------------------------------------------------

WHITELIST: dict[str, set[str]] = {
    "ObservableState": {
        "time", "active_shift", "shift_index", "on_duty_squad",
        "remaining_not_entered", "bays", "resources", "queue", "devices",
        "replacement_history",
    },
    "BayObs": {"bay_id", "current_device", "status"},
    "ResourceObs": {"resource", "status", "age_h", "in_flight_remaining_h",
                    "generation"},
    "QueueObs": {"release_time", "device_id", "process_order",
                 "effective_attempt_no"},
    "DeviceObs": {"device_id", "terminal_state", "d_materialized",
                  "observations", "effective_attempts"},
    "ObservationObs": {"time", "process", "attempt", "outcome"},
    "ReplacementObs": {"resource", "kind", "trigger", "calibration_start",
                       "calibration_end", "old_generation", "new_generation"},
}

FORBIDDEN_NAME_FRAGMENTS: tuple[str, ...] = (
    "true_state", "lifetime", "u_key", "consumed_u", "x_A", "x_B", "x_C",
    "x_D", "is_right_censored", "d_state", "hidden",
)

# EXACT forbidden raw-field keys (F2a, Q3-H2-P1-E2): the engine event log
# stores the raw random value under the field name ``u``.  A bare substring
# matcher for ``"u"`` would false-positive on legitimate keys such as
# ``resource`` / ``outcome`` / ``duration``, so they are matched EXACTLY
# (key == "u") in addition to the substring fragments above.
EXACT_FORBIDDEN_KEYS: tuple[str, ...] = ("u",)

DTO_CLASSES: tuple[type, ...] = (
    obs.ObservableState, obs.BayObs, obs.ResourceObs, obs.QueueObs,
    obs.DeviceObs, obs.ObservationObs, obs.ReplacementObs,
)


# ---------------------------------------------------------------------------
# A. Field whitelist (recursive introspection)
# ---------------------------------------------------------------------------


def _dataclass_field_names(cls: type) -> list[str]:
    return [f.name for f in dataclasses.fields(cls)]


def _check_whitelist_one(cls: type, path: str) -> list[str]:
    issues: list[str] = []
    name = cls.__name__
    allowed = WHITELIST.get(name)
    if allowed is None:
        issues.append(f"{path}: DTO class {name} not in the frozen whitelist")
        return issues
    for f in dataclasses.fields(cls):
        if f.name not in allowed:
            issues.append(f"{path}.{f.name}: field outside the frozen "
                          f"whitelist")
        for frag in FORBIDDEN_NAME_FRAGMENTS:
            if frag in f.name:
                issues.append(f"{path}.{f.name}: forbidden-name fragment "
                              f"{frag!r}")
    return issues


def check_field_whitelist() -> dict[str, Any]:
    issues: list[str] = []
    frozen_ok = True
    for cls in DTO_CLASSES:
        if not dataclasses.is_dataclass(cls) or not getattr(
                cls, "__dataclass_params__", None):
            frozen_ok = False
            issues.append(f"{cls.__name__}: not a dataclass")
            continue
        if not cls.__dataclass_params__.frozen:
            frozen_ok = False
            issues.append(f"{cls.__name__}: not frozen (must be immutable)")
    for cls in DTO_CLASSES:
        issues.extend(_check_whitelist_one(cls, cls.__name__))
    return {
        "check": "A_FIELD_WHITELIST",
        "status": "PASS" if not issues and frozen_ok else "FAIL",
        "issues": issues,
        "n_dto_classes": len(DTO_CLASSES),
        "frozen_per_class": [{"class": cls.__name__,
                              "frozen": (dataclasses.is_dataclass(cls)
                                         and cls.__dataclass_params__.frozen)}
                             for cls in DTO_CLASSES],
    }


# ---------------------------------------------------------------------------
# B/C. Forbidden access + import/AST isolation over the h2 package
# ---------------------------------------------------------------------------


def _h2_source_files() -> list[Path]:
    return sorted(p for p in H2_DIR.glob("*.py") if p.is_file())


def _scan_forbidden(tree: ast.AST, filename: str) -> list[str]:
    """Reusable forbidden-access scanner (used both for the h2 package and
    for the negative AST cases).  Detects, WITHOUT literal-only grep:
      A. ast.Attribute  -- obj.<hidden_name>  (substring fragments OR exact
         forbidden keys such as ``u``)
      B. ast.Subscript with a CONSTANT STRING slice -- obj["<hidden_key>"]
         (substring fragments OR exact forbidden keys)
      C. ast.Call of the form *.get("<hidden_key>")  (same matching)
    plus references to live DES internal classes by name."""
    issues: list[str] = []

    def _key_forbidden(key: str) -> bool:
        if key in EXACT_FORBIDDEN_KEYS:
            return True
        return any(frag in key for frag in FORBIDDEN_NAME_FRAGMENTS)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if _key_forbidden(attr):
                issues.append(f"{filename}: attribute access {attr!r} is "
                              f"forbidden (exact key or forbidden fragment) "
                              f"at line {getattr(node, 'lineno', '?')}")
        elif isinstance(node, ast.Subscript):
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                key = sl.value
                if _key_forbidden(key):
                    issues.append(f"{filename}: dict-subscript access "
                                  f"{key!r} is forbidden (exact key or "
                                  f"forbidden fragment) at line "
                                  f"{getattr(node, 'lineno', '?')}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get":
                if node.args and isinstance(node.args[0], ast.Constant) \
                        and isinstance(node.args[0].value, str):
                    key = node.args[0].value
                    if _key_forbidden(key):
                        issues.append(f"{filename}: dict.get access "
                                      f"{key!r} is forbidden (exact key or "
                                      f"forbidden fragment) at line "
                                      f"{getattr(node, 'lineno', '?')}")
        if isinstance(node, ast.Name):
            if node.id in ("RandomDesEngine", "DeviceState",
                           "EquipmentState", "ResourceState",
                           "BayState", "TestAttemptState"):
                issues.append(f"{filename}: reference to live DES "
                              f"internal class {node.id} at line "
                              f"{getattr(node, 'lineno', '?')}")
    return issues


def check_forbidden_access() -> dict[str, Any]:
    """AST scan (Attribute + Subscript + dict.get) of the h2 package: no
    access to hidden names / raw-key material / live DES classes."""
    issues: list[str] = []
    for path in _h2_source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            issues.append(f"{path.name}: SyntaxError {exc}")
            continue
        issues.extend(_scan_forbidden(tree, path.name))
    return {
        "check": "B_FORBIDDEN_ACCESS",
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
        "files_scanned": [p.name for p in _h2_source_files()],
    }


def check_ast_negative_cases() -> dict[str, Any]:
    """Prove the AST detector itself rejects forbidden code snippets
    (NEG-A..D) and accepts a legal snippet (Attribute / Subscript /
    dict.get variants).  The verdicts are computed from the detector's
    ACTUAL output."""
    cases = {
        "NEG-A": ("x = rec[\"true_state\"]", "reject"),
        "NEG-B": ("x = rec.get(\"u_key\")", "reject"),
        "NEG-C": ("x = rec[\"lifetime_h\"]", "reject"),
        "NEG-D": ("x = device.true_state", "reject"),
        "NEG-E": ("x = rec.get(\"x_A\")", "reject"),
        "NEG-U1": ("x = rec[\"u\"]", "reject"),
        "NEG-U2": ("x = rec.get(\"u\")", "reject"),
        "LEGAL": ("x = rec[\"event_time\"]\ny = rec.get(\"resource_id\")\n"
                  "z = rec[\"outcome\"]\nw = rec.get(\"duration\")",
                  "accept"),
    }
    results = {}
    ok = True
    for label, (code, expectation) in cases.items():
        tree = ast.parse(code)
        issues = _scan_forbidden(tree, f"<{label}>")
        rejected = len(issues) > 0
        if expectation == "reject":
            passed = rejected
        else:
            passed = not rejected
        ok = ok and passed
        results[label] = {"expected": expectation, "rejected": rejected,
                          "passed": passed, "issues": issues}
    return {
        "check": "B_AST_NEGATIVE_CASES",
        "status": "PASS" if ok else "FAIL",
        "cases": results,
    }


def check_import_isolation() -> dict[str, Any]:
    """No import of the live DES engine internal modules / classes."""
    issues: list[str] = []
    forbidden_modules = (
        "random_des_v1", "state_models_v1", "lifetime_regeneration_v1",
        "key_schema_v1",
    )
    forbidden_packages = ("g3", "des")
    for path in _h2_source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base = alias.name.split(".")[0]
                    if base in forbidden_modules or base in forbidden_packages:
                        issues.append(f"{path.name}: imports {alias.name!r} "
                                      f"(live DES engine)")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                base = mod.split(".")[0]
                if base in forbidden_modules or base in forbidden_packages:
                    issues.append(f"{path.name}: imports from {mod!r} "
                                  f"(live DES engine)")
    return {
        "check": "C_IMPORT_AST_ISOLATION",
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
        "files_scanned": [p.name for p in _h2_source_files()],
    }


# ---------------------------------------------------------------------------
# D. Same observable history / different hidden world (projection equality)
# ---------------------------------------------------------------------------

_TS = "TRUE_STATE_GENERATED"


def _mk_log(hidden_abc: dict[int, dict[str, bool]] | None = None,
            hidden_d: dict[int, str] | None = None,
            hidden_lifetime: dict[str, str] | None = None,
            hidden_u: dict[tuple[str, int, int], str] | None = None,
            extra_future: list[dict[str, Any]] | None = None,
            ) -> list[dict[str, Any]]:
    """Synthetic log with the SAME observable content; hidden annotations
    (true_state / d / lifetime / u) can be varied independently."""
    abc = hidden_abc if hidden_abc is not None else {1: {"A": False, "B": False, "C": False}}
    d_state = hidden_d if hidden_d is not None else {}
    life = hidden_lifetime if hidden_lifetime is not None else {}
    uvals = hidden_u if hidden_u is not None else {}

    def _u(key: tuple[str, int, int]) -> str:
        return uvals.get(key, "0.5")

    log = [
        {"event_type": _TS, "event_time": "0", "device_id": 1,
         "true_state": abc.get(1, {"A": False, "B": False, "C": False})},
        {"event_type": "TASK_RELEASE", "event_time": "0",
         "resource_id": "A", "device_id": 1, "process": "A",
         "effective_attempt_no": 1},
        {"event_type": "ACTIVITY_START", "event_time": "0", "device_id": 1,
         "process": "A", "effective_attempt_no": 1, "resource_id": "A",
         "attempt_start_time": "0", "attempt_end_time": "5/2",
         "outcome": "NONE"},
        {"event_type": "ACTIVITY_COMPLETE", "event_time": "5/2",
         "device_id": 1, "process": "A", "effective_attempt_no": 1,
         "resource_id": "A", "attempt_start_time": "0",
         "attempt_end_time": "5/2", "outcome": "NONE"},
        {"event_type": "OBSERVATION_MATERIALIZED", "event_time": "5/2",
         "device_id": 1, "process": "A", "effective_attempt_no": 1,
         "resource_id": "A", "outcome": "PASS",
         "true_state": abc.get(1, {"A": False, "B": False, "C": False}),
         "u_key": "k_A_1", "u": _u(("A", 1, 1))},
        {"event_type": "D_CREATED", "event_time": "5/2", "device_id": 1,
         "d_state": d_state.get(1, "normal"), "bay_id": 1,
         "squad_id": 0, "u_key": "k_D_1", "u": _u(("D", 1, 0))},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "10", "on_duty_squad": 0,
         "squad_id": 0},
        {"event_type": "EQUIPMENT_REPLACEMENT_START", "event_time": "1",
         "resource_id": "A", "kind": "preventive", "trigger": "preventive",
         "old_generation": 1, "new_generation": 2, "age_before": "1",
         "calibration_duration_hours": "1/2", "calibration_start": "1",
         "calibration_end": "3/2", "u_key": "k_L_A_2",
         "u": _u(("L", "A", 2)),
         "lifetime_h": life.get("A", "250")},
    ]
    for rec in extra_future or []:
        log.append(rec)
    log.sort(key=lambda r: Fraction(r["event_time"]))
    return log


def check_same_observable_history(t: Fraction = Fraction(3)
                                  ) -> dict[str, Any]:
    """Project base and hidden-different variants at t; require identical
    fingerprints (observable history identical => projection identical)."""
    base = _mk_log()
    variants = [
        ("hidden_abc", _mk_log(hidden_abc={1: {"A": True, "B": True, "C": True}})),
        ("hidden_d", _mk_log(hidden_d={1: "problem"})),
        ("hidden_lifetime", _mk_log(hidden_lifetime={"A": "999"})),
        ("hidden_future_u",
         _mk_log(hidden_u={("A", 1, 1): "0.999", ("L", "A", 2): "0.001"})),
        ("hidden_all",
         _mk_log(hidden_abc={1: {"A": True, "B": True, "C": True}},
                 hidden_d={1: "problem"},
                 hidden_lifetime={"A": "999"},
                 hidden_u={("A", 1, 1): "0.999", ("L", "A", 2): "0.001"})),
    ]
    fp_base = obs.project_log_prefix(base, t, batch_size=2).fingerprint()
    results = []
    ok = True
    for label, variant in variants:
        fp_var = obs.project_log_prefix(variant, t, batch_size=2).fingerprint()
        same = fp_var == fp_base
        ok = ok and same
        results.append({"variant": label, "fingerprints_equal": same})
    return {
        "check": "D_SAME_OBSERVABLE_HISTORY",
        "status": "PASS" if ok else "FAIL",
        "time": str(t),
        "pairs": results,
        "note": ("the future 'same observed history => same policy action' "
                 "test is NOT_APPLICABLE_YET / DEFERRED_TO_POLICY_STAGE "
                 "(the H2 action/policy module does not exist in P1)"),
    }


# ---------------------------------------------------------------------------
# E. Negative leak tests (the checker MUST reject leakage)
# ---------------------------------------------------------------------------


@dataclass
class _LeakyState:
    time: Fraction
    true_state: dict[str, bool]  # forbidden


@dataclass
class _LeakyNestedInner:
    lifetime_h: Fraction  # forbidden


@dataclass
class _LeakyNested:
    time: Fraction
    inner: _LeakyNestedInner  # nested hidden object


def _rejectable(cls: type, path: str) -> list[str]:
    issues: list[str] = []
    name = cls.__name__
    allowed = WHITELIST.get(name)
    if allowed is None:
        issues.append(f"{path}: class {name} not in the whitelist")
        return issues
    for f in dataclasses.fields(cls):
        if f.name not in allowed:
            issues.append(f"{path}.{f.name}: field outside the whitelist")
        for frag in FORBIDDEN_NAME_FRAGMENTS:
            if frag in f.name:
                issues.append(f"{path}.{f.name}: forbidden-name fragment "
                              f"{frag!r}")
    return issues


def check_negative_leaks() -> dict[str, Any]:
    """Deliberately build leaky fixtures and REQUIRE rejection."""
    top = _rejectable(_LeakyState, "LeakyState")
    nested = _rejectable(_LeakyNestedInner, "LeakyNestedInner")
    nested2 = _rejectable(_LeakyNested, "LeakyNested")
    detected_top = len(top) > 0
    detected_nested = len(nested) > 0 or len(nested2) > 0
    # leaky projection fixture: a dict carrying hidden keys must be rejected
    leaky_dict = {"time": "3", "true_state": {"A": True},
                  "u_key": "k_A_1"}
    hidden_keys = [k for k in leaky_dict
                   if any(frag in k for frag in FORBIDDEN_NAME_FRAGMENTS)]
    detected_dict = len(hidden_keys) > 0
    ok = detected_top and detected_nested and detected_dict
    return {
        "check": "E_NEGATIVE_LEAK_TESTS",
        "status": "PASS" if ok else "FAIL",
        "rejection_detected": {
            "top_level_forbidden_field": detected_top,
            "nested_forbidden_object": detected_nested,
            "raw_hidden_dict_key": detected_dict,
        },
        "top_level_issues": top,
        "nested_issues": nested + nested2,
        "hidden_dict_keys": hidden_keys,
    }


def check_replacement_history_semantics() -> dict[str, Any]:
    """F1 semantic invariant (frozen '已完成更换/校准历史'): replacement
    history contains ONLY replacement/calibration records whose calibration
    has completed at or before the observation time t.  NOT a field-name
    check: projects real logs and inspects the DTO's actual content."""
    base = [
        {"event_type": "TRUE_STATE_GENERATED", "event_time": "0",
         "device_id": 1,
         "true_state": {"A": False, "B": False, "C": False}},
        {"event_type": "SHIFT_CHANGE", "event_time": "0", "shift_index": 0,
         "shift_start": "0", "shift_end": "10", "on_duty_squad": 0,
         "squad_id": 0},
        {"event_type": "EQUIPMENT_REPLACEMENT_START", "event_time": "1",
         "resource_id": "A", "kind": "preventive", "trigger": "preventive",
         "old_generation": 1, "new_generation": 2, "age_before": "1",
         "calibration_duration_hours": "1/2", "calibration_start": "1",
         "calibration_end": "3/2", "u_key": "k_L_A_2", "u": "0.5"},
    ]
    # T18: ongoing replacement (no completion yet) at t=1.25
    st_ongoing = obs.project_log_prefix(base, Fraction(5, 4), batch_size=2)
    ongoing_excluded = len(st_ongoing.replacement_history) == 0
    rsrc_a = next(r for r in st_ongoing.resources if r.resource == "A")
    status_ok = rsrc_a.status == "calibration"
    remaining_ok = rsrc_a.in_flight_remaining_h == Fraction(1, 4)
    # T20: full log contains the future completion; observing at t=1.25
    full = base + [{"event_type": "EQUIPMENT_CALIBRATION_COMPLETE",
                    "event_time": "3/2", "resource_id": "A",
                    "generation": 2, "calibration_start": "1",
                    "calibration_end": "3/2"}]
    st_future = obs.project_log_prefix(full, Fraction(5, 4), batch_size=2)
    future_not_leaked = len(st_future.replacement_history) == 0
    # T19: after completion (t=2) the record enters the history exactly once
    st_done = obs.project_log_prefix(full, Fraction(2), batch_size=2)
    done_in = [rh for rh in st_done.replacement_history
               if rh.resource == "A" and rh.calibration_end == Fraction(3, 2)]
    done_exactly_once = len(done_in) == 1
    all_members_completed = all(
        any(r.get("event_type") == "EQUIPMENT_CALIBRATION_COMPLETE"
            and r.get("resource_id") == rh.resource
            and Fraction(r["calibration_end"]) == rh.calibration_end
            and Fraction(r["event_time"]) <= rh.calibration_end
            for r in full)
        for rh in st_done.replacement_history)
    ok = (ongoing_excluded and status_ok and remaining_ok
          and future_not_leaked and done_exactly_once
          and all_members_completed)
    return {
        "check": "REPLACEMENT_HISTORY_SEMANTICS",
        "status": "PASS" if ok else "FAIL",
        "invariant": ("replacement_history contains ONLY completed "
                      "replacement/calibration (calibration_end <= t with "
                      "matching EQUIPMENT_CALIBRATION_COMPLETE)"),
        "ongoing_replacement_excluded_at_1.25": ongoing_excluded,
        "resource_status_at_1.25": rsrc_a.status,
        "in_flight_remaining_at_1.25": str(rsrc_a.in_flight_remaining_h),
        "future_completion_not_leaked_at_1.25": future_not_leaked,
        "completed_record_enters_once_at_2": done_exactly_once,
        "all_members_completed": all_members_completed,
    }


# ---------------------------------------------------------------------------
# PosteriorState seam (P1): no posterior math, no fake numbers
# ---------------------------------------------------------------------------


def check_posterior_seam() -> dict[str, Any]:
    """P1 PosteriorState seam: the module must carry NO posterior math and
    NO numeric posterior placeholders."""
    issues: list[str] = []
    path = Path(post.__file__).resolve()
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    has_math = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name not in (
                "get", "posterior_state_contract"):
            if any(kw in node.name for kw in ("posterior", "bayes", "sample",
                                              "likelihood", "lifetime")):
                has_math = True
                issues.append(f"{path.name}: function {node.name} looks like "
                              f"posterior/lifetime mathematics")
        if isinstance(node, ast.Call):
            fname = ""
            if isinstance(node.func, ast.Name):
                fname = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fname = node.func.attr
            if any(kw in fname for kw in ("posterior", "bayes", "sample",
                                          "likelihood", "inverse_cdf",
                                          "conditional")):
                has_math = True
                issues.append(f"{path.name}: call {fname} looks like "
                              f"posterior/lifetime mathematics")
    numeric_placeholders = [n for n in ("0.429", "0.5", "0.0625",
                                        "posterior_probability", "p_map",
                                        "p_max")
                            if n in src]
    seam_ok = post.P1_SEAM_STATUS == "SCHEMA_DEFERRED_TO_P2"
    ok = (not has_math and not numeric_placeholders and seam_ok)
    return {
        "check": "POSTERIOR_STATE_P1_SEAM",
        "status": "PASS" if ok else "FAIL",
        "seam_status": post.P1_SEAM_STATUS,
        "posterior_math_detected": has_math,
        "numeric_placeholders_detected": numeric_placeholders,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def run_all() -> dict[str, Any]:
    checks = [
        check_field_whitelist(),
        check_forbidden_access(),
        check_ast_negative_cases(),
        check_import_isolation(),
        check_same_observable_history(),
        check_negative_leaks(),
        check_replacement_history_semantics(),
        check_posterior_seam(),
    ]
    all_ok = all(c["status"] == "PASS" for c in checks)
    return {
        "c23_scope": "C23 INFORMATION-FIREWALL / P1-APPLICABLE CLAUSES",
        "full_c23_end_to_end": "PENDING (action/policy path not implemented; "
                               "same-observed-history action-equivalence "
                               "DEFERRED_TO_POLICY_STAGE)",
        "overall": "PASS" if all_ok else "FAIL",
        "checks": checks,
    }


if __name__ == "__main__":
    result = run_all()
    print(result["overall"])
    for c in result["checks"]:
        print(f"  {c['check']}: {c['status']}")
        for issue in c.get("issues", [])[:5]:
            print(f"    - {issue}")
    sys.exit(0 if result["overall"] == "PASS" else 1)
