# Research: best practices for classifying first touches into channels

Scope: what changes the design of the `referral_tracking` channel classifier. The reference is
First-Class-LMS `apps/admin_dashboard/channels.py`. The benchmark is the GA4 default channel group.
Statements marked (unverified) come from background knowledge, not a fetched page.

## 1. GA4 default channel group: the rules that matter

GA4 evaluates rules in a fixed listed order and the first match wins. Matching is case-insensitive. No
match gives "Unassigned". [R1]

Manual-traffic order (UTM source/medium/campaign), as listed on the page [R1]:

1. Direct: source exactly `(direct)` and medium `(not set)` or `(none)`.
2. Cross-network: campaign name contains `cross-network`.
3. Paid Shopping: shopping source, or campaign matching `^(.*(([^a-df-z]|^)shop|shopping).*)$`, and a paid medium.
4. Paid Search: source in the search list and a paid medium.
5. Paid Social: source in the social list and a paid medium.
6. Paid Video: source in the video list and a paid medium.
7. Display: medium is `display`, `banner`, `expandable`, `interstitial` or `cpm`.
8. Paid Other: medium matches `^(.*cp.*|ppc|retargeting|paid.*)$`.
9. Organic Shopping.
10. Organic Social: social source, or medium in `social`, `social-network`, `social-media`, `sm`, `social network`, `social media`.
11. Organic Video: video source, or medium `^(.*video.*)$`.
12. Organic Search: search source, or medium exactly `organic`.
13. AI Assistant: medium `ai-assistant` (new, ignorable).
14. Referral: medium `referral`, `app` or `link`.
15. Email: source or medium is `email`, `e-mail`, `e_mail` or `e mail`.
16. Affiliates: medium `affiliate`.
17. Audio: medium `audio`.
18. SMS: source or medium `sms`.
19. Mobile Push: medium ends with `push`, or contains `mobile` or `notification`, or source `firebase`.

Design-relevant points:

- **Paid-ness is a gate on the source, not a channel by itself.** A search or social source with a paid
  medium is paid search or paid social. A paid medium with no known source is "Paid Other". Display
  media come before the generic paid rule.
- **Organic is the fallback for a known source with a non-paid medium.** Medium `organic` alone makes
  Organic Search.
- **Google Ads traffic is classified separately** from ad network and campaign type (Shopping, Video,
  Display, Performance Max and so on) [R1]. We store neither, so a stored first touch cannot reach
  those channels. That is the main reason a nine-channel set is a deliberate reduction of GA4.
- **Source lists are lists of sites/regexes, not exact keys.** GA4 uses Google's source-category
  spreadsheet, which matches variants such as `m.facebook.com` (unverified detail; the page only links
  the list [R1]).
- Direct is only the explicit `(direct)`/`(none)` pair at the UTM stage. In practice GA4 also gives
  Direct when a session has no referrer and no campaign data, because source defaults to `(direct)` and
  medium to `(none)` [R1, R2].

## 2. Click ids

- **gclid** is Google Ads auto-tagging. GA4 with auto-tagging on and Google Ads linked takes the
  Google Ads data over manual UTMs unless "manual tagging overrides" is set (unverified, documented in
  GA4 auto-tagging help [R3]). So in GA4 a click id beats UTM; the reference does the opposite.
