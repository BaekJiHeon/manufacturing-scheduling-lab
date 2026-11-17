SELECT step,metric,value FROM training_metrics WHERE run_id=${run_id:sqlstring} ORDER BY step;
