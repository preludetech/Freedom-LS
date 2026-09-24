# Educator interface rebuild

## Destination

A sequenced set of decision-complete idea files under `spec_dd/1. next/`, one per spec, each ready for `/sdd:spec_from_idea` without re-opening design questions, plus one index giving their dependency graph and build order. The existing drafts in `spec_dd/1. next/educator-interface-full-polish/` are retired once the new ideas supersede them.

## Notes

- **Source idea:** `spec_dd/1. next/educator-interface-full-polish/idea.md`. The sub-drafts in that folder (`01. educator interface critical functionality`, `panel-framework-tables-and-panel-api- upgrades-and-design`, `educator-interface-quick-view-panel`, `educator-interface-learner-quick-view`, `learner-management-actions`, `structure`, and their research files) are **input, not decisions**. Most predate `Organisation`/`Learner`.
- **Execution override:** writing the idea files is the destination, so the final task ticket does it inside the map. Nothing else gets built.
- **Nothing in the current educator interface is kept.** `educator_interface` views, the cohort course-progress matrix, all of it can be deleted and rebuilt from scratch. No need to keep anything alive in the meantime.
- **The users:** people associated with a school (an `Organisation`) who administer learners: TAs and the people who add learners to cohorts, register courses, and generate reports. **No new roles.** Use the existing `site_admin`, `organisation_staff`, `instructor` and `ta`, and make their permissions work.
- **The capability list:** add, remove and deactivate learners (create accounts, handle an existing email); cohort membership add, remove and move; cohort and individual course registration and unregistration; cohort create, deactivate and delete; add, remove and scope educators; CSV import and multi-select bulk actions; dashboards on screen plus downloadable reports; resend invite or password setup.
- **The panel framework** stays bespoke (see the research in `panel-framework-tables-and-panel-api- upgrades-and-design/`) but becomes complete, documented (product docs + an `fls-dev` skill) and reusable by downstream projects. It must cover everything in `structure/idea.md` (sidebar sections, table, instance and base views, URL state for view, tab, panel and table state), a non-blocking right-hand **quick view** populated over HTMX, and **modals**, and it must clear the tech debt.
- **Reporting** builds on the existing cohort report machinery in `freedom_ls/reports/`: dashboards on screen **and** downloads.
- **Design:** `Educator LMS Interface Design/*.dc.html` mockups were made for the first-class theme. Use them as the guide, but with brand tokens, looking good in the default theme. Implement the design-system pieces as cotton components in the panel framework.
- **Build order:** one framework spec first, then feature specs in parallel.
- **Responsive:** usable on mobile. Heavy flows (CSV import, bulk) may be desktop-first.
- **Research findings** live in `research/` next to this map; tickets link to them.
- **Skills every session should consult:** `domain-glossary` (vocabulary: learner, registration, `Learner` vs `User`), `brand-guidelines`, `fls-dev:multi-tenant`. Use `fls-dev:template`, `ds:htmx`, `fls-dev:alpine-js` and `fls-dev:frontend-styling` for framework and UI tickets.

## Decisions so far

- [Comparable systems: learner-management actions](issues/01-comparable-systems-learner-management.md): every system pairs a reversible deactivate with a hard-to-reach delete, and FLS's `is_active` flags already support that. Candidate additions: reactivate, a staff-readable audit log, pending and revocable invites, roster export, learner detail editing (registration access dates flagged as close to deadlines).
- [Modal, drawer and URL-state patterns for HTMX](issues/02-htmx-modal-drawer-url-state-patterns.md): native `<dialog>` for both (drawer: `show()` on desktop and `showModal()` on mobile, swapped over htmx with `hx-sync` replace; modal: one shared, lazily loaded `showModal()` host with 422 form swaps and an `HX-Trigger` close). View, instance and tab go in the path; per-table prefixed query params are pushed (search replaces). Drawer and modal stay out of the URL. Turn off htmx's history cache, add `Vary`, and fix the history-restore fragment bug. No new dependencies.

## Not yet specified

- What the quick view shows for each entity (learner, cohort, course, report row), and which interactions open it rather than navigating.
- Permission-denied experience: what an educator sees when a role doesn't allow something (the old draft said hide, don't disable, and return 403 with a message; this needs revisiting against the new permission matrix).
- Downstream impact: educator URL changes, template overrides, settings, `upgrade_notes.md` flags for projects that extended the old interface.
- Testing strategy for a reusable panel framework (unit, Playwright, and a reference consumer).
- Dashboard query performance at realistic organisation sizes, and whether dashboards read live or from gathered report data.

## Out of scope

- Application review workflow and its UI (`application-review-ui`): its own effort. The new interface only mustn't block hosting a review inbox later.
- Deadlines: to be reworked separately later.
- Learner-facing communications: the quick view must be able to host them later, nothing more.
- Learner-facing interface, content authoring, content preview in a modal.
- The Django admin: left untouched.
- Redesigning the cohort report PDF pipeline: reused, not redesigned.
- New roles.
- Deliberate retake or progress reset.
