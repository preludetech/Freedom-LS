# Research: known complaints about randomised attempts, attempt records and rescoring after edits

Topic: what learners, educators and auditors complain about in other LMSs, and what that changes in
this spec. Builds on `research_form_engine_seams.md`, `research_sacaa_requirements.md` and
`research_randomization_ux_integrity.md`; it does not repeat them.

Labels: (w) web-sourced, cited; (c) read from FLS code at HEAD 53fb74dfe; (i) inference.

## 1. Complaints, grouped by who raises them

### Learners

1. **Review shows a different order from the one sat.** Moodle long re-shuffled options on review
   and feedback pages "by design", and students were confused that feedback did not match the
   attempt (w, [Moodle forum d=6706](https://moodle.org/mod/forum/discuss.php?d=6706)). A college
   guide still warns that shuffle-within-questions reorders answers each time the quiz is opened,
   so a review can differ from what was seen
   ([Selkirk College](https://selkirkcollege.atlassian.net/wiki/spaces/KB/pages/6928010/Layout+Question+Behaviour+Moodle+Quiz)).
   Brightspace users ask why the review order differs from the sitting; the answer points at a
   separate event log, not the review itself
   ([D2L guides, search summary](https://www.torontomu.ca/courses/instructors/tutorials/quizzes/quiz-manage-questions)).
2. **Resume lands on a different question under the same number.** Articulate Rise/Storyline
   threads report that a resumed randomised quiz showed a different question at the same position
   (w, [Articulate community](https://community.articulate.com/discussions/discuss/rise-quiz---resume-problem-when-randomize-question-order/1225289);
   page blocks direct fetch, seen via search summary). Root cause: order derived per session, not
   stored.
3. **Navigation breaks under sequential or non-default order.** Moodle app regression MOBILE-4350
   broke sequential-navigation quizzes; CVE-2022-40208 let students bypass sequential navigation
   through web services (w, [MOBILE-4350](https://tracker-old.moodle.org/browse/MOBILE-4350),
   [CVE-2022-40208](https://acunetix.com/vulnerabilities/web/moodle-other-vulnerability-cve-2022-40208)).
   Expected behaviour stated in [MDL-11047](https://tracker-old.moodle.org/browse/MDL-11047): leave
   and come back "to the same place".
4. **Score denominator differs between learners or from the quiz total.** Storyline/Captivate
   users drawing from banks see totals computed from every scored object in the course, or from
   whatever the learner happened to reach (950/1200 instead of 950/2000) (w,
   [Articulate thread](https://community.articulate.com/discussions/discuss/multiple-choice-quiz-score-displaying-incorrectly-in-lms/1271964),
   [Adobe Captivate blog](https://elearning.adobe.com/2019/02/captivates-quizzes-3-attempts-scores/)).
   Canvas question groups that pick more than exist give "off" points
   ([Canvas community](https://community.canvaslms.com/t5/Canvas-Question-Forum/Quiz-Points-Issue-When-Using-Question-Groups/m-p/574177)).
5. **Grades change silently after a regrade.** Canvas's regrade option can reduce scores; guides
   tell instructors to warn students (w,
   [Manchester](https://www.elearning.fse.manchester.ac.uk/getting-started-with-canvas/editing-quizzes-post-submission/),
   [Monash](https://www.monash.edu/learning-teaching/TeachHQ/moodle/quiz/how-to/regrade-a-quiz)).

### Educators

6. **Editing after attempts gives inconsistent marking.** In Canvas, learners who submitted
   before an edit are marked against the old version, those after against the new one, which
   "creates inconsistencies in grading" (w, [Manchester](https://www.elearning.fse.manchester.ac.uk/getting-started-with-canvas/editing-quizzes-post-submission/)).
   Learners mid-attempt keep the version they started with
   ([CSU Chico](https://support.csuchico.edu/TDClient/1984/Portal/KB/ArticleDet?ID=113553)).
7. **Regrade covers some edits and not others.** Canvas regrade handles answer-key changes on MC,
   MA and T/F only. Changing points, adding or removing questions, or editing text does not
   trigger it, and gradebook totals sometimes fail to update (w,
   [CSU Chico regrade KB](https://support.csuchico.edu/TDClient/1984/Portal/KB/ArticleDet?ID=114626),
   [UBC](https://canvas.ubc.ca/courses/66705/modules/items/2437335)).
8. **Adding or removing an option destroys past answers.** Moodle: changing the number of choices
   in an attempted MC question deletes the responses; regrading after adding a choice showed every
   choice as "deleted after the attempt was started" (MDL-74752). Fix offered: revert to the
   version the students saw (w,
   [Moodle forum d=434465](https://moodle.org/mod/forum/discuss.php?d=434465),
   [Strathclyde notes](https://universityofstrathclyde.atlassian.net/wiki/x/xRRv),
   [MDL-74752](https://tracker-old.moodle.org/browse/MDL-74752)).
9. **The platforms lock editing instead.** Moodle blocks adding or removing questions once any
   attempt exists; the workaround is to set the bad question's mark to 0 (w,
   [Moodle Quiz FAQ](https://docs.moodle.org/401/en/Quiz_FAQ)). Moodle 4.0+ pins each attempt to
   the question version it started with
   ([Moodle forum d=438090](https://moodle.org/mod/forum/discuss.php?d=438090)). Canvas New
   Quizzes only lets you edit a copy once a question has answers
   ([Canvas community](https://community.canvaslms.com/t5/New-Quizzes-Discussion/Will-edited-question-in-New-Quizzes-show-up-in-a-second-attempt/m-p/630723)).

### Auditors and record keepers

10. **A deleted item leaves a hole, or a crash, in the record.** Moodle review shows "This
    question has been deleted. Please contact your teacher" while the stored score survives;
    some deleted questions showed no marks at all. Removed choices show "[Deleted choice]"
    (MDL-49368). Other reports crash review with "Can not find data record" once the owning quiz
    or bank is gone (w, [Moodle forum d=87799](https://moodle.org/mod/forum/discuss.php?d=87799),
    [MDL-49368](https://tracker-old.moodle.org/browse/MDL-49368),
    [MDL-51071](https://tracker-old.moodle.org/browse/MDL-51071),
    [MDL-84591](https://tracker-old.moodle.org/browse/MDL-84591)).
11. **The record of what was served lives somewhere other than the review.** Brightspace's
    answer is a separate "Quiz Event Log"; the review view itself is not authoritative (w,
    [search summary of Iowa/SMU guides](https://studio.smu.ca/s/BrightspaceInstructorGuideQuizzes.pdf)).
    Credentialing audit guides list "test papers, answer sheets, scoring sheets" as the records
    to keep ([IAF records](https://iaf.nu/wp-content/uploads/2021/05/07_Records_and_Information_Requirements.pdf)).
    No source found states a field-level rule; that gap matches `research_sacaa_requirements.md`.

## 2. FLS-specific findings that sharpen the complaints (code)

- **`content_save` never deletes a question, option, page or content block dropped from YAML**
  (c). The only `.delete()` in content_save.py is due dates (1258). `_resolve_condition` says so:
  "questions dropped from the YAML and options re-created without a uuid leave stale rows"
  (content_save.py:671-674). An option whose YAML lost its `uuid` is saved under a new uuid; the
  old row stays on the question (762-780). So:
  - the answers.md rule "skip a served item that no longer exists" will rarely fire through the
    content pipeline. The common real case is a stale row that still exists but the author meant
    to remove. Deletion happens only through admin or a manual clean-up.
  - a lazy record written on the next request after such an edit will freeze the stale rows in,
    because `form.pages.all()` and `page.children()` still return them.
  - Spec effect: say plainly that "served" means "rows linked to the form at record time", that
    the record does not try to tell stale rows from live ones, and leave pruning out of scope.
    Note it under risks, since an auditor reading a paper with a ghost question is complaint 10.
- **Scores are frozen at submission and never rescored; the results page flags drift** (c,
  learner_interface/views.py:2153-2164). That is Moodle's and Canvas's model (complaints 6-7):
  the stored score is the record and live edits only raise the "outdated" notice. Once
  `compute_quiz_scores` reads the served paper, the notice still fires on a later answer-key or
  `correct` change to a served question. That is correct and should stay; it must stop firing
  only for questions that were never served (the idea already says so).
- **`complete()` deletes answers to off-path questions** (c, form_engine/models.py:461-463).
  With a record, "off-path" must mean "not on the served paper". If it stays "not on the live
  computed path", an answer to a served question that a later edit moved or removed could be
  deleted at completion (complaint 8, in FLS form). The spec should name this caller with the
  other scoring callers.
- **Option order is read straight from `question.options.all`** in the three input templates and
  the dropdown answer key (seams research §2). Until spec 2 that is harmless, but complaint 1 is
  exactly the case where review uses DB order while the sitting used another. Spec 1 should give
  templates one accessor for "options in served order" now, so spec 2 does not have to find every
  template again, and the results page's incorrect-answers list uses it too.

## 3. What this changes in the spec

1. **Review and results read the record, in served order** (complaints 1, 11). The results
   page's incorrect-answers list and any option list on it follow the served paper, not authored
   order. Test: with an injected order, the results list order matches the served order.
2. **Resume returns to the same served position on the same paper** (complaints 2, 3). Add a test
   that edits the form between two requests of an in-flight attempt that already has a record
   (add a question, reorder pages) and checks that position, "page N of M" and the question at
   each position do not change.
3. **The denominator is the served paper, fixed at record time** (complaint 4). `max_score` comes
   from the served questions, never from what the learner reached or from the live form. A
   learner who submits without visiting a page is still scored out of the full served paper.
4. **Content edits after the record do not change what the attempt serves** (complaints 6, 9).
   A question added to the form after the record is written is not served and not counted. Test
   it explicitly; it is the FLS equivalent of Moodle's version pinning and Canvas's "already
   started students see the old version".
5. **Answer-key edits still flow through as an "outdated score" notice, not a silent change**
   (complaints 5, 7). Keep "scores frozen at submission". Do not add automatic rescoring in this
   spec. State it, so a reviewer does not read "scoring reads the record" as "rescore on edit".
6. **`complete()`'s off-path answer deletion uses the served paper** (section 2). Add it to the
   list of callers and add a test: an answer to a served question survives completion after the
   live form changes.
7. **A served item that is gone is skipped without crashing** (complaint 10). Reading a record
   that names a missing page, question or option must not raise. Test each of the three. The
   answers.md decision (skip, shrink `max_score`) stands, but the spec should record that the
   skip changes the stored audit picture. A later spec may want a visible "removed after the
   attempt" marker as Moodle shows; out of scope here, and spec 4 is where it would surface.
8. **Stale rows are a known limit, not a bug this spec fixes** (section 2). Put it in the spec's
   risks or out-of-scope list with a pointer for a follow-up idea (prune dropped form rows in
   `content_save`, or block it when attempts exist, as Moodle does).
9. **One accessor for served option order** (complaint 1). Small, no visible change now, and it
   saves spec 2 a template hunt.

Not changed by this research: one seed per attempt, explicit realised order, uuid references, lazy
write on next request, authored numbers in URLs. The complaints support each of them.

status: ok
