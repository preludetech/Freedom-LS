# Research: codebase (what revision questions touch, reuse, conflict with)

Verified against the current tree on this branch (shuffle + question-sections present). Paths are under `freedom_ls/`.

## 1. Form models and the question -> section link

- `form_engine/models.py`: `Form` (:54; `strategy`, `quiz_show_incorrect`, `quiz_pass_percentage`, `submit_on_exit`, `shuffle_pages/questions/options` :81-95), `FormPage` (:114, FK `form` related_name `pages`), `FormContent` (:153), `FormQuestion` (:190; FK `form_page`, `order`, `category`, `group`, `slug`, `condition_option`, `question`, `type`, `required`, `min/max/decimal_places`), `QuestionOption` (:299; `text`, `value`, `order`, `correct` nullable bool, `locked`). A question belongs to exactly one page, hence one form. No `explanation` field anywhere.
- Question -> section link lives in **content_engine**, not form_engine: `content_engine/models/question_sections.py` has `FormQuestionTopic(question FK CASCADE, topic FK PROTECT)` and `FormQuestionCoursePart(question FK CASCADE, course_part FK PROTECT)`, each unique on the pair, no `site` column. Exposed as `Topic.testing_questions` / `CoursePart.testing_questions` (M2M through) with reverse accessors `question.topics` and `question.course_parts`. A "section" = `CoursePart` or `Topic` (done spec `1. spec.md`, Terminology).
- Author key: `sections: list[Path] | None` on `Form` (default for its questions) and on `FormQuestion` (`form_engine/schema.py:100, 284`); absent inherits, `[]` means none. Allowed on every form strategy, so a bank form need not be QUIZ (decision 9). A form placed in no course needs no loader change (decision 10) but must sit in a sibling directory of the courses (a `_` prefix is not loaded; one inside a course dir without `children:` is auto-placed).
- Section targets must be inside the dir passed to `content_save`; every load rewrites the links (`replace_question_sections`, `content_save.py:806`).

## 2. Scoring and choice types

- `form_engine/scoring.py:11` `is_quiz_answer_correct(selected_option_ids: set[UUID], options) -> bool`: every `correct is True` selected and no `correct is False` selected; no required option => always False (so free text never scores). `evaluate_quiz_answers` (:28) is the batch form. Right/wrong is recomputed from current `correct` flags, never stored.
- Scorable types = `multiple_choice`, `checkboxes`, `dropdown` (the ones with options). Revision should reuse `is_quiz_answer_correct` directly; checkboxes are exact-match.
- Risk: a question whose options have all `correct=None` is unanswerable-correct; the bank query must require at least one `correct=True` option.

## 3. FormProgress / QuestionAnswer and who reads them

- `FormProgress` (:321; form, user, start/completed time, `scores`, `furthest_page_reached`, `asked`, `served_paper`); `QuestionAnswer` (:801; FK `form_progress`, FK `question` PROTECT, M2M `selected_options`, `text_answer`). Unique per sitting. 421 occurrences across 64 non-test files: admin, exports, reports (`reports/gather.py`, `indexes.py`), `learner_progress/attempts.py`, `queries.py`, `signals.py`, course_applications receivers, qa_helpers.
- Conclusion (matches the idea): revision answers must NOT go in these; they would appear in reports, exports, attempt history, completion receivers (`form_attempt_completed` -> `recalculate_course_progress_on_form_attempt`). New models needed (state per learner+question, review log).
- `QuestionAnswer.question` is PROTECT, so a question that has been answered in a real sitting cannot be deleted by anything (see conflict C1).

## 4. Loader and schema: explanation, bank-form flag, removal

