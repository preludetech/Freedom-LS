# Research: UX patterns for reporting dashboards (spec 10)

Question: what are the common UX patterns for this kind of work? Sections 1 to 2 describe the mockups (structure only). Sections 3 onward cover patterns, each with a recommendation for this spec. Web sources are listed at the end; they are mostly design blogs and vendor docs, so treat them as convergent practice, not standards.

Mockup directory: `spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/` (a copy sits in `spec_dd/3. done/2026-10-08_06:54_educator-interface-looks-good/design_source/`).

## 1. What the mockups show

### Dashboard, desktop (`Educator Dashboard.dc.html`, screen 01, 1440 wide)
- Sidebar (shared) plus a top bar: greeting ("Good morning, <name>"), a global search box, a notification bell.
- Row of 4 stat tiles in a 4-column grid. Each tile: small overline label, large number, one line of context.
  - Active learners: "284", context "Across 12 cohorts".
  - Average progress: "64%", with a thin progress bar under the number.
  - Pass rate, last 30 days: "87%", with a green trend line "Up 4 points".
  - Awaiting review: "11", context "Practical submissions".
- Below, a two-column grid (about 1.35 : 1).
  - Left, a card "Learners needing attention" with subtitle "No activity in 7 days or more, or a failed attempt" and a "View all" link. Rows: initials avatar, name, course or cohort line underneath, a mono-type detail ("14 days idle", "58% - attempt 2", "Awaiting review"), a status pill (Stalled, Retake due, Submitted), and a trailing text action (Message or Review).
  - Right top, a card "Cohort progress": one row per cohort, name left, percentage right, a thin progress bar below.
  - Right bottom, a card "This week": dated schedule entries.

### Dashboard, mobile (`Educator Mobile Dashboard.dc.html`, M01, 390 x 844)
- Top bar: hamburger, organisation name (truncated), search and bell icons. Bottom tab bar with 4 items: Dashboard, Cohorts, Learners, More.
- Greeting plus a sentence summary: "3 learners need attention today."
- Stat tiles collapse to a 2-column grid of 2 tiles (Active learners, Awaiting review). Average progress becomes a full-width single card with the percentage right-aligned over a thicker bar. Pass rate is dropped on mobile.
- "Needs attention" card with an "All" link. Rows are compact: avatar, name, one truncated detail line ("14 days idle - RPAS Basic"), a small pill. The trailing text action is dropped; the whole row is the tap target.
- "This week" card (two entries).
- No cohort progress list on mobile at M01.

### Cohort detail, screen 05 (`Educator Cohorts and Admin.dc.html`)
- Top bar breadcrumb (back arrow, "Cohorts", cohort name) with actions "Enrol learners" and "Edit cohort".
- Header band: status pill (Active), cohort code in mono, large cohort title; at right an inline stat strip (Learners 31, Avg progress 78%, Pass rate 91%, Closes date). Tab row under it: Overview, Learners (with count), Curriculum, Assessments, Schedule, Settings.
- Overview tab body is a 1.5 : 1 two-column layout.
  - Left: "Cohort details" key-value grid (3 columns of overline label over value: course, delivery, instructor, dates, capacity "31 of 35 enrolled", regulator, pass mark, attempts allowed). Then "Module completion across the cohort": rows of module name, a bar, and "29 / 31" counts. This is the closest mockup analogue to the report's per-course summary table.
  - Right: "Needs attention" card of three icon rows with a count sentence and a link each (3 learners idle 7+ days, 6 practical submissions awaiting review, 1 learner on a final attempt); an "Instructors" card (avatar, name, role); a "Compliance" checklist card.
- No report download, export or generation control appears anywhere on this screen.

