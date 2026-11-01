---
name: reference-clearing-form-sittings-around-an-application
description: Clearing a persona's stale FormProgress rows so every form start screen reads "Start Form" WITHOUT tripping the RESTRICT that a live CourseApplication holds on its own sitting; plus the self-registration shape for free courses
metadata:
  type: reference
---

Asked on `simple-application-forms`, Sep 2026, for `qa_applicant@email.com` (pk 73), site
DemoDev (**id 3, domain `127.0.0.1:8324`**). Two jobs in one pass: clear the QA-run form
residue, then enrol the persona in three free courses.

## The start-screen button is decided by `FormProgress` ALONE

`learner_interface/utils.py::form_start_page_buttons(form, incomplete_form_progress,
completed_form_progress, is_last_item)` looks at nothing else:

- an incomplete sitting -> "Continue Form"
- a completed sitting whose `quiz_verdict(...) is False` -> "Try Again"
- otherwise completed -> "Next" / "Finish Course"
- no sitting -> "Start Form"

`CourseFormAttempt` never enters it. So "make the placement read Start Form" is exactly
"delete the learner's `FormProgress` for that form" — deleting the join row alone would do
nothing, and there may not even be one (see below).

## `qa_reset_learner_progress` is now UNSAFE as a blunt tool on this branch

Run without `--course-slug` it does `FormProgress.objects.filter(user=...).delete()` across
every course. `CourseApplication.form_progress` is **RESTRICT**, so the moment a persona holds
a submitted application the whole reset aborts with `RestrictedError` (it fails safe, but it
fails). For an applicant persona, delete an explicit **pk list** and assert
`not CourseApplication._base_manager.filter(form_progress=fp).exists()` on each one.

RESTRICT vs PROTECT here is deliberate and documented on the model: deleting the *applicant*
must still take application + sitting away together, but the sitting can never be removed on
its own while the application stands.

## A duplicate "Application form" sitting is usually ORPHANED, not a second application

The ask assumed the older `Application form` sitting might still be referenced and that a stale
`CourseApplication` would have to go first. It was not: the apply flow re-mints a sitting and
re-points the one application at the new one (`unique_application_per_site_user_course` allows
only one row per user+course anyway). **Query before assuming a chained delete** —
`CourseApplication._base_manager.filter(form_progress=fp)` came back empty and no application
had to be touched. The `Collector` confirms it: no `CourseApplication` appeared in `c.data`.

## Blast radius of one `FormProgress.delete()`

```
survey, never answered : (1, {FormProgress: 1})
quiz, 3 answers        : (7, {QuestionAnswer_selected_options: 3, QuestionAnswer: 3, FormProgress: 1})
application, 4 answers : (7, {QuestionAnswer_selected_options: 1, QuestionAnswerFile: 1,
                              QuestionAnswer: 4, FormProgress: 1})
```

`QuestionAnswerFile` has a `post_delete` receiver
(`form_engine/receivers.py::delete_question_answer_file`) that calls `instance.file.delete()`.
Because it *has* a receiver Django cannot fast-delete it, so it shows up in `c.data` and the
stored object really is swept — verify with `af.file.storage.exists(af.file.name)` before and
after (`user_uploads/<user pk>/form_answers/<answer-file pk>.<ext>`). Grab the storage key
*before* the delete; afterwards there is no row to ask.

## No `CourseProgress` => no `CourseFormAttempt`, so "delete the join rows too" can be a no-op

This persona had 4 `FormProgress` rows and **zero** `CourseFormAttempt`, because
`CourseFormAttempt.course_progress` is non-null and the persona held no registration and
therefore no `CourseProgress` at all. Check both directions before reporting
(`form_progress__user=` and `course_progress__learner__user=`) and say plainly that the count
was already 0 — a QA plan naming rows to delete is describing what it saw in the admin, not a
guarantee they exist.

## The "ordinary self-registration shape" for a free course

`learner_interface/views.py::initiate_course_access` is the only self-service path, and it does:

```python
learner = ensure_learner(user, get_default_organisation(site))
LearnerCourseRegistration.objects.update_or_create(
    learner=learner, course=course, defaults={"is_active": True})
```

Reproduce it with `LearnerFactory(user=..., organisation=get_default_organisation(site), site=site)`
(it delegates to `ensure_learner`) + `LearnerCourseRegistrationFactory(learner=..., course=...,
site=site, is_active=True)`. Explicit `site=` on both — `SiteAwareFactory`'s site LazyFunction
returns None outside a request. The default organisation on DemoDev is named `DemoDev`
(`Organisation._base_manager.get(site=site, is_default=True)`), and the persona's existing
`Learner` row is already in it, so `LearnerFactory` returns that row rather than a second one.

The `post_save` receiver mints one `CourseProgress` per registration at
`progress_percentage=0`, `learner_registration=<reg>`, `cohort_registration=None`. It fires on
`transaction.on_commit`, which in `manage.py shell` (autocommit) runs immediately. It also
announces `course.registered`; check `WebhookEndpoint._base_manager.filter(site=..., is_active=True)`
first (0 on DemoDev) so nothing fires at an endpoint mid-QA.

