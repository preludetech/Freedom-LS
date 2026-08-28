# Current blast radius of re-keying course progress (verified against today's tree)

**This file supersedes `research_fls_impact_surface.md`.** That document predates three merges and
cites a `student_management` / `student_interface` / `student_progress` app namespace that no longer
exists anywhere in the repo (confirmed by grep across `docs/` and `freedom_ls/`: zero `student_*`
hits). The apps are now `learner_management`, `learner_interface`, `learner_progress`; the
registration model is `LearnerCourseRegistration` (not `UserCourseRegistration`), and there is a whole
new app, `reports`, that the old document never saw. Every citation below was re-read from the
working tree; where the old document is quoted for contrast, it is explicitly marked "(old doc,
stale)".

## Baseline facts (not re-derived, only verified)

- `CourseProgress.unique_together = ["user", "course"]` — `freedom_ls/learner_progress/models.py:568`.
- `TopicProgress.unique_together = ["user", "topic"]` — `freedom_ls/learner_progress/models.py:521`.
- Neither `Meta` includes `site`, confirmed by reading both classes in full
  (`freedom_ls/learner_progress/models.py:503-524` and `:527-571`) — uniqueness is global across
  Sites today.
- `FormProgress` (`freedom_ls/learner_progress/models.py:76-97`) has no `unique_together` /
  `UniqueConstraint` at all — multiple attempts already coexist there by design.
- `Learner` — `freedom_ls/learner_management/models.py:51-80`, unique on `(user, organisation)`
  (`unique_learner_per_organisation`, `:73-77`).
- `docs/app_structure.md:88` has `learner_progress --> learner_management`. There is **no**
  `learner_progress --> organisations` edge anywhere in the file (the runtime-deps table row for
  `learner_progress`, line 157, lists only `accounts, content_engine, learner_management,
  site_aware_models`). Keying `CourseProgress`/`TopicProgress`/`FormProgress` on `Learner` therefore
  reaches `Organisation` only transitively, through the app that already owns that edge — no new
  cross-app dependency for `learner_progress` to declare.
- `freedom_ls/contrib/conformance/test_migrations.py:19-26` diffs models against migrations with no
  DB connection and asserts `not changes` — any model change here needs a migration in the same PR or
  this test fails immediately, regardless of runtime behaviour.

---

## `freedom_ls/learner_interface/views.py`

| Site | Code | Verdict once >1 `CourseProgress`/`TopicProgress` row can exist |
|---|---|---|
| `:130-141` `_detail_cta_label` | `CourseProgress.objects.filter(user=user, course=course).first()` (`:136`) | **Silently picks one row.** CTA label ("Start"/"Continue"/"Review course") becomes whichever row the unordered `.first()` returns. |
| `:511-574` `initiate_course_access` | `learner = ensure_learner(request.user, get_default_organisation(...))` (`:554-559`), then `LearnerCourseRegistration.objects.update_or_create(learner=learner, collection=course, defaults={"is_active": True})` (`:563-567`) | **Confirmed: the old `MultipleObjectsReturned` bug is gone.** The lookup half of `update_or_create` is keyed on `(learner, collection)`, not `(user, collection)` with organisation only in `defaults` — matching `LearnerCourseRegistration`'s actual constraint `unique_learner_course_registration` on `(site_id, learner, collection)` (`learner_management/models.py:120-126`). Nothing to fix here. |
| `:620-727` `view_course_item`, write at `:665-670` | `CourseProgress.objects.get_or_create(user=request.user, course=course)` then `course_progress.last_accessed_item = current_item; course_progress.save()` | **Crashes** the instant the constraint is relaxed without this call gaining a disambiguating key: `get_or_create` on a non-unique filter can create a third row on a race, or silently resolve to whichever row Postgres returns first. This is *the* single write point for the resume pointer, reached on every authenticated page view. |
| `:730-785` `_player_chrome_context` | `CourseProgress.objects.filter(user=user, course=course).first()` (`:747-751`); also calls `organisation_for_learner_course(user, course)` (`:752-754`) | **Silently picks one row** for the header progress bar / %. |
| `:788-829` `view_topic` | `TopicProgress.objects.get_or_create(user=request.user, topic=topic)` (`:797-799`) | **Crashes** once `TopicProgress` is no longer 1:1 on `(user, topic)` — same `get_or_create`-on-non-unique-filter hazard as `view_course_item`. Drives `topic_progress.complete_time` read at `:822` and the `mark_complete` POST branch at `:803-811`. |
| `:1249-1294` `course_finish` | `get_object_or_404(CourseProgress, user=request.user, course=course)` (`:1256-1258`); `unpassed_forms(request.user, course)` (`:1263`) | **Highest-severity crash.** `get_object_or_404` on a non-unique filter raises `MultipleObjectsReturned` (Django does not catch it — only `DoesNotExist`), which is an unhandled 500, on the course-completion page, for exactly the learners this project's re-keying is meant to serve (more than one pass through a course). |
| `:1269-1280` `course.completed` webhook | Payload is exactly `{"user_id", "user_email", "course_id", "course_title", "completed_time"}` (`:1273-1279`) | No learner/course-progress-row identifier at all. Once a learner can have more than one `CourseProgress` per course, a consumer cannot tell *which pass* completed from the payload alone. |
| `:1342-1352` `_is_content_item_completed` | `TopicProgress.objects.filter(user=user, topic=content_item, complete_time__isnull=False).exists()` / same shape for `FormProgress` | Safe as an `.exists()` check today (existence, not singleton) — stays safe under multiplicity *only* if "completed" is meant to mean "completed on any pass"; if a per-pass answer is wanted instead, this needs a scoping key added. |
| `FormProgress` lifecycle call sites | `finalise_stale_incomplete` (`:845`, `:913`); `get_latest_incomplete` (`:848`, `:960`, `:1326`); `get_or_create_incomplete` (`:916`); the 5-latest-attempts query (`:861-867`); `course_form_complete`'s latest-completed query (`:1162-1168`) | All keyed on `(user, form)` only — no course/pass scoping. `FormProgress` has no uniqueness constraint today, so none of these *crash*; but once a course item can be reached from more than one pass through the same course, "the latest attempt at this form" becomes ambiguous across passes rather than across courses — a design question the re-keying plan needs to answer (item progress is being re-scoped to `ContentCollectionItem`, so this is likely resolved by that, not by these call sites individually). |

