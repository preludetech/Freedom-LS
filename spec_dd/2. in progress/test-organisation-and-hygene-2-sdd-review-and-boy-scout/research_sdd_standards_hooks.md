# Research: wiring test-organisation rules + boy-scout cleanup into the SDD workflow

Scope: how the SDD phases discover skills/steps today, where review and test-writing already happen,
where the plugin boundary should put the two new rules, and the best hook points for enforcement +
boy-scout cleanup. No web research — this is entirely a read of `claude_plugins/` and `.claude/` in
this repo.

## 1. How each SDD phase discovers skills and project-specific steps today

**Skills auto-trigger by description** (native Claude Code behaviour) or are **preloaded** via an
agent file's `skills:` frontmatter (`claude_plugins/sdd/skills/claude-code-authoring/SKILL.md:38-39`).
There is no SDD-specific "skill discovery" mechanism beyond that — every command/agent either lets a
skill trigger itself, or explicitly says "read `Skill(x:y)`" / lists it in `skills:`.

**Per-phase specifics:**

- **`spec_from_idea`** (`claude_plugins/sdd/commands/spec_from_idea.md` — not fully read here, but
  referenced from `spec_review.md:51`) and **`spec_review`**
  (`claude_plugins/sdd/commands/spec_review.md`) read **every file under `${CLAUDE_PLUGIN_ROOT}/resources/`**
  of the *sdd* plugin only (`spec_review.md:27`) to check the spec against "project norms" — this is
  scoped to `sdd`'s own resources, not `ds`'s or `fls-dev`'s. It also checks
  `${CLAUDE_PLUGIN_ROOT}/resources/domain_vocabulary.md` (`spec_review.md:29`).
- **`plan_from_spec`** (`claude_plugins/sdd/commands/plan_from_spec.md`) has an explicit **Step 4:
  "Skills/MCP scan"**: it fans out one `sdd:sdd-worker` to scan "the available skills and MCPs" (no
  further scoping given in the command file — the worker is expected to discover installed skills
  itself) and fold findings into the plan (`plan_from_spec.md:45-47`). This is the one place a plan
  is told what skills to reach for, generically, across all installed plugins.
- **`implement_plan`** (`claude_plugins/sdd/commands/implement_plan.md`) does **not** name any skill
  explicitly. Each batch is a `general-purpose` subagent (`implement_plan.md:28`), which has no
  `skills:` frontmatter to preload anything — it relies entirely on the plan text (written in Step 4
  above) telling it what skills/conventions apply, plus whatever skill descriptions happen to
  auto-trigger from the plan's own wording. **This is a gap**: unlike `qa-bugfixer`
  (`claude_plugins/fls-dev/agents/qa-bugfixer.md:8-10`, which preloads `ds:testing` +
  `fls-dev:testing` via `skills:` frontmatter), the `implement_plan` batch subagent has no dedicated
  agent file and thus no `skills:` frontmatter slot to pin testing skills into.
- **`address_pr_review`** (`claude_plugins/sdd/commands/address_pr_review.md`) names no skills at
  all; it fetches PR comments and fixes them ad hoc.
- **`finish_worktree`** (`claude_plugins/sdd/commands/finish_worktree.md`) and the **protected
  helpers** (`commands/protected/*.md`) are pure mechanics (git, `update_todo.md`, config reads) —
  no skill involvement.
- **`next`** (`claude_plugins/sdd/commands/next.md`) is a dispatcher: it resolves a `todo.md` line's
  `/prefix:command` to a file via a **hard-coded map** `{sdd, fls-dev, ds}` → commands dir
  (`next.md:44-53`) and inlines that file at depth 0. It injects no skills itself; it just runs
  whatever command the `todo.md` names.

**How a project injects extra steps today (the `plan_structure_review`/`plan_security_review` case):**
There is **no generic extension point**. The `todo.md` template that determines which commands run,
in what order, is **hard-coded inside the nominally-generic `sdd` plugin**, at
`claude_plugins/sdd/commands/protected/setup_todo_list.md:76-129`. That template literally writes
`/fls-dev:plan_security_review`, `/fls-dev:plan_structure_review`, `/fls-dev:do_qa`,
`/fls-dev:update_product_docs`, `/fls-dev:update_upgrade_notes`, `/fls-dev:update_claude_plugin_fls_content`,
and `/ds:threat-model` / `/ds:security-review` directly into the checklist. `sdd:next` then dispatches
each by the hard-coded prefix map. The `sdd` plugin's own README says this outright:

> **Coupling note.** `sdd` is not yet fully standalone: the `setup_todo_list` template and the
> `next.md` dispatcher name FLS-specific steps (`/fls-dev:*`), and FLS commands spawn the `sdd`
> agents. Untangling this bidirectional `fls-dev` ↔ `sdd` dependency is deferred.
> — `claude_plugins/sdd/README.md:12-14`

So today, "inject a step" = **edit `setup_todo_list.md`'s markdown template directly** and add the
new command name with its owning-plugin prefix (the prefix map in `next.md:44-53` already resolves
`sdd`/`fls-dev`/`ds`, so no dispatcher change is needed as long as the new command lives in one of
those three plugins). There is no config-driven or manifest-driven registration of extra phases —
config files (`.claude/sdd/config.md`, `.claude/fls-dev/config.md`) only carry **data** (worktree
scripts, vocab sources, dev credentials), never step lists.

## 2. Where code review happens today, and where tests are written

**Code review:**
- `claude_plugins/django-stack/agents/code-reviewer.md` — the general-purpose, user-invoked review
  agent (`model: opus`, `tools: Glob, Grep, Read, WebFetch, WebSearch`). Reviews diffs against
  Critical/Important/Nice-to-have buckets (security, missing tests, ORM misuse, HTMX conventions,
  type hints, etc. — `code-reviewer.md:67-113`). It is **not wired into the SDD `todo.md` flow** —
  it's invoked directly by the user ("review my changes"), not by any `/sdd:*` command.
- Inside the SDD flow itself, the closest things to "review" are the **plan-time** reviews:
  `plan_from_spec`'s own **Step 6** fans out one `sdd:sdd-worker` per review dimension over the plan
  text (success criteria met, no skill contradictions, no junk files, clean code, vocabulary match —
  `plan_from_spec.md:79-90`), plus the two fls-dev plan reviews
  (`claude_plugins/fls-dev/commands/plan_security_review.md`,
  `claude_plugins/fls-dev/commands/plan_structure_review.md`), which review the **plan**, not code.
  Post-implementation, `/ds:security-review` reviews the **diff** for security issues only
  (README step 5). There is currently **no SDD-flow step that reviews the implemented code (or its
  tests) for structure/organisation/hygiene** — that gap is exactly what this idea wants filled.
- `sdd-worker`/`sdd-mechanic` never review code themselves; they are fan-out/mechanic executors.

