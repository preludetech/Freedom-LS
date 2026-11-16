# Research: UX patterns for the touch timeline and payout list

Topic `ux_patterns` for `referral-attribution-over-time`. The interface is two read-only admin changelists (`AttributionTouchAdmin`, `ConversionAdmin`) plus CSV export, and nothing more. Findings are split into what affiliate tools do, what that implies for a changelist, and gaps in the idea's Requirement 8.

## 1. How affiliate tools present journeys and conversions

- **The conversion is the row, and it is the export unit.** Affiliate platforms treat a conversion or order as one row with the affiliate or code, date, amount and status. CSV export is a button on the filtered view: Audiohook's CPA dashboard exports "your current filtered view" as .csv; Affelios and WooCommerce Affiliates export by date range; Social Snowball's conversions export carries affiliate ID, commission and payout status. The idea's "filter ConversionAdmin by code, export" is this pattern. Source: https://docs.affelios.com/knowledge-base/reporting/reporting , https://docs.audiohook.com/guides-for-advertisers/2Sv53BBoQzCBsaapbXzEXF/cpa-dashboard/4S5eiBazV84RhQMDYd4k2P , https://help.socialsnowball.io/en/articles/8937051-analytics-dashboard-for-advanced-reporting-exports
- **Attribution models are a switch, not a column.** Tools describe first-click, last-click, last non-direct click, linear and position-based as alternative models applied to the same touch data. The idea's side-by-side `first_referral_code` / `last_referral_code` with no winner is the "show both, let the operator choose" form, which is more explicit than most dashboards. Source: https://tapfiliate.com/blog/affiliate-tracking-attribution-models-metrics-gp/ , https://www.modash.io/ko/blog/affiliate-conversion-tracking
- **Journey views are secondary.** Where a touchpoint timeline exists, it hangs off a single conversion or customer (a drill-in), not off the payout list. Search results found no tool exporting touches and conversions together, so a flat per-conversion export with both codes is a reasonable minimum. (Web coverage here was thin; this is a judgment, not a cited norm.)
- **Payout status is usually on the row.** Social Snowball and similar put paid or unpaid on the conversion. The idea deliberately excludes payouts, so an operator reconciling payments will do that outside FLS (spreadsheet). That is a known cost of the scope, not a defect.

## 2. What makes the payout list usable in a Django admin changelist

Existing pattern: `SignupAttributionAdmin` (`freedom_ls/referral_tracking/admin.py:48-78`) uses `date_hierarchy`, `list_filter` on UTM fields, `search_fields`, `list_select_related = ["user"]`, `readonly_fields`, and the three `has_*_permission` returns of `False`. The FLS skills require `SiteAwareExportModelAdmin` plus a `SiteAwareModelResource`, forbid setting `IMPORT_EXPORT_FORMATS` or the formula-escape setting, and use Unfold (`claude_plugins/fls-dev/skills/admin-interface/SKILL.md`, `claude_plugins/django-stack/skills/admin-interface/SKILL.md`). The idea follows all of this.

Specific points for the payout workflow:

