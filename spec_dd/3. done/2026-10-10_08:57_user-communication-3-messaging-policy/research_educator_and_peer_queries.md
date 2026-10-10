# Research: the relationship queries and which educators a learner is offered

Extends `spec_dd/1. next/user-communication/research_messaging_relationships_and_surfaces.md` (R2). It does not repeat R2. It verifies R2 against the code as it stands now, and R2 is **stale in several load-bearing places** (section 1). Everything below uses the live names.

## 1. How visibility is computed today (and where R2 is out of date)

### What changed since R2

`educator-interface-5-permissions` is **done** (`spec_dd/3. done/2026-10-01_22:00_educator-interface-5-permissions/`), not in progress. R2 describes the pre-spec-5 world. The corrections:

- **Role keys were renamed**, with no alias: `organisation_staff` -> `organisation_admin`, `instructor` -> `cohort_admin`, `ta` -> `cohort_viewer`. `site_admin` kept its key. R2's sketch query (`role__in=["instructor", "ta"]`, `role="organisation_staff"`) would match nothing. The `learner` and `observer` roles exist but carry empty permission sets, so they grant nothing.
- **Guardian no longer decides visibility.** `can()` and the `queries.py` helpers read `SiteRoleAssignment` / `ObjectRoleAssignment` rows plus the role config. They never read guardian rows. R2's advice to use `get_users_with_perms` is therefore wrong: it would disagree with `learners_visible_to`. The inverse query must be written against the assignment rows.
- **New gate: `OrganisationMember`** (`learner_management/models.py`, `(site, user, organisation, is_active)`). An `organisation_admin`, `cohort_admin` or `cohort_viewer` grant counts only while the holder has an *active* `OrganisationMember` for that organisation (for a cohort grant, the cohort's organisation). `site_admin` and superusers need no row. A `post_save` receiver on `ObjectRoleAssignment` creates the row for new or re-saved grants. No migration backfilled rows for older grants. The inverse query has to apply the same gate.
- **Roles are matched by capability, not by name.** `learners_visible_to` asks `roles_granting(VIEW_LEARNER, site)` (`capabilities.py:41`), which returns every role key in the per-site role config (`get_role_config(site.name)`) whose permissions include `freedom_ls_learner_management.view_learner`. In the built-in config that is `site_admin`, `organisation_admin`, `cohort_admin` and `cohort_viewer`. A downstream per-site config can add custom roles, and they count. The inverse must use `roles_granting`, never a hard-coded list of names, or the two directions drift apart on any install with a custom role.
- **The glossary has no role entries and no "educator" entry.** See section 5.

### The computation, exactly

`learners_visible_to(user, organisation)` (`queries.py:288-321`):

1. `within = Learner.objects.filter(organisation=organisation, is_active=True)`.
2. `_resolved_or_none`: an anonymous or inactive user gets `.none()`. A superuser gets all of `within`. Everyone else continues. `is_staff` plays no part.
3. `roles = roles_granting(VIEW_LEARNER, organisation.site)`. The site is taken from the **organisation**, not from the request.
4. **Organisation-first:** if the user holds an active `SiteRoleAssignment` for any of `roles` on that site (`_site_grants`, ungated), **or** an active `ObjectRoleAssignment` for any of `roles` on that `Organisation` with an active `OrganisationMember` for it (`_granted_organisations`), then `visible = Q(organisation=organisation)`. That is every active learner in the organisation, cohort or no cohort.
5. **Cohort-second:** otherwise `visible = Q(organisation=organisation, cohortmembership__cohort__in=_granted_cohorts(user, roles))`. `_granted_cohorts` is cohorts carrying an active `ObjectRoleAssignment` of `roles`, gated on an active `OrganisationMember` for the cohort's organisation.
6. Returns `Learner.objects.filter(visible, is_active=True).distinct()`. `distinct()` is needed because the cohort join duplicates a learner who sits in two granted cohorts.

Things the function does **not** do, which the inverse must copy rather than "fix":

- It does not check that the learner's **user** is active, only `Learner.is_active`.
- It does not exclude the caller. An `organisation_admin` who also holds a `Learner` row in the same organisation sees themselves.
- It does not look at `Cohort` state (no `is_active` on `Cohort` yet). `educator-interface-6-cohort-administration` is planned to add one (roadmap row 6). When it lands, `cohorts_visible_to` and the inverse will need the same decision, and `learners_visible_to` will need it too, so the property test below is what catches a one-sided change.
- It does not require `cohort.organisation == organisation` in the cohort branch. `CohortMembership.clean()` forbids a cross-organisation membership, but factories skip `clean()`. The inverse should mirror the forward behaviour, not tighten it.

### Which roles grant it, by scope

| Role | Scope row | Reaches | Gate |
| --- | --- | --- | --- |
| superuser (`is_superuser`) | none | every learner on the site | active user only |
| `site_admin` | `SiteRoleAssignment` | every active learner in every organisation on the site | none |
| `organisation_admin` | `ObjectRoleAssignment` on `Organisation` | every active learner in that organisation | active `OrganisationMember` |
| `cohort_admin` | `ObjectRoleAssignment` on `Cohort` | members of that cohort only | active `OrganisationMember` of the cohort's organisation |
| `cohort_viewer` | `ObjectRoleAssignment` on `Cohort` | members of that cohort only | same |
| custom role holding `view_learner` | either | depends on its `assignment_scope` | same as the built-in at that scope |
| `system_admin` | `SystemRoleAssignment` | **nothing**: empty permission set, never consulted by `queries.py` | n/a |

Neither `cohort_admin` nor `cohort_viewer` assigned **on an organisation** is a supported shape, but nothing in `learners_visible_to` forbids it: an `organisation_admin`-style reach comes from `_granted_organisations` for *any* role in `roles`, so a `cohort_viewer` row written on an `Organisation` would see the whole organisation. The inverse falls out the same way if it asks "any role in `roles` on the organisation".

### Site scoping outside a request

- `SiteAwareManager.get_queryset()` filters by site only when a request is on the thread-local (`site_aware_models/models.py:117-128`). In a task there is no request, so `Learner.objects`, `ObjectRoleAssignment.objects` and the rest return rows across every site.
- `learners_visible_to` is **safe outside a request** because every queryset is pinned to a specific `Organisation` (and the role config and `_site_grants` take `organisation.site`). Nothing in it calls `_current_site()`.
- `organisations_accessible_to` and `all_cohorts_visible_to` are **not safe**: they call `_current_site()`, which returns `None` with no request, and then return `.none()` for any non-superuser (`queries.py:209-211`, `265-267`). The comms queries must not be built on them. The idea already says relationship queries take the site explicitly, and this is the concrete reason.
- So the inverse takes a `Learner` (which carries `site` and `organisation`), and an explicit-site filter must be written on every table it touches. `ObjectRoleAssignment`, `OrganisationMember` and `SiteRoleAssignment` are all `SiteAwareModel`s with a `site` column. Inside a request the manager filters them for free, but inside a task nothing does, so add `site=learner.site` explicitly. It is redundant inside a request and mandatory outside. `User` is not site-aware, so any `User.objects.filter(...)` is global and must be restricted by the assignment subqueries.
- `get_role_config(site.name)` keys on the site **name**, so the role config is per site. A learner's site and the educator's assignment rows are in the same site by construction (assignment rows carry `site`).

### The registration and membership models (verified)

- `Learner(user, organisation, is_active)`, unique `(site, user, organisation)`. A user may hold several rows (several organisations).
- `CohortMembership(cohort, learner)` has no `is_active`. A membership is "active" only through `learner.is_active`.
- `LearnerCourseRegistration(course, learner, is_active, self_registered)`, unique `(site, learner, course)`.
- `CohortCourseRegistration(course, cohort, is_active)`, unique `(site, course, cohort)`.
- `OrganisationMember(user, organisation, is_active)`, unique `(site, user, organisation)`. It is independent of `Learner`: a user can hold both in one organisation.
- `active_organisation_admins(organisation)` (`queries.py:324`) already exists. It returns active `organisation_admin` holders gated on `OrganisationMember`, as `User`s. It hard-codes the role name and is used for "who to ask" copy. It is a **partial precedent** for the inverse query, but it covers neither site admins nor cohort roles and does not use `roles_granting`, so it cannot be reused as the inverse.

## 2. The inverse: `educators_of(learner)`

### Shape

Take a `Learner` row (a `learner_management` noun; the idea's `learners_visible_to` returns `Learner`s, and the glossary says not to add user-shaped siblings for learners). Return a `User` queryset. Educators are users and not `Learner`s, so this is the one place the answer is user-shaped. In prose:

1. If `learner.is_active` is false, return no users. This mirrors the `is_active` filter on `within`.
2. `roles = roles_granting(VIEW_LEARNER, learner.site)`.
3. Build three id sets as subqueries, all restricted to `site=learner.site`:
   - **Site level:** `SiteRoleAssignment` rows with `role in roles`, `is_active`, giving `user_id`. Ungated.
   - **Organisation level:** `ObjectRoleAssignment` rows for the `Organisation` content type, `object_id = str(learner.organisation_id)`, `role in roles`, `is_active`, restricted to users with an active `OrganisationMember` for that organisation.
   - **Cohort level:** `ObjectRoleAssignment` rows for the `Cohort` content type whose `object_id` is in the learner's cohort pks as text, `role in roles`, `is_active`, restricted to users with an active `OrganisationMember` for **the cohort's** organisation. Doing the gate on the cohort's organisation (not the learner's) is what mirrors `_granted_cohorts`.
4. `User.objects.filter(is_active=True).filter(Q(pk__in=site) | Q(pk__in=org) | Q(pk__in=cohort))`, plus the superuser branch below.

Prefer OR-ed `pk__in` subqueries over `.union()`. A union queryset cannot be filtered or ordered further, and the policy's third question ("which users may the sender start a conversation with") must stay composable. `pk__in` subqueries cannot produce duplicates, so no `distinct()` is needed. If any implementation joins through `CohortMembership` instead of using `pk__in`, it needs `distinct()`, which is the same duplicate that `learners_visible_to` already guards against.

The cohort-level text cast is the inverse of `_grant_exists`: forward direction casts the outer pk to text. Backward, cast the learner's cohort pks to text (`Cast("cohort_id", CharField())` or a `str()` list). `ObjectRoleAssignment` has an index on `(content_type, object_id, role, is_active)` that serves this lookup directly.

To make the two directions agree by construction and not by luck, the best option is to reuse `_active_role_assignments(model, roles)` and the `_member_organisations` shape from `capabilities.py`, which the file's own docstring says is the point ("the queryset twin of each step"). Add the inverse beside them. `queries.py` already imports these private helpers, so a `comms` or `learner_management` query module can too. Where it lives matters: the idea says `comms` base imports no cohort model, so the inverse belongs in `learner_management` (next to `learners_visible_to`) and `comms` calls it through the policy implementation.

### The pitfalls

- **Superusers.** `learners_visible_to` returns everything for any active superuser, with no assignment row. An exact inverse must include every active superuser in every learner's educators. That is almost certainly not what the composer should show. Recommendation: make the query function return the **role-derived** educators and have the superuser branch be an explicit, documented decision, either excluded from offer lists but permitted by `can_start` for pairs, or included. Whatever is chosen, say so in the docstring and test both. The property test must treat superusers as a separate assertion, not an exception that silently weakens it.
- **`is_staff` is irrelevant.** Only `is_superuser` changes `learners_visible_to`. Do not special-case staff.
- **`site_admin` sees everyone on the site.** The site branch contributes every site admin to every active learner's educators. This is correct for the inverse rule but is the source of the offer problem in section 4.
- **Inactive rows.** Five different flags apply: `Learner.is_active` (the learner), `User.is_active` (educator, checked in `_resolved_or_none` for the forward direction), `ObjectRoleAssignment.is_active` / `SiteRoleAssignment.is_active`, and `OrganisationMember.is_active`. The forward direction does **not** check the learner's `User.is_active`; the inverse should not add the check either, or they disagree. The policy can add "recipient user is active" on top, as an explicit extra, and the property test excludes it.
- **A user who is both learner and educator.** Self-visibility is possible (an `organisation_admin` with a `Learner` row in the same organisation sees themself). The policy must reject sender == recipient, since a conversation with oneself is meaningless. The pair query can exclude self, and the property test compares modulo self.
- **Multiple `Learner` rows for one user.** `educators_of(learner)` is per `Learner`. A message recipient is a `User`, so the policy question "may educator E message user U" is true if E is an educator of **any** active `Learner` row of U. That "any" is a spec decision ("whose context decides a pair" in the idea's open list) and the query function should expose a user-level form that ORs across the user's active `Learner` rows.
- **Duplicates from multiple paths.** Covered above. An educator who is `site_admin`, `organisation_admin` and `cohort_admin` of the learner's cohort is one row in the result.
- **Custom roles and per-site configs.** Covered above: use `roles_granting`.
- **Gate backfill.** Installs upgraded across spec 5 without the manual backfill have grant holders with no `OrganisationMember`. They are invisible to `learners_visible_to` and must be invisible to the inverse. Because both go through the same gate this holds, but it is a surprise worth a line in the upgrade notes.

### Testing the agreement

Write a property-style test, not a handful of examples. The repo has no `hypothesis` dependency (`pyproject.toml` has no match), so build a deterministic scenario matrix with factories, which is cheaper than adding a dependency:

1. One site, two organisations, three cohorts (two in organisation A, one in B), learners covering: in a cohort, in two cohorts, in no cohort, inactive, in both organisations (one user, two `Learner` rows), and a user who is also an educator.
2. Educators covering every row type and every gate state: `site_admin`; `organisation_admin` with and without an active `OrganisationMember`; `cohort_admin` and `cohort_viewer` on one cohort and on two; an inactive assignment; an inactive user; a superuser; a user with a custom role from a test role config; a user with no role.
3. The assertion: for every educator E, every organisation O, and every active-or-not learner L in O, `L in learners_visible_to(E, O)` iff `E in educators_of(L)`. Compare id sets in both directions, and compute both sets from the same fixture so a disagreement names the case.
4. Separate tests for the cases the property deliberately carves out (superuser, self, user-level OR across `Learner` rows), and a query-count test on `educators_of` (a fixed small number, independent of the number of cohorts), following `TestOrganisationForLearnerCourseQueryCount`.
5. Run the matrix under `mock_site_context` (as `TestLearnersVisibleTo` does) **and once with no request on the thread-local**, to prove the inverse really is request-independent, which is the property the idea relies on.

The existing `TestLearnersVisibleTo` (`tests/test_queries.py:489`) is a good template. It covers organisation role, inactive learner, removed learner still in a visible cohort, other organisation, cohort-only educator, anonymous and no-role.

## 3. The peers queryset

### Shape

"Peers of a learner": other **active** `Learner` rows (not the same user) who share an active cohort membership, or a course via either registration path. Returned as `Learner` rows, since the idea defines peers as learners, with a user-level wrapper for the composer, which needs distinct users and must collapse multiple `Learner` rows per user.

In prose, with `me` = the sender's active `Learner` row(s):

- **Shared cohort:** peer `Learner` p, active, with `Exists(CohortMembership where learner=p and cohort in me's cohorts)`.
- **Shared course, individual path:** `me_courses` = courses with an active `LearnerCourseRegistration` for `me`, unioned with courses with an active `CohortCourseRegistration` on any of `me`'s cohorts. Peer p shares if `Exists(LearnerCourseRegistration where learner=p, is_active, course in me_courses)`.
- **Shared course, cohort path:** `Exists(CohortCourseRegistration where is_active, course in me_courses, cohort__cohortmembership__learner=p)`.
- Outer filter: `p.is_active=True`, `p.user != me.user`, same site.

Both registration branches must sit in one `filter()` call per `Exists`, for the same reason `is_registered_for_course_expression` says: a split filter can match a membership belonging to one learner and a registration belonging to another. Here the join key is the outer peer `Learner` row, so the cohort and the membership conditions must both be on the same `CohortMembership` row.

Two things differ from `is_registered_for_course_expression`, which is user-based:

- It keys on `learner__user`, so a user with two `Learner` rows pools them. For peers, whether to pool is the same "whose context decides" question as in section 2. Decide once in the spec, then both functions follow it.
- Neither `CohortMembership` nor `CohortCourseRegistration` for an **inactive** `Learner` counts; the existing expression already requires `learner__is_active=True` on the cohort path.

### Cross-organisation peers

A course is not owned by an organisation. Two learners in different organisations can share a course. Cohorts are organisation-owned, so a shared cohort is always intra-organisation. Peers via a shared course can therefore cross organisations. Since `Organisation` is "a grouping, not an isolation boundary" (glossary), but a client organisation's learners seeing a competitor client's learners is a safeguarding and privacy risk, the spec should restrict course peers to the **same organisation** unless a level opens wider. At minimum it needs an explicit decision.

### Query cost and indexes

Cost is a small, fixed number of `EXISTS` subqueries against the outer `Learner` queryset, with one correlated subquery per branch and one subquery computing `me_courses`. It is fine for a composer (one sender, run per page view of the composer, not per message). It scales with the number of learners in the sender's cohorts and courses, so a course with thousands of peers returns thousands of rows. The composer needs search or pagination, not a full list. Peers are not safe to enumerate in a `<select>`.

Indexes, from `Meta` and default FK indexing (not verified against the migration SQL, so this is inferred from the model definitions):

- `CohortMembership`: unique `(learner, cohort)` serves learner -> cohorts. The `cohort` FK has its own index, so cohort -> members is covered.
- `LearnerCourseRegistration`: unique `(site, learner, course)` is site-leading, so it only helps when the site is in the predicate. The `learner` and `course` FKs have single-column indexes. There is **no** composite `(course, is_active)` or `(learner, is_active)` index and no partial index on `is_active=True`. At current scale this is fine. It is worth a note, not a migration.
- `CohortCourseRegistration`: unique `(site, course, cohort)` plus FK indexes on `course` and `cohort`. Same remark.
- `Learner`: unique `(site, user, organisation)` plus FK indexes. No index on `is_active`, and none is needed, since it is a low-selectivity flag.
- `ObjectRoleAssignment`: `(content_type, object_id, role, is_active)` and `(user, is_active)` (the inverse query's key lookup is served). `SiteRoleAssignment`: `(site, role)`. `OrganisationMember`: unique `(site, user, organisation)`. All adequate for the inverse.

No new index is required for this spec.

## 4. Which educators a learner is offered

### The problem

The inverse rule makes every `site_admin` an educator of every learner on the site, and every `organisation_admin` an educator of every learner in the organisation. A composer fed by the inverse query would show a learner every site admin and every organisation admin. On a large site that is a long, mostly irrelevant list, and it exposes the identities of administrators.

### Prior art

- **Canvas.** The Inbox recipient list is built from courses you are enrolled in. A student's only recipients are teachers, TAs and other students in their courses. Students cannot see a list of administrators, and the usual advice to students who need to reach an admin is to use a school-wide course that enrols both ([Canvas community: How can students send a message to administrators?](https://community.canvaslms.com/t5/Canvas-Question-Forum/How-can-students-send-a-message-to-administrators/m-p/455881)). Account admins can read conversations but are not in a student's recipient list unless enrolled. The permission "send messages to other course members" can be revoked from the student role, leaving students able to reply to teachers but not start peer messages ([Canvas Ideas: allow students to message...](https://community.canvaslms.com/t5/Canvas-Ideas/Conversations-Student-messaging-inbox-allow-students-to-message/idi-p/394244), as cited in `research_flexible_configurable_comms.md`). Lesson: **recipients are derived from teaching relationships in context (the course), not from administrative reach.**
- **Moodle.** A user's privacy setting restricts incoming messages to contacts, or contacts plus others in their courses. Site-wide messaging, which lets users find anyone, is an admin switch, off by default ([Moodle docs: Messaging](https://docs.moodle.org/401/en/Messages)). Lesson: "my contacts and anyone in my courses" is the default blast radius, and "anyone on the platform" is opt-in at site level.
- Both treat the **administrative** reach (account admins, site admins) as separate from the **teaching** relationship, and neither offers administrators to a learner by default.

### Options

**A. Offer only cohort-scoped roles** (`cohort_admin` and `cohort_viewer`, i.e. the holders who reach the learner through a cohort grant).
- Pros: matches the Canvas model (teaching staff in the learner's group), short list, no admin exposure, maps to a real relationship ("the people running my cohort"), and needs no configuration.
- Cons: a learner with no cohort has nobody to message, which is exactly the cohort-less install the idea says must work "with no special case". `cohort_viewer` is described as "Sees a cohort and its reports. Changes nothing." (`roles.py`): it is a read-only reporting role and may be a stakeholder (a sponsor or manager), not a person who answers learners. Offering them as someone to message is questionable.
- Hard-codes role names in a policy that elsewhere resolves by capability, which breaks custom roles.

**B. Offer role types selected by configuration** (a setting listing which role keys are offered as "someone I can message", defaulting to a conservative list).
- Pros: handles cohort-less installs (an install can list `organisation_admin`), custom roles work (the list names role keys), fits the idea's layered, closed-by-default configuration, and lets a site that wants "talk to a cohort admin" say so.
- Cons: more configuration surface, and it is a new axis next to the layered flags the spec is already deciding. A role key list needs validating against the role config, since a typo silently offers nobody.
- Interacts with the open item "flags per level versus named policies": a role list is a natural field on a per-level row.

**C. Offer everyone who can see the learner** (the plain inverse).
- Pros: one rule, no asymmetry, simplest to explain and to test, and exactly what the idea currently says "settles who counts".
- Cons: exposes every site admin and organisation admin, a long list on a large site, and a learner gets no signal about who is the right person. Also admin accounts become a harassment target, and it cuts against both reference LMSs.

### The asymmetry

If the composer offers less than the inverse set, the system is asymmetric in one direction:

- An educator may start a conversation with any learner they can see (the settled default, the forward rule). A learner may reply to that educator, even if the educator would not be offered in the learner's composer.
- A learner cannot **start** a conversation with that educator.

That is acceptable and is the common pattern (Canvas lets a student reply to anyone who messaged them while the recipient list is context-based). It does not break the "inverse of visibility" rule as long as the rule is stated precisely: *who counts as an educator of a learner* (for reply, for the educator-side quick view, for notifications) is the inverse of visibility, while *who a learner may be offered to start with* is a configured subset of that. The three policy questions already separate "may reply" from "may start" and from "which users", so the contract has room for this. The spec has to make sure two things hold:

1. `can_start(learner -> educator)` implies `educator in educators_of(learner)` (the offered set is a subset of the inverse set, never a superset). That is a clean testable invariant.
2. `can_reply` for the learner holds whenever the educator started the conversation, subject to the closed-conversation questions in the idea.

One further wrinkle is the learner who is blocked from starting but whose educator is also **their own recipient** through a different path. If a learner holds two roles toward one person (say that person is `cohort_admin` for the learner and `site_admin` of the site), the offered set is a union over roles, so the person is offered if **any** of their roles is on the offered list. State this.

## 5. Terminology against the domain glossary

- `.claude/skills/domain-glossary/SKILL.md` has **no entry for any role** (`site_admin`, `organisation_admin`, `cohort_admin`, `cohort_viewer`) and **no entry for "educator"**, `OrganisationMember`, or `ObjectRoleAssignment` / `SiteRoleAssignment`. The glossary also has no "peer". The four role keys are defined in `role_based_permissions/roles.py` and are the vocabulary of last resort. This spec should use them as written. The idea does (`cohort_admin`, `cohort_viewer`, `organisation_admin`, `site_admin`), so it matches the code and post-dates the spec-5 rename.
- **"Educator" is used loosely.** It is the name of an app (`educator_interface`) and of the person who uses it, but no model or role is called that. The idea defines it implicitly as "someone for whom a learner is visible". That is a **new meaning** for a word the repo already uses informally. The spec should say at first use that "educator of a learner" means a user for whom `learners_visible_to` includes the learner, defined in terms of the role keys, and not coin a role called `educator`. Do not use `instructor`, `ta`, or `organisation_staff`: those are the pre-rename keys, are gone, and R2 still uses them.
- **"Peer"** is new. The idea defines it ("learners who share a cohort or a course"). Define it once in the spec in terms of `CohortMembership` and the two registration models.
- **"Grant"** is a taken word in the glossary (a role or object permission). Using it for role holders ("an organisation grant") is consistent. Do not use it for messaging permission ("grant messaging"); say "open" and "close", as the idea does.
- **`is_active`** appears on `Learner`, both registrations, `OrganisationMember` and both assignment models. The glossary asks that a sentence naming two of them name the model. Section 2 of this note does.
- **Learner vs user.** `educators_of` takes a `Learner` and returns `User`s; the user-level policy question ORs across a user's `Learner` rows. Say `learner.user` when meaning the account.
- `OrganisationMember` is a real model with no glossary entry and it matters here (the gate). It should be added to the glossary as part of this effort or at least named in the spec.

## Recommendation

1. **Define "educator of a learner" as the inverse of `learners_visible_to`, built from the assignment rows and the capability-resolved role set.** Put `educators_of` in `learner_management` beside `learners_visible_to`, reusing `_active_role_assignments`, `_member_organisations` and `roles_granting`. Do not use guardian (R2 suggested it; spec 5 made that wrong) and do not hard-code role names. Take an explicit `Learner`, filter every table by `site=learner.site`, and do not depend on `_current_site()`.
2. **Agreement is enforced by a scenario-matrix test** (section 2), run both inside and outside a request, plus separate tests for superuser, self, and the user-level OR. No new dependency.
3. **Make "which educators the composer offers" a subset of the inverse set, selected by configuration (Option B)**, with a conservative closed default. Trade-offs:

   | | A: cohort roles only | B: configured role types | C: everyone who can see |
   | --- | --- | --- | --- |
   | Cohort-less install works | no | yes | yes |
   | Hides admin identities by default | yes | yes (by default list) | no |
   | Custom roles work | no | yes | yes |
   | Config surface | none | one list per level | none |
   | Matches Canvas/Moodle defaults | closest | adjustable to match | furthest |
   | Asymmetry with inverse rule | yes | yes | none |

   My suggested default for B: the roles that reach the learner **through a cohort** (`cohort_admin`, optionally `cohort_viewer`) when the learner has cohorts, with `organisation_admin` added by an explicit setting for cohort-less installs. `site_admin` is never offered by default. If the spec wants to avoid a configuration axis, **A is the simplest honest default**, with the known cost that cohort-less learners have no one to message until a level adds one, which is consistent with "nothing is open until a level opens it". Excluding `cohort_viewer` from the default is worth considering, given its description.
4. **State the asymmetry plainly in the spec:** educators of a learner (inverse of visibility) decide who may *reply* and who may *start toward* the learner; the configured offered set decides who the *learner* may start toward. Enforce `offered subset-of educators_of` as an invariant.
5. **Decide in the spec, not in code:** whether superusers count as educators (recommend: not offered, and the pair check treats a superuser like any user only if explicitly allowed), whether peers are restricted to the same organisation (recommend yes), whether a user's several `Learner` rows pool for pair decisions, and what `Cohort.is_active` (planned in `educator-interface-6`) does to all three relationship queries.
6. **Peers:** write once as a `Learner`-level queryset plus a user-level wrapper. It needs no new indexes. The composer must search or paginate, not list.
7. Add `OrganisationMember` and the four role keys to the glossary (or reference the code), and note in the upgrade notes that installs which skipped the `OrganisationMember` backfill will have educators who neither see learners nor appear as their educators.

## References

Code (all paths relative to the repo root):

- `freedom_ls/learner_management/queries.py` (`learners_visible_to` 288-321, `cohorts_visible_to`, `all_cohorts_visible_to`, `organisations_accessible_to`, `active_organisation_admins` 324, `is_registered_for_course_expression` 47, `learner_for_course`)
- `freedom_ls/learner_management/capabilities.py` (`roles_granting`, `_current_site`, `_site_grants`, `_active_role_assignments`, `_grant_exists`, `_member_organisations`, `_granted_organisations`, `_granted_cohorts`, `can`)
- `freedom_ls/learner_management/models.py` (`Cohort`, `Learner`, `OrganisationMember`, `CohortMembership`, `LearnerCourseRegistration`, `CohortCourseRegistration`)
- `freedom_ls/role_based_permissions/roles.py`, `freedom_ls/role_based_permissions/models.py` (assignment models, indexes)
- `freedom_ls/site_aware_models/models.py` (`SiteAwareManager`, 117-128)
- `freedom_ls/learner_management/tests/test_queries.py` (`TestLearnersVisibleTo` 489, `TestOrganisationForLearnerCourseQueryCount` 769)
- `spec_dd/3. done/2026-10-01_22:00_educator-interface-5-permissions/upgrade_notes.md` (role renames, guardian no longer deciding visibility, `OrganisationMember` gate)
- `spec_dd/1. next/user-communication/research_messaging_relationships_and_surfaces.md` (R2, the stale baseline)
- `spec_dd/2. in progress/user-communication-3-messaging-policy/idea.md` and `research_flexible_configurable_comms.md`
- `spec_dd/1. next/roadmap.md` (row 6 plans `Cohort.is_active`)
- `.claude/skills/domain-glossary/SKILL.md`

Web:

- Canvas, recipients limited to people in your courses, no admin list for students: https://community.canvaslms.com/t5/Canvas-Question-Forum/How-can-students-send-a-message-to-administrators/m-p/455881
- Canvas, revoking the student "send messages to other course members" permission: https://community.canvaslms.com/t5/Canvas-Ideas/Conversations-Student-messaging-inbox-allow-students-to-message/idi-p/394244
- Moodle, messaging privacy (contacts, contacts and course members, site-wide messaging as an admin switch): https://docs.moodle.org/401/en/Messages

status: ok
