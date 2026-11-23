---
description: Close out the current worktree: rebase, archive the spec, land the close-out on main, sync the main worktree and remove the feature worktree
allowed-tools: Bash, Read, Glob, Skill, Agent, AskUserQuestion
---

This command finishes a spec's worktree. It runs on the feature branch: it rebases the branch,
makes the close-out commits there (spec directory to done, roadmap row removed, project settings
tidied), lands the branch on `main` by fast-forward, brings the main worktree up to date, then removes the
feature worktree and its branch. It runs at **depth 0** and delegates mechanical steps to the `sdd:sdd-mechanic` agent.

Two rules hold throughout:

- Conflicts are only ever resolved here, in the feature worktree. `main` only moves by
  fast-forward, only to a commit `origin` already holds.
- The main worktree is never cleaned up from this command. Never run `merge --abort`, `stash`,
  `reset` or `checkout` there. The one exception is "A dirty main worktree" below: with the user's
  consent, this command commits the named paths in the main worktree and pushes `main`. Uncommitted
  work there stops this command only when it touches a file the landing changes, or when an
  operation is in progress; then say what is parked, and a human decides what it means. Any other
  uncommitted work on `main` is carried across the fast-forward untouched and is no reason to stop
  or to ask.

```
git branch --show-current
```

On `main` or `master`, stop: this command runs in a feature worktree only.

Never look at the pull request: not whether it is approved, reviewed, open or merged. No `gh`
call, and no todo item about the PR, stops or delays this command.

# Step 0: Pre-step rebase

Read `claude_plugins/sdd/commands/protected/pre_step_rebase.md` and follow its steps with `<tier>`:
`none`. The tests run once, in Step 1. Any status other than `ok` is this command's own status;
relay its reason and stop.

A conflict in `spec_dd/1. next/` or in the spec's own directory resolves by the list in
`claude_plugins/sdd/resources/rebase_auto_resolve.md`.

A PR that was squash-merged on GitHub replays as conflicts, because the replayed commits are not
patch-identical to the squash. The rebase returns `blocked`; the human fix is to point the branch
at `origin/main` (the content is already there) and re-run. Do not automate that.

## Rebase results

Every rebase this command runs, here and in Step 7's loop, is read the same way:

- `blocked` on a conflict outside the auto-resolve list → `status: blocked`, with its reason.
- `failed · reason: push rejected: stale lease` → `git fetch origin`, then a pass of Step 7's
  main-moved loop with blocker `stale lease`.
- `blocked · reason: force-push needed: <command>` →
  `status: paused · reason: force-push needed: <command>`. Re-running this command after the user
  runs that command continues: the rebase finds the branch up to date.

Any `paused` return first adds its item to `todo.md`, wherever the spec directory is at that point
(`spec_dd/2. in progress/` or `spec_dd/3. done/`). Delegate to `sdd:sdd-mechanic`: read
`claude_plugins/sdd/commands/protected/update_todo.md` and follow its steps with `<todo-path>` and
`add_first:"user|<what to do>, then re-run `/sdd:finish_worktree`"`.

# Step 0.5: Main-worktree preflight

Resolve `PLUGINS_ROOT` by `pre_step_rebase.md`'s "`PLUGINS_ROOT` rule". The script path is
`<PLUGINS_ROOT>/claude_plugins/sdd/scripts/land_on_main.sh`; when `PLUGINS_ROOT` is `.`, write it as
`claude_plugins/sdd/scripts/land_on_main.sh` with no `./` prefix, so it matches the project's allow
entry.

```
<script-path> sync
```

The script makes local `main` equal `origin/main` (pushing when it is ahead, fast-forwarding when
it is behind), and refuses when the main worktree has a merge, rebase, cherry-pick, revert or bisect
in flight or an uncommitted change to a file the incoming commits change. It prints `carried: <n>`
for uncommitted tracked files the incoming commits leave alone; those do not block and need no
mention until Step 8.

- exit 0 → continue. Keep any `synced: pushed` and `pushed:` lines for Step 8.
- exit 4 (an uncommitted change on `main` to a file the landing changes) → "A dirty main
  worktree" below.
