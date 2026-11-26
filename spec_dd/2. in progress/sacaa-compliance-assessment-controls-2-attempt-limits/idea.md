# Quiz attempt limits and waits

Spec 2 of 7 in the SACAA assessment controls effort. Read the "SACAA assessment controls" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A QUIZ form can set two things in its front matter:

- A maximum number of attempts. Default: no limit.
- A list of minimum waits between attempts. Default: none. Example: wait 1 hour after the first failure, 2 hours after the second, 2.5 hours after every later one. The last entry repeats for all later failures.

The server enforces both when a learner starts an attempt, including by typing the start URL. The form start page and the results page show attempts used, attempts left, and when the next attempt opens.

## Why

The regulation line (from the original brief):

> "a learner is allowed a maximum of two re-writes thereafter, shall redo the course for readmission to the exam;"

and the brief's own request: "Quizes can be configured with a maximum number of retries. By default there is no limit. Quizes can be configured to have a minimum elapsed time between attempts. By default no minimum."

Today "Try Again" is unconditional while the item is open. Nothing in the start gate or the UI knows an attempt count or a wait (`../sacaa-compliance-assessment-controls/research_attempts_and_scoring.md`, section 1).

## What is settled

- Every control in this effort is off by default and set in content front matter. Here the settings sit on the form and apply to QUIZ forms only; other strategies must reject them, like the existing QUIZ-only fields.
- Attempts are counted per `CourseProgress` record at a placement: the completed `CourseFormAttempt`s for that form under that record. An open attempt does not count. `sacaa-compliance-assessment-controls-7-course-restart` resets the count by giving the learner a new `CourseProgress` record; this spec builds no reset.
- Every completed attempt counts, including one completed by expiry or by disturbance. `sacaa-compliance-assessment-controls-3-test-time-limit` and `sacaa-compliance-assessment-controls-5-test-disturbance` own how those attempts get completed; this spec only counts them.
- Waits apply after a failed attempt only. The wait is measured from the failed attempt's `completed_time`. The wait for the Nth failure is entry N of the list, and the last entry repeats.
- A wait list given with no maximum is valid (the waits then apply to unlimited retries).
- When the cap is used up, the quiz stays locked for that learner. There is no automatic course restart. Staff restart by hand in `sacaa-compliance-assessment-controls-7-course-restart`. The cap locks only that quiz.
- Enforcement is server-side in `_form_start_gate` and `start_attempt` (`freedom_ls/learner_interface/views.py:1978`, `freedom_ls/learner_progress/attempts.py:184`), under the `CourseProgress` row lock `start_attempt` already takes, so two concurrent starts cannot both pass. The gate is shared by `form_start` and `form_declaration`, so both are covered. The gate today only redirects, so a refusal needs a new outcome that shows the reason.
- Reusing an already open attempt (continue) is never blocked by the cap or a wait.
- The learner sees the numbers on two pages: the form start page (`view_form`, `form_start_page_buttons`) and the results page (`course_form_complete`). Both show attempts used, attempts left, and when the next attempt opens when a wait is running. "Try Again" and "Start" become unavailable, with the reason, while the cap is used or a wait is running.
- Attempt numbers are already derived, never stored (`attempt_numbers` in `freedom_ls/reports/gather.py:392`). This spec adds no stored counter.
- New front matter fields need a `Form` field of the same name, a migration, the entry in the QUIZ-only `knobs` check in `freedom_ls/form_engine/schema.py`, the bundled copy in `claude_plugins/fls-content/validate/schema.py`, the authoring doc `claude_plugins/fls-content/skills/content-types/resources/form-files.md`, the educator preview rows (`freedom_ls/educator_interface/panels/course/content_preview.py:508`) and the demo quiz `demo_content/functionality_demo_end_with_quiz/3. quiz/form.md`. A `None` default drops out of `content_save`, so removing a key later does not reset a stored value; pick schema defaults with that trap in mind.
- Collision: `sacaa-compliance-assessment-controls-3-test-time-limit` and `sacaa-compliance-assessment-controls-5-test-disturbance` also edit `start_attempt`, `_form_start_gate` and the `Form` schema. Run the three one at a time.

## Open until the spec

- **Does a passed quiz refuse a new attempt?** Today `form_start` does not check whether the placement is passed, so a passed learner can mint a new sitting by URL, and a later failed retake un-completes the item (the latest attempt decides). The research does not settle whether to close this; it is a behaviour change beyond the cap. Recommend: yes, but only inside this spec's start gate, refusing a new attempt when the latest completed attempt passed, because a cap that a passed learner can bypass or burn through by URL is not a real cap. If the spec writer finds the course relies on repeat sittings after a pass (for example revision), keep today's behaviour and say so.
- **Shape of the wait list.** Recommend a list of durations in a plain unit, minutes, validated as non-empty positive numbers; a non-decreasing rule is not required.
- **Where the next-attempt time shows.** Recommend a clock time plus "in 40 minutes", rendered server-side with no live countdown.
- **Does a time-limited, expired or disturbed attempt that is still open block the next start?** Recommend no change: the existing stale-attempt handling in `start_attempt` runs first, then the count is read.

## Out of scope

- Educators granting an extra attempt. A course restart covers it.
- Any automatic course restart when the cap is used up.
- Resetting counts. `sacaa-compliance-assessment-controls-7-course-restart` owns that.
- Interaction with a course deadline closing: none needed, the existing closed check in the gate stays as it is.
- Per-cohort overrides of the cap or waits.
- Completion reasons, the time limit and disturbance rules.

## Resources

- `../sacaa-compliance-assessment-controls/research_attempts_and_scoring.md`, sections 1 (attempt lifecycle and start gate), 5 (front matter path) and 6 (collisions).
- `../sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`.
- Regulation quote source: the original brief, `spec_dd/1. next/sacaa-compliance-assessment-controls/idea.md`, sections "Re-registrations" and "maximum-quiz-attempts". The SA-CATS 141 criteria it comes from have not been read.
