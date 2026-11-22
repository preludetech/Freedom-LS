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

## Rerun of the last ranking

- Commit tested: `45d65c17989804feb418ad9d3647cff808d0f20b`. Main base SHA unchanged: `0a72a807fc4f9abcee739a256cb702c972d0ab4a`.
- Command: `/usr/bin/time -v uv run python scripts/rank_test_costs.py` (`-n 4`, `--no-cov`, random order off).
- Result: 18773 passed, 3 skipped; 18776 tests recorded.
- Total CPU: 1621.8 s. Wall: 530.6 s. Summed test cost: 1852.3 s. Database setup: 85.5 s across 4 workers.
- Cross-check: `/usr/bin/time` user 1468.45 s + system 153.85 s = 1622.30 s against the header's 1621.8 s (0.03%). Wall 8:51.22. Max resident set size 901716 kB.
- Load average (1, 5, 15 min) and CPU pressure `some avg60`:
  - start: 13.64 10.28 10.97, 7.40
  - end: 20.97 18.41 14.63, 24.32
  - first run, for comparison: start 10.26 10.88 9.41, 4.80; end 7.33 9.85 9.60, 1.59.

### Result of the rerun

- Target 1185.3 CPU seconds; rerun 1621.8. **Over the target by 436.5 s.** The machine was quieter at the start than for the last run but got busier during it (pressure 7.40 to 24.32), and stayed busier than the first run throughout.
- Areas the pruning did not touch (everything outside `freedom_ls/messaging_policy`): 1161.6 s in the first run, 1617.9 s here (x1.393; the last run was x1.830).
- Indicative total at the first run's load: 1621.8 / 1.393 = about 1164 CPU s, under the target.
- Indicative saving from the area that was pruned: `freedom_ls/messaging_policy` cost 294.6 s in the first run and 234.1 s here; 234.1 / 1.393 = about 168 s, so about 127 s of test cost saved, about 120 CPU s at the 0.9465 ratio. That is short of the 192.9 CPU s needed and well under slice 4's 229.4 CPU s estimate.
- The two indicative figures disagree (one under the target, one over), and both rest on a load ratio. The run is not a clean measurement of the target.

## Ranking run after the second pruning pass

- Commit tested: `595c530ca5540e0983337cf3ecf6cfc40ed183dc`, no `-dirty`. The ranking it wrote is committed as `afc221b6f`.
- **The branch was rebased onto main between the rerun above and this run.** Old base `0a72a807fc4f9abcee739a256cb702c972d0ab4a`, new base `29ab2524863ad7b621e11ceac465831e80c43ab4` (125 commits). Main added 19 test files and changed 27.
- A first attempt at this run failed on eleven tests in `tests/test_full_run_record.py`, which main brought in: the test project it builds copied `select_tests.py` without the `module_graph.py` it imports. Fixed in `595c530ca`; no ranking was written from the failed run.
- Command: `/usr/bin/time -v uv run python scripts/rank_test_costs.py` (`-n 4`, `--no-cov`, random order off).
- Result: 19071 passed, 3 skipped; 19074 tests recorded (18778 in the first run).
- Total CPU: 1081.9 s. Wall: 317.8 s. Summed test cost: 1123.2 s. Database setup: 50.4 s across 4 workers.
- Cross-check: `/usr/bin/time` user 972.33 s + system 109.79 s = 1082.12 s against the header's 1081.9 s (0.02%). Wall 5:17.97. Max resident set size 917304 kB.
- Load average (1, 5, 15 min) and CPU pressure `some avg60`:
  - start: 2.59 3.98 5.87, 0.06
  - end: 4.57 4.53 5.57, 0.00
  - first run, for comparison: start 10.26 10.88 9.41, 4.80; end 7.33 9.85 9.60, 1.59.

### Result after the second pass

- Target 1185.3 CPU seconds; this run 1081.9. **Under the target by 103.4 s**, with 296 more tests than the first run. The machine was quieter than for the first run, so the two totals are still not like for like; the figures below say by how much.
- Load ratio: the 34 areas (of 42) that neither main nor the pruning touched, and whose test count is unchanged (11991 tests), cost 652.4 s in the first run and 556.8 s here: x0.853.
- The target moved with the rebase. Tests in the 19 test files main added: 475, costing 95.9 s here, which is 95.9 / 0.853 = 112.4 s at the first run's load, or 106.4 CPU seconds at the 0.9465 ratio. The cost of the tests main removed cannot be subtracted, because `.sdd-work/test_costs_first.json` was deleted when the records were first closed; the net count (475 added, 296 more in total, 2 merged away by the pruning) puts them near 177 tests. So the adjusted target is at most 1185.3 + 106.4 = 1291.7 CPU seconds, and lower by whatever those removed tests cost.
- This run at the first run's load: 1081.9 / 0.853 = about 1268 CPU seconds, under the adjusted target's upper bound by about 23 s. The removed tests' cost is the uncertainty in that margin.
- The pruned tests on their own, which the rebase does not touch:

  | | First run | This run | At the first run's load (/ 0.853) |
  |---|---|---|---|
  | `freedom_ls/messaging_policy` (area) | 294.6 s | 94.6 s | 110.9 s |
  | `test_comparison_winner_on_each_side_of_the_lossy_wins_divisor` | 14.8 s | 2.7 s | 3.2 s |

  Saved: 183.7 + 11.6 = 195.3 s of test cost, about 184.9 CPU seconds at the 0.9465 ratio, against the 192.9 the target needs: 8 s short on this view, within the noise of the load ratio (database setup alone moved by x0.77 between the two runs).
- Reading: the run as measured is under the target. Brought to the first run's load, one view puts it just under the adjusted target and the other puts the saving 4% short of what the target needs. The pruning cut the costliest area from 294.6 s to about 111 s of test cost, about 13% of the first run's total CPU. Pruning stopped where the remaining candidates above the 7.28 s threshold have no cheaper form (see `pruned_tests.md`).
- Coverage: no whole-suite coverage run was made after the second pass, and the "before" report was no longer there to compare with. Each changed test file was compared against itself instead (see `pruned_tests.md`): no file under `freedom_ls/` lost a line or a branch.
- Tests run for the second pass: the targeted tier on its commit (312 passed, 0 failed), and this ranking run over the whole suite without the Playwright tests (19071 passed). The full tier was not run again after the rebase onto main.
