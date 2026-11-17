# Research: best practices for persisting the served paper and scoring only served items

Question: what are the established practices for persisting the exact paper (item and option
order) served in a randomised assessment attempt, and scoring only those items? This builds on
`research_form_engine_seams.md`, `research_sacaa_requirements.md` and
`research_randomization_ux_integrity.md` (sections 3 and 6.4) and does not repeat them. Code
references are under `freedom_ls/` at HEAD 53fb74dfe.

## 1. What mature engines actually do

### Moodle quiz (the closest analogue, read from source)

- **The realised order is stored explicitly. No seed is stored.** At attempt start,
  `quiz_start_new_attempt` shuffles slots with PHP's unseeded `shuffle()` and writes the result to
  `quiz_attempts.layout` as a comma list of slot numbers, with `0` as a page break
  (`mod/quiz/locallib.php`). Moodle never re-derives an order. The stored layout is the only
  source of truth for navigation and review.
- **Option order is stored per question, in the attempt's first step.** The multichoice
  `start_attempt` writes `_order` (the answer ids in the order shown) to step 0, and
  `apply_attempt_state` and `init_order` read it back on every later request
  (`question/type/multichoice/question.php`). The ids are stable row ids, not positions.
- **A drawn ("random") question is fixed at start.** The pick is made once in
  `quiz_start_new_attempt` and stored as that slot's question. It is never re-picked.
- **The mark each served item is worth is stored per attempt.** `question_attempts.maxmark` is
  written when the question is added to the usage ("Need to store maxmark because it could come
  from anywhere", Question Engine 2 design). The attempt total is summed over the attempt's own
  slots, so it covers exactly what was served.
- **Edits after the attempt are tolerated on read.** If an option id in `_order` no longer exists,
  `apply_attempt_state` puts in a "deleted choice" placeholder worth 0 rather than failing. Moodle
  also hides questions that attempts use instead of deleting them, and regrading to a new question
  version remaps old option ids onto new ones (`update_attempt_state_data_for_new_version`).
- **Everything is written in one go, inside attempt creation.** The layout, the drawn questions and
  every question's first step are written together before the learner sees page 1.

### IMS QTI results reporting (the interchange standard)

- Item results "must relate only to items that were selected for presentation as part of the
  corresponding test session", and "all items selected for presentation should be reported". This
  is the standard's version of "score only the served items".
- `itemResult.sequenceIndex` "must be used to indicate the position of the item within the specific
  instance of the test". Position is per attempt, not authored.
- "When shuffling is in effect, the sequence of choices should be reported" (`choiceSequence`, a
  list of choice identifiers). The served option order belongs in the record as identifiers.

### Open edX capa (the counter-example)

- Open edX stores a per-student `seed` in user state, set once, and re-derives the choice shuffle
  and variant from it on each render. That only works because the problem definition is treated as
  stable. When it is edited the student's order changes. This is the fragility the effort already
  ruled out ("store the realised order, not only the seed").

## 2. Practices that change the spec

### 2.1 The seed is optional. Make it provenance only.

Moodle, the most widely audited open engine, stores no seed at all. QTI reports no seed. The
realised order is what an auditor needs. Recommendation:

- The record's authority is the explicit lists. A seed, if kept, is a provenance field that nothing
  reads to rebuild an order. The spec should say so in one sentence so no later spec is tempted to
  re-derive.
- Spec 1 shuffles nothing, so it has no seed to write. The settled decision says "one seed per
  attempt". The least-surprise shape is a nullable `seed` key inside the record (or a nullable
  field) that spec 1 leaves null and `sacaa-compliance-2-shuffle` fills. Do not generate a random
  seed in spec 1 that nothing uses.

### 2.2 Shape: ids in list order, versioned, one document

All three engines name items by a stable identifier and carry order as list position. A shape that
matches the settled decisions and the existing `asked` convention (string uuids):

```json
{
  "version": 1,
  "seed": null,
  "pages": [
    {"id": "<page uuid>",
     "children": ["<content uuid>", "<question uuid>", "..."]}
  ],
  "options": {"<question uuid>": ["<option uuid>", "..."]}
}
```

- `children` mixes content and questions in one list, because `FormPage.children()` shares one
  order space (seams 1). The record does not need a type tag: the live tree says which is which.
- `options` is keyed by question so a question's order can be looked up without walking pages. It
  holds every choice question served, shuffled or not. That makes the record complete on its own,
  which is what QTI `choiceSequence` and Moodle `_order` do.
- A `version` key costs nothing and lets spec 3 (draws) or spec 4 (review) evolve the shape without
  guessing. Validate it with a pydantic model on write and on read. That is the project's existing
  schema tool, and it keeps the JSON free of `Any`.
- Drawn-but-unserved questions are simply absent. Spec 3 needs no extra key for "unserved".
- Per-item mark: FLS scores every quiz question as 1 (`compute_quiz_scores`, models.py:607-617),
  so no `maxmark` per item is needed now. If weighted marks ever arrive, Moodle's practice is to
  copy the mark into the record at start. Note it as a later extension, not spec 1 work.

### 2.3 Write once, idempotently, under concurrency

Moodle writes the paper inside attempt creation. FLS chose a lazy write on the next request
(answers.md), because attempts are created in two places (`learner_progress/attempts.py:94`,
`course_applications/views.py:119`) and in-flight attempts need a record too. Done naively, a lazy
write can lose a race: two tabs or a double-click both see no record and both write. Once spec 2
shuffles, the two writes differ. Practices:

- Write with a conditional update that only succeeds while the field is null, for example
  `FormProgress.objects.filter(pk=..., served_paper__isnull=True).update(served_paper=...)`, then
  re-read the row. Whoever loses the race reads the winner's paper. No lock is held across the
  request, and both callers converge on one paper.
