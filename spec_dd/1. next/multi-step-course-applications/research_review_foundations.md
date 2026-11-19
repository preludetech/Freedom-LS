# Research: foundations for "application review states and organisation-role reviewers"

Read-only research for the first child spec of `multi-step-course-applications`. Sources: the code under
`freedom_ls/` as of today, `multi-step-course-applications/idea.md`, and the older draft
`educator-interface-full-polish/application-review-ui/` (`idea.md`, `research_review_workflow.md`).
No web sources were used.

Short version:

- Today a `CourseApplication` has no state. "Submitted" is derived from the form sitting (`is_submitted`).
  Nothing approves an application, and nothing registers an applicant. Staff register people by hand.
- A course can be owned by organisations now (`Course.organisations`, `Course.shared_with`), so "a course
  is not owned by an organisation" in the idea is no longer true. That changes which organisation an
  application belongs to, and it makes "move to another organisation" a course-availability question too.
- Reviewers fit the `can()` capability system and a new organisation-level role. Guardian grants on
  applications, the staff fallback and the Django admin review phase from the draft are all stale.
- `audit_log` replaces the draft's `ApplicationStateTransition`. It needs new action codes and one
  glossary change, and it must not carry applicant-visible messages or applicant identity.
- No state machine library is installed. FLS keeps states as `TextChoices` plus service functions.
- This is three specs, not one. See section 9.

---

## 1. Today's `CourseApplication` lifecycle

### Models (`freedom_ls/course_applications/models.py`)

- `CourseApplication(SiteAwareModel)`: `user` (nullable), `anonymous_applicant` (nullable one-to-one),
  `course`, `form_progress` (nullable one-to-one to the form sitting, `RESTRICT`), `created_at`,
  `updated_at`. No state, no organisation, no reviewer, no decision fields.
- `AnonymousApplicant(SiteAwareModel, TimestampedModel)`: email, name, consent evidence, `user`,
  `claimed_at`, `claim_email_sent_at`, `claim_link_version`.
- The unique constraint `unique_application_per_site_user_course` is **unconditional**
  (migration `0006_unconditional_unique_application_per_site_user_course.py`). The class docstring's NOTE
  still says the review spec will swap it for an active-state partial index. That NOTE is stale: the
  claim code depends on "one application per account per course, however it began"
  (`claims.attach_to_user`, `queries.get_application_for_course`, which does `.first()`).
- Derived, not stored: `is_submitted` (no sitting, or `form_progress.completed_time` set),
  `submitted_time` (`created_at` when there is no sitting, else `completed_time`), `is_email_verified`
  (`user_id is not None`), `applicant_email`, `applicant_name`.

### Created

`views._start_application(course, user=…, anonymous_applicant=…)`: `get_or_create` inside
`transaction.atomic()`, then `select_for_update`, then create a `FormProgress` sitting when
`course.application_form` is set. Entry points:

- `views.apply` (signed in). A course with a form: any request, GET included, creates the application and
  its draft sitting, then redirects to the first form page. A course with no form: GET shows a
  confirmation page, POST creates the application, which counts as submitted on creation.
- `views._anonymous_apply` and `views.applicant_details` (a visitor). The details step creates an
  `AnonymousApplicant`, remembers it in the session, then `_start_application` runs.
- `record_conversion(kind=ConversionKind.COURSE_APPLICATION)` (referral tracking) runs when a signed-in
  application is created, and again in `claims.convert_attached_application` on a claim.

### Submitted

There is no submit transition. Submission is `application_check_answers` (POST) calling
`form_progress.complete()`, then `record_application_submitted(request, course)` (analytics, in
`course_access/analytics_events.py`). For a course with no form, creation is submission and
`record_application_submitted` runs in `apply`/`_anonymous_apply`.

After submission:

- Signed-in applicant: a success toast and a redirect to the dashboard.
- Anonymous applicant: a redirect to the status page, and the claim email is sent unless a live link
  already went out (`_send_claim_email_unless_live`).
- Form pages become read-only for the owner. For a visitor with no `user`, a submitted application's form
  pages 404 (`_owned_application_with_form`).

### Claimed (`claims.py`, `receivers.py`)

- `claim_application` view: GET confirms, POST claims (mail scanners fetch links, so GET changes nothing).
  `attach_claimed_application` finds or creates the `User` (`_create_claimed_user`, `_verify_address_by_claim`),
  writes `LegalConsent` rows, and calls `attach_to_user`.
- `attach_to_user` resolves a collision with an application the account already holds: **a submitted one
  beats a draft** (`held.is_submitted`), and between two drafts the incoming one wins. The loser is
  deleted with its sitting (`_discard_draft`) or erased with its applicant (`erase_anonymous_applicant`).
  This rule reads `is_submitted`, so it has to be rewritten in terms of state (or keep reading
  `is_submitted`) once states exist.
