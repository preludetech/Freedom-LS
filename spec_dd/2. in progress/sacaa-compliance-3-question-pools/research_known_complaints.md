# Research: known complaints about random question pools / draws

Scope: what learners, authors, educators and auditors complain about in Moodle, Canvas, Blackboard and Open edX. Articulate was not searched (no sources gathered). Evidence is from help pages and forum threads found with a few web searches, so treat it as indicative, not exhaustive. Terms are those of the source system. FLS terms are used where I compare.

## Complaints by system

### Moodle
- Same questions repeat across retakes. Forum threads report unlimited-attempt quizzes giving the same random set again. Moodle's docs say retakes should differ but a small bank may repeat. A bank of 50 with 10 drawn will overlap between attempts. A feature request (MDL-6340) asks for unseen questions on retakes. https://moodle.org/mod/forum/discuss.php?d=257898 , https://moodle.org/mod/forum/discuss.php?d=236679 , https://tracker-old.moodle.org/browse/MDL-6340 , https://docs.moodle.org/503/en/Random_question_type
- Duplicate questions in the pool. Two copies of the same question can both be drawn into one attempt, because Moodle cannot tell they are identical. Authors see it as the system repeating a question. https://moodle.org/mod/forum/discuss.php?d=257898 (thread cluster above)
- Difficulty variance. No native fix. Teachers benchmark by hand. Random slots are always worth 1 mark, which hurts when questions differ in weight. https://docs.moodle.org/503/en/Random_question_type
- Authoring error with too-small pools. "Not enough questions" appears when the random count exceeds the unused questions in the category. https://docs.moodle.org/404/en/Quiz_FAQ , https://docs.moodle.org/503/en/Editing_a_quiz
- Editing after attempts. The FAQ's advice is to delete all attempts and then edit. Editing a shared question can change it in other quizzes. https://docs.moodle.org/404/en/Quiz_FAQ
- Draw timing. The draw happens when the attempt starts, with a fresh selection per attempt. That is the same model as the idea. https://docs.moodle.org/503/en/Editing_a_quiz

### Canvas (New Quizzes)
- Regrading after bank edits. A regrade applies to every student who got that question, and only after all students have submitted. Cornell advises reading the regrade guide before editing a started quiz. https://infocanvas.upenn.edu/instructors/new-quizzes/ , https://celt.iastate.edu/learning-teaching-technology/new-quizzes-canvas , https://learn.canvas.cornell.edu/getting-started-with-canvas-new-quizzes
- Shared banks. One instructor's bank edit reaches other instructors' quizzes. https://celt.iastate.edu/learning-teaching-technology/new-quizzes-canvas
- Deleted banks. Random-draw groups tied to the bank stop working, while directly added questions stay. https://learn.canvas.cornell.edu/getting-started-with-canvas-new-quizzes
- Stimulus questions in random draws are a recurring request. See https://community.instructure.com/en/discussion/488646/randomly-select-a-stimulus-question (title only; I did not read the thread).
- Different students see different questions. This is stated as expected behaviour, with the count set per draw. https://teaching.usask.ca/articles/2025-03-04-randomizing-canvas-quizzes-using-item-banks.php

### Blackboard
- Unfair difficulty. A block mixing question types gives one student a harder paper. Points are the same for every question in a block, so authors cannot weight within it. The advice is to build pools of similar difficulty and use one pool or block per topic. https://help.blackboard.com/Learn/Instructor/Original/Tests_Pools_Surveys/Reuse_Questions/Random_Block , https://www.utep.edu/extendeduniversity/cid/faculty-training/tutorials/assessments-and-assignments/creating-random-blocks.html , https://elearning.uq.edu.au/staff-guides-original/tests-and-pools/overview-randomisation-original
- Advice to draw fewer questions than the pool holds, or the paper hardly varies. Same UQ and Blackboard pages.

