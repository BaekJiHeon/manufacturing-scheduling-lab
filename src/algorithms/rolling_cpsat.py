"""Observed-state replanning with frozen execution, normalized costs, and safe fallback.

A breakdown reveals its repair completion estimate at onset (perfect estimate in this
experiment). No future breakdown/arrival is visible. Interrupted work pauses on its
machine and resumes at recovery. Planning freezes simulation time; latency is measured
in wall seconds separately from dimensionless benchmark time.
"""
import copy,time
from ortools.sat.python import cp_model


def key(r):return r['job'],r['operation']

def active_segments(row,outages):
    spans=[(row['start'],row['end'])]
    for down in outages:
        if down['machine']!=row['machine']:continue
        a,b=down['start'],down['end'];new=[]
        for s,e in spans:
            if e<=a or s>=b:new.append((s,e));continue
            if s<a:new.append((s,a))
            if e>b:new.append((b,e))
        spans=new
    return spans


def validate(jobs,machines,rows,releases,outages=(),frozen=()):
    expected={(j,o) for j,job in enumerate(jobs) for o in range(len(job))}
    indexed={key(r):r for r in rows}
    if len(indexed)!=len(rows) or set(indexed)!=expected:raise ValueError('Missing/duplicate operations')
    machine_spans=[[] for _ in range(machines)]
    for (j,o),r in indexed.items():
        m=r['machine'];s=r['start'];e=r['end']
        if any(type(v)!=int for v in [j,o,m,s,e]) or m not in jobs[j][o] or s<releases[j] or e<=s:raise ValueError('Invalid assignment/time/release')
        segments=active_segments(r,outages)
        if r['duration']!=jobs[j][o][m] or sum(b-a for a,b in segments)!=r['duration']:raise ValueError('Processing duration mismatch')
        # Pauses may only occur when an operation already began before breakdown.
        if any(d['machine']==m and d['start']<=s<d['end'] for d in outages):raise ValueError('Starts during downtime')
        if o and s<indexed[j,o-1]['end']:raise ValueError('Precedence violation')
        machine_spans[m].extend(segments)
    for spans in machine_spans:
        spans.sort()
        if any(b>c for (_,b),(c,_) in zip(spans,spans[1:])):raise ValueError('Machine overlap')
    for r in frozen:
        if indexed[key(r)]!=r:raise ValueError('Frozen operation changed')
    return True


def metrics(jobs,machines,rows,due,releases,outages=(),reference=(),frozen=(),weights=(1,0,0)):
    validate(jobs,machines,rows,releases,outages,frozen)
    lookup={key(r):r for r in rows};fixed={key(r) for r in frozen}
    refs=[r for r in reference if key(r) in lookup and key(r) not in fixed]
    completion=[lookup[j,len(job)-1]['end'] for j,job in enumerate(jobs)]
    c=max(completion);t=sum(max(0,cj-d) for cj,d in zip(completion,due));h=sum(max(o.values()) for job in jobs for o in job)
    shift=sum(abs(lookup[key(r)]['start']-r['start']) for r in refs)
    switches=sum(lookup[key(r)]['machine']!=r['machine'] for r in refs)
    stability=shift/(max(1,len(refs))*h)+switches/max(1,len(refs))
    busy=sum(r['duration'] for r in rows);available=machines*c-sum(max(0,min(c,d['end'])-d['start']) for d in outages)
    return dict(makespan=c,total_tardiness=t,mean_tardiness=t/len(jobs),on_time_delivery_rate=sum(cj<=d for cj,d in zip(completion,due))/len(jobs),
      machine_utilization=busy/max(1,available),machine_idle_time=available-busy,constraint_violation_count=0,
      start_shift=shift,machine_changes=switches,reference_operations=len(refs),stability_cost=stability,
      normalized_objective=weights[0]*c/h+weights[1]*t/(len(jobs)*h)+weights[2]*stability,normalization_scale=h)


