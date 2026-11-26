# Research: UX patterns for timed tests

Scope: start-page wording, countdown, warnings, expiry, results page, educator display. Terms follow the FLS glossary (learner, test, sitting, educator). Web sources are cited. Items marked (unverified) come from general knowledge, not a fetched page.

## What the FLS UI already gives us

- The runner (`freedom_ls/learner_interface/templates/learner_interface/course_form_page.html`) has a top bar that is fixed by a flex column (`flex-none`). Left is the exit X, centre is the title, right is "N of M answered" (`text-sm text-muted whitespace-nowrap`). Below it is a progress strip. The countdown fits naturally in the top bar, next to or replacing the answered count on narrow screens.
- A polite `aria-live` region already announces "Page X of Y". It is `sr-only` with `aria-atomic`. Warnings need a separate region so page announcements do not overwrite them.
- Alpine is the CSP build: methods are registered in `alpine-components.js` and templates carry no inline expressions. The timer is therefore a registered component, e.g. `examTimer`.
- `form_declaration.html` is the pre-start page. It uses `c-callout tone=...`, `c-button`, `c-player-footer`, and `data-testid`. A limit notice can sit there as a `c-callout`. The no-JS fallback matters because the runner supports no-JS submit.
- Voice (`.claude/skills/brand-guidelines/voice.md`):
  - Use plain outcomes for adults. "Failed" and "Declined" are named plainly, never softened. A softer word that could mean "not yet" fails.
  - A label names what the value is. The reason text is labelled "Reason".
  - Error text names the problem, suggests the fix, and ends routine actions with a full stop.
  - Dates use `<c-datetime>` or `{% local_time %}`. Durations are not covered; the spec must pick one format.
  - Learners are "learners", not "students".
  - Direct over diplomatic. So "Time ran out", not "Unfortunately your session has concluded".
- Existing copy to stay consistent with: "Leave the test?", "Leave and submit", "Ready to submit?", "Your progress is saved — you can resume later."
  - The exit-dialog copy changes with a limit. The clock keeps running after "Leave and save", so the current "you can resume later" becomes untrue. Per the voice rule that every sentence in a confirm is true after the action, say that the time limit continues while you are away.
  - The `beforeunload` warning already exists in `examRunner`.

## 1. Start-page wording of the limit

Common pattern: state the limit before the learner commits, in plain words, next to the other rules (attempts, pass mark).

