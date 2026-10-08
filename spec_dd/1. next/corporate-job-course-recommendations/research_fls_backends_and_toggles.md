# Research: how FLS makes a feature pluggable and switchable

Scope: codebase only. Question: how to make "automatic registration rules" (auto-register learners into courses by role / job title) switchable per client, with room for alternative rule / recommendation backends later (see `idea.md`).

## 1. The pluggable-backend pattern

### 1.1 `AppSettings` / `Setting` (`freedom_ls/base/app_settings.py`)
- `Setting(default=None, required=False)` is a NamedTuple. `AppSettings` subclasses set `declared_settings: dict[str, Setting]`.
- `config.NAME` reads `django.conf.settings.NAME` lazily. A string value is stripped, and None or "" falls back to the declared default (deep-copied, so mutable defaults are safe).
- A `required=True` setting that is unset raises `ImproperlyConfigured` on read. It never raises at import.
- `AppSettings.missing_required()` returns the unset required names and never raises.
- `required_settings_errors(config, app_label)` builds `<app_label>.E001` `Error`s for a system check.
- Every app has a `config.py` with a module-level `config = XConfig()`. Examples: `course_access`, `comms`, `mail`, `webhooks`, `learner_management`, `blog`, `organisations`, `deployment`, `reports`, `referral_tracking`, `google_tag`.
- Skills: `claude_plugins/fls-dev/skills/app-settings/SKILL.md` is the FLS overlay. It points at `freedom_ls.base.app_settings` and uses `COURSE_ACCESS_BACKEND` as the worked example. It defers to `ds:app-settings`, which lives in `claude_plugins/django-stack/skills/app-settings/SKILL.md`. There is no `ds` directory. The generic skill is in the `django-stack` plugin.

### 1.2 `COURSE_ACCESS_BACKEND` end to end (`freedom_ls/course_access/`)
- **Declared** in `config.py`: `CourseAccessConfig.declared_settings["COURSE_ACCESS_BACKEND"] = Setting(required=True)`. It has no built-in default.
- **Contract** in `backends.py`:
  - Base class `CourseAccessBackend`.
  - Frozen dataclasses `CourseAccessDecision`, `AccessBadge`, `DashboardContribution`.
  - Core implementation `FreeOnlyCourseAccessBackend`.
  - The richer `ApplicationCourseAccessBackend(FreeOnlyCourseAccessBackend)` lives in `freedom_ls/course_applications/backends.py`, so `course_access` never imports `course_applications`.
- **Loaded** in `loader.py`:
  - `get_course_access_backend()` is `@functools.cache`d. It does `import_string(config.COURSE_ACCESS_BACKEND)`, instantiates the class, and wraps it in `VisibilityEnforcingBackend` so no backend can bypass visibility.
  - Tests that `override_settings` must call `.cache_clear()` before and after.
  - `validate_course_access_config` is the hook target for `COURSE_ACCESS_CONFIG_VALIDATOR`. `content_engine` resolves it by `import_string`, and `content_engine` never imports `course_access` (this avoids a dependency cycle).
- **Selected** in `config/settings_base.py` (~line 598): `COURSE_ACCESS_BACKEND = "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"`. A comment there says the free-only backend is the no-applications fallback.
- **Validated at startup** in `checks.py`, registered in `apps.py` `ready()`:
  - `freedom_ls_course_access.E001`: required setting missing (via `required_settings_errors`).
  - `E002`: a stored `Course.access_config` is rejected by the active backend. DB errors are swallowed so a fresh checkout stays silent.
  - `E003`: the backend's `freedom_ls.*` module is not in an installed app. A downstream's own backend path is skipped.
  - `W001`: preview overrides are on while `DEBUG=False`.
- **Overridden downstream** by pointing the setting at a class in the host project, and optionally `COURSE_ACCESS_CONFIG_VALIDATOR` at its own validator. The opt-in conformance suite `freedom_ls/contrib/conformance/test_settings.py` checks that the backend loads. Docs: `docs/product/configuration-and-extension.md`, "Pluggable Course Access".

### 1.3 Other backend-style settings
- **Notifications** (`freedom_ls/comms`):
  - `NOTIFICATION_DELIVERY_BACKENDS: list[str]` (default `[]`) names `NotificationDeliveryBackend` subclasses (`comms/delivery.py`; its docstring explicitly mirrors `CourseAccessBackend`).
  - `notify.py` enqueues a `deliver_notification` task per backend path. `tasks.py` does `import_string(path)().deliver(notification)`.
  - `comms/checks.py` E002 flags a path that does not import.
  - `NOTIFICATIONS_ENABLED` (default False) is the on/off switch. `NOTIFICATION_CATEGORIES` is a list a project can extend or trim. An FLS category left out of the list is a silent opt-out.
