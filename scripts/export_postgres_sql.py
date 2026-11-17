"""Create idempotent SQL for the latest repeated experiment outputs.
Used as mounted psql init when local Grafana stack is first created.
"""
import csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader(open(ROOT/'results/phase1/repeated_baselines.csv')))
out=ROOT/'postgres'/'02-phase1.sql'
with open(out,'w') as f:
    f.write('''CREATE TABLE IF NOT EXISTS repeated_experiment_metrics (
 instance TEXT NOT NULL, scenario_seed INT NOT NULL, method TEXT NOT NULL,
 makespan INT NOT NULL, total_tardiness INT NOT NULL,
 runtime_ms DOUBLE PRECISION, due_date_source TEXT NOT NULL,
 PRIMARY KEY (instance, scenario_seed, method));\n''')
    for r in rows:
        f.write("INSERT INTO repeated_experiment_metrics(instance,scenario_seed,method,makespan,total_tardiness,runtime_ms,due_date_source) VALUES ('%s',%d,'%s',%d,%d,%.6f,'%s') ON CONFLICT (instance,scenario_seed,method) DO UPDATE SET makespan=EXCLUDED.makespan,total_tardiness=EXCLUDED.total_tardiness,runtime_ms=EXCLUDED.runtime_ms;\n"%(r['instance'],int(r['scenario_seed']),r['method'],int(r['makespan']),int(r['total_tardiness']),float(r['runtime_ms']),r['due_date_source']))
print(out)
