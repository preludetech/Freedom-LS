# Deployment

_Last updated: 2026-09-23_

## Summary

FLS is never deployed standalone. It is a library, installed into a **concrete project** — a downstream repository that supplies its own settings, content and deployment scaffolding — and this page describes what the application requires of that host, not how any particular host is built. A production deployment needs a dedicated worker process for background tasks, system libraries for PDF rendering, and object storage for media; production logging goes to stdout, leaving capture and rotation to the deployment's container log driver. See [the deployment security checklist](../deployment-security-checklist.md) for the pre-launch steps this page does not cover.

## Background Tasks

Django 6's built-in task framework is wired in. Production uses a durable, database-backed backend that stores tasks as rows in PostgreSQL — no Celery, Redis, or separate broker — and enqueued tasks are inspectable in the Django admin. Dev and test instead run tasks synchronously inside the request cycle, so the whole test suite runs without a worker process.

**`python manage.py fls_run_worker` is a required production process.** An enqueued task sits in the database until a worker picks it up; without one running, background work — webhook delivery and [cohort report](./reports.md) generation — is accepted but never executes, and a requested report stays pending indefinitely. A deployment that turns on email queueing puts outgoing email on that same list — and unlike a stuck report, which sits visibly pending on screen, a queued email that never sends fails silently: the person is told to check their inbox and nothing ever arrives. Run it as its own long-lived process or container. It maintains a heartbeat file an external probe can poll to confirm the work loop is still turning, and exits rather than sitting wedged on a task it can no longer make progress on. A long-running task is not mistaken for a wedged one: the worker holds the heartbeat up for the whole of a task it is genuinely working on, up to a configurable ceiling, so a large cohort report renders to completion rather than being killed part-way. Past that ceiling the task is treated as hung and the worker exits as before.

Delivery is at-least-once, so a task can be redelivered. Task producers are idempotent under redelivery: a webhook is not sent twice for the same event and endpoint. See [webhooks](./webhooks.md).

**`python manage.py fls_run_housekeeping` is a required scheduled production process.** One run prunes finished task results — the task-results table grows without bound if left alone, which eventually becomes a disk problem on a small host — clears expired sessions, reports tasks left sitting unpicked, which is the signal that no worker is running, and closes out any task whose worker died mid-run rather than leaving it stuck. It also closes out any cohort report left rendering by a worker that died. That last sweep matters more than it sounds: only one report per cohort may be in flight at a time, so a report stranded mid-render would otherwise block that cohort from ever requesting another. It reports failures to Sentry and exits non-zero when something needs attention. The schedule is the deployment's to supply.

## Application-Level Capabilities

Built into the application and present regardless of deployment configuration:

- **Outgoing email** — sent over SMTP inside the request by default, needing nothing running but the web process. A deployment that runs a worker can instead set `EMAIL_BACKEND` to the queueing backend, handing the message to the task queue so a slow mail host no longer holds a page open. That is an explicit opt-in, not the default: queued mail with no worker behind it is accepted and never sent. See [security and data handling](./security-and-data-handling.md#queued-email).
- **Static files** — served compressed and cache-busted directly from the application. No separate static file server needed.
- **Object storage for media** — media is served from S3-compatible object storage (Cloudflare R2), split across three buckets by sensitivity: one for anonymously readable branding, one for course content, one for private data. Course content is private but holds no personal data and can be rebuilt from the content repository, so the private-data bucket is the one a leaked credential should reach the least. That private-data bucket holds cohort reports and the files applicants upload with a course application. Each of the five named locations resolves independently, optionally with its own credentials, so an operator can scope a token to the private-data bucket alone. Locations share the three buckets above rather than each getting one of their own. Leaving one unset falls back to local filesystem storage, which the deployment check reports as an error — that fallback is a development convenience, not a way to run in production. Media is **private by default**, with time-limited signed links rather than permanently public URLs. See [security and data handling](./security-and-data-handling.md).
- **Health probes** — `/health/liveness/` and `/health/readiness/`, available with no configuration. Liveness only confirms the process can serve a request and checks no dependency, so a transient database problem cannot trigger a restart loop. Readiness checks database connectivity and returns a non-200 when it is unreachable, making it the probe that container health checks and load balancers should poll to gate traffic; a setting lets an operator add further checks. Applied migrations are deliberately excluded — that belongs in a deploy-time smoke test, not a polled probe. Health paths are exempt from the HTTPS redirect, so a plain-HTTP internal probe behind a TLS-terminating proxy is served rather than mistaken for unhealthy.
- **Maintenance page** — FLS ships a branded maintenance page that depends on nothing else running in the application, so it still renders while the app itself is down. FLS never serves it: there is no maintenance mode and no switch to turn one on. A deployment that wants a maintenance window points its own reverse proxy or maintenance middleware at this page rather than building one of its own. See [learner experience](./learner-experience.md#error-pages) for FLS's other branded error pages.
- **Database-backed cache** — production runs a small database-backed cache, which is what lets the login and signup rate limits hold across restarts and across worker processes instead of resetting with each one. Its table is created by `manage.py createcachetable` in the deploy sequence; a deployment check fails when that step was missed, rather than letting the gap surface later as an error on the login page.
- **Error tracking (Sentry)** — configured by supplying a DSN, and a complete no-op until one is set, so development and unconfigured deployments send nothing. Once configured it tags events with the deployment's environment and release. Attaching learner personal data is an explicit opt-in, off by default. A staff-only endpoint lets an operator confirm a running deployment is actually reaching Sentry. If a DSN is set but the release identifier is left blank, a non-blocking deployment warning surfaces at boot and in CI, so untagged events are caught rather than quietly degrading release tracking.
- **Analytics (Google Analytics 4)** — a client-side snippet configured by `GOOGLE_ANALYTICS_MEASUREMENT_ID`. With no ID set nothing loads and nothing is sent. Signed-in sessions carry the numeric account ID as `user_id`, never an email address. Neither analytics snippet loads on the email-confirmation or password-reset pages, whose URLs carry one-time tokens. The GA4 property needs one-off setup before its reports are useful. See [Google Analytics 4 setup](#google-analytics-4-setup).
- **Advertising measurement (Google Ads)** — the same tag, given a Google Ads conversion ID, also reports to Google Ads. Conversions reach Ads either by importing GA4 key events, which needs no further configuration, or as native Ads conversions for the events an operator maps to conversion labels. Google Ads needs GA4 configured; a deployment warning flags an Ads ID on its own. See [Google Ads](#google-ads).
- **Analytics (PostHog)** — a client-side snippet configured by project token and region host. With no token set the snippet does not render, so development deployments send nothing.
- **Environment-variable configuration** — all secrets and deployment-specific settings are supplied by environment variable, with sensible in-repo defaults where one makes sense, so a deployment configures these services without copy-pasting settings code. No credentials are hardcoded. Database connection SSL mode is configurable and defaults to *preferred*, which suits a same-host containerised PostgreSQL; stricter modes are for external or managed databases. Persistent database connections are enabled with health checking, so a connection left stale by a database restart is recycled rather than failing the next request. A missing `SECRET_KEY` — or a missing `WEBHOOK_ENCRYPTION_SALT` — fails the application at startup as a visible crash-loop rather than booting into a silently broken state. See [security and data handling](./security-and-data-handling.md).
- **HTTPS detection behind a reverse proxy** — production trusts the proxy's forwarded scheme, so requests that reached the proxy over HTTPS are correctly recognised as secure. This is what makes the HTTPS redirect and HSTS work behind a proxy instead of looping. See [security and data handling](./security-and-data-handling.md) for the trust preconditions.
- **Shared production defaults** — the production settings FLS recommends are increasingly delivered as values a downstream project imports directly from FLS rather than copies. A fix to one of these lands once in FLS and reaches downstream projects on their next routine version update, instead of needing to be re-applied project by project.
- **Tailwind build at image-build time** — `npm run tailwind_build` must run during image construction, and `FLS_THEME` must be set at build time. It cannot be changed at runtime without a rebuild. The [cohort report](./reports.md) takes its colours from this compiled stylesheet rather than carrying any of its own, so a deployment that ships without running the build gets an explicit failure when generating a report rather than a colourless PDF.

**Logging.** The application's logging helper defaults to stdout/stderr only, and production uses that default: nothing here writes to disk. Capping and rotating what a container collects is the deployment's job, handled at the log-driver level, not the application's.

## Google Analytics 4 setup

FLS sends six events. Their names describe moments every course access backend shares, and whatever differs by backend travels as a parameter value. A new backend adds a value, so a funnel built today keeps working.

| Event | Sent when | Parameters |
| --- | --- | --- |
| `sign_up` | An account is created | `method` |
| `course_access_requested` | A learner expresses interest in a coming-soon course, or submits a course application | course parameters, `request_kind` (`interest` or `application`) |
| `course_registered` | A learner registers themselves for a course | course parameters, `registration_method` (`self_registration`) |
| `course_started` | A learner opens their first page of a course | course parameters, `registration_source` (`individual` or `cohort`) |
| `course_completed` | A learner completes a course | course parameters, `registration_source` |
| `generate_lead` | A concrete project's marketing form is submitted. FLS ships no such form | `lead_form`, optional course parameters |

The course parameters are `course_slug`, `course_id` and `access_type` (`free` or `application_gated`). No parameter carries personal data.

Staff and cohort registrations happen outside the learner's browser, so they never send `course_registered`. Those learners still send `course_started`, with `registration_source` set to `cohort` where that applies. The registration step of a funnel undercounts. The later steps do not.

**Set up each GA4 property once, before launch.** Reports pick up a custom dimension a day or two after it is registered, and earlier events are not backfilled.

1. Under Admin, Custom definitions, register six event-scoped custom dimensions: `course_slug`, `access_type`, `request_kind`, `registration_method`, `registration_source` and `lead_form`. Leave `course_id` unregistered. It has one value per course, GA4 folds dimensions with more than 500 values into "(other)", and an unregistered parameter still reaches BigQuery and DebugView.
2. Mark five key events: `sign_up`, `generate_lead`, `course_access_requested`, `course_registered` and `course_completed`.
3. In the data stream's enhanced measurement settings, leave "Page changes based on browser history events" on. FLS relies on it for page views during in-page navigation. Consider turning "Form interactions" off. It fires for every form on the site, quiz pages included.
4. To count applications apart from interest, use Admin, Events, Create event. Match `course_access_requested` where `request_kind` equals `application`, name the result, and mark it a key event.
5. Build the funnel under Explore, Funnel exploration, with the steps `sign_up`, then `course_access_requested` or `course_registered`, then `course_started`, then `course_completed`. Break it down by `course_slug` or `access_type`.

**Lead forms.** A concrete project's form view records its own event after the form validates and saves.

```python
from freedom_ls.base.google_analytics import (
    GoogleAnalyticsEvent,
    record_google_analytics_event,
)

record_google_analytics_event(
    request, GoogleAnalyticsEvent.GENERATE_LEAD, {"lead_form": "call_me_back"}
)
```

The next page the visitor sees sends it. The function takes any event name as a string and raises `ValueError` for a name GA4 would reject. Send the form's name and nothing the visitor typed into it. A form that belongs to one course can add `course_event_params(course)` from `freedom_ls.course_access.google_analytics`, so leads line up with the course funnel.

**Landing pages.** GA4 already records the first page of every session as its landing page, so a landing page needs no event. To tell marketing landing pages from any other first page, the landing page template fills one block from `_base.html`.

```django
{% block google_analytics_config_params %}content_group: 'landing_page'{% endblock %}
```

Every event from that page, `page_view` included, then carries that content group. It is a predefined GA4 dimension and needs no registration. Link onward from a landing page with ordinary full-page links. The value is set once per full page load, so after a boosted navigation it would stick to the pages that follow.

**Campaign links.** GA4 reads `utm_*` tags from the landing URL. [Referral links](./referral-codes.md) pass the visitor's query string through to the destination, so tags on the short link reach GA4. GA4 ignores the referral code itself. A referral link with no `utm_*` tags shows up as direct traffic.

### Google Ads

Setting `GOOGLE_ADS_CONVERSION_ID` to the account's `AW-` ID adds Google Ads as a second destination of the tag GA4 already loads. Ads then sets its click and conversion cookies on every page and can build remarketing audiences. It loads through the GA4 tag, so it needs `GOOGLE_ANALYTICS_MEASUREMENT_ID` as well; an Ads ID on its own produces deployment warning `freedom_ls_deployment.W002` and loads nothing. The Ads tag is off wherever the GA4 tag is off, including the two token-bearing pages.

Conversions can reach Google Ads two ways. They are not exclusive.

**Import GA4 key events.** Link the GA4 property to the Ads account, turn on auto-tagging in Ads, then in GA4 open Advertising, Conversion management, New conversion, and pick the key events from the table above. Nothing in FLS changes. Ads cannot see view-through conversions this way, and imported conversions reach Smart Bidding a day or more after the event.

**Native Ads conversions.** In Google Ads open Goals, Conversions, New conversion action, Website, and add the action manually. Its tag snippet ends in `send_to: 'AW-XXXXXXXXX/LABEL'`; the part after the slash is the label. Map event names to labels in `GOOGLE_ADS_CONVERSION_LABELS`, for example `sign_up=AbCdEfGhIj,course_registered=KlMnOpQrSt`. A mapped event then sends `gtag('event', 'conversion', {send_to: ...})` in the same script as its GA4 event, so the two fire together, once, wherever the GA4 event fires. An event with no label sends no conversion. Labels without an Ads ID produce warning `freedom_ls_deployment.W003`. Any event name works as a key, including a downstream project's own events, so a lead form can report `generate_lead` to Ads the same way. A malformed entry fails the application at boot.

When both routes report the same moment, Ads marks the imported GA4 conversion "secondary" so it counts once for bidding. Native conversions arrive within hours and support view-through conversions, so use them as the primary conversion where the Ads campaigns include Display or YouTube.

The report-only CSP names Google's Ads hosts. Google also calls `www.google.<country TLD>` for the visitor's country and CSP has no way to wildcard that, so FLS lists `www.google.co.za`; a deployment serving other countries adds theirs.

## Operator Responsibilities

FLS is not certified under ISO 27001 or any other framework, and a hosting provider's own certification, where one exists, typically covers its data centre, hardware and hypervisor layer only. Everything above that is the operator's: OS hardening and patching, TLS terminating somewhere in front of the application, encrypted backups that are actually tested by restoring from them, database SSL configuration, access control, and logging and monitoring beyond what Sentry provides once a DSN is configured.

A reverse proxy or edge in front of the application must also allow a request body comfortably above the 6 MB per-file cap on an applicant's course-application file upload (`form_engine.uploads.MAX_UPLOAD_BYTES`); 10 MB is a safe figure. That limit lives outside FLS's settings and checks, so nothing in FLS catches an edge configured below it; the symptom is a bare error from the edge before FLS's own in-form message can show.

PDF rendering needs Pango, cairo, gdk-pixbuf, and HarfBuzz present at runtime, since [cohort reports](./reports.md) render using WeasyPrint. The report bundles its own fonts, so rendering does not depend on what the base image otherwise carries. FLS does not load WeasyPrint at startup: a host missing those libraries still boots, and report generation fails at generation time with a clear error rather than a crash loop.

The full breakdown is in [security and data handling](./security-and-data-handling.md); the pre-deployment steps are in [the deployment security checklist](../deployment-security-checklist.md).

## Deploying a Concrete Project

FLS is never deployed standalone. A production deployment is a **concrete project** — a downstream repository that installs `freedom_ls` as a git submodule and supplies its own settings, content, and deployment scaffolding.

Before deploying, run the FLS conformance suite against the concrete project's own settings as a pre-launch check. Many FLS wiring mistakes are also reported when the application starts, rather than surfacing later as an error for a learner. See [configuration and extension](./configuration-and-extension.md) for both.

**First-run bootstrap.** `python manage.py setup_initial_prod_data <admin-email> --site-name "<Display Name>"` creates the site record, the administrative account and its verified email address in one step, so a fresh deployment has a working administrator login without any manual database editing. It generates that account's password and prints it once — nothing else stores or displays it, so it has to be recorded there and then. Because a CI or deploy log keeps whatever is printed into it, this command does not belong in the automated deploy sequence: the operator runs it by hand, once per stack, from a terminal the password can be read from and nowhere else. A second run against the same deployment leaves an existing administrator's password untouched, so re-running it later causes no harm if the first run's output was missed. `--site-name` is what the installation calls itself in email subject lines, on reports and in the navigation bar; `HEADER_TITLE` overrides it later without a database edit. See [configuration and extension](./configuration-and-extension.md).
