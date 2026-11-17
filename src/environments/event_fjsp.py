"""Masked dispatch environment with WAIT and prefix-only dynamic observations.

All external events are private simulator inputs. Unarrived job slots are zero.
WAIT is enabled only by an already running operation/known repair, never by a
hidden future arrival. The simulator still interrupts waiting at external events.
"""
import copy
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from src.algorithms.rolling_cpsat import active_segments,metrics
from src.run_baselines import build_due_dates
from src.simulator.rolling import scenario_tape


def generated_instance(seed):
    rng=np.random.default_rng(seed);m=int(rng.integers(3,7));jobs=[]
    for _ in range(int(rng.integers(4,11))):
        job=[]
        for _ in range(int(rng.integers(3,7))):
            ms=rng.choice(m,size=int(rng.integers(1,min(3,m)+1)),replace=False)
            job.append({int(k):int(rng.integers(1,11)) for k in ms})
        jobs.append(job)
    due=list(map(int,build_due_dates(jobs,seed+40000)))
    tape=scenario_tape(jobs,m,seed,'combined') if seed%2 else []
    return dict(jobs=jobs,machines=m,due=due,tape=tape)


class EventFJSPEnv(gym.Env):
    metadata={'render_modes':[]}
    def __init__(self,spec=None,training_seed=None,max_operations=260,max_machines=15,weights=(1.,1.),scale=100.):
        self.initial=copy.deepcopy(spec);self.training_seed=training_seed;self.capacity=max_operations;self.mc=max_machines
        self.wm,self.wt=weights;self.scale=scale;self.episode=0;self.generated_seeds=[]
        if spec is None and training_seed is None:raise ValueError('Need fixed instance or training seed')
        self.action_space=spaces.Discrete(self.capacity*self.mc+1);self.wait_action=int(self.action_space.n)-1
        self.observation_space=spaces.Dict(dict(operations=spaces.Box(0,np.inf,(self.capacity,9),np.float32),processing_times=spaces.Box(0,np.inf,(self.capacity,self.mc),np.float32),machines=spaces.Box(0,np.inf,(self.mc,4),np.float32),clock=spaces.Box(0,np.inf,(1,),np.float32)))
    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed)
        if self.initial is None:
            episode_seed=self.training_seed*100000+self.episode;self.episode+=1;self.generated_seeds.append(episode_seed);spec=generated_instance(episode_seed)
        else:spec=copy.deepcopy(self.initial)
        self.jobs=spec['jobs'];self.m=spec['machines'];self.due=list(spec['due']);self._events=copy.deepcopy(spec.get('tape',[]));self._event_index=0
        self.releases=[0]*len(self.jobs);self.outages=[];self.observed_events=[];self.now=0;self.rows=[];self.running={};self.finished=set();self.next=[0]*len(self.jobs);self.done=False;self.returns=0.
        self._index();self._process_events();return self._observation(),{}
    def _index(self):
        self.pairs=[(j,o) for j,job in enumerate(self.jobs) for o in range(len(job))]
        if len(self.pairs)>self.capacity or self.m>self.mc:raise ValueError('Instance exceeds policy capacity')
    def _dispatch_mask(self):
        mask=np.zeros(self.action_space.n,dtype=bool)
        if self.done:return mask
        occupied={r['machine'] for r in self.running.values()}
        down={d['machine'] for d in self.outages if d['start']<=self.now<d['end']}
        for i,(j,o) in enumerate(self.pairs):
            if self.next[j]!=o or j in self.running:continue
            for m in self.jobs[j][o]:
                if m not in occupied and m not in down:mask[i*self.mc+m]=True
        return mask
    def action_masks(self):
        mask=self._dispatch_mask()
        if not self.done:mask[-1]=bool(self.running or any(d['end']>self.now for d in self.outages))
        return mask
    def _process_events(self):
        while self._event_index<len(self._events) and self._events[self._event_index]['time']==self.now:
            e=self._events[self._event_index];self._event_index+=1;self.observed_events.append(copy.deepcopy(e))
            if e['type']=='breakdown':
                self.outages.append(dict(machine=e['machine'],start=self.now,end=e['repair_at']))
                for r in self.running.values():
                    if r['machine']==e['machine'] and r['end']>self.now:r['end']+=e['repair_at']-self.now
            elif e['type']=='arrival':
                self.jobs.append(e['job']);self.due.append(e['due']);self.releases.append(self.now);self.next.append(0);self._index()
            elif e['type']!='recovery':raise ValueError('Unknown event')
    def _tick(self):
        times=[r['end'] for r in self.running.values()]
        if self._event_index<len(self._events):times.append(self._events[self._event_index]['time'])
        if not times:raise RuntimeError('Deadlock')
        future=min(times)
        if future<=self.now:raise RuntimeError('Clock did not advance')
        self.now=future
        for j,r in list(self.running.items()):
            if r['end']==self.now:self.finished.add((j,r['operation']));del self.running[j]
        self._process_events()
    def _advance(self,force=False):
        if force:self._tick()
        while True:
            if len(self.finished)==len(self.pairs) and self._event_index==len(self._events):self.done=True;return
            if self._dispatch_mask().any():return
            self._tick()
    def step(self,action):
        if self.done:raise RuntimeError('Reset required')
        if not self.action_space.contains(action) or not self.action_masks()[action]:raise ValueError('Invalid masked action')
        old=self.now
        if action==self.wait_action:self._advance(force=True)
        else:
            i,m=divmod(int(action),self.mc);j,o=self.pairs[i];p=self.jobs[j][o][m]
            row=dict(job=j,operation=o,machine=m,start=self.now,end=self.now+p,duration=p)
            self.rows.append(row);self.running[j]=row;self.next[j]+=1;self._advance()
        reward=-self.wm*(self.now-old)/self.scale;info={}
        if self.done:
            info=metrics(self.jobs,self.m,self.rows,self.due,self.releases,self.outages,weights=(self.wm,self.wt,0))
            # The last recovery may be after all work finishes: do not reward fictitious production time.
            reward+=self.wm*(self.now-info['makespan'])/self.scale-self.wt*info['mean_tardiness']/self.scale
            info.update(schedule=copy.deepcopy(self.rows),outages=copy.deepcopy(self.outages),observed_events=copy.deepcopy(self.observed_events))
        self.returns+=reward
        return self._observation(),float(reward),self.done,False,info
    def _observation(self):
        op=np.zeros((self.capacity,9),np.float32);pt=np.zeros((self.capacity,self.mc),np.float32)
        for i,(j,o) in enumerate(self.pairs):
            active=j in self.running and self.running[j]['operation']==o
            op[i]=[1,j/30,o/20,(j,o) in self.finished,active,self.next[j]==o and j not in self.running,
                   sum(min(x.values()) for x in self.jobs[j][self.next[j]:])/self.scale,self.due[j]/self.scale,self.releases[j]/self.scale]
            for m,p in self.jobs[j][o].items():pt[i,m]=p/self.scale
        machine=np.zeros((self.mc,4),np.float32)
        for m in range(self.m):
            running=next((r for r in self.running.values() if r['machine']==m),None)
            repair=max([self.now,*[d['end'] for d in self.outages if d['machine']==m]])
            machine[m]=[1,bool(running),(running['end']-self.now)/self.scale if running else 0,(repair-self.now)/self.scale]
        return dict(operations=op,processing_times=pt,machines=machine,clock=np.array([self.now/self.scale],np.float32))
