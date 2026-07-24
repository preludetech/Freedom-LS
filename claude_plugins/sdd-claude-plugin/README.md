# sdd (spec-driven-development) plugin

The portable spec-driven-development (SDD) workflow for Claude Code: the `sdd-worker` / `sdd-mechanic`
tiering agents, the generic workflow command files, and the authoring/worktree/project-settings skills.
It carries the *scaffolding* for taking a feature from idea to merged PR; the FreedomLS-specific SDD
steps (`do_qa`, `plan_security_review`, `plan_structure_review`, the `update_*` docs/repo steps) live in
the separate `fls-dev` plugin, and generic stack commands (`app_map`, `threat-model`, `security-review`,
`commit`) live in `ds`.

Manifest name: `sdd`. Namespace: `/sdd:*`, `Skill(sdd:*)`.

> **Coupling note.** `sdd` is not yet fully standalone: the `setup_todo_list` template and the `next.md`
> dispatcher name FLS-specific steps (`/fls-dev:*`), and FLS commands spawn the `sdd` agents. Untangling
> this bidirectional `fls-dev` ↔ `sdd` dependency is deferred.

## What's inside (counted from disk)

### Commands (11 files)
Flat under `commands/`: `README` (the workflow guide), `init`, `start`, `improve_idea`, `spec_from_idea`,
`spec_review`, `plan_from_spec`, `implement_plan`, `next`, `finish_worktree`, `address_pr_review`.

`commands/protected/` (4 read-and-followed helper files, not advertised as slash commands): `setup_todo_list`,
`move_spec_to_in_progress`, `start_worktree`, `update_todo`.

`/sdd:next` is the workflow driver — it reads the spec's `todo.md`, finds the next unchecked step, and
dispatches each `(cmd)` item to its owning plugin via a deterministic keep-prefix map
(`sdd` → this plugin, `fls-dev` → the product plugin, `ds` → the stack plugin). This is why every command
the generated `todo.md` lists is written fully namespaced.

`/sdd:init` wires this plugin into a project (its own `enabledPlugins` key + `Skill(sdd:*)` permission +
`.claude/sdd/` config). It is **not** the primary init — it detect-and-skips the shared artifacts
(`claude.sh`, the `SessionStart` hook, the `.gitignore` `settings.local.json` line) that `/ds:init` owns.

### Agents (2)
`sdd-worker` (Sonnet) — one non-interactive unit of fan-out work (research topic / review dimension /
scan); `sdd-mechanic` (Haiku) — mechanical chores (test runs, commits, file moves, todo ticking). Spawn
one per unit from a depth-0 SDD command. Model tiering lives in each agent's `model:` frontmatter.

### Skills (3)
`claude-code-authoring` (+4 resources: `subagents`, `model_tiering`, `fanout_recipe`, `interactive_cli`) —
how Claude Code commands/skills/agents actually behave (targets 2.1.x); `git-worktree-setup` — the generic
bare-repo/worktree mechanics (the FLS per-branch-database delta lives in an `fls-dev` overlay);
`update-claude-project-settings` — audits `.claude/settings.json` and promotes useful permissions from
`.claude/settings.local.json`.

### Scripts (2)
`compress_screenshots.py`, `qa_cleanup.sh`.

### Resources (1)
`agent_memory_guidelines` — the canonical home for this generic guideline (it is also duplicated into
`ds` and `fls-dev` because `${CLAUDE_PLUGIN_ROOT}` is per-plugin and the agents that read it live in
different plugins).
