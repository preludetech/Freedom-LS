# Codebase research: educator-interface-13-staff-roles

Question: what in the existing codebase does this work touch, reuse or conflict with?
All paths relative to the repo root. Line numbers are as of branch `educator-interface-13-staff-roles` (9e8611c38).

## 1. Headline findings (read these first)

1. **`StaffMember` already exists.** `freedom_ls/learner_management/models.py:211` is a `SiteAwareModel`
   (`user`, `organisation`, `is_active`, `created_at`; constraint `unique_staff_member_per_organisation`
   on `(site, user, organisation)`). The answers say "a new model recording organisation staff
   membership, independent of roles". The model is not new; what is new is that it must stop being
   derived. Today it is a **gate**, created implicitly:
   - `ensure_staff_member` (`learner_management/utils.py:92`) is get-or-create and never reactivates an existing row.
   - A `post_save` receiver on `ObjectRoleAssignment` (`learner_management/signals.py:24`,
     `ensure_staff_member_for_active_grant`) creates the row for any active organisation or cohort grant.
   - `can()` (`learner_management/capabilities.py:167`, helper at `:135-160`) only counts an
     organisation- or cohort-level grant if the user holds an **active** `StaffMember` in that
     organisation. `is_active=False` suspends every grant without touching the assignments
     (`set_staff_member_active` in `learner_management/role_assignment.py:162`, UI: `DeactivateStaffMemberAction` /
     `ReactivateStaffMemberAction`, `educator_interface/actions.py:2349-2440`).
   - The spec must decide: **extend `StaffMember`** (the natural reading: a row with zero roles is
     already representable, since the row is independent of assignments) or add a second model. A
     second model would duplicate and conflict with the `Learner` counterpart design and the gate
     semantics. The model docstring literally describes it as "the counterpart of Learner".
   - **But the Staff list does not read `StaffMember`.** `staff_of(organisation)` and `staff_assignments`
     (`learner_management/queries.py:1096-1121`) are built from role-assignment rows only; the docstring
     says "a staff row only exists once a grant created it and nothing backfilled them". Every
     consumer (`StaffDataTable`, `_staff_member_param` at `actions.py:212` which 404s a non-staff `user`,
     `StaffRoleAction`, the intro callout in `StaffConfig.get_intro_context`) goes through `staff_of`. A
     staff member with no roles is therefore **invisible and un-actionable today**. Changing `staff_of`
     to include `StaffMember` rows (active, and inactive?) is the central change and ripples into
     `only_staff_member_is_viewer`, `staff_role_entries` (a row with no held assignments yields an empty
     role list; the cell template then shows only the member-level actions), and the "last organisation
     admin" logic.
   - "Removing staff membership deactivates all their roles, one audit entry per role" overlaps
     with, and differs from, the existing `DeactivateStaffMemberAction`, which flips `StaffMember.is_active`
     **without** touching role assignments (reversible by `ReactivateStaffMemberAction`, one
     `staff_member.deactivated` audit entry, `role_assignment.py:189`). The spec must say whether "remove
     staff membership" is a new action, a changed `DeactivateStaffMemberAction`, or deletion of the row (and what
     `PROTECT` on `organisation` and the unique constraint do on re-add). Reactivation after "deactivate all roles" would no
     longer "restore them exactly as they were" (docstring contract in the model).
2. **Names in the idea/answers do not match the code.**
   - There is no `AddMemberAction`. The action is `AddStaffMemberAction` (`actions.py:1710`) plus
     `AddStaffMemberToCohortAction` (`actions.py:2044`). Audit codes were renamed `member.*` ->
     `staff_member.*` by `audit_log/migrations/0005_rename_member_audit_codes.py`.
   - There is no `members_of` function anywhere in `freedom_ls/` (grep: none). The closest existing
     helpers are `staff_of`, `colleagues_of` (`queries.py:917`), `cohort_educators` (`queries.py:1124`),
     `educators_of`, `peers_of`, and the messaging policy's `recipients_for`. The org's learners come
     from active `Learner` rows (`learner_management/models.py`, `unique_learner_per_organisation`).
   - `lookup_user` is in `freedom_ls/accounts/account_setup.py:50`, **not** `learner_management/role_assignment.py`.
     It does `User._base_manager.filter(email__iexact=...)` across **all sites** and raises
     `EmailInUseOnAnotherSite` when the account is on a different site. So "anyone on the site, by full email"
     is correct; a person on another *site* is refused (`OTHER_SITE_MESSAGE`, `actions.py:1773`).
     `match_or_create_user` (`account_setup.py:64`) creates a pending account plus `EmailAddress`.
   - `role_assignment.py` holds `assign_role`, `deactivate_role`, `set_staff_member_active`, `grantable_roles`
     (+ `GrantableRole`), `is_widening`, `is_last_organisation_admin`, `is_site_level_admin`.

