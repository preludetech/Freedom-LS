# Research: codebase

Question: what in the existing codebase does the "update concrete projects from FLS" command touch,
reuse or conflict with? Paths are relative to the FLS repo unless marked `[FC]` (the First-Class
concrete project at `/home/sheena/workspace/first_class/First-Class-LMS.git/main/`, read only).

## 1. `claude_plugins/fls-dev/commands/concrete/update_fls.md`

No frontmatter (unlike every other command). 241 lines. It runs inside a concrete project and
moves its submodule pointer `submodules/Freedom-LS`.

| Step | What it does | New command |
| --- | --- | --- |
| 1 | `git fetch origin main` in the submodule; list commits that moved a dir into `spec_dd/3. done/`; chronological | Invert: FLS's own `git log` already has them. Pending set = done specs after the concrete's current submodule commit (`git -C <concrete>/submodules/Freedom-LS rev-parse HEAD`). No state file needed. |
| 2 | Dry-run preview table of `upgrade_notes.md` flags; operator confirms | Reuse; one table per concrete project |
| 3a | Parse frontmatter flags; no file means "no notes, infer from `1. spec.md`/`2. plan.md`/diff" | Reuse verbatim |
| 3b | Pre-flight `uv run python manage.py migrate --check` | Reuse, run against the concrete project |
| 3c | `git checkout <commit>` in the submodule | Same action, but the commit must already be pushed to FLS `origin/main` (update_fls Step 5 relies on this) |
| 3d | `uv sync` | Reuse |
| 3e | Flag-driven steps, **settings before migrations**: settings, `makemigrations && migrate`, packages, npm (mirror into concrete's own `package.json`), `npm run tailwind_build`, template review | Reuse verbatim |
| 3f | Template-drift: for each `changed_template_paths`, flag concrete overrides at the same path, never auto-merge | Reuse verbatim |
| 3g | `manage.py check` plus `check --deploy --settings=<prod settings>` (both needed) | Reuse; prod settings module name is concrete-specific |
| 3h | `makemigrations --check` | Reuse |
| 3i | Ensure `tests/test_fls_conformance.py` = `from freedom_ls.contrib.conformance import *  # noqa: F401,F403`; never write `conformance.drop(...)` there; then `uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint and not dev_tooling"`; Playwright MCP for front-end changes | Reuse; adds QA (see 5) |
| 3j | One commit per spec, `Update FLS: <spec-name>`, includes `uv.lock` | Reuse; commit lands in the concrete repo |
| 4, 5 | Final sync to `origin/main`; `git status`; `Update FLS: final sync`; `git push` of the concrete only; if on default branch, branch + PR | Reuse; the submodule needs no push because commits are on FLS `origin/main` |
| Rollback | `git checkout -- .`, `git clean -fd`, `git submodule update --init submodules/Freedom-LS`, `uv sync`, `npm install`, re-run gate | Reuse; but the old rollback stops at "investigate"; new command instead fixes in FLS then retries |

Flags read from `upgrade_notes.md` (schema in `claude_plugins/fls-dev/commands/update_upgrade_notes.md`):
`requires_migrations`, `requires_template_review` + `changed_template_paths`,
`requires_settings_change` + `changed_settings` (block-sequence, `# hard`/`# optional` comments; a
renumbered check id lists `SILENCED_SYSTEM_CHECKS`), `requires_package_upgrade` + `changed_packages`,
`requires_npm_install` + `changed_npm_packages`, `requires_tailwind_rebuild`. 72 specs in
`spec_dd/3. done/` have one; older ones do not (fallback needed).

What inverts: the direction of control. Today a concrete-project session drives and FLS is a
read-only dependency. The new command runs in an FLS worktree, edits another repo on disk, and
owns both the FLS fix and the downstream integration. The per-spec loop becomes: integrate, gate,
and on failure fix in FLS (or write a new idea), push the fix to FLS `origin/main`, advance the
pointer again, retry the same spec.

The file is also the only place the portable pytest `-m` expression is spelled. See Conflicts.

## 2. Plugin boundary and config

`CLAUDE.md` "Plugins": `claude_plugins/sdd` and `claude_plugins/django-stack` stay generic (no FLS
name, path, app or value); FLS content goes in `claude_plugins/fls-dev`; project values reach the
generic plugins only through `.claude/{ds,sdd,fls-dev}/config.md` or `[tool.*]` in `pyproject.toml`.
The new command names `submodules/Freedom-LS`, `upgrade_notes.md` and conformance, so it belongs in
`claude_plugins/fls-dev/commands/` (the `concrete/` dir already holds the sibling). It may call
`sdd:sdd-worker`/`sdd:sdd-mechanic` and read `sdd`'s `commands/protected/*` by path (fls-dev README
says it depends on `sdd` at runtime). Nothing FLS-specific may be added to `sdd`.

