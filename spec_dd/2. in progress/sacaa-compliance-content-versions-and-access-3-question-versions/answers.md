# Answers: sacaa-compliance-content-versions-and-access-3-question-versions

Asked by `/sdd:start` before the spec was written.

- Q: Where should an attempt pin the version of each question it was served? → A: Both: a versions key in the QUIZ served paper written at attempt start, and a nullable `QuestionAnswer` FK to the answered version, so survey and application answers are covered too (asked up front)
- Q: How should the cohort and learner PDF reports in `reports/` handle a question revised between attempts? → A: Leave reports out of scope; they stay on the live row and a later spec handles them (asked up front)
- Q: Once a question is revised, how should the form export show which version each learner answered? → A: Keep one column per question headed with the latest wording, and add a version column beside each; each cell is read through the answered version (asked while research ran)
- Q: What should `content_save` print about the versions it saves? → A: A summary line of new, revised and unchanged counts, plus one line per revised question with its file and slug, old → new version number, and the fields that changed (asked while research ran)
- Q: How hard should version-row immutability be enforced? → A: Django guards on save()/delete() and queryset update()/delete(), plus a PostgreSQL trigger refusing UPDATE, DELETE and TRUNCATE; danger_content_delete disables the trigger for its own run only (asked while research ran)
- Q: Should a changed `FormQuestion.explanation` make a new version? → A: Yes, explanation is a versioned field (asked while research ran)
