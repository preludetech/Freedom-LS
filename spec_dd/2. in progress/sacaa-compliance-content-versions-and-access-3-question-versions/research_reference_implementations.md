# Research: reference implementations of question versioning (concrete code and data model)

Topic: `reference_implementations`. Question: how do reference implementations solve "a past attempt shows and scores the version answered"?

Does not repeat `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_question_versioning_prior_art.md` (product behaviour of Moodle, Canvas, Open edX, QTI, Questionmark). This note goes to schema and code level where sources could be read.

Labels: (a) read in a fetched source this session; (b) search snippet or secondary claim; (c) my background knowledge or inference, NOT verified here. Primary Moodle schema pages and Canvas/TAO source were not fetchable (404s, truncation), so most Moodle column-level detail is (c). Treat it as a lead to confirm in the Moodle source before the spec quotes it.

## 1. Moodle 4.x question bank (the closest model)

Data model
- (a, search snippet of the 4.0 schema notes) `question_bank_entries`: a question that appears in the bank, which can have many versions. `question_versions`: joins all versions of a question (rows in `question`) to their `question_bank_entries` row. `question_references`: records where a specific question is used. `question_set_references`: records where groups of questions are used, e.g. random questions in a quiz. Data from the old quiz slot tables was moved into these reference tables in 4.0. Source: Moodle `question/upgrade.txt` mirrors (e.g. https://stack-demo.maths.ed.ac.uk/demo/question/upgrade.txt, https://moodle-sciences-24.sorbonne-universite.fr/question/upgrade.txt; the second host did not resolve when fetched).
- (c) Shape: `question_bank_entries(id, questioncategoryid, idnumber, ownerid)` 1..n `question_versions(id, questionbankentryid, version, questionid, status)` 1..1 `question(id, ...content...)`. The content row (`question` plus type-specific tables such as `question_answers` and `qtype_multichoice_options`) is the immutable version. Each version owns its own `question_answers` rows with new ids, so option ids are NOT stable across versions in Moodle.

Where the pin lives
- (a) Resolution rules from MDL-78025: a reference to a specific version is relevant only to that exact `questionid`; a reference to "always latest" is relevant to the latest non-draft version of the entry. Source: https://tracker-old.moodle.org/browse/MDL-78025 (search snippet; the page itself 404ed on fetch). MDL-74255 confirms "always latest" must pick only `ready` versions (bug returned a draft): https://tracker-old.moodle.org/browse/MDL-74255.
- (c) `question_references.version` is NULL for "always latest", an int for a pinned version. That is the quiz-slot (template) pin. The attempt pin is separate: `question_attempts.questionid` stores the id of the exact `question` (version) row served, so an attempt points at a version row even if the slot floats.
- (b) Tim Hunt (Moodle question-engine maintainer): once a student starts, Moodle records which version of which question is used in that attempt and sticks with it. https://moodle.org/mod/forum/discuss.php?d=438090 (fetch of ?d=453360 returned 403).

Snapshot beyond the FK
- (c) `question_attempts` also stores `questionsummary` and `rightanswer` as text, plus `variant` and `maxmark`, written at attempt start. Reviewing an attempt does not depend on re-deriving the question text from the live row, and the question engine re-instantiates the question from the pinned `questionid` for rendering and re-grading. This is a belt-and-braces denormalised copy beside the version FK.

In-progress attempts
- (b) They finish on the version they were served; only attempts that start after the edit see the new one (forum link above).

How a version is created
- (b) Every save of the edit form creates a new `question` row and a new `question_versions` row (version = max + 1). No change detection and no minor-edit concept; MDL-80006 asks for one: https://tracker-old.moodle.org/browse/MDL-80006. Status `ready`/`draft`/`hidden` gates whether it is drawn.

Lessons for FLS
- Pin lives at two levels in Moodle (slot reference; attempt row). FLS's "served paper key + `QuestionAnswer` FK" decision matches the attempt-level pin; there is no slot-level float because FLS serves only the live row.
- Moodle copies options per version with new ids, so a past attempt's chosen answer references the old version's own answer row. FLS plans the opposite (live option ids kept inside a JSON snapshot so `QuestionAnswer.selected_options` still match). That is workable only because option rows are never recycled or re-pointed; if `content_save` ever deletes and recreates an option with a new uuid, the snapshot's id and the live id diverge (see 6).
- Floating "latest" plus regrade rewrites history (MDL-75823, https://tracker-old.moodle.org/browse/MDL-75823, b). FLS has no float; keep it so.

## 2. Canvas (Classic Quizzes and New Quizzes)

- (a) Classic Quizzes API: `GET /courses/:id/quizzes/:id/questions` takes `quiz_submission_id` and `quiz_submission_attempt` and "returns the questions that were presented for that submission instead of the quiz's current questions... when the quiz was modified after the submission was created". Both parameters are required together. Source: https://developerdocs.instructure.com/services/canvas/resources/quiz_questions
- (b) Mechanism (secondary): Classic Quizzes keep a `quiz_submissions.quiz_data` JSON blob (the questions as generated for that submission, including the drawn random questions) and a `submission_data` JSON blob of answers keyed by `question_id`, and `quizzes` carry versionable `quiz_data`. Community note: https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-what-was-the-answers-of-quizes-of-each-student/m-p/197928 (snippet). I did not confirm an `assessment_question_version` table; that name returned no hits. Canvas Data 2 documents `assessments_questions` with a `quiz_version` int (b): https://developerdocs.instructure.com/services/dap/dataset/dataset-namespaces/dataset-newquizzes.
- (c) Model: copy the whole served paper into the attempt row at start (denormalised snapshot), rather than a normalised version table. Reading a past attempt never touches live question rows.
- (a, from prior art note) New Quizzes: once students have submitted, an edit forks a copy; the original is only reachable from quizzes already taken.

Lessons: Canvas is the "snapshot in the attempt" shape. It is simple and audit-proof, but it grows with every attempt and has no per-question version identity (statistics cannot group by version; New Quizzes works around that by forking items). FLS's version rows plus a pin is the normalised alternative; the cost is that the version row must be complete enough to reproduce the paper.

## 3. Open edX

- (a) `StudentModule` keeps state for one XBlock usage and one student, keyed `(student, module_state_key, course_id)`; `state` is a JSON object. Sources: https://git.andalsoftware.com/Andal.LND/edx-platform/raw/branch/master/lms/djangoapps/courseware/models.py and https://edx.readthedocs.io/projects/devdata/en/latest/internal_data_formats/sql_schema.html (search snippets).
- (a, prior art note) Editing a released problem leaves learner state untouched; later learners are scored on the new definition: https://docs.openedx.org/en/ulmo/educators/references/course_development/modifying_released_problem.html.
- (c) The key is the usage key, which is stable across edits, so state has no pointer to a definition version. The definition is held in the modulestore, which does have course-version history (draft/published branches, structure versions), but learner state is not linked to a structure version. Past answers are therefore shown/scored against whatever the current definition is. Not a model to copy; it is the "live row" behaviour FLS has today.

## 4. django-simple-history

- (a) Source read: https://github.com/jazzband/django-simple-history/blob/master/simple_history/models.py
  - A `post_save` handler writes a historical row on every non-raw save, type `+` create or `~` update. It returns early if the instance carries `skip_history_when_saving` (set by `save_without_historical_record`) or if `SIMPLE_HISTORY_ENABLED` is false.
  - No change detection at save time. Every save writes a row even if nothing changed. Diffs are on demand via `diff_against()` (compares `model_to_dict`, returns `ModelChange` objects).
  - `bulk_create`/`update` skip signals, so rows are not written unless `bulk_create_with_history` / `bulk_update_with_history` are used.
  - Immutability: none enforced. Historical rows are plain model instances; nothing blocks update or delete. `cascade_delete_history=True` deletes history when the live row is deleted; default writes a `-` row.
  - M2M: not tracked unless declared in `m2m_fields`; then an m2m history model copies the through rows on each save (`create_historical_record_m2ms`) and `m2m_changed` writes a `~` row. Docs: https://django-simple-history.readthedocs.io/en/latest/historical_model.html and https://django-simple-history.readthedocs.io/en/latest/advanced.html.
- Model: one historical table per tracked model (a copy of every field, with `history_id`, `history_date`, `history_type`, `history_user`, `history_change_reason`). History id can be a UUID (setting `SIMPLE_HISTORY_HISTORY_ID_USE_UUID`).
- Pin: simple-history has no concept of pinning; callers hold a `history_id` (or use `instance.history.as_of(date)`).
- Lessons: (1) copy-all-fields-per-row is the right shape for "version of one model", but the option set is a relation, and simple-history needs the separate m2m/historical-child machinery. A JSON snapshot of options on the question version avoids needing two historical tables with join logic. (2) Row-per-save without change detection would break FLS's "version only when versioned fields differ" rule, so change detection has to be written by hand in `content_save` (compare to the latest version's snapshot). (3) Do not rely on a library for immutability; enforce it in the model (see 6).

## 5. django-reversion

- (a) Source read: https://django-reversion.readthedocs.io/en/stable/api.html
  - A `Version` row stores `serialized_data` (Django serialization, JSON by default), `format`, `object_id`, `content_type`, and belongs to a `Revision` (date_created, user, comment). A revision groups versions saved in one `create_revision()` block, so a question plus its options are one atomic revision.
  - Related rows are included with `follow` (FK, M2M, reverse relations, or a property returning a queryset). Parent models of multi-table inheritance are not followed by default.
  - Versions are created on each `save()` of a registered model inside a revision block (signals; `QuerySet.update()` records nothing).
  - Change detection is opt-in: `ignore_duplicates=True` compares serialised fields to the previous version and the docs warn it adds significant overhead. `Version.objects.get_unique()` filters to distinct states.
  - Immutability is not stated; `Revision.revert(delete=True)` can delete instances reachable by `follow`.
- Model difference from simple-history: the snapshot is serialised JSON, so it survives live-schema changes only if the serialised field set stays loadable (`field_dict` raises `RevertError` when incompatible). FLS's version JSON should therefore be a hand-defined, versioned-schema dict (explicit keys), not a model serialisation, so a later migration of `FormQuestion` cannot break reading old versions.
- Lessons: one revision groups the parent and its children (FLS: one version row holds question fields plus options, same effect); dedupe by comparing serialised state to the latest is exactly the FLS rule, and it costs a read per question per `content_save` (fine at content-save frequency).

## 6. TAO (OAT) and QTI

- (a) TAO's `taoRevision` extension ("Item History") keeps multiple versions of an item, each with time, user and message; the latest is the live one. Created on an explicit "commit" by the author, not on every save. Sources: https://userguide.taotesting.com/user-documentation/latest/public/managing-different-versions-of-an-item and https://www.taotesting.com/?p=3672.
- (c, unverified) TAO deliveries are compiled/published snapshots of tests and items made at publish time, so a delivery is fixed content and results (QTI-style item identifier plus candidate response variables) refer to the delivery's compiled copy. I found no source this session stating how a delivery execution references item revisions, and TAO source was not read. The QTI Results Reporting model records item identifier, response and outcome variables per attempt, not the item definition. Spec: https://1edtech.org/standards/qti/index. QTI conveys identity, not versions.
- Lesson: "publish makes an immutable copy; sessions run the copy" is the same pin-at-start idea at delivery granularity (the paused `content_snapshots` idea in FLS).

## 7. Cross-implementation comparison

| System | Identity | Version unit | Options across versions | Pin | Created |
|---|---|---|---|---|---|
| Moodle | `question_bank_entries` | `question` row via `question_versions.version` | new answer rows per version (new ids) (c) | slot ref (version or latest) and `question_attempts.questionid` (c) | every save (b) |
| Canvas Classic | question id | copy inside attempt (`quiz_data` JSON) (b) | embedded in the blob | whole paper copied into the submission | at attempt start (b) |
| Open edX | usage key | none for learners | n/a | none | n/a |
| simple-history | model pk | full copy of row per save | m2m history model if declared | caller holds `history_id` | every save (a) |
| reversion | model pk + content type | serialised JSON per revision | followed relations in the same revision | caller holds a `Version` | every save in a revision block; dedupe optional (a) |
| TAO | item | explicit commit (a); published delivery copy (c) | copy | delivery | explicit |

Patterns that bear on the open decisions in `idea.md`
- Pin by FK to an immutable version row (Moodle) plus a denormalised readable copy at attempt time (Moodle `questionsummary`/`rightanswer` (c), Canvas `quiz_data`). FLS's two pins (served-paper `versions` key and `QuestionAnswer` FK) are a version of both. A cheap extra worth weighing: the served-paper `versions` key stores the version id and number, and the answer FK stores the version, so each can be cross-checked.
- Dedupe by exact comparison to the latest version is what simple-history and reversion leave to the caller (reversion's `ignore_duplicates`); Moodle skips it and makes a version on every save, which would produce a version for every `content_save` run in FLS. The FLS rule (compare, then write) is correct; the comparison should be on a canonical dict (sorted options by order then id, normalised types) of exactly the versioned fields.
- Immutability is never enforced by the libraries read. Moodle versions are immutable by convention. FLS should enforce it in the model (raise on update of an existing row, `save()` on a pk that exists, and block `QuerySet.update`/`delete` via a custom manager or a DB trigger) because the audit claim depends on it.
- A float-to-latest pin is the cause of history rewriting (MDL-75823). FLS has none; do not add one.
- Option identity: Moodle re-keys options per version; FLS's design keeps live option ids in the snapshot. That works only while `content_save` never deletes and re-creates an option under a new row id for an unchanged authored option. If an option is removed and later re-added, it gets a new row; old snapshots keep the old id, answers keep the old id, and no collision occurs. State it.
- Migration baseline: nothing surveyed does a "version 1 is the content when the migration ran" backfill. Moodle's 4.0 upgrade created one `question_bank_entries` and one `question_versions` row (version 1) per existing question (c), the same baseline and the same unavoidable caveat that it is not the content seen at the time. simple-history ships `populate_history` for the same backfill (a, https://django-simple-history.readthedocs.io/en/latest/quick_start.html): it writes a `+` row for rows with no history, which is the analogue of "first content_save after migration must not double-count version 1".

## Gaps
- Moodle column-level schema (`question_attempts`, `question_references`) was not read from source; confirm in `lib/db/install.xml` / `question/engine/db` on a stable branch (raw file is 390k characters; the question tables were beyond the 300k offset tried) before quoting.
- Canvas `assessment_question_version` not found; Canvas storage of question snapshots is from secondary sources.
- TAO delivery-to-item-revision linkage and Open edX modulestore versioning not read.

## URLs
- https://tracker-old.moodle.org/browse/MDL-78025
- https://tracker-old.moodle.org/browse/MDL-74255
- https://tracker-old.moodle.org/browse/MDL-75823
- https://tracker-old.moodle.org/browse/MDL-80006
- https://moodle.org/mod/forum/discuss.php?d=438090
- https://stack-demo.maths.ed.ac.uk/demo/question/upgrade.txt
- https://developerdocs.instructure.com/services/canvas/resources/quiz_questions
- https://developerdocs.instructure.com/services/dap/dataset/dataset-namespaces/dataset-newquizzes
- https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-what-was-the-answers-of-quizes-of-each-student/m-p/197928
- https://docs.openedx.org/en/ulmo/educators/references/course_development/modifying_released_problem.html
- https://git.andalsoftware.com/Andal.LND/edx-platform/raw/branch/master/lms/djangoapps/courseware/models.py
- https://github.com/jazzband/django-simple-history/blob/master/simple_history/models.py
- https://django-simple-history.readthedocs.io/en/latest/historical_model.html
- https://django-simple-history.readthedocs.io/en/latest/advanced.html
- https://django-simple-history.readthedocs.io/en/latest/quick_start.html
- https://django-reversion.readthedocs.io/en/stable/api.html
- https://userguide.taotesting.com/user-documentation/latest/public/managing-different-versions-of-an-item
- https://1edtech.org/standards/qti/index

status: ok
reason: Moodle, Canvas, Open edX, simple-history, reversion, TAO covered; simple-history and reversion read at source/doc level, Moodle column schema and Canvas/TAO internals unverified (labelled c/b)
