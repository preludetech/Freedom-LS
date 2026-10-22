# Research: best practices for reporting dashboards (spec 10)

Web-sourced findings carry URLs. Items marked "(general practice, not web-verified this session)" come from established Django/engineering knowledge and should be checked in the spec if they become load-bearing.

## 1. Educator and learning-analytics dashboards

Findings
- Most learning-analytics dashboards stay at descriptive analytics. Predictive ones that only flag at-risk students, without saying why, limit the advice an educator can act on. Source: https://mro.massey.ac.nz/items/c5e65326-b189-4cdb-8603-38e1af051d2a and https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8853217/
- Practitioner commentary (opinion, not peer reviewed) warns about vanity metrics such as login counts and bare completion rates, and about alerts with no owner. Source: https://8allocate.com/?p=104067
- A systematic review of teacher-facing dashboards (Kaliisa et al.) includes a design checklist. I did not open it. Source: https://Educationaltechnologyjournal.springeropen.com/counter/pdf/10.1186/s41239-023-00394-6.pdf
- Evidence that predicted risk leads to effective intervention is thin. Simple, explainable, rule-based flags with a visible reason are the defensible choice (general practice).

What it means for this idea
- The report's flags (no activity, failed latest quiz, inactive for a week) are rule-based and explainable. Keep them that way. Show the reason on every needs-attention row ("Failed latest quiz: X", "No activity in 9 days"), not just a red badge. Do not add scores or predictions.
- Every needs-attention row should lead to an action: the quick view and the learner link already do this. Consider ordering by severity, then by days inactive, so the top of the list is the thing to act on.
- "Average progress" and "active learners" are context tiles. The actionable tile is "learners needing attention". Define "active learners" explicitly (for example, registered in a cohort, or activity in the last N days) and put that definition in the `reports` module next to the flags, since the idea already wants one definition for statuses.
- Empty state matters: "0 need attention" is a result, not an error. Say so in text.
- Keep stat-tile counts equal to the list they summarise. Click-through from a tile to the matching list should show the same number, or trust is lost.
- Charts: none are needed for the first cut. Progress bars with a text percentage carry the cohort progress list. If a chart is added, use the `dataviz` skill and give it a table or text equivalent.

## 2. Rendering expensive aggregate reports in Django

