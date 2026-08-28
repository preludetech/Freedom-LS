# Notes for other specs

Findings the pre-deploy structure sweep surfaced that belong to somebody else's spec. Recorded here so
they are not lost, and not built by the wrong cut.

## `content_snapshots`: its dependency boundary is stale

The idea requires "no imports from apps other than `content_engine`, `accounts`, and
`site_aware_models`", and also lists `Form`, `FormContent` and `FormQuestion` as in-scope content
models. Those three now live in `form_engine`, and the dependency graph runs `content_engine` to
`form_engine`, so `content_snapshots` cannot reach `Form` through `content_engine` at all. It needs
`form_engine` as an explicit dependency, and probably `content_base`, which both content apps already
share for `BaseContent`/`TitledContent`/`MarkdownContent`. Otherwise its form-content scope has to
shrink.

Separately, freezing `question_text` and `selected_option_texts` on `QuestionAnswer` at answer time is
not this spec's to own. `content_snapshots` snapshots authored content, and that question is about
what a learner's answer row should remember. It could supply the mechanism, a caller storing a
`snapshot_id` on `FormProgress` at completion, but nothing in its idea commits to that.

## The course-application review spec: reassess `on_delete`

`CourseApplication.course` is `CASCADE` and correct today. An application holds only `user`, `course`
and timestamps, so deleting the course discards a stale preference. Once review adds a decision state,
`ApplicationNote` and `ApplicationStateTransition`, deleting the course out from under an application
changes from discarding a preference to erasing a decision record. Reassess `on_delete` then.

## `xapi_implementation`: attempt identity already exists

Point the event table's registration/attempt concept at `CourseProgress.id` rather than re-deriving or
reinventing attempt identity. It is already emitted, since `course.registered` fires
`course_progress_id`. For form-shaped events, `CourseFormAttempt.course_progress_id` is the route.
xAPI's own `Context` has a standing `registration` UUID field, so the shapes line up.

## `student-communication`: the idea still uses a retired name

Its registration-scoped comms config is described against `UserCourseRegistration`, a name
`learner-terminology-rename` retired. The model is `LearnerCourseRegistration`. The
attach-to-one-of-two-registrations shape it wants is the same exactly-one-of-two-FKs pattern
`CourseProgress` already uses, constraint included. Worth copying rather than reinventing.

## `learner-management-actions`: the retake question

`better_course_progress_tracking` deliberately left the retake trigger unbuilt, and nothing in the
codebase retires a `CourseProgress` record today. That is what makes a `CourseProgress` row stable
enough for `certificates` to FK against. When a retake trigger lands, whether it resets the same
record or mints a new one is this spec's question, and `certificates` depends on the answer.

## `debt_markdown_rendering_package_isolation`: `SiteFactory` placement

`SiteFactory` lives in `accounts` while `webhooks`, `site_aware_models` and others import it only for
tests. That spec already owns assessing whether it should move. Noted here only so this cut is not
read as having missed it.
