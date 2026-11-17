"""Event-driven, non-delay static FJSP. No intentional WAIT action (see report)."""
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from src.simulator.problem import scheduling_metrics
from src.run_baselines import build_due_dates


class StaticFJSPEnv(gym.Env):
    metadata = {'render_modes': []}

    def __init__(self, jobs, machines, due=None, max_operations=None, max_machines=None,
                 makespan_weight=1., tardiness_weight=0.):
        self.jobs=jobs; self.m=machines
        self.pairs=[(j,o) for j,job in enumerate(jobs) for o in range(len(job))]
        self.n=len(self.pairs);self.capacity=max_operations or self.n;self.mc=max_machines or machines
        if self.n>self.capacity or machines>self.mc or not self.n:
            raise ValueError('Instance exceeds configured capacity or is empty')
        self.due=np.asarray(build_due_dates(jobs,42) if due is None else due,dtype=float)
        if len(self.due)!=len(jobs) or not np.all(np.isfinite(self.due)):
            raise ValueError('One finite due date per job required')
        self.scale=float(sum(max(op.values()) for job in jobs for op in job))
        self.wm=makespan_weight;self.wt=tardiness_weight
        self.action_space=spaces.Discrete(self.capacity*self.mc)
        self.observation_space=spaces.Dict({
            'operations':spaces.Box(0,np.inf,(self.capacity,8),np.float32),
            'processing_times':spaces.Box(0,np.inf,(self.capacity,self.mc),np.float32),
            'machines':spaces.Box(0,np.inf,(self.mc,4),np.float32),
            'clock':spaces.Box(0,np.inf,(1,),np.float32)})
        self.reset()

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.now=0;self.next=[0]*len(self.jobs);self.running={};self.rows=[];self.done=False
        self.finished=set();self.busy=np.zeros(self.mc);self.returns=0.
        return self._observation(), {}

    def action_masks(self):
        mask=np.zeros(self.action_space.n,dtype=bool)
        if self.done: return mask
        occupied={v[0] for v in self.running.values()}
        for i,(j,o) in enumerate(self.pairs):
            if self.next[j]!=o or j in self.running: continue
            for m in self.jobs[j][o]:
                if m not in occupied:mask[i*self.mc+m]=True
        return mask

    def _advance(self):
        while not self.action_masks().any():
            if not self.running:
                if len(self.finished)==self.n:
                    self.done=True;return
                raise RuntimeError('Deadlock: unfinished work without completion event')
            future=min(v[2] for v in self.running.values())
            if future<=self.now:raise RuntimeError('Non-increasing event clock')
            self.now=future
            for j,(_,o,end) in list(self.running.items()):
                if end==self.now:
                    self.finished.add((j,o));del self.running[j]
            if len(self.finished)==self.n:
                self.done=True;return

    def step(self, action):
        if self.done:raise RuntimeError('Reset required after termination')
        if not self.action_space.contains(action) or not self.action_masks()[action]:
            raise ValueError(f'Invalid masked action: {action}')
        old_time=self.now;i,m=divmod(int(action),self.mc);j,o=self.pairs[i];p=self.jobs[j][o][m]
        self.rows.append(dict(job=j,operation=o,machine=m,start=self.now,end=self.now+p,duration=p))
        self.running[j]=(m,o,self.now+p);self.next[j]+=1;self.busy[m]+=p
        self._advance()
        reward=-self.wm*(self.now-old_time)/self.scale;info={}
        if self.done:
            info.update(scheduling_metrics(self.jobs,self.m,self.rows,self.due))
            reward-=self.wt*info['total_tardiness']/self.scale
            info['schedule']=list(self.rows)
        self.returns+=reward
        return self._observation(),float(reward),self.done,False,info

    def _observation(self):
        op=np.zeros((self.capacity,8),np.float32);pt=np.zeros((self.capacity,self.mc),np.float32)
        for i,(j,o) in enumerate(self.pairs):
            # present, job id, ordinal, completed, running, ready, remaining nominal work, due
            active=j in self.running and self.running[j][1]==o
            ready=self.next[j]==o and j not in self.running
            remaining=sum(min(x.values()) for x in self.jobs[j][self.next[j]:])
            op[i]=[1,j/max(1,len(self.jobs)-1),o/max(1,len(self.jobs[j])-1),
                   (j,o) in self.finished,active,ready,remaining/self.scale,self.due[j]/self.scale]
            for m,p in self.jobs[j][o].items():pt[i,m]=p/self.scale
        machine=np.zeros((self.mc,4),np.float32)
        for m in range(self.m):
            active=[v for v in self.running.values() if v[0]==m]
            remaining=(active[0][2]-self.now) if active else 0
            # busy includes booked duration; utilization uses only elapsed busy time.
            elapsed_busy=self.busy[m]-remaining
            machine[m]=[1,bool(active),remaining/self.scale,elapsed_busy/max(1,self.now)]
        return dict(operations=op,processing_times=pt,machines=machine,clock=np.array([self.now/self.scale],np.float32))
