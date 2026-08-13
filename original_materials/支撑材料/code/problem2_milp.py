#!/usr/bin/env python3
"""
Problem 2: 时间索引循环MILP — 最大化年出栏量
================================================
采用 scipy.optimize.milp (HiGHS求解器) 精确求解229天循环周期的
混合整数线性规划，得到全局最优配种计划 x_t (t=0..228)。

两阶段目标:
  Stage 1: 最大化年化出栏量
  Stage 2: 固定最优出栏量，最小化配种计划的波动性

与原始枚举结果对比，验证MILP的优越性。
"""

import numpy as np
import pandas as pd
import json
import sys
import os
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import csc_array, coo_array

# ============================================================
# 参数设置 (与问题1/2一致)
# ============================================================
T_MATE = 20
T_PREG = 149
T_NURS = 40
T_REST = 20
T_FATT = 210
T_CYCLE = T_MATE + T_PREG + T_NURS + T_REST  # 229
LAMB_PER_BIRTH = 2
TOTAL_PENS = 112

CAP_MATE = 14   # 配种栏容量 (母羊)
CAP_PREG = 8    # 怀孕栏容量
CAP_NURS = 6    # 哺乳栏容量
CAP_REST = 14   # 休整栏容量
CAP_FATT = 14   # 育肥栏容量
CAP_RAM = 4     # 公羊栏容量
RAM_EWE_RATIO = 50

# 各阶段在周期内的起始偏移和天数
# (stage_key, start_offset, duration, capacity, lamb_multiplier)
STAGES = [
    ('mate', 0, T_MATE, CAP_MATE, 1),       # j=0..19
    ('preg', T_MATE, T_PREG, CAP_PREG, 1),   # j=20..168
    ('nurs', T_MATE + T_PREG, T_NURS, CAP_NURS, 1),  # j=169..208
    ('rest', T_MATE + T_PREG + T_NURS, T_REST, CAP_REST, 1),  # j=209..228
    ('fatt', T_MATE + T_PREG + T_NURS, T_FATT, CAP_FATT, LAMB_PER_BIRTH),  # j=209..418
]


def build_variable_indices():
    """建立变量索引映射。返回 (offsets_dict, n_total)."""
    idx = 0
    off = {}
    off['x_start'] = idx
    idx += T_CYCLE  # 229 x_t variables

    for stage_key, _, _, _, _ in STAGES:
        off[f'p_{stage_key}_start'] = idx
        idx += T_CYCLE  # 229 pen variables per stage

    off['n_rams_total'] = idx
    idx += 1
    off['p_ram'] = idx
    idx += 1
    off['s_start'] = idx
    idx += T_CYCLE  # 229 smoothing variables (Stage 2)
    off['n_stage1'] = off['s_start']  # Stage 1 ends before s vars
    off['n_total'] = idx
    return off


