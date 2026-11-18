# Research: reference implementations of question-to-section/outcome links

Scope: data shape only (one vs several targets, where the link is authored, how it survives content edits). Web-sourced items carry URLs. Items marked (memory) come from my prior knowledge and were not re-verified this session.

## Findings by system

### Canvas (outcomes alignment)
- Link is a many-to-many alignment authored in the UI, in the quiz/bank tool, not in the content file. Classic quizzes aligned an outcome to a whole question bank; New Quizzes aligns to the quiz or to an individual question. Questions that already live in an item bank could not take an alignment, and users filed idea requests for it. The sources conflict and are partly archived, so this is low confidence.
- Lesson for the spec: even a mature LMS ended up with a gap where "question in a bank" and "question with a target" did not compose. Our answers already require the link to work on unplaced bank forms, so the link must sit on the question (or form), not on the placement.
- URLs: https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-Allow-outcomes-to-be-aligned-with-item-banks/m-p/543896 ; https://community.canvaslms.com/t5/Archived-Questions/Unable-to-Add-Outcomes-to-Item-Bank-Questions/m-p/474508 ; https://community.canvaslms.com/docs/DOC-1906

### Moodle
- Competencies link to a course and to an activity (course module), several per activity, and can drive completion. No question-level link: a forum answer says it is unavailable and suggests putting the competency code in the question name or feedback (a string convention, no integrity). Question bank categories are a tree of containers that scope reuse, not a link to course content (memory).
- Lesson: the activity-level link is a real FK row to a many-to-many join, several per activity. The question-level workaround is a free-text code, which is exactly the `tags` option the answers already rejected.
- URLs: https://moodle.org/mod/forum/discuss.php?d=346809 ; https://docs.moodle.org/404/en/Competencies

### Open edX content tagging
- Tags are authored in Studio (UI), many tags per block from controlled taxonomies, shown to authors only. Tag rows store a copy of the taxonomy export id and the tag value, so the display survives deletion of the taxonomy or tag (dangling links are tolerated, not errors). Tags are copied when a block is duplicated, and course export writes a tags CSV that import re-applies, matching taxonomy by export id (a stable id, not a display name). Whether tags follow a library block copied into a course is not clearly documented.
- Lesson: survival across export/import hinges on a stable external id, not the name; this matches our `uuid`/path split. Open edX tolerates dangling tags; the answers choose the opposite (error at load), which is stricter and fits a file-authored system better.
- URLs: https://openedx-core.readthedocs.io/en/stable/openedx_tagging/decisions/0006-tag-changes.html ; https://www.github.com/openedx/edx-platform/pull/34356 ; https://opencraft.com/projects/content-tagging/ ; https://docs.openedx.org/en/ulmo/educators/how-tos/course_development/add_delete_tags_in_library_content.html

### QTI (memory)
- QTI items carry descriptive metadata (LOM/`qtiMetadata`) and, in a test, `assessmentItemRef` has a `category` attribute: a list of free-string categories, many per item, that the test's `outcomeDeclaration`/`outcomeProcessing` can sum per category (this is how per-section subscores are built). Categories are authored in the test/package file next to the item reference, i.e. the "tested topic" is a label on the placement of the item in a test, and the item itself is reusable.
- Lesson: the closest standard to our need is many labels per item, authored in a file, with per-label scoring computed downstream. QTI labels are free strings with no integrity check, which the answers deliberately avoid. QTI also puts the label on the item-in-test reference, which is the opposite choice from "link on the question, not the placement"; the form-level default plus per-question override is roughly that two-level idea.

### Kolibri / Khan Academy (memory)
- Kolibri content is a tree of nodes (topic > exercise > assessment items). An exercise node belongs to its topic by tree position; assessment items sit inside the exercise node and inherit its place. Per-item skill links do not exist: the unit of "skill" is the exercise node. Khan similarly attaches exercises to skills/topics at exercise level, not per item.
- Lesson: both link at the container level (exercise), not per question. That supports the form-level default being the common case and the per-question override the exception.

## Cross-cutting data-shape observations
1. Many targets per question is the norm (Moodle activity, Open edX tags, QTI categories, Canvas alignments). One-only systems (Kolibri) get it by containment. Several targets matches the answers.
2. Where authored: file-first systems (QTI, Open edX export, Kolibri) put it beside the item or its container; UI-first systems (Canvas, Moodle) use a join table. Our "file key, stored as a join table row" combines both. A join table (ManyToMany or explicit through model) is the shape; a JSON list of paths is the failure mode (Moodle's name/feedback code convention).
3. Two-level default/override (QTI test-level vs item-level; Kolibri container vs item) is common. Gap worth settling in the spec: the per-question key replaces the form default, it does not merge; an explicit empty list is the way to say "no section" for a question under a form default. None of the references mention this, and it changes the schema (absent vs empty must differ).
4. Survival: the robust references key the link on a stable id (Open edX export id; our content `uuid`) and store a display copy. In FLS the targets are resolved by path at load into FK rows, so renaming or moving the target in the source tree breaks the path in the form file (loud error, per answers) but the stored FK to a row with a stable `uuid` is unaffected until the next reload. Spec should state that the path is only the authoring syntax and the row identity is the target's `uuid`, and decide whether `content_save` rewrites it.
5. Reload semantics: Open edX and QTI re-apply links wholesale on import. The matching behaviour for us is replace-the-set on every reload of the question (delete join rows no longer in the file, add new), so removing a section line from the YAML removes the link. Without this, links accumulate (stale rows) in a reference-style join table.
6. Bank/unplaced case: Canvas's bank gap shows the link must not depend on the form being placed or the item being inside a quiz. The FK targets content, never the placement, which the answers already say; the remaining check is the loader's unplaced-form behaviour (fact b in the prior research), not this feature's data shape.
7. Deletion of the target: references tolerate (Open edX keeps a display copy) or leave orphans. The answers choose error at load for a missing path; at the DB level the spec still has to choose the FK `on_delete` for a target removed after links were stored (suggest CASCADE on the join row only, never touching the question or answers, since answer rows are PROTECTed and learners' history must stay).

## Implications for the spec
- Join model (question to CoursePart or Topic, many per question), not a JSON field; two nullable FKs with a check constraint, or a generic FK, to support both target types. Pick one and say why.
- Form-level default plus per-question override with replace semantics and explicit-empty = none.
- Replace-the-set on reload; the path is authoring-only.
- Dangling-at-load is an error naming question and target; post-load target deletion must not delete questions or learner answers.

status: ok
