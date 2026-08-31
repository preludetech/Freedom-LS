# Research: FLS's user-facing surface, and how it maps onto `docs/product/`

Topic: what a browser-driving QA agent can actually reach, and whether "one plan per
`docs/product/` document area" is a carve-up that survives contact with the codebase.

---

## 1. The product-doc areas, and what each one earns

**Headline: of the 13 non-index docs, 4 are cleanly page-driven and deserve a full browser QA
plan as-is (Authentication, Learner Experience, Educator Interface, Admin Interface). 3 more have
a real but narrow browser surface and would need a thinner or differently-shaped plan (Cohort
Reports, Webhooks, Deployment). 5 have no distinct page surface of their own and would produce an
empty or content-free plan if forced into this carve-up (Learner Tracking, Multi-Tenancy and
Isolation, Content Editing Workflow, Configuration and Extension, Security and Data Handling).
Roadmap is the exclusion index, not a candidate at all.** That is **7 plans with real content, at
most**, against thirteen doc files — the literal "one plan per doc" carve-up does not survive
first contact.

| Area | Covers | Browser-testable? | Verdict |
|---|---|---|---|
| `authentication.md` | Email login/signup/verification, password reset, profile, legal consent | Yes — full page flows | **Earns a plan.** Gated by the email-verification problem — see §3. |
| `learner-experience.md` | Dashboard, catalogue, course detail, player, forms, quizzes, deadlines, applying, coming-soon/hidden | Yes — the largest page surface in FLS | **Earns a plan.** The obvious spine of the whole suite. |
| `learner-tracking.md` | What gets recorded (per-topic, per-attempt, per-course progress) | No distinct pages — it is data shown *inside* the Learner Experience and Educator Interface pages | **No standalone plan.** Verify it as assertions inside those two plans (e.g. "progress percentage updates after completing an item"), not a third plan with nothing of its own to click. |
| `educator-interface.md` | Single-page HTMX panel: Cohorts, Learners, Courses, progress matrix | Yes | **Earns a plan.** Also the plan that walks straight into the known authorisation defect — see below. |
| `reports.md` | Per-cohort PDF, generated from admin, downloaded via permission-checked link | Partially — trigger and download are browser actions; *content* verification is not (PDF, see §3) | **Earns a thinner plan**: assert the admin flow (pick cohort → generate → poll status → download link appears → response is a PDF) rather than assert what is printed on the page. |
| `admin-interface.md` | Django admin (Unfold), org management, cohort permission grants, consent records, webhook test-send | Yes — Django admin is itself a navigable, clickable UI | **Earns a plan.** Distinct from Educator Interface: different login population (staff), different section list. |
| `webhooks.md` | Outbound HTTP events, HMAC signing, admin-configured endpoints, test-send | Partially — endpoint CRUD and the test-send button are in-browser; actual delivery is outbound HTTP to a third party FLS does not control | **Earns a thinner plan**: configure an endpoint pointed at a controllable receiver (or assert the test-send admin action returns a success/failure state), not "prove a webhook was received" without a receiver. |
| `multi-tenancy-and-isolation.md` | Site-scoped query isolation; organisations as a non-isolating grouping layer | Not as its own page walk — it is a cross-cutting guarantee tested by comparing behaviour across hosts, not a set of URLs | **No standalone plan** in the ordinary sense. See §4 for the honest fallback. |
| `content-editing-workflow.md` | Git+Markdown authoring, `content_save`/`content_validate` CLI, rendering pipeline | No — explicitly "no browser-based content editor," all authoring is files + CLI | **Earns nothing from a browser QA suite.** The one browser-visible effect (rendered Markdown, widgets) is already covered by walking course pages under Learner Experience. |
| `configuration-and-extension.md` | Branding settings, theming tiers, pluggable access backend, conformance suite | No dedicated pages — it is settings, verified today by the (pytest, not browser) conformance suite | **Earns nothing from a browser QA suite** as a standalone plan; individual settings surface indirectly (e.g. active theme's CSS, which icon set renders) inside other plans. |
| `deployment.md` | VPS/Compose architecture, `db_worker`, object storage, health probes, Sentry | Almost entirely infrastructure — but `/health/liveness/`, `/health/readiness/`, and a staff-only `/sentry-debug/` endpoint (`freedom_ls/deployment/urls.py:8`, `freedom_ls/deployment/views.py`) are real URLs | **Earns a very thin plan**: hit the two health endpoints and confirm the expected status codes. Everything else in this doc (Gunicorn workers, backups, VPS) is unreachable from a browser by definition. |
| `security-and-data-handling.md` | Cross-cutting reviewer doc: CSRF, sanitisation, encryption, the educator-interface defect, media access, retention gaps | No dedicated pages — its one concretely browser-provable claim (the Courses authorisation gap) is a probe *inside* the Educator Interface plan | **No standalone plan.** Its claims are assertions layered onto other plans (e.g. "an authenticated non-educator can still read the Courses list" belongs in the Educator Interface plan), not a page walk of its own. |
| `roadmap.md` | Index of unbuilt/half-built features | N/A — it is the "do not test this" list | **Not a plan candidate.** It is the exclusion filter every other plan must consult. |

### What a QA plan must *not* test (per `roadmap.md`)

- MFA/2FA — no code in any form.
- Course application **review/approval** — applying works; there is no reviewer screen, no
  approve/reject, no withdraw. The status page is static.
- **Notify-on-launch** for coming-soon courses, and **auto-enrolment on launch** — neither exists.
- **Messaging** — educators cannot contact learners from FLS at all.
- **xAPI** — a non-functional stub; the app isn't installed.
- **Site-aware user groups** — drafted, commented out.
- **RBAC as an access-control authority** — the role system (`freedom_ls/role_based_permissions/`)
  exists and is migrated, but it does not decide access; per-object guardian permissions do. Do
  not test "assign the instructor role and confirm cohort access appears" as if the role itself
  grants anything.
- **Per-request media access control** — signed URLs are private-by-default but not re-checked
  per learner per request; do not test "revoke access, confirm the old signed link now 404s."
- **Certificates** — course completion has a finish page, no certificate.
- **Cohort report scheduling, emailing, retention/expiry, or a shareable link** — none exist; only
  on-demand admin generation and a permission-checked download.
- **CSP enforcement** — it is report-only; a QA agent will not see anything actually blocked.

### The known educator-interface authorisation defect

`docs/product/README.md:11` and `docs/product/educator-interface.md#access-control` both call this
out explicitly: **the Courses section of the educator interface has no permission filter at all.**
Any authenticated user on the site can list every course (hidden ones included) and open any
course detail page inside `/educator/organisations/<slug>/...`. Cohort and Learner sections *are*
now permission-checked (deny-by-default, "not found" for unauthorised access — see
`docs/product/security-and-data-handling.md:34-46`). A QA plan that walks the educator Courses
list with a low-privilege educator account will observe this — **this is expected, documented
behaviour to assert, not a bug the QA suite should raise as a new finding.**

---

## 2. The real URL surface

Routing root: `config/urls.py`. Grouped inventory (route name → what it renders → who can reach it
→ doc area):

| Route group | Names (app_name:name) | Renders | Reachable by | Doc area |
|---|---|---|---|---|
| Dashboard/catalogue | `learner_interface:dashboard`, `:courses`, `:course_detail` | Home `/`, all-courses list, public course detail | Anonymous, Learner | learner-experience |
| Course access & player | `learner_interface:initiate_course_access`, `:course_home`, `:view_course_item`, `:form_start`, `:form_fill_page`, `:course_form_complete`, `:form_submit_and_exit`, `:course_finish` | Enrol/apply redirect, player, form/quiz fill, finish page | Learner (registered) | learner-experience, learner-tracking (progress shown here) |
| Applications | `course_applications:apply`, `:status` | Apply confirmation, static status page | Learner | learner-experience (roadmap: no review workflow) |
| Course interest | `course_interest:express_interest`, `:remove_interest` | HTMX partials toggling "I'm interested" | Learner, on coming-soon courses | learner-experience |
| Accounts (FLS-owned) | `accounts:account_profile`, `:legal_doc`, `:complete_registration` | Profile edit, terms/privacy doc view, additional-registration-forms gate | Learner (authenticated, and mid-signup) | authentication |
| Accounts (allauth) | `allauth.urls` under `/accounts/` — not enumerated per instructions | Login, signup, logout, password reset/change, email verification/management | Anonymous → Learner | authentication |
| Educator panel | `educator_interface:root`, `:interface` (catch-all `path_string` under `/educator/organisations/<slug>/...`) | Cohorts/Learners/Courses sections, cohort detail incl. progress matrix, org switcher | Authenticated user (Courses unfiltered — see §1); Educator with grants (Cohorts/Learners) | educator-interface |
| Django admin | mounted at `DJANGO_ADMIN_URL` env var, default `admin/` (`config/urls.py:31,47`) | Full Django/Unfold admin: users, orgs, cohorts, reports, webhooks, consent | Staff/superuser | admin-interface (+ reports, webhooks as sub-surfaces) |
| Health | `health:liveness`, `health:readiness` under `/health/` | JSON status | Anonymous (unauthenticated, no-config) | deployment |
| Deployment/ops | `deployment:trigger_error` (`/sentry-debug/`) | Deliberate `ZeroDivisionError` to prove Sentry wiring | Staff only (`@staff_member_required`) | deployment |
| Sitemap/robots | `sitemap` (`sitemap.xml`), `robots_txt` | XML sitemap, robots.txt | Anonymous | learner-experience (discoverability) |
| Dev-only | `qa_helpers:toasts_*`, `__reload__/`, debug-toolbar URLs | Toast-widget playground, browser auto-reload, debug toolbar | Anonymous, **DEBUG-only** (`config/urls.py:71-81`) | none — not present on staging/prod at all |

Not enumerated (per instructions), but present and load-bearing for authentication: allauth's
login, signup, logout, password-change, password-reset (request + confirm), and email-management
flows, all mounted at `path("accounts/", include("allauth.urls"))` alongside FLS's own
`accounts.urls` at the same prefix.

### Gaps in both directions

**Routes with no product-doc area:**
- `deployment:trigger_error` (`/sentry-debug/`) — an ops/observability probe, not a product
  feature; belongs to nothing in `docs/product/` except by association with `deployment.md`'s
  Sentry paragraph.
- `qa_helpers:*` toast playground — explicitly marked `# QA-TEMP` in
  `freedom_ls/qa_helpers/urls.py:1`, DEBUG-only, and about to be removed per its own comment. Not
  a product surface at all; do not spec a plan around it.
- `django_browser_reload` and debug-toolbar URLs — dev tooling, no product meaning.

**Product-doc areas with no distinct routes:** `learner-tracking.md`, `multi-tenancy-and-isolation.md`,
`content-editing-workflow.md`, `configuration-and-extension.md`, `security-and-data-handling.md`,
`roadmap.md` — six of thirteen, matching the count in §1. This is where a literal "one plan per
doc" carve-up produces either an empty plan or a plan that duplicates assertions already made
elsewhere.

---

## 3. Surfaces that are not pages

**Headline: three of these five non-page surfaces (Django admin actions, cohort-report PDFs, and
background tasks) are the sharpest traps in a "runnable against staging" QA suite, because the
worker process and email delivery are both things a staging box may simply not have running, and
a browser cannot inspect PDF bytes at all.**

### Django admin surfaces

13 apps register `admin.py` (`grep -l` result): `learner_progress`, `content_engine`,
`organisations`, `form_engine`, `learner_management`, `course_interest`, `reports`, `webhooks`,
`site_aware_models`, `accounts`, `educator_interface`, `app_authentication`, `xapi_learning_record_store`.
The admin is mounted at `DJANGO_ADMIN_URL` (`config/urls.py:31`) — a QA plan must read this from
the environment, not hardcode `/admin/`.

User-facing-enough admin actions to actually QA in a browser:
- **Webhook test-send** (`freedom_ls/webhooks/admin.py:128-134`, `send_test_action`) — an
  `actions_detail` button on the endpoint detail page that redirects to a form, submits, and shows
  a result page (`send_test_form_view` / `send_test_result_view`). Fully clickable.
- **Cohort report generation** (`freedom_ls/reports/admin.py:110-134`, `generate_report_action`) —
  redirects to a "pick a cohort" form, and the resulting `GeneratedReport` row shows status and,
  once ready, a **Download** link (`freedom_ls/reports/admin.py:101-108`) that hits a
  permission-checked custom URL, not a media URL.
- **Webhook enable/disable** (bulk actions on the changelist) and **delivery retry**
  (`freedom_ls/webhooks/admin.py:252-265`) — both plain admin actions.
- **Organisation logo upload** — a real file-upload form on the Organisation admin page.
- Everything else in the admin (user CRUD, cohort/registration CRUD, consent records read-only) is
  ordinary Django admin browsing and is exactly as testable as any other admin form.

### Cohort reports are PDFs — content is not browser-checkable

Generation runs as a background task (see below) and produces a PDF served as an attachment
through `download_report_view` (never a media URL — `freedom_ls/reports/admin.py:128-131`,
confirmed by `docs/product/security-and-data-handling.md:86-94`). A browser QA agent can: trigger
generation, poll the admin list until status is "ready," click Download, and assert the response
has `Content-Type: application/pdf` and a non-trivial byte length. **It cannot assert anything
about what is printed inside the PDF** — no text is in the DOM to read. FLS's own test suite
proves PDF *contents* (fonts, page orientation, table-of-contents page numbers, running headers)
with `pypdf`, gated behind the `weasyprint` pytest marker
(`pyproject.toml:74-85`: `markers = [..., "weasyprint: marks tests that invoke WeasyPrint and need
Pango/cairo/gdk-pixbuf/HarfBuzz"]`), and that marker is **excluded from the default test run**
(`addopts = "... -m 'not ci_only and not weasyprint' ..."`, `pyproject.toml:79`). Two implications:
1. A staging box that hasn't installed Pango/cairo/gdk-pixbuf/HarfBuzz will still *boot* fine
   (`docs/product/deployment.md:90`: "FLS does not load WeasyPrint at startup") but report
   generation will fail at generation time with a visible error — a QA smoke test should look for
   exactly that failure mode rather than treat a failed report as a mystery.
2. Any content-level assertion about a report's PDF belongs to the existing `weasyprint`-marked
   pytest suite, not to a browser-driving QA agent. The QA plan's job here is "did the button work
   and did a PDF come back," full stop.

### Webhooks: outbound HTTP, partially observable in-app

There is no in-app surface that proves a *real* delivery reached a third party — that requires an
external receiver FLS has no control over. What **is** observable from the admin, read-only:
`WebhookEvent` and `WebhookDelivery` records (status, attempt count, last status code, last
response body — `freedom_ls/webhooks/admin.py:177-265`), and the test-send action's own
success/failure result page. A QA plan can exercise configuration and the test-send round trip
end-to-end; it cannot prove a production event (`user.registered`, course registration, course
completion) was actually delivered anywhere without standing up a receiver of its own.

### Background tasks — the sharpest staging trap

`freedom_ls/deployment/settings_defaults.py:45-51` documents the production task backend
(`django_tasks_db.DatabaseBackend`, no Celery/Redis) and the comment is explicit: **"HARD
operational dependency: an out-of-process `python manage.py db_worker` must be running, or
enqueued tasks persist in the DB and never execute."** `docs/product/deployment.md:41-47` names
exactly two features that depend on it:

- **Webhook delivery** — dispatch happens on the worker.
- **Cohort report generation** — "a requested report stays pending indefinitely" without a worker.

**On a staging box where `db_worker` isn't running, a QA test that clicks "Generate report" and
then polls for "ready" will hang or time out, not fail cleanly** — the admin UI shows "pending"
forever with no error. Note also: **dev and test run these tasks synchronously inside the request
cycle** (`docs/product/deployment.md:43`), so a test written and passing in dev against
`localhost` can pass purely because dev needs no worker at all, then silently never complete
against a staging URL that does. Any QA plan spanning reports or webhooks must either confirm
`db_worker` is running before asserting on task-dependent outcomes, or use a bounded timeout and
treat "still pending after N seconds" as its own explicit, expected failure mode rather than a
hang.

### Email flows — gates the entire authentication plan

Dev captures outbound mail via Mailpit on `localhost:1025` (`config/settings_dev.py:70-72`,
"Browse the inbox at http://localhost:8025"). **Nothing in the settings files inspected
(`config/settings_dev.py`, `config/settings_prod.py`) shows what a staging deployment substitutes**
— `EMAIL_BACKEND`/`EMAIL_HOST`/`EMAIL_PORT` are set only in `settings_dev.py`; production email
configuration is presumably supplied by the downstream concrete project's own settings module,
which does not exist in this repo. Concretely, this means: **signup requires following an emailed
verification link before login is permitted** (`docs/product/authentication.md:22` — "A user
cannot log in until they follow the verification link"), and password reset requires the same. A
QA agent driving only a browser against a remote staging URL, with no mailbox access, **cannot
complete a fresh signup or a password reset end-to-end** unless the staging environment exposes
some inbox-equivalent (a Mailpit-style catch-all reachable over HTTP, or a documented backdoor).
This is not a small caveat — it is the fact that gates whether the Authentication plan can run
unattended at all against staging, versus needing to fall back to pre-seeded, already-verified
accounts (see §6) for everything except the verification/reset link-following step itself.

---

## 4. Multi-tenancy, and what it means for a QA run

**Headline: site isolation is real and load-bearing, but it is fundamentally a dev-only thing to
QA by walking pages, because a remote staging deployment is one hostname. The honest fallback is
either test-in-dev-only, or `Host`-header manipulation against a staging box configured to
recognise more than one `Site` row — not a routine browser navigation.**

Dev exercises multi-site by running five demo sites on distinct `127.0.0.1:PORT` combinations,
each mapped to a Django `Site` row by domain
(`freedom_ls/learner_management/management/commands/create_demo_data.py:19-48`): `Demo`
(`127.0.0.1`), `DemoDev` (`:8000`), `Bloom` (`:8001`), `Prelude` (`:8002`), `Wrend` (`:8003`).
Isolation is enforced per-request by `SiteAwareManager.get_queryset` filtering every query to
`get_cached_site(request)` (`freedom_ls/site_aware_models/models.py:19-50`), which resolves the
site from the request's host **unless `FORCE_SITE_NAME` is set**, in which case host resolution is
skipped entirely and every request — whatever port it arrived on — resolves to that one named
site.

**This is where dev's own settings work against multi-site QA by default**:
`config/settings_dev.py:107` sets `FORCE_SITE_NAME = "DemoDev"`. With that setting active, hitting
`127.0.0.1:8001` (`Bloom`) or `:8002` (`Prelude`) in a dev browser still serves `DemoDev`'s data —
the multi-port setup only demonstrates isolation when `FORCE_SITE_NAME` is unset, which is not
dev's default. A QA plan wanting to exercise real per-port isolation in dev must run without that
override, which is a deliberate deviation from the shipped dev settings, not the default
experience a QA agent gets by pointing at `localhost:8000`.

**Against a remote staging URL**, none of this applies at all: staging is one hostname, so there
is exactly one `Site` reachable by ordinary navigation, and Django's own host-based resolution
gives a QA agent no second tenant to compare against. The three honest options, in order of
fidelity to what the isolation guarantee actually claims:
1. **Test it in dev only**, using the multi-port setup with `FORCE_SITE_NAME` unset — the only
   place multiple sites are simultaneously reachable by ordinary browser navigation.
2. **`Host`-header manipulation against staging** — send requests with a spoofed `Host` header
   matching a second `Site` row's domain, if one has been created and `ALLOWED_HOSTS` (or
   equivalent) permits it. This is not something an ordinary browser does; it needs raw HTTP
   control (unclear whether the QA tool this suite runs on can set arbitrary headers on browser
   navigations rather than API calls) and deliberately provisioning a second tenant on the staging
   box purely for the test.
3. **Skip it on staging** and rely on the dev-only pass. Given that a single staging URL by
   definition has no second tenant to leak into, this is the most defensible default — isolation
   is architecturally proven by the query-filter mechanism and by FLS's own pytest suite, not
   something an end-to-end browser walk of one hostname can newly demonstrate.

Organisations (`freedom_ls/organisations/`) are explicitly **not** an isolation boundary
(`docs/product/multi-tenancy-and-isolation.md:46`: "not a security or isolation boundary") — they
are a grouping layer *inside* one site's data, scoping cohorts and registrations. Testing
organisation *scoping* (an educator switching between two organisations on the same site, seeing
different cohort lists) is an ordinary single-hostname browser test and belongs in the Educator
Interface plan, not the isolation question above.

---

## 5. Critical-path journeys

Five journeys that, if broken, mean the product is down — independent of which doc they map to:

| # | Journey | Surfaces crossed | Doc areas spanned |
|---|---|---|---|
| 1 | A learner signs up, verifies, and enrols in a free course | allauth signup → email verification → `accounts:complete_registration` (if extra forms configured) → `learner_interface:course_detail` → `initiate_course_access` | authentication, learner-experience |
| 2 | A learner opens a course and completes a topic | `learner_interface:course_home` → `view_course_item` → mark-complete, resume pointer advances | learner-experience, learner-tracking |
| 3 | A learner sits a quiz and gets a score | `form_start` → `form_fill_page` (possibly multi-page) → `course_form_complete` → score/pass-fail shown | learner-experience, learner-tracking |
| 4 | An educator opens the panel and sees a cohort's progress | `educator_interface:root` → org switcher → cohort detail → Course Progress tab (matrix) | educator-interface, learner-tracking |
| 5 | A staff user generates and downloads a cohort report | Django admin → `GeneratedReport` generate action → status polling (needs `db_worker`, see §3) → permission-checked download | admin-interface, reports, security-and-data-handling (access check) |

A **smoke** subset is journeys 1–3 (the learner spine, no worker dependency, no staff account
needed beyond the fixtures in §6) plus a thin educator-panel-loads check from journey 4. A **full
regression** pass adds journey 5 (requires a running `db_worker`), the Educator Interface Courses
authorisation probe (§1), webhook test-send, and the health endpoints.

---

## 6. Roles and the accounts a QA run needs

**Headline: the roles that matter for access decisions are guardian per-object permissions and
per-object organisation staff roles — not the `role_based_permissions` role system, which exists
but (per `docs/product/roadmap.md`) does not itself govern access. And the DemoDev-specific role
extension (`config/role_based_permissions/demodev.py`) is a dev-settings-only fixture that will
not exist on a staging deployment unless the concrete project reproduces it.**

Distinct actor types a full pass needs, and what each must have attached:

| Actor | Needs | Notes |
|---|---|---|
| **Anonymous visitor** | Nothing — no `Site` beyond the one the request resolves to | Dashboard, catalogue, course detail, sitemap/robots, apply/enrol CTAs that redirect into login |
| **Unverified signup** | A `User` row with no verified `EmailAddress` | Exists only mid-flow; cannot reach anything past the verification gate. Testable only if staging exposes some inbox equivalent (§3) |
| **Registered learner, with progress** | A `User`, an `ensure_learner`-created `Learner` row tying them to an `Organisation`, a `LearnerCourseRegistration` or `CohortMembership` + `CohortCourseRegistration`, and at least one `TopicProgress`/`FormProgress` row | Needed for resume-pointer, "in progress"/"completed" dashboard sections, quiz retake behaviour |
| **Registered learner, no progress** | Same as above minus any progress rows | Needed for "first item always available," empty-dashboard-section behaviour |
| **Educator scoped to an organisation** | A `User`, plus **either** a per-cohort guardian grant **or** an organisation-wide staff role — both assigned via Django admin per-object permissions, per `docs/product/admin-interface.md#cohort-permissions` and `#organisation-management` | Two independent grant routes exist; a thorough plan needs one account of each kind to prove they're equivalent, plus one educator account with **neither** grant on a target cohort, to prove the deny-by-default "not found" response |
| **Staff/admin** | `is_staff=True` (and usually `is_superuser=True` for unrestricted admin access) | Needed for admin-interface plan, report generation, webhook admin, and the `/sentry-debug/` probe |

**Dev-settings-only things that will be missing on staging:**
- `FREEDOMLS_PERMISSIONS_MODULES = {"DemoDev": "config.role_based_permissions.demodev"}`
  (`config/settings_dev.py:103-105`) — only referenced from `config/settings_dev.py` in the whole
  repo (confirmed by search); `config/settings_prod.py` sets none of it. The `senior_ta` and
  `guest_reviewer` roles it adds (`config/role_based_permissions/demodev.py`) exist only when this
  dev module is loaded. Since roles don't govern access anyway (see roadmap note above), this
  mainly matters if a QA plan tries to test role-*assignment* UI/commands rather than the
  guardian-permission effect.
- `FORCE_SITE_NAME = "DemoDev"` (`config/settings_dev.py:107`) — pins every request to one site
  regardless of host; not present in `settings_prod.py`. Its presence in dev is also what defeats
  the multi-port isolation demo by default (§4).
- `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE = True` and `OVERRIDE_COURSE_ACCESS_TO_FREE = True`
  (`config/settings_dev.py:119-120`) — **a QA trap in the other direction**: with dev's shipped
  settings, *every* course presents as published and free, "no matter its configured access type"
  (`docs/product/configuration-and-extension.md:76-79`). A QA plan that wants to exercise
  coming-soon badges, hidden-course 404s, or the application-gated apply flow **cannot do so
  against an unmodified dev environment** — those overrides must be turned off first, or the plan
  must run in an environment (or against demo/staging content) where they are off, which is the
  default per `docs/product/configuration-and-extension.md:79` ("no shipped settings module
  enables them in production").
- `sync_role_permissions` (`freedom_ls/role_based_permissions/management/commands/sync_role_permissions.py`)
  is a manual management command, not something that runs automatically on save — role
  assignments and the guardian permissions they should produce can drift unless this is run. A
  staging box seeded once and never re-synced could have stale permission state relative to its
  role assignments.

`Organisation` requirement worth flagging explicitly: every `Learner`, `Cohort`, and course
registration must belong to **some** organisation (`freedom_ls/organisations/models.py`;
`docs/product/multi-tenancy-and-isolation.md:44`, "every cohort and every course registration
belongs to exactly one organisation"). Every site gets a default organisation automatically, so a
QA fixture that never explicitly creates one is still fine — but an educator account's grant must
name a real `Cohort` or `Organisation` object, not just exist.

---

status: ok
