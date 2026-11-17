"""Repeated *synthetic due-date* sensitivity study on fixed Brandimarte MK01.
All outputs are local to project root. No RL or CP-SAT claims.
"""
from pathlib import Path
import sys, csv, json, time, platform
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_baselines import parse_fjsp, simulate, build_due_dates
ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'results'/'phase1';FIG=ROOT/'figures'/'phase1'

N=50
METHODS=('FIFO','SPT','EDD','MWKR','Random')

def main():
    global RESULT, FIG
    from datetime import datetime, timezone
    from uuid import uuid4
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
    RESULT=ROOT/'results'/'legacy_repeated'/run_id;FIG=RESULT/'figures'
    FIG.mkdir(parents=True)
    jobs,m=parse_fjsp(ROOT/'data'/'mk01.txt')
    rows=[]
    for seed in range(N):
        due=build_due_dates(jobs,seed)
        for method in METHODS:
            start=time.perf_counter()
            result=simulate(jobs,m,method,seed=seed,due=due)
            runtime=(time.perf_counter()-start)*1000
            rows.append(dict(instance='MK01',scenario_seed=seed,method=method,makespan=result['makespan'],total_tardiness=result['total_tardiness'],runtime_ms=round(runtime,5),due_date_source='synthetic'))
    with open(RESULT/'repeated_baselines.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=[]
    for method in METHODS:
        subset=[r for r in rows if r['method']==method]
        item={'method':method,'n_scenarios':N}
        for metric in ('makespan','total_tardiness','runtime_ms'):
            v=np.array([r[metric] for r in subset],dtype=float)
            item[metric+'_mean']=float(np.mean(v));item[metric+'_std']=float(np.std(v,ddof=1));item[metric+'_median']=float(np.median(v))
        summary.append(item)
    with open(RESULT/'summary.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    with open(RESULT/'metadata.json','w') as f:
        json.dump({'benchmark':'Brandimarte1993 MK01','jobs':len(jobs),'machines':m,'operations':sum(map(len,jobs)),'scenario_seeds':list(range(N)),'scenario_description':'Due dates generated with seed and slack 1.7; Random dispatch seed reused. No dynamic machine failures or arrivals.','python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__},f,indent=2)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':10,'axes.titlesize':11,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none','savefig.facecolor':'white'})
    fig,axs=plt.subplots(1,2,figsize=(7.3,3.1),layout='constrained')
    for ax,metric,label in [(axs[0],'makespan','Makespan (benchmark time units)'),(axs[1],'total_tardiness','Total tardiness (synthetic due dates)')]:
        collections=[np.array([r[metric] for r in rows if r['method']==method]) for method in METHODS]
        ax.boxplot(collections,positions=np.arange(1,6),widths=.55,patch_artist=True,showfliers=False,boxprops={'facecolor':'#C7D8E8','edgecolor':'#234B6B'},medianprops={'color':'#B0413E','linewidth':1.5},whiskerprops={'color':'#234B6B'},capprops={'color':'#234B6B'})
        ax.set_xticks(range(1,6),METHODS);ax.set_ylabel(label);ax.grid(axis='y',alpha=.18)
    axs[0].set_title('(a) Completion time');axs[1].set_title('(b) Due-date sensitivity')
    fig.suptitle('MK01 | 50 synthetic scenarios | same job-shop instance',fontsize=11)
    for ext in ('pdf','svg','png'):fig.savefig(FIG/('mk01_50seed_heuristic_comparison.'+ext),dpi=600)
    plt.close(fig)
    print('Completed:',len(rows),'valid schedules across',N,'seeds')
    for s in summary:print(s['method'],round(s['makespan_mean'],2),round(s['total_tardiness_mean'],2))
if __name__=='__main__':main()
