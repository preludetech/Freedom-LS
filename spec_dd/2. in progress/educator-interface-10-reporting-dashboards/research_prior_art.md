# Prior art: educator reporting dashboards

Question: what has already been tried for this, here or elsewhere, and what happened?
Paths below are under `spec_dd/3. done/` unless stated.

## Part 1. Here (FLS)

### 1.1 The old on-screen view: the course-progress matrix (built, then deleted)

- `2026-02-27_08:53_educator-interface-cohort-course-progress/` built `CohortCourseProgressPanel`. It was a learners-by-course-items grid, one course at a time, paginated on two axes (20 learners and 15 items per page), with quiz cells showing score and pass state, plus deadline cells. It was the only on-screen view of progress.
- `2026-05-05_10:10_educator-experience-bug-fix/` (`research_pagination.md`, `research_recursive_table.md`) is the follow-up. The matrix needed its own pagination and could never be an ordinary table.
- `2026-08-28_14:19_better-course-progress-tracking/` QA found that the matrix keeps listing removed learners (G3). It also found stale `progress_percentage` values beside completed cells (B1). Report and matrix were reconciled by hand in QA. Both are symptoms of the matrix trusting cached `CourseProgress.progress_percentage`.
- Why it was deleted: `2026-09-26_16:41_educator-interface-1-panel-framework-core/1. spec.md` (lines 33, 156, 220, 248) deletes `CohortCourseProgressPanel`, `FormProgressData`, its helpers, its template and tests, and four `qa_helpers` commands. The recorded reason is structural. The matrix is hand-written `Panel` content, not a queryset, so it can't ride the new table layer. Also spec 2's research (`research_tables2_viability.md`, `research_current_table_layer.md`) notes the two-axis paginator "can never be a tables2 table". Spec 1 replaced it with a dashboard placeholder card ("Reporting ... arrives in a later release") and a one-line note in `docs/product/educator-interface.md`. The deletion was a rebuild decision, not a verdict that the matrix was useless. Spec 10 is where reporting returns.
- Spec 12 still lists leftovers to sweep: unused cell templates, and any matrix `qa_helpers` commands spec 1 left behind.
- Lesson: an on-screen view that reads cached or derived percentages drifts from the truth. The report's gather deliberately recomputes completion from progress rows (basic_reports spec section 3, "Completion percentage recomputed, not read from cache").

### 1.2 The cohort report (built, shipped, "proved useful")

`2026-08-21_20:12_basic_reports/` (spec, plan, six research files, QA) and `docs/product/reports.md`.

Decisions that bind spec 10:
- Layering. The spec says the gather and render layers "must not know what triggered them". The gather returns a typed dataclass (`CohortReportData`, not a template context) so other consumers can reuse it. The email adapter was the stated future consumer. This is the seam spec 10 plans to use for the on-screen tab.
- Render split. `build_report_html(data) -> str` is separate from `render_report_pdf(data) -> bytes`. The stated reason was testability: content assertions run without WeasyPrint. That is why an HTML renderer exists that no product path uses (today only `render.py` and tests/builders reference `build_report_html`). It was never meant as a screen view. It renders the print template tree, with the print stylesheet and hand-extracted theme tokens, so it is not a drop-in screen UI. Spec 10 should treat on-screen panels as new templates over the same dataclass, not as the print HTML dropped into a page.
- Gather discipline. Batched queries only, no query in a per-learner or per-question loop. Every query filters on explicit `site_id`, because a background task has no request and `SiteAwareManager` doesn't filter without one. The spec requires a query-count-bound test as cohorts grow. A live view in a request would have a request, but the same explicit-filter rule makes the gather safe either way.
- Definitions that must not drift on screen: attempt = completed `FormProgress`; quiz score = latest attempt; confusion analysis = first attempts only; below 10 respondents show counts, not percentages (anonymity floor, deliberately not a setting); Activities and free-text questions are excluded; individually registered courses are not covered; cohort membership has no history, so a report is a snapshot.
- At-risk rules. Three fixed rules in `at_risk.py` (no activity, failed latest quiz, inactive 7 days), one evaluation shared by the at-a-glance list and per-learner sections. A pluggable setting-based registry was built and then removed because it cost a cached loader, test `cache_clear()` discipline and a system check. Rule selection and thresholds were deferred to a later `report-upgrades` that would move them into the database. Consequence: the dashboard cannot let a deployment retune "at risk" yet. The idea's "one definition in `reports`" matches this.
- Deadlines were deliberately excluded from the report ("live-tracking concept"). Spec 10 inherits that; the roadmap also puts deadlines out of scope for all twelve specs.
- Cap disclosure. The attention list is capped at 12 and says so ("18 learners flagged, 12 shown"); quiz confusions are capped per quiz and say so. Never silent truncation. Spec 10's panels should keep the same disclosure rule.
- Performance. The research notes WeasyPrint is slow and memory-hungry, which motivated a row limit rather than an OOM mid-render. There was no measured gather time at 30/100/300 learners in the basic_reports record. The only large-cohort QA was a 25-learner fixture (`large-cohort-medium-course.pdf`, 33 pages). The "measure first" discovery step in spec 10 therefore has no prior numbers to lean on.

