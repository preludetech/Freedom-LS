---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/partials/header_bar_user_menu.html
  - freedom_ls/educator_interface/templates/educator_interface/interface.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/organisation_switcher.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/announcer.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_toc_header.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS   # add "freedom_ls.organisations" if you maintain your own list
requires_package_upgrade: true
changed_packages:
  - pillow>=11.0     # new base dependency — ImageField validation for organisation logos
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: Organisations

This release adds **Organisation** — a scoping layer between `Site` and cohorts/registrations. Site
remains the isolation boundary; an Organisation groups cohorts, registrations and staff access within
one Site.

Every Site carries one Organisation named after itself, created by a `post_save` receiver on `Site`
and kept in step from then on. **If you never create a second Organisation, nothing about the shape
of your data changes** — but several code-level contracts do, and they are listed below.

**There is no backfill.** The migrations add `organisation` to `Cohort` and `UserCourseRegistration`
as non-nullable in one step, which a database can only accept while both tables are empty. See
"Upgrade steps" below before you migrate.

## Breaking changes

### 1. `Cohort.organisation` and `UserCourseRegistration.organisation` are mandatory

Both are non-nullable FKs with `on_delete=PROTECT`. Any downstream code that creates a `Cohort` or a
`UserCourseRegistration` directly must now supply an organisation:

```python
from freedom_ls.organisations.utils import get_default_organisation

Cohort.objects.create(name="…", organisation=get_default_organisation(site))
```

`get_default_organisation(site)` returns the Organisation named after the Site, which is the right
answer wherever no organisation is otherwise in scope. Your own
factories that build cohorts or registrations need the same addition (FLS's `CohortFactory` and
`UserCourseRegistrationFactory` now carry an `OrganisationFactory` sub-factory).

`CohortCourseRegistration`, `CohortMembership` and the deadline models get **no** FK — they reach
their organisation through `cohort.organisation` / `student_course_registration.organisation`.

### 2. A learner can now hold more than one registration for the same course

`unique_user_course_registration` widened from `(site, collection, user)` to
`(site, organisation, collection, user)`. Any of your code doing
`UserCourseRegistration.objects.get(user=…, collection=…)` can now raise `MultipleObjectsReturned` —
a runtime 500, and only on Sites that have more than one Organisation. Audit those call sites,
especially anything behind `COURSE_ACCESS_BACKEND`.

Where a single row is genuinely needed, use the shared helper rather than inventing a rule:

```python
from freedom_ls.student_management.queries import latest_registration

registration = latest_registration(user, course)  # most recent active, else most recent of any status
```

`Cohort`'s constraint widened the same way: `(site, name)` → `(site, organisation, name)`. Cohort
names are now unique **per organisation**, not per Site.

Both constraint changes are **narrowing an existing key by adding a column**, so neither can fail
against existing data — two rows that satisfied the old, stricter key cannot collide under the looser
one. This is not the dangerous kind of constraint change.

### 3. Two separate breaking changes to `panel_framework.ListViewConfig`

If you have your own `ListViewConfig` subclass, you must make **both** of these changes — doing only
one leaves you broken:

- **`check_access` is deny-by-default.** Detail views now run
  `ListViewConfig.check_access(request, instance)`, whose default `authorise_instance` raises
  `Http404`. A config that does not override `authorise_instance` **cannot serve detail views at
  all**. This is correct — those views were previously unguarded — but it will look like a sudden
  404 regression. Override `authorise_instance(cls, request, instance)` (not `check_access`, which
  carries the fail-closed prologue) and raise `Http404` unless the request may see the instance.
- **`get_instance_view` gained a `request` argument** — the signature is now
  `get_instance_view(cls, request, pk)`. A subclass that overrides it breaks loudly at call time.

`ListViewConfig.check_access_exempt_reason` exists for a config that deliberately defers
authorisation; set it to a short reason string so the gap is declared rather than accidental.

### 4. Educator interface URLs are organisation-scoped

`educator_interface:interface` now takes **two** kwargs — `organisation_slug` and `path_string`:

```python
reverse("educator_interface:interface",
        kwargs={"organisation_slug": org.slug, "path_string": "cohorts"})
```

Every existing `reverse()` / `{% url %}` that passes only `path_string` raises `NoReverseMatch`.
Sweep your templates and views for `educator_interface:interface`.

