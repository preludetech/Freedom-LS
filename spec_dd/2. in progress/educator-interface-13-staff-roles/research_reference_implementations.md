# Reference implementations: staff roles and add-person pickers

Written from working knowledge of each system's public docs (not re-fetched this session). Reference URLs are the docs to confirm against. Each system keeps its own terms.

## Moodle
- Role assignment is per context: system, category, course, (also module, user). A person is "assigned" a role in a context and it inherits downward. Roles are separate from site accounts. Site-wide "Manager" or category-level roles are the org-level analogue.
- Assign-roles screen in a course lists only users already enrolled (or, for non-course contexts, a capability-limited set). Moodle also has `moodle/role:assign` plus an "allow assign" matrix: a role may only assign roles listed for it (own level and below).
- Borrow: the "who may grant which role" matrix is the same idea as the answer "viewer or admin, own level and below, inside own scope". Inheritance shows org-wide roles as read-only at the cohort level, matching the answer.
- https://docs.moodle.org/en/Roles_and_capabilities , https://docs.moodle.org/en/Assign_roles , https://docs.moodle.org/en/Role_assignment_matrix (allow-assign)

## Canvas
- Course enrollments carry a role type (TeacherEnrollment, TaEnrollment, DesignerEnrollment, ObserverEnrollment). One user holds several enrollments, each on its own course. Account admins are a separate model (account-level admin role grants), independent of course enrollments.
- "Add People" in a course takes emails/logins typed or pasted; it does not search the whole account. Account admins have a separate user search. Whether non-admin teachers can add depends on a permission ("Add/remove other teachers").
- Borrow: account admin separate from course enrollment confirms the separate-membership-versus-role split. Typed email as the way to reach people outside your scope. Removing from a course deactivates (soft state), not deletes.
- https://canvas.instructure.com/doc/api/enrollments.html , https://canvas.instructure.com/doc/api/admins.html , https://community.canvaslms.com/t5/Canvas-Basics-Guide/How-do-I-add-users-to-a-course-as-an-instructor/ta-p/1085

## Open edX
- Course team roles: Staff and Admin (course access roles), plus Instructor/Staff in the LMS instructor dashboard. Roles are rows of (user, role, course_id, optional org). Org-wide roles exist by leaving course_id empty and setting org. Course Team "Add a new team member" takes an exact email or username; no type-ahead. Only an Admin can add/remove other Admins.
- Borrow: single row model (user, role, scope) matches `ObjectRoleAssignment`. Exact-email add is the status quo FLS wants to improve on. Rule "only admin grants admin" echoes own-level-and-below.
- https://docs.openedx.org/en/latest/educators/references/course_development/course_team_roles.html (confirm path) , https://github.com/openedx/edx-platform/blob/master/common/djangoapps/student/models/user.py (CourseAccessRole)

## GitHub orgs
- Org membership (member, owner) is a record separate from repo/team permissions. You can invite someone to an org with no repo access; team and repo permissions (read/triage/write/maintain/admin) are granted separately and per repo. Removing from the org strips all their team and repo access. Outside collaborators are people with repo access but no org membership.
- Invite picker: type-ahead search over all GitHub, which is public; for adding to a team/repo it searches org members only. Invite by full email also works for non-users.
- Borrow: this is the closest match to the new model: org staff membership (no roles required), roles granted separately, and removing the membership deactivating every role (the answer). Searching only org members when adding to a team (not the whole site), with full email as the way in from outside.
- https://docs.github.com/en/organizations/managing-membership-in-your-organization/removing-a-member-from-your-organization , https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization , https://docs.github.com/en/organizations/organizing-members-into-teams/adding-organization-members-to-a-team

## Google Workspace
- Admin roles are assigned to users already in the org's directory. The admin-role assignment picker searches the org's own directory only; external addresses are not searchable. Delegated admin roles are scoped by organisational unit ("scope": all org or one OU). "Prebuilt roles" such as Groups Reader, User Management Admin, and a custom role builder. Read-only roles exist (e.g. Help Desk Admin, Services Admin; Groups Reader).
- Borrow: a read-only "directory viewer" role is the precedent for the "organisation staff viewer" role (visibility of the people list as a grantable privilege, separate from edit rights). Search scope = own directory, never global.
- https://support.google.com/a/answer/2405986 (admin roles) , https://support.google.com/a/answer/2406043 (prebuilt roles) , https://support.google.com/a/answer/9807615 (delegated roles)

## Picker patterns (cross-system)
| Question | Practice | For this spec |
|---|---|---|
| Search scope | Org-own directory (Google, GitHub team add); none/exact only (Open edX, Canvas course add) | Org's learners + staff only; widen for cohort admins only by the staff-viewer role |
| Outsider | Exact identifier or invite | Full email resolves through `lookup_user`, never listed |
| Min chars | GitHub/Google start at 1-2 | Two chars, 300 ms debounce, cap eight, as in idea |
| Enumeration guard | Only exact match on full email for non-members | Never return site-wide matches; consider no match-count leak for outsiders (same response whether or not the account exists, if full email typed and absent) |
| Who may add | Admin-only add of admins (Open edX); allow-assign matrix (Moodle); permission flag (Canvas) | Org admin creates staff; cohort admin grants viewer/admin on own cohorts to staff they can see |

## What this spec can borrow
1. Separate org staff membership from role grants (GitHub, Canvas admins, Moodle system context); membership removal cascades to deactivating all roles.
2. A grantable read-only "see the people list" role (Google directory-style read roles, GitHub member visibility), matching the organisation staff viewer role.
3. Inherited roles shown read-only in the narrower scope (Moodle context inheritance).
4. Grant-ceiling rule: you grant only your own level or below within your scope (Moodle allow-assign, Open edX).
5. Type-ahead restricted to the org's own people with exact full email as the escape hatch (GitHub, Google); do not leak whether an outsider's account exists beyond what `lookup_user` already does.
6. Per-scope soft deactivation (Canvas) is what makes two audit entries (deactivated then assigned) natural.

Caveat: reference behaviours are from memory and doc structure; URLs marked "confirm path" may have moved.

status: ok · reason: written from knowledge, URLs not re-fetched
