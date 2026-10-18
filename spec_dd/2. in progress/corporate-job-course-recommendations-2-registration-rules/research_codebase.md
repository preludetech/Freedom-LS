# Research: what registration rules touch, reuse and conflict with in the codebase

Topic `codebase`, for spec 2 (registration rules, `register` outcome). Paths are relative to the repo
root. Builds on `spec_dd/1. next/corporate-job-course-recommendations/research_fls_user_attributes_and_registrations.md`
(§4 registration paths) and `research_fls_backends_and_toggles.md` (§1 seam, §4 tasks/webhooks); it
re-verifies them against the code and adds what has changed since.

## 0. What exists and what is only planned

- **Spec 1 has landed on this branch.** `freedom_ls/hr_attributes/` exists, is in `INSTALLED_APPS`
  (`config/settings_base.py:123`), and `spec_dd/3. done/2026-10-10_09:58_corporate-job-course-recommendations-1-hr-attributes/` holds its spec, plan and QA.
- Built in `freedom_ls/hr_attributes/models.py`: `JobTitle`, `Department`, `Location` (each
  `SiteAwareModel`, per-`organisation`, `name`, `is_active`, manager `ListEntryManager`),
  `LearnerHRAttributes` (one-to-one `Learner`, related name `hr_attributes`; nullable FKs `job_title`,
  `department`, `location`; four nullable `DateField`s `organisation_start_date`, `job_title_start_date`,
  `department_start_date`, `location_start_date`), and `OrganisationHRSettings` (one-to-one
  `Organisation`, related name `hr_settings`, `registration_rules_enabled` default False; no row also
  means off). App label is `freedom_ls_hr_attributes`.
- **Nothing in the code reads `registration_rules_enabled`** (grep: only the model, admin inline,
  factories, migration, tests). Spec 2 is the first reader. A learner may have no `LearnerHRAttributes`
  row at all (reverse one-to-one raises `RelatedObjectDoesNotExist`), so evaluation must treat "no row"
  as "all attributes empty" and must not use the reverse accessor naively.
- **Nothing hooks attribute change or Learner creation.** `hr_attributes/apps.py` has no `ready()`,
  there is no `signals.py`; the attributes reach `Learner` only through `LearnerHRAttributesInline` on
  `LearnerAdmin` (wired by `LearnerAdmin.inlines = [*LearnerAdmin.inlines, LearnerHRAttributesInline]`
  at the bottom of `hr_attributes/admin.py`). Spec 2 must add the triggers.
- **A rules app does not exist.** There is no audit-log app either (`freedom_ls/*audit*` empty);
  `educator-interface-11-audit-log` is still an idea in `spec_dd/1. next/` (model: site-aware,
  append-only, actor/action/target/organisation/reason/JSON details; "registration deactivated" is in
  its vocabulary). `educator-interface-7-learner-administration` is in progress as an idea/todo only
  (its learner detail page lists "registrations with source and status"); no source display is in code.
- `spec_dd/2. in progress/corporate-job-course-recommendations-2-registration-rules/` already holds a
  `1. spec.md` alongside `idea.md`; I did not read it, so check it for drift against this file.
- Other planned and not-yet-existing things the idea names: `RecommendedCourse` already exists as a model
  (see §7) but without provenance; `fire_webhook_event` cohort events are a TODO
  (`learner_management/utils.py:announce_cohort_registration_change`).

## 1. `LearnerCourseRegistration` and every path that touches it

Model: `freedom_ls/learner_management/models.py:142`. Fields: `course` (PROTECT FK, related name
`learner_registrations`), `learner` (CASCADE FK to `Learner`), `is_active` (default True),
`self_registered` (bool default False, added in migration `0002_learnercourseregistration_self_registered`,
help text "The learner registered themselves rather than being registered by staff"), `registered_at`
(`auto_now_add`). Unique constraint `unique_learner_course_registration` on `(site, learner, course)`:
**one row ever per learner and course per site, active or not.** A rule therefore cannot make a second
row beside an existing inactive one; it must update or skip it. No `updated_at`, no `created_by`, no
source field, no history. Site-aware via `SiteAwareModel`.

Paths that create or change it in non-test code (grep of `freedom_ls/`):

| Path | Where | Effect |
|---|---|---|
| Learner self-registers | `learner_interface/views.py:~900`, `update_or_create(learner, course, defaults={"is_active": True}, create_defaults={"is_active": True, "self_registered": True})` | Creates with `self_registered=True`; **reactivates** an inactive row (including one staff deactivated) and leaves `self_registered` unchanged. Gated first by `get_course_access_backend().get_access(...).can_self_register`. Then deletes any `RecommendedCourse` for the user and course (line ~912). |
| Django admin | `learner_management/admin.py:376` `LearnerCourseRegistrationAdmin` (form `LearnerCourseRegistrationAdminForm`, `readonly_fields = ["self_registered", "registered_at"]`) | Staff create/edit/deactivate. `LearnerRegistrationInline` on `LearnerAdmin` is read-only. |
| Factories/QA commands | `learner_management/factories.py:103`, many `qa_helpers/management/commands/*` | Test/QA only. |

