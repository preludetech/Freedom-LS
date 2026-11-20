# Research: codebase touch points for `sacaa-compliance-2-shuffle`

Paths are relative to the worktree root. Line numbers are from this branch (after spec 1 landed).
Decisions taken in `answers.md` are assumed: a `group: <name>` string on content blocks and
questions, groups allowed with within-page shuffle off, no nested groups, form-level knobs only,
no page lock.

## 0. Headline findings

1. Spec 1 already did most of the read side. `SittingPath` follows served order for pages,
   children and options (`conditions.py`), the three option templates already render from
   `{% question_options %}` which calls `path.options_of(question)`
   (`form_engine/templatetags/form_engine_tags.py:63-74`), and scoring, results and reports read
   the served paper. The shuffle is therefore, in the main, a change to `build_served_paper` plus
   the authoring chain (schema, model fields, validator, `content_save`, docs, demo content).
2. Real gaps that shuffling exposes: `FormQuestion.question_number()` (authored order) is still
   used in learner-facing review labels, and `page_position` / `question_positions` need checking
   against shuffled pages (section 6 and 7).
3. `ServedPaper` has no group information and no per-child type, which the pools spec will want
   (section 10).

## 1. Content schema (`freedom_ls/form_engine/schema.py`)

- `Form` (l.58-113): `strategy`, `quiz_show_incorrect`, `quiz_pass_percentage`, `sections`,
  `submit_on_exit`. The `@model_validator validate_quiz_fields` (l.90-113) is the existing pattern
  for "only valid when strategy is QUIZ"; the errors read `... should only be set when strategy is
  QUIZ (in {self.file_path})`. New knobs `shuffle_pages`, `shuffle_questions`, `shuffle_options`
  (bool, default False) belong here, and the "knob on non-QUIZ" error can be raised in this same
  validator. Because the defaults are `False`, a non-QUIZ check must test `True`, not "is not
  None" (unlike the two quiz fields, which default to `None`).
- `QuestionOption` (l.180-191) has `model_config = ConfigDict(extra="forbid")`, fields `text`,
  `value`, `uuid`, `correct`. A `locked: bool | None` goes beside `correct`. Unknown keys are
  rejected, so nothing works until it is added.
- `FormContent` (l.194-196) and `FormQuestion` (l.199-301) both inherit `BaseBaseContentModel`;
  both have `when`. Add `group: str | None` to both. `FormPage` (l.168-177) gets none (answers.md:
  no page lock, no group on pages).
- `FormPage.derive_content_type` (l.173-177) distinguishes sections by a `content` or `question`
  key, so adding `group` does not disturb parsing.
- `freedom_ls/content_engine/schema.py` does not hold form types; the form schema is
  `form_engine/schema.py` (imported as `form_schema` in `content_save.py`). Nothing needs
  changing in `content_engine/schema.py` for this spec unless the content-type registry lists form
  fields (it does not).

## 2. Django models (`freedom_ls/form_engine/models.py`)

- `Form` l.54-90: add three `BooleanField(default=False)`. Pattern: `submit_on_exit` l.74-80
  (default False, help text).
- `FormPage` l.93-129 (`order`; `children()` l.112-123 merges `text_items` and `questions` and
  sorts by `order`). Unchanged.
- `FormContent` l.132-157 and `FormQuestion` l.160-257: add `group = CharField(max_length=...,
  blank=True, default="")`. `slug` (l.170-177) is the pattern for a blank-string optional author
  key.
- `QuestionOption` l.260-275: add `locked = BooleanField(default=False)`. `correct` is
  `null=True`, but `locked` has no reason to be tri-state.
- `FormProgress.served_paper` JSONField l.319-326 (null until written). `question_number()` l.236
  walks `form.pages.all()` and `page.questions.all()` in authored order: see section 7.
- A new `form_engine` migration is needed (latest is `0010_formprogress_served_paper.py`); run
  `makemigrations`, never edit an existing one. Existing rows take the opt-out defaults.
- Admin: `form_engine/admin.py` shows `served_paper` read-only at l.359 and l.378 (FormProgress).
  The Form/FormQuestion/QuestionOption admins should be checked for explicit `fields` /
  `fieldsets` lists that need the new fields.
