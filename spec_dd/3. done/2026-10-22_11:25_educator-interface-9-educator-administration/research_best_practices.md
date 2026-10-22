# Research: best practices for in-app staff/role administration

Scope: the educators section (list, add by email, scoped roles, change scope, remove, escalation, last-admin, immediate revocation). Web sources are cited. Items marked (general practice) are established engineering practice that I did not verify against a fetched page in this run. Each one still needs a decision in the spec.

## 1. Web-sourced findings

1. **Deny by default, enforce on every request.** OWASP says the application should be configured to deny access by default, and that permission must be validated correctly on every request. It also says to check access per object, not per object type.
   - Apply to this spec: every POST (add, re-scope, remove) re-checks the actor's grant rights server-side against the target role and the target cohorts. Hiding buttons is not the control. Cohort ids in a POST must be re-validated as belonging to this organisation.
   - Source: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html

2. **Least privilege and periodic review.** OWASP: grant the minimum needed. It notes that granting is easier than taking away, and that privilege creep is a risk. The list screen (added by, added on, scope per row, role filter) is the review tool, so keep those columns.
   - Source: same OWASP Authorization page.

3. **Logging is a key detective control.** Every grant, scope change and removal should be recorded with actor, target, role, scope before and after, and time. The idea already says the role description strings are shared with the audit log. Keep one source of truth for those strings.
   - Source: same OWASP Authorization page.

4. **Owners cannot change their own role, and orgs should keep at least two owners.** GitHub does both. Owners can change other owners' roles but not their own. GitHub recommends two or more owners so the org does not become inaccessible. This supports the "nobody changes their own roles" rule and the last-admin protection. A second admin is the recovery path, so show a hint when only one admin remains.
   - Source: https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/maintaining-ownership-continuity-for-your-organization

5. **Account enumeration.** OWASP says registration and recovery flows should not reveal whether an account exists. Responses, status codes and timing should be uniform. This is a public-flow rule. For a staff-only add form behind authentication and a grant permission, the practical stance is below in section 3.
   - Source: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html

6. **Re-authentication for sensitive changes.** OWASP recommends re-authentication for sensitive actions. Granting organisation admin or site admin is such an action. The idea asks for explicit confirmation, which is probably enough, but a spec could choose to record that password re-entry was considered and rejected.
   - Source: same OWASP Authentication page.

## 2. General practice (not fetched this run)

**Privilege escalation**
- Compute the set of grantable roles from the actor's own highest level, with the scope clipped to the actor's scope. Use one function for both rendering the form choices and validating the POST, so the two cannot drift.
- Compare grants as a lattice: `site_admin` > `organisation_admin` > `cohort_admin` > `cohort_viewer`. "Widening" is any change where the new effective permission set is not a subset of the old one. That covers a new role, a higher role, an added cohort, or cohort scope replaced by organisation scope.
- Treat a role change as add-then-remove inside one transaction, so a failure never leaves the person with no role or an extra one.

**Self-modification**
- Block it in the service layer, not only in the UI. Compare the actor's user id with the target's. Show the own row without actions and with a short reason, as the idea leans towards.

**Last-admin lockout and races**
- Do the check and the deactivation in one `transaction.atomic()` block. Lock the relevant active admin assignment rows with `select_for_update()` before counting. Two admins removing each other at once would otherwise both see "two admins left" and both succeed. Re-count after the lock and abort if the count would reach zero.
- Locking the set of active admin rows for the organisation, rather than just the target row, is the part that closes the race. A unique partial constraint cannot express "at least one", so the lock plus the count is the usual approach.
- The same rule applies to a scope change that would drop a role, and to deactivating a user account elsewhere. Note that spec 5 may own the account-deactivation case.
- Return a clear, non-technical error for the rejected case, with HTTP 422 for HTMX per the project conventions.

**Soft delete and audit**
- Deactivate (`is_active=False`) and keep `assigned_by`. Add who revoked and when, if the models do not hold that already. Re-adding later should create a new active row or reactivate one by a single rule, which the spec should state, so history is not ambiguous.
- Make the permission sync (guardian) part of the same transaction as the deactivation, so the two never disagree.

**Immediate revocation for open sessions**
- Since permission checks read the database on each request, revocation applies on the next request with no session invalidation needed, provided nothing caches permissions per session. Verify that guardian and any per-request or per-user caches do not outlive the request. Test: grant, load a page, revoke, repeat the action, and expect the spec 5 denied response.
- HTMX partial requests must hit the same checks as full pages, and should show the denied experience rather than a blank swap.

**Add by email**
- Normalise (strip, lower-case) before matching. Match on case-insensitive exact email only, not a prefix search, so the form cannot be used to browse the user base.
- The actor has already authenticated and been authorised to add staff, so telling them "this person already has an account" is a usability need and a low risk. Do not offer autocomplete of users from other organisations. In a multi-tenant system with site-aware users, match within this site only.
- For a new address, send the setup email and say so. Do not echo anything that reveals details of an existing account beyond name and email already visible to org admins.
- Rate-limit the add action to slow bulk probing. Whether to do so is a spec decision.
- Reject adding a person who already holds the same role and scope with a friendly message rather than a duplicate row.

**Confirmation UX**
- Use two kinds: a plain confirmation for removals (names what is lost) and a stronger one for widening (names what is gained). State the outcome in words from the role descriptions. Make the confirm step server-rendered, and carry a signed or re-derived summary so the final POST is validated again, not trusted.
- Use a confirm step for the last admin removal as well as a block where it is not allowed.

**Orphans**
- Generic-foreign-key assignment rows have no cascade. Deleting a cohort should remove its object-role rows and guardian permissions in the same transaction as the delete (a signal or an explicit service step). Add a test that deletes a cohort and asserts no active assignment remains. A role with cohort scope and no cohorts left should be flagged in the list, or removed, per a spec rule.

## 3. Suggested decisions for the spec

- One service function per operation (add, re-scope, remove), each atomic, each doing the permission check, the last-admin check and the audit write. Views stay thin.
- A single "grantable roles and scopes for actor" helper that drives both the form and validation.
- A pure function "is this change a widening" used by the confirmation step and unit tested.
- Concurrency tests using the last-admin rule (use `transaction=True` tests, or assert the lock query is issued).
- Keep the own row visible but inactive, with the reason.

status: ok
