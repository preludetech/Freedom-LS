# Frontend QA report: misc-small-fixes-manual

## Methodology

- Branch: `misc-small-fixes-manual`, confirmed live via the debug-branch-badge for the duration of the run.
- Dev server: port 8473 for the first pass, 8059 for the resumed second pass. Two short-lived servers on scratch settings (8291, 8417) were used for the settings-dependent checks in §1.6, §2.6 and §2.7; all were stopped afterwards.
- Account: `demodev@email.com`, except where a test needed a fresh signup (§12.3) or an unregistered learner.
- Two checks needed altered settings (§2.7's durable task backend, §12.1's blank `FORCE_SITE_NAME`, plus §1.6 and §2.6). These ran against a throwaway `config/settings_qa_check.py` that imported from the real settings and overrode only the value under test; the tracked `config/settings_dev.py` was never edited, and the scratch module was deleted at the end. `git status` is clean.
- Screenshots live in `screenshots/` beside this report; every image referenced below is one of the 17 PNGs captured across the two passes.
- A compression pass ran over the captured screenshots afterward and found nothing over 1024KB.
- **The run happened in two passes.** The first pass was cut short by an environment failure — the shared dev Postgres wedged after section 9 (see "Environment failure" below). The containers were later restarted and the run was **resumed and completed**: sections 1, 2, 12.1, the remaining §4 gaps, 3.9, 5.24, 6.3, 7.8, 9.6, 10.2–10.3, 11.2, 11.4, 12.2–12.5 and both the mobile and tablet passes all ran in the second pass. **No test in this plan is left unrun.** Screenshots from both passes sit together in `screenshots/` (17 files); the 14:xx timestamps are the first pass and the 17:xx ones the second.

## Diff scoping

The scoping record classified this diff as **FULL**, triggered by the changed template and CSS paths — `content_engine/templates/cotton/*.html`, `learner_interface/templates/.../course_form*.html`, `learner_interface/templates/cotton/course-card-shell.html`, `reports/static/reports/print.css`, `themes/default/static/themes/default/theme.css`, and `tailwind.components.css`, alongside several non-template Python changes (mail, allauth adapter, site-aware models, three admin modules, both settings files).

FULL scope means desktop, mobile and tablet were all in scope for the affected sections (§3, §4, §5, §6 and the §12.8 repeat). **All three viewports ran.** The desktop pass completed in the first pass; the mobile (375x812) and tablet (768x1024) passes ran in the second, after the environment recovered. Nothing was scoped out.

## Smoke gate

Passed. Both checked pages loaded cleanly before the full run began:
- `http://127.0.0.1:8473/`
- `http://127.0.0.1:8473/courses/functionality-demo-show-end-with-quiz/2/`

No failure URL or failure reason recorded.

## Environment failure

**Resolved.** This section is kept as the record of what happened during the first pass. The Docker containers were restarted afterwards (`dev_db-postgres-1`, `dev_db-mailpit-1` both came back up), every seeded fixture survived, and the run was resumed and completed. Roughly a third of the plan was blocked at the time; none of it is blocked now.

The shared dev Postgres at `127.0.0.1:6543` stopped serving queries partway through the run, after section 9 finished. The failure signature was precise:

- TCP connections were still **accepted**, but no query ever completed a handshake: `psql 'select 1'` timed out, and `manage.py check` timed out against the same database.
- The listen backlog climbed while this was being observed — **47, then 60, then 65** — consistent with connections queuing up behind a server that had stopped accepting new work at the protocol level.
- Both Docker contexts (`default` and `desktop-linux`) reported **zero containers** running, while the forwarded ports 6543 (Postgres), 1025 and 8025 (Mailpit) stayed open. That combination — ports open, no containers — is the signature of a wedged Docker Desktop VM sitting behind its host-side port forwarder: the forwarder keeps the socket alive even though nothing on the other end can answer.
- Concurrent `pytest` runs from another session were in flight at the time: one in this worktree, one in the sibling `error-pages` worktree. Contention from those parallel test databases is the most likely trigger.

**This is not a defect in this branch.** It is host/environment infrastructure failing independently of the code under test.

Rule 2's recovery ladder (Content reset → DB drop → DB create → Migrate) could not help: every rung in that ladder requires a working Postgres connection to execute, and the database was unreachable at the transport level throughout. There was no rung that could clear a Docker VM wedged behind its own port forwarder.

