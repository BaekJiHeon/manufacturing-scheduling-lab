"""Reproduce supplied metrics and execute a new immutable Phase 1 campaign."""
import argparse, csv, hashlib, importlib.util, json, os, platform, subprocess, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import numpy as np
import psutil
import yaml
from src.run_baselines import parse_fjsp,simulate,build_due_dates
from src.run_cpsat import solve
from src.simulator.problem import verify,scheduling_metrics
ROOT=Path(__file__).resolve().parents[2]
METHODS=('FIFO','SPT','EDD','MWKR','Random')


def write_csv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def audit(out):
    jobs,m=parse_fjsp(ROOT/'data/mk01.txt')
    original=json.loads((ROOT/'results/mk01_results.json').read_text())
    rows=[]; failures=[]
    for result in original['results']:
        verify(jobs,m,result['schedule'])
        new=simulate(jobs,m,result['rule'],seed=42,due=build_due_dates(jobs,42))
        equal=all(new[k]==result[k] for k in ['makespan','total_tardiness','schedule'])
        if not equal:failures.append('single:'+result['rule'])
    old=list(csv.DictReader((ROOT/'results/phase1/repeated_baselines.csv').open()))
    for record in old:
        seed=int(record['scenario_seed']);rule=record['method'];start=time.perf_counter()
        r=simulate(jobs,m,rule,seed=seed,due=build_due_dates(jobs,seed))
        runtime=(time.perf_counter()-start)*1000
        equal=all(r[k]==int(record[k]) for k in ['makespan','total_tardiness'])
        if not equal:failures.append(f'{rule}:{seed}')
        rows.append(dict(scenario_seed=seed,method=rule,makespan=r['makespan'],total_tardiness=r['total_tardiness'],runtime_ms=runtime,legacy_kpis_match=equal))
    write_csv(out/'reproduced_250.csv',rows)
    # Every original summary quality metric is recomputed; timing is machine dependent.
    summary=list(csv.DictReader((ROOT/'results/phase1/summary.csv').open()))
    for item in summary:
        for metric in ['makespan','total_tardiness']:
            a=np.array([r[metric] for r in rows if r['method']==item['method']])
            for key,value in [('mean',a.mean()),('std',a.std(ddof=1)),('median',np.median(a))]:
                if not np.isclose(value,float(item[metric+'_'+key])):failures.append('summary:'+item['method']+metric+key)
    answer=dict(single_schedules_verified=5,repeated_schedules_verified=len(rows),quality_mismatches=failures,
                exact_single_schedule_match=not any(x.startswith('single:') for x in failures),
                runtime_comparison='Not expected to match across hardware or runs',
                dataset_provenance=json.loads((ROOT/'data/raw/provenance.json').read_text()))
    (out/'audit.json').write_text(json.dumps(answer,indent=2))
    if failures:raise RuntimeError(f'Legacy reproduction failed: {failures}')
    return answer


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default='configs/experiments/phase1.yaml');args=p.parse_args()
    config=yaml.safe_load((ROOT/args.config).read_text())
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
    out=ROOT/'results/phase1_cpsat'/run_id;out.mkdir(parents=True)
    metadata=dict(due_date_source='synthetic',run_id=run_id,status='running',created_at=datetime.now(timezone.utc).isoformat(),config=config,
                  python=sys.version,platform=platform.platform(),machine=platform.machine(),
                  cpu= subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip() if sys.platform=='darwin' else platform.processor(),
                  cpu_count=psutil.cpu_count(),ram_bytes=psutil.virtual_memory().total,
                  git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  git_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
                  packages=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines() if __import__('importlib.util').util.find_spec('pip') else {d.metadata['Name']:d.version for d in __import__('importlib.metadata').metadata.distributions()},
                  timing='runtime_ms: parse/build/solve/validation for CP-SAT; dispatch/validation for heuristics; excludes import and file IO',
                  scope='One static MK01. Synthetic due dates seed 42 shared by all primary methods. Solver seeds and dispatch seeds are algorithm randomness, not independent instances.')
    metadata['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').rglob('*.py')) if not p.name.startswith('._')}
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2));(ROOT/'reports/latest_phase01_run.txt').write_text(run_id+'\n')
    begin=time.perf_counter()
    try:
        audit(out)
        jobs,m=parse_fjsp(ROOT/config['dataset']);due=build_due_dates(jobs,config['due_date_seed'],config['due_date_slack'])
        rows=[];schedules=[]
        def add(result,method,seed,limit):
            step=len(rows)
            metrics=scheduling_metrics(jobs,m,result['schedule'],due) if result['schedule'] else {k:None for k in ['makespan','total_tardiness','mean_tardiness','on_time_delivery_rate','machine_utilization','machine_idle_time','constraint_violation_count']}
            rows.append(dict(run_id=run_id,step=step,instance='MK01',method=method,seed=seed,due_seed=config['due_date_seed'],time_limit_s=limit,status=result.get('status','FEASIBLE'),
                             **metrics,runtime_ms=result['runtime_ms'],solver_runtime_ms=result.get('solver_runtime_ms'),model_build_ms=result.get('model_build_ms'),
                             best_bound=result.get('best_bound'),relative_bound_gap=result.get('relative_bound_gap'),
                             bks_gap=(metrics['makespan']-40)/40 if metrics['makespan'] is not None else None))
            for row in result['schedule']:schedules.append(dict(run_id=run_id,step=step,**row))
            (out/f'solution_{step:03}.json').write_text(json.dumps(result,indent=2))
            write_csv(out/'metrics.csv',rows);write_csv(out/'schedules.csv',schedules)
            print(method,seed,result.get('status','FEASIBLE'),metrics['makespan'],round(result['runtime_ms'],3),flush=True)
        for method in METHODS:
            for seed in config['solver_seeds']:
                t=time.perf_counter();r=simulate(jobs,m,method,seed=seed,due=due);r['runtime_ms']=(time.perf_counter()-t)*1000
                add(r,method,seed,0)
        for limit in config['time_limits_s']:
            for seed in config['solver_seeds']:
                r=solve(ROOT/config['dataset'],limit,seed,config['workers'],due=due)
                add(r,f'CP-SAT {limit}s',seed,limit)
        from src.visualization.generate_figures import generate
        figure_start=time.perf_counter();generate(out)
        metadata['figure_generation_s']=time.perf_counter()-figure_start
        metadata.update(status='completed',elapsed_s=time.perf_counter()-begin,rss_bytes_at_completion=psutil.Process().memory_info().rss,records=len(rows))
    except Exception:
        metadata.update(status='failed',error=traceback.format_exc(),elapsed_s=time.perf_counter()-begin)
        (out/'error.txt').write_text(metadata['error']);raise
    finally:
        (out/'metadata.json').write_text(json.dumps(metadata,indent=2))
    print('RUN_ID',run_id,flush=True)
if __name__=='__main__':main()
