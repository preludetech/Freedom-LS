---
description: Create an implementation plan based on a spec file
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, ToolSearch, AskUserQuestion
argument-hint: <spec path> [suffix, e.g. 2b]
---

You are helping to take a comprehensive development plan, based on this a spec file.

# Input

- `<spec path>`: the spec file.
- `[suffix]`: optional, `2` followed by letters (e.g. `2b`). The plan file is `<suffix>. plan.md`. The QA file swaps the leading `2` for `3`: `3<letters>. frontend_qa.md`. With no suffix they are `2. plan.md` and `3. frontend_qa.md`.

Below, **the plan file** and **the QA file** mean the resolved names.

# Output

- Create the plan file in the same directory as the spec file
- Optionally: Create the QA file
- Print a short summary of what you did

- DO NOT mention the frontend qa in the plan file. We will run the qa process after the plan is complete.

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents. See the `claude-code-authoring` skill for *why* it works this way (no subagent nesting, fan-out only at depth 0, `AskUserQuestion` is orchestrator-only, file-based hand-off, model tiering). Orchestrating units U1…Un:

1. **Start the work; don't ask permission for it.** Never ask whether to research, scan or fan out: spawn the workers. Subagents can't use `AskUserQuestion`, so bake into each prompt everything the worker needs from what the user has already said and what is on disk. Questions only the user can answer are asked at depth 0 *while* the workers run: as early as possible, batched up to four per `AskUserQuestion`. Never ask what a worker or the code will answer, and never hold a worker back for an answer it doesn't need. Ask once, early, with a default; late questions and review judgement calls follow "When a question comes late" in the `claude-code-authoring` skill's `fanout_recipe.md`.
2. **One output path per unit.** Durable artifacts keep their real names (e.g. `research_<topic>.md`); intermediate outputs go in `.sdd-work/` at the project root, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "sdd:sdd-worker"` (or `"sdd:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → supply the listed `needs` from the source, the code or another unit's output if they can; ask via `AskUserQuestion` only if they can't. Then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Once the phase artifact is finalised, delete this command's own scratch files **by name** — never the `.sdd-work/` directory itself, which is shared with every other SDD command and may hold a concurrent run's files. Durable artifacts are not deleted; an abandoned `.sdd-work/` from an interrupted run is intentional (it makes resume cheap).

# Step 0: Pre-step rebase

Read `claude_plugins/sdd/commands/protected/pre_step_rebase.md` and follow its steps.

# Step 1

Read the spec carefully and make sure you understand what is needed. Spawn the Step 4 skills/MCP scan now, in the background; it needs only the spec.

If the spec or its directory names a `design.md`, it registers a Claude Design design, and the Design section (Step 3) applies. Read `design_source/` and `design_screenshots/` from the directory that holds the `design.md`, and treat the design the way `design.md` says: a visual reference, never a source of scope. Load `DesignSync` (`ToolSearch` with `select:DesignSync`) only when those files are missing, and say so in the summary.

The plan builds only what the spec asks for. A drawn element the spec does not ask for is left out without a question: never ask the user whether to build something the design draws, and never add it to the spec.

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
- A slice that builds a designed screen carries the line `**Design states:** <id>, <id>`, naming the design states it builds. `implement_plan` reads this line.

## The Design section

Required when a `design.md` applies. It holds one transcription per design state the plan builds, then the token mapping.

**Transcription.** One block per design state, headed by its id: the screenshot's name without `.png` and with `__` as `/` (`<section-id>/<artboard-id>` for a canvas artboard, `<page>/<screen>` for a `.dc.html` screen):

- the design screenshot path;
- the viewport width, which is the screenshot's width;
- how to reach the state in the running app: the URL and the data it needs;
- the elements in order, with their hierarchy and copy;
- which controls show in this state;
- a **design checklist** closing the block: one checkable line per element, order rule or state rule.

Transcribe only the elements the spec builds; omit every other drawn element silently. Where the screenshot and the CSS disagree, transcribe the screenshot.

**Token mapping.** A table `Design treatment | FLS token / component / icon | Lost`, with a row for every tint, tile, weight, text treatment and icon the transcriptions use. Follow the shape of the "Token mapping" section in `spec_dd/3. done/2026-09-08_17:31_better-form-start-page/research_design_source.md`. Map to the project's existing theme tokens, cotton components and semantic icons only. Ignore the design's own colours, fonts and icons. Never propose a new theme, theme token, font or colour, and never propose an icon that does not fit the project's icon set. "Lost" records styling the theme cannot express, which is dropped; it is never something to add.

