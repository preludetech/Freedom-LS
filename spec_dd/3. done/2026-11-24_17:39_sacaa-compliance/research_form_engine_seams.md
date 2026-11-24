# Form-engine seams for randomisation (SACAA compliance)

Paths are under `freedom_ls/` unless noted. Read at HEAD 0d55135e9. Everything below is from code; nothing web-sourced.

## 1. Current model shape

- `Form` (form_engine/models.py:54): `strategy` (QUIZ / CATEGORY_VALUE_SUM / UNSCORED), `quiz_show_incorrect`, `quiz_pass_percentage`, `submit_on_exit`. No randomisation fields.
- `FormPage` (models.py:93): `order` int (99), `category`, nullable `condition_option` FK to `QuestionOption` (104). `children()` (112-123) merges `text_items` and `questions` and sorts by `order`, so content blocks and questions share one order space per page.
- `FormContent` (132): `content`, `order` (141), `condition_option` (145).
- `FormQuestion` (160): `order` (168), `slug` (170, author reference used only by `when`), `condition_option` (181), `type`, `required`, `min`/`max`/`decimal_places`. `question_number()` (236-251) walks the authored order.
- `QuestionOption` (260): `order` (268), `correct` nullable bool (269), `value` (267).
- `FormProgress` (281): `furthest_page_reached` (308, an authored page number), `asked` JSON (311), recorded only at `complete()`. It holds string uuids of pages, questions and content (`SittingPath.as_asked`, conditions.py:133-144). `scores` JSON (303).
- `QuestionAnswer` (722): one row per (progress, question), unique (736); `selected_options` M2M; `question` is PROTECT (728).
- **Grouping of content with a question: none.** The only link is adjacency by shared `order` on a page. Authoring has no grouping key either. A stimulus block ("Considering blah blah, answer the following") is a loose `FormContent` before its questions (`demo_content/functionality_demo_end_with_quiz/3. quiz/1. page.yaml:24-28`).
- Order is stored only as authored: `content_save` sets page `order` from the sorted file paths (content_engine/management/commands/content_save.py:1080-1090). Child `order` is the index within the file (1107-1136). Option order comes from list index (line 772 area).
- No per-attempt order is stored anywhere.

## 2. Learner flow and where a per-attempt order must apply

- URL carries the **authored page number** (1-based index into `path.all_pages`). `page_at`/`resolve_page` (page_flow.py:65-83) and `off_path_landing` (86-96) index into `all_pages`.
- Authored order is hard-wired into `SittingPath`:
  - `numbered_pages()` enumerates `all_pages` (conditions.py:71-77).
  - `next_page_number` / `previous_page_number` / `first_page_number_at_or_after` compare authored numbers by `>` / `<` (115-126).
  - `questions()` and `question_positions()` follow page order then child order (103-113).
- `page_position` (107) is the learner-visible "page N of M". `total_pages` is `page_count` (84). Both come from the path, so they already tolerate skipped pages. The "authored index in the URL, position on screen" split is the existing hook for a shuffled order.
- Resume: `resume_page_number` (paging.py:63-76) takes the max of the first page with an unanswered question, the furthest answered page and `furthest_page_reached`. All three are numeric comparisons in authored space, so under a shuffle "furthest" must be reinterpreted as a position in the realised order, not an authored index. This is the main hazard.
- Page-jump nav: `build_page_links` (paging.py:86-107) uses `number <= limit` for `is_accessible`. It is authored-ordered, so a shuffle would make it wrong unless numbers are positions.
- Question numbers in messages: `_question_numbers` (paging.py:165-167) uses `path.question_positions()`, so it follows the path order automatically.
- Progress indicator: `answered_counts` (paging.py:190-209) uses `path.question_ids`, which is correct for a subset.
- Back navigation uses `previous_page_number`; the learner view resolves everything through `current_path(form_progress)` (learner_interface/views.py:2048, 2059) and completes via `form_progress.complete()` (2079). The same path is rebuilt on every request from the saved answers (`compute_path`, conditions.py:187-209). Nothing is stored between requests, so a stable shuffle needs a persisted seed or order at attempt start.
- Order of application: `compute_path` is the single choke point. Page and child order both come from `form.pages.all()` / `page.children()` (198, 182). `frozen_path` (231-244) and `full_path` (247-251) rebuild from the current tree, so they would have to read the realised order too.
- Other callers of the path: course_applications/views.py:725-840 (application shell, same `page_flow`), form_engine/views.py:57 (file upload guard), educator preview (`full_path`, educator_interface/views.py:2262).
- Option rendering: templates iterate `question.options.all` (form_engine/templates/form_engine/inputs/multiple_choice.html:12, checkboxes.html:2, dropdown.html:11). They read the authored `order` directly. The answer-key lists also iterate `.options.all` (dropdown.html:15).

## 3. Scoring with a subset

