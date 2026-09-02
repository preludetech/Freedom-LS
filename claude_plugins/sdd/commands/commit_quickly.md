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

## Optimise for the user's time

A hook failure you can fix in under a minute is **not a decision point**. Fix it and move on.
Escalate only when the retry budget in Step 4 is spent, or the failure is genuinely outside this
commit. Never turn a fixable hook failure into a conversation.

## The speed contract

**Do not**:

- run pytest, ruff, mypy, or any other check **proactively** — the hooks are the gate, don't
  pre-empt them
- read the contents of a changed file **before** a hook has complained about it
- run `git diff` in patch mode — `--stat` and `--name-only` only
- spawn a subagent or invoke another slash command

**Once a hook fails**, exactly two things open up: you may read the files the hook named, and you
may re-run that one check to verify your fix. Nothing else — still no pytest, no full-repo sweeps,
no patch-mode diff.

The commit message comes from the file list and the spec directory name, not from reading the diff.
Lead the subject with the spec directory name, as every SDD commit does — e.g.
`interested_login: add the cohort filter form`.

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

**If `git diff --cached --name-only` prints anything**, work out *whose* staging it is:

- **You did not stage it in this conversation** → it is the user's. Commit exactly that. Never run
  `git add`. Ignore `$ARGUMENTS`.
- **An earlier run of this command staged it** (a previous attempt that a hook rejected) → it is
  yours, not a user decision. Re-apply `$ARGUMENTS` against the full dirty set and carry on.
  **Never** ask the user to adjudicate staging this command itself created.

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

### If the hooks reject the commit, fix it — do not stop

Hooks fail in layers: clearing one often reveals the next. That is normal progress, not a reason to
escalate. Work the loop.

**Budget: up to 5 attempts.** Stop early only when an attempt fails *identically* to the one before
it — same hook, same finding. That means you are not making progress, and another retry won't help.

On each failure, classify what you got:

| Failure | Action |
| --- | --- |
| A formatter rewrote files (`ruff-format`, `trailing-whitespace`, `end-of-file-fixer`) | `git add -u` the files it touched and retry. No thinking required. |
| A check reported fixable errors (`mypy`, `ruff check`, `bandit`, `shellcheck`) | **Fix them.** Read only the files named in the output, make the minimal correct change, `git add -u`, retry. |
| `detect-secrets` / `detect-private-key` flagged a line | Read the line. If it is a **real** credential, stop immediately and tell the user — never work around it. If it is plainly a false positive (a fixture name, a doc example, a reserved-domain URL), prefer removing the literal; where the wording cannot avoid it, append the tool's own `pragma: allowlist secret` marker, as `.claude/fls-dev/config.md` already does. |
| The failure is in a file you neither created nor modified in this conversation, and unrelated to this commit | Pre-existing breakage. Stop and report it — do not fix unrelated code. Note that the `mypy` hook is whole-repo (`pass_filenames: false`), so this can happen. |

**Hard rules for the loop:**

- Never pass `--no-verify`.
- Never `# type: ignore`, never a blanket `noqa`, never a new `[[tool.mypy.overrides]]` block, never
  any config relaxation to dodge an error. Fix the code. A *targeted* `noqa: <CODE>` with a comment
  justifying it is acceptable where the rule is genuinely wrong about the line.
- Never use `AskUserQuestion` about a hook failure. Fixing it **is** the job.
- Only once the budget is spent, or an attempt repeats identically: stop, print the last hook
  output, leave the work staged, and say in one line what still fails.

## Step 5: Report

One line: the short hash, the subject, and the number of files committed. Add the excluded-secrets
note from Step 2 if there was one.
