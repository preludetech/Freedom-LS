## Question

The idea (`spec_dd/1. next/git-rebase-safety/idea.md`) asks for a rebase step that, after `git
rebase main`, makes "a judgment call" about whether upstream changes are major enough to need "a
little research step" — and separately flags if those changes imply FLS is "heading in a different
direction in terms of architecture." This note is about how to make that judgment call concrete: what
counts as major/architecture-relevant here, how much of the answer is mechanical versus a genuine
judgment pass, and what "addressed" means once something is flagged. It does not cover the rest of
`git-rebase-safety`'s scope (test run, Playwright check on front-end changes) — see the roadmap row in
`spec_dd/1. next/roadmap.md`.

## What "major" means in this codebase

There is no single existing check for "did upstream change enough to warrant research," but three
existing SDD reviews already answer adjacent, narrower questions, and their signals compose into an
answer for this one:

- **Cross-app edges** — `/plan_structure_review` (`claude_plugins/fls-dev/commands/plan_structure_review.md`)
  treats `docs/app_structure.md` as "the authoritative picture of inter-app dependencies." A rebase
  that changed an app's imports, added an app, or moved code across the app boundaries listed in
  CLAUDE.md's "App Structure" section is exactly the kind of change that diagram exists to catch —
  it is architecture-relevant by the project's own definition of architecture.
- **Cross-app dependency direction** — the same diagram (`docs/app_structure.md`) enumerates every
  `A --> B` runtime edge and `A -.-> B` test-only edge for the current 27 apps. Diffing the rebase
  range's changed files against this table (which apps' files changed, and whether any newly-touched
  file imports across an edge the diagram doesn't have) is a cheap, mechanical proxy for "did the
  shape of the system change."
- **Insecure design choices** — `/plan_security_review` looks for the same class of structural
  concern from the security angle (raw SQL, missing auth, unvalidated input) before code is written.
  A rebase that lands such a change on `main` is a security-relevant "major change" even if it
  touches only one app.

Beyond those two existing dimensions, signals specific to judging an *already-landed* upstream diff
(rather than a not-yet-written plan) are:

- **Overlap with the in-flight spec's own footprint.** The spec/plan names files, apps or models it
  intends to touch (or the current branch's own diff already touches them). If the upstream diff's
  files intersect that set — same app, same model, same template, same view — the change is relevant
  regardless of size; if it lands in a completely disjoint app with no edge to the spec's apps in
  `docs/app_structure.md`, it is very unlikely to matter even if it is large.
- **Model and migration changes.** New/changed model fields, `related_name`s, or a changed base model
  (e.g. `site_aware_models`' base classes, `content_base`'s abstract content model bases, the
  content-type registry in `content_base`) ripple into every app that inherits from or registers with
  them. CLAUDE.md lists these as the shared foundations other apps build on, so a change there is a
  wider blast radius than a same-size change confined to a leaf app like `webhooks` or `mail`.
- **Changed skills or docs under `claude_plugins/` or `.claude/skills`.** CLAUDE.md states
  "documentation/skills are the source of truth for future development" and "if the code is
  structured in a way that contradicts what is documented in skills, the documentation is the source
  of truth." A changed skill (e.g. `fls-dev:multi-tenant`, `fls-dev:testing`, `ds:htmx`) is therefore
  itself a first-class architecture-direction signal, independent of how many lines of application
  code changed — it is upstream *telling* the branch the rules moved.
- **Changed conventions in `CLAUDE.md`** (root or a project's own) — the same reasoning: a convention
  edit is a declared direction change, not just a diff to review.
- **Newly-completed specs in `spec_dd/3. done/`.** A spec that finished on `main` while the branch was
  in flight is the most direct signal that "direction" moved: `spec_dd/1. next/roadmap.md` already
  tracks dependencies this way (a dependency is "met" when its directory appears under
  `spec_dd/3. done/`), and the roadmap's own per-effort sections (e.g. "Educator interface rebuild")
  record `Decisions already taken` that later specs must not reopen — a newly-done spec in the same
  effort is exactly the case where an in-flight spec's assumptions may now be wrong.
- **Diff size and commit count**, `git diff --stat base..main` and `git log --oneline base..main`,
  are the cheapest signal but the weakest on their own: a five-line change to a shared base class or a
  skill can matter more than a five-hundred-line change confined to a leaf app's templates. Size is a
  triage input, not a verdict.

## Cheap mechanical triage before the judgment pass

The model-tiering guidance in
`claude_plugins/sdd/skills/claude-code-authoring/resources/model_tiering.md` already draws this line
for the rest of SDD: mechanical, tool-driven, low-reasoning work runs on `sdd:sdd-mechanic` (Haiku);
anything that has to interpret an ambiguous result stays at depth 0 or moves to `sdd:sdd-worker`
(Sonnet) — "if a 'mechanical' step must interpret an ambiguous failure, keep that judgement at depth 0
and let Haiku only run-and-report." The same split applies here:

- **Mechanical (Haiku-safe):** `git merge-base main HEAD` to find the fork point, then
  `git diff --stat <merge-base>..main` and `git log --oneline <merge-base>..main` for the raw
  numbers; grouping the changed paths by top-level app directory (the same app list CLAUDE.md gives
  under "App Structure"); a grep for changed paths under `claude_plugins/**/skills/`,
  `claude_plugins/**/SKILL.md`, `CLAUDE.md`, and `docs/app_structure.md`; a check of whether any
  changed path matches a migration file (`*/migrations/*.py`) or a base-class module. All of this is
  "run a command, report the numbers" — no interpretation.
- **Judgment (Sonnet, or depth 0):** deciding whether the numbers add up to "major," whether an
  overlapping file actually changes something the in-flight spec depends on, and whether a changed
  skill or convention implies the spec's plan is now wrong rather than merely stale-but-compatible.
  This is the same distinction `/plan_structure_review` draws between edges it fixes by editing the
  plan directly versus edges it flags as a `> **Structure concern:**` callout for the user — "never
  auto-resolve ambiguity. When in doubt, flag it" (`claude_plugins/fls-dev/commands/plan_structure_review.md`).

Following the fan-out recipe (`claude_plugins/sdd/skills/claude-code-authoring/resources/fanout_recipe.md`,
mirrored in `SKILL.md`), a rebase command sitting at depth 0 can run the mechanical scan directly (or
via `sdd:sdd-mechanic`) and only spawn an `sdd:sdd-worker` for the "does this matter" pass when the
mechanical scan's numbers cross some threshold — cheap enough to run every rebase, expensive enough
that it should not run when nothing changed.

## What "addressed" looks like, by stage

The SDD writing standard (`claude_plugins/sdd/resources/writing_standard.md`) sets the shape any
research finding takes once produced: "detail worth keeping that does not belong in the artifact goes
into a sibling file in the same directory" — so an upstream-impact finding is a sibling file next to
whatever stage artifact exists (`idea.md`, `1. spec.md`, `2. plan.md`), never a new section bolted
onto them, and never process narration ("an earlier draft said...") inside the artifact itself.

What changes is *which* artifact gets edited, and by whom, depending on how far the spec has got:

- **Idea only, not yet a spec.** There is nothing downstream to invalidate yet. A flagged
  architecture-direction change is a note for whoever runs `/spec_from_idea` next — it belongs as
  context the next command reads, not as an edit to the idea's own decisions.
- **Spec or plan written, not yet implemented.** This is the same shape `/plan_structure_review`
  already uses for a live judgment call: insert a callout at the relevant section (its convention is
  `> **Structure concern:**`; an upstream-drift finding would use a comparable named callout, e.g.
  `> **Upstream change:**`) rather than editing the decision away, and let the user resolve it before
  planning/implementation continues. `/spec_review` (`claude_plugins/sdd/commands/spec_review.md`)
  is the existing precedent for "describe the problem, ask for input, edit the file" run repeatedly
  until no problems remain — the same loop applies to a spec whose assumptions an upstream change
  has undercut.
- **Partially implemented (mid-batch in `/implement_plan`).** `claude_plugins/sdd/commands/implement_plan.md`
  already has a resume model built on git: batches are marked by `[batch N] <summary>` commits, and a
  rebase mid-implementation risks conflicting with an in-progress batch's uncommitted work or an
  already-committed batch's assumptions. Here "addressed" means confirming completed batches still
  hold (their tests still pass post-rebase — the idea's own text: "we need to make sure we don't break
  anything... tests should pass") before continuing to the next batch, not rewriting the plan itself.
- **Implemented, in review/QA/ship stages.** `/address_pr_review`
  (`claude_plugins/sdd/commands/address_pr_review.md`) is the existing pattern for reconciling
  feedback against already-written code: classify each concern (it uses
  Bug/Correctness, Design/Architecture, Performance, Code Quality, Minor/Nit), state it, fix or ask.
  An upstream architecture-direction flag surfacing this late is treated the same way — as a
  Design/Architecture item raised against the diff, resolved or explicitly deferred with reasoning,
  never silently dropped.

Two habits recur across all of these and should carry over: never auto-resolve an architecture-level
ambiguity (`/plan_structure_review`'s rule), and record the outcome once, in the artifact whose reader
acts on it, not as a decision restated in a table and again in prose (the writing standard's "a
decision stated more than once").

## Prior art

External practice on "does this still make sense" for long-lived branches and plans converges on the
same three moves this section already derives from FLS's own conventions: cheap mechanical staleness
signals first, a judgment pass only when they fire, and a durable record of the decision rather than
silent adjustment.

- The "stale /plan problem" in coding agents: a plan file written early in a long task goes stale
  when the user's direction, the evidence gathered, or the underlying branch state moves without the
  plan being updated — branch-state drift specifically is "an agent dispatches a multi-hour task and
  by the time it finishes, main has moved twelve commits." (Arijit Dutta, *The "Stale /Plan" Problem
  in Coding Agents*, Medium, 2026 —
  https://medium.com/@arijitdutta23/the-stale-plan-problem-in-coding-agents-cde2c741f8ab)
- A harness-level pattern for catching branch drift cheaply: re-read HEAD SHA, branch name and
  working-tree dirty status every turn, diff against the previous turn's snapshot, and treat an
  unexpected move as a "context-invalidating event" that blocks further edits until the divergence is
  surfaced — cheap comparison first, refusal/flag as the judgment response, not silent
  reconciliation. (TianPan.co, *The Branch State Your Coding Agent Forgot to Check*, 2026 —
  https://tianpan.co/blog/2026-06-01-the-branch-state-your-coding-agent-forgot-to-check)
- Architecture-decision drift detection in git history uses cheap, purely mechanical git signals to
  decide when a documented decision needs a second look: co-change bursts across the decision's
  governed files and adjacent modules, changes to public interfaces (routes, events, config
  surfaces), ownership turnover on the governed files, and commit messages containing words like
  "temporary workaround" or "bridge until migration." None of these require reading the decision's
  prose to compute — they are the triage pass before a human (or agent) judgment pass reads the
  actual diff. (repowise.dev, *Architecture decision records workflow: catch stale ADRs*, 2026 —
  https://repowise.dev/blog/guides/use-git-history-to-catch-stale-adrs-before-they-mislead-agents)
- The complementary point from the ADR-automation literature: documentation alone does not stop
  drift, only checks that run do — "if an ADR says X, a fitness function can detect a violation and
  fail the build" — which is the same argument this project already makes for
  `docs/app_structure.md` and `/plan_structure_review`: the diagram is checked against the plan
  mechanically, not just read. (DEV Community, *Stop Architecture Drift: Operationalizing ADRs with
  Automated Fitness Functions*, 2026 —
  https://dev.to/alexandreamadocastro/stop-architecture-drift-operationalizing-adrs-with-automated-fitness-functions-22oi)

status: ok
reason: research complete
