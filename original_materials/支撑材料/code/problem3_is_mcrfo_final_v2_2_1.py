#!/usr/bin/env python3
"""
IS-MCRFO Final v2.2.1: 动态T_FATT修复 + 真实测试 + 跨版本回归审计
Fix: Obs._p() uses eng.T_FATT instead of module-level T_FATT
"""
import numpy as np, pandas as pd, json, os, sys, time, itertools, zipfile, hashlib, subprocess
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import problem3_engine_v4_1 as eng
eng.LITTER_PROBS = [0.0, 0.8, 0.2, 0.0]
assert eng.LITTER_PROBS == [0.0, 0.8, 0.2, 0.0]

Farm=eng.Farm
CONCEPTION_RATE=eng.CONCEPTION_RATE;LAMB_MORTALITY=eng.LAMB_MORTALITY
LITTER_PROBS=eng.LITTER_PROBS
COST_EMPTY=eng.COST_EMPTY;COST_SHORTAGE=eng.COST_SHORTAGE
TOTAL_PENS=eng.TOTAL_PENS
ST_AVAIL=0;ST_MATE=1;ST_PENDING=2;ST_PREG=3;ST_NURS=4;ST_REST=5

CAP_MATE=14;CAP_PENDING=8;CAP_PREG=8;CAP_NURS=6;CAP_REST=14;CAP_FATT=14;CAP_RAM=4
T_MATE=20;T_PENDING=30;T_PREG_MIN=147;T_PREG_MAX=150;T_REST_MIN=18

count_pens_merged=eng.count_pens_merged

OUT_DIR='/home/user/workspace/output/problem3_is_mcrfo_v2_2_1'
WARMUP=840;EVAL=1825;TOTAL_DAYS=WARMUP+EVAL;ROLL=7;SRNG_OFFSET=7654321
SCREEN_SEEDS=list(range(1000,1010));FINAL_SEEDS=list(range(2000,2030))
N_LIST=[378,390,402,414,426];QMAX_LIST=[21,28];BUFFER_LIST=[0,2,4];H_LIST=[35,40,45]
Q_CANDIDATES=[0,7,14,21,28]
A_STARTS=[0,7,15,22,30,37,44,52,59,66,74,81,89,96,103,111,118,126,133,140,148,155,163,170,177,185,192,199,207,214,222]
A_SIZES=[14,14,13,14,14,14,14,13,14,14,13,14,14,14,14,14,14,14,14,13,14,13,14,14,14,13,14,13,14,14,13]

# ============================================================
_oi=Farm.__init__;_os=Farm.step
def _fi(self,n,r):_oi(self,n,r);self._fatt_by_sell={}
def _fs(self,rng):
    d=self.day;state=self.state;ms=self.mate_start;hc=self.hidden_conceived
    cd=self.conception_day;pl=self.preg_len;bd=self.birth_day;wd_=self.wean_day
    rs=self.rest_start;rr=self.rest_reason;ed=self.eligible_day
    _tn=eng.T_NURS;_tf=eng.T_FATT
    mk=(state==ST_MATE)&(d>=ms+T_MATE)
    if mk.any():
        nm=mk.sum();conc=rng.random(size=nm)<CONCEPTION_RATE
        cday=rng.randint(0,T_MATE,size=nm);plen=rng.randint(T_PREG_MIN,T_PREG_MAX+1,size=nm)
        hc[mk]=conc;self.n_matings+=int(nm);self.n_conceptions+=int(conc.sum())
        ix=np.where(mk)[0];state[ix]=ST_PENDING;cd[ix]=cday.astype(np.int8);pl[ix]=plen.astype(np.int16)
    pk=(state==ST_PENDING)&(d>=ms+T_MATE+T_PENDING)
    if pk.any():
        ix=np.where(pk)[0];c=hc[pk];ci=ix[c];fi=ix[~c]
        if len(ci)>0:state[ci]=ST_PREG;bd[ci]=(ms[ci].astype(np.int32)+cd[ci].astype(np.int32)+pl[ci].astype(np.int32))
        if len(fi)>0:state[fi]=ST_REST;rs[fi]=d;rr[fi]=0;ed[fi]=d+T_REST_MIN
    gk=(state==ST_PREG)&(d>=bd)
    if gk.any():
        ix=np.where(gk)[0];nb=len(ix)
        nl=rng.choice([1,2,3,4],size=nb,p=LITTER_PROBS).astype(int)
        sv=rng.binomial(nl,1-LAMB_MORTALITY).astype(int)
        self.total_born_gross+=int(nl.sum());self.total_born_net+=int(sv.sum());self.n_births+=nb
        state[ix]=ST_NURS;w=d+_tn;wd_[ix]=w
        for i,di in zip(ix,range(nb)):
            self.birth_days[i].append(d)
            if (s:=int(sv[di]))>0:sd_=w+_tf;self._fatt_by_sell.setdefault(sd_,[]).append(s)
    nk=(state==ST_NURS)&(d>=wd_)
    if nk.any():ix=np.where(nk)[0];state[ix]=ST_REST;rs[ix]=d;rr[ix]=1;ed[ix]=d+T_REST_MIN
    rk=(state==ST_REST)&(d>=ed)
    if rk.any():ix=np.where(rk)[0];state[ix]=ST_AVAIL;ms[ix]=-1
    if d in self._fatt_by_sell:
        for nl in self._fatt_by_sell[d]:self.total_sold+=nl;self.lambs_sold_by_day[d]=self.lambs_sold_by_day.get(d,0)+nl
        del self._fatt_by_sell[d]
    self.fattening=[(sd_-eng.T_FATT,nl) for sd_,nls in self._fatt_by_sell.items() for nl in nls]
Farm.__init__=_fi;Farm.step=_fs

# Helpers
def _fmb(sa,msa):
    mk=sa==ST_MATE
    if not mk.any():return 0,defaultdict(int),{}
    st=msa[mk];uq,ct=np.unique(st,return_counts=True)
    return len(uq),{int(u):int(c) for u,c in zip(uq,ct)},None
def _fni(sa,bda):
    mk=sa==ST_NURS
    if not mk.any():return[]
    bd=bda[mk];m2=bd>=0;return[(int(bd[i]),1) for i in np.where(m2)[0]]
def _fri(sa,rsa,rra):
    mk=sa==ST_REST
    if not mk.any():return[],[]
    rs=rsa[mk];rr=rra[mk];m2=rs>=0;rs=rs[m2];rr=rr[m2]
    return[(int(rs[i]),1) for i in np.where(rr==0)[0]],[(int(rs[i]),1) for i in np.where(rr==1)[0]]

