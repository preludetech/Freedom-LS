# Research: known complaints about timed online quizzes and auto-submit

Topic `known_complaints`, for `sacaa-compliance-assessment-controls-3-test-time-limit`. Method: web searches only (Moodle tracker and docs, Canvas community and university guides, W3C and WebAIM lists, browser timer articles). Reddit and edX turned up nothing usable, so no claim below rests on them. Where a complaint is my inference and not sourced, it is marked "(inference)".

Design references below are to `idea.md` and `answers.md` beside this file: server clock from `start_time` plus limit; the countdown starts from server remaining seconds; the client posts the current page at zero and skips the required check; a page posted after expiry is not saved; any request that touches an expired open sitting completes it; the housekeeping sweep completes abandoned sittings; completion goes through `FormProgress.complete()` with a recorded reason shown to educators; warnings at 5 and 1 minutes (none if the limit is 5 minutes or less); no grace period; no extend control; the current limit applies to a sitting mid-edit.

## Complaints and how this design fares

### 1. Answers lost when the timer expires
- Moodle users report answers typed on the page are lost at expiry, since answers are saved on navigation and not in the background. Forum threads: https://moodle.org/mod/forum/discuss.php?d=219960 and https://moodle.org/mod/forum/discuss.php?d=217504. Suggested workarounds were smaller pages and checking the console for JS errors at zero.
- MDL-74378: the autosave script can stop on long windows, so the expiry auto-submit does not fire. Cron later submits only the last saved data, so late answers are lost. https://tracker-old.moodle.org/browse/MDL-74378
- Moodle's zero-grade guidance lists JS disabled and attempts saved but never submitted as causes: https://docs.moodle.org/35/en/Quiz_Time_Limit
- Design: partly addressed. Posting the current page with the submit at zero, skipping the required check, targets the typed-on-page case. Server-side completion on any request and in the sweep covers JS failure. Not addressed: if the post at zero fails (offline, tab asleep), the current page is lost, and the "no grace period, late page not saved" decision (answers.md) makes that permanent. Per-page saves only; there is no autosave while typing. This is the largest residual complaint and the spec should say so on the start page or results page (see Recommendations).

### 2. Timer keeps running through a network outage
- UBC: the countdown continues when the connection is lost, so it does not reflect time spent; the fix is instructors granting extra time. https://lthub.ubc.ca/technology-tips/internet-connection/
- Stanford: auto-submit will not work if the browser is closed, the computer sleeps or the connection fails at the moment time runs out; students should not rely on it. https://med.stanford.edu/edtech/services/lms/medcanvas/exams
- Canvas threads give inconsistent accounts of what happens after a disconnect (submit on return vs. immediately): https://community.canvaslms.com/t5/Admin-Group/Quiz-Timer-disconnection-auto-submit/m-p/462862 and https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-What-happens-to-Quiz-Timer-in-event-of-Canvas-Service/m-p/500703
- Canvas idea asking for connection status and a manual save button: https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-Show-connection-status-offer-a-save-button-with/idi-p/572851
- Design: not addressed by design. The clock is wall-clock by decision, with no pause, grace or accommodation (out of scope). That matches the regulation line but means an outage costs the learner time. Cheap mitigation within scope: a visible "could not save / offline" state next to the countdown (inference; not in idea). Also state plainly, on the start page, that the clock does not stop.

### 3. Auto-submit depends on the browser, and "stuck open" attempts
- Moodle MDL-36578: an attempt stays "in progress" forever when the student leaves and a teacher cannot close it; resuming completes it with overdue time listed. https://tracker-old.moodle.org/browse/MDL-36578
- Moodle overdue handling relies on cron (at most hourly), and overdue attempts show as "Never submitted" only after cron: https://tracker-old.moodle.org/browse/MDL-74543, https://tracker-old.moodle.org/browse/MDL-54907, https://docs.moodle.org/dev/Better_handling_of_overdue_quiz_attempts, https://docs.moodle.org/dev/States_of_a_quiz_attempt
- Design: well addressed. Request-time completion means a learner or educator touching the sitting sees it completed. The sweep handles sittings nobody returns to. Residual: sweep cadence is the operator's schedule, so an educator viewing a report between sweeps may see an expired sitting still open. Spec question: should the cohort report and attempt review also complete (or at least label "expired, not yet completed") expired open sittings they list? idea.md lists only start, runner, results and `form_submit_and_exit` as touchpoints, not educator views.

