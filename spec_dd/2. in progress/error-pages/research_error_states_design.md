# Research: what "Error States.html" actually contains, and how much FLS can honestly build

Design source (outside the repo, read in full): `/home/sheena/workspace/lms/designs/Learner experience/Error States.html`,
`styles-errors.css`, `design-system/colors_and_type.css`, `design-system/kit.css`. One extra file,
`design-system/styles.css`, was spot-checked (grep only) to resolve two classes (`.fc-mini-btn`,
`.fc-section-header`) that `styles-errors.css` uses but that live outside the four files named in the
brief — flagged inline below wherever used.

The gallery is a static, non-interactive HTML mockup titled "First Class" (the design tool's placeholder
product name — not an FLS name). It has 4 sections: `01 Full-page states`, `02 In-context failures`,
`03 Toasts & global banners`, `04 Coverage` (a summary table, reproduced faithfully in §1 below — it is
not new information, just cross-checked against the markup). The file is 380 lines total; there is
nothing past line 200 that wasn't captured — §1 covers every state in the file.

---

## 1. Inventory of every state drawn

Legend tags in the design's masthead (`Error States.html:19-24`): `err`=blocking, `warn`=recoverable,
`info`=informational, untagged=auto-retry. Copy is quoted verbatim from the HTML.

### 1.1 Full-page states (section 01 — rendered inside the mock app shell: topbar + centred panel)

| # | HTTP/state | Tag | Heading | Body copy (verbatim) | Icon (`ph-*`) | Mark colour | Primary action | Secondary/other actions | Supporting elements |
|---|---|---|---|---|---|---|---|---|---|
| 404 | 404 | — (neutral) | "We can't find that page" | "The link may be out of date, or the lesson may have moved to a different module. Nothing has been removed from your enrolment." | `ph-magnifying-glass` | `.ex-mark.neutral` | "Back to dashboard" (`ph-house`) | "Search courses" (`ph-magnifying-glass`) | `.ex-meta`: path `/courses/cpl-ground/module-4/4.2` · "Report a broken link" link |
| 500 | 500 | err | "Something went wrong on our end" | "This isn't your connection or your account. The failure has been logged and the team has been paged." | `ph-warning` | `.ex-mark.err` | "Try again" (`ph-arrow-clockwise`) | "Back to dashboard" (ghost) | `.ex-progressbar` (green check-circle): "Your progress is saved through **Module 4 · Section 4.1**. Nothing you completed today has been lost."; `.ex-meta`: "Reference FC-5X-9K2QD7" · "Contact support" · "status.firstclass.io" |
| 403 | 403 | err | "You don't have access to this course" | "Your account isn't enrolled in **Commercial Pilot Ground School**. If this looks wrong, your programme administrator can check your enrolment." | `ph-lock-key` | `.ex-mark.warn` | "View my courses" | "Request access" | `.ex-meta`: "Signed in as a.reyes@skypath.edu" |
| 401 | 401 | warn | "You've been signed out" | "For security, sessions end after 30 minutes of inactivity. Sign back in and you'll return to where you stopped." | `ph-clock-countdown` | `.ex-mark.info` | "Sign in again" (`ph-sign-in`) | — | `.ex-detail`: "Return to" → "Module 4 · Section 4.2"; "Unsaved notes" → "3 drafts kept locally" |
| 429 | 429 | warn | "Slow down for a moment" | "We've received an unusual number of requests from your account. Access unlocks automatically — no action needed." | `ph-gauge` | `.ex-mark.warn` | "Waiting…" button, **disabled**, spinning `ph-arrow-clockwise` (`ex-spin`) | — | `.ex-countdown`: "00:47" / "Retrying automatically"; `.ex-meta`: "Limit 120 requests / minute" · "Why did this happen?" |
| 503 | 503 | info | "First Class is down for maintenance" | "We're shipping an update to the exam engine. Course deadlines that fall inside this window have been pushed by 24 hours." | `ph-wrench` | `.ex-mark.info` | "Live status" (`ph-activity`, secondary) | — | `.ex-detail`: "Window" → "02:00 – 04:00 UTC"; "Expected back" → "in 38 minutes" |
| 504 | 504 | warn | "This is taking longer than it should" | "The page didn't load in time. It usually works on a second attempt." | `ph-hourglass-high` | `.ex-mark.warn` | "Reload page" (`ph-arrow-clockwise`) | "Back to dashboard" (ghost) | `.ex-meta`: "Timed out after 30s" · "Reference FC-504-TT41A" |
| — | offline | untagged | "We can't reach First Class" | "Check your Wi-Fi or mobile data. Anything you downloaded is still available, and quiz answers you submit offline are queued." | `ph-cloud-slash` | `.ex-mark.neutral` | "Try again" (`ph-arrow-clockwise`) | "Downloads (4)" (`ph-download-simple`) | `.ex-offline-strip` (dark bar above body): `ph-wifi-slash` "You're offline — progress will sync when you reconnect" + "Retry now" button; avatar tinted `--grey-400`, logo greyscale/faded; `.ex-meta`: "2 items waiting to sync" |
| 410 | 410 | untagged | "This course has been retired" | "**Meteorology for Pilots (2021 syllabus)** was withdrawn in June 2026. A replacement covering the current syllabus is available, and your completed modules carry over." | `ph-archive` | `.ex-mark.neutral` | "Open the 2026 edition" | — | `.ex-meta`: "Certificate from the old course stays valid" |
| 402 | 402 | err | "Your card was declined" | "Your bank turned down the charge for **ATPL Theory · annual**. You haven't been charged, and your seat is held for 7 days." | `ph-credit-card` | `.ex-mark.err` | "Update payment method" | "Contact billing" (ghost) | `.ex-detail`: "Card" → "•••• 4429"; "Reason given" → "insufficient_funds" |

