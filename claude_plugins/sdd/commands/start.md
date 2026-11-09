---
description: Initialise an SDD workflow — create the todo.md checklist next to the spec or idea, then create an isolated git worktree for the work
allowed-tools: AskUserQuestion, EnterWorktree, Artifact, Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, ToolSearch, WebFetch, WebSearch
---

This command kicks off Spec-Driven Development for a new spec. It is a chain: it sets up the todo
list and the worktree, enters the worktree, registers the design and writes the spec.

A mechanic that returns `blocked` in Steps 1 to 3 is asked about and re-spawned. Any other stop
ends the run: Step 4 returning `failed`, or a hook step (Step 6 or 7) returning `failed`, `blocked` or
`paused`. The report (Step 8) says what finished, why it stopped, and the single command that
continues, to be run from inside the worktree:
`/sdd:register_design <spec-dir>/design_prompt.md` when Step 6 did not finish, otherwise
`/sdd:spec_from_idea <idea path>`. When Step 3 never reported a worktree path, the command that
continues is `/sdd:start` itself, run again.

## Step 0: Check the spec roadmap

This runs before anything is spawned because its answer can be "stop".

If `spec_dd/1. next/roadmap.md` exists and has a bullet for this spec (the line starting
`` - `<spec directory name>` — ** ``), check its precursor first, then its blockers.

**Precursor.** A worktree branches off main, so work that has to happen on main comes first. The
spec has a precursor if its bullet ends with a `Before starting:` sentence, or if the directory
needs a cut by the test in `claude_plugins/sdd/resources/roadmap_format.md` (more than one
`idea*.md`, a nested idea or spec, or empty). Say what the precursor is and ask via
`AskUserQuestion`: "Stop and do it on main first (Recommended)" or "Start anyway". If the answer
is stop, stop here and name the command that does the precursor, e.g. `/sdd:roadmap <dir>` for a
cut.

**Blockers.** Read the bullet's `blocked by` list. A blocker is met when a directory named
`spec_dd/3. done/*_<name>` exists. For each unmet one, say where it stands (`ready`, `blocked` or
`in progress` per its own bullet) and ask via `AskUserQuestion` whether to start anyway or stop.
This is a warning, never a block: a feature's notes sometimes allow a spec to start before a
blocker lands. No roadmap, or no bullet: carry on without comment.

## Step 1: Set up the todo list

Delegate to `sdd:sdd-mechanic`: have it run the steps in `claude_plugins/sdd/commands/protected/setup_todo_list.md`. Pass through whatever the caller said about which spec or idea this is for, so the helper doesn't re-discover it.

Wait for the mechanic to finish and note the path to the spec directory it landed on and to its `todo.md` (`<todo-path>`); later steps need both. If the mechanic returns `status: blocked` (e.g. ambiguous spec dir, or an existing `todo.md`), gather the answer from the user via `AskUserQuestion` and re-spawn the mechanic with the answer.

## Step 2: Move the spec to "in progress" and commit

Delegate to `sdd:sdd-mechanic`: have it run the steps in `claude_plugins/sdd/commands/protected/move_spec_to_in_progress.md`, passing through the spec directory from Step 1.

This moves the spec into `spec_dd/2. in progress/` and commits the move (with the `todo.md` from Step 1) on the **current** branch, before any worktree exists. Wait for it to finish and confirm the working tree is clean and the move is committed before continuing. Handle any `blocked` return as in Step 1 (ask the user, re-spawn).

## Step 3: Create the worktree

Run this only **after** Step 2's commit has landed on the current branch: the new worktree must branch off a clean, up-to-date branch that already contains the move.

Delegate to `sdd:sdd-mechanic` with `run_in_background: true`, straight away: have it run the steps in `claude_plugins/sdd/commands/protected/start_worktree.md`, passing through the spec directory (now under `spec_dd/2. in progress/`).

While the mechanic runs:

- Read the idea and every sibling `*.md` in the spec directory. Ask the questions
  `${CLAUDE_PLUGIN_ROOT}/commands/spec_from_idea.md` Step 2 point 1 describes (the questions
  the idea itself leaves open and no research task bears on), under the recipe's test, up to
  four per `AskUserQuestion`, each with a recommended answer and one clause on why it matters.
  Further calls follow while the mechanic runs. Nothing is held back for a question.
- When `<spec-dir>/design_prompt.md` exists and `<spec-dir>/design.md` does not: load
  `Artifact` (`ToolSearch` with `select:Artifact`), take the link from the file the way
  `register_design.md` Step 1 does, call `list` with it as `url` and `scope: "files"`, then
  `read` `project/canvas.json` with `path` and an `out_dir` under the scratchpad directory, never
  the spec directory. Ask one question when the file holds no Design Artifact link (only a
  `claude.ai/design/p/` link, say), the listing has no `project/canvas.json`, or the `read`
  returns a summary: "Replace the link in `<spec-dir>/design_prompt.md` with the Design
  Artifact's link (get edit access, or move the design into Claude), then choose Done
  (Recommended)" or "Register the design without reading it". The answer is the design-access
  answer, passed to Step 6.
- Answers stay in context until Step 5.

Then collect the mechanic's return. A `blocked` return is handled as in Step 1 (ask, re-spawn), and the chain continues after it. Done when the mechanic has reported the worktree path.

## Step 4: Enter the worktree

Load the tool (`ToolSearch` with `select:EnterWorktree`), then call `EnterWorktree` with `path`
set to the worktree path the mechanic reported. Confirm `git branch --show-current` prints the
spec directory's folder name. Anything else is `status: failed` with the reason; stop.

## Step 5: Write `answers.md`

A single `Write` of `<spec-dir>/answers.md`:

```markdown
# Answers: <spec name>

Asked by `/sdd:start` before the spec was written.

- Q: <question>? → A: <answer> (asked up front)
```

One line per question asked in Step 3, the design-access answer included. No questions asked is an
empty list under the heading, and the file is still written.

When Step 7 will be skipped, or the chain stops before `spec_from_idea` Step 4 commits, delegate to
`sdd:sdd-mechanic`: read `${CLAUDE_PLUGIN_ROOT}/resources/commit_and_push.md` and follow it with
`<summary>`: `record the up-front answers`, staging `answers.md`. Otherwise `spec_from_idea` Step 4
commits it.

## Step 6: Register the design

When `<spec-dir>/design_prompt.md` exists and `design.md` does not, read
`${CLAUDE_PLUGIN_ROOT}/commands/register_design.md` and follow it with `mode: hook`, `<spec-dir>`,
the design input `<spec-dir>/design_prompt.md`, no notes, and the design-access answer. Otherwise
skip and say which condition failed.

## Step 7: Write the spec

When `<todo-path>` has the unticked item naming `/sdd:spec_from_idea`, read
`${CLAUDE_PLUGIN_ROOT}/commands/spec_from_idea.md` and follow it with `mode: hook`, `<spec-dir>`,
`<todo-path>`, the idea path and `answers: <spec-dir>/answers.md`. Otherwise skip and say so.

## Step 8: Report back

A fixed shape, at most fifteen lines:

- One line per step: `done`, `skipped: <why>`, or the status that stopped the chain.
- The worktree path.
- The artifacts written, with their paths.
- The number of assumed defaults the spec recorded, and the grep that finds them (`## Open questions`).
- The next human step from `todo.md`.
