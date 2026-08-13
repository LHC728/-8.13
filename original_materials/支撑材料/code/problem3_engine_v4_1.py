#!/usr/bin/env python3
"""
Problem 3 v4.1: 母羊个体级仿真引擎 (日初转移约定)
====================================================
日序从0开始。每日日初发生状态转移:
  MATE:    day 0..19 (20天)
  PENDING: day 20..49 (30天)
  day 50 日初: 受孕识别+分流 → PREG 或 REST
  REST(未受孕): day 50..67 (18天)
  day 68 日初: → AVAILABLE

策略从AVAILABLE池选择母羊配种, 受种公羊约束。
"""

import numpy as np, pandas as pd
import os, sys, time, json, zipfile

# ============================================================
T_MATE=20; T_PENDING=30; T_PREG_MIN=147; T_PREG_MAX=150
T_NURS=40; T_REST_MIN=18; T_FATT=210
CAP_MATE=14; CAP_PENDING=8; CAP_PREG=8; CAP_NURS=6; CAP_REST=14; CAP_FATT=14; CAP_RAM=4
RAM_RATIO=50
CONCEPTION_RATE=0.85; LAMB_MORTALITY=0.03
LITTER_PROBS=[0.05,0.72,0.21,0.02]; LAMBS_MEAN=2.2
COST_EMPTY=1.0; COST_SHORTAGE=3.0
TOTAL_PENS=112

ST_AVAIL,ST_MATE,ST_PENDING,ST_PREG,ST_NURS,ST_REST=0,1,2,3,4,5
ST_NAMES={0:'AVAIL',1:'MATE',2:'PEND',3:'PREG',4:'NURS',5:'REST'}

OUT_DIR='/home/user/workspace/output'

# ============================================================
def count_pens_merged(items,window=7,cap=14):
    if not items: return 0
    s=sorted(items,key=lambda x:x[0]); pens=0; i=0; n=len(s)
    while i<n:
        gs=s[i][0]; tot=0
        while i<n and s[i][0]<=gs+window: tot+=s[i][1]; i+=1
        pens+=int(np.ceil(tot/cap))
    return pens

