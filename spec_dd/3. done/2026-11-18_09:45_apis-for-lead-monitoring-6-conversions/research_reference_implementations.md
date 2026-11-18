# Research: reference implementations for touches and conversions lists

Scope: how affiliate and attribution platforms expose touches and conversions through list APIs. It does not repeat `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md` (auth, scoping, cursor envelope in general). Items marked (unverified) come from memory or a one-line summary, not a fetched page.

## What was verified

| System | Resource | Filters | Embedding | Incremental sync | Source |
|---|---|---|---|---|---|
| PartnerStack `GET /v2/customers` | customer rows carry the attribution: `partner_key`, `partnership_key`, `source_type`, `source_key`, plus `created_at`, `updated_at`, `customer_key`, `meta` | `min_created`/`max_created`, `min_updated`/`max_updated` (epoch ms), `partner_key`, `group` | none for the partner (key only); form `fields` are embedded | the `min_updated` filter. Newest first. Cursor is `starting_after` or `ending_before` with the last item's `key`. Response has `has_more` and `total`. `limit` 1-250 | https://docs.partnerstack.com/reference/get_v2-customers |
| FirstPromoter `GET /api/v2/company/referrals` | referral (lead or customer) with `state`, `entry_source` (api, coupon, cookie, manual_admin, manual_affiliate), `fraud_check`, `created_at`, `customer_since` | `filters[type]`, `filters[promoter_id]`, `filters[state]`, date ranges `[from]`/`[to]` (day precision) on `created_at`, `customer_since`, `cancelled_at`, plus `q` and `ids[]` | the promoter and campaign are embedded under `promoter_campaign` (id, email, name) | no documented cursor. Only date-range filters, so day precision | https://docs.firstpromoter.com/api-reference-v2/api-admin/referrals |
| Rewardful REST API | list shape is `{pagination:{current_page,next_page,count,limit,total_pages,total_count}, data:[]}`. UUID ids, ISO 8601 dates | per-endpoint (not fetched) | opt-in `expand=affiliate`, `expand[]=sale`. The default is ids only | page-number only | https://developers.rewardful.com/rest-api/overview.md |
| Stripe `GET /v1/events` | event with `created`, `type`, `data.object`, `api_version` | `created` (range object), `type`/`types`, `delivery_success` | the payload object is embedded, rendered at the version it was created under | `created` range plus `starting_after`. Retention is 30 days, so it works as a feed but not as a history | https://docs.stripe.com/api/events/list |
| Impact actions list | filters on action date and modified date. Fields include `ClickId`, `PromoCode` (unverified, one-line summary only) | campaign, date range, `ActionDate`, `ModifiedDate` | n/a | two separate date filters, one for the event time and one for modification | https://integrations.impact.com/impact-publisher/reference/list-actions (page 404; only a summary was available) |

Rewardful's referral, conversion and lead pages, Segment and HubSpot were not fetched. HubSpot is covered by the existing comparable-APIs note.

## Findings that bear on the spec

1. **Sync by write time, filter by event time separately: this is the common split.** PartnerStack offers both `created` and `updated` ranges. Impact offers both an action date and a modified date. Stripe's Events API is written-once records, filtered on `created`. The settled design here (page and sync on `recorded_at`, never filter or order on `occurred_at`) matches that. No reference system pages on the event time. The idea's reasoning for a late-arriving `occurred_at` is therefore sound. If a script wants an event-time range, a plain `occurred_at` filter that does not drive paging is the safe form, as with PartnerStack's separate created and updated filters. This is the "date-range filters beyond `updated_since`" open item. Offering it is optional; there is precedent but no need.

2. **Attribution rides on the conversion row as flat keys, not an embedded object.** PartnerStack's customer carries `partner_key`, `partnership_key`, `source_type` and `source_key` as plain strings and does not embed the partner. Rewardful's default is ids with opt-in `expand`. Only FirstPromoter embeds, and it returns a bare, unpaginated array. This supports the idea's default of flat lists joined by id: `first_touch`, `last_touch`, `first_referral_code` and `last_referral_code` on the conversion, with no embedding. Rewardful's `expand` is the precedent if embedding is wanted later. It is additive, so it can be deferred without breaking clients.

