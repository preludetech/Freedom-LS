# Idea: a registered learner on an application-gated course gets the free-course copy, and their application stays in "Your applications"

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (APP-4, LEARN-4, APP-5).

### Free copy for a registered learner

1. A learner has a submitted application for an application-gated course, e.g.
   `rpc-fixed-wing-aeroplane`.
2. An operator registers them (`learner_management.learner_actions.register_for_course`). With no
   review workflow yet, that is how access is granted.
3. The learner opens `/courses/rpc-fixed-wing-aeroplane/detail/`.

Expected: copy that matches the course. It is gated and priced ("Price on request"), or simply
"You're enrolled".

Actual: the hero reads "ENROLMENT Free · open" next to "PRICE Price on request", and the side
panel reads "Free · open to everyone / One click. No credit card." above "Start course". It happens on
every gated course once the learner is registered. The decision also carries
`is_accessible_for_free=True`, which feeds the free badge and the page's JSON-LD.

The same "One click. No credit card." line shows on a free course to a learner who has already
finished it, above "Review course". Nobody past the funnel needs acquisition copy.

### Applications panel keeps registered courses

Same learner, plus a draft application for `rpc-instructor-rating` on which they are also
registered. Open the dashboard.

Expected: once the learner is registered, the application leaves the panel or shows that it was
accepted.

Actual: "RPC Fixed-Wing (Aeroplane): Pending review" and "RPC Instructor Rating: Incomplete,
Continue application", while the same courses sit in "In progress" as REGISTERED. "Continue
application" still opens the editable form.

## Cause

`ApplicationCourseAccessBackend._ungated_decision`
(`freedom_ls/course_applications/backends.py:157`, the delegation at `:177-181`) hands every
registered learner to `super().get_access`. That reaches `_free_access_decision`
(`freedom_ls/course_access/backends.py:231`), whose registered branch (`:238-250`) always sets
`_FREE_ENROLMENT_SUMMARY`, `_FREE_ACQUISITION_HEADING` and `_FREE_ACQUISITION_SUBTEXT`
(`:226-228`) and leaves `is_accessible_for_free` at its default `True`. The comment on
`CourseAccessDecision` (`course_access/backends.py:57-59`) says a gated course must not inherit
the free copy. This path does.

The panel comes from `get_active_applications` (`course_applications/queries.py:43`), which
returns all of the user's applications. Its docstring says it will narrow once
approve/reject exist. Until then, registration is the grant, and the panel contradicts it.
Both `get_dashboard_contributions` and `get_dashboard_contributions_for_request`
(`course_applications/backends.py:249-298`) use it.

## Suggested fix

- In the registered branch, return post-funnel copy: heading "You're enrolled", no subtext, and
  keep the course's real enrolment summary and `is_accessible_for_free`. The free backend's
  registered branch should not offer "One click. No credit card." either.
- Exclude applications whose course the user is registered on from the signed-in panel query, or
  show them as accepted. Anonymous sessions can't be registered, so their query needs no change.

## Downstream workaround

`apps/project_setup/course_access.py` subclasses `ApplicationCourseAccessBackend`. It replaces
the copy on any decision with `can_access_content` and filters registered courses out of the
panel. `COURSE_ACCESS_BACKEND` in `config/settings_base.py` points at it.
