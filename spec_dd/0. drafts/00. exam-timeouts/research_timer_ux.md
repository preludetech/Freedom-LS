# Research: Timer UX for Timed Forms (MVP)

Scope: what the student sees and feels when completing a form with a maximum time limit. Covers pre-start, in-progress countdown, warnings, auto-submit, accessibility, mobile, and reload behaviour. Excludes proctoring, question randomisation, and retake policy (sibling ideas).

---

## 1. Pre-start screen

**Consensus pattern across Canvas, Moodle, Blackboard, Udemy:** the student lands on a dedicated "quiz info" / "launch" page *before* the timer starts. The timer begins only after an explicit action (e.g. "Start attempt" / "Begin quiz").

Things the pre-start screen should surface prominently:

- **Time limit** ("You will have 45 minutes to complete this quiz") — rendered as a bold, standalone line, not buried in a paragraph.
- **What starts the clock** — make it unambiguous: "The timer starts when you click Start. Once started, it cannot be paused."
- **What happens when time runs out** — "When time runs out, your answers will be submitted automatically." Moodle and UVA Collab explicitly recommend stating this in the quiz description; it is the single most-recommended mitigation for unfair-feeling timeouts.
- **Number of questions / sections** — so students can pace.
- **Whether they can navigate back** / review (relevant even without randomisation).
- **Accommodations note** — if a per-student extension is active, confirm the *effective* time limit ("Your time limit is 60 minutes, including your approved extension"). Do this without naming the accommodation reason, for privacy (NCSU DRO guidance).

**Start pattern:** a single primary CTA ("Start"). Do not auto-start on page load; this is a common complaint and breaks WCAG 2.2.1 user-control expectations. Once started, the first question should render immediately so the student doesn't burn seconds on another intermediate page.

**Delay / resume-later:** out of scope for MVP. Moodle supports it via `quizaccess_delayed`, but for MVP the rule "click to start, commits the attempt" is simpler and matches what most students expect from Canvas/Coursera.

---

## 2. Countdown display

### Position

- **Canvas:** top-right of the quiz sidebar; drops to the bottom on narrow windows — students report losing it when they scroll, which is a known usability regression. Avoid this.
- **Moodle:** fixed block, typically top-right, persistent while scrolling.
- **Blackboard Ultra:** has moved *away* from a persistent visible timer and toward dismissible notification pills at thresholds, citing anxiety feedback.
- **Canvas New Quizzes:** now offers a student-side hide/show toggle on the timer, explicitly to reduce anxiety.

**Recommendation for FLS MVP:** sticky element in the page header or top-right corner that stays visible on scroll, on both desktop and mobile. Never let it fall off-screen. Provide a hide/show toggle (the timer keeps running server-side either way — see §9).

### Format

- `MM:SS` for limits under 1 hour; `HH:MM:SS` for longer. Numeric is more precise than relative strings ("15 min left") and is what every major LMS uses. Relative phrasings are fine as *supplementary* screen-reader announcements but not as the primary visual.
- Use a **fixed-width / tabular-nums** font so the digits don't jitter every second (Chris Kiess, Prototypr — "Expressing Time in UI").
- Label it: `Time remaining` (not just a bare number) so first-time users know what they're looking at.

### Colour-coded thresholds

Common pattern across exam timer tools (ExamClock, VisualTimer, Online Stopwatch, Quiz & Survey Master):

- **Green / neutral** — default.
- **Yellow / amber** — at ~20% remaining, or a fixed 5 minutes for short quizzes.
- **Red** — at ~5% remaining, or fixed 1 minute; often combined with a subtle pulse.

Do **not** rely on colour alone (WCAG 1.4.1). Pair each colour change with an icon or text change ("5 minutes left").

### Should it be dismissable?

Yes — hide/show, but not permanently dismissable. Anxiety research (Brain Balance, Dr Emily King, Time Timer) shows a significant minority of students (ADHD, autism, test-anxiety) perform worse with a constantly visible countdown, while others perform worse *without* one. The student should choose. The server-side enforcement is what matters; the display is just a courtesy.

---

## 3. Warning thresholds that help pacing

Synthesising Blackboard, Canvas, Moodle, and generic exam-timer conventions:

| Threshold | Signal | Rationale |
|---|---|---|
| 50% elapsed (only for ≥1h quizzes) | Toast / aria-live polite | Halfway nudge; Blackboard Ultra default. |
| 5 minutes remaining | Toast + colour change to amber | Fixed absolute warning, works for any quiz ≥10 min. |
| 1 minute remaining | Toast + colour change to red | Final pacing cue. |
| 10 seconds remaining | Banner: "Submitting in 10 seconds" | Canvas pattern; gives time to type one last answer. |
| 0:00 | Auto-submit | See §8. |

