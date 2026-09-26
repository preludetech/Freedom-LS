# SDD review and boy-scout for test organisation

Spec 2 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Wire the two test-organisation rules from `test-organisation-and-hygene-1-testing-standards` into
`implement_plan` itself, so new work is written and reviewed to the standard rather than added to
the pile the other twelve specs clean up.

Three pieces:

1. `implement_plan`'s batch worker gets a real agent file. It preloads the project's testing
   skills (here `ds:testing` and `fls-dev:testing`) and replaces today's bare
   `subagent_type: "general-purpose"` spawn. This is the pattern
   `claude_plugins/fls-dev/agents/qa-bugfixer.md` already uses.
2. A test-organisation review dimension runs against each batch inside `implement_plan`, checking test
   placement and cross-app test imports against `docs/app_structure.md`, on the same fan-out shape
   `plan_from_spec.md` Step 6 already uses for plan review.
3. A boy-scout agent runs per batch, scoped to that batch's own `[batch N]` commit's touched files. It
   tidies test organisation in them and flags obvious, genuinely broken code it sees, without fixing it.

## Why

`implement_plan.md`'s batch worker is a bare `general-purpose` subagent today. It has no `skills:`
slot, so the two rules reach it only if skill auto-trigger happens to fire. Nothing in the SDD flow
reviews implemented code or tests once a spec is built. `plan_from_spec` Step 6 reviews the plan
text, not the code it produces, and `/ds:security-review` covers security only. Without this spec,
every future spec re-accumulates exactly the disorganisation the other twelve specs in this effort
exist to remove.

## What is settled

- The two rules and the conftest/fixture/factory layering material live in `ds:testing`; this spec
  does not restate or re-derive them, only loads and checks them inside `implement_plan`.
- The batch worker runs from a new agent file that preloads the project's testing skills, replacing
  the `subagent_type: "general-purpose"` spawn in `implement_plan.md` Step 2. In this project those
  are `ds:testing` and `fls-dev:testing`.
- The test-organisation review is a fan-out dimension inside `implement_plan`: one `sdd:sdd-worker`
  per dimension, writing a `.sdd-work/` file with a `status:` footer, not a new `todo.md` line and
  not a new entry in `setup_todo_list.md`'s template. This way it doesn't widen the `sdd` ↔ `fls-dev`
  coupling `claude_plugins/sdd/README.md` already documents.
- The review checks the batch's diff against `docs/app_structure.md`'s existing Runtime-deps /
  Test-only-deps columns. This is the same table `plan_structure_review.md` already parses. It
  invents no new dependency data.
- The boy-scout step is scoped to exactly one batch's own `[batch N]` commit, found from that commit
  alone (`git show --name-only`). It never runs a wider scan.
- The boy-scout fixes test organisation only: moving or renaming a touched test file to mirror the
  app hierarchy, removing a cross-app test dependency the batch itself introduced, splitting a touched
  over-grown test module. It changes no assertions and touches no file outside the batch's commit.
- In the files it touches, the boy-scout also flags obvious, genuinely broken code without fixing it.
  When a flagged item turns out not to be a bug, a code comment at that spot says why, so it is not
  flagged again.
- The boy-scout's guardrails are the effort's assumption, not this spec's to reopen. Touched means
  files the batch's own commit added or edited. Only mechanical, behaviour-preserving moves are
  allowed. The budget is about 3 test files moved and 1 cross-app dependency removed per branch. Past
  that budget, the boy-scout records a follow-up against the matching cleanup spec in the roadmap
  (specs 4-15) instead of doing the work, or a new idea under `spec_dd/1. next/` once no cleanup spec
  covers that app. The boy-scout makes its own labelled commit, separate from the batch's feature
  commit. It makes a move in one commit and the accompanying edit in the next, so git's rename
  detection survives rebase. What it tidied and what it deferred gets reported in the spec's PR.
- Whichever of this spec and `test-organisation-and-hygene-3-enforcement-checks` lands second makes
  the review step run the other's checks. If spec 3's pre-commit/CI checks land first, this spec's
  review dimension calls them. If this spec's review lands first, spec 3 wires its mechanical checks
  into it.

## Open until the spec

- Two things are open here. Where a flagged bug is reported: the PR body, a `.sdd-work/` file, or an
  inline comment. Who decides a flagged item is not a bug: the boy-scout agent itself, leaving the
  explanatory comment unchallenged, or a human at PR review.
- Whether a project names which skills the batch worker and reviewer preload through the agent file's
  `skills:` frontmatter directly (as `qa-bugfixer` does today, hard-coding `ds:testing` and
  `fls-dev:testing`), or through some project-level indirection. This matters because `sdd` is meant
  to stay generic across projects that may not have an `fls-dev`-shaped overlay skill. If hard-coding
  two skill IDs into an `sdd`-owned agent file doesn't warrant a generic naming mechanism, the spec
  should say so plainly and record it as the same kind of documented coupling
  `claude_plugins/sdd/README.md` already carries, rather than solving it.
- Whether the review dimension fans out once per batch, alongside the boy-scout step, or once at the
  end of `implement_plan`'s Step 3 over the whole spec's diff.
- Whether the boy-scout runs as its own new agent file or as an `sdd:sdd-worker`-shaped spawn given
  `Edit`/`Bash` breadth, and the same choice for the batch-implementer agent file.

## Out of scope

- Pre-commit or CI enforcement of either rule (`test-organisation-and-hygene-3-enforcement-checks`).
- Cleaning up any app's existing tests (specs 4-15).
- The boy-scout fixing anything beyond test organisation, or any big-bang cleanup.
- Gating "every module has a test", or reviewing general test quality (assertions, redundancy,
  coverage).

## Resources

- `research_sdd_standards_hooks.md` (this spec's directory): how each SDD phase loads skills today,
  why `implement_plan`'s batch worker has no `skills:` slot, and the concrete hook points for the new
  agent file, the review fan-out and the boy-scout step.
- `research_boy_scout_rule.md` (this spec's directory): the Boy Scout Rule / opportunistic-refactoring
  sources and the size, commit-shape and rebase-safety guardrails this spec's assumptions are drawn
  from.
- `claude_plugins/sdd/commands/implement_plan.md`, `claude_plugins/sdd/commands/plan_from_spec.md`
  (Step 6): the existing batch and fan-out shapes this spec extends.
- `claude_plugins/fls-dev/agents/qa-bugfixer.md`: the `skills:` frontmatter and structured-report
  pattern the new agent files follow.
- `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md`: the subagent and model-tiering
  constraints the new agent files must respect.
- `docs/app_structure.md`: the dependency table the review consumes for the second rule.