## 2. role_based_permissions

- `freedom_ls/role_based_permissions/roles.py`: `BASE_ROLES` (`SiteRolesConfig`) defines `site_admin`,
  `cohort_admin`, `cohort_viewer` (both `SCOPE_OBJECT`), `organisation_admin` (`SCOPE_OBJECT`, target is the Organisation),
  plus placeholders `system_admin`, `learner`, `observer`. The new **organisation staff viewer** role goes here. Its natural
  permission is `freedom_ls_learner_management.view_staffmember`, held today only by `site_admin` and
  `organisation_admin` (it is the Staff-section `view_capability`, `views.py:2017`). `cohort_admin` and `cohort_viewer` lack it.
  Roles are loaded via `role_based_permissions/loader.py` (`get_role_config(site.name)`) and registered in `registry.py`; downstream
  sites can override. A new role needs: entry in `BASE_ROLES`, registry/sync (`management/commands/sync_role_permissions.py`,
  `validate_role_permissions.py`), tests (`role_based_permissions/tests/test_roles.py`, `test_loader.py`, `test_registry.py`).
- A new role also implies a new custom permission `assign_<role>` (see `ASSIGN = "freedom_ls_role_based_permissions.assign_{role}"`,
  `role_assignment.py:45`) declared in `ObjectRoleAssignment.Meta.permissions` (`models.py:120`) => **a migration** in
  `role_based_permissions/migrations/` (existing: `0001_initial`, `0002_rename_educator_roles`, `0003_alter_objectroleassignment_options_and_more`).
  Existing perms: `assign_organisation_admin`, `assign_cohort_admin`, `assign_cohort_viewer` (and `assign_site_admin` on `SiteRoleAssignment`).
- `STAFF_ROLES` (imported from `learner_management/queries.py`) is the ordered tuple that drives the Staff table, `grantable_roles`,
  `offerable_roles`, `staff_assignments`, `staff_role_entries`, and the dialog's role cards. Adding the new role requires deciding its scope
  (organisation-level like `organisation_admin`, so `GrantableRole(role, None)` and `RoleEntry.cohorts == ()`) and updating the special cases that
  hard-code `role == "organisation_admin"`: `RoleEntry.scope/full_scope` (`educator_interface/staff.py:37,50`), `staff_role_entries`
  (`staff.py:70`), `grantable_roles` (`role_assignment.py:221`), `DeactivateRoleAction` (`actions.py:2161,2177,2192`),
  `AddStaffMemberAction._submit` (`:1915`), `ChangeCohortsAction` (excluded in `staff_roles.html:23`).
- `ObjectRoleAssignment` (`models.py:83`): `user`, GFK `target` (`content_type`+`object_id` CharField), `role`, `is_active`, `assigned_by`,
  unique on `(user, content_type, object_id, role)` => a person can hold `cohort_admin` on A and `cohort_viewer` on B, and org-wide + cohort roles together.
  Utilities in `role_based_permissions/utils.py`: `assign_object_role` (audit `role.assigned`, `:319`), `deactivate_object_role` (`role.deactivated`, `:349`),
  `delete_role_rows_for` (`role.removed`, `:60`), site-level variants. Audit entries are written inside these raw utilities, so any caller of
  `assign_role`/`deactivate_role` gets them. A role swap through those two calls already yields the two entries the answer wants, with the same
  actor (`assigned_by`/`deactivated_by`); no new verb. `role.changed` does not exist in `audit_log/actions.py:194-203` or the glossary verb table.
- Cohort role swap caveat: `deactivate_object_role` then `assign_object_role` on the same `(user, cohort)` with a different role touches two different rows (role is in the uniqueness key), fine. Re-adding a previously deactivated role reactivates the row (test at `role_based_permissions/tests/test_utils.py:998`: `["role.assigned","role.deactivated","role.assigned"]`).
- `is_widening` (`role_assignment.py:245`) compares permission sets by target; a role carrying only `view_staffmember` at org level interacts with it (it covers every cohort in the org as `organisation_key`), so the new org-level viewer role can make `is_widening` fire spuriously or hide a real widening: needs a test.

