"""Generate the tracked four-method Grafana comparison dashboard."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.campaign import ROOT
DS=dict(type='grafana-postgresql-datasource',uid='manufacturing_pg')
where='run_id=${run_id:sqlstring}'
base=f'FROM extended_records WHERE {where}'
panels=[]
queries=[
 ('Validation objective · lower is better','timeseries',f"SELECT (payload->>'recorded_at')::timestamptz AS time,(payload->>'method')||' seed '||(payload->>'seed') AS metric,(payload->>'objective_score')::float AS value {base} AND payload->>'record_type'='validation' ORDER BY time"),
 ('Validation by actual interaction count','table',f"SELECT payload->>'method' AS method,payload->>'seed' AS seed,(payload->>'env_steps')::int AS env_steps,(payload->>'objective_score')::float AS objective {base} AND payload->>'record_type'='validation' ORDER BY method,seed,env_steps"),
 ('Mean cost gap to CP-SAT 5s · positive is worse','table',f"WITH tests AS (SELECT payload AS p FROM extended_records WHERE {where} AND payload->>'record_type'='test'), cp AS (SELECT p->>'instance' AS instance,(p->>'objective_score')::float AS score FROM tests WHERE p->>'method'='CP-SAT' AND (p->>'budget_s')::float=5) SELECT t.p->>'scenario' AS scenario,t.p->>'method' AS method,round(avg(100*((t.p->>'objective_score')::float/cp.score-1))::numeric,2) AS gap_percent,count(*) AS episodes FROM tests t JOIN cp ON t.p->>'instance'=cp.instance WHERE t.p->>'method'!='CP-SAT' GROUP BY 1,2 ORDER BY 1,3"),
 ('Full episode latency and action latency · different units of work','table',f"SELECT payload->>'method' AS method,payload->>'scenario' AS scenario,COALESCE(payload->>'budget_s','') AS budget_s,round(avg((payload->>'runtime_ms')::numeric),3) AS episode_ms,round(avg((payload->>'mean_inference_ms')::numeric),3) AS action_ms,count(*) AS episodes {base} AND payload->>'record_type'='test' GROUP BY 1,2,3 ORDER BY 2,1,3"),
 ('Training runtime, parameters and checkpoint audit','table',f"SELECT payload->>'method' AS method,payload->>'seed' AS seed,payload->>'env_steps' AS interactions,round((payload->>'training_time_s')::numeric,2) AS seconds,payload->>'parameter_count' AS parameters,payload->>'unused_transitions' AS unused_interactions,payload->>'checkpoint_roundtrip' AS checkpoint_verified {base} AND payload->>'record_type'='training_summary' ORDER BY 1,2"),
 ('Observed training returns','timeseries',f"SELECT (payload->>'recorded_at')::timestamptz AS time,(payload->>'method')||' seed '||(payload->>'seed') AS metric,(payload->>'train_episode_return')::float AS value {base} AND payload->>'record_type'='training' AND payload->>'train_episode_return' IS NOT NULL ORDER BY time"),
 ('Optimizer losses · algorithm-specific scales','timeseries',f"SELECT (payload->>'recorded_at')::timestamptz AS time,(payload->>'method')||' seed '||(payload->>'seed')||' '||v.key AS metric,v.value::float AS value FROM extended_records CROSS JOIN LATERAL jsonb_each_text(payload) v WHERE {where} AND payload->>'record_type'='training' AND v.key IN ('train_policy_gradient_loss','train_value_loss','train_td_loss') ORDER BY time"),
 ('Raw evaluation results','table',f"SELECT step,payload->>'instance' AS instance,payload->>'scenario' AS scenario,payload->>'method' AS method,payload->>'seed' AS seed,payload->>'budget_s' AS budget_s,payload->>'makespan' AS makespan,payload->>'total_tardiness' AS tardiness,payload->>'objective_score' AS objective,payload->>'runtime_ms' AS runtime_ms,payload->>'constraint_violation_count' AS violations {base} AND payload->>'record_type'='test' ORDER BY step"),
]
y=0
for i,(title,kind,sql) in enumerate(queries):
 h=8 if kind=='timeseries' else 7
 panels.append(dict(id=1011+i,title=title,type=kind,datasource=DS,gridPos=dict(x=0,y=y,w=24,h=h),targets=[dict(refId='A',datasource=DS,format='time_series' if kind=='timeseries' else 'table',rawQuery=True,rawSql=sql)],fieldConfig=dict(defaults={},overrides=[]),options=dict(legend=dict(displayMode='table',placement='bottom')) if kind=='timeseries' else dict(showHeader=True)))
 y+=h
variable=dict(name='run_id',type='query',datasource=DS,query="SELECT run_id AS __value,(metadata->>'name')||' | '||run_id AS __text FROM extended_runs WHERE metadata->>'name'='multi_rl' ORDER BY metadata->>'created_at' DESC",refresh=1,multi=False,includeAll=False)
rid=(ROOT/'reports/latest_multi_rl_run.txt').read_text().strip()
meta=json.loads((ROOT/'results/multi_rl'/rid/'metadata.json').read_text())
dashboard=dict(uid='research-multi-rl',title='Manufacturing RL | PPO PQN GRPO GSPO Comparison',schemaVersion=40,version=1,tags=['manufacturing','measured','rl-comparison'],refresh='10s',time={'from':meta['created_at'],'to':'now'},templating=dict(list=[variable]),panels=panels)
p=ROOT/'grafana/dashboards/research-multi-rl.json';p.write_text(json.dumps(dashboard,indent=2));print(p)