- **Mail** (`freedom_ls/mail`):
  - `EMAIL_BACKEND = freedom_ls.mail.backends.QueuedEmailBackend` enqueues sends as tasks.
  - `EMAIL_UPSTREAM_BACKEND` (`mail/config.py`) names the real backend.
  - `mail/checks.py` import-validates the dotted path.
- **Icons**: `FREEDOM_LS_ICON_BACKEND` is resolved in `icons/backend.py` by `import_string`.
- **Registration forms**: `SiteSignupPolicy.additional_registration_forms` holds dotted paths. `accounts/registration_forms.py` `load_registration_form_classes()` imports each one, checks the protocol (`applies_to` / `is_complete` / `save`), and raises `ImproperlyConfigured` on any bad entry. The list is stored per Site in the DB but resolved by `import_string`. This is a hybrid: the choice of plug-in is per-site data, and the code is a plug-in contract.
- **Storage**: `REPORTS_STORAGE_ALIAS`, `CONTENT_MEDIA_STORAGE_ALIAS`, `ORGANISATION_LOGO_STORAGE_ALIAS` (aliases into Django `STORAGES`, built by `deployment/storage.py`).
- **Webhooks** are not backend-pluggable. The event-type registry is `webhooks/registry.py`, seeded from `FLS_WEBHOOK_EVENT_TYPES` in settings. Endpoints are per-site DB rows.
- **Documented exception to pluggability**: the report at-risk rules are a fixed list in code, with no settings seam (`configuration-and-extension.md`, "One stated exception"). This is a precedent for what to avoid.

## 2. How features switch on and off today

| Level | Mechanism | Examples |
|---|---|---|
| Deployment, by INSTALLED_APPS | Leave the app out. Code guards with `apps.is_installed(...)`. | `freedom_ls.blog` is optional. `config/urls.py` and `config/views.py` use `apps.is_installed("freedom_ls.blog")`. `qa_helpers` / `dev_tools` are added only in `settings_dev.py`. `dev_tools` management commands guard on `apps.is_installed("freedom_ls.course_applications")`. Docs: "Removing an FLS app removes its checks along with it"; conformance checks skip removed apps. |
| Deployment, by Django setting | An `AppSettings` boolean or a dotted-path choice. | `NOTIFICATIONS_ENABLED` (default False), `DEADLINES_ACTIVE` (`learner_management/config.py`, default True, read in `learner_interface/utils.py` and `views.py`), `ALLOW_SIGN_UPS`, `COURSE_ACCESS_BACKEND` (switching removes the apply flow entirely), `OVERRIDE_*` previews. `FORCE_SITE_NAME` pins one Site per deployment. |
| Per Site (DB) | A `SiteAwareModel` row, with a global setting as the fallback when no row exists. | `accounts.SiteSignupPolicy`: unique per site; `allow_signups`, `require_name`, `require_terms_acceptance`, `additional_registration_forms`. With no row, it falls back to `ALLOW_SIGN_UPS`, `REQUIRE_NAME`, `REQUIRE_TERMS_ACCEPTANCE`. Other per-site config: `WebhookEndpoint` rows and per-site encrypted secrets. `docs/product/multi-tenancy-and-isolation.md`, "Per-Site Configuration", names only signup policy and webhooks. |
| Per organisation | A column or relation on `Organisation` (`organisations/models.py`, `SiteAwareModel` + `TimestampedModel`). | Today it holds only logo, logo-on-dark, name, slug and a default flag (`one_default_organisation_per_site`; a `post_save` receiver on `Site` auto-creates the default). I found no feature toggle at organisation level. `Learner` and `OrganisationMember` link users to organisations (`learner_management/models.py`). |
| Per course | Content frontmatter, loaded by `content_save`. | `access_config` JSON on `Course`, validated by the active backend. |
| Not in use | No feature-flag library (no waffle or constance flags). `unfold.contrib.constance` appears in INSTALLED_APPS as an admin template only. | |

`docs/product/configuration-and-extension.md` describes the extension points as:
- Settings.
- A pluggable backend selected by a dotted path with no built-in default (course access).
- Notification delivery backends.
- App ordering and template shadowing in the host project.
- Optional apps.
- The conformance suite.
- Boot-time system checks.

Its stated philosophy is "the host project has override capability at every layer", and a swap should be "a new backend class and a settings change, with no template, view, or migration work".