def build_constraint_matrix(offsets):
    """
    构建完整的约束矩阵 (COO格式)。

    约束结构:
    - 每天每阶段: 2个ceil线性化约束
    - 每天: 1个总羊栏约束
    - 公羊相关约束

    返回 (row_data, b_l, b_u, n_rows) 用于 LinearConstraint。
    """
    rows = []
    cols = []
    data = []
    n_rows = 0
    b_u_list = []  # scipy.milp uses b_u (upper bound), b_l defaults to -inf

    def add_row(col_indices, coefficients, upper_bound):
        nonlocal n_rows
        for ci, co in zip(col_indices, coefficients):
            rows.append(n_rows)
            cols.append(ci)
            data.append(co)
        b_u_list.append(upper_bound)
        n_rows += 1

    # ---- Ceil linearization constraints ----
    # For each day d and each stage:
    #   Upper: E_stage[d] - cap * P_stage[d] <= 0
    #   Lower: -E_stage[d] + cap * P_stage[d] <= cap - 1
    stage_pen_offsets = {
        'mate': offsets['p_mate_start'],
        'preg': offsets['p_preg_start'],
        'nurs': offsets['p_nurs_start'],
        'rest': offsets['p_rest_start'],
        'fatt': offsets['p_fatt_start'],
    }

    for d in range(T_CYCLE):
        for stage_key, start_j, duration, cap, lamb in STAGES:
            pen_start = stage_pen_offsets[stage_key]
            pen_col = pen_start + d

            # Columns for x variables in this stage window
            x_indices = [(d - j) % T_CYCLE for j in range(start_j, start_j + duration)]
            x_coeffs = [float(lamb)] * len(x_indices)

            # Upper bound: sum(lamb * x) - cap * pen <= 0
            all_indices = x_indices + [pen_col]
            all_coeffs = x_coeffs + [float(-cap)]
            add_row(all_indices, all_coeffs, 0.0)

            # Lower bound: -sum(lamb * x) + cap * pen <= cap - 1
            all_indices = x_indices + [pen_col]
            all_coeffs = [-c for c in x_coeffs] + [float(cap)]
            add_row(all_indices, all_coeffs, float(cap - 1))

    # ---- Total pen constraint: sum(pen types) + p_ram <= 112 ----
    for d in range(T_CYCLE):
        indices = [offsets[f'p_{sk}_start'] + d for sk in ['mate', 'preg', 'nurs', 'rest', 'fatt']]
        indices.append(offsets['p_ram'])
        coeffs = [1.0] * 5 + [1.0]
        add_row(indices, coeffs, float(TOTAL_PENS))

    # ---- Ram constraints ----
    # n_rams_total >= p_mate[d] for all d
    # -> p_mate[d] - n_rams_total <= 0
    for d in range(T_CYCLE):
        add_row(
            [offsets['p_mate_start'] + d, offsets['n_rams_total']],
            [1.0, -1.0],
            0.0
        )

    # 50 * n_rams_total >= sum(x_t)
    # -> sum(x_t) - 50 * n_rams_total <= 0
    add_row(
        list(range(offsets['x_start'], offsets['x_start'] + T_CYCLE)) + [offsets['n_rams_total']],
        [1.0] * T_CYCLE + [-50.0],
        0.0
    )

    # 4 * p_ram >= n_rams_total - p_mate[d] for all d
    # -> n_rams_total - p_mate[d] - 4 * p_ram <= 0
    for d in range(T_CYCLE):
        add_row(
            [offsets['n_rams_total'], offsets['p_mate_start'] + d, offsets['p_ram']],
            [1.0, -1.0, -4.0],
            0.0
        )

    # ---- All pen variables >= 0 is handled by bounds ----
    # ---- n_rams_total >= 0, p_ram >= 0 handled by bounds ----

    b_l = np.full(n_rows, -np.inf)
    b_u = np.array(b_u_list, dtype=np.float64)

    rows32 = np.array(rows, dtype=np.int32)
    cols32 = np.array(cols, dtype=np.int32)
    data64 = np.array(data, dtype=np.float64)
    A = coo_array((data64, (rows32, cols32)), shape=(n_rows, offsets['n_stage1'])).tocsc()
    A.indices = A.indices.astype(np.int32)
    A.indptr = A.indptr.astype(np.int32)

    return A, b_l, b_u


