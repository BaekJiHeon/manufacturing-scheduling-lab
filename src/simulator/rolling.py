"""Exogenous event tapes and event-triggered rolling-horizon execution."""
import copy,time
import numpy as np
from src.algorithms.rolling_cpsat import solve,greedy,metrics,validate,key
from src.run_baselines import simulate,build_due_dates


def scenario_tape(jobs,machines,seed,kind):
    rng=np.random.default_rng(seed);base=simulate(jobs,machines,'SPT')['schedule'];span=max(r['end'] for r in base)
    down=max(1,int(span*.2));duration=max(2,int(span*.15));arrival=down+max(1,int(span*.08))
    active=[r for r in base if r['start']<down<r['end']]
    machine=int(rng.choice([r['machine'] for r in active] or list(range(machines))))
    events=[]
    if kind in ('breakdown','combined'):
        events.extend([dict(time=down,type='breakdown',machine=machine,repair_at=down+duration),dict(time=down+duration,type='recovery',machine=machine)])
    if kind in ('arrival','combined'):
        j=int(rng.integers(len(jobs)));new=copy.deepcopy(jobs[j]);due=arrival+int(np.ceil(sum(min(x.values()) for x in new)*1.7))
        events.append(dict(time=arrival,type='arrival',job=new,due=due))
    return sorted(events,key=lambda e:(e['time'],{'breakdown':0,'recovery':1,'arrival':2}[e['type']]))


def run_rolling(jobs,machines,due,tape,method='CP-SAT',budget=1,seed=0,weights=(1,1,1)):
    jobs=copy.deepcopy(jobs);due=list(map(int,due));releases=[0]*len(jobs);outages=[];plan=[];decisions=[]
    start=time.perf_counter();stability_total=0.;shifts=0;switches=0
    for event in [dict(time=0,type='initial'),*copy.deepcopy(tape)]:
        now=event['time'];reference=copy.deepcopy(plan);frozen=[copy.deepcopy(r) for r in plan if r['start']<now]
        if event['type']=='breakdown':
            d=dict(machine=event['machine'],start=now,end=event['repair_at']);outages.append(d)
            for r in frozen:
                if r['machine']==d['machine'] and r['end']>now:r['end']+=d['end']-now
        elif event['type']=='arrival':
            jobs.append(event['job']);releases.append(now);due.append(event['due'])
        decision_start=time.perf_counter()
        if method=='CP-SAT':r=solve(jobs,machines,due,releases,now,frozen,outages,reference,weights,budget,seed)
        else:
            rows=greedy(jobs,machines,due,releases,now,frozen,outages,method,reference)
            r=dict(**metrics(jobs,machines,rows,due,releases,outages,reference,frozen,weights),schedule=rows,status='FEASIBLE',solution_source=method,runtime_ms=(time.perf_counter()-decision_start)*1000)
        plan=r['schedule'];validate(jobs,machines,plan,releases,outages,frozen)
        stability_total+=r['stability_cost'];shifts+=r['start_shift'];switches+=r['machine_changes']
        decisions.append(dict(event=event,observed_job_count=len(jobs),observed_outages=copy.deepcopy(outages),frozen=frozen,**r))
    final=metrics(jobs,machines,plan,due,releases,outages,weights=weights)
    final.update(schedule=plan,decisions=decisions,events=tape,jobs_spec=jobs,due=due,releases=releases,outages=outages,
      status='FEASIBLE',rescheduling_decisions=len(tape),cumulative_stability_cost=stability_total,cumulative_start_shift=shifts,cumulative_machine_changes=switches,
      mean_replanning_ms=float(np.mean([r['runtime_ms'] for r in decisions[1:]])),max_replanning_ms=max(r['runtime_ms'] for r in decisions[1:]),
      fallback_count=sum(r.get('solution_source')=='heuristic_fallback' for r in decisions),runtime_ms=(time.perf_counter()-start)*1000)
    final['realized_dynamic_cost']=weights[0]*final['makespan']/final['normalization_scale']+weights[1]*final['total_tardiness']/(len(jobs)*final['normalization_scale'])+weights[2]*stability_total
    return final
