# -*- coding: utf-8 -*-
"""E2 independent checker for the frozen G2-02 Q1 probability & quality chain.

Role
----
This module is the INDEPENDENT oracle (E2) for task package G2-02-SPEC-V1.0.3
("Q1 概率与质量解析链闭合").  It re-derives every public quantity of an E1
``q1_response`` envelope from first principles and compares it against the
response, producing a ``q1_check_report`` envelope.

Isolation
---------
* It never imports, reads, or executes anything under ``04_代码/main_model/``
  (the main implementation) nor any other checker module.
* It never reads request files (its CLI has no request option), the external
  oracle fixture ``04_代码/tests/fixtures/q1_quality_oracles_v1.json``, nor any
  project documentation.  The only oracle expectations embedded in this task
  are the ``E2_embedded_oracles`` cases, which are consumed exclusively by the
  unit tests (not by the checker runtime).
* q_E / fourfold / lambda / tilde / counts are recomputed with this module's
  own 16-state summation over H in {A,B,C,D} (``_sixteen_state``), written
  from scratch with ``Fraction`` (exact rationals) or ``Decimal`` (>= 120
  precision).  The E-stage kernel is solved with this module's own frozen
  independent algorithm: closed-form back-substitution for
  ``single_test_unconditional_v1``, and outer-alpha bisection with inner-beta
  back-substitution for ``standard_chain_v1``.  Neither the main solver nor
  the G2-01 checker is imported or copied.

Inputs
------
Only the task package, the shared schema, ``parameters.csv`` and the raw
response are consumed.  Per the interface contract the E2 CLI is
``q1_quality_checker_v1.py --response <r.json> --parameters <p.csv>
--upstream <u.json> --schema <s.json> --task-package <t.yaml>
--report <check_report.json>`` and the ``--request`` option is forbidden.

Exit codes (frozen): 0 PASS, 1 FAIL, 2 validation (preflight or
response/schema/parameters), 3 checker numerical failure, 4 file I/O.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction

# --------------------------------------------------------------------------
# Frozen constants (from task package G2-02-SPEC-V1.0.3 and shared schema)
# --------------------------------------------------------------------------

SCHEMA_VERSION = "q1_quality_v1"
ENVELOPE_RESPONSE = "q1_response"
ENVELOPE_REPORT = "q1_check_report"

SEMANTICS_SINGLE = "single_test_unconditional_v1"
SEMANTICS_CHAIN = "standard_chain_v1"
SEMANTICS = (SEMANTICS_SINGLE, SEMANTICS_CHAIN)

SCENARIO_ROLES = ("canonical_g2_02", "generic", "test_oracle")
SCENARIO_CANONICAL = "canonical_g2_02"

OVERALL_STATUSES = (
    "ALL_ROUTES_AGREE",
    "ROUTE_MISMATCH",
    "HAS_INFEASIBLE",
    "HAS_INDETERMINATE",
    "FAILED_VALIDATION",
    "NUMERICAL_FAILURE",
)
PROCESS_STATUSES = ("UNIQUE_SOLUTION", "NONIDENTIFIABLE_FAMILY", "INFEASIBLE")
INFEASIBLE_STAGES = ("ABC_KERNEL", "E_KERNEL")
PROCESSES = ("A", "B", "C")

RUN_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{12}Z_[0-9a-f]{8}$")

# Decimal string patterns from the frozen schema.
DEC_PROB_RE = re.compile(r"^(0(?:\.[0-9]+)?|1(?:\.0+)?)$")
DEC_SIGNED_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
DEC_NONNEG_RE = re.compile(r"^(0|[1-9][0-9]*)(?:\.[0-9]+)?$")

# Frozen numeric-policy tolerances (fallbacks; the frozen task package
# ``numeric_policy.tolerances`` values are parsed at runtime and take
# precedence -- they must never be relaxed, only read verbatim).
TOL_QE_DIST = "1e-15"        # cross_channel_qE_distribution_absolute
TOL_KERNEL = "5e-11"         # cross_channel_kernel_alpha_beta_absolute
TOL_E_MAX = "5e-12"          # cross_channel_e_max_absolute
TOL_AGGREGATE = "1e-9"       # cross_channel_aggregate_absolute
TOL_CONSERVATION = "1e-15"   # conservation_absolute
TOL_CROSS_ROUTE = "1e-15"    # cross_route_absolute
TOL_RESIDUAL = "2e-12"       # E2_independent_residual_absolute

DEFAULT_PRECISION = 160  # p0 = max(120, 17+80) = 120; 160 is comfortably above.
KERNEL_PRECISION = 220   # p0 adaptive up to p0+800; fixed upper bound used here.
SIGNIFICANT_DIGITS = 17  # public serialization: significant_decimal_digits


class CheckerValidationError(Exception):
    """Response/schema/parameters/task-package validation failure (exit 2)."""


class CheckerPreflightError(Exception):
    """Report-context preflight failure (exit 2; report must stay untouched)."""


class CheckerNumericalError(Exception):
    """Checker's own numerical failure (exit 3)."""


class CheckerIOError(Exception):
    """File I/O or unrecoverable serialization failure (exit 4)."""


class _YamlParseError(Exception):
    pass


# --------------------------------------------------------------------------
# Minimal YAML-subset parser for the frozen task package
# --------------------------------------------------------------------------

def _yaml_tokens(text):
    """Tokenize a YAML-subset document: (indent, kind, payload, raw)."""
    toks = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        s = raw.strip()
        if s == "-" or s.startswith("- "):
            val = s[1:].strip()
            toks.append((indent, "item", val, raw))
        else:
            if ":" in s:
                k, v = s.split(":", 1)
                toks.append((indent, "key", (k.strip(), v.strip()), raw))
            else:
                toks.append((indent, "key", (s, ""), raw))
    return toks


def _is_block_scalar(v):
    return v in ("|", ">", "|-", ">-", "|+", ">+") or (
        len(v) >= 2 and v[0] in "|>" and v[1:].isdigit()
    )


def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v in ("null", "~", "NULL", "None"):
        return None
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    return v


def parse_simple_yaml(text):
    """Parse the YAML subset used by the frozen G2-02 task package.

    Supports indent-nested mappings, sequences of scalars and of mappings,
    plain/quoted scalars, full-line comments, block scalars (|/>, with
    chomping indicators), and inline flow maps ``{...}`` kept as opaque
    strings.  Returns nested dicts/lists/scalars.
    """

    toks = _yaml_tokens(text)
    if not toks:
        return {}
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def consume_block_lines(indent):
        parts = []
        while True:
            n = peek()
            if n is None or n[0] <= indent:
                break
            pos[0] += 1
            parts.append(n[3][n[0]:])
        return "\n".join(parts)

    def parse_map(indent):
        node = {}
        while True:
            t = peek()
            if t is None or t[0] != indent or t[1] != "key":
                break
            pos[0] += 1
            k, v = t[2]
            if _is_block_scalar(v):
                node[k] = consume_block_lines(indent)
            elif v == "":
                nxt = peek()
                if nxt is not None and nxt[0] > indent:
                    node[k] = parse_block(nxt[0])
                else:
                    node[k] = None
            elif v.startswith("{") or v.startswith("["):
                node[k] = v
            else:
                node[k] = _scalar(v)
        return node

    def parse_seq(indent):
        node = []
        while True:
            t = peek()
            if t is None or t[0] != indent or t[1] != "item":
                break
            pos[0] += 1
            val = t[2]
            if val == "":
                nxt = peek()
                if nxt is not None and nxt[0] > indent:
                    node.append(parse_block(nxt[0]))
                else:
                    node.append(None)
            elif val.startswith("{") or val.startswith("["):
                node.append(val)
            elif ":" in val and not _is_block_scalar(val):
                k, v = val.split(":", 1)
                k = k.strip()
                v = v.strip()
                item = {}
                if _is_block_scalar(v):
                    item[k] = consume_block_lines(indent)
                elif v == "":
                    nxt = peek()
                    if nxt is not None and nxt[0] > indent:
                        item[k] = parse_block(nxt[0])
                    else:
                        item[k] = None
                else:
                    item[k] = _scalar(v)
                nxt = peek()
                if nxt is not None and nxt[0] > indent:
                    sub = parse_map(nxt[0])
                    for sk, sv in sub.items():
                        item[sk] = sv
                node.append(item)
            else:
                node.append(_scalar(val))
        return node

    def parse_block(indent):
        first = peek()
        if first is None or first[0] < indent:
            return None
        if first[0] != indent:
            raise _YamlParseError("unexpected indentation in task package YAML")
        if first[1] == "item":
            return parse_seq(indent)
        return parse_map(indent)

    return parse_block(toks[0][0])


# --------------------------------------------------------------------------
# Decimal helpers
# --------------------------------------------------------------------------

def parse_finite_decimal(s, what="value"):
    """Parse a finite decimal string; exponent/NaN/Inf spelling is rejected."""
    if not isinstance(s, str):
        raise CheckerValidationError("%s must be a decimal string, got %r" % (what, s))
    if re.search(r"[eE]", s):
        raise CheckerValidationError("%s must not use exponent spelling: %r" % (what, s))
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise CheckerValidationError("invalid decimal %s: %r" % (what, s))
    if not d.is_finite():
        raise CheckerValidationError("non-finite decimal %s: %r" % (what, s))
    return d


