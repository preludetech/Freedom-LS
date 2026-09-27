---
name: implement_plan
description: Execute the implementation plan in resilient batches.
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, Skill, Agent, ToolSearch, AskUserQuestion, mcp__playwright__*, mcp__plugin_ds_playwright__*
argument-hint: [suffix, e.g. 2b]
---

# Executing Plans

This command runs at **depth 0** (the main thread) and orchestrates batch sub-agents.

## Input

`[suffix]`: optional, `2` followed by letters (e.g. `2b`). The plan file is `<suffix>. plan.md`. The QA file swaps the leading `2` for `3`: `3<letters>. frontend_qa.md`. With no suffix they are `2. plan.md` and `3. frontend_qa.md`.

Below, **the plan file** and **the QA file** mean the resolved names, and **`<id>`** means `<suffix>.N` with a suffix and `N` without.

## Step 0: Pre-step rebase

Read `claude_plugins/sdd/commands/protected/pre_step_rebase.md` and follow its steps.

## Step 1: Read and Review the Plan

1. Read the plan file
2. Before implementing anything, check for:
   - Missing or ambiguous steps
   - Steps that depend on things not covered earlier in the plan
   - Unclear success criteria
   - Missing dependencies or prerequisites
3. Proceed to Step 2. A batch that cannot proceed returns `blocked` and is handled per the recipe.

## Step 2: Batch and Execute (resilient)

### Testing skills

Before spawning anything, read `## Testing Skills` from `.claude/sdd/config.md`, then from
`.claude/sdd/config.local.md`, whose values win. Blank, or the file or section absent, means the
list is empty. When it is not empty, every brief for an implementer, reviewer, boy-scout or fix
agent opens with:

> Before anything else, invoke the `Skill` tool for each of: <ids>, in order.

Make one batch per vertical slice in the plan, in the plan's order. A slice runs end to end through every layer its behaviour needs (e.g. "learner can see their deadline on the course page": field + migration + view + template + tests), so never regroup the plan's steps by layer ("all the models", then "all the views"). A small shared-groundwork step the plan places before a slice goes into that slice's batch. If the plan is not ordered as slices, group its steps into the thinnest batches that each deliver working, tested behaviour. Assign each batch a deterministic completion marker: a git commit whose message is prefixed `[batch <id>] <summary>`. A batch owns several commits (see "Commit-subject grammar" below), and `[batch <id>]` is only the implementation's; the batch is finished at `[batch <id> record]`, or at `[batch <id>]` when `## Testing Skills` is blank.

**Resume scan (before spawning):** match the subjects from `git log --format=%s origin/main..HEAD` against this exact, anchored pattern and **skip completed batches**. Only run batches whose marker commit is missing. A `design fix`, `review fix` or `integration fix` commit counts as its batch's commit. The sub-sections below say what runs on resume and how each batch wave runs.

```
with suffix 2b: ^\[batch 2b\.[0-9]+\]     (only this suffix's batches)
without suffix: ^\[batch [0-9]+\]         (never matches [batch 2b.1])
```

Each batch is run by **one implementation sub-agent**, spawned via the `Agent` tool with `subagent_type: "sdd:sdd-implementer"` and the per-spawn `model: "sonnet"` parameter, so non-interactive batch work runs on a mid-tier model rather than the session model. (The user can override to `model: "opus"` per spawn — or set `CLAUDE_CODE_SUBAGENT_MODEL` — if a batch needs heavier reasoning.) Its brief carries the skill line (when the list from above is not empty), the batch's plan steps verbatim with any verifications the plan specifies after each step, and the commit subject `[batch <id>] <summary>`. The test-first, test-tier and commit rules live in the `sdd:sdd-implementer` agent file: it runs the `targeted` tier through `claude_plugins/sdd/commands/protected/run_test_tier.md` with `<diff>`: `--working-tree`, makes the commit itself as its final step, and returns a structured status (`status: ok|failed|blocked` · `reason:`).

Every brief also carries this rule: comments, docstrings and test names state facts about the code and stand on their own. They never mention the spec, plan, research notes or QA plan, or their numbers: no `§4b`, `spec 6`, `this slice`, `batch 3`, `a later spec`, `Phase 2` or `spec_dd/` paths. Where the reasoning came from the spec, write the reasoning itself. If the project has a skill for writing code comments, the batch follows it.

