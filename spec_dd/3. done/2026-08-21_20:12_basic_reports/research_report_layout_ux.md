# Report layout and UX research

Scope: layout and UX for a per-cohort, all-courses, on-demand PDF report generated from the Django
admin, for internal educator/staff eyes only (real names, no anonymisation). A4, orientation per
section. Sections already decided: (0) title page, (1) wide student x quiz/progress summary table,
(2) per-student detail, (3) cohort-wide quiz confusions.

## Bottom line

- **Lead with a one-page "at a glance" strip, not the wide table.** Put cohort N, median/mean
  completion, count not-started, count at-risk (behind schedule or failing), and a short "students
  needing attention" list on page 2, right after the title page and before the big matrix. Busy
  educators should get the picture in 30 seconds without reading the rest. See Q8.
- **Split the summary table by concern, not one mega-grid.** One table per course (or two: a
  "completion" table and a "quiz scores" table) rather than one table with every course's every quiz
  as a column. FLS already renders a students x course-items matrix in the educator interface
  (`docs/product/educator-interface.md`) — reuse that mental model, but for print, cap columns per
  table (see Q3) and repeat per course rather than trying to fit all courses side by side.
- **Reuse FLS's existing colour roles for status, don't invent new ones.** Forest `#38A169` =
  complete/on track, Sand `#F6E05E` (fill only, never as text colour) = warning/at risk, Signal
  `#E8553D` = badly behind/failing, Horizon `#4A9BD9` = in progress, Chalk `#F7F8FA`/white = not
  started. This matches the brand guide's existing "Forest = completed, Horizon = in-progress,
  Chalk = incomplete" convention and just adds Sand/Signal for the two risk tiers the printed report
  needs that the live UI doesn't currently encode.
- **Colour is never the only signal.** Every RAG cell also carries a glyph (a filled circle vs. a
  triangle vs. a cross, or a checkmark/dash/exclamation) and the number itself. This is what makes
  the report survive both colour-blind readers and black-and-white printing/photocopying — a real
  risk for a document staff will print.
- **Numeric-first, bar-second inside table cells.** Put the percentage/fraction as text; add a
  simple horizontal fill bar behind or beside it with no axis. Skip sparklines in the summary grid —
  they need a time series and this report's grid cell only has one number per course. Reserve any
  trend/sparkline-like device for the per-student section, if at all.
- **Cap wide tables at roughly 10–12 data columns on A4 landscape** at a body size that stays legible
  when printed (8.5–9pt data, 9–10pt headers), with a frozen/repeated student-name column and a
  repeated header row on every page a table spans. Past that column count, split into multiple
  tables (e.g., one table per course) rather than shrinking type further.
- **One student per section, not strictly one page per student**, with a running header carrying the
  student's name and a bookmarked/outlined PDF so staff can navigate a 40-student cohort without
  scrolling through it linearly. Explicitly print "No activity recorded for this course" for
  students with nothing to show, rather than silently omitting them (silent omission reads as a data
  bug, not as an absence of activity).
- **Add a short methodology/definitions block** (what counts as "complete", how a quiz score is
  derived across multiple attempts, data-as-of timestamp and timezone) either on the title page or
  its own page — these reports will be printed, filed, and compared over time, so the definitions
  need to travel with the document, not live only in a web UI tooltip.

---

## Q1. Reference implementations: how established LMSs present cohort/class progress reports

