# Research: known complaints about admin data exports

Scope: users and form/application submissions exported from an admin. Confidence is marked per item. Only the items with a URL were actually seen in search results this session. The rest is general knowledge, labelled "unverified here". It is not cited as fact.

## Complaints

| # | Complaint | Evidence | Applies here? |
|---|-----------|----------|---------------|
| 1 | Export ignores the active admin filters, so it exports the whole table. | django-import-export issue #2097, a regression in v4.0.0: the export URL lacked the changelist query params. https://github.com/django-import-export/django-import-export/issues/2097 | Yes. Admins will filter (e.g. by form, status, date) and expect that subset. Export must honour the changelist queryset, including search and filters. |
| 2 | Timeouts or memory blowups on large exports. | The django-import-export FAQ points to django-import-export-celery for long-running exports, and to paging through selections as a workaround. https://django-import-export.readthedocs.io/en/stable/faq.html | Likely at moderate scale. Stream rows with `.iterator()` and use `select_related`/`prefetch_related` (project rule). Avoid per-row queries. Decide up front whether background export is out of scope. |
| 3 | Garbled characters (accents, non-Latin names) when a CSV is opened in Excel. | Unverified here: the search found no source. Widely reported: Excel assumes the local code page unless the UTF-8 file starts with a BOM. | Yes. A learner base likely has non-ASCII names. Either write a UTF-8 BOM for CSV or offer XLSX. Wagtail offers XLSX and CSV (https://guide.wagtail.org/de/how-to/manage-forms/). |
| 4 | CSV/formula injection: a cell starting with `=`, `+`, `-`, `@`, tab or CR executes in Excel. | OWASP https://owasp.org/www-community/attacks/CSV_Injection. A USENIX WOOT25 paper found libraries mostly offer no built-in protection (https://www.usenix.org/conference/woot25/presentation/karl). | Yes, strongly. Anonymous applications are untrusted free text that staff open in Excel. Sanitise every text cell on export (prefix a `'` or similar). Note that a negative number or a phone number starting with `+` is legitimate, so the rule needs care. |
| 5 | Missing or misaligned columns when form questions were edited, added or removed. | Unverified here (general experience with form tools). Wagtail has the same problem space: custom columns need overrides of `get_data_fields`/`get_data` (https://docs.wagtail.org/en/7.1/reference/contrib/forms/customization.html). | Yes. "The full application form" implies the columns come from the form definition. Questions may change between attempts. Decide the column set as the union of the questions across the exported attempts, keyed by a stable question id and not by text. Decide how removed questions appear. |
| 6 | One row per submission versus many rows (long format) confusion. Multi-select answers, repeated questions or related rows end up multiplying rows or cramming values into one cell. | Unverified here (general experience). | Yes. Choose one row per application (wide: one column per question). Document how multi-select values are joined, and which delimiter is used. |
| 7 | Choice answers exported as stored keys/IDs rather than the labels the person saw. | Unverified here. Wagtail docs say choices are a text list but do not say what the export writes (https://guide.wagtail.org/de/how-to/manage-forms/). | Yes. Resolve option to its display text. Consider whether to export both key and label. |
| 8 | Dates and timezones: UTC timestamps, ambiguous formats, or timezone-naive values that Excel reinterprets. | Unverified here. | Yes. Use one documented format (ISO 8601, with the timezone made explicit or converted to the site's timezone). Excel may reformat dates in CSV and leading zeros get dropped from numeric-looking strings (phone numbers, IDs). |
| 9 | Foreign keys exported as numeric IDs (or `str()` of an object) rather than readable names. | Unverified here (a common django-import-export default). | Yes. Users reference cohorts, sites and similar objects. Export a readable name, and maybe the ID as well for re-matching. |
| 10 | Leaking data across tenants/sites: an export action uses an unfiltered manager or a different queryset than the changelist. | Unverified here (general multi-tenant concern). | Yes, important. The project is multi-site (`site_aware_models`). Build the export from the same site-filtered queryset the admin changelist uses, and test that another site's rows never appear. |
| 11 | Anonymous records are dropped or look blank because there is no user to join. | Unverified here. | Yes. Applications include anonymous ones, so user columns must be empty or explicit, not an error or a dropped row. Where identifying fields live on the application itself, they must be exported. |
| 12 | Personal data exported with no control or trace: any staff member can export everything. | Unverified here (general privacy concern). | Probably. Consider a permission check (export permission separate from view) and keep the audit-trail question open. Note that the project says not to add logging unless asked. |

## Sources actually retrieved
- https://github.com/django-import-export/django-import-export/issues/2097
- https://django-import-export.readthedocs.io/en/stable/faq.html
- https://owasp.org/www-community/attacks/CSV_Injection
- https://www.usenix.org/conference/woot25/presentation/karl
- https://guide.wagtail.org/de/how-to/manage-forms/
- https://docs.wagtail.org/en/7.1/reference/contrib/forms/customization.html

## Gaps
Searches did not surface Google Forms/Typeform community threads or LMS forum threads. No source was found for BOM/Excel encoding. Items 3 and 5 to 12 rest on general experience and should be treated as hypotheses to be confirmed in design.

## Suggested priorities for this project
1. Site scoping and honouring changelist filters (items 1, 10).
2. CSV injection and Excel encoding (items 3, 4).
3. Form-definition-driven columns with labels, one row per application (items 5, 6, 7, 11).
4. Readable foreign keys and consistent dates (items 8, 9).
5. Scale behaviour (item 2).

status: ok
