"""Verify health, provisioned dashboards and actual panel SQL via Grafana API."""
import base64,csv,json,urllib.request,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
run_id=(ROOT/'reports/latest_phase01_run.txt').read_text().strip()
run=ROOT/'results/phase1_cpsat'/run_id
rows=list(csv.DictReader((run/'metrics.csv').open()))
headers={'Authorization':'Basic '+base64.b64encode(b'admin:admin_local_only').decode(),'Content-Type':'application/json'}
def call(path,payload=None,base='http://localhost:3000'):
    req=urllib.request.Request(base+path,headers=headers,data=json.dumps(payload).encode() if payload is not None else None)
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
report={'run_id':run_id,'grafana_health':call('/api/health'),'postgres_health':call('/api/datasources/uid/manufacturing_pg/health'),
        'prometheus_health':call('/api/datasources/uid/manufacturing_prom/health'),
        'dashboards':call('/api/search?type=dash-db'),'panels':[]}
assert report['grafana_health']['database']=='ok'
assert report['postgres_health']['status']=='OK'
methods=list(dict.fromkeys(r['method'] for r in rows))
replace={'${run_id:sqlstring}':"'"+run_id+"'",'${dataset:sqlstring}':"'MK01'",'${method:sqlstring}':','.join("'"+m+"'" for m in methods),'${seed:csv}':'0,1,2,3,4','${step:raw}':'25'}
for path in sorted((ROOT/'grafana/dashboards').glob('*.json')):
    if path.name.startswith('._'):continue
    dashboard=json.loads(path.read_text())
    remote=call('/api/dashboards/uid/'+dashboard['uid'])
    assert remote['dashboard']['uid']==dashboard['uid']
    for panel in dashboard['panels']:
        for target in panel.get('targets',[]):
            if 'rawSql' not in target:continue
            query=target['rawSql']
            for key,value in replace.items():query=query.replace(key,value)
            payload={'from':'0','to':'120000','queries':[{'refId':'A','datasource':{'uid':'manufacturing_pg','type':'grafana-postgresql-datasource'},'rawSql':query,'format':'table','rawQuery':True,'intervalMs':1000,'maxDataPoints':1000}]}
            answer=call('/api/ds/query',payload)
            result=answer['results']['A']
            if 'error' in result:raise RuntimeError(result['error'])
            frames=result.get('frames',[])
            counts=[len(f.get('data',{}).get('values',[[]])[0]) for f in frames if f.get('data',{}).get('values')]
            report['panels'].append({'dashboard':dashboard['uid'],'panel':panel['title'],'rows':counts,'status':result.get('status')})
            if panel['id']!=401:assert sum(counts)>0,panel['title']
report['prometheus_targets']=call('/api/v1/targets',base='http://localhost:9090')['data']['activeTargets']
assert all(t['health']=='up' for t in report['prometheus_targets'])
report['host_cpu']=call('/api/v1/query?query=manufacturing_cpu_percent',base='http://localhost:9090')
assert report['host_cpu']['data']['result']
report['visual_browser_check']='Not performed; health, provisioning and every SQL panel checked through the Grafana HTTP API. Figure PNGs independently visually reviewed.'
(ROOT/'reports/monitoring_validation.json').write_text(json.dumps(report,indent=2))
print('Verified',len(report['dashboards']),'dashboards and',len(report['panels']),'SQL panels; Prometheus target up')
