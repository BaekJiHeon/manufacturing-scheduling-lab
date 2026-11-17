# Expanded CP-SAT audit, objectives, dynamics, and Maskable PPO pilot

This campaign implements the four steps authorized after the MK01 audit. It does not claim to complete all seven algorithm families in the original roadmap.

## Data and splits

MK01–MK10 are separate Brandimarte instances from ScheduleOpt/benchmarks at commit 8a6e36ef31263d36975e56fb481e0ba04e188d6f. Raw texts and SHA-256 provenance are under data/raw; source license was preserved in Phase 0. BKS means the repository's pinned best-known upper bound, not a proof by this experiment. MK10 has lower/upper bounds 189/193 in that snapshot. Synthetic due dates use seed 42 and the inherited minimum-work slack generator. Seeds within one instance are solver repeats, not independent factories.

Static scalability: all ten instances × three solver seeds × 1/5/30-second solver limits, plus five dispatch rules × three seeds. This preserves the original, unhinted CP-SAT formulation. Its limit excludes model construction and validation, which are separately measured. A limited incumbent can be worse than a heuristic; no fallback is silently substituted.

Objectives: MK01, MK06, MK10 × three seeds × 1/5 seconds × four objective settings. Settings are makespan (1,0,0), mean tardiness (0,1,0), balanced (1,1,0), stable (1,1,1). The static reference is the same SPT schedule for all settings. This comparison is exploratory and was fixed before outcomes.

Dynamics: MK01/MK06 × three event seeds × breakdown/arrival/combined. Compare Repair, SPT, EDD, MWKR, and CP-SAT at 1/5 seconds with balanced/stable objectives. Each method receives the exact same exogenous tape. Recovery is an additional replanning event. Method schedules can cause different operations to be interrupted by the same event; that is an outcome, not a different disturbance.

## Objective and feasibility contract

At a planning epoch, H is the sum of maximum eligible durations of every currently known operation, n is the number of known jobs, and R is the previously planned operations which have not begun. q=max(1,|R|).

J = wm*Cmax/H + wt*Ttotal/(n*H)
  + ws*[sum_R |new_start-old_start|/(q*H) + changed_machine_count/q].

New jobs and already started operations are excluded from R. All weights are nonnegative integers in configuration. Multiplying by n*q*H yields the exact integer CP objective; there is no rounding of normalized weights. When R is empty its stability contribution is zero. Full schedule metrics and the model expression are independently recomputed. A solver response objective discrepancy is retained explicitly; a discrepant OPTIMAL response is downgraded and inconsistent bounds are discarded. Bounds in this campaign use normalized objective units, whereas the original static campaign reports raw makespan bounds.

Four verified greedy schedules are built and scored within each rolling solver budget. The best is supplied as a hint and retained as a fallback. Model construction, candidate generation, solve, extraction, and validation are included in measured runtime. Solver time is the remaining budget after preparation. Validation/postprocessing can slightly overrun the wall budget; each overrun is reported. This is a measured soft wall budget, not a hard real-time guarantee. An external fallback does not become a solver incumbent or an OPTIMAL certificate.

## Dynamic assumptions

At an event, starts strictly before event time are frozen. Events at the same timestamp happen before new dispatches. Completed operations are immutable. A running operation interrupted by breakdown pauses, retains its processed work and assigned machine, and resumes on that machine at recovery. Final operation duration is checked from active segments after subtracting downtime. No restart or scrap penalty is modeled.

The simulator alone owns the complete tape. Planners and policies see only events already reached. The repair completion time is revealed when a failure occurs and is exact in this experiment. Unknown repair duration, processing-time uncertainty, overlapping repeated failures, operational/energy cost, and real factory data remain outside this campaign. These limits must not be hidden behind the term dynamic scheduling.

Planning freezes simulated production time. Wall milliseconds and benchmark time units have no asserted conversion. We report planning latency but do not claim that no production elapses while computing in a real factory. This restriction applies equally to all methods. Cumulative stability is the sum of revisions, not the difference between final schedule and the initial schedule.

## PPO pilot

Library: sb3-contrib MaskablePPO, MultiInputPolicy, padded MLP actor/critic. The locked configuration is configs/algorithms/ppo_pilot.json. Five seeds, 32,768 environment steps each, four synchronous environments, one fixed hyperparameter setting, no search. No model selection uses test outcomes; the final checkpoint is primary.

Train distribution: generated 4–10 jobs, 3–6 machines, 3–6 operations/job, duration 1–10, 1–3 eligible machines. Half of deterministic episode seeds produce static episodes and half combined events. Training episode seed lists are saved. Validation seeds 9,000,000–9,000,003 and test seeds 9,100,000–9,100,009 are disjoint from training. Their complete specifications are saved before training. Brandimarte problems were inspected during the audit and are described as external transfer tests, not pristine blind tests. Scales beyond the train distribution are reported separately.

The policy capacity is 260 operations and 15 machines, with zero padding. It is not a variable-size graph network. Unarrived jobs have no populated slots. Constant observation normalization prevents revealing future job counts or processing times. WAIT advances to a strictly later event and is enabled only by observed running work/repair, not by hidden future events. The simulator may interrupt a wait when an exogenous event occurs. This removes the old non-delay-only restriction, but does not prove that the policy represents every offline schedule.

With gamma=1, reward sum is exactly -(wm*Cmax + wt*mean_tardiness)/100, including a correction if the last recovery occurs after production completion. Multiple assignments at one time do not duplicate time penalties. No extra shaping is used. PPO produces online dispatches rather than revisable advance schedules, so its rescheduling stability is N/A; its primary comparison uses CP-SAT's balanced objective (ws=0). Feasibility, makespan, tardiness and computation cost are shared outcomes.

CPU vs MPS single-observation inference was measured with 100 repeats; CPU was selected from the measured result (reports/ppo_device_profile.json). CPU thread count is one. Learning logs include policy/value loss, entropy, KL, explained variance, pre-clipping gradient norm, steps/s and process RAM. Checkpoints contain optimizer, Python/NumPy/Torch RNG, simulator state and last observation. An exact CPU continuation test compares every parameter after resumption. These pickle sidecars are trusted local artifacts only.

## Storage, timing, and reproducibility limits

Two single-worker CP campaigns run concurrently on separate host cores. They share a desktop host and were not executed under isolated laboratory timing conditions. PPO starts after those campaigns complete. Wall-limited search paths may vary across repeats despite fixed random seeds.

PostgreSQL on the FAT32 bind mount produced a real `unexpected data beyond EOF` error during JSON writes. Existing files and SQL snapshots were preserved. The authoritative record is per-evaluation JSON plus scalar CSV under results. PostgreSQL now uses disposable tmpfs; scripts/start_monitoring.sh reconstructs it from project artifacts after a restart. scripts/restore_extended.py checks every restored JSON record; completed campaigns also compare all scalar CSV cells. No database storage outside the project is treated as a permanent artifact. Docker's runtime and Python dependency caches are disposable.

A failed objective-validation run remains in results with failed status. The static run and corrected objective run retain resume metadata. Partial runs are excluded from reported final comparisons. Publication figures must read saved result files; no illustrative values or smoothed learning curves substitute for measured results.

## Primary implementation references

- https://developers.google.com/optimization/cp/cp_solver
- https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html
- https://github.com/ScheduleOpt/benchmarks/tree/8a6e36ef31263d36975e56fb481e0ba04e188d6f/flexible-jobshop
