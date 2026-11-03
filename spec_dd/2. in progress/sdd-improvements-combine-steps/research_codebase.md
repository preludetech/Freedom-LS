# Research: codebase (sdd-improvements-combine-steps)

Question: what in the existing codebase does this work touch, reuse or conflict with?
Scope: `claude_plugins/sdd` (generic), its config `.claude/sdd/config.md`, and the hooks it calls in
`claude_plugins/django-stack` and `claude_plugins/fls-dev`. All paths are relative to the project root.

## Summary of the findings that matter most

- No command invokes another command today. Chaining is done by "read this helper file and follow
  its steps" (only for `protected/*.md` helpers, and only inline at depth 0), or by delegating a
  helper file to `sdd:sdd-mechanic`. The one cross-plugin call is the `Skill` tool (`/sdd:document`
  calling documentation hooks). `/sdd:register_design`, `/sdd:spec_from_idea` and
  `/sdd:do_qa` are slash commands with their own frontmatter (`allowed-tools`) and are not
  `protected/` helpers; a chain would have to read-and-follow them inline or call them with `Skill`.
- `/sdd:start` today runs in the ORIGINAL checkout (usually `main`) and never enters the new
  worktree. Everything after it (register_design, spec_from_idea, ...) needs the cwd to be the new
  worktree (the pre-step rebase, `register_design` Step 1 and `commit_and_push.md` all key off
  `git branch --show-current`). A chain must solve "how does the session move into the worktree".
- `isolation: worktree` appears once in the plugin, as a bare frontmatter-field mention in
  `claude_plugins/sdd/skills/claude-code-authoring/resources/subagents.md:36`. No command or
  agent uses it. `EnterWorktree` / `ExitWorktree` appear nowhere under `claude_plugins/`.
- Per-worktree dev resources are per-branch Postgres databases (`db_<branch>`,
  `test_db_<branch>`), created by `install_dev.sh` -> `rebuild_after_rebase.sh` -> `dev_db_init.sh`.
  A short-lived coding worktree on its own branch name gets its own databases for free (and needs
  its own teardown); on the same branch name it would collide.
- Generic-plugin rule (`CLAUDE.md` "Plugins"): anything FLS-specific (Postgres port 6543, `fls_dev`,
  `npm`, `uv`, `tailwind`) must stay out of `claude_plugins/sdd`; it can only come in through
  `.claude/sdd/config.md` keys. Parallel-worktree setup/teardown therefore must be driven by the
  existing `## Worktree Scripts` keys (or a new key), never hard-coded in `sdd`.

## 1. Current step-by-step of each command

### `/sdd:start` (`claude_plugins/sdd/commands/start.md`)
Thin orchestrator, `allowed-tools: Read, Write, Glob, Bash, Skill, Agent`. Note: no `AskUserQuestion`
in frontmatter even though Steps 0 and 1 use it.
- Step 0: roadmap check (`spec_dd/1. next/roadmap.md`). Precursor check (row Notes starts
  `Before starting:` or directory needs a cut) -> `AskUserQuestion` "Stop and do it on main first
  (Recommended)" / "Start anyway". Unmet dependency (no `spec_dd/3. done/*_<name>`) ->
  `AskUserQuestion` start anyway vs stop (a warning, never a block). No roadmap/row: silent.
- Step 1: delegate to `sdd:sdd-mechanic` to run `protected/setup_todo_list.md`; note spec dir. On
  `status: blocked` ask user via `AskUserQuestion`, re-spawn.
- Step 2: delegate to mechanic -> `protected/move_spec_to_in_progress.md`. Moves dir into
  `spec_dd/2. in progress/`, edits roadmap row to `in progress`, commits on the CURRENT branch (no
  push; usually `main`) with subject `<spec>: start the spec`; requires clean tree.
- Step 3: delegate to mechanic -> `protected/start_worktree.md` (after Step 2's commit so the branch
  contains the move).
- Step 4: prints todo.md path, worktree path, and tells the user to `cd` into the worktree, open
  `todo.md` and run `/sdd:spec_from_idea`. THIS is the manual hand-off the idea wants removed.
- Stop contract: no return line of its own; any helper `status: blocked` is handled by asking and
  re-spawning.

### `protected/setup_todo_list.md`
Locates spec/idea dir (caller input, else branch name, else `AskUserQuestion`-style "ask the caller"
- a mechanic cannot ask, so it returns `blocked`). If `todo.md` exists: asks caller overwrite or
leave. Pre-ticks items from artifacts found (`1. spec.md`, `2. plan.md`, `qa_report.md`). Reads
`## QA Hooks` -> `QA command` to word the QA item: `(cmd) Run /<QA command> to execute the QA plan`
or `(user) Execute the QA plan by hand`. Writes the five-section checklist (1 Spec, 2 Plan,
3 Implementation and QA, 4 Documentation and pull request, 5 Cleanup). Item markers `(user)` /
`(cmd)`. Does not commit (Step 2 of start commits it). This repo's own todo
(`spec_dd/2. in progress/sdd-improvements-combine-steps/todo.md`) shows the layout.

### `protected/move_spec_to_in_progress.md`
See start Step 2. Stops `blocked` if ambiguous dir or tree cannot be made clean. Does not run pytest.

### `protected/start_worktree.md`
- Step 1: preconditions (spec dir already in `2. in progress/`, tree clean) else `blocked`. Worktree
  name = spec directory folder name. Does not read the spec.
- Step 2: `cd ..` to the BARE REPO PARENT, `git worktree add <spec-folder-name>` (creates a branch of
  the same name; never inside an existing worktree).
- Step 3: reads `.claude/sdd/config.md` `## Worktree Scripts` -> `Setup script` (FLS:
  `.claude/fls-dev/scripts/install_dev.sh`), runs it from inside the new worktree; blank = skip.
- Step 4: prints the worktree path.
Does not cd the session into the worktree (Bash cwd resets between calls anyway).

