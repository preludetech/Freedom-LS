# Research: codebase (full-test-run-still-too-often)

Scope note: this worker had no shell. Everything below is from reading files. `git log` per file was
not available, so the "prior work" section is taken from the done specs and the docs, not from commit
history. Line numbers are in the worktree at HEAD `12fcfa439`.

## 1. Short answer

The checkpoint machinery from the earlier spec exists and works for a spec-only branch, but there
are four ways a rebase of a spec-only branch (and many branches with a little code) still ends in
`full`:

1. **`/sdd:finish_worktree` Step 1 is an unconditional `full` run** (`finish_worktree.md:80-85`). It
   never consults the full-run record, even when `implement_plan` Step 3's full run already passed and
   only `spec_dd/` changed since. This is the dominant cause for the idea's scenario.
2. The selector sends **any main-side path matching an escalation glob to `full`**
   (`select_tests.py:320-322`), with no notion of "this came from main, the branch never touches it".
3. The selector sends **any tracked path that no rule knows to `full`** (`select_tests.py:332-334`).
4. A **missing/stale full-run record** makes the checkpoint `full`, but only when the branch has a
   test-visible change (`full_run_record.py:140-144`); a spec-only branch short-circuits to `none` first.

The user's three recorded answers map onto: (1) rewrite finish Step 1 as a checkpoint; (2) change how
main-side paths are weighed in the selector and `resolve`; (3) leave `implement_plan.md:131` alone.

## 2. Every place a test tier is decided

