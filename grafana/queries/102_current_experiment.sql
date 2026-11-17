SELECT run_id,status,created_at,metadata->>'elapsed_s' AS elapsed_seconds,metadata->>'git_commit' AS git_commit FROM research_runs WHERE run_id=${run_id:sqlstring};