Every full-page frame also renders: a fixed 56px topbar (`.ex-topbar`) with logo, nav (`Dashboard / My
courses / Catalog` — omitted on some frames), a bell icon and an avatar/initials chip; centred
`.ex-panel` max-width 520px; and, where present, an `.ex-meta` strip separated by a top border.

### 1.2 In-context failures (section 02 — rendered inside the lesson, no app-shell chrome)

| Name | Tag | Heading/lead | Body copy (verbatim) | Icon | Primary action(s) | Supporting elements |
|---|---|---|---|---|---|---|
| Exam submission failed | critical | "We couldn't submit your exam" (`ph-fill ph-warning-octagon`, `.ex-ia-err`) | "All 40 answers are saved on this device and time is paused at **12:04 remaining**. We'll keep retrying in the background. Don't close this tab." | `ph-warning-octagon` (fill) | "Retry submission" (`ph-arrow-clockwise`) | "Download my answers" (`ph-download-simple`, mini-btn), "Call the proctor" (`ph-lifebuoy`, mini-btn) | Below the alert, mono-font status line: `ph-arrow-clockwise` (spinning) "Attempt 3 of 5 · next retry in 8s · reference FC-EX-77B21" |
| Widget failed to load | partial | "This diagram didn't load" | "The rest of the lesson is unaffected. You can continue and come back to it." | `ph-plugs` | "Reload diagram" (mini-btn) | Shown inline under a lesson paragraph, in a dashed-border `.ex-block-fail` box |
| Video playback error | media | "This video won't play" | "MEDIA_ERR_SRC_NOT_SUPPORTED" (the body copy here is literally a media API error code, not prose) | `ph-video-camera-slash` (fill) | "Retry" | Dark 16:9 video frame (`.ex-video`) with a footer bar: "4.3 Reading the altimeter · 08:42" · "Transcript available" |
| Attempt limit reached (learner-facing 429) | 429 | "You've used all 3 quiz attempts" | "Your next attempt unlocks in **11 h 24 m**. Your best score so far — 72% — is what counts toward the module." | `ph-hourglass` (fill), `.ex-ia-warn` | "Review the material" (`ph-book-open`, mini), "Ask your instructor" (`ph-chat-circle`, mini) | Inline alert, no countdown widget (plain text duration) |
| Autosave failed | recoverable | "Changes not saved since 14:02" | "We'll keep trying. Your text stays in this tab until it saves." | `ph-cloud-warning` (fill), `.ex-ia-neutral` | "Save now" (`ph-arrow-clockwise`, mini), "Copy text" (`ph-copy`, mini) | Plain inline alert |
| Upload rejected | 413 | file row "nav-log-final.pdf" | "62 MB · limit is 25 MB"; field error: "Compress the file or split it into two uploads." | `ph-file-x` (fill, on file row icon), `ph-warning-circle` (fill, on field error) | "Remove" (mini) | `.ex-file-row` styled as an error row (red border/bg); `.ex-field-err` line below |
| Field validation | 422 | label "Licence number", input value "UK-2049-XX" | "This doesn't match the format UK-0000-0000." | `ph-warning-circle` (fill) | (implicit — fix the field) | `.ex-input-err` red-ring input + `.ex-field-err` message |
| List failed to load | fetch | "We couldn't load your courses" | "Your enrolments are safe — this is a display problem. Try again, or reload the page." | `ph-cloud-x` | "Retry" (mini, in the `.fc-section-header`) and "Try again" (secondary button, duplicated) | Rendered under a `.fc-section-header` ("My courses" / "Everything you're enrolled in") so the retry control sits at both the section-header level and inside the failure box |

### 1.3 Toasts & global banners (section 03)

Four toast variants, each `.ex-toast {err|warn|info|ok}`, all with a dismiss `×`:

| Variant | Icon | Title | Subtitle |
|---|---|---|---|
| err | `ph-warning-circle` (fill) | "Couldn't mark section complete" | "We'll retry automatically." |
| warn | `ph-wifi-slash` (fill) | "Connection lost" | "Working offline — 2 changes queued." |
| info | `ph-arrow-clockwise` (spinning) | "Reconnecting…" | "Attempt 2 of 5" |
| ok | `ph-check-circle` (fill) | "Back online" | "All progress synced." |

Design note in the section intro: "Toasts never carry the only copy of a recovery action" — i.e. every
toast's action must also exist somewhere durable (the design does not put a retry button in the toasts
above; it relies on this stated principle).

### 1.4 Section 04 "Coverage" table

`Error States.html:356-375` is the design author's own summary table (Code / State / Primary action /
Progress-safety line) — cross-checked against §1.1–1.2 above; no new states or copy beyond what's already
quoted. One discrepancy worth flagging for whoever designs FLS's version: the coverage table lists 413 and
422 as full "states" with a progress-safety line ("Other files untouched" / "Form values preserved") that
does not appear anywhere in the actual §02 markup for those two — the in-context frames for 413/422 have no
`.ex-progressbar` or safety copy, only the field-error text. The coverage table is aspirational/summary, not
a faithful index.

---

## 2. Capability audit

