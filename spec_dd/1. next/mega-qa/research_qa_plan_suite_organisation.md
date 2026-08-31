# Research: naming, structure, traceability and report format for a durable whole-system QA suite

Scope: this file covers only the conventions that make `qa_whole_system/` survivable as a permanent,
repeatedly-run artifact — not the carve-up (decided) and not an implementation plan.

---

## 1. What FLS's existing QA plans actually look like

**Conclusion first.** FLS already has a plan convention worth keeping almost intact: a `§0`
setup/seed section, letter-or-number test IDs with inline `Expect:` lines, a pass/fail/partial
vocabulary applied per step, and a closing cross-cutting summary. What does **not** transfer is
everything that assumes a single throwaway feature branch: the "no `todo.md`, tick the parent's"
note, viewport-sharing between sibling plans that exist only because one feature got QA'd in pieces,
and "plan drift corrected against this diff" framing. The split-signpost file itself is the strongest
evidence for the directory-per-plan structure recommended in §3 below.

### The recurring structure, with evidence

- **A `§0` setup/seed section, not optional.** `3a. seam_qa/frontend_qa_seam.md` §0.0–0.5 covers, in
  order: a required database-rebuild check with the exact `showmigrations` command and its expected
  output, a numbered list of copy-pasteable seed commands with notes on which flags are positional vs.
  optional, a "former blocker, now fixed" subsection kept only so a regression is recognised rather
  than re-diagnosed, credentials, a persona/fixture table, an explicit "log out between personas"
  reminder, and a table of admin changelist URLs the tester will live in
  (`spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/3a. seam_qa/frontend_qa_seam.md:40-183`).
  The much older `deadlines` plan has no `§0` at all — just a "Prerequisites" bullet list assuming
  fixtures already exist (`spec_dd/3. done/2026-02-19_19:25_deadlines/3. frontend_qa.md:1-13`). The rich
  `§0` is the newer, hard-won convention; a durable plan needs it even more than a one-shot plan does,
  because it will be run by an agent with zero memory of the last run.
- **A "run with" header line and a viewport-ownership line.** Every current-generation plan states its
  own invocation and viewport scope at the very top: `**Run with:** /fls-dev:do_qa "…/frontend_qa_seam.md"`
  and `**Viewports: desktop only.**` with a cross-reference to whichever sibling plan owns mobile/tablet
  (`…/3a. seam_qa/frontend_qa_seam.md:1-9`). This transfers directly — a durable plan run against dev or
  staging still needs an explicit invocation line and an explicit viewport scope, since "owns the mobile
  pass" between nine permanent siblings needs to be as legible as it is between four temporary ones.
- **Test IDs vary by era, and none of the schemes are wrong.** The old `deadlines` plan uses
  `Test 1`/`1a`/`1b` (`spec_dd/3. done/2026-02-19_19:25_deadlines/3. frontend_qa.md`). The
  `better_course_progress_tracking` split uses a letter-per-plan-plus-number scheme: `S1`–`S10` (seam),
  `G1`–`G11` (progress gaps), `R1`–`R9` (form_engine regression), `RS1`–`RS7` (report smoke) — one letter
  per sibling plan so an ID is globally unambiguous even outside its own file
  (`spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/3. frontend_qa.md:28-33`). This
  letter-per-plan habit transfers directly to a whole-system suite with nine permanent siblings: a
  durable equivalent would use one stable prefix per area (e.g. `AUTH1`, `LX7`, `REP3`) so a bug report,
  a manifest row, or a human conversation can name a test unambiguously without saying which file it
  lives in.
- **Pass/fail/partial vocabulary, applied per step, not just per section.** `qa_report.md` for `3a`
  annotates almost every line: `(pass)`, `(**FAIL**)`, `(pass, plan drift corrected)`, `(pass, wording
  deviation, essence held)`, `(pass, documented design)`, `(pass, behaves per design, flagged for
  judgment)` (`spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/3a. seam_qa/qa_report.md:52-329`).
  This finer vocabulary than a bare pass/fail is worth keeping for a durable suite precisely because a
  durable suite will rediscover the same "documented design, not a bug" judgment call on every re-run —
  losing the annotation would mean re-litigating it each time.
  Rule 2 in `do_qa.md` separately defines **`PARTIAL`** for a test that could not be set up at all
  (`claude_plugins/fls-dev/commands/do_qa.md:47-79`), a fourth state distinct from fail.
- **A closing cross-cutting summary, not just per-section pass/fail.** `frontend_qa_seam.md` ends with
  "What 'pass' means" — a short list of the invariants that matter across every section, restated once
  so a reader does not have to reconstruct them from ten separate `Expect:` lines
  (`spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/3a. seam_qa/frontend_qa_seam.md:479-495`).
  This is exactly the shape a durable plan's own "what does this area's smoke coverage actually
  guarantee" section should take, and it is cheap to keep updated because it changes far less often
  than the step-by-step detail above it.
