# Research: reference implementations for referral data APIs

Method: a few pages were fetched live on 2026-11-04 (marked **[fetched]**): Bitly, Plausible, Dub analytics, DRF CursorPagination, django-filter. Others (Rewardful, FirstPromoter, Tapfiliate, PartnerStack, Short.io, ReferralCandy, Google/Meta) are from knowledge of their docs and not re-fetched (marked **(verify)**). Builds on `research_comparable_apis.md` (auth, scopes, cursor envelope, URL versioning are not repeated).

## 1. Per-system findings

| System | Resources | Time filter and pagination | Nesting of user / link | Daily aggregates | PII |
| --- | --- | --- | --- | --- | --- |
| Dub.co | links (`key`, `url`, `clicks`, `lastClicked`, `createdAt`), click/lead/sale events, `/analytics` | Analytics: `start`, `end` (date or datetime), `interval` preset (`24h`, `7d`, ... `all`), `timezone` IANA, default UTC; `start`/`end` beat `interval` **[fetched]**. Events list uses `page`/`limit` (verify) | Events nest `link` object and `customer` object (id, email, name) (verify) | `groupBy=timeseries` returns one bucket per interval; `event` = clicks/leads/sales **[fetched]** | Click events carry country, city, device, browser, os, referer, `ip` may be withheld/"unknown" (verify); customer email exposed on leads |
| Bitly | bitlinks, clicks | `GET /v4/bitlinks/{id}/clicks?unit=day&units=7&unit_reference=<ISO8601>`; `units=-1` means all; no separate timezone param, the offset in `unit_reference` is the only zone **[fetched]** | Link is in the path | Response `link_clicks: [{clicks, date}]` plus echoed `units`, `unit`, `unit_reference` **[fetched]** | Aggregates only (countries, referrers); no per-click IP |
| Plausible | Stats API v2 single `POST /api/v2/query` | `date_range` as relative (`7d`, `30d`, `all`) or ISO 8601 date or date-time pair; `time:day` dimension in site reporting timezone; pagination `{limit: 10000, offset: 0}`; `include.total_rows` gives `meta.total_rows`; empty buckets omitted unless `include.time_labels` **[fetched]** | n/a (aggregates) | Day buckets; docs say metrics may shift under 1% depending on metric set; no explicit "recent days change" warning on that page **[fetched]** | None: aggregate only, no visitor IP |
| Rewardful | affiliates, links (`token`, `url`, `visitors`, `leads`, `conversions`), referrals, commissions, campaigns | Page-number `page`, `limit`, response `pagination` block; `created_at[gte]`-style filters, `expand[]=affiliate` (verify) | Referral nests `affiliate` (id, email, first/last name) and `link` (id, token, url); expand param for fuller objects (verify) | No daily-stats endpoint; counters on the link row | Customer email exposed to the key; no IP or user agent (verify) |
| FirstPromoter | promoters, referrals, commissions, rewards | Page-number `page`, `per_page`; date filters on some lists (verify) | Referral nests promoter (id, email) and `referral_link`/`ref_id` (verify) | Reporting endpoints give aggregates by date range (verify) | Referral email; no IP in list responses (verify) |
| Tapfiliate | affiliates, referral links, clicks, conversions, commissions | Page-number `page`, with `Link` headers; `date_from`/`date_to` on conversions and clicks (verify) | Conversion nests `affiliate` and `program`; click nests `referral_link` (verify) | Click log is per row; no daily rollup | Click `ip` and user agent are not a documented field (verify) |
| PartnerStack | partnerships, customers, transactions | Cursor: `starting_after`/`ending_before`, `limit` (Stripe-like), `min_created`/`max_created` epoch filters (verify) | Customer carries `partner_key`, `customer_key` (opaque keys, plus email) (verify) | none | Customer email present |
| Short.io | links, `/statistics/link/{id}` | Statistics use `period` presets and `startDate`/`endDate`, `tz` (verify) | Link id in path | Clicks "by day" arrays | Aggregates only; per-click via domain stats with browser/os/country, no IP |
| ReferralCandy | referrers, referrals, purchases | Page-number; `from_date`/`to_date` on referrals (verify) | Referral nests referrer email and order id | none | Email only |
| Google Ads / Meta conversion upload | Upload shape rather than export: click ids `gclid`, `gbraid`, `wbraid` (Google), `fbclid` and `_fbp`/`_fbc` cookies (Meta Conversions API), hashed email/phone | Event timestamp is a datetime with offset (Google `conversion_date_time`, Meta `event_time` unix seconds) (verify) | User identity sent hashed (SHA-256 of normalised email) | n/a | These are exactly the identifiers FLS withholds (`ga_cookie`, `fbp_cookie`, `fbc_cookie`, `client_ip`, `user_agent`): the ad platforms require them for matching, so their absence from the read API means it cannot feed an ad-upload job (state this in the docs) |

