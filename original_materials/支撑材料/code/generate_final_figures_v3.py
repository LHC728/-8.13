#!/usr/bin/env python3
"""Final paper figures v3 — Chinese labels, fixed Gantt, clean axes."""
import pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.ticker as mticker
import os

OUT = '/home/user/workspace/latex-template/texfile/figures'
os.makedirs(OUT, exist_ok=True)

NAVY='#17324D';TEAL='#2A9D8F';GOLD='#E9B44C';CORAL='#E76F51';GREY='#E9EEF2';DG='#4B5563'
plt.rcParams.update({'font.sans-serif':['Noto Sans CJK SC','SimSun','DejaVu Sans'],'axes.unicode_minus':False,
    'axes.edgecolor':DG,'axes.grid':True,'grid.alpha':0.3,'grid.color':DG,
    'xtick.color':DG,'ytick.color':DG,'figure.dpi':150,'savefig.dpi':300})

# ── Fig P2: Batch schedule (fixed Gantt: ewe cycle only, + stacked pens) ──
def fig_p2():
    starts=[0,7,15,22,30,37,44,52,59,66,74,81,89,96,103,111,118,126,133,140,148,155,163,170,177,185,192,199,207,214,222]
    sizes=[14,14,13,14,14,14,14,13,14,14,13,14,14,14,14,14,14,14,14,13,14,13,14,14,14,13,14,13,14,14,13]
    fig,(ax1,ax2)=plt.subplots(2,1,figsize=(10,7.5),gridspec_kw={'height_ratios':[3,2]})
    colors={'配种期':TEAL,'妊娠期':'#5B9BD5','哺乳期':CORAL,'休整期':GOLD}
    for i,(s,sz) in enumerate(zip(starts,sizes)):
        phases=[('配种期',s,s+20),('妊娠期',s+20,s+20+149),('哺乳期',s+20+149,s+20+149+40),('休整期',s+20+149+40,s+20+149+40+18)]
        for ph,st,en in phases:
            ax1.barh(i+1,en-st,left=st,color=colors[ph],alpha=0.85,edgecolor='none')
    # Extend to show last batch completing rest
    last_end = max(s+20+149+40+18 for s in starts)
    ax1.set_xlim(0,max(250,last_end+10));ax1.set_ylim(0.5,31.5);ax1.invert_yaxis()
    ax1.set_xlabel('周期天数');ax1.set_ylabel('配种批次编号')
    ax1.set_title('图A：31批固定配种计划（23批×14只 + 8批×13只 = 426只母羊）')
    patches=[plt.Rectangle((0,0),1,1,color=c,label=k) for k,c in colors.items()]
    ax1.legend(handles=patches,ncol=4,loc='upper right',fontsize=8)

    # Panel B: daily pens
    df=pd.read_csv('/home/user/workspace/output/problem2_fixed_cohort_final_daily.csv')
    days=np.arange(len(df))
    ax2.stackplot(days,df['pens_mate'],df['pens_preg'],df['pens_nurs'],df['pens_rest'],df['pens_fatt'],df['pens_ram'],
                  labels=['配种栏','妊娠栏','哺乳栏','休整栏','育肥栏','公羊栏'],
                  colors=[TEAL,'#5B9BD5',CORAL,GOLD,'#9B59B6','#95A5A6'],alpha=0.85)
    ax2.axhline(112,color=CORAL,linewidth=2,linestyle='--',label='112栏容量线')
    ax2.set_xlabel('周期天数');ax2.set_ylabel('羊栏数量')
    ax2.set_title('图B：每日羊栏占用堆叠面积图（110–112栏，0个超限日）')
    ax2.legend(ncol=7,fontsize=7,loc='upper right')
    ax2.set_xlim(0,229);ax2.set_ylim(0,125)
    plt.tight_layout()
    fig.savefig(f'{OUT}/fig_p2_batch_schedule.pdf',bbox_inches='tight')
    fig.savefig(f'{OUT}/fig_p2_batch_schedule.png',bbox_inches='tight')
    plt.close()