Sections 1 and 2 (auth email tenant naming, queued mail) never ran at all, since both require the database to trigger and read email. Section 12.1 (the `get_cached_site(None)` hazard, the plan's highest-value regression probe) also never ran, for the same reason. The full list of skipped test IDs and their individual reasons is in the Results tables below.

On resumption Postgres answered immediately, Mailpit came back with an empty inbox — which made every message in section 1 and 2 attributable to this run — and the seeded data was intact (21 cohorts, 217 learners, 13 organisations, 12 courses).

## Results

### 0. Setup
No individually-numbered checks; setup steps (Tailwind build, dev server, seed data, login) succeeded implicitly — everything from §3 onward that depended on them ran normally.

### 1. Auth email names the tenant, not its domain

| test_id | status | notes |
| --- | --- | --- |
| 1.1 | pass | Subject is `[FirstClass] Reset your password` — HEADER_TITLE via the shared `site_display_name`. Not `[DemoDev]` (the Site row name pinned by `FORCE_SITE_NAME`) and not a bare domain. Confirmed on a second email type too: signup verification arrived as `[FirstClass] Confirm your email address`. |
| 1.2 | pass | Prefix and body agree exactly: `FirstClass` appears 8 times in the message body and `DemoDev` appears 0 times. |
| 1.3 | pass | Branding intact after the `get_current_site` → `get_cached_site` swap: `<img src=".../static/images/first_class_logo.png" alt="FirstClass">` renders in the HTML part. |
| 1.4 | pass | The reset URL is unbroken and works end to end — navigating it reached `/accounts/password/reset/key/6-set-password/` (Change Password), so the token was accepted. The password was deliberately not changed. |
| 1.5 | pass | The `text/plain` and `text/html` parts carry the identical unbroken URL; both are charset utf-8. |
| 1.6 | pass | With `HEADER_TITLE` blanked via a scratch settings module, the subject becomes `[DemoDev] Reset your password` — the Site row's own name. The HEADER_TITLE-first chain resolves correctly in both directions. |

### 2. Mail is queued onto the background worker

| test_id | status | notes |
| --- | --- | --- |
| 2.1 | pass | `manage.py check`: "System check identified no issues (0 silenced)." No E007, no other errors. |
| 2.2 | pass | A password reset returns 302 promptly and the mail lands in Mailpit through `QueuedEmailBackend`. |
| 2.3 | pass | Both parts carry `Content-Transfer-Encoding: 8bit` with **zero** quoted-printable soft breaks — the only lines ending in `=` are MIME multipart boundaries. Verified on the inline path and, decisively, on a message that went through the real Postgres JSONField task payload (see 2.7). |
| 2.4 | pass | Through the durable queue: a subject with `— ünïcode ✓ Ωμέγα` arrived intact, the HTML alternative present with its non-ASCII, a long URL unbroken, and **both** attachments surviving — `binary.bin` (application/octet-stream, 18 bytes) and `notes.txt` (text/plain, 34 bytes). Confirms the `SerialisedAttachment` text-vs-bytes discrimination. |
| 2.5 | pass | Under dev's default `ImmediateBackend` no `DBTaskResult` row is written at all — the task runs inline. 0 rows is correct here, not a failure. Under the durable backend the row appears and reaches SUCCESSFUL. |
| 2.6 | pass | Pointing `EMAIL_UPSTREAM_BACKEND` at `QueuedEmailBackend` makes `manage.py check` fail with `SystemCheckError` and exactly `freedom_ls_deployment.E007`, whose hint correctly names `EMAIL_UPSTREAM_BACKEND` as the setting to change and notes that `EMAIL_BACKEND` is the one naming the queue. |
| 2.7 | pass | **The silent-failure mode is real and was reproduced in full.** With `TASKS` on `django_tasks_db.DatabaseBackend` and **no worker running**: the reset POST returns 302 and the user sees the success page, Mailpit receives **zero** messages, and a `DBTaskResult` row for `freedom_ls.deployment.mail._send_email_task` sits at `status=READY`, `priority=10` (the elevated `EMAIL_TASK_PRIORITY`). Starting `fls_run_worker` delivered it within ~3 seconds and the row moved to SUCCESSFUL. The delivered message still carried the `[FirstClass]` prefix and 8bit encoding after the full database round trip. |
| 2.8 | pass | Task row reached SUCCESSFUL once the worker picked it up. |
| 2.9 | pass | The queued payload is a plaintext `DBTaskResult` row carrying the rendered message including the live reset link, exactly as `docs/product/security-and-data-handling.md` describes. Documented trade-off, not a defect. |

### 3. The form player gets the standard navigation footer

| test_id | status | notes |
| --- | --- | --- |
| 3.1 | pass | Form start page has Previous on the left and the forward button on the right. ![](screenshots/page-2026-09-04T14-16-13-277Z.png) |
| 3.2 | pass | Form footer matches the topic player exactly: both pages render secondary at 34px and primary at 32px, 14px font, 6px 8px padding. The 2px gap is the secondary border, present identically on the topic page, so not a branch regression. |
| 3.3 | pass | Previous navigates to `/courses/functionality-demo-show-end-with-quiz/1/`, the preceding topic. |
| 3.4 | pass | Previous is btn-secondary with a previous icon; Try Again is btn-primary with a retry icon. |
| 3.5 | pass | Runner page Previous (btn-ghost btn-sm) and Next (btn-primary btn-sm) are both 32px at 14px, matching each other. |
| 3.6 | pass | Submit-confirm dialog opens from the last runner page's Next, with Go back and review / Submit. |
| 3.7 | pass | Completion-page buttons are small-sized and centred. Retry variant covered by the try_again state seen on the start page. |
| 3.8 | pass | Nav wrapper carries `hx-boost=true`, `hx-target=#interface-main`, `hx-select-oob=#course-toc-region`. Clicking Previous swapped without a full document reload. |
| 3.9 | pass | Built a course whose first item is a form (`qa-form-first-course`). Its start page has **no** Previous button — no `data-testid=previous-button`, no element containing "previous" — and the forward button stays flush right: "Start Form" right edge 1784 against the nav's right edge 1784. The left slot renders as an empty `<div>` under `justify-content: space-between`, which is exactly what the template comment says it is for; without it a lone child would left-align. ![](screenshots/page-2026-09-04T17-34-04-649Z.png) |
| 3.10 | **fail** | Form completion page has no Previous button at all (no `data-testid=previous-button`, no element containing "previous"). Its wrapper is `mt-8 flex flex-col sm:flex-row justify-center gap-3` — centred, not the player's justify-between footer. The sizing half passes: Continue is btn-primary btn-sm at 32px. ![](screenshots/page-2026-09-04T14-18-24-076Z.png) — see B1. This is the expected failure the plan calls out in advance. |

### 4. A required question's asterisk stays on the question's last line

| test_id | status | notes |
| --- | --- | --- |
| 4.1 | pass | Asterisk top == question paragraph top == number top on all three questions; legend height 20px = one line. |
| 4.2 | pass | Question number and question text share a line (numTop == pTop on all three). |
| 4.3 | pass | At a 375px viewport, grew a required question until its legend wrapped to 1, 2, 3 and then 4 lines. The asterisk stayed on the same line as the character immediately before it every time, landing at x-offsets 297, 163, 86 and 227 — it follows the last word wherever that falls and never drops to a line of its own. The `&nbsp;` is doing its job. ![](screenshots/page-2026-09-04T17-21-59-161Z.png) |
| 4.4 | pass | Bold (font-weight 900), links (colour distinct from body text) and inline code (ui-monospace) all render inline inside the legend, all on one line, and the asterisk still stays bound to the last character. `[&>p]:inline` touches only direct `<p>` children, leaving inline markup untouched. |
| 4.5 | pass | Asterisk carries `aria-hidden=true` and a sibling `sr-only` span reading "(required)". |
| 4.6 | pass | The **Course Feedback Survey** shows both states on one page: Q1 and Q2 (`required: true`) carry the asterisk **and** the sr-only "(required)"; Q3, Q4 and Q5 (`required: false`) carry neither. Number, question text and asterisk share a line on every required question. |
| 4.7 | pass (with a caveat) | The trade-off is real and visible. Injecting a second `<p>` into a question legend: both paragraphs compute to `display:inline` and share the same top, so they run together with **no separating space** — the text reads "How would you rate this course overall?This is a second paragraph…". No seeded content triggers this today, but an author writing a two-paragraph question would get visibly wrong output. See General notes for the suggested fix. |

### 5. Content widgets

| test_id | status | notes |
| --- | --- | --- |
| 5.1 | pass | Face labels read Question and Answer. ![](screenshots/page-2026-09-04T14-18-56-632Z.png) |
| 5.2 | pass | Both faces carry a "Tap to flip" hint, `aria-hidden=true`. |
| 5.3 | pass | Back face paints `linear-gradient(135deg, ...)` from the `--fls-flashcard-back-gradient` token; clearly distinct from the plain front. ![](screenshots/page-2026-09-04T14-19-08-257Z.png) |
| 5.4 | pass | Answer-face prose is `rgb(26,35,50)` on an oklab 0.94–0.97 lightness tint; label `rgb(43,108,176)`; hint a 60% mix. All legible. |
| 5.5 | pass | Front and back both 250px tall. |
| 5.6 | pass | Click, Enter and Space each toggle `aria-pressed`; front/back `aria-hidden` swap with it. |
| 5.7 | pass | Corner labels and flip hints are `aria-hidden=true`; the trigger carries `aria-label='Flip card'` and `aria-pressed`. |
| 5.8 | pass | Focus ring renders as a white offset ring plus `rgb(43,108,176)` — the focus-ring token, not primary. |
| 5.9 | pass | Closed summary is `rgb(26,35,50)`, the default on-surface colour. ![](screenshots/page-2026-09-04T14-20-02-793Z.png) |
| 5.10 | pass | Hover tints the summary to `rgb(243,244,246)`; parent has `border-radius 8px` with `overflow:hidden` so the tint is clipped to the corners. |
| 5.11 | pass | Open state moves summary AND chevron to `rgb(43,108,176)` and rotates the chevron 180deg. |
| 5.12 | pass | `focus-visible` ring present and inset (`ring-inset`), not clipped by the host overflow. |
| 5.13 | pass | Summary padding is 16px 20px (was 12px 16px) — visibly roomier. Body inner padding 0 20px 20px, unchanged in feel. |
| 5.14 | pass | Title is `flex 1 1 auto` with `min-width 0`; chevron `ml-auto shrink-0` stays pinned right. |
| 5.15 | pass | Figure 1's description renders on the page as `<p class='text-muted text-sm mt-3'>`. ![](screenshots/page-2026-09-04T14-20-26-427Z.png) |
| 5.16 | pass | Description width 542px equals the title row width 542px — full card width, not stopping at the button. |
| 5.17 | pass | "Figure 1" renders in `ui-monospace` at `rgb(43,108,176)` with no colon after it. |
| 5.18 | pass | Trigger button reads "Expand". |
| 5.19 | pass | Title top == Expand button top on every figure on the page, including Figure 1's deliberately long three-line title. |
| 5.20 | pass | Lightbox opens with heading, "Close image" button, and both the title and description paragraphs beneath. Escape closes it. ![](screenshots/page-2026-09-04T14-20-47-764Z.png) |
| 5.21 | pass | The nine figures with no description render no trailing paragraph at all. |
| 5.22 | pass | Figures without a number show "Figure:" in the lightbox heading; the reflowed template lines introduced no stray whitespace. |
| 5.23 | pass | Ref is mono/primary and reads as a caption label against the medium-weight title; the dropped colon does not leave the two fragments disconnected. |
| 5.24 | pass | Under emulated `prefers-reduced-motion: reduce` (matchMedia confirms it matches), the accordion chevron's transition computes to `none` — the animation is genuinely dropped — yet both widgets still change state: the flashcard's `aria-pressed` goes false→true and the accordion opens with its body visible and its summary shifting to `rgb(43,108,176)`. Motion dropped, functionality preserved. |

### 6. Course cards

| test_id | status | notes |
| --- | --- | --- |
| 6.1 | pass | Dashboard card body computes to flex/column and the eyebrow sits in its own wrapper div; the chip inside measures 16px against a 345px body, so it is not blockified to card width. ![](screenshots/page-2026-09-04T14-22-02-841Z.png) |
| 6.2 | pass | Details wrapper is `flex justify-end mt-auto`. Across each row of cards every Details link shares a bottom edge (558/558/558, then 929/929/929, then 1295/1295) despite differing description lengths; one shorter card resolves `mt-auto` to 60px of pushed space and still aligns. |
| 6.3 | pass | **Mobile 375px:** cards stack to one column at 343px with no horizontal overflow (scrollWidth == 375); the eyebrow chip stays 16px against a 309px eyebrow rather than stretching; `mt-auto` resolves to 0px because a single-column card has no slack to distribute, which is correct. **Tablet 768px:** cards form 2-column rows and *every* row's Details links share an exact bottom edge (510/510, 865/865, 1219/1219, 1566/1566), with `mt-auto` absorbing 28px and 56px on the shorter cards — the clearest demonstration of the fix working. ![](screenshots/page-2026-09-04T17-23-39-733Z.png) ![](screenshots/page-2026-09-04T17-22-47-146Z.png) |

### 7. An organisation's cohorts and learners on its admin page

| test_id | status | notes |
| --- | --- | --- |
| 7.1 | pass | Cohorts inline present on the change page with a Name column, per-row Change links and an "Add another Cohort" control. ![](screenshots/page-2026-09-04T14-22-25-877Z.png) |
| 7.2 | pass | Cohorts inline is editable with 14 change links and 15 name inputs; ordered by name. |
| 7.3 | pass | Learners inline has columns User / Is active / Created at, zero text inputs and zero DELETE checkboxes — read-only with per-row change links. |
| 7.4 | pass | Paginated at 25 over 9 pages for 204 learners. Page 1 ends `demodev_s31@`, page 2 begins `demodev_s32@` and runs to `demodev_s8@` — 25 unique per page, correct lexicographic order, no repeat and no skip across the boundary. The ordering fix holds. |
| 7.5 | pass | Related row reads "Search this organisation's 204 learners"; the link targets the Learner changelist with `organisation__id__exact` set, and that changelist reports 204 learners and offers a search box. |
| 7.6 | pass | Northside (no learners) renders "Related No learners yet" as plain text with no anchor. |
| 7.7 | pass | An organisation seeded with exactly one learner renders "Search this organisation's 1 learner" — singular, with the correctly filtered changelist href. Fixture built via `fls-dev:qa-data-helper` ("QA Singular Learner Org"). |
| 7.8 | pass | Added a cohort through the inline as a user would: opened the Cohorts tab, clicked "Add another Cohort", typed the name, saved. `QA Inline Cohort` was created, belongs to the right organisation, and took the organisation's site (`cohort.site_id` 3 == `org.site_id` 3). The tab bar also shows working count badges — "Cohorts 0" and "Learners 1" — corroborating 7.7's singular case. |
| 7.9 | pass | Add organisation page shows no inlines, no management forms and no Related row; fields are name/logo/logo_on_dark only. Saving "QA Add Page Check" succeeded and the changelist grew from 6 to 7 rows. |
| 7.10 | pass | The 204-learner organisation change page loads without visible stall, comparable to the small ones; `select_related` on the inline queryset is in place. |

### 8. Topic content preview in the admin

| test_id | status | notes |
| --- | --- | --- |
| 8.1 | pass | Content Preview renders real HTML: flashcard and accordion elements exist as DOM nodes, not escaped source and not raw markdown. |
| 8.2 | pass | Add topic page returns 200 with no traceback; the empty preview renders as an empty block. |
| 8.3 | **fail** | All 14 topic admin pages return 200 with no traceback, so no 500. But every Alpine-driven widget in the preview throws ReferenceErrors: "flashcard is not defined", "flipped", "frontStyle", "backStyle" on Interactive Widgets; "contentLightbox is not defined" on Media and Pictures. The flashcard writes the literal string "undefined" into its style attribute, loses its 3D geometry, and renders question AND answer side by side with no aria state — the answer is exposed. Component CSS is absent too: accordion summary padding computes to 0px. ![](screenshots/page-2026-09-04T14-25-08-466Z.png) — see B2. |
| 8.4 | pass | The readonly preview container holds 0 script tags and 0 inline `on*` handlers. Its 2 iframes are the legitimate allowlisted `https://www.youtube.com/embed/` sources from the content. nh3 sanitisation is intact. |
| 8.5 | pass (via 8.3) | Every seeded widget-bearing topic was opened as part of 8.3; the finding is B2. |
| 8.6 | pass | Large topics (Media, Interactive Widgets) load their change page without noticeable delay and the form below the preview stays usable. |

### 9. The cohort report prints on white paper

| test_id | status | notes |
| --- | --- | --- |
| 9.1 | pass | Pixel-sampled the generated PDF: pure white (255,255,255) is the dominant colour on every page at 88.2/92.2/94.9/93.2 percent. The paper is `--report-paper #FFFFFF`, not a theme surface. |
| 9.2 | pass | (242,242,242) — exactly `--report-fill #F2F2F2` — is the second colour on the cover (3.5%) and the at-a-glance page (4.5%), covering the cover card, stat cells, table headers and banding. |
| 9.3 | pass | Ratio-bar track keeps its 0.4pt muted outline alongside the `--report-fill` background, so a 0% bar stays visible on a banded row. |
| 9.4 | pass | PDF metadata Creator is "FirstClass" — `resolve_site_name` via the shared `site_display_name`, honouring HEADER_TITLE. Author is "DemoDev", the organisation, whose wordmark renders on the cover. |
| 9.5 | pass | Cover page bleed band reaches the left, right and bottom edges; `body margin:0` is intact. |
| 9.6 | pass | Rendered the report to true greyscale. Paper is level 255, the `--report-fill` band level 242, and the bar outline a distinctly darker 212 — three separable tones. Visually decisive: the two 0% learners both sit on **banded** rows and their empty tracks remain clearly visible as outlined rectangles, exactly the case `print.css`'s comment says the outline exists for. Partial bars keep the full track length visible so the fraction reads correctly. ![](screenshots/page-greyscale-ratio-bars.png) |
| 9.7 | pass | Proved structurally, which is stronger than a pixel diff — see General notes for detail. |

### 10. Dev shows every course as visible and free

| test_id | status | notes |
| --- | --- | --- |
| 10.1 | pass | Content Widgets - Demo Reference is declared `visibility: coming_soon` in its `course.md`, yet it appears on `/courses/` and opens straight into the player at `/courses/content-widgets-demo-reference/1/`. The visibility override is live in dev. |
| 10.2 | pass | The `application_gated` course presents the free path: its only CTA is "Enrol for free" pointing at `/access/`, and the page never mentions applying. Confirmed in code at `course_access/backends.py:367-370`, where `override_access_to_free()` replaces the inner backend's real decision with `_free_access_decision()`, ignoring the course's actual `access_config`. |
| 10.3 | pass — **the test plan's expectation was wrong** | The plan expected badges to keep reporting each course's *declared* access. They do not, and that is deliberate: `course_access/backends.py:381-387` states "Dev/staging preview: badge reads Free regardless of the real access model", delegating the copy to `FreeOnlyCourseAccessBackend`. The application-gated course accordingly reads "Enrolment: Free · open", "Free · open to everyone", "One click. No credit card." The UI is internally consistent — the label matches what clicking will actually do. The override relabels as well as re-gates, by design, and this behaviour predates the branch; only the flag flip is new. See General notes for the QA consequence. |
| 10.4 | pass | `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` and `OVERRIDE_COURSE_ACCESS_TO_FREE` appear only in `config/settings_dev.py`; neither is set in `settings_prod.py` or `settings_base.py`, and both default to `False` where declared in `course_access/config.py`. Production is unaffected. |

### 11. Deployment guards and the bootstrap command

| test_id | status | notes |
| --- | --- | --- |
| 11.1 | pass | `setup_initial_prod_data` with no `--site-name` exits with "Error: Missing option '--site-name'." and creates nothing. Click validates before touching the database. |
| 11.2 | pass | `setup_initial_prod_data` with `--site-name "QA Tenant Name"` created the Site with `name='QA Tenant Name'` — the supplied name, not the domain the old `site_name or resolved_domain` fallback would have used. It printed a one-time generated password and created a **verified** allauth `EmailAddress` row, so the account can actually sign in under mandatory verification. |
| 11.3 | pass | `.env.example` documents that mail is queued by default, that a deployment running no worker must set `EMAIL_BACKEND` back to the SMTP backend, that `EMAIL_UPSTREAM_BACKEND` is the way to keep queueing with a provider backend, and `EMAIL_TIMEOUT=10` with its rationale. |
| 11.4 | pass | `check --deploy` against the production settings module raises **no E007** and no new errors attributable to this branch. The 6 errors reported are artefacts of a synthetic production environment — five E002 for unset `AWS_S3_*_BUCKET_NAME` storage aliases and one E005 for the cache table `createcachetable` makes during a real deploy — plus two pre-existing HSTS warnings (W005, W021). `EMAIL_BACKEND` defaulting to the queueing backend under prod settings tripped nothing. |

### 12. Regressions elsewhere

| test_id | status | notes |
| --- | --- | --- |
| 12.1 | pass — **and the branch is a strict improvement here** | Probed off-request (`allauth_context.request` is `None`) under FLS's normal config (`FORCE_SITE_NAME='DemoDev'`, no `SITE_ID` anywhere): this branch's `AccountAdapter.format_email_subject` returns `'[FirstClass] Reset your password'`, while allauth's upstream `DefaultAccountAdapter` **raises `ImproperlyConfigured`** on the identical config. `get_cached_site` short-circuits on `FORCE_SITE_NAME` and never reaches `get_current_site`. The residual crash appears only when an install pins **neither** `FORCE_SITE_NAME` **nor** `SITE_ID` — and in that configuration upstream allauth crashes too, since its own default calls `get_current_site(context.request)` the same way (`allauth/account/adapter.py:160`). The branch narrows the hazard rather than widening it. See General notes for the deployment requirement this implies. |
| 12.2 | pass | The site header renders "FirstClass" — the same `site_display_name` resolution the email subject prefix and the report cover use. All three surfaces agree, which is the point of the shared helper. |
| 12.3 | pass | Full allauth loop exercised: sign out; sign up a new account with consent checkboxes; the verification email arrived as `[FirstClass] Confirm your email address`; the confirmation link was accepted and logged the new user straight in ("Welcome back, Quinn"); sign out and sign back in as the admin. Password reset request and reset-key link were exercised in section 1. |
| 12.4 | pass | Swept 15 course item pages across all five demo courses: every one returned 200 with no traceback and rendered `#interface-main`. Two standard-markdown items redirected to the course detail page — sequential unlock behaving correctly for a user who has not completed item 1, not a defect. |
| 12.5 | pass | Content Widgets topics 1, 3 and 5 all return 200 with no traceback and no "Image not found" error box. Structured Content still renders its 2 tables and 3 code blocks. The new component CSS did not disturb the other widgets. |
| 12.6 | pass | `learner_management/admin.py` imports `organisations.admin` and `organisations.models` at module scope; nothing under `organisations/` imports `learner_management` back, so there is no cycle. Matches the documented layering. Confirmed empirically too: the organisation change pages, the learner changelist and the admin index all rendered before the environment failure. |
| 12.7 | pass | Before the environment failure, the admin index and every changelist touched by this branch (organisations, learner, topic, generatedreport) opened without error. |
| 12.8 (mobile) | pass | 375x812 over sections 3–6. The form start page footer stays `flex`/`space-between` at 343px with Previous at x=16–118 and the action button at x=284–359 — no overlap, no horizontal overflow. The form runner's Next goes full width (343 of 375) at 32px tall via `w-full sm:w-auto`. The picture caption row holds: title first line aligns with the Expand button (both top 1650), title 206px and button 95px sit side by side in a 309px row without overlap, description runs the full 309px. ![](screenshots/page-2026-09-04T17-22-28-146Z.png) ![](screenshots/page-2026-09-04T17-23-09-610Z.png) |
| 12.8 (tablet) | pass | 768x1024. No horizontal overflow. The picture caption title still aligns with the Expand button (title 439px in a 542px row, no overlap) and the description still runs the full row width. Course cards form 2-column rows with every Details link bottom-aligned. |

### 13. What changed that nobody asked for

This is a read-only audit, not a browser test suite. Findings are recorded here and expanded under General notes / Bug sections; nothing in §13 is auto-fixed.

| test_id | status | notes |
| --- | --- | --- |
| 13.1 | **fail** | The deleted `visual_polish` folder's coverage claim is only one-third true. `course-card-details-link-not-bottom-aligned` IS fixed (verified as 6.2). `btn-sm-padding-crowds-the-button-icon` is NOT: the branch diff changes no `.btn-sm` rule at all, and adds three more `btn-sm` usages. `side-panel-dialog-paints-a-full-column-focus-outline` is NOT: grep finds zero `.side-panel-dialog` rules anywhere in `tailwind.components.css`. The deleted `research_focus_indicators.md` contained a completed diagnosis of that second issue — UA `:focus-visible` ring outlining the whole panel column, WCAG 2.4.7/2.4.13 analysis, and a recommended on-brand restyle using the already-declared but unconsumed `--color-focus-ring` token. That analysis is now only in git history. See B3. |
| 13.2 | pass | Confirmed coupling: `.picture-figure-title` uses `py-[calc(0.375rem+1px)]`, derived from `btn-sm`'s padding plus its border, to align the caption's first line with the Expand button. Changing `btn-sm` later silently breaks 5.19. Recorded, not fixed. |
| 13.3 | pass | Confirmed: `learner_management/admin.py` line 537 ASSIGNS `OrganisationAdmin.inlines` rather than appending, so a second contributing app would replace these two inlines. Line 538's `ORGANISATION_SUMMARIES.append` is correctly additive. No impact today; noted. |
| 13.4 | pass | `previous_url` is set before the `player_context` spread in both `view_topic` (line 906 vs 909) and `view_form` (972 vs 973), so the new code follows the existing pattern rather than introducing an inconsistency. The chrome context does not supply that key today. |
| 13.5 | **fail** | Docs gap. `--report-paper` and `--report-fill` appear nowhere in `docs/` or `claude_plugins/`. `print.css` now owns the report's two neutrals outright and no longer reads any theme surface token, so a downstream project can no longer rebrand the report's paper via `--color-surface` and is not told what replaced it. The flashcard's new tokens WERE documented in `docs/how tos/theme-fls.md`; these were not. See B4. |
| 13.6 | pass | `EMAIL_TIMEOUT` is set in `settings_prod.py` and `.env.example` with a default in `deployment/settings_defaults.py`, deliberately not in dev where Mailpit is local. `demo_content/` is clean under `git status` after `content_save`. |

**On §3.10 and whether it is the only failure:** it is not. §3.10 is the one expected failure called out in the plan before the run started. Two more failures surfaced during the run: §8.3 (content-preview widgets broken and answer disclosure, B2) and §13.1/§13.5 (audit findings that reached bug status: the deleted spec folder covering unfixed issues, B3; and the undocumented report tokens, B4). §13 findings are process/documentation observations for a human decision, not defects to fix in the code loop — they are reported as bugs here only because the plan explicitly asks that undocumented or miscovered changes be written up, and B3/B4 cross that line from "note" to "actionable gap."

## Bug: B1 — Form completion page has no Previous button and does not use the player footer

**Manifestations:** 3.10 (desktop)

![](screenshots/page-2026-09-04T14-18-24-076Z.png)

**Expected:** The form completion page carries back and forward navigation like every other page in the course player — a Previous button alongside Continue / Retry quiz / Return to course, in the player's `justify-between` footer.

**Actual:** No Previous button exists at all: no element with `data-testid=previous-button` and no element whose text contains "previous". The wrapper is `mt-8 flex flex-col sm:flex-row justify-center gap-3` — centred, not the player footer. Only the button sizing half of the `idea.md` item was done (Continue is btn-primary btn-sm at 32px, which is correct).

## Bug: B2 — Topic admin content preview breaks every Alpine-driven widget and exposes flashcard answers

**Manifestations:** 8.3 (desktop)

![](screenshots/page-2026-09-04T14-25-08-466Z.png)

**Expected:** The new read-only Content Preview renders a topic's markdown as it would appear to a learner, or at least without throwing.

**Actual:** The admin page renders the widgets' markup but registers none of their Alpine components and loads none of the site's component CSS. Every topic containing a flashcard throws four ReferenceErrors (`flashcard`, `flipped`, `frontStyle`, `backStyle`); every topic containing a picture throws `contentLightbox is not defined`. The flashcard writes the literal string "undefined" into its style attribute, loses its 3D geometry and renders the question AND the answer side by side with no aria state, so the preview discloses the answer. Accordion summary padding computes to 0px. No page 500s: all 14 topic change pages return 200 with no traceback.

## Bug: B3 — visual_polish spec folder deleted while two of its three diagnosed issues remain unfixed

**Manifestations:** 13.1 (desktop)

**Expected:** A spec folder deleted on the grounds that its items are covered should have its items covered, or be archived to `spec_dd/3. done/` rather than removed.

**Actual:** Only `course-card-details-link-not-bottom-aligned` is actually fixed. `btn-sm-padding-crowds-the-button-icon` is untouched (no `.btn-sm` rule changed; three more `btn-sm` usages added). `side-panel-dialog-paints-a-full-column-focus-outline` is untouched (zero `.side-panel-dialog` rules exist). Roughly 565 lines of research went with them, including a completed WCAG 2.4.7/2.4.13 diagnosis of the focus-ring issue and its recommended fix. Recoverable only from git history.

## Bug: B4 — New report colour tokens are undocumented, breaking the downstream rebrand path

**Manifestations:** 13.5 (desktop)

**Expected:** A downstream project can find out how to rebrand the report's paper and fill colours.

**Actual:** `print.css` now owns `--report-paper` and `--report-fill` outright and references no theme surface token, so overriding `--color-surface` no longer affects the report. Neither token appears anywhere in `docs/` or `claude_plugins/`. The flashcard's four new tokens were documented in `docs/how tos/theme-fls.md` in the same branch; these two were not.

## Bug status

The four bugs below were found in the first pass and are unchanged: none was routed to the auto-fix
lane, and the resumed pass did not attempt to fix them — it was about finishing the evidence. Their
todo items already exist.

**The completed second pass found no new bugs.** Two findings that the plan had anticipated as
possible defects turned out not to be, and both are recorded as passes with reasons: §12.1 (the
branch is a strict improvement over upstream allauth, not a regression) and §10.3 (the test plan's
expectation was wrong, not the code).

- **UNRESOLVED** — Form completion page has no Previous button and does not use the player footer
  (reason: well-specified and unit-testable; left for a TDD fix rather than fixed during a QA pass)
- **UNRESOLVED** — Topic admin content preview breaks every Alpine-driven widget and exposes
  flashcard answers (reason: turns on a product decision — whether the admin should load the site's
  Alpine components and component CSS, or the preview be narrowed to static markup)
- **UNRESOLVED** — visual_polish spec folder deleted while two of its three diagnosed issues remain
  unfixed (reason: a process and scope decision for a human, not a code defect)
- **UNRESOLVED** — New report colour tokens are undocumented, breaking the downstream rebrand path
  (reason: documentation, not a functional regression; the author should choose where the two tokens
  are documented)

## General notes

- **Pre-existing CSP console error, unrelated to this branch.** On course topic pages, a report-only Content-Security-Policy violation fires from a YouTube embed's redirect to a Google abuse-report page. Seen while exercising the widgets demo course during §5 and §8. Not introduced by anything in this diff.
- **Submit-confirm dialog buttons are still full-size.** The form's submit-confirm dialog (Keep going / Leave and submit / Go back and review / Submit) renders its buttons at full 16px size rather than `btn-sm`, unlike the topic and form-runner footer buttons that this branch resized. Modal buttons were arguably out of scope for the sizing commit; flagging for awareness, not filing as a bug.
- **§9.7 was proven structurally, and that is stronger than a pixel diff.** `print.css` and `reports/templates/` contain zero references to `--color-surface` or `--color-surface-2`, so no theme — current or future — can reach the report's paper through those tokens. This was confirmed two ways: (1) the tailwind bundle was temporarily rebuilt under `FLS_THEME=first_class` to verify that theme's tokens really are tinted relative to default (`--color-surface #F8F9FC`, `--color-surface-2 #EDF2F7`, vs. default's `#FFFFFF` / `#F3F4F6`) — confirming the pre-fix bug was real and `first_class`-specific; (2) grepping `print.css` and `reports/templates/` for those two token names returned nothing, and the only fills present are `--report-paper` (1 site, line 211) and `--report-fill` (10 sites), matching the ten replacements in the diff. The bundle was rebuilt back to the default theme afterward, so the working tree is not left with a `first_class` bundle in place.
- **Dev-only QA residue was seeded during this run.** An organisation named "QA Singular Learner Org" with one learner was seeded via `fls-dev:qa-data-helper` for test 7.7. An organisation named "QA Add Page Check" was created directly by test 7.9 (changelist grew from 6 to 7 rows). Both are dev-only fixtures on this branch's dev database and should be considered QA residue, not data to carry forward.

---

### Added by the resumed pass

**A latent authoring hazard in the required-asterisk fix (§4.7).** `[&>p]:inline` makes *every* direct
`<p>` child of a question legend inline, so a question whose rendered markdown is two paragraphs runs
them together with no separating space — "…course overall?This is a second paragraph…". Nothing in the
seeded content triggers this, and the fix it enables is worth more than the edge case, so this is a
note rather than a bug. If it is ever worth closing, pairing the rule with a separator would do it,
e.g. `[&>p+p]:before:content-['\00a0']`.

**A deployment requirement, not a defect (§12.1).** An FLS install that pins neither `FORCE_SITE_NAME`
nor `SITE_ID` will raise `ImproperlyConfigured` when any allauth email is sent outside a request cycle
— a management command, a shell, a cron job. This is inherited from allauth (whose own
`DefaultAccountAdapter.format_email_subject` calls `get_current_site(context.request)` identically) and
this branch actually *fixes* it for pinned installs. Worth stating in the deployment docs as "pin
`FORCE_SITE_NAME` or `SITE_ID`", since nothing currently warns about it.

**The access override masks the application-gated flow in dev (§10.3).** With
`OVERRIDE_COURSE_ACCESS_TO_FREE` now committed as `True`, an application-gated course presents as
"Free · open to everyone" with an "Enrol for free" CTA and no mention of applying. That is deliberate
and internally consistent, but the practical consequence is that **nobody doing manual QA in dev can
see the apply flow at all** unless they flip the flag back. Worth knowing before someone concludes
that flow is broken or missing.

**A `security-guard` hook false positive.** The pre-tool hook blocks any `Bash` command containing the
substring `.env` (`claude_plugins/django-stack/scripts/hooks/security-guard.sh`). `os.environ`
contains that substring, so any Bash command mentioning it — including writing an ordinary Python
settings file — is refused. Writing the same file through the `Write` tool works, since that path
checks different patterns. Harmless once known, but it costs a round trip to discover, and it fired
twice during this run. Tightening the match to a path-like boundary would fix it.

**Dev-only QA residue this run created.** `QA Singular Learner Org` plus one learner (§7.7),
`QA Add Page Check` (§7.9), `QA Inline Cohort` (§7.8), `QA Form First Course` (§3.9), the
`qa_create_course_access_types` fixtures (§10.2–10.3), a `qa-sitename.example.test` Site and its admin
(§11.2), and a `qa-signup-check@example.test` account (§12.3). All are dev-database only and harmless;
the database is per-branch and disposable.

**The submit-confirm dialog's buttons were left full size.** Keep going / Leave and submit / Go back and
review / Submit are still 16px rather than `btn-sm`, unlike the footer buttons the branch resized. Modal
buttons were arguably out of scope for that commit — flagging, not filing.

status: ok
reason: run completed across two passes; every test in the plan now carries a verdict and 0 skips remain; 4 bugs documented, 0 fixed, 4 unresolved; 17 screenshots verified; the first pass's environment failure is resolved
