# Research: where form code lives today, and how course-bound each piece is

## Executive summary

**The definition and attempt layers are close to course-free already; the request layer is where all
the coupling is.** `FormProgress` and `QuestionAnswer` are keyed `(user, form)` with no `Course` FK
anywhere (`learner_progress/models.py:76-502`), `scoring.py` (36 lines) and `submissions.py`
(32 lines) are pure, and the per-question template partials in `course_form_page.html` take nothing
course-shaped. The single course coupling in the whole `learner_progress` app is
`signals.py:35`, one `post_save` receiver. What is genuinely course-bound is **identity and
authorisation**: all five form routes are `courses/<slug>/<index>/…`, the only resolver is
`get_form_for_index(course, index)` (`learner_interface/utils.py:748`), and every gate on answering
a form is a *course* gate (`views.py:577`). A form has no URL, no `preview_url()`, and no
permission concept of its own. Ordered by difficulty, the extraction work is: models and scoring
(trivial) → templates and JS (easy, already isolated) → views/URLs/authorisation (the real cost) →
reports (moderate, well-layered) → the completion signal (small, needs one new signal).

---

## 1. Definition — `content_engine`

| Location | Form share | Notes |
|---|---|---|
| `models.py:17-36` | `QuestionType`, `FREE_TEXT_QUESTION_TYPES`, `FormStrategy` | Enums, no dependencies on course concepts |
| `models.py:421-567` | `Form`, `FormPage`, `FormContent`, `FormQuestion`, `QuestionOption` | 147 of 605 lines |
| `schema.py:223-332` | `Form`, `FormPage`, `QuestionOption`, `FormContent`, `FormQuestion` pydantic models | ~130 of 336 lines |
| `admin.py:21-127, 236-259` | 5 ModelAdmins + 4 inlines | ~180 of 279 lines; **zero cross-references to the course admins** |
| `factories.py:71-132` | 5 factories | Cleanly separable, but 20+ external test modules import course and form factories from the same module |
| `management/commands/content_save.py:355-417` | `save_form`, `save_form_page`, `save_form_content`, `save_form_question` | 4 of 9 save functions |
| `management/commands/content_save.py:144-190` | `update_file_with_option_uuids` | Form-only: back-writes `QuestionOption` UUIDs into the page YAML |
| `templatetags/content_tags.py` | one `Form` reference | `get_content_by_path` tries `Topic`, falls back to `Form` |
| `templates/cotton/content-link.html` | one comment | *"It can be a Topic or a Form"* |

**Not form-related at all** — these would not move and are worth naming so a plan does not go
looking: `checks.py`, `config.py`, `course_accent.py`, `icon_validation.py`. `content_engine`'s only
setting (`COURSE_ACCESS_CONFIG_VALIDATOR`) is course-side, so a forms app needs no `config.py` on
day one.

### Model shapes

```
Form(TitledContent, MarkdownContent)      strategy, quiz_show_incorrect,
                                          quiz_pass_percentage, submit_on_exit
FormPage(TitledContent)                   form FK, order, category
FormContent(MarkdownContent)              content, form_page FK, order
FormQuestion(BaseContent)                 form_page FK, order, category,
                                          question, type, required
QuestionOption(SiteAwareModel)            question FK, text, value, order, correct
```

Four of five inherit `content_engine`'s abstract bases (`models.py:55-143`), which is the coupling
the prior research correctly identified as the hardest single question — answered in
`research_extraction_mechanics.md` §1 by moving the bases to a `content_base` app. Only
`QuestionOption` is a plain `SiteAwareModel`.

Note the smell inside the inheritance rather than across it: `BaseContent` contributes
`file_path`/`meta`/`tags`, and `TitledContent` contributes `slug`. A `FormPage` is not its own file
and does not need `file_path`; a `FormQuestion` is not titled and correctly extends bare
`BaseContent`, but still carries `file_path`. These fields exist because forms are authored as files
today, not because the models need them.

### Authoring on disk

`demo_content/` has six forms, all nested inside a course:

```
demo_content/functionality_demo_end_with_quiz/3. quiz/{form.md, 1. page.yaml, 2. another page.yaml}
demo_content/functionality_demo_end_with_topic/4. survey/{form.md, 1. page.yaml}
demo_content/functionality_demo_course_parts/02. Core Concepts/03. knowledge-check/…
```

