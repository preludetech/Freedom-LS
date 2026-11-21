# Research: UX patterns for question pools / random draws

Scope: authoring a draw in a file (`draw: N` on a page header), the learner taking and reviewing a
drawn quiz, and the educator preview line. Terms for other systems are theirs; FLS terms are used
for FLS. Evidence is thin in places; each claim is marked as sourced or as inference.

## Sourced facts from other systems

- **Moodle** ("Random question type", https://docs.moodle.org/500/en/Random_question_type):
  a random slot inserts a randomly chosen question from a category. Different students get different
  selections, and with multiple attempts "each attempt is likely to contain a new selection". A
  random slot always carries a mark of 1, so the denominator is set by the slot, not by whichever
  question was drawn. A question cannot repeat inside an attempt, and asking for more than the
  category holds raises an error when the student attempts the quiz (the error surfaces late, at
  attempt time; FLS should fail at validation instead). Source also
  https://www.waikato.ac.nz/students/eresources/moodle/quizzes/add-random-questions.
  A Moodle tracker item (https://tracker-old.moodle.org/browse/MDL-27573) reports the older draw
  clumped, so consecutive attempts could look alike: draw per attempt, not per learner or per day.
- **Canvas New Quizzes** (item banks; e.g. https://teaching.usask.ca/articles/2025-03-04-randomizing-canvas-quizzes-using-item-banks.php,
  https://www.usu.edu/teach/help-topics/canvas/new-quizzes-question-banks,
  https://elearning.ufl.edu/instructor-help/new-quizzes/overview/): the author picks a bank and
  types "number of questions to draw"; with multiple attempts the student gets a different set each
  time; every question in one draw must be worth the same points; the draw uses the whole bank, so
  each pool needs its own bank. The guides tell authors to "Preview the quiz" afterwards, and do
  not say whether the instructor preview shows a drawn or fixed set.
- **PrairieLearn** (https://docs.prairielearn.com/assessment/configuration/,
  https://prairielearn.readthedocs.io/en/latest/assessment/): assessments are a list of zones in a
  JSON file; a zone entry carries `numberChoose` (integer, min 0) alongside a list of
  `alternatives`. This is the closest precedent for "draw count written in the file next to the
  candidates": the count sits on the grouping (zone) not on a named pool, as `draw: N` sits on the
  page header. I did not find docs for how `numberChoose` interacts with alternatives; not relied on.
- No source found for review-page numbering of drawn quizzes in Moodle, Canvas or Articulate. The
  numbering guidance below is inference from the settled design, flagged as such.

## (a) Authoring a draw in a text/markdown/YAML file

- **One integer next to the candidates.** The pattern across PrairieLearn (`numberChoose`) and Canvas
  (a number box beside the bank) is a single count on the grouping. `draw: N` on the page header
  matches. Avoid a nested object (`draw: {count: N}`) until a second knob exists.
- **Name the key for the effect, not the mechanism.** `draw` reads as "draw N of this page"; it does
  not need a unit word. Authors should not have to read the schema: put one worked example in the
  `fls-content` plugin showing a two-subject page pair (inference from the idea's own goal).
- **Fail at save, with the numbers in the message.** Moodle's late failure (at attempt time) is the
  anti-pattern. Validation messages should name the page and both numbers, e.g. "Page 'Meteorology':
  draw 15 but the page has 12 items", "Page 'Air Law': items mix single questions and groups of
  different sizes", "Page 'X': content block outside a group on a drawing page", "draw on a
  non-QUIZ form". Each tells the author the fix. (inference)
- **State the unit once.** N counts items (a single question or a whole group). Where a page uses
  groups, the author guidance should say N counts groups, and the served question count is N times
  the group size; show that arithmetic in the example. (inference)
- **Equal worth is the shared rule.** Canvas requires equal points per drawn question and Moodle pins
  1 mark per slot; FLS's same-size-items rule serves the same end (common denominator). Say so in
  the author docs so the mixed-page rejection reads as a reason, not an arbitrary restriction.
- **Pool-homogeneity guidance** (difficulty) is documentation only, per the idea; one sentence.

## (b) Learner taking and reviewing a drawn quiz

Inference from the settled design, since no source covers it directly:

- **The learner's world is the served paper only.** Everything a learner sees (page flow, progress,
  results, incorrect-answers list) is computed from the served set. No wording such as "12 questions
  in the pool" or "5 of 12" may appear in learner UI: it leaks the pool. Say "Question 3 of 5".
- **Progress and numbering count served questions.** Number drawn questions 1..N within the paper,
  never by their position in the bank. Authored positions leak the bank size and make gaps (1, 4,
  9). With several drawing pages, number continuously across the paper, or per page, consistent with
  how undrawn pages number today; the denominator is the total served count, identical every
  attempt (matching Moodle's fixed slot mark and Canvas's equal-points rule).
- **Results page and incorrect-answers list** list only served items, in served order, with the same
  numbers the learner saw during the attempt, so "question 3" means the same thing in both places.
- **The "outdated score" warning must not fire** for a drawn attempt: the comparison is against the
  served set (already in the idea). A false "your score is out of date" banner would be the likeliest
  visible bug.
- **Retake shows a new paper.** Moodle ("each attempt is likely to contain a new selection") and
  Canvas ("different set ... each time") both frame it this way. Because the draw is random, a
  retake can overlap or even repeat; that is expected. Do not promise "all new questions" in UI
  copy; say nothing, or say "a new set of questions". Overlap is more likely when N is close to the
  page size (a draw of all items only reorders), which is a documentation note for authors, not a UI
  state. (inference)
- **Old attempts stay as they were.** Reviewing a past attempt shows that attempt's paper, not the
  latest retake's; this follows from persisting at start and is the one place a learner can compare
  papers across attempts, which is acceptable because they are their own questions.
- **Resume and back-navigation show the same questions** (draw once), so a reload never reshuffles.
  The learner should be unable to tell a drawn quiz from a fixed one except by the absence of
  questions.

## (c) Educator preview of a drawing page

- **One line, factual, on the page's heading in the content preview:** "Draws 5 of 12 questions per
  attempt" (the line named in the brief). Use the unit that matches the page: for a page of groups,
  "Draws 2 of 6 groups (4 questions) per attempt" so the served question count is visible. (inference)
- **Keep the full path visible.** The preview today shows every question; the line explains why a
  learner sees fewer. Do not hide undrawn questions from educators, the preview is for reviewing the
  bank. Canvas guidance only says "Preview the quiz"; it does not document a drawn preview, so there
  is no precedent to copy and the line is the minimum honest signal.
- **Non-drawing pages show nothing extra.** Absence of the line means "served whole", consistent with
  opt-in.
- **Do not show the pool to learners through the same component.** The line is educator-only; check
  that the learner path cannot reach the same template.
- Totals: if a quiz-level summary exists, show total served questions (the sum across pages) next to
  the pass mark, because that is the denominator learners are scored on. (inference; only if such a
  summary already exists, do not add one for this.)

## Takeaways for the spec

1. Validate everything at save with messages naming page and numbers (Moodle's attempt-time error is
   the counter-example).
2. Number and count served questions only, everywhere a learner looks; never expose the pool size.
3. Fixed denominator across attempts (Moodle 1 mark/slot, Canvas equal points) matches the
   same-size-items rule; say this in the author docs.
4. Educator preview gets one line; learner UI gets nothing.
5. Retake copy must not promise a disjoint set.

status: ok
