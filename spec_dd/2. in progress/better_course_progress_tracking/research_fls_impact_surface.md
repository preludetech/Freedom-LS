# Blast-radius map: repoint progress at a registration

Scope reminder (product owner): **"Models + keep existing UI correct."** New attempt-history UI is
out of scope. This document maps every place that currently assumes `(user, content-item)` or
`(user, course)` uniqueness and would need to change, or be re-verified, if `TopicProgress`,
`FormProgress`, `CourseProgress` are repointed to hang off a registration (allowing >1 registration
per user+course).

All citations are `path:line` against the working tree at the time of writing. `migrations/` excluded
per instructions except where a constraint name/shape needed confirming.

---

## 0. The two registration models today (baseline)

- `UserCourseRegistration` — `freedom_ls/student_management/models.py:46-97`. FK `user`, FK
  `collection` (Course), `is_active`, `registered_at`. **Unique constraint
  `unique_user_course_registration` on `(site_id, collection, user)`**
  (`freedom_ls/student_management/models.py:58-64`) — this is the load-bearing fact for this whole
  project: **today it is impossible to create a second `UserCourseRegistration` row for the same
  user+course, active or not.** A "renewal" or "unregister then re-register" scenario currently has
  nowhere to put a second row without deleting the first. This constraint itself is model-change #1,
  not a follow-on effect.
- `CohortCourseRegistration` — `freedom_ls/student_management/models.py:100-123`. Unique on
  `(site_id, collection, cohort)`. A cohort can only be registered for a course once, ever (same
  finding as above, at the cohort level).
- Both models fire nothing on delete/deactivate; there is **no "unregister" codepath anywhere in the
  app** (confirmed by grep — no view, no admin action, no management command sets
  `is_active=False` outside tests/fixtures). Unregistration today = an admin manually editing
  `is_active` in Django admin, or deleting the row. This matters for the "unregister-then-re-register"
  scenario in the change brief: there is no supported unregister flow to build the re-register story
  on top of.
- Deadlines already hang off the *registration*, not off `(user, course)`: `CohortDeadline.
  cohort_course_registration` FK (`student_management/models.py:129-133`), `StudentDeadline.
  student_course_registration` FK (`:176-180`), `UserCohortDeadlineOverride.
  cohort_course_registration` FK (`:223-227`). This is the existing pattern the progress models should
  probably mirror — see §I.

---

## A. Direct model usage, by app

### `student_progress/models.py`
| Line | Usage |
|---|---|
| `models.py:72-76` | `TopicProgress.objects.filter(user=user, complete_time__isnull=False)` — global per-user completed-topic set, no course/registration scoping |
| `models.py:77-81` | `FormProgress.objects.filter(user=user, completed_time__isnull=False)` — same, global per-user |
| `models.py:88-92` | `CourseProgress.objects.update_or_create(user=user, course=course, ...)` — the single write point for progress %, keyed on `(user, course)` |
| `models.py:110-123` | `CourseItemProgress.save()` hook — reads `self.user`, calls `update_course_progress_on_completion(user, content_item)` — no registration in the call signature |
| `models.py:167-188` | `FormProgress.get_latest_incomplete` / `get_or_create_incomplete` — keyed on `(user, form)` |
| `models.py:542-560` | `TopicProgress` — FK `user`, FK `topic`, **`unique_together = ["user", "topic"]`** (`:558-560`) — the load-bearing per-item singleton constraint |
| `models.py:566-607` | `CourseProgress` — FK `user`, FK `course`, **`unique_together = ["user", "course"]`** (`:605-607`) — the load-bearing per-course singleton constraint, plus `last_accessed_item` GenericFK used for resume |

### `student_interface/views.py`
| Line | Usage |
|---|---|
| `views.py:126` | `CourseProgress.objects.filter(user=user, course=course).first()` — CTA label |
| `views.py:592-596` | `CourseProgress.objects.get_or_create(user=request.user, course=course)` — resume-pointer write, single write point for both topics and forms |
| `views.py:666-670` | `CourseProgress.objects.filter(user=user, course=course).first()` — player chrome header % |
| `views.py:709-711` | `TopicProgress.objects.get_or_create(user=request.user, topic=topic)` — relies on the `unique_together` |
| `views.py:771-773` | `FormProgress.objects.filter(user=..., form=..., completed_time__isnull=False).order_by("-completed_time")[:5]` — "5 latest attempts" list on the form start screen |
| `views.py:996-1002` | `FormProgress.objects.filter(user=..., form=..., completed_time__isnull=False).order_by("-completed_time").first()` — result page, most-recent completion |
| `views.py:1071-1073` | `get_object_or_404(CourseProgress, user=request.user, course=course)` — **`course_finish` assumes exactly one row**; will `MultipleObjectsReturned` the instant a second registration/CourseProgress exists for the same course |
| `views.py:1145-1154` | `_is_content_item_completed` — `TopicProgress.objects.filter(user=user, topic=...).exists()` / same for `FormProgress` — global-per-item completedness, feeds deadline-lock logic |

