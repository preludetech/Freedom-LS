# Prior art: referer host normalisation

## In this repo

- No done spec covers referer host normalisation. `spec_dd/3. done/` has `referral-links` (2026-09-12), `referral-links-404-with-a-trailing-slash` (2026-10-08) and `apis-for-lead-monitoring-3-referral-data` (2026-11-05). None mentions www, trailing dots, ports or android-app referers (grep found nothing relevant).
- `freedom_ls/referral_tracking/capture.py` stores the raw `Referer` header into `first_touch["referer"]`, run through `sanitise()` with a length cap (lines ~49, 64, 123). It does no host parsing. That matches the idea: the stored value is raw, and comparison is left to the consumers.
- Git log was not checked (the worker has no shell tool). The latest commit on this branch is the spec start, and the done specs above show no earlier attempt.

## First-Class-LMS reference (`apps/lead_forms/referers.py`)

- Two pure functions. `normalised_host` strips, lowercases, drops the port (split on the first `:`), `rstrip(".")`, and removes a leading `www.`. `referer_host` uses `urlsplit`, returns the normalised host for http/https, the lowercased package name for `android-app://`, and `""` for anything else or on `ValueError`.
- Tests (`tests/test_referers.py`) pin these cases:
  - `WWW.Google.COM`, `google.com:8443`, `google.com.` and `www.google.co.za.` normalise to the bare host.
  - `l.facebook.com` is kept as is.
  - `wwwx.com` is untouched, because the prefix is `www.` with the dot.
  - `android-app://com.facebook.katana` gives `com.facebook.katana`, and extra path segments are ignored.
  - `ftp:`, `mailto:`, junk and unterminated IPv6 (`http://[::1`) all give `""`.
- Weak spots to decide on (observations, not known bugs):
  - `split(":", 1)` on a bare IPv6 host would mangle it. `referer_host` avoids this because `urlsplit().hostname` already removes the port and brackets. Only a direct `normalised_host` call with a raw `host:port` string is affected.
  - Only one leading `www.` is stripped, and `www2.` is not.
  - The android-app branch does not strip a trailing dot, which is harmless for package names.
  - `hostname` is already lowercased by `urlsplit`.
- The git history for this file could not be read. If the caller wants to know whether the file changed after its first commit, run `git log` on it in the First-Class-LMS repo.

## Web

- The common cause of one source splitting into several is subdomain variants, not www. Facebook appears as `facebook.com`, `m.facebook.com`, `l.facebook.com` (link shim) and `lm.facebook.com`.
  - https://indulge.digital/intelligence/articles/mysterious-lfacebookcom-referral
  - https://www.lovesdata.com/blog/facebook-referrals-in-google-analytics/
  - https://www.glew.io/articles/what-are-facebook-link-shims-and-how-do-they-affect-your-data
- Matomo issue #4033 (2013) proposed grouping `m.facebook.com` and `lm.facebook.com` under facebook. A search summary did not say whether it was adopted. https://github.com/matomo-org/matomo/issues/4033 (not fetched; the original URL redirects there)
- Matomo forum thread on Facebook and Twitter referrers not being marked as social shows the same pattern: tools solve it with a domain-to-source lookup list, not by stripping prefixes. https://forum.matomo.org/t/where-are-my-facebook-and-twitter-referrers/29734
- Google publishes a source-to-channel list in which `l.facebook.com`, `lm.facebook.com`, `l.instagram.com` and `l.messenger.com` are social (per a single secondary source, so verify against the GA4 docs).
- Not found in search: any write-up on port or trailing-dot splits. Those look rare in real Referer headers, because browsers normally send a bare host and omit default ports. Treat them as defensive handling.
- Not researched in depth: Android app referers. The `android-app://<package>` form comes from the Android `Intent.EXTRA_REFERRER`, which Chrome exposes as the Referer. The First-Class-LMS helper is the only prior art found.

## Takeaways for the spec

- The settled answer (strip only `www.`, leave `m.` and `l.` to suffix matching in the classifier) matches how analytics tools work: normalise lightly and classify by domain list.
- Keep First-Class-LMS's test table as the starting set of cases. Consider adding an IPv6 literal, `www2.`, an uppercase `ANDROID-APP` scheme (`urlsplit` lowercases the scheme) and a `host:port` input to `normalised_host`.

status: ok