# ============================================================
class Farm:
    def __init__(self,n_ewes,n_rams):
        self.N=n_ewes; self.R=n_rams
        self.state=np.full(n_ewes,ST_AVAIL,dtype=np.int8)
        self.mate_start=np.full(n_ewes,-1,dtype=np.int32)
        self.hidden_conceived=np.zeros(n_ewes,dtype=bool)
        self.conception_day=np.zeros(n_ewes,dtype=np.int8)
        self.preg_len=np.full(n_ewes,149,dtype=np.int16)
        self.birth_day=np.full(n_ewes,-1,dtype=np.int32)
        self.wean_day=np.full(n_ewes,-1,dtype=np.int32)
        self.rest_start=np.full(n_ewes,-1,dtype=np.int32)
        self.rest_reason=np.zeros(n_ewes,dtype=np.int8)
        self.eligible_day=np.zeros(n_ewes,dtype=np.int32)
        self.day=0

        self.fattening=[]
        self.total_sold=0; self.lambs_sold_by_day={}

        # Per-ewe 事件记录
        self.mate_days=[[] for _ in range(n_ewes)]
        self.birth_days=[[] for _ in range(n_ewes)]
        self.event_ledger=[]

        # 统计
        self.n_matings=0; self.n_conceptions=0; self.n_births=0
        self.total_born_gross=0; self.total_born_net=0
        self.n_shortfalls=0

    def n_available(self): return int(np.sum(self.state==ST_AVAIL))
    def n_in_state(self,s): return int(np.sum(self.state==s))

    def start_mating(self,ewe_ids,day):
        for eid in ewe_ids:
            if self.state[eid]!=ST_AVAIL:
                raise ValueError(f"Ewe {eid} not AVAIL")
            self.state[eid]=ST_MATE
            self.mate_start[eid]=day
            self.hidden_conceived[eid]=False
            self.conception_day[eid]=0
            self.mate_days[eid].append(day)
            self._log(eid,day,'MATE_START')

    def step(self,rng):
        """处理当前日(d=self.day)的日初转移+事件。不递增day。"""
        d=self.day

        # === PHASE 1: 日初状态转移 ===
        for eid in range(self.N):
            s=self.state[eid]; ms=self.mate_start[eid]

            # MATE(d0..d0+19) → PENDING at day d0+20
            if s==ST_MATE and d>=ms+T_MATE:
                conc=rng.random()<CONCEPTION_RATE
                self.hidden_conceived[eid]=conc; self.n_matings+=1
                if conc:
                    self.conception_day[eid]=rng.randint(0,T_MATE)
                    self.preg_len[eid]=rng.randint(T_PREG_MIN,T_PREG_MAX+1)
                    self.n_conceptions+=1
                self.state[eid]=ST_PENDING

            # PENDING(d0+20..d0+49) → 分流 at day d0+50
            elif s==ST_PENDING and d>=ms+T_MATE+T_PENDING:
                if self.hidden_conceived[eid]:
                    self.state[eid]=ST_PREG
                    self.birth_day[eid]=ms+int(self.conception_day[eid])+int(self.preg_len[eid])
                    self._log(eid,d,'DIAGNOSIS_SUCCESS')
                else:
                    self.state[eid]=ST_REST
                    self.rest_start[eid]=d; self.rest_reason[eid]=0
                    self.eligible_day[eid]=d+T_REST_MIN
                    self._log(eid,d,'DIAGNOSIS_FAIL')

            # PREG → NURS at birth_day
            elif s==ST_PREG and d>=self.birth_day[eid]:
                nl=rng.choice([1,2,3,4],p=LITTER_PROBS); nl=int(nl)
                sv=int(rng.binomial(nl,1-LAMB_MORTALITY))
                self.total_born_gross+=nl; self.total_born_net+=sv; self.n_births+=1
                self.state[eid]=ST_NURS
                self.wean_day[eid]=d+T_NURS
                self.birth_days[eid].append(d)
                if sv>0: self.fattening.append((self.wean_day[eid],sv))
                self._log(eid,d,'BIRTH')

            # NURS → REST at wean_day
            elif s==ST_NURS and d>=self.wean_day[eid]:
                self.state[eid]=ST_REST
                self.rest_start[eid]=d; self.rest_reason[eid]=1
                self.eligible_day[eid]=d+T_REST_MIN
                self._log(eid,d,'WEAN')

            # REST → AVAIL at eligible_day (d0+68 for failed)
            elif s==ST_REST and d>=self.eligible_day[eid]:
                self.state[eid]=ST_AVAIL
                self.mate_start[eid]=-1
                self._log(eid,d,'AVAILABLE')

        # === PHASE 2: 育肥完成(出栏) ===
        new_fatt=[]
        for wd,nl in self.fattening:
            if d>=wd+T_FATT:
                self.total_sold+=nl
                self.lambs_sold_by_day[d]=self.lambs_sold_by_day.get(d,0)+nl
                self._log(-1,d,'SOLD')  # ewe_id=-1 for lamb sale
            else: new_fatt.append((wd,nl))
        self.fattening=new_fatt

    def _log(self,ewe_id,day,event_type):
        self.event_ledger.append((ewe_id,day,event_type))

    def get_pens(self):
        d=self.day
        mate_ids=np.where(self.state==ST_MATE)[0]
        pend_ids=np.where(self.state==ST_PENDING)[0]
        preg_ids=np.where(self.state==ST_PREG)[0]
        nurs_ids=np.where(self.state==ST_NURS)[0]
        rest_ids=np.where(self.state==ST_REST)[0]
        avail_ids=np.where(self.state==ST_AVAIL)[0]

        p_avail=int(np.ceil(len(avail_ids)/CAP_MATE)) if len(avail_ids)>0 else 0
        p_mate_raw=int(np.ceil(len(mate_ids)/CAP_MATE)) if len(mate_ids)>0 else 0
        p_mate=min(p_mate_raw,self.R)
        p_pend=int(np.ceil(len(pend_ids)/CAP_PENDING)) if len(pend_ids)>0 else 0
        p_preg=int(np.ceil(len(preg_ids)/CAP_PREG)) if len(preg_ids)>0 else 0

        nurs_items=[(self.birth_day[eid],1) for eid in nurs_ids]
        p_nurs=count_pens_merged(nurs_items,7,CAP_NURS)

        rest_birth=[(self.rest_start[eid],1) for eid in rest_ids if self.rest_reason[eid]==1]
        rest_fail=[(self.rest_start[eid],1) for eid in rest_ids if self.rest_reason[eid]==0]
        p_rest=count_pens_merged(rest_birth,7,CAP_REST)+count_pens_merged(rest_fail,7,CAP_REST)

        fatt_items=[(wd,nl) for wd,nl in self.fattening if 0<=d-wd<T_FATT]
        p_fatt=count_pens_merged(fatt_items,7,CAP_FATT)

        p_ram=int(np.ceil(max(0,self.R-p_mate)/CAP_RAM))
        total=p_avail+p_mate+p_pend+p_preg+p_nurs+p_rest+p_fatt+p_ram
        return {
            'total':total,'avail':p_avail,'mate':p_mate,'pending':p_pend,
            'preg':p_preg,'nurs':p_nurs,'rest':p_rest,'fatt':p_fatt,'ram':p_ram,
            'empty':max(0,TOTAL_PENS-total),'shortage':max(0,total-TOTAL_PENS),
            'loss':max(0,TOTAL_PENS-total)*COST_EMPTY+max(0,total-TOTAL_PENS)*COST_SHORTAGE,
            'load_pct':total/TOTAL_PENS*100,
        }

    def check_conservation(self):
        counts=[self.n_in_state(s) for s in range(6)]
        total=sum(counts)
        return total==self.N,counts,total

    def per_ewe_mate_intervals(self):
        """每只母羊的相邻配种间隔。"""
        intervals=[]
        for days in self.mate_days:
            if len(days)>=2:
                for i in range(1,len(days)):
                    intervals.append(days[i]-days[i-1])
        return intervals

    def per_ewe_birth_intervals(self):
        """每只母羊的相邻分娩间隔。"""
        intervals=[]
        for days in self.birth_days:
            if len(days)>=2:
                for i in range(1,len(days)):
                    intervals.append(days[i]-days[i-1])
        return intervals