## 2. Patterns that apply to this spec

- **Nested relations**: id plus a human-readable value is the norm (Rewardful `affiliate{id,email}`, Dub `link{id,key}`). Matches the idea: hit carries `referral_code` (id) plus code text; attribution carries user id plus email. Flat sibling fields (`referral_code_code`, `user_email`) are the simplest for CSV-minded scripts; nested objects are what the vendors use. Pick one pattern across child 1 and keep the id field name unchanged from the export so scripts can join.
- **Click and visit logs are per row with an `id`, timestamp and link reference**; none of the vendors offer a changed-since filter on the click log, only created ranges. This agrees with using `hit_at` for both order and filter.
- **Time params**: vendors that accept dates and datetimes on one param (Dub `start`/`end`, Plausible `date_range`) accept ISO 8601 for both. Stripe uses suffixes (`created[gte]`). django-filter uses `<field>_after` / `<field>_before`.
- **Bitly echoes the resolved window** (`unit`, `units`, `unit_reference`) in daily responses. The idea may want the Day resource to echo nothing but to document the timezone: Dub defaults to UTC with a `timezone` param, Plausible uses a per-site reporting timezone, Bitly uses the offset in the reference timestamp. FLS `FirstTouchCount.day` is a date; state which timezone it was bucketed in (check `referral_tracking` model/docs) and say the API does not convert.
- **Warning that recent days change**: no vendor fetched states it prominently (Plausible notes only small metric drift). The idea's rule (re-pull most recent days) is therefore more explicit than the references and should be written into the docs page with a suggested overlap (for example, re-request from `today - N days`), noting counts only rise.
- **Absent buckets**: Plausible omits empty days. FLS counts are keyed by (day, key), so a missing row means zero; document that, and that `is_overflow` rows exist.
- **PII**: aggregates (Bitly, Plausible, Short.io) never carry IP. Per-event APIs (Dub, Tapfiliate) mostly expose geo/device derived fields, not raw IP (verify). Customer email is exposed in all affiliate tools. FLS withholding IP, UA and cookie ids while returning user email matches the market.
- **Referral code list**: Rewardful, Tapfiliate and Dub link lists are page-numbered or cursor lists with filters (Dub: `tagIds`, `search`, `sort`); a full pull of a small table with an optional `is_active` filter is common but not required. Cheap to add via django-filter; the idea leaves it open.

## 3. DRF-side implementation notes