Checked against: `freedom_ls/base/templates/_base.html`, `_base_interface.html`,
`partials/header_bar.html`, `allauth/layouts/entrance.html`, `allauth/layouts/base.html`,
`cotton/` (all templates), `freedom_ls/deployment/sentry.py`, `freedom_ls/deployment/views.py`,
`config/urls.py`, plus targeted checks below.

**Baseline fact, checked first because it changes the shape of everything else**: `config/urls.py` defines
no `handler404`/`handler500`/`handler403`/`handler400`, and no `**/templates/{404,500,403,400}.html`
exists anywhere under `freedom_ls/` (only vendored copies inside `.venv/`). FLS currently serves Django's
bare built-in error responses for 404/500/403/400 — there is no existing branded error page to extend.
The **one** exception is `freedom_ls/accounts/templates/accounts/lockout.html`, served by django-axes for
login lockout, already extending `allauth/layouts/entrance.html`, already returning **429** (see
`freedom_ls/accounts/tests/test_lockout_page.py:40`) and already on-brand (`c-icon`, `c-button`). This is
the only precedent in the codebase for any of the states in §1.

Per-element classification:

### Buildable now (FLS already has the underlying capability)

- **404 "Back to dashboard"** — a home/dashboard URL exists (`learner_interface` catch-all + dashboard view).
- **403 "View my courses"** — same.
- **401 "Sign in again"** — allauth's `account_login` exists; "return to where you stopped" only for the
  *next-page* redirect, see below re: unsaved-notes claim.
- **403 "Request access"** — FLS has a real, if differently-named, capability here: `freedom_ls/course_interest/`
  (learner expresses interest in a course) and `freedom_ls/course_applications/` (learner applies to a
  course), both with models/views/urls already wired into `config/urls.py:65-66`. This is the one design
  action in the whole gallery that maps onto an *existing* FLS feature rather than an invented one — worth
  flagging as a genuine option rather than only unbuildable.
- **429 lockout page shape** — `accounts/lockout.html` already does a simplified version of the 429 state
  (heading, body, one primary action, one secondary link) and already returns HTTP 429. It doesn't have a
  countdown, rate figure, or "why did this happen" link.
- **Toasts (§1.3)** — FLS already has a complete toast system: `freedom_ls/base/templates/partials/_toast.html`
  and `partials/messages.html`, four severities (error/warning/success/info→ mapped from Django messages
  tags), OOB-swap support, ARIA live regions, dismiss button, `x-transition` animations. The four toast
  variants in the design (err/warn/info/ok) map 1:1 onto FLS's four existing severities. No new
  infrastructure needed — only new message copy and, for the "Reconnecting… Attempt 2 of 5" variant, a
  spinning icon treatment that isn't currently one of the four (see below).
- **Field validation (422) shape** — FLS already returns HTTP 422 for HTMX validation errors per
  `CLAUDE.md` convention ("Return HTTP 422 for HTMX validation errors"), and `partials/form.html` /
  `cotton/` likely already render field-level errors; the *visual* treatment (red ring input,
  `ph-warning-circle` message) is a straightforward CSS/markup change, not new functionality.
  (Not independently re-verified against `partials/form.html` internals in this pass — flagged so the
  designer checks the current field-error markup before assuming a from-scratch build.)
- **Callout/alert shell** — `cotton/callout.html` already implements the info/warning/error/success
  4-variant alert-box pattern the design's `.ex-inline-alert` / `.fc-alert` classes are doing by hand; this
  is a direct component match (see §5).
- **Buttons** — `cotton/button.html` already has `primary`/`secondary`(implicit via `btn-secondary` class
  convention)/`ghost`/accent-equivalent variants, icon-left/right slots, a loading state, and disabled
  handling — a near-total match for `.fc-btn-primary/-secondary/-ghost` plus the 429 disabled "Waiting…"
  button.

### Implies functionality FLS does not have

Named precisely, one per design element:

- **"Search courses" (404 secondary action)** — no course-search view exists anywhere under
  `freedom_ls/learner_interface/` (grepped; only unrelated hits like SEO/breadcrumb tests). Would need a
  new search feature, not just a page.
- **"Report a broken link" (404 meta link)** — no support/feedback/ticketing endpoint exists in the
  codebase (grepped `report.*broken`, `contact.?support`, `feedback` — zero hits in `freedom_ls/`), and no
  `SUPPORT_EMAIL`/`SUPPORT_URL` setting exists (grepped, zero hits). Even a `mailto:` link needs an address
  from somewhere; today there's no canonical one.
- **"Your progress is saved through Module 4 · Section 4.1" (500 progress-safety strip)** — FLS's content
  hierarchy is `Course → CoursePart → Topic → Activity` (`freedom_ls/content_engine/models/courses.py`,
  `topics.py`), not "Module/Section". More importantly: on an actual Django 500, the failing request is
  by definition in an unknown state — the view that would compute "which topic was the learner last on"
  may itself be what crashed, and `learner_progress` (the app that could answer this) may not be safely
  queryable if the 500 is a DB-connectivity failure. Django's own `handler500` contract deliberately keeps
  the 500 template as static/context-free as possible for exactly this reason. Asserting a *specific*
  save-point on the one page class that cannot promise it isn't broken is answered as dishonest below
  (§ blunt notes).
- **"Reference FC-5X-9K2QD7" / "Reference FC-504-TT41A" / "reference FC-EX-77B21" (support reference IDs)**
  — `freedom_ls/deployment/sentry.py` calls `sentry_sdk.init()` with no `before_send` hook and nowhere in
  the codebase is a Sentry event ID captured into the Django request/response for display. Sentry *does*
  generate an internal event ID for every captured exception, but FLS makes no attempt to surface it. This
  is buildable (`sentry_sdk.last_event_id()` inside a custom `handler500`) but does **not exist today** —
  it is new plumbing, not a copy change.
