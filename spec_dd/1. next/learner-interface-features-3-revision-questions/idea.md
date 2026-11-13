# Revision questions

Spec 3 of 5 in the Learner interface features effort. Read the "Learner interface features" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Learners revise questions from the course sections they have finished. When a learner finishes a
section, that section's questions join a bank of questions they can practise. A revision screen shows
them questions, scheduled by spaced repetition, and records what they got right and wrong over time.

When a learner gets a question wrong, the revision screen gives a short explanation of why and
points them to the section to revise. Sections where a learner keeps getting things wrong are
highlighted, so their revision is guided.

## Why

Practice testing and spacing are the best-supported study methods in the research, and learners
rarely choose them on their own. Today a quiz is taken once or retaken whole, and the learner is
never brought back to material after they pass. Authors have no way to say why a wrong answer is
wrong, and learners get no hint of where to go next.

## What is settled

- The source idea asks for: a question bank tied to parts of a course; questions added to a learner's
  bank when they finish the section; a revision UI; right and wrong tracked over time; pointers to the
  section to revise and short explanations when an answer is wrong; spaced-repetition science to
  choose what to show; weak sections highlighted.
- This spec depends on `learner-interface-features-1-question-sections`, which gives a question the
  section it tests. This spec does not define that link.
- Flashcards with confidence ratings belong to `learner-interface-features-4-flashcards`, which
  follows this spec. This spec builds the scheduling and revision screen that spec reuses, and does
  not build flashcards.
- A section completed by test-out counts as finished. `learner-interface-features-2-test-out` adds
  that kind of completion. Whichever of the two specs lands second makes test-out completion add
  the section's questions to the bank.
- Facts about today's code (from the research):
  - `QuestionOption` has no explanation or feedback field, and the form file schema rejects extra keys.
  - A question belongs to exactly one form page and cannot be shared across forms.
  - `QuestionAnswer` is unique per sitting and read by reports, exports and completion receivers,
    so revision answers stored there would pollute them. `FormProgress` brings page flow and pass marks.
  - Right or wrong is recomputed from the current `correct` flags, not stored, so editing an option
    re-marks history.
  - Free-text questions cannot be marked automatically; `scoring.is_quiz_answer_correct` handles the
    choice types.
  - `form_engine/templates/form_engine/question.html` renders one question and is already shared by two shells.
  - The loader keeps a question's row only while its `uuid` stays in the source file.
  - Nothing today shuffles options, pools questions or stores explanations.

## Open until the spec

Each is decided in `/sdd:spec_from_idea`, which does its own research.

- **Scheduler.** FSRS via `py-fsrs` (MIT, one pure-Python dependency, per-learner-per-question state
  and a review log), Leitner boxes (simple, readable by the learner, same schedule for every item), or
  a mastery-level rule (Khan-style levels, retire after N correct). Whether one scheduler serves
  this spec and `learner-interface-features-4-flashcards` is part of the question. See section 3 and 4 of `research_spaced_repetition.md`.
- **Mapping right and wrong to ratings.** Options: wrong is Again and right is Good; a one-tap
  "I guessed" gives Hard; an optional Easy. No official guidance exists. See section 2 of `research_spaced_repetition.md`.
- **Explanation placement.** Per question, per wrong option, or both; required or optional; shown
  after each answer or after the set (delayed feedback did better in lab MCQ work). Writing them is the
  authors' real cost. See `research_learner_features.md` section 2 and point 4 of `research_question_model.md`.
- **Which question types qualify.** Only the choice types that score today, or more.
- **Backlog after a break.** Session size cap, weakest first, hold back new questions while many are
  overdue, or other handling. See section 5 of `research_spaced_repetition.md`.
- **Streaks.** None, forgiving ones, or something else.
- **Interleaving.** Mix sections by default, or let learners choose by section. Learners prefer blocking.
- **Option shuffling.** Shuffle each time or keep authored order, given that learners memorise the
  answer or its position. Related to the paused `compliance-form-randomization`, which is unbuilt.
- **Learner history when an author edits or removes a question.** Keep, reset, or archive the
  history; what counts as a substantial rewrite; what the loader does with a dropped question
  (unconfirmed). See points 2 and 10 of `research_question_model.md`.
- **Educator analytics.** Most-missed questions, per-option counts and per-learner weak sections: in
  this spec, or left for later.
- **Where the revision UI lives** in the learner interface, and how it ties to the course player.
  See point 9 of `research_question_model.md`.
- **How the bank is drawn**: from the section's existing quiz questions or from a separate bank form
  (point 3 of `research_question_model.md`), and what happens to a section the learner has not reached.
- **How weakness is measured and shown** per section, for example as levels or as a simple flag.

## Out of scope

- Flashcards and confidence ratings (`learner-interface-features-4-flashcards`).
- Linking a question to its section (`learner-interface-features-1-question-sections`).
- The pretest and recording a skip (`learner-interface-features-2-test-out`).
- The other features in section 4 of `research_learner_features.md`.

## Resources

- `spec_dd/1. next/learner-interface-features-3-revision-questions/research_spaced_repetition.md`:
  `py-fsrs` facts and fit to model fields, the MCQ-to-rating mapping, Leitner, one scheduler for
  questions and flashcards, backlog handling.
- `spec_dd/1. next/learner-interface-features/research_question_model.md`: today's form models,
  scoring, loader, answer history and the question UI. Points 2 to 5 and 9 apply here.
- `spec_dd/1. next/learner-interface-features/research_learner_features.md`: section 2 holds the
  learning science, how other products do revision, what learners dislike, and the design questions.
