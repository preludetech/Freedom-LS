# Research: reference implementations of per-learner course progress APIs

Extends `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md` (auth, scoping, general pagination are not repeated). Method: one live fetch (Canvas) confirmed; everything else is from knowledge of public docs and is marked (verify). Edx completion-aggregator and Moodle doc URLs returned 404 on fetch, so those entries are unconfirmed.

## Per-system findings

| System | Endpoint shape | Progress fields | Incremental sync | Enrolment / cohort link | Pagination |
|---|---|---|---|---|---|
| Canvas | `GET /api/v1/courses/:course_id/users/:user_id/progress` (one learner, one course; confirmed). Enrollments: `GET /api/v1/courses/:id/enrollments` | `requirement_count`, `requirement_completed_count`, `next_requirement_url`, `completed_at` (null until done). Enrollment object adds `created_at`, `updated_at`, `last_activity_at`, `total_activity_time`, `grades.current_score` (verify) | None on progress. Enrollments expose `updated_at` but the list filter is limited (verify); Data Services / Live Events cover change feeds | Enrollment carries `course_id`, `course_section_id`, `user_id`, `type`, `enrollment_state` | `Link` header, `per_page` |
| Moodle | `core_completion_get_course_completion_status(courseid, userid)` (verify) | Returns `completionstatus` with `completed` (bool), `aggregation`, `completions[]` per criterion each with `complete`, plus `timecompleted` per criterion. No percent; percent is derived client side. `core_completion_get_activities_completion_status` is per activity | None; per-user per-course call, caller loops | Course and user ids passed in; no enrolment object returned | None (one call per pair) |
| Open edX | Completion aggregator REST: `/completion-aggregator/v1/course/{course_key}/` (all learners, staff) and `/completion-aggregator/v1/user/{username}/` (verify). Grades: `/api/grades/v1/courses/{course_id}/` | `username`, `course_key`, `completion: {earned, possible, percent}`, `mean`; with `?requested_fields=` for block level (verify). Grades API: `percent`, `letter_grade`, `passed` | `last_modified` filtering is not offered on the list endpoint as far as known (verify); consumers re-pull | `course_key` plus `username`; enrolment lives in the separate enrollment API (`mode`, `is_active`, `created`) | DRF page-number (`page`, `page_size`) with `next`/`previous`/`count` |
| TalentLMS | `GET /api/v1/users/id:{id}` returns courses array; `GET /api/v1/getuserstatusincourse/user_id:X,course_id:Y` (verify) | `completion_status`, `completion_percentage`, `completed_on`, `enrolled_on`, `last_updated_on` (verify), `total_time` | None; fixed per-user lookups | Course status is nested inside the user | None |
| LearnDash REST (WP) | `/wp-json/ldlms/v2/users/{id}/course-progress` and `/ldlms/v2/users/{id}/courses` (verify) | `progress_status` (`not-started`/`in-progress`/`completed`), `last_step`, `steps_total`, `steps_completed`, `date_started`, `date_completed` | WP `modified_after` / `after` params on some collections (verify) | Per-user course list; groups via separate endpoint | WP `page`, `per_page`, `X-WP-Total` headers |
| LifterLMS REST | `/wp-json/llms/v1/students/{id}/progress/{post_id}` and `/students/{id}/enrollments` (verify) | `progress` (percent number), `status` | WP generic filters | `/enrollments` objects: `post_id`, `status`, `date_created`, `date_updated` (verify) | WP `page`, `per_page`, headers |
| Thinkific | `GET /api/public/v1/enrollments` | `percentage_completed` (0 to 1 decimal in docs; verify), `completed` (bool), `started_at`, `completed_at`, `activated_at`, `updated_at`, `expiry_date`, `is_free_trial` | `query[updated_after]`, `query[created_after]` style filters (verify); webhooks | Enrollment is the unit: `user_id`, `user_email`, `user_name`, `course_id`, `course_name`. Closest match to the FLS row | `page`, `limit`, `meta.pagination` |
| Teachable | `GET /v1/courses/{id}/enrollments`, `GET /v1/courses/{id}/progress?user_id=` (verify) | `percent_complete`, `enrolled_at`, `completed_at`, `has_full_access` | Limited | `user_id`, `course_id` | `page`, `per`, `meta` |
| Docebo | `GET /learn/v1/enrollments` (verify) | `status` (`enrolled`/`in_progress`/`completed`), `enrollment_date`, `completion_date`, `score`, `date_last_updated` (verify), `date_begin_validity` | `date_last_updated` style filter and sort available on `/learn/v1/enrollments` (verify); strongest of the LMSes | `course_id`, `user_id`, `session_id`, group via `enrollment_type` | `page`, `page_size`, `has_more_data` |
| xAPI LRS (`GET /statements`) | Statements, not rows | Progress as `result.completion`/`result.extensions` | `since` and `until` filter on the LRS-assigned `stored` time (not the actor's `timestamp`); `ascending=true` | `context.registration` UUID links statements to one enrolment | `more` URL token, `limit` |

## Patterns worth borrowing

1. **Enrolment is the unit.** Thinkific, Teachable, Docebo and LifterLMS all make the enrolment (learner x course) the row, with user and course ids and often user email/name inline. This matches one row per `CourseProgress`. Thinkific's flattened `user_email`, `user_name`, `course_name` supports FLS flattening.
2. **Status derived from timestamps.** Thinkific/LearnDash expose both a numeric percent and a status or `completed` flag next to `started_at` / `completed_at`. A null `completed_at` plus `started_at` gives the lead-monitor states (not started, in progress, finished) without extra fields.
3. **Percent representation varies** (0 to 1 decimal in Thinkific, 0 to 100 elsewhere, Open edX also `earned`/`possible`). Document unit and type explicitly; FLS integer 0 to 100 is fine.
4. **Incremental sync is rare on progress endpoints.** Only Docebo, Thinkific and Canvas enrollments expose any modified/updated filter. xAPI is the model for doing it right: `since` filters on the server-assigned `stored` time, not on a client-controlled timestamp. This is exactly the FLS reasoning: `last_accessed_time` is writer-controlled, so a server `updated_at` is the honest key.
5. **Registration identifier link.** xAPI `context.registration` and Open edX `course_key`+`username` show the link is by id. Nobody encodes cohort vs individual in the progress row; FLS `kind` is novel and should be a simple enum string.

## How Open edX keeps a modified timestamp under background recalculation (verify)

The completion aggregator stores `Aggregator` rows (`user`, `course_key`, `aggregation_name`, `block_key`, `earned`, `possible`, `percent`, plus `last_modified` from a `TimeStampedModel`). Recalculation is driven by Celery tasks (`update_aggregators`, `cohort`/`course` batch tasks) triggered by completion signals and by a management command (`reaggregate`/`migrate_batch`-style). The aggregators are written via `Aggregator.objects.submit_completion()` / `update_or_create`-style paths that go through `save()`, so `modified` moves; it also uses `bulk_update` for stale cleanup in places and there `modified` has to be set by hand (verify). Lesson: the dangerous path is bulk writes; every reference that is correct either routes through `save()`/`update_or_create` or sets the timestamp explicitly.

## Django libraries: `updated_at` plus bulk updates

- **django-model-utils** `TimeStampedModel`: `created = AutoCreatedField`, `modified = AutoLastModifiedField`. Its `save()` (recent versions) adds `modified` to `update_fields` when `update_fields` is passed, so partial saves still move it. `QuerySet.update()` and `bulk_update()` do not call `save()`/`pre_save` for the timestamp, so they leave `modified` stale; docs/issues say to include it manually. https://django-model-utils.readthedocs.io/en/latest/models.html#timestampedmodel
- **django-extensions** `TimeStampedModel`: `created = CreationDateTimeField`, `modified = ModificationDateTimeField`; `update_modified` attribute lets callers opt out on a save; same bulk caveat. https://django-extensions.readthedocs.io/en/latest/model_extensions.html
- **Django core**: `DateTimeField(auto_now=True)` is set in `pre_save`, so it works on `save()` and `bulk_update()` is documented as not calling `save()`, but `bulk_update` does call field `pre_save` (Django 4.x+: `bulk_update` does not apply `auto_now` unless the field is in `fields`; verify against current Django 6 docs). `QuerySet.update()` never applies `auto_now`. https://docs.djangoproject.com/en/stable/ref/models/fields/#django.db.models.DateField.auto_now and https://docs.djangoproject.com/en/stable/ref/models/querysets/#bulk-update
- Both libraries name the field `created`/`modified`; neither names collide-aware. FLS `created_at` on this model already means registration date, so a fresh `updated_at` field is lower risk than importing the mixin. (FLS-side check belongs to the spec.)
- Common safe patterns: (a) funnel all writes through a manager method that sets the timestamp; (b) pass `updated_at=now()` in every `.update()`; (c) include `updated_at` in `bulk_update(fields=[...])`; (d) a test that fails if a writer leaves it stale.

## What this means for the idea

- One row per enrolment with inline user and course names is the established shape (Thinkific is nearest); the idea's flattening is conventional.
- Keep `started_at`/`completed_at` null semantics documented; a script derives not-started / in-progress / finished from them plus percent. Consider whether the row needs an explicit status field (LearnDash, Docebo have one); the idea does not list one, and it is derivable, so default to leaving it out.
- A server-set `updated_at` is the right sync key (xAPI `stored` precedent); do not key `updated_since` on `last_accessed_time`.
- The risk is bulk writes: `QuerySet.update()` and possibly `bulk_update()` skip `auto_now`. The spec must audit every writer of `CourseProgress.progress_percentage`, and pick a pattern (explicit field in every update, or one service function) plus a test that fails if a writer leaves it stale.
- Do not import `TimeStampedModel` blindly: `modified`/`created` naming and the existing `created_at` meaning clash; a single added `updated_at` field is the lighter choice.
- State the percent unit (integer 0 to 100) in the API docs, since references disagree.
- `kind` for registration type has no precedent; keep it a simple two-value string shared with child 4.
- Backfill to the latest existing timestamp is sound; there is no reference that does better.

## References

- Canvas course progress (fetched): https://canvas.instructure.com/doc/api/courses.html ; enrollments: https://canvas.instructure.com/doc/api/enrollments.html
- Moodle: https://moodledev.io/docs/apis/subsystems/external ; function list https://docs.moodle.org/dev/Web_service_API_functions
- Open edX completion aggregator: https://github.com/openedx/completion-aggregator ; grades API https://docs.openedx.org/en/latest/developers/references/api_docs.html
- TalentLMS: https://www.talentlms.com/pages/docs/TalentLMS-API-Documentation.pdf
- LearnDash REST: https://developers.learndash.com/rest-api/v2/
- LifterLMS REST: https://gocodebox.github.io/lifterlms-rest/
- Thinkific: https://developers.thinkific.com/api/api-documentation/
- Teachable: https://docs.teachable.com/reference
- Docebo: https://help.docebo.com/hc/en-us/articles/360020255519 (API browser per tenant)
- xAPI spec (statements `since`, `stored`, `registration`): https://github.com/adlnet/xAPI-Spec/blob/master/xAPI-Communication.md
- django-model-utils: https://django-model-utils.readthedocs.io/
- django-extensions: https://django-extensions.readthedocs.io/

status: ok · reason: complete; only Canvas progress endpoint fetched live, other details from knowledge and marked (verify)
