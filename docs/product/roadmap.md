# Roadmap

_Last updated: 2026-10-25_

## Summary

- This is the canonical home for features that are planned, partially built, or not started. Other product docs link here rather than restating half-built status.
- **Half-built:** course applications (apply flow and authored application form built; review/approval workflow not built), role-based access control (organisation and cohort roles are managed in the educator interface; site admin is still assigned by a developer, and records edited directly in the Django admin are not logged), notifications (in-app bell and notification centre built, off by default; email and most events not built), direct messaging (one-to-one conversations built, off by default; moderation, email, real-time delivery and group messaging not built), xAPI (non-functional stub), site-aware user groups (drafted, disabled), registration rules (HR attributes and rules that register learners built; rules that recommend, educator-interface screens and CSV import not built).
- **Not built:** 2FA/MFA, educator-interface deadline override management, notify-on-launch for coming-soon courses, per-request access-controlled media downloads, data-retention/data-subject-rights tooling, the deliberately deferred organisation capabilities, and the deliberately deferred cohort report capabilities.
- Shipped features are documented in their own product docs; this one covers only what is incomplete.

## Organisation Deferrals

**Status: Not built — deliberate deferrals for this release.**

Organisations shipped as a grouping layer between a site and its cohorts and registrations; see [multi-tenancy and isolation](./multi-tenancy-and-isolation.md#organisations) for what an organisation is and where the isolation boundary actually sits. Several capabilities were deliberately left out rather than overlooked:

- **No delete or merge** — an organisation cannot be removed or combined with another once created, and a learner's association with one can only be deactivated, never deleted.
- **No nested organisations** — the structure is flat, with no parent/child relationship.
- **No roster management in the educator interface** — associating a learner with an organisation, or marking one removed, is done in the Django admin only; there is no add-, remove-, or suspend-learner action there, and no "show removed learners" filter.
- **Bulk and CSV tools are learner-only** — learners can be added to an organisation by CSV import, and deactivated or reactivated in bulk, but an import cannot update existing learners' details, create cohorts or map columns, and there is no bulk delete or bulk cohort move.
- **No cross-organisation view** — nothing shows one person's associations across every organisation they study with, though a person can hold several.
- **No notification when a learner is removed** — neither the learner nor anyone else is told, even though courses held through that organisation stop opening for them.
- **No per-organisation domain, subdomain, colours, or theme**, and no organisation branding in emails or certificates.
- **The organisation switcher has no search, recents, or favourites** — it is a flat list.

See [educator interface](./educator-interface.md#organisation-scope) and [admin interface](./admin-interface.md#organisation-management) for what is available today.

## Course Applications

**Status: Access type, apply flow, and authored application form built; review/approval workflow not built.**

A course can be configured as free or application-gated. A learner browsing an application-gated course sees an "Apply now" prompt; confirming creates an application. Where the course names an application form, the applicant works through it, including a file-upload question if the form has one, before reaching the status page; a gated course with no form goes straight to the status page. A superuser reads submitted answers and downloads uploaded files in the Django admin; other staff cannot. See [configuration and extension](./configuration-and-extension.md) for the access backend, [learner experience](./learner-experience.md) for the applicant's flow, and [admin interface](./admin-interface.md) for the admin's answer and file views.

What remains missing:

- **Review and approval** — nobody can review, approve, reject, request changes on, or withdraw an application. There are no reviewer roles or permissions, no audit trail, and no admin or educator review screen. The applicant's status page is static and never reflects a decision.
- **Malware scanning of uploaded files** — an upload's real type and size are checked and images are re-encoded, but nothing inspects the contents for a malicious payload; a reviewer downloads what was submitted, unmodified in the case of a PDF. This is a deliberate, tracked deferral; see [security and data handling](./security-and-data-handling.md#applicant-uploads-built).
- **A retention or expiry policy for uploaded files** — see [data retention](#data-retention-deletion-and-subject-rights).
- **Some question-authoring options** — no conditional questions, no dropdown or boolean question type, no per-question upload limit, and no numeric range validation.

The review workflow attaches to seams already in place; it will not require rearchitecting the access backend, the apply flow, or the form.

## Registration Rules

**Status: HR attributes and rules that register learners built; rules that recommend, educator-interface screens and CSV import not built.**

Registration rules let an organisation register learners automatically, for example "everyone with job title Driver is registered for Road Safety". Both parts are built, as optional apps managed in the Django admin: [HR attributes](./hr-attributes.md) record each learner's job title, department, location and start dates, and [registration rules](./registration-rules.md) register matching learners and retract them when they stop matching. Each organisation has a "Registration rules enabled" switch, off by default, that decides whether its rules act.

Not built:

- **Rules that recommend** a course rather than register for it.
- **Educator-interface screens** for the attribute lists, a learner's attributes and the rules; all of these are Django admin only. A registration's source is not shown in the educator interface either.
- **CSV import** of attributes.
- **A wider rule language**: only attribute matching exists; there are no other rule kinds, no rules that register cohorts, no exclusion conditions, and no "or" across attributes.
- **Rule administration extras**: no bulk enable or disable, no periodic reconcile job, and no audit log of rule changes.

Not planned: syncing attributes from SSO or SCIM, line managers, relative due dates, recertification, and organisation-defined custom attributes.

## Course Visibility & Express Interest

**Status: Visibility and the express-interest waitlist are built; notify-on-launch and auto-enrolment are not.**

Courses can be published, coming soon, or hidden, enforced consistently across every access backend, with an express-interest waitlist for coming-soon courses and an educator-facing demand view. See [learner experience](./learner-experience.md) and [educator interface](./educator-interface.md).

Not built:

- **Notify-on-launch** — when a coming-soon course is published, interested learners receive no notification. Expressing interest only records the interest; FLS's [in-app notifications](#notification-system) have no course-launch event, and there is no email to send instead. The coming-soon copy sets a soft "we'll let you know" expectation that nothing currently fulfils — a deferred dependency, not something learners can rely on today.
- **Auto-enrolment on launch** — interested learners are not registered automatically when a course launches; they must return and enrol or apply as normal.

## Notification System

**Status: In-app notifications built; delivery and most events not built.**

FLS has an in-app bell and notification centre, off by default, described in [notifications](./notifications.md). Two things raise a notification: a learner being registered for a course by someone else, and a new [direct message](./messaging.md). Still missing: email or any other delivery channel, notification preferences, digests, and notifications for course launch, removal from an organisation, deadlines and cohort events. Beyond the bell, FLS sends only the transactional emails for verification and password reset.

## Direct Messaging

**Status: One-to-one messaging built; moderation, email and real-time delivery not built.**

Educators and learners can exchange one-to-one messages where the site's messaging policy allows it; see [messaging](./messaging.md) for what is built. Not built:

- **Reporting and blocking** — nobody can report a message or block a user, and there is no moderation queue for site admins. Planned.
- **Email about messages** — a new message shows only in the in-app bell and Messages badge. Email delivery, preferences and digests are planned together with notification email.
- **Push delivery** — the inbox and open threads update by polling. Optional real-time push is planned, off by default.
- **Group, broadcast and cohort-wide messaging** — conversations are between two people only. Not planned in the current effort.
- **Attachments, editing and deleting messages, typing and presence indicators** — not built.

## Two-Factor Authentication (2FA / MFA)

**Status: Not built.**

No 2FA or MFA code exists in any form — no MFA app, no one-time-password integration, no related models, views, or settings. It should not be presented as available. When implemented it will be documented in [authentication](./authentication.md).

## Role-Based Access Control (RBAC)

**Status: Organisation and cohort roles are managed in the educator interface, and role changes are logged; site admin is not managed there.**

Role assignments decide who can use the educator interface and who can generate or download a cohort report; the roles and what each allows are in [educator interface](./educator-interface.md#members-and-roles). An organisation admin adds, deactivates and reactivates the organisation's members, and assigns and deactivates their roles, from the educator interface. Role definitions also exist for a system administrator, learner and observer, but grant nothing yet. What is missing:

- **Site admin is assigned by a developer.** Neither the educator interface nor the Django admin can grant or remove it.
- **No notification** tells a person that a role was granted or removed.
- **The audit log has gaps.** Role, membership, learner and cohort changes made through FLS are recorded (see [educator interface](./educator-interface.md#history)), but system administrator role changes and records edited directly in the Django admin are not. Nothing before the audit log was introduced is recorded, the log cannot be exported to CSV, and report downloads are not logged.

## Per-Request Media Access Control

**Status: Not built.**

When object storage is configured, course files are private and served through time-limited signed links, so they are not publicly discoverable. But FLS does not re-check a learner's authorisation at the moment a file is fetched — a signed link works for anyone holding it until it expires. Routing every download through the same access check that governs course pages is the stronger control and is not yet built. See [security and data handling](./security-and-data-handling.md).

## Data Retention, Deletion, and Subject Rights

**Status: Not built.**

There is no retention policy, scheduled deletion, subject-access-request tooling, right-to-erasure workflow, or portability export. User deletion is a manual admin or database operation. There is also no incident-response runbook or automated alerting for data events. All of this is operator responsibility today — see [security and data handling](./security-and-data-handling.md).

Generated [cohort reports](./reports.md) are a concrete instance of the same gap: the PDFs hold real learner names and answers and are kept until an administrator deletes them by hand, with no automatic expiry. Deletion itself is handled correctly — removing a report removes its stored file, whether deleted singly, in bulk, or as a consequence of deleting its cohort — so nothing is orphaned. What is missing is anything that prompts or schedules that deletion.

Files an applicant uploads to an application form are the same gap in miniature: they are kept until deleted by hand, and deleting the applicant's account is the only thing that removes them automatically. See [Course Applications](#course-applications).

## xAPI / Tin Can Tracking

**Status: Non-functional stub.**

An xAPI app directory exists but its model code is entirely commented out, and the app is not installed or connected to anything. xAPI is not a current capability. When implemented it will extend the tracking described in [learner tracking](./learner-tracking.md).

## Site-Aware User Groups

**Status: Drafted, disabled.**

A site-scoped equivalent of Django's groups is written but commented out, so group-based permissions across sites are unavailable. Permissions are granted per user via per-object grants. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

## Educator Interface Gaps

**Status: Cohorts and learners can be administered; deadline overrides cannot.**

The educator interface manages cohorts, cohort membership and course registration, one at a time or in bulk, and imports learners from a CSV file; its Courses section is read-only. See [educator interface](./educator-interface.md). Deadline overrides, which set or remove a due date or course time limit for a cohort course registration or a single learner, must still be managed in the Django admin by an administrator. See [admin interface](./admin-interface.md#deadline-overrides) for where this is done today.

Also not built in the educator interface: data for the cohort overview's "needs attention" card, which shows a placeholder.

Educators can message learners from within FLS; see [Direct Messaging](#direct-messaging) for what messaging still lacks.

## Deadlines

**Status: Due dates, course time limits and the overdue mark are built; nothing is enforced.**

Authors can give topics and forms a due date and courses a time limit, administrators can override them, and learners see deadlines and a missed deadline mark; see [learner experience](./learner-experience.md#deadlines). A missed deadline is only a label. Not built:

- **Consequences after a date passes** — nothing is locked, closed or ended.
- **Extensions and pause** — staff cannot extend a learner's deadlines or pause a course, and learners cannot pause their own.
- **Reminders** — no notification, email or webhook is sent as a date approaches or passes.
- **Educator-interface screens** — due dates and overrides are managed in the Django admin only; see [Educator Interface Gaps](#educator-interface-gaps).
- **Overdue in educator views** — overdue learners do not appear in a cohort's "needs attention" card or in [cohort reports](./reports.md).

## Enforcing Content Security Policy

**Status: Report-only.**

A Content Security Policy is configured but runs in report-only mode. Switching it to enforcing requires first removing the inline script and style usage the current templates depend on. See [security and data handling](./security-and-data-handling.md).

## Completion Certificates

**Status: Not built.**

Completing a course produces a finish page but no certificate or downloadable completion evidence. See [learner experience](./learner-experience.md).

## Cohort Report Deferrals

**Status: Not built — deliberate deferrals.**

The [cohort report](./reports.md) itself is built and shipped. Several capabilities around it were deliberately left out of this release rather than overlooked.

**No scheduled or emailed delivery.** A report is only ever produced on demand, by a staff member triggering it in the admin, and whoever wants it must return there to download it. There is no recurring generation and no notification when one finishes. The feature is built so that adding delivery later is a small addition — the same generation runs regardless of what starts it — but that addition is not here.

**No control over the platform's attribution mark.** A report carries a small "Powered by" mark naming the site on its cover and in every footer, alongside the organisation's own brand, and there is no setting to remove it. A deployment cannot produce a fully white-labelled report today.

**No organisation descriptor or strapline field.** An organisation's identity on the report is its name and logo only. There is no field for a second line such as an accreditation number or tagline, which a regulated training provider would want; a project needing one must fork.

**At-risk rules are not configurable.** The rules the report flags learners against are a fixed list in code, with no setting to add, remove, reorder, or retune a threshold. A project needing its own rule must fork. A future release moves rule selection and thresholds into the database, replacing the fixed list; until then this is the extension point to ask about. See [configuration and extension](./configuration-and-extension.md).
