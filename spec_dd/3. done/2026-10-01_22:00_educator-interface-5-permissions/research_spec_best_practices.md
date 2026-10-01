# Research: best-practice gaps the spec still needs settled

For educator-interface-5-permissions. Covers five implementation-detail questions the other five
research files don't: the role-key rename migration, the organisation-association model shape, the
capability-check function's signature and integration point, the last-admin row-lock pattern, and
what happens to guardian sync for container roles. Each section ends with a recommendation.

## 1. Renaming role keys stored as plain strings

`SiteRoleAssignment.role` / `ObjectRoleAssignment.role` / `SystemRoleAssignment.role` are bare
`CharField(max_length=50)`, not `choices=`, so Django has no built-in validation to update — the
rename is entirely a data-migration and application-code exercise.

**Migration shape.** Django's own docs are explicit that a data migration referencing a model must
use `apps.get_model()` (the historical model as it existed at that migration's point in the graph),
never the real imported model, because the real model may have fields the migration predates or
postdates. [Django: Data migrations](https://docs.djangoproject.com/en/6.0/topics/migrations/#data-migrations),
[Django: Historical models](https://docs.djangoproject.com/en/6.0/topics/migrations/#historical-models).
The standard pattern for a value rename:

```python
OLD_TO_NEW = {"instructor": "cohort_admin", "ta": "cohort_viewer", "organisation_staff": "organisation_admin"}

def rename_forward(apps, schema_editor):
    ObjectRoleAssignment = apps.get_model("role_based_permissions", "ObjectRoleAssignment")
    for old, new in OLD_TO_NEW.items():
        ObjectRoleAssignment.objects.filter(role=old).update(role=new)
    # repeat for SiteRoleAssignment; SystemRoleAssignment is untouched (its three roles don't rename)

def rename_reverse(apps, schema_editor):
    ObjectRoleAssignment = apps.get_model("role_based_permissions", "ObjectRoleAssignment")
    for old, new in OLD_TO_NEW.items():
        ObjectRoleAssignment.objects.filter(role=new).update(role=old)

class Migration(migrations.Migration):
    operations = [migrations.RunPython(rename_forward, rename_reverse)]
```

**Idempotence.** `.update(role=new)` filtered `role=old` is naturally idempotent: running it twice
is a no-op the second time because no rows still have `role=old`. This is the property to require
explicitly in the spec's migration description — a `.update()` keyed on the *old* value, not a
blind bulk-set, so a partial re-run (deploy retried after a failed migrate) can't double-map or
crash. [Better Simple: Django migrations and your database](https://www.better-simple.com/django/2023/06/03/django-migrations-and-your-database/)
discusses treating each `RunPython` step as re-runnable rather than assuming `migrate` only ever
runs once cleanly.

**Reverse function.** Provide one (`rename_reverse` above) even though the spec doesn't plan to roll
back in production — Django's migration docs recommend it so `migrate <app> <previous>` and test
suites that exercise reversibility (e.g. `django-test-migrations`) don't hard-fail on this
migration specifically, and so a bad deploy has a real rollback path rather than "restore from
backup." A `RunPython` with no reverse silently blocks every migration *before* it in the same
`migrate --fake` / rollback chain.

**Rows with unknown or custom keys.** The `.filter(role=old).update(role=new)` pattern only touches
rows whose value is exactly one of the three old keys — it leaves alone any row whose `role` is
something else entirely (a downstream custom role name that doesn't collide with the four FLS
names). That's correct and requires no special-casing: the migration's job is "rename these three
literal strings," not "understand every possible role a downstream project invented."

**Downstream custom roles that inherit an old key.** This idea.md already commits to "upgrade notes
give the mapping" for configs like `senior_ta` with `inherits: "ta"`. Two additional things worth
settling in the spec text:

- **A startup-time fail-loud check**, not silent breakage. Django's own precedent is the system
  checks framework (`django.core.checks`) — e.g. `fields.E008` fires at `manage.py check` /
  server-start time when a `CharField`'s `choices`/`default` don't line up
  ([Django ticket #25480](https://code.djangoproject.com/ticket/25480)). FLS's role config loader
  already validates `inherits` references at config-load time (implied by `check_role_name_in_config`
  raising `ValueError` for an unknown role); extend that same validation to run as a registered
  Django system check (`@register()` in `role_based_permissions/checks.py`) so a downstream site
  whose `FREEDOMLS_PERMISSIONS_MODULES` override still says `inherits: "ta"` gets a `manage.py check`
  error naming the old key and the new one, not a `KeyError` the first time someone loads the role
  config at request time. This mirrors how Django itself, and libraries like DRF, prefer a
  registered system check over a runtime `KeyError` for a static misconfiguration.
- **Deprecation alias vs hard break.** The spec should decide, don't leave it implicit: because
  `role` is a bare string (not an enum Django enforces), the *cheapest* option compatible with the
  system-check idea is a hard break with a one-release deprecation note (upgrade notes + the system
  check catching stale configs at deploy time) rather than a code-level alias table that maps
  `"ta"` to `"cohort_viewer"` forever — an alias table means every future `role in {...}` comparison
  in the codebase has two ways to spell the same role, which is exactly the kind of drift the rename
  is meant to remove. Recommend: hard break, with the system check as the safety net, matching how
  Django itself handles removed/renamed settings (a `RemovedInDjangoNN` check/warning naming the old
  and new name, not a silent alias).

## 2. Membership-with-`is_active` design for the organisation association

**Prior art, condensed** (full membership-lifecycle detail already summarized informally in
`idea.md` §"Organisation association"; this is the schema-level comparison):

- **GitHub org membership**: state machine `pending → active`, plus a separate removal (not a third
  "suspended" state) — leaving/removal deletes the membership row rather than flagging it inactive;
  re-joining creates a new membership. [GitHub: Managing membership](https://docs.github.com/en/organizations/managing-membership-in-your-organization),
  [GitHub Orgs API](https://docs.github.com/en/rest/orgs/members).
- **Slack workspace deactivation**: the *user account*, not a separate membership row, carries the
  deactivated flag; deactivating signs the user out everywhere and pulls them from every channel,
  but the historical fact "was a member" and their messages/files are retained, not deleted — the
  action is reversible by reactivating the same account. [Slack: Deactivate a member's account](https://slack.com/help/articles/204475027-Deactivate-a-members-account).
- **Moodle course enrolment**: `Active | Suspended | Not current`, stored as a status field on the
  enrolment row itself (`user_enrolments.status`), not the account — suspending blocks course access
  but leaves every other row (grades, submissions, group membership) untouched, and reactivating
  needs no re-setup. [Moodle: Enrolment FAQ](https://docs.moodle.org/502/en/Enrolment_FAQ),
  [Moodle: suspending an enrolment](https://moodle.org/mod/forum/discuss.php?d=227213).
- **Canvas enrollment `workflow_state`**: `active | invited | inactive | completed | rejected |
  deleted` on the `Enrollment` row — `inactive` (admin-initiated, reversible, hides the person from
  grading/rosters but keeps grades) is a distinct state from `deleted` (terminal, removed), which is
  the same active/deactivated-vs-deleted distinction FLS needs for `Educator`.

**Read for FLS's `Educator(user, organisation, is_active)`.** The pattern that matches every system
above except GitHub's binary membership is: **soft-deactivation on the association row, not
deletion, and not a flag on `User`.** GitHub's delete-on-removal doesn't fit FLS because the whole
point of the association (idea.md line: "Deactivating the association switches off every grant...
Reactivating it restores exactly what they had") is round-trippable without re-granting — that's
Moodle's `suspended` / Canvas's `inactive` shape, a status on the join row, not Slack's
account-level flag (FLS's `User` is site-wide and shared across organisations; deactivating the
person, not the association, would deactivate them everywhere, which is wrong when a person belongs
to two organisations and leaves only one).

**Uniqueness constraint.** One row per `(site, user, organisation)`, mirroring `Learner`'s own
`unique_learner_per_organisation` constraint exactly — `UniqueConstraint(fields=["site", "user",
"organisation"], name="unique_educator_per_organisation")`. Do not model repeated leave/rejoin
cycles as multiple rows (no GitHub-style delete+recreate): toggle `is_active` on the one row, so
there's a single stable foreign key for every `ObjectRoleAssignment`/audit-log entry that ever
referenced "this educator in this organisation" to point at, and no ambiguity about "which of the
two rows for this (user, org) pair is current."

**Backfill migration for existing grant holders.** idea.md already commits to this
("Existing `organisation_staff`, `instructor` and `ta` grants must keep working... current holders
get an association"). The backfill is a data migration run alongside the role-rename migration
(§1), in dependency order after it (or independently, since it reads `role` values by whichever
name is current at that point in the migration graph — using the *post-rename* names avoids a
double dependency on transitional state):

```python
def backfill_forward(apps, schema_editor):
    ObjectRoleAssignment = apps.get_model("role_based_permissions", "ObjectRoleAssignment")
    Educator = apps.get_model("<app>", "Educator")
    Organisation = apps.get_model("freedom_ls_organisations", "Organisation")
    Cohort = apps.get_model("learner_management", "Cohort")
    org_ct = ContentType.objects.get_for_model(Organisation)
    cohort_ct = ContentType.objects.get_for_model(Cohort)
    # organisation_admin grants: object_id is an Organisation pk directly
    for row in ObjectRoleAssignment.objects.filter(content_type=org_ct, role="organisation_admin", is_active=True):
        Educator.objects.get_or_create(user_id=row.user_id, organisation_id=row.object_id, defaults={"is_active": True})
    # cohort_admin/cohort_viewer grants: walk cohort -> organisation
    for row in ObjectRoleAssignment.objects.filter(content_type=cohort_ct, role__in=["cohort_admin", "cohort_viewer"], is_active=True):
        cohort = Cohort.objects.get(pk=row.object_id)
        Educator.objects.get_or_create(user_id=row.user_id, organisation_id=cohort.organisation_id, defaults={"is_active": True})
```

Using historical models here means importing `ContentType.objects.get_for_model` on the *historical*
`ContentType` model too (`apps.get_model("contenttypes", "ContentType")`), a common gotcha the
Django docs flag explicitly for content-type-bearing migrations
([Django: Historical models](https://docs.djangoproject.com/en/6.0/topics/migrations/#historical-models)
— "content types... are not managed by migrations" and need `RunPython.noop`-safe handling or the
real `ContentType` manager, since content types are created outside the migration graph).
`get_or_create` makes the backfill idempotent against a re-run (matches §1's idempotence
requirement) and against a person who already holds both an organisation-level and a cohort-level
grant in the same organisation (one `Educator` row either way).

**Relation to `Learner` for a person who is both.** Two separate models, not one row with a "type"
discriminator:

- `Learner` already exists with its own lifecycle (`ensure_learner` reactivation semantics,
  `CohortMembership`/`LearnerCourseRegistration` hanging off it) that has nothing to do with
  educator grants — a `Learner` row is "enrolled for content," an `Educator` row is "administers."
  Collapsing them into one polymorphic membership model with a `role_type` column would mean every
  enrolment-side query (`CohortMembership.learner`, `LearnerCourseRegistration.learner`) needs a
  `WHERE type='learner'` filter it doesn't need today, and every future field one side needs but the
  other doesn't (e.g. a field specific to enrolment) becomes nullable noise on rows that are really
  educator rows.
- The two are independent per organisation: a person can be a `Learner` in org A and an `Educator`
  in org B, or both in the same org (a TA who is also enrolled as a learner in a course the org
  runs) — a `UniqueConstraint` per model on `(site, user, organisation)` handles that correctly
  without cross-model coordination; a single combined model would need a *different* uniqueness
  rule ("one row per (user, org, type)") that's strictly more complex for no benefit, since nothing
  in the spec needs to query "every association a person has with an organisation regardless of
  kind" as a single table scan.
- Precedent: Moodle keeps `mdl_user_enrolments` (learner-side) and `mdl_role_assignments`
  (staff/teacher-side capability grants) as separate tables joined only by `userid` — it does not
  unify "enrolled" and "has a role" into one row, for the same separation-of-concerns reason.

**Recommendation**: `Educator(user, organisation, is_active)` as its own model (name/app TBD by the
spec, per idea.md's "open until the spec"), `UniqueConstraint` on `(site, user, organisation)`
identical in shape to `Learner`'s, soft-deactivation via `is_active` (never delete/recreate on
leave-rejoin), independent of `Learner` with no shared base beyond what both already get from
`SiteAwareModel`.

## 3. Capability-check function design

**Signature.** Match the shape every comparable system and django-rules converge on
(`research_scoped_capability_models.md` already lays out the Moodle/Canvas/Zanzibar/django-rules
precedent for this — this section is about the Django-specific calling convention, not repeating
that comparison):

```python
def can(user: User, capability: str, scope: Model) -> bool: ...
def objects_with_capability(user: User, capability: str, model: type[ModelT]) -> QuerySet[ModelT]: ...
```

`(user, capability, scope_obj)` — object last — matches Django's own `has_perm(perm, obj=None)`
convention and django-rules' `predicate(user, obj)`
([django-rules predicates.py](https://github.com/dfunckt/django-rules/blob/master/rules/predicates.py)),
so it reads the same as the framework calls FLS already makes, and a spec-1 hook that currently
calls `request.user.has_perm(perm, obj)` needs only its callee swapped, not its argument order
re-learned.

**Capability identifiers: strings, not `StrEnum`.** Enums are the generic best practice for a fixed,
closed set of constants
([Real Python: Build Enumerations of Constants](https://realpython.com/python-enum/)), but FLS's
own capability strings are explicitly *not* a fixed closed set defined once in this codebase — they
are `"applabel.codename"` Django permission strings (`"freedom_ls_learner_management.add_cohort"`),
extensible by every future spec (idea.md: "A capability that does not exist yet has no row. When a
later spec builds one, that spec adds the row and the check together") and by downstream
`FREEDOMLS_PERMISSIONS_MODULES` overrides that FLS cannot enumerate at package-build time. A
`StrEnum` requires a closed, centrally-maintained member list — exactly the coupling the roadmap is
trying to avoid by keeping role definitions data-driven and per-site overridable. Keep capability
identifiers as plain strings in Django's own `app_label.codename` shape (this is also what
`get_role_config()[role].permissions` already stores as a `frozenset[str]`, so `can()` needs no
translation layer between the role config and the check function). Where a *fixed* set does exist
(e.g. the four role keys, or the finite list of denial shapes), those are reasonable enum
candidates — the distinction is closed vs. open sets, not "identifiers are always enums."

**Per-request caching and invalidation.** `role_based_permissions/utils.py` already has one
process-lifetime cache (`_get_valid_codenames_for_content_type`, `@lru_cache`, explicitly
documented as "cached to avoid repeated DB queries," cleared by `clear_permission_cache()` in
tests) — that pattern (module-level `lru_cache` + an explicit `_clear` function tests call) is the
existing convention to extend, but role *assignments* must not use a process-lifetime cache the way
codename-to-content-type mappings do, because assignments change within a process's lifetime
(a grant added mid-request-cycle by a concurrent request must not be masked by a stale cache for
other users, though it's fine — and expected, matching the "Entra ID/GitHub re-check per request"
row in `research_role_assignment_rules.md` — for the *same* request to see a stable answer
throughout). The right scope is **per-request**, not per-process: either (a) a small
`functools.lru_cache`-wrapped helper rebuilt fresh via Django's connection-per-request lifecycle
(simplest: cache on the `user` object itself as an instance attribute set at first call, the same
trick `django.contrib.auth`'s own `ModelBackend` uses internally for `_perm_cache`/`_user_perm_cache`
— [Django ticket #26514: `refresh_from_db()` doesn't clear permission cache](https://code.djangoproject.com/ticket/26514)
documents exactly this pattern and its one sharp edge: the cache must be invalidated whenever a
view mutates role assignments mid-request, e.g. right after `assign_object_role`/`remove_object_role`
in the same request that calls them), or (b) `django-request-cache`'s middleware-scoped cache
(third-party, purpose-built for "cache per request, dropped at request end,"
[django-request-cache](https://pypi.org/project/django-request-cache/)) if FLS prefers not to hang
private attributes on `User`. Recommend (a): a private cache attribute keyed by
`(capability, scope-object identity)` on the `user` instance, invalidated explicitly by
`assign_object_role`/`remove_object_role`/`assign_site_role`/`remove_site_role` calling a
`clear_capability_cache(user)` the same way `sync_user_object_permissions` already runs inline
after every assignment change — no new caching framework, same discipline as Django's own
authentication backend.

**Avoiding N+1 when checking many rows.** The queryset twin (`objects_with_capability` /
`_visible_to`-style helpers) is exactly the N+1 answer: a list view must never call `can(user, cap,
row)` once per row in a loop (each call re-fetching `ObjectRoleAssignment`s and re-walking to the
organisation), it must build the filtered queryset in one shot — annotate/filter on
`ObjectRoleAssignment`/`Educator`/`SiteRoleAssignment` joins, matching how guardian's own
`get_objects_for_user` avoids N+1 today. This is why idea.md and
`research_scoped_capability_models.md` both insist `can()` and the `_visible_to` helpers share a
single primitive rather than the list helper being implemented as "filter in Python by calling
`can()` per row" — that shared-primitive requirement *is* the N+1 answer, not a separate concern.

**Shared primitive, concretely.** Both `can(user, cap, obj)` and `objects_with_capability(user,
cap, Model)` should be built from one private function that returns the *set of scope-object
identities* (organisation ids, cohort ids, "all" for site_admin) a user's role assignments cover for
a capability — `can()` checks membership of one id in that set (or its container-walk), the queryset
twin filters `Model.objects.filter(pk__in=that_set)` (or the organisation-walk equivalent). This
mirrors Moodle/Canvas/Zanzibar's "one function, two callers" shape already recommended in
`research_scoped_capability_models.md` §"Implications for FLS" — restated here specifically as a
Django-implementation instruction: one private set-returning function, two thin public callers, so
there is only one place a future capability's container-walk logic can be wrong.

**django-rules integration vs. standalone function — recommend standalone.** django-rules'
authorization backend lets `user.has_perm(perm, obj)` route to a predicate
([django-rules README](https://github.com/dfunckt/django-rules)), which would let the spec-1 hook
keep calling `has_perm` unchanged. But FLS already has a bespoke role-config/`Role`/`SiteRolesConfig`
layer that isn't django-rules' predicate-registration model, and `research_scoped_capability_models.md`
already recommends *not* adopting a new permission library, only a capability function layered over
the existing role-assignment tables. Wiring that function in through `has_perm`/an authentication
backend adds an indirection (Django's own backend-resolution order, `PermissionDenied` short-circuit
semantics, and guardian's already-registered backend in `AUTHENTICATION_BACKENDS`) for no gain, since
nothing outside the spec-1 hook calls `has_perm` today per `research_current_permission_machinery.md`.
Recommend a **standalone module-level function** (`can`/`objects_with_capability`), imported
directly by the spec-1 hook and by views, not registered as an auth backend — simpler call graph,
no interaction with guardian's own backend or Django's `ModelBackend`, and no risk of a capability
check silently no-op'ing because backend resolution order put guardian's `False`-for-`obj=None`
answer first.

## 4. Row-lock pattern for "refuse removing the last admin," and self-grant/self-removal

`research_role_assignment_rules.md` already flags that `remove_site_role` today does a bare
`.filter().update()` with no count check and no lock at all — this section is the concrete pattern
to close that gap.

**Which rows to lock.** Lock the *candidate admin population for the scope being modified*, not the
row being removed: `SELECT ... FOR UPDATE` over
`SiteRoleAssignment.objects.select_for_update().filter(site=site, role="site_admin", is_active=True)`
(or the organisation-scoped `ObjectRoleAssignment` equivalent for `organisation_admin`) — every row
in that queryset, not just the one being deactivated, because the race being closed is "two
concurrent removals of two different admins in the same scope, each individually leaving one admin
behind, executing concurrently" as much as "remove the actual last one." Locking only the target
row doesn't prevent that race since the two transactions lock two different rows and both pass their
count check against a pre-lock read.

```python
from django.db import transaction

@transaction.atomic
def remove_site_role(user, role, site=None, removed_by=None):
    ...
    if role == "site_admin":
        admins = (
            SiteRoleAssignment.objects.select_for_update()
            .filter(site=site, role="site_admin", is_active=True)
        )
        remaining = admins.exclude(user=user).count()
        if remaining == 0:
            raise LastAdminError("Cannot remove the last site_admin on this site.")
    SiteRoleAssignment.objects.filter(user=user, site=site, role=role).update(
        is_active=False, updated_at=timezone.now()
    )
```

`select_for_update()` inside `transaction.atomic()` is required together — the lock is only held
for the transaction's lifetime, and `select_for_update()` outside `atomic()` raises
`TransactionManagementError` in Django. Two concurrent calls both attempting to remove different
admins in the same scope serialize on this queryset: the second transaction's `select_for_update()`
blocks until the first commits (or rolls back on the raised error), so it recomputes `remaining`
against post-commit state and correctly sees zero left rather than racing against a stale count.
[Django docs: `select_for_update()`](https://docs.djangoproject.com/en/6.0/ref/models/querysets/#select-for-update),
[dev.to: Mastering select_for_update in Django](https://dev.to/karaa1122/mastering-selectforupdate-in-django-prevent-race-conditions-the-right-way-4l56),
[Medium: Django's atomic decorator doesn't prevent race conditions](https://medium.com/@anas-issath/djangos-atomic-decorator-didn-t-prevent-my-race-condition-and-the-docs-never-warned-me-58a98177cb9e)
— this source is worth citing directly in the spec because its whole point is the exact mistake
FLS's current code makes: wrapping a check-then-write in `transaction.atomic()` alone, with no
`select_for_update()`, does not prevent the race (Postgres's default Read Committed isolation lets
both transactions read the same "2 admins remain" snapshot before either writes).

**Extending to `organisation_admin`** (per `research_role_assignment_rules.md`'s suggested default
of applying the same rule): lock `ObjectRoleAssignment.objects.select_for_update().filter(
content_type=org_ct, object_id=str(organisation.pk), role="organisation_admin", is_active=True)` —
same shape, scoped to the organisation's content-type+object_id pair instead of a site.

**Refusing self-grant/self-removal.** idea.md already settles "nobody assigns or removes their own
grants" as an unconditional rule (not "unless they're not the last one") — this needs no lock at all,
just an equality check before any query runs: `if assigned_by == user: raise SelfAssignmentError(...)`
at the top of `assign_object_role`/`remove_object_role`/`assign_site_role`/`remove_site_role`,
evaluated before the last-admin check so a self-removal attempt is rejected for the self-removal
reason even when the actor isn't the last admin (clearer error message, and avoids taking the lock
at all for a request that's going to be refused regardless).

## 5. Guardian role-sync for container roles, once the capability layer exists

idea.md's "open until the spec" already flags this and states one certainty: "site_admin's cohort
strings stop pretending to do anything." Given the §3 recommendation (a standalone `can()` function
consulted directly by the spec-1 hook, not routed through `has_perm`), guardian's role sync
(`sync_user_object_permissions` in `utils.py`) has a narrower job left once `can()` exists:

- **Keep it, restricted to direct-object grants.** `cohort_admin`/`cohort_viewer` (today's
  `instructor`/`ta`) are assigned directly on the `Cohort` they administer — that's guardian's
  native shape (a row on the object being checked, content-type matched) and nothing about the
  capability layer changes that; `view_cohort` etc. for those two roles can keep syncing exactly as
  `sync_user_object_permissions` does today. This matches `research_scoped_capability_models.md`'s
  recommendation (B) explicitly: "guardian is not removed... it stays as-is for permissions that are
  genuinely assigned on the object being checked."
- **Drop the sync for `organisation_admin`/`site_admin`'s cross-content-type strings.** Once `can()`
  answers "may this org admin add a cohort in this organisation" and "may this site admin manage
  this cohort" directly from role assignments + the organisation walk, there is nothing left for
  guardian rows on those roles to do — they were only ever a workaround for guardian's content-type
  filter (idea.md line 18: "site_admin's four cohort permissions are dropped every time they sync
  onto a `Site`"), and the capability layer removes the reason those rows were attempted in the
  first place. Syncing them anyway is dead weight: every `assign_object_role`/`assign_site_role`
  call still pays the sync's query cost for permissions that get silently filtered out
  (`_filter_perms_for_content_type`) and never consulted, since `can()` doesn't read guardian for
  the container→child direction.
- **Migration concern: stale guardian rows.** Whatever direct-object guardian rows exist today for
  `instructor`/`ta` on cohorts (soon `cohort_admin`/`cohort_viewer`) stay correct and don't need
  cleanup — they're exactly the rows §5's "keep" case wants to keep. The rows worth auditing for
  staleness are any `UserObjectPermission` rows that synced onto a *Site* object for `site_admin`
  under the current code (idea.md documents these as already-useless, silently dropped by the
  content-type filter — meaning in practice there likely are none, since `organisation_staff`/
  `site_admin`'s permissions never had a matching content type to survive the filter). Worth a
  one-off data migration or management-command check (`UserObjectPermission.objects.filter(
  content_type=site_ct)` or `content_type=org_ct)`) that asserts this is actually empty before
  relying on "there's nothing to clean up" as an assumption, rather than asserting it in the spec
  without checking — a stale row from an earlier version of the sync logic (before the content-type
  filter was added) could still be sitting in the table with no code path left that reads it, and a
  spec-1 hook that changes *how* it decides `has_perm` (routing to `can()` rather than guardian
  directly) is the right moment to also confirm guardian carries nothing extra that a downstream
  `get_objects_for_user` call elsewhere in the codebase might still (incorrectly) rely on.

## Sources

- [Django: Data migrations](https://docs.djangoproject.com/en/6.0/topics/migrations/#data-migrations)
- [Django: Historical models](https://docs.djangoproject.com/en/6.0/topics/migrations/#historical-models)
- [Django ticket #25480: CharField + choices + default = fields.E008](https://code.djangoproject.com/ticket/25480)
- [Better Simple: Django migrations and your database](https://www.better-simple.com/django/2023/06/03/django-migrations-and-your-database/)
- [GitHub: Managing membership in your organization](https://docs.github.com/en/organizations/managing-membership-in-your-organization)
- [GitHub: REST API endpoints for organization members](https://docs.github.com/en/rest/orgs/members)
- [Slack: Deactivate a member's account](https://slack.com/help/articles/204475027-Deactivate-a-members-account)
- [Moodle: Enrolment FAQ](https://docs.moodle.org/502/en/Enrolment_FAQ)
- [Moodle: suspending an enrollment (forum)](https://moodle.org/mod/forum/discuss.php?d=227213)
- [Real Python: Build Enumerations of Constants With Python's Enum](https://realpython.com/python-enum/)
- [django-rules README](https://github.com/dfunckt/django-rules)
- [django-rules predicates.py](https://github.com/dfunckt/django-rules/blob/master/rules/predicates.py)
- [Django ticket #26514: User.refresh_from_db() does not clear permission cache](https://code.djangoproject.com/ticket/26514)
- [django-request-cache](https://pypi.org/project/django-request-cache/)
- [Django docs: select_for_update()](https://docs.djangoproject.com/en/6.0/ref/models/querysets/#select-for-update)
- [dev.to: Mastering select_for_update in Django](https://dev.to/karaa1122/mastering-selectforupdate-in-django-prevent-race-conditions-the-right-way-4l56)
- [Medium: Django's atomic decorator doesn't prevent race conditions](https://medium.com/@anas-issath/djangos-atomic-decorator-didn-t-prevent-my-race-condition-and-the-docs-never-warned-me-58a98177cb9e)

## Code read for this research

- `freedom_ls/role_based_permissions/roles.py` — current `BASE_ROLES` definitions (`site_admin`,
  `instructor`, `ta`, `organisation_staff` and their permission sets).
- `freedom_ls/role_based_permissions/models.py` — `SystemRoleAssignment`, `SiteRoleAssignment`,
  `ObjectRoleAssignment`: all three store `role` as a bare `CharField`, no `choices=`.
- `freedom_ls/role_based_permissions/utils.py` — `sync_user_object_permissions`,
  `_filter_perms_for_content_type`, `_get_valid_codenames_for_content_type` (the existing
  `lru_cache` convention), `assign_object_role`/`remove_object_role`/`assign_site_role`/
  `remove_site_role` (none currently lock or count for last-admin refusal, confirming
  `research_role_assignment_rules.md`'s finding).
- `freedom_ls/learner_management/models.py` — `Learner(SiteAwareModel)`: `(user, organisation)` with
  `is_active`, `UniqueConstraint(fields=["site", "user", "organisation"])` — the exact shape §2
  recommends mirroring for `Educator`.

status: ok