def to_public(x, sig=SIGNIFICANT_DIGITS):
    """Serialize a Decimal to ``sig`` significant digits, plain notation,
    no exponent, no trailing zeros; negative zero normalized to 0."""
    d = Decimal(x)
    if d == 0:
        return "0"
    s = format(d, ".%dE" % (sig - 1))
    if "E" not in s:
        return s
    mant, exp_s = s.split("E")
    exp = int(exp_s)
    neg = mant.startswith("-")
    if neg:
        mant = mant[1:]
    ip, fp = mant.split(".")
    digits = ip + fp
    if exp >= 0:
        point_pos = len(ip) + exp
        if point_pos >= len(digits):
            out = digits + "0" * (point_pos - len(digits))
        else:
            out = digits[:point_pos] + "." + digits[point_pos:]
    else:
        out = "0." + "0" * (-exp - 1) + digits
    out = out.rstrip("0")
    if out.endswith("."):
        out = out[:-1]
    if out == "":
        out = "0"
    if neg and out != "0":
        out = "-" + out
    return out


# --------------------------------------------------------------------------
# Independent E-stage kernel solve (frozen algorithm, self-contained)
# --------------------------------------------------------------------------

def solve_kernel_single(q, e, Num, prec):
    """Closed-form back-substitution for single_test_unconditional_v1.

    Equations (frozen): (1-q)*alpha = q*beta = e/2, i.e. alpha = e/(2(1-q)),
    beta = e/(2q); feasibility e <= 2*min(q,1-q).
    """
    one = Num(1)
    emax = 2 * (q if q < one - q else one - q)
    if e > emax:
        return {
            "status": "INFEASIBLE",
            "alpha": None,
            "beta": None,
            "e_max": emax,
            "free_parameters": [],
            "method": "closed_form_back_substitution",
            "feasibility": "INFEASIBLE",
            "residual_balance": None,
            "residual_total": None,
        }
    if q == 0:
        if e == 0:
            return {
                "status": "NONIDENTIFIABLE_FAMILY",
                "alpha": 0,
                "beta": None,
                "e_max": emax,
                "free_parameters": ["beta"],
                "method": "closed_form_back_substitution",
                "feasibility": "FEASIBLE",
                "residual_balance": None,
                "residual_total": None,
            }
        return {
            "status": "INFEASIBLE",
            "alpha": None,
            "beta": None,
            "e_max": emax,
            "free_parameters": [],
            "method": "closed_form_back_substitution",
            "feasibility": "INFEASIBLE",
            "residual_balance": None,
            "residual_total": None,
        }
    if q == 1:
        if e == 0:
            return {
                "status": "NONIDENTIFIABLE_FAMILY",
                "alpha": None,
                "beta": 0,
                "e_max": emax,
                "free_parameters": ["alpha"],
                "method": "closed_form_back_substitution",
                "feasibility": "FEASIBLE",
                "residual_balance": None,
                "residual_total": None,
            }
        return {
            "status": "INFEASIBLE",
            "alpha": None,
            "beta": None,
            "e_max": emax,
            "free_parameters": [],
            "method": "closed_form_back_substitution",
            "feasibility": "INFEASIBLE",
            "residual_balance": None,
            "residual_total": None,
        }
    alpha = e / (2 * (one - q))
    beta = e / (2 * q)
    residual_balance = (one - q) * alpha - q * beta
    residual_total = (one - q) * alpha + q * beta - e
    if Num is Decimal:
        with localcontext() as ctx:
            ctx.prec = prec
            if abs(residual_balance) > Decimal(TOL_RESIDUAL) or abs(residual_total) > Decimal(TOL_RESIDUAL):
                raise CheckerNumericalError(
                    "single kernel residual too large: balance=%s total=%s" % (residual_balance, residual_total)
                )
    return {
        "status": "UNIQUE_SOLUTION",
        "alpha": alpha,
        "beta": beta,
        "e_max": emax,
        "free_parameters": [],
        "method": "closed_form_back_substitution",
        "feasibility": "FEASIBLE",
        "residual_balance": residual_balance,
        "residual_total": residual_total,
    }


def _chain_domain(q):
    """Upper end of the feasible alpha domain for the standard chain."""
    if q == 0:
        return Decimal(0)
    if q == 1:
        return Decimal(1)
    c = 1 - q
    alpha_max = (-1 + (1 + 4 * q / c).sqrt()) / 2
    return min(Decimal(1), alpha_max)


def _chain_e_at(q, a):
    """e(alpha) = total misclassification / total tests in the chain population."""
    c = 1 - q
    S = c * a * (1 + a) / q
    if S > 1:
        S = Decimal(1)
    b = 1 - (1 - S).sqrt()
    v = 2 * b - b * b
    e_tests = 1 + c * a + q * (1 - b)
    return (c * a * (1 + a) + q * v) / e_tests


def _chain_emax(q, prec):
    """e_max(q) = max_{alpha in [0, a_dom]} e(alpha); golden-section search."""
    with localcontext() as ctx:
        ctx.prec = prec
        if q == 0 or q == 1:
            return Decimal(0)
        a_dom = _chain_domain(q)
        gr = (Decimal(5).sqrt() - 1) / 2
        lo = Decimal(0)
        hi = a_dom
        x1 = hi - gr * (hi - lo)
        x2 = lo + gr * (hi - lo)
        f1 = _chain_e_at(q, x1)
        f2 = _chain_e_at(q, x2)
        for _ in range(300):
            if f1 < f2:
                lo = x1
                x1 = x2
                f1 = f2
                x2 = lo + gr * (hi - lo)
                f2 = _chain_e_at(q, x2)
            else:
                hi = x2
                x2 = x1
                f2 = f1
                x1 = hi - gr * (hi - lo)
                f1 = _chain_e_at(q, x1)
        best = f1 if f1 > f2 else f2
        end = _chain_e_at(q, a_dom)
        if end > best:
            best = end
        zero = _chain_e_at(q, Decimal(0))
        if zero > best:
            best = zero
        return best


def _chain_residual(q, e, a):
    """h(alpha) = misclassification total - e * E[tests] for the standard chain."""
    c = 1 - q
    S = c * a * (1 + a) / q
    if S > 1:
        S = Decimal(1)
    b = 1 - (1 - S).sqrt()
    v = 2 * b - b * b
    e_tests = 1 + c * a + q * (1 - b)
    return c * a * (1 + a) + q * v - e * e_tests


def _chain_beta(q, a, prec):
    """Inner beta back-substitution from the balance equation."""
    c = 1 - q
    S = c * a * (1 + a) / q
    if S > 1:
        S = Decimal(1)
    return 1 - (1 - S).sqrt()


def solve_kernel_chain(q, e, prec):
    """Independent solve for standard_chain_v1.

    Outer bisection on alpha with inner beta back-substitution
    (beta = 1 - sqrt(1 - (1-q)alpha(1+alpha)/q)); the frozen equations are

      (1-q)*alpha*(1+alpha) = q*(2*beta - beta^2)      (balance)
      (1-q)*alpha*(1+alpha) + q*(2*beta - beta^2)
          = e * (1 + (1-q)*alpha + q*(1-beta))         (event-population closure)

    Feasibility iff e <= e_max(q).
    """
    with localcontext() as ctx:
        ctx.prec = prec
        if q == 0:
            if e == 0:
                return {
                    "status": "NONIDENTIFIABLE_FAMILY",
                    "alpha": Decimal(0),
                    "beta": None,
                    "e_max": Decimal(0),
                    "free_parameters": ["beta"],
                    "method": "alpha_bisection_beta_backsubstitution",
                    "feasibility": "FEASIBLE",
                    "residual_balance": Decimal(0),
                    "residual_total": Decimal(0),
                }
            return {
                "status": "INFEASIBLE",
                "alpha": None,
                "beta": None,
                "e_max": Decimal(0),
                "free_parameters": [],
                "method": "alpha_bisection_beta_backsubstitution",
                "feasibility": "INFEASIBLE",
                "residual_balance": None,
                "residual_total": None,
            }
        if q == 1:
            if e == 0:
                return {
                    "status": "NONIDENTIFIABLE_FAMILY",
                    "alpha": None,
                    "beta": Decimal(0),
                    "e_max": Decimal(0),
                    "free_parameters": ["alpha"],
                    "method": "alpha_bisection_beta_backsubstitution",
                    "feasibility": "FEASIBLE",
                    "residual_balance": Decimal(0),
                    "residual_total": Decimal(0),
                }
            return {
                "status": "INFEASIBLE",
                "alpha": None,
                "beta": None,
                "e_max": Decimal(0),
                "free_parameters": [],
                "method": "alpha_bisection_beta_backsubstitution",
                "feasibility": "INFEASIBLE",
                "residual_balance": None,
                "residual_total": None,
            }
        emax = _chain_emax(q, prec)
        if e > emax:
            return {
                "status": "INFEASIBLE",
                "alpha": None,
                "beta": None,
                "e_max": emax,
                "free_parameters": [],
                "method": "alpha_bisection_beta_backsubstitution",
                "feasibility": "INFEASIBLE",
                "residual_balance": None,
                "residual_total": None,
            }
        if e == 0:
            return {
                "status": "UNIQUE_SOLUTION",
                "alpha": Decimal(0),
                "beta": Decimal(0),
                "e_max": emax,
                "free_parameters": [],
                "method": "alpha_bisection_beta_backsubstitution",
                "feasibility": "FEASIBLE",
                "residual_balance": Decimal(0),
                "residual_total": Decimal(0),
            }
        a_dom = _chain_domain(q)
        lo = Decimal(0)
        hi = a_dom
        h_lo = _chain_residual(q, e, lo)
        h_hi = _chain_residual(q, e, hi)
        if h_lo > 0 or h_hi < 0:
            # Defensive: locate an interior sign change on a fine grid.
            grid_lo = lo
            grid_hi = hi
            found = False
            n = 4000
            for i in range(1, n + 1):
                a = hi * i / n
                if _chain_residual(q, e, a) >= 0:
                    grid_hi = a
                    grid_lo = hi * (i - 1) / n
                    found = True
                    break
            if not found:
                raise CheckerNumericalError(
                    "chain kernel: no sign change on feasible alpha domain (q=%s e=%s)" % (q, e)
                )
            lo = grid_lo
            hi = grid_hi
        for _ in range(600):
            mid = (lo + hi) / 2
            if _chain_residual(q, e, mid) > 0:
                hi = mid
            else:
                lo = mid
        alpha = (lo + hi) / 2
        beta = _chain_beta(q, alpha, prec)
        # residual check (frozen E2_independent_residual_absolute = 2e-12)
        c = 1 - q
        v = 2 * beta - beta * beta
        e_tests = 1 + c * alpha + q * (1 - beta)
        res_balance = c * alpha * (1 + alpha) - q * v
        res_total = c * alpha * (1 + alpha) + q * v - e * e_tests
        tol = Decimal(TOL_RESIDUAL)
        if abs(res_balance) > tol or abs(res_total) > tol:
            raise CheckerNumericalError(
                "chain kernel residual too large: balance=%s total=%s (q=%s e=%s)"
                % (res_balance, res_total, q, e)
            )
        return {
            "status": "UNIQUE_SOLUTION",
            "alpha": alpha,
            "beta": beta,
            "e_max": emax,
            "free_parameters": [],
            "method": "alpha_bisection_beta_backsubstitution",
            "feasibility": "FEASIBLE",
            "residual_balance": res_balance,
            "residual_total": res_total,
        }


