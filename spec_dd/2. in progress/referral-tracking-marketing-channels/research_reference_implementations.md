# Research: reference implementations of first-touch channel classification

## 1. Primary reference: First-Class-LMS `apps/admin_dashboard/channels.py`

Files read: `/home/sheena/workspace/first_class/First-Class-LMS.git/main/apps/admin_dashboard/channels.py` and `.../tests/test_channels.py`.

### Shape
- Pure module. Types: `Channel` (TextChoices: direct, organic_search, paid_search, organic_social, paid_social, email, referral, other, unknown), `ChannelBasis` (utm, gclid, referer, "fbclid only", none), frozen dataclasses `FirstTouch` (all strings plus `first_seen`) and `ChannelResult(channel, source_platform, basis)`.
- `FirstTouch.from_record` is the one project tie. It imports the project's `LeadSubmission` and `SignupAttribution`, and copies fields by name using `dataclasses.fields`. This is the only non-pure part. `from_record` pulls Django models into an otherwise pure module.
- `classify(None)` returns UNKNOWN/none. `has_signal()` is a separate helper.

### Rule order (first match wins), in `classify`
1. No record: UNKNOWN.
2. UTM: if `utm_source` or `utm_medium` is non-empty (lowercased and stripped) and the pair is not the "direct pair", go to `_utm_result`. This is final and does not fall through to click IDs or the referer.
3. Direct pair: source in {direct, (direct)} AND medium in {none, (none), (not set)}. It falls through to the next rules, and does not return DIRECT early.
4. gclid, gbraid or wbraid: PAID_SEARCH / Google / basis gclid.
5. Referer: `_referer_result(referer)`, using `referer_host` from the referer-host-normalisation spec.
6. fbclid alone: ORGANIC_SOCIAL / Meta / "fbclid only".
7. Otherwise DIRECT.
- `advert_code` and `referral_code` are never used by `classify`. They only count in `has_signal`. FLS has decided `referral_code` maps to Referral, so this differs from the reference.

### `_utm_result(source, medium)` order
Paid is `PAID_MEDIUM = ^(.*cp.*|ppc|retargeting|paid.*)$`, matched on medium.
1. source in SEARCH_SOURCES and paid: PAID_SEARCH.
2. source in social + video sources and paid: PAID_SOCIAL (video sources are folded into social).
3. medium in DISPLAY_MEDIA {display, banner, expandable, interstitial, cpm}, or paid: OTHER. This is paid with an unknown source.
4. source in SEARCH_SOURCES or medium == "organic": ORGANIC_SEARCH.
5. source in social/video sources, medium in SOCIAL_MEDIA, or medium matches `.*video.*`: ORGANIC_SOCIAL.
6. source or medium in EMAIL_VALUES: EMAIL (platform "Email").
7. medium in {referral, app, link, affiliate}: REFERRAL.
8. Otherwise OTHER.
- UTM matching is exact on lowercased strings. There are no host forms in the source tables, so `utm_source=google.com` or `facebook.com` is not recognised.

### Tables (plain module constants)
- Source-name dicts, name to platform label: SEARCH_SOURCES (15), SOCIAL_SOURCES (22, including aliases fb/ig/tt/an/msg/x/twitter), VIDEO_SOURCES (4).
- Host dicts: SEARCH_HOSTS, SOCIAL_HOSTS, VIDEO_HOSTS, EMAIL_HOSTS (Gmail, Yahoo Mail, Outlook), plus `GOOGLE_SEARCH_HOST = ^google\.([a-z]{2,3}|co\.[a-z]{2})$` and `APP_PACKAGES` (Android package to channel and platform).
- Host matching is `host == listed or host.endswith("." + listed)`. This is a label-boundary suffix match, so `box.com` is not `x.com` and `ghost.co` is not `t.co`. Tests cover both.
- Referer rule order (`_referer_result`): no host gives None. An `android-app://` scheme looks up APP_PACKAGES, with default REFERRAL. Then EMAIL_HOSTS, then the Google regex, then SEARCH_HOSTS, SOCIAL_HOSTS and VIDEO_HOSTS (video counts as ORGANIC_SOCIAL). Anything else is REFERRAL with no platform.
- Referer-derived results are always organic. A referer never produces a paid channel.