The brief also names the files under `## Review Hooks` in `.claude/sdd/config.md` (`config.local.md` wins): read and follow the `Comment standard` file and the `Test standard` file before writing code or tests. When `Comment standard` is non-blank the implementer also reads and follows `${CLAUDE_PLUGIN_ROOT}/skills/planning-references-in-code/SKILL.md`. A blank key names nothing.

When the batch's slice has a `**Design states:**` line, the brief also passes the **design paths**, as paths and never contents:

- the plan file and the heading of its Design section;
- the design screenshot for each of the slice's design states.

The brief adds: the design is a visual reference, never a source of scope. Build what the plan's Design section transcribes and nothing else the design shows. Use the project's theme tokens, components and semantic icons; never add a theme, theme token, font or colour, and never add an icon that does not fit the project's icon set.

Committing inside the worker keeps the work and its completion marker **atomic**: a crash between "work done" and "marker written" can't leave an uncommitted batch that the resume scan would wrongly re-run over a dirty tree. Agents whose work is a commit make it themselves; `sdd:sdd-mechanic` makes the bookkeeping commits.

**Names from git.** Every worktree path, worktree name and branch this step acts on comes from a `git worktree list` line or a worker's return line, never from free text. `<name>` is the last path component of the worktree path. A path, name or branch that does not match `^[A-Za-z0-9._/-]+$`, or a name containing `..`, is skipped and named in the Step 3 summary. Each value is passed to a command as its own single-quoted argument.

**Cap.** Read `Parallel batches` under `## Worktree Scripts` in `.claude/sdd/config.md` (`config.local.md` wins). Blank, absent or `1` is `1`. Read `Memory capacity` and `Batch memory (MB)` from the same section. When both are set, `capacity` is the integer printed by `<Memory capacity> <Batch memory (MB)>`, run just before each batch wave forms. When either is blank, or the command fails or prints no integer, there is no capacity limit.

**Leftover batch worktrees.** Before spawning anything, run `git worktree list`. For each worktree under this checkout's `.claude/worktrees/` whose branch holds a commit matching the plan's anchored `[batch …]` pattern: cherry-pick, in plan order, every such commit whose id has no marker on the feature branch. A conflict is `git cherry-pick --abort`; the worktree is then still torn down and removed, and the batch has no marker commit so it re-runs in plan order. Then run the Teardown script inside it (`cd <path> && <script>`, one call; blank: nothing), then `git worktree remove --force --force .claude/worktrees/<name>` and `git branch -D <branch>`. Any other worktree under `.claude/worktrees/` is left alone and named in the Step 3 summary. The permission prompt the `cd` call raises is accepted: it happens only on a resumed, attended run.

**Resume reviews.** On resume, the Design check and Batch review run again for every batch whose marker commit is later than the last `review fix`, `design fix` or `integration fix` commit, or for the last batch when there is none.

**Resume follow-ons.** When `## Testing Skills` is not blank, a batch with its marker commit but no `[batch <id> record]` runs its follow-ons only, in plan order, after its Design check and Batch review and before the first batch wave forms. See "Follow-ons" below for what each one reuses.

**Batch waves.** `remaining` is the batches without a marker commit, in plan order. Repeat until it is empty: `ready` is every batch in `remaining` whose `Builds on:` slices all have a marker commit. A plan in which any slice lacks a `Builds on:` line, or that this step regrouped into batches, runs sequentially: `ready` = the first remaining batch. The batch wave is the first `min(len(ready), cap, capacity)` of `ready`.

**A batch wave of one.** Runs in the feature worktree, with no isolation, as a single sequential batch: the brief above, then `ok` (verify the marker commit, Design check, Batch review, then the Follow-ons), `failed` (reset partial uncommitted work, retry with the prior error in the brief), `blocked` (ask at depth 0, re-spawn with the answers). This paragraph owns the attempt count: a batch gets at most two retries across every batch wave it appears in (a batch that dies from memory counts against the same two retries), and one that exhausts them stops the run with `status: failed`, naming it and every batch that builds on it. The tier must pass before the next batch wave is formed. A fix batch (`design fix`, `review fix` or `integration fix`) is a batch, so it runs `targeted` the same way.

