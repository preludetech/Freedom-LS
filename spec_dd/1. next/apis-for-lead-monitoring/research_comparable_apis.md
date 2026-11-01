# Research: comparable export APIs for lead monitoring

Method note: written from knowledge of each vendor's public docs; URLs are the canonical doc entry points, not re-fetched in this run. Details marked (verify) should be checked before being cited in a spec.

## Comparison table

| System | Server-to-server auth | Key scoping | Pagination | Incremental sync | Versioning | Resources (users / enrollments / progress / referrals) | PII handling |
|---|---|---|---|---|---|---|---|
| Canvas LMS | Bearer access token (per-user, generated in UI) or OAuth2 (developer key; client-credentials-style via service accounts) | Token inherits the user's role/permissions; developer keys can be scoped per endpoint (API scopes); tenant = the school's own domain | `Link` header (rel=next/prev/first/last), `per_page` | Limited: some endpoints accept `updated_since`/`start_at`; Live Events / Data Services for event feeds | Mostly unversioned `/api/v1/`; additive changes | users, enrollments, courses, assignments, submissions, analytics; no referrals | Role-gated: email/login visible only with permission; no field-level masking toggle |
| Moodle web services | Token (`wstoken`) per user per service; REST/XML-RPC | A "service" is an allow-list of functions; token bound to a user with capabilities | None standard; function-specific (`limitfrom`/`limitnum`, `page`/`perpage`) | Weak: ad hoc `timemodified` params on some functions | Per Moodle release; function names are the API (`core_user_get_users`) | users, enrolments, course completion, grades; no referrals | Capability-gated; `moodle/site:viewuseridentity` controls email etc. Token in query string is a known weakness |
| Open edX | OAuth2 client credentials (JWT) via LMS; session auth for browsers | OAuth application + staff/service-user permissions; per-site | Django REST Framework page-number (`page`, `page_size`, `next`/`previous`/`count`), some cursor | Partial: `updated`/`modified` filters on some endpoints (grades, enrollments v1 `course_id`/`username`) (verify) | URL versions `/api/enrollment/v1/`, `/api/grades/v1/` | enrollment, grades, certificates, user accounts; no referrals | Separate user-account API with permission-based field visibility; service users see more |
| Thinkific | API key (`X-Auth-API-Key` + `X-Auth-Subdomain`) or OAuth2 for apps | Key is per school (subdomain); all-or-nothing | Page-number: `page`, `limit`, `meta.pagination` block | `query[updated_after]`-style filters on some resources; webhooks for events (verify) | `/api/public/v1/` | users, enrollments, courses, course reviews, orders, coupons, promotions; progress via enrollment `percentage_completed` | Full user data to key holder; no masking |
| Teachable | API key (header `apiKey`) tied to school (Pro plan+) | Per school; no permission scoping | Page-number: `page`, `per`, `meta` | Limited (date filters on some endpoints); webhooks | `/v1/` | users, courses, enrollments, course progress, transactions, pricing plans | Full to key holder |
| LearnWorlds | OAuth2 client credentials (`client_credentials` grant) plus `Lw-Client` header (school id) | Per school; scopes on OAuth client (verify) | Page-number `page`, `items_per_page`/`limit`; `meta` with totals | Some date filters; webhooks | `/v2/` path | users, courses, enrollments, progress, certificates, payments, tags | Full to authorised client |
| HubSpot | Private app access token (Bearer), OAuth for multi-account apps | Per-scope (`crm.objects.contacts.read`) chosen per private app; per portal | Cursor (`after` + `paging.next.after`), `limit` | Search API with `lastmodifieddate` filter; `/crm/v3/objects` plus webhooks; Exports API for bulk | Dated path versions `/crm/v3/`; v4 for associations | contacts, companies, deals, forms/submissions; UTM/source properties as referral analogue | Properties marked sensitive need extra scope; scope = read contacts |
| Stripe | Secret API key (`Bearer sk_...`), restricted keys | Restricted keys with per-resource read/write/none permissions; test vs live mode | Cursor: `limit`, `starting_after`, `ending_before`, `has_more`, `data` list envelope | `created[gte]` filters, Events API (`/v1/events`, 30-day) and webhooks; `expand[]` for related objects | Dated version (`Stripe-Version` header), account pinned | customers, subscriptions, charges, ... prefixed ids (`cus_...`); referral via metadata | Resource ids rather than raw PII where possible; restricted keys limit exposure; masks card data |

## Common patterns