- `complete()` (models.py:446-473) builds the path, deletes the answers of off-path questions (461), stores `asked` (464), then `score(path)` (466).
- `score_category_value_sum` takes the path and counts only asked questions (490-491). It is already subset-safe.
- **`score_quiz()` / `compute_quiz_scores()` (598-639) ignore the path.** They loop over `self.form.pages.all()` and count every question in the form into `max_score` (608-617). `score()` passes `path` to the category strategy but not to quiz (645-646). A drawn subset of N out of M would therefore score against M, so a perfect score reads N/M.
- `get_incorrect_quiz_answers` (655-719) also walks all pages and so would list undrawn questions as "incorrect (blank)".
- `quiz_percentage()` (326-346) = score/max_score from the stored `scores`; `passed()` (348) compares with `quiz_pass_percentage`. These need no change once `max_score` is right.
- The learner results page compares stored and recomputed scores (learner_interface/views.py:2153-2164) via `compute_quiz_scores()`. That "outdated" check would flag every drawn attempt unless it uses the realised set.
- reports/indexes.py:544, 627-643 recomputes correctness from option lists for the report.
- Today a conditional QUIZ form is barred, so a quiz is always the full path: `when` is not allowed in a QUIZ form (content_engine/validate.py:1042-1053). Only the draw feature breaks that invariant.
- Fix: score over the frozen path (`frozen_path(form, asked)`, conditions.py:231) rather than the whole form. This is a prerequisite for subset draws and is a small change in models.py:598-719.

## 4. Conditions vs shuffling

- A condition is `when: {question: <slug>, equals|includes: <value>}` (schema.py:93-136). It is resolved at `content_save` to a `condition_option` FK (content_save.py:667-678). Evaluation is `_condition_holds` against `selected`, which grows as questions prove on-path **in page iteration order** (conditions.py:169-209).
- The validator requires the source to be on a strictly earlier page (validate.py:982-987) and the form not to be QUIZ (1042-1053).
- Conflicts:
  - Page shuffle: the "earlier" invariant is authored. A shuffle can place the source after the gated page, so the gate reads no answer and is false (conditions.py:172-174), so the page silently drops.
  - Question shuffle within a page: a condition source is always on an earlier page, but `compute_path` iterates children in order (203-208). A question gated on another question can be moved above it only if sources could be on the same page, and the validator forbids that. Question shuffle is therefore safe for question-to-question conditions, but option shuffling is unaffected by conditions because they key on option rows and values.
  - Subset draw: a source question left undrawn gives an off-path source, so every condition on it is false and the gated item silently vanishes.
- **Recommended rule** (cheap and enforceable in `validate_form_conditions`):
  1. A form with any randomisation knob that moves or drops pages or questions (page shuffle, question shuffle, draw) may not contain `when` anywhere. This mirrors the existing QUIZ rule at validate.py:1042 and keeps the check in the same function.
  2. Option shuffle is the one knob that is allowed with `when`. Conditions reference option `value`, not position (validate.py:1004-1005).
  3. Where a form needs both, a later spec can relax it to "sources may not be inside a shuffled or drawn scope and must stay on a fixed earlier page". Do not ship that now.
- The paused idea's concern was true only for the old single-gate model. The relevant code is `compute_path`; "AND" conditions (`form-engine-branch-logic-2-and-conditions`) make a `condition_option` list but do not change the rule above. It would touch `schema.Condition`, `_condition_holds` and `condition_option` (idea.md line 5), so it collides with this work on conditions.py, schema.py, validate.py and models.py. Sequence it separately.

## 5. Authoring

- Form file: `form.md` with YAML front matter (demo_content/.../3. quiz/form.md:1-9) holding strategy and quiz fields. Pydantic `Form` is at schema.py:40-90, with `validate_quiz_fields` at 67-90. A new flag on `Form` is a pydantic field plus a model field plus a `content_save` mapping.
- Pages: `N. name.yaml`. The first YAML doc is the `FORM_PAGE` header (title and other fields); later docs are content blocks and questions in order, each with `uuid` (1. page.yaml:1-61). Schema models: `FormPage` (schema.py:145; the page schema has only `when`), `FormContent` (171), `FormQuestion` (176), `QuestionOption` (157, `extra="forbid"`, so any new key needs a schema change).
- Natural homes:
  - Shuffle flags: `Form` front matter (`shuffle_pages`, `shuffle_questions`, `shuffle_options`). Per-page override is possible on the page header (`FormPage` schema).
  - Option lock (`locked: true`) on `QuestionOption` (schema.py:157), next to `correct`.
  - Keep-together group: a `group:` string key on `FormContent` and `FormQuestion` (schema.py:171, 176). A group is a contiguous run on one page. Validate that the members are contiguous.
  - Draw: `draw: N` on the page header (a page is the pool) or on `Form`. Section-based draw is covered in 7.
- Validation: pydantic validators run per item (e.g. `validate_bounds`, schema.py:258-274). Cross-file rules live in `content_engine/validate.py` (`validate_form_conditions`, 1015). Group contiguity, draw <= pool size, the no-`when` rule and "lock only with shuffle_options" all belong in a new `validate_form_randomisation` beside it.
- Model-side changes: new fields on `Form`, `QuestionOption` and `FormContent`/`FormQuestion`, plus `content_save` mapping (save_form_* at content_save.py:700-780). A migration is needed. Existing rows keep opt-out defaults.

