---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html
  - freedom_ls/learner_interface/templates/learner_interface/course_topic.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_status_label.html
requires_settings_change: true
changed_settings:
  - DEADLINE_POLICY_DEFAULTS  # hard if you set it: three new keys; freedom_ls_deadlines.E001 enforces them at boot
  - NOTIFICATION_CATEGORIES  # optional: three new FLS categories
  - WEBHOOK_EVENT_TYPES  # optional: three new FLS event types
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: deadlines-3-extensions-and-pause

## Breaking changes

- **If your settings define `DEADLINE_POLICY_DEFAULTS`, it must now name nine keys.** The three
  new ones are `learners_may_pause` (bool), `max_pauses` and `max_pause_days` (non-negative
  ints, 0 means no limit). `freedom_ls_deadlines.E001` fails at boot until they are there. A
  project that never set `DEADLINE_POLICY_DEFAULTS` gets the FLS default and needs nothing.
- **A paused learner loses content access.** `DeadlineEnforcingBackend`
  (`freedom_ls.course_access.backends`) checks for an open `CoursePause` before it checks the
  time limit, and withdraws content access from whatever decision your `COURSE_ACCESS_BACKEND`
  returned. A paused learner never reads as "access ended": the pause stops the clock.
- **`CourseAccessDecision` has two new fields**, `paused_at` and `planned_resume_at`. Both
  default to `None`, so backends that build decisions keep working.
- **`ResolvedDeadlinePolicy` has three new fields**, `learners_may_pause`, `max_pauses` and
  `max_pause_days`, with defaults (`False`, `0`, `0`). A custom `DEADLINE_POLICY` subclass of
  `freedom_ls.deadlines.policy.DeadlinePolicy` that builds `ResolvedDeadlinePolicy` itself keeps
  working and gets those defaults.
- **Deadlines read through the resolver now include pauses and extensions.**
  `freedom_ls.deadlines.resolver.course_deadlines` and `course_deadlines_for` move each unmet
  deadline and the course time limit forward by the whole days a learner was paused, plus any
  `DeadlineExtension` days. Code of yours that reads these sees the moved dates. Both functions
  take new keyword-only arguments (`now`, `items`, `pauses`) with defaults, so existing calls
  keep working.

## Manual steps

1. Run `manage.py migrate`. Three migrations in `freedom_ls_deadlines`:
   `0004_coursepause` adds `CoursePause`, `0005_deadlineextension` adds `DeadlineExtension`, and
   `0006_cohortcourseregistrationdeadlineconfig_learners_may_pause_and_more` adds
   `learners_may_pause`, `max_pauses` and `max_pause_days` to the six deadline policy tables.
2. If you set `DEADLINE_POLICY_DEFAULTS`, add the three new keys, then run `manage.py check`:

   ```python
   DEADLINE_POLICY_DEFAULTS = {
       # ...your existing six keys...
       "learners_may_pause": False,
       "max_pauses": 0,
       "max_pause_days": 0,
   }
   ```

3. Review your template overrides. If you override any template in `changed_template_paths`,
   carry the FLS changes into your copy. The dashboard card, all-courses row, status eyebrow and
   status label have a `paused` state ("Paused until <date>" or "Paused") and hide Continue and
   next-up while paused. The course detail page shows a paused callout. The outline shows a
   "Paused" chip on unfinished items. The topic, form and form-complete pages hide Next, Retry and
   Continue for a paused learner. The new semantic icon `paused` is mapped in every built-in icon
   set; a `FREEDOM_LS_ICON_OVERRIDES` entry for it is optional.
4. Optional: if your settings define `NOTIFICATION_CATEGORIES` or `WEBHOOK_EVENT_TYPES` as your
   own list, add the new FLS entries to opt in: notification categories `course.paused`,
   `course.resumed` and `deadline.extended` (from
   `freedom_ls.base.notification_categories.FLS_NOTIFICATION_CATEGORIES`), and the webhook event
   types of the same names (from `freedom_ls.base.webhook_event_types.FLS_WEBHOOK_EVENT_TYPES`).
   An FLS notification category left out of your list is skipped, not an error.
5. Nothing else to do for staff. The `CourseProgress` admin page gains "Pause course", "Resume
   course" and "Extend deadline" actions, and pauses and extensions are written to the audit log.