## 3. Add-staff dialog and the flow touched

- Action: `AddStaffMemberAction` (`educator_interface/actions.py:1710-2041`). Capability `freedom_ls_learner_management.add_staffmember` (org admin / site admin only);
  `AddStaffMemberToCohortAction` (`:2044`) overrides capability to `assign_cohort_viewer`, `renders_in_footer=False`, `offerable_roles=("cohort_admin","cohort_viewer")`, `_preset` = the cohort
  (this is what makes cohort admins able to add staff to their own cohort today, and why the answer "only org admins add *new* staff" is a constraint on the lookup/create path: today `_submit` -> `_perform` calls
  `match_or_create_user`, which creates a pending account + setup email for any unknown address for **both** actions, `actions.py:2032`).
- Steps: `step=email` (`StaffEmailForm`) -> `_lookup` -> `step=role` (`AddStaffMemberForm`, with `roles`, `cohorts`, `preset`, `new_account`) -> `step=confirmation` (`confirmed=1`) -> `_perform` (atomic: `match_or_create_user`, `assign_role` per target, `send_account_setup_email`). Template `educator_interface/templates/educator_interface/modal/add_staff_member.html` (one template, `step` switch; Alpine `memberRoleChooser`).
  Forms `StaffEmailForm`/`AddStaffMemberForm` live in `educator_interface/forms.py` (imported into actions.py; not re-read in full here).
- Needed changes this work implies: (a) Add role with preset person (skip email step) -> new action or `AddStaffMemberAction` parameter; (b) role step may submit with **no role** when an org admin adds new staff
  (today `role` is required and `_grantable` empty => `denied_response`; `is_offered` returns False when nothing grantable, `:1727`); the confirmation, `staff_member_state` ("new"/"missing"/"inactive"/"active", `:1673`) and `_entries_after` assume a role; (c) cohort admins must not be able to create or promote a learner
  into staff: needs a check in `_lookup/_submit` against a candidate set (their visible staff) rather than any email; the current dialog accepts any site email for anyone with the capability.
  Note `lookup_user` returns any site user including learners; "may never turn a learner into staff" is a new refusal (new `RefusalReason` in `role_based_permissions/exceptions.py`, message in `REFUSAL_MESSAGES`, `actions.py`), or a new check in the action.
- Refusal plumbing: `RoleChangeRefused`, `RefusalReason` (SELF, INACTIVE_USER, NOT_PERMITTED, LAST_ORGANISATION_ADMIN) in `role_based_permissions/exceptions.py`; `refusal_response` (`actions.py:1645`) maps NOT_PERMITTED to the 403 denied fragment, others to 422 in-dialog. 422 for HTMX errors is the project convention.

## 4. Existing row actions, Change cohorts, Staff table

- Staff table: `StaffDataTable` / `StaffConfig` (`educator_interface/views.py:~1940-2052`), columns "Staff member" (`data-table-cells/staff_member.html`) and "Roles" (`data-table-cells/staff_roles.html`). `StaffConfig.get_actions` registers `AddStaffMemberAction`, `DeactivateRoleAction`, `ChangeCohortsAction`, `DeactivateStaffMemberAction`, `ReactivateStaffMemberAction`. Cell context: `viewer`, `grantable_role_keys` (`grantable_roles_for(request)`, `actions.py:181`, cached on request). The Roles cell already renders one `<li>` per role entry with scope text (cohort names, shortened by `RoleEntry.scope`) and per-entry **Deactivate role** and **Change cohorts** triggers. The idea's "Roles cell lists one line per role per scope" is already substantially true; the new part is **Add role** per member row and org-level display.
- `DeactivateRoleAction` (`actions.py:2111`): deactivates one role entry on every cohort of the entry the grantor can reach (`_reach` = `cohorts_visible_to(..., capability=ASSIGN.format(role))`), or on the organisation; confirmation template `modal/deactivate_role_confirmation.html`; uses `ReasonMixin` (`ctx.reason`). Calls `deactivate_role` in a transaction. Cohort-scoped "Remove from cohort" from Settings is a single-cohort variant: reuse `deactivate_role(grantor, user, role, cohort, reason=...)`; there is no existing single-cohort variant of this action.
- `ChangeCohortsAction` (`actions.py:2217`): "Keep it" per the answers. Templates `modal/change_cohorts.html`. Offered only if `any(g.cohorts ...)`; excluded for `organisation_admin`. It already has the "Add role" capability partially (adding cohorts to a held role) but not adding a different role. Its `_plan` reads `grantable_roles_for`.
- `StaffRoleAction` base (`:2067`): `get_capability` -> `ASSIGN.format(role=...)` of the `role` param (falls back to `cohort_viewer`); target resolved through `_staff_member_param` -> `staff_of` (see headline 1).
- Self-protection: `_refuse_unless` refuses `grantor == user` (SELF) and `staff_roles.html` hides actions on the viewer's own row. The Settings-tab Change role must respect it too.