- any other exit → `status: blocked · reason: <the script's output, verbatim>`. Stop.

# Step 1: Checkpoint tier

The checkpoint run: with a passing full run on record, it tests only what changed since that run;
with none, it runs `full`.

1. Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/commands/protected/run_test_tier.md` and
   follow it with `<tier>`: `checkpoint` as far as its "Resolve the checkpoint tier" step, and
   return the `tier:`, `diff:` and `why:` lines. `none` → the report line is
   `tier: none · summary: <why>`; nothing else runs.
2. `targeted` or the full tier → rebuild generated assets ("Pre-test rebuild" below), then
   delegate to `sdd:sdd-mechanic`: follow `run_test_tier.md` with the tier and `<diff>` as
   resolved, returning the report line and any failing test names. Failing tests follow the
   failure rule below and "Flaky tests".
3. Keep every report line for Step 8.

A failure is `status: failed · reason: checkpoint run failed before landing: <tests>`. Nothing is
moved or landed until a human fixes it, except for a flaky test and an obvious failure, both
handled below. A rebased branch has also passed pre-commit; there is nothing to re-run for that.

## Pre-test rebuild

Read `Pre-test rebuild` under `## Test Hooks` in `.claude/sdd/config.md` (`config.local.md` wins).
A non-blank path: run it from the project root. A non-zero exit is
`status: failed · reason: pre-test rebuild failed: <its output>`. Blank, or the key absent: skip
the rebuild.

## Flaky tests

When a checkpoint run, in Step 1 or in Step 7's loop, reports failing tests:

1. Delegate to `sdd:sdd-mechanic`: run each failing test on its own, by node ID, three times, as the
   tier definition's single test run, and return the pass count per test. A test with 0 passes goes
   to "Obvious failures" below.
2. A test with at least one pass is flaky. Handle the flaky tests one at a time, because they share
   the worktree and its database. For each, spawn a `general-purpose` sub-agent with this brief,
   every input written into the prompt: the test's node ID, its failure output, and, when
   `Flaky test guide` under `## Test Hooks` (read the way "Pre-test rebuild" reads its key) is a
   non-blank path, that path to read first. Its rules:
   - Find and fix the root cause on the current branch.
   - Never skip, delete, mark or retry-wrap the test to get a pass.
   - Prove the fix with 10 consecutive passing runs of the tier definition's single test run.
   - Commit as `fix flaky test <test id>`.
   - Return `status: ok · commit: <sha>` or `status: failed · diagnosis: <one line>`.
3. A `failed` return gets one more sub-agent, briefed the same way plus the first diagnosis. A second
   `failed` is `status: failed · reason: flaky test <id> not fixed: <diagnosis>`.
4. After the fixes, `git push`, then follow the run that failed again from its start. A test already
   fixed once that fails again is a real failure. Keep each fix's commit for Step 8.

## Obvious failures

A test with 0 passes in "Flaky tests" step 1 gets one look here, at depth 0, before it becomes
`status: failed`. Read the test and its failure output. The failure is obvious when all of these
hold:

- The rebase brought the cause together: one side changed a name, label, path, import, selector or
  expected value, and a test from the other side still uses the old one. `git log origin/main..HEAD`
  and `git log <old-base>..origin/main` on the files involved show which side made each change.
- Both sides' intent is clear from their commits, and the fix keeps both: the test still checks what
  it was written to check, against the current name.
- The fix is a few lines, in the test or in the reference it holds, and changes no behaviour either
  side meant to ship.

Anything else is a real failure: report it as above. That includes a failure that needs a judgement
about which side's behaviour is right.

For an obvious failure:

1. Make the fix. Never skip, delete, mark or loosen the test to get a pass.
2. Run the test on its own, by node ID, as the tier definition's single test run. A failure means
   the diagnosis was wrong: undo the edit and report it as a real failure.
3. Commit as `fix <test id> after rebase`, with a body naming the change on each side, then
   `git push`.
4. Follow the run that failed again from its start, as "Flaky tests" step 4 does. A test already
   fixed once that fails again is a real failure. Keep each fix's commit for Step 8.

# Step 2: Tear down any per-worktree resources