- **gbraid / wbraid** are the iOS privacy-era substitutes for gclid (app and web-to-app campaigns).
  GA4 classifies them by campaign type, not as search [R1: "campaign type is used ... for
  GBRAID-tagged traffic"]. A gbraid/wbraid can come from App, Video, Display or Search campaigns, so
  "paid search" is a guess, not a fact.
- **gclid is also not always search.** Performance Max, YouTube, Display and Demand Gen clicks carry
  gclid too. Paid search is the right default for a first-party classifier with no campaign type, but
  the platform must be Google and the basis must say it came from a click id, so the call is visibly an
  inference.
- **fbclid** is appended by Meta to outbound clicks from all its surfaces, organic posts and ads alike.
  GA4 ignores it entirely. It proves only "came from a Meta surface", not paid. Defaulting to organic
  social with a distinct basis (`fbclid only`) is the honest call. Treat "Meta ads without UTM" as
  known under-counting of paid social.
- **msclkid** (Microsoft Advertising auto-tagging), **ttclid** (TikTok ads) and **li_fat_id**
  (LinkedIn Ads, first-party id) are strong paid signals for Bing, TikTok and LinkedIn respectively
  (unverified, vendor docs). `SignupAttribution` stores `gclid`, `gbraid`, `wbraid`, `fbclid` and
  `raw_query` (cap 512) but no `msclkid`/`ttclid`/`li_fat_id` column. The idea says no new capture,
  so these can only be read from `raw_query` if at all. Decision for the spec: either leave them out
  (matches the reference, simplest) or parse them from `raw_query` as extra paid-signal bases. Parsing
  `raw_query` would add a query-string parser to a "pure" classifier; leaving them out is defensible
  and should be stated as a non-goal.

## 3. Normalisation

- GA4 matching is case-insensitive [R1]. Lowercase and strip both `utm_source` and `utm_medium` before
  matching. The reference does this in `classify`. Also collapse whitespace/`+`/`%20` is not needed:
  Django already decodes the query, and the alias sets list the space forms (`e mail`, `social network`).
- Do the same for host matching (lowercase, strip `www.`, port, trailing dot). That belongs to the
  `referral-tracking-referer-host-normalisation` helper the reference depends on.
- Compare sources on the lowercased value, but consider also accepting host-shaped sources
  (`facebook.com`, `l.facebook.com`, `t.co`). The reference uses exact dict keys for `utm_source`
  (`SEARCH_SOURCES`, `SOCIAL_SOURCES`), so `utm_source=facebook.com` or `m.facebook` falls through to
  `other`/medium-only. Reusing the host-suffix `_lookup` for sources that contain a dot is a small
  change that would match GA4's variant handling.
- Treat `(direct)`/`direct` source with `(none)`/`none`/`(not set)` medium as no UTM, then fall
  through (reference `is_direct_pair`). Correct, and GA4 does the same for the pair. Note the reference
  also treats `direct` and `none` (no parentheses) as markers, a harmless widening.

## 4. UTM versus referer precedence

- GA4 gives explicit campaign tags precedence over the referrer for session source/medium [R1, R2].
  The reference follows this: UTM, then click id, then referer, then fbclid, then direct.
- Best practice for a stored first touch: explicit declaration (UTM) over inferred (referer). Keep it.
- A UTM with only a source (no medium), or only a medium, still counts as a UTM touch in the reference
  and ends in `other` if nothing matches. GA4 would equally land in Unassigned or by-source. Defensible:
  a tagged but unclassifiable visit is "other", not "direct".

## 5. Self-referrals and payment gateways

- GA4 does not treat your own domain and subdomains as a new referrer, and cross-domain traffic with the
  `_gl` linker is also exempt [R4]. The Referral Exclusion List marks listed domains so the referrer is
  ignored for attribution (PayPal, Stripe, payment gateways, SSO providers) [R4]. Exclusion affects
  only traffic seen after it was added.
- Relevance here: `SignupAttribution` is captured at first landing, before any checkout, so payment
  gateway round-trips mostly cannot be the first touch. SSO and email-verification round-trips can,
  e.g. `accounts.google.com` or the site's own host.
- Design implication: the classifier is pure and has no site host. Either (a) the caller passes the
  referer already blanked when it is the site's own host (the capture or the referer helper should
  drop self-referrals; this is the right layer, since the first touch should record no referer), or
  (b) the classifier takes an optional `own_hosts` argument. The reference does neither, so a
  self-referral becomes `referral` with basis `referer`. Recommend (a) as a documented precondition,
  or an explicit own-host parameter if the spec wants the classifier to be self-contained.
- Do not add a payment-gateway exclusion table: the project settled on fixed constants with no
  extension, and gateways are not first-touch sources.

## 6. android-app:// referers

- Android apps send `android-app://<package>` as the referer. GA4 treats it as a referral to the
  package name (unverified detail; GA4 shows the source as `android-app://com.example` style).
- The reference maps known packages to a channel and platform, and anything else to `referral`. This is
  a useful, bounded extension of GA4. Two points for the spec:
  - `referer_host` must return the package name for this scheme (the helper handles it, since the
    reference relies on it). The classifier detects the scheme with a prefix check on the raw value.
  - `com.google.android.youtube` as organic social and `com.google.android.googlequicksearchbox` as
    organic search are judgement calls; Google app opening links from search is organic search in GA4
    terms. Keep as is. Search-app and mail-app packages should stay few: the table is fixed.

