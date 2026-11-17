import numpy as np
import pytest
from src.environments.event_fjsp import EventFJSPEnv,generated_instance
from src.algorithms.rolling_cpsat import validate


def test_wait_is_positive_and_allows_intentional_idling():
    spec=dict(jobs=[[{0:5}],[{1:2}],[{0:1,1:1}]],machines=2,due=[10]*3)
    env=EventFJSPEnv(spec,max_operations=3,max_machines=2);env.reset()
    assert not env.action_masks()[-1]
    env.step(0);assert env.now==0 and env.action_masks()[-1]
    env.step(env.wait_action);assert env.now==5


def test_future_jobs_are_absent_in_state_and_mask():
    spec=dict(jobs=[[{0:8}]],machines=2,due=[20])
    a=EventFJSPEnv(spec);b=EventFJSPEnv(dict(spec,tape=[dict(time=2,type='arrival',job=[{1:3}],due=7)]))
    oa,_=a.reset();ob,_=b.reset()
    for k in oa:np.testing.assert_array_equal(oa[k],ob[k])
    np.testing.assert_array_equal(a.action_masks(),b.action_masks())
    b.step(0);assert b.now==2 and len(b.jobs)==2 and b.action_masks()[16]


def test_random_dynamic_rollouts_reward_and_feasibility():
    for seed in range(20):
        spec=generated_instance(seed);env=EventFJSPEnv(spec);env.reset();rng=np.random.default_rng(seed);steps=0;total=0
        while not env.done:
            acts=np.flatnonzero(env.action_masks());assert len(acts)
            _,r,_,_,info=env.step(int(rng.choice(acts)));steps+=1;total+=r
            assert steps<2000
        assert total==pytest.approx(-(info['makespan']+info['mean_tardiness'])/100)
        validate(env.jobs,env.m,env.rows,env.releases,env.outages)


def test_idle_after_completion_does_not_change_makespan_reward():
    spec=dict(jobs=[[{0:1}]],machines=2,due=[10],tape=[dict(time=2,type='breakdown',machine=1,repair_at=5),dict(time=5,type='recovery',machine=1)])
    env=EventFJSPEnv(spec);env.reset();_,r,done,_,info=env.step(0)
    assert done and env.now==5 and info['makespan']==1 and r==pytest.approx(-.01)


def test_evaluation_results_are_json_serializable():
    import json
    from src.evaluation.run_ppo_pilot import evaluate
    result=evaluate(generated_instance(9100001),rule='SPT')
    json.dumps(result)
    assert type(result['wait_count']) is int