**A batch wave of two or more.** Record `wave-base` = `git rev-parse HEAD`. Resolve the Setup script and Teardown script values once at depth 0 (`config.local.md` is gitignored and absent in a batch worktree). Spawn every batch of the batch wave in one message, each `subagent_type: "sdd:sdd-implementer"`, `model: "sonnet"`, `isolation: "worktree"`. The brief is the batch brief above plus: first run `<Setup script>` from the worktree root (blank: nothing); work only inside this worktree; whatever the outcome, run `<Teardown script>` the same way before returning (blank: nothing); return `status: ok|failed|blocked · reason: <short> · worktree: <abs path> · branch: <name>`. A worker that returns no status line counts as `failed` with reason `no return`.

**Integration.** When every worker of the batch wave has returned or been counted as failed, for each `ok` batch in plan order, cherry-pick the commits on its branch whose subject matches the plan's anchored `[batch …]` pattern. A conflict is `git cherry-pick --abort` and the batch is marked `failed` with the conflicting files as its reason. Then, for every batch of the batch wave, resolve its worktree path and branch from its return line, or from `git worktree list` when the return lacks them; for a batch that is not `ok`, run the Teardown script inside the worktree first (`cd <path> && <script>`; the script is safe to run twice); then `git worktree remove --force --force .claude/worktrees/<name>` and `git branch -D <branch>`.

**After integration.** Run the `Migrate` command under `## QA Dev Data` in `.claude/sdd/config.md` when non-blank, so the feature worktree's dev database holds the batch wave's migrations before the Design check starts a server. Then delegate to `sdd:sdd-mechanic`: read `${CLAUDE_PLUGIN_ROOT}/commands/protected/run_test_tier.md` and follow it with `<tier>`: `targeted` and `<diff>`: `--range <wave-base>..HEAD`. A failure is fixed by a sub-agent as Step 3 point 3 does, committed as `[batch <id>] integration fix` with the id of the last integrated batch. Then, for each integrated batch in plan order, the Design check, the Batch review and the Follow-ons run as for a batch wave of one.

**Retries.** Each batch of the batch wave that is not `ok` (returned `failed` or `blocked`, returned nothing, or conflicted) re-runs at once, in plan order, through the batch-wave-of-one rule above with its reason, before the next batch wave is formed. That rule counts the attempts.

### Design check

Runs at depth 0 after a batch returns `ok` whose slice has a `**Design states:**` line. Its judgement stays at depth 0. It never asks the user whether to build something the design draws, and fix batches never ask the user anything.

Read `Design check` under `## Design Hooks` in `.claude/sdd/config.md` (`config.local.md` wins), the way `claude_plugins/sdd/commands/protected/pre_step_rebase.md` reads `## Rebase Hooks`. A blank value, or an absent file or section, skips the check: record "design check skipped: no Design check hook" for the Step 3 summary and move on.

Otherwise, start with `fixes = 0` and repeat these steps until one of them ends the check:

1. Read the hook file and follow it here with `<spec-dir>`, the plan path and the slice's design states. It returns one screenshot path per state and width. On `failed`, stop the run with `status: failed` and its reason.
2. For each state, Read the app screenshot and the design screenshot. List each one's elements region by region, then diff both lists against the state's design checklist in the plan. Judge layout, order, hierarchy, relative density, states and copy. Colour, font, icons and exact pixels belong to the project's theme and stay out of the judgement. A drawn element the checklist does not list is not a miss: its absence is correct.
3. Every design checklist line is met (no **design miss**): delete the hook's screenshots by name, log "design check passed", and end the check.
4. A design miss that has already gone to two fix batches and still stands: record it with the plan line it contradicts and the hook's screenshot paths (they stay under `.sdd-work/`, which is gitignored), add it to the run's list of surviving design misses, and end the check. The run continues; Step 4 files the list in `todo.md`. Nothing writes `todo.md` while batches run, so a batch commit or a failed batch's reset can't take the item with it.
5. Otherwise spawn one fix batch (`subagent_type: "sdd:sdd-implementer"`, `model: "sonnet"`, the skill line first in its brief) with the list of misses and the design paths. It commits `[batch <id>] design fix <n>`, and `fixes` goes up by one. Act on its status as for any batch, then go back to step 1.

### Batch review

