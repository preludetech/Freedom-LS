# Research: update_fls verification steps

## Summary

- The plan's ground-truth claims about `update_fls.md` all check out: it currently runs `migrate --check`
  and `makemigrations --check` but **never** `manage.py check` and **never** the conformance suite
  (`freedom_ls/contrib/conformance/`). Confirmed by exhaustive grep — see § 3.
- The "four call sites" claim is correct in both count and exact line numbers (`105, 122, 147, 168`),
  and the marker string is byte-identical across all four (one has a trailing `# test gate` comment; the
  rest are bare). No drift to report — see § 2.
- `update_fls.md` has **no YAML front matter** (no `description:`/`allowed-tools:` block) — unlike its
  siblings `update_upgrade_notes.md` and `update_template_repo.md`, which both open with one. Worth
  flagging to the author even though it's out of this slice's stated scope.
- `update_fls.md` has **no runserver step at all** today, so there's nothing hardcoding port 8000 in it.
  The "documented port pattern" lives in sibling commands `do_qa.md` and `update_product_docs.md`
  (both in the same `claude_plugins/fls-dev/commands/` directory): allocate a port via
  `.claude/ds/scripts/find_available_port.sh`, then `uv run python manage.py runserver $PORT`. This only
  matters **if** the new steps add a runserver step (e.g. to exercise the conformance suite's
  runtime-only checks) — plain `manage.py check` and pytest-driven conformance tests don't need a
  running server at all, so a runserver step may not be needed here.
