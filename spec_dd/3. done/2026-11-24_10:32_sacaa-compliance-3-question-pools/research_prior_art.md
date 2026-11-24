# Research: prior art for per-attempt question pools and draws

Question: what has already been tried for per-attempt question pools/draws, here or elsewhere, and what happened?

Labels: (c) read from files in this repo; (w) web page or search summary (summaries only; pages not all read in full); (i) inference. This builds on `research_question_bank_patterns.md` (this directory), and the shuffle spec's `research_prior_art.md`; it does not repeat them. `git log` is not available, so history is taken from spec files.

## 1. In this repo

### 1.1 Nothing draws today; earlier attempts were spec-only (c)

- `spec_dd/3. done/2026-11-21_11:09_sacaa-compliance-2-shuffle/research_prior_art.md` s1.1 and `spec_dd/3. done/2026-11-20_10:30_sacaa-compliance-1-served-paper-record/research_prior_art.md` (history table, 2026-06-30 row): `compliance-form-randomization` (all four knobs plus a record in one idea, with `QuizAttemptDraw`, `QuestionPool`, `shuffle_seed`, `realized_order`) was moved to in progress 2026-07-01, never specced, paused, then cut into the four `sacaa-compliance-*` specs on 2026-11-17. No code, no branch. Lesson already drawn there: the single wide idea stalled; narrow specs shipped. This spec should stay narrow: the draw function, the page key, validation, scoring-on-served-set and authoring.
- The paused idea's `QuestionPool` / `QuizAttemptDraw` models (`research_question_bank_patterns.md` s5.1-5.5) are superseded by the settled design in `idea.md`: draw unit is the page, no pool model, the draw is written into the existing served paper. Do not resurrect `QuizAttemptDraw`; spec 1 explicitly rejected a defaulted per-attempt UUID and a second per-attempt record.
- `spec_dd/3. done/2026-11-18_15:43_learner-interface-features-1-question-sections/` (`idea.md` l.50, `1. spec.md` l.29, `research_prior_art.md` l.7-8, 41-47): sections are a static link from a question to a course part; pools, draw and shuffling are explicitly out of scope there. It found the bank-as-separate-namespace pattern and the Storyline resume-redraw failure, and deferred both. Net: no section data exists to key a draw on, consistent with "draw unit is the page".
- `spec_dd/1. next/learner-interface-features/research_question_model.md` s3 and item 7 (l.39-42, 76): no pool, random draw or shuffle exists in `form_engine`; a question belongs to exactly one page of one form (`FormQuestion.form_page` required CASCADE FK), cannot be shared. Notes that a retake today sees the identical full quiz. It lists "decide whether the pretest depends on randomization" as an open call, so `learner-interface-features-2-test-out` and `-3-revision-questions` (`idea.md` l.70) are downstream consumers that expect pool behaviour to exist; they do not constrain it.
- `spec_dd/1. next/sacaa-compliance/research_form_engine_seams.md` (c): s3 (l.39-45) scoring currently loops over every page in the form, so a drawn N-of-M scores N/M, `get_incorrect_quiz_answers` lists undrawn questions as blank-incorrect, and the results-page "outdated score" check would flag every drawn attempt. Fix named: score over the served set. s4 (l.54-58): a drawn-away source question silently drops a `when`-gated item, hence the no-`when` rule. l.75: admin `answer_groups` walks all pages and shows unasked questions as "not asked" rows (`is_asked`), so the admin answers view needs checking against undrawn questions. l.85-87: sections as pool key rejected for now because that spec was undecided. l.70: the validator belongs in a new `validate_form_randomisation` beside `validate_form_conditions`.

### 1.2 What spec 1 and spec 2 shipped, and what they left for this spec (c)

