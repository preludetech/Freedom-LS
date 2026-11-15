# Research: reference implementations of referer host normalisation

Topic: `reference_implementations`. Question: how do reference implementations normalise referer hosts?

## 1. First-Class-LMS (the stated reference)

Files: `/home/sheena/workspace/first_class/First-Class-LMS.git/main/apps/lead_forms/referers.py` and `.../apps/lead_forms/tests/test_referers.py`.

Behaviour:
- `normalised_host(host)`: strip whitespace, lowercase, cut at the first `:` (port), `rstrip(".")`, drop one leading `www.`.
- `referer_host(referer)`: `urlsplit(referer.strip())`, catch `ValueError` and return `""`. For `http`/`https` return `normalised_host(hostname)` (or `""` if no hostname). For `android-app` return `hostname.lower()` (the package name). Any other scheme returns `""`.

Tests cover: `WWW.Google.COM`, port, trailing dot, `www.google.co.za.`, `l.facebook.com` kept, `wwwx.com` not stripped, empty string; and for `referer_host`: https www, http with port and uppercase, `android-app://com.facebook.katana`, an android-app URL with a path, `ftp://`, `mailto:`, `not a url`, `http://[::1` (the ValueError path), empty.

### Bugs and gaps in the FCL reference
1. IPv6 hosts are broken. `urlsplit("http://[::1]/").hostname` is `::1`, and `normalised_host` then splits on the first `:` and returns `""`. A direct call with `[::1]:80` returns `[`. The test only covers the malformed `http://[::1`. The result `""` is harmless as "no source", but it is accidental, not designed. The port should be taken from `urlsplit` (`.hostname` already excludes it) and not by string-splitting.
2. `normalised_host` is a public helper that does its own port splitting, but `referer_host` never needs that, because `.hostname` already drops the port and userinfo. The port logic only matters for direct callers passing a raw `Host`-style string. Decide whether the helper is public or internal.
3. Only one `www.` is stripped (`www.www.x.com` becomes `www.x.com`). Fine, but undocumented.
4. A host that is just `www.` (or `www`-only after dot-stripping) gives `""` after the strip, so a degenerate host and "no host" are indistinguishable. Strip `www.` only if something remains.
5. `android-app` is lowercased only, with no trailing-dot or empty-package handling. `android-app:///path` returns `""` (fine). The path is discarded. For `android-app://com.google.android.googlequicksearchbox/https/www.google.com` the path carries the real web origin (Google web search), which is lost. That is a conscious trade-off, but it should be written down. The classifier then has to map the package name to a channel.
6. No IDN/punycode handling. `urlsplit` does not decode `xn--` labels, so Unicode and punycode forms of one host would split into two sources.
7. Scheme-less referers (`google.com/x`) and protocol-relative (`//google.com`) return `""`. Browsers always send absolute referers, so this is acceptable but should be stated.
8. `urlsplit(...).hostname` can still raise `ValueError` on some malformed inputs (for example bad bracketed hosts). The `try` wraps it, which is correct. Note that `.port` is never read, so an invalid port such as `http://a:abc/` does not raise and still yields `a`.
9. Mixed-case schemes are fine, because `urlsplit` lowercases the scheme.

## 2. Plausible (Elixir) — `lib/plausible/ingestion/source.ex`
URL: https://raw.githubusercontent.com/plausible/analytics/master/lib/plausible/ingestion/source.ex
- `format_referrer_host`: `String.replace_prefix(uri.host, "www.", "")`. This strips only a leading `www.`, nothing else (so `m.` and `l.` stay). Same decision as our answers.md.
- Ports are dropped implicitly (`uri.host` excludes the port). Trailing dots are NOT handled.
- Accepted schemes: `http`, `https`, `android-app`. For `android-app` the result is prefixed `android-app://` (so the package name stays distinct from web hosts). The source is looked up case-insensitively, but the unknown-host fallback returns the original-case host.
- Order: `utm_source`/`source`/`ref` query params first, then custom sources by exact host, then suffix match (`host == suffix or ends_with "." <> suffix`) for a few domains, then the RefInspector database (Snowplow/Matomo-derived `referers.yml`), then fall back to the host.
- Filters: the referer is rejected if its host equals the request's own host (after sanitising), if it is `localhost`, or if the scheme is not allowed.
- Gap: the Google Analytics import path skips the validity check, so a nil host could crash.
- Related discussion (Android traffic seen as direct, `com.google.android.googlequicksearchbox` for Google Discover): https://github.com/plausible/analytics/discussions/1337