def solve_kernel(q, e, semantics, Num=Decimal, prec=DEFAULT_PRECISION):
    """Independent kernel solve / classification for a process (A/B/C/E)."""
    if semantics == SEMANTICS_SINGLE:
        qv, ev = (Fraction(q), Fraction(e)) if Num is Fraction else (Decimal(q), Decimal(e))
        return solve_kernel_single(qv, ev, Num, max(prec, KERNEL_PRECISION))
    if semantics == SEMANTICS_CHAIN:
        if Num is Fraction:
            # Only rational sub-cases (e==0 and the q endpoints) are supported
            # in Fraction mode; anything else requires Decimal downstream.
            dec_q = Decimal(q)
            dec_e = Decimal(e)
            kr = solve_kernel_chain(dec_q, dec_e, max(prec, KERNEL_PRECISION))
            kr = dict(kr)
            if kr["alpha"] is not None:
                kr["alpha"] = Fraction(0) if kr["alpha"] == 0 else None
            if kr["beta"] is not None:
                kr["beta"] = Fraction(0) if kr["beta"] == 0 else None
            return kr
        return solve_kernel_chain(Decimal(q), Decimal(e), max(prec, KERNEL_PRECISION))
    raise CheckerValidationError("unknown semantics: %r" % (semantics,))


# --------------------------------------------------------------------------
# 16-state enumeration (this module's own summation code)
# --------------------------------------------------------------------------

def _kernel_numeric(kern, Num):
    """Identified alpha/beta for the 16-state sum; free parameters -> 0."""
    a = kern["alpha"] if kern["alpha"] is not None else Num(0)
    b = kern["beta"] if kern["beta"] is not None else Num(0)
    return a, b


def _sixteen_state(q_a, q_b, q_c, q_d, e_a, e_b, e_c, e_e,
                   ka, kb, kc, Num, prec):
    """Sum over the 16 states H = (x_A, x_B, x_C, x_D).

    Index i = x_A + 2*x_B + 4*x_C + 8*x_D (A is the lowest bit), matching the
    frozen ``reach_E_distribution`` ordering.  D is split by its prior q_D at
    the E entry (its state does not affect the reach probability), per the
    frozen rule "E 入口按 q_D 分裂 D".

    Returns un-normalized numerators; E-stage quantities are finalized by the
    caller after the E kernel is solved.
    """
    one = Num(1)
    zero = Num(0)
    qs = {"A": q_a, "B": q_b, "C": q_c, "D": q_d}
    kernels = {"A": ka, "B": kb, "C": kc}
    u = {}
    v = {}
    for j in "ABC":
        a, b = _kernel_numeric(kernels[j], Num)
        u[j] = one - a * a
        v[j] = 2 * b - b * b
    G = zero
    Z0 = zero
    Z1 = zero
    reach_raw = [zero] * 16
    lam_num = {"A": zero, "B": zero, "C": zero, "D": zero}
    tilde_num = {"A": zero, "B": zero, "C": zero, "D": zero}
    p_ge_preE = zero  # exit before E with A/B/C all normal (D not generated)
    for i in range(16):
        xA = i & 1
        xB = (i >> 1) & 1
        xC = (i >> 2) & 1
        xD = (i >> 3) & 1
        pH = one
        for j, x in (("A", xA), ("B", xB), ("C", xC), ("D", xD)):
            pH = pH * (qs[j] if x else one - qs[j])
        reach = one
        for j in "ABC":
            x = {"A": xA, "B": xB, "C": xC}[j]
            reach = reach * (v[j] if x else u[j])
        G = G + pH * reach
        reach_raw[i] = pH * reach
        hsize = xA + xB + xC + xD
        if hsize == 0:
            Z0 = Z0 + pH * reach
        else:
            Z1 = Z1 + pH * reach
        members = []
        if xA:
            members.append("A")
        if xB:
            members.append("B")
        if xC:
            members.append("C")
        if xD:
            members.append("D")
        if members:
            w = one / Num(hsize)
            for m in members:
                lam_num[m] = lam_num[m] + pH * reach * w
            for m in members:
                tilde_num[m] = tilde_num[m] + pH * reach
        if xA == 0 and xB == 0 and xC == 0:
            p_ge_preE = p_ge_preE + pH * (one - reach)
    return {
        "G": G,
        "Z0": Z0,
        "Z1": Z1,
        "reach_raw": reach_raw,
        "lam_num": lam_num,
        "tilde_num": tilde_num,
        "p_ge_preE": p_ge_preE,
    }


def compute_q1_full(semantics, q_a, q_b, q_c, q_d, e_a, e_b, e_c, e_e,
                    ka, kb, kc, Num=Decimal, prec=DEFAULT_PRECISION):
    """Full independent Q1 chain from raw inputs and A/B/C kernel dicts.

    ``ka/kb/kc`` are kernel dicts with keys alpha/beta/status/free_parameters.
    All downstream quantities are produced by this module's own 16-state
    summation and the frozen E-kernel solve.  Returns a plain dict of
    independent values.
    """
    if Num is Fraction and semantics == SEMANTICS_CHAIN:
        for kern in (ka, kb, kc):
            if kern["status"] == "UNIQUE_SOLUTION":
                a = kern["alpha"]
                if a is not None and not isinstance(a, Fraction):
                    raise CheckerValidationError(
                        "chain kernels with e>0 require Decimal arithmetic"
                    )
    with localcontext() as ctx:
        ctx.prec = max(prec, KERNEL_PRECISION)
        one = Num(1)
        s16 = _sixteen_state(q_a, q_b, q_c, q_d, e_a, e_b, e_c, e_e,
                             ka, kb, kc, Num, prec)
        G = s16["G"]
        Z0 = s16["Z0"]
        Z1 = s16["Z1"]
        if G == 0:
            raise CheckerNumericalError("unconditional reach probability G is zero")
        q_E = Z1 / G
        reach_dist = [r / G for r in s16["reach_raw"]]
        # --- E kernel independent solve ---
        ek = solve_kernel(q_E, e_e, semantics, Num, prec)
        # --- finalize downstream ---
        if ek["status"] == "INFEASIBLE":
            return {
                "overall_status": "HAS_INFEASIBLE",
                "infeasible_stage": "E_KERNEL",
                "abc_kernels": None,
                "q_E": q_E,
                "G": G,
                "Z_0": Z0,
                "Z_1": Z1,
                "reach_E_distribution": reach_dist,
                "E_kernel": ek,
                "E_rates": None,
                "fourfold": None,
                "anchors": None,
                "lambda": None,
                "multinomial": None,
            }
        if ek["status"] == "NONIDENTIFIABLE_FAMILY":
            # zero-weight analysis: free beta weight q_E & Z_1; free alpha
            # weight 1-q_E & Z_0.  At the endpoints the free parameter always
            # vanishes, so the downstream stays determined.
            free = ek["free_parameters"]
            if "beta" in free and not (q_E == 0):
                return {
                    "overall_status": "HAS_INDETERMINATE",
                    "infeasible_stage": "E_KERNEL",
                    "abc_kernels": None,
                    "q_E": q_E,
                    "G": G,
                    "Z_0": Z0,
                    "Z_1": Z1,
                    "reach_E_distribution": reach_dist,
                    "E_kernel": ek,
                    "E_rates": None,
                    "fourfold": None,
                    "anchors": None,
                    "lambda": None,
                    "multinomial": None,
                }
            if "alpha" in free and not (q_E == 1):
                return {
                    "overall_status": "HAS_INDETERMINATE",
                    "infeasible_stage": "E_KERNEL",
                    "abc_kernels": None,
                    "q_E": q_E,
                    "G": G,
                    "Z_0": Z0,
                    "Z_1": Z1,
                    "reach_E_distribution": reach_dist,
                    "E_kernel": ek,
                    "E_rates": None,
                    "fourfold": None,
                    "anchors": None,
                    "lambda": None,
                    "multinomial": None,
                }
        aE, bE = _kernel_numeric(ek, Num)
        uE = one - aE * aE
        vE = 2 * bE - bE * bE
        p_GP = Z0 * uE
        p_BP = Z1 * vE
        p_GE = s16["p_ge_preE"] + Z0 * aE * aE
        p_BE = one - p_GP - p_BP - p_GE
        total = p_GP + p_BP + p_GE + p_BE
        tol_c = Decimal(TOL_CONSERVATION)
        if Num is Decimal:
            if abs(total - one) > tol_c:
                raise CheckerNumericalError("fourfold independent sum deviates from 1: %s" % total)
        e_rates = {
            "first_abnormal": q_E * (one - bE) + (one - q_E) * aE,
            "process_exit": q_E * (one - bE) * (one - bE) + (one - q_E) * aE * aE,
            "device_total_exit": p_GE + p_BE,
        }
        anchors = {
            "E_S": 100 * (p_GP + p_BP),
            "E_PL": p_BP,
            "E_PW": p_GE,
        }
        # lambda main: NA iff q_E==0 or beta_E==1 ; tilde: NA iff q_E==0
        na_main = (q_E == 0) or (bE == 1)
        na_tilde = (q_E == 0)
        main = {"A": None, "B": None, "C": None, "D": None}
        tilde = {"A": None, "B": None, "C": None, "D": None}
        lam_sum = None
        if not na_main and Z1 != 0:
            for m in "ABCD":
                main[m] = s16["lam_num"][m] / Z1
            lam_sum = main["A"] + main["B"] + main["C"] + main["D"]
            if Num is Decimal:
                if abs(lam_sum - one) > tol_c:
                    raise CheckerNumericalError("lambda independent sum deviates from 1: %s" % lam_sum)
        if not na_tilde and Z1 != 0:
            for m in "ABCD":
                tilde[m] = s16["tilde_num"][m] / Z1
        counts = {
            "event_level": (one - bE) * (2 - bE),
            "first_test_only": one - bE,
            "at_most_once_per_device": one - bE,
        }
        lam_block = {
            "main": main,
            "sum": lam_sum,
            "tilde": tilde,
            "counts": counts,
            "na": bool(na_main),
        }
        multinomial = {
            "N": 100,
            "p": [p_GP, p_BP, p_GE, p_BE],
        }
        return {
            "overall_status": "ALL_ROUTES_AGREE",
            "infeasible_stage": None,
            "abc_kernels": None,
            "q_E": q_E,
            "G": G,
            "Z_0": Z0,
            "Z_1": Z1,
            "reach_E_distribution": reach_dist,
            "E_kernel": ek,
            "E_rates": e_rates,
            "fourfold": {
                "p_GP": p_GP,
                "p_BP": p_BP,
                "p_GE": p_GE,
                "p_BE": p_BE,
            },
            "anchors": anchors,
            "lambda": lam_block,
            "multinomial": multinomial,
        }


