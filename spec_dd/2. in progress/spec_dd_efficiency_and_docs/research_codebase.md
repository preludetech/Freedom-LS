# Research: codebase (spec_dd_efficiency_and_docs)

Paths are relative to the repo root. Line numbers refer to the worktree at commit 95288722c.
I had no shell, so sizes are non-blank line counts from Grep, not `wc` words (see section 7).

## 1. Where SDD runs tests

### 1.1 The tier machinery

- `claude_plugins/sdd/commands/protected/run_test_tier.md:12-22`. `.claude/sdd/config.md:23` sets `Test tiers` to `claude_plugins/django-stack/resources/test_tiers.md`.
  - A blank value falls back to a plain `uv run pytest`, which is always a full run.
  - The helper only runs and reports. The caller fixes failures (`run_test_tier.md:29`).
- `claude_plugins/django-stack/resources/test_tiers.md:6-33` defines the tiers.
  - `none` runs no pytest.
  - `targeted` runs `.claude/ds/scripts/select_tests.sh <diff args>`.
  - `full` runs `uv run pytest -n auto` through `run_tests.sh`. `run_tests.sh` sizes xdist workers from free memory and retries crashed workers (`test_tiers.md:44-66`).
  - `test_tiers.md:92-98`: on failure, re-run `--lf`, then re-run the whole tier.
- `claude_plugins/django-stack/scripts/select_tests.py` picks the tier. Rules apply first-match-wins per changed path (`select_tests.py:291-334`).
  - `none` globs (`:30-38`): `docs/**`, `.github/**`, root `*.md`, `.claude/**/*.md`, `.claude/**/*.json`, and others. `pyproject.toml:111-114` adds `spec_dd/**` and `claude_plugins/**/*.jsx`.
  - Escalation to **full** (`:41-52`): migrations, conftest, factories, fixtures, urls.py, middleware, signals, apps.py, `pyproject.toml`, `uv.lock`. `pyproject.toml:117-121` adds `config/**`, `site_aware_models/**` and `content_base/**`.
  - An unmapped tracked path is **full** (`:334`). An unmapped untracked path is `none` (`:332`).
  - `claude_plugins/*/**/*.md` maps to 3 tooling test files (`pyproject.toml:149-155`). `claude_plugins/*/scripts/**` and `templates/**` map to `tests/` (`:133-139`).
- Tests that read plugin prompts constrain wording changes to commands. `tests/test_test_tiers.py:31` reads `run_test_tier.md`. `tests/test_update_concrete_projects.py:16-17` reads `do_qa.md` and `roadmap.md`. They run whenever any `claude_plugins/*/**/*.md` changes.

### 1.2 Every step that runs tests

