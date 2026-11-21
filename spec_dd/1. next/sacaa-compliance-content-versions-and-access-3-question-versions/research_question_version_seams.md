# Research: seams for question versioning (codebase only)

Source idea: `idea.md` in this directory, section "sacaa-requirement Version control". SACAA text: a revised question must be blocked from the random questions available to the student but remain in the system for audit. Paths are under `freedom_ls/` unless stated. Two shapes are costed, neither is picked.

## 1. Models today

All in `form_engine/models.py`. Content bases come from `content_base/models.py`: `BaseContent` (site-aware, timestamped; `file_path`, `meta` JSON, `tags` ArrayField), `TitledContent` (`title`, `subtitle`, `description`, `slug`), `MarkdownContent` (`content`).

| Model | Fields and FKs | on_delete |
|---|---|---|
| `Form` (`TitledContent`+`MarkdownContent`) | `strategy` (QUIZ / CATEGORY_VALUE_SUM / UNSCORED), `quiz_show_incorrect`, `quiz_pass_percentage`, `submit_on_exit`; unique (`site`, `slug`) | n/a |
| `FormPage` (`TitledContent`) | `form` FK, `order`, `category`, `condition_option` FK to `QuestionOption` | form CASCADE; condition_option RESTRICT |
| `FormContent` (`MarkdownContent`) | `content`, `form_page` FK, `order`, `condition_option` | CASCADE; RESTRICT |
| `FormQuestion` (`BaseContent`) | `form_page` FK, `order`, `category`, `slug`, `condition_option`, `question` (text), `type`, `required`, `min`, `max`, `decimal_places` | page CASCADE; RESTRICT |
| `QuestionOption` (`SiteAwareModel`, `TimestampedModel`) | `question` FK, `text`, `value`, `order`, `correct` (nullable bool) | question CASCADE |

Ids are uuids (`BaseContent` and `QuestionOption` primary keys are authored or generated uuids). No `FormQuestion` or `QuestionOption` carries a version, retired flag, content hash or git commit. The `QuestionOption` rows have `created_at`/`updated_at` from `TimestampedModel`; `FormQuestion` has them too via `BaseContent`. `updated_at` is overwritten on every `content_save`, so it says "last synced", not "last changed".

Related: `content_engine/models/question_sections.py` has `FormQuestionTopic` and `FormQuestionCoursePart` (through rows, question CASCADE, topic/part PROTECT).

### How `content_save` writes them
`content_engine/management/commands/content_save.py`:
- `save_with_uuid()` calls `model_class.objects.update_or_create(id=uuid, site=site, defaults=fields)` when the YAML item has a `uuid`; otherwise `create()` and writes the new uuid back into the file (`update_file_with_uuid`, `update_file_with_option_uuids`). So rows are updated in place by uuid, everything in the row overwritten on every run, with no change detection and no history.
- `save_form_question()` saves the `FormQuestion` then each `QuestionOption` (by option uuid, `order=idx`, `value=str(option.value)`). Options are not recreated when they carry a uuid; an option with no uuid is created fresh (and its uuid written back to the YAML on that run).
- Nothing is ever deleted: a question or option dropped from the YAML stays in the database, still on its page, still served and still scored. The comment on `_resolve_condition` names this ("questions dropped from the YAML ... leave stale rows"). The idea's "Assume single source ... mark as retired" section is the planned fix for removed content; it is not built.
- `replace_question_sections()` replaces the section through rows each run.
- No git awareness in `content_save` (`git`/`commit` hits in `content_engine` are image cache and unrelated). Recording a commit means new code that shells out or reads `.git`.
- Hand edits bypass `content_save`: `form_engine/admin.py` `FormQuestionAdmin` edits `question`, `type`, etc., and `QuestionOptionInline` edits `text`, `value`, `order` (no `correct`, no delete: `can_delete = False`, `QuestionOptionAdmin.has_delete_permission` False). The idea says to remove question viewing from the admin; editing goes with it.

### What is lost today when a question or option changes
Everything prior: `FormQuestion.question`, `type`, `min`/`max`, `decimal_places`, `required`, and `QuestionOption.text`, `value`, `order`, `correct` are overwritten. A completed attempt's answers still point at the same ids, so every reader (section 3) shows today's wording and today's correctness against yesterday's answer. Only `FormProgress.scores` (a frozen JSON) keeps the old result; `compute_quiz_scores()` can disagree and the results page flags it (`learner_interface/views.py` around 2184, `stored_score_outdated`).

## 2. Learner records

