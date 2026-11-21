# Research: codebase touch points for `multi-step-course-applications-1-review-states`

Read-only. Paths are under `freedom_ls/` unless stated. Reading order: what the work touches (1-9), what it
reuses (10-13), then conflicts and risks (14). Section 15 lists tests to extend.

## 1. `course_applications/models.py`

- `CourseApplication(SiteAwareModel)`: `user` (nullable FK, CASCADE), `anonymous_applicant`
  (nullable OneToOne to `AnonymousApplicant`, CASCADE), `course` FK (CASCADE, `related_name="applications"`),
  `form_progress` (nullable OneToOne to `FormProgress`, `RESTRICT`), `created_at`, `updated_at`
  (`auto_now`). No `state`, no `organisation`, no decision fields.
- `Meta.constraints`: `UniqueConstraint(fields=["site","user","course"], name="unique_application_per_site_user_course")`,
  unconditional (migration `0006_unconditional_unique_application_per_site_user_course.py` removed and re-added it,
  so the migration state holds the plain constraint). Rows with `user` NULL never collide (Postgres NULLs are distinct).
  `Meta.indexes`: `courseapp_site_updated_idx` on `(site, updated_at, id)` (migration `0008`). Latest migration is
  `0008`; the new ones start at `0009`.
- Derived today, not stored: `is_submitted` (`form_progress is None or form_progress.completed_time is not None`),
  `submitted_time` (`created_at` when there is no sitting, else `completed_time`), `is_email_verified`
  (`user_id is not None`), `unverified_applicant`, `applicant_email`, `applicant_name`. These properties read
  `form_progress`, so every caller `select_related("form_progress")` (see `queries.py`, `views._status_applications`,
  `admin.list_select_related`, `api.get_queryset`, `resources.filter_export`).
- `__str__` returns ids only (no email), on purpose: the admin logs it on delete. Keep this; it is also what
  `record_entry` labels should imitate (course title + application id, never applicant identity).