Config files in this repo:

| File | Holds |
| --- | --- |
| `.claude/fls-dev/config.md` | `## Dev Credentials` (admin email/password), `## Project Settings` (`Base URL`), `## QA Dev Data` (Content reset, DB drop, DB create, Migrate) |
| `.claude/sdd/config.md` | Worktree Scripts, Rebase Hooks, Design/Test/Plan Review/Review/Documentation/QA/PR hooks, Vocabulary Sources |
| `.claude/ds/config.md` | Dev base URL, credentials (blank), Alpine CSP, admin theme, Rebase Scripts |

Format is `## Section` + `- Key: value` bullets. `config.local.md` is a real convention:
`.gitignore` lines 37-39 ignore `.claude/{ds,fls-dev,sdd}/config.local.md`; commands read
`config.md` then `config.local.md`, local values win (`claude_plugins/sdd/commands/protected/pre_step_rebase.md`
Steps 1-2, `start_worktree.md`, `finish_worktree.md`, `run_test_tier.md`). `.claude/ds/config.md`
says machine-specific values belong in `config.local.md`. Templates:
`claude_plugins/fls-dev/templates/config.md` and `config.local.md`; `[FC] .claude/fls-dev/config.local.md`
is an empty placeholder ("No default keys are shipped yet"). Absolute paths like
`/home/sheena/workspace/first_class/...` are machine-local, so the list of concrete projects belongs
in `.claude/fls-dev/config.local.md` under a new section, not committed `config.md`. Caveat: `sdd
init.md` line 211 notes a `config.local.md` list "replaces the whole list" in one place; a path
list should be a bullet list read from local only, with no committed default to merge.

## 3. Conventions for a depth-0 command (summary)

Sources: `claude_plugins/sdd/commands/spec_from_idea.md`, `commands/README.md`,
`skills/claude-code-authoring/SKILL.md` + `resources/{fanout_recipe,subagents,interactive_cli}.md`,
`agents/sdd-worker.md` (Sonnet; tools Read/Glob/Grep/WebFetch/WebSearch/Write; no Bash),
`agents/sdd-mechanic.md` (Haiku; Bash/Read/Edit/Write/Glob/Skill).

- Frontmatter: `description`, `allowed-tools`, optional `argument-hint`. `update_fls.md` has none
  today; the new command needs it. Helpers read inline have inert frontmatter and keep the caller's
  model, so the caller's `allowed-tools` is the union.
- Runs at depth 0; fan-out only there; subagents cannot nest, cannot ask, cannot run slash
  commands, get input only via the prompt. Questions go through `AskUserQuestion` at depth 0,
  batched up to four, recommended option first, only when the answer changes the outcome and nothing
  on disk answers it. Late questions take a default recorded as an "assumed default".
- One output file per unit; durable artifacts keep their names, scratch goes to `.sdd-work/<phase>_<unit>.md`
  (gitignored); resume by skipping files ending `status: ok`; retry `failed` up to 2; `blocked`
  supplied from code or asked; synthesis reads files, never dumped contents; clean scratch by
  name, never the directory.
- Return contract: footer `status: ok|failed|blocked · reason: …` (+ `needs:`); a one-line summary.
- Hooks: commands that can run as hooks open with "Inputs from the caller" and honour `mode: hook`.
- Browser driving (do_qa) stays at depth 0 on the session model; chores go to `sdd-mechanic`.
- Every artifact-writing command ends by delegating `commit_and_push.md` to `sdd-mechanic`.
- Step 0 convention: read `protected/pre_step_rebase.md` (a no-op on `main`).
- Vocabulary (`domain_vocabulary.md`, sources in `.claude/sdd/config.md`): use "spec", "idea",
  "plan", "QA plan", "worktree", "concrete implementation"/"downstream project" as the repo does.

