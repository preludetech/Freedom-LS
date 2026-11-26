# Research: reference implementations

How other systems handle: removing users, throttled last-active tracking, deletion audit records, and admin intermediate action pages. Depth is limited; items marked (unverified) came from search summaries, not the primary source. Several primary-source fetches (Moodle source, Unfold docs pages, edX readthedocs) returned 404, so field names for Moodle and Canvas beyond those cited are from general knowledge and flagged.

## 1. Throttled last-active

### Moodle
- Per-user last access is written to `user.lastaccess` (site) and the `user_lastaccess` table (per course: `userid`, `courseid`, `timeaccess`). The write is throttled by the constant `LASTACCESS_UPDATE_SECS`, 60 seconds. The tracker states that the `user_lastaccess` table is "throttled via the LASTACCESS_UPDATE_SECS global define (also set to 60)", and that web-service token `lastaccess` was modelled on it ("only updates when it is at least 1 minute newer"). Source: https://tracker-old.moodle.org/browse/MDL-65179 (via search summary).
- Edge case: anything that loads an authenticated URL (for example email images) moves lastaccess. https://tracker-old.moodle.org/browse/MDL-75010 . Lesson: count only real page requests, not asset or API requests.
- Where the write happens: in the request bootstrap/session code (`user_accesstime_log()` in `lib/moodlelib.php`, called per page request) (unverified, from memory).
- Moodle keeps `lastaccess` separate from `lastlogin`/`currentlogin`/`firstaccess`. This matches FLS's need to leave `last_login` alone.

### Open edX
- Relies on Django `last_login` (`auth_user.last_login`), set at login only. Activity is not tracked per request in core. Learner "last activity" comes from `StudentModule.modified` and course-level `CourseEnrollment`/courseware activity. This is the pattern FLS wants to avoid (last_login only moves at sign-in).

### Canvas LMS
- `users.last_logged_out`, `pseudonyms.last_request_at` and `pseudonyms.last_login_at`, plus `enrollments.last_activity_at` and `total_activity_time` (unverified, from memory). `last_request_at` is written throttled in the request path, with the interval held in a setting (`Setting.get('session_activity_update_interval'...)`) (unverified). Lesson: last-active as a separate timestamp from last-login, throttled by a configurable interval.

### Django packages
- django-last-seen: middleware, `LAST_SEEN_INTERVAL` (default 2 hours: how often the timestamp is written to the DB), `LAST_SEEN_DEFAULT_MODULE` ("default"); stores a `LastSeen` model row per user/module, with a cache in front. Archived Dec 2023. https://pypi.org/project/django-last-seen/ ; https://github.com/kursitet/django-last-seen
- django-last-active (fork, same two settings): https://pypi.org/project/django-last-active
- Common pattern: middleware after `AuthenticationMiddleware`; skip anonymous users; compare the stored value to now; write only if older than the interval; use `QuerySet.update(...)` (no `save()`, no signals, no `updated_at` side effects).

Implication for FLS (answers.md: throttled, default 5 minutes, setting; session only, not API keys): a middleware, or a hook on the session-authenticated path, that reads `request.user.last_active` (already loaded, so no extra query for the comparison) and runs `User.objects.filter(pk=...).update(last_active=now)` only when `None` or older than the interval. API-key requests are excluded naturally if the API-key auth never sets a session-authenticated `request.user`, or by checking the auth class. This is exactly Moodle's "compare, then write only if stale" shape.

## 2. User deletion versus deactivation