### `/sdd:register_design` (`commands/register_design.md`)
`allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, Skill, ToolSearch` (no `AskUserQuestion`).
Depth 0. Never runs the pre-step rebase. Steps: 1 resolve inputs (spec-dir from current branch name
when on a feature branch, else user names it; design input = handoff prompt text or file path or bare
claude.ai/design link; notes); 2 sync via `ToolSearch select:DesignSync` + `get_project`/`get_file`/
`list_files` (never WebFetch/browser); write `design_source/`; 3 write `design.md` (fixed "How to
read it"/"How to treat it" text, coverage table); 4 mechanic runs `design_screenshots.sh "<spec-dir>"`
(non-zero exit goes in summary, commit still happens); 5 edit consumers' `idea.md`/`1. spec.md`
"Resources" bullets and roadmap lines; 6 mechanic commits with `commit_and_push.md`, `<summary>`
`register the Claude Design design` (on `main`: commit only, no push, subject
`<spec-dir name>: register the Claude Design design`). Stop conditions: no branch match; user names a
different dir; input is not a prompt/link; `/design-login` needed (asks user to run it - an
interactive exit, retried once). It explicitly asks nothing about what the design draws and does not
ask for notes. Return: prints design.md path, read/not read, counts, consumer files. Does NOT tick
`todo.md` (no todo item exists for it).

### `/sdd:spec_from_idea` (`commands/spec_from_idea.md`)
`allowed-tools` includes `AskUserQuestion`, `Agent`, `WebFetch`, `WebSearch`. Depth 0. Steps:
- 0 pre-step rebase (inline).
- 1 spawn six `sdd:sdd-worker` research workers in parallel/background (`codebase`, `best_practices`,
  `reference_implementations`, `prior_art`, `ux_patterns`, `known_complaints`), each writing
  `research_<topic>.md` beside the idea; resume-skip when `status: ok` or no footer.
- 2 question batch while workers run (`AskUserQuestion`, up to four per call; front-loaded, then a
  follow-up as each file lands). Test: answer changes the spec, nothing on disk/research answers it,
  no obvious default.
- 3 gate (all research files present) then synthesis at depth 0 -> `1. spec.md`, following
  `writing_standard.md`, `domain_vocabulary.md`, `productivity:unslop`.
- 4 mechanic commits `write the spec` (spec + research files, pushes).
- 5 review wave (via `spec_review.md` Step 1: five `sdd-worker`s from `spec_review_dimensions.md`),
  6 apply clear fixes, 7 end-of-run question batch (`AskUserQuestion`; unanswered -> `## Open
  questions` in assumed-default shape), 8 clean up own scratch by name, 9 tick `Run
  /sdd:spec_from_idea` via `update_todo.md`, 10 mechanic commits `review the spec`.
- Return: printed summary (one line per applied fix, line/word counts). No `status:` line. Stops
  (no spec written) if a research topic still fails after retry.

### `/sdd:plan_from_spec` (`commands/plan_from_spec.md`)
`allowed-tools` includes `AskUserQuestion`, `Agent`, `ToolSearch`. Input `<spec path> [suffix]`.
- 0 pre-step rebase. 1 read spec; spawn skills/MCP scan (`.sdd-work/plan_skill_scan.md`) in background;
  read `design.md` if named; ask contradictions the code can't resolve (batched, up to four, while
  carrying on). 2 investigate code. 3 write plan as vertical slices (design section + token mapping when
  `design.md` applies; each designed slice has `**Design states:** <id>, ...`). 4 fold scan in.
  5 write QA file `3. frontend_qa.md` if frontend changes (port is chosen at run time; never named).
  6 plan review fan-out: one `sdd-worker` per row of `plan_review_dimensions.md` + one per
  `## Plan Review Hooks` bullet (FLS: Structure, FLS threats); clear fixes edited in; judgement
  calls become `> **... concern:**` callouts put to the user in one batch ("When a question comes
  late"), unanswered -> `> **Assumed default:** ...`. 7 delete scratch by name. 8 tick the plan item and
  `add_after:` any spec downstream item not covered by a Documentation Hook (as `(user)` items after the
  `/sdd:document` item). 9 mechanic commits `write the implementation plan` (plan, QA file, todo).
- Return: short printed summary. No `status:` line.

### `/sdd:implement_plan` (`commands/implement_plan.md`) - detail in section 4.

### `/sdd:do_qa` (`commands/do_qa.md`) - detail in section 5.

### `/sdd:document` (`commands/document.md`)
Depth 0, `allowed-tools: Read, Glob, Bash, Skill, Agent` (no AskUserQuestion). 0 pre-step rebase;
1 resolve spec-dir/todo-path; 2 for each `## Documentation Hooks` bullet (`<label>: <skill>`, FLS:
`ds:app_map`, `fls-dev:update_upgrade_notes`, `fls-dev:update_product_docs`,
`fls-dev:update_claude_plugin_fls_content`) invoke the skill with the `Skill` tool, args
`spec-dir=... todo-path=... mode: hook`. A hook either commits itself, ends with `changed: <paths>`
(document delegates a mechanic commit with `<summary>` = label), returns `status: needs-approval`
(commit nothing, keep for report) or `failed`. A failed/needs-approval hook does not stop the run.
3 mechanic ticks `Run /sdd:document` and commits `run the documentation hooks`. 4 report one line per
hook. `needs-approval` is the only soft user-input exit; the user decides about uncommitted files.

### `/sdd:make_pr_quickly` (`commands/make_pr_quickly.md`)
`allowed-tools: Bash` only. One Bash call: push if on a branch (failure ignored) then
`gh pr create --head <b> --base main --title <b> --body ""`, falling back to `gh pr view` for the URL.
Explicitly never rebases, tests, commits, ticks `todo.md`, spawns subagents, invokes other
commands/skills, or asks the user. Returns one line: the PR URL. (Note: `commands/README.md` Step 6 says
`gh pr create --fill`; the file uses `--title <branch> --body ""`. A doc drift, not material.) It does
not tick `todo.md`; the `Run /sdd:make_pr_quickly` item is ticked by hand/never by the command.

### `/sdd:finish_worktree` (`commands/finish_worktree.md`)
Depth 0, `allowed-tools: Bash, Read, Glob, Skill, Agent`. Refuses on main/master. 0 pre-step rebase at
`<tier>: full`; 0.5 `land_on_main.sh sync`; 1 full tier unless Step 0 already ran it; 2 Teardown script
from `## Worktree Scripts` (FLS: `.claude/fls-dev/scripts/dev_db_delete.sh`, drops `db_<branch>`,
`test_db_<branch>`, `test_db_<branch>_gw*`); 3 tick `Run /sdd:finish_worktree`; 4 move spec dir to
`spec_dd/3. done/yyyy-mm-dd_HH:MM_{title}`; 4.5 `update_roadmap.md` remove (retire cut-effort parent);
5 `update-claude-project-settings` skill; 6 mechanic commits `close out the worktree`; 7 PR guard
(`gh pr view`; CHANGES_REQUESTED -> blocked) then `land_on_main.sh land` (exit 7 -> one re-rebase and
retry; exits 3/6/8 -> blocked, re-runnable); 8 `git status --porcelain` must be empty.
Return: `status: ok|failed|blocked · landed: yes|nothing|no · main: <sha> · reason: <short>`.
No user questions at all.

## 2. Every `AskUserQuestion` use and every blocked/paused exit

Files with `AskUserQuestion` in commands (grep count): `start.md` 3, `roadmap.md` 6,
`commit_quickly.md` 1, `plan_from_spec.md` 5, `implement_plan.md` 2, `spec_review.md` 2,
`spec_from_idea.md` 7 (plus a reference in `README.md` 2, fls-dev `update_claude_plugin_fls_content`
1, `concrete/update_fls` 1, `update_concrete_projects` 3). `register_design`, `document`,
`finish_worktree`, `make_pr_quickly`, `do_qa` do NOT list it in frontmatter.

| Where | What it asks | When | Default? |
|---|---|---|---|
| `start.md` Step 0 precursor | Stop and do it on main first (Recommended) vs Start anyway | Before anything, from roadmap row | Recommended option marked; stop |
| `start.md` Step 0 dependencies | Start anyway or stop, per unmet dependency | Before anything | None stated; warning only |
| `start.md` Steps 1-3 | Answers for a mechanic's `blocked` (ambiguous spec dir; existing `todo.md` overwrite?) | On `blocked` | None |
| `spec_from_idea.md` Step 2 | Open idea questions (contradictions, ambiguity, edge cases, better implementation), batched <=4, while workers run; follow-ups as research lands | Right after Step 1 spawn | Each carries a recommended answer + a why clause |
| `spec_from_idea.md` Step 7 (via `spec_review.md` Step 3) | Judgement-call review findings, one batch at end | After review wave | Recommended option first; unanswered -> `## Open questions` assumed default |
| `plan_from_spec.md` Step 1 | Spec contradictions code can't resolve, batched <=4, run alongside Step 2 | Early | none; spec is fixed with answers |
| `plan_from_spec.md` Step 6 | Review callouts as one batch ("When a question comes late") | End of plan review | Recommended first; unanswered -> `> **Assumed default:**` |
| `implement_plan.md` Step 2 | Gather `needs` of a `blocked` batch | On batch `blocked` | None |
| `implement_plan.md` "When to Stop and Ask" | Test fails and cause not obvious; missing dependency | Mid-run | None - stops |
| `do_qa.md` Inputs | "If more than one candidate exists, ask which to use" (plain prose, no tool listed) | Before doing anything | None |
| `roadmap.md` (6) / `commit_quickly.md` (1) | Out of scope for this chain | | |
| `setup_todo_list.md` Step 2 | overwrite existing todo? (asked "of the caller"; mechanic cannot ask) | If `todo.md` exists | Do not silently overwrite |
| `register_design.md` | Only `/design-login` request to the user, retry once | When DesignSync unauthorised | Proceeds "not yet read" if still unreadable |

Blocked/paused/failed exits to know:
- `pre_step_rebase.md`: `status: paused` when `todo.md` has an unticked item naming
  `upstream_change_review.md` (checked at Step 0, and set at Step 5 when review says `direction:
  changed`; adds a `(user)` item and commits `upstream_change_review.md`). Also `blocked` (merge
  commit in branch, conflict needing a human, another worktree mid-merge), `failed` (conflicting
  `PLUGINS_ROOT`, scan error, push rejected, front-end check failure). A caller continues only on `ok`.
  This is the most important hard stop for a chain: any chained command that runs a pre-step rebase
  can halt the whole chain on `paused`.
- `start_worktree.md` / `move_spec_to_in_progress.md`: `blocked` on dirty tree or ambiguous dir.
- `setup_todo_list.md`: `blocked` (ambiguous dir, existing `todo.md`).
- `do_qa.md`: `status: blocked · needs: <key>` when `Playwright MCP`, `Port finder`, `Dev server start`
  or `Dev server stop` is blank; project-root-mode `blocked` when `## QA Login` is absent.
- `finish_worktree.md`: `blocked` (main worktree dirty, exit 3/6/8, PR changes requested, origin keeps moving),
  `failed` (full run failed, tree not clean).
- `implement_plan.md`: a batch returns `failed` (retry <=2, reset partial work) / `blocked`
  (`AskUserQuestion`).
- `document.md`: `needs-approval` per hook (does not stop).
- `sdd-worker` / `sdd-mechanic` / `qa-bugfixer`: all return `status: ok|failed|blocked` (+ `needs`).

## 3. How commands call each other; what `claude-code-authoring` says

Mechanisms in use today:
1. **Read-and-follow a helper file inline at depth 0** (`Read claude_plugins/sdd/commands/protected/pre_step_rebase.md and follow its steps`): `pre_step_rebase.md`, `run_test_tier.md`, hook files like
   `rebase_main.md`, `frontend_check.md`, `design_check.md`. Inline means the caller's model and
   tool grants apply; the helper's own frontmatter is inert.
2. **Delegate a helper file to `sdd:sdd-mechanic`** (Haiku, tools `Bash, Read, Edit, Write, Glob,
   Skill`): setup_todo_list, move_spec_to_in_progress, start_worktree, update_todo, update_roadmap,
   commit_and_push, run_test_tier. The mechanic follows the file literally and cannot ask.
3. **`Skill` tool** for hooks owned by another plugin (`/sdd:document` -> `ds:app_map`, `fls-dev:*`),
   args `spec-dir=... todo-path=... mode: hook`. Each hook keeps its own plugin root and grants.
   `Skill(sdd:*)` is permission-allowed in `.claude/settings.json`.
4. **`Skill` with `project-root:`/`diff-range:` args** for `do_qa` when "a calling command" drives it
   (project-root mode in `do_qa.md`): the only existing example of one SDD command being invoked
   from another, for a concrete project from `fls-dev:update_concrete_projects`. So `do_qa` already
   supports being called as a skill with args; the "Inputs from the caller" idiom exists.
5. **`mode: hook`** convention (claude-code-authoring SKILL.md "Hook mode"): a command read and
   followed inline at depth 0 skips its own pre-step rebase and todo tick and keeps its commit step;
   every command that can be a hook opens with an "Inputs from the caller" line naming `<spec-dir>`,
   `<todo-path>`, `mode: hook`. NOTE: check which commands actually have that line - `document.md`
   references it via `pre_step_rebase.md`'s "Inputs from the caller" line; `spec_from_idea`,
   `plan_from_spec`, `implement_plan`, `do_qa` and `register_design` do NOT open with such a line
   and have no `mode: hook` branch. A chain must either add it to them or read them inline with explicit
   overrides.
6. No command contains the text "invoke /sdd:..." as a slash command. The `claude-code-authoring`
   skill says (SKILL.md "Subagent limits", resources/subagents.md): slash commands cannot be typed
   from a subagent; prefer skills or "read-and-follow this helper file".

What `claude-code-authoring` says (`claude_plugins/sdd/skills/claude-code-authoring/SKILL.md` + resources):
- **Depth 0 only fan-out; no nesting.** `Agent` is not exposed at depth 1; "Depth is capped at 1:
  main session -> subagent" (subagents.md). A subagent cannot spawn another. So a "per-slice coding
  subagent" cannot itself fan out sub-subagents, and a "chain" run inside a subagent loses ALL
  fan-out and `AskUserQuestion`. Therefore the whole chained flow (`start` -> `register_design` ->
  `spec_from_idea`) must itself run at depth 0 in the main session; only leaf work is subagents.
- **`AskUserQuestion` is orchestrator-only** (interactive_cli.md; SKILL.md). Subagents fail fast with
  `status: blocked` + `needs`.
- **File-based hand-off.** Fixed-name artifacts (`1. spec.md`, `2. plan.md`, `todo.md`,
  `.sdd-work/*.md`) with a trailing `status:` footer; one `Write` per file; resume = skip units
  whose file ends `status: ok`. `Agent` `prompt` is the only input channel (spawn-time only).
- **Model tiering.** Per-agent `model:` frontmatter is the reliable knob: mechanical -> `sdd-mechanic`
  (haiku, effort low); fan-out -> `sdd-worker` (sonnet; tools Read/Glob/Grep/WebFetch/WebSearch/Write
  only); interactive authoring at depth 0 -> session model. Resolution order:
  `CLAUDE_CODE_SUBAGENT_MODEL` > per-spawn `model` param (enum `sonnet|opus|haiku` only) > frontmatter
  > parent. Inline-followed files keep the caller's model. `implement_plan` already passes
  `model: "sonnet"` per spawn to `subagent_type: "general-purpose"` agents. `qa-data-helper` is Opus;
  `qa-bugfixer` Sonnet.
- `isolation: worktree` is listed as a valid agent-frontmatter field in `subagents.md:36` and nowhere
  else. It is NOT documented in the skill's SKILL.md frontmatter bullet (which lists only `name`,
  `description`, `tools`, `model`, `skills`, `effort`, `disallowedTools`, `memory`, `color`). No
  command passes `isolation` on an `Agent` call; `EnterWorktree`/`ExitWorktree` are not referenced in
  `claude_plugins/` at all (grep: no hits). Two available paths for parallel worktrees therefore
  exist but are unused: the `Agent` tool's `isolation: "worktree"` per-spawn/frontmatter option
  (Claude Code creates a temp git worktree for the subagent, auto-cleaned if no changes) and the
  existing `git worktree add` via the Setup script. `isolation: worktree` would create the worktree
  without running the project's Setup script, so no per-branch database, venv sync, `npm i` or
  tailwind build would happen in it - a spec must decide how a coding subagent's tests run there.