### Edge cases covered by tests
- A parametrised UTM table of about 37 rows. It covers case insensitivity (`GOOGLE`/`CPC`), paid vs organic per platform, the `an`/`msg`/`fb`/`ig`/`tt` aliases, `x` and `twitter` mapping to X, empty source with a medium (`organic`, `sm`, `social media`, `video`), the `partner`+`banana` and bare `brochure` OTHER cases, and `tt`+`referral` giving ORGANIC_SOCIAL (not REFERRAL).
- `is_direct_pair` truth table: `direct`+`""` is not direct, `""`+`none` is not direct, `direct`+`email` is not direct.
- Direct pair falls through to a click ID and to the referer.
- gclid, gbraid and wbraid each give PAID_SEARCH. UTM beats a click ID. A click ID beats the referer. The referer beats fbclid. fbclid alone gives ORGANIC_SOCIAL/Meta.
- Subdomain referers (`l.`, `lm.`, `m.facebook.com`, `l.instagram.com`, `vm.tiktok.com`, `search.yahoo.com`), the `google.co.za` TLD, `accounts.google.com` and `docs.google.com` giving REFERRAL (not search), and the lookalike hosts `box.com` and `ghost.co`.
- Android app referers (listed and unlisted), an unparseable referer giving DIRECT, no signal giving DIRECT, and None giving UNKNOWN.
- A DB test checks `from_record`.

### Fragile points / gaps
1. `_lookup` iterates dict insertion order and returns the first match. Today it is safe only because no listed host is a suffix of another listed host, and nothing enforces this. Adding e.g. `google.com` to a table, or `mail.google.com` after a broader entry, would silently depend on order. EMAIL_HOSTS is checked first for that reason. A longest-suffix match, or a test asserting no table entry is a suffix of another, would remove the risk.
2. `GOOGLE_SEARCH_HOST` is matched against the whole host. The `www.` prefix is therefore assumed already stripped by `referer_host`, so the module depends on that normalisation. The country-code part `[a-z]{2,3}` also matches `google.com`, `google.org` and `google.dev`. `google.co.za` works via `co\.[a-z]{2}`, but `google.com.au`, `google.com.br` and `google.com.mx` fail it, because the regex has no `com.xx` form. They fall to REFERRAL, and the tests do not cover this. `google.com.au` is a real gap (the Matomo `{}` convention treats `com.*` as a country suffix). Other engines' regional hosts (`yahoo.co.uk`, `yandex.ua`, `bing` is fine) are not covered either, as there is no wildcard for non-Google engines.
3. `SEARCH_HOSTS` has Google only as four product subdomains (search, lens, news, play). `news.google.com` and `play.google.com` as ORGANIC_SEARCH is debatable.
4. `OTHER` for paid-with-unknown-source (rule 3) merges display ads, paid media with an unknown source, and anything unrecognised. A paid medium on an unknown source is not told apart from a mistyped medium. GA4 uses "Paid Other" and "Display" separately, and PostHog has "Paid Unknown".
5. `PAID_MEDIUM` uses `.*cp.*`. That also matches `cpc`, `cpm`, `cpv`, `cpa`, but also any medium containing "cp", e.g. `webcpage` or `scp`. It is the GA4 regex. A medium of `cpm` is both paid and display, so `("tiktok","cpm")` is PAID_SOCIAL but `("somesite","cpm")` is OTHER, as the tests show.
6. The click-ID rule runs after UTM, so `utm_source=newsletter&gclid=x` is Email, as tested (a deliberate choice). A gclid with `utm_medium=email` is handled the same way. Also, any UTM at all (even junk like `utm_source=brochure`) blocks gclid and referer detection and ends as OTHER.
7. `fbclid` alone is ORGANIC_SOCIAL, though fbclid is also added to paid Meta ad URLs when no UTMs are set. The basis `fbclid only` records the guess.
8. The `x` source alias is a 1-letter name, and `an`, `ig`, `tt`, `line`, `ask` and `msg` are short, generic names. A `utm_source=line` or `ask` from a partner would be misclassified.
9. `fields(cls)` is used to copy attributes, so any field added to `FirstTouch` must exist on both source models.
10. Video referers (YouTube) are ORGANIC_SOCIAL, and `com.google.android.youtube` is social. GA4 and PostHog use a separate Video channel. The reference has no AI, SMS, Push, Audio or Shopping channels.
11. APP_PACKAGES uses `referer_host` of an `android-app://` URL, so host extraction for that scheme matters (in the referer-host spec).

