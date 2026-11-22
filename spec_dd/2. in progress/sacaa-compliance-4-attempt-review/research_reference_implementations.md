# Research: reference implementations of per-attempt review and export

Question: how do Moodle, Canvas, Open edX, Blackboard and TalentLMS let staff review one attempt
at a randomised quiz, and how do they export it? Findings are limited to what affects this spec.

## 1. Per-attempt review page

**Moodle** (the closest match, and the most complete).
- Staff reach `mod/quiz/review.php?attempt=<id>` from the Grades report, where each attempt's
  score links to its review. Staff see the attempt "as the student saw it". Source:
  https://docs.moodle.org/en/Quiz_grades_report
- A summary table sits at the top: user, Status, Started, Completed, Duration ("Time taken"),
  Marks x/y, Grade (with percentage), Feedback. MDL-80900 reworked these labels in 4.3/4.4 to
  "Started", "Completed" and "Duration". Source: https://tracker-old.moodle.org/browse/MDL-80900
  (found in search results; the page now returns 404).
- The body is the questions in **slot order**, where a slot is a position on the paper served.
  Each question shows its number, status (Correct / Incorrect / Partially correct), "Mark x out
  of y", the options **in the shuffled order stored for that attempt**, the learner's choice and
  the right answer. The order lives with the attempt's first step (the `_order` step data) and is
  never re-derived. For a random question, the slot holds the question drawn for that attempt.
  A question that was not drawn does not appear. Staff also get a response history per question.
  (From Moodle's question engine design; these details were not re-fetched for this note.)
- Every review writes an event: `\mod_quiz\event\attempt_reviewed`, with crud `r`, `objectid` =
  the attempt, `userid` = the reviewer and `relateduserid` = the attempt owner. This is a direct
  precedent for the idea's open question on auditing a view. Source:
  https://github.com/moodle/moodle/blob/main/public/mod/quiz/classes/event/attempt_reviewed.php
- Access: `mod/quiz:viewreports` plus group visibility of the attempt's owner. No permission
  exists just for reviewing, which matches this spec reusing `VIEW_LEARNER` and
  `learners_visible_to`.

**Canvas.** Classic and New Quizzes open past attempts from the SpeedGrader or "Moderate this quiz"
sidebar, one attempt at a time, as the student saw it. Bank-drawn questions show the question the
student got. Source: https://support.uclaextension.edu/hc/en-us/articles/40677867578644-View-and-Export-Quiz-Results

**Open edX.** Has no attempt document. Staff see a learner's randomised `library_content` draw
either by masquerading as that learner or through per-problem "student state". The draw is stored
per learner per block (the selected children), not per attempt. This shows what to avoid: an
auditor cannot read one paper.

**Blackboard.** Grade Center → View Attempt shows one attempt with questions from random blocks
and pools as served, with points per question.

**TalentLMS.** The test report has a "View submission" link per learner per attempt and keeps at
most 7 attempts per user. The link opens **without logging in**. Source:
https://help.talentlms.com/hc/en-us/articles/9652242218396-How-to-export-test-reports
FLS must not copy that. Our page is permission-gated, and the spec should say so.

**What this means for the spec**
- Every reference shows the summary first (times, attempt number, score, percentage, pass/fail),
  then the paper in served order. This matches the user's decision: the quick view carries the
  summary and the instance page carries summary plus paper.
- "Served order and only what was served" is the norm (Moodle slots, Canvas, Blackboard). The
  idea's rule of no undrawn questions in the review matches common practice. The admin's
  `answer_groups` (`freedom_ls/form_engine/queries.py:118`) does not match it: it walks
  `form.pages.all()` in authored order and prints undrawn questions as "not asked".
- Options are shown in the order stored per attempt. In FLS that order is
  `FormProgress.served_paper` (`freedom_ls/form_engine/models.py:366`), read through
  `sitting_path()` → `served_path()` (`freedom_ls/form_engine/conditions.py:373`). The review
  should read the option order from there, not from `FormOption.order`.
- Precedent for auditing a read is strong (Moodle `attempt_reviewed`), so a `...viewed` audit
  entry has an outside reference. The spec still has to fit it to the audit log's own rules.
- Only finished attempts are reviewable from the attempts table. Moodle shows in-progress attempts
  too, but the user chose completed only, and the existing table
  (`freedom_ls/educator_interface/templates/educator_interface/panels/learner_courses.html:37-66`)
  already lists completed attempts with Attempt, Completed, Score, Percentage, Pass mark and
  Result. Neither "Started" nor duration appears there. The review summary needs `start_time`,
  which the table does not show.

## 2. Export of randomised attempts

There are two layouts in the wild.

| System | Column keyed by | Undrawn question | Order served in file |
|---|---|---|---|
| Moodle Responses report | **slot (position)**: `question<slot>`, `response<slot>`, `right<slot>`, headers "Question N" / "Response N" / "Right answer N" | absent (a slot always holds something) | implicit: the columns are the served order; the "Question N" text column says which question was in the slot |
| Canvas Student Analysis CSV | question id (one column pair per question) | blank cell | not recorded |
| Blackboard "Download results" | "By User" (one row per attempt, question columns) or "By Question and User" (one row per attempt × question) | depends on layout; long form has no row | long form lists the rows per attempt |
| TalentLMS Excel export | per question, correct/incorrect per user | not documented | not recorded |

Sources: Moodle responses report code
https://github.com/moodle/moodle/blob/main/public/mod/quiz/report/responses/report.php (columns
built per significant question, keyed by slot, labelled with `displaynumber`); Moodle docs
https://docs.moodle.org/405/en/Quiz_responses_report (shows the question text "helpful when the
question is randomised"); Blackboard
https://sites.reading.ac.uk/tel-support/2018/07/27/blackboard-downloading-blackboard-test-results/
and https://help.blackboard.com/node/42716; Canvas
https://community.canvaslms.com/t5/Question-Forum/Quiz-Student-Analysis-CSV-file-what-do-the-columns-mean/m-p/438443

