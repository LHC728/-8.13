#!/usr/bin/env python3
"""Q3-H2-P2 frozen parameters (local declarations).

Frozen source of truth:
  * parameters.csv P018-P029, P006-P013 (values verified against the
    accepted CSV rows);
  * Q1-frozen single-test kernel semantics (P060:
    ``(1-q)*alpha = q*beta = e/2`` -> alpha = e/(2(1-q)), beta = e/(2q));
  * Q1-frozen q_E propagation value ``0.062593912407392898``;
  * G3-SPEC-V1.0 section 4 piecewise-linear lifetime CDF (P018-P025 nodes).

These constants are declared LOCALLY inside the h2 package so that the
h2 consumer package never imports the live DES engine modules (C23
import/AST isolation, P1).  They are exact Fractions.

Python 3.12, standard library only.
"""
from __future__ import annotations

from fractions import Fraction

# --- defect priors (P026-P029) -------------------------------------------
Q_ABC: dict[str, Fraction] = {
    "A": Fraction(25, 1000),   # P026 q_A = 0.025
    "B": Fraction(3, 100),     # P027 q_B = 0.03
    "C": Fraction(2, 100),     # P028 q_C = 0.02
}
Q_D: Fraction = Fraction(1, 1000)  # P029 q_D = 0.001

# --- frozen observation-error probabilities (Q1) --------------------------
E_ABC: dict[str, Fraction] = {
    "A": Fraction(3, 100),     # P030 e_A = 0.03
    "B": Fraction(4, 100),     # P031 e_B = 0.04
    "C": Fraction(2, 100),     # P032 e_C = 0.02
}
E_E: Fraction = Fraction(2, 100)   # P033 e_E = 0.02
Q_E_TEXT: str = "0.062593912407392898"  # Q1-frozen q_E (P060 E kernel)
Q_E: Fraction = Fraction(Q_E_TEXT)

# --- lifetime CDF nodes (P018-P025) ---------------------------------------
F120: dict[str, Fraction] = {
    "A": Fraction(3, 100),  # P018
    "B": Fraction(4, 100),  # P019
    "C": Fraction(2, 100),  # P020
    "E": Fraction(3, 100),  # P021
}
F240: dict[str, Fraction] = {
    "A": Fraction(5, 100),  # P022
    "B": Fraction(7, 100),  # P023
    "C": Fraction(6, 100),  # P024
    "E": Fraction(5, 100),  # P025
}

# --- durations / calibration (P006-P013) ----------------------------------
DURATIONS_H: dict[str, Fraction] = {
    "A": Fraction(5, 2),   # P006 2.5
    "B": Fraction(2),      # P007 2
    "C": Fraction(5, 2),   # P008 2.5
    "E": Fraction(3),      # P009 3
}
CALIBRATION_MINUTES: dict[str, Fraction] = {
    "A": Fraction(30),     # P010
    "B": Fraction(20),     # P011
    "C": Fraction(20),     # P012
    "E": Fraction(40),     # P013
}
MIN_PREVENTIVE_AGE_H: Fraction = Fraction(120)  # P016
MANDATORY_AGE_H: Fraction = Fraction(240)       # P017

RESOURCES: tuple[str, ...] = ("A", "B", "C", "E")

# --- frozen observation kernel (P060 formula) -----------------------------


def frozen_alpha(q: Fraction, e: Fraction) -> Fraction:
    return e / (Fraction(2) * (Fraction(1) - q))


def frozen_beta(q: Fraction, e: Fraction) -> Fraction:
    return e / (Fraction(2) * q)


def observation_kernel() -> dict[str, dict[str, Fraction]]:
    kernel: dict[str, dict[str, Fraction]] = {}
    for proc in ("A", "B", "C"):
        q = Q_ABC[proc]
        e = E_ABC[proc]
        kernel[proc] = {"alpha": frozen_alpha(q, e), "beta": frozen_beta(q, e)}
    kernel["E"] = {"alpha": frozen_alpha(Q_E, E_E), "beta": frozen_beta(Q_E, E_E)}
    return kernel
