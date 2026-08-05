# Roadmap

_Last updated: 2026-08-05_

## Summary

- This is the canonical home for features that are planned, partially built, or not started. Other product docs link here rather than restating half-built status.
- **Half-built:** course applications (apply flow built; review/approval and authored form not built), role-based access control (built but not wired into access decisions), xAPI (non-functional stub), site-aware user groups (drafted, disabled).
- **Not built:** 2FA/MFA, educator-interface management actions, notify-on-launch for coming-soon courses, per-request access-controlled media downloads, and data-retention/data-subject-rights tooling.
- **Known defect:** educator cohort detail pages are not permission-checked.
- Shipped features are documented in their own product docs; this one covers only what is incomplete.

## Educator Detail-Page Authorisation Gap

**Status: Known defect — not yet fixed.**

Cohort listings in the educator interface are filtered by the per-cohort permission an administrator grants, but cohort *detail* pages — including the course-progress matrix — do not re-check that permission. The interface as a whole requires only that the visitor be logged in, so any authenticated user on the site who navigates directly to a cohort detail URL can view that cohort's students and their progress data.

Site isolation is unaffected: the gap is within a single tenant, never across tenants.

The fix is to apply the same object-level permission check on detail views that already governs the listings. See [educator interface](./educator-interface.md).

## Course Applications

**Status: Access type and bare apply flow built; review/approval workflow and authored application form not built.**

A course can be configured as free or application-gated. A learner browsing an application-gated course sees an "Apply now" prompt; confirming creates an application and shows a static status page saying it has been received and is pending review. The pluggable backend driving this is described in [configuration and extension](./configuration-and-extension.md) and the learner flow in [learner experience](./learner-experience.md).

Two pieces are missing:

- **Review and approval** — nobody can review, approve, reject, request changes on, or withdraw an application. There are no reviewer roles or permissions, no audit trail, and no admin or educator review screen. The applicant's status page is static and never reflects a decision.
- **Authored application form** — applying collects no questions, answers, or file uploads. A multi-step form with configurable questions and file upload is deferred to a follow-up.

The seams both follow-ups attach to are in place; neither will require rearchitecting the access backend or the apply flow.

## Course Visibility & Express Interest

**Status: Visibility and the express-interest waitlist are built; notify-on-launch and auto-enrolment are not.**

Courses can be published, coming soon, or hidden, enforced consistently across every access backend, with an express-interest waitlist for coming-soon courses and an educator-facing demand view. See [learner experience](./learner-experience.md) and [educator interface](./educator-interface.md).

Not built:

- **Notify-on-launch** — when a coming-soon course is published, interested learners receive no notification. Expressing interest only records the interest; FLS has no email or in-app notification system to build this on. The coming-soon copy sets a soft "we'll let you know" expectation that nothing currently fulfils — a deferred dependency, not something learners can rely on today.
- **Auto-enrolment on launch** — interested learners are not registered automatically when a course launches; they must return and enrol or apply as normal.

## Notification System

**Status: Not built.**

FLS has no email or in-app notification system beyond the transactional emails allauth sends for verification and password reset. This blocks notify-on-launch above, educator-to-learner messaging, and deadline reminders.

## Two-Factor Authentication (2FA / MFA)

**Status: Not built.**

No 2FA or MFA code exists in any form — no MFA app, no one-time-password integration, no related models, views, or settings. It should not be presented as available. When implemented it will be documented in [authentication](./authentication.md).

## Role-Based Access Control (RBAC)

**Status: Built and installed, but not the authority for access decisions.**

A role system ships and is migrated: system-level, site-level, and object-level role assignments, with role definitions for site admin, instructor, TA, system admin, student, and observer, plus commands to synchronise and validate role permissions.

It is not, however, what governs access today:

- Educator access to cohorts is decided by per-object permissions, not by role assignment. The role helpers *write* those object permissions, so roles act as a management layer over them rather than a parallel system — but assigning someone the instructor role does not by itself grant access to any specific cohort.
- Many permissions in the role definitions are marked as future work with no implementation behind them.
- Role assignments and the object permissions they produce are synchronised by running a command, not automatically.

For the access model that is actually in force, see [educator interface](./educator-interface.md) and [admin interface](./admin-interface.md).

## Per-Request Media Access Control

**Status: Not built.**

When object storage is configured, course files are private and served through time-limited signed links, so they are not publicly discoverable. But FLS does not re-check a learner's authorisation at the moment a file is fetched — a signed link works for anyone holding it until it expires. Routing every download through the same access check that governs course pages is the stronger control and is not yet built. See [security and data handling](./security-and-data-handling.md).

## Data Retention, Deletion, and Subject Rights

**Status: Not built.**

There is no retention policy, scheduled deletion, subject-access-request tooling, right-to-erasure workflow, or portability export. User deletion is a manual admin or database operation. There is also no incident-response runbook or automated alerting for data events. All of this is operator responsibility today — see [security and data handling](./security-and-data-handling.md).

## xAPI / Tin Can Tracking

**Status: Non-functional stub.**

An xAPI app directory exists but its model code is entirely commented out, and the app is not installed or connected to anything. xAPI is not a current capability. When implemented it will extend the tracking described in [learner tracking](./learner-tracking.md).

## Site-Aware User Groups

**Status: Drafted, disabled.**

A site-scoped equivalent of Django's groups is written but commented out, so group-based permissions across sites are unavailable. Permissions are granted per user via per-object grants. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

## Educator Interface Gaps

**Status: Read and monitoring only.**

These operations must be performed in the Django admin by an administrator:

- **Cohort membership** — adding or removing students.
- **Course registration** — registering a cohort or an individual student for a course.
- **Deadlines** — cohort deadlines, per-student deadlines, and overrides.

There is also **no messaging capability** — educators cannot contact students from within FLS (see [Notification System](#notification-system)). For what the interface does provide, see [educator interface](./educator-interface.md).

## Enforcing Content Security Policy

**Status: Report-only.**

A Content Security Policy is configured but runs in report-only mode. Switching it to enforcing requires first removing the inline script and style usage the current templates depend on. See [security and data handling](./security-and-data-handling.md).

## Completion Certificates

**Status: Not built.**

Completing a course produces a finish page but no certificate or downloadable completion evidence. See [learner experience](./learner-experience.md).
