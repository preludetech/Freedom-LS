# Retire content that is removed from the source

Spec 2 of 5 in the SACAA content versions and access effort. Read the "SACAA content versions and access" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

One `content_save` call for a site covers all of that site's content, across every path it is given. Any file-sourced row for that site that is not present in the run is marked retired. It is never deleted. Retired content is served to no one, new learners and existing learners alike. Everything learners left against it (progress, answers, attempts, registrations) is kept for audit. Educators see retired content marked retired wherever they see it. Content that returns to the source with the same uuid is un-retired.

## Why

Today a run adds and updates but never takes away. A Topic, Form or FormQuestion deleted from the content repo stays in the database and is still served, because every learner-facing query walks the relations and finds the row. SACAA requires that a revised question is blocked from the questions available to students yet stays in the system for audit. Deleting is not an option: learner rows reference content with PROTECT (`FormProgress.form`, `QuestionAnswer.question`, `TopicProgress.topic`, `CourseProgress.course`, both registration types), and a deleted `QuestionOption` silently drops the record of what a learner chose. Retiring is the safe state: the content stops being served and the audit trail stays whole.

## What is settled

- **Single source per site.** A `content_save` call for a Site is taken to point at all of that Site's content. Its paths are the whole source (the several-paths and git-repo rules belong to `sacaa-compliance-content-versions-and-access-1-content-save-safety`, which this spec builds on). "Present in the run" means the row's uuid was found in any of the paths given. The match key is the uuid, as for every other upsert. A run that is aborted or fails retires nothing: retirement is part of the same atomic save.
- **Content models in scope.** The file-sourced models that are never pruned today: `Course`, `CoursePart`, `Topic`, `Activity`, `Article`, `Form`, `FormPage`, `FormContent`, `FormQuestion`, `QuestionOption`, `CourseCategory` and `File`. Each gains a retired state. `ContentCollectionItem` is derived, not authored; see Open.
- **Never deleted.** A retire is a flag, not a delete. `danger_content_delete` stays the only thing that deletes content.
- **Served to no one.** A retired row is excluded from every learner-facing read, for learners who have never touched it and for learners with progress on it: the course catalogue, the course outline and its children, topic and activity and article pages, forms, question serving, and the draws and shuffles that pick questions for a paper. A retired `QuestionOption` is not offered as a choice. A retired `Course` leaves the learner's course list. The filter applies before any shuffle or draw, so a retired question can never be shuffled or drawn in.
- **Kept for audit.** Every `FormProgress`, `QuestionAnswer` (and its selected options), `TopicProgress`, `CourseProgress`, `CourseFormAttempt`, `LearnerCourseRegistration` and `CohortCourseRegistration` that points at retired content is left untouched. Registrations on a retired `Course` keep their own `is_active` value; retiring content does not deactivate any registration.
- **Attempts pin at start.** An attempt already in progress finishes on the paper it was served, even if a question on that paper is retired after it started. The retired question stays in that attempt's paper, is answered and scored in it, and the attempt's `max_score` is unchanged. Only attempts that start after the retirement get a paper without the question.
- **A retired `Form` or `Course` ends its in-progress work.** A retired `Form` is served to no one, so an attempt in progress on it cannot be resumed; it stays as recorded. A retired `Course` leaves the catalogue and every learner's course list and accepts no new registrations. A retired question on the paper of an attempt that started before the retirement is the one exception above, because the paper is pinned at start.
- **Un-retire.** A row whose uuid is present in a later run is un-retired by that run, along with its content update. Its kept learner data is live again without further action.
- **Educators see it marked.** Where educators see retired content, it carries a visible retired mark. Which surfaces are in Open.
- **The word.** The term is **retired**. The glossary already uses it for `JobTitle`, `Department` and `Location` entries with `is_active=False` that are hidden from pickers and never deleted; the content sense is the same idea (hidden from use, kept because rows still hold it) on models that do not share that flag. The glossary gains the content sense in its "Words with an existing meaning" table, kept apart from **deactivated** and **inactive** (an `is_active` flip on a registration, learner or the like) and from **removed** (a row actually deleted).
- **A separate axis from `Course.visibility`.** `Course.visibility` (published, coming soon) and `Article.visibility` are authored in the file and say how content is shown. Retired is set by the save from the content's absence and overrides visibility: a retired `Course` is not shown whatever its visibility.
- **Revision is not retirement.** A question that is merely changed is not retired here. The version rows that handle revision belong to `sacaa-compliance-content-versions-and-access-3-question-versions`, which depends on this spec's retired state.
- **Shuffle.** `sacaa-compliance-2-shuffle` reads the live question tree when it builds the served paper; the retired filter applies there.