**Where test code gets written:**
- **`implement_plan`**'s batch subagents (`subagent_type: "general-purpose"`, `model: "sonnet"` per
  spawn — `implement_plan.md:28`) write both production and test code, following TDD as directed by
  the plan (`plan_from_spec.md:68`: "We will be following TDD... Include pseudocode... don't write
  out all the tests at this point"). These subagents have **no dedicated agent file** and hence no
  `skills:` frontmatter — they rely on the plan's own prose plus skill auto-trigger.
- **`fls-dev:qa-bugfixer`** (`claude_plugins/fls-dev/agents/qa-bugfixer.md`) also writes tests, during
  `/fls-dev:do_qa`'s bug-fix loop: one failing test per bug, TDD, commit. This agent **does** preload
  `ds:testing` + `fls-dev:testing` via `skills:` frontmatter (lines 8-10) and is explicit that "the
  `ds:testing` and `fls-dev:testing` skills are the authority on how tests are written here" (line 48).
  It is the best-instrumented existing example of a test-writing subagent.
- The two testing skills themselves (`claude_plugins/django-stack/skills/testing/SKILL.md` and
  `claude_plugins/fls-dev/skills/testing/SKILL.md`) currently say **nothing** about file-hierarchy
  mirroring beyond "Test files: `<app>/tests/test_<module>.py`" (ds:testing line 20) /
  "FreedomLS tests live at `freedom_ls/<app_name>/tests/test_<module>.py`" (fls-dev:testing line 15)
  — i.e. flat "one `tests/` dir per app", not "mirror the app's internal module hierarchy". Neither
  skill says anything about rule 2 (an app's tests should only depend on apps the app itself depends
  on).

## 3. Where the two rules should live, given the plugin boundaries

Both rules are **generic Django project hygiene**, not FreedomLS-specific — they belong in
**`ds:testing`** (`claude_plugins/django-stack/skills/testing/SKILL.md` +
`claude_plugins/django-stack/resources/testing.md`), the same plugin that already owns "Test files:
`<app>/tests/test_<module>.py`" and the collection-safety/marker material every downstream project
needs. `fls-dev:testing` is explicitly "the FreedomLS overlay" that "does not repeat the generic body"
(`claude_plugins/fls-dev/skills/testing/SKILL.md:9`) — it should only get a one-line pointer back to
`ds:testing` if FLS's own directory layout needs a note (it already states its own path convention at
line 15, so it may need a one-line update to say "the hierarchy mirroring below is inherited from
`ds:testing`", not a restatement of the rule).

Rule 2 (an app's tests only depend on apps the app depends on) is **exactly** what
`docs/app_structure.md`'s test-only-edge column already tracks (see §5) — so the rule's *data source*
(the dependency graph) is `ds:app_map`'s output (`claude_plugins/django-stack/commands/app_map.md`,
`claude_plugins/django-stack/scripts/generate_app_map.py`), and the rule's *statement* belongs beside
it: `ds:testing`, cross-referencing `app_map`.

The SDD *workflow* changes (apply-while-writing, check-in-review, boy-scout) belong in **`sdd`**
itself, since `implement_plan` and any new review step are `sdd`-owned commands — but note the
existing coupling problem from §1: if the boy-scout / review-dimension step needs `docs/app_structure.md`
(an `ds`-owned artifact) or the `fls-dev:testing` overlay, `sdd` is *already* not fully standalone
(its own README documents this), so referencing `ds:app_map` and `ds:testing`/`fls-dev:testing` from an
`sdd` command is consistent with the existing (documented, deferred-cleanup) coupling, not a new
violation. Prefer implementing the hook points as **skill content + a review dimension list**, which a
generic `sdd` command can reference by name without hard-coding another plugin's command path (the
existing `plan_structure_review`/`plan_security_review` precedent hard-codes full command names into
`setup_todo_list.md`; a new review *dimension* inside `implement_plan`'s or a new command's existing
fan-out loop is a lighter-weight injection that doesn't need a `setup_todo_list.md` edit at all — see
§4).

**Plugin-sync / downstream copy mechanism:** There is **no** file-copy mechanism between `ds`,
`fls-dev`, and `sdd` — each plugin's skills/resources are simply read directly via
`${CLAUDE_PLUGIN_ROOT}` at runtime (no build step, no generated mirror). The only two "sync" flows
in this repo are unrelated to plugin-file duplication:

1. `claude_plugins/fls-dev/commands/update_claude_plugin_fls_content.md` — syncs the separate
   **`fls-content`** plugin's reference skills when FLS's own authoring-relevant *code* (schemas,
   cotton templates, widget allowlists) changes. Not applicable here — it mirrors FLS *content-authoring*
   schema, not testing conventions.
2. `claude_plugins/fls-dev/commands/concrete/update_fls.md` — the **downstream "concrete" project**
   integration flow: a concrete project vendors FLS as a git submodule and walks each completed
   `spec_dd/3. done/` spec's `upgrade_notes.md` to integrate it. This is a **spec/feature** sync (code
   + migrations + settings), not a **plugin skill-file** sync. `claude_plugins/fls-dev/commands/concrete/README.md`
   confirms these commands are "specifically for concrete implementations of FLS."

