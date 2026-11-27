# Answers: sacaa-compliance-assessment-controls-3-test-time-limit

Asked by `/sdd:start` before the spec was written.

- Q: Should the learner get timed warnings before the countdown ends the quiz? → A: Yes, a visible, screen-reader-announced warning at 5 minutes and 1 minute left; no warnings when the limit is 5 minutes or less (asked up front)
- Q: Should there be a grace period after the clock runs out, where a late page is still saved? → A: No grace period. A page posted after expiry is not saved; the sitting is marked on the answers already stored (asked up front)
- Q: If a `content_save` changes or removes a quiz's limit while a learner is mid-sitting, which limit applies to that sitting? → A: The current limit. Each request reads the limit from the form as it is now; no limit or deadline is stored on the sitting for enforcement (asked up front)
- Q: The browser's auto-post at 0:00 reaches the server after the deadline, and there is no grace period, so how does the open page get saved? → A: The client auto-posts the current page about 5 seconds before the deadline so it lands in time; the server keeps no grace period (asked while research ran)
- Q: When the sweep or a late request completes an expired sitting, what is its completion time? → A: The deadline: `completed_time` is `start_time` plus the limit for time-expired sittings (asked while research ran)
- Q: Should the sitting record the limit that applied when it completed? → A: Yes, one field on `FormProgress` written when a timed sitting completes; the attempt review shows it. Enforcement still reads the current limit (asked while research ran)
- Q: Should learners be able to hide the countdown? → A: No toggle. The countdown is always shown and never announced; only the warnings are announced (asked while research ran)
- Q: Should the client still post about 5 seconds early, or post at 0:00 with a server grace window for latency? → A: Post at 0:00. The server accepts the time-up post for a few seconds after the deadline so it can arrive; no other late request gets a grace window. This replaces the 5-seconds-early answer above (asked while reviewing the spec)
- Q: Should a Next post that lands just after the deadline get the same grace window as the auto-submit? → A: Yes. Any page post inside the window is saved, then the sitting completes as time expired (asked while reviewing the spec)
