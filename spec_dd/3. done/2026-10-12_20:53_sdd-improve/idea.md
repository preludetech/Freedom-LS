# SDD: run longer without a human

## The problem

The SDD pipeline stalls on human input far more often than the work needs. The checklist that
`/sdd:start` writes has 18 `(user)` items against 16 `(cmd)` items. In the 59 specs finished since
August the owner ticked about 9% of the review gates and ran the commands by hand rather than through
`/sdd:next`. Four commands in the checklist have not been run since July: `/ds:threat-model`,
`/fls-dev:plan_security_review`, `/fls-dev:plan_structure_review` and `/ds:security-review`. The
questions commands ask are mostly front-loaded already. The stalls come from gates nobody uses, steps
nobody runs, and a few late questions with an obvious default.
`research_where_the_pipeline_stalls.md` has every stop point per command and the counts.

## What we are doing

Fewer commands, each running longer, asking everything it needs once and early, and a checklist that
lists only what happens. The human reviews at three points, by running the next command when they are
satisfied: after the spec, after the plan, and after implementation and QA. Everything else is a
checkpoint they can read later from the committed artifacts.

## Settled decisions

### Questions are asked once, early, with a default

Every command that can ask does so in one batch at the start, while its workers run. It asks only
about things that change the artifact, that nothing on disk answers, and that have no obvious default.
A question that surfaces later in the same command takes the recommended default, and the command
records that choice in the artifact, under the spec's open questions or as a callout in the plan.
Each question carries a recommended answer and why it matters, so the human can accept it in one
word. spec-kit's `clarify` step is the model (`research_autonomous_pipeline_patterns.md`). Workers
never ask. The command answers a `blocked` worker from the idea, the code or another worker's output
before it turns to the human.

### `/sdd:next` goes

The owner runs commands by hand, so `/sdd:next` is deleted and every "skip this when `/sdd:next`
already ran it" clause goes with it. `todo.md` stays as the per-spec checklist: commands tick their own
box, the human ticks `(user)` items, and `/sdd:make_pr_quickly` reads the boxes for the PR body. The
template shrinks to the commands that run and the `(user)` items that are real decisions:

- `(cmd)` `/sdd:spec_from_idea`, then `(user)` review the spec, with `/sdd:spec_review` as an
  optional command for after hand edits
- `(cmd)` `/sdd:plan_from_spec`, then `(user)` review the plans
- `(cmd)` `/sdd:implement_plan`, `(cmd)` `/fls-dev:do_qa`, then `(user)` review the code and the
  QA report, and act on any `Decide` items QA filed
- `(cmd)` `/sdd:document`, `(cmd)` `/sdd:make_pr_quickly`, `(cmd)` `/sdd:address_pr_review` as
  feedback arrives, then `(user)` confirm the PR is approved
- `(cmd)` `/sdd:finish_worktree`, then `(user)` remove the worktree

Gone from the template: the optional improve-idea item and its review, the separate spec review and
its follow-up, the threat model, the plan security review, the plan structure review, the code
security review and its post-QA re-run, "spot-check the changes", "fix bugs using TDD" (QA does it),
"open a pull request" as a human act, and the three separate documentation sections. An item a
command adds at run time is `(user)` or `(cmd)`, never both. An observation with no action, such as
"no QA needed", is not an item.

### One idea-to-spec command

`/sdd:spec_from_idea` absorbs `/sdd:improve_idea`, which goes. One research wave covers the
idea-level topics, prior art, UX patterns and known complaints, together with the spec-level ones,
codebase, best practices and reference implementations. Durable findings keep their
`research_<topic>.md` names next to the idea. The idea file is not rewritten; the spec is the
refinement. One batch of questions runs while the workers do.

After the command writes and commits the spec, a second wave of review workers checks it, one per
dimension: contradictions and completeness against the idea and its siblings, feasibility and project
norms, vocabulary, the generic-plugin rule, and cut-list candidates. The command applies the clear
fixes, runs one bounded re-check, and puts the judgement calls to the human in a single batch at the
end. The dimension list lives in one sdd resource that `/sdd:spec_review` also reads, so the
standalone command stays available for a spec the human has edited by hand, without duplicated text.

### Plan review hooks replace the separate plan reviews

`/sdd:plan_from_spec` already fans out review dimensions over the finished plan. It gains a
repeatable `## Plan Review Hooks` entry in `.claude/sdd/config.md`. Each value is a brief file a
worker reads and follows, writing its findings beside the built-in dimensions. FLS supplies two
briefs in `claude_plugins/fls-dev/resources/`:

- the structure check, which is the existing scan from `plan_structure_review` moved into a brief
- a new-threats check that looks only at what the plan adds: a new view or endpoint, a
  state-changing request, user input, rendered user content, a redirect target, a file upload, an
  outbound call, a role or permission, or an ORM escape hatch. For each it asks one narrow question.
  Is it scoped to the user, is it validated, is it escaped, is the credential in the environment.
  The generic triggers and checks live in sdd. The FLS ones, site-aware base, storage alias,
  registration-form rules and consent, live in the brief. No hits is the normal result and produces
  nothing. Rate limiting, audit logging, dependency reputation and severity scales are out; they are
  what made the old commands feel paranoid. `research_security_review_retirement.md` has both
  checklists.

The command edits clear fixes into the plan. Judgement calls become `> **Structure concern:**` or
`> **Security concern:**` callouts in the plan, and the command puts them to the human in its single
end-of-run batch, recommended option first.

`/ds:threat-model`, `/ds:security-review`, `/fls-dev:plan_security_review` and
`/fls-dev:plan_structure_review` are deleted, with every reference to them. Bandit already runs in
pre-commit. Nothing in SDD replaces dependency or secret scanning; Claude Code's built-in
`/security-review` is still there for ad hoc use.

### A per-batch reviewer in `/sdd:implement_plan`

Today nothing reviews a batch's code. The Design check compares screenshots, and no SDD command calls
`ds:code-reviewer`. A new review runs after each `[batch N]` commit, bounded to that commit's diff,
with two concerns and no others:

- comments and docstrings: planning-document pointers (section signs, spec, slice, batch, phase and
  QA bug numbers, `spec_dd/` paths), implementation-history narration, and comments that restate the
  code. A `TODO` or `@claude` comment is rewritten, never deleted.
- tests: the project's test standard as the testing skills define it. Factories, not
  `objects.create`. `reverse()`, not literal URLs. Site-aware fixtures, the marker taxonomy, no
  control flow in a test body, no test whose only assertion is a 200, one behaviour per test, mocks
  at boundaries only.

A mechanic runs the greppable rules on added lines. One worker with a closed checklist runs the
judgement rules, and its brief tells it not to review security, performance, architecture or design.
Findings spawn a `[batch N] review fix n` batch, capped at two like the Design check. Whatever
survives the cap goes into the final summary and the run continues. The implementer's own brief also
names the test standard, so the reviewer is the second line, not the first. Project rules reach the
generic command through a `## Review Hooks` section in `.claude/sdd/config.md` with `Comment
standard` and `Test standard` entries pointing at the skill files.
`research_implementation_reviewer.md` has the greppable-versus-judgement split.

### One documentation command

A generic `/sdd:document` runs after QA and follows each entry under `## Documentation Hooks` in
`.claude/sdd/config.md`, in order, inline at depth 0. It cannot hand a hook to a worker, because a
worker cannot fan out and product docs fan out per document. For FLS the order is app map, upgrade
notes, product docs, course-author plugin sync. In hook mode a command skips its own pre-step rebase
and todo tick and keeps its own commit, so each hook is its own resume marker. "Only if needed" is
already how the app map and the plugin sync behave: a clean check or an empty grep costs nothing. A
failing hook is reported and the rest still run. `/fls-dev:update_upgrade_notes` stays runnable on
its own for the post-PR-review re-check.

### Late questions that become defaults

- `/sdd:implement_plan` no longer raises plan doubts with the user before starting; the plan was
  reviewed. A design miss that survives two fix batches is recorded for QA instead of ending the run.
- `/sdd:finish_worktree` does not ask whether to re-run QA after the rebase. It runs the full tier
  and lets the existing guard stop on failure.
- `/sdd:commit_quickly` defaults to the files this conversation touched.
- A command that asks which spec directory it is in resolves it from the branch name instead.
- `/sdd:address_pr_review` skips a comment with its reason in the summary instead of asking first.

### Stops that stay

A real secret in a commit, an incompatible rebase conflict, a dirty main worktree, an upstream change
whose review says `direction: changed`, design-tool authorisation, roadmap precursor warnings, the
`Decide` items QA files for red-lane bugs, and PR approval.

### The generic rule holds

Every FLS value above reaches sdd through `.claude/sdd/config.md`: three new hook sections, which
`/sdd:init` creates and validates like the existing ones. `research_merging_steps.md` lists every
file that references a removed or merged command.