| Command and step | Tier | Trigger | Repeats on unchanged code? |
|---|---|---|---|
| `protected/pre_step_rebase.md:15-52`, Step 0 of start, spec_from_idea, spec_review, plan_from_spec, implement_plan, do_qa, qa_fix, document, address_pr_review. Also the fls-dev `update_*` commands. It delegates to `rebase_main.md` Step 9. | `targeted` by default (`rebase_main.md:10`). Full only if `<tier>` is `full` or the selector escalates. | Runs only when `origin/main` is not already an ancestor of HEAD (`rebase_main.md:57-69`). | Not on identical code. It re-triggers each time main moves. Each spec command rebases first, so every command boundary is a chance to re-test. |
| `rebase_main.md:188-215`, Step 9 | The selection takes two ranges. (1) The branch diff `origin/main..HEAD`: `none` gives `tier: none` and the step goes straight to pre-commit (`:200`). (2) Main's diff `$OLD_BASE..origin/main` plus post-replay fix-ups, with the branch's tests: `none` gives `none`. | | The tier depends on **what main brought in**, not on what the branch changed. If main touched `pyproject.toml`, `uv.lock`, a migration, `config/**`, `content_base/**` and so on, the result is full, even when the branch holds only spec files. |
| `rebase_main.md:217-223`, Step 10 | `uv run pre-commit run --all-files` | Every rebase | Yes |
| `implement_plan.md:47`, each batch | `targeted --working-tree` | Per batch | No |
| `implement_plan.md:79`, after a parallel wave | `targeted --range <wave-base>..HEAD` | Per wave | Overlaps the per-batch runs |
| `implement_plan.md:113`, each review-fix batch | `targeted` | Per fix | No |
| `implement_plan.md:122-124`, Step 3 | **full** | Always after all batches. Any unmet criterion triggers a fix, then "repeat from step 1", which is **another full run**. | Yes |
| `do_qa.md:737-749`, "Full run after the last fix" | **full** | When at least one bug was FIXED this run | Yes. The qa-bugfixer already ran `targeted` per fix (`qa-bugfixer.md:98-110`). |
| `qa_fix.md:206-212`, Step 7 | **full** | When a `code` or `design` fix was committed | Yes |
| `finish_worktree.md:30-31`, Step 0 | Passes `<tier>: full` to the pre-step rebase | Only if `origin/main` moved. It then runs full unconditionally (`rebase_main.md:192`), even when the branch diff is spec-only. | |
| `finish_worktree.md:67-79`, Step 1 | **full**, unless Step 0's rebase already reported `tier: full` | Otherwise always. It runs `Pre-test rebuild` first (`.claude/sdd/config.md:24`). | Yes. This is the "proven branch" shortcut, but it is only skipped when a rebase just happened. |
| `finish_worktree.md:156-162`, Step 7 item 3 (exit 7) | **full** (`rebase_main` with `full`) | `origin/main` moved after Step 0 | Yes. A second exit 7 gives `blocked`. |
| `address_pr_review.md:53-55` | `targeted --working-tree` | Per run | |
| `commit_quickly.md:11` | none (explicitly no tests) | | |
| `qa-bugfixer.md:76-110` | single test RED/GREEN, then `targeted` | Per bug | |
| `fls-dev/commands/protected/frontend_check.md` | Browser smoke, not pytest | After a rebase that changed something (`pre_step_rebase.md:54-66`). It may spawn up to 3 bugfixers. | |
| `.github/workflows/tests.yml` | CI runs the whole suite on the PR (`address_pr_review.md:55` calls it "the backstop") | | Yes |

### 1.3 Full-suite count for a normal start to finish cycle

- **Minimum, no main movement:** `implement_plan` Step 3 (1), `do_qa` full-after-fix (0 or 1), `qa_fix` Step 7 (0 or 1), `finish_worktree` Step 1 (1). That is 2 to 4, plus one full CI run on the PR.
- **Each extra full run:**
  - A fix after the Step 3 full run repeats it (`implement_plan.md:124`).
  - Any rebase whose main-diff escalates triggers one, in whichever command ran next (up to 8 commands per spec).
  - A rebase in `finish_worktree` Step 0 or Step 7 item 3 runs full unconditionally.
- A change in `pyproject.toml`, a migration or `config/**` lands on `main` often, so a long-lived spec realistically sees 4 to 7 full runs.
- None of the later runs are fed any record that the code is unchanged. `run_test_tier.md` has no cache, no "tree hash already passed" check and no checkpoint concept.
- `plan_from_spec.md:66` asks every slice to be committable "with the full test suite passing". That is a plan-writing rule, not a run.

### 1.4 Why a spec-only diff triggers a full run

1. `finish_worktree.md:30` hard-codes `<tier>: full` for the rebase. `rebase_main.md:192` then runs full regardless of the diff.
2. For the default targeted tier, the selection is driven by main's diff (`rebase_main.md:203`). It escalates on main's `pyproject.toml`, migrations and similar, not on the branch's content.
3. `finish_worktree.md:69` runs a full tier whenever the rebase did not just run one, even if nothing but `spec_dd/**` changed since the last full run.
4. `spec_dd/**` is already a `none` path, so `select_tests.sh --range origin/main..HEAD` correctly says `none` for the branch half (`rebase_main.md:200`).
5. The `Pre-test rebuild` (`.claude/fls-dev/scripts/rebuild_after_rebase.sh`) also runs before this full run (`finish_worktree.md:69-75`).

## 2. Rebase on main

- `pre_step_rebase.md` is the wrapper. All depth-0 feature-branch commands follow it as Step 0.
  - Skipped on `main` or when no spec directory matches (`:17-24`).
  - Paused if `todo.md` holds an unticked item naming `upstream_change_review.md` (`:26-37`).
  - Step 1 (`:41-52`) reads `Rebase command` (`.claude/sdd/config.md:14` gives `claude_plugins/django-stack/commands/rebase_main.md`).
  - Step 2 (`:54-66`) runs `Front-end check` (`claude_plugins/fls-dev/commands/protected/frontend_check.md`, `.claude/sdd/config.md:15`) and pushes any commits it made.
  - Steps 3 to 5 (`:68-173`) run `upstream_change_scan.sh`. On exit 2 they spawn one `sdd-worker` that writes `upstream_change_review.md`. A `direction: changed` verdict pauses the spec with a `(user)` todo item (`:155-169`).
