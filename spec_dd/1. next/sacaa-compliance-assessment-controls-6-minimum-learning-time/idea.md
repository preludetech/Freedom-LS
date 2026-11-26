# Minimum learning time

Spec 6 of 7 in the SACAA assessment controls effort. Read the "SACAA assessment controls" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Record each learner's active learning time and let authors require a minimum before the learner moves on or opens a quiz. Two shapes, both off by default and set in content front matter:

1. **Topic or course part minimum.** A topic or a course part sets a minimum learning time. The author gives an explicit time, or asks for an estimate from content length (words plus audio durations). A topic minimum is met by the learner's active time on that topic. A course part minimum is met by the learner's total active time across the part, and it must be met before the part's last item can be completed. The learner sees how much time is left.
2. **Quiz minimum.** A quiz form sets a minimum total learning time on the course. The quiz does not open until the learner's total active time on the course meets it. Earlier modules must also be complete, which sequential unlock already guarantees.

Educators see a learner's learning time per item and per course.

## Why

The regulation says: "with the exception of timed modules trainees must be given adequate time to complete the training;" and "in the case where a minimum tutorial time applies, the programme shall not permit the student to write the accompanying knowledge test until those minimum tutorial course hours have been met and the course modules have been completed;". Today nothing measures time on a page. `TopicProgress.start_time` is only the first open, so a learner who opens a topic and returns hours later would already have "met" any minimum.

## What is settled

- Only active time counts. It is recorded through the activity signal that `sacaa-compliance-assessment-controls-4-inactivity-auto-exit` builds, which owns the signal and its client detector. This spec accumulates the seconds it reports into a stored counter on each `TopicProgress`. It cannot start before that signal exists.
- The learning time of a course is the sum over the learner's `TopicProgress` rows for that `CourseProgress`. A course part's time is the sum over the topics placed in it.
- Time does not accrue while the course is paused.
- A restart (`sacaa-compliance-assessment-controls-7-course-restart`) starts the new run at zero. The counters belong to the old run's records, which that spec keeps read-only.
- Topic and course part gate: the check sits server-side at the point that completes the topic, the Next / `mark_complete` POST in `view_topic` (`freedom_ls/learner_interface/views.py:1864`). It refuses to set `complete_time` while the minimum is unmet. The next item then stays `BLOCKED` through `get_content_status` (`freedom_ls/learner_interface/utils.py:316`), and `_blocked_item_redirect` already refuses URL guessing past it. A gate that lives only in the template is not acceptable (see the comment at `views.py:1341-1344`).
- A course part minimum is checked when the part's last item is completed.
- Quiz gate: the check sits in `_form_start_gate` (`views.py:1978`), alongside the other start rules, so the start page and the start route both enforce it.
- An explicit time is set in front matter on the topic, the course part or the quiz form. A course part's setting applies to its children unless a child sets its own (the effort's cascade rule). For an estimated minimum the author sets a switch instead of a time. Each new key needs a pydantic field, a model column and a migration (`save_with_uuid` rejects keys that are not model fields), and the offline validator and authoring docs must list it.
- The estimate counts words in the topic's stored markdown (tags and attribute text stripped) plus `File.duration_seconds` of audio. Video has no duration today, so it adds nothing until `learner-interface-features-5-protected-video` supplies one.
- The learner sees the time left on the topic page, and on the blocked Next control or the quiz start page. Refusals use the existing HTMX and redirect conventions (422 for HTMX validation errors).
- Reference topics (`course_reference_topic`) write no progress and stay outside both rules.
- Educators see learning time per item and per course in the existing learner progress views.
- `sacaa-compliance-assessment-controls-4-inactivity-auto-exit` owns the activity signal and the auto exit. This spec only reads it.

## Open until the spec

- **Does time on a form page count?** Recommend no: learning time accumulates on `TopicProgress` only, and time on a quiz page (including `FormProgress`) never counts toward a minimum. This matches "tutorial time" and avoids a test attempt filling its own prerequisite.
- **Reading speed for the estimate.** Recommend about 200 words per minute, a named constant, plus audio duration at 1x.
- **Where the estimate is computed.** Recommend at `content_save` time (`freedom_ls/content_engine/content_save.py`), stored on the `Topic`, so the player does not render markdown per request. Recompute on every content save.
- **Collision with `learner-interface-features-2-test-out`.** Does a skipped section still owe its minimum? Recommend that test-out waives it: a learner who tests out has shown the knowledge, and the quiz gate then counts only time actually spent. The test-out spec must state it.
- **Course part whose last item is a form.** The "complete" action for a form is not the topic Next POST. Recommend the part minimum then gates that form's start in `_form_start_gate`, so the learner cannot begin the form until the part's time is met.
- **Estimated minimum: what fraction of reading time.** Recommend the full estimate by default, with an optional author-set factor only if the spec finds a clear need; otherwise no factor.
- **Accumulation granularity and cap.** How often the client reports and the maximum seconds credited per report, to stop a forged report from filling the counter. Recommend the signal's own interval, with the server capping credit per report at that interval.
- **Placed twice.** `TopicProgress` is keyed per placement, so a topic placed twice has two counters. Recommend the minimum is checked per placement and time is not shared.

## Out of scope

- The activity signal, the interaction detector and the auto exit (`sacaa-compliance-assessment-controls-4-inactivity-auto-exit`).
- Restarting a course (`sacaa-compliance-assessment-controls-7-course-restart`).
- Video duration (`learner-interface-features-5-protected-video`).
- Counting time on quiz pages, per-cohort overrides of the minimums, and any identity verification.
- Back-filling time for learners who finished topics before this ships. They have no recorded time, so a minimum applies only to content they open after it is enabled.

## Resources

- `../sacaa-compliance-assessment-controls/research_learning_time_and_inactivity.md`, sections 2, 3, 4 and 6: gating seams, front matter cascade, estimate inputs and shared code.
- `../sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`, section 3: "minimum tutorial time" readings and prior art.
- Regulation source note: the two quoted lines come from the client's SA-CATS 141 e-learning criteria as pasted in the parent `idea.md` (under "Time spent learning"). SA-CATS 141 itself has not been read, so the reading of "minimum tutorial course hours" as a course total plus a per-item extension is inference.