A new URL name **`educator_interface:root`** serves the bare `/educator/` path and redirects to a
concrete organisation. Links that used to point at `{% url 'educator_interface:interface' '' %}`
should point at `{% url 'educator_interface:root' %}` instead — that is exactly the edit made to
`freedom_ls/base/templates/partials/header_bar_user_menu.html`.

Paths themselves moved from `/educator/<path>` to `/educator/organisations/<slug>/<path>`, so any
hard-coded educator links or bookmarks are stale.

### 5. Educator access now requires reaching an organisation

`/educator/` 404s for a user with neither an `organisation_staff` role on any Organisation nor a
per-cohort guardian grant on any cohort. Existing per-cohort grants keep working — they resolve to
the organisation owning the granted cohorts — so educators you have already set up are unaffected.
Staff users who had access to the interface purely by being `is_staff`, with no grants at all, will
now be turned away.

### 6. Deleting an Organisation is refused

There is no delete path: the admin disables it and `PROTECT` enforces it at the database layer. Do
not add one downstream without deciding what happens to the cohorts and registrations underneath.

## Manual steps

1. **Add the app to `INSTALLED_APPS`** if you maintain your own list rather than inheriting FLS's
   `config/settings_base.py`:

   ```python
   INSTALLED_APPS = [..., "freedom_ls.organisations", ...]
   ```

   It must be installed before you migrate — its `ready()` registers the `post_save` receiver that
   keeps every Site carrying a default Organisation.

2. **Install Pillow.** `pillow>=11.0` is a new base dependency (`ImageField` validation for logos).
   `uv sync` picks it up.

3. **Run `uv run manage.py migrate`.** Three migrations apply in sequence: create `Organisation`, add
   the `organisation` FKs as non-nullable, then swap the constraints.

   - **Your `Cohort` and `UserCourseRegistration` tables must be empty.** The FK is added
     non-nullable with no default and there is no backfill, so the `ALTER TABLE` fails outright if
     either table has rows. If you already have cohorts or registrations you care about, do not run
     this upgrade — write your own backfill first, or ask before proceeding.
   - **Do not roll back after go-live.** Rolling back far enough drops the `organisation_id` columns
     and the `Organisation` table outright — there is nothing to put back except a database restore.
   - If you have modified `unique_cohort_name_per_site` or `unique_user_course_registration` outside
     FLS's own migrations, reconcile that first — `RemoveConstraint` addresses them **by name**.

4. **Run `uv run manage.py sync_role_permissions`** so the new `organisation_staff` role and its
   `freedom_ls_organisations.view_organisation` permission exist. The role layers in from
   `BASE_ROLES`, so a downstream role config that overrides FLS's gets it automatically.

5. **Rebuild Tailwind** (`npm run tailwind_build`, or your project's equivalent). The organisation
   switcher and the course-player co-branding chip introduce utility classes your bundle has not
   seen. No new npm packages — the icons used (`dropdown`, `unknown`) are existing semantic names.

6. **Review and re-apply your customisations** to the changed templates listed in the frontmatter,
   in particular:
   - `freedom_ls/base/templates/partials/header_bar_user_menu.html` — URL name changed to
     `educator_interface:root`. If you override this file, you **must** make the same edit or the
     page raises `NoReverseMatch`.
   - `freedom_ls/educator_interface/templates/educator_interface/interface.html` — now includes the
     organisation switcher partial and a persistent `#scope-announcer` live region. That element
     must stay **outside** `#main-content` and must not be swapped wholesale, or screen readers miss
     the announcement.
   - `freedom_ls/student_interface/templates/student_interface/partials/course_toc_header.html` —
     renders the learner's organisation logo (or initials) and name as a small chip above the course
     title.

7. **Optional: create real Organisations.** Via the Django admin (`Organisations`): create, rename,
   upload a logo, and assign staff through guardian's object-permissions page using the
   `organisation_staff` role. Logos accept PNG/JPEG/WebP up to 2 MiB and 4000×4000px; they are served
   from your existing default media storage with the usual signed URLs — **no new storage alias,
   bucket policy or environment variable is needed.** Then set `Cohort.organisation` and
   `UserCourseRegistration.organisation` on the rows that belong to them; anything created against
   the Site's own Organisation stays there until you move it.
