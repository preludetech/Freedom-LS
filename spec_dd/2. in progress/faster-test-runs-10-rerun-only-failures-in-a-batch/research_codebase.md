# Research: codebase

What this spec touches, reuses or conflicts with. Paths are repo-relative; line numbers are at
`3c2750776`.

## 1. The rule today: one place, `test_tiers.md`

`claude_plugins/django-stack/resources/test_tiers.md:97-103`, "When a targeted run or full run fails":

- Addresses "the agent that owns the change, never a mechanic briefed only to run a tier" (l.99).
- Fix, then `uv run pytest --lf --no-cov` (+ `-n auto` for targeted/full), prefixed with
  `.claude/ds/scripts/run_tests.sh` when installed (l.100-102).
- "Once that is green, re-run the whole tier as it first ran. The gate is the whole tier, not the
  `--lf` subset." (l.102-103). This sentence is what the spec removes for batches.
- The section is keyed on tier name only ("targeted run or full run"). It has no notion of caller.

Other relevant lines in the same file:

- l.44-47: one tier at a time per worktree, run in background. A failed-only re-run plus a
  fix-diff selection (answers.md Q1) must therefore be two sequential runs, or one command.
- l.57-58 and l.91-92: a test whose worker died in every attempt (two or more) is `RESULT FAIL`.
  Matches the idea's "still counts as failed".
- l.90-92: `RESULT INCOMPLETE` is blocked-on-memory, not a failure to fix; unaffected.
- l.75-83: "A single test run" (`uv run pytest <file>::<test> -x --no-cov`), the shape other
  callers already use for node-ID re-runs.

No test asserts on the wording of l.97-103 (`git grep -- --lf tests/` is empty).

## 2. Every file that points at or restates the rule

`git grep` for `--lf`, "whole tier", "as it first ran" and the section title, outside `spec_dd/`:

| File | Line | What it says | Effect of the spec |
| --- | --- | --- | --- |
| `claude_plugins/sdd/commands/implement_plan.md` | 52 | Batch brief point 3: targeted `--working-tree`; "A failure follows 'When a targeted run or full run fails' in the tier definition". "Done when the helper reports a summary line with no failures." | Pointer only; inherits the new rule. "Done when" then means the failed-only re-run's line. |
| same | 82 | "The tier must pass before the next batch wave is formed. A fix batch (`design fix`, `review fix` or `integration fix`) is a batch, so it runs `targeted` the same way." | Already routes fix batches through point 3; settled item 2 of the idea needs no new text here, but "the tier must pass" reads as a whole-tier gate and may need rewording. |
| same | 88 | After integration: mechanic runs targeted `--range <wave-base>..HEAD`; "A failure is fixed by a sub-agent as Step 3 point 3 does, committed as `[batch <id>] integration fix`". | answers.md Q2 keeps this run. Note the pointer: "Step 3 point 3" is l.133 (Final Verification), not the batch brief's point 3 (l.52). |
| same | 122 | Review fix batch "runs `targeted` through `run_test_tier.md` like any batch". | Inherits. |
| same | 131-133 | Step 3: one `full` run; on failure the fix sub-agent "re-runs each failing test by node ID as the tier definition's single test run until it passes, then follows `run_test_tier.md` with `targeted` and `--range <sha before the fix>..HEAD`". | Already the shape answers.md Q1 asks for (failures + the fix's own diff). It is precedent to reuse, and it is the "final full run" the idea keeps; the gate there is the first full run, the fix is not re-gated by another full run. |
| `claude_plugins/django-stack/commands/rebase_main.md` | 191-222 (Step 9) | Targeted = two selector calls (`--range origin/main..HEAD`, then `--upstream-range ... --range $REPLAYED_TIP..HEAD --tests-changed-in ...`); l.215 "A failure is fixed on the branch, test first, following 'When a targeted run or full run fails' ... then committed"; l.222 "Three attempts." | answers.md Q3: targeted follows the new rule, `full` keeps the whole tier. The fix is committed (`<branch>: fix <what> after rebase`), so its diff is a range. "Three attempts" counts re-runs; it needs to say whether an attempt is a failed-only re-run. |
| `claude_plugins/sdd/agents/qa-bugfixer.md` | 94-105 | Step 5 targeted with explicit paths; l.100 "No `-x` here: it has to be the whole tier."; l.104 follows the same section. | **Conflict.** Not a batch, but it reads the same section, so a tier-definition rewrite changes it too. |
| `claude_plugins/sdd/commands/README.md` | 122 | "The agent's targeted run omits `-x` because the orchestrator skips re-driving the regression layer on the strength of that run, so it has to be the whole tier." | Depends on qa-bugfixer's run being whole. |
| `claude_plugins/sdd/resources/do_qa_fix_loop.md` | 78-79 | "Trust the fixer's targeted run for the regression layer ... do not re-drive what pytest already covers." | Same dependency. |
| `claude_plugins/sdd/commands/README.md` | 186 | Describes Step 3's node-ID + fix-range re-run; "It does not repeat the full run. The checkpoint in `finish_worktree` covers the fixes." | Unchanged; good wording precedent for the batch case. |
| `claude_plugins/sdd/docs/diagrams/implement_plan.drawio.svg` | labels | "Fix, as the tier definition says for a failed targeted ..." | Points to the definition; reword only if the label text names the whole-tier re-run. |
| `claude_plugins/sdd/docs/diagrams/rebase.drawio.svg` | labels | "A failed run is fixed test first ..." | Same. |

No other plugin file spells the rule. `claude_plugins/fls-dev/resources/flaky_tests.md` only uses
"A single test run" (l.6, l.62).

## 3. Callers whose failure handling is their own (must stay whole-tier)

- `claude_plugins/sdd/commands/finish_worktree.md:80-96` (Step 1 checkpoint) and l.106-153
  ("Flaky tests", "Obvious failures"): node-ID re-runs x3, fixes, then "follow the run that failed
  again from its start" (l.125, l.152). It follows its own rule, not the tier definition's section.
- **The checkpoint can resolve to `targeted`** (`run_test_tier.md:28-40`, `finish_worktree.md:89`).
  A new rule keyed on the tier name ("a failed targeted run re-runs only failures") would wrongly
  reach the checkpoint. The rule has to be keyed on who runs it (a batch, a fix batch, the
  integration run, the rebase command's targeted step) or the checkpoint has to be excluded by name.
- `finish_worktree.md:31-33` passes `<tier>: none` to the rebase, so answers.md Q3 leaves the
  checkpoint unchanged as stated.
- `pre_step_rebase.md:12-13, 45-47`: every other SDD step's pre-step rebase defaults to
  `targeted`, so the rebase rule change (Q3) applies at every step's start.
- `qa_fix.md:203-230` and `do_qa_fix_loop.md:126-130`: a mechanic runs targeted after fixes and
  failures become todo lines; nothing re-runs. Unaffected.

## 4. Helper and scripts

- `claude_plugins/sdd/commands/protected/run_test_tier.md`: runs and reports only ("Fixing a
  failure belongs to the caller", l.70). Inputs are `<tier>` and `<diff>`. No change needed unless
  the spec wants the helper to run the failed-only re-run itself; then it would need a new input
  (failed node IDs, or a `rerun` tier). Step 3 (l.42-63) records only `full` runs, so a failed-only
  re-run never touches the full-run record.
- `.claude/ds/scripts/run_tests.sh` (19 lines): `exec`s `claude_plugins/django-stack/scripts/run_tests.py`.
  The runner wraps any pytest command, so `run_tests.sh uv run pytest --lf ...` already works.
  - Crash retries pass `--ds-only-nodeids=<file>` (`run_tests.py:439-455`) and add `--no-cov` for
    a subset (l.449-454). A test that crashed every attempt is set to `failed` (l.648-654). xdist
    reports a crashed test as a failed report, so pytest's own `lastfailed` cache holds it too:
    `--lf` picks it up. No runner change is needed for the idea's last settled item.
  - `-p ds_run_record` (`ds_run_record.py:34-50`) deselects by node ID file; it is the existing
    mechanism if the spec prefers explicit node IDs over `--lf`.
- `claude_plugins/django-stack/scripts/select_tests.py` (`.claude/ds/scripts/select_tests.sh`):
  accepts explicit paths, `--working-tree`, `--range` (repeatable), `--upstream-range`,
  `--tests-changed-in` (docstring l.4-17, `main` l.713-812). Prints `tier:`, `why:`, `command:`.
  The targeted command is `run_tests.sh uv run pytest -n auto --no-cov -m '<markers>' [--ignore=<app>/playwright ...] <paths>`
  (`compose_command` l.686-700; sample output for one FLS test file confirmed). There is no flag to
  add node IDs to the printed command.

## 5. Gaps in the current `--lf` command the spec should close

1. **Markers.** The re-run command in `test_tiers.md:100` omits the tier's `-m`. FLS `addopts`
   deselects `dev_tooling` (`pyproject.toml`, `[tool.pytest.ini_options]`), while the tier runs with
   `markers = "not ci_only and not weasyprint"` (`[tool.test_tiers]`). A failed `dev_tooling` test
   (e.g. `freedom_ls/dev_tools/tests/*`, `claude_plugins/fls-content/validate/tests/test_validator.py`)
   is deselected by a bare `--lf` re-run: exit 5. With the runner that is `RESULT FAIL`
   (`run_tests.py:662-667`); without it, "no tests ran" can be misread as no failures. Today the
   whole-tier re-run hides this; once the `--lf` run is the gate it matters.
2. **`--lfnf` defaults to `all`** (pytest 9.0.3, `uv run pytest --help`). With no `lastfailed` data
   (cache cleared, a fresh batch worktree whose failure was outside pytest, `.pytest_cache/` is
   gitignored at `.gitignore:49`), `--lf` runs every test under `testpaths` — a full run in place of
   a tiny one. `--lfnf none`, or explicit node IDs, avoids it.
3. **`--lf` with paths is an intersection.** `pytest --lf <paths>` runs last-failed tests inside
   `<paths>`, not the union. answers.md Q1 (failed tests plus the fix's selection) needs two runs,
   one after the other (l.44-47), or one command naming the failed node IDs and the selected paths.
4. **Isolating the fix's diff inside a batch.** A batch's work is uncommitted until its marker
   commit (`implement_plan.md:52-53`), so `--working-tree` after a fix selects the batch's whole
   change again, not the fix. Options: pass the fix's edited files as explicit paths (qa-bugfixer
   already tracks "files created / files modified", `qa-bugfixer.md:96-98`), or snapshot before the
   fix. The integration fix and the rebase fix are committed, so `--range <sha before fix>..HEAD`
   works there, as `implement_plan.md:133` and `qa_fix.md:207` already do.
5. **Stale `lastfailed` entries.** pytest's cache accumulates; a failure from an earlier run in the
   same worktree that was never re-run stays in `lastfailed` and joins the `--lf` run. In the
   feature worktree (sequential batches share one cache) this widens, never narrows, so it is safe
   but noisy.

## 6. Tests that constrain the edit

- `tests/test_test_tiers.py:24-54`: only allowlisted files may spell a `uv run pytest` invocation
  (`tests/plugin_markdown.py:10-12`). The re-run command must stay in `test_tiers.md`; commands
  point there (matches the idea's "Commands point there and do not restate it").
- `tests/test_checkpoint_prompts.py:43-79`: `implement_plan.md` asks for `<tier>: full` exactly
  once and is the only command that does; `finish_worktree.md` never asks for `full`. New text must
  not add a `full` tier request.
- `claude_plugins/sdd/scripts/check_diagrams.py` (README l.279): diagrams must match `Step N`
  headings; relevant only if a step heading changes.

## 7. Overlap with `faster-test-runs-8-narrower-targeted-tier`

- State: worktree `/home/sheena/workspace/lms/freedom-ls-worktrees/faster-test-runs-8-narrower-targeted-tier`,
  branch has 3 commits past main (spec written and reviewed, `wip before rebase onto main`); no code
  yet. Spec at `spec_dd/2. in progress/faster-test-runs-8-narrower-targeted-tier/1. spec.md` on that
  branch.
- Scope split is explicit both ways: spec 8's Out list names "What happens after a failure
  (`faster-test-runs-10-...`)" (spec l.27); this idea's Out of scope names spec 8.
- Same file, different sections: spec 8 edits only the **targeted** bullet of `test_tiers.md`
  (adds `narrow`, `mode: narrow`, `--wide`) and says "Leave ... the failure section (spec 10) alone"
  (spec l.206-209). Textual merge risk is low; whichever lands second rebases.
- Spec 8 4.1 adds `--wide` to the checkpoint's selector, so checkpoint selection differs from batch
  selection. That reinforces §3 above: the failed-only rule must not attach to "a targeted run"
  generically.
- Spec 8 l.30-31: "Review fix, design fix and criterion fix runs already select from the fix alone
  (`--working-tree`, or a range starting at the fix) and keep doing so." Consistent with this
  spec's fix-diff widening; with `narrow = true` that widening selects fewer apps.
- Spec 8 changes `select_tests.py` and `pyproject.toml`; this spec should not need either (§4), so
  no code collision. The roadmap collision note (`spec_dd/1. next/roadmap.md`, Faster test runs
  Notes) lists spec 8 (selector), 9 (runner) and 10 (tier definition) as touching neighbouring files.
- Related but separate: `faster-test-runs-11-record-failed-full-runs` (failed full run records its
  failures for the checkpoint) and `-12-reliable-full-run-record` own the full-run record; this spec
  leaves `run_test_tier.md` Step 3 and `full_run_record.py` alone.

status: ok