### `student_interface/utils.py`
| Line | Usage |
|---|---|
| `utils.py:126` | `topic_progress_map.get(content_item.id)` — TOC status, one row per topic id, no per-registration disambiguation |
| `utils.py:207-215` | `get_course_registrations` — unions `UserCourseRegistration` + `CohortCourseRegistration` **distinct on `Course`** — already collapses multiple registrations for the same course into one row in every list (dashboard, catalogue) |
| `utils.py:218-239` | `get_resume_index` — `CourseProgress.objects.filter(user=user, course=course).select_related(...).first()` — **`.first()` on an assumed singleton**; with two `CourseProgress` rows this silently picks an arbitrary one (ordering is unspecified — insertion order in practice) |
| `utils.py:260-296` | `_fetch_player_progress_maps` — builds `topic_id -> TopicProgress` and `form_id -> latest FormProgress` maps **keyed by content-item id only**, not `(item, registration)`. This is the single busiest chokepoint: course-index/status/TOC all read through here |
| `utils.py:620-634` | `get_completed_courses` — `CourseProgress.objects.filter(user=user, course__in=all_registered, completed_time__isnull=False).values_list("course_id", ...)` — course-keyed set, collapses to "any completed row exists" |
| `utils.py:637-666` | `get_current_courses` — `{cp.course_id: cp for cp in CourseProgress.objects.filter(user=user, course__in=all_registered)...}` — **dict keyed by `course_id`, last-write-wins if two rows exist for the same course** (silent data loss, no error) |
| `utils.py:706-795` | `get_course_listing` — `progress_rows = {row["course_id"]: row for row in CourseProgress.objects.filter(user=user, course__in=registered_ids).values(...)}` — same course_id-keyed dict collapse as above |

### `educator_interface/views.py` — the cohort course-progress matrix
| Line | Usage |
|---|---|
| `views.py:213-241` | `CohortCourseRegistrationDataTable` — already lists registrations, not courses; unaffected in shape |
| `views.py:266-280` | `_get_selected_registration` — picker already operates on a list of `CohortCourseRegistration`; this is the **existing precedent for a registration-picker UI** (see §I) |
| `views.py:322-340` | `_paginate_students` — `progress_subquery = Subquery(CourseProgress.objects.filter(user=OuterRef("user"), course=course).values("progress_percentage")[:1], ...)` — **`[:1]` silently picks one arbitrary row** if two `CourseProgress` rows exist per user+course; no error, no ordering guarantee (matches `.first()`-style silent picking) |
| `views.py:359-364` | `TopicProgress.objects.filter(user_id__in=..., topic_id__in=...)` keyed into `(user_id, topic_id)` map — **last-write-wins** if two rows share a `(user, topic)` key once the per-item uniqueness constraint is loosened |
| `views.py:368-382` | `FormProgress` map keyed `(user_id, form_id)`, ordered by `completed_time desc nulls_last, -start_time` — deliberately "latest across all attempts", already registration-agnostic; if progress becomes per-registration this must decide whether the matrix shows "latest across all registrations" or "latest for the selected registration" |
| `views.py:386-440` | `_fetch_deadline_data` — reads `CohortDeadline`/`UserCohortDeadlineOverride` keyed by `selected_reg` (the `CohortCourseRegistration`) — **already registration-scoped**, unaffected |

### `student_progress/admin.py`, `factories.py`, `management/commands/`
Covered in §F, §E, §G below.

### `student_management`
| Line | Usage |
|---|---|
| `utils.py:67-91` | `is_registered_for_course` — two `.exists()` checks, `Q`-safe under multiple registrations (existence, not singleton), but see §D for the semantic question it doesn't answer |
| `utils.py:15-64` | `calculate_course_progress_percentage` — pure function over `(course, completed_topic_ids, completed_form_ids)`; no registration awareness at all — see §C |
| `queries.py:15-49` | `is_registered_for_course_expression` — two `Exists()` subqueries, same existence-safety as above |
| `deadline_utils.py` (whole file) | Already fully registration-scoped (`UserCourseRegistration`/`CohortCourseRegistration` FKs throughout) — the pattern to imitate, not a file that needs to change |

### `qa_helpers` management commands
Covered in §E.

### `webhooks`
Covered in §H.

---

## B. Uniqueness assumptions — exhaustive list (the important section)

These are the places that will **silently misbehave** (wrong data, not a crash) or **loudly break**
(`MultipleObjectsReturned` / `IntegrityError`) the moment a second `CourseProgress`/`TopicProgress`/
`FormProgress` row can exist for the same `(user, course)` / `(user, topic)` pair.

### B.1 Will raise `MultipleObjectsReturned` (loud break)
- `student_interface/views.py:1071-1073` — `get_object_or_404(CourseProgress, user=request.user, course=course)` in `course_finish`. **Highest-severity finding**: the course-completion page 500s for any learner with two `CourseProgress` rows for the course, which is exactly the scenario this project introduces.

### B.2 Will silently pick an arbitrary/first/last row (silent wrongness)
- `student_interface/utils.py:228-232` — `get_resume_index`'s `.first()` on `CourseProgress.objects.filter(user=user, course=course)` — resume position becomes nondeterministic across two registrations.
- `student_interface/views.py:126` — `_detail_cta_label`'s `.first()` — CTA label ("Start"/"Continue"/"Review") becomes nondeterministic.
- `student_interface/views.py:666-670` — `_player_chrome_context`'s `.first()` — header progress bar % becomes nondeterministic.
- `student_interface/utils.py:648-651` and `771-776` — dict comprehensions keyed by `course_id` (`{cp.course_id: cp for cp in ...}`) — **last row wins** with no warning; drives the dashboard's registered/current/completed course lists and the all-courses catalogue's status+percentage.
- `educator_interface/views.py:324-329` — `Subquery(...).values("progress_percentage")[:1]` — arbitrary row feeds the cohort progress-matrix's row-level "progress" sort column (`views.py:335-336` sorts by this value).
- `student_interface/views.py:592-596` — `CourseProgress.objects.get_or_create(user=request.user, course=course)` in `view_course_item` — with the uniqueness constraint removed, `get_or_create` on a non-unique filter is itself dangerous: a *third* row can be created by a race, or it silently "gets" whichever row `.filter().first()`-equivalent returns. This call **must** become registration-aware (`get_or_create(user=, course=, registration=)`) not just tolerate multiplicity.

