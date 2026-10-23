# Deadlines: integration points in FLS today

Research for cutting `spec_dd/1. next/deadlines/idea.md` into ordered specs. Facts and constraints
only. The existing deadline models are researched elsewhere (another worker); they appear here only
where they touch an integration point. Paths are relative to the repo root. Project vocabulary
(`Learner`, `Cohort`, `Organisation`, `CourseProgress`, `LearnerCourseRegistration`,
`CohortCourseRegistration`) follows `.claude/skills/domain-glossary/SKILL.md`.

## 1. Time-based work

**Nothing in FLS schedules itself.** There is no Celery beat, `django-q` or APScheduler, and the
digest idea lists "any scheduler inside FLS" as out of scope
(`spec_dd/1. next/user-communication-7-email-digests/idea.md`). Two mechanisms exist:

- **Background tasks on `django.tasks`.** `INSTALLED_APPS` has `django.tasks` and `django_tasks_db`
  (`config/settings_base.py:85-86`). `TASKS` is the `ImmediateBackend` in base, dev and tests (runs
  inline, no worker, `settings_base.py:607`) and `fls_defaults.DATABASE_TASKS` in production
  (`config/settings_prod.py:87`). Tasks are `@task()` functions taking only primitives:
  `webhooks/events.py::_dispatch_event_task`, `reports/tasks.py::_generate_cohort_report_task`,
  `comms/tasks.py::deliver_notification`, `mail/tasks.py` (priority `EMAIL_TASK_PRIORITY`). Enqueue
  with `default_task_backend.enqueue(task, args=[...], kwargs={})`.
- **`fls_run_worker` / `HeartbeatWorker`** (`deployment/worker.py`,
  `deployment/management/commands/fls_run_worker.py`). A copy of django_tasks_db 0.12.0's
  `Worker.run()` with a heartbeat touch and a watchdog (`start_watchdog`, `heartbeat_ticker`).
  `django-tasks-db` is pinned `==0.12.0` and a test asserts the pin. Tasks over
  `WORKER_MAX_TASK_SECONDS` (default 1800) get the worker killed, so a sweep must not be one giant
  task.
- **`fls_run_housekeeping`** (`deployment/management/commands/fls_run_housekeeping.py`) runs
  `run_housekeeping_sweeps()` (`deployment/housekeeping.py`) once and exits. **The deployment
  supplies the schedule** (cron, Kubernetes CronJob); FLS names a cadence in docs
  (`docs/product/deployment.md`) but cannot enforce one. Today's sweeps: `prune_db_task_results`,
  `clearsessions`, late-unpicked-task check, `mark_orphaned_running_tasks_failed`,
  `mark_orphaned_running_reports_failed`. Each is wrapped in its own `try/except` against
  `SWEEP_FAILURES = (CommandError, DatabaseError)` so one failure cannot stop the next. The result is
  a `HousekeepingOutcome(sweep_failures, findings, notes)`; a sweep failure withholds the heartbeat
  and exits non-zero, `findings` exit non-zero without withholding, `notes` do neither. Settings are
  `HOUSEKEEPING_*` on `deployment/config.py`.
- **Planned sweeps in the same function.** `retry-sent-emails` (next) adds a due-row requeue sweep
  and states "at least hourly". `file-scanning` (next) adds a pending-upload sweep. Spec 7 of user
  communication adds digest-send and quiet-hours-release sweeps and documents their cadence. The
  roadmap says whichever lands second rebases on `housekeeping.py`. A deadline sweep is a fourth
  contender for the same file.

**What a deadline sweep and an auto-unpause plug into.**

- Both are periodic scans over rows with a datetime, so both are new functions in
  `deployment/housekeeping.py`, called from `run_housekeeping_sweeps()` with their own `try/except`.
  Note the dependency direction: `housekeeping.py` already imports `reports.models`; importing
  `learner_management`/`comms` there adds more cross-app edges (check `docs/app_structure.md` and
  the layering check from test-organisation spec 3).
- **`spec_dd/1. next/user-communication-7-email-digests/idea.md` explicitly excludes**
  "Deadline-approaching reminders or any other new event produced by a periodic scan. Events come
  from features that raise them through spec 1's API." So the deadlines effort owns its own scan and
  its own `raise_notification` calls. Research file
  `spec_dd/1. next/user-communication/research_notification_sources_and_delivery.md` (lines ~62-68,
  229-231) says the same: deadline models have no signals, "approaching/passed" is not an event, a
  periodic scan is the only source, and `fls_run_housekeeping` is the seam.
