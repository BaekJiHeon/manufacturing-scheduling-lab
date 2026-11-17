# Phase 1 — measured static MK01 results

Run: `20261117T053721Z-c77ef3ce`. Date: 2026-11-17 (Asia/Seoul).
Code revision at execution: e27e3da00b9abd756cd21e556985ae897add8af0; dirty=True. Exact Python source hashes are in metadata.json. Later reporting/figure-error handling changes do not replace this measurement record.

## Experimental protocol

MK01: 10 jobs, 6 machines, 55 operations. Synthetic due dates seed 42, slack 1.7 shared by all primary methods. 5 algorithm seeds per method, CP-SAT 1 worker and 1/5/30 s solve limits. Objective: makespan only. Hardware: Apple M5, 16 GiB RAM, Python 3.11.15, OR-Tools 9.15.6755.
Runtime includes construction/scheduling and verification; excludes package imports, file output and plotting. First solve can carry initialization overhead; groups were run in fixed order, so sub-millisecond heuristic and tens-of-millisecond solver timing differences are descriptive, not a controlled microbenchmark. The three solver limits stop early on proof of optimality.

## Results (mean over 5 runs)

| Method | Makespan | Total tardiness | Runtime ms | Makespan SD | Tardiness SD |
|---|---:|---:|---:|---:|---:|
| FIFO | 51.00 | 76.00 | 0.482 | 0.00 | 0.00 |
| SPT | 55.00 | 59.00 | 0.479 | 0.00 | 0.00 |
| EDD | 54.00 | 53.00 | 0.451 | 0.00 | 0.00 |
| MWKR | 48.00 | 114.00 | 0.439 | 0.00 | 0.00 |
| Random | 58.20 | 107.20 | 0.655 | 8.14 | 16.33 |
| CP-SAT 1s | 40.00 | 74.80 | 40.540 | 0.00 | 5.85 |
| CP-SAT 5s | 40.00 | 74.80 | 37.245 | 0.00 | 5.85 |
| CP-SAT 30s | 40.00 | 74.80 | 34.076 | 0.00 | 5.85 |

All 15 CP-SAT runs: status OPTIMAL, incumbent 40 and lower bound 40. All 40 primary schedules independently feasible; constraint violations 0. Compared with MWKR (48), makespan is lower by 16.67% on this instance. This is not a generalized superiority claim.
CP-SAT total tardiness averages 74.8 (SD 5.85), while EDD gives 53. Makespan minimization does not optimize tardiness; equal optimal makespans can have different completion-time vectors. No conclusion of multi-objective dominance is justified.
summary.csv includes sample SD, Student-t 95% mean confidence intervals and worst observed value. These characterize algorithm repetitions on ONE fixed instance. FIFO/SPT/EDD/MWKR are deterministic under fixed due dates; their zero variance is not evidence of generalization. No significance test across independent instances is warranted here. The 50 legacy scenarios vary synthetic due dates, not factory topology.

## Reproduction and storage verification

5 original full schedules matched; 250 original scenario KPI pairs and summary quality statistics reproduced with zero mismatches. Original static JSON/CSV/SQL and repeated CSV/SQL also matched exactly, including stored historical runtimes. New runtimes are naturally different.
Database: 40 evaluation rows and 2200 operation rows. Two ingest executions preserved these counts; every stored cell matches CSV.
Grafana 11.6.0: database health OK, PostgreSQL datasource OK, 5 dashboards registered, 15 actual SQL panel queries passed. Prometheus host CPU/RAM target is up. Browser-rendered layout was not verified; provisioning and query execution were verified through HTTP APIs.

## Figures

Five figures, each PDF/SVG vector and 600 dpi PNG (4204 × 2007 pixels), 178 mm width. PNGs visually inspected for clipping/readability; SVGs contain no raster image elements. All are generated from persisted metrics.csv/schedules.csv and linked by source SHA256 in manifest.json. No smoothing.
- makespan_benchmark: actual observations, mean and published bound reference.
- tardiness_benchmark: shared synthetic due dates.
- runtime_benchmark: logarithmic runtime axis.
- objective_tradeoff: observed makespan/tardiness pairs; not a claimed Pareto-front solver.
- cpsat_static_gantt: verified optimal static schedule, not dynamic rescheduling.

Training convergence, sample efficiency, dynamic Gantt, unseen-scale generalization and ablation figures are absent because those experiments have not been executed. Single-column journal layout has not been produced; current exports use the specified double-column width.

## Next priorities

1. Add tested intentional WAIT semantics; current masked environment generates non-delay schedules while CP-SAT can strategically idle.
2. Integrate pinned MaskablePPO, run real training and checkpoint/RNG/optimizer resume smoke tests; then at least 5 training seeds.
3. Freeze independent train/validation/test partitions and tuning budget before graph/off-policy comparison.
4. Validate breakdown/pause-resume, recovery, arrivals and uncertainty with identical exogenous event tapes before rolling-horizon/hybrid evaluation.

Full environment/reward specification and staged plan: reports/environment_contract.md. PPO YAML is preparatory, not evidence of training.
