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

## Last ranking run

(filled in by the last slice)

## Result

(filled in by the last slice)
