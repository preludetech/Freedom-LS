# Research: reference implementations of an application-level audit log

Topic: `reference_implementations`. Question: how do reference systems solve a staff-readable audit log of administrative actions?

Provenance note: Wagtail's `register_log_actions` hook was checked against its docs this session (https://docs.wagtail.org/en/stable/reference/hooks.html). Everything else is from the researcher's prior knowledge of the projects and was NOT re-fetched. Treat field names and defaults as "verify before quoting in the spec". Items I am less sure of are marked (verify).

## 1. Django `django.contrib.admin.models.LogEntry`

- Data shape: `action_time`, `user` (FK, CASCADE), `content_type` (FK, null), `object_id` (text, null), `object_repr` (varchar 200), `action_flag` (smallint: ADDITION=1, CHANGE=2, DELETION=3), `change_message` (text; by convention a JSON list such as `[{"changed": {"fields": ["name"]}}]`, parsed by `get_change_message()` into a translated sentence).
- Naming: a closed three-value integer enum. No extensibility. Too coarse for FLS.
- Target survival: `object_repr` is a stored label, `object_id` is text, and the content type FK is nullable. A deleted target still reads. This is the pattern the idea already adopts.
- Bulk: not modelled. Admin actions log one entry per object (`log_deletions` / `log_actions` use `bulk_create`).
- Display: admin "History" tab per object and "Recent actions" sidebar. Filterable only through the admin changelist.
- Retention: none. Rows are never pruned. `user` CASCADE means deleting a user deletes their history, a flaw to avoid (use SET_NULL plus a stored actor label).
- Ref: https://docs.djangoproject.com/en/stable/ref/contrib/admin/#logentry-objects

## 2. django-auditlog

- Shape: `LogEntry` with `content_type`, `object_pk` (text), `object_id` (bigint, indexed, null), `object_repr`, `action` (create/update/delete/access), `changes` (JSON field-diff), `changes_text`, `actor` (FK SET_NULL), `remote_addr`, `timestamp`, `additional_data` (JSON), `cid` (correlation id for grouping a request/bulk), `serialized_data` (optional).
- Naming: four fixed CRUD actions. Registration is per model with `auditlog.register(Model, exclude_fields=...)`, which hooks signals.
- Survival: `object_repr` + `object_pk` text. Deleted targets stay readable.
- Bulk: signals do not fire for `bulk_create`/`update`; newer versions have opt-in support. The `cid` is a useful idea: a shared correlation id ties entries from one bulk run.
- Display: admin read-only; a `LogEntry` per-object history mixin. Filter by actor, action, content type, date.
- Retention: management command `auditlogflush` (`--before-date`, `--days`/`--yes`) and a `AUDITLOG_LOGENTRY_RETENTION...` style setting in newer releases (verify).
- Lesson: signal-based automatic capture records field diffs but not intent. FLS wants explicit intent-named events, so explicit writer calls are a better fit.
- Ref: https://django-auditlog.readthedocs.io/

## 3. django-simple-history

- Shape: a shadow history table per tracked model, with copies of all fields plus `history_id`, `history_date`, `history_change_reason`, `history_type` (+/~/-), `history_user`.
- Survival: the full row copy survives deletion.
- Bulk: `bulk_create_with_history`, `bulk_update_with_history` utilities.
- Display: admin `SimpleHistoryAdmin` shows a diff history per object.
- Retention: `clean_old_history` command (`--days`, `--auto`).
- Notable: `history_change_reason` is the closest analogue of FLS's optional reason.
- Lesson: field-level snapshots per model. Explicitly out of scope for FLS (no field-level tracking, no restore). It also needs a table per model. Reject.
- Ref: https://django-simple-history.readthedocs.io/

## 4. django-pghistory

- Shape: Postgres triggers write event rows into per-model event tables; `pghistory.Context` middleware attaches request context (user, url) via a session-variable JSON; separate `Events` aggregate views.
- Naming: trigger labels chosen by developer (e.g. `snapshot`, `insert_insert`), so vocabulary is developer-defined per tracker.
- Survival: row snapshot table. Bulk and raw SQL are captured because triggers fire at the DB level.
- Display: no UI shipped beyond admin helpers; you build your own.
- Lesson: DB-level capture is robust against bulk but records low-level row changes, not "learner deactivated" semantics. Also adds migration/trigger weight. Not for FLS, though the idea of context carried alongside events (request, user) is worth noting.
- Ref: https://django-pghistory.readthedocs.io/

