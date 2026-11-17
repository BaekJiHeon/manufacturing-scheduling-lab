"""Validate all new panels through the actual Grafana datasource API."""
import base64,json,sys,time,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.campaign import ROOT
headers={'Authorization':'Basic '+base64.b64encode(b'admin:admin_local_only').decode(),'Content-Type':'application/json'}
def api(path,payload=None):
    return json.load(urllib.request.urlopen(urllib.request.Request('http://localhost:3000'+path,headers=headers,data=json.dumps(payload).encode() if payload else None),timeout=30))
def main():
    dashboard=api('/api/dashboards/uid/research-multi-rl')['dashboard']
    rid=(ROOT/'reports/latest_multi_rl_run.txt').read_text().strip()
    checks=[]
    for panel in dashboard['panels']:
        query=panel['targets'][0].copy()
        if 'rawSql' in query:query['rawSql']=query['rawSql'].replace('${run_id:sqlstring}',"'"+rid+"'")
        result=api('/api/ds/query',dict(queries=[query],**{'from':str(int(time.time()*1000)-10800000),'to':str(int(time.time()*1000))}))['results']['A']
        if result.get('error'):raise RuntimeError((panel['title'],result))
        values=[v for f in result.get('frames',[]) for field,col in zip(f['schema']['fields'],f['data']['values']) if field['type']=='number' for v in col if v is not None]
        if panel['type'] in ['gauge','stat']:
            assert values,(panel['title'],result)
            if panel['id']==1002:assert abs(values[-1]-100)<1e-8
            if panel['id']==1003:assert values[-1]==20
        checks.append(dict(panel=panel['title'],ok=True,frames=len(result.get('frames',[])),last_numeric_value=values[-1] if values else None))
    (ROOT/'reports/multi_rl_dashboard_validation.json').write_text(json.dumps(dict(run_id=rid,checks=checks),indent=2))
    print('Validated panels:',len(checks))
if __name__=='__main__':main()