- Authoring tip to honour: the skill says commands must stay under depth 0 for any `Agent` spawn,
  and `sdd-worker` has no Bash, so coding agents have to be `general-purpose`
  (as `implement_plan.md` Step 2 says).

## 4. `/sdd:implement_plan` as it works now

(`claude_plugins/sdd/commands/implement_plan.md`; `allowed-tools: Read, Glob, Grep, Write, Edit, Bash,
Skill, Agent, ToolSearch, AskUserQuestion`.)
- Input `[suffix]` (`2b`) -> plan `<suffix>. plan.md`, QA `3<letters>. frontend_qa.md`; `<id>` is
  `<suffix>.N` or `N`.
- Step 0 pre-step rebase (inline; can `pause`/`block`).
- Step 1 read plan; check missing/ambiguous steps; proceed regardless (a batch that cannot proceed
  returns `blocked`).
- Step 2 batching: **one batch per vertical slice, in plan order**; "a small shared-groundwork step the
  plan places before a slice goes into that slice's batch"; if the plan is not slices, thinnest
  batches that deliver working tested behaviour. Marker = git commit subject `[batch <id>] <summary>`.
  Resume scan from `git log --format=%s origin/main..HEAD` with the anchored patterns
  `^\[batch 2b\.[0-9]+\]` (suffix) / `^\[batch [0-9]+\]` (no suffix). `design fix` and `review fix`
  commits count as their batch's commit.
