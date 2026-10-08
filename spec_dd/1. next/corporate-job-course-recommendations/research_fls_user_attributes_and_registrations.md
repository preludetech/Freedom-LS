# Research: user attributes and registration machinery in FLS today

Codebase-only research for `idea.md` (automatically register learners into courses by role, job
title and so on; switchable per client; other rule or recommendation backends may follow). Read
alongside `spec_dd/corporate-readiness/README.md` (phase 3 items 8 and 9, phase 4 item 12).
Vocabulary is the project's: `User`, `Learner`, `OrganisationMember`, `Cohort`, `CohortMembership`,
`LearnerCourseRegistration`, `CohortCourseRegistration`.

## Short answer

- Nowhere in FLS can a job title, department or role be stored per user today. `User` has only
  `email`, `first_name`, `last_name` and flags. `Learner` has only `user`, `organisation`,
  `is_active`, `created_at`. There is no profile model and no free-form attribute field on either.
- The corporate-readiness README (item 9) already says where they should live: per `Learner`
  (per organisation), arriving via SSO claims and SCIM. No spec has been cut for it.
- The machinery a rule engine would write into already exists and is solid: `ensure_learner`,
  `LearnerCourseRegistration` / `CohortCourseRegistration`, and `post_save` receivers in
  `learner_progress.signals` that mint the `CourseProgress` record and fire the
  `course.registered` webhook and notification. A rule only has to create ordinary registration rows.
- What is missing for a rule-created registration: no field says who or what made it
  (only the boolean `LearnerCourseRegistration.self_registered`), and `CohortCourseRegistration`
  has no such field at all.
- `course_recommendations.RecommendedCourse` is a real, shown-to-learners "recommendation", but it
  is a bare `(user, course)` row with no source. It is a good fit for the "recommend, do not
  register" half of the idea, and nothing in the code creates it today except the Django admin.

## 1. Where user-describing data lives today

### `accounts.User` (`freedom_ls/accounts/models.py`)
Fields: `email` (unique, the login identifier), `first_name`, `last_name`, `is_active`, `is_staff`,
`is_superuser`, plus `TimestampedModel` and the site from `SiteAwareModelBase`. Integer pk. No
JSON field, no profile fields. Properties `display_name`, `initials`, `username` are derived.
Site-aware: `UserManager.get_queryset` filters by the ambient request's site.

### `learner_management` (`freedom_ls/learner_management/models.py`)
- `Learner(SiteAwareModel)`: `user` FK, `organisation` FK, `is_active`, `created_at`. Unique on
  `(site, user, organisation)` (`unique_learner_per_organisation`). One user may hold several
  `Learner` rows, one per organisation. This is the natural home for per-organisation HR
  attributes (matches README item 9), but carries none today.
- `OrganisationMember(SiteAwareModel)`: `user`, `organisation`, `is_active`, `created_at`. The
  staff-side counterpart; gate for organisation and cohort role grants. Not a learner attribute.
- `Cohort(SiteAwareModel, TimestampedModel)`: `organisation`, `name`. No `is_active` yet (the
  educator-interface-6 spec adds it), no rule or source field.
- `CohortMembership(SiteAwareModel, TimestampedModel)`: `cohort`, `learner`; unique
  `(learner, cohort)`; `clean()` requires learner and cohort in the same organisation. No
  "added by" field.
- `ensure_learner(user, organisation)` in `freedom_ls/learner_management/utils.py` is the one
  idempotent way to get or create (and reactivate) a `Learner`.

### `organisations.Organisation` (`freedom_ls/organisations/models.py`)
`name`, `slug`, `logo`, `logo_on_dark`, `is_default` (one default per Site). No settings or JSON
field. So there is also nowhere today to hang a per-organisation "automatic registration on/off"
switch or rule configuration.

### Registration forms: `SiteSignupPolicy.additional_registration_forms`
- `SiteSignupPolicy(SiteAwareModel, TimestampedModel)` in `freedom_ls/accounts/models.py`:
  `allow_signups`, `require_name`, `require_terms_acceptance`, and
  `additional_registration_forms = JSONField(default=list)`. One row per site.