def greedy(jobs,machines,due,releases,now=0,frozen=(),outages=(),rule='EDD',reference=()):
    rows=copy.deepcopy(list(frozen));lookup={key(r):r for r in rows}
    ready=[now]*machines;job_ready=[max(now,r) for r in releases];next_op=[0]*len(jobs)
    for r in rows:
        ready[r['machine']]=max(ready[r['machine']],r['end']);job_ready[r['job']]=max(job_ready[r['job']],r['end']);next_op[r['job']]+=1
    for d in outages:ready[d['machine']]=max(ready[d['machine']],d['end'])
    refs={key(r):r for r in reference}
    while len(rows)<sum(map(len,jobs)):
        options=[]
        for j,job in enumerate(jobs):
            o=next_op[j]
            if o==len(job):continue
            for m,p in job[o].items():
                s=max(ready[m],job_ready[j]);old=refs.get((j,o))
                priority={'EDD':(due[j],p,j,m),'SPT':(p,due[j],j,m),'MWKR':(-sum(min(x.values()) for x in job[o:]),p,j,m),
                          'FIFO':(j,o,p,m),'Repair':(old['start'] if old else 10**9,0 if old and old['machine']==m else 1,p,j,m)}[rule]
                options.append(((s,*priority),j,o,m,p,s))
        _,j,o,m,p,s=min(options);r=dict(job=j,operation=o,machine=m,start=s,end=s+p,duration=p)
        rows.append(r);next_op[j]+=1;ready[m]=s+p;job_ready[j]=s+p
    validate(jobs,machines,rows,releases,outages,frozen);return rows


