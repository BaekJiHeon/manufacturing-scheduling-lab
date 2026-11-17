"""Provision one live audit/learning dashboard and validate every SQL target via Grafana."""
import base64,json,sys,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.campaign import ROOT,connect
DS={'type':'grafana-postgresql-datasource','uid':'manufacturing_pg'}
where="run_id=${run_id:sqlstring}"
base=f"FROM extended_records WHERE {where}"
queries=[
 ('Experiment status','table',"SELECT metadata->>'name' AS campaign,metadata->>'status' AS status,(SELECT count(*) FROM extended_records r WHERE r.run_id=extended_runs.run_id) AS records FROM extended_runs WHERE run_id=${run_id:sqlstring}"),
 ('Mean scheduling KPIs · group details in row label','table',f"SELECT (payload->>'instance')||' | '||(payload->>'method')||COALESCE(' '||(payload->>'budget_s')||'s',' '||(payload->>'time_limit_s')||'s','')||COALESCE(' | '||(payload->>'objective'),'')||' | '||(payload->>'scenario') AS case,round(avg((payload->>'makespan')::numeric),2) AS makespan,round(avg((payload->>'total_tardiness')::numeric),2) AS tardiness,round(avg((payload->>'runtime_ms')::numeric),2) AS runtime_ms {base} AND payload ? 'makespan' AND COALESCE(payload->>'record_type','test')='test' GROUP BY 1 ORDER BY 1"),
 ('Scheduling KPIs · one row per evaluation','table',f"SELECT step,payload->>'instance' AS instance,payload->>'scenario' AS scenario,payload->>'method' AS method,payload->>'objective' AS objective,(payload->>'seed')::int AS seed,payload->>'status' AS status,COALESCE(payload->>'budget_s',payload->>'time_limit_s') AS budget_s,(payload->>'makespan')::float AS makespan,(payload->>'total_tardiness')::float AS tardiness,(payload->>'runtime_ms')::float AS runtime_ms,(payload->>'best_bound')::float AS bound,payload->>'solution_source' AS solution_source {base} AND payload ? 'makespan' AND COALESCE(payload->>'record_type','test')='test' ORDER BY step"),
 ('PPO validation objective · lower is better','timeseries',f"SELECT (payload->>'recorded_at')::timestamptz AS time,'seed '||(payload->>'seed') AS metric,(payload->>'objective_score')::float AS value {base} AND payload->>'record_type'='validation' ORDER BY time"),
 ('PPO episode reward · gamma=1 objective identity','timeseries',f"SELECT (payload->>'recorded_at')::timestamptz AS time,'seed '||(payload->>'seed') AS metric,(payload->>'train_episode_return')::float AS value {base} AND payload ? 'train_episode_return' ORDER BY time"),
 ('PPO training losses · recorded optimizer updates','timeseries',f"SELECT (payload->>'recorded_at')::timestamptz AS time,'seed '||(payload->>'seed')||' '||v.key AS metric,(v.value)::float AS value FROM extended_records CROSS JOIN LATERAL jsonb_each_text(payload) v WHERE {where} AND v.key IN ('train_policy_gradient_loss','train_value_loss','train_approx_kl') ORDER BY time"),
 ('PPO entropy and gradient norm','timeseries',f"SELECT (payload->>'recorded_at')::timestamptz AS time,'seed '||(payload->>'seed')||' '||v.key AS metric,(v.value)::float AS value FROM extended_records CROSS JOIN LATERAL jsonb_each_text(payload) v WHERE {where} AND v.key IN ('train_entropy_loss','gradient_norm_before_clip') ORDER BY time"),
 ('Training throughput and checkpoint audit','table',f"SELECT step,payload->>'seed' AS seed,payload->>'env_steps' AS env_steps,payload->>'training_steps_per_second' AS steps_per_second,payload->>'ram_mb' AS ram_mb,payload->>'training_time_s' AS training_time_s,payload->>'checkpoint_bytes' AS checkpoint_bytes {base} AND payload->>'record_type' IN ('training','training_summary') ORDER BY step DESC LIMIT 50"),
 ('Dynamic outcomes and schedule stability','table',f"SELECT step,payload->>'instance' AS instance,payload->>'scenario' AS scenario,payload->>'method' AS method,payload->>'objective' AS objective,payload->>'seed' AS seed,payload->>'budget_s' AS budget_s,payload->>'rescheduling_decisions' AS replans,payload->>'cumulative_start_shift' AS start_shift,payload->>'cumulative_machine_changes' AS machine_changes,payload->>'mean_replanning_ms' AS mean_replanning_ms,payload->>'fallback_count' AS fallback_count,payload->>'constraint_violation_count' AS violations {base} AND payload ? 'decisions' ORDER BY step"),
 ('Each observed event and solver certificate','table',f"SELECT step,payload->>'instance' AS instance,payload->>'method' AS method,d->'event'->>'type' AS event,d->'event'->>'time' AS simulation_time,d->>'observed_job_count' AS known_jobs,d->>'status' AS solver_status,d->>'solution_source' AS solution_source,d->>'runtime_ms' AS latency_ms,d->>'makespan' AS planned_makespan,d->>'total_tardiness' AS planned_tardiness FROM extended_records CROSS JOIN LATERAL jsonb_array_elements(payload->'decisions') d WHERE {where} ORDER BY step,(d->'event'->>'time')::int"),
 ('Feasibility and solver-response audit','table',f"SELECT step,payload->>'instance' AS instance,payload->>'method' AS method,payload->>'constraint_violation_count' AS violations,payload->>'solver_response_objective_mismatch' AS response_mismatch,payload->>'invalid_bound_discarded' AS invalid_bound_discarded,payload->>'budget_overrun_ms' AS budget_overrun_ms {base} AND (payload->>'constraint_violation_count' IS NOT NULL) ORDER BY step"),
]
# Each dynamic planning call is one observation; never use whole-episode runtime.
planning_cte = f"""WITH calls AS (
 SELECT CASE WHEN payload ? 'budget_s' THEN (payload->>'runtime_ms')::float
             ELSE (payload->>'solver_runtime_ms')::float END AS latency_ms,
        COALESCE(payload->>'budget_s',payload->>'time_limit_s')::float AS budget_s
 {base} AND payload->>'method'='CP-SAT' AND NOT (payload ? 'decisions')
 UNION ALL
 SELECT (d->>'runtime_ms')::float,(d->>'budget_s')::float
 FROM extended_records CROSS JOIN LATERAL jsonb_array_elements(payload->'decisions') d
 WHERE {where} AND payload->>'method'='CP-SAT'
) """
budget_query=planning_cte+"SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY 100*latency_ms/(1000*budget_s)) AS budget_used_percent FROM calls WHERE budget_s>0"
latency_query=planning_cte+"SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS planning_ms FROM calls WHERE budget_s>0"
PROM={'type':'prometheus','uid':'manufacturing_prom'}
def headline(panel_id,title,x,kind,source,target,unit,description,maximum=None):
    defaults=dict(unit=unit,decimals=1,color=dict(mode='fixed',fixedColor='blue'),noValue='N/A')
    if maximum is not None: defaults.update(min=0,max=maximum)
    options=dict(reduceOptions=dict(values=False,calcs=['lastNotNull'],fields=''),orientation='auto')
    if kind=='gauge':
        defaults['thresholds']=dict(mode='absolute',steps=[dict(color='blue',value=None)]+([dict(color='orange',value=100)] if maximum==120 else []))
        defaults['color']=dict(mode='thresholds')
        options.update(showThresholdLabels=False,showThresholdMarkers=True)
    else: options.update(colorMode='value',graphMode='none',textMode='auto')
    return dict(id=panel_id,title=title,description=description,type=kind,datasource=source,gridPos=dict(x=x,y=0,w=6,h=6),targets=[dict(refId='A',datasource=source,**target)],fieldConfig=dict(defaults=defaults,overrides=[]),options=options)
