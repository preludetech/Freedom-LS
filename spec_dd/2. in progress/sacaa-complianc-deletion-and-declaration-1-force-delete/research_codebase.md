# Research: codebase touch points for force delete and last active

Read-only findings. Paths are under the repo root; `freedom_ls/...` is the package. Builds on
`research_user_deletion.md` (delete paths, cascades, audit log model, `last_login`) and does not
repeat it. Answers already taken (`answers.md`): last-active writes throttled (default 5 minutes, a
setting); API-key requests do not move it; force delete is both a changelist action and a "Force
delete" button on the change page; last active is read-only on the educator learner detail page.

## 1. Admin: superuser-only action, change-page button, confirmation page

The admin is Unfold (`SiteAwareModelAdmin` subclasses `unfold.admin.ModelAdmin`,
`freedom_ls/site_aware_models/admin.py:25`). Unfold's `ActionModelAdminMixin`
(`.venv/.../unfold/mixins/action_model_admin.py`) supplies `actions_list`, `actions_row`,
`actions_detail` (top of the change form) and `actions_submit_line`. Both `UserAdmin` and
`LearnerAdmin` already get this mixin.

Three existing, near-identical patterns to copy. The closest is the API key revoke flow.

- `freedom_ls/api_admin/admin.py` plus `freedom_ls/api_admin/views.py` plus
  `freedom_ls/api_admin/templates/admin/api_admin/revoke_confirm.html`.
  - `actions = ["revoke_selected"]` (stock `@admin.action(permissions=["change"])`) redirects the
    selection to a custom view as `?ids=a,b`.
  - `actions_detail = ["revoke_key"]` (`@unfold_action(url_path=..., permissions=["change"])`)
    redirects the single id to the same view.
  - `get_urls()` prepends `path("revoke/", self.admin_site.admin_view(partial(revoke_view,
    model_admin=self)), name="freedom_ls_api_apikey_revoke")` before `super().get_urls()`.
  - The view checks the permission itself ("this URL can be typed by hand"), reads ids from
    GET (confirm) or POST (do it) through the admin's own `get_queryset` (so another site's row is a
    404), does the write in `transaction.atomic()` with `select_for_update()` and `record_entry`
    per row, then `model_admin.message_user(...)` and `redirect`.
  - `admin_page_context(request, model_admin, title)` (`site_aware_models/admin.py:92`) supplies the
    `each_context` plus `model_admin` plus `title` an Unfold custom page needs.
  - The template extends `admin/base_site.html`, uses `{% component "unfold/components/card.html" %}`,
    `.../text.html` and `.../button.html with submit=1 variant="danger"`, lists the rows and has a
    POST form with `{% csrf_token %}` and a Cancel link.
- `freedom_ls/mail/admin.py` (`resend_view`, `has_resend_permission` returns
  `request.user.is_superuser`, `actions = ["resend_selected"]`, `actions_detail = ["resend_email"]`,
  `get_actions_detail` hides the button for rows the action cannot run on). Template
  `freedom_ls/mail/templates/admin/mail/resend_confirm.html`. This is the existing superuser-only
  precedent: `@admin.action(description=..., permissions=["resend"])` and
  `@unfold_action(description=..., url_path=..., permissions=["resend"])`.
- `freedom_ls/deadlines/admin_views.py` plus `templates/admin/deadlines/_action_form.html`: a
  confirmation page with a required reason field. `deadlines/forms.py:43` is
  `reason = forms.CharField(max_length=REASON_LENGTH, widget=UnfoldAdminTextareaWidget)` with
  `REASON_LENGTH` imported from `freedom_ls.audit_log.models`. The generic form template renders
  fields, errors and a submit/cancel pair. This is the shape of "list what goes, require a reason".
- `freedom_ls/reports/admin.py:110` is the `actions_list` example (`@unfold_action` with no
  object, redirects to a custom URL).

Mechanics that matter for the spec:

- Superuser-only: define `has_force_delete_permission(self, request, obj=None) -> bool: return
  request.user.is_superuser` and name it in `permissions=["force_delete"]` on both the stock
  `@admin.action` (checked by Django when building the action list) and the `@unfold_action`
  (checked by Unfold in `_filter_unfold_actions_by_permissions`, which passes `object_id` as the
  second arg for detail actions). The decorator also raises `PermissionDenied` when the action URL
  is hit directly. Because Unfold passes `object_id`, the method must accept the second positional
  argument (mail does: `obj=None`).
- Custom URL must be inserted before `super().get_urls()`: Django's catch-all
  `<path:object_id>/` pattern would otherwise swallow it (reports/admin.py:117 comments on this).
  The view re-checks `has_force_delete_permission`.
- "Where the Delete button used to be": the standard Delete link is gone once
  `has_delete_permission` returns False (`api_admin` tests assert
  `response.context["has_delete_permission"] is False`, `api_admin/tests/test_admin.py:348`). The
  `actions_detail` button is the replacement. `actions_submit_line` renders POST buttons beside
  Save, which is the wrong shape for a link to a confirmation page.
