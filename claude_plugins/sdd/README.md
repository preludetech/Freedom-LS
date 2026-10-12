# sdd (spec-driven-development) plugin

The portable spec-driven-development (SDD) workflow for Claude Code: the `sdd-worker` / `sdd-mechanic`
tiering agents, the generic workflow command files, and the authoring/worktree/project-settings skills.
It carries the *scaffolding* for taking a feature from idea to merged PR. It is independent: anything
project-specific reaches it only through the project's configuration in `.claude/sdd/config.md`
(worktree scripts, rebase, design, test, plan review, review, documentation, QA and PR hooks, and
vocabulary sources). `/sdd:init` documents every key.

Manifest name: `sdd`. Namespace: `/sdd:*`, `Skill(sdd:*)`.

## What's inside (counted from disk)

### Commands (14 files)
Flat under `commands/`: `README` (the workflow guide), `init`, `roadmap`, `register_design`, `start`,
`spec_from_idea`, `spec_review`, `plan_from_spec`, `implement_plan`, `document`, `commit_quickly`,
`make_pr_quickly`, `finish_worktree`, `address_pr_review`.

`/sdd:document` invokes the skills the project lists under `## Documentation Hooks` in
`.claude/sdd/config.md`, in order, in hook mode. Each hook is a skill that commits
its own work, or names the files it changed for `/sdd:document` to commit. The plan review in `/sdd:plan_from_spec` runs its built-in dimensions
plus the project's own briefs, which `## Plan Review Hooks` lists; `sdd` names none.
`/sdd:address_pr_review` fetches review comments through the `Fetch PR comments` script under
`## PR Hooks`, or with `gh` directly when the key is blank. `/sdd:start` writes the `QA command`
under `## QA Hooks` into the checklist as the QA step, or a by-hand item when there is none.

`/sdd:roadmap` owns the spec roadmap, `spec_dd/1. next/roadmap.md`: with no argument it syncs the
file with the spec directories; with a directory it cuts a big idea into ordered sibling specs and
adds the effort, its dependency graph and its shared decisions to the roadmap.

`/sdd:register_design [dir] <handoff prompt or claude-design-url>` records a design drawn in Claude
Design on the spec the current branch is working on (on `main`, on the spec or cut effort's parent you
name), and commits it to the current branch only: it writes `<dir>/design.md` (the link, how to read it through the Claude Design
integration rather than the web, how faithfully to build to it, which spec owns each screen) and points
the consuming specs at it. `spec_from_idea` and `plan_from_spec` read any `design.md` they are pointed at.

`commands/protected/` (7 read-and-followed helper files, not advertised as slash commands): `setup_todo_list`,
`move_spec_to_in_progress`, `start_worktree`, `update_todo`, `update_roadmap`, `pre_step_rebase`,
`run_test_tier`. `run_test_tier` reaches the project's test tier definition through the `Test tiers`
key under `## Test Hooks` in `.claude/sdd/config.md`; a blank key falls back to the project's plain pytest command.

`/sdd:init` wires this plugin into a project (its own `enabledPlugins` key + `Skill(sdd:*)` permission +
`.claude/sdd/` config). It does not create the shared launcher artifacts
(`claude.sh`, the `SessionStart` hook, the `.gitignore` `settings.local.json` line); it expects them to exist.

### Agents (2)
`sdd-worker` (Sonnet) — one non-interactive unit of fan-out work (research topic / review dimension /
scan); `sdd-mechanic` (Haiku) — mechanical chores (test runs, commits, file moves, todo ticking). Spawn
one per unit from a depth-0 SDD command. Model tiering lives in each agent's `model:` frontmatter.

### Skills (3)
`claude-code-authoring` (+4 resources: `subagents`, `model_tiering`, `fanout_recipe`, `interactive_cli`) —
how Claude Code commands/skills/agents actually behave (targets 2.1.x); `git-worktree-setup` — the generic
bare-repo/worktree mechanics;
`update-claude-project-settings` — audits `.claude/settings.json` and promotes useful permissions from
`.claude/settings.local.json`.

### Resources (9)
`agent_memory_guidelines` — how agents treat memory; `launcher_editing` — how to edit `claude.sh`
(with `<MAY_CREATE>` false: `sdd` adds its line to an existing launcher and never creates one); `domain_vocabulary` — use the project's existing words, and
declare any word that really is new. The project points at its own sources via
`## Vocabulary Sources` in `.claude/sdd/config.md`; `writing_standard` — the rules every SDD artifact
obeys; `commit_and_push` — the commit-and-push steps every artifact command ends with;
`roadmap_format` — the shape, classification rules and row grammar of the spec roadmap;
`spec_review_dimensions` — the five dimensions of the spec review wave; `plan_review_dimensions` — the
nine built-in plan review dimensions; `idea_standard` — what an idea must contain before a spec is written from it.