- Schema: `form_engine/schema.py`. `QuestionOption` is `extra="forbid"` (:222) so an option-level key needs a schema field. `FormQuestion` (:247) extends `BaseBaseContentModel` from `content_base/schema.py`. An `explanation: str | None` on `FormQuestion` (per answers.md: per question) is a plain field; `save_with_uuid` (`content_save.py:263`) dumps the schema model into the model's fields, so adding `explanation = TextField(blank=True)` on `FormQuestion` + schema field is enough; null in the dump is dropped, so, like `slug`/`group` (`content_save.py:777-778`), pass `explanation=item.explanation or ""` explicitly or a removed explanation stays stored. Markdown rendering: `FormQuestion.rendered_question` exists as a precedent.
- Bank flag: no form "kind" exists. Options: a `Form` field (e.g. `bank: bool`, valid on any strategy) versus using strategy. Must also be added to the `QUIZ`-only validator in `Form.validate_quiz_fields` (:122) pattern if restricted. Sync copies: `claude_plugins/fls-content/validate/schema.py` and `validate.py` via `/fls-dev:update_claude_plugin_fls_content`, plus `skills/content-types/resources/form-files.md` (done spec requirement; same here). `content_validate` already checks cross-file rules (`content_engine/validate.py`).
- Removal (verified): `content_save` never deletes a `FormQuestion` (`content_save.py:689` docstring: "questions dropped from the YAML ... leave stale rows"; the only `.delete()` calls are section-through rows :866 and `CoursePartChildDueDate` :1362). Options are re-created and updated by uuid only. See conflict C1.
- Edits: question and option rows keep their uuid, so ids (and any revision rows keyed on question id) survive edits. Option without uuid is re-created on each load (new id) until the loader writes the uuid back into the file (`update_file_with_option_uuids` :178).

## 5. Section/topic completion hooks

- Topic completion: `TopicProgress.complete_time` set in `learner_interface/views.py:1781-1789` (POST `mark_complete`; first completion wins), via `learner_progress/models.py:60`. `post_save` receiver `recalculate_course_progress_on_save` (`learner_progress/signals.py:84`, sender=TopicProgress) detects the transition with `CourseItemProgress.newly_completed_item()` and calls `mark_completion_recorded()`. Reuse this transition (add a second receiver, or call from it) to add a topic's questions to the bank. Receivers are skipped for `raw`, `update()`, `bulk_create()`.
- Form completion: `form_attempt_completed` signal (`form_engine/signals.py`), receiver at `signals.py:116`; quiz completion also counts via `completed_form_item_ids_by_course_progress` (`queries.py`).
- There is **no persisted "section finished" event for a `CoursePart`**: `learner_progress` never references `CoursePart` (only `utils.py:34` docstring). Part completion would have to be derived (all child placements in `completed_collection_item_ids(record)`, `queries.py:161`). A topic as section is directly a `TopicProgress` row. Test-out (spec 2) will add completion without `mark_complete`; the later spec hooks in.
- Alternative to a signal-populated bank: derive the bank on read ("questions whose section placements in this course are all complete") with no write at completion; avoids missed `bulk`/test-out paths and backfills learners who finished sections before deploy. Needs a decision in the spec.
- Placement is per course: the same Topic may be in two courses; `TopicProgress.collection_item` is the placement. Revision bank is per course (settled), so the question->section->placement must be resolved inside `course_progress.course`.

## 6. Shuffle code reusable

- `form_engine/served_paper.py`: `shuffle_with_locks(items, is_locked, rng)` (:38) is pure and reusable; `_scope_rng(seed, scope)` (:32); `new_seed()` (:27, tests patch it); `_served_options(question, form, seed)` (:55) is gated on `form.shuffle_options` and `QuestionOption.locked`, so revision should call `shuffle_with_locks` itself (bank-form shuffle flag is QUIZ-only, `Form.validate_quiz_fields` :145, and the per-sitting `served_paper` is stored on `FormProgress`, which revision does not have). Decide shuffle each time vs. always; `locked`/`group` semantics come with it. `shuffle_options` on the section's form should probably be honoured as "author wants shuffle" or revision always shuffles; spec must choose.
- Spec dir for the shuffle work: `spec_dd/2. in progress/sacaa-compliance-2-shuffle/`.

## 7. Question template and shells

- `form_engine/templates/form_engine/question.html`: one question's fieldset, legend, input includes (`inputs/multiple_choice.html`, `checkboxes.html`, `dropdown.html`...), reads `question`, `question_positions`, `rejected_answers`, `existing_answers`. Included via `form_engine/partials/page_children.html` by three shells: `learner_interface/course_form_page.html:284`, `course_applications/form_page.html:39`, `educator_interface/modal/content_preview.html:22`. A test pins it as the single rendering (`form_engine/tests/templatetags/test_form_engine_tags.py:73`).
- Revision page can include `form_engine/question.html` as a fourth shell (needs `question_positions` dict and context keys it reads; options come from `question.options.all()` unshuffled, so shuffled order needs to be passed in or the input templates must accept an ordered list; check `inputs/multiple_choice.html`).
- "Correct answer" mark: `form_engine/templates/cotton/correct-answer-mark.html` (reusable for the after-answer display). `cotton/` components are the convention (see `claude_plugins/fls-dev/resources/templates_and_cotton.md`).
- Explanation display goes after each answer: needs HTMX swap per question; follow 422-on-validation-error convention (CLAUDE.md).