### B.3 `get_or_create` / `update_or_create` calls whose kwargs must gain a registration key
- `student_progress/models.py:88-92` — `CourseProgress.objects.update_or_create(user=user, course=course, defaults={...})` inside `update_course_progress_on_completion` — **the** central write; without a registration key this cannot target "the right" `CourseProgress` row once several exist for one course.
- `student_interface/views.py:592-596`, `709-711` — see above.
- `student_progress/models.py:175-188` — `FormProgress.get_or_create_incomplete` — keyed `(user, form)`; once a topic/form can be reused across registrations of the same course (or across "modular courses" reusing items — see brief), this needs a registration key too, otherwise a learner's second registration's in-progress attempt on a shared form collides with the first registration's attempt.
- `qa_helpers/management/commands/qa_create_cohort_progress.py:32-46, 51-65, 73-78` — three `get_or_create`/`update_or_create` calls, all keyed `(user, topic/form/course, site)`. Will need a registration argument or will create/find the wrong row (or collide) once run twice for a re-registered learner.
- `qa_helpers/management/commands/qa_create_rich_dashboard_student.py:111, 115, 134, 208` — same shape, four call sites.
- `qa_helpers/management/commands/qa_create_course_player_student.py:129, 136` — same shape, two call sites.

### B.4 `unique_together` / constraint definitions that must change
- `student_progress/models.py:558-560` — `TopicProgress.Meta.unique_together = ["user", "topic"]` — must become `["registration", "topic"]` (or similar) once a learner's two registrations for the same course need independent topic-completion rows for shared topics. NB: if "modular courses reuse items from other courses" (per the brief) becomes real, the same topic could appear under **two different courses** for one registration too — the uniqueness key needs to be considered against that future, not just re-registration.
- `student_progress/models.py:605-607` — `CourseProgress.Meta.unique_together = ["user", "course"]` — must become `["registration"]` (a `CourseProgress` naturally becomes 1:1 with a registration, not `(user, course)`), or `OneToOneField(registration)` outright.
- `student_management/models.py:58-64` — `UserCourseRegistration`'s `unique_user_course_registration` on `(site_id, collection, user)` — **this is the constraint that currently prevents multiple registrations at all** and must be relaxed (e.g. drop it, or scope it to `(site_id, collection, user, is_active=True)` via a partial unique constraint so at most one *active* registration exists per user+course, but historical/inactive ones can accumulate). Decide this before anything else — every other change in this document is downstream of what replaces this constraint.
- `student_management/models.py:114-120` — `CohortCourseRegistration`'s `unique_cohort_course_registration` on `(site_id, collection, cohort)` — same question at cohort granularity; the brief's "cohort re-run" scenario implies either a *new* `Cohort` per re-run (sidesteps this constraint) or this constraint also needs relaxing. Needs an explicit product decision — the two scenarios (new cohort vs. same cohort registered twice) have very different spec shapes.

### B.5 Template-level / implicit singleton assumptions
- `student_interface/views.py:734` — `topic_progress.complete_time is not None` read straight off the single `get_or_create`d instance from `:709-711` — inherits B.3's problem, not a separate bug once that's fixed correctly.
- Player templates are not read line-by-line here (out of grep scope for this pass) but every template that receives `course_progress` from `_player_chrome_context` (`views.py:694`) inherits the `.first()` nondeterminism at B.2.

---

## C. The progress-percentage machinery

### `update_course_progress_on_completion` — `student_progress/models.py:27-92`
Current algorithm, precisely:
1. Given `(user, content_item)`, trace `ContentCollectionItem` links to find every `Course` (direct or via `CoursePart`) that contains this item — `:44-69`.
2. Build **two global per-user sets**: every topic id the user has ever completed (`:72-76`) and every form id the user has ever completed (`:77-81`) — **no course scoping, no registration scoping**, queried across the user's entire `TopicProgress`/`FormProgress` history.
3. For each affected course, call `calculate_course_progress_percentage(course, completed_topic_ids, completed_form_ids)` (`student_management/utils.py:15-64`), which walks the course's item tree and checks membership in the two global sets — `:39-58` recursion.
4. `CourseProgress.objects.update_or_create(user=user, course=course, defaults={"progress_percentage": percentage})` — `:88-92`.