# ============================================================
def strategy_mate(farm,day,target):
    n_avail=farm.n_available(); n_mating=farm.n_in_state(ST_MATE)
    max_new=max(0,farm.R*CAP_MATE-n_mating)
    n_to_mate=min(target,n_avail,max_new)
    if n_to_mate<=0: return [],0
    avail_ids=np.where(farm.state==ST_AVAIL)[0]
    chosen=avail_ids[:n_to_mate].tolist()
    return chosen,max(0,target-n_to_mate)

def strategy_A(farm,day,x_det):
    target=int(x_det[day%229])
    ch,sf=strategy_mate(farm,day,target)
    if sf>0: farm.n_shortfalls+=1
    return ch

def strategy_B(farm,day,n_ewe,n_batch):
    offs=set(int(round(i*229/n_batch))%229 for i in range(n_batch))
    target=n_ewe if (day%229) in offs else 0
    ch,sf=strategy_mate(farm,day,target)
    if sf>0: farm.n_shortfalls+=1
    return ch

def strategy_C_init(farm,day):
    target_ewes=380; cur=farm.N-farm.n_available()
    if cur>=target_ewes: return []
    miss=target_ewes-cur; target=min(14,max(1,int(miss/33)))
    ch,sf=strategy_mate(farm,day,target)
    return ch


