# Spec-Driven Development (SDD)

A step-by-step workflow for taking a rough idea all the way to a merged pull request. Each step produces an artifact that feeds the next one, so you can pause, review, and correct course between stages.

## The workflow at a glance

1. **Idea** → write a rough idea file, optionally refine it.
2. **Spec** → turn the idea into a specification, review it, threat-model it.
3. **Plan** → turn the spec into an implementation plan and a QA plan, then security-review the plan, then structure-review the plan.
4. **Worktree** → set up an isolated worktree for the work.
5. **Implement** → execute the plan.
6. **Code security review** → review the code diff for security issues.
7. **QA** → run the QA plan.
8. **Refresh the app map** → if structure changed, re-run `/app_map`.
9. **Ship** → PR, address feedback, finish worktree.

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

Run `/plan_from_spec`. This produces:

- an implementation plan, and
- a QA plan.

## Step 3.5: Plan security review

Run `/plan_security_review` to review the implementation plan for insecure design choices (raw SQL, missing auth, unvalidated input, etc.) before any code is written. This is cheaper than catching the same issues in `/security-review` after implementation, because design-level security problems often require structural rework.

This complements `/threat-model` (which reviews the spec) and `/security-review` (which reviews the code diff).

## Step 3.6: Plan structure review

Run `/plan_structure_review` to check whether the plan introduces any new cross-app dependencies. The command reads `docs/app_structure.md` (the authoritative dependency diagram) and compares it against the imports the plan implies. Any new edge becomes a `> **Structure concern:**` callout that the user must resolve — either by accepting the edge (with a rationale, and regenerating the diagram after implementation) or by restructuring to avoid it.

This complements `/plan_security_review`: same callout-and-approval pattern, different concern. Catching structural drift at plan time is cheaper than unpicking it after the code is written.

If `docs/app_structure.md` doesn't exist yet, run `/app_map` first. `/app_map` is a general command (not SDD-specific) that walks `apps.py`-containing directories, extracts cross-app `ImportFrom` edges via `ast`, and writes a mermaid diagram plus a dependency table. Re-run it whenever an approved structural change lands, then commit the updated file.

## Step 4: Set up a worktree

Run `/start_worktree` to create an isolated worktree for this spec. All implementation and QA work happens here.

## Step 5: Implement

Run `/implement_plan` to execute the implementation plan.

## Step 6: Code security review

Run `/security-review` to check the code diff for security issues. Running this before QA means structural security fixes don't force QA to be re-run.

## Step 7: QA

Run `/do_qa` to execute the QA plan.

### Reacting to the QA report

- If tests were skipped because of missing data or fixtures, create the needed test data (the `qa-data-helper` agent is designed for this).
- If bugs were detected, fix them using TDD — write a failing test that reproduces the bug, then implement the fix. *(A dedicated bugfix command is still TODO.)*
- If QA fixes change code significantly, re-run `/security-review`.

## Step 8: Refresh the app map

If `/plan_structure_review` surfaced any structure concerns that were accepted (i.e. the plan intentionally introduced new cross-app edges), or if implementation ended up adding, removing, or renaming apps, re-run `/app_map` to regenerate `docs/app_structure.md`. Commit the updated file alongside the feature so the diagram stays the authoritative reference for the next structure review.

If no structural change happened, skip this step.

## Step 9: Ship it

1. Open a pull request.
2. Run `/address_pr_review` to work through review feedback.
3. Once merged, run `/finish_worktree` to clean up the worktree.

---

## The `todo.md` checklist

`/sdd:init` creates a `todo.md` checklist in the spec directory that tracks every step above. Each SDD command ticks off its own box (and adds follow-up tasks where relevant) by invoking the protected helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` as its final step. You don't run this helper yourself — the other commands call it for you.

---

## TODO

- Command for reacting to QA-reported bugs.
- Command for producing an upgrade guide when a change affects downstream projects that extend FLS.
