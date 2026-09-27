---
name: implement_plan
description: Execute the implementation plan in resilient batches.
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, Skill, Agent
---

# Executing Plans

This command runs at **depth 0** (the main thread) and orchestrates batch sub-agents.

## Step 0: Pre-step rebase

Read `claude_plugins/sdd/commands/protected/pre_step_rebase.md` and follow its steps (skip this
when `/sdd:next` says it already ran this turn).

## Step 1: Read and Review the Plan

1. Read the plan file
2. Before implementing anything, check for:
   - Missing or ambiguous steps
   - Steps that depend on things not covered earlier in the plan
   - Unclear success criteria
   - Missing dependencies or prerequisites
3. If you find issues: raise them with the user before starting
4. If the plan is clear: proceed to Step 2

## Step 2: Batch and Execute (resilient)

### Testing skills

Before spawning anything, read `## Testing Skills` from `.claude/sdd/config.md`, then from
`.claude/sdd/config.local.md`, whose values win. Blank, or the file or section absent, means the
list is empty. When it is not empty, every brief for an implementer, reviewer, boy-scout or fix
agent opens with:

> Before anything else, invoke the `Skill` tool for each of: <ids>, in order.

Make one batch per vertical slice in the plan, in the plan's order. A slice runs end to end through every layer its behaviour needs (e.g. "learner can see their deadline on the course page": field + migration + view + template + tests), so never regroup the plan's steps by layer ("all the models", then "all the views"). A small shared-groundwork step the plan places before a slice goes into that slice's batch. If the plan is not ordered as slices, group its steps into the thinnest batches that each deliver working, tested behaviour. Assign each batch a deterministic completion marker per the commit-subject grammar below. A batch owns several commits, and `[batch N]` is only the implementation's; the batch is finished at `[batch N record]`, or at `[batch N]` when `## Testing Skills` is blank.

### Commit-subject grammar

Every commit a batch produces carries its number:

| Subject | Made by |
| --- | --- |
| `[batch N] <summary>` | implementer |
| `[batch N review-fix] <summary>` | fix agent, for a mechanical review finding |
| `[batch N boy-scout] move <old-path> -> <new-path>` | boy-scout; exactly one file, no content change |
| `[batch N boy-scout] edit <summary>` | boy-scout; the edit that goes with the move before it |
| `[batch N boy-scout] edit split <path> into <a>, <b>` | boy-scout; a split |
| `[batch N boy-scout] edit drop <app> test dependency on <other-app>` | boy-scout; one cross-app dependency removed |
| `[batch N bug-fix] <summary>` | implementer, for a flagged item answered "fix it now" |
| `[batch N flag-note] <path>` | depth 0, the "not a bug" comment |
| `[batch N record] <summary>` | depth 0 via `sdd:sdd-mechanic`: `boy_scout_record.md` plus any follow-up files; always the batch's last commit |
| `[final review-fix] <summary>` | fix agent, for a finding of the final review |

Matching `[batch N]` needs the closing bracket straight after the number, so no follow-on commit reads as the implementation's commit. Resume, the budget and the scope check read subjects only.

The boy-scout's budget is counted fresh each time from `git log`, never carried in memory:

```bash
LOG=$(git log --format=%s "$(git merge-base origin/main HEAD)..HEAD")
moved=$(grep -cE '^\[batch [0-9]+ boy-scout\] (move |edit split )' <<<"$LOG" || true)   # cap 3
dropped=$(grep -cE '^\[batch [0-9]+ boy-scout\] edit drop ' <<<"$LOG" || true)          # cap 1
```

Remaining budget is the cap minus the count, floored at 0. The boy-scout still runs at zero
budget, so it can report deferred items.

### Touched files

Touched files are the paths the `[batch N]` commit and its `[batch N review-fix]` commits add or modify, at their current paths. The review and the boy-scout work over this set:

```bash
N=<batch-number>
BASE=$(git merge-base origin/main HEAD)
git log --reverse --format='%H%x09%s' "$BASE..HEAD" \
  | while IFS=$'\t' read -r sha subject; do
      case "$subject" in
        "[batch $N] "*|"[batch $N review-fix] "*)
          git diff-tree --no-commit-id -r -M --name-only --diff-filter=AMR "$sha" ;;
      esac
    done | sort -u
# keep only paths that still exist in the working tree (their current paths)
```

This is the same rule the scope-check script uses for its own allowed set, kept separate on purpose: this one runs over `BASE..HEAD` and filters to paths that still exist, for a brief; the script takes an as-of-commit snapshot at `<from-ref>` for enforcement. If either rule changes, change both.

**Resume.** Resume reads `git log` subjects, never SHAs, because `pre_step_rebase` rewrites every SHA on each rebase. When `## Testing Skills` is blank:

- `[batch N]` present → skip.
- otherwise → implement it.

When `## Testing Skills` is not blank:

- no `[batch N]` → implement it, then run the follow-ons.
- `[batch N]` but no `[batch N record]` → run the follow-ons only. Reuse `.sdd-work/test_org_review_batch_<N>.md` when it ends `status: ok`; a `[batch N review-fix]` commit means the mechanical fixes have already landed, so don't send them again. Reuse `.sdd-work/boy_scout_batch_<N>.md` the same way when it ends `status: ok`, and give a re-spawned boy-scout's brief the batch's existing `[batch N boy-scout]` commits so it finishes a half-done pair instead of repeating it.
- `[batch N record]` → skip, but first delete any leftover `.sdd-work/test_org_review_batch_<N>.md` and `.sdd-work/boy_scout_batch_<N>.md` by name — an interrupt can land between the record commit and its own deletes.

For each remaining batch, spawn **one implementation sub-agent** via the `Agent` tool with `subagent_type: "sdd:sdd-implementer"`, and pass the per-spawn `model: "sonnet"` parameter so non-interactive batch work runs on a mid-tier model rather than the session model. (The user can override to `model: "opus"` per spawn — or set `CLAUDE_CODE_SUBAGENT_MODEL` — if a batch needs heavier reasoning.) Its brief carries the skill line (when the list from above is not empty), the batch's plan steps verbatim, and the commit subject `[batch N] <summary>`. The TDD, full-suite and commit rules live in the `sdd:sdd-implementer` agent file, which returns a structured status (`status: ok|failed|blocked` · `reason:`).

Committing inside the worker keeps the work and its completion marker **atomic**: a crash between "work done" and "marker written" can't leave an uncommitted batch that the resume scan would wrongly re-run over a dirty tree. Agents whose work is a commit make it themselves; `sdd:sdd-mechanic` makes the bookkeeping commits.

After a batch returns, act on its status:
- `ok` → verify the `[batch N]` commit exists, then run the follow-ons below (skipped when `## Testing Skills` is blank), and move to the next batch once they finish.
- `failed` → reset any partial uncommitted work so the retry starts clean, then retry that batch (≤2 attempts) with the prior error included in the brief.
- `blocked` → gather the listed `needs` via `AskUserQuestion` (legal at depth 0), then re-spawn the batch with the answers.

### Follow-ons

Run these in order after `[batch N]` lands and the suite passes. All of them are skipped when `## Testing Skills` is blank. Record is always last.

#### Review (follow-on 1)

One `sdd:sdd-worker`, spawned per the fan-out recipe as in `plan_from_spec.md` Step 6, writes `.sdd-work/test_org_review_batch_<N>.md`. Skip the spawn when that file exists and ends `status: ok`. Its brief:

- the skill line;
- the touched files, above;
- read the "Dependency table" (`App | Runtime deps | Test-only deps`) in `docs/app_structure.md` directly. If that file is absent, check mirroring only;
- mirroring: check each touched test file's placement against the mirroring rule in the loaded skills;
- dependency direction: for each touched test, conftest or factory file, check its imports of another app, and any fixtures it pulls from a `conftest.py` under another app, against its own app's Runtime deps. A project-wide pytest plugin (`pytest_plugins`, `pytest11`) is infrastructure, not an edge;
- write each finding in this format:

  ```
  - rule: mirroring | dependency-direction
    kind: mechanical | judgement
    file: <path>
    detail: <one line>
    recommendation: <one line, concrete enough to execute>
  ```

  under a `## Findings` heading (`(none)` when empty), then the `status:` footer, in one `Write`.

`failed` → retry up to twice with the prior error in the brief. `blocked` → depth 0 supplies the `needs` from the code, or asks via `AskUserQuestion`, then re-spawns.

#### Review fixes (follow-on 2)

If there are mechanical findings, send them all to one `sdd:sdd-implementer` with the skill line and the subject `[batch N review-fix] <summary>`. It may edit any file the fix needs, for example an app's existing `tests/conftest.py`. Put judgement findings to the user right away, up to four per `AskUserQuestion`, with the reviewer's recommendation as the first option. An answer that needs code takes the same fix path. If the answer accepts a new cross-app edge, the record says so and names `/app_map` as needing a re-run.

#### Boy-scout (follow-on 3)

Skip when no touched file is a test file (under a `tests/` directory, or named `test_*.py` or `conftest.py`) or production code (any other source file); markdown, `docs/` and `spec_dd/` paths count as neither. Otherwise record `FROM_REF=$(git rev-parse HEAD)` and spawn one `sdd:sdd-boy-scout` with the batch number, the touched files, the remaining budget, whether `docs/app_structure.md` exists, and — on a resumed run — the batch's existing `[batch N boy-scout]` commits. Before spawning, note `git status --porcelain`. `failed` → restore modified tracked files with `git restore --staged --worktree <paths>` and delete, by name, any untracked file that was not in the earlier listing, then retry up to twice with the prior error in the brief; its commits stay. `blocked` → as for the review.

#### Scope check (follow-on 4)

