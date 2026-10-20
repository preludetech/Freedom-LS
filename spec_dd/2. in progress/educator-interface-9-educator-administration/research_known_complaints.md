# Research: known complaints about staff and role administration

Topic `known_complaints` for spec 9 (educator administration). Sources are web search results; the vendor pages were read through search summaries, not fetched in full, so treat details as indicative. Complaints are grouped by theme. Each says what it implies for this spec. Terms for other systems are theirs; FLS terms are used for implications.

## 1. Roles whose power is hard to see or predict

**Moodle: layered roles, overrides and "prevent" resolution are opaque.** Teachers could not find or use "override roles". The fix needed an admin to change a hidden capability setting elsewhere. Conflicting allow/prevent resolves by walking up contexts, and PROHIBIT cannot be undone below.
- https://moodle.org/mod/forum/discuss.php?d=78416
- https://moodle.org/mod/forum/discuss.php?d=60416
- https://docs.moodle.org/en/Override_permissions

Implication: keep exactly four roles, with no overrides and no per-permission editing (already out of scope). Show the one-sentence description wherever a role is named: the picker, the list, the confirmation and the audit log. State the cohort scope in words next to the role ("Cohort admin for Cohort A, Cohort B"). Do not rely on users learning a model.

**Canvas: account vs sub-account scope and who can assign what.** Sub-account admins were denied permissions because users belong to the root account. Some permissions never apply at sub-account level. Custom roles were hard to assign there, with some functions reserved for the account admin. Staff said permission changes can take 30 minutes or more to apply.
- https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Sub-account-admins-being-denied-permissions/m-p/155058
- https://community.canvaslms.com/t5/Canvas-Question-Forum/Sub-Account-Permissions/m-p/615960
- https://community.canvaslms.com/t5/Canvas-Resource-Documents/Account-and-Sub-Account-Role-Comparison/ta-p/387045

Implication: the form must offer only the roles the current user may grant (already settled), and explain why a role is missing. For example, "Only site admins can grant site admin" can sit as help text, so people do not hunt for it. Changes should take effect on the next request, with no caching delay. Test that the guardian sync runs in the same transaction as the change.

## 2. Accidental lockout and removing the last admin

**GitHub: sole owner leaves, org is orphaned.** Third-party write-up of a community case: a sole owner left and no one could manage members, repos or billing. Official docs cover leaving but not this case.
- https://devactivity.com/insights/github-organization-lockout-recovering-from-sole-owner-exit-and-why-proactive-monitoring-matters
- https://docs.github.com/en/enterprise-server@3.14/account-and-profile/how-tos/organization-membership/removing-yourself-from-an-organization

**Slack: primary owner transfer is required and recovery is gated.** Only the primary owner can transfer ownership. Recovery through support is limited to workspaces created for a legal entity.
- https://slack.com/help/articles/204401633-Transfer-ownership-of-a-workspace-or-org

**Google Workspace: super admin lockout.** Many forum and blog reports of locked-out super admins. Recovery needs a second super admin, or a support form with DNS verification.
- https://discuss.google.dev/t/super-admin-locked-out-for-workspace/370825
- https://university.tenten.co/t/how-to-fix-google-workspace-admin-lockout/2069

**Google Classroom: primary teacher cannot be removed.** A primary teacher must hand over ownership first. The API has a `CannotRemoveTeacherWithNoCourseOwner` error when the owner's account is deleted. A co-teacher who owns the Drive folder must transfer it before removal.
- https://support.google.com/edu/classroom/answer/6069576
- https://developers.google.com/workspace/classroom/reference/addons_errors

Implication: the idea's last-admin rules are the right ones. Enforce them in the service function, not only the UI, so races and a second tab cannot bypass them. Count only active assignments. Run the check inside the transaction with a row lock, so two admins removing each other at the same moment cannot both succeed. Explain the refusal in words ("add another organisation admin first"). Block self-change on the server too. The last-site-admin rule covers re-scoping and deactivation, not only the Remove button.

## 3. Wrong email and duplicate accounts from case differences

**Case-sensitive email matching creates duplicates and duplicate invites.** Reported in DataHub (one account per casing variant), the Drupal invite module, GitLab (mixed-case invites that produced duplicate invites with different access levels), Mendix, and Databricks (an invite only works when casing matches exactly, possibly also stray whitespace).
- https://support.datahub.com/hc/en-us/articles/52984735650331-Duplicate-User-Accounts-Created-by-Case-Sensitive-Email-Matching-in-DataHub
- https://gitlab.com/gitlab-org/gitlab/-/issues/460708
- https://www.drupal.org/node/475004
- https://support.mendix.com/hc/en-us/articles/28273226096028-XSUAA-authentication-module-performs-case-sensitive-user-matching-causing-duplicate-accounts-or-login-failures
- https://community.databricks.com/t5/data-engineering/error-inviting-user-to-workspace-quot-failed-to-add-user-a-user/m-p/10734