## 7. Where the reference deviates from GA4, and whether it is defensible

| Area | GA4 | Reference | Verdict |
|---|---|---|---|
| Channel set | ~19 channels | 9 | Defensible: signup reporting, no ad-network data stored. |
| Display, Paid Other, Cross-network, Shopping | own channels | all `other` | Defensible, document that `other` covers them. |
| Video (YouTube, Vimeo) | Paid Video / Organic Video | folded into paid / organic social | Defensible; keeps platform (YouTube) in `source_platform`. Note it in the spec. |
| Affiliate, SMS, push, audio, AI assistant | own channels | affiliate becomes `referral`, the rest `other` | Defensible. `affiliate` as referral is reasonable. |
| Order of Referral vs Email | Referral before Email | Email before Referral | Only differs for odd combinations (source `email`, medium `link`). Harmless; mention in a test. |
| Click id vs UTM | click id (auto-tag) wins | UTM wins | Defensible: UTM is explicit; click id with a UTM means a tagged link or manual override. |
| gclid/gbraid/wbraid | by campaign type | always paid search, Google | Defensible default; the basis marks it as inferred. |
| fbclid | ignored | organic social (Meta), last resort | Defensible and an improvement for signup data; keep distinct basis `fbclid only`. |
| Referer table | source-category list incl. many sites | fixed host tables | Defensible. Known gap: no regional Google coverage beyond `GOOGLE_SEARCH_HOST` regex, no other-language sites. |
| Source matching | list/regex with variants | exact dict keys for `utm_source` | Weak spot: add host-style matching for dotted sources. |
| `x` source | n/a | `x` in `SOCIAL_SOURCES` | Short keys (`x`, `an`, `ig`, `tt`, `fb`, `msg`) are accepted as exact sources; fine because the match is exact, not substring. Never match them as substrings. |
| Paid shopping regex | yes | none | Fine; no shopping channel. |
| Unmatched, no data | Unassigned / Direct | `direct` if the touch is empty; `unknown` only when there is no stored record | Defensible, and the `unknown` vs `direct` split should be spec'd (no record vs empty record). |
| `referral_code` | not a GA4 concept | reference ignores it | The settled answer (referral_code gives Referral) is an addition. Precedence is open, see below. |

Open design points for the spec (not decided in `answers.md`):

- Where `referral_code` sits in the order. A referral code is explicit, first-party intent like UTM,
  but UTM and click ids carry channel meaning. Sensible rule: apply the code only when UTM, click ids
  and referer give nothing (so `referral_code` beats `direct` and `fbclid only`, loses to everything
  else), with the basis value `referral code` (a new `ChannelBasis`). The answer says "no UTM, click ID
  or referer", which matches this; fbclid-only is the unresolved case.
- A new basis value for the code is needed or the basis would lie.
- `has_signal` in the reference should also be revisited because it counts `advert_code` as a signal
  while `classify` ignores it; decide whether the port keeps `has_signal`.

## References

- R1. Google Analytics Help, "Default channel group": https://support.google.com/analytics/answer/9756891
- R2. Google Analytics Help, "Traffic-source dimensions" (source/medium defaults): https://support.google.com/analytics/answer/11242870
- R3. Google Analytics Help, "Auto-tagging" and Google Ads auto-tagging overriding manual tagging: https://support.google.com/google-ads/answer/16193746 (fetched, but the page did not cover gclid/gbraid; the override behaviour is from background knowledge)
- R4. Google Analytics Help, "Identify unwanted referrals" (referral exclusions, self-referrals, `_gl`): https://support.google.com/analytics/answer/10327750
- Reference code: `/home/sheena/workspace/first_class/First-Class-LMS.git/main/apps/admin_dashboard/channels.py`
- FLS model: `/home/sheena/workspace/lms/freedom-ls-worktrees/referral-tracking-marketing-channels/freedom_ls/referral_tracking/models.py`

R2 and the gbraid/msclkid/ttclid/li_fat_id claims were not fetched; check them before the spec quotes them.

status: ok