Via `sdd:sdd-mechanic`, run `batch_scope_check.sh N <from-ref>`, with the script path resolved as in `pre_step_rebase.md` Step 3. `<from-ref>` is `FROM_REF`; on resume it is the parent of the batch's oldest `[batch N boy-scout]` commit, or `HEAD` when there is none. Exit 1 stops the run and puts the `OUT_OF_SCOPE:` paths to the user. Commits are never reverted automatically. Any other non-zero exit is `failed`.

#### Flagged items (follow-on 5)

Up to four per `AskUserQuestion`. Each question shows `file:line` and why the boy-scout believes it is broken, and puts its recommendation first among three answers:

- "Not a bug": depth 0 writes the boy-scout's drafted comment at the spot, following `code-comments` (it says why the code is correct, never who judged it), and commits `[batch N flag-note] <path>`, staging that one path.
- "Fix it now": one `sdd:sdd-implementer` fixes it test-first, with the skill line and the subject `[batch N bug-fix] <summary>`, before the next batch starts.
- "Record a follow-up": handled as a deferred item, below.

On a resumed run, skip a flagged item that already has a `[batch N flag-note] <path>` or `[batch N bug-fix]` commit for its file.

#### Deferred items (follow-on 6)

For each `Deferred` entry: if a row with status `next` in `spec_dd/1. next/roadmap.md` has a Scope covering the item's app, append a bullet to that directory's `idea.md` under `## Follow-ups from other specs`, creating the heading if needed. Otherwise write a new `spec_dd/1. next/<slug>/idea.md` with `## What`, `## Why` and `## Resources`. Never edit `roadmap.md`, because `/sdd:roadmap` picks new ideas up. On a resumed run, skip an item whose bullet or `idea.md` already exists in the working tree.

#### Record (follow-on 7)

Append a `## Batch N` section to `<spec-dir>/boy_scout_record.md`, creating the file with a `# Boy-scout record: <spec name>` heading the first time. It lists the review findings and how each was fixed or answered, any accepted edge for `/app_map`, what the boy-scout tidied, each deferred item with where it went, and each flagged item with the user's answer. Commit it via `sdd:sdd-mechanic` as `[batch N record] <summary>`, even when nothing else was committed. Stage `boy_scout_record.md` and any follow-up `idea.md` files by explicit path. Then delete `.sdd-work/test_org_review_batch_<N>.md` and `.sdd-work/boy_scout_batch_<N>.md` by name.

**All tests must pass before moving to the next batch.**

### DO NOT run the frontend_qa plan during implementation
If there is a `3. frontend_qa.md` file, do **not** run it, and ignore any plan step that says to run it. The QA process runs separately, after the plan is complete.

## Step 3: Final Verification

After all batches are complete:

1. Run `uv run pytest` via `sdd:sdd-mechanic` to confirm everything passes
2. **Final test-organisation review.** Skipped when `## Testing Skills` is blank. One `sdd:sdd-worker` writes `.sdd-work/test_org_review_final.md` in the Review follow-on's finding format. Skip the spawn when that file already exists and ends `status: ok`. The worker has no `Bash`, so depth 0 puts these in its brief: the skill line, the output of `git diff --name-only "$(git merge-base origin/main HEAD)" HEAD`, the path to `boy_scout_record.md`, and the budget counts (see "Commit-subject grammar"). It looks for what no single batch's review shows: the same new cross-app edge appearing across several batches, an edge one batch's boy-scout removed and a later batch brought back, and the total budget spent. Resume, retry and `blocked` work as in Review (follow-on 1). Handle findings as in Review fixes and Flagged items: mechanical findings go to one `sdd:sdd-implementer` with the skill line and the subject `[final review-fix] <summary>`; judgement findings go to the user via `AskUserQuestion`. Delete `.sdd-work/test_org_review_final.md` by name once every finding is handled.
3. Check each success criterion from the plan — is it met?
4. If any criterion is unmet: fix it with one `sdd:sdd-implementer` (`subagent_type: "sdd:sdd-implementer"`, per-spawn `model: "sonnet"`), whose brief carries the skill line (when the Testing Skills list is not empty) and the unmet criterion, then repeat from step 1
5. Once everything passes: unless `## Testing Skills` is blank, append a `## Summary` section to `boy_scout_record.md` first, covering the final review's findings and answers, counts of review fixes, tidies, deferrals and flagged items by answer, and any edge that still needs an `/app_map` re-run. Then make the final commit via `sdd:sdd-mechanic`, staging `boy_scout_record.md` by explicit path alongside the commit's other files. Give the user the same counts and any `/app_map` edge in the conversation. The PR body is not touched.

## When to Stop and Ask

**Stop immediately when:**
- A step is unclear or ambiguous
- A test fails and the cause isn't obvious
- You hit a missing dependency or prerequisite
- The plan has a gap that blocks progress

**Ask for clarification rather than guessing. Don't force through blockers.**

## Branch Safety

Never start implementation on main/master branch without explicit user consent.

## Step 4: Update the todo list

Delegate to `sdd:sdd-mechanic`: invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory
- `tick:"Run `/implement_plan` to execute the implementation plan"`

No new items to add.