- Moodle shows the time limit on the quiz view page, and a confirm dialog "Your attempt will have a time limit of X. When you start, the timer will begin to count down and cannot be paused. You must finish your attempt before it expires. Are you sure you wish to start now?" (unverified wording; the behaviour is documented in https://docs.moodle.org/en/Quiz_settings).
- GOV.UK guidance on timeouts (https://design-system.service.gov.uk/patterns/session-timeout/): tell users before the limit applies, say plainly what happens at the end, and say what is saved. That is session-timeout guidance, but the wording principles carry over.
- NN/g, on time pressure and the importance of telling people up front (https://www.nngroup.com/articles/timed-tasks/ (unverified URL; search "NN/g time limits web")).

Suggested wording for FLS:
- Callout, before the start button: "This test has a time limit of 45 minutes. The clock starts when you press Start and does not stop if you leave. When time runs out, your test is submitted with the answers you have saved."
- Format the limit as "45 minutes", "1 hour 30 minutes", or "1 hour". Do not use "45:00" or "PT45M".
- The start button names what the person does: "Start test". The primary button is not "Begin timer".
- On resume, show the time left, not the full limit: "You have 12 minutes left."
- Because the clock keeps running on exit, the existing "you can resume later" copy is wrong for a limited test. Replace it with "Your answers are saved. The time limit keeps running while you are away."

## 2. Countdown placement and format

- Placement. Moodle puts the timer in a quiz-navigation block that is sticky on desktop. On mobile it collapses to a header strip (https://docs.moodle.org/en/Quiz_settings). Canvas shows an elapsed or remaining clock fixed at the top right of the quiz page (unverified). Pattern: always visible, top right, never scrolled away.
- FLS: put it in the runner top bar right slot. On narrow screens put the countdown first and drop the "answered" text to a compact "3/10". The top bar is already `flex-none`, so it never scrolls. This avoids a second sticky element, which would cost height on small phones.
- Format:
  - `mm:ss` under 1 hour.
  - `h:mm:ss` only when the limit is 1 hour or more. Show seconds in the last 5 minutes or once the limit is short.
  - Common alternative: show whole minutes ("23 min left") until the last 5 minutes, then switch to `m:ss`. This removes visual noise and reduces anxiety, and it makes ticking less distracting for screen-reader users.
- Visually update every second. Do not announce each second (see section 4).
- Base the clock on the server's expiry time, not a client counter. Compute `remaining = expires_at − server_now` on each page render and tick locally. Re-sync on every request, because tabs sleep and clocks drift. This fits the answers: no extra stored state, limit read from the form as it is now.
- Hide/show toggle. Moodle has a "Hide" button on the timer. The time reappears when fewer than 100 seconds remain (https://docs.moodle.org/en/Quiz_settings). It exists because a constantly visible countdown increases anxiety and distracts, particularly for neurodivergent learners. WCAG 2.2.2 (Pause, Stop, Hide) concerns moving information (https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html (unverified URL)). A hide toggle is cheap, so I recommend one: a button with `aria-pressed`, labelled "Hide time" or "Show time". The time must come back automatically at the 5-minute and 1-minute warnings, and the toggle must not suppress the warnings. Moodle's 100-second reappearance is a precedent; ours is tied to the warning points instead. Hiding the clock must not hide the limit from screen readers, which can still ask for it by key.
- If the toggle is out of scope, note it as a recommendation, not a requirement.

## 3. Colour and emphasis near the end

- Pattern: neutral until the final 5 minutes. Then amber/warning tone. Then red/error tone in the final minute. Pair every colour change with text or an icon, since colour alone fails WCAG 1.4.1 (https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html (unverified URL)).
- Contrast must be 4.5:1 or better in every state, including the red.
- Do not blink or flash. Do not pulse (WCAG 2.3.1 three-flashes, and 2.2.2).
- Do not use a shrinking progress bar as the only indicator.
- FLS fit: the existing tokens `text-muted`, `text-error`, and the callout tones (`c-callout tone="error"`). Check the tailwind theme for a warning token.

## 4. Warnings (5 min and 1 min; screen-reader announced)

Answers.md decision: warnings at 5 and 1 minutes, none when the limit is 5 minutes or less. The extra rule from the first-warning logic: with a 6-minute limit, the 5-minute warning fires one minute in. Consider also suppressing the 5-minute warning when it would fire within the first minute (e.g. for limits up to 6 minutes). The spec should state the exact rule.

- Presentation: an inline banner in the runner under the top bar (a `c-callout`) is better than a toast. A toast times out and can vanish before a keyboard or magnified-screen user reads it. WCAG 2.2.1 gives people control over timing, and toasts that auto-dismiss are a known problem (https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html). Make the banner persist until dismissed, or until the next stage replaces it.
- Do not put focus on the banner and do not use a modal. Stealing focus mid-answer loses the learner's place, and typed text in a textarea may be affected. A non-modal banner with an announcement is the pattern.
- Announcements:
  - Use one dedicated, always-present live region, separate from the page-progress one.
  - Set `aria-live="polite"` with `aria-atomic="true"` for the 5-minute warning.
  - For the 1-minute warning, `role="alert"` / assertive is defensible, because it is urgent and the learner has seconds. Use assertive only for the last warning and the expiry. Otherwise the learner's screen reader interrupts their own answer reading.
  - The region should be present in the DOM at page load and updated afterwards. Inserting a region and its text together is not reliably announced.
- `role="timer"` pitfalls (https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/timer_role):
  - It is a live region, but its implicit `aria-live` is `off`. A ticking counter is therefore silent by default, which is desired.
  - Do not set `aria-live="polite"` on the ticking element. The learner would hear every second.
  - Use `role="timer"` on the visible countdown. Pair it with `aria-atomic="true"` so a screen reader reads whole values, not changed digits.
  - Announce thresholds through the separate warning region (or MDN's pattern: swap to `role="alert"` once, then back), not through the ticker.
  - Guard each announcement with a fired-flag. MDN's example can fire twice because the matching value lasts about a second.
  - Give the timer an accessible name, e.g. `aria-label="Time remaining"`, only if it helps. Otherwise omit it.
- Warning wording (voice: direct, specific):
  - 5 minutes: "5 minutes left. Your test is submitted automatically when time runs out."
  - 1 minute: "1 minute left. Your saved answers are submitted when time runs out. Answers on this page that you have not saved are lost."
  - The second sentence is true because of the "no grace period" decision. Say it plainly.
- Unsaved answers. A page is saved only on Next, so at expiry the answers on the open page are not saved unless posted before expiry. The 1-minute warning should say so. Consider an auto-post of the current page when the client clock reaches zero. That is a spec decision, and it must respect "a page posted after expiry is not saved". The client could post slightly before expiry, but the server decides.
- No extend control. WCAG 2.2.1 lets a limit stay when it is essential (https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html). The essential exception: removing the limit would fundamentally change the assessment, and an extension would invalidate it. A warning-plus-extend option (at least 20 seconds to extend, at least 10 times) is only one of three alternatives, and is not required here. Record the exception in the spec text and in the educator docs. Educator-granted extra time for a learner with an accommodation is a different mechanism (a per-learner limit), and is outside the decisions so far; flag it as a likely follow-up.

## 5. The expiry moment

- Common pattern (Moodle): by default open attempts are submitted automatically with the answers saved so far. Optional grace period, or "must be submitted before time expires or the attempt is not counted". Moodle also notes that when the learner is actively working at zero, the attempt is submitted at that moment (https://docs.moodle.org/en/Quiz_settings). FLS chose submit-with-saved-answers and no grace period, which matches Moodle's default with the grace period off.
- Client side at zero:
  - Stop the ticker and show "00:00".
  - Disable inputs, then post the form or redirect to the server's expiry handler.
  - Announce once, assertively: "Time is up. Your test is being submitted."
  - Turn off the `beforeunload` guard so the browser does not show "Leave site?".
- Server side: any request after expiry, whether the learner reloads, presses Next, or opens the URL later, must run the same finish (mark on stored answers, set the finish reason) and then redirect to the results page. Make this idempotent. It covers the learner who closes the tab, since nothing runs in the browser then. The finish can happen lazily on the next request.
- A late POST gets no "page saved" success. Redirect to the results page with the time-ran-out message. Do not show a validation error; it is not the learner's input that is wrong.
- Non-JS fallback: the page shows the limit and the expiry time as text. The server enforces it either way. Use `{% local_time %}` or `<c-datetime>` for "must finish by 14:35".

## 6. Learner results page ("time ran out")

- State the cause near the top, in plain words, before the score: "Time ran out. Your test was submitted at 14:35 with the answers you had saved." The word is "Time ran out", not "Session expired" or "Not completed" (voice rule 5).
- Say what was counted: "You answered 7 of 10 questions. Unanswered questions score 0." (unverified that this matches scoring; check the scoring strategy.)
- Show the answered count, which the runner already tracks.
- If the learner can retry (attempt limits are the sibling spec), link the next step: "You have 1 attempt left." Do not promise anything the attempt limit does not give.
- Do not blame: GOV.UK error style is to name the problem without blame (https://design-system.service.gov.uk/components/error-message/).
- Screen readers: put the message in the page heading area, or use a `role="status"` region. It must not be a toast.
- Previous-attempts partial (`partials/exam_previous_attempts.html`) should carry the same reason per row, so the learner can tell a time-out from a submit.

## 7. Educator display of the finish reason

- Pattern: one column labelled "Finished", with a small text badge: "Submitted" or "Time ran out". Moodle's attempts report states "Finished" with the time taken, and distinguishes states such as "Never submitted" or "Submitted" (unverified). Canvas moderation shows "Auto-submitted" style flags (unverified).
- Recommendations:
  - Label the column "Finished by" (or "How it finished"), with values "Submitted" and "Time ran out". It names what the value is (voice rule 6). Add "Left the test" only if the product has that state.
  - Use a badge for a non-default reason and plain text for the default. "Time ran out" gets a warning-tone badge; "Submitted" gets none or a neutral one. This makes timed-out sittings easy to scan.
  - Never use colour alone; the text is the signal.
  - Show the time used beside it, e.g. "44:58 of 45:00", when the timestamps exist. Educators then see the difference between full-time and early submit.
  - Make it filterable and sortable, as it is an audit field for compliance review (SACAA).
  - On the detail view, include the limit that applied. By the "current limit" decision, nothing is stored on the sitting, so the detail shows the finish reason and times, and the limit is the form's present value. If the educator changed the limit afterwards, the displayed limit can disagree with what applied at the time. The spec should either store the reason only, or accept and document this. This is a compliance risk worth flagging.
  - Use `<c-datetime>` for times (voice: dates and times).
  - An export (CSV) should contain the same reason as text, not an icon.
- A sitting finished by an educator or by the system is a separate reason from "Time ran out". Keep the value set small and explicit.

## Open questions for the spec

1. Exact rule for the 5-minute warning with limits of 5 to 6 minutes. Answers say no warnings at 5 minutes or less.
2. Does the client auto-post the open page just before zero, or only the server finish at expiry?
3. Hide/show toggle: in scope or not? If yes, tie reappearance to the warnings.
4. Does the exit dialog copy change when a limit applies? ("you can resume later" becomes misleading.)
5. How the educator sees the limit that applied, given nothing is stored on the sitting.
6. Per-learner extra time for accommodations: out of scope, but WCAG 2.2.1 essential-exception reasoning says the limit must not be waivable by the learner. Note it as a follow-up.

## References

- WCAG 2.2 Understanding 2.2.1 Timing Adjustable: https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html (fetched)
- MDN ARIA timer role: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/timer_role (fetched)
- Moodle quiz settings (time limit, hide timer, when time expires): https://docs.moodle.org/en/Quiz_settings (fetched)
- GOV.UK session timeout pattern: https://design-system.service.gov.uk/patterns/session-timeout/ (not fetched)
- GOV.UK error message component: https://design-system.service.gov.uk/components/error-message/ (not fetched)
- WCAG 2.2 Pause, Stop, Hide: https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html (not fetched)
- WCAG 2.2 Use of Color: https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html (not fetched)
- Canvas student guide on timed quizzes: https://community.instructure.com/t5/Student-Guide/How-do-I-take-a-quiz-with-a-time-limit/ta-p/545 (redirected, not fetched)
- NN/g: not verified; no confirmed URL.

status: ok · reason: Moodle, MDN and W3C 2.2.1 were fetched. The GOV.UK, Canvas, NN/g and other WCAG pages were not fetched and are marked as unverified in the text.
