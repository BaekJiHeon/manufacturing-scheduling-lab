"""Predeclared four-method masked RL comparison; resumable between complete seeds."""
import hashlib,json,os,random,time
from pathlib import Path
import numpy as np
import psutil
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv
from src.algorithms.recent_rl import BankEnv,MaskedNetwork,train_pqn,train_group,flatten
from src.algorithms.ppo_checkpoint import save_checkpoint
from src.evaluation.campaign import ROOT,Campaign,instance_path
from src.evaluation.run_ppo_pilot import evaluate
from src.environments.event_fjsp import generated_instance
from src.algorithms.rolling_cpsat import solve
from src.simulator.rolling import run_rolling,scenario_tape
from src.simulator.problem import parse_fjsp
from src.run_baselines import build_due_dates


def specs_for(cfg):
    specs=[(f'GEN{i}',generated_instance(i),'fresh_generated_test') for i in cfg['test_seeds']]
    for name in [f'MK{i:02d}' for i in range(1,11)]:
        jobs,m=parse_fjsp(instance_path(name));due=list(map(int,build_due_dates(jobs,42)))
        specs.append((name,dict(jobs=jobs,machines=m,due=due,tape=[]),'external_static'))
    for name in ['MK01','MK06']:
        jobs,m=parse_fjsp(instance_path(name));due=list(map(int,build_due_dates(jobs,42)))
        for seed in [0,1,2]:
            specs.append((name+f'_event{seed}',dict(jobs=jobs,machines=m,due=due,tape=scenario_tape(jobs,m,seed,'combined')),'external_dynamic'))
    return specs


class Recorder:
    def __init__(self,run,method,seed,cfg,model):
        self.run,self.method,self.seed,self.cfg,self.model=run,method,seed,cfg,model
        self.start=time.perf_counter();self.last_log=0;self.next_val=cfg['evaluation_interval'];self.last_val=-1

    def validate(self,steps):
        results=[evaluate(generated_instance(i),self.model) for i in self.cfg['validation_seeds']]
        self.run.add(dict(record_type='validation',instance='generated_validation',scenario='mixed',method=self.method,seed=self.seed,env_steps=steps,
            **{k:float(np.mean([r[k] for r in results])) for k in ['objective_score','makespan','total_tardiness','episode_return']}))
        self.last_val=steps

    def __call__(self,steps,metrics):
        final=steps==self.cfg['total_steps_per_seed']
        if steps-self.last_log>=self.cfg['log_interval'] or final:
            elapsed=time.perf_counter()-self.start
            self.run.add(dict(record_type='training',instance='generated_train',scenario='mixed',method=self.method,seed=self.seed,env_steps=steps,
                elapsed_s=elapsed,training_steps_per_second=steps/elapsed,ram_mb=psutil.Process().memory_info().rss/2**20,**metrics))
            self.last_log=steps
        if steps>=self.next_val or (final and self.last_val!=steps):
            self.validate(steps)
            while self.next_val<=steps:self.next_val+=self.cfg['evaluation_interval']


class PPORecorder(BaseCallback):
    def __init__(self,recorder):
        super().__init__();self.recorder=recorder;self.last=0;self.returns=[]
    def _on_step(self):
        for done,info in zip(self.locals['dones'],self.locals['infos']):
            if done:self.returns.append(-(info['makespan']+info['mean_tardiness'])/100)
        return True
    def record(self):
        step=self.model.num_timesteps
        if not step or step==self.last:return
        self.last=step
        values={k.replace('/','_'):float(v) for k,v in self.model.logger.name_to_value.items() if k.startswith('train/') and isinstance(v,(float,int,np.floating))}
        if self.returns:values['train_episode_return']=float(np.mean(self.returns))
        self.recorder(step,values);self.returns.clear()
    def _on_rollout_start(self):self.record()
    def _on_training_end(self):self.record()


def load_model(method,path):
    if method=='MaskablePPO':return MaskablePPO.load(str(path),device='cpu')
    state=torch.load(path,map_location='cpu',weights_only=False)
    model=MaskedNetwork(**state['network_config']);model.load_state_dict(state['model']);model.eval();return model


