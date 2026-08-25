# Research: how comparable systems key progress when one person crosses organisations/tenants

## Scope and method

Web research only (no codebase changes). For each system: does progress attach to the *person*, or
to the *person's association with an org/tenant/department*? Findings are attributed to each
product's own vocabulary; FLS nouns (`Site`, `Organisation`, `Learner`, `LearnerCourseRegistration`,
`Cohort`, `CohortMembership`, `Course`, `CourseProgress`, `TopicProgress`, `FormProgress`) are used
only in the "What this means for FLS" section, never as a stand-in for another product's concept.

Every claim below is either sourced (URL given) or explicitly flagged as unverified.

---

## System-by-system findings

### Docebo — "domains" / Extended Enterprise, "branches"

Docebo's Extended Enterprise feature lets one platform serve several client-facing storefronts
("domains"), each mapped to a "branch" in Docebo's org tree. Docebo's own community confirms that,
in current versions, **a user cannot belong to more than one branch** — which is precisely the
"one person, two client organisations" case FLS now treats as a blessed steady state. Docebo's
answer instead is architectural exclusion: don't let it happen. Where admins actually need one
person to appear in two domains, the community-documented workaround is to give that person a
**second username/secondary email**, i.e. a second account — not a second progress-bearing
association on the same account.
[Community: "Can you access another domain with the same username?"](https://community.docebo.com/product-q-a-7/can-you-access-another-domain-with-the-same-username-4587)
[Community: "Extended Enterprise: Keeping Users in their Domain"](https://community.docebo.com/product-q-a-7/extended-enterprise-keeping-users-in-their-domain-10045)
[Help: "Managing the Extended enterprise app"](https://help.docebo.com/hc/en-us/articles/360020124899-Managing-the-Extended-enterprise-app)

Where a user *is* attached to a single branch, catalog visibility and enrolments "follow" the user,
i.e. progress is a property of the user, not separately keyed per branch — because Docebo prevents
the multi-branch case that would force the question. I could not verify from public sources what
Docebo's underlying enrolment/completion table's unique key literally is (Docebo does not publish
its schema); this is an inference from documented behaviour, not a confirmed schema fact.

For reporting, Docebo counts **enrolments** (user × course pairs), not branch-scoped progress rows:
"a user that is enrolled in five courses will be counted five times in reports." Branch-level
reports (the "Branch Dashboard", "Groups/Branches – Courses" report) are filters/rollups over that
same enrolment data, not a separate per-branch progress record, and the community explicitly
recommends building separate branch vs. group reports to avoid confusing membership overlaps.
[Help: "Organizing users with branches"](https://help.docebo.com/hc/en-us/articles/360020084140-Organizing-users-with-branches)
[Community: reporting completions per branch](https://community.docebo.com/let-s-talk-shop-42/getting-details-in-reporting-x-completions-of-a-course-per-branch-12336)

### Totara Learn / Totara TXP — "tenants", and the older "organisation"/"position" hierarchy

Totara's **tenant** is the multi-tenancy primitive (isolation), added as a context level between
"system" and "user" in the Totara context tree. Totara's own docs state that when a user is moved
from one tenant to another, **"they would retain access to their completion records"** — i.e.
completion/progress is a property of the person, carried across tenant membership changes, not
reset or forked per tenant.
[Totara Help: "Multitenancy in Totara Learn"](https://totara.help/17/docs/multitenancy-in-totara-learn)
[Totara dev wiki: Multitenancy](https://totara.atlassian.net/wiki/display/DEV/Multitenancy)

Totara's much older **organisation/position hierarchy** (distinct from "tenant") is explicitly a
reporting/assignment structure, not an isolation or progress-scoping boundary — it drives
dynamic audience rules and manager reporting lines, layered on top of person-scoped completion
records, not a second key on them.
[Totara: "How to support multiple tenants with Totara Learn"](https://totara.com/us/articles/how-to-support-multiple-tenants-with-totara-learn/)

I could not verify Totara's actual `course_completions`-equivalent table schema for tenant
awareness from public docs (Totara is a Moodle fork; see Moodle findings below, which likely carry
over since Totara did not redesign core completion around tenants — this is an inference, flagged
as such).

### Moodle Workplace — "tenants" and "departments"; plain Moodle "cohorts"

Moodle Workplace tenants isolate **users, hierarchies, roles, themes, reports, and learning
entities** from each other — but Moodle's own documentation explicitly says: **"Multi-tenancy does
not apply to course content"** — if a user from tenant A is enrolled in a course also used by
tenant B, that user will see tenant-B participants, forum posts, and the shared gradebook/reports
for that course. Course-level progress is therefore not tenant-scoped at all; it lives at the
course level, shared by whoever is enrolled, regardless of tenant.
[MoodleDocs: "Multi-tenancy"](https://docs.moodle.org/502/en/Multi-tenancy)
[Moodle: "Sharing content or courses using Moodle Workplace"](https://moodle.com/news/sharing-content-or-courses-with-different-teams-using-moodle-workplace/)

Underneath both plain Moodle and Workplace, the actual **`course_completions`** table (confirmed
schema) has a unique composite index **`(userid, course)`** — no organisation, cohort, or tenant
column at all. Plain Moodle **cohorts** are purely an enrolment-sync convenience (add a cohort,
its members get enrolled) with zero effect on the completion key; a user in two cohorts that both
lead to the same course still has exactly one `course_completions` row.
[Zoola schema: `course_completions` table](https://moodleschema.zoola.io/tables/course_completions.html)
[MoodleDocs: "Course completion"](https://docs.moodle.org/dev/Course_completion)

This is the closest direct structural analogue to FLS's current defect: Moodle's `course_completions`
is `unique(userid, course)`, exactly like FLS's `CourseProgress.unique_together = ["user", "course"]`
today — a system that, like FLS pre-fix, has no way to represent "this person's progress via
organisation A" separately from "via organisation B".

### Canvas — "sub-accounts" and "cross-listing"; `Enrollment` vs. `Submission`

Canvas's hierarchy unit is the **sub-account** (Canvas's rough equivalent of a department/division),
and its mechanism for combining class sections from different courses is **cross-listing** a
*section* into a different course. Canvas's own support docs are explicit that **"coursework is
retained with the course, not with the section enrollments"** — and warn that cross-listing *after*
students have already submitted work will cause the moved section's enrollments to **lose their
associated assignment submissions and grades**. This confirms progress/`Submission` data is keyed to
the (user, course) combination reachable via an `Enrollment`, and re-scoping the `Enrollment`'s
course after the fact silently detaches the `Submission` history rather than reconciling it.
[Rutgers: "Merging Course Sites using Cross-Listing"](https://canvas.rutgers.edu/documentation/support/crosslist/)
[FSU: "How do I cross-list a section in my course?"](https://support.canvas.fsu.edu/kb/article/924-how-do-i-crosslist-a-section-in-my-course/)

Cross-listing itself is also bounded: a section can only move to a course "in the same root
account (institution)" — Canvas does not attempt to let one Submission history span two
institutions, only two sub-accounts of the same one.
[Canvas API docs: Sections](https://canvas.instructure.com/doc/api/sections.html)
[Canvas API docs: Enrollments](https://www.canvas.instructure.com/doc/api/enrollments.html)

### Cornerstone OnDemand — "Organizational Units" (OUs), "Transcript"

Cornerstone's **Transcript** is the per-person learning-record object; **OUs** (Division, Position,
Group, Cost Center, Location, etc.) are a reporting/assignment hierarchy layered over users, not a
second key on the transcript. Cornerstone's own developer docs note a real limitation buyers hit:
OAuth API scopes can restrict *which fields* are visible, but **there is no built-in facility to
restrict Transcript/User API access to a specific division or region** — that kind of "only show me
this client's data" filtering "must be managed by the client" themselves, confirming the transcript
record has no native OU/tenant partition to filter on.
[Cornerstone API docs: Transcript](https://csod.dev/guides/learning/transcript/)
[Cornerstone: Organizational Units (OU) Quick Help](https://cornerstoneondemand.my.site.com/s/articles/Organizational-Units-OU-Quick-Help-Knowledge-Articles?language=en_US)

I could not verify from public sources what happens to a Cornerstone Transcript record if the same
person is represented in two different OUs and enrolled in the same course through each — this
looks structurally analogous to Docebo's branch restriction (a user's "home OU" is close to
1:1), but I found no page confirming or denying multiple concurrent transcript rows per course.
Flagged as unverified.

### Absorb LMS — "departments"

Absorb's own help center states plainly: **"Each user can only be allocated to one department...
a user may only be associated with one department at a time."** This sidesteps the multi-org
question entirely by construction, the same way Docebo's one-branch-per-user rule does. Absorb's
recommended escape hatch for anyone needing overlapping membership is **groups** (many-to-many),
which are explicitly documented as a *reporting and permissions* layer, not a re-scoping of the
department-based enrolment/progress model.
[Absorb: "Departments: Overview"](https://support.absorblms.com/hc/en-us/articles/29878102068371-Departments-Overview)
[Absorb: "Department & Group Structure Best Practices"](https://support.absorblms.com/hc/en-us/articles/43617074500627-Department-Group-Structure-Best-Practices)
[Absorb: "Department Progress Report"](https://support.absorblms.com/hc/en-us/articles/222071828-Department-Progress-Report)

Notably, both vendors that could have faced FLS's exact problem (Docebo branches, Absorb
departments) **chose to make the multi-membership case impossible** rather than design a
progress key that copes with it. FLS's `Learner = (user, organisation)` model, allowing a real
one-to-many between `User` and `Organisation`, is the less common design choice among the vendors
surveyed — most commercial LMSs picked "one home org per user" instead.

### SCORM — the "registration" as the unit of progress state

SCORM/SCORM Cloud (Rustici) is unusually explicit about naming the exact object this research
project is asking about: a **"registration"** is "the record... of a learner being associated with
a course" — i.e. SCORM's registration is deliberately **not** the same object as the learner or the
user. "A registration links one Learner to one Course," and "multiple registrations can be
associated with the same learner id" (e.g. one learner across three courses is three
registrations). SCORM Cloud's own docs distinguish **"User vs. Learner"** as related-but-different
concepts specifically to support this.
[SCORM Cloud: "Getting Started: What's a Registration?"](https://support.scorm.com/hc/en-us/articles/206163476-Getting-Started-What-s-a-Registration)
[SCORM Cloud: "Course Registrations"](https://support.scorm.com/hc/en-us/articles/115004359954-Course-Registrations)
[SCORM Cloud: "User vs. Learner"](https://support.scorm.com/hc/en-us/articles/360039781254-SCORM-Cloud-User-vs-Learner)

The SCORM runtime data model itself (`cmi.core.lesson_status` in 1.2; `cmi.completion_status` /
`cmi.success_status` / `cmi.progress_measure` in 2004) is written *per registration/attempt*, not
per bare user — the standard's own architecture already treats "learner associated with this
particular delivery context" as the natural unit of progress state, which is structurally the same
move FLS is making by keying on `Learner` instead of `User`.
[SCORM.com: "SCORM Run-Time Environment"](https://scorm.com/scorm-explained/technical-scorm/run-time/)
[SCORM.com: Run-Time Reference Chart](https://scorm.com/scorm-explained/technical-scorm/run-time/run-time-reference/)

SCORM itself has no native org/tenant concept — a "registration" is scoped to (learner, course) as
delivered by whatever LMS hosts it; any org/tenant dimension is entirely the hosting LMS's problem,
layered outside the standard.

### LTI — `resource_link_id` / `context_id`

LTI's identifiers scope to *placement*, not organisation: `context_id` identifies "the context
(typically the course)," and `resource_link_id` identifies one particular placement of a tool
within that context — "opaque unique identifier[s]... guaranteed... unique within the Tool
Consumer for every placement of the link." Two placements of the same tool in the same course get
different `resource_link_id`s and are tracked as separate grade/progress lines by the receiving
tool.
[IMS Global: "What is the resource_link_id in LTI?"](https://support.imsglobal.org/support/solutions/articles/48000607731-what-is-the-resource-link-id-in-lti-)
[IMS Global: "Best Practices for Managing IDs in LTI"](https://www.imsglobal.org/best-practices-managing-ids-lti)

Critically, IMS's own guidance flags that **`user_id` is only unique within one Tool Consumer** —
"the same user when launching from different Tool Consumers" gets a *different* LTI `user_id`.
LTI has no built-in notion of "the same person across two consumers/tenants" at all; each
consumer (roughly: each institution/tenant) is a hard identity and progress boundary by
construction, with no standard mechanism to say "these two `user_id`s are the same human." This is
the opposite end of the spectrum from FLS's `Learner` model, which explicitly links two
organisation-scoped identities back to one `User`.
[IMS Global: "Best Practices for Managing IDs in LTI"](https://www.imsglobal.org/best-practices-managing-ids-lti)

### Open edX — `CourseEnrollment` and `StudentModule`; the `organizations` app

Open edX's progress state (`courseware_studentmodule`, backing the Progress page and grades) is
looked up by **`(course_id, student_id, module_id)`** — no organisation dimension in the key at
all. Unenrolling and re-enrolling from the same course leaves `courseware_studentmodule` state
untouched ("courseware state is not lost"), confirming progress is a durable property of
(student, course-content), independent of the enrolment record's own lifecycle.
[Open edX docs: "User Info and Learner Progress Data"](https://docs.openedx.org/en/latest/developers/references/internal_data_formats/data_references/sql_schema.html)
[Open edX docs: "Enrollment"](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-juniper.master/manage_live_course/course_enrollment.html)

Open edX does have an **`organizations`** Django app, but its "Organization" is a
**course-publisher/content-provider** concept (feeds the `org` component of a
`course-v1:Org+Number+Run` course key, plus certificate/branding metadata) — it groups *courses*,
not *learners into tenants*, and has no relationship whatsoever to a learner's progress record.
This is a meaningfully different concept from FLS's `Organisation` (which groups learners/clients),
and is flagged here specifically so the word "Organization" is not mistaken for a precedent that
supports either side of the person-vs-association question. Open edX's `CourseEnrollment` also
has no per-org variant: `unique_together` is effectively (user, course) via its own constraints,
one active enrolment per user per course, matching the person-scoped model throughout.
[edx-organizations models.py](https://github.com/openedx/edx-organizations/blob/master/organizations/models.py)
[Open edX wiki: "Partners, Sites, and Organizations"](https://openedx.atlassian.net/wiki/spaces/AC/pages/103907632/Open+edX+Partners+Sites+and+Organizations)

---

## 1. The trade-off, framed honestly

Two coherent positions exist, and the systems above split roughly as follows:

- **Person-scoped ("do it once, done everywhere"):** Moodle/Workplace `course_completions`
  (userid+course only, confirmed schema), Open edX `StudentModule` (course_id+student_id+module_id,
  confirmed), Totara (completion explicitly said to survive a tenant move). None of these
  documentation sources frame this as a considered trade-off for the *multi-org* case
  specifically — it reads as an artifact of "course" being the natural unit and organisation being
  a bolt-on grouping layer added later (Moodle Workplace tenants, Totara tenants) without touching
  the underlying completion table. I found no vendor statement of the form "we chose person-scoped
  progress *because* buyers want a single shared training record" — that argument is not made
  explicitly by any source found, though it is the practical effect for buyers who *do* want it
  (e.g., a shared professional-body certification that should count once no matter which employer
  channel someone came through).

- **Association-scoped by construction exclusion:** Docebo (one branch per user) and Absorb (one
  department per user) both avoid the question by disallowing the underlying multi-membership
  case, rather than by deliberately keying progress on the association. Their own docs frame this
  as a limitation to route around (secondary usernames for Docebo; "groups" for Absorb reporting)
  rather than a designed feature.

- **SCORM is the one system that names a first-class "association" object (the registration) and
  explicitly separates it from the learner/user**, precisely so that "this learner, this course,
  this particular delivery" can be counted and re-counted without touching the identity of the
  learner. This is the closest external precedent to FLS's `Learner`-scoped `CourseProgress`
  direction — SCORM's registration and FLS's `(learner, course)` progress row solve the same shape
  of problem, even though SCORM's axis is "attempt/delivery" rather than "client organisation."

- **LTI takes person-scoping to the opposite extreme**: it doesn't even guarantee `user_id` is
  stable across tenants, so "shared progress across organisations" isn't offered *or* denied — it's
  simply outside what the standard tracks at all, pushed onto each Tool Consumer.

No source directly states "we evaluated shared-vs-siloed progress across client organisations and
chose X because our buyers said Y" for any of these products; every framing above is this
researcher's synthesis of documented behaviour, not a quoted rationale. That absence is itself a
finding: this exact design question is not something vendors discuss in public documentation,
supporting the assessment that FLS's `Learner`-scoped fix is addressing a genuinely underserved
corner of LMS design, not retreading a well-trodden, well-argued path.

## 2. What users and admins complain about

- **Docebo**: admins want a person present under two client domains and can't — the documented
  workaround is a second account/secondary email, which itself creates the double-counting problem
  in reverse (now it looks like two different people in reports).
  [Community thread](https://community.docebo.com/product-q-a-7/can-you-access-another-domain-with-the-same-username-4587)
- **Absorb**: identical shape — "each user can only be allocated to one department" is stated as a
  flat constraint in the help center, with groups offered as the only multi-membership escape,
  explicitly for reporting/permissions rather than progress.
  [Absorb Departments: Overview](https://support.absorblms.com/hc/en-us/articles/29878102068371-Departments-Overview)
- **Moodle Workplace**: the documentation itself flags, as a caveat rather than a complaint thread,
  that enrolling a tenant's user into a shared course means that user is now visible to and
  interacting with users from *other* tenants in that course's forums/gradebook/participant list —
  i.e. isolation leaks at the course boundary specifically because progress/participation data
  isn't tenant-partitioned. [MoodleDocs: Multi-tenancy](https://docs.moodle.org/502/en/Multi-tenancy)
- **Canvas**: the sharpest documented pain point — cross-listing a section *after* students have
  submitted work **destroys the link between the moved enrollment and its existing submissions/
  grades**. This is a direct, confirmed example of what happens when an association (section →
  course) is re-scoped without a stable identity to hang progress off: the progress silently
  detaches. [Rutgers cross-listing guide](https://canvas.rutgers.edu/documentation/support/crosslist/)
- **Cornerstone**: buyers wanting to restrict Transcript/User API visibility by division or region
  are told this "must be managed by the client" — the platform doesn't do it natively, because the
  transcript has no OU partition to filter on. [Cornerstone Transcript API docs](https://csod.dev/guides/learning/transcript/)
- **General across vendors**: I found no discussion-forum thread using the literal phrasing
  "why is this learner already complete" or similar for the org-crossing scenario specifically;
  searches for that phrasing returned only generic completion-status documentation, not complaint
  threads. Flagged as **unverified/not found** rather than asserted.

## 3. Reporting consequences (FLS's exact live defect, mirrored elsewhere)

- **Moodle**: `course_completions` has no organisation/cohort/tenant column, so any Moodle report
  that groups completions "by cohort" is doing a join through enrolment/cohort-membership tables
  at report time, not reading a stored per-cohort progress fact — if a learner is in two cohorts
  feeding the same course, both cohort-scoped reports will show the *same single* completion row,
  which is exactly the "one shared row, viewed from two angles" shape FLS has today with
  `CourseProgress.unique_together = ["user", "course"]` versus two `Organisation`s.
  [Zoola schema: course_completions](https://moodleschema.zoola.io/tables/course_completions.html)
- **Docebo**: the community's own remediation for branch-level completion reporting is "build
  separate reports for branches vs. groups to avoid confusing membership," which is a report-layer
  workaround for the same underlying fact — completion is one row per user × course, and any
  branch-scoped view is a filtered projection of it, not an independent measurement.
  [Docebo community: reporting per branch](https://community.docebo.com/let-s-talk-shop-42/getting-details-in-reporting-x-completions-of-a-course-per-branch-12336)
- **Canvas**: cross-listing's data loss shows the failure mode in the other direction — when an
  admin action *does* attempt to re-scope an association's ownership of progress after the fact,
  and there's no stable object to carry the link, the progress is orphaned rather than
  re-attributed.

## 4. Migration stories

I found no case study, vendor blog post, or public postmortem describing a system that
deliberately migrated its progress model **from person-scoped to association-scoped** (or vice
versa) and reported what it cost. General "LMS migration" search results returned only
generic platform-to-platform migration checklists (data export/import guidance), not schema
redesigns within a single platform. This should be treated as **an open gap in public information**,
not as evidence that no such migration has ever happened — vendors are unlikely to publish
postmortems of internal schema changes of this kind. FLS's own recent `User` → `Learner`
migration for enrolment records (already shipped, per project context) is itself the closest
concrete precedent available, and it is internal, not externally documented.

---

## What this means for FLS

- FLS's planned move — keying `CourseProgress`/`TopicProgress`/`FormProgress` on `Learner` instead
  of the bare `User` — has a real, named external precedent in **SCORM's "registration"**: an
  object deliberately distinct from the learner/user, scoped to one association with one course,
  so that re-associating (a new registration, or here, a second `Learner` row) doesn't corrupt or
  merge state. That is the strongest structural analogy found in this research.
- Most commercial vendors (Docebo, Absorb) avoid this problem by **forbidding** one user from
  belonging to more than one branch/department — FLS already rejected that path when it shipped
  `Learner` as `(user, organisation)` unique, allowing genuine multi-membership. That decision is
  the less common industry choice, so FLS should not expect to find a mature off-the-shelf pattern
  for the reporting layer; it has to build one.
- Where vendors *do* allow shared course libraries across tenant-like groupings (Moodle Workplace
  tenants, Totara tenants), their own documentation is candid that **course-level progress and
  participation are not tenant-partitioned at all** — Moodle explicitly warns that a shared course
  leaks visibility across tenants. FLS's design goal (per-`Learner`, i.e. per-`Organisation`,
  progress rows sharing one `Course`) is more precise than any of these — it is closer to SCORM's
  per-registration model than to Moodle/Totara's per-tenant leakage.
- Report-layer double-counting is not hypothetical or FLS-specific: Moodle's own cohort-completion
  reports and Docebo's own branch-completion reports are, underneath, filtered views over a single
  shared per-(user, course) row — the same shape as FLS's current defect. Moving the key to
  `Learner` fixes this at the *source* rather than requiring reports to keep working around a
  shared row, which is the workaround every surveyed vendor's admin community has had to invent.
- Canvas's cross-listing data-loss bug is a cautionary tale for **migration mechanics**, not the
  target model: if FLS's migration from `(user, course)` to `(learner, course)` ever needs to
  reattribute an *existing* `CourseProgress`/`TopicProgress` row to a specific `Learner` (when a
  `User` already has two `Learner` rows and one legacy progress row must be assigned to one of
  them), do it deliberately with a documented default (e.g. attribute to the `Learner` from the
  most recent/active `LearnerCourseRegistration`) rather than leaving it to silently orphan, the
  way Canvas's post-hoc cross-list does to submissions.
- FLS should keep completion/progress **explicitly out of Site's isolation semantics** and squarely
  inside the `Learner` grain — none of the surveyed systems that support real progress isolation
  (Moodle Workplace tenants, Totara tenants) partition progress at the *course-content* level, only
  at the *tenant/org membership* level, which maps to FLS's `Learner` (the org-facing association),
  not to `Course`/`TopicProgress`'s content structure. This matches the plan already described in
  the baked-in context and is reinforced, not contradicted, by these findings.
- Watch for the **Open edX "organizations" trap** specifically: that app's "Organization" is a
  course-publisher/branding concept with zero relationship to learner progress. Anyone drawing on
  Open edX prior art for this work should not assume its `organizations` app is a precedent for
  FLS's `Organisation` — it answers a different question entirely (who published this course, not
  who is this learner enrolled through).
  [edx-organizations models.py](https://github.com/openedx/edx-organizations/blob/master/organizations/models.py)
- No vendor source found frames "one shared record across employers" as a considered, named
  product decision — it should be treated as an accidental default of an older, simpler
  `(user, course)` schema that organisation/tenant layers were later bolted onto, exactly as FLS's
  own `CourseProgress` predates `Learner`. This supports treating the fix as closing technical debt
  rather than reversing a deliberate design choice anyone will miss.
- The migration-story gap (no public precedent found for changing progress grain after the fact)
  means FLS's own migration plan and rollback story should be written from first principles, with
  particular attention to: what happens to a pre-existing `CourseProgress` row for a `User` who
  currently has exactly one `Learner`, versus a `User` who (rare, but permitted by the data model)
  already has two `Learner` rows before the migration runs.

status: ok