- `FormProgress` (`SiteAwareModel`): `form` FK (PROTECT, "audit record of a sitting"), `user` FK (CASCADE, nullable), `start_time`, `completed_time`, `scores` JSON, `furthest_page_reached`, `asked` JSON (ids of pages, questions, content, written at `complete()`), `served_paper` JSON.
- `QuestionAnswer` (`SiteAwareModel`, `TimestampedModel`): `form_progress` FK (CASCADE), `question` FK to `FormQuestion` (PROTECT), `selected_options` M2M to `QuestionOption` (implicit through table), `text_answer`. Unique (`form_progress`, `question`). `QuestionAnswerFile` one-to-one for uploads.
- Served paper (`form_engine/served_paper.py`, typed as `ServedPaper` in `form_engine/conditions.py`): `{"seed": int, "pages": [{"id", "children": [ids]}], "options": {question_id: [option_ids]}}`. Ids only, no text, no correctness, no version. Written by `ensure_served_paper()` (QUIZ sittings only, once, before the first page; at `complete()` for a sitting without one). `build_served_paper()` reads `page.children()` and `child.options.all()` live, so it serves every row present, retired or not.
- `served_path()` in `conditions.py` rebuilds a `SittingPath` by looking each served id up in the live tree; a missing page, child or option sets `has_missing_served_items` and is skipped. A question left with no served options falls back to its live options.
- If an option row were deleted: the M2M through row cascades away silently (the answer loses its selection), and any `condition_option` pointing at it is RESTRICTed so the delete is refused. The answer's question is PROTECTed from deletion while answered. Nothing deletes options today (no UI, `content_save` never deletes; `dev_tools/management/commands/danger_content_delete.py` wipes all of them, development only). If an option row is changed in place, the answer keeps pointing at it and silently reads as the new text/correctness.

## 3. Readers of question/option text or correctness for a past attempt

All read the live `FormQuestion`/`QuestionOption` row through the answer's FK or the served id. Each would need to read the version instead.

| Reader | Where | Reads |
|---|---|---|
| Scoring (quiz) | `FormProgress.compute_quiz_scores()`, `score_quiz()` in `models.py`; `is_quiz_answer_correct()` and `evaluate_quiz_answers()` in `scoring.py` | `question.options.all()` and `QuestionOption.correct` live. Called at `complete()` (the frozen result, so fine at that instant) and again by the results page to detect staleness |
| Scoring (category) | `score_category_value_sum()` in `models.py` | `QuestionOption.value`, `category` live; not quiz, probably out of scope |
| Results page, incorrect answers | `FormProgress.get_incorrect_quiz_answers()`; view `learner_interface/views.py` ~2168-2173; template `learner_interface/templates/learner_interface/course_form_complete.html` (uses `option.correct`) | live `question`, `options`, `correct` |
| Answer-in-flight rendering | `form_engine/templates/form_engine/question.html`, `inputs/*.html`, `templatetags/form_engine_tags.py` (line ~73 `question.options.all()`), `FormQuestion.rendered_question()` | live; correct for the paper being served now, wrong for a past attempt re-shown |
| Export | `form_engine/exports.py` `answer_value()` (`answer.question.type`, `selected_options` `text`/`order`), `answer_cell()`, `off_path_question_ids()` | live text; the column headers are the live question text |
| Admin answers | `form_engine/queries.py` `answer_groups()` (walks the live form tree; docstring says "the join is to the live form definition, not a snapshot"), `AnswerRow`; `form_engine/templates/admin/form_engine/_answers.html` (`row.question.rendered_question`, `selected_options`); `QuestionAnswerAdmin.answer_preview` and `QuestionAnswerFileAdmin.question` in `form_engine/admin.py` | live text; also lists a final group "Questions no longer on the form" for off-page answers |
| Cohort/learner reports (PDF) | `reports/indexes.py` `load_quiz_questions()`, `build_question_index()` (`correct_option_texts`), `load_selected_options_by_pair()`, `build_sat_questions()`, `load_distractor_rows()`; `reports/gather.py` `wrong_selected_counts[(option.text, option.correct)]`, `question_text=questions.by_id[...].question`; `reports/templates/reports/partials/learner_detail.html` | Reports aggregate across attempts keyed on question id and option id, which assumes one meaning per id. `build_sat_questions()` re-derives correctness from current options. Pairs a sitting with `served_child_ids_by_attempt_id` or every question of the form |
| Applications | `course_applications/templates/course_applications/check_your_answers.html`, `course_applications/api.py` (~103, `QuestionOption._base_manager` prefetch), `course_applications/resources.py` | live text; applications are non-quiz so low priority |
| Educator interface | `educator_interface/panels/course/content_preview.py` (`_condition_question_text()` reads `condition_option.question.rendered_question()`; builds from `path.question_positions()`). `cohort_report_body_region.html` and `panels/common/actions.py` reach reports only. There is no per-attempt educator viewer yet (`sacaa-compliance-4-attempt-review` plans one) | the preview is of the current form, so it reads the live row correctly |
| Resume / page flow | `form_engine/page_flow.py`, `form_engine/views.py` (line ~57 `sitting_path(...).has_question`), `learner_interface/views.py` (1851, 1935, 2069, 2080, 2449) via `current_path()` | ids resolved against the live tree |