- `rebase_main.md`, the ds plugin's step list:
  1. Check the branch (Step 1).
  2. Commit work in flight as a wip commit (Step 2).
  3. Fetch, and stop early with `rebased: no` if main is already contained (Step 3).
  4. Record the start; stop if there are merge commits or another worktree is mid-merge (Step 4).
  5. `git rebase origin/main` (Step 5).
  6. Resolve conflicts (Step 6): lockfiles and migration renumbering are handled by rule.
  7. Lost-change check script (Step 7) and `makemigrations --check`.
  8. Rebuild and migrate (Step 8, `.claude/ds/config.md:30`).
  9. Tests (Step 9).
  10. `pre-commit run --all-files` (Step 10).
  11. Summarise (Step 11).
  12. `git push --force-with-lease --force-if-includes` (Step 12).
- Return contract: `rebase_main.md:248-256` and `pre_step_rebase.md:175-182`. It carries `tier: none|targeted|full`. `finish_worktree.md:69` already uses `tier: full` as "branch proven", but no other command reuses a prior full-pass result.
- `finish_worktree.md` Step 7 item 3 (`:156-162`) re-reads the same Rebase command with full. It cannot call the pre-step rebase again because the spec directory is under `3. done/` by then.
- Docs: `claude_plugins/sdd/commands/README.md` never mentions the pre-step rebase. It is only in `protected/pre_step_rebase.md` and `claude_plugins/sdd/README.md:52-56`.

## 3. `finish_worktree.md`: every stop

- Step 0 (`:28-41`): `pre_step_rebase` status other than `ok` is relayed and the command stops.
  - Rebase `blocked` on conflicts.
  - A squash-merged PR replays as conflicts: "Do not automate that" (`:39-41`).
  - `paused`, when an upstream-change review awaits a decision.
- Step 0.5 (`:43-65`): `land_on_main.sh sync`. Any non-zero exit gives `status: blocked`. Exit 3 comes from `claude_plugins/sdd/scripts/land_on_main.sh:120-124, 132-141, 149-155`:
  - an operation in flight in the main worktree (`:67-81`);
  - an uncommitted change overlapping the incoming files (`:92-96`);
  - local `main` diverged from `origin/main` (`:132-136`);
  - **local `main` ahead with no worktree checked out on it** (`:137-142`: "push main yourself"). This is the "main has not been pushed" stop. When a main worktree exists, the script already pushes (`:143-148`); only a rejected push is exit 6.
  - the fast-forward of main failing (`:149-155`).
- Step 1 (`:76-79`): a full failure gives `status: failed · reason: full run failed before landing`. Nothing is moved until a human fixes it. There is **no flaky-test diagnosis, no subagent fix and no re-run**. `test_tiers.md:92-98` ("When a targeted run or full run fails") addresses the agent that owns the change, never the mechanic that `finish_worktree` delegates to.
- Step 8 (`:170-176`): a non-empty `git status --porcelain` gives `failed`.
- Step 7 (`:139-166`):
  - the PR guard blocks on `CHANGES_REQUESTED` (`:141-143`);
  - exit 7 gives one retry rebase with a full run, then `blocked: origin/main keeps moving` (`:156-162`). This conflicts with the idea's "keep going every time main moves".
  - exit 3, 6 or 8 give `blocked` (`:164-166`).
- The idea's wish to rebase without a full re-run each time main moves and to treat that as an incompatible-change question maps onto `pre_step_rebase.md` Steps 3 to 5. That review already emits `direction: unchanged|changed` and is skipped on a done spec (`finish_worktree.md:158-160`).

## 4. `address_pr_review` references (to remove)

