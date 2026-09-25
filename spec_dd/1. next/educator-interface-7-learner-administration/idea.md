# Learner administration

Spec 7 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The learners section, complete. Add a learner to the organisation, whether or not the person already has an account. List and detail. Deactivate and reactivate. Add to a cohort, remove from one, move between two. Register for and unregister from a course individually. Resend the account setup email. The learners tab on the cohort detail page, and every membership action from either side.

## Why

Cohort membership is editable only in the Django admin. There is no way to register or unregister an individual learner anywhere. Creating an account for someone else means the admin's user form with a typed password and no email. Every routine task a school administrator does needs a superuser or a developer.

The vocabulary matters here and the `domain-glossary` skill has it. A `Learner` is a person's association with one organisation, not a profile and not a synonym for `User`. `Learner.is_active=False` means removed from the organisation and nothing cascades. `ensure_learner` is the only way to make one. "Registration" is the word for course access, and a membership is not a registration; it grants access through the cohort's registrations.

## What is settled

**Adding a learner.** One form. It takes one or more email addresses and optional names. For each address, an existing `User` on the site is matched case-insensitively and joined to this organisation through `ensure_learner`, which also reactivates a removed learner. Existing details are never overwritten. A new address gets a `User` with no usable password and an account setup email carrying a password-set link built on allauth's reset token. The form reports per address what happened. Optionally the form takes a cohort, so "add to cohort" and "add to organisation" are one step when wanted. The same code path serves spec 8's CSV import and spec 9's educator creation, so it lives in `learner_management` or `accounts`, not in a view.

**Pending state.** Derived, no new model. A learner is pending when their user was created by staff and has never logged in. The list shows it as a status. "Resend setup email" is available while pending and is rate limited. "Revoke" is deactivate. If the derived state proves unreliable, the spec may add one nullable timestamp to `Learner`; it may not add an invitation model.

**List.** Name, email, status (active, pending, removed), cohorts, courses with progress, last active. Search across name and email. Filters: status (active and pending by default), cohort, course. Row selection present for spec 8. A learner cell shared by every table, with the quick view trigger from spec 3.

**Detail.** Header with name, email, status and actions. Tabs: overview (details, cohorts with join dates, registrations with source and status), courses and progress (per registration, progress percentage, last activity; spec 10 deepens this), history (empty until spec 11). Editing a learner's name or email is `site_admin` only, because `User` is shared across organisations; for everyone else it stays in the admin. Decide in the spec whether even `site_admin` gets it here.

**Deactivate and reactivate.** Deactivate sets `Learner.is_active` false. Registrations, memberships and progress stay. The confirmation says the person loses access to this organisation's courses and keeps everything if reactivated. Reactivate reverses it. No hard delete here.

**Membership.** Add to a cohort from the learner's page or from the cohort's learners tab (search existing learners in the organisation, or add a new one inline through the same form). Remove from a cohort deletes the `CohortMembership` row, which is what the model supports; the confirmation says which courses the learner loses access to and that progress is kept. Move is one transaction: remove from one cohort, add to another in the same organisation, with the same statement of consequences.

**The move and the course progress record.** This is the open question that matters most, and the spec resolves it before anything else. Creating the destination membership mints a fresh course progress record under the destination cohort's registration, and `learner_for_course` resolves to that one, so the learner would resume at 0% for a course both cohorts grant. The old record is kept but not used. Options weighed in the old draft: re-point the old record's `cohort_registration` at the destination registration inside the move; teach the resolver to prefer the record with progress; or accept a fresh pass and say so. The done progress-tracking spec deferred exactly this to here. Whatever is chosen, the educator sees what will happen before confirming, and `learner_management` does not import `learner_progress` at runtime.

**Individual registration.** Register a learner for a course from their page; unregister sets `is_active` false on the `LearnerCourseRegistration` and re-register reactivates it. The confirmation notes whether a cohort registration still grants access.

**Webhooks.** `course.registered` fires today only for a new individual registration. The spec decides which events cohort registration, membership add, remove and move, deactivate and unregister should fire, names them in `base/webhook_event_types.py`, and fires them through `fire_webhook_event`. Spec 6 and 8 use the same names.

**Permissions.** From the spec 5 matrix. Instructors act within assigned cohorts, TAs read.

**Docs.** The learners section of `docs/product/educator-interface.md` rewritten. Upgrade notes flag any new setting (email subject, rate limit) and any new event type.

## Open until the spec

- The move and the progress record, above.
- Name and email editing for `site_admin`.
- Whether the setup email is a new allauth-adjacent email template in `accounts` or a plain Django email; either way it must be site-aware and themeable.
- The list of webhook events.

## Out of scope

- CSV import and bulk actions (spec 8). Educator roles (spec 9). Progress detail beyond a percentage (spec 10). Audit history (spec 11).
- Account merge, log in as a learner, cross-organisation moves.
- Deliberate retakes or progress resets.

## Resources

- `research_lms_educator_ux.md`, how educators expect learner management to feel.
- `../educator-interface-full-polish/comparable-systems-learner-management.md`, sections 6 and 7, and the per-system appendices for invitation and roster behaviour.
- `spec_dd/3. done/2026-08-23_17:20_learners-associated-with-organisations/`, where `Learner` came from, and its `research_learner_lifecycle.md`.
- `spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/decision.md`, the resolution rule the move has to live with.
- Mockups: `Educator Learners.dc.html` screens 02 and 03, mobile M03 to M05.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:registration` (for how accounts and consent work today), `fls-dev:testing`.
