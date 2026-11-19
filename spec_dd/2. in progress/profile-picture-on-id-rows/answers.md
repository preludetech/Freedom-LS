# Answers: profile-picture-on-id-rows

Asked by `/sdd:start` before the spec was written.

- Q: The on-screen cohort report (never its PDF) shows learners in its "Learners needing attention" list (`panel-attention-row`) and its "Summary of learner progress" table name column (`panel-person-link`). Which of these should show the profile picture? → A: Both. A learner looks the same everywhere on screen, at the cost of one more `User` query per report render. (asked up front)
