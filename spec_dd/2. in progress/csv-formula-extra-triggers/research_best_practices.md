# Research: best practices for CSV formula-injection neutralisation

Sourced claims cite the References list. Items marked (unverified) come from general knowledge, not from a fetched source.

## Canonical trigger list
- OWASP CSV Injection lists `=`, `+`, `-`, `@` as the formula triggers, plus tab (0x09) and carriage return (0x0D) [1].
- The current OWASP page also lists line feed / newline as a trigger [1]. It lists the full-width forms `＝ ＋ － ＠` as formulas "in some locales (e.g. Japanese)" [1][2].
- So the idea's extra set (LF plus the four full-width characters) matches the current OWASP list exactly. The search result text did not show the code points. The page's glyphs are the full-width ones; confirm the exact code points in the page source if needed.
- CWE-1236 ("Improper Neutralization of Formula Elements in a CSV File") is the weakness class. It names the same leading characters [3] (unverified detail).

## Is LF / full-width recognised?
- OWASP names both, with locale dependence for full-width [1]. No fetched source gives a reproducible Excel/LibreOffice/Sheets test for U+FF1D.
- A user-submitted gist reports a "Fullwidth Equals" bypass against json-2-csv 5.5.10 and a whitespace-prefix bypass. It is unverified, and its payload was not readable [4].
- Related: exceljs before 5.0.0 was reported (CVE-2026-78209) for not neutralising leading `=`, `+`, `-`, `@` [5].
- (unverified) Excel's CJK input and autocorrect can convert full-width ASCII, so treating them as triggers is cheap defence in depth.

## First character only, or after leading whitespace?
- OWASP's wording concerns the first character of the cell [1]. It also notes that attackers can inject separators and quotes to start a new cell, so the trigger lands at the start of a cell [1]. The fix is to proper-quote the field (RFC 4180 CSV writer), not to scan mid-string.
- Tab and CR are triggers precisely because they act as leading whitespace [1].
- The gist reports a leading-character regex missing a trigger after whitespace [4]. Recommended approach: check the first character only. Do not skip leading whitespace, because tab, CR and LF are already triggers. Consider also checking after other leading whitespace (space, U+00A0) as an optional hardening step (unverified; Excel typically trims leading spaces in formula entry but not for imported text).

## Quoting rules
- Wrap fields in double quotes and double any internal quotes [1]. This stops a cell being split, but does not by itself stop formulas [1].
- OWASP warns that Excel may drop quotes or escape characters when a file is saved and reopened, which can re-arm formulas [1].

## `'` prefix vs tab prefix
- OWASP lists both: prepend a single quote [1], or prepend a tab inside the quoted field for Excel resistance [1]. The tab stays in the data and can break programmatic imports, so OWASP suggests it for files meant for human viewing [1].
- The `'` prefix is the common choice for mixed use; the apostrophe is visible in non-Excel consumers (unverified). FLS already uses `'`, and nothing found argues for changing it.

## Other Unicode lookalikes
- None of the fetched authorities lists U+FE62 (small plus), U+FE63 (small hyphen-minus), U+2212 (minus sign), U+FE66 (small equals), U+FE6B (small at) or full-width `｜` (U+FF5C). OWASP names only the four full-width ASCII twins [1].
- (unverified) Only NFKC-compatible forms are plausible risks if an application normalises input. U+FE62, U+FE63, U+FE66, U+FE6B and the full-width forms all NFKC-fold to ASCII; U+2212 does not. Spreadsheets do not generally NFKC-fold on load, so these are low risk. Adding the small-form variants is optional hardening, not an established recommendation.
- `|` is a DDE-style trigger only after `=`, `+`, `-`, `@`; a leading `|` is not in OWASP's list.

## Trade-off with numeric values like "-5"
- Prefixing every leading `-` or `+` turns genuine negative numbers into text in the spreadsheet [1]. OWASP's list does not exempt numbers.
- Common mitigations (unverified): pass real numeric types without escaping (escape only strings); or exempt strings matching a strict numeric pattern such as `^[+-]?\d+(\.\d+)?$`. The exemption is risky: `-5+cmd|...` must not match, so anchor the pattern fully. Most libraries escape strings only and leave numbers alone.
- Recommendation for this idea: keep escaping string cells; apply the escape only to str values; do not add a numeric exemption unless asked.

## Recommendation summary
1. Add LF (`\n`) and U+FF1D, U+FF0B, U+FF0D, U+FF20 to the trigger set. This matches OWASP [1].
2. Keep check-first-character-only and keep the `'` prefix.
3. Keep proper CSV quoting in the writer; do not rely on it alone.
4. Small-form lookalikes (U+FE62, U+FE63, U+FE66, U+FE6B), U+2212 and `｜` are not recommended by any authority found; leave out unless the spec wants extra hardening.

## References
1. OWASP CSV Injection: https://community.owasp.org/attacks/CSV_Injection (redirected from https://owasp.org/www-community/attacks/CSV_Injection)
2. OWASP WSTG, Testing for CSV Injection: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection
3. CWE-1236: https://cwe.mitre.org/data/definitions/1236.html (not fetched)
4. json-2-csv bypass gist (user-submitted, unverified): https://gist.github.com/whoamins/299745a2d36b482b44e9613b78e40613
5. exceljs CVE-2026-78209 (OSV): https://api.osv.dev/v1/vulns/CVE-2026-78209

status: ok