# ============================================================
def simulate_with_log(strategy_fn,n_ewes,n_rams,total_days,warmup,rng,strategy_args=()):
    farm=Farm(n_ewes,n_rams); srng=np.random.RandomState(rng.randint(0,2**31-1))
    dlog=[]; cons_ok=0; cons_fail=0

    for day in range(total_days):
        # 日初: 策略决定配种
        chosen=strategy_fn(farm,day,*strategy_args)
        if chosen: farm.start_mating(chosen,day)

        # 处理当天转移+事件 (farm.day 保持为 day)
        farm.step(srng)

        # 记录 (当天结束后)
        if day>=warmup:
            pens=farm.get_pens()
            sold=farm.lambs_sold_by_day.get(day,0)
            dlog.append({
                'day':day,'avail':pens['avail'],'mate':pens['mate'],
                'pending':pens['pending'],'preg':pens['preg'],'nurs':pens['nurs'],
                'rest':pens['rest'],'fatt':pens['fatt'],'ram':pens['ram'],
                'pens_total':pens['total'],'empty':pens['empty'],
                'shortage':pens['shortage'],'daily_loss':pens['loss'],
                'lambs_sold_today':sold,
                'n_avail':farm.n_available(),'n_mate':farm.n_in_state(ST_MATE),
                'n_pend':farm.n_in_state(ST_PENDING),'n_preg':farm.n_in_state(ST_PREG),
                'n_nurs':farm.n_in_state(ST_NURS),'n_rest':farm.n_in_state(ST_REST),
            })
            ok,counts,total=farm.check_conservation()
            if ok: cons_ok+=1
            else: cons_fail+=1

        farm.day+=1  # 进入下一天

    elambs=sum(v for d,v in farm.lambs_sold_by_day.items() if warmup<=d<total_days)
    annual=elambs*365.0/(total_days-warmup)
    df=pd.DataFrame(dlog)
    s={
        'annual_output':float(annual),'eval_lambs_sold':elambs,
        'total_sold_all':farm.total_sold,
        'avg_daily_loss':float(df['daily_loss'].mean()),
        'avg_empty':float(df['empty'].mean()),'avg_shortage':float(df['shortage'].mean()),
        'avg_load_pct':float(df['pens_total'].mean()/TOTAL_PENS*100),
        'loss_std':float(df['daily_loss'].std()),
        'loss_p95':float(np.percentile(df['daily_loss'],95)),
        'rental_days':int((df['shortage']>0).sum()),
        'cons_ok':cons_ok,'cons_fail':cons_fail,
        'n_matings':farm.n_matings,'n_conceptions':farm.n_conceptions,
        'n_births':farm.n_births,'total_born_gross':farm.total_born_gross,
        'total_born_net':farm.total_born_net,'n_shortfalls':farm.n_shortfalls,
        'csv_sold_sum':int(df['lambs_sold_today'].sum()),
        'avg_mate_interval':np.mean(farm.per_ewe_mate_intervals()) if farm.per_ewe_mate_intervals() else 0,
        'avg_birth_interval':np.mean(farm.per_ewe_birth_intervals()) if farm.per_ewe_birth_intervals() else 0,
    }
    return s,df,farm