### Cursor pagination on (timestamp, id)
- DRF's `CursorPagination` requires "a unique, unchanging ordering", prefers indexed, non-null, set-once fields; timestamps with ms precision are recommended; ordering is a class attribute `ordering` (default `-created`, which would fail on these models) and only prev/next is offered. **[fetched]** https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination
- `ordering` accepts a tuple: `ordering = ("hit_at", "id")`. DRF encodes only the first field's value plus an offset (position and offset approach), so ties on the first field are handled by offset, not by id. The `id` tie-break still gives a deterministic SQL ordering. Rows sharing identical `hit_at` can slip if rows are inserted at the cursor position between pages; mitigated by checkpointing inclusively (re-reading the boundary and deduping on `id`), which the idea's inclusive filter already allows. (verify against DRF source: `CursorPagination.paginate_queryset` uses `ordering[0]` for the position.) Source: https://github.com/encode/django-rest-framework/blob/master/rest_framework/pagination.py
- `FirstTouchCount.day` is a date: many rows share one value, so DRF cursor offsets will carry large offsets within a day (DRF caps the offset at `offset_cutoff = 1000`). A day with more than 1000 rows of the same `day` can break paging. The cutoff is a class attribute and can be raised on the project paginator; check how many first-touch rows per day can occur (one per key, with overflow rows bounding it). This is the largest technical risk found; flag it for the spec.
- Fixed `ordering` per view (not user-overridable): do not combine with `OrderingFilter`, or restrict it.
- Referral codes (no timestamp changes, ordered by `created_at, id`) use the same paginator.

### Date versus datetime range filters (django-filter)
- `DateFromToRangeFilter` on a DateTimeField considers only the date. `DateTimeFromToRangeFilter` / `IsoDateTimeFromToRangeFilter` take full datetimes, with `<name>_after` and `<name>_before`; either bound may be omitted. The docs do not state inclusivity; the example suggests `_after` is inclusive, `_before` is also inclusive (it maps to Django `__range`) (verify). **[fetched]** https://django-filter.readthedocs.io/en/stable/ref/filters.html
- Consequence for the open question on spelling: django-filter's `RangeFilter` maps to `__range` (both ends inclusive), which is wrong for an "inclusive since" only if the user supplies `_before`; for `since`-only, define a plain `IsoDateTimeFilter(field_name="hit_at", lookup_expr="gte")` named e.g. `hit_at_since` or the effort's shared name, and for `FirstTouchCount` a `DateFilter(field_name="day", lookup_expr="gte")`. A single filter-name used on all three (a shared base with a `since_field` attribute) is easy: one base `FilterSet` that declares `since` using a per-view target field and parses date or datetime accordingly. For the date resource, accept a date (`2026-11-01`) only; if a datetime is sent, reject with 400 rather than silently truncating.
- Timezone: `IsoDateTimeFilter` makes aware datetimes using the current timezone if no offset is supplied; require offset (Z) in docs.
- Dub and Plausible accept both forms on one parameter; this is a precedent for a shared name across date and datetime resources.

## 4. Suggestions for the spec (for the owner to choose)

1. Same changed-since parameter name across all three resources, as the effort defines it; date-typed for `first-touch-counts`, 400 on a datetime value.
2. User as `user` (id) plus `user_email` flat fields (or nested `{id, email}`), matching child 1's pattern; do not add name.
3. Document the timezone of `day`, the omitted-means-zero rule, the re-pull window for recent days, and that cookie ids and IP are absent so the data cannot feed Google/Meta conversion uploads.
4. Check the DRF `offset_cutoff` (1000) against first-touch rows per day before settling on cursor pagination for that resource.
5. `is_active` filter on referral codes is cheap; omit unless a script needs it.

## References

- Dub analytics: https://dub.co/docs/api-reference/endpoint/retrieve-analytics (also https://dub.co/docs/api-reference/endpoint/retrieve-clicks, 404 at fetch time)
- Bitly clicks: https://dev.bitly.com/api-reference/#getClicksSummaryForBitlink
- Plausible Stats API: https://plausible.io/docs/stats-api
- Rewardful API: https://developers.rewardful.com/ (not reachable at fetch time)
- FirstPromoter: https://docs.firstpromoter.com/
- Tapfiliate: https://tapfiliate.com/docs/rest/
- PartnerStack: https://docs.partnerstack.com/
- Short.io: https://developers.short.io/
- ReferralCandy: https://www.referralcandy.com/api
- Google Ads offline conversions: https://developers.google.com/google-ads/api/docs/conversions/upload-clicks
- Meta Conversions API parameters: https://developers.facebook.com/docs/marketing-api/conversions-api/parameters
- DRF CursorPagination: https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination
- django-filter filters: https://django-filter.readthedocs.io/en/stable/ref/filters.html

status: ok
