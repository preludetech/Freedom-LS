---
description: Commit the current work quickly, without running tests or re-reading the changes
allowed-tools: Bash, Read
argument-hint: "[mine|all]"
---

Commit what is currently in flight. Fast.

This is the quick counterpart to `/ds:commit`, which runs the full pytest suite first. Use this one
mid-implementation, when you already know the state of the work and want it recorded. Use `/ds:commit`
when the commit is a checkpoint you have not verified.

This command runs at **depth 0**, inline. It spawns no subagents.

## The speed contract

**Do not**:

- run pytest, ruff, mypy, or any other check
- read the contents of a changed file
- run `git diff` in patch mode — `--stat` and `--name-only` only
- spawn a subagent or invoke another slash command

The commit message comes from the file list and the spec directory name, not from reading the diff.

## Arguments

`$ARGUMENTS` is optional and is one of:

- `mine` — stage only the files you edited or created in this conversation
- `all` — stage everything, including untracked files

Both are ignored when the index already has staged changes (see Step 2).

## Step 1: Safety

```
git branch --show-current
```

If the branch is `main` or `master`, stop and tell the user. Do not commit.

## Step 2: Decide what to stage

```
git status --short
git diff --cached --name-only
```

**If `git diff --cached --name-only` prints anything**, the user has already staged what they want.
Commit exactly that. Never run `git add`. Ignore `$ARGUMENTS`.

**Otherwise**, go by the argument:

- `mine` — stage only the files you edited or created in this conversation, by name. If you have no
  record of editing any file in this conversation, stop and say so. Never guess at which files
  were yours.
- `all` — `git add -A`.
- **No argument** — compare the files you edited in this conversation against the dirty set from
  `git status --short`. If the two sets are identical, the distinction is moot: `git add -A` and
  carry on. If they differ, or you have no record of your own edits, ask the user once with
  `AskUserQuestion` — `mine` or `all` — and then proceed.

Never stage environment files, credential files, or key material, whatever the argument says. If
`git status` shows one, leave it out and say so in the final report.

## Step 3: Write the message

Base it on `git diff --cached --name-only`, `git diff --cached --stat`, and the name of the spec
directory under `spec_dd/2. in progress/`.

- One subject line, imperative, lowercase after the first word, under about 72 characters.
- A body only when the change spans several unrelated concerns, and then at most three lines.
- No process narration — no "as requested", no "per the plan", no section citations.
- End with the trailer:

```
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

## Step 4: Commit

```
uv run git commit -m "…"
```

`uv run` is required by the project's `CLAUDE.md` — the pre-commit hooks live in the uv environment.

If a hook rewrites files and aborts the commit, `git add -u` the files it touched and retry **once**.
If it fails a second time, stop: print the hook output and leave the work staged. Never pass
`--no-verify`.

## Step 5: Report

One line: the short hash, the subject, and the number of files committed. Add the excluded-secrets
note from Step 2 if there was one.
