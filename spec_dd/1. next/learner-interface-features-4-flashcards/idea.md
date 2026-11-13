# Flashcards

Spec 4 of 5 in the Learner interface features effort. Read the "Learner interface features" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Authors add flashcards to course sections. A learner flips a card to see the answer, then rates how
confident they were. The revision schedule built by `learner-interface-features-3-revision-questions`
brings the card back when it is due.

## Why

The source idea says: "Perhaps include flashcards as well. With confidence levels." Flashcards test
recall of facts and terms, where revision questions test application. Learner research (Osmosis, a
vendor source) advises flashcards for recall and questions for application. The product owner decided
flashcards are a separate, later spec in this effort, built on the revision work rather than inside it.

## What is settled

- Flashcards come after `learner-interface-features-3-revision-questions` and build on what it ships: the
  revision schedule, the per-learner record of what has been revised, and the revision session.
- A flashcard is self-graded. The learner flips it and rates themselves, so it has no `correct`
  answer. Today's `QuestionOption.correct` and the quiz scorer cannot mark it.
- Learners rate their confidence after flipping a card. This is the source idea's "confidence levels".
- Flashcards belong to course sections, as revision questions do. What a section is, is settled by
  `learner-interface-features-1-question-sections`, not here.
- Today's code: `FormQuestion` has 12 types, all answered by selecting or typing, and a question
  belongs to exactly one page of one form (`research_question_model.md`, sections 1 and 2).
  `QuestionAnswer` is unique per sitting and is read by reports, so a flashcard rating must not be
  stored there.
- Today's code: no explanation, shuffle or pool exists. Nothing reads `FormQuestion.tags` or `meta`.
- Revision-record, session and scheduler choices belong to `learner-interface-features-3-revision-questions`.
  This spec reuses them or says why it cannot; it does not reopen them.

## Open until the spec

Each is for `/sdd:spec_from_idea` to settle in its own research.

- **New question type or separate card model.** Options: a new `QuestionType` on `FormQuestion`, or a
  separate flashcard model. `research_question_model.md`, implication 5, names both and notes
  flashcards would need one of them. A new type inherits form pages and loading but sits in a form
  that has quiz scoring; a separate model avoids that and is a new thing to author and load.
- **Confidence scale.** Options: Again / Hard / Good / Easy (FSRS native), or Brainscape-style 1-5,
  which collapses to FSRS as 1 Again, 2-3 Hard, 4 Good, 5 Easy. Also fewer buttons (Again / Good / Easy or
  Again / Hard / Good), since Anki users misuse Hard. `research_spaced_repetition.md`, section 4.
- **Shared scheduler and session.** Whether cards use the question scheduler and one mixed session,
  or have their own session, or a separate rule (a mastery rule for questions, spacing for cards).
  The research finds one FSRS scheduler can serve both, with an item type on the record. Also how a
  mixed session is ordered and capped. `research_spaced_repetition.md`, sections 4 and 5;
  `research_learner_features.md`, "Design questions for FLS".
- **Authoring and tie to a section.** How an author writes a card (file format, front and back, any
  media or markdown), how it is loaded, how it names its section, and whether it keeps a stable id
  across edits, as questions do with a `uuid`. Also what happens to a learner's history when a card is
  edited or removed, the same question `learner-interface-features-3-revision-questions` faces for questions.
- **Which sections' cards a learner sees.** Options: only sections the learner completed (as for
  questions), cards from any section the learner has reached, or cards from skipped sections too. How
  test-out completion counts is owned by `learner-interface-features-2-test-out`; this spec must follow
  whatever the two siblings settle.

## Out of scope

- Learner-written cards. Research found no demand data for them (`research_learner_features.md`, section 2, Gaps).
- Choosing the scheduler or building the revision session. `learner-interface-features-3-revision-questions` owns both.
- Section links on questions. `learner-interface-features-1-question-sections` owns them.
- Explanations on quiz options and educator analytics for questions, unless the sibling ships them.
- The other features in section 4 of `research_learner_features.md`.

## Resources

- `spec_dd/1. next/learner-interface-features-3-revision-questions/research_spaced_repetition.md`: FSRS
  and Leitner, rating mapping, one scheduler for questions and flashcards (section 4), session rule
  and backlog handling (section 5).
- `spec_dd/1. next/learner-interface-features/research_question_model.md`: the form model family, how
  questions are authored and loaded, and implication 5 on flashcards.
- `spec_dd/1. next/learner-interface-features/research_learner_features.md`, section 2: learning
  science, products compared, what learners dislike (backlog, ease hell), design questions.