## `freedom_ls/learner_interface/utils.py`

| Site | Code | Verdict |
|---|---|---|
| `:268-289` `get_resume_index` | `CourseProgress.objects.filter(user=user, course=course).select_related("last_accessed_content_type").first()` | **Silently picks one row** — resume position becomes nondeterministic across passes. |
| `:310-346` `_fetch_player_progress_maps` | Builds `topic_id -> TopicProgress` (`:331-334`) and `form_id -> latest FormProgress` (`:336-345`) maps keyed by **content-item id only**, ordered `-start_time`, last-seen-wins into the dict | **Silently merges/collapses**: with two passes, a learner's course-index status (`get_course_index` → `get_content_status`) reads whichever row this dict happens to keep, not "the row for this pass". This is the busiest chokepoint feeding the TOC/status for every course-index render. |
| `:683-697` `get_completed_courses` | `CourseProgress.objects.filter(user=user, course__in=all_registered, completed_time__isnull=False).values_list("course_id", flat=True)` | Course-keyed set: "any completed row exists" — collapses passes into a single yes/no per course, which may be the *intended* semantics post-change (a learner is "done with a course" if any pass is complete) or may not be; needs an explicit decision, not silent behaviour. |
| `:700-729` `get_current_courses` | `{cp.course_id: cp for cp in CourseProgress.objects.filter(user=user, course__in=all_registered).select_related("course")}` (`:709-714`) | **Silently merges (last-write-wins)**: dict keyed by `course_id` — with two rows for one course, whichever the queryset yields last overwrites the other with no error, no log. Feeds the dashboard's "current courses" list and each course's `progress_percentage` (`:724-726`). |
| `:769-858` `get_course_listing`, dict at `:834-839` | `progress_rows = {row["course_id"]: row for row in CourseProgress.objects.filter(user=user, course__in=registered_ids).values("course_id", "progress_percentage", "completed_time")}` | Same course_id-keyed last-write-wins collapse, feeding the all-courses catalogue's status + percentage (`:849-856`). |

## `freedom_ls/educator_interface/views.py` — the cohort progress matrix

