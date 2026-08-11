# Basic reports: cohort progress PDF

We need to be able to generate a PDF report showing the progress of a cohort. Initially this is
triggered from the admin panel. Later on we will work it into an automated email — that is out of
scope for now, but the design must make it a small addition rather than a rewrite.

Supporting research lives alongside this file: `research_pdf_engines.md`,
`research_report_layout_ux.md`, `research_quiz_item_analysis.md`,
`research_fls_data_availability.md`, `research_generation_and_delivery.md`.

## Scope

One report per **cohort**, covering **every course that cohort is registered for** (one section per
course). Audience is internal educators and staff only — real student names, no anonymisation.

Inactive course registrations (`is_active=False`) are **included** — learners did that work and it
should not vanish from the record. Mark those sections as inactive so the reader knows the course is
no longer running for this cohort.

All pages A4. Portrait by default; landscape for the wide summary tables.

## Decisions made

- **Renderer: WeasyPrint.** It is the only engine that does every hard requirement in a single
  render — repeating `<thead>` across page breaks, mixed portrait/landscape via CSS named pages,
  `counter(page)`/`counter(pages)` footers, `break-inside`/`break-before`, and PDF bookmarks. Layout
  stays in HTML/CSS templates. Accepted cost: downstream projects must install Pango, cairo,
  gdk-pixbuf and HarfBuzz system packages. Do **not** feed it the full compiled Tailwind stylesheet
  (known to produce ignored/invalid CSS) — author a small dedicated print stylesheet.
- **Generation: always a background task, with the PDF stored.** A `GeneratedReport` record with a
  file field; the admin action enqueues via the existing `django-tasks-db` backend and returns
  immediately; a Reports changelist shows status and a download link. Dev/test get synchronous
  behaviour for free via `ImmediateBackend` — the code path does not branch. This is also exactly
  what the future automated email needs.
- **Cohort-wide quiz analysis uses each student's first attempt** at each quiz, to avoid
  answer-memorisation from retakes skewing the picture. The report must state this rule on the page.
  Per-student detail still shows every attempt.
- **The report carries a "cohort at a glance" page** (see section 0.5 below) with a students-needing-
  attention list, using only rules derivable from data we already have.
- **The multi-select quiz scoring bug is fixed as part of this work** (see below). The report's whole
  purpose is showing where people went wrong; it cannot sit on top of scoring that marks a wrong
  answer right.

## Report structure

**0. Title page** (portrait)
Cohort name, the list of courses covered, generated-at timestamp *with timezone*, who generated it,
and a plain "figures reflect data as of generation time" caveat.

**0.5. Cohort at a glance** (portrait)
Headline numbers — cohort size, median completion, count not started, count complete — and a
**students needing attention** list: name, a one-line reason, and a page reference into their detail
section.

If more students qualify than fit comfortably, show the headline count rather than silently
truncating.

**At-risk rules are a registry of named rule objects, not a hardcoded `if` chain.** Each rule is a
small, independently testable unit carrying an identifier, a human-readable label, and a function
that takes a student's already-gathered report data and returns either a reason string or nothing.
The report iterates the registry per student and collects whatever comes back; a student can trip
several rules and show several reasons.

This matters because "what counts as at risk" is exactly the thing that will be tuned once real
educators use the report, and it varies by institution. Adding, removing or reordering a rule should
be a one-line change to a list, with no edit to the report-building or rendering code. Since FLS is
installed into other projects, the registry should also be overridable per project via the existing
per-app settings mechanism (the `AppSettings`/`declared_settings` pattern, as `COURSE_ACCESS_BACKEND`
does) so downstream projects can supply their own rules without forking FLS. Rules take their
thresholds as parameters rather than baking in constants, so the same rule can be reused at a
different number.

Rules must operate on data already gathered for the report — a rule that issues its own queries per
student reintroduces the N+1 problem the report is otherwise careful to avoid.

Ship these three for v1:
- 0% complete / no recorded activity
- failed their latest attempt at a quiz
- no activity in the last N days (N to be settled in the spec)

