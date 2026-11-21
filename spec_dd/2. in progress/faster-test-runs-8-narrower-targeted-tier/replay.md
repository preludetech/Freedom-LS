# Replay of the main batches with narrow off and on

`replay.py` ran the selector over every `[batch ...]` commit on `main` since 2026-11-19, once with
`--wide` (narrow off) and once without it (narrow on), and wrote the measured section below. Re-run
it with `python3 replay.py` from this directory; it rewrites only the part between the markers.

Three things to keep in mind when reading the numbers.

- The commit count is 128, not 119. Main kept taking batches after the research was taken, so this
  replay has 9 more commits than the research table. The research columns are copied as they were.
- Both runs use HEAD's tree and HEAD's module graph, not each batch's own. The research ran each
  batch against its own tree, so the narrow-off column does not match the research column. HEAD
  also has 39 app test directories where the research counted 42. The off and on columns share
  the same tree, so the comparison between them is fair.
- The time estimates are rough. The only per-test cost in `research_test_timings.md` is the
  `accounts` sample, so every directory gets that rate times a count of `def test_` lines.

## Outcome against the success criteria

- The `panel_framework` leaf-module case holds. A change to `panel_framework/csv_safety.py` selects
  36 app test directories off. On it selects the one `panel_framework` directory plus 31 test files
  in 3 other apps.
- Fewer than 69 batches at `full` or 28-plus directories holds, with room to spare for a replay of
  this kind. Off it is 71 of 128, on it is 31 of 128.
- At least 3 batches at `none` holds, but only because it already held. The count is 3 with narrow
  off and 3 with it on. Narrow changes nothing there, since the `none` batches are docs and
  markdown only.
- The under-10-seconds selector target holds on this run: median 6.0s, max 8.2s with
  narrow on, against 0.5s and 0.9s off. The cost is the import graph, which parses every tracked
  Python file on each run that reaches it. A single run taken earlier while other sessions loaded the
  machine took 9.5s, so the margin is thin and no cache was added.

## What narrow does to the buckets

Of the 71 batches that were `full` or wide off, 40 left those buckets. Nine batches are narrower
than a `full` run yet still wide: 10 stay at 28-plus directories. Conftest changes went
from 13 `full` batches to 3, the `urls.py`, `apps.py` and `factories.py` escalations to none.

The estimated serial test time falls from a median of 54.2 minutes per batch to 14.4. Across all
128 batches the total falls from 88.6 to 70.1 hours, a smaller drop than the median because the
`full` batches that remain dominate the sum.

Fifty-nine batches dropped app test directories, 845 in all. In every one the dropped directory was
selected off because it imports the changed app (a runtime or test-only dependency, direct or
through another app). On, the same importers are reached only through the test files that import
the changed module, and one app hop for non-Python files, `urls.py` and `apps.py`.

## Parent-package edges

An `__init__.py` that imports its own submodules makes every importer of any submodule an importer
of the package. Three batches, all in `icons`, reach 636 or 637 test files each, and 593 of those
come only through that edge. The whole of `icons` is one import cluster, so a leaf change there
selects most of the suite. The two `panel_framework` batches are small by comparison (1 and 3 test
files). The count is an upper bound, since a plain `import pkg` beside `import pkg.x` is counted as
a parent edge too.

## Measured results

<!-- replay:begin -->
Replayed 128 batch commits (`git log --first-parent main --since=2026-11-19 --grep='^\[batch'` finds 128; the research used 119). HEAD has 39 `freedom_ls/<app>/tests` directories.

### Buckets

| Result | Research | Narrow off | Narrow on |
|---|---|---|---|
| full | 34 | 35 | 21 |
| targeted, 28+ app test directories | 35 | 36 | 10 |
| targeted, 6 to 27 app test directories | 0 | 1 | 20 |
| targeted, 1 to 5 app test directories | 47 | 27 | 48 |
| targeted, test files or other targets only | 0 | 26 | 26 |
| none | 3 | 3 | 3 |
| total | 119 | 128 | 128 |

Batches at `full` or 28+ directories: off 71, on 31.

### Why batches are `full`, narrow off