**Moodle.** The **Grader report** is the closest analogue to the wide summary table: students as
rows, gradable items (assignments, quizzes) as columns, each cell a score. It exports to Excel/ODS/
plain text/XML, not natively to a styled PDF — Moodle's own docs recommend opening the Excel export
and manually setting landscape orientation and "fit all rows on one page" to get something printable
([Exporting and Printing the Moodle Gradebook](https://www.occc.edu/wp-content/legacy/c4lt/pdf/snap/ExportingAndPrintingTheMoodleGradebook.pdf),
[Grade export – MoodleDocs](https://docs.moodle.org/501/en/Grade_export)). Separately, Moodle's
**Course completion report** (`report_coursecompletion`) shows per-student completion state per
activity/criterion, and can export to CSV
([moodle-report_coursecompletion](https://github.com/catalyst/moodle-report_coursecompletion)).
Moodle's **Quiz statistics report** is the direct model for section 3 of this spec: per-question
facility index/discrimination plus, per question, a breakdown of which specific response/distractor
each student picked and how often — explicitly framed as revealing "if a question might be confusing
or if a misconception needs addressing"
([Quiz statistics report – MoodleDocs](https://docs.moodle.org/310/en/Quiz_statistics_report),
[Quiz analytics uncovered – Moodle](https://moodle.com/us/news/quiz-analytics-uncovered/)). Takeaway:
Moodle treats "wide grid" and "quiz confusion" as two genuinely different reports with different
shapes, not one document — this spec is right to keep them as separate sections.

**Canvas.** The Gradebook exports **only as CSV**; there is no native PDF/print report, and
Canvas's own support docs point instructors at pasting the CSV into Excel/Sheets and printing from
there ([How do I export a Gradebook Report? – TeamDynamix](https://teamdynamix.umich.edu/TDClient/76/Portal/KB/ArticleDet?ID=10717)).
**New Analytics** adds per-assignment average/high/low and a "weekly online activity" view per
student, but again lives only as an interactive web dashboard, not an exportable print artefact
([Understanding Analytics in Canvas](https://help.ohio.edu/TDClient/30/Portal/KB/ArticleDet?ID=1068),
[Canvas New Analytics guide, Liverpool](https://www.liverpool.ac.uk/media/livacuk/centre-for-innovation-in-education/digiguides/introduction-to-new-analytics/introduction-to-new-analytics.pdf)).
Takeaway: Canvas is a cautionary example of "reports that are just raw CSV dumps" — this spec's
explicit choice to produce a laid-out PDF rather than a CSV is the right call and is not something
Canvas offers at all.

**Open edX.** The instructor dashboard's "Data Download → Generate Grade Report" produces one row
per learner, one column per graded assignment, as CSV, generated as a background job the instructor
polls for
([Student Grades and Grading – Open edX docs](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/named-release-birch/running_course/course_grades.html)).
Same pattern as Canvas: wide grid, CSV-only, no print layout considerations at all. This spec is
explicitly building the thing these systems don't: a designed, printable version of that wide grid.

**TalentLMS / Docebo / Totara.** These commercial/enterprise LMSs are the closest existing analogue
to "one report per cohort, all courses." TalentLMS's "visual training matrix... shows status across
multiple courses on a single page" per user/group
([TalentLMS reports](https://help.talentlms.com/hc/en-us/articles/9652242394780-What-types-of-reports-are-available)).
Docebo has a dedicated **Groups–Courses report** showing course-progress detail for every course a
group is enrolled in, and a **Groups/Branches–Courses report** the other way around (all groups'
progress in one course)
([Managing standard reports – Docebo](https://help.docebo.com/hc/en-us/articles/360020084160-Managing-standard-reports),
[Available custom reports – Docebo](https://help.docebo.com/hc/en-us/articles/360020125499-Available-custom-reports-types)).
Takeaway: the "one cohort x all its courses" framing in this spec matches Docebo's Groups–Courses
report shape directly — validating the per-course-section structure over one flat table.

**Common pattern across all of them:** none of the mainstream LMSs ship a genuinely well laid-out
*printable* cohort report. Every one of them either (a) exports CSV and leaves formatting to the
user, or (b) keeps the "report" as an interactive web dashboard with no print path. That is this
spec's opportunity and also its risk — there is no reference PDF to copy pixel-for-pixel; the layout
choices below are synthesised from print/table-design and accessibility best practice generally,
not lifted from a competitor's PDF.

## Q2. Known complaints and failure modes

Recurring themes found in LMS-reporting complaint/critique writeups
([LMS Reporting Problems and How To Solve Them – WisdmLabs](https://wisdmlabs.com/blog/lms-reporting-problems-learndash/),
[LMS Dashboard best practices – apps365](https://www.apps365.com/blog/lms-dashboard/),
[Top LMS Reports for Administrators and Teachers – Schoolytics](https://www.schoolytics.com/blog/2023/03/top-lms-reports)):

- **Raw exports masquerading as reports.** CSV/Excel dumps with database column names, no
  formatting, no hierarchy — the reader has to build their own pivot table before they can answer
  "who needs help." Direct implication here: never ship a table that looks like a database dump;
  every table needs a purpose-built header row, units, and visual hierarchy.
- **Data overload with no signal.** "Overcomplicating the layout with more widgets does not mean
  more insight" — reports that show everything but answer nothing. Direct implication: this spec
  needs an explicit "what should I do about this" surface (Q8), not just raw numbers.
- **Ambiguous "complete."** Different systems count "complete" differently (item viewed vs. item
  marked done vs. passed a quiz vs. hit a time threshold), and reports rarely say which definition
  they used. FLS itself defines completion precisely (`docs/product/learner-tracking.md`: percentage
  = completed items / total items, recalculated on item completion) — this report must **state that
  definition on the page**, not assume the reader knows it.
- **Scores that hide attempt history.** A single "latest score" column with no attempt count
  invites the wrong read (mastery on attempt 1 looks identical to mastery on attempt 6 unless attempt
  count is shown alongside it) — the spec already asks for attempts count next to score, which is the
  right fix.
- **Tables that don't survive printing.** Headers that don't repeat when a table spans pages, column
  widths that overflow the page and get silently truncated by the renderer, colour-only status that
  vanishes in black-and-white — all directly addressed in Q3–Q4 below.

## Q3. Wide-table design for print

Concrete rules, in priority order:

1. **Repeat the header row on every page a table spans.** In `django-weasyprint`/WeasyPrint (the
   likely renderer given this is a Django app), this is `<thead>` on an HTML `<table>` — WeasyPrint
   repeats `<thead>` content across page breaks natively when the table is allowed to break, so no
   custom pagination code is needed; just don't accidentally trap the table inside a container with
   `overflow: hidden` or forced single-page sizing.
2. **Freeze/repeat the student-name column when a table is wide enough to need >1 page across.**
   For a table that only overflows *vertically* (many students, header repeats top of each page) this
   is automatic. For a table that would overflow *horizontally* (too many quiz columns), the fix is
   not a frozen column (that's a screen-scrolling concept with no print equivalent) but **splitting
   into multiple physical tables**, each carrying its own copy of the student-name column — e.g. one
   table per course rather than one table for all courses' quizzes.
3. **Prefer splitting a too-wide table over shrinking type or rotating headers.** Rotated
   (vertical) column headers are a legitimate space-saving technique and well documented
   ([Rotated Table Column Headers – CSS-Tricks](https://css-tricks.com/rotated-table-column-headers-now-with-fewer-magic-numbers/)),
   but they cost reading speed and don't work well in a document meant to be skimmed by a busy
   educator. Use rotation only for narrow numeric columns with short labels (e.g. "Q1", "Q2", "Q3"
   quiz short-codes with a legend), never for the row-defining student name.
4. **Abbreviate column labels and carry a legend.** For quiz columns, use a short code
   (`Q1`, `Q2`, or the quiz's own short slug) in the header and a legend line under the table title
   mapping code → full quiz title. This is standard technical-writing practice for tables with long
   headings ("shortened or abbreviated headings not easily recognized should be listed in a note
   before the table" — [USU Engineering Writing Center, Tables and Figures](https://engineering.usu.edu/students/ewc/writing-resources/tables-figures)).
5. **Split one wide table into several narrower ones along a natural seam** — by course is the
   natural seam here, since the report is already structured per-course. Do not try to fit "all
   courses x all quizzes" into one table; do "cohort x this course's items" as one table per course,
   repeated once per course section.
6. **Banding for row tracking.** Alternate row background (Chalk `#F7F8FA` / white) every other
   student row so a reader's eye doesn't lose the row when scanning right across many columns. This
   is standard and cheap; keep the contrast subtle (Chalk is already a near-white in the brand
   palette, good for this).
7. **Column ordering.** Left to right: student name → overall completion (%, bar, count) → last
   item completed + timestamp → then one column-group per quiz (score, attempts), ordered by the
   quiz's position in the course, not alphabetically — matches how an educator thinks about "where is
   this student in the course."
8. **Column budget for A4 landscape.** A4 landscape usable width after reasonable margins (15mm
   each side) is roughly 267mm (~10.5in). At a legible print body size (8.5–9pt data text, which is
   the practical floor for a document meant to be read rather than measured with a loupe), a numeric
   data column (score, attempts, %) comfortably needs ~18–22mm including padding; the student-name
   column needs ~35–45mm. That yields roughly **10–12 data columns** alongside one name column
   before the table should split rather than shrink further. This is a reasoned estimate from
   standard print-table sizing, not a number pulled from a single citable source — treat it as the
   assumption to validate against an actual rendered sample during implementation, not as a hard
   spec.

## Q4. Colour coding / RAG status, accessibility, and greyscale

- **Never encode status by hue alone.** The single most-cited fix for colour-blind accessibility
  ("red/green is the most common problem area for colour blindness... pairing colour with an icon or
  label is the standard fix") is to pair every coloured cell with a non-colour cue — in this report,
  the actual number (score, %) is always present as text, and each RAG tier should also get a
  distinct glyph (see below), which covers both colour-blind readers and greyscale printing/
  photocopying at once.
- **WCAG contrast.** Body/data text needs ≥4.5:1 contrast against its background (AA); large text
  (headings, ≥18pt or ≥14pt bold) needs ≥3:1. FLS's own brand guide already publishes tested pairings
  — reuse them rather than inventing new ones:
  - Midnight `#1A2332` on Chalk `#F7F8FA` — 15.7:1 — default body text.
  - Midnight `#1A2332` on Sand `#F6E05E` — 10.8:1 — the one safe way to put text *on* an amber fill
    (the brand guide is explicit that Sand must never be used *as* text colour, only as a background
    fill with dark text on top).
  - White on Signal `#E8553D` is not in the guide's tested table for AA body text — treat Signal as
    a background fill for short bold labels/badges only ("AT RISK", a glyph, or a 2–3 digit number),
    not as a fill behind a long text string.
- **Concrete RAG palette for this report** (reusing FLS's existing progress-indicator convention and
  extending it with the two "needs attention" tiers the live UI doesn't currently need):

  | Tier | Meaning | Fill | Text/number colour | Glyph |
  |------|---------|------|---------------------|-------|
  | Green | On track / complete / passed | Forest `#38A169` at ~15–20% tint, or solid for a small badge | Midnight `#1A2332` on tint; white on solid | filled circle or checkmark |
  | Amber | Behind pace / borderline score | Sand `#F6E05E` (fill only) | Midnight `#1A2332` (never Sand as text) | filled triangle or "!" |
  | Red | Failing / not started / significantly overdue | Signal `#E8553D` at ~15–20% tint for a table cell, solid only for small badges | Midnight `#1A2332` on tint; white on solid | filled square/diamond or "✕" |
  | Neutral | In progress, no verdict yet | Horizon `#4A9BD9` at low tint, or plain Chalk/white | Midnight `#1A2332` | open circle or dash |

  Using tints (not solid saturated fills) for full table cells keeps body text inside them readable
  and avoids the loud, poster-like look a solid-colour grid produces; reserve solid fills for small
  one-glyph/one-word badges (e.g. a status chip next to a name in the "students needing attention"
  list).
- **Greyscale/photocopy safety.** Forest, Sand and Signal convert to visibly different grey values
  when desaturated (green ≈ mid grey, yellow ≈ very light grey, red-orange ≈ another mid grey close
  to green's), which is precisely why the glyph is not optional — two of the three tiers can land at
  similar perceived greys on a low-quality photocopier. Test by printing a sample page on a
  black-and-white office printer before finalising; don't rely on colour theory alone.
- **Avoid the Okabe–Ito / Wong colour-blind-safe palettes wholesale** here — they're excellent for
  scientific multi-category charts, but this report already has an on-brand palette with tested
  contrast pairings; swapping to a generic scientific palette would break brand consistency for no
  real accessibility gain once the glyph+text rule above is applied.

## Q5. Micro-visualisation in table cells

- **Numeric-first, always.** The percentage or "12/18 items" fraction is text, full stop — it is
  the thing an educator will actually read, compare, and quote. Never ship a bar with no number.
- **Data bars, not sparklines, for the summary table.** A data bar (a simple horizontal fill
  proportional to completion %, no axis, no gridlines) reads well in print at small size and needs no
  legend beyond "0–100%" which is implicit. Sparklines are for *time series* (a trend across several
  points) — this report's summary cell has exactly one number per course (current completion), so
  there's no series to plot; a sparkline would either be decorative noise or require inventing a
  history the report doesn't otherwise show. Reserve any true trend view for a future "completion
  over time" enhancement, out of scope here.
- **Bar pitfalls to avoid:**
  - No axis or tick marks inside a table cell — the bar is a glanceable proportion, not a chart; add
    them and it fights the numeric label for attention.
  - Keep every bar in a column the same pixel width for 0–100%, so 50% always looks like half the
    same bar across every row — this is the same "aligned baseline" rule that makes sparkline columns
    comparable in paginated reports (misaligned bar widths across rows make cross-row comparison
    actively misleading).
  - Don't let the bar's fill colour double as the RAG status colour without the glyph rule above —
    a bar that is "60% full, coloured amber" needs the 60% as text and, ideally, the amber tier badge
    separately, not just a coloured bar guessed at by eye.
  - Keep bars out of the per-student detail section — that section is a chronological/tabular list of
    events (items completed, quiz attempts), not a proportion, so a bar has no place there.

## Q6. Per-student detail section layout for a 40-student cohort

- **One section per student, page-break-before, not strict one-page-per-student.** Force a page
  break at the start of each student's section (`page-break-before: always` in the print CSS) so a
  student's material always starts at the top of a page and is easy to locate, but let a student's
  content **flow across as many pages as their history needs** rather than truncating or shrinking to
  force it onto one page — a highly active student legitimately needs more space than an inactive
  one, and forcing uniform page counts either wastes paper for the quiet 40% of the cohort or
  truncates the busy ones.
- **Running header with the student's name (and cohort/course) on every page**, so a reader who
  flips straight to the middle of a printed stack always knows whose data they're looking at without
  paging backward.
- **Table of contents with page numbers**, placed right after the title page/summary strip, listing
  every student with the page their section starts on — this is the single highest-leverage
  navigation aid for a 40-student PDF meant to be searched, not read cover to cover.
- **PDF bookmarks/outline, in addition to the ToC.** Generate a PDF outline (WeasyPrint supports
  this via CSS `bookmark-level`/`bookmark-label` properties on headings) mirroring the ToC, so anyone
  reading on screen gets a clickable sidebar; the printed ToC and the on-screen outline should list
  the same names in the same order.
- **Explicit "nothing to report" for inactive students**, not silent omission. A one-line statement
  ("No activity recorded for [Course] as of [date]") under that student's heading, still inside their
  page-break-forced section — so the reader can distinguish "this student did nothing" from "this
  student's row fell out of the report by mistake," which matters both for the educator's trust in
  the document and because it's the students most worth flagging.
- **Order students consistently and predictably** — alphabetical by surname is the safest default
  for a document staff will file and re-generate over time (a "worst first" ranking would shuffle
  page numbers on every re-run and undermine the ToC/bookmark value across successive reports).

## Q7. Document-level conventions for a filed, comparable report

- **Title page contents:** cohort name, the list of courses covered (since scope is "all courses
  the cohort is registered for" and that list can change over time — record it explicitly per
  generation), "Generated at" timestamp with timezone (not just a date — the spec currently only asks
  for "date" but a timestamp+timezone is what makes two reports from the same day comparable/
  disambiguable), and the generating admin user's identity (useful for an internal audit trail on who
  pulled a given report, low cost to add).
- **Data-as-of caveat.** State plainly, near the timestamp, that all figures reflect data as of
  generation time and will not update — this is the single most important line for a document that
  will be printed and read later, once the underlying data has moved on.
- **A definitions/methodology page.** State, in the cohort's own terms:
  - What counts as "complete" for a course item and for a course overall — FLS's own definition
    (completed items / total items, recalculated on completion; see
    `docs/product/learner-tracking.md`) should be quoted directly so this document is
    self-consistent with the live product.
  - How a quiz's reported score is derived when there are multiple attempts (spec says "latest score"
    — say so explicitly here, since "latest" vs "best" vs "average" is exactly the kind of ambiguity
    Q2 flagged as a recurring LMS-report complaint).
  - What "attempts" counts (does an abandoned/unsubmitted attempt count? FLS records attempt start
    even if not submitted — this document needs to say which it's counting).
- **Page numbering.** "Page X of Y" in the footer of every page after the title page, plus a
  running footer identifying the cohort name (so a loose printed page can always be traced back to
  its cohort and report). Use one continuous page count across the whole document (not restarting
  per section) so the ToC page references stay simple.
- **Consistent per-generation identity.** Since these reports will be compared over time, keep the
  title-page + footer format byte-for-byte identical between runs (same fields, same order) so a
  reader flipping between two dated printouts isn't also parsing a changed layout.

## Q8. Signal over noise: what a busy educator needs on an early page

The single biggest risk in this spec as scoped is that the report is comprehensive but has no
"so what" page — an educator with 40 students across several courses should not have to read a wide
table plus 40 per-student sections to find out who needs a conversation this week. Concrete proposal:

- **Page 2 (right after the title page): a cohort-summary strip**, portrait, containing:
  - Headline numbers: cohort size (n), median completion % across the cohort's courses, count not
    started (0% and no activity), count "at risk" (behind an implicit or explicit pace, or failing a
    quiz on latest attempt), count complete.
  - A **"students needing attention" list** — name, the one-line reason (e.g. "0% complete, no login
    recorded" / "Quiz 'Safety Basics': failed, 3 attempts" / "No activity in 21 days"), and a page
    reference into their detail section. This is the single artefact busiest educators will actually
    read line-by-line; the rest of the document exists so that when they act on this list, the
    supporting detail is one flip away.
  - Keep this page short and scannable — a table of ≤15 rows max; if more than that many students
    qualify as "needing attention," say so as a headline number ("18 of 24 students need attention —
    see full list overleaf") rather than silently truncating, and let the full list run onto a second
    page if genuinely needed, but keep the *headline count* on page 2 regardless.
  - This is a genuinely opinionated addition beyond what the idea file currently specifies (the idea
    file's sections 0–3 don't include this) — flag it to the idea's author as a recommended new
    section 0.5, not an assumed requirement, since it does add scope (a "what counts as at risk"
    business rule needs defining) but it is the single highest-value thing this research turned up:
    every "known complaint" in Q2 traces back to reports that have all the data and no signal, and
    every comparator LMS in Q1 fails to solve this (they all stop at the wide grid).

## Proposed section-by-section outline

A concrete straw-man to accept or edit. Page counts are illustrative for a cohort of ~25 students
across 2–3 courses; actual counts scale with cohort size and content volume.

| # | Section | Orientation | Contents |
|---|---------|-------------|----------|
| 1 | Title page | Portrait | Cohort name, courses covered, generated-at timestamp + timezone, generating user, data-as-of caveat, FLS/org branding footer. |
| 2 | Cohort summary strip ("at a glance") | Portrait | Headline counts (n, median completion, not-started, at-risk, complete), "students needing attention" list with reasons and page refs. *(New section proposed in Q8 — confirm with idea author.)* |
| 3 | Table of contents | Portrait | Section list with page numbers; per-student list with page numbers. |
| 4 | Definitions & methodology | Portrait | What counts as "complete," how quiz score is derived (latest attempt), what counts as an "attempt," RAG tier thresholds, legend for any column abbreviations used later. |
| 5 | Per-course summary table(s) | Landscape | One sub-section per course the cohort is registered for. Each: student rows x (completion %, bar, last item + timestamp, then one column-group per quiz — score, attempts) with repeated header row, banded rows, RAG glyph+colour cells, legend for quiz short-codes. Split further if a course has more quizzes than the column budget in Q3 allows. |
| 6 | Per-student detail | Portrait (default); landscape only if a student's quiz-attempt table needs it | One page-break-forced section per student, alphabetical by surname, running header with name. Per student: per-item completion log with timestamps; per-quiz-attempt list (score, date); per-quiz wrong-question breakdown (question, times missed, which wrong options chosen and how often). "No activity recorded" line for inactive students. |
| 7 | Cohort-wide quiz confusions | Portrait (or landscape if option text is long) | One sub-section per quiz across all the cohort's courses: each question missed, with wrong-option distribution (option text + count/%), ordered by how often the question was missed (worst first) so the most actionable items surface first. |
| — | Every page after title page | — | Footer: cohort name, "Page X of Y", generated-at date (short form). |

## Risks and open questions

- **Column budget (Q3, "10–12 columns") is an estimate, not a validated number.** It should be
  checked against an actual rendered sample (real font, real WeasyPrint/renderer margins) before
  being treated as a hard limit in the spec.
- **The Q8 "cohort summary / at-risk" page is new scope** relative to the idea file's four sections.
  It requires defining "at risk" as a business rule (pace-based threshold on completion %, and/or
  failing-quiz threshold) which the idea file does not currently specify — flag this explicitly to
  the spec author rather than silently inventing a threshold.
- **PDF renderer choice affects several recommendations directly.** `<thead>` repetition, CSS
  `bookmark-level` for PDF outlines, and `page-break-before` all assume a CSS-driven renderer such as
  WeasyPrint; if a different rendering approach is chosen these need re-verifying against that
  tool's actual capabilities.
- **"Latest score" vs "best score" for the summary table** is specified in the idea file as
  "latest score" — this research did not find a strong best-practice argument either way; it's a
  product decision, just make sure it's stated on the methodology page (Q7) so it isn't ambiguous to
  the reader.
- **Landscape/portrait switching mid-document** is straightforward in principle for a CSS-paginated
  renderer (`@page` rules can vary by section) but should be explicitly tested — mixed orientation
  A4 PDFs sometimes render oddly in browser PDF viewers vs. print, and this document will likely be
  both viewed on screen and printed.
- **Greyscale readability claims here are reasoned, not lab-tested.** The recommendation to always
  pair colour with a glyph is standard accessibility practice, but the specific FLS palette's
  greyscale behaviour should be spot-checked by literally printing a sample page in black-and-white
  before sign-off.

## References

- [Exporting and Printing the Moodle Gradebook (OCCC)](https://www.occc.edu/wp-content/legacy/c4lt/pdf/snap/ExportingAndPrintingTheMoodleGradebook.pdf)
- [Grade export – MoodleDocs](https://docs.moodle.org/501/en/Grade_export)
- [Grader report – MoodleDocs](https://docs.moodle.org/502/en/Grader_report)
- [moodle-report_coursecompletion (GitHub)](https://github.com/catalyst/moodle-report_coursecompletion)
- [Quiz statistics report – MoodleDocs](https://docs.moodle.org/310/en/Quiz_statistics_report)
- [Quiz analytics uncovered – Moodle](https://moodle.com/us/news/quiz-analytics-uncovered/)
- [How do I export a Gradebook Report? – TeamDynamix/UMich](https://teamdynamix.umich.edu/TDClient/76/Portal/KB/ArticleDet?ID=10717)
- [Understanding Analytics in Canvas – Ohio University](https://help.ohio.edu/TDClient/30/Portal/KB/ArticleDet?ID=1068)
- [Introduction to New Analytics (Canvas) – University of Liverpool](https://www.liverpool.ac.uk/media/livacuk/centre-for-innovation-in-education/digiguides/introduction-to-new-analytics/introduction-to-new-analytics.pdf)
- [Student Grades and Grading – Open edX docs (Birch release)](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/named-release-birch/running_course/course_grades.html)
- [What types of reports are available in TalentLMS](https://help.talentlms.com/hc/en-us/articles/9652242394780-What-types-of-reports-are-available)
- [Managing standard reports – Docebo](https://help.docebo.com/hc/en-us/articles/360020084160-Managing-standard-reports)
- [Available custom reports types – Docebo](https://help.docebo.com/hc/en-us/articles/360020125499-Available-custom-reports-types)
- [LMS Reporting Problems and How To Solve Them – WisdmLabs](https://wisdmlabs.com/blog/lms-reporting-problems-learndash/)
- [LMS Dashboard: Transforming Digital Learning – apps365](https://www.apps365.com/blog/lms-dashboard/)
- [Top LMS Reports for Administrators and Teachers – Schoolytics](https://www.schoolytics.com/blog/2023/03/top-lms-reports)
- [Colorblind-Friendly Palettes for Web Design – AudioEye](https://www.audioeye.com/post/colorblind-friendly-palettes/)
- [Designing for Color Blindness: A Developer's Guide (2026) – CSSAWWWARDS](https://cssawwwards.com/blog/color-blindness-accessible-design-guide-2026)
- [Add sparklines and data bars in a paginated report – Microsoft Learn](https://learn.microsoft.com/en-us/sql/reporting-services/report-design/add-sparklines-and-data-bars-report-builder-and-ssrs?view=sql-server-ver16)
- [Sparklines and data bars in a paginated report – Microsoft Learn](https://learn.microsoft.com/en-us/sql/reporting-services/report-design/sparklines-and-data-bars-report-builder-and-ssrs?view=sql-server-ver16)
- [Rotated Table Column Headers... Now With Fewer Magic Numbers! – CSS-Tricks](https://css-tricks.com/rotated-table-column-headers-now-with-fewer-magic-numbers/)
- [Tables and Figures – USU Engineering Writing Center](https://engineering.usu.edu/students/ewc/writing-resources/tables-figures)
- [Designing Early-Alert Systems That Actually Help At-Risk Students](https://www.cfder.org/designing-early-alert-systems-that-actually-help-at-risk-students/)
- Repo docs consulted: `docs/product/educator-interface.md`, `docs/product/learner-tracking.md`,
  `.claude/skills/brand-guidelines/SKILL.md`, `spec_dd/2. in progress/basic_reports/idea.md`

status: ok
