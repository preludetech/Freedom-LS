# Multi-Tenancy and Isolation

_Last updated: 2026-08-23_

## Summary

- A single Freedom LS installation serves multiple sites (domains) from one database. Each site's data is isolated automatically at the query layer.
- Within a site, an **organisation** is a grouping layer for cohorts and course registrations — not an isolation boundary. Every site has at least one organisation automatically; groups needing genuine data isolation still need separate sites, not separate organisations.
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
- **Cohorts** — cohorts, memberships, cohort course registrations, and both cohort and per-learner deadlines.
- **Configuration** — signup policy, recommended courses, and legal consent records.
- **Webhooks** — endpoints and their encrypted secrets.
- **Public discoverability surfaces** — the sitemap, `robots.txt`, and structured data on catalogue and course pages. All absolute URLs are built from the requesting site's own domain rather than a fixed host, so a visitor on one site never sees another's courses or URLs.

Organisations are not on this list. They group cohorts and course registrations *within* a site — see [Organisations](#organisations) below — and add no isolation on top of the site boundary.

## Tenant Data-Separation Guarantee

For any HTTP request reaching the application, every database query executed while serving it is scoped to the site matching the request's host. A user or educator on site A cannot retrieve site B's records through any standard view or form interaction, because the filter is applied unconditionally rather than per-query.

This applies equally to anonymous visitors. The home page, course catalogue, and course detail pages are publicly accessible, and the same per-request scoping governs them, so anonymous browsing of one tenant's domain cannot surface another tenant's data.

This is the canonical statement of the isolation guarantee; other docs link here rather than restating it.

## Organisations

A site can be subdivided into one or more **organisations** — a grouping and scoping layer that sits between a site and its cohorts and course registrations. Every cohort and every course registration belongs to exactly one organisation.

**An organisation is not a security or isolation boundary.** Site remains the isolation boundary described above; two groups that need genuine data isolation still need two separate sites, not two organisations. Multiple organisations on one site share that site's course library, chrome, and domain.

Every site has at least one organisation, named after the site itself and created automatically — for existing sites on upgrade, and for every new site from then on. A single-organisation deployment needs no configuration and behaves as it did before organisations existed. Organisation names are unique within a site.

Staff can be granted a role scoped to a single organisation, which gives them access to everything in it without a separate grant per cohort. This sits alongside FLS's existing per-cohort grants rather than replacing them — see [educator interface](./educator-interface.md#access-control).

This is the canonical statement of what an organisation is and is not; other docs link here rather than restating it.

## Limitations and Gaps

- **Application-layer, not database-layer.** All tenants share a single PostgreSQL database and schema. Separate schemas or separate databases per tenant are not provided. Deployments needing physical separation should run a separate FLS installation per tenant.
- **Management commands run without a request**, so there is no site to scope to and the filter does not apply — commands see all sites' records and must filter explicitly. This is deliberate: it is what lets a command load content or run maintenance across sites.
- **Site-aware user groups are not available.** A site-scoped equivalent of Django's groups is drafted but not enabled; permissions are granted per user. See [roadmap](./roadmap.md).
- **The cohort admin page is not site-filtered** the way other admin pages are. This is a known gap and is tracked.
- **Organisations cannot be deleted or merged**, and there is no nested (parent/child) organisation structure.
- **No per-organisation domain, subdomain, colours, or theme.** All organisations on a site share the site's domain and branding; the only visual distinction is a small logo (or initials monogram) and name in the course player — see [learner experience](./learner-experience.md).
- **No standalone organisation membership.** A learner's organisation is derived from their cohort or individual course registration, not from a membership record they hold.
- **Courses, course interest, applications, and recommendations are not organisation-scoped** in this release — they remain shared across the whole site. See [roadmap](./roadmap.md).

## Per-Site Configuration

Signup policy and registration requirements are configured per site — see [authentication](./authentication.md). Webhook endpoints and secrets are likewise per site — see [webhooks](./webhooks.md).
