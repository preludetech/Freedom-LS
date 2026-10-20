# Reference implementations: educator and staff role administration

Topic: `reference_implementations`, for spec 9 (educator administration). Does not repeat the per-system staff role notes in `../../1. next/educator-interface-full-polish/comparable-systems-learner-management.md` (scope table, "Scoping educators", Appendix A and following). Read that first. This file adds the five things that note does not settle: add-by-email, which roles a granter may assign, last-owner protection, self-change rules, and how revocation is stored. It also covers the systems that note skips (GitHub, Slack, Thinkific, django-guardian and django-rules).

Confidence: items with a URL were read or returned by search on 2026-10-20. Items marked "(from knowledge)" were not re-fetched and should be treated as unverified. Several vendor pages did not answer the question; those gaps are listed at the end.

## 1. Add-by-email: existing user versus new user

| System | Existing account | No account | Pending state |
|---|---|---|---|
| Open edX | Admin types the email or username in Course Team / Instructor Dashboard Membership. | Refused. The person "must register a user account and activate" it first; lookup fails with "user couldn't be found". | None for staff (instant). |
| Canvas | Search by email, login ID or SIS ID, pick role and section. Creates an invitation shown as "pending" until accepted. | "Match not found", unless Open Registration is on; then it can invite a new user. | Yes, per course, until accepted. |
| Google Classroom | Owner enters email in People > Teachers; same-domain accounts only for Workspace. | Not possible; the account must exist in the domain. | Yes, "Pending" until the teacher accepts. |
| Thinkific | Admin creates the user form (name, email, role); roles include Site admin, Course admin, Group analyst. | Same form creates it. | Not confirmed. |
| Moodle | Pick from enrolled or all users in the role-assign screen. | Separate flow: Add a new user, then assign. | None; assignment is instant. |

