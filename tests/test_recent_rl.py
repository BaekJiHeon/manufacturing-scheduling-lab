import numpy as np
import pytest
import torch
from src.algorithms.recent_rl import (masked_max,q_lambda_targets,group_advantages,trajectory_objective,MaskedNetwork,flatten,BankEnv,collect_group_batch)
from src.environments.event_fjsp import generated_instance,EventFJSPEnv


def test_illegal_high_q_never_used_for_action_or_bootstrap():
    q=torch.tensor([[1.,1e9,2.]])
    value,action=masked_max(q,torch.tensor([[True,False,True]]))
    assert value.item()==2 and action.item()==2
    target=q_lambda_targets(torch.tensor([[3.]]),torch.tensor([[False]]),value[None])
    assert target.item()==5


def test_q_lambda_terminal_and_multistep_hand_calculation():
    r=torch.tensor([[1.],[2.],[3.]])
    done=torch.tensor([[False],[True],[False]])
    result=q_lambda_targets(r,done,torch.tensor([[10.],[1000.],[4.]]),lam=.5)
    assert torch.allclose(result,torch.tensor([[7.],[2.],[7.]]))


def test_group_normalization_does_not_mix_instances():
    a=group_advantages(torch.tensor([[1.,3.],[100.,102.],[7.,7.]]))
    assert torch.allclose(a,torch.tensor([[-1.,1.],[-1.,1.],[0.,0.]]))


@pytest.mark.parametrize('mode,clip',[('GRPO-Sched',.2),('GSPO-Sched',.0003)])
def test_trajectory_objective_matches_explicit_variable_length_formula(mode,clip):
    new=torch.tensor([[.1,.2,77.],[-.4,.3,.1]],requires_grad=True)
    old=torch.zeros_like(new);valid=torch.tensor([[1.,1.,0.],[1.,1.,1.]])
    adv=torch.tensor([1.,-1.])
    loss,_=trajectory_objective(new,old,valid,adv,mode,clip)
    pieces=[]
    for i,n in enumerate([2,3]):
        ratio=new[i,:n].exp() if mode=='GRPO-Sched' else new[i,:n].mean().exp()
        pieces.append(torch.minimum(ratio*adv[i],ratio.clamp(1-clip,1+clip)*adv[i]).mean())
    expected=-torch.stack(pieces).mean()
    assert torch.allclose(loss,expected)
    loss.backward();assert new.grad[0,2]==0 and torch.isfinite(new.grad).all()


def test_bank_is_disjoint_and_repeatable():
    bank=[2000000,2000001];a=BankEnv(bank);b=BankEnv(bank)
    for _ in range(3):
        x,_=a.reset();y,_=b.reset()
        assert np.array_equal(flatten(x),flatten(y))
    assert a.seen_seeds==[2000000,2000001,2000000]


def test_masked_distribution_and_checkpoint_roundtrip(tmp_path):
    torch.set_num_threads(1);torch.manual_seed(123)
    env=EventFJSPEnv(generated_instance(2000000));obs,_=env.reset();mask=env.action_masks()
    net=MaskedNetwork();dist=net.distribution(torch.from_numpy(flatten(obs))[None],torch.from_numpy(mask)[None])
    assert dist.probs[0,~mask].sum()==0
    path=tmp_path/'weights.pt';torch.save(net.state_dict(),path)
    other=MaskedNetwork();other.load_state_dict(torch.load(path,weights_only=True))
    assert net.predict(obs,mask)==other.predict(obs,mask)


def test_group_budget_exact_and_incomplete_groups_excluded():
    torch.set_num_threads(1);net=MaskedNetwork()
    trajectories,used,unused=collect_group_batch(net,[2000000],4,7)
    assert used==7 and unused==7 and not trajectories
