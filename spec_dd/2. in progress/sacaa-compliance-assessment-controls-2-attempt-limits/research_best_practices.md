# Best practices: attempt caps and escalating waits

Scope: server-enforced attempt cap and wait list, with a learner countdown (Django, HTMX, Alpine). Applies the settled decisions in `answers.md`. Regulation context is not repeated.

## 1. Server-authoritative enforcement and races

- The browser only displays state. Every rule (cap, wait, passed) is decided on the server at start. The countdown is a convenience; a click at zero is re-checked.
- Check and create must sit inside one transaction holding a lock that both concurrent starts contend on. The idea already names it: the `CourseProgress` row lock in `start_attempt`. Use `select_for_update()` on that row inside `transaction.atomic()`. Django requires an active transaction, and under `ATOMIC_REQUESTS=False` the lock is released at the end of the `atomic` block. Read the counts and the latest attempt after the lock is taken, in the same transaction, not before. (Django docs: https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-for-update; PostgreSQL row locks: https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS)
- Lock a parent row rather than counting rows and hoping. A count-then-insert at READ COMMITTED is racy because two transactions both see N-1 and both insert. Locking the parent serialises them. A unique constraint cannot express "at most N rows", so the parent lock is the right tool here.
- Order inside the lock: (1) stale-open-attempt handling, unchanged; (2) reuse of an open attempt returns early and is never blocked; (3) passed check; (4) cap check; (5) wait check; (6) create. Return a typed refusal object (reason enum plus the numbers and opens-at) rather than raising, so views choose the response.
- The gate in the view (`_form_start_gate`) may run the same check without the lock to pick the page quickly, but `start_attempt` is the authority. Build one pure function (`attempt_status(progress, form, now)`) returning used, left, next_open_at and refusal reason. Call it from the gate, `start_attempt`, the start page and the results page. This avoids repeating the rule in templates.
- Derive counts and waits from stored `completed_time`; do not store a counter (matches the idea). Pass `now` into the function so tests do not need to sleep.
- Test the race with two real threads or processes against PostgreSQL (`pytest.mark.django_db(transaction=True)`). A single-thread test cannot show the lock works.

## 2. Time measured from completion

- Wait for failure N is `list[min(N, len) - 1]` minutes, measured from the failed attempt's `completed_time`. Compute `opens_at = completed_time + timedelta(minutes=m)` and compare `now >= opens_at` (open at exactly zero, so the client and the server agree on the boundary).
- Only the latest failed attempt matters for the "next opens" time, but N is the count of failures, not of all attempts. Define precisely whether N counts all failures under the `CourseProgress` record at this form (the idea implies yes).
- Use the server clock (`timezone.now()`) only. Compare in UTC datetimes. Do not trust any time from the browser at the click.
- Edge: a wait that already elapsed when the page was rendered must show an enabled button, not a "0 minutes" message.

## 3. Clock skew and the countdown

