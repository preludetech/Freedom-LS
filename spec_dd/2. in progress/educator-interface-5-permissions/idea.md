# Educator permissions

Spec 5 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Decide who may do each thing the educator interface offers and at what scope, and rename the existing roles so their names say that. Build a capability layer that answers those questions, and make the framework's permission hooks from spec 1 ask it. Record which educators belong to which organisation, so that leaving an organisation switches their grants off and rejoining switches them back on. Decide who may assign which role, and what a person sees when the answer is no.

No new roles. The four that matter are the ones defined in `role_based_permissions/roles.py` as `site_admin`, `organisation_staff`, `instructor` and `ta`. Three of them are renamed below. `system_admin`, `learner` and `observer` exist and are untouched.

## Why

The roles cannot express the interface, and several of the checks that exist cannot pass:

- `instructor` and `ta` are identical: both carry only `view_cohort`. `organisation_staff` carries only `view_organisation`.
- Role sync keeps only the permissions whose app label matches the assignment target's content type. A role on an `Organisation` can carry nothing from `learner_management`. `site_admin`'s four cohort permissions are dropped every time they sync onto a `Site`, so a site admin has no cohort grants in guardian and works today only through superuser bypass. No test notices, because `TestSiteRoleFunctions` asserts on the assignment row, not on `has_perm`.
- `CreateCohortAction` inherits `CreateInstanceAction.has_permission`, which asks `has_perm("…add_cohort")` with no object. Guardian denies every objectless check, so only a superuser can create a cohort.
- The `_visible_to` helpers in `learner_management/queries.py` already work around the content-type filter by hand: an organisation role implies every cohort in it, done as a Python branch rather than by guardian.
- Nothing enforces who may assign what. The assign and remove utilities take a grantor but never check that the grantor may touch the target. `remove_site_role` does not refuse removing the last `site_admin`. The utilities are called only from tests and QA helpers.
- Nothing records that an educator belongs to an organisation. `Learner` is the only (user, organisation) association, and it exists for enrolment. An instructor's only link to an organisation is a grant on one of its cohorts.
- A denied action returns a bare `HttpResponse(status=403)` from `_handle_action`. htmx 2 does not swap 4xx responses by default, so the click silently does nothing.
- Two course-detail panels leak rows to cohort-scoped educators. `CourseLearnerRegistrationDataTable` and `CourseCohortRegistrationDataTable` filter by organisation only. `notes_from_spec_1_review.md` describes both, and both are still on `main`.

The code state behind each point is in `research_current_permission_machinery.md`.

## What is settled

**The users.** People associated with an organisation who administer its learners: organisation admins, cohort admins and cohort viewers. Site admins see every organisation on the site.

**The names.** A role name is its scope plus its level: `site_admin`, `organisation_admin`, `cohort_admin`, `cohort_viewer`. An admin may do everything the interface offers at that scope. A viewer may see everything at that scope and change nothing. The old names said what a person's job was, not what the role lets them do, and `instructor` and `ta` looked interchangeable when the difference is write versus read.

| Old key | New key | Display name | One-line description |
|---|---|---|---|
| `site_admin` | `site_admin` | Site admin | Everything, in every organisation on the site. |
| `organisation_staff` | `organisation_admin` | Organisation admin | Everything in one organisation, including who else administers it. |
| `instructor` | `cohort_admin` | Cohort admin | Manages who is in a cohort and what it is registered for. |
| `ta` | `cohort_viewer` | Cohort viewer | Sees a cohort and its reports. Changes nothing. |

"Viewer" rather than "read only" because it names a person, works as an identifier and a display name, and is the word other systems use for the same level. "Read-only" is the description. There is no organisation viewer; the roadmap says no new roles, and the scheme leaves the slot open if one is ever wanted. `observer` stays what it is, a learner-facing role, and is not the same thing as a cohort viewer.

Renaming has a cost, and the spec carries it:

- `SiteRoleAssignment.role` and `ObjectRoleAssignment.role` are plain strings, so a data migration rewrites the existing rows from the old keys to the new ones.
- Downstream role configs that reference the old keys, including any `inherits: "ta"` variant, break. The upgrade notes say so and give the mapping. `config/role_based_permissions/demodev.py` has the in-repo example, `senior_ta`.
- The `role_based_permissions` README, the factories, the QA commands and the tests follow the rename.
- `lti_role` is a per-role field and is unaffected. The LTI vocabulary can still map `cohort_admin` to Instructor and `cohort_viewer` to TeachingAssistant when LTI arrives.
- Roadmap decision 2 and the scope lines for specs 5 and 9 use the old words and the old assignment rule. Amend the roadmap once this idea is confirmed.