`form.md` is markdown with `content_type: FORM` frontmatter; pages are multi-document YAML where the
first document is the `FORM_PAGE` and each subsequent document is derived to `FORM_CONTENT` or
`FORM_QUESTION` by `FormPage.derive_content_type` (`schema.py:274-278`).

**Can a form stand alone on disk?** Mechanically yes — the loader groups by `content_type` and saves
every `FORM` it finds regardless of nesting. Practically no: there is no route to reach it, no
`preview_url()`, and the authoring contract in
`claude_plugins/fls-content/skills/content-types/resources/form-files.md` describes only the nested
form.

---

## 2. Attempt and marking — `learner_progress`

| Model | Lines | Keyed by | Course FK? |
|---|---|---|---|
| `CourseItemProgress` (abstract) | `models.py:36-75` | — | no |
| `FormProgress` | `models.py:76-482` | `(user, form)` | **no** |
| `QuestionAnswer` | `models.py:483-502` | `(form_progress, question)` unique | **no** |
| `TopicProgress` | `models.py:503-526` | `(user, topic)` unique | no |
| `CourseProgress` | `models.py:527-571` | `(user, course)` | yes — this is the course layer |

`FormProgress` is 407 lines, the largest model in the codebase. Multiple attempts are permitted (no
unique constraint); "the attempt" is always resolved by ordering. `qa_helpers`'
`qa_complete_form.py` creates a `FormProgress` from only a site, form and user — proof the data
layer already works without a course.

**Marking, in full, and all of it course-free:**

- `scoring.py` — `is_quiz_answer_correct(selected_option_ids, options)` (exact match;
  `correct is True` required, `False` forbidden, `None` ignored) and a query-free bulk
  `evaluate_quiz_answers` used by reports.
- `FormProgress.score()` (`models.py:406`) — a hard-coded if/elif on `self.form.strategy`, raising
  on an unknown strategy. No registry, no pluggability. `score_category_value_sum()`
  (`models.py:235`) builds a nested category tree from `FormPage.category` + `FormQuestion.category`
  and sums `QuestionOption.value`; `compute_quiz_scores()` (`models.py:363`) is a read-only rescore;
  `score_quiz()` (`models.py:399`) writes `self.scores`.
- `quiz_percentage()` (`models.py:101`), `passed()` (`models.py:117`, reads
  `form.quiz_pass_percentage`), `get_incorrect_quiz_answers()` (`models.py:416`).
- Lifecycle: `get_or_create_incomplete`, `get_latest_incomplete`, `finalise_stale_incomplete`
  (honours `Form.submit_on_exit`), `complete()` (idempotent: sets `completed_time`, calls `score()`).
- Answer capture: `submissions.py` — `submitted_option_ids`, `submitted_text_answer`,
  `has_submitted_answer`, all pure POST parsing on the `question_{id}` naming convention;
  `FormProgress.save_answers` (`models.py:204`) deletes the row when a question is submitted blank.

Scores are frozen at submission and never rescored; `course_form_complete` re-derives via
`compute_quiz_scores()` only to flag drift (`stored_score_outdated`).

**The seam, already correctly shaped.** `queries.py:28` `completed_form_ids_by_user(user_ids)`
returns `{user_id: {form_id}}`, and `queries.py:10` `attempt_completes_form(attempt)` encodes "a
failed scored quiz is not done". Course code asks *which forms are done*; form code never asks about
courses.

**The one coupling.** `signals.py:35` `update_course_progress_on_completion` is a `post_save`
receiver on `FormProgress` and `TopicProgress` that walks `ContentCollectionItem` up to
`Course`/`CoursePart`, calls `learner_management.utils.calculate_course_progress_percentage()`, and
does `CourseProgress.objects.update_or_create(...)`. It already returns early when no parent course
is found, so an orphan form is safe today — just silently unaccounted. The module carries a
`# @claude` note asking for a `form.courses()` helper.

---

## 3. Player — `learner_interface`

### URLs — every one course-scoped

```
courses/<slug:course_slug>/<int:index>/                          view_course_item
courses/<slug:course_slug>/<int:index>/start_form                form_start
courses/<slug:course_slug>/<int:index>/fill_form/<int:page_number>  form_fill_page
courses/<slug:course_slug>/<int:index>/complete                  course_form_complete
courses/<slug:course_slug>/<int:index>/submit-and-exit           form_submit_and_exit
```

`urls.py:58-72` preserves, commented out, an earlier form-first design
(`forms/<slug:form_slug>/`, `form_progress/<uuid:pk>/<int:page_number>/`) that was abandoned. It is
the clearest evidence that the current shape is a choice rather than a constraint.

