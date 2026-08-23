# Research: how other LMSs model "a user studies through several organisations"

Scope: only the **learner** side of the user↔org relationship (staff/educator attachment stays on
`ObjectRoleAssignment`, per the product owner's decision — not re-examined here). Student-facing UI
is out of scope for this cut; noted only where it constrains the data model.

---

## 1. Canvas LMS — `UserAccountAssociation`

Canvas's `Account` tree (root account → sub-accounts) is the closest external analogue to FLS's
Site → Organisation shape, and Canvas's answer is directly on-point: **yes, there is an explicit
membership row, and it is auto-maintained, not hand-curated.**

- `User` is the global identity. `Enrollment` ties a user to a *course* with a role. `Pseudonym` is
  a login credential, scoped to an account (a user can hold several pseudonyms, one per account they
  have separate credentials in).
- `UserAccountAssociation` is a **separate table** from `Enrollment`. It records `(user, account,
  depth)` and is maintained automatically by a callback (`update_account_associations_if_necessary`)
  triggered whenever a user enrols in a course or is otherwise added to an account. When that
  happens, Canvas writes an association row not just for the account the course lives in, but for
  **every ancestor account up the tree**, with `depth` recording how far up (`0` = the root account
  itself). This is exactly the "person is in this org" vs "person is enrolled in a course of this
  org" distinction the FLS idea is reaching for: `Enrollment` is the enrolment-level fact,
  `UserAccountAssociation` is the derived, denormalised **index** that answers "which accounts does
  this user touch at all", kept in sync by the system rather than an admin.
- **Many accounts per user** — a user can accumulate `UserAccountAssociation` rows for as many
  accounts as they have enrolments (direct or via ancestor accounts). Canvas does not restrict this.
  Canvas's own data-service event stream even emits a
  `user_account_association_created` event per row, confirming it is treated as a first-class,
  auditable fact rather than an incidental cache.
- **Login**: a `Pseudonym` is scoped to an account. A user with enrolments spanning two *separate
  root accounts* (e.g. two different institutions' Canvas tenants) genuinely needs two logins/two
  pseudonyms — this is the boundary Canvas treats as a security/identity edge, analogous to FLS's
  *Site*. Within **one** root account's sub-account hierarchy, however, the picture is different:
  Canvas's own account/sub-account docs and the `UserAccountAssociation` depth-propagation behaviour
  both point at sub-accounts sharing the root account's authentication configuration, so a learner
  moving between sub-accounts of the same institution does not need new credentials — this
  particular nuance is less explicitly spelled out in Instructure's docs than the association-table
  behaviour is, so treat it as corroborated-but-not-verbatim-quoted.
- **Identity shape**: the `User` is first-class and global; per-account facts (associations,
  pseudonyms, enrolments) hang off it. There is no per-account "user record" — `UserAccountAssociation`
  is explicitly a thin join/index, not a re-modelled person.

Sources:
[User Model and Authentication (DeepWiki, derived from canvas-lms source)](https://deepwiki.com/instructure/canvas-lms/3.2-user-model-and-authentication),
[Accounts API](https://mitt.uib.no/doc/api/accounts.html),
[Users API](https://www.canvas.instructure.com/doc/api/users.html),
[User data-service event doc — `user_account_association_created`](https://documentation.instructure.com/doc/api/file.data_service_canvas_user.html),
[Logins API](https://documentation.instructure.com/doc/api/logins.html).

---

## 2. Moodle Workplace — tenants

Moodle Workplace's multi-tenancy is the tightest possible answer to "can one person be in several
orgs": **no, on purpose.**

- "Each user belongs to a single tenant." Tenant separation is implemented as user/category-scoped
  isolation (a tenant maps onto a course-category subtree and a filtered user pool), not as a
  membership table designed for multiplicity.
- The stated reasoning is **privacy/isolation, not scoping convenience**: "by default, no personal
  data is shared between tenants, and each remains unaware of the others," explicitly framed as
  supporting GDPR data-protection-by-design. This is Moodle treating tenant as much closer to FLS's
  *Site* than to FLS's *Organisation* — which is exactly the parallel the shipped Organisation idea
  doc already draws ("Moodle draws exactly this line for its own tenants").
  Cross-tenant sharing exists but is an explicit admin-enabled exception (shared course categories,
  group-mode separation inside a shared course), not a native "belongs to many tenants" mode.
- The specific technical shape (is it a `tenantid` column on `mdl_user`, or a separate membership
  table?) is not spelled out in Moodle's own docs at the altitude fetched here; the *product*
  behaviour (single tenant, hard isolation, opt-in narrow sharing) is unambiguous and is the useful
  signal for FLS regardless of the exact column shape.

Sources:
[Multi-tenancy](https://docs.moodle.org/502/en/Multi-tenancy),
[Multi-tenancy Technical](https://docs.moodle.org/502/en/Multi-tenancy_Technical),
[moodleworkplace/multitenancy tool_tenant README](https://github.com/moodleworkplace/multitenancy/blob/MOODLE_38_STABLE/admin/tool/tenant/README.md).

---

## 3. Open edX — `Organization` is not a learner concept at all

This is the sharpest contrast in the set. Open edX's `organizations` Django app (`edx-organizations`)
models `Organization` purely as **course metadata** — "the entities responsible for creating and
publishing Courses" (title, logo, short name used in course keys) — linked to courses via
`OrganizationCourse`. There is **no `OrganizationUser`, no learner-to-organization membership model,
anywhere in core Open edX.** A learner's relationship to an "org" is entirely implicit and derived:
they are enrolled in a *course*, and that course happens to carry an org string in its course key
(`org/course/run`). Nothing tracks "this learner belongs to this org" as a fact independent of
specific course enrolments.

This matters for FLS as the **null hypothesis**: it is entirely possible to ship a credible LMS
without ever modelling learner-org membership explicitly, by treating "org" purely as a label
inherited from what's being taken — which is precisely the position the Organisation idea doc's
non-goal ("no organisation membership object... comes from their registrations") already occupied,
and precisely the position the new idea is proposing to leave.

Sources: [openedx/edx-organizations](https://github.com/openedx/edx-organizations),
[Understanding Open edX courseware organization (Appsembler KB)](https://help.appsembler.com/article/172-understanding-open-edx-courseware-organization).

---

## 4. TalentLMS branches, Docebo branches, Absorb departments — the "one, with an escape hatch" family

These three cluster together and are the most directly cautionary for FLS, because two of them show
the *product* actively narrowing from many-to-one after shipping the permissive version.

**Docebo** — explicit and well-documented walk-back:
- "A user can only exist in a single Branch. Any newly created platforms (after 10/16/2019) only
  allow for a user to be assigned to 1 branch at a time." Multi-branch membership still exists as a
  **legacy toggle** for pre-2019 platforms, activated by Docebo support rather than self-service —
  i.e. Docebo treats it as a grandfathered liability, not a supported design.
- Docebo's own community explicitly discourages using it even where available: "Try to avoid placing
  a user in multiple branches, as it often can make user management and user experience more complex
  (i.e. it may trigger multiple notifications for them)" — and recommends **Groups** (an orthogonal,
  unlimited-membership construct) for the "needs to see stuff from elsewhere" case instead of
  multi-branch membership.
- Cleanup pain is real and documented: admins on legacy platforms report auditing multi-branch users
  via CSV export (branches shown pipe-delimited in one export column) and consolidating them back to
  a single branch by re-importing corrected data. This is the exact "manual CSV cleanup" case the
  Organisation idea doc's Decision 5 already cites as the cautionary precedent for not building
  delete/merge machinery.

**Absorb LMS** — same shape, no escape-hatch-with-history: "Each User can only be allocated to one
Department... A User may only ever belong to one Department," full stop. Multiplicity is pushed
entirely onto a separate, unlimited-membership **Groups** construct, exactly mirroring Docebo's
recommended pattern. This is a strong second data point that "one mandatory org-like FK, arbitrary
group tags on top" is a stable, repeatedly-chosen shape in this product category — which is, again,
close to what FLS already has (mandatory `organisation` FK on `Cohort`/`UserCourseRegistration`).

**TalentLMS** — branches are documented as "distinct sub-portal[s] with... own URL, branding,
catalog, and admins," i.e. closer to a *Site* than an *Organisation* in FLS terms (full white-label
per branch, matching the LearnWorlds "School" pattern below). Official docs describe *moving* users
between branches (`usertobranches;branch` import, "move users between branches without losing
critical data") rather than describing simultaneous multi-branch membership as a normal supported
mode; TalentLMS's public docs did not yield a clear statement either way on whether one account can
hold live membership in two branches concurrently, so this should be treated as **unconfirmed** at
this altitude rather than asserted.

Sources:
[Organizing users with branches — Docebo](https://help.docebo.com/hc/en-us/articles/360020084140-Organizing-users-with-branches) (title only, page fetch blocked, corroborated via search index),
[Docebo community — finding users in multiple branches](https://community.docebo.com/product-q-a-7/how-can-i-find-users-that-are-assigned-to-multiple-branches-7700),
[Docebo community — handling users in multiple branches](https://community.docebo.com/product-q-a-7/how-do-you-handle-users-in-multiple-branches-13074),
[Absorb — Department Creation & Management](https://support.absorblms.com/hc/en-us/articles/5335232968723-Department-Creation-Management),
[Absorb — Group Creation & Management](https://support.absorblms.com/hc/en-us/articles/4418563347987-Group-Creation-Management),
[TalentLMS — Branches feature page](https://www.talentlms.com/features/branches),
[TalentLMS — using branches for multi-purpose training](https://help.talentlms.com/hc/en-us/articles/10730422734236-How-to-use-branches-for-multi-purpose-training-in-TalentLMS).

---

## 5. LearnWorlds "Schools" — confirms this maps to *Site*, not *Organisation*

LearnWorlds' "Multiple Schools Dashboard" lets one account-holder own several **separate LearnWorlds
installations** (each its own domain, branding, learner base), navigable via a single centralised
login for the *owner/super-admin*. This is not a within-one-instance learner-org membership model at
all — it is several independent white-labelled products under one billing/owner identity. This
corroborates the naming-note already in the shipped Organisation idea doc: LearnWorlds' "School" is
architecturally FLS's *Site*, not FLS's *Organisation*, and is not evidence either way about
multi-org learner modelling within one instance.

Source: [LearnWorlds — Multiple LearnWorlds Schools Dashboard Overview](https://support.learnworlds.com/support/solutions/articles/12000086985-multiple-learnworlds-schools-dashboard-overview).

---

## 6. D2L Brightspace Org Units — enrolment-derived, and normal to have many

Brightspace's `OrgUnit` hierarchy (department, semester, course offering, etc., all typed and
nestable) is closer in spirit to a pure enrolment model than to Canvas's association-table model:
membership in an org unit **is** an enrolment record (`POST .../enrollments/...`, with a role), and
the API to list "all org units this user touches" (`GET
/d2l/api/lp/(version)/enrollments/users/(userId)/orgUnits/`) reads directly off enrolments — there is
no separate denormalised association table analogous to Canvas's. A learner routinely holds many
concurrent org-unit enrolments (their department, several course offerings, a semester grouping,
etc.) and this is treated as completely unremarkable — no "pick one" constraint anywhere in the docs
reviewed. This is a useful counterweight to the Docebo/Absorb "one, please" cluster: it shows that
**enrolment-derived, no-cap multiplicity is also a mainstream, working design**, not just a
theoretical option — it's essentially the *status quo* FLS shipped in the Organisation cut, just with
Brightspace's hierarchy being deeper (typed org-unit tree vs FLS's flat Organisation layer).

Sources: [Brightspace — About Org administration](https://community.d2l.com/brightspace/kb/articles/17019-about-org-administration),
[Brightspace — Enroll users into org units](https://community.d2l.com/brightspace/kb/articles/4860-enroll-users-into-org-units-as-specified-roles),
[Valence API — Enrollments](https://docs.valence.desire2learn.com/res/enroll.html).

---

## 7. Cornerstone OnDemand — typed, explicit, HR-fed membership rows

Cornerstone's Organizational Units (Division, Position, Cost Center, Location, Grade, etc.) are the
clearest example in this survey of **membership as a genuinely first-class, explicit fact,
independent of any enrolment**:

- A user can simultaneously hold a Division OU, a Location OU, and a Position OU — "a user can be
  associated to the Finance Division, the Qatar Location, and the Director Position" — i.e. multiple
  memberships, but of **different types**, each type behaving closer to a single slot (one Division
  at a time, one Location at a time) than an unlimited multi-select. This is a materially different
  shape from Canvas/D2L's "as many as you have enrolments" — Cornerstone's multiplicity comes from
  *having several OU type axes*, not from allowing many values on one axis.
  - Note: the public API-design guide for the Employee/OU endpoints did not expose the underlying
    field-level shape (effective dates, primary-OU flag) at the depth fetched here; the multiplicity
    claim above is corroborated by Cornerstone's own admin-training material, not by schema
    inspection.
- OU membership persists independently of training: it is closer to an HR fact ("this person is in
  this Division") than a learning fact, and training *assignment profiles* are computed **from** OU
  membership (assign this course to everyone in Division X), not the other way around. This is the
  clean version of the "person is in this org" / "person is enrolled in a course of this org"
  distinction — Cornerstone treats them as two layers with an explicit dependency direction, and
  membership is the upstream one.

Sources: [Understand Organizational Units (Wisconsin DPM job aid)](https://dpm.wi.gov/Documents/JobAids/Cornerstone/Understand_Organizational_Units.pdf),
[Organizational Units Administration — Cornerstone Help](https://help.csod.com/help/csod_0/Content/System_Configuration/Organizational_Units/Organizational_Units_Administration_Overview.htm),
[Employee/OU API guide — csod.dev](https://csod.dev/guides/core-hr/employee-ou/).

---

## 8. SAP SuccessFactors Learning — membership sourced from HR, not from the LMS

SuccessFactors makes the dependency direction from §7 even more explicit: a learner's org
unit/job/position is an **HR-system fact**, imported into the LMS, and "Assignment Profiles" compute
what training is owed **from** that org/job/position data. The LMS never originates org membership —
it consumes it. This is the extreme end of "org membership is upstream of and independent from
enrolment," included here as the far pole from Open edX's "org membership doesn't exist, only course
labels do."

Sources: [The Building Blocks of a Learning Management System — SAP Help Portal](https://help.sap.com/docs/successfactors-learning/managing-sap-successfactors-learning-for-administrators/building-blocks-of-learning-management-system),
[SAP SuccessFactors Learning Assignment Profiles — SAP Help Portal](https://help.sap.com/docs/successfactors-learning/managing-sap-successfactors-learning-for-administrators/sap-successfactors-learning-assignment-profiles),
[SuccessFactors LMS: Power in Assignment Profiles — SAP Community](https://blogs.sap.com/2013/12/05/successfactors-lms-power-in-assignment-profiles/).

---

## Cross-cutting pattern

| Product | Explicit row? | Auto- or hand-maintained? | One org or many? | "In org" ≠ "enrolled in org's course"? | Same login across orgs? |
|---|---|---|---|---|---|
| Canvas | Yes (`UserAccountAssociation`) | Auto (callback on enrol/add) | Many | Yes — the whole point of the table | Yes, within one root account's tree; separate root accounts need separate pseudonyms |
| Moodle Workplace | Implicit (tenant scoping) | N/A (isolation, not index) | **One** (by design, GDPR-motivated) | N/A — tenant is closer to FLS's Site | N/A — different tenants, isolated |
| Open edX | **None** | N/A | N/A | No concept of learner-org membership at all | N/A |
| Docebo | Yes (branch FK) | Hand-set (single-branch is the norm; multi is a legacy toggle) | **One**, with a discouraged legacy escape hatch | No — branch membership *is* the "in org" fact, separate from enrolment already | Same account, branches are within one platform |
| Absorb | Yes (Department FK) | Hand-set | **One** (hard constraint); Groups handle multiplicity | No — same shape as Docebo | Same account |
| TalentLMS | Yes (branch) | Hand-set / import | Unclear from docs; branches read as separate sub-portals | Unclear | Branches are closer to separate portals |
| LearnWorlds | N/A — "Schools" are separate installations | N/A | N/A | N/A | Centralised owner login across installations, not a learner concept |
| D2L Brightspace | Enrolment record IS the membership | Auto, via enrol API | **Many**, unremarkable | No — deliberately conflated; enrolment is membership | Same account, one platform |
| Cornerstone | Yes, per OU type | Hand-set / HR-fed | Many **types**, ~one value per type | Yes — OU membership drives assignment, not the reverse | Same account |
| SuccessFactors | Yes, HR-sourced | Fed from HR system, not the LMS | Depends on HR org model | Yes — membership is upstream of learning entirely | Same account |

---

## What this suggests for FLS

Two structural facts already constrain the design before considering any external product:

1. **Site is FLS's only identity/security boundary.** None of the "separate login per org" products
   (Canvas across root accounts, TalentLMS/LearnWorlds branches-as-sub-portals) are the right analogy
   — the right analogues are the ones that keep one account, one login, working across multiple orgs
   inside one platform: Canvas *within* a root account, D2L Brightspace, Cornerstone.
2. **Staff/org-role attachment is already solved** via `ObjectRoleAssignment` and is explicitly out of
   scope here — so whatever shape is chosen only has to answer "is this user a *learner* of this
   org," not "does this user have *any* relationship with this org."

Four concrete shapes, from thinnest to most first-class:

**A. Thin auto-maintained index (Canvas `UserAccountAssociation` shape).**
A `LearnerOrganisationAssociation(user, organisation)` row, unique together, with no status field of
its own — created and deleted purely as a side effect of `UserCourseRegistration`/`CohortMembership`
rows appearing or disappearing under that organisation (mirroring Canvas's
`update_account_associations_if_necessary` callback, and D2L's "membership is just enrolment,
indexed"). This is the most conservative option: it doesn't reverse the existing non-goal
philosophically (organisation still *comes from* registrations), it just gives the educator interface
a fast, explicit thing to query and display instead of re-deriving "distinct users across two related
tables" on every list view.
*Trade-off:* it does not give the product owner's stated want — "a system that is more explicit" and
"we may need to automatically create learner instances" reads as wanting something with its own
identity and lifecycle, not just a cache. If the last registration under an org is deleted, this row
silently vanishes too — there's no way to say "this person is still considered one of our learners,
even between registrations."

**B. First-class `Learner` record with an independent lifecycle (Cornerstone-OU-membership shape).**
`Learner(user, organisation, status={active, inactive, ...}, created_at, source)` — auto-provisioned
the first time a registration or cohort membership appears under that organisation (same trigger
points as A), but **persisting independently** of any single registration once created, with its own
status. This directly answers "explicit... an educator should only see learners explicitly associated
with an org" (Decision-shaped requirement in the idea): the educator interface filters on `Learner`,
not on a join through registrations. It also gives a home for the "automatically create learner
instances under different circumstances" line — e.g. also provisioning on cohort assignment before
any course registration exists, matching how Cornerstone's OU membership can precede any specific
training assignment.
*Trade-off:* now there are two sources of truth (registrations and `Learner` rows) that must be kept
from drifting apart, and a lifecycle question that doesn't currently exist has to be answered:
what removes a `Learner` row (or flips it inactive)? Nothing in the current org model needs an answer
to "when does someone stop being a learner of an org" — this option manufactures that question.

**C. Admin-curated roster, registration constrained by it (SuccessFactors/Cornerstone-HR-feed shape).**
Org staff explicitly add/remove learners from an org's roster (a real admin action, not a system
side-effect); `UserCourseRegistration.organisation` and `Cohort` membership under that org are only
valid for users already on the roster. This is the most literal reading of "more explicit" and the
biggest reversal of the current model — it inverts the dependency direction (membership → eligible to
register, rather than registration → implies membership), which is exactly the SuccessFactors/
Cornerstone pattern of membership being upstream of and independent from enrolment.
*Trade-off:* this is a real product change, not just a schema addition — it needs new admin UI, a
validation rule at registration time ("can't register a non-member"), and a decision about
self-service signup flows (does a learner signing up for a course under an org auto-join the roster,
in which case this collapses back toward option B/A; or does it hard-block, in which case it's a
genuine new gate that doesn't exist today). Given Decision 5's "loosening later is easy, tightening
later is not" logic already used to justify no-delete/no-merge, and Docebo's cautionary tale about
walking back permissive multi-branch membership, this is the option most likely to generate exactly
that kind of later-regretted rigidity if the roster becomes a hard gate rather than an index.

**D. Hybrid — auto-provisioned by default, but a real row with status (B), with org staff able to
also create rows directly ahead of any registration.**
Same shape as B, but explicit about there being **two creation paths**: the system auto-provisions on
first registration/cohort-membership (the common case, needs no admin action, matches the existing
"comes from registrations" spirit), and org staff can *additionally* create a `Learner` row directly
for someone not yet registered for anything (covering onboarding-before-enrolment cases the idea
mentions). This keeps the system-derived default from A/B while adding C's explicit-admin-action
capability only where actually needed, rather than making it the universal gate.
*Trade-off:* two creation paths means two things to test and reason about, and the same "what removes
a `Learner` row" lifecycle question as B still needs an answer — this doesn't dodge that, it just adds
optionality on the creation side.

**Framing note for whichever option is chosen:** every product in this survey that treats "in-org"
and "enrolled-in-org's-course" as genuinely separate facts (Canvas, Cornerstone, SuccessFactors) does
so because something in their product needs a learner to be "in" an org *before or independent of* any
specific course — pre-provisioning, HR-driven assignment, or account-hierarchy permission checks. FLS
should be explicit about which of those reasons is actually driving this idea (the idea doc gestures
at "auto-create... under different circumstances" without naming the circumstance), because the answer
determines whether A (pure index, no new "membership before enrolment" capability) is sufficient, or
whether B/C/D's independent lifecycle is actually load-bearing for a concrete upcoming need.

status: ok
