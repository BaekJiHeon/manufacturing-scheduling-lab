"""Rebuild disposable PostgreSQL mirrors from authoritative project JSON/CSV files."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.campaign import ROOT,connect
from psycopg.types.json import Jsonb

def restore():
    with connect() as conn:
        counts={}
        for family in ['expanded_static','objectives_dynamic','ppo_pilot','multi_rl']:
            for path in sorted((ROOT/'results'/family).glob('*/metadata.json')):
                meta=json.loads(path.read_text());run_id=meta['run_id']
                conn.execute('INSERT INTO extended_runs VALUES (%s,%s) ON CONFLICT(run_id) DO UPDATE SET metadata=EXCLUDED.metadata',(run_id,Jsonb(meta)))
                rows=[json.loads(p.read_text()) for p in sorted(path.parent.glob('record_[0-9]*.json'))]
                for row in rows:conn.execute('INSERT INTO extended_records VALUES (%s,%s,%s) ON CONFLICT(run_id,step) DO UPDATE SET payload=EXCLUDED.payload',(run_id,row['step'],Jsonb(row)))
                actual=[r[0] for r in conn.execute('SELECT payload FROM extended_records WHERE run_id=%s ORDER BY step',[run_id])]
                if actual!=rows:raise RuntimeError('Restoration mismatch')
                counts[run_id]=len(rows)
        print(counts)
if __name__=='__main__':restore()