The single choke point for "what was this attempt asked" is `sitting_path()` / `current_path()` in `conditions.py`; it returns live `FormQuestion` and `QuestionOption` objects. Making `served_path()` return version-backed objects for a sitting with a served paper would fix scoring, results, admin, export and the future review in one place. The reports in `reports/indexes.py` do not use `SittingPath`; they load questions by form and would need separate work.

## 4. In-progress attempts today

- Learner starts a QUIZ sitting: `ensure_served_paper()` freezes ids, not content.
- `content_save` runs mid-sitting: question text, option text, `correct`, `order` change under the learner on the next page load (the page is rendered from the live row; `served_path()` only fixes which ids and the option order). A reworded question is shown reworded; the answer already saved for it points at the same option ids and is scored against the new `correct` at `complete()`. An option dropped from the YAML stays (never deleted), so nothing disappears. A question dropped from the YAML stays on its page for new sittings too.
- A question that vanished from the form (moved to another form, or deleted by hand where permitted) is skipped by `served_path()` and flagged `has_missing_served_items`; the results page then declines to challenge the stored score.
- Non-QUIZ forms get no served paper (`ensure_served_paper()` returns for non-QUIZ); `current_path()` falls through to `compute_path()` over the live tree. A retire filter would need to be added there too if non-quiz forms should honour retirement.
- Resume reads `furthest_page_reached` and `current_path()`; it has no content check.

## 5. Seams for two shapes

### (a) Immutable `FormQuestionVersion` row per question
Shape: `FormQuestionVersion` (`question` FK, `number`/created `at`, `text`, `type`, JSON snapshot of options including `value`, `order`, `correct`, `content_hash`, `git_commit`, `retired` flag or `superseded_by`). `content_save` creates a new row when the hash of the question plus its options differs from the latest. `FormQuestion` stays the live, authoring-facing row.

Touches:
- `content_save.save_form_question()`: compute hash from `question`, `type`, options' `text`/`value`/`order`/`correct` (and other fields, section 6), compare with latest version, insert. Needs a git-commit lookup (new; none exists).
- `FormProgress.served_paper` and/or `QuestionAnswer`: record the version id. Cheapest is an extra `"versions": {question_id: version_id}` key in `ServedPaper` (ids-only JSON stays consistent with the shipped spec; no migration beyond JSON shape, old papers lack the key). A nullable `QuestionAnswer.question_version` FK is the alternative, which also covers non-QUIZ sittings with no served paper.
- `served_path()` / `SittingPath.options_of()` / `build_served_paper()`: read text and options from the version. `SittingPath` currently holds model instances; templates call `question.rendered_question()` and `option.text`, so the version needs to expose the same API or the instances need to be proxy-built from the snapshot. This is the largest cost.
- `scoring.is_quiz_answer_correct()` takes `QuestionOption` objects with `.id` and `.correct`; the snapshot's options must keep the live option ids so `QuestionAnswer.selected_options` still match, or answers must also store option ids in the snapshot.
- Serving: "blocked from the random questions" becomes `build_served_paper()` (and `compute_path()`) filtering on a retired flag on the live row, as the live `FormQuestion` is the unit that is drawn or shuffled.
- Retiring: a removed or reworded question needs no new `FormQuestion` row, so `condition_option`, `FormQuestionTopic`, shuffle groups, pools and `QuestionAnswer.question` PROTECT are undisturbed.
- Readers in section 3 that join on live rows: `answer_groups()`, `exports.answer_value()`, `reports/*` need a version lookup. The reports are the awkward ones (aggregate per live question).
Cost: moderate model plus one new table; reads change at `served_path()`, admin/export and reports. Old attempts have no version: a backfill creating version 1 from the current state for every question is needed, and is only accurate for text that never changed.

