# Research: codebase (sacaa-compliance-4-attempt-review)

What the attempt review and the export touch, reuse or conflict with. Paths are from the repo root.
Status of the siblings: `sacaa-compliance-1-served-paper-record` and `sacaa-compliance-2-shuffle`
are done (on main). `sacaa-compliance-3-question-pools` is implemented and in QA on its branch, not
on main. `educator-interface-refactor-5-learner` is done, so `panels/learner/` exists.

## 1. The one reader: `sitting_path()` and the served paper

- `freedom_ls/form_engine/conditions.py` `sitting_path(form_progress, answers=None)` is the single
  reader. Precedence: `served_paper` (via `served_path`) > `asked` (via `frozen_path`) > completed
  with neither (`full_path`, every page and child) > in flight (`compute_path`).
- It returns a `SittingPath`. What the review needs is all there:
  `numbered_pages()` / `pages` (served page order), `children_of(page)` (questions and content
  blocks in served order), `options_of(question)` (served option order; authored order when there
  is no served paper), `question_positions()` (the number the learner was shown),
  `has_missing_served_items` (the paper names a page, child or option the form has since lost).
- `served_path` rebuilds over the current tree: a deleted item is skipped, a question moved to
  another page still shows under the page it was served on, a question whose served options all
  vanished falls back to its live options. So "question wording is current" is exactly what the
  reader gives today.
- `ServedPaper` (TypedDict, same module) is the stored shape of `FormProgress.served_paper`:
  `{"seed": int, "pages": [{"id", "children": [ids]}], "options": {question_id: [option_ids]}}`.
  Every id is a string uuid. Pools (spec 3, branch) do not change this shape: a draw only shortens
  a page's `children` (`_drawn_units` in `served_paper.py` on the branch) and adds `FormPage.draw`.
- `freedom_ls/form_engine/served_paper.py`: `build_served_paper` writes the paper;
  `ensure_served_paper` writes it for every open QUIZ sitting, randomised or not. So a quiz
  sitting started after spec 1 shipped always has a paper (authored order when no shuffle/draw),
  and its seed exists even when nothing was shuffled.
- **Seed is provenance, not a reproduction key.** The comment in `build_served_paper` says
  `random.shuffle`/`random.sample` output is not stable across Python versions, "so nothing
  rebuilds a paper from it; the stored lists are the record." The idea's "an inspector can
  reproduce the paper from the file" must rest on the served-order cell, not the seed.
- Legacy sittings: a quiz completed before spec 1 has no `served_paper` (no seed); before
  `asked` existed it has neither, and `full_path` shows every question. The review and export must
  handle "no seed".

## 2. `FormProgress` and its stored result

`freedom_ls/form_engine/models.py` `FormProgress`:

- Fields: `form` (PROTECT), `user` (nullable: anonymous application sitting), `start_time`,
  `last_updated_time`, `completed_time`, `scores` (JSON; for QUIZ `{"score", "max_score"}`),
  `furthest_page`, `asked`, `served_paper`. No stored attempt number, no stored pass mark, no
  stored percentage.
- `quiz_percentage()` derives from `scores`; raises `ValueError` for non-quiz, unscored,
  non-quiz-shaped scores or `max_score == 0`. `passed()` compares to the form's **current**
  `quiz_pass_percentage` (raises when it is None).
- `freedom_ls/form_engine/queries.py` `quiz_verdict(form, form_progress) -> bool | None` is the
  guarded verdict every caller should use (None for no pass mark / no percentage). The Courses tab
  goes through `reports/gather.py` `_score_attempt`, which has the same guard.
- "Pass mark applied" is therefore the form's current `quiz_pass_percentage`, not the value at
  sitting time. Worth one line in the spec as a known limit (out of scope to freeze it).
