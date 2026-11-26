# Research: UX patterns for attempt limits and waits

Topic `ux_patterns` for `sacaa-compliance-assessment-controls-2-attempt-limits`. Decisions from `answers.md` are taken as given: a live countdown, the button enabling in place at zero (server re-checks on click), and a passed quiz refusing a new attempt.

## 1. Project conventions that decide the shape

### Voice (`.claude/skills/brand-guidelines/voice.md`)
- Bad news uses the plain word, never a softer one a reader could take for "not yet". A refusal is named ("Closed", "Declined", "Failed") and the page gives the reason, labelled "Reason". Fits: "No attempts left", not "Attempts exhausted soon" or "Not available".
- "A disabled action shows its reason beside the control, and the control names it with `aria-describedby`." This is a project rule, not just a recommendation. The worked example is a disabled "Generate a new report" with its reason beside it. Do not use a hover tooltip.
- Error messages name the problem and the fix, are brief, and leave blame out. Routine actions end on a full stop.
- Dates and times have one format: `3 Nov 2026, 07:37`, 24-hour, in the viewer's zone, never a locale default. Use `<c-date>` / `<c-datetime>`. A deadline in the learner's own zone uses `{% local_time %}` (Alpine `localTime`, `time_tags` library). A template never writes its own format.
- Terms are "learners" and "content". Two buttons in one row never share a bare verb.

### Existing templates
- Start page: `freedom_ls/learner_interface/templates/learner_interface/course_form.html`. It is a centred `max-w-xl` column: badge, title, authored intro, fact pills (`form_engine/partials/form_facts.html`), `partials/exam_previous_attempts.html`, then `<c-player-footer>` holding one `<c-button>` per entry in `buttons` (`continue`, `start`, `try_again`, `next`, `finish_course`). The whole footer is hidden when `paused`.
- Buttons come from `form_start_page_buttons` (`freedom_ls/learner_interface/utils.py:940`). It returns dicts with `text` and `action` only. A failed quiz gets only "Try Again". No limit, wait or passed information reaches it today.
- Results page: `course_form_complete.html`. A banner (failed, passed, or no pass mark) sits above the score ring and the incorrect-answer review. The footer holds "Retry quiz" only when `quiz_verdict == "failed" and not item_closed`. The copy is already conditional: "This quiz has closed, so it can't be retaken." and "Your access to this course has ended." That is the pattern to extend: one more `elif` per reason, with the invitation to retry only when the footer offers one (the existing template comment says exactly that).
- Note the button text differs between pages ("Try Again" on the start page, "Retry quiz" on the results page). The idea and `answers.md` call both "Try Again"/"Start". The spec should either unify the wording or name each.
- `<c-button>` (`freedom_ls/base/templates/cotton/button.html`):
  - It takes `disabled` and `aria_describedby`.
  - It renders an `<a href>` when `href` is set, otherwise a `<button>`. The `disabled` attribute is emitted in both cases, but `disabled` is not valid on `<a>`. A disabled `<a>` stays focusable and clickable.
  - So a locked or waiting state must render as a real `<button disabled>` with no `href`, or as a link-less control. Only the enabled state is a link to `form_start`.
  - The Start and Try Again buttons today all carry `href`. That is a trap to flag for the spec.
- Existing precedent for a disabled button with its reason: `educator_interface/modal/move_confirmation.html:64` (`disabled="true" aria_describedby="move-disabled-reason"`) and `educator_interface/panels/cohort_report_downloads.html:26` (`aria-describedby` to a `-limit` message).
- `<c-callout tone="info|success|warning|error">` (`base/templates/cotton/callout.html`):
  - It is a static status box with an icon, an optional bold `title` and a slot.
  - `error` renders `role="alert"` and `success` renders `role="status"`. `info` and `warning` have no live role, so they are read in place.
  - For a locked quiz, `tone="warning"` or `"error"` with a plain title ("No attempts left") fits. Use `error` only if the page should announce it on arrival. A callout on page load rarely needs `role="alert"`, so prefer `warning`.
