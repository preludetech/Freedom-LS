# Research: reference implementations for exporting users and application submissions from an admin

Question: how do reference implementations export users and form/application submissions, with full question-and-answer data, from an admin?

Items marked (verified) were read from the cited source in this session. Items marked (from memory) were not re-verified here and should be checked before the spec relies on them.

## Already in the project

- `pyproject.toml` installs `django-unfold>=0.83.0` and `django-import-export>=4.4.1` (tablib comes with it). It has no wagtail, formtools, forms-builder or fobi.
- `freedom_ls/site_aware_models/admin_exports.py` is an existing in-project export layer built on django-import-export (verified):
  - `FormulaSafeCSV(CSV)` escapes every string cell against formula injection and prepends a UTF-8 BOM. Headers are not escaped.
  - `IsoDateTimeWidget` and `IsoDateWidget` render ISO 8601 whatever the settings say.
  - `SiteAwareModelResource(ModelResource)` drops the `site` column and swaps in the ISO widgets.
- `freedom_ls/referral_tracking/resources.py` and its tests already use this pattern (listed by grep, not read).
- Conclusion: new exports should reuse this layer rather than adopt a new library.

## 1. django-import-export (admin integration)

Source: https://django-import-export.readthedocs.io/en/latest/admin_integration.html (verified)

- Admin classes: `ImportExportModelAdmin` is the list-page export button. `ExportActionMixin` adds an export bulk action, so the admin can export only the selected rows. "Go" opens an export confirm page.
- Multi-tenant caution: restrict exportable records with `get_export_queryset()`. This matters here because the project is site-aware.
- Resource choice: `get_export_resource_classes()` can return several resources. The admin then shows a resource chooser, and the name comes from `Meta.name`. One model can therefore offer, for example, "Applications (summary)" and "Applications (full form)".
- Dynamic filtering: override `get_export_resource_kwargs()` to pass export-form values into the Resource constructor. The Resource then narrows its queryset in `filter_export()`. `export_form_class` can be subclassed to add filters such as date range or form.
- Formats: `IMPORT_EXPORT_FORMATS` and `EXPORT_FORMATS` limit the offered formats (CSV, XLSX, JSON, and others via tablib).
- Security: `IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT` escapes formulas, but only for exports made through the admin. Programmatic exports need their own sanitising. The project already has `FormulaSafeCSV` for this.
- Large exports: action-based exports of many rows can hit Django's `TooManyFieldsSent` (raise `DATA_UPLOAD_MAX_NUMBER_FIELDS`). The docs do not describe streaming or background export.
- Dynamic columns (from memory, not verified here): django-import-export's `Resource.get_export_fields()` and `export_field` hooks let a Resource build fields at runtime. A common pattern is to add `Field(column_name=..., attribute=...)` entries in `__init__`, or to override `export()` and `get_export_headers()` to append one column per question. For columns that do not map to a model attribute, use `dehydrate_<name>` methods or a `Field` with a callable.

## 2. django-unfold integration

Source: https://unfoldadmin.com/docs/integrations/django-import-export/ (verified)

- Add `unfold.contrib.import_export` at the top of `INSTALLED_APPS` so its templates override the package's.
- The admin combines `unfold.admin.ModelAdmin` with `ImportExportModelAdmin`.
- Set `import_form_class = ImportForm` and `export_form_class = ExportForm` or `SelectableFieldsExportForm`, from `unfold.contrib.import_export.forms`. `SelectableFieldsExportForm` lets the user pick which fields to export.
- `unfold.contrib.import_export.admin.ExportActionModelAdmin` was only needed on older versions. In django-import-export 4.x the action form is styled natively.
- Unfold adds no export logic of its own, only styling and forms.

## 3. Wagtail form submissions CSV/XLSX export

Source: https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/contrib/forms/views.py (verified)

- Column layout: the columns come from the form's current field definitions (`form_page.get_data_fields()`), not from the stored submissions. `to_row_dict` builds one row per submission using `item.get_data().get(field_name)`.
- Submission data is stored as JSON keyed by field name. Headers use the current field labels.
- Changed or deleted fields: there is no explicit handling in that excerpt.
  - A submission that lacks a key gets `None` in that column.
  - A field deleted from the form disappears from the export, even though old submissions still hold its answers.
  - A renamed field loses its old answers. Keys are names, so a renamed field gives a new, empty column.
  - This is the failure mode the spec should avoid or accept deliberately.
- Filters: `SubmissionsListFilterSet` filters by a `date` range on `submit_time`. The export uses the filtered, ordered queryset. Only `id` and `submit_time` can be ordered, and exports default to ascending `submit_time`.
- Extra columns: the excerpt adds no submit-date column to the export. The filename uses today's date. (From memory: Wagtail does add a "Submission date" column to the list view.)
- Formats: CSV and XLSX, chosen by an `export` query parameter through `SpreadsheetExportMixin` (not read).

