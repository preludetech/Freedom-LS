# Spec order and parallelism: educator interface rebuild

The `idea.md` in this directory asks for three things. A panel framework that is complete and self-contained. An educator interface where organisation staff administer learners, cohorts, course registrations and other educators. Reporting on learner progress built on the cohort report machinery. That is too much for one SDD run, so it is cut into twelve specs. Each lives in its own directory under `spec_dd/1. next/` as `educator-interface-N-<name>/`, and the number is its place in the order. This file is the index. The mockups, the two shared research files and `application-review-ui/` stay here.

Read this file before starting any of the twelve. Each idea assumes you have.

## The specs

| # | Directory | Scope | Depends on |
|---|---|---|---|
| 1 | `educator-interface-1-panel-framework-core` | Panel, tab and action API rework; scoping and permission hooks; a template contract instead of returned strings; URL-state hardening; sidebar sections and base views. The educator interface becomes the reference consumer, cut down to a skeleton with the progress matrix deleted. | none |
| 2 | `educator-interface-2-panel-framework-tables` | Table layer moves into the framework. Per-table prefixed query state, declared filters, row selection with a bulk-action hook, CSV export hook, stacked rows on mobile. | 1 |
| 3 | `educator-interface-3-panel-framework-dialogs` | One shared native dialog for modal forms and read-only content. The right-hand quick view, non-blocking on desktop, with its trigger component, endpoint convention and invalidation. | 1 |
| 4 | `educator-interface-4-panel-framework-components` | The cotton components the mockups show, built on FLS brand tokens: stat tile, status badge, avatar chip, attention list, progress bar, section card, toolbar, empty state, page header. | 1 |
| 5 | `educator-interface-5-permissions` | The permission matrix on the existing roles. Role permission strings and the sync fix, object-aware creation checks through the framework hook, who may assign which role, and what a denied user sees. | 1 |
| 6 | `educator-interface-6-cohort-administration` | Cohort list and detail, create and edit, `is_active` on `Cohort`, deactivate and reactivate, delete only when empty, cohort course registration and unregistration. The courses section rebuilt read-only and organisation-scoped. | 2, 3, 5 |
| 7 | `educator-interface-7-learner-administration` | Add a learner (new account with a setup email, or an existing user), list and detail, deactivate and reactivate, cohort membership add, remove and move, individual course registration and unregistration, resend the setup email. | 2, 3, 5 |
| 8 | `educator-interface-8-bulk-operations` | CSV import as a page flow with a preview and per-row outcome labels. Multi-select bulk actions on the learner and cohort tables. | 6, 7 |
| 9 | `educator-interface-9-educator-administration` | An educators section. Add, remove and scope instructors and TAs; grant organisation staff; role descriptions; confirmation on escalation and removal. | 5, 7 |
| 10 | `educator-interface-10-reporting-dashboards` | Organisation dashboard as a base view, the cohort report on screen from the existing gathered data, a learner drill-down that replaces the deleted matrix, PDF generation and download from the interface, roster CSV. | 2, 4 |
| 11 | `educator-interface-11-audit-log` | An append-only audit log recorded by the role utilities and every action in specs 6 to 9, shown per organisation, learner and cohort. | 6, 7, 9 |
| 12 | `educator-interface-12-docs-and-polish` | Product doc and an `fls-dev` skill for the panel framework, the educator product doc rewritten, a mobile and accessibility pass across all slices, consolidated upgrade notes, leftovers deleted. | all |

## Ordering and parallelism

```
1 core ──┬── 2 tables ──────┬── 6 cohort admin ──┬── 8 bulk ──────────┐
         ├── 3 dialogs ─────┤                    │                    │
         ├── 4 components ──┼── 7 learner admin ─┼── 9 educator admin ┼── 11 audit ── 12 docs and polish
         └── 5 permissions ─┘                    │                    │
                            └── 10 reporting ────┘────────────────────┘
```

- **Spec 1 runs alone and first.** Everything else builds on its API. It is also the spec that throws away the current educator interface, so nothing downstream has to keep old code alive.
- **Specs 2, 3, 4 and 5 run in parallel** once 1 has landed. They touch different files. Two cautions. Specs 2 and 3 both add Alpine components next to the framework's existing ones, so whoever lands second rebases onto the other's JS file. Spec 5 changes the role definitions and the framework's permission hook contract, so 2 and 3 should not invent their own permission checks.
- **Specs 6, 7 and 10 run in parallel** after their dependencies. 6 and 7 both add panels to the cohort detail view. 6 owns the view, its overview, courses and settings tabs. 7 owns the learners tab and every membership action, from either side. 10 needs only 2 and 4, so it can start before 5 is done; it links to learner and cohort pages but does not change them.
- **Specs 8 and 9 run in parallel.** Both reuse the account-creation path that 7 builds (match an existing user by email, or create one and send the setup email). Neither should write its own.
- **Spec 11 after 6, 7 and 9**, because it records their actions. **Spec 12 last.**

Together, 1 and the four after it are the "foundation". If you want an earlier vertical slice to show someone, 1 plus 2 plus 6 is the shortest path to a usable cohorts section.

## Decisions already taken

These were settled with the product owner while cutting the specs. The ideas rely on them and do not reopen them.

