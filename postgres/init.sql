CREATE TABLE IF NOT EXISTS experiment_metrics (
 id SERIAL PRIMARY KEY, instance TEXT NOT NULL, method TEXT NOT NULL,
 makespan INTEGER NOT NULL, total_tardiness INTEGER,
 runtime_ms DOUBLE PRECISION, source TEXT NOT NULL,
 recorded_at TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO experiment_metrics(instance,method,makespan,total_tardiness,runtime_ms,source) VALUES('MK01','FIFO',51,76,3.843547000002445,'static_heuristic');
INSERT INTO experiment_metrics(instance,method,makespan,total_tardiness,runtime_ms,source) VALUES('MK01','SPT',55,59,1.0883510000212482,'static_heuristic');
INSERT INTO experiment_metrics(instance,method,makespan,total_tardiness,runtime_ms,source) VALUES('MK01','EDD',54,53,0.9608599999921807,'static_heuristic');
INSERT INTO experiment_metrics(instance,method,makespan,total_tardiness,runtime_ms,source) VALUES('MK01','MWKR',48,114,1.345347000011543,'static_heuristic');
INSERT INTO experiment_metrics(instance,method,makespan,total_tardiness,runtime_ms,source) VALUES('MK01','Random',59,80,1.0691449999740144,'static_heuristic');