**Practical implication:** since there is no copy mechanism, editing `ds:testing` (skill +
`resources/testing.md`) and `docs/app_structure.md`'s consumers directly changes behaviour for every
project that has the `django-stack` plugin installed — no downstream file needs separate updating.
The one place that *would* need a mirrored update, if the boy-scout/test-org convention becomes
authoring-relevant enough to matter to `fls-content` authors (unlikely for pure test-hygiene rules),
is `update_claude_plugin_fls_content.md`'s watched-path list — but test organisation is not among the
paths it watches (content-base, content-engine, form-engine, cotton templates, widget allowlists, demo
content), so no update is needed there for this idea.

## 4. Best hook points

### 4a. Applying the rules while writing tests (implement_plan)

Two complementary levers, in order of leverage:

1. **Skill content** — add both rules to `ds:testing`'s `SKILL.md` "Key rules" section
   (`claude_plugins/django-stack/skills/testing/SKILL.md:18-29`) and expand
   `claude_plugins/django-stack/resources/testing.md` with a worked "mirror the app hierarchy" example
   and a worked "don't import a sibling app's factory unless the app depends on it" example (parallel
   to the existing collection-safety worked example at `resources/testing.md:271-311`). Because the
   skill auto-triggers on "pytest"/"TDD"/"test" mentions, this reaches `implement_plan`'s batch
   subagents even though they have no `skills:` frontmatter — but auto-trigger is probabilistic, so:
2. **Give the `implement_plan` batch subagent a `skills:` preload**, the same pattern `qa-bugfixer`
   already uses (`claude_plugins/fls-dev/agents/qa-bugfixer.md:6-11`). Today `implement_plan.md:28`
   spawns a bare `subagent_type: "general-purpose"` with no agent file of its own — it cannot carry
   `skills:` frontmatter. The fix is to give the batch worker its **own agent file** (e.g.
   `claude_plugins/sdd/agents/sdd-implementer.md`, tools matching what `implement_plan.md:28`'s prose
   already asks for — Bash/Edit breadth — plus `skills: [ds:testing, fls-dev:testing]`), and point
   `implement_plan.md` Step 2 at `subagent_type: "sdd:sdd-implementer"` instead of the bare
   `general-purpose` type. This is a small, surgical change consistent with the existing tiering
   pattern (`claude-code-authoring` SKILL.md's "Model resolution order" — agent-file `skills:` is
   inert on a bare `general-purpose` type, live once it has its own file).