## 6. Educator, review and export surfaces that assume authored order

- Admin attempt answers: `answer_groups` (queries.py:118-158) walks `form.pages.all()` in authored order and shows undrawn or unasked questions as "not asked" rows (`is_asked`, 100, 114). Used by form_engine/admin.py:295.
- Export: `form_engine/exports.py:116-140` (`off_path_question_ids`) builds per-sitting "Not asked" cells over the form's question list (`form_questions`, queries.py:83-90); `answer_value` sorts option text by authored `order` (152). Headers and columns are per question, so a shuffled attempt would still export correctly in authored columns. Only the displayed order matters.
- Learner results: `get_incorrect_quiz_answers` (models.py:655), results view at learner_interface/views.py:2145.
- course_applications uses the same path (views.py:725-870; resources.py:92; api.py:89).
- Educator interface: only a content **preview** reads `full_path` (educator_interface/views.py:2262). There is no per-learner attempt viewer there today (the grep found none), so "educator review reads the realised order" in the paused idea has no existing surface to patch. The attempt view that exists is the Django admin (queries.py `answer_groups`). A **review** surface is new work, not a patch.
- The reports app recomputes correctness from option lists (reports/indexes.py:544, 627-643). It is order-independent but max/subset-sensitive (see 3).
- Everything that shows what the learner saw should read one function. `sitting_path()` (conditions.py:254-266) is that function today: it returns the frozen path for a completed sitting, else a computed one. Extending it to honour a realised order covers admin, export and results at once.

## 7. Question sections (`learner-interface-features-1-question-sections`)

- That spec is in progress; per its idea.md the unit of "section" is still **open**: a `CoursePart`, a run of placements, or an author-named group (idea.md:36-40). It links a question to a course section from the form file and adds nothing about drawing.
- `FormQuestion` has no link to course content today (idea.md:24). `tags` and `meta` are stored but unread (idea.md:26).
- Section-tagged questions would make a natural pool key ("draw N per section", the pretest/test-out case), but randomisation cannot depend on it because that spec's shape is undecided. Recommendation: the draw unit stays form-local, a **page** (or a named `pool:` string) on the form. A later spec may let `draw` key on the section tag once that spec has shipped. The two touch the same schema lines (`FormQuestion`, schema.py:176), so sequence them or expect a merge collision.

## 8. Proposed seams

Foundation: the per-attempt realised-order record and its single reader.

1. **realised-order foundation (no visible shuffle yet).** Add `FormProgress.realised_order` JSON plus a seed, written at attempt start, and make `compute_path`/`frozen_path`/`sitting_path` build from it. A page's `number` stays the authored index (so URLs keep working); add an explicit order-aware `next`/`previous`/resume (paging.py, conditions.py). Fix `score_quiz`, `compute_quiz_scores` and `get_incorrect_quiz_answers` to score the frozen path, and make `answer_groups` and the export read the realised order. Outcome: an attempt records exactly what was served; any form's results are identical for forms without randomisation (regression-safe). Touches models.py (+migration), conditions.py, paging.py, page_flow.py, queries.py, exports.py, learner_interface/views.py (2153-2164).
2. **shuffle pages / questions / options (opt-in per form).** Form flags, option `locked`, `group:` keep-together for a content block plus the questions that depend on it, schema plus validation (including the no-`when` rule, 4). Outcome: two learners see different orders; "all of the above" stays last; a stimulus stays with its questions. Depends on 1. Touches schema.py, models.py (+migration), content_save.py, validate.py, the option templates (the three `inputs/*.html`), and the order builder from 1.
3. **random draw from a pool.** `draw: N` on a page or pool. Outcome: each attempt gets N of M questions, scored out of N. Depends on 1 (scoring on the frozen path). Touches the same schema and validate files as 2, so ship after 2 or merge their schema work; collides with 2 on schema.py, validate.py and content_save.py.
4. **educator review of the realised order.** A per-attempt view and an export column for the served order and seed. Depends on 1. Touches queries.py and exports.py, plus a new educator_interface view and template. Independent of 2 and 3; it is useful even with only the foundation, since it can show the served order and draw.

Order: 1, then 2 and 3 in either order (one at a time because of the schema collision), 4 any time after 1. A split into 4 specs gives each one a PR with its own visible outcome; 1 is the only one with no learner-visible change by itself, so ship it with a test that a complete attempt round-trips.

Collisions with in-flight work:
- `form-engine-branch-logic-2-and-conditions`: conditions.py, models.py and schema.py (`Condition`, `condition_option`) and validate.py (`_condition_problem`). Seam 1 changes `compute_path`, so expect to rebase around it.
- `learner-interface-features-1-question-sections`: schema.py `FormQuestion` and content_save.py (`save_form_question`), possibly a migration on `FormQuestion`.

status: ok