Skip 30-second / 15-second pings — they stack on top of the 10-second banner and just create noise.

**Toasts should auto-dismiss** after ~20 seconds (Blackboard Ultra uses 20s) and be manually dismissable. They should never block the form.

**Audio:** do not play sound by default. Browsers will often block autoplay anyway, and a sudden alert sound is a documented anxiety trigger. Offer it as an opt-in preference if at all; for MVP, skip entirely.

---

## 4. Accessibility

### WCAG 2.2.1 (Timing Adjustable, Level A)

The criterion requires that users can turn off, adjust, or extend a time limit, **except** when the time limit is *essential* to the activity. A graded exam/quiz is the canonical example of the Essential Exception — W3C, Pearson Accessibility, NYU, and Silktide all cite this explicitly. So a fixed timer on a graded form is compliant *provided*:

- Per-student extensions (accommodations) are available as an administrative override.
- The time limit is communicated *before* the user encounters it (pre-start screen).
- Warnings are provided before expiry.

For forms that are *not* graded (practice, surveys) the Essential Exception does **not** apply — WCAG then requires adjust/turn-off. MVP should gate the timer feature to assessed forms only, or allow educators to mark a form as "timer essential".

### Screen reader support

- Wrap the visible countdown in `role="timer"` with `aria-live="off"` by default. The timer role's default is `off` precisely because per-second announcements would be unusable (MDN).
- Use `aria-atomic="true"` on the container so that when it *is* announced, the whole string is read.
- At warning thresholds (5 min, 1 min, 10s), swap in `role="alert"` with `aria-live="assertive"` briefly to force an announcement, then revert. Paul Adam's ARIA Countdown demo and the Enable Project both use this pattern.
- Announcement cadence when the student has *requested* spoken updates (opt-in): every 5 minutes until the last 5 min, then every minute, then every 10 seconds in the final minute. Avoid 1-second announcements.
- The pre-start screen's time limit should be inside the main heading region and read naturally; don't stuff it into an aria-label only.

### Cognitive / attention disabilities

- Hide/show toggle on the timer (covered above).
- Warnings in plain language: "5 minutes left" not "T-5:00".
- Consistent placement — don't move the timer around as the student navigates questions.
- Avoid modals that steal focus on threshold warnings; use non-blocking toasts.
- Never flash (WCAG 2.3.1). Pulsing is fine if under 3 Hz.

### Reduced-motion

Honour `prefers-reduced-motion` — disable any pulse animation on the red countdown.

---

## 5. Extended-time accommodations

Every major LMS implements this as a **per-student override on the specific form**, not a user-profile flag. Canvas "Moderate Quiz", Moodle "User override", Blackboard "Test Exception".

Requirements:

- Override stores the effective limit (e.g. 90 min instead of 60), not a multiplier — instructors often disagree about whether 1.5x rounds up or down.
- Override is visible to the *educator* but the student only sees their own effective limit — no banner saying "you have an accommodation" (privacy, per NCSU Disability Resources).
- Override is per-attempt, not global; if the form is re-used in another cohort, the override shouldn't leak.
- Common multipliers to support via UI presets: 1.5x, 2x, unlimited. ADA/ADA.gov guidance is that these are standard, but the instructor must be able to set any arbitrary value because accommodation letters vary.

MVP can ship with a single "effective time limit per student per form" table. 1.5x/2x presets are a nice-to-have on the educator side; not a student-facing concern.

---

## 6. Mobile

Known hazards:

- **Backgrounded tabs:** Chrome throttles JS timers to once per minute after 5 min inactive (NinjaOne). iOS Safari is more aggressive. A client-only countdown will drift badly.
  - **Mitigation:** enforce the deadline **server-side**. Compute `deadline_at` on start, compare against server time on submit. The client countdown is purely a display; on focus/visibility change, re-sync from the server.
- **Small screens:** a 45×45 px countdown in the top-right is too cramped. Use the full header bar width on mobile, with the timer left-aligned next to the form title. Ensure it never overlaps question text.
- **Push notifications / backgrounding:** Albert, Blackboard, and QSM all explicitly warn students that the timer *continues* to run when the browser is closed or backgrounded. This expectation needs to be communicated on the pre-start screen ("the timer keeps running even if you close this tab"). This is both correct behaviour and a trust-building disclosure.
- **Touch targets:** the hide/show toggle must be at least 44×44 px (WCAG 2.5.5 AAA, and iOS HIG).
- **Safe area insets:** on notched iPhones, the sticky timer needs `env(safe-area-inset-top)` padding.

