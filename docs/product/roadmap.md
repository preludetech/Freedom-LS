# Roadmap

_Last updated: 2026-07-01_

## Summary

- This document is the canonical home for features that are planned, partially built, or not yet started. Other product docs link here rather than restating half-built status.
- Current half-built items: course applications (apply flow built; review/approval and authored form not yet built), RBAC role system (infrastructure exists, not wired into access control), xAPI tracking (placeholder stub only), `SiteGroup` (commented out).
- Features not yet built: 2FA/MFA, educator-interface management actions (membership, registration, deadlines, messaging), notify-on-launch/auto-enrolment for coming-soon courses (the visibility and express-interest features themselves have shipped).
- Shipped and functional features are documented in their own product docs; this document covers only what is not yet complete.

## Course Applications

**Status: Access type and bare apply flow built and functional; review/approval workflow and authored application form not yet built.**

A course can now be configured as either free or application-gated. Learners browsing an application-gated course are shown an "Apply now" prompt; confirming it creates an application record and shows a static status page confirming the application has been received and is pending review. The pluggable backend that drives this — controlling what learners see on course cards and detail pages, and what appears on their dashboard for in-flight applications — is described in [configuration and extension](./configuration-and-extension.md). The learner-facing flow is documented in [learner experience](./learner-experience.md).

Two significant pieces are not yet built:

- **Application review and approval** — there is no way for anyone to review, approve, reject, request changes on, or withdraw an application. There are no reviewer roles or permissions, no audit trail, and no admin or educator review screen. The applicant status page is static; it does not update to reflect any decision.
- **Authored application form** — applying collects no questions, answers, or file uploads. The multi-step application form — with configurable questions, per-question options, and file upload support — is deferred to a separate follow-up.

The `CourseApplication` model and the seams both follow-ups attach to are in place; neither will require any rearchitecture of the current access backend or apply flow.

## Course Visibility & Express Interest

**Status: Published/coming-soon/hidden visibility and the express-interest waitlist are built and functional; notify-on-launch, auto-enrolment, a separate draft state, and any scarcity mechanic are not built.**

Courses can now be set to published, coming soon, or hidden, enforced consistently across every course-access backend, with an express-interest waitlist for coming-soon courses and an educator-facing demand view. This is documented in [learner experience](./learner-experience.md) and [educator-interface](./educator-interface.md).

The following are not yet built:

- **Notify-on-launch** — when a coming-soon course is switched to published, interested students receive no automated notification. Expressing interest only records the interest; FLS has no email or in-app notification system yet to build this on. The coming-soon experience sets a soft "we'll let you know when it's ready" expectation, but nothing currently fulfils it. This is a deferred dependency on a future notification system, not something students can rely on today.
- **Auto-enrolment on launch** — students who expressed interest in a coming-soon course are not automatically registered when it launches; they must return and register or apply as normal.
- **A separate "draft" state** — visibility currently has three states (published, coming soon, hidden). A further educator-only "draft" state, invisible even by direct link, has not been built; it remains a possible small future addition.
- **Capacity-limited waitlists** — express interest is a plain, capacity-free signal of demand. There is no queue position, no "X people ahead of you," no count shown to students, and no waitlist capacity or cutoff. This is a deliberate design decision, not a gap to be filled later: FLS courses have no enrollment capacity limit, and implying one would mislead students.

When notify-on-launch (or auto-enrolment) is implemented, it will extend the behaviour described in [learner experience](./learner-experience.md) and [educator-interface](./educator-interface.md).

## Two-Factor Authentication (2FA / MFA)

**Status: Not built.**

No 2FA or MFA code exists in the codebase. There is no allauth MFA app, no django-otp integration, no TOTP models or views, and no 2FA-related settings. This feature does not exist in any form and should not be presented as available.

When 2FA is implemented, it will be documented in [authentication](./authentication.md). Until then, it is absent.

## Role-Based Access Control (RBAC)

**Status: Models and infrastructure built; minimally wired into access control.**

The role system exists as a foundation:

- Three role-assignment models are defined: `SystemRoleAssignment`, `SiteRoleAssignment`, `ObjectRoleAssignment`.
- Role definitions exist for: `site_admin`, `instructor`, `ta`, `system_admin`, `student`, `observer`.
- Management commands `sync_role_permissions` and `validate_role_permissions` exist.

However, the role system is **not the authoritative source for access control** in the current application:

- Educator access to cohorts flows through **django-guardian** object-level permissions, not through role assignments. A user must have the `view_cohort` guardian permission on a specific cohort — assigning them the `instructor` role does not automatically grant this.
- Many permissions in the role definitions are marked `# FUTURE` with no implementation.
- Role assignments and guardian permissions must be synchronised manually via the `sync_role_permissions` command; they are not automatically kept in sync.

For the current educator access model (which is functional), see [educator-interface](./educator-interface.md) and [admin-interface](./admin-interface.md).

## xAPI / Tin Can Tracking

**Status: Placeholder stub only — not functional, not installed.**

An `xapi_learning_record_store` app directory exists in the codebase. All model code in `freedom_ls/xapi_learning_record_store/models.py` is commented out (a rough draft sketch of a `LearningExperience` model). The app is **not in `INSTALLED_APPS`** and is not connected to any part of the application.

xAPI is not a current capability. When it is implemented, it will extend the tracking described in [learner-tracking](./learner-tracking.md).

## `SiteGroup` (Site-Aware User Groups)

**Status: Commented out.**

A `SiteGroup` model (a site-aware equivalent of Django's `Group`) is defined at the bottom of `freedom_ls/accounts/models.py` but is entirely commented out. `SiteGroupAdmin` is also commented out.

Site-aware group-based permissions are not currently available. The current permission model relies on django-guardian object-level grants per user. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md) for the current isolation model.

## Educator Interface Gaps

**Status: Specific management operations are admin-only; no messaging.**

The educator interface currently provides read and monitoring capabilities. The following operations are not available from the educator interface and must be performed in the Django admin by an administrator:

- **Cohort membership management** — adding or removing students from a cohort.
- **Course registration** — registering a cohort or individual student for a course.
- **Deadline management** — creating or modifying cohort deadlines, per-student deadlines, and deadline overrides.

Additionally, **there is no messaging capability** in the educator interface. Educators cannot send messages or notifications to students from within FLS.

For the current capabilities of the educator interface, see [educator-interface](./educator-interface.md).
