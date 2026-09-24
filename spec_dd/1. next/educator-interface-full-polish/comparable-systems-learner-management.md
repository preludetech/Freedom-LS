# Comparable systems: learner-management actions

Research for specs 6 to 9 of the educator interface rebuild (see `spec-order.md`). The question was: what do comparable systems let school staff do to administer learners, cohorts, course registrations and other staff, which actions are common versus long-tail, which are bulk-only, and what reversibility and audit do users expect?

The question: what do Moodle, Canvas, Open edX, TalentLMS, Docebo, LearnDash and Google Classroom let
staff do to administer learners, cohorts, course registration and other staff? Which actions are
common, which are long-tail, which are bulk-only, what audit and reversibility do people expect, and
what do they complain about? Then compare against the capability list in the map's Notes.

Deadlines, communications, application review and retakes are excluded.

This extends two earlier notes, now at
`../educator-interface-7-learner-administration/research_lms_educator_ux.md` and
`../educator-interface-5-permissions/research_permission_ux_patterns.md`. `research_lms_educator_ux.md` covered cohort structure, adding
learners, CSV-with-preview and general UX complaints, mostly from secondary blog sources.
`research_permission_ux_patterns.md` covered hide-vs-disable and role-assignment UI. Neither looked at
exact action semantics, reversibility or audit, and neither used first-party docs. This note does both.

Other products' words are kept where they name a product feature ("enrolment", "section", "branch",
"student"). FLS terms are used everywhere else: learner, registration, cohort, organisation.

## Method and confidence

Three parallel passes read official help centres, developer docs, source and issue trackers
(docs.moodle.org, tracker.moodle.org, docs.openedx.org, Instructure guides and API docs,
support.google.com, help.talentlms.com, help.docebo.com, LearnDash docs now hosted at
docs.nexcess.com). help.talentlms.com and help.docebo.com refused direct fetches (403), so those
claims come from search-engine extracts of the official pages. The full per-system notes, with a URL
on every claim and "unverified" flags, are in the appendices. Where a claim below rests on an
unverified or community source, it says so.

## 1. What the systems offer

| Action | Moodle | Canvas | Open edX | TalentLMS | Docebo | LearnDash | Google Classroom |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Create account for someone | yes, single + CSV | via SIS / invite | no, learner self-registers | yes, single + CSV | yes, single + CSV | WordPress core | no, invite only |
| Existing account on import | 4 explicit modes, preview | links existing login | n/a | upsert by username | opt-in "update existing" | n/a | n/a |
| Suspend / deactivate account | yes, reversible | "suspend" login, reversible | not found | yes, reversible, can schedule | yes, plus expiry date | not native | n/a (domain admin) |
| Delete account | anonymises, irreversible | restorable in Admin Tools | GDPR retirement only | irreversible after 300-user undo window | irreversible, also deletes uploads | WordPress core | n/a |
| Merge duplicate accounts | plugin only (MDL-24443 open since 2010) | yes, split within 180 days | no | no, manual workaround | yes, loses archived enrolments | no | no |
| Log in as a learner | yes | yes, both users logged | "view as" preview only | yes | yes, logged in audit trail | no | no |
| Cohort/group create | yes, single + CSV | sections | yes | groups, branches | groups, branches | groups | a class is the group |
| Cohort/group delete | yes, no undo | only if empty | never | yes | yes | yes | archive first, then delete, no undo |
| Cohort archive | no | no | no | no | no | group end date | archive, restorable |
| Move member between groups | no, remove + add | "edit sections" | yes | via mass add/remove | CSV branch move | arrow lists | n/a |
| Registration: deactivate vs remove | suspended vs unenrolled | inactive vs concluded vs deleted | enrolled vs not | not documented | suspended status | not documented | removed only |
| Registration access dates | per-enrolment start/end | term/section end concludes | no | expiry = enrolment + limit | active from/until, per learner override | group end date | no |
| Group-level registration | cohort sync, living link | sections | cohorts | groups | enrolment rules by group/branch | course added to group | the class |
| Staff roles and scope | per context (site/category/course) | course roles, custom roles, sub-account admins, limit to section | course roles only | custom user types | Power User profiles scoped to users/groups/branches | Group Leader, basic vs advanced | owner + co-teachers, transfer ownership |
| Bulk actions hub | Bulk user actions (add to cohort, delete, force password change, download) | People page bulk (enrol, delete, suspend) + SIS CSV | batch enrol box is the only UI | mass actions (activate, deactivate, delete, add/remove group, add/remove branch) | mass actions (add to branch, activate, deactivate, edit fields, delete) | group CSV (add-on) | none for teachers |
| Roster export | yes | yes (course roster CSV) | yes | yes | yes | group reports | no |
| Staff-visible audit log | Logs report | Admin Tools logging, masquerade logged | tracking log + ManualEnrollmentAudit | Timeline, CSV export | Audit Trail app, immutable | none | Admin console audit log |
| Pending invitations | n/a | "pending" state, resend (24h throttle) | pre-assign emails to cohorts | n/a | n/a | n/a | invite + class code, reset code |

## 2. Common versus long-tail

Common means at least five of the seven expose it to non-developer staff.

Common:

- Add a learner, both one at a time and by CSV. Every CSV importer has to decide what happens when the
  account already exists.
- Remove a learner reversibly (suspend, deactivate, inactive) as a separate action from deleting them.
  Six of seven have the reversible action. The odd one out, Open edX, has only unregister and GDPR
  retirement.
- Group-level registration, where adding someone to the group registers them for the group's
  courses.
- Group create, add member, remove member.
- Staff role assignment with a scope narrower than the whole site.
- Bulk add-to-group and bulk activate/deactivate from a filtered list.
- Roster export as CSV.
- A staff-visible record of who did what. Five of seven have one. LearnDash has none, and Open edX's is
  an event stream rather than a screen.

Long-tail (two or three systems, or clearly admin-only):

- Merge duplicate accounts. Moodle has kept it out of core since 2010 (MDL-24443, left to the `tool_mergeusers` plugin). Where it
  exists it loses data (Docebo) or needs an undo window (Canvas, 180 days).
