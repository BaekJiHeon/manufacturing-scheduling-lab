"""Local trusted checkpoints: SB3 optimizer plus simulator and RNG state."""
import pickle,random
import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv


def save_checkpoint(model,stem):
    model.save(str(stem))
    state=dict(python_rng=random.getstate(),numpy_rng=np.random.get_state(),torch_rng=torch.get_rng_state(),
      envs=model.get_env().envs,last_obs=model._last_obs,last_episode_starts=model._last_episode_starts)
    with open(str(stem)+'.state.pkl','wb') as f:pickle.dump(state,f)


def load_checkpoint(stem,device='cpu'):
    # Load only our own trusted local pickle; never untrusted downloaded checkpoints.
    with open(str(stem)+'.state.pkl','rb') as f:state=pickle.load(f)
    vec=DummyVecEnv([lambda e=e:e for e in state['envs']]);model=MaskablePPO.load(str(stem),env=vec,device=device,force_reset=False)
    model._last_obs=state['last_obs'];model._last_episode_starts=state['last_episode_starts']
    random.setstate(state['python_rng']);np.random.set_state(state['numpy_rng']);torch.set_rng_state(state['torch_rng'])
    return model
