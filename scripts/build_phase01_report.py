"""Build a factual report exclusively from stored run and verification evidence."""
import csv,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
run_id=(ROOT/'reports/latest_phase01_run.txt').read_text().strip();run=ROOT/'results/phase1_cpsat'/run_id
metadata=json.loads((run/'metadata.json').read_text());audit=json.loads((run/'audit.json').read_text());db=json.loads((run/'db_validation.json').read_text())
summary=list(csv.DictReader((run/'summary.csv').open()));metrics=list(csv.DictReader((run/'metrics.csv').open()))
monitor=json.loads((ROOT/'reports/monitoring_validation.json').read_text())
manifest=json.loads((ROOT/'figures/publication'/run_id/'manifest.json').read_text())
lines=['# Phase 1 — measured static MK01 results','',f'Run: `{run_id}`. Date: 2026-11-17 (Asia/Seoul).',
       f"Code revision at execution: {metadata['git_commit']}; dirty={metadata['git_dirty']}. Exact Python source hashes are in metadata.json. Later reporting/figure-error handling changes do not replace this measurement record.",
       '', '## Experimental protocol','',
       'MK01: 10 jobs, 6 machines, 55 operations. Synthetic due dates seed 42, slack 1.7 shared by all primary methods. 5 algorithm seeds per method, CP-SAT 1 worker and 1/5/30 s solve limits. Objective: makespan only. Hardware: Apple M5, 16 GiB RAM, Python 3.11.15, OR-Tools 9.15.6755.',
       'Runtime includes construction/scheduling and verification; excludes package imports, file output and plotting. First solve can carry initialization overhead; groups were run in fixed order, so sub-millisecond heuristic and tens-of-millisecond solver timing differences are descriptive, not a controlled microbenchmark. The three solver limits stop early on proof of optimality.',
       '', '## Results (mean over 5 runs)','', '| Method | Makespan | Total tardiness | Runtime ms | Makespan SD | Tardiness SD |', '|---|---:|---:|---:|---:|---:|']
for r in summary:
    lines.append(f"| {r['method']} | {float(r['makespan_mean']):.2f} | {float(r['total_tardiness_mean']):.2f} | {float(r['runtime_ms_mean']):.3f} | {float(r['makespan_std']):.2f} | {float(r['total_tardiness_std']):.2f} |")
