# Proving the chains: throwaway walkthrough

Covers `spec_dd/2. in progress/sdd-improvements-combine-steps/1. spec.md` § Testing, items 1–11.
Everything here lives on local branches named `sdd-chain-throwaway*`. Never merge or push them.

`W=/home/sheena/workspace/lms/freedom-ls-worktrees` below.

## How the throwaway is built

- `sdd-chain-throwaway` (worktree `$W/sdd-chain-throwaway`) is the **launch branch**. It plays
  `main`'s part: `main` + one squashed `qa: feature under test` commit + this fixtures commit.
  It is squashed because `implement_plan`'s resume scan reads `[batch N]` subjects in
  `origin/main..HEAD`, and the real feature branch already carries `[batch 1]`–`[batch 13]`.
- Every `sdd-chain-throwaway*` branch has `branch.<name>.remote = .`, so the SDD commit helper's
  `git push` pushes to the local repo (a no-op) and nothing reaches GitHub. The exception is
  `make_pr_quickly`, which runs `git push -u origin HEAD` by name (step 7).
- Three ideas sit in `spec_dd/1. next/`:
  - `sdd-chain-throwaway-plain`: no design, two open questions. Feeds tests 1, 2, 5–10.
  - `sdd-chain-throwaway-design`: a real `design_prompt.md`. Test 3.
  - `sdd-chain-throwaway-stop`: a stray `todo.md` (the mechanic blocks) and a design link to a
    project that does not exist (the design hook fails). Tests 4 and 11.
- Fixture plans here: `plan_parallel.md`, `plan_conflict.md`, `plan_older.md`, and
  `frontend_qa.md` (a two-check smoke pass).

## Step 0: once, before any `/sdd:start`

`/sdd:start`'s worktree mechanic runs `git worktree add <name>` from the bare repo, which
branches off the bare repo's `HEAD` (`main`). Point it at the launch branch for the three start
runs, and put it back afterwards (step 3 ends with that):

```bash
git -C $W symbolic-ref HEAD refs/heads/sdd-chain-throwaway
```

While it points there, any other session that runs `/sdd:start` would branch off the throwaway.
Keep the window short.

Launch from the launch worktree so the plugins under test load:

```bash
cd $W/sdd-chain-throwaway && ./claude.sh
```

## Step 1: start chain, no design (tests 1, 2)

```
/sdd:start spec_dd/1. next/sdd-chain-throwaway-plain
```

Watch for:

- The worktree mechanic runs **in the background** while the two open questions from the idea
  are asked. No question waits for the Setup script to finish.
- The session ends **inside** `$W/sdd-chain-throwaway-plain` (`! pwd`, `! git branch --show-current`).
- After `1. spec.md` is written, only the Step 7 review batch asks anything.

Then check:

```bash
git log --oneline -3 sdd-chain-throwaway            # only the move commit on top of the fixtures commit
git log --oneline sdd-chain-throwaway..sdd-chain-throwaway-plain   # answers.md, research, spec
cat "spec_dd/2. in progress/sdd-chain-throwaway-plain/answers.md"   # one line per question asked
```

**Test 2 (spike)**, in the same session, ask: "Print the absolute paths you resolve for
`.claude/worktrees/`, `.claude/settings.json` and `CLAUDE.md`, and read `.claude/settings.json`'s
`worktree.baseRef`." All three must be under `$W/sdd-chain-throwaway-plain`.

Tag the state the implement tests reset to:

```bash
git -C $W/sdd-chain-throwaway-plain tag throwaway/spec-written
```

## Step 2: start chain with a design (test 3)

New session from the launch worktree (`cd $W/sdd-chain-throwaway && ./claude.sh`):

```
/sdd:start spec_dd/1. next/sdd-chain-throwaway-design
```

- If you are logged in to Claude Design, there is no login question: the design is read.
- To test the refused login, run `/design-logout` first if your build has it (otherwise skip that
  half). Then pick "Register the design without reading it". `design.md`'s coverage table must
  read "not yet read" and the chain must carry on into the spec.