## 4. Spec lifecycle: "make a new spec here"

- Dirs: `spec_dd/1. next/` (waiting), `2. in progress/`, `3. done/` named
  `yyyy-mm-dd_HH:MM_<title>` (`finish_worktree.md` Step 4). `spec_dd/1. next/roadmap.md` has one row
  per waiting/in-flight dir (`claude_plugins/sdd/resources/roadmap_format.md`).
- Minimal existing mechanism: write `spec_dd/1. next/<slug>/idea.md` (standard in
  `claude_plugins/sdd/resources/idea_standard.md`: what/why/settled, no implementation checklists),
  run `/sdd:roadmap` (sync mode, no argument) to add the row, commit on `main` without pushing.
  Then the owner runs `/sdd:start` (todo list, move to `2. in progress/`, worktree) and
  `/sdd:spec_from_idea`. The command should write ideas only; it must not run spec/plan/implement.
- Bookkeeping on `main` has precedent: `/sdd:roadmap` and `protected/move_spec_to_in_progress.md`
  commit on `main` unpushed. But `commit_and_push.md` Step 1 refuses `main`/`master`.
- Idea format evidence: `[FC] spec_dd/for_freedom_ls/*/idea.md` (see 10) already is a hand-back
  idea. `/sdd:start` warns on unmet dependencies from the roadmap; a bug-fix idea that blocks the
  in-flight integration should say so in its Notes cell (`Before starting:` is the precursor syntax).
- Landing FLS fixes: a small fix needs a branch commit that reaches `origin/main` before the
  concrete can check it out. `claude_plugins/sdd/scripts/land_on_main.sh` (via `finish_worktree.md`
  Steps 0.5/7) is the existing fast-forward-only path, and it assumes a finished spec directory.
  An ad-hoc fix outside a spec has no existing landing path. This is the biggest gap.

## 5. `update_upgrade_notes` and `do_qa`

`update_upgrade_notes.md` (hook of `/sdd:document`, standalone-capable) writes
`<spec-dir>/upgrade_notes.md` after the spec reaches done; the schema is above; prose sections
"Breaking changes" / "Manual steps"; it verifies every name against the tree. It is the contract the
new command parses; no change needed. A failed integration is evidence the notes were incomplete,
so the fix may include correcting that file in `3. done/` (names must survive closure).

`do_qa.md` (17 steps) reads, relative to the cwd/project it runs in:
- the plan: `$ARGUMENTS` or the in-progress spec's plan (`3. frontend_qa.md`; `3b.` for a second plan);
  `§0` of the plan lists seed commands; writes `qa_report.md` and `screenshots/` beside the plan;
- `.claude/fls-dev/config.md`: admin credentials, `Base URL`, `## QA Dev Data` rungs
  (Content reset / DB drop / DB create / Migrate; blank rung = skipped);
- `.claude/ds/scripts/find_available_port.sh`, `kill_runserver.sh`, `.claude/fls-dev/scripts/qa_cleanup.sh`,
  `qa_collect_screenshots.sh`, `compress_screenshots.sh`, `delete_sdd_work_files.sh` (all relative);
- `uv run python manage.py runserver <PORT>` (own port, solo, backgrounded), the
  `debug-branch-badge` id naming the current branch (Step 4), `.sdd-work/qa_scratch.jsonl`;
- `git diff main...HEAD --name-only` for scoping (FULL/ADMIN_ONLY/BACKEND_ONLY), the
  `fls-dev:qa-data-helper` and `fls-dev:qa-bugfixer` agents (factory_boy seeders in the FLS repo),
  and an auto-fix loop (max 3 fixer spawns, TDD, `git revert` on failure).
Rule 3c: never `cd X && cmd` (prompts, collapses a batch). Rule 1: only `mcp__plugin_ds_playwright__*`.