- `receivers.adopt_anonymous_applications_on_login` does the same for a sign-in whose verified address
  matches an applicant the session still holds.

### Shown to the applicant (status page)

`views.application_status` renders `course_applications/application_status.html`: a static "received,
pending review" page. A draft GET redirects back to the form (`_resume_url`). POST resends the claim
email. The docstring NOTE marks this as the seam: "dynamic state rendering (state badge, reviewer message,
withdraw action …) goes here". The same status URL is the "View my application" CTA
(`backends._gated_decision`) and the dashboard panel (`get_dashboard_contributions`,
`queries.get_active_applications`, whose docstring says it should narrow to active states later).

### API (`api.py`, scope `ApiScope.COURSE_APPLICATIONS`)

`CourseApplicationApiSerializer` has an explicit field tuple: `id`, `applicant_email`, `applicant_name`,
`is_email_verified`, `course_id`, `course_title`, `is_submitted`, `submitted_time`, `created_at`,
`updated_at`, `answers`. The comment says the properties are "read through the model so they follow when
application review adds a state". The viewset is read-only, uses `_base_manager` and the key's site, and
pages by `(updated_at, id)` with an `updated_since` filter (index `courseapp_site_updated_idx`).

What `state` changes here:

- Add `state` (and the organisation id, and decision time) to the field tuple. Update the OpenAPI schema
  and `test_api.py`.
- Every state change must move `updated_at`. A normal `save()` does it (`auto_now`). A bulk `update()`
  does not: `receivers.touch_application_updated_at` shows the pattern for those.
- `is_submitted` and `submitted_time` become stored or state-derived. Keep them in the API for
  compatibility.

### Webhooks

**None are fired for applications today.** `base/webhook_event_types.py` has no application event, and
`course_applications` never calls `fire_webhook_event`. The only webhooks near this flow are
`registration.added` and friends, fired from `LearnerCourseRegistration`'s `post_save` receiver in
`learner_progress` (`audit_log/README.md`, "Audit actions and webhook event types"). So approval that
registers a learner will fire `registration.added` for free, and `learner.added` only if it goes through
`add_learner` (see section 2). Whether `application.*` webhooks are wanted is a product call; the helper
`learner_management.utils.fire_webhook_event_on_commit` is the existing pattern, but it lives in the wrong
app for this use.

### Admin, export, erasure

- `admin.CourseApplicationAdmin` is read-only on purpose ("Nothing here writes": `has_add/change/delete_permission`
  all False). It filters on `CourseApplicationSubmittedFilter` (the `is_submitted` rule as SQL) and
  `EmailVerifiedFilter`. A state filter replaces the first. `resources.CourseApplicationResource` has
  `is_submitted` and `submitted_time` columns that need `state` beside them.
- `erasure.erase_anonymous_applicant` deletes the applicant, which cascades to the application, and
  `receivers.erase_the_sitting_nobody_owns` removes the user-less sitting. A claimed applicant is refused.
  Anything the review spec stores about an application must survive or vanish with the right owner: see
  section 4 on audit rows and `actor_label`.
- `qa_helpers/management/commands/qa_create_application_review_accounts.py` seeds an `is_staff` reviewer
  holding four plain `view_*` model permissions, to prove they open the admin pages read-only. That is
  the previous spec's QA scaffold and will be stale once reviewers are an organisation role.

### What a `state` field has to change, in short

| Place | Change |
| --- | --- |
| `models.py` | `state` (`TextChoices` + `CharField`), `organisation` FK, decision fields. Existing rows need a data migration: no-sitting or completed sitting -> `submitted`, open sitting -> `draft`. |
| `views._start_application`, `application_check_answers` | Call the submit service function where `complete()` runs, and for a no-form course at creation. Two sources of truth (`completed_time` and `state`) must not drift. |
| `claims.attach_to_user`, `receivers.adopt_…` | "Submitted beats draft" becomes a rule over states. Decide what a rejected or withdrawn held application does to an incoming one. |
| Unique constraint | See section 8: reapplying after reject or withdraw needs a decision. |
| `application_status` and template | State badge, decision text, withdraw. |
| `queries.get_active_applications`, dashboard panel, `backends._gated_decision` | Active-state narrowing, and a CTA for a closed application ("Apply again" or "View my application"). |
| `api.py`, `resources.py`, `admin.py` | Add `state`, organisation, decision time. |
| `receivers.py` | `updated_at` already moves via `save()`. Any bulk update needs the touch helper. |
| `erasure.py`, `receivers.erase_*` | Audit entries and anything else written about an anonymous applicant. |

---

## 2. `course_access`, the gate, and what "accepted" means today

- `course_access` defines the seam only. `application_gated` is **not** a core value: it lives in
  `course_applications/backends.py` as `APPLICATION_GATED = "application_gated"`, and `course_access`
  never imports `course_applications`.