- `design.md` must be committed **before** the research workers spawn
  (`git log --oneline` in the worktree as soon as the workers start). The idea's Resources
  bullet must point at `design.md`.
- You may press Esc once the research workers start. Step 6 picks the run up again.

## Step 3: chain stop (test 4)

New session from the launch worktree:

```
/sdd:start spec_dd/1. next/sdd-chain-throwaway-stop
```

- The todo mechanic returns `blocked` on the stray `todo.md`. You are asked; answer overwrite.
  The chain continues.
- The design project does not exist, so `/sdd:register_design` fails and the run ends.
- The report gives the next command: `/sdd:register_design <spec-dir>/design_prompt.md`, to be
  run from inside `$W/sdd-chain-throwaway-stop`.
- `answers.md` is committed: `git -C $W/sdd-chain-throwaway-stop log -1 --stat`.

That is the last `/sdd:start`. Put the bare `HEAD` back:

```bash
git -C $W symbolic-ref HEAD refs/heads/main
```

## Step 4: batch wave + QA chain (tests 5, 9)

From here on, launch in the plain worktree: `cd $W/sdd-chain-throwaway-plain && ./claude.sh`.

Install the fixture yourself (resets the branch to the tag; history of a throwaway only):

```bash
cd $W/sdd-chain-throwaway-plain
S="spec_dd/2. in progress/sdd-chain-throwaway-plain"; F=spec_dd/sdd-chain-throwaway-fixtures
git reset --hard throwaway/spec-written
cp $F/plan_parallel.md "$S/2. plan.md"; cp $F/frontend_qa.md "$S/3. frontend_qa.md"
sed -i 's/^- Parallel batches:.*/- Parallel batches: 2/' .claude/sdd/config.md
git add "$S" .claude/sdd/config.md && uv run git commit -m "sdd-chain-throwaway-plain: install plan_parallel"
```

Run `/sdd:implement_plan`. In a second terminal during the batch wave:

```bash
git -C $W/sdd-chain-throwaway-plain worktree list | grep .claude/worktrees   # two entries
uv run python -m dev_db.stale_dbs
```

Afterwards:

- `git log --oneline throwaway/spec-written..HEAD` shows `[batch 1]` and `[batch 2]` (cherry-picked,
  no merge commit), then the QA commits.
- `git worktree list | grep .claude/worktrees` and `git branch --list 'worktree-*'` print nothing;
  `uv run python -m dev_db.stale_dbs` lists no batch database.
- Test 9: `qa_report.md` is in the spec directory and the `/sdd:do_qa` todo item is ticked. Then run
  `/sdd:do_qa` again by hand: it works as before (pre-step rebase included).

## Step 5: conflict (test 6)

Reset and install `plan_conflict.md` as in step 4, leaving out the `cp` of `frontend_qa.md`
(the tag has no QA file, so none is installed).

Plan review: in a fresh session ask, "Review `spec_dd/2. in progress/sdd-chain-throwaway-plain/2. plan.md`
against the `parallel_safety` row of `claude_plugins/sdd/resources/plan_review_dimensions.md` and
say whether it passes." It must flag slices 1 and 2 (same `Touches:`, no `Builds on:` path).

Override it: run `/sdd:implement_plan`. Expect: both workers create `freedom_ls/base/display_format.py`;
the second cherry-pick conflicts and is aborted; batch 2 re-runs alone in the feature worktree before
any further batch wave; the run ends with both functions in the file. The Step 6 report says
"no QA plan" (this also proves that branch).

## Step 6: resume (test 7)

Reset and install `plan_parallel.md` without the QA file. Then simulate a session that died
mid-wave, after one worker committed:

```bash
cd $W/sdd-chain-throwaway-plain
git worktree add -q .claude/worktrees/agent-sim1 -b worktree-agent-sim1 HEAD
cd .claude/worktrees/agent-sim1 && mkdir -p freedom_ls/health/tests
printf 'def format_duration(seconds: int) -> str:\n    if seconds < 0:\n        raise ValueError("seconds must not be negative")\n    hours, remainder = divmod(seconds, 3600)\n    return f"{hours}h {remainder // 60:02d}m"\n' > freedom_ls/health/durations.py
printf 'from freedom_ls.health.durations import format_duration\n\n\ndef test_hours_and_minutes() -> None:\n    assert format_duration(3720) == "1h 02m"\n' > freedom_ls/health/tests/test_durations.py
git add freedom_ls/health && git commit -q --no-verify -m "[batch 1] add format_duration to health (simulated worker)"
cd $W/sdd-chain-throwaway-plain
git worktree add -q .claude/worktrees/decoy -b worktree-decoy HEAD
git worktree list | grep .claude/worktrees
```

(Or do it for real: run step 4 and press Esc once one worker's `[batch …]` commit shows in
`git log --all --oneline | grep '\[batch'`. Background workers may keep running after Esc, so the
simulation is the reliable form.)

Run `/sdd:implement_plan`. Expect: `[batch 1]` cherry-picked from `agent-sim1`; one permission
prompt for `cd <path> && <Teardown script>` (accept it); `agent-sim1` and its branch removed;
`decoy` left alone and named in the summary; batch 2 runs. Then remove the decoy:

```bash
git worktree remove .claude/worktrees/decoy && git branch -D worktree-decoy
```

## Step 7: older plan (test 8)

Reset and install `plan_older.md` without the QA file. Run `/sdd:implement_plan`. Expect no
`.claude/worktrees/` entry at any point, batch 1 then batch 2 in the feature worktree, and the same
commit shape as before batch waves existed.

## Step 8: document chain (test 10)

Any state with an implemented plan works (step 4's is best). Add this line to the plain spec's
`todo.md`, right after the `/sdd:document` item, and commit it:

```
- [ ] (cmd) Write `notes.md` in the spec directory listing `format_duration` and `format_score` with one example each
```

Decide first: `/sdd:document` ends in `make_pr_quickly`, which runs `git push -u origin HEAD` and
`gh pr create`. That publishes `sdd-chain-throwaway-plain` to GitHub and opens a real PR against
`main`. Either accept it and close it straight after
(`gh pr close sdd-chain-throwaway-plain --delete-branch`), or accept the `gh` error as the result
and check only that the report carries it and ticks nothing.

Run `/sdd:document`. Expect: `notes.md` committed as `sdd-chain-throwaway-plain: <item text>`, the
item ticked, a PR URL (or the `gh` error), and the PR item ticked only with a URL. Then untick the
extra item by hand, commit, and run `/sdd:document` again: it ticks the item **without** a second
`notes.md` commit.

## Step 9: standalone commands (test 11)

- In `$W/sdd-chain-throwaway-stop`: copy the real prompt over the broken one
  (`cp "spec_dd/2. in progress/design_educator-interface-bulk-action/design_prompt.md" "spec_dd/2. in progress/sdd-chain-throwaway-stop/"`),
  commit, and run `/sdd:register_design "spec_dd/2. in progress/sdd-chain-throwaway-stop/design_prompt.md"`.
  It behaves as before: asks about `/design-login` itself if needed, writes and commits `design.md`.
- Same worktree: `/sdd:spec_from_idea "spec_dd/2. in progress/sdd-chain-throwaway-stop/idea.md"`.
  It runs its pre-step rebase, reads `answers.md`, and does not re-ask the question in it.
- `/sdd:do_qa` by hand: done in step 4.

## Cleanup

Run from `$W/sdd-improvements-combine-steps`. Each worktree's Teardown drops its dev databases:

```bash
git -C $W symbolic-ref HEAD refs/heads/main
for n in sdd-chain-throwaway-plain sdd-chain-throwaway-design sdd-chain-throwaway-stop sdd-chain-throwaway; do
  (cd $W/$n && .claude/fls-dev/scripts/dev_db_delete.sh)
  git worktree remove --force $W/$n
  git branch -D $n
  git config --remove-section branch.$n
done
git tag -d throwaway/spec-written
git ls-remote --heads origin 'sdd-chain-throwaway*'   # must print nothing
uv run python -m dev_db.stale_dbs
```

Then tick the `(user)` item in this spec's `todo.md`, noting any test that failed.
