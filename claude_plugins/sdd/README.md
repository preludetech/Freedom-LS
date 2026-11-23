# sdd (spec-driven-development) plugin

The portable spec-driven-development (SDD) workflow for Claude Code: the `sdd-worker` / `sdd-mechanic`
tiering agents, the generic workflow command files, and the authoring/worktree/project-settings skills.
It is the *scaffolding* for taking a feature from idea to merged PR. `sdd` needs the
`productivity` plugin loaded, because its writing standard invokes `productivity:unslop`; nothing
else project-specific reaches it except through the project's configuration in `.claude/sdd/config.md`
(worktree scripts, rebase, design, test, plan review, review, documentation, QA hooks, and
vocabulary sources). `/sdd:init` documents every key.

Manifest name: `sdd`. Namespace: `/sdd:*`, `Skill(sdd:*)`.

## What's inside (counted from disk)

### Commands (17 files)
Flat under `commands/`: `README` (the workflow guide), `init`, `roadmap`, `register_design`, `start`,
`spec_from_idea`, `spec_review`, `plan_from_spec`, `implement_plan`, `document`, `commit_quickly`,
`make_pr_quickly`, `finish_worktree`, `capture_feedback`, `do_qa`, `qa_fix`, `hotfix`.

`/sdd:document` invokes the skills the project lists under `## Documentation Hooks` in
`.claude/sdd/config.md`, in order, in hook mode, then executes the documentation items in `todo.md` and opens the pull request. Each hook is a skill that commits
its own work, or names the files it changed for `/sdd:document` to commit. The plan review in
`/sdd:plan_from_spec` runs its built-in dimensions plus the project's own briefs, which
`## Plan Review Hooks` lists; `sdd` names none.
`/sdd:start` creates the checklist and the worktree, enters it, registers a design when one is present and writes the spec, and writes the `QA command`
under `## QA Hooks` into the checklist as the QA step, or a by-hand item when there is none.

`/sdd:do_qa` runs a spec's QA plan in a browser. It reads `## QA Hooks`, `## QA Login` and
`## QA Dev Data` in `.claude/sdd/config.md` once, before it starts, and stops `blocked` naming the
key when the browser server, port finder or a dev-server command is blank. It makes no data of its
own: it delegates to `sdd:qa-data-helper` or runs a `## QA Dev Data` command, and lists each change
in the report.

`/sdd:qa_fix` works through the `(user)` items a QA run left in `todo.md`. It researches each one,
asks for one decision at a time, has `sdd:qa-bugfixer` make each code fix test-first, screenshots
each fix that changes what a page shows into `screenshots/fixed/` and looks at it before calling it
fixed, tests the change, and ticks what it closed. `/sdd:start` writes it into the checklist after the QA step.

`/sdd:roadmap` owns the spec roadmap, `spec_dd/1. next/roadmap.md`: what is up next, then one
section per feature listing its specs (in progress, ready or blocked), an SVG dependency diagram
and lean notes. With no argument it syncs the file with the spec directories; with a directory it
cuts a big idea into ordered sibling specs and adds them as a feature. `scripts/roadmap.py` derives
statuses, "Up next" and the diagrams. `spec_dd/1. next/priority.md` lists specs and efforts under
priority headings; the script orders and colours the roadmap by it, and a spec is always at least
as high as anything that depends on it.