- `ApplicationCourseAccessBackend.get_access` (`backends.py`): free course or registered learner ->
  inherited decision (content). Gated and unregistered -> "View my application" when an application
  exists, otherwise "Apply now". `can_self_register=False` always. `validate_course_config` accepts
  `access_type` and `application_form`.
- **There is no approval anywhere.** No state, no accept action, no link from an application to a
  registration. Gated courses stay discoverable; the gate is the CTA and `can_self_register=False`.
  Registration bypasses the gate by design ("admin/cohort enrolment deliberately bypasses the gate",
  `get_access` docstring). Today a staff member reads the application in the Django admin and then
  registers the person themselves in the educator interface.
- How a person gets registered (`freedom_ls/learner_management/`):
  - `utils.ensure_learner(user, organisation)`: get or create the `Learner` for `(user, organisation)`,
    reactivating a deactivated one. It writes **no** audit entry and fires **no** webhook.
  - `learner_actions.add_learner(organisation, entry, cohort, actor=…)`: matches or **creates** a `User` by
    email, calls `ensure_learner`, fires `learner.added` and writes the `learner.added` /
    `learner.reactivated` entry. If the account does not exist it creates one and emails a setup link.
  - `learner_actions.register_for_course(learner, course, actor=…, reason=…)`: creates or reactivates an
    individual `LearnerCourseRegistration` (`self_registered=False`), writes `registration.added` /
    `registration.reactivated` to the audit log, and the webhook comes from the `post_save` receiver.
    It calls `require_course_open_to(course, learner.organisation)` first and raises `CourseNotOpenError`.
  - `learner_actions.self_register`: the learner's own path. Not appropriate for approval: it sets
    `self_registered=True` and writes no entry for a new registration.
  - Cohorts: `CohortCourseRegistration` registers a whole cohort. **No cohort is needed** for an individual
    registration, and nothing in the idea asks for one.

### What automatic registration on approval needs

1. A `User`. An unclaimed `AnonymousApplicant` has none. Calling `add_learner` for it would create an
   account with no email proof, which the claim design exists to prevent. So approval of an unclaimed
   application has to wait for the claim, or reviewers can only decide on claimed applications. This is a
   real design decision, and it also decides the "applicant works for weeks" question in section 7.
2. The application's organisation. `ensure_learner(user, application.organisation)`.
3. The record: an individual `LearnerCourseRegistration` through `register_for_course(learner, course,
   actor=reviewer)`, inside the same `transaction.atomic()` as the state change. That path already writes
   the `registration.added` entry and fires the webhook. `learner.added` (entry plus webhook) is only
   written by `add_learner`, so the spec must pick: call `add_learner` for a user who exists (no account
   is created in that case), or call `ensure_learner` and write the entry itself. The first reuses more.
4. `course_open_to(organisation)`. If the application's organisation is not an owner of an organisation
   course, nor a `shared_with` organisation, `register_for_course` raises `CourseNotOpenError`. See
   section 3. Approval must either surface that as a refusal or prevent it earlier.
5. Idempotence. `register_for_course` returns False when an active registration already exists, so a
   second approval attempt or a staff member who registered the person first does not fail.
6. Later (spec 3): "approved, conditions outstanding" holds registration back until the registration-step
   requirements are accepted. The child spec should store the approval time and have registration be one
   function (`register_approved_applicant(application, actor)`) that spec 3 can call later.

The idea says approval registers the learner. The old draft says the opposite (approval is not enrolment,
hand-off by URL). That is a product reversal and should be stated plainly in the spec.

---

## 3. Organisations, roles and scoping

### Organisations (`freedom_ls/organisations`)

- `Organisation(SiteAwareModel, TimestampedModel)`, with `is_default` (one per site, enforced by the
  partial unique index `one_default_organisation_per_site`, created by a `Site` post_save receiver).
- `utils.get_default_organisation(site)` uses `_base_manager.get(site=site, is_default=True)` and raises
  `DoesNotExist` if the invariant is broken. `utils.organisation_of(target)` returns the target itself for
  an `Organisation`, `None` for a `Site`, otherwise `target.organisation` if the object has that
  attribute. **A `CourseApplication.organisation` FK would make `organisation_of` and `record_entry`
  work with no further code.**

### Is a course owned by an organisation today?

Yes, optionally. The done spec is `spec_dd/3. done/2026-10-27_20:02_organisation-courses/`, and the model
is in `freedom_ls/content_engine/models/courses.py`:

- `Course.organisations` (M2M, `related_name="courses"`): empty means "not an organisation course".
- `Course.shared_with` (M2M, `related_name="shared_courses"`): organisations an owner shared it with.
- `Course.audience` (`CourseAudience`, default `ORGANISATION_LEARNERS`), plus a `public` value.
- `learner_management/queries.py`: `is_organisation_course_expression`, `open_to_organisation_expression`,
  `available_to_organisation_expression`, `is_course_open_to_organisation`,
  `require_course_open_to`, `registerable_courses`, `courses_visible_to`.