Implications for a concrete project: do_qa is written as "run in the project under test". Run from
FLS, every relative path (config, scripts, runserver, diff scoping, qa-bugfixer's edits and commits)
points at FLS, not the concrete project. Options to weigh in the spec: (a) a thin variant that
takes a project root and substitutes absolute paths; (b) read the concrete's own
`.claude/fls-dev/config.md` for credentials/URL/reset rungs (it has its own admin login and
`danger_content_delete`); (c) the plan's `§0` seed uses FLS demo/`qa_*` commands, which exist in the
concrete only if `freedom_ls.qa_helpers` is installed and are `dev_tooling`-marked. "Adapt the QA
plan" therefore means writing a concrete-specific copy of `3. frontend_qa.md` (artifacts must not
land in `3. done/` of FLS or in the vendored submodule; the mega-qa idea 3 rejects symlinks for
that reason). Concrete's dev server runs on the concrete DB, not an FLS branch DB, so the
`debug-branch-badge` check names the concrete's branch.

## 6. Worktree model

FLS uses a bare-repo layout: worktrees are siblings (`claude_plugins/sdd/skills/git-worktree-setup/SKILL.md`;
the fls-dev one is a thin overlay). Setup/teardown scripts come from `.claude/sdd/config.md`
`## Worktree Scripts`: `.claude/fls-dev/scripts/install_dev.sh` (wrapper, `PLUGINS_ROOT="."`) calls
`claude_plugins/fls-dev/scripts/install_dev.sh`, which runs `git submodule update --init --recursive`,
`rebuild_after_rebase.sh` and `uv run manage.py migrate`; teardown `dev_db_delete.sh` drops the
per-branch DB. So the FLS session has its own branch DB; the concrete project has a different DB,
`.env` and branch. `[FC]` is itself a bare-repo worktree (`First-Class-LMS.git/main/`), so a
configured path should name the worktree to integrate in, and the command should work on a
non-default branch there (update_fls Step 5 rule). The concrete's `install_dev.sh` wrapper passes
`PLUGINS_ROOT="submodules/Freedom-LS"` (`[FC] claude.sh`).

## 7. Conformance and markers

`freedom_ls/contrib/conformance/`: `__init__.py` exports `drop` and six probes
(`test_fls_namespace_reverses`, `test_reference_url_reverses`, `test_configured_backend_instantiates`,
`test_active_theme_resolves`, `test_active_icon_set_resolves`, `test_migration_state_consistent`) plus
`test_admin_registry_survives_installed_apps_override`; note `update_fls.md` 3i lists six explicit
bindings and omits the admin probe (a stale list, a silent-false-green hazard that the new command
should not copy). `_registry.py` holds `drop`. `tests/` holds `fls_internal` tests.
Markers in `pyproject.toml` (lines 87-92): `playwright`, `ci_only`, `fls_internal`, `weasyprint`,
`dev_tooling`. FLS `addopts` deselects only `ci_only`, `weasyprint`, `dev_tooling`; `testpaths` =
`freedom_ls`, `tests`, `claude_plugins/fls-content`. `[FC]` `addopts` additionally deselects
`playwright` and `fls_internal`, `testpaths = ["tests", "apps", "submodules/Freedom-LS/freedom_ls"]`,
and carries four `--deselect` workarounds plus an `--ignore` for FLS tests that fail downstream.
Those are exactly the downstream workarounds the idea wants rolled back once FLS fixes them. A
failing portable test in a concrete project is an FLS bug class (see 10), usually fixed by marking
`fls_internal` or making the test settings-independent.

## 8. Test gate pieces

- `claude_plugins/django-stack/resources/test_tiers.md`: tiers `none`/`targeted`/`full`;
  `.claude/ds/scripts/select_tests.sh <diff args>` (`--working-tree`, `--range`, paths); `full` =
  `uv run pytest -n auto` plus `[tool.test_tiers]` markers; run in background; single test run
  `uv run pytest <file>::<test> -x --no-cov`; re-run `--lf` then the whole tier. Usable inside FLS
  for the FLS fix; `select_tests.sh` is relative to the cwd repo and `pyproject.toml`'s
  `[tool.test_tiers]`, so it would not select tests for the concrete project.
- `claude_plugins/django-stack/commands/rebase_main.md` (and `sdd`'s `protected/pre_step_rebase.md`
  Steps 0-5, with the upstream-change scan) apply to the FLS branch before each push; commits a wip
  commit, fetches, rebases onto `origin/main`, force-pushes the branch.