host_note='Host-wide resource use at the selected time range endpoint; not the training process alone. Refreshes live when the range ends at now. Utilization does not measure schedule quality.'
plan_note='P95 across individual CP-SAT planning calls in the selected run, including the initial plan. Dynamic episode totals are excluded. Expanded-static uses solver runtime / solver limit; other campaigns include preparation and validation in the planning budget. The full selected run is used regardless of the time range.'
panels=[
 headline(780,'Host CPU usage',0,'gauge',PROM,dict(expr='manufacturing_cpu_percent',instant=True,range=False),'percent',host_note,100),
 headline(781,'Host memory usage',6,'gauge',PROM,dict(expr='manufacturing_ram_percent',instant=True,range=False),'percent',host_note+' psutil percentage = (total - available) / total.',100),
 headline(782,'CP-SAT budget used · P95',12,'gauge',DS,dict(format='table',rawQuery=True,rawSql=budget_query),'percent',plan_note+' 100% is the allocated budget; orange indicates reaching/exceeding it. Display scale is 0–120%; the numeric value is not capped.',120),
 headline(783,'CP-SAT planning time · P95',18,'stat',DS,dict(format='table',rawQuery=True,rawSql=latency_query),'ms',plan_note+' Includes different configured budgets; see detailed rows for each budget.'),
];y=6
for i,(title,kind,query) in enumerate(queries):
    height=6 if kind=='timeseries' else (8 if i else 4)
    panels.append(dict(id=800+i,title=title,type=kind,datasource=DS,gridPos=dict(x=0,y=y,w=24,h=height),targets=[dict(refId='A',datasource=DS,format='time_series' if kind=='timeseries' else 'table',rawQuery=True,rawSql=query)],fieldConfig=dict(defaults={},overrides=[]),options=dict(legend=dict(displayMode='table',placement='bottom')) if kind=='timeseries' else dict(showHeader=True)))
    y+=height
