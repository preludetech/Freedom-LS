# Research: known complaints about referer/source normalisation

Scope: only what affects a host-normalising helper (strip port, `www.`, trailing dot; read `android-app://` package).

## Findings

1. **Split sources (the core complaint).** Facebook traffic appears as `facebook.com`, `m.facebook.com`, `l.facebook.com` (desktop link shim) and `lm.facebook.com` (mobile link shim), which "fractures your data". Analytics users fix it with a custom channel rule or by grouping hosts, not by host cleaning.
   - Implication: stripping `www.`, port and trailing dot does NOT merge these. Merging Facebook/Google subdomains is a classifier concern (`referral-tracking-marketing-channels`), not this helper's. The spec should say so explicitly, so nobody expects `l.facebook.com` -> `facebook.com` from `normalised_host`. Do not strip arbitrary leading subdomains (it would wrongly merge e.g. `blog.example.com` and `example.com`).
   - Sources: https://www.lovesdata.com/blog/facebook-referrals-in-google-analytics/ , https://www.graphed.com/blog/what-is-mfacebookcom-in-google-analytics

2. **`android-app://` referers.** Android apps opening a site in a webview send a referer starting `android-app://<package>`. Some tools show it as a separate source; GA traditionally lumps it into direct. A helper that parses the URL with a normal host parser gets the package name as the "host" (or nothing, depending on the parser), which is why the idea has a dedicated branch.
   - Implication: return the package name (case preserved or lowercased consistently), keep it distinguishable from web hosts, and tolerate a trailing path. Also expect `android-app://com.google.android.googlequicksearchbox` (Google app), which a classifier may want to map to Google search.
   - Sources: https://hl.thyngster.com/?p=2770 , https://github.com/plausible/analytics/discussions/1337

3. **Stripped or missing referers.** A significant share of Android and app traffic arrives with no referer at all and lands in "direct" regardless of configuration. Referrer-Policy (for example `strict-origin-when-cross-origin`, the browser default) trims the referer to origin only, so the path is lost but the host survives. `no-referrer` and `same-origin` policies remove it altogether.
   - Implication: the helper must accept empty or None input and return empty/None without raising. Never assume a path is present. Host-only referers (`https://google.com/`) must parse the same as full URLs. (Policy behaviour is common browser knowledge; the search returned no direct citation for it. See MDN Referrer-Policy: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy , not fetched.)
   - Source for the lost-referer part: https://github.com/plausible/analytics/discussions/1337

4. **Self-referrals.** Analytics users complain of their own domain (and subdomains, and checkout/payment domains) showing up as a referrer. Google's fix is an exclusion list that matches the listed domain and any subdomains.
   - Implication: comparing against the site's own host is a caller job, but it only works if both sides are normalised the same way (`www.example.com` vs `example.com`, port in dev). The helper being symmetric (usable on the request host as well as the referer) is what makes self-referral checks reliable. Subdomain-aware matching belongs to the caller.
   - Sources: https://support.google.com/analytics/answer/6350128?hl=en , https://support.google.com/analytics/answer/10327750?hl=en , https://bounteous.com/insights/2016/08/11/subdomain-tracking-google-analytics/

5. **IP-address hosts, ports, trailing dots.** The search found no community complaints specific to these. From the idea: ports and trailing dots do split one source into several. Edge cases to decide in the spec, unsourced here:
   - IP hosts (`http://192.168.1.5:8000/`, bracketed IPv6 `[::1]:8000`): port stripping must not break on IPv6 colons; `www.` stripping is irrelevant. Decide whether to return the IP as-is.
   - Lowercase the host (hostnames are case-insensitive).
   - `www.` strip should only remove a leading label (not `wwwexample.com`), and a bare `www.` or `www` should not become empty.
   - Strip a trailing dot before the `www.` check.

## Gaps
No sources found for IP-host or IPv6 handling, or for trailing-dot complaints. Treat the points under item 5 as design suggestions, not documented complaints.

status: ok
