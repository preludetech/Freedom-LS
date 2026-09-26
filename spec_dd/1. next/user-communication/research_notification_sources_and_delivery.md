# Research: notification sources and delivery (codebase, R1)

Scope: what in FLS today could feed a per-user notification (idea.md's "tell people different
things about their own activities"), what delivery infrastructure exists to carry it, and what a
real-time in-app layer would cost this deployment story. Codebase research only; one web check for
Django Channels deployment cost. Read alongside `idea.md`, the nested `student-communication/idea.md`
draft (comms/messaging, not repeated here), and `retry-sent-emails/1. spec.md` (the mail-transport
retry spec landing first, described in its pre-change state below unless noted).

Vocabulary: **learner** (`Learner`, `freedom_ls/learner_management/models.py:51`), never "student".
Course access is a **registration** (`LearnerCourseRegistration` / `CohortCourseRegistration`), never
an "enrolment". "Course progress record" for `CourseProgress`. See
`.claude/skills/domain-glossary/SKILL.md`.

## 1. Notification sources

FLS has exactly one outward event mechanism today, `fire_webhook_event(event_type, payload)`
(`freedom_ls/webhooks/events.py:10`). It validates `event_type` against a settings-driven registry
(`freedom_ls/webhooks/registry.py:9`, reading `WebhooksConfig.WEBHOOK_EVENT_TYPES`,
`freedom_ls/webhooks/config.py:7`, defaulting to `FLS_WEBHOOK_EVENT_TYPES`,
`freedom_ls/base/webhook_event_types.py:1`), creates a `WebhookEvent` row and enqueues delivery to
**external** endpoints — it has no in-app or email leg today, and it silently no-ops outside a
request context (management commands, shell, data migrations get nothing fired).

**All three registered event types, every call site:**

| Event type | File:line | Who fired it / recipient candidate | Hook point today |
| --- | --- | --- | --- |
| `user.registered` | `freedom_ls/accounts/allauth_account_adapter.py:138` (`AccountAdapter.save_user`, inside `if commit:`) | The new user, about their own signup | Yes — but it fires unconditionally as part of the signup transaction path, not from a place a notification consumer would want to hang a "welcome" email off (allauth already sends its own verification mail via `send_mail`, line 32). |
| `course.registered` | `freedom_ls/learner_progress/signals.py:143` (`_ensure_and_announce`, called from `ensure_course_progress_on_learner_registration`, `:180-198`) | The learner who just registered, about their own registration | Yes, for **individual** registration only. `ensure_course_progress_on_cohort_registration` (`:201-213`) fans a `CohortCourseRegistration` out to every member's `CourseProgress` and **never announces**; `ensure_course_progress_on_cohort_membership` (`:216-227`) catches a new cohort member up on existing registrations and also never announces. This is the exact gap `spec_dd/1. next/educator-interface-full-polish` ... no — it's flagged in `spec_dd/1. next/educator-interface-7-learner-administration/idea.md:35`: cohort registration, membership add/remove/move, deactivate/unregister fire nothing today, and that spec is where new event names get added. |
| `course.completed` | `freedom_ls/learner_interface/views.py:1642` (`course_finish`, inside the branch that stamps `completed_time`, `:1636-1653`) | The learner, about their own completion | Yes — fires in the same branch as the stamp, by design ("the stamp and the webhook share this branch deliberately", `:1631-1633`). A congratulations notification/email hangs here cleanly. |

**Model state changes with no `fire_webhook_event` (and mostly no signal) today:**

- **`CourseApplication`** (`freedom_ls/course_applications/models.py:18`) — deliberately has **no
  state field and no state machine**. The model's own docstring NOTE (`:24-29`) says application
  review will add `state = FSMField(...)`, submit/withdraw/pick_up/request_changes/resubmit/
  approve/reject transitions, and an `application_state_changed` signal. **"Application approved" /
  "application rejected" notifications are blocked on that review workflow landing** —
  `spec_dd/1. next/educator-interface-full-polish/application-review-ui/idea.md` and its
  `research_review_workflow.md` are where that state machine and its signal get designed. Until
  then the only observable fact is submission (`is_submitted`, `:72-83`, true once `form_progress`
  — the applicant's `FormProgress` sitting — has `completed_time` set), which itself fires no event;
  it rides `form_engine`'s `form_attempt_completed` signal (below), unaddressed to `course_applications`.
- **`CourseInterest`** (`freedom_ls/course_interest/models.py:17`) — "notify-on-launch" is an explicit
  documented deferral: the model's docstring (`:1-7`, `:23-25`) says a `notified_at` field lands "when
  the notify-on-launch feature is implemented"; nothing fires today when a course the learner
  expressed interest in opens. A course-launch → interested-learners fan-out is a genuinely new
  event, not a hook that already exists.
- **`form_engine` completion** — `Form.complete()` sends `form_attempt_completed`
  (`freedom_ls/form_engine/models.py:395-404`, a plain `django.dispatch.Signal`,
  `freedom_ls/form_engine/signals.py:7`), for **every** attempt, course-bound or not (a form can be
  sat standalone, e.g. an application form). `learner_progress` is the one connected receiver
  (`freedom_ls/learner_progress/signals.py:96-119`), and it only recalculates the course progress
  percentage — it does not re-fire a webhook or touch a notification. **There is no manual
  marking/grading workflow in FLS today** — `freedom_ls/form_engine/scoring.py`'s strategies
  (`CATEGORY_VALUE_SUM` etc., referenced at `form_engine/models.py:406` onward) are all automatic,
  computed at `complete()` time; no educator "marks" a submission and no signal exists for that
  because the action doesn't exist yet. A comms spec wanting "your quiz was scored" or "your
  application was reviewed" notifications has `form_attempt_completed` to hang the first on; the
  second needs the review workflow above.
- **Deadlines** (`CohortDeadline`, `LearnerDeadline`, `LearnerCohortDeadlineOverride`,
  `freedom_ls/learner_management/models.py:159`, `:205`, `:251`) — plain `SiteAwareModel` +
  `TimestampedModel` rows with **no signals at all** (confirmed: no `post_save`/`post_delete`
  receiver anywhere references these models, and `deadline_utils.py` has no notification-adjacent
  code). "Deadline approaching" / "deadline passed" is not an event that exists to hook — it would
  need a **new periodic scan** (there is no `deadline` field index today beyond the plain
  `DateTimeField`), which is exactly the kind of thing a daily digest sweep is for. See §2 on
  whether `fls_run_housekeeping` is the right place.
- **Account events beyond signup** — email verification, password reset and (per
  `spec_dd/3. done/2026-06-15_00:19_email-styling/1. spec.md:19-24`) a login-code mail are all
  allauth's own transactional mail, sent through `AccountAdapter.send_mail`
  (`freedom_ls/accounts/allauth_account_adapter.py:32-53`) directly — no webhook, no notification
  hook, and arguably none needed (these are not "activity" notifications, they're auth flow itself).

## 2. Delivery stack

**Mail transport, pre-`retry-sent-emails` state** (that spec is landing first and changes every file
named here — see its "Decisions"/"Requirements" for the target state):

- `EMAIL_BACKEND` opt-in: `freedom_ls.mail.backends.QueuedEmailBackend`
  (`freedom_ls/mail/backends.py:37`). `send_messages` serialises each message
  (`serialise_message`, `freedom_ls/mail/serialisation.py`) and enqueues
  `_send_email_task(payload)` (`freedom_ls/mail/tasks.py:42-44`) via `default_task_backend`. No
  persisted row today — the payload rides in `DBTaskResult.args_kwargs` — which is exactly the
  "reset link copied into a fresh task row on every attempt" flaw `retry-sent-emails/1. spec.md:45-49`
  is fixing. An `UnserialisableMessageError` falls back to an inline send (`_send_now`, `:83-90`);
  a `DatabaseError` from the enqueue itself re-raises unless `fail_silently`.
- The worker actually sends through `EMAIL_UPSTREAM_BACKEND`
  (`freedom_ls/mail/config.py:17-19`, default `django.core.mail.backends.smtp.EmailBackend`),
  in `send_serialised_email` (`freedom_ls/mail/tasks.py:27-39`). Failures propagate today — no
  classification, no retry — reported only via the task framework's own FAILED-result logging and
  Sentry's logging integration (`retry-sent-emails/1. spec.md:9-13`). `retry-sent-emails` adds the
  `OutboundEmail` row, error classification, backoff and admin resend on top of this same file set.
- **TASKS config**: dev/test run `django.tasks.backends.immediate.ImmediateBackend`
  (`config/settings_base.py:553-557`, "no worker" — sends inline). Production overrides to
  `django_tasks_db.DatabaseBackend` (`config/settings_prod.py:87`, `TASKS = fls_defaults.DATABASE_TASKS`,
  defined at `freedom_ls/deployment/settings_defaults.py:72-74`) — **database-backed, explicitly "no
  Celery/Redis"** (comment at `:65-67`, and `docs/product/deployment.md:11`: "no Celery, Redis, or
  separate broker"). A durable production deployment therefore already has an async queue and a
  dedicated worker process (`python manage.py fls_run_worker`,
  `freedom_ls/deployment/worker.py:185-278`, a heartbeat-and-watchdog wrapper over
  `django_tasks_db`'s `Worker`) — the idea.md's flagged "Async task queue" prerequisite
  (`idea.md:191-194`) is **already met in production**, provided the deployment opts `EMAIL_BACKEND`
  into `QueuedEmailBackend` (it is not the default even in prod — `EMAIL_BACKEND` docs at
  `docs/product/deployment.md:23`). Broadcast fan-out or digest batching would enqueue on this same
  worker; no new infra needed for that half.
- **`fls_run_housekeeping`** (`freedom_ls/deployment/housekeeping.py:221-308`,
  `run_housekeeping_sweeps()`) prunes task results, clears sessions, and reaps orphaned
  RUNNING task/report rows. It is a **management command run on a schedule the deployment supplies**
  ("The schedule is the deployment's to supply", `docs/product/deployment.md:17`) — there is no
  built-in cron, Celery beat, or `django-crontab`-style scheduler in FLS; a downstream project's own
  cron / Kubernetes CronJob calls it. `retry-sent-emails` adds three more sweeps to this same command
  (`requeue_due_outbound_email`, `recover_stuck_outbound_email`, `prune_outbound_email`,
  `retry-sent-emails/1. spec.md:231-255`) and *raises* its recommended cadence to "at least hourly"
  (`:355-358`). **This is the closest thing FLS has to a periodic-task mechanism, and it is a
  reasonable place to add a daily/weekly digest sweep** — but it inherits the same "the deployment
  supplies the schedule" constraint: a digest spec would need to document what cadence to configure,
  not assume one exists. There is no lighter-weight in-process scheduler (no `django-q`, no
  `APScheduler`) anywhere in the dependency tree.
- **Email templates/styling**: themed, brand-aware HTML mail already exists and is not something a
  comms feature needs to build from scratch. `spec_dd/3. done/2026-06-15_00:19_email-styling/1. spec.md`
  landed `get_email_theme()` (lazily-cached, token-merged against the active theme, fail-loud on a
  malformed required token) feeding `AccountAdapter.send_mail`'s context
  (`freedom_ls/accounts/allauth_account_adapter.py:43-49`), a unified logo/label
  (`_email_branding_context`, `:71-93`) resolved to an absolute URL for external mail clients
  (`_resolve_email_logo_url`, `:95-125`), and theme-driven fonts/button radius. A notification email
  template extends the same `base_email.html` and reuses this context builder rather than
  reinventing branding.

## 3. Real-time

**FLS is WSGI in production, and Channels is not installed anywhere in the dependency tree.**

- `config/asgi.py:1-15` and `config/wsgi.py:1-15` are both unmodified `django-admin startproject`
  boilerplate — plain `get_asgi_application()` / `get_wsgi_application()`, no `ASGI_APPLICATION`
  setting anywhere in `config/settings_base.py`, no channel routing. The
  `asgi-and-wsgi-name-a-settings-module-that-does-not-exist` idea
  (`spec_dd/3. done/2026-08-28_19:44_.../idea.md:20-23`) states plainly: **"Nothing in FLS imports
  `config/asgi.py` at all"**, and the template repo's Dockerfile "exports `config.settings_prod`
  before gunicorn imports `config.wsgi:application`" (`:19-21`) — i.e. the reference deployment is
  gunicorn-on-WSGI, and `asgi.py` is dead weight kept only "for whoever reaches for async"
  (`:51-58`).
- No Redis, no cache/channel-layer backend anywhere in the product code. Production's `CACHES` is
  the database-backed cache (`fls_defaults.DATABASE_CACHES`,
  `freedom_ls/deployment/settings_defaults.py:86-92`, "LOCATION is a table name... `createcachetable`"),
  explicitly for allauth's rate limiting — not a channel layer, and not swappable to one without a
  new dependency. Every "redis" hit in the repo outside `spec_dd/` research/idea prose and
  `docs/product/deployment.md`'s "no ... Redis" line is zero — grep confirms no `channels`,
  `channels_redis`, or `redis` package anywhere in `pyproject.toml`/`uv.lock`-adjacent config files.

**What adding Django Channels would cost this deployment story**, per the idea.md's own framing
(`idea.md:198-202`, "FLS is WSGI today"):

1. **A second server process/protocol.** Gunicorn-on-WSGI cannot serve WebSocket upgrades. The
   concrete project's Dockerfile/Procfile would need an ASGI server (Daphne or Uvicorn+Uvicorn
   workers) fronting `config.asgi:application`, either replacing gunicorn or running alongside it
   behind a reverse proxy that routes `/ws/` differently — a deployment topology change every
   downstream project inherits, not something FLS can absorb invisibly.
2. **A channel layer backend for cross-process fan-out.** Channels' in-memory layer only works
   single-process; anything with more than one web worker (which gunicorn already runs with by
   default) needs `channels_redis` (or a database-backed channel layer, which exists but is not
   the common/recommended path) — i.e. exactly the Redis dependency `docs/product/deployment.md:11`
   currently boasts FLS does *without*. That's a new piece of infra every downstream install must
   provision, patch, and back up, whereas today's "no Celery, Redis, or separate broker" is a
   selling point of the project (`docs/product/deployment.md:11`).
3. **New health/ops surface.** Health probes (`/health/liveness/`, `/health/readiness/`,
   `docs/product/deployment.md:26`) and the worker heartbeat pattern
   (`freedom_ls/deployment/worker.py`) would need an equivalent for the channel layer connection and
   the ASGI process; none of that exists today.
4. **Optional-by-construction, or it's not optional.** The comms idea already commits to "the
   real-time layer must degrade gracefully to HTMX polling" (`idea.md:63-64`, `:199-202`) — which
   means Channels has to be genuinely off-by-default and every UI path (unread badge, live message
   arrival) has to have a working polling fallback *anyway*. Given (1)-(3), a first cut of
   notifications/messaging can ship on HTMX polling alone and defer Channels entirely without
   losing anything a learner would notice immediately; polling UX trade-offs are covered in the
   nested draft's `research_prior_notification_ux.md` (not repeated here).
5. Web check on hosting cost: running a managed Redis instance (e.g. AWS ElastiCache, Upstash) for a
   channel layer is typically the cheapest tier available (single small node, a few USD/month) but is
   a new recurring line item and a new secret/credential per downstream deployment, on top of the
   ASGI process change in (1). No FLS-specific pricing claim is made here beyond that qualitative
   shape — see Django's own channel-layer docs.

## 4. Existing in-app surfaces for messages

- **Django's `messages` framework is in active use, but only as transient, request-scoped toasts —
  not a persistent notification centre.** `HtmxMessagesMiddleware`
  (`freedom_ls/base/middleware.py:20-77`) injects an out-of-band toast fragment
  (`partials/_toast.html` via `partials/messages.html`) into HTMX responses carrying queued
  messages, so a `messages.success(...)` call surfaces without a full page reload. This has no
  persistence, no per-user unread state, and nothing survives past the response that queued it.
- **No bell icon, no unread badge, no notification centre exists in product code today.** Every
  hit for "bell"/"notification centre"/"unread count" outside `spec_dd/` research and idea prose is
  in `freedom_ls/icons/mappings.py` (an icon name mapping, not a wired-up UI) or unrelated UX-pattern
  research for other in-progress specs (`educator-interface-3-panel-framework-dialogs`,
  `educator-interface-full-polish`). The unified in-app centre the nested draft (`idea.md:88-92`)
  proposes is genuinely new UI, not an existing surface to extend.

## 5. Implications for cutting

**Roughly independent of each other, so they can be separate specs without forcing an order:**

- The `course.completed` / `course.registered` (individual) → single-recipient notification path is
  the cheapest slice: two existing, well-placed hooks (`learner_interface/views.py:1642`,
  `learner_progress/signals.py:143`), one learner recipient each, no audience-resolution or
  cohort-fan-out logic needed. This is the natural "R2/first cut" of the notifications layer.
- Email template/branding work is **done** (email-styling spec) — nothing to build there, just
  extend `base_email.html` per notification template.
- The in-app notification centre UI (bell, unread badge, per-user rows) can be built and shipped on
  HTMX polling alone, with **no dependency on Channels, Redis, or an ASGI rewrite**. Treat "real-time
  over Channels" as a strictly-later enhancement behind the same graceful-degradation seam the idea
  already commits to (§3.4 above), not a blocking prerequisite.

**Genuine prerequisites / blocked-on relationships:**

- **Cohort-scoped notifications (registration, membership add/remove/move) fire nothing today** —
  `learner_progress/signals.py:201-227` deliberately never announces for `CohortCourseRegistration`
  or `CohortMembership`. Naming and firing those events is scoped to
  `spec_dd/1. next/educator-interface-7-learner-administration/idea.md:35`; any comms spec that wants
  "your cohort was registered for X" must either depend on that spec landing first, or duplicate its
  event-naming decision (worse — two specs picking the event name independently is the exact
  collision `domain_vocabulary.md` warns about).
- **"Application approved/rejected" notifications are hard-blocked** on
  `application-review-ui`'s state machine landing (`course_applications/models.py:24-29`) — there is
  no state to change and no signal to hook until that spec ships `application_state_changed`.
- **"Course launched, and you were interested" is hard-blocked** on the `notified_at` field / launch
  hook the `CourseInterest` model docstring defers (`course_interest/models.py:23-25`) — this is a
  net-new event, not something to wire up now.
- **Deadline reminders need a new periodic sweep**, not a signal — there is nothing to hook on
  `CohortDeadline`/`LearnerDeadline` today. If this ships as part of the notifications layer's
  digest mechanism, `fls_run_housekeeping` is the existing scheduled-command seam to extend
  (`retry-sent-emails` is already adding sweeps there), but the digest spec must state its own
  required cadence rather than assume one — housekeeping's schedule is deployment-supplied, not
  built in.
- **Email delivery reliability (per idea.md's own dependency note, `idea.md:191-197`) is being fixed
  by `retry-sent-emails` first** — the notifications layer's email leg should build on
  `OutboundEmail`/`QueuedEmailBackend` post-retry-spec rather than on today's fire-and-forget
  `_send_email_task(payload)`, since the whole point of that spec is that a notification email is
  no longer silently lost on a transient SMTP failure. Sequencing: retry-sent-emails → notifications'
  email delivery leg.
- **Broadcast fan-out to large audiences** needs the async queue, which production already has
  (§2) — but only once a deployment opts `EMAIL_BACKEND` into `QueuedEmailBackend`, which is not
  the default. A comms spec relying on queued mail should say so as an explicit deployment
  requirement, matching how `retry-sent-emails` treats it.

## References

- `freedom_ls/webhooks/events.py:10`, `freedom_ls/webhooks/registry.py:9`,
  `freedom_ls/webhooks/config.py:7`, `freedom_ls/base/webhook_event_types.py:1`
- `freedom_ls/accounts/allauth_account_adapter.py:32-53,127-148`
- `freedom_ls/learner_progress/signals.py:1-227`
- `freedom_ls/learner_interface/views.py:1613-1659`
- `freedom_ls/course_applications/models.py:1-83`
- `freedom_ls/course_interest/models.py:1-49`
- `freedom_ls/form_engine/models.py:395-404`, `freedom_ls/form_engine/signals.py:1-7`,
  `freedom_ls/form_engine/receivers.py:1-25`
- `freedom_ls/learner_management/models.py:159-315`, `freedom_ls/learner_management/deadline_utils.py`
- `freedom_ls/mail/backends.py:1-104`, `freedom_ls/mail/tasks.py:1-45`, `freedom_ls/mail/config.py:1-24`
- `config/settings_base.py:549-557`, `config/settings_prod.py:85-90`
- `freedom_ls/deployment/settings_defaults.py:65-92`, `freedom_ls/deployment/worker.py:185-278`,
  `freedom_ls/deployment/housekeeping.py:221-308`
- `docs/product/deployment.md:9-38`
- `config/asgi.py:1-15`, `config/wsgi.py:1-15`
- `spec_dd/3. done/2026-08-28_19:44_asgi-and-wsgi-name-a-settings-module-that-does-not-exist/idea.md:1-73`
- `spec_dd/3. done/2026-06-15_00:19_email-styling/1. spec.md:1-80`
- `freedom_ls/base/middleware.py:1-77`
- `spec_dd/1. next/retry-sent-emails/1. spec.md` (full file)
- `spec_dd/1. next/educator-interface-7-learner-administration/idea.md:35`
- `spec_dd/1. next/educator-interface-full-polish/application-review-ui/idea.md`

status: ok
