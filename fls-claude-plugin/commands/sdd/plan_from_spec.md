---
description: Create an implementation plan based on a spec file
allowed-tools: Read, Write, Glob, Agent
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

1. **Declare inputs up front.** Gather any user input the phase needs now, via `AskUserQuestion`. Bake the answers into each worker prompt.
2. **One output path per unit.** Durable artifacts keep their real names (e.g. `research_<topic>.md`); intermediate outputs go in `.sdd-work/` inside the spec directory, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "fls:sdd-worker"` (or `"fls:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → gather the listed `needs` via `AskUserQuestion`, then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Delete `.sdd-work/` once the phase artifact is finalised. Durable artifacts are not deleted; an abandoned `.sdd-work/` from an interrupted run is intentional (it makes resume cheap).

# Step 1

Read the spec carefully and make sure you understand what is needed.

If there are any contradictions then ask for clarification and fix the spec before continuing.

# Step 2

Investigate existing code to find relevant files and functionality. Make sure the code is kept DRY. If there is existing functionality we should be using, mention it in the plan.

# Step 3

Write the plan document.

# Step 4: Skills/MCP scan (fan-out)

Spawn **one `fls:sdd-worker`** that scans the available skills and MCPs and writes `.sdd-work/plan_skill_scan.md` (atomically, with a `status:` footer). Then fold the result into the plan: update it to say what skills and MCPs should be used where. (Single unit, but file-based + structured so it is resumable/retryable per the recipe.)

# Step 5

If there are changes to any frontend then create a frontend_qa.md file.

This should explain how to check that the feature works using a browser. It should explain where to go, how to log in, what urls to visit, what buttons to click, what you expect to see, etc.

This can include multiple tests and workflows.

If this plan is created then reference it in the plan file as a final step.

IMPORTANT: We will be generating a webserver port at random. we wont be using port 8000 (the default django runserver port). Don't talk about port 8000 in the test.
- `PORT=$(.claude/fls/scripts/find_available_port.sh)`
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

The review dimensions below become **one `fls:sdd-worker` per dimension**, each writing `.sdd-work/plan_review_<dim>.md` (structured status). Apply resume/retry/blocked per the recipe. Then read the findings (files, not dumped contents) and edit `2. plan.md` accordingly. Dimensions:

- All the success criteria will be met by the plan in place
- No step in the plan contradicts any skill
- No step will result in junk files that need to be manually cleaned up
- All suggested code changes are clean and simple

### IMPORTANT
The plan.md file MUST NOT say that the frontend_qa should be run. We will run that separately.

# Step 7: Clean up

Delete the `.sdd-work/` scratch directory once `2. plan.md` and any `3. frontend_qa.md` are finalised (recipe step 7).

# Step 8: Update the todo list

Invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as the spec file
- `tick:"Run `/plan_from_spec` to generate the implementation plan and QA plan"`
- If you did **not** create a `3. frontend_qa.md` (because the feature has no frontend changes), also pass `add:"QA|user|No QA needed — feature has no frontend changes"`. Otherwise omit `add:`.