Findings that matter for the rule design:

- **There is no other production creator.** The educator interface does not create or deactivate
  `LearnerCourseRegistration` today (`educator_interface/views.py` only reads it; lines ~769, ~893).
  There is no bulk-import path, no application-approval path and no deactivate-with-reason helper. There
  is no `queryset.update(is_active=False)` on registrations anywhere. So "a rule never takes over a
  registration that already existed" only has to hold against the admin, the self-register view, and
  whatever educator-interface specs 7/8 add later.
- **Deactivation is not announced and retires nothing.** `learner_progress/signals.py:194`
  `ensure_course_progress_on_learner_registration` returns early if `not instance.is_active`; the comment
  at line ~183 states there is deliberately no `post_delete`/deactivation counterpart: "removing a
  membership, withdrawing a registration and deactivating a learner are access decisions, and none of
  them retires work already recorded." Retraction by `is_active=False` therefore matches the idea.
  Access is gated on `is_active` in `learner_management/utils.py:is_registered_for_course` (also
  requires `learner__is_active=True`), so a deactivated row removes access while the `CourseProgress`
  rows remain.
- **Reactivation does not re-announce.** On a reactivating save `created` is False so
  `_ensure_and_announce(..., announce=False)` runs: the progress record is ensured (returns the
  existing one) and no `course.registered` fires. A rule reactivating its own row will therefore be
  silent unless the rule code announces explicitly. The idea says "A rule-made registration sends the
  usual notification"; decide whether re-creation after retraction counts (it will not, via the signal).
- **`self_registered` is `False` for "staff made it" and "before the field existed" and, soon, "a rule
  made it".** It is a boolean describing who, not why. A rule-made row with `self_registered=False`
  is indistinguishable from an admin row without new provenance, and the notify branch
  (`if not registration.self_registered: raise_notification(...)`) already does the right thing for it
  with no change.
- `registered_at` is `auto_now_add`: it is the creation date, not the last (re)activation date. A rule
  reactivation does not move it.

## 2. Provenance shape (Open item 1)

What the code bears on:

- A single nullable FK from `LearnerCourseRegistration` to the rule fits the existing grain: the model
  already has the unique `(site, learner, course)`, so a row has at most one origin. `CourseProgress`
  already uses a "exactly one of two nullable FKs" pattern with `CheckConstraint`
  (`learner_progress/models.py:116-181`) and `on_delete=PROTECT`, which is the in-repo precedent for
  recording what granted a thing.
- `LearnerCourseRegistration` lives in `learner_management`, which "must stay installable without"
  optional apps (comments in `hr_attributes/admin.py` and `organisations`). Roadmap decision 1a says core
  apps never import the optional app. A real FK from `learner_management.LearnerCourseRegistration`
  to a model in the rules app would make the core app depend on the optional one, and a migration in
  `learner_management` referencing `freedom_ls_registration_rules.RegistrationRule` would break any
  project that omits the rules app. So the FK, if used, must live the other way round, **or** the core
  field must be generic (e.g. a `source` string/choice) with the rule link stored in the rules app.
