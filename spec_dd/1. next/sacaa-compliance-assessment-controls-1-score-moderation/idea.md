# Score moderation

Spec 1 of 7 in the SACAA assessment controls effort. Read the "SACAA assessment controls" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A moderator overrides a learner's mark on one quiz question in one completed attempt (`FormProgress`), giving a required reason. The system mark is kept and never edited. The moderated mark is stored beside it and wins in every place a mark is read. The educator attempt review page carries the control. Every override writes an audit entry with the old mark, the new mark and the reason. The attempt review and the cohort report show the system and moderated marks side by side. The learner sees the moderated result.

## Why

Regulation, from the original brief: "where applicable, an acceptable form of moderation must be demonstrated; if after moderation it is found the question was defective or not clear and the student is awarded the marks then a record from the moderator showing the student mark awarded must be kept with the results. however the marks on the system cannot be manipulated."

Today a defective question can only be fixed by editing `scores` or the answers, which destroys the system mark. The regulation needs both marks kept and a record of who moderated and why.

## What is settled

- The override is a new record keyed on (`FormProgress`, `FormQuestion`). It is keyed on `FormQuestion` identity, not on option rows, so it survives the question-version changes in `sacaa-compliance-content-versions-and-access-3-question-versions`. Its `FormQuestion` link uses `on_delete=PROTECT`, like `QuestionAnswer.question`.
- The system mark is never edited. The stored `scores` pair keeps meaning "what the system marked". A second stored value beside it holds the moderated result, and a moderated mark is never written over `scores`.
- Questions score 1 point each (`max_score` counts questions). An override therefore awards or removes that question's one mark. `max_score` does not change.
- Overrides apply to completed QUIZ attempts only. An open attempt, or a form that is not a QUIZ, cannot be moderated.
- The moderated mark wins in every reader: the aggregate readers of `scores` (which read the moderated value when one exists), `compute_quiz_scores`, `_mark` in the educator attempt review, `get_incorrect_quiz_answers`, the reports (including `build_sat_questions`), at-risk (`FailedLatestQuizAttemptRule`), course completion and unlocking (through `quiz_verdict`, `attempt_completes_form` and the latest completed attempt), and the "score is outdated" check (`stored_score_outdated`). `compute_quiz_scores` applies overrides, so the outdated check does not fire on a moderated attempt.
- The aggregate readers never recompute, so saving an override also refreshes the moderated aggregate and sends the same recalculation `form_attempt_completed` triggers, so `CourseProgress` follows the new verdict.
- A new organisation permission to moderate quiz marks is held by a new moderator role. No existing role holds it by default. A site can grant it by extending a role through `FREEDOMLS_PERMISSIONS_MODULES`.
- Moderating also needs the question-viewing permission from `sacaa-compliance-content-versions-and-access-4-question-access`, which blocks this spec. Without both, the control is not shown and the action is refused.
- The control lives on the educator attempt review page (`educator_interface/panels/learner/quiz_attempt.py`), in the existing panel framework, with the `ReasonForm` dialog for the reason.
- Every override writes an audit entry through `record_entry`, inside the same transaction as the change. `details` holds the old and new marks, the reason goes in `reason` (max 500 characters), and the action is a `noun.verb` code that comes from the domain glossary, so the glossary gets any new noun first.
- The educator attempt review and the cohort report (screen and PDF) show the system mark and the moderated mark side by side. The learner's results page, attempt list, course progress and unlocking show the moderated result.
- Bulk award of one question to every attempt is out of scope here. A later spec owns it.
- Collisions: `sacaa-compliance-content-versions-and-access-3-question-versions` and `sacaa-compliance-content-versions-and-access-5-answered-version-review` change `compute_quiz_scores`, `_mark` and the same review panel. `sacaa-compliance-content-versions-and-access-4-question-access` shares `roles.py`, the permission registry, `audit_log/actions.py` and its README. Land the override reader on whichever of these has settled, and sequence role and permission edits with the question-access spec.

## Open until the spec

- **Can a moderator reverse or replace an override?** Recommend yes: a new override on the same question supersedes the old one, every earlier override is kept as history, and reversing is an override back to the system mark. Each change is its own audit entry. Nothing is deleted.
- **Does the learner get a notification?** Recommend no. The `notifications` skill (`claude_plugins/fls-dev/skills/notifications/SKILL.md`) passes a moderator-caused change on the "someone else acted" test, but the learner sees the result on the results page and the attempt list. A moderator may also move several questions in one attempt, which would fire repeatedly. The spec records the five checklist answers and leaves a verdict-flip notification for later.
- **How is "moderated mark beside the system mark" stored on the attempt?** Recommend a second aggregate pair stored on `FormProgress` next to `scores`, so readers choose the moderated pair when it exists. The spec picks the field and how `quiz_percentage()`, `passed()` and `quiz_verdict` pick between the two.
- **Where does the moderator role sit?** Recommend a new organisation-scoped role whose name the spec takes from the glossary, holding the moderate permission and the question-viewing permission, and nothing else beyond what the review page needs to open.

## Out of scope

- Awarding a question to every attempt in one action.
- Per-question weights or partial marks. Questions stay at 1 point.
- Overriding a whole attempt's total, or an open attempt.
- Changing the system mark, `scores` at completion, or the question content.
- A learner-facing appeal flow.

## Resources

- `../sacaa-compliance-assessment-controls/research_attempts_and_scoring.md`, sections 3 (scoring and consumers), 4 (audit log and educator gating) and 6 (collisions).
- `../sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`, for the regulation text.
- Regulation quote source: the original brief, `spec_dd/1. next/sacaa-compliance-assessment-controls/idea.md` (SACAA requirement on moderation, "Override question scores").
- `claude_plugins/fls-dev/skills/notifications/SKILL.md`, for the notification recommendation.