- `ServedPaper` TypedDict is in `conditions.py:47-52` (see section 5), not in models.

## 3. Validator (`freedom_ls/content_engine/validate.py`)

- `validate()` l.1218 runs cross-file passes at l.1269-1282: `validate_category_references`,
  `validate_widget_references`, `validate_children_lists`, `validate_due_date_placements`,
  `validate_form_conditions`, `validate_question_sections`. The shuffle checks are a new pass in
  the same style, appended to that list.
- `validate_form_conditions` l.1135-1180 is the model to copy: it builds `forms` keyed by
  `item.file_path.parent`, `sections_by_file` for FormPage/FormContent/FormQuestion items, and
  `page_files = sorted(f for f in sections_by_file if f.parent == form_dir)` (page order is sorted
  paths, so `10. x` sorts before `2. y`; the same helper logic is needed for "spans pages").
  Errors go through `_condition_error` (l.1032-1048, header `Invalid condition in ...`, a
  `Field:` line, `Problem:`, a fix line) and `_target_label` (l.1051-1056). A shuffle pass should
  either reuse that block shape under a different header or generalise it (do not copy-paste, per
  CLAUDE.md).
- It already rejects `when` on a QUIZ form (l.1162-1173), so "no condition and shuffle conflict"
  holds for QUIZ. Note the `continue` at l.1173 skips slug checks for QUIZ.
- Rules the new pass must cover (idea "What is settled"): knob on non-QUIZ; `locked` on an option
  of a form with `shuffle_options` off; `group` on a non-QUIZ form; group non-contiguous within a
  page; group spanning pages; nested groups (answers.md says nested is an error, but a
  string-key model has no syntax for nesting, so "nested" can only mean a name reappearing after
  a different name interrupted it, which is the same as non-contiguous; decide whether a
  separate nested error exists at all); an empty/whitespace group name; a group name used by only
  one member (probably allowed, a lone member is a trivial atom); locked on a question with no
  options.
- Locked-option subtleties to validate: at most all-but-one locked (everything locked is a no-op
  but harmless); `locked` on `correct` options is fine.
- `@claude`/TODO comments: none found in the touched validator region that need preserving.

## 4. `content_save` (`freedom_ls/content_engine/management/commands/content_save.py`)

- `save_with_uuid` l.262-350 dumps the pydantic item with `exclude_none=True` and then raises
  `ValueError` if any dumped field is not a model field (l.316-330). So every new schema field
  must have a same-named model field, or be added to `exclude_fields`. This is the "content_save
  writes the new fields" requirement: mostly automatic once model fields match.
- `save_form` is called at l.1141 (not read; it is the Form equivalent and follows the same
  path). `False` bools survive `exclude_none`, so `shuffle_*: false` writes through, and removing
  a key from a file resets via `update_or_create(defaults=fields)` only when the field is
  present. A key that is absent from the file is not in `fields` at all, so removing
  `shuffle_pages: true` from the file would leave the stored True. Same trap exists today for
  `submit_on_exit`? It defaults to `False` in pydantic, so the dump includes it and a removal does
  reset. New knobs with pydantic default `False` behave the same way; use `bool = False` (not
  `bool | None`) for the form knobs.
- `save_form_content` l.728-747 and `save_form_question` l.750-798: `group` is written as a
  plain field. For `FormQuestion` the code passes `slug=item.slug or ""` explicitly (l.773)
  because `None` is dropped by `exclude_none`: an absent `group:` would leave a stale stored
  group when an author deletes the key. Pass `group=item.group or ""` explicitly in both
  `save_form_content` and `save_form_question`, as is done for slug and `condition_option`
  (comment at l.712-714).
- Options: `save_form_question` l.776-796 saves each option through `save_with_uuid(QuestionOption,
  option, ...)` with `order=idx`. `locked` is written if present; since schema `locked` is
  `bool | None` it would be dropped when `None`, leaving a stale `locked=True` if removed. Make the
  schema field `bool = False` (as for `submit_on_exit`) so removal resets, or pass it explicitly.
- Option `order` is the authored position (`idx`): "locked keeps its absolute authored position"
  maps directly onto `QuestionOption.order`.