- **"status.firstclass.io" (500 meta link) / "Live status" (503 secondary action)** — no live status page
  exists or is referenced anywhere in FLS's settings/config.
- **429 countdown "00:47 / Retrying automatically" and "Limit 120 requests / minute"** — FLS's actual rate
  limiting (the only rate limiting found in the repo) is allauth's `ACCOUNT_RATE_LIMITS` for `login_failed`
  (`"10/m/ip,5/5m/key"`, `freedom_ls/accounts/tests/test_login_rate_limit.py:20`) and `signup`
  (`freedom_ls/accounts/tests/test_signup_rate_limit.py`), both enforced by allauth/django-axes in front of
  specific views, not a general per-request/per-account throttle behind every page. There is no evidence
  anywhere in the repo of a mechanism that would let a rendered page know *how many seconds remain* or
  *what the configured limit number is* at request time — that data would have to come from whatever
  layer (django-axes cache keys, a reverse-proxy, WAF) actually enforces the limit that triggered the page,
  and no such read-back exists today. A literal, ticking "00:47" countdown that isn't wired to the real
  cooldown is the auto-retry-countdown case the brief calls out as dishonest to fake.
- **503 "Course deadlines that fall inside this window have been pushed by 24 hours"** — no maintenance-mode
  / deadline-extension automation exists (`CohortDeadline`/`LearnerDeadline` models exist in
  `learner_management/models.py`, but nothing that auto-shifts them for a maintenance window). Also implies
  a **scheduled-maintenance banner/mode** with a start/end time and countdown ("in 38 minutes") — no such
  maintenance-mode toggle exists in `freedom_ls/deployment/`.
- **Offline state, entirely** — `.ex-offline-strip`, "downloaded lessons still play", "Downloads (4)",
  "quiz answers you submit offline are queued", "2 items waiting to sync" all imply a PWA/offline
  architecture: a service worker, a local content cache, an offline write queue, and a sync mechanism.
  Grepped the whole `freedom_ls/` tree for `service.?worker|manifest.json|offline` — no hits beyond two
  unrelated "legal docs manifest" files. FLS has **zero** offline infrastructure today; this entire state
  is unbuildable as designed, not just partially.
- **410 "your completed modules carry over" / "Certificate from the old course stays valid"** — no course
  retirement/supersession/certificate-migration feature exists in `content_engine` or `learner_progress`
  (not independently exhaustively verified for a certificates app, but nothing in the app list in
  `CLAUDE.md` names one, and no cross-course progress-carryover mechanism is referenced anywhere else in
  this research). This state asserts a data-migration guarantee FLS cannot make.
- **402 "Payment failed", entirely** — grepped the whole tree for `stripe|billing|payment` — the only hit
  is an unrelated PDF report test. FLS has **no payment/billing app, no card data, no seat-holding
  concept, no `insufficient_funds`-style decline reason, nothing**. This is not "missing a field" — the
  entire commercial/billing domain does not exist in FLS. 402 is the single least-buildable state in the
  gallery.
- **413 "62 MB · limit is 25 MB"** — plausible (file uploads presumably have a size limit somewhere in
  `form_engine`), but not independently verified in this pass which upload paths exist and what their
  actual limits are; the specific numbers in the mock are invented and must not be copied as real limits.
- **Exam submission failed: "answers are saved on this device", "time is paused", "we'll keep retrying in
  the background", "Attempt 3 of 5 · next retry in 8s"** — this implies a client-side local-storage answer
  cache, a client-driven exponential-backoff retry loop, and a server-side paused exam timer, none of which
  were found evidenced in `form_engine` in this pass. This is the single most functionally loaded
  in-context state in the gallery and the brief's own framing ("highest-stakes error in the product")
  makes it the worst candidate for a copy-only reskin — faked retry/pause claims here are actively harmful
  (a learner told their timer is paused when it isn't could run out of time for real).
- **"Call the proctor" (exam failure action)** — implies live proctoring/support contact; no such feature
  or contact channel found in the codebase.
- **Video "Transcript available"** — implies transcripts exist for video content; not verified as an
  existing content_engine capability in this pass.
- **List failed to load "Your enrolments are safe — this is a display problem"** — this is a claim about
  *why* the failure happened (display-layer, not data-layer) that the page cannot actually know unless the
  view distinguishes those failure modes itself; today's likely failure mode (an unhandled exception in the
  view) gives no such signal for free.

### Contradicts a constraint (request-context/DB-read problems specific to error pages)

- **500 page's progress-safety strip and reference ID both require exactly the kind of request-scoped,
  DB-backed lookups that are unsafe on the page Django serves *because* something already went wrong**.
  Django's `handler500` is deliberately called with a minimal/no-context request in many failure modes
  (e.g. `RequestContext` processors may not have run; a DB-down 500 must not itself try to hit the DB to
  render its own error page, or it 500s again while rendering the 500). Anything on this page that needs a
  `learner_progress` query (the "Module 4 · Section 4.1" line) or even just `request.user` resolved via a
  DB-backed auth backend is suspect and must be treated as "render with whatever is already on `request`,
  never re-query."
- **429/503 countdowns computed server-side and then "ticking" client-side without a real endpoint to
  re-check** — if the actual enforcement lives in a cache key or upstream proxy the app can't read back
  from, a countdown is cosmetic, not accurate, and will drift or misreport by the time it reaches zero.