### (b) New `FormQuestion` rows per revision, old retired
Shape: on a changed hash, `content_save` creates a new `FormQuestion` (new uuid) and its options, marks the previous one `retired_at`/`superseded_by`. Authors' YAML uuid would no longer be the primary key; it becomes a stable "lineage" key.
Touches:
- Identity: `save_with_uuid()` is keyed on `id=uuid`. A lineage key (new field on `FormQuestion`, e.g. `source_uuid`) plus a new id per revision, and every `update_file_with_uuid` / `update_file_with_option_uuids` / `_resolve_condition` / `options_by_slug` assumption (one row per authored uuid) has to change. `QuestionOption` likewise (each revision's options new rows, so old `selected_options` stay valid, which is the main attraction: `QuestionAnswer.question` and `selected_options` need no change and `served_paper` ids stay correct).
- `FormPage.children()`, `compute_path()`, `served_path()`, `build_served_paper()`, `count_form_questions()`, `form_questions()`, `page_questions()`, `load_quiz_questions()`, `FormQuestion.question_number()`: exclude retired rows (many query sites; a default manager filter would hide them from audit readers too, so an explicit filter is safer).
- `order` collision: two rows at one order on a page, one retired.
- `condition_option` (RESTRICT) and gated rows: a revised source question creates new options; the gated page/content/question must be repointed or the new condition is lost. `when` is banned on QUIZ forms per the shuffle/pool specs, so the cost is limited to survey forms; but the rule must be written down.
- `FormQuestionTopic` / `FormQuestionCoursePart`: must be copied to the new row.
- Unique `slug` within a form: the retired row shares it; no DB unique constraint on `FormQuestion.slug` exists today (only `Form` has one), but the validator checks the YAML.
- Admin answers (`answer_groups()`) already has a "Questions no longer on the form" group, which already fits a retired row's answers. Export columns: one column per live question, so a retired row's answers would need a column or a "retired" group. Reports aggregate by question id, so a revised question splits into two stats rows (arguably right).
- Resume of an in-progress sitting: its `served_paper` names the old row; `served_path()` still finds it if retired rows stay in the lookup; only fresh drawing excludes them.
Cost: lower new-table cost, higher blast radius in content_save and in every query that walks pages; the version history across revisions has to be reconstructed via the lineage key. Reads of past attempts need no change.

Common to both: a hash definition, a migration/backfill, a hook for the git commit, and an answer to "what happens to answers recorded before versions existed".

## 6. What "changes in any way" could cover

| Aspect | Exists as a field? |
|---|---|
| Question text | yes, `FormQuestion.question` (markdown, may embed cotton components and `![[image]]` translated to `<c-picture>` by `markdown_translate`; note `save_with_uuid` translates after `update_or_create`, so the hash must be taken on the stored value, not the authored one) |
| Type | yes, `FormQuestion.type` |
| Required | yes, `FormQuestion.required` |
| Bounds / precision | yes, `min`, `max`, `decimal_places` (scoring-irrelevant for quiz, but validity-relevant) |
| Option text | yes, `QuestionOption.text` |
| Option value | yes, `QuestionOption.value` (used by CATEGORY_VALUE_SUM scoring) |
| Option order | yes, `QuestionOption.order` (and the served order, which is already in `served_paper["options"]`) |
| Correctness | yes, `QuestionOption.correct` (nullable: None counts as neither required nor forbidden) |
| Option added/removed | yes, rows; removal currently leaves a stale row (section 1) |
| Explanations / feedback | no field on `FormQuestion`, `QuestionOption` or the pydantic `QuestionOption` in `form_engine/schema.py` (`extra="forbid"`) |
| Scoring settings | per-form only: `Form.strategy`, `quiz_pass_percentage`, `quiz_show_incorrect`. Each question counts 1; no per-question marks |
| Category | `FormQuestion.category`, `FormPage.category` (CATEGORY_VALUE_SUM) |
| Tags / meta | `BaseContent.tags`, `meta` (not scored; `content_save` leaves tags alone when the key is absent) |
| Sections | `FormQuestionTopic` / `FormQuestionCoursePart` through rows, not fields on the question |
| Condition | `condition_option` FK (survey only in practice) |
| Position | `order`, `form_page` (moves are placements, not revisions) |
| `file_path`, `slug`, `updated_at` | change on file moves; should not count as a revision |

A defensible rule: version on the learner-visible and scoring-relevant fields (`question`, `type`, `required`, `min`, `max`, `decimal_places`, and every option's `text`, `value`, `correct`, plus the set of options), and exclude `order` placement, `file_path`, `slug`, `tags`, `meta`, `sections`. Option order within the question is arguably learner-visible; with shuffle the served order is already per-sitting, so authored order is a judgement call. The idea says "in any way" and "exact text matching", so the simplest contract is to hash a canonical serialisation of the whole question and its options and exclude only housekeeping fields. `FormContent` (stimulus text) and `FormPage` have no version and are not in the idea's list, but a stimulus rewrite changes what a question asked; flag this to the author of the cut.

## 7. Interaction with shuffle and pool specs

(From `sacaa-compliance-2-shuffle/idea.md` and `sacaa-compliance-3-question-pools/idea.md`; both build on the shipped served-paper record.)
- Shuffle shuffles at attempt start and writes order into `served_paper`; it reads the live tree, so the retire filter must apply before the shuffle (in `build_served_paper()`), else a retired question could be shuffled in. A keep-together group is a contiguous run of content blocks and questions on a page; if one member question is retired, the group is left with a hole or a stimulus with fewer questions. Rule needed: retire the whole group, or keep serving the group minus the retired member, or block the content_save.
- Pools: a draw is "N items from the page", drawn from the page's questions and groups. A retired question must leave the pool before the draw, and a pool of N from fewer than N left items is a content_save-time validation error (the pool spec already requires N at most the number of items). With shape (b), the replacement row joins the pool and the old leaves: the pool size is stable. With shape (a), the live row stays in the pool and only its served content changes, so pool membership never changes on a revision; an "also retire entirely" flag is only for removal from the YAML.
- A pool requires every item to carry the same number of questions (`max_score` stays constant); a revision must not change the number of questions in a group.
- "Retired mid-draw": a sitting's draw is persisted at start (`served_paper`), so a question retired after the draw stays in that sitting's paper. That is consistent with SACAA ("not served any more" means to new papers) and with a frozen paper. State it in the spec.
- `max_score`: the served set is the denominator; retiring does not alter an already-completed sitting's `scores`.
- Educator preview reads the full form; it should show retired questions marked or hide them (decision).
- Review spec (`sacaa-compliance-4-attempt-review/idea.md`): it explicitly says "Question wording is the current wording" and defers freezing; this idea is what removes that caveat, so the review must read versions through `sitting_path()`.

## Implications for the cut

1. Decide the unit first: version row (a) is additive and keeps `FormQuestion` ids stable (so `QuestionAnswer`, `served_paper`, `condition_option`, shuffle groups and pools are untouched); (b) puts the cost into every query that walks the live tree and into `content_save` identity. The existing code is built around stable ids with ids-only JSON, which favours (a) in effort, but do not decide here.
2. Whichever shape, `served_path()` / `sitting_path()` / `SittingPath` (`form_engine/conditions.py`) is the single reader to change for the learner path, results, admin and the future educator review. Reports (`reports/indexes.py`, `reports/gather.py`) and `exports.py` do not all go through it and need their own cut line (one spec, or leave aggregate reports on live rows with a stated limitation).
3. Two separable concerns: (i) "block from serving" (a retired flag honoured in `build_served_paper()` and `compute_path()`; the removed-from-YAML half is already in the idea's "retired" section) and (ii) "audit what was answered" (the version record plus a pointer from the sitting). They can ship in order, and (i) alone satisfies the first half of the SACAA sentence.
4. The cut needs a rule for what hash covers (section 6), including that markdown is translated after save, and whether option order, `FormContent` and `FormPage` count.
5. Options are never deleted today and a question dropped from the YAML is still served; the retire work and the single-source work in the same idea overlap here. Decide whether "removed" and "revised" share one retired state.
6. Backfill: existing attempts have no version. A first version taken from current content is honest only if stated as "version 1 = content at migration time".
7. In-progress sittings: with ids-only served papers, a reworded question changes under a mid-attempt learner. The cut should say whether the served paper pins the version at attempt start (the natural reading of "answered version") and whether a sitting in flight keeps its retired question.
8. Git commit: `content_save` has no git code; the idea's "possibly git hash" is new code and ties to the single-source/git-repo requirement in the same idea. Make it optional on the version row.
9. Hand edits in the admin (`FormQuestionAdmin`, `QuestionOptionInline`) change a question without `content_save`; they are removed by the idea's "remove question viewing from the admin" item, but until then they bypass any versioning hook placed only in `content_save`. A hook on model save would cover both; a hook in `content_save` is simpler.
10. Coordinate with the shuffle and pool specs: apply the retire filter before shuffling and drawing; define behaviour for a retired member of a keep-together group; validate pool size after retirement.

status: ok