- Server-to-server scripts use a long-lived bearer secret (Thinkific, Teachable, Stripe, HubSpot private apps) or OAuth2 client credentials (Open edX, LearnWorlds). Canvas and Moodle tie tokens to a human user, which makes revocation and auditing awkward.
- Best-in-class scoping (Stripe restricted keys, HubSpot scopes) is per-resource read-only; the LMS vendors mostly give all-or-nothing per-school keys.
- Tenant is implied by the key or the host (subdomain), never a request parameter.
- Pagination: tidy APIs use cursors with a uniform list envelope (Stripe, HubSpot). LMS APIs use page-number or Link headers; Moodle has no standard.
- Incremental sync is the weakest area in LMS APIs. Stripe and HubSpot offer `created`/`modified` range filters; this is what lead-monitoring scripts need.
- Versioning is a URL prefix (`/v1/`) in nearly all of them; only Stripe and HubSpot use dated versions.
- None of the LMSes has a first-class referral/affiliate API (Thinkific/Teachable have affiliates only as a platform feature or via orders/coupons); HubSpot treats source/UTM as contact properties.
- PII: mostly role/permission-gated, rarely field-level. Stripe/HubSpot mitigate with scoped keys.

## Recommendations for FLS

- **Auth**: a dedicated API key model (hashed secret, shown once, name, site FK, created_by, expiry/revoked flag, last_used_at, optional read scopes per resource group), sent as `Authorization: Bearer <key>`. Keys are bound to one Site, matching site-aware models. Avoid OAuth for now (no interactive consumers); avoid query-string keys. DRF custom `BaseAuthentication` plus a permission class that checks scope; HTTPS-only; throttle per key. Do not reuse user session or DRF `TokenAuthentication` (one token per user, no scopes, stored plaintext).
- **Pagination**: cursor pagination (DRF `CursorPagination`) ordered by a stable key (`updated_at, id`), uniform `{next, previous, results}` envelope, capped `page_size`. Reliable across concurrent writes and large tables.
- **Incremental sync**: every resource gets `updated_at` (and `created_at`) in output and an `updated_since` filter (inclusive, ISO 8601); order by `updated_at, id` so scripts can checkpoint. Deletions/anonymisations are a known gap: consider a `deleted` flag or a later events feed, but defer.
- **Resource naming**: plural nouns, kebab-case paths, snake_case fields, under `/api/v1/`: `users`, `course-applications` (with `is_anonymous` or a nullable user), `referral-links`, `referral-attributions` (or similar, per the FLS referral models), `course-registrations`, `course-progress`. Read-only (`ReadOnlyModelViewSet`, GET/HEAD/OPTIONS only), filters via django-filter, `select_related`/`prefetch_related` throughout, OpenAPI schema (drf-spectacular) for tidiness.
- **PII**: return only fields lead monitoring needs; scope `users` separately so a key can read registrations without emails; document the field list; log key id (not secret) per request; never expose password hashes, staff flags or internal notes.
- **Minimum useful first release** (ordered specs):
  1. API foundation: key model and authentication, scopes, site binding, `/api/v1/` router, cursor pagination, `updated_since` filter base, throttling, schema, test harness.
  2. `users` and `course-registrations` (the core lead funnel, simplest models).
  3. `course-applications` (anonymous plus authenticated).
  4. `referral-links` and referral attribution.
  5. `course-progress`, the heaviest aggregation, last; plus a Python client example script.
  Key-management UI/admin can be Django admin only in the first release.

## References

- Canvas: https://canvas.instructure.com/doc/api/ (pagination: https://canvas.instructure.com/doc/api/file.pagination.html; OAuth: https://canvas.instructure.com/doc/api/file.oauth.html)
- Moodle: https://moodledev.io/docs/apis/subsystems/external and https://docs.moodle.org/en/Using_web_services
- Open edX: https://docs.openedx.org/en/latest/developers/references/api_docs.html and https://github.com/openedx/edx-platform/tree/master/openedx/core/djangoapps/enrollments
- Thinkific: https://developers.thinkific.com/api/api-documentation/ and https://developers.thinkific.com/api/authentication/
- Teachable: https://docs.teachable.com/ (API reference: https://docs.teachable.com/reference)
- LearnWorlds: https://www.learnworlds.dev/
- HubSpot: https://developers.hubspot.com/docs/api/overview and https://developers.hubspot.com/docs/api/private-apps
- Stripe: https://docs.stripe.com/api, https://docs.stripe.com/api/pagination, https://docs.stripe.com/keys#limit-access (restricted keys), https://docs.stripe.com/api/events
- DRF: https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination

status: ok · reason: complete, from knowledge of vendor docs; not re-fetched live (items marked verify)