- `_paginate_learners` (`:353-377`): `progress_subquery = Subquery(CourseProgress.objects.filter(user=OuterRef("learner__user"), course=course).values("progress_percentage")[:1], output_field=IntegerField())` (`:360-366`). **No organisation filter at all** — only `user` (via `OuterRef("learner__user")`) and `course`. **Silently picks an arbitrary row**: `[:1]` with no `.order_by()` returns whichever row Postgres hands back first once two rows exist for one `(user, course)` pair, and that value drives the row's sort order (`.order_by("progress", ...)` at `:372`).
- `_fetch_progress_maps` (`:378-419`): `topic_progress_map` keyed `(user_id, topic_id)` (`:395-400`) and `form_progress_map` keyed `(user_id, form_id)`, latest-first by `completed_time desc nulls_last, -start_time` (`:402-417`) — **same last-write-wins collapse** as `_fetch_player_progress_maps` above, for the matrix's per-cell status.
- Contrast with the tables that *are* organisation-scoped in the same file:
  - `LearnerDataTable.get_queryset` (`:154-177`) filters through `learners_visible_to(request.user, organisation)` — explicitly organisation-bounded.
  - `CourseLearnerRegistrationDataTable.get_queryset` (`:1013-1026`) filters `.filter(learner__organisation=organisation)` (`:1024`), with an explicit comment (`:1016-1018`) that "Courses themselves are not organisation-scoped... but the individual registrations rendered here belong to one organisation each and must not leak across them."
  - The progress-matrix subquery at `:360-366` has no equivalent guard — it reads straight through `learner__user` to any `CourseProgress` row for that user+course, regardless of organisation. This inconsistency already exists today and would only get worse once `CourseProgress` can have multiple rows per `(user, course)` across different `Learner`/organisation contexts.

## `freedom_ls/learner_progress/`

**`signals.py`** — `update_course_progress_on_completion` (`:35-96`) is a plain function, called from the `post_save` receiver `recalculate_course_progress_on_save` (`:99-125`, `@receiver(post_save, sender=FormProgress)` / `@receiver(post_save, sender=TopicProgress)`), not a model method.
- Completed-item sets are **global per-user, unfiltered by course**: `completed_topic_ids = set(TopicProgress.objects.filter(user=user, complete_time__isnull=False).values_list("topic_id", flat=True))` (`:80-84`), and `completed_form_ids_by_user([user.pk])` (`:85`) — same shape.
- The write: `CourseProgress.objects.update_or_create(user=user, course=course, defaults={"progress_percentage": percentage})` (`:92-96`) — **no `site=` passed at all**, and no scoping beyond `(user, course)`.
- `@claude` TODO, **must not be deleted**: `:43-46` — *"this function is very long. It needs to be refactored... topic.courses() should return the courses that a topic is included in; form.courses() should return the courses that the form is in."*

**`models.py`**
- `CourseItemProgress`, `:36-73` — a second `@claude` TODO at `:59`, **must not be deleted**: *"calculate `_original_completion_value` here instead of during `__init__`. Remove the `__init__` function."*
- The `CourseProgress` docstring (`:528-534`) reads: *"IMPORTANT!! These are only created when a user EXPLICITY chooses to register a learner for a course."* **This is provably false today**: `signals.py:88-96`'s `update_or_create` fires for **every** course reachable from a completed topic/form via `ContentCollectionItem` (`signals.py:52-77`), with no check that the user is registered for that course at all — a topic shared between two courses (which `content_engine` permits) would silently mint a `CourseProgress` row for a course the learner never registered for, the moment they complete that shared topic anywhere. The claim needs to be corrected, not preserved, when this docstring is next touched.
- `TopicProgress` (`:503-524`): `unique_together = ["user", "topic"]` at `:521`.
- `CourseProgress` (`:527-571`): `unique_together = ["user", "course"]` at `:568`.

**`queries.py`** — `attempt_completes_form` (`:10-25`) implements "a learner has to pass to complete" (a failed scored quiz with a pass mark is an attempt, not a completion); `completed_form_ids_by_user` (`:28-51`) reduces every user's `FormProgress` history to "latest completed attempt per `(user, form)`" and then applies `attempt_completes_form`. Both are keyed on `(user, form)` only — same "no pass scoping" shape as everything else in this section.

**`factories.py`** (`:21-59`) — `CourseProgressFactory` (`:21-28`), `TopicProgressFactory` (`:31-38`), `FormProgressFactory` (`:41-48`), `QuestionAnswerFactory` (`:51-58`): none define `django_get_or_create` — every factory call is an unconditional `.create()`, so nothing here masks the multiplicity question; callers that assume uniqueness must fetch the row themselves (which is exactly where the tests below break).

