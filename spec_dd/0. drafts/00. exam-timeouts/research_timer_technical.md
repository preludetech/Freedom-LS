# Research: Server-Authoritative Exam Timer — Technical Implementation

Audience: engineer turning this into a Django spec for FLS (Django 6 / HTMX 2 / Alpine.js / PostgreSQL).

Scope: the mechanics. UX polish (warning banners, colour changes, toast at T-5min, accessibility of the timer) is in a sibling doc.

---

## 1. Core principle: the server owns the deadline

Client-side timers alone are insecure. A student can:

- Change their OS clock.
- Open devtools and `clearInterval(...)` every timer in the page.
- Disable JS entirely.
- Close the tab, come back later, and expect the timer to "pause".
- Edit the DOM to show `99:99` indefinitely.

Therefore the authoritative state lives server-side. The client timer is a **display convenience** and a "nice path" auto-submit trigger, nothing more. The server MUST:

1. Record `started_at` on the attempt.
2. Know the attempt's `time_limit_seconds`.
3. Reject any answer submissions after `started_at + time_limit` (plus grace period, see §6).
4. Be able to finalise an abandoned attempt even if the student never comes back.

This is how Moodle, Canvas, and Open edX all work. From Moodle's quiz dev docs: "client-side JavaScript implementation... won't really be secure unless you also check the timings server-side" (<https://docs.moodle.org/dev/Better_handling_of_overdue_quiz_attempts>).

---

## 2. Storage: where do `started_at` and `deadline` live

**Recommendation:** extend the existing form-attempt / progress record in `freedom_ls/student_progress/`. Do not create a separate "timer" model — the timer is an intrinsic attribute of the attempt.

Fields on the attempt (names illustrative; match existing FLS conventions):

| Field | Type | Purpose |
| --- | --- | --- |
| `started_at` | `DateTimeField(null=True)` | First moment the clock started. Null until they start. |
| `time_limit_seconds` | `IntegerField(null=True)` | Snapshotted from the form at start time, NOT read live from the form config. Protects against admins changing the limit mid-attempt. |
| `deadline_at` | `DateTimeField(null=True)` | Denormalised `started_at + time_limit`. Makes queries cheap and ordering simple. Write once, never mutate. |
| `auto_submitted_at` | `DateTimeField(null=True)` | Set when the server finalises the attempt due to timeout (as opposed to the student pressing submit). Useful for reporting / audit. |
| `state` | `CharField` | See §7 state machine. |