def build_stage2_smoothing(offsets, x_sum_target):
    """
    构建Stage 2的平滑约束矩阵。

    添加变量 s_t 和对应的约束，加上固定总和的等式约束。
    返回扩展后的 (A2, b_l2, b_u2, c2, bounds2, integrality2).
    """
    n1 = offsets['n_stage1']
    n2 = offsets['n_total']
    n_smooth = T_CYCLE
    n_new_rows = 2 * T_CYCLE + 1  # 2*229 smoothing + 1 equality

    # Objective: minimize sum(s_t)
    c2 = np.zeros(n2, dtype=np.float64)
    c2[offsets['s_start']:offsets['s_start'] + T_CYCLE] = 1.0

    # Bounds
    lb2 = np.zeros(n2, dtype=np.float64)
    ub2 = np.full(n2, np.inf, dtype=np.float64)
    # x_t bounds: 0..14 per variable
    ub2[offsets['x_start']:offsets['x_start'] + T_CYCLE] = 14.0
    # Pen variables: non-negative, upper bound from total pens
    for sk in ['mate', 'preg', 'nurs', 'rest', 'fatt']:
        ub2[offsets[f'p_{sk}_start']:offsets[f'p_{sk}_start'] + T_CYCLE] = float(TOTAL_PENS)
    ub2[offsets['n_rams_total']] = float(TOTAL_PENS)
    ub2[offsets['p_ram']] = float(TOTAL_PENS)
    # s_t bounds
    ub2[offsets['s_start']:offsets['s_start'] + T_CYCLE] = float(T_CYCLE)

    # Integrality: all integer
    integrality = np.ones(n2, dtype=np.int32)

    # Build smoothing constraints
    rows = []
    cols = []
    data = []
    n_rows = 0
    b_u_list = []

    def add_row(col_indices, coefficients, upper_bound):
        nonlocal n_rows
        for ci, co in zip(col_indices, coefficients):
            rows.append(n_rows)
            cols.append(ci)
            data.append(co)
        b_u_list.append(upper_bound)
        n_rows += 1

    s_start = offsets['s_start']
    x_start = offsets['x_start']

    # s_t >= x_t - x_{t-1}  ->  -s_t + x_t - x_{t-1} <= 0
    for t in range(T_CYCLE):
        t_prev = (t - 1) % T_CYCLE
        add_row(
            [s_start + t, x_start + t, x_start + t_prev],
            [-1.0, 1.0, -1.0],
            0.0
        )

    # s_t >= x_{t-1} - x_t  ->  -s_t - x_t + x_{t-1} <= 0
    for t in range(T_CYCLE):
        t_prev = (t - 1) % T_CYCLE
        add_row(
            [s_start + t, x_start + t, x_start + t_prev],
            [-1.0, -1.0, 1.0],
            0.0
        )

    # Equality: sum(x_t) = S*
    add_row(
        list(range(x_start, x_start + T_CYCLE)),
        [1.0] * T_CYCLE,
        float(x_sum_target)
    )
    # For scipy.milp, we need b_l = b_u for equality
    eq_row = n_rows - 1

    b_l2 = np.full(n_rows, -np.inf, dtype=np.float64)
    b_u2 = np.array(b_u_list, dtype=np.float64)
    # Set equality: b_l == b_u for the last row
    b_l2[eq_row] = float(x_sum_target)

    rows32 = np.array(rows, dtype=np.int32)
    cols32 = np.array(cols, dtype=np.int32)
    data64 = np.array(data, dtype=np.float64)
    A2_coo = coo_array((data64, (rows32, cols32)), shape=(n_rows, n2)).tocsc()
    A2_coo.indices = A2_coo.indices.astype(np.int32)
    A2_coo.indptr = A2_coo.indptr.astype(np.int32)

    return A2_coo, b_l2, b_u2, c2, Bounds(lb2, ub2), integrality


def compute_littles_law_upper_bound():
    """
    用Little定律估算理论上界。

    每个羊栏的"产出率"取决于其容量和周转时间。
    计算加权平均每个栏位每天能支撑的羔羊产出。
    """
    # 每只母羊每天在周期中的时间比例
    frac_mate = T_MATE / T_CYCLE
    frac_preg = T_PREG / T_CYCLE
    frac_nurs = T_NURS / T_CYCLE
    frac_rest = T_REST / T_CYCLE
    frac_fatt = T_FATT / T_CYCLE

    # 每只母羊在各阶段所需的栏位面积 (pen-ewe-days per day)
    pen_per_ewe_mate = 1.0 / CAP_MATE
    pen_per_ewe_preg = 1.0 / CAP_PREG
    pen_per_ewe_nurs = 1.0 / CAP_NURS
    pen_per_ewe_rest = 1.0 / CAP_REST
    # 育肥: 每只母羊产2只羔羊
    pen_per_ewe_fatt = LAMB_PER_BIRTH / CAP_FATT

    # 平均每只母羊每天需要的栏位面积
    avg_pen_per_ewe = (
        frac_mate * pen_per_ewe_mate +
        frac_preg * pen_per_ewe_preg +
        frac_nurs * pen_per_ewe_nurs +
        frac_rest * pen_per_ewe_rest +
        frac_fatt * pen_per_ewe_fatt
    )

    # 公羊栏
    ewes_per_ram = RAM_EWE_RATIO
    rams_per_ewe = 1.0 / ewes_per_ram
    # 每只公羊占 1/CAP_RAM 个栏 (非配种期)
    # 配种公羊在配种栏内，不计入公羊栏
    pen_per_ewe_ram = rams_per_ewe * (1.0 / CAP_RAM) * (1 - frac_mate)

    avg_pen_per_ewe += pen_per_ewe_ram

    # 112个栏能支撑的最大母羊数
    max_ewes = TOTAL_PENS / avg_pen_per_ewe

    # 年出栏量
    max_output = max_ewes * LAMB_PER_BIRTH * 365.0 / T_CYCLE

    return max_output, avg_pen_per_ewe


