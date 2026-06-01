# Educator-Facing Application Review UI

Builds directly on top of **`applying-for-courses`** (`spec_dd/2. in progress/applying-for-courses`),
which ships the course-access backend, the `application_gated` access type, the
`CourseApplication` state machine, and — for v1 — **review through the Django admin**.

This follow-up replaces the admin review surface with a **bespoke, educator-facing review
UI in `educator_interface`**: a global applications inbox and a full-screen
single-application review screen, so that reviewers (educators / programme managers) no
longer need to be Django **staff** users to action applications.

Nothing here changes the state machine, the permission model, the notes/audit models, or the
apply flow. The base spec was written so this work is purely additive: the FSM transitions,
`get_available_user_state_transitions`, `ApplicationNote`, and `ApplicationStateTransition`
are all UI-agnostic, and the admin in the base spec is merely one caller of that machinery.

---

## Why this is its own spec

Reviewers are educators / programme managers, **not** Django superusers — but the base spec
ships review on the Django admin "to keep v1 simple", which forces reviewers to be `is_staff`.
Lifting review out of the admin so non-staff educators can review — using the access scoping
and panel framework `educator_interface` already provides — is the entire point of this spec.

`educator_interface` already houses cohort/student/registration UI and already scopes access
with `django-guardian`
(`get_objects_for_user(request.user, "view_cohort", klass=Cohort)`,
`educator_interface/views.py:84`), so the review UI belongs there.

This is also the spec that introduces the `educator_interface → course_applications`
dependency edge that the base spec deliberately avoids (it keeps `course_applications` a leaf
by putting its admin in its own `admin.py`). Flag the new edge for `/plan_structure_review`.

---

## What this adds

### 1. Global applications inbox (not per-course)

A filterable table across the reviewer's site — filter by course, status, date; search by
applicant name/email; default sort oldest-submitted-first. Built on the existing panel /
list-config framework (`CohortDataTable`, `educator_interface/views.py:80`;
`CohortConfig extends ListViewConfig`, `views.py:756`). Queryset is scoped via
`get_objects_for_user(request.user, "view_application", klass=CourseApplication)` and inherits
site isolation from `SiteAwareModel`. A global (not per-course) inbox is a recurring unmet
need elsewhere in `educator_interface`.

### 2. Single-application review screen (row click → full screen, not a modal)

- **Main area** = applicant identity + application metadata. (Answers/documents are not added
  here — they arrive with the `application-forms` spec, which adds them to this same main
  area; see "Relationship to `application-forms`" below.)
- **Sticky sidebar** = state-aware decision actions (rendered from
  `get_available_user_state_transitions`), internal notes (`ApplicationNote`), and the
  transition log (`ApplicationStateTransition`).
- `request_changes` and `reject` require a confirmation step capturing their
  message / reason.
- On resubmit, prominently mark "resubmitted at <time>" and link the prior reviewer message
  in the log.

### 3. Internal notes vs applicant-facing message are separate fields

Distinctly labelled, never merged (avoids leaking internal commentary). Same model split the
base spec already enforces (`ApplicationNote` vs the message on
`ApplicationStateTransition`); this surfaces them as two clearly distinct UI affordances.

### 4. Approval ≠ enrolment — in-context hand-off

The approved-application screen exposes an "Enrol this learner" deep-link into the existing
cohort + `UserCourseRegistration` flow with the user pre-filled. Approving never auto-creates
a registration. (Because admin/cohort enrolment bypasses the access backend, the approved
learner gets in cleanly.) This is the same hand-off the base spec ships as an admin link,
re-homed into the review screen.

---

## Permissions (unchanged from base spec)

- Model permissions `view_application`, `change_application` on `CourseApplication`, granted
  object-level via `django-guardian` (`assign_perm`), mirroring the cohort pattern
  (`role_based_permissions/utils.py:179`). State-changing transitions delegate to
  `user.has_perm("change_application", instance)`.
- Site isolation is automatic via `SiteAwareModel` — Site A reviewers never see Site B
  applications.
- The win over the base spec: reviewers no longer need `is_staff` / admin access — they
  review entirely within `educator_interface`.

---

## Out of scope (same deferrals as the base spec)

No bulk approve/reject; no multi-reviewer assignment / rubric / score review; no email
notifications (the `application_state_changed` signal remains the seam). Django/Unfold admin
may still expose the models read-mostly for support.

---

## Relationship to `application-forms`

`application-forms` (`spec_dd/0. drafts/application-forms`) §5 adds the applicant's
**answers + inline document previews** to "the single-application review screen's main area".
That screen is defined **here**. Whichever of these two follow-ups lands second renders the
answers/documents inside this review screen; until then, answers/documents are viewable on the
base spec's admin review surface. The two specs are independent and can ship in either order.

---

## Seams already in place (from `applying-for-courses`)

- `CourseApplication` + the full `django-fsm-2` state machine, with
  `get_available_user_state_transitions` driving available actions (never a hardcoded
  state→button map).
- `ApplicationNote` (staff-only internal notes) and `ApplicationStateTransition` (audit log +
  applicant-visible message) already structurally distinct.
- `view_application` / `change_application` guardian permissions and site isolation already in
  place; the admin review surface already consumes exactly this machinery.
- The "enrol this learner" hand-off already exists as an admin link; this re-homes it.

## Structure-review edges introduced here

- **`educator_interface → course_applications`** (review UI reads/actions
  `CourseApplication`). The base spec deliberately avoids this edge by keeping review in
  `course_applications`' own `admin.py`; this spec introduces it intentionally. Flag for
  `/plan_structure_review`.
