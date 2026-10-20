# Research: prior art for educator administration (spec 9)

Question: what has already been tried, here or elsewhere, and what happened. Paths are relative to
the project root; done specs live under `spec_dd/3. done/<date>_<name>/`.

## 1. In this repository

### 1.1 There is no earlier attempt at the screen

No educators screen, role form or assign view has ever been built. `git log` could not be run (no
shell for this worker), so the history was not searched. Instead the code was searched: the only
callers of `assign_object_role` / `assign_site_role` outside tests are QA helpers
(`freedom_ls/qa_helpers/management/commands/qa_create_*.py`, 12 files, including
`qa_create_permissions_scenario.py`, `qa_create_single_org_educator.py`,
`qa_create_cohort_administration_scenario.py`, `qa_create_learner_administration_scenario.py`) and
`freedom_ls/learner_management/role_assignment.py`. The idea's claim "nothing calls them from a
screen" is correct.

### 1.2 What spec 5 already built for this spec (do not rebuild)

Source: `spec_dd/3. done/2026-10-01_22:00_educator-interface-5-permissions/` (`1. spec.md`,
`upgrade_notes.md`, `research_role_assignment_rules.md`) and the live code.

- Checked entry points in `freedom_ls/learner_management/role_assignment.py`:
  `assign_role(grantor, user, role, target)`, `remove_role(...)`,
  `set_organisation_member_active(actor, member, is_active)`. Raw utilities in
  `role_based_permissions/utils.py` stay for QA, fixtures and the admin. The module docstring says
  anything reached by a person must go through the checked ones.
- Refusals raise `RoleChangeRefused(RefusalReason.<X>)` (`role_based_permissions/exceptions.py`):
  `SELF`, `INACTIVE_USER`, `NOT_PERMITTED`, `LAST_SITE_ADMIN`, `LAST_ORGANISATION_ADMIN`. Order of
  checks: self, inactive target (assign only), `can(grantor, "freedom_ls_role_based_permissions.assign_<role>", target)`.
- Last-admin guards run under `select_for_update()`: `remove_site_role` locks the `Site` row;
  `remove_role` locks the `Organisation` row. A site-level admin (superuser or active `site_admin`)
  bypasses the organisation lock, matching the idea ("a site admin can").
- New capability strings: `assign_site_admin`, `assign_organisation_admin`, `assign_cohort_admin`,
  `assign_cohort_viewer`; `view/add/change_organisationmember` for membership. Matrix rows are in
  spec 5 `1. spec.md` (lines ~56-58).
- Role keys renamed (`organisation_admin`, `cohort_admin`, `cohort_viewer`); no alias for old keys.
- `OrganisationMember(site, user, organisation, is_active)` gates every organisation and cohort
  grant (not `site_admin`/superuser). A `post_save` receiver on `ObjectRoleAssignment`
  (`learner_management/signals.py`) creates the row for every new or re-saved active grant.
  `ensure_organisation_member` never reactivates an inactive row, and assigning to a user with an
  inactive member row leaves it inactive. Consequence for spec 9: **a role can be assigned and
  look present while it has no effect because the member row is inactive.** The list and "Add"
  flow have to show or handle that state. Spec 5 explicitly deferred "the screen for managing
  organisation members, including adding and deactivating an `OrganisationMember` (spec 9)":
  "until it ships, operators have no way to deactivate one".
- `active_organisation_admins(organisation)` (`learner_management/queries.py`) is the shared source
  for the last-admin check and the "who to ask" copy.
- Denied experience: 403 fragment `panel_framework/partials/action_denied.html` swapped via
  `data-htmx-swap-error`; stale action on an object that left scope answers 404 with
  `action_unavailable.html` (the QA B1 fix, below). `can()` reads role assignments only, never
  guardian rows.
- `cohort_educators(cohort)` in spec 6 returns `(User, role)` pairs for active `cohort_admin` /
  `cohort_viewer` grants gated on an active `OrganisationMember`. Spec 6 built the educators block
  read-only "in its own panel class so spec 9 can extend it" (`1. spec.md` ~line 195).

### 1.3 Decisions that bind this spec

From the roadmap (`spec_dd/1. next/roadmap.md`, "Educator interface rebuild"):

- Decision 2: an admin hands out their own level and below, within scope; only `site_admin` grants
  `site_admin`. Spec 5's `idea.md` replaced the older "organisation grants reserved to site admins".