### Views — `views.py`

| Function | Line | Course dependence |
|---|---|---|
| `_course_access_redirect` | 577 | `raise_404_if_hidden_unregistered` + `get_course_access_backend().get_access(user, course)` — **the only authorisation gate that exists** |
| `_blocked_item_redirect` | 593 | sequential unlock via `current_entry_status(get_course_index(...))` |
| `view_course_item` | 621 | dispatches Topic vs Form by `isinstance`; writes `CourseProgress.last_accessed_item` |
| `_player_chrome_context` | 730 | TOC, breadcrumb part, `CourseProgress`, organisation |
| `view_form` | 832 | start screen; needs `course`, `index`, `is_last_item`, `next_url` |
| `form_start` | 895 | course lookup → access gate → `get_form_for_index` → block gate → mint attempt |
| `form_fill_page` | 940 | the runner; same three gates, then paging, `save_answers`, required-question validation (422) |
| `course_form_complete` | 1148 | results; percentage, `quiz_verdict`, drift flag, `next_url`/`retry_url` |
| `form_submit_and_exit` | 1299 | POST-only finalise for `submit_on_exit` |

Strip the course machinery and the generic core is small: resolve form → resolve page → render
children → `save_answers` → validate required → advance or `complete()`. Everything else —
`course_slug`, `index`, the access backend, sequential unlock, deadlines, player chrome, next/retry
URLs — is context, and today that context has exactly one implementation.

`apis.py` (136 lines) is entirely commented out: a dead Ninja sketch for form progress.

### Utils — `utils.py`

- `get_form_for_index(course, index, viewable_items=None)` (748) — the single resolver; 404s if the
  item at that index is not a `Form`.
- `quiz_verdict(form, form_progress)` (147) — form-only, guards against `passed()` raising on a null
  pass mark. **Misfiled: belongs with forms.**
- `count_form_questions(form)` (739) — form-only. **Misfiled.**
- `unpassed_forms(user, course)` (117) + `UnpassedForm` — course-scoped, stays.
- `get_content_status(...)` (165) — the TOC status machine; the `Form` branch maps to
  `COMPLETE`/`FAILED`/`IN_PROGRESS`/`READY`/`BLOCKED`, and `FAILED` forces the next item to
  `BLOCKED`. This is what makes a failed quiz gate the rest of a course — course policy expressed in
  terms of a form result, correctly on the course side.

### Templates and JS

| File | Lines | Course-bound? |
|---|---|---|
| `course_form_page.html` | 581 | **No, apart from context URLs.** Self-contained `{% partialdef %}` blocks: `form-input-multiple-choice`, `form-input-checkboxes`, `form-input-short-text`, `form-input-long-text`, `form-question`, `form-content` |
| `_exam_runner_base.html` | 31 | **No** — chromeless base, "no sidebar, no course TOC". Already the reusable piece |
| `course_form.html` | 80 | Yes — every button reverses a course-slug URL |
| `course_form_complete.html` | 254 | Mostly no; one hard-coded `{% url 'learner_interface:view_course_item' … index=1 %}` at line 245 |
| `partials/form_progress_scores.html`, `exam_meta_grid.html`, `exam_previous_attempts.html`, `exam_score_ring.html` | | Results widgets, generic |
| `static/learner_interface/js/alpine-components.js` | | `examRunnerForm`, `examRunner`, `examExitDialog`, live answered-count, `beforeunload` guard — course-agnostic |

---

## 4. Consumers

