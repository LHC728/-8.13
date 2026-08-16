"""MATHEMATICAL_MODELING_ROUTER_V2.1 — method family registry (spec 22).

METHOD_FAMILY_REGISTRY_V1.0: multi-label classification of a task into
generic method families.  Method family decides the verification strategy
(spec 5 separation) and NEVER decides the risk colour: route computation
does not consume families.

This module is part of the UNIVERSAL CORE (generalization guard scans it).
Python 3.12, standard library only.
"""
from __future__ import annotations

import re
from typing import Any

FAMILIES = (
    "ANALYTICAL_MATH",
    "PROBABILITY_STATISTICS",
    "REGRESSION_PREDICTION",
    "TIME_SERIES",
    "MACHINE_LEARNING",
    "OPTIMIZATION",
    "OPERATIONS_RESEARCH",
    "GRAPH_NETWORK",
    "DISCRETE_EVENT_SIMULATION",
    "MONTE_CARLO_STOCHASTIC",
    "ODE_PDE_DYNAMICAL_SYSTEM",
    "PHYSICS_MECHANISM",
    "MULTI_CRITERIA_EVALUATION",
    "SPATIAL_GIS",
    "NUMERICAL_COMPUTATION",
    "HYBRID_OTHER",
)

HYBRID_OTHER = "HYBRID_OTHER"

# generic keyword rules: family -> regex patterns on the task text
_FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ANALYTICAL_MATH", (
        r"closed\s*form", r"analytic", r"derive[ds]?\b", r"derivation",
        r"exact\s*solution", r"formula\b")),
    ("PROBABILITY_STATISTICS", (
        r"probabilit", r"distribution", r"hypothesis", r"bootstrap",
        r"confidence", r"estimator", r"p[- ]?value", r"significance",
        r"variance", r"expectation", r"likelihood")),
    ("REGRESSION_PREDICTION", (
        r"regression", r"predict", r"forecast", r"linear model",
        r"logistic", r"fitting|fit\b")),
    ("TIME_SERIES", (
        r"time series", r"rolling", r"seasonal", r"autocorrelation",
        r"arima", r"lag\b", r"trend\b", r"stationarity")),
    ("MACHINE_LEARNING", (
        r"machine learning", r"neural", r"gradient boosting",
        r"random forest", r"support vector", r"training set",
        r"cross[- ]validation", r"classifier", r"deep learning")),
    ("OPTIMIZATION", (
        r"optimiz", r"minimi[sz]e", r"maximi[sz]e", r"objective",
        r"constraint", r"linear program", r"integer program",
        r"milp", r"convex", r"gradient descent", r"knapsack")),
    ("OPERATIONS_RESEARCH", (
        r"schedul", r"routing", r"assignment", r"queueing",
        r"inventory", r"transportation", r"network flow",
        r"facility location", r"vehicle routing")),
    ("GRAPH_NETWORK", (
        r"graph\b", r"network\b", r"shortest path", r"connectivity",
        r"centrality", r"minimum spanning", r"max flow", r"topolog")),
    ("DISCRETE_EVENT_SIMULATION", (
        r"discrete.event", r"event-driven", r"simulat",
        r"agent[- ]based", r"queue.*simulat", r"servers?.*process")),
    ("MONTE_CARLO_STOCHASTIC", (
        r"monte carlo", r"stochastic", r"random draw", r"random seed",
        r"sampling", r"replicat", r"bootstrap")),
    ("ODE_PDE_DYNAMICAL_SYSTEM", (
        r"\bode\b", r"\bpde\b", r"differential equation",
        r"dynamical", r"equilibrium", r"phase plane",
        r"system of equations", r"stability analysis")),
    ("PHYSICS_MECHANISM", (
        r"physics", r"mechanism", r"force\b", r"mass\b", r"energy\b",
        r"conservation", r"mechanics", r"motion\b", r"friction")),
    ("MULTI_CRITERIA_EVALUATION", (
        r"topsis", r"ahp\b", r"entropy weight", r"multi-criteria",
        r"composite index", r"ranking", r"evaluation matrix",
        r"weighted scoring", r"normalization")),
    ("SPATIAL_GIS", (
        r"\bgis\b", r"spatial", r"coordinate", r"geospatial",
        r"raster", r"distance matrix", r"map\b")),
    ("NUMERICAL_COMPUTATION", (
        r"numerical", r"discretiz", r"step size", r"finite difference",
        r"finite element", r"iteration", r"solver", r"tolerance",
        r"convergence", r"grid refinement", r"interpolation")),
)

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_ -]*")


def classify_method_families(task_text: str) -> list[str]:
    """Multi-label keyword classification; HYBRID_OTHER when unrecognized."""
    text = task_text.lower()
    found: list[str] = []
    for family, patterns in _FAMILY_RULES:
        for pat in patterns:
            if re.search(pat, text):
                found.append(family)
                break
    if not found:
        found.append("HYBRID_OTHER")
    return found


def family_distribution(corpus: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in corpus:
        for fam in item.get("method_families", []):
            counts[fam] = counts.get(fam, 0) + 1
    return counts