**What changes when progress is scoped to a registration:**
- Step 2's "global per-user completed set" is exactly what makes this function currently *course-agnostic and registration-agnostic by construction* — it works today only because a topic/form can only ever have one `TopicProgress`/`FormProgress` row per user (the `unique_together`), so "completed anywhere" and "completed for this course/registration" are the same fact. The moment §B.4's constraints are relaxed, this equivalence breaks: a learner's *first* registration's completed topics must not silently count toward calculating the *second* registration's percentage (or, depending on the product's semantics for "modular courses reusing items", they explicitly *should* — this is a product decision, not just an implementation one).
- The function's completed-item lookups (`:72-81`) must become registration-scoped: `TopicProgress.objects.filter(user=user, registration=registration, complete_time__isnull=False)`, and the caller must know *which* registration triggered the save (today `update_course_progress_on_completion(user, content_item)` receives neither a course nor a registration — it discovers the course from the content item). The function's signature necessarily grows a `registration` (or equivalent) parameter, and every call site (`CourseItemProgress.save()` at `:118-123`) must supply it — meaning `TopicProgress`/`FormProgress` need the registration available on `self` at save time, which is exactly the model change in scope.
- Step 4's `update_or_create(user=user, course=course, ...)` must become `update_or_create(registration=registration, ...)` per §B.3/B.4.
- `calculate_course_progress_percentage` itself (`student_management/utils.py:15-64`) is registration-agnostic *by design* today (pure function over two id-sets) and can likely stay that way — the registration-scoping work moves entirely into what set of ids is passed in, not into this function's body. Low risk here, contingent on the two TODOs below not touching it.

### The two `@claude` TODOs in `student_progress/models.py` — must not be deleted, and this is a natural place to fold them in
- `models.py:35-38` — *"this function is very long. It needs to be refactored... topic.courses() should return the courses that a topic is included in; form.courses() should return the courses that the form is in."* This refactor is directly entangled with the registration-scoping change: once `update_course_progress_on_completion` needs a `registration` parameter and the completed-set queries need registration-scoping, the function's shape changes anyway — doing the refactor and the registration-scoping in the same unit of work (rather than sequentially) avoids touching this function twice. Recommend calling this out explicitly in the spec as an opportunistic combination, not skip it.
- `models.py:115-116` — *"calculate `_original_completion_value` here instead of during `__init__`. Remove the `__init__` function"* — `CourseItemProgress.__init__` (`:104-108`) and `.save()` (`:110-123`) are exactly the methods that will gain the registration-awareness (the `user`/`content_item` reads at `:120-122` need a registration alongside). Same argument: touch this code once, not twice — fold the TODO into this change's plan rather than doing it separately before or after.
- **Do not delete either comment** even if the spec phase decides not to action them in this change — project convention (CLAUDE.md) explicitly forbids removing `@claude` TODOs unless completed.

---

## D. Access-control coupling

- `student_management/utils.py:67-91` `is_registered_for_course` and `student_interface/utils.py:195-204` `get_is_registered` (thin wrapper) both reduce to `UserCourseRegistration.objects.filter(user=, collection=, is_active=True).exists()` OR the cohort equivalent — **pure existence check, not a singleton lookup**, so this survives multiple registrations without modification *as long as* "is registered" only ever needs to answer yes/no.
- `course_access/backends.py:191-223` (`_free_access_decision`) and `:332-371` (`VisibilityEnforcingBackend.get_access`) both call `is_registered_for_course` to decide the CTA (`Continue` vs `Enrol`) and content access — same "existence is enough" observation; these do not need to know *which* registration.
- `course_access/queries.py` — wait, it's `student_management/queries.py:15-49` `is_registered_for_course_expression` — same, `Exists()`-based, safe under multiplicity.
- **Where this breaks down**: the moment there are two *active* registrations for the same course (e.g. direct + cohort simultaneously, explicitly listed as an in-scope scenario in the brief), "is registered" is still correctly `True`, but **every downstream consumer that reads progress off `(user, course)` now has two candidate progress rows and no way to know which registration's row the access decision "means"**. The access-control layer itself doesn't need to change; every *progress* read reachable after an access decision does (§B). This is the connective finding: access control answers "can this user see the course", progress reads answer "what should we show them", and only the second one is registration-plural.
- `is_registered_for_course` deliberately has **no concept of "the current/primary registration"** — there is no `get_active_registration(user, course)` helper anywhere in the codebase. If the UI needs to pick one registration to drive `course_home`'s resume redirect (`student_interface/views.py:470-497`) and the player chrome, this helper does not exist yet and is new surface, not a refactor of existing surface.

---

## E. Management commands