- Questions/content order within a page is `content_order = enumerate(file_content_items)`
  (l.1192), shared across FormContent and FormQuestion, which is what makes contiguity checkable
  by `order`.

## 5. Served paper build and read paths

- `freedom_ls/form_engine/served_paper.py`
  - `build_served_paper(form)` l.19-33: the single change point (the spec 1 spec says "the one
    place spec 2 will change"). Today: pages from `form.pages.all()`, children from
    `page.children()`, options from `child.options.all()`, `seed = secrets.randbits(63)` stamped
    as "provenance only". Shuffle goes here, driven by `form.shuffle_pages/_questions/_options`
    and `QuestionOption.locked` and `.order`, `child.group`.
  - `served_child_ids` l.36-42, used by `reports/indexes.py:436`.
  - `ensure_served_paper` l.45-60: QUIZ-only, null-only, conditional update then re-read. Called
    from `learner_interface/views.py` l.1932 (`form_start`), l.2068 (`form_fill_page`), l.2445
    (submit-and-exit), `course_applications/views.py` l.726/752/833 and `FormProgress.complete()`
    (`models.py:464-467`).
  - Seed: spec 1 left the `seed` as provenance. Idea says "One seed per attempt". Practical
    choice: draw the seed, then build a `random.Random(seed)` (or `secrets.SystemRandom` if
    unreproducibility is wanted; reproducibility from seed is useful in tests and a plus for
    audit but the spec 1 decision says the order is stored explicitly and "nothing rebuilds an
    order from the seed"). `random.Random(seed).shuffle` is cheap and testable; keep the stored
    lists as the source of truth.
  - `factories.py:122-139` `served_paper_of(pages, options)` builds a paper by hand for tests;
    it will need no change unless the `ServedPaper` shape grows required keys (see section 10).
- `freedom_ls/form_engine/conditions.py`
  - `ServedPage` / `ServedPaper` TypedDicts l.42-52: `seed`, `pages[{id, children}]`,
    `options{question_id: [option_id]}`. Adding optional keys keeps old papers valid
    (`served_path` indexes `served_paper["options"]` and `["pages"]` only).
  - `SERVED_TREE_LOOKUPS` l.39 prefetches `pages__questions__options`. Options use the model's
    `ordering = ["order"]`, so `child.options.all()` is authored order for the shuffler's input,
    and group/lock lookups on children and options need no extra prefetch.
  - `served_path` l.286-326: walks the paper, so shuffled order comes out for free. A question
    moved to another page of the form keeps its served page (l.315-325). Questions whose served
    options are all gone fall back to live authored order (l.325). These already satisfy "reload,
    resume and back-navigation show the same order".
  - `SittingPath.options_of` l.174-178: returns served order or `question.options.all()`.
  - Position math: `_numbered` and `_page_positions` are built from `children_by_page` insertion
    order (l.77-96), so shuffled pages get served positions. `_question_positions` comes from
    `self.questions()` = page order then child order, so it is the served number. Good.
  - Hazards with a shuffled page order: `_first_number_above(number)` l.144-146 returns the first
    page *in served order* whose authored number is greater, which for a shuffled paper is not the
    "next authored page". Spec 1 documented this as intended ("A number that is not on the path
    lands on the first served page whose authored number is greater, else on the last served
    page"). It only fires for off-path numbers; on a QUIZ paper every page is on the path unless
    an author deletes a page mid-attempt. Low risk, but worth one test with a shuffled paper.
    `reached_position` l.163-172 has the same dependency.
  - `compute_path` / `_condition_holds` untouched (collision note in the roadmap with
    `form-engine-branch-logic-2-and-conditions`).
  - `frozen_path` / `full_path` (l.338-358) serve completed sittings with no served paper and the
    educator preview; they stay authored order, which satisfies "educator preview and answer-key
    lists keep their authored order".

## 6. Page flow, paging, learner views

- `page_flow.py`: `page_at` l.65-75 maps URL number to `path.all_pages[page_number-1]` (authored
  index); URLs therefore stay authored and a shuffled paper only changes what comes next.
  `page_context` l.158-203 supplies `next_page_url`, `previous_page_url` from
  `path.next_page_number` / `previous_page_number` (served order), `page_position` and
  `total_pages` (served), `page_children = current.path.children_of(page)` (served child order),
  `question_positions` (served numbers), `sitting_path` (used by `{% question_options %}`).
  Nothing to change here for shuffling.
- URL leak: URLs carry authored page numbers, so a shuffled quiz exposes the authored page index
  in the URL (`/form/.../page/3`), and a learner can type a number to jump to a page out of
  served order. `form_fill_page` (`learner_interface/views.py:2068-2073`) lets any on-path number
  render; page-jump nav gating is by served position (`paging.build_page_links` l.90-111,
  `page_accessibility_limit`). The idea and spec 1 accepted authored URLs. Decide whether to
  note this in the authoring docs ("shuffle is not proctoring").
- `paging.py`: `_question_numbers` l.169-171 uses `path.question_positions()`, so the
  "Question N needs an answer" messages already use served numbers. `unanswered_required_in_form`,
  `first_page_number_with_unanswered_required`, `resume_page_number` and `record_page_reached`
  (`models.py:364-376`) were made position-aware in spec 1.
- `learner_interface/views.py` `form_fill_page` flow: POST accepted -> `path.next_page_number`
  (l.2082), final page -> `unanswered_required_in_form`, `form_progress.complete()`.
  `course_form_complete` l.2123+ builds `sitting_path(form_progress)` for quiz sittings with a
  served paper (l.2168-2173).
- `course_applications/views.py`: uses `sitting_path`, `current_path`, `ensure_served_paper`; it
  serves UNSCORED forms, so it is unaffected (the shuffle is QUIZ only).

## 7. Question numbering, results and review

- Served numbering on the live page: `question.html:11-13` prints `{{ position }}.` from
  `question_positions|get_dict_item:question.id`, i.e. served numbers. Same file also uses
  `question.question_number` (authored) only in `data-testid` attributes
  (`question-number-{{ question.question_number }}` l.13, `required-indicator-...` l.19). That is
  two ORM walks per question per render but is not user-visible; it will keep reporting the
  authored number as the test id, which is arguably what tests want. Do not change without
  checking Playwright tests under `learner_interface/tests` that select by those ids.
- Leftover that spec 1 explicitly deferred ("Results page incorrect-answer labels stay as they are
  (`question.question_number`). They only differ from served positions once
  `sacaa-compliance-2-shuffle` lands.", spec 1 `1. spec.md` l.189-190):
  `learner_interface/templates/learner_interface/course_form_complete.html:105`
  `Question {{ item.question.question_number }}`. With shuffling this label shows the authored
  number while the learner saw a different one. This spec should fix it: pass served positions
  (`path.question_positions()`) into the results context, or add a `position` to each item built
  by `FormProgress.get_incorrect_quiz_answers` (`models.py:683-740`, already given `path`).
- `models.py:236-251` `question_number()` is also used by
  `educator_interface/templates/.../cohort_report_body_region.html:134` (`Q{{ ...question_number
  }}`) and by `reports` (`reports/indexes.py:539-588` `build_question_index` numbers per form with
  `order_by("form_page__order", "order")`; reports `gather.py:485,534` use
  `questions.number_by_id`). Those are authored numbers across many attempts and stay authored
  (a report cannot use one number for a question served at a different position per learner). The
  per-attempt served number is the job of `sacaa-compliance-4-attempt-review`. Worth stating in
  the spec that cohort report Q-numbers are authored.
- Scoring: `models.py` `_quiz_questions` l.611-629 uses `path.questions()` when a served paper
  exists; `compute_quiz_scores` l.631-657 and `get_incorrect_quiz_answers` l.683-740 read
  `question.options.all()` for correctness (unordered logic, order-insensitive); the incorrect
  list's `correct_options` uses `question.options.filter(correct=True)` (authored order) and
  `learner_selected` uses `selected_options.all()` (model ordering, i.e. authored). On the review
  page those option lists appear in authored order rather than served order: not wrong, but worth
  a decision (they list correct answers, not an options group, so authored is acceptable).
- Shuffle does not change score or `max_score` (every served paper has the same question set).
- Results outdated-score check `learner_interface/views.py:2184-2200` uses
  `path.has_missing_served_items`; unaffected by order.
- `exports.py:135-152` `sitting_path` for the answer export; `exports.py:152` sorts selected
  options by `option.order` (authored). Out of scope (spec 4 owns the served order in the export).
- `form_engine/admin.py:482` answer groups, `_answers.html:20` show authored order. Out of scope.

## 8. Option templates

`form_engine/templates/form_engine/inputs/`:
- `multiple_choice.html`, `checkboxes.html`, `dropdown.html` each begin with `{% load ...
  form_engine_tags %}` and `{% question_options as options %}`, then `{% for option in options %}`.
  They already render the served order and fall back to `question.options.all()` when the context
  has no `sitting_path` (educator preview). No DOM-order/CSS-order problem: no CSS reordering is
  used; options are in a plain `for` loop. So accessibility requirement (DOM order = visual
  order) holds already and needs a test, not a change.
- Answer key (`show_answer_key`): set only by `educator_interface/views.py:2312` (preview
  context with no `sitting_path`), so authored order in the key list (`dropdown.html:16` iterates
  `options`, same variable).
- `existing_answers` checks use `option in answer.selected_options.all`; independent of order.
- The `{% question_options %}` tag (`form_engine_tags.py:63-74`) is the single seam; no template
  edit is required.
- Educator preview: `_form_preview_context` (`educator_interface/views.py:2273-2313`) uses
  `full_path(form)`, passes no `sitting_path`, so shuffle never applies. Good, but note that an
  educator previewing a shuffled quiz sees one page with a note-free authored order. A one-line
  hint ("learners see this shuffled") is optional UI scope, not requested.

## 9. Demo content and author plugin docs

- Demo quizzes: `demo_content/functionality_demo_end_with_quiz/3. quiz/` (`form.md`, `1. page.yaml`,
  `2. another page.yaml`) and `5. quiz/` (same shape); `functionality_demo_course_parts/02. Core
  Concepts/03. knowledge-check/` (`form.md`, `1. page.yaml`). `3. quiz/form.md` is `QUIZ`,
  `quiz_show_incorrect: true`, `quiz_pass_percentage: 80`, `submit_on_exit: true`, `sections:
  [../2. topic/content.md]`. `3. quiz/1. page.yaml` has the shape needed for the example: three
  multiple_choice questions with a `FORM_CONTENT` block between question 1 and 2 (a picture) and
  uuid keys. Do not edit existing quizzes; add a new quiz directory (or new demo course
  placement) so existing QA and tests keep their authored order. A new demo form needs
  `children:` registration in the course file (see `course-files.md`) or auto-discovery.
  The example needs: three knobs on, one option with `locked: true` ("All of the above" style),
  and one `group:` linking a content block to its questions, spanning two or more pages.
- Author docs: `claude_plugins/fls-content/skills/content-types/resources/form-files.md` is the
  one file that documents form fields. Spots to change:
  - FORM table l.13-28 (add `shuffle_pages`, `shuffle_questions`, `shuffle_options`; note QUIZ only
    and the opt-in default);
  - QUIZ example l.36-44;
  - FORM_QUESTION fields table l.117-132 (add `group`) and options table l.136-141 (add `locked`);
  - FORM_CONTENT table l.277-281 (add `group`);
  - a new section, modelled on "Conditional pages, questions and content (`when`)" l.297-358:
    the rules (contiguous, one page, not nested, locked only with shuffle_options, QUIZ only),
    an example and a "this is not proctoring" note, per the idea.
  - Also check `claude_plugins/fls-content/skills/content-types/SKILL.md` and
    `README.md` for field summaries, and `skills/conventions/SKILL.md`. Note CLAUDE.md: FLS names
    in the generic plugins are forbidden; `fls-content` is the author plugin for FLS content so
    form field docs belong there.
- qa_helpers seeders (`freedom_ls/qa_helpers/management/commands/qa_create_served_paper_scenario.py`,
  spec 1's scenario) create papers by hand; a shuffle scenario may want a sibling command. Many
  seeders read `question.options.order_by("order")`: unaffected.

## 10. Conflicts and hooks: `sacaa-compliance-3-question-pools`, spec 1

- Spec 3 idea (`spec_dd/1. next/sacaa-compliance-3-question-pools/idea.md`) depends on this spec
  for the keep-together group as its "indivisible draw unit" and says "A group is drawn whole or
  not at all". With a string `group` key on each member there is no group row: spec 3 must
  recompute atoms with the same rule (contiguous run with one key). Put the atom-forming logic
  in one function now (for example `page_atoms(children) -> list[list[FormChild]]` in a shared
  module such as `freedom_ls/form_engine/served_paper.py` or a new `freedom_ls/form_engine/groups.py`)
  so spec 3 imports it instead of re-deriving. The validator needs the same contiguity rule on
  parsed schema items; the runtime function works on model instances. Share a rule over a minimal
  protocol (`.group`) to avoid duplicating, or keep two thin adapters over one pure function.
- Spec 3 says "`sacaa-compliance-2-shuffle` already extends the rule [no `when`] to its own
  knobs". QUIZ already bans `when`, so no new code; but be consistent in the validator wording.
- Spec 3 requires "every item on a drawing page carries the same number of questions" and the
  group of one or more questions with content. A content block in a group counts toward atom size
  but not question count; keep the group schema permissive about "stimulus first" (idea says
  "stimulus first, then its questions in authored order" is preserved, which means authored order,
  not enforced stimulus-first).
- Spec 3 will add `draw: N` to `FormPage` and a model field on `FormPage`; both specs change
  `schema.py`, `validate.py` and `content_save.py`, so they run in series (roadmap note). Keep
  migration numbers in order (this spec's migration lands first).
- `ServedPaper` shape: spec 3 will drop questions from `children`. `served_path` already tolerates
  an id absent from `children`. Spec 3 and 4 will want group membership in the paper; adding an
  optional `groups` key here is optional and probably unnecessary because `group` lives on the
  model rows; but the audit story ("what the learner was served") is stronger if the paper
  records the atoms. Decide in the spec; note that `has_missing_served_items` / `served_child_ids`
  use only `pages[].children`.
- Spec 1 hooks left for this spec:
  - `build_served_paper` is "the one place `sacaa-compliance-2-shuffle` will change"
    (`1. spec.md` l.99-101).
  - `seed` is stored but "provenance only" (`served_paper.py:32`).
  - Results incorrect-answer labels use `question_number` and "only differ from served positions
    once `sacaa-compliance-2-shuffle` lands" (`1. spec.md` l.189-190, `course_form_complete.html:105`).
  - Scoring judges answers against live options and stored scores are never rewritten (no change).
  - Educator preview (`full_path`), admin answer groups and form export keep authored order
    (spec 1 out-of-scope, deferred to spec 4).
  - `furthest_page_reached` stores an authored number, translated to served position on compare;
    with shuffled pages this is the path most exercised for the first time (resume,
    `record_page_reached` forward-only by served position, `build_page_links`). Needs a
    shuffled-paper test in `form_engine/tests/test_paging.py` (the spec 1 tests use "injected
    order").
- Existing tests to extend (mirrored paths): `form_engine/tests/test_served_paper.py` (34
  references), `test_conditions.py`, `test_paging.py`, `learner_interface/tests/views/
  test_form_runner.py`, `content_engine` validate/save tests (find by `validate_form_conditions`),
  `form_engine/tests/templatetags/test_form_engine_tags.py` (options order).

## 11. Open points for the spec writer

- Shuffle algorithm details: groups are atoms; ungrouped children are singleton atoms; shuffle
  atoms, flatten. With `shuffle_questions` off, groups still exist but nothing moves. With
  `shuffle_pages` on and questions off, only the page list is permuted.
- Locked options: choose "unlocked options fill the remaining positions in a shuffled order";
  edge cases: all locked, one unlocked (no change), `locked` on a type with no options (reject).
- What counts as an option list for `shuffle_options`: types `multiple_choice`, `checkboxes`,
  `dropdown` have options; other types have none and `options[...]` only holds questions with
  options (`served_paper.py:30-31`).
- A group name that appears on a content block only, with no questions: legal? Idea says a group
  binds a block to questions that depend on it; a lone block group is harmless but pointless.
- Error and warning wording can reuse the `_condition_error` shape (section 3).
- Is the migration a plain `AddField` set (no data migration)? Yes, with defaults.

status: ok
