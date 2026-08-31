# Idea 2 of 3: the whole-system QA suite

**Run second.** The plans can be written and run against dev before idea 1 exists. They cannot run
against a deployed environment until it does, so finish idea 1 first if you want the staging half.

---

## Why

FLS has no way to answer "does the whole product still work?" Every QA plan we have is written for one
spec, run once, and archived. Coverage of the system as a whole is whatever the union of those runs
happens to be, which nobody has ever measured.

We want a durable suite that covers the system, lives outside `spec_dd/`, and is kept current as a
normal part of shipping a feature rather than as an occasional clean-up.

---

## The suite has two tiers

A journey tier and an area tier, because they answer different questions and want different cadences.

**Journeys** are short end-to-end walks of the critical path, crossing whatever they need to cross.
They answer "is the product up?" and are cheap enough to run on every staging deploy:

- a learner logs in and enrols in a course
- a learner works through a course and completes it, with progress and the resume pointer advancing
- a learner sits a quiz and gets a score
- an educator opens the panel and reads a cohort's progress
- a staff user generates and downloads a cohort report

**Areas** go deep on one part of the product and answer "did anything here regress?" Seven of them,
derived from `docs/product/`: authentication, learner experience, educator interface, admin interface,
cohort reports, webhooks, and deployment health. The last three are genuinely thin. A cohort report
can only be triggered and downloaded, webhooks can only be configured and test-sent, and deployment
reduces to two health endpoints. They should stay thin rather than be padded to look like their
siblings.

The six remaining product docs get no plan of their own. Learner tracking has no pages of its own; it
is what the journey plans assert while walking someone through a course. The security document's one
browser-provable claim, the educator interface's unfiltered Courses section, is a probe inside the
educator interface plan. Content editing, configuration and the roadmap cannot be reached from a
browser at all. Multi-tenancy is covered below.

The journeys are what let the areas stay narrow. Cross-cutting behaviour has a home, so no area plan
has to duplicate another to cover it.

The roadmap is the exclusion list. Several things the product docs describe are not built, and a plan
that tests them will manufacture failures. The educator Courses authorisation gap is the opposite
case: it is a known, documented defect, so plans assert it as current behaviour rather than reporting
it as a new finding.

---

## What has been settled

### One directory per plan, and reports are not committed

`/fls-dev:do_qa` writes `qa_report.md` and `screenshots/` beside the plan it ran. FLS has already been
bitten by this once and split a flat plan into subdirectories so that concurrent runs could not delete
each other's artifacts. That was for four temporary siblings. This suite has a dozen permanent ones,
re-run indefinitely.

So: one directory per plan under `qa_whole_system/`, and a manifest at the top recording what each
plan covers, its inheritance status, and when it was last verified. The new SDD step needs one file to
read rather than a dozen.

Reports and screenshots are regenerated every run and stay out of git, matching how the repo already
treats QA evidence. There are over a thousand committed screenshots under `spec_dd/3. done/`. That is
a defensible permanent record for specs that finished and will never run again, and exactly the wrong
model for a suite that runs forever.

Plan directories get no ordinal prefix. They are not phases of a pipeline, and adding an eighth area
should not renumber seven others.

### What cannot be tested against staging

Being honest about this up front is what stops the suite quietly lying about its coverage.

**Email.** Signup verification and password reset require following an emailed link. Dev has Mailpit.
A staging box gives the agent no inbox. Idea 1's seed attaches verified email addresses so every other
plan can log in; the verification and password-reset steps themselves are marked dev-only.

**Multi-tenancy.** Staging is one hostname, so there is no second tenant to leak into and nothing for
an ordinary browser walk to demonstrate. Site isolation gets a dev-only plan using the multi-port demo
sites. That plan also has to unset `FORCE_SITE_NAME`, since dev's shipped settings pin every request
to one site and thereby defeat the very isolation the multi-port setup exists to show.

**Cohort report contents.** Reports are PDFs. A browser can confirm that generation was triggered,
that a download link appeared, and that a PDF of non-trivial size came back. Nothing inside the PDF is
assertable from a browser. That already belongs to the WeasyPrint-marked pytest suite.

**Anything needing a worker.** Cohort report generation and webhook delivery both dispatch to an
out-of-process worker. Dev and test run those tasks synchronously inside the request, so a test can
pass in dev purely because dev needs no worker, then hang forever against staging where one is not
running. Plans touching either must use a bounded wait and treat "still pending" as a named, expected
failure rather than a hang.

**Course visibility and access gating.** Dev ships with overrides that present every course as
published and free, so coming-soon badges, hidden-course behaviour and the application-gated flow
cannot be exercised in dev without turning those off first. This is the one case where staging is the
better environment.

### The report leads with what went wrong

Failures and bugs first, then a table of every test with its result, then per-bug detail with
screenshots, then methodology and notes.

Two additions the durable case needs and the one-shot case never did. A severity for each bug that is
independent of whether it got fixed, because unresolved bugs now accumulate across runs into a backlog
someone has to prioritise. And a distinct "not run" status, because a suite that exhausts its budget
mid-way must say so in the table rather than leave rows that look forgotten. FLS has already had a QA
run stop with twelve sections unexecuted.

Test IDs are stable and never reused, and the table is ordered by ID, so two runs can be compared.

### A plan that is wrong about the product gets fixed in place

Spec QA runs already do this occasionally as a courtesy. For a durable plan it is the whole
maintenance mechanism. A correction left in a report is lost when the next run overwrites it, and the
same wrong instruction gets rediscovered every time. Any run that finds the plan contradicting the
product edits the plan before finishing.

### A new SDD step keeps the suite current

It sits near the end of the todo, after the feature is built and QA'd. It may create plans, update
them, and delete or merge sections. The licence to remove matters as much as the licence to add, or
the suite only ever grows.

The gap signals are mechanical. A new file under `docs/product/` means an area is missing. A large
diff to an existing one since the manifest's last-verified checkpoint means a plan is stale.

Plans stay prose. The executor is an agent reading and exercising judgement, not a step-definition
runner, so Gherkin would add a translation tax and buy nothing. A claim-level traceability matrix is
also the wrong tool: it would restate `docs/product/` in a second document that drifts immediately.
One plan per area already is the traceability map, at the granularity that can be maintained.

---

## What `/fls-dev:do_qa` has to grow

The command assumes a feature branch throughout, and a whole-system run invalidates most of that.

There is no `todo.md` to tick, so the four categories it is allowed to append need a different sink.
There is no branch diff to scope against, because the suite tests everything that is live, so the
scoping gate has nothing to compute from and the smoke gate has no "primary changed page" to derive.
There is no dev server to start or kill when the target is a URL, and no branch badge to check;
against staging the right question is which build is deployed, not which branch is checked out. Its
ladder for fixing broken fixtures is entirely local, and idea 1's endpoint replaces all of it.

The auto-fix loop has no staging equivalent either. It commits a fix and re-verifies against a dev
server that auto-reloads. Staging serves an already-deployed build, so a staging run can only report.

The run needs its environment as an input: which target, which base URL, which credentials. Those
belong in configuration, not in plan bodies, and that parameterisation is also what makes idea 3
possible at all.

---

## Research

`research_fls_functional_surface.md` has the area-by-area assessment, the URL inventory grouped by who
can reach what, the non-page surfaces, and the list of features the roadmap says are not built.

`research_qa_plan_suite_organisation.md` enumerates every contract `/fls-dev:do_qa` places on a plan
today and which break, and carries the reasoning behind the directory layout, the report format, and
the decisions against Gherkin and a fine-grained traceability matrix.