- Cadence is the deployment's, so any consequence that must fire at the deadline instant cannot rely
  on the sweep. Two ways exist in the code already: **evaluate lazily on read** (the current
  deadline lock is computed at request time in `learner_interface/utils.py::_apply_deadline_locking`
  and `learner_management/deadline_utils.py::is_item_locked_by_deadline`, no stored state), or have
  the sweep write state. An auto-unpause is the second kind by nature (a stored pause ends at a
  time) unless it is also evaluated lazily (`now >= paused_until` read at request time). The sweep
  would then only need to emit the notification and webhook.
- The sweep must be **idempotent and safe to miss**: housekeeping may run late, twice or not at all
  (spec 7 states this as an open item: "send the overdue digest once on the next run, never two for
  the same period"). Reminder state needs a per-recipient, per-deadline "already sent" record.
- **`site_id` in background work.** `SiteAwareManager` filters only inside a request
  (`site_aware_models/models.py:127`, thread-local site). Existing code passes `site_id` explicitly
  and uses `_base_manager` or `.filter(site_id=site_id)`:
  `comms/tasks.py::deliver_notification` (`Notification._base_manager.filter(site_id=site_id)`),
  `reports/tasks.py::generate_cohort_report(report_id, site_id)`,
  `webhooks/events.py::dispatch_event(event_id, site_id)`,
  `housekeeping.py::find_orphaned_running_reports` (`GeneratedReport._base_manager`, "every site's
  rows are in scope"). A sweep therefore iterates all sites (via `_base_manager`) and passes
  `site_id` (an int) into every `raise_notification(site_id=...)` and task arg; `fire_webhook_event`
  takes `site=` and silently does nothing with no request and no `site` (`webhooks/events.py:27-34`).
  The `learner_management/utils.py::fire_webhook_event_on_commit` wrapper already passes `site`.
- The registration-rules effort (in progress, `corporate-job-course-recommendations-2-registration-rules`)
  also needs "evaluation as a background task on `django.tasks`" and an unresolved question "how
  rule-made registrations fire `course.registered` when `fire_webhook_event` does nothing outside a
  request". Whatever it answers is the pattern for a sweep firing deadline webhooks.

## 2. Notifications

**`comms` app, done** (specs 1, 3, 4: `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core`,
`...2026-10-10_08:57_user-communication-3-messaging-policy`, `...2026-10-22_20:02_user-communication-4-direct-messaging`).

- `freedom_ls/comms/notify.py::raise_notification(*, user, category, target, site_id, data)`.
  Validates the category and the `%(placeholder)s` data synchronously, writes the `Notification` row
  in `transaction.on_commit(..., robust=True)`, then enqueues `comms.tasks.deliver_notification` once
  per entry in `NOTIFICATION_DELIVERY_BACKENDS` (default `[]`, so today nothing but the bell).
  `target` is any model (generic key). An FLS category left out of `NOTIFICATION_CATEGORIES` is a
  silent opt-out. Because it uses `on_commit`, calling it from a sweep outside a transaction runs the
  write immediately (Django semantics), which is fine.
- Registry: `freedom_ls/base/notification_categories.py::FLS_NOTIFICATION_CATEGORIES` with
  `NotificationCategory(key, label, icon, message, url_builder, rollup=False, ...)`. Today two:
  `course.registered` (url builder `learner_interface.notification_urls.course_home_url`) and
  `message.received` (rollup). A project extends via `NOTIFICATION_CATEGORIES`
  (`comms/config.py::CommsConfig`). `NOTIFICATIONS_ENABLED` defaults `False`: the bell is hidden but
  rows are recorded anyway.
- `rollup=True` categories: while a user's notification for the same target is unread, a new event
  updates that row (bumps `created_at`, clears `seen_at`) and enqueues no delivery.
- `mark_notifications_read(user, target, site_id, condition)` is how opening the target clears a
  notification.

**Pending.**
- `user-communication-2-notification-email` (next; depends on `retry-sent-emails`, also next): email
  as a `NotificationDeliveryBackend` (`comms/delivery.py`, base class `deliver(notification)`), per
  category immediate-or-off preferences, per-site defaults row, one-click unsubscribe. Delivery
  contract (roadmap): the backend re-reads the notification at send time and skips if `read_at` is
  set; text comes from `Notification.message` at send time. Open there: always-emailed categories
  that users cannot turn off (a deadline reminder is a candidate).
- `user-communication-7-email-digests` (next; depends on 2): daily/weekly digests and quiet hours via
  a new `fls_run_housekeeping` sweep, timezone from the recipient, no user timezone field exists
  today. Open there: which categories may not wait for a digest or quiet hours (time-sensitive
  deadline reminders are the obvious case). Until 2 and 7 land, deadline notifications are in-app
  only.
- Not built: preferences, pop-up alerts, retention, SMS/push.

**The `notifications` skill (`.claude/skills/notifications/SKILL.md`) says:**
- Default is **no**. Raise only if (1) someone/something else caused it, or (2) it is "a reminder the
  user would thank us for... time-sensitive and missing it has a real cost: a deadline approaching".
- Plus all of: user is not the actor; user cannot already see it on the page they land on; it needs
  the user; they would thank us.
- Its example table lists "Deadline approaching on a course not yet complete: **Yes, if built**" and
  "Cohort registered for a course / learner added to a cohort: Yes, once built".
- A burst of events about one target is one notification (`rollup=True`). One event, one
  notification (a learner reached by two paths hears once). A notification and a webhook are
  separate: keep firing the webhook.
- **It says nothing specific about educator-facing "learner at risk" notifications.** The test would
  have to be argued: the educator is not the actor and the cause is system-observed, but the
  "can't already see it" and "reasonable person would thank us" tests, and the burst rule (a busy
  week of many learners going overdue), apply; the checklist's "How often can it fire for one user?
  Would a busy week make the bell unreadable?" is the binding question. This pushes toward a rollup
  category per cohort/course or a dashboard list rather than one notification per learner.
- A new category needs the five-question checklist in the spec (actor, what they would see without
  it, what they do with it, frequency, email-urgent or in-app enough).
- Constraint to carry into any deadline spec: learner-facing lifecycle events that the learner
  causes (pausing themselves, if learners can) must not notify the learner; an educator-initiated
  extension or pause does (somebody else acted).

## 3. Configurable policy patterns

**Messaging policy (`freedom_ls/messaging_policy/`, done spec 3).**
- Swappable class: `MESSAGING_POLICY` setting (default
  `freedom_ls.messaging_policy.policy.LayeredMessagingPolicy`), contract in
  `comms/messaging_policy.py` (`MessagingPolicy`, `MessagingDecision`, `MessagingRefusal`),
  loaded by `comms/messaging_loader.py::get_messaging_policy`, validated by Django system checks
  (`messaging_policy/checks.py`).
- Layered rows, one table per level, each a one-to-one with `related_name="messaging_config"` so a
  reverse LEFT JOIN resolves a chain in one queryset: `SiteMessagingConfig` (unique per site),
  `OrganisationMessagingConfig`, `CohortMessagingConfig`, `LearnerMessagingConfig`,
  `LearnerCourseRegistrationMessagingConfig`, `CohortCourseRegistrationMessagingConfig`
  (registration rows carry only the course-peer flag). Abstract `MessagingFlags` supplies three
  tri-state flags (`inherit`/`open`/`closed`), each guarded by a `CheckConstraint`.
- Resolution: `messaging_policy/resolver.py` with `LAYER_ORDER = ("learner", "registration",
  "cohort", "organisation", "site", "settings")`. `resolve_flag(layers)` returns the first value
  not `None`/`inherit`; `resolved_flag_expression(layers)` is the SQL twin (`Coalesce(NullIf(F,
  "inherit"), ...)`) for queryset use. A new layer is one more tuple entry. The settings layer
  (`config.MESSAGING_DEFAULT_FLAGS`) is always present. Missing row equals all-inherit.
- Edited in the Django admin only (roadmap: "an educator-interface screen is out of scope").
- Known sharp edge: a learner can hold several `Learner` rows (one per organisation) and several
  registrations for a course (cohort and individual); the policy combines them with "any path that
  resolves open" for messaging. A deadline policy needs an explicit rule for "which registration
  governs": `learner_management/queries.py::learner_for_course` already answers "which Learner/
  registration does work for this (user, course) land under" (cohort registration beats
  individual; `ResolvedRegistration(learner, registration)`), and `CourseProgress` is bound to exactly
  one registration (`learner_registration` xor `cohort_registration`, check constraint
  `course_progress_has_exactly_one_grant`).

**`COURSE_ACCESS_BACKEND`** (`course_access/config.py`, `backends.py`, `loader.py`). A required
setting string naming a `CourseAccessBackend` subclass (project default
`course_applications.backends.ApplicationCourseAccessBackend`; core fallback
`FreeOnlyCourseAccessBackend`). Contract objects: `CourseAccessDecision(cta_label, cta_url,
can_self_register, can_access_content, ...)`, `AccessBadge`, `DashboardContribution`. The loader
wraps any backend in `VisibilityEnforcingBackend` so no backend can bypass coming-soon/hidden.
`Course.access_config` is a JSON blob owned by the backend (`validate_course_config`, called at
content load, from a system check, and defensively in `get_access`). The registration-rules effort
reuses this seam style for "rule kind" (decision 14).

**`freedom_ls.base.app_settings`** (`base/app_settings.py`). `AppSettings` subclass with
`declared_settings = {NAME: Setting(default=..., required=False)}`; `config.NAME` returns the
project's Django setting or a deep-copied default, `required` raises `ImproperlyConfigured` on read;
`required_settings_errors(config, app_label)` builds `<app>.E001` checks. Existing config classes:
`CommsConfig`, `CourseAccessConfig`, `DeploymentConfig`, `LearnerManagementConfig`. Note
`learner_management/config.py` already declares `DEADLINES_ACTIVE` (default `True`).

**Reuse for a deadline policy.**
- *Layered most-specific-wins* (resolver + one-to-one config rows per level + settings default) fits
  "consequences differ by course, cohort, organisation" directly. Constraints: the messaging
  `MessagingFlag` is a three-value tri-state and `MessagingFlags` is flag-specific. Deadline policy
  values are richer (consequence enum, reminder offsets, pause limits as numbers or lists), so the
  resolver pattern (`LAYER_ORDER`, first non-inherit wins, SQL twin) transfers but the flag field
  does not. Each non-flag value needs its own "unset" sentinel (null) instead of `"inherit"`. Which
  layers apply is a decision for the specs: the `Course` is not in messaging's layer list (no role
  or messaging flag is course-scoped), while the deadlines idea explicitly wants per-course.
