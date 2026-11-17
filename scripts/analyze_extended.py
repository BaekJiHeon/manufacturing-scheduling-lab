"""Measured summaries and publication figures from persisted campaign artifacts only."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats
from src.evaluation.campaign import ROOT
from src.algorithms.rolling_cpsat import active_segments
COLORS=['#0072B2','#D55E00','#009E73','#CC79A7','#E69F00','#56B4E9','#000000','#999999']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.labelsize':8,'legend.fontsize':7,'axes.linewidth':.8,'lines.linewidth':1.2,'savefig.dpi':600,'svg.fonttype':'none','pdf.fonttype':42})

def load(family):
    rid=(ROOT/'reports'/f'latest_{family}_run.txt').read_text().strip();path=ROOT/'results'/family/rid
    if json.loads((path/'metadata.json').read_text())['status']!='completed':raise RuntimeError(f'{family} incomplete')
    return path,pd.read_csv(path/'metrics.csv')

def summarize(frame,group,values):
    rows=[]
    for keys,part in frame.groupby(group,dropna=False):
        row=dict(zip(group,keys if isinstance(keys,tuple) else [keys]))
        for value in values:
            x=part[value].dropna().astype(float);n=len(x)
            row[value+'_n']=n;row[value+'_mean']=x.mean();row[value+'_std']=x.std(ddof=1);row[value+'_worst']=x.max()
            width=stats.t.ppf(.975,n-1)*x.std(ddof=1)/np.sqrt(n) if n>1 else np.nan
            row[value+'_ci95_low']=x.mean()-width;row[value+'_ci95_high']=x.mean()+width
        rows.append(row)
    return pd.DataFrame(rows)

def main():
    sp,s=load('expanded_static');dp,d=load('objectives_dynamic');pp,p=load('ppo_pilot')
    output=ROOT/'figures/publication'/pp.name;output.mkdir(parents=True,exist_ok=True);manifest={'source_files':{},'figures':[],'generator':str(Path(__file__).relative_to(ROOT)),'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'matplotlib':matplotlib.__version__,'raster_dpi':600}
    for path in [sp/'metrics.csv',dp/'metrics.csv',pp/'metrics.csv']:manifest['source_files'][str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    def save(fig,name):
        fig.savefig(output/(name+'.pdf'),bbox_inches='tight');fig.savefig(output/(name+'.svg'),bbox_inches='tight');fig.savefig(output/(name+'.png'),bbox_inches='tight',dpi=600);plt.close(fig);manifest['figures'].append(name)
    cp=s[s.method=='CP-SAT'].copy()
    summarize(cp,['instance','time_limit_s'],['makespan','total_tardiness','runtime_ms','bks_gap']).to_csv(pp/'static_summary.csv',index=False)
    summarize(d,['instance','scenario','method','objective','budget_s'],['makespan','total_tardiness','runtime_ms','cumulative_stability_cost']).to_csv(pp/'dynamic_objective_summary.csv',index=False)
    fig,axs=plt.subplots(1,2,figsize=(178/25.4,78/25.4),layout='constrained')
    names=sorted(s.instance.unique());x=np.arange(len(names))
    for i,budget in enumerate([1,5,30]):
        group=cp[cp.time_limit_s==budget].groupby('instance').mean(numeric_only=True).reindex(names)
        axs[0].plot(x,group.bks_gap*100,marker=['o','s','^'][i],color=COLORS[i],label=f'CP-SAT {budget}s')
        axs[1].plot(x,group.runtime_ms,marker=['o','s','^'][i],color=COLORS[i])
    heur_groups=s[s.method!='CP-SAT'].groupby(['instance','method']).mean(numeric_only=True).reset_index()
    heuristic=heur_groups.loc[heur_groups.groupby('instance').bks_gap.idxmin()].set_index('instance').reindex(names)
    axs[0].plot(x,heuristic.bks_gap*100,'k--x',label='Best heuristic per instance');axs[1].plot(x,heuristic.runtime_ms,'k--x')
    for ax in axs:ax.set_xticks(x,names,rotation=60);ax.grid(alpha=.2)
    axs[0].set_ylabel('Gap to pinned BKS (%)');axs[1].set_ylabel('End-to-end runtime (ms)');axs[1].set_yscale('log');fig.legend(*axs[0].get_legend_handles_labels(),loc='outside lower center',ncol=2);save(fig,'01_scalability')
    fig,axs=plt.subplots(1,3,figsize=(178/25.4,78/25.4),layout='constrained')
    for ax,name in zip(axs,['MK01','MK06','MK10']):
        for i,obj in enumerate(['makespan','tardiness','balanced','stable']):
            part=d[(d.instance==name)&(d.scenario=='static_objective')&(d.budget_s==5)&(d.objective==obj)]
            ax.scatter(part.makespan,part.total_tardiness,color=COLORS[i],marker=['o','s','^','D'][i],label=obj,s=20)
        ax.set_title(name);ax.set_xlabel('Makespan (units)');ax.grid(alpha=.2)
    axs[0].set_ylabel('Total tardiness (time units)');fig.legend(*axs[0].get_legend_handles_labels(),loc='outside lower center',ncol=4);save(fig,'02_objective_tradeoff')
    combined=d[d.scenario=='combined'].copy();combined['label']=combined.method+combined.apply(lambda r:f' {int(r.budget_s)}s {r.objective}' if r.method=='CP-SAT' else '',axis=1)
    fig,axs=plt.subplots(1,2,figsize=(178/25.4,80/25.4),layout='constrained')
    for ax,name in zip(axs,['MK01','MK06']):
        for i,(label,part) in enumerate(combined[combined.instance==name].groupby('label')):
            ax.scatter(part.cumulative_stability_cost,part.makespan,label=label,color=COLORS[i],marker=['o','s','^','D','v','P','X','*'][i],s=22)
        ax.set_title(name+' | same event tapes');ax.set_xlabel('Cumulative normalized revision cost');ax.grid(alpha=.2)
    axs[0].set_ylabel('Realized makespan (time units)');fig.legend(*axs[0].get_legend_handles_labels(),loc='outside lower center',ncol=3);save(fig,'03_dynamic_stability')
    selected=combined[(combined.instance=='MK01')&(combined.method=='CP-SAT')&(combined.budget_s==5)&(combined.objective=='stable')&(combined.seed==0)].iloc[0]
    record=dp/f'record_{int(selected.step):04d}.json';detail=json.loads(record.read_text());manifest['source_files'][str(record.relative_to(ROOT))]=hashlib.sha256(record.read_bytes()).hexdigest()
    fig,axs=plt.subplots(2,1,figsize=(178/25.4,112/25.4),layout='constrained',sharex=True)
    for ax,rows,outages,title in zip(axs,[detail['decisions'][0]['schedule'],detail['schedule']],[[],detail['outages']],['Initial plan (before events)','Executed schedule after event-triggered replanning']):
        for r in rows:
            for a,b in active_segments(r,outages):
                ax.broken_barh([(a,b-a)],(r['machine']-.35,.7),facecolors=COLORS[r['job']%len(COLORS)],edgecolors='white',linewidth=.3)
                if b-a>=2:ax.text((a+b)/2,r['machine'],str(r['job']+1),ha='center',va='center',fontsize=6,color='white' if r['job']%len(COLORS) in [0,1,2,3,6] else 'black')
        for e in detail['events']:
            if e['type']=='breakdown':ax.axvline(e['time'],color='#D55E00',ls='--',lw=.9)
            if e['type']=='arrival':ax.axvline(e['time'],color='#009E73',ls=':',lw=1.2)
        for down in outages:ax.broken_barh([(down['start'],down['end']-down['start'])],(down['machine']-.4,.8),facecolors='none',edgecolors='black',hatch='////',linewidth=.6)
        ax.set_yticks(range(6),[f'M{i+1}' for i in range(6)]);ax.set_title(title,loc='left');ax.grid(axis='x',alpha=.2)
    axs[1].set_xlabel('Benchmark time units · labels: job ID · dashed: failure · dotted: arrival · hatch: downtime');save(fig,'04_dynamic_gantt')
    val=p[p.record_type=='validation'];fig,axs=plt.subplots(1,2,figsize=(178/25.4,78/25.4),layout='constrained')
    for ax,metric,label in zip(axs,['objective_score','makespan'],['Validation (Cmax + mean tardiness) / 100','Validation makespan (time units)']):
        for seed,part in val.groupby('seed'):ax.plot(part.env_steps,part[metric],marker=['o','s','^','D','v'][int(seed)],linestyle=['-','--',':','-.','--'][int(seed)],ms=3,alpha=.7,color=COLORS[int(seed)],label=f'Seed {int(seed)}')
        mean=val.groupby('env_steps')[metric].mean();ax.plot(mean.index,mean.values,'k-s',ms=3,label='Mean across 5 seeds');ax.set_xlabel('Environment steps');ax.set_ylabel(label);ax.grid(alpha=.2)
    fig.legend(*axs[0].get_legend_handles_labels(),loc='outside lower center',ncol=3);save(fig,'05_ppo_validation_raw')
    tests=p[p.record_type=='test'].copy();ppo=tests[tests.method=='MaskablePPO'];ref=tests[(tests.method=='CP-SAT')&(tests.budget_s==5)][['instance','scenario','objective_score']].rename(columns={'objective_score':'cp_score'})
    paired=ppo.merge(ref,on=['instance','scenario'],validate='many_to_one');paired['relative_cost_gap']=(paired.objective_score-paired.cp_score)/paired.cp_score
    paired.to_csv(pp/'ppo_paired_comparison.csv',index=False)
    seed_means=paired.groupby(['scenario','seed']).relative_cost_gap.mean().reset_index();summary=summarize(seed_means,['scenario'],['relative_cost_gap']);summary.to_csv(pp/'ppo_seed_summary.csv',index=False)
    fig,axs=plt.subplots(1,2,figsize=(178/25.4,83/25.4),layout='constrained');groups=['generated_test','external_static','external_dynamic']
    for i,group in enumerate(groups):
        values=seed_means[seed_means.scenario==group].relative_cost_gap*100;mean=values.mean();err=stats.t.ppf(.975,len(values)-1)*values.std()/np.sqrt(len(values))
        axs[0].errorbar(i,mean,yerr=err,fmt='ko',capsize=4);axs[0].scatter(np.full(len(values),i)+np.linspace(-.12,.12,len(values)),values,c=COLORS[:len(values)],s=20)
    axs[0].axhline(0,color='gray',lw=.8);axs[0].set_xticks(range(3),['Generated\ntest','External\nstatic','External\ndynamic']);axs[0].set_ylabel('PPO objective gap to CP-SAT 5s (%)\npoints: training seeds; error: t 95% CI')
    tests['label']=tests.method+tests.apply(lambda r:f' {int(r.budget_s)}s' if r.method=='CP-SAT' else '',axis=1)
    runtimes=tests.groupby('label').runtime_ms.median();axs[1].bar(range(len(runtimes)),runtimes,color=[COLORS[i] for i in range(len(runtimes))]);axs[1].set_yscale('log');axs[1].set_xticks(range(len(runtimes)),runtimes.index,rotation=45,ha='right');axs[1].set_ylabel('Median total episode computation (ms)')
    for ax in axs:ax.grid(axis='y',alpha=.2)
    save(fig,'06_ppo_quality_runtime')
    transfer=paired[paired.scenario=='external_static'].groupby(['instance','seed']).relative_cost_gap.mean().reset_index()
    transfer_summary=summarize(transfer,['instance'],['relative_cost_gap']);transfer_summary.to_csv(pp/'ppo_transfer_summary.csv',index=False)
    fig,ax=plt.subplots(figsize=(178/25.4,78/25.4),layout='constrained')
    for i,name in enumerate(names):
        values=transfer[transfer.instance==name].relative_cost_gap*100
        ax.scatter(np.full(len(values),i)+np.linspace(-.15,.15,len(values)),values,color=COLORS[:len(values)],s=15)
        err=stats.t.ppf(.975,len(values)-1)*values.std()/np.sqrt(len(values))
        ax.errorbar(i,values.mean(),yerr=err,fmt='ko',capsize=3)
    sizes=s.groupby('instance')[['jobs','machines']].first().reindex(names)
    ax.set_xticks(range(len(names)),[f'{name}\n{int(sizes.loc[name,"jobs"])}×{int(sizes.loc[name,"machines"])}' for name in names],rotation=45,ha='right')
    ax.set_ylabel('PPO objective gap to CP-SAT 5s (%)');ax.set_xlabel('External instance / jobs × machines (training: 4–10 jobs, 3–6 machines)');ax.axhline(0,color='gray',lw=.8);ax.grid(axis='y',alpha=.2)
    ax.set_title('Points: 5 training seeds; black: mean and t 95% CI',fontsize=8)
    save(fig,'07_external_scale_transfer')
    aggregate=paired[paired.scenario=='generated_test'].groupby('instance')[['objective_score','cp_score']].mean();diff=aggregate.objective_score-aggregate.cp_score
    statistic=stats.wilcoxon(diff,zero_method='wilcox',alternative='two-sided') if np.any(diff) else None
    stats_out={'generated_test_units':len(aggregate),'test':'exploratory paired Wilcoxon on per-instance mean across PPO seeds vs CP-SAT5s; no confirmatory claim','statistic':None if statistic is None else float(statistic.statistic),'p_value':None if statistic is None else float(statistic.pvalue),'seed_summary':summary.to_dict('records')}
    (pp/'statistical_summary.json').write_text(json.dumps(stats_out,indent=2));(output/'manifest.json').write_text(json.dumps(manifest,indent=2));print(output)
if __name__=='__main__':main()