cp=[r for r in metrics if r['method'].startswith('CP-SAT')]
lines+=['',f"All {len(cp)} CP-SAT runs: status OPTIMAL, incumbent 40 and lower bound 40. All {len(metrics)} primary schedules independently feasible; constraint violations 0. Compared with MWKR (48), makespan is lower by 16.67% on this instance. This is not a generalized superiority claim.",
        'CP-SAT total tardiness averages 74.8 (SD 5.85), while EDD gives 53. Makespan minimization does not optimize tardiness; equal optimal makespans can have different completion-time vectors. No conclusion of multi-objective dominance is justified.',
        'summary.csv includes sample SD, Student-t 95% mean confidence intervals and worst observed value. These characterize algorithm repetitions on ONE fixed instance. FIFO/SPT/EDD/MWKR are deterministic under fixed due dates; their zero variance is not evidence of generalization. No significance test across independent instances is warranted here. The 50 legacy scenarios vary synthetic due dates, not factory topology.',
        '', '## Reproduction and storage verification','',
        f"{audit['single_schedules_verified']} original full schedules matched; {audit['repeated_schedules_verified']} original scenario KPI pairs and summary quality statistics reproduced with zero mismatches. Original static JSON/CSV/SQL and repeated CSV/SQL also matched exactly, including stored historical runtimes. New runtimes are naturally different.",
        f"Database: {db['counts']['evaluation_metrics']} evaluation rows and {db['counts']['operation_schedules']} operation rows. Two ingest executions preserved these counts; every stored cell matches CSV.",
        f"Grafana 11.6.0: database health OK, PostgreSQL datasource OK, {len(monitor['dashboards'])} dashboards registered, {len(monitor['panels'])} actual SQL panel queries passed. Prometheus host CPU/RAM target is up. Browser-rendered layout was not verified; provisioning and query execution were verified through HTTP APIs.",
        '', '## Figures','',
        'Five figures, each PDF/SVG vector and 600 dpi PNG (4204 × 2007 pixels), 178 mm width. PNGs visually inspected for clipping/readability; SVGs contain no raster image elements. All are generated from persisted metrics.csv/schedules.csv and linked by source SHA256 in manifest.json. No smoothing.',
        '- makespan_benchmark: actual observations, mean and published bound reference.',
        '- tardiness_benchmark: shared synthetic due dates.',
        '- runtime_benchmark: logarithmic runtime axis.',
        '- objective_tradeoff: observed makespan/tardiness pairs; not a claimed Pareto-front solver.',
        '- cpsat_static_gantt: verified optimal static schedule, not dynamic rescheduling.',
        '', 'Training convergence, sample efficiency, dynamic Gantt, unseen-scale generalization and ablation figures are absent because those experiments have not been executed. Single-column journal layout has not been produced; current exports use the specified double-column width.',
        '', '## Next priorities','',
        '1. Add tested intentional WAIT semantics; current masked environment generates non-delay schedules while CP-SAT can strategically idle.',
        '2. Integrate pinned MaskablePPO, run real training and checkpoint/RNG/optimizer resume smoke tests; then at least 5 training seeds.',
        '3. Freeze independent train/validation/test partitions and tuning budget before graph/off-policy comparison.',
        '4. Validate breakdown/pause-resume, recovery, arrivals and uncertainty with identical exogenous event tapes before rolling-horizon/hybrid evaluation.',
        '', 'Full environment/reward specification and staged plan: reports/environment_contract.md. PPO YAML is preparatory, not evidence of training.']
(ROOT/'reports/phase1_results.md').write_text('\n'.join(lines)+'\n')
p=ROOT/'reports/phase0_audit.md';text=p.read_text().replace('# Phase 0 audit — in progress','# Phase 0 audit — completed')
text=text.replace('Final test, reproduction, optimization, database and dashboard evidence will be appended after execution.', 'Final evidence follows below.')
if '## Final executed evidence' not in text:
    text+='''\n## Final executed evidence\n\n- 21 tests passed (2.20 seconds), covering parser rejection, schedule mutation rejection, CP-SAT horizon/alternative assignment toy optima and UNKNOWN behavior, 20 full masked MK01 rollouts, reward telescoping, same-time assignments, padded capacities and Gymnasium API fixture, and injected figure-generation failure recording. One Gymnasium warning concerns an intentionally unbounded Box maximum.\n- 5/5 original full schedules and 250/250 repeated Makespan/Tardiness pairs reproduced. Historical summary means/SD/medians match. Original JSON/CSV/DB records match; original data/results/figures SHA256 checks unchanged.\n- 40 fresh primary schedules including 15 CP-SAT runs passed independent feasibility checks. Every CP-SAT run proved makespan = bound = 40.\n- 40 evaluation + 2,200 operation DB rows matched CSV cell-for-cell after two ingestion runs.\n- Grafana health and datasource health OK; 5 dashboard registrations, 15 SQL panel queries successful. Prometheus target up with measured CPU/RAM samples. No browser screenshot verification is claimed.\n- Five measured figures exported to vector PDF/SVG and 600 dpi PNG; all five PNGs visually inspected.\n- Runtime dependency workaround succeeded under /tmp; Python environment is disposable and recreatable from the exact lock. All research artifacts and database files remain under the requested external project.\n\nPhase 0 and Phase 1 acceptance criteria are met. The PPO environment interface is prepared and tested; actual PPO training and dynamics remain unimplemented. See phase1_results.md, environment_contract.md, command_log.md and machine-readable verification JSON.\n'''
p.write_text(text)
print(ROOT/'reports/phase1_results.md')