## 5. Cohort Settings panel Staff section (spec 12)

- `CohortSettingsPanel` (`educator_interface/views.py:1498`): `capability = change_cohort`; actions `EditCohortAction`, `AddStaffMemberToCohortAction`, `cohort_state_actions()`, `DeleteEmptyCohortAction`;
  `refresh_events = (COHORT_CHANGED, STAFF_CHANGED)`; context `educators = cohort_educators(cohort)`.
- Template `educator_interface/templates/educator_interface/panels/cohort_settings.html:17-34`: `<ul>` of `(user, role display name)` pairs with an avatar chip. **No per-row actions, no action triggers, no scope distinction.** The docstring says the context is "educators (user, role display name pairs)".
- `cohort_educators` (`learner_management/queries.py:1124`) returns `list[tuple[User, str]]` for **any role granting `VIEW_COHORT`**, via `_active_role_assignments(Cohort, roles_granting(VIEW_COHORT, site))` filtered to `object_id=cohort.pk`, and **only cohort-level assignments**, gated on active `StaffMember`. It does **not** currently include org-wide role holders (organisation_admin) or site admins; the answer says "the cohort Settings Staff section also lists people whose access comes from an organisation-wide role ... read-only there". Check against the spec 12 outcome: either the section already should list them (and the query was never extended) or this spec extends it. It returns display-name strings, not role keys or targets, so Change role / Remove from cohort rows need the role key and assignment scope: the tuple shape must change (and its callers/tests). Note the 3-tuple sort key (`educator[2]` is the role key) is discarded at the end.
- Tests: `educator_interface/tests/test_views.py` (around 3025 "Adding a staff member from the Settings tab writes a role.assigned..."; around 3711 audit assertion), `learner_management/tests/test_queries.py` for `cohort_educators`.
- Placement rule: `.claude/skills/brand-guidelines/visual.md` "Placement".

## 6. Audit log

- `freedom_ls/audit_log/actions.py:194-203` registers `role.assigned`, `role.deactivated`, `role.removed` (`_describe_role`, group "Staff and roles"), `staff_member.deactivated` and `staff_member.reactivated`. Reference: `freedom_ls/audit_log/README.md:96-106`.
- `record_entry(action, actor, target, target_label, organisation, subjects, reason)` in `freedom_ls/audit_log/writer.py`. Role entries are written by `role_based_permissions/utils.py::_record_role_change`, target = the object the role is on (cohort or organisation), subject = the user. A cohort History tab (`CohortHistoryPanel`, `views.py:1548`, `refresh_events = (COHORT_CHANGED, STAFF_CHANGED)`) shows role entries on the cohort because target is the cohort.
- If a new staff-membership add/remove is recorded, it needs new registered verbs. `staff_member.added` does not exist; verb vocabulary is constrained by the glossary table (`added` = "an association now exists", `deactivated` = `is_active` flip). Any new action code needs registering in `audit_log/actions.py` AND the README table AND the glossary, plus a data/migration check (see the rename migration `audit_log/migrations/0005`). "Removing staff membership deactivates every role, one audit entry per role": reuse `deactivate_role` per assignment in one `transaction.atomic()`; entries come free. Plus the existing `staff_member.deactivated` entry if the `StaffMember` row is flipped too.
- Audit tests to extend: `audit_log/tests/test_actions.py:103-113`, `learner_management/tests/test_role_assignment.py:588,669`, `educator_interface/tests/test_filters.py:536`.

## 7. Comms recipient picker (the model for as-you-type search)