3. **A `PostToolUse` hook is precedented but not the right tool for rule 2.** `django-stack` already
   ships real Claude Code hooks (`claude_plugins/django-stack/hooks/hooks.json`): `ruff_fix.sh` and
   `post-edit-bandit.sh` on `PostToolUse` for `Edit|Write`, and `security-guard.sh` on `PreToolUse` for
   `Bash|Write|Edit` (pattern-blocking raw SQL, `mark_safe`, etc. —
   `claude_plugins/django-stack/scripts/hooks/security-guard.sh`). This is a different "hooks" concept
   than the one the `claude-code-authoring` skill defers ("hooks... adopting them is explicitly out of
   scope for **the current [SDD orchestration] workflow**" — `resources/interactive_cli.md`, referenced
   at `SKILL.md:79`); that deferral is about not using Claude-Code hooks to orchestrate *SDD phase
   transitions*, not a ban on `ds`/`fls-dev` shipping code-quality hooks the way they already do. Rule
   1 (path mirrors hierarchy) is a **cheap, mechanical, per-file check** well suited to a small new
   `PostToolUse` hook script (check a newly written `test_*.py`'s path against its app's source module
   layout) — a natural sibling to `ruff_fix.sh`. Rule 2 (cross-app test import) needs the same
   AST-based app-resolution logic `generate_app_map.py` already has
   (`claude_plugins/django-stack/scripts/generate_app_map.py:82-118`) run against a single new/edited
   file's imports, compared to `docs/app_structure.md`'s per-app runtime-dep row — feasible as a
   `PostToolUse` hook (warn, don't block, since a legitimate new test-only edge might be an intentional,
   to-be-approved addition) but noticeably more code than the pattern-string hooks that exist today. If
   a hook is out of scope for this first spec (per the idea: "first spec is about setting up the skills
   and best practices"), the skill-content + agent-`skills:`-preload combination above (1+2) is the
   minimum viable version; the hook is a natural *follow-up* spec, and should be scoped as such rather
   than folded into this one.

### 4b. Checking the rules in review

There is currently no SDD-flow step that reviews *implemented* code/tests at all (§2) — `implement_plan`
Step 3 ("Final Verification") only re-checks the plan's own success criteria
(`implement_plan.md:47-53`), and `/ds:security-review` is security-only. The cleanest new hook point is
a **review dimension added to `implement_plan`'s Step 3**, following the exact fan-out pattern
`plan_from_spec.md` Step 6 already uses for plan review (`plan_from_spec.md:77-90`): after all batches
land, spawn one `sdd:sdd-worker` per dimension against the **implementation diff** (`git diff main...HEAD`
or the batch commit range) — one dimension being "new/moved test files mirror the app hierarchy; no
test in app A imports fixtures/factories/models from an app A doesn't runtime-depend on per
`docs/app_structure.md`" — writing findings to `.sdd-work/implement_review_<dim>.md` with the standard
`status:` footer, same resume/retry/blocked handling as every other SDD fan-out. This slots into the
**existing** Step 3 loop ("Check each success criterion... If any criterion is unmet: fix it with a
sub-agent" — `implement_plan.md:52-53`) rather than requiring a new top-level command or a
`setup_todo_list.md` edit, so it avoids adding to the `sdd` ↔ `fls-dev` coupling problem noted in §1.
`ds-code-reviewer` (`claude_plugins/django-stack/agents/code-reviewer.md`) already lists "Missing tests"
and "Code duplication" as Important-tier findings (lines 76, 79) and could gain a "Test organisation"
bullet in the same list for the user-invoked review path, but since that agent is not wired into the
`todo.md` flow today, it should not be the *only* enforcement point.

### 4c. The boy-scout step

**Where the touched-files set is known:** each `implement_plan` batch ends in its own
`[batch N] <summary>` commit, made by the batch subagent itself
(`implement_plan.md:24,33-35` — "Committing inside the worker keeps the work and its completion marker
atomic"). That commit is the natural boundary: `git show --name-only --pretty=format: <batch-N-sha>` (or
`git diff --name-only main...HEAD` for the whole spec, once every batch has landed) gives exactly the
files this run touched, without inventing new bookkeeping.

**How to scope a boy-scout subagent to "files this batch touched":**
- Add a **Step 2.5** to `implement_plan.md`, run once per batch immediately after that batch's commit
  lands (`ok` verified per `implement_plan.md:38`): compute the batch's touched-file list from its own
  commit (`git show --name-only --pretty=format: <sha>`), filter to files under `tests/` (or files whose
  sibling production file the batch also touched, if the rule should also cover moving/renaming
  existing tests the batch happened to pass through), and if any qualify, spawn **one**
  `sdd:sdd-worker`-shaped boy-scout subagent (or a new small dedicated agent file, since it needs
  `Edit`/`Bash` to actually fix files and commit, closer in shape to `qa-bugfixer` than to
  `sdd-worker`) whose prompt bakes in: the exact file list (never "look at what changed" — that reopens
  scope), the two rules (from `ds:testing`), and an instruction to **fix only those files**, run
  `uv run pytest` on the affected apps, and make its own `[batch N boy-scout] <summary>` commit —
  mirroring the atomic-commit-inside-the-worker pattern `implement_plan.md:33-35` already uses, for the
  same crash-resume reason.
- **Never** scan the whole app/repo for hygiene debt in this step — that would violate the idea's
  explicit "no big-bang cleanup unless asked" (`idea.md:10`) and the batch subagent has no mandate
  beyond its own batch's files. The idea's own text already anticipates that a big-bang cleanup is a
  **separate, later, per-app spec** (`idea.md:12`) — the boy-scout step here is strictly "the files this
  batch already touched," never a superset.
- **Reporting/committing:** the boy-scout subagent's commit is a normal git commit on the current
  worktree's branch, exactly like every other batch commit — no new reporting channel needed. If a
  fix would be large enough to be its own review-worthy change (a judgement call), it should behave
  like `plan_structure_review`'s callout pattern instead of silently editing: leave a short note in the
  batch's own summary for the user to see in the final `implement_plan` report, rather than committing
  a sprawling refactor.

**Parallel-worktree considerations:** each SDD worktree is a separate working directory sharing one
bare repo (`claude_plugins/sdd/skills/git-worktree-setup/SKILL.md:9-13`) on its own branch, so the
boy-scout subagent's `git` operations (diff/show/commit) are inherently scoped to that worktree's own
branch and history — there is no risk of one worktree's boy-scout step reading or committing another
worktree's uncommitted files, since they are different working directories entirely. The one shared
state to be careful with is anything **not** gitignored that multiple worktrees' agents might write
concurrently and later merge — e.g. `.claude/agent-memory/ds-code-reviewer/` is explicitly "shared with
your team via version control" (`claude_plugins/sdd/resources/agent_memory_guidelines.md:34`), so if a
boy-scout agent is given persistent memory, expect ordinary git merge conflicts on that memory file
across parallel branches (resolved at PR-merge time like any other file) — nothing worse, but worth
choosing a memory *file per topic* (as the guideline already recommends) so merges are line-level, not
whole-file collisions. `.sdd-work/` scratch files are per-project-root (i.e., per-worktree, since each
worktree is its own checkout root) so they don't collide either.

## 5. Does `docs/app_structure.md` already expose app dependencies in a consumable form?

**Yes, directly, and this is the single best-leverage finding in this research.**
`docs/app_structure.md`'s **"Dependency table"** section (generated by
`claude_plugins/django-stack/scripts/generate_app_map.py`) already has exactly the two columns rule 2
needs, per app: **Runtime deps** and **Test-only deps** (`docs/app_structure.md:205-238`). The
generator already does AST-based import resolution and classifies every cross-app edge as runtime
(`A --> B`) or test-only (`A -.-> B`) based on path markers (`tests/`, `test_`, `conftest.py`,
`factories.py` — `generate_app_map.py:42,75-79`), and already **excludes an edge from "test" if it's
already "runtime"** (`generate_app_map.py:117`, `edges.test -= edges.runtime`) — i.e. it already
encodes "this is a test-only dependency the app doesn't have at runtime," which is precisely what rule
2 says should ideally not exist.

Two consumers already read this table programmatically-by-convention (regex-based, not full JSON, but
deterministic): `claude_plugins/fls-dev/commands/plan_structure_review.md` Step 2 parses the mermaid
block's `A --> B` / `A -.-> B` lines to build the approved-edge sets
(`plan_structure_review.md:50-53`), and `generate_app_map.py`'s own `parse_existing_edges` does the
same for its diff-on-regenerate feature (`generate_app_map.py:180-196`). **Any new review/boy-scout
step can reuse the identical parse** (either regex over the mermaid block, or read the "Dependency
table" markdown table directly) — no new data-extraction code is needed, only a new *consumer* of data
that already exists. The one gap: today nothing **flags an already-existing test-only edge as
undesirable** — `plan_structure_review` only flags *new* edges or *promotions* of test-only → runtime
(`plan_structure_review.md:65-70`); it treats a standing test-only edge as accepted, not as tech debt.
The boy-scout/review step this idea wants would be the first consumer to treat "this batch's tests use
a test-only edge already in the table" as a hygiene finding worth surfacing (not necessarily fixing
automatically, since removing a real cross-app test dependency may need real refactoring) rather than
silence.

No separate "`ds:app_map` skill" exists — `app_map` is a **command** only
(`claude_plugins/django-stack/commands/app_map.md`), not a skill, so it doesn't auto-trigger; a
reviewer/boy-scout subagent must be told explicitly to read `docs/app_structure.md` (as
`plan_structure_review.md` already does at Step 1, `plan_structure_review.md:38-42`) rather than
relying on skill auto-discovery.

## Concrete recommendations (summary)

1. **Add both rules to `claude_plugins/django-stack/skills/testing/SKILL.md`** (Key rules section,
   near the existing "Test files: `<app>/tests/test_<module>.py`" line) plus a worked example in
   `claude_plugins/django-stack/resources/testing.md`. One-line cross-reference from
   `claude_plugins/fls-dev/skills/testing/SKILL.md` if FLS's own layout needs a call-out (it currently
   has none beyond the path convention).
