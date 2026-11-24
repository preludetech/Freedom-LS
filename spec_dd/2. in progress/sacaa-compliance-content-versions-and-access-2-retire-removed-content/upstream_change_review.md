# Upstream-change review: sacaa-compliance-content-versions-and-access-2-retire-removed-content

direction: changed

## What main gained
Main added a `revision` app. It is a learner-facing question bank with spaced-repetition scheduling, its own course revision page, and a sidebar entry. It builds banks from quiz-form questions (`freedom_ls/revision/queries.py`). Main also added `FormQuestion.dropped_from_source_at` (form_engine migration 0016). `content_save` sets it through `mark_dropped_questions` when a question disappears from its form file. A `form_questions_dropped` signal then removes that question from revision banks. The revision query filters only on `dropped_from_source_at__isnull=True`.

Main's quiz review also now compares stored scores against current options ("This quiz has changed since the attempt was marked"). The rebase merged this with the branch's served-paper scoring as "offered options plus live options added since".

## Why it matters for this spec
- `1. spec.md` Purpose and Success criteria say retired content is never shown to any learner. Revision is a new learner-facing read, and it reads only `dropped_from_source_at`.
  - A Form, Topic or Course deleted from the source retires every question under it through the sweep.
  - `mark_dropped_questions` only fires when a question vanishes from a form file that is still present.
  - So questions in a removed form, topic or course still sit in revision banks and are served, and a retired question can still be asked.
  - The "Leak tests, one per learner surface" list and the "Learner reads" sections omit revision. The plan has no revision coverage either (no match for "revision" or "dropped_from_source" in `2. plan.md`).
- The branch now has two "removed from source" markers on `FormQuestion`.
  - The Decisions section ("each row retires by its own absence", "retired overrides visibility and registration") does not say how the two relate.
  - The spec's own un-retire clears `retired_at` but not `dropped_from_source_at`. A question that returns to its file and is un-retired may stay out of revision banks, or a retired one may stay in. The spec gives no rule either way.
- The "Scoring and answer review read only the options the sitting was offered" decision is contradicted by main's "live options added since" merge. The merge now has to be stated in the spec, and "live" must mean non-retired.
- The shared bases the spec builds on (`BaseContent`, `save_with_uuid`, the `content_save` sweep) are unchanged. The explicit-filter decision stands, and no finished spec in `spec_dd/3. done/` is reopened. The change is a missed learner surface and an overlapping marker, not a reversal of the approach.

## What to change
- `1. spec.md` Decisions: add a decision that `retired_at` is the general state and `dropped_from_source_at` is the narrower revision-bank marker.
  - A question is out of revision when either is set.
  - Un-retiring a `FormQuestion` also clears `dropped_from_source_at` in the same write.
  - Say whether `mark_dropped_questions` stays as is, or the sweep sends `form_questions_dropped` for questions it retires so banks are pruned. Prefer the sweep sending the signal.
- `1. spec.md` "Learner reads: forms and questions": add a bullet that `freedom_ls/revision/queries.py` bank queries, the revision card, the dashboard counts and the ready count leave out retired questions and questions whose form is retired. Name the question's own `retired_at` and its `Form.retired_at` as the filters.
- `1. spec.md` Testing: add a leak test for the revision page (a retired question, and a question in a retired form, is never served or counted). Add an un-retire test that the question returns to banks. Add a test that the sweep and `mark_dropped_questions` coexist in one run.
- `1. spec.md` Scoring bullet: restate the merged rule as the offered options plus the non-retired options added since. Add the "This quiz has changed since the attempt was marked" review message to the Testing list.
- `1. spec.md` Records kept: add that `freedom_ls/revision` rows (scheduling and review state) are not changed on retire.
- `2. plan.md`: add a batch (or extend the learner-reads batch) for the revision filter and the un-retire and signal handling. Note that the content_save batch must reconcile `mark_dropped_questions` with the ledger.
- Already-implemented batches: re-check the `content_save` batch for the un-retire write, which must clear `dropped_from_source_at`. Re-check the quiz-review scoring batch against the merged rule. Add a revision-leak test.
- `docs/app_structure.md` is not changed by this. The `revision` app is already documented on main. The spec's documentation and upgrade-notes section should add a line that revision banks follow retire and un-retire.

status: ok