- For the concrete project the gate stays update_fls's explicit `-m` expression (the concrete's own
  `addopts` already holds it).
- `claude_plugins/sdd/commands/protected/run_test_tier.md` is the project-agnostic fallback runner.

## 9. Commits, cross-repo tooling, hooks

- `claude_plugins/sdd/resources/commit_and_push.md`: refuses `main`/`master`, stages named files
  only, subject `<spec name>: <summary>`, `uv run git commit` (pre-commit lives in the uv env),
  `git push` or `git push -u origin HEAD`, never force. Run by `sdd-mechanic`. In the concrete repo
  the subject convention is `Update FLS: <spec-name>`, so a mechanic would need an explicit command
  and a `git -C <path>` form; the pre-commit hooks of the concrete repo run in the concrete's uv env,
  so `uv run git commit` must run with that project as cwd.
- Cross-repo tool limits (no doc in this repo answers them; `grep` for `additionalDirectories`,
  `add-dir`, "sibling repo" found nothing outside a type file). Based on general Claude Code
  behaviour, unverified here: Read/Edit/Write to a path outside the launch directory prompt unless
  the directory is added (`/add-dir`, `--add-dir`, or `permissions.additionalDirectories`); Bash cwd
  resets between calls, so use absolute paths with `git -C <path>`, `uv --directory <path>` or
  `npm --prefix <path>`. `do_qa` Rule 3c forbids `cd X && …`. `.claude/settings.json` allow-list
  matches by command prefix: `Bash(uv run pytest:*)`, `Bash(uv run git commit:*)`, `Bash(git add:*)`,
  `Bash(git push *)` are allowed, but `uv --directory …`, `npm install`, `uv sync`, `git -C …`
  and `git checkout` are not listed, so each would prompt. The new command must list the
  forms it needs or ask the owner to extend `.claude/settings.json` (the file warns that script
  allow entries are security-sensitive).
- Hooks in `.claude/settings.json`: PreToolUse on Read/Edit/Write/NotebookEdit blocks any
  `.env*` basename except `.env.example` (applies to the concrete's `.env` too, so the command
  cannot read concrete DB URLs); `deny` has `git commit --no-verify`, `git push --force`, `*.pem`,
  `*.key`; SessionStart hard-stops sessions not launched via `./claude.sh` (so the FLS session needs
  `CLAUDE_PLUGINS_LOADED`). No hook gates by repo path. `[FC] CLAUDE.md` says "Do not edit the FLS
  submodule": consistent with the new design, where FLS fixes happen in the FLS worktree and never
  through `submodules/`.

## 10. Existing references to concrete projects

- `claude_plugins/fls-dev/README.md` line 31 lists `concrete/: README, update_fls` and the
  "Commands (9 files)" count; `concrete/README.md` is one sentence: "These commands are specifically
  for concrete implementations of FLS. They typically include FLS as a submodule."
- `tests/test_test_tiers.py` `ALLOWED` frozenset names `update_fls.md` as one of five plugin files
  permitted to spell out `uv run pytest`.
- Docs: `docs/product/configuration-and-extension.md` (conformance, tiers of override),
  `docs/product/deployment.md`, `docs/deployment-security-checklist.md` (check ids named by upgrade
  notes), `docs/app_conventions.md`. No product doc describes how a concrete project is upgraded.
- Specs: `spec_dd/1. next/mega-qa/idea_3_downstream_propagation.md` plans a downstream QA-plan command
  "alongside `/fls-dev:update_fls`" using stub files that resolve into the submodule,
  and `research_downstream_qa_inheritance.md` (§ submodule-advance flow); it overlaps the
  "adapt the QA plan" step. `mega-qa/research_staging_reset_endpoint.md` records that an earlier
  `update_fls.md` wrongly claimed FLS registers no `deploy=True` checks (now corrected by 3g).
  `spec_dd/2. in progress/test-organisation-and-hygene-2-sdd-review-and-boy-scout/research_sdd_standards_hooks.md`
  reads `update_fls.md` as the downstream flow.
