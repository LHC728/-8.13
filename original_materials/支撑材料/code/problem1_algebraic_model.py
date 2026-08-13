#!/usr/bin/env python3
"""
Problem 1: 代数递推模型 — 湖羊空间利用率分析
==================================================
确定性条件下，建立繁殖-育肥分阶段代数递推方程，
计算种公羊/基础母羊合理数量、年出栏量范围、羊栏缺口。

Author: CUMCM Team
"""

import numpy as np
import pandas as pd
from itertools import product

# ============================================================
# 参数设置
# ============================================================
T_MATE = 20       # 配种期 (天)
T_PREG = 149      # 怀孕期 (天)
T_NURS = 40       # 哺乳期 (天)
T_REST = 20       # 空怀休整期 (天)
T_FATT = 210      # 育肥期 (天)
T_CYCLE = T_MATE + T_PREG + T_NURS + T_REST  # 完整周期 229 天
LAMB_PER_BIRTH = 2  # 每胎产羔数
TOTAL_PENS = 112     # 总羊栏数

# 羊栏容量
CAP_REST = 14     # 空怀休整母羊/栏
CAP_RAM = 4       # 非配种种公羊/栏
CAP_MATE_EWE = 14 # 配种期母羊/栏 (+1只公羊)
CAP_PREG = 8      # 怀孕母羊/栏
CAP_NURS = 6      # 哺乳母羊/栏 (+羔羊)
CAP_FATT = 14     # 育肥羔羊/栏

# 公母比例
RAM_EWE_RATIO = 50  # 至少 1:50

# ============================================================
# 核心函数
# ============================================================

def compute_pens_for_config(n_ewe_per_batch, n_batches):
    """
    给定每批母羊数和批次数，计算所需各类型羊栏数。

    采用稳态时间比例法：在连续生产中，每种羊栏的占用数量
    等于 (处于该阶段的批次数) × (每批所需该类型栏数)。

    处于某阶段的批次数 = 总批次数 × (该阶段时长 / 总周期时长)
    """
    # 每批在各阶段所需栏数（向上取整）
    pens_mate_per_batch = 1  # 配种期: 1栏/批 (1公羊 + n母羊)
    pens_preg_per_batch = int(np.ceil(n_ewe_per_batch / CAP_PREG))
    pens_nurs_per_batch = int(np.ceil(n_ewe_per_batch / CAP_NURS))
    pens_rest_per_batch = int(np.ceil(n_ewe_per_batch / CAP_REST))

    # 每批产羔数，育肥所需栏数
    n_lambs_per_batch = n_ewe_per_batch * LAMB_PER_BIRTH
    pens_fatt_per_batch = int(np.ceil(n_lambs_per_batch / CAP_FATT))

    # 稳态下，处于各阶段的批次数（连续值，需要整数化处理）
    # 使用精确计数：模拟一个周期内的每日占用
    frac_mate = T_MATE / T_CYCLE
    frac_preg = T_PREG / T_CYCLE
    frac_nurs = T_NURS / T_CYCLE
    frac_rest = T_REST / T_CYCLE
    frac_fatt = T_FATT / T_CYCLE

    # 连续近似值
    n_mate_active = n_batches * frac_mate
    n_preg_active = n_batches * frac_preg
    n_nurs_active = n_batches * frac_nurs
    n_rest_active = n_batches * frac_rest
    n_fatt_active = n_batches * frac_fatt

    pens_mate = int(np.ceil(n_mate_active)) * pens_mate_per_batch
    pens_preg = int(np.ceil(n_preg_active)) * pens_preg_per_batch
    pens_nurs = int(np.ceil(n_nurs_active)) * pens_nurs_per_batch
    pens_rest = int(np.ceil(n_rest_active)) * pens_rest_per_batch
    pens_fatt = int(np.ceil(n_fatt_active)) * pens_fatt_per_batch

    # 公羊栏: 需要知道配种公羊数
    n_rams_mating = int(np.ceil(n_mate_active))  # 同时配种的公羊数
    n_rams_total = max(int(np.ceil(n_ewe_per_batch * n_batches / RAM_EWE_RATIO)), n_rams_mating)
    n_rams_non_mating = max(0, n_rams_total - n_rams_mating)
    pens_ram = int(np.ceil(n_rams_non_mating / CAP_RAM)) if n_rams_non_mating > 0 else 0

    total_pens = pens_mate + pens_preg + pens_nurs + pens_rest + pens_fatt + pens_ram

    # 年出栏量
    cycles_per_year = 365.0 / T_CYCLE  # 每年每只母羊几个周期
    annual_output = n_ewe_per_batch * n_batches * LAMB_PER_BIRTH * cycles_per_year

    return {
        'n_ewe_per_batch': n_ewe_per_batch,
        'n_batches': n_batches,
        'total_base_ewes': n_ewe_per_batch * n_batches,
        'total_rams': n_rams_total,
        'rams_mating': n_rams_mating,
        'rams_non_mating': n_rams_non_mating,
        'pens_mate': pens_mate,
        'pens_preg': pens_preg,
        'pens_nurs': pens_nurs,
        'pens_rest': pens_rest,
        'pens_fatt': pens_fatt,
        'pens_ram': pens_ram,
        'total_pens': total_pens,
        'annual_output': annual_output,
        'ewes_per_cycle': n_ewe_per_batch * n_batches,
    }


