# Test disturbance

Spec 5 of 7 in the SACAA assessment controls effort. Read the "SACAA assessment controls" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A QUIZ form's front matter sets what a disturbance does to an open attempt: nothing (the default,
today's behaviour), auto-fail, or auto-mark. An auto-fail completes the attempt with 0 of
`max_score` and a completion reason of disturbance. An auto-mark completes it with the normal score
on the answers saved so far and the same reason. Educators see the triggering event and its time on
the attempt review and the cohort report. The learner reads the rule on the start page before
starting and sees why the attempt ended on the results page.

## Why

The regulation line this answers (from the original brief):

> "during exam/knowledge test any disturbance/logout is regarded as a fail;"

The brief adds that some tests must auto-fail the learner and others should auto-mark them, so the
choice is configurable. Today a logout, a dropped connection or a closed tab does nothing on the
server. A `submit_on_exit` form is finalised only when the learner next opens the item, and a
learner who never returns leaves an open attempt forever.

## What is settled

- The rule is off by default and set in the form's front matter, like every control in the effort.
  It applies to `QUIZ` forms only.
- A disturbance is one of: logout; session end or expiry; an inactivity auto exit from
  `sacaa-compliance-assessment-controls-4-inactivity-auto-exit`; leaving the test page and coming
  back later. Switching tab or window (focus loss) does not count; focus-loss detection is out of
  scope for the whole effort.
- Leave-and-return is detected from the activity signal that `sacaa-compliance-assessment-controls-4-inactivity-auto-exit`
  records: an open attempt with no recorded interaction for longer than a threshold has been
  disturbed.
- Detection is server-side. A `user_logged_out` receiver catches logout. Session expiry and
  leave-and-return are caught on the learner's next request or by the housekeeping sweep from
  `sacaa-compliance-assessment-controls-3-test-time-limit`. The sweep is the safety net for
  learners who never return; the request path handles the rest.
- An auto-fail stores a real score pair of 0 of `max_score` in `FormProgress.scores`. This is
  required: `quiz_verdict` returns None for a record with no score pair, and
  `attempt_completes_form` treats None as not failed
  (`freedom_ls/form_engine/queries.py:29-67`). An auto-mark stores the normal score from the
  answers saved so far (`QuestionAnswer` rows); an unposted page is lost.
- Both outcomes complete the attempt and count as an attempt toward the caps from
  `sacaa-compliance-assessment-controls-2-attempt-limits`.
- This spec reuses the completion reason recorded on `FormProgress` and the sweep, both introduced
  by `sacaa-compliance-assessment-controls-3-test-time-limit`, and adds the disturbance reason to
  them. It also records which event triggered the disturbance and when (event kind and time).
- Educators see the event and its time on the attempt review
  (`freedom_ls/educator_interface/panels/learner/quiz_attempt.py`) and on the cohort report.
- The learner is told the rule on the start page before starting, and sees the reason the attempt
  ended on the results page.
- `submit_on_exit` is an existing form flag (`freedom_ls/form_engine/schema.py:105`). It finalises
  an abandoned attempt only lazily, on the next visit, and changes the exit dialog text. Disturbance
  auto-mark does the same finalising but also on logout and by the sweep, so it covers that case.
  See Open for what happens to the flag.
- `sacaa-compliance-assessment-controls-3-test-time-limit` and
  `sacaa-compliance-assessment-controls-4-inactivity-auto-exit` own the sweep, the completion reason
  and the activity signal. This spec does not redefine them.
- `-2`, `-3` and this spec all edit `start_attempt`, `_form_start_gate` and the `Form` schema, so
  they run one at a time. The front matter key needs a `Form` model field of the same name, a
  migration, the bundled copy in `claude_plugins/fls-content/validate/schema.py`, the authoring
  docs and the educator preview row.

## Open until the spec

- **Leave-and-return threshold.** Recommend: tie it to the auto-exit interval when the form or its
  enclosing part sets one, else a fixed default of 2.5 minutes, so the two rules agree and no extra
  setting is needed.
- **Fate of `submit_on_exit`.** Recommend: auto-mark subsumes it. Keep the flag working as a
  deprecated alias for auto-mark (exit dialog text unchanged) so existing content keeps its
  behaviour, and say so in the authoring docs. The alternative of keeping two flags gives a form
  that can set both with conflicting meaning.
- **Rule when both fields are set.** Recommend: the new disturbance setting wins, and the validator
  warns on a form that sets both with a disturbance of nothing.
- **Where the event record lives.** Recommend: two fields on `FormProgress` beside the completion
  reason (event kind and time), not a separate log, since an attempt has at most one.
- **When the sweep sees an expired timer and a disturbance together.** Recommend: whichever
  happened first in time sets the reason.

## Out of scope

- Focus-loss and tab-switch detection.
- The time limit itself and the inactivity countdown: `sacaa-compliance-assessment-controls-3-test-time-limit`
  and `sacaa-compliance-assessment-controls-4-inactivity-auto-exit` own them.
- Attempt caps and waits: `sacaa-compliance-assessment-controls-2-attempt-limits` owns them.
- Per-cohort overrides of the rule, and identity verification.
- Moderating a disturbed attempt's marks: `sacaa-compliance-assessment-controls-1-score-moderation`
  owns moderation.

## Resources

- `../sacaa-compliance-assessment-controls/research_attempts_and_scoring.md`, sections 1, 2 and 6
  (lifecycle, `submit_on_exit`, completion, sweep pattern, collisions).
- `../sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`, section 2: no
  SACAA, EASA, ICAO or FAA definition of "disturbance" was found, so the owner's definition above
  stands in for it.
- Regulation quote source: the original brief, `spec_dd/1. next/sacaa-compliance-assessment-controls/idea.md`
  ("Auto mark or auto fail"). The SA-CATS 141 criteria it comes from have not been read.