**`management/commands/recalculate_progress_percentages.py`** (whole file, `:1-63`) — iterates `CourseProgress.objects.select_related("course").all()` (`:27`) and recalculates each row's `progress_percentage` from user-scoped (not course/pass-scoped) `TopicProgress`/`completed_form_ids_by_user` sets (`:34-59`). Once `CourseProgress` is keyed on `Learner` with an `is_active` partial-unique constraint, this command's `for cp in all_course_progress.filter(user_id__in=batch).iterator()` (`:49`) needs no structural change to iterate — but the completed-id sets it feeds each row (currently global-per-user) will need to become per-pass or the recalculation will keep conflating passes exactly as `signals.py` does today.

**`management/commands/danger_clear_all_course_progress.py`** (whole file, `:1-11`) — unconditionally `.all().delete()`s all four models in order (`QuestionAnswer`, `FormProgress`, `TopicProgress`, `CourseProgress`). No per-row keying assumption; unaffected by the re-keying.

**`admin.py`** (whole file, `:1-140`) — `FormProgressAdmin` (`:17-51`), `TopicProgressAdmin` (`:86-111`), `CourseProgressAdmin` (`:114-139`) all declare `list_display`/`fieldsets`/`search_fields` directly against `"user"` and `"course"`/`"topic"`/`"form"` fields (e.g. `:19-26`, `:88-95`, `:116-123`). **This will crash (`FieldError`) the moment `CourseProgress`/`TopicProgress` gain a `learner` FK in place of, rather than alongside, `user`** — Django admin resolves `list_display` strings against actual model fields at class-definition/import time for some checks and at render time for others; either way a renamed field breaks these classes outright, not silently.

## `freedom_ls/learner_management/`

- `utils.py:17-66` `calculate_course_progress_percentage` — a pure function over `(course, completed_topic_ids: set[UUID], completed_form_ids: set[UUID])` (`:17-21`); it has no idea whether the id sets it's handed are course-scoped, pass-scoped, or global — the scoping decision lives entirely with the caller (`signals.py`). Low risk to this function's own body; all the risk is in what its two callers currently pass in.
- `queries.py:70-86` `latest_registration` — "most recent active registration, else most recent of any status" via `.order_by("-is_active", "-registered_at").first()`; explicitly documents (`:73-77`) that a learner can hold more than one registration for the same course (one per organisation) and picks a single row by design — an intentional, documented tiebreak, not a landmine.
- `queries.py:89-115` `organisation_for_learner_course` — resolves the organisation a learner studies a course through, cohort registration winning over individual, falling back to `latest_registration`'s tiebreak (`:111-115`) when more than one individual registration exists. Same intentional-tiebreak shape.
- `models.py:108-162` `LearnerCourseRegistration.save()` — fires `course.registered` on create (`:128-159`) with payload `{"user_id", "user_email", "course_id", "course_title", "registered_at"}` (`:152-158`) — no `learner_id`/organisation in the payload either, same shape as the `course.completed` webhook above.

## `freedom_ls/reports/`

