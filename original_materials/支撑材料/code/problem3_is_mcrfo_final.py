#!/usr/bin/env python3
"""
Problem 3 IS-MCRFO Final
个体状态驱动的蒙特卡洛滚动反馈优化模型
Individual-State Monte Carlo Rolling Feedback Optimization
"""
import numpy as np
import pandas as pd
import json
import os
import sys
import time
import itertools
from collections import defaultdict

# ============================================================
# Monkey-patch engine before aliasing
# ============================================================
import problem3_engine_v4_1 as eng

# Override litter distribution: P(2)=0.8, P(3)=0.2  (mean=2.2)
eng.LITTER_PROBS = [0.0, 0.8, 0.2, 0.0]

# Verify patch took effect
assert eng.LITTER_PROBS == [0.0, 0.8, 0.2, 0.0], \
    f"LITTER_PROBS patch failed: {eng.LITTER_PROBS}"

# Alias all constants and classes from the patched engine
Farm = eng.Farm
T_MATE = eng.T_MATE
T_PENDING = eng.T_PENDING
T_PREG_MIN = eng.T_PREG_MIN
T_PREG_MAX = eng.T_PREG_MAX
T_NURS = eng.T_NURS
T_REST_MIN = eng.T_REST_MIN
T_FATT = eng.T_FATT
CAP_MATE = eng.CAP_MATE
CAP_PENDING = eng.CAP_PENDING
CAP_PREG = eng.CAP_PREG
CAP_NURS = eng.CAP_NURS
CAP_REST = eng.CAP_REST
CAP_FATT = eng.CAP_FATT
CAP_RAM = eng.CAP_RAM
CONCEPTION_RATE = eng.CONCEPTION_RATE
LAMB_MORTALITY = eng.LAMB_MORTALITY
LITTER_PROBS = eng.LITTER_PROBS
COST_EMPTY = eng.COST_EMPTY
COST_SHORTAGE = eng.COST_SHORTAGE
TOTAL_PENS = eng.TOTAL_PENS
ST_AVAIL = eng.ST_AVAIL
ST_MATE = eng.ST_MATE
ST_PENDING = eng.ST_PENDING
ST_PREG = eng.ST_PREG
ST_NURS = eng.ST_NURS
ST_REST = eng.ST_REST
count_pens_merged = eng.count_pens_merged

# ============================================================
# Constants
# ============================================================
OUT_DIR = '/home/user/workspace/output'
WARMUP = 840
EVAL = 1825
TOTAL_DAYS = WARMUP + EVAL
ROLL = 7
SRNG_OFFSET = 7654321  # Must stay within 32-bit range for numpy RandomState

SCREEN_SEEDS = list(range(1000, 1010))
FINAL_SEEDS = list(range(2000, 2030))

# Scheme A: deterministic 31-batch schedule (from problem 2 final)
A_STARTS = [
    0, 7, 15, 22, 30, 37, 44, 52, 59, 66,
    74, 81, 89, 96, 103, 111, 118, 126, 133, 140,
    148, 155, 163, 170, 177, 185, 192, 199, 207, 214, 222
]
A_SIZES = [
    14, 14, 13, 14, 14, 14, 14, 13, 14, 14,
    13, 14, 14, 14, 14, 14, 14, 14, 14, 13,
    14, 13, 14, 14, 14, 13, 14, 13, 14, 14, 13
]


# ============================================================
# Monkey-patch Farm.step for faster fattening (allowed: runtime, not source)
# ============================================================
_original_step = Farm.step
_original_init = Farm.__init__


def _fast_init(self, n_ewes, n_rams):
    """Optimized __init__ with pre-allocated fattening tracking."""
    _original_init(self, n_ewes, n_rams)
    self._fatt_by_sell = {}  # sell_day -> list of lamb counts


