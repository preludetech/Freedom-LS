# Research: known complaints about quiz attempt review screens and result exports

Question: what do educators and auditors commonly complain about with LMS quiz attempt review
screens and quiz result exports, and what does that mean for this spec?

## Complaints from other LMSs (web)

1. **The review shows authored order, not the order the learner saw.** A Moodle forum report says
   the feedback page listed questions in authored order while the learner had a shuffled paper,
   which confused the learner and the teacher discussing it. Moodle QA cases expect the teacher's
   preview, the edit page and each learner attempt to all differ in order.
   https://moodle.org/mod/forum/discuss.php?d=6706 ·
   https://tracker-old.moodle.org/browse/MDLQA-8411
   → Spec: the review lists pages, blocks, questions **and options** in served order. Tests
   should cover an attempt whose order differs from the authored form.

2. **Current question text is shown against an old answer, and edits or regrades rewrite
   history.** Moodle's responses report shows current wording. A regrade after an edit erased the
   learner's original response (MDL-75823), and changing the number of choices made every choice
   on old attempts show as "deleted" (MDL-74752, forum d=333717).
   https://tracker-old.moodle.org/browse/MDL-75823 ·
   https://tracker-old.moodle.org/browse/MDL-74752 ·
   https://moodle.org/mod/forum/discuss.php?d=333717
   → Spec: text freezing is out of scope (the idea says so), but the page must not hide the gap.
   Say plainly that question wording is current. Define what a served question or option that
   has since been deleted looks like, because the served paper keeps its id and the reader can no
   longer resolve it. The page must never re-score: it shows the stored `FormProgress.scores`.

3. **Exports lose answers or are missing for randomised quizzes.** Canvas New Quizzes shipped
   with no per-student analysis export for years. Classic Quizzes' CSV left cells blank when
   options were images or LaTeX under randomised order, so the learner seemed to have chosen
   nothing. Teachers using random question groups asked for results across the whole bank.
   https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-Add-Student-Analysis-report-with-option-to-download/m-p/446956 ·
   https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Download-Quiz-data-when-quiz-items-are-Latex-Images/m-p/456056
   → Spec: a selected option must be identifiable in the export without the served order, by
   option text or id, never by position ("B"). "Not asked" must stay distinct from "asked, left
   blank" (exports.py already does this; keep it).

4. **Review summary block and timestamp precision.** Moodle reworked the review summary
   (started, completed, time taken, grade, result), which had not been revisited in years
   (MDL-80900). Tim Hunt asked for seconds on the teacher's review page (MDL-71927, MDL-45691).
   https://tracker-old.moodle.org/browse/MDL-80900 ·
   https://tracker-old.moodle.org/browse/MDL-71927
   → Spec: the header shows attempt number, started, completed, time taken, score/max,
   percentage, pass mark and verdict. Fix the timestamp precision and the timezone the times are
   shown in. Write export times as ISO 8601 with an offset, so a spreadsheet cannot shift them.

5. **Long attempts are slow or fail to load.** A Moodle review of 125 to 141 questions would not
   load page-by-page in the app, and rendering every question at once is heavy.
   https://tracker-old.moodle.org/browse/MOBILE-4792 ·
   https://moodle.org/mod/forum/discuss.php?d=466804
   → Spec: one query plan for the whole paper (prefetch through the served-paper reader, no
   per-question queries), with a query-count test on a multi-page attempt.

6. **Spreadsheet damage in CSV.** Excel strips leading zeros, turns large numbers into scientific
   notation and re-parses dates. Cells starting with `= + - @` are a formula-injection risk.
   https://owasp.org/www-community/attacks/CSV_Injection ·
   https://www.ibm.com/support/pages/node/372437
   → Spec: the seed is a large integer (`served_paper.new_seed`), so Excel will mangle it as a
   number. Write it as text, and say how. The export already uses
   `freedom_ls/site_aware_models/admin_exports.py` `FormulaSafeCSV`; new cells go through it too.

7. **Auditors want the paper as stored, not one rebuilt.** Aviation exam vendors sell "a copy of
   every exam attempt is stored" and audit trails for CAA reviews as their selling point
   (Aerostudies, Questionmark, CAE EGS). No source showed a regulator accepting regeneration
   from a seed.
   https://aerostudies.com/ · https://www.questionmark.com/solutions/aviation/ ·
   https://cae.com/civil-aviation/aviation-software/cae-pelesys/training-management-deployment-system-tmds/exam-generation-system-egs
   → See codebase finding C below.

## Codebase findings that bear on the spec

