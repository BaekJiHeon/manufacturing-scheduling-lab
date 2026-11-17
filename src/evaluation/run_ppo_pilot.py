"""Fixed-budget five-seed Maskable PPO pilot with genuine learning/evaluation logs."""
import json,time,random,os
from pathlib import Path
import numpy as np
import psutil,torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv
from src.environments.event_fjsp import EventFJSPEnv,generated_instance
from src.algorithms.ppo_checkpoint import save_checkpoint,load_checkpoint
from src.algorithms.rolling_cpsat import solve
from src.simulator.rolling import run_rolling,scenario_tape
from src.simulator.problem import parse_fjsp
from src.run_baselines import build_due_dates
from src.evaluation.campaign import Campaign,ROOT,instance_path


def evaluate(spec,model=None,rule='SPT'):
    env=EventFJSPEnv(spec);obs,_=env.reset();latencies=[];started=time.perf_counter();steps=0;waits=0
    while not env.done:
        t=time.perf_counter();mask=env.action_masks()
        if model is not None:action,_=model.predict(obs,action_masks=mask,deterministic=True);action=int(action)
        else:
            options=[]
            for a in np.flatnonzero(mask[:-1]):
                i,m=divmod(int(a),env.mc);j,o=env.pairs[i];p=env.jobs[j][o][m]
                priority={'SPT':(p,j,m),'EDD':(env.due[j],p,j,m),'MWKR':(-sum(min(x.values()) for x in env.jobs[j][o:]),p,j,m)}[rule]
                options.append((priority,int(a)))
            action=min(options)[1] if options else env.wait_action
        latencies.append((time.perf_counter()-t)*1000);waits+=action==env.wait_action
        obs,_,_,_,info=env.step(action);steps+=1
        if steps>10000:raise RuntimeError('Policy did not terminate')
    info.update(runtime_ms=(time.perf_counter()-started)*1000,decision_count=steps,wait_count=waits,
      mean_inference_ms=float(np.mean(latencies)),p95_inference_ms=float(np.percentile(latencies,95)),total_inference_ms=sum(latencies),
      objective_score=(info['makespan']+info['mean_tardiness'])/100,status='FEASIBLE',episode_return=env.returns)
    info.update(stability_applicable=False,stability_cost=None,start_shift=None,machine_changes=None,reference_operations=None)
    return info


class Monitor(BaseCallback):
    def __init__(self,run,seed,config,checkpoint_dir,gradient_norms):
        super().__init__();self.run=run;self.seed=seed;self.cfg=config;self.folder=checkpoint_dir;self.norms=gradient_norms;self.start=time.perf_counter();self.last=0;self.episodes=[];self.curve=[]
    def _on_step(self):
        for info,done in zip(self.locals['infos'],self.locals['dones']):
            if done:self.episodes.append({k:info[k] for k in ['makespan','total_tardiness','mean_tardiness']})
        return True
    def record(self):
        step=self.model.num_timesteps
        if step==self.last:return
        row=dict(record_type='training',instance='generated_train',scenario='mixed',method='MaskablePPO',seed=self.seed,env_steps=step,
          elapsed_s=time.perf_counter()-self.start,training_steps_per_second=step/(time.perf_counter()-self.start),ram_mb=psutil.Process().memory_info().rss/2**20,
          gradient_norm_before_clip=float(np.mean(self.norms)) if self.norms else None)
        for k,v in self.model.logger.name_to_value.items():
            if k.startswith('train/') and isinstance(v,(float,int,np.floating)):row[k.replace('/','_')]=float(v)
        if self.episodes:
            row['train_episode_makespan']=float(np.mean([e['makespan'] for e in self.episodes]));row['train_episode_tardiness']=float(np.mean([e['total_tardiness'] for e in self.episodes]));row['train_episode_return']=float(np.mean([-(e['makespan']+e['mean_tardiness'])/self.cfg['reward_scale'] for e in self.episodes]))
        self.episodes.clear();self.norms.clear();self.run.add(row);self.last=step
        if step%self.cfg['evaluation_interval']==0:
            vals=[]
            for i in self.cfg['validation_seeds']:vals.append(evaluate(generated_instance(i),self.model))
            point=dict(record_type='validation',instance='generated_validation',scenario='mixed',method='MaskablePPO',seed=self.seed,env_steps=step,
              makespan=float(np.mean([v['makespan'] for v in vals])),total_tardiness=float(np.mean([v['total_tardiness'] for v in vals])),objective_score=float(np.mean([v['objective_score'] for v in vals])),episode_return=float(np.mean([v['episode_return'] for v in vals])))
            self.curve.append(point);self.run.add(point)
            if step%16384==0:save_checkpoint(self.model,self.folder/f'seed{self.seed}_step{step}')
    def _on_rollout_start(self):self.record()
    def _on_training_end(self):self.record()