def _fast_step(self, rng):
    """Vectorized step: process all state transitions in bulk using numpy."""
    d = self.day
    state = self.state
    mate_start = self.mate_start
    hidden_conceived = self.hidden_conceived
    conception_day = self.conception_day
    preg_len = self.preg_len
    birth_day = self.birth_day
    wean_day = self.wean_day
    rest_start = self.rest_start
    rest_reason = self.rest_reason
    eligible_day = self.eligible_day
    N = self.N
    # Dynamically resolve eng globals for sensitivity support
    _T_NURS = eng.T_NURS
    _T_FATT = eng.T_FATT

    # ---- MATE → PENDING ----
    mate_mask = (state == ST_MATE) & (d >= mate_start + T_MATE)
    if mate_mask.any():
        n_mate = mate_mask.sum()
        conc = rng.random(size=n_mate) < CONCEPTION_RATE
        cday = rng.randint(0, T_MATE, size=n_mate)
        plen = rng.randint(T_PREG_MIN, T_PREG_MAX + 1, size=n_mate)

        hidden_conceived[mate_mask] = conc
        self.n_matings += int(n_mate)
        self.n_conceptions += int(conc.sum())

        idx = np.where(mate_mask)[0]
        state[idx] = ST_PENDING
        conception_day[idx] = cday.astype(np.int8)
        preg_len[idx] = plen.astype(np.int16)

    # ---- PENDING → PREG or REST ----
    pend_mask = (state == ST_PENDING) & (d >= mate_start + T_MATE + T_PENDING)
    if pend_mask.any():
        idx = np.where(pend_mask)[0]
        conceived = hidden_conceived[pend_mask]
        cidx = idx[conceived]
        fidx = idx[~conceived]

        if len(cidx) > 0:
            state[cidx] = ST_PREG
            birth_day[cidx] = (
                mate_start[cidx].astype(np.int32) +
                conception_day[cidx].astype(np.int32) +
                preg_len[cidx].astype(np.int32)
            )
            for i in cidx:
                self._log(i, d, 'DIAGNOSIS_SUCCESS')

        if len(fidx) > 0:
            state[fidx] = ST_REST
            rest_start[fidx] = d
            rest_reason[fidx] = 0
            eligible_day[fidx] = d + T_REST_MIN
            for i in fidx:
                self._log(i, d, 'DIAGNOSIS_FAIL')

    # ---- PREG → NURS ----
    preg_mask = (state == ST_PREG) & (d >= birth_day)
    if preg_mask.any():
        idx = np.where(preg_mask)[0]
        n_birth = len(idx)
        nl = rng.choice([1, 2, 3, 4], size=n_birth, p=LITTER_PROBS).astype(int)
        sv = rng.binomial(nl, 1 - LAMB_MORTALITY).astype(int)

        self.total_born_gross += int(nl.sum())
        self.total_born_net += int(sv.sum())
        self.n_births += n_birth

        state[idx] = ST_NURS
        wd = d + _T_NURS
        wean_day[idx] = wd
        for i, d_i in zip(idx, range(n_birth)):
            self.birth_days[i].append(d)
            if (s := int(sv[d_i])) > 0:
                sell_day = wd + _T_FATT
                if sell_day not in self._fatt_by_sell:
                    self._fatt_by_sell[sell_day] = []
                self._fatt_by_sell[sell_day].append(s)
            self._log(i, d, 'BIRTH')

    # ---- NURS → REST ----
    nurs_mask = (state == ST_NURS) & (d >= wean_day)
    if nurs_mask.any():
        idx = np.where(nurs_mask)[0]
        state[idx] = ST_REST
        rest_start[idx] = d
        rest_reason[idx] = 1
        eligible_day[idx] = d + T_REST_MIN
        for i in idx:
            self._log(i, d, 'WEAN')

    # ---- REST → AVAIL ----
    rest_mask = (state == ST_REST) & (d >= eligible_day)
    if rest_mask.any():
        idx = np.where(rest_mask)[0]
        state[idx] = ST_AVAIL
        mate_start[idx] = -1
        for i in idx:
            self._log(i, d, 'AVAILABLE')

    # ---- Fattening completion (O(1) dict lookup) ----
    if d in self._fatt_by_sell:
        for nl in self._fatt_by_sell[d]:
            self.total_sold += nl
            self.lambs_sold_by_day[d] = self.lambs_sold_by_day.get(d, 0) + nl
            self._log(-1, d, 'SOLD')
        del self._fatt_by_sell[d]

    # Rebuild fattening list for get_pens() compatibility
    self.fattening = [
        (sell_day - T_FATT, nl)
        for sell_day, nls in self._fatt_by_sell.items()
        for nl in nls
    ]


Farm.__init__ = _fast_init
Farm.step = _fast_step


# ============================================================
# Fast helpers using numpy vectorized operations
# ============================================================
def _fast_state_indices(state_arr, target_state):
    """Return indices where state == target_state (as numpy array)."""
    return np.where(state_arr == target_state)[0]


def _fast_mate_batches(state_arr, mate_start_arr):
    """Count ewes per mate_start day for ST_MATE ewes only (vectorized)."""
    mask = state_arr == ST_MATE
    if not mask.any():
        return 0, defaultdict(int), {}
    starts = mate_start_arr[mask]
    # Use numpy unique for fast counting
    uniq, counts = np.unique(starts, return_counts=True)
    batch_dict = {int(u): int(c) for u, c in zip(uniq, counts)}
    return len(uniq), batch_dict, batch_dict


def _fast_nurs_items(state_arr, birth_day_arr):
    """Collect (birth_day, 1) for all ST_NURS ewes (vectorized)."""
    mask = state_arr == ST_NURS
    if not mask.any():
        return []
    bd = birth_day_arr[mask]
    mask2 = bd >= 0
    return [(int(bd[i]), 1) for i in np.where(mask2)[0]]


def _fast_rest_items(state_arr, rest_start_arr, rest_reason_arr):
    """Collect (rest_start, 1) for ST_REST ewes, split by reason."""
    mask = state_arr == ST_REST
    if not mask.any():
        return [], []
    rs = rest_start_arr[mask]
    rr = rest_reason_arr[mask]
    mask2 = rs >= 0
    rs = rs[mask2]
    rr = rr[mask2]
    fail = [(int(rs[i]), 1) for i in np.where(rr == 0)[0]]
    birth = [(int(rs[i]), 1) for i in np.where(rr == 1)[0]]
    return fail, birth