So the idea's "a course is not owned by an organisation" is only true for a course whose `organisations`
set is empty (and `course_applications/queries.panel_rows` already prefetches `course__organisations`).
Consequences for the first spec:

- The application's organisation should not blindly be the site default. Candidate rule: the course's
  single owning organisation when there is exactly one; otherwise the default organisation. A course with
  several owners cannot be decided by code, so it takes the default and a reviewer moves it. This is a
  decision to confirm with the owner of the idea.
- A reviewer of organisation A cannot register an applicant into organisation B for a course B does not
  own or share. The same course-availability rule must limit the "move to another organisation" targets.

### Roles (`freedom_ls/role_based_permissions`)

- Roles are config (`roles.py` `BASE_ROLES`, loaded per site by `loader.get_role_config`): `site_admin`
  (scope site), `organisation_admin`, `organisation_staff_viewer`, `organisation_staff_roles_viewer`,
  `cohort_admin`, `cohort_viewer`, `learner`, `observer`, `system_admin` (scope system). Object roles are
  stored as `ObjectRoleAssignment` rows (user, content type, object id, role, `is_active`), site roles as
  `SiteRoleAssignment`.
- **Capabilities are checked by `learner_management.capabilities.can(user, capability, scope)`**, not by
  `user.has_perm`. It resolves superuser, then a site-level grant, then an organisation-level grant, then
  cohort grants. An organisation or cohort grant only counts if the user holds an **active `StaffMember`
  row** in that organisation (`_staff_organisations`). `can()` raises `TypeError` for a scope other than
  `Site`, `Organisation`, `Cohort`, `Learner`. So a reviewer check is `can(user, REVIEW_APPLICATIONS,
  application.organisation)`, or `can()` gains `CourseApplication` as a scope kind.
- Guardian object permissions are still synced from roles (`utils.sync_user_object_permissions`), but the
  educator interface does not rely on them. The draft's "assign `view_application` / `change_application`
  to reviewers on submit via guardian" is therefore the wrong model.

### Which role reviews applications

None existing fits cleanly:

- `organisation_admin` would work (it covers everything in the organisation) but it is too broad for
  someone who only reviews, and the idea says "several people can hold that role".
- `cohort_admin` / `cohort_viewer` are per cohort; applications have no cohort.
- So a **new organisation-level role**, for example `application_reviewer` (scope `SCOPE_OBJECT`, held on
  an `Organisation`), with a new Django permission on `CourseApplication` (for example
  `review_courseapplication` in `Meta.permissions`). `organisation_admin` and `site_admin` should list the
  same permission, so admins can review.
- Adding a staff role is not one line. It touches: `roles.py`; `role_based_permissions/registry.py`;
  `ObjectRoleAssignment.Meta.permissions` (a new `assign_application_reviewer`, plus a migration, like
  `role_based_permissions/migrations/0004_alter_objectroleassignment_options.py`);
  `learner_management/queries.STAFF_ROLES` and `ORGANISATION_ROLES` (a role missing from `STAFF_ROLES`
  "cannot be offered or shown" in the Staff UI, per the comment there); the staff table role display and
  filter in `educator_interface/staff.py`; and
  `educator_interface/tests/invariants/test_permission_matrix.py`.
- **A reviewer who holds only this role could not enter the educator interface.**
  `organisations_accessible_to` admits a user only through `view_organisation`, `view_organisation_staff`
  or a cohort role granting `view_cohort`. The new role either includes `view_organisation`, or
  `organisations_accessible_to` learns the new capability. The same goes for `OrganisationSectionConfig.is_visible`
  (a section with no `view_capability` needs `view_cohort`); the applications section sets its own
  `view_capability`.

### "Move an application to another organisation the person can access"

The existing scoping answers it directly:

- Targets: `organisations_accessible_to(user)` (superuser: all; otherwise organisations they may enter),
  narrowed to organisations where the reviewer **also** holds the review capability (`can(user, cap, org)`)
  and where `is_course_open_to_organisation(application.course, org)` is true. Otherwise the destination
  reviewers cannot see it, or the later registration raises `CourseNotOpenError`.
- The move is a plain `organisation` FK update plus one audit entry. It must be atomic with the state
  guard (a move after approval and registration would leave the `Learner` in the old organisation, so
  moving is refused once approved).
- The audit entry's `organisation` FK decides which organisation's Audit log shows it. A single entry
  (`organisation=destination`) leaves the source organisation's log blind to the move; see section 4.
- Inbox scoping: the educator URL is `organisations/<organisation_slug>/<path>`
  (`educator_interface/urls.py`), and `views.interface` resolves `request.organisation`. The inbox is
  therefore **per organisation**, which is exactly what the move needs. The draft's "global inbox across
  the site" is stale.

---

## 4. `freedom_ls/audit_log`