def solve_milp():
    """求解两阶段MILP。返回 (x_opt, stage1_result, stage2_result, stats)."""
    offsets = build_variable_indices()
    n1 = offsets['n_stage1']

    print("构建约束矩阵...")
    A, b_l, b_u = build_constraint_matrix(offsets)
    print(f"  约束矩阵: {A.shape[0]} 行 × {A.shape[1]} 列, {A.nnz} 非零元")

    # ---- Stage 1: 最大化出栏量 ----
    # 目标: max sum(x_t) -> min -sum(x_t)
    c1 = np.zeros(n1, dtype=np.float64)
    c1[offsets['x_start']:offsets['x_start'] + T_CYCLE] = -1.0

    # Bounds
    lb1 = np.zeros(n1, dtype=np.float64)
    ub1 = np.full(n1, np.inf, dtype=np.float64)
    ub1[offsets['x_start']:offsets['x_start'] + T_CYCLE] = 14.0
    for sk in ['mate', 'preg', 'nurs', 'rest', 'fatt']:
        ub1[offsets[f'p_{sk}_start']:offsets[f'p_{sk}_start'] + T_CYCLE] = float(TOTAL_PENS)
    ub1[offsets['n_rams_total']] = float(TOTAL_PENS)
    ub1[offsets['p_ram']] = float(TOTAL_PENS)

    integrality1 = np.ones(n1, dtype=np.int32)

    constraints1 = LinearConstraint(A, b_l, b_u)
    bounds1 = Bounds(lb1, ub1)

    print("\n=== Stage 1: 最大化年化出栏量 ===")
    res1 = milp(
        c=c1,
        integrality=integrality1,
        bounds=bounds1,
        constraints=constraints1,
        options={'time_limit': 300, 'disp': True, 'mip_rel_gap': 1e-4}
    )

    if not res1.success:
        if hasattr(res1, 'x') and res1.x is not None and np.any(res1.x):
            print(f"  WARNING: Stage 1 达到时间限制但找到可行解: {res1.message}")
            print(f"  目标值: {res1.fun:.4f}, 最优间隙: {getattr(res1, 'mip_gap', 'N/A')}")
        else:
            print(f"  ERROR: Stage 1 求解失败: {res1.message}")
            return None, None, None, None

    x_sum_opt = int(np.round(np.sum(res1.x[offsets['x_start']:offsets['x_start'] + T_CYCLE])))
    annual_output = x_sum_opt * LAMB_PER_BIRTH * 365.0 / T_CYCLE
    print(f"  Stage 1 完成: sum(x_t) = {x_sum_opt}, 年化出栏 = {annual_output:.1f} 只")
    print(f"  求解状态: {res1.message}")

    # ---- Stage 2: 平滑优化 (可选，如果Stage 1在时限内未达最优则跳过) ----
    print("\n=== Stage 2: 最小化配种波动 ===")
    # Check if Stage 1 found a fully optimal solution
    mip_gap = getattr(res1, 'mip_gap', 1.0)
    if mip_gap > 0.01:
        print(f"  Stage 1 间隙 {mip_gap*100:.2f}% > 1%，跳过Stage 2优化")
        print(f"  直接计算Stage 1解的平滑度")
        x_stage1 = np.round(res1.x[offsets['x_start']:offsets['x_start'] + T_CYCLE]).astype(int)
        smoothness_stage1 = float(np.sum(np.abs(np.diff(np.append(x_stage1, x_stage1[0])))))
        print(f"  Stage 1 平滑度 sum|diff| = {smoothness_stage1:.1f}")
        return x_stage1, annual_output, smoothness_stage1, {'stage1': res1, 'stage2': None}

    A2, b_l2, b_u2, c2, bounds2, integrality2 = build_stage2_smoothing(offsets, x_sum_opt)

    # 合并Stage 1约束和Stage 2新增约束
    # Stage 1约束 (A, b_l, b_u) 需要扩展到 n2 列
    n2 = offsets['n_total']
    # Extend A to have n2 columns (pad with zeros for smoothing vars)
    # Extend indptr to reflect extra columns (all zero)
    extended_indptr = np.zeros(n2 + 1, dtype=np.int32)
    extended_indptr[:A.indptr.shape[0]] = A.indptr
    extended_indptr[A.indptr.shape[0]:] = A.indptr[-1]
    A1_ext = csc_array((A.data.copy(), A.indices.copy(), extended_indptr),
                        shape=(A.shape[0], n2))
    # Stack A1_ext and A2
    from scipy.sparse import vstack
    A_full = vstack([A1_ext, A2])
    b_l_full = np.concatenate([b_l, b_l2])
    b_u_full = np.concatenate([b_u, b_u2])

    constraints2 = LinearConstraint(A_full, b_l_full, b_u_full)

    res2 = milp(
        c=c2,
        integrality=integrality2,
        bounds=bounds2,
        constraints=constraints2,
        options={'time_limit': 120, 'disp': False}
    )

    if not res2.success:
        print(f"  WARNING: Stage 2 求解失败: {res2.message}")
        print(f"  使用 Stage 1 结果作为最终结果")
        x_opt = np.round(res1.x[offsets['x_start']:offsets['x_start'] + T_CYCLE]).astype(int)
        smoothness = float(np.sum(np.abs(np.diff(np.append(x_opt, x_opt[0])))))
        return x_opt, annual_output, smoothness, {'stage1': res1, 'stage2': None}
    else:
        x_opt = np.round(res2.x[offsets['x_start']:offsets['x_start'] + T_CYCLE]).astype(int)
        smoothness = np.sum(res2.x[offsets['s_start']:offsets['s_start'] + T_CYCLE])
        annual_output_s2 = np.sum(x_opt) * LAMB_PER_BIRTH * 365.0 / T_CYCLE
        print(f"  Stage 2 完成: sum(x_t) = {np.sum(x_opt)}, 年化出栏 = {annual_output_s2:.1f} 只")
        print(f"  平滑度 sum(s_t) = {smoothness:.1f}")
        print(f"  求解状态: {res2.message}")
        return x_opt, annual_output, smoothness, {'stage1': res1, 'stage2': res2}


