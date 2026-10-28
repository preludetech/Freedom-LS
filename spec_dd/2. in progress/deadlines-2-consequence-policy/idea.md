# Deadline consequence policy

Spec 2 of 7 in the Deadlines effort. Read the "Deadlines" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A deadline policy decides what happens when a due date or the course time limit passes. The policy
is chosen per site, organisation, cohort, course or registration, and edited in the Django admin.
Four consequences are configurable: mark overdue, close the content item, end course access, and
notify educators. A grace window sits in front of the closing and ending consequences.

This spec builds the policy and enforces it. Enforcement happens in the course player (closed
items) and in the course access check (ended access). Marking overdue extends what spec 1 shows.
"Notify educators" exists here only as a policy setting; spec 5 raises the notifications.

It also settles the way back in. After the time limit ends access, only staff can restore it.
Restoring opens a new window and keeps all progress.

## Why

Consequences differ by course, cohort and organisation, and no comparable system documents that as
a first-class idea; Moodle and Canvas get there through per-course settings (landscape file,
section d). Users complain when a consequence is invisible or inconsistent: Docebo's soft deadline
silently suppresses a notification, Canvas marks "Late" inside a grace period and cannot turn the
label off (sentiment file, section a). A grace window and a separate late, closed and ended are
the strongest findings there.

FLS today has one consequence, a lock on a hard-deadline item, and nowhere to set it per cohort or
organisation.

## What is settled

- **The policy is a swappable class** behind a setting, in the `COURSE_ACCESS_BACKEND` style. The
  default class reads layered rows and resolves them most specific first, reusing the pattern of
  `messaging_policy/resolver.py`. The settings layer is always present. A missing row inherits.
- **Layers**: site, organisation, cohort, course and registration. The registration layer covers
  both `LearnerCourseRegistration` and `CohortCourseRegistration`. Each value that is not a flag has
  its own unset marker.
- **The default policy is mark overdue only**, with no grace window. An organisation turns on the
  rest.
- **Four consequences**: mark overdue, close the content item, end course access, notify educators.
  Each is a policy setting. Mark overdue is on by default and a policy can turn it off; spec 1
  shows it unconditionally until this spec adds the switch. Ending access applies to the course
  time limit; closing applies to item due dates.
- **Grace window.** A policy setting, a length of time after the due date. The overdue mark may
  appear at the due date while closing and ending wait for the window to pass. The learner is shown
  the consequence next to the date.
- **Enforcement is on read.** Whether an item is closed or access has ended is computed from the
  dates when the page is served. No sweep is needed for it to take effect.
- **Completed items never close.** Results pages and `form_submit_and_exit` stay ungated, as today.
- **Ending access does not set `is_active=False`.** The registration stays active, no
  `course.unregistered` fires, and the course shows on the dashboard as access ended.
- **Restore after the time limit (decision 8).** Only staff restore access. Restoring opens a new
  window and keeps progress. A learner cannot self-register their way back. The staff action itself
  is made in the Django admin here; the educator screen is spec 6.
- **One registration governs**: the one `learner_for_course` resolves.
- **Single source of truth for closing.** The two lock paths today (the player's check and the
  table of contents status) are replaced by one decision that the player and the table of contents
  both read.
- **Notify educators is a switch.** The policy records whether educators are notified of overdue
  learners. Nothing is raised here.
- **Configuration is admin-only.** Policy rows live in the Django admin; no educator screen edits
  them.

## Open until the spec

- **Layer order between course and organisation**, and which settings each layer can hold.
  Specs 3, 4 and 6 build on the answer.
- **Where "access ended" is enforced**: a deadline-aware wrapper around the access backend, applied
  by the loader like `VisibilityEnforcingBackend`, or the registration predicate
  (`is_registered_for_course`). The choice decides who still sees a hidden course. Specs 3, 4 and 7
  build on it.
- **Whether "close" leaves an in-progress form attempt finishable.** Spec 3 builds on it.
- **What the registration layer is keyed on** for a learner who holds both an individual and a
  cohort registration, given that one registration governs.
- **How the grace window interacts with an override** that moves a date, as far as spec 1's
  override record allows.

## Out of scope

- Due dates, the time limit and the overdue display (spec 1).
- Extensions, pause and resume, pause limits (spec 3). The policy gains those settings there.
- Learner self-pause (spec 4).
- Raising notifications, reminders, and the `deadline.missed` webhook (spec 5).
- Educator-interface screens, including a screen to restore access (spec 6).
- Needs attention and the cohort report (spec 7).
- Score penalties and "no credit after the deadline". Retakes. Payments and fees.

## Resources

- `spec_dd/1. next/deadlines/research_deadline_integration_points.md`: sections 3 and 4, the policy
  patterns and every enforcement point, including the exempt routes.
- `spec_dd/1. next/deadlines/research_current_deadlines.md`: sections 1, 3 and 4, the old hard and
  soft behaviour and the registration model.
- `spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md`: sections d and f.
- `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md`: sections a, g and the first
  implication.
- Done specs `user-communication-3-messaging-policy`, `better-course-progress-tracking`.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:app-settings`,
  `fls-dev:admin-interface`, `fls-dev:testing`.