Options: live on request, cached with a short TTL, or a precomputed snapshot (the last generated report's data).

Practices (general practice, not web-verified this session)
- Measure first, as the idea says. Count queries with `assertNumQueries` or `CaptureQueriesContext` at 30, 100 and 300 learners. The gather should be a constant number of queries per cohort or per course, not per learner. Per-learner queries mean an N+1 to fix before any caching.
- Cheap numbers (counts of learners and cohorts, average progress, not started / in progress / complete) should come from single `aggregate()` or `annotate()` queries over `CourseProgress`. Reserve the gather for numbers that need it (failed latest quiz, quiz confusion, wrong answers).
- Failed latest quiz is the costly flag. Use a subquery or `Window`/`DISTINCT ON` (PostgreSQL) to get the latest attempt per learner and form in one query, not a loop.
- Use `select_related`/`prefetch_related` (project rule) and `Prefetch(..., to_attr=...)` with filtered querysets for per-learner data.
- Live is the simplest and always correct. Add caching only if measurement says the gather is too slow at realistic sizes. If cached:
  - Key per cohort (and per site), short TTL (1 to 5 minutes), so staleness is bounded without any invalidation code.
  - Event-driven invalidation (progress, quiz attempt, registration change) is more precise but couples the cache to every write path. Avoid it unless the TTL is shown not to be enough.
  - Never cache per-user permission-filtered output under a cohort-only key. Cache the cohort gather (permission-neutral) and apply the permission check before reading it.
- A snapshot (render from the last `GeneratedReport` data) is cheap to read but can be hours old and has no data of its own to show if none exists. If used, show "as of <timestamp>" prominently. A mix is reasonable: dashboard tiles live from aggregates, cohort report tab live up to the cap, PDF is the snapshot.
- Max-size caps: `REPORTS_MAX_LEARNERS` must apply on screen and in the PDF. When hit, say so in text at the top of the panel ("Showing the first N of M learners") and do not silently truncate. Order deterministically before truncating.
- Paginate or collapse the per-learner detail on screen. Render summary and attention list first and load the per-learner detail lazily (HTMX `hx-trigger="revealed"` or a tab load) so the first paint stays fast.

What it means for this idea
- Likely design: dashboard tiles from aggregates, needs-attention list from a bounded gather per cohort (or a shared narrower query), cohort report tab live with a cap, with a TTL cache added only if the measurement demands it.
- Record the measurement results in the spec decisions and the roadmap unknowns table, as the idea requires.

## 3. Async report generation UX (polling with HTMX)

Findings
- htmx polls with `hx-trigger="every Ns"`. The server stops the poll by returning HTTP 286. Load polling (a delayed `load` trigger) suits jobs with an end point. Sources: https://htmx.org/docs/ and https://four.htmx.org/patterns/progress-bar.md
- `django-htmx` provides `HttpResponseStopPolling` (status 286). Source: https://pypi.org/project/django-htmx/1.6.0 (also https://github.com/Tiny-Tiny-App/django-htmx).
- Animate progress with `transform: scaleX()` rather than width, per the htmx progress-bar pattern: https://four.htmx.org/patterns/loading/progress-bar

Practices (general practice unless cited)
- States to show: none yet, pending/running ("A report is being generated"), done (download link plus generated-at time), failed (reason in plain words plus a retry). Each state is a partial returned by one status endpoint.
- Poll interval 2 to 5 seconds, with a stop on done or failed (286). Do not poll forever: also stop after a generous ceiling and show "taking longer than expected, refresh later".
- One in flight per cohort: enforce server-side (the existing `GeneratedReport` rule), not just by disabling the button. A second request while one runs should return the same in-progress partial, not an error. Several educators opening the same cohort page see the same state because it comes from the database, not the session.
- Status region should be `role="status"`/`aria-live="polite"` so screen-reader users hear "report ready". Do not move focus on each poll.
- A failed task must leave the row in a terminal state, otherwise the one-in-flight rule blocks the cohort forever. Spec should say how a stuck "running" report is treated (timeout after N minutes counts as failed).
- The download endpoint must re-check `can_view_cohort` and serve the file through a view, not a public media URL.
- HTMX validation errors return 422 (project convention).

## 4. CSV export safety

Findings
- OWASP lists the dangerous leading characters as `=`, `+`, `-`, `@`, tab (0x09), carriage return (0x0D), line feed (0x0A), and full-width variants. Prefixing the value with a single quote is the suggested mitigation. Escaping the leading character alone is not enough: field separators and quotes can start a new cell. Source: https://owasp.org/www-community/attacks/CSV_Injection
- The older OWASP wiki listed only four characters. Use the current list. Source: https://wiki.owasp.org/index.php/CSV_Injection
- Excel can strip quotes or escapes on save and re-open, so mitigations can be undone. Same OWASP page. A real-world advisory: https://symfony.com/cve-2021-41270

Practices (general practice, not web-verified this session)
- Learner names and emails are user-controlled (a learner can set their own display name), so every text cell in the roster is untrusted. Put one `sanitise_csv_cell()` helper in the export hook (spec 2) and apply it to every string field, not field by field.
- Do not prefix legitimate numeric values (a negative number) in a way that breaks numeric columns. Apply it to strings only.
- Encoding: write UTF-8 with a BOM (`utf-8-sig`) if educators open files in Excel, otherwise accented names are garbled. Use Python's `csv` module (never string joining), `lineterminator="\r\n"`, and ISO 8601 dates.
- Streaming: Django's `StreamingHttpResponse` with a generator and an echo buffer (pattern in the Django docs "Outputting CSV") keeps memory flat. A roster is small (hundreds of rows), so a plain `HttpResponse` with `csv.writer` is acceptable and simpler. Cap rows and iterate with `.iterator()`.
- Set `Content-Disposition: attachment; filename="..."` with a slugified cohort name and date. Avoid the user-controlled name in the header unsanitised.
- Test: a name of `=HYPERLINK("http://x","y")` comes out neutralised; a name with a comma, quote and newline round-trips through `csv.reader`.
- Roster includes organisation members with a role on the cohort: only emit columns the viewer is allowed to see (see section 5), and consider whether an email column is needed at all (minimise personal data).

## 5. Multi-tenant and permission-scoped aggregation

Practices (general practice, not web-verified this session; project skill `fls-dev:multi-tenant` is the source of truth for FLS)
- Build the set of visible cohorts first (from the spec 5 matrix: organisation admins see all in their site/organisation, cohort admins and viewers see assigned cohorts), then filter every aggregate by that set in the query (`cohort__in=visible`). Never compute the total and subtract.
- One function returns the visible-cohort queryset and every tile, list and drill-down uses it. A tile count and the list under it then cannot disagree.
- Aggregates leak through counts. A cohort admin's "average progress" must be over their cohorts only, and an empty visible set must give a zero/empty state, not a division error or an organisation-wide number.
- Site-aware managers filter by site automatically; do not bypass them with `all_objects`-style managers in report code. Check that gather queries go through the site-aware manager, including joins through `CourseProgress`, form attempts and registrations.
- Authorisation on object routes: the report tab, PDF generate, PDF download, quick view and learner drill-down must each call `can_view_cohort` (or the learner equivalent: learner visible via a visible cohort). Return 404 rather than 403 for objects outside the user's scope, to avoid confirming they exist.
- A learner in two cohorts, only one visible: the drill-down shows only the visible cohort's courses.
- Tests: for each role, assert numbers on the dashboard equal the numbers computed over only that role's cohorts, with a second out-of-scope cohort seeded to catch leaks. Include a cross-site case.

## 6. Accessibility of stat tiles and status badges

Findings
- WCAG 1.4.1 Use of Color: colour must not be the only way to convey information. Sufficient techniques include a text equivalent (G14) and additional visual cues (G182). Source: https://w3c.github.io/wcag/understanding/use-of-color.html
- Practitioner advice: pair each status colour with a label or icon and a shape. Source: https://www.disabilityworld.org/toolkit/standards/wcag/1-4-1-use-of-color/
- Badge text and icon contrast falls under separate criteria (1.4.3 text contrast 4.5:1, 1.4.11 non-text contrast 3:1) (general practice).

Practices
- Every badge carries visible text ("Needs attention", "In progress", "Complete", "Not started"), not just a dot. The spec 4 vocabulary already maps to the report flags; keep the text in the same single definition in `reports`.
- Do not rely on red versus green alone for at-risk. Add an icon with an accessible name or text.
- A stat tile is a label plus a value. Use a semantic structure the screen reader reads as a pair: for example `<dl>`/`<dt>`/`<dd>`, or a heading and value in reading order with the label first ("Learners needing attention: 7"). Avoid a big number followed by a detached caption.
- If a tile links to a filtered list, make the whole label-and-value a single link with a descriptive name.
- Progress bars: use `<progress>` or `role="progressbar"` with `aria-valuenow/min/max` and a visible percentage text.
- Tables in the cohort report need `<th scope>` and captions. Needs-attention lists work as a real list or table, with the quick view trigger being a `<button>` with an accessible name that includes the learner ("View Thandi Nkosi").
- The in-progress report region uses `aria-live` (section 3). Respect `prefers-reduced-motion` for the progress animation.
- Mobile: tiles stack in one column; do not hide the attention reason on small screens.

## 7. Summary of recommendations for the spec

1. Measure the gather (queries and time at 30/100/300) before choosing live versus cached. Default to live; add a short TTL cache per cohort only if needed; skip event-driven invalidation.
2. Compute dashboard tiles from aggregates over a single visible-cohort queryset; use the gather only for flags that need it.
3. One status/flag definition in `reports`, with a human reason string, used by tiles, lists, badges and CSV.
4. Surface `REPORTS_MAX_LEARNERS` truncation in text, with deterministic ordering.
5. PDF generation: server-enforced one-in-flight, HTMX polling with 286 stop, failed and stuck states handled, download re-checks permission.
6. Roster CSV: OWASP-complete formula neutralisation helper on all string cells, UTF-8 with BOM, `csv` module, attachment filename sanitised.
7. Tests per role, with out-of-scope data seeded, including cross-site.
8. Badges and tiles: text plus icon, semantic label/value pairs, live region for async status.

status: ok
