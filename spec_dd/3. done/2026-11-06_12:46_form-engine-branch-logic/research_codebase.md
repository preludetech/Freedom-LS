# Research: what the existing codebase touches, reuses and conflicts with

Spec: `form-engine-branch-logic`. Read against `idea.md` and the five existing `research_*.md` (not
repeated here). All paths are under the project root; line numbers are as of branch
`form-engine-branch-logic` at 55e9444a0.

## 1. Model layer (`freedom_ls/form_engine/models.py`)

- `Form(TitledContent, MarkdownContent)` L50; `FormPage(TitledContent)` L89 (`order`, `category`,
  `children()` L98 merges `text_items` + `questions` sorted by `order`); `FormContent(MarkdownContent)`
  L118; `FormQuestion(BaseContent)` L136; `QuestionOption` L218; `FormProgress` L239; `QuestionAnswer` L667;
  `QuestionAnswerFile` L717.
- `FormQuestion` has `form_page` FK, no `form` FK, no `title`, no `slug`. "Unique within its form" cannot be
  a `UniqueConstraint` over `form_page__form` (constraints cannot span a relation). Options are a
  denormalised `form` FK (new column), or a check at import only. Existing rows would get a blank slug,
  so any DB constraint has to exclude blank.
- `FormContent` is a `MarkdownContent` (no `TitledContent`), `FormQuestion` is `BaseContent`. Neither has
  `slug`; `FormPage.slug` is derived from title by the importer (below), so it is not author-chosen.
  Only `FormQuestion` would get an authored slug.
- `QuestionAnswer`: `UniqueConstraint(form_progress, question)` L679; `question` is `on_delete=PROTECT`
  (a question with answers cannot be deleted, so "question leaves the form" is already handled by the
  `FINAL_GROUP_TITLE` group in `queries.answer_groups`). `QuestionAnswerFile` is a OneToOne cascade with a
  `post_delete` receiver (`receivers.py` L15, `delete_question_answer_file`) that removes the stored
  object. Deleting an off-path file-upload answer at submit therefore also deletes the applicant's file
  from `user_uploads` storage. This is irreversible, unlike the text-answer rows.
- `FormProgress.furthest_page_reached` (L266, migration 0004) is a `PositiveSmallIntegerField` page
  *number* set by `record_page_reached` (L306, forward-only). There is no per-sitting record of pages or
  questions shown. Nothing else on `FormProgress` can hold a "path": it has only `scores` (JSON,
  `null` until complete), `completed_time`, `furthest_page_reached`.
- Migrations: `form_engine/migrations/0001`..`0008` (latest `0008_alter_formprogress_user`; app label
  `freedom_ls_form_engine`). Any new field (`slug`, `when`, a path record) is `0009`+. Never edit existing.

## 2. Page arithmetic: every caller of "all pages are in play"

The idea names `paging.py`; the following are the full set, including three it does not name.

`freedom_ls/form_engine/paging.py`:
- `_furthest_answered_page` L27, `_resume_page_number` L42, `resume_page_number` L54,
  `page_accessibility_limit` L69, `build_page_links` L76 (limit is `max(resume, current)`, `is_accessible`
  = `number <= limit`), `unanswered_required_on_page` L97 (reads POST, file questions read the stored
  row), `unanswered_required_in_form` L120 (reads `form_questions(form)` against `answers`),
  `answered_counts` L152 (`answered_count = form_progress.answers.count()`, no filter by question;
  `total_question_count = count_form_questions`), message builders L134/L143 (use `question_number()`).
- Not named in the idea: `FormProgress.get_current_page_number` (`models.py` L317) is the "first page with
  an unanswered question" walk that `_resume_page_number` feeds from. It walks every page's questions with
  one `.exists()` query each and treats an unanswered *optional* question as pending. It needs the same
  path-awareness as `resume_page_number`, and `resume_page_number` is its main consumer.