def compute_independent_full(semantics, q_a, q_b, q_c, q_d,
                             e_a, e_b, e_c, e_e,
                             Num=Decimal, prec=DEFAULT_PRECISION):
    """Self-contained independent recomputation (kernels solved internally).

    Used by the unit tests against the E2_embedded_oracles and available for
    diagnostic purposes.  The CLI verification path uses the response's
    abc_kernels instead (see ``verify_response``).
    """
    qs = (q_a, q_b, q_c)
    es = (e_a, e_b, e_c)
    kernels = []
    any_infeasible = False
    for j in range(3):
        kr = solve_kernel(qs[j], es[j], semantics, Num, prec)
        kernels.append({
            "process_id": PROCESSES[j],
            "q": qs[j],
            "e": es[j],
            "alpha": kr["alpha"],
            "beta": kr["beta"],
            "status": kr["status"],
            "free_parameters": kr["free_parameters"],
        })
        if kr["status"] == "INFEASIBLE":
            any_infeasible = True
    if any_infeasible:
        return {
            "overall_status": "HAS_INFEASIBLE",
            "infeasible_stage": "ABC_KERNEL",
            "abc_kernels": kernels,
            "q_E": None,
            "G": None,
            "Z_0": None,
            "Z_1": None,
            "reach_E_distribution": None,
            "E_kernel": None,
            "E_rates": None,
            "fourfold": None,
            "anchors": None,
            "lambda": None,
            "multinomial": None,
        }
    # zero-weight analysis for non-identifiable upstream kernels
    for j in range(3):
        kr = kernels[j]
        if kr["status"] == "NONIDENTIFIABLE_FAMILY":
            free = kr["free_parameters"]
            qj = qs[j]
            if "beta" in free and not (qj == 0):
                return {
                    "overall_status": "HAS_INDETERMINATE",
                    "infeasible_stage": "ABC_KERNEL",
                    "abc_kernels": kernels,
                    "q_E": None,
                    "G": None,
                    "Z_0": None,
                    "Z_1": None,
                    "reach_E_distribution": None,
                    "E_kernel": None,
                    "E_rates": None,
                    "fourfold": None,
                    "anchors": None,
                    "lambda": None,
                    "multinomial": None,
                }
            if "alpha" in free and not (qj == 1):
                return {
                    "overall_status": "HAS_INDETERMINATE",
                    "infeasible_stage": "ABC_KERNEL",
                    "abc_kernels": kernels,
                    "q_E": None,
                    "G": None,
                    "Z_0": None,
                    "Z_1": None,
                    "reach_E_distribution": None,
                    "E_kernel": None,
                    "E_rates": None,
                    "fourfold": None,
                    "anchors": None,
                    "lambda": None,
                    "multinomial": None,
                }
    kdicts = [{"alpha": k["alpha"], "beta": k["beta"],
               "status": k["status"], "free_parameters": k["free_parameters"]}
              for k in kernels]
    result = compute_q1_full(semantics, q_a, q_b, q_c, q_d, e_a, e_b, e_c, e_e,
                             kdicts[0], kdicts[1], kdicts[2], Num, prec)
    result["abc_kernels"] = kernels
    return result


# --------------------------------------------------------------------------
# Input loading (task package / schema / parameters)
# --------------------------------------------------------------------------

def load_task_package(path):
    """Parse the frozen task package and extract the pieces the checker needs:
    ``frozen_sha256``, ``numeric_policy.tolerances`` and
    ``significant_decimal_digits``."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        raise CheckerIOError("cannot read task package %s: %s" % (path, exc))
    try:
        doc = parse_simple_yaml(text)
    except _YamlParseError as exc:
        raise CheckerValidationError("task package YAML parse error: %s" % exc)
    frozen_sha256 = {}
    sha_block = (doc.get("shared_read_only_artifacts") or {}).get("frozen_sha256") or {}
    if isinstance(sha_block, dict):
        for k in ("parameters_csv", "schema", "oracle_fixture",
                  "upstream_single_response", "upstream_chain_response",
                  "upstream_file_hashes"):
            val = sha_block.get(k)
            if isinstance(val, str):
                frozen_sha256[k] = val
    tolerances = {}
    np_block = doc.get("numeric_policy") or {}
    tol_block = np_block.get("tolerances") or {}
    if isinstance(tol_block, dict):
        for k, v in tol_block.items():
            if isinstance(v, str):
                tolerances[k] = v
    sig_digits = SIGNIFICANT_DIGITS
    ser_block = np_block.get("serialization") or {}
    if isinstance(ser_block, dict) and isinstance(ser_block.get("significant_decimal_digits"), str):
        try:
            sig_digits = int(ser_block["significant_decimal_digits"])
        except (TypeError, ValueError):
            sig_digits = SIGNIFICANT_DIGITS
    version = doc.get("task_package_version")
    return {
        "frozen_sha256": frozen_sha256,
        "tolerances": tolerances,
        "significant_decimal_digits": sig_digits,
        "task_package_version": version if isinstance(version, str) else None,
        "_raw_doc": doc,
    }


def load_schema(path):
    """Parse the shared schema JSON and extract the enumeration + response
    envelope contract used by the structural validator."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except OSError as exc:
        raise CheckerIOError("cannot read schema %s: %s" % (path, exc))
    except ValueError as exc:
        raise CheckerValidationError("schema JSON parse error: %s" % exc)
    defs = doc.get("$defs", {})
    semantics = list((defs.get("semantics") or {}).get("enum", SEMANTICS))
    roles = list((defs.get("scenarioRole") or {}).get("enum", SCENARIO_ROLES))
    statuses = list((defs.get("processStatus") or {}).get("enum", PROCESS_STATUSES))
    overall = list((defs.get("overallStatus") or {}).get("enum", OVERALL_STATUSES))
    return {
        "semantics": semantics,
        "scenario_roles": roles,
        "process_statuses": statuses,
        "overall_statuses": overall,
    }


