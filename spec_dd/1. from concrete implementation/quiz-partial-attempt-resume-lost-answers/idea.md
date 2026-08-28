# Idea: fix quiz partial-attempt handling — abandoning an attempt scores it as a failure and loses answers

## The bug

Source: `system_qa/04_quizzes_and_assessments/qa_report.md`, **Finding B (Test 7 — FAIL)**.

Expected behaviour (per the QA plan): a learner who starts a quiz, answers the first page, and
navigates away should be offered a **Resume** control, and returning should retain the answers
already entered.

Actual behaviour observed:

- There is **no Resume control** anywhere.
- The moment the learner leaves an in-progress attempt, that attempt is **finalized as a scored
  attempt**. Any unanswered questions are graded **wrong**. Concretely, after answering page 1 of
  a 6-question quiz correctly (3/3) and leaving, the start screen showed the partial as a
  completed **"Previous attempt" scored 50% (3/6)** — the three untouched page-2 questions were
  counted as incorrect.
- The only available action is **"Try Again"**, which starts a **completely blank** new attempt
  ("0 of 6 answered", nothing retained). The answers from the abandoned attempt are gone.

Reproduced repeatedly: the attempts list accumulated abandoned, finalized, scored records —
including a `50% (3/6)` (left after page 1) and a `0% (0/6)` (left before answering anything) —
each an immutable failing attempt the learner never chose to submit.

So leaving an in-progress attempt (a) **burns a scored attempt** the learner never submitted, and
(b) **discards the answers already entered**. On a quiz with a limited number of attempts this is
especially damaging.

## Expected fix

Introduce genuine resume semantics for an in-progress attempt, in the FLS forms/quiz runner:

- An attempt that has been started but not explicitly submitted should be treated as
  **in-progress**, not finalized/scored. Its entered answers should be **persisted** so returning
  to the quiz reopens the same attempt with those answers still filled in.
- The start screen for a quiz with an in-progress attempt should offer a **Resume** action
  (continue the existing attempt) rather than only "Try Again" (start a fresh one).
- Only an explicit **Submit** should score the attempt. Navigating away must not silently finalize
  it or grade unanswered questions as wrong.

If, by design, the product intends that any started attempt is scored on abandonment (no resume),
then the fix is instead a **UX/copy** one: stop presenting abandoned attempts as scored failures,
warn the learner before they leave that leaving will submit-and-score, and don't discard entered
answers without consent. Either way the current behaviour contradicts the plan's Test 7
expectation and silently costs learners both work and attempts — a product decision plus
implementation is needed. Resume (the plan's expectation) is the stronger option.

## Sources

- `system_qa/04_quizzes_and_assessments/qa_report.md` — Finding B, screenshot
  `desktop_7_resume_attempt.png`.
