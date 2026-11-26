# Research: best practices for server-enforced timed quizzes

Topic `best_practices` for `sacaa-compliance-assessment-controls-3-test-time-limit`. Builds on
`spec_dd/1. next/sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md` (Moodle options, WCAG 2.2.1 essential exception) without repeating it. Where a point is my inference rather than a source's statement, it says so.

## 1. Server-authoritative timing and clock drift

Practice:
- The server owns the deadline: `start_time + limit`, compared with the server's own `now` on every request. The client countdown is display only; the server runs the final check on every save and submit (Mendix community, Laracasts below).
- Do not trust or send the client an absolute deadline to count down against its own clock. Reports of client clock changes ending sittings early: Moodle MDL-73960 and MDL-74817 (client clock jump auto-submitted or auto-finished the attempt), and an exam platform user scoring 0% after a clock error (magicjudges thread).
- Send remaining seconds (a delta) computed by the server at render time. The client converts it once to a local end point using a monotonic source (`performance.now()`), not `Date.now()`, so later wall-clock changes by the user do not move it. Only network latency at load (typically under a second) is lost, and it errs in the learner's favour only if the server computes the delta as late as possible in the render. The swizec post makes the same "send the delta" suggestion. This matches the idea's recommendation (remaining seconds on every page load).
- Drift is small within a sitting if the client recomputes `remaining = end - performance.now()` each tick instead of decrementing a counter once a second. Decrementing a counter drifts and is the thing background throttling breaks.
- Page reload: no client state is needed. The server recomputes remaining seconds on every render, so a reload, a new tab or another device shows the same time. HTMX partial swaps that re-render the page region should carry the fresh remaining value, or the countdown element should live outside the swapped region and be re-seeded from a response header or attribute.
- Background tabs: browsers throttle timers in hidden tabs (Chrome after about 10s, Firefox after 30s, budget based; MDN Page Visibility API). A throttled timer fires late but, with the end-point approach above, shows the right value when it does. Add a `visibilitychange` listener that, on becoming visible, recomputes at once, and if zero or less, fires the auto-submit immediately. Prefer `visibilitychange` over `blur`/`focus` (MDN). Optionally re-sync with the server on becoming visible (a cheap request that returns remaining seconds) to catch long sleep or laptop suspend, where `performance.now()` may not advance in some browsers (inference: treat as a reason to resync, not a proven fact).
- Because a hidden tab may never fire the auto-submit, the server-side enforcement on the next request and the housekeeping sweep are the real guarantee. The client submit is a convenience.
- Moodle: when the learner is active at zero, the attempt is submitted at that moment; "When time expires" only governs attempts left open. Answers entered after expiry earn no marks (Moodle Quiz settings). This matches the settled "late page is not saved".
- A small tolerance for network latency on the final auto-submit post is a common worry. The answer here is already settled (no grace period). The client should therefore post the last page slightly before zero is not advised either; just post at zero and accept that the in-flight page may be rejected. Flag for the spec: decide whether the zero-time post is the only chance to save the current page, since a post arriving after the deadline is dropped by design. A lenient option (inference) is to compare against `deadline` only, with no client-sent timestamp, so no skew exists; the unavoidable cost is the latency of that last post. Worth stating to the learner nothing more than "at zero, the sitting ends".

## 2. Auto-submit races

Races to cover (the sources agree the server decides; none works through these races, so the lock design below is standard practice and my inference):
1. Client auto-submit and a manual submit (or two tabs) arriving together: double completion.
2. Client auto-submit and the housekeeping sweep, or sweep and a request that touches the expired sitting.
3. A late page post arriving as the sitting is completed.
4. Double click or HTMX retry of the submit.