### Learner detail, screen 03 (`Educator Learners.dc.html`)
- Top bar breadcrumb (back to Learners), actions "Edit" and a primary "Send message".
- Header: avatar, name, email, learner id, a status pill (Retake due). Tabs: Overview, Courses & progress, Assessments, Certificates, Activity.
- Overview tab: "Learner details" key-value grid (4 columns: cohort, enrolled, role, licence, location, instructor, target completion, last active). Then "Module progress" card: header with "4 of 8 complete - 52%"; one row per module with a state icon (check = passed, warning = failed, lock = locked), module name, a bar, and a right-aligned result ("Passed - 91%", "58% - attempt 2" in the error colour, "Locked").
- A 380px "Quick view" side panel (with expand and close icons) shows a "Progress snapshot": completion bar with cohort-average comparison text, two small stat boxes (Study time, Avg score), a warning callout ("One retake remaining"), and a "Recent activity" list. Footer buttons: Message, Reset attempt.

### Excluded by the idea or not backed by FLS data
The idea says "awaiting review", "this week" and messaging are out of scope. In the mockups these appear as:
- Dashboard: the "Awaiting review" tile; the "Submitted" / "Review" row in the attention list; the whole "This week" schedule card; the "Message" trailing action on attention rows; the global search box and bell (not reporting).
- Mobile M01: the "Awaiting review" tile, "This week" card, the "Review" pill.
- Cohort detail: the "6 practical submissions awaiting review" row; Schedule and Assessments tabs; Instructors and Compliance cards; "Closes" date.
- Learner detail: "Send message", "Message" and "Reset attempt" buttons; "Retake remaining" and "Retake due" language (retakes are out of scope); Study time (the research on data availability should be checked before offering this); Certificates and Activity tabs; the locked-module state.
- Also not in the idea's tile list: "Pass rate, last 30 days" with a trend delta. The idea's tiles are active learners, cohorts, average progress and learners needing attention. A trend needs history FLS may not store; skip unless the spec finds data for it.
- Mockup "Needs attention" flag vocabulary (Stalled, Retake due, Submitted) differs from the report's flags (no activity, failed latest quiz, inactive for a week). The idea settles on the report's flags.

## 2. Mapping mockup structure to what this spec builds
| Mockup element | Spec 10 use |
|---|---|
| 4 stat tiles | Active learners (across N cohorts), cohorts, average progress (with bar), learners needing attention |
| Needs-attention card | Cross-cohort list; row = learner, cohort, reason detail, status badge, quick view trigger, link to learner |
| Cohort progress card | One row per cohort, name, percent, bar, link to cohort |
| Module completion rows (screen 05) | Per-course summary on the cohort report tab |
| Module progress rows (screen 03) | Per-course progress and per-form attempts on the learner courses tab |
| Quick view panel | Reuse the quick view trigger on attention rows (spec 3); an open question whether the learner drill-down needs one |

## 3. Patterns

### Stat tiles / KPI rows
- Label (overline), one big number, one line of context. The context line is where a tile earns its keep ("across 12 cohorts", "of 284 learners"). Keep 3 to 4 tiles; more dilutes the point.
- State the definition and the window on or near the tile when a number is derived. "Average progress" should say of what (mean of course progress over active registrations). A delta without a stated baseline is ambiguous; since FLS likely has no history, show no deltas.
- Make tiles links where the number has a destination: "learners needing attention" scrolls or links to the list; "cohorts" to the cohort list.
- Define loading, empty (zero) and error states for each tile. Zero is a valid, meaningful value (0 needing attention is good news; say so, e.g. "None").
- Mobile: 2-up grid, 4 tiles stack 2 x 2; or promote one primary metric. M01 keeps just two and gives progress a full-width card.
- Recommendation: tile = the spec 4 stat component; numbers from cheap aggregates over `CourseProgress` where the discovery step says so, the needs-attention tile from the same one status definition in `reports` as the list, so tile count and list length never disagree.

