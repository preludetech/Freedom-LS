# Cohort administration

Spec 6 of 12 in the educator interface rebuild. Read `../educator-interface-full-polish/spec-order.md` first. Depends on specs 2, 3 and 5. Runs in parallel with 7 and 10.

## What

The cohorts section, complete. List, detail, create, edit, deactivate, reactivate, delete when empty, and registering and unregistering a cohort for courses. Plus the courses section rebuilt as a read-only, organisation-scoped view, which closes the two remaining disclosure gaps from the deleted `critical_security_fixes` spec.

## Why

Cohorts are the unit everything else hangs off. A cohort's course registrations are what give its members access, and the cohort detail page is where an educator goes to see how a group is doing. Today the section can create, rename and delete a cohort, and nothing else. Registration is admin-only. There is no way to retire a cohort short of deleting it, and deletion is blocked as soon as any member has progress, because a course progress record protects the registration that minted it.

The courses section today lists every course on the site to every educator, hidden courses included, and its cohorts panel lists every cohort on the site registered to a course, by name, across organisations. Both are declared with `check_access_exempt_reason` on `CourseConfig` rather than fixed. Rebuilding the section removes the exemption instead of editing it.

## What is settled

**Cohort gets `is_active`.** A new boolean, default true, with a migration. Deactivating a cohort changes nothing about its members, their registrations or their progress. It marks the cohort inactive, hides it from lists by default, and stops it appearing as a destination for adds and moves. Reactivate reverses it. Whether an inactive cohort still grants course access through its registrations is decided in the spec; the safe default is that it does not, and the confirmation says so.

**Delete only when empty.** The delete action is offered only for a cohort with no memberships and no course registrations. Otherwise the action is deactivate, and the confirmation explains why delete is unavailable. This matches Canvas, Google Classroom and Open edX, and the data model enforces it anyway.

**List.** Name, status, learner count, courses, created. Search by name. Filters: status (active by default, with a toggle to show inactive), course. Row selection is present for spec 8. Sort by name, learner count, created.

**Create and edit.** Name only, plus anything the `Cohort` model gains. The organisation is the current one. The name is unique per organisation and the form says so on a clash. Create is a modal with "save" and "save and add another" as today.

**Detail.** Per the cohort detail mockup, cut to what exists: a header with name, status badge and actions; tabs for overview (details, course completion per registered course, needs-attention summary once spec 10 lands, otherwise a placeholder), learners (owned by spec 7), courses, settings (deactivate, reactivate, delete). The instructors block from the mockup shows the educators with grants on this cohort, read-only here; spec 9 makes it editable.

**Course registration.** From the courses tab: register the cohort for a course chosen from the courses visible in this organisation, and unregister. Unregister sets `is_active` false on the `CohortCourseRegistration` and reads as reversible; re-register reactivates the same row. Registering fans out course progress records to members as the existing signals already do. The unregister confirmation says that members keep their progress, and names any member who also holds an individual registration for the same course and so keeps access.

**Courses section.** Lists courses that are registered to at least one cohort or learner in this organisation, or that are visible on the site and not hidden, whichever the spec decides after checking `content_engine` visibility. Course detail shows the course, its cohort registrations in this organisation with links to the cohort, and its individual registrations in this organisation. No actions here; management happens from the cohort and learner sides. `CourseConfig.check_access_exempt_reason` and the `@claude` comment above it are removed because the gap they declared is closed, not because they are in the way.

**Permissions.** From the spec 5 matrix. Organisation staff and site admins manage cohorts; instructors see their assigned cohorts; TAs read.

**Webhooks.** Spec 7 decides which events fire for cohort registration changes. This spec fires whatever spec 7 named, and if 7 has not landed, leaves a clearly named seam and a test that documents the absence.

**Docs.** The cohorts and courses sections of `docs/product/educator-interface.md` are rewritten. Upgrade notes flag the migration.

## Open until the spec

- Whether an inactive cohort's registrations still grant course access. See above.
- Whether "courses visible in this organisation" needs a new query helper next to `cohorts_visible_to`, and where it lives.
- What the overview tab shows before spec 10 exists. Probably counts and the course list.

## Out of scope

- Membership actions from the cohort side (spec 7 owns the learners tab and every membership action).
- Bulk actions (spec 8). Deadlines. Reports (spec 10).

## Resources

- `../educator-interface-full-polish/comparable-systems-learner-management.md`, sections 4, 6 and 7 for deactivate versus delete and unregistration semantics.
- `../educator-interface-full-polish/Educator LMS Interface Design/Educator Cohorts and Admin.dc.html` screens 05 and 07, and the mobile `M08` and `M10`.
- `spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/decision.md`, why nothing retires a course progress record.
- Skills: `fls-dev:multi-tenant`, `domain-glossary`, `fls-dev:testing`, `fls-dev:update_product_docs`.
