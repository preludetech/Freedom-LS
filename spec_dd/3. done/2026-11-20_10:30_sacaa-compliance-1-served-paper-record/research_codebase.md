# Research: codebase seams for the served paper record

Paths are under `freedom_ls/` unless noted. Read at HEAD 53fb74dfe. This note builds on
`spec_dd/1. next/sacaa-compliance/research_form_engine_seams.md` (cited as "seams") and only adds
what that note does not already say, or corrects it where line numbers or behaviour differ. All
findings are from code; nothing is web-sourced except the one Django reference in section 8.

## 1. What changes the spec (summary)

1. **The record must be honoured by `current_path`, not only `sitting_path`.** Every in-flight
   reader of the learner runner calls `current_path` directly (section 3). `sitting_path` for an
   incomplete attempt also bypasses `current_path` and calls `compute_path` itself
   (`form_engine/conditions.py:264-266`). Both routes must reach the record.
2. **`compute_path(form, answers)` cannot see the record**: it takes a `Form`, not a
   `FormProgress` (`conditions.py:187`). The signature or its two wrappers have to change.
3. **Seven authored-number comparisons**, not the three the seams note lists, break under a
   non-authored order (section 4).
4. **No code path deletes a served page, question or option today.** Admin forbids every delete
   and `content_save` never deletes form rows (section 6). The realistic hazard is a served
   question **moved** to another page or form (admin `form_page` is editable), plus deletion by
   shell or site cascade. "Skip on read" (answers.md) must also cover "no longer on this form".
5. **The lazy write has many readers that should not write.** Admin `answer_groups`, the export
   and the file-upload guard all reach `sitting_path` for in-flight attempts (section 3). The spec
   must say whether a read there writes the record or reads an authored-order fallback.
6. **Scoring fallbacks change one existing behaviour.** A completed attempt that already has
   `asked` would, if scored over `frozen_path(asked)`, stop flagging "a question was added since"
   on the results page (section 5).
7. **The `asked` field overlaps the record.** `asked` is written at completion with the same
   uuid lists, in path order (`conditions.py:133-144`, `models.py:464`). The spec must say whether
   the record replaces `asked` for quizzes, sits beside it, or extends it.

## 2. `FormProgress` today

- Fields (`form_engine/models.py:281-318`): `form` FK PROTECT (290-292), `user` nullable CASCADE
  (293-298), `start_time` auto_now_add (299), `last_updated_time` auto_now (300),
  `completed_time` (301), `scores` JSON (302-304), `furthest_page_reached`
  PositiveSmallIntegerField default 0, help text "The highest-numbered page this sitting has been
  shown" (308-310), `asked` JSON nullable (311-318, help text says "recorded when it completed").
- `record_page_reached(page_number)` (356-365) is forward-only on the authored number
  (`if page_number <= self.furthest_page_reached: return`). Called from
  `learner_interface/views.py:1973` on every render of a runner page.
- `get_current_page_number(path, answered_ids)` (367-375) iterates `path.numbered_pages()`, so it
  follows whatever order the path yields. It returns an authored number.
- `complete()` (446-473) calls `current_path(self)` (455), deletes this form's off-path answers
  (461-463), writes `self.asked = path.as_asked()` (464) and scores (466). It is the single
  completion point for the runner, submit-and-exit, `finalise_stale_incomplete` and the
  application check-your-answers page.
- Admin shows `asked` and `furthest_page_reached` read-only (`form_engine/admin.py:353-360`,
  fieldset 366-380). A new field needs adding there to be visible.
- Latest migration is `form_engine/migrations/0009_formcontent_condition_option_and_more.py`
  (adds `asked`). The new field is 0010; renumber on rebase if `form-engine-branch-logic-2` or
  `learner-interface-features-1-question-sections` (in progress) lands a form_engine migration
  first.

## 3. Where a `FormProgress` is created, and who reads its path

Created in exactly two production places (grep of `FormProgress.objects.create`):

- `learner_progress/attempts.py:94` in `get_or_create_incomplete` (79-105), inside
  `transaction.atomic()` with its `CourseFormAttempt`. Reached from `form_start`
  (`learner_interface/views.py:1912`) and from `ensure_attempt` (64-76), which only QA seeding
  commands use (`qa_helpers/management/commands/qa_create_*`).
- `course_applications/views.py:119` in `_start_application` (86-125), under
  `select_for_update` on the application.
- Plus `FormProgressFactory` (`form_engine/factories.py:86-93`), used by tests and by several
  `qa_helpers` commands that build sittings by hand (e.g.
  `qa_create_phone_question_scenario.py:183`, `qa_create_bulk_applications.py:95`,
  `qa_create_second_application_form_course.py:142`, which set `furthest_page_reached=1`
  directly).