- **The todo-tick convention does *not* transfer.** Every plan in the split states plainly: "This
  directory has no `todo.md`. Tick and append against the parent one … section `## 9. QA`"
  (`…/3a. seam_qa/frontend_qa_seam.md:5-6`, repeated in the signpost at
  `…/3. frontend_qa.md:45-47`). That convention exists because a spec-run QA plan is one step of a
  single feature's todo. A durable suite has no owning feature and no parent `todo.md` to tick — its
  bookkeeping belongs in whatever manifest tracks plan status (§3), not in a todo item that gets
  archived into `spec_dd/3. done/` when the feature ships.
- **"Plan corrections applied" is a spec-run habit worth generalising, not dropping.** `3a`'s report
  documents two in-run rewrites to the plan file itself — one because the plan named a
  `submit_on_exit` form for a resume test that structurally cannot resume, one because it told the
  tester to edit a field the admin makes read-only for signal-integrity reasons
  (`…/3a. seam_qa/qa_report.md:384-401`). For a one-shot plan this is a courtesy to the next reader. For
  a durable plan, this *is* the maintenance mechanism — see §4's discussion of prose-ambiguity rot.

---

## 2. What `/fls-dev:do_qa` requires of a plan, and what breaks for a whole-system run

**Conclusion first.** `do_qa.md` is written entirely around one assumption: an in-progress feature
branch, diffed against `main`, tested on a disposable local database the agent can drop and recreate,
served by a `runserver` the agent itself started. A whole-system run — especially against a remote
staging URL — invalidates that assumption at nearly every step. Below is every contract the plan file
and the surrounding project must satisfy, then the exhaustive list of what breaks.

### Contracts a plan (and its spec dir) must satisfy today

1. **Discovery.** The plan is either named explicitly in `$ARGUMENTS`, or found under
   `spec_dd/2. in progress/` if ambiguous, ask (`claude_plugins/fls-dev/commands/do_qa.md:16-18`).
2. **`<spec-dir>` is the plan's parent directory**, and `qa_report.md` / `screenshots/` are written
   *beside the plan* inside it (`do_qa.md:20-22`), quoted everywhere because spec directory names
   contain spaces.
3. **A `§0` seed the ladder can restart from.** Rule 2 rungs 2 and 3 explicitly re-run "the test
   plan's seed list" after a content reset or a full DB drop/create/migrate (`do_qa.md:65-67`) — the
   plan file is the sole source of how to rebuild fixtures, there is no other seed registry.
4. **A local, disposable, per-branch database** the agent can wipe: rung 3 runs `DB drop`, `DB create`,
   `Migrate` from `.claude/fls-dev/config.md`'s `## QA Dev Data` section, whose configured scripts derive
   the database name from the current git branch (`do_qa.md:47-79`; confirmed in
   `.claude/fls-dev/config.md:19-22` and the seam plan's own `dev_db_delete.sh` note that it "derives
   the name from the current branch, so no other worktree is touched",
   `…/3a. seam_qa/frontend_qa_seam.md:76-78`).
5. **A `qa-data-helper` `Agent` that owns factory conventions** for missing/blocking data, addressed by
   primary key, with no hand-rolled ORM scripts (`do_qa.md:54-64`).
6. **A `git diff main...HEAD --name-only`-scopeable branch** (Step 2) that classifies the run as
   `FULL`/`ADMIN_ONLY`/`BACKEND_ONLY` and is reported as a `scoping` record
   (`do_qa.md:139-166`).
7. **One derivable "primary changed page"** for the smoke gate (Step 6), "derive it from the test plan
   or from the changed file paths from Step 2" (`do_qa.md:219-231`) — i.e. it needs the diff from
   contract 6 to exist.
8. **A locally startable dev server** on a freshly chosen port, confirmed via a `debug-branch-badge`
   element that must name *the branch currently checked out* (`do_qa.md:175-206`), and killed again at
   the end (`do_qa.md:541-547`).
9. **Credentials from `.claude/fls-dev/config.md`**, a dev-only, git-local file (`do_qa.md:208-216`,
   `.claude/fls-dev/config.md:3-5`).
10. **A `todo.md` in `<spec-dir>` (or its parent) naming this exact plan** with a matchable
    `/fls-dev:do_qa` line, and a closed list of four categories the mechanic may append
    (`do_qa.md:551-598`).
11. **A git checkout the auto-fix loop can commit to and revert.** Step 13's green lane runs
    `fls-dev:qa-bugfixer`, which commits, and re-verifies against the *same still-running* dev server
    because "Django auto-reloads after the fixer's commit" (`do_qa.md:436-537`).