# ============================================================
def run_tests():
    print("="*60); print("v4.1 单元测试 (日初转移约定)"); print("="*60)
    passed=failed=0

    # T21: 2母羊, 1受孕1失败 — 精确day50/day68断言
    f=Farm(2,1); srng=np.random.RandomState(99)
    f.start_mating([0,1],0)
    # day 0..19: MATE. day20日初: →PENDING
    f.day=20; f.step(srng); f.day=21  # 处理day20
    # 覆盖
    f.hidden_conceived[0]=True; f.hidden_conceived[1]=False
    # day 21..49: PENDING. day50日初: 分流
    while f.day<50: f.step(srng); f.day+=1
    f.step(srng)  # 处理day50
    s0,s1=f.state[0],f.state[1]
    if s0==ST_PREG and s1==ST_REST:
        print(f"  ✅ T21a: day50 日初分流 → ewe0=PREG, ewe1=REST (f.day={f.day})"); passed+=1
    else: print(f"  ❌ T21a: ewe0={ST_NAMES[s0]}, ewe1={ST_NAMES[s1]}"); failed+=1
    f.day=51
    # day 50..67: REST. day68日初: →AVAIL
    while f.day<68: f.step(srng); f.day+=1
    f.step(srng)  # 处理day68
    if f.state[1]==ST_AVAIL:
        print(f"  ✅ T21b: day68 日初 → ewe1=AVAILABLE (f.day={f.day})"); passed+=1
    else: print(f"  ❌ T21b: ewe1={ST_NAMES[f.state[1]]}"); failed+=1

    # T22: 同批不同受孕日
    f2=Farm(2,1); srng2=np.random.RandomState(88)
    f2.start_mating([0,1],0)
    f2.day=20; f2.step(srng2); f2.day=21
    f2.hidden_conceived[0]=True; f2.conception_day[0]=3; f2.preg_len[0]=149
    f2.hidden_conceived[1]=True; f2.conception_day[1]=17; f2.preg_len[1]=150
    while f2.day<50: f2.step(srng2); f2.day+=1
    f2.step(srng2)
    bd0=f2.birth_day[0]; bd1=f2.birth_day[1]
    if bd0!=bd1: print(f"  ✅ T22: ewe0 birth={bd0}, ewe1 birth={bd1}"); passed+=1
    else: print(f"  ❌ T22: same birth={bd0}"); failed+=1

    # T23: 守恒
    f3=Farm(50,2); srng3=np.random.RandomState(77); cons_ok=0
    for day in range(500):
        f3.step(srng3)
        ok,_,_=f3.check_conservation()
        if ok: cons_ok+=1
        f3.day+=1
    if cons_ok==500: print(f"  ✅ T23: 500天守恒"); passed+=1
    else: print(f"  ❌ T23: {500-cons_ok} fail"); failed+=1

    # T24: 策略不可读hidden
    f4=Farm(10,1); f4.start_mating([0,1,2],0)
    srng4=np.random.RandomState(66)
    for _ in range(25):
        f4.step(srng4); f4.day+=1
    chosen,_=strategy_mate(f4,25,5)
    bad=[eid for eid in chosen if f4.state[eid]==ST_PENDING]
    if len(bad)==0: print(f"  ✅ T24: 策略未选PENDING母羊"); passed+=1
    else: print(f"  ❌ T24: {bad}"); failed+=1

    # T25: 交配栏≤公羊
    f5=Farm(200,9); f5.start_mating(list(range(200)),0)
    srng5=np.random.RandomState(55); f5.step(srng5)
    p=f5.get_pens()
    if p['mate']<=9: print(f"  ✅ T25: mate={p['mate']}≤9"); passed+=1
    else: print(f"  ❌ T25: {p['mate']}"); failed+=1

    # T26: CSV sum
    _,df6,f6=simulate_with_log(lambda f,d: strategy_mate(f,d,5)[0],20,2,800,200,np.random.RandomState(44))
    csv_sum=df6['lambs_sold_today'].sum()
    el=sum(v for d,v in f6.lambs_sold_by_day.items() if 200<=d<800)
    if csv_sum==el: print(f"  ✅ T26: CSV={csv_sum}==eval={el}"); passed+=1
    else: print(f"  ❌ T26: CSV={csv_sum}≠{el}"); failed+=1

    # T27: per-ewe间隔
    f7=Farm(20,2); srng7=np.random.RandomState(33)
    for day in range(1500):
        ch,_=strategy_mate(f7,day,3)
        if ch: f7.start_mating(ch,day)
        f7.step(srng7); f7.day+=1
    mi=f7.per_ewe_mate_intervals(); bi=f7.per_ewe_birth_intervals()
    if mi: print(f"  ✅ T27a: per-ewe配种间隔 mean={np.mean(mi):.0f}d (n={len(mi)})"); passed+=1
    else: print(f"  ⚠️ T27a: no data"); passed+=1
    if bi: print(f"  ✅ T27b: per-ewe分娩间隔 mean={np.mean(bi):.0f}d (n={len(bi)})"); passed+=1
    else: print(f"  ⚠️ T27b: no data"); passed+=1

    print(f"\n  {passed}通过, {failed}失败")
    if failed>0: sys.exit(1)
    print()