### Needs-attention lists
- Reasons visible per row, not just a name. The user's first question is "why is this person here?". Show the flag as a badge plus a short detail ("14 days since last activity", "failed latest quiz: 42%").
- Sort by severity or recency then name; a learner with several flags appears once with multiple badges, not once per flag.
- Cap the dashboard list (say top 5 to 10) with a "View all" link; the cap and the total must be shown ("Showing 5 of 23").
- Row is a link to the learner; a secondary trigger opens the quick view. Do not nest links in links; keep one primary target.
- Cross-cohort lists need the cohort name on each row.
- Empty state: a positive statement ("Nobody needs attention right now"), not a blank card.
- Permissions: the list aggregates only cohorts the viewer may see.

### Cohort progress lists
- Row: name, percent right-aligned, thin bar, optionally learner count and an attention count. Sort by an obvious key (least progress first helps an educator find laggards; or alphabetical for predictability). State the sort.
- Progress bars here are not decorative: they carry the one number the row exists for. Add the numeric value next to it (do not rely on bar length alone; accessibility: give the bar `role="progressbar"` with value attributes or an accessible text).
- Long lists: paginate or cap on the dashboard and link to the cohorts list (spec 6) for the full table.

### On-screen report panels
- A report tab should look like the PDF's sections in order, each as a titled panel: summary per course, attention list, quiz confusion, cohort statistics. Same headings as the PDF so the two are recognisable as the same report.
- Show provenance: "Report as of <time>" and, if gathered live, say it is current; if from the last generated report, say when it was generated and offer refresh. This answers the open "live vs gathered" question from the user's side: whichever the spec picks, label it.
- Tables over cards for comparing many learners; use fixed column order and right-aligned numerals.
- Quiz confusion (per-question wrong-answer distribution) is a ranked list: put the most-missed questions first and show the count or percent next to a short bar. Truncate long question text with the full text on expand.
- Collapse long sections (per-learner detail with wrong answers) behind expanders so the tab opens fast and scannable.
- Print/PDF parity: the same numbers, so do not re-derive anything in the template.

### Learner drill-downs
- Structure from screen 03: header with identity and status badge, key-value details, then a per-course card.
- Per course: progress bar and fraction ("4 of 8 items"), course status badge, last activity as a relative date with the absolute date in a tooltip/title.
- Completed items: collapsed by default (list can be long), expandable.
- Attempts per form: a compact table, one row per attempt: attempt number, date, score, pass/fail badge. Mark the latest attempt; highlight a failed latest attempt since that is the report's flag. Show the pass mark next to the score ("58% of 75% needed") to make pass/fail self-explanatory. Do not show colour alone for pass/fail; include the word.
- Wrong answers: link or expand per attempt, only if the gatherer provides them.
- Not-started courses: show a row with "Not started" rather than omitting it.
- Empty state: "Not registered on any courses yet."

### Status badges
- A small fixed vocabulary, each with an icon or text, not colour alone (WCAG 1.4.1). Suggested mapping to the idea: no activity, failed latest quiz, inactive (attention, warning/error tones); not started (neutral), in progress (info), complete (success).
- One component, one definition in `reports`; the same label text on dashboard, lists, report tab and PDF.
- Precedence rule needed when several apply (e.g. complete beats inactive; failed quiz beats in progress). Write the precedence down in the spec. Show multiple attention badges only when they genuinely differ in required action.
- Keep labels short for mobile (one or two words, as M01 shortens "Retake due" to "Retake").