2. **Reference `docs/app_structure.md`'s existing dependency table** for rule 2 rather than inventing
   new dependency-tracking data — cite it exactly as `plan_structure_review.md` already does.
3. **Give `implement_plan`'s batch worker a real agent file** (new
   `claude_plugins/sdd/agents/sdd-implementer.md` or similar) with `skills: [ds:testing,
   fls-dev:testing]` frontmatter, replacing the bare `general-purpose` subagent_type at
   `implement_plan.md:28`, so the rules are preloaded rather than relying on auto-trigger.
4. **Add a review dimension to `implement_plan` Step 3** (or a new small Step 3.5) that fans out one
   `sdd:sdd-worker` to check the batch's/spec's diff against the two rules using
   `docs/app_structure.md`, following the exact fan-out shape `plan_from_spec.md` Step 6 already uses —
   no `setup_todo_list.md` edit needed since it lives inside `implement_plan`'s existing loop.
5. **Add a boy-scout step immediately after each batch commit**, scoped strictly to that commit's
   touched files (via `git show --name-only`), implemented as a dedicated small agent (shaped like
   `fls-dev:qa-bugfixer` — explicit file tracking, its own atomic commit, structured report) — never a
   repo-wide scan, per the idea's explicit no-big-bang constraint.
6. **No downstream plugin-sync file needs updating** for this idea — there is no skill-file copy
   mechanism between `ds`/`fls-dev`/`sdd` (each plugin is read live via `${CLAUDE_PLUGIN_ROOT}`), and
   `update_claude_plugin_fls_content.md`'s watched paths don't include testing conventions. The
   `concrete/update_fls.md` downstream-integration flow is spec/feature sync, not plugin-skill sync,
   and is unaffected.
