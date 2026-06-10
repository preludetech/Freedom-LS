# Roadmap

_Last updated: 2026-06-09_

## Summary

- This document is the canonical home for features that are planned, partially built, or not yet started. Other product docs link here rather than restating half-built status.
- Current half-built items: RBAC role system (infrastructure exists, not wired into access control), xAPI tracking (placeholder stub only), `SiteGroup` (commented out).
- Features not yet built: 2FA/MFA, educator-interface management actions (membership, registration, deadlines, messaging).
- Shipped and functional features are documented in their own product docs; this document covers only what is not yet complete.

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