`/sdd:register_design [dir] <design artifact link>` records a Design Artifact on the spec the current
branch is working on (on `main`, on the spec or cut effort's parent you name), and commits it to the
current branch only. It reads the design through the `Artifact` tool and writes `<dir>/design.md` (the
link and version, how to read it, how faithfully to build to it, which spec owns each artboard) and points
the consuming specs at it. `spec_from_idea` and `plan_from_spec` read any `design.md` they are pointed at.

`commands/protected/` (7 read-and-followed helper files, not advertised as slash commands): `setup_todo_list`,
`move_spec_to_in_progress`, `start_worktree`, `update_todo`, `update_roadmap`, `pre_step_rebase`,
`run_tests`. `run_tests` is the only way this plugin runs tests. It hands one request (`change`, `everything`,
`before landing`, `one test` or `failed`) to the file the `Test runner` key under `## Test Hooks` in
`.claude/sdd/config.md` names, and returns that file's `tests:` line. The plugin names no test command, test
tool or CI service: the project's runner file owns all of it. A blank key returns `status: blocked`.
The `Pre-test rebuild` key in the same section names a script the runner runs before the tests of
`/sdd:finish_worktree`'s landing run.

`/sdd:init` wires this plugin into a project (its own `enabledPlugins` key + `Skill(sdd:*)` permission +
`.claude/sdd/` config). It expects the shared launcher artifacts (`claude.sh`, the `SessionStart` hook,
the `.gitignore` `settings.local.json` line) to exist and does not create them.

### Agents (4)
`sdd-worker` (Sonnet) — one non-interactive unit of fan-out work (research topic / review dimension /
scan); `sdd-mechanic` (Haiku) — mechanical chores (test runs, commits, file moves, todo ticking). Spawn
one per unit from a depth-0 SDD command. Each agent's `model:` frontmatter sets its tier. `qa-data-helper` (Opus) — creates, resets or
deletes development-database records a QA run needs, following the project's `Data helper guide`; its
memory lives at `.claude/agent-memory/sdd-qa-data-helper/`. `qa-bugfixer` (Sonnet) — fixes one
QA-reported bug TDD-style (failing test, fix, test the change, commit), using the skills under
`## Testing Skills` in `.claude/sdd/config.md`.

### Skills (5)
`claude-code-authoring` (+4 resources: `subagents`, `model_tiering`, `fanout_recipe`, `interactive_cli`) —
how Claude Code commands/skills/agents actually behave (targets 2.1.x); `git-worktree-setup` — the generic
bare-repo/worktree mechanics;
`update-claude-project-settings` — audits `.claude/settings.json` and promotes useful permissions from
`.claude/settings.local.json`; `planning-references-in-code` — keeps spec, plan, slice, batch, QA-bug and
`spec_dd/` references out of code comments, docstrings and test names; `outstanding-items` — puts
everything outstanding from the user into the spec's `todo.md`, so the chat never holds the only copy.

### Scripts (10 files)
`upstream_change_scan.sh`, `land_on_main.sh`, `design_screenshots.sh` (+ `design_screenshots.py`) — the
rebase upstream scan, the close-out landing and design screenshots. The QA scripts, allow-listed at
`claude_plugins/sdd/scripts/`: `qa_cleanup.sh`, `qa_collect_screenshots.sh`, `compress_screenshots.sh`
(+ `compress_screenshots.py`) and `delete_sdd_work_files.sh`. `qa_collect_screenshots.sh` takes the
spec directory, the screenshot source directory and an optional subfolder name (`fixed` for
`qa_fix`), and refuses a directory outside the project or a subfolder that is not a plain name.
`python_with.sh` runs Python with one extra package for the two screenshot scripts, using the
`Python with packages` command in `.claude/sdd/config.md` (`## Script Hooks`).

### Resources (9)
`agent_memory_guidelines` — how agents treat memory; `launcher_editing` — how to edit `claude.sh`
(with `<MAY_CREATE>` false: `sdd` adds its line to an existing launcher and never creates one); `domain_vocabulary` — use the project's existing words, and
declare any word that really is new. The project points at its own sources via
`## Vocabulary Sources` in `.claude/sdd/config.md`; `writing_standard` — the rules every SDD artifact
obeys; `commit_and_push` — the commit-and-push steps every artifact command ends with;
`roadmap_format` — the shape, classification rules and bullet grammar of the spec roadmap;
`spec_review_dimensions` — the five dimensions of the spec review wave; `plan_review_dimensions` — the
ten built-in plan review dimensions; `idea_standard` — what an idea must contain before a spec is written from it.
