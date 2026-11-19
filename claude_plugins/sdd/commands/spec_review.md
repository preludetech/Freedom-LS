---
description: Check that the spec makes sense
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, Skill, Agent, AskUserQuestion
---

You are doing the final check on a feature spec before it is planned. Five workers each check one dimension in parallel. You apply the fixes that have one reading and ask the user about the rest.

# Output

- Edit the spec to fix every problem the wave finds.
- Print a summary with one line per applied fix (what, dimension, evidence) and the spec's line and word counts before and after.

## Fan-out recipe

This command runs at **depth 0** and fans work out to sub-agents. When it spawns workers, read and
follow `${CLAUDE_PLUGIN_ROOT}/skills/claude-code-authoring/resources/fanout_recipe.md` (units U1…Un): never ask whether to review or fan out, ask once, early, with a default,
and send a `blocked` worker's need to the end-of-run batch only when you cannot supply it.

# Step 0: Pre-step rebase

Read `${CLAUDE_PLUGIN_ROOT}/commands/protected/pre_step_rebase.md` and follow its steps.

# Step 1: Review wave

Spawn one `sdd:sdd-worker` per row of `${CLAUDE_PLUGIN_ROOT}/resources/spec_review_dimensions.md`, each writing `.sdd-work/spec_review_<id>.md`. Brief each with the spec path, the idea path, the sibling `*.md` files, its row, and the finding format and clear-fix rule from that resource. For `feasibility`, add the `SKILL.md` paths of the skills the spec touches. Apply resume, retry and blocked per the recipe.

# Step 2: Apply the clear fixes

Read the five output files by path. Edit each clear fix into the spec.

Then re-run only the dimensions that produced an applied fix, once, briefed with the changed sections and writing `.sdd-work/spec_review_<id>_recheck.md` (a new path, so the resume scan never skips the re-check). A re-check finding that is not a regression of an applied fix goes to Step 3. There is no third round.

# Step 3: The end-of-run question batch

Put every judgement call to the user as "When a question comes late" in `fanout_recipe.md` describes. Edit each answer into the spec. Write an unanswered one under `## Open questions` in the assumed-default shape. Neither this step nor Step 2 resolves an open question by deleting it.

# Step 4: Clean up

Delete `.sdd-work/spec_review_<id>.md` and `.sdd-work/spec_review_<id>_recheck.md` for each id, by name, skipping any that does not exist.

# Step 5: Commit and push

Delegate to `sdd:sdd-mechanic`: read `${CLAUDE_PLUGIN_ROOT}/resources/commit_and_push.md` and follow its steps with `<summary>`: `review the spec`. Tell it to stage `1. spec.md`.