**0.6. Contents and definitions** (portrait)
Table of contents with page numbers (plus PDF bookmarks for on-screen readers), and a short
methodology block stating what "complete" means, that quiz score means *latest* attempt, what counts
as an attempt, the first-attempt rule for cohort analysis, and the RAG legend.

**1. Summary of student progress** (landscape)
**One table per course**, not one mega-grid across all courses. Each table: student rows against
completion (percentage/count plus a simple fill bar), last course item completed and when, then a
column group per quiz showing latest score and number of attempts.
- Repeat the header row on every page the table spans.
- Cap at roughly 10–12 data columns; split the table rather than shrinking the type. (This number is
  an estimate — validate it against a real rendered sample.)
- Band alternate rows so the eye tracks across wide tables.
- Abbreviate quiz column headers with a legend under the table title.
- Order columns by the quiz's position in the course, not alphabetically.

**2. Details per student** (portrait)
One page-break-forced section per student, alphabetical by surname, with a running header carrying
the student's name. Per student: every item completed and when; every quiz attempt with score and
date; and per quiz, each question they got wrong, how many times, and which incorrect options they
picked (rolled up across all their attempts).

**Every at-risk flag the student tripped is shown at the top of their own section**, with the same
rule labels and reason text used on the at-a-glance page. The two views are rendered from one
evaluation of the rule registry, never computed twice — an educator who turns to a student's pages
after spotting them on page 2 must find the same flags, and a student who tripped nothing shows a
plain "no flags" line so the absence is explicit rather than inferred.

Students with nothing to show get an explicit "No activity recorded" line — never silent omission,
which reads as a data bug.

