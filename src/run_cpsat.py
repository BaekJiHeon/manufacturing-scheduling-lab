"""Static FJSP CP-SAT. Separate model-build, solver, and end-to-end timing."""
import argparse, json, time
from pathlib import Path
try:
    from .simulator.problem import parse_fjsp, verify, scheduling_metrics
    from .run_baselines import build_due_dates
except ImportError:
    from simulator.problem import parse_fjsp, verify, scheduling_metrics
    from run_baselines import build_due_dates
ROOT = Path(__file__).resolve().parents[1]


def solve(path, limit, seed=0, workers=1, due=None):
    from ortools.sat.python import cp_model
    if limit <= 0 or workers < 1:
        raise ValueError('Positive time limit and workers required')
    begin = time.perf_counter()
    jobs,m = parse_fjsp(path)
    # Safe serial schedule upper bound; old code only summed one max per job.
    horizon = sum(max(op.values()) for job in jobs for op in job)
    model=cp_model.CpModel(); intervals=[[] for _ in range(m)]; ends={}; ops={}
    for j,job in enumerate(jobs):
        for o,choices in enumerate(job):
            start=model.new_int_var(0,horizon,f's_{j}_{o}')
            end=model.new_int_var(0,horizon,f'e_{j}_{o}')
            selectors=[]; options=[]
            for machine,p in choices.items():
                sel=model.new_bool_var(f'x_{j}_{o}_{machine}')
                interval=model.new_optional_interval_var(start,p,end,sel,f'i_{j}_{o}_{machine}')
                intervals[machine].append(interval); selectors.append(sel)
                options.append((machine,p,sel,start,end))
            model.add_exactly_one(selectors)
            if o: model.add(start >= ends[j,o-1])
            ends[j,o]=end; ops[j,o]=options
    for machine_intervals in intervals:
        model.add_no_overlap(machine_intervals)
    makespan=model.new_int_var(0,horizon,'makespan')
    model.add_max_equality(makespan,[ends[j,len(job)-1] for j,job in enumerate(jobs)])
    model.minimize(makespan)
    validation=model.validate()
    if validation: raise ValueError(validation)
    solver=cp_model.CpSolver()
    solver.parameters.max_time_in_seconds=limit
    solver.parameters.num_search_workers=workers
    solver.parameters.random_seed=seed
    build_ms=(time.perf_counter()-begin)*1000
    solver_start=time.perf_counter(); status=solver.solve(model)
    solver_ms=(time.perf_counter()-solver_start)*1000
    result=dict(instance=path.stem.upper(),method='CP-SAT',status=solver.status_name(status),
                time_limit_s=limit,solver_seed=seed,workers=workers,model_build_ms=build_ms,
                solver_runtime_ms=solver_ms,solver_wall_time_s=solver.wall_time,
                best_bound=float(solver.best_objective_bound),makespan=None,total_tardiness=None,
                schedule=[],horizon=horizon,branches=solver.num_branches,conflicts=solver.num_conflicts)
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        for (j,o),choices in ops.items():
            for machine,p,sel,start,end in choices:
                if solver.boolean_value(sel):
                    result['schedule'].append(dict(job=j,operation=o,machine=machine,start=solver.value(start),end=solver.value(end),duration=p))
        due = build_due_dates(jobs,42) if due is None else due
        result.update(scheduling_metrics(jobs,m,result['schedule'],due))
        if result['makespan'] != solver.value(makespan): raise RuntimeError('Objective mismatch')
        result['relative_bound_gap']=(result['makespan']-result['best_bound'])/max(1,abs(result['makespan']))
    else:
        result['relative_bound_gap']=None
    result['runtime_ms']=(time.perf_counter()-begin)*1000
    return result


def main():
    from datetime import datetime, timezone
    from uuid import uuid4
    p=argparse.ArgumentParser();p.add_argument('--instance',default='mk01');p.add_argument('--time-limit',type=float,default=30)
    p.add_argument('--seed',type=int,default=0);p.add_argument('--workers',type=int,default=1)
    args=p.parse_args();run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
    out=ROOT/'results'/'phase1_cpsat'/run_id;out.mkdir(parents=True)
    result=solve(ROOT/'data'/f'{args.instance}.txt',args.time_limit,args.seed,args.workers)
    result['run_id']=run_id;(out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='schedule'},indent=2))
if __name__=='__main__':main()
