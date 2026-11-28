# Research: known complaints about question versioning in quiz engines

Topic `known_complaints`. Sources are search-result summaries (titles and snippets) from forum, tracker and university support pages. I did not open every ticket, so ticket status and fixed-in versions are unverified. Where a point is my inference it says so.

Design under test: stable `FormQuestion` identity, immutable version rows, exact-comparison change detection with no minor-edit carve-out, pin at attempt start (served paper `versions` key plus nullable `QuestionAnswer` FK), past-attempt readers read the pinned version, reports out of scope (answers.md).

## Complaint table

| # | Complaint | Seen in | Spec design | Note |
|---|-----------|---------|-------------|------|
| 1 | Edit after attempts silently changes past results or what the auditor sees | Canvas classic quizzes; Canvas community says it is hard to track who got which version. New Quizzes added a "edit a copy" prompt because of it | Avoids | Readers use the pinned version and stored scores are never recomputed. |
| 2 | Teacher fixes an error in a new version, but attempts stay on the old one, so the fix "didn't work" | Moodle forum d=438090 ("Problem with version question"), d=434465 ("Update question after quiz probs") | Inherits, by design | Pinning is the audit requirement. The spec should say that a fix reaches only new attempts and that regrading is not built. Docs and any admin message should say this plainly. |
| 3 | Regrade confusion: regrade after edit uses the wrong version, or changes recorded answers | Moodle MDL-75823 (regrade changed recorded answers after an edit); Tim Hunt's workaround is to set the fixed version back and regrade; Wharton and BC note Canvas New Quizzes regrade applies to all students who got the question | Avoids, by omission | Regrading is out of scope. State that stored `scores` do not change and that a wrong correct-answer has no remedy in this spec. A teacher will ask for one. |
| 4 | Version proliferation from typo fixes; teachers ask to save without a new version | Moodle MDL-80006 (feature request to save an edit without a version) | Inherits, deliberately | Exact comparison with no carve-out is the settled decision. Cost is rows only, one JSON snapshot per real change. State that a typo fix is a version and that this is the audit position. Because `content_save` is the only writer, a no-op re-run must not make a version (exact comparison covers this). |
| 5 | Question bank clutter and a confusing history list | Moodle 4.x question bank history view; UOW guide advises duplicating when reusing across contexts | Mostly avoids | No bank UI in this spec. Old versions are never served and are not browsable until `...-5-answered-version-review`. The risk moves to that spec. |
| 6 | Statistics and reports merge or split across versions | Moodle 4.0 docs: facility index and discrimination are aggregated across all versions of a question. Mixed meanings in one row is the complaint (my inference) | Inherits, must state | Reports are out of scope, so the cohort and learner PDFs stay on the live row. Write the limitation into the report text and docs, as the idea already suggests. The per-attempt learner detail should read the answered version if it is touched at all. |
| 7 | Exports with mismatched headers or columns after edits | Microsoft Forms: each question edit adds a column. Google Forms: deleted questions leave old columns, renamed headers break integrations. Advice is to add a new question rather than rewrite | Partly avoids | The form export reads the pinned version per attempt, but a column keyed on the question uuid is stable. Decide and state whether the header is the live or the answered text, because the two can differ within one export. Recommend the header carries the live text and the cell the answered answer, or add a version column. Spec must choose. |
| 8 | In-progress attempts see changed questions | Canvas "do not edit after students start"; Moodle thread d=453360 "Update quiz question version in active attempt" (teachers want to push a fix into a live attempt) | Avoids, but expect the request | Pinning means an open attempt never sees the fix. State this as intended. |
| 9 | Performance of version lookups | Moodle MDL-85637 (`question_versions` index on questionbankentryid, version still slow), MDL-78622 (`question_references` join slow in "Add question"), MDL-81301 (slow delete on `question_set_references` without an itemid index) | Avoids if designed for it | Moodle's cost came from resolving "latest version" through joins at read time. Here the live row is the latest version and an attempt stores its pin, so no read-time resolution is needed. Add an index on (question, number), and index the `QuestionAnswer` FK. Load the pinned versions for a sitting in one query, not one per question. |
| 10 | Migration and upgrade problems when versioning was introduced | Moodle MDL-73808 (`upgrade_migrate_question_table` slow and memory-heavy, failed on 3.9 to 4.0), MDL-76509 (invalid rows break the migration), MDL-83151 (orphaned slots after upgrade), forum d=439615 (restore failure of random questions from older sites) | Must state; risk is real | The backfill makes version 1 for every question and pins existing answers. Batch it (`iterator()`, `bulk_create`), tolerate answers whose question has no options or was retired, and test with orphan rows. The "version 1 is the content at migration time, not the original wording" caveat must appear in the migration and docs, as the idea says. Moodle's backfill had the same inherent limit. |
| 11 | First `content_save` after migration double-counts or makes a spurious version | Not found in sources; my inference from the "stored vs authored markdown" open question | Must state | Compare on stored, translated values. Unchanged content after migration must not produce version 2. |
| 12 | Editing an old version makes a new version instead of amending it | Moodle MDL-85781 | Avoids | No path edits a past version. `content_save` always compares to the latest. A revert to old wording is a new version, not a reuse of the old row. State this so an auditor is not surprised by a version identical to an earlier one. |
| 13 | Versions that do not cover everything that changes meaning | Canvas/Google advice: a stimulus change makes old and new answers incomparable | Inherits, must state | `FormContent` and `FormPage` are not versioned, so a rewritten stimulus alters the question's meaning without a version. This is a known audit gap. State it as a limit. |