The app is new since the old research file (which never mentions it). It **never queries
`CourseProgress`**: grep across `freedom_ls/reports/*.py` for `CourseProgress` finds exactly one
runtime hit, and it is a comment explaining why not — `gather.py:218`, inside `_latest_completion`'s
docstring: *"Never `CourseProgress.last_accessed_item` — that tracks last viewed, not last
completed."* Every completion/percentage figure in the report is recomputed from `TopicProgress`/
`FormProgress` (`indexes.py`'s loaders, folded in `gather.py`). This is proven by a test, not just
asserted: `reports/tests/test_gather.py:152-165`
(`test_completion_percentage_ignores_stale_course_progress_field`) seeds a `CourseProgressFactory`
with a deliberately wrong `progress_percentage=87` (`:160`) and asserts the report shows `0` (`:165`)
because no `TopicProgress`/`FormProgress` backs it.

So the re-keying cannot break `reports` through `CourseProgress` at all — but it is still exposed,
through the same `(user, item)` / `(user, form)` keying shape as everywhere else, applied at cohort
scale:

- `indexes.py:256-284` `load_topic_progress_rows` / `fold_topic_progress_rows` — `(user_id, topic_id,
  complete_time)` rows folded into `completed_topic_ids_by_user: dict[int, set[UUID]]` (`:272-278`,
  keyed by `user_id` only, no course/pass axis).
- `indexes.py:287-348` `load_form_progress_rows` / `fold_form_progress_rows` — every sitting of every
  cohort form, ordered `completed_time desc nulls_last, -start_time` (`:296-302`); folded into
  `latest_by_user_form: dict[(user_id, form_id), FormProgress]` (first-seen wins, `:319-322`) and
  `completed_attempts_by_user_form` (`:323-333`).
- `indexes.py:379-400` `load_first_attempt_ids` — a `Window(RowNumber(), partition_by=[F("user_id"),
  F("form_id")], order_by=F("start_time").asc())` filtered to `rank=1` (`:391-398`) — "each learner's
  earliest completed sitting of each quiz", used to build the cohort-wide confusion analysis
  (`gather.py:338-372` `tally_quiz_answers`, `:403-450` `build_confusion_block`).
- `at_risk.py:56-64` `NoRecordedActivityRule.evaluate` reads `learner.has_any_progress`, itself built
  in `gather.py:642` as `user_id in progress.user_ids_with_any_progress` — the union of
  `TopicProgressIndex.user_ids_seen | FormProgressIndex.user_ids_seen` (`indexes.py:120-128`), i.e.
  "has a row anywhere", not "has a row for this pass".

**What goes wrong once one learner can have more than one pass through the same course, sharing the
same underlying `Topic`/`Form` rows across those passes:**
- **Unioned completions.** `completed_topic_ids_by_user`/`completed_form_ids_by_user` are keyed by
  `user_id` alone (`indexes.py:272-278`, `:314`) — a topic completed on pass 1 reads as complete for
  pass 2 too, inflating the completion percentage the cohort report shows for a fresh pass.
- **Attempt renumbering.** `_quiz_result_for` (`gather.py:293-335`) numbers `attempt_number` by
  enumerating every row in `completed_attempts_by_user_form[(user_id, form_id)]` (`:302-319`) —
  attempts from an earlier pass are counted into the "attempt 1, 2, 3..." sequence shown for the
  current pass, since the key has no pass axis.
- **Confusion analysis taking the first attempt ever, not the first attempt this pass.**
  `load_first_attempt_ids`'s window is `partition_by=[F("user_id"), F("form_id")]` (`indexes.py:394`)
  — the "first attempt" it finds is the earliest sitting across the learner's entire history with
  that form, which could belong to a prior pass, silently contaminating the cohort-wide "most
  confusing question" tally (`gather.py:338-372`) with data from a pass the current report isn't
  about.

## Tests, factories and QA

- `freedom_ls/learner_interface/tests/test_resume_and_redirect.py:205-208`
  (`test_viewing_topic_records_last_accessed_item`) and `:320-321` (inside the form-resume test) both
  do a bare `cp = CourseProgress.objects.get(user=..., course=...)` — **will raise
  `MultipleObjectsReturned`** the moment a test (deliberately or accidentally) creates two
  `CourseProgress` rows for the same learner+course.
- `freedom_ls/learner_progress/tests/test_course_progress.py:150`
  (`test_completing_item_creates_course_progress_if_missing`) does the same:
  `cp = CourseProgress.objects.get(user=user, course=course)` — same failure mode.
- `freedom_ls/qa_helpers/management/commands/qa_create_report_cohort.py:285-292` — the docstring at
  `:285-290` states the workaround directly: *"Pre-create CourseProgress WITH a site... `qa_complete_form`... calls `CourseProgress.objects.update_or_create()` without a site... Owning the row first with `site=site` avoids that"* — a hand-rolled guard (`:291-292`) that only exists because `signals.py:92-96`'s `update_or_create` never passes `site=`.
- `freedom_ls/qa_helpers/management/commands/qa_create_rich_dashboard_learner.py:111-117` — the
  identical workaround, same docstring shape: *"Pre-create the CourseProgress row with a site
  set... `FormProgress.complete()` fires `update_course_progress_on_completion`, which creates
  `CourseProgress` WITHOUT a site (NotNullViolation). Owning the row first with `site=site` avoids
  that."*
  These are the two commands that pass `site=` by hand specifically to work around
  `update_course_progress_on_completion`'s missing `site=`; no other `qa_helpers` command needs the
  same workaround (the other 12 files matching a broader `CourseProgress|TopicProgress|FormProgress`
  grep pass `site=` only through ordinary `SiteAwareFactory` construction, not as a targeted fix for
  this bug).

## Swept and clear

- `freedom_ls/course_access/`, `freedom_ls/xapi_learning_record_store/`, `freedom_ls/
  course_applications/`, `freedom_ls/course_interest/` — grepped for `CourseProgress`/
  `TopicProgress`/`FormProgress`: **zero matches in all four apps.** None of them touch progress
  models directly; `course_access` reasons only about registration existence
  (`is_registered_for_course`), not progress.
- Templates: `progress_percentage`/`CourseProgress` etc. appear only in
  `learner_interface/templates/.../course_card.html`, `course_row.html`, `course_toc_header.html`,
  `cotton/course-progress-bar.html`, `_course_base.html` — all read plain context values
  (`progress_percentage`, `course_progress.completed_time`, ...) passed in by the views above. They
  carry no query-level uniqueness assumption of their own; they inherit whatever the view handed them.
- `docs/` — grepped for `CourseProgress`/`TopicProgress`/`FormProgress`/`student_`: **zero matches.**
  No product documentation currently describes the per-topic/per-course singleton claim the way the
  old research file's §J once quoted (that quoted text was from `docs/product/learner-tracking.md`,
  which either never existed at this path or has since been removed/renamed — not found today).