def exact_timeline_pens(n_ewe_per_batch, n_batches):
    """
    精确时间线模拟：按日计算一个完整周期内的羊栏占用情况。
    假设批次均匀交错（每 T_CYCLE/n_batches 天启动一批）。

    返回每天各类型羊栏占用数，以及最大占用数。
    """
    batch_interval = T_CYCLE / n_batches  # 批次间隔

    # 每个批次的起始偏移（天）
    batch_offsets = [i * batch_interval for i in range(n_batches)]

    # 在足够长的时间内模拟（覆盖所有批次至少一个完整周期）
    sim_days = int(T_CYCLE * 2 + n_batches * batch_interval)

    pens_mate_per_batch = 1
    pens_preg_per_batch = int(np.ceil(n_ewe_per_batch / CAP_PREG))
    pens_nurs_per_batch = int(np.ceil(n_ewe_per_batch / CAP_NURS))
    pens_rest_per_batch = int(np.ceil(n_ewe_per_batch / CAP_REST))
    n_lambs_per_batch = n_ewe_per_batch * LAMB_PER_BIRTH
    pens_fatt_per_batch = int(np.ceil(n_lambs_per_batch / CAP_FATT))

    daily_mate = np.zeros(sim_days)
    daily_preg = np.zeros(sim_days)
    daily_nurs = np.zeros(sim_days)
    daily_rest = np.zeros(sim_days)
    daily_fatt = np.zeros(sim_days)

    for offset in batch_offsets:
        # 配种期: [offset, offset+20)
        # 怀孕期: [offset+20, offset+20+149)
        # 哺乳期: [offset+20+149, offset+20+149+40)
        # 休整期: [offset+20+149+40, offset+20+149+40+20)
        # 育肥期 (羔羊): [offset+20+149+40, offset+20+149+40+210)
        #        = [offset+209, offset+419)

        t0 = int(np.floor(offset))
        t_mate_end = t0 + T_MATE
        t_preg_end = t_mate_end + T_PREG
        t_nurs_end = t_preg_end + T_NURS
        t_rest_end = t_nurs_end + T_REST
        t_fatt_end = t_nurs_end + T_FATT  # 羔羊断奶开始育肥

        # 为每个批次重复多个周期
        for cycle_start in [t0, t0 + T_CYCLE, t0 + 2 * T_CYCLE]:
            if cycle_start >= sim_days:
                break
            me = min(cycle_start + T_MATE, sim_days)
            pe = min(cycle_start + T_MATE + T_PREG, sim_days)
            ne = min(cycle_start + T_MATE + T_PREG + T_NURS, sim_days)
            re = min(cycle_start + T_MATE + T_PREG + T_NURS + T_REST, sim_days)
            fe = min(cycle_start + T_MATE + T_PREG + T_NURS + T_FATT, sim_days)

            daily_mate[cycle_start:me] += pens_mate_per_batch
            daily_preg[cycle_start + T_MATE:pe] += pens_preg_per_batch
            daily_nurs[cycle_start + T_MATE + T_PREG:ne] += pens_nurs_per_batch
            daily_rest[cycle_start + T_MATE + T_PREG + T_NURS:re] += pens_rest_per_batch
            daily_fatt[cycle_start + T_MATE + T_PREG + T_NURS:fe] += pens_fatt_per_batch

    # 取稳态后的最大值（跳过前T_CYCLE天的预热期）
    warmup = T_CYCLE
    max_mate = int(np.max(daily_mate[warmup:])) if warmup < sim_days else int(np.max(daily_mate))
    max_preg = int(np.max(daily_preg[warmup:])) if warmup < sim_days else int(np.max(daily_preg))
    max_nurs = int(np.max(daily_nurs[warmup:])) if warmup < sim_days else int(np.max(daily_nurs))
    max_rest = int(np.max(daily_rest[warmup:])) if warmup < sim_days else int(np.max(daily_rest))
    max_fatt = int(np.max(daily_fatt[warmup:])) if warmup < sim_days else int(np.max(daily_fatt))

    # 公羊
    n_rams_mating = max_mate
    n_rams_total = max(int(np.ceil(n_ewe_per_batch * n_batches / RAM_EWE_RATIO)), n_rams_mating)
    n_rams_non_mating = max(0, n_rams_total - n_rams_mating)
    pens_ram = int(np.ceil(n_rams_non_mating / CAP_RAM)) if n_rams_non_mating > 0 else 0

    total = max_mate + max_preg + max_nurs + max_rest + max_fatt + pens_ram
    annual_output = n_ewe_per_batch * n_batches * LAMB_PER_BIRTH * 365.0 / T_CYCLE

    return {
        'n_ewe_per_batch': n_ewe_per_batch,
        'n_batches': n_batches,
        'total_base_ewes': n_ewe_per_batch * n_batches,
        'total_rams': n_rams_total,
        'pens_mate': max_mate,
        'pens_preg': max_preg,
        'pens_nurs': max_nurs,
        'pens_rest': max_rest,
        'pens_fatt': max_fatt,
        'pens_ram': pens_ram,
        'total_pens': total,
        'annual_output': annual_output,
    }


