# Recommended Order

## Tier 1 — Foundational (do first, others depend on these)

### 1. Role-Based Permission System Foundations

This is both the most mature draft (full spec + 3 research docs) and the most foundational. Almost everything else — educator CRUD, notifications, messaging, reporting — needs to know "who is allowed to do what." Building on top of a proper permission system avoids retrofitting access control later.

### 2. Student Content Access Control

Small but critical security fix. Students can currently bypass blocked content by typing URLs directly. This is a bug-class issue, not really a feature. Should be quick to implement and shouldn't wait.

### 3. Security Audit

Best done early while the codebase is smaller and before adding many new features. Findings from ISO 27001/POPI/GDPR compliance will likely influence how you build everything else (data retention, consent, audit trails).

## Tier 2 — Core Educator Functionality

### 4. Deadline Setting for Cohorts

Currently just an empty placeholder, but deadlines are a prerequisite for meaningful notifications (overdue alerts) and reporting. Get the data model in place early.

### 5. Educator Interface Misc Functionality (Cohort CRUD)

Educators need to create/edit cohorts in the educator interface rather than the admin. This is basic operational functionality that other features build on.

### 6. Educator Interface Learner Quick View

A UX enhancement for the educator interface. Not blocking anything, but makes the educator experience significantly better and sets up a reusable pattern (the drawer component) for future features.

## Tier 3 — Communication & Notifications

### 7. Simple Notifications

The notification bell and notification infrastructure is needed by messaging (and eventually deadlines, new courses, etc.). Build this before messaging.

### 8. Messages

Well-researched and ready for a spec. Depends on the notification bell from simple_notifications. The research explicitly references polling for unread badge counts and a notification UX.

## Tier 4 — Analytics & Tracking

### 9. xAPI Implementation

Event tracking touches everything, so it's better to have it in place before adding many more features — but it's also a large undertaking. Doing it here means new features built after this point can emit xAPI events from the start.

### 10. Email Tracking

Depends on having emails being sent (and ideally xAPI as the event store). Currently just a one-liner idea.

## Tier 5 — Reporting & Compliance

### 11. Corporate Reporting (WSP/ATR)

Requires student progress data, cohort data, and likely deadline data to be meaningful. Also benefits from xAPI data.

### 12. B-BBEE Skills Development Reporting

South Africa-specific compliance reporting. Similar dependencies to corporate reporting. Currently empty — needs an idea document first.

## Tier 6 — Cross-Cutting Quality

### 13. Make Accessible (a11y)

Listed last not because it's unimportant, but because the idea itself says "full review and cleanup of the entire site." Doing this after the major UI features (messaging, notifications, educator CRUD, quick view) are built means you only do the accessibility pass once rather than retrofitting each new feature. That said, accessibility best practices should be followed during development of all the above.

---

## What's Obviously Missing

1. **Email sending system** — Email tracking assumes emails are being sent, but there's no draft for transactional email (password resets, welcome emails, deadline reminders, digest notifications). This is a prerequisite for email tracking and for the deferred "email notifications for messages" feature.
2. **Audit logging** — The permission spec explicitly excludes it, the security audit will almost certainly require it (ISO 27001), and POPI/GDPR compliance needs data access records. This should be its own draft.
3. **Student-facing permissions/self-service** — The permission system is educator-only. There's nothing about students managing their own profile, changing email, or deleting their account (POPI/GDPR "right to be forgotten").
4. **Data export / portability** — GDPR and POPI both require data portability. No draft covers this.
5. **Course content management (educator-side)** — Educators can view cohorts and progress, but there's no draft for creating/editing course content through the educator interface (as opposed to the admin).
6. **Search** — As the platform grows (courses, students, messages), there's no mention of search functionality anywhere.
7. **Bulk operations** — Importing students via CSV, bulk-enrolling in cohorts, bulk-messaging — common LMS pain points that aren't covered.
8. **LTI integration** — The permission spec references LTI 1.3 role alignment as future work, but there's no standalone draft for LTI integration, which is critical for LMS interoperability.
