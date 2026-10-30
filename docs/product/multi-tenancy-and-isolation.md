# Multi-Tenancy and Isolation

_Last updated: 2026-10-30_

## Summary

- A single Freedom LS installation serves multiple sites (domains) from one database. Each site's data is isolated automatically at the query layer.
- Within a site, an **organisation** is a grouping layer for cohorts and course registrations — not an isolation boundary. Every site has at least one organisation automatically; groups needing genuine data isolation still need separate sites, not separate organisations.
- People are associated with organisations as learners in their own right, before any enrolment, and one person can be a learner of several organisations on a site while keeping a single account. See [Organisations](#organisations).
- Isolation is not opt-in per query: every database read during a request is scoped to the site matching the request's host, and new records are assigned to that site on save.
- Users are site-scoped — the same email address can hold separate accounts on different sites.
- Isolation is enforced in the application, not the database. All tenants share one PostgreSQL database and schema.

## How Isolation Works

Each site corresponds to a domain, using Django's sites framework. When a request arrives, FLS resolves which site it belongs to from the request's host header, and every database query made while serving that request is filtered to that site. Records created during the request are assigned to it automatically, so no application code has to set the site by hand.

Deployments serving a single site can pin the site explicitly with the `FORCE_SITE_NAME` setting, which skips host-based resolution. This is also how tests run. Work that has no request at all — a management command, a scheduled job, a queue worker — needs the same pinning to resolve a tenant. With nothing pinned, such work is refused rather than guessed at, because outbound mail carries the tenant's branding and sending under the wrong name is worse than not sending.

## What Is Isolated

All of the following are site-scoped, so a given site's copy is invisible to every other site:

- **User accounts**, including the ability to reuse an email address across sites.
- **Course content** — courses, parts, topics, activities, and forms.
- **Learner data** — course, topic, and form progress, quiz answers, and course registrations.
- **Cohorts** — cohorts, memberships, cohort course registrations, and the deadline overrides set on cohort course registrations or on individual learners.
- **Configuration** — signup policy, recommended courses, legal consent records, and the site's time zone.
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

**People are associated with organisations as learners.** Someone can belong to an organisation as a learner before, and independently of, any cohort membership or course registration, and every cohort membership and course registration belongs to one of those associations — an enrolment with no organisation behind it cannot exist. The same person can be a learner of several organisations on one site, keeping one account and one set of profile fields; each organisation sees only its own association, which is scoping within the site rather than an isolation boundary of its own. An organisation can mark a learner removed, which withdraws their access to courses held through that organisation while leaving their enrolments and progress history intact; it is never a hard delete. See [admin interface](./admin-interface.md#learner-rosters) for how learners are added and removed.

Staff access within an organisation comes from role assignments: a role on the organisation covers everything in it, including cohorts created later, and a role on a cohort covers that cohort only. Either counts only while the person is an active member of that organisation. See [educator interface](./educator-interface.md#access-control).

A course can belong to one or more organisations, declared by its authors in the course content (see [content editing workflow](./content-editing-workflow.md)). Such a course is seen and opened only by learners of those organisations, unless its audience is set to public, and it can be registered onto only through those organisations. A course with no organisation stays open to the whole site. A learner already registered keeps access for as long as the learner association they registered through stays active.

This is the canonical statement of what an organisation is and is not; other docs link here rather than restating it.

## Limitations and Gaps

- **Application-layer, not database-layer.** All tenants share a single PostgreSQL database and schema. Separate schemas or separate databases per tenant are not provided. Deployments needing physical separation should run a separate FLS installation per tenant.
- **Management commands run without a request**, so there is no site to scope to and the filter does not apply — commands see all sites' records and must filter explicitly. This is deliberate: it is what lets a command load content or run maintenance across sites.
- **Site-aware user groups are not available.** A site-scoped equivalent of Django's groups is drafted but not enabled; permissions are granted per user. See [roadmap](./roadmap.md).
- **Organisations cannot be deleted or merged**, and there is no nested (parent/child) organisation structure.
- **No per-organisation domain, subdomain, colours, or theme.** All organisations on a site share the site's domain and theme, and there is no per-organisation brand colour. An organisation's name and logo are what distinguish it visually: learners see them in the course player and on course cards, rows and the course page — see [learner experience](./learner-experience.md) — and they are the primary brand on the cover of a [cohort progress report](./reports.md).
- **Only course visibility and registration are organisation-scoped.** Course interest and applications are not restricted by a course's organisations, and recommendation rules are not set per organisation, though recommendations only surface courses the learner may see. See [roadmap](./roadmap.md).

## Per-Site Configuration

Signup policy and registration requirements are configured per site — see [authentication](./authentication.md). Webhook endpoints and secrets are likewise per site — see [webhooks](./webhooks.md). Each site also has its own time zone for due dates, and can choose whether learners see a zone label next to them — see [admin interface](./admin-interface.md#site-time-zone).