- Route every read through one accessor (for example "the served paper of this attempt, written if
  missing"). `current_path` and `sitting_path` are the only entry points, so the lazy write lives
  there or just before them. No caller may build a paper and use it without persisting it first.
  If one did, the learner could see an order that was never recorded.
- Enforce immutability in code, not only by convention. Reject a write when the stored value is
  non-null and differs, and add a test that a second write is a no-op. "Written once" is the
  property the audit relies on.
- Completed attempts with no record must **not** get one lazily. Writing authored order onto an
  old completed attempt would claim a paper that was never recorded at the time. They keep the
  existing `asked` / `full_path` fallback. The spec should limit the lazy write to incomplete
  attempts.

### 2.4 Navigation reads positions, URLs keep authored numbers

Moodle's page parameter is a position in `layout`. FLS settled on keeping authored numbers in the
URL. That only works with one translation table, built from the record, from authored number to
served position and back, so that every comparison (`next_page_number`, `previous_page_number`,
`first_page_number_at_or_after`, resume, `build_page_links`'s `number <= limit`) compares
positions, never authored numbers. Practice from Moodle: "furthest reached" and "current page" are
stored and compared in served space. If `furthest_page_reached` stays in authored numbers (open
question), every reader must translate it. The fewer readers, the safer. Storing it as a position
is simpler, but it changes the meaning of an existing column for in-flight attempts. The spec must
pick one and test the in-flight case.

### 2.5 Score only what was served, and refuse what was not

- QTI and Moodle both bound scoring by the served set. In FLS that means `compute_quiz_scores`,
  `get_incorrect_quiz_answers` and the reports recompute iterate the record's questions (minus any
  deleted since, per answers.md), not `form.pages.all()`. Scores are independent of order, so
  iterating in served order is for display only (as `research_randomization_ux_integrity.md` 6.4
  notes).
- One gap the effort's research does not mention: **the answer-save path must reject a question id
  that is not in the served paper.** QTI's "only items selected for presentation" applies to
  responses as well as results. Today `complete()` deletes off-path answers at the end
  (models.py:461). With a record, an answer to an unserved question is a tampered or stale POST, and
  the save should refuse it (422 per project convention), not store it and clean up later. This
  matters most after spec 3. Spec 1 is where the check belongs, because it owns the record.
- Load answers once with `prefetch_related("selected_options")` and score in memory. The current
  loop runs `self.answers.get(...)` per question (models.py:621), which is N+1 and gets worse with a
  record. That is incidental, but the scoring loop is being rewritten anyway.

### 2.6 Relationship to `asked` and `frozen_path`

- `frozen_path` filters the live tree by the `asked` id **sets** and then orders by authored order
  (conditions.py:231-244). It throws away order, so it cannot be reused as-is for the served paper.
  The served-paper builder must order by the record's lists.
- For a quiz, served equals asked (quizzes have no conditions), so `asked` becomes redundant for
  attempts that have a record. Keep writing `asked` at `complete()` for non-quiz forms and for
  continuity, and decide in the spec which wins in `sitting_path` when both exist. Recommendation:
  for quizzes, the record wins. The two must never disagree, and that can be asserted in a test.

### 2.7 Deleted items

The settled decision is to skip deleted pages and options on read and shrink `max_score`. Moodle
does the opposite (a 0-mark "deleted choice" placeholder, and questions are hidden, not deleted).
The spec should record two consequences of skipping:

- If the deleted option was the one a learner picked, or the correct one, a recompute changes that
  question's correctness. The learner results "outdated score" check will then flag the attempt.
  That is honest, but the spec should state it is expected.
- The record still holds the deleted id, so the audit trail keeps evidence that the item was
  served. The record is never rewritten to drop it. Skipping happens only in the readers.

## 3. Suggested test additions (beyond the idea's list)

- Two concurrent first requests on a record-less incomplete attempt end with one stored paper, and
  both responses use it.
- A completed attempt with no record is not given one on read.
- An answer POST for a question absent from the injected paper is refused, and no `QuestionAnswer`
  is written.
- An option rendered for a choice question follows the record's option order (inject a reversed
  order) on all three input templates (`multiple_choice`, `checkboxes`, `dropdown`).
- An injected record with an unknown `version` or a malformed shape fails loudly, not silently
  falling back to authored order.

## References

- Moodle source, quiz attempt start and layout: https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/mod/quiz/locallib.php
- Moodle source, multichoice `_order` in first step: https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/question/type/multichoice/question.php
- Moodle source, `question_attempt` maxmark: https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/question/engine/questionattempt.php
- Moodle Question Engine 2 design (maxmark stored per attempt): https://docs.moodle.org/dev/Question_Engine_2:Design
- Moodle question engine overview: https://docs.moodle.org/dev/Overview_of_the_Moodle_question_engine
- IMS QTI v2.2 Results Reporting (sequenceIndex, items selected for presentation, choiceSequence): http://www.imsglobal.org/question/qtiv2p2/QTIv2p2-Results-InfoBindModelv1p0/imsqtiv2p2_result_v1p0_InfoBindv1p0.html
- IMS QTI 3.0 Results Reporting binding: https://www.imsglobal.org/sites/default/files/spec/qti/v3/rr-bind/index.html
- Open edX per-student seed in capa (historical commit): https://git.andalsoftware.com/Andal.LND/edx-platform/commit/b0d41f6ebbe647d72333f37b2a8f0531f4fc7874
- Open edX shuffle docs: https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-koa.master/exercises_tools/multiple_choice.html

status: ok