- One sub-agent per remaining batch: `subagent_type: "general-purpose"`, per-spawn `model: "sonnet"`
  (user can override to opus). **Sequential, not parallel**: nothing in the file spawns two batches at
  once; each batch must finish (status ok + commit exists + Design check + Batch review, tier pass)
  before the next batch is spawned ("The batch's tier must pass before moving to the next batch").
  This is "plan is ordered by dependency, each slice builds only on previous ones"
  (plan_from_spec Step 3), so there is no machine-readable dependency graph.
- Each batch sub-agent: (1) implement steps exactly as written, (2) run plan verifications, (3) read
  `protected/run_test_tier.md` and follow with `tier: targeted`, `diff: --working-tree` (resolves to
  `.claude/ds/scripts/select_tests.sh --working-tree`, runs printed `uv run pytest -n auto ...` with
  `run_in_background`; one tier at a time per worktree per `test_tiers.md`), a failure follows
  "When a targeted run or full run fails" (fix test first, re-run `--lf`, then the whole tier);
  (4) commits itself with `uv run git commit` as `[batch <id>] <summary>` (the one place a worker
  commits its own work, for atomic resume). Returns `status: ok|failed|blocked · reason:`.
  The brief also forbids planning references in comments (`§`, `spec 6`, `this slice`, `batch 3`,
  `spec_dd/` paths), names the `Comment standard` + `Test standard` files from `## Review Hooks`, and
  - for designed slices - passes design screenshot and plan paths (paths, never contents).
- Status handling: `ok` -> verify commit, Design check (only when slice has `**Design states:**`,
  via `Design check` hook `design_check.md`: screenshots states, up to two `design fix` batches, surviving misses go to
  `todo.md` via Step 4), then Batch review (mechanic diff+grep, sonnet worker, up to two `review fix`
  batches). `failed` -> reset partial uncommitted work, retry <=2 with prior error. `blocked` ->
  `AskUserQuestion`, re-spawn with answers.
