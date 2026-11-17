"""Masked PQN and trajectory-group objectives adapted to scheduling.

References and intentional departures are in reports/multi_rl_protocol.md.
No claim of reproducing Atari/LLM benchmark results is made.
"""
import copy
import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical
from src.environments.event_fjsp import EventFJSPEnv, generated_instance

KEYS = ('clock', 'machines', 'operations', 'processing_times')


def flatten(obs):
    return np.concatenate([np.asarray(obs[k], dtype=np.float32).ravel() for k in KEYS])


class BankEnv(EventFJSPEnv):
    """Identical finite training bank for all methods, with deterministic cycling."""
    def __init__(self, bank_seeds, offset=0, stride=1):
        super().__init__(generated_instance(bank_seeds[0]))
        self.bank_seeds = list(bank_seeds)
        self.cursor, self.stride = offset, stride
        self.seen_seeds = []

    def reset(self, **kwargs):
        seed = self.bank_seeds[self.cursor % len(self.bank_seeds)]
        self.cursor += self.stride
        self.seen_seeds.append(seed)
        self.initial = generated_instance(seed)
        return super().reset(**kwargs)


class MaskedNetwork(nn.Module):
    def __init__(self, input_size=6301, actions=3901, q_network=False):
        super().__init__()
        self.input_size, self.actions, self.q_network = input_size, actions, q_network
        layers = []
        for before, after in [(input_size, 128), (128, 128)]:
            layer = nn.Linear(before, after)
            nn.init.orthogonal_(layer.weight, np.sqrt(2)); nn.init.zeros_(layer.bias)
            layers.append(layer)
            if q_network: layers.append(nn.LayerNorm(after))
            layers.append(nn.ReLU() if q_network else nn.Tanh())
        head = nn.Linear(128, actions)
        nn.init.orthogonal_(head.weight, 1.0 if q_network else .01); nn.init.zeros_(head.bias)
        self.network = nn.Sequential(*layers, head)

    def forward(self, x):
        return self.network(x)

    def distribution(self, x, mask):
        if not torch.all(mask.any(-1)): raise ValueError('No feasible action')
        return Categorical(logits=self(x).masked_fill(~mask, -1e8))

    def predict(self, obs, action_masks, deterministic=True):
        with torch.no_grad():
            x = torch.from_numpy(flatten(obs)).unsqueeze(0)
            mask = torch.as_tensor(action_masks, dtype=torch.bool).unsqueeze(0)
            if deterministic: action = masked_max(self(x), mask)[1]
            else: action = self.distribution(x, mask).sample()
        return int(action.item()), None


def masked_max(q, mask):
    if not torch.all(mask.any(-1)): raise ValueError('No feasible action')
    return q.masked_fill(~mask, -torch.inf).max(-1)


def q_lambda_targets(rewards, dones, next_values, gamma=1., lam=.65):
    """Next values are masked max Q(s[t+1]); terminal bootstrap is zero."""
    result = torch.empty_like(rewards)
    carry = next_values[-1]
    for t in reversed(range(len(rewards))):
        bootstrap = next_values[t] if t == len(rewards)-1 else (1-lam)*next_values[t] + lam*carry
        carry = rewards[t] + gamma*(~dones[t]).to(rewards.dtype)*bootstrap
        result[t] = carry
    return result


def group_advantages(returns):
    """Population standard deviation; each row contains one same-instance group."""
    centered = returns - returns.mean(-1, keepdim=True)
    return centered / returns.std(-1, keepdim=True, unbiased=False).clamp_min(1e-8)


def trajectory_objective(new_logp, old_logp, valid, advantages, mode, clip):
    """Equal weight per complete trajectory, including when lengths differ."""
    lengths = valid.sum(-1).clamp_min(1)
    log_ratio = (new_logp - old_logp) * valid
    if mode == 'GRPO-Sched':
        ratio = log_ratio.exp()
        a = advantages[:, None]
        surrogate = torch.minimum(ratio*a, ratio.clamp(1-clip, 1+clip)*a)
        objective = ((surrogate*valid).sum(-1)/lengths).mean()
        clip_fraction = (((ratio-1).abs()>clip)*valid).sum()/valid.sum()
    elif mode == 'GSPO-Sched':
        ratio = (log_ratio.sum(-1)/lengths).exp()
        objective = torch.minimum(ratio*advantages, ratio.clamp(1-clip, 1+clip)*advantages).mean()
        clip_fraction = ((ratio-1).abs()>clip).float().mean()
    else: raise ValueError(mode)
    return -objective, clip_fraction