Runs at depth 0 after the Design check of every batch that returned `ok`, on the batch commit and its design-fix commits together. Read `## Review Hooks` in `.claude/sdd/config.md` (`config.local.md` wins). A blank `Comment standard` or `Test standard`, or an absent section or file, skips that half and records "review skipped: no <key> hook" for the Step 3 summary; both blank skips the review.

The scratch files are `.sdd-work/batch_review_<id>_diff.md`, `.sdd-work/batch_review_<id>_mechanic.md` and `.sdd-work/batch_review_<id>.md`. They are deleted by name, skipping any that does not exist, at the start of every round and on every exit from this section, including a `failed` or `blocked` status.

Start with `fixes = 0` and `scope = <batch-commit>^..HEAD`, then repeat:

1. **Mechanic** (`sdd:sdd-mechanic`), briefed with `<scope>` and `<id>`: write the added lines of `git diff <scope>`, each as `<path>:<line>: <text>`, to the diff file. Then run, over the diff file,

       grep -nE '§|\b([Ss]pec|[Ss]lice|[Bb]atch|[Pp]hase) ?[0-9]|this spec|a later spec|QA bug|spec_dd/|[0-9]+\. (spec|plan|frontend_qa)\.md'

   and write the hits to the mechanic file, one per line in the same shape, or the single line `none`.
2. **Worker** (`sdd:sdd-worker`): read the diff file, the mechanic file and the `Comment standard` and `Test standard` files, plus `${CLAUDE_PLUGIN_ROOT}/skills/planning-references-in-code/SKILL.md`. Apply the `Comment standard` file and the planning-references file together as one checklist, and the `Test standard` file as the other, as a closed checklist (a blank `Comment standard` still skips the comment half, planning-references check included) to the added lines only. Write the review file: one line per finding, `<path>:<line>: <rule>: <what to change>`, then the `status:` footer. The brief says: no findings is the normal result; review nothing outside the two standards (no security, performance, architecture, design, naming or style); a `TODO` or `@claude` comment is rewritten with the concrete detail it stood for, never deleted; do not run tests. On a second round the brief names only the rules violated in the previous round.
3. Drop any finding whose `<path>:<line>` is not a line of the diff file. No findings left: log "batch review passed" and end the review.
4. `fixes == 2`: the leftovers go into the Step 3 summary; end the review. The run continues.
5. Otherwise spawn one fix batch (`subagent_type: "sdd:sdd-implementer"`, `model: "sonnet"`, the skill line first in its brief) with the findings and the two standard files' paths. It commits `[batch <id>] review fix <n>` and runs `targeted` through `run_test_tier.md` like any batch; `fixes` goes up by one and `scope` becomes `<fix-commit>^..HEAD`. Act on its status as for any batch, then go back to step 1.

### Commit-subject grammar

Every commit a batch produces carries its id (later slices add more rows):

| Subject | Made by |
| --- | --- |
| `[batch <id>] <summary>` | implementer |
| `[batch <id>] design fix <n>`, `[batch <id>] review fix <n>`, `[batch <id>] integration fix` | fix batch, for the Design check, the Batch review or an integration failure |
| `[batch <id> review-fix] <summary>` | fix agent, for a mechanical test-organisation finding |
| `[batch <id> boy-scout] move <old-path> -> <new-path>` | boy-scout; exactly one file, no content change |
| `[batch <id> boy-scout] edit <summary>` | boy-scout; the edit that goes with the move before it |
| `[batch <id> boy-scout] edit split <path> into <a>, <b>` | boy-scout; a split |
| `[batch <id> boy-scout] edit drop <app> test dependency on <other-app>` | boy-scout; one cross-app dependency removed |
| `[batch <id> record] <summary>` | depth 0 via `sdd:sdd-mechanic`: `boy_scout_record.md` plus any follow-up files; always the batch's last commit |

Matching `[batch <id>]` needs the closing bracket straight after the id, so no follow-on commit reads as the implementation's commit, and the resume pattern above never matches one. Resume, and later the budget and the scope check, read subjects only, never SHAs, because `pre_step_rebase` rewrites every SHA on each rebase.

The boy-scout's budget is counted fresh each time from `git log`, never carried in memory:

```bash
LOG=$(git log --format=%s "$(git merge-base origin/main HEAD)..HEAD")
moved=$(grep -cE '^\[batch [^] ]+ boy-scout\] (move |edit split )' <<<"$LOG" || true)   # cap 3
dropped=$(grep -cE '^\[batch [^] ]+ boy-scout\] edit drop ' <<<"$LOG" || true)          # cap 1
```

