# Research: codebase (sacaa-compliance-3-question-pools)

Question: what in the existing codebase does the per-page draw touch, reuse or conflict with?
All paths are under the worktree root. Line numbers are as read on branch
`sacaa-compliance-3-question-pools` (after specs 1 and 2 landed).

## 0. Headline

- Specs 1 and 2 left almost every reader on the served paper. A draw is therefore mostly a change
  inside **`build_served_paper`** (omit the undrawn children from `pages[].children` and
  `options`) plus the author-facing plumbing (schema field, model field, migration, validator,
  `content_save`, docs, demo). Scoring, results, navigation, resume, reports and the file-upload
  guard already skip anything the paper does not name.
- The real conflicts are the surfaces that still count or list the **whole form** instead of the
  served paper: the learner start screen question count (`count_form_questions`), the educator
  preview (`full_path`), and a few admin/export readers that are educator-side by design. See
  section 8.
- `sacaa-compliance-2-shuffle` already built the seams the draw reuses: `new_seed`,
  `_scope_rng(seed, scope)`, `shuffle_units`, `_served_children`, the `group` field on schema
  and model, and the validator's `_form_pages` walk. The draw adds one new RNG scope.
- No `when` conflict: `validate_form_conditions` (`content_engine/validate.py:1197-1228`) already
  rejects `when` anywhere in a QUIZ form, and draw is QUIZ-only, so the idea's "no `when` in a
  form that draws" is already guaranteed. No new rule is needed, only a test that a drawing QUIZ
  page with `when` still fails (via the existing message).

## 1. Schema (`freedom_ls/form_engine/schema.py`)

- `FormPage` (line 210-219) is `BaseContentModel` with `extra="forbid"` (`content_base/schema.py:26`
  `BaseBaseContentModel.model_config`). Only field today: `when` (line 213). A `draw:` key in a
  page header fails the schema now, so the new field is a pure addition.
  - Add `draw: int | None = Field(None, ge=1, description=...)`. `ge=1` gives the "N at least 1"
    rule at parse time; "at most the number of items" and the rest need the cross-file validator.
  - A bare `draw:` (YAML null) parses as None, i.e. "no draw", silently. Shuffle's `group` had
    the same shape and added `_check_group`; `sections` added `_reject_bare_sections`
    (line 47-55, applied via `field_validator("sections", mode="before")`). Consider the same
    "bare key is an error" guard for `draw`, and rejecting `bool`/`float` (YAML `draw: true` is
    read as bool and `int` accepts it in pydantic lax mode; `Condition._literal_as_str` line 176
    is the precedent for guarding yaml coercions). Spec decision.
  - Non-QUIZ rejection: the page header has no strategy. It goes in the cross-file validator
    (section 3), like `group` on non-QUIZ forms (`validate_form_shuffle`).
- `Form.validate_quiz_fields` (line 122-155) is form-level and cannot see pages, so do not put
  the draw rule there.
- Bundled copy: `claude_plugins/fls-content/validate/schema.py` mirrors this file (it has
  `_check_group` at line 935 and the shuffle knobs at 987-1026). Re-sync is a documented step
  (`claude_plugins/fls-dev/commands/update_claude_plugin_fls_content.md` lines 36 and 51: re-copy
  and re-apply every patch in the `# Patches applied:` headers of the bundled `schema.py` and
  `validate.py`; `.pre-commit-config.yaml:62` type-checks it; tests in
  `claude_plugins/fls-content/validate/tests/test_validator.py`). The spec must list this as a
  downstream step.

## 2. Models and migration (`freedom_ls/form_engine/models.py`)

- `FormPage` (line 114-150): add `draw = models.PositiveSmallIntegerField(null=True, blank=True,
  help_text=...)`. `null` is the opt-out. (Shuffle used `CharField(blank=True, default="")` for
  `group`; for an integer, null is the natural "no draw".) Help text in the style of
  `Form.shuffle_*` (lines 81-101).