1. **Deactivate, never delete, in the educator interface.** Learners, registrations and cohorts get deactivate and reactivate. A cohort can be deleted only when it has no memberships and no course registrations. Hard deletion of a `User` stays in the Django admin, where GDPR requests are handled. The data model agrees: a course progress record protects the registration that minted it, so a cohort with any progress cannot be deleted anyway.
2. **Organisation staff manage instructors and TAs** inside their own organisation. Only `site_admin` may grant `organisation_staff` or `site_admin`. No new roles.
3. **An audit log is in scope**, as spec 11, after the actions it records exist.
4. **The old drafts are gone.** The six sub-drafts and the wayfinder output that used to sit in this directory were deleted once their research had moved into the new spec directories. This index and the twelve ideas are the record.

## Assumptions the ideas make

Nobody asked about these; they were judgement calls. Say so in the spec if one turns out wrong.

- **The mockups are the visual language, not the scope.** `Educator LMS Interface Design/*.dc.html` were drawn for the first-class brand by a tool that knows nothing about FLS. Build to match their layout, density and component shapes, using FLS role tokens and `c-icon`. Ignore what they show that is out of scope: custom roles and a "create role" button, messaging, "reset attempt", certificates, schedule, compliance, "this week". The mobile bottom tab bar is an open question in spec 1, and the default is no, keep the shared sidebar sheet.
- **Individual course registration is in scope** alongside cohort registration. The older draft said cohorts only. The capability list wins.
- **The denied experience has three parts.** Organisation and instance scope stays a 404, as today, so slugs and ids cannot be enumerated. An action the user can see but may no longer perform returns 403 with a message saying what happened and who to ask. Controls the user cannot use are hidden, not disabled.
- **No new dependencies.** The framework stays bespoke and the table layer is built locally (the tables2 research in spec 2 explains why). Native `<dialog>`, htmx 2 and Django 6's `{% querystring %}` cover the dialogs and URL state.
- **No invitation model.** A learner is "pending" when staff created the account and the person has never logged in. "Resend" re-sends the account setup email, built on allauth's password reset token. "Revoke" is deactivate. Spec 7 confirms this.
- **Deadlines are left alone.** Existing deadline data is neither shown nor touched. The rework comes later.
- **Everything is organisation-scoped and site-aware.** `Learner`, `Cohort` and `CohortCourseRegistration` reach an `Organisation`; registrations reach it through the learner or the cohort. Nothing lets an educator reach across organisations.

## Unknowns resolved inside a spec

Each of these is an open question in the idea that owns it. Resolve it there and write the answer into any later idea it affects.

| Unknown | Owner | Affects |
|---|---|---|
| Does the shared interface shell (`_base_interface.html`, `sidePanel`) need to change, and is a mobile bottom tab bar wanted? Changes hit the learner course player too. | 1 | 3, 4, 12 |
| Does `site_admin`'s cohort permission set land in guardian at all, given that role sync filters permissions to the target's content type? What replaces the content-type filter so organisation roles can carry learner-management permissions? | 5 | 6, 7, 9 |
| A cohort move deletes one membership and creates another. The new membership mints a fresh course progress record and the resolver picks it, so the learner would resume at 0%. Re-point the old record, or accept a fresh pass? | 7 | 8, 10 |
| Which webhook events fire for membership and cohort registration changes? Today only individual registration creation fires `course.registered`. | 7 | 6, 8 |
| Which dashboard levels read live queries and which read gathered report data, and what does that cost at a realistic organisation size? | 10 | 12 |
| Role description copy, and whether the mockup's "roles and permissions" screen survives as a read-only list. | 9 | 12 |
| Audit log retention. | 11 | none |

## Out of scope for all twelve

- Deadlines, in any form. A separate rework follows.
- Learner-facing communications. The quick view must be able to host a message composer later, nothing more.
- Application review (`application-review-ui/` in this directory is a separate effort). The rebuilt interface must not block hosting a review inbox as a section later.
- Deliberate retakes or progress resets.
- New roles, the Django admin, the learner interface, content authoring, and the cohort report PDF pipeline itself (reused, not redesigned).
- `/tmp/lms_templates` sitting early in `TEMPLATES[0]["DIRS"]` in `config/settings_base.py`. It was item 4 of the deleted `critical_security_fixes` spec and has nothing to do with this work. It still needs its own fix.

## Shared references

- The source idea, `idea.md`, in this directory.
- Design mockups in `Educator LMS Interface Design/`. Eight desktop screens, eleven mobile, one shared sidebar. Its `_ds/` folder is the first-class design system and is not FLS's.
- `htmx-modal-drawer-url-state.md`, the mechanics for the drawer, the modal and URL state, read for specs 1, 2 and 3.
- `comparable-systems-learner-management.md`, what seven LMSs let staff do and where FLS differs, read for specs 6 to 9.
- Done specs that shaped the data model: `organisations`, `learners-associated-with-organisations`, `better-course-progress-tracking` (its `decision.md` overrides its idea), `basic_reports`, `report-rendered-with-org-name`, `role_based_permission_system_foundations`. All under `spec_dd/3. done/`.
- Skills every one of these specs should consult: `domain-glossary`, `brand-guidelines`, `fls-dev:multi-tenant`, `fls-dev:template`, `ds:htmx`, `fls-dev:alpine-js`, `fls-dev:frontend-styling`, `fls-dev:icon-usage`, `fls-dev:testing`.