Sources:
- Open edX: https://docs.openedx.org/en/ulmo/educators/how-tos/set_up_course/add_course_team_members.html and the search result summaries for https://docs.openedx.org/en/latest/educators/references/course_development/course_team_roles.html
- Canvas: https://community.canvaslms.com/docs/DOC-2878 (Instructure "How do I add users to a course?"), summarised via https://www.montana.edu/ecat/help/instructors/add-people and https://its.gmu.edu/knowledge-base/canvas-user-roles-and-adding-users-to-courses/
- Google Classroom: https://support.google.com/edu/classroom/answer/7477648 (transfer) and teacher guides such as https://source.mpls.k12.mn.us/google-classroom-add-a-coteacher-to-a-class
- Thinkific (via a college guide, not Thinkific's own docs): https://saultcollege.teamdynamix.com/TDClient/53/Portal/KB/Article/344/Thinkific-Creating-an-Account
- Moodle: https://docs.moodle.org/502/en/Assign_roles

Findings for FLS:
- Nobody offers a single "type an email, the system works it out" form that creates the account too, except Thinkific's user form. Open edX and Google reject unknown addresses. Canvas gates it behind a site setting. FLS's design (existing user matched, otherwise create through the spec 7 path with the setup email) is more permissive than every reference. The risk that follows is a typo creating a stray account and sending a setup email to a wrong address. The confirmation step should therefore show whether the address matched an existing person ("Existing user: Jane Doe") or will create a new account. This is the one place the references say to be explicit, because Canvas and Open edX both surface "found / not found" as the first feedback.
- Canvas and Google keep an explicit pending (invited, not accepted) state. FLS grants immediately, so the list should show "has not set up their account yet" using the spec 7 setup-email state, rather than a separate invitation model. This follows the Canvas "pending" marker already noted in the existing note.
- Open edX restricts adding people to the course Admin role: other staff "can edit the course and perform all tasks except adding and removing other team members and granting Admin access". That is the same shape as FLS's rule that cohort admins cannot administer educators.

## 2. Scoped grants

(Existing note covers Canvas "limit to section", Docebo Power User and Moodle contexts; not repeated.)

Additional details:
- Moodle assignments inherit downward: a role granted at category level applies to every course below it, and "local" assignments sit on an activity. Roles combine additively when a user holds several in one context, and changing someone's role does NOT remove the old one automatically; the admin must remove it by hand. Source: https://docs.moodle.org/502/en/Assign_roles. For FLS: the form should make "change role" an explicit replace (or forbid a second role per organisation), otherwise the stale-role trap Moodle users hit appears.
- Canvas roles are also additive across multiple enrolments. Source: the Montana and GMU pages above.
- Google Classroom has no scope narrower than one class (each class has its own teacher list). Open edX staff roles are per course. Both support the point that scope = a set of target objects is the norm; FLS's cohort set is the same idea.
- GitHub scopes at two levels: organisation roles (Owner, Member, Moderator, Billing manager, Security manager) and team roles (maintainer), with repository access per team or per repository. Custom organisation roles are Enterprise only. Source: https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/roles-in-an-organization. The lesson: even a very mature product keeps the preset list short and puts "what exactly can they reach" in a second, separate step (team or repo picker). That matches FLS's two-step add (role, then cohorts).
- django-guardian (from knowledge, unverified in this session): permissions are rows keyed by (user or group, permission, object) in generic-key tables; `assign_perm` and `remove_perm` create and hard-delete rows; there is no built-in "who granted it", timestamp or soft revoke. FLS's `ObjectRoleAssignment` with `assigned_by` and `is_active` already goes beyond this, and the guardian rows are a derived cache rebuilt by the sync. Generic foreign keys have no cascade on target deletion, so orphans are the application's problem. This confirms the orphan-grant cleanup concern in the idea (cohort deletion).
- django-rules (from knowledge): predicates evaluated at check time, no storage. It is useful for "may this actor grant this role" because that rule is computed from the actor's own roles, not stored. The grant rule is therefore best implemented as a single function (actor, target role, target scope) returning allowed or not, used by both the form (to filter the role dropdown) and the POST handler (to re-check). Every reference that hides options also re-checks server-side.

## 3. Which roles a granter may assign

| System | Rule | Source |
|---|---|---|
| Moodle | Explicit matrix "Allow role assignments": a row (my role) by column (role I may assign). By default teachers can assign only non-editing teacher, student and guest, not teacher. Some roles (Manager, Course creator) only exist at system level. | https://docs.moodle.org/502/en/Assign_roles |
| Open edX | Only course Admin may add or remove team members or grant Admin. Staff and limited staff cannot. | Open edX docs above |
| Slack | Ladder: Primary Owner assigns Owners; Owners assign Admins. Only the Primary Owner can delete the workspace or transfer primary ownership. Admins cannot see billing. The page does not say whether an Owner can demote another Owner. | https://slack.com/help/articles/360018112273-Types-of-roles-in-Slack |
| GitHub | Owners can change roles of other members and owners. "You can't change your own role." | https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/maintaining-ownership-continuity-for-your-organization |
| Google Classroom | Co-teachers can do everything the owner can except delete or archive the class, remove the primary teacher, or mute another teacher. Education leaders who visit a class get co-teacher permissions including "manage other co-teachers and the roster". | https://support.google.com/edu/classroom/answer/6020279 and the transfer article above |

Findings for FLS: the Moodle matrix is the most flexible but needs an admin screen; the ladder rule (assign your own level and below) used by Slack, GitHub and Open edX is the simple default. FLS's rule ("hand out your own level and below, within your scope; only site admins grant `site_admin`") is the ladder rule with scope added. Note the one asymmetry in every product: the top rung has an extra privilege no one else can take (Slack: delete workspace and transfer ownership; Google: remove the primary teacher; FLS: grant `site_admin`).

## 4. Last-owner protection

- GitHub recommends "no less than two" owners and says an organisation with one owner can become inaccessible. The cited pages state this as a recommendation, not an enforced rule, and the pages fetched did not say what happens when the last owner leaves (not confirmed). Sources: the two GitHub pages above.
- Slack avoids the problem structurally: there is always exactly one Primary Owner, and handing it over is a deliberate transfer, not a removal (https://slack.com/help/articles/360018112273-Types-of-roles-in-Slack).
- Google Classroom: the primary teacher cannot be removed or unenrolled; the owner role is moved by "Make class owner", which sends an invitation, stays with the old owner until accepted, cannot be undone after, and has a "Revoke invite to own" cancel while pending. Source: https://support.google.com/edu/classroom/answer/7477648
- Open edX docs do not describe protection (not confirmed).

Findings for FLS: two enforceable patterns exist. (a) Refuse the removal and say why and what to do ("Add another organisation admin first"). (b) Make top-rung change a transfer. FLS's settled rule is (a) with a nuance (organisation admins blocked, site admins allowed). The reference-backed refinements are to apply the check on every path that reduces the count (remove, and scope or role change that would demote), to run it inside the same transaction as the write, and to show the explanation in the UI rather than just hiding the button (see the open question on the user's own row). Slack and Google's "transfer, don't remove" can be offered in prose as the way out, without building a transfer feature.

## 5. Self-demotion and self-change

- GitHub: "You can't change your own role" (owners edit others only). Source: the continuity page above.
- Google Classroom: the owner cannot be removed; a co-teacher can leave (from knowledge, unverified).
- Moodle: administrators can alter their own assignments; no guard (from knowledge, unverified).
- Slack: not covered by the fetched page.

The idea's "nobody changes their own roles" matches GitHub. A useful complementary detail from the references is that leaving is different from being changed: GitHub, Slack and Google all have a separate "leave" action for yourself. FLS has none and the idea does not ask for one; do not build it, but the list's explanatory text for your own row can say "Ask another administrator to change your access".

## 6. Revocation storage (soft versus hard)

- django-guardian: hard delete of the permission row, no history (from knowledge).
- Moodle: role assignments are deleted; history exists only in the logs report. The existing note records that the Logs report is staff-visible.
- Open edX: course-access roles are rows that are deleted on removal; the existing note records `ManualEnrollmentAudit` for enrolment only, not for staff role changes (from knowledge, unverified for staff roles).
- Google Classroom: invitations have a state (pending, revoked); removal drops the teacher record, with the audit log in the Admin console recording it (existing note).
- FLS: soft deactivation with `is_active` and `assigned_by` is more than most references keep. Two consequences to specify: re-adding a person who has an inactive row should reactivate or create a fresh row consistently, and "added by" and "added on" in the list must come from the active row only; and who removed it plus when should be in an audit log, because `assigned_by` records only the granter, not the remover.

## 7. List columns and filters seen in references

- Canvas People page: name, login ID, SIS ID, section, role, last activity, total activity; filter by role; search by name or email; pending users labelled. Source: the Canvas documents above (columns from knowledge; the guides fetched confirm pending and section).
- Open edX Course Team: list of members per role with email and an X to remove (from knowledge).
- Google Classroom People: teachers section with owner marked, pending shown, per-row menu (More) (transfer article above).
- Slack members page: name, account type, last active, filter by account type (from knowledge).
- GitHub people: avatar, name, role, 2FA state, teams count, filter by role (from knowledge).

For FLS the idea's columns (name, email, roles with scope, added by, added on) cover the common set. Two columns the references add that FLS lacks and might consider: a status marker (pending, matching Canvas and Google) and last activity (Canvas, Slack). The pending marker is cheap and supported by the existing note; last activity is more speculative and not requested. Not building last activity is consistent with "don't build functionality not requested".

## 8. Implications to carry into the spec (summary)

1. Show whether the email matched an existing person or will create one, before confirming (Canvas, Open edX "not found" feedback).
2. Reuse one grant-check function for the form and the POST handler (Moodle matrix, django-rules style); filter the role dropdown by it.
3. Make "change role" a replace, or document that roles in one organisation are additive (Moodle trap).
4. Enforce last-owner protection on all paths that reduce the count, in the transaction, and explain it in the UI.
5. Self-change is blocked (GitHub); show your own row without actions and with a one-line reason.
6. Revocation is soft; record who removed it and when in the audit log, since `assigned_by` only holds the granter.
7. Cohort deletion must clean up orphaned generic-key assignment rows (guardian has no cascade).
8. Pending marker in the list from the setup-email state, not a new invitation model.

## Gaps

- Docebo and TalentLMS staff-role administration were not re-researched here; the existing note's appendix covers them.
- Thinkific's own help centre did not return; only a third-party college guide did.
- Canvas's own Instructure page returned the wrong content (an Inbox article), so Canvas details come from university guides that quote or adapt it.
- The GitHub pages fetched did not state what happens to the last owner. Search the GitHub docs "Removing yourself from an organization" if the spec needs this.
- Google's co-teacher help page did not list invitation steps; they come from search summaries of teacher guides.

status: ok