---

## Ranked by risk

**Crashes (loud, `MultipleObjectsReturned` / `FieldError`, first thing to break)**
1. `learner_interface/views.py:1256-1258` `course_finish`'s `get_object_or_404(CourseProgress, user=,
   course=)` — 500s the completion page for any learner with a second `CourseProgress` row.
2. `learner_interface/views.py:666-670` `view_course_item`'s `CourseProgress.objects.get_or_create(user=,
   course=)` and `:797-799` `view_topic`'s `TopicProgress.objects.get_or_create(user=, topic=)` — both
   reached on ordinary player navigation, both `get_or_create` on what stops being a unique filter.
3. `learner_interface/tests/test_resume_and_redirect.py:205, 320` and
   `learner_progress/tests/test_course_progress.py:150` — bare `.get()` calls that will start failing
   as soon as any test path creates a second row.
4. `learner_progress/admin.py` (`FormProgressAdmin`, `TopicProgressAdmin`, `CourseProgressAdmin`,
   `:17-139`) — `list_display` built directly on `"user"`/`"course"`/`"topic"`/`"form"`; breaks outright
   if those fields are renamed rather than supplemented.

**Silently misleading (wrong numbers, no error, nothing to grep for)**
5. `educator_interface/views.py:360-366` `_paginate_learners`'s `Subquery(...)[:1]` with **no
   organisation filter** — picks an arbitrary `CourseProgress` row for the cohort matrix's sort column.
6. `learner_interface/utils.py:700-729` `get_current_courses` and `:769-858` `get_course_listing`'s
   `course_id`-keyed dicts (`:709-714`, `:834-839`) — last-write-wins collapse of two `CourseProgress`
   rows into one, feeding the dashboard and the all-courses catalogue.
7. `learner_interface/utils.py:310-346` `_fetch_player_progress_maps` and
   `educator_interface/views.py:378-419` `_fetch_progress_maps` — item-id-keyed (not pass-keyed) maps
   driving the course-index/TOC status and the cohort progress-matrix cells respectively.
8. `learner_progress/signals.py:80-96` `update_course_progress_on_completion` — global per-user
   completed-id sets, no course/pass scoping, and no `site=` on its `update_or_create` (hence the two QA
   command workarounds). This is the root cause several of the above ultimately trace back to.
9. `reports/indexes.py` — unioned completions (`:272-278`, `:314`), attempt renumbering
   (`gather.py:302-319`), and confusion analysis keyed on each learner's first attempt *ever*
   (`indexes.py:391-398`) rather than first attempt *this pass*. Never touches `CourseProgress`, so
   immune to the crash-class bugs above, but silently wrong the moment passes share underlying
   `Topic`/`Form` rows.
10. `learner_progress/models.py:528-534` — the `CourseProgress` docstring's "only created on explicit
    registration" claim, already disprovable today via `signals.py:88-96`, and more visibly wrong once
    re-keying is in flight.

**Merely tedious (mechanical, no correctness risk once done)**
11. `learner_progress/factories.py:21-48` — three factories with no `django_get_or_create`; will need a
    `learner=`/pass-scoping parameter threaded through every call site across the test suite.
12. `learner_interface/views.py:1269-1280` (`course.completed`) and
    `learner_management/models.py:128-159` (`course.registered`) webhook payloads — no
    learner/pass identifier; straightforward additive payload changes, not urgent, but should land in
    the same PR as the model change so consumers get the new field from day one.
13. `learner_progress/management/commands/recalculate_progress_percentages.py:34-59` — needs its
    completed-id sets rescoped from global-per-user to per-pass; `danger_clear_all_course_progress.py`
    needs nothing.

status: ok