# ============================================================
# ObservableState — only publicly visible information
# ============================================================
class ObservableState:
    """Snapshot of farm state accessible to the strategy function."""

    def __init__(self, farm):
        self.day = farm.day
        self.N = farm.N
        self.R = farm.R
        self.n_avail = farm.n_in_state(ST_AVAIL)
        self.n_mate = farm.n_in_state(ST_MATE)
        self.n_pend = farm.n_in_state(ST_PENDING)
        self.n_preg = farm.n_in_state(ST_PREG)
        self.n_nurs = farm.n_in_state(ST_NURS)
        self.n_rest = farm.n_in_state(ST_REST)

        # Active mating batches grouped by mate_start_day (vectorized)
        self.active_batches, self.mate_batches, _ = \
            _fast_mate_batches(farm.state, farm.mate_start)

        # Fattening lambs currently in the system
        d = farm.day
        self.n_fatt = sum(
            nl for wd, nl in farm.fattening
            if 0 <= d - wd < T_FATT
        )
        self.total_rams = farm.R

        self.pens = self._pens(farm)

    def _pens(self, farm):
        d = farm.day
        R = farm.R

        # NURS and REST items (vectorized)
        nurs = _fast_nurs_items(farm.state, farm.birth_day)
        rest_fail, rest_birth = _fast_rest_items(
            farm.state, farm.rest_start, farm.rest_reason)

        # PEN CALCULATIONS
        pa = int(np.ceil(self.n_avail / CAP_MATE)) if self.n_avail > 0 else 0

        # MATE pen: per-batch ceiling (fixed-cohort rule)
        pm = sum(int(np.ceil(c / CAP_MATE)) for c in self.mate_batches.values())

        pp = int(np.ceil(self.n_pend / CAP_PENDING)) if self.n_pend > 0 else 0
        pg = int(np.ceil(self.n_preg / CAP_PREG)) if self.n_preg > 0 else 0
        pn = count_pens_merged(nurs, 7, CAP_NURS)
        pr = (count_pens_merged(rest_fail, 7, CAP_REST) +
              count_pens_merged(rest_birth, 7, CAP_REST))

        pf_items = [(wd, nl) for wd, nl in farm.fattening if 0 <= d - wd < T_FATT]
        pf = count_pens_merged(pf_items, 7, CAP_FATT)

        pram = int(np.ceil(max(0, R - pm) / CAP_RAM))
        t = pa + pm + pp + pg + pn + pr + pf + pram
        return {
            'avail': pa, 'mate': pm, 'pending': pp, 'preg': pg,
            'nurs': pn, 'rest': pr, 'fatt': pf, 'ram': pram,
            'total': t,
            'empty': max(0, TOTAL_PENS - t),
            'shortage': max(0, t - TOTAL_PENS),
            'loss': (max(0, TOTAL_PENS - t) * COST_EMPTY +
                     max(0, t - TOTAL_PENS) * COST_SHORTAGE),
        }


# ============================================================
# Decision helpers
# ============================================================
def preview_action(obs, q):
    """Compute total pens after executing action q, without side effects."""
    if q == 0:
        return obs.pens['total']
    bn = int(np.ceil(q / CAP_MATE))
    if obs.active_batches + bn > obs.R:
        return None
    na = obs.n_avail - q
    pa = int(np.ceil(na / CAP_MATE)) if na > 0 else 0
    pm = obs.pens['mate'] + bn
    return obs.pens['total'] + (pa + pm) - (obs.pens['avail'] + obs.pens['mate'])


def decide_action(obs, params):
    """
    Choose the maximum feasible q ∈ {21,14,7,0} respecting:
      q ≤ available ewes
      active_batches + ceil(q/14) ≤ R
      after-action pens ≤ 112 − B
    """
    N, q_max, B = params
    for q in [q for q in [21, 14, 7, 0] if q <= q_max]:
        if q > obs.n_avail:
            continue
        bn = int(np.ceil(q / CAP_MATE))
        if obs.active_batches + bn > obs.R:
            continue
        after = preview_action(obs, q)
        if after is not None and after <= TOTAL_PENS - B:
            return q, f'q={q}', after
    return 0, 'default', obs.pens['total']