- `[FC] spec_dd/for_freedom_ls/` holds 27 hand-back ideas (direct evidence of the pain). Shapes:
  test-portability bugs (`settings-defaults-tests-assert-against-the-downstream-config-package`,
  `icon-intrinsic-size-test-assumes-the-default-icon-set`,
  `sidebar-sections-test-assumes-messaging-is-enabled`,
  `registration-rules-playwright-tests-escape-the-not-installed-gate`,
  `registration-signal-test-leaks-a-mock-site-request`); an integration bug with a downstream
  workaround (`error-page-render-depends-on-base-dir-node-modules`, worked around by the session
  fixture `_warm_icon_cache` in `[FC] conftest.py`, "remove once the loader stops resolving through
  mutable settings"); product bugs (`honeypot-rerenders-its-value`,
  `course-access-url-changes-state-on-get`, `zero-page-form-blocks-course-completion`,
  `profile-form-allows-a-blank-required-name`); and feature requests (`social-login`,
  `phone-number-verification`, `learner-polish-from-mega-qa-2026-10-29`). Each is an `idea.md` titled
  `# Idea: …` with "The bug / Why this is an FLS change", sources by path:line, and an expected fix.
  The `[FC]` tree also has `spec_dd/1. next/social-login-{google,facebook,tiktok}` and
  `phone-number-verification`, i.e. downstream copies of the same asks. The folder is a ready-made
  inbox: the new command can read it, and a fixed item should be deleted/marked there, which edits
  the concrete repo too.
- Pull-in candidates in `[FC]`: `apps/` (e.g. `landing_pages`, lead forms, contact page, admin
  dashboard) and `spec_dd/3. done/` ideas (lead_form, lead_export_and_explore, more-markdown-widgets,
  landing pages). Most are product-specific; "more-markdown-widgets" and lead forms are the kind
  that could be generic. The command needs a rule for what to scan (a diff of `apps/`, `templates/`,
  `config/` against what FLS provides) and must ask per item.
- `[FC]` also holds: `CLAUDE.md` (do not edit submodule; update with `git -C … pull`),
  `claude.sh` (`PLUGINS_ROOT="submodules/Freedom-LS"`), `.claude/{ds,sdd,fls-dev}/config.md`
  (admin login `admin@email.com`, `Base URL: http://127.0.0.1:8000`, same QA Dev Data rungs, sdd hooks
  pointing at `submodules/Freedom-LS/claude_plugins/...`), `tests/test_fls_conformance.py`
  (`from freedom_ls.contrib.conformance import *  # noqa: F403`), and `pyproject.toml`
  `[tool.uv.sources] freedom_ls = { path = "submodules/Freedom-LS", editable = true }`,
  `DJANGO_SETTINGS_MODULE = "config.settings_dev"` (which shadows FLS's own `config/` package, the
  root of the settings-defaults bug).

## Conflicts and risks

1. **Where it lives.** `concrete/README.md` says those commands run inside concrete
   implementations; the new one runs from FLS. Beside `update_fls.md` is wrong by that rule. Choices:
   a new dir (e.g. `commands/` top level, since `do_qa` and `update_*` are FLS-side) or reword the
   README. Moving or deleting `update_fls.md` breaks `tests/test_test_tiers.py` `ALLOWED`, the README
   count, and concrete projects that run it today. Keep `update_fls` as is; it is the right tool when
   there is no local FLS checkout.
2. **Pytest allow-list test.** Any new `claude_plugins/**/*.md` containing the string `uv run pytest`
   fails `test_only_allowlisted_plugin_files_spell_out_a_pytest_invocation` unless added to `ALLOWED`.
   Prefer "run the portable contract test set from `update_fls.md` Step 3i" or the tier file.
3. **Duplicated procedure.** Copying 3a-3j into a second file doubles upkeep (a stale conformance
   binding list already exists). The new command should reference `update_fls.md`'s steps by path.
4. **Landing FLS fixes.** The concrete can only check out commits on FLS `origin/main`. Fixes need a
   branch and a land path; `finish_worktree` assumes a finished spec; `commit_and_push.md` refuses
   `main`. Alternatives: fetch the fix commit into the concrete's submodule from the local FLS
   worktree path (works locally, but the concrete's pushed pointer then breaks for everyone else
   until FLS is pushed). Needs a decision.