### Async "report is being generated" and download links
- Pattern across products (sources below): the request returns at once, the UI shows an in-progress state, and the download appears when ready; fast jobs may just download.
- For this spec (single PDF task, `GeneratedReport`, one in flight per cohort):
  - Button states: idle "Generate report"; in-flight disabled button with a spinner and text "Generating report..." plus "A report is being generated" so a second user who opens the page sees the same state; ready shows "Download report (generated <date/time>)" and still allows "Generate a new report".
  - HTMX polling: swap a status fragment with `hx-trigger="every 2s"` while pending; the returned fragment omits the trigger once finished, which stops the polling (the usual HTMX idiom). Poll with a bounded interval; do not poll forever, and give a way out.
  - Failure state: say it failed and offer retry; a stuck "generating" row needs a timeout rule, otherwise the one-in-flight rule blocks the cohort for good. Worth checking how the existing task marks failure.
  - Show who generated it and when, since reports are shared across educators of the cohort.
  - A short history list (last few `GeneratedReport` rows) with download links is common; keep it to the latest unless the spec asks for more.
  - Do not rely on email as the only completion signal; the user may leave the page. The page must show the right state on return.
  - Download link: a normal link behind the `can_view_cohort` gate (never a public media URL), `Content-Disposition: attachment`, filename with cohort and date.

### Export buttons
- Place on the surface it exports: the cohort's roster export sits on the cohort page's learners area or the actions menu, not on the dashboard. Label by outcome and format: "Export roster (CSV)".
- Say what is included, one short line (learners plus organisation members holding a role on the cohort), since that is not obvious from the label.
- Small exports download directly; no spinner state needed unless the spec's hook makes it async.
- Keep the PDF and the CSV visually grouped as "Downloads" so an educator finds both together.
- Respect permissions; hide or disable (with a reason) for those who cannot view the cohort.

### Cap-reached notices ("report limited to N learners")
- Show a persistent, non-modal notice at the top of the affected panel(s), in warning tone, where the truncated numbers appear, not in a footer. Text: "This report covers the first 200 of 340 learners (limit: 200). Totals and averages reflect only those learners." State what is and is not affected (counts, averages, attention lists).
- Say what the user can do (narrow the cohort, ask an admin to raise the limit) only if that is true; otherwise say nothing misleading.
- The same notice text on the PDF and the screen; one source of the string.
- Tiles that use the gather should carry the cap note too, or tiles should use aggregates that are not capped, in which case say the tile counts everyone while the report panel counts a subset (a visible mismatch otherwise confuses).
- Also ensure the notice is announced to assistive tech (`role="status"` or a visible region in reading order).

### Empty states
Three distinct cases, with distinct copy:
1. Nothing exists yet (no cohorts, no learners): explain what will appear and offer the one action that populates it (create a cohort, if the viewer has the right).
2. Exists but no data yet (learners enrolled, nobody has started; no attempts): say so plainly ("No activity yet"). Tiles show 0 or a dash, not NaN, and averages with no denominator show a dash.
3. Filtered or permission-restricted to nothing: for a cohort admin with no assigned cohorts, "You have no cohorts assigned" with who to ask.
Positive empties ("Nobody needs attention") use a calmer tone than error empties. Never leave a blank panel that looks broken. Avoid division by zero in average progress.

### Mobile layouts for dashboards
- Single column. Order by priority: summary sentence, tiles (2-up), needs attention, cohort progress.
- Drop low-value tiles rather than shrinking them (M01 does this).
- Rows, not tables: attention and cohort rows use a two-line row (name, then truncated detail) with badge at right; whole row tappable; 44px minimum tap target.
- Wide report tables on a phone: prefer one of (a) card-per-row with 2 to 3 key fields and an expander, (b) hide secondary columns, (c) horizontal scroll with the first column sticky as a last resort. Horizontal scroll alone is a weak answer for people who need to compare.
- Tabs on the cohort page become a horizontally scrollable tab strip or a select.
- Download and generate buttons full width on mobile; status text below, not hidden in a tooltip.
- Keep polling cheap on mobile.