---

## 7. Common user complaints (LMS forums / reviews)

Recurring themes from Canvas Community, Moodle.org forums, and Blackboard help threads:

1. **"The timer disappeared when I scrolled."** — Canvas at narrow widths. Fix: sticky positioning, viewport-independent.
2. **"It auto-submitted while I was typing my last answer."** — no grace period, no 10-second warning. Fix: explicit 10-second banner + a ~60-second server-side grace window for in-flight submissions.
3. **"My internet blipped and I lost 5 minutes of my exam time."** — timer is absolute wall-clock, not "time actively engaged". This is actually industry standard (Canvas, Moodle, Blackboard all do it) and students need to be *told* this on the pre-start screen. Don't try to build pause-on-disconnect for MVP; the complaint is expectation mismatch, not a wrong design.
4. **"The clock was fast/slow / didn't match the server."** — Moodle bug where client-side clock drift caused discrepancies. Fix: always authoritative server-side, client re-syncs on focus.
5. **"I was marked late by 2 seconds because of server lag."** — Moodle's `graceperiodmin` (default 60s) explicitly accepts submissions for up to a minute after expiry to avoid penalising students for server-side delay. Worth replicating.
6. **"I didn't know there was a time limit until it started."** — missing or buried pre-start screen.
7. **"The timer kept making me anxious; I couldn't focus."** — driver of Canvas New Quizzes' hide toggle and Blackboard Ultra's notification-only mode.
8. **"My accommodation wasn't applied and I ran out of time."** — override applied to wrong attempt, or applied globally but not to the specific quiz. Make the educator-facing override UI show the *student's effective time* prominently.

---

## 8. Auto-submit UX

When the timer hits zero:

- **Do not show a confirmation modal.** At this point the student has no input to give; a modal just wastes the few seconds before actual submission. Canvas and Moodle both submit without confirmation.
- **Save-as-you-go.** Each question answer should post to the server as soon as it's entered (or on blur). This is already standard in Canvas New Quizzes and Moodle. The timeout submission then just closes out the attempt with whatever is on the server. For FLS, HTMX partials on each field blur are the natural fit.
- **Server-side grace window:** accept form submits for ~60 seconds after `deadline_at`. Covers network lag and in-flight POSTs. Moodle default is 60s; use the same.
- **Last-10-seconds banner:** persistent banner "Submitting in 10 seconds" so the student knows what's happening and can type one final character.
- **Post-submit screen:** be clear about what was submitted and what was skipped. Show:
  - Confirmation that the attempt closed due to timeout (not explicit submit).
  - Which questions had answers recorded (count, not full review — review is a separate concern).
  - Next step (return to course, see results when published).
- **Do not discard answers** on timeout. This is the single most damaging pattern (Moodle forum complaints). "Overdue handling = autosubmit" is the correct default.

---

## 9. Page reload / navigate-away mid-form

**Student mental model (from forum complaints):** "the timer should pause if I lose connection or reload." This is *not* how any major LMS works, and it is the single biggest expectation gap.

**Industry-standard behaviour (Canvas, Moodle, Blackboard, Udemy, Coursera):**

- Timer is **wall-clock** from the moment Start was clicked — a `deadline_at` timestamp stored server-side.
- Reload / close tab / sign out / navigate away does **not** pause it.
- On return, the student resumes the attempt with whatever time is left against `deadline_at`.
- The client countdown always re-computes from `deadline_at - server_now` on load, so a reload can't gain or lose time.

**Implementation implications:**

- Persist `attempt.started_at` and `attempt.deadline_at` on start.
- Do not trust any client-sent remaining-time value on submit — always validate against `deadline_at` + grace period server-side.
- On each page load of an in-progress attempt, send `server_time` and `deadline_at` to the client; the countdown recomputes locally but is visual only.
- A background sync / heartbeat every 30–60s re-syncs the displayed timer against the server, correcting any drift (especially after a backgrounded mobile tab).

**Communicate it:** pre-start screen must say "The timer runs continuously once started. Closing or reloading the page will not pause it."

A background auto-save of answers (per §8) makes reloads non-destructive for the student's work, which mitigates most of the complaint volume even without pausing.

---

## 10. Reference implementations — quick comparison