def load_parameters(path):
    """Read parameters.csv by parameter_id (csv stdlib); validate the frozen
    bindings P026-P033 and P037."""
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
    except OSError as exc:
        raise CheckerIOError("cannot read parameters %s: %s" % (path, exc))
    if not rows:
        raise CheckerValidationError("parameters.csv is empty")
    header = rows[0]
    if "parameter_id" not in header or "value" not in header:
        raise CheckerValidationError("parameters.csv header missing parameter_id/value")
    pid_idx = header.index("parameter_id")
    val_idx = header.index("value")
    values = {}
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        pid = row[pid_idx].strip()
        if pid in values:
            raise CheckerValidationError("duplicate parameter_id: %s" % pid)
        values[pid] = row[val_idx].strip()
    required = {
        "P026": "q_A", "P027": "q_B", "P028": "q_C", "P029": "q_D",
        "P030": "e_A", "P031": "e_B", "P032": "e_C", "P033": "e_E",
        "P037": "N_2",
    }
    parsed = {}
    for pid, name in required.items():
        if pid not in values:
            raise CheckerValidationError("missing parameter_id %s (%s)" % (pid, name))
        raw = values[pid]
        try:
            d = Decimal(raw)
        except InvalidOperation:
            raise CheckerValidationError("non-decimal value for %s: %r" % (pid, raw))
        if not d.is_finite():
            raise CheckerValidationError("non-finite value for %s: %r" % (pid, raw))
        parsed[pid] = d
    for pid in ("P026", "P027", "P028", "P029", "P030", "P031", "P032", "P033"):
        d = parsed[pid]
        if d < 0 or d > 1:
            raise CheckerValidationError("parameter %s out of [0,1]: %s" % (pid, d))
    if parsed["P037"] != 100:
        raise CheckerValidationError("N_2 (P037) must equal 100, got %s" % parsed["P037"])
    return {
        "q_a": parsed["P026"], "q_b": parsed["P027"], "q_c": parsed["P028"],
        "q_d": parsed["P029"],
        "e_a": parsed["P030"], "e_b": parsed["P031"], "e_c": parsed["P032"],
        "e_e": parsed["P033"],
        "N_2": parsed["P037"],
    }


def sha256_file(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError as exc:
        raise CheckerIOError("cannot hash %s: %s" % (path, exc))


# --------------------------------------------------------------------------
# Structural response validation (targeted, stdlib-only)
# --------------------------------------------------------------------------

def _check(cond, msg):
    if not cond:
        raise CheckerValidationError(msg)


def validate_response_structure(response, schema_info):
    """Targeted structural validation of a q1_response envelope against the
    frozen schema contract (stdlib-only; not a full JSON-Schema engine)."""
    _check(isinstance(response, dict), "response must be a JSON object")
    _check(response.get("schema_version") == SCHEMA_VERSION,
           "response schema_version must be %r" % SCHEMA_VERSION)
    _check(response.get("envelope_type") == ENVELOPE_RESPONSE,
           "response envelope_type must be %r" % ENVELOPE_RESPONSE)
    _check(isinstance(response.get("request_id"), str) and response["request_id"],
           "response request_id must be a non-empty string")
    _check(response.get("scenario_role") in schema_info["scenario_roles"],
           "response scenario_role invalid: %r" % response.get("scenario_role"))
    _check(response.get("semantics") in schema_info["semantics"],
           "response semantics invalid: %r" % response.get("semantics"))
    _check(response.get("overall_status") in schema_info["overall_statuses"],
           "response overall_status invalid: %r" % response.get("overall_status"))
    kernels = response.get("abc_kernels")
    _check(isinstance(kernels, list) and len(kernels) == 3,
           "response abc_kernels must be exactly 3 items")
    seen = []
    for item in kernels:
        _check(isinstance(item, dict), "abc_kernel item must be an object")
        pid = item.get("process_id")
        _check(pid in PROCESSES and pid not in seen, "abc_kernel process_id invalid/duplicate")
        seen.append(pid)
        _check(item.get("q") is None or (isinstance(item.get("q"), str) and DEC_PROB_RE.match(item["q"])),
               "abc_kernel q invalid")
        _check(item.get("e") is None or (isinstance(item.get("e"), str) and DEC_PROB_RE.match(item["e"])),
               "abc_kernel e invalid")
        _check(item.get("alpha") is None or (isinstance(item.get("alpha"), str) and DEC_PROB_RE.match(item["alpha"])),
               "abc_kernel alpha invalid")
        _check(item.get("beta") is None or (isinstance(item.get("beta"), str) and DEC_PROB_RE.match(item["beta"])),
               "abc_kernel beta invalid")
        _check(item.get("status") in schema_info["process_statuses"],
               "abc_kernel status invalid")
        fp = item.get("free_parameters")
        _check(isinstance(fp, list) and set(fp).issubset({"alpha", "beta"}),
               "abc_kernel free_parameters invalid")
        _check(item.get("source") in ("upstream_bound", "derived"),
               "abc_kernel source invalid")
    _check(seen == list("ABC"), "abc_kernels must be strictly ordered A,B,C")
    status = response["overall_status"]
    if status in ("ALL_ROUTES_AGREE", "ROUTE_MISMATCH"):
        for field in ("q_E", "G", "Z_0", "Z_1", "reach_E_distribution", "E_kernel",
                      "E_rates", "fourfold", "anchors", "lambda", "multinomial",
                      "route_agreement", "diagnostics"):
            _check(field in response, "response missing %s for %s" % (field, status))
        _check(response.get("q_E") is None or DEC_PROB_RE.match(response["q_E"]), "q_E invalid")
        _check(isinstance(response.get("reach_E_distribution"), list) and
               len(response["reach_E_distribution"]) == 16, "reach_E_distribution must have 16 items")
        _check(all(isinstance(x, str) and DEC_PROB_RE.match(x) for x in response["reach_E_distribution"]),
               "reach_E_distribution items invalid")
        ek = response.get("E_kernel")
        _check(isinstance(ek, dict), "E_kernel missing")
        _check(ek.get("status") in schema_info["process_statuses"], "E_kernel.status invalid")
        _check(isinstance(ek.get("free_parameters"), list) and
               set(ek.get("free_parameters", [])).issubset({"alpha", "beta"}),
               "E_kernel.free_parameters invalid")
        # V1.0.3: e_max_E is asserted only for single_test_unconditional_v1;
        # for standard_chain_v1 E1 omits the key (NOT_APPLICABLE), so the
        # field is optional here and only validated when present.
        if ek.get("e_max_E") is not None:
            _check(isinstance(ek.get("e_max_E"), str) and DEC_PROB_RE.match(ek["e_max_E"]),
                   "E_kernel.e_max_E invalid")
        diag = ek.get("diagnostics")
        _check(isinstance(diag, dict) and isinstance(diag.get("method"), str) and diag["method"]
               and isinstance(diag.get("feasibility"), str) and diag["feasibility"]
               and isinstance(diag.get("notes"), list),
               "E_kernel.diagnostics invalid")
        lb = response.get("lambda")
        _check(isinstance(lb, dict) and isinstance(lb.get("na"), bool),
               "lambda block invalid")
        for sub, fields in (("main", "ABCD"), ("tilde", "ABCD")):
            block = lb.get(sub)
            _check(isinstance(block, dict), "lambda.%s missing" % sub)
            for m in fields:
                _check(block.get(m) is None or (isinstance(block.get(m), str) and DEC_PROB_RE.match(block[m])),
                       "lambda.%s.%s invalid" % (sub, m))
        # V1.0.3 NA/null contract: sum and max_abs_deviation are nullable
        # (null when lambda.na=true); the null-vs-numeric equivalence is
        # enforced semantically in verify_response.
        _check(lb.get("sum") is None or (isinstance(lb.get("sum"), str) and DEC_SIGNED_RE.match(lb["sum"])),
               "lambda.sum invalid")
        _check(lb.get("max_abs_deviation") is None or
               (isinstance(lb.get("max_abs_deviation"), str) and DEC_SIGNED_RE.match(lb["max_abs_deviation"])),
               "lambda.max_abs_deviation invalid")
        counts = lb.get("counts")
        _check(isinstance(counts, dict) and all(
            counts.get(k) is None or (isinstance(counts.get(k), str) and DEC_NONNEG_RE.match(counts[k]))
            for k in ("event_level", "first_test_only", "at_most_once_per_device")),
            "lambda.counts invalid")
        er_block = response.get("E_rates")
        _check(isinstance(er_block, dict) and all(
            isinstance(er_block.get(k), str) and DEC_PROB_RE.match(er_block[k])
            for k in ("first_abnormal", "process_exit", "device_total_exit")),
            "E_rates invalid")
        an_block = response.get("anchors")
        _check(isinstance(an_block, dict) and isinstance(an_block.get("E_S"), str)
               and DEC_NONNEG_RE.match(an_block["E_S"])
               and isinstance(an_block.get("E_PL"), str) and DEC_PROB_RE.match(an_block["E_PL"])
               and isinstance(an_block.get("E_PW"), str) and DEC_PROB_RE.match(an_block["E_PW"]),
               "anchors invalid")
        ff_block = response.get("fourfold")
        _check(isinstance(ff_block, dict) and all(
            isinstance(ff_block.get(k), str) and DEC_PROB_RE.match(ff_block[k])
            for k in ("p_GP", "p_BP", "p_GE", "p_BE")),
            "fourfold values invalid")
        _check(isinstance(ff_block.get("sum"), str) and DEC_SIGNED_RE.match(ff_block["sum"]),
               "fourfold.sum invalid")
        pr = ff_block.get("per_route")
        _check(isinstance(pr, dict) and all(
            isinstance(pr.get(route), dict) and all(
                isinstance(pr[route].get(k), str) and DEC_PROB_RE.match(pr[route][k])
                for k in ("p_GP", "p_BP", "p_GE", "p_BE"))
            for route in ("closed_form", "enumeration", "absorption_chain")),
            "fourfold.per_route invalid")
        mn_block = response.get("multinomial")
        _check(isinstance(mn_block, dict) and mn_block.get("N") == 100
               and isinstance(mn_block.get("p"), list) and len(mn_block["p"]) == 4
               and all(isinstance(x, str) and DEC_PROB_RE.match(x) for x in mn_block["p"]),
               "multinomial invalid")
        ra = response.get("route_agreement")
        _check(isinstance(ra, dict), "route_agreement missing")
        for field in ("q_E", "G", "Z_0", "Z_1", "p_GP", "p_BP", "p_GE", "p_BE"):
            _check(isinstance(ra.get(field), str) and DEC_SIGNED_RE.match(ra[field]),
                   "route_agreement.%s invalid" % field)
        # V1.0.3: route_agreement.lambda_* (NA when lambda.na) and
        # route_agreement.tilde_* (NA when q_E == 0) are nullable; the
        # null-vs-numeric equivalence is enforced semantically in
        # verify_response.
        for field in ("lambda_A", "lambda_B", "lambda_C", "lambda_D",
                      "tilde_A", "tilde_B", "tilde_C", "tilde_D"):
            v = ra.get(field)
            _check(v is None or (isinstance(v, str) and DEC_SIGNED_RE.match(v)),
                   "route_agreement.%s invalid" % field)
    elif status == "HAS_INFEASIBLE":
        _check(response.get("infeasible_stage") in INFEASIBLE_STAGES,
               "infeasible_stage invalid")
        stage = response["infeasible_stage"]
        for null_field in ("E_rates", "fourfold", "anchors", "lambda",
                           "multinomial", "route_agreement"):
            _check(response.get(null_field) is None,
                   "%s must be null for HAS_INFEASIBLE" % null_field)
        if stage == "ABC_KERNEL":
            _check(response.get("q_E") is None,
                   "q_E must be null for ABC_KERNEL infeasible")
        elif stage == "E_KERNEL":
            _check(response.get("q_E") is not None, "q_E must be present for E_KERNEL infeasible")
    elif status == "HAS_INDETERMINATE":
        _check(response.get("infeasible_stage") in INFEASIBLE_STAGES,
               "infeasible_stage invalid for HAS_INDETERMINATE")
        for null_field in ("E_rates", "fourfold", "anchors", "lambda",
                           "multinomial", "route_agreement"):
            _check(response.get(null_field) is None,
                   "%s must be null for HAS_INDETERMINATE" % null_field)
    return True


# --------------------------------------------------------------------------
# Report helpers
# --------------------------------------------------------------------------

def _item(quantity, response_value, independent_value, tolerance, verdict):
    return {
        "quantity": quantity,
        "response_value": response_value,
        "independent_value": independent_value,
        "abs_deviation": None,
        "tolerance": tolerance,
        "verdict": verdict,
    }


def _num_item(items, quantity, resp_str, ind, tol_str):
    """Compare a numeric response string against an independent numeric value."""
    if ind is None:
        items.append(_item(quantity, resp_str, None, tol_str, "NOT_APPLICABLE"))
        return "NOT_APPLICABLE"
    if resp_str is None:
        items.append(_item(quantity, None, to_public(ind), tol_str, "FAIL"))
        return "FAIL"
    resp = parse_finite_decimal(resp_str, quantity)
    dev = abs(resp - Decimal(ind))
    tol = Decimal(tol_str)
    verdict = "PASS" if dev <= tol else "FAIL"
    items.append({
        "quantity": quantity,
        "response_value": resp_str,
        "independent_value": to_public(ind),
        "abs_deviation": to_public(dev),
        "tolerance": tol_str,
        "verdict": verdict,
    })
    return verdict


def _exact_item(items, quantity, resp_val, ind_val):
    verdict = "PASS" if resp_val == ind_val else "FAIL"
    items.append(_item(quantity, resp_val, ind_val, "0", verdict))
    return verdict


def write_report(path, payload):
    """Serialize a q1_check_report envelope: UTF-8, sort_keys, compact
    separators, trailing LF."""
    try:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    except OSError as exc:
        raise CheckerIOError("cannot write report %s: %s" % (path, exc))


# --------------------------------------------------------------------------
# Response verification
# --------------------------------------------------------------------------

def _ek_certificate(ek):
    """Schema-shaped independent E-kernel certificate (12-key certificate:
    status, alpha_E, beta_E, e_max_E, free_parameters and diagnostics
    {method, feasibility, notes})."""
    notes = []
    if ek.get("residual_balance") is not None:
        notes.append("independent_residual_balance=%s" % to_public(ek["residual_balance"]))
    if ek.get("residual_total") is not None:
        notes.append("independent_residual_total=%s" % to_public(ek["residual_total"]))
    notes.append("independent_method=%s" % ek["method"])
    return {
        "status": ek["status"],
        "alpha_E": None if ek["alpha"] is None else to_public(ek["alpha"]),
        "beta_E": None if ek["beta"] is None else to_public(ek["beta"]),
        "e_max_E": None if ek["e_max"] is None else to_public(ek["e_max"]),
        "free_parameters": ek["free_parameters"],
        "diagnostics": {
            "method": ek["method"],
            "feasibility": ek["feasibility"],
            "notes": notes,
        },
    }


def _response_kernels_typed(resp_kernels):
    """Convert response abc_kernels to Decimal-typed kernel dicts."""
    out = []
    for item in resp_kernels:
        out.append({
            "process_id": item["process_id"],
            "alpha": None if item.get("alpha") is None else Decimal(item["alpha"]),
            "beta": None if item.get("beta") is None else Decimal(item["beta"]),
            "status": item["status"],
            "free_parameters": item.get("free_parameters"),
        })
    return out


_TOL_TOKEN_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)")