## The BUTTON reads `FormProgress`; the OUTLINE reads `CourseFormAttempt`. Clear both.

Second pass, Sep 2026, same persona: "clear two sittings so the start screens read Start Form
again". The two surfaces are decided by **different tables**, which is the thing to get right:

| surface | source | function |
|---|---|---|
| start-screen button | `FormProgress` for (user, form) | `form_start_page_buttons` |
| outline item status | `CourseFormAttempt` for (course_progress, collection_item) | `_fetch_player_progress_maps` -> `get_content_status` |

`_fetch_player_progress_maps` builds `form_map` **only from attempts** (`FormPlacementProgress`
= `is_complete` via `completed_form_item_ids(attempts)`, `has_open_attempt`,
`has_completed_attempt`). Delete the `FormProgress` and leave the attempt and the outline still
calls the item COMPLETE; delete the attempt and leave the sitting and the button still says
"Next". Deleting the `FormProgress` does take the attempt with it (`CourseFormAttempt.form_progress`
is a **OneToOne CASCADE**), so one delete is enough — but it lands as a *fast delete*, so it only
shows up in `Collector.fast_deletes`, never in `c.data`.

Note the maps key on **`collection_item`**, not on the form: one form placed twice is two
placements, answered separately. Filter attempts by `collection_item_id`, not `form_id`.

## Whether clearing a form re-locks what follows: it depends on the NEXT item's own progress

`get_content_status` returns `(status, next_status)`, and a placement with progress of its own
**ignores the incoming `next_status`**: a Topic with `complete_time` returns `COMPLETE, READY`
unconditionally. So clearing a mid-course form drops it to READY and hands BLOCKED forward, but:

- items after it that hold their own completed `TopicProgress` / attempts stay COMPLETE — the
  chain heals immediately. (end-with-quiz: items 3 and 4 stayed COMPLETE and clickable.)
- the first item after it with **no progress row of its own** was only READY because the form's
  completion unlocked it, and it goes BLOCKED — taking everything past it. (end-with-topic item 4
  "Pictures" went READY -> BLOCKED, items 5-7 were already BLOCKED.)

So "will this re-lock anything?" is answered by looking at the *next unstarted* item, not by the
count of items after the form. Check it by diffing `get_course_index(user, course,
can_access_content=True)` before and after — that is the real player code and is cheap to run
twice, far better than reasoning about the branches.

## `progress_percentage` is stored and does NOT recalculate on delete

`CourseProgress.progress_percentage` for end-with-quiz stayed at **100** with the Mid course Quiz
now un-sat and READY. Nothing recomputes it on `FormProgress`/`CourseFormAttempt` delete (the
recalc hangs off completion, not deletion). Report the stale number rather than silently fixing
it — the tester's next submit rewrites it, and `qa_complete_form` is the command that recalcs
([[reference_qa_complete_form_now_recalculates]]).

## Field/import corrections that cost a round-trip this run

- `FormProgress` has **no `created_at` / `score_percentage`**: it is `start_time`,
  `last_updated_time`, and `scores` (a JSONField, e.g. `{'score': 3, 'max_score': 6}`, or
  per-category dicts for a survey). Percentage comes from the `quiz_percentage()` method.
- **`Form` lives in `form_engine.models`**, not `content_engine.models` — the latter exports
  `Course`, `Topic`, `CoursePart` but not `Form`, and the import raises.
- `uv run python manage.py shell < script.py` needs the project root as cwd; agent bash calls
  reset cwd between invocations, so use
  `uv run --project <root> python <root>/manage.py shell < script.py`.

## Cascade shape of one course-sat sitting (add to the table above)

```
quiz sitting, 6 answers : loaded {FormProgress: 1, QuestionAnswer: 6}
                          fast   {QuestionAnswer_selected_options: 6, CourseFormAttempt: 1}
3 sittings (6+3+2 answers) deleted together:
  (25, {QuestionAnswer_selected_options: 11, QuestionAnswer: 11, FormProgress: 3})
```

The persona holds **two** `CourseApplication` rows and only one names a sitting
(`advanced-product-analytics-masterclass` has `form_progress=None` — it is the gated-but-names-no-form
fixture from [[reference_application_forms_qa_baseline]]). Assert
`not CourseApplication._base_manager.filter(form_progress=fp).exists()` per fp rather than
"the persona has an application, so be careful" — most of their sittings are unreferenced.

## This is now a command — use it instead of scripting the delete

`qa_clear_form_sittings --learner EMAIL [--course-slug SLUG]... [--item-title TITLE]...
[--keep-pk UUID]... [--dry-run]`
(`freedom_ls/qa_helpers/management/commands/qa_clear_form_sittings.py`, written on the fourth
ask). Placement-scoped, skips sittings a `CourseApplication` names rather than aborting, leaves
`TopicProgress`/`CourseProgress` alone, prints the resulting outline. Always `--dry-run` first;
it lists each `FormProgress` with its scores and the attempt pks that will go with it.

## Import/field drift on this branch (re-checked Sep 2026)