**3. Quiz confusions across the cohort** (portrait)
Per quiz: each question people got wrong, with the incorrect options chosen and how often. Rank
worst-first by error rate, cap the list per quiz and **disclose the cap** ("showing worst 10 of 23
questions with at least one incorrect answer"). Always show the correct option alongside the wrong
ones so the table stands alone.

Raw counts and percentages only — **no discrimination indices or point-biserial statistics**. With
cohorts of 5–50 those are unstable to meaningless. Below a small-n threshold, show plain counts
("7 of 9 students got this wrong") rather than percentages implying precision. Carry a short
interpretive caution: a high error rate can mean a hard-but-fair question, not a broken one.

## Colour and accessibility

Use the existing semantic role tokens rather than naming specific colours, so the report stays
portable across themes: `success` for on-track/complete, `warning` for behind/borderline, `error` for
failing/significantly behind, `info` for in-progress, and `surface`/`muted` for not-started.

For full table cells use the `*-light` tints with their paired `on-*-light` foregrounds; reserve the
solid role fills with their `on-*` foregrounds for small badges. Never hardcode a hex value or a
brand colour name in the report templates or stylesheet — a downstream theme overrides these tokens,
and a report that names colours directly will silently stop matching its own product.

**Colour is never the only signal.** Every status cell also carries the number and a distinct glyph.
These PDFs will be printed, sometimes in greyscale on an office printer, where two RAG tiers can land
at similar greys — and since a downstream theme can pick any hue for these roles, that risk varies by
theme and cannot be designed away centrally. The glyph is what makes the report survive it. Print a
sample in black and white before sign-off.

## In scope: fix multi-select quiz scoring

`FormProgress.score_quiz()` awards the mark for a question if **any** selected option is correct
(`freedom_ls/student_progress/models.py:443-447`), breaking out of the loop on the first correct hit.
On a checkbox question with two correct and two incorrect options, a student who ticks all four scores
full marks — ticking everything is a guaranteed 100%. `get_incorrect_quiz_answers()` repeats the same
rule (`models.py:505`), so the wrong-answer view agrees with the wrong score and the bug is invisible.
Single-select `multiple_choice` questions are unaffected, since only one option can be selected.

This is a bug, not a design choice, and it is fixed here rather than filed away: a report whose stated
purpose is revealing where learners went wrong cannot be built on scoring that marks a wrong answer
right, and under the current rule a checkbox question can never surface as confusing.

- **Correct rule: exact match, all-or-nothing.** A checkbox question is correct when every correct
  option is selected and no incorrect one is. No partial credit — it is the easiest rule to state on
  the report's definitions page and it leaves `max_score` semantics untouched.
- Both `score_quiz()` and `get_incorrect_quiz_answers()` must move to the new rule together, along
  with the bulk equivalent the report needs, so scores and wrong-answer detail never diverge.
- **No rescore of historical attempts.** Scores are frozen at submission time, and we are not
  backfilling them — learners keep the score they were shown. The consequence to handle: for checkbox
  questions answered before the fix, a stored score can be higher than a live re-derivation of the
  same answers, so the summary table's score and the wrong-answer detail may not reconcile. The
  report shows the stored score as-is and the definitions block notes that scoring for multi-select
  questions changed, so the mismatch reads as history rather than a reporting bug.
- Expect knock-on effects beyond reporting: the student-facing quiz results view, pass/fail via
  `quiz_pass_percentage`, and any content authored on the assumption that ticking everything passes.

## Data gaps to work around

Surfaced by `research_fls_data_availability.md`. These are existing product gaps, not things this
feature creates.

- **"Last item completed" is not stored.** `CourseProgress.last_accessed_item` means last *viewed*.
  Derive it from `max()` over `TopicProgress.complete_time` and `FormProgress.completed_time` across
  the course's items.
- **Activities are left out of the report entirely.** They are not tracked — there is no
  `ActivityProgress` model — so omit them from item lists and from completion totals, matching what
  the app already does. Not a question for the spec to reopen.
- **Free-text quiz questions are left out of the report entirely.** We are not using them in quizzes.
  They have no correctness concept in the app anyway (`short_text`/`long_text` answers are effectively
  always scored wrong), so omit them from the wrong-answer aggregation and the confusion tally rather
  than inventing a way to display them. Not a question for the spec to reopen.
- **`QuestionOption.correct` can be edited after students have answered.** Frozen `FormProgress.scores`
  and a live re-derivation of "what they got wrong" can therefore disagree. Date-stamp the report and
  disclose the limitation; detecting *which* questions changed is not possible today (no timestamp on
  the content models).
- **Cohort membership has no history** — no `is_active`, no "left on date X". The report reflects
  membership as of generation time; say so on the title page.
- **Courses a student registered for individually** (outside the cohort's own registrations) are out
  of scope. Note the exclusion in the methodology block so it isn't mistaken for a bug.
- **`quiz_pass_percentage` is nullable** and `passed()` raises when it is unset. Guard defensively.

## Non-negotiables for implementation

- **Site isolation.** `SiteAwareManager` only filters by site when there is an HTTP request. A
  background task has none, so every query must filter explicitly by the cohort's `site_id` — pass
  ids, not model instances, into the task, following the existing webhook dispatch pattern. Getting
  this wrong leaks another tenant's students into a PDF.
- **The stored PDF must never be reachable via a public media URL.** It contains student names and
  their answers. Serve it only through a download view gated on the existing object-level
  `freedom_ls_student_management.view_cohort` permission for the cohort the report covers — the same
  check `educator_interface` already uses — rather than inventing a report-specific permission.
  Generating a report must be gated on that same permission, not just on staff status.
- **Layer it as: gather data → render PDF → thin trigger adapters** (admin action now; management
  command and scheduled email later). The gather and render layers should not know what triggered
  them.
- **Batch the queries.** The existing `FormProgress.get_incorrect_quiz_answers()` is per-attempt and
  unbatched — calling it in a loop over a cohort would run thousands of queries. It needs a bulk
  equivalent.
- One in-flight report per cohort, so a double-click or two staff members don't spawn duplicate
  expensive jobs.

## Open questions for the spec

- The "no activity in N days" threshold for the attention list.
- The small-n threshold below which percentages are replaced by plain counts.
- Retention policy for stored report files.
- Whether repeated wrong answers by the same student across attempts count once or every time in the
  per-student tally.