- `claude_plugins/sdd/commands/address_pr_review.md` (47 lines): the command itself.
- `claude_plugins/sdd/commands/README.md:96` (Step 6.2 "Run `/sdd:address_pr_review`"), and `:11` and `:91` mention "address review feedback".
- `claude_plugins/sdd/README.md:18` (command list), `:25-26` (Fetch PR comments description), and "Commands (16 files)" at `:15` (count to update).
- `claude_plugins/sdd/commands/init.md:145-146` (`PR Hooks`, fourteen sections at `:131`), and `:321` (blank default behaviour).
- `claude_plugins/sdd/commands/protected/setup_todo_list.md:86` (template item). The README line `:11` also describes the section.
- `.claude/sdd/config.md:77-79` (`## PR Hooks`, `Fetch PR comments: .claude/ds/scripts/fetch_pr_comments.sh`).
- `.claude/ds/scripts/fetch_pr_comments.sh`, `claude_plugins/django-stack/scripts/fetch_pr_comments.sh`, `claude_plugins/django-stack/templates/wrapper_scripts/fetch_pr_comments.sh`, and `claude_plugins/django-stack/README.md` (the ds side of the PR-comments script).
- `.claude/settings.json` (a permission entry for `fetch_pr_comments.sh`).
- Existing `todo.md` files carry the item: 7 in progress (including this spec's own `todo.md:27`) plus `spec_dd/0. paused/content_snapshots/todo.md:62`. Done specs do not carry it. Search found 0 ticks of `address_pr_review` in `spec_dd/3. done/*/todo.md`, so it has never been used.
- No `tests/` file references it (grep of `tests/` came back clean). Removing a `claude_plugins/**/*.md` selects 3 test files (section 1.1).
- Other references: `spec_dd/1. next/educator-interface-refactor/research_collisions.md:47` is a note in a different spec, not code.
- Careful: `fetch_pr_comments.sh` lives in the generic ds plugin. Whether it is only used by `address_pr_review` is not confirmed (grep found no other caller). Treat removing it as a separate decision for the spec to make.

## 5. Existing docs, diagrams and hooks

- The SDD workflow guide is `claude_plugins/sdd/commands/README.md` (81 lines of prose, no diagrams). `claude_plugins/sdd/README.md` is the plugin inventory (counts "Commands (16 files)", "Agents (4)", "Skills (5)", "Scripts (9 files)", "Resources (9)"). The counts will drift when commands are removed.
- There is no `docs/` page about SDD. `docs/` is product and app documentation (`docs/app_structure.md`, `docs/product/`).
- **No SDD diagrams exist.** The only `*.drawio*` files are demo course content (`demo_content/functionality_demo_end_with_topic/images/graph1.drawio.svg` and the quiz twin). `spec_dd/1. next/roadmap_diagrams/` holds generated roadmap SVGs (`scripts/roadmap.py`), not drawio.
- Where to put `.drawio.svg` files affects tests. `select_tests.py` treats an unmapped tracked path as **full** (`:334`). A new `*.svg` under `claude_plugins/sdd/` or elsewhere that is not under `docs/**`, `spec_dd/**` or `.claude/**/*.md|json` would trigger a **full run** for the very spec that adds it. `docs/**` is a `none` glob (`select_tests.py:31`). A diagram under `claude_plugins/sdd/docs/` would need a new `none` entry in `pyproject.toml [tool.test_tiers] none`. Either way the spec has to name the location.
- "Hooks" in the SDD sense means the sections of `.claude/sdd/config.md` (16 sections; `init.md:131` says "fourteen" and is stale). Each is read by a named command:
  - Worktree Scripts: `start_worktree`, `finish_worktree` Step 2, `implement_plan` (Parallel batches, Memory capacity, Batch memory).
  - Rebase Hooks: `pre_step_rebase` Steps 1 and 2.
  - Design Hooks: `implement_plan` Design check.
  - Test Hooks (`Test tiers`, `Pre-test rebuild`): `run_test_tier` and `finish_worktree` Step 1.
  - Plan Review Hooks: `plan_from_spec`.
  - Review Hooks (`Comment standard`, `Test standard`): `implement_plan` Batch review and `document` Step 2b.
  - Documentation Hooks: `document` Step 2 (`.claude/sdd/config.md:36-41`; skills `ds:app_map`, `fls-dev:update_upgrade_notes`, `update_product_docs`, `update_claude_plugin_fls_content`, invoked as `mode: hook`, `document.md:20-34`).
  - QA Hooks, QA Login, QA Dev Data, Testing Skills: `do_qa`, `qa-bugfixer`, `setup_todo_list` (QA command).
  - PR Hooks: only `address_pr_review`.
  - Rule Files: `capture-feedback` and QA.
  - Vocabulary Sources.
- The hook-mode convention: a command run with `mode: hook` skips the pre-step rebase (`pre_step_rebase.md:6-7`; `fls-dev` commands `update_product_docs.md:72`, `update_upgrade_notes.md:61`). `start.md` runs `register_design` and `spec_from_idea` in hook mode (`start.md:103-114`).
- There are no Claude Code `settings.json` hooks for SDD. `.claude/settings.json:183-` holds `.env` guard PreToolUse hooks and SessionStart; `claude_plugins/django-stack/hooks/hooks.json` holds PostToolUse and PreToolUse. A diagram showing "where hooks fit" means the config-section hooks.
- Command flow to draw, as written:
  - `start` (`start.md`, Steps 0 to 8) delegates to mechanics (setup_todo_list, move_spec_to_in_progress, start_worktree), then `EnterWorktree`, writes `answers.md`, then runs `register_design` and `spec_from_idea` in hook mode.
  - `spec_from_idea` fans out research to `sdd-worker` agents, then the review wave.
  - `plan_from_spec` fans out the plan review dimensions plus the skills scan.
  - `implement_plan` runs batches (`general-purpose`/sonnet) per slice, waves in batch worktrees, then Design check and Batch review, then the full tier.
  - `do_qa` and `qa_fix` follow.
  - `document` runs the hooks, then 2b items, then `make_pr_quickly`.
  - `finish_worktree` rebases, tests, archives, lands.

## 6. Constraints that apply

- `CLAUDE.md` (Plugins section): `claude_plugins/sdd`, `django-stack` and `productivity` stay generic. Everything FLS-specific goes through `.claude/sdd/config.md`, `.claude/ds/config.md` or `pyproject.toml [tool.*]`, or lives in `claude_plugins/fls-dev`. Candidates for this spec's changes:
  - Which tier a step uses and the checkpoint names must be generic (`full`/`targeted`/`none`). The FLS-specific globs (`spec_dd/**`) are already in `pyproject.toml [tool.test_tiers]`. A new "diagram location" `none` glob belongs there.
  - A "flaky test diagnosis" instruction in `finish_worktree.md` (generic sdd) must not name FLS tests. The playbook for FLS flakes goes in `claude_plugins/fls-dev/skills/testing/SKILL.md` or through a `Test Hooks` config key.
  - `rebase_main.md` is in the generic ds plugin. A "skip the full tier when the branch changed nothing a test can see" rule goes in the generic selector logic.
- `sdd` depends only on `productivity` (`claude_plugins/sdd/README.md:6-9`). `fls-dev` hooks (`frontend_check.md`, `design_check.md`) are named by config, not by `sdd`.
- Do not delete TODO or `@claude` comments (CLAUDE.md). I did not check the touched files for any.
- Never rewrite `idea.md`.

## 7. Token size

`wc` was unavailable. Figures are non-blank line counts from Grep (word counts not measured). Lines in several files run long, for example `implement_plan.md:79` and `plan_from_spec.md:138` were truncated as "long matching line".

| File | Non-blank lines |
|---|---|
| `commands/do_qa.md` | 610 |
| `scripts/roadmap.py` (not loaded as prompt) | 553 |
| `commands/init.md` | 322 |
| `commands/roadmap.md` | 211 |
| `commands/qa_fix.md` | 189 |
| `commands/register_design.md` | 184 |
| `agents/qa-bugfixer.md` | 152 |
| `commands/finish_worktree.md` | 143 |
| `commands/protected/pre_step_rebase.md` | 131 |
| `commands/spec_from_idea.md` | 122 |
| `commands/plan_from_spec.md` | 113 |
| `commands/implement_plan.md` | 101 (but dense, several paragraphs over 1,000 characters at `:36-81`) |
| `commands/commit_quickly.md` | 96 |
| `skills/capture-feedback/SKILL.md` | 96 |
| `commands/start.md` | 89 |
| `resources/launcher_editing.md` | 89 |
| `resources/roadmap_format.md` | 90 |
| `skills/claude-code-authoring/SKILL.md` | 83 (+4 resources totalling 194) |
| `commands/README.md` | 81 |

- `claude_plugins/django-stack/commands/rebase_main.md` is 260 lines and the largest prompt in the rebase path. `django-stack/resources/test_tiers.md` is 98 lines.
- Files that most commands load (counts of references across `sdd/commands` and `sdd/agents`):
  - `spec_from_idea.md`: 9 references.
  - `plan_from_spec.md`: 5.
  - `roadmap.md`: 5.
  - `spec_review.md`: 5.
  - `document.md`, `qa_fix.md`, `register_design.md`: 3 each.
  - They point at `resources/writing_standard.md` (38 lines), `domain_vocabulary.md`, `commit_and_push.md`, `skills/claude-code-authoring/resources/fanout_recipe.md` (73 lines) and `claude-code-authoring/SKILL.md`.
- Every feature-branch command reads `pre_step_rebase.md` (131 lines). A depth-0 command run in an unmoved branch pays that full read to learn it has nothing to do (`rebase_main` returns `rebased: no` at Step 3, but the whole file has already been loaded).
- `do_qa.md` has 610 lines. It is also read in part by `frontend_check.md:12` and `:44-80`, which cite rules 1, 3, 4 and Steps 3 to 16 of `do_qa.md`.
- Token savers I see (to be confirmed by the best-practice research):
  - Split `pre_step_rebase.md` so the common path "up to date" is a few lines and the upstream-review path loads lazily.
  - Split `do_qa.md` and `init.md`.
  - Trim `implement_plan.md`'s dense paragraphs into tables.
  - Remove `address_pr_review.md`, `commit_quickly.md` (96 lines) and `init.md` overlaps.

## 8. Candidates for "unused" commands and steps

Evidence: ticks of `/sdd:*` items in `spec_dd/3. done/*/todo.md` (Grep of `[x] ... /sdd:<cmd>`), plus how late the item entered the template.

- `address_pr_review`: 0 ticks in all done todos (checked 166 files with any matching command). Confirmed unused; it is removed.
- `spec_review` as a standalone command: ticked in 13 todos from 2026-10-01 to 2026-10-22 and not since. `spec_from_idea` already runs the review wave (`commands/README.md:39`).
- `commit_quickly`: no todo item; used ad hoc, not part of the checklist. Keep or confirm with the user.
- `make_pr_quickly`: ticked from `2026-10-29_12:46_more_lead_admin_exports` onwards, and `document` opens the PR (`document.md:65-73`). The standalone command is now only a helper that `document` reads inline. Candidate to fold into `document` or keep as helper.
- `register_design`: heavily used (design-prefixed specs).
- `qa_fix`: ticked in only 3 recent todos (2026-11-16 to 2026-11-18). It is new, not unused.
- `capture_feedback` (17 lines): a thin wrapper over the `capture-feedback` skill.
- `roadmap`: used. `init`: one-time.
- Lower-value steps inside commands:
  - `pre_step_rebase` Steps 3 to 5 (upstream-change scan and review worker) cost an agent spawn each time main changed something; it returned `changed` in three done specs (`educator-interface-looks-good`, `educator-interface-6-cohort-administration`, `learner-facing-ux-refinements`), each with real plan or spec changes.
  - `finish_worktree` Step 5 `update-claude-project-settings` and Step 2 leftover batch worktree sweep.
  - `do_qa` "Full run after the last fix" and `qa_fix` Step 7 duplicate the `implement_plan` Step 3 and `finish_worktree` Step 1 full runs.
  - `Worker memory (MB):` is blank in `.claude/sdd/config.md:10`.
  - `setup_todo_list.md:36` mentions `3. frontend_qa.md` as "also covered by the plan step".
  - `Fetch PR comments` hook, as the only user of `## PR Hooks`.
  - `.claude/sdd/config.md:84-86` lists the same Panel-framework rule file twice under `## Rule Files`.
- Git log frequency was not collected (no shell). The above is from todo ticks only.

## 9. Gaps and open points for the spec

- No checkpoint list exists. The user's answer ("the spec names them") means the spec must pick, from section 1.2, which of implement_plan Step 3, qa_fix Step 7, do_qa full-after-fix, finish_worktree Step 1 and the rebase escalation keep a full run. A natural rule: a full run only when the tree changed since the last recorded full pass, plus at landing (`finish_worktree`).
- No mechanism records "full passed at tree/commit X". `run_tests.sh` and `run_test_tier.md` return a summary line only.
- Flaky-test handling does not exist in `sdd`. The only related text is `django-stack/resources/testing.md:421` (order dependence is a bug) and `skills/testing/SKILL.md:109` (delete or fix flakiness).
- `sdd-mechanic` (Haiku) is the finish_worktree test runner, so it cannot diagnose. A fix needs a non-mechanic subagent. The answers file says fix on the current branch.
- CI duplicates the full run on the PR (`.github/workflows/tests.yml`), so the local landing-time full run is the second full proof.

status: ok
