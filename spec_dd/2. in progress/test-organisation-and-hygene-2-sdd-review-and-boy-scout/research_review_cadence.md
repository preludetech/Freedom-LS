# Research: when the test-organisation review and boy-scout should run in `implement_plan`

Scope: per-batch vs end-of-spec vs hybrid cadence for the review dimension and the boy-scout step
`implement_plan` will gain, how each interacts with `implement_plan`'s existing resume scan, retry
loop and `pre_step_rebase`, and what industry CI-review-bot practice suggests. Builds on
`research_sdd_standards_hooks.md` (hook points, plugin boundaries) and `research_boy_scout_rule.md`
(what "tidy" means, size budget, commit shape) — neither is repeated here.

One framing note up front: `idea.md`'s "What is settled" list already fixes the boy-scout's own
scope to **one batch's `[batch N]` commit** ("scoped to exactly one batch's own `[batch N]` commit,
found from that commit alone... It never runs a wider scan") — so *whether* the boy-scout runs
per-batch is not actually open; only the **review dimension's** cadence is listed as open ("Whether
the review dimension fans out once per batch, alongside the boy-scout step, or once at the end").
This research treats the boy-scout's per-batch cadence as given and analyses how it composes with
resume/retry/rebase, and treats the review dimension's cadence as the genuinely open question, including
whether a hybrid (per-batch review + a cheap final whole-diff pass) is worth its extra cost.

## 1. Per-batch vs end-of-spec vs hybrid

### 1a. Cost (agent spawns per batch)

Today `implement_plan` spawns exactly **one** subagent per batch (the implementer,
`implement_plan.md:33`). Adding a boy-scout (settled, per batch) and a review dimension adds:

- **Per-batch review**: 1 `sdd:sdd-worker` spawn per dimension per batch. The idea currently names two
  rules (mirroring, cross-app test imports) — whether that's one dimension checking both or two
  dimensions matters for the multiplier: 1–2 extra Sonnet spawns × N batches.
- **End-of-spec review**: the same 1–2 dimension spawns, but paid **once** regardless of batch count.
- **Boy-scout**: 1 spawn per batch that touched qualifying files (settled either way).