3. **Denormalised codes beside the id are normal.** PartnerStack's `partner_key` and `source_key` sit beside the row key. Keeping `first_referral_code` and `last_referral_code` on the conversion as well as the touch ids is the same pattern. It lets the payout query run with no join.

4. **Filter names follow the field names.** PartnerStack filters by `partner_key`, the same name as the field. FirstPromoter uses `filters[promoter_id]`, `filters[state]` and `filters[type]`. This supports the three filters in `answers.md` (`referral_code`, `first_referral_code`, `last_referral_code`) and `kind`, each named after its field. None of the systems offers a combined "either" filter. `referral_code` matching first or last is an FLS-specific convenience taken from the admin. Its documentation should say plainly that it is an OR.

5. **Enumerated state and source fields are first-class and filterable.** FirstPromoter exposes `entry_source` (cookie, coupon, api, manual) and `state`. PartnerStack exposes `source_type`. This parallels `kind` on a conversion and `recorded_via` on a touch. `recorded_via` is not a stated filter in the idea. A script judging ordering trust may want it, and FirstPromoter's `entry_source` is a precedent. It is a cheap, optional add, so flag it as an open decision.

6. **Cursor pagination uses the object key, ordered newest first in PartnerStack.** Our order is ascending `(recorded_at, id)`, the right order for checkpointing. PartnerStack's descending default is awkward for incremental sync. Keep ascending, and keep the cursor opaque (DRF `CursorPagination`) rather than exposing `starting_after` ids.

7. **Totals.** PartnerStack and Rewardful return `total` or `total_count`. Child 1 uses a cursor envelope, which has no count. Do not add a count. It is expensive on append-only tables that will grow, and no sync script needs it.

8. **Retention and deletion.** Stripe's events window is 30 days, and its docs say to use webhooks or `created` filters beyond that. For FLS, touches are append-only and will be pruned later (out of scope). A script's checkpoint on `recorded_at` stays valid after pruning, because a row never reappears with an older `recorded_at`. Say in the docs that pruned rows are not reported.

9. **Inclusive lower bound.** Stripe's `created[gte]` is inclusive and PartnerStack's `min_*` is inclusive, so `updated_since` being inclusive on `recorded_at` agrees. The tie-break id from the cursor handles duplicates at the boundary. Scripts must de-duplicate by id. State this in the docs example.

10. **Field naming.** Impact uses `ClickId` and `PromoCode` and PartnerStack uses `source_key`. FLS names (`advert_code`, `referral_code`, `landing_path`, `recorded_via`) have no close equivalents, so keep them. ISO 8601 UTC timestamps match Rewardful. PartnerStack uses epoch milliseconds, which child 1 does not.

## Recommendations (what would change the spec)

- Keep flat lists with ids. Resolve "embedding vs ids" as ids, and note `expand` as a future additive option, not part of this spec.
- Resolve "date-range filters": offer only `updated_since` (and an optional `recorded_until`, if child 1 provides one). If an `occurred_at` range is added, document it as a filter only, with paging still on `recorded_at`.
- Consider `recorded_via` as a touch filter (optional).
- Document the `referral_code` filter as matching either code.
- Do not add a total count.
- The docs example should de-duplicate on id and checkpoint on the last `recorded_at`.

## References

- https://docs.partnerstack.com/reference/get_v2-customers
- https://docs.firstpromoter.com/api-reference-v2/api-admin/referrals
- https://developers.rewardful.com/rest-api/overview.md
- https://docs.stripe.com/api/events/list
- https://integrations.impact.com/impact-publisher/reference/list-actions (unreachable page; summary only)

status: ok · reason: complete for PartnerStack, FirstPromoter, Rewardful overview and Stripe events; Impact, Segment and Rewardful per-resource pages not verified