12. **Scratch files scoped to one run**, deleted by explicit path at the end (`do_qa.md:601-616`) —
    the whole scratch/report/todo pipeline assumes a single, one-shot execution with a clean start and
    a clean end.

### What breaks for a whole-system run — exhaustively

- **No `todo.md` (contract 10 fails outright).** Step 15 has nothing to tick, and its "closed list of
  four categories" (`add:` an UNRESOLVED bug fix item, an impossible-to-seed scenario, a smoke-gate
  failure, a product/UX decision) is phrased entirely in terms of *this feature's* todo. A whole-system
  run needs a different sink for the same four kinds of finding — most plausibly the manifest (§3) or a
  standing backlog, not a per-run `add:`/`tick:` pair against a file that does not exist.
- **No `git diff main...HEAD` to scope against (contract 6 fails).** There is no "this branch's diff"
  for a permanent suite being run against dev or a deployed staging build — the whole point is to test
  *everything currently live*, not what one branch changed. `CLASS = FULL/ADMIN_ONLY/BACKEND_ONLY`
  has no input to compute from, so Step 2 cannot run as written, and neither can the smoke gate's
  "primary changed page" (contract 7), which is defined only in terms of that diff. A whole-system run
  needs its own, diff-free notion of "what always gets tested" (arguably: always full breadth, since
  there is no diff to say otherwise) and, separately, a *staleness* signal (§4) that is not the same
  thing as a diff-scoping gate.
- **No dev server to start when the target is a remote staging URL (contracts 8 fails).** Steps 3
  (`find_available_port.sh` + `runserver <PORT>`), 4 (branch-badge check) and 14 (kill the server) are
  all meaningless against a URL the agent does not control the lifecycle of. The base URL must instead
  be an input to the run, not a derived `http://127.0.0.1:<PORT>/`. The branch-badge check (Step 4)
  has no staging equivalent at all unless staging exposes some other "what build is this" signal — and
  even if it did, "is this the branch we are on" is the wrong question for staging; the right question
  is closer to "is this the build we expect."
- **Rule 2's whole ladder is local-only (contracts 3, 4, 5 fail against staging).** Rung 1 delegates to
  `fls-dev:qa-data-helper`, a subagent that fixes data "by pk" using project factory conventions — this
  presumes ORM/Bash access to the target database, which a remote staging deployment does not grant an
  agent. Rungs 2 and 3 run `.claude/fls-dev/scripts/dev_db_delete.sh` / `dev_db_init.sh` / `migrate`,
  which are literally `dropdb`/`createdb` wrappers scoped to *this worktree's* locally-named database
  (`…/3a. seam_qa/frontend_qa_seam.md:70-78`) — there is no path by which these reach a remote Postgres
  instance, and there should not be: an agent should never hold drop/create credentials for a shared
  staging database. This is precisely the gap the idea's own item 2 (a single `setup_qa_data`,
  reachable only as an environment-gated staging *view* rather than a Bash script) is designed to close
  — noted here because it is the direct answer to this specific contract failure, not because this
  research proposes the mechanism.
- **The auto-fix loop assumes the run and the fix live in the same checkout (contract 11 fails,
  partially, for staging).** Step 13 commits a fix and re-verifies against "the dev server, which
  Django auto-reloads" — there is no equivalent for a staging target: staging serves an already-built,
  already-deployed artifact, so a bug found there cannot be fixed and re-verified inside the same QA
  run. A whole-system run against staging can only ever produce **UNRESOLVED** findings (or nothing new
  at all — see below); the green lane does not exist for it.
- **Credentials (contract 9) need to vary by environment**, not just by project — `.claude/fls-dev/config.md`
  is explicitly dev-only ("Dev Credentials"); a staging run needs its own, presumably
  environment-variable-sourced, credential source, per `CLAUDE.md`'s "never hardcode credentials" rule.
- **Scratch-file lifecycle (contract 12) is fine as-is, but its assumption of a single run needs
  revisiting for scheduling.** `.sdd-work/qa_scratch.jsonl` being deleted at the end of every run is
  correct behaviour to keep — but if a whole-system run is meant to produce a diffable history (§5), the
  *rendered* report and/or a small sidecar must be the durable artifact, not the scratch file, exactly
  as today.
