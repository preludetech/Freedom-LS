# Educator permissions

Spec 5 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Decide, on the roles that already exist, who may do each thing the educator interface offers and at what scope. Then make the permission machinery able to answer those questions, and make the framework's permission hooks (from spec 1) ask them. Also decide what a person sees when the answer is no.

No new roles. The four that matter are `site_admin`, `organisation_staff`, `instructor` and `ta`, defined in `role_based_permissions/roles.py`. `system_admin`, `learner` and `observer` exist and are untouched.

## Why

Today the roles cannot express the interface. `instructor` and `ta` are identical (both carry only `view_cohort`). `organisation_staff` carries only `view_organisation`. The `FUTURE` note on `organisation_staff` in `roles.py` names two blockers that this spec has to remove: creation checks are made with no object, and guardian denies every objectless check; and role sync filters a role's permissions to the content type of the object it is assigned on, so a role on an `Organisation` cannot carry `learner_management.*` permissions at all. The same filter means it is unclear whether `site_admin`'s cohort permissions land anywhere when synced onto a `Site`.

Nothing decides who may assign which role. The assign and remove utilities exist and are called only from tests and QA helpers. There is no assignment UI; spec 9 builds one on this spec's rules.

The old draft said "hide, don't disable, and return 403 with a message". The current code returns 404 for organisation scope on purpose, to stop slug enumeration. Both are right for their cases and this spec writes down which case is which.

## What is settled

**The users.** People associated with an organisation who administer its learners. Organisation staff, instructors and TAs. Site admins see every organisation on the site.

**The matrix.** Written as a table in the spec, capability by role by scope. The starting position, from the decisions already taken in the roadmap:

| Capability | site_admin | organisation_staff | instructor | ta |
|---|---|---|---|---|
| See the organisation dashboard and reports | all organisations | own organisation | assigned cohorts only | assigned cohorts only |
| Add, deactivate, reactivate learners | yes | own organisation | no | no |
| Cohort membership add, remove, move | yes | own organisation | within assigned cohorts | no |
| Cohort and individual registration, unregistration | yes | own organisation | within assigned cohorts | no |
| Cohort create, edit, deactivate, delete when empty | yes | own organisation | no | no |
| CSV import, bulk actions | yes | own organisation | no | no |
| Add, remove, scope instructors and TAs | yes | own organisation | no | no |
| Grant organisation_staff or site_admin | yes | no | no | no |
| Read the audit log | yes | own organisation | no | no |
| Generate and download reports | yes | own organisation | assigned cohorts | assigned cohorts |

The spec confirms each row with the product owner and may narrow it. It does not widen `ta`, which is read-only by definition. A person may hold several roles; the union applies.

**Scope is the organisation for organisation roles and the cohort for cohort roles.** An instructor with a grant on one cohort sees that cohort's learners and may act on them there, and sees nothing else in the organisation. Cross-organisation is never possible for anyone but `site_admin`.

**Object-aware creation.** "May this user create a cohort in this organisation" is a question about the organisation, not about a non-existent cohort. The framework hook from spec 1 receives the request and the scope object, and this spec implements the check behind it. Guardian's objectless deny is worked around by asking the question of the organisation or the cohort, never of nothing.

**The content-type filter.** Either the sync learns that a role on an organisation implies permissions on the things inside it, or the interface stops asking guardian about model permission strings for organisation roles and asks a small capability layer instead, which consults the role assignments directly. The spec chooses after reading `role_based_permissions/utils.py` and `learner_management/queries.py`. The `organisations_accessible_to`, `cohorts_visible_to` and `learners_visible_to` helpers stay the way the interface scopes what is listed. Whatever is chosen, a downstream project's `FREEDOMLS_PERMISSIONS_MODULES` override keeps working.

**Who may assign.** Site admins assign anything. Organisation staff assign `instructor` and `ta` on cohorts in their organisation and remove them. Nobody assigns to themselves. Removing the last `site_admin` on a site is refused.

**The denied experience.**

- Organisation scope: an organisation slug the user cannot reach is a 404, as now, and so is an instance outside their scope.
- An action they can see but may not perform (their role changed while the page was open): 403 with a fragment saying what happened, why, and who to ask. For htmx requests the fragment renders where the form was.
- Controls the user may not use are not rendered. Each role's view is a complete interface, not a greyed-out admin.
- Panels and tabs use the spec 1 hook to hide themselves per role. Lists use the visibility helpers to filter rows.

**Tests.** A matrix test that iterates roles and capabilities against the table above, so the table in the spec and the behaviour cannot drift apart. The existing test that asserts every `ListViewConfig` either authorises or declares an exemption stays, and the courses exemption is expected to be gone by spec 6.

## Open until the spec

- Whether `site_admin`'s cohort permissions currently reach guardian at all. Verify by test before designing around it.
- Permission strings versus a capability layer. Read the code, then decide; the matrix must be expressible either way.
- Whether `instructor` should be able to add learners to the organisation (not only to their cohorts). Default no.

## Out of scope

- The assignment UI (spec 9). The audit log (spec 11).
- New roles, per-site custom roles, the "roles and permissions" screen in the mockups with its "create role" button.
- Anything about learner-facing permissions.

## Resources

- `research_permission_ux_patterns.md`, how other systems show and explain permissions, and the case for hide-not-disable.
- `spec_dd/3. done/2026-03-09_11:26_role_based_permission_system_foundations/`, where the roles came from, including `research_lms_permission_models.md`.
- `spec_dd/3. done/2026-08-21_09:09_organisations/`, which added the organisation access path and the deny-by-default instance check.
- `../educator-interface-full-polish/comparable-systems-learner-management.md`, section 6 on scoping educators to groups.
- Skills: `fls-dev:multi-tenant`, `fls-dev:testing`, `domain-glossary` (the word "grant" means a role or object permission; course access is "registration").