### When a chart helps vs when it is decorative
Helps:
- Shows a distribution or comparison the reader cannot get from a number in a glance, and lets them make a decision: e.g. a histogram of learner progress in a cohort (are most stuck at the start?), a ranked bar of questions by wrong-answer rate (quiz confusion), progress over time per learner to see a stall.
- Comparing many cohorts at once on one scale: ranked horizontal bars (which the "cohort progress" list already is).
Decorative:
- A donut or gauge repeating a single percentage already in text; sparkline with no axis or baseline; trend arrows without a baseline; charts of two or three values; 3D, gradients.
Guidance for the spec:
- The row-with-bar pattern already serves the cohort progress list and per-course summary. Treat these as bars-as-data, not charts, and no chart library needed.
- Time-series charts need history FLS may not hold (`CourseProgress` stores state, not snapshots); check before promising one.
- A chart must have a text or table equivalent, labelled axes starting at zero for bars, colour not the only encoding. If a chart is added, use the `dataviz` skill as the idea states.
- Default recommendation: no chart in this spec unless the measurement shows a distribution worth reading; the idea's own "nothing decorative" line fits this.

## 4. Suggested decisions for the spec (from the UX side)
1. Tiles: active learners, cohorts, average progress (bar), learners needing attention (link to list). No deltas, no pass-rate trend.
2. Attention list: capped, shows reason per row, one row per learner with all flags as badges, positive empty state, cohort name on each row.
3. Report tab: panels in PDF order, provenance line ("as of"), cap notice at the top of the tab, same wording as PDF.
4. Download area: Generate, in-progress (polling fragment that stops itself), ready (download link with timestamp), failed (retry), plus roster CSV beside it.
5. Learner courses tab: one card per course, collapsed completed items, attempts table with score, pass mark and badge.
6. Mobile: two-line rows, 2-up tiles, card-style tables, full-width action buttons.
7. Charts: none by default.
8. Remove from the mockups on implementation: Awaiting review, This week, Message, Review, Retake language, Pass-rate delta, Compliance, Instructors cards.

## 5. Open questions this research surfaces
- Failure and timeout handling for a stuck in-flight `GeneratedReport` (affects the "being generated" state).
- Whether dashboard tiles should be capped like the report or count everyone (visible mismatch otherwise).
- Status precedence when multiple flags and states apply.
- Whether the learner drill-down needs a quick view (mockup 03 has one with a snapshot; the idea leaves it open).

## References
- KPI cards, empty states, async report patterns (summary of vendor and design blog guidance): https://www.saasui.design/blog/saas-metric-kpi-card-ux-patterns
- SaaS data export and download UX: https://www.saasui.design/blog/saas-data-export-download-ux-patterns
- Dashboard UI design, KPIs to layouts: https://setproduct.com/blog/dashboard-ui-design
- Empty dashboard best practices (Uxcel): https://app.uxcel.com/lessons/empty-states-best-practices-330/empty-dashboard-6854
- SAP design system, no-item empty state: https://www.sap.com/design-system/hcm/mobile-patterns/empty-state/no-item-empty-state/usage
- Asynchronous reports (JoinedUp): https://support.joinedup.com/en/articles/5767046-asynchronous-reports
- Brightidea asynchronous reporting: https://support.brightidea.com/hc/en-us/articles/205840067-Brightidea-s-Asynchronous-Reporting
- GitHub changelog, asynchronous generation of the Copilot activity report CSV: https://github.blog/changelog/2025-08-07-asynchronous-generation-of-the-copilot-activity-report-csv
- Designing mobile tables (UXmatters): https://www.uxmatters.com/mt/archives/2020/07/designing-mobile-tables.php
- Responsive table options (Uxcel glossary): https://app.uxcel.com/glossary/tables
- Mobile dashboard UI (Toptal): https://www.toptal.com/designers/dashboard-design/mobile-dashboard-ui
- How to design dashboards for mobile users (Querio): https://querio.ai/articles/how-to-design-dashboards-for-mobile-users

Not web-sourced (my own synthesis, flagged as such): the HTMX polling idiom, WCAG 1.4.1 colour-not-alone rule, chart-vs-decorative guidance, and the recommendations in section 4.

status: ok