- Correctness per question is computed live, not stored: `freedom_ls/form_engine/scoring.py`
  `is_quiz_answer_correct(selected_ids, options)` (exact match; `correct=None` options are
  neutral; a question with no correct option is never correct, so free text scores 0) and the
  batch `evaluate_quiz_answers`. Scores are frozen at submission; the learner results view
  (`learner_interface/views.py` ~2160-2215) recomputes with `compute_quiz_scores(path)` and shows
  a `stored_score_outdated` notice when they disagree, skipping it when
  `path.has_missing_served_items`. The review will show live per-question marks beside a stored
  score, so it meets the same disagreement and should reuse that rule.
- `get_incorrect_quiz_answers(path)` already orders options by the served paper and numbers by
  served position, but only lists wrong answers and skips free-text questions; the review needs
  every served question, so it builds its own rows from `SittingPath` rather than reusing this.
- Attempt number is computed, not stored: `reports/gather.py` `_quiz_result_for` numbers the
  completed sittings chronologically per (course progress record, form) from
  `FormProgressIndex.completed_attempts_by_learner_form` (`reports/indexes.py`, keyed by course
  progress record when `keyed_by="course_progress"`). Two placements of one form in one course
  share one numbering. The instance page must compute the number the same way, or the table and
  the page can disagree.
- Course linkage: `learner_progress/models.py` `CourseFormAttempt` (`form_progress` one-to-one,
  `related_name="course_attempt"`; `course_progress`; nullable `collection_item`). A sitting
  outside any course has no `course_attempt` and cannot be reached from the learner page. Per the
  glossary, course code resolves attempts through `learner_progress/attempts.py`
  (`completed_attempts(course_progress, collection_item)`), never `FormProgress`'s `(user, form)`
  helpers.

## 3. The learner Courses tab and its attempts table

- `freedom_ls/educator_interface/panels/learner/panels.py` `LearnerCoursesPanel` (title
  "Courses", template `educator_interface/panels/learner_courses.html`, refresh on
  `LEARNER_CHANGED`, `REGISTRATION_CHANGED`). It filters registrations through
  `quick_view.py` `visible_registrations_with_progress` (drops a registration made through a
  cohort the educator cannot see) and calls `reports/gather.py` `gather_learner_course_details`.
- The attempts table is a static `<c-panel-table caption="<quiz> attempts">` per quiz, columns
  Attempt, Completed, Score, Percentage, Pass mark, Result (`{% passed_badge %}` from
  `educator_interface/templatetags/educator_tags.py`, plus a muted "Latest" on the last row). Only
  completed attempts are listed (matches the "completed only" answer). Rows carry no link and no
  actions today.
- Rows are `reports/report_data.py` `QuizAttempt(attempt_number, completed_at, score, max_score,
  percentage, passed)`: **no `FormProgress` id**, so nothing can link a row. The spec has to add
  one (for example `form_progress_id: UUID`) in `_quiz_result_for`.
- `QuizAttempt` sits inside `QuizResult`, which sits in `LearnerDetail` inside the cached
  `CohortReportData`. `reports/screen_cache.py` says "Bump whenever a cached dataclass changes
  shape": adding a field means bumping `SCHEMA_VERSION` (now 2).
- The table holds no start time. The quick view summary (score, pass/fail, times) needs
  `start_time` from the row itself, which the quick view loads anyway.
- Per the panel-framework skill a row's own record opens in the quick view, a row's buttons go in
  its last column (small, secondary), a table with action columns declares `cards_when_narrow`
  (`<c-panel-table cards="true" cards_when_narrow="true">`), and a row the viewer cannot act on
  leaves the buttons column empty. The quick-view trigger is
  `panel_framework/partials/quick_view_button.html` (`href` = full page, `url` = drawer URL,
  `label`), or `<c-quick-view-trigger>`; `data-table-cells/learner.html` is the worked example of
  `href=".../learners/<pk>"`, `quick_view_url=".../__quick-view"`.
