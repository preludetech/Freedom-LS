---
description: Check that the spec makes sense
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, Skill, Agent, AskUserQuestion
---

You are doing the final check on a feature spec before it is planned. Five workers each check one dimension in parallel. You apply the fixes that have one reading and ask the user about the rest.

# Output

- Edit the spec to fix every problem the wave finds.
- Print a summary with one line per applied fix (what, dimension, evidence) and the spec's line and word counts before and after.

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents. See the `claude-code-authoring` skill for *why* it works this way. Orchestrating units U1…Un:

1. **Start the work; don't ask permission for it.** Never ask whether to review or fan out: spawn the workers. Subagents can't use `AskUserQuestion`, so bake into each prompt everything the worker needs from what is on disk. Never ask what a worker or the code will answer, and never hold a worker back for an answer it doesn't need. Ask once, early, with a default; late questions and review judgement calls follow "When a question comes late" in the `claude-code-authoring` skill's `fanout_recipe.md`.
2. **One output path per unit.** Intermediate outputs go in `.sdd-work/` at the project root, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "sdd:sdd-worker"`. Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → supply the listed `needs` from the source, the code or another unit's output if you can; ask in the end-of-run batch only if you can't. Then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step.** Read the output *files* (pass paths, never dump contents into the prompt) and edit the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Delete this command's own scratch files **by name**, never the `.sdd-work/` directory, which is shared with every other SDD command.

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