## 3. Which level fits "some clients need this, others don't"

The word "client" is ambiguous. It could mean a whole deployment (a downstream project), a Site (one tenant in a deployment), or an organisation (inside a Site).

| Level | Fits when | Pros | Cons / costs |
|---|---|---|---|
| A. Optional app in INSTALLED_APPS (own app, `apps.is_installed` guards) | Client = separate deployment, or the feature should be absent from the schema and UI | Matches blog and course_applications. Nothing left behind in core screens. Zero cost when off. Fits the "new app plus settings change" story. | Cannot vary between Sites in one deployment. Migrations and tables exist if the app is installed anywhere. Core code that wants to call it needs `is_installed` guards or signals, because it cannot import it. |
| B. Django setting (an `AppSettings` bool and/or a dotted-path backend, e.g. `AUTO_REGISTRATION_BACKEND`) | Client = deployment; backend swapping is the main goal | Direct reuse of the `COURSE_ACCESS_BACKEND` pattern: config, loader with `functools.cache`, and system checks (E001/E003, import errors). Supports "other backends later". Cheap to test. | Deployment-wide. Every Site and organisation in that deployment gets the same behaviour. Changing it needs a settings change and a deploy. A required setting with no default forces all downstreams to set it. A default-off bool avoids that (as `NOTIFICATIONS_ENABLED` does). |
| C. Per-Site DB row (a `SiteAwareModel`, like `SiteSignupPolicy`, with a global setting as fallback) | Client = a Site; one deployment serves several clients and ops want to toggle without deploying | Mirrors the established per-site policy and the multi-tenant isolation model (a `SiteAwareModel` is automatically site-filtered). Editable in admin. A "no row means the global default" rule is already a known idiom. | A new model and migration, plus admin. Needs a cache or lookup in background tasks (no request context; the webhook code filters explicitly by `site_id`). The backend still has to be chosen somewhere: the per-site row would hold a dotted-path or key from a registered set. `additional_registration_forms` shows this pattern, with its DB-stored import-path risks. |
| D. Per-organisation flag or rule rows | Client = an organisation within a Site (e.g. one employer inside a multi-employer Site) | Finest granularity. Rules naturally scope to an organisation's learners (`Learner.organisation`). | No precedent for an organisation-level toggle. Every Site has a default Organisation, so org-level toggles must treat a single-org Site sensibly. Most config here would be rule data (which role maps to which course), not a feature switch. |

Layered options exist. Both are patterns already in the repo.
- B plus C: setting for the backend and a global default, per-Site row to enable or disable (the `SiteSignupPolicy` / `ALLOW_SIGN_UPS` pattern).
- A plus B: an optional app, whose backend is selected by setting.

Rule data (which role or title maps to which course) is separate from the switch. The existing analogue is `course_recommendations.RecommendedCourse` (`SiteAwareModel`; user, course, `created_at`; no source, rank or expiry, and the model says to "keep this model standalone and additive"). It is a result record, not a rule.

No `job_title` field exists on `User`, `Learner` or `OrganisationMember`. Role and job data would come in through a registration form (`additional_registration_forms` protocol) or the `User` model. Roles here are `role_based_permissions` roles, which are about permissions, not job.

## 4. Background jobs, signals, notifications, webhooks

- **Tasks**: Django 6 `django.tasks` (`from django.tasks import default_task_backend, task`).
  - `config/settings_base.py` `TASKS` defaults to `ImmediateBackend`, which runs inline, for dev and tests.
  - Production (`settings_prod.py`) sets `TASKS = fls_defaults.DATABASE_TASKS`, i.e. `django_tasks_db.DatabaseBackend` (`django-tasks-db==0.12.0`, pinned).
  - Worker: `manage.py fls_run_worker` (`freedom_ls/deployment/management/commands/fls_run_worker.py`, `deployment/worker.py` with a heartbeat).
  - Housekeeping: `manage.py fls_run_housekeeping` (`fls_run_housekeeping.py`, `deployment/housekeeping.py`). It runs once and exits, so it is intended for an external scheduler (cron or a container job). There is no in-process scheduler and no celery.
  - Existing task modules: `mail/tasks.py`, `comms/tasks.py`, and the `@task` `_dispatch_event_task` in `webhooks/events.py`.
