---
name: reference-organisation-admin-summary-counts
description: The Organisation admin change page's learner-count summary line (ngettext) — where it lives, how to seed an exact-N organisation, and how to render the wording headlessly instead of guessing
metadata:
  type: reference
---

## Where the summary line lives

`freedom_ls/learner_management/admin.py::organisation_learner_search_link(organisation)`
— NOT in `freedom_ls/organisations/`. `organisations` sits below `learner_management`
in `docs/app_structure.md` and cannot import `Learner`, so the wiring is pushed up:

    OrganisationAdmin.inlines = [OrganisationCohortInline, OrganisationLearnerInline]
    ORGANISATION_SUMMARIES.append(organisation_learner_search_link)

`ORGANISATION_SUMMARIES` is the seam `OrganisationAdmin` declares. Any future
"summary line on the org change page" ask hangs off that list, from the app that
owns the model being counted.

Three render branches, so three fixture shapes are needed for full coverage:

| count | rendered |
|---|---|
| 0 | `No learners yet` (plain text, no link) |
| 1 | `Search this organisation's 1 learner` |
| N | `Search this organisation's %(count)d learners` |

## The count is `Learner.objects` — site-aware, and NOT filtered by is_active

`Learner.objects.filter(organisation=organisation).count()`. Two consequences:

- A **removed** learner (`is_active=False`) still counts. Do not reach for
  `is_active=False` to shrink a count to 1 — delete the row or seed a fresh org.
- `objects` is the `SiteAwareManager`, so under a request it ANDs the ambient
  site on. Counting from a bare `manage.py shell` (no thread-local request)
  sees every site and can disagree with the browser. Use `_base_manager` for
  locating rows, and re-count under a faked request before reporting.

## Seeding an exact-N organisation

```python
site = Site.objects.get(name="DemoDev")
org = OrganisationFactory(site=site, name="QA Singular Learner Org")   # slug auto via get_unique_slug
user = UserFactory(site=site, email="...", password="testpass123")
LearnerFactory(user=user, organisation=org)      # site comes from organisation.site
```

- `OrganisationFactory.slug` is a `LazyAttribute` over `get_unique_slug`, so never pass `slug=`
  unless a specific stable slug is wanted.
- `LearnerFactory._create` delegates to `ensure_learner`, so it is **already idempotent** on
  `(user, organisation)` — a re-run returns the existing row instead of tripping
  `unique_learner_per_organisation`. It also reactivates, so `is_active=False` is applied after.
- Guard the whole seed on `Learner._base_manager.filter(organisation=org).count()` rather than on
  the org's existence: "org exists" and "org has exactly one learner" are different states, and the
  ask is usually the latter.

## Proving the wording without touching the tester's server

Call the summary function directly with a thread-local request; do not eyeball the page.

```python
from freedom_ls.site_aware_models.models import _thread_locals
request = RequestFactory().get("/admin/")
_thread_locals.request = request
try:
    print(organisation_learner_search_link(org))
finally:
    del _thread_locals.request
```

Dev pins every request to DemoDev (`FORCE_SITE_NAME` in `config/settings_dev.py`), so no
`override_settings` is needed for a DemoDev org. Assert on the exact substring
(`"1 learner"` vs `"1 learners"`) — that is the whole point of an ngettext check.

## Fixture seeded Sep 2026

`QA Singular Learner Org` on DemoDev, slug `qa-singular-learner-org`, one learner
`qa_singular_learner@email.com` / `testpass123` (no cohorts, no registrations — deliberately,
so nothing else can add a second Learner to it). Leave it at exactly one.