- Removing "delete selected" from `UserAdmin`: `has_delete_permission(request, obj=None)` returning
  False also removes Django's `delete_selected` action (`LearnerAdmin` already relies on this,
  `learner_management/admin.py:232`; `referral_tracking/tests/test_admin.py:361` asserts
  `b"delete_selected" not in response.content`). The stock delete URL then answers 403
  (`accounts/tests/test_admin.py:81` style).
- `UserAdmin` inherits `SiteAwareExportModelAdmin` (`ExportActionMixin`), which already adds
  `export_admin_action`; a new action joins the same `actions` list. `UserAdmin` has no `actions`
  attribute today, so `actions = ["force_delete_selected"]` is safe to add. `LearnerAdmin` is a plain
  `SiteAwareModelAdmin` with no actions.
- The Unfold button class: `@unfold_action(..., variant=ActionVariant.DANGER)` (see
  `unfold/decorators.py`, `variant` param) gives the red styling.
- Reason field: use a Django `forms.Form` with `reason = CharField(max_length=REASON_LENGTH,
  widget=UnfoldAdminTextareaWidget)` as `deadlines/forms.py` does, importing `REASON_LENGTH` from
  `freedom_ls.audit_log.models`. `record_entry` strips the reason and raises `ValueError` over
  `REASON_LENGTH` (`audit_log/writer.py:52-54`), so the form limit must be the same constant.
  Note `panel_framework.forms.REASON_LENGTH` is a second copy that must stay at least as long
  (`audit_log/README.md:26`); the admin form should import the audit one.

## 2. Collector, `get_deleted_objects` and PROTECT

- `UserAdmin.get_deleted_objects` (`accounts/admin.py:194`) calls Django's
  `django.contrib.admin.utils.get_deleted_objects` and subtracts the `verbose_name` of every model
  in `USER_ERASURE_CASCADE_MODELS` from `perms_needed`. Django computes `perms_needed` by calling
  `admin_site.get_model_admin(model).has_delete_permission(request, obj)` for each collected model
  that has a registered admin, so a model whose admin denies delete (`LegalConsent`, `Learner`,
  `CourseApplication`, `AnonymousApplicant`) would block the page; that is the only job the set
  has. Registrations: `accounts/admin.py:26` (`{LegalConsent}`), `learner_management/admin.py:279`
  (`Learner`), `course_applications/admin.py:29-30`.
  - After the change `has_delete_permission` is False on `UserAdmin`, so the stock delete page
    returns 403 and nothing calls `get_deleted_objects` on it. The set only keeps a job if the
    force-delete page reuses `UserAdmin.get_deleted_objects` for its listing, or if it is still
    consulted by something else. If the confirmation view builds its own collector, the set is
    dead code. This is a spec decision (the idea says "the cascade list keeps its job"): either
    route the listing through `get_deleted_objects` (which also gives the nested `<ul>` with admin
    links Django users know) or drop the set and its three registrations and the `perms_needed`
    stripping together.
  - `CourseApplicationAdmin`/`AnonymousApplicantAdmin` messages say "delete the user instead"
    (`course_applications/admin.py:272`) and `course_applications/erasure.py:16-18` says "delete the
    user to erase their records"; both strings become wrong when the User delete button goes. They
    should say "force delete the user".
- The collector already used outside the admin: `panel_framework/actions.py:719` (`DeleteAction.
  get_cascade_summary`) builds `django.db.models.deletion.Collector`, calls `collector.collect`,
  counts `collector.data` plus `collector.fast_deletes`, and catches `ProtectedError`/`RestrictedError`
  with `_protected_dependents()` (line 683). It lists counts per model (`count_noun`), which is the
  "grouped by model" shape the idea wants, but is educator-modal code (not for reuse from admin).
- Django's admin collector `NestedObjects` (`.venv/.../django/contrib/admin/utils.py:186`) catches
  `ProtectedError`/`RestrictedError` inside `collect`, adds the blocking objects to
  `collector.protected` and stops collecting that branch. It also exposes `collector.model_objs`
  (`{model: set(instances)}`), which is exactly "records grouped by model", and
  `can_fast_delete()` is forced False so every row is loaded and listed.

PROTECT handling for force delete (the load-bearing finding):

- `CourseProgress.learner` is `on_delete=PROTECT` (`learner_progress/models.py:110`). A collector run
  from a `User` or `Learner` therefore raises `ProtectedError` at the `Learner -> CourseProgress`
  edge, and `NestedObjects` swallows it so the listing silently omits `CourseProgress`,
  `TopicProgress`, `CourseFormAttempt` and the deadlines rows below it, listing them under
  "protected" only.