## 5. django-easy-audit

- Shape: three tables: `CRUDEvent` (event_type, object_repr, object_json_repr, changed_fields, user, user_pk_as_string, datetime, content_type, object_id), `LoginEvent`, `RequestEvent` (url, method, query_string, remote_ip).
- Survival: `object_json_repr` snapshot and `user_pk_as_string` keep the row readable after the user or object goes.
- Notable: stores `user_pk_as_string` to survive user deletion, a cheap way to keep the actor.
- Display: admin; retention via settings that purge by age (`DJANGO_EASY_AUDIT_...`, verify).
- Lesson: request/login logging mixes concerns; FLS leaves login to axes/allauth.
- Ref: https://github.com/soynatan/django-easy-audit

## 6. Open edX

- `ManualEnrollmentAudit` (student app): `enrolled_by` (FK user, null), `enrollment` (FK to CourseEnrollment, null), `enrolled_email` (stored, so it survives account changes/deletion of the user before registration), `time_stamp`, `state_transition` (choices like `UNENROLLED_TO_ENROLLED`, `ENROLLED_TO_UNENROLLED`, `ALLOWEDTOENROLL_TO_ENROLLED`, ... a transition vocabulary), `reason` (text, optional), `role` (staff/instructor).
- Naming: state transitions rather than verbs. A closed enum in code.
- Survival: stored email plus nullable FKs.
- Bulk: bulk enroll (CSV or batch email list in instructor dashboard) writes one audit row per learner with the same reason. There is no summary row.
- Display: not shown in the instructor dashboard. Viewed in Django admin or SQL. Course Team page itself has no audit.
- Reason: a free text box in the enroll/unenroll form, optional. This is where the idea's "reason, following Open edX" comes from.
- Retention: none.
- Lesson: reason on the removal/deactivation form; stored identifying label; but the Open edX audit is hidden from staff, which FLS fixes with a tab.
- Ref: https://github.com/openedx/edx-platform (common/djangoapps/student/models/ ... `ManualEnrollmentAudit`) (verify path)

## 7. Moodle logstore and events API

- Shape (`logstore_standard_log`): `eventname` (full class name e.g. `\core\event\user_enrolment_deleted`), `component`, `action` (e.g. `deleted`), `target` (e.g. `user_enrolment`), `objecttable`, `objectid`, `crud` (c/r/u/d), `edulevel` (teaching / participating / other), `contextid`, `contextlevel`, `contextinstanceid`, `userid` (actor), `courseid`, `relateduserid` (the affected person), `anonymous`, `other` (serialised extra data), `timecreated`, `origin` (web/cli/ws), `ip`, `realuserid` (when "logged in as").
- Naming: events are PHP classes; name = `component\event\target_action` (past tense verb). Every event class declares `crud`, `edulevel`, `get_name()`, `get_description()`; third-party plugins define their own events in `classes/event/` and are discovered automatically. This makes the vocabulary downstream-extendable by class registration.
- Survival: `objectid` plus `other`; description is rendered from the event class at read time, so a missing object degrades gracefully ("The user with id X ...").
- Bulk: one event per object. Some bulk operations emit per-object events with the same request.
- Display: Site admin > Reports > Logs, filterable by course, user, day, activity, action (c/r/u/d), education level, origin; downloadable. Per-course logs are available to teachers by capability (`report/log:view`).
- Retention: setting "Keep logs for" (`loglifetime`) with a cron task that deletes older rows; default keep forever; options from days to years.
- Lessons: separate "who did it" (`userid`) from "who it happened to" (`relateduserid`), which FLS can express with target + a `learner`-like context; the `crud` flag is cheap filter sugar; the `loglifetime` retention setting matches the idea's prune command; `origin` (web/cli/import) is a useful detail.
- Ref: https://docs.moodle.org/dev/Events_API ; https://docs.moodle.org/en/Logs ; https://docs.moodle.org/en/Logging

## 8. Canvas audit logs

