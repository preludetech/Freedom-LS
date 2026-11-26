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
- Q: A passed learner at an attempt-limited quiz who types the start URL lands on the start page. What explains the refusal? → A: The start page of a passed attempt-limited quiz always says "You passed this quiz, so it can't be retaken." (asked at the end of spec_from_idea)
- Q: Does a quiz that sets only retry_wait_minutes show an attempts-used count? → A: No. The count line shows only when max_attempts is set. (asked at the end of spec_from_idea)
- Q: When a failed sitting is followed by a sitting with no verdict, does the wait from the failure still run? → A: No. A wait runs only when the latest completed sitting failed. (asked at the end of spec_from_idea)
- Q: What does the results page's failed banner say with no attempts left, or during a wait? → A: With no attempts left it drops the try-again sentence and gives no next step. During a wait it reads "Review the material before your next attempt." (asked at the end of spec_from_idea)
