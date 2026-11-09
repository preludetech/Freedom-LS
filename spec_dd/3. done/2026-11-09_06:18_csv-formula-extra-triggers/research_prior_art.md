# Prior art: widening CSV formula-injection triggers (LF, full-width)

## Here (FLS)

- `csv_safety.py` came from spec `spec_dd/3. done/2026-10-03_05:29_educator-interface-2-panel-framework-tables` (spec section "CSV export", plan "`base/csv_safety.py` (new)"). It moved `FORMULA_TRIGGERS`, `escape_csv_formula` and `UTF8_BOM` out of `site_aware_models/admin_exports.py` so the admin export and the panel-framework export share one helper. Its tests are parametrised over `FORMULA_TRIGGERS` (`base/tests/test_csv_safety.py`).
- Decision on the trigger set: keep it as it was. `research_csv_export.md` (lines ~107-132) took the OWASP list (`= + - @ \t \r`) and said "same trigger characters, same leading-quote mitigation". Only string values are escaped. It did not consider LF or full-width forms.
- `2026-10-29_12:46_more_lead_admin_exports` reused the helper, extended it to header cells, and restated the six-character list. Its `research_best_practices.md` called django-import-export's own escape "weaker than the OWASP guidance" and so kept the project helper. No spec has discussed LF or Unicode lookalikes. This idea is the first.
- Implication: because the parametrised test iterates `FORMULA_TRIGGERS`, adding characters to the tuple widens the tests for free. Because the helper checks only `value[0]`, a value whose first line is clean but which holds a later line starting with a trigger is not covered (see the embedded-newline class below).

## Elsewhere

- OWASP CSV Injection page: the remediation list named only CR (0x0D). A change merged 2025-08-01 (PR #1116, issue #1115) added LF (0x0A), citing Unix newlines and spreadsheets treating `\n` and `\r` alike. The page does not discuss full-width characters in that change. The OWASP page text does mention double-byte variants as a locale risk, and warns that Excel can drop quotes when a file is re-opened.
- Mozilla Bugzilla (2016): bug 1263581 reported a bypass of an earlier CSV-injection fix (bug 1054702) by prefixing the payload with LF (`%0A`). Excel (2007/2013, Unicode import) treated the LF as a row break, so the text after it ran as a formula. It was closed as a duplicate of bug 1259881. A mirrored HackerOne report describes the same 0x0A bypass of a prior fix. The reporter suggested stripping LF from titles. The fix details are not on the page I could read.
- json-2-csv CVE-2026-9673 (fixed in 5.5.11): the sanitizer checked a limited set of leading characters and did not normalise whitespace, control characters or alternative prefixes. The public gist PoC (against 5.5.10) shows leading spaces and full-width `＝` (U+FF1D) getting through. The gist proposes NFKC normalisation then stripping, but its draft regex would strip characters anywhere in the value. That is a third-party PoC. I did not confirm that full-width `＝` actually executes in Excel.
- workglow-dev/sec PR #119 (2026): hardens an escaper against leading whitespace, non-breaking spaces, and trigger characters after embedded newlines inside quoted multi-line cells. Its fix defuses each physical line independently, on the grounds that spreadsheets re-parse each line.
- django-import-export PR #1568 (merged 2023-04-06, issue #1543): added `IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT`, which strips only a leading `=`. I found no reported bypass or widening of it. InvenTree wrote its own override to strip other leading characters.
- Symfony CVE-2021-41270: the tab-prefix fix was later outdated when OWASP added tab and CR. It is an example of the list drifting from the OWASP guidance.
- Not found: any public report or fix for the named products (GitLab, Metabase, Nextcloud, Odoo) about LF or full-width bypasses. I could not verify those either way.

## Takeaways for the spec

- LF has strong precedent (Mozilla/HackerOne bypass, an OWASP update). Full-width has thinner precedent (one CVE with a third-party PoC, and an OWASP mention). Whether Excel/Sheets/LibreOffice really evaluate `＝` is unverified.
- Two approaches exist elsewhere: extend the trigger tuple (First-Class-LMS, OWASP), or NFKC-normalise then test (json-2-csv gist). NFKC covers every compatibility lookalike but changes what the check sees, not the cell contents, if it is used for detection only.
- Leading whitespace (space, NBSP) and later-line triggers are known adjacent bypass classes, outside this idea's stated scope.

## References

- https://owasp.org/www-community/attacks/CSV_Injection
- https://github.com/OWASP/www-community/pull/1116
- https://bugzilla.mozilla.org/show_bug.cgi?id=1263581
- https://bugzilla.mozilla.org/show_bug.cgi?id=1259881
- https://www.sentinelone.com/vulnerability-database/cve-2026-9673/
- https://gist.github.com/whoamins/299745a2d36b482b44e9613b78e40613
- https://github.com/workglow-dev/sec/pull/119
- https://github.com/django-import-export/django-import-export/pull/1568
- https://github.com/inventree/InvenTree/commit/26bf51c20a1c9b3130ac5dd2e17649bece5ff84f
- https://symfony.com/cve-2021-41270

status: ok
