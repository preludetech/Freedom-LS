# Research: known complaints about channel classification / attribution reporting

Scope: what changes the design of a pure first-touch classifier in `referral_tracking`. Module only, no UI;
`referral_code` maps to Referral; `advert_code` ignored; fixed host tables (see answers.md). The reference
is First-Class-LMS `apps/admin_dashboard/channels.py` (read in full).

Evidence quality: the GA4 points come from Google's own help page and practitioner write-ups. The Facebook
in-app-browser points come mostly from vendor blogs, so treat them as unverified. I did not find any source
saying whether `l.facebook.com` or `lm.facebook.com` preserves or strips the original referer.

## Complaints, and whether a classifier can mitigate them

| # | Complaint | Mitigable by a classifier? | Design consequence |
|---|---|---|---|
| 1 | GA4 "Unassigned": traffic that matches no rule. The commonly cited cause is a custom or invalid `utm_medium`, such as a mailer tool tagged with a made-up medium, which then lands in Unassigned instead of Email. | Partly. The reference has a catch-all `Channel.OTHER` for a UTM that matches no rule. | Keep `OTHER`, separate from `DIRECT` and `UNKNOWN`. Users confuse "Unassigned" with "Direct", so the three need distinct, documented meanings. The reference also lets a source-only UTM such as `utm_source=newsletter` fall to `OTHER`, so an email tool with a custom source is not recognised. Fixed tables mean the fix is "tag with standard mediums", and that belongs in the docs. |
| 2 | Too much Direct. Direct is a residual bucket for "no referrer and no tags", not proof of typed or bookmarked visits. Causes: `Referrer-Policy`, https to http, in-app browsers, messaging apps, stripped params. | No. The classifier cannot recover a signal that was never stored. | Document that `DIRECT` means "no signal captured", not "typed the URL". Do not claim more. The reference returns `DIRECT` with basis `none`, so the basis field is what carries the honesty. |
| 3 | Dark social (WhatsApp, Slack, Messenger, SMS, email clients without a referer). No referer, so it appears as Direct. | No. | Only a UTM or a `referral_code` on the shared link helps, and `referral_code` is the one signal FLS can add. The Referral mapping decided in answers.md is the useful mitigation: a shared invite link is classified Referral rather than Direct. |
| 4 | Facebook in-app browser traffic arrives with `fbclid` but no UTM and often no referer. | Partly. | The reference's `FBCLID_ONLY` basis returns `ORGANIC_SOCIAL`/Meta. `fbclid` is also appended to organic outbound clicks, so it cannot tell paid from organic. Calling it organic is a guess, and the basis string says so. Keep the weak basis so reports can show "inferred". Paid Meta traffic is only reliably `PAID_SOCIAL` when the advertiser tags `utm_medium=paid...` (a gap, see item 6). |
| 5 | Mis-cased or whitespace-varied UTMs split rows ("Facebook" vs "facebook" vs "fb"). | Yes. | Lower-case and strip source and medium before matching, as the reference does. Alias tables (`fb`, `ig`, `tt`) collapse variants into one platform. Normalise the platform to a canonical display name, never echo the raw `utm_source`. |
| 6 | Paid detection misses custom mediums (`cpc` is caught, but `boosted`, `sponsored`, `promo`, `ads` are not). Reference regex is `.*cp.*`, `ppc`, `retargeting`, `paid.*`. | Partly. | The regex also over-matches: anything containing "cp" (for example `webcp`) counts as paid. Fixed tables mean the wrapper is where a project handles its own mediums. Document the exact paid rule. Consider `cpc`, `ppc`, `paid*`, `cpm` and `retargeting` as an explicit list rather than a loose substring. |
| 7 | `gclid`, `gbraid` and `wbraid` mean Google Ads, but the click ID alone does not distinguish Search from Display, YouTube or Shopping. The reference calls all of it `PAID_SEARCH`/Google. | Partly. | Call it a known approximation. `basis=gclid` flags it. Order matters: a UTM wins over a click ID, and a click ID wins over the referer. Auto-tagging can also overwrite manual UTMs in some setups, so a UTM-first order is a policy choice to state explicitly. |
| 8 | Email: webmail clients send a referer from the mail host (`mail.google.com`, `outlook.live.com`), while desktop and mobile clients send none. Newsletter links are routinely Direct. | Partly. | The reference's `EMAIL_HOSTS` table is short. `outlook.office.com`, `outlook.office365.com`, `mail.yahoo.com` subdomains and `mail.proton.me` are missing. Email is only reliable when the link carries `utm_medium=email`. Check the table against the answers.md decision that it is fixed. |
| 9 | Instagram and LinkedIn app referers: `l.instagram.com`, `lnkd.in`, `linkedin.com` mobile, and `android-app://com.instagram.android`. | Yes, with a table. | Suffix-matching (`_matches`) handles `l.` and `lm.facebook.com` subdomains, and `android-app://` packages need their own table (reference has `APP_PACKAGES`). Unknown packages should fall to `REFERRAL` with an empty platform. Android package names can change, so this table will age. |
| 10 | `l.facebook.com` and `lm.facebook.com` are Facebook's outbound link shim, so the referer is the shim host, not the page. | Yes, by suffix match on `facebook.com`. | A suffix match resolves them. No special case needed, but a test should pin it. Whether the shim keeps a referer at all is unverified, and that is why complaint 4 exists. |
| 11 | Self-referrals: the visitor's own site or subdomains appear as a referrer, for example after a login redirect or from a marketing site to the app. | No. The classifier is pure and does not know the site's host. | The reference does not handle this: a first touch whose referer is the project's own host classifies as `REFERRAL`. The first touch should be captured on the first request, so a self-referral should not normally be stored. If it can be, a wrapper filters it before calling `classify`. State this as a precondition, not a feature, since FLS captures no new data. |
| 12 | Payment gateways and identity providers (PayPal, Stripe, 3-D Secure, Google/Microsoft sign-in) steal attribution when the visitor returns. GA4 needs a manual "unwanted referrals" list. | Mostly no for first touch. | These matter for last-touch or session attribution. For a first touch recorded at landing, the return trip is not the first touch. Do not build a gateway exclusion list. Mention it in docs so nobody asks for it. |
| 13 | A reported channel disagrees with the ad platform (Meta or Google Ads report more clicks than analytics) because of in-app browsers, consent and blockers. | No. | Out of scope. Not a classifier defect, but the docs should state that the output is "best inference from stored fields". |
| 14 | A mutating or silently changing taxonomy: when channel rules change, historical reports shift. | Yes, by design. | The classifier is pure and computed at read time. Treat `Channel` values and basis strings as a stable contract and add new values rarely. If `Channel` is stored by a project, renaming a value breaks it. The reference's `ChannelBasis.FBCLID_ONLY = "fbclid only"` contains a space, an awkward stored value. Prefer a snake_case value such as `fbclid_only`. |

