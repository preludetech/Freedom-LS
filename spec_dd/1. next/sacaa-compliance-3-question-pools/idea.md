# Question pools: draw N questions per attempt

Spec 3 of 4 in the SACAA compliance effort. Read the "SACAA compliance" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

On a QUIZ `Form`, an author sets a `FormPage` to draw N. Each attempt is served N items drawn at
random from that page's questions. The page is the pool. The draw is written into the served paper
(the record `sacaa-compliance-1-served-paper-record` persists at attempt start), so every
reader of the attempt sees the same N items. A retake is a new attempt and draws afresh.

A form with several drawing pages gives a syllabus-weighted paper: one page per syllabus subject,
each with its own N. Pages with no draw are served whole, as today.

A learner never sees an undrawn question: not on the page flow, the results page or the
incorrect-answers list. Nothing in the learner interface lets them browse the pool.

Authors get the draw in the page header of the form files. The demo content gets one pool quiz
(two or more subject pages), and the `fls-content` author plugin documents and exemplifies the
draw key so authors can write one without reading the schema.

## Why

SACAA's own papers are syllabus-weighted draws from a bank; an ATO's internal tests that mirror
that need a fixed number of questions per subject per paper (`research_sacaa_requirements.md`).
A different paper on each retake keeps a learner who failed from simply rehearsing the same
questions. Every surveyed system (Moodle, Canvas, Articulate, QTI) draws a fixed count so the
denominator is common (`research_question_bank_patterns.md`); FLS's pass mark and cohort
comparisons depend on the same thing.

## What is settled

- **The draw unit is the page.** The form file's page header carries `draw: N`. No separate pool
  model and no named pool string. Shared banks and draws keyed on course sections are out of scope.
- **Draw items.** A drawable item is a single question, or a keep-together group from
  `sacaa-compliance-2-shuffle`. A group is drawn whole or not at all; it is never split.
- **N counts items, and every item on a drawing page carries the same number of questions.** A
  drawing page is therefore all single questions, or all groups of the same size. The validator
  rejects a mixed page. This keeps `max_score` equal to N times that size for every attempt, the
  rule the cut fixed. A page that needs a stimulus with two questions and a lone question is split
  into two pages.
- **Validation.** N is at least 1 and at most the number of items on the page. A draw of all items
  is allowed (it only reorders, when `sacaa-compliance-2-shuffle` shuffles are on).
- **Opt-in and QUIZ only.** No draw key means today's behaviour. A draw on a non-QUIZ form is
  rejected at validation.
- **No `when` conditions** anywhere in a form that draws, per the seams research
  (`research_form_engine_seams.md`, section 4): an undrawn source question would silently drop
  the gated item. `sacaa-compliance-2-shuffle` already extends the rule to its own knobs, and the
  draw joins it.
- **Draw at attempt start, once.** The selection is made with the attempt's seed when the attempt
  begins and written to the served paper. Resume, reload and back-navigation read it; nothing
  redraws.
- **Scoring reads the served paper.** `max_score` is the number of served questions, identical for
  every attempt of the form. `FormProgress.scores`, `quiz_percentage()` and `passed()` keep
  their shape. The "outdated score" check on the results page uses the served set, so a drawn
  attempt is not flagged.
- **Draw is uniform and unweighted.** Pools should be homogeneous in difficulty; that is authoring
  guidance, not enforced. Difficulty tiers and stratified draws are out of scope.
- **Order of drawn items** follows the page's shuffle setting from `sacaa-compliance-2-shuffle`;
  with no shuffle they keep authored order.

## Open until the spec

- **Loose content blocks on a drawing page.** A `FormContent` outside any group has no question to
  travel with. Recommendation: the validator requires content on a drawing page to sit inside a
  group, so a stimulus is never served without its questions and never served alone.
- **How the draw reads in the content-save command and the file schema.** Key name and whether
  the page header is the only home. Recommendation: `draw` on the page header, nowhere else.
- **Whether the page's question count in the educator content preview shows the pool size and N.**
  Recommendation: yes, one line, since the preview reads the full path today and would otherwise
  imply every learner sees every question.

## Out of scope

- Drawing by course section (`learner-interface-features-1-question-sections`) and banks shared
  across forms.
- Difficulty-weighted or tag-based draws; score equating.
- Retake waiting periods and time limits.
- Persisting the served paper, scoring on it, and the shuffle knobs and groups: those belong to
  `sacaa-compliance-1-served-paper-record` and `sacaa-compliance-2-shuffle`.
- The educator per-attempt view and export of the draw:
  `sacaa-compliance-4-attempt-review`.
- Frozen copies of question text (`content_snapshots`).

## Resources

- `spec_dd/1. next/sacaa-compliance/research_form_engine_seams.md`, sections 3 (scoring with a
  subset), 5 (authoring), 7 (sections) and 8 (seam 3).
- `research_question_bank_patterns.md` (in this directory): the Canvas fixed `pick_count`, the QTI
  `selection`, and the principle that the resolved draw is persisted at attempt start.
- `spec_dd/1. next/sacaa-compliance/research_sacaa_requirements.md`: syllabus-weighted draws, a
  different paper per retake, bank confidentiality.
