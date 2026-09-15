# Application Review Workflow & Educator-Facing Review UI

Builds on top of **`applying-for-courses`** (`spec_dd/2. in progress/applying-for-courses`),
which ships the course-access backend, the `application_gated` access type, and a **form-less
Apply flow that creates a `CourseApplication`** — and nothing more. The base spec deliberately
stops at *creating* the application: it has **no state machine, no reviewer permissions, no
audit log, and no review surface**.

This spec owns the **entire review workflow**:

1. the `CourseApplication` **state machine** (`django-fsm-2`) — the submit/withdraw/pick-up/
   request-changes/resubmit/approve/reject lifecycle, the audit log, and the
   `application_state_changed` signal;
2. the **reviewer permission model** (object-level guardian via the role machinery);
3. **review v1 through the Django admin** (a filterable inbox + per-application transition
   actions), as the minimum reviewer surface; and
4. the **bespoke, educator-facing review UI** in `educator_interface` (a global applications
   inbox + a full-screen single-application screen) so reviewers no longer need to be Django
   **staff** users.

Phases 1–3 are the workflow + the simplest reviewer surface; phase 4 is the richer educator UI.
When this draft is promoted via `/spec_from_idea`, phases 3 and 4 may collapse into a single
"build the educator UI directly" decision, or ship as two increments — that is a planning call.

> **Scope note:** the base spec previously shipped the state machine + admin review itself, with
> this draft layered on top as "UI only". That was split: the base spec now ships **create-only**,
> and the whole review workflow moved here. So this spec *builds* the FSM — it does not assume it
> already exists.

---

## Why this is its own spec

Reviewers are educators / programme managers, **not** Django superusers. Shipping review on the
Django admin (phase 3) forces reviewers to be `is_staff`. Lifting review out of the admin so
non-staff educators can review — using the access scoping and panel framework
`educator_interface` already provides — is the end goal (phase 4).

`educator_interface` already houses cohort/student/registration UI and already scopes access
with `django-guardian`
(`get_objects_for_user(request.user, "view_cohort", klass=Cohort)`,
`educator_interface/views.py:84`), so the review UI belongs there.

This spec introduces the `course_applications → role_based_permissions` and (phase 4)
`educator_interface → course_applications` dependency edges that the base spec deliberately
avoids. Flag both for `/plan_structure_review`.

---

## 1. State machine (`django-fsm-2`)

Add the dependency: `uv add django-fsm-2`. Optionally `uv add django-fsm-admin`
(`FSM_ADMIN_FORCE_PERMIT = True`) to render the admin transition buttons (phase 3) — only if it
composes with django-fsm-2 + Unfold; otherwise fall back to plain Unfold admin actions (the
transition methods + permission callables are identical either way).

`CourseApplication` gains `state = FSMField(default="draft", protected=True)` plus the
decision/timestamp fields, as an **additive migration** (the base ships the model without a
`state` field, so this is a fresh defaulted column — not a CharField→FSMField conversion). The
full transition set (per `research_review_workflow.md §1.3`):

| method | actor | source → target | notes |
|---|---|---|---|
| `submit` | applicant | draft → submitted | set `submitted_at`; the `application-forms` spec adds required-answer validation here |
| `withdraw` | applicant | [draft, submitted, changes_requested] → withdrawn | terminal-ish; frees re-application |
| `pick_up` | reviewer | submitted → under_review | requires `change_application` |
| `request_changes` | reviewer | under_review → changes_requested | **requires** an applicant-visible message |
| `resubmit` | applicant | changes_requested → submitted | re-submits (gains answer re-validation with the form) |
| `approve` | reviewer | under_review → approved | terminal; set `decided_at`/`decided_by`; optional internal note |
| `reject` | reviewer | under_review → rejected | terminal; set `decided_at`/`decided_by`; optional internal note |

- Reviewer transitions use `permission=` callables delegating to
  `user.has_perm("change_application", instance)` (django-guardian, object-level).