- Template `freedom_ls/comms/templates/comms/partials/recipient_picker.html`: `<form id="recipient-search" hx-get="{{ search_url }}" hx-trigger="submit, input changed delay:300ms from:#recipient-q, search from:#recipient-q" hx-sync="this:replace" hx-target="#recipient-results" hx-select hx-swap="outerHTML">` with a `<c-panel-search-field>`, and `{% partialdef results inline %}` rendering `#recipient-results` (groups of `<c-panel-avatar-chip>` links; "Keep typing" hint under two characters; sr-only count).
- View: `comms/messaging_views.py:685 partial_recipient_search` renders `recipient_picker.html#results` with `_picker_context(request, term, in_pane)` (`:573`), calling `comms.messaging.search_recipients(...)` (`comms/messaging.py:576`). Its candidates default to `get_messaging_policy().recipients_for(sender, site)`; the function accepts a **`candidates` queryset** and `scope`, and `include_email` (the picker passes `False`).
  `PICKER_MIN_TERM_LENGTH = 2`, `PICKER_RESULT_LIMIT = 20`; results grouped (`RecipientSearch`, `RecipientGroup`). The picker is bound to the **messaging** recipient policy (`comms/messaging_policy.py`, `messaging_policy/policy.py` using `colleagues_of`). The staff-add search is a different candidate set and wants email matching and eight results, so reuse `search_recipients(candidates=..., include_email=True)` only if the limit (20 vs 8) and group semantics can be parameterised; otherwise a new sibling view and template in `educator_interface` using the same `hx-*` attributes. Do not make `educator_interface` import `comms` internals, and do not widen `recipients_for`.
- The security requirement ("never widens to every account on the site") means the candidate set must be built from `Learner` rows (`Learner.objects.filter(organisation=org, is_active=True)`) union `staff_of`/`StaffMember` of the org, and, for a cohort admin, the new organisation-staff-viewer visibility vs "staff of own cohorts". `search_recipients`'s result is "a name you may not message looks the same as a name that doesn't exist" - same property needed.
- Tests: `comms/tests/` (search, policy), `comms/tests/playwright/test_messaging_flow.py`.

## 8. Learner model and organisation relation

- `Learner(user, organisation, is_active)` unique per `(site, user, organisation)`; `ensure_learner` (`learner_management/utils.py`) get-or-creates and reactivates. A learner is never staff automatically: "a user may hold both a StaffMember and a Learner row in the same organisation" (model docstring). `DeactivateRoleAction._kept` already mentions "their learner access in this organisation". "Don't turn a learner into staff" means: a lookup that resolves to a user with an active `Learner` row in the org and no staff standing must be refused for cohort admins; org admins can (they hold `add_staffmember`).
- `Organisation` (`organisations/models.py`) is "a client inside a site, a grouping, not an isolation boundary" per the glossary (`docs/product/multi-tenancy-and-isolation.md`). `User` has `site` (site-aware user model).

## 9. Glossary check (`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`)

- Contains `StaffMember` only in the audit noun list (line 182: "`staff_member` (a `StaffMember`)"); the model table (Learner at line 63, Cohort 66, CohortMembership 67, Tenancy at 133-138) has **no `StaffMember` row** and no entries for "staff", "member", or `STAFF_ROLES`. The glossary says "member" is not a noun; "learner" is the model, and `removed` = deleted row, `deactivated` = `is_active` flip (lines 188-228). "Educator of a learner", "colleague", "peer" are coined terms tied to `queries.py`.
- Spec should add: a `StaffMember` row (gate semantics, and now "staff membership independent of roles"), "staff" and "organisation staff viewer" as a role, and use "organisation staff membership", not "member". The idea.md already uses "Staff section"; stay with `StaffMember` / "staff member" and avoid "member" alone (also avoid `AddMemberAction`, `members_of`, which are stale).

## 10. Tests that cover these paths (extend or will break)

- `freedom_ls/learner_management/tests/test_role_assignment.py` (assign/deactivate/set_staff_member_active, audit entries at :588, :669).
- `freedom_ls/learner_management/tests/test_capabilities.py`, `test_signals.py` (the `ensure_staff_member` receiver), `test_utils.py:307 TestEnsureStaffMember`, `test_queries.py` (staff_of, `cohort_educators`, `colleagues_of`, `active_organisation_admins`; 5+ tests that mutate `StaffMember` directly).
- `freedom_ls/educator_interface/tests/test_actions.py`, `test_views.py` (8 matching tests: staff table, Settings tab, add staff), `test_denied_experience.py`, `invariants/test_permission_matrix.py` (the permission matrix: a new role/permission will extend it and may fail it until the matrix includes the new role), `playwright/test_members_flow.py` (end-to-end staff add/deactivate/change cohorts).
- `freedom_ls/role_based_permissions/tests/` (test_roles, test_loader, test_registry, test_utils (audit), test_migrations (a new migration may need a test entry)).
- `freedom_ls/audit_log/tests/test_actions.py`.
- QA seeders referencing `StaffMember`: `freedom_ls/qa_helpers/management/commands/qa_create_{permissions,educator_polish,cohort_administration,bulk_operations,staff_administration,direct_messaging}_scenario.py` (the staff-administration one explicitly covers "no StaffMember row"/"inactive row"; new states "staff member with no roles" and the new viewer role want a seed there).
- Factories: `role_based_permissions/factories.py` (the role factory also writes the `StaffMember` gate row, per `qa_helpers/tests/.../test_qa_create_direct_messaging_scenario.py:84`).