def train_pqn(model, cfg, bank, hook):
    envs = [BankEnv(bank, i, cfg['n_envs']) for i in range(cfg['n_envs'])]
    obs = [e.reset()[0] for e in envs]
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg['pqn_lr'], eps=1e-5)
    steps = 0; update = 0
    while steps < cfg['total_steps_per_seed']:
        xs=[]; acts=[]; rewards=[]; dones=[]; maxqs=[]; completed=[]
        for _ in range(cfg['pqn_rollout_steps']):
            x=torch.from_numpy(np.stack([flatten(o) for o in obs]))
            mask=torch.from_numpy(np.stack([e.action_masks() for e in envs]))
            epsilon=max(.05, 1-.95*steps/(cfg['total_steps_per_seed']*.5))
            with torch.no_grad():
                maximum, greedy=masked_max(model(x), mask)
                random_action=torch.multinomial(mask.float(),1).squeeze(-1)
                actions=torch.where(torch.rand(len(envs))<epsilon,random_action,greedy)
            rs=[]; ds=[]
            for i,(e,a) in enumerate(zip(envs,actions)):
                o,r,done,_,info=e.step(int(a));rs.append(r);ds.append(done)
                if done:
                    completed.append(-(info['makespan']+info['mean_tardiness'])/100)
                    o=e.reset()[0]
                obs[i]=o
            xs.append(x);acts.append(actions);rewards.append(rs);dones.append(ds);maxqs.append(maximum)
            steps+=len(envs)
        with torch.no_grad():
            last=masked_max(model(torch.from_numpy(np.stack([flatten(o) for o in obs]))),torch.from_numpy(np.stack([e.action_masks() for e in envs])))[0]
            next_values=torch.stack(maxqs[1:]+[last])
            targets=q_lambda_targets(torch.tensor(rewards),torch.tensor(dones),next_values,lam=cfg['q_lambda']).flatten()
        x=torch.stack(xs).flatten(0,1); actions=torch.stack(acts).flatten()
        losses=[]; norms=[]
        optimizer.param_groups[0]['lr']=cfg['pqn_lr']*(1-(steps-len(x))/cfg['total_steps_per_seed'])
        for _ in range(cfg['n_epochs']):
            for ids in torch.randperm(len(x)).split(cfg['batch_size']):
                selected=model(x[ids]).gather(1,actions[ids,None]).squeeze(-1)
                loss=(selected-targets[ids]).square().mean()
                if not torch.isfinite(loss): raise FloatingPointError('PQN loss')
                optimizer.zero_grad();loss.backward()
                norms.append(float(nn.utils.clip_grad_norm_(model.parameters(),10.)))
                optimizer.step();losses.append(float(loss.detach()))
        update+=1
        hook(steps,dict(train_td_loss=float(np.mean(losses)),gradient_norm_before_clip=float(np.mean(norms)),epsilon=epsilon,optimizer_updates=update*cfg['n_epochs']*len(x)//cfg['batch_size'],train_episode_return=float(np.mean(completed)) if completed else None))
    return dict(optimizer=optimizer.state_dict(),training_seeds=[e.seen_seeds for e in envs],unused_transitions=0)


def collect_group_batch(model, bank_seeds, group_size, budget):
    envs=[EventFJSPEnv(generated_instance(seed)) for seed in bank_seeds for _ in range(group_size)]
    observations=[e.reset()[0] for e in envs]
    trajectories=[dict(x=[],mask=[],action=[],old_logp=[],return_value=0.) for _ in envs]
    active=list(range(len(envs)));used=0
    while active and used<budget:
        selected=active[:budget-used]
        x=torch.from_numpy(np.stack([flatten(observations[i]) for i in selected]))
        mask=torch.from_numpy(np.stack([envs[i].action_masks() for i in selected]))
        with torch.no_grad():
            dist=model.distribution(x,mask);actions=dist.sample();old=dist.log_prob(actions)
        for k,i in enumerate(selected):
            tr=trajectories[i];tr['x'].append(x[k]);tr['mask'].append(mask[k]);tr['action'].append(actions[k]);tr['old_logp'].append(old[k])
            observations[i],r,done,_,info=envs[i].step(int(actions[k]));tr['return_value']+=r
            if done:
                assert abs(tr['return_value']+(info['makespan']+info['mean_tardiness'])/100)<1e-5
        used+=len(selected);active=[i for i in active if not envs[i].done]
    complete=[]
    for start in range(0,len(envs),group_size):
        if all(e.done for e in envs[start:start+group_size]):complete.extend(trajectories[start:start+group_size])
    return complete,used,used-sum(len(t['action']) for t in complete)


def train_group(model, mode, cfg, bank, hook):
    optimizer=torch.optim.Adam(model.parameters(),lr=cfg['learning_rate'],eps=1e-5)
    steps=0;cursor=0;unused=0;updates=0;seen=[]
    clip=cfg['grpo_clip'] if mode=='GRPO-Sched' else cfg['gspo_clip']
    while steps<cfg['total_steps_per_seed']:
        seeds=[bank[(cursor+i)%len(bank)] for i in range(cfg['prompt_batch'])]
        cursor+=len(seeds);seen.extend(seeds)
        trajectories,used,discarded=collect_group_batch(model,seeds,cfg['group_size'],cfg['total_steps_per_seed']-steps)
        steps+=used;unused+=discarded
        if not trajectories:
            hook(steps,dict(unused_transitions=unused));break
        returns=torch.tensor([t['return_value'] for t in trajectories])
        advantages=group_advantages(returns.reshape(-1,cfg['group_size'])).flatten()
        losses=[];fractions=[];norms=[];entropies=[]
        for _ in range(cfg['n_epochs']):
            for ids in torch.randperm(len(trajectories)).split(cfg['trajectory_minibatch']):
                ts=[trajectories[int(i)] for i in ids];lengths=[len(t['action']) for t in ts]
                x=torch.cat([torch.stack(t['x']) for t in ts]);masks=torch.cat([torch.stack(t['mask']) for t in ts])
                actions=torch.cat([torch.stack(t['action']) for t in ts]);old=torch.cat([torch.stack(t['old_logp']) for t in ts])
                dist=model.distribution(x,masks);logp=dist.log_prob(actions)
                pad=lambda v:nn.utils.rnn.pad_sequence(v.split(lengths),batch_first=True)
                valid=pad(torch.ones_like(old));newp=pad(logp);oldp=pad(old)
                pg,fraction=trajectory_objective(newp,oldp,valid,advantages[ids],mode,clip)
                entropy=torch.stack([e.mean() for e in dist.entropy().split(lengths)]).mean()
                loss=pg-cfg['ent_coef']*entropy
                if not torch.isfinite(loss):raise FloatingPointError(mode+' loss')
                optimizer.zero_grad();loss.backward();norm=nn.utils.clip_grad_norm_(model.parameters(),cfg['max_grad_norm']);optimizer.step();updates+=1
                losses.append(float(pg.detach()));fractions.append(float(fraction.detach()));norms.append(float(norm));entropies.append(float(entropy.detach()))
        hook(steps,dict(train_policy_gradient_loss=float(np.mean(losses)),train_entropy_loss=-float(np.mean(entropies)),train_clip_fraction=float(np.mean(fractions)),gradient_norm_before_clip=float(np.mean(norms)),optimizer_updates=updates,train_episode_return=float(returns.mean()),zero_variance_groups=int((returns.reshape(-1,cfg['group_size']).std(-1,unbiased=False)<1e-8).sum()),unused_transitions=unused))
    return dict(optimizer=optimizer.state_dict(),training_seeds=seen,unused_transitions=unused)