### 4. Timer not matching the server, drift, background tabs, sleeping devices
- Background tabs are throttled to about one timer callback per second or worse, and Firefox keeps a high clamp. Counters that decrement per tick drift; the standard fix is an end timestamp and computing remaining time on each update. https://developer.chrome.com/blog/timer-throttling-in-chrome-88, https://bugzilla.mozilla.org/show_bug.cgi?id=1326614, https://dev.to/raylabs/build-a-zero-drift-web-timer-3bip, https://dev.to/alphashark/building-a-reliable-countdown-timer-is-harder-than-it-looks-3e53
- Changing the device clock moves a `Date.now()` based timer. (Inference from how Date.now works; no source found. Sources I found do not cover clock changes or server-time mismatch.)
- No source found specifically on phones sleeping or screen lock affecting quiz timers; Stanford (above) says sleep defeats auto-submit.
- Design: addressed in direction. "Server sends remaining seconds on every page load" avoids trusting the client clock for the start. The spec should still say how the client counts down between loads: use a monotonic clock (`performance.now()`) anchored to the server value, and recompute on `visibilitychange` and `pageshow` so a woken device snaps to the right value. Server enforcement is the authority either way. Page-load latency means the displayed value is slightly generous; this should be stated as accepted, since the server decides.
- Timezones and DST: no sourced complaints. The design compares instants (`start_time` plus limit, wall-clock), which are timezone-free if stored as aware datetimes. Do not display an absolute "ends at" in server time; show remaining time or a local-time rendering (inference).

### 5. Timer anxiety and per-second screen reader announcements
- A university timer redesign notes a per-second visible countdown can add stress, so students can hide it. https://ctl.jhsph.edu/blog/posts/redesigned-countdown-timer/
- W3C WAI thread (2020): an auditor flagged a per-second text countdown; replies suggested lower update frequency and a heading-coded timer. https://lists.w3.org/Archives/Public/w3c-wai-ig/2020JulSep/0064.html (related: .../0062.html, .../0063.html)
- UGA guidance suggests an `aria-live="polite"` region and a request-more-time button: https://dash.uga.edu/accessibility-techniques/time-limits/
- Canvas New Quizzes accessibility notes: https://kb.wisc.edu/accessibility/page.php?id=138873
- I found no direct user complaints, only guidance and one auditor's remark.
- Design: partly addressed. Warnings at 5 and 1 minutes, announced, fit the "one clear warning" advice. The spec must keep the ticking countdown out of any live region (the visual timer should be `aria-hidden` or `role="timer"` with no live announcements; only the two warnings go in a live region), and give the learner a way to reach the time left on demand (a focusable control or heading). Consider a hide-the-countdown toggle (visual only, warnings stay). Not in the idea; a small scope question. "No extend control" matches WCAG 2.2.1 essential exception per the idea, but accommodation requests are the standard answer in sources above (1.5x, 2x), and idea.md defers them. Expect that complaint from educators and learners.

### 6. Unclear whether the quiz was submitted
- Blackboard and Sakai guides: saving is not submitting; students are told to look for a confirmation and to check the attempt status; "answers may be lost" if the connection or browser dies. https://hub.ncat.edu/_files/bb9-online-test-taking-tips.pdf, https://sites.nicholas.duke.edu/admittedstudents/files/2021/06/Sakai-How-Can-Students-Avoid-Problems-When-Taking-Online-Tests.pdf, https://collab-help.its.virginia.edu/a/405234
- Design: addressed by landing on the results page after expiry (and for a returning learner). Recommend the results page state, in words, "Your time ran out and the quiz was submitted on the answers saved at [time]" and that a learner submit shows a distinct message. The idea records the reason but does not say the learner sees it; make the learner-facing wording explicit. Also worth stating how many questions were answered, since the learner will otherwise wonder if their last page counted (see 1).

