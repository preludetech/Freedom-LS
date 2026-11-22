# Timings

## First ranking run

- Commit tested: `732080502af9342b643656f1c755fb728a26beb0` (ranking committed as `1888541a0`).
- Main base SHA (`git merge-base HEAD main`): `0a72a807fc4f9abcee739a256cb702c972d0ab4a`.
- Command: `/usr/bin/time -v uv run python scripts/rank_test_costs.py` (`-n 4`, `--no-cov`, random order off).
- Result: 18775 passed, 3 skipped; 18778 tests recorded.
- Total CPU: 1378.2 s. Wall: 443.0 s. Summed test cost: 1456.1 s.
- Database setup: 65.7 s across 4 workers.
- Ratio total CPU seconds / summed test cost: 1378.2 / 1456.1 = 0.9465.
- Load average (1, 5, 15 min) and CPU pressure `some avg60`:
  - start: 10.26 10.88 9.41, 4.80
  - end: 7.33 9.85 9.60, 1.59

### Cross-check against `/usr/bin/time -v`

- User 1247.43 s + system 131.03 s = 1378.46 s. Header: 1378.2 s. Difference: 0.26 s (0.02%). Passes the 10% limit.
- `/usr/bin/time` wall: 7:23.25 (443.25 s). Max resident set size 842256 kB.

## Target

- Rule: S is the cumulative share in the 50th row of the top-functions table. Target = total CPU seconds x (1 - 1/2 x S).
- S = 28% (row 50: `freedom_ls/content_engine/tests/test_image_cache.py::test_unclaimed_webp_file_is_removed_by_write_manifests`).
- Target = 1378.2 x (1 - 0.5 x 0.28) = 1378.2 x 0.86 = **1185.3 CPU seconds**.
- 0.5% rule threshold = 0.005 x 1456.1 = **7.28 seconds** of test cost.

## Coverage before

- Command: `uv run pytest -m "not playwright and not dev_tooling" -n 4 --cov --cov-fail-under=92 --cov-report=json`.
- The plan writes `-n auto`. The coverage runs use `-n 4` instead, at the user's choice, because of memory pressure on the shared machine: a first run with `-n auto` was killed for low memory. The last coverage run must use the same `-n 4` command.
- Result: 18817 passed, 3 skipped; total coverage 96.55% (required 92%). Pytest time 1004.58 s; `/usr/bin/time` wall 16:49.93; max resident set size 1001480 kB.
- Load average and CPU pressure: start 18.32 17.61 18.65, 16.65; end 7.79 14.21 21.56, 1.47.
- Report: `.sdd-work/coverage_before.json`.

## "Before" samples

Serial, `-n 0 -p no:randomly --no-cov -p scripts.record_test_costs`, three runs each, fastest kept.

| App | Run | Load average at start | Test-body time (sum of `call`) | Wall | Database setup |
|---|---|---|---|---|---|
| course_access | 1 | 17.89 17.53 18.62 | 5.89 s | 33.9 s | 20.6 s |
| course_access | 2 | 18.53 17.78 18.67 | 4.80 s | 28.0 s | 17.5 s |
| course_access | 3 (kept) | 16.79 17.44 18.53 | 4.58 s | 28.8 s | 18.5 s |
| accounts | 1 | 15.61 17.11 18.38 | 22.45 s | 79.0 s | 23.5 s |
| accounts | 2 | 22.50 18.84 18.89 | 27.65 s | 90.8 s | 22.9 s |
| accounts | 3 (kept) | 30.34 22.08 20.01 | 20.61 s | 77.5 s | 25.4 s |

- course_access (230 tests): fastest test-body time 4.58 s. Copy: `.sdd-work/costs_course_access_before.json`.
- accounts (658 tests, 2 deselected): fastest run wall 77.5 s (pytest-reported 72.50 s), database setup 25.4 s. Copy: `.sdd-work/costs_accounts_before.json`.

## Coverage after

- Command: the coverage-before command, unchanged (`-n 4`).
- Result: 18815 passed, 3 skipped; total coverage 96.56% (required 92%). Pytest time 734.40 s; `/usr/bin/time` wall 12:19.28; max resident set size 865328 kB.
- Load average and CPU pressure: start 9.53 14.76 17.16, 4.77; end 19.99 21.01 18.05, 23.05.
- Report: `.sdd-work/coverage_after.json`. Per-file comparison: `pruned_tests.md`; no file lost coverage.

## "After" samples

Same commands and method as the "before" samples (serial, `-n 0 -p no:randomly --no-cov -p scripts.record_test_costs`, three runs each, fastest kept). The machine was busier than for the "before" samples, so these figures overstate the after state.