def _tol_value(raw):
    """Extract the leading numeric token of a tolerance entry.  The frozen
    task package writes tolerances like ``"1e-15（q_E,G,... 说明）"`` — the
    numeric token is the authoritative value; any trailing commentary is
    ignored."""
    m = _TOL_TOKEN_RE.match(raw)
    if not m:
        raise CheckerValidationError("invalid tolerance entry: %r" % raw)
    return m.group(1)


_ROUTE_CORE_FIELDS = ("q_E", "G", "Z_0", "Z_1", "p_GP", "p_BP", "p_GE", "p_BE")


def _route_agreement_verify(items, ra, tol_str, na_lambda, na_tilde):
    """Verify the response route_agreement block and emit one item per field.

    V1.0.3 NA/null contract: the eight core deviation fields must be numeric
    and within the cross-route tolerance; ``lambda_A..D`` must be null when
    the lambda main table is NA (na_lambda) and numeric otherwise;
    ``tilde_A..D`` must be null when q_E == 0 (na_tilde) and numeric
    otherwise.  A numeric "0" in an NA field is a FAIL, never a pass.

    Returns the route_table verdict ("PASS"/"FAIL").
    """
    verdict = "PASS"

    def emit(field, val, na_expected):
        nonlocal verdict
        if na_expected:
            ok = val is None
            if not ok:
                verdict = "FAIL"
            items.append(_item("route_agreement.%s" % field, val, None,
                               tol_str, "PASS" if ok else "FAIL"))
            return
        if isinstance(val, str):
            try:
                dev = abs(parse_finite_decimal(val, "route_agreement.%s" % field))
            except CheckerValidationError:
                dev = None
        else:
            dev = None
        ok = dev is not None and dev <= Decimal(tol_str)
        if not ok:
            verdict = "FAIL"
        items.append({
            "quantity": "route_agreement.%s" % field,
            "response_value": val,
            "independent_value": "0",
            "abs_deviation": None if dev is None else to_public(dev),
            "tolerance": tol_str,
            "verdict": "PASS" if ok else "FAIL",
        })

    for field in _ROUTE_CORE_FIELDS:
        emit(field, ra.get(field), False)
    for m in "ABCD":
        emit("lambda_%s" % m, ra.get("lambda_%s" % m), na_lambda)
    for m in "ABCD":
        emit("tilde_%s" % m, ra.get("tilde_%s" % m), na_tilde)
    return verdict