- Option the code makes natural: a rules-app model `RuleRegistration` (or similar) with one-to-one to
  `LearnerCourseRegistration` (on the rules-app side, so core imports nothing) plus FK to the rule and a
  `deactivated_by_rule` flag. This keeps core untouched ("A project that leaves the app out sees no
  change") but needs a join in every "source" display (educator-interface 7), in spec 3's "every
  registration path clears one", and in the "reactivates only rows it deactivated itself" rule.
- Option with a small core change: add a nullable `source` field (choices e.g. admin / self / rule) or
  nullable generic `origin_content_type`/`origin_id` to `LearnerCourseRegistration`. Roadmap caution
  line 392-396 says spec 2 "adds provenance to `LearnerCourseRegistration`", so the roadmap assumes a
  change to the core model, and educator-interface 7 reads it. Note the roadmap also says spec 1 "adds no
  columns or migrations to `learner_management`" but does not forbid spec 2 doing so.
- `self_registered` should remain as is (it drives the notify branch, `record_course_self_registered`
  analytics, and admin readonly display `learner_management/admin.py:389-393`). Treat it as a derived
  duplicate of source=self only if a source field is added; leaving it avoids touching three call sites.
- "Reactivates only rows it deactivated itself" needs a second fact beyond "made by the rule": which
  deactivations were the rule's. Staff deactivation is a bare `is_active=False` with no actor, so the
  rule must store "I deactivated this" (e.g. a nullable `deactivated_by_rule` FK/timestamp) or treat
  any inactive row with provenance=rule as its own. The latter is wrong if staff deactivate a rule-made
  row later; so a separate marker is needed. There is no audit log to reconstruct this from.
- Rows existing before the effort have no source; "false for registrations made before this field
  existed, whoever made them" is the existing convention (`models.py:152` comment). A new nullable
  source column would follow it: null/default = unknown/staff.

## 3. `course.registered` and `fire_webhook_event` outside a request (Open item 2)

- Notification path works without a request. `learner_progress/signals.py:_ensure_and_announce`
  (line 122) calls `comms.notify.raise_notification(user=..., category="course.registered", target=course,
  site_id=registration.site_id, data={"course_title": ...})` with an explicit `site_id`; it writes from
  `transaction.on_commit(..., robust=True)` and enqueues `deliver_notification` per
  `NOTIFICATION_DELIVERY_BACKENDS` with `args=[backend_path, str(notification.pk), site_id]`. The category
  is registered in `base/notification_categories.py:39` (key `course.registered`); an FLS category the
  project omitted from `NOTIFICATION_CATEGORIES` is silently skipped. So a rule-made registration
  gets the learner notification "as an admin registration does" **for free** provided it is saved through
  the ORM with `self_registered=False`, because `post_save` -> `on_commit` -> `_ensure_and_announce` runs
  in a task too (note: `on_commit` inside a task needs a transaction; in autocommit the callback runs
  immediately; inside `atomic()` it runs at commit; bulk_create or queryset.update would bypass the signal).
- Webhook path does **not** work without a request. `webhooks/events.py:fire_webhook_event` validates
  the type, then reads `_thread_locals.request`; if `None` it returns silently ("Silently returns if called
  outside a request context (e.g. management commands, shell, data migrations)"). Site comes only from
  `get_cached_site(request)`. It has no `site_id` parameter. `_ensure_and_announce` calls it
  unconditionally, so in a `django.tasks` worker (no request) a rule-made registration produces the
  notification but **no `course.registered` webhook and no error**.
- Subtlety: with `ImmediateBackend` (default in `config/settings_base.py:603`, dev and tests) the task
  runs inline on the calling thread, so if enqueued from a request (e.g. an admin save) the
  thread-local request is still set and the webhook fires against the *request's* site, which could differ
  from the rule's site in principle. Under `DatabaseBackend` (prod, `settings_prod.py:87`, `settings_defaults.DATABASE_TASKS`)
  there is no request. Behaviour differs by backend, so tests under ImmediateBackend would pass while prod
  silently drops the webhook. A spec should test with the database backend, as
  `deployment/tests/test_housekeeping.py:51` and `mail/tests/test_backends.py:147` do (`settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}`).
- Options the code supports: (a) add an optional `site_id: int | None = None` to `fire_webhook_event`
  (it already builds `WebhookEvent(..., site_id=site_id)` and enqueues with explicit `site_id`; the
  downstream `dispatch_event(event_id, site_id)` is already request-free and filters explicitly), used
  when no request is present. That is a small change in `freedom_ls/webhooks/events.py`, and also fixes
  the ImmediateBackend ambiguity by letting callers pass the site. `_ensure_and_announce` already has
  `registration.site_id`. (b) Have the rule task set `_thread_locals.request` to a stand-in, as
  `qa_helpers/.../qa_create_organisation_scenarios.py:135` and `qa_create_notification_scenarios.py:113`
  do; this is a test/QA-only hack with `middleware.py` save/restore semantics, not a pattern for
  production code. (c) Leave webhooks off for rule-made rows (contradicts idea: "usual `course.registered`
  notification"; the idea says notification, the webhook is the Open item). Specs 3 and 5 build on the
  answer, and (a) is the only one that does not need per-caller workarounds. Note `webhooks/events.py`
  docstring step 2 "Capture site_id from current request context (or return early)" is the documented
  contract and `learner_management/capabilities.py:57` describes `_current_site` as resolving "the
  same way fire_webhook_event does" (read-only comment; changing the function doesn't break it).
- Payload fields `_ensure_and_announce` builds: `user_id`, `user_email`, `course_id`, `course_title`,
  `registered_at`, `organisation_id`, `course_progress_id`; event listed in
  `base/webhook_event_types.py:4,23`. No field says who or what registered; adding a source to the
  payload is possible but is a schema change for integrators.
- `accounts/allauth_account_adapter.py:33-35` also calls `fire_webhook_event` (inside a request).

## 4. COURSE_ACCESS_BACKEND seam and the `app_settings` pattern

Files: `freedom_ls/course_access/{config.py,loader.py,backends.py,checks.py}`.

- Settings via `freedom_ls/base/app_settings.py`: `class CourseAccessConfig(AppSettings)` with
  `declared_settings = {"COURSE_ACCESS_BACKEND": Setting(required=True), ...}` and a module-level
  `config = CourseAccessConfig()`. `config.NAME` returns the project's Django setting or the declared
  default; a required, unset setting raises `ImproperlyConfigured` lazily. `required_settings_errors(config,
  app_label)` builds `<app_label>.E001` errors for a system check. Reads must not happen at import time.
- Loader: `loader.get_course_access_backend()` is `@functools.cache`; it does
  `import_string(config.COURSE_ACCESS_BACKEND)`, instantiates it, and wraps it in
  `VisibilityEnforcingBackend` so no backend can bypass visibility. Test caveat: callers using
  `override_settings(COURSE_ACCESS_BACKEND=...)` must `cache_clear()` before/after
  (`freedom_ls/conftest.py:87` has a fixture for it).
- Checks: `course_access/checks.py` has E-numbered checks (including E003 "backend names an app that
  isn't installed", `apps.is_installed`-style lookup of the dotted path's app).
- Conformance: `freedom_ls/contrib/conformance/test_settings.py` has `_COURSE_ACCESS_BACKEND_CONSUMERS`
  and skips when no consumer is installed; the pattern for "a seam whose backends must satisfy a
  contract test".
- Seam *shape* for rule kinds should follow this: an ABC/Protocol in the rules app (CLAUDE.md says
  "Don't create abstract base classes unless asked" but the idea asks for a seam "in the style of
  `COURSE_ACCESS_BACKEND`", and `backends.CourseAccessBackend` is the precedent), a `RULE_KIND_BACKENDS`
  style setting declared in `config.py` via `AppSettings` with a default pointing at the attribute-
  matching kind, a cached loader, and the `skills` named in the idea: `fls-dev:app-settings`. Two
  differences from `COURSE_ACCESS_BACKEND` to be aware of: that setting is a **single** backend;
  rule kinds are **several** coexisting kinds, so a dict/list of dotted paths keyed by a per-rule `kind`
  field is needed (the course side stores opaque per-course config in `Course.access_config`
  (`content_engine/models/courses.py:160-169`, "interpreted ONLY by the active backend; core never reads
  or branches on its contents"), which is a precedent for an opaque JSON `conditions` column interpreted
  only by the kind; the idea instead settles on structured conditions, so choose deliberately).
  `AppSettings.__getattr__` deep-copies defaults and treats `""`/`None` as unset, so an empty dict falls
  back to the default.

## 5. `django.tasks` usage and carrying site

Settings: `"django.tasks"` in `INSTALLED_APPS` (`settings_base.py:85`); `TASKS` default is
`ImmediateBackend` (`settings_base.py:603`); prod overrides to `django_tasks_db.DatabaseBackend` via
`fls_defaults.DATABASE_TASKS` (`settings_prod.py:87`); dev opts into queueing (`settings_dev.py:89`).

Existing tasks and how they carry the site (all pass primitive args, all explicit):

| Task | File | Args |
|---|---|---|
| `_dispatch_event_task` | `webhooks/events.py:42` | `[str(event.pk), site_id]` |
| `_generate_cohort_report_task` | `reports/tasks.py:20` | `(report_id: str, site_id: int)`; wrapper delegating to a plain function; all queries `filter(site_id=...)` |
| `deliver_notification` | `comms/tasks.py:15` (enqueued from `comms/notify.py`) | `[backend_path, str(notification.pk), site_id]` |
| mail send | `mail/tasks.py:42`, `mail/backends.py:58` | not read in detail |

The pattern to copy (documented in `reports/tasks.py` docstring and `webhooks/events.py:dispatch_event`):
a `@task()` wrapper taking JSON-safe primitives, delegating to a plain function, which "filters explicitly
on `site_id` rather than relying on `SiteAwareManager`'s thread-local site". `SiteAwareManager.get_queryset`
(`site_aware_models/models.py:117`) filters only when `_thread_locals.request` exists; with no request it
returns the **unfiltered** queryset across all sites, so in a worker `Model.objects.get(pk=...)` spans
tenants. Writes: `SiteAwareModelBase._set_site_from_request` only fills `site` from a request, so a
task creating a `LearnerCourseRegistration` must pass `site=`/`site_id=` explicitly and use
`_base_manager` for lookups the way `ensure_learner`, `register_cohort_for_course` and
`ensure_course_progress_record` do (their docstrings explain the foreign-ambient-site trap with
`update_or_create`). `get_cached_site(None)` raises `SiteResolutionError` unless `FORCE_SITE_NAME` is
set, so rule code must never call it from the task.

Enqueue conventions: `default_task_backend.enqueue(fn, args=[...], kwargs={})` (every call site passes both
`args` and `kwargs`). `reports/views.py:96` enqueues from `transaction.on_commit(lambda: ...)`, the right
pattern for rule triggers inside a save so the task never reads uncommitted state; `comms/notify.py` uses
`on_commit(write, robust=True)`. No task is idempotency-keyed in the framework; at-least-once is handled
per task by unique rows (`WebhookDelivery` get_or_create comment). Rule evaluation is naturally idempotent
(compare desired state to actual), which suits at-least-once. There is no existing de-duplication of
duplicate enqueues, so a learner edited five times queues five evaluations; this needs a decision (enqueue
per rule-and-learner vs per learner vs per organisation).

Housekeeping: `deployment/housekeeping.py` finds stuck `DBTaskResult` rows (`started_at` old) and reports
them; long evaluations (enable on a large organisation) fall under that watchdog. Tests: under
ImmediateBackend tasks run inline; switch `settings.TASKS` to the DB backend to test queued behaviour.

## 6. What "started" could mean (Open item 3)

`freedom_ls/learner_progress/models.py`:

- **`CourseProgress`** (line 106): one row per `(registration, learner)`, minted on registration commit by
  the post_save receiver, so an active registration always has one (barring failure/lag).
  `created_at` = registration date; **`started_at`** (nullable) = first content access;
  `last_accessed_time`; `completed_time`; `progress_percentage` (int, default 0, indexed);
  `last_accessed_item`. The model comment (lines 134-137) says: "created_at is the registration date and
  started_at is the first content access. Nothing may read one for the other."
- `started_at` is stamped in exactly one place: `learner_interface/views.py:~1030-1043` (the player view,
  first time a collection item is viewed and not blocked), once, never re-stamped, and fires
  `record_course_started`. It is *not* set by background percentage recalculation
  (`signals.py:recalculate_progress_percentage` uses `update_fields=["progress_percentage"]` precisely so
  it doesn't look like a visit).
- `learner_progress/admin.py:47-66` already has a monitoring filter that splits "registered, not
  started" from "started" using `started_at__isnull=True`: in-repo precedent for the same definition.
  The learner-facing views use `course_progress.started_at` too (`learner_interface/utils.py:~848-889`,
  `course_finish.html:82-88`).
- **`TopicProgress`** (line 59): `start_time` (`auto_now_add`), `last_accessed_time`, `complete_time`.
  Rows can exist without completion. **`CourseFormAttempt`** (line 242, links `FormProgress` to a
  `CourseProgress`): a form attempt started inside a course.
- Therefore three candidate definitions, in order of strictness: (1) `started_at IS NOT NULL` (first
  content access; one indexed column, one stamping point, matches admin filter and `course_finish`);
  (2) `progress_percentage > 0` or `completed_time` set (misses a learner who opened content but
  completed nothing, so they could be retracted from a course they are mid-way through); (3) any
  `TopicProgress`/`CourseFormAttempt`/`FormProgress` rows (broadest, more joins, and bulk-created or
  imported rows (`bulk_create` bypasses `save()`/signals) can exist without a visit).
  The idea's two phrasings map to (2) "any progress" and (3) "any activity". The code's own definition
  is (1), and it is the safest for the "left alone if they have" rule because it triggers on the first
  visit. Caveat: `started_at` is only written by the player view, so a form submitted through another
  entry point, or progress written by import/`bulk_create` without a visit, will not set it. Consider
  "started = `started_at` set OR `progress_percentage > 0` OR `completed_time` set" as a union guard.
- A learner with a cohort-granted `CourseProgress` for the same course also has a separate record (one
  per registration): `ensure_course_progress_record` docstring says a second grant is a second record.
  "Started" for retraction should look at the progress record granted by *this* `learner_registration`
  (`CourseProgress.learner_registration`), not at the learner's whole history in the course; a started
  cohort record should not block retracting the rule's registration, and conversely (also relevant to
  whether a cohort registration counts as "another enabled rule/registration" - it does not; the idea
  only says another *rule* blocks retraction).
- Progress is never deleted by deactivation; `CourseProgress.learner_registration` is `PROTECT`, so
  a registration with a progress row cannot be deleted, which supports "retract = deactivate, never
  delete".

## 7. Learner creation and attribute-change hooks

- `Learner` creation sites: `learner_management/utils.py:ensure_learner` (`update_or_create` via
  `Learner._base_manager`, `defaults={"is_active": True}`, explicit `site=organisation.site`; also
  *reactivates* a removed learner) used by self-registration (`learner_interface/views.py:889`),
  `LearnerFactory`, and QA commands; the admin `LearnerAdmin` (`learner_management/admin.py:191`, form
  `LearnerAdminForm`); and `qa_create_organisation_scenarios.py:306` directly. A `post_save` receiver on
  `Learner` (created, or `is_active` flipped to True) is the single catch-all; `ensure_learner`'s
  `update_or_create` goes through `save()` so it fires. Note a freshly created `Learner` has **no**
  `LearnerHRAttributes` row, so at `Learner` creation a rule that conditions on any attribute cannot
  match (unless the condition is only on... nothing); creation matters mostly for organisations whose rules
  have no matching condition or for later ordering with the attributes row. The attributes row is created
  later by the admin inline (post_save of `LearnerHRAttributes`), so the real trigger is that model.
- Attribute change: `LearnerHRAttributes` post_save / post_delete (rare; `can_delete = False` in the inline,
  but the learner delete cascade removes it). An inline save with no changed field still saves the model
  only when `has_changed()`, otherwise no signal; no spec-1 hook exists. `queryset.update()`/`bulk_create`
  (a spec-5 CSV import) bypass signals, which is why spec 5 is described as running "one rule evaluation
  per import"; the trigger API should therefore be a plain function (`evaluate_learners(site_id,
  learner_ids)`) callable from signals and imports alike, not signal-only.
- `Learner.organisation` change: `LearnerAdmin` allows editing `organisation` (field in `fields`); a learner moved
  to another organisation changes which rules apply (rules belong to one organisation) and
  `LearnerHRAttributes.clean()` refuses entries from the old organisation only when that row is saved
  (see `_picker_querysets` docstring in `hr_attributes/admin.py`). The idea does not list organisation
  change as a trigger. Also `Learner.is_active=False`: `is_registered_for_course` requires
  `learner__is_active=True`; evaluation should skip inactive learners (as `_ensure_for_membership` and
  `ensure_course_progress_records_for_cohort_registration` do).
- List-entry deactivation: `ListEntryAdmin.deactivate_selected` uses `queryset.update(is_active=False)`
  (no signal), consistent with "deactivating an entry retracts nothing".
- The organisation switch (`OrganisationHRSettings.registration_rules_enabled`) is a one-to-one reverse
  `Organisation.hr_settings`, absent row means off; evaluation needs a query that handles no row
  (e.g. `OrganisationHRSettings.objects.filter(organisation=..., registration_rules_enabled=True).exists()`).
  Turning the switch on should itself be a trigger (decision 11: "Off means no evaluation") or enabling
  rules covers it; the idea does not say.
- Existing site-creation receiver: `get_default_organisation(site)` "guaranteed to exist by the post_save
  receiver that gives every Site one" (`learner_interface/views.py:886`), so each Site has at least one
  Organisation.

`RecommendedCourse` (`views.py:912`: `RecommendedCourse.objects.filter(user=..., course=...).delete()`)
is touched only on self-registration; rule-made registrations should do the same clearing only if spec 3
says so ("every registration path clears one" is spec 3's scope).

## 8. Admin: `SiteAwareModelAdmin`

`freedom_ls/site_aware_models/admin.py:23`: `class SiteAwareModelAdmin(ModelAdmin)` (unfold `ModelAdmin`),
`exclude = ["site"]` and a CSS bundle; the site is filled from the request on save by
`SiteAwareModelBase._set_site_from_request`. Variants: `SiteAwareExportModelAdmin` (CSV export, formula-
safe), `GuardedSiteAwareModelAdmin` (guardian object permissions). Precedents for the rule admin:

- Registry: `@admin.register(...)` on a `SiteAwareModelAdmin` subclass (e.g. `LearnerCourseRegistrationAdmin`
  with `form = LearnerCourseRegistrationAdminForm`; `ConstraintValidationFormMixin` surfaces model
  constraints as form errors).
- Custom actions with `@admin.action` and `self.message_user(request, ngettext(...))`
  (`hr_attributes/admin.py:57-85`); `has_delete_permission` overrides to forbid deletion
  (`webhooks/admin.py:191,236`), the precedent for "a rule can be deleted only once it is disabled" (a
  `has_delete_permission(request, obj)` that returns `obj is None or not obj.is_enabled`; note the
  bulk-delete action calls it with `obj=None`, and deletion of a rule with provenance FKs from
  registrations needs a defined `on_delete`).
- Cross-app contribution to existing admins is done by appending to `.inlines` from the optional app's
  `admin.py` (`LearnerAdmin.inlines = [*LearnerAdmin.inlines, ...]`). The rules app can use the same to
  show a registration's source on `LearnerCourseRegistrationAdmin` without core knowing it, and a
  rule-source readonly field/column on `LearnerRegistrationInline`.
- **A preview-before-confirm step is not an existing admin pattern.** There is no
  intermediate-confirmation admin view in `hr_attributes`; `ExportForm`/`skip_export_form` is the only
  related admin form hack. Django's own delete confirmation and the `ModelAdmin.response_*` hooks, or a
  custom `get_urls()` view rendering the list, would have to be new; per the idea "a list, not a count"
  of learners, so must be paged/bounded for a large organisation (the
  `ReportTooLargeError` in `reports/gather.py` shows a size guard precedent).
- Admin tests use `fls-dev:testing` with `mock_site_context` (`freedom_ls/conftest.py:168`) because admin
  views need a request/site.

## 9. Audit log

None in code (see §0). Related: `role_based_permissions/utils.py` carries six `# TODO: AuditLog entry`
comments (per the audit-log idea); never delete these. `LegalConsent`, `WebhookEvent` and `assigned_by` are
the only audit-shaped records. So rule actions (enable, edit, disable, delete, a run that registered N
learners, retraction) have nowhere to write today. The idea is conditional ("If `educator-interface-11-audit-log` has landed")
so the spec should write its own minimal record or define the integration point as a later, optional
call, not depend on it. The model for the rule can carry `created_at`/`updated_at` via `TimestampedModel`
(`site_aware_models/models.py:167`) and the evaluation run could be its own small result table if the
admin wants to show "last run registered N". The rule-made registration's own provenance is the only
lasting trace of "why", since `LearnerCourseRegistration` has no history.

## 10. Is the rules app optional in `INSTALLED_APPS` (Open item 4)

- Precedent: `hr_attributes` is optional by design and enforced by direction of imports: it imports
  `learner_management.admin.LearnerAdmin`, `organisations.admin.OrganisationAdmin`,
  `learner_management.models.Learner`; core apps never import it (its comments: "learner_management... must
  stay installable without this app"). Contract is enforced by `test_organisation/import_contracts.toml`
  and the `app-map-fresh` and `lint-imports` hooks (spec 1 spec line 197), and `docs/app_structure.md`.
  The rules app depends on `hr_attributes` (conditions use its lists and the switch), so it can be
  installed only with `hr_attributes`; add a system check (like `course_access/checks.py` E003 using
  `apps.is_installed`) that errors if rules is installed without `hr_attributes`.
- Because rules reach into `learner_management` (registration creation, receivers) and optionally
  `comms`/`webhooks`/`learner_progress`, "optional in `INSTALLED_APPS`" is feasible if all hooks
  (post_save receivers, admin inlines) are registered from the rules app's own `ready()`/`admin.py`.
  The only core touchpoints that would break it: a provenance column/FK on `LearnerCourseRegistration`
  pointing into the rules app (see §2) and the `fire_webhook_event` change (§3, which is app-agnostic).
  A provenance design where core holds a plain `source` value and rules holds the FK avoids the problem.
- Specs 3 and 4 build on this: spec 3 adds `RecommendedCourse` provenance (`RecommendedCourse` lives in
  `learner_interface`/`course_applications`-adjacent code; core `learner_interface/views.py` already
  imports it) and edits the self-registration view in `learner_interface`; if the rules app is optional,
  spec 3's "clear a recommendation on every registration path" must not import the rules app from core
  (use a signal or a core-owned provenance field).
- Two layers of "off" exist already: `INSTALLED_APPS` (app absent) and `registration_rules_enabled`
  (per organisation). The idea's switch makes the second layer cheap; the first (INSTALLED_APPS) is needed
  for the zero-footprint guarantee of decision 1a (no tables, no admin entries, no receivers firing on
  every `Learner`/`LearnerHRAttributes` save). I recommend: optional in `INSTALLED_APPS`, per-organisation
  switch on top, and a system check tying it to `hr_attributes`.

## 11. Other conflict and reuse points

- **Unique constraint interplay.** `unique_learner_course_registration` means: if the learner already has
  an inactive row the rule would otherwise create, the rule must classify it (staff-deactivated: leave;
  rule-deactivated: reactivate; self/admin made and active: leave). The `update_or_create` in the self-
  register view reactivates *any* inactive row, including a rule-deactivated or staff-deactivated one, and
  does not touch provenance; after that a row with `source=rule` could be self-reactivated: define whether
  ownership transfers. Also the view's `update_or_create` is not guarded by `select_for_update`, so a
  rule task and a self-registration can race; the constraint makes the loser an `IntegrityError` that a
  rule-side `get_or_create`/`ignore_conflicts` must handle.
- **Messaging policy.** `messaging_policy/models.py:147` `LearnerCourseRegistrationMessagingConfig` has a
  OneToOne-ish link to a `LearnerCourseRegistration`; `messaging_policy/policy.py:251` queries active
  learner and cohort registrations for messaging. Rule-made registrations will flow into these queries
  unchanged (it reads `is_active`); rows retracted vanish from messaging, a behaviour worth stating.
- **Deadlines.** `learner_management/deadline_utils.py` reads `LearnerCourseRegistration` (lines 96, 188,
  262, 396) and `LearnerDeadline` hangs off the registration via CASCADE; a rule-made registration has
  no deadline until staff add one. Not a conflict, but rules do not carry deadlines.
- **Course access backend.** `get_course_access_backend().get_access(...).can_self_register` gates only
  the self-register view. A rule registers regardless of access type (application-gated courses
  included), so the rule admin should decide whether to validate the course (`Course.access_config`,
  visibility "hidden"/"coming soon" via `VisibilityEnforcingBackend`) when a rule is saved.
  `is_registered_for_course` does not consult the backend; `learner_interface/views.py:1116` notes a
  backend can gate on registration.
- **Danger tooling.** `dev_tools/management/commands/danger_content_delete.py:101` lists
  `("freedom_ls_learner_management", "LearnerCourseRegistration")` among tables it clears; a new rules
  app's tables and the registration provenance FK ordering will need adding there if rule rows reference
  courses (`PROTECT`).
- **Test infrastructure.** Factories: `LearnerCourseRegistrationFactory` (learner_management),
  `hr_attributes/factories.py` (builds on `LearnerFactory`); `SiteAwareFactory` reads the thread-local
  request (`site_aware_models/factories.py:15`). QA commands such as `qa_create_hr_attributes_scenario`
  exist for the earlier spec and are the model for a rule scenario command; `mock_site_context` for admin
  views; DB task backend switch for queued tests.
- **Domain vocabulary.** `.claude/skills/domain-glossary/SKILL.md` already mentions
  `registration_rules_enabled`; new terms (registration rule, outcome, provenance) go there.

## 12. Answers to the four "Open until the spec" items, with the code's bearing

1. **Provenance shape.** The code favours not putting an FK into the optional app on the core model
   (decision 1a; core must not import `hr_attributes`/rules). Two workable shapes: (A) rules-app side-table
   one-to-one to `LearnerCourseRegistration` with FK to the rule plus a deactivated-by-rule marker; core
   unchanged. (B) a small core change: nullable `source`/origin on `LearnerCourseRegistration` (plain
   choices or generic key) with the rule FK in the rules app. `self_registered` stays untouched either way
   (drives notify branch and analytics). (A) honours "project that leaves the app out sees no change"
   and the cross-app inlines pattern, but every reader (educator-interface 7 source display, spec 3
   clearing, spec 5) needs a join. Either needs a rule-owned "I deactivated this" marker because staff
   deactivation leaves no trace.
2. **`course.registered` outside a request.** Notification works as-is (`raise_notification` takes
   explicit `site_id`). The webhook is silently dropped in a worker because `fire_webhook_event` resolves
   site from the thread-local request only; under ImmediateBackend in tests it will misleadingly appear to
   work. Smallest fix: let `fire_webhook_event` accept an explicit `site_id` (the downstream task and
   `WebhookEvent` already carry it) and pass `registration.site_id` from `_ensure_and_announce`. Reactivation
   by a rule does not re-announce (signal's `created` is False).
3. **"Started".** Existing definition in code: `CourseProgress.started_at IS NOT NULL` (first content
   access, one stamping point in the player view, used by the admin filter and learner pages), evaluated on
   the `CourseProgress` row granted by that registration (`learner_registration`). Wider "any progress" or
   "any activity" ways exist (`progress_percentage`, `TopicProgress`, `CourseFormAttempt`) but have gaps
   (bulk-created rows, no visit). Recommend `started_at` set, optionally unioned with `progress_percentage
   > 0` / `completed_time` for rows written without a visit.
4. **Optional in `INSTALLED_APPS`.** Yes is feasible and consistent with spec 1: the rules app imports
   `hr_attributes`, `learner_management` and registers its own receivers/admin; add a check that it
   requires `hr_attributes`. Only the provenance choice (item 1) and the webhook change (item 2) could
   break it, and both can be made app-agnostic.

## 13. Risks and things the spec must settle (found while reading)

- Trigger fan-out: no existing receiver for `LearnerHRAttributes`/`Learner`; no debounce of repeated
  enqueues; bulk paths (`queryset.update`, import) bypass signals.
- Race between rule task and self-registration/admin on the unique constraint.
- Large organisations: preview must be a bounded/paged list; enable evaluation is O(learners) in one task
  under a stuck-task watchdog (`deployment/housekeeping.py`).
- Learner with no `LearnerHRAttributes` row; list entries from other organisations; deactivated entries
  (conditions on them must keep matching: use `_base_manager`/unfiltered by `is_active`, not
  `for_picker`, when evaluating).
- Dates: all four nullable, unordered; "on or after / before" must define null (no date = no match) and
  `DateField` comparison with today's boundaries; no timezone issue (DateField).
- Switch off: existing rows stay and, per idea, nothing is evaluated, so retractions are also suspended.
- Deleting a rule: provenance FKs (`PROTECT` vs `SET_NULL`) decide whether deletion orphans rule-made
  registrations; the "delete only when disabled" admin rule does not by itself answer it.

status: ok · reason: complete; read-only research, spec 1 verified landed, no files besides this one written