**`educator_interface`** — attempt-level only, no question-level data. `_fetch_progress_maps` (378)
bulk-loads `FormProgress` keyed `(user_id, form_id)` ordered
`F("completed_time").desc(nulls_last=True), "-start_time"` (deliberately different from
`learner_interface`'s ordering). `_build_form_cell` (498) branches on `item.strategy == "QUIZ"` then
reads `quiz_percentage()`/`passed()`. `_fetch_deadline_data` (421) calls
`DjangoContentType.objects.get_for_model(Form)` at line 438 — **a content-type lookup that a
cross-app move must not break.**

**`reports`** — the only question-level consumer, and the best-layered. `indexes.py` holds all ORM
(`load_quiz_questions` 403, `build_question_index` 428, `load_selected_options_by_pair` 460,
`build_sat_questions` 486, `load_distractor_rows` 540, plus the `FormProgressIndex` folders);
`gather.py` is pure transformation; `report_data.py` is frozen dataclasses. The entry point is the
problem, not the layering: `build_course_catalogue` (211) goes Cohort → `CohortCourseRegistration` →
`Course.viewable_items()`, so quizzes are discovered only by walking courses. A form-first entry
(a set of form ids) is the change needed, and `indexes.py`'s split from `gather.py` makes it cheap.
`at_risk.py` has one rule, `failed_latest_quiz`.

**`learner_management`** — `deadline_utils.py:12` imports `Course, CoursePart, Form, Topic`;
`content_item: Topic | Form | CoursePart` at lines 39 and 396. The three deadline models attach to a
`Form` via GenericFK but are always scoped to a `CohortCourseRegistration`.

**`qa_helpers`** — roughly 16 management commands import `Form`, the form factories, `FormStrategy`
or `QuestionType`.

**`freedom_ls/conftest.py:204-212`** — the project-wide `course_with_scored_quiz` fixture.

**`webhooks`** — `FLS_WEBHOOK_EVENT_TYPES` (`base/webhook_event_types.py`) has
`user.registered`, `course.completed`, `course.registered`. **No form or quiz events exist.**

**`xapi_learning_record_store`** — models entirely commented out; emits nothing. The commented sketch
anticipates `result.score.scaled`, so it is a future consumer, not a current one.

**`config/`** — no form imports. Only `config/sitemaps.py:15` imports `Course`.

**`claude_plugins/fls-content/validate/schema.py`** — a hand-patched bundled copy of
`content_engine/schema.py`, containing every form pydantic model verbatim. Re-synced via
`/fls-dev:update_claude_plugin_fls_content`.

---

## 5. The ten places that assume a form is reached through a course

1. All five form routes are `courses/<slug>/<index>/…` (`learner_interface/urls.py:27-44`).
2. `get_form_for_index(course, index)` (`utils.py:748`) is the only resolver in the request path.
3. `_course_access_redirect` (`views.py:577`) is the only authorisation gate — applied to
   `form_start`, `form_fill_page`, `course_form_complete`, `form_submit_and_exit`,
   `view_course_item`. **There is no form-level permission anywhere**;
   `role_based_permissions/` and `course_access/` contain zero `Form` references.
4. Sequential unlock: `_blocked_item_redirect` / `get_course_index` / `current_entry_status`, all
   derived from the course TOC.
5. `Form` has no `preview_url()` (only `Topic` has one, `models.py:155`), so
   `cotton/content-link.html` cannot link a bare form.
6. `content_engine` has no `urls.py` or `views.py` — it is storage only, so no route into a `Form`
   exists outside the player. (`Topic.preview_url()` reverses `content_engine:topic_detail`, but no such
   URLconf exists — the only content_engine include in `config/urls.py` is a commented-out
   `content_preview` line — so it would raise `NoReverseMatch` today.)
7. Deadlines attach to a `Form` by GenericFK but always through a `CohortCourseRegistration`.
8. `learner_progress/signals.py` traces `ContentCollectionItem` up to a `Course` on every form
   completion.
9. `reports/indexes.py:211` `build_course_catalogue` discovers quizzes only via
   `CohortCourseRegistration.collection.viewable_items()`.
10. `learner_management/models.py:368` has a commented-out `form_progress` FK on `RecommendedCourse`
    — *"Created when a parent fills out a form"* — an abandoned earlier attempt at exactly the
    non-course form use case this idea is about.

---

## 6. What this implies for an extraction plan

**Already clean, moves with no rewrite:** `FormProgress`, `QuestionAnswer`, `scoring.py`,
`submissions.py`, every `FormProgress` scoring and paging method, `quiz_verdict()`,
`count_form_questions()`, the `course_form_page.html` question partials, `_exam_runner_base.html`,
the Alpine runner.

**Needs one new signal:** `signals.py` subscribes to `form_attempt_completed` instead of
`post_save` on a model in another app. Small, but it must be explicit or `form_engine` ends up
importing `Course`.

**Needs design, and is the real cost:** form identity (slug route, `preview_url()`), a
context/authorisation seam to replace `_course_access_redirect`, and lifting the ~15 context keys
`form_fill_page` builds into something a non-course caller can supply. Roughly half of those keys
are course chrome.

**Needs a new entry point:** `reports` from a set of form ids rather than a cohort.

**Difficulty order:** models and scoring (trivial) → templates and JS (easy) → views, URLs and
authorisation (the real cost) → reports (moderate) → the completion signal (small).

status: ok
