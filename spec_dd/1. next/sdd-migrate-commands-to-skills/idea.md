# Idea: Migrate the SDD workflow from slash commands to skills

## Goal

Re-architect the `fls-claude-plugin/commands/sdd/` workflow so its reusable logic lives in **skills**
rather than **slash commands**. This is the deferred follow-up to the
`sdd-token-efficiency-and-structure` round, which explicitly scoped this migration out (see decision **D3**
in that spec) and fixed only the immediate "impossible instruction" problems by moving fan-out to depth 0.

## Background: why this is the right direction

Research done for the `sdd-token-efficiency-and-structure` round (the four `research_*.md` docs in that
spec directory) verified current Claude Code behaviour and found:

- **Custom commands have largely merged into skills.** Skills are the going-forward primitive.
- **Subagents can invoke skills (via the `Skill` tool) but cannot type slash commands.** So any workflow
  step a subagent needs to run reusably must be a skill, not a slash command.
- **Skills can be auto-triggered and can be preloaded** via a `skills:` frontmatter field — no special
  permission needed.

The previous round worked *around* this by running `(cmd)` steps at depth 0 on the main thread (so their
own fan-out is legal) and making the user `/clear` before each `/sdd:next`. That removed the bug but kept
the slash-command structure. Converting to skills is the structurally clean fix and unblocks subagents
invoking workflow logic directly.

## Problems / opportunities to address

### 1. Convert each SDD command to a skill
Decide, per command, whether it becomes a skill, stays a thin slash-command shim that invokes a skill, or
is retired. Candidates in `commands/sdd/`: `start`, `improve_idea`, `spec_from_idea`, `spec_review`,
`plan_from_spec`, `plan_security_review`, `plan_structure_review`, `implement_plan`, `do_qa`,
`finish_worktree`, `next`, and the `protected/` helpers (`setup_todo_list`, `start_worktree`,
`update_todo`).

### 2. Re-evaluate the orchestration model
With logic in skills, a subagent *can* run a workflow step itself. Reconsider the depth-0 /
fresh-agent-per-step model chosen in the previous round: is the manual `/clear` before `/sdd:next` still
needed, or can an orchestrator skill manage context and fan-out more cleanly now that nesting constraints
interact differently with skills?

### 3. Keep the slash-command UX for the user
Users still trigger steps with `/sdd:next`, `/sdd:start`, etc. The migration should preserve that
entry-point UX (likely thin command shims that delegate to skills), so the change is internal.

### 4. Preserve all current behaviour and outputs
Same artifacts (idea/spec/plan/QA/todo), same user-facing step sequence, same model-tiering and
resilience improvements landed in the previous round. This is a structural migration, not a behaviour
change.

## Out of scope (likely)

- Changing what the workflow produces or the user-facing step order.
- Experimental Agent Teams / `SendMessage` / resumable live subagents.

## Open questions for the spec phase

- Per-command disposition: skill vs. shim-over-skill vs. retire.
- Whether the orchestration (depth-0 + manual `/clear`) model from the previous round can be simplified
  once steps are skills.
- How `skills:` preloading interacts with the input-contract + re-spawn pattern.
- Confirm the target Claude Code version's skill/command behaviour before committing (the previous round
  targeted the 2.1.x line).

## Success criteria

- SDD workflow logic lives in skills; subagents can invoke any step directly via the `Skill` tool.
- User-facing entry points (`/sdd:*`) and the produced artifacts are unchanged.
- The token-efficiency, model-tiering, and resilience gains from the previous round are preserved.