| Command | File | What it needs |
|---|---|---|
| `recalculate_progress_percentages` | `student_progress/management/commands/recalculate_progress_percentages.py:1-55` | `completed_topics_by_user`/`completed_forms_by_user` dicts keyed by `user_id` (`:28-38`) must become keyed by `(user_id, registration_id)` or similar; the `for cp in all_course_progress.iterator()` loop (`:41`) already iterates `CourseProgress` rows directly so naturally becomes per-registration once `CourseProgress` is registration-scoped — moderate rewrite, not structural. |
| `danger_clear_all_course_progress` | `student_progress/management/commands/danger_clear_all_course_progress.py:1-11` | Unaffected — deletes all rows of all four models unconditionally; no per-row keying assumptions. |
| `qa_create_cohort_progress` | `qa_helpers/management/commands/qa_create_cohort_progress.py:30-78` | Four helper functions (`_complete_topic`, `_start_topic`, `_complete_form`, `_start_form`, `_set_course_progress`) all `get_or_create`/`update_or_create` on `(user, item, site)` — every one needs a registration parameter threaded through from the cohort's `CohortCourseRegistration` (already fetched at `:157-163`, just not passed down). |
| `qa_create_rich_dashboard_student` | `qa_helpers/management/commands/qa_create_rich_dashboard_student.py:111,115,134,208` | Same shape, 4 call sites; not read in full here but grep confirms the pattern matches `qa_create_cohort_progress`. |
| `qa_create_course_player_student` | `qa_helpers/management/commands/qa_create_course_player_student.py:129,136` | Same shape, 2 call sites. |
| `qa_complete_form` | `qa_helpers/management/commands/qa_complete_form.py:43-67` | Uses `FormProgressFactory(form=, user=, site=, ...)` (`:57-66`) after an `.exists()` guard (`:56`) — factory call needs a `registration` kwarg once the field exists; the `.exists()` guard's semantics ("has this student already completed this form") may also need to become per-registration. |
| `create_demo_data` | `student_management/management/commands/create_demo_data.py` | No direct references to the four progress/registration models found by grep — likely delegates to factories/fixtures loaded elsewhere; re-verify once the actual data-loading path is traced in the spec phase (not done here — out of grep's reach without reading the full file, which is long; flagging as unresolved). |

---

## F. Factories and tests

### Factories
- `student_progress/factories.py:21-58` — `CourseProgressFactory` (`:21-28`), `TopicProgressFactory`
  (`:31-38`), `FormProgressFactory` (`:41-48`), `QuestionAnswerFactory` (`:51-58`) — **none of the
  three progress factories take a `registration` parameter today** because the field doesn't exist yet.
  All three need a `registration = factory.SubFactory(UserCourseRegistrationFactory)` (or similar)
  added, which is itself a breaking change to every call site that doesn't explicitly override it
  (auto-created registration may not match the `user`/`course`/`topic`/`form` passed explicitly at the
  call site — most call sites `factory.SubFactory` a fresh `Course`/`Topic`/`Form` too, so a
  mismatched auto-registration would be silently wrong unless the factory's `LazyAttribute` derives
  the registration from the same course/user being passed in, mirroring how `CohortDeadlineFactory`
  (`student_management/factories.py:66-94`) derives `content_type`/`object_id` from `content_item` via
  `LazyAttribute`).
- `student_management/factories.py:44-63` — `UserCourseRegistrationFactory` /
  `CohortCourseRegistrationFactory` — these do not need to change themselves, but every progress
  factory becomes downstream of them.

### Test file impact (files that construct progress via the three factories, with occurrence counts from grep)
136 total factory-call occurrences across 21 files. By file:

| File | Occurrences | App |
|---|---|---|
| `student_progress/tests/test_course_progress.py` | 19 | student_progress |
| `student_interface/tests/test_form_runner_views.py` | 14 | student_interface |
| `student_interface/tests/test_all_courses_rows.py` | 10 | student_interface |
| `student_interface/tests/test_course_cards.py` | 10 | student_interface |
| `student_progress/tests/test_form_progress.py` | 9 | student_progress |
| `student_interface/tests/test_form_start_page_buttons.py` | 8 | student_interface |
| `student_progress/tests/test_form_progress_complete_idempotent.py` | 6 | student_progress |
| `student_interface/tests/test_course_listing.py` | 6 | student_interface |
| `student_interface/tests/test_course_part_children.py` | 6 | student_interface |
| `educator_interface/tests/test_cohort_course_progress_panel.py` | 6 | educator_interface |
| `qa_helpers/management/commands/qa_create_course_player_student.py` | 6 | qa_helpers (not a test, listed for completeness) |
| `student_interface/tests/test_dashboard_view.py` | 5 | student_interface |
| `student_progress/tests/test_form_progress_score_category_value_sum.py` | 5 | student_progress |
| `student_progress/factories.py` | 4 | (factory defs themselves) |
| `qa_helpers/management/commands/qa_create_application_docs_scenario.py` | 4 | qa_helpers |
| `student_progress/tests/test_form_progress_score_quiz.py` | 4 | student_progress |
| `student_interface/tests/test_course_completion_webhook_events.py` | 3 | student_interface |
| `student_interface/tests/test_course_helpers.py` | 3 | student_interface |
| `student_interface/tests/test_all_courses_view.py` | 3 | student_interface |
| `student_interface/tests/test_course_access_integration.py` | 3 | student_interface |
| `qa_helpers/management/commands/qa_complete_form.py` | 2 | qa_helpers |

**Estimate: every one of these 19 test files (excluding the two qa_helpers command files, which are
production code, and the factories.py definition file) will need at minimum a mechanical update to
supply/derive a `registration` on each factory call — roughly 130+ individual call sites** across
those 19 files if the new field is required (non-nullable) with no auto-deriving default; fewer if the
factory can safely default it via `LazyAttribute` from the `user`+`course`/`topic`+`form` already
being passed (mirroring the `CohortDeadlineFactory` pattern). Additionally:
- `student_interface/tests/test_resume_and_redirect.py:151,266` and
  `student_progress/tests/test_course_progress.py:150` do a bare `CourseProgress.objects.get(user=,
  course=)` (not via factory) — these three assertions will need a `registration=` argument added or
  they will raise `MultipleObjectsReturned` in any test that (deliberately or accidentally) creates two
  registrations for the same user+course.
- `student_management/tests/test_registration_webhook_events.py` and the deadline test files
  (`test_cohort_deadline.py`, `test_student_deadline.py`, `test_student_cohort_deadline_override.py`,
  `test_deadline_utils.py`, `test_deadline_utils_bulk.py`) already construct registrations explicitly
  and are the closest existing precedent for "tests that think in terms of registrations, not bare
  user+course" — useful models for the new progress tests, not files that need rewriting themselves.

---

## G. Admin

- `student_progress/admin.py:17-51` `FormProgressAdmin`, `:86-111` `TopicProgressAdmin`, `:114-139`
  `CourseProgressAdmin` — all three `list_display`/`fieldsets`/`search_fields` are built around
  `(user, topic/form/course)` pairs (e.g. `:19-26`, `:88-95`, `:116-123`) with **no registration
  column at all**. Once the FK exists, all three admins need a `registration` column added to
  `list_display` (else two rows for the same user+course/topic/form are visually indistinguishable in
  the list view) and probably `list_filter`/`autocomplete_fields` additions. Not a blocking change, but
  an immediate usability regression if skipped — an admin looking at `CourseProgressAdmin`'s changelist
  today has no way to tell two rows for the same user+course apart once they can coexist.
- `student_management/admin.py:56-81` `UserCourseRegistrationAdmin` already has an inline
  `StudentDeadlineInline` (`:47-54,69`) keyed off the registration — no change needed here structurally,
  but its `list_display`/`search_fields` (`:58-66`) will show duplicate-looking rows (same user, same
  course) once the uniqueness constraint is relaxed; consider whether `registered_at` ordering or an
  `is_active` filter badge needs to be more prominent to disambiguate renewals in the list view (UX
  question for spec phase, not a hard requirement under "keep existing UI correct").
- `student_management/admin.py:43-44` — existing `@claude` comment: *"We need a base class that
  extends from Guarded model admin and excludes the site... implement it... update
  docs/admin_interface.md"* — unrelated TODO, flagged only so it is not accidentally touched/deleted
  while editing this file for the registration-column changes above.

---

## H. Webhooks and events

- `student_management/models.py:66-94` `UserCourseRegistration.save()` — fires `course.registered`
  on `is_new` (`_state.adding`, `:67`) with payload `{user_id, user_email, course_id, course_title,
  registered_at}` (`:87-93`). **No registration id in the payload today.** Once multiple registrations
  per user+course are possible, a webhook consumer (e.g. an external CRM/LMS-adjacent system) cannot
  distinguish "first-time registration" from "renewal registration" from the payload alone — both fire
  the identical shape. The payload should almost certainly gain `"registration_id": str(self.id)` at
  minimum, and arguably a `is_renewal: bool` or a `previous_registration_id` signal, once the spec phase
  decides how renewals are modelled (new row vs. reactivated row).
- `student_interface/views.py:1080-1091` — `course.completed` fired from `course_finish`, payload
  `{user_id, user_email, course_id, course_title, completed_time}` (`:1084-1090`) — **also has no
  registration id**, and is read off `course_progress.completed_time` (`:1076-1078`) which is the
  exact model instance affected by §B.1's `get_object_or_404` bug. Fixing the `get_object_or_404` call
  to be registration-scoped (§B.1) and adding `registration_id` to this payload are two edits to the
  same 20 lines — do together.
- `freedom_ls/base/webhook_event_types.py:1-28` — `FLS_WEBHOOK_EVENT_TYPES` defines only
  `user.registered`, `course.completed`, `course.registered` — no `course.progressed` /
  `course.attempt.completed` event exists today, so there is no third payload to worry about for
  now, but any new event added as part of this change (e.g. `course.re-registered`) must get a
  sample added to `WEBHOOK_EVENT_TYPE_SAMPLES` in the same file (enforced by
  `webhooks/tests/test_event_samples.py:9-17`, which asserts every event type has a sample) and does
  not need a migration (`webhooks/views.py:29` reads the choices from the setting directly).
- `webhooks/events.py:10-19` `fire_webhook_event` — no changes needed; it is payload-shape-agnostic.

---

## I. Interaction with in-flight and queued specs

- **`2. in progress/basic_reports/idea.md`** — wants a per-cohort PDF report showing, per student,
  "how much of the course they have completed", "what item they completed last, and when", and
  per-quiz "latest score and number of attempts" (`idea.md:16-19`). Every one of these reads is exactly
  the `(user, course)`-keyed data this project is repointing to `(registration)`. **Sequencing risk**:
  if `basic_reports` is built against today's `(user, course)` model and this project lands after, the
  report either needs a registration picker (mirroring the cohort matrix's `_get_selected_registration`,
  `educator_interface/views.py:266-280`) or will silently report on an arbitrary registration once
  `CourseProgress` is no longer 1:1 with `(user, course)`. Recommend explicitly sequencing this project
  *before* `basic_reports`, or scoping `basic_reports`'s first cut to the (then-still-valid) assumption
  of one registration per student, with a documented follow-up.
- **`2. in progress/content_snapshots/0. idea.md`** — standalone `content_snapshots` app, explicitly
  scoped to have "no imports from apps other than `content_engine`, `accounts`, and
  `site_aware_models`" (`0. idea.md:75`). No direct collision — it snapshots `content_engine` objects,
  not progress — but if a future consumer wants to record "which snapshot of a Form a learner's
  `FormProgress` attempt was actually filled against" (a natural pairing, given content can change
  between a learner's first and second registration/attempt), that FK would land on `FormProgress`,
  which is exactly the model being touched here. Worth a one-line note in this project's spec that a
  `FormProgress.content_snapshot` FK is plausible future work, not in scope now.
- **`1. next/certificates/idea.md`** — "verifiable, tamper-evident certificates with a public verify
  URL" (`idea.md:1-3`), effectively no detail yet. A certificate is almost certainly minted off a
  `CourseProgress.completed_time` event — once that event is registration-scoped, a certificate needs
  to reference *which* registration/completion it certifies (relevant for the renewal scenario: a
  second certificate for a second completion of the same course). Directly depends on this project
  landing first, or at minimum on the two projects agreeing on the registration FK shape before
  `certificates` is spec'd.
- **`1. next/xapi_implementation/0. idea.md`** — wants to `track(user, verb, object, result=...)`
  events including `registered` and `progressed` (`0. idea.md:26-38, 59-66`). An xAPI "registered"
  statement and a "completed" statement both need a way to disambiguate which registration/attempt they
  belong to once multiplicity is possible — same shape of problem as the webhook payloads in §H.
  Recommend the xAPI spec phase read this document's §H before finalising its event schema, since both
  will independently want a `registration_id`-equivalent field.
- **`1. next/compliance-exam-remediation/idea.md`** — "structured corrective-content loop" for
  wrong quiz answers, with per-question explanations (`idea.md:1-8`). This reads `FormProgress`/
  `QuestionAnswer` at the *attempt* level, which is already multi-row today (each attempt is its own
  `FormProgress` row, `unique_together` only applies to `TopicProgress`/`CourseProgress`, not
  `FormProgress`). Low collision risk — `FormProgress` doesn't need a uniqueness constraint relaxed,
  only (per §B.3/B.4) potentially gain a `registration` FK for scoping which registration an attempt
  belongs to. compliance-exam-remediation should be largely insulated from this change as long as it
  keys its own reads off `FormProgress.id`/`form_progress` FK rather than `(user, form)`.
- **`0. drafts/deadline-setting-for-cohorts/`** — directory not found (glob returned no files); no
  idea/spec exists at this path today, nothing to cross-reference. (Note: cohort/student deadline
  functionality already exists and ships — see `CohortDeadline`/`StudentDeadline` in
  `student_management/models.py:126-217` — this draft folder may be a stale or renamed reference; flag
  for the spec author to confirm whether this refers to already-shipped functionality or a genuinely
  separate future draft.)
- **Consistency win**: `CohortDeadline`, `StudentDeadline`, `UserCohortDeadlineOverride` (§0 above)
  already hang off `CohortCourseRegistration`/`UserCourseRegistration`, not off `(user, course)`. This
  project makes `TopicProgress`/`FormProgress`/`CourseProgress` follow the exact same pattern the
  deadline models already established — **this is not a novel architecture for FLS, it is completing
  a pattern that's already half-adopted.** The spec phase should explicitly hold up the deadline models
  as the reference implementation (FK shape, `Meta.constraints` style with `condition=Q(...)`,
  `get_effective_deadlines`'s per-registration resolution loop in `deadline_utils.py:36-87`) rather than
  inventing a new shape for progress.

---

## J. Product documentation — statements that become false

`docs/product/learner-tracking.md`:
- `:15` *"**Per topic** — one record per learner per topic..."* → becomes "one record per learner per
  topic **per registration**" (or equivalent) — the per-topic singleton claim is exactly what §B.4
  removes.
- `:21` *"**Per course** — one record per learner per course, created when they register."* → becomes
  "one record per **registration**" — same change, course-level.
- `:23-25` *"Progress Percentage... recalculates automatically the first time an item is marked
  complete."* — mechanically still true, but the underlying "global per-user completed set" described
  in §C changes meaning; the doc's implicit assumption that "an item marked complete" unambiguously
  belongs to one course/percentage calculation no longer holds once the same topic can belong to
  multiple registrations (renewal) or multiple courses (modular courses, per the brief's forward-looking
  note).
- `:27` *"Bulk database updates that bypass the normal save path do not trigger recalculation. The
  `recalculate_progress_percentages` management command..."* — command still exists but its internals
  change per §E; the doc's description of *what* it recomputes ("every course's percentage") should
  become "every registration's percentage".

`docs/product/educator-interface.md`:
- `:49` *"The Course Progress tab on a cohort detail page shows a paginated matrix of students (rows)
  against course items (columns)."* — already implicitly registration-scoped via the
  `CohortCourseRegistration` picker (`educator_interface/views.py:266-280`, already supports multiple
  registrations *per cohort*, just not multiple *per student* within one registration) — this
  statement stays true as written, but the underlying per-cell progress lookup (`_fetch_progress_maps`,
  `views.py:342-383`) needs the fix in §A/§B.2 to stay correct once a student can have progress against
  more than one registration of the *same* course simultaneously (direct + cohort scenario from the
  brief) — the matrix would otherwise conflate the two.
- No other statements in this file are directly falsified — the panel/access-control/limits sections
  are registration-model-agnostic prose.

---

## Change budget

Ordered roughly by dependency (each item depends on the ones above it being decided/landed first).

1. **(S) Decide the registration-uniqueness relaxation.** Product/spec decision on how
   `UserCourseRegistration`'s `unique_user_course_registration` constraint (§B.4) changes — full drop,
   or partial-unique-on-`is_active`. Same decision needed for `CohortCourseRegistration`. This is a
   design decision, not code, but it gates everything else — put it first in the spec, not the plan.
2. **(M) Model migration: add `registration` FK to `TopicProgress`, `FormProgress`, `CourseProgress`;
   relax/replace the three `unique_together`s (§B.4).** Needs a data migration to backfill
   `registration` on every existing row (derivable: one active `UserCourseRegistration` or
   `CohortCourseRegistration` per user+course exists today, by construction of the current
   constraints, so backfill is unambiguous *for existing data* — this is the one part of the migration
   that's actually easy).
3. **(M) `update_course_progress_on_completion` rewrite + fold in both `@claude` TODOs (§C).** Signature
   gains a registration parameter; completed-item lookups become registration-scoped; `CourseItemProgress.
   __init__`/`.save()` gain registration-awareness in the same pass.
4. **(L) `student_interface` read-path fixes (§A, §B.1, §B.2).** `course_finish`'s
   `get_object_or_404` (loud break, must fix), `get_resume_index`, `_detail_cta_label`,
   `_player_chrome_context`, `_fetch_player_progress_maps`, `get_completed_courses`/
   `get_current_courses`/`get_course_listing`'s course_id-keyed dicts, and the `get_or_create` call
   sites in `view_course_item`/`view_topic`. This is the largest single unit — it's the whole player
   and dashboard read surface, and per the product decision ("keep existing UI correct") it must not
   regress observable behaviour for the common single-registration case while becoming correct for the
   multi-registration case. Needs a decision on **which registration drives the player/dashboard when
   more than one is active** (most-recent? explicitly selected? — no existing helper answers this, per
   §D).
5. **(M) `educator_interface` cohort progress-matrix fixes (§A, §B.2).** `_fetch_progress_maps`'s
   `(user_id, item_id)` keys, `_paginate_students`'s `Subquery(...)[:1]` — needs a registration
   parameter threaded from the already-selected `selected_reg` through to every progress lookup.
6. **(S) Admin: add `registration` column to the three `student_progress` admins (§G).**
7. **(S) Webhook payloads: add `registration_id` to `course.registered`/`course.completed` (§H).**
8. **(M) Factories + test fixups (§F).** ~130+ call sites across 19 test files, mechanical but wide;
   do this incrementally per-app as each app's production code lands, not as one giant sweep.
9. **(S) Management commands: `recalculate_progress_percentages`, the three `qa_helpers` commands with
   multi-site call sites (§E).**
10. **(S) Product docs: `learner-tracking.md`, `educator-interface.md` updates (§J).**
11. **(XS–S, opportunistic) `qa_helpers/create_demo_data.py` re-verification** — flagged unresolved in
    §E; the spec phase should trace this file's data-loading path before committing to a size estimate.

Not budgeted here (explicitly out of scope per the product decision): any new attempt-history UI,
any renewal/re-registration *workflow* UI (only the underlying model support), and the "modular courses
reuse items across courses" future scenario beyond ensuring the new uniqueness keys don't foreclose it.

---

## Landmines

1. **`course_finish`'s `get_object_or_404(CourseProgress, user=, course=)` (`student_interface/views.py:1071-1073`)
   is a live 500 waiting to happen the day this ships**, not a slow-burn correctness bug — it is a hard
   crash on course completion for exactly the population this feature serves (learners with >1
   registration). Must be in the first PR that touches read paths, not deferred.
2. **Silent last-write-wins dict collapses** (`utils.py:648-651`, `utils.py:771-776`,
   `educator_interface/views.py:324-329`'s `[:1]` subquery) produce *plausible-looking wrong numbers* —
   a dashboard that shows 40% instead of 85% for a renewed course, with no error, no log line, nothing
   to grep for in production. These are more dangerous than the `MultipleObjectsReturned` crash because
   nothing will alert anyone that they're wrong. Needs deliberate test coverage asserting *which*
   registration's data appears where, not just "does it 500".
3. **The `UserCourseRegistration` uniqueness relaxation (§B.4 point 1) has no obvious "right answer"
   already encoded anywhere in the codebase** — there is no unregister flow, no "reactivate" flow, no
   existing UI concept of a learner having two rows for one course. Whatever the spec decides here is
   genuinely new product surface, not a mechanical extraction of an existing pattern (unlike the
   deadline-model precedent in §I, which the progress-model FK shape *can* copy).
4. **`FormProgress.get_or_create_incomplete` (`student_progress/models.py:175-188`) and
   `get_latest_incomplete`/`finalise_stale_incomplete`** are used across *all* of `view_form`,
   `form_start`, `form_fill_page`, `form_submit_and_exit` (`student_interface/views.py:757-762, 812,
   837, 1129-1131`) to find "the" in-progress attempt for `(user, form)`. If a form/topic can be shared
   between two of a learner's registrations (renewal reusing the same course content, or the brief's
   "modular courses" reusing items across courses), an in-progress attempt started under registration A
   could be silently resumed/finalised under registration B's context if the registration scoping isn't
   threaded through *all four* of these call sites consistently — a partial fix (e.g. scoping
   `get_or_create_incomplete` but not `get_latest_incomplete`) would reintroduce the bug asymmetrically.
5. **Test coverage for "two registrations, same course, same user" essentially does not exist today** —
   grep found no test file constructing two `UserCourseRegistration` rows for the same user+course
   (the current unique constraint makes this impossible to write anyway). Every new test for this
   feature is *net-new* test surface, not a modification of an existing test's assertions — budget
   accordingly; §F's "mechanical update" estimate for the 19 existing files is separate from, and
   smaller than, the new-test-writing effort for the actual multi-registration behaviour.

status: ok