# ============================================================
# Simulation runner
# ============================================================
def run_one(N, R, sfn, args, seed, is_fb=False):
    """
    Run one simulation replicate.

    Returns (stats_dict, daily_log_df, decisions_df).
    """
    # CRN: derive srng deterministically from seed (no master rng consumption)
    srng_seed = (seed + SRNG_OFFSET) & 0xFFFFFFFF
    srng = np.random.RandomState(srng_seed)

    farm = Farm(N, R)
    dlog = []      # daily metrics (post-warmup)
    decs = []      # decision records (only for feedback strategies)

    for day in range(TOTAL_DAYS):
        q = 0
        reason = ''
        after_total = 0
        obs_before = None

        if is_fb and day % ROLL == 0:
            obs_before = ObservableState(farm)
            q, reason, after_total = decide_action(obs_before, args)
        elif not is_fb:
            q, reason, _discard = sfn(farm, day, args)
            after_total = 0

        # Execute the action: all q ewes start on the SAME day,
        # split into fixed batches of ≤ CAP_MATE (14) ewes each.
        executed_q = 0
        if q > 0:
            avail_ids = np.where(farm.state == ST_AVAIL)[0]
            nm = int(np.sum(farm.state == ST_MATE))
            mx = max(0, R * CAP_MATE - nm)
            n_to_mate = min(q, len(avail_ids), mx)
            for b in range(0, n_to_mate, CAP_MATE):
                batch = avail_ids[b:b + CAP_MATE]
                farm.start_mating(batch.tolist(), day)
            executed_q = n_to_mate

        # Record decision (for feedback strategies)
        if is_fb and day % ROLL == 0 and obs_before is not None:
            decs.append({
                'day': day,
                'planned_q': q,
                'executed_q': executed_q,
                'decision_reason': reason,
                'current_total_pens': obs_before.pens['total'],
                'after_action_pens': after_total,
                'available_before': obs_before.n_avail,
                'active_mating_batches': obs_before.active_batches,
            })

        # Process today's transitions and events
        farm.step(srng)

        # Record metrics (post-warmup only) — use fast get_pens() not ObservableState
        if day >= WARMUP:
            pens = farm.get_pens()
            dlog.append({
                'day': day,
                'pens_total': pens['total'],
                'empty': pens['empty'],
                'shortage': pens['shortage'],
                'daily_loss': pens['loss'],
                'lambs_sold_today': farm.lambs_sold_by_day.get(day, 0),
            })

        farm.day += 1

    # Compute statistics
    df = pd.DataFrame(dlog)
    el = int(df['lambs_sold_today'].sum())
    annual = el * 365.0 / EVAL

    stats = {
        'annual_output': float(annual),
        'eval_lambs_sold': el,
        'total_sold': farm.total_sold,
        'mean_daily_loss': float(df['daily_loss'].mean()),
        'mean_idle': float(df['empty'].mean()),
        'mean_shortage': float(df['shortage'].mean()),
        'utilization': float(df['pens_total'].mean() / TOTAL_PENS * 100),
        'loss_std': float(df['daily_loss'].std()),
        'loss_p95': float(np.percentile(df['daily_loss'], 95)),
        'loss_cvar95': float(np.mean(
            df['daily_loss'][df['daily_loss'] >= np.percentile(df['daily_loss'], 95)]
        )),
        'rental_day_ratio': float((df['shortage'] > 0).mean()),
        'planned_matings': sum(d['planned_q'] for d in decs),
        'executed_matings': sum(d['executed_q'] for d in decs),
        'execution_rate': (sum(d['executed_q'] for d in decs) /
                           max(1, sum(d['planned_q'] for d in decs))),
    }

    df_decs = pd.DataFrame(decs) if decs else pd.DataFrame()
    return stats, df, df_decs


# ============================================================
# Deterministic schedule strategies (A and B)
# ============================================================
def sched_A(farm, day, args):
    """Scheme A: deterministic 31-batch open-loop schedule."""
    starts, sizes = args
    T = 229
    for s, b in zip(starts, sizes):
        if day % T == s:
            obs = ObservableState(farm)
            nm = int(np.sum(farm.state == ST_MATE))
            cap = max(0, farm.R * CAP_MATE - nm)
            n = min(b, obs.n_avail, cap)
            return n, 'A_sched', 0
    return 0, 'A_idle', 0


def sched_B(farm, day, args):
    """Scheme B: uniform 27-batch × 14 ewes per 229-day cycle."""
    T = 229
    nb = 27
    offs = set(int(round(i * T / nb)) % T for i in range(nb))
    if day % T in offs:
        obs = ObservableState(farm)
        nm = int(np.sum(farm.state == ST_MATE))
        cap = max(0, farm.R * CAP_MATE - nm)
        n = min(14, obs.n_avail, cap)
        return n, 'B_sched', 0
    return 0, 'B_idle', 0


