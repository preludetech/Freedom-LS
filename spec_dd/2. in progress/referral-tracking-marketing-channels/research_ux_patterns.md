# Research: UX patterns for channel attribution in signup reports

## What the tools do

- GA4 default channel group (https://support.google.com/analytics/answer/9756891): Title Case names ("Organic Search", "Paid Social", "Direct", "Referral", "Email"). Direct is the strict pair source `(direct)` with medium `(not set)` or `(none)`. Anything no rule matches is "Unassigned", a separate bucket and not Direct.
- PostHog channel type (https://posthog.com/docs/data/channel-type): Title Case, acronyms upper-case ("SMS", "AI"). Direct needs no referring domain and no UTM medium. "Unknown" is the last fallback. "Paid Unknown" covers paid traffic with no known platform. Both keep paid traffic separate from organic.
- HubSpot original source (page 404'd; recalled from memory, not verified): Sentence case ("Organic search", "Paid social", "Direct traffic", "Offline sources"). It has a second field, "drill-down 1/2", holding the platform or campaign. So channel and platform sit in separate fields.
- Plausible and Matomo (not fetched; from general knowledge, so treat as weak evidence): Plausible shows Channel and Source as separate breakdowns. Matomo's Channel Type report has Websites, Search Engines, Social Networks, Campaigns and Direct Entry. It drills from channel to a named source.

## Patterns that matter for a classifier

1. Casing of labels is not standardised. GA4 and PostHog use Title Case ("Organic Search"). HubSpot and First-Class-LMS use sentence case ("Organic search"). Either is fine if one project picks one. Put the label on the enum (`TextChoices` label), so a report never builds its own wording. Labels stay out of the stored value, and the value stays snake_case.
2. "Unknown" and "Direct" must stay apart. GA4 calls the no-match bucket "Unassigned"; PostHog calls it "Unknown". Direct means "arrived with no signal". Unknown means "no first touch record at all, so we cannot say". Merging them hides missing data inside Direct. The reference keeps `UNKNOWN` (no record) separate from `DIRECT` (a record with no signal). Keep that. Also keep `OTHER` for a signal that matched no rule, as GA4's Unassigned and PostHog's Paid Unknown do.
3. Platform is a separate field from channel. HubSpot's drill-down and Matomo's channel-to-source drill do this. It lets a report group by channel and drill into "Facebook" or "Google". The platform is a display string such as "Google", "Facebook", "LinkedIn", "X". It uses the brand's own casing ("LinkedIn", "YouTube", "TikTok"), not host or utm casing. Empty string means "no platform known", and the report decides how to show that. The classifier should not emit a placeholder like "n/a".
4. Basis is the "why" and is mostly shown in a CSV column or a tooltip, not in a headline chart. Reference values are raw tokens ("utm", "gclid", "referer", "fbclid only", "none"). A person reading a report needs a human label ("UTM tags", "Google click ID", "Referring site", "Facebook click ID only", "No signal"). So the basis enum should carry labels, and the machine value should be a clean token. The reference's `"fbclid only"` has a space and is not a clean token. It also names the weakness (a click ID alone cannot separate paid from organic). Keep that information in the basis. CSV exports should carry the machine value, which is stable for filtering. The on-screen table should carry the label.
5. Grouping and order. GA4 and PostHog list in a fixed order, not alphabetically. Report order is a presentation choice, but an enum defined in a sensible order (Direct, Organic Search, Paid Search, Organic Social, Paid Social, Email, Referral, Other, Unknown) gives a default for `.choices`, so filter dropdowns and breakdown tables agree. Unknown and Other go last. The reference already orders this way. Documenting that the enum order is the display order is the cheap way to give grouping.
6. Filter dropdowns reuse the enum's `.choices`. The reference does this with an "All channels" first entry. The enum should therefore have stable values and no helper-only members.

## Implication for the output shape

- `Channel` (TextChoices): snake_case values, human labels, declared in display order, with `OTHER` and `UNKNOWN` last. Pick one casing (the reference's sentence case is consistent with the existing project report).
- `ChannelBasis` (TextChoices): clean snake_case values (for example `fbclid_only`, not `"fbclid only"`) with human labels, so reports and CSVs do not need a mapping table. Changing a value from the reference is a breaking rename for First-Class-LMS, so the spec should state that.
- `platform`: a plain string in brand casing, empty when unknown. Only one string per result.
- Result is a frozen dataclass of three fields (channel, platform, basis), as in the reference, and needs no extra "explanation" string. The basis label is the explanation.
- Decided: no UI, so no templates, badges or colours belong in the classifier. Label, order and value are all that it needs to supply.
- `referral_code` with no other signal gives Referral. The basis for it needs its own value (for example `referral_code`), because "none" would wrongly say "no signal" for a touch that carried one. This is a spec decision, flagged here because the reference has no basis for it.

status: ok
