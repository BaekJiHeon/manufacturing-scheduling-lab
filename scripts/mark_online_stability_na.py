"""Correct non-applicable revision fields; preserve old empty-reference placeholders."""
import csv,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.campaign import ROOT,connect
from psycopg.types.json import Jsonb
rid=(ROOT/'reports/latest_ppo_pilot_run.txt').read_text().strip();folder=ROOT/'results/ppo_pilot'/rid
meta=json.loads((folder/'metadata.json').read_text());assert meta['status']=='completed'
rows=[];old=[]
for file in sorted(folder.glob('record_[0-9]*.json')):
    r=json.loads(file.read_text())
    if r.get('record_type')=='test' and r['method']!='CP-SAT':
        fields=['stability_cost','start_shift','machine_changes','reference_operations']
        if any(r.get(k) is not None for k in fields):old.append(dict(step=r['step'],original={k:r.get(k) for k in fields}))
        r.update({k:None for k in fields});r['stability_applicable']=False;file.write_text(json.dumps(r,indent=2))
    rows.append(r)
if old:(folder/'original_empty_reference_placeholders.json').write_text(json.dumps(old,indent=2))
meta['metric_annotation']='Online dispatch methods publish no advance schedule. Revision fields are N/A; original empty-reference zero placeholders are preserved separately. Scheduling/timing/learning measurements unchanged.'
meta['metric_annotation_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(folder/'metadata.json').write_text(json.dumps(meta,indent=2))
scalar=[{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in rows];keys=list(dict.fromkeys(k for r in scalar for k in r))
with (folder/'metrics.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,keys);w.writeheader();w.writerows(scalar)
with connect() as conn:
    conn.execute('UPDATE extended_runs SET metadata=%s WHERE run_id=%s',(Jsonb(meta),rid))
    for r in rows:conn.execute('UPDATE extended_records SET payload=%s WHERE run_id=%s AND step=%s',(Jsonb(r),rid,r['step']))
    actual=[x[0] for x in conn.execute('SELECT payload FROM extended_records WHERE run_id=%s ORDER BY step',[rid])]
    if actual!=rows:raise RuntimeError('JSON DB mismatch')
    for a,b in zip(csv.DictReader((folder/'metrics.csv').open()),actual):
        for k,v in a.items():
            if v!=('' if b.get(k) is None else str(b[k])):raise RuntimeError('CSV DB mismatch')
(folder/'db_validation.json').write_text(json.dumps(dict(all_json_and_csv_cells_match=True,records=len(rows),after_na_annotation=True),indent=2))
print('N/A annotation applied; all cells verified',len(old))
