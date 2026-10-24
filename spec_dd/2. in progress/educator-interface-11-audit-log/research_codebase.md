# Research: codebase (what the audit log touches, reuses and conflicts with)

Scope: `educator-interface-11-audit-log`. All paths are relative to the repo root. Line numbers are from
this worktree at commit `dcf91ef8`. Specs 6, 7 and 9 are done and live under `spec_dd/3. done/` in
date-prefixed directories (for example `2026-10-20_13:37_educator-interface-7-learner-administration`);
spec 8 is in progress and has only `idea.md` and `todo.md` (no spec, no plan, no code on this branch).

## 1. Headline findings (read these first)

1. **The educator-interface actions do not carry an actor.** `freedom_ls/learner_management/learner_actions.py`
   (`deactivate_learner`, `reactivate_learner`, `add_to_cohort`, `remove_from_cohort`,
   `move_between_cohorts`, `register_for_course`, `unregister_from_course`, `add_learners`) and
   `learner_management/utils.py` (`register_cohort_for_course`, `unregister_cohort_from_course`) take no user.
   Only the role seam (`role_assignment.py`: `assign_role(grantor, ...)`, `remove_role(grantor, ...)`,
   `set_organisation_member_active(actor, ...)`) does. Writing "who" means adding an `actor` parameter to
   these functions (or writing from the panel action, outside the transaction the service opens). Their
   other callers are `qa_helpers` commands (`qa_toggle_cohort_learner.py:128,133`,
   `qa_create_learner_administration_scenario.py:200`) that have no actor.
2. **Several actions have no service function at all.** Cohort create, edit, delete and cohort
   activate/deactivate, and the learner name edit, are done inline in panel action classes or in the generic
   `panel_framework/actions.py` classes (`CreateInstanceAction.form_valid` line 275, `EditAction.form_valid`
   line 330, `DeleteAction.handle_submit` line 440). None runs in a transaction of its own and the project
   does not set `ATOMIC_REQUESTS` (no match anywhere). "Writing happens inside the action's transaction" needs
   a `transaction.atomic()` added around these, or a hook in the generic classes.
3. **`SystemRoleAssignment` is not site-aware** (`role_based_permissions/models.py:9-44`, plain `Model`, BigAutoField).
   A site-aware, `site`-non-null audit model cannot hold the system-role TODOs (`utils.py:399,417`) without either
   a nullable `site` or a rule (skip, or stamp with the current site). `assign_site_role` entries have a site but
   no organisation.
4. **The model's `organisation` must be nullable** and resolved by a rule: an `ObjectRoleAssignment` target is an
   open set (`object_id` is a `CharField`, `models.py:95`), so the target may be an `Organisation`, a `Cohort`, or
   (README says "e.g. a Course") something with no organisation.
5. **The history tab slot already exists on the learner page and is missing on the cohort page.**
   `LearnerHistoryPanel` (`educator_interface/views.py:695-699`) with an empty-state template; `CohortTabSet`
   (`views.py:963-970`) has overview, learners, courses, settings and no history.
6. **No permission row, no `Meta.permissions`, no migration is needed if the capability is the model's built-in
   `view_<model>` permission** (auto-created). Custom (non-CRUD) capabilities need `Meta.permissions` plus a
   migration (precedent: `learner_management/models.py:49,83`, `role_based_permissions/models.py:77,120-127`).