### Open edX user retirement
- At a deletion request: sessions are logged out and the account is disabled; a `UserRetirementStatus` row is created in state `PENDING`; no PII erased yet. States are rows in a `RetirementState` table (`PENDING`, `RETIRING_*`, `*_COMPLETE`, plus terminal `COMPLETE`, `ABORTED`, `ERRORED`). Triggers: the account "Delete My Account" button, `bulk_retire_users` API, `retire_user` management command. After the steps run, username and email are scrambled so they cannot be reused; `retirement_cleanup` later deletes the stored original username/email. The `User` row is kept, so FKs stay valid. https://docs.openedx.org/en/latest/site_ops/concepts/user_retirement.html ; https://opencraft.com/demystifying-user-retirement-in-the-open-edx-platform/ ; https://edx-installing-configuring-and-running.readthedocs.io/en/latest/configuration/user_retire/implementation_overview.html
- Lesson: the status/audit row survives while the identity is scrubbed. FLS differs: it hard-deletes on purpose, so the audit entry must carry label and `subjects` itself (already in the idea).

### Moodle
- `delete_user()` does not remove the row: it sets `user.deleted = 1`, mangles `username` and `email`, removes enrolments and sessions, and fires `\core\event\user_deleted`. Hard purge is not offered in the UI. Suspension (`user.suspended = 1`) is the soft equivalent of `is_active = False`. (unverified, from memory.)

### Canvas
- Users have `workflow_state` (`registered`, `deleted`, ...). Delete is a soft delete (`destroy`), with a separate "merge users" flow. Hard delete is only through support/DB. (unverified, from memory.)

### django-safedelete
- Model field `deleted` (timestamp) with policies (`SOFT_DELETE`, `HARD_DELETE`, `SOFT_DELETE_CASCADE`, `NO_DELETE`). `NO_DELETE` policy is the nearest to "ordinary delete does nothing". It is a model-level policy, a heavier change than FLS wants (admin-level removal only; orm `delete()` still works for the force-delete path). https://github.com/makinacorpus/django-safedelete

Takeaway: every mature LMS makes deactivate/suspend the default and keeps true erasure behind a separate, privileged, logged path. The Django equivalent of "remove delete" is `has_delete_permission` returning False plus removing `delete_selected` from actions; the force path then performs deletion itself.

## 3. Audit records of deletions

- django-auditlog `LogEntry` fields: `content_type`, `object_pk` (CharField), `object_id` (BigInteger, if integer), `object_repr` (TextField, `smart_str(instance)`), `action` (PositiveSmallInteger: CREATE 0, UPDATE 1, DELETE 2, ACCESS 3), `changes` (JSON), `actor` (FK, SET_NULL), `actor_email`, `remote_addr`, `timestamp`, `additional_data` (JSON from instance `get_additional_data()`), `serialized_data`. The row stores a text repr and pk, not an FK to the deleted object, so it outlives the row. https://github.com/jazzband/django-auditlog/blob/master/auditlog/models.py
- django-simple-history: a `Historical<Model>` table copying all fields with `history_type` (`+`, `~`, `-`), `history_date`, `history_user`, `history_change_reason`. Deletion adds a `-` row retaining the full data. `history_change_reason` is the closest analogue to FLS's required reason. https://django-simple-history.readthedocs.io/en/latest/historical_model.html (unverified, from memory.)
- Django's own `LogEntry` (`django.contrib.admin.models`): `object_id`, `object_repr`, `action_flag` (DELETION = 3), `change_message`. `delete_selected` calls `ModelAdmin.log_deletions(request, queryset)` before deleting. https://docs.djangoproject.com/en/dev/ref/contrib/admin/actions/

Takeaways for FLS: store a text label (`object_repr`), the target pk as text, the actor, the reason, and a JSON blob of subjects, with no FK to the deleted row; write the entries before or in the same transaction as the delete; none of these references makes the log itself deletable from the admin. Django's built-in admin `LogEntry` records deletions with no reason, so the FLS `AuditLogEntry` is needed for the reason.

## 4. Admin intermediate action page (Django built-in)