## 2. Open-source and vendor comparisons

### Matomo (searchengine-and-social-list)
- URL: https://github.com/matomo-org/searchengine-and-social-list
- The data is in YAML files: `SearchEngines.yml`, `Socials.yml`, `AIAssistants.yml`. Each entry has a name and URLs. Search engines also carry keyword parameters, regexes, backlink patterns and charsets.
- Instructions say to define hostnames only. A `{}` placeholder stands for country codes in a subdomain (`{}.searchengine.com`) or in a TLD (`searchengine.{}`). In a TLD position `{}` also matches combined suffixes such as `co.uk` (the README lists `com.*`, `org.*`, `net.*`, `co.*`, `it.*`, `edu.*`).
- The first URL listed is used for the icon and backlink generation.
- It classifies referers only (medium: search, social, website, campaign, direct). Matomo does not map to a paid/organic channel group in this list.

### Snowplow referer-parser
- URL: https://github.com/snowplow-referer-parser/referer-parser
- `referers.yml` has top-level mediums (unknown, email, social, search, plus `chatbot` in the 5.3 database). Each medium lists providers, with their domains (and search-term parameters).
- Docs do not state how subdomains or country TLDs are matched. Country domains appear to be listed individually. The file is derived from Matomo's lists (GPLv3). `referers-5.3` is updated daily, and `referers-latest` is frozen at July 2025. The data is shared across the language ports of the library.
- Referer-only, with no paid classification and no UTM logic.

### PostHog channel type
- URL: https://posthog.com/docs/data/channel-type
- The input is a referring domain, UTM fields, and gclid/`gad_source`. It has an ordered list of 42 first-match rules.
- Paid is defined by: `utm_medium` in {cpc, cpm, cpv, cpa, ppc, retargeting}, or starting with `paid`, or a gclid or `gad_source` present. Paid rules run first (cross-network campaign, then source in search/social/video/shopping lists, then referring domain in the same lists, shop regex, social/video mediums, display, `gad_source=1`, video campaign regex, "Paid Unknown" as the catch-all).
- Direct comes next (domain `$direct`, no medium, and source empty/direct/(direct)), then the organic rules (search, AI, social, video, shopping, email, SMS, push by source, then by referring domain, then by medium and campaign). Referral is "domain present and not direct, and nothing earlier matched". Final fallback is Unknown.
- Lists live in a data file, `channel_definitions.json`, in the PostHog source. The docs do not say whether subdomains are matched or whether matching is case-sensitive.
- Differences from the reference: a paid signal (gclid) is checked before any referer, but paid status does not require known platform sources, so there is a "Paid Unknown" bucket where the reference uses OTHER. AI, SMS, Push, Audio and Affiliate channels exist.

