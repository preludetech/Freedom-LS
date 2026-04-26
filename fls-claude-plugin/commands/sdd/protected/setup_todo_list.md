---
description: Helper — create a todo.md checklist next to the spec or idea
allowed-tools: Read, Write, Glob, Bash
---

This is a helper command, invoked by `/sdd:start`. It creates a `todo.md` checklist that tracks a spec through the full Spec-Driven Development workflow.

The checklist is the single source of truth for where the work is. Every SDD step (from idea refinement through to merging the PR) is a checkbox, with clear markers for which steps the user does and which steps are run via slash commands.

## Step 1: Locate the spec or idea directory

Figure out which spec or idea we're working with. In order:

1. If the caller's input names a file or directory, use that.
2. Otherwise, look at the current branch name and try to match it to a directory inside `spec_dd/` (usually under `spec_dd/2. in progress/`).
3. If still ambiguous, list candidate directories under `spec_dd/` and ask the caller which one.

The target directory is the directory containing the idea or spec markdown file.

## Step 2: Check for an existing todo.md

If `todo.md` already exists in that directory:

- Read it.
- Ask the caller whether to overwrite it or leave it alone.
- Do not silently overwrite.

## Step 3: Detect existing artifacts

Most of the time an idea (and possibly more) is already in the directory. List the directory and pre-tick any checklist items whose artifacts already exist. Use these rules:

| Artifact found in the spec directory | Tick this item |
|---|---|
| A file matching `*idea*.md` (e.g. `0. idea.md`, `0.idea.md`, `idea.md`) | "Write the idea file in this directory" |
| Any file matching `research*.md` (e.g. `research_foo.md`, `research-bar.md`) | "Optionally run `/improve_idea`…" |
| `1. spec.md` | "Run `/spec_from_idea`…" |
| `2. plan.md` | "Run `/plan_from_spec`…" |
| `3. frontend_qa.md` | (also covered by the plan step — `/plan_from_spec` produces both) |
| `qa_report.md` | "Run `/do_qa`…" |

Only tick boxes for artifacts that actually exist. Do **not** tick user-review items, threat-model items, worktree/PR/cleanup items, or anything else where presence of a file can't confirm the step was done — those are for the user to tick manually.

If you're unsure whether a file counts (e.g. an unusually named markdown file that might be an idea, research, or something else), leave the box unchecked rather than guessing.

## Step 4: Write todo.md

Create `todo.md` in the target directory with the checklist below, applying the tick marks determined in Step 3. Preserve the structure exactly — later commands and the user both rely on it.

Each item is marked with who does it:

- **(user)** — the user does this by hand
- **(cmd)** — run a slash command

Every item must have exactly one marker. If a step involves both a manual action and a command, split it into two separate items (or use sub-items under a parent step).

```markdown
# SDD Todo

Checklist for taking this spec from idea to merged PR. Tick items as they are completed. See `fls-claude-plugin/commands/sdd/README.md` for the full workflow description.

## 1. Idea

- [ ] (user) Write the idea file in this directory
- [ ] (cmd) Optionally run `/improve_idea` to research and refine the idea
- [ ] (user) Review the refined idea and edit as needed

## 2. Spec

- [ ] (cmd) Run `/spec_from_idea` to generate the spec
- [ ] (user) Review the spec carefully and edit where needed
- [ ] (cmd) Run `/spec_review` to sanity-check the spec
- [ ] (user) Address any issues raised by the review

## 3. Threat model

- [ ] (cmd) Run `/threat-model` against the spec
- [ ] (user) Update the spec to close any security gaps surfaced

## 4. Plan

- [ ] (cmd) Run `/plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 5. Plan security review

- [ ] (cmd) Run `/plan_security_review` to check the plan for insecure design choices before implementation
- [ ] (user) Address any concerns raised in the plan

## 6. Plan structure review

- [ ] (cmd) Run `/plan_structure_review` to check for new cross-app dependencies
- [ ] (user) Address any structure concerns raised in the plan

## 7. Implementation

- [ ] (cmd) Run `/implement_plan` to execute the implementation plan
- [ ] (user) Spot-check the changes

## 8. Code security review

- [ ] (cmd) Run `/security-review` on the pending changes
- [ ] (user) Address any issues raised

## 9. QA

- [ ] (cmd) Run `/do_qa` to execute the QA plan (missing test data will be created automatically via the `qa-data-helper` agent)
- [ ] (user) Review the QA report
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/security-review` and address any new issues

## 10. Pull request

- [ ] (user) Open a pull request
- [ ] (cmd) Run `/address_pr_review` as review feedback comes in
- [ ] (user) Merge the PR once approved

## 11. Cleanup

- [ ] (cmd) Run `/finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
```

## Step 5: Report back

Print a short summary that includes:

- The path to the new `todo.md`
- Which items were pre-ticked (and why — i.e. which files were detected)
- A one-line reminder that the caller will continue the workflow (e.g. by setting up a worktree)
