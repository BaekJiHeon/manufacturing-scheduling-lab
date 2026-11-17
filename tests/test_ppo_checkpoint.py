import torch
import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv
from src.environments.event_fjsp import EventFJSPEnv
from src.algorithms.ppo_checkpoint import save_checkpoint,load_checkpoint


def test_exact_cpu_resume(tmp_path):
    torch.set_num_threads(1)
    spec=dict(jobs=[[{0:2,1:3},{1:1}],[{0:1},{1:3}]],machines=2,due=[3,5])
    env=DummyVecEnv([lambda:EventFJSPEnv(spec,max_operations=4,max_machines=2)])
    model=MaskablePPO('MultiInputPolicy',env,n_steps=16,batch_size=16,n_epochs=2,gamma=1,seed=12,device='cpu',policy_kwargs=dict(net_arch=[16]))
    model.learn(32);stem=tmp_path/'checkpoint';save_checkpoint(model,stem)
    model.learn(32,reset_num_timesteps=False);expected={k:v.clone() for k,v in model.policy.state_dict().items()}
    resumed=load_checkpoint(stem);assert resumed.num_timesteps==32
    resumed.learn(32,reset_num_timesteps=False)
    for k,v in resumed.policy.state_dict().items():torch.testing.assert_close(v,expected[k],rtol=0,atol=0)
    assert resumed.policy.optimizer.state_dict()['state']
