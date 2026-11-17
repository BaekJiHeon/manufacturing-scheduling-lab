from pathlib import Path
import copy
import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env
from src.simulator.problem import parse_fjsp, verify
from src.run_baselines import simulate, build_due_dates
from src.run_cpsat import solve
from src.environments.static_fjsp import StaticFJSPEnv
ROOT=Path(__file__).resolve().parents[1]


def test_dataset():
    jobs,m=parse_fjsp(ROOT/'data/raw/mk01.txt')
    assert (len(jobs),m,sum(map(len,jobs)))==(10,6,55)
    assert (jobs,m)==parse_fjsp(ROOT/'data/mk01.txt')


@pytest.mark.parametrize('content', ['1 1 1\n1 0\n','1 1 1\n1 1 1 0\n','1 1 1\n1 2 1 1 1 2\n','1 1 1\n1 1 1\n','1 1 1\n1 1 1 2 99\n'])
def test_bad_parser(tmp_path,content):
    p=tmp_path/'bad.txt';p.write_text(content)
    with pytest.raises(ValueError):parse_fjsp(p)


def test_fractional_flexibility(tmp_path):
    p=tmp_path/'ok.txt';p.write_text('1 2 1.5\n1 2 1 2 2 3\n')
    assert parse_fjsp(p)==([[{0:2,1:3}]],2)


def test_validator_mutations():
    jobs=[[{0:2},{1:3}],[{0:1}]]
    rows=[dict(job=0,operation=0,machine=0,start=0,end=2,duration=2),
          dict(job=0,operation=1,machine=1,start=2,end=5,duration=3),
          dict(job=1,operation=0,machine=0,start=2,end=3,duration=1)]
    assert verify(jobs,2,rows)
    mutations=[(0,{'end':1}),(0,{'job':-1}),(0,{'machine':-1}),(0,{'machine':1}),
               (0,{'start':float('nan')}),(1,{'start':1,'end':4}),(2,{'start':1,'end':2}),
               (2,{'job':0,'operation':0})]
    for idx,change in mutations:
        bad=copy.deepcopy(rows);bad[idx].update(change)
        with pytest.raises(ValueError):verify(jobs,2,bad)
    with pytest.raises(ValueError):verify(jobs,2,rows[:-1])


def test_horizon_regression(tmp_path):
    p=tmp_path/'chain.txt';p.write_text('1 1 1\n3 1 1 10 1 1 10 1 1 10\n')
    result=solve(p,1)
    assert result['status']=='OPTIMAL' and result['makespan']==30 and result['best_bound']==30


def test_alternative_machine_optimum(tmp_path):
    p=tmp_path/'tiny.txt';p.write_text('2 2 2\n1 2 1 4 2 2\n1 2 1 3 2 5\n')
    result=solve(p,1)
    assert result['status']=='OPTIMAL' and result['makespan']==3


def test_unknown_does_not_fabricate_incumbent():
    result=solve(ROOT/'data/mk01.txt',1e-9)
    assert result['status']=='UNKNOWN' and result['makespan'] is None and result['schedule']==[]
    assert result['best_bound'] is not None


def test_masked_env():
    jobs,m=parse_fjsp(ROOT/'data/mk01.txt')
    for seed in range(20):
        env=StaticFJSPEnv(jobs,m,makespan_weight=.5,tardiness_weight=.5)
        obs,_=env.reset(seed=seed);rng=np.random.default_rng(seed);total=0
        assert env.observation_space.contains(obs)
        invalid=np.flatnonzero(~env.action_masks())[0]
        with pytest.raises(ValueError):env.step(int(invalid))
        for step in range(55):
            mask=env.action_masks();assert mask.any()
            obs,reward,done,truncated,info=env.step(int(rng.choice(np.flatnonzero(mask))))
            assert env.observation_space.contains(obs)
            assert not truncated
            total+=reward
            if done:break
        assert done and step==54 and not env.action_masks().any()
        assert total==pytest.approx(-(.5*info['makespan']+.5*info['total_tardiness'])/env.scale)
        assert verify(jobs,m,info['schedule'])


def test_zero_time_actions_not_double_penalized():
    env=StaticFJSPEnv([[{0:2}],[{1:3}]],2)
    _,r,done,_,_=env.step(0)
    assert r==0 and not done
    _,r,done,_,info=env.step(3)
    assert done and r==-3/5 and info['makespan']==3


def test_padded_variable_instances():
    a=StaticFJSPEnv([[{0:1}]],1,max_operations=3,max_machines=2)
    b=StaticFJSPEnv([[{0:2}],[{1:3}]],2,max_operations=3,max_machines=2)
    assert a.observation_space==b.observation_space and a.action_space==b.action_space
    assert np.flatnonzero(a.action_masks()).tolist()==[0]


def test_gymnasium_contract():
    # Generic checker samples unmasked actions: use all-valid one-step fixture.
    env=StaticFJSPEnv([[{0:2,1:3}]],2)
    check_env(env,skip_render_check=True)


@pytest.mark.parametrize('rule',['FIFO','SPT','EDD','MWKR','Random'])
def test_baseline(rule):
    jobs,m=parse_fjsp(ROOT/'data/mk01.txt')
    r=simulate(jobs,m,rule,seed=42,due=build_due_dates(jobs,42))
    assert verify(jobs,m,r['schedule'])


def test_campaign_records_figure_failure(tmp_path,monkeypatch):
    import json,sys,yaml
    from src.evaluation import run_phase01
    from src.visualization import generate_figures
    (tmp_path/'reports').mkdir()
    (tmp_path/'data').mkdir()
    (tmp_path/'data/mk01.txt').write_bytes((ROOT/'data/mk01.txt').read_bytes())
    (tmp_path/'config.yaml').write_text(yaml.safe_dump(dict(dataset='data/mk01.txt',solver_seeds=[0],time_limits_s=[],workers=1,due_date_seed=42,due_date_slack=1.7)))
    monkeypatch.setattr(run_phase01,'ROOT',tmp_path)
    monkeypatch.setattr(run_phase01,'audit',lambda out:None)
    monkeypatch.setattr(sys,'argv',['run_phase01','--config','config.yaml'])
    original=run_phase01.subprocess.check_output
    def command(args,**kwargs):
        if args[:2]==['git','rev-parse']:return 'test-source-commit\n'
        if args[:2]==['git','status']:return ''
        return original(args,**kwargs)
    monkeypatch.setattr(run_phase01.subprocess,'check_output',command)
    def fail(_):raise RuntimeError('injected figure write failure')
    monkeypatch.setattr(generate_figures,'generate',fail)
    with pytest.raises(RuntimeError,match='injected figure'):
        run_phase01.main()
    run=next((tmp_path/'results/phase1_cpsat').iterdir())
    assert json.loads((run/'metadata.json').read_text())['status']=='failed'
    assert 'injected figure write failure' in (run/'error.txt').read_text()
