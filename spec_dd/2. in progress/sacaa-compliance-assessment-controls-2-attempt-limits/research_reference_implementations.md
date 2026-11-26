# Reference implementations: attempt caps and waits between attempts

Scope: how other systems solve a cap on attempts plus a minimum wait. Regulation and prior art for the whole effort is in `spec_dd/1. next/sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md` and is not repeated.

## Moodle (the closest match)

Sources:
- https://docs.moodle.org/en/Quiz_settings
- https://raw.githubusercontent.com/moodle/moodle/main/public/mod/quiz/accessrule/delaybetweenattempts/rule.php
- https://raw.githubusercontent.com/moodle/moodle/main/public/mod/quiz/accessrule/delaybetweenattempts/lang/en/quizaccess_delaybetweenattempts.php
- https://raw.githubusercontent.com/moodle/moodle/main/public/mod/quiz/accessrule/numattempts/rule.php

Settings shape:
- "Attempts allowed": an integer, 0 means unlimited (the rule is skipped when the limit is 0).
- Two delays, "Enforced delay between 1st and 2nd attempts" and "Enforced delay between later attempts", each a duration from seconds to weeks. Either, both or neither may be set. Docs example: two attempts with no wait, a week before the third. The rule is inactive when both are empty.
- Both limits can be overridden per group or per user (quiz overrides).
- Each rule is a separate access-rule plugin. Each one gets the count of previous attempts and the last attempt, and returns a message string or `false`.

Delay logic (`compute_next_start_time`):
- No previous attempt: no wait.
- Exactly one previous attempt and `delay1` set: next start = last `timefinish` + `delay1`.
- Two or more previous attempts and `delay2` set: next start = last `timefinish` + `delay2`. This one value covers all later attempts, so it is a two-slot version of "last entry repeats".
- If the quiz has a time limit, the finish time used is the earlier of `timefinish` and `timestart + timelimit`, so a timed-out attempt is measured from when its time ran out.
- It does not look at pass or fail. The delay follows every finished attempt, so Moodle waits after a pass too. It counts all previous attempts, not failures.
- The delay stops the learner when the wait runs past the quiz close time: "youcannotwait" tells them the quiz closes before they can start again.

Cap logic (`numattempts`): refuse when `numprevattempts >= attempts`. Passing is not considered. A passed learner is blocked only by the cap, and may sit again if attempts are left. Moodle handles this with the grading method (highest, average, first, last), not with a block.

Learner-visible wording:
- Cap: `nomoreattempts` (quiz lang string, "No more attempts are allowed").
- Wait: "You must wait before you may re-attempt this quiz. You will be allowed to start another attempt after {$a}." The `{$a}` is a formatted clock date and time. There is no live countdown. The wait message replaces the start button.
- The start page also lists the rules as bullets, such as "Attempts allowed: N".

Concurrency: not found in the fetched rule files. The checks run in the start path before the attempt row is created. From memory only (not verified here), Moodle relies on a unique index on (quiz, userid, attempt number) and on rejecting a start while an unfinished attempt exists. Treat as unconfirmed.

## Canvas

Sources:
- https://support.eclass.ualberta.ca/Knowledgebase/Article/View/627
- https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-attempts-allowed/idi-p/409505
- https://gcps.wsu.edu/?p=2028
- https://canvas.ubc.ca/courses/66705/modules/items/2429771

- New Quizzes: attempts are unlimited (the default) or limited. A "waiting period between attempts" can be set. Which score counts is configurable (highest, average, latest, first).
- Classic Quizzes: "Allow Multiple Attempts" with a count. The limit is per quiz.
- Staff can grant extra attempts per student (Moderate Quiz / quiz exceptions). This is only available when the quiz has a limited count.
- Canvas has a known trap: the assignment-level attempts field does not control New Quizzes, so there are two places to set the limit.
- I did not find source code or message wording for the wait. Do not assume the details.

## Open edX

Sources:
- https://docs.openedx.org/en/ulmo/educators/references/course_development/problem_settings.html
- https://docs.openedx.org/en/ulmo/educators/references/course_development/learner_problem_view.html

- "Maximum Attempts" is per problem, with a course-wide default. It is null, meaning unlimited, by default. The problem setting overrides the course-wide one.
- It is a cap only. There is no built-in delay between attempts.
- The learner sees "You have used N of M attempts" on each problem. The counter is a plain text count that is always shown, and the Submit button is disabled when attempts are used up.
- The Reset button vanishes when the cap is reached or the problem was answered correctly, so a correct answer stops further tries. Staff can reset a learner's attempts from the instructor dashboard, which fits the "restart by hand" model.
- "Show Answer: After All Attempts" requires a cap to be set.