| Platform | Pre-start | Timer position | Hide option | Warnings | Auto-submit | Grace period |
|---|---|---|---|---|---|---|
| Canvas Classic | Yes (launch page) | Top-right, drops to bottom on narrow | No | 30min, 5min, 1min, 30s, 10s (variable) | Yes | Short, implicit |
| Canvas New Quizzes | Yes | Top-right | **Yes (toggle)** | Threshold toasts | Yes | Short |
| Moodle | Yes | Fixed block, top-right | No | Configurable | Yes | **`graceperiodmin` = 60s default** |
| Blackboard Original | Yes | Always visible | No | 50%, 30s increments | Yes | No |
| Blackboard Ultra | Yes | **Notifications only** (no persistent timer) | N/A | 50% (long), 10% remaining, auto-dismiss 20s | Yes | Yes |
| Google Forms | No (third-party only) | Add-on dependent | Varies | Varies | Varies | Usually none |
| Coursera | Yes | Top of quiz | No | Minimal | Yes | Short |
| Udemy Practice Tests | Yes | Top of test | No | End-of-time alert | Soft (lets you continue past time, flags as over) | N/A |
| Khan Academy | Yes (for timed practice only) | Header | N/A | Minimal | Yes | N/A |
| Typeform timed | Yes | Top bar | No | Colour change near end | Yes | None documented |

---

## 11. MVP recommendations (tl;dr)

1. **Pre-start screen** with: time limit, number of questions, "timer runs continuously once started, reloading won't pause it", "answers auto-submit when time runs out", single "Start" CTA.
2. **Server-side `deadline_at`** stored on attempt start. Client countdown is display-only; always recomputed from `deadline_at - server_now` on page load.
3. **Sticky countdown** in top-right (desktop) / header bar (mobile), `MM:SS` format, tabular-nums, with `role="timer" aria-live="off" aria-atomic="true"`.
4. **Hide/show toggle** on the countdown (server-side clock keeps running regardless).
5. **Warnings** at 5 min (amber + polite aria-live toast), 1 min (red + toast), 10s (persistent banner "Submitting in 10 seconds" with `role="alert"`).
6. **No default audio.**
7. **Answer autosave** on blur / on field change so timeout never loses work.
8. **Auto-submit at expiry**, no confirmation modal, with **60-second server-side grace window** for in-flight submits.
9. **Per-student effective-time override** on each form (absolute minutes, not multiplier). Student never sees that an override was applied; only sees their own effective limit.
10. **Visibility-change resync** on mobile: when the tab becomes visible again, re-fetch `server_now` and recompute remaining.
11. **Scope timer to assessed forms** (WCAG 2.2.1 Essential Exception). For non-assessed forms, either no timer or treat limit as soft/advisory.

---

## Sources