- Each list entry is a dotted path to a `django.forms.Form` subclass implementing
  `RegistrationFormProtocol` (`applies_to(user)`, `is_complete(user)`, `save(user)`), loaded by
  `load_registration_form_classes` and `get_incomplete_forms` in
  `freedom_ls/accounts/registration_forms.py`. Forbidden field names: `user`, `user_id`, `email`.
  Enforced by `freedom_ls/accounts/middleware.py` and the complete-registration view.
- Crucially, FLS does not store the answers. The project's own form class implements `save(user)`
  and decides where the data goes (its own model, or fields on a project model). The only fixtures
  are test classes in `freedom_ls/accounts/tests/_registration_form_fixtures.py`. So today a
  site could collect a job title at signup through this hook, but FLS provides nowhere to put it.
  This hook is the existing extension point for self-declared attributes.

### `form_engine` answers (`freedom_ls/form_engine/models.py`)
`FormProgress` (`form`, `user`, `start_time`, `completed_time`, `scores` JSON, ...) with
`QuestionAnswer` rows (`form_progress`, `question`, ...) and `QuestionAnswerFile`. This is where a
learner's answers to an ordinary `Form` live. A job-title question answered in a form is therefore
queryable, but only as `QuestionAnswer` rows keyed to a `FormQuestion`, with no semantic "this is
the user's job title" meaning. It is not user-describing data in a stable sense.

### Other JSON or extra-data fields
`JSONField` appears in models only for: `content_base.models` (`meta`), `form_engine.FormProgress.scores`,
`accounts.SiteSignupPolicy.additional_registration_forms`, `webhooks` (`event_types`, `payload`),
`comms.Notification.data`. None describes a user. There is no profile model in `freedom_ls`.

### Role-based permissions (not HR roles)
`role_based_permissions` (`ObjectRoleAssignment`, `can()`) holds access roles (`site_admin`,
`organisation_admin`, `cohort_admin`, `cohort_viewer`, after educator-interface-5). These are
permission roles, not job roles. The idea's "role" should be named carefully to avoid colliding
with them.

### So: can a job title or role be stored per user today?
No. Candidate homes, in the order the README implies: new fields (or a JSON attributes field) on
`Learner`; a downstream project's own model written by its `additional_registration_forms` form
`save(user)`; or `FormProgress`/`QuestionAnswer` rows (queryable but awkward).

## 2. Existing specs and ideas under `spec_dd/`

`spec_dd/1. next/roadmap.md` has no row for `corporate-job-course-recommendations`; the directory
holds only `idea.md` (one line pointing at `spec_dd/corporate-readiness/research_corporate_features.md`)
and is not yet registered, so `/sdd:roadmap` will need to add it.

Relevant plans, all unbuilt:
- `spec_dd/corporate-readiness/README.md` (recommendation, "not on the spec roadmap yet"):
  - Item 1 SSO (SAML/OIDC via allauth `socialaccount`, not installed): JIT provisioning calls
    `ensure_learner`.
  - Item 8 SCIM 2.0: deactivation maps to `Learner.is_active=False` and `User.is_active`; "SCIM
    groups could map onto cohorts".
  - Item 9 HR attributes on users: department, job title, location, employee ID, start date,
    manager, per `Learner`, standard fields plus organisation-defined custom fields.
  - Item 12 rule-based automatic registration: rule output should be ordinary
    `CohortCourseRegistration` or `LearnerCourseRegistration` rows; rules re-run when SCIM/SSO
    change attributes; "rule-maintained cohorts (dynamic cohorts) may be the cheapest way in".
  - Items 11 (recertification) and 13 (relative due dates) must agree with item 12.
- `spec_dd/1. next/user-profile-upgrades` (status `next`, depends on `phone-number-form-field`):
  profile page redesign plus phone number and date of birth, some required at signup. README says
  explicitly this is a different need from HR attributes. It will probably put fields on `User`
  or a profile; coordinate so there is not a second place for the same data.
- `spec_dd/1. next/phone-number-form-field`: form-engine field only.
- Educator interface rebuild (roadmap "Efforts"): `educator-interface-6-cohort-administration`
  (adds `Cohort.is_active`, cohort registration), `-7-learner-administration` (learner
  add/deactivate, cohort membership, individual registration; its open unknown is which webhook
  events fire for membership and cohort registration changes), `-8-bulk-operations` (CSV import),
  `-11-audit-log` (records every action in 6 to 9). A rule engine writes the same rows these
  specs administer, so it should reuse their account/registration paths and, if the audit log lands first, be
  attributable in it. Decision 1 there: "deactivate, never delete".