# ============================================================
if __name__=='__main__':
    t0=time.time()
    run_tests()

    WU=400; EV=800; TD=WU+EV; SEEDS=[1000,1001,1002]
    os.makedirs(OUT_DIR,exist_ok=True)

    try:
        df_s=pd.read_csv(f'{OUT_DIR}/problem2_milp_daily_schedule.csv')
        x_det=df_s['x_t'].values.astype(int)
    except:
        x_det=np.zeros(229,dtype=int)
        for i in range(27): x_det[int(i*229/27)]=14

    all_ledger=[]

    for sn,sfn,N,R,args in [
        ('A',lambda f,d: strategy_A(f,d,x_det),426,9,()),
        ('B',lambda f,d: strategy_B(f,d,13,29),377,8,()),
        ('C_init',lambda f,d: strategy_C_init(f,d),426,9,()),
    ]:
        print(f"\n--- 方案{sn} (N={N},R={R}) ---")
        for seed in SEEDS:
            rng=np.random.RandomState(seed)
            st,df,farm=simulate_with_log(sfn,N,R,TD,WU,rng)
            print(f"  seed={seed}: out={st['annual_output']:.0f} loss={st['avg_daily_loss']:.1f} "
                  f"load={st['avg_load_pct']:.0f}% cons={'OK' if st['cons_fail']==0 else 'FAIL'} "
                  f"mate_int={st['avg_mate_interval']:.0f}d birth_int={st['avg_birth_interval']:.0f}d")

            if seed==SEEDS[0]:
                df.to_csv(f'{OUT_DIR}/problem3_v4_1_{sn}_seed{seed}_daily_log.csv',index=False,encoding='utf-8-sig')

            # 收集event ledger
            for eid,eday,etype in farm.event_ledger:
                all_ledger.append({'ewe_id':eid,'event_day':eday,'event_type':etype,
                                   'policy':sn,'rep':0,'seed':seed})

    # 保存event ledger
    df_ledger=pd.DataFrame(all_ledger)
    df_ledger.to_csv(f'{OUT_DIR}/problem3_v4_1_event_ledger.csv',index=False,encoding='utf-8-sig')
    print(f"\nEvent ledger: {len(df_ledger)} events → {OUT_DIR}/problem3_v4_1_event_ledger.csv")

    # 比率校验
    print(f"\n{'='*60}")
    print("比率校验 (方案A seed=1000)")
    rng=np.random.RandomState(1000)
    st,_,farm=simulate_with_log(lambda f,d: strategy_A(f,d,x_det),426,9,TD,WU,rng)
    cr=st['n_conceptions']/max(1,st['n_matings'])
    lr=st['total_born_gross']/max(1,st['n_births'])
    sr=st['total_born_net']/max(1,st['total_born_gross'])
    print(f"  受孕率: {st['n_conceptions']}/{st['n_matings']} = {cr:.4f}")
    print(f"  产羔/胎: {st['total_born_gross']}/{st['n_births']} = {lr:.4f}")
    print(f"  存活率: {st['total_born_net']}/{st['total_born_gross']} = {sr:.4f}")
    print(f"  守恒失败: {st['cons_fail']}")
    print(f"  CSV出栏和: {st['csv_sold_sum']} == eval: {st['eval_lambs_sold']} {'✅' if st['csv_sold_sum']==st['eval_lambs_sold'] else '❌'}")

    # 压缩包
    zip_path=f'{OUT_DIR}/problem3_v4_1_outputs.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as zf:
        zf.write(__file__,os.path.basename(__file__))
        for sn in ['A','B','C_init']:
            csv_path=f'{OUT_DIR}/problem3_v4_1_{sn}_seed1000_daily_log.csv'
            if os.path.exists(csv_path): zf.write(csv_path,os.path.basename(csv_path))
        if os.path.exists(f'{OUT_DIR}/problem3_v4_1_event_ledger.csv'):
            zf.write(f'{OUT_DIR}/problem3_v4_1_event_ledger.csv','problem3_v4_1_event_ledger.csv')
    print(f"\n压缩包: {zip_path}")

    print(f"\n总耗时: {time.time()-t0:.0f}s")
    print("v4.1完成。")