A. **There is no quiz attempt export today.** `freedom_ls/form_engine/exports.py`
   (`answer_columns`, `answer_cell`, `off_path_question_ids`) is a helper library, and its only
   export caller is `freedom_ls/course_applications/resources.py`, the course-application export.
   `FormProgressAdmin` (`freedom_ls/form_engine/admin.py:320`) has no export resource. The idea's
   "the existing form export gains the served order and the seed" therefore has no quiz export to
   extend, and course applications are explicitly out of scope. The spec must decide whether to
   build a quiz-attempt export (where, who may run it, which rows) or narrow the export part.
   This is the largest open item.

B. **The attempts table has nothing to link with, and numbers attempts on the fly.**
   `freedom_ls/educator_interface/templates/educator_interface/panels/learner_courses.html`
   renders each quiz's attempts as a plain `<c-panel-table>`, not a `DataTable`. The rows come
   from `freedom_ls/reports/report_data.py` `QuizAttempt` (attempt_number, completed_at, score,
   max_score, percentage, passed), which carries **no `FormProgress` id**. `attempt_number` is
   `len(attempts) + 1` over completed sittings in `freedom_ls/reports/gather.py`
   (`_quiz_result`, around line 411). Consequences for the spec:
   - `QuizAttempt` needs the `FormProgress` id to build the link.
   - The review page must number the attempt by the same rule, or a learner's "Attempt 2" in the
     table opens a page that says "Attempt 3". The rule is completed sittings only, ordered as
     `completed_attempts_by_learner_form` orders them. Put it in one function both read.
   - The panel-framework quick view is fed by `ListViewConfig` / `QuickView`
     (`freedom_ls/panel_framework/quick_view.py`) on a list page. Whether a plain `c-panel-table`
     row inside a learner instance tab can open a quick view needs checking against
     `Skill(fls-dev:panel-framework)` before the spec promises the user's chosen quick view.

C. **The seed alone does not reproduce the paper.** `freedom_ls/form_engine/served_paper.py`
   shuffles with `Random(f"{seed}:{scope}")`, where the scopes are page and question ids, and
   honours `locked` options. Re-running the seed against a form edited since then gives a
   different paper. The stored `served_paper` (`{"seed", "pages", "options"}`) is the record. The
   export must carry the served order itself; the seed goes beside it, never instead of it. Say
   this in the export's column docs so no one mistakes the seed for a regeneration key.

D. **Three kinds of sitting, and the review must handle each.** `sitting_path()`
   (`freedom_ls/form_engine/conditions.py:373`) reads `served_paper` if present, else the frozen
   `asked`, else everything for an older completed sitting. A pre-served-paper attempt has no
   seed and no recorded option order. The review and export must state "order not recorded" (or
   the spec's chosen wording) and must not present authored order as if it were what was served.
   Without this, an auditor sees an invented order (complaint 1).

E. **The pass mark and verdict are read live, not stored.** `FormProgress.passed()` compares to
   the form's **current** `quiz_pass_percentage`, and `_score_attempt` (`reports/gather.py:366`)
   does the same. An author who changes the pass mark silently flips old verdicts on the review,
   in the attempts table and in any export. "Pass mark applied" is then not the mark applied.
   The idea settles on `quiz_pass_percentage`, so the spec should at least record this as a known
   limit, or raise storing the mark at completion as a question for
   `sacaa-compliance-1-served-paper-record`. Auditors treat a changed verdict on an old attempt
   as a red flag.

F. **The Django admin view shows undrawn questions.** `freedom_ls/form_engine/queries.py`
   `answer_groups` walks `form.pages.all()` (authored order) and marks undrawn questions "not
   asked", which is the complaint-1 pattern. If it stays, the admin and the educator review show
   the same attempt in two orders. Moving it onto the served-paper reader removes that.

G. **Auditing the open.** The glossary (`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`)
   allows `viewed` only "for a read worth auditing", with `conversation.viewed` as the precedent.
   Nothing in the complaints above asks for a log of who viewed a result. Auditors ask for the
   record itself. Holding `viewed` for question-bank access
   (`sacaa-compliance-content-versions-and-access-4-question-access`) is consistent with that.

## What the spec should therefore say (summary)

- Served order for pages, blocks, questions and options; undrawn questions absent; an explicit
  label for attempts with no recorded order.
- Stored scores only, never a re-score; a clear statement that wording is current; defined
  rendering for a served item since deleted.
- Header: attempt number (same rule as the table), started, completed, time taken, score/max,
  percentage, pass mark, verdict, with a stated precision and timezone.
- Link and quick view need a `FormProgress` id on `QuizAttempt`. Confirm the quick view fits a
  non-`DataTable` table.
- Export: decide first whether a quiz-attempt export exists to extend (finding A). The served
  order goes in the file, the seed as text beside it, ISO 8601 times, `FormulaSafeCSV`, and
  options named by text or id, never by position.
- Note that the live pass mark can flip old verdicts.
- Query-count test on a long multi-page attempt.

status: ok
