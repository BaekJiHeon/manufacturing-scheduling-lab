"""Transactional, idempotent CSV ingestion and full-row round-trip verification."""
import argparse,csv,json,os
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
ROOT=Path(__file__).resolve().parents[1]

def ingest(run):
    metadata=json.loads((run/'metadata.json').read_text())
    dsn=os.getenv('MANUFACTURING_DB_DSN','postgresql://demo:demo_local_only@localhost:5432/manufacturing_rl')
    with psycopg.connect(dsn) as conn:
        conn.execute((ROOT/'postgres/03-research.sql').read_text())
        conn.execute('INSERT INTO research_runs VALUES (%s,%s,%s,%s) ON CONFLICT(run_id) DO UPDATE SET status=EXCLUDED.status,metadata=EXCLUDED.metadata',
                     (metadata['run_id'],metadata['status'],metadata['created_at'],Jsonb(metadata)))
        counts={}
        for file,table,keys in [('metrics.csv','evaluation_metrics',['run_id','step']),('schedules.csv','operation_schedules',['run_id','step','job','operation'])]:
            rows=list(csv.DictReader((run/file).open()));columns=list(rows[0]);values=[[None if r[k]=='' else r[k] for k in columns] for r in rows]
            query=sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}').format(
                sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(sql.Placeholder() for _ in columns),
                sql.SQL(',').join(map(sql.Identifier,keys)),sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(k),sql.Identifier(k)) for k in columns if k not in keys))
            with conn.cursor() as cur:cur.executemany(query,values)
            actual=conn.execute(sql.SQL('SELECT {} FROM {} WHERE run_id=%s ORDER BY {}').format(sql.SQL(',').join(map(sql.Identifier,columns)),sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,keys))),[metadata['run_id']]).fetchall()
            expected=sorted(rows,key=lambda r:tuple(int(r[k]) if k!='run_id' else r[k] for k in keys))
            if len(actual)!=len(expected):raise RuntimeError('DB row count differs from CSV')
            for db,csv_row in zip(actual,expected):
                for k,value in zip(columns,db):
                    source=csv_row[k]
                    if value is None:
                        assert source=='',(table,k,source,value)
                    elif isinstance(value,(int,float)):
                        assert float(source)==value,(table,k,source,value)
                    else:assert str(value)==source,(table,k,source,value)
            counts[table]=len(actual)
    (run/'db_validation.json').write_text(json.dumps(dict(run_id=metadata['run_id'],all_cells_match=True,counts=counts),indent=2))
    print(counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);a=p.parse_args();ingest(ROOT/'results/phase1_cpsat'/a.run_id)