## Decisions the findings support

1. Keep the output as a triple of channel, platform and basis. The basis is what lets a reader tell a hard signal (UTM) from an inference (`fbclid` only, `gclid`).
2. Keep `OTHER` (tagged but unrecognised) distinct from `DIRECT` (no signal) and `UNKNOWN` (no record). This directly answers the "Unassigned vs Direct" confusion.
3. Normalise case and whitespace before matching, and map aliases to canonical platform names.
4. Make the paid-medium rule an explicit list or tight pattern, and document it. The reference's `.*cp.*` over-matches.
5. Match hosts by suffix (handles `l.facebook.com`, `lm.facebook.com`, `l.instagram.com`) and handle `android-app://` packages with an unknown-package fallback of Referral.
6. `referral_code` with no other signal gives Referral. Decide the precedence of this rule against UTM, click ID and referer: it fits last, where the reference returns Direct. A `referral_code` should arguably not override a real UTM or referer.
7. Document the limits: Direct is "no signal", dark social and gateway or self-referral effects are not recoverable, and `fbclid`-only and `gclid` are inferences.
8. Check the reference tables against the reference's own gaps (Outlook business hosts, `l.instagram.com`, Telegram, Proton Mail) before copying them in, since tables are fixed once shipped.

## Sources

- GA4 tagging best practices to avoid unassigned, (not set) and direct traffic: https://support.google.com/analytics/answer/14847402?hl=en
- Analytics Mania, Unassigned in GA4: https://www.analyticsmania.com/post/unassigned-in-google-analytics-4/
- Search Engine Land, fix unassigned traffic: https://searchengineland.com/fix-unassigned-traffic-ga4-433239
- Bounteous, GA4 attribution issues: https://www.bounteous.com/insights/2025/12/05/ga4-attribution-issues-explained-not-set-unassigned-and-more/
- Wikipedia, Dark social media: https://en.wikipedia.org/wiki/Dark_social_media
- Meta, fbp and fbc / click ID parameters: https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/fbp-and-fbc
- SegmentStream, click propagation and attribution accuracy: https://segmentstream.com/blog/articles/what-is-click-propagation-and-how-it-impacts-marketing-attribution-accuracy
- Adobe community, in-app browser and dark social: https://experienceleaguecommunities.adobe.com/adobe-analytics-3/in-app-browser-tracking-adobe-analytics-dark-social-90779
- URLgeni.us, in-app browsers and ad ROI (vendor, unverified): https://app.urlgeni.us/blog/how-in-app-browser-hurts-roi
- GA4 referral exclusion (payment gateways, self-referrals): https://optimizesmart.com/blog/self-referral-google-analytics-4-referral-exclusion-ga4/ and https://analytify.io/ga4-referral-exclusion/

status: ok