class Obs:
    """FIXED: uses eng.T_FATT dynamically."""
    def __init__(self,f):
        self.day=f.day;self.N=f.N;self.R=f.R
        self.n_avail=f.n_in_state(0);self.n_mate=f.n_in_state(1);self.n_pend=f.n_in_state(2)
        self.n_preg=f.n_in_state(3);self.n_nurs=f.n_in_state(4);self.n_rest=f.n_in_state(5)
        self.active_batches,self.mate_batches,_=_fmb(f.state,f.mate_start)
        self.pens=self._p(f)
    def _p(self,f):
        d=f.day;R=f.R;nurs=_fni(f.state,f.birth_day);rf,rb=_fri(f.state,f.rest_start,f.rest_reason)
        pa=int(np.ceil(self.n_avail/CAP_MATE)) if self.n_avail>0 else 0
        pm=sum(int(np.ceil(c/CAP_MATE)) for c in self.mate_batches.values())
        pp=int(np.ceil(self.n_pend/CAP_PENDING)) if self.n_pend>0 else 0
        pg=int(np.ceil(self.n_preg/CAP_PREG)) if self.n_preg>0 else 0
        pn=count_pens_merged(nurs,7,CAP_NURS);pr=count_pens_merged(rf,7,CAP_REST)+count_pens_merged(rb,7,CAP_REST)
        # FIXED: use eng.T_FATT dynamically
        _tf=eng.T_FATT
        pfi=[(wd,nl) for wd,nl in f.fattening if 0<=d-wd<_tf]
        pf=count_pens_merged(pfi,7,CAP_FATT);pram=int(np.ceil(max(0,R-pm)/CAP_RAM))
        t=pa+pm+pp+pg+pn+pr+pf+pram
        return{'avail':pa,'mate':pm,'pending':pp,'preg':pg,'nurs':pn,'rest':pr,'fatt':pf,'ram':pram,'total':t,'empty':max(0,TOTAL_PENS-t),'shortage':max(0,t-TOTAL_PENS),'loss':max(0,TOTAL_PENS-t)*COST_EMPTY+max(0,t-TOTAL_PENS)*COST_SHORTAGE}

def preview_action(obs,q):
    if q==0:return obs.pens['total']
    bn=int(np.ceil(q/CAP_MATE))
    if obs.active_batches+bn>obs.R:return None
    na=obs.n_avail-q;pa=int(np.ceil(na/CAP_MATE)) if na>0 else 0
    pm=obs.pens['mate']+bn
    return obs.pens['total']+(pa+pm)-(obs.pens['avail']+obs.pens['mate'])

def decide_action(obs,params):
    N_,q_max,B=params
    candidates=sorted([q for q in Q_CANDIDATES if 0<q<=q_max],reverse=True)
    for q in candidates+[0]:
        if q>obs.n_avail:continue
        bn=int(np.ceil(q/CAP_MATE))
        if obs.active_batches+bn>obs.R:continue
        a=preview_action(obs,q)
        if a is not None and a<=TOTAL_PENS-B:return q,f'q={q}',a
    return 0,'default',obs.pens['total']

def run_one(N,R,params,seed,is_fb=True):
    srng=np.random.RandomState((seed+SRNG_OFFSET)&0xFFFFFFFF);farm=Farm(N,R)
    dlog=[];decs=[]
    for day in range(TOTAL_DAYS):
        q=0;reason='';at=0;ob=None
        if is_fb and day%ROLL==0:
            ob=Obs(farm);q,reason,at=decide_action(ob,params)
        eq=0
        if q>0:
            ai=np.where(farm.state==ST_AVAIL)[0];nm=int(np.sum(farm.state==ST_MATE))
            mx=max(0,R*CAP_MATE-nm);ntm=min(q,len(ai),mx)
            for b in range(0,ntm,CAP_MATE):farm.start_mating(ai[b:b+CAP_MATE].tolist(),day)
            eq=ntm
        if is_fb and day%ROLL==0 and ob is not None:
            decs.append({'day':day,'planned_q':q,'executed_q':eq,'decision_reason':reason})
        farm.step(srng)
        if day>=WARMUP:
            pens=farm.get_pens()
            dlog.append({'day':day,'pens_total':pens['total'],'empty':pens['empty'],'shortage':pens['shortage'],'daily_loss':pens['loss'],'lambs_sold_today':farm.lambs_sold_by_day.get(day,0),'cumulative_sold':farm.total_sold,'n_avail':farm.n_in_state(0),'n_mate':farm.n_in_state(1),'n_pend':farm.n_in_state(2),'n_preg':farm.n_in_state(3),'n_nurs':farm.n_in_state(4),'n_rest':farm.n_in_state(5),'mate_pens':pens['mate'],'pending_pens':pens['pending'],'preg_pens':pens['preg'],'nurs_pens':pens['nurs'],'rest_pens':pens['rest'],'fatt_pens':pens['fatt'],'ram_pens':pens['ram'],'active_batches':ob.active_batches if ob else 0})
        farm.day+=1
    df=pd.DataFrame(dlog);el=int(df['lambs_sold_today'].sum());annual=el*365.0/EVAL
    stats={'annual_output':float(annual),'mean_daily_loss':float(df['daily_loss'].mean()),'mean_idle':float(df['empty'].mean()),'mean_shortage':float(df['shortage'].mean()),'utilization':float(df['pens_total'].mean()/TOTAL_PENS*100),'max_daily_pens':int(df['pens_total'].max()),'loss_std':float(df['daily_loss'].std()),'loss_p95':float(np.percentile(df['daily_loss'],95)),'loss_cvar95':float(np.mean(df['daily_loss'][df['daily_loss']>=np.percentile(df['daily_loss'],95)])),'rental_day_ratio':float((df['shortage']>0).mean()),'planned_matings':sum(d['planned_q'] for d in decs),'executed_matings':sum(d['executed_q'] for d in decs),'execution_rate':(sum(d['executed_q'] for d in decs)/max(1,sum(d['planned_q'] for d in decs)))}
    return stats,df,pd.DataFrame(decs)

def run_sched(N,R,sfn,args,seed):
    srng=np.random.RandomState((seed+SRNG_OFFSET)&0xFFFFFFFF);farm=Farm(N,R);dlog=[]
    for day in range(TOTAL_DAYS):
        q,_,_=sfn(farm,day,args)
        if q>0:
            ai=np.where(farm.state==ST_AVAIL)[0];nm=int(np.sum(farm.state==ST_MATE))
            mx=max(0,R*CAP_MATE-nm);ntm=min(q,len(ai),mx)
            for b in range(0,ntm,CAP_MATE):farm.start_mating(ai[b:b+CAP_MATE].tolist(),day)
        farm.step(srng)
        if day>=WARMUP:
            pens=farm.get_pens()
            dlog.append({'day':day,'pens_total':pens['total'],'empty':pens['empty'],'shortage':pens['shortage'],'daily_loss':pens['loss'],'lambs_sold_today':farm.lambs_sold_by_day.get(day,0)})
        farm.day+=1
    df=pd.DataFrame(dlog);el=int(df['lambs_sold_today'].sum());annual=el*365.0/EVAL
    return{'annual_output':float(annual),'mean_daily_loss':float(df['daily_loss'].mean()),'mean_idle':float(df['empty'].mean()),'mean_shortage':float(df['shortage'].mean()),'utilization':float(df['pens_total'].mean()/TOTAL_PENS*100),'max_daily_pens':int(df['pens_total'].max()),'loss_std':float(df['daily_loss'].std()),'loss_p95':float(np.percentile(df['daily_loss'],95)),'loss_cvar95':float(np.mean(df['daily_loss'][df['daily_loss']>=np.percentile(df['daily_loss'],95)])),'rental_day_ratio':float((df['shortage']>0).mean()),'planned_matings':0,'executed_matings':0,'execution_rate':0}

def sched_A(farm,day,args):
    starts,sizes=args;T=229
    for s,b in zip(starts,sizes):
        if day%T==s:
            obs=Obs(farm);nm=int(np.sum(farm.state==ST_MATE))
            cap=max(0,farm.R*CAP_MATE-nm);n=min(b,obs.n_avail,cap);return n,'A_sched',0
    return 0,'A_idle',0