## Open until the spec

- **Which educator surfaces show the retired mark.** Candidates: course preview and outline in the educator interface, the cohort report, learner progress views, and registration lists. The content and form admins are gone, so there are no admin changelists to mark. Recommend: every educator interface page that lists or opens content or a question shows a retired badge; the cohort report and attempt views also mark answers given to retired questions; the admin answers page marks a question that is retired. Retired content stays visible to educators (not hidden), marked.
- **A retired question inside a keep-together group, or inside a drawing page.** A group is a contiguous run of content blocks and questions on a page; a page may draw N items from its questions and groups. Options: retire the whole group; serve the group minus the retired member; block the save. Recommend: serve the rest of the group minus the retired question, and for a draw, remove the retired question (or its whole group, if it was in one) from the pool before the draw; when what remains has fewer items than the page's N, fail the save with a validation error naming the page, so a thin pool is never served silently. Draws that `sacaa-compliance-3-question-pools` introduces follow the same rule; this spec states it, that spec builds it.
- **`ContentCollectionItem` left-behind rows.** A sync today never removes the row a moved child left behind, and a dropped child's row stays. Recommend: a collection item whose child is retired is skipped when outlines are read, but the row itself is not given a retired state; and the row is un-hidden automatically when the child returns. A collection item left behind by a move to another collection keeps its present behaviour.
- **`File` and `CourseCategory` retirement.** `File` is keyed by `(site, file_path)` and has no uuid. Recommend: a `File` is retired when its path is absent from the run and un-retired when it returns; a retired `CourseCategory` leaves the catalogue filters.
- **Field shape.** One flag per model, a timestamp that records when it was retired, or both. Recommend: a nullable timestamp (retired when set), so the audit can say when the source dropped it.
- **Whether a retire and an un-retire write an audit entry.** Recommend: no per-row entry (a save can retire many rows); the save records a count in its own output.

## Out of scope

- Versioning questions on revision, and pinning versions: `sacaa-compliance-content-versions-and-access-3-question-versions`.
- Git checks, several paths, missing-uuid failure and organisation creation: `sacaa-compliance-content-versions-and-access-1-content-save-safety`.
- The question-viewing role and audit entry, and admin page removal: `sacaa-compliance-content-versions-and-access-4-question-access`.
- Deleting content, or any change to `danger_content_delete`.
- `content_snapshots` (paused) and versioning topics or courses.
- Changing `Course.visibility` or `Article.visibility`.

## Resources

- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/idea.md`: the source brief ("Assume single source").
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_content_save_pipeline.md`: what a run removes today (section 3) and the word "retired" in the glossary (section 5).
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_question_versioning_prior_art.md`: retirement and additive-import patterns (Moodle hides, Questionmark retires, all surveyed imports are additive).
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access-3-question-versions/research_question_version_seams.md`: section 7, a retired question against shuffle groups and pools.
- `spec_dd/2. in progress/sacaa-compliance-2-shuffle/idea.md` and `spec_dd/1. next/sacaa-compliance-3-question-pools/idea.md`: the served paper and draws the retired filter feeds.
- `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`: the existing "retired" and `is_active` rows.