# ── Fig P3a: Pareto ──
def fig_p3a():
    df=pd.read_csv('/home/user/workspace/output/problem3_is_mcrfo_v2_2_2/screening_summary_corrected.csv')
    gp=pd.read_csv('/home/user/workspace/output/problem3_is_mcrfo_v2_2_2/global_pareto_corrected.csv')
    gp=gp[gp['pareto']]
    fig,ax=plt.subplots(figsize=(9,6))
    h_colors={35:CORAL,40:TEAL,45:NAVY}
    sizes_map={378:40,390:60,402:80,414:100,426:120}
    for _,r in df.iterrows():
        c=h_colors.get(int(r['h']),GREY);s=sizes_map.get(int(r['N']),30)
        ax.scatter(r['mean_output'],r['mean_loss'],c=c,s=s,alpha=0.35,edgecolors='none')
    for _,r in gp.iterrows():
        lbl=str(r.get('scheme',''))
        ax.scatter(r['mean_output'],r['mean_loss'],c=GOLD,s=200,edgecolors=NAVY,linewidth=2,zorder=10,marker='D')
    best_out=1218.64;best_loss=5.316
    ax.scatter(best_out,best_loss,c=GOLD,s=400,edgecolors='black',linewidth=3,zorder=20,marker='*')
    ax.annotate('最终推荐\nN=378,q_max=21,B=0,h=45',(best_out,best_loss),
                xytext=(best_out-70,best_loss-2.5),arrowprops=dict(arrowstyle='->',color=NAVY),fontsize=9,color=NAVY,fontweight='bold')
    ax.axvline(1194.30,color=CORAL,linestyle='--',linewidth=1.5,label=r'$Y_{\min}=1194.30$')
    ax.set_xlabel('年化出栏量（只/年）');ax.set_ylabel('日均损失')
    ax.set_title('90种反馈策略的产出—损失分布与全局Pareto前沿')
    from matplotlib.lines import Line2D
    leg=[Line2D([0],[0],marker='o',color='w',markerfacecolor=c,markersize=8,label=f'h={h}') for h,c in h_colors.items()]
    leg+=[Line2D([0],[0],marker='D',color='w',markerfacecolor=GOLD,markeredgecolor=NAVY,markersize=10,label='全局Pareto方案')]
    leg+=[Line2D([0],[0],marker='*',color='w',markerfacecolor=GOLD,markeredgecolor='black',markersize=15,label='最终推荐方案')]
    leg.append(Line2D([0],[0],color=CORAL,linestyle='--',label='Y_min=1194.30'))
    ax.legend(handles=leg,loc='upper left',fontsize=8)
    ax.annotate('损失降低方向',xy=(0.05,0.12),xycoords='axes fraction',fontsize=10,color=TEAL,fontweight='bold',
                arrowprops=dict(arrowstyle='->',color=TEAL))
    ax.annotate('产量增加方向',xy=(0.82,0.88),xycoords='axes fraction',fontsize=10,color=NAVY,fontweight='bold',
                arrowprops=dict(arrowstyle='->',color=NAVY))
    plt.tight_layout()
    fig.savefig(f'{OUT}/fig_p3_pareto.pdf',bbox_inches='tight')
    fig.savefig(f'{OUT}/fig_p3_pareto.png',bbox_inches='tight')
    plt.close()