API (`audit_log/writer.py`, `audit_log/README.md`):

```python
record_entry(action="application.approved", actor=reviewer, target=application,
             target_label="...", organisation=application.organisation,
             subjects=[application.course], reason="...", details={...})
```

- `action` must be a registered `noun.verb` code; `ValueError` otherwise. `reason` is at most 500 chars.
  The site comes from the target. It opens no transaction; call inside the `atomic()` that changes state.
  Write only when state changed.
- `subjects` is an array of model keys with a GIN index. Anything listed shows on those objects' History
  tabs (`HistoryPanel` in `educator_interface`). An application as target gives an application History
  tab for free; the course as a subject gives a course History.
- Append-only, site-aware manager, `organisation` is `PROTECT`.

### Fit

| Event | Fit | Notes |
| --- | --- | --- |
| State transitions (approve, reject, pick up, withdraw, submit) | Good | Replaces `ApplicationStateTransition`. `from` and `to` go in `details`. |
| Move to another organisation | Good, with a gap | One entry, `organisation=destination`, source in `details` and `subjects`. The source organisation's Audit log filters on the `organisation` FK, so it does not show the move. Decide: write one entry per organisation, or accept it. |
| Requirement verdicts (spec 3 and 4) | Good | `requirement.accepted` / `requirement.rejected`, reason code in `details`, the reviewer's free text in `reason`. |
| Form reopen (spec 3) | Good | One entry per reopen; the idea asks for exactly this. |
| Applicant-visible message | **Poor** | Audit rows are staff-facing: anyone holding `view_auditlogentry` (organisation admins) reads them, and `details` must hold ids and labels only. An applicant message needs its own field on the application (or a requirement row). |
| Internal notes (draft `ApplicationNote`) | Poor | Not an event. The new idea does not ask for them. Drop or defer; a free-text note can ride on `reason`. |
| Applicant's own actions | Conflict | See below. |

### What it needs

- **New action codes.** `audit_log/tests/invariants/test_vocabulary.py` fails any noun or verb outside
  the glossary's "Changes" section. So `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` gains the
  noun `application` and verbs it does not have yet (`approved`, `rejected`, `withdrawn`, `submitted`,
  `picked_up` or similar; `moved` already exists), and `FLS_AUDIT_ACTIONS` plus `AUDIT_ACTION_GROUPS`
  gain an "Applications" group. `audit_log/README.md` gets table rows.
- **`organisation_of`** works once `CourseApplication.organisation` exists.
- **Privacy.** `actor_label` copies the actor's display name and "keeps the entry readable" after the user
  is deleted. An applicant erased under `erase_anonymous_applicant` or by deleting the user would leave
  their name in the entries about their own application. The README says the audit log "records staff
  actions only" (self-registration writes nothing). Follow that: audit reviewer and system actions; keep
  the applicant's own timestamps on the model (`submitted_at`, `withdrawn_at`), and do not put the
  applicant's name or email into `target_label` or `details` (use the course title and the application id).
- **Ordering.** The row must be written in the same `transaction.atomic()` as the state change, which a
  service function gives and `@transition` plus a later `save()` makes easy to get wrong.

Verdict: use `audit_log`. Do not build `ApplicationStateTransition`. Keep the applicant-visible message as
a field.

---

## 5. State machines, and how other FLS models do states

- `pyproject.toml` has `django-guardian>=3.3.0` and **no** `django-fsm`, `django-fsm-2`, `transitions` or
  `python-statemachine`. No `FSMField` anywhere in `freedom_ls/`. The draft's claim that "the subscriptions
  spec adopts django-fsm-2" is not something I could verify in code; there is no subscriptions app.
- Existing states are `models.TextChoices` plus a `CharField`, changed by functions:
  `api.models.ApiKeyStatus`, `panel_framework.models.RunStatus`, `learner_management.models.ImportStatus`,
  `mail.models.Status`, `registration_rules.models.Outcome`. Deadlines (`deadlines/models.py`) and the
  course pause use `is_active`-style rows and service functions in `deadlines/actions.py`, not a state
  machine. Audit action codes name the change.
- The project convention is a service function per change that opens `transaction.atomic()`, locks the row,
  checks the current state, writes it, writes the audit entry and fires the webhook on commit
  (`learner_actions.py`, `learner_management/utils.py`).

Recommendation: no new dependency. A `TextChoices` `state`, one table of allowed transitions, and one
service module (`course_applications/review.py` or `transitions.py`) in the house style. Reasons: the
draft's `protected=True` FSMField fights `get_or_create`, bulk updates and data migrations; an allowed-
transitions table is small; and `can()` is the permission check, which `@transition(permission=…)` would
only wrap.

---

## 6. Panel framework and the educator interface

What an inbox and a review screen are built from (`freedom_ls/panel_framework`,
`freedom_ls/educator_interface/views.py`, skills `fls-dev:panel-framework` and `fls-dev:educator-interface`):

