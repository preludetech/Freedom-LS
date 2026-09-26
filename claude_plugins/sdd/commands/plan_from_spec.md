---
description: Create an implementation plan based on a spec file
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent
---

You are helping to take a comprehensive development plan, based on this a spec file.

# Output

- Create a plan document in the same directory as the spec file. Name it `2. plan.md`
- Optionally: Create a document called `3. frontend_qa.md`
- Print a short summary of what you did

- DO NOT mention the frontend qa in the plan file. We will run the qa process after the plan is complete.
- DO NOT mention the security review in the plan file. We will run this later on

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents. See the `claude-code-authoring` skill for *why* it works this way (no subagent nesting, fan-out only at depth 0, `AskUserQuestion` is orchestrator-only, file-based hand-off, model tiering). Orchestrating units U1…Un:

1. **Start the work; don't ask permission for it.** Never ask whether to research, scan or fan out: spawn the workers. Subagents can't use `AskUserQuestion`, so bake into each prompt everything the worker needs from what the user has already said and what is on disk. Questions only the user can answer are asked at depth 0 *while* the workers run: as early as possible, batched up to four per `AskUserQuestion`. Never ask what a worker or the code will answer, and never hold a worker back for an answer it doesn't need.
2. **One output path per unit.** Durable artifacts keep their real names (e.g. `research_<topic>.md`); intermediate outputs go in `.sdd-work/` at the project root, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "sdd:sdd-worker"` (or `"sdd:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → supply the listed `needs` from the source, the code or another unit's output if they can; ask via `AskUserQuestion` only if they can't. Then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Once the phase artifact is finalised, delete this command's own scratch files **by name** — never the `.sdd-work/` directory itself, which is shared with every other SDD command and may hold a concurrent run's files. Durable artifacts are not deleted; an abandoned `.sdd-work/` from an interrupted run is intentional (it makes resume cheap).

# Step 0: Pre-step rebase

Read `claude_plugins/sdd/commands/protected/pre_step_rebase.md` and follow its steps (skip this
when `/sdd:next` says it already ran this turn).

# Step 1

Read the spec carefully and make sure you understand what is needed. Spawn the Step 4 skills/MCP scan now, in the background; it needs only the spec.

If the spec or its directory names a `design.md`, it registers a Claude Design design. Read the design through the Claude Design integration as that file says, and have the plan name, per slice, the design screens and states it builds and the `design.md` path.

If there are contradictions the code can't resolve, ask about them all at once, batched up to four per `AskUserQuestion`, and carry on with Step 2 while you wait. Fix the spec with the answers before writing the plan.

# Step 2

Investigate existing code to find relevant files and functionality. Make sure the code is kept DRY. If there is existing functionality we should be using, mention it in the plan.

# Step 3

Write the plan document.

The spec's vocabulary is the plan's vocabulary, in every identifier the plan proposes. A concept the plan turns up that the spec never named gets its name in the spec, not here.

## Order the plan as vertical slices

Structure the plan as a sequence of vertical slices, not horizontal layers. A slice is a thin piece of behaviour that runs end to end through every layer it needs (model, migration, service, view, URL, template, tests) and leaves the system working and testable when it is done.

- Make the first slice the thinnest one that runs end to end. Later slices widen it: more fields, more cases, permissions, error branches, edge cases.
- Order slices by value and dependency. Each slice builds only on slices before it.
- Each slice names the behaviour it delivers and the tests that prove it, so it can be implemented and committed alone with the full test suite passing.
- Don't group work by layer ("all the models", then "all the views", then "all the templates"). A slice holds only the model, view or template changes its behaviour needs.
- Put shared groundwork in its own step only when no single slice can own it. Keep it as small as possible and put it immediately before the first slice that uses it.

# Step 4: Skills/MCP scan (fan-out)

This worker was spawned in Step 1. It is **one `sdd:sdd-worker`** that scans the available skills and MCPs and writes `.sdd-work/plan_skill_scan.md` (atomically, with a `status:` footer). Then fold the result into the plan: update it to say what skills and MCPs should be used where. (Single unit, but file-based + structured so it is resumable/retryable per the recipe.)

# Step 5

If there are changes to any frontend then create a frontend_qa.md file.

This should explain how to check that the feature works using a browser. It should explain where to go, how to log in, what urls to visit, what buttons to click, what you expect to see, etc.

This can include multiple tests and workflows.

When scoping QA, don't only walk the golden path. For each area of functionality the change touches, explicitly reason about what *else* is affected and what could reasonably break — including unintended side-effects and failure/adversarial branches (e.g. "an existing account signs up again", enumeration/permission branches, invalid input, repeat submissions) — and add QA steps that exercise those. Keep it proportionate: prompt side-effect/failure-mode thinking, don't mandate exhaustive matrices.

If this plan is created then reference it in the plan file as a final step.

IMPORTANT: We will be generating a webserver port at random. we wont be using port 8000 (the default django runserver port). Don't talk about port 8000 in the test.
- `PORT=$(.claude/ds/scripts/find_available_port.sh)`
- We run the runserver command like this: `uv run python manage.py runserver $PORT`
- Base ul is `http://127.0.0.1:$PORT`

## Notes

- Note we will be following TDD. Do not write out all the tests at this point.
- Include pseudocode for desired functionality where appropriate
- if specific functions should be used or edited, or specific files need to be edited or referenced, mention them in the task description

## IMPORTANT

- DO NOT include any manual verification in the plan.md file, ALL manual verification should be in the frontend_qa file
- If you created a `3. frontend_qa.md` file, DO NOT mention it inside `2. plan.md`

# Step 6: Review the plan (fan-out)

The review dimensions below become **one `sdd:sdd-worker` per dimension**, each writing `.sdd-work/plan_review_<dim>.md` (structured status). Apply resume/retry/blocked per the recipe. Then read the findings (files, not dumped contents) and edit `2. plan.md` accordingly. Dimensions:

- All the success criteria will be met by the plan in place
- The plan is ordered as vertical slices (see Step 3): each slice delivers working, tested behaviour end to end, the first slice is the thinnest one that runs end to end, and no step groups work by layer
- No step in the plan contradicts any skill
- No step will result in junk files that need to be manually cleaned up
- All suggested code changes are clean and simple
- Every noun, and every identifier the plan proposes, matches the spec's vocabulary and the codebase's

### IMPORTANT
The plan.md file MUST NOT say that the frontend_qa should be run. We will run that separately.

The plan also must not create documentation of any kind. It must just be an implementation plan. It should not include any other steps from the SDD plugin. It is only implementation.

# Step 7: Clean up

Delete this run's own scratch files — one `.sdd-work/<phase>_<unit-id>.md` per worker you spawned — once `2. plan.md` and any `3. frontend_qa.md` are finalised. Name each path explicitly; never remove the `.sdd-work/` directory itself (recipe step 7).

# Step 8: Update the todo list

Invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as the spec file
- `tick:"Run `/plan_from_spec` to generate the implementation plan and QA plan"`
- If you did **not** create a `3. frontend_qa.md` (because the feature has no frontend changes), also pass `add:"QA|user|No QA needed — feature has no frontend changes"`. Otherwise omit `add:`.

# Step 9: Commit and push

Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/resources/commit_and_push.md` and follow its
steps with `<summary>`: `write the implementation plan`. Tell it to stage `2. plan.md`, any
`3. frontend_qa.md`, and the `todo.md` beside them.