- **403's "Signed in as a.reyes@skypath.edu"** is fine (that's just `request.user.email`, safe), but the
  **404/410's "programme administrator can check your enrolment"** implies a specific admin-contact routing
  (which administrator, for which cohort) that would need a real lookup (`Cohort`/`CohortMembership`) rather
  than being generic copy — cheap to make honest (say "an administrator" not a specific named path) but
  worth flagging as a copy trap.

---

## 3. Token translation table

Design tokens actually used by the error-state markup/CSS (not the whole design system — only what §1
uses), mapped onto FLS's role tokens in `freedom_ls/themes/default/static/themes/default/theme.css`. FLS
tokens are declared as Tailwind v4 `@theme` custom properties and consumed as both CSS vars and via
Tailwind utility classes (`bg-error`, `text-on-error-light`, etc.) — the CSS-variable names below are
identical in `default` and `first_class` (only their *values* differ; that's the point of the token layer,
and it's checked in the row-by-row diff after this table).

| Design token / class | Design value (from `colors_and_type.css` / `styles-errors.css`) | FLS role-token equivalent | Notes |
|---|---|---|---|
| `--fg-1` | `--grey-800` (headings) | `--color-on-surface` | Direct semantic match (high-emphasis text on a surface). |
| `--fg-2` | `--grey-600` (body) | `--color-muted` used loosely, but FLS has no dedicated "secondary body text" role distinct from `--color-muted` — closest is `--color-muted`, though FLS's `--color-muted` (`#4A5568` default / `#718096` first_class) is closer to design's `--fg-3` in *intent* (captions) than `--fg-2` (body-secondary). **No clean 1:1** — flag below. |
| `--fg-3` | `--grey-500` (metadata/captions) | `--color-muted` | Best fit — FLS's single "muted" role has to absorb both the design's `--fg-2` and `--fg-3` shades. |
| `--fg-4` | `--grey-400` (placeholder/disabled) | No FLS equivalent role token; would fall back to a raw Tailwind grey utility (`text-gray-400`) or a new `--color-muted-2`-style token. **Flag: no role-token equivalent.** |
| `--border` | `--grey-200` | `--color-border` | Direct match. |
| `--border-strong` | `--grey-300` | No FLS equivalent — `--color-border` is FLS's only border role. **Flag: no role-token equivalent** (used by `.ex-stage`, `.ex-block-fail`'s dashed border, `.ex-masthead`). |
| `--bg` (page bg) | `= --color-surface` (`#F8F9FC`) | `--color-surface` | Direct match — design's own alias already points at the same concept FLS names `surface`. |
| `--bg-elev` (`#FFFFFF`, cards/panels) | literal white | No exact FLS role — FLS's `--color-surface` *is* white in `default` (`#FFFFFF`) but is `#F8F9FC` in `first_class`; FLS's closest "elevated card on top of the page surface" role is `--color-surface-2` (`#F3F4F6` default / `#EDF2F7` first_class), which is *not* white either. **Flag: FLS has no "pure white card on a tinted page" role** — the design's frequent literal `#fff` (`.ex-detail`, `.ex-progressbar`, `.ex-block`, `.ex-field`, `.ex-upload`, `.ex-toast`) has no token, only a hardcoded colour, in both design and FLS. |
| `.ex-mark.err` → `background: var(--color-error-light); color: var(--color-error)` | — | `bg-error-light text-on-error-light` (FLS's *-light surfaces are paired with dedicated `--color-on-*-light` foregrounds, not the base `--color-error`) | **Do not copy the design's pairing literally** — FLS's own contrast-safe pairing is `-light` background with `-on-*-light` foreground, e.g. `text-on-error-light` (`#742A2A` default, same value first_class), not `text-error` on a `-light` background as the design does. FLS's `-light` values are numerically identical to the design's across both themes (all four `--color-*-light` hexes match `colors_and_type.css` exactly), so this pairing swap is low-risk. |
| `.ex-mark.warn` | `background: var(--color-warning-light); color: var(--color-warning)` | `bg-warning-light text-on-warning-light` | **Same fix, and more important here**: FLS `default` theme's `--color-warning` is `#F6E05E` (a pale yellow, chosen as a *background* colour, paired with a **dark** `--color-on-warning: #1A2332`) — using it as an icon foreground on a light background under `default` gives low-contrast pale-yellow-on-pale-yellow. `first_class`'s `--color-warning` is `#D69E2E` (a saturated amber, the design's actual source value) and reads fine as a foreground. **This is the clearest "design detail that looks wrong under `default`" in the whole audit** — the warning mark must use `text-on-warning-light`, not `text-warning`, to be theme-safe. |
| `.ex-mark.info` | `background: var(--color-info-light); color: var(--color-info)` | `bg-info-light text-on-info-light` | Same fix; `--color-info` (`#0EA5E9` default vs `#3182CE` first_class) both read fine as foregrounds, lower risk than warning, but use the `-on-*-light` pairing for consistency. |
| `.ex-mark.neutral` | `background: var(--grey-100); color: var(--fg-3)` | `bg-surface-2 text-muted` | Reasonable direct mapping. |
| `.ex-status` (uppercase mono status line) | `color: var(--fg-3); font-family: var(--font-mono)` | `text-muted font-mono` | `--font-mono` is FLS's `--fls-font-mono` alias — direct match, though FLS's mono stack (`ui-monospace, SFMono-Regular, Menlo…`) differs from the design's self-hosted "IBM Plex Mono" in `first_class` only — see typography note below. |
| `.fc-btn-primary` | `background: var(--color-primary); color: #fff` | `.btn.btn-primary` (via `cotton/button.html` → `variant="primary"`) | Direct match — FLS's button component already resolves `--color-primary`/`--color-on-primary` through its own CSS, not the design's hardcoded `#fff`, which is theme-safer than the design itself (FLS's `--color-on-primary` is always `#FFFFFF` in both shipped themes, but a future theme with a light primary wouldn't need a design update). |
| `.fc-btn-secondary` | `background: transparent; color: var(--color-primary); border-color: var(--color-primary)` | `.btn.btn-secondary` | Match, assuming FLS's secondary variant follows the same outline pattern (not independently re-verified in this pass — `cotton/button.html` only shows the `btn-{{variant}}` class hook, not the CSS itself). |
| `.fc-btn-ghost` | `background: transparent; color: var(--color-primary)` | `.btn.btn-ghost`(assumed) | Same caveat as above. |
| `.fc-mini-btn` (found in `design-system/styles.css:562-570`, **outside the 4 files specified** — flagged per the brief's note above) | `border: 1px solid var(--border); color: var(--fg-2)` | No direct FLS equivalent component; closest is a small/ghost variant of `cotton/button.html` (`size="small"`) or a new small-button treatment. **Flag: no existing FLS component for this specific chip-like small button** used throughout §1.2's in-context alerts. |
| `.ex-tag.err/.warn/.info` (small status pills in the frame labels — gallery chrome only, not shipped UI) | `background: var(--color-*-light); color: literal hex (#742A2A etc.); border: literal hex` | `.chip.chip-error/-warning/-info` (`cotton/chip.html`, not read in full this pass, but named in the base template glob) | These are the design gallery's own scaffolding (labelling each frame "404"/"blocking" etc.) — not part of the shipped error page. No action needed unless a "state" badge is wanted on the FLS page itself. |
| `--font-heading` (`"Outfit"`, first_class) / `--font-body` (`"DM Sans"`) | self-hosted webfonts, `colors_and_type.css:9-58` | `--fls-font-sans` / `--fls-font-display` | FLS's `first_class` theme (`freedom_ls/themes/first_class/static/themes/first_class/theme.css:81-86`) already sets exactly these families (`"DM Sans"` sans, `"Outfit"` display, `"IBM Plex Mono"` mono) — **the design's typography is already fully represented as first_class theme tokens**; nothing to translate here, it's already 1:1. `default` theme uses system-ui sans-serif throughout (`theme.css:124-128`) — headings will look generic/system-font under `default`, which is expected and correct (the whole point of the token layer). |
| `--shadow-sm/-lg` | `colors_and_type.css:143-146` | No FLS `--shadow-*` role tokens found in `theme.css` (grepped only the two theme files fully read; FLS likely uses raw Tailwind `shadow-sm`/`shadow-lg` utilities rather than a themed shadow token) | **Flag: unverified** whether FLS has themed shadow tokens — only the two `theme.css` files were read in full, and neither declares a `--shadow-*` custom property, meaning FLS shadows (if used) are plain Tailwind defaults, not brand-tunable. Not a blocker, just note it isn't a themed value. |
| `--radius` / `--radius-lg` | `8px` / `12px` | `--fls-radius-md` / `--fls-radius-lg` | Direct conceptual match, but **values differ from the design in `default`**: FLS `default` radii are `0.375rem`(6px)/`0.5rem`(8px) — notably smaller/squarer than the design's `8px`/`12px`. `first_class` radii (`0.5rem`/`0.75rem` = 8px/12px) match the design almost exactly (`theme.css` first_class:76-78). This is a second concrete "looks different under default" — panels/cards will read tighter-cornered under `default` than the mockup shows. |

### Colours with NO role-token equivalent (real decisions for the idea to make)

1. **`--fg-4` / `--grey-400`-style "disabled/placeholder" tier** — FLS's palette collapses this into
   `--color-muted`, losing the design's 4-step foreground hierarchy (`fg-1`…`fg-4`) down to effectively 2
   usable tiers (`on-surface`, `muted`). Meta-line text (`.ex-meta`, timestamps, reference codes) will need
   to pick one of FLS's two tiers rather than get its own faint fourth tier.
2. **`--border-strong`** — used for the outer frame (`.ex-stage`) and dashed empty-state borders
   (`.ex-block-fail`). FLS has one border role. A stronger border for card containers vs. field borders is
   not distinguishable via tokens today.
3. **Literal white (`#fff`) "elevated card on a tinted page" surface** — both the design and FLS lack a
   named token for this; the design just hardcodes `#fff`, FLS would have to do the same (or accept
   `--color-surface-2`, which is *not* white and changes the intended "card lifts off the page" effect,
   especially under `first_class` where the page surface is already off-white `#F8F9FC`).
4. **The `first_class` course-accent gradient palette** (`--fls-course-accent-*`) has no counterpart need
   in the error-state design and is irrelevant here — noted only to confirm it was checked and correctly
   excluded.

---

## 4. Icons

The design is built on the **Phosphor** icon font, loaded directly via CDN
(`Error States.html:7-8`, `@import` in `kit.css:6-8`) — literal `ph`/`ph-fill` classes, not semantic
names.

Phosphor icon names used across §1 (deduplicated): `ph-magnifying-glass`, `ph-house`, `ph-bell`,
`ph-warning`, `ph-arrow-clockwise`, `ph-check-circle` (fill), `ph-lock-key`, `ph-clock-countdown`,
`ph-sign-in`, `ph-gauge`, `ph-wrench`, `ph-activity`, `ph-hourglass-high`, `ph-cloud-slash`,
`ph-download-simple`, `ph-wifi-slash` (fill), `ph-archive`, `ph-credit-card`, `ph-warning-octagon` (fill),
`ph-lifebuoy`, `ph-plugs`, `ph-video-camera-slash` (fill), `ph-hourglass` (fill), `ph-book-open`,
`ph-chat-circle`, `ph-cloud-warning` (fill), `ph-copy`, `ph-file-x` (fill), `ph-warning-circle` (fill),
`ph-trash`, `ph-cloud-x`, `ph-user`, `ph-x`.

**FLS does not ship or use Phosphor at all.** `freedom_ls/icons/config.py:13` defaults
`FREEDOM_LS_ICON_SET = "heroicons"`; the icon system (`freedom_ls/icons/mappings.py`) supports four
backends (`heroicons`, `lucide`, `tabler`, `phosphor` — Phosphor *is* one of the four supported backends,
mapping table at `mappings.py:148-192`), but all are addressed only through **semantic names**
(`freedom_ls/icons/semantic_names.py`, `SEMANTIC_ICON_NAMES`), never literal icon-set class names — per
`claude_plugins/fls-dev/skills/icon-usage/SKILL.md`: "Never use raw Font Awesome classes... or
hand-coded" (and by the same logic, never raw `ph-*` classes either, even though Phosphor is a supported
backend — the contract is semantic names via `<c-icon name="..." />`, always).

Mapping design icon → closest existing FLS semantic name (from `SEMANTIC_ICON_NAMES`,
`semantic_names.py:1-53`):

| Design icon (Phosphor) | Existing FLS semantic name | Fit |
|---|---|---|
| `ph-warning`, `ph-warning-octagon`, `ph-warning-circle` | `"warning"` | Good — direct status match |
| `ph-check-circle`, `ph-arrow-clockwise` (as a completion glyph) | `"success"` / `"complete"` | Good |
| `ph-lock-key` | `"locked"` | Good |
| `ph-arrow-clockwise` (retry contexts) | `"retry"` | Good — exact semantic match already exists |
| `ph-download-simple` | `"download"` | Good |
| `ph-house` | `"home"` | Good |
| `ph-x`, `ph-trash` (dismiss/remove) | `"close"` | Partial — `"close"` fits dismiss; there is no `"remove"`/`"delete"` semantic name for the upload-row trash icon |
| `ph-user` | `"user"` | Good |
| `ph-bell` | `"notifications"` | Good |
| `ph-info` (implied by `.ex-mark.info`, not literally in the icon list but same family) | `"info"` | Good |
| `ph-cloud-x`, `ph-cloud-slash`, `ph-cloud-warning`, `ph-wifi-slash`, `ph-plugs`, `ph-video-camera-slash` | **none** | **Missing** — no offline/connectivity/media-failure family exists in `SEMANTIC_ICON_NAMES` at all |
| `ph-hourglass`, `ph-hourglass-high`, `ph-clock-countdown` | `"deadline"` (uses a plain clock glyph, not an hourglass/countdown) | Partial — conveys "time-related" but not the countdown/waiting connotation |
| `ph-gauge` (rate-limit gauge) | **none** | Missing — no rate-limit/throttle icon concept |
| `ph-magnifying-glass` (search) | **none** | Missing — no "search" semantic name exists |
| `ph-wrench` (maintenance) | `"settings"` (gear, not wrench) | Weak — different connotation (config vs. maintenance/repair) |
| `ph-credit-card` | **none** | Missing — no payment/billing icon concept (consistent with §2's finding that billing doesn't exist as a domain at all) |
| `ph-archive` (retired course) | **none** | Missing |
| `ph-sign-in` | **none** (`"user"` is the closest, but not a sign-in-specific glyph) | Missing |
| `ph-activity` (status page link) | **none** | Missing |
| `ph-lifebuoy` (call the proctor) | **none** | Missing |
| `ph-book-open` | `"topic"` (already maps to `book-open` in every backend, `mappings.py:35` etc.) | Good — coincidentally exact |
| `ph-chat-circle` | **none** | Missing |
| `ph-copy` | **none** | Missing |
| `ph-file-x` | **none** (`"boolean_false"` uses an X but is a data-display icon, wrong context) | Missing, no good fallback |

Net: of the ~29 distinct Phosphor icons the design uses, roughly 10 have a good-to-partial existing
semantic-name match; **the remaining ~19, including the entire offline/connectivity family, the rate-limit
gauge, billing, maintenance/wrench, and several action icons (copy, chat, lifebuoy, sign-in, search,
archive), have no existing FLS semantic name and would need new entries added to
`SEMANTIC_ICON_NAMES`/`mappings.py`** (one new dict key per icon set, per the pattern already in
`mappings.py`) before the error pages could use `<c-icon />` for them. Building error pages "from what FLS
already has" therefore either means accepting close-but-imperfect substitutions from the existing 52-name
set, or extending the icon system — a small, well-precedented change, but a real one, not zero-effort.

---

## 5. Layout and shell

The design renders every full-page state inside: a 56px topbar (logo + nav + bell + avatar) →
a centred, vertically-centred content well → a max-520px text column (`.ex-panel`) → optional
detail/progress/countdown block → action row → meta footer, all inside a bordered, rounded, drop-shadowed
"device frame" (`.ex-stage`) that is gallery-only chrome (not part of the shipped page — it exists so the
static HTML file can show many states side-by-side).

FLS shell comparison:

- **`_base.html`** (`freedom_ls/base/templates/_base.html:70-88`) already provides the outer shell: a
  `{% block header %}` defaulting to `partials/header_bar.html` (logo, title, nav slot via
  `header_bar_user_menu.html`/`login_prompt.html`), a messages/toast include, and a `<main>` with
  `{% block content %}`. This is the direct FLS equivalent of the design's `.ex-topbar` — already themed
  (`--color-header`, `--color-on-header` roles, differing between `default` and `first_class` per
  `theme.css`), already responsive, already has the bell/avatar-equivalent user menu. **No new topbar
  needed** — extending `_base.html` (not `_base_interface.html`, since error pages have no course sidebar)
  gives the design's shell for free.
- **`_base_interface.html`** is the *course-player* shell (sidebar + breadcrumbs + page-title header,
  `_base_interface.html:1-116`) — this is heavier than what any error state needs (no error state in the
  design shows a lesson sidebar) and is the wrong base for full-page error states. It **is** arguably the
  right shell for the §1.2 in-context failures, since those render *inside* an existing lesson page that
  already uses this shell — but that's a statement about where the failure is inserted, not about building
  new shell.
- **`allauth/layouts/entrance.html`** (extends `allauth/layouts/base.html` → `_base.html`) is a narrower,
  centred, `max-w-2xl` column with vertical padding (`entrance.html:4`) — this is close to the design's
  `.ex-body`/`.ex-panel` centring pattern and is **already the shell the one existing precedent
  (`accounts/lockout.html`) uses**. It's a good candidate for the unauthenticated-adjacent states (401, 429,
  403) but is narrower (`max-w-2xl` ≈ 672px) than the design's panel (`max-w-520px` content but a wider
  `.ex-stage` frame) — actually roomier, not tighter, so no problem.
