# Research: UX patterns for question versions (spec 3)

Scope: backend-leaning. No educator version UI (later spec). Evidence comes from a small web search (Moodle, Canvas). I found nothing for Blackboard, TalentLMS or Questionmark. Items marked INFERENCE are my recommendations and are not documented vendor behaviour.

## 1. Showing a past attempt whose question has changed

What the sources say:
- Moodle pins the question version when an attempt starts and keeps it after the attempt closes. QA test MDLQA-16685 states the goal that the version a student starts with should not change, even after the attempt closes. The review page shows the recorded version, not the latest.
  - Moodle marks it. The question info box on the review page shows a label such as "v2". After a teacher changes the quiz's version selector, the label stays "v2" for the earlier attempt (MDL-77745).
  - MDL-80682 asks for the label to read "v1 (latest)" or "v1 (of 12)". This shows that a bare "v1" is ambiguous, because the reader cannot tell whether it is current.
- Moodle regrading can move an attempt onto a different version (forum thread). Users found this surprising. This supports the spec's "regrading is not built" decision.
- Canvas New Quizzes avoids the problem. Once a question has submissions, the teacher can only edit a copy, so the answered item is never changed. Regrading is a separate, explicit action. Regraded items carry an alert and the previous score in SpeedGrader.
- Moodle docs warn to be very careful editing questions after attempts, because regrading cannot be undone easily.

Pattern for the learner results page (INFERENCE from the above):
- Show the answered wording and answered correct answers, unmarked, to the learner. A learner has no use for version numbers, and the stored score matches what they see.
- Put the marking on audit and educator surfaces only. Use a small "Version N" label. If the question has since been revised, add "(superseded)" or "N of M". That follows MDL-80682.
- Do not add a "this question has changed" banner to the learner page. It would confuse the learner and invite disputes. This is a decision for the spec to confirm.

## 2. Export column labelling when wording changed

I found no documented vendor behaviour. The Moodle statistics docs say reports can be downloaded in several formats. They do not say how a changed wording is handled. Options:
- A. One column per `FormQuestion` (stable uuid), header from the latest wording, plus a "version answered" column per question or per row. Simple and stable for pivoting. The header can misdescribe older answers, so add the version column.
- B. One column per version, such as "Q (v1)" and "Q (v2)". It is accurate but sparse, and the column count grows with each revision.
- C. A long format with one row per answer: attempt, question uuid, version number, wording as answered, answer, correct. It is the most audit-friendly, and it is what an auditor wants.

Recommendation for the spec (INFERENCE): keep the existing wide layout, one column per question keyed on the stable question identity. Add an adjacent "version" column for each question. Where a cell's version is not the latest, carry the answered wording in that cell or in a companion column. State in the header or documentation that the header shows the latest wording. Consider C as an optional audit export, not a requirement of this spec.

## 3. Output of a CLI or content-sync tool when versions are created

I found no vendor documentation for a CLI that prints this. Moodle creates versions on edit in the UI. The pattern below comes from common sync-tool practice (INFERENCE):
- Print counts per category: "Questions: 120 unchanged, 3 revised (new version), 2 new (version 1), 0 removed". The roadmap says retire is spec 2, so keep it separate.
- List each revised question: uuid, slug or file path, "v2 -> v3", and the changed fields (text, option set, correct). The changed-field list lets an author confirm that a typo fix was meant to be a version.
- Warn, before writing, that every difference makes a version and that there is no minor-edit carve-out (the spec bans one). A dry-run or a confirm step is out of scope unless sdd-1 provides it. Reuse its commit-hash line: "Versions saved at commit <hash>".
- Make an unchanged run print "0 revised". Make a re-run after a failure idempotent, so counts do not double.
- Make the output the same on a first run after the migration: no "revised" for questions whose content equals the migrated version 1.

## 4. Disclosing the backfilled "version 1 = content at migration time"

No vendor sources found. Moodle's own upgrade created version 1 for existing questions (the sources I found do not describe its disclosure). Recommendation (INFERENCE, matching the idea's settled item):
- Record the origin on the version row itself, for example a flag or origin field "backfilled at migration" with the migration date. Prose in documentation alone is easy to lose.
- Any audit surface that shows a backfilled version says so in plain words: "Version 1 was recorded when versions were introduced (date). It is the content at that time, not necessarily the wording the learner saw."
- State the same in the migration docstring and in the documentation that describes versions. This spec's readers need only expose the flag. The educator UI is a later spec.
- Never present backfilled version 1 as "original wording" in export headers or documentation.

## 5. Takeaways for the spec

1. Learners see the answered version unmarked. Audit and educator readers show "vN" and whether it is superseded.
2. Exports should be keyed on the stable question identity, with an explicit version column and a documented rule for the header.
3. The sync command prints per-category counts plus a per-question list of revised questions with changed fields, and the commit hash.
4. The backfill is a stored fact on the version row, not only documentation.
5. Moodle's regrading surprise and Canvas's edit-a-copy rule both support the spec's "no regrading, stored scores unchanged".

## References

- Moodle tracker MDL-77745, version label on the review page: https://tracker.moodle.org/browse/MDL-77745
- Moodle QA MDLQA-16685, version fixed at attempt start: https://tracker-old.moodle.org/browse/MDLQA-16685
- Moodle tracker MDL-80682, "v1 (latest)" label request: https://tracker-old.moodle.org/browse/MDL-80682
- Moodle forum, attempt keeps its version, regrade can change it: https://moodle.org/mod/forum/discuss.php?d=438090
- Moodle quiz statistics report docs, edit and regrade warning, exports: https://docs.moodle.org/503/en/mod/quiz/statistics
- Canvas Community, New Quizzes edit-a-copy warning: https://community.canvaslms.com:443/t5/New-Quizzes-Discussion/Will-edited-question-in-New-Quizzes-show-up-in-a-second-attempt/m-p/630723
- Canvas regrading in New Quizzes (SpeedGrader alert and previous score): https://cteresources.bc.edu/documentation/assignments-and-grades/get-started-with-new-quizzes/grading-new-quizzes/

status: ok
