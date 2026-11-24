# Research: best practices for an auditor-grade attempt review and its export

Question: what are the established practices for showing one assessment attempt (served paper,
answers, marking) in a way an auditor accepts, and exporting it for inspectors? This builds on
`spec_dd/1. next/sacaa-compliance/research_sacaa_requirements.md` and
`spec_dd/3. done/2026-11-20_10:30_sacaa-compliance-1-served-paper-record/research_best_practices.md`
(Moodle layout, QTI `sequenceIndex` / `choiceSequence`) and does not repeat them. Code references
are under `freedom_ls/` at the branch head.

## 1. What the review page must show (practice from Moodle and QTI)

Moodle's teacher review of one attempt is the reference most auditors will have seen. Teachers
bypass the learner review options and see everything, at any time
(https://docs.moodle.org/405/en/Quiz_settings, "Review options"). The page has two parts:

- **An attempt summary block at the top:** Started, Completed (or Submitted), Time taken, State,
  Marks (score / max), Grade (percentage), plus overall feedback. Moodle has since shortened the
  labels to "Started" / "Completed", kept "Time taken", and the app uses "Duration"
  (https://tracker-old.moodle.org/browse/MDL-80900, https://tracker-old.moodle.org/browse/MOBILE-4550,
  https://tracker-old.moodle.org/browse/MDLQA-18442).
- **Every served question in served order, each showing:** its position number in this attempt,
  the question text, the options in the order the learner saw them, which one the learner
  selected, which one is correct ("Right answer"), whether the response was correct, and the mark
  out of the maximum for the question. A question left blank says so ("Not answered"). It is never
  just an empty cell.

What the spec should take from this:

- **Summary fields** (one `InstanceDetailsPanel`, in the shape of `LearnerDetailsPanel` in
  `educator_interface/panels/learner/panels.py`): learner, quiz (form title), course, attempt
  number, started, completed, time taken, score / max score, percentage, pass mark, Passed/Failed
  badge. `QuizAttempt` in `reports/report_data.py:50` has every one of these except start time,
  duration and the attempt's pk. The row link and the quick view need the pk (section 4).
- **Per-question rows** read through `sitting_path()` (`form_engine/conditions.py:373`). Pages
  come from `path.pages` and children from `children_by_page`, and options from
  `served_options_by_question`, which is None for an attempt with no served paper. In that case
  use the live option order and say so (section 3). Number the questions by served position, as
  the learner saw them (`SittingPath` keeps `_question_positions`). Never use authored order.
- **Each option is marked twice:** "Selected" and "Correct". An auditor checks the marking by
  comparing the two, so both must be visible together, not only a verdict. Use text and an icon,
  never colour alone (brand and accessibility rules).
- **Content blocks served** (FormContent) appear in place. QTI reports items only, but the idea
  asks for the whole paper, and showing them keeps positions honest.
- **Undrawn questions are absent.** QTI says results "relate only to items that were selected for
  presentation" (http://www.imsglobal.org/question/qtiv2p2/QTIv2p2-Results-InfoBindModelv1p0/imsqtiv2p2_result_v1p0_InfoBindv1p0.html).
  This page must not reuse `answer_groups` (`form_engine/queries.py:118`). That function walks
  every authored page and marks undrawn questions "not asked", which is the behaviour the idea
  rejects.

## 2. Provenance: show what is stored and what is derived, and flag disagreement

This matters most for "auditor-grade". An audit record must not present a value computed today as
though it were recorded at the time.

- **The total is stored. Each question's verdict is not.** `FormProgress.scores` holds
  `{"score", "max_score"}`, frozen at `complete()` (`form_engine/models.py:508-531`). Per-question
  correctness is not stored anywhere. It can only be re-derived from the option's current
  `correct` flag (`is_quiz_answer_correct`, used in `compute_quiz_scores`, `models.py:689`). If an
  author has since changed which option is correct, the ticks on the page will disagree with the
  stored total.
- **Precedent to reuse:** the learner results page already detects this. In
  `learner_interface/views.py:2189-2203`, `stored_score_outdated` compares `scores` with
  `compute_quiz_scores(path)`, and the check is skipped when `path.has_missing_served_items`. The
  review should apply the same check and, when it fires, show a `c-panel-callout` along the lines
  of "Marking has changed since this attempt. The score shown is the one recorded at submission;
  the per-question marks reflect the current answer key." The spec should extract the check into
  one shared function rather than copy it (CLAUDE.md "avoid repeating code").
- **Deleted served items.** `served_path` drops a served page, child or option that the form no
  longer has, and sets only the boolean `has_missing_served_items` (`conditions.py:298-338`).
  Moodle's practice is a "deleted choice" placeholder rather than silence. The minimum is a
  callout saying "N items served in this attempt have since been removed from the quiz". The
  served-paper JSON still holds the ids, so the review could list them as placeholder rows
  ("Question removed from the quiz") at their served position. The spec should pick one. A silent
  gap in a numbered paper reads as tampering to an inspector.
- **The pass mark is not stored per attempt.** `FormProgress.passed()` (`models.py:403`) reads
  the form's current `quiz_pass_percentage`, so changing the pass mark later flips the verdict on
  every past attempt. The idea accepts the current value. The spec should label the field
  accordingly (for example "Pass mark (current setting)") or record it as a known limit beside
  frozen question text. Storing the pass mark in `scores` at `complete()` would be a scoring
  change, and scoring changes are out of scope for this spec. Note that as a follow-up, not as
  work here.
- **Question wording is current.** The idea already settles this. The page should still say it
  once ("Questions show their current wording") so that an inspector is not misled.
  `sacaa-compliance-content-versions-and-access-5-answered-version-review` later replaces this
  with the version answered.
- **Older attempts without a served paper:** `sitting_path` falls back to `asked` (a set, ordered
  by authored order) or to `full_path`. For these attempts the served order was never recorded.
  The page should say "Order shown is the authored order; this attempt predates the served-paper
  record" rather than imply the order is the one served.

## 3. Attempt identity must match the table it is opened from

- `attempt_number` is assigned in `reports/gather.py:401-411` as the attempt's 1-based position
  among the learner's completed attempts at that form, in `completed_attempts_by_learner_form`
  order (`reports/indexes.py:104-120`). The review page and the quick view must take the number
  from the same function. If they recompute it differently, the number on the review page can
  differ from the number on the row that opened it.
- The key is (learner, form), not course, so a form used in two courses numbers its attempts
  across both. The spec should state this, or narrow the key, so the review and the table agree.
- Only completed attempts link to the review (decided in answers.md). An attempt that has
  `completed_time` but `scores` that cannot be read (`_score_attempt` returns None values) still
  opens, and its summary shows blanks with a reason. It must not raise a 500.

## 4. Access, URL and auditing the read

- **Instance URL scoped through the learner.** Resolve the attempt with `get_object_or_404` over
  attempts whose user is the learner, and resolve the learner through `learners_visible_to`
  (`VIEW_LEARNER`). Never resolve the attempt by pk alone. That is the usual IDOR guard, and it
  matches the idea's "nobody else". Filter to `form__strategy=QUIZ` and `completed_time__isnull=False`
  so that an application or in-progress sitting returns 404, not an empty page.
- **Audit the view.** The precedent is `conversation.viewed` (`audit_log/actions.py:275`, written
  in `educator_interface/panels/learner/messages.py:229` with `record_entry(..., subjects=[learner])`).
  The sibling roadmap decision for `sacaa-compliance-content-versions-and-access-4-question-access`
  is "every view is audited". The review shows the answer key (the correct options), so it
  exposes the same material that spec gates. Recommendation: add `quiz_attempt.viewed` (or the
  glossary's noun), recorded on the full page only and not on the quick view or HTMX refreshes,
  so that one visit is one entry. Exports already write their own entry (`_record_export` in
  `educator_interface/panels/audit_log/data_tables.py`). An attempt export should do the same.
- Moodle's teacher review is gated by a capability, and the student-facing review options never
  limit it. That matches using `VIEW_LEARNER` here without a new permission.

## 5. The export: a codebase finding that changes the idea

- **No quiz attempt export exists.** `form_engine/exports.py` (`answer_columns`,
  `off_path_question_ids`, `answer_cell`) is called only by `CourseApplicationResource`
  (`course_applications/resources.py`), the admin export of course applications. That export
  covers application forms, which are never QUIZ, and those forms are never shuffled.
  `FormProgressAdmin` (`form_engine/admin.py:319`) has no `resource_classes`, and the reports app
  writes no CSV. "The existing form export gains the served order and the seed" therefore has no
  quiz attempts to attach the served order to. The spec must decide one of:
  1. Add the served order and seed columns to the application export anyway. This is cheap but
     carries no SACAA value, since applications are not quizzes.
  2. Add a new quiz-attempt export: an admin `SiteAwareModelResource` on `FormProgress`
     (`site_aware_models/admin_exports.py` gives CSV formula escaping and ISO timestamps), or an
     Export on an educator data table (the panel framework's `ExportColumn`, as the audit log's
     `get_export_columns` does).
  3. A per-attempt download from the review page.
  This is the largest open decision for the spec. Raise it with the user, because the idea
  assumed an export that does not exist.
- **Shape recommended for an inspector export** (QTI results reporting, Moodle responses report):
  - The authoritative record is the realised order, not the seed. Write the served question
    sequence as identifiers in served order (QTI `sequenceIndex`), and the option sequence per
    choice question (QTI `choiceSequence`). A seed reproduces the paper only with the same code
    (`_scope_rng(seed, scope)` in `form_engine/served_paper.py`) run over the same form tree, and
    the export cannot promise either.
  - Long format (one row per attempt per served question: attempt id, learner, form, attempt
    number, position, question id, question text, options shown in order, selected, correct,
    mark) re-sorts and filters cleanly in a spreadsheet. It also handles different draws per
    attempt without "Not asked" columns. Wide format (one row per attempt, authored-order
    columns) is what the application export does, and the idea wants to keep it. If wide is kept,
    one extra cell per attempt holding the served order as `;`-joined question ids is the
    smallest change. A second sheet is not possible: django-import-export CSV is single-sheet,
    and XLSX is not enabled.
  - **Write the seed as text.** `new_seed()` returns `secrets.randbits(63)`, which can be up to
    19 digits. Excel and Sheets keep 15 significant digits, so a numeric cell silently corrupts
    the seed. Export it as a string, for example prefixed `seed:` or as hex.
  - Timestamps in ISO 8601 with offset (`IsoDateTimeWidget` already does this). Keep
    `escape_csv_formula` on every text cell (`base/csv_safety.py`), because question and option
    text is author-written. OWASP CSV injection: https://owasp.org/www-community/attacks/CSV_Injection.
  - State "score as recorded at submission" in the header, and keep the pass mark's
    current-setting caveat. Include the stored score and any flag from section 2, so that the
    file carries the same caveats as the screen.

## 6. Regulatory anchors (for the spec's Why)

- SACAA CAR 141.01.17: detailed student records, kept 5 years, produced on request (already
  sourced in `research_sacaa_requirements.md`).
- EASA ORA.ATO.120 is the comparable European rule. ATOs keep each student's training details and
  "progress tests and examinations" for 3 years after the training ends
  (https://www.ecologie.gouv.fr/sites/default/files/documents/AltMoc_ORA.ATO_.120.pdf, an AltMoC
  copy; check against the official EASA Part-ORA text). Neither rule names per-attempt fields. The
  page content above is inferred from engine practice (Moodle, QTI), not mandated.

## 7. Suggested tests

- A shuffled attempt shows questions and options in served order. An injected reversed
  `served_paper` reverses the page.
- An undrawn question is absent. An attempt with no served paper shows the authored order, with
  the caveat.
- An answer key changed after submission shows the outdated-marking callout. A deleted served
  question shows the missing-items notice or placeholder, never a renumbered gap.
- Another learner's attempt, an attempt outside `learners_visible_to`, an in-progress attempt and
  a non-quiz sitting all return 404.
- The attempt number on the review page equals the number on the Courses-tab row.
- Opening the page writes one audit entry. The quick view writes none.
- The exported seed survives a round trip as text (19 digits intact).

## References

- Moodle quiz settings, review options and teacher bypass: https://docs.moodle.org/405/en/Quiz_settings
- Moodle review summary labels: https://tracker-old.moodle.org/browse/MDL-80900 , https://tracker-old.moodle.org/browse/MOBILE-4550 , https://tracker-old.moodle.org/browse/MDLQA-18442
- Moodle response history on review: https://tracker-old.moodle.org/browse/MDL-77225
- Moodle responses report: https://docs.moodle.org/405/en/Quiz_responses_report
- IMS QTI 2.2 results reporting: http://www.imsglobal.org/question/qtiv2p2/QTIv2p2-Results-InfoBindModelv1p0/imsqtiv2p2_result_v1p0_InfoBindv1p0.html
- OWASP CSV injection: https://owasp.org/www-community/attacks/CSV_Injection
- EASA ORA.ATO.120 (AltMoC copy): https://www.ecologie.gouv.fr/sites/default/files/documents/AltMoc_ORA.ATO_.120.pdf

status: ok
