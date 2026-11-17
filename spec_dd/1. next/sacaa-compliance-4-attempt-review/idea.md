# Educators review one learner's quiz attempt

Spec 4 of 4 in the SACAA compliance effort. Read the "SACAA compliance" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

An educator opens one learner's quiz attempt (one `FormProgress`) from the learner area and sees the
paper that learner was served and how it was marked:

- every page, content block and question served, in the order served;
- each question's options in the order shown;
- the learner's answer to each question and whether it was correct;
- the score, the percentage, the pass mark applied, and pass or fail;
- when the attempt started and when it was completed, and its attempt number.

A question that was not drawn for this attempt is not shown. The existing form export gains the
served order and the seed, so an inspector can reproduce the paper from the file.

## Why

SACAA's only citable record rule is CAR 141.01.17: an ATO keeps "detailed student records" showing
that the requirements were met, for at least 5 years, and produces them on request. In an audit
that means an attempt can be reproduced: the exact paper the learner sat and how it was marked.
`sacaa-compliance-1-served-paper-record` stores that paper. Nothing lets an educator read it: the
only per-attempt view today is the Django admin's `answer_groups`, which walks the authored form
and shows undrawn questions as "not asked". The educator interface has no attempt viewer at all, so
this is a new surface, not a patch.

## What is settled

- **One reader.** The review and the export read the attempt through the served-paper record via
  `sitting_path()`, which `sacaa-compliance-1-served-paper-record` makes the single reader. They
  never re-derive a shuffle and never walk the whole form. Scores, percentage and pass/fail come
  from the stored result, and "pass mark applied" is the form's `quiz_pass_percentage`.
- **Works before the siblings ship.** When `sacaa-compliance-2-shuffle` and
  `sacaa-compliance-3-question-pools` have not shipped, or the quiz is not randomised, the served
  paper is the authored order and every question is shown. The review is correct for a quiz that
  has never been randomised.
- **Scope: QUIZ forms.** The review is for quiz attempts, where a pass mark applies.
- **Lives in the learner area.** The view is reached from a learner and sits in
  `freedom_ls/educator_interface/panels/learner/`, which `educator-interface-refactor-5-learner`
  creates. It is built from the panel framework (`Skill(fls-dev:panel-framework)`) and follows
  `Skill(fls-dev:educator-interface)`.
- **Permissions follow the existing educator access to the learner.** An educator who may view the
  learner (`VIEW_LEARNER`, `learners_visible_to`) may open that learner's attempts, and nobody
  else can. No new permission is introduced.
- **Export.** The existing form export (`freedom_ls/form_engine/exports.py`) gains the served order
  and the seed for each attempt. Its per-question columns stay in authored order, and the "Not
  asked" cell for an undrawn question stays.
- **Question wording is the current wording.** Question text shown is the form's current
  text. Freezing text against later edits is out of scope (below), so the review shows the
  question identifiers served and the current wording.

## Open until the spec

- Where the attempt opens from: a panel on the learner instance page (the Courses tab or Overview),
  or its own instance view. Which table holds the link, and whether the educator-interface
  skill's Placement table gains a row. The skills do not settle this.
- Whether the quick view for an attempt row is wanted.
- Whether a design pass is wanted for the review page. The spec decides.
- Whether the export's served-order column is one cell per attempt or a second sheet, and how the
  seed is written. Decided against the export's present shape.
- Whether the Django admin's attempt answers (`answer_groups`) move onto the same reader in this
  spec or stay as they are. `sacaa-compliance-1-served-paper-record` may already have moved them.
- Whether opening an attempt writes an audit entry. The glossary has a `viewed` verb for "a read
  worth auditing" (`conversation.viewed` is the precedent). Decide against the audit log's rules.

## Out of scope

- Frozen question text when content is edited later (`content_snapshots`, paused).
- PDF export.
- Retention enforcement: the 5-year keep and deletion rules.
- Exam time limits and retake waiting periods.
- Any change to scoring, shuffling or drawing: those belong to
  `sacaa-compliance-1-served-paper-record`, `sacaa-compliance-2-shuffle` and
  `sacaa-compliance-3-question-pools`.
- Reviewing attempts of non-quiz forms or course applications.

## Resources

- `spec_dd/1. next/sacaa-compliance/research_sacaa_requirements.md`: the per-attempt record SACAA
  would want, 5-year retention, export for inspectors.
- `spec_dd/1. next/sacaa-compliance/research_form_engine_seams.md`: section 6 (surfaces that
  assume authored order) and section 8, seam 4.
- `spec_dd/1. next/educator-interface-refactor-5-learner/idea.md`: the `panels/learner/` layout
  this view lands in.
- `claude_plugins/fls-dev/skills/educator-interface/SKILL.md` and
  `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`.