## 8. learner_interface course page, URLs, views

- `learner_interface/urls.py` (`app_name="learner_interface"`): `course_home` `courses/<slug:course_slug>/` (view `views.py:1027`), `course_detail` `.../detail/`, `view_course_item` `.../<int:index>/`, `course_finish` `.../finish/`. A new route `courses/<slug:course_slug>/revise/` must not collide with `<int:index>` (it will not; slug vs int, but place it before nothing ambiguous). URL names snake_case, paths kebab-case.
- Link placement: `learner_interface/templates/learner_interface/course_detail.html`, `_course_base.html` and `cotton/player-nav.html` / `player-footer.html` / `partials/course_toc_header.html` are the course chrome; `course_home` is the entry. Paused courses (`test_course_paused.py`) and access rules (`test_course_access.py`) are enforced in views; the revision view must respect `paused` and registration (`learner_progress/queries.py:184 course_progress_for`, "every read path starting from a User goes through here").
- Existing helper: `learner_interface/utils.py`; tests under `learner_interface/tests/views/`.

## 9. Settings pattern

- `base/app_settings.py` `AppSettings` + `Setting(default=..., required=...)`; per-app `config.py` (e.g. `content_engine/config.py:6`). 28 apps have one; `learner_interface` and `learner_progress` and `form_engine` do NOT. Session size etc. belongs on a new `config.py` in whichever app owns the logic (and `docs/` ownership map). Settings are for the downstream installer; per-course or per-form author overrides would need a field.

## 10. App layering (import-linter / app map)

- `test_organisation/import_contracts.toml` is generated ("do not hand-edit"; regenerate via `/ds:app_map`, which also refreshes `docs/app_structure.md`); contracts only forbid an app's **tests/factories** from importing apps outside its runtime deps (not runtime imports). Baselines/exemptions in `test_organisation/{declared_edges,import_baseline,mirroring_baseline,mirroring_exemptions}`. Hooks: `app-map-fresh`, `lint-imports`, `test-mirroring`.
- Runtime edges (`docs/app_structure.md`): `content_engine -> form_engine`; `form_engine -> accounts, base, content_base, markdown_rendering, site_aware_models` (no content_engine, no learner_*); `learner_progress -> content_engine, form_engine, learner_management, accounts, ...`; `learner_interface -> learner_progress, form_engine, content_engine, ...`. `form_engine/tests/invariants/test_import_independence.py` pins form_engine's independence.
- Consequence: the new models (per-learner-per-question state referencing `FormQuestion`, user/learner and, for weak sections, `Topic`/`CoursePart`) cannot live in `form_engine` (would need content_engine/learner edges). `learner_progress` already depends on all needed apps and owns completion receivers: the natural home. A new app (`revision`?) is also possible (needs registering, app map, config, mirroring, `INSTALLED_APPS`). The scheduler (pure, FSRS wrapper) should be dependency-free so flashcards (spec 4) reuse it. `learner_interface` would add the views (already depends on learner_progress and form_engine).
- Tests in learner_progress cannot import `learner_interface`; learner_interface tests cannot import `reports`, `educator_interface`, etc.; learner_interface test baseline allows `course_applications.factories` only.

## 11. Dependencies

- `fsrs` / `py-fsrs` is NOT in `pyproject.toml` (`[project] dependencies` at :7; `import-linter` present in dev groups :74, :232). Adding it is `uv add fsrs`; check Python 3.13 compat and licence (MIT per prior research). FLS is installed into downstream projects, so it becomes a transitive requirement of the package.

## 12. Demo content

- Existing quiz content with `sections:`: `demo_content/functionality_demo_course_parts/02. Core Concepts/03. knowledge-check/` (`form.md:8` default, `1. page.yaml:19` per-question override) and `demo_content/functionality_demo_end_with_quiz/3. quiz/form.md:5`, `5. quiz/form.md:5`. These give the default bank. A bank form sample would be a new sibling directory (e.g. beside the course dirs) with `strategy: UNSCORED` or QUIZ and `sections:` naming parts/topics; explanations need adding to a few questions. Demo tests: `content_engine/tests/demo_content/test_question_sections.py` (marker `fls_internal`).

## 13. Test layout