- `freedom_ls/form_engine/served_paper.py` exists. Functions: `new_seed`, `_scope_rng(seed, scope)`, `shuffle_with_locks`, `_served_options`, protocol `Groupable` (`.group`), `shuffle_units(children) -> list[list[T]]`, `_served_children(page, form, seed)`, `build_served_paper(form)`, `served_child_ids`, `ensure_served_paper`. Spec 2's plan (`3. done/.../sacaa-compliance-2-shuffle/2. plan.md` l.173, 299) says `shuffle_units` is public, does not touch the DB, and is imported by pools; and that `build_served_paper` draws the seed first.
- Spec 2 research (`research_best_practices.md` l.69, 94-96, 269) says: draw must run before shuffle on the same atoms; keep `build_atoms`, draw and shuffle as separate functions; do not draw all knobs from one RNG stream in loop order (per-scope RNGs; `_scope_rng` is that fix, so the draw needs its own scope name).
- Spec 2 `research_codebase.md` s10 (l.287-319): the group is a string `group` key on each member, no group row; atoms are recomputed by contiguity. It flags for spec 3: (a) group names must be unique per page, or the validator must enforce it, if atoms are keyed by name; (b) a content block in a group counts toward atom size but not question count, so "same number of questions per item" must count questions only; (c) `ServedPaper` has no group info and `served_path` tolerates an id absent from `children`, but `has_missing_served_items` and `served_child_ids` use only `pages[].children`, so a dropped (undrawn) question must not be reported as "missing"; (d) the paper does not record atoms, so the educator/audit story (spec 4) may want a `groups` key; (e) `schema.py`, `validate.py`, `content_save.py` and migrations collide with spec 2's, so run in series (spec 2 is done, so migration numbers continue from 0013).
- Spec 2 answers: groups are allowed on an unshuffled page precisely so pools can draw them; nested groups stay a validation error. Spec 2 research notes this combination (group on unshuffled page) is untested prior art outside QTI's invisible sections.
- Spec 2 QA (`3. done/.../sacaa-compliance-2-shuffle/qa_report.md`): reload, Back/Forward, resume and results all kept the stored order; results labels follow the served position; a retake was NOT exercised for the shuffled quiz because a pass blocks a retake (Test 3-resit skipped). Consequence for this spec: "a retake draws afresh" has never been exercised end to end in this repo. The QA plan needs a failing learner who retakes (the "Mid course Quiz" at an 80% pass mark allowed a retry, test 5). Also known QA bugs of that run (long form page scrolls the document; demo SVG placeholder caption) are fixed, but they show demo pictures and long grouped pages are where visual bugs appear; a pool demo with stimulus groups will hit the same page type.
- Results page labels: spec 2 switched incorrect-answer labels to the served position. A draw adds a second reason they must not use `question_number` (authored number) since numbers of drawn items would have gaps.

### 1.3 Corporate readiness

`spec_dd/corporate-readiness/README.md` l.61 groups `compliance-form-randomization` with `file-scanning` and `content_snapshots` as paused items. It is background only.

## 2. Elsewhere: what happened, and the lesson

### 2.1 Draw count larger than the bank (or bank shrinks after publish)

- Moodle raises the error `notenoughrandomquestions` when a category cannot satisfy a random slot, including when the other questions in the quiz already use up the category, and it has surfaced in preview. A 4.3 bug (MDL-79708) threw it for an empty parent category with non-empty sub-categories. (w) <https://docs.moodle.org/502/en/error/quiz/notenoughrandomquestions>, <https://tracker-old.moodle.org/browse/MDL-79708>
- Canvas requires pick count <= bank size. (w) <https://athelp.sfsu.edu/hc/en-us/articles/10407262465043>
- Lesson: validate N <= items at authoring time (already settled) and re-validate on every content save, since a later edit can shrink the page. At draw time, a page whose item count fell below N must fail loudly, not silently serve fewer questions (which would make `max_score` vary). Note FLS never deletes a question on save (`research_question_model.md` l.35), so shrinkage comes from the author removing a question and the validator or a draw-time check catching it. (i)

### 2.2 Small pools make consecutive attempts near-identical