def main():
    cfg=json.loads((ROOT/'configs/algorithms/multi_rl.json').read_text())
    torch.set_num_threads(cfg['torch_threads'])
    run=Campaign('multi_rl',cfg,os.getenv('RESUME_RUN_ID'))
    (ROOT/'reports/latest_multi_rl_run.txt').write_text(run.run_id+'\n')
    folder=ROOT/'checkpoints'/run.run_id;folder.mkdir(parents=True,exist_ok=True)
    specs=specs_for(cfg)
    (run.path/'evaluation_instances.json').write_text(json.dumps([dict(instance=n,scenario=g,spec=s) for n,s,g in specs],indent=2))
    (run.path/'protocol.md').write_text((ROOT/'reports/multi_rl_protocol.md').read_text())
    models=[]
    try:
        for method in cfg['methods']:
            for seed in cfg['seeds']:
                bank=list(range(cfg['training_seed_base']+seed*1000,cfg['training_seed_base']+seed*1000+cfg['training_bank_size']))
                stem=folder/f'{method}_seed{seed}_final';path=stem.with_suffix('.zip' if method=='MaskablePPO' else '.pt')
                summary=next((r for r in run.records if r.get('record_type')=='training_summary' and r['method']==method and r['seed']==seed),None)
                if summary:
                    assert hashlib.sha256(path.read_bytes()).hexdigest()==summary['checkpoint_sha256']
                    models.append((method,seed,path));continue
                random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
                env=None
                if method=='MaskablePPO':
                    env=DummyVecEnv([lambda i=i:BankEnv(bank,i,cfg['n_envs']) for i in range(cfg['n_envs'])])
                    model=MaskablePPO('MultiInputPolicy',env,seed=seed,device='cpu',policy_kwargs=dict(net_arch=cfg['net_arch']),**{k:cfg[k] for k in ['n_steps','batch_size','n_epochs','learning_rate','gamma','gae_lambda','ent_coef','max_grad_norm']})
                    parameters=sum(p.numel() for p in model.policy.parameters())
                else:
                    model=MaskedNetwork(q_network=method=='MaskedPQN');parameters=sum(p.numel() for p in model.parameters())
                recorder=Recorder(run,method,seed,cfg,model);recorder.validate(0);start=time.perf_counter()
                if method=='MaskablePPO':
                    model.learn(cfg['total_steps_per_seed'],callback=PPORecorder(recorder));save_checkpoint(model,stem)
                    state=dict(training_seeds=[e.seen_seeds for e in env.envs],unused_transitions=0)
                else:
                    state=(train_pqn(model,cfg,bank,recorder) if method=='MaskedPQN' else train_group(model,method,cfg,bank,recorder))
                    torch.save(dict(model=model.state_dict(),optimizer=state['optimizer'],network_config=dict(input_size=model.input_size,actions=model.actions,q_network=model.q_network),python_rng=random.getstate(),numpy_rng=np.random.get_state(),torch_rng=torch.get_rng_state(),completed_steps=cfg['total_steps_per_seed'],config=cfg),path)
                elapsed=time.perf_counter()-start
                # Every checkpoint must reproduce deterministic validation actions/objectives.
                probe=generated_instance(cfg['validation_seeds'][0]);before=evaluate(probe,model);reloaded=load_model(method,path);after=evaluate(probe,reloaded)
                assert before['schedule']==after['schedule'] and before['objective_score']==after['objective_score']
                (run.path/f'{method}_seed{seed}_training_seeds.json').write_text(json.dumps(state['training_seeds']))
                run.add(dict(record_type='training_summary',instance='generated_train',scenario='mixed',method=method,seed=seed,env_steps=cfg['total_steps_per_seed'],training_time_s=elapsed,
                    training_timing_scope='learn + periodic validation + record IO + checkpoint save',parameter_count=parameters,unused_transitions=state['unused_transitions'],
                    checkpoint_path=str(path.relative_to(ROOT)),checkpoint_bytes=path.stat().st_size,checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),checkpoint_roundtrip=True,device='cpu',status='completed'))
                models.append((method,seed,path))
                if env is not None:env.close()
                del model,reloaded,state
        for name,spec,group in specs:
            for rule in ['SPT','EDD','MWKR']:
                if any(r.get('record_type')=='test' and r['instance']==name and r['method']==rule for r in run.records):continue
                run.add(dict(record_type='test',instance=name,scenario=group,method=rule,seed=0,**evaluate(spec,rule=rule)))
            for budget in [1,5]:
                if any(r.get('record_type')=='test' and r['instance']==name and r['method']=='CP-SAT' and r.get('budget_s')==budget for r in run.records):continue
                r=run_rolling(spec['jobs'],spec['machines'],spec['due'],spec['tape'],'CP-SAT',budget,0,(1,1,0)) if spec['tape'] else solve(spec['jobs'],spec['machines'],spec['due'],weights=(1,1,0),budget=budget)
                r['objective_score']=(r['makespan']+r['mean_tardiness'])/100;r.pop('budget_s',None)
                run.add(dict(record_type='test',instance=name,scenario=group,method='CP-SAT',seed=0,budget_s=budget,**r))
        for method,seed,path in models:
            model=load_model(method,path)
            for name,spec,group in specs:
                if any(r.get('record_type')=='test' and r['instance']==name and r['method']==method and r['seed']==seed for r in run.records):continue
                run.add(dict(record_type='test',instance=name,scenario=group,method=method,seed=seed,env_steps=cfg['total_steps_per_seed'],**evaluate(spec,model)))
        run.finish()
    except Exception as error:
        run.finish(error);raise

if __name__=='__main__':main()