Practice:
- Make completion idempotent: `complete()` on an already completed row is a no-op that returns the existing result and never re-marks or changes the recorded reason. First valid completion wins and its reason sticks (so a late "learner submitted" cannot overwrite "time expired", and the reverse).
- Serialise with a row lock: inside `transaction.atomic()`, load the `FormProgress` with `select_for_update()`, then check `completed_time`, check expiry, then save or complete. Django requires a transaction, blocks by default, and takes `nowait` / `skip_locked` / `of=("self",)`. Use `of=("self",)` if `select_related` joins are present so only the sitting row is locked (Django docs). `SQLite` ignores the lock, and `TestCase` wraps tests in a transaction, so test the lock with `TransactionTestCase` (Django docs). The project uses PostgreSQL, so locks are real.
- Housekeeping sweep: select expired open rows with `select_for_update(skip_locked=True)` inside a transaction (Django docs), so a sweep run never blocks on, or double-handles, a row a request is completing, and two overlapping sweep runs share the work. Complete each row through `FormProgress.complete()` in its own small transaction so one failure does not roll back the rest (inference; fits the "no silent failures" rule if the exception is specific and surfaced).
- A page save and a completion share the same lock, so "page posted after expiry is not saved" is decided under the lock, against server time read after acquiring it.
- Request-time enforcement order for any request touching an open sitting: lock, if open and expired then complete (reason: time expired), then respond as for a completed sitting (redirect to results). The same helper should be called from start, runner pages, results and `form_submit_and_exit`, so there is one code path (project rule: avoid repeating code).
- The auto-submit post from the client should carry a flag or hit a distinct endpoint ("time up") that skips the required-answer check, but the server must not trust the flag to set the reason: it sets "time expired" only if the server confirms the deadline has passed; otherwise it treats it as a normal submit or rejects it. This stops a client early-firing the post (for example after a clock change, the MDL-73960 failure mode) from ending the sitting with the wrong reason. If the post arrives early with the flag, the choices are reject and keep the sitting open, or complete as learner submitted; the spec should pick one (recommend reject, as the client clock is what is wrong).
- Client: disable the submit control and stop the timer after first fire, so one tab posts once. Redirect to results after the response (HX-Redirect or normal redirect). If the post fails (network), retry; the next request of any kind completes it anyway.
- Redis TTL based timers (oneuptime write-up) are an alternative design but add infrastructure; for this project the DB deadline plus sweep is enough.

## 3. Accessibility

- WCAG 2.2.1 Timing Adjustable (A): the essential exception applies when removing the limit would fundamentally change the content and no other conforming way exists (W3C Understanding example: ticket hold). Real-time exception and 20-hour exception also exist. A regulator-mandated exam limit fits the essential exception, so no extend control is needed (matches the settled decision). Techniques SCR16 (warn before expiry) and SCR1 (extend) are the usual pair; with the essential exception only the warning is useful. Source: https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html
- Document the essential-limit reasoning (regulation line, CAR 141.07.1) in the spec, as a conformance statement, and show the limit on the start page before starting. That also serves 2.2.6.
- WCAG 2.2.6 Timeouts (AAA): users must be warned of the inactivity duration that causes data loss, unless data is kept over 20 hours; showing the duration once at the start of the task suffices. It concerns inactivity timeouts, which this spec does not add; relevant to `sacaa-compliance-assessment-controls-4-inactivity-auto-exit` more than here. Source: https://www.w3.org/WAI/WCAG22/Understanding/timeouts.html
- Live regions: ARIA `role="timer"` has an implicit `aria-live="off"`, so changes are not announced; users read it on demand. This is the right default for a ticking countdown. Do not set it to `polite`/`assertive`, which would announce every tick. Name it with `aria-label` (for example "Time remaining"). Source: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/timer_role
- Warnings (5 min, 1 min per the answers): use a separate, visually present message in a dedicated live region (`role="status"` / `aria-live="polite"` for the 5 minute warning; `role="alert"` is defensible for the 1 minute one as it is urgent, though it interrupts) rather than toggling the timer itself. MDN shows a one-off switch to `role="alert"` for a single announcement, then back to `timer` after about 999 ms; a separate region avoids that trick. Announce each warning once, guarded by a "fired" flag so reloads or tab resync do not repeat or skip it incorrectly: on load, if already below a threshold, show the visible state without re-announcing (inference).
- Warnings must be visible as well as announced (not colour alone: add text and an icon), must not take focus or steal it from the question being answered, and must not be dismissed by a timeout shorter than they need to be read.
- Provide the on-demand time: some LMSs let the learner hide the timer (Moodle: hidden timer reappears under 100 seconds) to reduce anxiety and distraction. Optional here; if added, keep the warnings.
- Reduced motion: do not animate the countdown (no pulsing or flashing at low time); respect `prefers-reduced-motion` and use static colour or text changes. Avoid anything flashing more than three times a second (WCAG 2.3.1).
- Sentence format: give the visible timer text in words for screen readers ("4 minutes 30 seconds remaining") through `aria-label` or visually hidden text updated only on demand, while the visible digits stay "04:30" (inference: a common pattern, not from the sources above).
- Colour contrast and no-JS: the start page states the limit in text so it is available without script. Without JS the server still enforces it, and the sitting completes on the next request.
- At expiry, move the learner to the results page; announce the reason there ("Your time ran out and the quiz was marked on the answers saved"), so a screen-reader user is not left with an unexplained page change.

