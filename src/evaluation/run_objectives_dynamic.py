import json,os
from src.evaluation.campaign import Campaign,ROOT,instance_path
from src.simulator.problem import parse_fjsp
from src.run_baselines import simulate,build_due_dates
from src.algorithms.rolling_cpsat import solve
from src.simulator.rolling import scenario_tape,run_rolling


def main():
    cfg=json.loads((ROOT/'configs/experiments/objectives_dynamic.json').read_text());run=Campaign('objectives_dynamic',cfg,os.getenv('RESUME_RUN_ID'))
    (ROOT/'reports/latest_objectives_dynamic_run.txt').write_text(run.run_id+'\n')
    try:
        for name in cfg['objective_instances']:
            jobs,m=parse_fjsp(instance_path(name));due=list(map(int,build_due_dates(jobs,cfg['due_seed'])));ref=simulate(jobs,m,'SPT',due=due)['schedule']
            for obj,weights in cfg['weights'].items():
                for seed in cfg['seeds']:
                    for budget in cfg['objective_limits_s']:
                        if any(r['instance']==name and r['scenario']=='static_objective' and r['objective']==obj and r['seed']==seed and r['budget_s']==budget for r in run.records):continue
                        r=solve(jobs,m,due,reference=ref,weights=weights,budget=budget,seed=seed)
                        run.add(dict(instance=name,method='CP-SAT',objective=obj,scenario='static_objective',seed=seed,due=due,weights=weights,reference=ref,**r))
        for name in cfg['dynamic_instances']:
            jobs,m=parse_fjsp(instance_path(name));due=list(map(int,build_due_dates(jobs,cfg['due_seed'])))
            for seed in cfg['seeds']:
                for kind in cfg['scenarios']:
                    tape=scenario_tape(jobs,m,seed,kind)
                    tape_path=ROOT/'data/generated_scenarios'/f'{run.run_id}_{name}_{kind}_{seed}.json';tape_path.write_text(json.dumps(tape,indent=2))
                    for method in ['Repair','SPT','EDD','MWKR','CP-SAT']:
                        for budget in cfg['dynamic_limits_s'] if method=='CP-SAT' else [0]:
                            for obj in ['balanced','stable'] if method=='CP-SAT' else ['stable']:
                                if any(r['instance']==name and r['scenario']==kind and r['objective']==obj and r['seed']==seed and r['budget_s']==budget and r['method']==method for r in run.records):continue
                                r=run_rolling(jobs,m,due,tape,method,budget,seed,cfg['weights'][obj])
                                run.add(dict(instance=name,method=method,objective=obj,scenario=kind,seed=seed,budget_s=budget,weights=cfg['weights'][obj],**r))
    except Exception as e:run.finish(e);raise
    run.finish()
if __name__=='__main__':main()
