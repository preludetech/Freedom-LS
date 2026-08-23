# Research: what goes wrong when one person is a learner in several organisations on one platform

Scope note: this document researches the *human* failure modes of cross-organisation identity in
LMS/multi-tenant products, to inform the `learners-associated-with-organisations` idea, which adds an
explicit `Learner` model (user ↔ organisation) on top of the already-shipped `Organisation` layer
described in `spec_dd/3. done/2026-08-21_09:09_organisations/idea.md`. Evidence quality varies —
vendor documentation is reliable for "what the product does", forum/community threads are reliable
for "what actually goes wrong", and several claims below rest on a single anecdote; those are flagged
explicitly rather than presented as settled patterns.

---

## 1. The shared-profile problem

The recurring shape across every product researched: **one identity row, several organisations that
each believe they own it.** Vendors differ mainly in how much they admit this is unresolved.

- **Moodle Workplace** is the most explicit about the design. All user information across tenants
  lives in the same database and table; by default no personal data is shared between tenants and
  each is "unaware of the others". Crucially, Moodle Workplace does **not** give each tenant its own
  copy of core profile fields — instead a tenant admin gets *edit permission over locked profile
  fields* for users in their tenant, and separate "identity fields" can be defined per report so
  different tenants see different subsets of the same underlying fields. This is a partial answer to
  "who owns the name/email/phone": nobody owns it exclusively, but visibility and *editability* of
  specific fields can be scoped per tenant. ([Moodle Multi-tenancy docs](https://docs.moodle.org/502/en/Multi-tenancy))

- **Canvas** takes the opposite approach: it does not attempt shared-profile arbitration at all.
  Multiple institutions using Canvas independently and a learner enrolling at more than one produces
  genuinely separate accounts by default, each with its own profile, and Canvas's own documentation
  frames "Trust Accounts" (shared login) as an opt-in relationship between *specific* Canvas
  instances, not a general solution. When trust *is* configured and a user reuses the same email
  across institutions, the reported failure is not a subtle profile-sync bug but a much blunter one:
  accessing a course at one institution can pull in content or context from the other, and the fix
  offered to end users is an *account merge* — which is one-way and destructive (Canvas "will pick
  one account as the primary... Canvas has no control over which account is the primary, and the user
  must use the primary account going forward"). ([Instructure Community: merge accounts with same
  email](https://community.canvaslms.com/t5/Student-Guide/How-do-I-merge-my-user-account-with-an-account-using-the-same/ta-p/416),
  [Same email used — unable to access new course](https://community.instructure.com/t5/Canvas-Question-Forum/Same-email-used-unable-to-access-new-course/m-p/532036),
  [What is a trusted account in Canvas?](https://community.instructure.com/en/kb/articles/661408-what-is-a-trusted-account-in-canvas))

- **Docebo** and **TalentLMS** both use a "branch" model that is architecturally closer to FLS's
  Organisation-under-Site than Canvas's separate-institution model, so their profile-ownership
  problems are the most directly comparable. Docebo's community forum documents the practical
  consequence of *not* resolving profile ownership up front: duplicate accounts are routinely created
  because uniqueness is checked against username rather than a stable external identifier, "the
  original account is abandoned and the new account is treated as a brand new user and gets assigned
  training they may have already completed." Docebo's answer is a manual **merge** tool, and even that
  is incomplete — "the merge process does not deactivate the 'source' user, so you need to do that
  after," and "learning plans are not transferred to the final user during the merge." ([Docebo
  community: user creation issues](https://community.docebo.com/product-q-a-7/automation-app-user-creation-issues-new-profile-for-name-changes-and-overwrite-for-same-fullname-username-6581),
  [Docebo community: best practice for merging duplicate accounts](https://community.docebo.com/product-q-a-7/best-practice-for-merging-two-user-accounts-with-separate-learning-histories-9502))

- **TalentLMS**'s branch documentation states plainly that "each branch has its own users, admins, and
  reports, so privacy and compliance stay fully intact" — i.e. TalentLMS's stated design is to avoid
  the shared-profile problem altogether by making a branch user a *branch-scoped* record, with a
  separate `delete duplicate` workflow for accidental double-adds rather than a cross-branch identity
  layer. ([TalentLMS: branches for multi-purpose training](https://help.talentlms.com/hc/en-us/articles/10730422734236-How-to-use-branches-for-multi-purpose-training-in-TalentLMS))

- **Salesforce**, as a non-LMS but directly relevant analogy (person-to-multiple-org relationships is
  its core data model problem), shows the mature version of this pattern: a `Contact` can be linked to
  several `Account`s via an explicit **Account-Contact Relationship** object, precisely so that "who
  owns this contact" is not a single answer. Before this feature existed, Salesforce admins worked
  around the one-account-per-contact limitation with "deliberate duplication" — creating a second
  contact record on purpose — which is exactly the failure mode Docebo and Canvas fall into by
  accident. ([Salesforce Ben: relate a contact to multiple accounts](https://www.salesforceben.com/salesforce-account-contact-relationship-fields-relate-a-contact-to-multiple-accounts/))

**Takeaway:** products that never designed an explicit multi-org relationship object end up with
either silent merge-editing chaos (Moodle's shared fields, mitigated only by locking) or duplicate
accounts and destructive merges (Canvas, Docebo). Products that *did* design the relationship object
up front (Salesforce's Account-Contact Relationship) treat "who can edit what" as a first-class
question the object answers, not an emergent property of whoever got there first.

---

## 2. Visibility leakage between organisations

This is the sharpest and best-evidenced failure mode.

- **Canvas has an open, unresolved GitHub issue** for exactly this shape of bug: an admin in one
  sub-account who is *also* enrolled as a student in a course in a different sub-account sees calendar
  events from sections they are not enrolled in — "the user sees the calendar events of SectionA1 and
  A2" when they should only see their own section. The issue has been open with no resolution, and the
  documented workaround institutions actually use is "maintaining several user accounts for the same
  user" — i.e. giving up on one identity per person specifically to avoid the leak. This is a directly
  on-point precedent for FLS: **a role held on one Organisation, combined with a role held on
  another, produced cross-organisation visibility that nobody intended and nobody could turn off.**
  ([canvas-lms issue #2093](https://github.com/instructure/canvas-lms/issues/2093))

- **Docebo's own community forum shows the admin-side mirror image of the same problem**: an admin
  who *wants* the whole picture cannot get it through the ordinary UI. A support/reporting admin
  asked how to find "users assigned to multiple branches" without checking each branch manually, and
  the answer revealed two separate limitations: the export "only shows you one of the stores they are
  assigned to, not all of them," and Docebo encodes multiple branches as pipe-separated values inside
  a single export cell rather than one row per membership — the admin had assumed (reasonably) that a
  multi-branch user would appear as multiple rows. This is the concrete version of "I can see a user
  but not their courses [in other branches]" — the admin can see *that* the user exists but has to
  fight the tooling to see the full cross-branch picture, even though they are entitled to it. ([Docebo
  community: find users assigned to multiple branches](https://community.docebo.com/product-q-a-7/how-can-i-find-users-that-are-assigned-to-multiple-branches-7700))

- **Docebo restricting multi-branch membership entirely (from October 2019 onward) is the vendor's
  own answer to this tension** — rather than solve "who should see what across branches", newer
  Docebo platforms simply disallow a user being in more than one branch, and the *only* documented
  path to a person needing two portals is giving them a second account and a "power user" role that
  can impersonate the other identity. That is an admission that the visibility question was hard
  enough to make the product regress the feature rather than solve it. ([Docebo community: same
  username across domains](https://community.docebo.com/product-q-a-7/can-you-access-another-domain-with-the-same-username-4587))

- **Moodle Workplace's default answer is the FLS answer** — hide the other tenant's data by default,
  with sharing as an explicit administrator decision affecting "forums, participant lists, gradebooks
  and reports" individually rather than as an all-or-nothing toggle. This supports FLS's existing
  educator-detail-view filtering-by-organisation as the right default, provided the *decision to widen
  it* (a "site staff" or superuser role seeing across all organisations) is deliberate and explicit
  rather than a side-effect of some other permission.

**On the "admins actually want the cross-org view" tension named in the brief**: the Docebo
"find users in multiple branches" thread is direct evidence that this want is real and that vendors
under-serve it — the admin was not asking for a security bypass, they were doing legitimate license
and reporting work and had to fight pipe-delimited exports to do it. FLS should expect the same
request ("show me this person across every organisation they're in") to come from legitimate
platform-level staff, and should design *how that request is served* (a distinct, higher-privileged
view) rather than leaving it to accrete as an accidental consequence of holding two organisation
roles, which is exactly the Canvas #2093 failure.

---

## 3. The "invisible learner" failure mode

This is the one most directly analogous to what the `Learner` model changes about FLS's shape, because
FLS is moving from *purely derived* organisation-membership (a learner's organisation comes from their
registrations — the current, shipped model) toward an *explicit* membership row.

- **Moodle's cohort-sync feature is the closest existing precedent for the exact risk being taken
  on.** Cohort sync deliberately couples an explicit membership row (cohort membership) to a derived
  one (course enrolment): "cohort sync synchronises cohort membership with course enrolment... If a
  user is added or removed from the cohort, they are automatically enrolled or unenrolled
  respectively." Moodle's own documentation for the *contrasting* method (self-enrolment with a cohort
  restriction) makes the divergence explicit: "the self-enrolment cohort restriction merely restricts
  who can perform the self-enrolment initially... once enrolled they are the same as any other
  self-enrolled user — what cohort they are in no longer matters or controls their enrolment." The
  forum record is full of confusion between these two, and the sharpest edge is stated plainly:
  "the only way to unenroll [under cohort sync] is to remove a user from the cohort, but this will
  mean they are unenrolled from *all* courses synced to that cohort" — a single membership change with
  a blast radius the admin did not necessarily intend. ([Cohort sync — MoodleDocs](https://docs.moodle.org/33/en/Cohort_sync),
  [Moodle forum: Don't unenrol on cohort sync](https://moodle.org/mod/forum/discuss.php?d=383856),
  [Moodle forum: Unenrolling a single user enrolled via cohort sync](https://moodle.org/mod/forum/discuss.php?d=397946))

- **Docebo's single-department-at-a-time design (Absorb has the identical constraint)** is the
  vendors' shared answer to avoiding the "roster says X, enrolment says Y" divergence: rather than
  let two structures (membership, enrolment) potentially disagree, they collapse a learner's
  organisational home to one value. Absorb's help documentation states "a learner may only be
  associated with one department at a time" as a stated design constraint, and community feedback
  records at least one operator who found this a real limitation for their multi-client offering,
  needing to "adjust their offering and prices for clients" as a result. This is a single-anecdote data
  point, not a broad pattern, but it corroborates the same trade-off Docebo made independently.
  ([Absorb: Department Creation & Management](https://support.absorblms.com/hc/en-us/articles/5335232968723-Department-Creation-Management))

- The general IT-identity concept of an **"orphaned account"** — an active identity with no valid
  owning record — is well documented in identity-governance literature, though the sources found are
  general IAM rather than LMS-specific, so this is presented as a naming/framing tool rather than an
  LMS precedent: an orphaned-account report (accounts with no current department/owner) is the
  standard reconciliation tool these systems use to catch exactly the divergence Moodle's cohort sync
  produces. ([RoboMQ: orphaned accounts](https://www.robomq.io/blog/orphaned-accounts-identity-governance/))

**Takeaway for the "invisible learner" question specifically**: no product researched ships a
first-class "learner is enrolled but not on the roster" or "learner is on the roster but not enrolled"
report as a polished feature — the closest thing found is Docebo's crude pipe-delimited export and
Moodle's cohort-sync forum folklore about what happens when the two get out of step. **This is a gap
in the market, not a solved problem**, and it is exactly the gap the new `Learner` model creates by
introducing a second source of truth (`Learner` row) alongside the existing one
(`UserCourseRegistration`/`CohortMembership`). No vendor researched has a clean answer; FLS building
its own reconciliation view/report is not catching up to prior art, it is doing work nobody else has
done well.

---

## 4. Search and disambiguation

- **Docebo's default is branch-scoped search** in current deployments — since same-user-in-two-branches
  is now disallowed by default (see §1/§2), the "does search scope to the current org" question is
  moot for those installs: a learner can only be *found* in the one branch they belong to. Where
  multi-branch membership still exists (pre-October-2019 platforms), the export tooling shows only one
  membership per row by default, meaning ordinary admin search genuinely does hide the other
  memberships unless the admin knows to decode the pipe-delimited field. ([Docebo community: find
  users assigned to multiple branches](https://community.docebo.com/product-q-a-7/how-can-i-find-users-that-are-assigned-to-multiple-branches-7700))

- **The "invite existing user" / duplicate-account trap is the single most consistently reported sharp
  edge across every product researched.** Concrete accounts:
  - Canvas: reusing the same email across two institutions with a trust relationship produces a state
    where "trying to access a course at one institution brings up everything from the other
    institution," and the documented remedy is a one-way, admin-arbitrated **merge** with no undo.
    ([Instructure Community: merge accounts](https://community.canvaslms.com/t5/Student-Guide/How-do-I-merge-my-user-account-with-an-account-using-the-same/ta-p/416))
  - Docebo: uniqueness checked on username rather than a stable external ID silently produces a second,
    "abandoned" account that starts the learner's training history over, discovered only when someone
    notices duplicate progress. ([Docebo community: user creation issues](https://community.docebo.com/product-q-a-7/automation-app-user-creation-issues-new-profile-for-name-changes-and-overwrite-for-same-fullname-username-6581))
  - Moodle: the long-running "multiple users with same email address" forum thread shows admins split
    on whether to *bar* duplicate emails at all, with some resorting to fake dummy emails per account
    purely to satisfy uniqueness — trading away the notification mechanism to route around the
    identity model. ([Moodle forum: multiple users with same email address](https://moodle.org/mod/forum/discuss.php?d=7706))
  - Google Workspace / Microsoft Entra (non-LMS but the clearest documented "invite existing user"
    flow for B2B multi-tenant identity): when an email collision is detected, Entra "will add the
    email to the proxyAddress of the existing B2B user" for external users, or route local users to
    sign in with the account they already have — i.e. the mature pattern is *detect-and-attach*, not
    *silently create a duplicate*. This is the pattern to aim for rather than any of the LMS-specific
    behaviour above. ([Microsoft Learn: troubleshoot B2B issues](https://learn.microsoft.com/en-us/entra/external-id/troubleshoot))

- No product researched documents a clean "invite existing user to this organisation" UI pattern for
  the LMS case specifically — every LMS example above is either a prevention (Docebo now disallows
  multi-branch), a scoped-search dead end (Docebo pre-2019 exports), or a destructive fix-after-the-fact
  (Canvas merge, Docebo merge). The Entra/Workspace "detect-and-attach" pattern from adjacent B2B SaaS
  is the best model found, not an LMS one.

---

## 5. Privacy and compliance framing

Kept practical, as requested — this is a design-constraint flag, not a legal opinion.

- **Moodle Workplace's stated GDPR framing is data-protection-by-default**: "no personal data is
  shared between tenants" unless an admin explicitly opts in, which the docs tie directly to GDPR's
  "protection by default and by design" principle. This is the correct default for FLS's Organisation
  layer to inherit, and matches the shipped Organisation feature's existing filtering behaviour.
  ([Moodle Multi-tenancy docs](https://docs.moodle.org/502/en/Multi-tenancy))

- **"Delete this learner" is not one action when the learner studies with more than one organisation
  on the platform.** Two separate, well-documented constraints apply:
  1. **Legal retention can override deletion.** "A request for the erasure of data which is legally
     required, such as a record of compliance training, does not have to be granted" — a genuine
     GDPR exception, not a workaround. IACET (an accreditation body for training providers) documents
     the concrete version of this tension: its accreditation standard requires **seven years** of
     learner records, which can directly conflict with an erasure request, and providers are expected
     to resolve this by anonymising/restricting rather than deleting where retention is mandated.
     ([IACET: navigating GDPR right to be forgotten while retaining learner records](https://iacet.org/events/iacet-blog/blog-articles/navigating-the-gdpr-right-to-be-forgotten-while-retaining-learner-records-a-guide-for-iacet-accredited-providers/))
  2. **Multiple organisations may each have an independent, legitimate basis to keep their own
     records even if one organisation's relationship with the learner ends.** General SaaS GDPR
     guidance frames this as a controller/processor question: "if the data belongs to your customer's
     end users and you act as processor, the customer usually leads" a deletion request — implying a
     platform-level "delete this learner" action cannot unilaterally erase what a *different*
     organisation legitimately controls about the same person. ([Drata: GDPR for SaaS](https://drata.com/learn/gdpr/for-saas-compliance))

- **Practical consequence for FLS**: "delete this learner" cannot mean "delete the user account" (the
  user may still be a learner elsewhere on the Site, or hold a login the Site itself needs), and it
  probably cannot even cleanly mean "delete the `Learner` row" if that row is the only thing anchoring
  historical registrations, deadlines and progress to that organisation for audit/compliance purposes.
  This argues for **soft-delete or an explicit "removed from organisation" state on `Learner`**, not a
  hard delete, echoing the "No delete, no merge" caution the shipped Organisation feature already
  applied to `Organisation` itself for the identical reason (Decision 5, citing Docebo's post-toggle
  migration pain).

---

## 6. Terminology

- **"Learner" is a genuinely common and well-understood term in this space** — Docebo's own
  documentation uses "Learner" as the name for its default enrolled-user role ("all learners added to
  the LMS are assigned the role of learner... anyone enrolled in a course is assigned the learner role
  in systems like Docebo"), so an educator coming from Docebo, TalentLMS or similar products will not
  find "Learner" surprising. ([Docebo: LMS user roles for L&D managers](https://www.docebo.com/learning-network/blog/lms-user-roles/))

- **The specific confusion this brief flags — "user" meaning both the global account and the
  org-local record — is exactly what several vendors' own terminology collides on.** Absorb's help
  documentation uses "User Management" for the screen that manages department-scoped learner records,
  not a global account list, and Docebo's export/reporting language uses "User" for rows that are
  actually branch-scoped. Neither vendor's UI copy consistently distinguishes "the account" from "this
  organisation's record of the account" — which is precisely the ambiguity FLS is trying to resolve by
  giving the org-local record its own name (`Learner`) rather than overloading `User`.
  ([Absorb: User Management](https://support.absorblms.com/hc/en-us/articles/4407928382483-User-Management))

- **"Member"** is the term Moodle Workplace–adjacent and general SaaS products (Slack, Salesforce
  communities) tend to use for "this person, scoped to this organisation/workspace" — and it reads
  more naturally than "Learner" for the *general* concept of org-scoped membership, precisely because
  it carries no assumption about the person's role. But FLS has already scoped this cut to **learners
  only** (staff use the existing role mechanism), so "Learner" is more precise than "Member" would be
  for what the model actually represents in this cut — it is naming the thing correctly for what it
  is *now*, at some cost if the model is ever widened to cover other org-scoped relationships later,
  at which point "Member" would generalise better and "Learner" would need a role check bolted on.

- **Recommendation:** "Learner" reads clearly to an educator and matches established industry usage
  (Docebo). The one thing worth stating explicitly in the spec, because no vendor researched gets this
  right in their own copy: **UI text and docs should never say "user" where "learner" (the org-scoped
  record) is meant**, and should reserve "user" for the account-level concept FLS already has
  (`accounts.User`). This is cheap to get right at introduction and expensive to fix once screens have
  shipped with the ambiguous word, based on the Absorb/Docebo evidence above.

---

## What this suggests for FLS

Each item below is tied to a specific failure mode found above, not a generic best practice.

1. **The multi-org reality already exists in FLS before this cut ships — the `Learner` model is
   formalising it, not introducing it.** `UserCourseRegistration` already carries an `organisation`
   FK and a learner can already register through two organisations (idea.md, "Uniqueness changes").
   This matters because it changes what the Docebo/Absorb precedent (§1, §3: both vendors ended up
   *restricting* users to one organisation) actually implies: their walk-back was a reaction to letting
   one *mutable, shared* profile be edited by several branch admins with no ownership model — not to
   the mere fact of multi-org membership. FLS's Site/Organisation split already avoids their worst
   trigger (Organisation is explicitly not a security or profile-ownership boundary; profile fields
   live on `accounts.User`, one Site-wide record, not duplicated per organisation). The `Learner`
   model doesn't need to re-litigate Decision 5's "no delete, no merge" caution against multi-org
   membership itself — but see point 5 below for the part of that caution that *does* still apply.

2. **Treat "learner enrolled but not on the roster" and "learner on the roster but not enrolled" as a
   named, tested state, not an edge case discovered later.** No product researched (§3) has a clean
   answer to this — Moodle's cohort-sync forum folklore and Docebo's pipe-delimited exports are the
   closest prior art, and both are widely reported as confusing. Concretely: decide up front what an
   educator sees for a `Learner` row with no active registration in that organisation (show it,
   greyed out, with a reason?), and what happens to a registration created without a corresponding
   `Learner` row (auto-create one? block the registration? surface a warning?). Whichever is chosen,
   put a reconciliation view or at least a management-command report in scope — this is exactly the
   gap every vendor above leaves to manual export-and-diff.

3. **Do not let "an educator holds a role on two organisations" become an accidental cross-org leak.**
   Canvas's open, unfixed issue (§2, #2093) is the direct precedent: a role on Org A plus enrolment/
   membership in Org B combined into visibility neither role alone would have granted. FLS's
   organisation-scoped querysets already filter by the *current* organisation in the URL (idea.md,
   "Scoping and access"), which avoids Canvas's specific bug — but the `Learner` model adds a new
   query surface (the roster). Make sure roster queries filter on `Learner.organisation` the same
   strict way cohort/registration queries already filter on `organisation`, with the same test
   guarantee pattern idea.md already commits to (two organisations, a role on one only, assert the
   other returns nothing).

4. **Design the legitimate cross-org admin view on purpose, rather than letting it emerge.** The
   Docebo "find users in multiple branches" thread (§2) shows this want is real, not hypothetical —
   and un-designed cross-org visibility is how Canvas's leak happened. If FLS ever needs a
   platform/site-level "show me this learner across every organisation they belong to" view, it
   should be an explicit, separately-authorised capability (e.g. a site-staff permission), not a
   side-effect of holding two organisation roles simultaneously.

5. **"Delete this learner" needs a defined, non-destructive meaning before the roster ships a delete
   button.** §5's finding — that a different organisation may have an independent, legitimate reason
   to retain its own record of the same person, and that legal retention can override an erasure
   request outright — means a hard delete on `Learner` is very likely wrong. This is the same shape of
   caution the shipped Organisation feature already applied to `Organisation` itself (Decision 5: no
   delete, no merge, citing Docebo's cleanup pain). Recommend the same discipline here: no hard delete
   on `Learner` in this cut, or if removal is needed, a soft "removed from organisation" state that
   preserves what historical registrations/progress point back to.

6. **"Learner" is the right name and matches industry usage (Docebo) — but audit every screen for the
   word "user" leaking through where "learner" is meant.** §6's evidence is that this is precisely
   where Absorb and Docebo's own UI copy gets sloppy. Cheap to enforce now via a spec note and a
   copy-review pass; expensive later once "user" has shipped in a dozen templates.

7. **Flag against the brief's "student-facing interface is out of scope" holding as cleanly as
   hoped, specifically around identity/search, not display.** The idea.md non-goals correctly scope
   *out* organisation branding and theming from the student side for this cut. But §4's evidence (the
   duplicate-account trap is the single most consistently reported sharp edge across every vendor) is
   about *account creation and lookup*, which is a shared surface: however a new `Learner` row gets
   created (an educator adding someone to a roster, or a self-registration flow later), the same
   "does this email already have an account on this Site?" question has to be answered once, correctly,
   for every entry point — and that logic does not naturally stay confined to the educator interface.
   Worth an explicit line in the plan phase saying where that check lives, even though the
   student-facing *UI* stays out of scope.

---

status: ok
