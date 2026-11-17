# Served paper record

Spec 1 of 4 in the SACAA compliance effort. Read the "SACAA compliance" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Every quiz attempt records, at the moment it starts, the exact paper it serves: a seed, the ordered
pages, the children of each page in order, and the option order of each question. The learner's
navigation and the quiz score then read that record, not the live form.

- The record lives on the attempt (`FormProgress`) and is written once, at attempt start. After
  that it never changes for the life of the attempt.
- The path builders (`compute_path`, `frozen_path`, `sitting_path`) build from the record.
- Next, previous, resume and page-jump navigation follow the served order. URLs keep the authored
  page number. The learner sees their position in the served order ("page N of M").
- Quiz scoring counts only the served questions: `compute_quiz_scores`, `score_quiz`,
  `get_incorrect_quiz_answers`, the learner results page's "outdated score" check, and the report
  recompute.
- With no randomisation switched on, the served paper equals the authored order. Every existing
  quiz behaves exactly as it does today.
- An attempt that has no stored paper (started before this ships) falls back to authored order.

This spec ships no shuffle and no draw. It is the foundation the three sibling specs
(`sacaa-compliance-2-shuffle`, `sacaa-compliance-3-question-pools`,
`sacaa-compliance-4-attempt-review`) build on.

## Why

The client's training organisation is audited by SACAA against its own manual. The research
(`research_sacaa_requirements.md`, "Implications") finds the audit needs the exact paper a student
sat, in order, reproducible years later, with each answer and mark. Today nothing about an attempt's
order is stored (`research_form_engine_seams.md:16`), and scoring walks the whole form, so a
later edit or a drawn subset would corrupt old and new scores alike.

Doing the record first, with no visible change, makes the later shuffle and draw safe. The seams
research puts the whole foundation in one choke point: `compute_path` and its two siblings
(`research_form_engine_seams.md:31`, `:81`). It also finds the one hazard to design around: resume
and page-jump compare authored page numbers with `>` and `<`, which is wrong once the served order
differs from the authored one (`:26-27`).

## What is settled

- One seed per attempt. The served paper is persisted at attempt start. A retake is a new attempt
  with its own record.
- The record stores the realised order explicitly (ordered pages, children, option order), not only
  the seed. Scoring, results, export and review read the record and never re-derive an order
  from the seed. The paused research prefers explicit storage as unambiguous and robust to later
  edits (`research_randomization_ux_integrity.md` section 3.2, "Audit Trail Value").
- The record holds references to live pages, questions and options, as the rest of the engine
  does. Frozen copies of question text are out of scope.
- URLs keep authored page numbers. Position shown to the learner comes from the served order. The
  existing split of "authored index in the URL, position on screen" is the hook
  (`research_form_engine_seams.md:25`).
- "Furthest page reached" and resume are reinterpreted as positions in the served order, not
  authored indexes (`research_form_engine_seams.md:26`).
- Scoring is over the served questions only. `max_score` is the total of the served questions.
  `quiz_percentage` and `passed` need no change once `max_score` is right
  (`research_form_engine_seams.md:41`).
- All surfaces that show what the learner saw read through one function, `sitting_path`
  (`research_form_engine_seams.md:81`).
- Existing attempts with no stored paper fall back to authored order, so no old attempt changes
  its score or its pages.
- Quizzes only. Quiz forms already forbid `when` conditions, so the record carries no
  conditional-path state.
- Randomisation stays off by default and opt-in per form; this spec adds no author-facing flag.

## How it is exercised

Until `sacaa-compliance-2-shuffle` lands, every attempt is served in authored order, so the
feature has no visible effect. It is proven by tests that inject a non-authored served paper:

- An attempt round-trips its served paper: start an attempt, read the record back, and the
  pages, children and option order are exactly what was written.
- With an injected order, next, previous, resume and page-jump all follow it, URLs carry authored
  numbers and the learner sees position, and a refresh or resume shows the same paper.
- With an injected order that omits questions, scores and `max_score` count only the served
  ones, the incorrect-answers list leaves out unserved questions, and the results page does not
  report an outdated score.
- With no stored paper, an attempt behaves as authored order.

## Open until the spec

- The exact JSON shape of the record, and whether the seed is a separate field.
- Whether the record is written eagerly when the attempt is created or lazily on first load,
  given the attempt may be created in more than one place (learner views and
  `course_applications`, which share the page flow).
- Whether an in-flight attempt (started, not completed) at deploy time gets a record written
  from the authored order at the next request, or stays record-less and falls back.
- How the record names pages, questions and options so it survives content edits (the models use
  uuids; `FormProgress.asked` already stores string uuids).
- Handling a served item deleted from the live form after the attempt started (`QuestionAnswer`
  protects the question, but pages and options may be removed).
- The exact positions semantics for `furthest_page_reached`, and whether it stays stored in
  authored numbers and is translated on read.
- Whether the educator preview (`full_path`) and the admin answer groups follow the record in
  this spec or are left to `sacaa-compliance-4-attempt-review`.
- Rebase plan around `form-engine-branch-logic-2-and-conditions`: both change `conditions.py`,
  so whichever lands second rebases (`research_form_engine_seams.md:101`).

## Out of scope

- Any shuffle, option lock, keep-together group or authoring flag
  (`sacaa-compliance-2-shuffle`).
- Drawing N questions from a page (`sacaa-compliance-3-question-pools`).
- The educator per-attempt view and the served order in the form export
  (`sacaa-compliance-4-attempt-review`).
- Frozen copies of question text (`content_snapshots`, paused), exam time limits, retake waiting
  periods.

## Resources

- `spec_dd/1. next/sacaa-compliance/research_form_engine_seams.md`: sections 1-3, 6 and 8 (seam 1).
- `spec_dd/1. next/sacaa-compliance/research_sacaa_requirements.md`: "Implications for FLS
  randomisation", the per-attempt record list.
- `spec_dd/1. next/sacaa-compliance-2-shuffle/research_randomization_ux_integrity.md`:
  sections 3 and 6.4 (seed per attempt, persisting the realised order).