## 4. django-forms-builder, django-fobi, django-formtools

All from memory, not verified here.

- django-forms-builder: the admin exports entries to CSV or XLS. Columns are the form's current fields in order, plus a timestamp, and each entry stores field-value rows. Field values are stored per field (`FieldEntry`), so a deleted field's values are dropped from the export, though they may still exist in the database. It has filters by date range.
- django-fobi: it has a "save data" handler plugin and an export in the admin. The columns are the form's elements, with a saved-data JSON per submission.
- django-formtools: a wizard and preview library with no storage or export. It is not relevant.
- Common pattern across all of them: one row per submission, one column per current question, a fixed leading set of metadata columns (id, timestamp), and a `None` or blank cell for a missing answer.

## 5. LMS exports (Moodle, Canvas, Open edX)

All from memory. A fetch of the Moodle docs URL returned 404, so none of this is verified.

- Moodle:
  - Feedback and Questionnaire responses can be downloaded as CSV or Excel. The shape is one row per response, one column per question, with user details and a timestamp up front. Anonymous feedback omits the identity columns.
  - User lists can be downloaded as CSV, XLSX, ODS or JSON from Site administration > Users > Browse list of users, with the chosen user fields and filters.
- Canvas: the gradebook and the "Download Course Content" exports are CSV. Survey results are a CSV with one row per student and one column per question. The survey report uses the question text as the header.
- Open edX: the instructor dashboard offers CSV downloads such as "enrolled students profile information", which has one row per learner and fixed columns, and "problem responses". A problem-response report produces a row per learner per answer, with the answer in JSON. This is an example of a long-format alternative to wide columns.

## 6. Google Forms, Typeform, Jotform response export shape

- Google Forms: responses are exported to CSV or to a linked Google Sheet. Layout is one row per response, a "Timestamp" column first, then one column per question with the question title as the header. The API says `answers` is a map keyed by questionId (verified: https://developers.google.com/forms/api/reference/rest/v1/forms.responses). The page does not say what happens to answers for deleted questions. (From memory: the Sheet keeps an old column for deleted questions, and duplicates the column when a question is renamed.)
- Typeform: results download as CSV or XLSX, one row per response, one column per question, with metadata columns such as Response ID, Submitted At, Network ID. Typeform CSV exports for forms with edited questions keep old columns (from memory).
- Jotform: Submissions table exports to Excel, CSV, PDF and others. Columns are the fields, plus "Submission Date" and a submission ID. It has a "Download all as PDF" option for the full filled form (from memory).
- Common pattern: wide format, one row per submission, the question text as header, a timestamp and ID up front, and optionally a PDF per submission for the full-form view.

## Comparison and design options for FLS

| Question | What the references do | Relevance to FLS |
|---|---|---|
| Variable question sets | Wide: one column per current question (Wagtail, forms-builder, Google, Typeform, Jotform, Moodle). Long: one row per answer (Open edX problem reports). | Wide is the norm and is what a human reading a spreadsheet expects. Long is more robust where questions differ between forms. |
| Changed or deleted questions | Wagtail drops deleted fields and starts a fresh column on rename. Google and Typeform keep stale columns (from memory). | Decide whether to snapshot the form at submission time, or use the union of questions seen across the exported submissions. Not decided here. |
| Several different forms in one export | Wagtail and Google export per form only. | Either require the user to filter to one form, or offer a long-format export. Open question for the spec. |
| Anonymous submissions | Moodle anonymous feedback omits identity columns. | The identity columns should be blank, not error. |
| File format | CSV and XLSX are the usual pair. JSON and ODS are offered by Moodle and tablib. | Existing `FormulaSafeCSV` plus tablib's XLSX. Check whether XLSX also needs formula escaping. |
| Filters | Date range (Wagtail), selected rows (ExportActionMixin), form (forms-builder). | `ExportActionMixin` for selected rows, the admin changelist filters for the rest, and the export form class for extra fields. |
| Security | Formula escaping on export. | Already solved in `admin_exports.py`. |
| Tenancy | `get_export_queryset()` is the documented hook. | Site-aware models filter by site, but the export queryset must be confirmed to stay inside the current site. |

## Reference URLs

- https://django-import-export.readthedocs.io/en/latest/admin_integration.html
- https://django-import-export.readthedocs.io/en/latest/getting_started.html
- https://unfoldadmin.com/docs/integrations/django-import-export/
- https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/contrib/forms/views.py
- https://developers.google.com/forms/api/reference/rest/v1/forms.responses
- https://docs.moodle.org/en/Download_feedback_responses (returned 404, unverified)

status: ok