- So force delete cannot be one `user.delete()`. The sequence must be: collect and delete the
  user's (or learner's) `CourseProgress` rows first (`CourseProgress._base_manager.filter(learner__user=user)`
  or `learner=learner`), which cascades to `TopicProgress`, `CourseFormAttempt` (`CASCADE` from
  `course_progress`, `learner_progress/models.py:266`) and `deadlines` rows (`DeadlineOverride`,
  `CoursePause`, `DeadlineExtension` all `CASCADE` from `course_progress`,
  `deadlines/models.py:156,437,519`); then delete the user or learner. All of it in one
  `transaction.atomic()` with the `record_entry` call(s).
- The preview must therefore union two collections: a `NestedObjects` (or `Collector`) over the
  `CourseProgress` queryset, plus one over the user/learner, then group `model_objs` by model. A
  `NestedObjects.collect` on the user alone will not show the course progress.
- Other PROTECTs near the path do not block: `CourseProgress.course`, `.registration`,
  `.cohort_registration`, `TopicProgress.topic` protect the other side. `LearnerCourseRegistration`
  is a CASCADE child of `Learner`, but a `CourseProgress` PROTECT-references it
  (`learner_progress/models.py:121`), so the registration can only go after the progress rows. This
  reinforces the order above. `Learner.organisation` and `AuditLogEntry.organisation` PROTECT are
  irrelevant to deleting a learner.
- Signals that run inside `collector.delete()` and are invisible to a preview built from
  `collect()` alone:
  - `course_applications/receivers.py:134` `pre_delete(User)`: erases `AnonymousApplicant` rows with
    the user's email that are unclaimed (matched by address, not by FK), taking their
    `CourseApplication` and user-less `FormProgress` and uploaded files with them. A collector
    preview will not list these, so the confirmation page should add a line for them (it can reuse
    the same query: `AnonymousApplicant._base_manager.filter(site_id=..., email=email.lower(),
    user__isnull=True)`).
  - `course_applications/receivers.py:111` `post_delete(CourseApplication)` removes the user-less
    sitting.
  - `registration_rules/signals.py:451` `pre_delete(Learner)` enqueues rule re-evaluation for the
    user (courses read before the cascade); `re_recommend_on_registration_withdrawn` and
    `re_recommend_on_membership_deleted` do the same per row. Harmless but they enqueue work
    (`_enqueue_rule`) inside a transaction.
  - `accounts/signals.py:25` `post_delete(User)`: deletes the profile-picture prefix on commit.
  - `form_engine/receivers.py:16` `post_delete(QuestionAnswerFile)`: deletes the stored file.
  - `AuditLogEntry.actor` uses `set_null_by_instance` (`audit_log/README.md:172-175`), so deleting
    a superuser who acted before keeps entries and nulls the actor; `AuditLogEntryQuerySet.delete`
    raises, so the collector never deletes entries.
- A Learner-only force delete leaves `FormProgress` rows behind. `CourseFormAttempt.form_progress`
  is a `OneToOneField(FormProgress, on_delete=CASCADE)` (`learner_progress/models.py:280`): the
  cascade runs from the sitting to the course-side row, not the other way. Deleting a
  `CourseProgress` deletes its `CourseFormAttempt` but not the quiz `FormProgress`, its
  `QuestionAnswer` rows or answer files, because `FormProgress.user` points at the `User`, which
  stays. The idea says a learner force delete removes "`CourseProgress` (and what cascades from it,
  `TopicProgress` and `CourseFormAttempt`)". That leaves the quiz sittings and answers (the detailed
  student records) in place with no course link. The spec must decide: leave them (state it on the
  confirmation page) or delete each `CourseFormAttempt.form_progress` too. User force delete is
  unaffected, since `FormProgress` cascades from the user.

## 3. Audit log

- Registry: `FLS_AUDIT_ACTIONS` in `freedom_ls/audit_log/actions.py:151`, a tuple of
  `AuditAction(code, label, describe=None, group="Other")`. `group` must be in
  `AUDIT_ACTION_GROUPS` (line 20).
- Signature (`audit_log/writer.py:33`): `record_entry(*, action, actor, target, target_label,
  organisation, subjects=(), reason="", details=None, run_id=None, site=None)`. `target` must be a
  `Site` or `SiteAwareModelBase` unless `site` is passed (both `User` and `Learner` qualify).
  `subjects` always gets `subject_key(target)` prepended
  (`"<app_label>.<model_name>:<pk>"`, e.g. `accounts.user:12`, `freedom_ls_learner_management.learner:5`
  by app label). `ContentType` is stored (PROTECT) and `target_object_id` is a string, so the entry
  survives the row.
- Existing helper for learner-targeted entries: `learner_management/learner_actions.py:64`
  `record_learner_entry(learner, action, actor, *, reason, subjects, details)`, labels by
  `learner.user.display_name` and takes `organisation=learner.organisation`. A learner force delete
  can call it directly, inside the transaction, before the delete (it reads `learner.user` and
  `learner.organisation`, which must be loaded first).
