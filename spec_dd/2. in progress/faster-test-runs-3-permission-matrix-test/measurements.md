# Measurements: permission matrix test, before and after

## What was measured

- Before: `freedom_ls/educator_interface/tests/invariants/test_permission_matrix.py` as it stood at the merge base with `origin/main` (`0325aab454b031b5ac6d6f089f87e9b1c2fd84f8`), restored under a temporary name.
- After: the same file at commit `65221afb4` (the walks; the last commit that changed the file).
- Password hasher in both runs: `django.contrib.auth.hashers.Argon2PasswordHasher` (first entry of `PASSWORD_HASHERS` under `config.settings_dev`; nothing overrides it for tests). Both runs came from one script, back to back, so they share the hasher and machine state.

Command for each file:

```
uv run pytest <file> -n 0 -p no:randomly --no-cov --durations=0 --durations-min=0 -q
```

`-n 0` runs serially. The suite's `--dist loadfile` default would put the whole file on one worker anyway, so a parallel run of this file is also single-worker. The serial run is the cost the file adds to a parallel run.

## Before and after

| | Before | After |
|---|---|---|
| Tests collected | 802 | 54 |
| Summed setup and call time | 1566.35 s | 158.54 s |
| Wall time (pytest summary) | 1572.31 s (26:12) | 159.14 s (2:39) |

Ratio of after to before, setup and call: 158.54 / 1566.35 = 0.101 (limit 0.2). Wall time ratio: 0.101.

## Against the earlier timing research

`spec_dd/1. next/faster-test-runs/research_test_timings.md`, "Largest parametrized tests", lists `test_can_matches_the_matrix` as 696 cases at about 3.5 s each, about 2,440 s in all for that test alone. The file as a whole measured here is 1566 s over 802 tests, an average of 1.95 s per test. Time per world build came out lower on this run than in the research, so the research figure overstates today's before cost by roughly a factor of 1.6. The ratio above compares like with like, since both runs were taken here.

## Cell sets

The old tests identify each cell by its parametrize id. Collecting them gave 696 `test_can_matches_the_matrix` cells and 67 `test_deactivating_the_staff_member_row_withdraws_the_grant` cells. The cells that `_cases()` and `_gated_true_cases()` yield in the new file are also 696 and 67. After sorting both lists and splitting ids on `-`, `diff` printed nothing (exit 0). The walks cover exactly the cells the parametrized tests did.

The three temporary files (the restored test file and the two cell lists) were deleted by the script's `trap`. `git status --porcelain` showed none of them.