1. **Exact-match code filter beats search.** `list_filter` on `first_referral_code` and `last_referral_code` gives a clickable exact filter, but a sidebar list of every distinct code grows without bound and does not scale past a few dozen partners. Options in order of preference: (a) keep the field filters but add a text-input filter (Unfold ships `unfold.contrib.filters` text and dropdown filters; Unfold docs: https://unfoldadmin.com/docs/filters/text-filter/ ), (b) a custom `SimpleListFilter` offering only active `ReferralCode` rows plus an "unmatched text" entry. Plain `search_fields` is a `icontains` match, so searching `AB` also matches `XABY`, which is a payout-accuracy hazard. Using `search_fields = ["=first_referral_code"]` (the `=` prefix is exact, case-insensitive) avoids it. Django docs: https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.ModelAdmin.search_fields
2. **"Code in play" means first OR last.** A partner's payout list is every conversion where the code is first, last, or either, depending on policy. Two separate filters AND together, so "code X as first or last" cannot be expressed with them. A small custom filter, "code appears as first or last" (a `Q` OR), is the single highest-value addition, and it matters most because the idea refuses to choose a rule. Without it the operator exports twice and merges by hand.
3. **A "first and last differ" signal.** The conversions worth review are those where first != last (multi-partner). A boolean computed column or filter ("Credit split") lets the operator see disputes at a glance. It can be done in the queryset without a generic FK query.
4. **Date range for a payout period.** `date_hierarchy = "occurred_at"` drills year/month/day, but a payout period rarely matches a month boundary. Unfold's date-range filter (https://unfoldadmin.com/docs/filters/datetime-filter/ ) or Django's `DateFieldListFilter` ("past 7 days", "this month") is closer to what affiliate tools offer. Use `occurred_at`, not `recorded_at`, which the idea already does.
5. **Export respects the active filter.** django-import-export's admin export has two paths: the "Export" toolbar button and the "Export selected" action. The toolbar export in recent versions offers the current changelist filter as the queryset. Confirm in the spec that the shipped `SiteAwareExportModelAdmin` exports the filtered, not the whole, queryset, because the payout list is defined by filter then export. This is also the Success Criterion. Docs: https://django-import-export.readthedocs.io/en/latest/admin_integration.html
6. **Export columns are the payout contract.** Columns should include `user` (email), `kind`, `target_label`, `occurred_at`, `first_referral_code`, `last_referral_code`, ideally the touch timestamps (`first_touch.occurred_at`, `last_touch.occurred_at`), and a stable conversion `id` so a payer can reconcile and dedupe across exports. The idea omits `site` and exports user by email; `id` and the touch dates are worth stating explicitly. Dehydrating touch dates adds an FK join, so `list_select_related` or a `select_related` on the export queryset is needed (the CLAUDE.md rule).
7. **Counting.** Admins show "N results" but no total. A payout operator wants a count per code. Django admin offers none by default; the filtered "N results (M total)" line is the only cue. Treat per-code totals as out of scope (the idea excludes dashboards) and let the CSV carry it.
8. **Stable default ordering and pagination.** `ordering = ["-occurred_at"]` is set. For payout the operator may prefer ascending by period; list ordering can be changed by clicking the column header, so no change is needed. Set `list_per_page` modestly and note that "Show all" on large tables is expensive (`show_full_result_count = False` avoids the extra COUNT on filtered large tables).
9. **Link touches to conversions.** Since the touch list is the "journey" view, the useful drill-in is touches for one user. Without writing a custom view, a `list_display` link or `list_filter`/search on `user__email` gives it. A read-only conversion detail page that shows `first_touch` and `last_touch` as links (via `readonly_fields` displaying the FK) lets the operator verify a figure. Because the FKs are `PROTECT` and read-only, Django's readonly FK rendering shows a link only when the target model admin has view permission; confirm the touch admin grants view to the same staff group. Avoid `raw_id_fields`-style widgets: they are editable.
10. **Trust cues for ordering.** `recorded_via` is in the touch `list_display`; consider showing `recorded_at` too (hidden by default) so a reader can see flushed versus live ordering, which the idea says is the point of `recorded_via`.
11. **Blank-code rows.** Both codes blank is a legitimate "nothing in play" answer. The admin shows blank as `-`, which is indistinguishable from a missing value. Use `empty_value_display` or a display function ("No code") on the conversion list, and a "has a code / none" filter so payout exports can exclude them in one click.
12. **CSV safety.** The base class already fixes formula-escaping and BOM. Referral codes are hand-typed text, which is precisely the CSV-injection input class, so this protection is genuinely load-bearing here. Reference: https://owasp.org/www-community/attacks/CSV_Injection

## 3. Touch timeline specifics

- A per-user timeline is best served in the changelist by `search_fields = ["=user__email"]` or a filter, ordered by `occurred_at`. A tabular inline on a user is the usual Django answer but would make the user admin editable ground and the idea forbids touching other admins. Leave to search.
- Column choice: the idea includes advert code, referral code, UTM source, UTM campaign. A touch with only UTM data and no referral code shows a blank code column; a filter "has referral code" helps, mirroring the idea's rule that only coded touches count in play.
- `list_filter` on `utm_source` and `utm_campaign` has the same unbounded-sidebar problem as codes.

## 4. Recommendations for the spec (for the lead to accept or reject)

1. Add a combined "code is first or last" filter on `ConversionAdmin`; it is the payout list.
2. Use exact-match search (`=` prefix) on code fields, not `icontains`.
3. State that export honours the active filter, and add `id` and touch timestamps to the export columns.
4. Add a date-range filter in addition to `date_hierarchy`.
5. Show blank codes explicitly and offer a "has a code" filter.
6. Consider `show_full_result_count = False` and bounded filter lists as tables grow.
7. Accept that payout status, per-partner totals and any partner-facing view are out; say so in the docs so operators know to reconcile outside FLS.

## Sources

- https://tapfiliate.com/blog/affiliate-tracking-attribution-models-metrics-gp/
- https://www.modash.io/ko/blog/affiliate-conversion-tracking
- https://docs.affelios.com/knowledge-base/reporting/reporting
- https://docs.audiohook.com/guides-for-advertisers/2Sv53BBoQzCBsaapbXzEXF/cpa-dashboard/4S5eiBazV84RhQMDYd4k2P
- https://help.socialsnowball.io/en/articles/8937051-analytics-dashboard-for-advanced-reporting-exports
- https://docs.djangoproject.com/en/stable/ref/contrib/admin/ (cited from knowledge, not re-fetched this session)
- https://unfoldadmin.com/docs/filters/text-filter/ , https://unfoldadmin.com/docs/filters/datetime-filter/ (cited from knowledge, not re-fetched; verify before relying)
- https://django-import-export.readthedocs.io/en/latest/admin_integration.html (cited from knowledge, not re-fetched; verify filtered-export behaviour)
- https://owasp.org/www-community/attacks/CSV_Injection

Caveat: only the affiliate-tool search was run this session. Django, Unfold and import-export claims are from background knowledge and are flagged for verification in the plan stage.

status: ok · reason: complete
