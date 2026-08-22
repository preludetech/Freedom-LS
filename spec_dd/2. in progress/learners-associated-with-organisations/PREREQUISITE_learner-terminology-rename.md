# Prerequisite: `learner-terminology-rename`

**Added by the `learner-terminology-rename` work. This spec's own prose is untouched — read this
file alongside it, not instead of it.**

## Why you are reading this

This spec introduces a model called **`Learner`**. Its open-question section punts the terminology
decision upstream. That decision has now been made and implemented:
`spec_dd/2. in progress/learner-terminology-rename`.

**That rename is this spec's hard prerequisite.** Without it, this spec files a model named
`Learner` inside an app named `student_management` — which is exactly the incoherence the rename
exists to remove.

## What changed under you

The three apps are renamed. Anything in this spec's research or plan that names the old paths is
now stale:

| Old | New |
| --- | --- |
| `freedom_ls.student_management` | `freedom_ls.learner_management` |
| `freedom_ls.student_progress` | `freedom_ls.learner_progress` |
| `freedom_ls.student_interface` | `freedom_ls.learner_interface` |
| app label `freedom_ls_student_management` | `freedom_ls_learner_management` |
| app label `freedom_ls_student_progress` | `freedom_ls_learner_progress` |
| app label `freedom_ls_student_interface` | `freedom_ls_learner_interface` |
| `StudentDeadline` | `LearnerDeadline` |
| `StudentDeadline.student_course_registration` | `LearnerDeadline.learner_course_registration` |
| role key `"student"` | `"learner"` |
| URL namespace `student_interface:` | `learner_interface:` |

The full old→new table, including permission strings, template paths and table names, is in
`spec_dd/2. in progress/learner-terminology-rename/upgrade_notes.md`.

## What this means for the work here

- The new `Learner` model belongs in **`freedom_ls/learner_management/`**, under the app label
  `freedom_ls_learner_management`. Its permissions will therefore be
  `freedom_ls_learner_management.view_learner` and friends.
- **`view_learner` / `add_learner` / `change_learner` / `delete_learner` do not exist yet.** The
  rename *deleted* the four dead `*_student` codenames rather than translating them, precisely
  because they named a model that did not exist. Once this spec creates a real `Learner` model,
  Django generates the four real codenames — and this spec owns adding them back to
  `role_based_permissions/registry.py` and to whichever roles should hold them. Do not assume
  they are already wired up.
- Names that deliberately **did not** change, and must not be renamed here either:
  `UserCourseRegistration`, `UserCohortDeadlineOverride`, `CohortMembership`, and the webhook
  payload keys `user_id` / `user_email`.
- Re-read this spec's research files with the table above applied before trusting any path,
  import or label they quote.

## Ordering

Land `learner-terminology-rename` first. If this spec lands first instead, it acquires rename debt
in every file it touches, and the rename's own sweep will then have to reason about a brand-new
`Learner` model mid-flight.