- Recommended slot: insert both new steps in **Step 3h "Verify"** (and mirror in the "Per-spec loop
  (reference)" pseudocode, which is an explicit summary of 3h) — not necessarily into all four pytest
  call sites (Step 4's final sync and the rollback's green-check list are cheaper `--check`-only gates
  and shouldn't necessarily grow slower).
- Recommended order: `manage.py check` **before** the pytest test-gate, and the conformance suite
  **as part of / immediately alongside** the pytest test-gate (it's a pytest suite, so it can literally
  be a second `pytest` invocation targeting `freedom_ls/contrib/conformance/`, or folded into the same
  marker-selected run if it's already collected by the default `not playwright and not fls_internal and
  not ci_only` selection — needs a decision, see § 5). Both new checks should run **after** `migrate`
  (Step 3e's `requires_migrations` branch) so they see post-migration state, not before — the file's
  existing pre-flight (`migrate --check`, 3b) is a different, earlier gate for a different purpose
  (dirty DB state) and should stay put.
- Failure-handling convention already in the file: every verification step is treated as **blocking** —
  the two existing `--check` gates (`migrate --check` at 3b, `makemigrations --check` at 3g) both use
  "stop and resolve" / "resolve it before committing" language, and Step 3h's pytest run feeds directly
  into the Rollback section ("tests won't pass" is explicitly named as a rollback trigger). `manage.py
  check` and the conformance suite should follow the same blocking convention for consistency — no
  existing step in this file is advisory-only.
- House style for these command files: plain numbered/lettered `#`/`##` step headings, imperative prose
  addressed to the Claude Code agent (not a human running a shell script), fenced code blocks for the
  actual commands to run, and explicit "if this fails, do X" prose immediately following the command
  rather than a separate error-handling section. `update_fls.md` itself lacks the front-matter block that
  its siblings have — the SDD `claude-code-authoring` skill referenced by the plan should be consulted
  for whether adding one is appropriate while touching this file (though it's out of this slice's
  explicit scope to fix that gap).

## 1. Full anatomy of `update_fls.md`

Path: `claude_plugins/fls-dev/commands/concrete/update_fls.md` (172 lines).

**Front matter:** none. The file opens directly with prose at line 1 (`claude_plugins/fls-dev/commands/concrete/update_fls.md:1`) — no `---`-delimited `description:`/`allowed-tools:` block. Compare
`claude_plugins/fls-dev/commands/update_upgrade_notes.md:1-4` and
`claude_plugins/fls-dev/commands/update_template_repo.md:1-4`, both of which have one.

**Intro (lines 1-3):** one-paragraph summary of the whole command's purpose (spec-by-spec submodule
advance, per-spec upgrade-notes-driven integration, migration guards, rollback docs).

**Structure, in order:**

- `# Step 1: Identify new completed specs` (`:5-10`) — fetch, diff commit log, list completed specs
  chronologically. No verification here.
- `# Step 2: Dry-run preview (no changes yet)` (`:12-33`) — read each spec's `upgrade_notes.md`
  frontmatter, print a preview table, get operator confirmation before touching anything. No
  verification here; explicitly "Do not modify... during this step" (`:33`).
- `# Step 3: Integrate each spec sequentially` (`:35-114`) — per-spec subagent loop, lettered sub-steps:
  - `## 3a. Read the upgrade notes` (`:39-43`)
  - `## 3b. Pre-flight migration check` (`:45-53`) — **verification step**: `migrate --check`
  - `## 3c. Move the submodule pointer` (`:55-61`)
  - `## 3d. Sync dependencies` (`:63-71`) — `uv sync`
  - `## 3e. Apply the flagged integration steps` (`:73-82`) — conditional on upgrade-notes flags
    (migrations, settings, packages, npm, tailwind, template review)
  - `## 3f. Template-drift detection` (`:84-88`)
  - `## 3g. Post-flight conflict check` (`:90-98`) — **verification step**: `makemigrations --check`
  - `## 3h. Verify` (`:100-108`) — **verification step**: the pytest marker-selected run, plus a
    Playwright-MCP note for front-end changes
  - `## 3i. Commit` (`:110-114`)
- `# Step 4: Final sync` (`:116-122`) — after all specs, sync to `origin/main`, `uv sync` if pointer
  moved, then **verification step**: pytest run "one last time"
- `# Rollback: recovering from a spec that fails mid-integration` (`:124-150`) — numbered recovery
  procedure ending in a **verification step**: `git status`, `migrate --check`, then the pytest run
  (`:143-148`)
- `# Per-spec loop (reference)` (`:152-171`) — a pseudocode summary of the whole Step 3 loop, restating
  every verification gate as a comment (`:158`, `:161`, `:167`, `:168`)

**Verification sections quoted in full:**

`## 3b. Pre-flight migration check` (`claude_plugins/fls-dev/commands/concrete/update_fls.md:45-53`):

```
Before moving the pointer, confirm the concrete project's migration state is clean:

```
uv run python manage.py migrate --check
```

If this fails, stop and resolve the dirty migration state before integrating further — do not move the pointer on top of an inconsistent database state.
```

`## 3g. Post-flight conflict check` (`:90-98`):

```
After applying the integration, confirm no migrations are missing or in conflict:

```
uv run python manage.py makemigrations --check
```

A non-zero result here means the integration left the migration state inconsistent (e.g. a model change with no migration). Resolve it before committing.
```

`## 3h. Verify` (`:100-108`):

```
Run the portable contract test set and confirm everything passes — this is the concrete project's own suite, so it deselects FLS's browser tests, brand/demo-coupled tests, and slow-only tests (the downstream is verifying its own wiring, not re-running FLS's regression suite):

```
uv run pytest -m "not playwright and not fls_internal and not ci_only"
```

If there are front-end changes, use the Playwright MCP to verify things work visually.
```

`# Step 4: Final sync`, item 3 (`:122`):

```
3. Run the portable contract test set one last time: `uv run pytest -m "not playwright and not fls_internal and not ci_only"`
```

Rollback procedure's final check (`:143-148`):

```
4. Confirm you are clean and green:
   ```
   git status
   uv run python manage.py migrate --check
   uv run pytest -m "not playwright and not fls_internal and not ci_only"
   ```
```

There is **no runserver step anywhere** in this file (confirmed by grep — see § 4).

## 2. The pytest call sites — verified

The plan (`2. plan.md:13-16`) claims **four** call sites of
`-m "not playwright and not fls_internal and not ci_only"` at lines "~105, ~122, ~147, ~168". Grepping
the file confirms exactly four matches, at exactly those lines:

- `claude_plugins/fls-dev/commands/concrete/update_fls.md:105` — `uv run pytest -m "not playwright and not fls_internal and not ci_only"` (Step 3h, in its own fenced code block)
- `claude_plugins/fls-dev/commands/concrete/update_fls.md:122` — inline in prose: `Run the portable contract test set one last time: \`uv run pytest -m "not playwright and not fls_internal and not ci_only"\`` (Step 4, not its own code block)
- `claude_plugins/fls-dev/commands/concrete/update_fls.md:147` — `uv run pytest -m "not playwright and not fls_internal and not ci_only"` (Rollback step 4, inside a fenced block alongside `git status` and `migrate --check`)
- `claude_plugins/fls-dev/commands/concrete/update_fls.md:168` — `uv run pytest -m "not playwright and not fls_internal and not ci_only"  # test gate` (per-spec-loop pseudocode, with a trailing `# test gate` comment)

**Verdict: the plan's claim is accurate**, both in count (4) and in line numbers (exact, not just
"roughly" — the plan hedges with `~` but they're exact). The marker string itself is byte-identical
across all four; the only textual difference is line 168's trailing `# test gate` comment and line 122
being inline prose rather than its own fenced block. No drift to report.

Each of the four sites will need the same new steps threaded alongside it if the new checks are meant to
run everywhere the pytest gate runs today (Step 3h, Step 4, the rollback verification, and the
pseudocode summary) — see § 5 for which of these actually need it.

## 3. Does it already run `manage.py check` or a conformance suite?

**No — the plan's claim is correct.** Grepped `update_fls.md` for `check|conformance|collectstatic|
runserver|migrate` (case-sensitive) across the whole file; the only `check` occurrences are the two
migration-state gates already quoted in § 1:

- `claude_plugins/fls-dev/commands/concrete/update_fls.md:50` — `uv run python manage.py migrate --check`
- `claude_plugins/fls-dev/commands/concrete/update_fls.md:95` — `uv run python manage.py makemigrations --check`
- `claude_plugins/fls-dev/commands/concrete/update_fls.md:146` — `uv run python manage.py migrate --check` (rollback copy)
- `claude_plugins/fls-dev/commands/concrete/update_fls.md:158`, `:161`, `:167` — pseudocode comments for the same two gates

No bare `manage.py check` invocation exists anywhere in the file. No mention of `conformance` or
`collectstatic` exists anywhere in the file. `freedom_ls/contrib/conformance/` itself exists in the repo
(confirmed present, per the plan's ground-truth note at `2. plan.md:21-22` and the idea's dependency note
at `idea.md:55-57` — this slice does not need to re-verify the suite's shipped status, only that
`update_fls.md` doesn't yet reference it, which it doesn't).

## 4. The "documented port pattern"

`update_fls.md` has **no runserver step today** — confirmed by grep across the file for
`runserver|8000|port` (case-insensitive): zero matches. So there is nothing in the file currently
hardcoding port 8000, and the instruction "use the documented port pattern... do not hardcode 8000" is
a **forward-looking constraint** that only bites if the new verification steps end up needing a live dev
server (e.g. to exercise runtime-only conformance checks such as sitemap/robots reachability). Plain
`manage.py check` (a static/boot-time check, no server needed) and pytest-driven conformance tests
(pytest starts its own test client/server as needed) do **not** require a `runserver` step at all, so
this constraint may simply not be triggered by the two additions as scoped — worth flagging as an open
question (see below).

The documented pattern itself is established in two sibling command files, both in the same
`claude_plugins/fls-dev/commands/` directory as `update_fls.md`'s parent:

- `claude_plugins/fls-dev/commands/do_qa.md:151-168` (`## Step 3: Find an unused PORT and start the dev
  server`):
  > `.claude/ds/scripts/find_available_port.sh` ... Then start the dev server as its **own solo,
  backgrounded** Bash call ... `uv run python manage.py runserver <PORT>`
  Base URL is then `http://127.0.0.1:<PORT>/` (`do_qa.md:24`, `:174`, `:200`).
- `claude_plugins/fls-dev/commands/update_product_docs.md:144-158`:
  ```
  PORT=$(.claude/ds/scripts/find_available_port.sh)
  uv run python manage.py runserver $PORT
  ```
  followed by `Base URL: http://127.0.0.1:$PORT/` (`:149`) and a teardown call to
  `.claude/ds/scripts/kill_runserver.sh $PORT` (`:158`).
- The underlying script is `claude_plugins/django-stack/scripts/find_available_port.sh:2-9`, which starts
  at 8000 and probes upward (`START_PORT=8000` / `PORT=$((START_PORT + RANDOM % 1000))`, then loops past
  in-use ports via `ss -tlnp`) — so "documented pattern" ultimately bottoms out at this script, vendored
  into concrete projects at `.claude/ds/scripts/find_available_port.sh` (per the wrapper-script mechanism
  described in `claude_plugins/django-stack/README.md:59-60,84-85`).
- The SDD plan-authoring command also documents the same convention prescriptively, for anyone writing a
  frontend_qa/plan file: `claude_plugins/sdd/commands/plan_from_spec.md:59-62` — *"we won't be using port
  8000 (the default django runserver port). Don't talk about port 8000... `PORT=$(.claude/ds/scripts/
  find_available_port.sh)` ... `uv run python manage.py runserver $PORT` ... Base url is
  `http://127.0.0.1:$PORT`"*.
- `.claude/fls-dev/config.md:8` and `.claude/ds/config.md:5` both list a **static** `http://127.0.0.1:8000`
  as the plain dev base URL for manual/local use — that's a different, non-randomized convention for
  ordinary `runserver` use outside of QA/automation contexts. It should not be confused with the
  randomized-port pattern above, which exists specifically so automated/backgrounded runserver instances
  (QA agents, doc-verification agents) don't collide on 8000.

**If** the new verification steps add a runserver step, it must follow the `find_available_port.sh` +
`$PORT` pattern from `do_qa.md`/`update_product_docs.md`, not a bare `runserver` (implicit 8000) or an
explicit `runserver 8000`.

## 5. Where the two new steps should slot in

**Recommended anchor:** `## 3h. Verify` (`update_fls.md:100-108`) is the single existing "verification"
step in the per-spec loop, and it already bundles "run tests" + "if front-end changed, use Playwright" in
one place. Both new checks belong here, as two more items in the same step, run in this order:

1. **`uv run python manage.py check`** — run **first**, immediately after 3h begins (or even as a
   separate `## 3h-i` between `3g` and the existing `3h`, since it's a check on Django's app/model/
   settings graph, not a test run). Ordering rationale:
   - It must run **after** Step 3e's `requires_migrations` branch (migrations applied) and 3g's
     `makemigrations --check` (schema conflicts resolved), because `manage.py check` inspects installed
     apps/models/settings, and a broken migration state can itself surface as check noise unrelated to
     the actual settings problem being tested for. Running it after the migration gates keeps its
     failures attributable to genuine settings/config drift (the scenario D6/Layer 4 exist for), not to
     migration hygiene already caught upstream.
   - It should run **before** the pytest test-gate, so a fast, cheap, boot-time failure (a missing
     required setting, e.g. the `COURSE_ACCESS_BACKEND` example in `1. spec.md:26-30`) is reported before
     spending time on the slower pytest suite. This also matches Django's own convention that `check` is
     the fast pre-flight signal `runserver`/`migrate`/`test` already run implicitly (see
     `claude_plugins/django-stack/skills/app-settings/SKILL.md:103` — *"manage.py check` non-zero; blocks
     `runserver`/`migrate`/`test`"*).
2. **Conformance suite invocation** — run as part of / directly alongside the existing pytest test-gate
   line. Since `freedom_ls/contrib/conformance/` is itself a pytest-collected suite, the simplest,
   least-invasive integration is either (a) confirm it's already swept up by the existing
   `-m "not playwright and not fls_internal and not ci_only"` selection (likely, since conformance tests
   are explicitly the "positive signal" and shouldn't be marked `ci_only`/`fls_internal`/`playwright`),
   in which case the only change needed is a sentence pointing this out and no new command; or (b) if it
   needs to be isolated/pointed at explicitly (e.g. to guarantee it ran and wasn't silently deselected,
   or to give a distinct pass/fail signal from the rest of the downstream's own tests), add a second,
   explicit invocation such as `uv run pytest freedom_ls/contrib/conformance/` immediately after the
   existing marker-selected line. **This research did not read the conformance suite's own pytest
   markers/config**, so this is a decision point for the plan/spec author, not settled here — see Open
   Questions.
   - It must run **after** migrations (same reasoning as `manage.py check`) since conformance tests very
     plausibly exercise the DB/app surface (e.g. sitemap/robots existence per D1, referenced in
     `idea.md:47-51`).

**Propagate to all four sites, or just the main one?** The plan (`2. plan.md:49-54`) only says "add to the
verification steps" without specifying whether that means every one of the four call sites (§ 2) or just
the canonical Step 3h. Recommendation: add both new commands **only in 3h** (the per-spec gate — this is
where a regression would actually be caught spec-by-spec) and in the **Per-spec loop pseudocode**
(`:152-171`) since that block is an explicit summary/mirror of 3h and would otherwise drift out of sync.
Do **not** duplicate into Step 4's "final sync" one-liner (`:122`) or the rollback procedure's
green-check list (`:143-148`) unless the author wants belt-and-braces — those are cheaper, `--check`-only
recovery gates, and piling `manage.py check` + a full conformance suite onto the rollback path risks
turning a quick "are we back to a good state" check into a slow one. This is a judgement call for the
plan/spec author; flagged as an open question below since the idea/spec/plan don't say explicitly.

**Blocking or advisory?** The file's existing convention is **uniformly blocking** — see § 1's quoted
sections: `migrate --check` says "stop and resolve... before integrating further" (`:53`);
`makemigrations --check` says "Resolve it before committing" (`:98`); the pytest run has no advisory
language at all and its failure is explicitly one of the three named Rollback triggers ("tests won't
pass, a migration conflicts, an override can't be reconciled", `:126`). There is **no precedent anywhere
in this file for an advisory/non-blocking step** — every check that can fail is treated as a hard stop
before commit. `manage.py check` and the conformance suite should follow the same convention: both
blocking, both feeding into the Rollback section as additional named triggers (the Rollback intro at
`:126` should probably gain "a system check fails" / "the conformance suite fails" to its list of named
triggers for consistency, though the recovery mechanics don't change).

## 6. Sibling commands for style

`claude_plugins/fls-dev/commands/` contains: `plan_security_review.md`, `do_qa.md`,
`update_claude_plugin_fls_content.md`, `update_template_repo.md`, `update_product_docs.md`, `init.md`,
`plan_structure_review.md`, `update_upgrade_notes.md`, plus `concrete/update_fls.md` and
`concrete/README.md` (the only two files under `concrete/`).

`concrete/README.md` (`claude_plugins/fls-dev/commands/concrete/README.md:1`) is a one-line scope note:
*"These commands are specifically for concrete implementations of FLS. They typically include FLS as a
submodule."* No style guidance there.

**House style, from `update_upgrade_notes.md` and `update_template_repo.md` (both quoted in full above)
plus spot-checks of `do_qa.md`:**

- **Front matter is the norm, but `update_fls.md` lacks it.** Both `update_upgrade_notes.md:1-4` and
  `update_template_repo.md:1-4` open with a `---`-delimited block: `description: ...` and
  `allowed-tools: Read, Write, Glob, Edit, Bash, Agent`. `update_fls.md` has none (§ 1). This is a
  pre-existing gap, not something this slice is asked to fix, but worth a one-line callout since the
  editor may want to add one while touching the file (out of explicit scope per `1. spec.md:73-77`,
  which restricts this slice to the two named edits — flag only, don't act).
- **Numbered/lettered step headings** (`# Step N: ...`, `## Na. ...`) with short imperative prose under
  each, addressed to the Claude Code agent executing the command, not to a human reading a runbook.
  E.g. `update_template_repo.md:12` `## Step 1: Locate the spec directory`, followed by a 3-item ordered
  list of concrete lookup rules including an escape hatch (`update_template_repo.md:16-18`: *"If
  ambiguous, use `AskUserQuestion` to confirm before proceeding"*).
- **Shell/command blocks are fenced and minimal**, immediately followed by prose interpreting the result
  — never a separate "troubleshooting" section. E.g. `update_upgrade_notes.md:65-73` fences two `git`
  commands under a `# comment` explaining each, then "Read the output. Focus on: ..." as a bullet list
  mapping diff signals to upgrade-notes flags.
  `update_fls.md` follows the identical pattern throughout (e.g. `:49-53`, `:94-98`, `:104-108` — command
  block immediately followed by one or two sentences of "if this fails, do X" or "if true, do Y").
- **"If this fails, do X" is inline, right after the command**, not deferred to a dedicated error-handling
  section — e.g. `update_fls.md:53` ("If this fails, stop and resolve...") and `update_fls.md:98`
  ("...Resolve it before committing."). `update_template_repo.md:28-34` shows the richer version of this
  pattern: a **stop condition** with a full templated message to relay to the user, plus an explicit
  escape hatch ("If you don't maintain the template repo locally, tick this step by hand and skip it").
- **Tables for signal→action mappings** where there's a many-to-many correspondence — see
  `update_template_repo.md:48-55` (`| Signal | Template repo file(s) to update |`). `update_fls.md` uses
  a flat bullet list instead for its flag→action mapping (`:77-82`), which is arguably the same pattern
  in a lighter-weight form (single-column consequences, not a genuine table). This suggests the new
  "conformance suite" / "manage.py check" verification bullets can stay in `update_fls.md`'s existing
  flat-bullet style rather than needing a table.
- **Escape hatches and "an honest 'no action' is fine" language recur** — e.g.
  `update_template_repo.md:64` ("An honest 'no template repo update needed' is the correct output for
  most features") and `update_upgrade_notes.md:95` ("an honest 'no action needed' is more useful than
  padding"). Not directly relevant to blocking-vs-advisory design for the new checks (§ 5), but shows the
  house voice tolerates saying "nothing to do here" plainly rather than forcing busywork.
- `do_qa.md` (much longer, QA-specific) confirms the same style at scale: explicit numbered "Step N"
  sections, a documented port-allocation subroutine (§ 4 above), and inline recovery guidance (e.g.
  `do_qa.md:180`: "If this happens, return to Step 3.").

## Open questions for the user

- Should the two new checks be added to **all four** pytest call sites (§ 2), or only to the per-spec
  `3h`/pseudocode pair as recommended in § 5? The idea/spec/plan text ("add to the verification steps")
  doesn't disambiguate.
- Does `freedom_ls/contrib/conformance/`'s own pytest configuration already fall inside the existing
  `-m "not playwright and not fls_internal and not ci_only"` marker selection (making the "invoke it"
  instruction a documentation-only sentence, no new command), or does it need an explicit separate
  `pytest` invocation to guarantee it isn't silently deselected? This slice's research scope didn't cover
  reading the conformance suite's own markers/pytest config — that's the `test_portability_2_conformance_suite`
  slice's territory, but the answer directly determines whether `update_fls.md`'s edit is a new command
  line or just prose.
- Confirmed the "documented port pattern" instruction is currently a no-op for `update_fls.md` (it has no
  runserver step and the two new checks as scoped don't need one) — should the plan/spec instead be read
  as "if you *do* add anything runserver-shaped while making these edits, follow the pattern," rather than
  implying a runserver step must be added? Worth confirming before the implementer goes looking for a
  runserver step to add where none may be needed.

status: ok