**The matrix.** The spec writes it as a table, capability by role by scope:

| Capability | site_admin | organisation_admin | cohort_admin | cohort_viewer |
|---|---|---|---|---|
| See the organisation dashboard and reports | all organisations | own organisation | assigned cohorts only | assigned cohorts only |
| Add, deactivate, reactivate learners | yes | own organisation | no | no |
| Cohort membership add, remove, move | yes | own organisation | within assigned cohorts; a move needs a grant on both cohorts | no |
| Cohort and individual registration, unregistration | yes | own organisation | within assigned cohorts | no |
| Cohort create, edit, deactivate, delete when empty | yes | own organisation | no | no |
| CSV import, bulk actions | yes | own organisation | no | no |
| Add, remove, scope cohort admins and cohort viewers | yes | own organisation | no | no |
| Add and remove organisation admins | yes | own organisation | no | no |
| Grant or remove site_admin | yes | no | no | no |
| Generate and download reports | yes | own organisation | assigned cohorts | assigned cohorts |

The product owner has confirmed these rows. A cohort admin adds existing organisation learners to their cohorts and never creates a learner in the organisation. A cohort viewer may download the PDF report and the roster CSV for assigned cohorts, since they show only what the viewer already sees on screen. `cohort_viewer` is read-only by definition and is never widened. A person may hold several roles; the union applies.

The matrix covers what specs 6 to 10 build. A capability that does not exist yet has no row. When a later spec builds one, that spec adds the row and the check together; spec 11 adds the audit log row. The completeness test below is what makes a missing row fail loudly rather than silently deny.

One wrinkle in the name "cohort admin": the matrix does not let a cohort admin edit the cohort itself, only its membership and registrations. The description above says so. Whether a cohort admin may edit the name and description of a cohort they administer is open until the spec, with the default being no.

**Scope is the organisation for organisation roles and the cohort for cohort roles.** A cohort admin with a grant on one cohort sees that cohort's learners and may act on them there, and sees nothing else in the organisation. Nobody but `site_admin` can act across organisations.

**Organisation association.** A new (user, organisation, `is_active`) row records that an educator belongs to an organisation. It is the educator's counterpart of `Learner`. Its working name is `Educator`, a coined word that is free in both the code and the glossary. The spec settles the name and the app. Every check on something an organisation owns requires both:

1. the capability, from the person's grants, and
2. an active association with that organisation.

Deactivating the association switches off every grant the person holds in that organisation without touching the grants. Reactivating it restores exactly what they had, with no set-up from scratch. `site_admin` needs no association. Whoever may add and remove cohort admins and cohort viewers in an organisation may add and remove the association. Spec 9 builds the screen. Existing `organisation_staff`, `instructor` and `ta` grants must keep working after the upgrade under their new names, so current holders get an association.

**A capability layer, not more permission strings.** One function answers "may this user do this capability on this organisation, cohort or learner". It reads role assignments, the association and the site's role config live. It walks from a learner or cohort up to the organisation and the site, so a grant on a container covers what is inside it without writing guardian rows onto children. The consequences:

- A cohort created later is covered at once, with nothing to re-sync.
- A downstream `FREEDOMLS_PERMISSIONS_MODULES` override takes effect on the next check, because the role config is read live.
- Guardian stays for grants held directly on the object being checked, such as a cohort admin's grant on a cohort.

The `_visible_to` helpers stay the way the interface scopes what is listed. They become the queryset twin of the capability function, built from the same assignments and the same association, so a list and a single-object check cannot disagree. `research_scoped_capability_models.md` has the prior art and the case against copying grants onto children.

**Object-aware creation.** "May this user create a cohort in this organisation" is asked of the organisation, never of nothing. The framework hook receives the request and the scope object. `CreateInstanceAction`'s objectless `has_perm` goes.

**Who may assign.** Assigning is a capability like any other and is checked by the same layer, not left to spec 9's views. An admin may hand out their own level and every level below it within their scope, and nothing above it. This replaces roadmap decision 2, which reserved organisation grants to site admins.