def compute_daily_pens_from_milp(x_values):
    """根据MILP解x_t计算每日羊栏占用，用于交叉验证。

    关键：将每日进入配种的母羊人数按繁殖周期展开，
    逐日统计各阶段母羊/羔羊总数，再根据容量计算栏位。
    与MILP中的E_stage[d]计算方式一致。
    """
    sim_days = T_CYCLE * 4 + 500
    daily_ewes_mate = np.zeros(sim_days, dtype=int)
    daily_ewes_preg = np.zeros(sim_days, dtype=int)
    daily_ewes_nurs = np.zeros(sim_days, dtype=int)
    daily_ewes_rest = np.zeros(sim_days, dtype=int)
    daily_lambs_fatt = np.zeros(sim_days, dtype=int)

    # 每天开始的x_t只母羊，进入配种期20天，然后依次进入后续阶段
    for t0 in range(T_CYCLE):
        n = x_values[t0]
        if n <= 0:
            continue
        for cycle in range(20):
            start = t0 + cycle * T_CYCLE
            if start >= sim_days:
                break

            # 配种期: day start .. start+19 (20 days)
            me = min(start + T_MATE, sim_days)
            daily_ewes_mate[start:me] += n

            # 怀孕期: day start+20 .. start+168 (149 days)
            ps = start + T_MATE
            pe = min(ps + T_PREG, sim_days)
            if ps < sim_days:
                daily_ewes_preg[ps:pe] += n

            # 哺乳期: day start+169 .. start+208 (40 days)
            ns = start + T_MATE + T_PREG
            ne = min(ns + T_NURS, sim_days)
            if ns < sim_days:
                daily_ewes_nurs[ns:ne] += n

            # 休整期: day start+209 .. start+228 (20 days)
            rs = start + T_MATE + T_PREG + T_NURS
            re_r = min(rs + T_REST, sim_days)
            re_f = min(rs + T_FATT, sim_days)
            if rs < sim_days:
                daily_ewes_rest[rs:re_r] += n
                daily_lambs_fatt[rs:re_f] += n * LAMB_PER_BIRTH

    # 取稳态
    warmup = T_CYCLE * 2
    window = slice(warmup, warmup + T_CYCLE)

    # 计算每日栏位需求 (ceil(ewes/capacity))
    daily_pens_mate = np.ceil(daily_ewes_mate / CAP_MATE).astype(int)
    daily_pens_preg = np.ceil(daily_ewes_preg / CAP_PREG).astype(int)
    daily_pens_nurs = np.ceil(daily_ewes_nurs / CAP_NURS).astype(int)
    daily_pens_rest = np.ceil(daily_ewes_rest / CAP_REST).astype(int)
    daily_pens_fatt = np.ceil(daily_lambs_fatt / CAP_FATT).astype(int)

    total_ewes = int(np.sum(x_values))
    n_rams_mating = int(np.max(daily_pens_mate[window]))
    n_rams_total = max(int(np.ceil(total_ewes / RAM_EWE_RATIO)), n_rams_mating)
    n_rams_non_mating = max(0, n_rams_total - n_rams_mating)
    pens_ram = max(0, int(np.ceil(n_rams_non_mating / CAP_RAM)))

    max_mate = int(np.max(daily_pens_mate[window]))
    max_preg = int(np.max(daily_pens_preg[window]))
    max_nurs = int(np.max(daily_pens_nurs[window]))
    max_rest = int(np.max(daily_pens_rest[window]))
    max_fatt = int(np.max(daily_pens_fatt[window]))
    total_pens = max_mate + max_preg + max_nurs + max_rest + max_fatt + pens_ram

    return {
        'pens_mate': max_mate,
        'pens_preg': max_preg,
        'pens_nurs': max_nurs,
        'pens_rest': max_rest,
        'pens_fatt': max_fatt,
        'pens_ram': pens_ram,
        'total_pens': total_pens,
        'total_ewes': total_ewes,
        'daily_mate': daily_pens_mate[window],
        'daily_preg': daily_pens_preg[window],
        'daily_nurs': daily_pens_nurs[window],
        'daily_rest': daily_pens_rest[window],
        'daily_fatt': daily_pens_fatt[window],
    }