**What this means for the spec**
- FLS keeps authored, question-keyed columns with "Not asked" (Canvas style), as the idea
  settles. None of the references adds a served-order column to that layout. Moodle gets served
  order by keying columns by position instead. The cleanest fit for FLS's present shape is
  **one served-order cell per attempt row**: the question identifiers in order, joined with a
  separator, and per page if pages shuffle. A second sheet would be the Blackboard long form
  (attempt × served position → question, options shown). That is the only layout that also
  records **option order**, which a one-cell list does not carry readably. The spec must decide
  whether option order goes in the file. Moodle's export does not include it either: option
  order stays in the attempt record and its review page.
- **The seed alone does not reproduce the paper.** Every reference stores the realised order
  explicitly, not a seed. FLS's `served_paper.py` (`_scope_rng(seed, scope)`, `new_seed`) derives
  the order from seed + form state + code. A later content edit, or a change to the shuffle code,
  produces a different paper from the same seed. The export should carry the explicit served
  order and treat the seed as a secondary column, written as a plain integer.
- **No quiz export exists today.** `freedom_ls/form_engine/exports.py` (`answer_columns`,
  `off_path_question_ids`, `answer_cell`) is used only by
  `freedom_ls/course_applications/resources.py` (`CourseApplicationResource`). No quiz-attempt
  export calls it: `freedom_ls/reports/gather.py` builds the cohort report from `FormProgress`
  without per-answer columns. So "the existing form export gains the served order" lands in the
  course-application export, which out-of-scope bars from QUIZ forms. The spec must either name
  a new quiz-attempt export, built on `exports.py` and reached from somewhere, or restate the
  export scope. Every reference ships a per-quiz export of attempts (Moodle Responses/Grades
  download, Canvas Student Analysis, Blackboard Download Results, TalentLMS Export in Excel), and
  SACAA research (`spec_dd/1. next/sacaa-compliance/research_sacaa_requirements.md:81`) expects
  records "exportable (PDF/CSV) for inspectors".
- `off_path_question_ids` already subtracts `sitting_path(...).question_ids`, so undrawn
  questions already export as "Not asked" once `served_paper` exists. Only the order and seed
  columns are new.

## 3. Placement and the quick view

- The references put the review link on the attempt's score or row in a per-quiz attempts list.
  That matches linking from the Courses-tab attempts table.
- That table is a plain `<c-panel-table>`, not a panel-framework data table. The quick view and
  row link are panel-framework data-table features (`Skill(fls-dev:panel-framework)`). The spec
  must say whether the attempts table becomes a data table, or how a quick view triggers from a
  plain panel table.

status: ok