- *Swappable class* (`COURSE_ACCESS_BACKEND`/`MESSAGING_POLICY` style: setting string, loader,
  system check, base class with `NotImplementedError` methods, contract dataclass return) fits "if
  it makes sense to allow different deadline backends". Course-access is the closer analogue because
  the backend is called on a hot path (course player, TOC) and must stay cheap; messaging's policy
  is already query-heavy.
- Both patterns store config in the Django admin only; the educator-interface screen is a separate
  concern.

## 4. Consequence enforcement points

There is **no pause or end-date concept** for a registration. The only switches are
`LearnerCourseRegistration.is_active`, `CohortCourseRegistration.is_active`, `Cohort.is_active` and
`Learner.is_active`. `learner_management/learner_actions.py::register_for_course` /
`unregister_from_course` flip the first and rely on `post_save` receivers in
`learner_progress/signals.py` to fire `course.registered` / `course.unregistered`.

**Course-level ("course access ended", paused, expired).**
- `learner_management/utils.py::is_registered_for_course` and
  `learner_management/queries.py::is_registered_for_course_expression` are the single definition of
  "has access through a registration". Both go through
  `queries.py::access_granting_cohort_registrations()` (`is_active=True, cohort__is_active=True`),
  documented as the one place nobody can forget `Cohort.is_active` (progress fan-out deliberately
  does not use it, so inactive-cohort members keep their records).