## 3. Snowplow referer-parser
Repo: https://github.com/snowplow-referer-parser/referer-parser (shared `referers.yml`); Python implementation read at https://raw.githubusercontent.com/snowplow-referer-parser/python-referer-parser/master/referer_parser/__init__.py
- Parses with `urlparse`; only `http`/`https` with a hostname are considered. No `www` strip and no explicit port or trailing-dot handling (`.hostname` drops the port).
- Matching is by suffix fallback: look up the full host, then remove the leftmost label and retry until no dot remains. So `www.google.com` and `m.facebook.com` resolve to the parent-domain entry. This is the same "match by suffix" idea that answers.md relies on for the classifier.
- Each pass tries host+path, host+first path segment, then bare host; the path-aware pass runs through all parents before the host-only pass (a quirk: a path rule on a parent can beat an exact host-only entry).
- Internal detection compares the current host to the referer host exactly, so `www.example.com` vs `example.com` is NOT internal. This is a known weakness that normalisation fixes.
- Non-matching hosts give medium `unknown`. No `android-app` support.

## 4. Matomo
Sources: `plugins/Referrers/Columns/Base.php` (https://raw.githubusercontent.com/matomo-org/matomo/5.x-dev/plugins/Referrers/Columns/Base.php); list repo https://github.com/matomo-org/searchengine-and-social-list ; changelog bug on custom engine with the tracked domain https://matomo.org/changelog/piwik-2-16-2/
- Host comes straight from `parse_url`. No `www` strip in this file. Lowercasing happens when naming a website referrer (`mb_strtolower($host)`). Same-host direct-entry check lowercases both hosts.
- Domain matching is delegated to the `SearchEngine` and `SocialNetwork` lists (enumerated hosts and URL patterns), and to `SiteUrls` for "is this our own site". `www` handling lives there (not read here).
- Order: AI assistant, campaign (`utm_*`), direct entry, search engine, social, then generic website. Referer is dropped if it does not look like a URL.
- Truncates names to 255 characters, strips tracking params from the referer URL, and keeps a non-root path in the website name.
- No android-app handling in Referrers.
- Edge-case history: a custom search engine on the tracked domain was not detected (fixed in 2.16.2), which shows the order-of-checks hazard between "own site" and "known source".

## 5. GA4 and `android-app://`
- Google documents no host-normalisation rules. Observed behaviour: GA treats Android-app referers (`android-app://<package>`) inconsistently; much Android traffic ends up `(direct)`. Install referrals from Google Play appear as `google-play`. See https://support.google.com/analytics/answer/10311900 and https://github.com/plausible/analytics/discussions/1337 .
- I found no GA4 documentation that says how `android-app://com.google.android.gm` is recorded. Treat it as unverified. Do not rely on GA4 as a reference for this.
- The Adobe thread shows the same ambiguity for `android-app://com.google.android.googlequicksearchbox` (search vs no referer): https://experienceleaguecommunities.adobe.com/adobe-experience-platform-18/google-search-app-referrer-android-app-com-google-android-googlequicksearchbox-113722

## Takeaways for the spec
- Consensus on `www.`: Plausible strips only a leading `www.`; Snowplow and Matomo do not strip but rely on suffix matching. FCL plus Plausible agree with answers.md.
- Trailing dot is handled only by FCL. Keep it, and add a test.
- Port: use `urlsplit().hostname`, not string splitting, which avoids the FCL IPv6 bug. Add a test for `http://[::1]:8080/`, and decide whether the result is `""` or `::1`.
- android-app: Plausible keeps the `android-app://` prefix to keep package names distinct from web hosts. FCL returns the bare package name. A package name like `com.facebook.katana` does look like a domain, so the classifier must know which kind it has been given. Consider whether the raw package could collide with a real host.
- Matching own host: Snowplow and Matomo show that exact comparison without normalisation misses `www` versus bare. Normalising both sides is the fix.
- IDN, userinfo (`http://user@host`), and uppercase scheme are cheap test cases that no reference covers.

status: ok