- **What still holds unchanged:** the `<spec-dir>`-relative `qa_report.md`/`screenshots/` placement
  (contract 2), the `qa-data-helper` delegation model for *local* dev/CI runs (contract 5, when the
  target is dev), the bug-grouping-before-report-generation step (Step 12), and the Playwright-MCP
  screenshot-capture mechanics (Step 7's no-filename convention) — none of these are diff-shaped or
  branch-shaped, so none of them need to change for a whole-system dev run. Only the staging case and
  the diff/todo/branch assumptions above need a different contract.

---

## 3. Naming and directory conventions

**Recommendation, stated first:** one directory per plan, named after the exact `docs/product/`
filename stem it covers, with no ordinal prefix, plus a single manifest file at the top of
`qa_whole_system/`. Reports and screenshots are generated artifacts and should not be committed.

### Directory-per-plan is not a style choice here — it is forced by an already-observed failure mode

`do_qa.md` writes `qa_report.md` and `screenshots/` **beside the plan file**, inside `<spec-dir>`
(`do_qa.md:20-22`, Step 1's `qa_cleanup.sh "<spec-dir>"`, Step 10's `qa_collect_screenshots.sh
"<spec-dir>"`). FLS has already hit the consequence of ignoring this once: the original
`better_course_progress_tracking` QA was a single flat `3. frontend_qa.md`, and it had to be split into
`3a.`–`3d.` subdirectories specifically because — as the signpost states outright — "each writes its
own `qa_report.md` and `screenshots/` and **no run can delete another's artifacts**"
(`spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/3. frontend_qa.md:24-26`). That
split was for four *temporary* siblings inside one branch's lifetime. A whole-system suite has **nine
permanent siblings**, re-run indefinitely, plausibly overlapping (a dev run and a staging run happening
in the same window, or two people re-running different areas at once) — the exact condition that made
the flat layout unsafe, sustained forever rather than for one branch's duration. Flat files
(`qa_whole_system/authentication.md`) sharing one `qa_whole_system/screenshots/` would reproduce that
failure on the very first concurrent run, so:

- `qa_whole_system/<area>/plan.md`
- `qa_whole_system/<area>/report.md` (generated; see below on committing it)
- `qa_whole_system/<area>/screenshots/` (generated)

### Naming per area: use the `docs/product/` filename, not a paraphrase

The user has fixed the carve-up to one plan per `docs/product/` document. `docs/product/` uses these
nine stems for the nine areas named in the idea: `authentication`, `learner-experience`,
`learner-tracking`, `educator-interface`, `reports` (the doc titled "Cohort Reports" in
`docs/product/README.md`'s display table is the file `docs/product/reports.md` — the display label and
the filename differ; the *filename* is the stable identifier), `admin-interface`, `webhooks`,
`multi-tenancy-and-isolation`, `content-editing-workflow` (`docs/product/*.md`, thirteen files present in
total; five — `deployment.md`, `security-and-data-handling.md`, `configuration-and-extension.md`,
`roadmap.md`, `README.md` — are not in the user's nine-area list and are out of scope here). Naming each
`qa_whole_system/<area>/` directory after the doc's own filename stem, not after the README's
prose label, means a plan and its source document form a lookup-free pair — this follows
`claude_plugins/sdd/resources/domain_vocabulary.md`'s instruction to use the concept's existing name
rather than a synonym: "cohort reports" is the product's spoken name for the area, `reports.md` is
where it actually lives, and `qa_whole_system/reports/` should match the latter so grep, not memory,
answers "which plan covers this doc."

### No ordinal prefix

`spec_dd`'s numeric prefixes (`1. spec.md`, `3a. seam_qa/`) order the *phases of one pipeline* — a
spec moves from idea to spec to QA to done, and `3a`/`3b`/`3c`/`3d` sequenced one branch's
after-the-fact decomposition. None of that applies to nine permanent, independent area plans: they are
not phases of anything, they do not run in a fixed order, and adding a tenth area (a new
`docs/product/` file) should not require renumbering nine existing directories the way inserting a
step into a numbered pipeline would. Recommend plain, unprefixed, kebab-matching directory names
(`qa_whole_system/webhooks/`, not `qa_whole_system/7. webhooks/`); whatever ordering matters for a
particular run (e.g. "run content-editing-workflow before learner-experience because the latter reads
fixtures the former's `§0` needs") belongs in the manifest and in the dependent plan's own prose `§0`
note, not encoded in a directory name that would need to keep being correct as areas are added.

### Prerequisites between plans: state them in prose, do not build a dependency system

The idea's own item 2 — one shared `setup_qa_data` that seeds a fixture state usable by every plan
without per-plan `§0` rebuilds — already removes most of the "X must run before Y" problem by making
every plan start from the same known-good baseline rather than from whatever state a sibling plan left
behind. Where a plan still needs something created *during its own run* that another plan also happens
to use (e.g. an in-progress application before it can be reviewed), the existing FLS convention already
covers it: `3a. seam_qa`'s own `§0.1` rebuilds and reseeds from scratch rather than trusting another
plan's leftover state, and the seam plan's `§S4.setup` step creates the two registrations it needs
inline rather than assuming an earlier section made them
(`…/3a. seam_qa/frontend_qa_seam.md:288-291`). Follow the same pattern: a plan that has an ordering
dependency says so in one prose sentence at its own `§0` ("assumes `setup_qa_data` has run; if a fixture
this plan needs is absent, create it here rather than waiting on another plan"), and the manifest
carries the same note for a human scanning the whole suite. This is deliberately *not* a machine-checked
gate — FLS's whole QA-plan convention is prose read and judged by an agent acting as a human tester, and
a dependency system would be new machinery the rest of the convention does not have.

### A manifest is needed, and its absence has a specific, nameable cost

Yes — needed. Idea item 3 adds "a new SDD step … that updates the full system QA. It can create new
plans and/or update existing ones." That step cannot know what already exists without either
(a) globbing `qa_whole_system/**/plan.md` and re-deriving coverage by re-reading nine files' prose every
time, which is exactly the cost a manifest exists to avoid, or (b) missing an area entirely because a
plan was mid-split (compare `3a`–`3d`: without the signpost table naming what each sibling covers and at
what priority, a reader has no way to tell the four apart short of opening all four). The FLS precedent
for the manifest's shape already exists: the split-signpost's own table — `Plan | Covers | Priority`
(`…/3. frontend_qa.md:28-33`) — is exactly a manifest for four siblings, ad hoc and temporary. Generalise
that same three-column shape (plan / area covered / status, where "status" replaces "priority" — a
durable manifest cares about last-verified state and staleness, not urgency) into a permanent
`qa_whole_system/README.md` or `manifest.md`, one row per area, so the "update the full-system QA" SDD
step has a single file to read and a single file to update, rather than nine.

### Reports and screenshots should not be committed

`.gitignore` already treats regenerated QA evidence as local-only in two places directly relevant here:
`**/qa-artifacts/`, whose comment states plainly "QA report artifacts for the biggest cohorts — every
regeneration lands above the 1 MB check-added-large-files limit, so they stay local evidence only"
(`.gitignore:57-59`), and `qa-screenshots/`, the Playwright MCP output directory itself
(`.gitignore:64-65`). This is the same problem a durable suite has, worse: a `spec_dd/3. done/` QA run's
`screenshots/` is a **one-time** artifact from a spec that finished and will never run again, so
committing it is a defensible permanent record — and indeed there are already **1,094+** committed PNGs
under `spec_dd/3. done/**/screenshots/` (counted via glob; the tool truncated the listing at 100 of
1094 matches, confirming the true count is at least that high). A whole-system plan's report and
screenshots are regenerated on every run — weekly, or more, per the idea's own framing of a suite kept
"up to date" on a schedule — so committing them would mean git history growing by a full new
image set on every single run, forever, with no natural end the way a finished spec has one.
Recommend: `qa_whole_system/*/screenshots/` and `qa_whole_system/*/report.md` are gitignored
alongside `plan.md`'s neighbours, matching the existing `qa-artifacts/`/`qa-screenshots/`/`.sdd-work/`
entries rather than inventing a new rule; only `plan.md` and the manifest are committed. This does mean
a human cannot `git diff` two runs' reports for free — §5 addresses what to keep instead so that
capability is not simply lost.

---

## 4. Keeping the suite from rotting

**Conclusion first.** A full requirement-to-test traceability matrix is the wrong tool here — it would
duplicate `docs/product/` at claim granularity and drift immediately, which `domain_vocabulary.md`
already warns against for any invented restatement of an existing concept. Gherkin/BDD structure is
also the wrong tool: its value comes from a step-definition layer mechanically executing each clause,
and FLS's executor is an LLM agent directly interpreting prose with judgement — the opposite of what
Gherkin optimises for. What actually protects a durable suite is smaller and already partly present in
FLS's own habits: area-granularity (not claim-granularity) matching against `docs/product/`, a manifest
that records last-verified state, and treating the new SDD step's "update existing plans" instruction as
the suite's pruning point rather than a one-way ratchet of accretion.

### Traceability matrices: right granularity matters more than having one at all

A full requirements traceability matrix links every requirement to at least one test case and is
valued in regulated domains and Agile teams alike for catching gaps and locating blast radius when a
requirement changes, but it costs continuous upkeep and is most often criticised, unmaintained, as a
spreadsheet nobody updates
([Perforce, "Requirements Traceability Matrix"](https://www.perforce.com/resources/alm/requirements-traceability-matrix);
[Kualitee, "RTM: Death by Excel or a Useful Tool?"](https://www.kualitee.com/blog/test-management/requirements-traceability-matrix-death-by-excel-or-a-useful-tool/);
[aqua-cloud, "Traceability Matrix in Software Testing"](https://aqua-cloud.io/traceability-matrix/)).
The decided carve-up already **is** a coarse traceability matrix: one plan per `docs/product/` area is a
1:1 mapping at document granularity. Going finer — one row per sentence or claim inside a doc — would
mean maintaining a second document that restates `docs/product/`'s own claims as "requirements," which
is precisely the invented-synonym failure `domain_vocabulary.md` warns against: the concept (what the
product claims to do) already has a home, and a matrix that paraphrases it is a translation table
someone has to keep in sync by hand. FLS's own bug-report style already does fine-grained traceability
the cheap way — by citing the actual source location (`freedom_ls/reports/gather.py:293`,
`…/3a. seam_qa/qa_report.md:354`) rather than a matrix row — and a durable plan's `§0` should cite the
`docs/product/<area>.md` section it walks the same way, in prose, rather than in a separate table.

### Gherkin / living documentation: overhead, not fit, for this executor

Specification-by-example tools (Cucumber, Gherkin) are valued because the same text that documents
behaviour also drives automated execution
([search summary, Gherkin as living documentation and spec-by-example](https://dl.acm.org/doi/10.1145/3678719.3685692)).
Recent work on LLM-driven Gherkin execution frames the goal explicitly as making scenarios
"deterministic enough for language models to follow" through stable, implementation-free vocabulary
([AutomationPanda, "Gherkin Guidelines for AI"](https://github.com/AutomationPanda/gherkin-guidelines-for-ai/blob/main/gherkin-guidelines.md)),
and that same research base found large, loosely-specified scenarios cause LLM agents markedly more
execution errors than small, well-defined steps
([ACM DL, "First Experiments on Automated Execution of Gherkin Test Specifications with Collaborating LLM Agents"](https://dl.acm.org/doi/10.1145/3678719.3685692)).
Both of those findings actually describe FLS's plans as they already are, without Gherkin's
ceremony: `do_qa.md` explicitly frames its executor as "a human QA expert" exercising "exploratory
visual judgement" that "MUST NOT be delegated" (`do_qa.md:7`, `do_qa.md:302-305`) — there is no
step-definition layer translating a `Given/When/Then` clause into a browser action; the agent reads the
prose directly and acts. Gherkin's payoff (one text, two consumers — a human reader and a mechanical
runner) requires that second consumer to exist. FLS has no such runner, so adopting Gherkin's syntax
would add a translation tax (write the scenario in constrained Given/When/Then vocabulary, then have the
agent translate it back into concrete browser actions and judgement calls) while gaining none of the
benefit Gherkin exists for. FLS's existing convention — numbered steps, an inline `Expect:` clause,
rich narrative context about *why* the step exists and what regression it guards — is functionally
already "specification by example," just without Gherkin's controlled vocabulary, and it should stay
prose.

### Known failure modes of manual regression suites, and what FLS should borrow

Regression-suite guidance converges on a few maintenance habits: periodic "sprint pruning" of obsolete
tests, quarterly hygiene passes to catch bloat and duplicated coverage, and risk-tiering so low-value
tests do not dominate every run
([Katalon, "How to Maintain Regression Tests?"](https://katalon.com/resources-center/blog/how-to-maintain-regression-tests);
[PullNotifier, "10 Regression Testing Best Practices for 2025"](https://blog.pullnotifier.com/blog/10-regression-testing-best-practices-for-2025)).
The mechanism FLS should reuse for this is the new SDD step itself (idea item 3): give it explicit
license to *delete or merge* sections, not only add them, and make the manifest's per-area status field
the trigger for a hygiene pass (an area unverified for a long stretch is exactly the "prune or
prioritise" signal the sources above recommend making visible rather than discovering by accident).

FLS also already has direct, first-party evidence of the sharpest failure mode named in the prompt —
"flaky by prose ambiguity." `3a. seam_qa`'s own report records two mid-run rewrites to the plan file
because the plan contradicted its own fixture table (a resume test written against a
`submit_on_exit` form that cannot structurally support resuming) and because it told the tester to hand-
edit a field the model deliberately makes read-only (`…/3a. seam_qa/qa_report.md:384-401`). For a
one-shot spec plan this self-correction is a courtesy noted once and archived. For a durable plan it is
existential: the same drift will be rediscovered on every future run unless the correction is written
back into `plan.md` itself, not left sitting in one run's `report.md` (which, per §3, is gitignored and
will be overwritten by the next run anyway). The clearest, cheapest anti-rot rule available to FLS: any
run of a durable plan that finds the plan wrong about the product must edit `plan.md` in place before
finishing, the same instinct `3a` already had, made mandatory rather than incidental.

### Detecting coverage gaps mechanically

Diff-based coverage tooling in the broader industry works by inspecting a pull request's changed lines
against what the regression suite exercises
([Qodo, "How Can AI-Powered Test Coverage Detect PR-Level Gaps Before Merge?"](https://www.qodo.ai/blog/ai-powered-test-coverage/)).
FLS has an equivalent mechanical signal without adopting any new tooling, precisely because the carve-up
is 1:1 with `docs/product/`: a **new file** under `docs/product/` is a checkable, no-judgement trigger
for "a tenth plan is needed" (`docs/product/*.md` is a stable, small directory — `Glob` against it costs
nothing). A **large diff to an existing** `docs/product/<area>.md` since the date/commit the manifest
last recorded as "verified" is the equivalent signal that an *existing* plan may be stale — this only
works if the manifest records that checkpoint per area (§3), which is one more reason the manifest is
load-bearing rather than optional. New URL patterns (`freedom_ls/*/urls.py`) and new templates are a
noisier secondary signal — useful for a human skimming "what shipped that no product doc yet
mentions," but they are a proxy for the same underlying fact the `docs/product/` diff already gives
directly, so they should not become a second parallel gap-detection mechanism.

---

## 5. Report format

**Conclusion first.** The user's decided shape (bugs first, then a results table, then per-bug detail,
then methodology/scoping/notes) is not a departure from IEEE 829 — it is IEEE 829's own ordering with
one section promoted: 829 already puts its narrative "Summary of Activities" near the end
([ZetCode, "IEEE 829 Tutorial"](https://zetcode.com/terms-testing/ieee-829/)), which is where the
decided shape's "methodology/scoping/notes" already sits. The one real departure is treating the bug
list itself as the executive summary, which is a defensible, busy-reader-first choice rather than a
rejection of the standard. What is missing from FLS's current report and worth adding for a *durable*
suite specifically is a severity vocabulary distinct from FIXED/UNRESOLVED, and a mechanism for making
two runs' reports comparable by machine, not just by eye.

### What to borrow, and from where

IEEE 829's Test Summary Report defines eight sections — report identifier, executive summary,
variances from plan, comprehensive assessment, results summary, evaluation/recommendations, summary of
activities, approvals
([ZetCode, "IEEE 829 Tutorial"](https://zetcode.com/terms-testing/ieee-829/);
[professionalqa.com, "Test Summary Report"](https://www.professionalqa.com/test-summary-report)).
Modern practice keeps the *shape* (identify → summarise → assess → detail → close with process notes)
and drops the paperwork (no separate "approvals" section makes sense for an agent-generated report with
no sign-off workflow). Allure/ReportPortal-style reports contribute two ideas worth taking directly:
grouping failures by feature/story rather than by raw test order, and an explicit **severity** field —
Allure's vocabulary is blocker/critical/normal/minor/trivial, with an unmarked test defaulting to
"normal"
([search summary, Allure severity levels](https://github.com/orgs/allure-framework/discussions/1512)).

### Summary table columns and severity vocabulary

The table's columns should be exactly what `do_qa.md`'s own scratch-record shape already carries — no
new data model needed, only a different rendering order: **test ID**, **area** (the plan/section it
belongs to — meaningful once nine areas exist where today there is one), **viewport**, **status**
(pass/fail/partial/blocked/**not run**, the last one specifically for the partial-run case below), and
a short **note** column that doubles as the cross-reference to a bug ID when the row is a failure —
this is the reverse index of the `bug` record's existing `manifestations: [{test_id, viewport}]` list
(`do_qa.md:387-394`), so a reader can jump from the table straight to the matching `## Bug` section.

For severity: FLS's existing **FIXED/UNRESOLVED** vocabulary and a **blocker/major/minor** severity
vocabulary answer two different questions and should coexist rather than replace one another. FIXED/
UNRESOLVED is a same-run *triage outcome* — it only exists once Step 13 has decided whether to auto-fix
(`do_qa.md:420-429`, `436-537`). Severity is an assessment of *how bad the bug is*, assigned the moment
it is found, independent of whether it ever gets a fix attempt. This distinction barely mattered for a
one-shot spec QA report, whose bugs are triaged the same run they are found and then the report is
archived. It matters a great deal for a durable suite, where UNRESOLVED bugs accumulate across dozens
of runs into a backlog a human has to prioritise — and prioritising an undifferentiated list of
UNRESOLVED items is exactly the job severity exists to do. Recommend adding a `severity` field to the
`bug` record (blocker/major/minor is the smaller, sufficient vocabulary suggested in the prompt; Allure's
five-level scale is more granularity than a QA-plan bug list needs) alongside, not instead of, the
existing FIXED/UNRESOLVED status.

### Making the report diffable between runs

Three things make two runs comparable by a human at a glance, and FLS already has the raw material for
all three:

- **Stable test IDs.** The existing `S1`/`G11`/`1.1` convention gives this for free *as long as IDs are
  never renumbered or reused* — a durable plan retires a dead test by marking it retired in place, the
  way a database never reuses a deleted primary key, rather than deleting the line and letting every ID
  after it shift. Renumbering has no cost for a one-shot spec plan (there is no "last run" to compare
  against) and a real cost for a plan re-run for years.
- **Stable ordering.** The summary table should list rows in test-ID/section order, not discovery order
  and not fail-first — fail-first belongs only to the top-of-report bug list the user has already
  decided on. An unordered or run-order table is the one design choice that would make eyeballing "what
  changed since last time" impossible even with stable IDs.
- **A machine-readable sidecar is worth it, and FLS already produces one — it just deletes it.**
  `.sdd-work/qa_scratch.jsonl` is exactly a per-run, machine-readable record of every `test`, `bug`,
  `scoping` and `smoke_gate` event (`do_qa.md:159-171`, `234-236`, `287-291`, `387-394`), and Step 16
  deletes it once the report and todo have consumed it (`do_qa.md:601-616`) — correct for a one-shot
  spec run, wrong for a durable suite that wants runs comparable over time. The natural adaptation is
  not a new format but a change of lifecycle: keep a compacted `test_id → status` JSON per plan run
  (locally, per §3's gitignore recommendation — the same "regenerated evidence stays local" rule that
  already governs `qa-artifacts/`), so a future run or a small diff script can compare two runs' status
  maps mechanically instead of a human re-reading two full markdown reports.

### Expressing a partial run

FLS has direct precedent for a run that "ran out of budget and left twelve sections unexecuted" — the
`better_course_progress_tracking` split handled it by carving the unreached sections into their own
named sibling plan (`…/3. frontend_qa.md:16-17`, `31`). That resolution does not transfer to a durable
suite: a spec-run plan is temporary and can be split into ad hoc siblings that never run again once the
spec ships, but a durable area plan is permanent — the same plan will simply be re-run later, in full,
not split. What a durable plan's report needs instead is to say the incompleteness plainly rather than
resolve it structurally: an explicit "run coverage" line in the methodology section naming which
sections/test IDs were not reached and why (budget exhausted, smoke-gate abort, environment
unreachable), plus — per the summary-table recommendation above — a **`not_run`** status value distinct
from pass/fail/partial/skip, so the unreached rows are visible directly in the table rather than only in
a prose aside a reader could miss. Without a distinct `not_run` state, a blank or omitted table row for
an unreached test is indistinguishable from a row someone forgot to write, which is precisely the
ambiguity a durable, repeatedly-read report cannot afford.

---

## References

- [Perforce — "Requirements Traceability Matrix: Definition, Benefits, and Examples"](https://www.perforce.com/resources/alm/requirements-traceability-matrix)
- [Kualitee — "Requirements Traceability Matrix (RTM) Guide"](https://www.kualitee.com/blog/test-management/requirements-traceability-matrix-death-by-excel-or-a-useful-tool/)
- [aqua-cloud — "Traceability Matrix in Software Testing"](https://aqua-cloud.io/traceability-matrix/)
- [AutomationPanda — "Gherkin Guidelines for AI" (gherkin-guidelines-for-ai)](https://github.com/AutomationPanda/gherkin-guidelines-for-ai/blob/main/gherkin-guidelines.md)
- [ACM Digital Library — "First Experiments on Automated Execution of Gherkin Test Specifications with Collaborating LLM Agents"](https://dl.acm.org/doi/10.1145/3678719.3685692)
- [Katalon — "How to Maintain Regression Tests? A Practical Guide"](https://katalon.com/resources-center/blog/how-to-maintain-regression-tests)
- [PullNotifier — "10 Regression Testing Best Practices for 2025"](https://blog.pullnotifier.com/blog/10-regression-testing-best-practices-for-2025)
- [Qodo — "How Can AI-Powered Test Coverage Detect PR-Level Gaps Before Merge?"](https://www.qodo.ai/blog/ai-powered-test-coverage/)
- [ZetCode — "IEEE 829 Tutorial: Test Documentation Standard Explained"](https://zetcode.com/terms-testing/ieee-829/)
- [professionalqa.com — "Test Summary Report"](https://www.professionalqa.com/test-summary-report)
- [GitHub — allure-framework discussion #1512, "How to set the severity level in the allure report"](https://github.com/orgs/allure-framework/discussions/1512)

In-repo evidence cited above:

- `claude_plugins/fls-dev/commands/do_qa.md` (full command contract)
- `claude_plugins/sdd/resources/domain_vocabulary.md` (vocabulary discipline)
- `spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/3a. seam_qa/frontend_qa_seam.md`
- `spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/3a. seam_qa/qa_report.md`
- `spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/3. frontend_qa.md` (split signpost)
- `spec_dd/3. done/2026-02-19_19:25_deadlines/3. frontend_qa.md` (old-style plan, no `§0`)
- `.claude/fls-dev/config.md`
- `.gitignore`
- `docs/product/README.md` and `docs/product/*.md`
- `spec_dd/1. next/mega-qa/idea.md`

---

status: ok · reason: researched FLS's own QA-plan and do_qa.md conventions in depth, cross-checked against .gitignore and committed-screenshot volume, and grounded the traceability/Gherkin/report-format recommendations in external sources; all claims either cite an in-repo path or a fetched URL