- Shape: separate event streams, each its own API and store: Grade change (assignment, student, grader, grade before/after, `event_type` e.g. `grade_change`), Course (`created`, `updated`, `concluded`, `published`, `deleted`, with `event_data` before/after), Authentication (login/logout), plus Admin/Account changes and Enrollment (`/api/v1/audit/...`).
- Naming: per-stream `event_type` strings in snake_case.
- Survival: ids plus event_data snapshot; linked users included in API response.
- Display: Admin > Account > Admin Tools > Logging, with search by user or course and date range; results are retrieved by API for detail.
- Retention: logs retained for a limited window (documented around 1 year of queryable history; verify).
- Lesson: separate streams per concern are heavier than needed; FLS's one model with an action string is simpler. Date range plus subject search is the minimum viable viewer.
- Ref: https://canvas.instructure.com/doc/api/ (Grade Change Log, Course Audit log, Authentication Audit log); https://community.canvaslms.com (Admin Tools Logging)

## 9. Sentry / GitLab / GitHub audit events

- Sentry `AuditLogEntry`: `organization_id`, `actor` (user, null), `actor_label` (stored text so it survives), `actor_key` (API key), `target_object` (int), `target_user`, `event` (integer id mapped through `audit_log.get_event_id`), `ip_address`, `data` (JSON), `datetime`. Events registered in `audit_log.py` as `AuditLogEvent(event_id, name="member.add", api_name="member.add", template="add member {email} to org with role {role}")`. Template strings are rendered from `data` at read time. Organisation-scoped; owners/managers view and filter by event and actor; fixed retention of 90 days on SaaS (verify), unbounded self-hosted.
- GitLab audit events: `author_id`, `author_name` (stored), `entity_id`/`entity_type` (project/group/user scope), `target_id`, `target_type`, `target_details` (stored label), `event_name` (e.g. `member_created`, `project_destroyed`), `details` (JSON), `ip_address`. Streaming to external sinks. Filters by actor, entity, date; retention not pruned by default.
- GitHub org audit log: dotted `category.action` names (`org.add_member`, `repo.remove_member`, `team.add_member`), fields `actor`, `user` (target), `org`, `repo`, `action`, `created_at`, `reason`/`operation_type` (`create|modify|remove|...`). Query language filters `action:org.*`, `actor:`, `created:`. Retention: 180 days in the UI, 7 days of Git events (verify).
- Common conventions: `noun.verb_past` or `noun_verb` (`member.added`); actor label stored; target type + id + label; organisation as the scoping key; JSON `data` for specifics; templated messages; filter by actor/action/date; time-boxed retention plus export.
- Refs: https://github.com/getsentry/sentry/blob/master/src/sentry/audit_log/events.py ; https://docs.gitlab.com/ee/administration/audit_events.html ; https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/reviewing-the-audit-log-for-your-organization

## 10. Wagtail log entries and action registry

- Shape: abstract `BaseLogEntry` with `content_type` (FK, null, for target), `label` (stored text, so the entry reads after deletion), `action` (string e.g. `wagtail.create`, `wagtail.publish`, `wagtail.delete`), `data` (JSON), `timestamp`, `uuid` (groups related entries, like a correlation id), `user` (FK, null SET_NULL), `deleted_user_label`, `content_changed`, `deleted` (boolean, set when the target is removed so UI can say so). Concrete: `ModelLogEntry` (any model, `object_id` as text) and `PageLogEntry` (FK to page, `revision`).
- Naming: dotted `app.verb` strings; third parties use their own prefix.
- Registry (checked against docs): `@hooks.register("register_log_actions")`, function receives `actions`; call `actions.register_action("pkg.echo", _("Echo"), _("Sent an echo"))` with action string, label, message. For messages that depend on `data`, subclass `wagtail.log_actions.LogFormatter`, set `label`, implement `format_message(self, log_entry)` and use `@actions.register_action("pkg.greet")` as a decorator. Registry also drives the filter dropdown labels.
- Bulk: `log(instance, action, user=..., data=...)` per object; a bulk action helper creates a `uuid` shared across the batch (`log_bulk`-style) (verify).
- Display: Reports > Site history, filterable by action, user, date range, content type; per-page History tab with the same rendering; messages come from the registry.
- Retention: setting `WAGTAILADMIN_LOG_ENTRY_RETENTION...` (later versions) and `purge_log_entries` command (`--days`) (verify names).
- Ref: https://docs.wagtail.org/en/stable/reference/hooks.html ; https://docs.wagtail.org/en/stable/extending/audit_log.html (verify)