### 1.3 `REPORTS_MAX_LEARNERS`

- Origin: `REPORTS_MAX_STUDENTS`, default 500 (basic_reports `2. plan.md` ~lines 241-262, 620-641, 1175, 1399; `upgrade_notes.md` line 248). Renamed `REPORTS_MAX_LEARNERS` in `2026-08-22_15:42_learner-terminology-rename/` (upgrade notes lines 49 and 641; pr_body line 142).
- Reasoning: it is a declared setting, not a module constant, because exceeding it makes generation fail, so a deployment with legitimately bigger cohorts needs a lever. Other layout caps (attention list, per-quiz confusion list) stay module constants. `REPORTS_MAX_QUIZ_COLUMNS` (10) is a layout budget.
- Behaviour today: `freedom_ls/reports/indexes.py:203-207` raises `ReportTooLarge` (defined `report_data.py:22`) when the cohort has more learners than the limit, with a message naming the setting. Task tests cover it (`test_tasks.py`, `test_indexes.py`, with the setting overridden to 1 or 2).
- Rationale was render time and memory of PDF generation, not gather cost. Nobody has argued the cap is right for a request-time on-screen gather. `2026-10-03_05:29_educator-interface-2-panel-framework-tables/research_csv_export.md` (line ~69) notes the cap exists "for the same reason" (bounded memory) and that the table export hook has no equivalent cap, with organisation size stated as "hundreds to tens of thousands of rows". That is relevant to the roster export (streaming recommended there: Django's `StreamingHttpResponse` Echo pattern).
- Open consequence for spec 10: the idea says the cap "applies either way and the page says so when hit". The record doesn't say whether 500 is also right for a screen. That belongs in the measurement.

### 1.4 One report in flight per cohort

- Enforced in the database: `UniqueConstraint(fields=["cohort"], condition=Q(status__in=["pending","running"]), name="one_inflight_report_per_cohort")`, a Postgres partial unique index (basic_reports spec section 5). Reason: an `.exists()`-then-`.create()` guard is a check-then-act race (double click, two staff at once). The view keeps a friendly pre-check and catches `IntegrityError` to show "already in progress" instead of a 500. `ready` and `failed` reports do not block a new run.
- Stuck-row protection: a crashed render must not leave `running` forever, since that would block the cohort permanently. The task records `error_message` and sets `failed`, and a scheduled sweep (see `docs/product/deployment.md`) closes interrupted rows as failed.
- Implication for spec 10: surface the existing constraint ("a report is being generated"). Don't build a second guard.

### 1.5 Delivery and security decisions to reuse

- Always a background task (never inline), enqueued in `transaction.on_commit`, with primitive ids passed. A synchronous POST past the 60s gunicorn timeout would 502 (`research_generation_and_delivery.md`). `ImmediateBackend` makes dev and test synchronous for free.
- Download through a permission-checked view: `has_perm("freedom_ls_student_management.view_cohort", report.cohort)` (guardian, object-level), `FileResponse` as attachment, `Cache-Control: private, no-store, must-revalidate`, slugified filename, never `report.file.url`. Deleting a cohort cascades to reports and the PDFs must be removed from storage (two deletion paths covered).
- The trigger lives in `reports`, not on `CohortAdmin`, to avoid a `student_management` to `reports` import cycle. `reports` depends on others and nothing depends on `reports`. Spec 10's educator-interface views would import `reports`, so check the dependency direction (`fls-dev` structure review applies, `docs/app_structure.md`).
- Known gaps the report documented and spec 10 inherits: `last_accessed_item` is "last viewed" and mustn't be shown as last completed; `QuestionOption.correct` can be edited after answers; multi-select scoring changed (stored scores were not rescored, so score and wrong-answer detail can disagree for old attempts).

### 1.6 Branding

`2026-08-28_07:52_report-rendered-with-org-name/`: the report leads with the organisation's name and logo, with a small "Powered by" site mark that cannot be switched off (none shown for the site's default organisation). PDF metadata names the organisation as author. A filename built from organisation and cohort is part of the download. On-screen panels need no logo treatment, but the in-interface download keeps this naming.

### 1.7 Roadmap and docs signals