- Icons (`<c-icon name=...>`): `error`, `success`, `complete`, `retry`, `check`, `next`, `home` are already used on these pages. Check `Skill(fls-dev:icon-usage)` for a clock or lock name. `claude_plugins/fls-dev/skills/icon-usage/SKILL.md` is the authority for adding one. I did not verify that a clock or lock icon exists.
- Alpine inventory (`claude_plugins/fls-dev/skills/alpine-js/SKILL.md`): `localTime` rewrites a server-rendered instant into the viewer's zone. `refreshTimer` polls `hx-get` on an interval. `dateEyebrow` refreshes when the tab is shown again. No countdown component exists, so the spec needs a new `Alpine.data` in `learner_interface/static/learner_interface/js/alpine-components.js`. It must follow `Skill(ds:alpine-js)` and be listed in the inventory table. Existing practice in `audioReveal` is a `role="status"` line that announces only on a meaningful change. That is a useful model.
- Existing live regions in the project: `partials/messages.html` (`role=status aria-live=polite`), `comms/partials/recipient_picker.html:57` (`sr-only` polite status).
- Template conventions: `claude_plugins/fls-dev/resources/templates_and_cotton.md` (HTMX 422 convention, cotton usage). I did not find rules in it about disabled or countdown patterns.

## 2. Patterns elsewhere

### Attempts used and left
- Moodle sets "Attempts allowed" on the quiz and shows it in the quiz info before the learner starts. It has group and user overrides. https://docs.moodle.org/en/Quiz_settings
- Common shape across LMSs and exam tools: a short fact line near the start action. Two forms are in use. One is "Attempt 2 of 3". The other is "Attempts used: 2 of 3 · 1 left". Both are plain text, not a progress bar. Several LMSs also list past attempts. FLS already has "Previous attempts", so this spec only adds the counts.
- Claim not sourced from a fetched page, from general knowledge of Moodle and Canvas behaviour: the count is shown before starting, so the learner knows what a start costs.
- Fit for FLS: add to the fact pills (`form_facts.html`) or directly above the footer as "Attempts: 2 of 3 used, 1 left". On the results page, put it in the banner paragraph or as a line under the banner. Use words and digits, not colour alone.

### "No attempts left" locked state
- Moodle lists the finished attempts and replaces the start button with "No more attempts are allowed". The retrieved docs page does not describe that message. This is from memory and not verified.
- Good pattern: say the state plainly, say what the learner can do, and name the contact. Without a contact the learner hits a dead end.
- FLS decision already taken: no automatic restart, staff restart by hand (spec 7). So the copy should be something like "No attempts left. You used all 3. To try again, ask your educator to restart the course for you." Which word to use for who to contact ("educator" is the term in `educator_interface`) should be checked against `Skill(fls-dev:domain-glossary)`. There is no per-course contact field that I found. A generic "ask your educator" avoids inventing one.
- The wording should say "restart the course", because that is what the regulation requires ("redo the course for readmission", from the idea). Check the final noun against spec 7's name.
- Replace the button with the reason, or keep it disabled with the reason beside it. The voice rule says disabled plus reason. For a state that will not change by itself, hiding the button and showing only the explanation is also defensible, because a disabled button that can never enable invites repeated clicking. Recommendation: keep the button visible and disabled for a wait, which ends. For a used-up cap, show the callout and omit the retry button, as the existing `item_closed` branch does (the results page withholds "Retry quiz" when closed). That matches existing practice.

### A running wait with a countdown
- Format by length (common practice across timers and rate-limit UIs, not tied to one fetched source):
  - Under 1 minute: seconds, "45 seconds".
  - 1 to 60 minutes: "12 min 30 s" or "in 12 minutes". Update each second only inside the last minute or two. Per-second updates for a multi-hour wait are noise.
  - Hours: "2 h 15 min", dropping seconds. Update once a minute. Show seconds only in the final minute.
  - Over a day: "1 day 3 h". The idea's examples top out at 2.5 hours, and the list is whole minutes, so the hours-and-minutes form covers it. Do not design a days form unless a wait can exceed 24 hours; the spec should decide a maximum or accept long waits rendering as hours.