| Reason | Batches |
|---|---|
| unmapped path | 15 |
| **/conftest.py | 13 |
| **/urls.py | 5 |
| dependency file | 4 |
| config/** | 4 |
| **/factories.py | 3 |
| **/migrations/** | 3 |
| **/apps.py | 2 |

### Why batches are `full`, narrow on

| Reason | Batches |
|---|---|
| unmapped path | 13 |
| dependency file | 4 |
| config/** | 4 |
| **/conftest.py | 3 |
| **/migrations/** | 3 |

### Selector run time

| | Median | Max | Over 10s |
|---|---|---|---|
| narrow off | 0.5s | 0.9s | 0 of 128 |
| narrow on | 6.0s | 8.2s | 0 of 128 |

### Test-run time estimate

Estimate, not a measurement: `def test_` count of the selected targets (Playwright directories excluded, parametrised cases counted once) times 0.37s, the `accounts` sample's per-test cost with its database setup taken out. Serial test-body seconds, before xdist and the 55 to 65s database setup per worker.

| | Median per batch | Total over all batches |
|---|---|---|
| narrow off | 54.2 min | 88.6 h |
| narrow on | 14.4 min | 70.1 h |

### Parent-package edges

78 batches have a changed Python path that the narrow selector resolved through imports. Test files reached through those paths: 13832, of which at most 1783 only through a parent-package edge.

| Batch | Reached | Only via parent edge |
|---|---|---|
| 3ce8aca68 [batch 3] Icons render from bundled data overlaid with SEMANTIC_ICONS_ICONIFY_DIR | 637 | 593 |
| 5ebd86d99 [batch 2] Generate bundled icon data from node_modules | 637 | 593 |
| cbf74178e [batch 1] icons reads SEMANTIC_ICONS_* via its own settings reader, old names deprecated | 636 | 593 |
| 69b8e5bf6 [batch 2] Move the three course data tables to panels/course/data_tables.py | 19 | 1 |
| a88abc3b1 [batch 1] move the organisation request types into panels.common.request | 27 | 3 |

### The leaf-module case

`freedom_ls/panel_framework/csv_safety.py`, one tracked non-`__init__` module of `panel_framework`.

- narrow off: tier targeted, 36 app test directories, 0 test files in 0 apps.
- narrow on: tier targeted, 1 app test directories (panel_framework), 31 test files in 3 apps.

### Per batch

Dropped means an app test directory narrow off selects and narrow on does not. A test file from a dropped directory can still be selected by name. Rule columns: what the wide `why:` lines gave the dropped directories, then the rules the narrow `why:` lines used.

| Batch | Off | On | Dropped | Wide rule of the dropped | Narrow rules |
|---|---|---|---|---|---|
| 3d03848a2 | full (0) | full (0) | n/a | - | **/conftest.py |
| 533dde3cc | full (0) | full (0) | n/a | - | **/conftest.py |
| a1b4f4876 | targeted, 1 to 5 app test directories (5) | targeted, 1 to 5 app test directories (1) | 4 | runtime dep 1, test-only dep 3 | imports, owning app |
| e5734e7a7 | targeted, 1 to 5 app test directories (5) | targeted, 1 to 5 app test directories (5) | 0 | - | imports, one app hop, owning app |
| d4561ed34 | targeted, 28+ app test directories (38) | targeted, 6 to 27 app test directories (6) | 32 | runtime dep 24, test-only dep 8 | imports, one app hop, owning app, tooling |
| 38df4e03d | targeted, 6 to 27 app test directories (7) | targeted, 1 to 5 app test directories (5) | 2 | runtime dep 1, test-only dep 1 | imports, one app hop, owning app, tooling |
| e3518bd5e | targeted, 1 to 5 app test directories (5) | targeted, 1 to 5 app test directories (1) | 4 | runtime dep 1, test-only dep 3 | imports, owning app |
| ff70b4611 | full (0) | targeted, 1 to 5 app test directories (5) | n/a | - | imports, one app hop, owning app |
| 0c6197f15 | full (0) | full (0) | n/a | - | **/migrations/**, imports, one app hop, owning app, unmapped path |
| 3baae9de2 | full (0) | full (0) | n/a | - | imports, one app hop, owning app, unmapped path |
| 3ce8aca68 | full (0) | full (0) | n/a | - | **/conftest.py, config/**, conftest scope, dependency file, imports, owning app, tooling, unmapped path |
| 5ebd86d99 | full (0) | full (0) | n/a | - | dependency file, imports, one app hop, owning app, tooling |
| cbf74178e | full (0) | full (0) | n/a | - | config/**, imports, owning app, tooling, unmapped path |
| fab6b122d | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | tooling |
| 5492fc20d | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | tooling |
| 6f4adeea8 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | tooling |
| fb7e9f762 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | imports, tooling |
| 4b0e7cc9d | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | imports, tooling |
| 492aee108 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | imports, tooling |
| c1aba029c | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | imports, tooling |
| be239c124 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | tooling |
| db80a6f5e | full (0) | targeted, 6 to 27 app test directories (24) | n/a | - | imports, one app hop, owning app |
| 87ff83074 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| 81c56d9a9 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| a0f12fc05 | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (24) | 12 | runtime dep 8, test-only dep 4 | imports, one app hop, owning app, tooling |
| 8ae14a019 | full (0) | full (0) | n/a | - | config/**, one app hop, owning app |
| 1bc95b99a | targeted, 28+ app test directories (28) | targeted, 6 to 27 app test directories (24) | 4 | runtime dep 2, test-only dep 2 | imports, one app hop, owning app |
| daa1e423c | targeted, 1 to 5 app test directories (1) | targeted, 1 to 5 app test directories (1) | 0 | - | imports, tooling |
| 7df920a3b | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | tooling |
| 62d686a17 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| b80bef066 | targeted, 28+ app test directories (29) | targeted, 1 to 5 app test directories (1) | 28 | runtime dep 18, test-only dep 10 | imports, owning app, tooling |
| 2cec81f21 | targeted, 28+ app test directories (29) | targeted, 1 to 5 app test directories (1) | 28 | runtime dep 18, test-only dep 10 | imports, owning app, tooling |
| c09b1f87e | targeted, 28+ app test directories (28) | targeted, 1 to 5 app test directories (1) | 27 | runtime dep 17, test-only dep 10 | imports, owning app |
| 0a05297a5 | targeted, 28+ app test directories (29) | targeted, 1 to 5 app test directories (3) | 26 | runtime dep 16, test-only dep 10 | imports, one app hop, owning app, tooling |
| be286a26a | full (0) | targeted, 1 to 5 app test directories (1) | n/a | - | imports, owning app, tooling |
| ceb459d09 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| bdcf259d9 | full (0) | full (0) | n/a | - | **/migrations/**, imports, owning app, tooling |
| c8b2035fe | none (0) | none (0) | 0 | - | - |
| 5bcfdb98e | full (0) | targeted, 1 to 5 app test directories (1) | n/a | - | conftest scope, imports, owning app |
| 9f2f5990d | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 175ab5eaa | full (0) | targeted, 1 to 5 app test directories (1) | n/a | - | conftest scope, imports, owning app |
| 7c9fce5bb | full (0) | targeted, 1 to 5 app test directories (1) | n/a | - | conftest scope, imports, owning app |
| e7f686dfb | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 217490369 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| e50777235 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| a0e19e573 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| fdf00a716 | full (0) | full (0) | n/a | - | imports, owning app, unmapped path |
| 338389323 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 69b8e5bf6 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (2) | 0 | - | imports, owning app |
| 7a013c519 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 9d44b866b | none (0) | none (0) | 0 | - | - |
| 76a4088bf | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| af2493755 | full (0) | targeted, 1 to 5 app test directories (1) | n/a | - | conftest scope, imports, owning app |
| 6dc6d3d67 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 5174ce2fa | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| d909c2d03 | full (0) | full (0) | n/a | - | imports, owning app, unmapped path |
| 764b30b26 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 6e42b3de1 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 3893f06e8 | full (0) | targeted, 6 to 27 app test directories (8) | n/a | - | imports, one app hop, owning app |
| c093da1c7 | full (0) | full (0) | n/a | - | imports, one app hop, owning app, unmapped path |
| dc6379fb0 | targeted, 28+ app test directories (36) | targeted, 28+ app test directories (31) | 5 | runtime dep 3, test-only dep 2 | imports, one app hop, owning app |
| fa5ce52df | full (0) | full (0) | n/a | - | one app hop, owning app, unmapped path |
| da609f3e6 | full (0) | targeted, 28+ app test directories (31) | n/a | - | imports, one app hop, owning app |
| c32e751b0 | full (0) | full (0) | n/a | - | imports, one app hop, owning app, unmapped path |
| 61a4c516f | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| 23fbf6c3a | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (8) | 28 | runtime dep 19, test-only dep 9 | one app hop, owning app |
| 621138a03 | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (8) | 28 | runtime dep 19, test-only dep 9 | imports, one app hop, owning app |
| bf23e6383 | targeted, 28+ app test directories (36) | targeted, 1 to 5 app test directories (1) | 35 | runtime dep 25, test-only dep 10 | imports, owning app |
| f6b795dd2 | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (8) | 28 | runtime dep 19, test-only dep 9 | imports, one app hop, owning app |
| 1c72fa7de | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (8) | 28 | runtime dep 19, test-only dep 9 | imports, one app hop, owning app |
| 8c13c64f1 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| dd0905396 | targeted, 28+ app test directories (36) | targeted, 1 to 5 app test directories (1) | 35 | runtime dep 25, test-only dep 10 | imports, owning app |
| 12a86acad | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| b56a11c61 | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (8) | 28 | runtime dep 19, test-only dep 9 | imports, one app hop, owning app |
| 3efdf1a0e | full (0) | targeted, 6 to 27 app test directories (8) | n/a | - | conftest scope, imports, one app hop, owning app |
| 1b4bad2aa | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (8) | 28 | runtime dep 19, test-only dep 9 | imports, one app hop, owning app |
| 06d0fb08e | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| 753937487 | full (0) | targeted, 6 to 27 app test directories (8) | n/a | - | conftest scope, imports, one app hop, owning app |
| 9cd0cc01c | targeted, 28+ app test directories (36) | targeted, 1 to 5 app test directories (1) | 35 | runtime dep 25, test-only dep 10 | imports, owning app |
| 146c9d012 | targeted, 28+ app test directories (38) | targeted, 6 to 27 app test directories (8) | 30 | runtime dep 29, test-only dep 1 | imports, one app hop, owning app |
| 2f6e86913 | full (0) | full (0) | n/a | - | imports, one app hop, owning app, unmapped path |
| d466d19a0 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| 275fc0c58 | full (0) | full (0) | n/a | - | config/**, conftest scope, imports, one app hop, owning app, tooling |
| 3e6035ad3 | full (0) | full (0) | n/a | - | conftest scope, dependency file, imports, one app hop, owning app |
| f0733750e | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (8) | 28 | runtime dep 19, test-only dep 9 | one app hop, owning app |
| 4098afe4e | full (0) | targeted, 6 to 27 app test directories (8) | n/a | - | imports, one app hop, owning app |
| 3b8e6793e | targeted, 28+ app test directories (38) | targeted, 28+ app test directories (32) | 6 | runtime dep 5, test-only dep 1 | one app hop, owning app |
| 038ce7c43 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| d5d65ae50 | targeted, 28+ app test directories (38) | targeted, 28+ app test directories (32) | 6 | runtime dep 5, test-only dep 1 | one app hop, owning app |
| 3a04e4f4c | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| c640ec5e6 | targeted, 28+ app test directories (38) | targeted, 28+ app test directories (32) | 6 | runtime dep 5, test-only dep 1 | imports, one app hop, owning app |
| c3c01fb57 | targeted, 28+ app test directories (38) | targeted, 28+ app test directories (32) | 6 | runtime dep 5, test-only dep 1 | one app hop, owning app |
| 8fedf3496 | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (8) | 28 | runtime dep 19, test-only dep 9 | one app hop, owning app |
| 245c556b5 | targeted, 28+ app test directories (38) | targeted, 28+ app test directories (32) | 6 | runtime dep 5, test-only dep 1 | one app hop, owning app |
| f071d2705 | full (0) | targeted, 28+ app test directories (32) | n/a | - | conftest scope, one app hop, owning app |
| 09f281966 | full (0) | full (0) | n/a | - | dependency file, imports, one app hop, owning app, unmapped path |
| 6e197ed24 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| a9b14708a | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (8) | 28 | runtime dep 19, test-only dep 9 | one app hop, owning app, tooling |
| e044bd43e | targeted, 28+ app test directories (38) | targeted, 28+ app test directories (32) | 6 | runtime dep 5, test-only dep 1 | imports, one app hop, owning app |
| 655546c01 | targeted, 28+ app test directories (38) | targeted, 28+ app test directories (30) | 8 | runtime dep 7, test-only dep 1 | one app hop, owning app |
| 23fb3f248 | full (0) | full (0) | n/a | - | one app hop, owning app, unmapped path |
| 3d3520aec | targeted, 28+ app test directories (29) | targeted, 1 to 5 app test directories (2) | 27 | runtime dep 17, test-only dep 10 | imports, owning app, tooling |
| 0ffdb59bd | targeted, 28+ app test directories (29) | targeted, 1 to 5 app test directories (1) | 28 | runtime dep 18, test-only dep 10 | imports, owning app, tooling |
| e3eb3e932 | targeted, 28+ app test directories (29) | targeted, 1 to 5 app test directories (2) | 27 | runtime dep 17, test-only dep 10 | imports, owning app, tooling |
| 9d6d5551e | targeted, 1 to 5 app test directories (5) | targeted, 1 to 5 app test directories (1) | 4 | runtime dep 1, test-only dep 3 | imports, owning app |
| 716a7992d | targeted, 28+ app test directories (29) | targeted, 6 to 27 app test directories (9) | 20 | runtime dep 10, test-only dep 10 | imports, one app hop, owning app |
| d57a39cc2 | targeted, 28+ app test directories (29) | targeted, 1 to 5 app test directories (3) | 26 | runtime dep 14, test-only dep 12 | imports, owning app, tooling |
| 6e2e2edbf | targeted, 28+ app test directories (29) | targeted, 1 to 5 app test directories (1) | 28 | runtime dep 18, test-only dep 10 | imports, owning app, tooling |
| 6e215cf3c | full (0) | full (0) | n/a | - | **/migrations/**, imports, owning app, tooling |
| 0b98ecc25 | none (0) | none (0) | 0 | - | - |
| 20c63cc0d | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| 594b68b33 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 0c3ef8e89 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| b895ca999 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| c9835cd46 | full (0) | targeted, 1 to 5 app test directories (1) | n/a | - | conftest scope, imports, owning app |
| a64b9c1c6 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| ecab29cea | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| b9c1a8a06 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 5c4655e58 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 10c3fc5f5 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| 84f998682 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| a70ca503f | full (0) | full (0) | n/a | - | imports, owning app, unmapped path |
| a88abc3b1 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (1) | 1 | runtime dep 1 | imports, owning app |
| 70eab77a9 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (2) | 0 | - | imports, one app hop, owning app |
| 940e00fc9 | targeted, test files or other targets only (0) | targeted, test files or other targets only (0) | 0 | - | - |
| 36b93f37c | targeted, 28+ app test directories (38) | targeted, 1 to 5 app test directories (3) | 35 | runtime dep 24, test-only dep 11 | imports, one app hop, owning app, tooling |
| debd1c4a9 | targeted, 1 to 5 app test directories (2) | targeted, 1 to 5 app test directories (2) | 0 | - | imports, one app hop, owning app |
| 3109c5c4a | targeted, 28+ app test directories (36) | targeted, 6 to 27 app test directories (8) | 28 | runtime dep 19, test-only dep 9 | imports, one app hop, owning app |
<!-- replay:end -->

## Open points

- Those three `icons` batches are `full` on both sides, mostly because they also touch a dependency
  file or `config/**`, so the parent-package cost does not show in the buckets. It would show for a
  change to an `icons` module alone.
- Without the per-batch tree, a batch that deleted a module is replayed by name against HEAD's
  graph. A few rows may differ from what that batch would have selected on the day.