- `FormPage.children()` (line 133-144) returns text items + questions sorted by `order`. It is
  the only way the units are formed (`served_paper._served_children` line 89 and the validator
  mirror it), so a draw uses `shuffle_units(page.children())` unchanged.
- Latest migration is `0013_remove_formprogress_furthest_page_reached.py`
  (`freedom_ls/form_engine/migrations/`); the next is `0014_...`. Note the existing 0011 is the
  shuffle migration (`0011_shuffle.py`), and 0010 is `0010_formprogress_served_paper.py`. The new
  migration is one nullable `AddField`: existing rows null, no backfill, and no callable default
  (same rule spec 1 set for `served_paper`).
- `FormPage` admin (`form_engine/admin.py`): `FormPageAdmin.fieldsets` line 211-228,
  `FormPageInline.fields` line 194. Spec 2 left the shuffle fields out of the admin ("does not
  expose the sibling fields"). Following that, `draw` is not exposed either; decide explicitly.
  Showing it read-only in `FormPageAdmin` is cheap and would let an admin see why a quiz serves N.

## 3. Validator (`freedom_ls/content_engine/validate.py`)

Reuse, do not copy:

- `_form_pages(all_parsed)` (line 1088-1118) returns each `Form` with its page files'
  `_PageSections` (`page: FormPage | None`, `sections` labelled, `.children` property at line
  1077). Pages are in the order `content_save` assigns (sorted file paths). This is exactly what a
  draw check needs: `page.page.draw`, `page.children`, `form.strategy`.
- `_form_error(file_path, target, problem, fix, field, header)` (line 1034-1056) takes a header;
  `_shuffle_error` (line 1231-1241) wraps it with header `"Invalid shuffle setting"`. A draw
  needs its own `_draw_error` wrapper with header e.g. `"Invalid draw"` (do not reuse the
  shuffle header). `target` for a page-level error is `_target_label(page, 0)` ->
  `page "<title>"` (line 1059-1064).
- `validate()` (line 1402-1486) chains cross-file passes at lines 1455-1468 in this order:
  category refs, widget refs, children lists, due dates, `validate_form_conditions`,
  `validate_form_shuffle`, `validate_question_sections`. Add `validate_form_draw` after
  `validate_form_shuffle` (line 1465-1466).
- `validate.py` imports only `content_base.schema`, `content_engine.schema` and
  `form_engine.schema` (lines 22-24), **not Django models**. So the validator cannot import
  `served_paper.shuffle_units` (which imports `.models`, `served_paper.py:19`). Two options for
  forming units on schema items: (a) reuse the validator's own run logic
  (`itertools.groupby` on `child.group`, as `_split_group_errors` does at line 1293-1295), or (b)
  move `shuffle_units` and the `Groupable` protocol to a model-free module and import from both.
  (b) is the cleaner single source of truth, but the bundled standalone validator copy then also
  has to carry the new module. The bundled validator is a Django-free copy, so (a) is the lower
  risk; flag for the spec.
- Rules a new pass needs (all reported in one run, as the sibling passes do):
  1. `draw` on a page of a non-QUIZ form: `draw is only allowed on QUIZ forms (this form is
     <strategy>).` (mirror line 1336-1343 `group` message).
  2. `draw > number of items` on the page, where items = `shuffle_units(page.children)`; fix text
     names the item count. "At least 1" is the schema's `ge=1`.
  3. Mixed page: every item must carry the same number of questions. Compute question count per
     unit (units are `list[(child, label)]`; count `FormQuestion` instances); all must be equal.
     A unit with zero questions fails this too (a group of content only, or a loose ungrouped
     `FormContent`, which the answers file separately rejects as "loose content").
  4. Loose `FormContent` (outside any group) on a drawing page: reject (answers.md: rejected).
     A loose content block is a one-element unit holding no question. A group that is only
     content blocks is also a zero-question unit; one error message covering both ("content on a
     drawing page must sit inside a group with its questions") is enough.
  5. A QUIZ draw with `when`: already caught by `validate_form_conditions`.
- Error ordering note: `validate_form_shuffle` already emits "group split" and cross-page group
  errors; a split group makes the unit computation on that page unreliable (units are formed
  from consecutive runs). The draw pass should skip (or tolerate) pages the shuffle pass already
  reports, to avoid noisy duplicate errors.
- Validator tests live in `freedom_ls/content_engine/tests/test_validate.py` (31 shuffle/served
  hits; the shuffle validator tests are the template) and schema tests in
  `freedom_ls/content_engine/tests/test_schema.py` and `freedom_ls/form_engine/tests/test_schema.py`.

## 4. `content_save` (`freedom_ls/content_engine/management/commands/content_save.py`)

- `save_with_uuid` dumps with `exclude_none=True` (line 298), so a `draw: None` is never written
  and a removed `draw:` key would leave the stored value. `save_form_page` (line 703-725) already
  passes `condition_option=condition_option` explicitly for exactly this reason (comment line
  712-714). Add `draw=item.draw` (None allowed) there. Same idiom as `group=item.group or ""` in
  `save_form_content` (line 748) and `save_form_question` (line 778).
- `save_form_page` is called once per page file from line 1175-1184. No other call site changes.
- The `FormPage.draw` model field must be nullable or the kwarg would write `None` into a NOT NULL
  column; with `null=True` the explicit `draw=item.draw` just works. Test (as spec 2 did):
  removing `draw:` from a file and re-saving resets it.
- Nothing else in `content_save` depends on the draw: the questions of an undrawn pool still get
  saved, with `order` from enumeration (line 1197).

## 5. The draw inside the served paper (`freedom_ls/form_engine/served_paper.py`)

Existing structure (read in full):

- `new_seed()` line 29-31, patched in tests (`factories.seed_serving` patches
  `served_paper_module.new_seed`, `factories.py:148-161`).
- `_scope_rng(seed, scope)` line 34-37: `Random(f"{seed}:{scope}")`, one private generator per
  scope so editing one page leaves other scopes unchanged for the same seed. The draw needs its
  own scope, e.g. `f"draw:{page.id}"`, distinct from `page:{page.id}` (the order shuffle), so
  that turning `shuffle_questions` on/off does not change which items are drawn and vice versa.
  Do not reuse `page:{page.id}`.
- `shuffle_units` line 73-86: takes schema items (`group` None) and model rows (`group` ""), so
  it works on `page.children()` directly. Returns `list[list[T]]`.
- `_served_children(page, form, seed)` line 89-93: `units = shuffle_units(page.children())`,
  shuffled with the page RNG if `form.shuffle_questions`, then flattened. **This is the one place
  to change**: after forming units, if `page.draw` is set, pick `page.draw` of them with the draw
  RNG, then apply the order rule. "Order of drawn items follows the page's shuffle setting;
  with no shuffle they keep authored order" means: select with `rng.sample(range(len(units)), n)`
  then `sorted(...)` indices for the authored order, or select then shuffle if
  `shuffle_questions`. Avoid `rng.sample(units, n)` as the final order when shuffle is off, since
  it returns a random order. (Python's `random.sample` output is not stable across versions; the
  stored lists are the record, as in spec 2.)
- `build_served_paper` line 96-116: builds `pages` and `options` from `_served_children`. Options
  are only emitted for children returned there (line 108-112), so undrawn questions get no
  `options` entry automatically. The seed comment (line 113-115) should add "and the draw".
- Idiom for the unit-size invariant: "every item carries the same number of questions" holds for
  every attempt only if validated at content_save time. The model/DB path (admin edits, hand-built
  forms) can still produce a mixed page. `build_served_paper` should not crash on one; the spec
  should say what it does (draw anyway, `max_score` then varies, or raise). A defensive choice is
  needed since `max_score` comes from `len(path.questions())` (section 7), not from N times size.
- `ServedPaper` / `ServedPage` TypedDicts (`conditions.py:42-52`) need no change: `seed`, `pages`,
  `options`. Undrawn children are simply absent. The draw is not recorded separately; spec 4
  (`attempt-review`) will need to know the page was drawn from a pool and its size, which it can
  read from `FormPage.draw` and the live page children (the same trade-off spec 2 took for groups,
  "Groups are read from the model rows"). Flag: the paper alone does not say "drawn 3 of 8".
- `served_child_ids(served_paper)` line 119-125 is already used by `reports/indexes.py:44,436` and
  returns only served ids. No change.
- `ensure_served_paper` line 128-143 writes once per quiz sitting (conditional update on
  `served_paper__isnull=True`, then re-read). A retake is a new `FormProgress`, so it calls
  `build_served_paper` again with a new `new_seed()`: "a retake draws afresh" needs no new code,
  only a test (two sittings with different patched seeds draw differently).
- Resume/reload/back read the stored paper: `current_path` (`conditions.py:341-347`) and
  `sitting_path` (`conditions.py:373-390`) both call `served_path` when `served_paper` is set.

Edge case to cover in the spec: `served_path` (`conditions.py:298-338`) rebuilds over the live
tree and skips ids that are no longer found, setting `has_missing_served_items` when
`len(children) != len(served_page["children"])`. An undrawn question is not in
`served_page["children"]`, so it is never "missing". An author who **deletes a drawn question**
after the attempt starts gets today's missing-item behaviour (skipped on read, `max_score` shrinks,
outdated notice suppressed). Nothing in `served_path` redraws a replacement (right: "nothing
redraws").

## 6. Scoring, `quiz_percentage`, `passed`, outdated check (`form_engine/models.py`, `learner_interface/views.py`)

Already served-paper based (spec 1), so a drawn paper scores correctly with **no code change**:

- `FormProgress._quiz_questions(path)` (`models.py:673-687`): a sitting with a served paper walks
  `served.questions()`; otherwise the whole form. This is where "scoring reads the served paper"
  already holds.
- `compute_quiz_scores` (`models.py:689-715`): `max_score` = `len` of those questions (one point
  each). So `max_score` equals the drawn question count for every attempt only if every item has
  the same question count (the validator rule). `score_quiz` (717-725) stores it;
  `quiz_percentage` (381-401) and `passed` (403-409) read `scores` and keep their shape.
- `complete()` (`models.py:508-537`): calls `ensure_served_paper(self)` then
  `current_path(self)`, deletes answers off the path (line 525-527), sets `asked =
  path.as_asked()` and `self.score(path)`. Off-path = undrawn, which cannot have answers anyway.
- `get_incorrect_quiz_answers` (`models.py:741-822`): iterates `_quiz_questions(served)` so the
  incorrect list never names an undrawn question. The `number` key comes from
  `served.question_positions()` (line 765, 812-816); positions are over drawn questions only.
  The fallback branch (no paper) calls `question.question_number()` (`models.py:275-290`), which
  walks the whole form; fine for sittings with no paper, since those cannot be drawn.
- Results page (`learner_interface/views.py`): `path` built at 2168-2172 only when the sitting
  has a served paper; `incorrect_answers` at 2173; `stored_score_outdated` at 2184-2198 compares
  `scores` to `compute_quiz_scores(path)` unless `path.has_missing_served_items`. A drawn paper is
  never flagged because both sides read the served set (idea: "a drawn attempt is not flagged").
  Needs a test, not a change. Note the guard `form_progress.served_paper is not None` at line
  2170: a quiz sitting with no paper falls back to the whole form, which is today's behaviour and
  correct for pre-draw sittings.
- Interaction to flag: an author **adds `draw:` to a quiz that already has completed sittings**.
  Their stored `scores` (e.g. 8/8) stay; their served paper is the full old paper, so
  `compute_quiz_scores(path)` still gives 8/8: no stale-notice. A sitting with **no** served paper
  (completed before spec 1) takes the whole-form fallback and the live form now has the same
  questions but a draw key is ignored by that fallback, which is correct (it was served all).

## 7. Learner page flow, start screen, counts

Page-flow readers all take a `SittingPath` and need no change for a draw:

- `form_start` / `form_fill_page` / `form_submit_and_exit`: `ensure_served_paper` at
  `learner_interface/views.py:1932`, `2068`, `2445`; imports at line 66, 87.
- `form_engine/paging.py:192-211` `answered_counts`: `total_question_count =
  len(path.question_ids)` = drawn count; `answered_ids & path.question_ids` excludes undrawn.
  Surfaced in `course_form_page.html:189` and `:403` ("N of M answered"): drawn count, correct.
- `form_engine/queries.py:answer_groups` (line 127-158, admin answer view): walks
  `form_progress.form.pages.all()` and lists **every** page question, marking those off the path
  "not asked" via `_answer_row(question, answers, path)`. Admin/educator side, so the pool is
  visible there by design, and undrawn rows show as not asked. Not a learner leak, but the admin
  answer document will list every pool question for every attempt. Spec 4 owns the per-attempt
  view; note it.
- `form_engine/views.py:37-59` file-upload guard `_owned_file_question`: rejects a question not
  in `sitting_path(form_progress).has_question(...)`, so an undrawn file question cannot be
  uploaded to. Good (and idea says learners never see an undrawn question, including a forged
  upload URL).
- `form_engine/exports.py:116-140` `off_path_question_ids`: `on_page - path.question_ids`; undrawn
  questions are reported "not asked" in the export. Educator side; spec 4 owns the served-order
  export. Also relevant to cohort CSV: columns exist for every pool question.
- `reports/indexes.py:628-642` `build_sat_questions`: pairs a sitting only with
  `served_child_ids_by_attempt_id` (built at 429-437 from `fp.served_paper`). A drawn question
  has a per-question denominator = number of sittings that drew it, which is the right unit
  (cohort distractor/difficulty stats). No change; add a test. Note `reports` `question_ids`
  (line 582) and `questions.by_form` still enumerate the whole form, so a per-question report
  shows pool questions with fewer sittings each. Fine, but call it out.

**Conflict: the start-screen question count.** `learner_interface/views.py:1877`:
`"question_count": count_form_questions(form)` (`form_engine/queries.py:62-68`, a COUNT over
`FormQuestion.objects.filter(form_page__form=form)`), and `page_count: form.pages.count()`
(line 1878). `form_engine/templates/form_engine/partials/form_facts.html` renders
`{{ question_count }} question(s)` and `{{ page_count }} page(s)`; included by
`learner_interface/templates/learner_interface/course_form.html:45`. For a pool form this shows
the pool total (e.g. 20 questions) before the learner starts and the sitting then serves N. This
leaks the pool size (the idea: nothing lets a learner browse the pool; and "A learner never sees
an undrawn question") and is wrong. The fix is a draw-aware count: for each page,
`draw * questions_per_item` if `draw` is set, else the page's question count. It also needs
`count_form_questions` callers adjusted: `learner_interface/views.py:86,1877`; QA helpers
`qa_helpers/management/commands/qa_create_form_count_edge_cases.py:54,186` and
`qa_create_form_attempt_history.py:53,227` (QA seeders, no behaviour change). The same file
`form_start` view must keep the page count right: with no served paper yet, "pages" equals
authored pages (a draw never removes a page).
Also `FormQuestion.question_number()` (`models.py:275-290`) is the authored number used by
`reports/indexes.py` and the question `data-testid` in `question.html:12`; unaffected.

## 8. Educator content preview (question count)

- `educator_interface/panels/course/content_preview.py:317-357` `_form_preview_context`: builds
  `path = full_path(form)` (`conditions.py:366-370`, every page and child, authored order),
  returns `"question_count": len(path.question_positions())` (line 351) and
  `"total_pages": path.page_count` (line 350). `question_positions` is in `question.html:12`
  via `partials/page_children.html`.
- Template: `educator_interface/templates/educator_interface/modal/content_preview.html:39`
  includes `form_engine/partials/form_facts.html with page_count=total_pages`, so the same chip
  text "N questions" is the full pool count. The answers: "Yes, one line" showing pool size and N.
  Implementation shape: add a per-page context entry (the preview renders one page at a time via
  `preview_pages` line 341-348 / `page_position`) such as `"draw": page.draw` and
  `"page_question_count"`, and a one-line note in the template ("Draws 3 of 8 questions per
  attempt"). Also the form-level chip should not claim "20 questions" when an attempt serves
  fewer: use a draw-aware total (same helper as section 7) or show both ("12 in pool, 6 per
  attempt"). Spec to choose. The preview is read-only (`"read_only": True`,
  `"show_answer_key": True`) and shows every pool question by design; that is the educator view
  and not a learner leak.
- Outline: `_form_page_rows` (line 82-95) lists every page; unaffected.

## 9. Demo content and the shuffled demo

- Existing shuffled demo: `demo_content/functionality_demo_shuffled_quiz/` (`course.md`,
  `1. topic/content.md`, `2. quiz/form.md`, `2. quiz/1. the solar system.yaml`, `2. quiz/2. the
  sky.yaml`, `2. quiz/3. mixed questions.yaml`, `images/shuffled-quiz-picture.svg`). `form.md`
  has `shuffle_options/pages/questions: true`, `quiz_pass_percentage: 50`, `sections:
  [../1. topic/content.md]`. `2. the sky.yaml` has a page with one ungrouped question, a content
  block + two questions in group `sky-picture`, and a second ungrouped question. That page is
  **mixed** (a group of 2 questions plus singletons), so it would be rejected as a drawing page.
  **Do not add `draw` to the existing shuffled quiz.** The idea says "The existing demo quizzes are not
  changed" (spec 2) and the draw needs "one pool quiz (two or more subject pages)": a new course,
  e.g. `demo_content/functionality_demo_question_pools/`, with its own `course.md` (no
  `children:` list: auto-discovered, like the shuffled demo), `form.md` (QUIZ, probably no
  shuffle or `shuffle_questions: true` to show ordering), and two or more page files each with
  `draw: N` in the FORM_PAGE section. UUIDs: the demo files carry `uuid:` keys written by
  `content_save`; omit them on new files then run `content_save` to write them (see the
  fls-content doc rule "omit on new files").
- Course category: the shuffled demo uses `categories: [assessment-demo]` (`course.md:2`); reuse.
- Demo tests as template: `freedom_ls/content_engine/tests/demo_content/test_shuffled_quiz.py`
  (marked `fls_internal`, uses `loaded_demo_content`, `validate()` on a copied tree) and
  `freedom_ls/learner_interface/tests/demo_content/test_shuffled_quiz.py` (24 hits; two sittings
  with patched seeds give different orders). The pool demo should have the equivalent: loads
  through `content_save`; two sittings with different patched `new_seed` draw different
  questions; each page draws exactly N; `validate()` passes; a copy with a mixed page or
  `draw > items` fails with the new messages.
- `conftest.py` has a `loaded_demo_content` fixture that loads every demo course: a new demo
  course must keep the whole tree valid (and any test that counts demo courses will change).
- QA seed command for the served-paper scenario exists:
  `freedom_ls/qa_helpers/management/commands/qa_create_served_paper_scenario.py` (27 hits). A
  pool QA scenario would follow its shape if frontend QA needs a seeded sitting.

## 10. fls-content author plugin docs

- `claude_plugins/fls-content/skills/content-types/resources/form-files.md`: the single doc to
  extend. Structure today: FORM frontmatter table (line 13-31, shuffle knobs at 21-23, the
  knob/non-QUIZ sentence at 33), FORM_PAGE frontmatter table (line 92-99, only `when`, `uuid`,
  `title`, `subtitle`, `description`, `content_type`), "Example FORM_PAGE section" (line
  101-110), FORM_QUESTION fields (122-137, `group` at 135), FORM_CONTENT fields (284-289),
  "Conditional pages, questions and content (`when`)" (305-366), "Shuffling a quiz" (370-427),
  `sections` (431-487), "Full page YAML file example" (491-521).
  - Add a `draw` row to the FORM_PAGE table (line ~98), a new "Drawing questions from a page"
    section modelled on "Shuffling a quiz" (validator rules list, authoring guidance: pool
    should be homogeneous in difficulty; content must sit in a group; every item the same
    number of questions; no `when`; QUIZ only; split a stimulus-with-two-questions plus a lone
    question into two pages), and an example with two subject pages. Also add the line to the
    shuffle section's last bullet about groups ("Groups are a no-op when `shuffle_questions` is
    off"): groups are also the draw unit.
  - Spec 2's doc is the model: it states each validator rule and an example pointing at the demo
    course (line 427).
- `claude_plugins/fls-content/skills/content-types/SKILL.md` (line 38 is a long table line) and
  `README.md` summarise content types; check whether they list page fields. `commands/
  validate-content.md` and `commands/init.md` describe the bundled validator.
- Bundled validator copy (see section 1): `claude_plugins/fls-content/validate/schema.py`,
  `validate.py`, `tests/test_validator.py`. Re-sync via `fls-dev:update_claude_plugin_fls_content`
  (`claude_plugins/fls-dev/commands/update_claude_plugin_fls_content.md`).
- `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` has the term table (lines ~32, 129-130,
  141-144); a "draw" / "pool" term (the page is the pool) belongs there if the spec coins one.
- `docs/product/learner-experience.md:15` already carries one line on shuffling ("A quiz can be set to
  shuffle its pages, questions and answer options..."); add a draw sentence there
  (`fls-dev:update_product_docs`). Upgrade notes (`fls-dev:update_upgrade_notes`): one nullable
  `FormPage.draw` field and migration, no backfill, and bundled-validator re-sync.

## 11. Conflicts and risks (collected)

1. **Start-screen count** (`views.py:1877`, `queries.py:62`, `form_facts.html`): shows pool size,
   wrong and a pool leak. Must be draw-aware. Also affects the educator preview chip (section 8).
2. **Validator cannot import `served_paper`** (`validate.py` is Django-free, bundled standalone
   copy): unit formation must be duplicated with `itertools.groupby` or moved to a Django-free
   module. Keep the single semantics of "maximal run of one truthy group = one unit" (matches
   `shuffle_units`, `served_paper.py:73-86`).
3. **Existing shuffled demo page "The sky" is mixed**: do not retrofit; add a new course.
4. **Unit-size invariant is only enforced by the file validator.** A DB/admin edit can make a
   drawn page mixed. `max_score` is `len(path.questions())` per attempt (`models.py:702-703`),
   so a mixed page would give varying `max_score`. Decide: document as authoring-only, or have
   `FormPage.clean()` / `build_served_paper` guard it. `FormQuestion.clean()` (`models.py:244-255`)
   is the precedent for model-level mirror of a schema rule (`question_bounds_error` shared).
5. **`draw` exceeding items after a later edit** (an author deletes questions; `content_save`
   deletes rows no longer in the file, `content_save.py:~1329-1362`): the file validator catches
   it before the save, but an admin deletion does not. `build_served_paper` must not crash on
   `draw > len(units)`: clamp to all units (serve whole page) or fail loudly. Pick one in the spec.
6. **Content_snapshot-style audit gap**: the served paper records only drawn ids; nothing records
   that the page was a pool or its size. `sacaa-compliance-4-attempt-review` can derive it from
   live `FormPage.draw`, which can change later. Acceptable per "stored lists are the record", but
   worth a spec line (spec 2 made the same call for groups, `1. spec.md` Open questions).
7. **`FormQuestion.question_number()` (`models.py:275-290`) and report `question_number`**
   stay authored (whole-form walk). Results labels use served positions (spec 2). A drawn page's
   questions get numbers 1..N across the paper, so they differ from authored numbers; reports
   keep authored. No change, but the educator cohort report (`cohort_report_body_region.html:134`
   `Q{{ question.question_number }}`) will show authored numbers with fewer sittings per Q.
8. **Collisions with other specs** (per roadmap lines 105, 130, 457): the roadmap notes
   `sacaa-compliance-content-versions-and-access-3-question-versions` changes the served paper
   and "collides with `sacaa-compliance-3-question-pools`", and
   `sacaa-complianc-deletion-and-declaration-2-quiz-declaration` changes the form schema, `Form`,
   `FormProgress`, `content_save` and `form_start`. Both rebase onto whichever lands first.
   The shared touch points here: `build_served_paper`, `_served_children`, `save_form_page`,
   `form_start`, the next `form_engine` migration number. `form-engine-branch-logic-2-and-conditions`
   (ready, not started) will change conditions on forms; QUIZ forms still reject `when`.
9. **Seed reuse, scope isolation**: a draw sharing the pages scope (`"pages"`) or the order scope
   (`page:{id}`) would couple the draw to the shuffle knobs (turning `shuffle_questions` off
   would change which questions are drawn for the same seed). Use a separate `draw:{page.id}`
   scope. Include in the tests: toggling `shuffle_questions`/`shuffle_pages` on or off, or
   editing another page, leaves the drawn set unchanged for the same seed.
10. **Tests that need touching**: `freedom_ls/form_engine/tests/test_served_paper.py` (130 hits) is the
    template for draw tests; `freedom_ls/form_engine/factories.py` has `served_paper_of` (125)
    and `seed_serving` (148) helpers for building a paper with injected order/seed.
    `freedom_ls/learner_interface/tests/views/test_form_runner.py` (197 hits) covers the learner
    flow and the existing outdated-score tests (must pass unchanged); a draw flow test belongs
    there. `freedom_ls/educator_interface/tests/test_learner_section.py`/`panels` hold the content
    preview tests (`content_preview` context). `freedom_ls/reports/tests/test_indexes.py` (7
    served hits) for the sitting/served pairing.

## 12. Change list (where a change is needed)

| Area | File and symbol | Change |
| --- | --- | --- |
| Schema | `form_engine/schema.py` `FormPage` (210-219) | add `draw: int \| None`, `ge=1`, guards for bare key/bool |
| Model + migration | `form_engine/models.py` `FormPage` (114-150); new `migrations/0014_*.py` | nullable `draw` field, `AddField` only |
| Validator | `content_engine/validate.py` new `validate_form_draw`, `_draw_error`; call in `validate()` after line 1466 | non-QUIZ, N > items, mixed sizes, loose/contentless unit |
| content_save | `content_engine/management/commands/content_save.py` `save_form_page` (703-725) | pass `draw=item.draw` |
| Draw | `form_engine/served_paper.py` `_served_children` (89-93), `build_served_paper` (96-116) | select N units with `draw:{page.id}` RNG, then order per shuffle |
| Counts | `learner_interface/views.py:1877`; `form_engine/queries.py:62` | draw-aware `question_count` for the start screen |
| Preview | `educator_interface/panels/course/content_preview.py:317-357`; `modal/content_preview.html:39`; `partials/form_facts.html` | one-line pool/N note; draw-aware count |
| Admin | `form_engine/admin.py` `FormPageAdmin` (200-228) | optional read-only `draw` |
| Demo | new `demo_content/functionality_demo_question_pools/` (+ demo tests mirroring the shuffled ones) | two or more subject pages with `draw` |
| Docs | `claude_plugins/fls-content/.../form-files.md` (92-99, new section after 427); `docs/product/learner-experience.md:15`; domain glossary if a term is coined; upgrade notes | author guidance |
| Bundled validator | `claude_plugins/fls-content/validate/{schema,validate}.py` + tests | re-sync with patches |
| No change needed | `models.py` `_quiz_questions`, `compute_quiz_scores`, `quiz_percentage`, `passed`, `get_incorrect_quiz_answers`, `complete`; `conditions.py` `served_path`/`current_path`/`sitting_path`; `paging.py` counts; `views.py` results page; `form_engine/views.py` upload guard; `reports/indexes.py` | read the served paper already; add tests only |

status: ok