- `course_access/backends.py::_free_access_decision` returns `can_access_content=True` iff
  `is_registered_for_course`. `FreeOnlyCourseAccessBackend.get_access` and (via inheritance)
  `ApplicationCourseAccessBackend` use it. `VisibilityEnforcingBackend` exempts registered users
  from coming-soon/hidden, so changing the meaning of "registered" also changes who sees hidden
  courses (`filter_visible` uses `is_registered_for_course_expression`).
- The player chokepoint is `learner_interface/views.py::_course_access_redirect` (hidden-404 then
  `get_course_access_backend().get_access(...).can_access_content`, else redirect to
  `course_detail`). It is called by `view_course_item`, `form_start`, `form_fill_page`,
  `course_form_complete`, `form_submit_and_exit`; `course_home` and `course_detail` call the backend
  directly.
- Consequence if "access ended" is implemented by flipping `is_active`: the course drops out of
  the dashboard "In progress" list (`_annotate_registered_courses`), `learner_for_course` stops
  resolving, a re-registration reactivates the same row (progress kept, `registered_at` unchanged
  because `auto_now_add`), and `course.unregistered` webhooks fire. A paused-with-resume learner
  should probably not look "unregistered" to integrators, so a separate state read by the same
  predicate is the other option. The `latest_registration` docstring notes a removed learner is
  deliberately still reachable for deadlines ("Filtering instead would cut a removed learner off from
  their own deadlines").
- A backend-level enforcement (a deadline-aware wrapper like `VisibilityEnforcingBackend`, applied
  by the loader) would cover every route that already calls `get_access`, with the TOC/CTA reading
  the `CourseAccessDecision` (extra fields would be additive; callers read only the four contract
  fields). `CourseAccessDecision` has no "why not" field today.

**Item-level ("locked/closed content item").**
- Existing path: `learner_interface/utils.py::get_course_index` builds each TOC entry's
  status (`BLOCKED`/`READY`/`IN_PROGRESS`/`COMPLETE`/`FAILED`); `_apply_deadline_locking` forces
  `BLOCKED` and `url=None` for non-complete items whose most permissive hard deadline passed (gated
  on `config.DEADLINES_ACTIVE`, `learner_management.config`). `derive_part_status` rolls children up.
- The player re-checks in `view_course_item`: `if config.DEADLINES_ACTIVE and ...
  is_item_locked_by_deadline(...)` (`views.py:991-1002`), then the sequential-unlock gate
  `_blocked_item_redirect(...)`, which redirects when `current_entry_status(course_index) == BLOCKED`.
  `form_start` and `form_fill_page` call only `_blocked_item_redirect`, which reads the same index,
  so a deadline lock reaches forms through the index status rather than through
  `is_item_locked_by_deadline`. Two sources of truth to keep in step.
- Deliberate exemptions (comments in code): `course_form_complete` has no gate ("a learner is always
  entitled to the score they earned — including after a deadline has closed the quiz itself");
  `form_submit_and_exit` has no gate ("refusing it would strand that attempt incomplete").
  `_is_content_item_completed` scopes completion to the `CourseProgress` record so the same topic
  completed under another registration does not unlock this one. A "closed" consequence for
  in-progress attempts must decide these cases explicitly.
- Topic completion is a POST inside `view_topic` (`mark_complete` -> `TopicProgress.complete_time`),
  reached only via `view_course_item`, so the player gate covers it. Form completion is
  `form_progress.complete()` in `form_fill_page` after `_blocked_item_redirect`.
- `learner_progress` has no deadline logic. Progress recalculation is signal-driven:
  `recalculate_course_progress_on_save` (`TopicProgress`), `recalculate_course_progress_on_form_attempt`,
  `update_course_progress_on_completion`; course completion sets `CourseProgress.completed_time` and
  fires `course.completed`. A consequence such as "no credit after the deadline" would have to live in
  these signal paths or in what counts as complete; today neither knows about time.
- `learner_progress/queries.py::registrations_with_progress_for_learner` (-> `LearnerRegistrationProgress`)
  and `course_progress_by_course_for` feed the educator learner pages and dashboard.
- Soft vs hard: the existing locking recognises `is_hard_deadline` (hard = lock after expiry, soft =
  badge only). Everything else a consequence could do (mark late, notify an educator, restrict to
  review, end course access) is new.

## 5. Educator interface

**State (done: educator-interface 1 to 7 and 9, plus `educator-interface-looks-good`; 10 in progress;
8, 11, 12 next).** `freedom_ls/panel_framework/` (Panel, PanelStack, TabSet, DataTable, PanelAction,
FormPanelAction, QuickView, bulk actions) and `freedom_ls/educator_interface/` built on it:
`educator_interface/views.py` (organisation-scoped sections `CohortConfig`, `LearnerConfig`,
`CourseConfig`, `MessagesConfig`, `MemberConfig`, `DashboardConfig`, request class
`OrganisationScopedRequest`), `actions.py`, `events.py` (`LEARNER_CHANGED`, `COHORT_CHANGED`,
`REGISTRATION_CHANGED`, `MEMBER_CHANGED` HTMX refresh events), `quick_views.py`
(`LearnerQuickView`, `CohortQuickView`), `members.py`.

**Where deadline UI would live today.**
- *Learner detail* (`LearnerInstanceView`, `LearnerTabSet` tabs overview/courses/history):
  - Overview stack has `LearnerRegistrationsPanel` (registration rows with `UnregisterLearnerFromCourseAction`
    and `ReregisterLearnerForCourseAction`, per-row, modal confirmation, refresh on
    `LEARNER_CHANGED`/`REGISTRATION_CHANGED`). A per-registration "extend / pause / resume" action sits
    next to these; they show the pattern (`renders_in_footer = False`, `capability`, a
    `registration` param, `_registration_changed_response`).
  - Courses tab: `LearnerCoursesPanel` (per-registration progress via
    `visible_registrations_with_progress`) is where per-item deadlines would be listed. Spec 10 owns
    the learner drill-down here ("spec 7 leaves the slot").
  - History tab: `LearnerHistoryPanel`, the slot for the audit log (spec 11).
  - `LearnerQuickView` (`quick_views.py`): last active, memberships, registrations; a compact
    due/paused summary would go here.
- *Cohort detail* (`CohortInstanceView`, tabs overview/learners/courses/settings): `CohortCoursesPanel`
  lists `CohortCourseRegistration` rows with `Register`/`Unregister` actions (cohort-level deadline and
  cohort-wide extension belong here); `CohortCourseCompletionPanel` shows completion per registration.
- **`CohortNeedsAttentionPanel` is an empty stub** (`views.py:907`;
  `templates/educator_interface/panels/cohort_needs_attention.html` has a TODO: "list the learners
  ... who need an educator's attention, such as stalled or overdue progress, once something computes
  that"). An at-risk list for overdue/approaching learners has an obvious home. Existing
  at-risk logic is the cohort report's `reports/at_risk.py` (`AT_RISK_RULES`: `NoRecordedActivityRule`,
  `FailedLatestQuizAttemptRule`, `InactiveForDaysRule(days=7)`; protocol `AtRiskRule.evaluate(
  LearnerDetailLike) -> str | None`, evaluated in `reports/gather.py::_evaluate_at_risk_flags`).
  Adding an "overdue" rule means extending `LearnerDetailLike` with deadline data; the roadmap says
  spec 10 will define the statuses "in `reports`, used by the dashboard, the lists and the badges".
  `educator-interface-10-reporting-dashboards` (in progress) will build the organisation dashboard's
  needs-attention list and the cohort report tab and explicitly puts **deadlines out of scope**.
- The "Educator interface rebuild" section of the roadmap says "Deadlines, in any form" are out of
  scope for all twelve and "existing deadline data is neither shown nor touched". So no educator UI
  for deadlines exists; the deadlines effort adds panels to views that specs 6/7 own (cohort and learner detail).

**Permissions** (`role_based_permissions/roles.py`, `BASE_ROLES`; renamed in spec 5):
`site_admin` (site scope), `organisation_admin`, `cohort_admin`, `cohort_viewer` (object scope), plus
placeholders `system_admin`, `learner`, `observer`. Capabilities are Django permission strings,
e.g. `freedom_ls_learner_management.change_learnercourseregistration` (held by `site_admin`,
`organisation_admin`, `cohort_admin`), `change_cohortcourseregistration` (same three),
`view_learner`/`view_cohort` (all four), `download_cohort_report` (all four). `cohort_viewer`
changes nothing. Panels and actions declare `capability = "<perm>"`; visibility checks go through
`learner_management/capabilities.py::can(user, capability, scope)` and `queries.py::cohorts_visible_to`
/ `learners_visible_to`. Denied experience: organisation/instance scope is a 404, a visible but
forbidden action is a 403 with a message, unusable controls are hidden. A new "extend deadline" /
"pause" capability needs a new permission added to `roles.py` plus a data migration (the file notes
"create data migrations for them") and a role-membership decision (`organisation_admin` and
`cohort_admin` are the natural holders; roles hand out their own level and below).

**Audit log** (`spec_dd/1. next/educator-interface-11-audit-log/idea.md`, next, ready): one
append-only site-aware model; fixed past-tense vocabulary "one entry per capability in the spec 5
matrix"; every action in specs 6 to 9 writes one entry per object inside the action's transaction;
history tabs on learner and cohort detail; role utilities close six `# TODO: AuditLog entry`
comments. Constraints for deadlines: extending a deadline, pausing, resuming and any consequence
applied by staff are exactly the kind of action it records. Whether a deadline spec lands before or
after spec 11 changes who adds the vocabulary: after spec 11 the deadline actions write entries
(vocabulary extension is an open item there: "whether a downstream project can extend the
vocabulary"); before it, spec 11 must retrofit. Automatic changes (sweep-driven unpause) are "system
actions" with a null actor, which the model allows.

## 6. Learner interface

Where a learner sees status today (`learner_interface/views.py`, `utils.py`, templates):
- **Dashboard** (`dashboard`, `_dashboard_sections`, `_in_progress_section`): sections of course
  cards; each registered course annotated by `_annotate_registered_courses` with
  `CourseListingEntry(course, status: CourseListingStatus, progress_percentage, access_badge)` where
  `CourseListingStatus` is NOT_REGISTERED/REGISTERED/IN_PROGRESS/COMPLETE/COMING_SOON. No due date or
  paused state appears on cards. `CourseAccessBackend.get_dashboard_contributions` lets a backend
  add panels without `learner_interface` naming it (a deadline panel could be a backend
  contribution; `DashboardContribution(template_name, context)`).
- **Course detail** (`course_detail`, `templates/learner_interface/course_detail.html`): hero stats
  (a "Duration" stat uses the `deadline` icon), CTA from `_detail_cta_label`/`_detail_start_url`, and
  the table of contents partial `partials/course_minimal_toc.html` with a `deadline-badges` partial
  showing each item's deadlines (`child.deadlines`, hard vs soft style, `d M` date) when
  `config.DEADLINES_ACTIVE`. `partials/course_status_eyebrow.html` shows the course status line.
  This is where course-level "ends on" / paused banners and per-item due dates would show.
  Course-level deadlines currently fall back onto items with none (`_get_deadlines_for_item` ->
  `deadlines_map.get((None, None))`).
- **Course player** (`view_course_item` -> `view_topic` / `view_form`, `_player_chrome_context`): the
  player shows the TOC chrome and prev/next; blocked items bounce to `course_detail`.
  `course_form_complete` (score after quiz) and `course_finish` (completion page).
- **Notification bell** (header, `comms_tags`) and notification centre exist; `NotificationCategory`
  carries `url_builder` (e.g. `learner_interface/notification_urls.py::course_home_url`) that a
  deadline category would reuse.
- No learner-initiated pause control exists anywhere; a learner "pause" action would be a new
  authenticated POST in `learner_interface` (HTMX, 422 for validation errors per `CLAUDE.md`) and, per
  the notification skill, must not notify the learner about their own action.
- Many existing tests assert the current deadline UI (`learner_interface/tests/views/test_course_player.py`
  has ~51 mentions, `learner_management/tests/test_deadline_utils.py`, `test_models.py`,
  `test_admin.py`); a replacement removes or rewrites them. QA helper commands in
  `freedom_ls/qa_helpers/management/commands/qa_create_*deadline*.py` (4 files) seed the old models.

## 7. Webhooks

Registry: `freedom_ls/base/webhook_event_types.py::FLS_WEBHOOK_EVENT_TYPES` (+ `WEBHOOK_EVENT_TYPE_SAMPLES`
for the admin test button); projects extend via `WEBHOOK_EVENT_TYPES` (`webhooks/config.py`).
Existing events: `user.registered`, `course.completed`, `course.registered`, `course.unregistered`,
`cohort.course_registered`, `cohort.course_unregistered`, `learner.added`, `learner.deactivated`,
`learner.reactivated`, `cohort.member_added`, `cohort.member_removed`. No deadline, pause, extension
or overdue event exists.

Firing: `webhooks/events.py::fire_webhook_event(event_type, payload, site=None)` validates the type
against the registry, resolves the site (argument, else request thread-local, else returns silently),
creates a `WebhookEvent`, and enqueues `_dispatch_event_task(event_id, site_id)`, which fans out to
active `WebhookEndpoint`s subscribed to the type (explicit `site_id` filter, circuit breaker,
unique `(event, endpoint)` row for at-least-once idempotency). Callers: `learner_progress/signals.py`
(registration/completion), `learner_interface/views.py:1646` (course finish), `learner_management/utils.py`
and `learner_actions.py::_fire` (via `fire_webhook_event_on_commit(..., site=...)`),
`accounts/allauth_account_adapter.py`.

Do deadline events fit? Yes in shape: they are system-observed domain events with an organisation,
learner and course in the payload (payload convention: `user_id`, `user_email`, `organisation_id`,
`learner_id`, `course_id`, `course_title`). Candidates: deadline approaching/missed, deadline
extended, registration paused/resumed/expired. Constraints: (a) a sweep has no request so it must
pass `site=` (see section 1); (b) the sweep may run twice, so the event needs an idempotency marker
(the same record that guards the notification); (c) events are added in the base list plus a sample
payload, and `webhooks/forms.py` builds its picker from `FLS_WEBHOOK_EVENT_TYPES`; (d) the
registration-rules effort has an open question about how background-made registrations fire
`course.registered`; (e) integrators receive webhooks for actions users caused, notifications do not.

## 8. Other in-flight specs that touch the same files (collisions)

Source: `spec_dd/1. next/roadmap.md` and the idea files. None of these mention deadlines as scope;
the collisions are on files.

| Spec (status) | Shared area | Note |
|---|---|---|
| `retry-sent-emails` (next, ready) | `deployment/housekeeping.py`, `mail/` | Adds a sweep and states an "at least hourly" cadence; whichever lands second rebases. Needed before `user-communication-2`. |
| `file-scanning` (next, ready) | `deployment/housekeeping.py` | Adds a pending-upload sweep (spec says sweep or management command). |
| `user-communication-7-email-digests` (next) | `deployment/housekeeping.py`, `docs/product/deployment.md` cadence wording | Sweep cadence the deadline sweep should share. Explicitly excludes deadline reminders. |
| `user-communication-2-notification-email` (next) | `comms/`, category flags | Open: always-emailed categories; deadline reminders qualify as time-sensitive. |
| `user-communication-5-educator-messaging`, `-6-moderation`, `-8-realtime` (next) | `comms/`, educator thread views | Little overlap; 5 edits the educator quick view that a deadline summary may also edit. |
| `educator-interface-10-reporting-dashboards` (in progress) | `educator_interface/views.py` (dashboard, cohort report tab, learner courses tab), `reports/` (at-risk statuses) | Out of scope: "Deadlines". Owns the needs-attention list and the single status definition the deadline "overdue" status should plug into; deadlines must follow its status vocabulary. Also `test-organisation-and-hygene-11-reports`. |
| `educator-interface-8-bulk-operations` (next, ready) | `learner_management`, panel bulk actions | Bulk "extend deadline" would be a later bulk action. |
| `educator-interface-11-audit-log` (next, ready) | `role_based_permissions/utils.py`, every educator action | See section 5: ordering decides who writes the vocabulary. |
| `educator-interface-12-docs-and-polish` (next) | `docs/product/educator-interface.md`, upgrade notes | Docs would need deadline sections or a note. |
| `corporate-job-course-recommendations-2-registration-rules` (in progress), `-3`, `-4`, `-5` (next) | `LearnerCourseRegistration` (adds provenance), `learner_management/admin.py` (`LearnerAdmin` inline), self-registration view in `learner_interface`, background `django.tasks` evaluation | Their decision 3 says no rule-filled cohorts because "those change what cohort reports, cohort deadlines and cohort-scoped roles see". Relative due dates (README item 13, "fold this into [the deadlines rework]") and recertification (item 11) are out of scope there and must "agree with rules". |
| `test-organisation-and-hygene-8-learner-management-and-progress`, `-13`/`-14-learner-interface-part-1/2`, `-7-course-access-and-applications` (next) | Tests of `learner_management`, `learner_progress`, `learner_interface`, `course_access` | Deadline tests live in the same directories (`learner_management/tests/test_deadline_utils.py`, `learner_interface/tests/views/test_course_player.py`); moves and rewrites collide. Move test files in their own commit. |
| `compliance-form-randomization` (in progress), `form-engine-branch-logic` (next) | `form_engine`, `learner_interface` form views | `form_fill_page` and quiz flow are shared with any item-closed enforcement. |
| `in-app-feedback`, `content_snapshots`, `anon-application-improvements`, `panel-framework-looks-good` (in progress) | Not deadline-related; `panel-framework-looks-good` touches panel_framework visuals | Low risk. |
| `deadlines/research_lms_deadlines_landscape.md` (this directory) | Sibling research | Another worker; not reviewed here. |

Existing deadline code touches (for a removal spec): `learner_management/models.py` (3 models),
`learner_management/deadline_utils.py`, `admin.py` (inlines and 3 admins), `config.py`
(`DEADLINES_ACTIVE`), `queries.py` (docstring), `factories.py`; `learner_interface/utils.py`,
`views.py`, `partials/course_minimal_toc.html`; `icons/mappings.py`/`semantic_names.py` ("deadline"
icon); `qa_helpers` commands; `role_based_permissions/registry.py` (12 mentions);
`contrib/conformance/tests`. Past specs: `spec_dd/3. done/2026-02-19_19:25_deadlines/` and
`2026-02-21_16:30_deadlines_deactivate/`.

## Constraints to carry into the cut (not a design)

1. A time-driven consequence cannot rely on housekeeping firing on time; deployments schedule it.
   Either evaluate on read or make the sweep tolerant of lateness.
2. Every sweep and task passes `site_id` explicitly and uses `_base_manager`/explicit filters; the
   webhook needs `site=`.
3. `deployment/housekeeping.py` is a merge-hot file (three other specs add sweeps).
4. Spec 7's digest idea refuses to own deadline reminders; the deadlines effort owns the scan, the
   category (checklist in the `notifications` skill), and the email-urgency question.
5. No pause/end-date state exists; `is_active` on registration, cohort registration, cohort and
   learner is the only access switch, and it also drives dashboard listing, webhooks and progress
   resolution.
6. Two enforcement paths for item locks exist (`is_item_locked_by_deadline` in `view_course_item`,
   and the TOC `BLOCKED` status read by `_blocked_item_redirect`); results pages and
   `form_submit_and_exit` are deliberately ungated.
7. New educator capabilities need `roles.py` entries plus data migrations; `cohort_viewer` must stay
   read-only.
8. Educator interface deadlines are explicitly out of scope of specs 1 to 12 and spec 10; the stub
   `CohortNeedsAttentionPanel` and `reports/at_risk.py::AT_RISK_RULES` are the existing hooks.

status: ok
