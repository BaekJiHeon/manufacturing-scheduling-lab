"""All figures read persisted CSV, never hard-coded result arrays."""
import argparse,csv,json,hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import t
ROOT=Path(__file__).resolve().parents[2]
COLORS=['#0072B2','#E69F00','#009E73','#CC79A7','#56B4E9','#D55E00','#999999','#000000']


def generate(run):
    rows=list(csv.DictReader((run/'metrics.csv').open()));methods=list(dict.fromkeys(r['method'] for r in rows))
    out=ROOT/'figures/publication'/run.name;out.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.labelsize':8,'axes.titlesize':9,
                         'axes.linewidth':.8,'lines.linewidth':1.4,'axes.spines.top':False,'axes.spines.right':False,
                         'pdf.fonttype':42,'svg.fonttype':'none','savefig.facecolor':'white'})
    files=[];summary=[]
    for method in methods:
        group=[r for r in rows if r['method']==method];item=dict(method=method,n=len(group))
        for metric in ['makespan','total_tardiness','runtime_ms','bks_gap']:
            v=np.array([float(r[metric]) for r in group if r[metric]!=''])
            if not len(v):continue
            sd=v.std(ddof=1) if len(v)>1 else 0;ci=t.ppf(.975,len(v)-1)*sd/np.sqrt(len(v)) if len(v)>1 else 0
            item.update({metric+'_mean':v.mean(),metric+'_std':sd,metric+'_ci95_halfwidth':ci,metric+'_worst':v.max()})
        summary.append(item)
    keys=list(dict.fromkeys(k for item in summary for k in item))
    with (run/'summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(summary)
    def save(fig,name):
        for ext in ['pdf','svg','png']:
            path=out/f'{name}.{ext}';fig.savefig(path,dpi=600);files.append(str(path.relative_to(ROOT)))
        plt.close(fig)
    for metric,label,name in [('makespan','Makespan (benchmark time units)','makespan_benchmark'),('total_tardiness','Total tardiness (benchmark time units)','tardiness_benchmark'),('runtime_ms','End-to-end scheduling runtime (ms; log scale)','runtime_benchmark')]:
        fig,ax=plt.subplots(figsize=(178/25.4,85/25.4),layout='constrained')
        for i,method in enumerate(methods):
            v=np.array([float(r[metric]) for r in rows if r['method']==method and r[metric]!=''])
            if not len(v):continue
            ax.scatter(np.full(len(v),i)+np.linspace(-.12,.12,len(v)),v,color=COLORS[i],marker=['o','s','^','D','v','P','X','*'][i],s=22,alpha=.8)
            ax.plot([i-.23,i+.23],[v.mean()]*2,color='black',lw=1.4)
        if metric=='makespan':ax.axhline(40,color='gray',ls='--',lw=1,label='Published lower/upper bound = 40');ax.legend(fontsize=7)
        if metric=='runtime_ms':ax.set_yscale('log')
        ax.set_xticks(range(len(methods)),methods,rotation=25,ha='right');ax.set_ylabel(label);ax.grid(axis='y',alpha=.18)
        ax.set_title('MK01 · fixed synthetic due dates · 5 algorithm seeds per method')
        save(fig,name)
    fig,ax=plt.subplots(figsize=(178/25.4,85/25.4),layout='constrained')
    for i,method in enumerate(methods):
        group=[r for r in rows if r['method']==method and r['makespan']!='']
        ax.scatter([float(r['makespan']) for r in group],[float(r['total_tardiness']) for r in group],label=method,c=COLORS[i],marker=['o','s','^','D','v','P','X','*'][i],s=24)
    ax.set(xlabel='Makespan (benchmark time units)',ylabel='Total tardiness (benchmark time units)',title='Observed trade-off · CP-SAT minimizes makespan only')
    ax.legend(fontsize=7,ncol=2);ax.grid(alpha=.15);save(fig,'objective_tradeoff')
    feasible=[r for r in rows if r['method'].startswith('CP-SAT') and r['makespan']!='']
    if feasible:
        best=min(feasible,key=lambda r:(float(r['makespan']),int(r['step'])))
        schedule=[s for s in csv.DictReader((run/'schedules.csv').open()) if s['step']==best['step']]
        fig,ax=plt.subplots(figsize=(178/25.4,85/25.4),layout='constrained')
        for r in schedule:
            j=int(r['job']);m=int(r['machine']);s=float(r['start']);duration=float(r['duration'])
            ax.barh(m+1,duration,left=s,height=.72,color=plt.get_cmap('tab10')(j),edgecolor='black',lw=.3,hatch=['','//','\\\\','..','xx'][j%5])
            if duration>=2:ax.text(s+duration/2,m+1,f'J{j+1}',ha='center',va='center',fontsize=6)
        ax.set(xlabel='Simulation time (benchmark time units)',ylabel='Machine',title=f"Static CP-SAT schedule · {best['status']} · makespan {best['makespan']}")
        ax.set_yticks(range(1,7));ax.invert_yaxis();ax.grid(axis='x',alpha=.15);save(fig,'cpsat_static_gantt')
    manifest=dict(script='src/visualization/generate_figures.py',sources=[str((run/x).relative_to(ROOT)) for x in ['metrics.csv','schedules.csv']],files=files,
                  width_mm=178,dpi=600,smoothing='none',confidence_interval='Summary CSV: Student t 95% CI over algorithm seeds on ONE fixed instance; deterministic repetitions do not measure generalization.',
                  limitations='No training/dynamic/generalization/ablation curves: those experiments have not run.')
    manifest['source_sha256']={str((run/x).relative_to(ROOT)):hashlib.sha256((run/x).read_bytes()).hexdigest() for x in ['metrics.csv','schedules.csv']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);args=p.parse_args();generate(ROOT/'results/phase1_cpsat'/args.run_id)
if __name__=='__main__':main()