| Grantor | May assign and remove | Where |
|---|---|---|
| `site_admin` | `site_admin`, `organisation_admin`, `cohort_admin`, `cohort_viewer` | anywhere on the site |
| `organisation_admin` | `organisation_admin`, `cohort_admin`, `cohort_viewer` | their own organisation, and cohorts in it |
| `cohort_admin`, `cohort_viewer` | nothing | |

- Nobody assigns or removes their own grants.
- Removing the last `site_admin` on a site is refused. An organisation admin removing the last `organisation_admin` in their organisation is refused; a site admin may do it, since site admins can always reach the organisation. The count and the removal happen under a row lock, so two simultaneous removals cannot both pass.
- The target must be an active user.
- Deactivating a cohort leaves the grants on it intact. What an inactive cohort still allows is spec 6's call.

`research_role_assignment_rules.md` has the prior art and the edge cases behind these rules.

**The denied experience.**

- An organisation, cohort or learner outside the user's scope is a 404, so slugs and ids cannot be enumerated. That includes a cohort a cohort admin has no grant on, inside an organisation they can otherwise see.
- An action they can see but may no longer perform returns 403 with a fragment that says what happened, why, and who to ask. For htmx requests the fragment renders where the form was. It goes through the existing `htmx:beforeSwap` listener in `alpine-components.js`, which already force-swaps 422s. There is no new htmx extension and no global `responseHandling` change. A full-page 403 uses the existing `403.html`.
- "Who to ask" names a role, such as an organisation admin, and names a person only when the user can already see that organisation's educators. The message does not distinguish "your role changed" from "you never had it".
- Controls the user may not use are not rendered. Each role's view is a complete interface, not a greyed-out admin.
- Panels and tabs use the spec 1 hook to hide themselves per role. Lists use the visibility helpers to filter rows, and that includes the two course-detail panels above.

`research_htmx_denied_responses.md` covers the htmx mechanics and how errors behave in the drawer and the dialog. Spec 3 describes error rendering in the drawer. Whichever of 3 and 5 is specced second cross-references the other, so a 403 shows "who to ask" instead of a retry button.

**Tests.** The matrix is transcribed once as data in a test and reviewed against the spec's table. It is not generated from the markdown and not parsed from it. The test parametrises over role, capability and scope relation: own, other cohort, other organisation, other site. A completeness check fails when the interface asks about a capability the matrix lacks. Endpoint tests cover one case per denial shape, not one per cell. The shapes are 404, the 403 fragment and the hidden control. The existing test that asserts every `ListViewConfig` either authorises or declares an exemption stays, and the courses exemption is expected to be gone by spec 6. `research_permission_matrix_testing.md` works through the test shape and its cost.

## Open until the spec

- The association's name, app and fields, and how it relates to `Learner` for a person who is both.
- Whether a cohort admin may edit the name and description of a cohort they administer. Default no.
- What becomes of role sync into guardian for organisation and site roles once the capability layer answers those checks. At minimum, `site_admin`'s cohort strings stop pretending to do anything.

## Out of scope

- The assignment UI, including adding and removing the organisation association (spec 9). The audit log (spec 11).
- New roles, per-site custom roles, the "roles and permissions" screen in the mockups with its "create role" button.
- Anything about learner-facing permissions.

## Resources

- `research_current_permission_machinery.md`: the role config, sync, `_visible_to` helpers and spec 1 hooks as they stand.
- `research_scoped_capability_models.md`: Moodle, Canvas, django-rules and Zanzibar-style inheritance, and the capability layer recommendation.
- `research_role_assignment_rules.md`: who may grant what elsewhere, last-admin rules, and edge cases.
- `research_htmx_denied_responses.md`: htmx 2 error swapping, the repo's existing listener, 403 versus 404.
- `research_permission_matrix_testing.md`: matrix-as-data tests, completeness checks, endpoint-test budget.
- `research_permission_ux_patterns.md`: how other systems show and explain permissions, and the case for hide-not-disable.
- `notes_from_spec_1_review.md`: the two course-detail row-visibility gaps.
- `spec_dd/3. done/2026-03-09_11:26_role_based_permission_system_foundations/`, where the roles came from, including `research_lms_permission_models.md`.
- `spec_dd/3. done/2026-08-21_09:09_organisations/`, which added the organisation access path and the deny-by-default instance check.
- `../educator-interface-full-polish/comparable-systems-learner-management.md`, section 6 on scoping educators to groups.
- Skills: `fls-dev:multi-tenant`, `fls-dev:testing`, `ds:htmx`, `domain-glossary` ("grant" means a role or object permission; course access is "registration").