Remaining budget is the cap minus the count, floored at 0. The boy-scout still runs at zero
budget, so it can report deferred items.

### Touched files

Touched files are the paths the `[batch <id>]` commits (the implementation and its design, review and integration fixes) and its `[batch <id> review-fix]` commits add or modify, at their current paths. The test-organisation review, and later the boy-scout, work over this set:

```bash
ID=<id>
BASE=$(git merge-base origin/main HEAD)
git log --reverse --format='%H%x09%s' "$BASE..HEAD" \
  | while IFS=$'\t' read -r sha subject; do
      case "$subject" in
        "[batch $ID] "*|"[batch $ID review-fix] "*)
          git diff-tree --no-commit-id -r -M --name-only --diff-filter=AMR "$sha" ;;
      esac
    done | sort -u
# keep only paths that still exist in the working tree (their current paths)
```

This is the same rule the scope-check script uses for its own allowed set, kept separate on purpose: this one runs over `BASE..HEAD` and filters to paths that still exist, for a brief; the script takes an as-of-commit snapshot at `<from-ref>` for enforcement. If either rule changes, change both.

### Follow-ons

Run these in order after a batch's Batch review. All of them are skipped when `## Testing Skills` is blank. Later follow-ons go between Review fixes and Record, and Record is always last. They run at depth 0 in the feature worktree, one batch at a time in plan order, before the next batch wave forms.

On resume, a batch whose follow-ons are pending reuses `.sdd-work/test_org_review_batch_<id>.md` when it ends `status: ok`; a `[batch <id> review-fix]` commit means the mechanical fixes have already landed, so don't send them again. Reuse `.sdd-work/boy_scout_batch_<id>.md` the same way when it ends `status: ok`, and give a re-spawned boy-scout's brief the batch's existing `[batch <id> boy-scout]` commits so it finishes a half-done pair instead of repeating it. A batch with `[batch <id> record]` is done, but first delete any leftover `.sdd-work/test_org_review_batch_<id>.md` and `.sdd-work/boy_scout_batch_<id>.md` by name: an interrupt can land between the record commit and its own deletes.

#### Review (follow-on 1)

One `sdd:sdd-worker`, spawned per the fan-out recipe as in `plan_from_spec.md` Step 6, writes `.sdd-work/test_org_review_batch_<id>.md`. Skip the spawn when that file exists and ends `status: ok`. Its brief:

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

If there are mechanical findings, send them all to one `sdd:sdd-implementer` with the skill line and the subject `[batch <id> review-fix] <summary>`. It may edit any file the fix needs, for example an app's existing `tests/conftest.py`. Put judgement findings to the user right away, up to four per `AskUserQuestion`, with the reviewer's recommendation as the first option. An answer that needs code takes the same fix path. If the answer accepts a new cross-app edge, the record says so and names `/app_map` as needing a re-run.

#### Boy-scout (follow-on 3)

Skip when no touched file is a test file (under a `tests/` directory, or named `test_*.py` or `conftest.py`) or production code (any other source file); markdown, `docs/` and `spec_dd/` paths count as neither. Otherwise record `FROM_REF=$(git rev-parse HEAD)` and spawn one `sdd:sdd-boy-scout` with the batch id, the touched files, the remaining budget, whether `docs/app_structure.md` exists, and — on a resumed run — the batch's existing `[batch <id> boy-scout]` commits. Before spawning, note `git status --porcelain`. `failed` → restore modified tracked files with `git restore --staged --worktree <paths>` and delete, by name, any untracked file that was not in the earlier listing, then retry up to twice with the prior error in the brief; its commits stay. `blocked` → as for the review.

#### Scope check (follow-on 4)

Via `sdd:sdd-mechanic`, run `batch_scope_check.sh <id> <from-ref>`, with the script path resolved as in `pre_step_rebase.md` Step 3. `<from-ref>` is `FROM_REF`; on resume it is the parent of the batch's oldest `[batch <id> boy-scout]` commit, or `HEAD` when there is none. Exit 1 stops the run and puts the `OUT_OF_SCOPE:` paths to the user. Commits are never reverted automatically. Any other non-zero exit is `failed`.