## Blackboard

Not researched. Searches returned nothing usable. From memory (unverified): Blackboard Test options have "Number of Attempts" (unlimited or a count) with instructor "Grade Settings" to allow extra attempts. I know of no built-in delay. Do not cite this.

## TalentLMS

Sources:
- https://help.talentlms.com/hc/en-us/articles/360014574294-How-to-view-a-user-s-previous-test-attempts (about viewing attempts only)
- Search summary only: the old test options page has "Allow repetitions (if not passed)", "Maximum number of attempts", and "Control delay between attempts" with a value in minutes.

- Repeating is allowed only when the test is not passed ("if not passed"). So a pass ends further retakes. This is a design choice we also made.
- Delay is a single value in minutes, not escalating.
- Reported pitfall (Articulate forum): limits set inside SCORM authoring tools are per session, so the LMS must enforce the cap. This supports server-side enforcement.
- I did not verify exact wording or how the delay combines with the cap.

## LearnDash

Sources:
- https://learndash.com/support/kb/core/uncategorized/quiz-access-progression/
- https://wooninjas.com/downloads/learndash-retake-quiz/
- https://wisdmlabs.com/learndash-quiz-customization/learndash-retake-wrong-answers/

- Core LearnDash has a "Restrict Quiz Answer Attempts" / "repeats" count, not a delay. Check the labels against the current docs before citing them, since I could not confirm them.
- Cooldowns come only from third-party add-ons (Wooninjas Retake Quiz has a retake limit and a delay; WisdmLabs has a delay timer). The delay is one value.
- Admins reset a learner's quiz attempts by deleting the attempt records.

## Others seen in search (not read)

- iMocha has a cooling period between retakes: https://help.imocha.io/how-to-set-up-cooling-period-between-the-retakes-of-a-test
- Docebo has a community thread asking for a waiting period between test attempts, so a delay is a commonly requested feature that is often missing: https://community.docebo.com/product-q-a-7/tests-waiting-period-between-attempts-4683

## Comparison

| Question | Moodle | Canvas | Open edX | TalentLMS | LearnDash |
| --- | --- | --- | --- | --- | --- |
| Cap default | unlimited (0) | unlimited | unlimited (null) | unlimited | unlimited |
| Delay shape | 2 slots (1st-2nd, later) | one value | none | one value, minutes | add-on, one value |
| Delay after | any finished attempt | not confirmed | n/a | not confirmed | not confirmed |
| Pass blocks retake | no (grading method instead) | no | yes (no reset after correct) | yes | not confirmed |
| Countdown | no, clock time | not confirmed | n/a | not confirmed | not confirmed |
| Extra attempts | override per user | per-student exception | staff reset | not confirmed | delete attempts |

## What this means for us

- Our list of waits (one entry per failure, last repeats) is a superset of Moodle's two-slot design. Moodle is the model for where the check runs: a rule that gets the previous attempts and the last attempt and returns a message.
- Moodle measures from the last finish and counts all attempts. We wait after failures only and measure from the failed attempt's `completed_time`, as settled. This is stricter on pass, and fits the answer that a pass refuses a new attempt (TalentLMS and Open edX also stop retakes after a pass).
- Moodle's cap ignores passing, so it needs a pass check as a separate rule. In our start gate, run the checks in this order: open attempt (continue, never blocked), then passed, then cap, then wait. Each gives its own message.
- Use a count of completed attempts only, as every reference does. Moodle and Open edX both show the count to the learner ("N of M"), which matches the "used / left" display.
- Moodle shows a formatted clock time, not a countdown. The decision for a live countdown that enables the button in place is a deliberate step beyond the references. Plan for the server re-check on click (Moodle's check runs at start anyway) and for clock skew between browser and server: send the remaining seconds or a server-computed end time, and re-check on click.
- Moodle also has a "quiz closes before you can retry" message. Our out-of-scope note on deadlines covers this, so skip it.
- Learn from TalentLMS and Canvas: keep one place for each setting, and enforce on the server because client-side limits get bypassed by a start URL.
- Concurrency was not confirmed in any reference's code. The row lock in `start_attempt` is our answer. No reference documents a better one.
- Staff relief: Open edX and Canvas let staff grant attempts. We leave that to course restart in spec 7, which matches the "restart by hand" scope.
- Blackboard and part of the TalentLMS and LearnDash detail are unverified. Verify before quoting in the spec.

status: ok
