from pathlib import Path
import csv,json,hashlib
import psycopg
ROOT=Path(__file__).resolve().parents[1]
records=json.loads((ROOT/'results/mk01_results.json').read_text())['results']
summary=list(csv.DictReader((ROOT/'results/mk01_summary.csv').open()))
with psycopg.connect('postgresql://demo:demo_local_only@localhost:5432/manufacturing_rl') as conn:
    old_db=conn.execute('SELECT method,makespan,total_tardiness,runtime_ms FROM experiment_metrics ORDER BY method').fetchall()
    for record in records:
        csv_row=next(x for x in summary if x['rule']==record['rule'])
        db_row=next(x for x in old_db if x[0]==record['rule'])
        for col,idx in [('makespan',1),('total_tardiness',2),('runtime_ms',3)]:
            assert float(csv_row[col])==record[col]==db_row[idx]
    repeated=list(csv.DictReader((ROOT/'results/phase1/repeated_baselines.csv').open()))
    db=conn.execute('SELECT scenario_seed,method,makespan,total_tardiness,runtime_ms FROM repeated_experiment_metrics').fetchall()
    indexed={(int(x['scenario_seed']),x['method']):x for x in repeated}
    assert len(db)==len(repeated)==250
    for seed,method,makespan,tardiness,runtime in db:
        r=indexed[seed,method]
        assert (makespan,tardiness,runtime)==(int(r['makespan']),int(r['total_tardiness']),float(r['runtime_ms']))
answer={'legacy_single_json_csv_db_exact_match':True,'legacy_repeated_csv_db_exact_match':True,'single_rows':5,'repeated_rows':250}
(ROOT/'reports/legacy_storage_validation.json').write_text(json.dumps(answer,indent=2));print(answer)