- **One DRY audit helper, `from_state` captured *before* the transition fires.** By the time a
  `@transition`-decorated method body runs, django-fsm-2 has already flipped `self.state`, so the
  call site captures the source first:
  ```python
  with transaction.atomic():
      from_state = application.state          # capture BEFORE
      application.submit(actor=request.user)  # FSM flips state, sets submitted_at, etc.
      application.save()
      application._record_transition(from_state=from_state, to_state=application.state,
                                     actor=request.user, message=message)
  ```
  ```python
  def _record_transition(self, *, from_state, to_state, actor, message=""):
      # site-aware — ApplicationStateTransition.save() reads the active request's site
      # thread-local, so this runs inside a request/admin action (or mock_site_context in tests).
      ApplicationStateTransition.objects.create(
          application=self, from_state=from_state, to_state=to_state, actor=actor, message=message)
      application_state_changed.send(sender=type(self), application=self,
                                     from_state=from_state, to_state=to_state, actor=actor)
  ```
  All seven transitions log + signal identically through this one helper; the transition methods
  themselves only mutate FSM-adjacent fields (`submitted_at`, `decided_at`/`decided_by`). Wrap
  flip + save + record in `transaction.atomic()` so the state change and its audit row are atomic.
- **Signal:** define `application_state_changed` in `course_applications/signals.py`; wire it in
  `course_applications/apps.py` `ready()` (the base spec's `ready()` does not import signals — this
  spec adds that). v1 has no listener; it is the seam for a future email backend.
- Drive buttons off `instance.get_available_user_state_transitions(user)` — never hardcode
  state→button maps (used by the admin and the educator UI alike).
- `request_changes` / `resubmit` ship now even though, with no form, there is nothing for the
  applicant to edit between them; they become fully meaningful once `application-forms` lands.
- `expired`/`waitlisted` and multi-reviewer are out (the audit row + signal already accommodate
  them — do not architect away).

### Re-apply / active-application rule

The base spec ships a **plain** unique constraint (one `CourseApplication` per
`(site, user, course)`). This spec **replaces** it with the **active-state partial unique index**
(spec §5.1) — at most one ACTIVE application per `(site, user, course)`, active = state in
`{draft, submitted, under_review, changes_requested}` — so a rejected/withdrawn application no
longer blocks re-application. Per `fls:multi-tenant`, include the **site column explicitly**:
```python
constraints = [
    models.UniqueConstraint(
        fields=["site", "user", "course"],
        condition=Q(state__in=["draft", "submitted", "under_review", "changes_requested"]),
        name="unique_active_application_per_site_user_course",
    )
]
```
Migration: drop `unique_application_per_site_user_course`, add the partial index. Also narrow the
base's `get_active_applications(user)` (currently "all of the user's applications") to filter on
the active states.

## 2. Models added here

```
# Added to CourseApplication:
  state        FSMField(default="draft", protected=True)
  submitted_at, decided_at  DateTimeField(null=True, blank=True)
  decided_by   FK User | None (on_delete=SET_NULL, related_name="+")
  Meta.permissions = [("view_application", ...), ("change_application", ...)]   # guardian-friendly codenames

ApplicationNote                # staff-only internal note (structurally distinct from applicant message)
  application FK (related_name="notes"), author FK User|None, body Text, created_at

ApplicationStateTransition     # audit log; one row per transition
  application FK (related_name="transitions")
  from_state, to_state  CharField
  actor    FK User | None
  message  TextField(blank=True, default="")   # applicant-visible (e.g. the request_changes reason)
  created_at
```

Both new models inherit `SiteAwareModel` (UUID pk + `site` FK). Internal notes
(`ApplicationNote`) and applicant-facing transition messages (`ApplicationStateTransition.message`)
stay **structurally separate** — never merged, so no internal commentary leaks to applicants.

Declare the custom permissions explicitly (Django also auto-creates `view_courseapplication` etc.;
the short guardian-friendly `view_application` / `change_application` are what the role config and
`has_perm` calls use).

## 3. Permissions — guardian via the role machinery (mirror the cohort pattern)

The "cohort pattern" is **not** raw `assign_perm`; it is `assign_object_role(user, target, role)`
→ creates an `ObjectRoleAssignment` → `sync_user_object_permissions` translates the role's
configured permission set (filtered to the target's content type by
`_filter_perms_for_content_type`) into guardian grants
(`role_based_permissions/utils.py:123–226`). **Use that machinery, not ad-hoc `assign_perm`**, so
applications participate in the same role/permission model as cohorts.

- Add a **reviewer role** to the role config (`role_based_permissions/roles.py` — no reviewer role
  exists in `BASE_ROLES` today) whose permission set includes `view_application` +
  `change_application`.
- **Grant trigger:** assign the reviewer role on the `submit`/`resubmit` transition (same atomic
  block as the audit row), to the users who already hold that role on the course's site.