def find_optimal_configs():
    """寻找所有可行配置并找出最优"""
    results = []

    for n_ewe in range(1, CAP_MATE_EWE + 1):  # 每批1-14只母羊
        for n_batches in range(1, 200):  # 批次数
            # 先用近似法快速筛选
            r_approx = compute_pens_for_config(n_ewe, n_batches)
            if r_approx['total_pens'] <= TOTAL_PENS * 1.2:  # 宽松筛选
                r_exact = exact_timeline_pens(n_ewe, n_batches)
                if r_exact['total_pens'] <= TOTAL_PENS:
                    results.append(r_exact)

    return sorted(results, key=lambda x: x['annual_output'], reverse=True)


def compute_shortfall_for_target(target_output=1500):
    """计算达到目标年出栏量所需的羊栏缺口"""
    # 每只母羊年产出羔羊数
    lambs_per_ewe_per_year = LAMB_PER_BIRTH * 365.0 / T_CYCLE

    # 所需基础母羊总数
    ewes_needed = target_output / lambs_per_ewe_per_year

    # 尝试不同的每批母羊数，计算所需羊栏
    best_configs = []
    for n_ewe in range(1, CAP_MATE_EWE + 1):
        n_batches = int(np.ceil(ewes_needed / n_ewe))
        if n_batches < 1:
            continue
        r = exact_timeline_pens(n_ewe, n_batches)
        best_configs.append(r)

    best_configs.sort(key=lambda x: x['total_pens'])

    return {
        'ewes_needed': ewes_needed,
        'lambs_per_ewe_per_year': lambs_per_ewe_per_year,
        'configs': best_configs[:5],
        'min_pens_needed': best_configs[0]['total_pens'] if best_configs else None,
        'shortfall': best_configs[0]['total_pens'] - TOTAL_PENS if best_configs else None,
    }