# Step 4: Skills/MCP scan (fan-out)

This worker was spawned in Step 1. It is **one `sdd:sdd-worker`** that scans the available skills and MCPs and writes `.sdd-work/plan_skill_scan.md` (atomically, with a `status:` footer). Then fold the result into the plan: update it to say what skills and MCPs should be used where. (Single unit, but file-based + structured so it is resumable/retryable per the recipe.)

# Step 5

If there are changes to any frontend then create the QA file.

This should explain how to check that the feature works using a browser. It should explain where to go, how to log in, what urls to visit, what buttons to click, what you expect to see, etc.

This can include multiple tests and workflows.

When scoping QA, don't only walk the golden path. For each area of functionality the change touches, explicitly reason about what *else* is affected and what could reasonably break — including unintended side-effects and failure/adversarial branches (e.g. "an existing account signs up again", enumeration/permission branches, invalid input, repeat submissions) — and add QA steps that exercise those. Keep it proportionate: prompt side-effect/failure-mode thinking, don't mandate exhaustive matrices.

A QA test that maps to a design state names that state's design screenshot path and copies the state's design checklist from the plan's transcription.

If this plan is created then reference it in the plan file as a final step.

IMPORTANT: We will be generating a webserver port at random. we wont be using port 8000 (the default django runserver port). Don't talk about port 8000 in the test.
- `PORT=$(.claude/ds/scripts/find_available_port.sh)`
- We run the runserver command like this: `uv run python manage.py runserver $PORT`
- Base ul is `http://127.0.0.1:$PORT`

## Notes

- Note we will be following TDD. Do not write out all the tests at this point.
- Include pseudocode for desired functionality where appropriate
- if specific functions should be used or edited, or specific files need to be edited or referenced, mention them in the task description
- Comments and docstrings in pseudocode and code snippets state the reasoning itself. They never cite the spec, the plan, its slices or its section numbers, because implementers copy them into the code verbatim.

## IMPORTANT

- DO NOT include any manual verification in the plan file, ALL manual verification should be in the QA file
- If you created the QA file, DO NOT mention it inside the plan file

# Step 6: Review the plan (fan-out)

One `sdd:sdd-worker` per row of `${CLAUDE_PLUGIN_ROOT}/resources/plan_review_dimensions.md`, each writing `.sdd-work/plan_review_<id>.md`. Then read `## Plan Review Hooks` in `.claude/sdd/config.md` (and `config.local.md`; a non-empty list there replaces the whole list). For each bullet `<label>: <path>`, in order, spawn one more `sdd:sdd-worker` briefed to read `<path>` and follow it with the plan path, the spec path and the output path `.sdd-work/plan_review_<file-stem>.md`, where `<file-stem>` is the path's basename without `.md`. Blank list, or absent section or file: no hook workers. Resume, retry and blocked per the recipe; a hook brief returning `blocked` with a need nothing on disk satisfies is recorded as "plan review hook <label> skipped: <need>" for the summary and the run continues.

Read every output file by path. A clear fix is edited into the plan. A judgement call becomes a callout at the relevant section, options numbered and the recommended one first. The callout is `> **Security concern:**` for `new_threats` and for a brief whose output opens with `callout: Security concern`, `> **Structure concern:**` for a brief whose output opens with `callout: Structure concern`, and `> **Review concern:**` otherwise. Then put every callout to the user as "When a question comes late" in `fanout_recipe.md` describes; the answer replaces the callout with the decision, and an unanswered callout becomes `> **Assumed default:** <what>. Why: <clause>. To change: <section>.` No callout survives without one or the other.

### IMPORTANT
The plan file MUST NOT say that the QA file should be run. We will run that separately.

The plan also must not create documentation of any kind. It must just be an implementation plan. It should not include any other steps from the SDD plugin. It is only implementation.

# Step 7: Clean up

Once the plan file and any QA file are finalised, delete by name every `.sdd-work/plan_review_<id>.md`, every `.sdd-work/plan_review_<file-stem>.md` and `.sdd-work/plan_skill_scan.md`, skipping any that does not exist. Never remove the `.sdd-work/` directory itself (recipe step 7).

# Step 8: Update the todo list

Invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as the spec file
- `tick:` the unticked item that names this command. With a suffix, that is the item that also names the suffix. Without one, it is `"Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan"`.

# Step 9: Commit and push

Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/resources/commit_and_push.md` and follow its
steps with `<summary>`: `write the implementation plan`. Tell it to stage the plan file, any
QA file and the `todo.md` beside them.
