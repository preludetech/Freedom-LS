# Research: known_complaints (durations and scores)

Small web scan plus general knowledge. Kept short; throwaway idea.

## Duration complaints
- Short items show as zero: a 40-minute course displayed "Duration: 0" because only whole hours were shown (WPLMS). Relevant to our "under one minute" case: flooring to `0h 00m` is the same surprise, so the spec should say it is intentional.
- Rounding surprises: Absorb LMS learners saw a 15-minute minimum while admins saw the real figure; the vendor removed the minimums and rounding so both see one number. Bridge rounds to the nearest hour above 44 minutes.
- Mismatch with reality: stated duration vs. actual video length, or auto-calculated vs. real time (Adobe, Storyline threads). Cause is the definition of "duration" differing between places. Display helpers should document what they floor or round.
- Inconsistent units between admin and learner views (hours in admin UI, minutes on learner UI, Oracle thread).

## Score complaints (general knowledge, not sourced)
- "x / 0" or NaN/percent-of-zero outputs when no points are possible. Rendering the numbers as given (`0 / 0`) avoids a crash but may read as a failure; do not compute a percentage here.
- Ambiguous formats ("7/10" vs "70%" vs "7") with no label.

## Implications for the spec
- Zero-padded minutes (`1h 02m`) is unambiguous; floor, never round up, and test the boundaries (0, 59, 60, 3599, 3600).
- Test `possible == 0` explicitly, plus `earned > possible`.

## References
- https://wplms.io/support/forums/topic/lesson-duration
- https://ideas.absorblms.com/ideas/LMS-I-1205
- https://bongarde.freshdesk.com/support/solutions/articles/68000006266-how-does-bridge-calculate-the-estimated-time-to-complete-a-course-
- https://community.articulate.com/discussions/articulate-storyline/storyline-360-automatic-duration-calculation-way-off-why
- https://community.oracle.com/customerconnect/discussion/884584/course-duration-is-in-hours-in-admin-ui-but-minutes-on-learner-ui

status: ok
