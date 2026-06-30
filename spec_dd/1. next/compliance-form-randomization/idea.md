# Quiz / form randomization

Let authors randomize how an assessment is presented, so each learner attempt sees the
questions in a different order and/or a different subset — instead of the current behaviour
where every learner sees the identical full set in the same authored order.

## Problem

Today a quiz is a `Form(strategy=QUIZ)` made of ordered `FormPage`s, each holding ordered
`FormContent` (markdown, e.g. a diagram) and `FormQuestion`s. The order is fixed and the full
set is always shown. For compliance / examination use this is weak: learners can share a fixed
question-and-answer sequence, and there is no way to draw a smaller exam from a larger bank.

We want randomization to be **opt-in per form** — existing quizzes keep working untouched.

The hard constraint: some questions depend on associated content (a diagram, a passage). The
content block and the questions that refer to it must **stay together as a group** and keep their
relative order even when everything around them is shuffled. A question that says "refer to the
diagram above" must never be separated from its diagram.

## Scope (V1)

Four independent, opt-in randomization knobs on a `Form`:

1. **Shuffle page order** — present `FormPage`s in a random order per attempt.
2. **Shuffle questions within a page** — randomize item order inside a page, respecting
   keep-together groups (below).
3. **Shuffle answer options** — randomize `QuestionOption` order within a question, with
   per-option position locking for options that can't move (see pitfalls).
4. **Draw a random subset from a bank** — author defines a pool of questions; each attempt is
   served a fixed-size random subset rather than the whole pool.

All four default to off. A form opts into any combination.

### Keep-together grouping

Introduce a sub-page **group** primitive (a section between `FormPage` and its items) that binds a
`FormContent` stimulus to the specific questions that depend on it. A group is the atomic unit of
shuffling: when its surroundings are reordered, the group moves as one block and its internal
order is preserved. This mirrors QTI's nested `assessmentSection` and Canvas New Quizzes' Stimulus
type. Subset draws must include or exclude a whole group together — a dependent question can never
be drawn without its stimulus.

(The current positional-adjacency link between a `FormContent` block and its question becomes an
explicit relationship via the group.)

### Per-attempt stability & audit

Randomization must be **stable within an attempt** (reloads, back-navigation and resume show the
same order/subset) and **reproducible for review**. Seed the shuffle once per attempt and persist
the **realized order/selection** (the exact pages, questions, and option orders the learner saw).
Scoring, educator review, and compliance audit read from this record, not from a re-derived
shuffle. For audit contexts this "what the learner actually saw" record is a hard requirement.

### Scoring

Subset draws use a **fixed draw count**, so `max_score` stays constant across learners (every
attempt is scored out of the same denominator) and cross-attempt / cohort comparisons remain
valid. Order shuffling alone does not affect scoring. The existing `FormProgress.scores`
(`{score, max_score}`) shape and `quiz_percentage()` / `passed()` should not need to change.

## Pitfalls to handle (from research)

- **Positional options** — "All of the above", "Both A and B", "None of these" break when options
  shuffle. Support per-option position locking; advise authors to lock or redesign such options.
- **Cross-question references** — "building on the previous question" breaks under shuffle; the
  keep-together group is the supported way to preserve valid relative references.
- **Accessibility** — the DOM/reading order must match the shuffled visual order (WCAG 1.3.2 /
  2.4.3). Templates render from the realized-order record, not from DB `order`.
- **Integrity, honestly framed** — randomization reduces casual copying and item exposure; it is
  not proctoring and should not be sold as such.

## Out of scope / deferred

- Wrong-answer remediation, retry-with-a-different-variant, mastery gating — these live in the
  sibling `compliance-exam-remediation` spec. This spec stays narrow and builds only what
  randomization needs. (Note the overlap: both touch a "pool of questions" concept; the remediation
  spec will define its own primitives and may later converge — that convergence is not a goal here.)
- Difficulty tagging / stratified draws, score equating across difficulty.
- Shared cross-form banks (V1 pools belong to a single form).
- Tag-based or topic-area draws.

## Design directions to firm up in the spec

Flagging model-layer choices so the spec author picks deliberately:

- **Group model shape** — a new `FormGroup`/section model owning `order` and a "lock internal
  order" flag, with `FormContent`/`FormQuestion` pointing at it; ungrouped items stay directly on
  the page. How groups interact with the subset draw (group as the draw unit when it contains a
  stimulus).
- **Bank / pool shape** — is the pool the whole page, a group, or an explicit pool object the form
  draws from? How `draw_count` is expressed, and where pool membership is recorded.
- **Per-attempt record** — store an explicit `realized_order` (and/or seed) on `FormProgress`;
  `QuestionAnswer` currently records no "served set", so this is new.
- **Authoring syntax** — current quizzes are YAML/markdown files where order comes from
  file/in-file position. Pools, groups, draw counts, shuffle flags and per-option locks need a
  markdown-friendly authoring representation that doesn't explode the files or break existing forms.
- **Educator review surface** — completed-attempt views must reconstruct the learner's actual
  order/subset from the realized-order record.

## Research pointers

- `research_question_bank_patterns.md` — how Moodle / Canvas / Articulate / QTI / aviation CBTs
  model banks and random draws; selection mechanics, served-set recording, scoring fairness,
  authoring ergonomics, and concrete FLS model suggestions.
- `research_randomization_ux_integrity.md` — what to randomize independently, stimulus
  keep-together grouping, per-attempt seeding & audit, integrity rationale and limits, and the
  shuffling pitfalls above with their fixes.