#### Deferred items (follow-on 6)

For each `Deferred` entry: if a row with status `next` in `spec_dd/1. next/roadmap.md` has a Scope covering the item's app, append a bullet to that directory's `idea.md` under `## Follow-ups from other specs`, creating the heading if needed. Otherwise write a new `spec_dd/1. next/<slug>/idea.md` with `## What`, `## Why` and `## Resources`. Never edit `roadmap.md`, because `/sdd:roadmap` picks new ideas up. On a resumed run, skip an item whose bullet or `idea.md` already exists in the working tree.

#### Record (follow-on 7)

Append a `## Batch <id>` section to `<spec-dir>/boy_scout_record.md`, creating the file with a `# Boy-scout record: <spec name>` heading the first time. It lists the review findings and how each was fixed or answered, any accepted edge for `/app_map`, what the boy-scout tidied, and each deferred item with where it went. Commit it via `sdd:sdd-mechanic` as `[batch <id> record] <summary>`, even when nothing else was committed. Stage `boy_scout_record.md` and any follow-up `idea.md` files by explicit path. Then delete `.sdd-work/test_org_review_batch_<id>.md` and `.sdd-work/boy_scout_batch_<id>.md` by name.

### QA never runs inside a batch
QA runs in Step 5, never inside a batch, and a plan step that says to run it is ignored.

## Step 3: Final Verification

After all batches are complete:

1. Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/commands/protected/run_test_tier.md` and follow it with `<tier>`: `full`, returning the summary line and any failing test names.
2. Write the summary: per batch, the Design check as passed, skipped or the surviving misses with their `fixes` count; the Batch review as findings, fix batches and leftovers, or "review skipped: no <key> hook"; per batch wave, its batches and where they ran (feature worktree or batch worktree path); the leftover worktrees removed, left or skipped; then the full-tier result and each success criterion (is it met?).
3. If any criterion is unmet: fix it with one `sdd:sdd-implementer` (`subagent_type: "sdd:sdd-implementer"`, per-spawn `model: "sonnet"`), whose brief carries the skill line (when the Testing Skills list is not empty) and the unmet criterion. It runs `targeted`, like any batch. Then repeat from step 1, so a fix is followed by another full run
4. Once everything passes: make the final commit via `sdd:sdd-mechanic`

## When to Stop and Ask

**Stop immediately when:**
- A test fails and the cause isn't obvious
- You hit a missing dependency or prerequisite

**Ask for clarification rather than guessing. Don't force through blockers.**

## Branch Safety

Never start implementation on main/master branch without explicit user consent.

## Step 4: Update the todo list

Delegate to `sdd:sdd-mechanic`: invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory
- `tick:` the unticked item that names this command. With a suffix, that is the item that also names the suffix. Without one, it is `"Run `/sdd:implement_plan` to execute the implementation plan"`.
- one `add:"<section>|user|Decide what to do about design miss: <miss> (screenshots: <paths>)"` per surviving design miss, where `<section>` is the heading text, without the `##`, of the section holding the ticked item (`3. Implementation and QA` in the current layout, `7. Implementation` in older checklists).

With no surviving design misses there is nothing to add.

## Step 5: Run QA

Read `QA command` under `## QA Hooks` in `.claude/sdd/config.md` (`config.local.md` wins).

- Blank: say "no QA command configured; the checklist's QA item is a user item" and go to Step 6.
- The QA file does not exist: say the plan has no QA plan and go to Step 6.
- The value names a command of this plugin (`sdd:<name>`): read `${CLAUDE_PLUGIN_ROOT}/commands/<name>.md` and follow it with `mode: hook`, `<spec-dir>`, `<todo-path>` and the QA file path.
- Any other value: invoke it with the `Skill` tool and `args: "spec-dir=<spec-dir> todo-path=<todo-path> plan=<QA file> mode: hook"`.

Done when the hook has returned `ok`, `failed`, `blocked` or `paused`; any of the last three is carried to Step 6 with its reason.

## Step 6: Final report

Report the QA report path, the bug counts per lane, the `Decide` items filed, and the next human step from `todo.md`. A QA hook that returned `failed`, `blocked` or `paused` is reported with its reason; the implementation commits are already on the branch, and `/sdd:do_qa` is the command that continues.