def main():
    cfg=json.loads((ROOT/'configs/algorithms/ppo_pilot.json').read_text());torch.set_num_threads(cfg['torch_threads'])
    run=Campaign('ppo_pilot',cfg,os.getenv('RESUME_RUN_ID'));(ROOT/'reports/latest_ppo_pilot_run.txt').write_text(run.run_id+'\n')
    folder=ROOT/'checkpoints'/run.run_id;folder.mkdir(parents=True,exist_ok=bool(os.getenv('RESUME_RUN_ID')));models=[]
    validation=[dict(seed=i,**generated_instance(i)) for i in cfg['validation_seeds']]
    tests=[dict(seed=i,**generated_instance(i)) for i in cfg['test_seeds']]
    (run.path/'validation_instances.json').write_text(json.dumps(validation,indent=2));(run.path/'test_instances.json').write_text(json.dumps(tests,indent=2))
    try:
        for seed in cfg['seeds']:
            stem=folder/f'seed{seed}_final'
            if any(r.get('record_type')=='training_summary' and r['seed']==seed for r in run.records):
                if not stem.with_suffix('.zip').exists():raise RuntimeError('Missing completed checkpoint')
                models.append(stem);continue
            env=DummyVecEnv([lambda index=index:EventFJSPEnv(training_seed=seed*cfg['n_envs']+index) for index in range(cfg['n_envs'])])
            model=MaskablePPO(cfg['policy'],env,seed=seed,device=cfg['device'],policy_kwargs=dict(net_arch=cfg['net_arch']),
              **{k:cfg[k] for k in ['n_steps','batch_size','n_epochs','learning_rate','gamma','gae_lambda','ent_coef','max_grad_norm']})
            initial=[evaluate(generated_instance(i),model) for i in cfg['validation_seeds']]
            run.add(dict(record_type='validation',instance='generated_validation',scenario='mixed',method='MaskablePPO',seed=seed,env_steps=0,
              makespan=float(np.mean([r['makespan'] for r in initial])),total_tardiness=float(np.mean([r['total_tardiness'] for r in initial])),objective_score=float(np.mean([r['objective_score'] for r in initial])),episode_return=float(np.mean([r['episode_return'] for r in initial]))))
            norms=[];original_clip=torch.nn.utils.clip_grad_norm_
            def track_clip(*args,**kwargs):
                value=original_clip(*args,**kwargs);norms.append(float(value));return value
            torch.nn.utils.clip_grad_norm_=track_clip;start=time.perf_counter()
            monitor=Monitor(run,seed,cfg,folder,norms)
            try:model.learn(cfg['total_steps_per_seed'],callback=monitor)
            finally:torch.nn.utils.clip_grad_norm_=original_clip
            elapsed=time.perf_counter()-start;stem=folder/f'seed{seed}_final';save_checkpoint(model,stem);models.append(stem)
            (run.path/f'training_seeds_{seed}.json').write_text(json.dumps([e.generated_seeds for e in env.envs]))
            run.add(dict(record_type='training_summary',instance='generated_train',scenario='mixed',method='MaskablePPO',seed=seed,env_steps=model.num_timesteps,
              training_time_s=elapsed,checkpoint_bytes=stem.with_suffix('.zip').stat().st_size,device=str(model.device),status='completed'))
            del model;env.close()
        # All test sets are fixed before training; no test-based selection or tuning.
        specs=[(f'GEN{i}',generated_instance(i),'generated_test') for i in cfg['test_seeds']]
        for name in [f'MK{i:02d}' for i in range(1,11)]:
            j,m=parse_fjsp(instance_path(name));specs.append((name,dict(jobs=j,machines=m,due=list(map(int,build_due_dates(j,42))),tape=[]),'external_static'))
        for name in ['MK01','MK06']:
            j,m=parse_fjsp(instance_path(name));d=list(map(int,build_due_dates(j,42)))
            for tape_seed in [0,1,2]:specs.append((name+f'_event{tape_seed}',dict(jobs=j,machines=m,due=d,tape=scenario_tape(j,m,tape_seed,'combined')),'external_dynamic'))
        for name,spec,group in specs:
            for rule in ['SPT','EDD','MWKR']:
                if any(r.get('record_type')=='test' and r['instance']==name and r['method']==rule for r in run.records):continue
                run.add(dict(record_type='test',instance=name,scenario=group,method=rule,seed=0,**evaluate(spec,rule=rule)))
            for budget in [1,5]:
                if any(r.get('record_type')=='test' and r['instance']==name and r['method']=='CP-SAT' and r.get('budget_s')==budget for r in run.records):continue
                if spec['tape']:r=run_rolling(spec['jobs'],spec['machines'],spec['due'],spec['tape'],'CP-SAT',budget,0,(1,1,0))
                else:r=solve(spec['jobs'],spec['machines'],spec['due'],weights=(1,1,0),budget=budget)
                r['objective_score']=(r['makespan']+r['mean_tardiness'])/100
                r.pop('budget_s',None)
                run.add(dict(record_type='test',instance=name,scenario=group,method='CP-SAT',seed=0,budget_s=budget,**r))
        for seed,stem in zip(cfg['seeds'],models):
            model=MaskablePPO.load(str(stem),device='cpu')
            for name,spec,group in specs:
                if any(r.get('record_type')=='test' and r['instance']==name and r['method']=='MaskablePPO' and r['seed']==seed for r in run.records):continue
                run.add(dict(record_type='test',instance=name,scenario=group,method='MaskablePPO',seed=seed,env_steps=cfg['total_steps_per_seed'],**evaluate(spec,model)))
    except Exception as e:run.finish(e);raise
    run.finish()
if __name__=='__main__':main()