- `spec_dd/1. next/roadmap.md`, "Educator interface rebuild": spec 10 depends on 2 (tables, export hook) and 4 (components); it needs neither 5 nor 6/7 done, and it "links to learner and cohort pages but does not change them". The unknowns table row for 10 reads: "Which dashboard levels read live queries and which read gathered report data, and what does that cost at a realistic organisation size?", affects spec 12. No decision has been recorded yet.
- Roadmap decision 3 puts an audit log in scope as spec 11. Spec 11 will need to know whether report generation is an auditable action. The roadmap's out-of-scope list freezes the PDF pipeline ("reused, not redesigned"), deadlines and retakes.
- Open question from spec 7 that affects 10: a cohort move mints a fresh `CourseProgress` record, so the drill-down could show a learner resuming at 0% unless 7 re-points the old record.
- `docs/product/educator-interface.md` line 42: the Overview's needs-attention card is a placeholder that always reads "Nothing needs attention yet." That is the slot to fill. `docs/product/reports.md` currently describes only the admin route, and its Limits list says "No scheduled or emailed reports", "No retention or expiry", "No shareable link". Those stay true after spec 10.
- Previously built, never-built or deferred ideas relevant to this spec: automated email of the report (out of scope in basic_reports), CSV export (a `# TODO ... Export as csv` in the old educator views was left in place, resolved by spec 2's export hook and spec 10's roster), report retention, and the `report-upgrades` spec for database-held at-risk rules.

### 1.8 What the record does not contain

No measured gather timings, no caching experiment, no chart or other dataviz in an FLS report, no on-screen use of the gathered data, and no usage data for the report. All of these are things spec 10's discovery step must produce.

## Part 2. Elsewhere

Short, web-sourced. The `WebSearch` snippets below were not read in full, so treat claims as indicative. Some points are commentary rather than peer-reviewed.

### 2.1 Purdue Course Signals (traffic-light at-risk dashboard)

- What was tried: a traffic-light signal (red, yellow, green) from grades and effort data, shown to students and instructors, with instructor-triggered messages.
- What was claimed: Purdue reported that taking two Signals-enabled courses raised six-year graduation rates (about 21%).
- What happened: Mike Caulfield and Al Essa (and then Michael Feldstein) argued the effect was selection bias or reverse causality, because students who stay longer take more courses. One course showed a slight negative effect, two a strong benefit, and the one-course effect faded as the programme expanded. Purdue did not publicly revisit the findings. Sources are blog commentary and Inside Higher Ed reporting, not peer-reviewed rebuttals.
- Lessons for FLS: do not claim the dashboard causes outcomes; the docs and UI should state what a flag means, as the report's definitions page does. Keep the evidence behind a flag visible (reasons, not just a colour), which the report already does. Colour is never the only signal. Avoid inferring causation from usage.
- URLs: https://downes.ca/post/61378 ; https://eliterate.us/purdue-course-signals-data-issue-explainer/ ; https://eliterate.us/course-signals-effectiveness-data-appears-meaningless-care/ ; https://www.insidehighered.com/index%2Ephp/node/62116

### 2.2 Educator adoption of learning-analytics dashboards (Open University UK, Moodle plugins)

- Study of 95 teachers (Open University): willingness to use a dashboard follows perceived ease of use and usefulness; most wanted training and follow-up support. Lesson: put the few numbers educators act on (who needs attention, why) where they already land, rather than a wall of charts.
  https://www.irrodl.org/index.php/irrodl/article/view/3493 ; https://oro.open.ac.uk/56001
- Macquarie University Moodle Engagement Analytics Plugin pilot (36 units): the authors note Moodle lacks integrated analytics that give actionable information and let teachers efficiently contact the students. Lesson: a list of at-risk learners without a path to act (open the learner, contact them) is the failure mode; spec 10's list links to the learner and (later) the quick view and messaging.
  https://publications.ascilite.org/index.php/APUB/article/view/745
- Liu, Rogers and Pardo (ASCILITE 2015) argue that predictive, retention-focused approaches have been received slowly and that outsourcing at-risk outreach to a system can distance educators from students. Lesson: keep the educator the actor; use transparent rule-based flags (as the report does) rather than opaque prediction.
  https://publications.ascilite.org/index.php/APUB/article/download/1022/914/5605
- Moodle's own commentary, "Learning analytics - are we at risk of missing the point?": https://research.moodle.org/73
- Gap: the searches returned nothing on Moodle's Inspire prediction model outcomes. I did not verify measured results for it, so I make no claim.

### 2.3 Synthesis for spec 10

1. Rule-based, explainable flags with reasons win over opaque scores; FLS already has this.
2. Actionability beats coverage: every attention row needs a next step.
3. Say what the numbers are and are not (snapshot, latest attempt, exclusions) next to the numbers.
4. Don't over-claim from small cohorts: the report's small-n counts rule applies on screen too.
5. Cached or derived progress numbers drift (FLS's own matrix showed this in QA), so the dashboard's cheap aggregates over `CourseProgress` need an explicit staleness position, and the recompute-versus-cache choice from the report spec should be revisited on purpose, not by accident.

## Sources

- https://downes.ca/post/61378
- https://eliterate.us/purdue-course-signals-data-issue-explainer/
- https://eliterate.us/course-signals-effectiveness-data-appears-meaningless-care/
- https://www.insidehighered.com/index%2Ephp/node/62116
- https://www.irrodl.org/index.php/irrodl/article/view/3493
- https://oro.open.ac.uk/56001
- https://publications.ascilite.org/index.php/APUB/article/view/745
- https://publications.ascilite.org/index.php/APUB/article/download/1022/914/5605
- https://research.moodle.org/73

status: ok