- Decision 1: deactivate, never delete. Decision 3: audit log is spec 11, after this spec; the
  role utilities carry six `# TODO: AuditLog entry` comments that must stay.
- Assumptions: no invitation model (pending = account made, never logged in; resend uses allauth
  reset token); controls the user cannot use are hidden, not disabled; out-of-scope is 404, visible
  but no-longer-allowed action is 403 with who-to-ask; no new dependencies; everything org-scoped
  and site-aware.
- Specs 8 and 9 run in parallel and must both reuse spec 7's account-creation path, not write their
  own. Unknown owned by spec 9: role description copy and whether the "roles and permissions"
  screen survives as a read-only page.
- `status_vocabulary` research (spec 4) found no badge word chosen for removed educator
  assignments ("active / removed (implied)").

### 1.4 Account creation path from spec 7 (reuse)

`spec_dd/3. done/2026-10-20_13:37_educator-interface-7-learner-administration/1. spec.md`, R1:
`freedom_ls/accounts/account_setup.py` has `match_or_create_user(site, email, first_name="",
last_name="") -> (User, created)` and `send_account_setup_email(user, organisation_name)`.
Decision 5 says it was placed in `accounts` precisely "because spec 9 needs user creation without
`ensure_learner`". The resend has a cache-based throttle (`SETUP_EMAIL_RESEND_SECONDS`, 900) and
raises `SetupEmailRecentlySent`. Staff-created accounts do not fire `user.registered`. The send
takes an organisation name, not an `Organisation`, to avoid a runtime edge. Note the idea says
"matched case-insensitively": check that `match_or_create_user` does this (it "strips the address
and normalises the domain" per the spec; confirm the local part).

### 1.5 QA findings that carry over

- Spec 5 QA, bug B1 (`.../educator-interface-5-permissions/qa_report.md`): after an organisation
  admin grant is removed mid-flow, a stale delete on a cohort now out of scope returned 404, which
  `alpine-components.js` dropped silently (modal stayed open, no feedback). The todo records it was
  decided and fixed (404 from an in-page action gets an `action_unavailable` fragment). Spec 9
  relies on this when an admin removes someone's role while that person has the page open. QA
  setup pattern: grants changed mid-test from the shell with `remove_object_role` and
  `OrganisationMember.is_active` flips; to see the 403 variant the persona needed an extra
  `cohort_viewer` grant so the target stayed in scope.
- Spec 5 QA general notes: a 403 CSRF failure swapped into a modal rendered a whole nested page
  (observation, flagged for a human look, not fixed). Any educator-admin form that sits in a modal
  inherits this. The denial-modal heading touches its X icon, and the X is ~24px on mobile; both
  pre-existing modal chrome issues. Duplicate-name 422 text leaks model field names ("Site,
  Organisation and Name") which a duplicate-grant message could repeat.
- Spec 7 QA (`.../qa_report.md`): B1, an empty filter selection showed everyone instead of the
  default (fixed by `TableFilter` falling back to `default`); B2, a bare "Cohort:" label for a hidden
  input in a dialog (fixed); four pickers showed an empty select with no message, fixed with an
  "Empty pickers" sentence (R6); a picker labelled options "email - Organisation" instead of the
  agreed text (fixed); a cohort admin's picker only offers learners they can see (R5). Lessons for
  the educator picker: design the empty state ("no active cohorts"), the option label text, a
  default-bearing filter (role filter) and hidden inputs up front. Spec 6 QA: learners with no
  name could not be opened from lists (fixed; email or "Unnamed learner" shown). Educators created
  from the Add flow may also have no name, so the list needs the same fallback.

### 1.6 Gaps and loose ends handed to this spec

1. **Cohort deletion leaves orphan grants.** Confirmed by code search: nothing in
   `freedom_ls/educator_interface`, `learner_management` or `role_based_permissions` deletes
   `ObjectRoleAssignment` rows on cohort delete, and the spec 6 spec/plan do not mention
   it. Spec 6 landed before this one (2026-10-11), so the idea's "whoever lands first" resolves to
   spec 9 doing the cleanup (plus guardian permission rows). Also check `ObjectRoleAssignment`
   has no `GenericRelation` on `Cohort` (it uses `content_type` + `object_id`, `str(pk)` lookups).
2. **The member-state screen.** See 1.2: deactivating or reactivating an `OrganisationMember` has
   a checked entry point (`set_organisation_member_active`) and no UI. Decide whether this spec's
   "remove" means deactivating the assignment, the member row or both, since removing the last
   grant leaves an active `OrganisationMember` behind.
3. **Backfill hazard.** Spec 5's upgrade notes say no migration backfills `OrganisationMember`
   for pre-existing grants (the spec said it would; the notes say manual shell step). A listing
   built on `OrganisationMember` would omit such people; build the list from assignments, not
   members, and cross-check the `learner_management` migration state before relying on either.
4. **Self row.** `RefusalReason.SELF` is checked for add and remove; the UI should show the own row
   without actions (idea default).
5. **Mid-session removal** is covered by spec 5 (permission is re-checked per request).
6. Custom downstream roles (e.g. `senior_ta`) have no `assign_` string and so stay assignable only
   via raw utilities and the admin (spec 5). The educators list should probably only list or edit
   the four built-in roles, and say nothing about custom ones; decide in the spec.

### 1.7 Prior research in repo worth re-reading

- `spec_dd/3. done/.../educator-interface-5-permissions/research_role_assignment_rules.md`:
  Moodle assign matrix, IAM boundaries, last-admin pattern in GitHub/Slack/M365, edge-case table.
  Its recommended defaults were adopted (self-removal allowed unless last admin; inactive targets
  refused in the end, which differs from its suggested "allowed and inert").
- `.../role_based_permission_system_foundations/research_permission_ux_patterns.md`,
  `research_common_complaints.md`, and `.../educator-interface-5-permissions/research_permission_ux_patterns.md`.
- `.../educator-interface-full-polish/comparable-systems-learner-management.md` (per the idea).
- Mockup `Educator Cohorts and Admin.dc.html` screen 06 and mobile M09, screenshots in
  `spec_dd/3. done/2026-10-08_06:54_educator-interface-looks-good/design_screenshots/`
  (`educator-cohorts-and-admin__06-roles-and-permissions.png`).

## 2. Elsewhere: known failures in in-app role management

- **Assigning a role above your own (privilege escalation).** Weaviate CVE-2026-59093: the
  assign handlers checked whether the caller could assign roles to a target but not that the caller
  held the permissions inside the role, so a delegated assigner could give themselves the admin
  role. Foreman/Satellite CVE-2026-5136: group role assignment not validated against the caller's
  permissions, so a group manager could attach admin roles and join the group. Cerebrate
  CVE-2025-66385: the user-edit endpoint let a non-privileged user change `role_id`. WordPress User
  Management plugin CVE-2025-22736: privilege assignment without authorisation checks. Lesson:
  enforce the grant check on the server in the same place for every path (form, direct POST,
  re-scope), check the target's scope as well as the role, and test each role as grantor against
  each role as target. FLS's `_refuse_unless` does this centrally; the spec should require the
  view to call only the checked entry points and test with hand-made POSTs. Sources:
  - https://nvd.nist.gov/vuln/detail/cve-2026-59093
  - https://fieldguide.lutrasecurity.com/CVE-2026-5136/
  - https://www.sentinelone.com/vulnerability-database/cve-2025-22736/
- **Last-admin lockouts.** GitHub, Slack and Microsoft 365 refuse removal of the last owner or
  global admin; Microsoft advises at least two Global Admins because a lone locked-out admin is an
  outage. Details and URLs are in spec 5's `research_role_assignment_rules.md` (not repeated). FLS
  already locks and refuses; the new risk is the lockout seen from the UI: show why a removal is
  disabled-by-refusal rather than a bare error, and remember the organisation-admin guard only
  applies to non-site-level actors, so an organisation can still end up with no admin only via a
  site admin acting.
- **Stale and orphaned permissions (django-guardian).** Guardian's own caveats page: object
  permissions are not foreign-keyed to their target, so deleting the object leaves
  `UserObjectPermission` rows behind; a reused primary key can hand old grants to a new object.
  Remedy: delete the rows explicitly on object removal (view or signal), run
  `clean_orphan_obj_perms` as a backstop. FLS's `ObjectRoleAssignment` has the same generic-key
  shape plus guardian rows, so cohort deletion needs both cleaned. Sources:
  - https://django-guardian.readthedocs.io/en/stable/userguide/caveats/
  - https://django-guardian.readthedocs.io/en/stable/api/management/
- **UI confirmation of access changes.** The web search did not surface a specific incident for
  confirmation dialogs; the idea's escalation-confirmation requirement rests on the escalation CVEs
  above and spec 5's UX research rather than a cited failure.

Caveat: the CVE descriptions come from search-result summaries and the NVD pages were not opened.

status: ok
