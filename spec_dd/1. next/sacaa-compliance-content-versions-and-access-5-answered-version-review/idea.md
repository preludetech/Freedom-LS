# Educators see the question version a learner answered

Spec 5 of 5 in the SACAA content versions and access effort. Read the "SACAA content versions and access" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The attempt review built by `sacaa-compliance-4-attempt-review` shows an educator one learner's quiz attempt (one `FormProgress`). This spec makes that review show, for each question served, the version the learner answered, and whether that question is still served.

Per question, the review shows:

- the version answered: its question text, its options in the order shown, which options were correct, and which the learner chose;
- the version number, when that version was saved, and the git commit recorded with it;
- a status: current, superseded by a newer version, or retired.

Everything else the attempt review shows is unchanged: the pages, content blocks and questions served in the order served, the score, percentage, pass mark applied, pass or fail, the start and completion times and the attempt number.

An educator who may view the learner but does not hold the question-viewing permission still opens the attempt. They see the attempt number, start and completion times, score, percentage, pass mark applied and pass or fail, and no question or answer detail.

## Why

SACAA CAR 141.01.17 expects an ATO to reproduce what a learner sat and how it was marked, and SACAA expects a revised question to remain in the system for audit. `sacaa-compliance-4-attempt-review` shows the served paper but states the question wording is today's wording, so an attempt reviewed after a question was reworded would show text the learner never saw, with correctness the learner was never marked against. `sacaa-compliance-content-versions-and-access-3-question-versions` keeps the version each attempt answered. Nothing shows it to an educator. Reviewing an attempt also exposes questions and correct answers, so it falls under the same access rule as the other question-viewing surfaces from `sacaa-compliance-content-versions-and-access-4-question-access`.

An inspector or educator needs to tell three cases apart: the question is unchanged, it has been revised since the learner answered, or it has been taken out of the source. Showing a status next to the version answered covers all three.

## What is settled

- **Answered version, never today's wording.** The review shows the version the attempt pinned at start, for every question, whether or not the question has since changed. It never falls back to the current `FormQuestion` or `QuestionOption` text for a past attempt. This replaces the rule in `sacaa-compliance-4-attempt-review` that question wording is the current wording; that idea's wording rule no longer applies once this spec ships, and the version-backed reader makes the review correct from the day it opens.
- **One reader.** The review reads through the served-paper reader (`sitting_path()`) as made version-backed by `sacaa-compliance-content-versions-and-access-3-question-versions`, so the paper, the options and their correctness all come from the pins. The review does not match answers to versions itself and does not re-derive a shuffle.
- **Version facts shown.** Version number, the time the version was saved, and the git commit recorded with it. These are the facts stored on the version row by `sacaa-compliance-content-versions-and-access-3-question-versions`; this spec adds no new stored data.
- **Three statuses.**
  - Retired: the question is retired (`sacaa-compliance-content-versions-and-access-2-retire-removed-content`). It is served to no one and kept.
  - Superseded: the question is not retired and the version the learner answered is not its latest version.
  - Current: the question is not retired and the version answered is its latest version.
  A retired question shows as retired whatever version was answered. A status is read at the time the review is opened, so the same attempt can show current today and superseded after a later content save.
- **Past versions stay readable.** An attempt that answered a superseded or retired question shows it in full. Superseded and retired questions are marked, never hidden or collapsed.
- **Permission.** Opening a review that shows questions and answers needs the question-viewing permission from `sacaa-compliance-content-versions-and-access-4-question-access`, held through its organisation-scoped role. The existing access to the learner (`VIEW_LEARNER`, `learners_visible_to`) is still required as well; the new permission adds to it and replaces nothing.
- **Audit.** Each open of the full review writes the same kind of audit entry as the other question-viewing surfaces, one per open with no dedupe, superusers included. It follows the `conversation.viewed` precedent: the viewer is the actor, the attempt is the target, the learner is a subject, and the organisation is the learner's.
- **Without the permission.** An educator who may view the learner but lacks the permission gets the score and pass or fail view only, with no question or answer detail anywhere on the page, including no question count by status. Opening that reduced view writes no audit entry, because no question or answer text is shown.
- **Form export unchanged in shape.** The form export keeps its per-question columns in authored order and the "Not asked" cell for an undrawn question. The version actually read by the export is the answered version, as `sacaa-compliance-content-versions-and-access-3-question-versions` already requires; this spec adds nothing to what the export reads.
- **Scope.** QUIZ forms only, as in `sacaa-compliance-4-attempt-review`. The panel placement, framework and educator-interface conventions are those the attempt review set; this spec adds to its page rather than creating a new one.

## Open until the spec

- **Whether the form export carries version numbers.** Recommendation: add one cell per attempt listing the version number answered for each served question, next to the served-order and seed cells, and leave the per-question columns as they are. An inspector then reproduces the paper from the file, and the answer cells stay comparable across attempts. The alternative is no change, which leaves the export unable to say which wording an answer cell refers to.
- **How the retired and superseded marks look and read.** Badge wording and placement, and whether a superseded mark links nowhere or shows the current version's number. Recommendation: a plain badge with the version number answered, and for superseded the latest version number as text, no link, since browsing version history is out of scope.
- **What the reduced view says to a viewer without the permission.** Recommendation: one line stating that question and answer detail needs the question-viewing permission, so the page does not look broken.
- **Whether the quick-view row for an attempt, if `sacaa-compliance-4-attempt-review` adds one, is gated like the full review.** Recommendation: yes, and a quick view that shows no question detail needs no audit entry.

## Out of scope

- Browsing a question's version history outside an attempt.
- Regrading an attempt against a newer version.
- The learner's own results page and `quiz_show_incorrect`.
- Changes to what versions store, to scoring, to shuffling or to drawing.
- The cohort report quiz panel and the content preview, which `sacaa-compliance-content-versions-and-access-4-question-access` gates.
- Frozen whole-content snapshots (`content_snapshots`, paused).
- Retention enforcement.

## Resources

- `spec_dd/1. next/sacaa-compliance-4-attempt-review/idea.md`: the review this spec extends, and the current-wording rule it replaces.
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access-3-question-versions/research_question_version_seams.md`: section 3, the readers of question and option text for a past attempt and the single reader `sitting_path()`.
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_question_versioning_prior_art.md`: staff display of status, version number and date, and the flag when a question is no longer current.
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access-4-question-access/research_question_access_surfaces.md`: the audit log and the `conversation.viewed` precedent.
