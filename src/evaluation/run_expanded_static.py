import json,time,os
from src.evaluation.campaign import Campaign,ROOT,instance_path,bks
from src.simulator.problem import parse_fjsp,scheduling_metrics
from src.run_baselines import simulate,build_due_dates
from src.run_cpsat import solve

def main():
    config=json.loads((ROOT/'configs/experiments/expanded_static.json').read_text());run=Campaign('expanded_static',config,os.getenv('RESUME_RUN_ID'));known=bks()
    (ROOT/'reports/latest_expanded_static_run.txt').write_text(run.run_id+'\n')
    try:
        for name in config['instances']:
            path=instance_path(name);jobs,m=parse_fjsp(path);due=build_due_dates(jobs,config['due_seed']);ub=known[name]['upper_bound']
            common=dict(instance=name,jobs=len(jobs),machines=m,operations=sum(map(len,jobs)),due=list(map(int,due)),bks_lower=known[name]['lower_bound'],bks_upper=ub,objective='makespan',scenario='static')
            for seed in config['seeds']:
                for rule in ['FIFO','SPT','EDD','MWKR','Random']:
                    if any(r['instance']==name and r['method']==rule and r['seed']==seed for r in run.records):continue
                    t=time.perf_counter();r=simulate(jobs,m,rule,seed,due);metrics=scheduling_metrics(jobs,m,r['schedule'],due)
                    run.add(dict(**common,method=rule,seed=seed,status='FEASIBLE',runtime_ms=(time.perf_counter()-t)*1000,**metrics,schedule=r['schedule'],bks_gap=(metrics['makespan']-ub)/ub))
                for limit in config['limits_s']:
                    if any(r['instance']==name and r['method']=='CP-SAT' and r['seed']==seed and r.get('time_limit_s')==limit for r in run.records):continue
                    r=solve(path,limit,seed,1,due);r.pop('instance');r.pop('method');r['bks_gap']=None if r['makespan'] is None else (r['makespan']-ub)/ub
                    run.add(dict(**common,method='CP-SAT',seed=seed,**r))
    except Exception as e:run.finish(e);raise
    run.finish()
if __name__=='__main__':main()
