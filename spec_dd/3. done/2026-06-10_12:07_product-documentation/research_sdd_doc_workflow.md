# Research: SDD Doc Workflow

Research for the "product-documentation" idea: how to build a repeatable `/fls:sdd:update_product_docs` command that slots into the SDD workflow.

---

## A. SDD Command Structure

### File layout

Commands live in `fls-claude-plugin/commands/sdd/` (SDD-specific) or `fls-claude-plugin/commands/` (general). Protected helper commands are in `fls-claude-plugin/commands/sdd/protected/`. Agent definitions are in `fls-claude-plugin/agents/`.

Key files read:
- `fls-claude-plugin/commands/sdd/improve_idea.md` — example of a depth-0 fan-out command
- `fls-claude-plugin/commands/sdd/implement_plan.md` — batched worker fan-out
- `fls-claude-plugin/commands/sdd/do_qa.md` — Playwright MCP at depth 0, uses helper agents
- `fls-claude-plugin/commands/sdd/next.md` — orchestrator that runs other commands inline
- `fls-claude-plugin/commands/sdd/finish_worktree.md` — final cleanup step
- `fls-claude-plugin/commands/sdd/protected/setup_todo_list.md` — canonical todo template
- `fls-claude-plugin/commands/sdd/protected/update_todo.md` — tick/append helper
- `fls-claude-plugin/skills/claude-code-authoring/SKILL.md` — authoritative rules

### Frontmatter format

Every command file opens with YAML frontmatter:

```yaml
---
description: <short description>
allowed-tools: Read, Write, Glob, Bash, Agent, ...
---
```

Optional: `name:`, `model:` (inert when inlined by `/sdd:next`). There is no command registration file beyond the directory layout — `plugin.json` only names the plugin.

### How the fan-out recipe works

All fan-out must happen at **depth 0**. The pattern used consistently across commands:

1. Declare and bake inputs up front.
2. One output file per research/review unit — durable artifacts use real names (e.g. `research_<topic>.md`); scratch goes in `.sdd-work/` inside the spec directory.
3. Resume = skip units whose output file ends with `status: ok`.
4. One `fls:sdd-worker` (Sonnet) per unit, spawned in parallel via the `Agent` tool. Mechanical units use `fls:sdd-mechanic` (Haiku).
5. Structured returns: `ok` done, `failed` retry ≤2, `blocked` ask user then re-spawn.
6. Synthesis is a separate step that reads the output files (by path, never inline contents).
7. Delete `.sdd-work/` on success.

### How todo.md is structured and items get ticked/appended

