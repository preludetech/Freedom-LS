# Educator revision analytics

Split out of `learner-interface-features-3-revision-questions` when that spec was started: the
user chose to keep educator analytics out of it and give them their own idea.

## What

Educators see how learners do in revision. Three views were named:

- the questions learners miss most often, per course and per section;
- per-option answer counts for a question, so a misleading distractor or a wrong `correct` flag shows up;
- a learner's weak sections, the same signal the learner sees on their revision screen.

## Why

The revision screen tells a learner where they are weak. Educators get none of that today, so they
cannot spot a badly written question, a section most of a cohort struggles with, or a learner who
needs help.

## What is settled

- This builds on `learner-interface-features-3-revision-questions`, which stores an append-only
  review log of revision answers and the per-learner, per-question schedule. This idea reads that
  data; it does not define it.
- Revision answers are kept apart from `QuestionAnswer`, so these views do not mix with quiz reports
  and exports.

## Open

- Which of the three views come first, and where each sits in the educator interface (course,
  cohort or learner pages).
- Whether flashcard reviews (`learner-interface-features-4-flashcards`) appear beside questions.
- How a question an author has edited or removed shows in the history.
- Whether any of it belongs in exports.