# ── Fig P3b: Five-scheme dashboard ──
def fig_p3b():
    dfs=pd.read_csv('/home/user/workspace/output/problem3_is_mcrfo_v2_2_2/final_summary_corrected.csv')
    fig,axes=plt.subplots(2,2,figsize=(12,9))
    schemes=['A','B','C_h35','C_h40','C_h45']
    colors_bar=[NAVY,TEAL,CORAL,TEAL,GOLD]
    short_labels=['A\n(开环,426只)','B\n(保守,378只)','C_h35\n(N=378,q=21,\nB=0,h=35)','C_h40\n(N=378,q=21,\nB=0,h=40)','C_h45\n(N=378,q=21,\nB=0,h=45)']
    x=np.arange(5)
    # A: Output with CI
    ax=axes[0,0]
    o=dfs['mean_output'].values;olo=dfs['ci95_output_low'].values;ohi=dfs['ci95_output_high'].values
    ax.bar(x,o,color=colors_bar,alpha=0.85)
    ax.errorbar(x,o,yerr=[o-olo,ohi-o],fmt='none',ecolor=DG,capsize=4)
    ax.axhline(1194.30,color=CORAL,linestyle='--',linewidth=1.2,label='Y_min=1194.30')
    # Mark C_h35 as infeasible
    ax.annotate('不满足\nY_min',(2,1157),fontsize=8,color=CORAL,fontweight='bold',ha='center',va='top')
    ax.set_xticks(x);ax.set_xticklabels(short_labels,fontsize=7)
    ax.set_ylabel('年化出栏量（只/年）');ax.set_title('A：年化出栏量与95%置信区间')
    ax.legend(fontsize=7)
    # B: Loss with CI
    ax=axes[0,1]
    l=dfs['mean_loss'].values;llo=dfs['ci95_loss_low'].values;lhi=dfs['ci95_loss_high'].values
    ax.bar(x,l,color=colors_bar,alpha=0.85)
    ax.errorbar(x,l,yerr=[l-llo,lhi-l],fmt='none',ecolor=DG,capsize=4)
    ax.set_xticks(x);ax.set_xticklabels(short_labels,fontsize=7)
    ax.set_ylabel('日均损失');ax.set_title('B：日均损失与95%置信区间')
    # C: Idle + Shortage stacked
    ax=axes[1,0]
    idle=dfs['mean_idle'].values;short=dfs['mean_shortage'].values
    ax.bar(x,idle,color=TEAL,alpha=0.85,label='空栏损失（×1）')
    ax.bar(x,short*3,bottom=idle,color=CORAL,alpha=0.85,label='租栏损失（×3）')
    ax.set_xticks(x);ax.set_xticklabels(short_labels,fontsize=7)
    ax.set_ylabel('损失分量');ax.set_title('C：损失分解（空栏 + 3×租栏）')
    ax.legend(fontsize=7)
    # D: P95 and CVaR95 only (no twin axis)
    ax=axes[1,1]
    b1=ax.bar(x-0.15,dfs['loss_p95'].values,0.3,color=NAVY,alpha=0.85,label='P95')
    b2=ax.bar(x+0.15,dfs['loss_CVaR95'].values,0.3,color=CORAL,alpha=0.85,label='CVaR95')
    ax.set_xticks(x);ax.set_xticklabels(short_labels,fontsize=7)
    ax.set_ylabel('损失值');ax.set_title('D：损失P95与CVaR95')
    ax.legend(loc='upper left',fontsize=7)
    plt.tight_layout()
    fig.savefig(f'{OUT}/fig_p3_comparison.pdf',bbox_inches='tight')
    fig.savefig(f'{OUT}/fig_p3_comparison.png',bbox_inches='tight')
    plt.close()