- Show the absolute time alongside: "Next attempt opens at 14:35 (in 2 h 15 min)". The learner can plan around a clock time, and a countdown alone is wrong if the tab sleeps. Use `<c-datetime>` or `{% local_time %}` for the clock part, so it follows the viewer's zone and the project format. The idea's open question recommended this (clock plus "in 40 minutes"); the answer changed only the "no live countdown" half.
- Computation: render the end instant server-side as an ISO value in a `<time datetime=...>`. The browser computes the remainder from `Date.now()` against that instant, not by counting ticks. Counting ticks drifts when the tab is throttled or the laptop sleeps. Recompute on `visibilitychange`, as `dateEyebrow` does. Clock skew between server and browser can make the button enable early or late; this is why the server re-checks on click. Consider rendering the server's remaining seconds too and using it as the base, to avoid trusting the learner's clock. This is a design choice for the spec.
- What happens at zero (decided: enable in place). Practical points:
  - Swap the disabled state, text and `href` without a reload. Either change the DOM through Alpine, or let the countdown hit an HTMX endpoint that returns the real button. HTMX gives the server the final word and reuses the same template as the page load, so a clock-skewed browser cannot enable early. The page already uses `refreshTimer`.
  - Announce the change once, politely: a `role="status"` line "You can start the next attempt now." Never announce each tick.
  - Move no focus. Focus theft at zero would be disorienting. If the button was already focused, keep it focused.
  - The click still goes to `form_start`, which re-checks. If the browser was early, `form_start` shows the refusal page with the correct time. That page must be a readable state, not a bare 403.
- Accessibility of the timer itself:
  - A live-updating countdown must not sit in a live region that speaks every second. Keep the ticking text outside live regions, or `aria-hidden` it, and give the polite `role="status"` line only at set milestones (for example at the start and at zero). Static text with the absolute time is the screen reader's source of truth. Milestone announcements are judgement from general ARIA practice, not a cited rule.
  - WCAG 2.2.1 Timing Adjustable covers time limits set by the content. A wait before retry is not a limit on the learner's work, but the W3C notes a retry delay is often a security measure and the exceptions (real-time event, essential) rarely fit. The fair reading: this wait is a regulatory requirement, so a case for "essential" exists, but it should be argued in the spec rather than assumed. The control the learner has is simple: nothing is lost by leaving, and the page can be revisited. https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html
  - `prefers-reduced-motion`: a text countdown has no motion, so no issue.
  - No-JS: render the absolute time and the server-computed remaining time as static text. With JavaScript off the learner sees the clock time and, on click after the wait, gets in. This keeps the start page honest if Alpine fails.

### A passed quiz that cannot be retaken
- Common pattern: no retry button. The results page shows the pass banner and "Continue". The start page shows the best or latest score and "Next". No explanation is needed on the happy path, because a passed learner is not looking for a retake.
- The case that needs words is the learner who arrives by a stale link or by typing `form_start`. Per the settled decision, the gate refuses and shows a reason. The copy should be: "You passed this quiz, so it can't be retaken." plus a link to continue. Use the existing phrasing pattern ("it can't be retaken", already in `course_form_complete.html` for a closed quiz).
- Today the start page for a passed quiz shows "Next" or "Finish Course" via `form_start_page_buttons`. That already omits "Try Again", so the UI change for passed is small. Only the refusal page and the server check are new.
- Do not show "attempts left" on a passed quiz in a way that implies more can be taken. Either hide the "left" count, or say "Passed on attempt 2 of 3". Decide in the spec.

### Disabled vs hidden buttons, and how the reason is attached
- Hide when the action will never apply in this state (passed, or cap used with no wait): the existing code does this already for a closed quiz and for a passed quiz. Show disabled when the state is temporary and the learner should see what they are waiting for (a running wait). This follows the usual guidance that a disabled control with a visible reason is better than an unexplained absence, and hiding is better than a permanently dead button.
- Attach the reason:
  - A visible text node next to the button, with an `id`, and `aria-describedby="<id>"` on the button. This is the project rule and `<c-button aria_describedby=...>` already supports it.
  - Do not rely on `title` or hover tooltips. They are not shown to keyboard or touch users and are inconsistent in screen readers.
  - The native `disabled` attribute removes the button from the tab order, so a keyboard or screen reader user may never reach it and never hear the description. The usual answer is `aria-disabled="true"` (the button stays focusable, and the click is ignored or refused with the reason). The project's existing precedent uses native `disabled` with `aria-describedby`, so following it is consistent but has this limit. With native `disabled` the visible reason text sits right beside the control and is read in reading order, which covers the screen reader browse case. I could not fetch the CSS-Tricks article on this (the fetch returned a loading page), so the `aria-disabled` advice is from general knowledge. Cite it as unverified: https://css-tricks.com/making-disabled-buttons-more-inclusive/
  - The `<c-button>` has no `aria-disabled` support today. If the spec wants a focusable disabled button it must add it, which is a cotton change. Keep the cost in mind: native `disabled` plus a visible reason next to it matches existing practice and needs no component change.
  - The reason element must be present at page load, not injected, and when the countdown ends, update both the button and the reason together (clear or replace the reason, and drop `aria-describedby` or point it at the new text). A stale "You can try again in 0 s" description on an enabled button is a bug.