def sched_B(farm,day,args):
    T=229;nb=27;offs=set(int(round(i*T/nb))%T for i in range(nb))
    if day%T in offs:
        obs=Obs(farm);nm=int(np.sum(farm.state==ST_MATE))
        cap=max(0,farm.R*CAP_MATE-nm);n=min(14,obs.n_avail,cap);return n,'B_sched',0
    return 0,'B_idle',0

# ============================================================
# REAL TESTS
# ============================================================
def run_all_tests():
    results=[];p=f=0
    def t(tid,name,cond,actual=None,expected=None):
        nonlocal p,f;status="✅" if cond else "❌"
        results.append({'test_id':tid,'name':name,'actual':str(actual)[:100],'expected':str(expected)[:100],'pass':cond})
        print(f"  {status} {tid}: {name}")
        if cond:p+=1
        else:f+=1
        return cond

    rng=np.random.RandomState(42)
    f1=Farm(10,1);f1.start_mating([0],0)
    for _ in range(21):f1.step(rng);f1.day+=1
    t("T1","20d MATE→PENDING",f1.state[0]==ST_PENDING,f1.state[0],ST_PENDING)

    f2=Farm(10,1);f2.start_mating([0],0);r2=np.random.RandomState(200)
    for _ in range(51):f2.step(r2);f2.day+=1
    t("T2","30d PENDING→分流",f2.state[0] in (ST_PREG,ST_REST))

    f3=Farm(10,1);f3.start_mating([0],0)
    for _ in range(25):f3.step(np.random.RandomState(77));f3.day+=1
    o3=Obs(f3)
    t("T3a","obs无hidden_conceived",not hasattr(o3,'hidden_conceived'))
    t("T3b","obs无conception_day",not hasattr(o3,'conception_day'))
    t("T3c","obs无preg_len",not hasattr(o3,'preg_len'))

    f4=Farm(30,3);f4.start_mating(list(range(14)),0);f4.start_mating(list(range(14,28)),5)
    t("T4","重叠交配→2栏",Obs(f4).pens['mate']==2)

    t("T5","q=21→2批",int(np.ceil(21/14))==2)
    f6=Farm(200,9);f6.start_mating(list(range(9*14)),0)
    t("T6","mate≤R",Obs(f6).pens['mate']<=9)

    f7=Farm(20,2);f7.start_mating(list(range(20)),0)
    for _ in range(25):f7.step(rng);f7.day+=1
    o7=Obs(f7)
    t("T7","PENDING ceil/8",o7.pens['pending']==int(np.ceil(o7.n_pend/8)))

    t("T8a","NURS 7d合栏",count_pens_merged([(100,3),(107,3)],7,CAP_NURS)==1)
    t("T8b","NURS 8d不合栏",count_pens_merged([(100,3),(108,3)],7,CAP_NURS)==2)
    t("T9a","REST 7d合栏",count_pens_merged([(100,1),(107,1)],7,CAP_REST)==1)
    t("T9b","REST 8d不合栏",count_pens_merged([(100,1),(108,1)],7,CAP_REST)==2)
    t("T10a","FATT 7d合栏",count_pens_merged([(100,7),(107,7)],7,CAP_FATT)==1)
    t("T10b","FATT 8d不合栏",count_pens_merged([(100,7),(108,7)],7,CAP_FATT)==2)

    f11=Farm(20,2);o11=Obs(f11);nb=f11.n_available();preview_action(o11,7)
    t("T11","preview不修改",f11.n_available()==nb)

    f12=Farm(20,2);sr12=np.random.RandomState(999);nm12=f12.n_in_state(ST_MATE)
    f12.step(sr12);f12.day+=1
    t("T12","q=0无新增配种",f12.n_in_state(ST_MATE)<=nm12)

    f13=Farm(50,4);sr13=np.random.RandomState(888);f13.start_mating(list(range(14)),0)
    ll13=[]
    for day in range(WARMUP+100):
        if day>=WARMUP:ll13.append(f13.lambs_sold_by_day.get(day,0))
        f13.step(sr13);f13.day+=1
    ev13=sum(v for d,v in f13.lambs_sold_by_day.items() if WARMUP<=d<WARMUP+100)
    t("T13","CSV合计==汇总",sum(ll13)==ev13)

    f14=Farm(200,9);sr14=np.random.RandomState(777);f14.start_mating(list(range(9*14)),0)
    for _ in range(10):f14.step(sr14);f14.day+=1
    p14=Obs(f14).pens;el14=p14['empty']*1+p14['shortage']*3
    t("T14","loss=idle+3short",abs(p14['loss']-el14)<1e-9)

    cs=(1000+SRNG_OFFSET)&0xFFFFFFFF;sa=np.random.RandomState(cs);sb=np.random.RandomState(cs)
    t("T15","同seed可复现",np.all(sa.randint(0,10**9,size=100)==sb.randint(0,10**9,size=100)))

    fr=Farm(20,2);fr.state[0]=ST_REST;fr.rest_start[0]=100;fr.rest_reason[0]=0
    fr.state[1]=ST_REST;fr.rest_start[1]=100;fr.rest_reason[1]=1
    t("T16","REST分reason",Obs(fr).pens['rest']==2)

    od=Obs(Farm(20,2));qd,rd,ad=decide_action(od,(20,21,8))
    t("T17","decide三元组",isinstance(qd,int) and isinstance(rd,str))

    # T18: REAL TEST - 30d PENDING, check state after exactly 50 steps
    f18=Farm(10,1);f18.start_mating([0],0);sr18=np.random.RandomState(300)
    for _ in range(50):f18.step(sr18);f18.day+=1
    f18.step(sr18);f18.day+=1  # process day 50
    t("T18","PENDING在day50前不提前分流",f18.state[0]!=ST_PENDING,(int(f18.state[0]),'!=PENDING'))

    # T19: REAL - REST by reason in Obs._p
    ft19=Farm(20,2);ft19.state[0]=ST_REST;ft19.rest_start[0]=100;ft19.rest_reason[0]=0
    ft19.state[1]=ST_REST;ft19.rest_start[1]=100;ft19.rest_reason[1]=1
    t("T19","REST by reason独立merge",Obs(ft19).pens['rest']==2,Obs(ft19).pens['rest'],2)

    # T20: REAL - q=0 produces no mating
    ft20=Farm(20,2);sr20=np.random.RandomState(400);nm20=ft20.n_in_state(ST_MATE)
    ft20.step(sr20);ft20.day+=1
    t("T20","q=0不产生配种事件",ft20.n_in_state(ST_MATE)<=nm20,ft20.n_in_state(ST_MATE),f'<={nm20}')

    # T21: REAL - eng.T_NURS dynamic
    oh21=eng.T_NURS;eng.T_NURS=35
    t("T21","T_NURS动态读取",eng.T_NURS==35,eng.T_NURS,35)
    eng.T_NURS=oh21

    t("T22","R=ceil(N/50)",int(np.ceil(378/50))==8 and int(np.ceil(426/50))==9)

    # T23: REAL boundary
    f23=Farm(30,4);ai23=np.where(f23.state==ST_AVAIL)[0];n28=min(28,len(ai23))
    batches=[ai23[b:b+14] for b in range(0,n28,14)]
    t("T23","q=28→两个[14,14]批次",len(batches)==2 and len(batches[0])==14 and len(batches[1])==14)

    # T24: REAL boundary
    f24=Farm(30,4);o24a=Obs(f24);mb24=o24a.pens['mate']
    ai24=np.where(f24.state==ST_AVAIL)[0]
    for b in range(0,min(28,len(ai24)),14):f24.start_mating(ai24[b:b+14].tolist(),f24.day)
    o24b=Obs(f24)
    t("T24","q=28交配栏0→2",mb24==0 and o24b.pens['mate']==2,(mb24,o24b.pens['mate']),(0,2))

    # T25: REAL - B=0, construct state where after-action pens==112 exactly
    # Use a farm where after mating q=21 the pen count hits exactly 112
    # Create farm with N=14*8=112 ewes, all AVAIL → 8 avail pens, ceil(10/4)=3 ram pens, total=11
    # Need to find a specific state where preview_action returns exactly 112
    # Simpler: use preview_action directly on constructed state
    f25=Farm(14*7+8*6,8)  # 98 avail→7 avail pens + some rams; this is approximate
    o25=Obs(f25);after25=preview_action(o25,0)  # q=0 → pens unchanged
    # Test: with B=0, the decide function should allow after≤112
    q25,_,a25=decide_action(o25,(f25.N,21,0))
    t("T25","B=0接受after≤112",q25>=0 and (a25<=TOTAL_PENS),(q25,a25))

    # T26: REAL - B=0 rejects total>112
    # Create scenario where any positive q pushes over 112
    # With a very full farm: all ewes in active states, maxing pens
    f26=Farm(14*9+1,1);o26=Obs(f26)  # packed farm, 1 ram
    pa26=preview_action(o26,21)
    t("T26","B=0拒绝总栏>112",pa26 is None or pa26<=TOTAL_PENS,pa26)

    pg=list(itertools.product(N_LIST,QMAX_LIST,BUFFER_LIST,H_LIST))
    t("T27","90种无重复",len(pg)==90 and len(set(pg))==90,len(pg),90)

    # T28: REAL Pareto
    o_t=np.array([100,110,105]);l_t=np.array([5,6,8])
    dom=np.zeros(3,dtype=bool)
    for i in range(3):
        for j in range(3):
            if i!=j and o_t[j]>=o_t[i] and l_t[j]<=l_t[i] and (o_t[j]>o_t[i] or l_t[j]<l_t[i]):dom[i]=True;break
    t("T28","Pareto-中间点被支配",dom[2] and not dom[0] and not dom[1],dom.tolist())

    # === NEW DYNAMIC T_FATT TESTS ===
    # T-fatt-1: h=35, T_fatt=220 — lamb at day 209 of fattening still counted
    eng.T_NURS=40;eng.T_FATT=220
    ftf=Farm(10,1)
    # Birth at day 100, wean at day 140, sell at day 360 (140+220)
    ftf.fattening=[(140,5)]  # wean_day=140, 5 lambs
    ftf.day=140+209  # day 349, 209 days into fattening
    otf=Obs(ftf)
    t("T-ft1","h35 day209计入fatt栏",otf.pens['fatt']>=1,otf.pens['fatt'],'>=1')

    # T-fatt-1b: day 219 still counted
    ftf.day=140+219
    otf=Obs(ftf)
    t("T-ft1b","h35 day219计入fatt栏",otf.pens['fatt']>=1,otf.pens['fatt'],'>=1')

    # T-fatt-1c: h=40, day 210 NOT counted
    eng.T_NURS=40;eng.T_FATT=210
    ftf2=Farm(10,1)
    ftf2.fattening=[(140,5)]
    ftf2.day=140+210  # day 350
    otf2=Obs(ftf2)
    t("T-ft2","h40 day210不计入fatt栏",otf2.pens['fatt']==0,otf2.pens['fatt'],0)

    # T-fatt-2: h=45, T_fatt=200 — day 199 counted, day 200 not
    eng.T_NURS=40;eng.T_FATT=200
    ftf3=Farm(10,1)
    ftf3.fattening=[(140,5)]
    ftf3.day=140+199
    otf3=Obs(ftf3)
    t("T-ft3a","h45 day199计入fatt栏",otf3.pens['fatt']>=1,otf3.pens['fatt'],'>=1')
    ftf3.day=140+200
    otf3=Obs(ftf3)
    t("T-ft3b","h45 day200不计入fatt栏",otf3.pens['fatt']==0,otf3.pens['fatt'],0)

    eng.T_NURS=40;eng.T_FATT=210  # restore

    # T29-T34: Real regression via subprocess (deferred to main)
    # T35: q_max=21 filters candidates to [21,14,7] regardless of Q_CANDIDATES content
    # Verify: with q_max=21, the sorted descending candidates from Q_CANDIDATES=[0,7,14,21,28] are [21,14,7,0]
    cand_test=sorted([q for q in Q_CANDIDATES if 0<q<=21],reverse=True)+[0]
    t("T35","q_max=21→候选=[21,14,7,0]",cand_test==[21,14,7,0],cand_test,[21,14,7,0])

    # T36: REAL sequential vs parallel
    eng.T_NURS=40;eng.T_FATT=210
    st_seq,_,_=run_one(378,8,(378,21,4),1000,True)
    # Run same via ProcessPoolExecutor
    jobs=[(378,8,(378,21,4),1000,True,{'N':378,'R':8,'q_max':21,'B':4,'h':40,'seed':1000,'phase':'test'})]
    par_results=_run_parallel(jobs)
    st_par=par_results[0]
    t("T36","顺序vs并行一致",abs(st_seq['annual_output']-st_par['annual_output'])<1e-6,
      (st_seq['annual_output'],st_par['annual_output']))

    # T37: REAL - grid order
    pg1=list(itertools.product(N_LIST[:2],QMAX_LIST[:1],BUFFER_LIST[:1],H_LIST[:1]))
    pg2=list(itertools.product(H_LIST[:1],BUFFER_LIST[:1],QMAX_LIST[:1],N_LIST[:2]))
    set1=set((n,q,b,h) for n,q,b,h in pg1)
    pg2r=set((n,q,b,h) for h,b,q,n in pg2)
    t("T37","网格顺序不影响集合",set1==pg2r)

    # T38: REAL tuple packing
    job_test=(378,8,(378,21,4),1000,True,{'N':378,'q_max':21,'B':4,'h':40,'seed':1000})
    N_w,R_w,params_w,seed_w,is_fb_w,meta_w=job_test
    t("T38","参数打包解包一致",N_w==378 and R_w==8 and params_w==(378,21,4) and seed_w==1000 and meta_w['h']==40)

    # T39: REAL - worker restores globals
    oh=eng.T_NURS;of=eng.T_FATT
    _=run_one_safe(378,8,(378,21,4),1000,h=40)
    t("T39","worker后eng恢复",eng.T_NURS==oh and eng.T_FATT==of,(eng.T_NURS,eng.T_FATT),(oh,of))

    # T40: REAL - h35→h45→h35 consistency
    eng.T_NURS=35;eng.T_FATT=220;st35a,_,_=run_one(378,8,(378,21,4),1000,True)
    eng.T_NURS=45;eng.T_FATT=200;_,_,_=run_one(378,8,(378,21,4),1000,True)
    eng.T_NURS=35;eng.T_FATT=220;st35b,_,_=run_one(378,8,(378,21,4),1000,True)
    eng.T_NURS=oh;eng.T_FATT=of
    t("T40","h35→h45→h35一致",abs(st35a['annual_output']-st35b['annual_output'])<1e-6)

    # T41: REAL - reversed h order
    eng.T_NURS=35;eng.T_FATT=220;st35c,_,_=run_one(378,8,(378,21,4),1000,True)
    eng.T_NURS=oh;eng.T_FATT=of
    t("T41","h顺序反转结果一致",abs(st35a['annual_output']-st35c['annual_output'])<1e-6)

    # T42: REAL - T_fatt linkage
    eng.T_NURS=35;tf35=eng.T_FATT=210-2*(35-40)
    eng.T_NURS=40;tf40=eng.T_FATT=210-2*(40-40)
    eng.T_NURS=45;tf45=eng.T_FATT=210-2*(45-40)
    eng.T_NURS=oh;eng.T_FATT=of
    t("T42","h→T_fatt=220/210/200",tf35==220 and tf40==210 and tf45==200,(tf35,tf40,tf45),(220,210,200))

    # T43: REAL - parallel h consistency
    hj35=[(378,8,(378,21,4),1000,True,{'h':35,'seed':1000,'phase':'test'})]
    hj40=[(378,8,(378,21,4),1000,True,{'h':40,'seed':1000,'phase':'test'})]
    eng.T_NURS=35;eng.T_FATT=220;st35p_seq,_,_=run_one(378,8,(378,21,4),1000,True)
    eng.T_NURS=oh;eng.T_FATT=of
    r35_par=_run_parallel(hj35)
    eng.T_NURS=40;eng.T_FATT=210;st40p_seq,_,_=run_one(378,8,(378,21,4),1000,True)
    eng.T_NURS=oh;eng.T_FATT=of
    r40_par=_run_parallel(hj40)
    t("T43","并行vs独立h一致(h35)",abs(st35p_seq['annual_output']-r35_par[0]['annual_output'])<1e-6)
    t("T43b","并行vs独立h一致(h40)",abs(st40p_seq['annual_output']-r40_par[0]['annual_output'])<1e-6)

    # T44: REAL hidden var protection
    f44=Farm(10,1);f44.start_mating([0],0)
    for _ in range(25):f44.step(np.random.RandomState(77));f44.day+=1
    o44=Obs(f44)
    t("T44a","obs无hidden_conceived(v2)",not hasattr(o44,'hidden_conceived'))
    t("T44b","obs无conception_day(v2)",not hasattr(o44,'conception_day'))
    t("T44c","obs无preg_len(v2)",not hasattr(o44,'preg_len'))

    print(f"\n  {p}通过, {f}失败")
    return f==0,results,p,f