- **Webhooks**: `fire_webhook_event(event_type, payload)` in `webhooks/events.py`.
  - It validates the type against the registry.
  - It silently returns when there is no request (`_thread_locals.request`), so it does nothing from management commands, shell or data migrations.
  - Otherwise it creates a `WebhookEvent` row and enqueues `_dispatch_event_task(event_id, site_id)`.
  - `dispatch_event` has no request context, so it filters endpoints explicitly by `site_id` and `is_active`, applies a circuit breaker, and writes a unique (event, endpoint) `WebhookDelivery` as an idempotency guard.
  - Event types are listed in `base/webhook_event_types.py`.
- **Notifications**: `comms/notify.py` raises a `Notification`.
  - Category and data are validated synchronously.
  - The row is written in `transaction.on_commit(..., robust=True)`.
  - One delivery task is enqueued per `NOTIFICATION_DELIVERY_BACKENDS` entry.
  - Categories are in `base/notification_categories.py`.
- **Signals**: `learner_progress/signals.py` handles `post_save` on `LearnerCourseRegistration` and `CohortCourseRegistration`, with `raw` guarded, and does its work with `transaction.on_commit` (a `course.registered` event is announced from there). Other signal hooks:
  - `allauth.account.signals.user_signed_up`, used in `referral_tracking/signals.py`.
  - A `post_save` on `Site` in `organisations/signals.py` that creates the default Organisation.
  - A `post_save` on `GeneratedReport`.
  - `post_delete` in `form_engine/receivers.py`.
- **Registration helpers** that rule evaluation would reuse: `learner_management/utils.py` `ensure_learner(user, organisation)` and `ensure_organisation_member`. They are idempotent and use `_base_manager` because the ambient site is not always the target's. `LearnerCourseRegistration` is a `SiteAwareModel`, so an auto-registration could use it, or `CohortCourseRegistration` if users are placed in a cohort.

Implications for rule evaluation:
- On-event evaluation (signup, or a profile change) can ride a signal plus `transaction.on_commit` plus a `django.tasks` task, as the progress, mail and notification code does.
- Batch re-evaluation (a rule changed) fits a management command run by cron, like `fls_run_housekeeping`, or a task.
- Any task must carry `site_id` and filter explicitly, because the `SiteAwareManager` needs a request.
- Registrations created by it would themselves trigger the `course.registered` webhook and progress signals.

## 5. `docs/app_structure.md` constraints

- The file is generated by `/app_map` and is "the source of truth for what cross-app imports are allowed". Per its header, any plan introducing a new cross-app edge "should be called out and approved before code is written".
- It contains `course_recommendations`, which has runtime deps on `accounts`, `content_engine` and `site_aware_models` only. It is imported by `learner_interface` and `qa_helpers`.
- The file does not force any new app to depend on `learner_management` and `accounts`, but registering a learner needs a `LearnerCourseRegistration` in `learner_management`, so a new app that creates registrations needs the edge new app to `learner_management`. Related facts:
  - `learner_management` depends on `accounts`, `base`, `content_engine`, `form_engine`, `organisations`, `role_based_permissions`, `site_aware_models`. It has no dependency on `course_access` or any recommendations app, so a new app depending on it creates no cycle.
  - `course_access` already depends on `learner_management` and `accounts`. `course_applications` depends on `course_access`, `learner_management`, `accounts`, `content_engine`, `form_engine`, `site_aware_models`. It is the existing model of an optional app that extends registration.
  - Because `learner_management` and `learner_progress` must not import a new optional app, the new app has to hook in through signals, a settings string resolved by `import_string`, or `apps.is_installed` guards. That is the pattern `content_engine` uses toward `course_access` (`COURSE_ACCESS_CONFIG_VALIDATOR`).
  - `learner_interface` is the only app that imports `course_recommendations`, `course_interest` and `course_access` at runtime.
  - An app that reads the user's organisation also needs `organisations` (already a dep of `learner_management`).
- A new app would gain edges at least to `accounts`, `learner_management`, `content_engine`, `site_aware_models` and `base`, plus `organisations` if rules are organisation-scoped. It would add a `declared_edges.toml` entry only if the dependency is not otherwise visible. The doc must be regenerated with `/app_map`.
- `base` already has a runtime dep on `learner_management` (an oddity), and `site_aware_models` is depended on by almost everything. A new app should not be imported by either.

## Open points for the spec (not decided here)
- Which level is "client" (deployment, Site or organisation).
- Whether the default is on or off.
- Whether the backend is a required setting (as with course access) or optional (as with notifications).
- Where rule data lives.
- Where the job or title attribute comes from.
- How a role or job title maps to a course: new rule model, or content frontmatter.

Sources: files named inline; all read from the working tree at the project root.

status: ok