- Step 3 final verification: mechanic runs `full` tier (`uv run pytest -n auto`), summary per batch +
  success criteria; unmet criterion -> fix sub-agent (general-purpose/sonnet) then re-run full;
  final commit via mechanic. "DO NOT run the frontend_qa plan during implementation" (Step 2
  trailing section) - a rule that must be changed for "run QA as soon as the plan is implemented".
- Step 4: mechanic ticks `Run /sdd:implement_plan...` and adds one `user` `Decide what to do about
  design miss` item per surviving design miss. Branch safety: never on main/master.
- Return: a printed summary only; no `status:` line.
- Plan format (real example `spec_dd/3. done/2026-11-03_05:13_deadlines-8-per-placement-dates/2. plan.md`):
  header (Source, TDD note), `## Skills to use`, `## What exists and is reused`, then
  `## Slice N: <behaviour>` blocks each with `**Behaviour.**`, `> **Assumed default:**` callouts and
  `### <layer>` sub-sections (Schema, Model and migration, Loader, Resolver, Admin, Tests).
  Slices are numbered, ordered by value and dependency ("Each slice builds only on slices before
  it"). There is NO explicit dependency notation (no `Depends on:`/`Builds on:` fields) - a grep of the
  plan finds none. Designed slices add `**Design states:** <id>, <id>`. The plan "MUST NOT mention the QA file or say it
  should be run" (plan_from_spec Step 5/6), "must not create documentation". Therefore parallel
  coding needs a new, explicit way to say which slices are independent (e.g. a `**Depends on:**`
  line and a file-disjointness rule) and the plan template/reviewer would have to be changed
  (`plan_review_dimensions.md` would also need a dimension; not read in full here).
- Overlap risks for parallel slices: shared migration chains (two slices adding migrations to the
  same app produce conflicting leaf nodes - `rebase_main.md` Step 6 treats renumbering as a manual
  rule, never `makemigrations --merge`), shared test files, `uv.lock`/`package-lock.json`, and
  `todo.md`/`.sdd-work` (todo is not written while batches run by design).

## 5. How `/sdd:do_qa` starts today

(`commands/do_qa.md`; `allowed-tools: ... Agent, mcp__playwright__*, mcp__plugin_ds_playwright__*`;
no `AskUserQuestion`.)
- Input: `$ARGUMENTS` = path to the test plan file or spec dir; if none, find the plan in the
  in-progress spec dir for the branch; if >1 candidate, ask which (plain-prose ask). Optional skill
  args `project-root: <abs path>` and `diff-range: <a>..<b>` (project-root mode, for another repo's
  server; skips Step 0, 13, 15, 17 etc.). So it already runs as a callable unit, but `todo.md`,
  `qa_report.md`, `screenshots/` are written beside the plan.
- Reads `## QA Hooks` (QA command, Playwright MCP, Screenshot directory, Port finder, Dev server
  start/stop, Branch badge, Diff scoping, Data helper guide, Screenshot prep, Layout regions), `## QA Login`,
  `## QA Dev Data` once. Blank `Playwright MCP`, `Port finder`, `Dev server start/stop` -> `status:
  blocked · needs: <key>`.
- Step 0 pre-step rebase; 1 `qa_cleanup.sh "<spec-dir>"` (deletes previous `qa_report.md` and
  `screenshots/`); 2 diff scoping gate (`git diff main...HEAD --name-only`, class FULL / ADMIN_ONLY /
  BACKEND_ONLY via `Diff scoping` file); 3 free port from `Port finder`
  (`.claude/ds/scripts/find_available_port.sh`) + backgrounded `Dev server start` (solo Bash);
  4 check branch badge `debug-branch-badge` names the current branch (collision -> back to step 3);
  5 login with `## QA Login` (admin email/password from config); 6 smoke gate (home + primary
  changed page; failure aborts matrix); 7-9 desktop/mobile/tablet, browser driving by hand at
  depth 0 ("MUST NOT be delegated to a subagent"); layout probe (`qa_layout_probe.js`), visual review,
  design comparison; 10 `qa_collect_screenshots.sh`; 11 mechanic compress; 12 group failures into
  distinct bugs, `sdd-worker` writes `qa_report.md`; 13 triage: green lane -> `sdd:qa-bugfixer`
  (max 1 attempt per bug, 3 spawns per run, `git revert --no-edit` on failed re-verify),
  red lane -> UNRESOLVED; full run after any fix; 14 kill dev server (`kill_runserver.sh <PORT>`);
  15 mechanic updates `todo.md`: tick, plus `add:` items - the closed list of five categories
  (UNRESOLVED bugs, impossible-to-set-up data, smoke gate failure, product decision, full-run fail),
  where the "Decide" items come from: `Decide what to do about QA bug: <title> (TDD: failing test
  first, then fix)`; 16 delete scratch by name (`delete_sdd_work_files.sh`); 17 mechanic commits
  `run the frontend QA pass` (report, screenshots, todo).
- No `AskUserQuestion`; fully autonomous except the candidate-pick prompt. Safe to chain after
  implement_plan (the todo QA item is `(cmd) Run /sdd:do_qa ...`).
- Parallel safety already designed in: picks its own free port ("It is CRITICAL that you do not use
  existing processes"), checks the branch badge; but browser driving is single-threaded at
  depth 0 (Rule 3a/3e: Agent spawns and Dev-server start are solo calls). The cannot-be-parallel
  parts are the Playwright MCP session and the single dev DB (`Rule 2`: data helpers).
  Things that CAN run alongside QA: nothing it owns; documentation hooks (`/sdd:document`) could
  start in a different step but write to shared docs/todo.
- QA is invoked as `sdd:do_qa` (the `QA command` key); `todo.md` item text is generated from that key
  (so a chained `implement_plan` should read the key rather than hard-code `/sdd:do_qa`, to stay
  generic; a blank key means "run QA plan by hand" and chaining must skip).

## 6. Worktree conventions and what parallel coding would need

- Layout (sdd skill `git-worktree-setup`): bare repository parent; each worktree is a sibling dir of
  the same name as the branch; `.git` is a file. `start_worktree.md` runs `cd .. && git worktree add
  <spec-folder-name>`. The FLS overlay skill (`claude_plugins/fls-dev/skills/git-worktree-setup/SKILL.md`)
  adds only the per-worktree setup and per-branch DB convention. This repo's own cwd is already a worktree
  (`.../freedom-ls-worktrees/sdd-improvements-combine-steps`, git "Current branch: sdd-improvements-combine-steps").
- `.claude/sdd/config.md` `## Worktree Scripts`: Setup `.claude/fls-dev/scripts/install_dev.sh`,
  Teardown `.claude/fls-dev/scripts/dev_db_delete.sh`. Both are thin wrappers (set `PLUGINS_ROOT=.`)
  over `claude_plugins/fls-dev/scripts/*`.
- `install_dev.sh`: `git submodule update --init --recursive`; `rebuild_after_rebase.sh` (`uv sync`;
  `npm i`; `npm run tailwind_build`; `dev_db_init.sh`); then `uv run manage.py migrate`.
  So a fresh worktree costs a full `.venv` sync (a per-worktree `.venv`, gitignored), a per-worktree
  `node_modules/` (gitignored) and a Tailwind build, plus DB creation and migrate. Minutes, not seconds.
- `dev_db_init.sh`: Postgres at 127.0.0.1:6543 (docker container from `dev_db/`), role `fls_dev`
  (created if missing, 15 min idle-in-transaction timeout); creates `db_<sanitized-branch>` (lowercase,
  non-alnum -> `_`, cut at 50 chars) and `test_db_<...>` owned by `fls_dev`, stamps the dev DB with a
  COMMENT recording repo + worktree path. xdist workers use `test_db_<branch>_gw<N>`; `dev_db_delete.sh`
  drops dev, test and `_gw*` DBs for the current branch (via `DROP DATABASE ... WITH (FORCE)`). It does
  nothing on a detached HEAD (no branch). `config/settings_dev.py` derives DB name from the git branch
  (`branch_to_db_name`), sets `TEST: {NAME: test_<db>}`, and a per-branch `SESSION_COOKIE_NAME`.
  `uv run python -m dev_db.stale_dbs` lists databases whose worktree is gone (cleanup safety net).
  Consequences for short-lived sibling worktrees:
  - They need a DISTINCT branch name (git forbids the same branch checked out twice, and DB name derives
    from the branch). Any temp-branch name must differ within the first 50 sanitised chars, since the db
    name is cut at 50 characters: a feature branch `sdd-improvements-combine-steps-slice-1` would collapse
    with a long parent name if the prefix is >=50 chars. Name length is a real hazard because spec
    folder names are already long.
  - Each needs its own dev + test database (can't share: the same migrations are in progress and tests
    would clash on a shared `test_db_*`), created by `dev_db_init.sh` and torn down by
    `dev_db_delete.sh` run from inside that worktree. Run time dominated by `migrate` on a fresh DB.
  - Each needs its own `uv sync` venv and `npm i` unless the setup is made cheaper (no shared venv option
    exists in the scripts; `UV_PROJECT_ENVIRONMENT` or a symlinked `node_modules` would be a design
    decision for the spec, and project-specific so it would belong in the FLS setup script, not `sdd`).
  - Ports: only `runserver`/QA use ports, picked free at run time by `find_available_port.sh`; coding
    subagents running pytest need no port, except pytest-playwright tests, which start their own server
    (not read here). The Postgres port 6543 is shared and fine.
  - `claude_plugins/fls-dev/commands/protected/...` rebase hooks and `.claude/ds/scripts/select_tests.sh` are
    relative to the worktree root, so they work per worktree.
- Teardown for a short-lived worktree: `git worktree remove` (not wrapped in any script; no
  permission entry for `git worktree` in `.claude/settings.json` - see section 9), and `dev_db_delete.sh`
  from inside it BEFORE removing it (the script uses the branch name of cwd), then delete the temp
  branch. `finish_worktree` only tears down the main feature worktree's DB and says removing the worktree and
  branch is a `(user)` item. A "short-lived worktrees" feature needs its own teardown on every exit path
  (including a failed/aborted subagent), or `stale_dbs` will list leftovers.
- Merging back: nothing in sdd merges a sibling branch into the feature branch. `finish_worktree` and
  `land_on_main.sh` are the only merge-ish scripts, and they land on main by fast-forward only;
  `rebase_main.md` refuses merge commits in the branch (Step 4: `git log --merges` non-empty =>
  `blocked`), so integrating parallel slice branches must be by cherry-pick or rebase-then-fast-forward,
  never `git merge` with a merge commit. The `[batch <id>]` commit marker also has to survive the
  integration (resume scan matches on commit subject on `origin/main..HEAD`).
- `.sdd-work/` (gitignored at repo root, `.gitignore:67`) is per-worktree, so a sibling worktree has its own
  `.sdd-work/`, not the parent's: files written there by a sibling subagent are not visible to the
  parent unless it passes the absolute path of the parent's directory. `delete_sdd_work_files.sh` takes
  explicit file paths, refuses anything outside `${CLAUDE_PROJECT_DIR}/.sdd-work/` (resolved with
  `git rev-parse --show-toplevel` when the env var is unset - so it resolves per worktree) and refuses directories, so concurrent writers each
  delete only their own named files; the directory is never wiped (`--prune-empty` uses `rmdir`, which
  only removes an empty dir). The recipe's rule "scratch files named by unit id, deleted by name" already makes concurrent
  writers safe provided names don't collide (e.g. `batch_review_<id>_...` names by batch id; a
  parallel batch must keep that id).
- Generated artifacts the QA/hook scripts assume at project root: `qa-screenshots/` (Screenshot
  directory), `.sdd-work/design_check_*.png`, `.sdd-work/qa_scratch.jsonl` (one fixed name - a second
  concurrent `do_qa` in the same worktree would clobber it).

## 7. `design_prompt.md` / `design.md` and `register_design`

- On disk before the command: nothing is required in the spec dir. It takes the design input as an
  ARGUMENT (pasted handoff prompt, a file path to one, or a bare claude.ai/design link), NOT from a
  file already in the spec dir. The command itself writes `design_prompt.md` (verbatim prompt), then
  `design_source/`, `design_screenshots/`, `design.md`.
- `/sdd:start` today never looks for `design_prompt.md`. So for the idea's "if there is a
  `design_prompt.md` then call `sdd:register_design`": the file would be placed by the user in the
  spec dir BEFORE `/sdd:start` (e.g. under `spec_dd/1. next/<dir>/design_prompt.md`, moved with the
  dir by `move_spec_to_in_progress.md`), and the chained call would pass that file's path as the
  design input (the command already accepts "a file path" and reads it when the argument is an existing
  path; step 1 would then rewrite the same file verbatim to the same path - harmless but must not
  delete first). Note: `register_design` Step 1 resolves `<spec-dir>` from the current branch name when
  on a feature branch (the directory under `spec_dd/2. in progress/` named after the branch), which
  holds after `start_worktree` (worktree name == branch == spec dir name) provided the session works
  inside the new worktree.
- What it asks the user: nothing except `/design-login` authorisation (no AskUserQuestion in its
  allowed-tools). It never asks for notes or about what the design draws. Failures are non-blocking
  (mark "not yet read", commit anyway), except an unrecognised input which stops it.
- It runs `claude_plugins/sdd/scripts/design_screenshots.sh` (Playwright via Python) via a mechanic;
  non-zero exit only goes in the summary.
- It never runs the pre-step rebase; commits to the current branch only (so it must run after the worktree
  exists, on the feature branch); on `main` it commits without push. Committing to the new worktree's
  branch would also need a push (feature branch: `commit_and_push.md` pushes; first push
  `git push -u origin HEAD`).
- The `design.md` content is read by `spec_from_idea` ("A design.md, beside the idea or named under its
  Resources"), `plan_from_spec` Step 1/3 and `implement_plan` (via the plan's Design section), so
  registering BEFORE `spec_from_idea` is the right order for the idea's chain, and the idea file edits
  made in `register_design` Step 5 (Resources bullet) happen before research workers read the idea.

## 8. Front-loading patterns available for a chained start -> register_design -> spec_from_idea

- `spec_from_idea.md` Step 2 and the shared recipe (`fanout_recipe.md` step 1; copied verbatim in
  `spec_from_idea.md`, `plan_from_spec.md`, `spec_review.md`): "Start the work; don't ask permission
  for it", spawn workers first, then ask at depth 0 in batches of up to four per `AskUserQuestion`
  while the workers run; strike questions as research files land and ask the new ones raised.
- The earns-a-question test (changes what gets built; not answerable from source/code/finished unit/running
  unit; no obvious default) and "each question carries a recommended answer and one clause on why it
  matters".
- "When a question comes late": takes the recommended default and records it (spec: `## Open
  questions` as `- Q: ... -> A: ... (assumed default: <why safe>. Overrule by editing <section>.)`;
  plan: `> **Assumed default:** ...`), judgement calls batched once at the end. Nothing is stored or
  stalled. This is the pattern the idea ("get the input up front so that nothing gets stored. ...
  without stalling") maps to.
- `blocked` -> supply `needs` from source, else ask in the command's question batch; a hook-run brief
  is instead recorded as skipped.
- Existing pre-flight question sites already in `/sdd:start` Step 0 (roadmap precursor / dependency
  `AskUserQuestion`) and `setup_todo_list.md` overwrite-todo question, `register_design`'s
  `/design-login`. A chained flow could batch these (Step 0 precursor/dependency, todo overwrite,
  the idea-level spec questions that today come after research starts) into one `AskUserQuestion` at the
  top, then pass answers into the helpers' prompts. Important: `spec_from_idea` Step 2's questions are
  "the questions the idea itself leaves open and no research task bears on" - these can be asked before
  or while the worktree is being set up (setup takes minutes: `uv sync`, `npm i`, tailwind, migrate).
  The setup script could run in the background (Bash `run_in_background`) while questions are asked at depth 0.
- Hard limit on pre-asking: questions that depend on research findings ("as each research file lands")
  and review judgement calls ("end-of-run batch") are produced later; only the first group is front-loadable.
  Mechanics (`sdd:sdd-mechanic`) can't ask, so the orchestrator must bake answers in the prompt.

## 9. Conflicts / things a chained or parallel flow would break

1. **Generic-plugin rule** (`CLAUDE.md` "Plugins"): `sdd` must carry no FLS name/path/value. Therefore:
   - No `db_<branch>`, port 6543, `uv`, `npm`, or `fls_dev` in `sdd` text. Today `sdd` already says `uv run
     git commit` in `implement_plan.md` and `commit_and_push.md` ("uv run"), `uv run pytest` in
     `run_test_tier.md`; these are already generic-ish "project's commit command" leaks (`qa-bugfixer`
     says "the command the project's CLAUDE.md names"). New text should follow the `CLAUDE.md`-named
     commit command pattern rather than add more.
   - Parallel-worktree setup/teardown must go through `.claude/sdd/config.md` keys. The existing
     `Setup script` / `Teardown script` run "from inside the new worktree" and the Teardown script
     "drops the current branch's DB" - reusable as-is for short-lived worktrees, since both are
     cwd/branch-based. A cheaper variant (skip `npm i`/tailwind for a worktree that only runs pytest)
     would be a new optional key (e.g. a lighter setup script) set in `.claude/sdd/config.md` and
     documented in `/sdd:init` (`init.md` documents every key; not read in this pass).
   - `settings.json` permissions are project files; adding `Bash(git worktree *)` there is project
     config, not plugin text. But `update-claude-project-settings` is the only skill that edits it.
2. **Permissions** (`.claude/settings.json`): allowed already: `Bash(git branch *)`, `git switch *`,
   `git rebase *`, `git add:*`, `git fetch:*`, `git push *`, `git -C * ...` for a subset
   (`status, rev-parse, log, diff, fetch origin main, add, rm, checkout --, branch --show-current, ...`),
   `uv run git commit:*`, `uv run --directory * git commit *`, `uv run --directory * pytest*`,
   the three fls-dev DB scripts and `install_dev.sh` (bare, `./`, and `bash` forms), `uv sync --directory *`,
   `npm --prefix * run tailwind_build*`, `Skill(sdd:*)`. NOT allowed: `git worktree *` (add/remove/list/prune),
   `git cherry-pick`, `git merge`, `git -C * commit`/`cherry-pick`/`worktree`, `git branch -D` is covered
   by `git branch *`, `npm i`/`npm install` (hence `npm --prefix * run tailwind_build` only), `cd` into
   another directory (do_qa Rule 3c forbids `cd X && ...` because it triggers a prompt). Each of
   these would prompt (stall) the unattended flow, which defeats the point of the idea unless the permissions
   are added. Deny list blocks `git commit --no-verify`, `git push --force` (note
   `rebase_main.md` pushes with `--force-with-lease --force-if-includes`, kept allowed by prefix design).
   Note `git worktree add <name>` run from the bare repo parent: bare-parent paths are outside the project
   root; `Read`, `Edit`, `Write` outside the project root also prompt.
3. **Hooks**: `.claude/settings.json` has PreToolUse hooks that block `.env*` read/edit (not a
   concern) and a `SessionStart` hook that halts the session ("PLUGINS NOT LOADED") unless
   `CLAUDE_PLUGINS_LOADED` is set (the `claude.sh` launcher). A `claude -p` / `Agent` spawned process
   in another worktree inherits the env in-process (subagents), but a separately launched `claude`
   process (for a second session in a new worktree) must be started via `./claude.sh` or it stops
   at SessionStart. Relevant if "continue the chain inside the new worktree" were implemented as
   launching a new Claude session; it is NOT needed if the chain keeps running in the current
   session and passes absolute worktree paths (but then every Bash call needs `git -C`/absolute paths,
   because cwd resets between Bash calls and `cd` prompts).
   The `security-guard` PreToolUse hook (referenced in `do_qa.md` Rule 3b) blocks raw recursive force-delete on
   `Bash`/`Write`/`Edit` - so removal of a temp worktree directory must use `git worktree remove`, never `rm -rf`.
4. **Session model / cwd**: `/sdd:start` runs where the session started (main checkout). Pre-step rebase,
   `register_design` (branch name -> spec dir), `commit_and_push.md` (`git rev-parse --abbrev-ref HEAD`,
   refuses on main), `.sdd-work/`, `todo.md` paths all assume cwd == the feature worktree. The new
   worktree is outside the project root of the starting session (`../<name>`). The Claude Code session cannot
   change its own cwd by a Bash `cd` (it resets), and no command uses `EnterWorktree`. So the chain must
   either (a) pass absolute paths and `git -C <worktree>` everywhere (breaks the "follow these steps" text of
   every helper which assumes relative paths/cwd, and `git -C` has a limited allow-list), (b) use the
   session tools `EnterWorktree`/`ExitWorktree` if available in the deferred tool set (UNVERIFIED here;
   no reference in the repo) or (c) end the command with the user relaunching in the worktree
   (today's behaviour). This is the central design decision for item 1 of the idea.
5. **`todo.md` is the manifest and serial**: only a mechanic edits it, via `update_todo.md`, and
   "Nothing writes `todo.md` while batches run" (implement_plan). Parallel branches/worktrees editing
   `todo.md` would conflict; keep ticks at depth 0 in the feature worktree only.
6. **Pre-step rebase can `pause`** a chain (upstream-change review awaiting a decision). A chained
   `start -> register_design -> spec_from_idea` begins right after `start_worktree` branched from the
   freshly updated branch, so the rebase is usually a no-op (`rebased: no`, only a `git fetch`), but the
   `paused`/`blocked` return must stop the whole chain and relay the reason. `register_design` runs no rebase
   at all.
7. **Commit semantics**: `start` commits on the CURRENT (main) branch and does not push; subsequent
   artifact commits are on the feature branch and push (`commit_and_push.md` refuses main). The first
   push of the new feature branch is `git push -u origin HEAD`. In a chain `register_design` commits to
   the feature branch and pushes before the spec exists. Fine, but each of those is a separate commit per
   current rules; "combine steps" does not change commit granularity unless the spec decides it should.
8. **`implement_plan` and QA text conflicts**: `implement_plan.md` "DO NOT run the frontend_qa plan during
   implementation" and `plan_from_spec.md` "The plan file MUST NOT say that the QA file should be run" are
   explicit prohibitions to rewrite/scope (the plan must stay free of QA mentions - chaining can live in the
   command, not the plan). Also `setup_todo_list.md` produces a separate `(cmd)` QA item that `do_qa` ticks;
   if `implement_plan` runs QA inline it must still tick both items (via `update_todo.md`). `do_qa` Step 15's
   `tick:` must still match the plan's file name.
9. **Fix loops vs worktrees**: `do_qa` fixers (`qa-bugfixer`) commit on the feature branch with the dev
   server still running (reload from the same worktree), and `git revert --no-edit` (allowed: `uv run git
   revert:*`). Parallelising QA bug-fixers across worktrees would break "re-drive the failed flow on the
   still-running dev server" (the server serves one worktree's code); keep bugfixing serial.
10. **Test tiers**: `test_tiers.md` says "Run one tier at a time per worktree" (shared dev DB `test_db_<branch>`
    and xdist `_gw` databases). So parallel coding in sibling worktrees is compatible only because each has its
    own branch-derived test DB, never for two tiers in the SAME worktree. `implement_plan`'s Batch review mechanic/worker
    and `run_test_tier` already assume one tier at a time.
11. **Docs drift to fix when editing**: `commands/README.md` step 6 `--fill` vs the file; `README.md` (plugin)
    counts ("15 files", "7 helper files", "Skills (4)", "Scripts (9)", "Resources (9)"), and
    `claude_plugins/sdd/commands/README.md` is "the" workflow guide that any chained flow has to update
    (including the checklist layout, since `setup_todo_list.md` defines the items commands tick).
12. **Context protection / models**: running `spec_from_idea` etc. at depth 0 inside one long session
    grows the main context; the idea wants subagents to protect context. Only leaf work can go to a subagent
    (no nesting), so the sensible split is: depth-0 orchestrator does only question-asking, state tracking
    and review; `sdd-mechanic` runs worktree creation and setup (in the background), `sdd-worker`s do research,
    and `general-purpose`/sonnet agents do coding and QA support. `do_qa` browser driving explicitly must stay at
    depth 0 on the session model (the context cost sits there).

## Open items I could not verify from the repo alone

- Whether this Claude Code build exposes `EnterWorktree`/`ExitWorktree` and the `Agent` `isolation: "worktree"`
  parameter; the repo mentions `isolation: worktree` only as a frontmatter field in `subagents.md:36` and has no
  usage. The spec should check the Claude Code documentation (https://code.claude.com/docs/en/sub-agents) rather than assume.
- `commands/init.md` (documents every config key) and `resources/plan_review_dimensions.md`,
  `domain_vocabulary.md`, `writing_standard.md` were not read in this pass; the spec author needs them for
  adding a config key / a plan-review dimension / wording.
- `.claude/ds/scripts/select_tests.sh` and pytest-playwright port behaviour in a second worktree.

status: ok · reason: all requested files read except init.md, writing_standard.md, domain_vocabulary.md, plan_review_dimensions.md, qa-data-helper.md and pyproject test config (flagged in Open items)