def verify_response(response, parameters, schema_info, task_pkg, upstream_path,
                    semantics, prec=DEFAULT_PRECISION):
    """Compare the response against the independent recomputation.

    Returns (checker_status, items, ek_independent, route_table_verdict,
    errors).
    """
    items = []
    errors = []
    ek_ind = None
    # route_table verdict is derived from the response route_agreement after
    # the independent recomputation (NA state must come from the independent
    # values, not from the response's self-declared na); initialized here so
    # every branch has a defined value.
    route_verdict = "PASS"
    tol = {
        "qe": TOL_QE_DIST, "kernel": TOL_KERNEL, "emax": TOL_E_MAX,
        "agg": TOL_AGGREGATE, "conserv": TOL_CONSERVATION,
        "route": TOL_CROSS_ROUTE, "resid": TOL_RESIDUAL,
    }
    t = task_pkg.get("tolerances", {})
    mapping = {
        "qe": "cross_channel_qE_distribution_absolute",
        "kernel": "cross_channel_kernel_alpha_beta_absolute",
        "emax": "cross_channel_e_max_absolute",
        "agg": "cross_channel_aggregate_absolute",
        "conserv": "conservation_absolute",
        "route": "cross_route_absolute",
        "resid": "E2_independent_residual_absolute",
    }
    for key, yaml_key in mapping.items():
        if yaml_key in t and isinstance(t[yaml_key], str):
            try:
                tol[key] = _tol_value(t[yaml_key])
            except CheckerValidationError:
                errors.append("invalid tolerance %s in task package" % yaml_key)

    q_a, q_b, q_c, q_d = (parameters["q_a"], parameters["q_b"], parameters["q_c"],
                          parameters["q_d"])
    e_a, e_b, e_c, e_e = (parameters["e_a"], parameters["e_b"], parameters["e_c"],
                          parameters["e_e"])

    # --- abc kernels: read from the response, verify independently ---
    resp_kernels = response["abc_kernels"]
    kernels = []
    for j, item in enumerate(resp_kernels):
        pid = item["process_id"]
        qj = parse_finite_decimal(item["q"], "abc_kernels.%s.q" % pid)
        ej = parse_finite_decimal(item["e"], "abc_kernels.%s.e" % pid)
        ind_k = solve_kernel(qj, ej, semantics, Decimal, prec)
        ind_alpha = ind_k["alpha"]
        ind_beta = ind_k["beta"]
        param_q = (q_a, q_b, q_c)[j]
        param_e = (e_a, e_b, e_c)[j]
        q_dev = abs(qj - param_q)
        e_dev = abs(ej - param_e)
        items.append({
            "quantity": "abc_kernels.%s.q" % pid,
            "response_value": item["q"],
            "independent_value": to_public(param_q),
            "abs_deviation": to_public(q_dev),
            "tolerance": "0",
            "verdict": "PASS" if q_dev == 0 else "FAIL",
        })
        items.append({
            "quantity": "abc_kernels.%s.e" % pid,
            "response_value": item["e"],
            "independent_value": to_public(param_e),
            "abs_deviation": to_public(e_dev),
            "tolerance": "0",
            "verdict": "PASS" if e_dev == 0 else "FAIL",
        })
        _num_item(items, "abc_kernels.%s.alpha" % pid, item.get("alpha"),
                  ind_alpha, tol["kernel"])
        _num_item(items, "abc_kernels.%s.beta" % pid, item.get("beta"),
                  ind_beta, tol["kernel"])
        _exact_item(items, "abc_kernels.%s.status" % pid, item["status"], ind_k["status"])
        _exact_item(items, "abc_kernels.%s.free_parameters" % pid,
                    item.get("free_parameters"), ind_k["free_parameters"])
        kernels.append({
            "process_id": pid,
            "q": qj,
            "e": ej,
            "alpha": None if ind_alpha is None else Decimal(ind_alpha),
            "beta": None if ind_beta is None else Decimal(ind_beta),
            "status": ind_k["status"],
            "free_parameters": ind_k["free_parameters"],
        })
        if ind_k["status"] != item["status"]:
            errors.append(
                "abc_kernels.%s.status: response %s vs independent %s"
                % (pid, item["status"], ind_k["status"])
            )

    # --- route_table verdict from the response's own route_agreement ---
    overall = response["overall_status"]
    if overall in ("ALL_ROUTES_AGREE", "ROUTE_MISMATCH"):
        _exact_item(items, "overall_status", overall, "ALL_ROUTES_AGREE")
        kdicts = _response_kernels_typed(resp_kernels)
        ind = compute_q1_full(semantics, q_a, q_b, q_c, q_d, e_a, e_b, e_c, e_e,
                              kdicts[0], kdicts[1], kdicts[2], Decimal, prec)
        if ind["overall_status"] != "ALL_ROUTES_AGREE":
            errors.append("independent computation disagrees on overall status: %s"
                          % ind["overall_status"])
            items.append(_item("overall_status.independent", overall,
                               ind["overall_status"], "0", "FAIL"))
        else:
            _num_item(items, "q_E", response.get("q_E"), ind["q_E"], tol["qe"])
            _num_item(items, "G", response.get("G"), ind["G"], tol["qe"])
            _num_item(items, "Z_0", response.get("Z_0"), ind["Z_0"], tol["qe"])
            _num_item(items, "Z_1", response.get("Z_1"), ind["Z_1"], tol["qe"])
            for i in range(16):
                _num_item(items, "reach_E_distribution[%d]" % i,
                          response["reach_E_distribution"][i],
                          ind["reach_E_distribution"][i], tol["qe"])
            ek = ind["E_kernel"]
            rk = response.get("E_kernel") or {}
            _exact_item(items, "E_kernel.status", rk.get("status"), ek["status"])
            _exact_item(items, "E_kernel.free_parameters",
                        rk.get("free_parameters"), ek["free_parameters"])
            _num_item(items, "E_kernel.alpha_E", rk.get("alpha_E"), ek["alpha"], tol["kernel"])
            _num_item(items, "E_kernel.beta_E", rk.get("beta_E"), ek["beta"], tol["kernel"])
            # V1.0.3 e_max_E semantic gate: single asserts numerically;
            # chain is NOT_APPLICABLE (E1 omits the key and an omitted
            # e_max_E must not fail).
            if semantics == SEMANTICS_SINGLE:
                _num_item(items, "E_kernel.e_max_E", rk.get("e_max_E"), ek["e_max"], tol["emax"])
            else:
                items.append(_item("E_kernel.e_max_E", rk.get("e_max_E"), None,
                                   tol["emax"], "NOT_APPLICABLE"))
            er = ind["E_rates"]
            rer = response.get("E_rates") or {}
            for field in ("first_abnormal", "process_exit", "device_total_exit"):
                _num_item(items, "E_rates.%s" % field, rer.get(field), er[field], tol["agg"])
            ff = ind["fourfold"]
            rff = response.get("fourfold") or {}
            for field in ("p_GP", "p_BP", "p_GE", "p_BE"):
                _num_item(items, "fourfold.%s" % field, rff.get(field), ff[field], tol["agg"])
            ind_sum = ff["p_GP"] + ff["p_BP"] + ff["p_GE"] + ff["p_BE"]
            _num_item(items, "fourfold.sum", rff.get("sum"), ind_sum, tol["conserv"])
            an = ind["anchors"]
            ran = response.get("anchors") or {}
            _num_item(items, "anchors.E_S", ran.get("E_S"), an["E_S"], tol["agg"])
            _num_item(items, "anchors.E_PL", ran.get("E_PL"), an["E_PL"], tol["agg"])
            _num_item(items, "anchors.E_PW", ran.get("E_PW"), an["E_PW"], tol["agg"])
            lb2 = ind["lambda"]
            rlb = response.get("lambda") or {}
            _exact_item(items, "lambda.na", rlb.get("na"), bool(lb2["na"]))
            rmain = rlb.get("main") or {}
            if lb2["na"]:
                for m in "ABCD":
                    items.append(_item("lambda.main.%s" % m, rmain.get(m), None,
                                       tol["agg"], "PASS" if rmain.get(m) is None else "FAIL"))
            else:
                for m in "ABCD":
                    _num_item(items, "lambda.main.%s" % m, rmain.get(m), lb2["main"][m], tol["agg"])
            if lb2["sum"] is None:
                # V1.0.3 NA contract: when lambda is NA the sum must be null
                # (a numeric "0" is a contract violation -> FAIL).
                items.append(_item("lambda.sum", rlb.get("sum"), None, tol["conserv"],
                                   "PASS" if rlb.get("sum") is None else "FAIL"))
            else:
                _num_item(items, "lambda.sum", rlb.get("sum"), lb2["sum"], tol["conserv"])
            # V1.0.3 NA contract: lambda.max_abs_deviation must be null when
            # lambda is NA and a numeric decimal string otherwise.
            m_abs = rlb.get("max_abs_deviation")
            if lb2["na"]:
                items.append(_item("lambda.max_abs_deviation", m_abs, None,
                                   tol["route"], "PASS" if m_abs is None else "FAIL"))
            else:
                if isinstance(m_abs, str):
                    try:
                        dev = abs(parse_finite_decimal(m_abs, "lambda.max_abs_deviation"))
                    except CheckerValidationError:
                        dev = None
                else:
                    dev = None
                items.append({
                    "quantity": "lambda.max_abs_deviation",
                    "response_value": m_abs,
                    "independent_value": "0",
                    "abs_deviation": None if dev is None else to_public(dev),
                    "tolerance": tol["route"],
                    "verdict": "PASS" if (dev is not None and dev <= Decimal(tol["route"])) else "FAIL",
                })
            rtilde = rlb.get("tilde") or {}
            if lb2["tilde"]["A"] is None:
                for m in "ABCD":
                    items.append(_item("lambda.tilde.%s" % m, rtilde.get(m), None,
                                       tol["agg"], "PASS" if rtilde.get(m) is None else "FAIL"))
            else:
                for m in "ABCD":
                    _num_item(items, "lambda.tilde.%s" % m, rtilde.get(m), lb2["tilde"][m], tol["agg"])
            rc = rlb.get("counts") or {}
            for field in ("event_level", "first_test_only", "at_most_once_per_device"):
                _num_item(items, "lambda.counts.%s" % field, rc.get(field),
                          lb2["counts"][field], tol["agg"])
            mn = response.get("multinomial") or {}
            _exact_item(items, "multinomial.N", mn.get("N"), 100)
            mp = mn.get("p")
            if isinstance(mp, list) and len(mp) == 4:
                for i in range(4):
                    _num_item(items, "multinomial.p[%d]" % i, mp[i],
                              ind["multinomial"]["p"][i], tol["agg"])
            else:
                errors.append("multinomial.p missing/invalid")
                items.append(_item("multinomial.p", mp, None, tol["agg"], "FAIL"))
            ra = response.get("route_agreement") or {}
            route_verdict = _route_agreement_verify(
                items, ra, tol["route"],
                na_lambda=bool(ind["lambda"]["na"]),
                na_tilde=ind["lambda"]["tilde"]["A"] is None)
            for key, block in (("fourfold", response.get("fourfold")),
                               ("lambda", response.get("lambda"))):
                m = (block or {}).get("max_abs_deviation") if isinstance(block, dict) else None
                if isinstance(m, str):
                    try:
                        if abs(parse_finite_decimal(m, "%s.max_abs_deviation" % key)) > Decimal(tol["route"]):
                            route_verdict = "FAIL"
                    except CheckerValidationError:
                        route_verdict = "FAIL"
            ek_ind = _ek_certificate(ek)
    elif overall == "HAS_INFEASIBLE":
        _exact_item(items, "overall_status", overall, overall)
        stage = response.get("infeasible_stage")
        _exact_item(items, "infeasible_stage", stage, stage)
        if stage == "ABC_KERNEL":
            any_inf = any(k["status"] == "INFEASIBLE" for k in kernels)
            items.append(_item("infeasible_stage.independent", stage,
                               "ABC_KERNEL" if any_inf else "E_KERNEL", "0",
                               "PASS" if any_inf else "FAIL"))
            if not any_inf:
                errors.append("response says ABC_KERNEL infeasible but all A/B/C kernels are feasible")
        elif stage == "E_KERNEL":
            kdicts = _response_kernels_typed(resp_kernels)
            ind = compute_q1_full(semantics, q_a, q_b, q_c, q_d, e_a, e_b, e_c, e_e,
                                  kdicts[0], kdicts[1], kdicts[2], Decimal, prec)
            _num_item(items, "q_E", response.get("q_E"), ind["q_E"], tol["qe"])
            _num_item(items, "G", response.get("G"), ind["G"], tol["qe"])
            _num_item(items, "Z_0", response.get("Z_0"), ind["Z_0"], tol["qe"])
            _num_item(items, "Z_1", response.get("Z_1"), ind["Z_1"], tol["qe"])
            for i in range(16):
                _num_item(items, "reach_E_distribution[%d]" % i,
                          response["reach_E_distribution"][i],
                          ind["reach_E_distribution"][i], tol["qe"])
            ek = ind["E_kernel"]
            rk = response.get("E_kernel") or {}
            _exact_item(items, "E_kernel.status", rk.get("status"), "INFEASIBLE")
            _exact_item(items, "E_kernel.free_parameters", rk.get("free_parameters"), [])
            # V1.0.3 e_max_E semantic gate: single asserts numerically (the
            # frozen O3 single case pins e_max_E = 1/8); chain is
            # NOT_APPLICABLE and an omitted key must not fail.
            if semantics == SEMANTICS_SINGLE:
                _num_item(items, "E_kernel.e_max_E", rk.get("e_max_E"), ek["e_max"], tol["emax"])
            else:
                items.append(_item("E_kernel.e_max_E", rk.get("e_max_E"), None,
                                   tol["emax"], "NOT_APPLICABLE"))
            ek_ind = _ek_certificate(ek)
    elif overall == "HAS_INDETERMINATE":
        _exact_item(items, "overall_status", overall, overall)
        _exact_item(items, "infeasible_stage", response.get("infeasible_stage"),
                    response.get("infeasible_stage"))
    else:
        # FAILED_VALIDATION / NUMERICAL_FAILURE: an E1 envelope that reached
        # this state is itself evidence of a broken run.
        _exact_item(items, "overall_status", overall, overall)
        errors.append("response overall_status %s is not independently verifiable" % overall)

    checker_status = "PASS"
    for it in items:
        if it["verdict"] == "FAIL":
            checker_status = "FAIL"
    if route_verdict == "FAIL":
        checker_status = "FAIL"
    if errors:
        checker_status = "FAIL"
    return checker_status, items, ek_ind, route_verdict, errors


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _preflight(response_path):
    """Report-context preflight: read only the response's top-level
    scenario_role / request_id / semantics.  Raises CheckerPreflightError."""
    try:
        with open(response_path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except OSError as exc:
        raise CheckerIOError("cannot read response %s: %s" % (response_path, exc))
    except ValueError as exc:
        raise CheckerPreflightError("response is not valid JSON: %s" % exc)
    if not isinstance(doc, dict):
        raise CheckerPreflightError("response must be a JSON object")
    role = doc.get("scenario_role")
    semantics = doc.get("semantics")
    request_id = doc.get("request_id")
    if role != SCENARIO_CANONICAL:
        raise CheckerPreflightError(
            "scenario_role must be %r, got %r" % (SCENARIO_CANONICAL, role))
    if not isinstance(request_id, str) or ":" not in request_id:
        raise CheckerPreflightError("request_id must be <run_id>:<semantics>")
    run_id, suffix = request_id.rsplit(":", 1)
    if suffix != semantics:
        raise CheckerPreflightError(
            "request_id suffix %r does not match response.semantics %r"
            % (suffix, semantics))
    if not RUN_ID_RE.match(run_id):
        raise CheckerPreflightError("request_id run_id prefix does not match "
                                    "^[0-9]{8}T[0-9]{12}Z_[0-9a-f]{8}$")
    if semantics not in SEMANTICS:
        raise CheckerPreflightError("unknown semantics %r" % (semantics,))
    return run_id, semantics, doc


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="q1_quality_checker_v1",
        description="E2 independent checker for the frozen G2-02 Q1 chain",
        allow_abbrev=False,
    )
    parser.add_argument("--response", required=True)
    parser.add_argument("--parameters", required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--task-package", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--request", dest="_forbidden_request", default=None,
                        help=argparse.SUPPRESS)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 2
    if args._forbidden_request is not None:
        sys.stderr.write("E2 checker: --request is FORBIDDEN; E2 never reads request files\n")
        return 2

    # ---- report-context preflight (before any report write) ----
    try:
        run_id, semantics, response = _preflight(args.response)
    except CheckerPreflightError as exc:
        sys.stderr.write("E2 preflight failure: %s\n" % exc)
        return 2
    except CheckerIOError as exc:
        sys.stderr.write("E2 IO failure: %s\n" % exc)
        return 4

    report_path = args.report
    # ---- input hashes (needed for every post-preflight report) ----
    try:
        params_hash = sha256_file(args.parameters)
        upstream_hash = sha256_file(args.upstream)
    except CheckerIOError as exc:
        sys.stderr.write("E2 IO failure: %s\n" % exc)
        return 4

    def fail_validation(msg):
        # schema-valid VALIDATION_ERROR report using the derived parent run id
        payload = {
            "schema_version": SCHEMA_VERSION,
            "envelope_type": ENVELOPE_REPORT,
            "request_id": response.get("request_id"),
            "semantics": semantics,
            "checker_status": "FAIL",
            "report_context_run_id": run_id,
            "frozen_input_hashes": {"parameters_sha256": params_hash,
                                    "upstream_sha256": upstream_hash},
            "items": [],
            "E_kernel_independent": None,
            "route_table_verdict": "FAIL",
            "errors": [msg],
        }
        try:
            write_report(report_path, payload)
        except CheckerIOError as exc:
            sys.stderr.write("E2 IO failure: %s\n" % exc)
            return 4
        sys.stderr.write("E2 validation failure: %s\n" % msg)
        return 2

    try:
        schema_info = load_schema(args.schema)
        task_pkg = load_task_package(args.task_package)
        parameters = load_parameters(args.parameters)
        validate_response_structure(response, schema_info)
    except CheckerValidationError as exc:
        return fail_validation(str(exc))
    except CheckerIOError as exc:
        sys.stderr.write("E2 IO failure: %s\n" % exc)
        return 4

    # ---- frozen hash binding (frozen_sha256 from the task package) ----
    # NOTE: the task package keys are upstream_single_response /
    # upstream_chain_response (short names), not the full semantics strings.
    frozen = task_pkg.get("frozen_sha256", {})
    expected_params = frozen.get("parameters_csv")
    upstream_short = {SEMANTICS_SINGLE: "single", SEMANTICS_CHAIN: "chain"}[semantics]
    expected_upstream = frozen.get("upstream_%s_response" % upstream_short)
    if expected_params and params_hash != expected_params:
        return fail_validation(
            "parameters SHA-256 %s does not match frozen_sha256.parameters_csv %s"
            % (params_hash, expected_params))
    if expected_upstream and upstream_hash != expected_upstream:
        return fail_validation(
            "upstream SHA-256 %s does not match frozen_sha256.upstream_%s_response %s"
            % (upstream_hash, upstream_short, expected_upstream))

    prec = max(DEFAULT_PRECISION, SIGNIFICANT_DIGITS + 80)
    try:
        checker_status, items, ek_ind, route_verdict, errors = verify_response(
            response, parameters, schema_info, task_pkg, args.upstream, semantics, prec)
    except CheckerValidationError as exc:
        return fail_validation(str(exc))
    except CheckerNumericalError as exc:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "envelope_type": ENVELOPE_REPORT,
            "request_id": response.get("request_id"),
            "semantics": semantics,
            "checker_status": "FAIL",
            "report_context_run_id": run_id,
            "frozen_input_hashes": {"parameters_sha256": params_hash,
                                    "upstream_sha256": upstream_hash},
            "items": [],
            "E_kernel_independent": None,
            "route_table_verdict": "FAIL",
            "errors": ["NUMERICAL_ERROR: %s" % exc],
        }
        try:
            write_report(report_path, payload)
        except CheckerIOError as exc2:
            sys.stderr.write("E2 IO failure: %s\n" % exc2)
            return 4
        sys.stderr.write("E2 numerical failure: %s\n" % exc)
        return 3

    payload = {
        "schema_version": SCHEMA_VERSION,
        "envelope_type": ENVELOPE_REPORT,
        "request_id": response.get("request_id"),
        "semantics": semantics,
        "checker_status": checker_status,
        "report_context_run_id": run_id,
        "frozen_input_hashes": {"parameters_sha256": params_hash,
                                "upstream_sha256": upstream_hash},
        "items": items,
        "E_kernel_independent": ek_ind,
        "route_table_verdict": route_verdict,
        "errors": errors,
    }
    try:
        write_report(report_path, payload)
    except CheckerIOError as exc:
        sys.stderr.write("E2 IO failure: %s\n" % exc)
        return 4
    if checker_status == "PASS":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