7. **Flag, don't silently fix, the `sdd` ↔ `fls-dev` coupling** noted in `claude_plugins/sdd/README.md:12-14`
   if the eventual spec wants the new review/boy-scout step to be provider-agnostic — the recommended
   hook points above (3-5) deliberately avoid deepening that coupling by living inside `sdd`'s own
   `implement_plan` rather than adding another hard-coded `/fls-dev:*` line to `setup_todo_list.md`.

## Files read (citations)

- `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md`
- `claude_plugins/sdd/commands/README.md`, `implement_plan.md`, `plan_from_spec.md`, `next.md`,
  `spec_review.md`, `finish_worktree.md`, `address_pr_review.md`
- `claude_plugins/sdd/commands/protected/setup_todo_list.md`
- `claude_plugins/sdd/agents/sdd-worker.md`, `sdd-mechanic.md`
- `claude_plugins/sdd/resources/commit_and_push.md`, `agent_memory_guidelines.md`
- `claude_plugins/sdd/skills/git-worktree-setup/SKILL.md`
- `claude_plugins/sdd/README.md`
- `claude_plugins/django-stack/skills/testing/SKILL.md`, `resources/testing.md`
- `claude_plugins/django-stack/agents/code-reviewer.md`
- `claude_plugins/django-stack/commands/app_map.md`, `scripts/generate_app_map.py`
- `claude_plugins/django-stack/hooks/hooks.json`, `scripts/hooks/security-guard.sh`
- `claude_plugins/fls-dev/skills/testing/SKILL.md`, `resources/testing.md`
- `claude_plugins/fls-dev/commands/plan_structure_review.md`, `plan_security_review.md`, `init.md`
- `claude_plugins/fls-dev/commands/concrete/README.md`, `concrete/update_fls.md`
- `claude_plugins/fls-dev/agents/qa-bugfixer.md`, `agents/qa-data-helper.md`
- `claude_plugins/fls-dev/.claude-plugin/plugin.json`, `templates/config.md`
- `.claude/sdd/config.md`, `.claude/fls-dev/` (config listing)
- `docs/app_structure.md`
- `spec_dd/1. next/test-organisation-and-hygene/idea.md`

status: ok
