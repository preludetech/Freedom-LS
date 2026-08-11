# Basic reports: cohort progress PDF

We need to be able to generate a PDF report showing the progress of a cohort. Initially this is
triggered from the admin panel. Later on we will work it into an automated email — that is out of
scope for now, but the design must make it a small addition rather than a rewrite.

Supporting research lives alongside this file: `research_pdf_engines.md`,
`research_report_layout_ux.md`, `research_quiz_item_analysis.md`,
`research_fls_data_availability.md`, `research_generation_and_delivery.md`.

## Scope

One report per **cohort**, covering **all courses that cohort is actively registered for** (one
section per course). Audience is internal educators and staff only — real student names, no
anonymisation.

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

## Report structure

**0. Title page** (portrait)
Cohort name, the list of courses covered, generated-at timestamp *with timezone*, who generated it,
and a plain "figures reflect data as of generation time" caveat.

**0.5. Cohort at a glance** (portrait)
Headline numbers — cohort size, median completion, count not started, count complete — and a
**students needing attention** list: name, a one-line reason, and a page reference into their detail
section. Attention rules for v1, all derivable today:
- 0% complete / no recorded activity
- failed their latest attempt at a quiz
- no activity in the last N days (N to be settled in the spec)

If more students qualify than fit comfortably, show the headline count rather than silently
truncating.

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

Reuse the existing FLS brand colour roles rather than inventing a report palette — Forest for
on-track/complete, Sand (fill only, never as text colour) for warning, Signal for failing/behind,
Horizon for in-progress. Use tints for full table cells and solid fills only for small badges.

**Colour is never the only signal.** Every status cell also carries the number and a distinct glyph.
These PDFs will be printed, sometimes in greyscale on an office printer, where two of the three RAG
tiers can land at similar greys. Print a sample in black and white before sign-off.

## Data gaps to work around

Surfaced by `research_fls_data_availability.md`. These are existing product gaps, not things this
feature creates.

- **"Last item completed" is not stored.** `CourseProgress.last_accessed_item` means last *viewed*.
  Derive it from `max()` over `TopicProgress.complete_time` and `FormProgress.completed_time` across
  the course's items.
- **Activities are not tracked at all** — there is no `ActivityProgress` model. Skip them in item
  lists and exclude them from completion totals, matching what the app already does. Adding activity
  tracking is out of scope here.
- **Free-text quiz questions have no correctness concept** and are effectively always scored wrong.
  Exclude them from the wrong-answer aggregation, label them "not auto-graded", and at most show the
  raw text answer. Do not lump them into the confusion tally.
- **Multi-select questions are scored leniently** — a question counts as correct if *any* selected
  option is correct. The report must reuse that exact definition to stay consistent with scores shown
  elsewhere, and say so in the definitions block.
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
  their answers. Serve it only through a permission-checked download view.
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
- Retention policy for stored report files, and who may download them (a dedicated permission, or
  reuse of the existing cohort-view permission).
- Whether the summary table should include inactive (`is_active=False`) course registrations.
- Whether repeated wrong answers by the same student across attempts count once or every time in the
  per-student tally.
