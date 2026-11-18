# Prior art: linking questions to course sections

Scope: what this repo already did for cross-file YAML references, author paths and unplaced forms, and what outside systems do. Findings that would change the spec only. Prior research files in `spec_dd/1. next/` are not repeated.

## 1. In this repo: no earlier attempt at question-to-content links

- No spec in `spec_dd/` (all stages, including `3. done/` and the paused `compliance-form-randomization`) links a question or form to a `CoursePart` or `Topic`. This spec is the first.
- `compliance-form-randomization` (`spec_dd/0. paused/`) discusses question banks only as outside patterns (`research_question_bank_patterns.md`). It never touched `tags`/`meta` on questions. Its Moodle/Canvas/QTI finding: the bank is "a separate content namespace" the quiz references by identifier. FLS has no bank namespace today (`research_question_bank_patterns.md` line 180). The answers settle this spec on real links from a form file, so a bank form is just an unplaced form.

## 2. The precedent to copy: `application_form` (the only cross-file reference from a course to a FORM)

Added by the course-applications specs (`spec_dd/3. done/2026-10-12_18:37_ananomous-course-applications`, `2026-10-24_06:02_anon-application-improvements`). Mechanism, from code:

- Author writes a path relative to the declaring file: `application_form: ../functionality_demo_application_form/form.md` in `access_config`.
- Type/shape check at parse time in the backend (`course_applications/backends.py` `validate_course_config`): non-empty string, and only valid with `application_gated`.
- Resolution in a separate pass in `content_save.save_content_to_db`, after every Form is saved: `resolve_author_path(schema_item.file_path, author_path)` then `content_by_path.get(...)`; raises `ValueError("... names application_form {path}, which is not a loaded FORM")` if missing or the wrong model type. The same function `resolve_author_path` and map `content_by_path` (keys from `content_key`, i.e. `Path.resolve()`) resolve `children:`.
- Reconciling on reload: the binding writes `None` when the key is absent, because `save_with_uuid`'s `update_or_create` drops None keys and would otherwise leave the old value. A comment in the loader says this explicitly. Tests: `test_content_save.py` (binds, unbinds when the line is deleted, a path to a Topic fails the load).
- Lesson for this spec: a link is written in a binding pass after all targets are saved, and removal of the authoring key must be an explicit clear/replace. The same trap hits questions: dropping `sections:` from a question must clear the stored links. `collection.categories.set(...)` in the same function is the existing "replace, not merge" idiom for a many-to-many (the loader comment calls it "the one place a load takes something away"). Multi-section links (answers: several) fit that idiom, not `update_or_create`.
- Order hazard the spec must keep: Topics, Activities, Courses and CourseParts are all saved (into `content_by_path`) before Forms and form pages (loader lines 1014-1132), so a question's targets already exist when its form is saved. No ordering change is needed for resolution, but `save_form_question` currently has only `form_page`, `order`, `condition_option` and `slug` to carry things, so the resolved targets must be passed in or bound in a later pass like `application_form`.

## 3. Unplaced forms already load (settles open item 5 / research "fact b")

- `application_form` forms sit in a sibling directory and are placed in no collection (the demo gated course points at `../functionality_demo_application_form/form.md`; `content_engine/tests/demo_content/test_application_form.py` asserts it loads, with pages, and question types). The loader builds `forms_by_dir` from FORM files regardless of placement, and pages are attached by directory (`pages_by_form`), never through `ContentCollectionItem`.
- `validate_children_lists` / `validate_due_date_placements` only look at what a course or part names; nothing requires a FORM to be named by a collection. So "a form placed nowhere may not load" is false at the loader. What is untested is a quiz-type (scored) unplaced form with questions; the application form is `UNSCORED`. Spec should add a test for an unplaced `QUIZ` form carrying section links rather than make a loader change.
- One catch: `auto_discovered_children` adopts every content file beside a collection file when `children:` is absent, so an unplaced form kept in a course directory with no `children:` list gets placed by accident. Bank forms should live in a sibling directory or under a `_`/`.`-prefixed directory (skipped by `is_skipped_path`, which also stops the form loading at all, so `_` is wrong for a bank form; use a sibling directory like the application form).