def run_enumeration_baseline():
    """运行原始枚举方法作为基准。导入 problem2_optimization 的贪婪搜索。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from problem2_optimization import greedy_optimization
        best, _ = greedy_optimization()
        return best['annual_output'], best
    except Exception as e:
        print(f"  WARNING: 无法运行枚举基准: {e}")
        return 1205.0, None  # fallback to known value


def validate_milp_solution(x_values):
    """验证MILP解是否满足所有约束。"""
    pens = compute_daily_pens_from_milp(x_values)
    errors = []

    if pens['total_pens'] > TOTAL_PENS:
        errors.append(f"总羊栏超限: {pens['total_pens']} > {TOTAL_PENS}")

    total_ewes = pens['total_ewes']
    min_rams = int(np.ceil(total_ewes / RAM_EWE_RATIO))
    # 公羊数已在pens中验证

    if total_ewes == 0:
        errors.append("总母羊数为0")

    return len(errors) == 0, errors, pens


# ============================================================
# 主程序
# ============================================================
if __name__ == '__main__':
    print("=" * 70)
    print("问题2: 时间索引循环MILP — 最大化年出栏量")
    print("=" * 70)

    # ---- Little's Law 上界 ----
    print("\n## 0. Little's Law 理论上界")
    upper_bound, avg_pen_per_ewe = compute_littles_law_upper_bound()
    print(f"  平均每只母羊占用栏位: {avg_pen_per_ewe:.4f} 栏/只")
    print(f"  理论最大年出栏量: {upper_bound:.1f} 只/年")

    # ---- 枚举基准 ----
    print("\n## 1. 运行枚举基准 (原始方法)")
    enum_output, enum_config = run_enumeration_baseline()
    print(f"  枚举最优年出栏量: {enum_output:.1f} 只/年")

    # ---- MILP求解 ----
    print("\n## 2. MILP求解")
    x_opt, milp_output, smoothness, solvers = solve_milp()

    if x_opt is None:
        print("\nERROR: MILP求解失败，退出")
        sys.exit(1)

    # ---- 交叉验证 ----
    print("\n## 3. 交叉验证 (MILP解 → 时间线模拟)")
    valid, errors, pens = validate_milp_solution(x_opt)
    if valid:
        print(f"  ✓ 验证通过: 总羊栏 {pens['total_pens']} ≤ {TOTAL_PENS}")
    else:
        print(f"  ✗ 验证失败:")
        for e in errors:
            print(f"    - {e}")

    # 比较 MILP 和 MILP 后验证的羊栏数
    print(f"\n  MILP解的羊栏分配:")
    print(f"    配种栏: {pens['pens_mate']}  怀孕栏: {pens['pens_preg']}")
    print(f"    哺乳栏: {pens['pens_nurs']}  休整栏: {pens['pens_rest']}")
    print(f"    育肥栏: {pens['pens_fatt']}  公羊栏: {pens['pens_ram']}")
    print(f"    总计: {pens['total_pens']}")

    # ---- 结果对比 ----
    print("\n## 4. 三组结果对比")
    print(f"  {'方案':<25s} {'年出栏量':>10s} {'差距':>10s}")
    print(f"  {'-'*47}")
    print(f"  {'枚举基准 (等批量/等间隔)':<25s} {enum_output:>10.1f} {'基准':>10s}")
    print(f"  {'MILP最优 (平滑后)':<25s} {milp_output:>10.1f} {f'+{milp_output-enum_output:.1f}':>10s}")
    print(f"  {'Little定律理论上界':<25s} {upper_bound:>10.1f} {f'+{upper_bound-enum_output:.1f}':>10s}")

    gap_to_upper = (upper_bound - milp_output) / upper_bound * 100 if upper_bound > 0 else 0
    print(f"\n  MILP距理论上界: {gap_to_upper:.2f}%")

    # ---- 非零x_t的分布 ----
    print("\n## 5. 配种计划分布")
    nonzero = np.where(x_opt > 0)[0]
    print(f"  非零配种日: {len(nonzero)} 天 (共229天周期)")
    print(f"  x_t 取值: min={x_opt.min()}, max={x_opt.max()}, mean={x_opt.mean():.2f}")
    print(f"  sum(x_t) = {np.sum(x_opt)}")
    s_val = smoothness if smoothness is not None else float('nan')
    print(f"  平滑度 sum|diff| = {s_val:.1f}")

    # 前20个非零日
    print(f"\n  前20个配种日: (日, 只数)")
    pairs = [(t, x_opt[t]) for t in nonzero[:20]]
    for t, v in pairs:
        print(f"    第{t:3d}天: {v:2d}只")

    # ---- 保存结果 ----
    print("\n## 6. 保存结果")
    os.makedirs('/home/user/workspace/output', exist_ok=True)

    # MILP解
    milp_solution = {
        'T_CYCLE': T_CYCLE,
        'TOTAL_PENS': TOTAL_PENS,
        'stage1_output': float(milp_output),
        'smoothness': float(smoothness),
        'x_sum': int(np.sum(x_opt)),
        'n_nonzero_days': int(len(nonzero)),
        'daily_mate_pens': int(pens['pens_mate']),
        'daily_preg_pens': int(pens['pens_preg']),
        'daily_nurs_pens': int(pens['pens_nurs']),
        'daily_rest_pens': int(pens['pens_rest']),
        'daily_fatt_pens': int(pens['pens_fatt']),
        'daily_ram_pens': int(pens['pens_ram']),
        'total_pens': int(pens['total_pens']),
        'total_ewes': int(pens['total_ewes']),
        'enumeration_output': float(enum_output),
        'littles_law_bound': float(upper_bound),
    }
    with open('/home/user/workspace/output/problem2_milp_solution.json', 'w', encoding='utf-8') as f:
        json.dump(milp_solution, f, ensure_ascii=False, indent=2)

    # 每日x_t排程
    df_schedule = pd.DataFrame({
        'day': range(T_CYCLE),
        'x_t': x_opt,
        'pen_mate': pens['daily_mate'],
        'pen_preg': pens['daily_preg'],
        'pen_nurs': pens['daily_nurs'],
        'pen_rest': pens['daily_rest'],
        'pen_fatt': pens['daily_fatt'],
        'pen_total': (pens['daily_mate'] + pens['daily_preg'] + pens['daily_nurs'] +
                      pens['daily_rest'] + pens['daily_fatt'] + pens['pens_ram']),
    })
    df_schedule.to_csv('/home/user/workspace/output/problem2_milp_daily_schedule.csv',
                       index=False, encoding='utf-8-sig')

    # 对比表
    df_comparison = pd.DataFrame([
        {'method': '枚举基准', 'annual_output': enum_output,
         'gap_vs_enum': 0.0, 'gap_vs_bound_pct': (upper_bound - enum_output) / upper_bound * 100},
        {'method': 'MILP最优', 'annual_output': milp_output,
         'gap_vs_enum': milp_output - enum_output,
         'gap_vs_bound_pct': (upper_bound - milp_output) / upper_bound * 100},
        {'method': 'Little定律上界', 'annual_output': upper_bound,
         'gap_vs_enum': upper_bound - enum_output, 'gap_vs_bound_pct': 0.0},
    ])
    df_comparison.to_csv('/home/user/workspace/output/problem2_milp_vs_enumeration.csv',
                         index=False, encoding='utf-8-sig')

    # 文本摘要
    with open('/home/user/workspace/output/problem2_milp_results.txt', 'w', encoding='utf-8') as f:
        f.write("问题2: 时间索引循环MILP 结果\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"MILP最优年出栏量: {milp_output:.1f} 只/年\n")
        f.write(f"枚举基准年出栏量: {enum_output:.1f} 只/年\n")
        f.write(f"Little定律理论上界: {upper_bound:.1f} 只/年\n")
        f.write(f"距上界: {gap_to_upper:.2f}%\n\n")
        f.write(f"总基础母羊: {pens['total_ewes']} 只\n")
        f.write(f"非零配种日: {len(nonzero)} 天\n")
        f.write(f"平滑度: {smoothness:.1f}\n\n")
        f.write(f"羊栏分配:\n")
        f.write(f"  配种栏: {pens['pens_mate']}\n")
        f.write(f"  怀孕栏: {pens['pens_preg']}\n")
        f.write(f"  哺乳栏: {pens['pens_nurs']}\n")
        f.write(f"  休整栏: {pens['pens_rest']}\n")
        f.write(f"  育肥栏: {pens['pens_fatt']}\n")
        f.write(f"  公羊栏: {pens['pens_ram']}\n")
        f.write(f"  总计: {pens['total_pens']}\n")

    print(f"  已保存: problem2_milp_solution.json")
    print(f"  已保存: problem2_milp_daily_schedule.csv")
    print(f"  已保存: problem2_milp_vs_enumeration.csv")
    print(f"  已保存: problem2_milp_results.txt")

    print("\n" + "=" * 70)
    print("问题2 MILP求解完成！")