- **`cotton/page.html`** (`freedom_ls/base/templates/cotton/page.html`) is the general content-well
  wrapper (`width="wide"|"narrow"`, `flush`) used inside `_base.html`-derived pages generally — a
  `width="narrow"` page is the natural container for a centred error panel, playing the same role as the
  design's `.ex-panel` sizing, though it's a block-level max-width wrapper, not a flex-centred column, so
  vertical centring (`.ex-body { align-items:center; justify-content:center }`) would need to be added
  around it, not assumed to come from `c-page` itself.
- **`cotton/callout.html`** maps directly onto the design's inline alert pattern (`.ex-inline-alert`,
  `.fc-alert-*`) used throughout §1.2 — same four-level severity contract (info/warning/error/success),
  same "icon + heading + body" shape (`callout.html:8-18`). It does **not** currently support an actions
  row (`.acts` in the design, e.g. "Retry submission" + "Download my answers" + "Call the proctor") — the
  component's slot is a single content block, so an actions row would be new markup inside the slot, not a
  missing feature of the component itself.
- **`cotton/button.html`** maps onto `.fc-btn-*` per §3 above — variant/icon/loading/disabled all already
  supported.
- **A "status mark" component** (`.ex-mark` — the circular icon badge with a coloured ring at the top of
  every full-page panel) has **no existing FLS cotton component**. The closest existing primitive is
  `<c-icon />` at a large size (the skill's own sizing guide names `size-16` as "hero (success/error result
  pages)", `icon-usage/SKILL.md:93` — i.e. the skill already anticipates this exact use case), but the
  circular coloured-background ring treatment itself would be new markup, not a wrapped existing component.

