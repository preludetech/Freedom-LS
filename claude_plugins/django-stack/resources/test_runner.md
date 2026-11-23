# Test runner

A caller hands this file one request and reads back one line. The tiers, their commands and
their flags are in [`test_tiers.md`](test_tiers.md); read it before running anything.

## Requests

| Request | Inputs | What runs |
| --- | --- | --- |
| `change` | `<change>`, optional `<widen>: no` | The `targeted` tier over `<change>` |
| `everything` | | The `full` tier |
| `before landing` | optional `<prepare>` | The checkpoint (below) |
| `one test` | `<test>` | "A single test run" for `<test>` |
| `failed` | `<failed>`, `<change>` of the fix | The "Failed-only re-run" of `<failed>`, selected with the fix's `<change>` |

`<change>` becomes the selector's diff arguments:

- `uncommitted` → `--working-tree`
- `paths <p…>` → those paths
- `commits <a>..<b>` → `--range <a>..<b>`

`<widen>: no` applies when the selector prints `tier: full` for a `change`: run nothing and
return `tests: needs everything`. Without it, run the full tier the selector printed.

## The checkpoint

A checkpoint runs only what changed since the last passing full run on record.

```
.claude/ds/scripts/full_run_record.sh resolve --selector ".claude/ds/scripts/select_tests.sh --wide"
```

- `tier: none` → run nothing. Return `tests: nothing to run`, with the `why:` line as the summary.
- `tier: targeted` → run `<prepare>`, then the `targeted` tier with `--wide` and the `diff:`
  line as its diff arguments.
- `tier: full` → run `<prepare>`, then the `full` tier.

`<prepare>` is a script the caller names. Run it from the project root before the tests. A
non-zero exit returns `tests: failed · summary: prepare failed: <its output>` with nothing run.

## Record every full run

This applies to each `full` tier this file runs: an `everything` request, a checkpoint that
resolved to `full`, and a `change` the selector widened.

Before the run starts, note the commit it tests:

```
.claude/ds/scripts/full_run_record.sh start
```

`<sha>` is the value on its `sha:` line, empty when the tree is dirty.

After the run finishes, record it. `<verdict>` is `pass` at `RESULT PASS`, `incomplete` at
`RESULT INCOMPLETE`, and `fail` otherwise.

```
.claude/ds/scripts/full_run_record.sh write --verdict <verdict> --sha "<sha>"
```

Record a remote full run only when its `run: tested <sha>` equals `<sha>`; otherwise pass
`--verdict fail`. Record a fallback local run as any local run.

The script records `<sha>` only when HEAD is still that commit and the tree is clean. A commit
another process made during the run leaves no record, so the next checkpoint is a full run.

## Return

Fixing a failure belongs to the caller. Return this line and stop:

```
tests: passed|failed|incomplete|nothing to run|needs everything · summary: <verdict line> · failed: <test ids>
```

- `tests:` is `passed` at `RESULT PASS`, `failed` at `RESULT FAIL`, `incomplete` at
  `RESULT INCOMPLETE`, and `nothing to run` when the selector or the checkpoint printed
  `tier: none`. Without the runner, read pass or fail from the summary line "Reporting" names.
- `summary:` starts with the tier that ran (`targeted:` or `full:`), then the verdict line
  "Reporting" in `test_tiers.md` names. A checkpoint puts the resolver's `why:` first:
  `targeted: range abc1234..HEAD: <verdict line>`. A `nothing to run` summary is the `why:`
  line alone, as in `no test-visible change since full green at abc1234`, and never contains
  the word "passed".
- The summary of a remote full run ends `(remote: <url>)` from its `run: url` line. A fallback
  run's ends `(local: <reason>)` with the `UNAVAILABLE` reason.
- `failed:` appears only when the run failed. It is the failed set as `test_tiers.md` defines
  it: node IDs, space-separated, or the "and N more" note. A caller passes it back as `<failed>`
  unchanged, and passes one of its node IDs as `<test>`.
