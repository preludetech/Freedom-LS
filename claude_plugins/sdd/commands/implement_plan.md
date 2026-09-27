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

Make one batch per vertical slice in the plan, in the plan's order. A slice runs end to end through every layer its behaviour needs (e.g. "learner can see their deadline on the course page": field + migration + view + template + tests), so never regroup the plan's steps by layer ("all the models", then "all the views"). A small shared-groundwork step the plan places before a slice goes into that slice's batch. If the plan is not ordered as slices, group its steps into the thinnest batches that each deliver working, tested behaviour. Assign each batch a deterministic completion marker per the commit-subject grammar below. A batch now owns several commits, and `[batch N]` is only the implementation's; the batch is finished at `[batch N record]`, or at `[batch N]` when `## Testing Skills` is blank.

### Commit-subject grammar

Every commit a batch produces carries its number (later slices add more rows):

| Subject | Made by |
| --- | --- |
| `[batch N] <summary>` | implementer |
| `[batch N review-fix] <summary>` | fix agent, for a mechanical review finding |
| `[batch N record] <summary>` | depth 0 via `sdd:sdd-mechanic`: `boy_scout_record.md` plus any follow-up files; always the batch's last commit |

Matching `[batch N]` needs the closing bracket straight after the number, so no follow-on commit reads as the implementation's commit. Resume, and later the budget and the scope check, read subjects only.

### Touched files

Touched files are the paths the `[batch N]` commit and its `[batch N review-fix]` commits add or modify, at their current paths. The review, and later the boy-scout, work over this set:

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
- `[batch N]` but no `[batch N record]` → run the follow-ons only. Reuse `.sdd-work/test_org_review_batch_<N>.md` when it ends `status: ok`; a `[batch N review-fix]` commit means the mechanical fixes have already landed, so don't send them again.
- `[batch N record]` → skip, but first delete any leftover `.sdd-work/test_org_review_batch_<N>.md` by name — an interrupt can land between the record commit and its own deletes.

For each remaining batch, spawn **one implementation sub-agent** via the `Agent` tool with `subagent_type: "sdd:sdd-implementer"`, and pass the per-spawn `model: "sonnet"` parameter so non-interactive batch work runs on a mid-tier model rather than the session model. (The user can override to `model: "opus"` per spawn — or set `CLAUDE_CODE_SUBAGENT_MODEL` — if a batch needs heavier reasoning.) Its brief carries the skill line (when the list from above is not empty), the batch's plan steps verbatim, and the commit subject `[batch N] <summary>`. The TDD, full-suite and commit rules live in the `sdd:sdd-implementer` agent file, which returns a structured status (`status: ok|failed|blocked` · `reason:`).

Committing inside the worker keeps the work and its completion marker **atomic**: a crash between "work done" and "marker written" can't leave an uncommitted batch that the resume scan would wrongly re-run over a dirty tree. Agents whose work is a commit make it themselves; `sdd:sdd-mechanic` makes the bookkeeping commits.

After a batch returns, act on its status:
- `ok` → verify the `[batch N]` commit exists, then run the follow-ons below (skipped when `## Testing Skills` is blank), and move to the next batch once they finish.
- `failed` → reset any partial uncommitted work so the retry starts clean, then retry that batch (≤2 attempts) with the prior error included in the brief.
- `blocked` → gather the listed `needs` via `AskUserQuestion` (legal at depth 0), then re-spawn the batch with the answers.

### Follow-ons

Run these in order after `[batch N]` lands and the suite passes. All of them are skipped when `## Testing Skills` is blank. Later follow-ons go between Review fixes and Record, and Record is always last.

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

#### Record (follow-on 7)

Append a `## Batch N` section to `<spec-dir>/boy_scout_record.md`, creating the file with a `# Boy-scout record: <spec name>` heading the first time. It lists the review findings and how each was fixed or answered, and any accepted edge for `/app_map`. Commit it via `sdd:sdd-mechanic` as `[batch N record] <summary>`, even when nothing else was committed. Stage `boy_scout_record.md` by explicit path. Then delete `.sdd-work/test_org_review_batch_<N>.md` by name.

**All tests must pass before moving to the next batch.**

### DO NOT run the frontend_qa plan during implementation
If there is a `3. frontend_qa.md` file, do **not** run it, and ignore any plan step that says to run it. The QA process runs separately, after the plan is complete.

## Step 3: Final Verification

After all batches are complete:

1. Run `uv run pytest` via `sdd:sdd-mechanic` to confirm everything passes
2. Check each success criterion from the plan — is it met?
3. If any criterion is unmet: fix it with one `sdd:sdd-implementer` (`subagent_type: "sdd:sdd-implementer"`, per-spawn `model: "sonnet"`), whose brief carries the skill line (when the Testing Skills list is not empty) and the unmet criterion, then repeat from step 1
4. Once everything passes: make the final commit via `sdd:sdd-mechanic`

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
