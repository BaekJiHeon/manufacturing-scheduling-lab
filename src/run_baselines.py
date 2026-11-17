"""Reproducible STATIC FJSP heuristic baselines on Brandimarte mk01.
Dataset mirrored from ScheduleOpt/benchmarks (Brandimarte 1993); original remains authoritative.
No RL or dynamic fault is claimed here.
"""
from pathlib import Path
import json, csv, time
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]

try:
    from .simulator.problem import parse_fjsp, verify
except ImportError:  # Legacy direct script invocation
    from simulator.problem import parse_fjsp, verify

def build_due_dates(jobs,seed,slack=1.7):
    """Synthetic due-dates for EDD analysis; NOT part of original Brandimarte data."""
    rng=np.random.default_rng(seed)
    lengths=[sum(min(op.values()) for op in j) for j in jobs]
    return [int(np.ceil(l*slack*rng.uniform(.85,1.2))) for l in lengths]

def simulate(jobs,n_machines,rule,seed=0,due=None):
    rng=np.random.default_rng(seed)
    n=len(jobs); total=sum(map(len,jobs))
    next_op=[0]*n; running={}; time_now=0; rows=[]; completions=[0]*n
    while sum(next_op)<total or running:
        # at current decision time, launch nonconflicting ready operations until none possible
        while True:
            candidates=[]
            for j,ops in enumerate(jobs):
                if next_op[j]>=len(ops) or j in running: continue
                oi=next_op[j]
                for m,ptime in ops[oi].items():
                    if any(v[0]==m for v in running.values()):continue
                    remaining=sum(min(o.values()) for o in ops[oi:])
                    if rule=='FIFO': key=(j, oi, ptime, m)
                    elif rule=='SPT':key=(ptime,j,m)
                    elif rule=='EDD':key=(due[j],j,ptime,m)
                    elif rule=='MWKR':key=(-remaining,j,ptime,m)
                    elif rule=='Random':key=(rng.random(),j,m)
                    else:raise ValueError(rule)
                    candidates.append((key,j,oi,m,ptime))
            if not candidates:break
            _,j,oi,m,ptime=min(candidates,key=lambda a:a[0])
            next_op[j]+=1
            running[j]=(m,time_now+ptime)
            rows.append(dict(job=j,operation=oi,machine=m,start=time_now,end=time_now+ptime,duration=ptime))
        if not running:raise RuntimeError('deadlock')
        time_now=min(x[1] for x in running.values())
        for j,(m,finish) in list(running.items()):
            if finish==time_now:
                del running[j]
                if next_op[j]==len(jobs[j]):completions[j]=time_now
    verify(jobs,n_machines,rows)
    makespan=max(r['end'] for r in rows)
    return dict(rule=rule,makespan=makespan,total_tardiness=sum(max(0,c-d) for c,d in zip(completions,due)) if due else None,
                schedule=rows)

def plot_gantt(result,n_machines,out):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
    fig,ax=plt.subplots(figsize=(7.1,3.5),layout='constrained')
    palette=plt.get_cmap('tab10')
    for r in result['schedule']:
        ax.barh(r['machine']+1,r['duration'],left=r['start'],height=.65,color=palette(r['job']),edgecolor='white',linewidth=.3)
    ax.set(xlabel='Simulation time (benchmark time units)',ylabel='Machine',title=f"Brandimarte MK01 | {result['rule']} | Makespan = {result['makespan']}")
    ax.set_yticks(range(1,n_machines+1))
    ax.invert_yaxis();ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
    fig.savefig(out.with_suffix('.svg'))
    fig.savefig(out.with_suffix('.png'),dpi=600)
    fig.savefig(out.with_suffix('.pdf'))
    plt.close(fig)

def main():
    from datetime import datetime, timezone
    from uuid import uuid4
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
    output=ROOT/'results'/'legacy_baselines'/run_id
    figures=output/'figures';figures.mkdir(parents=True)
    jobs,m=parse_fjsp(ROOT/'data/mk01.txt');due=build_due_dates(jobs,42)
    results=[]
    for rule in ('FIFO','SPT','EDD','MWKR','Random'):
        s=time.perf_counter()
        res=simulate(jobs,m,rule,seed=42,due=due)
        elapsed=(time.perf_counter()-s)*1000
        res['runtime_ms']=elapsed
        results.append(res)
        plot_gantt(res,m,figures/f'mk01_{rule.lower()}_gantt')
    with (output/'mk01_results.json').open('w') as f:json.dump(dict(dataset='Brandimarte1993/mk01',jobs=len(jobs),machines=m,operations=sum(map(len,jobs)),due_dates='synthetic seeded 42',results=results),f,indent=2)
    with (output/'mk01_summary.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['rule','makespan','total_tardiness','runtime_ms']);w.writeheader();w.writerows({k:r[k] for k in w.fieldnames} for r in results)
    fig,ax=plt.subplots(figsize=(6.0,3.4),layout='constrained')
    names=[r['rule'] for r in results];vals=[r['makespan'] for r in results]
    bars=ax.bar(names,vals,color=plt.get_cmap('tab10')(0),width=.62)
    for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+1,str(v),ha='center',fontsize=9)
    ax.set(ylabel='Makespan (benchmark time units)',title='Brandimarte MK01 | Static scheduling baselines',ylim=(0,max(vals)*1.15))
    ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.16);ax.set_axisbelow(True)
    for suffix in ('.pdf','.svg','.png'):fig.savefig(figures/('mk01_makespan_comparison'+suffix),dpi=600)
    plt.close(fig)
    print('Data:',len(jobs),'jobs',m,'machines',sum(map(len,jobs)),'operations')
    for r in results:print(r['rule'],r['makespan'],r['total_tardiness'],round(r['runtime_ms'],2))

if __name__=='__main__':main()
