# Educator administration

Spec 9 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

An educators section in the educator interface. It lists the people who hold a role in this organisation, lets the right people add an educator (an existing user or a new account), pick a role, scope it to cohorts, change the scope, and remove the role. It shows what each role means in plain words and asks for confirmation before anything that raises or removes someone's access.

## Why

There is no way to give someone an educator role except a shell or a QA helper. The assign and remove utilities exist in `role_based_permissions`, and the assignment models carry `assigned_by` and `is_active`, but nothing calls them from a screen. Spec 5 decides who may assign what; this spec puts that behind a form.

## What is settled

**Who may do this.** From decision 2 of the decisions already taken in the roadmap, and the spec 5 matrix. Organisation staff and site admins add, remove and re-scope instructors and TAs within the organisation. Only site admins grant `organisation_staff` or `site_admin`. Nobody changes their own roles. The last site admin cannot be removed.

**List.** One row per person with any role in this organisation: name, email, roles with their scope (the organisation, or the cohorts), added by, added on. Search by name or email. Filter by role.

**Add.** Email first. An existing user is matched case-insensitively; a new address gets an account through spec 7's shared creation path, with the same setup email. Then a role from the ones the current user may grant, with a one-sentence description under each. For `instructor` and `ta`, a cohort picker limited to this organisation's active cohorts. Confirmation restates what the person will be able to do.

**Role descriptions.** Written for a school administrator, not a developer. The spec drafts them from the spec 5 matrix and they are the same strings used in the audit log and the product docs. Site admin: full access to every organisation on this site. Organisation staff: manage learners, cohorts, courses and educators in this organisation. Instructor: manage learners and their progress in assigned cohorts. TA: view learners and progress in assigned cohorts.

**Change scope.** Add or remove cohorts from an instructor's or TA's grant without removing the role. Confirmation on removal.

**Remove.** Deactivates the assignment (the models already do this; nothing is deleted) and drops the guardian permissions through the existing sync. Confirmation names what the person loses.

**Escalation.** Any change that widens access beyond what the person had gets an explicit confirmation naming the widening.

**Educator who is also a learner.** Allowed. A person can hold a `Learner` row and an educator role in the same organisation. The educator interface treats them by their role; the learner interface by their `Learner`. The list shows a small "also a learner" marker so it is not a surprise.

**Cohort deletion and orphan grants.** When spec 6 deletes an empty cohort, its `ObjectRoleAssignment` rows and guardian permissions would be orphaned because the target is a generic key. This spec adds the cleanup, or spec 6 does and this spec tests it; decide by who lands first.

**The cohort page.** The instructors block on the cohort overview (spec 6 renders it read-only) gains an "add" action here for those allowed.

**Permission-denied.** A person whose role was removed while they had the interface open sees the spec 5 denied experience on their next action.

**Docs.** An "Educators and roles" section in `docs/product/educator-interface.md` with the role descriptions.

## Open until the spec

- The final role description copy, with the `brand-guidelines` voice.
- Whether the mockup's "roles and permissions" screen survives as a read-only page listing the four roles and what they do, or the descriptions live only inline. Default: inline plus one help paragraph.
- Whether an educator's own row is shown with actions disabled or hidden. The house rule is hide, but hiding your own row entirely is confusing. Probably show without actions and say why.

## Out of scope

- New roles, custom roles, per-permission editing.
- Site-level administration of organisations.
- Anything the Django admin does with `SystemRoleAssignment`.

## Resources

- `../educator-interface-5-permissions/idea.md` and its research file.
- `../educator-interface-full-polish/comparable-systems-learner-management.md`, the staff role notes per system in the appendices.
- Mockup `Educator Cohorts and Admin.dc.html` screen 06 and mobile M09, for layout only; the custom roles they show are out of scope.
- Skills: `fls-dev:multi-tenant`, `brand-guidelines`, `fls-dev:testing`.
