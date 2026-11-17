CREATE TABLE IF NOT EXISTS research_runs (
 run_id TEXT PRIMARY KEY, status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
 metadata JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluation_metrics (
 run_id TEXT NOT NULL REFERENCES research_runs(run_id), step INTEGER NOT NULL,
 instance TEXT NOT NULL, method TEXT NOT NULL, seed INTEGER NOT NULL,
 due_seed INTEGER NOT NULL, time_limit_s DOUBLE PRECISION NOT NULL, status TEXT NOT NULL,
 makespan DOUBLE PRECISION, total_tardiness DOUBLE PRECISION,
 mean_tardiness DOUBLE PRECISION, on_time_delivery_rate DOUBLE PRECISION,
 machine_utilization DOUBLE PRECISION, machine_idle_time DOUBLE PRECISION,
 constraint_violation_count INTEGER, runtime_ms DOUBLE PRECISION,
 solver_runtime_ms DOUBLE PRECISION, model_build_ms DOUBLE PRECISION,
 best_bound DOUBLE PRECISION, relative_bound_gap DOUBLE PRECISION, bks_gap DOUBLE PRECISION,
 PRIMARY KEY (run_id,step)
);
CREATE TABLE IF NOT EXISTS operation_schedules (
 run_id TEXT NOT NULL, step INTEGER NOT NULL, job INTEGER NOT NULL,
 operation INTEGER NOT NULL, machine INTEGER NOT NULL,
 start DOUBLE PRECISION NOT NULL, "end" DOUBLE PRECISION NOT NULL, duration DOUBLE PRECISION NOT NULL,
 PRIMARY KEY(run_id,step,job,operation),
 FOREIGN KEY(run_id,step) REFERENCES evaluation_metrics(run_id,step),
 CHECK ("end">start AND duration>0)
);
CREATE TABLE IF NOT EXISTS training_metrics (
 run_id TEXT NOT NULL REFERENCES research_runs(run_id), step BIGINT NOT NULL,
 metric TEXT NOT NULL, value DOUBLE PRECISION, recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 PRIMARY KEY (run_id,step,metric)
);
