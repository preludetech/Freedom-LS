# Known complaints: removing, hiding, retiring content in an LMS

Scope: what learners, educators, authors and auditors complain about in other systems when content is removed, hidden, archived or soft-deleted. Evidence is thin in places (two web searches per platform at most); each item says how strong the source is. Other systems' terms are kept (Moodle "hidden", Canvas "deleted"); FLS's word is **retired**.

## 1. Hidden/deleted questions still drawn from random pools (Moodle)

- Moodle MDL-50373 (filed against 2.9/3.0): a Cloze question deleted while in use was only hidden, and it kept appearing through a random-question slot taken from a category. It rendered wrongly, as a short-answer question showing the raw cloze code as its text. https://tracker-old.moodle.org/browse/MDL-50373
- Moodle MDL-82875: the delete message says a question will be hidden rather than deleted, and hidden questions are still exported even though the category count shows only visible ones. So the count, the export and the draw disagree about what exists. https://tracker-old.moodle.org/browse/MDL-82875
- Lesson for the spec: every reader of "the question tree" needs the same retired filter (serving, draws, shuffles, counts, exports). The idea already says the filter applies before any shuffle or draw. Add counts and exports to the checklist.

## 2. Edits and deletions that silently change grades or scores (Canvas)

- Canvas regrade only covers some question types. It does not cover added or deleted questions, and deleting questions has unexpected effects. Questions linked to a bank are excluded, because the bank question may be used in several quizzes. https://community.instructure.com/en/kb/articles/661038-what-options-can-i-use-to-regrade-a-quiz-in-a-course
- Staff say grades cannot be "rolled back", least of all per question. https://community.canvaslms.com/t5/Canvas-Question-Forum/Is-a-roll-back-possible-to-graded-essay-questions-after-editing/m-p/570267
- Deleted quizzes: forum users report attempts and responses are lost and grades must be re-entered by hand. https://community.canvaslms.com/t5/Canvas-Question-Forum/Undelete-a-quiz/m-p/620532 and https://community.canvaslms.com/t5/Canvas-Question-Forum/Deleted-Quiz/m-p/197796
- Lesson: complaints cluster around irreversibility and silent score change. This supports "attempts pin at start, `max_score` unchanged" and "never deleted". Retire must not trigger any rescore.

## 3. Completion percentages moving when content changes

- Open edX forum: adding sections or units in Studio lowers the course progress percentage in the MFE. The poster treats it as expected, but it is the same mechanism a removal would reverse. https://discuss.openedx.org/t/how-does-the-progress-work/18836
- Open edX forum: the student progress page did not update when problems were added, edited or deleted. https://discuss.openedx.org/t/students-progress-page-doesn-t-update-when-new-problems-are-added-or-update-and-delete-the-problem/10475
- edx-platform PR 33963: grades not persisted, so the progress page and gradebook were wrong; the block-structure cache had missing blocks. https://github.com/openedx/edx-platform/pull/33963
- OpenLearning: "course percentages drop after new module introduced". https://help.openlearning.com/t/q5r0vy/course-percentages-drop-after-new-module-introduced
- Schoox: learners show 100% completion alongside lower course/learning-path progress after content changes. https://support.schoox.com/hc/en-us/articles/38131780027543-Understanding-100-Completion-Rate-with-Lower-Course-and-Learning-Path-Progress
- Oracle customer connect: an activity was removed but is still reflected in the progress. https://community.oracle.com/customerconnect/discussion/681849/removed-activity-but-it-is-still-reflected-in-the-progress
- Lesson: two opposite complaints. Either a percentage changes under a learner (a learner at 100% drops, or a finished course reopens), or it does not change and the numbers disagree with what is visible. The idea says retired content is served to no one but progress rows are kept. The spec should state whether retired content counts in the denominator of `CourseProgress` and in cohort completion figures, and say the same thing in every report. (Inference from these threads; no source says what a "right" answer is.)

## 4. Learners cut off mid-attempt

- Not found as a documented, sourced complaint in this search. The design risk is plain from the idea: a retired `Form` ends in-progress work, and a retired `Course` leaves the learner's list. Moodle and Canvas threads above show the neighbouring complaint (a changed quiz changes in-flight or past attempts). Treat as a risk to test, not a sourced fact. Suggest the educator surface shows a count of in-progress attempts on a form before the save retires it, or the save output reports it.

## 5. Reports showing orphaned or unexplained answers

- Canvas and Moodle threads above: after deletion, answers remain with no question text, or the question renders as raw code (MDL-50373). Auditors then cannot say what the learner saw.
- Lesson: answers to retired questions must still resolve to the question text and options (retired `QuestionOption` rows must stay readable in audit views), and be visibly marked retired. This matches the idea's Open recommendation to mark answers given to retired questions.

## 6. Accidental mass removal from a bad sync

- No platform-specific complaint found in these searches; the surveyed content imports are additive (see `research_question_versioning_prior_art.md`), so there is little prior art for a pruning sync. Treat as a first-principles risk: a wrong path, a partial checkout or a missing directory makes every row "absent" and retires everything at once, and learners lose the course catalogue immediately.
- Suggested guards for the spec (not sourced): the save fails, or needs an explicit flag, when the run would retire more than a stated share of a site's content, or retire a whole course; the save output lists counts per model; retire is reversible by re-running with the right paths (already true via un-retire). Spec 1 (`content-save-safety`) owns path and git checks, so cross-reference it.

## 7. Surprise reappearance on restore

- Not found as a sourced complaint. Un-retire is automatic on the next run with the same uuid, so a stray restore can resurrect a question or course mid-term, with old learner data live again. Consider: the save output reports un-retired counts as prominently as retired counts, so an educator sees a reappearance came from the sync.

## 8. Retired state invisible to educators

- Moodle's hidden questions are counted and exported inconsistently (MDL-82875 above). Educators and auditors complain when a state is invisible or inconsistent between screens. Supports the recommendation that every educator surface shows the retired mark and that admin changelists get a filter and column.

## Checklist the complaints suggest for the spec

1. One shared "not retired" filter used by serving, draws, shuffles, counts, exports and progress denominators.
2. No rescore, no `max_score` change, on retire or un-retire.
3. Retired options and questions stay readable wherever answers are shown, marked retired.
4. Define how completion and progress treat retired content, once, and apply it everywhere.
5. Guard against a bad run retiring most of a site; report retired and un-retired counts per model.
6. Say what happens to in-progress attempts on a retired `Form`, and make the learner-facing page say so rather than 404 silently.

status: ok
