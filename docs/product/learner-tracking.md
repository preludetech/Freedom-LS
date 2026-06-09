# Learner Tracking

_Last updated: 2026-06-09_

## Summary

- Freedom LS records per-item completion for every topic and form a learner interacts with, plus a per-course progress percentage and a resume pointer — this is the closest built-in equivalent to an activity log.
- Quiz attempts store per-question answers, scores, and pass/fail outcomes; multiple attempts are supported with each attempt saved as a separate record.
- Course progress percentage is recalculated automatically whenever an item is completed; a management command can recompute all percentages from scratch.
- All progress records are visible to administrators through the Django admin. Educators see completion data and quiz scores for their permissioned cohorts via the educator interface.
- **Limits:** no time-on-task duration is recorded; no score or grade export is available. The legal-consent audit trail is separate — see [authentication](./authentication.md).

## What Is Recorded

### `TopicProgress`

One record per user per topic. Created when a learner first opens a topic item.

| Field | Content |
|---|---|
| `start_time` | Set automatically when the record is created. |
| `last_accessed_time` | Updated automatically each time the record is saved. |
| `complete_time` | Set when the learner marks the topic as done. `None` while incomplete. |

There is one `TopicProgress` row per user+topic combination (unique constraint). No duration field exists; time-on-task is not recorded.

### `FormProgress`

One record per attempt per user per form. Multiple attempts are supported: each new attempt creates a new `FormProgress` row.

| Field | Content |
|---|---|
| `start_time` | Set when the form is started. |
| `last_updated_time` | Updated on each page save. |
| `completed_time` | Set on final submission. `None` while in progress. |
| `scores` | JSON field holding raw score data used by the scoring strategy. |

**Methods available on `FormProgress`:**

- `score()` — returns the numeric score.
- `passed()` — returns `True` / `False` based on the scoring strategy's pass threshold.
- `quiz_percentage()` — returns the percentage score for QUIZ-strategy forms.
- `get_incorrect_quiz_answers()` — returns the set of questions answered incorrectly (used for optional feedback display to the learner).

### `QuestionAnswer`

One row per question per `FormProgress`. Stores the learner's answer to each question within a form attempt.

| Field | Content |
|---|---|
| `selected_options` | Many-to-many to `QuestionOption`; used for multiple-choice questions. |
| `text_answer` | Free-text answer for open-response questions. |

### `CourseProgress`

One record per user per course. Created when the learner registers for a course.

| Field | Content |
|---|---|
| `start_time` | Set at registration. |
| `last_accessed_time` | Updated each time the learner opens a course item. |
| `completed_time` | Set when all items are complete. `None` while in progress. |
| `progress_percentage` | Integer (0–100). DB-indexed. Recalculated on each item completion. |
| `last_accessed_item` | `GenericForeignKey` to the most recently accessed item. Used by the course player to resume. |

`CourseProgress` is created only on explicit registration — browsing a course without registering leaves no tracking record.

## Progress Percentage Calculation

When a `TopicProgress` or `FormProgress` record transitions from incomplete to complete (i.e., when `complete_time` or `completed_time` is set for the first time), `update_course_progress_on_completion()` is called automatically via the model's `save()` signal path. This function recalculates `progress_percentage` for all courses that contain the completed item.

The percentage is the count of completed items divided by the total number of items in the course, expressed as an integer.

### `recalculate_progress_percentages` command

The management command `recalculate_progress_percentages` recomputes all `CourseProgress.progress_percentage` values from scratch. It is intended for use after bulk data changes or if percentages become inconsistent.

## Who Can Read Tracking Data

- **Administrators** have full read access to `FormProgress`, `TopicProgress`, `CourseProgress`, and `QuestionAnswer` via the Django admin. The admin also exposes `QuestionAnswer` as an inline within `FormProgress`.
- **Educators** can see completion status, quiz scores, and deadline information for students in their permissioned cohorts via the course-progress matrix in the educator interface. See [educator interface](./educator-interface.md).
- **Learners** see their own progress indirectly through the course player status indicators, dashboard sections, and quiz feedback. There is no raw data export for learners.

## Limits

**No time-on-task duration.** `TopicProgress` has `start_time` and `complete_time` but no duration field. The elapsed time a learner spent on any item is not recorded.

**No score or grade export.** There is no built-in export (CSV, API, or otherwise) of scores or grades. Administrators can view records in the Django admin; extraction requires a direct database query or a custom integration.

**No xAPI / learning-record-store.** An xAPI integration is a placeholder in the codebase (all model code is commented out; the app is not in `INSTALLED_APPS`). See [roadmap](./roadmap.md).

**Legal-consent audit trail is separate.** Consent to terms and privacy documents is recorded in `LegalConsent`, which is owned by the authentication system. See [authentication](./authentication.md) for the full description; it is not restated here.