- **Course↔reviewer mapping — v1 staff fallback.** There is no existing model edge linking a
  *course* to its reviewers. **v1 (chosen):** grant on submit to site **staff** holding the
  reviewer role (matching the v1 `is_staff` admin constraint), leaving a `# TODO` for per-course
  reviewer scoping. Do not silently invent a richer course↔reviewer mapping.
- State-changing transitions delegate to `user.has_perm("change_application", instance)`; the admin
  changelist scopes to `get_objects_for_user(...)`. Site isolation is automatic via
  `SiteAwareModel` — Site A reviewers never see Site B applications.

**Structure edges introduced:** `course_applications → role_based_permissions` (grant the role) and
a read of `student_management` (which staff hold the reviewer role). Regenerate
`docs/app_structure.md` via `/app_map` after implementation; add the edges to the base spec's §8.
(Rejected: raw `guardian.shortcuts.assign_perm` — avoids the `role_based_permissions` edge but does
not reuse the project's role model, inconsistent with cohorts.)

## 4. Review v1 — Django admin (`course_applications/admin.py`)

The app owns its own admin → **no** `educator_interface → course_applications` edge for v1. Per
`fls:admin-interface`: Unfold `ModelAdmin` + `guardian.admin.GuardedModelAdmin` (same combination
as `CohortAdmin`, `student_management/admin.py:38`). `GuardedModelAdmin` does **not** inherit
`SiteAwareModelAdmin`, so set `exclude = ["site"]` **manually**.

- **Changelist = the v1 inbox.** `list_display = [applicant, course, state, submitted_at,
  decided_at]` (an `applicant` method showing name/email); `list_filter = [state, course,
  submitted_at]`; `search_fields = [user__email, user__first_name, user__last_name,
  course__title]`; `ordering = ["submitted_at"]` (oldest first); `autocomplete_fields = [user,
  course]`; `readonly_fields` for timestamps + `decided_by`. `get_queryset` scopes via
  `get_objects_for_user(request.user, "view_application", klass=CourseApplication)` (site isolation
  automatic). Reviewers must additionally be `is_staff` to reach the admin (v1 tradeoff).
- **Transition actions (intermediate pages).** Buttons driven by
  `instance.get_available_user_state_transitions(request.user)`, each gated on
  `user.has_perm("change_application", instance)`. `request_changes` and `reject` use Django's
  **intermediate action page** to capture the required applicant-facing message/reason before
  applying; `approve` takes an optional internal note (→ `ApplicationNote`). Each action calls the
  model transition method inside `transaction.atomic()` (FSM flip + audit row + signal commit
  together).
- **Inlines.** Both inline models extend `SiteAwareModel`; Unfold `TabularInline` does **not**
  exclude `site` — each inline **must set `exclude = ["site"]`**. (Follow the resource file +
  `student_management/admin.py`, which use `unfold.admin.TabularInline` directly; the
  `fls:admin-interface` SKILL.md references a nonexistent `SiteAwareTabularInline` — flag that stale
  reference separately.)
  - `ApplicationNoteInline` — writable, staff-only; set `author = request.user` on save.
  - `ApplicationStateTransitionInline` — **read-only** (`has_add/change_permission → False`, all
    fields in `readonly_fields`), newest-first: who/when/from→to + applicant-visible message.
- **Approval ≠ enrolment.** On an approved application's change page, surface an **"Enrol this
  learner"** link into the existing cohort + `UserCourseRegistration` flow with the user pre-filled
  — a **URL hand-off**, not a code dependency. Approving never auto-creates a registration. Because
  admin/cohort enrolment bypasses the access backend (base spec §4.4), the approved learner enrols
  cleanly.
- **No bulk approve/reject in v1.**

## 5. Applicant status-page additions

The base spec ships a **static** status page ("your application has been received, pending
review"). This spec adds:
- plain-language current state driven by the FSM; when `changes_requested`, show the reviewer's
  message (latest `request_changes` transition `message`); when `approved`/`rejected`, the decision
  + any applicant-visible message;
- a **withdraw** action available while active, driven by
  `get_available_user_state_transitions(request.user)` (never a hardcoded button map), POSTing an
  atomic `withdraw` transition.
Dashboard reachability is unchanged — still the base spec's `get_dashboard_contributions` panel.

## 6. Bespoke educator-facing review UI (the end goal)

Replace the admin review surface (phase 4) so non-staff educators can review.

### Global applications inbox (not per-course)
A filterable table across the reviewer's site — filter by course, status, date; search by
applicant name/email; default sort oldest-submitted-first. Built on the existing panel/list-config
framework (`CohortDataTable`, `educator_interface/views.py:80`; `CohortConfig extends
ListViewConfig`, `views.py:756`). Queryset scoped via
`get_objects_for_user(request.user, "view_application", klass=CourseApplication)`, site-isolated.

### Single-application review screen (row click → full screen, not a modal)
- **Main area** = applicant identity + application metadata. (Answers/documents arrive with
  `application-forms`, which adds them to this same main area.)
- **Sticky sidebar** = state-aware decision actions (from `get_available_user_state_transitions`),
  internal notes (`ApplicationNote`), and the transition log (`ApplicationStateTransition`).
- `request_changes` and `reject` require a confirmation step capturing their message/reason.
- On resubmit, prominently mark "resubmitted at <time>" and link the prior reviewer message in the
  log.

### Internal notes vs applicant-facing message
Two clearly distinct UI affordances, never merged — same model split enforced in §2.

### Approval ≠ enrolment — in-context hand-off
The approved-application screen exposes the "Enrol this learner" deep-link (the same hand-off §4
ships as an admin link, re-homed into the review screen).

**Structure edge (phase 4):** `educator_interface → course_applications`. Flag for
`/plan_structure_review`.

---

## Permissions summary

- `view_application` / `change_application` granted object-level via guardian through the **role
  machinery** (not raw `assign_perm`), mirroring cohorts. A new reviewer role lists those codenames.
- State-changing transitions delegate to `user.has_perm("change_application", instance)`.
- Site isolation automatic via `SiteAwareModel`.
- The win of phase 4 over phase 3: reviewers no longer need `is_staff` / admin access.

## Out of scope (same deferrals as the base spec)

No bulk approve/reject; no multi-reviewer assignment / rubric / score review; no email
notifications (the `application_state_changed` signal remains the seam). Django/Unfold admin may
still expose the models read-mostly for support even after the educator UI lands.

## Seams in place from the base spec (`applying-for-courses`)

- The created `CourseApplication` (user, course, timestamps, plain unique constraint) — **no
  `state` field, no transitions, no audit/notes models, no reviewer permissions**: all built here.
- The course-access seam + the `ApplicationCourseAccessBackend` ("Apply now" CTA, the
  `application_gated` type, the in-flight dashboard panel via `get_dashboard_contributions`).
- The form-less Apply view (create + redirect to status) and the static status page — this spec
  re-enters them to add `submit`/audit and the dynamic state/withdraw display (the base marks both
  with `# NOTE (review spec)` seam markers).

## Relationship to `application-forms`

`application-forms` (`spec_dd/0. drafts/application-forms`) hangs answers/files/config off
`CourseApplication` **and** off this spec's state machine (its `submit` gains required-answer
validation; its review screen gains the answers/documents). The two follow-ups are independent and
can ship in either order; whichever lands second renders the answers/documents inside the review
screen defined here. **`application-forms` depends on this spec for the FSM** (the base spec no
longer ships it) — if `application-forms` lands first, it must introduce a minimal draft/submitted
state itself.

---

## QA seed (carried over from the base spec's frontend QA)

These reviewer flows were removed from the base spec's `3. frontend_qa.md` (Tests 5–7) and belong
to this spec's eventual QA plan. Setup additionally needs a **staff reviewer** account
(`is_staff=True`) holding object-level `view_application` + `change_application` on the gated
course's applications on DemoDev.

- **Reviewer actions in the admin/UI:** the inbox shows the application (applicant, course, state,
  submitted/decided); filtering by state/course + search by applicant email work; only own-site
  applications appear. `pick_up` → under_review (logs a transition row). `request_changes` with no
  message → intermediate page re-renders with an error, no transition. `request_changes` with a
  message → changes_requested; the log records the applicant-visible message. Add an internal note
  → saved with reviewer as author, not shown to the applicant.
- **Applicant sees the reviewer's message (not internal notes):** status shows changes_requested +
  the applicant-facing message; the internal note is not visible. Withdraw → withdrawn; the action
  then disappears.
- **Approval & enrol hand-off (approval ≠ enrolment):** pick_up → approve → approved (transition
  logged). The learner is not auto-enrolled. The approved change page exposes "Enrol this learner"
  with the learner pre-filled; completing it registers the learner (bypassing the access gate), who
  can then reach content.