# ============================================================
# 主程序
# ============================================================
if __name__ == '__main__':
    print("=" * 70)
    print("问题1: 代数递推模型 — 湖羊空间利用率分析")
    print("=" * 70)

    # ---------- 基本周期分析 ----------
    print("\n## 1. 基本周期参数")
    print(f"   配种期: {T_MATE}天")
    print(f"   怀孕期: {T_PREG}天")
    print(f"   哺乳期: {T_NURS}天")
    print(f"   休整期: {T_REST}天")
    print(f"   完整周期: {T_CYCLE}天")
    print(f"   育肥期: {T_FATT}天")
    print(f"   每胎产羔: {LAMB_PER_BIRTH}只")
    print(f"   年周期数: {365/T_CYCLE:.3f}")
    print(f"   每只母羊年产羔: {LAMB_PER_BIRTH * 365/T_CYCLE:.3f}只")

    # ---------- 寻找可行配置 ----------
    print("\n## 2. 寻找112栏下的可行配置")
    configs = find_optimal_configs()

    # 输出前20个最优配置
    print(f"\n   共找到 {len(configs)} 个可行配置，按年出栏量排序（前20）：\n")
    print(f"   {'批次':>4s} {'每批':>4s} {'母羊':>6s} {'公羊':>4s} | {'配种':>4s} {'怀孕':>4s} {'哺乳':>4s} {'休整':>4s} {'育肥':>4s} {'公羊栏':>5s} | {'总栏':>4s} {'年出栏':>8s}")
    print("   " + "-" * 85)

    top_configs = []
    for i, c in enumerate(configs[:20]):
        print(f"   {c['n_batches']:4d} {c['n_ewe_per_batch']:4d} {c['total_base_ewes']:6d} {c['total_rams']:4d} | "
              f"{c['pens_mate']:4d} {c['pens_preg']:4d} {c['pens_nurs']:4d} {c['pens_rest']:4d} {c['pens_fatt']:4d} {c['pens_ram']:5d} | "
              f"{c['total_pens']:4d} {c['annual_output']:8.1f}")
        top_configs.append(c)

    # ---------- 推荐配置 ----------
    print("\n## 3. 推荐配置")
    best = configs[0]
    print(f"\n   推荐配置（最大化年出栏量）：")
    print(f"   - 基础母羊总数: {best['total_base_ewes']} 只")
    print(f"   - 每批母羊数: {best['n_ewe_per_batch']} 只")
    print(f"   - 批次数: {best['n_batches']} 批")
    print(f"   - 种公羊总数: {best['total_rams']} 只")
    print(f"   - 年化出栏量: {best['annual_output']:.1f} 只")
    print(f"   - 总羊栏使用: {best['total_pens']} 栏")
    print(f"   - 空闲栏数: {TOTAL_PENS - best['total_pens']} 栏")

    # 输出前5名
    print("\n   前5名配置：")
    df_top = pd.DataFrame(configs[:5])
    print(df_top[['n_batches', 'n_ewe_per_batch', 'total_base_ewes', 'total_rams',
                   'total_pens', 'annual_output']].to_string(index=False))

    # ---------- 年出栏量范围 ----------
    print("\n## 4. 年出栏量范围")
    outputs = [c['annual_output'] for c in configs]
    # 去重后的范围
    print(f"   最低年出栏量: {min(outputs):.1f} 只")
    print(f"   最高年出栏量: {max(outputs):.1f} 只")
    print(f"   可达到的出栏量范围: [{min(outputs):.0f}, {max(outputs):.0f}] 只/年")

    # ---------- 1500只/年的缺口 ----------
    print("\n## 5. 年出栏1500只的羊栏缺口")
    shortfall_info = compute_shortfall_for_target(1500)
    print(f"\n   每只母羊年产羔: {shortfall_info['lambs_per_ewe_per_year']:.3f} 只")
    print(f"   所需基础母羊: {shortfall_info['ewes_needed']:.1f} 只")

    for i, cfg in enumerate(shortfall_info['configs']):
        print(f"\n   方案{i+1}: {cfg['n_ewe_per_batch']}只/批 × {cfg['n_batches']}批 = {cfg['total_base_ewes']}只母羊")
        print(f"       需要羊栏: {cfg['total_pens']} 栏")
        print(f"       预计年出栏: {cfg['annual_output']:.1f} 只")
        print(f"       羊栏缺口: {cfg['total_pens'] - TOTAL_PENS} 栏")

    print(f"\n   最小所需羊栏数: {shortfall_info['min_pens_needed']} 栏")
    print(f"   最小羊栏缺口: {shortfall_info['shortfall']} 栏")

    # ---------- 保存结果 ----------
    print("\n## 6. 保存结果到CSV")
    df_all = pd.DataFrame(configs)
    df_all.to_csv('/home/user/workspace/output/problem1_configs.csv', index=False, encoding='utf-8-sig')
    print(f"   已保存 {len(configs)} 条配置到 output/problem1_configs.csv")

    # 保存详细结果
    with open('/home/user/workspace/output/problem1_results.txt', 'w', encoding='utf-8') as f:
        f.write("问题1: 代数递推模型结果\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"完整周期: {T_CYCLE}天\n")
        f.write(f"每年每只母羊周期数: {365/T_CYCLE:.4f}\n")
        f.write(f"每只母羊年产羔: {LAMB_PER_BIRTH * 365/T_CYCLE:.3f}只\n\n")
        f.write(f"最优配置:\n")
        f.write(f"  基础母羊: {best['total_base_ewes']}只\n")
        f.write(f"  种公羊: {best['total_rams']}只\n")
        f.write(f"  年出栏量: {best['annual_output']:.1f}只\n")
        f.write(f"  羊栏使用: {best['total_pens']}栏\n\n")
        f.write(f"1500只/年目标:\n")
        f.write(f"  最小羊栏需求: {shortfall_info['min_pens_needed']}栏\n")
        f.write(f"  缺口: {shortfall_info['shortfall']}栏\n")

    print("   已保存详细结果到 output/problem1_results.txt")
    print("\n" + "=" * 70)
    print("问题1求解完成！")
