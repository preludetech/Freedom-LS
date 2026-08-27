---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/course_finish.html
  - freedom_ls/learner_interface/templates/learner_interface/course_topic.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/delete_confirmation.html
  - freedom_ls/reports/templates/reports/partials/attention_entry.html
  - freedom_ls/reports/templates/reports/partials/contents.html
  - freedom_ls/reports/templates/reports/partials/learner_detail.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: better_course_progress_tracking

Progress is no longer keyed on the `User`. A `CourseProgress` row is now one learner's pass through
one course, minted by the registration that granted access, and it owns the item progress beneath
it. Every read path that used to ask "what has this user done" now asks a course progress record.

## Breaking changes

### The progress tables are rebuilt, and no progress data survives

`learner_progress`'s migration history was reset: `0002` and `0003` were deleted and `0001_initial`
regenerated against the new models. There is no data migration and no backfill — progress rows are
dropped, not converted. A project that has already applied the old `learner_progress` migrations
cannot migrate forward; it has to drop the app's tables and its `django_migrations` rows and migrate
again (see Manual steps). This is a pre-production change and assumes no production progress data.

Existing registrations are untouched and are not backfilled with records. A registration saved
before the upgrade gets its record the first time the learner opens the course.

### Model changes

- `CourseProgress` has no `user`. It carries `learner` (FK to `learner_management.Learner`), and
  exactly one of `learner_registration` / `cohort_registration`, enforced by the
  `course_progress_has_exactly_one_grant` check constraint. `user.course_progress` and
  `user.topic_progress` are gone; the reverse accessors are now
  `learner.course_progress_records`, `registration.course_progress_records`.
- `CourseProgress.start_time` is split. `created_at` is when the registration minted the record;
  `started_at` is when the learner first opened the course and is nullable.
  `last_accessed_time` is now nullable and is stamped only by opening an item, not by submitting an
  attempt.
- The `last_accessed_content_type` / `last_accessed_object_id` generic foreign key is replaced by
  `last_accessed_item`, an FK to `content_engine.ContentCollectionItem`.
- `unique_together = ("user", "course")` and `("user", "topic")` are gone. The new keys are
  `UNIQUE(learner_registration, learner)`, `UNIQUE(cohort_registration, learner)` and, on
  `TopicProgress`, `UNIQUE(course_progress, collection_item)`. One learner and one course can now
  hold more than one record — one per grant.
- `TopicProgress` hangs off `course_progress` and `collection_item` instead of `(user, topic)`.
- New model `learner_progress.CourseFormAttempt` binds a `form_engine.FormProgress` to a record and
  the placement it was sat at. `FormProgress` itself stays course-agnostic; its `form` FK moved from
  `CASCADE` to `PROTECT` (`form_engine` migration `0003`).

### Deleting registrations, cohorts and content now raises `ProtectedError`

Both grant FKs, plus `CourseProgress.course` and `TopicProgress.topic`, are `PROTECT`. Once a
registration has granted a record, deleting the registration — or the `Cohort` or `Course` that
cascades to it — fails. Deactivation (`is_active = False`) is the supported removal, and a
deactivated registration keeps its record and its progress. Any downstream admin action, management
command or cleanup script that deletes these objects needs to deactivate instead, or clear progress
first with `manage.py danger_clear_all_course_progress`.

`panel_framework.DeleteAction` catches `ProtectedError` on both the render and the submit path and
shows a message instead of a 500. Override `get_blocked_reason(instance, error)` to word it for your
own models.

### Records are minted by signals, so bulk writes need an explicit call

`learner_progress.signals` mints records on `post_save` of `LearnerCourseRegistration`,
`CohortCourseRegistration` and `CohortMembership`, deferred to `transaction.on_commit`.
`bulk_create` does not fire `post_save`: code that creates registrations in bulk must call
`ensure_course_progress_record()` or `ensure_course_progress_records_for_cohort_registration()`
from `freedom_ls.learner_progress.utils` itself. The same applies to percentages — a completion
written by `queryset.update()`, `bulk_create()` or `bulk_update()` must be followed by
`recalculate_progress_percentage(record)` from `freedom_ls.learner_progress.signals`.

### Python API

Removed or renamed:

| Was | Now |
| --- | --- |
| `learner_management.utils.calculate_course_progress_percentage(course, completed_topic_ids, completed_form_ids)` | `calculate_course_progress_percentage(course, completed_collection_item_ids)` |
| `form_engine.queries.completed_form_ids_by_user()` | `learner_progress.queries.completed_form_item_ids_by_course_progress()` / `completed_form_item_ids()` |
| `FormProgress.get_latest_incomplete()` / `.get_or_create_incomplete()` / `.finalise_stale_incomplete()` classmethods | functions in `learner_progress.attempts` |
| `learner_interface.utils.unpassed_forms()` / `UnpassedForm` | `outstanding_items()` / `OutstandingItem` |
| `reports.gather.build_wrong_answers_by_user_quiz()` | `build_wrong_answers_by_learner_quiz()` |
| `reports.report_data.LearnerRow/SummaryRow/LearnerDetail.user_id: int` | `.learner_id: UUID` |

Added: `learner_management.queries.learner_for_course()` (returns a `ResolvedRegistration` named
tuple of `.learner` and `.registration`), `learner_progress.queries.course_progress_for()` and
`course_progress_by_course_for()`, and `Course` / `CoursePart.collection_items()`,
`collection_items_flat()`, `viewable_collection_items()`. `children()`, `children_flat()` and
`viewable_items()` keep their behaviour and now derive from the collection-item accessors.

Test factories changed shape: `CourseProgressFactory` takes `learner=` rather than `user=` and
builds an individual registration by default, `TopicProgressFactory` takes `course_progress=`, the
new `CourseFormAttemptFactory` builds both halves of an attempt, and the `sit_quiz` fixture takes a
course progress record instead of a user.

### Behaviour changes visible to learners

- A course completes only when every item in it is finished. Previously only a sat-and-failed quiz
  withheld completion, so an item the learner never opened could not stop a course being marked
  complete — and firing `course.completed`. It now does.
- The progress percentage counts placements, not distinct content. A course that places the same
  topic or quiz twice has two items to complete, which is what the course outline already showed.

### Webhook payloads

`course.completed` and `course.registered` both gain `organisation_id` and `course_progress_id`.
`course.registered` also moved out of `LearnerCourseRegistration.save()` into a receiver deferred to
transaction commit, so consumers now see it after the registration commits rather than mid-save. It
still fires only for individual registrations; cohort fan-out mints records without announcing.

### Templates

Context names changed in the templates listed in the frontmatter:

- `course_finish.html` — `unpassed_forms` is now `outstanding_items`, whose entries expose
  `.content`, `.url`, `.is_retry`, `.is_quiz` and `.is_form`. The `data-testid` changed from
  `unpassed-forms` to `outstanding-items`, and the "Started" row reads `course_progress.started_at`
  (nullable) rather than `course_progress.start_time`.
- `course_topic.html` — the completion form is gated on a new `can_record_progress` flag, for a
  learner viewing a course no registration grants them.
- Report partials — the learner anchor id is built from `learner.learner_id`, not `learner.user_id`.

## Manual steps

1. **Rebuild the `learner_progress` tables.** Nothing preserves progress data, so on a development
   database the simplest route is to clear it and migrate from scratch. On a database you want to
   keep the rest of: drop the `freedom_ls_learner_progress_*` tables, delete the
   `django_migrations` rows for `freedom_ls_learner_progress`, then run
   `uv run manage.py migrate`.
2. **Run `uv run manage.py migrate`** — `form_engine` also ships `0003_alter_formprogress_form`.
3. **Re-apply your customisations** to the templates listed in `changed_template_paths`, using the
   context-name changes above.
4. **Update code that reads progress.** Anything filtering `CourseProgress`/`TopicProgress` on
   `user`, reading `start_time`, or calling one of the removed functions in the table above.
5. **Update code that deletes registrations, cohorts or courses** to deactivate instead, or to
   handle `ProtectedError`.
6. **Update code that creates registrations in bulk** to call `ensure_course_progress_record()` or
   `ensure_course_progress_records_for_cohort_registration()`.
7. **Check webhook consumers** that assert on the exact payload shape of `course.completed` or
   `course.registered`.
