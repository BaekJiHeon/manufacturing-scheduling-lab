"""Append-only experiment records, local JSON/CSV and transactional PostgreSQL mirror."""
import csv, hashlib, importlib.metadata, json, platform, subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg.types.json import Jsonb
ROOT=Path(__file__).resolve().parents[2]
DSN='postgresql://demo:demo_local_only@localhost:5432/manufacturing_rl'
DDL='''CREATE TABLE IF NOT EXISTS extended_runs(run_id text PRIMARY KEY, metadata jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS extended_records(run_id text REFERENCES extended_runs, step integer, payload jsonb NOT NULL, PRIMARY KEY(run_id,step));'''

def connect():
    conn=psycopg.connect(DSN);conn.execute(DDL);conn.commit();return conn

class Campaign:
    def __init__(self, name, config, run_id=None):
        self.run_id=run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
        self.path=ROOT/'results'/name/self.run_id;self.path.mkdir(parents=True,exist_ok=bool(run_id))
        self.conn=connect();self.records=[]
        self.meta=dict(run_id=self.run_id,name=name,status='running',created_at=datetime.now(timezone.utc).isoformat(),config=config,
          python=platform.python_version(),platform=platform.platform(),git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
          source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').rglob('*.py') if not p.name.startswith('._')})
        if run_id:
            old=json.loads((self.path/'metadata.json').read_text());self.meta['created_at']=old['created_at']
            self.meta['previous_attempts']=old.get('previous_attempts',[])+[{k:old[k] for k in ['status','error','source_sha256','finished_at'] if k in old}]
            self.records=[json.loads(p.read_text()) for p in sorted(self.path.glob('record_[0-9]*.json'))]
        self.save_meta()
        for row in self.records:
            self.conn.execute('INSERT INTO extended_records VALUES (%s,%s,%s) ON CONFLICT(run_id,step) DO UPDATE SET payload=EXCLUDED.payload',(self.run_id,row['step'],Jsonb(row)))
        self.conn.commit();print('RUN',self.run_id,flush=True)
    def save_meta(self):
        (self.path/'metadata.json').write_text(json.dumps(self.meta,indent=2))
        self.conn.execute('INSERT INTO extended_runs VALUES (%s,%s) ON CONFLICT(run_id) DO UPDATE SET metadata=EXCLUDED.metadata',(self.run_id,Jsonb(self.meta)));self.conn.commit()
    def add(self, record):
        row=dict(run_id=self.run_id,step=len(self.records),recorded_at=datetime.now(timezone.utc).isoformat(),**record)
        # Round-trip through JSON so numpy values cannot silently enter the DB.
        row=json.loads(json.dumps(row));self.records.append(row)
        (self.path/f'record_{row["step"]:04d}.json').write_text(json.dumps(row,indent=2))
        self.conn.execute('INSERT INTO extended_records VALUES (%s,%s,%s)',(self.run_id,row['step'],Jsonb(row)));self.conn.commit()
        scalar=[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in self.records]
        keys=list(dict.fromkeys(k for r in scalar for k in r))
        with (self.path/'metrics.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,keys);w.writeheader();w.writerows(scalar)
        print(json.dumps({k:row[k] for k in ['step','instance','method','status','makespan','total_tardiness','runtime_ms'] if k in row}),flush=True)
    def finish(self, error=None):
        self.conn.rollback()
        self.meta.update(status='failed' if error else 'completed',finished_at=datetime.now(timezone.utc).isoformat(),records=len(self.records))
        if error:self.meta['error']=str(error)
        self.save_meta()
        db=[r[0] for r in self.conn.execute('SELECT payload FROM extended_records WHERE run_id=%s ORDER BY step',[self.run_id])]
        if db!=self.records:raise RuntimeError('PostgreSQL JSON round-trip mismatch')
        with (self.path/'metrics.csv').open() as f:
            csv_rows=list(csv.DictReader(f))
        if len(csv_rows)!=len(db):raise RuntimeError('CSV count mismatch')
        for a,b in zip(csv_rows,db):
            for k,v in a.items():
                if v!=('' if b.get(k) is None else str(b[k])):raise RuntimeError((k,v,b.get(k)))
        (self.path/'db_validation.json').write_text(json.dumps(dict(all_json_and_csv_cells_match=True,records=len(db)),indent=2))
        self.conn.close()

def instance_path(i):
    return ROOT/'data/raw/mk01.txt' if i=='MK01' else ROOT/'data/raw/brandimarte'/f'{i.lower()}.txt'

def bks():
    return {r['instance'].upper():r for r in json.loads((ROOT/'data/raw/brandimarte/provenance.json').read_text())['bks']}