- NOTE blocks to rewrite (spec says rewrite, not delete as TODOs; they are NOTEs, the work completes them):
  1. `models.py` class docstring: "when application review lands, this model gains `state = FSMField(protected=True)`,
     the submit/withdraw/pick_up/request_changes/resubmit/approve/reject transitions, submitted_at/decided_at/decided_by,
     the view_application/change_application permissions, ApplicationNote + ApplicationStateTransition, the
     application_state_changed signal, and the active-state PARTIAL unique index". Most of that is now explicitly not
     planned (FSM, `pick_up`, `request_changes`, `resubmit`, notes, transition table, signal, guardian permissions).
     The module docstring ("Deliberately minimal and standalone... Application review will later add a state machine...")
     is stale for the same reason.
  2. `views.apply` docstring: "NOTE: when application review lands, the POST body will wrap get_or_create in an atomic
     block and call app.submit() (the FSM transition) + create an ApplicationStateTransition audit row."
  3. `views.application_status` docstring: "NOTE: ... dynamic state rendering (state badge, reviewer message, withdraw
     action via get_available_user_state_transitions) goes here."
  4. Template comment block in `templates/course_applications/application_status.html` (`{% comment %} NOTE: when
     application review lands ... {% endcomment %}`), also a NOTE for the same seam.
  5. `queries.get_active_applications` docstring: "With no terminal states yet, this returns all ... narrows to active
     states once withdraw/approve/reject exist."
  6. `api.py` comment on `CourseApplicationApiSerializer` ("read through the model so they follow when application
     review adds a state") and `admin.CourseApplicationSubmittedFilter` docstring.
  7. `migrations/0006` is not edited (never edit existing migrations).

## 2. `views.py`

- `_start_application(course, *, user, anonymous_applicant)`: `transaction.atomic()`, then
  `CourseApplication.objects.get_or_create(course=course, **({"user": user} or {"anonymous_applicant": ...}))`,
  then `select_for_update().get(pk=app.pk)`, then creates a `FormProgress` when `course.application_form` is set and
  `app.form_progress is None`. **Risk:** once a user can hold several applications per (user, course) (one closed, one
  active), `get_or_create(course=, user=)` raises `MultipleObjectsReturned`. The lookup must add the active-state
  filter (the `get_or_create` lookup and the `defaults` for `state`/`organisation`). The race-safety relies on the
  unique constraint; the partial index (active states only) is what makes `get_or_create`'s IntegrityError fallback
  still converge on one active row, but the retry `get` also needs the active filter.
  For a course with no form, creation must set `state=submitted` (and a submit time); with a form, `draft`. A course
  gaining a form after creation is handled at lines ~471-477 (`_anonymous_apply`).
- `apply(request, course_slug)`: signed-in path: `existing_app = get_application_for_course(user, course)`; if there
  is one it redirects to `course_applications:status` ("An existing applicant always reaches their application
  record" precedes `_coming_soon_redirect`). **Conflict:** a closed (rejected/withdrawn/approved) application is also
  "existing", so the "apply again" path must let the request fall through to `_start_application`, and the
  coming-soon redirect then applies to it. Anonymous path `_anonymous_apply`: `application_of(applicant)` is a OneToOne,
  see risk in section 14.
- `application_status(request, pk)`: `_owned_application` over `_status_applications(request)`
  (`owned_applications(request).select_related("course","form_progress","anonymous_applicant")`). Behaviour today:
  POST (unverified only for the claim email resend, including `HX-Request` returning the claim notice); GET of a draft
  (`form_progress` set and `completed_time is None`) redirects to `_resume_url`; otherwise `_render_status`. The
  withdraw POST must be distinguished from the existing resend POST: the status URL already takes POST for the claim
  email resend (`_unverified_applicant_of(app)` 404s for a verified application). Options: a new URL (like
  `change_applicant_email` at `status/<uuid:pk>/change-email/`, a `@require_POST` view with the same
  `_owned_application(..., next_url=status_url)` pattern, and the same 422-on-HTMX-error convention), or a hidden
  field on the same URL. The existing house precedent is a separate `@require_POST` URL (`change_applicant_email`).
  Add `status/<uuid:pk>/withdraw/` to `urls.py` (`app_name = "course_applications"`, snake_case name).
  The draft redirect must key off `state == draft` (a withdrawn draft has `completed_time is None` and still must
  render, not redirect to the form). Likewise `_owned_application_with_form` (form pages 404/allow rules use
  `app.is_submitted`) and `application_form_page` (`read_only = form_progress.completed_time is not None`) need to
  consider state: a withdrawn or rejected draft must not accept more writes.
- `application_check_answers`: the single `form_progress.complete()` call (line ~848) followed by
  `record_application_submitted(request, app.course)`, then branch on `app.is_email_verified` (verified: success toast
  "Your application for ... has been submitted and is pending review." and redirect to dashboard; anonymous: send claim
  email unless live, redirect to status). The submit service call belongs here, inside one `transaction.atomic()` with
  `complete()` (`complete()` itself opens `transaction.atomic()` and then sends `form_attempt_completed` after its
  block; `FormProgress.save()` fires the `touch_application_on_sitting_save` bulk-update receiver). The toast copy says
  "pending review" and is asserted in `tests/test_views.py` (line ~1045). `submitted = form_progress.completed_time is not None`
  drives the template and the `elif request.method == "POST": redirect(status)` guard: this must be consistent with state
  (a withdrawn application whose sitting is open must not be submittable; its check-answers URL must refuse).
- `apply` for no-form courses: creation is submission; `record_application_submitted(request, course)` runs in
  `apply` and `_anonymous_apply`. The `submit` service function must run in `_start_application` when there is no form.
- `claim_application` view computes `held_application` = `"" | "submitted" | "draft"` from `held.is_submitted`
  (line ~968) and `is_submitted` from `application.is_submitted` and passes them to `claim.html`; both need state
  semantics (a held rejected/withdrawn application should read as "none held").
- `applicant_details` redirects to status when `app is not None and app.is_submitted` (line ~593).
- `emails.send_application_claim_email(..., is_submitted: bool)`: callers pass `app.is_submitted`; template wording
  follows. These keep working if `is_submitted` stays a derived property of `state`.

## 3. `queries.py`

- `get_application_for_course(*, user, course)`: `CourseApplication.objects.filter(user=user, course=course).select_related("form_progress").first()`.
  Used by `backends.get_access` (CTA), `views.apply`, `views.claim_application`. Needs to prefer an active
  application, else the most recent closed one (CTA for a closed application, "apply again" path). `.first()` with no
  ordering today; with several rows it needs an explicit order (active first, then `-created_at`).
- `panel_rows(applications)`: `select_related("course","form_progress").prefetch_related("course__organisations").order_by("-created_at","pk")`;
  also used for the anonymous session branch of the dashboard (`backends.get_dashboard_contributions_for_request`
  filters `form_progress__isnull=False, form_progress__completed_time__isnull=True`, i.e. a derived draft: switch to
  `state=draft`).
- `get_active_applications(user)`: today all of the user's applications. Idea narrows to active; answers.md says the
  dashboard panel **keeps closed (rejected and approved) applications visible too**, so the panel needs a
  distinct selection ("active, plus rejected and approved"; withdrawn hidden), and the name `get_active_applications`
  no longer describes it. Paging: `APPLICATIONS_PAGE_SIZE = 3`, `APPLICATIONS_SWAP_ID`, `Paginator`/`clamped_page`.
  A rejected application's message must be on the row (the panel template reads `app.is_submitted` for the chip
  "Pending review"/"Incomplete", the copy "Finish your application to have it reviewed.", and the button "View my
  application"/"Continue application"). Ordering is `-created_at` newest first, so a re-application sorts above the
  closed one.
- Docstring: `learner_interface` must not import from `queries.py`; it reaches the panel through
  `backend.get_dashboard_contributions()`.

## 4. `backends.py` (course CTA and dashboard)

- `ApplicationCourseAccessBackend._gated_decision(*, course, application)`: application present → label
  `"View my application"` with `course_applications:status`; none → `"Apply now"` with `course_applications:apply`.
  The closed-application case needs a third branch: an "apply again" CTA (`course_applications:apply` URL), with
  state-appropriate copy. `acquisition_heading`/`acquisition_subtext` ("Application required" / "Apply and we'll review
  your request.") are shared. `get_access_for_request` for anonymous sessions uses `application_of(applicant)`.
  `learner_interface` tests assert "View my application" (`learner_interface/tests/views/test_course_detail.py` lines
  ~208, ~225); `tests/test_backends.py` asserts the label at lines ~298, ~368, ~486, ~497, ~720, ~752, and the panel
  rendering ("Pending review"/"Incomplete" at ~460-477, ~1010); a Playwright test asserts
  `get_by_text("Pending review")` and `View my application` hidden (`tests/playwright/test_application_form_flow.py`
  lines ~120, ~469).
- `is_accessible_for_free`, `get_access_badge`, `get_access_type` are config-only; unaffected.

## 5. `claims.py` and `receivers.py`

- `attach_to_user(application, applicant, user)`: locks the `User` row (`User._base_manager.filter(pk=user.pk).select_for_update()`),
  then `held = CourseApplication.objects.select_for_update(of=("self",)).select_related("form_progress").filter(user=user, course_id=application.course_id).exclude(pk=application.pk).first()`.
  If `held.is_submitted`: `erase_anonymous_applicant(applicant)` and return `AttachResult(held, discarded_draft=False)`
  ("submitted beats draft"). Otherwise `_discard_draft(held)` (deletes the held application and its sitting, discards
  its conversion via `discard_conversions_for`), then sets `application.user`, saves with
  `update_fields=["user","updated_at"]`, repoints the sitting's user, marks the applicant claimed. Docstring:
  "An account holds one application per course".
  To rewrite over states: `held` must be the account's **active** application only (a closed one does not collide
  under the partial index, so the incoming one attaches beside it). `held.is_submitted` → `held.state == submitted`
  (or "not draft"), covering `approved`, which is not an active-pending state but also should win. Decide: if the
  incoming application is itself closed (an anonymous applicant who withdrew before claiming) and the account holds an
  active one, the incoming one should lose and be erased, like a draft loses to a submission (the idea leaves this
  open: "Whether an application that becomes active again needs any claim-time rule beyond preferring the active one
  when two applications collide").
  The partial unique index check happens on the `application.save(update_fields=["user", ...])`, so any held active
  application left in place makes this raise `IntegrityError` (the surrounding code in `attach_claimed_application`
  catches `IntegrityError` only around `_user_for_claim`, not around `attach_to_user`).
- `_discard_draft(draft)` deletes with `discard_conversions_for(draft)`; **a rejected/withdrawn held application
  carries a conversion too** (`record_conversion` is keyed by `(site, kind, content_type, object_id)` per application
  target, `referral_tracking/conversions.py`). A re-application records a new conversion (`record_conversion` in
  `views.apply` when `created`), so the same user gets one conversion per application attempt; this changes
  attribution counts. Note for the spec: decide whether a re-apply should count as a second `COURSE_APPLICATION`
  conversion (it will by default).
- `receivers.adopt_anonymous_applications_on_login`: calls `attach_to_user`, uses `result.application.is_submitted` to
  pick the toast verb ("submitted"/"started") and `result.application.pk != application.pk` for the "kept" message.
  Tests: `tests/test_receivers.py` lines ~131-254, ~377.
- `receivers.touch_application_updated_at(**match)` is the touch helper for bulk updates: `CourseApplication._base_manager.filter(**match).update(updated_at=timezone.now())`,
  with a `match` of keyword lookups (e.g. `form_progress_id=...`, `anonymous_applicant_id=...`, `user_id=...`). Used by
  receivers on `FormProgress`, `QuestionAnswer`, `QuestionAnswerFile`, `AnonymousApplicant`, `User` saves. A state
  change through the service function uses a locked-row `save(update_fields=[..., "updated_at"])` (`auto_now` only
  applies when `updated_at` is in `update_fields`, which is why `attach_to_user` lists it explicitly); a bulk
  `update()` (the data migration, or any queryset-level state flip) uses `touch_application_updated_at`. The data
  migration cannot import it (migrations must not import app code), so it must set `updated_at` itself, or deliberately
  leave it (decide whether a backfill should appear in the `updated_since` API feed; the registration migration
  `learner_management/migrations/0011_registration_updated_at.py` backfilled `updated_at` from `registered_at`).
- `erasure.erase_anonymous_applicant` just deletes the applicant (cascades the application); `receivers.erase_the_sitting_nobody_owns`
  removes a user-less sitting on application `post_delete`. Unaffected by state, but audit entries for an application
  of an erased applicant keep target ids/labels (no PII, per the idea).

## 6. API (`api.py`), export (`resources.py`), admin (`admin.py`)

- `CourseApplicationApiSerializer`: explicit `fields` tuple, `read_only_fields = fields`:
  `id, applicant_email, applicant_name, is_email_verified, course_id, course_title, is_submitted, submitted_time,
  created_at, updated_at, answers`. Add `state`, the organisation id (`organisation_id` as `UUIDField(read_only=True)`,
  like `course_id`), and the decision time field (name open). `is_submitted`/`submitted_time` declared as
  `BooleanField`/`DateTimeField(read_only=True, allow_null=True)`: keep as derived properties of state (spec decision)
  or stored fields. OpenAPI: `extend_schema_field`; a `state` field from a `TextChoices` model field picks up choices
  automatically in `ModelSerializer`. `get_queryset` uses `_base_manager.select_related("user","anonymous_applicant","course","form_progress__form")`:
  `organisation_id` needs no extra join. Tests: `tests/test_api.py` has an expected-field list at lines ~60-75 and the
  draft/submitted tests at ~162-181; `docs/api.md` documents the scope and fields (grep `course_applications` lines
  54, 262, 776; read the application section for the field table before editing it).
- `resources.CourseApplicationResource`: `APPLICATION_EXPORT_FIELDS` tuple (`id, applicant_email, applicant_name,
  is_email_verified, course, is_submitted, submitted_time, created_at`) is both `fields` and `export_order`; answer
  columns are appended after (`answer_columns(sittings, APPLICATION_EXPORT_FIELDS)` uses it to avoid header
  collisions). Add `state`. `SpreadsheetBooleanWidget` writes TRUE/FALSE; `IsoDateTimeWidget` for times. Tests:
  `tests/test_resources.py` (rows at ~131-163).
- `admin.CourseApplicationAdmin(SiteAwareExportModelAdmin)`: read-only (`has_add/change/delete_permission` False),
  `list_display` includes `is_submitted` (boolean column via `@admin.display`) and `submitted_time`; `list_filter` starts
  with `CourseApplicationSubmittedFilter` (title "submitted", `Q(form_progress__isnull=True)|Q(form_progress__completed_time__isnull=False)`)
  - replace with a `state` filter (a plain model-field filter or `ChoicesFieldListFilter`; the idea says "state column
  and filter in place of the submitted filter"). `fields = ["is_submitted","submitted_time_display","created_at"]` with
  `readonly_fields = fields` is the change page; add state there. Unfold `AutocompleteSelectFilter`,
  `InclusiveRangeDateTimeFilter`, `list_filter_submit = True` already in place. Tests: `tests/test_admin.py`
  (`test_is_submitted_column` line ~86, `test_submitted_filter_agrees_with_is_submitted` line ~284, submitted time
  formatting ~341).
- `docs/app_structure.md` is generated (`tests/test_generate_app_map.py`); the new imports (`course_applications` →
  `audit_log`, `organisations`) change the generated edges table (currently course_applications imports accounts, api,
  base, content_engine, course_access, form_engine, learner_management, mail, referral_tracking, site_aware_models).
  `audit_log` imports `accounts`, `organisations`, `site_aware_models`; no cycle through `course_applications`.

## 7. Templates

- `templates/course_applications/application_status.html`: `{% if application.is_email_verified %}` shows "Your
  application / has been received and is currently pending review ... A reviewer will assess your application. You will
  be notified once a decision has been made."; else "Check your email" plus `partials/claim_link_notice.html` (an
  `x-data` Alpine component, `static/course_applications/js/alpine-components.js` provides `claimLinkNotice`; CSP
  Alpine build, so no inline expressions). The state block, reject message and withdraw control go in the
  `{% comment %}NOTE{% endcomment %}` seam above the "Back to dashboard" `c-button`. The static copy is asserted by
  `test_status_page_contains_pending_review_message` (`tests/test_views.py` ~347-360, `"received" in content.lower() or
  "pending" in content.lower()`).
  Unverified (anonymous) applicants never reach state wording beyond the email check today; a withdrawn/closed
  anonymous application needs a decision (it can only be withdrawn from the session that holds it; see section 14).
- `templates/course_applications/partials/dashboard_applications.html`: row shell with the chip
  (`c-chip variant="info"` "Pending review" / `variant="warning"` "Incomplete"), the draft hint, and the CTA button
  ("View my application" / "Continue application"). Uses `partialdef` blocks (`panel-page`, `panel-status`,
  `panel-page-response`). States `approved` and `rejected` need chips and, for rejected, the message. The panel is
  contributed to `learner_interface` as a rendered template; it never imports `course_applications`.
- `check_your_answers.html`: `submitted` flag (from the sitting) shows "Your application has been submitted. You will
  hear back once it has been reviewed." plus link to status. Stays valid; the flag should follow state.
- `claim.html`/`claim_link_notice.html`/`email/application_claim_message.*`: consume `is_submitted` /
  `held_application`.

## 8. `Course.organisations`, `get_default_organisation`

- `Course.organisations = ManyToManyField("freedom_ls_organisations.Organisation", blank=True, related_name="courses")`
  (`content_engine/models/courses.py`, line ~179); `shared_with` is a separate M2M. `Course.single_organisation()`
  (line ~412) returns None for zero, several, **and for the site default organisation**, so it must **not** be reused
  for "the course's only owning organisation": an organisation course owned only by the default org returns None
  there, and the idea's rule ("exactly one in `Course.organisations`, otherwise the site default") would give the same
  organisation either way, but the code path must read `course.organisations.all()` directly (with prefetch where
  available). `panel_rows` already prefetches `course__organisations`.
- `organisations/utils.get_default_organisation(site) -> Organisation`: `Organisation._base_manager.get(site=site, is_default=True)`;
  raises `DoesNotExist` if the invariant (the `Site` post_save receiver in `organisations/signals.py`, partial unique
  index `one_default_organisation_per_site`) is broken. `organisation_of(target)` returns `target.organisation` when it
  is an `Organisation` (so a plain `organisation` FK on `CourseApplication` makes it work). Importing
  `organisations.utils` from `course_applications` is a new edge but not a cycle (`organisations` imports only
  `site_aware_models`).
- No existing "organisation for a new object" helper to reuse: `learner_management` models carry `organisation` as a
  `PROTECT` FK (`Learner`, `Cohort`: `learner_management/migrations/0001_initial.py`); follow that for
  `CourseApplication.organisation` (PROTECT, since `AuditLogEntry.organisation` is PROTECT and organisations are never
  deleted). Nullability decision: non-null requires the data migration to fill before `AlterField` (the three-step
  pattern, section 12), because a Site without a default organisation fails `get_default_organisation`. Applications
  are always created in a site with a request, so `get_cached_site(request)`/`course.site` supplies the Site.
- Tests need an organisation to exist per site: `mock_site_context` fixtures create the Site, which creates the default
  organisation through the post_save receiver; `tests/test_backends.py` line ~962 shows `course.organisations.create(...)`.

## 9. `audit_log`

- `writer.record_entry(*, action, actor, target, target_label, organisation, subjects=(), reason="", details=None, run_id=None, site=None)`.
  Opens no transaction; raises `ValueError` for an unknown action (via `validate_action`) or `reason` longer than
  `REASON_LENGTH` (500). Site is derived from the target (`site_of`), which needs a `SiteAwareModelBase`
  (`CourseApplication` is one). `actor` is a `User | None`; `actor_label = actor.display_name`. `details: Mapping[str, JSONValue]`
  (type in `audit_log/types.py`). `subjects` takes the course (History tabs read them; `subject_key(obj)` =
  `"<app_label>.<model_name>:<pk>"`).
- `actions.py`: `FLS_AUDIT_ACTIONS: tuple[AuditAction, ...]` of `AuditAction(code, label, describe=None, group="Other")`;
  `AUDIT_ACTION_GROUPS` tuple of headings in order (`Learners`, `Cohort membership`, `Course registrations`,
  `Course progress`, `Cohorts`, `Staff and roles`, `Other`): add `"Applications"` (placement before "Other"). The
  `_describe_*` helpers render `details`; a `from`/`to` renderer is a new one (compare `_describe_move`, `_describe_rename`).
  Registry built by `_registry(extra)`; `checks.py` (`freedom_ls_audit_log.E001`) rejects `AUDIT_LOG_EXTRA_ACTIONS`
  collisions with FLS codes; `tests/test_actions.py` and `tests/test_checks.py` iterate `FLS_AUDIT_ACTIONS`.
- `README.md` "Audit actions" table has columns `Code | Label | Group | Target | Other subjects | details`; add rows
  for `application.*` codes between "Staff and roles" and "bulk_action.completed". The README states the audit log
  "records staff actions only" (self-registration writes no entry; `self_register` writes `learner.reactivated` /
  `registration.reactivated` as the system only when it undoes something), which is the basis for not auditing the
  applicant's own submit/withdraw. Also states "`details` holds ids, labels and counts. Never put tokens, links or
  email addresses in it".
- **Vocabulary invariant test** `audit_log/tests/invariants/test_vocabulary.py`: hard-coded `NOUNS`, `VERBS`,
  `QUALIFIED_VERBS`, `WEBHOOK_ONLY`, `NOUN_GROUPS` sets. It asserts: every audit action noun is in `NOUNS` and verb in
  `VERBS`/`QUALIFIED_VERBS`; `action.group in AUDIT_ACTION_GROUPS`; **`action.group == NOUN_GROUPS.get(noun, "Other")`**
  (so `NOUN_GROUPS` needs `"application": "Applications"`); webhook types use the same vocabulary (none added here). Needs
  `NOUNS += {"application"}` and `VERBS += {...}` for any new verb: the existing set has `created, added, deactivated,
  reactivated, removed, deleted, assigned, moved, renamed, resent, completed, committed, signed_up, viewed, issued,
  revoked, paused, resumed, extended, exported`. `submitted`, `approved`, `rejected`, `withdrawn` are **absent**;
  `moved` exists (idea: not used here; `application.moved` belongs to spec 2). The retired-words test
  (`unregister, suspend, revoke, granted, reregister`) forbids the substring `revoke` in a code (`revoked` is
  allow-listed): irrelevant here unless a verb like `withdrawn` hits another list (it does not).
- Glossary: `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, section "Changes" (lines ~182-223): the noun list
  sentence (line ~190-192: "`learner`, `cohort`, `cohort_membership`, `registration`, ... `audit_log`") and the verb
  table (`| Verb | Means | Not |`, line ~194+) where new verbs are added (rows like `| `issued` | ... | `generated`, `minted` |`);
  the "Words that are already taken" table (line ~225+) has no `application` entry: **"application"** is not defined
  anywhere in the glossary today; it gains a noun entry and, because "withdrawn" overlaps the dev's `qa_reset_course_application`
  command's local `_withdraw_application` (which *deletes* rows), consider a "Not" note. It also says `registration`
  means course access (an approved application is not a registration; spec 3). The audit group sentence ("The audit log
  groups codes by the noun's family") gains Applications. A "Tenancy" table and a "Course access" table exist
  where `application` could be defined (`freedom_ls/course_applications/models.py`).
- Existing `record_entry` writers (house style to imitate): `learner_management/learner_actions.py`
  (`_set_learner_active`: `transaction.atomic()`, `Model._base_manager.select_for_update().get(pk=...)`, return False and
  write nothing when already in the state; `_change_learner_state` wraps the flip plus `record_learner_entry`;
  `record_learner_entry` labels with `learner.user.display_name`, `organisation=learner.organisation`),
  `learner_management/role_assignment.py`, `learner_management/utils.py`, `role_based_permissions/utils.py`,
  `api_admin/views.py`. Webhooks fire with `fire_webhook_event_on_commit` (not used here: no `application.*` webhooks).
  Applicant-name leak: `learner_actions` labels with a person's name, which this spec must NOT do; use course title +
  application id for `target_label`.
- `AuditLogEntry.organisation` is PROTECT; `organisation=None` is allowed by `record_entry` (type
  `Organisation | None`), but `organisation_of(application)` will return the FK, so use `organisation_of` or the field.
- Migration pattern for audit codes: `audit_log/migrations/0005_rename_member_audit_codes.py` (RunPython with
  `apps.get_model` and `update`). Not needed for new codes, only for renames.

## 10. House-style service functions (pattern to follow)

From `learner_management/learner_actions.py` and `README.md` "Writing an entry":

```
with transaction.atomic():
    locked = Model._base_manager.select_for_update().get(pk=obj.pk)
    if locked.state is already target / not allowed: refuse (here: raise)
    locked.state = new; locked.save(update_fields=[..., "updated_at"])
    record_entry(action=..., actor=..., target=locked, target_label=..., organisation=locked.organisation, details={"from": ..., "to": ...})
```

- Module location: the idea names none; the research doc suggested `course_applications/review.py` or `transitions.py`.
  `claims.py`, `queries.py`, `emails.py`, `erasure.py` are the existing flat modules.
- Refusal exception: audit_log has `exceptions.py` (check it before defining a new one); the repo's pattern for a
  refused action is a dedicated exception (e.g. `CourseNotOpenError` from `register_for_course`).
- Approve of an application with `user is None` must raise (idea). Approve/reject act on `submitted` only (answers.md);
  reject message required (service refuses empty); the message is a new text field on the application, stored not
  audited. No existing `ReasonForm`-style limit applies to it; `REASON_LENGTH=500` is for audit `reason`.
- Applicant actions (submit, withdraw) are service functions too but write no audit entry: the README says audit is
  staff-only, and `actor_label` would retain the applicant's name.

## 11. Confirm dialog for a destructive POST on a learner-facing page

answers.md: withdraw asks for confirmation first. Existing patterns:

- Educator side: `panel_framework` (`ConfirmAction`, `templates/panel_framework/modal/confirm.html`,
  `modal_host.html`, `educator_interface/templates/educator_interface/modal/*_confirmation.html`). That is the
  panel-framework modal machinery, educator interface only; `learner_interface` does not use it and
  `course_applications` must not depend on `panel_framework`/`educator_interface`.
- Learner side: `learner_interface/templates/learner_interface/course_form_page.html` holds the exam-exit and submit
  dialogs: `x-data="examExitDialog"` / `examRunnerForm` wrapper, trigger `x-on:click="showExit($el)"`, panel with
  `x-ref="dialogPanel" role="dialog" aria-modal="true" x-show="open" x-cloak x-on:keydown.escape.window="dismiss"`, buttons
  `x-on:click="dismiss"`. The Alpine factory `makeConfirmDialog(extraProps)` (open state, focus trap, focus return to
  trigger, Escape) lives **inline in** `learner_interface/static/learner_interface/js/alpine-components.js`, not shared
  and not exported; `course_applications` cannot import it (it must not reach into `learner_interface`; the dependency
  runs one way: `learner_interface -.-> course_applications` only through the backend). A withdraw dialog in
  `course_applications` therefore needs its own Alpine component in
  `course_applications/static/course_applications/js/alpine-components.js` (CSP-compatible, registered in an
  `alpine:init` listener like `claimLinkNotice`, loaded in the page via `{% block extra_alpine_components %}`) or a native
  `<dialog>`; check `fls-dev:alpine-js` (`claude_plugins/fls-dev/skills/alpine-js/SKILL.md` mentions course_applications).
  No generic `<c-confirm>`/`<c-dialog>`/`<c-modal>` cotton component exists in `base/templates/cotton/` (it holds `back-link`,
  `breadcrumbs`, `button`, `button-group`, `callout`, `chip`, `content-header`, `date`, `datetime`, `dropdown-menu`,
  `error-page`, `form-page-link`, `header-button`, `loading-indicator`, `markdown-container`, `media-card`, `page`,
  `pagination`, `panel-callout`, `section-pagination`).
- No `hx-confirm`/`window.confirm` use found in the learner templates. A plain no-JS fallback: the withdraw `<form
  method="post">` still works without JS if the dialog just toggles visibility of a form.
- Reference for the wording and behaviour: `claim.html` is a GET-confirm/POST-claim page (a whole confirm page rather than
  a dialog); that is the other house precedent for "confirm before an action", and is no-JS safe.

## 12. Migrations: ordering, data migration patterns, risks

- Latest `course_applications` migration: `0008_courseapplication_courseapp_site_updated_idx` (depends on
  `freedom_ls_content_engine 0011`, `freedom_ls_form_engine 0008`, `sites 0002`, `AUTH_USER_MODEL`). `organisations` has
  `0001_initial`, `0002_organisation_bio_organisation_profile_logo`. The new `organisation` FK adds a dependency on
  `freedom_ls_organisations` (latest). `audit_log` is at `0005`.
- Repo data-migration patterns (`RunPython`, 9 files): `learner_management/migrations/0011_registration_updated_at.py`
  (add nullable column → `RunPython(backfill, noop)` → `AlterField` to final; `backfill` uses `apps.get_model` and
  `model._base_manager.update(...)` with `F()`); `0006_delete_orphan_cohort_role_rows.py`;
  `learner_progress/migrations/0003_courseprogress_updated_at.py`; `course_interest/migrations/0002_courseinterest_updated_at.py`;
  `deadlines/migrations/0007_deadlineextension_granted_at.py`; `audit_log/migrations/0005_rename_member_audit_codes.py`;
  `role_based_permissions/migrations/0002_rename_educator_roles.py`. Reuse the three-step: add `state` with a
  default (or nullable), `organisation` nullable, `RunPython` to fill both, then tighten, then swap the constraint.
- Migration ordering for the constraint swap: `RemoveConstraint(unique_application_per_site_user_course)` then
  `AddConstraint(UniqueConstraint(fields=["site","user","course"], condition=Q(state__in=[draft, submitted, approved]) , name=...))`.
  Which states count as "active" for uniqueness is open in the idea: `draft`, `submitted` surely; **`approved`** must also
  block a new application (an approved applicant should not reapply, and approved is the state that later registers),
  while `rejected`/`withdrawn` do not. The condition must be written with literal strings in the migration (not the
  enum import). `AddConstraint` with a `condition` on Postgres builds a partial unique index: building on large tables
  without `CONCURRENTLY` takes a lock; the table is small by comparison to others in this project but note it. The new
  constraint name should differ from the old one or the migration must remove before adding (`0006` itself did this).
  Existing data cannot violate the new partial index (it is a strict subset of the old unconditional one).
- Data migration rules from the idea: no sitting or a completed sitting → `submitted`; open sitting → `draft`. Query
  shape: `form_progress__isnull=True` or `form_progress__completed_time__isnull=False` → submitted;
  `form_progress__isnull=False, form_progress__completed_time__isnull=True` → draft. `submitted_time` derived the
  same way from existing fields means the backfill can also set a stored `submitted_at` (if one is added) from
  `created_at`/`completed_time`; the idea says `is_submitted` and `submitted_time` are "derived from it and stay in the
  API", so a stored `submitted_at` is not required but derived-from-state alone cannot recover the time for no-form
  courses (creation time) or for form courses (sitting `completed_time`): keep `submitted_time` reading
  `form_progress.completed_time`/`created_at`, or store a timestamp. This is an open design point for the spec.
- Organisation backfill: per row `course.organisations` count; exactly one → that org else the site's default org
  (`Organisation._base_manager.get(site_id=app.site_id, is_default=True)`; a migration must not import
  `get_default_organisation`). A site with no default organisation (the invariant says none, but dev databases can be
  odd) would make the migration crash or leave NULL rows; decide fail-loudly vs create. Use `_base_manager` in migrations;
  `apps.get_model` historical models in this repo expose `_base_manager`/`objects` as plain managers (the 0011
  migration uses `_base_manager.update`).
- `updated_at` on the backfill: see section 5; `0011` set `updated_at` explicitly for the sync feed.
- `makemigrations` must be run, and generated migration files keep the project's `0006`/`0008` formatting (single
  quotes, `Generated by Django 6.0.4`). CLAUDE.md: never edit existing migrations.
- Tests that create rows through `CourseApplicationFactory` (no `state`): the model default for `state` decides what
  they mean. If the default is `draft`, every no-form factory application (which `test_models.py:139` asserts
  `is_submitted is True`) becomes a draft unless the factory or `save()` sets state from `form_progress`. If the
  default is `submitted`, factory applications with `form_progress` are wrong unless the factory sets `draft`. The factory
  (`factories.py`, params `anonymous`, `anonymous_draft`) must be updated either way; many tests build a draft by passing
  `form_progress=FormProgressFactory(...)` without `completed_time`. QA commands also use the factory:
  `qa_create_application_docs_scenario.py:337`, `qa_create_bulk_applications.py:101`,
  `qa_create_dashboard_applications_panel.py:217`, `qa_create_phone_question_scenario.py:172`,
  `qa_create_second_application_form_course.py:148`; the first four `complete()` the sitting after creation (bulk line
  ~124, second line ~173), which **bypasses the service function**: those scripts would leave `state=draft` with a
  completed sitting, and their tests (`qa_helpers/tests/management/commands/test_qa_create_bulk_applications.py:50`,
  `test_qa_create_dashboard_applications_panel.py:54`, `test_qa_create_second_application_form_course.py:35`) assert
  `is_submitted`. Any other `FormProgress.complete()` caller on an application sitting (no other production code path
  besides `application_check_answers`; QA commands only) must go through the submit service function, or `state` and
  `completed_time` drift apart (the idea says state is the one source of truth). `qa_create_application_review_accounts.py`
  and its test seed an `is_staff` reviewer with `view_*` model permissions for the Django admin, a stale scaffold from the
  earlier plan.
- `contrib/conformance/tests/test_timestamped_models.py` lists `AnonymousApplicant` (a `TimestampedModel`) but not
  `CourseApplication` (which defines its own `created_at`/`updated_at`): no new conformance entry needed unless fields are
  added with `TimestampedModel`.
- Dev tools that bulk-delete applications: `dev_tools/management/commands/danger_clear_all_course_progress.py` and
  `danger_content_delete.py` (they work around the `form_progress` RESTRICT; `dev_tools/tests/test_danger_commands_with_applications.py`).
  `AuditLogEntry.organisation` PROTECT plus a new `CourseApplication.organisation` PROTECT does not change what they delete
  (applications are deleted, organisations are not). `qa_reset_course_application.py` has `_withdraw_application`, which
  *deletes* the application (the word "withdraw" is already used there for deletion); it filters `user=user, course=course`
  and now may match several rows (fine, it iterates a queryset).

## 13. Other reuse and neighbours

- `form_engine/admin.py` line 46 conditionally links to the application admin through `apps.is_installed`; unchanged.
- `course_access/analytics_events.record_application_submitted(request, course)` fires on submission. It takes a
  request: the submit service function is request-less, so the event stays in the view (as today), after the service call.
- `referral_tracking.conversions.record_conversion`/`discard_conversions_for`: see section 5.
- `deployment/context_processors.py` line 13 names `"course_applications:claim"` (a URL name allow-list/strip); a new
  `course_applications:withdraw` URL name is not claim-token-bearing, so unaffected, but check the list's purpose first.
- `docs/api.md` (course-applications section), `docs/app_structure.md` (generated), and
  `claude_plugins/fls-dev/skills/testing/SKILL.md` / `resources/testing.md` mention `course_applications` (testing guidance
  for the app's fixtures).
- Agent memory files under `.claude/agent-memory/sdd-qa-data-helper/` mention `CourseApplication` having "no `status`"
  (e.g. `reference_withdrawing_a_course_application.md`); they become stale but are not part of the work.

## 14. Conflicts and risks (summary)

1. **`get_or_create` and `.first()` assume one application per (user, course).** `_start_application`'s `get_or_create`,
   `get_application_for_course`'s `.first()`, `attach_to_user`'s `held` lookup and `qa_reset_course_application` all break
   or pick arbitrarily once a closed and an active application coexist. Each needs the active-state filter or an explicit order.
2. **Anonymous re-apply.** `AnonymousApplicant` and its application are a OneToOne, and the session maps one applicant per
   course (`ANONYMOUS_APPLICANTS_SESSION_KEY: {course_id: applicant_pk}`, `anonymous_applicant_for_course` filters by the
   course and `user__isnull=True`). After an anonymous application is withdrawn, `_anonymous_apply` finds
   `application_of(applicant)` and redirects to status; there is no way to start a second application for the same
   applicant (`anonymous_applicant` OneToOne). The idea's "apply again" is for signed-in accounts; spec should state what an
   anonymous (unclaimed) applicant sees after withdrawing (and whether they can withdraw at all; the idea says withdraw is on
   the status page for draft/submitted, and `owned_applications` lets an anonymous session reach it).
   Rejection requires approve/reject on an application with a `user` for approve only; reject of an unclaimed one is allowed
   by the idea's wording (only approve is refused) and the status page for it renders under "Check your email" today.
3. **Two sources of truth.** `form_progress.completed_time` vs `state`. Every reader of `is_submitted` (views at lines ~216,
   268, 411, 460, 593, 708, 853, 940, 969; claims; admin; resources; API) must read state-derived values. Callers that
   test `form_progress.completed_time` directly bypass state: `application_status` (line ~281), `application_form_page`
   (`read_only`), `application_check_answers` (`submitted`), `backends.get_dashboard_contributions_for_request` (anonymous
   draft filter). A withdrawn draft keeps `completed_time=None`: a naive reader would send the applicant back to the form.
4. **Partial index vs claim attach.** `attach_to_user` writes `user` last; a leftover active held row raises `IntegrityError`
   from the partial unique index. Cover with a two-active-states test (held submitted/approved vs incoming draft or
   submitted).
5. **Approved counts as active for uniqueness** (open); if it does not, an approved applicant can re-apply and end with two
   approved rows.
6. **Existing test assertions on copy.** "View my application", "Pending review", "Incomplete", the "has been submitted and
   is pending review" toast, and "received"/"pending" on the status page are asserted in many tests (sections 3, 4, 7, 15).
7. **New module edges** change the generated `docs/app_structure.md` and its test. `course_applications` → `audit_log` and
   → `organisations`. Check `claude_plugins`/structure invariants (`tests/test_generate_app_map.py`).
8. **Vocabulary test needs three coordinated edits** (`NOUNS`, `VERBS`, `NOUN_GROUPS`) plus `AUDIT_ACTION_GROUPS` and the glossary;
   the test fails if any one is missed. `application_status` and similar prose nouns must not clash with the glossary's
   `Words that are already taken` (no `application` row today).
9. **Reject message privacy/limits.** Stored on the application, not audited. No existing max-length convention beyond
   `REASON_LENGTH=500` for audit reasons; choose a limit and a `TextField`/`CharField`. The applicant sees it on the status
   page and the dashboard panel (answers.md); it must be escaped (template autoescape), not rendered as markdown.
10. **Conversions on re-apply** (section 5): a second application writes a second `COURSE_APPLICATION` conversion for the same
    user and course.
11. **`organisation` backfill failure mode** if a site has no default organisation (section 12).
12. **Dashboard panel wording/ordering.** Showing closed (rejected/approved) applications on the panel means a re-application
    sorts above its closed predecessor (`-created_at`), so both appear until the closed one is dismissed or aged out; the spec
    should say whether a closed application is hidden once a newer one exists for the same course.
13. **Pytest/dev DB.** Per CLAUDE.md run `uv run manage.py makemigrations` then `migrate`; never edit `0001`-`0008`.

## 15. Existing tests to extend (all under `freedom_ls/course_applications/tests/` unless noted)

- `test_models.py`: class around lines 139-189 (`is_submitted`/`submitted_time`), constraint tests (grep `unique`), `__str__`.
- `test_views.py` (~4800 lines): apply (154-306), status page (347-360, 525, 1709-1769, 2025-2062, 3913-3995, 4731-4794), check
  answers (1045, 1229-1298), claim (3244-3600), anonymous (2001-2710).
- `test_claims.py` (73 tests): "submitted beats draft" at lines ~468-640, 1055 (conversion count); `test_receivers.py` (login adopt,
  `updated_at` touches at ~465-635, conversions ~739-756).
- `test_queries.py`: `get_application_for_course` (22-80) and `get_active_applications` (86-106).
- `test_backends.py`: CTA label tests (283-368, 720, 752) and panel rendering (460-497, 962 org prefetch, 1010, 1179 query counts).
- `test_api.py`: field list (60-75), submitted/draft rows (162-181); `test_resources.py` (131-163); `test_admin.py` (86-91, 284-298, 341).
- `tests/conftest.py`, `tests/helpers.py` (`gated_course_with_form`, `unverified_application_with_file`,
  `anonymous_request_holding`, `application_ids_updated_since`): new helpers for states belong here; `factories.py` gets a state/organisation default.
- `tests/playwright/test_application_form_flow.py` (lines ~120, ~469): panel text; the spec's frontend QA will add withdraw flow.
- Elsewhere: `audit_log/tests/invariants/test_vocabulary.py`, `audit_log/tests/test_actions.py`, `audit_log/tests/test_writer.py`;
  `learner_interface/tests/views/test_course_detail.py` (~208, ~225), `test_course_listing.py`, `test_course_access.py`,
  `templatetags/test_course_card_tags.py`; `qa_helpers/tests/...` listed in section 12; `course_access/tests/test_checks.py`,
  `test_overrides.py` reference `course_applications`.
- New tests the spec implies: service-function tests (each transition allowed/refused, atomic audit entry, no entry on no-op,
  no applicant name/email in entry, `from`/`to` in details, unclaimed approve refused, empty reject message refused, approve/reject only from
  `submitted`), migration test for the data migration (the repo has no migration-test convention in `course_applications`;
  check `tests/` of other apps with `RunPython` migrations before choosing), state transition on `updated_at`, withdraw view
  (POST only, owner only, 404 otherwise, refused for closed states), partial index (second active refused, second after
  reject/withdraw allowed), vocabulary invariant, dashboard panel states.

status: ok
