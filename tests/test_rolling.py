import copy
import pytest
from src.algorithms.rolling_cpsat import solve,validate,metrics,active_segments
from src.simulator.rolling import run_rolling


def test_tardiness_optimization_changes_order():
    jobs=[[{0:3}],[{0:1}]]
    r=solve(jobs,1,[10,1],weights=(0,1,0),budget=1)
    assert r['status']=='OPTIMAL' and r['total_tardiness']==0
    assert r['normalized_objective']==pytest.approx(r['best_bound'])


def test_stability_preserves_reference_when_only_cost():
    jobs=[[{0:3,1:3}],[{0:2,1:2}]]
    reference=[dict(job=0,operation=0,machine=0,start=2,end=5,duration=3),dict(job=1,operation=0,machine=1,start=0,end=2,duration=2)]
    r=solve(jobs,2,[5,5],reference=reference,weights=(0,0,1),budget=1)
    assert r['stability_cost']==0 and r['status']=='OPTIMAL'


def test_interrupted_operation_resumes_same_machine():
    jobs=[[{0:10},{0:2}],[{1:7}]]
    tape=[dict(time=3,type='breakdown',machine=0,repair_at=8),dict(time=5,type='arrival',job=[{1:2}],due=12),dict(time=8,type='recovery',machine=0)]
    r=run_rolling(jobs,2,[30,20],tape,'CP-SAT',1,0,(1,1,1))
    row=next(x for x in r['schedule'] if (x['job'],x['operation'])==(0,0))
    assert row['start']==0 and row['end']==15 and row['machine']==0
    assert active_segments(row,r['outages'])==[(0,3),(8,15)]
    assert r['decisions'][1]['observed_job_count']==2 and r['decisions'][2]['observed_job_count']==3
    assert r['constraint_violation_count']==0


def test_future_tape_does_not_change_prefix():
    jobs=[[{0:6}],[{1:3}]]
    a=[dict(time=2,type='breakdown',machine=0,repair_at=4),dict(time=4,type='recovery',machine=0)]
    b=a+[dict(time=5,type='arrival',job=[{1:2}],due=9)]
    x=run_rolling(jobs,2,[10,10],a,'EDD');y=run_rolling(jobs,2,[10,10],b,'EDD')
    assert [d['schedule'] for d in x['decisions']]==[d['schedule'] for d in y['decisions'][:3]]


def test_budget_exhaustion_returns_verified_fallback():
    r=solve([[{0:3}]],1,[5],budget=1e-9)
    assert r['status']=='BUDGET_EXHAUSTED' and r['solution_source']=='heuristic_fallback'
    assert r['best_bound'] is None and not r['solver_has_incumbent'] and r['makespan']==3


def test_validator_detects_release_pause_and_frozen_errors():
    jobs=[[{0:5}]];row=dict(job=0,operation=0,machine=0,start=0,end=5,duration=5)
    with pytest.raises(ValueError):validate(jobs,1,[row],[1])
    with pytest.raises(ValueError):validate(jobs,1,[row],[0],[dict(machine=0,start=2,end=4)])
    other=dict(row,start=1,end=6)
    with pytest.raises(ValueError):validate(jobs,1,[other],[0],frozen=[row])
