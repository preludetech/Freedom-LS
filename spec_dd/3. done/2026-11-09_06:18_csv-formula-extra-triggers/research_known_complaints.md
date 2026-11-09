# Research: known complaints about CSV formula-injection escaping

Scope: web search (two queries). Evidence is thin on CJK-specific complaints and opt-out requests; none found.

## Complaints found

1. **Negative numbers get a leading apostrophe.** Atlassian Jira export started prefixing negative values after a security fix; the workaround is a feature flag that reopens the hole [3]. A Clojure CSV library notes the same and that a "+"-leading email changes value on re-read [1].
2. **Phone numbers / "+" and "-" in legitimate data.** Avni Server proposed a quote-plus-tab prefix removed on import so phone and negative numbers survive [2]. Stripping the characters is not a fix because real data has them [4].
3. **Round trip is lossy.** Jackson maintainer: cannot sensibly strip a leading minus from general data; the fix is application-specific [6]. Mitigation seen: prefix only when a cell has a dangerous symbol plus more than one number [7]. No source shows a reliable exact round trip.
4. **Incompleteness / bypasses.**
   - OWASP says checking only the first character is not sufficient. It lists full-width variants (risk in e.g. Japanese locales) and line feed [5][8].
   - OWASP notes Excel may strip quotes/escape characters on re-save, re-activating formulas [5].
   - One project (self-reported, unverified) fixed misses on leading whitespace, NBSP, and characters after embedded newlines in quoted cells [9].
5. **Not found:** spurious apostrophes for CJK users, explicit opt-out requests.

## Effect of this change (LF + full-width `＝＋－＠`)

- **Better:** closes the incompleteness complaint (item 4) for LF and full-width forms, as OWASP lists them.
- **Worse (small):** more cells get a visible `'` and lose exact round trip. Cells starting with full-width `－`/`＋` (CJK text, e.g. full-width minus in numbers) now gain an apostrophe, plausible but unreported spurious-apostrophe cases. Cells starting with LF are rare, so low impact.
- **Unchanged:** `-` and `+` negative numbers and phone numbers (+27...) are already prefixed; complaints 1-3 persist and this change does not address them. Whitespace-prefix and zero-width bypasses (item 4, unverified) remain open; consider noting as out of scope or follow-up.

## References

1. https://cljdoc.org/d/dev.arkaitz/web-base/0.22.0/api/dev.arkaitz.web-base.csv
2. https://github.com/avniproject/avni-server/issues/695
3. https://jira.atlassian.com/browse/JRASERVER-77480
4. https://dev.to/abdurrahmanhassan/how-i-prevented-csv-injection-attacks-in-a-qr-batch-generator-and-why-you-should-care-6en
5. https://owasp.org/www-community/attacks/CSV_Injection
6. https://github.com/FasterXML/jackson-dataformats-text/issues/326
7. https://help.expedientsoftware.com.au/?p=17328
8. https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection
9. https://github.com/workglow-dev/sec/pull/119

status: ok
