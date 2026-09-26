# Research: scoped capability models — container-scope grants, inherited by contents

For educator-interface-5-permissions. Answers: how do other systems grant a permission at a
container (organisation/account/category) and have it apply to contents (cohorts/courses/learners)
that may not exist yet, and how do they keep "may I create X inside Y" and "list the Xs I may see"
answering from the same source of truth.

## The two questions FLS needs answered consistently

1. **Creation-in-container**: "may this user create a cohort in this organisation" — asked of the
   organisation, because the cohort doesn't exist yet.
2. **List filtering**: `organisations_accessible_to`, `cohorts_visible_to`, `learners_visible_to` —
   must return exactly the objects that a per-object check would say yes to, or the UI and the guard
   diverge (a row is listed but 403s on click, or omitted despite being permitted).

Every system below is shaped by how it answers these two questions without one row per
(user, permission, descendant-object).

## Moodle: contexts, capabilities, inheritance by context tree

Moodle's authorization unit is the **context** — `CONTEXT_SYSTEM`, `CONTEXT_COURSECAT`,
`CONTEXT_COURSE`, `CONTEXT_MODULE` — arranged in a tree that mirrors the container hierarchy
(site → category → course → activity module). A role assignment is a triple (user, role, context).
`has_capability($capability, $context)` walks up from the given context toward the system context,
collecting the role assignments a user holds at or above that context, and resolves the capability
against each role's permission for that capability (`allow`, `prevent`, `prohibit`, or *inherit* —
"use whatever the more general context already decided"). The most specific non-inherit setting
wins, except `prohibit` at any level in the chain overrides everything below it. [Development:Roles](https://docs.moodle.org/test/Development:Roles), [Roles and capabilities](https://docs.moodle.org/19/en/Roles_and_capabilities), [Inherit vs Prevent discussion](https://moodle.org/mod/forum/discuss.php?d=72564)

**Creation-in-container**: `moodle/course:create` must be checked against the *category* context
(or system), never a course context, because the course doesn't exist yet. The Course Creator role
is granted at category or system level and carries `moodle/course:create`; the category picker in
the "create course" UI is itself built by listing which categories the user holds that capability
in. [Capabilities/moodle/course:create](https://docs.moodle.org/311/en/Capabilities/moodle/course:create), [forum: has_capability create course](https://moodle.org/mod/forum/discuss.php?d=344349)

**List filtering / single source of truth**: because inheritance is a context-tree walk rather than
per-object rows, "list courses I may manage" is answered by walking the same
`has_capability` logic against each course's context (with query helpers that batch this by
pre-fetching the user's role assignments across the context tree once). There is exactly one
function that decides yes/no, called both for single-object guards and for building lists — no
separate "listing" logic to drift from the "can I do this" logic.

**Cost**: no row explosion — role assignment rows are proportional to (user, context) pairs, not
(user, descendant-object) pairs. Never stale, because nothing is synced onto children: a new course
created under a category with permissive category-level roles is immediately covered by every check
made against its context, because the tree walk reaches the category. Query cost is a bounded walk
up the tree (site → category → course → module is at most 4 hops) plus one query to fetch the
user's role assignments, cached per request.

## Canvas: account / sub-account / course / section roles

Canvas has the same container tree — root account → sub-account → course → section — with roles
defined per account level and enrollments scoped to a course or, more narrowly, to one or more
sections within a course. An account-level admin role's permissions apply to every sub-account,
course and section beneath it without any row being written for those descendants; Canvas resolves
permissions by checking the admin's account-role permission set against the account chain of the
object being acted on, the same shape as Moodle's context walk. Locking a permission at a higher
account level prevents sub-account admins from loosening it, which is the "prohibit wins" idea
applied top-down instead of Moodle's context-tree evaluation order. [Account Admin Roles and Permissions](https://canvas.rutgers.edu/documentation/support/account-admin/), [Sub-account Admins: Admin and Course Permissions](https://support.canvas.fsu.edu/kb/article/1162-subaccount-admins-admin-and-course-permissions/), [Canvas Account Role Permissions PDF](https://s3.amazonaws.com/tr-learncanvas/docs/Canvas_Permissions_Account.pdf)

Section-limited enrollment is the closest Canvas analogue to FLS's instructor/ta-on-a-cohort: a
TA's *enrollment* record carries a `limit_privileges_to_course_section` flag, so the same "ta" role
definition is reused, but the object the grant is checked against is narrowed from course to
section. This is a scope-narrowing flag on the assignment, not a different role and not extra rows
per learner in the section — it changes what the enrollment's existing permission set is checked
*against*, which is close to what FLS's `assignment_scope=SCOPE_OBJECT` on a cohort already does,
except Canvas's course-vs-section narrowing is a property of the enrollment rather than a
separate content-type filter problem.

**Creation-in-container**: "may create a course in this sub-account" is checked against the
sub-account, exactly as Moodle checks category. **List filtering**: same permission-resolution
function serves both a single "can this admin manage this course" check and "list courses this
admin can manage" by iterating courses under the account subtree the admin already has resolved
access to — again one function, no separate sync artifact to go stale.

## django-rules: predicates over relationships, no DB rows at all

django-rules replaces guardian's row-per-(user, permission, object) model with **predicates**:
plain callables `predicate(user, obj) -> bool` registered under a permission name via
`rules.add_perm("app.change_cohort", predicate)`. A predicate for "may manage this cohort" can walk
the relationship graph in Python/ORM at check time — e.g. `is_org_staff_of(cohort.organisation)`  —
rather than requiring a materialized permission row on the cohort. Predicates compose with `&`, `|`,
`~`, so "org staff of the cohort's organisation, or instructor assigned to the cohort" is one
expression. django-rules ships an authorization backend so `user.has_perm(perm, obj)` and
`@rules.test_rule` integrate with Django's normal `has_perm` call sites, including
`ModelBackend`-style objectless checks (a predicate can ignore `obj` and answer at the model level,
answering FLS's "guardian denies every objectless check" problem directly, since a predicate
without a row can simply be written to accept `obj=None` and answer using the user's own role
assignments). [django-rules README](https://github.com/dfunckt/django-rules), [predicates.py](https://github.com/dfunckt/django-rules/blob/master/rules/predicates.py), [Vinta Software comparison](https://www.vintasoftware.com/blog/controlling-access-a-django-permission-apps-comparison)

**Creation-in-container** is natural: the predicate for `add_cohort` takes the organisation as
`obj` and checks "is this user org_staff of this organisation", no cohort needed, no guardian
objectless-check limitation because there's no guardian row involved.

**List filtering**: this is django-rules's known weak spot. Predicates answer single-object
questions; they don't generate a queryset filter. Projects using django-rules for lists still write
a parallel `visible_to(user)` queryset function, and must hand-verify it agrees with the predicate —
the "one source of truth" property Moodle/Canvas get from a shared tree-walk function is not free
here; it has to be a project discipline (e.g. a test that, for every object, the predicate's answer
and the queryset's membership agree — which is exactly the "matrix test" the FLS spec is already
committing to).

**Cost**: zero row explosion (no permission rows for descendants at all), zero staleness (nothing to
sync — a predicate reads live role-assignment/relationship state), but every check re-derives the
answer from relationships at request time rather than reading a precomputed row, so cost moves from
storage/sync into per-check query cost (typically one or two indexed lookups per predicate,
memoizable per-request).

## django-guardian: rows per object, and why FLS is hitting its edges

Guardian's model is deliberately row-based: `assign_perm(perm, user, obj)` writes a
`UserObjectPermission` row scoped to that object's content type, and `get_objects_for_user` filters
a queryset to objects with such a row — which is exactly how `cohorts_visible_to`-style helpers stay
consistent with single-object `has_perm` checks *when the row exists*. But guardian has two
structural constraints FLS has already hit: `assign_perm`/`get_perms` require the permission's
`content_type` to match the target object's content type, so a role held on an `Organisation` can
only ever carry `freedom_ls_organisations.*` permissions once synced — there is no built-in notion
of "this permission, though granted on the organisation, should be readable when checking a cohort
inside it"; and guardian's backend returns `False` for any permission check made with `obj=None`,
so "may create a cohort" (no cohort exists) cannot be asked of guardian at all — it can only be
asked of some existing object, which is why FLS's plan is to ask the *organisation* the question
instead of asking nothing. [Check object permissions docs](https://django-guardian.readthedocs.io/en/v1.0/userguide/check.html), [GitHub issue #766: permissions for all objects of a type via content types](https://github.com/django-guardian/django-guardian/issues/766), [Overcoming Django's Object-Based Permissions Challenge](https://medium.com/@hamzaashes/overcoming-djangos-object-based-permissions-challenge-8eaa0ba8bd53)

The common workaround pattern (visible in the GitHub issue thread and several guardian-adjacent
blog posts) is exactly option (A) below: sync guardian rows onto every descendant object whenever
a container-level role is assigned, and re-sync onto every new child object at creation time, so
that guardian's own content-type-scoped row-based model is satisfied by materializing one row per
(user, permission, descendant object) rather than trying to make guardian understand hierarchy.
Nobody found a way to make guardian itself inheritance-aware; the workarounds all materialize rows.

## django-role-permissions: roles as named permission bundles, no scoping primitive

django-role-permissions (Vinta Software) layers named roles with a fixed permission set on top of
Django's `Group`/`Permission` tables — closer to FLS's own `Role`/`SiteRolesConfig` shape than to
guardian. It supports `has_object_permission(perm, user, obj)` for object-level checks, but the
object-permission story is left to the calling code to implement per permission; the library itself
has no concept of container→child inheritance or scope objects. It is evidence that a
"named role → bundle of capability strings" layer is a reasonable core (FLS already has this in
`roles.py`), but it doesn't solve the container-inheritance problem either — that has to be layered
on top, same as FLS needs to do. [django-role-permissions docs](https://django-role-permissions.readthedocs.io/), [GitHub](https://github.com/vintasoftware/django-role-permissions)

## django-scopes: tenant-scoping querysets, not a permission model

django-scopes solves a different but related problem — making it hard to *forget* a tenant filter,
via `with scope(site=current_site): Model.objects.all()`, backed by a manager that raises if used
without an active scope. It's relevant to FLS only as a pattern for "list filtering can't
accidentally skip the scope" (it enforces that every query passes through the scope, at the ORM
manager level, rather than trusting each view to remember to call `cohorts_visible_to`). It says
nothing about container inheritance of capabilities. [django-scopes README](https://github.com/raphaelm/django-scopes), [pretix: bringing scoping to multi-tenant Django](https://behind.pretix.eu/2019/06/17/scopes/)

## Zanzibar / OpenFGA: relation inheritance as the native primitive

Google Zanzibar's model (and OpenFGA, its open-source implementation) stores facts as relationship
tuples `object#relation@user` (e.g. `organisation:acme#staff@user:alice`) and defines relations in
terms of other relations, so a schema can say a cohort's `manage` relation is satisfied by
`organisation#staff from parent` — "check the cohort's parent-organisation tuple, then check
whether the user has `staff` there" — which is a **tuple-to-userset** rewrite rule, evaluated at
check time, not materialized as a new tuple. This is structurally the same idea as Moodle's context
walk and Canvas's account chain, generalized to an arbitrary relation graph rather than a fixed
container tree, and it is the one model among these that has both a first-class "does X have
relation R on Y" check *and* a first-class "list all Y such that X has relation R" primitive
(`ListObjects`/`ListUsers` in OpenFGA) defined over the same rewrite rules — so list filtering is
provably consistent with the single check by construction, not by convention. [Object to Object Relationships](https://openfga.dev/docs/modeling/building-blocks/object-to-object-relationships), [Authorization Through Organization Context](https://openfga.dev/docs/modeling/organization-context-authorization), [FGA 2026 Implementation Guide](https://guptadeepak.com/ciam-compass/guides/fine-grained-authorization-fga/)

**Creation-in-container** in Zanzibar/OpenFGA is checked the same way: "may create a cohort in this
organisation" is `check(user, "create_cohort", organisation:acme)` — always asked of the parent,
since the child tuple doesn't exist yet, identical to Moodle/Canvas.

**Cost**: no row explosion for inherited relations (the rewrite rule is evaluated, not
materialized), no staleness on child creation (a new cohort automatically has an
"organisation#staff implies cohort#manage" edge the moment its parent-link tuple is written — one
tuple, not one row per permission per user). Query cost is a graph walk per check, which OpenFGA
optimizes with a resolution-depth-bounded BFS and caching; for FLS's shallow tree (site → org →
cohort, 2-3 hops) this is a non-issue, but it does mean every check is a live graph evaluation
rather than a row lookup — the same trade-off as django-rules, at bigger scale with a purpose-built
engine instead of Python predicates.

## The general Django pattern: capability layer vs. row expansion

Stripped of vendor specifics, the field reduces to two shapes:

- **Row expansion**: materialize permission rows onto every object a container-role should reach —
  guardian's `assign_perm` called on each descendant, or Zanzibar tuples pre-computed and stored
  instead of evaluated. Reads are then a plain indexed lookup (fast, familiar, plugs straight into
  `get_objects_for_user`-style list filtering). Writes must materialize on both role
  assignment/removal *and* on every new child object's creation, or the sync goes stale — this is a
  correctness-critical hook that has to live wherever `Cohort.objects.create()` is called, forever,
  for every future object type inheriting from a container role.
- **Capability layer**: one function `can(user, capability, scope_obj)` (django-rules's shape,
  Moodle/Canvas's `has_capability(cap, context)` shape, Zanzevar's `Check` shape) that walks
  role-assignment → scope-object relationships live, with no rows per descendant. Reads cost a
  small live computation instead of a row lookup (usually one or two queries, cacheable per
  request); nothing to keep in sync on child creation, because the child is covered the instant it
  is linked to its parent. List filtering needs its own explicit companion (a queryset-returning
  twin of `can`, verified against it by test) rather than getting it for free from
  `get_objects_for_user` — which is exactly what FLS's `organisations_accessible_to`,
  `cohorts_visible_to`, `learners_visible_to` already are, and exactly what the roadmap's planned
  matrix test is for.

## Implications for FLS

FLS's `Role`/`SiteRolesConfig`/`ObjectRoleAssignment`/`SiteRoleAssignment` layer is already a named
role → capability-string bundle (django-role-permissions's shape), sitting on top of guardian for
enforcement. The choice the spec has to make is what enforces the string once the role is on a
container: guardian rows on every descendant, or a capability function that consults the role
assignment table directly.

**(A) Extend the guardian sync to child objects.**
On `assign_object_role(user, organisation, "organisation_staff")`, also `assign_perm` for every
existing cohort in that organisation (and every future permission FLS adds must be re-classified:
does it belong to the org's content type or a child's?). On `Cohort.objects.create(organisation=...)`,
walk up to find every user with an org-level role that should reach the new cohort and call
`assign_perm` for each. `learner_management.*`, `form_engine.*` etc. permissions now get real
content-type-matched guardian rows on cohorts/learners, so `get_objects_for_user`-based helpers keep
working unmodified, and `has_perm(perm, obj)` at the panel-framework hook is a plain guardian call —
consistent with how the framework currently expects to ask.
Costs: row count is O(users × roles × descendant objects) — every organisation_staff grant writes a
row per existing cohort and must be re-run per new cohort; a cohort created without going through
the one blessed creation path (a fixture, an admin action, a future bulk import) silently has no
rows and the org staff who should manage it can't, until something re-runs the sync — this is
exactly the "sync staleness when objects are created" failure mode, and it recurs for every new
child-of-a-container model FLS adds (a learner is a child of a cohort which is a child of an
organisation — does a two-level walk get run on every learner creation too?). It also still can't
answer creation-in-container by itself: `add_cohort` at the model level is still an objectless
check, so a small carve-out (ask the question of the organisation, as spec 1's hook already plans)
is needed regardless of which side is chosen — (A) does not remove that carve-out, it only helps
list/detail checks on existing children.
A downstream `FREEDOMLS_PERMISSIONS_MODULES` override that redefines what `organisation_staff`
means (e.g. adds `learner_management.add_learner`) keeps working under (A) only if the override
also triggers a re-sync across every existing descendant object for every affected user — the sync
function has to be re-run project-wide whenever role definitions change, not just at
assign/remove-role time, or objects created before the override was deployed keep the old
permission set until touched again.

**(B) A capability layer over role assignments.**
Add `can(user, capability: str, scope_obj: Model) -> bool` that, given a cohort, looks up active
`ObjectRoleAssignment`s on that cohort *and* walks to its organisation for `ObjectRoleAssignment`s
there (and to the site for `SiteRoleAssignment`s), resolving each role's permission set against the
requested capability without ever writing a guardian row for the descendant. `add_cohort` on an
organisation becomes `can(user, "learner_management.add_cohort", organisation)` — no carve-out
needed, because the layer was never restricted to objectless-check-denies-everything; it simply
takes the container as `scope_obj` when the child doesn't exist. Guardian still enforces content
permissions where an object genuinely carries its own row (e.g. per-cohort `view_cohort` for
instructor/ta, which already works because instructor/ta *are* assigned directly on the cohort);
the capability layer is only needed for the container→child direction that guardian's content-type
filter blocks.
`organisations_accessible_to`/`cohorts_visible_to`/`learners_visible_to` become the queryset-shaped
twin of `can`, built from the same role-assignment tables, and the matrix test the spec already
plans is the mechanism that keeps `can` and the `_visible_to` helpers from drifting apart — same
discipline django-rules projects need, but FLS is already committed to writing that test regardless.
Costs: a live walk of 2-3 hops (cohort → organisation → site) per check instead of a row lookup —
negligible at FLS's scale and shape, cacheable per-request the way guardian's own permission cache
already is. No sync step exists to go stale: a cohort created under an organisation is covered by
every org-level role the instant its `organisation_id` foreign key is set, with no second write.
A downstream `FREEDOMLS_PERMISSIONS_MODULES` override that changes what `organisation_staff` means
takes effect immediately for every object, existing or future, the next time `can` is called,
because `can` reads the role config live rather than reading materialized rows written under the
old config — no re-sync pass, no window where old and new grants coexist.

**Recommendation (marked as such): (B), a capability layer.**
It removes the objectless-check problem at its root rather than working around it per call site, it
does not add a hierarchy-walking sync obligation to every future child-of-a-container model FLS
introduces (learners under cohorts under organisations, and whatever comes after), and it makes a
downstream role-definition override behave correctly without a re-sync sweep — matching the spec's
explicit requirement that `FREEDOMLS_PERMISSIONS_MODULES` overrides keep working. Guardian is not
removed: it stays as-is for permissions that are genuinely assigned on the object being checked
(instructor/ta on a cohort, `view_cohort`), where its content-type-matched row model is already
correct. The capability layer is added specifically for the organisation-staff-reaches-into-cohorts
direction guardian's content-type filter blocks, and for every objectless creation check the
framework's spec-1 hook needs to ask of a container. The cost is that `cohorts_visible_to` and
`can` must be kept in lockstep by the matrix test rather than getting that guarantee for free from
`get_objects_for_user` — a real cost, but one the spec's own test plan already pays for.

status: ok