7. **GDPR and the append-only rule collide** via `USER_ERASURE_CASCADE_MODELS` (`accounts/admin.py:20`) and by the
   stored label of a target (a learner's name or email). See section 11.

## 2. Role utilities: the six `# TODO: AuditLog entry` comments

File `freedom_ls/role_based_permissions/utils.py`. The comments must stay until the TODO is completed (CLAUDE.md).
Spec 9's plan (`3. done/.../educator-interface-9-educator-administration/2. plan.md:36`) lists them as a
`code-comments` rule: they stay.

| Line | Function | Signature | Actor param | Transaction | Notes for the entry |
|---|---|---|---|---|---|
| 271 | `assign_object_role` | `(user, target: SiteAwareModelBase, role, assigned_by: User \| None = None) -> ObjectRoleAssignment` (243-248) | `assigned_by` | none | `get_or_create` then `_refresh_assignment` (217-240); `created` flag and `fields_to_update` tell new vs reactivated vs no-op. Then `sync_user_object_permissions` (itself atomic, 202). Entry is at the very end, after the sync. |
| 294 | `remove_object_role` | `(user, target, role, removed_by: User \| None = None) -> None` (275-280) | `removed_by` | none | Uses `.filter(...).update(is_active=False, updated_at=...)` (287-292). The `update()` count is discarded, so "was anything actually active" is unknown today. An entry on a no-op removal would be wrong. |
| 328 | `assign_site_role` | `(user, role, assigned_by=None, site=None) -> SiteRoleAssignment` (297-302) | `assigned_by` | none | Site defaults to current site (`Site.objects.get_current()`, 311). No organisation. |
| 373 | `remove_site_role` | `(user, role, site=None, removed_by=None) -> None` (332-337) | `removed_by` (docstring 346: "for future audit logging") | `transaction.atomic()` wraps the last-site-admin guard and the update (351-371), but the sync and the TODO sit **outside** it (372-373) | Raises `RoleChangeRefused(LAST_SITE_ADMIN)` before the update. The entry should sit inside the atomic block. |
| 399 | `assign_system_role` | `(user, role, assigned_by=None) -> SystemRoleAssignment` (376-380) | `assigned_by` | none | No site, no organisation (finding 3). |
| 417 | `remove_system_role` | `(user, role, removed_by=None) -> None` (403-407) | `removed_by` | none | Same. |

Callers:

- Production: only `learner_management/role_assignment.py` (`assign_role` lines 117-125, `remove_role` 128-149),
  which passes `grantor` as `assigned_by`/`removed_by` and already runs `remove_object_role` inside
  `transaction.atomic()` (142-149). `assign_role` does not open a transaction, and nothing wraps
  `_refuse_unless` + `assign_*` together, but `AddMemberAction._perform` (`educator_interface/actions.py:1629`) and
  `RemoveRoleAction.handle_submit` (1789) and `ChangeCohortsAction.handle_submit` (1893) wrap loops in
  `transaction.atomic()`.
- The module docstring of `role_assignment.py` (1-9) says the raw utilities "stay available for QA commands,
  fixtures and the Django admin" and bypass the checks. So a raw call has `assigned_by=None`; a role-utility entry
  with a null actor is the normal case for fixtures, tests (dozens of `assign_object_role(user, target, role)` calls in
  `learner_management/tests`, `reports/tests`, `scenario_world.py:175-192`, `test_permission_matrix.py:374-383`) and
  `qa_helpers`. Writing an entry from every raw call adds a row per fixture grant. The spec must decide whether a
  null-actor grant is logged (as a system action) or skipped.
- Side effect to know about: `post_save` on `ObjectRoleAssignment` (`learner_management/signals.py:24-44`) creates an
  `OrganisationMember` row (`ensure_organisation_member`, `learner_management/utils.py:87-114`) for any active
  organisation or cohort grant. That implicit member creation has no entry of its own; it is covered by the role
  entry.
- Raw role rows delete on cohort delete: `pre_delete` on `Cohort` -> `delete_role_rows_for` (`utils.py:35-51`),
  hard deleting `ObjectRoleAssignment` and guardian rows. This is a role removal with no `remove_object_role` call, so
  no entry unless the cohort-deleted entry says so.

### The `view_audit_log` placeholders

- `role_based_permissions/registry.py:131`, inside the FUTURE comment block:
  `#   "freedom_ls_role_based_permissions.view_audit_log": "Can view the system audit log"`.
- `role_based_permissions/roles.py:134`, inside `system_admin`'s placeholder: `# freedom_ls_role_based_permissions.manage_settings, freedom_ls_role_based_permissions.view_audit_log`.
  `system_admin` has `permissions=frozenset()` (132) and `assignment_scope=SCOPE_SYSTEM`.

The idea says the row is for **site admins and organisation admins**, scoped per organisation. `system_admin` has no
site, so the placeholder name (`role_based_permissions.view_audit_log`, "system audit log") describes a different
thing (a platform-wide log) and the stale comments should be reconciled: either removed or renamed.

## 3. How permissions and roles are defined (spec 5) and how a new row is added

- Roles: `role_based_permissions/roles.py` `BASE_ROLES` (13-154), `Role(display_name, assignment_scope, lti_role,
  description, permissions=frozenset({...}))`. `site_admin` permissions 21-51; `organisation_admin` 96-122;
  `cohort_admin` 58-73; `cohort_viewer` 80-89.
- Registry: `role_based_permissions/registry.py` `PERMISSIONS: dict[str, str]`. Every string a role carries must be in
  it (`tests/test_roles.py:12-16`, `validate_role_permissions` command line 75).
- Resolution: `learner_management/capabilities.py:170-203` `can(user, capability, scope)` reads role assignments and
  the role config, never guardian rows. Scope kinds supported: `Site`, `Organisation`, `Cohort`, `Learner`
  (`_site_of` 71-79, `_organisation_of` 82-95; any other scope raises `TypeError`). An organisation-level grant is
  gated on an active `OrganisationMember` (`_member_organisations` 137-148); a site grant is not.
  `roles_granting(capability, site)` (46-51) is how the config feeds `can`.
- Matrix: spec 5's table (`3. done/2026-10-01_22:00_educator-interface-5-permissions/1. spec.md:48-64`) says
  "spec 11 adds the audit log row" and "a later spec that builds a capability outside these rows adds the row, the
  string and the check together". Its enforcement is `educator_interface/tests/invariants/test_permission_matrix.py`:
  - `MATRIX: dict[str, dict[str, set[tuple[str, str]]]]` (line 102 on): capability -> role -> (scope kind, relation) pairs.
  - `CAPABILITY_SCOPE_KINDS` (316-341): which scope kinds each capability is asked of.
  - `test_every_capability_a_role_holds_has_a_matrix_entry` (440), `test_every_matrix_entry_names_all_four_roles` (449),
    `test_a_roles_permissions_equal_the_capabilities_its_matrix_column_allows` (457),
    `test_every_capability_reachable_from_the_interface_is_in_matrix` (565, via `interface_walk.walk_interface`).
  So adding a capability fails these tests until both dicts gain the row, with `site_admin` and `organisation_admin`
  holding it on `("organisation", OWN)` (and site admin also `OTHER_ORGANISATION`), `cohort_admin`/`cohort_viewer`
  `set()`.
- To add the row, four edits plus tests: (1) a permission on the new model (built-in `view_<model>` needs none; a custom
  one needs `Meta.permissions` and a migration); (2) `registry.py` `PERMISSIONS` entry; (3) the string in
  `site_admin` and `organisation_admin` `permissions` in `roles.py`; (4) `MATRIX` and `CAPABILITY_SCOPE_KINDS` in
  `test_permission_matrix.py`. Section visibility uses `view_capability` on the section config (below).
- Downstream: `config/role_based_permissions/prelude.py` and `demodev.py` build roles on `BASE_ROLES` and
  `SiteRolesConfig`. A downstream role config that spells out its own permission sets for these roles will not gain the
  new string automatically; this belongs in the upgrade notes.
- Product docs: `docs/product/educator-interface.md:94` says there is "no record of past role changes";
  `docs/product/security-and-data-handling.md:21` lists "an audit log of role changes" as not yet built.

## 4. Inventory of educator-interface actions (specs 6, 7, 9) -> audit write point

"Actor available" = the actor can be read at the write point without new plumbing.
`panel` = `freedom_ls/educator_interface/actions.py`; `svc` = `freedom_ls/learner_management/learner_actions.py`;
`lm_utils` = `freedom_ls/learner_management/utils.py`; `rbac` = `learner_management/role_assignment.py`.
Organisation reaches the entry through `learner.organisation`, `cohort.organisation`, or `OrganisationMember.organisation`.

### Cohort actions (spec 6)

| Action | Class / function | File:line | Objects touched | Transaction? | Actor available | Proposed entry |
|---|---|---|---|---|---|---|
| Create cohort | `CreateCohortAction` -> `CreateInstanceAction.form_valid` -> `form.save()` | `educator_interface/views.py:1002-1025`; `panel_framework/actions.py:275-276` | `Cohort` | no | request in `form_valid(request, form)` | `cohort.created` (target cohort) |
| Rename / edit cohort | `EditCohortAction` (`RequiresActiveCohortMixin, EditAction`) -> `EditAction.form_valid` -> `form.save()` | `actions.py:226`; `panel_framework/actions.py:330-331` | `Cohort.name` | no | request | `cohort.renamed`; details `{old, new}` (the form has `changed_data` and `initial`) |
| Deactivate / reactivate cohort | `DeactivateCohortAction` / `ReactivateCohortAction` via `CohortStateAction.handle_submit` | `actions.py:255-305`, save at 274-275 | `Cohort.is_active` | no | `ctx.request.user` | `cohort.deactivated`, `cohort.reactivated` |
| Delete empty cohort | `DeleteEmptyCohortAction.handle_submit` | `actions.py:308-351` | `Cohort` (deleted), cascades role rows via `pre_delete` receiver (`signals.py:47-53`) | yes (`transaction.atomic()` + `select_for_update`, 334-351) | `ctx.request.user` | `cohort.deleted`; target label must be stored (target gone); details: role rows removed |
| Register cohort for course | `RegisterCohortForCourseAction.form_valid` -> `register_cohort_for_course` | `actions.py:354-391`; `lm_utils.py:159-182` | `CohortCourseRegistration` (create or reactivate); post_save fans out course progress | no (utility is not atomic; webhook uses `on_commit`) | request | `cohort_registration.created` / `.reactivated` (target cohort, details course) |
| Unregister cohort from course | `UnregisterCohortFromCourseAction.handle_active_submit` -> `unregister_cohort_from_course` | `actions.py:501-548`; `lm_utils.py:185-192` | `CohortCourseRegistration.is_active` | no | `ctx.request.user` | `cohort_registration.deactivated` |

### Learner actions (spec 7)

| Action | Class / function | File:line | Objects touched | Transaction? | Proposed entry |
|---|---|---|---|---|---|
| Edit learner name | `EditLearnerNameAction` (`EditAction` on `learner.user`) | `actions.py:230-252` | `User.first_name/last_name` (a `User` shared across organisations) | no | `learner.renamed` or skip; details `{old, new}`. Target is the learner; the User is global. |
| Add learners (by email) | `AddLearnersAction.handle_submit` -> `add_learners(organisation, entries, cohort)` -> `_add_one` | `actions.py:1095-1189`; `svc:240-263`, `204-237` | `User` (maybe created), `Learner` (create/reactivate), `CohortMembership` (optional), setup email | yes: `add_learners` wraps the loop in one `transaction.atomic()` (256), each `_add_one` calls nested atomics | `learner.added` per row with outcome in details (`created`/`joined`/`reactivated`/`already_learner`/`invalid_email`/`email_in_use_elsewhere`, `AddOutcome` at 179-188). A bulk add of N addresses is already "a bulk run" inside the single-action path; `AddLearnersAction` is also the "add many" path (up to 50 addresses) and the model for spec 8's commit. |
| Add to cohort (from learner page) | `AddToCohortAction.handle_submit` -> `add_to_cohort` | `actions.py:977-1026`; `svc:90-101` | `CohortMembership` | yes (atomic, 95-101) | `membership.added` (target learner, details cohort) |
| Add existing learners to cohort | `AddExistingLearnersAction.handle_active_submit` -> `add_to_cohort` in a loop | `actions.py:1029-1092`, `transaction.atomic()` at 1087 | `CohortMembership` x N | yes | one `membership.added` per learner (or a summary) |
| Remove from cohort | `RemoveFromCohortAction` -> `MembershipAction.handle_submit` -> `remove_from_cohort` | `actions.py:750-834`; `svc:77-87` | `CohortMembership` (hard delete) | yes | `membership.removed` (target learner, details cohort) |
| Move between cohorts | `MoveToCohortAction.handle_submit` -> `move_between_cohorts` | `actions.py:837-943`; `svc:104-138` | `CohortMembership` delete + create, signal `cohort_membership_moved`, course progress re-pointed (`learner_progress`) | yes (single atomic, 115-138) | `membership.moved`, details `{source, destination, move_id}`. `move_id` (a uuid, `svc:114`) already ties the two webhook events together; reuse it. |
| Deactivate / reactivate learner | `DeactivateLearnerAction` / `ReactivateLearnerAction` -> `deactivate_learner` / `reactivate_learner` -> `_set_learner_active` | `actions.py:394-453`; `svc:43-63` | `Learner.is_active` | yes (`select_for_update`, 45-53) | `learner.deactivated`, `learner.reactivated`. `_set_learner_active` returns `False` on a no-op, so write only when it returns true. |
| Resend setup email | `ResendSetupEmailAction.handle_submit` -> `resend_account_setup_email` | `actions.py:456-495` | sends mail, no data change | no | optional `learner.setup_email_resent`; no write today. The spec decides in or out. |
| Register learner for course | `RegisterLearnerForCourseAction.form_valid` -> `register_for_course` | `actions.py:556-597`; `svc:141-154` | `LearnerCourseRegistration` (create or reactivate) | yes | `registration.created` / `.reactivated` |
| Unregister learner from course | `UnregisterLearnerFromCourseAction.handle_submit` -> `unregister_from_course` | `actions.py:600-657`; `svc:157-169` | `LearnerCourseRegistration.is_active` | yes | `registration.deactivated` |
| Re-register learner for course | `ReregisterLearnerForCourseAction.handle_submit` -> `register_for_course` | `actions.py:660-700` | same row reactivated | yes | `registration.reactivated` |

### Member actions (spec 9)

| Action | Class / function | File:line | Objects touched | Transaction? | Proposed entry |
|---|---|---|---|---|---|
| Add member (role on organisation or cohorts) | `AddMemberAction._perform` -> `match_or_create_user` + `assign_role` per target + `send_account_setup_email` | `actions.py:1308-1639`, atomic at 1629 | `User` (maybe), `ObjectRoleAssignment` per target, `OrganisationMember` (implicit via signal) | yes | role entries come free from `assign_object_role`; an extra `member.added` / `account.created` entry only if the vocabulary wants "account created". |
| Add member to cohort | `AddMemberToCohortAction` (subclass, same `_perform`) | `actions.py:1642-1660` | as above, role fixed to cohort | yes | as above |
| Remove role | `RemoveRoleAction.handle_submit` -> `remove_role` per target | `actions.py:1707-1796`, atomic at 1789 | `ObjectRoleAssignment.is_active` | yes (plus `remove_role`'s own atomic, `role_assignment.py:142`) | `role.removed` per target from `remove_object_role` |
| Change cohorts on a role | `ChangeCohortsAction.handle_submit` -> `assign_role` / `remove_role` | `actions.py:1805-1934`, atomic at 1893 | several `ObjectRoleAssignment` | yes | `role.granted` / `role.removed` per cohort |
| Suspend member | `SuspendMemberAction.handle_submit` -> `set_organisation_member_active(actor, row, False)` | `actions.py:1955-1983`; `role_assignment.py:152-167` | `OrganisationMember.is_active` | yes (atomic 163) | `member.suspended` (no `RoleAssignment` change, so the role utilities do not cover it) |
| Reactivate member | `ReactivateMemberAction.handle_submit` -> `ensure_organisation_member` + `set_organisation_member_active(..., True)` | `actions.py:1986-2016`, atomic at 2009 | `OrganisationMember` | yes | `member.reactivated` |

### Out-of-interface writers (not in scope per the idea, but the spec should say so)

- Self-registration on the default organisation: `learner_interface/views.py:889` calls `ensure_learner`, and
  `learner_interface` also writes `LearnerCourseRegistration` with `self_registered=True`. These are learner actions,
  not educator ones. The idea says "Anything learner-facing" is out of scope.
- Django admin edits to `Learner`, `Cohort`, `OrganisationMember`, `ObjectRoleAssignment` (`learner_management/admin.py`,
  `role_based_permissions/admin.py` if any) bypass every service function; they would write no entry.
- `course_applications`, `registration_rules`, `qa_helpers`, `dev_tools/create_demo_data.py:214` call `ensure_learner` etc.

### Cross-cutting facts about the inventory

- Panel actions return `changed_response({LEARNER_CHANGED: ...})` and HX events (`educator_interface/events.py`: only
  four names `learnerChanged`, `cohortChanged`, `registrationChanged`, `memberChanged`). A History panel on the
  learner page should refresh on `LEARNER_CHANGED` (the existing `LearnerHistoryPanel.refresh_events` already does) and
  a cohort one on `COHORT_CHANGED`. Most actions already trigger both events, so no new event is needed. Cohort state and
  `RegisterCohortForCourseAction` use `navigation_response` (full re-render), not events (`actions.py:278,391,548`).
- Webhook event names already form a past-tense-ish dotted vocabulary: `learner.added`, `learner.deactivated`,
  `learner.reactivated`, `cohort.member_added`, `cohort.member_removed` (with `move_id`), `cohort.course_registered`,
  `cohort.course_unregistered`, `course.registered`, `course.unregistered`
  (`svc:86,100,136,137,225`; `lm_utils.py:142-146`; `docs/product/webhooks.md:22`). The event type registry is
  `WEBHOOK_EVENT_TYPES` in app settings (`webhooks/registry.py:4-6`). They fire through `fire_webhook_event_on_commit`
  (`lm_utils.py:128-135`). The audit write must be inside the transaction and not on commit, so it rolls back with the
  action. The idea's list is "learner added, learner deactivated, membership moved, registration deactivated,
  role granted, role removed, cohort deactivated, import committed". These do not equal the webhook names; the spec
  decides whether to align (a stable string either way).
- The exclusion rule: `can()` is not what writes; the writer is whichever function mutates. Spec 9's plan says "one
  service function per operation ... each atomic, each doing the permission check, the last-admin check and the audit
  write" (`3. done/.../educator-interface-9.../research_best_practices.md:66`). For specs 6/7 the seam is `learner_actions.py`
  (docstring line 1: "The single seam for each learner administration action: one transaction, no request, webhook
  events on commit only when something changed").

## 5. Learner and cohort detail views, tabs and panels

- Learner page: `educator_interface/views.py:711-727` `LearnerInstanceView(panel=LearnerTabSet)`; `LearnerTabSet`
  (702-708) `children = {"overview": LearnerOverviewStack, "courses": LearnerCoursesStack, "history": LearnerHistoryPanel}`.
  `LearnerHistoryPanel(Panel)` (695-699): `model = Learner`, `title = "History"`, `template_name =
  "educator_interface/panels/learner_history.html"` (a single `<c-panel-empty-state message="Nothing has been recorded for
  this learner yet." />`), `refresh_events = (LEARNER_CHANGED,)`. Spec 7 plan lines 468-470 and `1. spec.md:342`.
  The panel has no `capability` (so it shows whenever the page is reachable). Gate it with the new capability.
- Cohort page: `CohortTabSet` (963-970) has `overview`, `learners`, `courses`, `settings`. Add `"history"`.
  `CohortSettingsPanel` and `CohortEducatorsPanel` show how `capability = "..."` hides a panel (`Panel.has_permission`
  uses `ctx.scope_object()` + `config.has_capability`, `panel_framework/panels.py:70-85`).
- Panel mechanics: `Panel` (33), `PanelStack` (181), `TabSet` (193; tab label = child `title`, count = `get_tab_count()`),
  `DataTablePanel` (239; needs `data_table`, `table_key`, `get_queryset(request)`; `card_flush = True`),
  `ListViewPanel` (`panel_framework/views.py:321`). The tab's URL is `<base>/__tabs/<name>`; tabs share a page.
- A history tab as a table: subclass `DataTablePanel` with `data_table = <AuditTable>`, `table_key = "history"` (query
  params are namespaced `<table_key>-page` etc., `tables.py` `TableQuery`), `get_queryset` filtered to the target (a
  `GenericForeignKey` filter by `content_type` + `object_id`, or a denormalised target id).
  Examples: `LearnerCohortsPanel` (570-605) filters `super().get_queryset(request)` by `self.instance`;
  `CohortLearnersPanel` (799-825).
- The learner's history ought to show events that target the learner and also, arguably, events that target their
  memberships and registrations (`membership.added` has a learner and a cohort). Entries that name two objects (a move)
  need to show on both learner and the two cohorts' pages; a single GFK target cannot give that without either a
  second link field or JSON lookups. The spec decides (a `related` key, a second nullable FK, or query on details).
- Object lifetimes: the page's learner may be deactivated (still viewable: `LearnerConfig.authorise_instance`
  `include_removed=True`, `views.py:1073-1081`) and a deleted cohort has no page, so a deleted cohort's history lives only
  in the organisation-level log (hence the stored label).

## 6. Organisation-level sections and spec 2's table framework

- Sections are declared in `interface_config` (`views.py:1678-1684`): `NavGroup("Teaching", [DashboardConfig,
  CohortConfig, LearnerConfig, CourseConfig, MessagesConfig])` and `NavGroup("Administration", [MemberConfig])`. The log
  fits beside Members under Administration.
- `MemberConfig` (1633-1675) is the closest template: `OrganisationSectionConfig, ListViewConfig`, `model = User`,
  `list_view = MemberDataTable`, `table_key = "members"`, `view_capability = "freedom_ls_learner_management.view_organisationmember"`
  (hides the section and 404s every path under it, `panel_framework/views.py:125-135`), `check_access_exempt_reason =
  "members have no instance pages"` (a test asserts exemptions are declared, 106), `intro_template_name`,
  `refresh_events`. `OrganisationSectionConfig` (191-225) supplies `get_scope` (the organisation), `has_capability`
  (`can(...)`) and `get_denied_context`.
- Table framework (`panel_framework/tables.py`, `filters.py`):
  - `DataTable` (202): `page_size = 10`, `search_fields`, `default_sort`, `empty_state_template`, `card_template`,
    `get_queryset(request)` (static), `get_columns() -> list[Column]`, `get_filters() -> list[TableFilter]`, `get_row_label`,
    `get_export_columns() -> list[ExportColumn]` (CSV export hook; exports default to off), `parse_query`, `filter_queryset`,
    `get_rows` (a `Paginator`, which you can override as `MemberDataTable.get_rows` does, 1590-1604), `get_context`.
  - `Column` (148): `header`, `template` (a cell template path, e.g. `cotton/data-table-cells/text.html`, `link.html`),
    `attr`, `text_attr`, `sortable`, `sort_field`, `card` ("primary"/"secondary"/"md_only").
  - Filters (`filters.py`): `ChoiceFilter(key, label, lookup=, choices=, always_shown=, default=)` (77), `RelatedChoiceFilter(...,
    queryset=)` (99; select widget; choices are `str(obj)`, scoped by `get_queryset(request)` to avoid leaking), `BooleanFilter` (130).
    **There is no date-range filter**; the idea needs "filterable by actor, action and date", so a date filter class is new
    framework code (subclass `TableFilter`, override `get_choices` / `validate` / `apply`; `validate` must accept free-form
    values, which today's `validate` rejects if not in `get_choices`). Alternatives: presets ("Last 7 days", "Last 30 days",
    "Last 90 days") through `ChoiceFilter` with a custom `apply`, which fits the existing contract and needs no new widget.
  - URL state: all query state is prefixed `<table_key>-` (`TableQuery.to_params`, 40-56), pagination via
    `get_elided_page_range`, sorting via `sort_changes`. `DataTable.default_sort` and the queryset's `ordering` give the
    newest-first order; `filter_queryset` appends `pk` as a tiebreaker (322), which on a UUID pk gives a stable but
    arbitrary tail order for identical timestamps (use a monotonic tiebreaker, see section 11).
  - Bulk actions exist (`panel_framework/bulk_actions.py`: `BulkAction.execute(request, queryset)`, `max_rows = 500`,
    `Selection` modes "keys" and unresolved "all_matching"); the audit table must not offer them.
  - CSV export hook: `get_export_columns` and the `<table_key>-export=csv` parameter. An audit CSV is a natural ask; the
    default is off, and the idea's out-of-scope list does not mention export. Note `escape_csv_formula` is applied by
    `ExportColumn.cell` (199).
- A scoped queryset must pass `get_queryset(request)`: `OrganisationScopedRequest.organisation` is on the request
  (`views.py:169-188`). Site isolation comes from `SiteAwareManager` (below) and the organisation filter must be added by the
  table (the manager filters site only).
- The sidebar and the interface walk: `educator_interface/tests/interface_walk.py` enumerates every section (`SECTIONS`,
  38) and `test_config_authorisation.py` sweeps their paths; a new section with `model` set needs a `_seed_instance` branch
  (60+) or an exemption.

## 7. Site-aware base, Organisation, and how objects reach an organisation

- `site_aware_models/models.py`: `SiteAwareModelBase` (131; `site` FK to `Site` with `PROTECT`; `objects =
  SiteAwareManager()` which ANDs the ambient request site onto every query, 117-128; `save()` and `full_clean()` fill
  `site` from the thread-local request when unset, 139-157), `SiteAwareModel(SiteAwareModelBase)` adds a UUID `id`
  (165), `TimestampedModel` (172: `created_at`, `updated_at`, composed alongside). `site_of(obj)` (160).
  **Trap**: outside a request (management commands, tests, Celery-like tasks), `site` is not auto-filled and `objects`
  does not filter, so the audit writer must always pass `site=` explicitly and read through `_base_manager` when it
  needs to see rows regardless of the ambient site. This is why `ensure_learner` etc. use `_base_manager` (`utils.py:68-74`).
  A write inside a view uses the request site, but the target's site is the correct value (`site_of(target)`).
- `Organisation(SiteAwareModel, TimestampedModel)` (`organisations/models.py:58`): `name`, `slug`, logos, `is_default`.
  Uniqueness `(site, slug)` and `(site, name)`. An organisation can be renamed, so the entry should store a label
  (name) for the organisation if the FK could be removed; today `Learner.organisation` and `Cohort.organisation` are
  `PROTECT` (`learner_management/models.py:35-38,70-72`) so an organisation with content cannot be deleted, and an
  entry's organisation FK may use `PROTECT` or `SET_NULL`; the org-level log needs it.
- How an object reaches an organisation: `Cohort.organisation`, `Learner.organisation`, `OrganisationMember.organisation`
  are direct FKs; `CohortMembership` via `cohort.organisation` / `learner.organisation` (the two must match,
  `CohortMembership.clean` 131-138); `LearnerCourseRegistration` via `learner.organisation`; `CohortCourseRegistration` via
  `cohort.organisation`; `ObjectRoleAssignment` via the open GFK target (Organisation itself, a Cohort's organisation, or
  neither). `can()` already encodes this (`_organisation_of`, `capabilities.py:82-95`) and raises `TypeError` for any other
  scope kind. Reuse that rule to fill `organisation`.
- `User` is site-aware (`SiteAwareModelBase`, per `docs/app_conventions.md:87-97`), with `display_name` (`accounts/models.py:103-108`:
  full name, else first/last, else email) and `email`. An actor label can be stored from `display_name`.

## 8. Existing audit-shaped records and patterns to copy

- **`LegalConsent`** (`accounts/models.py:174-230`): `SiteAwareModel`; append-only by raising `ValueError` in `save()` when
  `pk is not None and not _state.adding` (212-224). The comment says it only covers `.save()`; `QuerySet.update()` and
  `bulk_update()` bypass it, "the admin registers this model as fully read-only as the second layer of defence". Admin
  (`accounts/admin.py:69-97`): `LegalConsentAdmin(SiteAwareModelAdmin)` with `readonly_fields`, `has_add_permission`,
  `has_change_permission`, `has_delete_permission` returning `False`; `LegalConsentInline` (27-51) read-only inline on the
  User page. **A custom `QuerySet`/`Manager` that raises on `update`/`delete` is stronger than the model-level guard and
  nothing in FLS does it yet** (the idea says "no update or delete through the ORM in application code").
- **`USER_ERASURE_CASCADE_MODELS`** (`accounts/admin.py:20`): a `set[type[Model]]`; apps add their read-only audit models
  from their own admin (`course_applications/admin.py:26-27`, `learner_management/admin.py:299`,
  `referral_tracking/admin.py:81`); the User admin lists them in its delete-confirmation (line 174) and vouches for the
  cascade. An actor FK with `on_delete=CASCADE` would put this model in that set and delete the actor's history on erasure;
  `SET_NULL` keeps history. The idea says "actor nullable for system actions", consistent with SET_NULL, but then the
  actor identity after erasure is the stored label only.
- **`WebhookEvent`/`WebhookDelivery`** (`webhooks/models.py:376-420`): `WebhookEvent(event_type, payload JSON,
  created_at)`; `WebhookDelivery.endpoint_url` stores "the attempted target after the endpoint itself is deleted" (392-394)
  - the same "stored label" idea as the audit target label. The idea's default excludes webhook deliveries from the log.
- **`assigned_by`** fields: `SystemRoleAssignment.assigned_by` (23-29), `SiteRoleAssignment.assigned_by` (57-63),
  `ObjectRoleAssignment.assigned_by` (99-105): FK to user, `SET_NULL`, `related_name="+"`. `assigned_at`/`updated_at` stamped.
  The Members table already shows added-by/added-on from the active row (`MemberDataTable`, `views.py:1561-1583`,
  `select_related("assigned_by")`). Removal is not recorded anywhere today (`updated_at` moves, remover is not stored); the
  audit entry is the only record of who removed a role.
- **GenericForeignKey precedent**: `ObjectRoleAssignment.target` (`role_based_permissions/models.py:95-96`,
  `object_id` `CharField(255)` because the set of targets is open), `comms/models.py:93-97` `Notification.target`
  (same: `CharField(255)` "Open-set ... a downstream project can add categories whose targets aren't UUID-keyed"),
  `content_engine/models/courses.py:530,537` and `learner_management/models.py:232,278,325` (UUID `object_id`, closed set).
  `docs/app_conventions.md:124-136` is the rule: match whichever situation applies; do not default to `CharField`. For the
  audit target the set is open (downstream vocabulary), so `CharField(max_length=255)` is the convention-consistent choice,
  and the cohort/learner/registration queries filter by `content_type` + `object_id` with a `str(pk)`.
  Existing code that queries these by `Cast(OuterRef("pk"), CharField())` (`capabilities.py:121-134`) shows the join cost; an
  index on `(content_type, object_id)` is the equivalent.
- **Read-only admin patterns**: `SiteAwareModelAdmin` (`site_aware_models/admin.py:23-29`, excludes `site`),
  `SiteAwareExportModelAdmin` (32-59, CSV export gated on view permission, `FormulaSafeCSV`),
  `GuardedSiteAwareModelAdmin` (62-72). `fls-dev:admin-interface` skill (named in the idea) at
  `claude_plugins/fls-dev/skills/admin-interface/SKILL.md` and `claude_plugins/fls-dev/resources/admin_interface.md`.
  Admin forms for site-aware models with constraints need `ConstraintValidationFormMixin` (not needed for a no-form admin).
- **Immutability helpers**: none generic. `ObjectRoleAssignment` and others allow update.

## 9. App settings, management commands, housekeeping

- App-settings pattern: `base/app_settings.py` `AppSettings` + `Setting(default, required)` (11-59), each app has a
  `config.py` singleton (e.g. `organisations/config.py`; `comms/config.py:23-34` shows list defaults:
  `NOTIFICATION_CATEGORIES: Setting(default=FLS_NOTIFICATION_CATEGORIES)`). That is the precedent for "downstream project
  extends the vocabulary through an app setting" (open question 3): `comms.notify` validates the category against the
  registry synchronously (`comms/notify.py:37`). `webhooks` does the same with `WEBHOOK_EVENT_TYPES`
  (`webhooks/registry.py:4-6`). Skill `fls-dev:app-settings`. A retention age setting would be
  `AUDIT_LOG_RETENTION_DAYS: Setting(default=None)`.
  Note `AppSettings.__getattr__` treats `None` and `""` as unset, then returns the default; `0` is a valid value.
  Required settings need a system check (`required_settings_errors`, `base/app_settings.py:62-75`); ids are
  `<label>.E001` where `<label>` is the app's own label (`docs/app_conventions.md:59-67`).
- Management commands live at `<app>/management/commands/<name>.py` with an `__init__.py` in `management/` and
  `commands/` (e.g. `role_based_permissions/management/commands/{sync_role_permissions,validate_role_permissions}.py`;
  `learner_progress/management/commands/recalculate_progress_percentages.py`; tests mirrored at
  `<app>/tests/management/commands/test_*.py`). `test_organisation/mirroring_*` hooks check the mirroring.
- Housekeeping: `deployment/management/commands/fls_run_housekeeping.py` runs `deployment/housekeeping.py`
  `run_housekeeping_sweeps()` (221) "Run once and exit" (task result pruning, session clearing, orphan reports). It would be
  the home for a scheduled prune, but the idea says "not run by default"; also `deployment` imports `organisations` and
  `reports`, not `role_based_permissions`. A plain `prune_audit_log` command in the audit app with `--older-than` /
  setting default and `--dry-run` fits; the sweep can opt in later.
- Prior state of retention in docs: nothing is pruned anywhere app-side except task results and queued mail
  (`docs/product/security-and-data-handling.md:148`). There is no retention policy doc to align with; the audit log's
  retention decision becomes a new "Gap" or "Built" line there.

## 10. Where the model should live (dependency rules)

Source: `docs/app_structure.md` (generated by `/app_map`; import-linter contracts generated from it in
`test_organisation/import_contracts.toml`; `import_baseline.txt` only shrinks).

Production edges that matter (solid arrows): `role_based_permissions --> accounts, base, site_aware_models`;
`organisations --> base, site_aware_models`; `learner_management --> accounts, base, content_engine, form_engine,
organisations, role_based_permissions, site_aware_models, webhooks`; `educator_interface --> accounts, comms, content_engine,
learner_management, learner_progress, organisations, panel_framework, role_based_permissions, site_aware_models`;
`accounts --> base, mail, markdown_rendering, site_aware_models, webhooks`; `site_aware_models --> base`. Dotted edges are
test-only or lazy (`organisations -.-> role_based_permissions` is `organisations/tests/test_models.py:23`).

Constraints this creates:

- The writers are `role_based_permissions` (utils), `learner_management` (`learner_actions`, `role_assignment`,
  `utils`), and `educator_interface` (panel actions). The model must be importable by all three without a cycle.
- The model needs FKs to the user (`settings.AUTH_USER_MODEL`, a string reference needs no import), to `Site` (via
  `SiteAwareModel`) and to `Organisation` (string reference `"freedom_ls_organisations.Organisation"` as
  `learner_management/models.py:35-37` does). `organisations` does not import `role_based_permissions` or
  `learner_management` in production code, so any placement works for cycles.
- Options:
  1. **New app `freedom_ls/audit_log`** (label `freedom_ls_audit_log`, `verbose_name="Audit log"`, `default_auto_field`
     set, per `docs/app_conventions.md:10-97`). Depends on `accounts` (or string-only), `base`, `organisations`,
     `site_aware_models`. `role_based_permissions`, `learner_management`, `educator_interface` depend on it. Keeps
     `role_based_permissions` generic (it currently imports no organisations). Its tests are mirrored; the declared
     import contracts regenerate via `/ds:app_map` (the `app-map-fresh` hook fails if stale), and `docs/app_structure.md`
     changes. `freedom_ls/contrib/conformance/tests/test_app_labels.py` checks label/heading.
  2. `role_based_permissions` (it already holds `GenericForeignKey` usage, assignment tables, `exceptions.py`,
     a `README.md`, and the six TODOs). Adds a production edge `role_based_permissions --> organisations` (and nullable org
     FK). Smaller diff, but conflicts with its generic framing and with `role_based_permissions -.-> learner_management`.
  3. `learner_management`: cannot be imported by `role_based_permissions` (that is the cycle: `learner_management -->
     role_based_permissions`, and the app map lists `role_based_permissions -.-> learner_management` as a lazy/test edge).
     **Ruled out** for the role utilities' writes.
  4. `organisations`: no cycle (`organisations --> base, site_aware_models`), but then `role_based_permissions -->
     organisations` and the log's vocabulary has nothing to do with organisation records. Not natural.
- Reader side (the history tab, the section, the capability) lives in `educator_interface`, which already imports all of
  these. The string vocabulary should live with the model (a constants module), importable by both writers and readers.
- Settings: `config/settings_base.py:74-` `INSTALLED_APPS` lists `freedom_ls.organisations` (121), `learner_management`
  (122), `site_aware_models` (126), `role_based_permissions` (130), `webhooks` (144); a new app is added there, and
  `settings_dev.py`/`test` settings inherit. Downstream projects must add the app too: upgrade notes.

## 11. Conflicts and risks

1. **Actor plumbing (finding 1).** The service functions in `learner_actions.py` and `lm_utils.py` need an optional `actor`
   keyword; every caller (`educator_interface/actions.py` lines 438, 448, 596, 656, 699, 1025, 1089, 1172, and
   `register_cohort_for_course`/`unregister_cohort_from_course` at 388/545) must pass `ctx.request.user`; `qa_helpers`
   commands pass none. Adding a required parameter would break callers and tests; an optional keyword with `None` meaning
   "system" matches the existing `assigned_by: User | None = None` shape.
2. **No-op writes.** `add_to_cohort`, `remove_from_cohort`, `_set_learner_active`, `register_for_course`, `unregister_from_course`
   return `False` when nothing changed; write an entry only on `True`. `remove_object_role`/`remove_site_role`/`remove_system_role`
   discard the `update()` row count today, and `assign_*` has `created`/`fields_to_update`. An audit entry on an unchanged
   state would claim a change that did not happen. A refused or rolled back action must write nothing (it does, if the write is
   inside the action's atomic block).
3. **Two sources of actor.** `RoleChangeRefused` actions raise before writing; `AddMemberAction._perform` catches it outside
   `atomic()` (1635-1636) so the rollback is clean. Writing inside the loop is consistent.
4. **Bulk (spec 8).** The idea says "a bulk run writes one summary entry with per-object detail in the JSON field" while the
   other writers write "one entry per object". The two overlap: a bulk action that internally calls the single-object functions
   (spec 8 idea: "using the single-object actions specs 6 and 7 built", "Commit uses spec 7's add-learner path row by row") would
   also write the per-object entries unless the writer is suppressed or the bulk path wraps it. Spec 8's idea line 35: "Each bulk
   run is one entry with a per-object breakdown once spec 11 exists. Until then, the result summary is the record." Decide whether
   the bulk summary replaces the per-object entries or adds to them (the former needs a context flag; the latter double counts
   in the learner's history). Also: the JSON detail for 500 rows (`BulkAction.max_rows = 500`, `bulk_actions.py:30`) and the
   import threshold (low hundreds, background task via `django-tasks`) are unbounded without a cap; in a background task there is
   no request (ambient site is empty, `SiteResolutionError` from `get_cached_site(None)` when no `FORCE_SITE_NAME`), so the
   writer must take `site` from the target and the actor must be passed explicitly. Spec 8 is not yet written, so this spec
   should expose a small entry-writing function that takes `actor`, `action`, `target`, `organisation`, `site`, `reason`,
   `details` and bulk summaries as a separate action name (for example `import_committed`).
5. **Append-only enforcement.** Model-level `save()` guard (as `LegalConsent`) is bypassed by `QuerySet.update/delete`,
   `bulk_update`, and by cascades. Cascades: if `target`'s content-type is a deleted model nothing cascades (GFK has no reverse
   cascade) and `site` is `PROTECT`; `organisation` FK choice matters (`PROTECT` blocks organisation deletion; `SET_NULL`
   loses the log's org-level grouping). A custom manager/queryset raising on `update()`/`delete()`, plus read-only admin
   with delete denied, is the only comprehensive answer in-app. `delete()` from `prune` must still be possible: expose it
   only from the prune command (a private queryset method).
6. **GDPR and erasure.** `USER_ERASURE_CASCADE_MODELS` (`accounts/admin.py:20`) means deleting a user must either cascade
   or leave the row. Entries store an actor label and a target label (a learner's display name or email). After an erasure
   request those labels hold the erased person's PII indefinitely in an append-only table. Options: store the user id plus a
   label that is cleared on erasure (needs an update path, contradicts append-only), store no personal data in labels
   (use ids and role/cohort names only; learner labels read "Learner <id>"), or document the manual erasure step. The
   product docs say there is no data-subject tooling (`security-and-data-handling.md:21,190`). Also `User` deletion with
   `SET_NULL` on the actor FK needs the actor FK nullable (the idea already says nullable).
7. **Ordering.** UUID primary keys (`SiteAwareModel.id`) have no creation order; `DataTable.filter_queryset` appends `pk` as the
   final tiebreaker (`tables.py:322`) so identical-timestamp entries (a bulk loop) sort arbitrarily across pages. Index
   `(site, organisation, -created_at)` and `(content_type, object_id, -created_at)`; consider a `BigAutoField` sequence or rely
   on `created_at` with microsecond resolution plus tiebreak by `pk`.
8. **Matrix tests.** Adding the capability breaks `test_every_capability_a_role_holds_has_a_matrix_entry` and the other
   three matrix tests until `MATRIX` and `CAPABILITY_SCOPE_KINDS` gain the row (section 3). `test_organisation_isolation.py`
   and `test_config_authorisation.py` also sweep sections.
9. **`can()` scope.** The capability must be asked of an organisation (or, for the per-learner/cohort tab, of the learner or
   cohort): `can()` supports `Site`, `Organisation`, `Cohort`, `Learner` only. If the history tab uses the learner scope,
   a `cohort_admin` holding the capability on a cohort would see a learner's entire history; the idea gives the row to site
   admins and organisation admins only, so the cohort roles hold nothing and `can(..., learner)` still resolves via
   organisation-level grants (`capabilities.py:194`). Fine, but it means cohort admins see no history tab at all, and the tab
   must disappear (hidden, not disabled, per the roadmap's denied-experience rule, `roadmap.md:90`).
10. **Entry ordering with webhook fan-out.** Webhooks fire on commit; audit rows write inside. A reader could see an audit
    entry for an action whose webhook has not yet fired. No functional conflict.
11. **Transaction nesting.** `assign_object_role` and `remove_object_role` have no atomic block, so a failed audit write after
    the `get_or_create`/`update`/`sync` would leave the change without its entry when called outside an outer transaction
    (fixtures, QA commands). Wrap in `transaction.atomic()`; the guardian sync is already atomic on its own.
12. **Name collision.** The TODOs say `AuditLog entry` (an `AuditLog` class whose rows are "entries"); the idea says "one
    append-only model" and the product vocabulary says "audit log" for the whole feature. Choose one model class name (the
    row) and use it in identifiers; `view_audit_log` in the placeholder comments and `AuditLog` in the TODOs imply `AuditLog`
    is the row. A row named `AuditLog` makes its auto permission `view_auditlog`. (Domain vocabulary rule: the document's noun
    is the model class name.) Search the domain-glossary skill before fixing.
13. **Vocabulary alignment.** Existing words in code: `Learner` (status active/pending/removed, `learner_status`), `CohortMembership`
    ("membership"), `LearnerCourseRegistration`/`CohortCourseRegistration` ("registration"), `OrganisationMember` ("member",
    suspended), `ObjectRoleAssignment` ("role", `assigned_by`), "deactivate/reactivate", "remove" (membership, role), "unregister",
    "suspend" (member). UI strings in `docs/product/educator-interface.md` and the role description strings ("the same strings used
    in the audit log", `3. done/.../educator-interface-9.../idea.md:23`) live in `BASE_ROLES[...].description` and
    `educator_interface/members.py` `RoleEntry`. The spec 9 plan says one string source feeds the form, confirmations, audit log and docs
    (`research_ux_patterns.md:118`); entries should render role display names through `get_role_config(site.name)[role].display_name`
    rather than copy the strings.
14. **Reading by non-organisation entries.** Site-role and system-role entries have no organisation. They show up in the
    per-organisation log only if the spec decides how (site admins see site-level entries in every organisation's log, or
    they are shown only in the Django admin). The `site_admin` role is "not given or removed from the educator interface"
    (`docs/product/educator-interface.md:131`), so these entries are written only by the Django admin / commands / fixtures.
15. **Downstream roles config.** `config/role_based_permissions/{prelude,demodev}.py` build roles from `BASE_ROLES`; a downstream
    role definition with explicit sets will not carry the new permission: upgrade note.
16. **Admin model for existing data.** No backfill is possible: past actions left no record. Existing `assigned_by`/`assigned_at`
    could seed a "role granted" entry per active assignment via a data migration, which the idea does not ask for; skipping is
    the default and the docs should say history starts at the upgrade.
17. **Docs.** `docs/product/educator-interface.md` lines 51 ("The history tab is an empty placeholder"), 94 ("there is no record of
    past role changes"), and the summary (line 16) need updates; add a short "History" section (idea). `docs/product/security-and-data-handling.md:21`
    and `docs/product/roadmap.md` (not-built lists) mention the audit log as absent. `docs/product/README.md` has an index table.
    Spec 12's developer doc (`docs/product/panel-framework.md`, or `docs/how tos/`; not written; `spec_dd/1. next/educator-interface-12-docs-and-polish/idea.md:17`)
    does not mention the audit vocabulary yet, and spec 12 depends on this spec. This spec should place the vocabulary list in its own
    doc that spec 12 links, rather than waiting on 12's file. Product docs are produced by `fls-dev:update_product_docs`.

## 12. Spec 8 alignment (in progress, no spec yet)

What exists: `spec_dd/2. in progress/educator-interface-8-bulk-operations/idea.md` and `todo.md` only. Nothing is implemented on this branch.
Relevant statements in the idea:

- Line 23: commit uses "spec 7's add-learner path row by row" and runs as a `django-tasks` background task above a threshold.
- Line 27-29: bulk actions on the learner table (add to cohort, remove from cohort, register for a course, unregister, deactivate,
  reactivate, resend setup email) and on the cohort table (register for a course, unregister, deactivate, reactivate).
- Line 33: "each object is checked server-side, not only the first."
- Line 35: "**Audit.** Each bulk run is one entry with a per-object breakdown once spec 11 exists. Until then, the result summary is the record."
- Open: partial commit on error (default: valid rows commit, error rows reported).

What already exists to build on: `panel_framework/bulk_actions.py` (the row-selection payload and `BulkAction`; `execute(request, queryset)`
returns `None`, so a summary must be stashed on the request or the action; `max_rows = 500`), the `selection_bar` template and
`data-table.html` checkbox column (spec 2). No educator-interface `BulkAction` is declared yet.

Alignment points the audit spec should state (spec 8 will read them):

- The writer API (a function, not a model `.save()` scattered): `record(actor, action, target, *, organisation, reason="", details=None)` and a
  bulk form (`record_bulk(...)`) so spec 8 calls one thing. The `import_committed` and bulk action names go in the vocabulary now (idea lists
  `import committed`).
- Whether single-object writers called by a bulk run write their own per-object entries (and the summary links to them), or the summary
  replaces them. The idea says "Every action in specs 6 to 9 writes one entry per object, and a bulk run writes one summary entry with the
  per-object detail in the JSON field": the two statements conflict unless the bulk path suppresses the per-object writes or the learner's
  history relies on the summary entries' JSON (which a GFK filter on the learner cannot find). The learner history tab reading JSON is the
  hard part; the cheapest consistent rule is "bulk run = one summary entry for the organisation log, plus per-object entries for each changed
  object, linked by a shared id" (mirrors `move_id`).
- Reason text (optional, prompted for removals and deactivations) must be an input of the bulk dialogs, which spec 8 will reuse
  (`panel_framework/partials/bulk_confirmation.html`).
- Background tasks: no request, ambient site absent, so `site` must come from the organisation; actor passed through the task payload.

## 13. Files the work touches (summary)

New: the audit model, a writer module, vocabulary constants, admin (read-only), a prune command, tests, a migration, an `AppConfig` (and
`config.py` if settings), history templates/cell templates; a table class and `*Config` section in `educator_interface/views.py`; a date filter.
Edited: `role_based_permissions/utils.py` (six TODO sites), `registry.py` (and the FUTURE comment lines), `roles.py` (`site_admin`,
`organisation_admin` permissions and the `system_admin` placeholder comment), `learner_management/learner_actions.py`, `learner_management/utils.py`,
`learner_management/role_assignment.py` (suspend/reactivate member, `set_organisation_member_active`), `educator_interface/actions.py` and
`views.py` (history panels, `CohortTabSet`, `LearnerHistoryPanel`, the new section, `interface_config`), `panel_framework/actions.py` only if the
generic `CreateInstanceAction`/`EditAction`/`DeleteAction` get a hook, `educator_interface/tests/invariants/test_permission_matrix.py`, the app map
and import contracts (`docs/app_structure.md`, `test_organisation/import_contracts.toml`), `config/settings_base.py` (`INSTALLED_APPS`),
`docs/product/educator-interface.md`, `docs/product/security-and-data-handling.md`, `docs/product/roadmap.md`, upgrade notes.

status: ok