**Applications inbox (list view)**

- A section config `ApplicationConfig(OrganisationSectionConfig, ListViewConfig)` (compare `CohortConfig`,
  `LearnerConfig`, `CourseConfig`, `StaffConfig`, `AuditLogConfig` in `views.py`), with `url_name`,
  `menu_label`, `icon`, `model = CourseApplication`, `list_view`, `table_key`, and its own `view_capability`.
- A `DataTable` / `DataTablePanel` subclass for the rows: applicant (`<c-panel-person-link>`, or the
  anonymous email), course (with the owning-organisation label helper on `Course`), `StatusBadge` for the
  state, submitted time, `search_fields`, `PeriodFilter` and a state filter from `filters.py`, a default
  order of oldest submitted first, and a quick view (`QuickView`) for the row.
- Queryset: a new `applications_visible_to(user, organisation)` beside `cohorts_visible_to` in
  `learner_management/queries.py`, or its own module. It must show only the request's organisation and
  only submitted applications (drafts are not the reviewers' business).
- Added to `interface_config` (a `NavGroup`, probably "Teaching" or a new "Applications" entry).
  Only the capability decides visibility; controls the user cannot use are hidden, and an application
  outside their scope returns 404 (the educator interface's access rule in the roadmap).

**Single-application review screen (instance view)**

- `ObjectViewConfig` with an `InstanceView` subclass: `panel` is a `TabSet` or `PanelStack`
  (Overview with `InstanceDetailsPanel`, Answers, History), `get_status_badge()` returns the state,
  `get_stats()` and `get_subtitle()` give submitted time and course.
- Decision actions are `PanelAction`s. Approve is a `ConfirmAction` that says what it does (registers the
  learner for the course in the organisation). Reject and Move use `ReasonMixin` with `reason_required`
  and `reason_choices` for the reason code. "Move" is a `FormPanelAction` with an organisation picker
  limited as in section 3. Each is hidden when the state does not allow it.
- Answers: `form_engine.admin.answers_context` is admin-only. The educator screen needs its own read-only
  answers panel. `form_engine.exports.answer_value` and `off_path_question_ids` (already used by
  `api.py`) are the reusable parts.
- History: `HistoryPanel` filters `AuditLogEntry.subjects`. An application as target or subject gets it
  with no new model.

**Code layout.** The `educator-interface-refactor` effort (see "Educator interface code layout" in
`spec_dd/1. next/roadmap.md`) is moving views into `panels/<area>/` packages, one per area, with `config.py`,
`data_tables.py`, `data_table_panels.py`, `panels.py`, `instance_view.py` (a file), `actions.py`,
`filters.py`, `quick_view.py`, tests under `tests/panels/<area>/`. Roadmap says to land it before specs that
add educator panels and otherwise rebase. `-1-scaffolding-and-common` is in progress; the rest are
blocked. The applications area should be written **directly in `panels/applications/`** and should
depend on `educator-interface-refactor-1-scaffolding-and-common`. `interface_config` stays in `views.py`
until `-7-cleanup`, so adding the section is a one-line edit that will collide mechanically.

Structure edges: `educator_interface -> course_applications` is new. The draft flagged it for the
structure review; `course_applications -> organisations`, `-> audit_log` and `-> learner_management`
(registration) are also new (`course_applications.backends` already imports `learner_management.utils`,
and `learner_management` does not import `course_applications`, so there is no cycle I can see).

---

## 7. Anonymous applicants coming back

- A visitor's access is **session only** (`anonymous_session.py`): the session holds
  `{course_id: applicant_pk}` under `course_applications_anonymous_applicants`. `owned_applications` lets
  the session reach an unverified application (`user__isnull=True`). The status page works from the
  session, so the applicant can see it again as long as the session lives. Production sets
  `SESSION_COOKIE_AGE = 1209600` (two weeks) in `config/settings_prod.py`.
- The **form pages stop working once an anonymous application is submitted**:
  `_owned_application_with_form` raises 404 for `user_id is None and is_submitted`, "the answers and files
  wait for whoever follows the claim link, not for the next person at the same computer".
- The **claim link** is the only way back across browsers or after the session ends. It is a signed token
  (`claims.claim_token`) valid for `claim_link_max_age()`, which is
  `allauth EMAIL_CONFIRMATION_EXPIRE_DAYS`. That setting is not set in `config/`, so it is allauth's
  default (3 days). After expiry the link shows an "expired" page and a POST sends a fresh one
  (`claim_application`), so recovery works but needs the mailbox.
- Signing in does not rescue an unclaimed application: `adopt_anonymous_applications_on_login` only reads
  applicants the **current session** remembers.
- `forget_all_anonymous_applicants` clears the session map on any login.

What this means for an applicant working on requirements over weeks:

- An anonymous applicant with a lost session and an expired link needs an email round-trip to get back in.
  Twelve days of document hunting is the stated use case, so the multi-step flow should **require the claim
  before requirements start** (that is, claim at or soon after submit, which creates the account and makes
  the application the user's). Requirements and uploads (specs 3 and 4) should only exist for a claimed
  applicant.
- It also resolves the registration-on-approval question: reviewers decide on a claimed application, or
  approval of an unclaimed one is held until the claim (a state or flag for that is extra scope).
- The first spec should not change claim behaviour. It should write down that "reviewable" means
  `state == submitted` and say what it does with an unclaimed submitted application: show it to
  reviewers read-only with an "address not confirmed" marker (`is_email_verified`), and refuse approve until
  `user` is set. That is a few lines in the state service, and it avoids creating accounts without email
  proof.

---

## 8. What is stale or contradicted in the old draft

Check each against the code and the new idea.

**Contradicted by today's code**

- "A form-less Apply flow ... `application-forms` hangs answers/files/config off `CourseApplication`":
  `application_form`, `form_progress`, check-your-answers, branching are all live. `submit` is not a free
  transition: it is `form_progress.complete()` in `application_check_answers`. The draft's `draft ->
  submitted` and the sitting's `completed_time` are two views of one fact. Pick one source (state stored,
  set where `complete()` runs) and keep `is_submitted` derived from state.
- "`CourseApplication.user` required, one per `(site, user, course)`": `user` is nullable and an
  `anonymous_applicant` can hold it. The draft's partial unique index (`unique_active_application_per_site_user_course`
  on `site, user, course` and active states) ignores unclaimed rows, which is fine because they have no
  user. But the unconditional constraint was made unconditional deliberately (`0006`), and `claims.attach_to_user`
  and `get_application_for_course` assume one application per account and course. Re-apply after reject
  or withdraw needs a decision (a partial index plus `get_application_for_course` preferring the active
  one, or reopen the same row). The draft's migration instruction ("drop the base constraint, add the
  partial index") is the wrong starting point.
- Applicant name and email: the draft's admin `applicant` column assumes a `User`; use `applicant_email`
  and `applicant_name`.
- Admin review: today's admin is read-only by design and has four filters tied to `is_submitted` and
  `is_email_verified`. The draft's phases 3 (Django admin inbox, `GuardedModelAdmin`, intermediate action
  pages, `django-fsm-admin`, inlines with `exclude = ["site"]`, "Enrol this learner" link) are **dropped**
  entirely. The educator interface is the one review surface, and it must not need `is_staff`.
- "Guardian grant on submit": guardian grants per application are the wrong mechanism now. Access is
  `can()` over roles plus an active `StaffMember` row, and the draft's cited `get_objects_for_user(…,
  "view_cohort", klass=Cohort)` at `educator_interface/views.py:84` no longer describes the scoping
  (`cohorts_visible_to`, `organisations_accessible_to` do).
- "Staff fallback (grant to site staff holding the reviewer role) with a TODO for per-course reviewer
  scoping": replaced by organisation role + `CourseApplication.organisation`. There is no course-to-
  reviewer mapping and none is needed.
- "Global applications inbox (site-wide)": the educator interface is organisation-scoped by URL. Inbox per
  organisation; superusers and site admins see every organisation through the switcher.
- `ApplicationStateTransition` and `ApplicationNote` models, `application_state_changed` signal: the audit
  log exists and replaces the first. The signal's purpose (a seam for email and integrators) is served by
  audit entries plus webhooks. Internal notes are not in the new idea.
- "`django-fsm-2` ... subscriptions spec adopts it": nothing in the repo uses it. See section 5.
- `apps.ready()` "does not import signals; this spec adds that": `ready()` already imports `receivers`.
- The base spec path `spec_dd/2. in progress/applying-for-courses` and its `# NOTE (review spec)` seam
  markers: the spec is finished; the markers are NOTE blocks in `models.py`, `views.apply` and
  `views.application_status` docstrings. Rewrite or remove them as part of the work (the project rule is
  to keep TODOs, but these are NOTEs that the work completes).
- "Approval is not enrolment; hand-off by URL": reversed by the idea (approval registers the learner via
  `ensure_learner`). Say so in the spec.

**Contradicted by the new idea**

- `changes_requested` / `request_changes` / `resubmit`: the idea says a turned-down requirement already
  carries "the applicant has more to do", so the application-level pair "may no longer be needed". With
  no requirements until spec 3, the first spec has nothing for the applicant to change, so **drop both**.
  States for the first spec: `draft`, `submitted`, `under_review` (optional), `approved`, `rejected`,
  `withdrawn`. Spec 3 adds "approved, conditions outstanding" (the idea's "approved, conditions outstanding
  or similar") and `superseded` lives on requirements, not applications.
- "One accept is enough" and "several can hold the role": consistent with the new role; no multi-reviewer
  assignment. `pick_up` (submitted -> under_review) is optional; no assignee is stored, so it is a flag
  for the queue. Decide whether to keep it. I lean to dropping it in v1 (nobody is assigned, and with
  several reviewers "under review" lies as soon as the first one wanders off).
- "`application-forms` depends on this spec for the FSM": reversed; forms landed first.
- The draft assumes reject and approve are terminal and re-application is somehow free. Decide the
  reapply rule (above) and what a rejected applicant sees.

**Still valid**

- The audit principle ("write only when state changed", atomic with the change), the "internal notes
  versus applicant message" split (only the message survives), state-driven buttons, oldest-first queue,
  no bulk decisions in v1, no email in v1.

---

## 9. Size, and where to split

One spec (one PR) for all of: states, reviewer role, organisation assignment and move, audit, applicant
status page, educator inbox and review screen, registration on approval. **It does not fit.** Rough counts
of what each piece costs:

| Piece | Work |
| --- | --- |
| States + organisation FK | Migration with a data migration for existing rows (state and default or sole-owner organisation), model and constraint decision, service module, status derivation in claims, queries, backend CTA, dashboard, admin filter, export, API fields and tests. |
| Audit | New glossary noun and verbs, `FLS_AUDIT_ACTIONS` entries and group, README rows, vocabulary test, entries in every service function. |
| Reviewer role | `roles.py`, registry, `ObjectRoleAssignment` permission and migration, `STAFF_ROLES` and staff UI, `organisations_accessible_to`, permission-matrix invariant, new `CourseApplication` permission, docs. |
| Applicant status page | Template per state, decision text, withdraw action (POST, 422 rules), claim-notice interplay. |
| Educator inbox + review screen | New area with table, filters, quick view, instance view, answers panel, four or five actions, History tab, nav entry, access tests, Playwright or QA scripts, structure-edge docs. |
| Move between organisations | Picker scoped by `organisations_accessible_to`, review capability and course availability, audit decision. |
| Registration on approval | `add_learner` or `ensure_learner` plus `register_for_course`, `CourseNotOpenError` handling, the unclaimed case. |

The educator inbox plus review screen alone is a full PR (compare the cohort or staff areas), and the
role plumbing is another.

### Proposed split by user-visible outcome

1. **`application-review-1-states-and-audit`** (data and applicant side). *"An applicant sees where their
   application stands, and can withdraw."*
   - `state`, `organisation` (default or sole owner), `submitted_at`, decision fields; data migration;
     reapply rule.
   - A service module with `submit`, `withdraw`, `approve`, `reject` as functions (reviewer ones callable
     but with no UI yet), each atomic, each writing the audit entry. Audit vocabulary and README.
   - Applicant status page states and withdraw; dashboard panel and CTA for closed applications;
     claim-attach rules over states.
   - API (`state`, `organisation_id`, decision time), export, admin read-only columns and a state filter.
   - No reviewer UI and no registration. Approving exists only through the service function (tested), so
     nobody can use it from a screen yet. Optionally a Django-admin-free management command is not
     needed.
2. **`application-review-2-reviewers-and-inbox`** (reviewer side). *"Reviewers see their organisation's
   applications and decide them."*
   - The `application_reviewer` role and everything it touches; `organisations_accessible_to`.
   - Inbox and review screen in `panels/applications/` (blocked by `educator-interface-refactor-1`),
     approve and reject with reason, History tab, move to another organisation, the unclaimed-applicant
     rule. Approve in this spec only changes the state.
3. **`application-review-3-approval-registers-learner`** (outcome). *"An approved applicant is registered
   for the course."*
   - Approve calls the registration function, with the `CourseNotOpenError` refusal in the dialog, the
     claim-held case, the `registration.added` and `learner.added` events, the status page text, and
     the idempotence rule. This is small (a service function, a dialog change, tests) and could fold into
     spec 2 if the unclaimed case is settled to "no approval before claim". I would keep it separate
     because registering a person is a data-affecting change, with its own QA, that is worth shipping and
     checking on its own, and because spec 3 of the parent idea (requirements) will rework it into
     "approved, conditions outstanding".

Spec 2 and 3 depend on 1; spec 2 also depends on the educator-interface refactor scaffolding. Spec 1
could land before the refactor does.

### Open decisions for the idea's owner (not resolved by code)

1. Which organisation a new application gets when the course has exactly one owner: the owner, or the
   default as the idea says.
2. Reapply after reject or withdraw: new row (partial unique index) or reopen the old one.
3. Approval of an unclaimed application: refuse until claimed, or hold.
4. `add_learner` (writes `learner.added`) or `ensure_learner` plus a hand-written entry.
5. Keep `under_review` / "pick up" or drop it.
6. `application.*` webhooks: wanted or not (none exist today).
7. Whether the applicant's own submit and withdraw are audited (the audit README says staff only; erasure
   leaves `actor_label` behind).
8. Whether the move entry shows in the source organisation's Audit log.

status: ok
