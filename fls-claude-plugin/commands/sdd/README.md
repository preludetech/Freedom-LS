# Spec-Driven Development (SDD)

A step-by-step workflow for taking a rough idea all the way to a merged pull request. Each step produces an artifact that feeds the next one, so you can pause, review, and correct course between stages.

## The workflow at a glance

1. **Idea** → write a rough idea file, optionally refine it.
2. **Spec** → turn the idea into a specification, review it, threat-model it.
3. **Plan** → generate the QA plan (`/plan_qa`), then generate the implementation plan via `/plan_dev` which reviews the plan via subagents (testing, structure, security) and commits per reviewer.
4. **Implement** → execute the plan.
5. **Code security review** → review the code diff for security issues.
6. **QA** → run the QA plan.
7. **Refresh the app map** → if structure changed, re-run `/app_map`.
8. **Ship** → PR, address feedback, finish worktree.

> `/sdd:start` is the entry point: it creates the `todo.md` checklist next to the spec/idea **and** sets up an isolated worktree for the work. Run it once, then do everything else inside the worktree.

> **One-time setup:** before the first SDD run on a project, run `/app_map` to generate `docs/app_structure.md`. The structure review step compares proposed plans against that diagram.

---

## Step 1: Capture the idea

1. Create an idea file manually (a markdown file describing what you want to build and why).
2. Optionally run `/improve_idea` to research the idea and suggest improvements.

## Step 2: Write the spec

1. Run `/spec_from_idea` to generate a specification from the idea file.
2. Review the spec and edit it manually where needed.
3. Run `/spec_review` to sanity-check the spec.

## Step 2.5: Threat model

1. Run `/threat-model` on the spec to identify security considerations.
2. Update the spec to close any gaps the threat model surfaced, before moving on to planning.

## Step 3: Build the plan

The plan phase is **two slash-command invocations**, not three:

1. **`/plan_qa`** generates `3. frontend_qa.md` from the spec — a sequence of declarative behaviour rules (`BR-NN`) paired with Playwright walkthroughs. Skippable for features with no frontend and no frontend-triggered side effects.
2. **`/plan_dev`** generates `2. plan.md` from the spec (and the QA plan, if there is one). Internally, `/plan_dev` runs three reviewers — testing, structure, security — as subagents in sequence. They flag concerns in the plan, the orchestrator commits per reviewer, and you get a single end-of-flow summary instead of three separate gates.

Reviewer commands stay first-class as escape hatches: `/plan_security_review`, `/plan_structure_review`, and `/plan_testing_review` all remain runnable from the CLI on their own if you've manually edited the plan after `/plan_dev` ran.

If `docs/app_structure.md` doesn't exist yet, run `/app_map` first — the structure reviewer compares plans against that diagram. `/app_map` is a general command (not SDD-specific) that walks `apps.py`-containing directories, extracts cross-app `ImportFrom` edges via `ast`, and writes a mermaid diagram plus a dependency table. Re-run it whenever an approved structural change lands, then commit the updated file.

The `/plan_dev` orchestration mode complements `/threat-model` (which reviews the spec) and `/security-review` (which reviews the code diff): the in-plan reviewers catch design-level problems before code exists.

## Step 4: Implement

Run `/implement_plan` to execute the implementation plan.

## Step 5: Code security review

Run `/security-review` to check the code diff for security issues. Running this before QA means structural security fixes don't force QA to be re-run.

## Step 6: QA

Run `/do_qa` to execute the QA plan.

### Reacting to the QA report

- If tests were skipped because of missing data or fixtures, create the needed test data (the `qa-data-helper` agent is designed for this).
- If bugs were detected, fix them using TDD — write a failing test that reproduces the bug, then implement the fix. *(A dedicated bugfix command is still TODO.)*
- If QA fixes change code significantly, re-run `/security-review`.

## Step 7: Refresh the app map

If `/plan_structure_review` surfaced any structure concerns that were accepted (i.e. the plan intentionally introduced new cross-app edges), or if implementation ended up adding, removing, or renaming apps, re-run `/app_map` to regenerate `docs/app_structure.md`. Commit the updated file alongside the feature so the diagram stays the authoritative reference for the next structure review.

If no structural change happened, skip this step.

## Step 8: Ship it

1. Open a pull request.
2. Run `/address_pr_review` to work through review feedback.
3. Once merged, run `/finish_worktree` to clean up the worktree.

---

## The `todo.md` checklist

`/sdd:start` creates a `todo.md` checklist in the spec directory that tracks every step above. Each SDD command ticks off its own box (and adds follow-up tasks where relevant) by invoking the protected helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` as its final step. You don't run this helper yourself — the other commands call it for you.

---

## TODO

- Command for reacting to QA-reported bugs.
- Command for producing an upgrade guide when a change affects downstream projects that extend FLS.
