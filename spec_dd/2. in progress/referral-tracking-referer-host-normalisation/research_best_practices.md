# Research: best practices for normalising a Referer into a comparable host

Sources: Python urllib.parse docs (https://docs.python.org/3/library/urllib.parse.html), WHATWG URL Standard host parsing (https://url.spec.whatwg.org/#host-parsing), Android Intent EXTRA_REFERRER (https://developer.android.com/reference/android/content/Intent#EXTRA_REFERRER; page was truncated when fetched, so the android-app format below is from general API knowledge).

## Python urllib.parse facts

- `urlsplit()` does not validate. It may return empty or `None` parts instead of raising, so the caller must check scheme and hostname.
- `urlsplit()` itself raises `ValueError` for unmatched `[`/`]` in the netloc, and (3.8+) for netloc characters that NFKC-decompose to `/ ? # @ :`. Wrap the call in try/except. The reference does this.
- `.port` raises `ValueError` for a non-numeric or out-of-range port. `.hostname` does not read the port, so using `.hostname` and ignoring `.port` is safe. Never touch `.port` just to strip it.
- `.hostname` is lowercased, has brackets stripped from IPv6 literals, and excludes userinfo (it takes the text after the last `@`) and the port. So `urlsplit(...).hostname` already does most of the port, userinfo, case and IPv6 work. The reference's `":" in lowered` split in `normalised_host` is only right for names. It would break a bare IPv6 literal such as `::1` (it returns `""`). It is safe only because `referer_host` passes in `.hostname`.
- Leading C0 controls and spaces are stripped (3.12+), and `\n`, `\r` and tab are removed anywhere (3.10+). Percent-escapes are not decoded.
- `hostname` is `None` for `http:///path`, `http:path`, or a value with no scheme (a bare `google.com` parses as a path). The reference returns `""` for these.
- Scheme matching: `urlsplit` lowercases the scheme, so `HTTP://` matches `{"http", "https"}`.

## Normalisation rules (practice)

1. Lowercase. DNS names are case-insensitive, and the WHATWG standard lowercases ASCII hosts.
2. Drop the port by using `.hostname` (not string splitting). Treat `:443` and `:80` as noise for grouping.
3. Strip one trailing dot. A FQDN root dot is semantically the same name. WHATWG keeps the dot, so URL-level equality does not ignore it. For grouping, stripping is the usual choice. `rstrip(".")` strips several dots, so `google.com..` also folds. Use `removesuffix(".")` if only one is wanted, but multi-dot input is malformed either way.
4. Strip a leading `www.` only as a heuristic that is applied after stripping the trailing dot. Do not strip other subdomains. `www.` alone, or a host that becomes empty, needs a guard. The reference turns `www.` into `""`.
5. IPv6 literals: `.hostname` returns them without brackets and lowercased. Do not strip a port with `split(":")` on a bare host. Either skip `www.`/dot logic for IP literals or accept it as harmless.
6. IDN: the Referer header is normally already punycode (`xn--...`) because browsers send the ASCII form, but a non-ASCII host can appear. WHATWG applies UTS #46 ToASCII (percent-decode, then IDNA). A comparable key can be produced with `host.encode("idna")`. That is IDNA 2003, so `idna`-library UTS46 handling is more accurate, and it raises `UnicodeError` on bad labels. The best practice is to convert to ASCII/punycode, catch `UnicodeError` and keep the lowercased input (or return `""`). Skipping it is acceptable if stored referers are always browser-sent. Decide this explicitly.
7. Userinfo (`user:pass@host`): `.hostname` drops it. It is almost never present in a browser Referer, because browsers strip credentials. Do not store or log it.
8. Percent-encoding in the host: WHATWG decodes it before IDNA. `urlsplit` does not. Treating a host that still contains `%` as malformed (return `""`) is the simple safe choice.
9. Malformed or forbidden characters (space, `<`, `>`, `^`, `|`, `\`, control chars): WHATWG rejects the host. Return `""` rather than a guess. An optional cheap check is a regex of allowed host characters (`[a-z0-9.-]` plus `_`, or an IP literal) applied to the result.
10. Missing or empty Referer, `about:`, `file:`, `data:`, `javascript:` and other schemes: return `""` (no comparable host). Reference does this.
11. Referer is client-controlled. Treat the output as untrusted grouping data, not an identity. Cap the input length before parsing (the DB field limit is a natural cap).

## android-app:// referers

- Format: `android-app://<package-name>[/<scheme>/<host>...]`. The host component is the package name, for example `android-app://com.google.android.googlequicksearchbox/`. A newer form with a path appears for deep links.
- `urlsplit("android-app://com.google.android.gm").hostname` gives `com.google.android.gm`. Package names are lowercase by convention, and the reference lowercases anyway. Package names contain no `www.`, port or trailing dot, so none of the web rules apply. The reference correctly skips `normalised_host` for them.
- The value is set by the sending app and unverified. Use it only for attribution grouping.
- Collision caution: a package name such as `com.example` is indistinguishable from a domain string once both are returned as a bare string. If the downstream classifier needs to tell them apart, return the scheme too, or prefix, for example `android-app:com.x`. This is a design decision for the spec. The reference returns a bare package.

## Assessment of the reference implementation

Good: catches `ValueError` from `urlsplit`, uses `.hostname` (which makes it safe against bad ports), restricts schemes, returns `""` as the "no host" sentinel, and handles an empty hostname.

Gaps to consider (none are bugs for browser-sent referers):
- `normalised_host` is public and splits on the first `:`, which is wrong for bare IPv6 literals and for `http://[::1]` if the string form is ever passed in directly. Either make it private or have it handle IP literals.
- `rstrip(".")` strips many dots, and `www.` alone gives `""`.
- No IDN to punycode step (item 6).
- `.hostname` can raise `ValueError` only inside `urlsplit` here, but reading `.hostname` is inside the `try`, which is correct. Keep it there.
- Android: a missing or empty package gives `""`, which is fine.

## Suggested tests (edge cases)

`HTTPS://WWW.Google.COM:443/x` -> `google.com`; `google.com.` -> `google.com`; `http://user@www.a.com/` -> `a.com`; `http://[::1]:8080/` -> `::1`; `http://[::1/` -> `""` (ValueError); `http://a.com:99999/` -> `a.com` (port ignored); `http://a.com:abc/` -> `a.com`; `http:///x` -> `""`; `google.com` (no scheme) -> `""`; `  http://a.com` -> `a.com`; `android-app://Com.Google.Android.Gm/` -> `com.google.android.gm`; `ftp://a.com` -> `""`; `http://www./` -> `""`; `http://münchen.de/` -> `xn--mnchen-3ya.de` if IDN is adopted; empty string -> `""`.

status: ok