### Start page versus results page
- Start page (before): the learner decides whether to begin. Show the whole picture: attempts used and left, the pass mark, the wait if one is running, and the action or its reason. The numbers are most useful here, before a choice that costs an attempt. A caution before the last attempt is a known pattern ("This is your last attempt") and is cheap: a line on the start page when attempts left is 1. Not requested in the idea, so only list it as optional and do not build it (project rule: build only what is asked).
- Results page (after): the learner has just failed. Lead with the verdict, then the consequence of it: "1 attempt left. You can try again at 14:35 (in 59 minutes)." The next action sits in the footer where "Retry quiz" is today. The wait applies after a failed attempt only, so the first time the learner sees a wait is usually right after submitting. Both pages must therefore render the same wait from one shared template partial and one shared context object, so the numbers and wording cannot drift. That also serves the "avoid repeating code" convention.
- After the countdown finishes on the results page, the same in-place enable applies. Keep the "Continue/Return to course" fallbacks the existing footer logic chooses.
- Paused learner and ended access: existing branches hide the footer entirely. The new messages must not appear to contradict them. A paused learner should not see a live countdown that enables a button that is not shown.

## 3. Suggested copy (checked against voice.md; to be adjusted in the spec)
- Count line: "Attempt 2 of 3 used. 1 left." / no limit: show nothing about a cap, or "Attempts: 2 so far" only if useful.
- Wait: "You can try again at 14:35 (in 59 min)." Reason label for a disabled button: "Reason: next attempt opens at 14:35." The brand rule wants the label "Reason" for a reason.
- Zero: "You can try again now."
- Cap used: "No attempts left. You used all 3. Ask your educator to restart the course so you can try again."
- Passed: "You passed this quiz, so it can't be retaken."
- Refusal page after URL typing: the same text as the matching state above, plus a link back to the quiz start page. Keep the status code decision (403 vs 200) for the spec; it affects `form_declaration` too, which shares the gate.

## 4. Points for the spec writer
1. `<c-button href>` plus `disabled` is not a working disabled link. Render a real button or no `href` when blocked.
2. No countdown component exists. A new `Alpine.data` is needed, with the inventory table in `claude_plugins/fls-dev/skills/alpine-js/SKILL.md` updated, and a no-JS fallback of absolute time plus static remaining time.
3. `form_start_page_buttons` returns only `text` and `action`. It needs the limit and wait state (or a sibling function does) so the start and results pages share one decision, with the server gate as the real check.
4. Compute the countdown from an absolute instant, not ticks; recheck on `visibilitychange`; re-render through the server at zero if the spec wants the server to have the last word.
5. Announce zero once with `role="status"`; never put the ticking text in a live region.
6. Start-page and results-page button text differ ("Try Again" vs "Retry quiz"). Decide one name.
7. Decide whether a used-up cap hides the retry button (matches the closed-quiz branch) or shows it disabled.
8. Say who to contact in generic words ("your educator"); there is no contact field.

## Sources
- WCAG 2.2 Understanding 2.2.1 Timing Adjustable: https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html
- WCAG technique ARIA19 (alert/status live regions, present at load): https://www.w3.org/WAI/WCAG22/Techniques/aria/ARIA19
- Moodle quiz settings (attempts allowed, enforced delay between attempts, first and later attempts): https://docs.moodle.org/en/Quiz_settings
- CSS-Tricks, Making disabled buttons more inclusive (not retrieved, cited only for the advice that is marked unverified above): https://css-tricks.com/making-disabled-buttons-more-inclusive/
- Project: `.claude/skills/brand-guidelines/voice.md`; `freedom_ls/learner_interface/templates/learner_interface/course_form.html`, `course_form_complete.html`, `partials/exam_previous_attempts.html`; `freedom_ls/learner_interface/utils.py:940`; `freedom_ls/base/templates/cotton/button.html`, `callout.html`, `datetime.html`; `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`.

status: ok
