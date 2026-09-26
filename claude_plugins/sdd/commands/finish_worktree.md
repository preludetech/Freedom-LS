---
description: Close out the current worktree: rebase, archive the spec, land the close-out on main and sync the main worktree
allowed-tools: Bash, Read, Glob, Skill, Agent
---

This command finishes a spec's worktree. It runs on the feature branch: it rebases the branch,
makes the close-out commits there (spec directory to done, roadmap row removed, project settings
tidied), then lands the branch on `main` by fast-forward and brings the main worktree up to date.
It runs at **depth 0** and delegates mechanical steps to the `sdd:sdd-mechanic` (Haiku) agent. See
the `claude-code-authoring` skill for the model behind this.

Two rules hold throughout:

- Conflicts are only ever resolved here, in the feature worktree. `main` only moves by
  fast-forward, only to a commit `origin` already holds.
- The main worktree is never cleaned up from this command. Never run `merge --abort`, `stash`,
  `reset` or `checkout` there. If it holds uncommitted work or an operation in progress, stop and
  say what is parked; a human decides what it means.

```
git branch --show-current
```

On `main` or `master`, stop: this command runs in a feature worktree only.

# Step 0: Pre-step rebase

Read `claude_plugins/sdd/commands/protected/pre_step_rebase.md` and follow its steps (skip this
when `/sdd:next` says it already ran this turn). Any status other than `ok` is this command's own
status; relay its reason and stop.

Two notes for its conflict resolution:

- A conflict in `spec_dd/1. next/roadmap.md` means two specs finished close together: it is one
  row per spec, so keep both sides' removals and status changes, and both sides' bullet edits in
  "Ready to start" and "Needs work on main first".
- A PR that was squash-merged on GitHub replays as conflicts, because the replayed commits are not
  patch-identical to the squash. The rebase returns `blocked`; the human fix is to point the branch
  at `origin/main` (the content is already there) and re-run. Do not automate that.

# Step 0.5: Main-worktree preflight

Resolve `PLUGINS_ROOT` the way `pre_step_rebase.md` Step 3 does. The script path is
`<PLUGINS_ROOT>/claude_plugins/sdd/scripts/land_on_main.sh`; when `PLUGINS_ROOT` is `.`, write it as
`claude_plugins/sdd/scripts/land_on_main.sh` with no `./` prefix, so it matches the project's allow
entry.

```
<script-path> sync
```

The script fetches `origin/main`, finds the worktree that has `main` checked out, refuses if that
worktree has tracked changes or a merge, rebase, cherry-pick, revert or bisect in flight, and
otherwise makes local `main` equal `origin/main` (pushing when it is ahead, fast-forwarding when it
is behind). It never touches untracked files.

- exit 0 → continue.
- any other exit → `status: blocked · reason: <the script's output, verbatim>`. Stop.

Running this before anything is committed means a parked operation on `main` is found before the
branch is touched, and it is what keeps Step 7 from needing a second rebase when local `main` was
ahead of `origin`.

# Step 1: Front-end QA

Only when Step 0 reported `rebased: yes` and there is a `3. frontend_qa.md` for this spec (inside
`spec_dd/2. in progress/{branch name}/`):

- summarise what the rebase brought in
- say whether you think the frontend_qa should be run again
- only if you think it should, ask the user for confirmation before moving forward

The rebase command has already run the test suite and pre-commit; there is nothing to re-run here.

# Step 2: Tear down any per-worktree resources

The teardown step (e.g. dropping a per-branch dev database) is project-specific and configured, not hard-coded into the `sdd` plugin.

Read `.claude/sdd/config.md` (and `.claude/sdd/config.local.md` if it exists — its values take precedence). Under the **Worktree Scripts** section, look at the **Teardown script** value:

- If **Teardown script** is a non-blank path, run that script now.
- If it is blank, or the config file / section is absent, skip this step — this project has no per-worktree teardown step.

# Step 3: Update the todo list