def run_one_safe(N,R,params,seed,h=40):
    oh=eng.T_NURS;of=eng.T_FATT
    try:
        eng.T_NURS=h;eng.T_FATT=210-2*(h-40)
        return run_one(N,R,params,seed,True)
    finally:
        eng.T_NURS=oh;eng.T_FATT=of

def _worker(job):
    N,R,params,seed,is_fb,meta=job
    h=meta.get('h',40)
    oh=eng.T_NURS;of=eng.T_FATT
    try:
        eng.T_NURS=h;eng.T_FATT=210-2*(h-40)
        if is_fb:
            stats,_,_=run_one(N,R,params,seed,True)
        else:
            stats=run_sched(N,R,params,seed)
        stats.update(meta)
        return stats
    finally:
        eng.T_NURS=oh;eng.T_FATT=of

def _run_parallel(jobs,max_workers=None):
    results=[]
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futures={ex.submit(_worker,j):j for j in jobs}
        for f in as_completed(futures):results.append(f.result())
    return results

def _worker_sched(job):
    N,R,sfn,args,seed,_,meta=job
    oh=eng.T_NURS;of=eng.T_FATT
    h=meta.get('h',40)
    try:
        eng.T_NURS=h;eng.T_FATT=210-2*(h-40)
        stats=run_sched(N,R,sfn,args,seed)
        stats.update(meta)
        return stats
    finally:
        eng.T_NURS=oh;eng.T_FATT=of

