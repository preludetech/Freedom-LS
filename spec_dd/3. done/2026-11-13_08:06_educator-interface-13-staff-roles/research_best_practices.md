# Best practices: scoped roles, staff membership, delegated admin, scoped people search

Note: written from established literature and Django practice, with reference URLs. Pages were not re-fetched in this run, so check wording before quoting.

## 1. Scoped per-object role assignment

- Model the grant as a (subject, role, object) tuple, unique on that triple. This is the core of ReBAC/Zanzibar-style systems and of "scoped role bindings" in Kubernetes (RoleBinding is namespaced, ClusterRoleBinding is global). FLS's `ObjectRoleAssignment` already matches. Keep org-wide grants as a separate, visibly different scope, not a magic cohort value.
  - https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/
  - https://kubernetes.io/docs/reference/access-authn-authz/rbac/#rolebinding-and-clusterrolebinding
  - https://csrc.nist.gov/projects/role-based-access-control
- UI: show one line per (role, scope set), not per person. Offer actions per grant ("Change role", "Remove from cohort") and per person ("Add role"). Show inherited (org-wide) access read-only with its source, as GitHub and Google Cloud IAM do. Inherited grants cannot be removed at the child scope.
- Deactivate rather than delete grants (soft state with timestamps). It keeps history and lets an "undo" be a re-assign. Re-assigning an inactive row should reactivate it, not violate the unique constraint (check `assign_role` does this).
- Role swap = revoke + grant inside one `transaction.atomic()` so a failure never leaves the person with no role or both. Two audit entries from one transaction is fine; give both a shared correlation id or the same request id in metadata so History can show them as one action.

## 2. Staff membership separate from role grants

- Keep "is a member of this tenant/org in a staff capacity" (membership) separate from "what can they do" (grants). Pattern seen in GitHub org membership vs team/repo roles, Slack workspace membership vs channel permissions, and django-organizations (`OrganizationUser` vs roles).
  - https://django-organizations.readthedocs.io/
- Membership: unique (user, organisation), plus `is_active`/`created_by`/timestamps. A role without a membership should be impossible (enforce in the service function `assign_role`, not only the UI), or the reverse must be explicitly defined. Removing membership cascades by calling `deactivate_role` per grant in one transaction (matches the answer: one audit entry per role), then writes its own `staff.removed` entry.
- Site-aware: put the membership on the site-aware base so it filters like other models. Index (organisation, user).
- Make "staff or not" a single query helper (`staff_of(org)`), so lists, search and permission checks cannot disagree.

## 3. Delegated administration

- Rule of thumb (NIST ARBAC97/ARBAC02 "can-assign" ranges, and least privilege): an admin may grant only roles at or below their own level, only within scopes where they hold that level. Encode as a function `grantable_roles(actor, target_scope)` returning the allowed roles. Use it both to build the dialog's role choices and to validate on POST. Never trust the form's role value.
  - https://csrc.nist.gov/projects/role-based-access-control (ARBAC literature)
  - https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html (deny by default, enforce server-side on every request, least privilege)
- Also guard revoke/change: an actor may only change or remove a grant if they could have made it (same function). Prevent self-lockout (last org admin cannot remove or downgrade themselves) and privilege escalation by changing their own role.
- OWASP A01 Broken Access Control: for every object id in a POST (user id, cohort id, grant id), re-check the actor's scope. IDOR is the main failure here.
  - https://owasp.org/Top10/A01_2021-Broken_Access_Control/
- Creating a new staff member is a higher privilege than granting a role (the answers restrict it to org admins). Make it its own permission check, separate from `grantable_roles`. The rule "no promoting a learner to staff if you hold cohort edit access" is a separation-of-duties rule: check it in the service layer.
- A new "organisation staff viewer" role works best as an org-scoped, read-only visibility grant. It widens what a person can see (the staff list) and never what they can grant. Keep grantable_roles independent of it.

## 4. As-you-type people search without enumeration

- Scope the queryset first, then filter by the typed text. Build the base queryset from what the actor may see (org staff membership, org learners, or the actor's cohorts' people), never `User.objects.all()` narrowed by text. Test with a user outside the scope and assert zero results.
- Exact-email lookup of any site user is an enumeration oracle by design (OWASP: user enumeration through differing responses). Mitigate:
  - Respond identically whether the email exists or not where possible, for example "If this person has an account they will be added", or only reveal name/chip after the actor submits, not while typing.
  - Require the full email (case-insensitive exact match). Never allow prefix/`icontains` search outside the scope.
  - Rate-limit the lookup endpoint per user (django-ratelimit) and cap results (eight, as in the idea). Require a minimum length (2) and only HTMX `GET` with `hx-sync="this:replace"`.
  - https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/03-Identity_Management_Testing/04-Testing_for_Account_Enumeration_and_Guessable_User_Account
  - https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#authentication-and-error-messages
- Exposed fields: return only name and email (what a chip needs), not ids of other organisations, roles or last login. Escape output (Django templates do by default).
- Search endpoint needs the same permission decorator as the Add-staff dialog; a viewer must get 403 and not an empty list.
- Log (audit) full-email lookups that hit an out-of-scope account? Optional, helps spot scraping; cheap if the audit table exists. Do not log keystroke-level queries.
- HTMX: use `hx-trigger="input changed delay:300ms"`, `hx-sync="this:replace"`, `hx-get` to a partial returning a result list; return 200 with empty-state text for no results. See https://htmx.org/examples/active-search/

## 5. Audit logging of permission changes

- Record: actor, subject user, role, scope (cohort/org), action verb, before/after, timestamp, request id. Append-only; never edited. OWASP logging guidance lists authorization changes as events that must be logged.
  - https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- Write the audit entry inside the same transaction as the change (`transaction.atomic`), so there are never changes without entries or the reverse.
- Use one service function per mutation (`assign_role`, `deactivate_role`, membership add/remove) that is the only writer, so UI, admin and any API all log the same way. Two entries for a swap (revoke then grant) is the standard, no `changed` verb needed.
- Repeating a no-op (assign an already-active role) should write nothing.

## 6. Django specifics

- Do checks in a service/permission layer called by views, not in templates. Templates only hide buttons; the view is the control. Use `get_object_or_404` on a scoped queryset (cohort limited to those the actor administers) so out-of-scope ids return 404, not 403, which leaks less.
- Wrap multi-row changes in `transaction.atomic()`; use `select_for_update` on the actor-count check for "last admin" to avoid races.
- Prefer `UniqueConstraint(fields=[user, target, role])` plus `get_or_create`/`update_or_create` in services; handle `IntegrityError` specifically.
- Libraries like django-guardian (per-object permissions) and django-rules exist, but FLS already has its own model; stay with it rather than adding a dependency.
  - https://django-guardian.readthedocs.io/
  - https://docs.djangoproject.com/en/stable/topics/db/transactions/

## Short checklist for the spec

1. One `grantable_roles(actor, scope)` function, used to render and to validate.
2. Staff membership model; service enforces role-requires-membership; removal cascades with one audit entry per role.
3. Search base queryset derived from actor visibility; full-email exact match is the only way to reach outside it; rate-limit and cap; identical response shape.
4. Org admin only for creating staff; refuse learner-to-staff for cohort-edit holders in the service.
5. Swap in one transaction, two audit entries, shared request id.
6. Guard last-org-admin removal/self-downgrade.
7. Tests: out-of-scope user never in results; forged user/cohort/role ids rejected; viewer gets 403 on every endpoint.

status: ok · reason: complete