The todo has numbered sections (## 1. Idea, ## 2. Spec, etc.) with checklist items. Each item is prefixed `(user)` or `(cmd)`.

Ticking is done by calling `update_todo.md` helper with:
- `<todo-path>` — absolute path to `todo.md`
- `tick:"<exact item text minus the - [ ] prefix>"`
- Optionally: `add:"<section heading>|<marker>|<item text>"` for follow-up tasks

The `update_todo.md` helper uses `Edit` to flip `- [ ]` to `- [x]` and appends new items at the end of the named section. This is called by the SDD command itself as its last step (or delegated to `fls:sdd-mechanic`).

### How `next` decides the next step

`next.md` reads `todo.md`, walks top-to-bottom for the first `- [ ]` item, inspects its `(user)`/`(cmd)` marker, then either asks the user to confirm manual completion or reads the referenced command file inline and follows its steps on the main thread (depth 0). The command file for `(cmd)` items is resolved by stripping the `/sdd:` or `/` prefix and checking `fls-claude-plugin/commands/sdd/<name>.md` then `fls-claude-plugin/commands/<name>.md`.

### Where a new `update_product_docs` command slots in

A new command file at `fls-claude-plugin/commands/sdd/update_product_docs.md` is the correct location. Its final step calls `update_todo.md` to tick its own checkbox. The command is invoked by `/sdd:next` like any other `(cmd)` item.

---

## B. SDD Lifecycle / Canonical Step Order

From `fls-claude-plugin/commands/sdd/protected/setup_todo_list.md` (the authoritative template) and `fls-claude-plugin/commands/sdd/README.md`:

```
1. Idea          — write idea, optionally /improve_idea, user reviews
2. Spec          — /spec_from_idea, user reviews, /spec_review, user addresses issues
3. Threat model  — /threat-model, user closes gaps
4. Plan          — /plan_from_spec (produces plan + frontend_qa), user reviews
5. Plan security review — /plan_security_review, user addresses
6. Plan structure review — /plan_structure_review, user addresses
7. Implementation — /implement_plan, user spot-checks
8. Code security review — /security-review, user addresses
9. QA            — /do_qa, user reviews, user fixes bugs TDD
10. Pull request  — user opens PR, /address_pr_review, user merges
11. Cleanup       — /finish_worktree, user moves spec to done/
```

### Where the documentation step belongs

The documentation update step should be inserted between the existing **step 9 (QA)** and **step 10 (Pull request)**, becoming a new **step 9.5 or step 10** before the PR is opened. This is the right moment because:

- The feature code is fully implemented and QA-verified.
- Screenshots can be taken of the finished, working UI before any teardown.
- The PR reviewer sees the updated docs alongside the code change.
- It is after all code changes are final, so docs won't be invalidated by later fixes.

The todo template in `setup_todo_list.md` must have a new section (or appended items under a new section heading) added between QA and Pull request:

```markdown
## 10. Product documentation

- [ ] (cmd) Run `/update_product_docs` to update docs/product/ for this feature
- [ ] (user) Review the updated documentation
```

The existing Pull request and Cleanup sections shift to ## 11 and ## 12, or the new step is inserted as a sub-section of QA. Either approach works; a new numbered section is cleaner.

Note: the `setup_todo_list.md` artifact-detection table should also be updated to pre-tick the documentation step if a `docs/product/` file already matches the feature (though this is edge-case).

---

## C. Claude Code Authoring Conventions

Source: `fls-claude-plugin/skills/claude-code-authoring/SKILL.md`

### Key rules for writing a new command/skill

**Model tiering:**
- Mechanical chores (ticking todo, git commits, file moves) → delegate to `fls:sdd-mechanic` (`model: haiku`)
- Non-interactive fan-out (research, review) → `fls:sdd-worker` (`model: sonnet`)
- Interactive authoring / depth-0 orchestration → session model (no `model:` override needed)
- `model:` frontmatter on a command file is **inert when the command is inlined by `/sdd:next`** — tiering must live on the agent files, not the command file.

**Fan-out constraints:**
- `Agent` tool is only available at depth 0 — no subagent can spawn subagents.
- Subagents cannot call slash commands, only read helper files and follow their steps.
- `AskUserQuestion` is depth-0 only.
- Subagents signal completion via `status: ok|failed|blocked` footer in output file.

**New command frontmatter minimum:**
```yaml
---
description: <short, clear description that triggers skill auto-loading if needed>
allowed-tools: Read, Glob, Write, Edit, Bash, Agent, mcp__playwright*
---
```

**Practical do/don't:**
- Do use `fls:sdd-mechanic` for the final `update_todo` call (cheap mechanical step).
- Do use `fls:sdd-worker` for parallel research units (one per doc section to update).
- Do end each worker output with `status: ok|failed|blocked` + `reason:`.
- Do not invent extra work beyond what was asked.
- Do not add logging or abstract base classes.
- Do not use `# type: ignore`.

---

## D. Screenshot Capability (Playwright MCP)

### Available skills and MCP

- `fls-claude-plugin/skills/use-playwright/SKILL.md` — the interactive browsing skill; covers `browser_take_screenshot`, `browser_snapshot`, navigation, forms, HTMX interactions. Pre-loads the Playwright MCP tool grants.
- `fls-claude-plugin/skills/playwright-tests/SKILL.md` — for writing Playwright E2E test code (not interactive browsing).
- `fls-claude-plugin/commands/sdd/do_qa.md` — the live example of Playwright MCP at depth 0 for visual testing.

### How screenshots are captured in the existing workflow (`do_qa.md`)

1. A free port is found: `PORT=$(.claude/fls/scripts/find_available_port.sh)`
2. Dev server starts: `uv run python manage.py runserver $PORT`
3. Playwright MCP tools are used directly: `mcp__playwright__browser_navigate`, `mcp__playwright__browser_take_screenshot`, `mcp__playwright__browser_resize`, etc.
4. Screenshots are saved to a `screenshots/` subdirectory named `desktop_<id>_<desc>.png`, `mobile_<id>_<desc>.png`, `tablet_<id>_<desc>.png`.
5. After all captures: `uv run --with pillow python ${CLAUDE_PLUGIN_ROOT}/scripts/compress_screenshots.py` compresses to stay under the 1024 KB pre-commit limit.
6. Server is killed: `.claude/fls/scripts/kill_runserver.sh $PORT`

The `mcp__playwright*` wildcard in `allowed-tools` grants all Playwright MCP tools.

### For the doc workflow

The `update_product_docs` command should:
- Run at depth 0 (for Playwright MCP access — MCP tools are not available in subagents unless explicitly granted).
- Launch a dev server at a free port, capture screenshots with `browser_take_screenshot`, compress them, kill the server.
- Store screenshots under `docs/product/screenshots/` (or a feature-specific subdirectory).
- Reference them in the markdown doc files with standard `![](screenshots/...)` syntax.
- Only capture screenshots for features with visible UI (skip for pure backend/API features).

The `do_qa.md` command is the live template for this whole pattern and can be used as a direct reference when authoring `update_product_docs.md`.

---

## Summary of Actionable Notes

1. **New command location:** `fls-claude-plugin/commands/sdd/update_product_docs.md` — follows existing naming and location conventions exactly.

2. **Todo template change needed:** `fls-claude-plugin/commands/sdd/protected/setup_todo_list.md` must gain a new section (between QA and Pull request) with one `(cmd)` item and one `(user)` review item.

3. **Command structure:** depth-0 orchestrator with `mcp__playwright*` in `allowed-tools`; fan out research units as `fls:sdd-worker` per doc section; delegate todo-ticking to `fls:sdd-mechanic`; screenshot capture at depth 0 following the `do_qa.md` pattern.

4. **Screenshot pattern is already established:** the `compress_screenshots.py` script, `find_available_port.sh`, and `kill_runserver.sh` scripts are all ready to reuse. Screenshots for docs should land in `docs/product/screenshots/`.

5. **README.md for SDD** (`fls-claude-plugin/commands/sdd/README.md`) should be updated to mention the new step 10 (documentation) in the workflow overview.

---

status: ok
reason: All four research areas covered with direct file evidence from the codebase.
