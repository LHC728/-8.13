"""MATHEMATICAL_MODELING_ROUTER_V2.1.1 — method family registry (spec 22 as
repaired: P1-1 bilingual classification, §15 Chinese terms, §16 DES
refinement).

METHOD_FAMILY_REGISTRY_V1.0: multi-label classification of a task into
generic method families, recognising Chinese AND English mathematical-modeling
vocabulary.  Method family decides the verification strategy (spec 5
separation) and NEVER decides the risk colour.

V2.1.1 repairs:
* P1-1: Chinese equivalents added for every family.
* §16: a generic "simulation/simulate/仿真" alone is NO LONGER classified as
  DISCRETE_EVENT_SIMULATION — DES requires discrete-event evidence
  (discrete-event / event-driven / event queue / queue simulation /
  离散事件 / 事件驱动 / 事件队列 / 排队仿真 ...).  Generic simulation maps
  to another matching family or HYBRID_OTHER / MONTE_CARLO as appropriate.

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
DISCRETE_EVENT_SIMULATION = "DISCRETE_EVENT_SIMULATION"

# Bilingual keyword rules: family -> regex patterns on the task text
# (Chinese patterns are literal phrases; English patterns are lowercase).
_FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ANALYTICAL_MATH", (
        r"closed\s*form", r"analytic", r"derive[ds]?\b", r"derivation",
        r"exact\s*solution", r"formula\b",
        r"解析解", r"数学推导", r"解析法", r"公式推导", r"闭式解")),
    ("PROBABILITY_STATISTICS", (
        r"probabilit", r"distribution", r"hypothesis", r"bootstrap",
        r"confidence", r"estimator", r"p[- ]?value", r"significance",
        r"variance", r"expectation", r"likelihood",
        r"概率", r"统计", r"分布", r"假设检验", r"置信区间",
        r"自助法", r"显著性", r"方差", r"期望", r"似然")),
    ("REGRESSION_PREDICTION", (
        r"regression", r"predict", r"forecast", r"linear model",
        r"logistic", r"fitting|fit\b",
        r"回归", r"预测", r"拟合", r"线性回归", r"逻辑回归")),
    ("TIME_SERIES", (
        r"time series", r"rolling", r"seasonal", r"autocorrelation",
        r"arima", r"lag\b", r"trend\b", r"stationarity",
        r"时间序列", r"趋势", r"季节性", r"自相关", r"平稳性")),
    ("MACHINE_LEARNING", (
        r"machine learning", r"neural", r"gradient boosting",
        r"random forest", r"support vector", r"training set",
        r"cross[- ]validation", r"classifier", r"deep learning",
        r"机器学习", r"神经网络", r"随机森林", r"支持向量机", r"交叉验证",
        r"深度学习", r"训练集")),
    ("OPTIMIZATION", (
        r"optimiz", r"minimi[sz]e", r"maximi[sz]e", r"objective",
        r"constraint", r"linear program", r"integer program",
        r"milp", r"convex", r"gradient descent", r"knapsack",
        r"优化", r"最优化", r"线性规划", r"整数规划", r"混合整数规划",
        r"目标函数", r"约束条件", r"凸优化", r"梯度下降")),
    ("OPERATIONS_RESEARCH", (
        r"schedul", r"routing", r"assignment", r"queueing",
        r"inventory", r"transportation", r"network flow",
        r"facility location", r"vehicle routing",
        r"运筹", r"调度", r"排队", r"库存", r"指派", r"运输",
        r"设施选址", r"车辆路径", r"排班")),
    ("GRAPH_NETWORK", (
        r"graph\b", r"network\b", r"shortest path", r"connectivity",
        r"centrality", r"minimum spanning", r"max flow", r"topolog",
        r"图论", r"网络", r"最短路", r"最大流", r"最小生成树", r"连通性",
        r"中心性", r"拓扑")),
    ("DISCRETE_EVENT_SIMULATION", (
        r"discrete.event", r"event-driven", r"event queue",
        r"event scheduling", r"queue simulation", r"queuing simulation",
        r"server.*process|service.*process",
        r"离散事件", r"事件驱动", r"事件队列", r"事件调度", r"排队仿真",
        r"排队系统仿真")),
    ("MONTE_CARLO_STOCHASTIC", (
        r"monte carlo", r"stochastic", r"random draw", r"random seed",
        r"sampling", r"replicat", r"bootstrap",
        r"蒙特卡洛", r"蒙特卡罗", r"随机模拟", r"随机抽样", r"随机种子",
        r"随机数", r"抽样")),
    ("ODE_PDE_DYNAMICAL_SYSTEM", (
        r"\bode\b", r"\bpde\b", r"differential equation",
        r"dynamical", r"equilibrium", r"phase plane",
        r"system of equations", r"stability analysis",
        r"常微分方程", r"偏微分方程", r"微分方程", r"动力系统",
        r"平衡点", r"相平面", r"稳定性分析")),
    ("PHYSICS_MECHANISM", (
        r"physics", r"mechanism", r"force\b", r"mass\b", r"energy\b",
        r"conservation", r"mechanics", r"motion\b", r"friction",
        r"物理", r"力学", r"受力", r"能量", r"守恒", r"摩擦",
        r"运动", r"机械")),
    ("MULTI_CRITERIA_EVALUATION", (
        r"topsis", r"ahp\b", r"entropy weight", r"multi-criteria",
        r"composite index", r"ranking", r"evaluation matrix",
        r"weighted scoring", r"normalization",
        r"层次分析", r"熵权", r"多指标评价", r"综合评价", r"加权评分",
        r"综合评分", r"评价矩阵", r"归一化")),
    ("SPATIAL_GIS", (
        r"\bgis\b", r"spatial", r"coordinate", r"geospatial",
        r"raster", r"distance matrix", r"map\b",
        r"空间", r"地理", r"坐标", r"地图", r"栅格", r"距离矩阵")),
    ("NUMERICAL_COMPUTATION", (
        r"numerical", r"discretiz", r"step size", r"finite difference",
        r"finite element", r"iteration", r"solver", r"tolerance",
        r"convergence", r"grid refinement", r"interpolation",
        r"数值计算", r"数值积分", r"有限差分", r"有限元", r"步长",
        r"网格", r"收敛", r"插值", r"迭代", r"数值解")),
)


def classify_method_families(task_text: str) -> list[str]:
    """Multi-label bilingual classification.

    V2.1.1 DES refinement: generic "simulation"/"simulate"/"仿真" without
    discrete-event evidence does NOT map to DISCRETE_EVENT_SIMULATION; a
    generic simulation task maps to whatever other families match, or
    HYBRID_OTHER / MONTE_CARLO when stochastic terms are present.
    """
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