- MDL-27573: with a three-question category, consecutive attempts look alike. (w, search summary) <https://tracker-old.moodle.org/browse/MDL-27573>
- Lesson: "a different paper on retake" is only as strong as the pool/N ratio, and a draw of all items is just a reorder. Authoring guidance should state a suggested pool-to-N ratio, and the author plugin should say a retake may repeat questions. FLS has no "avoid last attempt's questions" rule and the idea does not ask for one. (i)

### 2.3 Duplicates across draws

- Open edX: several randomized blocks from the same library cannot guarantee a learner does not receive the same problem twice; nothing tracks what was seen outside one block. (w) <https://openedx.atlassian.net/wiki/spaces/OEPM/pages/3945234827/Randomized+Content+-+Current+State+Gaps+and+Opportunities>
- Moodle tests that a random slot does not duplicate a fixed question already in the quiz (MDLQA-19428). (w, search summary) <https://tracker-old.moodle.org/browse/MDLQA-19428>
- Lesson: FLS avoids this because the pool is one page's own items, so pages cannot overlap. State in the spec that a question lives on exactly one page and so can never be drawn twice in a paper. (i)

### 2.4 Stored selection vs live pool; editing the pool after attempts exist

- Open edX design material: a learner's existing selection stays fixed while pool and `max_count` are unchanged; lowering `max_count` randomly removes previously selected blocks; Open edX random blocks have no concept of attempts, so assigned problems never change for a learner (so a retake does not redraw there). (w) <https://openedx.atlassian.net/wiki/x/coEn6w>, <https://discuss.openedx.org/t/get-blocks-shown-to-the-user-in-a-randomised-librarycontentblock/14685>, <https://openedx.atlassian.net/wiki/spaces/COMM/pages/3858661405/Bugs+from+Content+Libraries+V1>
- Canvas: a question group's questions are copied into the quiz; edits to bank questions do not flow into existing quizzes, and a group must be created a certain way to be editable and regradable after students sat. (w) <https://canvas.ubc.ca/courses/66705/modules/items/2427564>, <https://richland.instructure.com/courses/1647246/modules/items/18365477>
- Canvas `question_points` applies one point value per group, so mixed-difficulty banks get equal weights. (w) <https://canvas.emory.edu/doc/api/quiz_question_groups.html>
- Lesson: FLS stores explicit question ids in the served paper, so a published paper does not change if `draw` is edited later; the spec must say what an in-flight attempt does when the author changes N or removes a drawn question (spec 1's rule: missing items skipped on read, ids never dropped from the paper). Open edX's "randomly remove selections when max drops" is the alternative to avoid. (i)

### 2.5 Resume redraws

Covered already: Storyline/Rise redraws on resume (`research_question_bank_patterns.md` s1.3; shuffle prior art s2.2). Moodle persists the resolved question per slot and redraws only on a new attempt. FLS's write-once served paper is the guard; the draw must happen inside `build_served_paper`, never at render time.

### 2.6 Scoring when subsets differ

Covered in `research_question_bank_patterns.md` s3: fixed count draws, ex-ante vs ex-post fairness (arXiv:2304.06254), NUS Pattern A variant pools. Moodle's random questions are always worth 1 mark regardless of source marks, a documented limitation (<https://docs.moodle.org/502/en/Random_question_type>); FLS scores one point per question, so the same holds and the "same size per item" rule keeps `max_score` fixed.

### 2.7 Stimulus questions in banks

- Canvas New Quizzes: stimulus (passage-linked) questions cannot go in an Item Bank and a stimulus's attached questions do not travel with it (w-search per shuffle prior art s2.4, <https://celt.iastate.edu/learning-teaching-technology/new-quizzes-canvas>). Moodle has no stimulus container; a Description question is drawn alone.
- Only QTI (nested `assessmentSection` inside a selecting section) cleanly draws a group whole. (w) <https://www.imsglobal.org/question/qtiv2p2/imsqti_v2p2_impl.html>
- Lesson: FLS's group-as-draw-unit is ahead of Canvas and Moodle; there is no field-tested behaviour to copy. The "equal size per item" rule is FLS's own answer to the weight problem keyed groups create (Moodle/Canvas avoid the problem by not supporting it). Test a group drawn whole, never split, never alone, with the stimulus before its questions. (i)

## 3. What this changes in the spec

1. Do not build `QuestionPool` or `QuizAttemptDraw`; write the draw into the served paper inside `build_served_paper`, using a new RNG scope for the draw, before shuffle, over the same units `shuffle_units` returns.
2. Reuse `shuffle_units`; decide group-name uniqueness per page and validate it (spec 2 flagged it). Count questions, not children, for the equal-size rule.
3. Check every reader of the full page list, not only scoring: `score_quiz`/`compute_quiz_scores`, `get_incorrect_quiz_answers`, the results-page outdated-score check, results labels (use served position), `has_missing_served_items` / `served_child_ids` (an undrawn question must not read as missing), admin `answer_groups` ("not asked" rows), the cohort report column per question, the educator content preview (settled: one line), and exports.
4. Validate on every content save, not only at first import: N >= 1, N <= items, QUIZ only, no `when`, no loose content, equal question counts per item. At draw time fail loudly if N > items.
5. Decide what an in-flight attempt does when N or the pool changes after the attempt started (stored ids win, per spec 1).
6. QA must include a failing learner who retakes and receives a fresh draw (never exercised for shuffle) and a resume/reload on a drawn paper that shows identical items.
7. Authoring docs: pool-to-N guidance (small pools make retakes near-identical); retakes may repeat questions; no cross-question references ("see question 3") in drawn forms, which also break under shuffle (shuffle prior art s2.6).

## Reference URLs

- <https://docs.moodle.org/502/en/error/quiz/notenoughrandomquestions>
- <https://tracker-old.moodle.org/browse/MDL-79708>
- <https://tracker-old.moodle.org/browse/MDL-27573>
- <https://tracker-old.moodle.org/browse/MDLQA-19428>
- <https://docs.moodle.org/502/en/Random_question_type>
- <https://athelp.sfsu.edu/hc/en-us/articles/10407262465043>
- <https://canvas.ubc.ca/courses/66705/modules/items/2427564>
- <https://richland.instructure.com/courses/1647246/modules/items/18365477>
- <https://canvas.emory.edu/doc/api/quiz_question_groups.html>
- <https://celt.iastate.edu/learning-teaching-technology/new-quizzes-canvas>
- <https://openedx.atlassian.net/wiki/spaces/OEPM/pages/3945234827/Randomized+Content+-+Current+State+Gaps+and+Opportunities>
- <https://openedx.atlassian.net/wiki/x/coEn6w>
- <https://openedx.atlassian.net/wiki/spaces/COMM/pages/3858661405/Bugs+from+Content+Libraries+V1>
- <https://discuss.openedx.org/t/get-blocks-shown-to-the-user-in-a-randomised-librarycontentblock/14685>
- <https://www.imsglobal.org/question/qtiv2p2/imsqti_v2p2_impl.html>
- Repo: `spec_dd/3. done/2026-11-21_11:09_sacaa-compliance-2-shuffle/` (`research_prior_art.md`, `research_codebase.md` s10, `research_best_practices.md`, `2. plan.md`, `qa_report.md`), `spec_dd/3. done/2026-11-20_10:30_sacaa-compliance-1-served-paper-record/research_prior_art.md`, `spec_dd/3. done/2026-11-18_15:43_learner-interface-features-1-question-sections/research_prior_art.md`, `spec_dd/1. next/learner-interface-features/research_question_model.md`, `spec_dd/1. next/sacaa-compliance/research_form_engine_seams.md`, `freedom_ls/form_engine/served_paper.py`.

status: ok
reason: in-repo history and web incidents covered; web items are search summaries, flagged (w)