- Existing admin precedent for an entry written from an admin view: `api_admin/views.py:89`
  (`record_entry(action="api_key.revoked", actor=acting_user(request), target=key,
  target_label=str(key), organisation=None, ...)`); `api_admin/audit.py:acting_user` is the pattern for
  `request.user` to `User` narrowing (raises `PermissionDenied` if not a real user).
- Where actions are documented: the table in `freedom_ls/audit_log/README.md:75-109` (code, label,
  group, target, other subjects, details) and the glossary's "Changes" section,
  `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md:190-230`. Both must gain the new rows.
  `docs/product/security-and-data-handling.md` lines 21, 142 and 198-202 (audit log section,
  "Deleted people stay named") describe what the log covers and say "an operator handles an erasure
  request ... by hand"; they need a sentence.
- The vocabulary invariant `audit_log/tests/invariants/test_vocabulary.py` constrains the new codes:
  - noun must be in `NOUNS` (`user` and `learner` are), verb in `VERBS` (`deleted` and `removed`
    are).
  - `test_an_actions_group_follows_its_noun`: group must equal `NOUN_GROUPS.get(noun, "Other")`.
    `learner.*` goes to "Learners"; `user.*` is absent from `NOUN_GROUPS`, so `user.deleted` must be
    group "Other", unless the test and `AUDIT_ACTION_GROUPS` gain a "Users"/"Accounts" heading.
  - Glossary: `deleted` = "a standalone object was deleted" (`cohort.deleted`); `removed` = "an
    association row was deleted" (`cohort_membership.removed`). A `Learner` is described as the
    `(user, organisation)` association row (`learner.added` is the "association now exists" verb),
    so by the glossary a forced learner deletion is `learner.removed`, a forced user deletion is
    `user.deleted`. `learner.removed` vs `learner.deleted` is a naming decision for the spec; if
    the glossary row for `removed` is extended it must be agreed there first (the test file says
    the glossary is where a new word is agreed). A webhook event type for the same string would
    need `FLS_WEBHOOK_EVENT_TYPES` and `WEBHOOK_EVENT_TYPE_SAMPLES` entries
    (`test_a_webhook_event_type_shared_with_the_audit_log...`); nothing in the idea asks for a
    webhook, so none is needed.
- A downstream's `AUDIT_LOG_EXTRA_ACTIONS` check `freedom_ls_audit_log.E001` fails on a collision
  with an FLS code (`audit_log/README.md:163`). A new FLS code can therefore collide with a
  downstream's own; mention in upgrade notes.
- How the organisation is set and what a user with several Learner rows needs:
  - Educator views filter by organisation: the organisation Audit log is
    `AuditLogEntry.objects.filter(organisation=organisation)`
    (`educator_interface/panels/audit_log/data_tables.py:149`); a learner's History tab filters by
    `subjects__contains=[subject_key(learner)]` (`data_table_panels.py:47`). The Django admin
    `AuditLogEntryAdmin` shows every entry for the site.
  - A user force delete is a site-level fact. One entry per user has one `organisation` column. For
    a user with Learner rows in several organisations the options are: `organisation=None` (visible
    in the Django admin only, as `api_key.*` entries are today); or one `user.deleted` entry with
    `organisation=None` plus one `learner.*` entry per Learner so each organisation's educators see
    the loss in their log. The idea says "one entry per deleted user or learner", so the second is
    an extra and needs a decision. If a user has exactly one Learner, `organisation` could be that
    organisation. A deleted learner's History tab no longer exists, but the organisation log still
    shows an entry whose `organisation` is set.
  - `details` should carry names of organisations, the counts per model from the confirmation page
    and the user's pk and email (the audit README says `details` holds ids, labels and counts and
    "never ... email addresses beyond the labels themselves"; `target_label` can be the display name,
    which is the email address where there is no name, as `docs/product/security-and-data-handling.md:202`
    notes). Whether the email is allowed in the label for a hard-erasure entry is a privacy decision
    for the spec: a legal erasure request may want the label minimal.
  - `AuditLogEntry.organisation` is PROTECT, so an Organisation that appears in a forced-delete entry
    can never be deleted afterwards (organisation admin already forbids delete,
    `organisations/tests/test_admin.py:71`).
  - `site` is required: `User` and `Learner` are site-aware so `_site_for(target)` resolves from the
    target. Pass the user's `site` explicitly if the actor's site could differ from the target's.
  - Self-deletion and last-superuser cases: a superuser force deleting their own account makes
    `actor` null (`set_null_by_instance`) but `actor_label` keeps the name, so the entry stays
    readable. Whether to refuse self-deletion or the last superuser is not decided in the idea.