- `freedom_ls/educator_interface/tests/test_reporting.py` (~line 1310) asserts on the
  `learner_courses.html` template; changes to the table land there too.

## 4. A new instance page and quick view: what the framework allows today

This is the biggest finding. **The panel framework has no route for a record that is not a
sidebar section's row.**

- `freedom_ls/panel_framework/views.py`: an instance page is `<section url_name>/<pk>` on a
  `ListViewConfig` with `instance_view`; the drawer is `<section>/<pk>/__quick-view` on the same
  config's `quick_view` (`_resolve_path`, `_bind_root`, `_handle_quick_view`). Below the instance
  only `__tabs/<name>`, `__panels/<name>`, `__actions/<name>` and `__runs/<id>` resolve; there is
  no nested instance (`learners/<pk>/attempts/<id>`).
- Every section comes from `educator_interface/views.py` `interface_config` (NavGroups) and
  `build_menu_items` lists every visible, available section in the sidebar. `is_available()`
  False hides it **and** 404s its paths. There is no "routable but not in the menu" flag.
- `build_breadcrumbs` gives an instance page one back link, to its section's list
  (`section.menu_label`). An attempt page wants a back link to the learner's Courses tab
  (`learners/<learner_pk>/__tabs/courses`), which the framework cannot express.
- So "its own instance page plus a quick view, from the panel framework" needs one of:
  1. A small, generic framework addition: a `ListViewConfig` that is routable but left out of the
     menu (for example a class flag read by `build_menu_items`), with an overridable back link
     (for example a classmethod returning the label and URL for the instance's back link). Then an
     `AttemptConfig(OrganisationSectionConfig, ListViewConfig)` with `model = FormProgress`, no
     `list_view`, an `instance_view` and a `quick_view`, added to a NavGroup.
     `ListViewConfig.list_view` may be None (`_bind_root` raises only on the list path;
     `checks.table_key_errors` needs a `table_key` only when `list_view` is set). It must stay
     generic (the framework imports nothing from `freedom_ls`; `test_import_guard.py`), and it
     collides with `extract_panels_framework-5-package-and-install` (ready to start), which moves
     the framework to its own repo: whichever lands second carries the change.
  2. The existing precedent for "open one learner-owned record from the learner page":
     `panels/learner/messages.py` `ViewConversationAction`, a `PanelAction` with a
     `template_name`, reached at `learners/<pk>/__actions/view_conversation?conversation=<id>` and
     rendered in `#app-modal`. That is a dialog, not the instance page the user chose, so it only
     fits if the spec revisits the answer.
- `InstanceView` (`panel_framework/views.py`) fits the page well: `get_subtitle`,
  `get_status_badge` (a Passed/Failed `StatusBadge`), `get_stats` (`HeaderStat`, for score and
  percentage), `get_header_actions` (return `[]`). `panel` would be a `PanelStack`: an
  `InstanceDetailsPanel` (`detail_row(label, value, kind)`) for the result and times, and a panel
  for the paper. Per the skill a page header shows a state badge only when it differs from the
  default; Passed/Failed are both outcomes, so the spec should say whether the header badge shows
  both.
- `QuickView` (`panel_framework/quick_view.py`): `template_name`, `refresh_events`, `get_title`,
  `get_subtitle`, `get_context_data`. Worked example: `panels/learner/quick_view.py`
  `LearnerQuickView`, template `educator_interface/quick_views/learner.html`.
- Section configs authorise through `authorise_instance`, called by `check_access` for the page,
  the drawer and every action (`test_config_authorisation.py` and `tests/interface_walk.py` will
  pick up a new config). `LearnerConfig.authorise_instance` is the model:
  `learners_visible_to(request.user, organisation, include_inactive=True).filter(pk=...)`, raising
  `OrganisationScopeDenied`.

## 5. Rendering the paper: reuse the content preview

- `educator_interface/panels/course/content_preview.py` `_form_preview_context` and
  `educator_interface/templates/educator_interface/modal/content_preview.html` already draw form
  pages read-only for educators through `form_engine/partials/page_children.html` with
  `read_only=True`, `show_answer_key=True` (the `<c-correct-answer-mark>` on correct options),
  `existing_answers`, `question_positions`. The question inputs (`form_engine/inputs/
  multiple_choice.html`, `checkboxes.html`, `dropdown.html`) mark the learner's selection from
  `existing_answers` and take option order from `{% question_options %}`
  (`form_engine/templatetags/form_engine_tags.py`), which reads `sitting_path` from the context.
- So passing `sitting_path=sitting_path(form_progress)`, `existing_answers=answers_by_question(...)`
  (`conditions.py`), `question_positions=path.question_positions()` and the path's
  `children_of(page)` per served page draws the served paper with the learner's choices, the
  answer key and served option order, with no new question templates. Missing: a per-question
  correct/incorrect mark (nothing in those templates shows it) and the page position/title
  heading (the preview's `form_page` partial is close).
- Content blocks render via `rendered_content` (`fls-dev:markdown-content`).

## 6. The export (`freedom_ls/form_engine/exports.py`)

- **There is no quiz-attempt export today.** `form_engine/exports.py` (`answer_columns`,
  `off_path_question_ids`, `answer_cell`, `answer_value`) has one consumer:
  `course_applications/resources.py` `CourseApplicationResource`, the Django admin's application
  export (also `course_applications/api.py` reads `answer_value`/`off_path_question_ids`). It is
  one row per `CourseApplication`, not per quiz sitting. Application forms are in practice not
  QUIZ, so a served paper (and a seed) is never written for them (`ensure_served_paper` gates on
  QUIZ). Adding served order and seed to this export would add columns that are always empty.
  The spec has to settle what "the existing form export" means: these shared helpers plus a new
  quiz export somewhere (admin `FormProgressAdmin` export, or an educator-interface export), or
  the application export only. This is a decision the user may need to make.
- Present shape: one CSV, no sheets. `site_aware_models/admin.py` `SiteAwareExportModelAdmin`
  fixes the format to `FormulaSafeCSV` (`site_aware_models/admin_exports.py`, formula-escaped).
  A "second sheet" is not possible in CSV, so served order is one cell per row (or a separate
  file).
- Columns: the fixed `APPLICATION_EXPORT_FIELDS`, then one column per question (`answer_columns`):
  forms by title then id, each form's current on-page questions in authored order, then answered
  off-page questions; headers deduplicated by `_qualified`. Cells: `answer_cell(answer,
  is_asked=...)` gives "Not asked" when the question is in `off_path_question_ids`, which already
  reads `sitting_path`, so an undrawn or unserved question is "Not asked" today with no change.
  Authored column order stays as the idea requires.
- `answer_value` sorts selected option text by authored `order`, not served order. Fine for the
  per-question columns; the served-order cell is where served option order goes.
- Seed in CSV: a 63-bit int (`secrets.randbits(63)`) is 19 digits; spreadsheets keep about 15
  significant digits and show it as `9.22E+18`, losing the value. The spec should say how it is
  written so it survives opening in a spreadsheet, and that legacy sittings have no seed.
- `FormulaSafeCSV` escapes formula triggers (`=`, `+`, `-`, `@`...); a served-order cell built of
  uuids or numbers is safe, but one starting with `-` would be escaped.

## 7. Django admin `answer_groups`

- Not moved onto the served order. `form_engine/queries.py` `answer_groups` walks
  `form_progress.form.pages.all()` in authored order and uses `sitting_path` only for `is_asked`,
  so unserved/undrawn questions show as "not asked" rows, and served page/question order is
  ignored. Used by `form_engine/admin.py` `answers_context` (`FormProgressAdmin` change page,
  template `admin/form_engine/answers_change_form.html` / `_answers.html`) and
  `course_applications/admin.py`. Spec 1 listed it as out of scope and deferred it to this spec.
- `sacaa-compliance-content-versions-and-access-4-question-access` (ready) removes "the answers
  document on `FormProgressAdmin` for forms scored as quizzes" and `QuestionAnswerAdmin` for QUIZ.
  Moving quiz `answer_groups` onto served order here would be removed by that spec; survey and
  application answers (the ones that stay) have no served paper. Leaving `answer_groups` as is
  costs nothing.

## 8. Permissions

- `learner_management/queries.py`: `VIEW_LEARNER = "freedom_ls_learner_management.view_learner"`;
  `learners_visible_to(user, organisation, include_inactive=False)` (site/organisation grant sees
  every learner in the organisation; a cohort grant sees that cohort's members).
- Reaching an attempt: `FormProgress` -> `course_attempt.course_progress` -> `learner` (a
  per-organisation `Learner`). Authorisation should require: the learner is in
  `learners_visible_to(..., include_inactive=True)` for the URL's organisation (as
  `LearnerConfig` does); the sitting is QUIZ and completed (else 404, per the answers); and the
  registration is visible the way the Courses tab filters it (a `CourseProgress.cohort_registration`
  whose cohort is not in `cohorts_visible_to` is hidden on the tab, so its attempts should not
  open either, or a guessed URL reveals what the tab hides).
- `FormProgress` is a `SiteAwareModel`; its default manager filters to the current site.

## 9. Audit log

- `freedom_ls/audit_log/README.md`: the log is "one append-only record of administrative
  changes"; write "only when state changed". The glossary's `viewed` verb is the exception, "only
  for a read worth auditing" (`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`).
- Precedent: `panels/learner/messages.py` `ViewConversationAction` writes `conversation.viewed`
  (actor viewer, target conversation, `subjects=[learner]`, `organisation=learner.organisation`)
  only on the HTMX request that renders the content (plain GET is a 404), because the read is of
  a private conversation under oversight. Ordinary learner reads (Courses tab scores, the
  learner quick view) write nothing.
- The siblings settle it for this spec:
  `sacaa-compliance-content-versions-and-access-4-question-access` puts "gating the attempt review
  ... out of scope" there and hands it to
  `sacaa-compliance-content-versions-and-access-5-answered-version-review`, which adds the
  question-viewing permission to the review and "each open of the full review writes" an entry
  (target the attempt, learner a subject, learner's organisation), with no entry for the reduced
  view or a detail-free quick view. That spec needs a new audit noun for the attempt (none in the
  glossary's noun list today).
- So under today's rules this spec writes no audit entry; spec 5 adds it. Consequence to state:
  until spec 5 ships, any `VIEW_LEARNER` holder sees question text and correct answers in the
  review unlogged, the same exposure as today's ungated `PreviewContentAction`.

## 10. Other touch points and collisions

- `sacaa-compliance-content-versions-and-access-5-answered-version-review` builds on this page
  (adds version facts per question, a reduced view, audit) and on the quick view if one exists.
  Keeping the per-question rendering in one place (one partial, rows built from `SittingPath`)
  makes that easy.
- `sacaa-compliance-content-versions-and-access-3-question-versions` will make `sitting_path`
  version-backed; reading only through it keeps this spec compatible.
- `extract_panels_framework-5-package-and-install` (any framework change, section 4).
- `fls-dev:educator-interface` Placement table lists only actions; a row "A learner's Courses tab
  attempts table: open the attempt (page and quick view)" would record the new link. The
  "Visual checklist" there and in `fls-dev:panel-framework` is what QA checks.
- `docs/product/educator-interface.md` line 44 describes the Courses tab ("every quiz attempt with
  its score and the quiz's pass mark"); it needs the review added.
- Free-text questions in a quiz render their answer text through the same templates; they score
  0 and are skipped by `get_incorrect_quiz_answers`, so the review must not mark them wrong
  without a word.

status: ok