Delegate to `sdd:sdd-mechanic`: invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory (still under `spec_dd/2. in progress/…/` at this point)
- `tick:"Run `/sdd:finish_worktree`"` (a unique substring; the item's wording has changed over time)

No new items to add.

# Step 4: Move the spec to done

Delegate to `sdd:sdd-mechanic`: move the current spec directory from `in progress` to `done` and name it appropriately with the current date and time.

The spec directory should be named like this:

```
yyyy-mm-dd_HH:MM_{spec title}
```

# Step 4.5: Update the spec roadmap

Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/commands/protected/update_roadmap.md` and
follow its steps with `<roadmap-path>`: `spec_dd/1. next/roadmap.md` and `remove:"<spec directory
name>"`. If there is no roadmap the helper returns `ok` and nothing happens.

If the helper reports `effort retired: <parent path>`, this spec was the last of a cut effort.
Delegate a second mechanic run: move that parent directory to `spec_dd/3. done/` named the same way
as Step 4, `yyyy-mm-dd_HH:MM_{parent directory name}`. The archived `spec-order.md` the helper wrote
travels with it.

# Step 5: Tidy Claude project settings

Invoke the `update-claude-project-settings` skill to promote any useful permissions accumulated in `.claude/settings.local.json` to the shared `.claude/settings.json`, and clean up redundant entries in the project settings.

# Step 6: Commit and push

Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/resources/commit_and_push.md` and follow its
steps with `<summary>`: `close out the worktree`. Tell it to stage the moved spec directory, the
`todo.md` inside it, `spec_dd/1. next/roadmap.md` and any retired parent directory from Step 4.5,
and any `.claude/settings.json` change from Step 5.

# Step 7: Land on main

1. **PR guard.** `gh pr view <branch> --json number,state,reviewDecision`. No pull request, or
   `MERGED` → continue. `OPEN` with `reviewDecision` of `CHANGES_REQUESTED` →
   `status: blocked · reason: PR #<n> has changes requested`. `OPEN` otherwise → continue: the
   human ticked the approval item before this command ran, and the fast-forward push closes the
   PR as merged. `gh` missing or not logged in → say so and continue; the fast-forward is what
   protects `main`, not the PR.

2. **Land.**

   ```
   <script-path> land
   ```

   The script re-runs the Step 0.5 checks, then pushes `HEAD` to `origin/main` as a fast-forward
   (never with force) and fast-forwards the main worktree to what `origin` now holds. A rejected
   push changes nothing anywhere.

3. **exit 7** → `origin/main` moved after Step 0. Read the `Rebase command` value from
   `.claude/sdd/config.md` (and `.claude/sdd/config.local.md`, whose values take precedence) under
   `## Rebase Hooks`, exactly as `pre_step_rebase.md` Step 1 does, follow that file once, then run
   `<script-path> land` again. Do not re-run the whole pre-step rebase: the spec directory is now
   under `3. done/`, so its skip rule would return early, and an upstream-change review is
   meaningless for a finished spec. A second exit 7 → `status: blocked · reason: origin/main keeps
   moving; re-run when it settles`.

4. **exit 3, 6 or 8** → `status: blocked · reason: <the script's output, verbatim>`. The close-out
   commits are already on the branch and pushed, so re-running this command later picks up here:
   Steps 3 to 6 find nothing left to do.

5. **exit 0** → delete the branch's backup ref if the rebase left one:

   ```bash
   git show-ref --verify --quiet refs/heads/rebase-backup/<branch>
   ```

   If that succeeds, `git branch -D rebase-backup/<branch>`. It is deleted here rather than earlier
   because the retry in item 3 recreates it.

# Step 8: Verify and report

```
git status --porcelain
```

Must be empty in this worktree; anything else is `status: failed` naming the files. The script's
own post-landing check has already confirmed the main worktree is clean and at the landed commit.

Report:

- the landed commit and the main worktree path the script printed
- the PR number and state from Step 7, if any
- whether the item 3 retry rebase was needed
- that the worktree directory and the branch still exist; removing them is the `(user)` item that
  follows in `todo.md`

## Return contract

```
status: ok|failed|blocked · landed: yes|nothing|no · main: <sha> · reason: <short>
```

`landed: nothing` means the branch was already contained in `origin/main` (for example, a PR
merged on GitHub with a merge commit) and there was nothing left to push.