| Place | File:line | Tier it asks for |
| --- | --- | --- |
| `/sdd:implement_plan` per-batch run | `implement_plan.md:52`, `:82`, `:122` | `targeted`, `<diff>` = `--working-tree` (batch/fix batch) |
| `/sdd:implement_plan` Step 3 | `implement_plan.md:131` | **`full`**, outright, once (user says keep) |
| implement_plan Step 3 fix sub-agent | `implement_plan.md:133` | `targeted`, `--range <sha before fix>..HEAD`; "does not repeat the full run" |
| `/sdd:finish_worktree` Step 0 | `finish_worktree.md:31-32` | passes `<tier>: none` to the pre-step rebase |
| `/sdd:finish_worktree` Step 1 | `finish_worktree.md:80-90` | **`full`**, unconditional (to change to checkpoint) |
| finish_worktree main-moved loop | `finish_worktree.md:222-264` | rebase with `<tier>: none`, then `checkpoint` (resolve, rebuild, run) |
| `qa_fix` Step 7 | `qa_fix.md:206-207` | `targeted`, `--range <sha before first fix>..HEAD` |
| `do_qa` after last fix | README `commands/README.md:189` says `targeted`; `do_qa.md` itself only mentions "tiered" chores (`:315`) and routes through the fix loop | `targeted` |
| pre-step rebase (every feature-branch command's Step 0) | `pre_step_rebase.md:12`, `:45-47` | caller's `<tier>`, default **`targeted`** |
| rebase_main Step 9 | `rebase_main.md:191-220` | `none` / `full` / `targeted` as passed; hand run = `targeted` (`:11-12`) |
| `run_test_tier.md` | `:9`, `:28-40` | accepts `targeted`, `full`, `checkpoint`; resolves checkpoint via `full_run_record.py resolve --selector "<selector>"` |
| Plain run, no tier definition | `run_test_tier.md:23-26` | `uv run pytest`, treated as `full` |
| Front-end check | `fls-dev/commands/protected/frontend_check.md` | No test tier. Browser pass at three viewports; skipped when no front-end change (`:34-35`). It cannot cause a full run. |

Writers of the full-run record: `run_test_tier.md:42-63` (Step 3) for every `full`, however it was
asked for (a passed `full`, a resolved checkpoint-`full`, the plain no-definition run).

## 3. Every condition that escalates to `full`

### `select_tests.py` (generic, `claude_plugins/django-stack/scripts/`)

Order of rules in `decide()` (`:291-334`); first match wins:

1. `none` globs (`:304-306`) -> `none`. Generic `NONE_GLOBS` (`:30-38`): `docs/**`, `.github/**`, `*.md` (root only),
   `.claude/**/*.md`, `.claude/**/*.json`, `.claude/agent-memory/**`, `.gitignore`. FLS adds `spec_dd/**` and
   `claude_plugins/**/*.jsx` in `pyproject.toml:114-117`.
2. Changed collected test file under a `tests` dir (`:309-318`) -> `select` that file (deleted -> none).
3. **Escalation globs (`:320-322`) -> `full`.** Generic `ESCALATION_GLOBS` (`:41-52`): `**/migrations/**`,
   `**/conftest.py`, `**/factories.py`, `**/fixtures/**`, `**/urls.py`, `**/middleware.py`,
   `**/signals.py`, `**/apps.py`, `pyproject.toml`, `uv.lock`. FLS adds `config/**`,
   `freedom_ls/site_aware_models/**`, `freedom_ls/content_base/**` (`pyproject.toml:120-124`).
4. Owning app (`:324-326`): `decide_app_path`. `edges is None` (app map `docs/app_structure.md` missing or
   unparsable) -> **`full`** (`:219-220`). Otherwise select the app's tests dir plus importers' tests dirs
   (runtime deps chain, test-only deps one hop, `importers()` `:183-204`); UI globs keep Playwright (`:231-235`).
5. Tooling globs (`:328-330`): `.claude/*/scripts/**` and `tests/**` -> `tests`; FLS adds plugin scripts,
   templates, `claude_plugins/*/**/*.md` (four plugin-prompt tests), `*.drawio.svg`, `fls-content/**`.
6. **No rule matched (`:332-334`): untracked -> `none`; tracked -> `full` ("unmapped path").**

Tier = `full` if any decision is `full` (`:489-490`), else `targeted` if anything selected, else `none`
(`:491-494`). `--tests-changed-in` decisions are excluded from the tier (`:480-487`, `branch_test_decisions` `:387-405`).
`--range` uses `git diff --no-renames --name-only <range>` (`:351-363`), so both sides of a rename count.

There is no parameter for "this path came from main" and no way to scope an escalation to a set of apps.
Each `--range` simply unions into one flat path list (`:366-384`); provenance is lost before `decide()`.

### `full_run_record.py` (generic, `claude_plugins/sdd/scripts/`)

`resolve()` (`:132-155`), in order:

1. No `--selector` -> `full` "no tier selector" (`:133-134`). Also `run_test_tier.md:23-26` when no definition.
2. Branch diff `--range origin/main..HEAD --working-tree` selects `none` -> `none` (`:137-139`). This is what
   protects a spec-only branch. Note `origin/main..HEAD` is the branch's own commits only, but `--working-tree`
   adds uncommitted and untracked paths (untracked unmapped files count as `none`, `select_tests.py:332-333`).
3. No/invalid record -> `full` (`:140-142`). Record missing causes: never ran a full run in this worktree;
   dirty tracked tree at start (`:169-171`); HEAD moved during the run (`:189-190`); non-pass verdict (`:180-181`);
   detached HEAD (`:62`, `:182-184`); the `.sdd-work/` directory deleted.
4. Recorded commit gone (`git rev-parse --verify`) -> `full` (`:143-144`), e.g. after gc following a rebase.
5. Selector over `--range <sha>..HEAD --working-tree`: `none` -> `none`, `targeted` -> targeted, else **`full`**
   (`:147-155`). After a rebase this tree diff contains **both** the branch's changes and everything main brought
   in since the recorded commit (as the README says, `commands/README.md:195`: "escalation globs ... still force
   `full`, including files main brought in"). This is the exact behaviour the second answer wants changed.
6. A selector that exits non-zero or prints no `tier:` line is `full` (`selected_tier` `:107-129`). That includes `git failed` from an unreachable ref.

### `rebase_main.md` Step 9 (`ds`, generic)

- `<tier>: none` -> no run (`:195`). `full` -> full (`:197`).
- `targeted` (`:199-211`): (1) branch diff `--range origin/main..HEAD`; `none` -> report `none` and stop (spec-only
  branches stop here). (2) `--range $OLD_BASE..origin/main --range $REPLAYED_TIP..HEAD --tests-changed-in origin/main..HEAD`.
  A main-side path matching an escalation glob, or an unmapped tracked path, makes step 2 `full` even if the
  branch's tiny diff is far from it. Step 2 is the only place that already separates main's diff from the branch's
  diff, but only to compose arguments, not to weigh them differently.
- It does not use the full-run record at all.

### `finish_worktree.md`

- Step 1 (`:80-85`): `<tier>: full`, always, no record check. Later text (`:254`) already says "Step 1's full run wrote
  the full-run record, so a pass tests only what the rebase brought in", so the record-reading checkpoint code
  path exists in Step 7 only (`:252-264`).
- Step 7 loop (`:229-243`): each pass = rebase with `none`, then checkpoint (resolve -> `none` / targeted / full), then `land`.
  A checkpoint can still reach `full` through the paths above (record missing, escalation glob from main, unmapped tracked path).
- Step 0 (`:31-32`) rebases with `none` so the idea's case, "rebase on a spec-only branch triggers a full rerun", is Step 1's run, not the rebase itself.

### `upstream_change_review.md` (`claude_plugins/sdd/resources/`)

Not a test tier. It scans paths main brought in and may pause the spec; a spec-root-only change exits 3 (no worker, no pause)
(`:15-16`). It uses `<old-base>`, which is the same input the new "main's diff" logic needs.

## 4. Concrete trace: a branch that only changed `spec_dd/` rebases onto a main that moved

Case A: `/sdd:finish_worktree` (the idea's case).
1. Step 0: pre-step rebase, `tier: none`. Replays commits. No tests.
2. Step 1: `run_test_tier.md` with `full`. Unconditional, so the whole suite runs. Even though
   `implement_plan` Step 3 already passed and recorded, and the branch added only spec files since.
   Fix per answer 1: use `checkpoint`. `resolve()` returns `none` at `full_run_record.py:137-139`.
3. Step 7 loop after `origin/main` moves again: checkpoint resolves `none` (branch diff all `spec_dd/**`). OK already.

Case B: `/sdd:rebase_main` by hand or another command's Step 0 (default `targeted`) on a spec-only branch.
Step 9.1 branch diff -> all `spec_dd/**` -> `none` -> stops. OK. It would be `full` only if the branch diff
itself contained a non-none path. Candidates that look harmless but are not `none`:
- `.claude/**/*.sh`, `.claude/**/*.py`, `.claude/settings.local.json`-style files not under the glob (`*.json` is covered),
  `.claude/**/*.yml|toml|txt`, `.claude/**/*.sh` outside `.claude/*/scripts/**` -> **unmapped -> full**
  (`select_tests.py:334`). Under `.claude/*/scripts/**` it selects `tests` (targeted, not full).
- `.claude/**/*.md` is `none`, so wording tweaks are fine; `.claude/settings.json` is `none` (`test_select_tests.py:348`).
- Root files: `package.json`, `package-lock.json`, `tailwind` config, `Dockerfile`, `.pre-commit-config.yaml`,
  `.python-version`, `manage.py`, `scripts/*`, `demo_content/**` etc. are none of the rule kinds -> unmapped -> `full`.
  (I could not list the tracked files; the glob command returned only `.venv`. Confirm by running the selector on `git ls-files`.)
- Nested markdown outside `docs/`, e.g. `pkg/README.md`, is `full` on purpose (`test_select_tests.py:352`), but under
  `claude_plugins/*/**/*.md` the FLS tooling entry maps it to four tests.

Case C: the branch has a code change, main brings in a migration, `conftest.py`, `pyproject.toml` or something under
`config/` or `content_base/`. Checkpoint `resolve()` step 5 and rebase_main Step 9.2 both escalate to `full`, because
provenance is lost. This is the second answer's target.

Case D: spec-only branch, but a checkpoint resolves after the record is lost. `resolve` step 2 returns `none` before it
reads the record, so a missing record is harmless for spec-only branches. It matters for code branches (Case C).

Also confirm: no path through `frontend_check.md` or `upstream_change_review.md` runs tests.

## 5. What a design change touches (reuse and conflict)

Reusable as is:
- `full_run_record.py` verbs `start`, `write`, `read`, and `resolve`'s `none` shortcut (`:137-139`) and
  record-missing handling.
- `select_tests.py` decision functions (`decide`, `decide_app_path`, `importers`) and the `Decision` model (`:100-106`),
  which already carries `kind`, `selects`, `reason`.
- `run_test_tier.md` Step 2 and 3, the `checkpoint` tier, and `finish_worktree.md:252-264` (the checkpoint run text
  already exists once; Step 1 can point at the same procedure).
- The app map edges (`generate_app_map.py` `Edges` `:87-90`, `parse_existing_edges`) give "apps the branch depends on".
  `importers(app, edges)` goes the other way (apps that import `app`). The second answer's "apps main changed that the
  branch's apps depend on" needs the *dependency* direction (runtime deps of the branch's apps), which has no helper yet;
  `forbidden_modules` (`generate_app_map.py:497-500`) shows the `edges.runtime` lookup pattern (`src == app`).

New logic the answers imply (not present today):
- A way to give `select_tests.py` ranges with different roles: branch-side ranges vs main-side ranges, so main-side
  paths are filtered to the branch-related set before `decide()`, and so an escalation glob on a main-side path only
  escalates to that set (tests of the branch's apps plus dependencies main changed), not to `full`.
- Dependency files (`pyproject.toml`, `uv.lock`) keep escalating even from main. They are inside `ESCALATION_GLOBS` along with
  the others, so the split is needed in config or code: no list today separates dependency files from fan-out files.
- `full_run_record.py resolve` must tell main-side from branch-side. It cannot recover that from `sha..HEAD` alone after a
  rebase. It would need the old base (`pre_step_rebase.md`/`rebase_main.md` already keep `old-base` and `old-tip`; the
  finish loop calls the rebase directly, so `old-base` is available there but `resolve` does not take it).
- `rebase_main.md` Step 9.2 would carry the same rule.

Conflicts and cautions:
- Plugin genericity (`CLAUDE.md`): `select_tests.py`, `full_run_record.py`, `run_test_tier.md`, `rebase_main.md`,
  `test_tiers.md` and the sdd commands must not name FLS apps (`site_aware_models`, `content_base`, `config/`). The FLS list
  stays in `[tool.test_tiers]` (`pyproject.toml:111-164`). Any new concept (e.g. which escalation globs are "dependency
  files that always escalate") needs a generic key in `[tool.test_tiers]` or a generic constant, not an FLS path. Today
  the generic `ESCALATION_GLOBS` already holds Django-shaped names; that is existing generic content for `ds`.
- `tests/test_test_tiers.py` bans spelling pytest invocations in plugin prompts (`:53`) except allowlisted files, so edits to
  `finish_worktree.md` / `run_test_tier.md` must not add raw pytest lines. The flags live only in `test_tiers.md`.
- `tests/test_rebase_prompts.py` and `tests/test_check_diagrams.py` (listed in the tooling `tests` for plugin `*.md` and `*.drawio.svg`)
  guard the prompts and diagrams, so a changed prompt must update the matching diagram or the check fails.
- The README "When the full suite runs" section (`commands/README.md:182-203`) states the two full points; Step 1 becoming a
  checkpoint changes item 2 and the sentence "Step 1's full run wrote the record"
  (`finish_worktree.md:254`, README `:197`). The diagram `docs/diagrams/finish_worktree.drawio.svg` has a "Full tier" box
  and the red full-run markers; `overview.drawio.svg` also marks both runs in red (README `:184`); `rebase.drawio.svg` mentions "full tier".
  `implement_plan.drawio.svg` is unchanged (Step 3 stays).
- Step 1 as a checkpoint: with no record (e.g. implement_plan ran in another worktree or the record was lost) the checkpoint
  still resolves `full` when the branch has code, so the first and only guaranteed full run is still implement_plan Step 3.
  The finish report must say whether Step 1 ran `none`/`targeted`/`full`.
- Another reason Step 1 can legitimately need `full`: `implement_plan` Step 3 fix sub-agents run only `targeted` over the fix range
  (`:133`), then the "full run in finish_worktree covers the fixes" (README `:186`). With Step 1 a checkpoint, those fixes are covered
  only if the record's SHA predates them. The record is written by the Step 3 full run itself before the fixes, so `sha..HEAD` includes them
  and the selector picks tests for them: consistent, but worth a test.

## 6. Existing tests (all under `tests/`; there is no plugin-local test dir)

- `tests/test_select_tests.py` (58 tests): tier rules, `why:` lines, glob facts (`:339-363`: conftest/factories/fixtures full; `.claude/settings.json` none; `pkg/README.md` full; unmapped `scripts/deploy.sh` full `:330-336`), determinism, importers, `--tests-changed-in`.
- `tests/test_full_run_record.py`: `resolve` cases (`:125-278`: no record -> full; spec-only no record -> none; spec-only + uncommitted app edit -> full; none after record; targeted over range; lock file -> full; unusable/unreadable record -> full; **`:258` "record taken before a rebase onto a moved main sees what main changed"**, the test that pins the behaviour answer 2 wants changed), missing selector, selector outside root, `read`, `start`, `write` guards (`:340-418`).
- `tests/test_test_tiers.py` (pytest-invocation ban), `tests/test_select_tests_wrapper.py` (the `.claude/ds/scripts/select_tests.sh` wrapper, an `exec uv run python .../select_tests.py "$@"`, so new flags pass straight through), `tests/test_rebase_prompts.py`, `tests/test_rebuild_after_rebase.py`, `tests/test_check_diagrams.py`, `tests/test_concrete_spec_integration.py`, `tests/test_update_concrete_projects.py`.

## 7. Prior work

- Done spec `spec_dd/3. done/2026-11-19_16:16_spec_dd_efficiency_and_docs/` (`1. spec.md:22-36,59,73-96,110,148`) introduced the **checkpoint tier**, the **full-run record**, `full_run_record.py`, the Step 7 loop's checkpoint run, and the README "When the full suite runs" section. That spec kept finish Step 1 as `full` and the escalation globs applying to main's files ("including files main brought in" is documented behaviour, README `:195`).
- Done spec `spec_dd/3. done/2026-10-09_09:03_make-sdd-more-efficient/research_current_test_runs.md` and `2026-10-01_09:40_database-keeps-going-down/research_test_run_sites.md` map earlier test-run sites; read them before choosing the new design.
- The current worktree's `research_best_practices.md` exists next to this file.

## 8. Open points for the spec

- Where to hold "main-side vs branch-side": new selector flags (e.g. role-tagged ranges) vs `resolve` computing the split from `old-base`. The wrapper script is a pure exec, so either works without touching the FLS wrapper.
- "Branch-related set" definition: apps the branch's changed paths own (and their importers, as today) plus apps main changed that the branch's apps depend on (runtime edges, plus test-only edges when a branch test imports it). Unowned main paths (root files, `.claude`, unmapped) have no "meeting point" with the branch, so the rule must say what they trigger (suggest `none`, or the existing rules unchanged for dependency files only).
- Whether `rebase_main.md` Step 9.2 shares the same filter, and whether `--tests-changed-in` stays as is.
- Where dependency files are named so they stay generic: `pyproject.toml`/`uv.lock` are already in the generic `ESCALATION_GLOBS`; other languages' lockfiles would need a config key.

status: ok
