# Shuffle quiz pages, questions and answer options

Spec 2 of 4 in the SACAA compliance effort. Read the "SACAA compliance" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

An author can make a QUIZ form present differently on every attempt, through three independent
opt-in knobs:

- shuffle the order of the form's pages;
- shuffle the order of the content blocks and questions within each page;
- shuffle the order of the answer options within each question.

Two further author controls keep a shuffled quiz correct:

- **Position lock on an option.** A locked option stays at its authored position while the
  unlocked options shuffle among the remaining positions. This is for "All of the above" and
  "None of these", which stop making sense when they move.
- **Keep-together group.** A group binds a content block (a stimulus such as a diagram or passage)
  to the questions that depend on it. When the page's children shuffle, the group moves as one
  block and its internal order (stimulus first, then its questions in authored order) is preserved.

A learner sees the shuffled order everywhere: the page sequence, the order within a page, the
option order in the radio, checkbox and dropdown inputs, and the question numbers, which follow the
order served. The shuffle is performed once when an attempt starts and written into the served-paper
record; nothing re-derives it later.

The `fls-content` course-author plugin documents the new authoring and the demo content gains a
shuffled quiz example (all three knobs, one locked option, one keep-together group).

## Why

A quiz with a fixed order lets learners share "question 3 is B" and reconstruct the paper. A
shuffle defeats casual copying and reduces item exposure across cohorts. It is not proctoring and
the authoring documentation says so. No SACAA text mandates shuffling; the client's ATO manual is
the audit reference, and shuffling is common practice for ATO progress tests and end-of-course
exams. See `research_randomization_ux_integrity.md` for the industry comparison (QTI, Moodle,
Canvas, Open edX) that the lock and the group follow.

## What is settled

- Randomisation is opt-in per quiz form and off by default. A form with no knob set, and every
  existing quiz, behaves exactly as today.
- The three knobs are independent: any combination is valid.
- Knobs apply to QUIZ forms only. The content validator rejects a knob (and an option lock or a
  group) on a form with any other scoring strategy. Because a QUIZ form already bans `when`
  conditions, no condition and shuffle conflict arises.
- One seed per attempt, shuffled at attempt start, the result stored in the served-paper record that
  `sacaa-compliance-1-served-paper-record` builds. A retake is a new attempt with a fresh order.
  Reloads, back-navigation and resume show the same order. This child supplies the shuffled
  order; it does not build the record, the path, the resume logic or the scoring change.
- Scoring, results and review read the served paper, never a re-derived shuffle. A shuffle alone
  does not change the score or `max_score`.
- Unlocked options shuffle among the unlocked positions; locked options keep their absolute
  authored positions. A lock on a form that does not shuffle options is a validation error.
- A keep-together group is a contiguous run of content blocks and questions on one page. The
  validator rejects a group that is non-contiguous or spans pages. A group's internal order is
  never shuffled, and a group is one atom in the page-level shuffle alongside ungrouped
  children. Ungrouped children shuffle individually.
- A content block with no group shuffles like any other child. Authors are told to group a
  stimulus with its questions; the validator does not infer groups from adjacency.
- Accessibility: the DOM order of options and questions equals the visual order (WCAG 1.3.2 and
  2.4.3). The three option templates (`inputs/multiple_choice.html`, `inputs/checkboxes.html`,
  `inputs/dropdown.html`) render from the served option order, not from a database `order` query,
  and no CSS reordering is used.
- Authoring lives in the form files (form front matter, page files); validation lives in the
  content schema and validator; `content_save` writes the new fields. Existing rows keep opt-out
  defaults.
- The educator preview and the answer-key lists keep their authored order.

## Open until the spec

- Exact authoring syntax: the keyword names for the three knobs, the option lock and the group;
  whether a page header can override a form-level knob. The research suggests form-level
  `shuffle_pages`, `shuffle_questions` and `shuffle_options`, a `locked` flag beside `correct` on an
  option, and a `group:` string on content blocks and questions, but none of these is fixed.
- Model shape of a group: a string key stored on each member, or a separate group model between the
  page and its children. Whichever is chosen must give `sacaa-compliance-3-question-pools` a
  clean indivisible draw unit.
- Whether a group may sit inside a page-level shuffle that is off, and whether groups can nest.
- Seed algorithm and where the shuffle function lives, within what the served-paper record exposes.
- Validator wording for the lock, group and strategy errors.

## Out of scope

- The served-paper record, path, navigation, resume and scoring changes (`sacaa-compliance-1-served-paper-record`).
- Drawing N questions from a pool (`sacaa-compliance-3-question-pools`).
- Educator per-attempt view and export of the served order (`sacaa-compliance-4-attempt-review`).
- Shuffling on CATEGORY_VALUE_SUM or UNSCORED forms; shuffle combined with `when` conditions.
- Per-question shuffle overrides, shuffling inside a group, difficulty weighting.
- Proctoring, time limits and retake rules.

## Resources

- `spec_dd/1. next/roadmap.md`, the "SACAA compliance" section.
- `spec_dd/1. next/sacaa-compliance/research_form_engine_seams.md` (sections 1, 2, 4, 5 and seam 2).
- `spec_dd/1. next/sacaa-compliance/research_sacaa_requirements.md` (implications).
- `research_randomization_ux_integrity.md` (moved into this directory).
