# Quiz time limit

Spec 3 of 7 in the SACAA assessment controls effort. Read the "SACAA assessment controls" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A QUIZ form's front matter can set a time limit. The default is none, so existing quizzes are unchanged. When a limit is set:

- The learner sees the limit on the start page before starting, and a countdown on every page of the sitting.
- The server enforces the limit. The clock is the attempt's `start_time` plus the limit, in wall-clock time.
- At expiry the sitting is completed and marked on whatever answers are saved, however few questions were answered. The learner lands on the results page.
- The sitting records why it was completed (learner submitted, time expired). Educators see the reason on the attempt review and in the cohort report attempts table.

## Why

The regulation line this answers: "the programme shall assess the student when the exam/skills test time has lapsed regardless of the number of questions answered;". The brief asks to "Allow setting a time_limit on Quizes. Show the time remaining to the learner. Once the time elapses, submit the form and redirect the learner."

Nothing on a quiz is timed today, and an abandoned open sitting stays open forever unless the form has `submit_on_exit`. An auditor needs to see that a result came from a lapsed clock and not from the learner pressing submit.

## What is settled

- The limit is set in the form's content front matter, like `quiz_pass_percentage`. There is no per-cohort or per-learner override.
- The clock runs on wall-clock time from `FormProgress.start_time`. It keeps running if the learner leaves, logs out or the course is paused. Learning-time rules do not apply to it.
- Expiry is per sitting (`start_time` plus the limit). The deadlines app is not reused: only its idea of comparing an instant with now on each request carries over.
- Enforcement is on the server in four places:
  - The client posts the current page together with the submit when the countdown reaches zero, then redirects to results. The post must skip the required-answer check. This is the pattern of the exit dialog and `form_submit_and_exit`.
  - A page posted after expiry is not saved. The sitting is completed on the answers already stored.
  - Any request that touches an expired open sitting completes it: the start route, the runner pages, the results page and `form_submit_and_exit`.
  - A housekeeping sweep (in `run_housekeeping_sweeps`) completes expired sittings nobody returns to. It uses the unscoped manager because it has no request, and completes each row through `FormProgress.complete()`. The sweep's cadence is the operator's schedule, so request-time enforcement is what the learner meets.
- Completion goes through `FormProgress.complete()`, which already marks saved answers, so an expired sitting is marked like any other. `max_score` follows the served paper as usual.
- The sitting gets a recorded completion reason. Today `complete()` has no reason field. This spec adds it with the values learner submitted and time expired. `sacaa-compliance-assessment-controls-5-test-disturbance` adds its own values later, so the field must be easy to extend.
- An expired attempt counts as an attempt toward the caps in `sacaa-compliance-assessment-controls-2-attempt-limits`.
- Educators see the reason on the attempt review and on the cohort report attempts table.
- The limit is shown on the start page before the learner starts.
- Collisions to run one at a time: `sacaa-compliance-assessment-controls-2-attempt-limits` and `sacaa-compliance-assessment-controls-5-test-disturbance` also edit `start_attempt`, `_form_start_gate` and the `Form` schema. This spec, with them, edits the runner's `examRunner` Alpine component and `form_submit_and_exit`. The `Form` schema change needs one migration, the schema edit, the bundled content schema and docs, and `content_preview.py`.
- A countdown that ends the sitting is an essential limit under WCAG 2.2.1, so no extend control is offered.

## Open until the spec

- Warnings at set points. Recommend a visible, screen-reader-announced warning at 5 minutes and 1 minute left, and none when the limit is 5 minutes or less.
- What the countdown shows after the client clock drifts or the page is reloaded. Recommend the server sends the remaining seconds on every page load and the client counts down from that, never from its own clock.
- Where a learner with an expired open sitting lands when they open the item. Recommend the results page, after the sitting is completed on the spot.
- How the completion reason is stored. Recommend a choice field on `FormProgress` with a default of learner submitted, so existing rows need no backfill.
- Whether the Moodle option of a grace period belongs. Recommend no: the brief gives none.

## Out of scope

- Per-learner extra time or other accommodations. Recommend revisiting only if a client asks.
- Any change to how a sitting is marked.
- Auto-fail or marking on disturbance, owned by `sacaa-compliance-assessment-controls-5-test-disturbance`.
- Inactivity auto-exit, owned by `sacaa-compliance-assessment-controls-4-inactivity-auto-exit`.
- Time limits on topics or course parts, and per-question timers.
- Pausing the clock when the learner leaves.

## Resources

- `../sacaa-compliance-assessment-controls/research_attempts_and_scoring.md`, sections 1 (attempt lifecycle, `complete()`, `submit_on_exit`), 2 (time limit seams, housekeeping sweep, per-page saves) and 6 (collisions).
- `../sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`: Moodle's "when time expires" options (auto-submit open attempts is the default) and the WCAG 2.2.1 essential-limit exception.
- Regulation quote source: the line is client-supplied. It is very likely from the SA-CATS 141 e-learning criteria, which are not public (see section 1 of the regulation research). The legal hook is CAR 141.07.1.