def solve(jobs,machines,due,releases=None,now=0,frozen=(),outages=(),reference=(),weights=(1,0,0),budget=1.,seed=0):
    begin=time.perf_counter();releases=list(releases or [0]*len(jobs))
    if budget<=0 or any(type(w)!=int or w<0 for w in weights) or not any(weights):raise ValueError('Positive budget and nonnegative integer weights required')
    # Fallback is generated and scored inside the same wall budget; no invented incumbent.
    candidates=[greedy(jobs,machines,due,releases,now,frozen,outages,r,reference) for r in ['EDD','SPT','MWKR','Repair']]
    fallback=min(candidates,key=lambda rows:metrics(jobs,machines,rows,due,releases,outages,reference,frozen,weights)['normalized_objective'])
    h=sum(max(o.values()) for job in jobs for o in job);n=len(jobs);fixed={key(r):r for r in frozen}
    refs={key(r):r for r in reference if key(r) not in fixed};q=max(1,len(refs))
    horizon=h+max([now,*releases,*[r['end'] for r in frozen],*[d['end'] for d in outages],*[r['start'] for r in reference]])
    model=cp_model.CpModel();starts={};ends={};selectors={};intervals=[[] for _ in range(machines)]
    blocked=[now]*machines
    for d in outages:blocked[d['machine']]=max(blocked[d['machine']],d['end'])
    hint={key(r):r for r in fallback}
    for j,job in enumerate(jobs):
        for o,choices in enumerate(job):
            k=(j,o);r=fixed.get(k)
            if r:
                s=model.new_int_var(r['start'],r['start'],f's{j}_{o}');e=model.new_int_var(r['end'],r['end'],f'e{j}_{o}')
                intervals[r['machine']].append(model.new_interval_var(s,r['end']-r['start'],e,f'fixed{j}_{o}'))
            else:
                s=model.new_int_var(max(now,releases[j]),horizon,f's{j}_{o}');e=model.new_int_var(0,horizon,f'e{j}_{o}');sels=[]
                for m,p in choices.items():
                    x=model.new_bool_var(f'x{j}_{o}_{m}');sels.append(x);selectors[j,o,m]=x
                    intervals[m].append(model.new_optional_interval_var(s,p,e,x,f'i{j}_{o}_{m}'))
                    model.add(s>=blocked[m]).only_enforce_if(x);model.add_hint(x,int(hint[k]['machine']==m))
                model.add_exactly_one(sels);model.add_hint(s,hint[k]['start']);model.add_hint(e,hint[k]['end'])
            starts[k]=s;ends[k]=e
            if o:model.add(s>=ends[j,o-1])
    for ints in intervals:model.add_no_overlap(ints)
    c=model.new_int_var(0,horizon,'C');model.add_max_equality(c,[ends[j,len(job)-1] for j,job in enumerate(jobs)])
    tardies=[]
    for j,job in enumerate(jobs):
        t=model.new_int_var(0,horizon+abs(int(due[j])),'t'+str(j));model.add_max_equality(t,[0,ends[j,len(job)-1]-int(due[j])]);tardies.append(t)
    terms=[weights[0]*n*q*c,weights[1]*q*sum(tardies)]
    for k,r in refs.items():
        delta=model.new_int_var(0,horizon,'delta'+str(k));model.add_abs_equality(delta,starts[k]-r['start'])
        terms.extend([weights[2]*n*delta,weights[2]*n*h*(1-selectors[*k,r['machine']])])
    model.minimize(sum(terms));error=model.validate()
    if error:raise ValueError(error)
    build_ms=(time.perf_counter()-begin)*1000;remaining=budget-(time.perf_counter()-begin)
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.random_seed=seed
    solve_start=time.perf_counter();status='BUDGET_EXHAUSTED';bound=None;candidate=None
    if remaining>0:
        solver.parameters.max_time_in_seconds=remaining;code=solver.solve(model);status=solver.status_name(code)
        if code==cp_model.MODEL_INVALID:raise RuntimeError('Model invalid')
        bound=float(solver.best_objective_bound)/(n*q*h)
        if code in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            candidate=copy.deepcopy(list(frozen))
            for k in starts:
                if k in fixed:continue
                j,o=k;m=next(m for m in jobs[j][o] if solver.boolean_value(selectors[j,o,m]));p=jobs[j][o][m]
                candidate.append(dict(job=j,operation=o,machine=m,start=solver.value(starts[k]),end=solver.value(ends[k]),duration=p))
    solve_ms=(time.perf_counter()-solve_start)*1000
    fm=metrics(jobs,machines,fallback,due,releases,outages,reference,frozen,weights)
    cm=metrics(jobs,machines,candidate,due,releases,outages,reference,frozen,weights) if candidate is not None else None
    use_cp=cm is not None and cm['normalized_objective']<=fm['normalized_objective']+1e-9
    rows=candidate if use_cp else fallback;chosen=cm if use_cp else fm
    modeled_objective=None if cm is None else solver.value(sum(terms))/(n*q*h)
    reported_objective=None if cm is None else solver.objective_value/(n*q*h)
    if cm is not None and abs(cm['normalized_objective']-modeled_objective)>1e-8:
        raise RuntimeError('Independent schedule score differs from model expression')
    response_mismatch=cm is not None and abs(modeled_objective-reported_objective)>1e-8
    raw_status=status
    if response_mismatch and status=='OPTIMAL':status='FEASIBLE_RESPONSE_MISMATCH'
    invalid_bound=bound is not None and bound>chosen['normalized_objective']+1e-8
    if invalid_bound:bound=None
    result=dict(**chosen,schedule=rows,status=status,solution_source='CP-SAT' if use_cp else 'heuristic_fallback',solver_has_incumbent=cm is not None,
      solver_objective=None if cm is None else cm['normalized_objective'],best_bound=bound,relative_bound_gap=None if bound is None else max(0,(chosen['normalized_objective']-bound)/max(1e-12,abs(chosen['normalized_objective']))),
      model_build_ms=build_ms,solver_runtime_ms=solve_ms,budget_s=budget,runtime_ms=(time.perf_counter()-begin)*1000,solver_reported_status=raw_status,solver_reported_objective=reported_objective,model_expression_objective=modeled_objective,solver_response_objective_mismatch=response_mismatch,invalid_bound_discarded=invalid_bound)
    result['budget_overrun_ms']=max(0,result['runtime_ms']-budget*1000)
    return result
