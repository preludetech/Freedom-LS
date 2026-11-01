---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/cotton/callout.html
  - freedom_ls/learner_interface/templates/learner_interface/_course_base.html
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/learner_interface/templates/learner_interface/course_item_closed.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_deadline_line.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/deadline_labels.html
requires_settings_change: true
changed_settings:
  - DEADLINE_POLICY  # optional: new, has a default; freedom_ls_deadlines.E002 checks it at boot
  - DEADLINE_POLICY_DEFAULTS  # optional: new, has a default; freedom_ls_deadlines.E001 checks it at boot
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: deadlines-2-consequence-policy

## Breaking changes

None with the default settings. A missed deadline still shows a "Missed deadline" chip, and
nothing closes or ends until a deadline policy row or a settings value turns it on.

Some changes reach your own code:

- **Every course-access backend is now wrapped in `DeadlineEnforcingBackend`**
  (`freedom_ls.course_access.backends`). `get_course_access_backend()` returns
  `VisibilityEnforcingBackend(DeadlineEnforcingBackend(<your COURSE_ACCESS_BACKEND>))`. When a
  learner's policy has `end_course_access` on and the course time limit plus the grace window has
  passed, the wrapper withdraws content access from whatever decision your backend returned. No
  data is written, so a later deadline override restores access straight away.
- **`CourseAccessDecision` has two new fields**, `access_ended_at` and `after_access_ended`. Both
  default to `None`, so backends that build decisions keep working.
- **`CourseAccessBackend` has a new method, `get_access_many(user=..., courses=...)`.** By default
  it calls `get_access` once per course. Override it only if your backend can answer for a whole
  list of courses more cheaply.
- **Warning and success callouts have darker text.** `<c-callout level="warning">` and
  `level="success"` now use `text-on-warning-light` and `text-on-success-light`, so the text is
  readable on the pale tint. The component also accepts a `class` attribute.

## Manual steps

1. Run `manage.py migrate`. Migration
   `freedom_ls_deadlines.0003_cohortcourseregistrationdeadlineconfig_and_more` adds six deadline
   policy tables: `SiteDeadlineConfig`, `OrganisationDeadlineConfig`, `CourseDeadlineConfig`,
   `CohortDeadlineConfig`, `CohortCourseRegistrationDeadlineConfig` and
   `LearnerCourseRegistrationDeadlineConfig`. They start empty.
2. Review your template overrides. If you override any template in `changed_template_paths`,
   carry the new FLS changes into your copy. `course_item_closed.html` (the player's closed-item
   notice) and `partials/deadline_labels.html` (the shared deadline, "Closes" and "Closed"
   labels) are new. The course card, course row, status eyebrow, course detail page and outline
   now show "Closed", "Access ends" and "Access ended", and they hide the "Missed deadline" chip
   when `mark_overdue` is off.
3. Optional: set a policy for the whole project in settings. `DEADLINE_POLICY_DEFAULTS` is the
   last layer and must name all six keys, with no `"inherit"`:

   ```python
   from datetime import timedelta

   DEADLINE_POLICY_DEFAULTS = {
       "mark_overdue": True,
       "close_items": False,
       "end_course_access": False,
       "notify_educators": False,
       "grace_window": timedelta(0),
       "after_access_ended": "outline_and_results",  # or "nothing"
   }
   ```

   If you set it, `manage.py check` validates it as `freedom_ls_deadlines.E001`.
   `DEADLINE_POLICY` (default `freedom_ls.deadlines.policy.LayeredDeadlinePolicy`) selects the
   policy class. A replacement must subclass `freedom_ls.deadlines.policy.DeadlinePolicy` and
   implement `resolve_for`. `freedom_ls_deadlines.E002` checks it at boot.
4. Optional: staff can now set the policy per site, organisation, course, cohort, cohort
   registration or learner registration through the six new admins under "Deadlines". The
   admin's `CourseProgress` page shows the effective policy and which layer set each value. To
   restore a learner whose access has ended, add a fixed-date (or day-count) "Course time limit"
   override on the existing deadline override inlines.