5. **Moving target.** The concrete's pointer must advance one done-spec commit at a time, but a
   fixed FLS `main` has newer commits than the spec under test. Retesting spec N after a fix means
   pointing at a post-fix commit, which also carries later specs. The "one spec at a time" claim
   needs a defined retest commit (the fix commit rebased as ancestor-of-next-spec).
6. **QA tooling is project-rooted** (section 5). `do_qa` cannot be pointed at another project
   without path changes, and `qa-bugfixer` commits in the cwd repo. Whether QA for a concrete uses
   FLS's `qa_*` seed commands needs verifying per project.
7. **Permissions.** Cross-directory edits, `git -C`, `uv --directory`, `npm`, `uv sync` are not on
   the allow-list; a long loop will prompt constantly unless `.claude/settings.json` is extended
   (and its comment says doing so is security-relevant). `.env` hooks block reading concrete
   secrets. Concrete `migrate` against a developer's real local database is destructive; the
   command should use the concrete's dev DB only and say so.
8. **Overlap with mega-qa idea 3** (downstream QA propagation command "alongside `update_fls`").
   Not yet specced; the two should share the plan-adaptation mechanism or one should depend on the
   other (check `spec_dd/1. next/roadmap.md`).
9. **State and idempotence.** Resume is derivable from the concrete's pointer plus `git log` of
   done-spec moves; a half-integrated working tree needs the update_fls rollback first.
10. **Worktree identity.** This spec itself is running in an FLS feature worktree, but "fix FLS
    before continuing" and "make a new spec" are `main`-side operations (`1. next/` on `main`, no
    push) while code fixes need a branch. Running from the FLS main worktree is unsupported by
    `pre_step_rebase` and `commit_and_push` (both stop on `main`).
11. **Plugin boundary.** The path list and any project value stay in `.claude/fls-dev/config.local.md`;
    nothing FLS-named goes into `sdd` or `ds`. The command may reference `sdd` helpers by path only.
12. **Concrete rule.** `[FC] CLAUDE.md` forbids editing `submodules/`; the new command must never edit
    the concrete's submodule contents (only its pointer and its own files).

## Reuse candidates

- `claude_plugins/fls-dev/commands/concrete/update_fls.md` Steps 1-5 and Rollback: the per-spec integration body, by reference.
- `claude_plugins/fls-dev/commands/update_upgrade_notes.md` schema: the flag contract, unchanged.
- `claude_plugins/fls-dev/commands/do_qa.md`: QA run, triage and green-lane fixer loop, with path substitution.
- `claude_plugins/fls-dev/agents/qa-bugfixer.md`: TDD fixer, for a small FLS-side fix.
- `claude_plugins/sdd/commands/spec_from_idea.md` and `skills/claude-code-authoring/resources/fanout_recipe.md`: fan-out, resume, status footer, question batching.
- `claude_plugins/sdd/agents/{sdd-worker,sdd-mechanic}.md`: probes (scan downstream for pull-in candidates) and mechanical commits.
- `claude_plugins/sdd/resources/idea_standard.md` and `commands/roadmap.md` (sync mode): the minimal "new spec" path for a bigger bug or a pull-in.
- `claude_plugins/sdd/resources/commit_and_push.md`: FLS-side commits.
- `claude_plugins/sdd/commands/protected/pre_step_rebase.md`, `django-stack/commands/rebase_main.md`, `sdd/scripts/land_on_main.sh`: get FLS fixes onto `origin/main`.
- `claude_plugins/django-stack/resources/test_tiers.md` and `.claude/ds/scripts/select_tests.sh`: FLS-side test gate.
- `freedom_ls/contrib/conformance/` and the markers in `pyproject.toml`: the downstream contract gate and the `fls_internal` fix for non-portable tests.
- `.claude/fls-dev/config.local.md` (gitignored; template `claude_plugins/fls-dev/templates/config.local.md`): home of the machine-local concrete-project path list.
- `[FC] spec_dd/for_freedom_ls/*/idea.md`: ready-made inbox of hand-back ideas already in idea format.

status: ok · reason: codebase mapped across all ten items; unverified cross-repo permission behaviour flagged