## 4. Error and validator conventions to follow

- Load-time errors for references are a single `ValueError` naming file and path (`"Collection '...' names a child at {path} that was not loaded"`), raised inside the atomic load so nothing is written. Parse-time structural errors are collected and joined in `validate.py` via `_reference_error` / `_condition_error` with a fixed block layout ("Field / Problem / fix"). A missing-section error should be collected in the early validation pass (before any write, like `validate_children_lists`) rather than only in the binding pass, so one run reports every broken link. The existing `application_form` check only raises one error at binding time; `children:` errors are batched. The batched style is the better precedent here and is what the answer ("naming the question and the missing target") implies.
- Type-check the target: `application_form` rejects a path that resolves to a Topic (`test_an_application_form_path_pointing_at_a_topic_fails_the_load`). The equivalent here: accept only `CoursePart` or `Topic`, reject Course, Activity, Form, Article; the due-date code has the same idea with `_DUE_DATE_CHILD_TYPES`.
- Schema models forbid extra keys (idea), so `sections` must be added to the question schema and to the Form schema for the form-level default. The same applies to the `fls-content` validator and docs the idea asks about.

## 5. Dropped questions and stale rows (open item 6, "fact a")

- `_resolve_condition` carries a comment that "questions dropped from the YAML and options re-created without a uuid leave stale rows". That confirms `content_save` does not delete dropped questions or options; they stay as database rows. So a link table keyed to questions would keep links from questions the author removed. The spec should state this: stale questions retain links, and any reader of "questions for section X" must be aware (or filter to questions seen in the latest load, which today is not recorded).
- The only deletion in the loader is `CoursePartChildDueDate` rows (and M2M `categories.set`). No precedent for deleting questions; answer rows PROTECT them, so adding deletion is out of this spec.
- A link table deleted by CASCADE when a `CoursePart` or `Topic` row is deleted is consistent with how nothing in `content_save` deletes content; deletion happens in the admin only. Use CASCADE on the link to the section; the missing-target load error covers the authoring side.

## 6. Notable outside attempts (already researched; summary and sources)

From `spec_dd/0. paused/compliance-form-randomization/research_question_bank_patterns.md` and this effort's `research_learner_features.md`:

- Moodle: a question belongs to a bank category (`question_bank_entries.questioncategoryid`), plus tags for cross-cutting filters. https://docs.moodle.org/502/en/Question_banks
- Canvas: a quiz question group links to a bank by name and draws N. https://community.instructure.com (see paused research for exact pages)
- QTI 2.x / 3: a bank is an `assessmentSection` of `assessmentItemRef` URI references; items are separate files, referenced by identifier or URI. Reference by path-like identifier is the standard and survives item reuse across tests.
- Common principle (paused research line 176): the quiz references the bank by identifier, not by embedding questions. Here the direction is reversed (the question names the content), but the same lesson applies: identifier-based references plus load-time resolution, not free-text tags. Moodle's tag-only approach has no existence check, which is why the answers rejected `tags`.
- Failure mode seen outside: Storyline in some LMSs re-draws on resume, corrupting continuity (paused research line 49). Not relevant to a static link, but relevant to the later pretest spec.

## 7. What would change the spec

1. Bank-form support needs no loader change; the spec should state that and carry a test, with the "keep bank forms out of an auto-discovered course directory" authoring rule in the docs.
2. Use the `application_form` shape (author path, `resolve_author_path`, `content_by_path`, type check, explicit clear on removal), but use the batched early-validation style for the missing-target error, and a many-to-many "replace" for multi-section links.
3. State explicitly that dropping a question from a file leaves its row and its links in place.
4. Add the key to the question and form schemas (extra keys are forbidden) and to the `fls-content` validator and docs.
5. A form-level default is resolved against the form file's location; a per-question override against the same file (questions live in the page file). Spec should say which file the path is relative to. The only precedent is relative to the declaring file, so a page file's relative path may differ from the `form.md`'s: pick one anchor or require paths relative to the declaring file and document it.

status: ok