- Browser clocks drift and users change them. Do not compute remaining time as `opens_at - Date.now()` using an absolute server timestamp alone.
- Recommended: render both `remaining_seconds` (server computed at render) and the absolute `opens_at` ISO. Client starts a monotonic timer at load: `target = performance.now() + remaining*1000` and derives the display from `performance.now()`, which is immune to wall-clock changes. Use the absolute time only for the static "opens at" text. (Pattern widely used for countdowns; see MDN `performance.now`: https://developer.mozilla.org/en-US/docs/Web/API/Performance/now)
- Caveat: `performance.now()` can pause while a laptop sleeps or a tab is throttled in some browsers. Handle `visibilitychange` (and a `pageshow`) by re-fetching the status (an HTMX `hx-get` to a small partial) rather than trusting the timer. That also fixes sleeping devices.
- Network latency makes `remaining_seconds` slightly stale (by one round trip). Round up, so the button never enables early; the server re-check on click is the backstop.
- At zero: enable the button in place (Alpine `x-data` toggling `disabled`, or swapping the partial via HTMX). If the server still refuses (skew, rounding), the click returns the refusal page with a fresh time. This must not loop. Offer a second re-poll with a small delay, not a tight retry.
- Without JavaScript: the server-rendered text ("opens at 14:30, in about 40 minutes") is the fallback, and the button stays a real form submit that the server decides. Progressive enhancement.

## 4. Accessible countdown

- WCAG 2.2.1 Timing Adjustable (Level A) covers time limits set by content. A wait before a retry is a content-imposed delay, not a limit on completing a task, so the "turn off / adjust / extend" options do not obviously apply. The cooldown is a regulatory control. Record that as the exception rationale in the spec and do not claim it is adjustable. Still give users the information they need. (https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html)
- Do not announce every second. `role="timer"` has an implicit `aria-live="off"`, so updates are silent by default, which is right for a ticking value. (MDN: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/timer; WAI-ARIA spec: https://www.w3.org/TR/wai-aria-1.2/#timer)
- Practical pattern:
  - A visible countdown element with `role="timer"` and no live announcement (the per-second text may be `aria-hidden="true"` if a screen-reader-friendly sibling exists).
  - A static sentence the screen reader reads on focus: "Next attempt opens at 14:30 (in about 40 minutes)". Prefer coarse units, whole minutes while above one minute.
  - A separate visually hidden `aria-live="polite"` region (not `assertive`) updated rarely: at coarse milestones only (for example 10 min, 1 min) and once when the button becomes available ("You can now start your next attempt"). Update it with a text change, not a re-render of the region, so that it is announced reliably.
  - Move no focus when the button enables. Changing `disabled` without moving focus is correct. Prefer `aria-disabled="true"` plus an explanation linked by `aria-describedby` over bare `disabled`, because a disabled button drops out of the tab order and a screen-reader user may never learn why. If using `aria-disabled`, the click handler must do nothing and the server still refuses.
- Reduced motion: a ticking number is not animation, but avoid any pulsing, flipping or animated rings, and wrap any such effect in `@media (prefers-reduced-motion: no-preference)`. (https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion; WCAG 2.3.3 https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)
- Do not rely on colour alone (WCAG 1.4.1), keep contrast on the disabled state at 4.5:1 for the explanatory text (the text carries the meaning, the button need not meet contrast when inactive, but the text should), and make the explanatory text real text, not a tooltip.

## 5. Wording refusal messages

State what happened, why, and what can be done next, with concrete numbers. No blame, no jargon, no error codes. Draft wording:

- Wait running: "You can start your next attempt at 14:30 (in 40 minutes). You have used 1 of 3 attempts, so 2 are left." Add "Use the time to review the material" only if the course offers it.
- Cap used: "You have used all 3 attempts for this quiz, so it is now locked. To continue, contact your course administrator." Name who to contact if the config has one; do not promise a restart exists.
- Passed: "You have already passed this quiz, so a new attempt is not needed."
- Rules: say "attempts left", never "retries remaining" ambiguity (a first attempt is not a retry). Use the same terms on the start page, the results page and the refusal page. Use one reason enum per message so tests assert the reason, not the string. Put the refusal text in the page body, not only in a transient toast, so assistive tech and reloads keep it.
- State the rule before the learner spends an attempt where possible: show the cap and the waits (for example "3 attempts, with waits between failures") on the start page. Research on error messaging (Nielsen Norman Group, https://www.nngroup.com/articles/error-message-guidelines/) supports plain, specific, constructive wording.

## 6. HTTP status for a refused start

- A normal page navigation (typed URL, bookmark, a stale tab) should get a rendered, explanatory HTML page, not a bare error and not a silent redirect that hides the reason. Today's gate only redirects, which loses the reason; the spec needs an outcome that renders it.
- Recommended: render the refusal page directly at the start URL with a status that matches meaning:
  - Wait running: `429 Too Many Requests` fits semantically (rate limiting) and allows `Retry-After` (seconds or HTTP date), which is useful to clients. (RFC 6585 https://www.rfc-editor.org/rfc/rfc6585#section-4; RFC 9110 Retry-After https://www.rfc-editor.org/rfc/rfc9110#section-10.2.3). Counter-view: 429 usually means too many requests in a window, and monitoring tools treat it as abuse. 409 Conflict (request conflicts with current state of the resource) is also defensible for every refusal reason, and the simplest consistent choice. (RFC 9110 §15.5.10 https://www.rfc-editor.org/rfc/rfc9110#section-15.5.10)
  - Cap used or passed: 409 or 403. 403 means "understood, will not authorise", and that matches a locked quiz, but it can read as a permission fault and trips generic 403 handlers and templates. 409 is the lower-risk choice. Pick one status and document it in the spec; do not mix.
- Do not use `redirect` to a results page with a message in the session for the typed-URL case: it is lossy and loses the reason on refresh. A redirect after POST (PRG) is right for successful starts only.
- HTMX: HTMX does not swap 4xx/5xx responses by default. The project convention is 422 for HTMX validation errors (CLAUDE.md). For an HTMX-initiated start refused at the click, return the refusal partial with 422 (or configure `htmx:beforeSwap` to swap that status), so that the button is replaced in place with the fresh reason and time. Non-HTMX requests get the full page with the chosen status. Distinguish with `request.htmx`.
- Server-side tests assert both the status and the reason enum, and that no `CourseFormAttempt` row was created.

## 7. Timezone display of "opens at"

- Store and compare UTC. Display in the learner's timezone, in a form that is unambiguous: Django `USE_TZ=True` and `{% load tz %}` with `timezone.localtime` / the active timezone, set per user or per site. (Django: https://docs.djangoproject.com/en/stable/topics/i18n/timezones/)
- A SA-only deployment means a single zone (SAST, UTC+2, no DST) would be simple, but the code should still use the project's configured timezone and not hardcode it. Check how the project activates the timezone before choosing; if no per-user zone exists, use the site `TIME_ZONE` and show the zone abbreviation or offset beside the time ("14:30 SAST").
- Show the date as well when the opening time is not today (a 2.5-hour wait can cross midnight): "tomorrow at 00:10" or "Fri 27 Nov, 00:10". Relative text ("in 40 minutes") goes next to it, rendered server-side. Use the `<time datetime="2026-11-26T12:30:00Z">` element with the local text inside, so the markup is machine-readable. A client script may reformat in the browser zone, but then it can disagree with the server text. Prefer a single source: the server-rendered local time, with no client reformat, unless the project already localises in the browser.
- The relative text goes stale on a page that stays open. The countdown (section 3) or an HTMX re-poll covers that. Say "about" for minutes and round up.

## 8. Edge cases the spec should state

- Boundary: opens exactly at `completed_time + wait`; a click at that instant is allowed.
- Passed learner: refuse new attempts (user decision). Say the check reads the latest completed attempt.
- Open attempt reuse is never blocked; stale ones are completed first, and then they count (as the idea says), which may itself start a wait or use the last attempt. Say so in the wording, since a learner can lose an attempt "silently" to expiry.
- Cap and waits both apply: when the last attempt has failed, show "locked", not a wait.
- Wait list of one entry means a constant wait. Entries must be positive whole minutes (user decision); reject zero, negative, float and booleans in the schema (note `bool` is an `int` in Python, so validate explicitly).
- Staff and preview use must not consume attempts or be blocked, if the preview path calls `start_attempt`. Check.

## Sources

- https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-for-update
- https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS
- https://docs.djangoproject.com/en/stable/topics/i18n/timezones/
- https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html
- https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html
- https://www.w3.org/TR/wai-aria-1.2/#timer
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/timer
- https://developer.mozilla.org/en-US/docs/Web/API/Performance/now
- https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
- https://www.rfc-editor.org/rfc/rfc6585#section-4
- https://www.rfc-editor.org/rfc/rfc9110#section-10.2.3
- https://www.rfc-editor.org/rfc/rfc9110#section-15.5.10
- https://www.nngroup.com/articles/error-message-guidelines/

Note: only the WCAG 2.2.1 page was returned by a live search in this run. The other URLs are standard reference pages cited from knowledge and were not re-fetched; the ARIA `timer` implicit `aria-live="off"` claim should be verified against the WAI-ARIA spec before the spec relies on it.

status: ok