- `user-communication-2-notification-email` and the notification core: a rule-created registration
  will notify the learner (see section 4).
- Roadmap decision: deadlines are deliberately left alone; a rework follows.
- Nothing under `spec_dd/` plans dynamic cohorts as a spec. Nothing in `freedom_ls/` mentions SCIM, SAML,
  OIDC or `socialaccount`.

## 3. `freedom_ls/course_recommendations`

- Single model `RecommendedCourse(SiteAwareModel)` in `models.py`: `user` FK (related_name
  `recommended_courses`), `course` FK to `freedom_ls_content_engine.Course` (related_name
  `recommendations`), `created_at`; ordering `-created_at`. No uniqueness constraint, no source,
  rank, reason or expiry. The module docstring says "Deliberately minimal ... Keep this model
  standalone and additive."
- The `form_progress` FK is commented out ("drafted below but not yet live"). The class docstring
  ("Created when a parent fills out a form") is stale; nothing creates rows from a form.
- Who creates it: no production code. Only the Django admin (`RecommendedCourseAdmin`), the
  `RecommendedCourseFactory`, and QA helpers. `qa_extend_start_here_section` asserts counts.
- Who deletes it: `learner_interface.views` (the self-registration view, around line 912) runs
  `RecommendedCourse.objects.filter(user=request.user, course=course).delete()` after registering.
  Registration through any other path (admin, cohort) does not clear it.
- Where shown: `get_recommended_courses(user)` in `queries.py` is called from
  `learner_interface/views.py` (lines ~185-195, `_annotate_recommendations`, the dashboard). It
  renders as the "Recommended courses" dashboard section (`dashboard_sections.py`, section key
  `recommended`; `"recommended"` is a reserved course-category slug in `content_engine/schema.py`).
  Paginated, newest first, ties broken by course slug; "Available" excludes recommended courses.
