# Form Time Limits

## Overview

Allow a form (quiz/exam) to have a maximum time limit. Before starting, the student sees the limit. While working, they see how much time is left. When time runs out, the form auto-submits through the existing submission path.

This is the MVP timer mechanic. Richer exam features (question randomisation, proctoring, retakes, proctor dashboards) live in the sibling `02. exam-proctering` idea. Building this first unblocks that work and is useful on its own for any timed form (mock test, diagnostic quiz, assessed exercise).

## Scope

- Time limit is a per-form setting, declared in the content source (same place as other form config).
- Applies to the whole attempt, not per-page.
- The server is authoritative: the deadline is pinned to a server-recorded `started_at`, and the server refuses writes after it.
- The client-side countdown is display only — a courtesy, plus a "happy path" auto-submit trigger.
- Per-student extensions (accommodations) are **out of scope** for this MVP — see "What this is NOT" and "Future work" below.

## Core capabilities

### 1. Form configuration

- Optional `time_limit_seconds` (or `time_limit_minutes`) on a `Form`. Null = untimed (current behaviour).
- Configurable `grace_period_seconds` per form, **defaulting to 60 s** (Moodle's default). Protects against network lag and in-flight POSTs; answers submitted within grace are accepted but no new answers can be started after the hard deadline. Educators can set `0` for strict-mode exams (e.g. CAA official exams) where no tolerance is acceptable.
- Settings are declared in the markdown content source and flow through the existing `content_save` pipeline — no new plumbing needed beyond the field itself.

### 2. Attempt model changes

Extend the existing `FormProgress` record in `student_progress` with:

- `started_at` — when the student clicked Start.
- `time_limit_seconds` — snapshotted from the form *at start time*, so if an educator edits the form mid-attempt the deadline doesn't move under the student.
- `deadline_at` — denormalised `started_at + time_limit_seconds`. Written once, never mutated.
- `auto_submitted_at` — set when the server finalises an attempt because time ran out (distinguishes "student finished" from "we closed it for them").
- A state field or equivalent, distinguishing not-started / in-progress / submitted.

### 3. Start flow

- Pre-start screen appears **only when the form has a time limit**. Untimed forms keep their current behaviour — no start screen, no deadline fields populated.
- On timed forms, the student lands on a **pre-start screen** showing:
  - The time limit (bold, standalone line).
  - That the timer runs continuously once started and reload will not pause it.
  - That answers auto-submit when time runs out.
  - Number of questions / pages.
- Single primary "Start" CTA.
- Start is an explicit POST to a dedicated idempotent endpoint. First call records `started_at`, `time_limit_seconds`, `deadline_at`; subsequent calls are no-op redirects into the form. Concurrency-safe via `select_for_update`.

### 4. In-progress countdown

- Sticky, always-visible timer in the page header (or top-right on desktop), following FLS UI conventions and the brand-guidelines skill.
- `MM:SS` format (or `HH:MM:SS` for limits ≥ 1 h), tabular-nums.
- Server sends `seconds_remaining: int` on every page render; client countdown uses `performance.now()` deltas (never `Date.now()`) to stay safe against clock tampering and OS clock skew.
- Student-toggleable hide/show — display only, server clock runs regardless. Anxiety-mitigation (per UX research).
- Colour cues at 5 min (amber) and 1 min (red), paired with icon/text so WCAG 1.4.1 is not violated.
- Threshold toasts at 5 min and 1 min. Persistent banner in the final 10 s: "Submitting in 10 seconds".
- ARIA: `role="timer" aria-live="off" aria-atomic="true"` by default; brief switch to `role="alert" aria-live="assertive"` at thresholds. No default audio.
- Honour `prefers-reduced-motion`.

### 5. Network / reload / multi-page behaviour

- Timer is wall-clock from start. Reload, tab close, navigate-away do not pause it — industry standard. The pre-start screen must say so explicitly.
- On every page render of an in-progress attempt, the server recomputes `seconds_remaining` fresh. No client-side persistence of the clock.
- Answers are saved on page navigation (this matches the existing page-by-page submission flow; no new autosave needed for v1).
- Visibility-change listener: on tab refocus, re-sync displayed time from last server value via `performance.now()` delta (no new fetch needed — the value on screen is computed, not decremented).

### 6. Server-side enforcement

- Every submission endpoint (per-page answer save, final submit) checks `now > deadline_at + grace` at the top and rejects (HTTP 422 per FLS HTMX convention) if so, after finalising the attempt.
- A single `finalise_if_expired(attempt)` helper is called at the top of every view that loads an attempt — student views and educator views. This closes attempts lazily on first touch after expiry (Canvas pattern).
- A management command `close_overdue_attempts` finalises abandoned attempts (clock expired, student never came back). Run via cron by ops; no Celery dependency.
- Finalisation reuses the exact grading/scoring path the normal submit button uses — do not fork.

### 7. Auto-submit at expiry

- Client: when the countdown hits zero, Alpine dispatches a `timer-expired` event which calls `form.requestSubmit()`. Plain form submit, no special path.
- Server: covered above (Layer B). Even with JS disabled, dead tabs, backgrounded mobile tabs, etc., the attempt still closes on time.
- No confirmation modal at expiry — the student has no input left to give.
- Post-timeout screen shows: confirmation that the attempt closed due to timeout, what was recorded (count, not full review), next step.

### 8. Scope of the timer feature

- Timer is intended for **assessed** forms (WCAG 2.2.1 Essential Exception). For non-assessed forms (surveys, practice), either don't set a limit or treat it as advisory — no hard enforcement.
- For v1 this is implicit (educators just don't set a limit on non-assessed forms). Explicit gating can come later if misuse becomes an issue.

## What this is NOT

- Not proctoring. No webcam, no focus-loss detection, no screen recording, no identity verification. Those live in `02. exam-proctering`.
- Not question randomisation or question pools. Sibling idea.
- Not a retake policy. Sibling idea.
- Not a "pause on disconnect" feature. Industry standard is wall-clock absolute, per-attempt. Grace period covers real-world network blips; the rest is expectation-setting on the pre-start screen.
- Not finer-grained per-question autosave. Page-boundary save is enough for v1 given the existing FLS submission flow.
- Not a Web Worker timer. Cosmetic drift on backgrounded mobile tabs is acceptable because Layer B server finalisation covers correctness.
- Not per-student time accommodations. Deferred to a follow-up (see "Future work").

## Known expectation gaps to manage

From LMS forum research, these are the top drivers of "unfair timer" complaints:

1. "I didn't know there was a time limit." → pre-start screen is mandatory.
2. "Reload wiped my time / my answers." → server-authoritative deadline + page-boundary save. Communicate on pre-start screen.
3. "Auto-submit cut off my last answer." → 10-second persistent banner + 60-second server grace window.
4. "Internet blipped and I lost 5 minutes." → server grace window + explain on pre-start screen that the clock is wall-clock.
5. "Timer made me anxious." → hide/show toggle (server still enforces).

## Future work (out of scope for this MVP)

- **Per-student time accommodations** (ADA / WCAG 2.2.1 extensions). Strong recommendation from UX research. When built, it should be a per-`(student, form)` override storing an absolute effective time (not a multiplier), invisible to the student beyond their own effective limit (privacy). Retrofitting is more disruptive than greenfield — the "effective deadline" concept will need to propagate everywhere time is displayed.
- **Proctoring** — sibling idea `02. exam-proctering`.
- **Question randomisation / pools** — sibling idea `02. exam-proctering`.
- **Retake policies** — sibling idea `02. exam-proctering`.

## Research

- `research_timer_ux.md` — UX patterns, accessibility, anxiety mitigations, comparison across Canvas / Moodle / Blackboard / Coursera / etc.
- `research_timer_technical.md` — server-authoritative design, clock-skew-safe client countdown, state machine, finalisation strategy, HTMX/Alpine wiring.
- `research_codebase_integration.md` — concrete FLS integration points: `Form`, `FormProgress`, `form_start` / `form_fill_page` views, content schema flow.