From Django `contrib/admin/actions.py` `delete_selected` (summarised from the source via fetch):
- Single view for confirmation and execution: the action checks `request.POST.get("post")`. If set and nothing is protected, it deletes; otherwise it renders the confirmation template. The deleting branch returns `None`, so the changelist reloads.
- `modeladmin.get_deleted_objects(queryset, request)` returns `(deletable_objects, model_count, perms_needed, protected)`; the template groups by model through `model_count`.
- `perms_needed` non-empty makes the page title "Cannot delete"; a POST anyway raises `PermissionDenied`. `protected` blocks too (this is the `CourseProgress.learner` PROTECT case: force delete must delete protected dependents first or compute its own collector).
- Template lookup order: `modeladmin.delete_selected_confirmation_template`, then `admin/<app>/<model>/delete_selected_confirmation.html`, then `admin/<app>/delete_selected_confirmation.html`, then `admin/delete_selected_confirmation.html`.
- Hidden inputs carry `action`, `_selected_action` ids and `post=yes`; the CSRF token is in the form.
- Action permission: `@admin.action(permissions=["force_delete"])` makes Django call `has_force_delete_permission(request)` on the ModelAdmin. This is the mechanism for superuser-only visibility on the list; `get_actions()` drops actions the user is not permitted to run.
- Pattern for adding a required reason: a plain Django `Form` with a `reason` CharField (`max_length=REASON_LENGTH`) rendered in a copy of the confirmation template; on POST validate the form, re-render with status 200 (or 422 if the project treats this as an HTMX-style response; for a normal full-page POST in admin, Django convention re-renders with 200) if invalid; on valid, write audit entries then delete, in `transaction.atomic()`.
- The Delete button on the change page is `delete_view` plus the `submit_row` template tag, controlled by `has_delete_permission`; with delete removed that button disappears and the change page needs a custom button.

## 5. Unfold change-page buttons

- Unfold (django-unfold) offers `actions_list` (changelist top buttons, signature `(self, request)`), `actions_detail` (change-page buttons, signature `(self, request, object_id)`), `actions_row` (per-row, signature `(self, request, object_id)`), and `actions_submit_line` (buttons in the submit row). Declared with `unfold.decorators.action` (`@action(description=..., permissions=[...], url_path=..., attrs=...)`). `@action(permissions=["foo"])` makes Unfold call `has_foo_permission(request[, object_id])`; permissions containing a dot are treated as built-in Django perms and do not receive the object on detail views. `actions_list_hide_default` / `actions_detail_hide_default` hide the defaults. Detail actions are routed to their own URL under the object (`<object_id>/<url_path>/`), so they can render a confirmation page themselves. Docs: https://unfoldadmin.com/docs/actions/ , https://unfoldadmin.com/docs/actions/changeform/ , https://unfoldadmin.com/docs/decorators/action/ , https://www.mintlify.com/unfoldadmin/django-unfold/actions/list-actions (mirror, unverified against current release).
- Selected-rows actions in Unfold remain the standard Django `actions` (with `@action`), which is where "force delete" in the changelist action dropdown belongs; this reuses the built-in confirmation flow above.
- Whether FLS uses Unfold is not verified here; if the admin uses stock Django, the equivalent for the change-page button is overriding `change_form_template`/`submit_row` or using `change_form_object_tools`, and adding a `get_urls()` route to a view that reuses the same confirmation view with a one-element queryset.

## Summary of mechanisms to copy

| Need | Reference mechanism |
|---|---|
| Throttled last-active | Moodle `LASTACCESS_UPDATE_SECS` (60 s) compare-then-write; django-last-seen `LAST_SEEN_INTERVAL`; use `.update()` |
| Separate from last_login | Moodle `lastaccess` vs `lastlogin`; Canvas `last_request_at` vs `last_login_at` |
| Superuser-only action | `@admin.action(permissions=[...])` and `has_<name>_permission` |
| Confirmation with grouped list | `delete_selected` view, `get_deleted_objects`, `model_count`, `post=yes` pattern |
| Audit after row gone | django-auditlog `object_repr` + `object_pk` + `additional_data`, no FK; simple-history `history_change_reason` |
| Reason on file | simple-history `history_change_reason`; edX status rows |
| Deactivate by default | edX disables account first; Moodle suspend |

status: ok