### GA4 default channel group
- URL: https://support.google.com/analytics/answer/9756891
- For manual (UTM) traffic the rules are: Direct, Cross-network, Paid Shopping, Paid Search, Paid Social, Paid Video, Display, Paid Other (a paid medium with no known source), then Organic Shopping, Organic Social, Organic Video, Organic Search, AI Assistant, Referral, Email, Affiliates, Audio, SMS, Mobile Push, and unassigned if nothing matches. The reference's `_utm_result` is a trimmed copy of this order.
- The paid-medium pattern is the `^(.*cp.*|ppc|retargeting|paid.*)$` regex copied by the reference. The Direct rule is source "(direct)" with medium "(not set)" or "(none)", again as in the reference. Matching is case-insensitive.
- Google Ads, DV360, CM360 and SA360 traffic is classified from the ad platform's own data, which has no analogue for FLS.
- The source category lists (search, social, video, shopping) come from a Google-maintained spreadsheet reviewed at least yearly, and are not public in code.

### Plausible
- Source code: https://github.com/plausible/analytics/blob/master/lib/plausible/ingestion/source.ex. That file covers source only, not channels.
- Source resolution: `utm_source`, then `source`, then `ref` parameters, then the referer (http, https or android-app scheme only, non-empty host, not the site's own host or localhost). The referer host is trimmed, lowercased and stripped of `www.`.
- Referer lookup order: exact host in `priv/custom_sources.json`, then suffix match for known domain families (a host and all its subdomains), then RefInspector with `priv/ref_inspector/referers.yml`, then the bare host. Custom overrides come first so `gemini.google.com` can beat `google.com`.
- Paid sources are derived from `custom_sources.json` keys ending in "ads" or "ad" (plus "adwords"). The Channels tab rules were not confirmed in an official source. A mirrored docs page says the channel lists follow GA closely. Treat the channel rules as unverified (I did not find a primary source).
- Matches the Matomo/Snowplow approach: YAML/JSON data files, plus exact-then-suffix matching, with specific overrides ahead of generic entries.

## 3. Summary of design comparisons

| Concern | First-Class-LMS | Matomo | Snowplow | PostHog | GA4 | Plausible |
|---|---|---|---|---|---|---|
| Host lists as data files | No, Python dict constants | YAML | YAML | JSON | Google spreadsheet | YAML + JSON |
| Subdomains | label-boundary suffix match | explicit `{}` or list host | not documented | not documented | not documented | exact, then suffix, then lookup |
| Country TLDs | one Google regex, nothing else | `{}` placeholder (`co.*`, `com.*` too) | listed individually | not documented | not documented | listed in YAML |
| Rule order | explicit, first match | n/a | n/a | explicit, 42 rules | explicit | n/a |
| Paid with unknown source | OTHER | n/a | n/a | Paid Unknown | Paid Other | derived from "ads" source names |
| Click IDs | gclid/gbraid/wbraid after UTM | n/a | n/a | gclid and gad_source = paid | autotag via ads link | n/a |

### Takeaways for FLS
- The reference follows the GA4 manual-traffic rules in a simplified form. Its ordering (UTM, click ID, referer, fbclid, direct) is the part to keep, and FLS adds `referral_code` to Referral (per answers.md).
- Where to put `referral_code` in the order is open: after the referer and fbclid steps and before the final DIRECT is the least disruptive for the reference's rules.
- Tests worth carrying over: the UTM table, the direct-pair fall-through cases, the lookalike hosts (`box.com`, `ghost.co`), the precedence tests, and Android app referers.
- Add tests the reference lacks: `google.com.au`/`google.com.br`, a "no table entry is a suffix of another entry" invariant (or longest-match lookup), `www.` and mixed-case referers, `utm_source` given as a host (`facebook.com`), and each of `x`/`ask`/`line`/`ig` as a generic UTM source.
- The tables are fixed constants with no project extension (per answers.md), so they could stay as Python dicts. The established reference projects keep these tables in data files (Matomo YAML, PostHog JSON), with `{}`-style placeholders for country variants, so the data and the rules could be separated.
- `from_record` ties the reference to two project models. FLS should build the touch from `SignupAttribution` in `referral_tracking`.

status: ok