- Django's own `LogEntry` is written by the stock delete view (`ModelAdmin.log_deletions`,
  `.venv/.../django/contrib/admin/options.py:968`). A custom view skips it unless it calls
  `self.log_deletions(request, queryset)`. `LogEntry.user` is CASCADE to the actor, so it is lost if
  the actor is later deleted, which is why the audit log is the record. Worth deciding whether to
  also write `LogEntry`; the idea does not ask for it.

## 4. Middleware, API-key identity, last-active writes

- `config/settings_base.py:177` `MIDDLEWARE` order: Security, CSP, WhiteNoise, Session, Common,
  `base.middleware.RemoveSlashMiddleware`, Csrf, Authentication,
  Messages, `base.middleware.HtmxMessagesMiddleware`, XFrameOptions,
  `site_aware_models.middleware.CurrentSiteMiddleware`,
  `referral_tracking.middleware.AttributionCaptureMiddleware`, allauth `AccountMiddleware`,
  `accounts.middleware.RegistrationCompletionMiddleware`, `axes.middleware.AxesMiddleware`.
  `settings_dev.py:43` prepends the debug toolbar and `:145` appends `BrowserReloadMiddleware`;
  `settings_prod.py` has no `MIDDLEWARE` changes. Static files are answered by WhiteNoise before the
  rest.
- Placement: a new class in `freedom_ls/accounts/middleware.py` (it already holds
  `RegistrationCompletionMiddleware`, same `__init__(get_response)` / `__call__` shape and
  `request.user.is_authenticated` guard) placed after `AuthenticationMiddleware` and, to be before
  anything that short-circuits, before `RegistrationCompletionMiddleware` (which redirects
  authenticated users with incomplete forms; those requests are still activity). Putting it after
  `CurrentSiteMiddleware` is not required: the write should use `User._base_manager` so it works
  without a request site (same reason as `accounts/signals.py:22`).
- API-key requests: `api/authentication.py:38` `ApiKeyAuthentication` is a DRF authenticator, so it
  runs inside the view, after all Django middleware. It returns `(None, api_key)`: there is no user,
  only a key. Django middleware sees `request.user` from the session only, so API-key requests carry
  no `request.user` and do not move last active unless the same request also sends a valid
  session cookie. The answer "no" needs no code, only a test (a request with a Bearer header and no
  session leaves `last_active` null). `ApiKey.last_used_at` is its own column
  (`api/models.py:38`, `LAST_USED_RESOLUTION = timedelta(minutes=5)` at `api/models.py:18`), and
  `_record_use` (authentication.py:78) is the throttle pattern to copy: read the stored value from
  the fetched row to decide, then a conditional `update` (`Q(null) | Q(lt=now - interval)`) so two
  workers race safely, via `_base_manager`, leaving `updated_at` alone.
