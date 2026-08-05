# Multi-Tenancy and Isolation

_Last updated: 2026-08-05_

## Summary

- A single Freedom LS installation serves multiple sites (domains) from one database. Each site's data is isolated automatically at the query layer.
- Isolation is not opt-in per query: every database read during a request is scoped to the site matching the request's host, and new records are assigned to that site on save.
- Users are site-scoped — the same email address can hold separate accounts on different sites.
- Isolation is enforced in the application, not the database. All tenants share one PostgreSQL database and schema.

## How Isolation Works

Each site corresponds to a domain, using Django's sites framework. When a request arrives, FLS resolves which site it belongs to from the request's host header, and every database query made while serving that request is filtered to that site. Records created during the request are assigned to it automatically, so no application code has to set the site by hand.

Deployments serving a single site can pin the site explicitly with the `FORCE_SITE_NAME` setting, which skips host-based resolution. This is also how tests run.

## What Is Isolated

All of the following are site-scoped, so a given site's copy is invisible to every other site:

- **User accounts**, including the ability to reuse an email address across sites.
- **Course content** — courses, parts, topics, activities, and forms.
- **Learner data** — course, topic, and form progress, quiz answers, and course registrations.
- **Cohorts** — cohorts, memberships, cohort course registrations, and both cohort and per-student deadlines.
- **Configuration** — signup policy, recommended courses, and legal consent records.
- **Webhooks** — endpoints and their encrypted secrets.
- **Public discoverability surfaces** — the sitemap, `robots.txt`, and structured data on catalogue and course pages. All absolute URLs are built from the requesting site's own domain rather than a fixed host, so a visitor on one site never sees another's courses or URLs.

## Tenant Data-Separation Guarantee

For any HTTP request reaching the application, every database query executed while serving it is scoped to the site matching the request's host. A user or educator on site A cannot retrieve site B's records through any standard view or form interaction, because the filter is applied unconditionally rather than per-query.

This applies equally to anonymous visitors. The home page, course catalogue, and course detail pages are publicly accessible, and the same per-request scoping governs them, so anonymous browsing of one tenant's domain cannot surface another tenant's data.

This is the canonical statement of the isolation guarantee; other docs link here rather than restating it.

## Limitations and Gaps

- **Application-layer, not database-layer.** All tenants share a single PostgreSQL database and schema. Separate schemas or separate databases per tenant are not provided. Deployments needing physical separation should run a separate FLS installation per tenant.
- **Management commands run without a request**, so there is no site to scope to and the filter does not apply — commands see all sites' records and must filter explicitly. This is deliberate: it is what lets a command load content or run maintenance across sites.
- **Site-aware user groups are not available.** A site-scoped equivalent of Django's groups is drafted but not enabled; permissions are granted per user. See [roadmap](./roadmap.md).
- **The cohort admin page is not site-filtered** the way other admin pages are. A `@claude` TODO in the code tracks this.

## Per-Site Configuration

Signup policy and registration requirements are configured per site — see [authentication](./authentication.md). Webhook endpoints and secrets are likewise per site — see [webhooks](./webhooks.md).
