# Answers: sacaa-compliance-content-versions-and-access-4-question-access

Asked by `/sdd:start` before the spec was written.

- Q: The course content preview (`PreviewContentAction`) shows topics, activities, surveys and quizzes; what should the new permission gate? → A: Quiz forms only. Topics, activities and survey forms stay previewable by anyone who can see the course; quiz previews are refused without the permission and audited. This matches the admin rule, which tests the form's scoring strategy. (asked up front)
- Q: When does viewing the question detail in a cohort report PDF write an audit entry? → A: On each download of a PDF that carries the detail. Whether a PDF carries the detail is decided when it is generated. (asked up front)
- Q: PDFs generated before this change have no record of whether they carry question detail (all of them do); who can download them? → A: Treat them as carrying the detail. Only holders of the permission can download them, and each download is audited. (asked up front)
- Q: Should holders of the permission be told their views are logged (one-line note, confirm before opening, or nothing)? → A: No notice. Views are logged silently. (asked up front)
- Q: A person without the permission gets no Preview on quiz rows of the course outline; should the panel say why? → A: Show a disabled Preview button on quiz rows (user's own answer; not the recommended panel-level note). (asked up front)
- Q: Should a refused request for question detail (a quiz preview or a PDF download) write an audit entry? → A: No. Only views are logged. (asked up front)
- Q: The educator quiz attempt review (`panels/learner/quiz_attempt.py`) already shows the answer key with no permission and no log; gate it here or leave it to spec 5? → A: Gate it here, with the same permission and the same audit entry. Spec 5 adds only the answered-version display. (asked up front)
- Q: Who can grant the new role from the Staff section? → A: Site admins and organisation admins, like the other organisation roles. (asked up front)