# ── Fig P3c: h sensitivity ──
def fig_p3c():
    df=pd.read_csv('/home/user/workspace/output/problem3_is_mcrfo_v2_2_2/h_comparison_corrected.csv')
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(10,4.5))
    h=df['h'].values
    o=df['mean_output'].values;olo=df['ci95_output_low'].values;ohi=df['ci95_output_high'].values
    l=df['mean_loss'].values;llo=df['ci95_loss_low'].values;lhi=df['ci95_loss_high'].values
    ax1.errorbar([35],[o[0]],[(o[0]-olo[0],)],[(ohi[0]-o[0],)],fmt='o',color=CORAL,markersize=10,capsize=6,label='不满足Y_min')
    ax1.errorbar([40],[o[1]],[(o[1]-olo[1],)],[(ohi[1]-o[1],)],fmt='o',color=TEAL,markersize=10,capsize=6,label='满足Y_min')
    ax1.errorbar([45],[o[2]],[(o[2]-olo[2],)],[(ohi[2]-o[2],)],fmt='*',color=GOLD,markersize=15,capsize=6,markeredgecolor='black',markeredgewidth=1.5,label='最终推荐')
    ax1.axhline(1194.30,color=CORAL,linestyle='--',linewidth=1.2)
    ax1.annotate('Y_min=1194.30',(35.5,1195.5),fontsize=8,color=CORAL)
    for hi,tf in zip([35,40,45],[220,210,200]):
        ax1.annotate(f'育肥期{tf}天',(hi,o[[35,40,45].index(hi)]+25),fontsize=7,color=DG,ha='center')
    ax1.set_xlabel('哺乳期 h（天）');ax1.set_ylabel('年化出栏量（只/年）')
    ax1.set_title('A：年化出栏量与95%置信区间');ax1.legend(fontsize=8)
    ax1.set_xticks([35,40,45]);ax1.set_ylim(1050,1300)
    # Loss
    ax2.errorbar([35],[l[0]],[(l[0]-llo[0],)],[(lhi[0]-l[0],)],fmt='o',color=CORAL,markersize=10,capsize=6)
    ax2.errorbar([40],[l[1]],[(l[1]-llo[1],)],[(lhi[1]-l[1],)],fmt='o',color=TEAL,markersize=10,capsize=6)
    ax2.errorbar([45],[l[2]],[(l[2]-llo[2],)],[(lhi[2]-l[2],)],fmt='*',color=GOLD,markersize=15,capsize=6,markeredgecolor='black',markeredgewidth=1.5)
    ax2.set_xlabel('哺乳期 h（天）');ax2.set_ylabel('日均损失')
    ax2.set_title('B：日均损失与95%置信区间')
    ax2.set_xticks([35,40,45])
    plt.tight_layout()
    fig.savefig(f'{OUT}/fig_p3_h_sensitivity.pdf',bbox_inches='tight')
    fig.savefig(f'{OUT}/fig_p3_h_sensitivity.png',bbox_inches='tight')
    plt.close()

# ── Fig P3d: Daily pens trajectory ──
def fig_p3d():
    fig,axes=plt.subplots(3,1,figsize=(10,7),sharex=True)
    for ax,label,color,title,csv_dir in [
        (axes[0],'A_h40',CORAL,'A：方案A（开环，426只母羊，h=40）— 长期超容量运行','v2_2'),
        (axes[1],'B_h40',TEAL,'B：方案B（保守，378只母羊，h=40）— 保守运行，低于容量','v2_2'),
        (axes[2],'C_h45',GOLD,'C：方案C_h45（最终推荐，N=378，q_max=21，B=0，h=45）— 容量与产量平衡','v2_2_2')]:
        if csv_dir=='v2_2':
            df=pd.read_csv(f'/home/user/workspace/output/problem3_is_mcrfo_v2_2/daily_{label}_seed2000.csv')
        else:
            df=pd.read_csv(f'/home/user/workspace/output/problem3_is_mcrfo_v2_2_2/daily_{label}_seed2000.csv')
        days=df['day'].values
        ax.plot(days,df['pens_total'].values,color=color,alpha=0.5,linewidth=0.5)
        rm=pd.Series(df['pens_total'].values).rolling(50).mean()
        ax.plot(days,rm,color=NAVY,linewidth=1.5,label='50天滚动均值')
        ax.axhline(112,color=CORAL,linestyle='--',linewidth=1.2,label='112栏容量线')
        ax.set_ylabel('总羊栏数');ax.set_title(title,fontsize=9)
        ax.legend(fontsize=7,loc='upper right')
        ax.set_ylim(80,135)
    axes[-1].set_xlabel('评价期天数（第840–2664天）')
    plt.tight_layout()
    fig.savefig(f'{OUT}/fig_p3_daily_pens.pdf',bbox_inches='tight')
    fig.savefig(f'{OUT}/fig_p3_daily_pens.png',bbox_inches='tight')
    plt.close()

if __name__=='__main__':
    fig_p2();fig_p3a();fig_p3b();fig_p3c();fig_p3d()
    print("All 5 figures generated with Chinese labels.")
