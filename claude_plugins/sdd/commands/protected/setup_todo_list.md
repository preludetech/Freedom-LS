---
description: Helper — create a todo.md checklist next to the spec or idea
allowed-tools: Read, Write, Glob, Bash
---

This is a helper command, invoked by `/sdd:start`. It creates a `todo.md` checklist that tracks a spec through the full SDD workflow.

The checklist is the single source of truth for where the work is. Every step from idea refinement to merging the PR is a checkbox, marked as a user step or a slash-command step.

## Step 1: Locate the spec or idea directory

Find the spec or idea. In order:

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

An idea (and possibly more) is usually already in the directory. List the directory and pre-tick the checklist items whose artifacts exist:

| Artifact found in the spec directory | Tick this item |
|---|---|
| `1. spec.md` | "Run `/sdd:spec_from_idea`…" |
| `2. plan.md` | "Run `/sdd:plan_from_spec`…" |
| `3. frontend_qa.md` | (also covered by the plan step — `/sdd:plan_from_spec` produces both) |
| `qa_report.md` | the item that executes the QA plan (see Step 4) |

Only tick boxes for artifacts that exist. Do **not** tick user-review items, worktree/PR/cleanup items, or anything else a file's presence can't confirm; the user ticks those. If unsure whether a file counts (e.g. an unusually named markdown file), leave the box unchecked.

## Step 4: Read the QA command

Read `.claude/sdd/config.md` (and `.claude/sdd/config.local.md` if it exists — its values take precedence). Under the **QA Hooks** section, look at the **QA command** value:

- A non-blank value is a skill name such as `<plugin>:<skill>`. The QA item in the checklist becomes `- [ ] (cmd) Run \`/<QA command>\` to execute the QA plan`.
- A blank value, or an absent section or file, means the project has no QA command. The QA item becomes `- [ ] (user) Execute the QA plan by hand`.

## Step 5: Write todo.md

Create `todo.md` in the target directory with the checklist below, applying the tick marks from Step 3 and the QA item from Step 4 in place of `<QA item>`. Preserve the structure exactly; later commands and the user rely on it.

Each item is marked with who does it:

- **(user)** — the user does this by hand
- **(cmd)** — run a slash command

Every item has exactly one marker. A step with both a manual action and a command becomes two items (or sub-items under a parent).

```markdown
# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [ ] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [ ] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [ ] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
<QA item>
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
```

## Step 6: Report back

Print a short summary that includes:

- The path to the new `todo.md`
- Which items were pre-ticked (and why — i.e. which files were detected)
- A one-line reminder that the caller continues the workflow (e.g. by setting up a worktree)