**Summary**: FLS's shell (`_base.html` + `header_bar.html`) already gives the topbar-plus-centred-panel
shape the design wants, and `entrance.html` already gives a working precedent narrower panel with exactly
one shipped example (`lockout.html`). `cotton/callout.html` and `cotton/button.html` cover the alert-box
and action-button pieces respectively. The only genuinely new *component* (as opposed to new *page*) the
gallery implies is the circular status-mark badge, which is a small wrapper around the existing
`<c-icon size-16 />` pattern rather than a structural gap.

---

## Blunt notes (per the brief's instruction to call out unbuildable/dishonest elements explicitly)

- The 500 page's "Your progress is saved through Module 4 · Section 4.1" is the single worst element to
  copy literally: it is prose on the one page in the entire gallery that Django's own error-handling
  contract says should assume the least about what's safely queryable, asserting a specific, checkable
  fact it cannot verify at render time.
- The 429 "00:47" ticking countdown and "Limit 120 requests / minute" figure are cosmetic unless wired to
  FLS's actual rate-limit enforcement (today: allauth/django-axes keys, not exposed to any view) — a fake
  countdown that doesn't match when the limit will actually lift is worse than no countdown.
- The exam-submission-failure state's "time is paused at 12:04 remaining" and "we'll keep retrying in the
  background" are safety claims about a live exam timer and an unverified retry loop — the brief's own tag
  for this state ("critical", "highest-stakes error in the product") makes faking either claim actively
  dangerous rather than merely inaccurate.
- Every reference code (`FC-5X-9K2QD7`, `FC-504-TT41A`, `FC-EX-77B21`) is invented by the design tool and
  corresponds to nothing FLS currently generates or stores — treat as "this concept could exist" copy, not
  as literal strings, and don't ship a reference-ID field that isn't wired to anything.
- 402 (payment) and the offline state are not "missing a detail" — they assume entire subsystems (billing,
  PWA/offline sync) that do not exist in FLS in any form. Building "good-looking versions of these two
  specifically" without implementing anything real underneath them is the two states where "good-looking
  page, not the functionality" is hardest to pull off honestly, because almost every line of copy in them
  references that missing functionality directly.

status: ok