- Verdict: this is the existing recommendation concept and the idea should reuse it for the
  "recommend rather than enrol" outcome (README: "other enrolment rules / recommendation rules
  backends"). The idea says "recommendation rules", which maps cleanly. Gaps to fill if reused:
  a source/reason field (rule id or backend name) so a rule can retract only its own rows, a
  unique constraint on `(user, course)` for idempotent evaluation, and clearing on any
  registration path, not only self-registration. It is keyed on `User`, not `Learner`, so it is
  not organisation-scoped, unlike the registration models.

## 4. Course registrations: creation, ending, hooks

### Models (`freedom_ls/learner_management/models.py`)
- `LearnerCourseRegistration(SiteAwareModel)`: `course` (PROTECT, related_name
  `learner_registrations`), `learner`, `is_active`, `self_registered` (bool, default False,
  "learner registered themselves rather than being registered by staff"), `registered_at`. Unique
  `(site, learner, course)` (`unique_learner_course_registration`).
- `CohortCourseRegistration(SiteAwareModel)`: `course` (PROTECT, `cohort_registrations`),
  `cohort` (CASCADE, `course_registrations`), `is_active`, `registered_at`. Unique `(site, course,
  cohort)`. No `self_registered`, no source field.
- Deadlines hang off these (`CohortDeadline`, `LearnerDeadline`, `LearnerCohortDeadlineOverride`),
  absolute datetimes only.
- "Ending" is `is_active=False` (no hard delete in normal use; `CourseProgress` PROTECTs the
  registration that minted it). There is no `ended_at` or reason field.

### Every non-test code path that creates a registration
1. Self-service: `learner_interface.views` (around lines 884-912) after the `COURSE_ACCESS_BACKEND`
   gate (`get_course_access_backend().get_access(...).can_self_register`): `ensure_learner(user,
   get_default_organisation(site))` then `LearnerCourseRegistration.objects.update_or_create(...,
   defaults={"is_active": True}, create_defaults={"is_active": True, "self_registered": True})`.
   Note that the comment records the deliberate rule that `self_registered` is set only on create so
   reactivation does not change who made it. Then `record_course_self_registered` analytics.
2. Django admin: `LearnerCourseRegistrationAdmin` (`self_registered` and `registered_at` are
   read-only), `CohortCourseRegistrationAdmin`, and `CohortCourseRegistrationInline` on the cohort
   admin, with `LearnerCourseRegistrationAdminForm` / `CohortCourseRegistrationAdminForm` in `forms.py`.
3. Educator interface: only reads today (`educator_interface/views.py` data tables). Creation
   arrives with educator-interface-6 and -7.
4. Applications: `course_applications` does not create registrations in its source (only its tests
   build them with `LearnerCourseRegistrationFactory`). Its access backend routes applicants to an
   apply page (`can_self_register=False`); approval-to-registration is part of the unbuilt review
   workflow. So no registration is created by application approval yet.
5. Management and QA commands: `dev_tools ... create_demo_data` (cohort membership and
   registrations), many `qa_helpers` commands via factories.
6. Signals do not create registrations; they react to them.

`CohortMembership` creation: admin inline and `create_demo_data` only. `ensure_organisation_member`
is created by a `post_save` receiver on `ObjectRoleAssignment`
(`learner_management/signals.py`).

### Signals and hooks that fire on registration (`freedom_ls/learner_progress/signals.py`)
All are `post_save` receivers, deferred with `transaction.on_commit`, and skip `raw` (loaddata):
- `ensure_course_progress_on_learner_registration` (sender `LearnerCourseRegistration`): if
  `is_active`, runs `_ensure_and_announce(instance, announce=created)`: mints the course progress
  record via `ensure_course_progress_record`, then, only on creation, (a) calls
  `comms.notify.raise_notification(user, category="course.registered", ...)` unless
  `registration.self_registered`, and (b) `webhooks.events.fire_webhook_event("course.registered",
  {user_id, user_email, course_id, course_title, registered_at, organisation_id, course_progress_id})`.
- `ensure_course_progress_on_cohort_registration` (sender `CohortCourseRegistration`): fans out
  `ensure_course_progress_records_for_cohort_registration` to a record per active member. It
  raises no notification and fires no webhook (the roadmap lists this as an open unknown owned by
  educator-interface-7).
- `ensure_course_progress_on_cohort_membership` (sender `CohortMembership`): catches a new member up
  on every active cohort registration (`_ensure_for_membership`), again with no announce.
- Deadlines are not applied by a signal; `learner_management/deadline_utils.py` computes them from
  existing deadline rows. There is no hook that creates a deadline on registration (this is the
  gap README item 13 describes).
- Other hooks: `access` is checked by `is_registered_for_course` in `learner_management/utils.py`
  (direct registration or cohort registration, with `learner__is_active` and `is_active` all true),
  which `course_access.backends` call.

Implication: a rule that writes a `LearnerCourseRegistration` with `self_registered=False` gets,
for free, the progress record, a `course.registered` notification to the learner ("someone else
registered you") and a webhook. A rule that creates a `CohortCourseRegistration` gets progress
records for members but no announcement.

### What would distinguish a rule-created registration from a manual one?
Today nothing does. `self_registered=False` means "registered by staff" and a rule-created row
would be indistinguishable from an admin-created one; it would also notify the learner as if staff
had acted. Options, all new schema:
- A nullable source field on both registration models (a short backend/rule identifier, or a FK to
  a rule model) so a rule can find, reconcile and retract only its own registrations and never
  touch manual ones or reactivate ones staff deactivated.
- A deactivation-by-staff marker, or a rule must not reactivate `is_active=False` rows, otherwise
  the rule re-enrols someone staff removed (compare the explicit `update_or_create` comment in the
  self-registration view).
- A decision on whether `self_registered` stays a bool or becomes a source/choices field; the
  README's `course.registered` webhook payload has no source field today either.
Existing code would then need updating where `self_registered` is read: `learner_progress/signals.py`
(notification gate) and the `LearnerCourseRegistrationAdmin` fields.

### Existing swap and switch patterns to copy
- Swappable backend: `COURSE_ACCESS_BACKEND` resolved by `course_access.loader` with `import_string`,
  base class `CourseAccessBackend` (`course_access/backends.py`), validated by `course_access/checks.py`
  (system checks E003). Same shape as the planned `MessagingPolicy` in user-communication-3. This is the
  obvious precedent for "other rule/recommendation backends may follow".
- Per-app config: `learner_management/config.py` uses `AppSettings`/`Setting` from
  `freedom_ls/base/app_settings.py` (for example `DEADLINES_ACTIVE`). `NOTIFICATIONS_ENABLED` is the
  "ship dark" precedent. These are project-wide Django settings, not per-client database rows. A
  per-client switch could therefore be a Django setting (one deployment per client), a per-`Site`
  row (like `SiteSignupPolicy`, which is per-site with a JSON hook list) or a per-`Organisation`
  setting; `Organisation` has no settings field today. This is the main open design decision.
- Ordered, site-configured hook list: `SiteSignupPolicy.additional_registration_forms` with strict
  loading that raises `ImproperlyConfigured` rather than skipping silently is the precedent for
  loading rule backends from configuration.

## 5. Dynamic cohorts

Fit is good, with caveats.
- A `CohortCourseRegistration` already registers a whole `Cohort`, and
  `ensure_course_progress_on_cohort_membership` already catches a new `CohortMembership` up on every
  active cohort registration. So a rule that only maintains `CohortMembership` (add learners who
  match, remove ones who stop matching) would drive registration with no change to registration
  code or signals. "Everyone with job title Driver gets Road Safety" becomes a cohort "Drivers",
  a `CohortCourseRegistration` for Road Safety, and a rule that fills the cohort.
- What a dynamic cohort needs that does not exist: a flag or rule link on `Cohort` marking it as
  rule-maintained (and blocking manual membership edits or at least marking them), a source on
  `CohortMembership` so the rule removes only memberships it added, and an evaluation trigger
  (on attribute change, on `Learner` create, and a sweep alongside `fls_run_housekeeping`, the
  pattern the README names).
- Constraints: `CohortMembership.clean()` and `Cohort` are single-organisation, so a dynamic cohort
  is per organisation, consistent with attributes living on `Learner`. `Cohort` currently has no
  `is_active`; educator-interface-6 adds it and a delete-only-when-empty rule, which a dynamic
  cohort must respect.
- Costs and risks: cohort membership also drives reports (cohort report), role grants scoped to a
  cohort (`ObjectRoleAssignment` on a `Cohort` target), messaging policy at cohort level, and
  cohort-level deadlines. A rule-maintained cohort therefore changes who an educator, a report or
  a deadline sees. Removing a membership does not retire existing progress (the signals module says
  there is deliberately no post_delete counterpart), so a learner who stops matching keeps their
  record and their registration unless the rule also deactivates the registration.
- `CohortCourseRegistration` is cohort-wide with no per-course relative deadline, so "due 30 days
  after joining" (README item 13) is not available; deadlines remain absolute.
- Alternative to dynamic cohorts: rules that write `LearnerCourseRegistration` directly give
  per-learner granularity, per-learner `self_registered`-style provenance, and the existing
  `course.registered` announcement, at the price of one row per learner per course.

## Open questions this research surfaces for the idea

1. Where do attributes live (`Learner` fields, a `Learner` JSON field, or a downstream-owned model
   fed by `additional_registration_forms`)? Without this nothing can be matched. The README claims
   `Learner`, per organisation, with SSO/SCIM as sources, but neither exists, so a first version
   needs a manual or CSV entry path (educator-interface-8 CSV import is the nearest).
2. Where does the per-client on/off switch live (Django setting, per-`Site` row, per-`Organisation`)?
3. Rule output: direct registrations, cohort membership (dynamic cohorts), or `RecommendedCourse`?
   The idea names both enrol and recommend, which suggests a backend interface with more than one
   output type.
4. Provenance field on `LearnerCourseRegistration`, `CohortCourseRegistration` (and
   `CohortMembership` if dynamic cohorts): needed to reconcile and retract safely.
5. Should a rule-created registration notify the learner, and should it count as
   `self_registered=False`? The current signal logic notifies.
6. What happens when a person stops matching: leave the registration, deactivate it (progress is
   kept either way), or retract only a `RecommendedCourse`.
7. Coordination with `user-profile-upgrades`, `educator-interface-6/7/8/11` and the
   unwritten SCIM/SSO items so attributes, audit logging and registration paths are not built twice.

status: ok