So an eager write at creation would need two call sites plus the factory, and still miss rows
built by hand. The lazy write chosen in answers.md fits the code better, but the readers are
spread out:

| Reader | Path function | Line |
|---|---|---|
| Course start screen (GET, read-only by design: "the start screen reads, form_start writes") | `current_path` | `learner_interface/views.py:1812-1829` |
| `form_start` resume | `current_path` | `learner_interface/views.py:1915` |
| `form_fill_page` GET and POST | `current_path` | `learner_interface/views.py:2048`, `2059` |
| `form_submit_and_exit` | `current_path` | `learner_interface/views.py:2414`, `2427` |
| `complete()` | `current_path` | `form_engine/models.py:455` |
| Application resume URL | `current_path` | `course_applications/views.py:725` |
| Application page GET / POST | `sitting_path` / `current_path` | `course_applications/views.py:750`, `770` |
| Application check-your-answers | `sitting_path` | `course_applications/views.py:836` |
| File-upload guard | `sitting_path` | `form_engine/views.py:57` |
| Admin answer groups | `sitting_path` | `form_engine/queries.py:137` |
| Export "not asked" cells | `sitting_path` | `form_engine/exports.py:135` |
| Educator preview | `full_path` | `educator_interface/views.py:2262` |

Points for the spec:

- `view_form` is a GET that deliberately creates nothing (comment at
  `learner_interface/views.py:1811-1812`). If the lazy write lives inside `current_path`, this
  GET starts writing. If the write lives only in `form_start` and the fill page, `view_form` reads
  a record-less in-flight attempt in authored order, which is the same paper.
- `finalise_stale_incomplete` (`learner_progress/attempts.py:108-132`) can complete an attempt
  from the start screen without any fill-page request in between, so `complete()` must cope with
  (or write) a missing record.
- Admin and export reads of an in-flight attempt would write as a side effect if the write is in
  `sitting_path`. A pure fallback reader (record if present, else authored) for those callers
  avoids that.
- Two tabs hitting the lazy write together need a write-once guard, for example an update
  filtered on the field being null, then re-read. `get_or_create_incomplete` already relies on
  `transaction.atomic` but not a row lock.
- Application forms are not barred from the QUIZ strategy: no validation ties
  `Course.application_form` to a strategy (`content_save.py:1144-1160` binds it by path only).
  "Quizzes only" therefore still reaches `course_applications` when an application form is a
  quiz, and `Form.strategy` can change after attempts exist (`models.py:331-335` comment).
  The spec should say whether the record is gated on strategy at write time or written for every
  form.

## 4. Navigation: every authored-order assumption

`SittingPath` (`conditions.py:38-144`) keeps `all_pages` in authored order and builds
`_page_positions` as `{authored number: position}` from `numbered_pages()` (55-61), which
enumerates `all_pages` (71-77). `children_by_page` is a dict, so its insertion order is the only
child order (`_path`, 212-223). Option order is not in the path at all.

Comparisons that assume served order equals authored order:

1. `next_page_number`: `n > after` (`conditions.py:115-116`).
2. `previous_page_number`: `n < before` (118-119).
3. `first_page_number_at_or_after`: `n >= number` (121-122), used by resume (`paging.py:59`).
4. `last_page_number`: last key of `_page_positions` (124-126); used by `landing_page_number`
   (128-131), `get_current_page_number` (`models.py:375`) and the application resume
   (`course_applications/views.py:726`).
5. `_furthest_answered_page`: `max(number ...)` (`paging.py:32-41`) and `_resume_page_number`
   `max(...)` of three authored numbers, clamped to `len(path.all_pages)` (44-60).
6. `build_page_links`: `"is_accessible": number <= limit` (`paging.py:97-105`).
7. `first_page_number_with_unanswered_required(after=)`: `number > after` (`paging.py:149-162`).
   Used with `after=page_number` by the application edit-from-check flow
   (`course_applications/views.py:775-779`) and without `after` by the runner
   (`learner_interface/views.py:2066`).
8. `record_page_reached`: `page_number <= self.furthest_page_reached` (`models.py:362`).

Already position-safe: `page_position` (107-109), `page_count` (84-85), `question_positions`
(111-113, follows `questions()`), `_question_numbers` (`paging.py:165-167`), `answered_counts`
(190-209), `page_at`/`resolve_page`/`off_path_landing` (`page_flow.py:65-96`, index into
`all_pages`, so authored numbers keep resolving), and `page_context` (`page_flow.py:157-201`),
which only calls the path's next/previous and passes `page_position`/`total_pages`.