For a 5-batch plan, per-batch review costs roughly 5× what end-of-spec review costs in spawns alone.
This is a real, not hypothetical, difference given `sdd:sdd-worker` runs on Sonnet
(`model_tiering.md`: "Sonnet (`sdd:sdd-worker`): non-interactive fan-out units (research, review
dimensions, scans)") — but it is bounded, because these two rules are deliberately narrow and
mechanical (not "review test quality" — that's explicitly out of scope, `idea.md:91-92`), so each
review spawn is cheap relative to the batch implementer spawn it follows (general-purpose, Bash/Edit
breadth, doing the actual TDD work).

### 1b. Feedback timing

The strongest argument for per-batch review is that a **later batch can build on an earlier batch's
misplaced test or newly-introduced cross-app import** — copy a factory import across an app boundary,
or add a second test file beside a file the mirroring rule would already have flagged. If review only
runs once at the end, by the time a violation surfaces it may be replicated across several batches,
and any fix must now touch multiple already-landed `[batch N]` commits rather than one. That is a
heavier, more entangled fix than "fix the one batch that just landed," and it's exactly the kind of
debt `research_boy_scout_rule.md` §3 warns compounds ("noisy diffs hide the actual change," "the rule
doesn't scale... once debt is architectural"). Per-batch review keeps each finding scoped to the
smallest possible diff, which is also the cheapest to fix and the safest to auto-fix without human
judgement.

The counter-argument (end-of-spec) is that some findings are only visible once the whole diff exists
— e.g. the per-branch **budget** (§1d below) is a spec-wide quantity, and a genuinely new cross-app
edge might look like a one-off in batch 2 but turn out to be one of three near-identical edges once
batches 3–5 land, changing whether it's "accept and document" or "restructure" (the same judgement
call `plan_structure_review.md:82-89` already makes at plan time, now needed at implementation time).
A pure per-batch review structurally cannot see that pattern.

### 1c. How findings get fixed, and by whom

Idea.md leaves this open by design (this spec's open question). The two existing SDD precedents point
in different directions:

- **`plan_from_spec.md` Step 6**: findings are read by depth 0 itself, which edits `2. plan.md`
  directly — no sub-agent spawn for the fix. That works there because depth 0 (the interactive
  session) already has full context and Edit access.
- **`plan_structure_review.md` Step 3**: same pattern — depth 0 reads `.sdd-work/plan_structure_findings.md`
  and either edits the plan directly (obvious, small fix) or inserts a `> **Structure concern:**`
  callout for the user to resolve (judgement call). Never auto-resolves ambiguity.

`implement_plan` runs at depth 0 too (`implement_plan.md:9`), so the same shape applies directly: the
review worker(s) stay read-only (`sdd:sdd-worker`, no Edit/Bash — matches the "review dimensions" tier
in `model_tiering.md`), write a `.sdd-work/batch_N_review_<dim>.md` with a `status:` footer, and depth
0 reads the file (not dumped contents, per the fan-out recipe) and decides:

- **Obvious/mechanical finding** (a file that should move to mirror the app hierarchy; an import that
  should come from a runtime-dependency app instead) → depth 0 spawns a **fix sub-agent**, same tier
  and tool-breadth as the batch implementer (`general-purpose`, `model: "sonnet"`, Bash/Edit — it needs
  to move files and run `uv run pytest`), scoped to exactly the flagged files, which makes its own
  commit, e.g. `[batch N review-fix] <summary>` — mirroring the batch's own "commit as the atomic
  completion marker" pattern (`implement_plan.md:38-40`) rather than amending `[batch N]` (amending
  would break the git-log-as-resume-ledger property described in §1e; a `git commit --fixup` targeting
  the batch commit is an alternative worth the spec considering, since `--fixup` preserves the
  distinction while still being squashable later).
- **Judgement-call finding** (a genuinely new cross-app edge the rule can't auto-resolve, e.g. "this
  app now legitimately needs to depend on that one") → same `> **Structure concern:**`-shaped callout,
  but since there's no plan file to annotate mid-implementation, the equivalent at depth 0 is
  `AskUserQuestion` (legal here — `implement_plan.md` runs at depth 0, same as `plan_structure_review`)
  batched with any other open question, per the fan-out recipe's "ask while workers run" pattern —
  never silently auto-accepted.

This gives a natural **two-tool relationship** between the review dimension and the boy-scout that
idea.md doesn't spell out but that resolves the apparent overlap (both look at "test placement /
cross-app imports"): **review classifies and reports** (including things the boy-scout's budget or
mandate can't touch — a genuine new edge, a violation bigger than the per-branch budget); **boy-scout
executes** the narrow, budgeted, mechanical subset of what review would find on the batch's own files.
Recommended ordering per batch, if both run per batch: **review first, then boy-scout** — running
boy-scout first risks it spending its small budget tidying something the review step would have
flagged as needing a real (non-mechanical) fix or as already over budget; running review first lets
its findings inform what's left for boy-scout to mechanically tidy. (This is an inference connecting
the two settled mechanisms, not something idea.md states directly — worth the spec author confirming.)

### 1d. Tracking the per-branch budget across batches

The budget is explicitly **per branch**, not per batch (`idea.md:58-59`, roadmap
`spec_dd/1. next/roadmap.md:304`: "about 3 test files moved and 1 cross-app dependency removed **per
branch**"). Each boy-scout spawn is a fresh, isolated, one-shot subagent with no memory of prior
spawns (`fanout_recipe.md`: "no mid-run messaging... no nesting"), so if boy-scout runs per batch, the
budget must be tracked **outside** any individual spawn and threaded into each new spawn's prompt.

Two candidate ledgers:

1. **A `.sdd-work/` counter file**, updated by depth 0 after each boy-scout spawn returns. Simple, but
   it's exactly the kind of intermediate artifact the fan-out recipe treats as disposable
   ("Clean up on success... an abandoned `.sdd-work/` from an interrupted run is intentional") — if it
   survives a crash it's fine (resume can re-read it), but if a later run's cleanup step deletes it
   between batches for any reason, the running total is lost silently, with no fallback.
2. **`git log` itself**, parsed for prior `[batch N boy-scout]`-prefixed commit subjects on the current
   branch, each stating what it moved/removed (e.g. `[batch 2 boy-scout] move 1 test file`). This is
   the same trick `implement_plan.md:31` already uses for batch-commit resume ("scan `git log` for
   existing `[batch N]` commits"), and it survives everything a scratch file might not: crashes,
   resumed sessions, and — critically — **rebases** (§2), since a rebase rewrites SHAs but preserves
   commit messages, so a prefix-and-subject grep still finds every prior boy-scout commit after a
   rebase replays them.

Recommendation: use git log as the ledger (option 2), consistent with the project's existing pattern
of treating commit-message prefixes as the durable, rebase-safe manifest, and bake the *remaining*
budget (not a fresh 3/1 every time) into each new boy-scout spawn's prompt so a later batch's
boy-scout doesn't over-spend a budget earlier batches already used.

### 1e. The resume marker for review and boy-scout, and how resume must treat it

These need **different** markers because they have different write shapes:

- **Boy-scout**: a git commit is both correctness marker and content — no separate ledger is needed.
  Resume for boy-scout is: after finding `[batch N]` in `git log`, also look for a following
  `[batch N boy-scout ...]`-prefixed commit; if absent, run boy-scout for batch N (never re-run the
  batch's own implementation). Since boy-scout makes a **move commit then an edit commit**
  (`idea.md:62-63`, for rebase-safety — see §2), resume must treat *either* half being present as
  meaning "already started" and know to resume from the missing half, not restart both.
- **Review dimension**: idea.md is explicit this writes a `.sdd-work/` file with a `status:` footer,
  *not* a commit (`idea.md:42-44`) — because the review dimension itself makes no edits, only reports.
  This creates a subtlety the plan-time fan-out doesn't have: `plan_from_spec` Step 6's `.sdd-work/`
  files are cleaned up once *that command's* single durable artifact (`2. plan.md`) is finalized
  (`fanout_recipe.md` step 7) — but `implement_plan` has no single end-of-run artifact to fold review
  findings into; the findings' fix (if any) becomes its own commit, and the `.sdd-work/` file becomes
  disposable **once that fix commit lands** — but only then. If it's deleted immediately after each
  batch's review completes (mirroring the plan-review cleanup pattern), a later crash mid-run has no
  way to tell "batch N was reviewed and found clean" from "batch N was never reviewed," because an
  empty/absent `.sdd-work/batch_N_review_<dim>.md` looks the same in both cases, and there is no
  commit to check either (a clean review makes no commit at all). Two ways to keep resume correct:
  1. **Don't delete `.sdd-work/batch_N_review_<dim>.md` until the whole `implement_plan` run finishes**
     (all batches + Step 3), i.e. treat these as run-scoped, not batch-scoped, intermediate files —
     simplest, costs only some `.sdd-work/` clutter for the run's duration.
  2. **Always make a marker commit for the review step**, even when it found nothing —
     `[batch N review] no findings` — so git log stays the single resume ledger for every per-batch
     step (implementation, review, boy-scout alike), at the cost of an extra near-empty commit per
     batch.
  This research recommends (1): it needs no new commit convention, and re-running a review that
  already passed is cheap and side-effect-free (it's read-only), so even if resume errs toward
  re-running review after an ambiguous crash, the cost is one extra Sonnet spawn, not a correctness
  bug — a materially different risk profile than boy-scout or the batch implementer accidentally
  re-running (which would touch already-landed code).

### 1f. Ordering with the batch's own commit, and what resume must add

The settled ordering is: `[batch N]` lands first (tests green, atomic per `implement_plan.md:40`),
then boy-scout's own commit(s) follow, scoped to reading *only* `[batch N]`'s own touched files
(`idea.md:48-49`, `git show --name-only`). The consequence for resume: **today's resume scan has only
two states per batch** — "no `[batch N]` commit → spawn the implementer" and implicitly "`[batch N]`
exists → move on" (`implement_plan.md:31`, `:43`). Adding review + boy-scout means a batch now has (up
to) **three states**, and resume must check all of them independently before deciding what (if
anything) to spawn for that batch:

1. No `[batch N]` commit → spawn the implementer (unchanged).
2. `[batch N]` exists, but no completed review (§1e) and/or no boy-scout commit for N → spawn only the
   missing follow-on step(s), never re-implement.
3. `[batch N]` exists and both follow-ons are done → skip entirely, move to batch N+1.

This is the same "resume mid-review" shape `pre_step_rebase.md` Step 4 already uses ("If
`.sdd-work/rebase_upstream_review.md` already exists and ends `status: ok`, this is a resumed run —
reuse it and skip straight to Step 5") — a precedent worth citing directly in the eventual spec/plan
for this idea, since it's the one place SDD already resumes mid-multi-step-sequence rather than
mid-single-unit.

One more retry-interaction worth naming: because a batch's own `[batch N]` commit is made **only as
its last, successful step** ("As its final step, make the `[batch N] <summary>` git commit itself,"
`implement_plan.md:38`), a `failed` batch retry (`implement_plan.md:44`) never has a `[batch N]` commit
to contend with — the failure happens before commit, and the retry resets uncommitted work and starts
clean. So batch-level retries never interact with review/boy-scout resume at all: review and boy-scout
only ever trigger off a *confirmed-landed* batch commit, and exactly one such commit will ever exist
per batch by construction. Review and boy-scout need their **own** failed/blocked handling, though,
since idea.md doesn't specify it: the review worker (read-only `sdd:sdd-worker`) should follow the
plain fan-out recipe's contract (`failed` → retry same unit ≤2 attempts with the prior error folded
in; `blocked` → depth 0 supplies `needs` or asks via `AskUserQuestion`), while boy-scout (Edit/Bash
breadth, can leave a half-done move mid-crash) should follow the **batch's** retry contract instead
(reset any partial uncommitted work, then retry ≤2 attempts) — because unlike the review worker, it can
leave dirty working-tree state a plain re-spawn would trip over.

## 2. Interaction with rebase

`pre_step_rebase.md` runs once per `implement_plan` **invocation** (Step 0, skipped only when
`/sdd:next` says it already ran "this turn" — i.e. once per command run, not once per batch). Within a
single `implement_plan` run, all N batches plus their per-batch review/boy-scout steps happen without
an intervening rebase — the rebase only happens at the **start** of the next invocation (a crash-resume
days later, or a fresh `/sdd:next` dispatch after other work landed on `main`). That is the actual risk
window for rebase interaction, and it has three concrete consequences:

1. **Never key resume logic to a captured SHA.** `pre_step_rebase.md`'s rebase step force-pushes a
   rewritten history (new SHAs for every replayed commit). `implement_plan.md:31`'s existing resume
   scan already avoids this correctly — it matches on the `[batch N]` **message prefix** in `git log`,
   never a stored hash. Any new review/boy-scout resume logic (§1e, §1f) must follow the same
   convention: search `git log --oneline` for the `[batch N boy-scout ...]` / review-marker prefix,
   never persist a SHA across a step boundary that might see a rebase in between (this also rules out
   option 2's "budget file keyed by commit SHA" variant in §1d — prefix-and-subject text search is the
   only rebase-safe form).
2. **The move-then-edit split (`idea.md:62-63`) matters most exactly at this multi-invocation boundary.**
   Within one run there's no rebase to survive, so the split's payoff is entirely about the *next*
   invocation's `pre_step_rebase` replaying batches 1..k's commits (including their boy-scout commits)
   via `git rebase --onto`. `research_boy_scout_rule.md`'s citations on git's heuristic rename detection
   apply directly here: a move-only commit (100% content similarity) rebases cleanly even if upstream
   `main` touched the file's *content* meanwhile, producing an ordinary single-file content conflict on
   the follow-on edit commit rather than a confusing delete+add pseudo-conflict on a combined
   move-and-edit commit.
3. **Per-batch (small, frequent) tidy-commits have a smaller rebase-conflict surface than one
   end-of-spec tidy-commit.** If review/boy-scout instead ran once at the end, all of a spec's tidy
   moves would land in one larger commit near the finish, right before Step 4. Per Google's Small-CLs
   reasoning (`research_boy_scout_rule.md` §1) and the boy-scout's own small budget (~3 files, 1 dep),
   the intent is clearly small-and-frequent, not large-and-rare — a single large "move everything"
   commit is a bigger, harder-to-resolve target for the next rebase (whether this branch's own
   `pre_step_rebase`, or a sibling worktree's later rebase onto this branch once merged, per
   `research_boy_scout_rule.md`'s parallel-worktree note in §5). This is an independent argument for
   per-batch boy-scout cadence beyond the "already settled" point — it would also argue for **not**
   batching the review-driven fixes into one commit at spec-end.
4. **`pre_step_rebase.md` Step 3's upstream-change scan already treats `[batch N]` commit messages as a
   machine-readable progress ledger** ("the scan file's commit list shows how far implementation has
   got through any `[batch N]` commits it lists," `pre_step_rebase.md:103-104`). Once boy-scout/review
   commits exist with their own prefixes sharing a batch's number, whatever parses that ledger
   (`upstream_change_scan.sh`, not read in this research) needs to expect that a `[batch N]` commit is
   not necessarily the *last* commit belonging to that batch anymore. This is a concrete detail for
   whoever specs the actual commit-message grammar, not something to resolve here.

## 3. Industry practice, briefly

Automated review tooling in the wild draws the same per-commit/per-push vs whole-PR distinction this
research is asking about, and the emerging consensus is a hybrid very close to the one this research
leans toward:

- **`reviewdog`** posts inline review comments from any linter's output, but deliberately **filters to
  changed lines only**, "cutting noise on incremental PRs" — i.e. it reviews incrementally, scoped to
  what's new, not the whole file/PR every time.
  [reviewdog on GitHub](https://github.com/reviewdog/reviewdog)
- **Danger** runs PR-level policy rules during CI (e.g. "every PR needs a changelog entry," "files in
  `/billing` need a billing-team reviewer") rather than per-commit — it's the "review the whole unit of
  work against project conventions" layer, complementary to line-level linters rather than a
  replacement for them.
  [Danger](https://danger.systems/ruby/)
- Broader 2026 guidance on AI/CI review bots converges on **incremental review on new work, with a
  full-diff pass gating merge**: "Don't re-review the entire PR on every push — only review the new
  commits since the last review," specifically to avoid re-reviewing the same PR five times as commits
  accumulate, "but the orchestrator dispatches... full for the final review before recommending a
  merge, so the pre-merge gate remains a full-diff pass."
  [CI: review only the diff since the last automated review (agent-harness #140)](https://github.com/dflippojr/agent-harness/issues/140)

This is structurally the same shape as the hybrid this research's §1 leans toward for the review
dimension: **cheap, scoped, incremental checks on each new unit of work** (reviewdog's changed-lines
filter ≈ this project's per-batch review scoped to that batch's own diff) **plus a final, whole-diff
gate before the work is considered done** (the "full for the final review before merge" pattern ≈ a
lightweight end-of-spec check reusing `docs/app_structure.md` and the accumulated git log, at Step 3).
No source found argues for *only* an end-of-spec/whole-PR pass with no incremental step, or *only*
per-commit with no final gate — every source that discusses cadence explicitly recommends both,
differing only in how heavy the incremental step is.

## Recommendation

1. **Boy-scout: keep it per-batch** (this is already settled by idea.md; this research just confirms it
   composes correctly with resume/rebase — §1f, §2 — and adds that the budget ledger should be derived
   from `git log`'s `[batch N boy-scout ...]` commit subjects, never a scratch counter file or a stored
   SHA, so it survives crashes and rebases alike (§1d, §2.1).
2. **Review dimension: run it per batch, immediately after that batch's boy-scout step (or immediately
   before it — see the ordering note in §1c), not deferred to end-of-spec.** The feedback-timing
   argument (§1b) — a later batch compounding an earlier batch's misplaced test or bad import — outweighs
   the spawn-count cost (§1a), because the rules are narrow enough that each per-batch review spawn is
   cheap, and because fixes are cheapest exactly when scoped to one just-landed batch rather than several.
3. **Add a lightweight, non-fan-out final check at Step 3** (not a second full review fan-out): re-read
   `docs/app_structure.md`'s test-only-edge table plus the accumulated boy-scout/review commit trail
   for the whole branch, to catch what per-batch checks structurally can't — the summed-across-batches
   budget (§1d), or a later batch re-introducing an edge an earlier batch's boy-scout removed. This
   mirrors industry practice's "incremental checks plus a final full-diff gate" (§3) at a fraction of
   the cost of running the full per-dimension fan-out twice.
4. **Resume must gain a third per-batch state** (§1f): not-implemented / implemented-but-not-yet-reviewed-
   or-boy-scouted / fully-done — following the same "resume mid-multi-step-sequence" shape
   `pre_step_rebase.md` Step 4 already uses for its own review step, rather than treating "`[batch N]`
   commit exists" as sufficient to skip a batch entirely.
5. **Never key any of this to a captured SHA** — only to commit-message prefixes searched fresh each
   time — because `pre_step_rebase` can rewrite every SHA on this branch between `implement_plan`
   invocations (§2.1).

## Files read

- `spec_dd/1. next/test-organisation-and-hygene-2-sdd-review-and-boy-scout/idea.md`
- `spec_dd/1. next/test-organisation-and-hygene-2-sdd-review-and-boy-scout/research_sdd_standards_hooks.md`
- `spec_dd/1. next/test-organisation-and-hygene-2-sdd-review-and-boy-scout/research_boy_scout_rule.md`
- `spec_dd/1. next/roadmap.md` ("Test organisation and hygiene" section)
- `claude_plugins/sdd/commands/implement_plan.md`
- `claude_plugins/sdd/commands/plan_from_spec.md` (Step 6)
- `claude_plugins/sdd/commands/protected/pre_step_rebase.md`
- `claude_plugins/fls-dev/commands/plan_structure_review.md`
- `claude_plugins/sdd/skills/claude-code-authoring/resources/fanout_recipe.md`
- `claude_plugins/sdd/skills/claude-code-authoring/resources/model_tiering.md`
- Web: [reviewdog](https://github.com/reviewdog/reviewdog), [Danger](https://danger.systems/ruby/),
  [CI: review only the diff since the last automated review](https://github.com/dflippojr/agent-harness/issues/140)

status: ok
