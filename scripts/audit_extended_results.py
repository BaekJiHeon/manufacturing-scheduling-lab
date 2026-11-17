"""Independent persisted-artifact validator (not the simulator's validator)."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.campaign import ROOT,instance_path
from src.simulator.problem import parse_fjsp
from src.environments.event_fjsp import generated_instance
from src.run_baselines import build_due_dates


def jobs_int(jobs):return [[{int(m):int(p) for m,p in op.items()} for op in job] for job in jobs]

def check(jobs,m,due,releases,rows,downs,reported,frozen=(),reference=(),weights=(1,1,0)):
    jobs=jobs_int(jobs);index={(r['job'],r['operation']):r for r in rows};expected={(j,o) for j,job in enumerate(jobs) for o in range(len(job))}
    if set(index)!=expected or len(index)!=len(rows):raise ValueError('Incomplete/duplicate schedule')
    by_machine=[[] for _ in range(m)]
    for (j,o),r in index.items():
        machine,s,e=r['machine'],r['start'],r['end']
        if machine not in jobs[j][o] or not 0<=s<e or s<releases[j]:raise ValueError('Ineligible assignment/release')
        interruption=sum(max(0,min(e,d['end'])-max(s,d['start'])) for d in downs if d['machine']==machine)
        if e-s-interruption!=jobs[j][o][machine] or r['duration']!=jobs[j][o][machine]:raise ValueError('Busy duration mismatch')
        if any(d['machine']==machine and d['start']<=s<d['end'] for d in downs):raise ValueError('Starts while machine down')
        if o and index[j,o-1]['end']>s:raise ValueError('Precedence violation')
        by_machine[machine].append((s,e))
    for spans in by_machine:
        spans.sort()
        if any(e>s for (_,e),(s,_) in zip(spans,spans[1:])):raise ValueError('Machine assignment overlap, including pause reservation')
    for r in frozen:
        if r!=index[r['job'],r['operation']]:raise ValueError('Frozen work changed')
    completion=[index[j,len(job)-1]['end'] for j,job in enumerate(jobs)];c=max(completion);t=sum(max(0,x-d) for x,d in zip(completion,due))
    for k,v in [('makespan',c),('total_tardiness',t),('constraint_violation_count',0)]:
        if abs(reported[k]-v)>1e-8:raise ValueError(('Metric mismatch',k,reported[k],v))
    if 'normalized_objective' in reported:
        h=sum(max(op.values()) for job in jobs for op in job);fixed={(x['job'],x['operation']) for x in frozen}
        refs=[x for x in reference if (x['job'],x['operation']) not in fixed];q=max(1,len(refs))
        shift=sum(abs(index[x['job'],x['operation']]['start']-x['start']) for x in refs)
        switch=sum(index[x['job'],x['operation']]['machine']!=x['machine'] for x in refs)
        expected_score=weights[0]*c/h+weights[1]*t/(len(jobs)*h)+weights[2]*(shift/(q*h)+switch/q)
        if abs(reported['normalized_objective']-expected_score)>1e-8:raise ValueError('Independent normalized objective mismatch')
    return c,t


def audit(families=None, output_name="expanded_artifact_audit.json"):
    counts={};warnings=[];traces=0
    for family in families or ['expanded_static','objectives_dynamic','ppo_pilot']:
        rid=(ROOT/'reports'/f'latest_{family}_run.txt').read_text().strip();folder=ROOT/'results'/family/rid
        metadata=json.loads((folder/'metadata.json').read_text())
        if metadata['status']!='completed':raise RuntimeError(f'{family} is not completed')
        count=0
        for file in sorted(folder.glob('record_[0-9]*.json')):
            r=json.loads(file.read_text())
            if 'schedule' not in r or not r['schedule']:continue
            name=r['instance'].split('_event')[0]
            if name.startswith('GEN'):
                spec=generated_instance(int(name[3:]));jobs=spec['jobs'];m=spec['machines'];due=spec['due']
            else:
                jobs,m=parse_fjsp(instance_path(name));due=list(map(int,build_due_dates(jobs,42)))
            releases=[0]*len(jobs);downs=[]
            if 'decisions' in r:
                prior=[]
                for decision in r['decisions']:
                    event=decision['event'];now=event['time'];frozen=[dict(x) for x in prior if x['start']<now]
                    if event['type']=='arrival':jobs.append(jobs_int([event['job']])[0]);due.append(event['due']);releases.append(now)
                    if event['type']=='breakdown':
                        downs.append(dict(machine=event['machine'],start=now,end=event['repair_at']))
                        for x in frozen:
                            if x['machine']==event['machine'] and x['end']>now:x['end']+=event['repair_at']-now
                    if decision['frozen']!=frozen or decision['observed_job_count']!=len(jobs) or decision['observed_outages']!=downs:raise ValueError('Observed prefix/frozen state mismatch')
                    check(jobs,m,due,releases,decision['schedule'],downs,decision,frozen,prior,r.get('weights',(1,1,0)));prior=decision['schedule'];traces+=1
                    if decision.get('solver_response_objective_mismatch'):warnings.append(dict(run_id=rid,step=r['step'],event=event['type'],kind='solver_response_objective_mismatch'))
            elif 'observed_events' in r:
                for event in r['observed_events']:
                    if event['type']=='arrival':jobs.append(jobs_int([event['job']])[0]);due.append(event['due']);releases.append(event['time'])
                    if event['type']=='breakdown':downs.append(dict(machine=event['machine'],start=event['time'],end=event['repair_at']))
            check(jobs,m,due,releases,r['schedule'],downs,r,reference=r.get('reference',()),weights=r.get('weights',(1,1,0)));count+=1
            if r.get('solver_response_objective_mismatch'):warnings.append(dict(run_id=rid,step=r['step'],kind='solver_response_objective_mismatch'))
            if r.get('invalid_bound_discarded'):warnings.append(dict(run_id=rid,step=r['step'],kind='invalid_bound_discarded'))
        counts[family]=count
    provenance=json.loads((ROOT/'data/raw/brandimarte/provenance.json').read_text())
    for item in provenance['files']:
        if hashlib.sha256((ROOT/'data/raw/brandimarte'/f'{item["id"]}.txt').read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Raw input changed')
    report=dict(schedule_records_checked=counts,decision_schedules_checked=traces,feasibility_violations=0,source_hashes_match=True,warnings=warnings)
    (ROOT/'reports'/output_name).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':audit()