Read **Teardown script** under `## Worktree Scripts` in `.claude/sdd/config.md` (`config.local.md` wins):

- A non-blank path: run that script now.
- Blank, or the config file / section absent: skip this step; this project has no per-worktree teardown.

Then remove leftover batch worktrees, taking names the way `implement_plan.md` Step 2
"Names from git" says: for each `git worktree list` path under this checkout's
`.claude/worktrees/` whose branch holds a `[batch …]` commit, run the Teardown script inside it
(`cd <path> && <script>`; skip when the script is blank), then
`git worktree remove --force --force .claude/worktrees/<name>` and `git branch -D <branch>`. Report
each one in Step 8.

# Step 3: Update the todo list

Delegate to `sdd:sdd-mechanic`: invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory (still under `spec_dd/2. in progress/…/` here)
- `tick:"Run `/sdd:finish_worktree`"` (a unique substring; the item's wording has changed over time)
- `tick:"Remove the worktree and delete the branch"` (older todo lists carry this `(user)` item; Step 9
  does it now; not found is fine)

No new items to add.

# Step 4: Move the spec to done

Delegate to `sdd:sdd-mechanic`: move the current spec directory from `in progress` to `done`, named with the current date and time:

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

Invoke the `update-claude-project-settings` skill to promote useful permissions from `.claude/settings.local.json` to the shared `.claude/settings.json` and clean up redundant entries.

# Step 6: Commit and push

Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/resources/commit_and_push.md` and follow its
steps with `<summary>`: `close out the worktree`. Tell it to stage the moved spec directory, the
`todo.md` inside it, `spec_dd/1. next/roadmap.md`, `spec_dd/1. next/priority.md`,
`spec_dd/1. next/roadmap_diagrams/` and any
retired parent directory from Step 4.5,
and any `.claude/settings.json` change from Step 5.

# Step 7: Land on main

1. **Land.**

   ```
   <script-path> land
   ```

   The script re-runs the Step 0.5 checks, then pushes `HEAD` to `origin/main` as a fast-forward
   (never with force) and fast-forwards the main worktree. A rejected push changes nothing anywhere.

2. **exit 7** → `origin/main` moved after Step 0.5. Run the main-moved loop below.

3. **exit 4** → "A dirty main worktree" below.

4. **exit 3, 6 or 8** → `status: blocked · reason: <the script's output, verbatim>`. The
   close-out commits are already on the branch and pushed, so re-running this command later picks
   up here: Steps 3 to 6 find nothing left to do.

## The main-moved loop

A pass is one turn of the loop. A pass is entered with a blocker: `origin/main` (exit 7 from
`land`), `stale lease` (a rebase reported it) or `main worktree commit` (the main worktree commit
below was pushed).

```
blocker = none; in_a_row = 0
on each pass, entered with its <blocker>:
    in_a_row = in_a_row + 1 if <blocker> == blocker else 1; blocker = <blocker>
    # the fifth occurrence of one blocker is not retried
    if in_a_row == 5: status: blocked · reason: <blocker> moved 5 times in a row
    follow the Rebase command (## Rebase Hooks) with <tier>: none and <auto-resolve>:
        the list from rebase_auto_resolve.md, <own-spec-dir> = the spec's directory under
        spec_dd/3. done/ once Step 4 moved it, else its directory under spec_dd/2. in progress/
    map its result as Step 0's "Rebase results" does
    # nothing lands before the close-out commits
    entered before Step 7 (from Step 0, or from Step 0.5's exit 4): leave the loop and continue
        at Step 0.5
    follow the checkpoint run (below)
    <script-path> land        → exit 0 leaves the loop; exit 7 is the next pass
```

Read the `Rebase command` value under `## Rebase Hooks` exactly as `pre_step_rebase.md` Step 1 does.
With `origin/main` as the blocker the reason reads `origin/main moved 5 times in a row`.

Do not use the pre-step rebase here: it skips a spec already under `3. done/`, and no
upstream-change review runs for a finished spec. After the loop's exit 0, any exit other than 7 is
handled as items 3 and 4 above.

### The checkpoint run

Follow Step 1's checkpoint run. The last passing full run, usually `implement_plan` Step 3, wrote
the full-run record, so a pass tests only what the rebase brought in.

## A dirty main worktree

Followed on exit 4 from `sync` (Step 0.5) or `land` (Step 7). `<paths>` are the script's `dirty:`
lines and `<main>` is its `main-worktree:` line.

1. Ask with `AskUserQuestion`: "The main worktree has uncommitted changes to files this landing
   changes: `<paths>`. Another process may be working on them. Committing them here also pushes
   that commit to `origin/main`." Options: "Commit and push them to main for me", "I'll commit
   main, then continue".
2. **I'll commit main, then continue** → return
   `status: paused · reason: main worktree has uncommitted changes: <paths>`.
3. **Commit and push them to main for me** → commit exactly those paths, as their own commit. The
   message is fixed text, so the shell expands no branch name or path, and each path is its own
   single-quoted argument after `--`:

   ```
   git -C '<main>' commit --only -m 'wip: uncommitted changes on main before a landing' -- '<path>' ['<path>' ...]
   git -C '<main>' pull --rebase origin main
   ```

   `--only` commits the named paths and leaves every other change in the main worktree as it is.
   - A hook rejects the commit → `paused` with its output. Never `--no-verify`.
   - Git refuses to start `pull --rebase` because the main worktree holds other uncommitted
     tracked changes → `status: paused · reason: main worktree commit <sha> made; other
     uncommitted changes there block the rebase onto origin/main: <git's message>`. The commit
     stays on local `main`.
   - `pull --rebase` stops on a conflict → `git -C '<main>' rebase --abort`, then
     `status: paused · reason: main worktree commit conflicts with origin/main: <paths>`. The
     commit stays on local `main`.
4. Otherwise `git -C '<main>' push origin main`, record "main-worktree commit <sha>: <paths>" for
   Step 8, and enter the main-moved loop with blocker `main worktree commit`. A pass entered before
   Step 7 rebases and continues at Step 0.5; a pass entered from Step 7 follows the checkpoint run
   and lands.

# Step 8: Verify and report

```
git status --porcelain
```

Must be empty in this worktree; anything else is `status: failed` naming the files.

Report:

- the landed commit and the main worktree path the script printed
- the number of passes of the main-moved loop, and each auto-resolved conflict path with its side
- the main-worktree commit, when one was made: "main-worktree commit <sha>: <paths>"
- the script's `synced: pushed` and `pushed:` lines, as "main pushed"
- every test report line, from Step 1's checkpoint run and from each checkpoint run of the
  main-moved loop
- each flaky test fix, with its commit
- each obvious-failure fix, with its commit
- the `carried:` count, when the script printed one
- the leftover batch worktrees removed, if any
- Step 9's result: the worktree and branch removed, or why they were kept

# Step 9: Remove the feature worktree

Only after Step 8 passed with `status: ok` and `landed: yes` or `landed: nothing`. Any other status
keeps the worktree, so a re-run can pick up where it stopped.

`<main>` is the script's `main-worktree:` path, `<wt>` is `git rev-parse --show-toplevel` and
`<branch>` is `git branch --show-current`, all read here before anything is removed. Run every
command from `<main>` with `git -C`, because this session's directory is the worktree being removed:

```
git -C '<main>' worktree remove --force '<wt>'
git -C '<main>' branch -d '<branch>'
```

`--force` is what lets git remove a worktree that holds initialised submodules; without it git
refuses with "working trees containing submodules cannot be moved or removed". Step 8 already proved
the worktree has no uncommitted or untracked work, so the force discards nothing. Step 2 already ran
the Teardown script.

`branch -d`, not `-D`: `main` holds the branch after a landing, so git deletes it; a refusal means
`main` does not have it, so report git's message and keep the branch. A failed `worktree remove`
is reported verbatim too; it does not change the status. The remote branch is left as it is.

After the removal, run nothing more in this session's old directory.

## Return contract

```
status: ok|failed|blocked|paused · landed: yes|nothing|no · main: <sha> · worktree: removed|kept · reason: <short>
```

`landed: nothing` means the branch was already contained in `origin/main` (for example, a PR
merged on GitHub with a merge commit) and there was nothing left to push.