## Cross-cutting comparison

| Concern | Common solution |
| --- | --- |
| Actor survives deletion | FK SET_NULL plus stored label (Sentry `actor_label`, Wagtail `deleted_user_label`, easy-audit `user_pk_as_string`, GitLab `author_name`). Django LogEntry CASCADE is the counterexample. |
| Target survives deletion | Content type + text object id + stored label (LogEntry `object_repr`, Wagtail `label`, GitLab `target_details`). |
| Action naming | Past tense, dotted or snake: `member.added`, `member_created`, Moodle `target_action`, Wagtail `wagtail.create`. Fixed enum only in Django and Open edX. |
| Registered vocabulary | Wagtail registry hook (label + message + formatter), Sentry event table with templates, Moodle event classes. |
| Bulk | Either one row per object (Django, Open edX, Moodle) or a shared correlation id (auditlog `cid`, Wagtail `uuid`). None records a summary row, which the idea does. |
| Display | Per-object history tab plus organisation-wide log filtered by actor, action, date. Message rendered at read time from action + data. |
| Reason | Open edX `reason`, simple-history `history_change_reason`, GitHub `reason`. Always optional text. |
| Retention | Keep forever by default (Django, Moodle default, GitLab); explicit purge command or "keep for" setting (auditlogflush, clean_old_history, Moodle loglifetime, Wagtail purge). Time-boxed on SaaS (Sentry, GitHub, Canvas). |

## What FLS should borrow

1. Model shape: one concrete append-only model. `actor` FK SET_NULL plus `actor_label` text (Sentry, Wagtail); `content_type` (null) + `object_id` as text + `target_label` (LogEntry, Wagtail); `organisation` FK as scoping key (Sentry, GitHub); `timestamp` indexed; `action` string; `reason` text blank; `data` JSON. Do not CASCADE from the user.
2. Action vocabulary: past-tense `noun.verb` strings (`learner.deactivated`, `membership.moved`, `role.granted`), the idea's list mapped to dotted names. Pick one convention and use it for the product docs and UI (the idea requires that).
3. Registry (the Wagtail idea): a small FLS registry mapping action string to a label and a message formatter that reads `data`; the log writer rejects unregistered actions; the filter dropdown reads the registry. This answers the open "can downstream extend the vocabulary" question: expose a registration function or setting, with namespacing by a prefix so downstream strings cannot collide. Messages rendered at read time (Sentry templates, Moodle `get_description`), not stored, so wording can improve.
4. Bulk: a summary entry with counts and per-object detail in `data` (the idea), plus optionally a shared correlation id (Wagtail `uuid`, auditlog `cid`) if per-object entries ever coexist with a summary. Moodle/Open edX per-object rows are what the single-object actions already write.
5. Moodle's actor versus affected-person split: store a `related`-learner reference or put the affected learner into `data` so the per-learner history tab can find entries where the learner is the target and entries where they are a related party (e.g. a move of their membership). Decide the query path for the learner and cohort tabs in the spec; a nullable cohort/learner indexed field is cheaper than JSON queries.
6. Reason: optional text, prompted on removals/deactivations (Open edX).
7. Display: per-object tab plus organisation log with actor, action, date filters (Moodle, Wagtail, Sentry); newest first, paged. Read-only admin.
8. Retention: keep forever by default; a prune command with a configurable age, not scheduled (auditlogflush, Wagtail purge, Moodle `loglifetime` as the naming model for the setting).
9. Writing: explicit writer calls inside the action's transaction (auditlog/pghistory signal capture reject: records mechanism not intent, misses `bulk_*`).
10. Avoid: field-level diffs and shadow tables (simple-history, pghistory), login events (easy-audit, Canvas authentication), separate stores per concern (Canvas), integer-enum action flags (Django LogEntry), cascade-deleting history with the user.

Open items for the spec author: confirm exact retention setting names and Wagtail audit_log doc URL before citing; none of the above beyond the Wagtail hook was re-fetched.

status: ok · reason: complete; only the Wagtail hook was verified live, the rest is from prior knowledge and flagged