- Setting: use `AccountsConfig` in `freedom_ls/accounts/config.py` (an `AppSettings` subclass, see
  the `fls-dev:app-settings` skill). Existing time setting precedent is
  `SETUP_EMAIL_RESEND_SECONDS: int` with `Setting(default=900)`. A new `LAST_ACTIVE_WRITE_SECONDS`
  (name is the spec's call) with `Setting(default=300)` fits. `ApiKey`'s constant is not a setting;
  the idea wants the user one to be a setting.
- Do `User` signals fire? Writing with `User._base_manager.filter(pk=...).update(last_active=now)`
  runs no `save()`, so none of these run:
  - `TimestampedModel.updated_at` is `auto_now=True` (`site_aware_models/models.py:182`): `update()`
    does not touch it. This matters because `updated_at` is the API's changed-since sync cursor
    (`accounts/api.py` `UpdatedSinceFilterSet`, index `accounts_user_site_updated_idx`), and
    `docs/api.md:413` already says a sign-in must not move it
    (`accounts/tests/test_signals.py:110` `test_a_login_does_not_move_updated_at`). Last active
    must not move it either; a test should assert that.
  - `course_applications/receivers.py:98` `post_save(User)` calls `touch_application_updated_at` for
    every full `save()` (`update_fields` of None) and early-returns only when `update_fields` misses
    `USER_FIELDS_THE_API_SHOWS`. A `save(update_fields=["last_active"])` would avoid it, but only if
    `last_active` is not in that set; `update()` avoids all of it with no dependency on the set.
  - `accounts/signals.py:14` (`touch_user_updated_at`) listens to `EmailAddress`, not `User`.
  - Django's `update_last_login` is wired to `user_logged_in`, untouched. `account_setup.py:40,47`
    reads `last_login is None` and is unaffected.
- Query cost and tests: the middleware reads `request.user.last_active` from the already loaded
  user (no extra read), and writes at most once per interval per user. But the first authenticated
  request of every test client logs in a fresh `UserFactory` whose `last_active` is null, so that
  request issues one extra `UPDATE`. There are ~483 query-count assertions across 94 test files
  (`django_assert_num_queries`, `django_assert_max_num_queries`, `CaptureQueriesContext`, e.g.
  `educator_interface/tests/...`, `learner_interface/tests/views/...`, `comms/tests/...`). Mitigation
  options for the spec: `UserFactory` (`freedom_ls/accounts/factories.py`) sets `last_active` to now
  so a fresh client is inside the interval; or the middleware tests set the interval to 0 and the
  rest of the suite leaves the factory default. Settings: tests run with a `TESTING` flag in
  `config/settings_dev.py`.
- Background traffic counts as activity: any authenticated request moves last active, including
  HTMX polling (`educator_interface/templates/educator_interface/partials/run_status.html:17`
  `every 2s`, and `panels/cohort_report_downloads_region.html:17` `every {{ poll_seconds }}s`) and
  anything the comms bell fetches. With the throttle this is one write per 5 minutes while a tab is
  open. The spec could name this or exclude `HX-Request` polling; the idea says "an authenticated
  request moves it".
- Downstream adoption: downstream projects keep their own `MIDDLEWARE` list. Precedent is
  `spec_dd/3. done/2026-09-10_18:18_referal_tracking/upgrade_notes.md:8,100` (hard requirement,
  "add the middleware directly after `CurrentSiteMiddleware`") and
  `...referral-links-404.../upgrade_notes.md:7,35` (optional, `RemoveSlashMiddleware`). A system
  check enforcing registration exists as a precedent in `freedom_ls/base/checks.py:19-48`
  (`check_htmx_messages_middleware`, E001). Without an enforced registration last active silently
  stays null in a downstream that does not add the middleware; the spec should say hard (with a
  check) or optional.

## 5. Educator interface: where a read-only last active fits

- The learner page: `educator_interface/panels/learner/instance_view.py` `LearnerInstanceView`
  (`panel = LearnerTabSet`), tabs `overview`, `courses`, `messages`, `settings`, `history`. The
  Overview tab's `LearnerOverviewStack` holds `LearnerDetailsPanel`
  (`panels/learner/panels.py:40`), an `InstanceDetailsPanel` whose `get_rows()` returns
  `detail_row("Name"|"Email"|"Status"|"Date added", ...)`. `detail_row(label, value, kind)`
  (`panel_framework/panels.py:557`) accepts `kind="date"` for a date or datetime. A
  `self.detail_row("Last active", learner.user.last_active, "date")` row is the natural slot, and
  needs `select_related("user")` which the panel already relies on (`learner.user.display_name`).
- Tests that pin that row list and would break: `educator_interface/tests/panels/learner/
  test_instance_view.py:261` (`labels == ["Name", "Email", "Status", "Date added"]`) and
  `tests/panels/learner/test_data_tables.py:505` (`labels[:4] == [...]`, prefix only, should survive).
- A collision to resolve: "Last active" already exists on the educator interface and means something
  else. `educator_interface/panels/learner/quick_view.py:69` computes
  `Max(CourseProgress.last_accessed_time)` for a learner; the quick view template
  `educator_interface/templates/educator_interface/quick_views/learner.html:11-16` labels it "Last
  active" with a comment saying it is deliberately not `User.last_login` because that is site-wide.
  The learners data table has a "Last active" column and export column from the same annotation
  (`panels/learner/data_tables.py:134,153,197`, `_last_active_cell`), and `docs/product/
  educator-interface.md:62,199` describe it as "when they were last active". The new `User.last_active`
  is site-wide (a user, not a learner), so on the learner detail page it would sit beside a differently
  defined "Last active" in the quick view and list. The spec needs a distinct label ("Last seen on
  the site", "Last active on the site") or a decision to unify. Same comment applies to
  `reports/gather.py:314`, which also computes "when the learner was last active" for the
  inactivity rule.
- Privacy and scope: an educator sees only their organisation's learners, but `User.last_active` is
  site-wide, so it reveals activity in other organisations' pages or the admin. The existing comment
  at `quick_view.py`'s template shows the project already weighed "site-wide vs per-organisation" for
  `last_login` and chose per-organisation activity. Flag for the spec.
- Skills to follow when implementing: `claude_plugins/fls-dev/skills/educator-interface/SKILL.md` and
  `.../panel-framework/SKILL.md`.

## 6. `UserResource` export and `UserAdmin` fields

- `accounts/resources.py:17` `USER_EXPORT_FIELDS = ("id", "email", "first_name", "last_name",
  "is_active", "is_staff", "email_verified", "created_at", "last_login")`. The tuple is both
  `UserResource.Meta.fields`/`export_order` and the REST API's field list:
  `accounts/api.py:40` `fields = (*USER_EXPORT_FIELDS, "updated_at")`. Adding `last_active` to the
  tuple changes the export and the API response together. Tests that pin them:
  `accounts/tests/test_resources.py:83` (derived from the tuple, adapts), `:169` last_login blank
  cell (add a twin for last_active), `accounts/tests/test_api.py:28` `EXPECTED_FIELDS` (a literal
  set; must gain `last_active`), plus `docs/api.md:403-415` (field table and the "Signing in does not
  move it" paragraph) and `docs/product/security-and-data-handling.md:116` ("when it was created, last
  logged in and last updated"). The idea says "in the user export"; whether the API shows it too is
  implied by the shared tuple unless the spec splits it. `docs/api.md` is a public contract, so a new
  field is additive but the "does not move `updated_at`" sentence needs extending.
- Not exported anywhere else: `last_login` is also used by `qa_helpers` commands and `educator_interface/
  tests/helpers.py` only for fixtures.
- `UserAdmin` (`accounts/admin.py:119`): `readonly_fields = ["last_login", "profile_picture"]`;
  `fieldsets` group `("Important dates", {"fields": ("last_login",)})`; `list_display` is
  `["email", "first_name", "last_name", "is_staff", "is_active"]`; `list_filter` has `is_active`.
  Add `"last_active"` to `readonly_fields` and next to `last_login` in "Important dates". It is not in
  `add_fieldsets`, correct. Optionally a `list_display` column with ordering, since the use case is
  "see who has gone quiet" (a `list_filter` by date range would use
  `site_aware_models/admin_filters.py:InclusiveRangeDateTimeFilter`, already used by
  `course_applications/admin.py:20`). The form is `unfold.forms.UserChangeForm`; a model field
  with `editable=False` stays out of any ModelForm, which is what `ApiKey.last_used_at`
  (`editable=False`) does. A new field must be `editable=False` or be in `readonly_fields`.
- Migration: next is `accounts/migrations/0006_*` (current latest `0005_user_profile_picture.py`).
  A nullable `DateTimeField(null=True, blank=True, editable=False)`; no backfill is needed (null means
  "no activity recorded yet"; `last_login` is the fallback). The `accounts_user_site_updated_idx` index
  is on `updated_at` and unaffected. Do not edit existing migrations.

## 7. Upgrade notes

- Mechanism: `claude_plugins/fls-dev/commands/update_upgrade_notes.md` writes
  `<spec-dir>/upgrade_notes.md`, frontmatter flags `requires_migrations`, `requires_template_review`
  (+ `changed_template_paths`), `requires_settings_change` (+ `changed_settings`, hard vs optional via
  inline `#` comment), `requires_package_upgrade`, `requires_npm_install`,
  `requires_tailwind_rebuild`, plus "Breaking changes" and "Manual steps". It reads the branch diff
  and verifies every name against the tree. Examples: the two `MIDDLEWARE` precedents above.
- Expected flags for this work: `requires_migrations: true` (new `User.last_active`);
  `requires_settings_change: true` with `MIDDLEWARE` (new middleware, hard or optional per the
  spec), the new throttle setting key (optional) and possibly nothing else; templates: two new admin
  templates under `freedom_ls/accounts/templates/admin/...` are new rather than overrides, so
  template review is likely `false` unless the change-form template is overridden.
- Breaking changes to name: the User admin no longer offers delete or "delete selected"; anyone
  relying on them (including scripts posting to `admin:freedom_ls_accounts_user_delete`) gets 403 and
  must use force delete as a superuser; `USER_ERASURE_CASCADE_MODELS` keeps or loses its role per the
  spec; downstream apps that registered into it keep importing it (so do not remove the name without
  a deprecation); new audit action codes (collision check `freedom_ls_audit_log.E001` for downstream
  `AUDIT_LOG_EXTRA_ACTIONS`); the user API/export gains `last_active`.

## 8. Tests that break or need replacing

Breaking because they use the stock User delete path:

- `freedom_ls/accounts/tests/test_admin.py:85` `test_user_admin_delete_cascades_to_audit_rows` and
  `:105` `test_user_admin_delete_cascades_to_touches_and_conversions` (GET and POST to
  `admin:freedom_ls_accounts_user_delete`, assert `perms_lacking == set()`; become 403 and need
  rewriting against the force-delete view).
- `freedom_ls/learner_management/tests/test_admin.py:122`
  `TestDeletePermission::test_erasing_the_user_takes_their_learner_rows` (POST to the user delete
  URL, `staff_client` is a superuser from `freedom_ls/conftest.py:331`). The other test in that class,
  `test_delete_permission_is_always_false` (`has_delete_permission(request=None) is False`), keeps
  passing, but note it calls the method with `request=None`; any change that reads `request.user` in
  `LearnerAdmin.has_delete_permission` would break it. Keep that method untouched and put the
  superuser check in `has_force_delete_permission`.
- `freedom_ls/course_applications/tests/test_admin.py:120` `test_deleting_applicant_removes_application_and_sitting`
  and `:755-781` (the claimed-applicant/answer-file erasure, posts to the user delete URL with
  `django_capture_on_commit_callbacks`): both exercise the User cascade through the admin and need the
  force-delete view instead; they are the best template for the new tests of `pre_delete(User)`
  behaviour.
- `freedom_ls/course_applications/tests/test_admin.py:544-575` assert the "(claimed): delete the user
  instead" message if the string is changed.
- `freedom_ls/referral_tracking/tests/test_models.py` mentions `user_delete`/erasure (grep hit); check
  before touching.
- API/export: `accounts/tests/test_api.py:28` `EXPECTED_FIELDS`, `accounts/tests/test_resources.py`
  header test (adapts), `educator_interface/tests/panels/learner/test_instance_view.py:261`.
- New invariants to add: `audit_log/tests/invariants/test_vocabulary.py` constraints on new codes;
  a test that `UserAdmin.has_delete_permission` is False for a superuser and `delete_selected` is
  absent (pattern: `referral_tracking/tests/test_admin.py:361`, `content_engine/tests/test_admin.py:86`).
- Query-count tests (see section 4) if the factory does not seed `last_active`.

## 9. Conflicts with other specs

- `spec_dd/2. in progress/remove-unnecessary-admin-panel-functionality/idea.md` (in progress, on
  main): "Learner and cohort admin is also best achieved through the educator interface. We dont
  need it in the unfold admin." If that removes `LearnerAdmin`, this spec's "force delete on
  `LearnerAdmin`" and the `USER_ERASURE_CASCADE_MODELS.add(Learner)` line at
  `learner_management/admin.py:279` have nowhere to live, and force delete of a single learner would
  have no entry point (educator-interface force delete is explicitly out of scope). The idea is only
  a one-paragraph stub; the spec should check its current scope with the owner and say which lands
  first. It also says content-engine admin goes, which does not touch this work.
- `spec_dd/1. next/sacaa-complianc-deletion-and-declaration-2-quiz-declaration/idea.md` (not yet in
  progress, `ready`): touches `FormProgress`, `form_engine` models and `FormProgressAdmin`; shares no
  code with this spec per the roadmap. Two interactions: (a) it says "Force deleting the learner
  removes their declarations with their `FormProgress`; nothing in this spec blocks that". For a
  Learner-only force delete the `FormProgress` is not removed (section 2), so the declarations stay
  unless this spec also deletes the sittings. (b) Its open question "own append-only model, how
  'never updated' is enforced": if the declaration model refuses delete the way `AuditLogEntry` does
  (`AppendOnlyError`), a `FormProgress -> declaration` cascade would break every user force delete.
  The declaration model must allow cascade delete from `FormProgress`; flag it to that spec.
- `sacaa-compliance-3-question-pools`, `sacaa-compliance-4-attempt-review` (in progress): change the
  form schema, `FormProgress`, form export and add an educator attempt view; they add FKs/rows
  hanging off `FormProgress` and so enlarge the force-delete cascade. Any new FK to `FormProgress`,
  `Learner` or `User` that is PROTECT would block force delete; the collector preview picks up
  CASCADE additions automatically. No file-level conflict found with `accounts/admin.py` or
  `accounts/models.py`.
- `educator-interface-refactor-6-cohort` (closing): no overlap; educator learner pages were rewritten
  by `educator-interface-refactor-5-learner` (done), whose `LearnerDetailsPanel` and quick view are
  the pieces above.
- `audit-log-coverage-gaps` (`spec_dd/1. next`, Low): adds audit actions; additions to
  `FLS_AUDIT_ACTIONS` and the README table conflict textually at merge, not semantically.
- Documentation to update: `docs/product/admin-interface.md:10` ("a learner cannot be deleted
  outright"), `:46` is about organisations and stays; `docs/product/security-and-data-handling.md`
  (audit log, erasure paragraph line 202, API user fields line 116); `docs/api.md:403-415`;
  `freedom_ls/audit_log/README.md` table; `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`
  (new codes). `docs/product/roadmap.md` has a "retention, deletion, and data-subject rights (not yet
  built)" section that this partly delivers.

## 10. Smaller notes

- `AnonymousApplicantAdmin.has_delete_permission` (`course_applications/admin.py:247`) refuses
  claimed applicants and its message points at "the user"; the unclaimed-by-email erasure on user
  delete is the reason a user's records include applicants with no FK to the user.
- `User` integer pk: `subject_key` gives `accounts.user:<pk>`; the pk is reused never (Postgres
  sequence), so entries stay unambiguous after deletion. `Learner` pk is a UUID
  (`CohortMembership`/`Learner` tests use `UUID(...)`; `learner_management/admin.py` imports `UUID`).
- `django.contrib.admin.LogEntry` for the User delete is CASCADE to the actor (see section 3).
- `Learner._base_manager` and `User._base_manager` are used throughout outside request contexts (the
  site-aware default manager filters on the request's site); the force-delete view should use the
  admin `get_queryset` for the lookup (as revoke does) and `_base_manager` inside the transaction.

status: ok
