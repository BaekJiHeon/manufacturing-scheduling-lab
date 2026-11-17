SELECT * FROM operation_schedules WHERE run_id=${run_id:sqlstring} AND step=${step:raw} ORDER BY machine,start;
