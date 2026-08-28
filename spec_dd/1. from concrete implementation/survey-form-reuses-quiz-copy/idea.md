# Idea: survey (non-quiz) forms reuse quiz "scored / marking" copy

## The bug

Source: `system_qa/04_quizzes_and_assessments/qa_report.md`, **Finding E**.

A `CATEGORY_VALUE_SUM` **survey** form is not scored or marked — it just tallies category values
and shows category summaries with no pass/fail verdict (confirmed working in Test 8). But the
survey flow reuses the QUIZ copy in two places, which is wrong for a survey:

- **Submit confirmation dialog:** *"your answers will be scored and you won't be able to change
  them"* — a survey isn't scored.
- **Completion page:** *"Your responses are being reviewed — marking is in progress."* — nothing
  is being marked.

Functionally the survey works; this is purely misleading copy inherited from the quiz path.

## Expected fix

In the FLS forms templates/flow, branch the submit-dialog and completion-page copy on the form
type so survey-style (non-scored) forms show survey-appropriate wording (e.g. "your responses will
be recorded" / "Thanks, your responses have been recorded") instead of the quiz "scored" /
"marking in progress" strings. Quiz forms keep their existing copy.

## Sources

- `system_qa/04_quizzes_and_assessments/qa_report.md` — Finding E, screenshot `desktop_8_survey.png`.
