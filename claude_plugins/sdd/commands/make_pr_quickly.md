---
description: Open a pull request for the current branch from the spec and todo, without re-reading the work
allowed-tools: Bash, Read, Glob, Edit
---

Open a pull request for the current branch. Fast, from what the SDD workflow already wrote down.

The spec directory already holds the *what* and `todo.md` already holds the *status*. Neither needs
to be reconstructed from the diff, and reconstructing it is what makes ordinary PR-writing slow.

This command runs at **depth 0**, inline. It spawns no subagents.

## The speed contract

Read these and nothing else:

- the **first 80 lines** of the spec's `1. spec.md`
- the spec's `todo.md`, in full

Run these git commands and nothing else, plus the push and `gh` calls in Step 5:

- `git branch --show-current`
- `git log main..HEAD --oneline`
- `git diff main...HEAD --stat`
- `git status --short`

**Do not**, under any circumstances:

- read `2. plan.md`, `research_*.md`, `qa_report.md`, `upgrade_notes.md`, `3. frontend_qa.md`, or any
  source file in the repo
- run `git diff` in patch mode (no `-p`, no bare `git diff`, no `git show`)
- run tests, linters, type checkers, or `gh pr view`
- spawn a subagent, invoke another slash command, or launch a search

If the spec does not say something, the PR body does not claim it.

## Step 1: Locate the spec

```
git branch --show-current
```

The spec directory is `spec_dd/2. in progress/<branch>/`.

If that directory does not exist, run `ls "spec_dd/2. in progress/"`:

- exactly one entry — use it
- zero or several entries — skip Step 2, build the body from the commit log alone, and say so in the
  final report

## Step 2: Read the two files

```
head -80 "<spec dir>/1. spec.md"
```

Use `head` via Bash, not the Read tool. Spec files run to tens of thousands of tokens; the title and
the opening summary are all the body needs.

Then read `<spec dir>/todo.md` in full. It is small.

## Step 3: Get the git facts

```
git log main..HEAD --oneline
git diff main...HEAD --stat
git status --short
```

If `git status --short` prints anything, stop. Tell the user to run `/sdd:commit_quickly` first and
do not continue.

## Step 4: Draft the body

Write the body to `.sdd-work/pr_body.md` (create `.sdd-work/` if it is missing). Writing to a file
rather than passing `--body` avoids shell quoting problems entirely.

```markdown
## What

<Two to four sentences, taken from the spec summary. Nothing invented.>

## Changes

<Three to eight bullets, grouped from the commit log. Group related commits — the reviewer
wants the shape of the change, not a commit-by-commit replay.>

## Spec

`spec_dd/2. in progress/<branch>/`

## SDD status

Done: <every ticked (cmd) item, by section name>
Outstanding: <every unticked (cmd) item, by section name>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

The **SDD status** section is a mechanical transcription of the `todo.md` checkboxes. Make no
judgement about whether a step was really needed and add no commentary. This section is what earns
the PR its review: it tells the reviewer at a glance that, say, the security review and the QA pass
have not run yet.

Title: a short imperative line drawn from the spec title. Lowercase after the first word, no trailing
full stop, no branch name.

## Step 5: Push and create

```
git push -u origin HEAD
gh pr create --base main --head "<branch>" --title "<title>" --body-file .sdd-work/pr_body.md
```

If `gh pr create` reports that a pull request already exists for the branch, run this instead and
report it as an update rather than a new PR:

```
gh pr edit --title "<title>" --body-file .sdd-work/pr_body.md
```

Delete `.sdd-work/pr_body.md` once the call succeeds.

## Step 6: Tick the todo

Read `claude_plugins/sdd/commands/protected/update_todo.md` and follow its steps literally, with:

- `<todo-path>`: the `todo.md` in the spec directory
- `tick:"Open a pull request"`

No new items to add. If Step 1 could not find a spec directory, skip this step.

## Step 7: Report

One line. The PR URL, then the outstanding SDD steps from the body.
