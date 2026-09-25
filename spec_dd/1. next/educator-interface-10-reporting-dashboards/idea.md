# Reporting and dashboards

Spec 10 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

What an educator sees when they log in to check how things are going, and what they can download. An organisation dashboard as the interface's landing page. The cohort report on screen, built from the same gathered data as the PDF. A learner drill-down that replaces the deleted course-progress matrix. Generating and downloading the cohort report PDF from the interface instead of the Django admin. A roster export.

## Why

The cohort report (`freedom_ls/reports/`) has proved useful. It gathers, per cohort, a summary table per course, at-risk flags (no activity, failed latest quiz, inactive for a week), an attention list, per-learner detail with wrong answers, quiz confusion per question, and cohort statistics. Today all of that reaches an educator only as a PDF requested from the admin. There is even an HTML renderer of the same template tree that nothing uses. The source idea says reporting should be based on this mechanism, and the old progress matrix, which was the only on-screen view of progress, is gone as of spec 1.

## What is settled

**Levels.** Organisation, cohort, learner. Course-within-cohort is a section of the cohort level, not a page.

**Organisation dashboard.** A base view (spec 1) at the section root, per the dashboard mockup: stat tiles (active learners, cohorts, average progress, learners needing attention), a needs-attention list across cohorts with a quick view trigger and a link to the learner, and a cohort progress list. Nothing from the mockup that is out of scope ("awaiting review", "this week", messaging).

**Cohort report on screen.** A tab on the cohort detail page. It renders the gathered report data as panels using spec 4's components: the summary per course, the attention list, the quiz confusion. Same numbers as the PDF, because it is the same gather. The spec decides whether it renders live on request, from the last generated report's data, or from a short-lived cache, after measuring the gather at a realistic organisation size. `REPORTS_MAX_LEARNERS` applies either way and the page says so when hit.

**Learner drill-down.** On the learner detail page's courses tab (spec 7 leaves the slot): per course progress record, the completed items, the attempts per form with score and pass state, last activity. Built from the report's per-learner gatherer, not from a new query, unless the gatherer proves too heavy for one learner, in which case a narrower query with the same shape.

**Statuses.** The attention flags are the report's: no activity, failed latest quiz, inactive. The status badge vocabulary in spec 4 maps to them plus not started, in progress and complete. One definition, in `reports`, used by the dashboard, the lists and the badges.

**Downloads.** Generate the cohort report PDF from the cohort page and download it there, reusing `GeneratedReport`, the existing task and the existing `can_view_cohort` gate. The one-in-flight-per-cohort rule is surfaced as "a report is being generated". Roster export (members plus the educators with grants, as CSV) through spec 2's export hook. The admin route stays.

**Permissions.** From the spec 5 matrix. Instructors and TAs see dashboards and reports for their assigned cohorts only; the organisation dashboard aggregates only what they may see.

**Docs.** `docs/product/reports.md` gains the on-screen and in-interface paths; `docs/product/educator-interface.md` gains a reporting section.

## Discovery first

The spec starts with a short measurement, because the answers change the design:

- How long does `gather_cohort_report_data` take for a cohort of 30, 100, 300 learners on a seeded database, and what does it cost in queries?
- Which of the dashboard's numbers can come from cheap aggregates over `CourseProgress` and which need the gather?
- Is a cached gather (per cohort, invalidated on progress events) worth it, or is live fine at the sizes FLS actually runs?

Write the answers into the spec's decisions and into the roadmap's unknowns table.

## Open until the spec

- Live versus gathered per level, from the measurement above.
- Whether a chart is wanted anywhere. If so, the `dataviz` skill, and nothing decorative.
- Whether the learner drill-down needs a quick view version (spec 3) or the full page is enough.

## Out of scope

- Redesigning the PDF or its pipeline. Deadlines. Retakes. Anything learner-facing.
- New report types beyond the cohort report and the roster.

## Resources

- `docs/product/reports.md` and `spec_dd/3. done/2026-08-21_20:12_basic_reports/` (its `research_fls_data_availability.md` and `research_quiz_item_analysis.md` explain what the gather can and cannot know).
- `spec_dd/3. done/2026-08-28_07:52_report-rendered-with-org-name/` for branding.
- Mockups: `Educator Dashboard.dc.html`, `Educator Mobile Dashboard.dc.html` M01, the cohort overview in `Educator Cohorts and Admin.dc.html` screen 05, the learner detail in `Educator Learners.dc.html` screen 03.
- Skills: `dataviz` if charts, `fls-dev:multi-tenant`, `fls-dev:testing`, `fls-dev:qa-data-helper` for seeding realistic sizes.
