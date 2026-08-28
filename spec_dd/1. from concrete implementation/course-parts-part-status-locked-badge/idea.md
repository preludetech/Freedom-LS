# Idea: part-level "Locked" badge misrepresents a partially-completed part (and is inconsistent between pages)

## The bug

Source: `system_qa/03_free_enrolment_and_course_player/qa_report.md`, **Issue 3**.

On `functionality-demo-course-parts`, the part **"Core Concepts"** contains a **Completed** item
(2.1 "Key Ideas") followed by a deadline-locked item (2.2). Its **part-level status badge**:

- read **"In progress"** on one player page, then **flipped to "Locked"** on another once the next
  item became deadline-blocked — i.e. the badge is **inconsistent between pages** for the same
  underlying state; and
- labelled the whole part **"Locked"** even though it contains a lesson the learner has already
  completed and can still view.

The effect is that a part which is partially done reads as if the entire part — including the
finished lesson — is inaccessible, which is both wrong and confusing.

## Expected fix

Fix the part-level status derivation in FLS's course-parts logic so it is:

- **Consistent** — the same part state produces the same badge on every player page (single source
  of truth for part status rather than two divergent computations); and
- **Correct** — a part that contains completed and/or accessible items is not labelled fully
  "Locked". A part with a mix of completed and locked items should read as "In progress" (or an
  equivalent partial state), reserving "Locked" for parts that are genuinely wholly inaccessible.

## Sources

- `system_qa/03_free_enrolment_and_course_player/qa_report.md` — Issue 3 (and Test 4 / Test 9
  context describing the parts structure and per-part badges).