- `answered_counts` counts `form_progress.answers` unfiltered, so once off-path rows survive during a
  sitting (the idea's rule) the "answered" numerator drifts above the path-derived denominator unless it
  is filtered too. `answered_other_pages` is the base the Alpine progress component adds the live
  current-page tally to (`course_form_page.html` L63 `data-answered-base`, L187 `x-text="answeredCount"`).
- `question_number()` (`models.py` L194) walks `form.pages.all()` / `page.questions.all()` and is
  *per call* O(questions) with queries. It is rendered twice per question in `form_engine/question.html`
  L12 and L17 (`data-testid="question-number-{{ n }}"` and `required-indicator-{{ n }}`). Its ordering is
  `page.questions.all()` (model `Meta.ordering = ["order"]`), and it ignores interleaved `FormContent`.
  `reports/indexes.py` L525-579 explicitly says DO NOT call it and re-derives numbering from
  `order_by("form_page__order", "order")` into `QuestionIndex.number_by_id`, and `gather.py` L485/L534
  reads that. So there are already two independent implementations of "stable ordinal in the full form";
  the idea's "keeps meaning what it means now" holds for both so long as neither is path-filtered.
- Course start screen (not named in the idea): `learner_interface/views.py` L1810-1811 passes
  `question_count = count_form_questions(form)` and `page_count = form.pages.count()` to
  `course_form.html`, and `qa_helpers/management/commands/qa_create_form_count_edge_cases.py` builds fact
  pills from the same two numbers. A pre-sitting count is by definition not path-aware; the start screen
  will quote the whole-form number unless changed.
- `queries.py`: `count_form_questions` L61 (single `COUNT`), `page_questions` L70, `form_questions` L82
  (every question in page order; the base of `unanswered_required_in_form`, `exports.answer_columns`),
  `answer_groups` L105 (admin answer view; walks all pages and emits a row per question with
  `answer=None` => "Not answered").

`freedom_ls/form_engine/page_flow.py`:
- `CurrentPage` L36 holds `all_pages` and `is_last` (`number == len(all_pages)`); `page_at` L59 and
  `resolve_page` L73 404 only for an out-of-range number. A page whose condition is false is a valid
  number today and would render. `page_context` L139 sets `next_page_url`/`previous_page_url` as
  `number +/- 1` and `has_next_page = not is_last`. `submit_page` L99 passes `current.questions` (all of the
  page's questions) to both `unanswered_required_on_page` and `form_progress.save_answers`.
  This is the single choke point for the idea's "save_answers must be given the questions the path
  says apply" rule, and it is shared by both runners and `form_submit_and_exit`.

`FormProgress.save_answers` (`models.py` L356): a blank submission *deletes* the row for that question
(L381-383), so an off-path question that is blank in the POST is already deleted if it is in the list
passed in. The idea's "keep during sitting" rule therefore only holds if off-path questions are not
passed to `save_answers` at all (its docstring: "A question submitted with no answer ... loses any row").
File questions are skipped there (L375) and use their own endpoints.

`form_engine/views.py` L81-153 (`partial_question_file_upload`, `partial_question_file_remove`) accept
any `FILE_UPLOAD` question of the sitting's form (`_owned_file_question` L36 matches only
`form_page__form`). They are not path-aware, so an off-path file question can be uploaded to and removed
by direct POST. That endpoint also writes `QuestionAnswer` rows outside `save_answers`.

## 3. The two runners and the check-your-answers page

- Course player: `learner_interface/views.py` `form_fill_page` L1944 -> `submit_page` ->
  on accepted: `if not current.is_last: redirect(page_number + 1)` else `form_progress.complete()` and
  redirect to `course_form_complete` (L1992-2004). Skipping page N+1 means `is_last` is false on the last
  *applicable* page; the "+1" and `is_last` completion decision both have to be path-derived.
  `form_start` L1818 and the start screen L1789 use `resume_page_number`. `_render_form_fill_page` L1886
  calls `record_page_reached` L1918 and merges `answered_counts` L1927. `form_submit_and_exit` L2266
  calls `submit_page(..., require_answers=False)` then `complete()`: required questions are explicitly
  unenforced there, so "complete() deletes off-path answers" runs on a partial sitting.
- `FormProgress.complete()` (`models.py` L403) is the one finalising method (idempotent, score, signal
  `form_attempt_completed`). It is also called from `form_engine/admin.py` (comment L325) and from several
  `qa_helpers` commands. The natural home for "delete off-path rows on submit" and "freeze the path" is
  here, but note `complete()` has no `require_answers` knowledge and `unanswered_required_in_form` is
  checked only by the application view, not by `complete()`.
- Application shell: `course_applications/views.py` `application_form_page` L722. `RETURN_TO_CHECK = "check"`
  L719, read from `request.GET["return"]` L740. On an accepted POST: `if not current.is_last and not
  return_to_check: redirect(next)` else `redirect(check_answers)` L751-753. The marker rides the query
  string through the 422 re-render (the form posts to its own URL). `form_page.html` L47-61 switches the
  Back and submit labels ("Back to your answers" / "Save and return to your answers") on it.
  `_resume_url` L706 sends a zero-page form straight to check answers. Edit links come from
  `application_check_answers` L781 (`edit_url = _page_url(...)?return=check` L829).
  `application_check_answers` builds `sections` by iterating **every page** with `page_questions(page)`
  L822-835, showing "Not answered" for rows without an answer (`check_your_answers.html` L69-71); a
  skipped page would render as an empty/all "Not answered" card unless filtered. The POST path L795-812
  uses `unanswered_required_in_form` then `complete()`; that is the place for the delete-on-submit.
- `app.is_submitted` is derived from the sitting; read-only render (L737) for a completed sitting re-reads
  pages via `application_form_page`, so a frozen path must also drive the read-only page nav and the
  check-your-answers `submitted` view.
- Query-string marker tests: `course_applications/tests/test_views.py` has 7 references to the marker.
  `data-testid` exists only on `form_engine/question.html` (L12, L17) and `course_form_page.html`
  (`leave-and-submit-button` L154, `answered-summary` L186, `page-indicator` L198, `modal-answered-count`
  L396). The application shell templates (`form_page.html`, `check_your_answers.html`) carry none, so
  the "identity that does not shift" argument for `question_number` rests on those two templates plus
  the "Question N needs an answer" messages, not on any application-shell test id.
- Page-jump nav: `build_page_links` output is consumed by `course_form_page.html` L29 (dots) and
  `course_applications/form_page.html` L20 (via `cotton/form-page-link.html` L36). The nav has a numeric
  label per page (`number`), which would show gaps (1, 2, 4) if a skipped page is just omitted unless
  numbering is also path-derived. `course_form_page.html` L199/L203/L232-255 renders "Page X of
  {{ total_pages }}" and a `widthratio current_page_num total_pages` progress bar. `total_pages` comes from
  `CurrentPage.total_pages` (`len(all_pages)`), so a denominator the idea does not name besides
  `total_question_count`. The `<h1 class="sr-only">` also carries it.

## 4. Scoring and reports

- `score_category_value_sum` (`models.py` L414-541): walks all `form.pages` x `children()`; for
  `multiple_choice` / `dropdown` only; per question `max_value` = **highest numeric option value**
  (not 1 per question), `value` = first selected option's int (else 0); nested via `|`-split
  `page.category`, then `question.category`, "Uncategorized" fallback. Output shape:
  `{cat: {score, max_score, sub_categories: {...}}}`. This is the loop that has to take the path to make
  `max_score` per sitting and to drop an inapplicable `page.category` subtree. Note `self.answers.get(...)`
  per question (N+1) and `self.save()` at the end.
- `compute_quiz_scores` L543 / `score_quiz` L579 / `get_incorrect_quiz_answers` L600: untouched if
  quizzes are rejected, which is consistent with the idea. `queries.quiz_verdict` L20 and
  `attempt_completes_form` L46 only act on QUIZ.
- Important correction to the idea's reporting claim: `freedom_ls/reports/` reads
  `scores["max_score"]` **only for QUIZ forms**. `gather.py` `_score_attempt` L366-389 calls
  `fp.quiz_percentage()` (raises `ValueError` unless `scores` has top-level `score` and `max_score`, i.e.
  not the category-tree shape), and the collection is gated by `is_quiz=item.strategy == FormStrategy.QUIZ`
  (`gather.py` ~L360). `QuizAttempt.max_score` and `QuizResult.latest_max_score` are per attempt already
  (`report_data.py` L36, L46) and rendered per attempt in `learner_detail.html` L76 and
  `quiz_result_cell.html` L14. There is no existing reports surface that reads a `CATEGORY_VALUE_SUM`
  `scores` tree, so "reports must present out of N per learner" has no current consumer to change. If a
  survey-score report is wanted it is new work, not a modification.
- Where a category-tree `scores` is shown today: `learner_interface/templates/learner_interface/
  course_form_complete.html` L189-228 (per category and sub-category `score / max_score`, `widthratio`),
  `partials/form_progress_scores.html` L1-15, and `learner_progress/admin.py` L82-83 (reads `score`,
  `max_score` from `attempt.scores`). All read each sitting's own `scores`, so a per-sitting tree is
  already the display model. A category absent from the tree means its row is simply not rendered.
- `exam_previous_attempts.html` L25-32 and `exam_score_ring.html` L56-60 read `scores.score` / `max_score`
  for QUIZ only.
- `reports/indexes.py` `load_quiz_questions` L525, `build_question_index` L550, `load_selected_options_by_pair`
  L582, `build_sat_questions` L608: "every scorable question each completed sitting covered" is computed
  as `completed_attempt_ids x questions.by_form`. This already encodes the same "what this sitting was
  shown" assumption (full form) that the compliance randomization spec will break. It is QUIZ-only, so
  out of scope here, but it is the code the compliance spec will have to change to read a per-attempt record.

## 5. Importer and schema

- Form directory = `form.md` (FORM) + page YAML files; each page file is split on `---` into sections
  (`content_engine/validate.py` `split_yaml_documents` L162, `parse_yaml_file` L239). First section is the
  FORM_PAGE; later sections: `derive_content_type` in `form_engine/schema.py` L96 (`content` => FORM_CONTENT,
  `question` => FORM_QUESTION).
- Schemas: `form_engine/schema.py` `Form` L40 (`validate_quiz_fields` L67 quotes `file_path`), `FormPage`
  L93, `QuestionOption` L103 (`extra="forbid"`, `value: int | str`), `FormContent` L117,
  `FormQuestion` L121 (`BaseBaseContentModel`, `extra="forbid"` from `content_base/schema.py` L26, so
  any new key, `slug` or `when`, is rejected until the schema declares it on each of the three classes).
  `BaseBaseContentModel.file_path` L33 is a `Path`, `uuid` L34 an optional `str`.
- `content_engine/validate.py` runs per-file Pydantic and then **cross-file passes** over `all_parsed`
  (L968-981): `validate_category_references` L443, `validate_widget_references`, `validate_children_lists`,
  `validate_due_date_placements`, `validate_article_images`. All return error strings that are appended to
  `failed_files`. This is the existing seam for the earlier-page, dangling-reference, cycle and
  option-value checks (they need the whole form's page order, so cannot live in a per-section validator).
  `content_save` consumes the same validated items.
- Page order assigned at save: `content_save.py` L1011 `for page_order, (file_path, page_items) in
  enumerate(sorted(form_pages))` -- sorted by **file path as a string/Path**, so `10. x.yaml` sorts
  before `2. y.yaml` (lexicographic). `FormPage.order` is therefore the loader's order, not the author's
  number. The earlier-page check must use the same sort, or it will disagree with `FormPage.order`
  that the runner uses. In the same loop, question `order` = index within the file among content/question
  items (`content_order`, L1031), shared with `FormContent` ordering.
- Slug / uuid assignment (`save_with_uuid` L252): drops `content_type`, `file_path`, `uuid`; dumps
  fields with `exclude_none=True`; checks every dumped field exists on the Django model (L306-319, raises
  naming the unknown fields); if `derive_slug` (default True) and the model has `title` and `slug`, sets
  `slug = get_unique_slug(model_class, site, slugify(title), item.uuid)` (L322-324). With a `uuid` in the file
  it does `update_or_create(id=uuid, site=site, defaults=fields)` (L326-329), otherwise creates and writes
  the uuid back into the file (`update_file_with_uuid` L119, via `PreservingDumper` L90, `yaml.dump` the
  section). Consequences:
  - A new `slug` on `FormQuestion` would not be clobbered (no `title` in its fields so derivation is
    skipped), but `FormPage` and `Form` slugs are always derived; there is no way for an author to set them.
  - **Absent key does not clear.** `exclude_none` means a `when:` removed from the YAML leaves the old
    stored condition in place on the existing row (`update_or_create` only writes `defaults`). The same trap
    is documented at `content_save.py` L1047-1049 for `Course.application_form`, which writes `None`
    explicitly to unbind. A stored `when` needs the same explicit-null treatment, or it never goes away.
  - Options: `save_form_question` L682-715 converts `option.value` to `str(...)`. YAML `value: 1` is an int
    in the schema (`int | str`), and a condition literal compared against `QuestionOption.value` must
    normalise the same way (`str`) or `equals: 1` never matches. Unquoted `yes` / `no` / `on` parse as
    booleans under PyYAML's YAML 1.1 `safe_load`, so the idea's `equals: "yes"` example works only because
    it is quoted. The existing `min`/`max` fields already carry `_coerce_bound_to_str` (`schema.py` L181) for
    exactly this reason; a `when.equals` needs the same coercion (and a check for bool arriving where a
    `QuestionOption.value` string was meant).
  - `update_file_with_uuid` re-dumps a section with `yaml.dump`: a hand-written `when:` block round-trips
    through `PreservingDumper`; worth a test that a `when` mapping and comments are not mangled.
- The importer deletes nothing: a question removed from the YAML is not deleted (answers `PROTECT` it);
  it is left in the DB and `queries.answer_groups` reports it in the "Questions no longer on the form"
  group. Not specific to this feature, but "dangling reference" validation has to be on the YAML, not on
  the DB state, or it will see removed questions.
- Offline mirror: `claude_plugins/fls-content/validate/schema.py` (bundled copy; header L1-8 states it
  mirrors `form_engine/schema.py` and `typed_answers.py` and that "a stale FormQuestion rejects valid
  content (extra=\"forbid\")") and `claude_plugins/fls-content/validate/validate.py` (also holds the
  cross-file passes). Re-sync is via `/update_claude_plugin_fls_content`. Any `slug`/`when` schema change
  must be mirrored there or the author's validator rejects what `content_save` accepts. Author docs to
  update: `claude_plugins/fls-content/skills/content-types/resources/form-files.md` (field tables for
  FORM_PAGE L84-92, FORM_QUESTION L113-127, FORM_CONTENT L266-271), `file-layout.md`, `SKILL.md`,
  `agents/content-formatter.md`; product doc `docs/product/content-editing-workflow.md` L41-44. Tests
  that mirror the schema: `claude_plugins/fls-content/validate/tests/test_validator.py`.

## 6. Educator and admin display, exports

- The educator interface has no answer view of its own (no `FormProgress`/`answer_groups`/`.answers`
  references in `educator_interface` non-test code). Answers are shown in Django admin:
  `form_engine/admin.py` L270 `answer_groups(form_progress)` -> `admin/form_engine/_answers.html` /
  `answers_change_form.html`; `FormProgress` admin L325-350 exposes `scores` and `furthest_page_reached`.
- CSV/XLSX export: `form_engine/exports.py` `answer_columns` L30 builds one column per question currently
  on the form's pages (`form_questions`) plus orphans; `answer_cell` L115 renders an empty string for no
  answer. `course_applications/resources.py` (L59-111) uses it for application export (prefetch of
  `form_progress__answers__*`). With off-path answers deleted at submit, a column for a skipped
  question is blank, indistinguishable in the export from "asked and left blank" unless the path record
  is consulted. Same ambiguity exists in `answer_groups` ("Not answered" for both).
- `dev_tools/management/commands/danger_content_delete.py` L96 and `danger_clear_all_course_progress.py`
  L15 delete `QuestionAnswer` rows by model; a new path-record model would need adding to both lists
  (both note ordering because `QuestionAnswer.question` is `PROTECT`).

## 7. Tests, factories, QA helpers

- `form_engine/tests/`: `test_models.py`, `test_paging.py` (18 tests), `test_page_flow.py`,
  `test_schema.py`, `test_scoring.py`, `test_submissions.py`, `test_typed_answers.py`, `test_views.py`,
  `test_queries.py`, `test_exports.py`, `test_admin.py`, `test_uploads.py`, `test_signals.py`,
  `test_session_access.py`, `test_permissions.py`, plus subdirs `invariants/test_import_independence.py`,
  `playwright/test_admin_answers_layout.py`, `templatetags/`. `form_engine/factories.py` has
  `QuestionAnswer` factory (L97). Tests for the learner runner live in `learner_interface`, and for the
  application shell in `course_applications/tests/test_views.py` (marker tests). The roadmap notes
  `test-organisation-and-hygene-9` (form_engine) and `-14` (learner_interface form tests) will move
  these files; `roadmap.md` L309 says to move test files in their own commit to survive the rebase.
- `invariants/test_import_independence.py` guards `form_engine`'s dependency set (`docs/app_structure.md`
  L303: form_engine depends on accounts, base, content_base, markdown_rendering, site_aware_models). A
  condition evaluator in `form_engine` is within it. `reports` already imports `form_engine`
  (`app_structure.md` L320).
- `qa_helpers` commands that build sittings directly and would bypass any new path-recording step:
  `qa_complete_form.py` (L120, goes through `complete()`), `qa_create_report_cohort.py`,
  `qa_create_second_application_form_course.py` L144 and `qa_create_bulk_applications.py` L97 (both set
  `furthest_page_reached` by hand), `qa_create_form_attempt_history.py` L227 (writes `max_score =
  count_form_questions(form)`), `qa_create_legacy_checkbox_score.py`. Any non-`complete()` writer of
  `FormProgress` yields a completed sitting with no path record.

## 8. Demo content

`demo_content/functionality_demo_application_form/`: `form.md` (UNSCORED), `1. about-you.yaml` (page
with 1 FORM_CONTENT + 8 questions: short_text, date, email, phone, url, number, multiple_choice
"How did you hear" with `value: other`, checkboxes, long_text), `2. supporting-documents.yaml`,
`3. availability.yaml`. All uuids are written. There is a natural fit for a demonstration: the
"Somewhere else" (`value: other`) option on page 1 is exactly the "Other, please specify" case the idea
says now costs a page break, so a follow-up has to go on page 2+. None of the existing files has a slug on
any question. A demo of branching would need a new page or a new demo form; the demo is also what
`qa_helpers` and the application-form tests lean on, so changing its existing pages changes their
question counts.

## 9. Other specs touching `form_engine`

- `spec_dd/2. in progress/compliance-form-randomization/` (`idea.md`, two research files, `todo.md` with
  only idea ticked). Overlap and conflicts with this spec:
  - Its "per-attempt record of the realised order and subset" and "Templates render from the
    realized-order record, not from DB `order`" (idea L69) are the same record as this spec's path. It
    scopes to `Form(strategy=QUIZ)` and keeps "`FormProgress.scores` (`{score, max_score}`) should not need
    to change" and constant `max_score` via a fixed draw count; this spec has a per-sitting `max_score`
    on `CATEGORY_VALUE_SUM` and rejects conditions on a QUIZ. The two do not collide on the same form
    types, but both want one persisted record, and neither has chosen its shape.
  - It introduces a `FormGroup` between `FormPage` and its items; this spec attaches `when` to
    `FormPage`, `FormQuestion` and `FormContent` directly. If groups land first, "show this block" may
    prefer a condition on the group; if conditions land first, a group inherits the evaluator.
  - It changes the ordering source (realized order) that `question_number()`, `resume_page_number`,
    `build_page_links`, `page_at(form, number)` and `reports/indexes.py` (`order_by("form_page__order",
    "order")`) all derive from DB `order`. This spec's rule that `question_number()` stays "a stable
    ordinal in the full authored form" conflicts in spirit with a shuffled order, but the two forms
    are disjoint (QUIZ vs non-QUIZ), so the conflict is only in shared code, not shared data.
  - Both extend `FormProgress`; both create `form_engine` migrations (numbering collision, `0009`).
  - Both touch `paging.py`/`page_flow.py`/`models.py`, so expect merge conflicts there.
- `spec_dd/1. next/roadmap.md` L895 and L907 already cross-reference the two. L309 and L544 flag
  `test-organisation-and-hygene-9` meeting both in `form_engine`. L898 `phone-number-form-field`
  adds a question type in the same files (`QuestionType`, schema, `typed_answers`, fls-content mirror).
- `spec_dd/1. next/multi-step-course-applications/idea.md` L34-35 names this spec as covering "ask
  about previous qualifications and branch on the answer". It is a consumer: its "reviewer sends the
  applicant down a different path" case would need a path that changes *after* submission, which this
  spec's frozen-at-submit path does not provide (out of scope here, but worth a note).
- In progress `learner-facing-ux-refinements` has a `research_codebase.md` and design for the
  application form pages (`ApplicationForm.jsx`, `styles-application.css`); it touches
  `course_applications` page chrome, which this spec's templates also touch. Not read in detail.
- `downstream_bugs_oct_29` entries touching form code: `zero-page-form-blocks-course-completion`,
  `leave-and-save-discards-the-current-page`, `profile-form-allows-a-blank-required-name`. The first is
  directly relevant: a form with no applicable pages is the same edge case as a form with zero pages
  (`course_applications/views.py` L712 `_resume_url`, `form_fill_page`).

## 10. Things that make the three named rules hard

Earlier-page rule:
- Page order is the importer's sorted file-path order, string-sorted (see section 5). The same order must
  be used offline by `claude_plugins/fls-content/validate/`.
- Pages are only identified by file; `FormPage.slug` is derived from the title, so the condition's *source*
  question is addressable (by new slug) but "which page is it on" has to be recovered from the form tree.
  The existing cross-file pass (`validate.py` L968-981) is the right shape because it sees all parsed items
  at once, but it validates files, not the DB, so it cannot lean on `FormQuestion.form_page`.
- Same-page triggers are the "Other, please specify" survey case; the demo content's own
  `value: other` question is an instance of it.

Per-sitting `max_score`:
- `score_category_value_sum` has no notion of a sitting's questions; it loops the form. It also ignores
  non-choice question types entirely, and `max_value` is "highest numeric option", so "reached questions
  only" changes both numerator and denominator for the affected subtree only.
- The only readers of a category-tree `scores` are per-sitting templates (section 4), so per-sitting
  `max_score` needs no reader changes there; `reports/` does not read a category tree at all.
- `complete()` calls `score()` with no knowledge of the path; the path has to exist (or be computable
  from `answers` at that moment) before `score()` runs, and be persisted in the same transaction as the
  deletion of off-path rows, since scoring reads `answers` and deletion removes them.
- `submit_on_exit` forms can complete on a partial sitting (`form_submit_and_exit`), so the path at
  completion is "reached so far" and unreached pages that are not on the path become skipped vs
  not-yet-reached; that distinction is exactly the one the idea notes for `resume_page_number`.

Deleting off-path answers on submit:
- `QuestionAnswerFile` cascade + `post_delete` receiver removes stored objects (section 1). Deletion on
  submit is destructive for file questions in a way it is not for text.
- No transaction wraps `complete()` today (it sets `completed_time`, calls `score()` which `save()`s,
  then saves again, then sends `form_attempt_completed`). A delete-then-score-then-freeze sequence has no
  atomic boundary now; the signal receivers (`learner_progress`, `webhooks`) run after `complete()`.
- Any non-`complete()` writer (qa_helpers, admin, the fixtures in `learner_progress/factories.py` L81 that
  seed `form_progress__scores`) leaves off-path rows or no path record.
- A reader that skips `complete()` filtering and reads stored answers directly will see off-path rows
  while the sitting is in progress: `answered_counts`, `existing_answers_dict` (L340),
  `answer_groups`, `exports.answer_columns`, `course_applications/resources._answers`. The idea's "every
  reader filters by the live path" enumerates these implicitly; this is the concrete list.
- `QuestionAnswer.question` is `PROTECT` and answers are unique per (sitting, question), so a stored
  `selected_options` M2M row for an off-path question stays attached to its `QuestionOption`s until the
  answer row is deleted.

## Sources

Codebase only; no web sources. Files read: `form_engine/{models,schema,paging,page_flow,queries,views,
exports,receivers}.py`, `content_base/{models,schema}.py`, `content_engine/{validate.py,
management/commands/content_save.py}`, `learner_interface/views.py` (L1770-2060, L2248-2345),
`course_applications/{views,resources}.py` and its `form_page.html` / `check_your_answers.html`,
`form_engine/templates/form_engine/{question.html,partials/page_children.html}`,
`reports/{gather,indexes}.py`, `claude_plugins/fls-content/{skills/content-types/resources/form-files.md,
validate/schema.py}`, `docs/app_structure.md`, `spec_dd/2. in progress/compliance-form-randomization/{idea,
todo}.md`, `spec_dd/1. next/{roadmap.md,multi-step-course-applications/idea.md}`,
`demo_content/functionality_demo_application_form/`.

status: ok
reason: Mapped the form_engine/runner/importer/reports/plugin surface with file:line refs, corrected the reports claim (quiz-only), and listed overlaps with compliance-form-randomization and implementation hazards.