## 4. Auditability

- Store the completion reason as a field on the sitting, set in one place (`complete()`), with a choice field. A `TextChoices` with a stable string value for each reason is easy to extend by later specs (test disturbance adds its own). Default `learner_submitted` means no backfill for existing rows (matches the idea's recommendation).
- Record the reason as decided by the server, never from a client claim (section 2). Also worth recording (a design choice, not required by the idea): the actual `completed_time`, and for expired sittings, the deadline, so an auditor can see how long after the deadline the sitting was closed (a swept sitting may be completed hours later). Recommend that `completed_time` for a time-expired sitting is set to the deadline (`start_time + limit`), not the sweep's run time, or else store both; the spec should decide, because duration-taken reports and attempt-ordering depend on it. This is inference; Moodle does the equivalent by recording the finish time of an overdue attempt as the time limit end.
- Show the reason wherever the result is shown: attempt review and cohort report attempts table (settled).
- A reason value of the sweep versus request-time enforcement need not be separate values; "time expired" covers both. Distinguishing them would add noise for the auditor.
- Because the limit is read from the current form (answer 3), the stored sitting does not remember the limit that applied. For audit, consider whether the recorded deadline matters; the answer says store nothing extra, so keep to that and note the trade-off in the spec.

## 5. Housekeeping sweep of abandoned timed attempts

- A sweep is the standard backstop: Moodle runs a scheduled task that finishes overdue attempts according to "When time expires" (default: submit automatically); its cadence is the operator's schedule. Source: https://docs.moodle.org/en/Quiz_settings (describes the overdue option; the task detail is not on that page).
- Query: open sittings of timed forms whose `start_time + limit` has passed. The limit lives in form content front matter, not on the sitting, so the sweep must resolve each form's current limit (inference: load the open sittings of forms that have a limit, in batches, and compare in Python, or prefilter by oldest possible `start_time`). Use `select_related` as the project requires.
- Run idempotently and safely to repeat: `skip_locked`, per-row transaction, `complete()` is a no-op on completed rows. Keep it in `run_housekeeping_sweeps` using the unscoped manager (settled), and report a count (the project says not to add logging unless asked, so return or print as the existing sweeps do).
- Reason set to "time expired" with a `completed_time` choice as above.
- Do not auto-complete sittings of forms with the limit removed since (answer 3: current limit applies, so none are expired).
- Test: with `TransactionTestCase` for lock behaviour; with plain tests, freeze time and check a request and the sweep produce the same result.

## 6. Points for the spec to decide (summary)

1. Server sends remaining seconds; client uses a monotonic end point and recomputes on `visibilitychange` (recommended).
2. "Time up" post: server verifies the deadline before recording "time expired"; early flagged post is rejected (recommended) or treated as a normal submit.
3. One locked, idempotent completion helper used by all five paths (start, runner, results, `form_submit_and_exit`, sweep).
4. `completed_time` for time-expired sittings: deadline, or actual completion time with the deadline derivable.
5. Timer is `role="timer"` (silent) plus a separate polite live region for the 5 and 1 minute warnings, fired once; no animation under reduced motion.

## References

- https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html
- https://www.w3.org/WAI/WCAG22/Understanding/timeouts.html
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/timer_role
- https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API
- https://docs.moodle.org/en/Quiz_settings
- https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-for-update
- https://tracker-old.moodle.org/browse/MDL-73960
- https://tracker-old.moodle.org/browse/MDL-74817
- https://support.magicjudges.org/t/l2p-exam-timer-malfunction-exam-issues/151
- https://swizec.com/blog/yet-another-hard-lesson-about-time/
- https://community.mendix.com/link/spaces/app-development/questions/145252
- https://laracasts.com/discuss/replies/934798
- https://oneuptime.com/blog/post/2026-03-31-redis-online-exam-timer/view

Note: the Mendix, Laracasts, magicjudges, swizec and oneuptime claims come from a search summary, not a full page read.

status: ok