variable=dict(name='run_id',type='query',datasource=DS,query="SELECT run_id AS __value,(metadata->>'name')||' | '||run_id AS __text FROM extended_runs ORDER BY metadata->>'created_at' DESC",refresh=1,multi=False,includeAll=False)
with connect() as conn:
    latest=conn.execute("SELECT metadata FROM extended_runs WHERE metadata->>'name'='ppo_pilot' ORDER BY metadata->>'created_at' DESC LIMIT 1").fetchone()
plot_time=dict(**{'from':'now-24h','to':'now'}) if not latest else dict(**{'from':latest[0]['created_at'],'to':'now'})
dashboard=dict(uid='research-extended',title='Manufacturing RL | Expanded Research and PPO',tags=['manufacturing','measured'],schemaVersion=40,version=1,refresh='10s',time=plot_time,templating=dict(list=[variable]),panels=panels)
path=ROOT/'grafana/dashboards/research-extended.json';path.write_text(json.dumps(dashboard,indent=2))
legacy_path=ROOT/'grafana/dashboards/research-training.json'
training=json.loads(legacy_path.read_text());resource_panels=[p for p in training['panels'] if p.get('datasource',{}).get('type')=='prometheus']
training['panels']=json.loads(json.dumps([p for p in panels if p['title'].startswith(('PPO','Training throughput'))]))+resource_panels
training['templating']=dashboard['templating'];training['time']=plot_time;training['version']=training.get('version',1)+1
row_y=0
for index,panel in enumerate(training['panels']):
    panel['id']=900+index;panel['gridPos']=dict(x=0,y=row_y,w=24,h=7);row_y+=7
legacy_path.write_text(json.dumps(training,indent=2))

auth=base64.b64encode(b'admin:admin_local_only').decode()
def request(path,payload=None):
    req=urllib.request.Request('http://localhost:3000'+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Authorization':'Basic '+auth,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
for definition in [dashboard,training]:
    try:existing=request('/api/dashboards/uid/'+definition['uid'])
    except urllib.error.HTTPError as error:
        if error.code!=404:raise
        existing={}
    if existing.get('meta',{}).get('provisioned'):
        print('Tracked file provisioning:',definition['uid'])
    else:print(request('/api/dashboards/db',dict(dashboard=definition,overwrite=True)))
with connect() as conn:run_ids=[r[0] for r in conn.execute('SELECT run_id FROM extended_runs')]
checks=[]
for run_id in run_ids:
    for i,(_,kind,query) in enumerate(queries + [('CP budget','gauge',budget_query),('CP latency','stat',latency_query)]):
        q=query.replace('${run_id:sqlstring}',"'"+run_id+"'")
        result=request('/api/ds/query',{'from':'0','to':'9999999999999','queries':[dict(refId='A',datasource=DS,rawSql=q,format='time_series' if kind=='timeseries' else 'table',rawQuery=True)]})
        if result['results']['A'].get('error'):raise RuntimeError(result)
        checks.append(dict(run_id=run_id,panel=i,ok=True))
(ROOT/'reports/extended_dashboard_validation.json').write_text(json.dumps(checks,indent=2));print('SQL checks:',len(checks))
