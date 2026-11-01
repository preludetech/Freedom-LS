# Lead monitoring API: foundation and users

Spec 1 of 6 in the Lead monitoring API effort. Read the "Lead monitoring API" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A site's admin issues a scoped API key in the Django admin. A Python script sends it as a bearer token and reads `/api/v1/users/`, paged with a cursor and filtered by `updated_since`. This child builds the whole foundation the other five children use: the key model, key authentication, the four scopes, the shared read-only conventions (pagination, `updated_since`, throttling, JSON-only output, schema) and the first resource, users. It also ships the docs page with a short Python example that follows pages, which each resource child extends with its own endpoint.

## Why

Lead monitoring needs scripts to pull learner and lead data out of a site without a person exporting CSVs from the admin. Nothing in FLS authenticates machines today, so the credential, its site binding and its audit trail have to exist before any resource is exposed. Users is the smallest resource and proves the stack end to end. Applications, referral data, registrations and interest, course progress and conversions are the consumers this foundation must serve: each adds a viewset, serializer and filter, registers it with the API router, and uses one of the four scopes this child defines.

## What is settled

**Stack and shape**
- Read only: GET, HEAD and OPTIONS. No write endpoints.
- Django REST framework with `django-filter` and `drf-spectacular`. `django-ninja` is not used and its dependency is left alone.
- JSON renderer only. No browsable API, no Swagger UI. The OpenAPI schema is served by drf-spectacular behind the same key authentication.
- Consumers are automated Python scripts. There is no UI on top of the API.
- URLs live under `/api/v1/`, with plural kebab-case resource paths, snake_case fields, explicit field lists (never `__all__`), ISO 8601 timestamps and UUIDs as strings.
- The admin exports stay as they are.

**The API key**
- A custom key model, not an unmaintained third-party key package and not a user token. It carries a site, the chosen scopes, an optional expiry, a revoked state and `last_used_at`.
- A key belongs to one site and reads only that site's rows. It is not tied to a user.
- Each key holds read scopes chosen when it is issued, from exactly four names: `users`, `course_applications`, `referral_data`, `registrations_and_progress`. This child defines the scope list and the `users` scope's use; the siblings use the other three.
- Keys are stored hashed, never in plain text. The full key is shown once, at issue.
- A key can have an expiry, can be revoked, and records `last_used_at`.
- Keys are issued and revoked in the Django admin. Issue and revoke are each written to the audit log.

**Authentication**
- The key is sent as `Authorization: Bearer <key>`. It is never accepted in the query string.
- Only API-key authentication is enabled on API views. There is no session authentication, so a signed-in browser cannot call the API.
- Authentication rejects a key used on another site's host, and rejects any request where the site cannot be resolved. Site is read from the request host as everywhere else in FLS; the key's site must match it.
- Failures return a generic 401 that does not reveal whether a key exists. A request whose key lacks the scope an endpoint needs is refused with 403.
- The Authorization header is never logged.
- The docs say HTTPS only: a key sent over plain http is to be treated as compromised.

**Shared read conventions**
- Cursor pagination ordered on `(updated_at, id)`, with a default page size and a capped maximum.
- Every resource accepts `updated_since`, inclusive, for incremental sync. Deletions are not visible to `updated_since`; there is no deletion feed in this effort.
- Throttled per key, not per IP.
- Querysets use `select_related` and `prefetch_related` and are filtered to the key's site.

**Users**
- `/api/v1/users/` requires the `users` scope and returns the admin export's columns: id, email, first name, last name, `is_active`, `is_staff`, `email_verified`, `created_at`, `last_login`, plus `updated_at`. It never returns password, groups, permissions or `is_superuser`.
- It returns only users of the key's site.

**Docs**
- A docs page with a short Python example using `httpx` that sends the bearer header and follows pages. Each resource child adds its endpoint to this page.
- `docs/product/security-and-data-handling.md` is updated to describe the API key, the data the users endpoint exposes and the retention of `last_used_at`.

## Open until the spec

- Where each resource's serializer and viewset live: in its own app, registered with the API router, or all in the API app. The import-linter contracts follow from this. The answer binds children 2 to 6.
- The name of the new app and the app setting that turns the API on for a concrete project.
- Throttle rates, and whether a shared cache is required for them to hold across processes.

## Out of scope

- Any resource other than users: applications, referral data, registrations and interest, course progress and conversions belong to the sibling specs.
- Any UI, browsable API or Swagger UI. Write endpoints. Webhooks or push.
- OAuth. Cross-site keys. Keys tied to users or to the role-based permission system.
- Removing the `django-ninja` dependency.
- Changing the admin exports.
- A deletion feed.

## Resources

- `research_api_foundation.md` (in this child's directory): codebase findings on site resolution, audit log and app settings, auth options compared, DRF conventions, security notes.
- `spec_dd/1. next/apis-for-lead-monitoring/research_data_sources.md`: models, admin export columns and hazards.
- `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md`: naming and conventions from comparable APIs.
- Skills: `fls-dev:multi-tenant`, `fls-dev:app-settings`, `ds:testing`, `fls-dev:testing`, `domain-glossary`.