The fix is local: build `_page_positions` (and `numbered_pages()`) in served order, and replace
the eight comparisons with position comparisons. `furthest_page_reached` is stored as an
authored number; a page deleted or inserted before it shifts every later authored number
(numbers are list indexes into `form.pages.all()`, not stable ids). Storing it as a served
position, or translating on read through the record, is the spec's choice; storing a position is
stable for the life of the attempt because the record is frozen.

Templates: question numbers on screen already come from `question_positions`
(`form_engine/templates/form_engine/question.html:11-13`). The `data-testid` uses
`question.question_number` (authored, `models.py:236-251`); tests key on it, so leave it.

Options: `multiple_choice.html:12`, `checkboxes.html:2`, `dropdown.html:11` and `:15` (answer
key) iterate `question.options.all`. Proving "a refresh shows the same paper" with an injected
option order requires these to read the served order (for example a per-question option list in
the page context). `FORM_TREE_LOOKUPS` (`conditions.py:31-35`) does not prefetch options, so a
record-backed path that orders options needs `pages__questions__options` added.

## 5. Scoring and results

Confirmed as the seams note says (`models.py:598-632`, `655-719`): `compute_quiz_scores` and
`get_incorrect_quiz_answers` walk `self.form.pages.all()` and `page.children()`, issue one
`self.answers.get(question=...)` per question, and ignore the path. `score(path)` (641-653)
passes `path` only to the category strategy. `quiz_percentage` (326-346) already raises
`ValueError` for `max_score == 0`, which every caller guards, so a served paper whose items were
all deleted degrades safely.

New points:

- **Fallback for completed attempts.** Today `sitting_path` returns `frozen_path(asked)` when
  `asked` is set and `full_path` for older completed attempts (`conditions.py:254-263`). If
  scoring reads `sitting_path`, a completed attempt with `asked` stops counting questions added
  after it was sat. The results "outdated" check (`learner_interface/views.py:2150-2164`) then no
  longer flags "the quiz gained a question". The existing test
  `test_a_changed_question_count_is_explained`
  (`learner_interface/tests/views/test_form_runner.py:2066-2088`) uses an attempt with no
  `asked`, so it still passes via `full_path`; no current test pins the "gained" case. The spec
  should state the intended outcome. Deleting a served question still shrinks `max_score`, which
  the check reports as outdated.
- **Results page labels.** `course_form_complete.html:105` labels each incorrect answer
  "Question {{ item.question.question_number }}", the authored number from a full form walk
  (`models.py:236-251`). It equals the served position only while served equals authored. Out of
  scope here if the spec keeps served = authored, but it is a read-through surface for spec 2.
- **Report recompute.** `reports/indexes.py:523-545` loads every quiz question of the form
  ordered `form_page__order, order` and numbers them per form (548-578). `build_sat_questions`
  (601-638) pairs every completed attempt with **every** question of its form. To "count only the
  served questions" the report needs each attempt's served (or `asked`) question set; today
  `FormProgressIndex` (`reports/indexes.py:98`, built at 365-441) carries ids only, not `asked`.
  This is a query change in `load_form_progress_rows`, not just in `models.py`.
- `is_quiz_answer_correct` (`form_engine/scoring.py:11-25`) is order-independent; option order
  does not affect any score.
- QA seeding comments state "score_quiz() counts every question toward max_score"
  (`qa_helpers/management/commands/qa_create_report_course.py:13`,
  `qa_create_checkbox_scoring_quiz.py:4`, `qa_create_report_cohort.py:403`). Still true for an
  authored paper; worth a glance when scoring changes.

## 6. Identity and deletion: what protects served items

All ids are UUID primary keys from `SiteAwareModel`/`BaseContent`
(`site_aware_models/models.py:167`; `FormPage`, `FormContent`, `FormQuestion` via
`content_base/models.py:11`; `QuestionOption` is `SiteAwareModel` directly, `models.py:260`).
`content_save` keeps them stable by writing uuids back into the YAML, including option uuids
(`content_save.py:126-216`, `759-781`) and upserting by id (`save_with_uuid`, 333-340). So
"reference by uuid" is the existing convention, and `asked` already stores string uuids.

`on_delete` that guards a served item:

| Relation | on_delete | Line | Effect on a served item |
|---|---|---|---|
| `FormProgress.form` | PROTECT | `models.py:290-292` | Form with attempts cannot be deleted |
| `FormPage.form` | CASCADE | 98 | Deleting a form would cascade, but PROTECT above blocks it |
| `FormContent.form_page` | CASCADE | 138-140 | Content goes with its page; nothing protects content |
| `FormQuestion.form_page` | CASCADE | 165-167 | Question goes with its page unless answered |
| `QuestionAnswer.question` | PROTECT | 728 | An answered question blocks its own and its page's deletion |
| `QuestionOption.question` | CASCADE | 263-265 | Options go with their question |
| `QuestionAnswer.selected_options` | M2M | 729-731 | Deleting a selected option silently drops the through row, so a recompute changes |
| `*.condition_option` | RESTRICT | 104-108, 145-149, 181-185 | Irrelevant to quizzes (no `when`) |

Deletion is not reachable from the product today:

- Admin forbids delete on every form model: `QuestionOptionAdmin` (`admin.py:74-77`),
  `FormContentAdmin` (127-130), `FormQuestionAdmin` (183-186), `FormPageAdmin` (234-237),
  `FormAdmin` (265-268); all inlines set `can_delete = False` (64, 89, 99, 196).
- `content_save` never deletes form rows. Its only `.delete()` is for due dates
  (`content_save.py:1252-1258`). A question dropped from the YAML, or an option re-created without
  its uuid, stays as a stale row on the page (`content_save.py:672-674` says so). Such rows keep
  their old `order` and still appear in `page.children()` and `question.options.all()`.

What does happen:

- **Moves.** `FormQuestionAdmin` exposes `form_page` as an editable field (`admin.py:150-160`),
  so a served question can move to another page or another form. `save_with_uuid` also rewrites
  `form`/`form_page` on re-import, so reusing a uuid in another form file moves the row.
  `answer_groups` already handles "answered question no longer on any page"
  (`queries.py:150-158`). The record's read must decide: render a moved question under its served
  page, or treat "not on this form any more" like deleted. `_owned_file_question` already scopes
  a question to `form_page__form=form_progress.form` (`form_engine/views.py:51-56`), the
  precedent for the latter.
- **Order edits.** Admin inlines and list views expose `order` on pages, content, questions and
  options (`admin.py:61`, 86, 97, 205). Today such an edit reorders every in-flight attempt; the
  record freezes it, which is the point.
- **Stale rows.** Because removed items are not deleted, the live form can grow stale questions
  that today count toward `max_score`. A record written from the authored order at first request
  still includes them; this is existing behaviour, not new.

## 7. Spec-scope boundaries the code makes concrete

- `answer_groups` (`queries.py:118-158`) and the export (`exports.py:120-140`) walk the live form
  for **layout** and use `sitting_path` only for **membership** (`is_asked`, `off_path_question_ids`).
  If `sitting_path` follows the record, their "not asked" marks follow it with no edit, while row
  order stays authored. That is consistent with answers.md (layout left to
  `sacaa-compliance-4-attempt-review`) and needs no change in this spec.
- `full_path` is used only by the educator preview (`educator_interface/views.py:2262`) and as
  the old-completed fallback inside `sitting_path` (`conditions.py:262-263`). Leaving the preview
  alone does not block the fallback.
- The course start screen shows `count_form_questions(form)` and `form.pages.count()`
  (`learner_interface/views.py:1855-1856`, `form_engine/queries.py:62`). Correct while served
  equals authored; spec 3 (draw) will need them from the record.
- `frozen_path` (`conditions.py:231-244`) turns `asked` lists into sets and rebuilds in authored
  order, so it discards the order `asked` already records. A record-backed builder replaces the
  set filter with an ordered walk of the record, looking items up by id in the prefetched tree.

## 8. Collisions and gotchas

- `form-engine-branch-logic-2-and-conditions` (still in `spec_dd/1. next/`) changes
  `_condition_holds` and `condition_option` in the same module as `compute_path`
  (`conditions.py:169-209`). Last commit to `conditions.py` on main is 1eca4518e. Whichever lands
  second rebases, as the seams note says; keep the record work out of `_condition_holds`.
- `learner-interface-features-1-question-sections` is in progress and may add a `FormQuestion`
  migration in form_engine; renumber 0010 if it lands first.
- A seed field declared as `UUIDField(default=uuid.uuid4)` and added by `AddField` gives every
  existing row the **same** value, because the callable default is evaluated once for the
  migration. Use a nullable field (record-less rows fall back anyway) or a RunPython backfill.
  Reference: https://docs.djangoproject.com/en/5.2/howto/writing-migrations/#migrations-that-add-unique-fields
- Tests that will move with this work: `form_engine/tests/test_conditions.py`, `test_paging.py`,
  `test_page_flow.py`, `test_models.py` (scoring), `test_queries.py`, `test_exports.py`, and
  `learner_interface/tests/views/test_form_runner.py` (outdated-score tests at 2021-2088).

status: ok
