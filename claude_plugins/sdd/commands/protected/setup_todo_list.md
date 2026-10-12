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
| `1. spec.md` | "Run `/sdd:spec_from_idea`…" |
| `2. plan.md` | "Run `/sdd:plan_from_spec`…" |
| `3. frontend_qa.md` | (also covered by the plan step — `/sdd:plan_from_spec` produces both) |
| `qa_report.md` | the item that executes the QA plan (see Step 4) |

Only tick boxes for artifacts that actually exist. Do **not** tick user-review items, worktree/PR/cleanup items, or anything else where presence of a file can't confirm the step was done — those are for the user to tick manually.

If you're unsure whether a file counts (e.g. an unusually named markdown file that might be an idea, research, or something else), leave the box unchecked rather than guessing.

## Step 4: Read the QA command

Read `.claude/sdd/config.md` (and `.claude/sdd/config.local.md` if it exists — its values take precedence). Under the **QA Hooks** section, look at the **QA command** value:

- A non-blank value is a skill name such as `<plugin>:<skill>`. The QA item in the checklist becomes `- [ ] (cmd) Run \`/<QA command>\` to execute the QA plan`.
- A blank value, or an absent section or file, means the project has no QA command. The QA item becomes `- [ ] (user) Execute the QA plan by hand`.

## Step 5: Write todo.md

Create `todo.md` in the target directory with the checklist below, applying the tick marks determined in Step 3 and the QA item from Step 4 in place of `<QA item>`. Preserve the structure exactly — later commands and the user both rely on it.

Each item is marked with who does it:

- **(user)** — the user does this by hand
- **(cmd)** — run a slash command

Every item must have exactly one marker. If a step involves both a manual action and a command, split it into two separate items (or use sub-items under a parent step).

```markdown
# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items and the two PR commands. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [ ] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [ ] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [ ] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
<QA item>
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed

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
- A one-line reminder that the caller will continue the workflow (e.g. by setting up a worktree)
