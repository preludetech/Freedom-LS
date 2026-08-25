# Learner Tracking

_Last updated: 2026-08-21_

## Summary

- FLS records per-item completion for every topic and form a learner interacts with, plus a per-course progress percentage and a resume pointer. This is the closest built-in equivalent to an activity log.
- Quiz attempts store per-question answers, scores, and pass/fail. Attempts are unlimited and every attempt is kept as a separate record.
- Course progress percentage recalculates automatically when an item is completed. A quiz only counts toward it once the learner has passed — a failed attempt does not complete the item. See [progress percentage](#progress-percentage).
- Administrators see all progress data in the Django admin. Educators see completion and quiz data for their cohorts in the [educator interface](./educator-interface.md).
- **Not built:** time-on-task duration and xAPI. There is still no CSV or API export of scores or grades, though a staff user can generate a per-cohort PDF report holding completion, quiz scores, and per-question answers — see [cohort reports](./reports.md). See [roadmap](./roadmap.md).

## What Is Recorded

**Per topic** — one record per learner per topic, created when they first open it. It holds when they started, when they last opened it, and when they marked it done.

**Per form or quiz attempt** — one record per attempt. It holds when the attempt started, when it was last saved (forms can span multiple pages and be resumed), when it was submitted, and the raw score data the course's scoring strategy uses to produce a score and a pass/fail result. Because each attempt is its own record, a learner's full attempt history is retained.

**Per question** — the learner's selected options or free-text answer, stored against the attempt it belongs to.

**Per course** — one record per learner per course, created when they register. It holds start time, last-accessed time, completion time, the progress percentage, and a pointer to the item they last viewed, which is what the course player uses to resume them. Browsing a course without registering leaves no tracking record.

None of this is scoped by organisation. A learner can hold a separate registration for the same course through more than one organisation — see [multi-tenancy and isolation](./multi-tenancy-and-isolation.md#organisations) — but progress tracks the learner and the course, not the registration: they still have one record per topic, one course record, and one shared quiz-attempt history, however many organisations they are registered through.

## Progress Percentage

The percentage is completed items divided by total items in the course, rounded to a whole number. It recalculates automatically the first time an item is marked complete.

Items are counted by where they sit in the course, not by the content behind them. A course that places the same topic or quiz at two positions has two items to complete, and finishing one of them counts once — which is also what the course outline shows.

A topic or a non-quiz form counts as complete as soon as the learner completes it. A quiz counts as complete only if the learner's latest attempt passed it: a failed attempt leaves the quiz — and so the course — short of complete, however many times it has been attempted. A quiz with no pass mark configured has no bar to clear and counts as complete on completion, the same as a survey.

Bulk database updates that bypass the normal save path do not trigger recalculation. The `recalculate_progress_percentages` management command recomputes every course's percentage from scratch and exists for exactly this case. The pass-to-complete rule above is new, so an existing deployment must run this command once after upgrading or percentages calculated under the old rule stay stale; the upgrade notes carry the full procedure.

## Who Can Read Tracking Data

- **Administrators** — full read access to all progress and answer records in the Django admin, and can generate a [cohort progress report](./reports.md) for any cohort.
- **Educators** — completion status, quiz scores, and deadline information for learners in their cohorts, via the course-progress matrix. Which cohorts and learners an educator can reach this way is bounded by the organisation they are currently viewing as well as by their access grants. See [educator interface](./educator-interface.md#access-control). An educator with access to a cohort under either of those routes can also generate that cohort's [progress report](./reports.md), from the Django admin.
- **Learners** — their own progress, shown indirectly through course player status indicators, dashboard sections, and quiz feedback. There is no raw data export for learners.

## Limits

**No time-on-task.** Start and completion timestamps are recorded, but not elapsed time spent on an item.

**No machine-readable score or grade export.** There is no CSV, API, or other structured export of scores or grades; extraction for integration still requires a direct database query or a custom integration. A staff user can generate a [cohort progress report](./reports.md) covering completion, quiz scores, and per-question answers for a whole cohort, but it is a formatted document for reading, printing, and filing — not structured data.

**No xAPI / learning-record-store.** An xAPI integration exists only as a non-functional stub; see [roadmap](./roadmap.md).

**Legal consent is tracked separately** from learning activity — see [authentication](./authentication.md).