### Open edX (Randomized Content Block)
- Learner confusion. Learners were not told they had randomised content, and noticed in discussion forums that they saw different problems. https://openedx.atlassian.net/wiki/spaces/OEPM/pages/3945234802/Randomized+Content
- Stability. The draw is made on first visit and the same set is shown on later visits, unless the block is updated in Studio. A later update to the block can therefore change what a learner sees. https://groups.google.com/g/edx-code/c/-VanoiKyv0o
- Staff must adjust grades or reset attempts per assigned problem. https://edx.readthedocs.io/projects/edx-partner-course-staff/en/latest/exercises_tools/randomized_content_blocks.html
- Limited to problem types, not HTML or video. The same wiki page as above.
- Easily confused with per-problem Python randomisation ("On Reset"). https://docs.openedx.org/en/ulmo/educators/references/course_development/advanced_problem_editor.html

### Not found
- Results pages leaking unseen questions: no complaint found in any system. It is probably a design risk rather than a reported one, so keep it as a test case in the spec.
- Auditor complaints: none found in the LMS forums. The audit need (which paper did this learner get) comes from `research_sacaa_requirements.md`.

## Mapping to the idea's settled decisions

| Complaint | Status | Where |
|---|---|---|
| Same questions across retakes | Partly addressed. A retake draws afresh, but with a small pool, overlap is inevitable. No "unseen first" rule, and none is wanted (out of scope). | Open: authoring guidance on pool size vs N |
| Duplicate question in one draw | The page holds distinct items, so no within-draw repeats. Near-duplicate authored questions are not detected. | Open, low |
| Unfair difficulty variance | Acknowledged. Uniform draw, authoring guidance only, tiers out of scope. Same position as Blackboard's "similar difficulty" advice. | Settled as guidance; a known residual risk |
| Different weights in a draw | Addressed. Every drawn item has the same question count, so `max_score` is fixed. Mixed pages are rejected. | Settled |
| Questions change on resume or reload | Addressed. Draw at attempt start, written to the served paper. | Settled |
| Scores change when the pool is edited | Partly addressed. The served paper from spec 1 fixes the question set, and scoring reads it. Question text edits after the draw are out of scope (`content_snapshots`). Deleting a drawn question after attempts began is not covered. | Open |
| Results pages leak unseen questions | Addressed (never shown on page flow, results or incorrect list; no pool browsing). | Settled |
| Confusing totals | Addressed. Fixed denominator for every attempt and no "outdated score" flag. | Settled |
| Authoring errors, pool too small | Addressed. N must be at least 1 and at most the item count. | Settled |
| Stimulus with random draw | Addressed. Groups are drawn whole and loose content on a drawing page is rejected (answers.md). | Settled |
| Conditional logic and draws | Addressed. `when` is banned on drawing forms. | Settled |
| Learners unaware of randomisation (Open edX) | Open. The idea says nothing about telling the learner that their paper is a draw. Open edX's wiki records the confusion. | Open |
| Educator expects to see all questions in preview | Addressed. One line shows pool size and N (answers.md). | Settled |
| Shared banks, deleted banks, cross-quiz edit leakage (Canvas, Moodle) | Avoided by design. The page is the pool, and no shared banks exist. | Settled (out of scope) |
| Per-student regrade or reset after a question error | Open. Not in this spec. The attempt-review spec may cover staff handling of a bad question. | Open |
| Auditor needs to reconstruct the paper | Addressed by spec 1's record. The per-attempt view belongs to spec 4. | Elsewhere |

## Suggested items for the spec to decide or state
1. A pre-start or in-quiz line telling learners their paper is drawn from a larger set (Open edX confusion). Low cost, decide yes or no.
2. Authoring guidance in `fls-content`: keep N well below the item count so retakes differ, keep pool items of equal difficulty, and avoid near-duplicate questions.
3. What a content-save does when a drawing page's items are removed or the page falls below N after learners have attempts. Validation covers N versus item count at save. Existing served papers should remain readable. State this explicitly.
4. A test that results and incorrect-answer views never show undrawn questions, since this complaint class has no public evidence and is easy to regress.

status: ok