Precedent:
- Open edX `ProctoredExamStudentAttempt` stores `started_at`, `allowed_time_limit_mins`, `completed_at`, `status`, plus `time_remaining_seconds` for resume scenarios (<https://github.com/openedx/edx-proctoring/blob/master/edx_proctoring/models.py>).
- Moodle stores `quiz_attempt.state` plus the attempt's `timestart` and computes deadlines from `quiz.timelimit` + `quiz.graceperiod`.

Snapshotting `time_limit_seconds` onto the attempt (rather than dereferencing the form config each time) matters: if an educator edits the form's time limit while a student is mid-attempt, you don't want the deadline to shift under them. Canvas has had bugs here (<https://github.com/instructure/canvas-lms/issues/1769>).

---

## 3. When does the clock start?

Three candidate triggers:

| Trigger | Pros | Cons |
| --- | --- | --- |
| First GET of any form page | Zero-click UX. | Student accidentally clicks the link to preview — clock starts. Ambiguous if they navigate away. |
| First answer submitted | Feels fair. | Student has already seen all questions before the clock started. Defeats the purpose of a time limit. |
| Explicit "Start" click | Unambiguous, consentful, audit-friendly. Industry standard (Moodle, Canvas, edX all use this). | One extra click. |

**Recommendation:** explicit "Start exam" button that POSTs to a dedicated endpoint. That POST is the one and only place where `started_at`, `time_limit_seconds`, and `deadline_at` are written. Use `F()` expressions or `select_for_update()` inside a transaction so a double-click cannot start the clock twice.

Pseudocode:

```python
with transaction.atomic():
    attempt = Attempt.objects.select_for_update().get(id=attempt_id)
    if attempt.started_at is not None:
        # Idempotent: already started, just redirect to the form.
        return redirect(...)
    now = timezone.now()
    attempt.started_at = now
    attempt.time_limit_seconds = form.time_limit_seconds
    attempt.deadline_at = now + timedelta(seconds=form.time_limit_seconds)
    attempt.state = "in_progress"
    attempt.save()
```

Starting is a one-way door. A second GET or POST to the start endpoint after `started_at` is set is a no-op redirect into the form.

---

## 4. Handling page reload and multi-page navigation

The deadline lives on the attempt record, not in the page. On every render of any form page for this attempt:

1. Load the attempt.
2. Compute `seconds_remaining = (deadline_at - now).total_seconds()`.
3. If `seconds_remaining <= 0`: do not render the form, finalise (see §7) and redirect to a summary/review page.
4. Otherwise render the form and pass `seconds_remaining` to the template.

The client does not persist the timer in `localStorage`. Every navigation re-reads `seconds_remaining` from the server. This means reloads, cross-page navigation, opening the form in a second tab, and reconnects all converge on the same truth.

---

## 5. Clock-skew-safe client countdown

Do NOT send an absolute wall-clock timestamp (`deadline_at` as ISO) and have the client compute `deadline - Date.now()`. `Date.now()` reads the user's OS clock; if it's wrong, the timer is wrong. (And a malicious user can set it to anything.)

**Pattern:**

1. Server sends `seconds_remaining: int` (integer, from its own `timezone.now()`).
2. Client records `t0 = performance.now()` at page load.
3. Each tick: `displayed = Math.max(0, seconds_remaining - (performance.now() - t0) / 1000)`.

`performance.now()` is a monotonic clock, unaffected by NTP adjustments or user tampering (<https://developer.mozilla.org/en-US/docs/Web/API/Performance/now>, <https://dev.to/brinobruno/javascript-countdown-gotcha-why-datenow-depends-on-the-users-clock-2gl9>).

Network latency between server computing `seconds_remaining` and client receiving it is small (tens to hundreds of ms) and favours the student. Ignore it. Do not try to correct for it — it's not worth the complexity.

---

## 6. Handling network disconnection

Scenario: student loses wifi mid-answer. They keep typing locally. Wifi comes back and they try to submit.

Options:

- **Hard cutoff** — server rejects submission if `now > deadline_at`. Simple. Students lose their last answer if they were disconnected when the clock ran out.
- **Grace period** — server accepts submission up to `deadline_at + grace_seconds` (Moodle default: 60s, admin-tunable via `quiz | graceperiodmin`). Answers submitted in the grace window are saved but no further answers may be added after the original deadline. Balance: forgiving of real-world network blips without letting students "buy" extra thinking time.

**Recommendation:** configurable grace period per form (default ~60s), applied server-side. Document that partial answers saved before the deadline are always preserved — it's only the final submission that has this tolerance.

Combine with **per-page autosave**: when the student navigates from page N to page N+1 of a multi-page form, save page N's answers server-side. That way if they disconnect on page 3, pages 1 and 2 are already banked. Moodle follows this pattern explicitly: "an answer is saved when you move to the next question" (<https://docs.moodle.org/501/en/Quiz_Time_Limit>). Canvas autosaves every ~15s; Moodle autosaves open pages once a minute (<https://moodle.org/mod/forum/discuss.php?d=262872>).

For FLS a conservative rule: save on page navigation (natural boundary, no extra engineering) and skip finer-grained autosave in v1 unless the forms are very long.

---

## 7. Server-side finalisation: how does the attempt actually get closed?

Two layers are needed. Neither is sufficient alone.

### Layer A: client-triggered submit at zero

When the countdown hits zero in the browser, JS fires the form's submit. This is the happy path. Student is present, tab is open, network is up — their current answers post through the normal submission endpoint. Same view, same validation, same templates.

### Layer B: server-side finalisation for abandoned attempts

Student closed the tab. Laptop died. Browser crashed. The clock ran out 3 hours ago. Layer A never fired. The attempt is sitting in `in_progress` state with `deadline_at` in the past.

Three implementation options:

| Option | Pros | Cons |
| --- | --- | --- |
| **(1) Celery Beat scheduled task** every N seconds: `Attempt.objects.filter(state="in_progress", deadline_at__lt=now-grace).update(...)` | Attempt is finalised promptly regardless of student activity. Clean separation. Report/grade pipelines fire deterministically. | Requires Celery + beat infrastructure. |
| **(2) Lazy finalisation on next request** — whenever anyone touches that attempt (student, educator dashboard), check if it's expired and finalise if so. | No extra infra. Dead simple. Canvas actually does this: "Canvas realizes there is an in-progress quiz that the timer has expired for and submits it when the student logs in, rather than immediately when the timer expires" (<https://community.canvaslms.com/t5/Canvas-Question-Forum/Timed-Quiz-Did-Not-Auto-Submit-for-a-Student/m-p/418126>). | Attempts that are never looked at again stay in `in_progress` forever, polluting queries and reports. Educator dashboards may show stale state. |
| **(3) Django management command** run via system cron (`manage.py close_overdue_attempts`) | No Celery needed. Django-native. Matches Moodle's approach (`quiz_cron`). | Cron granularity (usually 1-5 min) means slight lag before finalisation. Still needs infra. |

**Recommendation for FLS:** hybrid of (2) + (3). Do lazy finalisation on every read/write touch of an attempt (a single helper function `finalise_if_expired(attempt)` called at the top of every view that loads an attempt, including educator views). Additionally, ship a management command `close_overdue_attempts` that educators/ops can run via cron to sweep up truly abandoned attempts. Celery is overkill for v1 and FLS doesn't currently require it.

Moodle does the same pattern: cron closes overdue attempts, but `processattempt.php` also actively detects state transitions on every student request (<https://docs.moodle.org/dev/Better_handling_of_overdue_quiz_attempts>).

### Finalisation logic

```python
def finalise_if_expired(attempt):
    if attempt.state != "in_progress":
        return attempt
    if timezone.now() <= attempt.deadline_at + GRACE:
        return attempt
    with transaction.atomic():
        locked = Attempt.objects.select_for_update().get(pk=attempt.pk)
        if locked.state != "in_progress":
            return locked
        locked.state = "submitted"
        locked.auto_submitted_at = timezone.now()
        locked.save()
        # Trigger the exact same grading / scoring pathway the normal
        # submit button uses. Reuse, don't fork.
        score_attempt(locked)
        return locked
```

### Attempt state machine

Borrowing from Moodle (<https://docs.moodle.org/dev/States_of_a_quiz_attempt>), minimal states for FLS:

- `not_started` — record exists (e.g. auto-created on enrolment) but student has not clicked Start.
- `in_progress` — `started_at` is set, clock is running.
- `submitted` — final. Reached either by student submitting or by server auto-finalisation.

Add a separate `auto_submitted_at` timestamp so reports can distinguish "student finished in time" from "we had to close it for them". Moodle models this with a distinct "overdue" intermediate state for the grace-period case — overkill for v1.

---

## 8. Server-side submission guard

Every submission endpoint (per-page save, final submit) does this at the top:

```python
if timezone.now() > attempt.deadline_at + GRACE:
    finalise_if_expired(attempt)
    return HttpResponse(status=422, ...)  # HTMX validation convention
```

This is the single hard line. Even if a student bypasses the client timer, devtools the DOM, replays the request with curl, or uses a delay attack, the server will not write answers after `deadline + grace`.

Preventing the "start, close tab, come back tomorrow for more time" attack falls out of this for free: the deadline is absolute, pinned to `started_at` which was recorded server-side.

---

## 9. HTMX + Alpine wiring for the client timer

Two viable patterns. Pick one and stick with it.

### Pattern A: Alpine manages state, dispatches a custom event, HTMX listens

```html
<div
  x-data="examTimer({{ seconds_remaining }})"
  x-init="init()"
  @timer-expired.window="$el.closest('form').requestSubmit()"
>
  <span x-text="formatted"></span>
</div>
```

```js
function examTimer(secondsRemaining) {
  return {
    secondsRemaining,
    t0: null,
    formatted: '',
    init() {
      this.t0 = performance.now();
      this.tick();
      setInterval(() => this.tick(), 1000);
    },
    tick() {
      const elapsed = (performance.now() - this.t0) / 1000;
      const remaining = Math.max(0, this.secondsRemaining - elapsed);
      this.formatted = formatMMSS(remaining);
      if (remaining <= 0) {
        window.dispatchEvent(new CustomEvent('timer-expired'));
      }
    },
  };
}
```

The form itself is already an HTMX form (`hx-post`, `hx-target`, etc). When `requestSubmit()` fires, HTMX picks it up and submits normally — no special-case code path.

### Pattern B: HTMX `hx-trigger` on a custom event

```html
<form hx-post="..." hx-trigger="submit, timer-expired from:body">
```

Dispatch the event via the htmx API (not a raw DOM event, which HTMX's listener does not pick up consistently — see <https://github.com/bigskysoftware/htmx/discussions/692>):

```js
htmx.trigger('body', 'timer-expired');
```

Tradeoff: Pattern A keeps the "expired" logic inside Alpine and uses a native form submit, so it works identically whether the form is HTMX-enhanced or not. Pattern B ties auto-submit to HTMX specifically. **Recommended: Pattern A** — it's closer to how Moodle's `timer.js` works (it calls the form's submit directly) and it's decoupled from HTMX internals.

Relevant docs:
- <https://htmx.org/attributes/hx-trigger/>
- <https://alpinejs.dev/directives/data>

---

## 10. Background tab throttling

`setInterval` is throttled to at most 1Hz in background/hidden tabs, and to ~1 per minute after 5+ minutes hidden with heavy chained timers (<https://developer.chrome.com/blog/timer-throttling-in-chrome-88>, <https://pontistechnology.com/learn-why-setinterval-javascript-breaks-when-throttled/>).

For an exam timer this is **mostly fine**:

- Display drift in a hidden tab is invisible — the student isn't looking at it.
- On tab refocus, the next tick catches up (because we compute `remaining` from `performance.now()` deltas, not by decrementing a counter each interval).
- When the tab is hidden at the moment of expiry, client auto-submit may fire late. That's what Layer B (server finalisation) is for.

`performance.now()` itself continues to advance in hidden tabs on modern browsers (<https://github.com/w3c/hr-time/issues/65>), so the delta-based display stays correct as soon as the next tick fires.

**Optional v2 enhancement:** run the timer in a Web Worker, which is not throttled the same way (<https://hackwild.com/article/web-worker-timers/>). This gives a precise countdown even in a background tab, at the cost of extra complexity. Not recommended for v1 — Layer B already covers the correctness gap.

**Document explicitly** for QA: "a backgrounded tab may briefly show stale time on refocus; this is cosmetic. Submissions past the deadline are rejected server-side regardless."

---

## 11. What about students with JS disabled?

- The page should render normally. Show the deadline (as a fixed wall-clock time, e.g. "Submit by 14:32") rather than a live countdown.
- Layer B (server finalisation) means their attempt closes on time regardless.
- Their final submission before the deadline still works — it's just a plain form POST.
- Do not block the exam on JS. Moodle historically made JS mandatory for timed quizzes; this is accessibility-hostile and not required if your server enforcement is correct.

---

## 12. What does NOT protect you

- Disabling the browser back button.
- `beforeunload` warnings. (Users can dismiss them. Not a security measure — at best a UX nudge.)
- Hiding the timer in devtools. (Irrelevant — the timer is display-only.)
- Checking `Date.now()` against anything. (Untrusted.)

The only real defence is §8: server refuses writes after the deadline.

---

## 13. Multi-page forms: where the timer lives in the template

The timer component should render on every form page. To keep implementation DRY, put it in a shared template partial / cotton component. The view passes `seconds_remaining` fresh on every render, so the component is stateless beyond its own Alpine state.

Consider: the timer component should be sticky (position: sticky or similar) so the student can always see it. That's a UX concern — see the sibling research doc.

---

## 14. Summary of recommended approach for FLS

1. Add `started_at`, `time_limit_seconds`, `deadline_at`, `auto_submitted_at`, `state` to the form-attempt record in `freedom_ls/student_progress/`.
2. Add a `time_limit_seconds` field to the form config in `content_engine` (nullable — no limit means no timer).
3. Explicit "Start" endpoint. Idempotent via `select_for_update`.
4. Every view that loads an attempt calls `finalise_if_expired(attempt)` first.
5. Every submission endpoint rejects writes when `now > deadline_at + grace` (return 422 per FLS HTMX convention).
6. Timer display: Alpine component, `performance.now()`-based delta, `seconds_remaining` passed from server on every render. Fires `timer-expired` event which calls `form.requestSubmit()`.
7. Per-page answer save on navigation (already the natural flow in a multi-page form).
8. Management command `close_overdue_attempts` for ops/cron to finalise truly abandoned attempts. No Celery for v1.
9. Configurable grace period, default 60s.
10. Document background-tab throttling as a known cosmetic quirk, covered by server finalisation.

---

## References

- <https://docs.moodle.org/501/en/Quiz_Time_Limit> — Moodle quiz time limit user docs.
- <https://docs.moodle.org/dev/Better_handling_of_overdue_quiz_attempts> — Moodle's data model, states, cron, and grace period for overdue handling.
- <https://docs.moodle.org/dev/States_of_a_quiz_attempt> — Moodle attempt state machine.
- <https://community.canvaslms.com/t5/Canvas-Question-Forum/Timed-Quiz-Did-Not-Auto-Submit-for-a-Student/m-p/418126> — Canvas lazy finalisation behaviour (auto-submit triggered on next login).
- <https://github.com/instructure/canvas-lms/issues/1769> — Canvas bug showing deadline precedence issues when config changes mid-attempt.
- <https://extensionhelpcenter.ucsd.edu/hc/en-us/articles/30245159641613-Canvas-Quiz-Behavior-for-Timed-Quizzes> — Canvas timed-quiz behaviour including ~15s autosave.
- <https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/manage_timed_exams.html> — Open edX timed exams overview.
- <https://github.com/openedx/edx-proctoring/blob/master/edx_proctoring/models.py> — `ProctoredExamStudentAttempt` model fields (started_at, allowed_time_limit_mins, completed_at, status, time_remaining_seconds).
- <https://github.com/openedx/edx-proctoring/blob/master/edx_proctoring/api.py> — `_check_for_attempt_timeout` server-side expiration logic.
- <https://github.com/tomwalker/django_quiz> — Reference Django quiz app; records start/end times for attempts.
- <https://developer.mozilla.org/en-US/docs/Web/API/Performance/now> — `performance.now()` monotonic clock.
- <https://dev.to/brinobruno/javascript-countdown-gotcha-why-datenow-depends-on-the-users-clock-2gl9> — Why `Date.now()` is unsafe for countdowns.
- <https://developer.chrome.com/blog/timer-throttling-in-chrome-88> — Chrome background-tab timer throttling.
- <https://pontistechnology.com/learn-why-setinterval-javascript-breaks-when-throttled/> — setInterval drift in inactive tabs.
- <https://github.com/w3c/hr-time/issues/65> — `performance.now()` behaviour in background tabs.
- <https://hackwild.com/article/web-worker-timers/> — Web Worker timers for higher accuracy in background tabs.
- <https://htmx.org/attributes/hx-trigger/> — HTMX `hx-trigger` reference.
- <https://github.com/bigskysoftware/htmx/discussions/692> — Use `htmx.trigger()` (not raw `dispatchEvent`) for reliable custom-event triggering.
- <https://moodle.org/mod/forum/discuss.php?d=262872> — Moodle autosave discussion (per-minute for open pages).