# ============================================================
# Unit tests
# ============================================================
def run_tests():
    print("=" * 60)
    print("IS-MCRFO 单元测试")
    print("=" * 60)
    p = f = 0

    def t(name, cond):
        nonlocal p, f
        if cond:
            print(f"  ✅ {name}")
            p += 1
        else:
            print(f"  ❌ {name}")
            f += 1

    # --- Test 1: 20d MATE → PENDING ---
    rng = np.random.RandomState(42)
    farm1 = Farm(10, 1)
    farm1.start_mating([0], 0)
    for _ in range(21):
        farm1.step(rng)
        farm1.day += 1
    t("T1: 20d MATE→PENDING", farm1.state[0] == ST_PENDING)

    # --- Test 2: 30d PENDING → diagnosis at day 50 ---
    farm2 = Farm(10, 1)
    farm2.start_mating([0], 0)
    rng2 = np.random.RandomState(200)
    for _ in range(51):
        farm2.step(rng2)
        farm2.day += 1
    t("T2: 30d PENDING→分流(day50)",
      farm2.state[0] in (ST_PREG, ST_REST))

    # --- Test 3: ObservableState has NO hidden variables ---
    farm3 = Farm(10, 1)
    farm3.start_mating([0], 0)
    for _ in range(25):
        farm3.step(np.random.RandomState(77))
        farm3.day += 1
    obs3 = ObservableState(farm3)
    t("T3a: obs无hidden_conceived", not hasattr(obs3, 'hidden_conceived'))
    t("T3b: obs无conception_day", not hasattr(obs3, 'conception_day'))
    t("T3c: obs无preg_len", not hasattr(obs3, 'preg_len'))

    # --- Test 4: overlapping mating batches → 2 pens ---
    farm4 = Farm(30, 3)
    farm4.start_mating(list(range(14)), 0)
    farm4.start_mating(list(range(14, 28)), 5)
    obs4 = ObservableState(farm4)
    t("T4: 重叠交配→2栏", obs4.pens['mate'] == 2)

    # --- Test 5: q=21 → 2 batches ---
    t("T5: q=21→2批(ceil(21/14))", int(np.ceil(21 / 14)) == 2)

    # --- Test 6: active batches ≤ R ---
    farm6 = Farm(200, 9)
    farm6.start_mating(list(range(9 * 14)), 0)
    obs6 = ObservableState(farm6)
    t("T6: mate批次≤R(9)", obs6.pens['mate'] <= 9)

    # --- Test 7: PENDING 按 8只/栏独立计算 ---
    farm7 = Farm(20, 2)
    farm7.start_mating(list(range(20)), 0)
    for _ in range(25):
        farm7.step(rng)
        farm7.day += 1
    obs7 = ObservableState(farm7)
    t("T7: PENDING ceil/8(独立)",
      obs7.pens['pending'] == int(np.ceil(obs7.n_pend / 8)))

    # --- Test 8: NURS 7d合栏, 8d不合栏 ---
    t("T8a: NURS 7d合栏",
      count_pens_merged([(100, 3), (107, 3)], 7, CAP_NURS) == 1)
    t("T8b: NURS 8d不合栏",
      count_pens_merged([(100, 3), (108, 3)], 7, CAP_NURS) == 2)

    # --- Test 9: REST 7d合栏, 8d不合栏 ---
    t("T9a: REST 7d合栏",
      count_pens_merged([(100, 1), (107, 1)], 7, CAP_REST) == 1)
    t("T9b: REST 8d不合栏",
      count_pens_merged([(100, 1), (108, 1)], 7, CAP_REST) == 2)

    # --- Test 10: FATT 7d合栏, 8d不合栏 ---
    t("T10a: FATT 7d合栏",
      count_pens_merged([(100, 7), (107, 7)], 7, CAP_FATT) == 1)
    t("T10b: FATT 8d不合栏",
      count_pens_merged([(100, 7), (108, 7)], 7, CAP_FATT) == 2)

    # --- Test 11: preview_action does not modify Farm state ---
    farm11 = Farm(20, 2)
    obs11 = ObservableState(farm11)
    n_before = farm11.n_available()
    preview_action(obs11, 7)
    t("T11: preview不修改Farm", farm11.n_available() == n_before)

    # --- Test 12: q=0 → no state change ---
    farm12 = Farm(20, 2)
    srng12 = np.random.RandomState(999)
    n_mate_before = farm12.n_in_state(ST_MATE)
    farm12.step(srng12)
    farm12.day += 1
    t("T12: q=0无新增配种", farm12.n_in_state(ST_MATE) <= n_mate_before)

    # --- Test 13: CSV lambs_sold_today sum == eval sum ---
    farm13 = Farm(50, 4)
    srng13 = np.random.RandomState(888)
    farm13.start_mating(list(range(14)), 0)
    log_lambs = []
    for day in range(WARMUP + 100):
        if day >= WARMUP:
            log_lambs.append(farm13.lambs_sold_by_day.get(day, 0))
        farm13.step(srng13)
        farm13.day += 1
    csv_sum = sum(log_lambs)
    eval_sum = sum(
        v for d, v in farm13.lambs_sold_by_day.items()
        if WARMUP <= d < WARMUP + 100
    )
    t("T13: CSV合计==汇总出栏", csv_sum == eval_sum)

    # --- Test 14: daily_loss = idle + 3*shortage ---
    farm14 = Farm(200, 9)
    srng14 = np.random.RandomState(777)
    farm14.start_mating(list(range(9 * 14)), 0)
    for day in range(10):
        farm14.step(srng14)
        farm14.day += 1
    obs14 = ObservableState(farm14)
    p14 = obs14.pens
    expected_loss = p14['empty'] * COST_EMPTY + p14['shortage'] * COST_SHORTAGE
    t("T14: daily_loss=idle+3*shortage", abs(p14['loss'] - expected_loss) < 1e-9)

    # --- Test 15: CRN — same seed → identical srng streams ---
    crn_seed = (1000 + SRNG_OFFSET) & 0xFFFFFFFF
    srng_a = np.random.RandomState(crn_seed)
    srng_b = np.random.RandomState(crn_seed)
    t("T15: CRN同种子→同srng",
      np.all(srng_a.randint(0, 10 ** 9, size=100) ==
             srng_b.randint(0, 10 ** 9, size=100)))

    # --- Bonus: REST split by reason ---
    farm_r = Farm(20, 2)
    farm_r.state[0] = ST_REST
    farm_r.rest_start[0] = 100
    farm_r.rest_reason[0] = 0   # failed
    farm_r.state[1] = ST_REST
    farm_r.rest_start[1] = 100
    farm_r.rest_reason[1] = 1   # post-nursing
    obs_r = ObservableState(farm_r)
    t("T+: REST分reason→独立栏组",
      obs_r.pens['rest'] == 2)

    # --- Bonus: decision record structure ---
    params_test = (20, 21, 8)
    obs_d = ObservableState(Farm(20, 2))
    q_d, reason_d, after_d = decide_action(obs_d, params_test)
    t("T+: decide_action返回三元组",
      isinstance(q_d, int) and isinstance(reason_d, str) and isinstance(after_d, (int, float)))

    print(f"\n  {p}通过, {f}失败")
    return f == 0


