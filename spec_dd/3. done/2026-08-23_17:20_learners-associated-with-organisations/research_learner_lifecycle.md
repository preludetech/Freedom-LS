# Research: the learner roster lifecycle in other LMS/SaaS products

> Researched for the "learners associated with organisations" idea. Question: once "learner belongs
> to organisation" becomes an explicit `Learner` row rather than a fact derived from registrations,
> who creates and destroys that row, and what goes wrong when they do?

---

## 1. Creation triggers

Ranked roughly by how common and how load-bearing each trigger is across the products surveyed.

1. **Implicit, via enrolment/cohort membership (the most common and most load-bearing trigger).**
   In every product that syncs a group construct to courses, joining the group *is* the membership
   trigger — there is no separate step. Moodle's cohort sync enrolment method enrols (and by default
   un-enrols) a user in a course purely because cohort membership changed
   ([Cohort sync](https://docs.moodle.org/502/en/Cohort_sync),
   [Cohorts FAQ](https://docs.moodle.org/502/en/Cohorts_FAQ)). Docebo and TalentLMS both let an admin
   "enrol all users in this branch" in one action, and branch membership is the thing that decides who
   is swept up (TalentLMS: [branches](https://help.talentlms.com/hc/en-us/articles/10730422734236-How-to-use-branches-for-multi-purpose-training-in-TalentLMS);
   Docebo: [Organizing users with branches](https://help.docebo.com/hc/en-us/articles/360020084140-Organizing-users-with-branches)).
   This maps closely to what FLS already has today (organisation reached via cohort/registration) —
   it is the baseline every other trigger sits on top of, not a separate mechanism.

2. **Manual add by an admin/educator.** Docebo and TalentLMS both expose an explicit "move/add user(s)
   to branch" action, independent of any course action — via mass actions on the user list
   ([Docebo mass actions](https://help.docebo.com/hc/en-us/articles/360020126399-Managing-users-with-mass-actions),
   [TalentLMS mass actions](https://help.talentlms.com/hc/en-us/articles/9652274050588-How-to-perform-mass-actions-on-users)).
   Blackboard exposes membership on an "Organization" as its own role-assignment surface, separate
   from course enrolment ([Enroll Users](https://help.blackboard.com/Learn/Administrator/SaaS/Courses/Enroll_Users)).
   This is common wherever the membership construct is treated as a first-class object rather than a
   side-effect.

3. **Bulk CSV import.** Docebo's CSV import supports a `branch_code` field to place/move users by
   branch in bulk, and it is explicitly called out as the tool of choice for reorganising large numbers
   of users at once (used, for example, to move deactivated users into a holding branch —
   [deactivated users discussion](https://community.docebo.com/docebo-superadmins-46/deactivated-users-10429)).
   TalentLMS has an equivalent import path. Treated everywhere as an admin-side bulk variant of #2, not
   a separate concept.

4. **Self-registration via a branch/org-specific signup URL.** TalentLMS generates a branch-specific
   signup URL, and a branch can define a **default group** that is auto-assigned to anyone who
   registers through that URL, which is also how default course assignment on signup is implemented
   ([self-register](https://help.talentlms.com/hc/en-us/articles/9652306120348-How-to-allow-users-to-self-register-sign-up-in-TalentLMS),
   [assign courses upon registration](https://help.talentlms.com/hc/en-us/articles/360014572374-How-to-assign-courses-to-users-upon-registration)).
   Docebo has the equivalent via its Extended Enterprise sub-domain feature (below). Load-bearing for
   products that sell self-serve B2B2C training; irrelevant to FLS in this cut since student-facing UI
   and self-registration are explicitly out of scope for the Learner cut.

5. **SSO/SAML attribute mapping.** Docebo lets an admin map an IdP attribute to "Branch Name" or
   "Branch Code" so a user lands in the right branch on first login via SSO
   ([Docebo for SAML — Okta example](https://help.docebo.com/hc/en-us/articles/8676613427858-Docebo-for-SAML-Okta-single-sign-on-configuration-example),
   [SAML legacy configuration](https://help.docebo.com/hc/en-us/articles/31128852079506-SAML-legacy-configuration)).
   Notably, this trigger is **weaker than it sounds**: Docebo's own docs warn that branch creation via
   SAML/CSV-at-SSO-time is not supported, and newly-provisioned SSO users land in the *root* branch
   unless the separate Extended Enterprise sub-domain feature is active — i.e. even a mature product
   treats "SSO decides your org" as a partial, add-on capability, not the default path. Not relevant
   to FLS today (no SSO).

6. **Invite link/code.** Present in various forms (Docebo user invites, TalentLMS/Absorb invitation
   emails) but functions as a delivery mechanism for #4/#2 rather than a distinct membership-creation
   rule — the invite just pre-fills who gets added and to what group. Not independently significant.

**Open edX is the outlier worth naming explicitly.** Its "Organization" is fundamentally a *course
authoring/ownership* scope (which Studio users can create courses under which org key,
[OEP-66](https://docs.openedx.org/projects/openedx-proposals/en/latest/best-practices/oep-0066-bp-authorization.html)),
not a learner-roster construct at all — learners are only ever enrolled per-course
([course staffing](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-ficus.master/set_up_course/course_staffing.html);
[edunext multi-tenancy overview](https://www.edunext.co/articles/open-edx-multi-tenancy-enhanced-features/)).
This is a useful reminder that "explicit learner-to-org membership" is a deliberate product choice, not
something every LMS needs — FLS's decision to add it is closer to the Docebo/TalentLMS branch model
than to Open edX's org-as-authoring-scope model.

## 2. Manual roster management

Every product that treats the org/branch as a first-class object also gives admins an **explicit
add/remove action on the roster itself**, separate from "enrol in a course":

- **Docebo**: mass actions let an admin move selected users into/out of a branch with no course
  action attached ([mass actions](https://help.docebo.com/hc/en-us/articles/360020126399-Managing-users-with-mass-actions)).
- **TalentLMS**: branch admin screens support adding/removing users to a branch directly
  ([work with branches](https://help.talentlms.com/hc/en-us/articles/10730422769436-How-to-work-with-branches)).
- **Blackboard**: "Organization Roles" is its own management surface distinct from course enrolment
  ([Enroll Users](https://help.blackboard.com/Learn/Administrator/SaaS/Courses/Enroll_Users)).

None of the products surveyed ships a **read-only, purely-derived** roster once the org/branch object
exists — the moment a product decided the membership was worth its own row, it also gave admins a
direct lever on that row. This is a meaningful signal: a derive-only Learner (computed live from
registrations, never independently editable) would be an unusual choice given the precedent, and would
not solve the problem that motivated adding the row in the first place (see §6/recommendation).

## 3. Removal semantics — the important part

This is where products diverge sharply, and where the failure mode the research question is worried
about is real and well documented.

**Deleted vs deactivated vs archived, by product:**

- **Canvas** has the cleanest three-state model, and it lives on the *enrolment*, not on any
  account/org-level membership object: `active`, `invited`, `creation_pending`, `completed`,
  **`inactive`**, and **`deleted`** are all valid `workflow_state` values on an Enrollment, with a
  documented, separate reactivation endpoint for `inactive` enrolments
  ([Enrollments API](https://www.canvas.instructure.com/doc/api/enrollments.html);
  confirmed by admin/developer discussion of the inactive-vs-deleted split —
  [GitHub #1723](https://github.com/instructure/canvas-lms/issues/1723),
  [inactive status? thread](https://groups.google.com/g/canvas-lms-users/c/dic5DkHlHJA)). `inactive`
  blocks participation but is fully recoverable and keeps grades; `deleted` is the destructive,
  effectively non-recoverable state.

- **Absorb** draws the same distinction but names it differently, and is the single clearest example
  of a product that made "soft" the *safe default* precisely because hard removal destroys reporting
  history: re-enrolling (or the standard "unenrol" mass action) moves the learner's active enrolment
  into their **Enrollment History**, preserving status and progress, whereas the separate **Delete**
  action on an enrolment removes it and it is **not** retained in history at all
  ([Understanding Enrollment](https://support.absorblms.com/hc/en-us/articles/32624653167251-Understanding-Enrollment),
  [Re-Enrollment & Re-Certification](https://support.absorblms.com/hc/en-us/articles/219544607-Re-Enrollment-Re-Certification),
  [Learner Un-Enrollment](https://support.absorblms.com/hc/en-us/articles/1500010095222-Learner-Un-Enrollment)).
  Absorb's own support docs effectively tell admins: use unenrol/re-enrol, not delete, if you care about
  the record.

- **Docebo** admins on the community forum are explicit that this distinction matters in practice:
  *"Docebo does not do any type of automated un-enrolment when users are deactivated"* and *"if you were
  to unenroll users who had completed courses, you would actually be removing their learning history and
  affecting your historical reports"*
  ([deactivated users thread](https://community.docebo.com/docebo-superadmins-46/deactivated-users-10429)).
  Their recommended pattern is to move deactivated/departed users to a separate branch (or an
  automatic group) and leave enrolments untouched, rather than unenrol — i.e. the community-level
  best practice is "change branch/status, never touch the enrolment," which only works because branch
  membership and enrolment lifecycle are already independent of each other in Docebo. Deletion itself
  is discussed only as a mechanical bulk operation in the forums, with no documented statement of what
  survives it — which is itself telling: it's treated as a break-glass operation, not a supported
  roster-maintenance path
  ([mass deletion thread](https://community.docebo.com/product-q-a-7/mass-deletion-of-users-in-docebo-10170)).

- **Moodle**'s cohort sync is the sharpest cautionary tale, because it is the *opposite* of soft-by-default:
  the enrolment method has an explicit **"unenrol action"** setting that controls what happens when a
  user leaves the cohort, and the default is destructive — the user is unenrolled from every course
  synced from that cohort the moment they leave it
  ([Cohort sync](https://docs.moodle.org/502/en/Cohort_sync)). Admins can instead choose "keep the
  enrolment, just remove the role/suspend access" to preserve grades, but this is opt-in configuration,
  not the default, and there is a long trail of forum threads from admins surprised or unhappy about it:
  [Prevent unenroll when removed from cohort](https://moodle.org/mod/forum/discuss.php?d=439414),
  [Cohort Sync — Remove enrolment method — What happens?](https://moodle.org/mod/forum/discuss.php?d=395009&lang=en_us),
  [Unenrolling a single user enrolled via cohort sync](https://moodle.org/mod/forum/discuss.php?d=397946),
  [Cohort sync — suspend enrolment instead of unenroll](https://moodle.org/mod/forum/discuss.php?d=440135),
  [Suspend a Cohort Sync user](https://moodle.org/mod/forum/discuss.php?d=208915). Separately, Moodle's
  general unenrolment docs confirm suspend-vs-unenrol is the recognised safe/unsafe pair at the
  single-course level too: *"Unenrolment removes the user... and may remove or delete their course
  data including grades"* vs suspend, which *"blocks access... without affecting their data"*
  ([Unenrolment](https://docs.moodle.org/502/en/Unenrolment),
  [difference between unenrol or disable course enrolment](https://moodle.org/mod/forum/discuss.php?d=437929),
  [should suspended users appear in the gradebook?](https://moodle.org/mod/forum/discuss.php?d=172365)).

**Re-adding and history.** Where the product distinguishes inactive/suspended from deleted, re-adding
restores full history (Canvas reactivation, Absorb archived Enrollment History, Docebo's advice to
never touch the enrolment in the first place). Where a product only offers hard removal (Moodle
cohort-sync default), re-adding starts a fresh enrolment and the *appearance* of lost history is exactly
the complaint driving the forum threads above — whether or not the underlying grade rows are technically
retained (Moodle's data model does retain grade history under some retention settings), admins clearly
experience unenrol-on-cohort-exit as data loss, which is the perception failure mode as much as a
technical one.

**Verdict for the research question.** The failure mode named in the brief — "deleting a membership
silently destroys or orphans progress data" — is real, documented, and is exactly why Absorb built a
separate Delete vs Unenrol pair, why Canvas has an inactive state distinct from deleted, and why Moodle
admins keep asking for cohort-sync to default to suspend instead of unenrol. Every product that got this
right did so by **never letting the higher-level membership object's lifecycle directly delete the
lower-level enrolment/progress rows** — removal at the roster level either does nothing to the
enrolment (Docebo's actual behaviour) or flips a status flag on it (Moodle's opt-in "keep enrolled"
setting, Canvas's `inactive`), and a *separate*, deliberate action is required to actually delete
enrolment/progress data.

## 4. Status fields

A genuinely interesting, consistent pattern across every product studied: **none of them puts a rich
status directly on the org/branch membership row itself.** The membership link (cohort member, branch
member) is essentially binary — you're in or you're not. All the interesting state — active, inactive,
suspended, pending/invited, completed — lives one level down, on the **enrolment**, or one level up, on
the **user account**:

- Canvas: status lives on the Enrollment (`active`/`invited`/`inactive`/`completed`/`deleted`), not on
  any account-level org membership — Canvas doesn't really have one below sub-account
  ([Enrollments API](https://www.canvas.instructure.com/doc/api/enrollments.html)).
- Moodle: status (`active`/`suspended`) lives on the `user_enrolment` row per course, not on cohort
  membership, which has no status field at all — you're a cohort member or you're not
  ([Cohort sync](https://docs.moodle.org/502/en/Cohort_sync)).
- Docebo: the deactivated/active distinction lives on the **user account**, orthogonal to which
  branch(es) the user sits in; branch placement itself carries no separate status
  ([deactivated users thread](https://community.docebo.com/docebo-superadmins-46/deactivated-users-10429)).
- Absorb: status (active/completed/not-completed, plus an admin override) lives on the enrolment
  ([Enrollment, Completion & Progress](https://support.absorblms.com/hc/en-us/articles/115015751048-Enrollment-Completion-Progress)).

The regret pattern in the sources is specifically about **conflating** these layers — Moodle's
cohort-sync default conflates "left the cohort" with "should lose course access/data," which is exactly
the wrong layer to carry that decision on, and is the source of most of the forum complaints above.

## 5. The auto-created-row trap

Two distinct, opposite-facing versions of this trap show up in the research, and FLS should design
against both:

**A. Stale/orphaned rows that outlive their trigger ("ghost" rows).** Where membership is a side-effect
of something else and nothing actively prunes it, it lingers indefinitely. This shows up most sharply
as a *licensing* problem: the "Ghost User" pattern — inactive accounts that remain registered (and
billed per seat) long after the person left, because deleting the row would also destroy the compliance
record the organisation is legally required to keep
([The Ghost User Trap](https://www.atrixware.com/blog/wp/the-ghost-user-trap-aligning-lms-spend-with-actual-utilization/)).
Docebo's admin community confirms this is deliberate current behaviour, not a bug: deactivating a user
does not auto-clean anything downstream
([deactivated users thread](https://community.docebo.com/docebo-superadmins-46/deactivated-users-10429)).
Whether this counts as "the bug" depends entirely on whether the product gives admins a *separate*,
intentional lever to clean it up when they actually want to (active-vs-registered billing splits,
archiving flows) — products that don't are the ones users complain about.

**B. Over-eager cascading deletes when the trigger disappears.** Moodle's cohort sync is the mirror
image: removing the *trigger* (cohort membership) by default destructively removes the *consequence*
(course enrolment), and admins have been asking Moodle for years to decouple the two
([Prevent unenroll when removed from cohort](https://moodle.org/mod/forum/discuss.php?d=439414),
[Cohort Sync — Remove enrolment method](https://moodle.org/mod/forum/discuss.php?d=395009&lang=en_us)).

Both failure modes are real and documented; they sit at opposite ends of the same design question —
**"when the thing that created a row goes away, what happens to the row?"** — and the answer that
avoids both traps in the products that got it right (Canvas, Absorb, Docebo's advised practice) is:
*nothing happens automatically to the downstream row*, and cleanup (if wanted) is a distinct, deliberate
admin action, informed by knowing *why* the row exists in the first place (see recommendation on a
`source`/provenance field below).

## 6. Bulk operations and reporting

- **Bulk add/remove/suspend is standard**, not a power-user edge case, in every product with an
  explicit membership object: Docebo mass actions
  ([Managing users with mass actions](https://help.docebo.com/hc/en-us/articles/360020126399-Managing-users-with-mass-actions)),
  TalentLMS mass actions
  ([mass actions](https://help.talentlms.com/hc/en-us/articles/9652274050588-How-to-perform-mass-actions-on-users)),
  Docebo CSV import by `branch_code`. These exist because branches/orgs in those products routinely
  hold hundreds to thousands of users — a different scale than FLS's stated "2–5 organisations per
  site."
- **Absorb's Department Templates** show the membership row doing double duty as a *reporting/UX
  segmentation* key, not just an access-control link — changes to a department template affect exactly
  the learners belonging to that department
  ([Overview of Curriculum Settings](https://support.absorblms.com/hc/en-us/articles/22943771271571-Overview-of-Curriculum-Settings)).
- **Licensing is the strongest evidence that a membership row often exists mainly for counting, not
  access control.** The per-seat vs per-active-user tension described in the Ghost User research and
  general LMS pricing surveys exists *because* vendors use the registered/member-of-org row as the
  billing unit, independent of whether that row does anything for access control that day
  ([Ghost User Trap](https://www.atrixware.com/blog/wp/the-ghost-user-trap-aligning-lms-spend-with-actual-utilization/),
  [LMS Pricing 2026](https://www.educate-me.co/blog/lms-pricing)). FLS has no seat-based billing today,
  but this is the pattern to recognise if/when it ever does: a `Learner` row is exactly the kind of
  object a future "active learners per organisation" metric would be built on, and its lifecycle
  decisions (soft vs hard removal, active/inactive) will directly become billing/reporting decisions
  even if that's not the reason it's being built now.

---

## What this suggests for FLS

**Creation triggers — build two, defer the rest.**

- **v1: implicit creation** when a user first gets a registration or cohort membership in an
  organisation (mirrors what nearly every product treats as the primary, load-bearing trigger, and
  matches FLS's existing derivation logic almost exactly — this is the smallest possible change from
  today's behaviour).
- **v1: manual add by an educator/staff member holding a role on that organisation** — see the
  dedicated recommendation below; this is not optional, it's the reason to build the row at all.
- **Defer:** bulk CSV import (no evidence FLS's stated scale — 2–5 organisations per site — needs it;
  every product that has it, has it because its branches hold hundreds+ of users), self-registration via
  an org-specific signup URL (blocked on student-facing UI being out of scope for this cut), SSO/SAML
  attribute mapping (FLS has no SSO), invite links/codes (a delivery wrapper around manual add, not a
  distinct mechanism — build it later if/when self-registration is built, not before).

**Removal — soft status, never a hard delete that touches registrations.** The evidence against hard
delete-as-default is consistent and comes from every product that has been burned by it: Canvas's
`inactive`/`deleted` split, Absorb's explicit Delete-vs-Unenrol pair (with support docs steering admins
away from Delete), Docebo admins warning in their own words that unenrolling completed learners destroys
learning history, and years of Moodle forum threads asking cohort sync to stop doing exactly that by
default. FLS is actually **better positioned than every product studied** to get this right cheaply:
`UserCourseRegistration` already carries its own `is_active` flag and its own `organisation` FK,
independent of any `Learner` row. That means the Learner row's lifecycle can be decoupled from
registration/progress lifecycle *by construction*, not by careful discipline layered on top after the
fact (which is what Docebo's community-sourced best practice amounts to). Concretely: removing a
`Learner` should flip its own `is_active` to `False` and must never cascade to `UserCourseRegistration`,
`CohortMembership`, or any progress model. Re-adding is just flipping it back — no history to restore,
because none was ever at risk.

**Minimal field set.** Every product surveyed puts rich status on the *enrolment*, not on the
org/branch membership row — the membership link itself is essentially binary everywhere. FLS should
follow that pattern rather than over-building the `Learner` row: `user` FK, `organisation` FK,
`is_active` boolean (matching the existing `UserCourseRegistration.is_active` convention), and enough
audit metadata to answer "who added this and when" (an `added_by` FK and timestamp), since accountability
for a manual-add action is the one thing every product's admin-facing add flow implies is needed. Add
one field the research specifically motivates that FLS doesn't have a precedent for yet: a **provenance
marker** (e.g. "created automatically from a registration" vs "added manually") — this is what lets a
future cleanup job resolve the auto-created-row trap correctly (safe to prune an auto-derived row with no
remaining registrations; never prune a manually-added one) without which FLS would have to guess, exactly
as Docebo currently does. Do **not** add invited/pending states in v1 — every product that has them uses
them to support self-registration/SSO flows FLS isn't building in this cut; adding the field now with
nothing to drive it is the "regretted" version of a status field the research surfaced.

**Should educators be able to add/remove learners manually in v1, or should Learner rows be
auto-derived only? Recommendation: yes, manual add/remove, in v1.**

Reasoning:

1. **Auto-derive-only doesn't solve the problem that motivated this cut.** The idea document is explicit
   that today "educators reach learners today purely by derivation" and that this is a limitation being
   fixed. If `Learner` rows are still only ever a byproduct of registrations, nothing has actually
   changed — an educator still can't reach someone before a registration exists (e.g. pre-building a
   roster ahead of a course going live, or tracking someone who's been told they'll join but hasn't
   registered yet). A derive-only implementation is extra schema for the same behaviour FLS already has.
2. **It's the universal shape, not an outlier choice.** Every product surveyed that promoted membership
   to a first-class object (Docebo branches, TalentLMS branches, Blackboard organisation roles) also gave
   admins a direct, manual lever on it, independent of enrolment. None of them shipped read-only/derived
   only once the object existed. Building FLS's the same way is the low-risk, well-precedented choice;
   building it derive-only would be the novel, unvalidated one.
3. **The blast radius is already bounded by existing access control.** The organisation-scoped
   authorisation boundary this feature sits on top of already restricts an educator to organisations they
   hold a role on. A manual-add action doesn't open a new privilege-escalation surface — it's bounded to
   exactly the organisations the educator can already see and act within.
4. **What to defer, specifically:** bulk manual-add tooling (mass actions, CSV) — start with one-at-a-time
   in the v1 UI, matching FLS's stated 2–5-organisation scale rather than the hundreds/thousands-of-users
   scale that motivated Docebo/TalentLMS's bulk tooling; and any UI for manual removal that implies or
   offers cascading deletion of registrations/progress — removal must only ever be the soft `is_active`
   flip described above, with no "also remove their registrations" option in v1, precisely because that
   option is where every product studied that went wrong, went wrong.

---

status: ok
