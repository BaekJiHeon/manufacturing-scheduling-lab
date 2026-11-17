# Phase 0 audit — completed

Date: 2026-11-17 (Asia/Seoul).

## Location and preservation
The requested manufacturing_rl directory was absent. Its parent existed and contained manufacturing_rl_phase1_complete.zip (41 entries). ZIP CRC integrity passed; all paths were checked to remain within manufacturing_rl and contain no symlink/path traversal entries. The archive was preserved and extracted to the exact requested root. NFC 취업자료 and NFD 취업자료 resolve to the same directory. A temporary write probe succeeded.

Original files and ZIP SHA256 are in reports/original_inventory.json. Initial Git snapshot: a1485cb. Git user was not configured; commits use command-local Codex <codex@local.invalid>, without modifying global identity. Original data/results/figures remain preserved.

## Data audit
Official repository commit: 8a6e36ef31263d36975e56fb481e0ba04e188d6f. data/raw/provenance.json records URLs, SHA256, Git blob hash, best-known bounds and conversion. Original MK01 data has 10 jobs / 6 machines / 55 operations. Legacy file differs only in whitespace: every integer token is equal. Downloaded raw text exactly matches Git blob 365d04a98ca8cd11a69a4e50ad9cfcf0fbacd5e0. No due dates or dynamic events are supplied by this benchmark.

## Findings and implemented fixes
- CP-SAT horizon incorrectly summed one maximum per job; corrected to sum each operation's maximum. A single-job chain regression test exposes the old failure.
- Schedule verifier did not assert end-start equals processing duration and could accept negative Python indices. Replaced with explicit exceptions, exact operation set, eligible/ranged machine checks, finite timestamps, interval consistency, precedence and machine disjointness. Validation no longer disappears under python -O.
- Parser now accepts fractional header flexibility and rejects empty alternatives, truncated/extra tokens, duplicate machines and nonpositive processing durations.
- Old CLIs overwrote fixed result/figure paths. New outputs use unique run directories; supplied historical files remain unchanged. Install helper refuses conflicting existing files.
- Dependencies were unbounded; Python 3.11 environment and exact lock added. macOS default Python is 3.14.7; experiment interpreter is separately recorded.
- New DB schema keys evaluation by (run_id, step), schedule by (run_id, step, job, operation), training metric by (run_id, step, metric). CSV ingestion is transactional/idempotent and verifies every stored cell.
- Docker was installed but stopped. Started existing Docker Desktop. FAT32 initial DB initialization exceeded old health timeout. Extended startup allowance; postgres runs as image UID 70 to avoid recursive chown of macOS AppleDouble files on restart. Grafana files are individually mounted to exclude ._ metadata.
- Generic compileall encounters ._*.py on FAT32; syntax checks explicitly exclude these binary metadata files. Initial pytest/import attempts before dependency installation completed failed due to incomplete packages; not treated as simulator test results.

## Validation status
Final evidence follows below. No RL training or dynamic experiment has been performed.

## Actual storage failures and workaround

- Direct uv installation to FAT32 failed after approximately 12 minutes: fonttools wheel relocation attempted to copy an AppleDouble `._ttx.1` file that did not exist. This environment is preserved at runtime/failed_venv_fat32.
- Project-local APFS sparsebundle creation succeeded; attachment failed (permission denied / no mountable filesystem). No reformat or privileged escalation was performed. Image retained at runtime/python-runtime.sparsebundle.
- Dependency-only temporary APFS environment under /tmp is permitted by the user exception for temporary files. Its exact executable is stored in runtime/python_path.txt; setup/launcher scripts reproduce it from the lock. All research outputs remain in the project. A first filesystem detection attempt used a subdirectory instead of the volume root, was stopped, and corrected to locate the mount root.
- Grafana's SQLite provisioning failed with readonly database on FAT32. Changed Grafana metadata backend to a separate grafana PostgreSQL database in the existing project-local cluster. Disabled unrelated automatic plugin preinstallation. Grafana health, datasource health and five dashboard registrations subsequently returned success.

## Final executed evidence

- 21 tests passed (2.20 seconds), covering parser rejection, schedule mutation rejection, CP-SAT horizon/alternative assignment toy optima and UNKNOWN behavior, 20 full masked MK01 rollouts, reward telescoping, same-time assignments, padded capacities and Gymnasium API fixture, and injected figure-generation failure recording. One Gymnasium warning concerns an intentionally unbounded Box maximum.
- 5/5 original full schedules and 250/250 repeated Makespan/Tardiness pairs reproduced. Historical summary means/SD/medians match. Original JSON/CSV/DB records match; original data/results/figures SHA256 checks unchanged.
- 40 fresh primary schedules including 15 CP-SAT runs passed independent feasibility checks. Every CP-SAT run proved makespan = bound = 40.
- 40 evaluation + 2,200 operation DB rows matched CSV cell-for-cell after two ingestion runs.
- Grafana health and datasource health OK; 5 dashboard registrations, 15 SQL panel queries successful. Prometheus target up with measured CPU/RAM samples. No browser screenshot verification is claimed.
- Five measured figures exported to vector PDF/SVG and 600 dpi PNG; all five PNGs visually inspected.
- Runtime dependency workaround succeeded under /tmp; Python environment is disposable and recreatable from the exact lock. All research artifacts and database files remain under the requested external project.

Phase 0 and Phase 1 acceptance criteria are met. The PPO environment interface is prepared and tested; actual PPO training and dynamics remain unimplemented. See phase1_results.md, environment_contract.md, command_log.md and machine-readable verification JSON.