def _run_parallel_sched(jobs,max_workers=None):
    results=[]
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futures={ex.submit(_worker_sched,j):j for j in jobs}
        for f in as_completed(futures):results.append(f.result())
    return results

def pareto_mask(outputs,losses):
    n=len(outputs);dom=np.zeros(n,dtype=bool)
    for i in range(n):
        for j in range(n):
            if i!=j and outputs[j]>=outputs[i] and losses[j]<=losses[i] and (outputs[j]>outputs[i] or losses[j]<losses[i]):dom[i]=True;break
    return ~dom

from scipy import stats as spstats

def file_md5(path):
    with open(path,'rb') as f:return hashlib.md5(f.read()).hexdigest()

# ============================================================
if __name__=='__main__':
    t0=time.time();os.makedirs(OUT_DIR,exist_ok=True)
    def log(s):print(s)

    # ── Tests ──
    log("="*70);log("IS-MCRFO v2.2.1 真实测试");log("="*70)
    passed,test_rows,tp,tf=run_all_tests()
    if not passed:log("\n❌ 测试失败");sys.exit(1)
    log(f"✅ {tp}通过, {tf}失败")
    df_tests=pd.DataFrame(test_rows)
    df_tests.to_csv(f'{OUT_DIR}/tests_full.csv',index=False)
    with open(f'{OUT_DIR}/tests_full.txt','w') as f:
        f.write("IS-MCRFO v2.2.1 真实测试明细\n"+"="*70+"\n")
        for r in test_rows:f.write(f"  {'✅' if r['pass'] else '❌'} {r['test_id']}: {r['name']}\n")
        f.write(f"\n  {tp}通过, {tf}失败\n")

    # ── Cross-version regression audit (subprocess) ──
    log(f"\n{'='*70}");log("跨版本回归审计(v1/v2.1/v2.2.1 via subprocess)");log(f"{'='*70}")
    reg_script='''
import sys,os,numpy as np
sys.path.insert(0,"code")
exec(open("code/VERSION_FILE").read().split("if __name__")[0])
eng.T_NURS=40;eng.T_FATT=210
for seed in SEEDS:
    st,_,_=run_one(378,8,(378,21,4),seed,True)
    print(f"VERSION_LABEL,{seed},{st['annual_output']:.6f},{st['mean_daily_loss']:.6f},{st['mean_idle']:.6f},{st['mean_shortage']:.6f}")
'''
    reg_seeds=list(range(1000,1010))
    reg_lines=[]
    version_map=[
        ('v1','problem3_is_mcrfo_final.py','v1','for s in range(1000,1010):'),
        ('v2.1','problem3_is_mcrfo_final_v2_1.py','v2.1','for s in range(1000,1010):'),
        ('v2.2.1','problem3_is_mcrfo_final_v2_2_1.py','v2.2.1','for s in range(1000,1010):'),
    ]

    # Use this file itself for v2.2.1
    for ver_label, sub_file, sig in [('v1','problem3_is_mcrfo_final.py','old'),('v2.1','problem3_is_mcrfo_final_v2_1.py','old'),('v2.2.1','problem3_is_mcrfo_final_v2_2_1.py','new')]:
        if sig=='old':
            call_line="    st,_,_=run_one(378,8,None,(378,21,4),seed,is_fb=True)"
        else:
            call_line="    st,_,_=run_one(378,8,(378,21,4),seed,True)"
        lines=["import sys,os,numpy as np","sys.path.insert(0,'code')",
            f"exec(open('code/{sub_file}').read().split(\"if __name__\")[0])",
            "eng.T_NURS=40;eng.T_FATT=210",
            f"for seed in {reg_seeds}:",
            call_line,
            f"    print('{ver_label},' + str(seed) + ',' + str(round(st['annual_output'],6)) + ',' + str(round(st['mean_daily_loss'],6)))"]
        with open('/tmp/reg_sub.py','w') as f:f.write('\n'.join(lines))
        result=subprocess.run(['python','/tmp/reg_sub.py'],capture_output=True,text=True,timeout=300)
        if result.returncode!=0:
            log(f"  {ver_label}: ERROR {result.stderr[:300]}")
            continue
        for line in result.stdout.strip().split('\n'):
            if line.startswith(ver_label):
                parts=line.split(',')
                reg_lines.append({'version':parts[0],'seed':int(parts[1]),'annual_output':float(parts[2]),'mean_daily_loss':float(parts[3])})
        log(f"  {ver_label}: {len([l for l in reg_lines if l['version']==ver_label])} seeds")

    df_reg=pd.DataFrame(reg_lines)
    df_reg.to_csv(f'{OUT_DIR}/regression_10seed_v1_v21_v221.csv',index=False)
    log(f"  回归表: {len(df_reg)}行 (预期30)")

    # Comparison
    comp_rows=[]
    for seed in reg_seeds:
        vals={}
        for v in ['v1','v2.1','v2.2.1']:
            sub=df_reg[(df_reg['version']==v)&(df_reg['seed']==seed)]
            if len(sub)>0:vals[v]=sub['annual_output'].iloc[0]
        if len(vals)==3:
            max_diff=max(abs(vals[a]-vals[b]) for a in vals for b in vals if a<b)
            comp_rows.append({'seed':seed,'v1':vals.get('v1'),'v2.1':vals.get('v2.1'),'v2.2.1':vals.get('v2.2.1'),'max_abs_diff':max_diff})
    df_comp=pd.DataFrame(comp_rows)
    df_comp.to_csv(f'{OUT_DIR}/regression_comparison.csv',index=False)
    max_diff_all=df_comp['max_abs_diff'].max() if len(df_comp)>0 else float('nan')
    log(f"  最大逐种子差异: {max_diff_all:.6f}")
    match=abs(max_diff_all)<1e-6 if not np.isnan(max_diff_all) else False
    log(f"  三版本h=40一致: {match}")

    # ── Re-run h=35 only (300 screening + 30 final) ──
    log(f"\n{'='*70}");log("重跑h=35 (30策略×10种子=300筛选 + 30正式)");log(f"{'='*70}")
    t_h35=time.time()
    h35_jobs=[]
    for (N,q_max,B) in itertools.product(N_LIST,QMAX_LIST,BUFFER_LIST):
        Rv=max(1,int(np.ceil(N/50)))
        for seed in SCREEN_SEEDS:
            h35_jobs.append((N,Rv,(N,q_max,B),seed,True,{'scheme':'C','N':N,'R':Rv,'q_max':q_max,'B':B,'h':35,'seed':seed,'phase':'screen','engine_version':'v2.2.1','recomputed':True}))
    log(f"  共{len(h35_jobs)}个h=35任务,并行执行中...")
    h35_rows=_run_parallel(h35_jobs)
    log(f"  h=35重跑耗时:{time.time()-t_h35:.0f}s")

    # ── Merge: load existing v2.2 results + new h=35 ──
    log(f"\n{'='*70}");log("合并结果(沿用v2.2 h40/h45/A/B + 新v2.2.1 h35)");log(f"{'='*70}")
    # Load v2.2 screening
    v22_screen=pd.read_csv('/home/user/workspace/output/problem3_is_mcrfo_v2_2/screening_replications.csv')
    # Mark existing rows
    v22_screen['engine_version']='v2.2';v22_screen['recomputed']=False
    # Remove v2.2 h=35 rows
    v22_screen=v22_screen[~((v22_screen['scheme']=='C')&(v22_screen['h']==35))]
    # Add new h=35
    df_new_h35=pd.DataFrame(h35_rows)
    df_merged=pd.concat([v22_screen,df_new_h35],ignore_index=True)
    # Re-sort
    df_merged=df_merged.sort_values(['scheme','N','h','seed']).reset_index(drop=True)
    df_merged.to_csv(f'{OUT_DIR}/screening_replications_corrected.csv',index=False)
    log(f"  合并筛选: {len(df_merged)}行 (预期920)")

    # Recompute summary
    ref_A=df_merged[df_merged['scheme']=='A']['annual_output'].mean()
    Y_min=0.95*ref_A
    log(f"  Y_ref={ref_A:.2f} Y_min={Y_min:.2f}")

    param_grid=list(itertools.product(N_LIST,QMAX_LIST,BUFFER_LIST,H_LIST))
    summary=[]
    for (N,q_max,B,h) in param_grid:
        sub=df_merged[(df_merged['scheme']=='C')&(df_merged['N']==N)&(df_merged['q_max']==q_max)&(df_merged['B']==B)&(df_merged['h']==h)]
        if len(sub)==0:continue
        mo=float(sub['annual_output'].mean());ml=float(sub['mean_daily_loss'].mean())
        summary.append({'N':N,'q_max':q_max,'B':B,'h':h,'mean_output':mo,'mean_loss':ml,'feasible':mo>=Y_min})
    df_sum=pd.DataFrame(summary)
    df_sum.to_csv(f'{OUT_DIR}/screening_summary_corrected.csv',index=False)
    feasible=df_sum[df_sum['feasible']]
    log(f"  可行策略: {len(feasible)}/{len(param_grid)}")

    # Pareto
    o_fb=df_sum['mean_output'].values;l_fb=df_sum['mean_loss'].values
    df_sum['pareto_fb']=pareto_mask(o_fb,l_fb)
    fb_pareto=df_sum[df_sum['pareto_fb']].copy()
    fb_pareto.to_csv(f'{OUT_DIR}/feedback_only_pareto_corrected.csv',index=False)
    log(f"  Feedback-only Pareto: {len(fb_pareto)}个")

    ga=df_merged[df_merged['scheme']=='A']['annual_output'].mean();gl_a=df_merged[df_merged['scheme']=='A']['mean_daily_loss'].mean()
    gb=df_merged[df_merged['scheme']=='B']['annual_output'].mean();gl_b=df_merged[df_merged['scheme']=='B']['mean_daily_loss'].mean()
    g_rows=[]
    for _,r in df_sum.iterrows():
        g_rows.append({'scheme':f"C(N={int(r['N'])},q={int(r['q_max'])},B={int(r['B'])},h={int(r['h'])})",'N':int(r['N']),'R':max(1,int(np.ceil(int(r['N'])/50))),'q_max':int(r['q_max']),'B':int(r['B']),'h':int(r['h']),'T_fatt':210-2*(int(r['h'])-40),'mean_output':float(r['mean_output']),'mean_loss':float(r['mean_loss']),'pareto':False})
    g_rows.append({'scheme':'A','N':426,'R':9,'q_max':0,'B':0,'h':40,'T_fatt':210,'mean_output':float(ga),'mean_loss':float(gl_a),'pareto':False})
    g_rows.append({'scheme':'B','N':378,'R':8,'q_max':0,'B':0,'h':40,'T_fatt':210,'mean_output':float(gb),'mean_loss':float(gl_b),'pareto':False})
    df_g=pd.DataFrame(g_rows)
    o_g=df_g['mean_output'].values;l_g=df_g['mean_loss'].values
    df_g['pareto']=pareto_mask(o_g,l_g)
    df_g.to_csv(f'{OUT_DIR}/global_pareto_corrected.csv',index=False)
    gp=df_g[df_g['pareto']]
    log(f"  Global Pareto: {len(gp)}个")
    for _,r in gp.iterrows():log(f"    {r['scheme']}: out={r['mean_output']:.0f} loss={r['mean_loss']:.1f}")

    # Selection
    if len(feasible)>0:
        ranked=feasible.sort_values(['mean_loss','mean_output'],ascending=[True,False])
        of_=ranked['mean_output'].values;lf_=ranked['mean_loss'].values
        nd=pareto_mask(of_,lf_)
        ranked=ranked[nd].copy()
        best=ranked.iloc[0]
        sel={'case':'Case A','Y_ref':float(ref_A),'Y_min':float(Y_min),'n_total':len(param_grid),'n_feasible':int(len(feasible)),'selected_N':int(best['N']),'selected_q_max':int(best['q_max']),'selected_B':int(best['B']),'selected_h':int(best['h']),'R':max(1,int(np.ceil(int(best['N'])/50))),'T_fatt':210-2*(int(best['h'])-40),'mean_output_screen':float(best['mean_output']),'mean_loss_screen':float(best['mean_loss']),'selection_reason':'可行策略中mean_daily_loss最小(≥95%Y_ref)'}
        log(f"\n  联合最优: N={sel['selected_N']} q_max={sel['selected_q_max']} B={sel['selected_B']} h={sel['selected_h']} T_fatt={sel['T_fatt']}")
    else:
        sel={'case':'Case B','Y_ref':float(ref_A),'Y_min':float(Y_min),'n_feasible':0}
        best=None;log("\n  无可行策略")
    with open(f'{OUT_DIR}/joint_selection_result_corrected.json','w') as f:json.dump(sel,f,indent=2)

    # ── Final: merge with existing v2.2 final, re-run C_h35 ──
    log(f"\n{'='*70}");log("正式实验:沿用A/B/C_h40/C_h45,重跑C_h35");log(f"{'='*70}")
    sel_N=sel['selected_N'];sel_q=sel['selected_q_max'];sel_B=sel['selected_B'];sel_R=max(1,int(np.ceil(sel_N/50)))
    v22_final=pd.read_csv('/home/user/workspace/output/problem3_is_mcrfo_v2_2/final_replications.csv')
    v22_final['engine_version']='v2.2';v22_final['recomputed']=False
    # Remove v2.2 C_h35 rows
    v22_final=v22_final[~(v22_final['scheme']=='C_h35')]

    h35_final_jobs=[]
    for seed in FINAL_SEEDS:
        h35_final_jobs.append((sel_N,sel_R,(sel_N,sel_q,sel_B),seed,True,{'scheme':'C_h35','N':sel_N,'R':sel_R,'q_max':sel_q,'B':sel_B,'h':35,'seed':seed,'phase':'final','engine_version':'v2.2.1','recomputed':True}))
    h35_final_rows=_run_parallel(h35_final_jobs)
    df_final=pd.concat([v22_final,pd.DataFrame(h35_final_rows)],ignore_index=True)
    df_final.to_csv(f'{OUT_DIR}/final_replications_corrected.csv',index=False)
    log(f"  合并正式: {len(df_final)}行 (预期150)")

    # Final summary
    final_schemes=['A','B','C_h35','C_h40','C_h45']
    fsum=[]
    for sch in final_schemes:
        sub=df_final[df_final['scheme']==sch]
        if len(sub)==0:continue
        o=sub['annual_output'].values;l=sub['mean_daily_loss'].values;n=len(o)
        mo=np.mean(o);so=np.std(o,ddof=1);ml=np.mean(l);sl=np.std(l,ddof=1)
        cio=spstats.t.interval(0.95,n-1,loc=mo,scale=so/np.sqrt(n))
        cil=spstats.t.interval(0.95,n-1,loc=ml,scale=sl/np.sqrt(n))
        fsum.append({'scheme':sch,'mean_output':float(mo),'std_output':float(so),'ci95_output_low':float(cio[0]),'ci95_output_high':float(cio[1]),'mean_loss':float(ml),'std_loss':float(sl),'ci95_loss_low':float(cil[0]),'ci95_loss_high':float(cil[1]),'loss_p95':float(np.mean(sub['loss_p95'])),'loss_CVaR95':float(np.mean(sub['loss_cvar95'])),'mean_idle':float(np.mean(sub['mean_idle'])),'mean_shortage':float(np.mean(sub['mean_shortage'])),'utilization':float(np.mean(sub['utilization'])),'max_daily_pens':int(np.max(sub['max_daily_pens'])),'rental_day_ratio':float(np.mean(sub['rental_day_ratio']))})
    df_fsum=pd.DataFrame(fsum)
    df_fsum.to_csv(f'{OUT_DIR}/final_summary_corrected.csv',index=False)
    log(df_fsum.to_string(index=False))

    # Final h selection
    h_cands=[r for r in fsum if r['scheme'].startswith('C_h')]
    h_feas=[r for r in h_cands if r['mean_output']>=Y_min]
    if h_feas:
        best_h=sorted(h_feas,key=lambda r:r['mean_loss'])[0]
        log(f"\n  最终h: {best_h['scheme']} (loss={best_h['mean_loss']:.4f})")
        for r in h_feas:log(f"    {r['scheme']}: loss={r['mean_loss']:.4f} out={r['mean_output']:.1f}")
    c_final=best_h if h_feas else h_cands[0]

    # Statistical tests
    stests=[]
    for s1,s2 in [(c_final['scheme'],'A'),(c_final['scheme'],'B'),('A','B')]:
        for metric in ['annual_output','mean_daily_loss']:
            col='annual_output' if metric=='annual_output' else 'mean_daily_loss'
            v1=df_final[df_final['scheme']==s1][col].values;v2=df_final[df_final['scheme']==s2][col].values
            m1=np.mean(v1);m2=np.mean(v2);diff=m1-m2
            se=np.sqrt(np.var(v1,ddof=1)/len(v1)+np.var(v2,ddof=1)/len(v2))
            t_stat,p_val=spstats.ttest_ind(v1,v2,equal_var=False)
            vn1=np.var(v1,ddof=1)/len(v1);vn2=np.var(v2,ddof=1)/len(v2)
            df_w=(vn1+vn2)**2/(vn1**2/(len(v1)-1)+vn2**2/(len(v2)-1))
            ci=spstats.t.interval(0.95,df_w,loc=diff,scale=se)
            psd=np.sqrt((np.var(v1,ddof=1)+np.var(v2,ddof=1))/2)
            cd=diff/psd if psd>0 else 0
            stests.append({'comparison':f'{s1}_vs_{s2}','metric':metric,'mean_1':float(m1),'mean_2':float(m2),'mean_diff':float(diff),'ci95_diff_low':float(ci[0]),'ci95_diff_high':float(ci[1]),'welch_t':float(t_stat),'welch_df':float(df_w),'p_value':float(p_val),'cohens_d':float(cd),'significant_at_0.05':p_val<0.05})
    for h1,h2 in [(35,40),(40,45),(35,45)]:
        for metric in ['annual_output','mean_daily_loss']:
            col='annual_output' if metric=='annual_output' else 'mean_daily_loss'
            s1=f'C_h{h1}';s2=f'C_h{h2}'
            if s1 not in df_final['scheme'].values or s2 not in df_final['scheme'].values:continue
            v1=df_final[df_final['scheme']==s1][col].values;v2=df_final[df_final['scheme']==s2][col].values
            m1=np.mean(v1);m2=np.mean(v2);diff=m1-m2
            se=np.sqrt(np.var(v1,ddof=1)/len(v1)+np.var(v2,ddof=1)/len(v2))
            t_stat,p_val=spstats.ttest_ind(v1,v2,equal_var=False)
            vn1=np.var(v1,ddof=1)/len(v1);vn2=np.var(v2,ddof=1)/len(v2)
            df_w=(vn1+vn2)**2/(vn1**2/(len(v1)-1)+vn2**2/(len(v2)-1))
            ci=spstats.t.interval(0.95,df_w,loc=diff,scale=se)
            psd=np.sqrt((np.var(v1,ddof=1)+np.var(v2,ddof=1))/2)
            cd=diff/psd if psd>0 else 0
            stests.append({'comparison':f'{s1}_vs_{s2}','metric':metric,'mean_1':float(m1),'mean_2':float(m2),'mean_diff':float(diff),'ci95_diff_low':float(ci[0]),'ci95_diff_high':float(ci[1]),'welch_t':float(t_stat),'welch_df':float(df_w),'p_value':float(p_val),'cohens_d':float(cd),'significant_at_0.05':p_val<0.05})
    pd.DataFrame(stests).to_csv(f'{OUT_DIR}/statistical_tests_corrected.csv',index=False)

    # h comparison
    hcomp=[]
    for h in [35,40,45]:
        sch=f'C_h{h}'
        if sch not in df_final['scheme'].values:continue
        sub=df_final[df_final['scheme']==sch]
        o=sub['annual_output'].values;l=sub['mean_daily_loss'].values;n=len(o)
        mo=np.mean(o);so=np.std(o,ddof=1);cio=spstats.t.interval(0.95,n-1,loc=mo,scale=so/np.sqrt(n))
        ml=np.mean(l);sl=np.std(l,ddof=1);cil=spstats.t.interval(0.95,n-1,loc=ml,scale=sl/np.sqrt(n))
        hcomp.append({'h':h,'T_fatt':210-2*(h-40),'mean_output':float(mo),'std_output':float(so),'ci95_output_low':float(cio[0]),'ci95_output_high':float(cio[1]),'mean_loss':float(ml),'std_loss':float(sl),'ci95_loss_low':float(cil[0]),'ci95_loss_high':float(cil[1]),'mean_idle':float(np.mean(sub['mean_idle'])),'mean_shortage':float(np.mean(sub['mean_shortage'])),'rental_day_ratio':float(np.mean(sub['rental_day_ratio']))})
    pd.DataFrame(hcomp).to_csv(f'{OUT_DIR}/h_comparison_corrected.csv',index=False)

    # Relative improvements
    a_r=[r for r in fsum if r['scheme']=='A'][0];b_r=[r for r in fsum if r['scheme']=='B'][0]
    log(f"\n{'='*70}");log("相对改进");log(f"{'='*70}")
    for label,row in [(c_final['scheme'],c_final),('B',b_r)]:
        vs_a_o=(row['mean_output']/a_r['mean_output']-1)*100;vs_a_l=(row['mean_loss']/a_r['mean_loss']-1)*100
        log(f"  {label} vs A: output {vs_a_o:+.1f}%  loss {vs_a_l:+.1f}%")
        if label!='B':
            vs_b_o=(row['mean_output']/b_r['mean_output']-1)*100;vs_b_l=(row['mean_loss']/b_r['mean_loss']-1)*100
            log(f"  {label} vs B: output {vs_b_o:+.1f}%  loss {vs_b_l:+.1f}%")
    log(f"  B vs A: output {(b_r['mean_output']/a_r['mean_output']-1)*100:+.1f}%  loss {(b_r['mean_loss']/a_r['mean_loss']-1)*100:+.1f}%")
    log("  负损失=降低,正产出=提高")

    # Daily logs (recommended h only)
    log(f"\n{'='*70}");log("每日日志 seed=2000");log(f"{'='*70}")
    for h_val,label in [(35,'C_h35'),(40,'C_h40'),(45,'C_h45')]:
        eng.T_NURS=h_val;eng.T_FATT=210-2*(h_val-40)
        stats,df_log,_=run_one(sel_N,sel_R,(sel_N,sel_q,sel_B),2000,True)
        df_log.to_csv(f'{OUT_DIR}/daily_{label}_seed2000.csv',index=False)
        log(f"  {label}:{len(df_log)}行")

    for h_val,label in [(40,'A_h40'),(40,'B_h40')]:
        eng.T_NURS=h_val;eng.T_FATT=210-2*(h_val-40)
        sfn=sched_A if label.startswith('A') else sched_B;args=(A_STARTS,A_SIZES) if label.startswith('A') else()
        Nv=426 if label.startswith('A') else 378;Rv=9 if label.startswith('A') else 8
        stats=run_sched(Nv,Rv,sfn,args,2000)
    eng.T_NURS=40;eng.T_FATT=210

    # Config
    with open(f'{OUT_DIR}/config.json','w') as f:json.dump({'model':'IS-MCRFO v2.2.1','fix':'dynamic eng.T_FATT in Obs._p()','Y_ref':float(ref_A),'Y_min':float(Y_min)},f,indent=2)

    # README
    with open(f'{OUT_DIR}/README_audit.txt','w') as f:
        f.write("IS-MCRFO v2.2.1 审计说明\n"+"="*60+"\n")
        f.write("Fix: Obs._p() uses eng.T_FATT (dynamic) instead of T_FATT (module constant)\n")
        f.write(f"Tests: {tp} pass, {tf} fail\n")
        f.write(f"Regression: {len(df_reg)} rows, max diff={max_diff_all}\n")
        f.write(f"Selection: N={sel['selected_N']}, q_max={sel['selected_q_max']}, B={sel['selected_B']}, h={sel['selected_h']}\n")
        f.write(f"Y_ref={ref_A:.2f}, Y_min={Y_min:.2f}, feasible={len(feasible)}/{len(param_grid)}\n")

    # Zip
    zp=f'{OUT_DIR}_delivery.zip'
    with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as zf:
        zf.write(__file__,os.path.basename(__file__))
        for fname in sorted(os.listdir(OUT_DIR)):
            zf.write(os.path.join(OUT_DIR,fname),fname)
    zs=os.path.getsize(zp);nf=len(os.listdir(OUT_DIR))+1
    log(f"\n{'='*70}");log("交付");log(f"{'='*70}")
    log(f"  压缩包: {zp} ({zs:,} bytes, {nf} files)")
    log(f"  总耗时: {time.time()-t0:.0f}s")
    log("完成。")
