# Critical Security Fixes — Educator Interface Authorisation

Found while fact-checking `docs/product/` against the code. The educator interface grants
object-level permissions but only enforces them in two places, so most of the interface is
readable by any logged-in user.

This supersedes the draft `spec_dd/0. drafts/educator-idor-fixes/`, whose two bugs are
items 1 and 2 below.

## Why this is critical

Any authenticated user on a site — including an ordinary learner — can navigate directly to
an educator URL and read:

- **Any cohort's detail page and course-progress matrix.** Student names, email addresses,
  completion state, quiz scores, and deadlines for people they have no relationship to.
- **Any individual user's detail page.**
- **Every course on the site**, including courses authored as `hidden`, which learners
  cannot otherwise discover.

The interface is mounted at `educator/` (`config/urls.py:60`), so the URLs are guessable
once one identifier is known, and cohort detail links leak identifiers.

This is learner personal data and learning records. POPIA treats both as personal
information.

## The three defects

**1. Detail views fetch by identifier with no permission check.**
`freedom_ls/panel_framework/views.py:184` — `ListViewConfig.get_instance_view` does a bare
`get_object_or_404(cls.model, pk=pk)`. All three educator detail views resolve through it:
`CohortInstanceView`, `UserInstanceView`, `CourseInstanceView`
(`freedom_ls/educator_interface/views.py:713`, `:200`, `:1015`).

**2. `CourseDataTable` has no permission filter.**
`freedom_ls/educator_interface/views.py:781` — the queryset is `Course.objects.all()`.
`CohortDataTable` (`:85`) and `UserDataTable` (`:126`) both filter through
`guardian.shortcuts.get_objects_for_user` with `view_cohort`; this one does not. Because
visibility filtering is deliberately learner-only, hidden courses are included.

**3. `@login_required` is the only gate on the interface.**
`freedom_ls/educator_interface/views.py:1037`. There is no check that the visitor is an
educator at all — no group, role, or "has any cohort grant" test. Even with 1 and 2 fixed,
every learner could still reach the interface shell and its empty listings.

## What is NOT broken

Worth recording so the fix does not churn code that is already correct:

- **Writes are permission-checked.** `CreateInstanceAction`, `EditAction`, and
  `DeleteAction` check `add_`/`change_`/`delete_` object permissions
  (`freedom_ls/panel_framework/actions.py:151`, `:208`, `:267`), and
  `panel_framework/views.py:334` enforces before executing. This is a read/disclosure
  defect, not a path to modifying or deleting data.
- **Site isolation holds.** Every query stays scoped to the request's site. The gap is
  within a single tenant, never across tenants.
- **Instance panels scope correctly.** Nested data tables are filtered to the parent
  instance via `Panel.get_filters()` (e.g. `UserCohortsPanel`,
  `educator_interface/views.py:196`), and `UserCohortsPanel` reuses the guardian-filtered
  `CohortDataTable`. Panels are not a separate hole.
- **Anonymous visitors cannot reach any of it.**

## Questions to resolve when specifying

- **Where does the fix belong?** A generic object-permission hook in `panel_framework`
  benefits every future panel consumer but changes a shared framework; a targeted fix in
  `educator_interface` is smaller but leaves the next panel consumer to rediscover the trap.
  The framework option is probably right given `panel_framework` exists to be reused — worth
  deciding deliberately rather than by default.
- **What permission should the Courses list filter on?** Courses have no per-object educator
  grant today. Options include deriving visible courses from the cohorts the educator can
  see, or introducing a `view_course` object permission. This decision has content-authoring
  consequences and should not be made incidentally.
- **How does this intersect `role_based_permissions`?** That app is installed and migrated,
  and its helpers already write the object permissions that are actually enforced. The fix
  should extend that model rather than build a parallel one. See `roadmap.md` for its
  current status.
- **Should the interface require an educator check at all, or is a permission-filtered
  interface that renders empty for a learner acceptable?** Defence in depth argues for both.

## Testing

Regression coverage should assert the negative case directly: a logged-in user with no
grant on a cohort gets a 403/404 from its detail URL, its progress matrix, each panel
endpoint, and the Courses list. QA data helpers already exist —
`qa_create_cohort_progress`, `qa_create_large_cohort`, `qa_create_empty_student_cohort`.

## Follow-on work

`docs/product/` currently documents this defect honestly in
`educator-interface.md#access-control`, `security-and-data-handling.md`, `roadmap.md`, and
the `README.md` up-front notes. All four must be updated when the fix lands.

Note also that the repository is public, so the defect is publicly described while it
remains unfixed.

## Out of scope

These have their own drafts and are not absorbed here:
`0. drafts/educator-interface-permission-checks/`,
`0. drafts/educator-interface-permission-config/`,
`0. drafts/CSP-rollout/`, `0. drafts/sentry-pii-scrubbing/`,
`0. drafts/encryption-at-rest/`.
