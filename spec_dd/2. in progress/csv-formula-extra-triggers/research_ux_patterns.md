# Research: UX patterns for formula-escaped CSV exports

## Summary

- The standard mitigation (OWASP) is a leading `'` on cells starting with `=`, `+`, `-`, `@`, tab or CR. It is the de facto pattern. The alternative is a leading tab inside the quoted field.
- The apostrophe is a real character in the CSV file. Some spreadsheet apps hide it on display and some show it. See the matrix below, which flags what I confirmed and what I did not.
- The apostrophe does not round-trip. A CSV parser reads it back as ordinary data. `=1+1` goes out as `'=1+1` and comes back as `'=1+1`.
- I found no mainstream tool that documents the escaping to the person downloading the export. This is a gap, not an established pattern.
- Skipping numeric-looking values is a known tradeoff (see below). Plain numbers are not dangerous, but `-5` and `+27...` can only be skipped safely with a strict full-match numeric test.

## Display by application

The notes are from search results only. I did not run hands-on tests, and no source I found covers every application.

| App | Leading `'` from a CSV |
|---|---|
| Excel | Microsoft docs describe the prefix character as cell metadata that is hidden when you type it. A literal `'` inside CSV text is, as I understand it, imported as ordinary text and shown. Not confirmed by a source. Several developer sources claim it is invisible, which conflates typed entry with CSV import. Needs a hands-on check. |
| LibreOffice Calc | Bug reports and forum threads show the apostrophe being kept on text-forced values. One bug was closed as intended. Another OpenOffice report shows inconsistent stripping of a leading apostrophe on non-numeric strings. Behaviour varies by version and import settings. |
| Google Sheets | No source found. Unverified. |
| Numbers | No source found. Unverified. |

Practical consequence for FLS: treat the apostrophe as probably visible in at least some apps. Each newly escaped cell then shows a stray `'` to the person who opens the export. With the new triggers, that covers a cell with a leading LF and a cell with a leading full-width `＝＋－＠`. Examples are Japanese or Chinese text starting with `－`, or multi-line text that begins with a newline.

## Round-trip re-import

- A programmatic parser does not strip the `'`, so the data is altered on re-import.
- OWASP warns the `'` mitigation may not stay reliable in Excel after save and reopen, because Excel may drop quotes or escape characters and reactivate the formula.
- The tab-prefix alternative leaves the tab in the data. OWASP says that suits files meant for human viewing and can affect programmatic imports.
- The advice from developer sources is to sanitise untrusted, user-facing exports. Skip it only for strict machine-to-machine exports that must round-trip exactly.

## Documenting the escaping to the downloader

I found no tool that documents it. The only mention is in developer-facing PR and code comments, and OWASP does not suggest a UI note. Options for FLS, as ideas rather than established patterns:
- A short note by the export button, or a note in the docs.
- A stable single-character marker, so a consumer can strip it deliberately.

## Skip escaping for pure numbers?

- OWASP's page does not treat numbers as a separate case. `-` and `+` are on its trigger list regardless.
- Skipping is only safe with a strict full-match test, for example `^[+-]?\d+(\.\d+)?$`. Anything looser, such as `-5+cmd|...`, is a payload.
- A `+27...` phone number is the awkward case. Prefixing it makes Excel show text `'+27...`. Leaving it makes Excel read it as a number or formula and drop the `+`. A phone number can also carry spaces or brackets, which would then fail a numeric test and be escaped anyway.
- The existing helper escapes `-5`. Extending the skip to numbers is a behaviour change beyond the idea's scope ("add triggers"). It should be an explicit decision in the spec.

## Open items for the spec

- Hands-on check of Excel, Calc, Sheets and Numbers with `'－テスト` and `'\nfoo`.
- Decide whether the numeric exemption is in scope.

## References

- OWASP CSV Injection: https://community.owasp.org/attacks/CSV_Injection
- OWASP WSTG, Testing for CSV Injection: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection
- TimeTrackerAPI PR #266 (apostrophe invisibility and round-trip claims): https://github.com/CryptoJones/TimeTrackerAPI/pull/266
- CSV Formula Injection in AI Exports: https://aident.ai/blog/csv-formula-injection-ai-exports
- Microsoft Q&A on prefix character: https://learn.microsoft.com/en-us/answers/a/9851336
- LibreOffice bug 99374: https://www.libreoffice.org/bugzilla/show_bug.cgi?id=99374
- OpenOffice issue 60110: https://bz-he-de.apache.org/ooo/show_bug.cgi?id=60110
- OpenOffice issue 65510: https://issues.apache.org/ooo/show_bug.cgi?id=65510

status: ok
reason: Google Sheets and Numbers display behaviour not found in sources; Excel CSV-import display not confirmed; flagged for hands-on verification
