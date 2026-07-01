# Multi-Tenancy and Isolation

_Last updated: 2026-07-01_

## Summary

- A single Freedom LS installation serves multiple sites (domains) from one database; each site's data is automatically isolated at the query layer — no cross-tenant data leakage is possible through the ORM.
- `SiteAwareModel` and `SiteAwareManager` are the foundation: every site-scoped model inherits from `SiteAwareModel`, and `SiteAwareManager` automatically filters every query to the current site derived from the active HTTP request.
- New site-scoped records are automatically assigned to the current site on save; no code path is required to set the `site` field manually.
- Users are site-scoped: the same email address can exist as separate accounts on different sites.
- Per-site configuration includes signup policy, additional registration forms, webhook endpoints, and webhook secrets.

## Architecture

Freedom LS uses Django's `django.contrib.sites` framework as the foundation. Each site corresponds to a domain. A single database holds records for all sites; isolation is enforced at the model and manager layer, not at the database level.

### `SiteAwareModel` and `SiteAwareManager`

Defined in `freedom_ls/site_aware_models/models.py`.

**`SiteAwareModel`** is an abstract base model with:

- A `site` ForeignKey to `django.contrib.sites.models.Site` (protected against deletion).
- A UUID primary key (`id`).
- `objects` set to `SiteAwareManager`.

All site-scoped models inherit from `SiteAwareModel` (or the base variant `SiteAwareModelBase`, which omits the UUID primary key — used for the `User` model).

**`SiteAwareManager`** overrides `get_queryset()`. On every query, it checks the current request from a thread-local, derives the current site via `get_cached_site(request)`, and appends `.filter(site=site)` to the base queryset. If no request is present in the thread-local (e.g., in management commands), the filter is not applied and all records are visible.

**Automatic site assignment on save.** `SiteAwareModelBase.save()` and `full_clean()` both call `_set_site_from_request()`. If a new record's `site` field is not yet set, the site is read from the current request's thread-local and applied automatically. This means application code never needs to set `obj.site = ...` manually during a request/response cycle.

### Site Resolution

The current site is resolved via `get_cached_site(request)`:

1. If `FORCE_SITE_NAME` is set in settings, that named site is used (useful for single-site or test deployments).
2. Otherwise, Django's standard `get_current_site(request)` is called, which matches on the request's `Host` header against the `Site.domain` table.

The resolved site is cached on the request object for the duration of the request.

### `CurrentSiteMiddleware`

`freedom_ls.site_aware_models.middleware.CurrentSiteMiddleware` stores the current request in a thread-local at the start of each request and clears it after. This is what makes the site context available to `SiteAwareManager` without passing the request through every function call.

## Scope of Isolation

The following data categories are site-scoped and therefore isolated between tenants:

- **Users** — `User` model uses `SiteAwareModelBase`. Each site has its own user population; the same email address can hold separate accounts on different sites.
- **Course content** — `Topic`, `Activity`, `Form`, `Course`, `CoursePart`, and all related content models extend `SiteAwareModel`.
- **Student data** — `CourseProgress`, `TopicProgress`, `FormProgress`, `QuestionAnswer`, `UserCourseRegistration`, `CohortMembership`.
- **Cohort management** — `Cohort`, `CohortCourseRegistration`, `CohortDeadline`, `StudentDeadline`.
- **Signup policy** — `SiteSignupPolicy` has a unique constraint per site.
- **Webhooks** — `WebhookEndpoint` and `WebhookSecret` are both `SiteAwareModel` subclasses; each site's webhook configuration and secrets are isolated.
- **Legal consent** — `LegalConsent` is site-scoped.
- **Recommended courses** — `RecommendedCourse` is site-scoped.
- **Public discoverability surfaces** — the per-site `sitemap.xml`, `robots.txt`, and `schema.org` JSON-LD structured data on catalogue and course-detail pages are tenant-isolated in the same way. The `CourseSitemap` queryset is site-filtered automatically by `SiteAwareManager`, and all absolute URLs in the sitemap and JSON-LD are built per-request from the current site's domain — never a hardcoded host. A visitor on site A therefore never sees site B's courses, sitemap entries, or JSON-LD URLs. See [learner experience](./learner-experience.md) for SEO and discoverability details.

## Limitations and Gaps

- **`SiteGroup`** (a site-aware version of Django's `Group` model) is defined in `freedom_ls/accounts/models.py` but is commented out. Group-based permissions across sites are not currently available; see [roadmap](./roadmap.md).
- **Management commands** run without a request context. `SiteAwareManager` does not apply the site filter in this context; commands must filter by site explicitly or operate on all sites.
- **`Cohort` admin** currently uses `GuardedModelAdmin` rather than `SiteAwareModelAdmin`. A `@claude` TODO on the `CohortAdmin` class in `freedom_ls/student_management/admin.py` notes this needs fixing.

## Compliance: Tenant Data-Separation Guarantee

From a compliance perspective, the isolation guarantee is: for any HTTP request arriving at the application, all ORM queries executed during that request are automatically scoped to the site matching the request's `Host` header. An authenticated user or educator on site A cannot retrieve records belonging to site B through any standard view or form interaction, because `SiteAwareManager` applies the site filter unconditionally on every queryset. This guarantee extends equally to anonymous (unauthenticated) visitors: the home page, course catalogue, and course-detail pages are now publicly accessible, and `SiteAwareManager` applies the same per-request site filter on every ORM query they trigger, so anonymous browsing of one tenant's domain cannot surface another tenant's courses, sitemap entries, or structured-data URLs.

This isolation is at the application layer, not the database layer. All tenants share a single PostgreSQL database and schema. Physical database-level isolation (separate schemas, separate databases) is not provided. For deployments requiring stricter separation, a separate FLS installation per tenant is the supported approach.