- Per app `tests/` mirrored to modules (`test-mirroring` hook): `learner_progress/tests/{test_signals,test_models,test_queries,test_attempts}.py`, `learner_progress/tests/quiz_fixtures.py` and `helpers.py` (quiz setup), `factories.py` per app; `learner_interface/tests/views/` (+ `playwright/test_form_flow.py`), `form_engine/tests/test_scoring.py`, `test_served_paper.py`, `content_engine/tests/` (`test_schema.py`, demo_content, `management/`). pytest markers: `playwright`, `fls_internal`, `dev_tooling` (QA seeders, content validator), `ci_only`; sockets disabled; `--dist loadfile`. QA seeders live in `qa_helpers/management/commands/qa_*.py` (e.g. `qa_create_served_paper_scenario.py`, `qa_set_item_completion.py`) — a revision seeder is likely needed for frontend QA.

## Conflicts and risks

- **C1 (conflicts with a settled answer):** answers.md says "a question removed from the source file loses its revision rows with it". Today `content_save` never deletes a `FormQuestion` (question-sections spec "Pruning ... out of scope"; `QuestionAnswer.question` PROTECT), so a dropped question and its revision rows would persist and keep being scheduled. Spec must pick: (a) the loader gains pruning of questions absent from the file (cascade revision rows; PROTECT blocks it for any answered question, so must also handle `QuestionAnswer`), (b) the revision bank excludes questions no longer in the loaded file via a marker updated by each load, or (c) a revision-row FK with CASCADE plus an explicit prune step only for questions with no `QuestionAnswer`. Also `FormQuestionTopic` PROTECT on topic means a dropped-but-stored question blocks topic deletion today.
- C2: option rows without `uuid` are re-created on every load until written back, so an option-keyed history (per-option counts, saved selected options) would orphan; key revision history on question id and store selected option ids carefully, or store the option `value`.
- C3: editing `correct` flags re-marks history if correctness is recomputed; revision log should store the correctness outcome (and rating) at answer time, not recompute.
- C4: no "section finished" event for `CoursePart`; completion hook covers only topics/forms; test-out (spec 2) paths bypass `mark_complete`; receivers skip `bulk`/`update`. Prefer derivation or a shared "section completed" function both specs call.
- C5: `form_engine/question.html` expects shuffled-order options handled elsewhere; a fourth shell needs the pinned test and context contract updated, and `inputs/*.html` must render a given option order.
- C6: `Form.validate_quiz_fields` forces quiz knobs QUIZ-only; a bank-form flag must be allowed on non-QUIZ strategies, and `FormPage`/loader auto-placement rules (sibling dir) must be respected; the fls-content plugin copy and docs must be re-synced.
- C7: ownership: models cannot go in form_engine; adding them to learner_progress grows an app already imported by 10+ apps; a new app needs registration plus `/ds:app_map` regeneration (generated files, do not hand-edit).
- C8: the course page is per course and a topic can be placed in several courses; the bank is per course, so rows should carry the course (or be derived through placements).
- C9: free-text/number etc. questions in the section's quiz must be filtered out (non-choice, no `correct` flags); bank-form questions may be UNSCORED (no strategy marks), `is_quiz_answer_correct` still works from `correct` flags.
- C10: `@claude`/TODO comment in `learner_progress/models.py:43` about `_original_completion_value`; leave in place if touching `CourseItemProgress`.

## Touch / reuse / conflict summary

- Touch: `form_engine` (FormQuestion `explanation` field + migration, schema `explanation`, bank flag on Form, admin, validator), `content_engine` (`content_save.py` save_form/save_form_question, `validate.py`, possibly question pruning), `learner_progress` (new models, completion receiver/derivation, queries), `learner_interface` (urls/views/templates, course page link), `claude_plugins/fls-content` (schema/validate copy, form-files.md), `demo_content`, `qa_helpers` (seeder), docs/app map, `pyproject.toml` (+`fsrs`), a new `config.py` for session size.
- Reuse: `scoring.is_quiz_answer_correct`, `shuffle_with_locks`/`_scope_rng`, `question.html` + `inputs/*`, `correct-answer-mark.html`, question->section link (`topics`/`course_parts`), `TopicProgress` transition, `completed_collection_item_ids`, `course_progress_for`, `AppSettings`, the section-link loader pattern (`replace_question_sections`) for any bank-form handling.
- Conflict: C1 (question removal), C2/C3 (history keys and correctness recompute), C4 (no part-completion event), C5/C6 (template and schema contracts), C7 (app layering).

status: ok