| App | Run | Load average at start | Test-body time (sum of `call`) | Wall | Database setup |
|---|---|---|---|---|---|
| course_access | 1 (kept) | 18.33 20.53 17.95 | 5.89 s | 33.55 s | 21.4 s |
| course_access | 2 | 18.70 20.39 18.00 | 10.01 s | 47.58 s | 28.1 s |
| course_access | 3 | 23.56 21.43 18.48 | 11.22 s | 50.72 s | 28.9 s |
| accounts | 1 (kept) | 26.79 22.59 19.03 | 26.14 s | 90.76 s | 24.9 s |
| accounts | 2 | 26.39 23.63 19.73 | 29.06 s | 97.69 s | 26.7 s |
| accounts | 3 | 28.32 25.19 20.68 | 25.16 s | 93.84 s | 26.4 s |

- course_access (230 tests): fastest test-body time 5.89 s (before 4.58 s). Copy: `.sdd-work/costs_course_access_after.json`.
- accounts (658 tests, 2 deselected): fastest run wall 90.76 s (before 77.5 s), database setup 24.9 s (before 25.4 s). Copy: `.sdd-work/costs_accounts_after.json`.
- Both apps are untouched by the pruning; the differences are load (1-minute load average 18 to 28 here, against 16 to 30 before, with the pressure and the slow runs both higher), not the code.

## Last ranking run

- Commit tested: `3f63bbee7ac5b4898086cedece5e75a2af511262` (ranking committed on top of it; the header names no `-dirty`).
- Main base SHA unchanged: `0a72a807fc4f9abcee739a256cb702c972d0ab4a` (no rebase between the first run and this one).
- Command: `/usr/bin/time -v uv run python scripts/rank_test_costs.py` (`-n 4`, `--no-cov`, random order off).
- Result: 18774 passed, 3 skipped; 18776 tests recorded (first run 18778: the pruning merged 4 tests into 2).
- Total CPU: 1680.1 s. Wall: 676.0 s. Summed test cost: 2419.0 s. Database setup: 84.2 s across 4 workers.
- Cross-check: `/usr/bin/time` user 1520.64 s + system 159.97 s = 1680.61 s against the header's 1680.1 s (0.03%). Wall 11:16.89. Max resident set size 837992 kB.
- Load average (1, 5, 15 min) and CPU pressure `some avg60`:
  - start: 15.89 26.47 25.47, 12.22
  - end: 32.58 30.93 27.31, 49.77
  - first run, for comparison: start 10.26 10.88 9.41, 4.80; end 7.33 9.85 9.60, 1.59.

## Result

- Target 1185.3 CPU seconds; last run 1680.1. **Over the target by 494.8 s, but the run is not comparable with the first.** The machine was far busier: CPU pressure avg60 12.22 at the start and 49.77 at the end (first run 4.80 and 1.59), and the 1-minute load average 15.89 rising to 32.58 (first run 10.26 falling to 7.33), on 16 CPUs. Other worktrees were running their suites.
- Evidence that the load, not the code, set the figure: the 18774 tests that exist in both runs cost 1325.4 s in the first run and 2334.9 s in the last (x1.76). The tests outside `freedom_ls/messaging_policy/tests/test_policy.py`, which the pruning did not touch, went from 1169.7 s to 2141.3 s (x1.83). Database setup went from 65.7 s to 84.2 s.
- Indicative figure at the first run's load: dividing the last run's CPU seconds by that x1.83 gives about 918 s. This is arithmetic on a noisy ratio, not a measurement; the measurement is the 1680.1 s above.
- Pruning did not stop on the 0.5% rule (threshold 7.28 s): the next candidate in the first ranking, `freedom_ls/content_engine/tests/test_images.py::test_comparison_winner_on_each_side_of_the_lossy_wins_divisor` (14.8 s), is above it. Pruning stopped because slice 4's estimate reached the target: 242.36 s saved x 0.9465 = 229.4 CPU seconds, against the 192.9 needed (1378.2 - 1185.3).
- With load and pressure clearly higher than in the first run, no rerun was made. The decision (accept slice 4's estimate, rerun on a quieter machine, or prune more) is the user's.

## Full tier

- Commit tested: `8d941327f64284f84269f42df05618a05c1f8e43`. Command: `.claude/ds/scripts/run_tests.sh uv run pytest -n auto -m 'not ci_only and not weasyprint'` (once).
- `run: summary (merged): 19832 passed, 0 failed, 3 skipped in 814.9s`; `run: RESULT PASS`. 19835 collected, 19835 finished.
- Files other specs own: `git diff main...HEAD` (against the merge base, since main has moved on and the branch is not rebased) is empty for `.github/workflows/tests.yml`, `run_tests.py`, `select_tests.py` and `test_tiers.md`; `pyproject.toml` shows the one new `[[tool.test_tiers.tooling]]` entry as its only `[tool.test_tiers]` change, plus the ruff per-file ignore for the ranking script.