### 7. Educators cannot tell why an attempt ended
- Moodle exposes overdue time and "Never submitted" status for this reason (MDL-36578, MDL-74543 above). Canvas threads show instructors guessing from logs (Canvas links in section 2). Canvas "Digital Exam Disruptions" shows instructors needing to reason about lost time and grant more: https://teaching.usask.ca/articles/2025-03-04-digital-exam-disruptions.php
- Design: well addressed. A stored reason on `FormProgress`, shown on attempt review and the cohort attempts table, is what the sources lack. For audit value, consider also recording when completion happened vs. the deadline (`complete()` time vs. `start_time` plus limit), so a sweep-completed sitting that was completed hours late is distinguishable from one completed at the deadline. The marked answers are the same either way, but an auditor will ask. Also, the "current limit applies" decision (answers.md) means the limit is not stored on the sitting, so a later `content_save` can make a past expired sitting look inconsistent in review. Consider showing the limit used on the review only when it can be derived, or storing the completion instant (inference).

### 8. Grace period disputes
- Moodle offers a 60 second default grace for network delay and three "when time expires" options: https://docs.moodle.org/401/en/Quiz_settings, https://docs.moodle.org/310/en/Quiz_settings, https://docs.moodle.org/311/en/mod/quiz/config. Automatic regrading only recovers attempts submitted within the limit plus 60 seconds: https://docs.moodle.org/35/en/Quiz_Time_Limit
- Design: deliberately no grace (answers.md). Expect "I clicked submit at 0:00 and lost the page" complaints. Mitigation within the decision: the client posts at zero on its own, not on the learner click, and the server compares against the server clock, so the only loss is genuine latency. Document this on the spec so support has the answer.

## Recommendations for the spec (summary)
1. Make the countdown non-live: only the 5 and 1 minute warnings are announced; give an on-demand way to read the time left; consider a hide-countdown toggle.
2. Say on the start page that the clock does not stop for leaving, disconnect or sleep.
3. Show an offline/save-failed indicator beside the countdown.
4. Count down from the server value with a monotonic clock; resync on `visibilitychange` and `pageshow`.
5. Learner-facing wording on results that says the sitting ended on time and what was marked.
6. Decide whether educator reports complete or label expired-but-open sittings between sweeps.
7. Consider recording the completion instant alongside the reason, for audit.

## Sources
- https://tracker-old.moodle.org/browse/MDL-74378
- https://tracker-old.moodle.org/browse/MDL-36578
- https://tracker-old.moodle.org/browse/MDL-74543
- https://tracker-old.moodle.org/browse/MDL-54907
- https://moodle.org/mod/forum/discuss.php?d=219960
- https://moodle.org/mod/forum/discuss.php?d=217504
- https://docs.moodle.org/35/en/Quiz_Time_Limit
- https://docs.moodle.org/401/en/Quiz_settings
- https://docs.moodle.org/310/en/Quiz_settings
- https://docs.moodle.org/311/en/mod/quiz/config
- https://docs.moodle.org/dev/Better_handling_of_overdue_quiz_attempts
- https://docs.moodle.org/dev/States_of_a_quiz_attempt
- https://community.canvaslms.com/t5/Admin-Group/Quiz-Timer-disconnection-auto-submit/m-p/462862
- https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-What-happens-to-Quiz-Timer-in-event-of-Canvas-Service/m-p/500703
- https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-Show-connection-status-offer-a-save-button-with/idi-p/572851
- https://lthub.ubc.ca/technology-tips/internet-connection/
- https://med.stanford.edu/edtech/services/lms/medcanvas/exams
- https://teaching.usask.ca/articles/2025-03-04-digital-exam-disruptions.php
- https://ctl.jhsph.edu/blog/posts/redesigned-countdown-timer/
- https://lists.w3.org/Archives/Public/w3c-wai-ig/2020JulSep/0064.html
- https://dash.uga.edu/accessibility-techniques/time-limits/
- https://kb.wisc.edu/accessibility/page.php?id=138873
- https://developer.chrome.com/blog/timer-throttling-in-chrome-88
- https://bugzilla.mozilla.org/show_bug.cgi?id=1326614
- https://dev.to/raylabs/build-a-zero-drift-web-timer-3bip
- https://dev.to/alphashark/building-a-reliable-countdown-timer-is-harder-than-it-looks-3e53
- https://hub.ncat.edu/_files/bb9-online-test-taking-tips.pdf
- https://sites.nicholas.duke.edu/admittedstudents/files/2021/06/Sakai-How-Can-Students-Avoid-Problems-When-Taking-Online-Tests.pdf
- https://collab-help.its.virginia.edu/a/405234

status: ok · reason: complete; some items (timezone/DST, clock changes, mobile sleep, Reddit/edX) had no direct sources and are marked as inference or gaps