## What the evidence suggests for the spec

- The most common teacher complaints (2, 3, 4, 8) are about immutability and pinning itself. They cannot be designed away. They need plain documentation and wording that tells an author the effect of a fix: new attempts only, no regrade.
- The most common admin and operator complaints (9, 10) come from resolving versions at read time and from heavy migrations. The pin-at-start design avoids the first. The backfill needs batching and orphan tests.
- The most common analyst complaints (6, 7) are about aggregation and exports. Reports are deferred, so the limit must be written down. The form export is in scope, so the header decision (row 7) must be explicit.
- No source showed a complaint about pinning in the served paper plus a per-answer FK. The cost is two places that can disagree. Add a consistency rule: the answer FK must match the served-paper pin, or the sitting reader treats it as an error.

## References

- Moodle forum, "Problem with version question": https://moodle.org/mod/forum/discuss.php?d=438090
- Moodle forum, "M401 - Update question after quiz probs": https://moodle.org/mod/forum/discuss.php?d=434465
- Moodle forum, "Update quiz question version in active attempt": https://moodle.org/mod/forum/discuss.php?d=453360
- Moodle forum, restore error with random questions: https://moodle.org/mod/forum/discuss.php?d=439615
- MDL-75823 (regrade changes recorded answers): https://tracker-old.moodle.org/browse/MDL-75823
- MDL-80006 (save edit without a new version): https://tracker.moodle.org/browse/MDL-80006
- MDL-85781 (editing an earlier version): https://tracker-old.moodle.org/browse/MDL-85781
- MDL-73808 (4.0 question migration slow): https://tracker-old.moodle.org/browse/MDL-73808
- MDL-76509 (invalid rows break the upgrade): https://tracker-old.moodle.org/browse/MDL-76509
- MDL-81301 (slow delete, missing index): https://tracker-old.moodle.org/browse/MDL-81301
- MDL-85637 (`question_versions` index): https://tracker-old.moodle.org/browse/MDL-85637
- MDL-83151 (orphaned slots after upgrade): https://tracker-old.moodle.org/browse/MDL-83151
- MDL-78622 (`question_references` join slow): https://tracker-old.moodle.org/browse/MDL-78622
- Moodle 4.0 question bank docs (statistics aggregated across versions): https://docs.moodle.org/400/en/Question_Bank
- Moodle 4.0 question reports: https://docs.moodle.org/400/en/Question_reports
- Canvas community, "Will edited question in New Quizzes show up in a second attempt": https://community.canvaslms.com/t5/New-Quizzes-Discussion/Will-edited-question-in-New-Quizzes-show-up-in-a-second-attempt/m-p/631181
- Canvas docs, "How do I edit a quiz in New Quizzes?": https://community.canvaslms.com/docs/DOC-15037
- Wharton, All about New Quizzes (regrade applies to all students): https://support.wharton.upenn.edu/help/canvas-new-quizzes
- BC, grading New Quizzes: https://cteresources.bc.edu/documentation/assignments-and-grades/get-started-with-new-quizzes/grading-new-quizzes/
- Chico State, editing Canvas quizzes after students begin: https://support.csuchico.edu/TDClient/1984/Portal/KB/ArticleDet?ID=113553
- Manchester, editing quizzes post submission: https://www.elearning.fse.manchester.ac.uk/getting-started-with-canvas/editing-quizzes-post-submission/
- Microsoft Forms, extra columns after edits: https://techcommunity.microsoft.com/t5/Microsoft-Forms/Additional-columns-added-to-Form-results-in-Excel/m-p/269635
- JotForm, Google Sheets integration breaks on edit: https://www.jotform.com/answers/1387779-google-spreadsheet-integration-breaks-when-editing-the-data
- Not covered: Blackboard and Questionmark (no complaint threads surfaced in two searches).

status: ok
