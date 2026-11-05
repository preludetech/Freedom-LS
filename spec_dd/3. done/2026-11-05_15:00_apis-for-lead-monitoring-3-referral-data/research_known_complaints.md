# Research: known complaints about referral / attribution / analytics export APIs

Scope: what script authors complain about, and what this idea's design prevents or exposes. Evidence level: two web searches (vendor docs and help articles) plus widely documented API behaviour from general knowledge. Vendor-specific forum threads (Rewardful, FirstPromoter, PartnerStack, Dub) were not found directly. Those complaints are marked "general pattern".

## Complaints and how the design answers them

| # | Complaint | Idea design: prevented or exposed? |
| --- | --- | --- |
| 1 | API counts do not match the dashboard. Causes: "(other)" row grouping, sampling, different metric variant or attribution window, extra dimensions changing totals ([Coupler](https://docs.coupler.io/troubleshooting/why-api-data-is-different-from-what-users-see-in-the-ui), [Daasity](https://help.daasity.com/extract/integrations/google-analytics-4/api-integration/important-notes), [NinjaCat](https://docs.ninjacat.io/docs/troubleshooting-ga4-data-discrepancies), [Merkle](https://www.merkle.com/en/merkle-now/articles-blogs/2025/navigating-ga4-pitfalls-that-could-derail-your-analytics.html)) | Mostly prevented. The API returns raw rows with the same field names as the admin export, so there is no sampling or grouping. EXPOSED: `hit_count` on a referral code can differ from the number of hit rows, because the hit log is pruned and `hit_count` does not reconcile with it. Document this on the endpoint and in the shared docs page, or scripts will report it as a bug. |
| 2 | Bot and machine traffic inflates click counts. Raw-hit tools count higher than bot-filtered ones; vendors split "Clicks" and "Invalid Clicks" ([Rebrandly](https://support.rebrandly.com/en/articles/755638-why-don-t-my-rebrandly-numbers-match-other-analytics-tools), [Trackier](https://help.trackier.com/en/articles/6984073-click-discrepancy-issue-between-trackier-panel-publisher-panel), [RedTrack](https://help.redtrack.io/knowledgebase/kb/conversion-tracking/clicks-inconsistency/)) | Prevented. `is_machine_fetch` is exposed on each hit, so a script can exclude machine traffic. EXPOSED: `hit_count` on the code and the hit log may count machine fetches. Spec should state whether `hit_count` includes them, and that a script wanting human visits should count hits where `is_machine_fetch` is false. |
| 3 | Recent-day numbers change after the pull. GA4 needs processing time; Improvado advises pulling as late as possible ([Improvado](https://improvado.io/docs/google-analytics-4-troubleshooting)). Google Ads restates for conversion lag (general pattern) | Exposed for `first-touch-counts`: `count` rises through the day with no `updated_at`. The idea already handles this by documenting a "re-pull the most recent days" rule. Spec should give a concrete number (for example the last 2 days plus today) and say whether a row for a day can appear late. Hits and signup attributions are append-only, so they do not have this problem. |
| 4 | Timezone and day-boundary confusion for daily buckets ([Adriel](https://docs.adriel.com/troubleshooting/numbers-dont-match-source-platform.md), [Coupler](https://docs.coupler.io/troubleshooting/why-api-data-is-different-from-what-users-see-in-the-ui)) | Exposed. `day` is a date, while the other timestamps are ISO 8601 datetimes. The spec must say which timezone defines `day` (the site or project timezone, or UTC) and whether the changed-since filter on `first-touch-counts` takes a date. A script that checkpoints on `signed_up_at` in UTC and compares with `day` will be off by one near midnight unless this is stated. |
| 5 | No incremental filter forces full re-pulls (general pattern, common in affiliate tools) | Mostly prevented: inclusive changed-since on hits, signup attributions and first-touch counts. Referral codes are intentionally a full pull; the small table makes that acceptable. A `created_at`-ordered list with no filter means edits to `label`, `is_active` and `hit_count` are only seen by a full re-read. This is documented, which is the right answer. |
| 6 | Pagination skips or duplicates rows. Offset paging with a mutable sort key, or ordering on a non-unique timestamp (general pattern, Stripe-style lists use ids as cursors) | Prevented in design: order by timestamp then `id`, with cursor pagination. Inclusive "from the last value" checkpoints produce duplicates at the boundary row by design. Document that scripts must de-duplicate on `id`. For `first-touch-counts`, ordering on `day` then `id` is fine for reading but rows mutate mid-pull, so a long pull can see a `count` change between pages; document it. |
| 7 | Rate limits surprise scripts (general pattern) | Out of this child; inherited from child 1. Spec should only link to the shared limit and `Retry-After` behaviour. |
| 8 | Field renames and removals break scripts (general pattern) | Prevented: names equal the admin export, are explicit lists (never `__all__`), and live under `/api/v1/`. EXPOSED: the user is returned as id plus email, and the code as id plus code text. Pick the nested key names once, because adding fields later is safe while renaming is not. |
| 9 | PII over-exposure | Prevented: `client_ip`, `user_agent`, `ga_cookie`, `fbp_cookie`, `fbc_cookie` are withheld. EXPOSED residual PII: user email, `referer`, `raw_query`, `landing_path` and `gclid`/`fbclid` click ids can carry personal data (query strings sometimes hold emails or tokens). The security doc update should list these as returned. Decide in the spec whether to return only id plus email for the user (the idea leans that way; do not add name). |
| 10 | Nulls versus empty strings are inconsistent ([Daasity](https://help.daasity.com/extract/integrations/google-analytics-4/api-integration/important-notes) and others discuss "(not set)" style placeholders) | Exposed. The UTM, click id and `advert_code` fields on signup attributions and first-touch counts are probably blank strings in the model, and `last_hit_at` is probably null. The spec should pick one rule (blank string for text fields, null for dates) and test it. `is_overflow` rows in first-touch counts mean the key may be a bucket for rows that overflowed. Document what `utm_*` mean on those rows. |
| 11 | Deletions are invisible to incremental pulls (general pattern) | Exposed and acknowledged: pruned hits disappear. Scripts that sum hits per code over time will see totals drop after pruning. Document the retention window for hits. |
| 12 | Dashboard and API disagree on which "first touch" counts (general pattern) | Exposed: `first-touch-counts` is the denominator while signup attributions are per user, and `is_overflow` rows hold the surplus keys. A script computing conversion rate needs to know that sum of counts per campaign key must include the overflow rows. Write a worked example in the docs page. |

## Priorities for the spec

1. State the timezone that defines `day`, and the spelling and type of the changed-since filter on `first-touch-counts`.
2. Give the late-increment re-pull rule a concrete window.
3. Document that duplicates are possible at the checkpoint boundary and that scripts de-duplicate on `id`.
4. Document the `hit_count` versus hit-log mismatch, machine fetches, and pruning.
5. Fix null versus empty-string rules and test them.
6. List the residual PII (email, `referer`, `raw_query`, `landing_path`) in the security doc.

## References

- https://docs.coupler.io/troubleshooting/why-api-data-is-different-from-what-users-see-in-the-ui
- https://help.daasity.com/extract/integrations/google-analytics-4/api-integration/important-notes
- https://docs.ninjacat.io/docs/troubleshooting-ga4-data-discrepancies
- https://improvado.io/docs/google-analytics-4-troubleshooting
- https://www.merkle.com/en/merkle-now/articles-blogs/2025/navigating-ga4-pitfalls-that-could-derail-your-analytics.html
- https://docs.adriel.com/troubleshooting/numbers-dont-match-source-platform.md
- https://support.rebrandly.com/en/articles/755638-why-don-t-my-rebrandly-numbers-match-other-analytics-tools
- https://help.trackier.com/en/articles/6984073-click-discrepancy-issue-between-trackier-panel-publisher-panel
- https://help.redtrack.io/knowledgebase/kb/conversion-tracking/clicks-inconsistency/

status: ok
