# Answers: sacaa-compliance-4-attempt-review

Asked by `/sdd:start` before the spec was written.

- Q: Where should an educator open one quiz attempt from (the learner's Courses tab already has a per-quiz attempts table)? → A: Its own attempt instance page, linked from the attempts table row, and the row also gets a quick view with the summary (score, pass/fail, times) (asked up front)
- Q: Can an educator open an attempt that is still in progress? → A: Completed attempts only; only submitted attempts link to the review (asked up front)
- Q: Should the attempt review page get a Claude Design pass before it is built? → A: No; build it from panel-framework pieces and the brand rules, checked in QA (asked up front)
- Q: There is no quiz-attempt export to extend (`form_engine/exports.py` only serves the course-application export); what should this spec do for the inspector export? → A: Defer the export to a follow-up spec; only the review page and quick view ship here (asked while research ran)