## 11. Concurrent / neighbouring specs

- `spec_dd/2. in progress/` holds no other spec that touches staff, roles, the cohort Settings panel, the Add-staff dialog or the comms picker. Present: auto-run-tailwind-watch, content_snapshots, compliance-form-randomization, csv-formula-extra-triggers, design_educator-interface-bulk-action (bulk-actions on learner tables, may touch `educator_interface/actions.py` and `views.py` in unrelated regions), design_learner-interface-deadlines, downstream_bugs_oct_29, educator-interface-course-content-preview (touches `educator_interface/views.py`), in-app-feedback, learner-facing-ux-refinements, new-register-design-process, qa-boy-scout-throwaway, test-organisation-and-hygene-2-sdd-review-and-boy-scout. Merge-conflict risk is therefore limited to `views.py`/`actions.py` neighbours (not same functions).
- `spec_dd/1. next/`: `educator-interface-misc-polish`, `educator-interface-full-polish`, `audit-log-coverage-gaps` (may add audit verbs and cover role/staff paths: check for overlap before registering new verbs), `extract_panels_framework-*` (moves generic panel code; touching `PanelAction` base usage in `actions.py` could collide), `mega-qa` (QA seeds). Roadmap: `spec_dd/1. next/roadmap.md`.
- Predecessors (done): `spec_dd/3. done/2026-10-22_11:25_educator-interface-9-educator-administration/` (built Staff section, `StaffMember` gate, add/deactivate role, change cohorts: its `1. spec.md`, `2. plan.md`, `research_codebase.md` are the source of truth for contracts) and `spec_dd/3. done/2026-11-06_08:20_educator-interface-12-docs-and-polish/` (moved Educators into Settings, `upgrade_notes.md`/`effort_upgrade_notes.md` mention the permissions). Also `educator-interface-5-permissions` (capabilities and `can()`).
- Same-spec research siblings already in the dir: `research_known_complaints.md`, `research_reference_implementations.md`, `research_best_practices.md`.

## 12. Conflicts and risks, summarised

1. `StaffMember` exists with gate semantics; the "new model" answer should become "extend `StaffMember` as the source of truth for who is staff" and rewrite `staff_of`/`staff_assignments` consumers. Decide the interplay of `is_active=False` (suspend, reversible, roles untouched) with "remove membership deactivates all roles" (irreversible-ish): they are two different operations on the same row.
2. `cohort_educators` returns `(User, display_name)` pairs and omits org-wide holders; Settings needs richer rows (role key, scope, read-only flag) and likely org-level roles listed.
3. `AddStaffMemberToCohortAction` currently lets a cohort admin create **new accounts** and reach any site user by email; the answers forbid that. Needs a candidate-set restriction (staff visible to them; org staff viewer sees whole org staff) and a "never learner -> staff" refusal. The "Anyone on the site is still found by typing their full email" sentence in the idea conflicts with the answer for cohort admins; the spec should restrict full-email lookup to org admins.
4. Org-admin "add staff with no role" conflicts with `is_offered` / `_grantable`-driven gating, required `role` form field, and the confirmation/`staff_member_state` text.
5. A new org-level role breaks every `role == "organisation_admin"` special case (scope text, cohorts empty, Change cohorts exclusion, `DeactivateRoleAction`, `is_widening`) and needs a new `assign_*` permission + migration + `BASE_ROLES` + permission matrix tests.
6. Idea/answers use stale or wrong names (`AddMemberAction`, `members_of`, `lookup_user` in `role_assignment.py`); the spec should use `AddStaffMemberAction`, `staff_of`, `lookup_user` (accounts), `StaffMember`.
7. Picker reuse: `search_recipients` is tied to messaging policy and caps at 20 with `include_email=False` in the picker; the staff search needs email matching, 8 results, an organisation-scoped candidate set. A shared helper may be extracted but `comms` must not be made to depend on `educator_interface`.

status: ok · reason: complete