`CourseApplication` has moved OUT of `form_engine` into its own app:
`from freedom_ls.course_applications.models import CourseApplication`
(`freedom_ls/course_applications/{models,factories}.py`; the old import raises
`ImportError: ... Did you mean: 'course_applications'`). `FormProgress` is still in
`freedom_ls.form_engine.models`.

`CohortMembership` has **no `user` FK** — it is `(cohort, learner)`. Any purge script must
filter `CohortMembership._base_manager.filter(learner__user=u)`; `filter(user=u)` raises
`FieldError: Cannot resolve keyword 'user' ... Choices are: cohort, learner, site, ...`.

`Course` has no `status` / `access_type` attribute: visibility is `Course.visibility`
(`"published"`) and the gating lives in the `access_config` JSON
(`{"access_type": "application_gated", "application_form": "<path>"}`) alongside the
resolved `application_form` FK.

## Fifth ask (Sep 17 2026, `form_engine_data_field`): the command fit unchanged

`qa.applicant.a@email.com` (pk 71), DemoDev (**id 3, domain `127.0.0.1:8000`** — note the domain
moved from `:8324`; dev server was on 8890, so do not infer the Site row from the port).
One flag set did the whole job, no scripting of the delete:

```
qa_clear_form_sittings --learner qa.applicant.a@email.com \
  --course-slug functionality-demo-show-end-with-topic \
  --item-title "Course Feedback Survey" --site-name DemoDev [--dry-run]
```

`--item-title` matches **`item.child.title`** (the Form's title), not any attribute of the
`ContentCollectionItem`. Cascade of one completed survey sitting with 3 answers:
`(8, {QuestionAnswer_selected_options: 3, CourseFormAttempt: 1, QuestionAnswer: 3, FormProgress: 1})`
— here the attempt *did* show in the counts rather than being a silent fast delete.

The persona's other sitting (`Application form`) is named by a `CourseApplication`, and the
placement scope excluded it before the RESTRICT skip ever mattered. Scope by item first; the skip
is a backstop, not the plan.

### Field names that raise on this branch (all cost a round-trip this run)

- **`Form` has no `uuid` field.** The pk *is* the UUID: `Form._base_manager.get(pk="7ed91f7d-...")`.
  `filter(uuid=...)` -> `FieldError ... Choices are: ..., id, meta, pages, quiz_pass_percentage,
  quiz_show_incorrect, site, slug, strategy, submit_on_exit, subtitle, tags, title, ...`.
  A QA ask saying "uuid 7ed9..." means the pk.
- **`ContentCollectionItem` has no `title`.** `FieldError`/`AttributeError: ... Did you mean: 'site'`.
  Read the title off `item.child.title`.
- **`TopicProgress` has no `learner` FK** — it hangs off the course progress:
  `TopicProgress._base_manager.filter(course_progress__learner__user=u)`. Its fields are
  `collection_item, complete_time, course_progress, last_accessed_time, site, start_time, topic`.
  Completion is **`complete_time`**, not `completed_time` (which is what `FormProgress` uses).
- **`form_start_page_buttons(form, incomplete_form_progress, completed_form_progress, is_last_item)`**
  takes a **QuerySet** for the completed arg (it calls `.first()` on it) and a single instance or
  None for the incomplete one. Passing `.first()` for both raises
  `AttributeError: 'NoneType' object has no attribute 'first'`.

### Re-locking downstream is still the thing to flag, not fix

end-with-topic again: item 3 went COMPLETE -> READY ("Start Form" confirmed by calling
`form_start_page_buttons` directly), items 1-2 stayed COMPLETE on their own `TopicProgress`, and
item 4 "Pictures" went **READY -> BLOCKED** because it holds no progress row of its own. Same shape
as the second pass above. `CourseProgress.progress_percentage` stayed stale at **43**. Report both;
the caller asked only about items 1-3 and neither is in scope to "fix".

## Sixth ask (Sep 17 2026): same flags, repeat after a re-sit — no drift

The tester re-completed the survey and asked for the identical clear a second time. The exact
command from the fifth ask above worked unchanged; **this ask is now routine — dry-run, run,
verify, done.** Two deltas worth noting:

- **Cascade counts vary with how many questions were answered.** The re-sit answered 6 questions,
  not 3: `(11, {QuestionAnswer_selected_options: 3, CourseFormAttempt: 1, QuestionAnswer: 6,
  FormProgress: 1})` vs `(8, {... QuestionAnswer: 3 ...})` the first time. Don't treat a
  previously-recorded count as the expected one — read it off `.delete()`.
- **`CourseApplication` has NO `status` field.** `AttributeError: 'CourseApplication' object has
  no attribute 'status'`. Full field list: `site, id, user, course, form_progress, created_at,
  updated_at`. There is no application state machine on this branch — "has an application" is just
  "a row exists", and "names a sitting" is `form_progress_id is not None`.

Verified post-state each time with: survey `FormProgress` list empty, `CourseFormAttempt` for
(user, course) empty, `form_start_page_buttons(...)` -> `[{'text': 'Start Form', 'action': 'start'}]`,
and registration / CourseProgress / both TopicProgress rows unchanged. `progress_percentage`
stale at **43** again (unchanged behaviour — nothing recomputes on delete).