# ============================================================
# Parallel runner for multiprocessing
# ============================================================
def _worker(job):
    """Multiprocessing worker: unpack and run_one."""
    N, R, sfn, args, seed, is_fb, meta = job
    stats, df_log, df_decs = run_one(N, R, sfn, args, seed, is_fb=is_fb)
    stats.update(meta)
    return stats


def run_parallel(jobs, max_workers=None):
    """Run jobs in parallel using ProcessPoolExecutor."""
    from concurrent.futures import ProcessPoolExecutor, as_completed
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, j): j for j in jobs}
        for future in as_completed(futures):
            results.append(future.result())
    return results


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---- Run tests ----
    if not run_tests():
        print("\n❌ 单元测试失败，终止运行。")
        sys.exit(1)
    print("✅ 全部测试通过\n")

    # Write test result
    with open(f'{OUT_DIR}/problem3_is_mcrfo_tests.txt', 'w') as f:
        f.write("IS-MCRFO 15项测试: PASS\n")

    # ---- Build parameter grid ----
    param_grid = list(itertools.product([378, 402, 426], [7, 14, 21], [4, 8]))

    # ================================================================
    # Phase 1: Screening (10 seeds each) — PARALLEL
    # ================================================================
    print(f"{'=' * 60}")
    print(f"阶段一: 筛选 ({len(param_grid)}反馈策略 + 2基准) × {len(SCREEN_SEEDS)}种子 "
          f"(并行)")
    print(f"{'=' * 60}")
    t1 = time.time()

    # Build job list
    screen_jobs = []
    for scheme, sfn, N, R, args, is_fb in [
        ('A', sched_A, 426, 9, (A_STARTS, A_SIZES), False),
        ('B', sched_B, 378, 8, (), False),
    ]:
        for seed in SCREEN_SEEDS:
            screen_jobs.append((N, R, sfn, args, seed, is_fb,
                                {'scheme': scheme, 'N': N, 'R': R,
                                 'seed': seed, 'phase': 'screen'}))
    for (N, q_max, B) in param_grid:
        R_val = max(1, int(np.ceil(N / 50)))
        for seed in SCREEN_SEEDS:
            screen_jobs.append((N, R_val, None, (N, q_max, B), seed, True,
                                {'scheme': 'C', 'N': N, 'R': R_val,
                                 'q_max': q_max, 'B': B,
                                 'seed': seed, 'phase': 'screen'}))

    print(f"  共 {len(screen_jobs)} 个任务, 并行执行中...")
    all_rows = run_parallel(screen_jobs)

    elapsed_screen = time.time() - t1
    print(f"  筛选并行耗时: {elapsed_screen:.0f}s")

    # Print per-scheme summary
    for scheme in ['A', 'B']:
        sub = [r for r in all_rows if r['scheme'] == scheme]
        if sub:
            print(f"  {scheme}: out={np.mean([s['annual_output'] for s in sub]):.0f} "
                  f"loss={np.mean([s['mean_daily_loss'] for s in sub]):.1f}")
    for (N, q_max, B) in param_grid:
        sub = [r for r in all_rows
               if r['scheme'] == 'C' and r['N'] == N
               and r.get('q_max') == q_max and r.get('B') == B]
        if sub:
            print(f"  C(N={N},q={q_max},B={B}): "
                  f"out={np.mean([s['annual_output'] for s in sub]):.0f} "
                  f"loss={np.mean([s['mean_daily_loss'] for s in sub]):.1f}")

    df_screen = pd.DataFrame(all_rows)
    df_screen.to_csv(
        f'{OUT_DIR}/problem3_is_mcrfo_screening_replications.csv', index=False)

    # Compute reference and feasibility
    ref_A = df_screen[df_screen['scheme'] == 'A']['annual_output'].mean()
    Y_min = 0.95 * ref_A

    summary = []
    for (N, q_max, B) in param_grid:
        sub = df_screen[
            (df_screen['scheme'] == 'C') &
            (df_screen['N'] == N) &
            (df_screen['q_max'] == q_max) &
            (df_screen['B'] == B)
        ]
        if len(sub) == 0:
            continue
        mo = np.mean(sub['annual_output'])
        ml = np.mean(sub['mean_daily_loss'])
        summary.append({
            'N': N, 'q_max': q_max, 'B': B,
            'mean_output': mo, 'mean_loss': ml,
            'feasible': mo >= Y_min,
        })

    df_sum = pd.DataFrame(summary)
    df_sum.to_csv(
        f'{OUT_DIR}/problem3_is_mcrfo_screening_summary.csv', index=False)

    feasible = df_sum[df_sum['feasible']]
    if len(feasible) > 0:
        top = feasible.sort_values('mean_loss').head(3)
    else:
        top = df_sum.sort_values('mean_output', ascending=False).head(3)

    print(f"\n  Y_ref = {ref_A:.0f}   Y_min(95%) = {Y_min:.0f}")
    print(f"  可行策略: {len(feasible)}/{len(param_grid)}")
    print(f"  Top 3:")
    print(top.to_string(index=False))
    print(f"  筛选耗时: {time.time() - t1:.0f}s")

    # ================================================================
    # Phase 2: Final evaluation (30 seeds each) — PARALLEL
    # ================================================================
    print(f"\n{'=' * 60}")
    print(f"阶段二: 正式 ({len(top) + 2}方案) × {len(FINAL_SEEDS)}种子 (并行)")
    print(f"{'=' * 60}")
    t2 = time.time()

    # Build final job list
    final_jobs = []
    for scheme, sfn, N, R, args in [
        ('A', sched_A, 426, 9, (A_STARTS, A_SIZES)),
        ('B', sched_B, 378, 8, ()),
    ]:
        for seed in FINAL_SEEDS:
            final_jobs.append((N, R, sfn, args, seed, False,
                               {'scheme': scheme, 'N': N, 'R': R,
                                'seed': seed, 'phase': 'final'}))

    top_params_list = []
    for rank, (_, row) in enumerate(top.iterrows()):
        N = int(row['N'])
        q_max = int(row['q_max'])
        B = int(row['B'])
        R_val = max(1, int(np.ceil(N / 50)))
        top_params_list.append({
            'rank': rank + 1, 'N': N, 'q_max': q_max, 'B': B, 'R': R_val,
        })
        for seed in FINAL_SEEDS:
            final_jobs.append((N, R_val, None, (N, q_max, B), seed, True,
                               {'scheme': f'C_top{rank + 1}', 'N': N,
                                'R': R_val, 'q_max': q_max, 'B': B,
                                'seed': seed, 'phase': 'final'}))

    print(f"  共 {len(final_jobs)} 个任务, 并行执行中...")
    final_rows = run_parallel(final_jobs)
    print(f"  正式并行耗时: {time.time() - t2:.0f}s")

    df_final = pd.DataFrame(final_rows)
    df_final.to_csv(
        f'{OUT_DIR}/problem3_is_mcrfo_final_replications.csv', index=False)

    # Summary with confidence intervals
    from scipy import stats as spstats

    fsum = []
    for scheme in ['A', 'B', 'C_top1', 'C_top2', 'C_top3']:
        sub = df_final[df_final['scheme'] == scheme]
        if len(sub) == 0:
            continue
        o = sub['annual_output'].values
        l = sub['mean_daily_loss'].values
        n = len(o)
        mo = np.mean(o)
        so = np.std(o, ddof=1)
        ml = np.mean(l)
        sl = np.std(l, ddof=1)
        cio = spstats.t.interval(0.95, n - 1, loc=mo, scale=so / np.sqrt(n))
        cil = spstats.t.interval(0.95, n - 1, loc=ml, scale=sl / np.sqrt(n))
        fsum.append({
            'scheme': scheme,
            'mean_output': mo, 'std_output': so,
            'ci95_output_low': cio[0], 'ci95_output_high': cio[1],
            'mean_loss': ml, 'std_loss': sl,
            'ci95_loss_low': cil[0], 'ci95_loss_high': cil[1],
            'mean_idle': np.mean(sub['mean_idle']),
            'mean_shortage': np.mean(sub['mean_shortage']),
            'utilization': np.mean(sub['utilization']),
            'rental_day_ratio': np.mean(sub['rental_day_ratio']),
        })
    df_fsum = pd.DataFrame(fsum)
    df_fsum.to_csv(
        f'{OUT_DIR}/problem3_is_mcrfo_final_summary.csv', index=False)
    print(df_fsum.to_string(index=False))

    # Comparison vs A
    a_row = df_fsum[df_fsum['scheme'] == 'A']
    if len(a_row) > 0:
        ao = a_row['mean_output'].values[0]
        al = a_row['mean_loss'].values[0]
        for s in ['B', 'C_top1', 'C_top2', 'C_top3']:
            r = df_fsum[df_fsum['scheme'] == s]
            if len(r) > 0:
                print(f"  {s} vs A: "
                      f"output {(r['mean_output'].values[0] / ao - 1) * 100:+.1f}%  "
                      f"loss {(r['mean_loss'].values[0] / al - 1) * 100:+.1f}%")

    # ================================================================
    # Sensitivity: nursing duration h ∈ {35, 40, 45} — PARALLEL
    # ================================================================
    print(f"\n{'=' * 60}")
    print("哺乳期敏感性分析 (h=35/40/45) (并行)")
    print(f"{'=' * 60}")

    top1 = top.iloc[0]
    N_t = int(top1['N'])
    q_t = int(top1['q_max'])
    B_t = int(top1['B'])
    R_t = max(1, int(np.ceil(N_t / 50)))

    sens_jobs = []
    for h in [35, 40, 45]:
        fatt_h = 210 - 2 * (h - 40)
        for seed in FINAL_SEEDS:
            sens_jobs.append((N_t, R_t, None, (N_t, q_t, B_t), seed, True,
                              {'h': h, 'T_NURS': h, 'T_FATT': fatt_h,
                               'seed': seed, 'phase': 'sensitivity'}))

    # For sensitivity, we need to run with different T_NURS/T_FATT settings.
    # We'll run sequentially for each h since we need to change eng globals.
    sens = []
    for h in [35, 40, 45]:
        on = eng.T_NURS
        of = eng.T_FATT
        eng.T_NURS = h
        eng.T_FATT = 210 - 2 * (h - 40)

        h_jobs = [(N_t, R_t, None, (N_t, q_t, B_t), seed, True,
                   {'h': h, 'seed': seed, 'phase': 'sensitivity'})
                  for seed in FINAL_SEEDS]
        h_results = run_parallel(h_jobs)
        sens.extend(h_results)

        eng.T_NURS = on
        eng.T_FATT = of
        sub = [s for s in sens if s['h'] == h]
        if sub:
            print(f"  h={h}: out={np.mean([s['annual_output'] for s in sub]):.0f}  "
                  f"loss={np.mean([s['mean_daily_loss'] for s in sub]):.1f}")
    pd.DataFrame(sens).to_csv(
        f'{OUT_DIR}/problem3_is_mcrfo_sensitivity.csv', index=False)

    # ================================================================
    # Daily logs for seed=2000 (A, B, Top1)
    # ================================================================
    print(f"\n{'=' * 60}")
    print("生成seed=2000每日日志")
    print(f"{'=' * 60}")

    for scheme, sfn, N, R, args, label, is_fb in [
        ('A', sched_A, 426, 9, (A_STARTS, A_SIZES), 'A', False),
        ('B', sched_B, 378, 8, (), 'B', False),
        ('C', None, N_t, R_t, (N_t, q_t, B_t), 'Top1', True),
    ]:
        stats, df_log, df_decs = run_one(N, R, sfn, args, 2000, is_fb=is_fb)
        df_log.to_csv(
            f'{OUT_DIR}/problem3_is_mcrfo_daily_{label}_seed2000.csv',
            index=False)
        if is_fb and len(df_decs) > 0:
            df_decs.to_csv(
                f'{OUT_DIR}/problem3_is_mcrfo_decisions_top1.csv',
                index=False)
            print(f"  决策记录: {len(df_decs)}行 → decisions_top1.csv")

    # ================================================================
    # Config and summary
    # ================================================================
    config = {
        'model': 'IS-MCRFO',
        'model_full': '个体状态驱动的蒙特卡洛滚动反馈优化模型',
        'engine': 'v4.1',
        'warmup': WARMUP, 'eval': EVAL, 'total_days': TOTAL_DAYS,
        'decision_interval': ROLL,
        'screen_seeds': SCREEN_SEEDS, 'final_seeds': FINAL_SEEDS,
        'param_grid': {
            'N_values': [378, 402, 426],
            'q_max_values': [7, 14, 21],
            'B_values': [4, 8],
        },
        'top_params': top_params_list,
        'Y_ref': float(ref_A), 'Y_min': float(Y_min),
        'litter_probs': eng.LITTER_PROBS,
        'crn_offset': SRNG_OFFSET,
    }
    with open(f'{OUT_DIR}/problem3_is_mcrfo_config.json', 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    # ================================================================
    # Final verification
    # ================================================================
    print(f"\n{'=' * 60}")
    print("输出验证")
    print(f"{'=' * 60}")
    print(f"  筛选重复表: {len(df_screen)} 行 (预期 200)")
    print(f"  正式重复表: {len(df_final)} 行 (预期 150)")
    print(f"  敏感性表:   {len(sens)} 行 (预期 90)")
    print(f"  总耗时: {time.time() - t0:.0f}s")
    print("完成。")