**Invite goes to a different address than the one the person uses.** Robin and Auth0 show that signing in with a different identity than the invited one fails, and may burn the invite.
- https://support.robinpowered.com/hc/en-us/articles/206920793
- https://community.auth0.com/t/errorcase-failed-invite-accept-invalidates-the-invitation-and-doesnt-allow-users-for-a-retry/80350

Implication: strip whitespace and match case-insensitively on lookup, as the idea says. Also check what spec 7's shared creation path stores, and whether the user table enforces case-insensitive uniqueness. If it does not, a pre-existing mixed-case duplicate is possible, so decide what the form does when two users match. Use the shared path so spec 7's setup email is the only creation behaviour. On the confirm step, show the matched existing user, or "new account will be created for x@y", so a typo is visible before it is sent. Removing a role must not delete the account, so a wrong-email mistake is recoverable.

## 4. No visibility of who granted access, no audit trail

Canvas, Moodle and GitHub admins repeatedly ask for "who changed this and when". The models already carry `assigned_by` and `is_active`. Canvas and Google also publish role-comparison PDFs because the console does not show what a role can do (https://community.canvaslms.com/t5/Resource-Documents/Canvas-Account-Role-Permissions-PDF/ta-p/387078). This is a common-pattern inference; no single thread was found.

Implication: the list shows added by and added on (already settled). Removal sets `is_active` false and keeps the row, so the history survives. Record who removed an assignment and when, and who changed scope, if the model does not already do that. Check whether spec 5 or an earlier spec owns the audit log, and if so reuse its strings. Note that `assigned_by` can be null for shell or QA-helper grants, so the list needs a readable "unknown (set up by system)" value, not a blank.

## 5. Revoked users keep access in open sessions

Canvas notes permission changes can take 30 minutes or longer to apply (see section 1). The idea covers this by sending the person to the spec 5 denied experience on the next action.

Implication: every educator-interface view and HTMX endpoint must re-check permissions on each request, with no role caching in the session. Test removal with a second client that already has a page open, and test both a full page and an HTMX partial. The denied response for an HTMX request must be rendered usefully, not as an empty swap.

## 6. Too many clicks to scope to many groups

Canvas sub-account complaints (section 1) show that scoping by hierarchy is painful. A site with many cohorts means ticking each one. No direct thread was found on Moodle or Blackboard bulk enrolment of staff to groups, but it is the standard reason for bulk tools.

Implication: the cohort picker needs search, a visible selected list with a count, and perhaps "select all active cohorts" and "clear". Changing scope should be add/remove on the existing grant, as the idea says, not delete and re-create. Selecting all cohorts is different from the organisation role. State that in the picker, or people will use it as a workaround for becoming an organisation admin. This is an inference to confirm with the user.

## 7. Staff who are also students

Canvas advises that an admin who also holds a student role in a course can still see admin features, and recommends a separate account to avoid permission conflicts (https://canvas.rutgers.edu/documentation/support/account-admin/).

Implication: the idea allows one person to hold both. The risk is that a person sees their own marks or preview data with educator-level reach. Define in the spec what the learner interface shows for such a person, and test that an educator role does not leak into learner views and vice versa. The "also a learner" marker is the right low-cost cue. Check that removing an educator role leaves the `Learner` untouched, and that deactivating a learner (spec 7) leaves the educator role alone.

## 8. Dependencies that block removal

Google Classroom's drive-folder ownership and "no owner" errors show that removal can be blocked by hidden things the person owns. Source as in section 2.

Implication: check what in FLS references the assigning or assigned user (`assigned_by` on other people's rows, content authorship, notes). Removing someone who granted others' roles must not cascade. Because assignments are deactivated rather than deleted, `assigned_by` should survive.

## 9. Escalation and confirmation fatigue

GitLab's duplicate invites with different access levels (https://gitlab.com/gitlab-org/gitlab/-/issues/460708) show that two paths to the same person can leave a higher level in place unnoticed. No direct thread was found on confirmation fatigue. The inference is that a confirmation on every change gets clicked through.

Implication: if the same email already holds a role, say so and offer to change it, not to add a second grant. Reserve the explicit "widening" confirmation for real widening so it keeps its meaning. Plain removals and narrowing get a short, named confirmation. Consider whether adding a role to someone who already holds a lower one is widening, and treat it as such.

## Gaps

- No Blackboard, Teachable or Thinkific complaints were found in the searches. Searches were stopped after Moodle, Canvas, Google, GitHub, Slack and the invite/case threads.
- No G2 or Capterra review excerpts were gathered.
- No Google Classroom co-teacher numeric limit was found; a Code.org page says 5 co-teachers per section for that product (https://support.code.org/hc/en-us/articles/228116368).

status: ok
