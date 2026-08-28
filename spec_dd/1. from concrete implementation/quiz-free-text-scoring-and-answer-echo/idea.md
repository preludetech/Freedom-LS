# Idea: free-text questions in a scored QUIZ are always marked wrong and their answers aren't echoed

## The bug

Source: `system_qa/04_quizzes_and_assessments/qa_report.md`, **Finding C**.

On a scored QUIZ that contains `short_text` and `long_text` questions:

- Those free-text answers — even when typed in correctly — are always counted as **incorrect**,
  because a free-text question has no stored "correct answer" to grade against. This silently
  drags down the denominator: an all-question-types quiz scored **2/4 = 50%** when the two
  free-text answers should not have counted against the learner (effective 2/2).
- In the results page's **"Review incorrect answers"** list, those free-text questions appear with
  **both "Your answer" and "Correct answer" blank** — the learner's submitted text is never echoed
  back, so the review is empty and confusing.

This is partly an artifact of the QA course design (mixing ungradeable free-text into a *scored*
QUIZ rather than a survey), but the two symptoms are genuine product defects regardless of course
design: a free-text answer silently counting as wrong, and the learner's own submitted text not
being shown back to them.

## Expected fix

In the FLS forms/quiz scoring and results-review logic:

- **Scoring:** exclude free-text (`short_text` / `long_text`) questions from the pass/fail score
  of a QUIZ (or otherwise clearly mark them as *ungraded* rather than *incorrect*), so an
  ungradeable question can't drag the percentage down. Decide and document how free-text
  contributes (most likely: not counted in the graded denominator, shown as "submitted / not
  auto-graded").
- **Review echo:** echo the learner's **submitted text** in the "Your answer" cell for free-text
  questions on the review page, and don't render a misleading blank "Correct answer" for a
  question that has no correct answer.

## Sources

- `system_qa/04_quizzes_and_assessments/qa_report.md` — Finding C, screenshot
  `desktop_2_question_types_complete.png`.
