# Answers: sacaa-compliance-assessment-controls-2-attempt-limits

Asked by `/sdd:start` before the spec was written.

- Q: Once a learner has passed a quiz, should starting a new attempt be refused? → A: Yes. The start gate refuses a new attempt when the latest completed attempt passed. (asked up front)
- Q: What shape does the wait-between-attempts list take in quiz front matter? → A: A list of whole minutes, validated as a non-empty list of positive numbers. Waits do not have to be non-decreasing. (asked up front)
- Q: How do the start and results pages show when the next attempt opens during a wait? → A: As a live countdown, not the recommended server-rendered clock time. (asked up front)
- Q: When the wait runs out while the learner is on the start or results page, what happens? → A: The Start or Try Again button becomes active in place, without a reload. The server re-checks the wait when the button is clicked. (asked up front)
- Q: Does an open attempt that has gone stale (expired or disturbed) block the next start? → A: No change. `start_attempt`'s existing stale-attempt handling runs first, then the completed count is read. (asked up front)
- Q: Does refusing a new attempt after a pass apply to every QUIZ form, or only to quizzes that set a max attempts or a wait list? → A: Only to quizzes that set one of them. A quiz with neither keeps today's behaviour, retakes after a pass included. (asked during spec_from_idea)
- Q: Should this spec show educators a learner's attempts used, attempts left and when the next attempt opens? → A: No. Add a new spec for the educator view. (asked during spec_from_idea)
- Q: When a learner has used every attempt, what does the locked message tell them to do? → A: It states the fact only, e.g. "You have used all 3 attempts.", with no next step. (asked during spec_from_idea)