### WCAG / Accessibility
- [W3C — Understanding SC 2.2.1 Timing Adjustable](https://www.w3.org/WAI/WCAG21/Understanding/timing-adjustable)
- [Pearson Accessibility — Timing Adjustable (SC 2.2.1, Level A)](https://accessibility.pearson.com/guidelines/accessibility-guidance-for-assessment/level-a/timing-adjustable/)
- [NYU Digital Accessibility — 2.2.1 Timing Adjustable](https://digitalaccessibility.nyu.edu/testing/sc221.html)
- [Silktide — WCAG 2.2.1 Timing Adjustable](https://silktide.com/accessibility-guide/the-wcag-standard/2-2/enough-time/2-2-1-timing-adjustable/)
- [MDN — ARIA timer role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/timer_role)
- [MDN — ARIA live regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions)
- [Paul Adam — ARIA Countdown Timer demo](https://pauljadam.com/demos/ariacountdown.html)
- [The Enable Project — ARIA Timer walkthrough](https://useragentman.com/enable/timer.php)
- [BATI-ITAO — ARIA live regions and time limits](https://bati-itao.github.io/learning/esdc-self-paced-web-accessibility-course/module11/aria-live.html)

### LMS reference implementations
- [Canvas — Quiz Behavior for Timed Quizzes (UCSD)](https://extensionhelpcenter.ucsd.edu/hc/en-us/articles/30245159641613-Canvas-Quiz-Behavior-for-Timed-Quizzes)
- [Canvas Community — New Quizzes Toggle Timer Visibility idea](https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-Toggle-Timer-Visibility/idi-p/625707)
- [Canvas Community — Time Warnings on Quizzes discussion](https://community.canvaslms.com/t5/Canvas-Question-Forum/Time-Warnings-on-Quizzes/td-p/241015)
- [Moodle Docs — Quiz settings](https://docs.moodle.org/501/en/Quiz_settings)
- [Moodle Docs — Better handling of overdue quiz attempts](https://docs.moodle.org/dev/Better_handling_of_overdue_quiz_attempts)
- [Moodle Docs — Quiz Time Limit](https://docs.moodle.org/501/en/Quiz_Time_Limit)
- [Moodle Plugin — quizaccess_delayed (delayed attempts)](https://moodle.org/plugins/quizaccess_delayed)
- [Blackboard Help — Test Timer Notifications (3900.48)](https://help.blackboard.com/node/43976)
- [Blackboard Help — Timed assessments](https://help.blackboard.com/node/19846)
- [Drexel LeBow — Recommended Settings for Blackboard Exams](https://www.lebow.drexel.edu/about/support-services/knowledge-base/recommended-settings-blackboard-exams)
- [QMplus — What happens when quiz time expires](https://www.qmul.ac.uk/technology-enhanced-learning-team/telt-magazine/items/qmplus-quizzes---what-happens-when-the-time-expires.html)
- [UWaterloo — Changes to Time Limit options and Auto-Submit](https://uwaterloo.atlassian.net/wiki/spaces/ISTKB/pages/43600249905/Changes+to+Time+Limit+options+and+Auto-Submit)
- [UVA Collab — How Automatic Submission works](https://collab-help.its.virginia.edu/m/assessments/l/694855-how-does-automatic-submission-work-in-tests-quizzes)
- [Albert — How timed assignments work](https://help.albert.io/en/articles/1885063-how-do-timed-assignments-work)
- [Udemy — Practice Tests FAQ](https://support.udemy.com/hc/en-us/articles/231954647-Practice-Tests-Frequently-Asked-Questions)
- [Coursera — Troubleshoot quizzes & assignments](https://www.coursera.support/s/article/209818783-Troubleshoot-quizzes-assignments?language=en_US)
- [Google Forms + AutoProctor timer integration](https://www.autoproctor.co/add-timer-proctor-google-forms/)
- [Extended Forms — Time limits on Google Forms](https://extendedforms.io/blog/time-limit-in-google-form-quiz)

### Accommodations / ADA
- [ADA.gov — Testing Accommodations](https://www.ada.gov/resources/testing-accommodations/)
- [JAN — Extended Time](https://askjan.org/concerns/Extended-Time.cfm)
- [JAN — Testing Accommodations](https://askjan.org/topics/test.cfm)
- [NCSU DRO — Extended Time on Tests and Quizzes](https://dro.equalopportunity.ncsu.edu/accommodations/accommodation-descriptions-and-procedures/extended-time-on-in-class-assignments-tests-and-quizzes/)
- [CUHK EdTech — Extending time for a student in a Blackboard Test](https://cuhk-edt.knowledgeowl.com/docs/extending-time-for-a-student-in-a-blackboard-test)
- [Hood College — Timed Test / Test Exceptions (PDF)](https://www.hood.edu/sites/default/files/CAAR/Timed%20Test-Hood.pdf)

### Timer UX / anxiety / design
- [Chris Kiess — Expressing Time in UI & UX Design (Prototypr)](https://blog.prototypr.io/expressing-time-in-ui-ux-design-5-rules-and-a-few-other-things-eda5531a41a7)
- [Brain Balance — Visual Timers for Test Taking: Friend or Foe?](https://www.brainbalancecenters.com/blog/visual-timers-for-test-taking-friend-or-foe)
- [Dr Emily King — But Timers Make My Kid Anxious](https://learnwithdremily.substack.com/p/but-timers-make-my-kid-anxious)
- [Time Timer — Visual vs Digital Timers](https://www.timetimer.com/blogs/news/visual-timers-vs-digital-timers-why-seeing-time-matters)
- [Time Timer — IEP, 504, and Workplace Accommodations](https://www.timetimer.com/blogs/news/visual-timers-for-iep-504-and-workplace-accommodations)
- [Cañada College — Test Anxiety Tips](https://canadacollege.edu/disabilityresourcecenter/test-anxiety-tips.php)

### Mobile / browser behaviour
- [NinjaOne — Configure Chrome Background Tab Throttling](https://www.ninjaone.com/blog/configure-background-tab-throttling-chrome/)
- [Quiz and Survey Master — Advanced Timer docs](https://quizandsurveymaster.com/docs/add-ons/advanced-timer/)