- Log in as a learner. Four of seven, always gated to the top admin role, always logged. Canvas users
  have asked for years for sub-account admins to get it
  (https://community.canvaslms.com/t5/Idea-Conversations/Act-as-User-Masquerade-for-Sub-Account-Admins/idi-p/414164).
- Rule-based automatic registration (Docebo enrolment rules, TalentLMS automations). Docebo's own docs
  admit rules cannot unregister.
- Self-join codes (Google class code, TalentLMS group key).
- Scheduled account deactivation (TalentLMS "deactivate at", Docebo expiry date).
- Cross-listing or combining groups (Canvas).

## 3. Bulk-only and bulk-first

- CSV import is bulk-only everywhere, and it is where account creation, "existing email" handling and
  group assignment meet. Moodle's Upload users does all three in one pass, with a preview.
- Open edX's batch enrolment box is the only enrol/unenrol UI. One learner is a batch of one. That is
  a reasonable pattern: one form, one to many emails.
- Group-level registration is bulk by nature.
- Docebo runs any mass action over 250 users as a background job. None of the others document a
  threshold, but their CSV imports are all asynchronous.
- Bulk actions come in pairs where they are liked and alone where they are complained about. Moodle
  has bulk "add to cohort" but not "remove from cohort" (MDL-61007) or bulk unenrol for teachers
  (https://moodle.org/mod/forum/discuss.php?d=166158, recurring since Moodle 2.0). TalentLMS has every
  add paired with a remove. The lesson is that a bulk add without a matching bulk remove gets noticed.

## 4. Audit and reversibility

The pattern is the same in every system that does it well:

1. A reversible "off" state is the default removal. Moodle suspend, Canvas deactivate, TalentLMS and
   Docebo deactivate all keep every record, and flipping the flag back restores the learner exactly.
   TalentLMS's docs describe deactivation as the safe alternative to delete.
2. Delete is separate, harder to reach, and warned about. Moodle anonymises the account. Canvas says
   of a deleted enrolment "there is not any way to undo" it. Google requires a class to be archived
   before it can be deleted. Canvas refuses to delete a section with learners in it. Open edX does not
   let anyone delete a cohort at all.
3. Where delete exists, the good systems add a way back. Canvas restores deleted users and courses from
   Admin Tools. TalentLMS keeps the last 300 deleted users restorable. Canvas lets a merge be split for
   180 days.
4. Removing a registration should not lose progress. Open edX does this best: unenrolled state "remains
   in the database and is reinstated if the learner does re-enroll", with no checkbox. Moodle recovers
   grades only if a "Recover user's old grades" box is ticked, and it is off by default. That is the
   trap to avoid. FLS already behaves like Open edX (progress survives learner deactivation,
   membership removal and registration deactivation, per `better_course_progress_tracking`), so the
   confirmation step can say so plainly.
5. People expect a log they can read without a developer. Docebo's Audit Trail is described as "an
   immutable record ... of administrative actions", recording who, what and when, including the real
   person behind an impersonation. Google's Classroom audit log is marketed for questions like "who
   removed a student from a class". Canvas logs both users on every masqueraded call. Open edX makes
   staff type a reason to unenrol someone and stores it (`ManualEnrollmentAudit`).

Nobody offers a general undo button. Reversibility comes from the data model (flags instead of
deletes), not from an undo feature.

## 5. What users complain about

From first-party trackers and idea boards. Vote counts and current status were not confirmable after
Instructure's community migration.

- No bulk remove to match bulk add: Moodle MDL-61007, Moodle teacher bulk-unenrol threads, Canvas "Bulk
  Delete Users" idea, Canvas threads on removing many users at account level.
- No direct move between groups: Moodle forum (remove and re-add is the workaround); Canvas idea "Bulk
  Combine Students from Multiple Sections into One Section".
- Duplicate accounts with no merge: Moodle MDL-24443, TalentLMS's own help page describing a manual
  workaround, Docebo community reports that merge drops enrolments.
- Rules that add but never remove: Docebo enrolment rules (stated in Docebo's own docs).
- Exports that leave out staff: Canvas idea "Export course People list (including Teachers/TA/Support)".
- Not being able to see which groups a learner is in: Docebo community feedback.
- Scoped admins lacking tools the top admin has: Canvas masquerade for sub-account admins.
- LearnDash has no bulk group add/remove from the WordPress users table (unverified, from a search
  extract, not a quoted page).

## 6. Compared with the FLS capability list

The list in the map: add, remove and deactivate learners (create accounts, handle an existing email);
cohort membership add, remove and move; cohort and individual course registration and
unregistration; cohort create, deactivate and delete; add, remove and scope educators; CSV import and
multi-select bulk actions; dashboards on screen plus downloadable reports; resend invite or password
setup.

### Common actions missing from the list

1. **Reactivate.** The list names deactivate for learners and cohorts but not the way back. Every
   system with a deactivate has a matching reactivate, and bulk activate sits next to bulk deactivate
   in TalentLMS and Docebo. Today `ensure_learner` only reactivates on self-registration.
2. **An audit log that staff can read.** Missing entirely. Five of seven systems have one and the
   earlier FLS permission research already recommended it. FLS has no audit model; the stored
   `WebhookEvent` rows cover only webhook event types. At minimum: actor, action, target, organisation,
   time, and an optional reason on removals (the Open edX pattern). Where it is shown (quick view
   history tab, organisation-level log) is a separate question.
3. **Pending invitation state, and revoking an invite.** The list has "resend invite" but not the state
   it acts on. Canvas shows "pending" on the roster and throttles resends; Open edX lets staff
   pre-assign an email to a cohort before the account exists. Staff need to see who has not set up
   their account yet and cancel an invite sent to the wrong address.
4. **Roster export.** Probably covered by "downloadable reports", but worth naming. It is the most
   common export in every system, and Canvas users complain when it leaves out staff. A cohort's
   learner list plus its educators, as CSV.
5. **Edit a learner's details (name, email).** Docebo and TalentLMS expose it as a single and bulk
   action. In FLS `User` is shared across organisations, so changing an email from one organisation's
   view changes it for all of them. It probably belongs to `site_admin` only, or stays in the Django
   admin. Needs a decision either way.
6. **Registration access dates** (start and end of access). Moodle, Docebo, TalentLMS, LearnDash and
   Canvas all have them. This sits close to deadlines, which are out of scope and being reworked, so I
   am flagging it for the human to place rather than recommending it.

Long-tail items I would not add: account merge (leave to the Django admin or a management command;
it loses data even where it is built in), log in as a learner (high risk, only ever given to the top
admin, and FLS's default roles have no equivalent need yet), rule-based auto-registration (cohort
registration already gives the living link), self-join codes, cross-listing.

### Actions on the list that others handle notably better

- **CSV import.** Moodle's Upload users is the model: an explicit mode ("add new only", "add new and
  update existing", "update existing only") and a preview before commit. Docebo makes overwriting
  existing details an explicit opt-in. For FLS: a preview that labels every row (new account, existing
  account joined to this organisation, already a member, reactivated, error); never overwrite an
  existing `User`'s details by default; errors downloadable. The earlier note found the preview step;
  the per-row outcome labels and the no-overwrite default are new.
- **Unregistration.** Canvas separates deactivate (reversible, keeps everything), conclude (read-only
  after the end) and delete (irreversible). FLS registrations already have `is_active`, so
  "unregister" in the educator interface should mean `is_active=False` and read as reversible. A hard
  delete does not need to exist in the educator interface.
- **Unregistering a cohort from a course.** Moodle forces a global choice between unenrolling members
  and suspending them when a cohort sync is removed. FLS should say in the confirmation what happens to
  a member who also holds an individual registration for the same course, and that progress is kept.
- **Cohort delete.** Canvas refuses to delete a section with members. Google requires archive before
  delete. Open edX forbids delete. For FLS: allow delete only for a cohort with no memberships and no
  course registrations, or only after it has been deactivated; otherwise offer deactivate.
- **Learner remove versus delete.** The list says "remove and deactivate". In FLS `Learner.is_active =
  False` already means removed from the organisation, reversibly. Every system that does this well
  keeps hard account deletion away from day-to-day staff. Recommendation: "remove" in the educator
  interface is deactivate; deleting a `User` stays in the Django admin, where GDPR requests are handled.
- **Move.** FLS is ahead here. Moodle has no move and gets complaints; Open edX and Canvas have it.
  The earlier idea's "show what happens to progress before confirming" is what the others lack.
- **Bulk actions.** Pair every bulk add with a bulk remove (the Moodle complaint). Run large batches as
  a background job with a result summary (Docebo's 250-user cut-off). Open edX shows a single box that
  takes one to many emails and is both the single and the bulk path. That could keep FLS's add-learner
  UI to one form.
- **Scoping educators.** Canvas's "limit to section" and Docebo's Power User resources both scope a
  staff member to a set of groups rather than a whole organisation. That matches FLS's per-cohort
  grants. Docebo also lets a scoped admin see the groups their learners belong to even when not
  assigned to those groups; users complained when they could not.

## 7. Where each action belongs

Answering the question of where each action belongs (educator interface, Django admin, or a management command):

| Educator interface | Django admin or management command |
| --- | --- |
| Add learner (single and CSV), remove (deactivate), reactivate | Hard delete of a `User` |
| Cohort membership add, remove, move, in bulk | Account merge |
| Cohort and individual registration, unregistration (deactivate), re-registration | Log in as a learner, if ever |
| Cohort create, deactivate, reactivate, delete when empty | Editing a `User`'s email if not `site_admin`-only in the interface |
| Educator add, remove, scope | Bulk data repair |
| Invite resend and revoke, pending state | |
| Roster export, audit log view | |

## Appendix A. Moodle and Open edX source notes

Scope: account/cohort/group/enrolment/staff-role admin actions only. Excludes deadlines,
messaging, application review, retakes. All claims sourced; unverifiable items flagged.

### MOODLE

#### 1. Concrete actions

**Account create/invite**
- Manual: Site admin > Users > Accounts > Add a new user. https://docs.moodle.org/36/en/Add_a_new_user
- Bulk CSV: Site admin > Users > Accounts > Upload users. Four "Upload type" modes:
  "Add new only, skip existing", "Add all, append number to usernames if needed",
  "Add new and update existing users", "Update existing users only". Has a preview step
  ("Upload users preview") before commit, showing exceptions/changes.
  https://docs.moodle.org/502/en/Upload_users
- CSV can also enrol users into courses/groups/cohorts at upload time via `course1`,
  `group1`, `cohort1` fields (cohort field uses cohort ID/shortname, not display name —
  documented risk of duplicates if IDs misassigned). https://docs.moodle.org/502/en/Upload_users ; https://docs.moodle.org/502/en/Cohorts
- CSV `suspended=1` field suspends an account on upload/update (toggle controlled by
  "Allow suspending and activating of accounts" setting, default enabled).
  https://docs.moodle.org/502/en/Upload_users
- `oldusername` field renames; `deleted` field deletes accounts via CSV.
  https://docs.moodle.org/502/en/Upload_users

**Duplicate/existing email handling**
- Default upload behaviour skips rows whose username already exists; "update existing"
  modes instead overwrite matching accounts — documented as risky ("errors updating
  existing accounts can affect your users badly"). https://docs.moodle.org/502/en/Upload_users
- No native duplicate-account merge. Feature request MDL-24443 ("Merge Users") open/unresolved
  in Moodle Tracker since ~2010; only solution is 3rd-party plugin `tool_mergeusers`
  (not core), which reassigns activity from user A to user B.
  https://moodle.atlassian.net/browse/MDL-24443 ; https://moodle.org/plugins/tool_mergeusers

**Suspend/deactivate vs delete vs reactivate**
- Suspend: admin edits profile, checks "Suspended account" box, or toggles via cog icon
  in Browse list of users / Bulk user actions. Suspended accounts cannot log in or use
  web services; outgoing messages discarded; all data/enrolments retained unchanged.
  https://docs.moodle.org/405/en/Browse_list_of_users ; site search of docs.moodle.org "suspend user"
- Reactivate: same toggle, unsuspend. CSV `enrolstatus`/`suspended=0` unsuspends in bulk.
  https://docs.moodle.org/502/en/Upload_users
- Delete: on delete, Moodle anonymises the record — "the MD5 hash of the username is
  stored as the email address; the email address + timestamp is stored as the username."
  Deletion is effectively irreversible: profile details, preferences, enrolments,
  cohort/group memberships are not recoverable; forum posts remain but attributed to
  anonymised user; grades are lost unless user is re-enrolled with "recover old grades".
  https://docs.moodle.org/405/en/Browse_list_of_users
- Confirm: separate action for email-based self-registration accounts pending
  confirmation (not suspend/delete). https://docs.moodle.org/405/en/Browse_list_of_users

**Password reset / resend**
- Bulk user actions includes "Force password changes" (forces password change at next
  login for selected users). https://docs.moodle.org/502/en/Bulk_user_actions

**Login-as / masquerade**
- "Log in as" link on a user's profile lets an admin/manager view the site as that
  user; default role permitted is Manager + Admin (not for other admins if applied at
  course level, restricted to that course). Auto-logout back to normal role when
  finished, "for security reasons". https://docs.moodle.org/502/en/Log_in_as ;
  https://docs.moodle.org/25/en/Capabilities/moodle/user:loginas

**Cohort create/archive/delete/members**
- Create: Site admin > Users > Accounts > Cohorts > Add (system-wide or
  category-scoped), or bulk via Upload cohorts CSV. https://docs.moodle.org/502/en/Cohorts
- No "archive" concept documented; only active cohorts.
- Delete: select cohorts in the Cohorts list, "Delete selected" button. No cohort
  "trash"/undelete described. https://docs.moodle.org/502/en/Cohorts
- Add/remove members: cohort "assign" interface (individually), CSV upload with cohort
  IDs, or Bulk user actions > "Add to cohort" (bulk-add only — no bulk-remove in core
  UI; see gap MDL-61007 below). https://docs.moodle.org/502/en/Cohorts ;
  https://docs.moodle.org/502/en/Bulk_user_actions
- **No direct "move member between cohorts" action** — must remove from one, add to
  other separately (documented behaviour, no shortcut found).
  https://docs.moodle.org/502/en/Cohorts

**Enrol/unenrol (individual & cohort)**
- Individual manual enrol/unenrol: Course > Participants > Enrolled users; teachers
  can edit individual enrolment start/end dates. Unenrolling "purges grades, group
  memberships, preferences and other user related data" for that enrolment (but grade
  history is retained for recovery — see below). https://docs.moodle.org/502/en/Manual_enrolment ;
  https://docs.moodle.org/502/en/Unenrolment
- Cohort sync enrolment method: add via Course admin > Enrolment methods > Cohort sync;
  auto keeps course enrolment in sync with cohort membership (add cohort member = auto
  enrol; remove = auto un-enrol/suspend per setting below); can also auto-create/populate
  a course group from the cohort. https://docs.moodle.org/502/en/Cohort_sync
- **"External unenrol action" (cohort sync unlink behaviour)** — global setting at
  Site admin > Plugins > Enrolments > Cohort sync: two options —
  (a) "Unenrol user from course" — removes enrolment, role, and course data;
  (b) "Disable course enrolment and remove roles" — user is *suspended* (not
  unenrolled), role removed, but course data/enrolment retained; user reappears if
  re-added to cohort. This is a single global setting affecting ALL cohort-sync
  enrolments site-wide, not per-course. (Sourced from Moodle forum quoting the actual
  admin setting text; equivalent named setting documented for the analogous
  `enrol_database` "External unenrol action" with the same 3-way semantics —
  Unenrol / Keep enrolled / Disable+suspend.) https://moodle.org/mod/forum/discuss.php?d=437929 ;
  https://docs.moodle.org/37/en/External_database_enrolment
- **Enrolment status active vs suspended**: teachers change a participant's status via
  Participants > Enrolled users > edit (gear) icon. Suspended enrolment = user retains
  data/history but cannot access the course; hidden from most participant UI by default.
  CSV `enrolstatus` field: 1 = suspend, 0 = unsuspend/active.
  https://docs.moodle.org/502/en/Upload_users (search result); community docs corroborate.
- **Bulk enrol/unenrol from a course**: NOT a core Moodle feature — done via
  third-party "Mass enrolments"/"local_mass_enroll" style plugins or the core "Flat
  file" (`enrol_flatfile`) global CSV enrolment method that reads a server-side file.
  Core alternative for bulk enrol-at-creation-time is Upload users with `course1` field.
  https://moodle.org/plugins/local_mass_enroll ; forum context https://moodle.org/mod/forum/discuss.php?d=373197
  (Caveat: initial WebFetch mis-attributed a "Bulk enrolments" doc page as core — verify
  before relying on it; treat as UNVERIFIED/likely-plugin, not core.)

**Grades/progress on unenrol + recovery**
- Unenrolling doesn't delete grade history outright; if unenrolled accidentally,
  re-enrol via Enrolled users > "Enrol users" with "Recover user's old grades if
  possible" checkbox ticked (NOT ticked by default, easy to miss). Site-wide default
  can be forced on via "Recover grades default" in Site admin > Grades > General
  settings (`recovergradesdefault`). https://docs.moodle.org/502/en/Enrolment_FAQ (search-sourced)

**Staff role assignment/scoping**
- System-level: Site admin > Users > Permissions > "Assign system roles" (e.g.
  Manager, Course creator) — applies sitewide; assigning Teacher/Student here is
  warned against as it grants access to every course. https://docs.moodle.org/502/en/Assign_roles
- Category/course-level role assignment via each context's "Assign roles" page (same
  doc). Bulk system-role assignment via CSV `sysrole1` field.
  https://docs.moodle.org/502/en/Assign_roles ; https://docs.moodle.org/502/en/Upload_users
- Who can assign what is governed by "Allow role assignments" matrix in Define roles.
  https://docs.moodle.org/502/en/Assign_roles

**Bulk user actions (core list)**
- Confirm accounts, Send a message, Delete user accounts, Display users on a page,
  Download user data (text/ODS/Excel), Force password changes, Add users to cohorts.
  Filter by name/email/city/country/confirmed/first-access/last-access/last-login/
  username/auth-method/custom profile field. https://docs.moodle.org/502/en/Bulk_user_actions

**Export of user lists**
- Bulk user actions > "Download user data" (txt/ODS/xls). https://docs.moodle.org/502/en/Bulk_user_actions

#### 2. Bulk-only / bulk-first in Moodle
- Upload users (CSV) — only way to batch-create/update accounts + assign cohorts/course/
  group/sysrole in one pass. https://docs.moodle.org/502/en/Upload_users
- Upload cohorts (CSV) — bulk-only cohort creation at category scope for non-admin
  category managers. https://docs.moodle.org/502/en/Cohorts
- Bulk user actions itself is filter-then-batch-only — confirm/delete/message/download/
  force-password/add-to-cohort have no equivalent single-click alternative in that screen
  (each is achievable individually elsewhere, e.g. delete from Browse list of users).
  https://docs.moodle.org/502/en/Bulk_user_actions
- Cohort sync enrolment method is inherently bulk (whole cohort at once) vs Manual
  enrolment which is per-user. https://docs.moodle.org/502/en/Cohort_sync

#### 3. Audit / reversibility (Moodle)
- Site-wide Logs report: Site admin > Reports > Logs — filterable by user/course/
  activity/date, captures logins, failed logins, site errors, all logged actions.
  https://docs.moodle.org/19/en/Logs_report (content re-confirmed via https://docs.moodle.org/405/en/Logs search)
- Live Logs (past hour) also available under Reports > Logs (capability
  `report/loglive:view`). https://docs.moodle.org/38/en/Capabilities/report/loglive:view
- Course Participation report: who did what activity/how many times, filter by
  role/group/action. https://docs.moodle.org/502/en/Participation_report
- Suspend = fully reversible (toggle), all data retained.
- Delete = anonymises username/email via MD5 hash + timestamp; NOT reversible via UI;
  described as effectively permanent data loss for profile/enrolments/cohort
  membership. https://docs.moodle.org/405/en/Browse_list_of_users
- Unenrol (manual) purges enrolment-specific data (group membership, preferences) but
  grade history can be recovered on re-enrol via "Recover old grades" option/setting.
  https://docs.moodle.org/502/en/Unenrolment ; https://docs.moodle.org/502/en/Enrolment_FAQ
- Cohort-sync unlink is NOT a hard delete when "Disable course enrolment and remove
  roles" is set — reversible (suspend, not purge) since re-adding to cohort restores
  active enrolment/roles. https://moodle.org/mod/forum/discuss.php?d=437929

#### 4. Documented gaps (Moodle Tracker / forums, with IDs)
- **MDL-24443** "Merge Users" — feature request to merge two user profiles; status
  Open/Unresolved (long-standing, since ~2010); core team direction is to keep it as
  a contributed admin tool (`tool_mergeusers`) rather than merge into core.
  https://moodle.atlassian.net/browse/MDL-24443 ; https://moodle.org/plugins/tool_mergeusers
- **MDL-61007** "Bulk User Actions - Remove from cohort" — tracker issue requesting a
  bulk-remove-from-cohort action to complement the existing bulk "Add to cohort" (could
  not confirm resolution status/version via WebFetch — Jira UI is JS-rendered and did
  not return field data to the fetch tool; UNVERIFIED whether shipped).
  https://moodle.atlassian.net/browse/MDL-61007 (existence + title verified via search
  snippet: "Bulk User Actions - Remove from cohort")
- Forum-documented long-standing complaint: "In the Teacher role, there is no way to
  bulk unenrol students from courses" (Moodle 2.0-era thread, recurring complaint in
  later threads too — "How to UNENROLL IN BULK?"). No core bulk-unenrol UI confirmed to
  exist as of latest docs reviewed; core relies on Cohort sync/Flat file/plugins.
  https://moodle.org/mod/forum/discuss.php?d=166158 ; https://moodle.org/mod/forum/discuss.php?d=464265
- No direct "move cohort member to another cohort" action — community forum threads
  confirm workaround is remove+re-add. https://moodle.org/mod/forum/discuss.php?d=424958
  (forum, not tracker — flagged as corroborating but not authoritative)

---

### OPEN EDX

#### 1. Concrete actions

**Account create/invite (learner)**
- No staff-driven "invite/create learner account" flow documented in educator docs;
  learners self-register. Staff instead pre-associate email addresses with
  cohorts/teams before the learner even has an account ("Preassignment" — email added
  to a cohort auto-applies on that email's future enrolment).
  https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/manage_cohorts.html

**Course-team account create/invite**
- Add course team member (Staff/Admin) via Studio Settings > Course Team, or via LMS
  Instructor > Membership; requires the target user to have already registered/
  activated an account (no invite-and-auto-create). Role assignment both adds to team
  and assigns the role in one action; requires Admin role in the course to do so.
  https://docs.openedx.org/en/latest/educators/how-tos/set_up_course/add_course_team_members.html

**Duplicate/existing email**
- Not documented as a staff-facing concern (learner self-registration path); no
  primary-source evidence found of a staff merge/duplicate-resolution tool.
  UNVERIFIED — no equivalent of Moodle's merge-users found in docs.openedx.org.

**Suspend/deactivate vs delete vs reactivate (learner accounts)**
- Could not find a primary-source *educator*-facing "suspend/deactivate learner
  account" action in docs.openedx.org (searched explicitly). Account
  deletion/retirement is a learner self-service + GDPR "retirement" pipeline (retires
  username, email, PII) rather than a staff admin action described in educator docs.
  UNVERIFIED for staff-initiated suspend; flagged as a documented gap area (see §4).
  Search performed: site:docs.openedx.org support tools disable/deactivate account —
  no direct hits beyond retirement/account-deletion feature toggle references.

**Login-as / masquerade**
- Closest documented feature is "View this course as" (View Course As dropdown) —
  lets staff preview content as a persona/content-group/cohort or as a *specific*
  enrolled learner for content visibility testing, not a full account-level
  impersonation/login-as like Moodle's. https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/view_cohort_specific_courseware.html

**Cohort create/delete/members**
- Create: Instructor > Cohorts > Add Cohort — name, assignment method (automatic or
  manual), optional content-group link. At least one automatic cohort must exist
  before course launch (or Moodle-equivalent default cohort auto-created on first
  learner access). https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/manage_cohorts.html
- **Cohorts CANNOT be deleted** — verified direct quote: "You cannot delete cohorts.
  However, you can rename a cohort, change its assignment method, or move learners to
  other cohorts." https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/manage_cohorts.html
- Members: manual add via username/email list, or CSV upload (`email`/`username` +
  `cohort` columns; later rows in the file overwrite earlier duplicate-learner rows;
  UTF-8, max 2MB). Learners CAN be moved between cohorts (move = reassignment,
  supported despite delete not being supported); default cohort's assignment method
  cannot be changed to manual if it's the last automatic cohort.
  https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/manage_cohorts.html
- Known caveat documented: discussion posts can visually "disappear" for a learner
  moved to a new cohort because divided-discussion visibility doesn't retroactively
  update. https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/manage_cohorts.html

**Enrol/unenrol (Instructor Dashboard > Membership, "Batch Enrollment")**
- Enter username/email (comma- or newline-separated, or paste from CSV) then choose
  Enroll or Unenroll. Options: "Auto Enroll" checkbox, "Notify students by email"
  checkbox. Documented as "better suited to courses with smaller enrollments" (no
  stated hard limit found). https://docs.openedx.org/en/latest/educators/how-tos/student_management/manage_course_enrollments.html
- Unenrolling requires entering "a specific, detailed reason" for the action (captured
  for audit — see ManualEnrollmentAudit below).
  https://docs.openedx.org/en/latest/educators/how-tos/student_management/manage_course_enrollments.html
- All new enrolments default to the audit track. Unenrolling does NOT delete learner
  state: "an unenrolled learner's state remains in the database and is reinstated if
  the learner does re-enroll" — i.e., grades/progress preserved and restored on
  re-enrol (unlike Moodle where this needs an explicit "recover grades" checkbox).
  https://docs.openedx.org/en/latest/educators/how-tos/student_management/manage_course_enrollments.html
- Beta testers: separate "Batch Beta Tester Addition" box on Membership tab.
  https://docs.openedx.org/en/open-release-sumac.master/educators/how-tos/releasing-course/add_beta_testers.html
- Allowlist ("may enroll") — CSV export available:
  `{org}_{course_id}_may_enroll_info_{date}.csv`; separate report lists "students who
  are enrolled but have not activated their account yet."
  https://docs.openedx.org/en/latest/educators/how-tos/data/view_learners_not_yet_enrolled.html
- No documented "active vs suspended" enrolment status distinct from enrolled/
  unenrolled — Open edX model appears binary (enrolled or not) rather than Moodle's
  tri-state (active/suspended/unenrolled). UNVERIFIED as an explicit absence (searched,
  found no status field beyond enrollment mode + is_active).
- Programmatic/admin-driven unenrol (not as the logged-in learner) is NOT clearly
  documented as a supported REST endpoint: `DELETE`/`PATCH`
  `/api/enrollment/v1/enrollment` return 405; community workaround is
  `/api/bulk_enroll/v1/bulk_enroll/` with `action=unenroll`, no official maintainer
  confirmation of a dedicated endpoint found in this thread.
  https://discuss.openedx.org/t/how-can-i-programmatically-unenroll-users-as-an-admin-not-as-the-learner-in-open-edx/17361
  (Discourse thread — maintainer-adjacent but not docs.openedx.org; treat as
  community-source, flagged accordingly.)

**Staff role assignment/scoping**
- Roles: Staff, Limited Staff (no Studio/content-editing access), Admin (manages
  Staff/Admin membership, beta testers, discussion-role assignments, full grade
  access), Course Data Researcher (Data Download tab access: learner data, anonymized
  IDs, certificate data, enrollment info), Beta Tester, Discussion Admin/Moderator/
  Community TA (discussion moderation, require enrolment not Staff/Admin).
  https://docs.openedx.org/en/latest/educators/references/course_development/course_team_roles.html
- All roles assigned at course level via Instructor > Membership (enter
  username/email, select role, Add) or Studio Course Team; "Revoke access" removes.
  Doc found no org-level role assignment for Staff/Admin; one search snippet claimed
  "data researcher role at the organization level or for a specific course run" —
  UNVERIFIED, could not confirm by direct page fetch of that exact claim.
  https://docs.openedx.org/en/latest/educators/how-tos/set_up_course/add_course_team_members.html
- New "Course Authoring" role system (separate from legacy LMS Staff/Admin): Course
  Admin / Course Staff, managed via a "Roles and Permissions" console.
  https://docs.openedx.org/en/latest/educators/references/course_development/course_team_roles.html

**CSV upload incl. update-existing / preview**
- Team membership CSV: format `user, mode, <team-set>, <team-set>, ...` for bulk team
  assignment. https://docs.openedx.org/en/latest/educators/references/advanced_features/managing_teams_via_csv.html
- Cohort CSV: no explicit "preview" step documented (contrast with Moodle's preview
  page) — processes and applies directly; duplicate-learner rows are resolved by
  last-row-wins. https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/manage_cohorts.html
  UNVERIFIED whether a preview/dry-run exists — not mentioned in the how-to.

**Bulk user actions list equivalent**
- No single "bulk user actions" hub like Moodle; actions are split by
  purpose/tab on Instructor Dashboard: Membership (enrol/unenrol/roles/cohorts/beta
  testers), Data Download (exports), Cohorts.
  https://docs.openedx.org/en/latest/educators/how-tos/student_management/manage_course_enrollments.html

**Export of user lists**
- Data Download tab: "Download profile information as a CSV" (enrolled learners,
  incl. enrollment mode + verification status); "Download a CSV of all… students who
  can enroll" (may-enroll list); list of enrolled-not-activated accounts.
  https://docs.openedx.org/en/latest/educators/how-tos/data/view_learner_data.html ;
  https://docs.openedx.org/en/latest/educators/how-tos/data/view_learners_not_yet_enrolled.html

#### 2. Bulk-only / bulk-first in Open edX
- Batch Enrollment box on Membership tab is the *only* documented enrol/unenrol UI —
  no separate "enrol one learner" screen distinct from typing one email into the batch
  box, so effectively bulk-first/bulk-only by design.
  https://docs.openedx.org/en/latest/educators/how-tos/student_management/manage_course_enrollments.html
- Cohort CSV upload is bulk-only for mass (re)assignment; manual username/email entry
  covers small-scale. https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/manage_cohorts.html
- Team-membership CSV is bulk-only path for large team-set assignment.
  https://docs.openedx.org/en/latest/educators/references/advanced_features/managing_teams_via_csv.html
- `/api/bulk_enroll/v1/bulk_enroll/` — a batch API endpoint used (per community) as
  the de facto way to unenrol programmatically, since single-object
  DELETE/PATCH on `/api/enrollment/v1/enrollment` are not available (405).
  https://discuss.openedx.org/t/how-can-i-programmatically-unenroll-users-as-an-admin-not-as-the-learner-in-open-edx/17361 (community-sourced)

#### 3. Audit / reversibility (Open edX)
- Tracking-log event types exist for both enrolment and cohort/team changes:
  `edx.course.enrollment.activated` / `edx.course.enrollment.deactivated` emitted on
  enrol/unenrol (including staff-driven changes); `edx.cohort.creation_requested` and
  related cohort events emitted when course team creates/assigns cohorts.
  https://docs.openedx.org/en/latest/developers/references/internal_data_formats/tracking_logs/student_event_types.html ;
  https://docs.openedx.org/en/latest/developers/references/internal_data_formats/tracking_logs/course_team_event_types.html
- `ManualEnrollmentAudit` — edx-platform "support" app model that records manual
  enrolment/unenrolment changes made by staff, including the required "reason" text,
  used by the Support Tools enrollment view.
  https://docs.openedx.org/projects/edx-platform/en/latest/references/docstrings/lms/lms.djangoapps.support.html
  (docstring reference — primary source, but terse; exact fields UNVERIFIED beyond
  "serializes a manual enrollment audit object")
- Unenrol reversibility: state is retained in DB and restored automatically on
  re-enrolment (grades/progress) — see §1 above (Moodle-equivalent of "always recovers
  grades," no separate checkbox needed).
  https://docs.openedx.org/en/latest/educators/how-tos/student_management/manage_course_enrollments.html
- Cohort reassignment: fully reversible (move learner again); cohort itself
  undeletable (see §1), so "undo cohort creation" isn't offered — only rename/
  reconfigure. https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/manage_cohorts.html
- No equivalent of Moodle's sitewide "Logs" report was found documented for general
  staff-action auditing across learner-management operations beyond the tracking-log
  event stream (which is an analytics/event pipeline, not a browsable admin UI log by
  default). UNVERIFIED whether a browsable equivalent exists without Aspects/analytics
  stack installed.

#### 4. Documented gaps / complaints (Open edX)
- Cohorts cannot be deleted — documented as permanent platform limitation, not a bug
  report, i.e. by-design gap acknowledged in official docs (quoted in §1).
  https://docs.openedx.org/en/latest/educators/how-tos/advanced_features/manage_cohorts.html
- No dedicated, clearly-documented admin-initiated single-user unenrol REST endpoint;
  DELETE/PATCH on `/api/enrollment/v1/enrollment` return 405 per a Discourse report;
  workaround is the bulk-enroll endpoint with `action=unenroll`. No maintainer in the
  thread confirmed this as an intentional gap vs. an oversight — flagged UNVERIFIED as
  an official "known gap," but the underlying limitation (405 responses) is
  independently reported by the poster's testing.
  https://discuss.openedx.org/t/how-can-i-programmatically-unenroll-users-as-an-admin-not-as-the-learner-in-open-edx/17361
- No primary-source evidence found (docs.openedx.org or GitHub issue) of a staff
  "suspend/deactivate learner account" action, unlike Moodle's suspend toggle —
  Open edX's nearest analogue is per-course unenrol or the full account-retirement
  (GDPR delete) pipeline; nothing in between documented. Flagged as a functional gap
  relative to Moodle, but I could not find an issue tracker ticket explicitly
  requesting it — UNVERIFIED as a tracked complaint, only as an observed doc gap.
- Could not locate a specific edx-platform GitHub issue ID for "delete cohort" or
  "bulk unenroll" feature requests within the search budget of this task — the
  underlying limitations are documented as permanent product behaviour (above) rather
  than open tracker tickets, so no issue ID to cite. UNVERIFIED / not found.

---

### Summary of citation confidence
- High confidence (direct doc fetch, exact text quoted): Moodle delete-anonymisation
  behaviour, Moodle Upload users types, Moodle cohort no-move, Moodle
  External-unenrol-action two options, Open edX "cannot delete cohorts" quote, Open edX
  unenrol-state-retained quote, Open edX course team roles list.
- Medium confidence (WebSearch snippet from docs.moodle.org/docs.openedx.org, not
  independently re-fetched verbatim): Bulk user actions list, enrolment status
  active/suspended field, recover-grades setting, ManualEnrollmentAudit docstring.
- Low/community confidence (forums, Discourse, GitHub — flagged inline as such):
  MDL-61007 resolution status, bulk-unenrol community complaints, programmatic-unenrol
  405 report, org-level data-researcher-role claim.

(MDL-61007 resolution, Open edX staff-suspend gap, specific gap-tracker issue IDs for
Open edX) could not be verified from primary sources within tool constraints and are
explicitly marked unverified above.

## Appendix B. Canvas and Google Classroom source notes

Research scope: learner/section/enrolment/staff admin actions, bulk vs single, audit/reversibility, documented gaps.
Excluded: due-date extensions, messaging/announcements, application review, retakes.

### 1. CANVAS LMS

#### 1.1 Adding users / invitations
- "Add People" on course People page: invite by email, Login ID, SIS ID, or User ID; sets role + section. Invited users get "pending" (invited) enrollment until accepted. https://community.instructure.com/en/kb/articles/663052-how-do-i-enroll-additional-users-in-my-course (via community.instructure.com; ta-p/1119 "How do I add users to a course?")
- Resending invitation: People page > 3-dot menu next to name > "Resend" (must wait ≥24h between resends). https://community.instructure.com/en/kb/articles/660964-how-do-i-resend-student-invitations-to-a-course
- If a pasted email/login already exists in the account, Canvas links the new enrollment to the existing user record (no duplicate account created) — course-level behavior confirmed via "How do I add users to a course?" guide; exact wording not independently re-verified this session — **unverified** exact matching rules (email vs Login ID priority).
- Non-SIS bulk add: paste list of UIDs/Login IDs/SIS IDs into "Add People" text box (invite-only, leaves "pending" status) OR root-account admin SIS Import CSV. Enrollments API can also be scripted by a root-account admin to bypass "pending" status and avoid the SIS-lock flag. https://groups.google.com/g/canvas-lms-users/c/B9IgTMcojro (secondary community group thread — **treat as unverified/supplementary**, not an Instructure-authored source)

#### 1.2 Enrollment states — exact semantics (PRIMARY: Canvas Enrollment Status Comparison doc)
Canvas enrollment `workflow_state` values include: active, invited, creation_pending, deleted, rejected, completed, inactive (+ synthetic query states current_and_invited/current_and_future/current_and_concluded). https://www.canvas.instructure.com/doc/api/enrollments.html
- **Deactivate → `inactive`**: course-level only (no account-wide deactivate). Retains all prior activity/submissions/grades; user loses all access to the course (no login, no content, no grades visibility) but remains listed on People page. Fully **reversible** — reactivating restores exactly as before. https://community.instructure.com/en/kb/articles/660973-how-do-i-deactivate-an-enrollment-in-a-course ; comparison doc: https://community.canvaslms.com/t5/Canvas-Resource-Documents/Canvas-Enrollment-Status-Comparison/ta-p/387055
- **Conclude → `completed`**: happens automatically at term/course/section end date, or manually per-enrollment or for whole course. Enrollment moves to "Prior Enrollments" on People page. Grades/submissions retained; user gets read-only access typically (per Canvas conventions). **Reversible**: a manually-concluded enrollment can be restored "at any time before the course concludes via term/course/section end date" via People page. https://community.instructure.com/en/kb/articles/660975-how-do-i-restore-a-concluded-enrollment-in-a-course ; https://community.instructure.com/en/kb/articles/660974-how-do-i-conclude-an-enrollment-in-a-course
- **Delete/Remove → `deleted`**: "Removing (deleting) a user from a course means deleting their enrollment so they are no longer visible to the instructor and have no access in the course at all." Also removes associated coursework/grades/submissions from the course. **NOT reversible via UI — "There is not any way to undo deleting an enrollment."** https://community.instructure.com/en/kb/articles/660977-how-do-i-remove-an-enrollment-from-a-course (Note: dev-facing threads discuss admin/API-level enrollment restoration in narrow cases — https://community.canvaslms.com/t5/Canvas-Developers-Group/Deleting-and-restoring-enrollments-via-API/m-p/516051 — **unverified** whether this is officially supported vs a workaround.)
- Summary distinction (community-doc phrasing): "Deactivating enrollments will not wipe out the person's activity in the course (or delete submissions), and re-activating their enrollment puts everything back to normal. In contrast, removing an enrollment removes all associated coursework and grades from the course." — same KB source as above.

#### 1.3 Account-level user actions
- **Delete user from account**: Admin > People > user > Delete. If account uses SIS, SIS-side changes are separate (Canvas deletion doesn't push back to SIS). Deleted users **can be restored** via Admin Tools. https://community.canvaslms.com/t5/Admin-Guide/How-do-I-delete-a-user-from-an-account/ta-p/136 ; restore: https://community.canvaslms.com/t5/Admin-Guide/How-do-I-restore-a-deleted-user-or-course-in-an-account/ta-p/596828
- **Suspend/reactivate (account-level login lock)**: distinct from delete. "Suspending a user allows you to remove the user's login access to authorized systems" (blocks login/API) without deleting the account; reactivating restores login + API access. https://community.canvaslms.com/t5/Admin-Guide/How-do-I-suspend-or-reactivate-users-in-an-account/ta-p/504141
- Canvas has **no account-level "deactivate"** — deactivation is a course-enrollment-only concept; at account level a user is either active, suspended, or deleted. (Per community thread synthesis: https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-User-License-Info-Difference-in-Deactivate-Suspend-and/m-p/527624 — this is an **Archived** (community, not official-guide) thread; treat the "account level has no deactivate" framing as **community-sourced, not Instructure-authored guide text**.)
- **Merge users**: account admin can merge two user records, combining logins, contact methods, and enrollments; page views are NOT retained for the merged-away user. https://community.canvaslms.com/t5/Admin-Guide/How-do-I-merge-users-in-an-account/ta-p/134
  - **Split (undo) merge**: possible "within 180 days of the user merge" via Split Merged Users on account Users page. https://community.canvaslms.com/t5/Admin-Guide/How-do-I-split-merged-users-in-an-account/ta-p/425634
- **Password reset**: admin can create/edit logins and reset passwords/MFA for a user IF the institution manages passwords through Canvas; if institution uses external auth (e.g., SSO/Auth0), Canvas admins cannot alter passwords. https://community.instructure.com/en/kb/articles/661550-how-do-i-manage-a-users-login-information-in-an-account
- **Act-as-user (masquerade)**: requires the account-level "Become other users" / "Act as users" permission. Admin logs in as the target user with no password; actions appear as performed by that user. Audit: "for auditing purposes, all calls log both the calling user and the target user." API: pass `as_user_id` param; requires same permission. https://developerdocs.instructure.com/services/canvas/basics/file.masquerading ; https://community.instructure.com/en/kb/articles/661555-how-do-i-act-as-another-user-in-an-account

#### 1.4 Sections
- Create: Course Settings > Sections tab, add section. https://tuftsedtech.screenstepslive.com is secondary; primary: Instructure Sections API https://developerdocs.instructure.com/services/canvas/resources/sections
- Delete: Course Settings > Sections; **cannot delete a section that has users enrolled**; SIS-created sections (with an SIS ID) may not be deletable by non-SIS-privileged users. https://community.instructure.com/en/kb/articles/660761-how-do-i-delete-a-course-section
- Move a user between sections: People page > 3-dot menu next to name > "Edit Sections" — add new section, remove old one. If sections are SIS-managed/locked, must be done via SIS or by an admin. https://community.canvaslms.com/t5/Canvas-Question-Forum/How-do-you-move-a-student-from-one-section-to-another/m-p/191205 (community Q&A — cites in-product mechanism; **treat exact UI label as approximate**, cross-referenced with "How do I edit sections for an enrollment in a course?" official guide ta-p/895)
- Cross-listing (admin, and instructor for own sections): moves a section's enrollments from one course into another (merges gradebooks/rosters). **Must be done while unpublished** — "if a published course is cross-listed, all cross-listed enrollments will lose any associated assignment submissions and grades." Reversible via "de-cross-list," which returns enrollments to the original course/section. https://community.canvaslms.com/t5/Admin-Guide/How-do-I-cross-list-a-section-in-a-course-as-an-admin/ta-p/207 ; de-cross-list: https://community.canvaslms.com/t5/Admin-Guide/How-do-I-de-cross-list-a-section-in-a-course-as-an-admin/ta-p/206
- Limit user to section (`limit_privileges_to_course_section`): restricts a teacher/TA/student's visibility and (for teacher/TA) grading privileges to only their own section's users. Settable per-enrollment via API (`enrollment[limit_privileges_to_course_section]=true`), via SIS import (`limit_section_privileges` flag), or manually on the Add People screen. https://developerdocs.instructure.com/services/canvas/resources/enrollments ; SIS importer source: https://github.com/instructure/canvas-lms/blob/master/lib/sis/enrollment_importer.rb (code, not a guide — **secondary/technical, not a user-facing doc**)

#### 1.5 Staff roles
- Course-level base roles: Teacher, TA, Designer, Observer (plus Student); account-level base roles: Account Admin, Sub-Account Admin. Admins can create **custom roles** at account or course level by copying a base role and modifying its permission set. https://community.instructure.com/en/kb/articles/661567-what-user-roles-and-permissions-are-available-in-canvas ; https://community.instructure.com/en/kb/articles/661569-how-do-i-add-a-new-user-role-in-canvas
- Permissions page (Admin > Permissions > Account Roles tab) sets/edits what each account-level role can do; permissions can be **locked** at a parent account level so sub-account admins cannot override them in child (sub-)accounts. https://community.canvaslms.com/t5/Admin-Guide/How-do-I-set-permissions-for-an-account-level-role/ta-p/213
- Sub-account admins: scoped to their sub-account and its descendants; can manage courses/settings/reporting within that scope only (cannot act outside it by default). Source: community synthesis of admin-guide content, not a single canonical URL — **partially unverified** as a single-citation claim.

#### 1.6 Bulk operations
- **SIS CSV Import**: bulk-creates/updates users, accounts, terms, courses, sections, enrollments, logins. https://developerdocs.instructure.com/services/canvas/sis/file.sis_csv ; https://www.canvas.instructure.com/doc/api/file.sis_csv.html
  - **Batch mode**: full-dataset import; can run against all terms in one import when in "multi-term batch mode" (requires a `change_threshold`); anything omitted from the batch can be auto-dropped/concluded per `batch_mode_enrollment_drop_status` (newer addition, parallels diffing mode). https://community.canvaslms.com/t5/Canvas-Ideas/Add-batch-drop-status-param-to-SIS-Import-API-for-batchmode-like/idi-p/455179
  - **Diffing mode**: Canvas compares the current import to the last successful import with the same "data set identifier" and applies only the delta — objects missing from the new import are by default marked "deleted" unless `diffing_drop_status` specifies "completed" or "inactive" instead. https://community.canvaslms.com/t5/Canvas-Developers-Group/Tips-for-transitioning-SIS-Import-to-Diffing-Mode/m-p/54522 ; https://developerdocs.instructure.com/services/canvas/sis/file.sis_csv
- **People page bulk actions**: a dedicated permission "Bulk actions - people page" lets an authorized user **Enroll, Delete, or Suspend** multiple users at once directly from the People page UI (not just via SIS). https://developerdocs.instructure.com/services/canvas/permissions/details/file.permissions_manage_users_in_bulk (role-eligibility for this permission not specified in the doc — **unverified** which base roles get it by default)
- Roster export: People page > 3-dot options menu (course-level) > "Export Course Roster" produces a CSV (name, ID, section, role, activity). Confirmed via community Q&A threads referencing the in-product option; canonical "How do I" guide URL not directly retrieved this session — **moderately verified** (multiple independent community threads agree, but no single official ta-p guide URL captured).

#### 1.7 Audit / reversibility (account-level Admin Tools)
- Admin Tools has separate tabs: **Logging** (view records of admin/account activity — grade change events, course activity, enrollment activity, etc.) and course/user **restore** tools. https://community.canvaslms.com/t5/Admin-Guide/How-do-I-view-course-activity-for-an-account/ta-p/160
- **Restore deleted courses**: Admin > Admin Tools > "Restore Course"; requires `Courses - manage` (delete) + `Course Content - view` + `Courses - undelete` permissions enabled for the admin role. https://developerdocs.instructure.com/services/canvas/permissions/details/file.permissions_undelete_courses
- **Restore deleted users**: same Admin Tools area, "How do I restore a deleted user or course in an account?" https://community.canvaslms.com/t5/Admin-Guide/How-do-I-restore-a-deleted-user-or-course-in-an-account/ta-p/596828
- **Login/logout activity log**: Admin Tools shows a user's login/logout history; requires `Users - manage login details` or `Statistics - view` permission to be enabled (both must be off to hide the option). https://community.instructure.com/en/kb/articles/661413-how-do-i-view-login-and-logout-activity-for-a-user-in-an-account
- Course-content-level undelete (`/undelete` URL suffix) is a **separate, course-scoped** feature (not an account admin tool) for restoring deleted quizzes/assignments/pages/discussions within a course; shows only the 25 most-recently-deleted items and not all content types are recoverable (e.g., discussion restore does not restore prior student submissions to that discussion). Sourced from institutional KB pages (not Instructure's own guide) — **secondary source**, e.g. https://it.umn.edu/services-technologies/how-tos/canvas-undelete-restore-canvas-content — treat mechanism as directionally correct but **verify against an Instructure-authored guide before relying on specifics**.

### 2. GOOGLE CLASSROOM

#### 2.1 Inviting / adding students and co-teachers
- Teachers invite students by **email invite** or by sharing the **class code** (students enter code in Classroom); teachers can also invite via **invite link**. https://support.google.com/edu/classroom/answer/6020282
- **Reset invite codes**: "Reset invite codes" generates a new code; "the previous codes won't work" (i.e., anyone with the old code can no longer join — existing enrolled students are unaffected, only the join mechanism changes). Codes can also be disabled/enabled. https://support.google.com/edu/classroom/answer/6020282 (thread on whether reset kicks out existing students: https://support.google.com/edu/classroom/thread/12595717 — this is a **community thread, not an authoritative statement**, flagged as such)
- **Invite co-teachers**: class > People > "Invite teachers," by individual email or group email. Invited teacher must accept via email link or the Classroom class card. https://support.google.com/edu/classroom/answer/6190760
- **Remove student or co-teacher**: class > People > next to name > More > Remove. **You cannot remove the primary teacher/owner.** Co-teachers have full teacher capabilities except they cannot delete the class, remove the primary teacher, or mute another teacher. https://support.google.com/edu/classroom/answer/6069576
- Known complaint (community, unofficial): "Cannot remove invited co-teacher from Google Classroom" — a co-teacher invite that hasn't been accepted yet reportedly can't always be revoked/removed cleanly. https://support.google.com/edu/classroom/thread/230024689/cannot-remove-invited-co-teacher-from-google-classroom — **community thread, unverified as a confirmed product limitation** (not a maintainer-confirmed bug).

#### 2.2 Transfer ownership
- A primary teacher (owner) can transfer ownership to a co-teacher: class > People > next to teacher's name > More > "Invite to own" (grant), or "Revoke invite to own" to cancel before acceptance. **Until the co-teacher accepts, the original owner still owns the class. Once transferred, the transfer cannot be undone** (ownership would need to be transferred back explicitly by the new owner). Domain-bound accounts can only transfer to a co-teacher in the same Workspace domain; personal accounts only to another personal account. https://support.google.com/edu/classroom/answer/7449476

#### 2.3 Archive / delete / restore a class
- **Archive**: removes the class from the active Classes view; archived classes are read-only (per Google's general description) and are found under "Archived classes." **Restore**: from Archived Classes, click Restore, which returns the class to the active list. https://support.google.com/edu/classroom/answer/6149813
- **Delete**: only the **primary teacher** can delete a class, and a class **must be archived before it can be deleted**. **"There's no way to undo deleting a class."** After deletion, no access to class posts/comments; underlying files remain accessible in Google Drive (assignment attachments, etc., persist in Drive independent of the Classroom deletion). https://support.google.com/edu/classroom/answer/6149813

#### 2.4 Removing a student — effect on grades/work
- Removing a student "removes their grades from the gradebook and they won't see your assignments in Classroom." Their **past submitted work remains in the class folder in Google Drive**, and their prior stream contributions (posts/comments/answers) **remain visible** to other class members. https://support.google.com/edu/classroom/answer/6069576

#### 2.5 Admin console: roster sync (SIS/OneRoster) and teacher verification
- **SIS roster import**: Workspace for Education admin console (classroom.google.com/admin) lets a super admin connect Classroom to an SIS via native OneRoster support (natively supported: PowerSchool, Infinite Campus, Skyward SMS, Skyward Qmlativ, Follett Aspen as of the 2024 update) or via Clever/ClassLink middleware for other SIS platforms; sync flows student, teacher, class, and enrollment data automatically to keep rosters current, and can export grades back to the SIS. https://support.google.com/edu/classroom/answer/9356588 ; https://support.google.com/edu/classroom/answer/10495270 ; general OneRoster developer reference: https://developers.google.com/workspace/classroom/sis-integrations/validate-your-SIS ; update announcement: https://workspaceupdates.googleblog.com/2023/11/google-classroom-now-supports-roster-import.html
- **Teacher verification** ("Verify teachers and set permissions," Workspace for Education admin-only): when a user first signs in to Classroom they self-identify as teacher or student; self-identified teachers are added as **pending members** of the domain's "Classroom Teachers" Google Group, and an admin must **approve** them to grant full teacher permissions/features (e.g., create classes, invite guardians). Requires "Groups for Business" service enabled for the domain; process can be automated (auto-verify by OU, security group, etc.). https://support.google.com/edu/classroom/answer/6071551
- Per Google's developer docs, Classroom user roles are Teacher, Student, Guardian, and Administrator; a Course has multiple possible co-teachers but exactly one **Course owner**, and "only a Course owner can delete the Course and change the Course owner." https://developers.google.com/workspace/classroom/guides/key-concepts/user-types

#### 2.6 Audit log
- Admin console: **Reporting > Audit and investigation > Classroom log events** (requires the Audit & Investigation admin privilege). Tracks actions such as "who removed a student from a class or archived a class." Supports filtering (date range, other filters); default view shows last 7 days. Available on Education Fundamentals, Standard, Plus, and Workspace for Nonprofits. https://support.google.com/a/answer/11479793 ; https://support.google.com/edu/classroom/answer/11362627
- Education Standard/Plus customers can export Classroom audit log data to **BigQuery** for further querying. https://workspaceupdates.googleblog.com/2021/09/google-classroom-activity-audit-logs-and-big-query-activity-logs.html (Google Workspace Updates blog — **official Google blog, treated as primary** since it's Google's own product-announcement channel, but is not a Help Center article)

### 3. BULK-ONLY OR BULK-FIRST OPERATIONS
- Canvas: SIS CSV import is the only route for true bulk creation of **accounts, terms, courses, sections, cross-course enrollment sets, and logins** at scale; the People-page "Bulk actions" permission (enroll/delete/suspend) is course/account-scoped bulk-UI but still manual selection, not a full provisioning pipeline. https://developerdocs.instructure.com/services/canvas/sis/file.sis_csv ; https://developerdocs.instructure.com/services/canvas/permissions/details/file.permissions_manage_users_in_bulk
- Canvas: Cross-listing is inherently a "move a whole section" bulk-first operation (there's no per-student cross-list).
- Google Classroom: SIS/OneRoster roster import (admin console) is the only bulk-first path for provisioning classes/enrollments at scale; there is **no documented bulk "add multiple students by CSV" tool inside the teacher-facing Classroom UI itself** — individual invite (email/code) or SIS sync are the two documented paths. (Synthesized from sections 2.1 and 2.5 — no single Google doc states this as a gap explicitly; treat the "no CSV bulk-add in teacher UI" claim as an **inference from the absence of documentation**, not a directly cited limitation.)

### 4. DOCUMENTED GAPS / COMPLAINTS (Canvas Idea Conversations / community threads)
NOTE: WebFetch of the specific idea-conversation URLs below returned 404 after Instructure's community-domain migration (community.canvaslms.com → community.instructure.com); titles/URLs were obtained via the site's own search index (so the topic and existence of the idea/thread is verified), but I could not confirm current vote counts or official Instructure status ("Under Consideration," "Not Right Now," etc.) for these threads this session. Treat status claims below as **unverified**; existence and topic are as-indexed by the Instructure Community search itself.
- "Bulk Delete Users" idea — requests ability to bulk-delete users (beyond the People-page bulk action / SIS route). https://community.canvaslms.com/t5/Idea-Conversations/Bulk-Delete-Users/idi-p/360136 — status unverified.
- "[Enrollments] Bulk Combine Students from Multiple Sections into One Section" — requests a bulk tool for merging/moving students across sections without full cross-listing. https://community.canvaslms.com/t5/Canvas-Ideas/Enrollments-Bulk-Combine-Students-from-Multiple-Sections-into/idi-p/582489 — status unverified.
- "[Reports] Export course People list (including Teachers/TA/Support)" — complains that roster export via People page and/or Gradebook export does not include TAs/observers/support staff, only students. https://community.canvaslms.com/t5/Canvas-Ideas/Reports-Export-course-People-list-including-Teachers-TA-Support/idi-p/541812 — status unverified. Corroborating detail from search: "the grade book does not include TAs or observers; the People list does" (i.e., partial workaround exists but full combined export is the ask).
- "Act as User (Masquerade) for Sub-Account Admins" — multi-page idea conversation requesting that sub-account admins (not just root account admins) be able to use act-as-user/masquerade within their scoped sub-account. https://community.canvaslms.com/t5/Idea-Conversations/Act-as-User-Masquerade-for-Sub-Account-Admins/idi-p/414164 (page 2 of thread indexed) — status unverified; existence of ongoing multi-page discussion suggests sustained community interest but no confirmed resolution found this session.
- "Force Enroll Students" — older idea (indexed via legacy instructure.jiveon.com Jive-platform community, Instructure's pre-Khoros forum) requesting a way to bulk-force-enroll students bypassing invitation-pending status without SIS. https://instructure.jiveon.com/ideas/9520-force-enroll-students — **legacy platform, likely stale; status unverified, treat as historical**.
- Community Q&A "How to bulk remove users in the 'people' tab of an account" and "Removing large group of users from Canvas in one step" indicate recurring user pain around bulk removal outside SIS Export; official guidance (per search synthesis) is that account-wide bulk removal is expected to go through a **SIS Export**, with no lighter-weight bulk UI at account scope. https://community.canvaslms.com/t5/Canvas-Question-Forum/How-to-bulk-remove-users-in-the-quot-people-quot-tab-of-an/m-p/232710 ; https://community.canvaslms.com/t5/Canvas-Question-Forum/Removing-large-group-of-users-from-Canvas-in-one-step/m-p/572775 — community Q&A, **not an official statement of product limitation**, but directionally consistent with permission-doc scope (bulk-actions permission is People-page/course-scoped, not account-roster-scoped).
- No Google Classroom equivalent "Idea Conversations" forum with maintainer responses was located in this session (Google's public feedback path for Classroom is the community support thread system at support.google.com/edu/classroom/community, which is user-to-user, not maintainer-tracked feature requests) — **gap in available primary-source venue**, not a specific documented product gap.


## Appendix C. TalentLMS, Docebo and LearnDash source notes

Scope: learner mgmt, groups/branches, course enrolment, staff roles, bulk actions, audit/reversibility, gaps.
Excluded per brief: due-date extensions, notifications, application review, retakes/progress reset.
All items sourced from official help centres / dev docs unless marked **unverified**.

### 1. TalentLMS

#### Learner management
- Create user: Admin > Users > Add user; or import (bulk). Users identified by unique **username** (email can differ). https://help.talentlms.com/hc/en-us/articles/9652321881628-How-to-create-new-user-profiles-in-TalentLMS
- Bulk import: Home > Users > Import; if a user with the same login (username) already exists, their info is **updated** (upsert semantics). https://help.talentlms.com/hc/en-us/articles/9652274499484-How-to-add-multiple-users-to-your-portal-at-once-Import
- Duplicate accounts: **TalentLMS has no built-in merge.** Documented workaround: manually transfer completion data from the account to be discarded to the one to keep, then delete the duplicate. https://help.talentlms.com/hc/en-us/articles/28896603531932-How-to-handle-duplicate-user-accounts-in-TalentLMS
- Deactivate (individual): Users > Edit > uncheck "Active" > Save. Deactivation **preserves all user data/progress**; distinct from delete. https://help.talentlms.com/hc/en-us/articles/9652291013788-How-to-deactivate-users-in-TalentLMS
- Deactivate on a specific future date: check "Deactivate at" on user Info tab, pick date. Also can be automated via a trigger (Pro/Enterprise). https://help.talentlms.com/hc/en-us/articles/9652321528732-How-to-deactivate-a-user-on-a-specific-date-in-TalentLMS
- Reactivate: re-check "Active" box on the same Edit screen (implied by same article family; explicit "reactivate" article not found for current UI — **unverified** exact separate article, but mechanism is the same toggle). https://help.talentlms.com/hc/en-us/articles/9652291013788-How-to-deactivate-users-in-TalentLMS
- Delete (permanent): Reports > Timeline, filter Event = "User deletion", click **Permanently delete** (two-step confirm). **Deleted users cannot be restored; all progress/records permanently lost** — explicitly contrasted with deactivation which preserves data. Undo (soft-delete recovery) only available for the **last 300 deleted users or 30 deleted courses** before permanent purge. https://help.talentlms.com/hc/en-us/articles/9651506819612-How-to-delete-users-and-courses-permanently-in-TalentLMS ; restore mechanism (Legacy) https://help.talentlms.com/hc/en-us/articles/360014573074-How-to-restore-deleted-users-and-courses
- Self-delete (GDPR): learners can self-delete; a portal admin can restore only by contacting support/authorized action. https://help.talentlms.com/hc/en-us/articles/9652274328732-How-can-users-self-delete-their-account-in-TalentLMS
- Password reset: user-initiated via "Forgot your password?" (email/username + reset link). No explicit "admin-forces-reset" article found in search results — **unverified** whether admin can force-reset vs only self-service. https://help.talentlms.com/hc/en-us/articles/9651529942812-How-to-reset-your-password-on-TalentLMS
- Login-as / impersonate: Admin > Users > click sign-in icon in Options column, or from user profile "More… > Log into account." Admin can switch back via return icon on top bar. (Article found for Legacy interface; same capability, **current-UI-specific article not directly confirmed** — treat as verified-for-Legacy, likely-same-in-current, unverified exact new-UI URL.) https://help.talentlms.com/hc/en-us/articles/360014573114-How-to-login-as-another-user-in-the-Legacy-interface
- User expiration/course expiration: course-level "Expiration date = enrollment date + time limit" (auto-recalculated if time limit changes); separate from account deactivation date. https://help.talentlms.com/hc/en-us/articles/9651386888092-How-to-work-with-time-limits-and-expired-courses-in-TalentLMS

#### Groups / Branches
- Difference: Groups = flexible sets of users (for org/reporting/selling bundles), Branches = separate sub-portals/organizational units. https://help.talentlms.com/hc/en-us/articles/9651522351260-What-is-the-difference-between-groups-and-branches-in-TalentLMS
- Create group: Home > Groups > Add group; optional Price (sell bundle) or **Group key** for self-registration. https://help.talentlms.com/hc/en-us/articles/9651522442396-How-to-work-with-groups-in-TalentLMS
- Group key / self-join: check "Assign group key" to generate a key; share with users to self-register. Requires the "Group key" permission enabled for the user's User Type (Account & Settings > User types > Learner tree > Course catalog). https://help.talentlms.com/hc/en-us/articles/9651522442396-How-to-work-with-groups-in-TalentLMS
- Assign group to a branch: on the group's Info tab, pick branch from dropdown, Save. https://help.talentlms.com/hc/en-us/articles/10730406045980-How-to-use-groups-in-branches-in-TalentLMS
- Add/remove members to group/branch: available both individually and via mass actions (see below).

#### Course enrolment
- Individual: "How to add users to courses" — assign existing users directly to a course. https://help.talentlms.com/hc/en-us/articles/9651387104284-How-to-add-users-to-courses-in-TalentLMS
- Bulk: "How to enroll multiple users to a course at once." https://help.talentlms.com/hc/en-us/articles/20287329508508-How-to-enroll-multiple-users-to-a-course-at-once-in-TalentLMS
- Enrolment requests (self-enrol with admin approval): https://help.talentlms.com/hc/en-us/articles/18294487844764-How-to-work-with-course-enrollment-requests-in-TalentLMS
- Automations (rules engine): trigger-based actions, e.g. "Z hours after course X assignment, assign course(s) Y"; "Z hours after certificate expiration, reset and assign course(s) Y"; also can deactivate users inactive for a set period. Admin > Automations. https://help.talentlms.com/hc/en-us/articles/9651467215900-How-to-work-with-automations-in-TalentLMS

#### Staff / roles
- Three base roles: Administrator, Instructor, Learner — from which default user types (SuperAdmin, Admin-type, Trainer-type, Learner-type) derive. **Custom User Types** can be created per base role with granular permission tree (Account & Settings > User types). https://help.talentlms.com/hc/en-us/articles/9652280520092-A-guide-to-the-TalentLMS-user-types
- Change a user's role portal-wide or per-course: dedicated action. https://help.talentlms.com/hc/en-us/articles/9652335763996-How-to-change-a-user-s-role-across-your-portal-or-on-a-single-course

#### Mass/bulk actions (Users page)
- Confirmed list: **Activate, Deactivate, Delete, Add to branch, Remove from branch, Add to group, Remove from group, Send message.** Selection via checkboxes, then "Mass actions" dropdown. https://help.talentlms.com/hc/en-us/articles/9652274050588-How-to-perform-mass-actions-on-users
- Mass deactivation on specific dates also supported (Legacy-confirmed article; presumed current-UI equivalent). https://help.talentlms.com/hc/en-us/articles/360014660133-How-to-mass-deactivate-users-on-specific-dates

#### Export
- Reports > Users > "Save as CSV": exports status (active/inactive), user type, last login, courses assigned/completed, gamification stats, custom fields. https://help.talentlms.com/hc/en-us/articles/9652244802204-How-to-export-user-reports-in-TalentLMS
- Full portal Export (CSV/XLSX) includes users, courses, categories, branches, groups, custom fields, and relationships between them. https://help.talentlms.com/hc/en-us/articles/9651492281756-How-to-import-export-data-in-TalentLMS

#### Audit / reversibility
- **Timeline** (Reports > Timeline): "records and stores nearly every event that occurs on your TalentLMS portal," filterable by Event type (incl. "User deletion," "Added user to course"), date range, user, course; exportable to CSV. This is the closest TalentLMS has to an audit log. https://help.talentlms.com/hc/en-us/articles/9652229276828-How-to-work-with-the-extended-timeline
- Deactivate = reversible, preserves data. Delete = **not reversible** once "Permanently delete" confirmed (soft-delete undo window limited to last 300 users/30 courses). https://help.talentlms.com/hc/en-us/articles/9651506819612-How-to-delete-users-and-courses-permanently-in-TalentLMS
- Effect of unenrolment on progress: **not found in primary sources searched — unverified.**

#### Documented gaps
- No native merge-duplicate-accounts feature; official workaround is manual data transfer + delete, i.e. an acknowledged gap. https://help.talentlms.com/hc/en-us/articles/28896603531932-How-to-handle-duplicate-user-accounts-in-TalentLMS
- support.talentlms.com hosts a "Knowledge Base & Feature Ideas" board (legacy support portal) but a specific current feature-request URL for learner-management gaps was not located in this research — **unverified** which open ideas exist. http://support.talentlms.com/knowledgebase

---

### 2. Docebo

#### Learner management
- Create/manage users: Admin > Manage Users; supports manual create, CSV import, or API. https://help.docebo.com/hc/en-us/articles/360020084460-Creating-and-managing-users
- CSV import upsert: for existing users, must select **"Update Information for existing users"** under Update Users section; flagged imports overwrite existing user info. Branch handling on update: platforms activated after **Oct 21, 2019** move users by default to the new branch (no copy option); older platforms can choose copy vs move. https://help.docebo.com/hc/en-us/articles/360020128839-Importing-and-managing-users-via-CSV-files
- Merge duplicate profiles: **native "Merge user profiles" feature exists** — source profile's data merged into destination profile. Restriction: cannot merge Superadmins or Power Users. https://help.docebo.com/hc/en-us/articles/360020082480-Merging-user-profiles
  - Documented limitations (community, corroborating official gap): archived enrollments and Learning Plan enrollments are **not** transferred during merge — users must re-enrol in learning plans post-merge. https://community.docebo.com/product-q-a-7/best-practice-for-merging-two-user-accounts-with-separate-learning-histories-9502
- Account statuses (platform level): **Activated / Deactivated / Expired.** Deactivated = exists but no platform access (login blocked with error). Expired = reached set expiration date, also loses access; expired users **retain** whichever activation state (activated/deactivated) they had when they expired. https://help.docebo.com/hc/en-us/articles/20923512163602-User-account-statuses
- User expiration date: settable per user; distinct from deactivation. Edited individually or in bulk via "Edit User Fields" mass action. https://help.docebo.com/hc/en-us/articles/360020126399-Managing-users-with-mass-actions
- Delete user: **permanently deletes**, "cannot be undone," and **also deletes any asset the user uploaded to the platform.** https://help.docebo.com/hc/en-us/articles/360020126399-Managing-users-with-mass-actions
- Password/email fields, role, manager, language: editable individually or via bulk "Edit User Fields." https://help.docebo.com/hc/en-us/articles/360020126399-Managing-users-with-mass-actions
- Login-as / impersonate: exists (referenced by Audit Trail doc tracking "impersonation details" of who performed actions while impersonating) — dedicated how-to article not directly retrieved; **partially verified** via Audit Trail article. https://help.docebo.com/hc/en-us/articles/360020124059-Managing-the-Audit-trail

#### Groups / Branches
- Branches: static, org-chart-style structure; a user belongs to only **one** branch (or sub-branch). https://help.docebo.com/hc/en-us/articles/360020084140-Creating-and-Managing-an-Organization-Chart
- Groups: static (manually added members) or **automatic/dynamic** (rule-based on profile fields and/or course status); a user can belong to **multiple** groups. https://help.docebo.com/hc/en-us/articles/360020084100-Managing-groups ; community best-practice explainer: https://community.docebo.com/product-q-a-7/groups-vs-branches-10425
- Groups do not fully control Power User resource-access the way branches do (per community best-practice discussion, corroborating help docs' "resources" model for Power Users). https://community.docebo.com/product-q-a-7/groups-vs-branches-10425

#### Course enrolment
- Individual and bulk enrolment via Manage Enrollments (Courses > Enrollments tab), or CSV. https://help.docebo.com/hc/en-us/articles/360020124659-Managing-enrollments-of-courses-and-sessions ; CSV: https://help.docebo.com/hc/en-us/articles/9298423851794-Enrolling-users-in-courses-and-sessions-using-CSV-files
- Enrolment statuses: **Enrolled/Subscribed** (not yet started), **In progress**, **Completed**, **Waiting users** (ILT waitlist — placed there due to capacity/policy or manually by Superadmin/Power User), **Enrollment to confirm**, **Suspended** (manually set by Superadmin/Power User; suspended users lose access to training material/course pages while suspended), **Overbooking**. https://help.docebo.com/hc/en-us/articles/21854582461458-Enrollment-statuses
- Enrolment validity dates: "Active from" / "Active until" set per course for all enrolled learners, and can be **overridden per learner** by editing the individual enrolment. If enrolment not yet valid, course is locked with a "starts on" indicator; once valid, shows expiration if set. Time-based validity: expiration = status-change date + configured number of days. https://help.docebo.com/hc/en-us/articles/360020126779-Setting-time-validity-for-courses
- Enrolment Rules app (automation): auto-enrols users into e-learning courses, ILT courses, and Learning Plans based on **branch or group membership** (cannot combine branches+groups, or courses+learning plans, in one rule). ILT **sessions** not supported by rules. https://help.docebo.com/hc/en-us/articles/360020128579-Activating-and-managing-the-Enrollment-rules-app
- **Automatic unenrolment is NOT supported** by Enrollment Rules — documented gap; workaround is manual/bulk **rollback** from the rule's Logs tab (single user or selection), which unenrols them from ALL courses/learning-plans that rule auto-enrolled them into. https://help.docebo.com/hc/en-us/articles/360020128579-Activating-and-managing-the-Enrollment-rules-app (rollback detail corroborated by community: https://community.docebo.com/product-q-a-7/unenroll-rules-11833)

#### Staff / roles
- Three account **levels**: User, Power User, Superadmin. https://help.docebo.com/hc/en-us/articles/360020082940-User-levels-roles-and-statuses
- Course-context **roles**: learner, tutor, instructor, manager, expert. https://help.docebo.com/hc/en-us/articles/360020082940-User-levels-roles-and-statuses
- **Power Users**: given a scoped subset of Superadmin permissions via assignable **permission profiles** (a profile can be applied to multiple Power Users; a Power User can hold multiple profiles). Scope defined by assigned **resources**: users, groups, branches, courses, learning plans, catalogues, channels, pages, menus, etc. Power Users can see info about groups/branches their managed users belong to even if not directly assigned to them; a branch itself can be assigned as a resource, granting management of its users. https://help.docebo.com/hc/en-us/articles/360020081500-Creating-and-managing-Power-Users ; https://help.docebo.com/hc/en-us/articles/6463399445394-Power-User-permissions
- Bulk Power User creation via CSV also documented (community API note, not fully primary — **partially unverified** detail; general CSV user-import mechanism is primary-confirmed above). https://community.docebo.com/api-webhooks-95/api-browser-quick-grabs-bulk-create-power-users-9005

#### Mass/bulk actions (All Users table)
- Confirmed action list: **Add to Branch, Activate Users, Deactivate Users, Edit User Fields** (password, email-validation status, expiration date, language, role, direct manager, additional fields), **Delete Users**. Selections over 250 users run as a **background job**. https://help.docebo.com/hc/en-us/articles/360020126399-Managing-users-with-mass-actions
- Bulk unenrol from courses/learning plans available via API ("Bulk Unenroll Users") — **API-level, not confirmed as a UI mass action**; community reference only. https://community.docebo.com/api-webhooks-95/api-browser-quick-grabs-bulk-unenroll-users-from-courses-or-learning-plans-7044

#### Audit / reversibility
- **Audit Trail app**: "an immutable record that keeps track of administrative actions performed in the system," including changes to course completion and enrolment status, and records **who** (including impersonation identity), **what** resource, and **when**. Positioned for regulatory-compliance accountability. https://help.docebo.com/hc/en-us/articles/360020124059-Managing-the-Audit-trail ; event catalogue: https://help.docebo.com/hc/en-us/articles/6095145987346-Audit-trail-events-details
- Retention period of Audit Trail entries: **not found/confirmed in sources retrieved — unverified.**
- Delete user = irreversible, also purges uploaded assets (see above) — no restore documented. https://help.docebo.com/hc/en-us/articles/360020126399-Managing-users-with-mass-actions
- Deactivate = reversible (status toggle), data retained (implied by status model, not explicitly restated per-deactivation — reasonably inferred from "Activated/Deactivated" status article). https://help.docebo.com/hc/en-us/articles/20923512163602-User-account-statuses
- Effect of unenrolment on progress: **not found in primary sources searched — unverified.**

#### Documented gaps
- Automatic unenrolment absent from Enrollment Rules app (Docebo help article itself states the limitation, not just a complaint). https://help.docebo.com/hc/en-us/articles/360020128579-Activating-and-managing-the-Enrollment-rules-app
- Merge does not carry over archived enrolments / Learning Plan enrolments — flagged in Docebo Community by users, and per one report Docebo staff acknowledged it as a possible bug with no resolution at time of posting. https://community.docebo.com/docebo-superadmins-46/unique-merge-request-14777 ; https://community.docebo.com/product-q-a-7/best-practice-for-merging-two-user-accounts-with-separate-learning-histories-9502
- Bulk "select all / move to branch" reported broken by a user on the official feedback board. https://community.docebo.com/docebo-feedback-68/select-all-moving-users-to-new-branch-doesn-t-work-13639
- Community members note no bulk-action or reporting view for "which groups a learner belongs to" — gap noted on Docebo's own community feedback forum. https://community.docebo.com/community-feedback-43/how-to-view-groups-including-a-learner-5749
- General feedback/ideas boards exist at https://community.docebo.com/feedback-requests-1 and https://community.docebo.com/docebo-feedback-68 (official Docebo-hosted community, primary channel for feature requests).

---

### 3. LearnDash

Note: LearnDash's official support docs (learndash.com/support/...) currently 302-redirect to **docs.nexcess.com/software/learndash/...** (Nexcess/Liquid Web acquired LearnDash); content there is treated as the current official documentation destination.

#### Learner management
- LearnDash core relies on **WordPress core user management** (Users screen) for create/invite/deactivate/delete/reset-password — LearnDash itself layers course/group access on top rather than replacing WP user admin. (Inferred from doc structure; explicit statement not directly quoted — **partially unverified**, based on absence of any LearnDash-specific create/delete/deactivate/reset-password/impersonate articles found, and presence of WP-standard "User Management" doc.) https://learndash.com/support/kb/core/users/user-management/
- No LearnDash-specific: account **deactivate**, **delete semantics**, **merge**, **login-as/impersonate**, or **user expiration date** articles were found in official docs during this research — **unverified / likely not native features** (commonly added via 3rd-party plugins, out of scope per "primary sources only").

#### Groups (LearnDash has no "branches" concept — groups only)
- **Group Leader role**: WordPress user role LearnDash uses to grant group-management permissions. https://learndash.com/support/kb/core/groups/group-leader-capabilities/ (redirects to) https://docs.nexcess.com/software/learndash/group-leader-capabilities/
- Group Leader capability tiers: **Basic** = core permissions to manage assigned groups/courses/users; **Advanced** = adds management of content created by others, private items, higher-impact admin actions. https://docs.nexcess.com/software/learndash/group-leader-capabilities/
- Confirmed Group Leader actions: manage users in their group(s)/course(s) via LearnDash LMS > Groups > Group Administration > List Users; review/approve assignment submissions; review/approve essay submissions; email everyone in a managed group; export group-related reports (course data, quiz data). https://docs.nexcess.com/software/learndash/group-leader-capabilities/
- **"Group Leader user management" setting** — confirmed name in docs is **"Manage Users"**: enables Group Leaders to "access the user profiles to add or remove progress, manage specific user access, creating and deleting users, etc." Scope again split Basic (own groups/users only) vs Advanced (all users/groups site-wide). https://docs.nexcess.com/software/learndash/global-group-settings/
- Add/remove users to a group: via arrow-list UI (move between "available"/"group" columns) in Group admin; for **Group Registration** add-on, Group Leaders can either directly remove users or a removal request is routed to an admin who accepts/rejects it under LearnDash LMS > Groups. https://learndash.com/support/kb/add-ons/uncategorized/group-registration/
- Group access "End date": ends access to the group **and all its courses** for **all** enrolled users on a set date; no start date required. https://learndash.com/support/kb/core/groups/group-access-settings/ (via redirect to docs.nexcess.com equivalent)
- Course auto-enrolment via group: adding a course to a group can auto-enrol all group members; global setting controls whether this is automatic or requires explicit user course-enrolment. Enrolment date/duration/expiration for group-added courses is calculated from **when the course was added to the group**, not when the individual user joined the group. https://learndash.com/support/kb/core/uncategorized/group-users-leaders/ (search-derived; direct nexcess equivalent not separately fetched — **moderately verified**)

#### Course enrolment
- Individual enrolment: standard WP/LearnDash course access assignment (per-user).
- Bulk/group enrolment: primarily via **group course assignment** (add a course to a group → all members enrolled) or **CSV bulk import via Group Registration add-on** (download CSV template, fill, upload). https://learndash.com/support/kb/add-ons/uncategorized/group-registration/
- Enrolment "rules"/automation equivalent to Docebo's Enrollment Rules app: **not found — likely does not exist natively**, unverified.

#### Staff / roles
- Roles found: **Administrator** (WP), **Group Leader** (LearnDash-specific WP role). No LearnDash-native "Instructor" role/marketplace-style capability distinctions were surfaced in this research within the excluded scope — **unverified** whether an "Instructor" role exists as a first-class LearnDash concept (may require add-on).

#### Mass/bulk actions — documented as bulk-only / bulk-first, or missing
- Group Leaders **can** bulk-enrol users into a group via CSV upload (Group Registration add-on: sample CSV template on Groups Dashboard, single "email" column). https://learndash.com/support/kb/add-ons/uncategorized/group-registration/
- **Longstanding documented gap**: "the LearnDash development team has been unable for many years to realize the possibility of bulk actions for enrolling users to the groups and unenrolling from the groups directly in the Users table" (WP admin Users screen) — i.e. no native bulk enrol/unenrol row-action from the standard WP Users list; only via the group-side CSV workflow. Source for this specific claim was a search-engine synthesis rather than a directly quoted primary page — **flagged as needing re-verification**; treat as unverified pending direct citation. (No direct URL captured for this exact quote.)

#### Audit / reversibility
- **No LearnDash-native audit-trail/event-log feature found** in official docs (consistent with brief's expectation of "probably none"). No article located covering an audit log, activity log, or timeline for admin/group-leader actions. **Unverified as an explicit absence** (could not confirm a negative beyond "not found"), but strongly suggested by lack of any such doc page across all searches performed.
- Group end-date behavior (access removal) and its effect on stored progress: not documented in sources found — **unverified**.

#### Documented gaps / feature requests
- Official LearnDash Ideas & Improvements board (LoopedIn-powered): **https://app.loopedin.io/learndash/ideas** — public voting board for feature requests; confirmed as official channel, ~100 requests logged as of Dec 2023 per a third-party writeup (board itself is primary; the count is secondary and unverified as current). https://app.loopedin.io/learndash/ideas
- Specific open ideas about bulk group user-management / bulk enrol-unenrol from the Users table were **not individually retrieved with item-level URLs** in this pass — recommend a follow-up search directly on the LoopedIn board for "bulk," "group leader," "unenroll" if item-level citations are required.

---

### Summary of biggest unverified/gap items
- TalentLMS: no native effect-of-unenrolment-on-progress doc found; admin-forced password reset not confirmed; current-UI login-as article not directly located (Legacy-UI confirmed only).
- Docebo: Audit Trail retention period not found; UI-level (vs API-only) bulk unenrol from courses not confirmed.
- LearnDash: core user create/deactivate/delete relies on WordPress core (not LearnDash-specific docs); no audit log found (consistent with brief's expectation); "bulk enrol/unenrol from WP Users table" gap claim needs a directly-quoted primary citation to fully verify.
